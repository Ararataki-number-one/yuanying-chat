#!/usr/bin/env python3
"""Compare production observation assets through real Gecko and the Android native bridge."""
import argparse, hashlib, http.server, json, pathlib, re, select, socket, socketserver, struct, subprocess, threading, time, urllib.parse, uuid

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / 'work/gecko-integration'
BASELINE = '835d59991218eda70c7a4fdd73ea9d7ae6052688'
SDK_IME_BASE_SOURCE = '1f970ea51f90466fb69fc282692ecb535c38ce64'
SDK_IME_TRANSFORM = 'tools/gecko/build_ime_writer_diagnostic.py'


def sdk_ime_receipt(path, source, tree):
    """Bind the explicitly modified, test-only SDK to its frozen build receipt."""
    raw = pathlib.Path(path).read_bytes()
    if len(raw) > 131072:
        raise ValueError('SDK IME transform receipt exceeds the bounded receipt size')
    value = json.loads(raw)
    if not isinstance(value, dict) or type(value.get('schema')) is not int:
        raise ValueError('SDK IME transform receipt must be a versioned JSON object')
    official = json.loads((ROOT / 'third-party/sdk/geckoview-157.0.1-official.json').read_text())
    expected = dict(schema=1, sourceCommit=source, sourceTree=tree, baseSourceCommit=SDK_IME_BASE_SOURCE,
                    sdkCoordinate=official['coordinate'], officialAarSha256=official['aar']['sha256'],
                    officialPomSha256=official['pom']['sha256'],
                    officialSourcesSha256=official['sources']['sha256'], sourceTransformPath=SDK_IME_TRANSFORM)
    for key, wanted in expected.items():
        if value.get(key) != wanted:
            raise ValueError('SDK IME transform receipt mismatch: ' + key)
    for key, wanted in dict(diagnosticOnly=True, releaseAcceptance=False,
                            sdkInputWriterDiagnosticsEnabled=True, nativeArchivesIdentical=True,
                            javaApiIdentical=True, debugFalsePreserved=True, inputBehaviorChanged=False).items():
        if value.get(key) is not wanted:
            raise ValueError('SDK IME transform receipt must explicitly declare: ' + key)
    for key in ['diagnosticAarSha256', 'diagnosticClassesJarSha256', 'sourceTransformSha256',
                'compileClasspathReceiptSha256']:
        if not isinstance(value.get(key), str) or not re.fullmatch(r'[0-9a-f]{64}', value[key]):
            raise ValueError('SDK IME transform receipt has invalid digest: ' + key)
    if value['diagnosticAarSha256'] == official['aar']['sha256'] or value['diagnosticClassesJarSha256'] == official['classesJarSha256']:
        raise ValueError('SDK IME diagnostics require an explicitly modified diagnostic SDK')
    if value['sourceTransformSha256'] != hashlib.sha256((ROOT / SDK_IME_TRANSFORM).read_bytes()).hexdigest():
        raise ValueError('SDK IME transform script differs from its receipt')
    return value, raw, hashlib.sha256(raw).hexdigest()


def sdk_ime_identity(value, receipt, receipt_sha, source, tree):
    """Check the device's installed APK stamp before launching the diagnostic activity."""
    if not isinstance(value, dict) or type(value.get('schema')) is not int:
        raise ValueError('Installed SDK IME diagnostic identity must be a versioned JSON object')
    expected = dict(schema=1, sourceCommit=source, sourceTree=tree,
                    sdkCoordinate=receipt['sdkCoordinate'], package='local.pocketchat.test',
                    diagnosticSdkAarSha256=receipt['diagnosticAarSha256'],
                    sdkInputWriterTransformReceiptSha256=receipt_sha)
    for key, wanted in expected.items():
        if value.get(key) != wanted:
            raise ValueError('Installed SDK IME diagnostic identity mismatch: ' + key)
    for key, wanted in dict(dirtySource=False, sdkInputWriterDiagnosticsEnabled=True,
                            diagnosticOnly=True, releaseAcceptance=False).items():
        if value.get(key) is not wanted:
            raise ValueError('Installed SDK IME diagnostic identity must explicitly declare: ' + key)
    if type(value.get('apkBytes')) is not int or value['apkBytes'] <= 0:
        raise ValueError('Installed SDK IME diagnostic APK bytes were not measured')
    for key in ['apkSha256', 'buildStampSha256']:
        if not isinstance(value.get(key), str) or not re.fullmatch(r'[0-9a-f]{64}', value[key]):
            raise ValueError('Installed SDK IME diagnostic identity has invalid digest: ' + key)
    return value


