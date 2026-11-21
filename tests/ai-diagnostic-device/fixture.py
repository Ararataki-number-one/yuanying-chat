"""Closed proxy for original-APK certificate-failure tests, in a new netns only.

No upstream socket is ever opened. Only the three fixed CONNECT authorities below
are admitted. A temporary self-signed leaf is presented, never installed in a
trust store. Even if a client unexpectedly trusts it, application data is never
read. TCP/OpenSSL may buffer received bytes; this module does not read/parse
HTTP authentication values or HTTP bodies. Counts are observations, not proof
that a particular Gecko callback or certificate-validation branch occurred.

The owner must create a Linux network namespace with only loopback, enable lo,
and start the emulator there. This module does not create namespaces or invoke
adb. The emulator uses 10.0.2.2 to reach the host namespace's loopback listener.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import os
import errno
import shutil
import socket
import socketserver
import ssl
import subprocess
import sys
import tempfile
import threading
import time


_PORT = 37891
_TARGETS = {
    b"fixture-control.test:443": "control",
    b"gecko-failure.test:443": "gecko",
    b"gateway-failure.test:443": "gateway",
}
_HEADER_NAMES = {b"host", b"user-agent", b"proxy-connection", b"connection", b"accept",
                 b"accept-language", b"accept-encoding", b"cache-control", b"pragma"}
_HEADER_DEADLINE = 5.0
_TLS_DEADLINE = 5.0
_GATEWAY_HANDSHAKE_DELAY = 2.0
_DESTINATIONS = ("control", "gecko", "gateway", "other")
_PHASES = (
    "requestLineParsed", "proxyRejected", "rejectedRequestLine", "rejectedHeaderName",
    "rejectedHeaderValue", "rejectedHeaderEnd", "connectAccepted", "connectResponseSent",
    "connectResponseFailed", "handshakeDelayed", "tlsSetupFailed", "handshakeStarted",
    "sniMatched", "sniRejected", "handshakeCompleted", "peerUnknownCa",
    "peerCertificateAlert", "tlsEof", "tlsReset", "tlsTimeout", "tlsOtherFailure",
)
_CONNECT_OK = b"HTTP/1.1 200 Connection Established\r\n\r\n"
_DENIED = b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"


class _Rejected(Exception):
    """Private fixed failure; never includes input bytes or exception details."""

    def __init__(self, category="malformed"):
        self.category = category
        self.destination = "other"
        self.request_type = "other"
        self.phase = "requestLine"
        self.blocked_timezone = False


def _require_isolated_netns():
    if sys.platform != "linux":
        raise RuntimeError("fixture_requires_isolated_linux_network_namespace")
    try:
        lines = Path("/proc/self/net/dev").read_text(encoding="ascii").splitlines()[2:]
        interfaces = {line.split(":", 1)[0].strip() for line in lines if ":" in line}
        if interfaces != {"lo"}:
            raise ValueError()
        # The owner creates the new netns. Check this process's routing only;
        # do not inspect another PID's namespace (which runuser cannot access).
        ipv4 = Path("/proc/self/net/route").read_text(encoding="ascii").splitlines()[1:]
        for line in ipv4:
            fields = line.split()
            if len(fields) < 8:
                raise ValueError()
            if fields[1] == "00000000" and fields[7] == "00000000" and int(fields[3], 16) & 1:
                raise ValueError()
        ipv6 = Path("/proc/self/net/ipv6_route").read_text(encoding="ascii").splitlines()
        for line in ipv6:
            fields = line.split()
            if len(fields) != 10:
                raise ValueError()
            # Linux may expose an unreachable default route on lo without UP.
            if fields[0] == "0" * 32 and fields[1] == "00" and int(fields[8], 16) & 1:
                raise ValueError()
    except (OSError, UnicodeError, ValueError):
        raise RuntimeError("fixture_requires_isolated_linux_network_namespace") from None


def _read_connect(sock, observe=None):
    state = {"destination": "other", "request_type": "other", "phase": "requestLine", "blocked_timezone": False}
    try:
        return _read_connect_impl(sock, state, observe)
    except (_Rejected, OSError) as error:
        rejected = error if isinstance(error, _Rejected) else _Rejected("io")
        rejected.destination = state["destination"]
        rejected.request_type = state["request_type"]
        rejected.phase = state["phase"]
        rejected.blocked_timezone = state["blocked_timezone"]
        raise rejected from None


def _read_connect_impl(sock, state, observe):
    """No buffered I/O: reject secret-bearing header names before their value.

    The blank line terminates reads exactly, so no pipelined HTTP body is read.
    A CONNECT request with any unrecognized header is rejected without its value.
    """
    deadline = time.monotonic() + _HEADER_DEADLINE
    remaining = 4096

    def byte():
        nonlocal remaining
        if remaining <= 0:
            raise _Rejected()
        timeout = deadline - time.monotonic()
        if timeout <= 0:
            raise _Rejected()
        sock.settimeout(timeout)
        value = sock.recv(1)
        remaining -= 1
        if len(value) != 1:
            raise _Rejected()
        return value

    def line(limit):
        value = bytearray()
        while True:
            part = byte()
            if part == b"\r":
                if byte() != b"\n":
                    raise _Rejected()
                return bytes(value)
            if not b" " <= part <= b"~" or len(value) >= limit:
                raise _Rejected()
            value.extend(part)

    request = line(128)
    method, separator, target_and_version = request.partition(b" ")
    authority, version_separator, version = target_and_version.partition(b" ")
    if method == b"CONNECT":
        state["request_type"] = "connect"
        state["destination"] = _TARGETS.get(authority, "other")
        state["blocked_timezone"] = authority == b"ipwho.is:443"
    elif method in (b"GET", b"HEAD", b"POST", b"PUT", b"PATCH", b"DELETE", b"OPTIONS", b"TRACE"):
        state["request_type"] = "http"
        scheme, divider, remainder = authority.partition(b"://")
        # Denial classification only; discard path/query immediately and keep
        # only a boolean. This hostname never enters the admitted target map.
        host = remainder.split(b"/", 1)[0].split(b"?", 1)[0].split(b"#", 1)[0]
        if divider and scheme in (b"http", b"https"):
            default_port = b":80" if scheme == b"http" else b":443"
            for fixed_authority, destination in _TARGETS.items():
                hostname = fixed_authority.removesuffix(b":443")
                if host in (hostname, hostname + default_port):
                    state["destination"] = destination
                    break
        state["blocked_timezone"] = bool(divider) and (
            (scheme == b"http" and host in (b"ipwho.is", b"ipwho.is:80")) or
            (scheme == b"https" and host in (b"ipwho.is", b"ipwho.is:443")))
    if observe is not None:
        observe(state["destination"], "requestLineParsed")
    if not separator or method != b"CONNECT" or authority not in _TARGETS:
        raise _Rejected("targetOrRequestLine")
    if not version_separator or version not in (b"HTTP/1.0", b"HTTP/1.1"):
        raise _Rejected("testTargetVersion")
    seen = set()
    for _ in range(16):
        state["phase"] = "headerName"
        first = byte()
        if first == b"\r":
            state["phase"] = "headerEnd"
            if byte() != b"\n" or b"host" not in seen:
                raise _Rejected()
            return _TARGETS[authority]
        name = bytearray()
        part = first
        while part != b":":
            if len(name) >= 32 or not (b"a" <= part.lower() <= b"z" or part == b"-"):
                raise _Rejected()
            name.extend(part.lower())
            part = byte()
        key = bytes(name)
        # Do not consume Authorization, Proxy-Authorization, Cookie, framing,
        # or any unknown header's value. No incoming header is ever logged.
        if key not in _HEADER_NAMES or key in seen:
            raise _Rejected("headerName")
        seen.add(key)
        state["phase"] = "headerValue"
        if key == b"host":
            # Both authority forms identify the same fixed HTTPS endpoint.
            if line(128).strip(b" ") not in (authority, authority.removesuffix(b":443")):
                raise _Rejected("host")
        else:
            # Discard bounded, printable nonsecret metadata without retaining it.
            for _ in range(513):
                part = byte()
                if part == b"\r":
                    if byte() != b"\n":
                        raise _Rejected()
                    break
                if not b" " <= part <= b"~":
                    raise _Rejected()
            else:
                raise _Rejected()
    raise _Rejected()


class Fixture:
    control_url = "https://fixture-control.test/"
    url = "https://gecko-failure.test/"
    proxy_host = "10.0.2.2"
    proxy_port = _PORT
    gateway_url = "https://gateway-failure.test/v1/diagnose"

    def __init__(self):
        self._lock = threading.Lock()
        self._serving = False
        self._destination_phases = {destination: {phase: 0 for phase in _PHASES}
                                    for destination in _DESTINATIONS}
        self._counts = {name: 0 for name in (
            "connectionsAccepted", "proxyRejected", "capacityRejected",
            "rejectTargetOrRequestLine", "rejectTestTargetVersion", "rejectHeaderName",
            "rejectHost", "rejectMalformed", "rejectIo",
            "controlConnectAccepted", "geckoConnectAccepted", "gatewayConnectAccepted",
            "deniedConnect", "deniedHttp", "deniedOtherRequest",
            "blockedTimezoneConnect", "blockedTimezoneHttp",
            "gatewayHandshakeDelayed", "tlsHandshakeStarted",
            "tlsHandshakeFailed", "tlsHandshakeCompleted", "connectionsClosed",
        )}

    def _count(self, key):
        with self._lock:
            self._counts[key] += 1

    def _observe(self, destination, phase):
        # Both keys are derived fixed enums. Never retain raw authority, SNI,
        # request line, headers, SSL reasons, peer addresses or exception text.
        with self._lock:
            self._destination_phases[destination][phase] += 1

    def host_self_test(self):
        """Explicit owned-control loopback probe; never trusts the test leaf.

        Call only inside serve(). This sends a fixed CONNECT and TLS handshake,
        but no HTTP application data. It does not test the emulator or Gecko.
        Server alert counters may settle shortly after the client result.
        """
        if not self._serving:
            raise RuntimeError("fixture_not_serving")
        _require_isolated_netns()
        deadline = time.monotonic() + 5.0
        raw = tls = None
        outcome = "loopbackOrProxyFailed"
        try:
            raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            raw.settimeout(max(0.001, deadline - time.monotonic()))
            raw.connect(("127.0.0.1", _PORT))
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError()
            raw.settimeout(remaining)
            raw.sendall(b"CONNECT fixture-control.test:443 HTTP/1.1\r\nHost: fixture-control.test:443\r\n\r\n")
            for expected in _CONNECT_OK:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError()
                raw.settimeout(remaining)
                if raw.recv(1) != bytes((expected,)):
                    return self._control_result(outcome)
            outcome = "tlsFailureUnclassified"
            # An empty client trust store is deliberate. No CA files, custom
            # roots or certificates are loaded, installed or bypassed.
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            tls = context.wrap_socket(raw, server_hostname="fixture-control.test",
                                      do_handshake_on_connect=False)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError()
            tls.settimeout(remaining)
            try:
                tls.do_handshake()
            except ssl.SSLCertVerificationError as error:
                # The generated leaf is self-signed. A hostname/date failure is
                # a different control failure, not proof of this expected case.
                outcome = "untrustedCertificateRejected" if error.verify_code == 18 else "otherCertificateVerificationRejected"
            else:
                outcome = "unexpectedHandshakeSuccess"
        except OSError:
            pass
        finally:
            for peer in (tls, raw):
                if peer is not None:
                    try:
                        peer.close()
                    except OSError:
                        pass
        return self._control_result(outcome)

    @staticmethod
    def _control_result(outcome):
        return {"status": "passed" if outcome == "untrustedCertificateRejected" else "failed",
                "outcome": outcome, "destination": "control", "httpApplicationBytesSent": 0,
                "trustStoresModified": False}

    def summary(self):
        with self._lock:
            return {
                "counts": dict(self._counts),
                "destinationPhases": {key: dict(value) for key, value in self._destination_phases.items()},
                "upstreamConnections": 0,
                "httpApplicationReads": 0,  # Compatibility: post-CONNECT only.
                "tlsApplicationReads": 0,
                "httpBodyReads": 0,
                "authenticationValueReads": 0,
                "trustStoresModified": False,
                "providerRequests": 0,
            }


def _tls_context(directory, fixture=None):
    executable = shutil.which("openssl")
    if executable is None:
        raise RuntimeError("fixture_requires_openssl")
    certificate = Path(directory) / "temporary-leaf.pem"
    private_key = Path(directory) / "temporary-key.pem"
    try:
        subprocess.run([
            executable, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
            "-subj", "/CN=gecko-failure.test",
            "-addext", "subjectAltName=DNS:fixture-control.test,DNS:gecko-failure.test,DNS:gateway-failure.test",
            "-keyout", str(private_key), "-out", str(certificate),
        ], check=True, timeout=20, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env={"PATH": os.defpath, "LC_ALL": "C", "OPENSSL_CONF": "/dev/null"})
        private_key.chmod(0o600)
        contexts = {}
        for authority, target in _TARGETS.items():
            hostname = authority.decode("ascii").split(":", 1)[0]
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.load_cert_chain(str(certificate), str(private_key))

            def check_sni(sock, server_name, initial_context, expected=hostname, destination=target):
                matched = server_name == expected
                if fixture is not None:
                    fixture._observe(destination, "sniMatched" if matched else "sniRejected")
                return None if matched else ssl.ALERT_DESCRIPTION_UNRECOGNIZED_NAME

            context.set_servername_callback(check_sni)
            contexts[target] = context
        return contexts
    except (OSError, subprocess.SubprocessError, ssl.SSLError):
        raise RuntimeError("fixture_certificate_setup_failed") from None


class _Server(socketserver.TCPServer):
    address_family = socket.AF_INET
    allow_reuse_address = False
    daemon_threads = False
    block_on_close = True
    request_queue_size = 8

    def __init__(self, fixture, context):
        self.fixture = fixture
        self.context = context
        self.stopping = threading.Event()
        self._slots = threading.BoundedSemaphore(8)
        self._active_lock = threading.Lock()
        self._active = set()
        self._workers = set()
        super().__init__(("127.0.0.1", _PORT), _Handler)

    def process_request(self, request, client_address):
        self.fixture._count("connectionsAccepted")
        if not self._slots.acquire(blocking=False):
            self.fixture._count("capacityRejected")
            self.shutdown_request(request)
            self.fixture._count("connectionsClosed")
            return
        with self._active_lock:
            if self.stopping.is_set():
                self._slots.release()
                self.shutdown_request(request)
                self.fixture._count("connectionsClosed")
                return
            self._active.add(request)
        worker = None
        try:
            worker = threading.Thread(target=self.process_request_thread,
                                      args=(request, client_address), daemon=False)
            with self._active_lock:
                self._workers.add(worker)
            worker.start()
        except Exception:
            with self._active_lock:
                self._workers.discard(worker)
            self._release(request)
            self.shutdown_request(request)
            raise

    def _release(self, request):
        with self._active_lock:
            self._active.discard(request)
        self._slots.release()
        self.fixture._count("connectionsClosed")

    def process_request_thread(self, request, client_address):
        try:
            self.finish_request(request, client_address)
        except Exception:
            self.handle_error(request, client_address)
        finally:
            try:
                self.shutdown_request(request)
            finally:
                try:
                    self._release(request)
                finally:
                    with self._active_lock:
                        self._workers.discard(threading.current_thread())

    def server_close(self):
        try:
            super().server_close()
        finally:
            with self._active_lock:
                workers = tuple(self._workers)
            for worker in workers:
                worker.join()

    def handle_error(self, request, client_address):
        # socketserver's default would print a traceback and input-associated
        # client addresses. This fixture intentionally has no request logs.
        pass

    def close_active(self):
        self.stopping.set()
        with self._active_lock:
            for sock in tuple(self._active):
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                try:
                    sock.close()
                except OSError:
                    pass


def _tls_failure_kind(error):
    # Only enumerated reason classes escape; raw OpenSSL text is discarded.
    reason = getattr(error, "reason", None)
    if reason == "TLSV1_ALERT_UNKNOWN_CA":
        return "peerUnknownCa"
    if reason in ("SSLV3_ALERT_BAD_CERTIFICATE", "SSLV3_ALERT_CERTIFICATE_UNKNOWN",
                  "SSLV3_ALERT_CERTIFICATE_EXPIRED", "SSLV3_ALERT_CERTIFICATE_REVOKED",
                  "SSLV3_ALERT_UNSUPPORTED_CERTIFICATE"):
        return "peerCertificateAlert"
    if isinstance(error, ssl.SSLEOFError) or reason == "UNEXPECTED_EOF_WHILE_READING":
        return "tlsEof"
    if isinstance(error, TimeoutError):
        return "tlsTimeout"
    if getattr(error, "errno", None) == errno.ECONNRESET:
        return "tlsReset"
    return "tlsOtherFailure"


class _Handler(socketserver.BaseRequestHandler):
    def handle(self):
        server = self.server
        fixture = server.fixture
        tls = None
        try:
            target = _read_connect(self.request, fixture._observe)
        except _Rejected as rejected:
            key = {"targetOrRequestLine": "rejectTargetOrRequestLine", "testTargetVersion": "rejectTestTargetVersion",
                   "headerName": "rejectHeaderName", "io": "rejectIo",
                   "host": "rejectHost", "malformed": "rejectMalformed"}.get(rejected.category)
            fixture._count(key or "rejectMalformed")
            fixture._count("proxyRejected")
            fixture._observe(rejected.destination, "proxyRejected")
            fixture._observe(rejected.destination, {
                "requestLine": "rejectedRequestLine", "headerName": "rejectedHeaderName",
                "headerValue": "rejectedHeaderValue", "headerEnd": "rejectedHeaderEnd",
            }[rejected.phase])
            if rejected.blocked_timezone:
                fixture._count("blockedTimezoneConnect" if rejected.request_type == "connect" else "blockedTimezoneHttp")
            if rejected.category == "targetOrRequestLine":
                fixture._count({"connect": "deniedConnect", "http": "deniedHttp",
                                "other": "deniedOtherRequest"}[rejected.request_type])
                # Empty, fixed denial only. Do not read headers or body to reply.
                try:
                    self.request.settimeout(1.0)
                    self.request.sendall(_DENIED)
                except OSError:
                    pass
            return
        fixture._count(target + "ConnectAccepted")
        fixture._observe(target, "connectAccepted")
        try:
            self.request.settimeout(_TLS_DEADLINE)
            self.request.sendall(_CONNECT_OK)
        except OSError:
            fixture._observe(target, "connectResponseFailed")
            return
        fixture._observe(target, "connectResponseSent")
        try:
            if target == "gateway":
                fixture._count("gatewayHandshakeDelayed")
                fixture._observe(target, "handshakeDelayed")
                if server.stopping.wait(_GATEWAY_HANDSHAKE_DELAY):
                    return
            if server.stopping.is_set():
                return
            tls = server.context[target].wrap_socket(self.request, server_side=True,
                                                     do_handshake_on_connect=False)
            with server._active_lock:
                server._active.discard(self.request)
                if server.stopping.is_set():
                    return
                server._active.add(tls)
            tls.settimeout(_TLS_DEADLINE)
            fixture._count("tlsHandshakeStarted")
            fixture._observe(target, "handshakeStarted")
            tls.do_handshake()
            fixture._count("tlsHandshakeCompleted")
            fixture._observe(target, "handshakeCompleted")
            # Never read TLS application data, including path, auth or body.
        except OSError as error:
            fixture._count("tlsHandshakeFailed")
            fixture._observe(target, "tlsSetupFailed" if tls is None else _tls_failure_kind(error))
        finally:
            if tls is not None:
                with server._active_lock:
                    server._active.discard(tls)
                tls.close()


@contextmanager
def serve():
    """Serve the fixed negative fixtures; stop and destroy temporary material."""
    _require_isolated_netns()
    fixture = Fixture()
    with tempfile.TemporaryDirectory(prefix="pocketchat-negative-tls-") as directory:
        context = _tls_context(directory, fixture)
        server = _Server(fixture, context)
        try:
            worker = threading.Thread(target=server.serve_forever,
                                      kwargs={"poll_interval": 0.05}, daemon=True)
            worker.start()
        except Exception:
            try:
                server.close_active()
            finally:
                server.server_close()
            raise RuntimeError("fixture_listener_start_failed") from None
        fixture._serving = True
        try:
            yield fixture
        finally:
            fixture._serving = False
            try:
                server.close_active()
            finally:
                try:
                    server.shutdown()
                finally:
                    try:
                        server.server_close()
                    finally:
                        worker.join(timeout=2)
