"""Offline network-boundary tests; only synthetic credentials and in-memory I/O."""
import copy
import io
import json
import socket
import ssl
import threading
import time
import unittest
from unittest.mock import patch

import responses_transport as t

SYNTHETIC_KEY = "synthetic-api-key-never-use-in-production"
BODY = b'{"status":"completed","output":[]}'


def payload(provider="openai"):
    value = {"model": "synthetic-test-model", "instructions": "Only synthetic evidence.",
             "input": [{"role": "user", "content": [{"type": "input_text", "text": "{}"}]}],
             "stream": False, "tools": [], "tool_choice": "none", "max_output_tokens": 1024,
             "text": {"format": {"type": "json_schema", "name": "test", "strict": True,
                                  "schema": {"type": "object", "properties": {}, "additionalProperties": False}}}}
    if provider == "openai":
        value["store"] = False
    else:
        del value["text"]["format"]["strict"]
    return value


class FakeSocket:
    def __init__(self, release=None):
        self.timeouts = []
        self.closed = False
        self.shutdowns = 0
        self.release = release
        self.sent = []

    def settimeout(self, value):
        self.timeouts.append(value)

    def shutdown(self, _):
        self.shutdowns += 1
        if self.release:
            self.release.set()

    def close(self):
        self.closed = True

    def connect(self, address):
        self.address = address

    def sendall(self, value):
        self.sent.append(value)


class FakeResponse:
    def __init__(self, body=BODY, status=200, headers=None, before_read=None):
        self.body = io.BytesIO(body)
        self.status = status
        self.headers = headers if headers is not None else [("Content-Type", "application/json"),
                                                            ("Content-Length", str(len(body)))]
        self.before_read = before_read
        self.reads = 0
        self.closed = False

    def getheaders(self):
        return self.headers

    def read1(self, size):
        self.reads += 1
        if self.before_read:
            self.before_read()
        return self.body.read(size)

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, host, port, *, timeout, context, state, response=None, hook=None, release=None):
        self.host, self.port, self.timeout, self.context, self.state = host, port, timeout, context, state
        self.sock = FakeSocket(release)
        self.response = response or FakeResponse()
        self.hook = hook
        self.requests = []
        self.connected = False
        self.closed = threading.Event()

    def connect(self):
        self.state.register(self.sock)
        if self.hook:
            self.hook("connect")
        self.connected = True

    def request(self, method, path, *, body, headers, encode_chunked):
        self.requests.append((method, path, body, headers, encode_chunked))
        if self.hook:
            self.hook("request")

    def getresponse(self):
        if self.hook:
            self.hook("headers")
        return self.response

    def close(self):
        self.sock.close()
        self.closed.set()


