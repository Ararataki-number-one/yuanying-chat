#!/usr/bin/env python3
"""Prepare native TCP on a synthetic emulator before any application workload.

The original normal preflight and every input/identity oracle still run against
emulator-5554. This independent bootstrap adapter uses only emulator-5556.
"""
import argparse
import json
import os
from pathlib import Path
import re
import socket
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/gecko'))
import prepare_emulator as normal

BOOTSTRAP = 'emulator-5556'
ACCEPTANCE = 'emulator-5554'
PREPARATION_TIMEOUT_SECONDS = 45
RULE = 'hostfwd_add virtio-wifi tcp:127.0.0.1:5555-10.0.2.16:5555'
CNXN = int.from_bytes(b'CNXN', 'little')


class BootstrapCommands:
    # Share bounded command recording, not the normal target constructor. The
    # latter remains unchanged and continues to reject bootstrap/physical IDs.
    run = normal.Commands.run

    def __init__(self, executable, serial, record, deadline):
        if serial != BOOTSTRAP:
            raise ValueError('Only the synthetic bootstrap target is allowed')
        self.executable, self.serial, self.record, self.deadline = executable, serial, record, deadline
        self._sdk_wifi_session, self._sdk_wifi_ap = object(), None


def require(condition, message):
    if not condition:
        raise ValueError(message)


def monitor(path, command):
    require(command in ('help hostfwd_add', 'info usernet', 'info network', RULE),
            'Unexpected experimental monitor command')
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as stream:
        stream.settimeout(5)
        stream.connect(str(path))
        def response():
            raw = b''
            while b'(qemu)' not in raw:
                data = stream.recv(65536)
                if not data:
                    raise ValueError('QEMU monitor closed before response')
                raw += data
                require(len(raw) <= 1024 * 1024, 'Oversized QEMU monitor response')
            return raw.decode(errors='replace')
        response()
        stream.sendall(command.encode('ascii') + b'\n')
        return response().split('\r\n', 1)[-1]


def verify_backend(text):
    require(re.search(r'(?m)^virtio-wifi-device: [^\r\n]*\r?\n\s*\\ virtio-wifi: [^\r\n]*type=user,net=10\.0\.2\.0(?:,|\r?$)', text),
            'Actual Wi-Fi NIC/user backend not proven')


def verify_forward(text):
    backend, forwards = None, []
    for line in text.splitlines():
        match = re.fullmatch(r'VLAN -1 \(([^)]+)\):', line.strip())
        if match:
            backend = match[1]
        elif 'TCP[HOST_FORWARD]' in line:
            fields = line.split()
            if len(fields) == 8 and fields[3] == '5555':
                forwards.append((backend, fields[2:6]))
    require(forwards == [('virtio-wifi', ['127.0.0.1', '5555', '10.0.2.16', '5555'])],
            'Unique actual Wi-Fi native forwarding rule differs')


