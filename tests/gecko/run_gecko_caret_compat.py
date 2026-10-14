#!/usr/bin/env python3
"""Independent 14-case Android/Gecko compatibility evidence; normal mode requires actual APK/SDK byte binding."""
import argparse
import hashlib
import html
import http.server
import json
import pathlib
import select
import socket
import socketserver
import struct
import subprocess
import tempfile
import threading
import time
import urllib.parse
import sys
import secrets
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'tools/gecko'))
from caret_build_identity import audit_apk, digest, embedded_identity, require, strict_json, validate_sdk_receipt
from caret_dispatch import CaretDispatch
from installed_apk_read import read_installed_apk
from integration_event_contract import parse_receipt_line
from profile_invocation_contract import verify_installed

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / 'work/gecko-integration'
PACKAGE = 'local.pocketchat.test'
SEEDS = ['abcdefghij', 'abcdefghij', 'abcdef', 'undo draft', 'left-right', 'clipboard tail',
         'seed tail', 'seed tail', 'batch tail', 'abcdef', 'rejected draft', 'soft tail', 'A😀B', 'noop tail']
IDS = ['rapid-taps', 'selected-replace', 'arrow-delete', 'undo', 'ime-multiword', 'clipboard-paste',
       'chinese-composition', 'finish-composition', 'batch-commit', 'reversed-selection', 'rejected-input',
       'soft-single-char', 'codepoint-delete', 'noop-composition']


