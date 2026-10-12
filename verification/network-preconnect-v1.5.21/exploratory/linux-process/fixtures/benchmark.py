#!/usr/bin/env python3
"""Real loopback SOCKS/TLS wire experiment, not a production-core speed claim.

Cold: entry setup, authenticated entry CONNECT, exit method/auth, target
CONNECT, TLS, HEAD. Candidate: an unused bounded exit socket is prepared only
through method/auth; the measured request still performs target CONNECT/TLS/HEAD.
Each prepared socket is consumed exactly once. No user credentials or WAN traffic.
"""
import argparse
import hashlib
import json
import pathlib
import select
import socket
import ssl
import statistics
import struct
import subprocess
import threading
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = pathlib.Path(__file__).resolve().parent


def mono():
    return time.perf_counter_ns()


class Wire:
    def __init__(self):
        self.began = mono()
        self.lock = threading.Lock()
        self.rows = []
        self.sequence = 0

    def new(self, label, sock):
        with self.lock:
            self.sequence += 1
            ident = label + '-' + str(self.sequence)
        self.event(ident, 'accepted', peerPort=sock.getpeername()[1], localPort=sock.getsockname()[1])
        return ident

    def event(self, ident, phase, data=None, **extra):
        row = {'socket': ident, 'phase': phase, 'atNs': mono() - self.began, **extra}
        if data is not None:
            row.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        with self.lock:
            self.rows.append(row)

    def count(self, phase, prefix=None):
        with self.lock:
            return sum(r['phase'] == phase and (prefix is None or r['socket'].startswith(prefix)) for r in self.rows)

    def socket_for_peer(self, prefix, peer_port):
        with self.lock:
            rows=[r for r in self.rows if r['socket'].startswith(prefix) and r['phase']=='accepted' and r['peerPort']==peer_port]
            return rows[-1]['socket'] if rows else None

    def phase(self, ident, phase):
        with self.lock:
            rows=[r for r in self.rows if r['socket']==ident and r['phase']==phase]
            return rows[-1] if rows else None


def exact(sock, count):
    data = b''
    while len(data) < count:
        part = sock.recv(count-len(data))
        if not part:
            raise EOFError('peer closed')
        data += part
    return data


def relay(left, right):
    while True:
        readable, _, _ = select.select((left, right), (), (), 2)
        for source in readable:
            data = source.recv(65536)
            if not data:
                return
            (right if source is left else left).sendall(data)


class Listener:
    def __init__(self, name, wire):
        self.name, self.wire = name, wire
        self.sock = socket.socket()
        self.sock.bind(('127.0.0.1', 0))
        self.sock.listen()
        self.port = self.sock.getsockname()[1]
        self.closed = False
        threading.Thread(target=self.accept, daemon=True).start()

    def accept(self):
        while not self.closed:
            try:
                sock, _ = self.sock.accept()
            except OSError:
                return
            sock.settimeout(5)
            threading.Thread(target=self.handle, args=(sock,), daemon=True).start()

    def close(self):
        self.closed = True
        self.sock.close()


class Target(Listener):
    def __init__(self, wire, context):
        self.context = context
        super().__init__('target', wire)

    def handle(self, sock):
        ident = self.wire.new(self.name, sock)
        try:
            with self.context.wrap_socket(sock, server_side=True) as tls:
                self.wire.event(ident, 'target-tls-ready', alpn=tls.selected_alpn_protocol())
                request = b''
                while b'\r\n\r\n' not in request:
                    request += exact(tls, 1)
                    assert len(request) < 4096
                assert request.startswith(b'HEAD /probe HTTP/1.1\r\n')
                self.wire.event(ident, 'target-head-received', request)
                response = b'HTTP/1.1 204 No Content\r\nContent-Length: 0\r\nConnection: close\r\n\r\n'
                tls.sendall(response)
                self.wire.event(ident, 'target-head-sent', response)
        except (EOFError, OSError, ssl.SSLError):
            self.wire.event(ident, 'target-closed')
        finally:
            sock.close()


