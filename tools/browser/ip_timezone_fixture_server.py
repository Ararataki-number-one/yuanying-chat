#!/usr/bin/env python3
"""Controlled native proxy/TLS fixture, never a public-IP geolocation oracle.

All endpoints are terminated locally. Private certificates remain in /tmp.
SOCKS5, HTTP CONNECT and HTTPS-proxy CONNECT exercise different real transports;
the fixed production ipwho.is response is explicitly synthetic test data.
"""
import contextlib
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import socket
import ssl
import tempfile
import threading
import time
from urllib.parse import parse_qs, urlsplit

from fingerprint_fixture_server import HOSTS, openssl, read_header, require
from newworker_fixture_server import WorkerFixtureServer

GEO_HOST = 'ipwho.is'
GEO_SOURCE = 'https://ipwho.is/?fields=success,ip,timezone.id'
GEO_TARGET = '/?fields=success,ip,timezone.id'
GUEST_CONTROL_PORT = 18769
ROUTES = {
    'socks': dict(protocol='socks5', guestPort=18766, zoneId='America/New_York', ip='8.8.8.8'),
    'http': dict(protocol='http-connect', guestPort=18767, zoneId='Asia/Kathmandu', ip='1.1.1.1'),
    'https': dict(protocol='https-connect', guestPort=18768, zoneId='UTC', ip='9.9.9.9'),
}
CASES = ('default-socks', 'route-switch-http', 'https-proxy', 'cancel-late',
         'manual-system', 'manual-iana', 'rfp-priority', 'manual-rfp-denied',
         'bootstrap-isolation', 'redirect-rejected', 'invalid-geo-rejected')
MAX_NATIVE_EVENTS = 240
TRANSPORT_STAGES = ('accepted','proxy-tls','socks-greeting','socks-methods','socks-command',
    'socks-host-length','socks-host','socks-port','connect-header','connect-authority',
    'target-tls','target-header','target-authority','target-sni','geo-get','content-get','response-written')
TRANSPORT_REASONS = {
    'SOCKS version invalid':'socks-version', 'SOCKS authentication unsupported':'socks-auth',
    'SOCKS must use proxy domain DNS':'socks-command-domain-dns', 'SOCKS hostname bound invalid':'socks-host-bound',
    'SOCKS target port invalid':'socks-port', 'SOCKS target outside controlled hosts':'socks-host',
    'CONNECT target invalid':'connect-target', 'CONNECT authority differs':'connect-authority',
    'controlled target authority differs':'target-authority', 'actual target TLS SNI differs':'target-sni',
    'fixed credential-free geo GET required':'fixed-geo-get',
    'incomplete controlled transport':'peer-closed',
}


def host_class(host):
    return 'geo' if host == GEO_HOST else 'fixture' if host in HOSTS else 'unknown'