def capture_failure_diagnostics(adb_executable, serial, output):
    """Read terminal failure state without input, retries, or Activity changes."""
    output = pathlib.Path(output)
    remote_ui = '/sdcard/gecko-caret-compat-failure-' + secrets.token_hex(16) + '.xml'

    def read(*parts):
        return subprocess.check_output([str(adb_executable), '-s', serial, *parts],
                                       stderr=subprocess.PIPE, timeout=30)

    def read_ui():
        read('shell', 'uiautomator', 'dump', remote_ui)
        return read('exec-out', 'cat', remote_ui)

    # Window ownership is captured first, before the slower UI dump.
    operations = [
        ('gecko-caret-compat-failure-window.txt', lambda: read('shell', 'dumpsys', 'window')),
        ('gecko-caret-compat-failure-activity.txt', lambda: read('shell', 'dumpsys', 'activity', 'activities')),
        ('gecko-caret-compat-failure-screen.png', lambda: read('exec-out', 'screencap', '-p')),
        ('gecko-caret-compat-failure-ui.xml', read_ui),
        ('gecko-caret-compat-failure-log.txt', lambda: read('logcat', '-d')),
    ]
    captures = {}
    for name, capture in operations:
        record = dict(startedAtWallTimeMillis=time.time_ns() // 1_000_000,
                      startedAtMonotonicNanos=time.monotonic_ns())
        try:
            raw = capture()
            (output / name).write_bytes(raw)
            record.update(saved=True, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        except Exception as error:
            record.update(saved=False, error=str(error))
            for field in ('output', 'stderr'):
                value = getattr(error, field, None)
                if value is not None:
                    if isinstance(value, bytes):
                        value = value[:8192].decode('utf-8', 'replace')
                    record[field] = str(value)[:8192]
        finally:
            record['completedAtMonotonicNanos'] = time.monotonic_ns()
            record['completedAtWallTimeMillis'] = time.time_ns() // 1_000_000
        captures[name] = record
    return captures


def perform_android_action(action, adb):
    """Execute the complete decoded original request once, without delays or replay."""
    require(action.get('scenario') in IDS and isinstance(action.get('id'), str)
            and action['id'].startswith(action['scenario'] + '-'), 'Unexpected fixture action owner')
    invocations = []
    for command in action['commands']:
        require(isinstance(command, dict), 'Original Android command required')
        if command.get('op') == 'tap':
            require(set(command) == {'op', 'x', 'y', 'expectedCaret', 'clientPoint', 'nativeGeometry', 'viewport'}
                    and type(command['x']) is int and type(command['y']) is int
                    and command['x'] >= 0 and command['y'] >= 0, 'Unexpected original touch action')
            invocations.append(('shell', 'input', 'tap', str(command['x']), str(command['y'])))
        elif command.get('op') == 'text':
            require(set(command) == {'op', 'text'} and command['text'] in ('Q', 'Z', 'X'),
                    'Unapproved fixture text action')
            invocations.append(('shell', 'input', 'keyboard', 'text', command['text']))
        elif command.get('op') == 'key':
            require(set(command) == {'op', 'code'} and type(command['code']) is int
                    and command['code'] in (21, 67, 112), 'Unexpected original key action')
            invocations.append(('shell', 'input', 'keyboard', 'keyevent', str(command['code'])))
        elif command.get('op') == 'combination':
            require(set(command) == {'op', 'codes'} and command['codes'] == [113, 54],
                    'Unexpected original combination')
            invocations.append(('shell', 'input', 'keyboard', 'keycombination', '113', '54'))
        else:
            raise ValueError('Unknown original Android command: ' + repr(command))
    executions = action['executions']
    require(executions == [], 'Android action cannot be replayed')
    for index, (command, invocation) in enumerate(zip(action['commands'], invocations)):
        execution = dict(commandIndex=index, op=command['op'], invocationCount=1, completed=False)
        executions.append(execution)
        execution['adbStartedAtWallTimeMillis'] = time.time_ns() // 1_000_000
        execution['adbStartedAtMonotonicNanos'] = time.monotonic_ns()
        try:
            adb(*invocation)
            execution['completed'] = True
        finally:
            execution['adbCompletedAtMonotonicNanos'] = time.monotonic_ns()
            execution['adbCompletedAtWallTimeMillis'] = time.time_ns() // 1_000_000
    return executions


def document(case):
    # Seed only via immutable response HTML. No JS sets text, focus or selection.
    return ('''<!doctype html><html data-caret-case="''' + str(case) + '''"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Controlled original input semantics</title><style>
body{margin:0;padding:12px;background:white;font:18px monospace}textarea{box-sizing:border-box;width:100%;height:96px;padding:10px;border:1px solid #888;font:26px monospace;white-space:pre;resize:none}#other-draft{height:58px;margin-top:22px}button{margin-top:16px}h2{font:18px sans-serif}
</style><h2>''' + html.escape(IDS[case]) + '''</h2><textarea id="prompt-textarea" rows="2" spellcheck="false" autocorrect="off">''' +
            html.escape(SEEDS[case]) + '''</textarea><textarea id="other-draft" tabindex="-1">untouched independent draft</textarea>
<button id="send" type="button">Send</button></html>''').encode('utf-8')


class Fixture(http.server.BaseHTTPRequestHandler):
    requests = []

    def log_message(self, *args):
        pass

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(url.query)
        try:
            case = int(query.get('case', ['-1'])[0])
        except ValueError:
            case = -1
        if url.path != '/caret' or not 0 <= case < len(SEEDS):
            self.send_response(404)
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        self.requests.append({'case': case, 'id': IDS[case], 'method': 'GET', 'path': url.path})
        body = document(case)
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Set-Cookie', 'session=synthetic-caret; Path=/; SameSite=Strict')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def exact(sock, size):
    out = b''
    while len(out) < size:
        data = sock.recv(size - len(out))
        if not data:
            raise ConnectionError('Controlled proxy closed')
        out += data
    return out


class Socks(socketserver.BaseRequestHandler):
    routes = []

    def handle(self):
        client = self.request
        client.settimeout(20)
        try:
            version, count = exact(client, 2)
            assert version == 5 and 0 in exact(client, count)
            client.sendall(b'\x05\x00')
            version, command, _, kind = exact(client, 4)
            assert version == 5
            if kind == 1:
                host = socket.inet_ntoa(exact(client, 4))
            elif kind == 3:
                host = exact(client, exact(client, 1)[0]).decode('ascii')
            else:
                return
            port = struct.unpack('!H', exact(client, 2))[0]
            allowed = command == 1 and host == '127.0.0.1' and port == 8771
            self.routes.append({'host': host, 'port': port, 'addressType': kind, 'accepted': allowed})
            if not allowed:
                client.sendall(b'\x05\x02\x00\x01' + b'\x00' * 6)
                return
            with socket.create_connection(('127.0.0.1', 8771), timeout=10) as upstream:
                client.sendall(b'\x05\x00\x00\x01' + b'\x00' * 6)
                while True:
                    ready, _, _ = select.select([client, upstream], [], [], 20)
                    if not ready:
                        return
                    for source in ready:
                        data = source.recv(65536)
                        if not data:
                            return
                        (upstream if source is client else client).sendall(data)
        except (OSError, AssertionError, UnicodeError):
            return


class SocksServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def event_vectors(events):
    return dict(characterKeys=[e['key'] for e in events if e['type'] == 'keydown' and len(e['key'].encode('utf-16-le', 'surrogatepass')) // 2 == 1],
                beforeInputTypes=[e['inputType'] for e in events if e['type'] == 'beforeinput'],
                inputTypes=[e['inputType'] for e in events if e['type'] == 'input'],
                compositionTypes=[e['type'] for e in events if e['type'].startswith('composition')])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--adb', required=True)
    parser.add_argument('--serial', default='emulator-5554')
    parser.add_argument('--root', type=pathlib.Path, default=ROOT)
    parser.add_argument('--out', type=pathlib.Path, required=True)
    parser.add_argument('--normal-acceptance', action='store_true', help='Formal controlled compatibility mode; default is diagnostic.')
    for flag in ('build-receipt', 'sdk-receipt', 'sdk-aar', 'official-sdk-aar', 'integration-apk', 'release-apk'):
        parser.add_argument('--' + flag, type=pathlib.Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    require(not out.exists() or not any(out.iterdir()), 'Refusing to mix a new invocation with retained evidence')
    out.mkdir(parents=True, exist_ok=True)
    build = strict_json(args.build_receipt.read_text())
    sdk = validate_sdk_receipt(args.sdk_receipt, args.sdk_aar, args.root, args.official_sdk_aar)
    embedded = embedded_identity(sdk, args.sdk_receipt)
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=args.root, text=True).strip()
    require(source == embedded['sourceCommit'], 'Checkout differs from the actual SDK source receipt')
    require(build.get('schema') == 1, 'Unexpected APK build receipt schema')
    for key in ('sourceCommit', 'runId', 'runAttempt', 'sdkReceiptSha256', 'sdkAarSha256',
                'sdkClassJarSha256', 'sdkEditableClassSha256', 'sdkManifestSha256', 'normalMode', 'sdkObserverIncluded'):
        require(build.get(key) == embedded[key], 'APK build receipt identity differs: ' + key)
    require(digest(args.integration_apk) == build.get('integrationApkSha256')
            and digest(args.release_apk) == build.get('releaseApkSha256'), 'Compiled APK bytes differ from build receipt')
    compiled_audit = audit_apk(args.integration_apk)
    release_audit = audit_apk(args.release_apk, package='local.pocketchat', component=None, require_fixture=False)
    require(compiled_audit['embeddedBuildIdentity'] == embedded
            and compiled_audit['embeddedIdentityAssetSha256'] == build.get('embeddedIdentityAssetSha256'),
            'Compiled integration APK caret identity differs')
    # The production APK excludes the caret asset; both APKs carry the common SDK assets.
    import zipfile
    import sdk_identity_contract as sdk_contract
    tree = sdk['sourceTree']
    def selected_reader(selected_source, name):
        return subprocess.check_output(['git', 'show', selected_source + ':' + name],
                                       cwd=args.root, stderr=subprocess.PIPE)
    for apk in (args.integration_apk, args.release_apk):
        with zipfile.ZipFile(apk) as archive:
            common_sdk = sdk_contract.sdk_from_apk(archive, source, tree, selected_reader)
            require(common_sdk['sdkBuildReceiptSha256'] == digest(args.sdk_receipt)
                    and common_sdk['runId'] == build['runId'] and common_sdk['runAttempt'] == build['runAttempt'],
                    'Compiled APK common SDK bytes/run identity differs')
            if apk == args.integration_apk:
                stamp_raw = archive.read('assets/pocketchat-integration-build.json')
                common_expected = strict_json(stamp_raw)
                common_expected.update({key: common_sdk[key] for key in sdk_contract.SDK_FIELDS})
                common_expected.update(sdkBuildIdentity=common_sdk, package=PACKAGE,
                    apkSha256=build['integrationApkSha256'], apkBytes=apk.stat().st_size,
                    buildStampSha256=hashlib.sha256(stamp_raw).hexdigest())
                require(compiled_audit['observerScriptSha256'] == hashlib.sha256(
                    selected_reader(source, 'tests/gecko/assets/caret-document-observer.js')).hexdigest(),
                    'Compiled passive observation asset differs from selected source')
    build_identity = dict(schema=1, **{key: build[key] for key in (
        'sourceCommit', 'runId', 'runAttempt', 'integrationApkSha256', 'releaseApkSha256',
        'sdkReceiptSha256', 'sdkAarSha256', 'sdkClassJarSha256', 'sdkEditableClassSha256', 'sdkManifestSha256',
        'embeddedIdentityAssetSha256', 'normalMode', 'sdkObserverIncluded')})
    checks, scenarios, steps, api, clipboard, checkpoints = {}, {}, {}, {}, {}, {}
    chunks, trusted, seen = [], {}, set()
    report, installed_audit, installed_identity = None, None, None
    activity_launched = False
    nonce = secrets.token_hex(16)
    transfer = dispatcher = None
    collection = None
    servers = []

    def adb(*parts):
        return subprocess.check_output([args.adb, '-s', args.serial, *parts], text=True, timeout=30)

    def fetch_event(uri):
        return subprocess.check_output([args.adb, '-s', args.serial, 'exec-out', 'content', 'read', '--uri', uri], timeout=30)

    def unique(target, key, value, kind):
        require(key not in target, 'Duplicate ' + kind + ' index/id: ' + str(key))
        target[key] = value

    def save(value):
        # Preserve activity identity; never replace a conflicting source with local HEAD.
        require(value.get('sourceCommit') == source and value.get('runId') == build['runId']
                and value.get('runAttempt') == build['runAttempt'], 'Activity identity differs from installed build')
        ordered_events = {key: [e for part in parts for e in part['events']] for key, parts in trusted.items()}
        value.update(buildIdentity=build_identity, embeddedBuildIdentity=embedded,
                     installedBuild=installed_identity, buildReceiptSha256=digest(args.build_receipt),
                     sdkReceiptSha256=digest(args.sdk_receipt),
                     apkDefinitionAuditSha256=digest(out / 'installed-apk-definition-audit.json'),
                     checks=[checks[k] for k in sorted(checks)], scenarios=[scenarios[k] for k in IDS if k in scenarios],
                     checkpoints=[checkpoints[k] for k in sorted(checkpoints)],
                     actualAndroidActions=list({**(dispatcher.actions if dispatcher is not None else {}), **steps}.values()),
                     actualInputConnectionCalls=[api[k] for k in sorted(api)],
                     actualClipboardCalls=[clipboard[k] for k in sorted(clipboard)],
                     trustedEventChunks=chunks, actualTrustedEvents=ordered_events,
                     eventVectors={key: event_vectors(events) for key, events in ordered_events.items()},
                     fixtureRequests=Fixture.requests, controlledProxyRoutes=Socks.routes,
                     eventTransport=dict(schema=1, runNonce=nonce, fixtureAction='caretCompatibility', processSlot=0,
                         command=1, buildIdentity=transfer.identity if transfer is not None else common_expected,
                         records=transfer.records if transfer is not None else [],
                         receiptLedger=dispatcher.receipts if dispatcher is not None else [],
                         scope='Existing shell-only IntegrationEventStore/provider handoff; complete UTF8 bytes, SHA256, ordered sequence, invocation and installed APK/source/SDK fences.'),
                     evidenceCollection=collection,
                     device={'sdk': adb('shell', 'getprop', 'ro.build.version.sdk').strip(),
                             'screen': adb('shell', 'wm', 'size').strip(), 'density': adb('shell', 'wm', 'density').strip()},
                     capabilities={'controlledSdkChineseComposition': True, 'physicalPhoneAcceptance': False,
                                   'vendorKeyboardUiAcceptance': False, 'realAccountAcceptance': False})
        (out / 'gecko-caret-compat-results.json').write_text(json.dumps(value, indent=2) + '\n')

    try:
        # Pull the actual installed package before any fixture launch. No install/update is performed by this runner.
        paths = [line[len('package:'):] for line in adb('shell', 'pm', 'path', PACKAGE).splitlines() if line.startswith('package:')]
        require(len(paths) == 1 and paths[0].startswith('/data/app/'), 'Expected one installed integration APK; splits unsupported')
        with tempfile.TemporaryDirectory(prefix='caret-installed-', dir=out) as installed_directory:
            installed_apk = pathlib.Path(installed_directory) / 'base.apk'
            read_installed_apk(adb=args.adb, serial=args.serial, installed_path=paths[0], destination=installed_apk,
                expected_sha256=build['integrationApkSha256'], expected_bytes=args.integration_apk.stat().st_size,
                diagnostics=out / 'installed-apk-read-caret.json', label='caret-preflight')
            require(digest(installed_apk) == build['integrationApkSha256'], 'Actually installed APK differs from same-run compiled APK')
            installed_audit = audit_apk(installed_apk)
        require(installed_audit == compiled_audit, 'Installed APK definition/embedded asset audit differs')
        audit_path = out / 'installed-apk-definition-audit.json'
        audit_path.write_text(json.dumps(installed_audit, indent=2) + '\n')
        installed_identity = dict(apkSha256=installed_audit['apkSha256'], package=PACKAGE,
                                  component='local.pocketchat.GeckoCaretCompatibilityIntegrationActivity',
                                  observerDefinitions=installed_audit['observerDefinitions'],
                                  apkDefinitionAuditSha256=digest(audit_path),
                                  embeddedIdentityAssetSha256=installed_audit['embeddedIdentityAssetSha256'],
                                  sdkManifestSha256=installed_audit['sdkManifestSha256'])
        servers = [http.server.ThreadingHTTPServer(('127.0.0.1', 8771), Fixture), SocksServer(('127.0.0.1', 1088), Socks)]
        Fixture.requests, Socks.routes = [], []
        for server in servers:
            threading.Thread(target=server.serve_forever, daemon=True).start()
        for port in (8771, 1088):
            adb('reverse', 'tcp:' + str(port), 'tcp:' + str(port))
        adb('shell', 'am', 'force-stop', PACKAGE)
        require('Success' in adb('shell', 'pm', 'clear', PACKAGE), 'Could not clear isolated test package')
        common_installed = strict_json(fetch_event('content://' + PACKAGE + '.evidence/build-identity'))
        verify_installed(common_installed, common_expected)
        dispatcher = CaretDispatch(identity=common_installed, nonce=nonce, slot=0, action='caretCompatibility',
                                   fetch=fetch_event, command=1, dispatch=lambda value: perform_android_action(value, adb))
        transfer = dispatcher.transfer
        adb('shell', 'wm', 'size', '1080x2400')
        adb('shell', 'wm', 'density', '420')
        adb('shell', 'settings', 'put', 'system', 'font_scale', '1.0')
        adb('logcat', '-c')
        started = adb('shell', 'am', 'start', '-W', '-n', PACKAGE + '/local.pocketchat.GeckoCaretCompatibilityIntegrationActivity',
            '--ez', 'normalAcceptance', str(args.normal_acceptance).lower(), '--es', 'sourceCommit', source,
            '--es', 'runId', build['runId'], '--es', 'runAttempt', build['runAttempt'], '--es', 'eventNonce', nonce)
        require('Status: ok' in started, 'Actual integration Activity did not start: ' + started)
        activity_launched = True
        collection = dict(schema=1, scope='host-artifact-io', activeOperationBudgetMillis=300000,
                          readOnlyDrainBudgetMillis=600000,
                          receiptCaptureStartedAtMonotonicNanos=time.monotonic_ns())
        expires = time.monotonic() + 300
        while time.monotonic() < expires:
            raw = adb('logcat', '-d', '-s', 'PocketGeckoIntegration:I', 'PocketCaretCompat:E', 'AndroidRuntime:E', '*:S')
            require('FATAL EXCEPTION' not in raw, 'Android activity crashed: ' + raw)
            receipts = []
            for line in raw.splitlines():
                if 'PocketCaretCompat' in line:
                    raise ValueError('Native caret event transport unavailable: ' + line)
                receipt = parse_receipt_line(line)
                if receipt is None:
                    continue
                require(receipt.get('runNonce') == nonce and receipt.get('fixtureAction') == 'caretCompatibility'
                        and receipt.get('processSlot') == 0, 'Foreign native caret event receipt')
                require(receipt.get('kind') != 'eventTransportError', 'Native complete event publication failed: ' + str(receipt))
                receipts.append(receipt)
            # Validate the ENTIRE receipt snapshot before input. Passive immutable
            # evidence must not consume the Activity's unchanged input deadlines.
            dispatcher.ingest(receipts)
            if not dispatcher.terminal:
                time.sleep(.25)  # Receipt polling only; never pace/retry hardware input.
                continue
            # Read-only collection has its own finite budget. No input executes
            # while all original bytes undergo the unchanged ordered decoder.
            collection['receiptCaptureCompletedAtMonotonicNanos'] = time.monotonic_ns()
            collection['receiptCaptureDurationNanos'] = (collection['receiptCaptureCompletedAtMonotonicNanos']
                                                        - collection['receiptCaptureStartedAtMonotonicNanos'])
            collection['drainStartedAtMonotonicNanos'] = time.monotonic_ns()
            try:
                dispatcher.drain(timeout=600)
            finally:
                collection['drainCompletedAtMonotonicNanos'] = time.monotonic_ns()
                collection['drainDurationNanos'] = (collection['drainCompletedAtMonotonicNanos']
                                                   - collection['drainStartedAtMonotonicNanos'])
            for receipt in dispatcher.receipts:
                event = transfer.read(receipt)
                if receipt['sequence'] in seen:
                    continue
                seen.add(receipt['sequence'])
                kind, value = event['kind'], event['result']
                if kind == 'stepNeeded':
                    actual = dispatcher.actions.get(value['id'])
                    # A terminal already observed suppresses queued actions; keep
                    # their original request and honestly record zero executions.
                    unique(steps, value['id'], actual if actual is not None else dict(value, executions=[]), 'Android action')
                elif kind == 'check':
                    unique(checks, value['index'], value, 'check')
                elif kind == 'checkpoint':
                    unique(checkpoints, value['index'], value, 'checkpoint')
                elif kind == 'scenario':
                    unique(scenarios, value['id'], value, 'scenario')
                elif kind == 'api':
                    unique(api, value['index'], value, 'original SDK API')
                elif kind == 'clipboard':
                    unique(clipboard, value['index'], value, 'original Android clipboard API')
                elif kind == 'trustedEvents':
                    parts = trusted.setdefault(value['id'], [])
                    expected_offset = sum(len(part['events']) for part in parts)
                    require(value['offset'] == expected_offset and 0 < len(value['events']) <= 4,
                            'Trusted event chunk gap/duplicate/overflow')
                    parts.append(value); chunks.append(value)
                elif kind == 'report':
                    require(report is None, 'More than one terminal activity report')
                    report = value
            if report is not None:
                require(report.get('embeddedBuildIdentity') == embedded, 'Activity read a different actual build identity asset')
                require(report.get('mode') == ('normal' if args.normal_acceptance else 'diagnostic')
                        and report.get('diagnosticOnly') is (not args.normal_acceptance), 'Activity mode differs')
                save(report)
                require(report['status'] == 'passed', 'Compatibility activity failed: ' + str(report.get('error')))
                if args.normal_acceptance:
                    from check_caret_compat_evidence import verify_report
                    verify_report(report, build=build, sdk=sdk, audit=installed_audit,
                                  source=source, run_id=build["runId"], run_attempt=build["runAttempt"],
                                  build_hash=digest(args.build_receipt), sdk_hash=digest(args.sdk_receipt),
                                  audit_hash=digest(audit_path), artifact_root=args.root, sdk_raw=args.sdk_receipt.read_bytes())
                (out / 'gecko-caret-compat-screen.png').write_bytes(subprocess.check_output(
                    [args.adb, '-s', args.serial, 'exec-out', 'screencap', '-p'], timeout=30))
                print(json.dumps({'status': report['status'], 'scenarioCount': len(scenarios),
                                  'checkCount': len(checks), 'mode': report['mode'],
                                  'controlledCaretCompatibilityAcceptance': args.normal_acceptance,
                                  'physicalPhoneAcceptance': False, 'vendorKeyboardUiAcceptance': False}), flush=True)
                return
            time.sleep(.25)  # Poll the completed workload; never pace/retry input characters.
        raise TimeoutError('No completed real Gecko caret compatibility report')
    except Exception as error:
        if installed_audit is not None:
            if report is None:
                report = dict(schema=1, status='failed', mode='normal' if args.normal_acceptance else 'diagnostic',
                              diagnosticOnly=not args.normal_acceptance, releaseAcceptance=False,
                              actualAndroidExecution=activity_launched, sourceCommit=source, runId=build['runId'], runAttempt=build['runAttempt'])
            report.update(status='failed', controlledCaretCompatibilityAcceptance=False, runnerError=str(error))
            report['failureCaptures'] = capture_failure_diagnostics(args.adb, args.serial, out)
            save(report)
        else:
            (out / 'preflight-failure.json').write_text(json.dumps(dict(status='failed', actualAndroidExecution=False,
                error=str(error), sourceCommit=source, runId=build['runId'], runAttempt=build['runAttempt']), indent=2) + '\n')
        raise
    finally:
        for server in servers:
            server.shutdown(); server.server_close()


if __name__ == '__main__':
    main()
