#!/usr/bin/env python3
"""Actual official/patched Mihomo probe timing and cancellation, local routes only."""
import hashlib, http.client, http.server, importlib.util, json, socket, ssl, struct
from pathlib import Path
import subprocess, threading, time, urllib.parse, urllib.request, urllib.error

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
BASE = REPO / 'work/chain-performance'
spec = importlib.util.spec_from_file_location('chain_fixture', BASE / 'benchmark.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
EVENTS = []
LOCK = threading.Lock()
COUNTS = {}

def event(kind, **data):
    with LOCK:
        EVENTS.append(dict(kind=kind, at=time.monotonic(), **data))

class TrackedSocks(fixture.Socks):
    def handle(self):
        try:
            return super().handle()
        finally:
            event('socksClosed', role=self.server.role, peer=self.client_address)

class Endpoint(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def do_HEAD(self):
        with LOCK:
            COUNTS[self.path] = COUNTS.get(self.path, 0) + 1
            attempt = COUNTS[self.path]
        path = self.path.split('?')[0]
        event('head', uri=self.path, attempt=attempt, peer=self.client_address,
              tls=isinstance(self.connection, ssl.SSLSocket))
        if path == '/cancel-first' or path in ['/cancel-second', '/timeout'] and attempt >= 2:
            self.connection.settimeout(12)
            try:
                data = self.rfile.readline()
                event('targetEof', uri=self.path, eof=data == b'')
            except OSError:
                event('targetEof', uri=self.path, eof=False)
            self.close_connection = True
            return
        if path == '/rst' and attempt >= 2:
            time.sleep(.250)
            event('reset', uri=self.path, attempt=attempt)
            self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER,
                                       struct.pack('ii', 1, 0))
            self.close_connection = True
            return
        time.sleep(.100)
        self.send_response(403 if path == '/wrong-status' else 204)
        self.send_header('Content-Length', '0')
        if path == '/close':
            self.send_header('Connection', 'close')
            self.close_connection = True
        self.end_headers()
        event('response', uri=self.path, attempt=attempt)

    def log_message(self, *args):
        pass

def get(controller, path):
    request = urllib.request.Request(f'http://127.0.0.1:{controller}{path}')
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as response:
        return response.code, json.load(response)

def wait_event(uri, kind, minimum=0, timeout=12):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with LOCK:
            found = [e for e in EVENTS if e.get('uri') == uri and e['kind'] == kind
                     and e.get('attempt', minimum) >= minimum]
        if found:
            return found[-1]
        time.sleep(.005)
    raise AssertionError(f'Missing controlled {kind} for {uri}')

def cancel(controller, api_path, uri, second):
    s = socket.create_connection(('127.0.0.1', controller), 3)
    s.sendall((f'GET {api_path} HTTP/1.1\r\nHost: 127.0.0.1:{controller}\r\n\r\n').encode('ascii'))
    wait_event(uri, 'head', minimum=2 if second else 1)
    cancelled = time.monotonic()
    s.shutdown(socket.SHUT_RDWR)
    s.close()
    ended = wait_event(uri, 'targetEof')
    assert ended['eof'], 'The target did not observe actual socket EOF.'
    return round((ended['at'] - cancelled) * 1000, 3)

def run(binary, variant, round_id, entry, exit_port, hp, sp, bad_sp, ca):
    folder = ROOT / 'trace-compare' / f'{variant}-{round_id}'
    folder.mkdir(parents=True, exist_ok=True)
    proxy, controller = fixture.configuration('app', folder, entry, exit_port, ca)
    output = (folder / 'core.log').open('w')
    process = subprocess.Popen([str(binary), '-d', str(folder), '-f', str(folder / 'config.json')],
                               stdout=output, stderr=output)
    rows = []
    try:
        for _ in range(100):
            if process.poll() is not None:
                raise RuntimeError((folder / 'core.log').read_text())
            try:
                version = fixture.api(controller, '/version')
                group = fixture.api(controller, '/proxies/EntryChoice')
                if 'Entry|node-0' not in group.get('all', []):
                    time.sleep(.025)
                    continue
                break
            except OSError:
                time.sleep(.025)
        else:
            raise RuntimeError('Core controller unavailable')
        fixture.api(controller, '/proxies/EntryChoice', 'PUT', {'name': 'Entry|node-0'})
        for scheme, port in [('http', hp), ('https', sp)]:
            for path in ['/ok', '/close', '/rst', '/timeout', '/wrong-status']:
                uri = path + f'?variant={variant}&round={round_id}&scheme={scheme}'
                target = f'{scheme}://127.0.0.1:{port}{uri}'
                limit = 1500 if path == '/timeout' else 8000
                route = '/proxies/FixedExit/delay?timeout=' + str(limit) + '&expected=204&url=' + urllib.parse.quote(target, safe='')
                began = time.monotonic()
                code, value = get(controller, route)
                elapsed = (time.monotonic() - began) * 1000
                state = fixture.api(controller, '/proxies/FixedExit')['extra'][target]
                wire = [dict(e, relativeMs=round((e['at'] - began) * 1000, 3))
                        for e in EVENTS if e.get('uri') == uri]
                heads = [e for e in wire if e['kind'] == 'head']
                if path == '/timeout':
                    assert code == 504 and 'delay' not in value
                else:
                    assert code == 200 and value['delay'] > 0
                    assert state['alive'] == (path != '/wrong-status')
                if variant == 'patched':
                    p = value['probe']
                    assert p['schema'] == 1 and p['totalMs'] >= 0
                    assert p['warmError'] in ['', 'transport', 'cancelled', 'timeout']
                    assert p['warmAttempted'] and p['firstStatus'] in [204, 403]
                    assert p['attempts'] == len(heads)
                    if path == '/ok':
                        assert p['kind'] == 'warm' and p['warmSucceeded'] and p['secondConnectionReused']
                        assert p['dialCount'] == 1 and p['attempts'] == 2
                        assert heads[0]['peer'] == heads[1]['peer']
                        assert value['delay'] == p['warmMs']
                    elif path == '/close':
                        assert p['kind'] == 'cold-retest' and p['warmSucceeded'] and not p['secondConnectionReused']
                        assert p['dialCount'] == 2 and p['attempts'] == 2
                        assert heads[0]['peer'] != heads[1]['peer']
                        assert value['delay'] == p['warmMs']
                    elif path == '/rst':
                        assert p['kind'] == 'cold-fallback' and not p['warmSucceeded']
                        assert p['warmError'] == 'transport' and value['delay'] == p['firstMs']
                        assert p['attempts'] <= 3 and p['dialCount'] <= 2
                        assert p['warmMs'] >= 240 and p['totalMs'] >= p['firstMs'] + 240
                    elif path == '/timeout':
                        assert p['kind'] == 'cold-fallback' and not p['warmSucceeded'] and p['warmError'] == 'timeout'
                    else:
                        assert not p['warmSucceeded'] and p['error'] == 'unexpected-status'
                elif path == '/rst':
                    assert len(heads) >= 2 and value['delay'] > wire[1]['relativeMs'] + 230
                rows.append(dict(scheme=scheme, path=path, code=code, result=value,
                                 elapsedMs=round(elapsed, 3), alive=state['alive'], wire=wire))
        for path in ['/cancel-first', '/cancel-second']:
            uri = path + f'?variant={variant}&round={round_id}'
            target = f'http://127.0.0.1:{hp}{uri}'
            route = '/proxies/FixedExit/delay?timeout=8000&expected=204&url=' + urllib.parse.quote(target, safe='')
            stopped = cancel(controller, route, uri, path == '/cancel-second')
            if variant == 'patched':
                assert stopped < 1500, 'Controller cancellation did not promptly close the native HEAD.'
            else:
                assert stopped > 5000, 'Unexpected official controller cancellation behavior.'
            assert process.poll() is None
            rows.append(dict(path=path, nativeTargetClosedAfterControlCancelMs=stopped, sameCorePid=process.pid))
        target = f'https://127.0.0.1:{bad_sp}/untrusted?variant={variant}&round={round_id}'
        code, value = get(controller, '/proxies/FixedExit/delay?timeout=8000&expected=204&url=' + urllib.parse.quote(target, safe=''))
        state = fixture.api(controller, '/proxies/FixedExit')['extra'][target]
        assert code == 503 and not state['alive'] and 'delay' not in value
        if variant == 'patched':
            p = value['probe']
            assert p['kind'] == 'first' and p['firstMs'] == -1 and not p['warmAttempted']
            assert p['dialCount'] == 1 and p['attempts'] == 0 and p['error'] == 'transport'
        rows.append(dict(path='/untrusted', code=code, result=value, alive=state['alive']))
        return dict(variant=variant, round=round_id, corePid=process.pid, version=version,
                    binarySha256=hashlib.sha256(binary.read_bytes()).hexdigest(), rows=rows)
    finally:
        process.terminate()
        process.wait(timeout=8)
        output.close()

def main():
    (ROOT / 'trace-compare').mkdir(exist_ok=True)
    cert, key = BASE / 'fixture.crt', BASE / 'fixture.key'
    bad_cert, bad_key = ROOT / 'untrusted.crt', ROOT / 'untrusted.key'
    if not bad_cert.exists():
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '2',
                        '-subj', '/CN=127.0.0.1', '-addext', 'subjectAltName=IP:127.0.0.1',
                        '-keyout', str(bad_key), '-out', str(bad_cert)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    http_server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Endpoint)
    https_server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Endpoint)
    bad_server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Endpoint)
    for server, leaf, private in [(https_server, cert, key), (bad_server, bad_cert, bad_key)]:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(leaf, private)
        server.socket = ctx.wrap_socket(server.socket, server_side=True)
    hp, sp, bad = fixture.serve(http_server), fixture.serve(https_server), fixture.serve(bad_server)
    exit_server = fixture.TCP(('127.0.0.1', 0), TrackedSocks)
    exit_server.role = 'fixedExit'
    exit_server.allowed = {hp, sp, bad}
    ep = fixture.serve(exit_server)
    entry_server = fixture.TCP(('127.0.0.1', 0), TrackedSocks)
    entry_server.role = 'entry'
    entry_server.allowed = {ep}
    np = fixture.serve(entry_server)
    binaries = {'official': BASE / 'mihomo', 'patched': REPO / 'work/mihomo-build/bin/mihomo-linux-amd64'}
    rows = []
    try:
        for round_id, variants in enumerate([['official', 'patched'], ['patched', 'official']]):
            for variant in variants:
                value = run(binaries[variant], variant, round_id, np, ep, hp, sp, bad, cert.read_text())
                rows.append(value)
                print(json.dumps({'variant': variant, 'round': round_id,
                                  'rows': [{k:v for k,v in x.items() if k != 'wire'} for x in value['rows']]}), flush=True)
        assert all(e['permitted'] for e in fixture.EVENTS if e['kind'] == 'socksConnect')
        result = dict(status='passed', actualMihomoExecution=True, actualTwoSocksHops=True,
                      comparison='AB/BA official binary vs source-distributed probe-only patch',
                      upstreamTarSha256=hashlib.sha256((REPO / 'third-party/source/mihomo-v1.19.31.tar.gz').read_bytes()).hexdigest(),
                      patchSha256=hashlib.sha256((REPO / 'third-party/patches/mihomo-v1.19.31-probe.patch').read_bytes()).hexdigest(),
                      scope='Synthetic loopback fixture; not Android runtime or user provider throughput.',
                      runs=rows, chainEvents=fixture.EVENTS, closureEvents=[e for e in EVENTS if e['kind'] == 'socksClosed'])
        (ROOT / 'trace-compare-report.json').write_text(json.dumps(result, indent=2))
        print('All real native probe, redial, failure timing, request cancellation and TLS refusal checks passed.', flush=True)
    finally:
        for server in [entry_server, exit_server, http_server, https_server, bad_server]:
            server.shutdown()
            server.server_close()

if __name__ == '__main__':
    main()