def transport_reason(error):
    # Do not export error strings: OpenSSL/HTTP errors may contain peer bytes.
    for text, code in TRANSPORT_REASONS.items():
        if str(error) == 'Synthetic TLS fixture: ' + text:
            return code
    if isinstance(error, (TimeoutError, socket.timeout)):
        return 'timeout'
    if isinstance(error, ssl.SSLError):
        return 'tls-rejected'
    if isinstance(error, UnicodeError):
        return 'non-ascii-rejected'
    if str(error) == 'Incomplete synthetic request':
        return 'peer-closed'
    return 'validation-rejected' if isinstance(error, ValueError) else 'socket-rejected'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class IpFixtureCertificates:
    """Fresh controlled authority and exact fixed-host SANs, no release trust."""
    def __init__(self):
        self._temporary = tempfile.TemporaryDirectory(prefix='pocketchat-ip-timezone-tls-', dir='/tmp')
        self.directory = Path(self._temporary.name)
        os.chmod(self.directory, 0o700)
        self._sni, self._lock = {}, threading.Lock()
        try:
            ca_key, leaf_key = self.directory / 'ca.key', self.directory / 'leaf.key'
            self.ca, self.leaf = self.directory / 'ca.pem', self.directory / 'leaf.pem'
            csr, extension = self.directory / 'leaf.csr', self.directory / 'leaf.ext'
            openssl('req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '2', '-sha256',
                    '-subj', '/CN=Ephemeral controlled IP-timezone fixture CA', '-keyout', ca_key,
                    '-out', self.ca, '-addext', 'basicConstraints=critical,CA:TRUE,pathlen:0',
                    '-addext', 'keyUsage=critical,keyCertSign,cRLSign')
            openssl('req', '-new', '-newkey', 'rsa:2048', '-nodes', '-subj', '/CN=' + GEO_HOST,
                    '-keyout', leaf_key, '-out', csr)
            extension.write_text('basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\n'
                                 'extendedKeyUsage=serverAuth\nsubjectAltName=' +
                                 ','.join('DNS:' + host for host in (*HOSTS, GEO_HOST)) + ',IP:127.0.0.1\n')
            openssl('x509', '-req', '-in', csr, '-CA', self.ca, '-CAkey', ca_key, '-CAcreateserial',
                    '-days', '2', '-sha256', '-extfile', extension, '-out', self.leaf)
            for path in self.directory.iterdir():
                os.chmod(path, 0o600)
            self.ca_bytes = self.ca.read_bytes()
            self.ca_sha = digest(self.ca_bytes)
            self.leaf_sha = digest(ssl.PEM_cert_to_DER_cert(self.leaf.read_text('ascii')))
            self.subject_hash = openssl('x509', '-in', self.ca, '-subject_hash_old', '-noout').decode('ascii').strip()
            require(re.fullmatch('[0-9a-f]{8}', self.subject_hash), 'public CA identity invalid')
            for host in (*HOSTS, GEO_HOST):
                openssl('verify', '-CAfile', self.ca, '-verify_hostname', host, self.leaf)
            openssl('verify', '-CAfile', self.ca, '-verify_ip', '127.0.0.1', self.leaf)
            self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            self.context.minimum_version = ssl.TLSVersion.TLSv1_2
            self.context.load_cert_chain(self.leaf, leaf_key)
            def sni(channel, name, context):
                with self._lock:
                    self._sni[id(channel)] = name or ''
            self.context.set_servername_callback(sni)
            self.public = dict(caPemSha256=self.ca_sha, leafDerSha256=self.leaf_sha,
                               subjectHashOld=self.subject_hash, opensslChainVerified=True,
                               hostnameVerified=[*HOSTS, GEO_HOST], proxyIpSanVerified='127.0.0.1',
                               ephemeral=True, privateMaterialLocation='host-tmp-only',
                               privateMaterialExported=False, certificateExceptionUsed=False)
        except BaseException:
            self.close()
            raise

    def server_name(self, channel):
        with self._lock:
            return self._sni.get(id(channel.ssl if isinstance(channel, NestedTlsChannel) else channel), '')

    def close(self):
        self._temporary.cleanup()


class NestedTlsChannel:
    """Target TLS inside an already authenticated HTTPS proxy TLS connection."""
    def __init__(self, transport, context, server_side=True, server_hostname=None):
        self.transport = transport
        self.incoming, self.outgoing = ssl.MemoryBIO(), ssl.MemoryBIO()
        self.ssl = context.wrap_bio(self.incoming, self.outgoing, server_side=server_side,
                                    server_hostname=None if server_side else server_hostname)
        self._drive(self.ssl.do_handshake)

    def _flush(self):
        while self.outgoing.pending:
            self.transport.sendall(self.outgoing.read())

    def _drive(self, action):
        while True:
            try:
                result = action()
                self._flush()
                return result
            except ssl.SSLWantWriteError:
                self._flush()
            except ssl.SSLWantReadError:
                self._flush()
                value = self.transport.recv(65536)
                if not value:
                    self.incoming.write_eof()
                else:
                    self.incoming.write(value)

    def recv(self, count):
        try:
            return self._drive(lambda: self.ssl.read(count))
        except (ssl.SSLZeroReturnError, ssl.SSLEOFError):
            return b''

    def sendall(self, value):
        offset = 0
        while offset < len(value):
            offset += self._drive(lambda: self.ssl.write(value[offset:]))

    def settimeout(self, value):
        self.transport.settimeout(value)

    def shutdown(self, how):
        self.transport.shutdown(how)

    def close(self):
        self.transport.close()


