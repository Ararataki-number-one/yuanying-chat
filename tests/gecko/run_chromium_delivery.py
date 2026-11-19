#!/usr/bin/env python3
"""Exercise standalone Gecko and inherited Chromium installation on a disposable Android emulator."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
import uuid
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/gecko'))
from stage_chromium_module import ASSET_SHA, ABI_CONFIGS, ABIS, DELIVERY, SIGNER, apk_signer, attributes, check_payload

ACTIVITY_NS = 'local.pocketchat.'
PACKAGES = ('local.pocketchat', 'local.pocketchat.test')
SAFE_SCREEN = ('请先确认此环境的网络设置', '请先为此环境配置网络线路', '此环境未明确启用系统直连', '系统网络尚未连接',
               'Chromium 尚不能验证此环境的受保护线路，可在环境设置中选择 Gecko')
FEATURE = 'chromium'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def git(*arguments):
    return subprocess.check_output(['git', '-C', str(ROOT), *arguments], text=True).strip()


def source_state():
    return {'sourceCommit': git('rev-parse', 'HEAD'), 'sourceTree': git('rev-parse', 'HEAD^{tree}'),
            'sourceDirty': bool(git('status', '--porcelain', '--untracked-files=normal'))}


def apk_info(args, apk):
    raw = subprocess.check_output([args.aapt2, 'dump', 'xmltree', '--file', 'AndroidManifest.xml', apk], text=True, timeout=40)
    sections, metadata = attributes(raw)
    root, sdk, application = (sections.get(name, {}) for name in ('manifest', 'uses-sdk', 'application'))
    role = root.get('split', '')
    version = root.get('versionName', args.version if role.startswith('chromium.config.') else None)
    require(root.get('package') == args.package and root.get('versionCode') == str(args.version_code)
            and version == args.version and root.get('versionCodeMajor', '0') == '0', 'Unexpected APK package or version: ' + apk.name)
    require(application, 'APK has no application manifest: ' + apk.name)
    minimum = int(sdk['minSdkVersion'])
    if not role:
        require(minimum == 26 and application.get('debuggable') == 'true'
                and application.get('extractNativeLibs', 'true') == 'true' and not root.get('requiredSplitTypes')
                and root.get('isFeatureSplit', 'false') == 'false' and application.get('isSplitRequired', 'false') == 'false',
                'Expected standalone, debuggable Android 8+ Gecko from the candidate (fixture needs run-as)')
        capability = [item.get('value') for item in metadata if item.get('name') == DELIVERY]
        require(capability == ['true']
                and not re.search(r'(?:com[.]cefrium|org[.]chromium[.](?:base|content|content_public|net))[.]', raw),
                'Candidate base lacks enabled delivery configuration or leaked engine components')
    elif role == FEATURE:
        require(26 <= minimum <= 29 and root.get('isFeatureSplit') == 'true'
                and not root.get('configForSplit'), 'Unexpected Chromium feature manifest')
    else:
        match = re.fullmatch(r'chromium[.]config[.]([A-Za-z0-9_]{1,60})', role)
        require(match and 26 <= minimum <= 29 and root.get('configForSplit') == FEATURE
                and application.get('hasCode') == 'false'
                and (match[1] not in ABI_CONFIGS or match[1] == ABIS[args.abi]),
                'Unexpected Chromium configuration role: ' + role)
    apk_signer(args.apksigner, apk, 26 if not role else 29, args.signer)
    engine = check_payload(apk, role, args.abi)
    return role, engine, {'path': str(apk.resolve()), 'file': apk.name, 'bytes': apk.stat().st_size,
                         'sha256': sha256(apk), 'signerSha256': args.signer, 'minSdk': minimum}


def artifact_set(args):
    role, engine, base = apk_info(args, args.base)
    require(not role and not engine, 'Base argument must be the standalone Gecko APK')
    split_set = {}
    native_roles = []
    shared_base = False
    for apk in sorted(args.splits.glob('*.apk')):
        role, engine, info = apk_info(args, apk)
        if not role:
            require(not shared_base and info['sha256'] == base['sha256'],
                    'Combined APK set does not contain the exact standalone base once')
            shared_base = True
            continue
        require(role not in split_set, 'Duplicate installed role ' + role)
        split_set[role] = info
        if engine:
            native_roles.append(role)
    require(shared_base, 'Combined APK set must include the same base exported by bundletool')
    require(FEATURE in split_set and len(native_roles) == 1 and 1 <= len(split_set) <= 64,
            'Expected the main feature and a single native engine location')
    require(sum(info['bytes'] for info in split_set.values()) <= 512 * 1024 * 1024, 'Feature set exceeds client limit')
    return {'base': base, **split_set}, native_roles[0]


class Device:
    def __init__(self, args):
        self.args = args
        self.nonce = uuid.uuid4().hex

    def adb(self, *arguments, timeout=None, check=True, input=None):
        result = subprocess.run([self.args.adb, '-s', self.args.serial, *map(str, arguments)],
                                input=input, text=True, capture_output=True, timeout=timeout or self.args.timeout)
        if check and result.returncode:
            raise RuntimeError(f'adb {arguments[0]} exited {result.returncode}: {(result.stdout + result.stderr)[-1500:]}')
        return result.stdout.strip()

    def shell(self, *arguments, **kwargs):
        return self.adb('shell', shlex.join(map(str, arguments)), **kwargs)

    def run_as(self, *arguments, **kwargs):
        return self.shell('run-as', self.args.package, *arguments, **kwargs)

    def wait(self, callback, reason):
        deadline = time.monotonic() + self.args.timeout
        while time.monotonic() < deadline:
            value = callback()
            if value:
                return value
            time.sleep(3)
        raise TimeoutError(reason)

    def guard(self):
        require(re.fullmatch(r'emulator-[0-9]{4,6}', self.args.serial) and self.shell('getprop', 'ro.kernel.qemu') == '1',
                'Device writes are restricted to a disposable emulator')
        abi = self.shell('getprop', 'ro.product.cpu.abi')
        sdk = int(self.shell('getprop', 'ro.build.version.sdk'))
        require(sdk >= 29 and abi == self.args.abi and self.shell('getprop', 'sys.boot_completed') == '1',
                'Wrong or not fully booted Android device')
        self.offline()
        require(self.shell('pm', 'path', 'android').startswith('package:'), 'Android Package Manager is unavailable')
        require(not self.installed_paths(), 'PocketChat already exists on this emulator. Use a fresh disposable guest')
        return {'sdk': sdk, 'abi': abi}

    def offline(self):
        webview = self.shell('dumpsys', 'webviewupdate')
        require(re.search(r'Current WebView package[^\n]*(?:null|none)', webview, re.IGNORECASE),
                'Disable WebView in the disposable device before running the acceptance')
        require(self.shell('settings', 'get', 'global', 'airplane_mode_on') == '1', 'Device airplane mode is off')
        connection = self.shell('dumpsys', 'connectivity')
        require(re.search(r'(?im)^\s*Active default network:\s*(none|null)\s*$', connection),
                'Could not prove Android has no active default network')

    def installed_paths(self):
        raw = self.shell('pm', 'path', self.args.package, check=False)
        paths = {}
        for line in raw.splitlines():
            if not line.startswith('package:'):
                continue
            path = line.removeprefix('package:')
            name = Path(path).name
            role = 'base' if name == 'base.apk' else name.removeprefix('split_').removesuffix('.apk')
            require(path.startswith('/data/app/') and (role == 'base' or name == f'split_{role}.apk') and role not in paths,
                    'Unexpected installed APK path: ' + path)
            paths[role] = path
        return paths

    def verify_device_file(self, path, expected):
        actual = self.shell('sha256sum', path).split()
        require(self.shell('stat', '-c', '%s', path) == str(expected['bytes']) and actual and actual[0] == expected['sha256'],
                'Device APK bytes differ from the validated source: ' + path)

    def verify_installed(self, expected):
        paths = self.installed_paths()
        require(paths.keys() == expected.keys(), 'Installed roles differ from the verified candidate')
        for role, path in paths.items():
            self.verify_device_file(path, expected[role])
        return paths

    def install(self, apks, inherit=False):
        uploaded = {}
        session = None
        try:
            for role, apk in apks.items():
                path = f'/data/local/tmp/pocketchat-chromium-{self.nonce}-{role}.apk'
                self.adb('push', '-Z', apk['path'], path)
                uploaded[role] = path
                self.verify_device_file(path, apk)
            flags = ['-t', '-S', str(sum(apk['bytes'] for apk in apks.values()))]
            if inherit:
                flags += ['-r', '-p', self.args.package]
            created = self.shell('pm', 'install-create', *flags)
            match = re.fullmatch(r'Success: created install session \[([0-9]+)\]', created)
            require(match, 'Android did not create an install session: ' + created)
            session = match[1]
            for role, path in uploaded.items():
                response = self.shell('pm', 'install-write', '-S', apks[role]['bytes'], session, role + '.apk', path)
                require(response.startswith('Success'), 'Installer rejected ' + role + ': ' + response)
            require(self.shell('pm', 'install-commit', session) == 'Success', 'Android did not install the APK set')
            return int(session)
        finally:
            commands = [('rm', '-f', path) for path in uploaded.values()]
            if session is not None:
                commands.insert(0, ('pm', 'install-abandon', session))
            for command in commands:
                try:
                    self.shell(*command, timeout=15, check=False)
                except (OSError, subprocess.TimeoutExpired):
                    pass

    def launch_default_entry(self):
        self.shell('input', 'keyevent', '224')
        self.shell('wm', 'dismiss-keyguard')
        self.shell('am', 'force-stop', self.args.package)
        started = self.shell('am', 'start', '-W', '-n', self.args.package + '/' + ACTIVITY_NS + 'MainActivity',
                             '-a', 'android.intent.action.VIEW', '-d', 'https://pocketchat-optional-fixture.invalid/')
        require('Status: ok' in started, 'PocketChat entry launch failed: ' + started)

    def resumed(self, activity):
        component = self.args.package + '/' + ACTIVITY_NS + activity
        short = self.args.package + '/.' + activity
        raw = self.shell('dumpsys', 'activity', 'activities', timeout=25, check=False)
        return next((line.strip() for line in raw.splitlines() if 'ResumedActivity' in line
                     and any(re.search(r'\b' + re.escape(value) + r'(?=\s|\})', line) for value in (component, short))), '')

    def native_engine(self, library, require_main_maps=False):
        processes = self.shell('ps', '-A', '-o', 'PID,NAME', timeout=20, check=False)
        main_maps_read = False
        for line in processes.splitlines():
            parts = line.split()
            if len(parts) != 2 or not parts[0].isdigit() or not (parts[1] == self.args.package
                    or parts[1].startswith(self.args.package + ':gecko_env')):
                continue
            maps = self.run_as('cat', '/proc/' + parts[0] + '/maps', timeout=20, check=False)
            if parts[1] == self.args.package and re.search(r'(?m)^[0-9a-f]+-[0-9a-f]+\s', maps):
                main_maps_read = True
            match = re.search(r'(?m)^[0-9a-f]+-[0-9a-f]+\s.*(?:/|!/)' + re.escape(library) + r'(?=\s|$).*$', maps)
            if match:
                return {'pid': int(parts[0]), 'process': parts[1], 'libraryMap': match[0]}
        require(not require_main_maps or main_maps_read, 'Could not inspect actual engine host process memory mappings')
        return None

    def gecko_runtime(self):
        mapped = self.native_engine('libxul.so')
        if mapped:
            return mapped
        pid = self.shell('pidof', self.args.package, timeout=15, check=False)
        if not pid.isdecimal():
            return None
        raw = self.adb('logcat', '-d', '--pid=' + pid, '-s', 'GeckoThread:D', '*:S', timeout=25, check=False)
        event = next((line for line in raw.splitlines() if 'GeckoThread:' in line and 'State changed to RUNNING' in line), None)
        if event:
            return {'pid': int(pid), 'process': self.args.package, 'runningEvent': event}
        return None

    def seed_marker(self):
        script = 'mkdir -p files && printf %s ' + shlex.quote(self.nonce) + ' > files/pocketchat-chromium-delivery-fixture'
        self.run_as('sh', '-c', script)
        self.check_marker()

    def check_marker(self):
        require(self.run_as('cat', 'files/pocketchat-chromium-delivery-fixture') == self.nonce,
                'Private data marker was not retained by split installation')

    def engine_preference(self, pick_chromium=False):
        file = 'shared_prefs/chat.xml'
        self.shell('am', 'force-stop', self.args.package)
        raw = self.run_as('cat', file)
        xml = ElementTree.fromstring(raw)
        require(xml.tag == 'map', 'Unexpected SharedPreferences after native Gecko startup')
        choices = xml.findall("*[@name='browserStartScreen']")
        require(not choices or (len(choices) == 1 and choices[0].text == 'chatgpt-enhanced'),
                'Fresh environment is not default Gecko')
        if pick_chromium:
            choice = choices[0] if choices else ElementTree.SubElement(xml, 'string', {'name': 'browserStartScreen'})
            require(choice.tag == 'string', 'Unexpected engine preference type')
            choice.text = FEATURE
            updated = ElementTree.tostring(xml, encoding='unicode', xml_declaration=True)
            self.run_as('sh', '-c', f'cat > {file}.tmp && mv {file}.tmp {file}', input=updated)
            require(ElementTree.fromstring(self.run_as('cat', file)).find("string[@name='browserStartScreen']").text == FEATURE,
                    'Could not seed the independent fixture choice')

    def safe_status(self):
        file = f'/data/local/tmp/pocketchat-chromium-ui-{self.nonce}.xml'
        try:
            self.shell('uiautomator', 'dump', file, timeout=25, check=False)
            raw = self.shell('cat', file, timeout=15, check=False)
            if not raw.startswith('<?xml'):
                return None
            xml = ElementTree.fromstring(raw)
            return next((node.get('text') for node in xml.iter('node') if node.get('text') in SAFE_SCREEN), None)
        finally:
            self.shell('rm', '-f', file, timeout=15, check=False)


def run(args, report):
    device = Device(args)
    report.update(device.guard())
    report['runNonce'] = device.nonce
    artifacts = report['apkSet']
    base = {'base': artifacts['base']}
    report['baseOnlyInstallSession'] = device.install(base)
    report['baseOnlyPaths'] = device.verify_installed(base)
    device.offline()
    device.launch_default_entry()
    report['geckoForeground'] = device.wait(lambda: device.resumed('MainActivity'), 'MainActivity did not resume with Gecko')
    report['geckoNative'] = device.wait(device.gecko_runtime, 'No native Gecko startup in a live app process')
    require(device.native_engine('libcef.so', require_main_maps=True) is None, 'Chromium loaded before its split was present')
    report['initWithoutChromium'] = True
    device.seed_marker()
    device.engine_preference()
    report['inheritedInstallSession'] = device.install({role: apk for role, apk in artifacts.items() if role != 'base'}, inherit=True)
    report['inheritedPaths'] = device.verify_installed(artifacts)
    device.check_marker()
    report.update(appendInstall=True, baseDataRetained=True)
    device.offline()
    device.launch_default_entry()
    report['geckoAfterInstallForeground'] = device.wait(lambda: device.resumed('MainActivity'), 'Module install changed the Gecko default')
    report['geckoAfterInstallNative'] = device.wait(device.gecko_runtime, 'Default Gecko did not load after feature install')
    device.engine_preference(pick_chromium=True)
    device.launch_default_entry()
    report['chromiumForeground'] = device.wait(lambda: device.resumed('CefriumBrowserActivity'), 'Environment selection did not open Chromium activity')
    report['chromiumOfflineStatus'] = device.wait(device.safe_status, 'Chromium did not display a safe blocked network status')
    require(device.native_engine('libcef.so', require_main_maps=True) is None, 'Chromium initialized before the route allowed it')
    device.offline()
    device.check_marker()
    device.verify_installed(artifacts)
    require(all(report[key] == value for key, value in source_state().items()), 'Host source changed during invocation')
    report.update(systemWebViewUnavailable=True, offlineRouteRejectedBeforeNativeInitialization=True,
                  actualAndroidExecution=True, status='passed')


def joined_report(host, transcript):
    installed = host.get('apkSet', {})
    require(host.get('schema') == 1 and host.get('package') == 'local.pocketchat' and host.get('status') == 'passed'
            and type(host.get('sdk')) is int and host['sdk'] >= 29 and host.get('abi') == 'x86_64'
            and set(installed) == {'base', FEATURE} and host.get('nativeSplit') == FEATURE
            and host.get('sourceDirty') is False and host.get('nativeRenderer') is False,
            'Require a clean-source running Gecko/feature receipt for the exact two-APK x86_64 candidate')
    require(all(host.get(field) is True for field in ('actualAndroidExecution', 'initWithoutChromium', 'appendInstall',
                'baseDataRetained', 'systemWebViewUnavailable', 'offlineRouteRejectedBeforeNativeInitialization')),
            'The host device acceptance gates have not all passed')
    require(all(host.get(key) == value for key, value in source_state().items()),
            'Host receipt source does not match the active clean source')
    output = transcript.decode('utf-8')
    require(re.findall(r'(?m)^INSTRUMENTATION_CODE:\s*(-?[0-9]+)\s*$', output) == ['-1'],
            'Android instrumentation did not finish successfully')
    observed = {}
    for line in output.splitlines():
        if line.startswith('INSTRUMENTATION_RESULT: '):
            key, separator, value = line.removeprefix('INSTRUMENTATION_RESULT: ').partition('=')
            if separator and re.fullmatch(r'[A-Za-z][A-Za-z0-9]*', key):
                require(key not in observed, f'Duplicate instrumentation field {key}')
                observed[key] = value
    base, feature = installed['base']['sha256'], installed[FEATURE]['sha256']
    expected = {'scope': 'production-debug-synthetic-signing-local-content', 'package': 'local.pocketchat',
                'runNonce': host['runNonce'], 'baseSha256': base, 'featureSha256': feature,
                'versionCode': str(host['versionCode']), 'sdk': str(host['sdk']), 'abi': host['abi'],
                'androidExecution': 'true', 'noSystemWebViewProvider': 'true', 'localContentRendered': 'true',
                'defaultNetworkInitiallyPresent': 'true', 'defaultNetworkLost': 'true',
                'chromiumBrowserRetired': 'true', 'navigationAfterLossWasBlocked': 'true'}
    require(all(re.fullmatch(r'[a-f0-9]{64}', value) for value in (base, feature))
            and re.fullmatch(r'[a-f0-9]{32}', host['runNonce'])
            and all(observed.get(key) == value for key, value in expected.items()),
            'Renderer report does not match the exact installed pair, nonce, device or route-loss checks')
    require(re.fullmatch(r'[1-9][0-9]*', observed.get('nativeRenderers', ''))
            and re.fullmatch(r'[0-9]+(?:[.][0-9]+){3}', observed.get('chromiumVersion', ''))
            and observed.get('publicNetworkRouteVerified') == 'false'
            and observed.get('androidInstallerConfirmationVerified') == 'false',
            'Missing actual renderer evidence or unsupported public network/consent claim')
    protected = {}
    for prefix in ('protectedHttpProxy', 'protectedHttpsProxy', 'protectedSocksProxy'):
        require(all(observed.get(prefix + key) == 'true' for key in ('Handshake', 'Rendered', 'Revoked', 'NoPrivateBypass'))
                and all(re.fullmatch(r'[1-9][0-9]*', observed.get(prefix + key, '')) for key in ('HandshakeCount', 'PageCount'))
                and observed.get(prefix + 'HeldConnectionsClosed') == '1'
                and observed.get(prefix + 'PrivateTrapAccepted') == '0', 'Protected localhost fixture did not pass: ' + prefix)
        protected[prefix] = {'handshakes': int(observed[prefix + 'HandshakeCount']), 'pages': int(observed[prefix + 'PageCount']),
                             'heldConnectionsClosed': 1, 'privateTrapAccepted': 0}
        if prefix == 'protectedHttpsProxy':
            handshakes = observed.get(prefix + 'TlsHandshakeCount', '')
            require(re.fullmatch(r'[1-9][0-9]*', handshakes), 'Upstream HTTPS fixture lacks verified TLS handshakes')
            protected[prefix]['tlsHandshakes'] = int(handshakes)
    require(observed.get('tlsFixtureVerified') == 'true', 'Upstream HTTPS TLS fixture was not verified')
    unsupported = ('publicNetworkRouteVerified', 'vpnRouteVerified', 'internalRouteVerified', 'originTlsVerified')
    require(all(observed.get(key) == 'false' for key in unsupported), 'Unexpected real network verification claim')
    return dict(host, nativeRenderer=True, baseSha256=base, featureSha256=feature,
                nativeRendererCount=int(observed['nativeRenderers']), chromiumVersion=observed['chromiumVersion'],
                actualLocalRouteLoss=True, tlsFixtureVerified=True, **protected, **dict.fromkeys(unsupported, False),
                rendererTranscriptSha256=hashlib.sha256(transcript).hexdigest(),
                testScope='combined-debug-candidate-local-install-and-renderer',
                sourceEvidence='Clean host invocation plus exact artifacts. No embedded debug APK source stamp.')


def join_main():
    parser = argparse.ArgumentParser(description='Join a completed device receipt and the exact instrumentation output')
    parser.add_argument('--host-report', required=True, type=Path)
    parser.add_argument('--renderer-log', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(sys.argv[2:])
    host = json.loads(args.host_report.read_text(encoding='utf-8'))
    report = joined_report(host, args.renderer_log.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': report['status'], 'report': str(args.output)}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb')
    parser.add_argument('--aapt2', required=True)
    parser.add_argument('--apksigner', required=True)
    parser.add_argument('--serial')
    parser.add_argument('--disposable-emulator', action='store_true')
    parser.add_argument('--base', required=True, type=Path)
    parser.add_argument('--splits', required=True, type=Path)
    parser.add_argument('--package', choices=PACKAGES, default=PACKAGES[0])
    parser.add_argument('--version', required=True)
    parser.add_argument('--version-code', required=True, type=int)
    parser.add_argument('--abi', choices=tuple(ABIS), required=True)
    parser.add_argument('--signer', required=True, help='Expected SHA-256 digest of the dedicated test signer')
    parser.add_argument('--timeout', default=300, type=int)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    if not args.verify_only and not (args.adb and args.serial and args.disposable_emulator):
        parser.error('Running on Android requires --adb, --serial and --disposable-emulator')
    if not 10 <= args.timeout <= 900 or not re.fullmatch(r'[a-f0-9]{64}', args.signer) or args.signer == SIGNER:
        parser.error('Use a dedicated debug test signer and a bounded timeout of 10..900 seconds')
    report = {'schema': 1, 'status': 'running', 'testScope': 'split-install-debug-candidate',
              'actualAndroidExecution': False, 'actualOnlineSignedMetadataDownload': False,
              'actualSystemInstallerConsent': False, 'nativeRenderer': False, 'diagnosticOnly': True,
              'package': args.package, 'version': args.version, 'versionCode': args.version_code,
              'signerSha256': args.signer, **source_state(), 'runnerSha256': sha256(Path(__file__)),
              'sourceEvidence': 'Host invocation source snapshot plus exact candidate APK bytes'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        report['apkSet'], report['nativeSplit'] = artifact_set(args)
        report['verifiedCefriumAssets'] = sorted(ASSET_SHA)
        if args.verify_only:
            report['status'] = 'artifact-check-passed'
        else:
            run(args, report)
    except Exception as failure:
        report.update(status='failed', error=str(failure))
        if 'sdk' in report:
            try:
                raw = Device(args).adb('logcat', '-d', '-t', '1200', timeout=30, check=False)
                args.output.with_suffix('.logcat.txt').write_text(raw + '\n')
            except (OSError, subprocess.SubprocessError):
                pass
        raise
    finally:
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': report['status'], 'report': str(args.output)}, ensure_ascii=False))


if __name__ == '__main__':
    if sys.argv[1:2] == ['join-renderer']:
        join_main()
    else:
        main()
