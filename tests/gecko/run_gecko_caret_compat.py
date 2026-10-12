#!/usr/bin/env python3
"""Additional editing semantics over real Gecko/Android, always diagnostic evidence."""
import argparse
import hashlib
import html
import http.server
import json
import pathlib
import os
import re
import select
import socket
import socketserver
import struct
import subprocess
import threading
import time
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / 'work/gecko-integration'
PACKAGE = 'local.pocketchat.test'
SEEDS = ['abcdefghij', 'abcdefghij', 'abcdef', 'undo draft', 'left-right', 'clipboard tail',
         'seed tail', 'seed tail', 'batch tail', 'abcdef', 'rejected draft', 'soft tail', 'A😀B', 'noop tail']
IDS = ['rapid-taps', 'selected-replace', 'arrow-delete', 'undo', 'ime-multiword', 'clipboard-paste',
       'chinese-composition', 'finish-composition', 'batch-commit', 'reversed-selection', 'rejected-input',
       'soft-single-char', 'codepoint-delete', 'noop-composition']


def document(case):
    # Seed only via immutable response HTML. No JS sets text, focus or selection.
    return ('''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Controlled original input semantics</title><style>
body{margin:0;padding:12px;background:white;font:18px monospace}textarea{box-sizing:border-box;width:100%;height:96px;padding:10px;border:1px solid #888;font:26px monospace;white-space:pre;resize:none}#other-draft{height:58px;margin-top:22px}button{margin-top:16px}h2{font:18px sans-serif}
</style><h2>''' + html.escape(IDS[case]) + '''</h2><textarea id="prompt-textarea" rows="2" spellcheck="false" autocorrect="off">''' +
            html.escape(SEEDS[case]) + '''</textarea><textarea id="other-draft" tabindex="-1">untouched independent draft</textarea>
<button id="send">Send</button>''').encode('utf-8')


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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--adb', required=True)
    parser.add_argument('--serial', default='emulator-5554')
    parser.add_argument('--installed-apk-sha256', required=True)
    parser.add_argument('--sdk-receipt', required=True, type=pathlib.Path)
    args = parser.parse_args()
    assert re.fullmatch('[0-9a-f]{64}', args.installed_apk_sha256), 'Expected installed APK SHA256 is required'
    sdk_raw = args.sdk_receipt.read_bytes()
    sdk_receipt = json.loads(sdk_raw)
    assert sdk_receipt['normalCandidateContainsObserver'] is False
    assert sdk_receipt['transform']['observerIncluded'] is False
    assert sdk_receipt['allNativeAndResourceEntriesUnchanged'] is True
    assert hashlib.sha256((ROOT / 'tools/build-gecko-hardware-caret.py').read_bytes()).hexdigest() == sdk_receipt['builderSha256']
    for name, digest in sdk_receipt['sourceSha256'].items():
        assert pathlib.Path(name).name == name and re.fullmatch('[0-9a-f]{64}', digest)
        source = ROOT / 'tools/gecko/hardware_caret' / name
        assert hashlib.sha256(source.read_bytes()).hexdigest() == digest, 'SDK receipt belongs to different candidate tools: ' + name
    sdk_identity = {key: sdk_receipt[key] for key in ['officialVersion', 'officialAarSha256', 'officialJarSha256',
                    'officialEditableSha256', 'candidateAarSha256', 'candidateJarSha256', 'candidateEditableSha256',
                    'helperSha256', 'builderSha256']}
    for key, value in sdk_identity.items():
        if key.endswith('Sha256'):
            assert re.fullmatch('[0-9a-f]{64}', value), key
    sdk_identity.update(receiptSha256=hashlib.sha256(sdk_raw).hexdigest(),
                        sourceSha256=sdk_receipt['sourceSha256'],
                        normalCandidateContainsObserver=False, allNativeAndResourceEntriesUnchanged=True)
    OUT.mkdir(parents=True, exist_ok=True)

    def adb(*parts):
        return subprocess.check_output([args.adb, '-s', args.serial, *parts], text=True, timeout=30)

    checks, scenarios, steps, api, trusted, checkpoints, geometry = {}, {}, {}, {}, {}, {}, {}
    seen = set()
    report = None
    servers = [http.server.ThreadingHTTPServer(('127.0.0.1', 8771), Fixture), SocksServer(('127.0.0.1', 1088), Socks)]
    for server in servers:
        threading.Thread(target=server.serve_forever, daemon=True).start()

    def save(value):
        value.update(sourceCommit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                     runId=os.environ.get('GITHUB_RUN_ID', ''), runAttempt=os.environ.get('GITHUB_RUN_ATTEMPT', ''),
                     expectedInstalledApkSha256=args.installed_apk_sha256, sdkBuildIdentity=sdk_identity,
                     checks=[checks[k] for k in sorted(checks)], scenarios=[scenarios[k] for k in IDS if k in scenarios],
                     actualCheckpoints=[checkpoints[k] for k in sorted(checkpoints)],
                     actualGeometrySamples=[geometry[k] for k in sorted(geometry)],
                     actualAndroidActions=list(steps.values()), actualInputConnectionCalls=list(api.values()),
                     actualTrustedEvents={key: [e for offset in sorted(parts) for e in parts[offset]] for key, parts in trusted.items()},
                     fixtureRequests=Fixture.requests, controlledProxyRoutes=Socks.routes,
                     device={'sdk': adb('shell', 'getprop', 'ro.build.version.sdk').strip(),
                             'screen': adb('shell', 'wm', 'size').strip(), 'density': adb('shell', 'wm', 'density').strip()})
        (OUT / 'gecko-caret-compat-results.json').write_text(json.dumps(value, indent=2) + '\n')

    try:
        for port in [8771, 1088]:
            adb('reverse', 'tcp:' + str(port), 'tcp:' + str(port))
        adb('shell', 'am', 'force-stop', PACKAGE)
        adb('shell', 'pm', 'clear', PACKAGE)
        adb('shell', 'wm', 'size', '1080x2400')
        adb('shell', 'wm', 'density', '420')
        adb('shell', 'settings', 'put', 'system', 'font_scale', '1.0')
        adb('logcat', '-c')
        adb('shell', 'am', 'start', '-W', '-n', PACKAGE + '/local.pocketchat.GeckoCaretCompatibilityIntegrationActivity')
        expires = time.monotonic() + 240
        while time.monotonic() < expires:
            raw = adb('logcat', '-d', '-s', 'PocketCaretCompat:I', 'AndroidRuntime:E', '*:S')
            if 'FATAL EXCEPTION' in raw:
                raise AssertionError(raw)
            for line in raw.splitlines():
                if 'PocketCaretCompat' not in line or '{' not in line or line in seen:
                    continue
                seen.add(line)
                item = json.loads(line[line.index('{'):])
                kind, value = item['kind'], item['value']
                if kind == 'stepNeeded':
                    if value['id'] in steps:
                        raise AssertionError('An Android action was requested twice')
                    steps[value['id']] = value
                    for command in value['commands']:
                        if command['op'] == 'tap':
                            adb('shell', 'input', 'tap', str(command['x']), str(command['y']))
                        elif command['op'] == 'text':
                            assert command['text'] in ['Q', 'Z', 'X'], command
                            adb('shell', 'input', 'keyboard', 'text', command['text'])
                        elif command['op'] == 'key':
                            assert command['code'] in [21, 67, 112], command
                            adb('shell', 'input', 'keyboard', 'keyevent', str(command['code']))
                        elif command['op'] == 'combination':
                            assert command['codes'] == [113, 54], command
                            adb('shell', 'input', 'keyboard', 'keycombination', *map(str, command['codes']))
                        else:
                            raise AssertionError(command)
                elif kind == 'check':
                    assert value['index'] not in checks, 'Duplicate check index'
                    checks[value['index']] = value
                elif kind == 'scenario':
                    scenarios[value['id']] = value
                elif kind == 'api':
                    assert value['index'] not in api, 'Duplicate InputConnection call index'
                    api[value['index']] = value
                elif kind == 'checkpoint':
                    assert value['index'] not in checkpoints, 'Duplicate checkpoint index'
                    checkpoints[value['index']] = value
                elif kind == 'geometry':
                    assert value['index'] not in geometry, 'Duplicate geometry evidence index'
                    geometry[value['index']] = value
                elif kind == 'trustedEvents':
                    assert value['offset'] not in trusted.get(value['id'], {}), 'Duplicate trusted event chunk'
                    trusted.setdefault(value['id'], {})[value['offset']] = value['events']
                elif kind == 'report':
                    report = value
            if report is not None:
                save(report)
                assert report['diagnosticOnly'] and not report['releaseAcceptance'], report
                assert report['sdkObserverEnabled'] is False and report['sdkObserverAbsenceVerified'] is True
                assert report['sdkObserverClass'] == 'org.mozilla.geckoview.PocketGeckoEditableTrace'
                installed = report['installedApk']
                assert installed['actualInstalledPackageRead'] is True and installed['packageName'] == PACKAGE
                assert installed['sha256'] == args.installed_apk_sha256 and installed['bytes'] > 0
                assert installed['source'] == 'applicationInfo.sourceDir' and installed['debuggable'] is False
                assert report['domTextWrites'] == 0, report
                assert report['status'] == 'passed' and report['scenarioCount'] == len(IDS) == len(scenarios), report
                assert report['checkCount'] == len(checks) and all(x['pass'] for x in checks.values()), report
                assert list(sorted(checks)) == list(range(report['checkCount']))
                assert report['apiCount'] == len(api) and list(sorted(api)) == list(range(report['apiCount']))
                assert all(x['accepted'] and x['origin'] == 'original-sdk-inputconnection' for x in api.values())
                assert report['checkpointCount'] == len(checkpoints)
                assert list(sorted(checkpoints)) == list(range(report['checkpointCount']))
                assert {x['scenario'] for x in checkpoints.values()} == set(IDS)
                assert report['geometryCount'] == len(geometry) and list(sorted(geometry)) == list(range(len(geometry)))
                for identifier in IDS:
                    for phase in ['before-unique-focus-tap', 'after-unique-focus-tap']:
                        ready = [x for x in geometry.values() if x['scenario'] == identifier and x['phase'] == phase and x['settled']]
                        assert len(ready) == 1 and ready[0]['consistent'] and ready[0]['stableMillis'] >= 600 and ready[0]['stableSamples'] >= 5
                for checkpoint in checkpoints.values():
                    expected, actual = checkpoint['expected'], checkpoint['actual']
                    assert actual['draft'] == expected['draft'] and actual['start'] == expected['start'] and actual['end'] == expected['end']
                    assert actual['keyCount'] >= expected['minimumKeys'] and actual['inputCount'] >= expected['minimumInputs'] and actual['beforeCount'] >= expected['minimumBefore']
                    assert actual['sendCount'] == 0 and actual['otherDraft'] == 'untouched independent draft'
                    assert 'session=synthetic-caret' in actual['cookie'] and actual['allTrusted'] and not actual['overflow']
                    assert checkpoint['stableMillis'] >= (600 if checkpoint['phase'] == 'focus' else 350)
                assert Fixture.requests and {x['case'] for x in Fixture.requests} == set(range(len(IDS))), report
                assert Socks.routes and all(x['accepted'] for x in Socks.routes), report
                for case in scenarios.values():
                    actual = case['actual']
                    assert actual['allTrusted'] and not actual['overflow'] and actual['sendCount'] == 0, case
                    assert actual['otherDraft'] == 'untouched independent draft' and 'session=synthetic-caret' in actual['cookie'], case
                    parts, offset, events = trusted.get(case['id'], {}), 0, []
                    for position in sorted(parts):
                        assert position == offset and 1 <= len(parts[position]) <= 4, case
                        events.extend(parts[position])
                        offset += len(parts[position])
                    assert offset == actual['eventCount'] and all(e['trusted'] for e in events), case
                    for key, kind in [('keyCount', 'keydown'), ('inputCount', 'input'), ('beforeCount', 'beforeinput'),
                                      ('compositionCount', 'compositionstart'), ('compositionEndCount', 'compositionend')]:
                        assert actual[key] == sum(e['type'] == kind for e in events), case
                for action in steps.values():
                    for command in action['commands']:
                        if command['op'] != 'tap':
                            continue
                        source = command['coordinateSource']
                        assert source['mapping'] == 'uniform-visual-viewport' and source['stableMillis'] >= 600 and source['stableSamples'] >= 5
                        viewport, point = source['viewport'], source['cssPoint']
                        scale = source['nativeWidth'] / viewport['width']
                        assert abs(source['uniformScale'] - scale) < 1e-9
                        assert command['x'] == source['nativeX'] + int((point['x'] - viewport['offsetLeft']) * scale + .5)
                        assert command['y'] == source['nativeY'] + int((point['y'] - viewport['offsetTop']) * scale + .5)
                (OUT / 'gecko-caret-compat-screen.png').write_bytes(subprocess.check_output([args.adb, '-s', args.serial, 'exec-out', 'screencap', '-p'], timeout=30))
                print(json.dumps({'status': report['status'], 'scenarioCount': len(scenarios), 'checkCount': len(checks), 'diagnosticOnly': True}), flush=True)
                return
            time.sleep(.25)
        raise TimeoutError('No completed real Gecko caret compatibility report')
    except Exception as error:
        if report is None:
            report = {'status': 'failed', 'diagnosticOnly': True, 'releaseAcceptance': False, 'actualAndroidExecution': True}
        report['status'] = 'failed'
        report['runnerError'] = str(error)
        save(report)
        (OUT / 'gecko-caret-compat-failure-log.txt').write_text(adb('logcat', '-d'))
        raise
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    main()