def prepare_native_wifi_path(commands, record, identity):
    """One synthetic SDK-AP repair, within the existing preparation budget.

    A usable cellular default network is not proof of the Wi-Fi endpoint's
    source route. This is preparation only, before native TCP or app workload.
    """
    deadline, session = commands.deadline, commands._sdk_wifi_session
    identity_snapshot = json.dumps(identity, sort_keys=True, separators=(',', ':'))
    owner = (commands.executable, commands.serial)
    stage = None
    guarded_run, original_run = None, BootstrapCommands.run

    def owned():
        require(type(commands) is BootstrapCommands and commands.record is record
                and (commands.executable, commands.serial) == owner
                and commands.serial == BOOTSTRAP and commands.deadline == deadline
                and BootstrapCommands.run is original_run
                and ((guarded_run is None and 'run' not in vars(commands))
                     or (guarded_run is not None and vars(commands).get('run') is guarded_run))
                and commands._sdk_wifi_session is session
                and record.get('confirmedQemu') is True
                and record.get('disabledStateConfirmed') is True
                and re.fullmatch('[0-9a-f]{40}', identity.get('sourceCommit', ''))
                and re.fullmatch('[0-9a-f]{40}', identity.get('sourceTree', ''))
                and record.get('sourceCommit') == identity['sourceCommit']
                and record.get('sourceTree') == identity['sourceTree']
                and (stage is None or record.get('nativeWifiPathPreparation') is stage)
                and json.dumps(identity, sort_keys=True, separators=(',', ':')) == identity_snapshot,
                'Native Wi-Fi preparation owner/source changed')

    owned()
    require('nativeWifiPathPreparation' not in record, 'Native Wi-Fi preparation already attempted')
    stage = dict(status='failed', serial=BOOTSTRAP, startedAt=time.monotonic(),
                 deadlineMonotonic=deadline, repairAttempted=False, repairAttempts=0,
                 observations=[], applicationAcceptance=False, originalWorkloadInvoked=False)
    record['nativeWifiPathPreparation'] = stage

    def observe():
        owned()
        address = commands.run('shell', 'ip', '-4', '-o', 'addr', 'show', 'wlan0')
        owned()
        row = dict(addresses=address, route=None, ready=None, observedAt=time.monotonic())
        stage['observations'].append(row)
        require(time.monotonic() < deadline, 'Native Wi-Fi path arrived after preparation deadline')
        if address == '':
            # A completed empty -4 address read is a known DHCP transition,
            # not authorization to mutate configuration or query a missing source.
            return None
        # Only the observed synthetic address and understood route forms can
        # authorize repair. Unknown output never becomes a retry instruction.
        address_match = re.fullmatch(
            r'\d+:\s+wlan0\s+inet 10\.0\.2\.16/(?:[0-9]|[12][0-9]|3[0-2])(?P<tail>(?:\s+[^\n]*)?)', address)
        require(len(address) <= 65536 and len(address.splitlines()) == 1
                and address.count('inet ') == 1 and address_match,
                'Unrecognized native Wi-Fi address observation')
        tail = address_match.group('tail').replace('\\', ' \\ ').split()
        if tail[:1] == ['brd']:
            require(len(tail) >= 2 and re.fullmatch(r'(?:[0-9]{1,3}\.){3}[0-9]{1,3}', tail[1])
                    and all(int(part) <= 255 for part in tail[1].split('.')),
                    'Unrecognized native Wi-Fi broadcast address')
            tail = tail[2:]
        if tail[:1] == ['scope']:
            require(tail[:2] == ['scope', 'global'], 'Unrecognized native Wi-Fi address scope')
            tail = tail[2:]
        if tail[:1] == ['wlan0']:
            tail = tail[1:]
        if tail[:1] == ['\\']:
            tail = tail[1:]
            require(tail, 'Incomplete native Wi-Fi address lifetime')
        require(not tail or (len(tail) == 4 and tail[0] == 'valid_lft' and tail[2] == 'preferred_lft'
                and all(re.fullmatch(r'forever|[0-9]+sec', value) for value in (tail[1], tail[3]))),
                'Unrecognized native Wi-Fi address metadata')
        route_parts = ('shell', 'ip', '-4', 'route', 'get', '10.0.2.2', 'from', '10.0.2.16')
        command_index = len(record['commands'])
        route = commands.run(*route_parts, check=False)
        owned()
        require(len(record['commands']) == command_index + 1,
                'Native Wi-Fi route command record changed')
        result = record['commands'][command_index]
        require(result.get('command') == [owner[0], '-s', owner[1], *route_parts]
                and type(result.get('exitCode')) is int and result.get('timedOut') is False
                and result.get('stdout', '').replace('\r', '').strip() == route,
                'Native Wi-Fi route result is not bound to its command')
        row.update(route=route, routeExit=result['exitCode'], routeErrors=result['stderr'],
                   routeCommandIndex=command_index, observedAt=time.monotonic())
        require(time.monotonic() < deadline, 'Native Wi-Fi path arrived after preparation deadline')
        if (result['exitCode'] == 2 and not route and result['stderr'].strip() in
                ('RTNETLINK answers: Network is unreachable',
                 'RTNETLINK answers: Cannot assign requested address')):
            return None
        require(result['exitCode'] == 0 and not result['stderr'] and len(route) <= 65536,
                'Unrecognized native Wi-Fi route failure')
        lines = [line.strip() for line in route.splitlines() if line.strip()]
        require(1 <= len(lines) <= 2 and (len(lines) == 1 or lines[1] == 'cache'),
                'Unrecognized native Wi-Fi route observation')
        tokens, fields = lines[0].split(), {}
        require(tokens and tokens[0] == '10.0.2.2' and len(tokens) % 2 == 1,
                'Unrecognized native Wi-Fi route fields')
        for key, value in zip(tokens[1::2], tokens[2::2]):
            require(key in ('from', 'dev', 'table', 'src', 'uid') and key not in fields,
                    'Unrecognized native Wi-Fi route field')
            fields[key] = value
        sources = [fields[key] for key in ('from', 'src') if key in fields]
        require(fields.get('dev') in ('wlan0', 'eth0') and sources
                and all(value == '10.0.2.16' for value in sources)
                and ('table' not in fields or fields['table'].isdigit())
                and ('uid' not in fields or fields['uid'].isdigit()),
                'Unrecognized native Wi-Fi source/device')
        row['ready'] = fields['dev'] == 'wlan0'
        return row['ready']

    def wait():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Native Wi-Fi source path not ready within preparation deadline')
        time.sleep(min(.25, remaining))

    try:
        state = observe()
        while state is None:
            wait()
            state = observe()
        if state is False:
            owned()
            # provision_sdk_wifi itself reserves ten seconds after its scan.
            # Do not start repair when that original reservation is unavailable.
            if deadline - time.monotonic() <= 10:
                raise TimeoutError('Native Wi-Fi repair preparation budget unavailable')
            stage.update(repairAttempted=True, repairAttempts=1)
            # The original provisioner issues several synchronous commands.
            # Check ownership at every boundary, then restore normal dispatch.
            def checked_run(*parts, **options):
                owned()
                result = original_run(commands, *parts, **options)
                owned()
                return result
            guarded_run = checked_run
            commands.run = checked_run
            try:
                normal.provision_sdk_wifi(commands, record, identity,
                    'native-wifi-source-path-repair', 'after-native-wifi-source-path-repair',
                    reuse_observed_ap=False)
                owned()
            finally:
                vars(commands).pop('run', None)
                guarded_run = None
            owned()
            while observe() is not True:
                wait()
        stage['status'] = 'passed'
    except BaseException as failure:
        stage.update(failureType=type(failure).__name__, reason=str(failure))
        raise
    finally:
        stage['completedAt'] = time.monotonic()


