#!/usr/bin/env python3
"""Bounded, optional editing-device observations; never repair or accept a run.

Connect only to the existing local ADB server. Unlike an adb CLI invocation,
these read-only smart-socket services cannot start a daemon or reconnect a
device. Never store arbitrary command output, SSIDs, addresses or credentials.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import signal
import socket
import stat
import struct
import subprocess
import time
from itertools import islice
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = 'local.pocketchat.test'
SERIAL = 'emulator-5554'
MAX_TOTAL_SECONDS = 60
MAX_COMMAND_SECONDS = 4
MAX_STDOUT_BYTES = 131072
MAX_REPORT_BYTES = 16384
MAX_EVENTS = 32
PREFIX = 'EDITING_TRANSPORT13_DIAGNOSTIC '
COMMANDS = {
    'qemu': ('getprop', 'ro.kernel.qemu'),
    'user': ('am', 'get-current-user'),
    'package': ('pm', 'path', PACKAGE),
    'wifi': ('cmd', 'wifi', 'status'),
    'connectivity': ('dumpsys', 'connectivity'),
    'events': ('logcat', '-d', '-v', 'threadtime', '-t', '400', '-s', 'IpClient/wlan0:V',
               'wpa_supplicant:I', 'adbd:I', 'WifiService:V', 'WifiNative:V',
               'wificond:I', 'ConnectivityService:I', 'netd:I', '*:S'),
}


class Unavailable(RuntimeError):
    pass


def require(value, code):
    if not value:
        raise Unavailable(code)


def identity_from_environment(env, head, tree, dirty):
    if (env.get('CI') != 'true' or env.get('GITHUB_ACTIONS') != 'true'
            or env.get('GITHUB_SERVER_URL') != 'https://github.com'
            or env.get('GITHUB_REPOSITORY') != 'Ararataki-number-one/yuanying-chat'
            or env.get('GITHUB_JOB') != 'android' or env.get('POCKET_EDITING_TRANSPORT_PHASE') != 'editing'
            or env.get('POCKET_EDITING_TRANSPORT_OUTCOME') not in ('success', 'failure', 'cancelled', 'skipped')
            or not isinstance(head, str) or re.fullmatch('[0-9a-f]{40}', head) is None
            or not isinstance(tree, str) or re.fullmatch('[0-9a-f]{40}', tree) is None
            or env.get('GITHUB_SHA') != head or dirty != b''):
        return None
    if not all(isinstance(env.get(k), str) and re.fullmatch('[1-9][0-9]{0,19}', env[k])
               for k in ('GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT')):
        return None
    return dict(sourceCommit=head, sourceTree=tree, runId=env['GITHUB_RUN_ID'],
                runAttempt=env['GITHUB_RUN_ATTEMPT'], phase='editing',
                editingOutcome=env['POCKET_EDITING_TRANSPORT_OUTCOME'])


def remaining(deadline):
    value = deadline - time.monotonic()
    require(value > 0, 'total-budget-exhausted')
    return min(MAX_COMMAND_SECONDS, value)


def source_identity(root, env, deadline):
    # Reject absent workflow ownership before even inspecting Git or ADB.
    if (env.get('CI') != 'true' or env.get('GITHUB_JOB') != 'android'
            or env.get('POCKET_EDITING_TRANSPORT_PHASE') != 'editing'):
        return None
    def git(*parts):
        process_env = dict(os.environ, GIT_NO_LAZY_FETCH='1', GIT_OPTIONAL_LOCKS='0', GIT_TERMINAL_PROMPT='0')
        value = subprocess.run(['git', '--no-replace-objects', *parts], cwd=root, env=process_env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=remaining(deadline))
        require(value.returncode == 0 and len(value.stdout) <= 65536, 'source-unavailable')
        return value.stdout
    head = git('rev-parse', 'HEAD').decode().strip()
    tree = git('rev-parse', 'HEAD^{tree}').decode().strip()
    dirty = git('status', '--porcelain', '--untracked-files=no').strip()
    return identity_from_environment(env, head, tree, dirty)


def ordinary_bytes(path, limit):
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'unsafe-local-input')
    with path.open('rb') as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_size <= limit, 'local-input-bound')
        value = stream.read(limit + 1)
    require(len(value) <= limit, 'local-input-bound')
    return value


def apk_identity(root, identity, deadline):
    remaining(deadline)
    receipt = json.loads(ordinary_bytes(root / 'work/gecko-integration/caret-apk-build-receipt.json', 65536))
    # The real caret build receipt has sourceCommit/runId/runAttempt; its
    # sourceTree is supplied by the actual integration APK stamp below.
    require(all(receipt.get(k) == identity[k] for k in ('sourceCommit', 'runId', 'runAttempt')), 'build-source-run-mismatch')
    apk = root / 'app/build/outputs/apk/integration/app-x86_64-integration.apk'
    require(not any(p.is_symlink() for p in (apk, *apk.parents)), 'unsafe-apk')
    require(apk.is_file() and 0 < apk.stat().st_size <= 256 * 1024 * 1024, 'apk-bound')
    digest = hashlib.sha256()
    with apk.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            remaining(deadline)
            digest.update(block)
    require(digest.hexdigest() == receipt.get('integrationApkSha256'), 'local-apk-digest-mismatch')
    with ZipFile(apk) as archive:
        name = 'assets/pocketchat-integration-build.json'
        require(archive.namelist().count(name) == 1 and archive.getinfo(name).file_size <= 65536, 'apk-stamp-bound')
        stamp = json.loads(archive.read(name))
    require(stamp.get('schema') == 1 and stamp.get('dirtySource') is False
            and all(stamp.get(k) == identity[k] for k in ('sourceCommit', 'sourceTree')),
            'apk-source-mismatch')
    return dict(apkSha256=digest.hexdigest(), apkBytes=apk.stat().st_size)


class ExistingAdb:
    """Read-only smart socket + shell-v2; never invoke or create an adb server."""
    def __init__(self, deadline):
        self.deadline = deadline

    @staticmethod
    def recv(stream, length, deadline):
        value = bytearray()
        while len(value) < length:
            stream.settimeout(remaining(deadline))
            chunk = stream.recv(length - len(value))
            require(chunk, 'adb-stream-closed')
            value.extend(chunk)
        return bytes(value)

    def request(self, stream, service, deadline):
        encoded = service.encode('ascii')
        stream.settimeout(remaining(deadline))
        stream.sendall(('%04x' % len(encoded)).encode() + encoded)
        require(self.recv(stream, 4, deadline) == b'OKAY', 'adb-service-unavailable')

    def connect(self, deadline):
        return socket.create_connection(('127.0.0.1', 5037), timeout=remaining(deadline))

    def online(self):
        deadline = min(self.deadline, time.monotonic() + MAX_COMMAND_SECONDS)
        with self.connect(deadline) as stream:
            self.request(stream, 'host:devices-l', deadline)
            length = int(self.recv(stream, 4, deadline), 16)
            require(length <= 8192, 'adb-device-list-bound')
            raw = self.recv(stream, length, deadline).decode('utf-8')
        rows = [line.split() for line in raw.splitlines() if line.split()[:1] == [SERIAL]]
        require(len(rows) == 1 and len(rows[0]) >= 2 and rows[0][1] == 'device', 'native-device-not-online')

    def read(self, parts):
        require(parts in COMMANDS.values() or (len(parts) == 2 and parts[0] == 'sha256sum'
                and re.fullmatch('/data/app/[A-Za-z0-9_./=+~-]+/base[.]apk', parts[1])), 'command-not-allowed')
        deadline = min(self.deadline, time.monotonic() + MAX_COMMAND_SECONDS)
        with self.connect(deadline) as stream:
            self.request(stream, 'host:transport:' + SERIAL, deadline)
            self.request(stream, 'shell,v2,raw:' + shlex.join(parts), deadline)
            output, stderr_bytes = bytearray(), 0
            while True:
                channel, length = struct.unpack('<BI', self.recv(stream, 5, deadline))
                require(channel in (1, 2, 3) and length <= MAX_STDOUT_BYTES, 'adb-shell-frame-bound')
                if channel == 1:
                    require(len(output) + length <= MAX_STDOUT_BYTES, 'stdout-bound')
                elif channel == 2:
                    require(stderr_bytes + length <= 8192, 'stderr-bound')
                else:
                    # AOSP shell_protocol.h: uint8 ID + uint32 length; adbd's
                    # daemon/shell_service.cpp writes kIdExit with length1.
                    # Official source: aosp-mirror/platform_system_core,
                    # android-10.0.0_r47/adb/daemon/shell_service.cpp:751-752.
                    require(length == 1, 'adb-shell-exit-format')
                payload = self.recv(stream, length, deadline)
                if channel == 1:
                    output.extend(payload)
                elif channel == 2:
                    stderr_bytes += length  # Untrusted stderr is never stored or echoed.
                else:
                    require(int.from_bytes(payload, 'little') == 0, 'adb-command-unavailable')
                    return bytes(output).decode('utf-8', errors='replace')


def project_wifi(raw):
    enabled = re.findall(r'^Wi-?Fi is (enabled|disabled)\s*$', raw, re.M | re.I)
    return dict(status='observed', enabled=enabled[0].lower() == 'enabled') if len(enabled) == 1 else dict(status='unavailable', reasonCode='format-unrecognized')


def project_connectivity(raw):
    defaults = re.findall(r'^\s*Active default network:\s*(none|[0-9]{1,10})\s*$', raw, re.M)
    transports = set()
    for value in re.findall(r'\bTransports: ([A-Z_ |]+?)(?: Capabilities:|\])', raw):
        transports.update(word for word in re.split('[ |]+', value) if word in ('WIFI', 'CELLULAR', 'ETHERNET', 'VPN', 'BLUETOOTH'))
    transports = sorted(transports)
    result = dict(status='observed', observedTransportEnums=transports)
    if len(defaults) == 1:
        result['activeDefaultNetworkId'] = None if defaults[0] == 'none' else int(defaults[0])
    return result


def project_events(raw):
    selected = []
    modules = {'IpClient/wlan0', 'wpa_supplicant', 'adbd', 'WifiService', 'WifiNative', 'wificond', 'ConnectivityService', 'netd'}
    for line in raw.splitlines():
        match = re.fullmatch(r'(\d\d-\d\d \d\d:\d\d:\d\d[.]\d{3})\s+(\d+)\s+(\d+)\s+[VDIWEF]\s+([^:]+):\s*(.*)', line)
        if not match or match[4].strip() not in modules:
            continue
        module, body = match[4].strip(), match[5]
        event = None
        if module == 'IpClient/wlan0' and 'interfaceLinkStateChanged:' in body:
            value = re.fullmatch(r'interfaceLinkStateChanged: ifindex (\d+) (up|down)', body)
            if value: event = dict(kind='interface-link', state=value[2], interfaceIndex=int(value[1]))
        elif module == 'wpa_supplicant' and 'CTRL-EVENT-DISCONNECTED' in body:
            value = re.search(r'\breason=(\d{1,5}) locally_generated=([01])(?:\s|$)', body)
            if value: event = dict(kind='wifi-disconnected', reason=int(value[1]), locallyGenerated=value[2] == '1')
        elif module == 'wpa_supplicant' and 'CTRL-EVENT-CONNECTED' in body:
            event = dict(kind='wifi-connected')
        elif module == 'adbd' and any(value in body for value in ('connection terminated:', ': offline', ': already offline', 'authentication not required')):
            event = dict(kind='adb-transport', state='offline' if 'offline' in body or 'connection terminated:' in body else 'handshake')
        elif module == 'wificond' and 'Regulatory domain changed to country:' in body:
            event = dict(kind='regulatory-domain-change')
        elif module == 'netd' and 'Destroyed ' in body:
            value = re.search(r'\bDestroyed (\d{1,8}) sockets\b', body)
            if value: event = dict(kind='sockets-destroyed', count=int(value[1]))
        elif module == 'ConnectivityService' and 'DISCONNECTED' in body:
            event = dict(kind='connectivity-disconnected')
        elif module == 'WifiService':
            value = re.fullmatch(r'(setWifiEnabled|disconnect|reconnect|reassociate|startScan).*\b(?:uid|Uid|UID)[=: ]+(\d{1,8})(?:\D.*)?', body)
            if value and int(value[2]) <= 199999: event = dict(kind='wifi-api-call', operation=value[1], callerUid=int(value[2]))
        if event is not None:
            event.update(timestamp=match[1], module=module, pid=int(match[2]), tid=int(match[3]))
            selected.append(event)
    return dict(status='observed', totalMatched=len(selected), events=selected[-MAX_EVENTS:], omitted=max(0, len(selected) - MAX_EVENTS))


def host_health(root, deadline):
    # Same-process observation of this editing job, never a generic later-phase
    # merged runner-health file. Only typed memory/process facts are emitted.
    def read(path, limit):
        remaining(deadline)
        with path.open('rb') as stream:
            raw = stream.read(limit + 1)
        require(len(raw) <= limit, 'host-input-bound')
        return raw
    result, memory = {}, {}
    for line in read(Path('/proc/meminfo'), 8192).decode().splitlines():
        fields = line.split()
        if len(fields) == 3 and fields[0] in ('MemTotal:', 'MemAvailable:', 'SwapTotal:', 'SwapFree:') and fields[1].isdigit() and fields[2] == 'kB':
            memory[fields[0][:-1] + 'KiB'] = int(fields[1])
    result['memory'] = memory
    candidates = []
    for path in islice(Path('/proc').iterdir(), 8192):
        remaining(deadline)
        if not path.name.isdigit(): continue
        try:
            if not read(path / 'comm', 128).decode().strip().startswith('qemu-system-x86'): continue
            raw = read(path / 'cmdline', 8192)
            args = raw.split(b'\0')
            if not args or Path(os.fsdecode(args[0])).name not in ('qemu-system-x86_64-headless', 'qemu-system-x86_64'): continue
            if not (b'-avd' in args and args[args.index(b'-avd') + 1] == b'geckoproduction' and b'-port' in args and args[args.index(b'-port') + 1] == b'5556'): continue
            monitor = b'unix:' + os.fsencode(root / 'work/gecko-integration/qemu-monitor.sock') + b',server=on,wait=off'
            if not (b'-monitor' in args and args[args.index(b'-monitor') + 1] == monitor): continue
            fields = read(path / 'stat', 4096).decode().rsplit(')', 1)[1].split()
            if fields[0] not in ('R', 'S', 'D', 'T', 'Z', 'I'): continue
            candidates.append(dict(pid=int(path.name), state=fields[0], startTicks=int(fields[19]), residentPages=int(fields[21])))
        except (OSError, ValueError, IndexError):
            continue
    result['qemu'] = dict(status='observed', **candidates[0]) if len(candidates) == 1 else dict(status='unavailable', reasonCode='qemu-owner-not-unique')
    return result


def collect(root, env, serial):
    started = time.monotonic()
    deadline = started + MAX_TOTAL_SECONDS
    result = dict(schema=1, diagnosticOnly=True, releaseAcceptance=False, applicationAcceptance=False,
                  originalEditingAcceptance=False, physicalPhoneAcceptance=False, status='unavailable',
                  reasonCode='identity-unavailable', actualCommands=False, deviceIdentityConfirmed=False,
                  serverInspectionAttempted=False, totalBudgetSeconds=MAX_TOTAL_SECONDS,
                  transport='existing-adb-server-read-only-shell-v2', commands=[])
    try:
        identity = source_identity(root, env, deadline)
        if identity is None: return result
        result['identity'] = identity
        require(serial == SERIAL, 'serial-unavailable')
        apk = apk_identity(root, identity, deadline)
        result['host'] = host_health(root, deadline)
        remaining(deadline)
        connection = ExistingAdb(deadline)
        result['serverInspectionAttempted'] = True
        connection.online()
        result['actualCommands'] = True  # Actual read-only guest command attempts, not acceptance.
        require(connection.read(COMMANDS['qemu']).strip() == '1', 'qemu-unconfirmed')
        require(connection.read(COMMANDS['user']).strip() == '0', 'user-unconfirmed')
        paths = connection.read(COMMANDS['package']).splitlines()
        require(len(paths) == 1 and re.fullmatch('package:/data/app/[A-Za-z0-9_./=+~-]+/base[.]apk', paths[0]), 'installed-apk-path-unconfirmed')
        installed = paths[0][len('package:'):]
        device_digest = connection.read(('sha256sum', installed)).strip()
        require(re.fullmatch('[0-9a-f]{64}  ' + re.escape(installed), device_digest) and device_digest[:64] == apk['apkSha256'], 'installed-apk-unconfirmed')
        result.update(deviceIdentityConfirmed=True, package=PACKAGE, serial=SERIAL, apkSha256=apk['apkSha256'], actualCommands=True)
        for name, projector in (('events', project_events), ('wifi', project_wifi), ('connectivity', project_connectivity)):
            row = dict(name=name, status='unavailable')
            try:
                raw = connection.read(COMMANDS[name])
                result[name] = projector(raw)
                row.update(status='observed', stdoutBytes=len(raw.encode('utf-8')))
            except Exception as error:
                row['reasonCode'] = str(error) if isinstance(error, Unavailable) else type(error).__name__
            result['commands'].append(row)
        remaining(deadline)
        result.update(status='available', reasonCode='bounded-observations-only')
    except Exception as error:
        result['reasonCode'] = str(error) if isinstance(error, Unavailable) else type(error).__name__
    finally:
        result['elapsedMillis'] = int((time.monotonic() - started) * 1000)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', required=True, help='Original workflow interface; the CLI is never executed')
    parser.add_argument('--serial', required=True)
    args = parser.parse_args()
    def expired(signum, frame):
        raise Unavailable('total-budget-exhausted')
    previous = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, MAX_TOTAL_SECONDS)
    try:
        value = collect(ROOT, os.environ, args.serial)
    except Exception:
        value = dict(schema=1, diagnosticOnly=True, status='unavailable', reasonCode='diagnostic-unavailable',
                     releaseAcceptance=False, applicationAcceptance=False, originalEditingAcceptance=False,
                     physicalPhoneAcceptance=False)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'))
    if len(raw.encode()) > MAX_REPORT_BYTES:
        value = dict(schema=1, diagnosticOnly=True, status='unavailable', reasonCode='projection-bound',
                     releaseAcceptance=False, applicationAcceptance=False, originalEditingAcceptance=False,
                     physicalPhoneAcceptance=False)
        raw = json.dumps(value, sort_keys=True)
    target = ROOT / 'work/gecko-integration/editing-transport13-diagnostic.json'
    try:
        target.write_text(raw + '\n')
    except OSError:
        pass  # Diagnostic storage cannot change an original workload's result.
    print(PREFIX + raw, flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
