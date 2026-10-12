#!/usr/bin/env python3
"""Compare production observation assets through real Gecko and the Android native bridge."""
import argparse, hashlib, http.server, json, pathlib, select, socket, socketserver, struct, subprocess, threading, time, urllib.parse

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / 'work/gecko-integration'
BASELINE = '835d59991218eda70c7a4fdd73ea9d7ae6052688'


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
    observation.add_argument('--sdk-input-diagnostics', action='store_true',
                        help='Test-only same-class SDK primitive instrumentation; original single input burst unchanged. Never release acceptance.')
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
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
        adb('logcat', '-c')
        activity = ['shell', 'am', 'start', '-W', '-n', package + '/local.pocketchat.GeckoPerformanceIntegrationActivity']
        if args.input_diagnostics:
            activity.extend(['--ez', 'inputDiagnostics', 'true'])
        if args.native_input_diagnostics:
            activity.extend(['--ez', 'inputNativeDiagnostics', 'true'])
        if args.sdk_input_diagnostics:
            activity.extend(['--ez', 'inputSdkDiagnostics', 'true'])
        adb(*activity)
        checks, measurements, gestures, text_inputs, diagnostics = {}, {}, {}, {}, {}
        input_readiness, input_events, input_evaluations, native_input_events = {}, {}, {}, {}
        sdk_input_events, sdk_input_summary = {}, None
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
                elif item['kind'] == 'sdkInputTrace':
                    trace = item['value']
                    sdk_input_events[trace['offset']] = trace
                elif item['kind'] == 'sdkInputSummary':
                    sdk_input_summary = item['value']
                elif item['kind'] == 'report':
                    report = item['value']
                elif item['kind'] in ['load', 'route', 'loadError']:
                    diagnostics[line] = item
            if report:
                report.update(sourceCommit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                              diagnosticOnly=bool(args.input_diagnostics or args.native_input_diagnostics or args.sdk_input_diagnostics),
                              checks=list(checks.values()), measurements=list(measurements.values()), fixtureRequests=Fixture.requests,
                              controlledProxyRoutes=Socks.routes, browserDiagnostics=list(diagnostics.values()),
                              baselineAssetVerification=receipt, actualAndroidGestures=list(gestures.values()),
                              actualAndroidTextInputs=list(text_inputs.values()), device=device)
                report.update(actualInputReadinessTrace=[input_readiness[key] for key in sorted(input_readiness)],
                              actualTrustedInputEvents=[event for key in sorted(input_events) for event in input_events[key]['events']],
                              actualInputEvaluationTrace=[input_evaluations[key] for key in sorted(input_evaluations)],
                              actualNativeInputTrace=[native_input_events[key] for key in sorted(native_input_events)],
                              actualSdkInputTrace=[row for key in sorted(sdk_input_events) for row in sdk_input_events[key]['rows']],
                              actualSdkInputSummary=sdk_input_summary)
                (OUT / 'gecko-performance-results.json').write_text(json.dumps(report, indent=2) + '\n')
                print(json.dumps(report, indent=2), flush=True)
                assert report['inputDiagnosticsEnabled'] == args.input_diagnostics, report
                assert report['inputNativeDiagnosticsEnabled'] == args.native_input_diagnostics, report
                assert report['inputSdkDiagnosticsEnabled'] == args.sdk_input_diagnostics, report
                if args.sdk_input_diagnostics:
                    assert not native_input_events and not input_evaluations, 'Same-class SDK diagnostic unexpectedly attached proxy/JS observers'
                    rows = report['actualSdkInputTrace']; summary = report['actualSdkInputSummary']
                    assert summary and not summary.get('error') and summary['mode'] == 'same-class-primitives', summary
                    assert summary['overflow'] == 0 and summary['reserved'] == summary['published'] == summary['rowCount'] == len(rows), summary
                    assert rows and all(len(row) == 14 for row in rows), 'SDK primitive trace is absent or malformed'
                    assert [row[13] for row in rows] == list(range(len(rows))), 'SDK primitive trace sequence is incomplete'
                    assert any(row[0] == 14 for row in rows) and any(row[0] == 11 for row in rows), 'Missing actual replace/selection writers'
                else:
                    assert not sdk_input_events and sdk_input_summary is None, 'Normal SDK unexpectedly emitted same-class diagnostic data'
                if not args.input_diagnostics:
                    assert not input_evaluations, 'Normal/primitive-only regression unexpectedly traced JavaScript evaluation'
                    assert not any(event['type'] == 'selectionchange' or event['type'].startswith('script')
                                   for event in report['actualTrustedInputEvents']), 'Normal regression unexpectedly instrumented DOM selection'
                if not args.input_diagnostics and not args.native_input_diagnostics:
                    assert not native_input_events, 'Normal regression unexpectedly attached native diagnostic observers'
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
                image = subprocess.check_output([args.adb, '-s', args.serial, 'exec-out', 'screencap', '-p'], timeout=30)
                (OUT / 'gecko-performance-screen.png').write_bytes(image)
                return
            time.sleep(1)
        raise TimeoutError('No completed real Gecko performance report')
    except Exception as error:
        if report is not None:
            report['status'] = 'failed'
            report['runnerError'] = str(error)
            (OUT / 'gecko-performance-results.json').write_text(json.dumps(report, indent=2) + '\n')
        (OUT / 'gecko-performance-failure-log.txt').write_text(adb('logcat', '-d'))
        raise
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    main()
