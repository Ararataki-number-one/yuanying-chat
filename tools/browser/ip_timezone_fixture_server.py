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
MAX_TRANSPORT_DIAGNOSTICS = 128
TRANSPORT_STAGES = ('connection', 'proxy-tls', 'greeting', 'authentication',
                    'command', 'host', 'port', 'target-tls', 'http-connect',
                    'http', 'send')
TRANSPORT_HOST_ROLES = ('fixture-a', 'fixture-b', 'geo', 'latency-probe-host',
                        'update-host', 'gecko-startup-host', 'other', 'unavailable')
TRANSPORT_HOST_FORMS = ('exact', 'case-variant', 'trailing-dot', 'case-and-trailing-dot',
                        'ipv4', 'ipv6', 'other', 'unavailable')
TRANSPORT_EXCEPTION_TYPES = {
    ValueError: 'ValueError', OSError: 'OSError', TimeoutError: 'TimeoutError',
    ConnectionError: 'ConnectionError', BrokenPipeError: 'BrokenPipeError',
    ConnectionAbortedError: 'ConnectionAbortedError',
    ConnectionRefusedError: 'ConnectionRefusedError',
    ConnectionResetError: 'ConnectionResetError',
    ssl.SSLError: 'SSLError', ssl.SSLEOFError: 'SSLEOFError',
    ssl.SSLZeroReturnError: 'SSLZeroReturnError',
    ssl.SSLWantReadError: 'SSLWantReadError', ssl.SSLWantWriteError: 'SSLWantWriteError',
    ssl.SSLSyscallError: 'SSLSyscallError',
    ssl.SSLCertVerificationError: 'SSLCertVerificationError',
    UnicodeError: 'UnicodeError', UnicodeDecodeError: 'UnicodeDecodeError',
    UnicodeEncodeError: 'UnicodeEncodeError', UnicodeTranslateError: 'UnicodeTranslateError',
}
TRANSPORT_GUARD_CODES = {
    'Synthetic TLS fixture: incomplete controlled transport': 'incomplete-read',
    'Synthetic TLS fixture: SOCKS version invalid': 'socks-version',
    'Synthetic TLS fixture: SOCKS authentication unsupported': 'socks-authentication',
    'Synthetic TLS fixture: SOCKS must use proxy domain DNS': 'socks-command',
    'Synthetic TLS fixture: SOCKS hostname bound invalid': 'socks-host-bound',
    'Synthetic TLS fixture: SOCKS target port invalid': 'socks-port',
    'Synthetic TLS fixture: SOCKS target outside controlled hosts': 'socks-host',
    'Synthetic TLS fixture: CONNECT target invalid': 'connect-target',
    'Synthetic TLS fixture: CONNECT authority differs': 'connect-authority',
    'Synthetic TLS fixture: controlled target authority differs': 'http-authority',
    'Synthetic TLS fixture: actual target TLS SNI differs': 'target-sni',
    'Incomplete synthetic request': 'incomplete-http-read',
    'Synthetic header exceeds bound': 'http-header-bound',
    'Synthetic TLS fixture: request line invalid': 'http-request-line',
    'Synthetic TLS fixture: header invalid': 'http-header',
    'Synthetic TLS fixture: header duplicate or invalid': 'http-header-duplicate',
    'Synthetic TLS fixture: header value exceeds bound': 'http-header-value-bound',
    'Synthetic TLS fixture: request body unsupported': 'http-body',
    'Synthetic TLS fixture: fixed credential-free geo GET required': 'geo-request',
    'Synthetic TLS fixture: held geo response was not released': 'geo-hold-deadline',
    'Synthetic TLS fixture: only synthetic Worker GET permitted': 'content-method',
    'Synthetic TLS fixture: target outside Worker fixture paths': 'content-target',
    'Synthetic TLS fixture: Worker HTTP authority differs': 'content-authority',
    'Synthetic TLS fixture: duplicate Worker query': 'content-query-duplicate',
    'Synthetic TLS fixture: favicon query differs': 'content-favicon-query',
    'Synthetic TLS fixture: Worker phase invalid': 'content-phase',
    'Synthetic TLS fixture: Worker document query differs': 'content-document-query',
    'Synthetic TLS fixture: Worker resource query differs': 'content-resource-query',
    'Synthetic TLS fixture: Worker realm/document invalid': 'content-realm',
    'Synthetic TLS fixture: Worker path/realm differs': 'content-path-realm',
    'Synthetic TLS fixture: Worker request receipt bound exceeded': 'content-receipt-bound',
    'Synthetic TLS fixture: native event bound exceeded': 'native-event-bound',
}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _transport_target(host):
    """Classify bounded ASCII bytes only; this never authorizes a target.

    Known Gecko hosts are default URLs in the locally inspected SDK omni.ja
    d9141a46206221677da206884e3be2789e48d9e3b84eaeded50a374699687b45:
    modules/AppConstants.sys.mjs and defaults/pref/x86_64/geckoview-prefs.js.
    A known default endpoint is not evidence that a request actually occurred.
    """
    if type(host) is not str or not 1 <= len(host) <= 80:
        return ('unavailable', 'unavailable', None)
    try:
        raw = host.encode('ascii')
    except UnicodeError:
        return ('unavailable', 'unavailable', None)
    known = {
        HOSTS[0]: 'fixture-a', HOSTS[1]: 'fixture-b', GEO_HOST: 'geo',
        # NativeNetwork.PROBE and AppUpdatePolicy's fixed trusted origins.
        'www.gstatic.com': 'latency-probe-host',
        'api.github.com': 'update-host', 'github.com': 'update-host',
        'raw.githubusercontent.com': 'update-host',
        'release-assets.githubusercontent.com': 'update-host',
        'objects.githubusercontent.com': 'update-host',
        'firefox.settings.services.mozilla.com': 'gecko-startup-host',
        'aus5.mozilla.org': 'gecko-startup-host',
        'versioncheck-bg.addons.mozilla.org': 'gecko-startup-host',
        'versioncheck.addons.mozilla.org': 'gecko-startup-host',
    }
    without_dot = host[:-1] if host.endswith('.') else host
    role = known.get(without_dot.lower(), 'other')
    form = 'other'
    if role != 'other':
        case = without_dot != without_dot.lower()
        dot = host.endswith('.')
        form = ('case-and-trailing-dot' if case and dot else 'case-variant' if case
                else 'trailing-dot' if dot else 'exact')
    else:
        for family, kind in ((socket.AF_INET, 'ipv4'), (socket.AF_INET6, 'ipv6')):
            try:
                socket.inet_pton(family, host)
                form = kind
                break
            except (OSError, ValueError):
                pass
    return (role, form, digest(raw))


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
        self._response.transport_stage = 'connection'
        self._response.transport_target = None
        try:
            connection.settimeout(15)
            proxy_tls = self.route['protocol'] == 'https-connect'
            if proxy_tls:
                self._response.transport_stage = 'proxy-tls'
                connection = self._track(connection, self.certificates.context.wrap_socket(connection, server_side=True))
            if self.route['protocol'] == 'socks5':
                self._response.transport_stage = 'greeting'
                require(exact_bytes(connection, 1) == b'\x05', 'SOCKS version invalid')
                count = exact_bytes(connection, 1)[0]
                self._response.transport_stage = 'authentication'
                require(1 <= count <= 16 and 0 in exact_bytes(connection, count), 'SOCKS authentication unsupported')
                self._response.transport_stage = 'send'
                connection.sendall(b'\x05\x00')
                self._response.transport_stage = 'command'
                require(exact_bytes(connection, 4) == b'\x05\x01\x00\x03', 'SOCKS must use proxy domain DNS')
                self._response.transport_stage = 'host'
                count = exact_bytes(connection, 1)[0]
                require(1 <= count <= 80, 'SOCKS hostname bound invalid')
                host = exact_bytes(connection, count).decode('ascii')
                self._response.transport_target = _transport_target(host)
                self._response.transport_stage = 'port'
                require(exact_bytes(connection, 2) == b'\x01\xbb', 'SOCKS target port invalid')
                self._response.transport_stage = 'host'
                require(host in (*HOSTS, GEO_HOST), 'SOCKS target outside controlled hosts')
                self._response.transport_stage = 'send'
                connection.sendall(b'\x05\x00\x00\x01\x7f\x00\x00\x01\x00\x00')
            else:
                self._response.transport_stage = 'http-connect'
                method, target, headers = read_header(connection)
                require(method == 'CONNECT' and target in tuple(host + ':443' for host in (*HOSTS, GEO_HOST)), 'CONNECT target invalid')
                host = target[:-4]
                self._response.transport_target = _transport_target(host)
                require(headers.get('host') in (host, target) and 'proxy-authorization' not in headers, 'CONNECT authority differs')
                self._response.transport_stage = 'send'
                connection.sendall(b'HTTP/1.1 200 Connection Established\r\n\r\n')
            self._response.transport_stage = 'target-tls'
            target_tls = (NestedTlsChannel(connection, self.certificates.context) if proxy_tls
                          else self.certificates.context.wrap_socket(connection, server_side=True))
            connection = self._track(connection, target_tls)
            self._response.transport_stage = 'http'
            method, target, headers = read_header(connection)
            require(method == 'GET' and headers.get('host') in (host, host + ':443'), 'controlled target authority differs')
            require(self.certificates.server_name(connection) == host, 'actual target TLS SNI differs')
            if host == GEO_HOST:
                self.fleet.geo(self, connection, target, headers, proxy_tls)
            else:
                super()._respond(connection, 'gecko', host, True, method, target, headers)
                uri = urlsplit(target)
                query = parse_qs(uri.query, strict_parsing=True)
                self.fleet.content(self.name, dict(host=host, path=uri.path,
                    phase=query.get('phase', [''])[0], realm=query.get('realm', ['document'])[0],
                    documentId=query.get('documentId', [''])[0], responseSha256=self._response.sha,
                    tls=True, proxyTls=proxy_tls, targetSni=host, responseWritten=True))
        except (ValueError, OSError, ssl.SSLError, UnicodeError) as error:
            self.fleet.error(self.name, 'controlled-transport-rejected')
            self.fleet._transport_failure(self.name, self._response.transport_stage, error, self._response.transport_target)
        finally:
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
        previous_stage = getattr(self._response, 'transport_stage', 'http')
        self._response.transport_stage = 'send'
        WorkerFixtureServer._send(connection, kind, body, coop=coop)
        self._response.sha = digest(body)
        self._response.transport_stage = previous_stage


