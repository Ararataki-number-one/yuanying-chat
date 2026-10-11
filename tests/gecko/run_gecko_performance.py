#!/usr/bin/env python3
"""Compare production observation assets through real Gecko and the Android native bridge."""
import argparse, hashlib, http.server, json, pathlib, subprocess, threading, time, urllib.parse

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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--adb', required=True)
    parser.add_argument('--serial', default='emulator-5554')
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    baseline_root = ROOT / 'tests/gecko/assets/performance-baseline'
    receipt = json.loads((baseline_root / 'source.json').read_text())
    assert receipt['sourceCommit'] == BASELINE, receipt
    for name in ['page-driver.js', 'web-performance.js']:
        historical = subprocess.check_output(['git', 'show', BASELINE + ':app/src/main/assets/' + name], cwd=ROOT)
        packaged = (baseline_root / name).read_bytes()
        assert historical == packaged, 'Immutable historical baseline changed: ' + name
        assert len(packaged) == receipt['files'][name]['bytes'], name
        assert hashlib.sha256(packaged).hexdigest() == receipt['files'][name]['sha256'], name

    def adb(*parts):
        return subprocess.check_output([args.adb, '-s', args.serial, *parts], text=True, timeout=30)

    server = http.server.ThreadingHTTPServer(('127.0.0.1', 8767), Fixture)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        adb('reverse', 'tcp:8767', 'tcp:8767')
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
        adb('shell', 'am', 'start', '-W', '-n', package + '/local.pocketchat.GeckoPerformanceIntegrationActivity')
        checks, measurements, gestures = {}, {}, {}
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
                            adb('shell', 'input', 'tap', str(gesture['x']), str(gesture['y']))
                            adb('shell', 'input', 'keyevent', 'KEYCODE_MOVE_END')
                            adb('shell', 'input', 'text', '-user-typed')
                        else:
                            raise AssertionError(gesture)
                elif item['kind'] == 'report':
                    report = item['value']
            if report:
                report.update(sourceCommit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                              checks=list(checks.values()), measurements=list(measurements.values()), fixtureRequests=Fixture.requests,
                              baselineAssetVerification=receipt, actualAndroidGestures=list(gestures.values()), device=device)
                (OUT / 'gecko-performance-results.json').write_text(json.dumps(report, indent=2) + '\n')
                print(json.dumps(report, indent=2), flush=True)
                assert report['status'] == 'passed' and report['actualAndroidExecution'] and report['actualGeckoExecution'] and report['actualAndroidTouchExecution'], report
                assert report['baselineSource'] == BASELINE and report['checkCount'] == len(checks), report
                assert len(checks) >= 65 and all(check['pass'] for check in checks.values()), report
                assert set(measurements) == {'baseline', 'current'}, report
                assert all(case['samples'] == 12 for case in measurements.values()), report
                assert set(gestures) == {'baseline-scroll', 'current-scroll', 'current-input'}, report
                assert len([request for request in Fixture.requests if request['path'] == '/performance']) == 2, report
                image = subprocess.check_output([args.adb, '-s', args.serial, 'exec-out', 'screencap', '-p'], timeout=30)
                (OUT / 'gecko-performance-screen.png').write_bytes(image)
                return
            time.sleep(1)
        raise TimeoutError('No completed real Gecko performance report')
    except Exception:
        (OUT / 'gecko-performance-failure-log.txt').write_text(adb('logcat', '-d'))
        raise
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
