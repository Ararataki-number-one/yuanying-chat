#!/usr/bin/env python3
"""Bounded real-CM preflight for the fixed synthetic emulator, never app acceptance."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import time
import uuid

try:
    from .profile_invocation_contract import expected_build, verify_installed
except ImportError:
    from profile_invocation_contract import expected_build, verify_installed

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = 'com.google.android.googlesdksetup'
SERIAL = 'emulator-5554'
AUTHORITY = 'local.pocketchat.test.network-preflight'
SSID = 'AndroidWifi'


def validate_observation(value, identity, nonce):
    """Reject stale/foreign or promoted metadata; usability is an actual CM value."""
    if (not isinstance(value, dict) or value.get('schema') != 1
            or value.get('runNonce') != nonce or not re.fullmatch('[0-9a-f]{32}', nonce)
            or value.get('sourceCommit') != identity['sourceCommit']):
        raise ValueError('Exact native preflight invocation/source required')
    if not isinstance(value.get('buildIdentity'), dict):
        raise ValueError('Native installed APK identity required')
    verify_installed(value['buildIdentity'], identity)
    if (value.get('actualAndroidExecution') is not True
            or value.get('actualConnectivityManagerExecution') is not True
            or any(value.get(key) is not False for key in
                   ['actualGeckoExecution', 'applicationAcceptance', 'physicalPhoneAcceptance'])
            or type(value.get('androidSdk')) is not int or value['androidSdk'] < 26
            or type(value.get('pid')) is not int or value['pid'] <= 0
            or type(value.get('observedAtElapsedRealtime')) is not int
            or value['observedAtElapsedRealtime'] < 0):
        raise ValueError('Native environment observation scope is invalid')
    for key in ['capabilitiesPresent', 'internetCapability', 'stableDuringRead', 'usable']:
        if type(value.get(key)) is not bool:
            raise ValueError('Actual CM field must be boolean: ' + key)
    active, after = value.get('activeNetwork'), value.get('activeNetworkAfter')
    if not isinstance(active, str) or not isinstance(after, str):
        raise ValueError('Actual active-network identities required')
    stable = bool(active) and active == after
    if value['internetCapability'] and not value['capabilitiesPresent']:
        raise ValueError('INTERNET cannot be observed without network capabilities')
    if not active and (value['capabilitiesPresent'] or value['internetCapability']):
        raise ValueError('Absent active network cannot have captured capabilities')
    usable = stable and value['capabilitiesPresent'] and value['internetCapability']
    if value['stableDuringRead'] != stable or value['usable'] != usable:
        raise ValueError('Native CM usability does not match its captured fields')
    return usable


class Commands:
    def __init__(self, executable, serial, record, deadline):
        if serial != SERIAL:
            raise ValueError('Only the fixed synthetic adb target is allowed')
        self.executable, self.serial, self.record, self.deadline = executable, serial, record, deadline

    def run(self, *parts, check=True, diagnostic=False):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Bounded emulator environment preflight expired')
        command = [self.executable, '-s', self.serial, *parts]
        timeout = min(2 if diagnostic else 8, remaining)
        try:
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, timeout=timeout)
        except subprocess.TimeoutExpired as error:
            def decoded(raw):
                return raw.decode('utf-8', errors='replace') if isinstance(raw, bytes) else (raw or '')
            self.record['commands'].append(dict(command=command, exitCode=None, timedOut=True,
                stdout=decoded(error.stdout), stderr=decoded(error.stderr),
                observedAt=time.monotonic(), timeoutSeconds=timeout))
            raise
        self.record['commands'].append(dict(command=command, exitCode=result.returncode,
            stdout=result.stdout, stderr=result.stderr, timedOut=False,
            observedAt=time.monotonic(), timeoutSeconds=timeout))
        self.record['actualAndroidCommands'] = True
        if check:
            result.check_returncode()
        return result.stdout.replace('\r', '').strip()


def network_observation(commands, record, identity, phase):
    nonce = uuid.uuid4().hex
    raw = commands.run('exec-out', 'content', 'read', '--uri',
                       'content://' + AUTHORITY + '/default-network?runNonce=' + nonce)
    row = dict(phase=phase, runNonce=nonce, raw=raw, receivedAt=time.monotonic())
    record['networkObservations'].append(row)
    value = json.loads(raw)
    usable = validate_observation(value, identity, nonce)
    row['value'] = value
    record['actualIntegrationProviderExecution'] = True
    record['actualConnectivityManagerExecution'] = True
    return usable


def provision_sdk_wifi(commands, record, identity, phase, observation_phase):
    """Restore only the observed SDK AP, within the original preflight deadline."""
    stage = dict(phase=phase, startedAt=time.monotonic(),
                 firstCommand=len(record['commands']),
                 firstNetworkObservation=len(record['networkObservations']),
                 wifiScans=[], status='failed')
    record.setdefault('sdkWifiProvisioningStages', []).append(stage)
    try:
        # Reproduce only the SDK image's AndroidWifi provisioning convention.
        # No airplane/mobile-data change, arbitrary SSID, or IME policy change.
        commands.run('shell', 'cmd', 'wifi', 'set-wifi-enabled', 'enabled')
        scan_deadline = min(commands.deadline - 10, time.monotonic() + 8)
        while True:
            scan = commands.run('shell', 'cmd', 'wifi', 'list-scan-results')
            record['wifiScan'] = scan
            stage['wifiScans'].append(dict(raw=scan, receivedAt=time.monotonic()))
            # Exact SSID column followed by optional capability flags. Never
            # accept a similarly named AP such as AndroidWifi-other.
            if any(re.search(r'\sAndroidWifi\s*(?:\[[^\n]*\])?\s*$', line) for line in scan.splitlines()):
                break
            if time.monotonic() >= scan_deadline:
                raise ValueError('The SDK emulator AndroidWifi access point was not observed')
            time.sleep(min(1, max(0, scan_deadline - time.monotonic())))
        commands.run('shell', 'cmd', 'wifi', 'connect-network', SSID, 'open')
        record['sdkWifiProvisioningRequested'] = True
        while not network_observation(commands, record, identity, observation_phase):
            if commands.deadline - time.monotonic() <= 1:
                raise TimeoutError('Actual Android active network with INTERNET did not become available')
            time.sleep(min(1, max(0, commands.deadline - time.monotonic())))
        stage['status'] = 'passed'
    finally:
        stage.update(completedAt=time.monotonic(),
                     afterCommand=len(record['commands']),
                     afterNetworkObservation=len(record['networkObservations']))


def preflight(commands, record, identity):
    if commands.run('shell', 'getprop', 'ro.kernel.qemu') != '1':
        raise ValueError('The fixed adb target is not a confirmed emulator')
    record['confirmedQemu'] = True
    # These readings describe image provisioning; no input policy is modified.
    for key in ['show_ime_with_hard_keyboard', 'default_input_method', 'enabled_input_methods']:
        record['initialInputSettings'][key] = commands.run('shell', 'settings', 'get', 'secure', key)
    record['initialKeyboardLayoutProperty'] = commands.run('shell', 'getprop', 'vendor.qemu.keyboard_layout')
    before = network_observation(commands, record, identity, 'before-network-configuration')
    record['initialNetworkUsable'] = before
    if not before:
        provision_sdk_wifi(commands, record, identity, 'initial-network-provisioning',
                           'after-sdk-wifi-configuration')
    present = commands.run('shell', 'pm', 'list', 'packages', PACKAGE).splitlines()
    record['packagePresent'] = 'package:' + PACKAGE in present
    if record['packagePresent']:
        # Disable this captured first-boot ANR package only after real networking.
        commands.run('shell', 'am', 'force-stop', PACKAGE)
        commands.run('shell', 'pm', 'disable-user', '--user', '0', PACKAGE)
        disabled = commands.run('shell', 'pm', 'list', 'packages', '-d', PACKAGE).splitlines()
        if 'package:' + PACKAGE not in disabled:
            raise ValueError('Setup-package disabled state was not confirmed')
        record['disabledStateConfirmed'] = True
    if not network_observation(commands, record, identity, 'after-setup-package-handling'):
        # Setup may own the initial Wi-Fi request. Its removal can tear down a
        # network that was healthy above, so restore the same SDK AP and read CM
        # again. A successful shell command or an expired wait is never success.
        record['postSetupNetworkRecoveryRequired'] = True
        provision_sdk_wifi(commands, record, identity, 'post-setup-network-recovery',
                           'after-post-setup-sdk-wifi-configuration')
        if not network_observation(commands, record, identity, 'after-post-setup-network-recovery-confirmation'):
            raise ValueError('Actual default network disappeared after SDK Wi-Fi recovery')
    record['status'] = 'passed'


def diagnostics(commands, record):
    operations = [('connectivity', ('shell', 'dumpsys', 'connectivity')),
                  ('wifi', ('shell', 'dumpsys', 'wifi')),
                  ('routes', ('shell', 'ip', 'route', 'show', 'table', 'all')),
                  ('input-setting', ('shell', 'settings', 'get', 'secure', 'show_ime_with_hard_keyboard')),
                  ('airplane-setting', ('shell', 'settings', 'get', 'global', 'airplane_mode_on')),
                  ('setup-package', ('shell', 'dumpsys', 'package', PACKAGE))]
    for name, parts in operations:
        try:
            record['diagnostics'][name] = commands.run(*parts, check=False, diagnostic=True)
        except (OSError, subprocess.SubprocessError) as failure:
            record['diagnostics'][name] = dict(failureType=type(failure).__name__, reason=str(failure))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', required=True)
    parser.add_argument('--serial', required=True, choices=[SERIAL])
    parser.add_argument('--apk', required=True, type=Path)
    parser.add_argument('--timeout', type=int, default=45, help='Total preflight budget, 15..45 seconds')
    args = parser.parse_args()
    if not 15 <= args.timeout <= 45:
        parser.error('--timeout must be 15..45 seconds')
    out = ROOT / 'work/gecko-integration/emulator-bootstrap-results.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    record = dict(schema=2, status='failed', serial=args.serial, exactSetupPackage=PACKAGE,
        commands=[], networkObservations=[], diagnostics={}, initialInputSettings={},
        actualAndroidCommands=False, actualIntegrationProviderExecution=False,
        actualConnectivityManagerExecution=False, applicationAcceptance=False,
        actualGeckoExecution=False, physicalPhoneAcceptance=False, confirmedQemu=False,
        applicationOrInputPolicyModified=False, gestureReplayed=False,
        sdkWifiProvisioningRequested=False, disabledStateConfirmed=False,
        postSetupNetworkRecoveryRequired=False, sdkWifiProvisioningStages=[],
        scope='Synthetic emulator prerequisite only; not production Android, Gecko, website or phone acceptance')
    started = time.monotonic()
    deadline = started + args.timeout
    record.update(timeoutSeconds=args.timeout, startedAt=started)
    commands = None
    try:
        source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True, timeout=8).strip()
        tree = subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], cwd=ROOT, text=True, timeout=8).strip()
        record.update(sourceCommit=source, sourceTree=tree)
        if subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=normal'], cwd=ROOT, text=True, timeout=8).strip():
            raise ValueError('Emulator preflight requires a clean committed APK/source')
        settings = (ROOT / 'app/build.gradle').read_text()
        version = re.search(r"versionName '([^']+)'", settings).group(1)
        code = int(re.search(r'versionCode ([0-9]+)', settings).group(1))
        identity = expected_build(args.apk.resolve(), source, tree, version, code)
        record['expectedBuildIdentity'] = identity
        # Reserve up to twelve seconds for actual environment diagnostics.
        commands = Commands(args.adb, args.serial, record, deadline - 12)
        preflight(commands, record, identity)
    except (ValueError, OSError, subprocess.SubprocessError) as failure:
        record.update(failureType=type(failure).__name__, reason=str(failure),
                      failureClassification='emulator-environment-precondition')
        if commands is not None and record['confirmedQemu']:
            commands.deadline = deadline
            diagnostics(commands, record)
        raise
    finally:
        record['completedAt'] = time.monotonic()
        temporary = out.with_suffix('.partial')
        temporary.write_text(json.dumps(record, indent=2) + '\n')
        temporary.replace(out)
    print(json.dumps({key: record[key] for key in
        ['sourceCommit', 'status', 'initialNetworkUsable', 'sdkWifiProvisioningRequested',
         'disabledStateConfirmed', 'actualConnectivityManagerExecution', 'applicationAcceptance']}))


if __name__ == '__main__':
    main()