class IpTimeZoneFleet:
    def __init__(self, certificates, script, gecko_script, binding):
        self.certificates, self.binding = certificates, dict(binding)
        self.lock = threading.Lock()
        self.case = CASES[0]
        self.behavior = {name: 'normal' for name in ROUTES}
        self.release_events = {name: threading.Event() for name in ROUTES}
        self.events, self.errors = [], {name: 0 for name in ROUTES}
        self._transport_events = []
        self._transport_counts = {name: {stage: {} for stage in TRANSPORT_STAGES} for name in ROUTES}
        self._transport_total = 0
        self._transport_quiescent = False
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

    def _transport_failure(self, route, stage, error, target=None):
        """Fixed classes/buckets only; never retain exception messages or raw wire data.

        The original error counter is deliberately separate and remains strict.
        Other* identifies an unlisted subclass, not its potentially private name.
        """
        require(route in ROUTES and stage in TRANSPORT_STAGES, 'fixed diagnostic transport owner')
        require(isinstance(error, (ValueError, OSError, ssl.SSLError, UnicodeError)), 'fixed diagnostic exception family')
        category = TRANSPORT_EXCEPTION_TYPES.get(type(error))
        if category is None:
            category = ('OtherSSLError' if isinstance(error, ssl.SSLError) else
                        'OtherUnicodeError' if isinstance(error, UnicodeError) else
                        'OtherOSError' if isinstance(error, OSError) else 'OtherValueError')
        guard_code = 'other-guard'
        if type(error) is ValueError and len(error.args) == 1 and type(error.args[0]) is str:
            guard_code = TRANSPORT_GUARD_CODES.get(error.args[0], 'other-guard')
        role, form, target_sha = ('unavailable', 'unavailable', None) if target is None else target
        with self.lock:
            self._transport_total += 1
            counts = self._transport_counts[route][stage]
            counts[category] = counts.get(category, 0) + 1
            if len(self._transport_events) < MAX_TRANSPORT_DIAGNOSTICS:
                self._transport_events.append(dict(sequence=self._transport_total,
                    route=route, protocol=ROUTES[route]['protocol'], stage=stage,
                    exceptionClass=category, guardCode=guard_code, collectorClosed=self.closed,
                    hostRole=role, hostForm=form, hostSha256=target_sha))

    def diagnostic_snapshot(self):
        """Separate bounded failure observations, never an EOF exemption or proof.

        quiescent becomes true only after the unchanged close guards complete.
        A pre-close snapshot can still gain later failures and is not final.
        """
        with self.lock:
            return dict(schema=1, kind='ip-timezone-transport-diagnostics-v1',
                binding=json.loads(json.dumps(self.binding)),
                collectorClosed=self.closed, quiescent=self._transport_quiescent,
                eventLimit=MAX_TRANSPORT_DIAGNOSTICS, totalFailures=self._transport_total,
                recordedEvents=len(self._transport_events),
                droppedEvents=self._transport_total - len(self._transport_events),
                counts=json.loads(json.dumps(self._transport_counts)),
                events=json.loads(json.dumps(self._transport_events)))

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
        proxy._response.transport_stage = 'send'
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
        with self.lock:
            self._transport_quiescent = True