class Socks(Listener):
    def __init__(self, name, wire, destination, entry_setup_ms, phase_ms):
        self.destination, self.entry_setup_ms, self.phase_ms = destination, entry_setup_ms, phase_ms
        self.user = (name + '-fixture-user').encode()
        self.password = (name + '-fixture-password').encode()
        super().__init__(name, wire)

    def response(self, sock, ident, phase, data):
        # Deliberate server response delay, not a claim of real WAN RTT.
        time.sleep(self.phase_ms / 1000)
        sock.sendall(data)
        self.wire.event(ident, phase, data)

    def handle(self, sock):
        ident = self.wire.new(self.name, sock)
        upstream = None
        try:
            if self.entry_setup_ms:
                time.sleep(self.entry_setup_ms / 1000)
                self.wire.event(ident, 'entry-setup-ready')
            head = exact(sock, 2)
            methods = exact(sock, head[1])
            assert head[0] == 5 and 2 in methods
            self.wire.event(ident, 'method-received', head + methods)
            self.response(sock, ident, 'method-sent', b'\x05\x02')
            auth = exact(sock, 2)
            user = exact(sock, auth[1])
            length = exact(sock, 1)
            password = exact(sock, length[0])
            assert auth[0] == 1 and user == self.user and password == self.password
            self.wire.event(ident, 'auth-received', auth + user + length + password)
            self.response(sock, ident, 'auth-sent', b'\x01\x00')
            head = exact(sock, 4)
            assert head[:3] == b'\x05\x01\x00'
            if head[3] == 1:
                address = exact(sock, 4)
                host = socket.inet_ntoa(address)
            elif head[3] == 3:
                length = exact(sock, 1)
                address = length + exact(sock, length[0])
                host = address[1:].decode()
            else:
                raise AssertionError('unexpected address family')
            port_bytes = exact(sock, 2)
            port = struct.unpack('!H', port_bytes)[0]
            assert (host, port) == self.destination
            self.wire.event(ident, 'connect-received', head + address + port_bytes, host=host, port=port)
            upstream = socket.create_connection(('127.0.0.1', port), 3)
            upstream.settimeout(5)
            self.wire.event(ident, 'upstream-opened', peerPort=upstream.getpeername()[1], localPort=upstream.getsockname()[1])
            self.response(sock, ident, 'connect-sent', b'\x05\x00\x00\x01\x7f\x00\x00\x01\x00\x00')
            relay(sock, upstream)
        except (EOFError, OSError) as error:
            self.wire.event(ident, 'peer-eof', error=type(error).__name__)
        except Exception as error:
            self.wire.event(ident, 'fixture-error', error=type(error).__name__)
        finally:
            sock.close()
            if upstream is not None:
                upstream.close()


def auth(sock, node, wire, ident):
    packet = b'\x05\x01\x02'
    wire.event(ident, node.name + '-method-send', packet)
    sock.sendall(packet)
    assert exact(sock, 2) == b'\x05\x02'
    wire.event(ident, node.name + '-method-recv')
    packet = b'\x01' + bytes((len(node.user),)) + node.user + bytes((len(node.password),)) + node.password
    wire.event(ident, node.name + '-auth-send', packet)
    sock.sendall(packet)
    assert exact(sock, 2) == b'\x01\x00'
    wire.event(ident, node.name + '-auth-recv')


def connect(sock, host, port, wire, ident, phase):
    if host == '127.0.0.1':
        address = b'\x01' + socket.inet_aton(host)
    else:
        raw = host.encode()
        address = b'\x03' + bytes((len(raw),)) + raw
    packet = b'\x05\x01\x00' + address + struct.pack('!H', port)
    wire.event(ident, phase + '-send', packet, host=host, port=port)
    sock.sendall(packet)
    assert exact(sock, 10) == b'\x05\x00\x00\x01\x7f\x00\x00\x01\x00\x00'
    wire.event(ident, phase + '-recv')


