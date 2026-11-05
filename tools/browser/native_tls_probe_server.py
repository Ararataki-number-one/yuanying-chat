#!/usr/bin/env python3
"""Diagnostic-only, upstream-free TLS peers and bounded actual ClientHello capture."""
import hashlib
import json
import select
import socket
import ssl
import threading
import time
from urllib.parse import parse_qs, urlsplit

from fingerprint_fixture_server import HOSTS, read_header, require

GUEST_PORT = 18776
TRIALS = (("default-tls12", 41441, "TLSv1.2", True),
          ("strict-tls12", 41442, "TLSv1.2", False),
          ("strict-tls13", 41443, "TLSv1.3", True),
          ("restored-tls12", 41444, "TLSv1.2", True))
HELLO_LIMIT = 65536


class NeedMore(Exception):
    pass


class Cursor:
    def __init__(self, raw):
        self.raw, self.at = raw, 0

    def take(self, count):
        require(type(count) is int and count >= 0 and self.at + count <= len(self.raw), "truncated ClientHello")
        value = self.raw[self.at:self.at + count]
        self.at += count
        return value

    def number(self, count):
        return int.from_bytes(self.take(count), "big")

    def vector(self, count):
        return self.take(self.number(count))

    def done(self):
        require(self.at == len(self.raw), "trailing ClientHello bytes")


def handshake_bytes(records):
    """Reassemble only the first handshake across bounded real TLS records."""
    require(type(records) is bytes and len(records) <= HELLO_LIMIT, "TLS record bound")
    offset, handshake = 0, bytearray()
    while True:
        if len(records) - offset < 5:
            raise NeedMore()
        kind, major, minor = records[offset:offset + 3]
        count = int.from_bytes(records[offset + 3:offset + 5], "big")
        require(kind == 22 and major == 3 and minor in (1, 2, 3) and 0 < count <= 18432, "initial TLS record invalid")
        if len(records) - offset - 5 < count:
            raise NeedMore()
        handshake.extend(records[offset + 5:offset + 5 + count])
        require(len(handshake) <= HELLO_LIMIT, "ClientHello handshake bound")
        if len(handshake) >= 4:
            require(handshake[0] == 1, "first TLS handshake is not ClientHello")
            target = 4 + int.from_bytes(handshake[1:4], "big")
            require(38 <= target <= HELLO_LIMIT, "ClientHello length invalid")
            if len(handshake) >= target:
                return bytes(handshake[:target])
        offset += 5 + count


def parse_client_hello(records):
    handshake = handshake_bytes(records)
    body = Cursor(handshake[4:])
    legacy = body.number(2)
    require(legacy == 0x0303, "unexpected ClientHello legacy version")
    random = body.take(32)
    session = body.vector(1)
    require(len(session) <= 32, "ClientHello session id bound")
    ciphers = body.vector(2)
    require(len(ciphers) >= 2 and len(ciphers) % 2 == 0, "ClientHello cipher vector invalid")
    require(body.vector(1) == b"\x00", "ClientHello compression invalid")
    extensions = Cursor(body.vector(2))
    body.done()
    seen, versions, alpn, names, psk = [], [], [], [], False
    while extensions.at < len(extensions.raw):
        kind, value = extensions.number(2), extensions.vector(2)
        require(kind not in seen, "duplicate ClientHello extension")
        seen.append(kind)
        current = Cursor(value)
        if kind == 43:
            items = current.vector(1)
            require(items and len(items) % 2 == 0, "supported_versions invalid")
            versions = [int.from_bytes(items[index:index + 2], "big") for index in range(0, len(items), 2)]
            require(len(versions) == len(set(versions)), "duplicate supported version")
            current.done()
        elif kind == 16:
            items = Cursor(current.vector(2))
            current.done()
            while items.at < len(items.raw):
                item = items.vector(1)
                require(item and all(32 <= c <= 126 for c in item), "ALPN entry invalid")
                alpn.append(item.decode("ascii"))
            require(len(alpn) == len(set(alpn)), "duplicate ALPN entry")
        elif kind == 0:
            items = Cursor(current.vector(2))
            current.done()
            while items.at < len(items.raw):
                require(items.number(1) == 0, "SNI name type invalid")
                names.append(items.vector(2).decode("ascii"))
            require(names == [HOSTS[0]], "controlled SNI differs")
        elif kind == 41:
            psk = True
    require(43 in seen and versions and names == [HOSTS[0]], "required ClientHello extension missing")
    require("http/1.1" in alpn, "HTTP/1.1 ALPN unavailable")
    return dict(schema=1, actualWireBytes=True, clientHelloSha256=hashlib.sha256(handshake).hexdigest(),
                clientHelloHandshakeHex=handshake.hex(),
                clientRandomHex=random.hex(), legacyVersion=legacy, supportedVersions=versions,
                offeredAlpn=alpn, serverNames=names, extensionIds=seen,
                preSharedKeyOffered=psk, sessionIdBytes=len(session),
                cipherSuites=[int.from_bytes(ciphers[i:i + 2], "big") for i in range(0, len(ciphers), 2)])