def exact_bytes(connection, count):
    result = bytearray()
    while len(result) < count:
        value = connection.recv(count - len(result))
        require(value, 'incomplete controlled transport')
        result.extend(value)
    return bytes(result)


class IpRouteProxy(WorkerFixtureServer):
    def __init__(self, fleet, name, script, binding, gecko_script):
        self.fleet, self.name = fleet, name
        self.route = dict(ROUTES[name])
        self._response = threading.local()
        super().__init__(fleet.certificates, script, binding, gecko_script=gecko_script)

    def _track(self, previous, current):
        with self._lock:
            self._clients.discard(previous)
            self._clients.add(current)
        return current

    def _serve(self, connection, engine):
        diagnostic = self.fleet.transport_start(self.name)
        failure = None
        try:
            connection.settimeout(15)
            proxy_tls = self.route['protocol'] == 'https-connect'
            if proxy_tls:
                self.fleet.transport_stage(diagnostic, 'proxy-tls')
                connection = self._track(connection, self.certificates.context.wrap_socket(connection, server_side=True))
            if self.route['protocol'] == 'socks5':
                self.fleet.transport_stage(diagnostic, 'socks-greeting')
                greeting = exact_bytes(connection, 1)
                self.fleet.transport_stage(diagnostic, 'socks-greeting', greetingVersion=greeting[0])
                require(greeting == b'\x05', 'SOCKS version invalid')
                self.fleet.transport_stage(diagnostic, 'socks-methods')
                count = exact_bytes(connection, 1)[0]
                self.fleet.transport_stage(diagnostic, 'socks-methods', methodCount=count)
                # Preserve original short-circuit/bounds and exact strict gate.
                methods = exact_bytes(connection, count) if 1 <= count <= 16 else b''
                self.fleet.transport_stage(diagnostic, 'socks-methods', noAuthOffered=0 in methods)
                require(1 <= count <= 16 and 0 in methods, 'SOCKS authentication unsupported')
                connection.sendall(b'\x05\x00')
                self.fleet.transport_stage(diagnostic, 'socks-command')
                command = exact_bytes(connection, 4)
                self.fleet.transport_stage(diagnostic, 'socks-command', commandVersion=command[0], command=command[1], addressType=command[3])
                require(command == b'\x05\x01\x00\x03', 'SOCKS must use proxy domain DNS')
                self.fleet.transport_stage(diagnostic, 'socks-host-length')
                count = exact_bytes(connection, 1)[0]
                require(1 <= count <= 80, 'SOCKS hostname bound invalid')
                self.fleet.transport_stage(diagnostic, 'socks-host')
                host = exact_bytes(connection, count).decode('ascii')
                self.fleet.transport_stage(diagnostic, 'socks-port', hostClass=host_class(host))
                port = exact_bytes(connection, 2)
                self.fleet.transport_stage(diagnostic, 'socks-port', httpsPort=port==b'\x01\xbb')
                require(port == b'\x01\xbb', 'SOCKS target port invalid')
                require(host in (*HOSTS, GEO_HOST), 'SOCKS target outside controlled hosts')
                connection.sendall(b'\x05\x00\x00\x01\x7f\x00\x00\x01\x00\x00')
            else:
                self.fleet.transport_stage(diagnostic, 'connect-header')
                method, target, headers = read_header(connection)
                self.fleet.transport_stage(diagnostic, 'connect-authority', httpMethod='CONNECT' if method=='CONNECT' else 'other')
                require(method == 'CONNECT' and target in tuple(host + ':443' for host in (*HOSTS, GEO_HOST)), 'CONNECT target invalid')
                host = target[:-4]
                self.fleet.transport_stage(diagnostic, 'connect-authority', hostClass=host_class(host))
                require(headers.get('host') in (host, target) and 'proxy-authorization' not in headers, 'CONNECT authority differs')
                connection.sendall(b'HTTP/1.1 200 Connection Established\r\n\r\n')
            self.fleet.transport_stage(diagnostic, 'target-tls')
            target_tls = (NestedTlsChannel(connection, self.certificates.context) if proxy_tls
                          else self.certificates.context.wrap_socket(connection, server_side=True))
            connection = self._track(connection, target_tls)
            self.fleet.transport_stage(diagnostic, 'target-header')
            method, target, headers = read_header(connection)
            self.fleet.transport_stage(diagnostic, 'target-authority', httpMethod='GET' if method=='GET' else 'other', credentialsPresent='authorization' in headers or 'cookie' in headers)
            require(method == 'GET' and headers.get('host') in (host, host + ':443'), 'controlled target authority differs')
            self.fleet.transport_stage(diagnostic, 'target-sni', sniClass=host_class(self.certificates.server_name(connection)))
            require(self.certificates.server_name(connection) == host, 'actual target TLS SNI differs')
            if host == GEO_HOST:
                self.fleet.transport_stage(diagnostic, 'geo-get', exactGeoPath=target==GEO_TARGET)
                self.fleet.geo(self, connection, target, headers, proxy_tls)
            else:
                self.fleet.transport_stage(diagnostic, 'content-get')
                super()._respond(connection, 'gecko', host, True, method, target, headers)
                uri = urlsplit(target)
                query = parse_qs(uri.query, strict_parsing=True)
                self.fleet.content(self.name, dict(host=host, path=uri.path,
                    phase=query.get('phase', [''])[0], realm=query.get('realm', ['document'])[0],
                    documentId=query.get('documentId', [''])[0], responseSha256=self._response.sha,
                    tls=True, proxyTls=proxy_tls, targetSni=host, responseWritten=True))
            self.fleet.transport_stage(diagnostic, 'response-written')
        except (ValueError, OSError, ssl.SSLError, UnicodeError) as error:
            failure = error
            self.fleet.error(self.name, 'controlled-transport-rejected')
        finally:
            self.fleet.transport_end(diagnostic, failure)
            with self._lock:
                self._clients.discard(connection)
                self._threads.discard(threading.current_thread())
            with contextlib.suppress(OSError):
                connection.close()
            self._gate.release()

    def _send(self, connection, kind, body, coop=False):
        # The existing real SW remains the observer. This additional message
        # handler executes an ordinary, credential-free fetch without private
        # host metadata; it cannot borrow the extension's bootstrap capability.
        if kind == 'text/javascript' and b"const cacheName='pocketchat-worker-policy-v1'" in body:
            prefix = ("addEventListener('message',event=>{if(!event.data||event.data.action!=='fixed-ip-bootstrap')return;"
                "event.stopImmediatePropagation();event.waitUntil((async()=>{let allowed=false;try{const r=await fetch("
                + json.dumps(GEO_SOURCE) + ",{credentials:'omit',redirect:'error',cache:'no-store'});allowed=r.ok;}catch(_){}"
                "event.ports[0].postMessage({executed:true,networkAllowed:allowed});})());});").encode()
            body = prefix + body
        WorkerFixtureServer._send(connection, kind, body, coop=coop)
        self._response.sha = digest(body)


