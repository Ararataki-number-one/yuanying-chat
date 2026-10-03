#!/usr/bin/env python3
"""Actual Android Gecko integration test. Only synthetic loopback traffic."""
import argparse, base64, hashlib, http.server, json, pathlib, select, socket
import socketserver, struct, subprocess, threading, time, urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent
OUTPUT = ROOT.parents[1] / 'work/gecko-sdk-validation'
TRACE = []
CONNECTIONS = set()
CONNECTION_LOCK = threading.Lock()


class Fixture(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *args):
        pass

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        TRACE.append({'kind': 'http', 'path': path})
        if path == '/socket':
            key = self.headers['Sec-WebSocket-Key']
            accept = base64.b64encode(hashlib.sha1((key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
            self.send_response(101)
            self.send_header('Upgrade', 'websocket'); self.send_header('Connection', 'Upgrade')
            self.send_header('Sec-WebSocket-Accept', accept); self.end_headers()
            header = self.rfile.read(2)
            if len(header) != 2:
                return
            size = header[1] & 127
            mask = self.rfile.read(4)
            data = self.rfile.read(size)
            data = bytes(value ^ mask[i % 4] for i, value in enumerate(data))
            self.wfile.write(bytes([0x81, len(data)]) + data); self.wfile.flush()
            self.close_connection = True
            return
        status, content_type, body = 200, 'text/plain', b'synthetic-ok'
        if path == '/fixture':
            content_type, body = 'text/html; charset=utf-8', (ROOT / 'fixture.html').read_bytes()
        elif path == '/worker.js':
            content_type = 'text/javascript'
            body = b"self.addEventListener('install',e=>self.skipWaiting());self.addEventListener('activate',e=>e.waitUntil(clients.claim()));self.addEventListener('message',e=>e.waitUntil((async()=>{await fetch('/service-worker-ping');const c=await caches.open('engine-probe'),r=await c.match('/stored-token');e.ports[0].postMessage(r?await r.text():null);})()));"
        elif path == '/dedicated-worker.js':
            content_type, body = 'text/javascript', b"fetch('/dedicated-worker-ping').then(r=>r.text()).then(v=>postMessage(v));"
        elif path == '/redirect':
            status, body = 302, b''
        elif path == '/download':
            body = b'synthetic-download' * 64
        self.send_response(status)
        if status == 302:
            self.send_header('Location', '/redirect-final')
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers(); self.wfile.write(body)


def exact(sock, size):
    result = b''
    while len(result) < size:
        part = sock.recv(size - len(result))
        if not part:
            raise ConnectionError('closed')
        result += part
    return result


class Socks(socketserver.BaseRequestHandler):
    def handle(self):
        with CONNECTION_LOCK:
            CONNECTIONS.add(self.request)
        try:
            client = self.request
            version, count = exact(client, 2)
            assert version == 5
            exact(client, count); client.sendall(b'\x05\x00')
            version, command, _, address_type = exact(client, 4)
            if address_type == 1:
                host = socket.inet_ntoa(exact(client, 4))
            elif address_type == 3:
                host = exact(client, exact(client, 1)[0]).decode()
            elif address_type == 4:
                host = socket.inet_ntop(socket.AF_INET6, exact(client, 16))
            else:
                return
            port = struct.unpack('!H', exact(client, 2))[0]
            accepted = command == 1 and port == 8765 and host in ['127.0.0.1', 'remote-probe.invalid']
            TRACE.append({'kind': 'socks', 'host': host, 'port': port, 'addressType': address_type, 'accepted': accepted})
            if not accepted:
                client.sendall(b'\x05\x02\x00\x01' + b'\x00' * 6); return
            with socket.create_connection(('127.0.0.1', 8765), timeout=10) as upstream:
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
        except (OSError, AssertionError):
            return
        finally:
            with CONNECTION_LOCK:
                CONNECTIONS.discard(self.request)


class ThreadedSocks(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--adb', required=True); parser.add_argument('--serial', default='emulator-5556')
    args = parser.parse_args(); OUTPUT.mkdir(parents=True, exist_ok=True)
    def adb(*arguments, timeout=30):
        return subprocess.check_output([args.adb, '-s', args.serial, *arguments], timeout=timeout, text=True)
    http_server = http.server.ThreadingHTTPServer(('127.0.0.1', 8765), Fixture)
    socks = ThreadedSocks(('127.0.0.1', 1080), Socks)
    for server in [http_server, socks]:
        threading.Thread(target=server.serve_forever, daemon=True).start()
    adb('reverse', 'tcp:8765', 'tcp:8765'); adb('reverse', 'tcp:1080', 'tcp:1080')
    adb('shell', 'pm', 'clear', 'local.pocketchat.engineprobe')
    steps, logs = [], []
    def run(context, action):
        adb('logcat', '-c')
        adb('shell', 'am', 'start', '-n', 'local.pocketchat.engineprobe/.ProbeActivity',
            '--ei', 'context', str(context - 1), '--es', 'fixtureAction', action)
        deadline = time.monotonic() + 150
        while time.monotonic() < deadline:
            output = adb('logcat', '-d', '-s', 'PocketEngineProbe:I', '*:S')
            for line in output.splitlines():
                if '{' not in line:
                    continue
                try:
                    event = json.loads(line[line.index('{'):])
                except json.JSONDecodeError:
                    continue
                if event.get('kind') == 'fixture' and event['result'].get('action') == action:
                    logs.append(output); steps.append(event); print(json.dumps(event), flush=True)
                    if 'error' in event['result']:
                        raise AssertionError(event['result']['error'])
                    return event['result']
            time.sleep(2)
        (OUTPUT / 'last-device-log.txt').write_text(adb('logcat', '-d'))
        raise TimeoutError(f'no native fixture result: context={context}, action={action}')
    def check(result, context, populated):
        expected = f'synthetic-environment-{context}' if populated else None
        for name in ['localStorage', 'indexedDB', 'cache', 'workerToken']:
            assert result[name] == expected, (name, result)
        assert result['cookie'] == (f'probe={expected}' if populated else ''), result
        assert result['serviceWorkers'] == int(populated), result
    report = {'actualAndroidExecution': True, 'googleLogin': 'not-tested', 'perEnvironmentProxy': 'not-integrated'}
    try:
        check(run(1, 'seed'), 1, True)
        check(run(2, 'read'), 2, False)
        check(run(2, 'seed'), 2, True)
        check(run(1, 'read'), 1, True)
        check(run(1, 'clear'), 1, False)
        check(run(2, 'read'), 2, True)
        adb('shell', 'am', 'force-stop', 'local.pocketchat.engineprobe')
        check(run(2, 'read'), 2, True)
        check(run(1, 'read'), 1, False)
        result = run(2, 'network')
        assert result['webSocket'] == 'synthetic-probe' and result['remoteDns'] == 'synthetic-ok'
        assert result['dedicatedWorker'] == 'synthetic-ok' and result['downloadBytes'] == 1152
        assert any(x['kind'] == 'socks' and x['host'] == 'remote-probe.invalid' and x['addressType'] == 3 for x in TRACE)
        socks.shutdown(); socks.server_close()
        with CONNECTION_LOCK:
            for connection in list(CONNECTIONS):
                try:
                    connection.shutdown(socket.SHUT_RDWR)
                    connection.close()
                except OSError:
                    pass
        before = sum(x['kind'] == 'http' for x in TRACE)
        adb('logcat', '-c')
        adb('shell', 'am', 'start', '-n', 'local.pocketchat.engineprobe/.ProbeActivity',
            '--ei', 'context', '1', '--es', 'fixtureAction', 'network')
        time.sleep(15)
        assert sum(x['kind'] == 'http' for x in TRACE) == before, 'proxy outage caused direct requests'
        outage_log = adb('logcat', '-d', '-s', 'PocketEngineProbe:I', '*:S')
        assert '"kind":"loadError"' in outage_log, 'proxy outage did not produce an actual navigation failure'
        logs.append(outage_log)
        report.update(status='passed', storageIsolation='passed', persistentStorage='passed',
            globalSocksRoute='passed', proxyRemoteDns='passed', workersAndWebSocket='passed',
            proxyOutageNoDirect='passed')
    except Exception as error:
        report.update(status='failed', error=f'{type(error).__name__}: {error}')
        raise
    finally:
        report['steps'] = steps
        (OUTPUT / 'device-results.json').write_text(json.dumps(report, indent=2) + '\n')
        (OUTPUT / 'device-route-trace.json').write_text(json.dumps(TRACE, indent=2) + '\n')
        (OUTPUT / 'device-native-events.txt').write_text('\n'.join(logs))
        http_server.shutdown()


if __name__ == '__main__':
    main()
