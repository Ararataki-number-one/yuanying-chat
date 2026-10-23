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
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/gecko'))
import prepare_emulator as normal

BOOTSTRAP = 'emulator-5556'
ACCEPTANCE = 'emulator-5554'


class BootstrapCommands:
    # Share bounded command recording, not the normal target constructor. The
    # latter remains unchanged and continues to reject bootstrap/physical IDs.
    run = normal.Commands.run

    def __init__(self, executable, serial, record, deadline):
        if serial != BOOTSTRAP:
            raise ValueError('Only the synthetic bootstrap target is allowed')
        self.executable, self.serial, self.record, self.deadline = executable, serial, record, deadline


def monitor(path, command):
    if command not in ('info usernet', 'info network'):
        raise ValueError('Unexpected QEMU metadata/setup command')
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as stream:
        stream.settimeout(5)
        stream.connect(str(path))
        def response():
            raw = b''
            while b'(qemu)' not in raw:
                data = stream.recv(65536)
                if not data:
                    raise ValueError('QEMU monitor closed without a complete response')
                raw += data
                if len(raw) > 1024 * 1024:
                    raise ValueError('Oversized QEMU metadata response')
            return raw.decode(errors='replace')
        response()
        stream.sendall(command.encode('ascii') + b'\n')
        # HMP echoes input with ANSI cursor movement. The actual reply follows
        # its first CRLF; retain only that bounded metadata reply in the report.
        return response().split('\r\n', 1)[-1]


def verify_forward(text):
    active = None
    found = []
    for line in text.splitlines():
        match = re.fullmatch(r'VLAN -1 \(([^)]+)\):', line.strip())
        if match:
            active = match[1]
        elif 'TCP[HOST_FORWARD]' in line:
            fields = line.split()
            if len(fields) == 8 and fields[2:6] == ['127.0.0.1', '5555', '10.0.2.15', '5555']:
                found.append(active)
    if found != ['mynet']:
        raise ValueError('Actual native forwarding backend/address differs')


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
                              'persistent-sdk-wifi-after-setup', 'after-persistent-sdk-wifi')
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


def native_transport(adb, monitor_path, record):
    base = [adb, '-s', BOOTSTRAP]
    def command(*parts):
        return subprocess.check_output(base + list(parts), text=True, timeout=8)
    record['tcpService'] = command('tcpip', '5555')
    subprocess.run(base + ['wait-for-device'], check=True, timeout=30)
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
    record['beforeUsernet'] = monitor(monitor_path, 'info usernet')
    record['forwardResult'] = command('emu', 'redir', 'add', 'tcp:5555:5555')
    record['afterUsernet'] = monitor(monitor_path, 'info usernet')
    verify_forward(record['afterUsernet'])
    # Register the real native emulator service once; no serial aliases, server
    # restart, transport fallback or application/installed-byte retry exists.
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
        commands = BootstrapCommands(args.adb, BOOTSTRAP, record, time.monotonic() + 33)
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