def persistent_network(commands, record, identity):
    normal.preflight(commands, record, identity)
    if not record.get('confirmedQemu') or not record.get('disabledStateConfirmed'):
        raise ValueError('SDK emulator/package prerequisite not confirmed')
    # Removing the first-boot SDK request can asynchronously revoke Wi-Fi after
    # an immediately healthy CM snapshot. Finish that transition on VSOCK,
    # then provision the same observed SDK AP before creating native TCP.
    commands.run('shell', 'cmd', 'wifi', 'set-wifi-enabled', 'disabled')
    while True:
        addresses = commands.run('shell', 'ip', '-4', '-o', 'addr', 'show', 'wlan0')
        record.setdefault('wifiResetAddresses', []).append(addresses)
        if 'inet ' not in addresses:
            break
        if commands.deadline - time.monotonic() <= 1:
            raise TimeoutError('SDK Wi-Fi teardown did not finish')
        time.sleep(.25)
    normal.provision_sdk_wifi(commands, record, identity,
                              'persistent-sdk-wifi-after-setup', 'after-persistent-sdk-wifi',
                              reuse_observed_ap=True)
    if not normal.network_observation(commands, record, identity, 'persistent-sdk-wifi-confirmation'):
        raise ValueError('Actual persistent SDK connection not usable')
    prepare_native_wifi_path(commands, record, identity)


