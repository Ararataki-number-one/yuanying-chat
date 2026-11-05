"""Read-only wire evidence around the unchanged controlled IP/SOCKS fixture.

This adapter is used only by the twelfth integration case. It returns the same
real SSLSocket, so the original certificate SNI callback and fleet ownership
checks continue to apply. No request is forwarded and no engine API is mocked.
"""
import copy
import re
import select
import socket
import ssl
import sys
import threading
import time
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'browser'))
from fingerprint_fixture_server import HOSTS, require
from ip_timezone_fixture_server import GEO_HOST, IpTimeZoneFleet
from native_tls_probe_server import (Cursor, HELLO_LIMIT, NeedMore,
    handshake_bytes, parse_client_hello)

MAX_RECORDS = 32
MAX_RECORD_BYTES = 1024 * 1024
RECORD_METADATA_RESERVE = 1024
MAX_HEADER_BYTES = 16384
PHASE = 'gecko-new-york'
HOST = HOSTS[0]


def client_hello_name(records):
    """Bounded SNI selector; the selected webpage is reparsed by the old parser."""
    body = Cursor(handshake_bytes(records)[4:])
    require(body.number(2) == 0x0303, 'combined TLS legacy version')
    body.take(32)
    require(len(body.vector(1)) <= 32, 'combined TLS session bound')
    ciphers = body.vector(2)
    require(len(ciphers) >= 2 and len(ciphers) % 2 == 0, 'combined TLS ciphers')
    require(body.vector(1) == b'\0', 'combined TLS compression')
    extensions = Cursor(body.vector(2)); body.done()
    names, seen = [], set()
    while extensions.at < len(extensions.raw):
        kind, raw = extensions.number(2), extensions.vector(2)
        require(kind not in seen, 'duplicate combined TLS extension'); seen.add(kind)
        if kind == 0:
            current = Cursor(raw); items = Cursor(current.vector(2)); current.done()
            while items.at < len(items.raw):
                require(items.number(1) == 0, 'combined SNI type')
                name = items.vector(2)
                require(0 < len(name) <= 80 and all(33 <= b <= 126 for b in name), 'combined SNI bound')
                names.append(name.decode('ascii'))
    require(len(names) == 1 and names[0] in (*HOSTS, GEO_HOST), 'combined fixed SNI')
    return names[0]


def peek_original(connection):
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        ready, _, _ = select.select([connection], [], [], min(.05, max(0, deadline - time.monotonic())))
        if not ready:
            continue
        raw = connection.recv(HELLO_LIMIT, socket.MSG_PEEK)
        require(raw, 'combined peer closed before ClientHello')
        try:
            handshake_bytes(raw)
            return raw
        except NeedMore:
            time.sleep(.005)
    raise TimeoutError('bounded combined ClientHello')


