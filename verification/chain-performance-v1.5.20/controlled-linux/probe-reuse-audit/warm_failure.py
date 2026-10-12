#!/usr/bin/env python3
"""Exercise the official Mihomo binary through two actual loopback SOCKS hops.

All endpoints, authentication and certificates are synthetic; this is a timing
mechanism audit, not a benchmark of the user's provider or Android device.
"""
import hashlib, http.server, importlib.util, json, socket, ssl, struct
from pathlib import Path
import subprocess, threading, time, urllib.parse

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
BASE = REPO / 'work/chain-performance'
spec = importlib.util.spec_from_file_location('local_chain_fixture', BASE / 'benchmark.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
EVENTS = []
LOCK = threading.Lock()

def event(kind, **data):
    with LOCK:
        EVENTS.append(dict(kind=kind, at=time.monotonic(), **data))

class WarmFailure(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def do_HEAD(self):
        attempt = getattr(self, 'attempt', 0) + 1
        self.attempt = attempt
        event('received', path=self.path, attempt=attempt, peer=self.client_address,
              tls=isinstance(self.connection, ssl.SSLSocket))
        if self.path == '/second-reset' and attempt == 2:
            time.sleep(.250)
            event('reset', path=self.path, attempt=attempt)
            self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER,
                                       struct.pack('ii', 1, 0))
            self.close_connection = True
            return
        time.sleep(.100)
        self.send_response(204)
        self.send_header('Content-Length', '0')
        self.send_header('Connection', 'keep-alive')
        self.end_headers()
        event('response', path=self.path, attempt=attempt)

    def log_message(self, *args):
        pass

def main():
    ROOT.mkdir(exist_ok=True)
    cert, key = BASE / 'fixture.crt', BASE / 'fixture.key'
    assert cert.is_file() and key.is_file(), 'Generate the existing local fixture certificate first.'
    ordinary = http.server.ThreadingHTTPServer(('127.0.0.1', 0), WarmFailure)
    secure = http.server.ThreadingHTTPServer(('127.0.0.1', 0), WarmFailure)
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.load_cert_chain(cert, key)
    secure.socket = tls.wrap_socket(secure.socket, server_side=True)
    hp, sp = fixture.serve(ordinary), fixture.serve(secure)
    exit_server = fixture.TCP(('127.0.0.1', 0), fixture.Socks)
    exit_server.role = 'fixedExit'
    exit_server.allowed = {hp, sp}
    ep = fixture.serve(exit_server)
    entry_server = fixture.TCP(('127.0.0.1', 0), fixture.Socks)
    entry_server.role = 'entry'
    entry_server.allowed = {ep}
    np = fixture.serve(entry_server)
    directory = ROOT / 'official-core'
    directory.mkdir(exist_ok=True)
    proxy, controller = fixture.configuration('app', directory, np, ep, cert.read_text())
    log = (directory / 'core.log').open('w')
    binary = BASE / 'mihomo'
    process = subprocess.Popen([str(binary), '-d', str(directory), '-f', str(directory / 'config.json')],
                               stdout=log, stderr=log)
    rows = []
    try:
        for _ in range(100):
            if process.poll() is not None:
                raise RuntimeError((directory / 'core.log').read_text())
            try:
                version = fixture.api(controller, '/version')
                break
            except OSError:
                time.sleep(.025)
        else:
            raise RuntimeError('Core not ready')
        fixture.api(controller, '/proxies/EntryChoice', 'PUT', {'name': 'Entry|node-0'})
        for scheme, port in [('http', hp), ('https', sp)]:
            for trial in range(3):
                for path in ['/ok', '/second-reset']:
                    before = len(EVENTS)
                    started = time.monotonic()
                    target = f'{scheme}://127.0.0.1:{port}{path}'
                    result = fixture.api(controller, '/proxies/FixedExit/delay?timeout=8000&expected=204&url=' + urllib.parse.quote(target, safe=''))
                    ended = time.monotonic()
                    history = fixture.api(controller, '/proxies/FixedExit')['extra'][target]
                    seen = [dict(item, relativeMs=round((item['at'] - started) * 1000, 2))
                            for item in EVENTS[before:]]
                    response_events = [e for e in seen if e['kind'] == 'response']
                    request_events = [e for e in seen if e['kind'] == 'received']
                    resets = [e for e in seen if e['kind'] == 'reset']
                    elapsed = (ended - started) * 1000
                    assert len(request_events) == 2 and request_events[0]['peer'] == request_events[1]['peer']
                    assert history['alive'] and history['history'][-1]['delay'] == result['delay']
                    if path == '/ok':
                        assert len(response_events) == 2 and not resets
                        assert result['delay'] < elapsed - 200
                    else:
                        assert len(response_events) == 1 and len(resets) == 1
                        assert elapsed - result['delay'] < 20
                        assert result['delay'] > response_events[0]['relativeMs'] + 200
                    rows.append(dict(scheme=scheme, trial=trial, path=path, delayMs=result['delay'],
                                     completeApiMs=round(elapsed, 2), alive=history['alive'],
                                     responses=len(response_events), events=seen))
        report = dict(status='passed', mechanism='official unified-delay includes a failed second attempt in the successful first-response fallback',
                      actualMihomoExecution=True, actualTwoSocksHops=True, version=version,
                      binarySha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                      scope='Synthetic loopback fixture; no Android, public provider, user credentials or production changes.',
                      rows=rows, chainEvents=fixture.EVENTS)
        (ROOT / 'warm-failure-report.json').write_text(json.dumps(report, indent=2))
        print(json.dumps({'status': report['status'], 'binarySha256': report['binarySha256'],
                          'rows': [{k:v for k,v in row.items() if k != 'events'} for row in rows]}, indent=2))
    finally:
        process.terminate()
        process.wait(timeout=8)
        log.close()
        for server in [entry_server, exit_server, ordinary, secure]:
            server.shutdown()
            server.server_close()

if __name__ == '__main__':
    main()