class IpTimeZoneFleet:
    def __init__(self, certificates, script, gecko_script, binding):
        self.certificates, self.binding = certificates, dict(binding)
        self.lock = threading.Lock()
        self._transport_lock = threading.Lock()
        self._transport_serial = 0
        self._transport_active = {}
        self._transport_closed = []
        self._transport_counts = {}
        self._transport_overflow = False
        self.case = CASES[0]
        self.behavior = {name: 'normal' for name in ROUTES}
        self.release_events = {name: threading.Event() for name in ROUTES}
        self.events, self.errors = [], {name: 0 for name in ROUTES}
        self.control_requests = 0
        self.closed = False
        self.proxies = {name: IpRouteProxy(self, name, script, binding, gecko_script) for name in ROUTES}
        fleet = self
        class Control(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_POST(self):
                try:
                    require(self.path == '/__ip-control', 'control path invalid')
                    size = self.headers.get('Content-Length', '')
                    require(size.isdigit() and 0 < int(size) <= 8192 and 'Transfer-Encoding' not in self.headers, 'control body bound invalid')
                    def pairs(rows):
                        result = {}
                        for key, value in rows:
                            require(key not in result, 'duplicate control key')
                            result[key] = value
                        return result
                    value = json.loads(self.rfile.read(int(size)), object_pairs_hook=pairs,
                        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite control number')))
                    require(type(value) is dict and value.get('sourceCommit') == fleet.binding['sourceCommit'] and value.get('runNonce') == fleet.binding['runNonce'], 'control invocation differs')
                    response = fleet.control(value)
                    raw = json.dumps(response, separators=(',', ':')).encode()
                    require(len(raw) <= 262144, 'control receipt exceeds bound')
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                except (ValueError, OSError, UnicodeError):
                    self.send_error(400)
        self.control_server = ThreadingHTTPServer(('127.0.0.1', 0), Control)
        # server_close joins these bounded handlers, including incomplete body
        # readers. A final snapshot must have no possible later receipt writer.
        self.control_server.daemon_threads = False
        original_get_request = self.control_server.get_request
        def bounded_request():
            connection, address = original_get_request()
            connection.settimeout(5)
            return connection, address
        self.control_server.get_request = bounded_request
        self.control_thread = threading.Thread(target=self.control_server.serve_forever, daemon=True)

    def start(self):
        for proxy in self.proxies.values():
            proxy.start()
            proxy.begin('gecko')
        self.control_thread.start()
        return self

    def ports(self):
        return {ROUTES[name]['guestPort']: proxy.port for name, proxy in self.proxies.items()} | {GUEST_CONTROL_PORT: self.control_server.server_port}

    def transport_start(self, route):
        require(route in ROUTES, 'fixed diagnostic route only')
        with self._transport_lock:
            if self._transport_serial >= 10000:
                self._transport_overflow = True
                return 0
            self._transport_serial += 1
            serial = self._transport_serial
            self._transport_active[serial] = dict(connection=serial, route=route, stage='accepted', hostClass='unknown')
            return serial

    def transport_stage(self, serial, stage, **values):
        require(stage in TRANSPORT_STAGES and set(values)<=set(('greetingVersion','methodCount','noAuthOffered','commandVersion','command','addressType','hostClass','httpsPort','httpMethod','credentialsPresent','sniClass','exactGeoPath')), 'fixed diagnostic metadata only')
        for key, value in values.items():
            if key in ('greetingVersion','methodCount','commandVersion','command','addressType'):
                require(type(value) is int and 0 <= value <= 255, 'bounded protocol number required')
            elif key in ('hostClass','sniClass'):
                require(value in ('geo','fixture','unknown'), 'fixed host category required')
            elif key == 'httpMethod':
                require(value in ('GET','CONNECT','other'), 'fixed method category required')
            else:
                require(type(value) is bool, 'typed protocol flag required')
        with self._transport_lock:
            row = self._transport_active.get(serial)
            if row is None:
                return
            row.update(stage=stage, **values)
            key = row['route'] + ':' + stage
            self._transport_counts[key] = min(10000, self._transport_counts.get(key, 0) + 1)

    def transport_end(self, serial, error):
        with self._transport_lock:
            row = self._transport_active.pop(serial, None)
            if row is None:
                return
            row.update(outcome='completed' if error is None else 'rejected', reason='none' if error is None else transport_reason(error), duringCleanup=self.closed)
            self._transport_closed.append(row)
            if len(self._transport_closed)>32:
                self._transport_closed.pop(0)

    def diagnostics_snapshot(self):
        with self._transport_lock:
            return dict(schema=1, binding=dict(self.binding), diagnosticOnly=True,
                releaseAcceptance=False, actualPublicIpGeolocationVerified=False,
                upstreamConnections=0, forwardingImplemented=False,
                connectionsObserved=self._transport_serial, counters=dict(self._transport_counts),
                active=json.loads(json.dumps(list(self._transport_active.values()))),
                recentClosed=json.loads(json.dumps(self._transport_closed)),
                olderClosedOmitted=max(0,self._transport_serial-len(self._transport_active)-len(self._transport_closed)),
                connectionBoundExceeded=self._transport_overflow,
                scope='Protocol stage/reason enums and fixed host categories only; no original host, IP, credential, request body or TLS key is exported.')

    def control(self, value):
        common = {'sourceCommit', 'runNonce', 'action'}
        action = value.get('action')
        with self.lock:
            require(not self.closed and self.control_requests < 20000, 'control request bound exceeded')
            self.control_requests += 1
            if action == 'snapshot':
                require(set(value) == common, 'snapshot control keys differ')
            elif action == 'stage':
                require(set(value) == common | {'case'} and value['case'] in CASES, 'stage control differs')
                self.case = value['case']
            elif action == 'behavior':
                require(set(value) == common | {'route', 'behavior'} and value['route'] in ROUTES and value['behavior'] in ('normal', 'hold', 'redirect', 'invalid'), 'behavior control differs')
                route = value['route']
                self.behavior[route] = value['behavior']
                self.release_events[route].clear()
            elif action == 'release':
                require(set(value) == common | {'route'} and value['route'] in ROUTES, 'release control differs')
                self.release_events[value['route']].set()
            else:
                raise ValueError('Unknown controlled action')
        return self.snapshot()

    def _event(self, route, value):
        require(route in ROUTES and len(self.events) < MAX_NATIVE_EVENTS, 'native event bound exceeded')
        row = dict(sequence=len(self.events) + 1, route=route, protocol=ROUTES[route]['protocol'], case=self.case, **value)
        self.events.append(row)
        return row

    def content(self, route, value):
        with self.lock:
            self._event(route, dict(kind='content', **value))

    def error(self, route, code):
        require(code == 'controlled-transport-rejected', 'error category invalid')
        with self.lock:
            self.errors[route] += 1

    def geo(self, proxy, connection, target, headers, proxy_tls):
        require(target == GEO_TARGET and 'authorization' not in headers and 'cookie' not in headers,
                'fixed credential-free geo GET required')
        with self.lock:
            behavior = self.behavior[proxy.name]
            row = self._event(proxy.name, dict(kind='geo', host=GEO_HOST, path=GEO_TARGET,
                method='GET', tls=True, proxyTls=proxy_tls, targetSni=GEO_HOST,
                credentialsPresent=False, responseWritten=False, behavior=behavior,
                responseNonce=self.binding['runNonce'] + '-' + proxy.name + '-' + str(len(self.events) + 1)))
        if behavior == 'hold':
            require(self.release_events[proxy.name].wait(15), 'held geo response was not released')
        data = dict(success=True, ip=proxy.route['ip'], timezone={'id': proxy.route['zoneId']})
        if behavior == 'invalid':
            data['timezone']['id'] = 'Invalid/ControlledFixtureZone'
        body = json.dumps(data, separators=(',', ':')).encode()
        status = 302 if behavior == 'redirect' else 200
        head = ('HTTP/1.1 ' + ('302 Found' if status == 302 else '200 OK') + '\r\n'
                'Content-Type: application/json\r\nAccess-Control-Allow-Origin: *\r\n'
                'Cache-Control: no-store\r\nConnection: close\r\nContent-Length: ' + str(len(body)) + '\r\n' +
                ('Location: https://' + HOSTS[0] + '/forbidden-geo-redirect\r\n' if status == 302 else '') + '\r\n').encode('ascii')
        with self.lock:
            row['responseAttempted'] = True
        try:
            connection.sendall(head + body)
        except (OSError, ssl.SSLError):
            with self.lock:
                row['responseWriteFailed'] = True
            raise
        with self.lock:
            row.update(responseWritten=True, status=status, responseSha256=digest(body),
                       syntheticIp=data['ip'], syntheticZoneId=data['timezone']['id'])

    def snapshot(self):
        with self.lock:
            return dict(schema=1, binding=dict(self.binding), syntheticGeoService=True,
                actualPublicIpGeolocationVerified=False, productionEndpointOverride=False,
                geoSource=GEO_SOURCE, routes={name: {key: value for key, value in row.items() if key in ('protocol', 'guestPort')} for name, row in ROUTES.items()},
                events=json.loads(json.dumps(self.events)), errors=dict(self.errors),
                controlRequests=self.control_requests, upstreamConnections=0,
                forwardingImplemented=False, certificateExceptionUsed=False,
                caPemSha256=self.certificates.ca_sha, leafDerSha256=self.certificates.leaf_sha,
                closed=self.closed)

    def close(self):
        with self.lock:
            self.closed = True
            for event in self.release_events.values():
                event.set()
        self.control_server.shutdown()
        self.control_server.server_close()
        if self.control_thread.is_alive():
            self.control_thread.join(3)
        failures = []
        for name, proxy in self.proxies.items():
            try:
                proxy.close()
            except Exception:
                failures.append(name)
        require(not self.control_thread.is_alive() and not failures, 'native fixture did not quiesce')