class CandidatePool:
    """One route's unused preauthenticated connections; never an HTTP/CONNECT pool."""
    def __init__(self, entry, exit_node, wire, key, cap=2, ttl_ms=5000):
        self.entry, self.exit, self.wire, self.key = entry, exit_node, wire, key
        self.cap, self.ttl_ms = cap, ttl_ms
        self.lock = threading.Lock()
        self.items, self.owned = [], set()
        self.epoch, self.consumed = 0, set()
        self.sequence = 0

    def prepare(self, expected_key):
        with self.lock:
            if expected_key != self.key or len(self.owned) >= self.cap:
                return None
            epoch = self.epoch
            sock = socket.create_connection(('127.0.0.1', self.entry.port), 2)
            sock.settimeout(3)
            self.owned.add(sock)
            self.sequence += 1
            ident = 'client-' + str(self.sequence) + '-' + str(sock.getsockname()[1])
        began = mono()
        self.wire.event(ident, 'prepare-start', localPort=sock.getsockname()[1])
        try:
            auth(sock, self.entry, self.wire, ident)
            connect(sock, '127.0.0.1', self.exit.port, self.wire, ident, 'entry-connect')
            auth(sock, self.exit, self.wire, ident)
            self.wire.event(ident, 'preauthenticated-no-target-connect')
            item = {'sock': sock, 'id': ident, 'key': expected_key, 'epoch': epoch, 'readyNs': mono(), 'prepMs': (mono()-began)/1e6}
            with self.lock:
                if epoch != self.epoch or expected_key != self.key:
                    raise EOFError('route invalidated while preparing')
                self.items.append(item)
            return item
        except (EOFError, OSError):
            self.discard(sock)
            return None

    def checkout(self, expected_key):
        with self.lock:
            if expected_key != self.key:
                return None
            while self.items:
                item = self.items.pop(0)
                if item['epoch'] != self.epoch or (mono()-item['readyNs'])/1e6 > self.ttl_ms:
                    self.owned.discard(item['sock'])
                    item['sock'].close()
                    continue
                assert item['id'] not in self.consumed
                self.consumed.add(item['id'])
                self.wire.event(item['id'], 'checkout-once')
                return item
        return None

    def permitted(self, item):
        with self.lock:
            return item['key'] == self.key and item['epoch'] == self.epoch and item['sock'] in self.owned

    def discard(self, sock):
        with self.lock:
            self.owned.discard(sock)
            self.items = [item for item in self.items if item['sock'] is not sock]
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        sock.close()

    def purge(self, next_key):
        with self.lock:
            self.epoch += 1
            self.key = next_key
            sockets = list(self.owned)
            self.items.clear()
            self.owned.clear()
        for sock in sockets:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            sock.close()


def request(pool, client_tls, target_port, key, warm):
    began = mono()
    item = pool.checkout(key) if warm else None
    fallback = item is None
    if item is None:
        item = pool.prepare(key)
        assert item is not None
        item = pool.checkout(key)
    assert pool.permitted(item)
    checkout = mono()
    ident, sock = item['id'], item['sock']
    try:
        connect(sock, 'bench.invalid', target_port, pool.wire, ident, 'target-connect')
        connected = mono()
        with client_tls.wrap_socket(sock, server_hostname='bench.invalid') as tls:
            tls_ready = mono()
            pool.wire.event(ident, 'client-target-tls-ready', alpn=tls.selected_alpn_protocol())
            packet = b'HEAD /probe HTTP/1.1\r\nHost: bench.invalid\r\nConnection: close\r\n\r\n'
            tls.sendall(packet)
            pool.wire.event(ident, 'client-head-sent', packet)
            response = b''
            while b'\r\n\r\n' not in response:
                response += exact(tls, 1)
            assert response.startswith(b'HTTP/1.1 204 ')
            completed = mono()
            pool.wire.event(ident, 'client-head-complete', response)
        return {'socket': ident, 'variant': 'prepared' if warm and not fallback else 'cold', 'poolMiss': fallback,
                'requestMs': (completed-began)/1e6, 'preparationMs': item['prepMs'],
                'readyLeadMs': max(0, (began-item['readyNs'])/1e6),
                'targetConnectMs': (connected-checkout)/1e6, 'targetTlsMs': (tls_ready-connected)/1e6,
                'headMs': (completed-tls_ready)/1e6, 'socketWorkToHeadersMs': item['prepMs']+(completed-checkout)/1e6}
    finally:
        pool.discard(sock)


