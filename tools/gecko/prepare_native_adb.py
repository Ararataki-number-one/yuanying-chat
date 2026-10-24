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
    while True:
        address = subprocess.run(base + ['shell', 'ip', '-4', '-o', 'addr', 'show', 'wlan0'],
                                 capture_output=True, text=True, timeout=8)
        route = subprocess.run(base + ['shell', 'ip', '-4', 'route', 'get', '10.0.2.2'],
                               capture_output=True, text=True, timeout=8)
        record.setdefault('routeObservations', []).append(dict(addressExit=address.returncode,
            routeExit=route.returncode, addresses=address.stdout, route=route.stdout,
            errors=address.stderr + route.stderr))
        if address.returncode == route.returncode == 0 and 'inet 10.0.2.16/' in address.stdout and 'dev wlan0' in route.stdout:
            break
        if time.monotonic() > deadline:
            raise TimeoutError('Actual SDK Wi-Fi address/return route not ready')
        time.sleep(.25)
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