def announce_native(record):
    # host:emulator is a one-way notification. AOSP's own test sends the
    # framed request and closes; unlike ordinary services it has no OKAY reply.
    # Device readiness must be checked separately, never inferred from this.
    with socket.create_connection(('127.0.0.1', 5037), timeout=5) as stream:
        request = b'host:emulator:5555'
        stream.sendall(('%04x' % len(request)).encode('ascii') + request)
    record['announcementSent'] = True
    record['announcementIsNotificationOnly'] = True


def wait_native(adb, record):
    deadline = time.monotonic() + 30
    while True:
        result = subprocess.run([adb, '-s', ACCEPTANCE, 'get-state'],
                                capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout.strip() == 'device':
            record['nativeReady'] = True
            return
        if time.monotonic() > deadline:
            raise TimeoutError('Native TCP target did not become ready')
        time.sleep(.25)


def endpoint_probe(deadline):
    """One CNXN attempt, header only, constrained by the shared total deadline."""
    row = {'address': '127.0.0.1', 'port': 5555, 'tcpAccepted': False,
           'payloadRead': False, 'authResponseSent': False, 'applicationCommandsSent': False}
    started = time.monotonic()
    try:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Endpoint deadline expired')
        with socket.create_connection(('127.0.0.1', 5555), timeout=min(1, remaining)) as stream:
            row['tcpAccepted'] = True
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('Endpoint deadline expired before CNXN')
            stream.settimeout(min(1, remaining))
            banner = b'host::\0'
            stream.sendall(struct.pack('<6I', CNXN, 0x01000000, 1024 * 1024,
                                       len(banner), sum(banner), CNXN ^ 0xffffffff) + banner)
            raw = b''
            header_deadline = min(deadline, time.monotonic() + 3)
            while len(raw) < 24:
                remaining = header_deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('Endpoint response header deadline expired')
                stream.settimeout(remaining)
                block = stream.recv(24 - len(raw))
                if not block:
                    raise EOFError('Endpoint closed before a complete header')
                raw += block
            command, arg0, arg1, size, checksum, magic = struct.unpack('<6I', raw)
            require(magic == command ^ 0xffffffff and size <= 1024 * 1024,
                    'Invalid ADB protocol header')
            name = command.to_bytes(4, 'little').decode('ascii', errors='replace')
            require(name in ('CNXN', 'AUTH', 'CLSE'), 'Unexpected ADB response command')
            row.update(responseCommand=name, argument0=arg0, argument1=arg1,
                       payloadBytesAdvertised=size)
    except (OSError, EOFError, ValueError) as error:
        row.update(errorType=type(error).__name__, error=str(error))
    row['elapsedMs'] = (time.monotonic() - started) * 1000
    return row


def wait_endpoint(record):
    deadline = time.monotonic() + 8
    record.update(endpointDeadlineSeconds=8, endpointProbeAttempts=[],
                  endpointProtocolReachable=False)
    while True:
        row = endpoint_probe(deadline)
        record['endpointProbeAttempts'].append(row)
        if row.get('responseCommand') in ('CNXN', 'AUTH'):
            record['endpointProtocolReachable'] = True
            return
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Real Wi-Fi native endpoint did not answer ADB within 8 seconds')
        time.sleep(min(.25, remaining))


def native_transport(adb, monitor_path, record):
    require(record.get('confirmedQemu') is True, 'Confirmed synthetic QEMU required')
    base = [adb, '-s', BOOTSTRAP]
    deadline = time.monotonic() + 30
    record['returnRouteSource'] = '10.0.2.16'
    record['routeReadinessCommands'] = []
    record['routeDiagnostics'] = []

    def route_command(parts, *, diagnostic=False):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Actual SDK Wi-Fi address/return route not ready')
        command = base + parts
        row = dict(command=command, timeoutSeconds=min(8, remaining),
                   deadlineMonotonic=deadline, diagnosticOnly=diagnostic)
        target = record['routeDiagnostics'] if diagnostic else record['routeReadinessCommands']
        target.append(row)
        try:
            result = subprocess.run(command, capture_output=True, text=True,
                                    timeout=row['timeoutSeconds'])
        except subprocess.TimeoutExpired as error:
            def decoded(value):
                return value.decode('utf-8', errors='replace') if isinstance(value, bytes) else value or ''
            row.update(exitCode=None, timedOut=True, stdout=decoded(error.stdout),
                       stderr=decoded(error.stderr), observedAt=time.monotonic())
            if diagnostic:
                return None
            raise
        row.update(exitCode=result.returncode, timedOut=False, stdout=result.stdout,
                   stderr=result.stderr, observedAt=time.monotonic())
        return result

    # The shell's default network can legitimately be cellular. Preserve that
    # context without using it as the Wi-Fi-targeted endpoint's return path.
    # These one-shot reads share, and never extend, the original route deadline.
    for parts in (['shell', 'ip', '-4', 'route', 'get', '10.0.2.2'],
                  ['shell', 'ip', '-4', 'rule', 'show'],
                  ['shell', 'ip', '-4', 'route', 'show', 'table', 'all']):
        route_command(parts, diagnostic=True)
    while True:
        address = route_command(['shell', 'ip', '-4', '-o', 'addr', 'show', 'wlan0'])
        route = route_command(['shell', 'ip', '-4', 'route', 'get', '10.0.2.2',
                               'from', '10.0.2.16'])
        record.setdefault('routeObservations', []).append(dict(addressExit=address.returncode,
            routeExit=route.returncode, addresses=address.stdout, route=route.stdout,
            routeSource='10.0.2.16', errors=address.stderr + route.stderr))
        if time.monotonic() > deadline:
            raise TimeoutError('Actual SDK Wi-Fi address/return route not ready')
        devices = re.findall(r'(?:^|\s)dev\s+(\S+)', route.stdout)
        sources = re.findall(r'(?:^|\s)(?:from|src)\s+(\S+)', route.stdout)
        if (address.returncode == route.returncode == 0
                and 'inet 10.0.2.16/' in address.stdout and devices == ['wlan0']
                and sources and all(value == '10.0.2.16' for value in sources)):
            break
        time.sleep(min(.25, max(0, deadline - time.monotonic())))
    record['networkDevices'] = monitor(monitor_path, 'info network')
    verify_backend(record['networkDevices'])
    record['hostfwdHelp'] = monitor(monitor_path, 'help hostfwd_add')
    require('hostfwd_add' in record['hostfwdHelp'] and 'netdev' in record['hostfwdHelp'],
            'Pinned emulator does not advertise explicit-backend forwarding')
    record['beforeUsernet'] = monitor(monitor_path, 'info usernet')
    require(not re.search(r'(?m)TCP\[HOST_FORWARD\]\s+\S+\s+\S+\s+5555\s', record['beforeUsernet']),
            'Fresh native endpoint must not replace an existing forward')
    record['forwardCommand'] = RULE
    record['forwardResult'] = monitor(monitor_path, RULE)
    record['afterUsernet'] = monitor(monitor_path, 'info usernet')
    verify_forward(record['afterUsernet'])
    command = base + ['tcpip', '5555']
    record['tcpipCommand'] = {'command': command, 'invocations': 1,
                            'startedMonotonicNs': time.monotonic_ns()}
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=8)
    except subprocess.TimeoutExpired as error:
        record['tcpipCommand'].update(exitCode=None, timedOut=True,
            stdout=str(error.stdout or ''), stderr=str(error.stderr or ''))
        raise
    finally:
        record['tcpipCommand']['elapsedMs'] = (time.monotonic_ns() - record['tcpipCommand']['startedMonotonicNs']) / 1000000
    row = record['tcpipCommand']
    row.update(exitCode=result.returncode, stdout=result.stdout, stderr=result.stderr,
               timedOut=False, commandSucceeded=result.returncode == 0)
    closed = result.returncode == 1 and result.stderr.strip() == 'error: closed' and not result.stdout.strip()
    row['completionUncertainClosed'] = closed
    if result.returncode != 0 and not closed:
        result.check_returncode()
    # No VSock command follows the transition. Protocol readiness is separate
    # from command success, and cannot satisfy the final native device gate.
    wait_endpoint(record)
    announce_native(record)
    wait_native(adb, record)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', required=True)
    parser.add_argument('--apk', required=True, type=Path)
    parser.add_argument('--monitor', required=True, type=Path)
    args = parser.parse_args()
    out = ROOT / 'work/gecko-integration/native-adb-setup-results.json'
    record = dict(schema=1, status='failed', serial=BOOTSTRAP, normalAcceptanceTarget=ACCEPTANCE,
        exactSetupPackage=normal.PACKAGE, commands=[], networkObservations=[], diagnostics={}, initialInputSettings={},
        actualAndroidCommands=False, actualIntegrationProviderExecution=False, actualConnectivityManagerExecution=False,
        applicationAcceptance=False, actualGeckoExecution=False, physicalPhoneAcceptance=False, confirmedQemu=False,
        applicationOrInputPolicyModified=False, gestureReplayed=False, sdkWifiProvisioningRequested=False,
        disabledStateConfirmed=False, postSetupNetworkRecoveryRequired=False, sdkWifiProvisioningStages=[],
        runId=os.environ['GITHUB_RUN_ID'], runAttempt=os.environ.get('GITHUB_RUN_ATTEMPT', '1'),
        normalPreflightStillRequired=True, originalWorkloadInvoked=False,
        scope='Synthetic bootstrap network and native transport only; no application/input acceptance')
    try:
        def git(*parts):
            return subprocess.check_output(['git', *parts], cwd=ROOT, text=True, timeout=8).strip()
        if git('status', '--porcelain'):
            raise ValueError('Bootstrap requires a clean committed APK/source')
        source, tree = git('rev-parse', 'HEAD'), git('rev-parse', 'HEAD^{tree}')
        settings = (ROOT / 'app/build.gradle').read_text()
        version = re.search(r"versionName '([^']+)'", settings).group(1)
        code = int(re.search(r'versionCode ([0-9]+)', settings).group(1))
        identity = normal.expected_build(args.apk.resolve(), source, tree, version, code)
        record.update(sourceCommit=source, sourceTree=tree, expectedBuildIdentity=identity)
        # One budget covers preflight, the persistent Wi-Fi reset and both fresh
        # CM observations. Each command still has the original eight-second cap.
        started = time.monotonic()
        record.update(preparationBudgetSeconds=PREPARATION_TIMEOUT_SECONDS,
                      preparationStartedAt=started,
                      preparationDeadlineMonotonic=started + PREPARATION_TIMEOUT_SECONDS)
        commands = BootstrapCommands(args.adb, BOOTSTRAP, record, record['preparationDeadlineMonotonic'])
        persistent_network(commands, record, identity)
        native_transport(args.adb, args.monitor, record)
        record['status'] = 'passed'
    except BaseException as error:
        record.update(status='failed', failureType=type(error).__name__, reason=str(error))
        raise
    finally:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(dict(status='passed', setupOnly=True, applicationAcceptance=False,
                         actualForwardingVerified=True, normalPreflightStillRequired=True)))


if __name__ == '__main__':
    main()