def wait_for(condition, timeout=2):
    began = mono()
    while not condition():
        if (mono()-began)/1e9 > timeout:
            raise AssertionError('wire condition did not happen')
        time.sleep(.003)
    return (mono()-began)/1e6


def exact_exit_socket(wire,item):
    client=wire.phase(item['id'],'prepare-start')
    entry=wire.socket_for_peer('entry-',client['localPort'])
    upstream=wire.phase(entry,'upstream-opened')
    return wire.socket_for_peer('exit-',upstream['localPort'])


def certificates():
    cert, key = OUT/'fixture-cert.pem', OUT/'fixture-key.pem'
    if not cert.exists() or not key.exists():
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','2','-subj','/CN=bench.invalid','-addext','subjectAltName=DNS:bench.invalid','-keyout',str(key),'-out',str(cert)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    server = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server.load_cert_chain(cert,key)
    server.set_alpn_protocols(['http/1.1'])
    client = ssl.create_default_context(cafile=str(cert))
    client.set_alpn_protocols(['http/1.1'])
    return server,client


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pairs',type=int,default=20)
    args=parser.parse_args()
    assert 4<=args.pairs<=40
    wire=Wire();server_tls,client_tls=certificates()
    target=Target(wire,server_tls)
    exit_node=Socks('exit',wire,('bench.invalid',target.port),0,35)
    entry=Socks('entry',wire,('127.0.0.1',exit_node.port),80,15)
    key=('environment-A','entry-A','fixed-exit-A','lifetime-1')
    rows=[];checks=[]
    def check(name,condition,**evidence):
        assert condition,name
        checks.append({'name':name,'pass':True,**evidence})
    try:
        for index in range(args.pairs):
            order=('cold','prepared') if index%2==0 else ('prepared','cold')
            for variant in order:
                pool=CandidatePool(entry,exit_node,wire,key,cap=1)
                if variant=='prepared':
                    before=wire.count('connect-received','exit-')
                    assert pool.prepare(key)
                    check('Prepared socket has no target CONNECT '+str(index),wire.count('connect-received','exit-')==before)
                row=request(pool,client_tls,target.port,key,variant=='prepared')
                row.update(pair=index,order='AB' if index%2==0 else 'BA')
                rows.append(row)
                pool.purge(None)
        pool=CandidatePool(entry,exit_node,wire,key,cap=2)
        assert pool.prepare(key) and pool.prepare(key)
        check('Capacity never creates a third authenticated tunnel',pool.prepare(key) is None and len(pool.owned)==2)
        check('Other environment cannot check out this route',pool.checkout(('environment-B',*key[1:])) is None)
        item=pool.checkout(key)
        pool.discard(item['sock'])
        item2=pool.checkout(key)
        check('Each item is issued at most once',item2['id']!=item['id'] and pool.checkout(key) is None)
        pool.discard(item2['sock'])
        pool=CandidatePool(entry,exit_node,wire,key)
        item=pool.prepare(key);assert item
        before=wire.count('connect-received','exit-');exit_socket=exact_exit_socket(wire,item)
        pool.purge(('environment-A','entry-B','fixed-exit-A','lifetime-2'))
        eof_ms=wait_for(lambda:wire.phase(exit_socket,'peer-eof') is not None)
        check('Entry/lifetime change closes actual unused exit socket without target CONNECT',wire.count('connect-received','exit-')==before and pool.checkout(key) is None,actualExitEofMs=eof_ms,observedExitSocket=exit_socket)
        pool=CandidatePool(entry,exit_node,wire,key,ttl_ms=20)
        assert pool.prepare(key)
        time.sleep(.03)
        check('Expired authenticated socket is not issued',pool.checkout(key) is None and not pool.owned)
        pool=CandidatePool(entry,exit_node,wire,key)
        started=threading.Event();outcome=[]
        def prepare():
            started.set();outcome.append(pool.prepare(key))
        job=threading.Thread(target=prepare);job.start();started.wait()
        wait_for(lambda:bool(pool.owned));port=next(iter(pool.owned)).getsockname()[1]
        pool.purge(None);job.join(2)
        wait_for(lambda:wire.socket_for_peer('entry-',port) is not None)
        entry_socket=wire.socket_for_peer('entry-',port)
        cancel_ms=wait_for(lambda:wire.phase(entry_socket,'peer-eof') is not None)
        check('Cancellation closes actual preparation socket and cannot publish a late item',not job.is_alive() and outcome==[None] and not pool.items and not pool.owned,actualEntryEofMs=cancel_ms,observedEntrySocket=entry_socket)
        pool=CandidatePool(entry,exit_node,wire,key)
        assert pool.prepare(key);item=pool.checkout(key);before=wire.count('connect-received','exit-')
        pool.purge(('environment-A','entry-A','fixed-exit-A','lifetime-2'))
        check('Restart after checkout revokes its actual socket before CONNECT',not pool.permitted(item) and item['sock'].fileno()==-1 and wire.count('connect-received','exit-')==before)
        pool=CandidatePool(entry,exit_node,wire,key)
        fallback=request(pool,client_tls,target.port,key,True)
        check('Empty pool follows the same full cold chain',fallback['poolMiss'] and fallback['variant']=='cold')
        wait_for(lambda:wire.count('target-head-sent')==len(rows)+1)
        check('Every completed request reached both actual SOCKS servers and target TLS',wire.count('connect-received','exit-')==len(rows)+1 and wire.count('target-tls-ready')==len(rows)+1)
        check('No fixture protocol or destination failure occurred',wire.count('fixture-error')==0)
        grouped={v:[r['requestMs'] for r in rows if r['variant']==v] for v in ['cold','prepared']}
        def summary(values):
            ordered=sorted(values)
            return {'samples':len(values),'p50Ms':statistics.median(values),'p95Ms':ordered[min(len(ordered)-1,int(.95*len(ordered)))],'minMs':min(values),'maxMs':max(values)}
        report={'schema':1,'status':'passed','sourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                'actualTcpWireExecution':True,'actualTwoAuthenticatedSocksHops':True,'actualTargetTls':True,
                'actualMihomoExecution':False,'actualAndroidExecution':False,'productionPoolImplemented':False,
                'scope':'Independent Python protocol candidate, loopback with server response delays; not a shipped core or WAN speed claim.',
                'scriptSha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),
                'fixture':{'entrySetupDelayMs':80,'entryResponseDelayPerSocksPhaseMs':15,'exitResponseDelayPerSocksPhaseMs':35,'fixedExitUdp':False,'target':'https://bench.invalid/probe','targetStatus':204,'alpn':'http/1.1','allDestinationsLoopback':True},
                'sampling':'paired AB/BA, new target TCP/TLS each request; prepared work kept in the report, not subtracted from socket work',
                'summary':{v:summary(values) for v,values in grouped.items()},'rows':rows,'emptyPoolFallback':fallback,
                'checks':checks,'wireEvents':wire.rows,'privateKeysArchived':False}
        report['p50RequestReductionMs']=report['summary']['cold']['p50Ms']-report['summary']['prepared']['p50Ms']
        (OUT/'results.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps({k:report[k] for k in ['status','scope','actualMihomoExecution','actualAndroidExecution','summary','p50RequestReductionMs']},indent=2))
    finally:
        entry.close();exit_node.close();target.close()


if __name__=='__main__':
    main()