def document():
    history = ''.join(
        '<article data-message-author-role="user" data-message-id="old-user-{0}">Historical question {0}</article>'
        '<section data-turn="assistant"><div data-message-author-role="assistant" data-message-id="old-answer-{0}">'
        '<div class="markdown"><p>{1}</p></div></div>'
        '<button data-testid="copy-turn-action-button" aria-label="Copy response">Copy</button></section>'.format(
            index, ('Historical reply paragraph %d. ' % index) * 12)
        for index in range(120)
    )
    return (
        '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Controlled long-conversation performance fixture</title>'
        '<style>body{font:18px sans-serif;margin:0;padding:12px}p{overflow-wrap:anywhere}pre{overflow:auto}'
        '#composer{position:fixed;bottom:0;left:0;right:0;background:white;padding:10px}'
        'textarea{width:90%;font:inherit}</style><main>' + history +
        '<article data-message-author-role="user" data-message-id="current-question">'
        '<div data-user-message-bubble>bound performance prompt</div></article>'
        '<section data-turn="assistant"><div id="current-answer" data-message-author-role="assistant" '
        'data-message-id="current-answer"><div class="markdown"><p id="long-body">' +
        'preserved reply line ' * 5000 +
        '</p><pre><code class="language-js">const keep = 1;</code></pre>'
        '<a id="generated-file" download="result.csv" href="/backend-api/files/controlled">result.csv</a>'
        '</div></div><button id="current-copy" data-testid="copy-turn-action-button" aria-label="Copy response">Copy</button></section>'
        '</main><div id="composer"><textarea id="prompt-textarea">unsent draft stays unchanged</textarea>'
        '<button id="stop-button" data-testid="stop-button" aria-label="Stop">Stop</button>'
        '<button id="send-button" data-testid="send-button" aria-label="Send" '
        'onclick="document.getElementById(\'send-count\').textContent=String(Number(document.getElementById(\'send-count\').textContent)+1)">Send</button>'
        '</div><output id="send-count" hidden>0</output><div id="fixture-ready" hidden>ready</div>'
    ).encode('utf-8')


class Fixture(http.server.BaseHTTPRequestHandler):
    requests = []

    def log_message(self, *args):
        pass

    def do_GET(self):
        address = urllib.parse.urlparse(self.path)
        self.requests.append({'method': 'GET', 'path': address.path})
        if address.path != '/performance':
            self.send_response(404)
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        body = document()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Set-Cookie', 'session=synthetic-performance; Path=/; SameSite=Strict')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def exact(sock, size):
    data = b''
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise ConnectionError('Controlled SOCKS connection closed')
        data += chunk
    return data


class Socks(socketserver.BaseRequestHandler):
    """Same production proxy path as the existing Gecko suite, bounded to this fixture."""
    routes = []

    def handle(self):
        client = self.request
        client.settimeout(20)
        try:
            version, count = exact(client, 2)
            assert version == 5 and 0 in exact(client, count)
            client.sendall(b'\x05\x00')
            version, command, _, address_type = exact(client, 4)
            assert version == 5
            if address_type == 1:
                host = socket.inet_ntoa(exact(client, 4))
            elif address_type == 3:
                host = exact(client, exact(client, 1)[0]).decode('ascii')
            elif address_type == 4:
                host = socket.inet_ntop(socket.AF_INET6, exact(client, 16))
            else:
                return
            port = struct.unpack('!H', exact(client, 2))[0]
            accepted = command == 1 and host == '127.0.0.1' and port == 8767
            self.routes.append({'host': host, 'port': port, 'addressType': address_type, 'accepted': accepted})
            if not accepted:
                client.sendall(b'\x05\x02\x00\x01' + b'\x00' * 6)
                return
            with socket.create_connection(('127.0.0.1', 8767), timeout=10) as upstream:
                client.sendall(b'\x05\x00\x00\x01' + b'\x00' * 6)
                while True:
                    ready, _, _ = select.select([client, upstream], [], [], 20)
                    if not ready:
                        return
                    for source in ready:
                        chunk = source.recv(65536)
                        if not chunk:
                            return
                        (upstream if source is client else client).sendall(chunk)
        except (OSError, AssertionError, UnicodeError):
            return


class SocksServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--adb', required=True)
    parser.add_argument('--serial', default='emulator-5554')
    observation = parser.add_mutually_exclusive_group()
    observation.add_argument('--input-diagnostics', action='store_true',
                        help='Enable extra SDK/IME and JS selection observations; disabled for the normal release regression.')
    observation.add_argument('--native-input-diagnostics', action='store_true',
                        help='Buffer only primitive SDK/IME observations and flush after input; no extra JS observers. Diagnostic evidence cannot replace the normal regression.')
    observation.add_argument('--sdk-ime-log', action='store_true',
                        help='Use a separately receipted, log-only SDK transform. Diagnostic-only; no native/JS observer flags or release acceptance.')
    parser.add_argument('--sdk-ime-receipt', type=pathlib.Path,
                        help='Exact external transform receipt required with --sdk-ime-log')
    args = parser.parse_args()
    if bool(args.sdk_ime_receipt) != args.sdk_ime_log:
        parser.error('--sdk-ime-log and --sdk-ime-receipt must be supplied together')
    OUT.mkdir(parents=True, exist_ok=True)
    started_ms = int(time.time() * 1000)
    diagnostic_run = uuid.uuid4().hex
    for name in ['gecko-performance-results.json', 'gecko-performance-failure-log.txt',
                 'gecko-performance-failure-screen.png', 'gecko-performance-failure-ui.xml',
                 'gecko-performance-failure-window.txt', 'gecko-performance-failure-activity.txt',
                 'gecko-scroll-diagnostics.json', 'gecko-scroll-diagnostic-log.json',
                 'gecko-performance-screen.png', 'gecko-sdk-ime-log.txt',
                 'gecko-sdk-ime-transform-receipt.json', 'gecko-sdk-ime-build-identity.json']:
        (OUT / name).unlink(missing_ok=True)
    sdk_receipt = sdk_receipt_sha = installed_sdk_identity = None
    if args.sdk_ime_log:
        source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        tree = subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], cwd=ROOT, text=True).strip()
        if subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=normal'], cwd=ROOT, text=True).strip():
            raise ValueError('SDK IME diagnostic execution requires a clean committed source tree')
        sdk_receipt, sdk_receipt_raw, sdk_receipt_sha = sdk_ime_receipt(args.sdk_ime_receipt, source, tree)
        (OUT / 'gecko-sdk-ime-transform-receipt.json').write_bytes(sdk_receipt_raw)
    baseline_root = ROOT / 'tests/gecko/assets/performance-baseline'
    receipt = json.loads((baseline_root / 'source.json').read_text())
    assert receipt['sourceCommit'] == BASELINE, receipt
    if subprocess.run(['git', 'cat-file', '-e', BASELINE + '^{commit}'], cwd=ROOT,
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
        subprocess.run(['git', 'fetch', '--depth=1', 'origin', BASELINE], cwd=ROOT, check=True)
    for name in ['page-driver.js', 'web-performance.js']:
        historical = subprocess.check_output(['git', 'show', BASELINE + ':app/src/main/assets/' + name], cwd=ROOT)
        packaged = (baseline_root / name).read_bytes()
        assert historical == packaged, 'Immutable historical baseline changed: ' + name
        assert len(packaged) == receipt['files'][name]['bytes'], name
        assert hashlib.sha256(packaged).hexdigest() == receipt['files'][name]['sha256'], name

    def adb(*parts):
        return subprocess.check_output([args.adb, '-s', args.serial, *parts], text=True, timeout=30)

    package = 'local.pocketchat.test'
    scroll_samples, scroll_touches, scroll_dom_events, scroll_errors = {}, {}, {}, {}
    sdk_input_clocks = {}

    def sdk_diagnostic_report(value):
        if args.sdk_ime_log:
            value.update(diagnosticOnly=True, releaseAcceptance=False,
                         sdkInputWriterDiagnosticsRequested=True,
                         sdkInputWriterTransformReceiptSha256=sdk_receipt_sha,
                         sdkInputWriterTransformReceipt=sdk_receipt,
                         sdkInputWriterInstalledBuildIdentity=installed_sdk_identity,
                         actualSdkInputClockTrace=list(sdk_input_clocks.values()),
                         sdkInputWriterDiagnosticScope='Log-only Java SDK instrumentation can affect timing. '
                         'Original assertions, passive DOM listeners, real tap and single Android input text burst remain unchanged. '
                         'This transformed SDK is diagnostic-only and cannot establish release acceptance.')
            value.setdefault('sdkInputWriterDiagnosticsEnabled', False)

    def capture_sdk_input_log():
        raw = adb('logcat', '-d', '-v', 'epoch', '-b', 'all')
        encoded = raw.encode('utf-8')
        (OUT / 'gecko-sdk-ime-log.txt').write_bytes(encoded)
        return dict(saved=True, bytes=len(encoded), sha256=hashlib.sha256(encoded).hexdigest(),
                    sdkLogLines=sum('PocketSDKIME' in line for line in raw.splitlines()),
                    format='epoch', buffers='all', filtered=False)

    def save_scroll_diagnostics():
        scope = ('Read-only scroll-phase diagnostics add passive DOM listeners, bounded native touch/delegate '
                 'capture, geometry and existing before/after snapshots; no new evaluations or changes to '
                 'gestures, pacing, timeouts, assertions or typing. First four busy samples are unchanged; '
                 'APZ touch dispatch, scroll-phase scheduling and frame timing may be affected by the added work '
                 'and passive touch listeners.')
        source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        observed = dict(schema=1, sourceCommit=source, run=diagnostic_run, startedUnixMs=started_ms, instrumentationScope=scope,
                        samples=list(scroll_samples.values()), nativeTouches=list(scroll_touches.values()),
                        trustedDomEvents=list(scroll_dom_events.values()), diagnosticErrors=list(scroll_errors.values()))
        (OUT / 'gecko-scroll-diagnostic-log.json').write_text(json.dumps(observed, indent=2) + '\n')
        try:
            actual = json.loads(adb('exec-out', 'content', 'read', '--uri', 'content://' + package + '.evidence/gecko-scroll'))
            if actual.get('run') != diagnostic_run:
                raise ValueError('Android scroll diagnostics do not belong to this invocation')
            actual.update(sourceCommit=source, startedUnixMs=started_ms, instrumentationScope=scope,
                          actualAndroidFileRead=True)
            (OUT / 'gecko-scroll-diagnostics.json').write_text(json.dumps(actual, indent=2) + '\n')
            return dict(schema=1, actualAndroidFileRead=True, phases=len(actual['phases']), instrumentationScope=scope)
        except Exception as error:
            return dict(schema=1, actualAndroidFileRead=False, fileReadError=str(error), instrumentationScope=scope)

    servers = [http.server.ThreadingHTTPServer(('127.0.0.1', 8767), Fixture), SocksServer(('127.0.0.1', 1087), Socks)]
    for server in servers:
        threading.Thread(target=server.serve_forever, daemon=True).start()
    report = None
    try:
        for port in [8767, 1087]:
            adb('reverse', 'tcp:' + str(port), 'tcp:' + str(port))
        package = 'local.pocketchat.test'
        adb('shell', 'am', 'force-stop', package)
        adb('shell', 'pm', 'clear', package)
        # Keep both historical and current observation cases on the same screen setup.
        # These commands target the selected isolated CI device, as the other Android runners do.
        adb('shell', 'wm', 'size', '1080x2400')
        adb('shell', 'wm', 'density', '420')
        adb('shell', 'settings', 'put', 'system', 'font_scale', '1.0')
        device = {'androidSdk': int(adb('shell', 'getprop', 'ro.build.version.sdk').strip()),
                  'androidRelease': adb('shell', 'getprop', 'ro.build.version.release').strip(),
                  'screen': adb('shell', 'wm', 'size').strip(), 'density': adb('shell', 'wm', 'density').strip(),
                  'frameTimingInterpretation': 'Descriptive actual Gecko RAF and Android Choreographer gaps during the controlled polling and gesture workload; no claim of real-account FPS.'}
        if args.sdk_ime_log:
            source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
            tree = subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], cwd=ROOT, text=True).strip()
            installed_sdk_identity = sdk_ime_identity(json.loads(adb('exec-out', 'content', 'read', '--uri',
                'content://' + package + '.evidence/build-identity')), sdk_receipt, sdk_receipt_sha, source, tree)
            (OUT / 'gecko-sdk-ime-build-identity.json').write_text(json.dumps(installed_sdk_identity, indent=2) + '\n')
        adb('logcat', '-c')
        activity = ['shell', 'am', 'start', '-W', '-n', package + '/local.pocketchat.GeckoPerformanceIntegrationActivity']
        activity.extend(['--es', 'scrollDiagnosticRun', diagnostic_run])
        if args.input_diagnostics:
            activity.extend(['--ez', 'inputDiagnostics', 'true'])
        if args.native_input_diagnostics:
            activity.extend(['--ez', 'inputNativeDiagnostics', 'true'])
        if args.sdk_ime_log:
            activity.extend(['--ez', 'sdkInputWriterDiagnostics', 'true',
                             '--es', 'sdkInputWriterTransformReceiptSha256', sdk_receipt_sha])
        adb(*activity)
        checks, measurements, gestures, text_inputs, diagnostics = {}, {}, {}, {}, {}
        input_readiness, input_events, input_evaluations, native_input_events = {}, {}, {}, {}
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            raw = adb('logcat', '-d', '-s', 'PocketGeckoPerformance:I', 'AndroidRuntime:E', '*:S')
            if 'FATAL EXCEPTION' in raw:
                raise AssertionError(raw)
            report = None
            for line in raw.splitlines():
                if 'PocketGeckoPerformance' not in line or '{' not in line:
                    continue
                item = json.loads(line[line.index('{'):])
                if item['kind'] == 'check':
                    checks[item['value']['name']] = item['value']
                elif item['kind'] == 'measurement':
                    measurements[item['value']['variant']] = item['value']
                elif item['kind'] == 'gestureNeeded':
                    gesture = item['value']
                    if gesture['id'] not in gestures:
                        gestures[gesture['id']] = gesture
                        if gesture['action'] == 'scroll':
                            adb('shell', 'input', 'swipe', str(gesture['x']), str(gesture['startY']), str(gesture['x']), str(gesture['endY']), '300')
                        elif gesture['action'] == 'input':
                            assert gesture['text'] == '-user-typed', gesture
                            adb('shell', 'input', 'tap', str(gesture['x']), str(gesture['y']))
                            # The DOM and Android InputConnection settle separately.
                            # Wait for the activity's actual focus handshake before text.
                        else:
                            raise AssertionError(gesture)
                elif item['kind'] == 'textNeeded':
                    request = item['value']
                    assert request['id'] == 'current-input' and request['id'] in gestures, request
                    assert gestures[request['id']]['action'] == 'input' and request['text'] == gestures[request['id']]['text'], request
                    assert request['composerFocused'] and request['nativeFocused'] and request['acceptingText'] and request['stableFocusSamples'] >= 2, request
                    assert request['imeVisible'] and request['imeBottom'] > 0 and request['settledMs'] >= 600, request
                    assert request['start'] == request['end'] and 0 <= request['start'] <= len(request['draft']), request
                    if request['id'] not in text_inputs:
                        text_inputs[request['id']] = request
                        # Keep the caret from the real tap. The activity removes
                        # exactly one marker and checks every original character.
                        adb('shell', 'input', 'text', request['text'])
                elif item['kind'] == 'inputReadiness':
                    trace = item['value']
                    input_readiness[trace['sequence']] = trace
                elif item['kind'] == 'inputEvents':
                    trace = item['value']
                    input_events[trace['offset']] = trace
                elif item['kind'] == 'inputEvaluation':
                    trace = item['value']
                    input_evaluations[(trace['sequence'], trace['phase'])] = trace
                elif item['kind'] == 'nativeInputTrace':
                    trace = item['value']
                    native_input_events[trace['seq']] = trace
                elif item['kind'] == 'sdkInputClock' and args.sdk_ime_log:
                    trace = item['value']
                    # The same logcat buffer is reread; retain the single actual
                    # passive clock anchor without replaying or synthesizing it.
                    sdk_input_clocks[json.dumps(trace, sort_keys=True)] = trace
                elif item['kind'] == 'report':
                    report = item['value']
                elif item['kind'] in ['load', 'route', 'loadError']:
                    diagnostics[line] = item
                elif item['kind'] == 'scrollSample':
                    value = item['value'];scroll_samples[(value['phase'], value['sequence'])] = value
                elif item['kind'] == 'scrollNativeTouch':
                    value = item['value'];scroll_touches[(value['phase'], value['event']['sequence'])] = value
                elif item['kind'] == 'scrollDomEvent':
                    value = item['value'];scroll_dom_events[(value['phase'], value['event']['sequence'])] = value
                elif item['kind'] == 'scrollDiagnosticError':
                    scroll_errors[line] = item['value']
            if report:
                report['scrollDiagnostics'] = save_scroll_diagnostics()
                report.update(sourceCommit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                              diagnosticOnly=bool(args.input_diagnostics or args.native_input_diagnostics),
                              checks=list(checks.values()), measurements=list(measurements.values()), fixtureRequests=Fixture.requests,
                              controlledProxyRoutes=Socks.routes, browserDiagnostics=list(diagnostics.values()),
                              baselineAssetVerification=receipt, actualAndroidGestures=list(gestures.values()),
                              actualAndroidTextInputs=list(text_inputs.values()), device=device)
                report.update(actualInputReadinessTrace=[input_readiness[key] for key in sorted(input_readiness)],
                              actualTrustedInputEvents=[event for key in sorted(input_events) for event in input_events[key]['events']],
                              actualInputEvaluationTrace=[input_evaluations[key] for key in sorted(input_evaluations)],
                              actualNativeInputTrace=[native_input_events[key] for key in sorted(native_input_events)])
                sdk_diagnostic_report(report)
                if args.sdk_ime_log:
                    report['sdkInputWriterLogCapture'] = capture_sdk_input_log()
                (OUT / 'gecko-performance-results.json').write_text(json.dumps(report, indent=2) + '\n')
                print(json.dumps(report, indent=2), flush=True)
                assert report['inputDiagnosticsEnabled'] == args.input_diagnostics, report
                assert report['inputNativeDiagnosticsEnabled'] == args.native_input_diagnostics, report
                if not args.input_diagnostics:
                    assert not input_evaluations, 'Normal/primitive-only regression unexpectedly traced JavaScript evaluation'
                    assert not any(event['type'] == 'selectionchange' or event['type'].startswith('script')
                                   for event in report['actualTrustedInputEvents']), 'Normal regression unexpectedly instrumented DOM selection'
                if not args.input_diagnostics and not args.native_input_diagnostics:
                    assert not native_input_events, 'Normal regression unexpectedly attached native diagnostic observers'
                if args.sdk_ime_log:
                    assert report.get('sdkInputWriterDiagnosticsEnabled') is True, 'Activity did not confirm SDK IME diagnostic mode'
                    assert len(sdk_input_clocks) == 1, 'Diagnostic SDK clock anchor must be observed exactly once'
                    assert report['sdkInputWriterLogCapture']['sdkLogLines'] > 0, 'Diagnostic SDK did not emit its SDK IME witness log'
                if args.native_input_diagnostics:
                    assert native_input_events and all(event['mode'] == 'buffered-primitives' for event in native_input_events.values()), report
                    summaries = [event for event in native_input_events.values() if event['api'] == 'trace.bufferedSummary']
                    assert len(summaries) == 1 and not summaries[0]['overflow'] and not summaries[0]['restoreError'], summaries
                    assert summaries[0]['published'] == summaries[0]['reserved'] == len(native_input_events) - 1, 'Buffered native event log is incomplete'
                    assert summaries[0]['focusedChildAttached'] and not summaries[0]['focusedChildError'], summaries
                assert report['status'] == 'passed' and report['actualAndroidExecution'] and report['actualGeckoExecution'] and report['actualAndroidTouchExecution'] and report['actualGeckoBindingRegressionExecution'], report
                assert report['baselineSource'] == BASELINE and report['checkCount'] == len(checks), report
                assert len(checks) >= 125 and all(check['pass'] for check in checks.values()), report
                assert set(measurements) == {'baseline', 'current'}, report
                assert all(case['samples'] == 12 for case in measurements.values()), report
                assert set(gestures) == {'baseline-scroll', 'current-scroll', 'current-input'}, report
                assert set(text_inputs) == {'current-input'}, report
                assert len([request for request in Fixture.requests if request['path'] == '/performance']) == 2, report
                assert Socks.routes and all(route['accepted'] for route in Socks.routes), report
                decisions = [item['value'] for item in diagnostics.values() if item['kind'] == 'route' and item['value']['url'].startswith('http://127.0.0.1:8767/performance')]
                assert len(decisions) >= 2 and all(item['guardAllowed'] and item['decision']['type'] == 'socks' and item['decision']['host'] == '127.0.0.1' and item['decision']['port'] == 1087 for item in decisions), report
                if not report['scrollDiagnostics']['actualAndroidFileRead'] or report['scrollDiagnostics'].get('phases') != 2:
                    raise RuntimeError('Actual same-invocation scroll diagnostic phases were not captured')
                image = subprocess.check_output([args.adb, '-s', args.serial, 'exec-out', 'screencap', '-p'], timeout=30)
                (OUT / 'gecko-performance-screen.png').write_bytes(image)
                return
            time.sleep(1)
        raise TimeoutError('No completed real Gecko performance report')
    except Exception as error:
        if report is None:
            report = dict(status='failed', sourceCommit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                          observedActivityReport=False, actualAndroidExecution=False, actualGeckoExecution=False,
                          checkCount=len(checks) if 'checks' in locals() else 0)
        report['scrollDiagnostics'] = save_scroll_diagnostics()
        captures = {}
        ui_remote = '/sdcard/gecko-performance-failure-' + diagnostic_run + '.xml'
        operations = [
            ('gecko-performance-failure-screen.png', lambda: subprocess.check_output([args.adb, '-s', args.serial, 'exec-out', 'screencap', '-p'], timeout=30)),
            ('gecko-performance-failure-ui.xml', lambda: (adb('shell', 'uiautomator', 'dump', ui_remote), adb('shell', 'cat', ui_remote))[1]),
            ('gecko-performance-failure-window.txt', lambda: adb('shell', 'dumpsys', 'window')),
            ('gecko-performance-failure-activity.txt', lambda: adb('shell', 'dumpsys', 'activity', 'activities')),
            ('gecko-performance-failure-log.txt', lambda: adb('logcat', '-d')),
        ]
        for name, capture in operations:
            try:
                data = capture()
                if isinstance(data, bytes):
                    (OUT / name).write_bytes(data)
                else:
                    (OUT / name).write_text(data)
                captures[name] = dict(saved=True, bytes=(OUT / name).stat().st_size)
            except Exception as capture_error:
                captures[name] = dict(saved=False, error=str(capture_error))
        report['failureCaptures'] = captures
        sdk_diagnostic_report(report)
        if args.sdk_ime_log:
            try:
                report['sdkInputWriterLogCapture'] = capture_sdk_input_log()
            except Exception as capture_error:
                report['sdkInputWriterLogCapture'] = dict(saved=False, error=str(capture_error))
        if report is not None:
            report['status'] = 'failed'
            report['runnerError'] = str(error)
            (OUT / 'gecko-performance-results.json').write_text(json.dumps(report, indent=2) + '\n')
        raise
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    main()