def peek_client_hello(connection):
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        select.select([connection], [], [], min(.05, max(0, deadline - time.monotonic())))
        raw = connection.recv(HELLO_LIMIT, socket.MSG_PEEK)
        require(raw, "peer closed before ClientHello")
        try:
            return parse_client_hello(raw)
        except NeedMore:
            time.sleep(.005)
    raise TimeoutError("bounded incomplete ClientHello")


class NativeTlsServer:
    """Each controlled CONNECT authority owns a fresh, non-resuming TLS peer."""
    def __init__(self, certificates, nonce, source):
        self.certificates, self.nonce, self.source = certificates, nonce, source
        self.socket = socket.socket()
        self.socket.bind(("127.0.0.1", 0))
        self.socket.listen(12)
        self.socket.settimeout(.2)
        self.port = self.socket.getsockname()[1]
        self.closed, self.lock = False, threading.Lock()
        self.records, self.threads = [], []
        self.recordOverflow = False
        self.contexts = {}
        for name, port, version, expected in TRIALS:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.minimum_version = context.maximum_version = getattr(ssl.TLSVersion, version.replace(".", "_"))
            context.options |= ssl.OP_NO_TICKET
            context.num_tickets = 0
            context.set_alpn_protocols(["http/1.1"])
            context.load_cert_chain(certificates.leaf, certificates.directory / "leaf.key")
            self.contexts[port] = context

    def start(self):
        thread = threading.Thread(target=self._accept, name="native-tls-probe-listener", daemon=True)
        self.threads.append(thread)
        thread.start()
        return self

    def _accept(self):
        while not self.closed:
            try:
                connection, address = self.socket.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            thread = threading.Thread(target=self._serve, args=(connection,), daemon=True)
            self.threads.append(thread)
            thread.start()

    def _serve(self, connection):
        record = dict(schema=1, trial=None, clientHello=None, tlsNegotiated=False, httpReceived=False)
        try:
            connection.settimeout(12)
            method, target, headers = read_header(connection)
            if method == "GET":
                query = urlsplit(target)
                require(query.path == "/__native_tls_evidence" and parse_qs(query.query) == {"run": [self.nonce], "source": [self.source]}, "control query differs")
                raw = (json.dumps(self.snapshot(), sort_keys=True) + "\n").encode()
                connection.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nCache-Control: no-store\r\nConnection: close\r\nContent-Length: " + str(len(raw)).encode() + b"\r\n\r\n" + raw)
                return
            require(method == "CONNECT", "uncontrolled proxy method")
            choices = [trial for trial in TRIALS if target == HOSTS[0] + ":" + str(trial[1])]
            require(len(choices) == 1, "uncontrolled TLS authority")
            name, port, version, expected = choices[0]
            record.update(trial=name, destinationPort=port, serverOnlyVersion=version, expectedSuccess=expected)
            connection.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            record["clientHello"] = peek_client_hello(connection)
            wrapped = self.contexts[port].wrap_socket(connection, server_side=True)
            connection = wrapped
            record.update(tlsNegotiated=True, negotiatedVersion=wrapped.version(), negotiatedAlpn=wrapped.selected_alpn_protocol(), sessionReused=wrapped.session_reused)
            method, target, headers = read_header(wrapped)
            query = urlsplit(target)
            require(method == "GET" and query.path == "/tls-probe" and parse_qs(query.query) == {"run": [self.nonce], "source": [self.source], "trial": [name]}, "TLS application request differs")
            require(headers.get("host") == HOSTS[0] + ":" + str(port), "controlled TLS Host differs")
            record["httpReceived"] = True
            raw = ("<!doctype html><meta charset=utf-8><link rel=icon href=data:,><title>Native TLS " + name + ":" + self.nonce + "</title><p>Controlled native TLS probe</p>").encode()
            wrapped.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nCache-Control: no-store\r\nConnection: close\r\nContent-Length: " + str(len(raw)).encode() + b"\r\n\r\n" + raw)
        except ssl.SSLError as error:
            reason = getattr(error, "reason", "")
            record.update(tlsErrorReason=reason if reason in ("UNSUPPORTED_PROTOCOL", "TLSV1_ALERT_PROTOCOL_VERSION", "NO_SHARED_CIPHER", "TLSV1_ALERT_UNKNOWN_CA", "SSLV3_ALERT_CERTIFICATE_UNKNOWN") else "OTHER_SSL_ERROR", errorType="SSLError")
        except Exception as error:
            record.update(errorType=type(error).__name__)
        finally:
            try:
                connection.close()
            except OSError:
                pass
            if record["trial"] is not None:
                with self.lock:
                    if len(self.records) < 32:
                        self.records.append(record)
                    else:
                        self.recordOverflow = True

    def snapshot(self):
        with self.lock:
            return json.loads(json.dumps(dict(schema=1, runNonce=self.nonce, sourceCommit=self.source,
                actualNativeWireCapture=True, upstreamConnections=0, forwardingImplemented=False,
                privateMaterialExported=False, certificateExceptionUsed=False,
                ticketsDisabled=True, h2OrH3PrefsModified=False, recordsOverflow=self.recordOverflow, records=self.records)))

    def close(self):
        self.closed = True
        self.socket.close()
        deadline=time.monotonic()+15
        for thread in self.threads:
            thread.join(timeout=max(0,deadline-time.monotonic()))
        require(not any(thread.is_alive() for thread in self.threads),"controlled TLS threads did not terminate")