def request_metadata(raw):
    """Export fixed page/marker paths and the page's frame/favicon diagnostics."""
    require(type(raw) is bytes and 0 < len(raw) <= MAX_HEADER_BYTES and raw.endswith(b'\r\n\r\n'), 'combined HTTP header bound')
    lines = raw[:-4].decode('ascii').split('\r\n')
    pieces = lines[0].split(' ')
    require(len(pieces) == 3 and pieces[0] == 'GET' and pieces[2] in ('HTTP/1.0', 'HTTP/1.1'), 'combined HTTP request')
    headers = {}
    for line in lines[1:]:
        require(':' in line and not line.startswith((' ', '\t')), 'combined HTTP header shape')
        key, value = line.split(':', 1); key, value = key.lower(), value.strip()
        require(re.fullmatch('[a-z0-9-]+', key) and key not in headers and '\0' not in value and len(value) <= 2048, 'combined HTTP header duplicate/bound')
        headers[key] = value
    require(headers.get('host') in (HOST, HOST + ':443'), 'combined HTTP authority')
    require('transfer-encoding' not in headers and headers.get('content-length', '0') == '0', 'combined HTTP body forbidden')
    uri = urlsplit(pieces[1]); require(not uri.scheme and not uri.netloc and not uri.fragment, 'combined origin-form request')
    if uri.path == '/favicon.ico':
        require(not uri.query, 'combined favicon query')
        return dict(path=uri.path, phase='', realm='auxiliary', documentId='')
    query = parse_qs(uri.query, strict_parsing=True)
    require(all(len(v) == 1 for v in query.values()) and query.get('phase') == [PHASE], 'combined exact phase')
    if uri.path == '/env-policy':
        require(set(query) == {'phase'}, 'combined document query')
        return dict(path=uri.path, phase=PHASE, realm='document', documentId='')
    if uri.path == '/env-frame':
        require(set(query) == {'phase'}, 'combined frame query')
        return dict(path=uri.path, phase=PHASE, realm='frame', documentId='')
    require(uri.path == '/worker-probe' and set(query) == {'phase', 'realm', 'documentId'} and query['realm'] == ['document'] and re.fullmatch('[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', query['documentId'][0]), 'combined marker query')
    return dict(path=uri.path, phase=PHASE, realm='document', documentId=query['documentId'][0])


