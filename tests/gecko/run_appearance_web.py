#!/usr/bin/env python3
"""Actual Gecko/native receipts on synthetic loopback CSS, never the official site.

This runner requires an already installed integration APK. It never installs an
APK or invokes run_device.main(), and it gives each fixture phase one invocation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
from urllib.parse import parse_qs, urlsplit
import uuid
import xml.etree.ElementTree as ET
from zipfile import ZipFile

import run_device as device


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/gecko'))
from diagnostic_capture_privacy import checked_bytes, safe_error_text
OUT = ROOT / 'work/gecko-integration'
PACKAGE = 'local.pocketchat.test'
ACTION = 'appearanceSync'
ORIGIN = 'http://127.0.0.1:8765'
PHASES = ('prepare', 'dark', 'same', 'light', 'spa', 'reload', 'white', 'restore',
          'storageRead', 'storageWrite', 'storageRestore', 'newSession', 'oldSession', 'cleanup')
CAPTURE_PHASES = {'prepare', 'dark', 'light', 'white', 'newSession', 'oldSession'}
SCOPE = ('Actual Gecko and native receipt bridge using controlled synthetic loopback CSS; '
         'not a test of the official ChatGPT website. Storage faults and new-session creation '
         'use controlled test API injections, not real quota exhaustion or a user popup gesture.')


def require(condition, message):
    if not condition:
        raise ValueError('Appearance web fixture: ' + message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def asset_identity(apk):
    # The generator has already been staged before Gradle. Verify only: a stale
    # post-build source or overlay cannot silently become this run's expected asset.
    from generate_appearance_fixture import OVERLAY, RECEIPT, SOURCE, stage
    receipt = stage(ROOT, verify=True)
    with ZipFile(apk) as archive:
        for path in ('assets/gecko/appearance.js', 'assets/pocketchat-appearance-fixture.json'):
            require(archive.namelist().count(path) == 1, 'exactly one APK asset: ' + path)
        raw = archive.read('assets/gecko/appearance.js')
        embedded = archive.read('assets/pocketchat-appearance-fixture.json')
        require(raw == (ROOT / OVERLAY).read_bytes(), 'APK overlay differs from staged exact transform')
        require(embedded == (ROOT / RECEIPT).read_bytes(), 'APK transform receipt differs from generated receipt')
        require(json.loads(embedded) == receipt and digest(raw) == receipt['overlaySha256'], 'APK overlay receipt hash')
        require(digest((ROOT / SOURCE).read_bytes()) == receipt['sourceSha256'], 'production source hash')
        # These bridge assets remain the exact production source in the test APK.
        for name in ('content.js', 'background.js', 'manifest.json'):
            path = 'assets/gecko/' + name
            require(archive.namelist().count(path) == 1, 'exactly one production bridge asset: ' + name)
            require(archive.read(path) == (ROOT / 'app/src/main/assets/gecko' / name).read_bytes(),
                    'APK production bridge differs from selected source: ' + name)
    return receipt


def release_assets(paths):
    source = (ROOT / 'app/src/main/assets/gecko/appearance.js').read_bytes()
    rows = []
    for path in paths:
        require(path.is_file(), 'selected release APK does not exist: ' + str(path))
        with ZipFile(path) as archive:
            require(archive.namelist().count('assets/gecko/appearance.js') == 1, 'release appearance asset')
            raw = archive.read('assets/gecko/appearance.js')
            require(raw == source, 'release APK contains an overlay or stale production appearance asset')
            require('assets/pocketchat-appearance-fixture.json' not in archive.namelist(),
                    'release APK contains the integration fixture receipt')
        rows.append(dict(path=str(path.resolve()), apkSha256=digest(path.read_bytes()),
                         appearanceSha256=digest(raw), productionAssetExact=True, fixtureReceiptAbsent=True))
    return rows


def verify_phase(result, phase, suite_nonce, assets):
    require(type(result.get('schema')) is int and result['schema'] == 1, phase + ': result schema')
    require(result.get('status') == 'passed' and result.get('phase') == phase, phase + ': native phase failed')
    require(result.get('suiteNonce') == suite_nonce, phase + ': suite nonce differs')
    checks = result.get('checks')
    require(isinstance(checks, list) and checks, phase + ': missing native checks')
    require(all(isinstance(row, dict) and isinstance(row.get('name'), str) and row['name']
                and row.get('pass') is True for row in checks), phase + ': incomplete or failed native check')
    require(len({row['name'] for row in checks}) == len(checks), phase + ': duplicate native check names')
    require(isinstance(result.get('scope'), str) and result['scope'], phase + ': missing scope')
    require(result.get('assets') == assets, phase + ': device asset receipt differs from APK')
    page, appearance = result.get('page'), result.get('appearance')
    require(isinstance(page, dict) and isinstance(appearance, dict), phase + ': missing DOM/native observations')
    location = urlsplit(page.get('url', ''))
    require(location.scheme == 'http' and location.netloc == '127.0.0.1:8765'
            and location.path.startswith('/appearance-sync/')
            and parse_qs(location.query).get('runNonce') == [suite_nonce], phase + ': unowned observed page URL')
    require(isinstance(page.get('fixtureDocument'), str)
            and re.fullmatch('[a-zA-Z0-9-]{16,80}', page['fixtureDocument']), phase + ': missing actual document marker')
    require(result.get('actualAndroidExecution') is True and result.get('actualGeckoExecution') is True
            and result.get('synthetic') is True, phase + ': native execution scope')
    if phase == 'cleanup':
        return
    expected_dark = phase not in {'prepare', 'light', 'spa', 'reload', 'newSession'}
    expected_status = {'white': 'failed', 'storageRead': 'partial', 'storageWrite': 'partial'}.get(phase, 'confirmed')
    require(appearance.get('status') == expected_status and appearance.get('desiredDark') is expected_dark,
            phase + ': unexpected native outcome')
    require(type(appearance.get('version')) is int and appearance['version'] > 0
            and appearance.get('received') is True and appearance.get('applied') is True,
            phase + ': actual native receipt stages missing')
    require(page.get('isolatedHelper') is True and page.get('isolatedNativeBridge') is True
            and page.get('mainWorldHelper') == 'undefined'
            and page.get('colorScheme') == ('dark' if expected_dark else 'light'),
            phase + ': actual isolated-world helper or selected root attributes differ')
    require(set(page.get('rootClass', '').split()) == {'dark' if expected_dark else 'light'},
            phase + ': selected root class differs')
    wire = result.get('wireReceipts')
    require(isinstance(wire, list) and bool(wire), phase + ': original wire receipts missing')
    require(all(isinstance(row, dict) and isinstance(row.get('receipt'), dict)
                and type(row.get('port')) is int and type(row.get('elapsed')) is int for row in wire),
            phase + ': malformed original wire trace')
    current = [row['receipt'] for row in wire if row['port'] == result.get('nativePort')
               and row['receipt'].get('version') == appearance['version']]
    require({'received', 'applied', 'observed'} <= {row.get('stage') for row in current},
            phase + ': current native version lacks complete real wire stages')
    documents = {row.get('documentId') for row in current}
    require(len(documents) == 1 and isinstance(next(iter(documents)), str)
            and re.fullmatch('[a-zA-Z0-9-]{16,80}', next(iter(documents))),
            phase + ': wire stages belong to different documents')
    require(all(row.get('kind') == 'appearanceReceipt' and row.get('protocol') == 1
                and row.get('dark') is expected_dark for row in current), phase + ': wire protocol/theme differs')
    observed = [row for row in current if row.get('stage') == 'observed'][-1]
    expected_storage = {'storageRead': 'unavailable', 'storageWrite': 'failed'}.get(phase)
    expected_colors = 'mismatch' if phase == 'white' else 'verified'
    require(appearance.get('colorStatus') == observed.get('colorStatus') == expected_colors,
            phase + ': native and actual observed colors differ')
    if expected_storage:
        require(appearance.get('storage') == observed.get('storage') == expected_storage
                and appearance.get('attempt') == 3, phase + ': controlled storage failure was not retained')
    elif phase != 'white':
        require(appearance.get('storage') in {'written', 'unchanged'}
                and observed.get('storage') in {'written', 'unchanged'}, phase + ': unpersisted theme was confirmed')
    samples = observed.get('samples')
    require(isinstance(samples, list), phase + ': computed receipt samples missing')
    regions = {row.get('region'): row for row in samples if isinstance(row, dict)}
    require({'main', 'composer'} <= set(regions), phase + ': both visible chat regions must be observed')
    for name in ('main', 'composer'):
        sample = regions[name]
        value = sample.get('backgroundLuminance')
        require(sample.get('visible') is True and type(value) in (int, float) and 0 <= value <= 1,
                phase + ': actual visible computed ' + name + ' sample unavailable')
        require((value > .5 if phase == 'white' or not expected_dark else value < .35),
                phase + ': actual computed ' + name + ' luminance does not match the expected CSS behavior')


def verify_continuity(invocations):
    """Cross-check actual documents, versions and native session identity."""
    rows = {row['phase']: row['result'] for row in invocations}
    base = rows['prepare']
    native = base['nativeSession']
    original_document = base['page']['fixtureDocument']
    current_document = original_document
    cookie = base['page']['cookie']
    previous_version = 0
    captured = set()
    for phase in PHASES:
        row, page, appearance = rows[phase], rows[phase]['page'], rows[phase]['appearance']
        for point in row.get('wireReceipts', []):
            captured.add((point['port'], json.dumps(point['receipt'], sort_keys=True)))
        replays = row.get('staleReceiptReplays')
        require(isinstance(replays, list) and len(replays) == (1 if phase in {'same', 'reload', 'newSession', 'oldSession'} else 0),
                phase + ': stale-receipt replay evidence differs')
        for replay in replays:
            require(replay.get('nativeAccepted') is False
                    and (replay.get('port'), json.dumps(replay.get('receipt'), sort_keys=True)) in captured,
                    phase + ': production did not reject a previously captured exact raw receipt')
            require(replay['receipt']['version'] < appearance['version'],
                    phase + ': replay was not an older actual native version')
            current = [point['receipt'] for point in row['wireReceipts']
                       if point['port'] == row['nativePort'] and point['receipt']['version'] == appearance['version']]
            require(bool(current), phase + ': current replay comparison lacks original wire bytes')
            if phase == 'same':
                require(replay['port'] == row['nativePort']
                        and replay['receipt']['documentId'] == current[-1]['documentId'],
                        'Same-theme retry did not exercise an older version in the same document')
            else:
                require(replay['port'] != row['nativePort']
                        and replay['receipt']['documentId'] != current[-1]['documentId'],
                        phase + ': stale receipt did not belong to a different actual document/port')
        if phase in {'storageRead', 'storageWrite'}:
            injection = row.get('storageInjection', {})
            require(injection.get('ready') is True
                    and injection.get('method') == ('getItem' if phase == 'storageRead' else 'setItem')
                    and injection.get('errorName') == 'SecurityError'
                    and injection.get('errorMessage') == 'Controlled fixture API injection',
                    phase + ': isolated-world API injection was not actually observed')
        if phase != 'cleanup':
            require(appearance['version'] > previous_version, phase + ': explicit native synchronization did not advance version')
            previous_version = appearance['version']
        if phase == 'newSession':
            require(row['nativeSession'] != native and page['fixtureDocument'] != current_document,
                    'New actual native session or document was reused')
        else:
            require(row['nativeSession'] == native, phase + ': original native Gecko session replaced')
            if phase == 'reload':
                require(page['fixtureDocument'] != current_document
                        and page['url'] == rows['spa']['page']['url']
                        and row['nativePort'] != rows['spa']['nativePort'],
                        'Same-URL reload did not replace the actual document and bridge')
                current_document = page['fixtureDocument']
            else:
                require(page['fixtureDocument'] == current_document, phase + ': appearance changed the actual page document')
        if phase not in {'newSession', 'cleanup'}:
            require(page.get('draft') == 'unsent appearance fixture draft'
                    and page.get('selectionStart') == 7 and page.get('selectionEnd') == 17,
                    phase + ': appearance lost the unsent draft or selection')
        if phase != 'cleanup':
            require(page.get('cookie') == cookie, phase + ': appearance changed document cookies')
    require('appearance-fixture=' not in rows['cleanup']['page'].get('cookie', ''),
            'Owned fixture cookie was not retired')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', required=True)
    parser.add_argument('--serial', default='emulator-5554')
    parser.add_argument('--apk', type=Path, default=ROOT / 'app/build/outputs/apk/integration/app-x86_64-integration.apk')
    parser.add_argument('--release-apk', type=Path, action='append',
                        help='Also verify this release APK contains the unchanged production appearance asset')
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    require(not list(OUT.glob('appearance-web-*')), 'archive prior appearance-web evidence before another run')
    suite_nonce = uuid.uuid4().hex
    invocations, commands, captures, servers, started_servers, reversed_ports = [], [], [], [], [], []
    report = dict(schema=1, status='failed', runNonce=suite_nonce, scope=SCOPE,
                  actualAndroidExecution=False, synthetic=True, officialChatGptSiteTested=False,
                  automaticRetryPerformed=False, phaseTimeoutSeconds=35,
                  invocations=invocations, adbObservations=commands, captures=captures)

    def save_json(path, value):
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    def adb(*parts, binary=False, timeout=30, check=True):
        command = [args.adb, '-s', args.serial, *parts]
        try:
            value = subprocess.run(command, capture_output=True, timeout=timeout)
            stdout, stderr, code = value.stdout, value.stderr, value.returncode
        except subprocess.TimeoutExpired as error:
            stdout, stderr, code = error.stdout or b'', error.stderr or b'', None
        index = len(commands) + 1
        observation = dict(index=index, command=command, returnCode=code, streams={})
        public_stdout = stdout
        for stream, raw in (('stdout', stdout), ('stderr', stderr)):
            # Only logcat diagnostics are byte derivatives; primary commands remain exact.
            stored, privacy = checked_bytes(raw) if parts and parts[0] == 'logcat' else (raw, None)
            path = OUT / ('appearance-web-adb-%04d-%s.raw' % (index, stream))
            path.write_bytes(stored)
            observation['streams'][stream] = dict(path=path.name, bytes=len(stored), sha256=digest(stored))
            if privacy is not None:
                observation['streams'][stream]['capturePrivacy'] = privacy
                if stream == 'stdout':
                    public_stdout = stored
        commands.append(observation)
        if check and code != 0:
            raise RuntimeError('Appearance fixture ADB command failed: ' + repr(observation))
        return public_stdout if binary else public_stdout.decode('utf-8', errors='strict')

    def capture(phase):
        png = adb('exec-out', 'screencap', '-p', binary=True)
        require(png.startswith(b'\x89PNG\r\n\x1a\n'), phase + ': screenshot is not PNG')
        png_path = OUT / ('appearance-web-' + phase + '.png')
        png_path.write_bytes(png)
        adb('shell', 'uiautomator', 'dump', '/sdcard/pocket-appearance-web.xml')
        xml = adb('exec-out', 'cat', '/sdcard/pocket-appearance-web.xml', binary=True)
        require(ET.fromstring(xml).tag == 'hierarchy', phase + ': invalid Android UI XML')
        xml_path = OUT / ('appearance-web-' + phase + '.xml')
        xml_path.write_bytes(xml)
        captures.append(dict(phase=phase, screenshot=dict(path=png_path.name, bytes=len(png), sha256=digest(png)),
                             uiXml=dict(path=xml_path.name, bytes=len(xml), sha256=digest(xml))))

    def run_phase(phase, identity, assets):
        nonce = uuid.uuid4().hex
        invocation = dict(phase=phase, runNonce=nonce, suiteNonce=suite_nonce,
                          fixtureAction=ACTION, processSlot=0, events=[])
        invocations.append(invocation)
        def fetch(uri):
            raw = adb('exec-out', 'content', 'read', '--uri', uri, binary=True,
                      timeout=max(.1, min(30, deadline - time.monotonic())))
            path = OUT / ('appearance-web-' + phase + '-event-' + uri.rsplit('/', 1)[1] + '.raw.json')
            path.write_bytes(raw)
            return raw
        transfer = device.EventTransfer(identity=identity, nonce=nonce, slot=0, action=ACTION, fetch=fetch)
        invocation['events'] = transfer.records
        adb('logcat', '-c')
        deadline = time.monotonic() + 35
        invocation['startOutput'] = adb('shell', 'am', 'start', '-W', '-n',
            PACKAGE + '/local.pocketchat.GeckoIntegrationTestActivity',
            '--es', 'fixtureAction', ACTION, '--es', 'eventNonce', nonce,
            '--es', 'appearancePhase', phase, '--es', 'appearanceSuiteNonce', suite_nonce,
            timeout=min(30, deadline - time.monotonic()))
        while time.monotonic() < deadline:
            raw = adb('logcat', '-d', '-s', 'PocketGeckoIntegration:I', 'AndroidRuntime:E', '*:S',
                      binary=True, timeout=max(.1, min(30, deadline - time.monotonic())))
            (OUT / ('appearance-web-' + phase + '.raw.log')).write_bytes(raw)
            log = raw.decode('utf-8', errors='strict')
            require('FATAL EXCEPTION' not in log, phase + ': Android fixture process crashed')
            for line in log.splitlines():
                if 'PocketGeckoIntegration' not in line:
                    continue
                receipt = device.parse_receipt_line(line)
                if receipt is None or receipt.get('runNonce') != nonce:
                    continue
                require(receipt.get('kind') != 'eventTransportError', phase + ': native event publication failed')
                event = transfer.read(receipt)
                save_json(OUT / ('appearance-web-' + phase + '-transport.json'), transfer.records)
                require(event.get('kind') != 'error', phase + ': native fixture error: ' + repr(event))
                if event.get('kind') != ACTION:
                    continue
                invocation['result'] = event['result']
                invocation['elapsedSeconds'] = 35 - (deadline - time.monotonic())
                verify_phase(event['result'], phase, suite_nonce, assets)
                if phase in CAPTURE_PHASES:
                    capture(phase)
                return
            time.sleep(min(.15, max(0, deadline - time.monotonic())))
        raise TimeoutError(phase + ': no owned native appearance result within 35 seconds')

    try:
        source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        tree = subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], cwd=ROOT, text=True).strip()
        require(not subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip(),
                'exact clean committed fixture source required')
        gradle = (ROOT / 'app/build.gradle').read_text()
        identity = device.expected_build(args.apk.resolve(), source, tree,
            re.search(r"versionName '([^']+)'", gradle).group(1), int(re.search(r'versionCode (\d+)', gradle).group(1)))
        assets = asset_identity(args.apk.resolve())
        report.update(sourceCommit=source, sourceTree=tree, buildIdentity=identity, assets=assets)
        paths = args.release_apk if args.release_apk is not None else sorted((ROOT / 'app/build/outputs/apk/release').glob('*.apk'))
        report['releaseApks'] = release_assets(paths)
        report['releaseApkAvailable'] = bool(paths)
        names = ('tests/gecko/run_appearance_web.py', 'tests/gecko/fixtures/appearance-sync.html',
                 'tests/gecko/GeckoAppearanceIntegration.java', 'tools/gecko/generate_appearance_fixture.py',
                 'app/src/main/java/local/pocketchat/GeckoWebView.java',
                 'app/src/main/java/local/pocketchat/WebAppearanceSync.java',
                 'app/src/main/assets/gecko/appearance.js', 'app/src/main/assets/gecko/content.js')
        report['sourceFileSha256'] = {name: digest((ROOT / name).read_bytes()) for name in names}
        body = (ROOT / 'tests/gecko/fixtures/appearance-sync.html').read_bytes()
        requests = []
        report['httpRequests'] = requests
        device.fixture.TRACE.clear()
        report['proxyTrace'] = device.fixture.TRACE

        class AppearanceFixture(device.fixture.http.server.BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'
            def log_message(self, *unused):
                pass
            def do_GET(self):
                target = urlsplit(self.path)
                query = parse_qs(target.query)
                owned = (target.path.startswith('/appearance-sync/')
                         and query.get('runNonce') == [suite_nonce]
                         and self.headers.get('Host') == '127.0.0.1:8765')
                requests.append(dict(method='GET', path=target.path, query=target.query,
                                     host=self.headers.get('Host'), accepted=owned,
                                     observedAtMonotonicNs=time.monotonic_ns()))
                payload = body if owned else b'Only this invocation\'s controlled appearance fixture is served.\n'
                self.send_response(200 if owned else 404)
                self.send_header('Content-Type', 'text/html; charset=utf-8' if owned else 'text/plain; charset=utf-8')
                self.send_header('Content-Length', str(len(payload)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(payload)

        servers.append(device.fixture.http.server.ThreadingHTTPServer(('127.0.0.1', 8765), AppearanceFixture))
        servers.append(device.Server(('127.0.0.1', 1080), device.Socks))
        for server in servers:
            threading.Thread(target=server.serve_forever, daemon=True).start()
            started_servers.append(server)
        for port in (1080, 8765):
            adb('reverse', 'tcp:' + str(port), 'tcp:' + str(port))
            reversed_ports.append(port)
        # Clearing this integration package also removes ensureBuiltIn's cached
        # extension version. Never reuse same-version production JS by accident.
        adb('shell', 'am', 'force-stop', PACKAGE)
        require(adb('shell', 'pm', 'clear', PACKAGE).strip() == 'Success', 'integration package clear failed')
        before = adb('exec-out', 'content', 'read', '--uri', 'content://' + PACKAGE + '.evidence/build-identity', binary=True)
        (OUT / 'appearance-web-installed-before.raw.json').write_bytes(before)
        device.verify_installed(json.loads(before), identity)
        report['installedBefore'] = json.loads(before)
        if int(adb('shell', 'getprop', 'ro.build.version.sdk').strip()) >= 33:
            adb('shell', 'pm', 'grant', PACKAGE, 'android.permission.POST_NOTIFICATIONS')
        report['actualAndroidFixtureAttempted'] = True
        for phase in PHASES:
            run_phase(phase, identity, assets)
        verify_continuity(invocations)
        after = adb('exec-out', 'content', 'read', '--uri', 'content://' + PACKAGE + '.evidence/build-identity', binary=True)
        (OUT / 'appearance-web-installed-after.raw.json').write_bytes(after)
        device.verify_installed(json.loads(after), identity)
        report['installedAfter'] = json.loads(after)
        require(any(row['accepted'] for row in requests), 'no actual owned HTTP fixture request')
        require(any(row.get('kind') == 'socks' and row.get('accepted') is True for row in device.fixture.TRACE),
                'no actual accepted controlled SOCKS request')
        report.update(status='passed', actualAndroidExecution=True,
                      phaseCount=len(invocations), checkCount=sum(len(row['result']['checks']) for row in invocations))
    except BaseException as error:
        report.update(status='failed', error=type(error).__name__ + ': ' + safe_error_text(error, use_repr=False))
        if report.get('actualAndroidFixtureAttempted'):
            try:
                capture('failure')
            except BaseException as secondary:
                report['failureCaptureError'] = type(secondary).__name__ + ': ' + safe_error_text(secondary, use_repr=False)
        raise
    finally:
        if commands:
            try:
                raw = adb('logcat', '-d', binary=True, check=False)
                (OUT / 'appearance-web-logcat.raw.log').write_bytes(raw)
            except BaseException as error:
                report['finalLogError'] = safe_error_text(error, use_repr=False)
        for port in reversed_ports:
            try:
                adb('reverse', '--remove', 'tcp:' + str(port), check=False)
            except BaseException as error:
                report.setdefault('cleanupErrors', []).append(safe_error_text(error, use_repr=False))
        with device.fixture.CONNECTION_LOCK:
            for connection in tuple(device.fixture.CONNECTIONS):
                try:
                    connection.close()
                except OSError:
                    pass
        for server in servers:
            if server in started_servers:
                server.shutdown()
            server.server_close()
        save_json(OUT / ('appearance-web-results.json' if report['status'] == 'passed' else 'appearance-web-failure.json'), report)
    print(json.dumps(dict(status=report['status'], runNonce=suite_nonce, phases=report['phaseCount'],
                          checks=report['checkCount'], scope=SCOPE), sort_keys=True))


if __name__ == '__main__':
    main()
