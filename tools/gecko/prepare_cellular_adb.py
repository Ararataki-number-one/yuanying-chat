#!/usr/bin/env python3
"""Prepare the explicit cellular prerequisite on a fresh API 35 CI emulator.

The legacy preparation modules remain unchanged. This adapter reuses their
real installed-identity/CM readers and native ADB protocol gates, never their
Wi-Fi provisioner. It executes no application workload or input acceptance.
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
import prepare_native_adb as native

RULE = 'hostfwd_add mynet tcp:127.0.0.1:5555-10.0.2.15:5555'
require = native.require


def cellular_observation(commands, record, identity, phase):
    index = len(record['networkObservations'])
    usable = normal.network_observation(commands, record, identity, phase)
    row = record['networkObservations'][index]
    value = row['value']
    require(usable and type(value.get('transports')) is list
            and value['transports'] == ['cellular'] and value['androidSdk'] == 35,
            'Actual stable API 35 cellular default network with INTERNET required')
    return index, row


def cellular_after_setup(commands, record, identity):
    """Observe the known SDK Wi-Fi handover within the same preparation budget.

    The verified original Wi-Fi may remain briefly after SDK package teardown,
    then disappear before Android selects cellular. Neither the retained Wi-Fi
    nor an empty default satisfies a cellular proof. Returning to Wi-Fi after
    an empty observation is not a handover continuation.
    """
    stage = record['cellularPreparation']
    initial = record['networkObservations'][stage['initialNetworkObservationIndex']]['value']
    initial_wifi = (type(initial) is dict and type(initial.get('schema')) is int and initial['schema'] == 1
                    and type(initial.get('androidSdk')) is int and initial['androidSdk'] == 35
                    and type(initial.get('transports')) is list and initial['transports'] == ['wifi']
                    and type(initial.get('capabilities')) is str and bool(initial['capabilities'])
                    and all(initial.get(key) is True for key in
                            ('capabilitiesPresent', 'internetCapability', 'stableDuringRead', 'usable'))
                    and bool(initial['activeNetwork'])
                    and initial['activeNetwork'] == initial['activeNetworkAfter'])
    empty_seen = False
    while True:
        index = len(record['networkObservations'])
        usable = normal.network_observation(commands, record, identity,
                                             'after-setup-package-handling-cellular')
        rows = record['networkObservations']
        require(len({row['runNonce'] for row in rows}) == len(rows),
                'Every preparation network observation requires a fresh nonce')
        row, value = rows[index], rows[index]['value']
        if (usable and type(value.get('transports')) is list
                and value['transports'] == ['cellular'] and value['androidSdk'] == 35):
            return index, row
        require(record.get('packagePresent') is True
                and record.get('disabledStateConfirmed') is True
                and type(value) is dict and type(value.get('schema')) is int and value['schema'] == 1
                and type(value.get('androidSdk')) is int and value['androidSdk'] == 35,
                'Verified SDK teardown and API 35 observation required for handover waiting')
        empty_default = (usable is False
                and value.get('activeNetwork') == '' and value.get('activeNetworkAfter') == ''
                and all(value.get(key) is False for key in
                        ('capabilitiesPresent', 'internetCapability', 'stableDuringRead', 'usable'))
                and type(value.get('transports')) is list and value['transports'] == []
                and type(value.get('capabilities')) is str and value['capabilities'] == '')
        retained_wifi = (not empty_seen and initial_wifi and usable is True
                and type(value.get('transports')) is list and value['transports'] == ['wifi']
                and type(value.get('capabilities')) is str and bool(value['capabilities'])
                and all(value.get(key) is True for key in
                        ('capabilitiesPresent', 'internetCapability', 'stableDuringRead', 'usable'))
                and value['activeNetwork'] == value['activeNetworkAfter'] == initial['activeNetwork'])
        require(empty_default or retained_wifi,
                'Only the verified initial Wi-Fi or exact empty default may await cellular handover')
        if empty_default:
            empty_seen = True
            stage.setdefault('emptyDefaultNetworkObservationIndices', []).append(index)
        else:
            stage.setdefault('retainedInitialWifiObservationIndices', []).append(index)
        remaining = commands.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Cellular handover did not finish within the original preparation budget')
        time.sleep(min(.25, remaining))


def wifi_state(commands, stage):
    index = len(commands.record['commands'])
    raw = commands.run('shell', 'cmd', 'wifi', 'status')
    states = re.findall(r'^Wifi is (enabled|disabled)\s*$', raw, re.M)
    stage['wifiObservations'].append(dict(commandIndex=index, raw=raw,
                                          observedAt=time.monotonic()))
    require(len(states) == 1, 'Actual Wi-Fi service state is ambiguous')
    return states[0]


def cellular_preflight(commands, record, identity):
    """Keep the original identity/input/package prerequisites without fallback."""
    require(commands.record is record and commands.serial in (normal.SERIAL, native.BOOTSTRAP),
            'Only the fixed synthetic preparation targets are allowed')
    require('cellularPreparation' not in record, 'Cellular preparation already attempted')
    require(record.get('networkMode', 'cellular') == 'cellular', 'Preparation mode differs')
    record['networkMode'] = 'cellular'
    stage = dict(status='failed', serial=commands.serial, startedAt=time.monotonic(),
                 deadlineMonotonic=commands.deadline, wifiDisableAttempts=0,
                 wifiObservations=[], wifiAddressObservations=[],
                 applicationAcceptance=False, originalWorkloadInvoked=False)
    record['cellularPreparation'] = stage
    try:
        properties = {}
        for key, expected in (('ro.kernel.qemu', '1'), ('ro.build.version.sdk', '35'),
                              ('ro.product.cpu.abi', 'x86_64'), ('ro.hardware', 'ranchu')):
            properties[key] = commands.run('shell', 'getprop', key)
            stage['imageProperties'] = properties
            require(properties[key] == expected, 'Fresh API 35 synthetic emulator required: ' + key)
        record['confirmedQemu'] = True
        # Preserve the original input-policy observations; never write them.
        for key in ['show_ime_with_hard_keyboard', 'default_input_method', 'enabled_input_methods']:
            record['initialInputSettings'][key] = commands.run('shell', 'settings', 'get', 'secure', key)
        record['initialKeyboardLayoutProperty'] = commands.run('shell', 'getprop', 'vendor.qemu.keyboard_layout')
        stage['initialNetworkObservationIndex'] = len(record['networkObservations'])
        before = normal.network_observation(commands, record, identity, 'before-network-configuration')
        record['initialNetworkUsable'] = before
        initial_row = record['networkObservations'][stage['initialNetworkObservationIndex']]
        initial = initial_row['value']
        require(before and initial['androidSdk'] == 35,
                'Actual initial API 35 default network with INTERNET required; no Wi-Fi fallback')
        # The SDK setup package may own the initial Wi-Fi request. Preserve
        # its original handling before requiring the independent cellular path.
        present = commands.run('shell', 'pm', 'list', 'packages', normal.PACKAGE).splitlines()
        record['packagePresent'] = 'package:' + normal.PACKAGE in present
        if record['packagePresent']:
            commands.run('shell', 'am', 'force-stop', normal.PACKAGE)
            commands.run('shell', 'pm', 'disable-user', '--user', '0', normal.PACKAGE)
            disabled = commands.run('shell', 'pm', 'list', 'packages', '-d', normal.PACKAGE).splitlines()
            require('package:' + normal.PACKAGE in disabled, 'Setup-package disabled state was not confirmed')
            record['disabledStateConfirmed'] = True
        first_index, first = cellular_after_setup(commands, record, identity)
        stage['firstCellularObservationIndex'] = first_index
        state = wifi_state(commands, stage)
        stage['wifiInitiallyDisabled'] = state == 'disabled'
        if state == 'enabled':
            stage['wifiDisableAttempts'] = 1
            stage['wifiDisableCommandIndex'] = len(record['commands'])
            commands.run('shell', 'cmd', 'wifi', 'set-wifi-enabled', 'disabled')
        # Teardown is asynchronous. These are only readbacks under the same
        # original preparation deadline, never a second mutation or repair.
        while True:
            state = wifi_state(commands, stage)
            address_index = len(record['commands'])
            addresses = commands.run('shell', 'ip', '-4', '-o', 'addr', 'show', 'wlan0')
            stage['wifiAddressObservations'].append(dict(commandIndex=address_index,
                raw=addresses, observedAt=time.monotonic()))
            if state == 'disabled' and not addresses:
                stage['disabledWifiStatusCommandIndex'] = stage['wifiObservations'][-1]['commandIndex']
                stage['emptyWifiAddressCommandIndex'] = address_index
                break
            require(not stage['wifiInitiallyDisabled'] or state == 'disabled',
                    'Wi-Fi became enabled during cellular preparation')
            remaining = commands.deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('Wi-Fi teardown did not finish within the original preparation budget')
            time.sleep(min(.25, remaining))
        second_index, second = cellular_observation(commands, record, identity,
                                                     'disabled-wifi-cellular-confirmation')
        stage['confirmationCellularObservationIndex'] = second_index
        require(second_index == first_index + 1
                and len({row['runNonce'] for row in record['networkObservations']})
                    == len(record['networkObservations'])
                and first['value']['activeNetwork'] == second['value']['activeNetwork'],
                'Two fresh consecutive cellular observations must retain the same default-network identity')
        require(time.monotonic() < commands.deadline, 'Cellular confirmation exceeded the original preparation budget')
        stage.update(status='passed', activeNetwork=second['value']['activeNetwork'],
                     wifiDisabledConfirmed=True, sameCellularIdentityConfirmed=True)
    except BaseException as error:
        stage.update(failureType=type(error).__name__, reason=str(error))
        raise
    finally:
        stage['completedAt'] = time.monotonic()


def verify_backend(text):
    require(len(re.findall(r'(?m)^virtio-net-pci\.0:', text)) == 1
            and len(re.findall(r'(?m)^\s*\\ mynet:', text)) == 1
            and len(re.findall(r'(?m)^virtio-net-pci\.0: [^\r\n]*type=nic,model=virtio-net-pci(?:,[^\r\n]*)?\r?\n'
                           r'\s*\\ mynet: [^\r\n]*type=user,net=10\.0\.2\.0,restrict=off(?:,|\r?$)', text)) == 1,
            'Actual cellular virtio-net-pci/mynet user backend not proven')


def verify_forward(text):
    backend, forwards = None, []
    for line in text.splitlines():
        match = re.fullmatch(r'VLAN -1 \(([^)]+)\):', line.strip())
        if match:
            backend = match[1]
        elif 'TCP[HOST_FORWARD]' in line:
            fields = line.split()
            require(len(fields) == 8, 'Unrecognized native forwarding record')
            if fields[3] == '5555':
                forwards.append((backend, fields[2:6]))
    require(forwards == [('mynet', ['127.0.0.1', '5555', '10.0.2.15', '5555'])],
            'Unique actual cellular native forwarding rule differs')


def verify_source_path(addresses, route):
    address = addresses.replace('\r', '').strip()
    match = re.fullmatch(r'\d+:\s+eth0\s+inet 10\.0\.2\.15/(?:[0-9]|[12][0-9]|3[0-2])(?P<tail>(?:\s+[^\n]*)?)', address)
    require(len(address) <= 65536 and len(address.splitlines()) == 1
            and len(re.findall(r'\binet\s', address)) == 1
            and match,
            'Actual eth0 address must be exactly the native cellular endpoint')
    tail = match.group('tail').replace('\\', ' \\ ').split()
    if tail[:1] == ['brd']:
        require(len(tail) >= 2 and re.fullmatch(r'(?:[0-9]{1,3}\.){3}[0-9]{1,3}', tail[1])
                and all(int(part) <= 255 for part in tail[1].split('.')), 'Unrecognized cellular broadcast address')
        tail = tail[2:]
    if tail[:1] == ['scope']:
        require(tail[:2] == ['scope', 'global'], 'Unrecognized cellular address scope')
        tail = tail[2:]
    if tail[:1] == ['eth0']:
        tail = tail[1:]
    if tail[:1] == ['\\']:
        tail = tail[1:]
        require(tail, 'Incomplete cellular address lifetime')
    require(not tail or (len(tail) == 4 and tail[0] == 'valid_lft' and tail[2] == 'preferred_lft'
            and all(re.fullmatch(r'forever|[0-9]+sec', value) for value in (tail[1], tail[3]))),
            'Unrecognized cellular address metadata')
    lines = [line.strip() for line in route.splitlines() if line.strip()]
    require(len(route) <= 65536 and 1 <= len(lines) <= 2
            and (len(lines) == 1 or lines[1] == 'cache'), 'Unrecognized cellular source route')
    tokens, fields = lines[0].split(), {}
    require(tokens[0] == '10.0.2.2' and len(tokens) % 2 == 1, 'Unrecognized cellular route destination/fields')
    for key, value in zip(tokens[1::2], tokens[2::2]):
        require(key in ('from', 'dev', 'table', 'src', 'uid') and key not in fields,
                'Unrecognized cellular route field')
        fields[key] = value
    require(fields.get('from') == '10.0.2.15' and fields.get('dev') == 'eth0'
            and ('src' not in fields or fields['src'] == '10.0.2.15')
            and all(fields[key].isdigit() for key in ('table', 'uid') if key in fields),
            'Actual source-specific native cellular return route differs')


def install_forward(path):
    # Only this fixed loopback rule is writable. Metadata remains on the
    # original bounded, read-only monitor implementation.
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as stream:
        stream.settimeout(5)
        stream.connect(str(path))
        def response():
            raw = b''
            while b'(qemu)' not in raw:
                block = stream.recv(65536)
                require(block, 'QEMU monitor closed before response')
                raw += block
                require(len(raw) <= 1024 * 1024, 'Oversized QEMU monitor response')
            return raw.decode(errors='replace')
        response()
        stream.sendall(RULE.encode('ascii') + b'\n')
        return response().split('\r\n', 1)[-1]


def native_transport(adb, monitor_path, record):
    require(record.get('confirmedQemu') is True and record.get('networkMode') == 'cellular'
            and record.get('cellularPreparation', {}).get('status') == 'passed',
            'Confirmed cellular synthetic preparation required')
    require(record.get('disabledStateConfirmed') is True, 'SDK setup-package prerequisite not confirmed')
    base = [adb, '-s', native.BOOTSTRAP]
    deadline = time.monotonic() + 30
    record.update(returnRouteSource='10.0.2.15', routeReadinessDeadlineMonotonic=deadline,
                  routeReadinessCommands=[], routeDiagnostics=[])
    def route_command(parts, *, diagnostic=False):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Actual cellular address/return route not ready within 30 seconds')
        command = base + list(parts)
        row = dict(command=command, timeoutSeconds=min(8, remaining),
                   deadlineMonotonic=deadline, diagnosticOnly=diagnostic)
        record['routeDiagnostics' if diagnostic else 'routeReadinessCommands'].append(row)
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=row['timeoutSeconds'])
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
        if not diagnostic:
            result.check_returncode()
            require(not result.stderr, 'Unexpected cellular route readback error')
        return result
    for parts in (('shell', 'ip', '-4', 'route', 'get', '10.0.2.2'),
                  ('shell', 'ip', '-4', 'rule', 'show'),
                  ('shell', 'ip', '-4', 'route', 'show', 'table', 'all')):
        route_command(parts, diagnostic=True)
    address = route_command(('shell', 'ip', '-4', '-o', 'addr', 'show', 'eth0'))
    route = route_command(('shell', 'ip', '-4', 'route', 'get', '10.0.2.2', 'from', '10.0.2.15'))
    record['routeObservations'] = [dict(addressExit=address.returncode, routeExit=route.returncode,
        addresses=address.stdout, route=route.stdout, routeSource='10.0.2.15', errors=address.stderr + route.stderr)]
    require(time.monotonic() < deadline, 'Cellular route readback exceeded the original route budget')
    verify_source_path(address.stdout, route.stdout)
    record['networkDevices'] = native.monitor(monitor_path, 'info network')
    verify_backend(record['networkDevices'])
    record['hostfwdHelp'] = native.monitor(monitor_path, 'help hostfwd_add')
    require('hostfwd_add' in record['hostfwdHelp'] and 'netdev' in record['hostfwdHelp'],
            'Pinned emulator does not advertise explicit-backend forwarding')
    record['beforeUsernet'] = native.monitor(monitor_path, 'info usernet')
    require(not re.search(r'(?m)TCP\[HOST_FORWARD\]\s+\S+\s+\S+\s+5555\s', record['beforeUsernet']),
            'Fresh native endpoint must not replace an existing forward')
    record['forwardCommand'] = RULE
    record['forwardResult'] = install_forward(monitor_path)
    record['afterUsernet'] = native.monitor(monitor_path, 'info usernet')
    verify_forward(record['afterUsernet'])
    command = base + ['tcpip', '5555']
    record['tcpipCommand'] = dict(command=command, invocations=1, startedMonotonicNs=time.monotonic_ns())
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
    # Original 8-second CNXN budget, one-way announcement, and 30-second
    # actual device readiness. No bootstrap command follows tcpip.
    native.wait_endpoint(record)
    native.announce_native(record)
    native.wait_native(adb, record)


def native_failure_diagnostics(commands, record):
    """Read the confirmed bootstrap target only after its original failure.

    This separate twelve-second collection cannot extend the preparation
    instance, create a CM observation, repair a network, or resume acceptance.
    A tcpip attempt permanently excludes the old bootstrap channel.
    """
    if (commands is None or not isinstance(commands, native.BootstrapCommands)
            or commands.record is not record or commands.serial != native.BOOTSTRAP
            or record.get('serial') != native.BOOTSTRAP or record.get('phase') != 'native'
            or record.get('status') != 'failed' or record.get('confirmedQemu') is not True
            or 'failureObservedAt' not in record or 'failureType' not in record
            or 'tcpipCommand' in record or 'nativeFailureDiagnostics' in record):
        return
    started = time.monotonic()
    capture = dict(status='collecting', startedAt=started, budgetSeconds=12,
                   deadlineMonotonic=started + 12, commandStartIndex=len(record['commands']),
                   preparationDeadlineMonotonic=commands.deadline,
                   applicationAcceptance=False, originalWorkloadInvoked=False,
                   scope='Read-only diagnostics after the original native preparation failure')
    record['nativeFailureDiagnostics'] = capture
    diagnostic_commands = native.BootstrapCommands(commands.executable, native.BOOTSTRAP,
                                                   record, capture['deadlineMonotonic'])
    operations = [('mobile-data-setting', ('shell', 'settings', 'get', 'global', 'mobile_data')),
                  ('device-provisioned-setting', ('shell', 'settings', 'get', 'global', 'device_provisioned')),
                  ('device-provisioning-mobile-data-setting',
                   ('shell', 'settings', 'get', 'global', 'device_provisioning_mobile_data')),
                  ('provisioning-mobile-data-property', ('shell', 'getprop', 'ro.com.android.prov_mobiledata')),
                  ('airplane-setting', ('shell', 'settings', 'get', 'global', 'airplane_mode_on')),
                  ('telephony-registry', ('shell', 'dumpsys', 'telephony.registry')),
                  ('connectivity', ('shell', 'dumpsys', 'connectivity')),
                  ('wifi', ('shell', 'dumpsys', 'wifi')),
                  ('routes', ('shell', 'ip', 'route', 'show', 'table', 'all')),
                  ('setup-package', ('shell', 'dumpsys', 'package', normal.PACKAGE))]
    try:
        for index, (name, parts) in enumerate(operations):
            if time.monotonic() >= diagnostic_commands.deadline:
                capture.update(status='budget-exhausted',
                               unattempted=[item[0] for item in operations[index:]])
                return
            try:
                record['diagnostics'][name] = diagnostic_commands.run(*parts, check=False, diagnostic=True)
            except (OSError, subprocess.SubprocessError) as failure:
                record['diagnostics'][name] = dict(failureType=type(failure).__name__, reason=str(failure))
        capture['status'] = 'collected'
    except BaseException:
        capture['status'] = 'interrupted'
        raise
    finally:
        capture.update(completedAt=time.monotonic(), commandEndIndex=len(record['commands']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', required=True, choices=['native', 'normal'])
    parser.add_argument('--network-mode', choices=['cellular'], default='cellular')
    parser.add_argument('--adb', required=True)
    parser.add_argument('--apk', required=True, type=Path)
    parser.add_argument('--monitor', type=Path)
    parser.add_argument('--serial', choices=[normal.SERIAL])
    parser.add_argument('--timeout', type=int, default=45)
    args = parser.parse_args()
    if args.phase == 'native' and (args.monitor is None or args.serial is not None or args.timeout != 45):
        parser.error('Native cellular preparation requires --monitor, fixed bootstrap target, and the original 45-second budget')
    if args.phase == 'normal' and (args.serial != normal.SERIAL or args.monitor is not None or not 15 <= args.timeout <= 45):
        parser.error('Normal cellular preparation requires --serial emulator-5554 and a 15..45-second total budget')
    is_native = args.phase == 'native'
    serial = native.BOOTSTRAP if is_native else normal.SERIAL
    out = ROOT / 'work/gecko-integration' / ('native-adb-setup-results.json' if is_native else 'emulator-bootstrap-results.json')
    record = dict(schema=1 if is_native else 2, status='failed', networkMode='cellular', phase=args.phase,
        serial=serial, exactSetupPackage=normal.PACKAGE, commands=[], networkObservations=[], diagnostics={},
        initialInputSettings={}, actualAndroidCommands=False, actualIntegrationProviderExecution=False,
        actualConnectivityManagerExecution=False, applicationAcceptance=False, actualGeckoExecution=False,
        physicalPhoneAcceptance=False, confirmedQemu=False, applicationOrInputPolicyModified=False,
        gestureReplayed=False, sdkWifiProvisioningRequested=False, disabledStateConfirmed=False,
        postSetupNetworkRecoveryRequired=False, sdkWifiProvisioningStages=[], originalWorkloadInvoked=False,
        runId=os.environ['GITHUB_RUN_ID'] if is_native else os.environ.get('GITHUB_RUN_ID', ''),
        runAttempt=os.environ.get('GITHUB_RUN_ATTEMPT', '1'),
        scope='Explicit cellular synthetic prerequisite only; no application, input, Gecko or phone acceptance')
    started = time.monotonic()
    deadline = started + args.timeout
    commands = None
    try:
        def git(*parts):
            return subprocess.check_output(['git', *parts], cwd=ROOT, text=True, timeout=8).strip()
        require(not git('status', '--porcelain', '--untracked-files=normal'), 'Preparation requires clean committed APK/source')
        source, tree = git('rev-parse', 'HEAD'), git('rev-parse', 'HEAD^{tree}')
        record.update(sourceCommit=source, sourceTree=tree)
        settings = (ROOT / 'app/build.gradle').read_text()
        version = re.search(r"versionName '([^']+)'", settings).group(1)
        code = int(re.search(r'versionCode ([0-9]+)', settings).group(1))
        identity = normal.expected_build(args.apk.resolve(), source, tree, version, code)
        record['expectedBuildIdentity'] = identity
        if is_native:
            # Same fixed preparation budget; Git/APK discovery is outside it,
            # matching the original native adapter's timing boundary.
            started = time.monotonic()
            deadline = started + native.PREPARATION_TIMEOUT_SECONDS
            record.update(normalAcceptanceTarget=native.ACCEPTANCE, normalPreflightStillRequired=True,
                preparationBudgetSeconds=native.PREPARATION_TIMEOUT_SECONDS,
                preparationStartedAt=started, preparationDeadlineMonotonic=deadline)
            commands = native.BootstrapCommands(args.adb, serial, record, deadline)
        else:
            record.update(timeoutSeconds=args.timeout, startedAt=started)
            commands = normal.Commands(args.adb, serial, record, deadline - 12)
        cellular_preflight(commands, record, identity)
        if is_native:
            native_transport(args.adb, args.monitor, record)
        record['status'] = 'passed'
    except BaseException as error:
        record.update(status='failed', failureType=type(error).__name__, reason=str(error),
                      failureClassification='emulator-environment-precondition')
        if is_native:
            record['failureObservedAt'] = time.monotonic()
            try:
                native_failure_diagnostics(commands, record)
            except BaseException as diagnostic_error:
                record['diagnosticsFailure'] = dict(failureType=type(diagnostic_error).__name__,
                                                    reason=str(diagnostic_error))
        elif commands is not None and record['confirmedQemu']:
            commands.deadline = deadline
            try:
                normal.diagnostics(commands, record)
            except Exception as diagnostic_error:
                record['diagnosticsFailure'] = dict(failureType=type(diagnostic_error).__name__,
                                                    reason=str(diagnostic_error))
        raise
    finally:
        record['completedAt'] = time.monotonic()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(dict(status='passed', networkMode='cellular', phase=args.phase,
                         setupOnly=True, applicationAcceptance=False, originalWorkloadInvoked=False)))


if __name__ == '__main__':
    main()