class TransportTests(unittest.TestCase):
    def setUp(self):
        # Any accidental real resolver call in ordinary tests fails immediately.
        self.no_network = patch("socket.getaddrinfo", side_effect=AssertionError("network prohibited by test"))
        self.no_network.start()
        self.addCleanup(self.no_network.stop)
        self.connections = []
        self.credential_calls = []

    def make(self, response=None, hook=None, release=None, credential=None, **options):
        def factory(*args, **kwargs):
            conn = FakeConnection(*args, response=response, hook=hook, release=release, **kwargs)
            self.connections.append(conn)
            return conn
        def synthetic_credential(provider):
            self.credential_calls.append(provider)
            self.assertTrue(self.connections[-1].connected)
            return SYNTHETIC_KEY
        return t.ResponsesTransport(credential or synthetic_credential, connection_factory=factory, **options)

    def send(self, transport, provider="openai", value=None, seconds=1):
        return transport.send(provider, payload(provider) if value is None else value,
                              deadline=time.monotonic() + seconds)

    def assertReason(self, reason, fn):
        with self.assertRaises(t.TransportError) as caught:
            fn()
        self.assertEqual(caught.exception.reason, reason)
        self.assertEqual(str(caught.exception), reason)

    def test_constructor_does_not_access_credentials_or_network(self):
        called = []
        t.ResponsesTransport(lambda _: called.append(1))
        self.assertFalse(called)

    def test_exact_fixed_https_request_for_each_provider(self):
        for provider in ("openai", "deepseek"):
            transport = self.make()
            self.assertEqual(self.send(transport, provider), json.loads(BODY))
            conn = self.connections[-1]
            host, port, path = t.ENDPOINTS[provider]
            self.assertEqual((conn.host, conn.port), (host, port))
            self.assertEqual(port, 443)
            self.assertEqual(conn.context.verify_mode, ssl.CERT_REQUIRED)
            self.assertTrue(conn.context.check_hostname)
            self.assertGreaterEqual(conn.context.minimum_version, ssl.TLSVersion.TLSv1_2)
            self.assertEqual(len(conn.requests), 1)
            method, actual_path, body, headers, chunked = conn.requests[0]
            self.assertEqual((method, actual_path), ("POST", path))
            self.assertFalse(chunked)
            self.assertEqual(headers["Authorization"], "Bearer " + SYNTHETIC_KEY)
            self.assertEqual(headers["Content-Length"], str(len(body)))
            self.assertEqual(headers["Accept-Encoding"], "identity")
            self.assertEqual(headers["Connection"], "close")
            self.assertEqual(json.loads(body), payload(provider))
            self.assertTrue(conn.closed.is_set())
            self.assertTrue(conn.response.closed)
        self.assertEqual(self.credential_calls, ["openai", "deepseek"])

    def test_invalid_inputs_never_connect_or_fetch_credentials(self):
        invalid = []
        for key, item in (("endpoint", "https://example.invalid"), ("stream", True),
                          ("tools", [{"type": "web_search"}]), ("store", True),
                          ("max_output_tokens", True), ("model", "bad\r\nvalue")):
            value = payload()
            value[key] = item
            invalid.append(value)
        value = payload()
        value["instructions"] = "x" * (t.MAX_REQUEST_BYTES + 1)
        invalid.append(value)
        for value in invalid:
            self.assertReason("invalid_request", lambda v=value: self.send(self.make(), value=v))
        transport = self.make()
        self.assertReason("invalid_request", lambda: transport.send("other", payload(), deadline=time.monotonic()+1))
        self.assertReason("invalid_request", lambda: transport.send("openai", payload(), deadline=float("inf")))
        self.assertReason("invalid_request", lambda: transport.send("openai", payload(), deadline=time.monotonic()+301))
        for huge in (10**1000, -(10**1000), 1e100):
            self.assertReason("invalid_request", lambda d=huge: transport.send("openai", payload(), deadline=d))
        self.assertFalse(self.connections)
        self.assertFalse(self.credential_calls)

    def test_input_is_only_single_user_json_text_and_provider_format_differs(self):
        changes = [
            ("input", [{"role": "user", "content": [{"type": "input_image", "image_url": "https://example.invalid/a"}]}]),
            ("input", [{"role": "user", "content": [{"type": "input_file", "file_url": "https://example.invalid/a"}]}]),
            ("input", [{"role": "system", "content": [{"type": "input_text", "text": "{}"}]}]),
            ("input", [{"role": "user", "content": [{"type": "input_text", "text": "not JSON"}]}]),
            ("input", [{"role": "user", "content": [{"type": "input_text", "text": "{}", "extra": 1}]}]),
            ("instructions", {"unexpected": "structure"}),
            ("text", {"format": {"type": "text"}}),
        ]
        for key, replacement in changes:
            value = payload()
            value[key] = replacement
            self.assertReason("invalid_request", lambda v=value: self.send(self.make(), value=v))
        value = payload("deepseek")
        value["text"]["format"]["strict"] = True
        self.assertReason("invalid_request", lambda: self.send(self.make(), provider="deepseek", value=value))
        value = payload()
        del value["text"]["format"]["strict"]
        self.assertReason("invalid_request", lambda: self.send(self.make(), value=value))
        self.assertFalse(self.connections)
        self.assertFalse(self.credential_calls)

    def test_request_schema_depth_is_bounded(self):
        value = payload()
        nested = value["text"]["format"]["schema"]
        for _ in range(80):
            nested["nested"] = {}
            nested = nested["nested"]
        self.assertReason("invalid_request", lambda: self.send(self.make(), value=value))
        self.assertFalse(self.connections)
        self.assertFalse(self.credential_calls)

    def test_request_schema_tree_budget_precedes_serialization(self):
        for nested in ({"enum": ["x" * 8192] * 40}, {"enum": [0] * (t.MAX_REQUEST_BYTES // 2 + 1)},
                       {"description": "x" * (t.MAX_REQUEST_BYTES + 1)}, {"minimum": 10**2000}):
            value = payload()
            value["text"]["format"]["schema"] = nested
            self.assertReason("invalid_request", lambda v=value: self.send(self.make(), value=v))
        self.assertFalse(self.connections)
        self.assertFalse(self.credential_calls)

    def test_redirect_and_upstream_errors_never_retry_or_read_error_body(self):
        for status in (301, 302, 307, 308, 401, 429, 500):
            response = FakeResponse(body=b"synthetic-secret-error-body", status=status,
                                    headers=[("Location", "https://elsewhere.invalid")])
            transport = self.make(response=response)
            self.assertReason("upstream_rejected", lambda: self.send(transport))
            self.assertEqual(response.reads, 0)
            self.assertEqual(len(self.connections[-1].requests), 1)

    def test_strict_utf8_json(self):
        values = (b"\xff", b"not json", b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}',
                  b'{"x":1e9999}', b'{"x":"\\ud800"}', b'[]', b'{"x":1} trailing',
                  b'{"x":' + b'[' * 65 + b'0' + b']' * 65 + b'}')
        for body in values:
            self.assertReason("invalid_response", lambda b=body: self.send(self.make(response=FakeResponse(body=b))))

    def test_response_headers_framing_encoding_and_sizes(self):
        cases = [
            [("Content-Type", "text/html")],
            [("Content-Type", "application/json"), ("Content-Encoding", "gzip")],
            [("Content-Type", "application/json"), ("Content-Type", "application/json")],
            [("Content-Type", "application/json"), ("Content-Length", "3"), ("Content-Length", "3")],
            [("Content-Type", "application/json"), ("Content-Length", "-1")],
            [("Content-Type", "application/json"), ("Content-Length", "10000000")],
            [("Content-Type", "application/json"), ("Transfer-Encoding", "gzip")],
            [("Content-Type", "application/json"), ("Transfer-Encoding", "chunked"), ("Content-Length", str(len(BODY)))],
            [("Content-Type", "application/json"), ("Content-Length", str(len(BODY) + 1))],
        ]
        for fields in cases:
            self.assertReason("invalid_response", lambda h=fields: self.send(self.make(response=FakeResponse(headers=h))))
        large = FakeResponse(body=b"x" * 1025, headers=[("Content-Type", "application/json")])
        self.assertReason("invalid_response", lambda: self.send(self.make(response=large, max_response_bytes=1024)))
        response = FakeResponse(headers=[("Content-Type", "Application/JSON; charset=UTF-8")])
        self.assertEqual(self.send(self.make(response=response)), json.loads(BODY))

    def test_bad_credentials_and_exception_are_not_reflected(self):
        for key in (None, "has whitespace", "bad\r\nHeader", "密钥", "x"*4099):
            self.assertReason("credentials_unavailable", lambda k=key: self.send(self.make(credential=lambda _: k)))
            self.assertFalse(self.connections[-1].requests)
        def raises(_):
            raise RuntimeError(SYNTHETIC_KEY)
        self.assertReason("credentials_unavailable", lambda: self.send(self.make(credential=raises)))
        def fail_connect(phase):
            if phase == "connect":
                raise OSError(SYNTHETIC_KEY)
        self.assertReason("network_failed", lambda: self.send(self.make(hook=fail_connect)))

    def test_deadline_bounds_request_headers_and_body_and_closes_socket(self):
        for phase in ("request", "headers", "body"):
            entered, release = threading.Event(), threading.Event()
            def block():
                entered.set()
                release.wait(1)
            hook = lambda actual, p=phase: block() if actual == p else None
            response = FakeResponse(before_read=block if phase == "body" else None)
            transport = self.make(response=response, hook=hook, release=release)
            start = time.monotonic()
            self.assertReason("deadline_exceeded", lambda: self.send(transport, seconds=0.10))
            self.assertLess(time.monotonic()-start, 0.5)
            self.assertTrue(entered.is_set())
            conn = self.connections[-1]
            self.assertGreater(conn.sock.shutdowns, 0)
            self.assertTrue(conn.closed.wait(0.5))
            self.assertEqual(len(conn.requests), 1)

    def test_deadline_in_credentials_never_posts(self):
        entered, release = threading.Event(), threading.Event()
        def credential(_):
            entered.set()
            release.wait(1)
            return SYNTHETIC_KEY
        transport = self.make(credential=credential, release=release)
        self.assertReason("deadline_exceeded", lambda: self.send(transport, seconds=0.10))
        self.assertTrue(entered.is_set())
        self.assertTrue(self.connections[-1].closed.wait(0.5))
        self.assertFalse(self.connections[-1].requests)

    def test_stuck_worker_keeps_capacity_bounded(self):
        entered, release = threading.Event(), threading.Event()
        def stuck(phase):
            if phase == "connect":
                entered.set()
                release.wait(1)  # Intentionally ignores socket close, like stuck resolver.
        transport = self.make(hook=stuck, max_workers=1)
        try:
            self.assertReason("deadline_exceeded", lambda: self.send(transport, seconds=0.10))
            self.assertTrue(entered.is_set())
            self.assertReason("capacity_reached", lambda: self.send(transport))
            self.assertEqual(len(self.connections), 1)
        finally:
            release.set()
        self.assertTrue(self.connections[-1].closed.wait(0.5))
        self.assertFalse(self.connections[-1].requests)

    def test_expired_deadline_does_not_start_worker(self):
        transport = self.make()
        self.assertReason("deadline_exceeded", lambda: transport.send("openai", payload(), deadline=time.monotonic()-1))
        self.assertFalse(self.connections)


class NativeConnectionTests(unittest.TestCase):
    def test_late_dns_never_creates_socket_or_posts(self):
        entered, release = threading.Event(), threading.Event()
        def resolve(*args, **kwargs):
            entered.set()
            release.wait(1)
            return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("192.0.2.1", 443))]
        transport = t.ResponsesTransport(lambda _: SYNTHETIC_KEY, max_workers=1)
        with patch("socket.getaddrinfo", side_effect=resolve), patch("socket.socket") as sockets:
            try:
                with self.assertRaises(t.TransportError) as caught:
                    transport.send("openai", payload(), deadline=time.monotonic()+0.10)
                self.assertEqual(caught.exception.reason, "deadline_exceeded")
                self.assertTrue(entered.is_set())
            finally:
                release.set()
            self.assertTrue(transport.slots.acquire(timeout=0.5))
            transport.slots.release()
            sockets.assert_not_called()

    def test_tls_socket_registered_before_handshake_and_cancelled(self):
        entered, release = threading.Event(), threading.Event()
        raw, secured = FakeSocket(), FakeSocket(release)
        def handshake():
            entered.set()
            release.wait(1)
        secured.do_handshake = handshake
        class Context:
            check_hostname = True
            verify_mode = ssl.CERT_REQUIRED
            def set_alpn_protocols(self, protocols):
                self.protocols = protocols
            def wrap_socket(self, sock, *, server_hostname, do_handshake_on_connect):
                self.host = server_hostname
                self.handshake_on_connect = do_handshake_on_connect
                return secured
        context = Context()
        addresses = [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("192.0.2.1", 443))]
        credential_calls = []
        transport = t.ResponsesTransport(lambda _: credential_calls.append(True), max_workers=1)
        with patch("socket.getaddrinfo", return_value=addresses), patch("socket.socket", return_value=raw), \
                patch("ssl.create_default_context", return_value=context):
            with self.assertRaises(t.TransportError) as caught:
                transport.send("openai", payload(), deadline=time.monotonic()+0.05)
            self.assertEqual(caught.exception.reason, "deadline_exceeded")
            self.assertTrue(entered.is_set())
            self.assertGreater(secured.shutdowns, 0)
            self.assertFalse(secured.sent)
            self.assertFalse(credential_calls)
            self.assertEqual(context.host, "api.openai.com")
            self.assertFalse(context.handshake_on_connect)
            self.assertTrue(transport.slots.acquire(timeout=0.5))
            transport.slots.release()

    def test_stdlib_response_parser_header_budget_and_chunked_body(self):
        class InputSocket:
            def __init__(self, value):
                self.value = value
            def makefile(self, mode):
                return io.BytesIO(self.value)
        for header in (b"X-A: " + b"a" * 9000 + b"\r\n", (b"X-A: " + b"a" * 1000 + b"\r\n") * 20):
            response = t._BoundedHTTPResponse(InputSocket(b"HTTP/1.1 200 OK\r\n" + header + b"\r\n{}"))
            with self.assertRaises(t.TransportError):
                response.begin()
            response.close()
        wire = b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nTransfer-Encoding: chunked\r\n\r\n2\r\n{}\r\n0\r\n\r\n"
        response = t._BoundedHTTPResponse(InputSocket(wire))
        response.begin()
        self.assertEqual(t._read_response(response, t._Call(time.monotonic()+1), 1024), {})
        response.close()


if __name__ == "__main__":
    unittest.main()