class TlsCpuIpCapture:
    """Install before fleet construction; freeze only after fleet.close()."""
    def __init__(self, certificates, binding):
        require(set(binding) == {'sourceCommit','sourceTree','runNonce','integrationApkSha256','sdkRunId','sdkRunAttempt'}, 'combined full invocation binding')
        require(all(type(binding[k]) is str and re.fullmatch(pattern, binding[k]) for k, pattern in {
            'sourceCommit':'[0-9a-f]{40}', 'sourceTree':'[0-9a-f]{40}', 'runNonce':'[0-9a-f]{32}',
            'integrationApkSha256':'[0-9a-f]{64}', 'sdkRunId':'[1-9][0-9]*', 'sdkRunAttempt':'[1-9][0-9]*'}.items()), 'combined typed invocation')
        require(isinstance(certificates.context, ssl.SSLContext), 'fresh actual SSLContext required')
        self.certificates, self.binding = certificates, dict(binding)
        self.context = certificates.context
        self.context.minimum_version = self.context.maximum_version = ssl.TLSVersion.TLSv1_3
        self.context.options |= ssl.OP_NO_TICKET
        self.context.num_tickets = 0
        self.context.set_alpn_protocols(['http/1.1'])
        self.lock = threading.RLock()
        self.records, self.record_bytes, self.active, self.rejected = [], 0, 0, 0
        self.overflow, self.frozen = False, False
        self._final = None
        certificates.context = self

    def wrap_socket(self, connection, *args, **kwargs):
        require(not args and kwargs == {'server_side': True}, 'combined direct server TLS only')
        with self.lock:
            require(not self.frozen, 'combined capture already frozen'); self.active += 1
        record = None
        try:
            original = peek_original(connection)
            name = client_hello_name(original)
            if name == HOST:
                record = dict(schema=1, host=HOST, clientHello=parse_client_hello(original),
                    tlsNegotiated=False, requestObserved=False, responseObserved=False)
                with self.lock:
                    # Reserve before native handshake, including actual failures.
                    import json
                    size = len(json.dumps(record, separators=(',', ':')).encode()) + RECORD_METADATA_RESERVE
                    if len(self.records) >= MAX_RECORDS or self.record_bytes + size > MAX_RECORD_BYTES:
                        self.overflow = True; raise ValueError('combined wire record bound')
                    self.record_bytes += size; record['sequence'] = len(self.records) + 1; self.records.append(record)
            wrapped = self.context.wrap_socket(connection, server_side=True)
            if record is not None:
                with self.lock:
                    record.update(tlsNegotiated=True, negotiatedVersion=wrapped.version(),
                        negotiatedAlpn=wrapped.selected_alpn_protocol(), sessionReused=wrapped.session_reused)
                self._observe(wrapped, record)
            return wrapped  # Same actual object seen by the original SNI callback.
        except ssl.SSLError as error:
            if record is not None:
                with self.lock: record.update(errorType='SSLError', tlsErrorReason=getattr(error, 'reason', '') if getattr(error, 'reason', '') in ('UNSUPPORTED_PROTOCOL','TLSV1_ALERT_PROTOCOL_VERSION','NO_SHARED_CIPHER','TLSV1_ALERT_UNKNOWN_CA','SSLV3_ALERT_CERTIFICATE_UNKNOWN') else 'OTHER_SSL_ERROR')
            else:
                with self.lock: self.rejected += 1
            raise
        except Exception as error:
            if record is not None:
                with self.lock: record.update(errorType=type(error).__name__)
            else:
                with self.lock: self.rejected += 1
            raise
        finally:
            with self.lock: self.active -= 1

    def _observe(self, wrapped, record):
        original_recv, original_sendall = wrapped.recv, wrapped.sendall
        header = bytearray(); complete = False
        def recv(count, flags=0):
            nonlocal complete
            raw = original_recv(count, flags)
            if raw and not complete:
                header.extend(raw)
                require(len(header) <= MAX_HEADER_BYTES, 'combined observed header bound')
                end = header.find(b'\r\n\r\n')
                if end >= 0:
                    complete = True
                    try:
                        metadata = request_metadata(bytes(header[:end + 4]))
                        with self.lock:
                            require(not self.frozen, 'late combined request after freeze')
                            record.update(requestObserved=True, **metadata)
                    except Exception:
                        with self.lock: record['requestRejected'] = True
                        raise
            return raw
        def sendall(raw, flags=0):
            result = original_sendall(raw, flags)
            if type(raw) is bytes and raw.startswith(b'HTTP/1.1 200 OK\r\n'):
                with self.lock:
                    require(not self.frozen, 'late combined response after freeze')
                    require(record['requestObserved'], 'combined response before fixed request')
                    record['responseObserved'] = True
            return result
        wrapped.recv, wrapped.sendall = recv, sendall

    def wrap_bio(self, *args, **kwargs):
        # The case selects the SOCKS transport. Never silently accept an
        # unobserved nested HTTPS-proxy transport as equivalent wire evidence.
        raise ValueError('combined capture requires direct SOCKS target TLS')

    def snapshot(self, fleet):
        require(isinstance(fleet, IpTimeZoneFleet) and fleet.certificates is self.certificates and fleet.binding == self.binding, 'combined exact owned fleet')
        require(fleet.closed and not fleet.control_thread.is_alive() and all(proxy._closed.is_set() and not proxy.thread.is_alive() and not any(t.is_alive() for t in proxy._threads) for proxy in fleet.proxies.values()), 'combined fleet must quiesce before wire freeze')
        with self.lock:
            require(self.active == 0 and self.certificates.context is self, 'combined all handshake writers finished')
            require(self.context.minimum_version == self.context.maximum_version == ssl.TLSVersion.TLSv1_3
                and self.context.options & ssl.OP_NO_TICKET and self.context.num_tickets == 0,
                'combined actual TLS peer range and ticket readback')
            if self._final is None:
                self.frozen = True
                self._final = dict(schema=1, binding=copy.deepcopy(self.binding), records=copy.deepcopy(self.records),
                    recordsOverflow=self.overflow, rejectedHandshakes=self.rejected, actualWireCapture=True,
                    serverOnlyVersion='TLSv1.3', ticketsDisabled=True, observerIsReadOnly=True,
                    serverClosed=True, serverThreadsJoined=True, upstreamConnections=0,
                    forwardingImplemented=False, privateMaterialExported=False, certificateExceptionUsed=False,
                    rawFatalAlertPacketDecoded=False, fullTlsFingerprintEmulation=False, quicWireVerified=False)
            return copy.deepcopy(self._final)
