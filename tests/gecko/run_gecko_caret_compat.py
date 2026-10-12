#!/usr/bin/env python3
"""Additional editing semantics over real Gecko/Android, always diagnostic evidence."""
import argparse
import html
import http.server
import json
import pathlib
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
<button id="send" onclick="window.sendCount++">Send</button><script>
window.sendCount=0;const composer=document.getElementById('prompt-textarea');const events=[];let overflow=false;
const caseNumber=''' + str(case) + ''';
for(const type of ['keydown','keyup','beforeinput','input','compositionstart','compositionupdate','compositionend']){
composer.addEventListener(type,e=>{if(events.length>=512){overflow=true;return}events.push({type,key:e.key||'',data:e.data||'',inputType:e.inputType||'',trusted:e.isTrusted,ctrl:!!e.ctrlKey,shift:!!e.shiftKey,composing:!!e.isComposing,start:composer.selectionStart,end:composer.selectionEnd});if(type==='beforeinput'&&caseNumber===10)e.preventDefault()});}
window.__caretSnapshot=()=>{const r=composer.getBoundingClientRect(),style=getComputedStyle(composer),canvas=document.createElement('canvas'),context=canvas.getContext('2d');context.font=style.font;const points=[];
for(let i=0;i<=composer.value.length;i++)points.push({x:r.left+parseFloat(style.borderLeftWidth)+parseFloat(style.paddingLeft)+context.measureText(composer.value.slice(0,i)).width-composer.scrollLeft,y:r.top+parseFloat(style.borderTopWidth)+parseFloat(style.paddingTop)+parseFloat(style.fontSize)*.6});
return {ready:true,case:caseNumber,draft:composer.value,otherDraft:document.getElementById('other-draft').value,focused:document.activeElement===composer,start:composer.selectionStart,end:composer.selectionEnd,direction:composer.selectionDirection,cookie:document.cookie,sendCount:window.sendCount,width:innerWidth,height:innerHeight,bounds:{x:r.x,y:r.y,width:r.width,height:r.height},points,events,overflow,eventCount:events.length,keyCount:events.filter(e=>e.type==='keydown').length,inputCount:events.filter(e=>e.type==='input').length,beforeCount:events.filter(e=>e.type==='beforeinput').length,compositionCount:events.filter(e=>e.type==='compositionstart').length,compositionEndCount:events.filter(e=>e.type==='compositionend').length,allTrusted:events.every(e=>e.trusted)}};
</script>''').encode('utf-8')


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
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    def adb(*parts):
        return subprocess.check_output([args.adb, '-s', args.serial, *parts], text=True, timeout=30)

    checks, scenarios, steps, api, trusted = {}, {}, {}, {}, {}
    seen = set()
    report = None
    servers = [http.server.ThreadingHTTPServer(('127.0.0.1', 8771), Fixture), SocksServer(('127.0.0.1', 1088), Socks)]
    for server in servers:
        threading.Thread(target=server.serve_forever, daemon=True).start()

    def save(value):
        value.update(sourceCommit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                     checks=[checks[k] for k in sorted(checks)], scenarios=[scenarios[k] for k in IDS if k in scenarios],
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
                    checks[value['index']] = value
                elif kind == 'scenario':
                    scenarios[value['id']] = value
                elif kind == 'api':
                    api[value['index']] = value
                elif kind == 'trustedEvents':
                    trusted.setdefault(value['id'], {})[value['offset']] = value['events']
                elif kind == 'report':
                    report = value
            if report is not None:
                save(report)
                assert report['diagnosticOnly'] and not report['releaseAcceptance'], report
                assert report['sdkObserverEnabled'] is False and report['domTextWrites'] == 0, report
                assert report['status'] == 'passed' and report['scenarioCount'] == len(IDS) == len(scenarios), report
                assert report['checkCount'] == len(checks) and all(x['pass'] for x in checks.values()), report
                assert Fixture.requests and {x['case'] for x in Fixture.requests} == set(range(len(IDS))), report
                assert Socks.routes and all(x['accepted'] for x in Socks.routes), report
                for case in scenarios.values():
                    actual = case['actual']
                    assert actual['allTrusted'] and not actual['overflow'] and actual['sendCount'] == 0, case
                    assert actual['otherDraft'] == 'untouched independent draft' and 'session=synthetic-caret' in actual['cookie'], case
                    assert len(trusted.get(case['id'], {})) or actual['eventCount'] == 0, case
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
