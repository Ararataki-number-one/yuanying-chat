"""Pure synthetic unit checks. No sockets, emulator, certificate or CI startup."""
import importlib.util
from pathlib import Path
import ssl
import threading
import types
import unittest
from unittest import mock

_SPEC = importlib.util.spec_from_file_location("negative_fixture", Path(__file__).with_name("fixture.py"))
fixture = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(fixture)


class BytesSocket:
    def __init__(self, payload):
        self.remaining = payload
        self.sizes = []
        self.sent = []
        self.closed = False

    def recv(self, size):
        self.sizes.append(size)
        if size != 1:
            raise AssertionError("buffered read")
        chunk, self.remaining = self.remaining[:size], self.remaining[size:]
        return chunk

    def settimeout(self, value):
        if not 0 < value <= 5:
            raise AssertionError("unbounded timeout")

    def sendall(self, value):
        self.sent.append(value)

    def close(self):
        self.closed = True


def request(host=b"gecko-failure.invalid:443", headers=b"", tail=b""):
    return b"CONNECT " + host + b" HTTP/1.1\r\nHost: " + host + b"\r\n" + headers + b"\r\n" + tail


class SyntheticTests(unittest.TestCase):
    def test_import_has_no_network_or_paid_dependencies(self):
        source = Path(fixture.__file__).read_text()
        for forbidden in ("create_connection", "getaddrinfo", "urlopen", "requests.",
                          "responses_transport", "assistant_gateway", "adb ", "load_verify_locations"):
            self.assertNotIn(forbidden, source)

    def test_both_exact_targets_leave_body_unread(self):
        for authority, label in fixture._TARGETS.items():
            sock = BytesSocket(request(authority, b"User-Agent: synthetic\r\nProxy-Connection: keep-alive\r\n", b"BODY_SENTINEL"))
            self.assertEqual(label, fixture._read_connect(sock))
            self.assertEqual(b"BODY_SENTINEL", sock.remaining)
            self.assertEqual({1}, set(sock.sizes))

    def test_secret_and_unknown_headers_rejected_before_value(self):
        for name in (b"Authorization", b"Proxy-Authorization", b"Cookie", b"Content-Length",
                     b"Transfer-Encoding", b"X-Unknown"):
            sock = BytesSocket(request(headers=name + b": SECRET_SENTINEL\r\n"))
            with self.assertRaises(fixture._Rejected):
                fixture._read_connect(sock)
            self.assertTrue(sock.remaining.startswith(b" SECRET_SENTINEL\r\n"))

    def test_unregistered_authorities_methods_and_versions_rejected(self):
        candidates = [request(host=host) for host in (
            b"example.com:443", b"127.0.0.1:443", b"gecko-failure.invalid:80",
            b"gecko-failure.invalid.:443", b"GECKO-FAILURE.INVALID:443",
            b"u@gecko-failure.invalid:443", b"gecko-failure.invalid:443/path")]
        candidates += [request().replace(b"CONNECT", b"GET"), request().replace(b"HTTP/1.1", b"HTTP/1.0")]
        for payload in candidates:
            with self.subTest(payload=payload), self.assertRaises(fixture._Rejected):
                fixture._read_connect(BytesSocket(payload))

    def test_header_structure_rejected(self):
        payloads = [request(headers=b"Host: gecko-failure.invalid:443\r\n"),
                    request().replace(b"Host: gecko-failure.invalid:443", b"Host: gateway-failure.invalid:443"),
                    request().replace(b"Host: gecko-failure.invalid:443\r\n", b""),
                    request(headers=b" User-Agent: folded\r\n"), request().replace(b"\r\n", b"\n"),
                    request(headers=b"User-Agent: a\tb\r\n"), request(headers=b"User-Agent: \xff\r\n"),
                    request(headers=b"User-Agent: " + b"x" * 513 + b"\r\n"),
                    request(headers=b"x" * 33 + b": value\r\n"), request()[:-2]]
        for payload in payloads:
            with self.subTest(payload=payload), self.assertRaises(fixture._Rejected):
                fixture._read_connect(BytesSocket(payload))

    def test_header_deadline_is_total(self):
        sock = BytesSocket(request())
        ticks = iter([0, 1, 2, 6])
        with mock.patch.object(fixture.time, "monotonic", side_effect=lambda: next(ticks)):
            with self.assertRaises(fixture._Rejected):
                fixture._read_connect(sock)
        self.assertEqual(2, len(sock.sizes))

    @staticmethod
    def _proc_contents(path, **kwargs):
        values = {
            "/proc/self/net/dev": "header\nheader\n lo: data\n",
            "/proc/self/net/route": "header\n",
            "/proc/self/net/ipv6_route": "0" * 32 + " 00 " + "0" * 32 + " 00 " + "0" * 32 + " ffffffff 00000001 00000000 00200200 lo\n",
        }
        return values[str(path)]

    def test_namespace_guard_uses_only_this_process_and_accepts_loopback(self):
        with mock.patch.object(fixture.Path, "read_text", autospec=True,
                               side_effect=self._proc_contents), mock.patch.object(
                fixture.os, "stat", side_effect=AssertionError("cross-process stat forbidden")):
            fixture._require_isolated_netns()

    def test_namespace_guard_rejects_extra_interfaces(self):
        with mock.patch.object(fixture.Path, "read_text", return_value="header\nheader\n lo: data\n eth0: data\n"):
            with self.assertRaisesRegex(RuntimeError, "fixture_requires_isolated"):
                fixture._require_isolated_netns()

    def test_namespace_guard_rejects_default_routes(self):
        defaults = {
            "/proc/self/net/route": "header\nlo 00000000 00000000 0001 0 0 0 00000000 0 0 0\n",
            "/proc/self/net/ipv6_route": "0" * 32 + " 00 " + "0" * 32 + " 00 " + "0" * 32 + " 00000001 00000001 00000000 00000001 lo\n",
        }
        for target, value in defaults.items():
            def content(path, **kwargs):
                return value if str(path) == target else self._proc_contents(path, **kwargs)
            with mock.patch.object(fixture.Path, "read_text", autospec=True, side_effect=content):
                with self.assertRaisesRegex(RuntimeError, "fixture_requires_isolated"):
                    fixture._require_isolated_netns()

    def _handler(self, *, handshake_error=None, target="gecko", stop_on_delay=False):
        raw = BytesSocket(request((target + "-failure.invalid:443").encode()))
        tls = types.SimpleNamespace(settimeout=mock.Mock(), close=mock.Mock(),
                                    do_handshake=mock.Mock(side_effect=handshake_error))
        # SimpleNamespace is not hashable; use a standalone fake TLS object.
        class Tls:
            settimeout = tls.settimeout
            close = tls.close
            do_handshake = tls.do_handshake
        session = Tls()
        context = types.SimpleNamespace(wrap_socket=mock.Mock(return_value=session))
        stop = mock.Mock()
        stop.wait.return_value = stop_on_delay
        stop.is_set.return_value = False
        details = fixture.Fixture()
        server = types.SimpleNamespace(fixture=details, context={target: context}, stopping=stop,
                                       _active_lock=threading.Lock(), _active={raw})
        fixture._Handler(raw, ("127.0.0.1", 1), server)
        return details.summary(), raw, session, stop

    def test_handshake_failure_is_bounded_without_application_read(self):
        result, raw, tls, _ = self._handler(handshake_error=ssl.SSLError("synthetic"))
        self.assertEqual(1, result["counts"]["tlsHandshakeFailed"])
        self.assertEqual(0, result["httpApplicationReads"])
        self.assertEqual([b"HTTP/1.1 200 Connection Established\r\n\r\n"], raw.sent)
        tls.close.assert_called_once()

    def test_unexpected_handshake_success_closes_without_application_read(self):
        result, _, tls, _ = self._handler()
        self.assertEqual(1, result["counts"]["tlsHandshakeCompleted"])
        self.assertEqual(0, result["httpApplicationReads"])
        tls.close.assert_called_once()

    def test_gateway_delay_interrupts_before_handshake(self):
        result, _, tls, stop = self._handler(target="gateway", stop_on_delay=True)
        stop.wait.assert_called_once_with(2.0)
        self.assertEqual(1, result["counts"]["gatewayHandshakeDelayed"])
        self.assertEqual(0, result["counts"]["tlsHandshakeStarted"])
        tls.do_handshake.assert_not_called()

    def test_certificate_contexts_require_matching_sni_without_trust_setup(self):
        contexts = []

        class Context:
            def __init__(self, protocol):
                self.protocol = protocol
                self.minimum_version = None
                self.loaded = None
                self.callback = None
                contexts.append(self)

            def load_cert_chain(self, cert, key):
                self.loaded = (cert, key)

            def set_servername_callback(self, callback):
                self.callback = callback

        with mock.patch.object(fixture.shutil, "which", return_value="/synthetic/openssl"), mock.patch.object(
                fixture.subprocess, "run") as run, mock.patch.object(fixture.Path, "chmod"), mock.patch.object(
                fixture.ssl, "SSLContext", Context):
            result = fixture._tls_context("/synthetic/private")
        self.assertEqual({"gecko", "gateway"}, set(result))
        for target, context in result.items():
            self.assertIsNone(context.callback(None, target + "-failure.invalid", None))
            self.assertEqual(ssl.ALERT_DESCRIPTION_UNRECOGNIZED_NAME,
                             context.callback(None, "example.com", None))
            self.assertEqual(ssl.ALERT_DESCRIPTION_UNRECOGNIZED_NAME,
                             context.callback(None, None, None))
        self.assertEqual("/dev/null", run.call_args.kwargs["env"]["OPENSSL_CONF"])
        self.assertEqual(20, run.call_args.kwargs["timeout"])

    def test_capacity_and_stopping_reject_without_worker_or_socket_leak(self):
        for stopped in (False, True):
            server = object.__new__(fixture._Server)
            server.fixture = fixture.Fixture()
            server.stopping = threading.Event()
            server._active_lock = threading.Lock()
            server._active = set()
            server._slots = threading.BoundedSemaphore(1)
            if stopped:
                server.stopping.set()
            else:
                server._slots.acquire()
            server.shutdown_request = mock.Mock()
            raw = BytesSocket(b"")
            with mock.patch.object(fixture.threading, "Thread",
                                   side_effect=AssertionError("must not start worker")):
                server.process_request(raw, ("127.0.0.1", 1))
            server.shutdown_request.assert_called_once_with(raw)
            self.assertEqual(set(), server._active)
            self.assertEqual(1, server.fixture.summary()["counts"]["connectionsClosed"])
            if stopped:
                self.assertTrue(server._slots.acquire(blocking=False))

    def test_request_worker_start_failure_releases_capacity_and_avoids_join(self):
        server = object.__new__(fixture._Server)
        server.fixture = fixture.Fixture()
        server.stopping = threading.Event()
        server._active_lock = threading.Lock()
        server._active = set()
        server._workers = set()
        server._slots = threading.BoundedSemaphore(1)
        server.shutdown_request = mock.Mock()
        worker = mock.Mock()
        worker.start.side_effect = RuntimeError("synthetic thread limit")
        raw = BytesSocket(b"")
        with mock.patch.object(fixture.threading, "Thread", return_value=worker):
            with self.assertRaises(RuntimeError):
                server.process_request(raw, ("127.0.0.1", 1))
        self.assertEqual(set(), server._active)
        self.assertEqual(set(), server._workers)
        self.assertTrue(server._slots.acquire(blocking=False))
        server.shutdown_request.assert_called_once_with(raw)
        worker.join.assert_not_called()

    def test_listener_thread_start_failure_closes_without_shutdown_wait(self):
        server = mock.Mock()
        worker = mock.Mock()
        worker.start.side_effect = RuntimeError("synthetic thread limit")
        directory = mock.MagicMock()
        directory.__enter__.return_value = "/synthetic/private"
        with mock.patch.object(fixture, "_require_isolated_netns"), mock.patch.object(
                fixture.tempfile, "TemporaryDirectory", return_value=directory), mock.patch.object(
                fixture, "_tls_context"), mock.patch.object(fixture, "_Server", return_value=server), mock.patch.object(
                fixture.threading, "Thread", return_value=worker):
            with self.assertRaisesRegex(RuntimeError, "fixture_listener_start_failed"):
                with fixture.serve():
                    self.fail("must not yield")
        server.close_active.assert_called_once()
        server.server_close.assert_called_once()
        server.shutdown.assert_not_called()
        directory.__exit__.assert_called_once()

    def test_close_active_interrupts_registered_socket(self):
        server = object.__new__(fixture._Server)
        server.stopping = threading.Event()
        server._active_lock = threading.Lock()
        raw = mock.Mock()
        server._active = {raw}
        server.close_active()
        self.assertTrue(server.stopping.is_set())
        raw.shutdown.assert_called_once_with(fixture.socket.SHUT_RDWR)
        raw.close.assert_called_once()

    def test_summary_is_safe_copy(self):
        details = fixture.Fixture()
        snapshot = details.summary()
        snapshot["counts"]["proxyRejected"] = 999
        self.assertEqual(0, details.summary()["counts"]["proxyRejected"])
        self.assertEqual(0, snapshot["providerRequests"])
        self.assertFalse(snapshot["trustStoresModified"])

    def test_fixed_external_interface_and_non_daemon_cleanup(self):
        self.assertEqual("https://gecko-failure.invalid/", fixture.Fixture.url)
        self.assertEqual("https://gateway-failure.invalid/v1/diagnose", fixture.Fixture.gateway_url)
        self.assertEqual("10.0.2.2", fixture.Fixture.proxy_host)
        self.assertEqual(37891, fixture.Fixture.proxy_port)
        self.assertFalse(fixture._Server.daemon_threads)
        self.assertFalse(fixture._Server.allow_reuse_address)


if __name__ == "__main__":
    unittest.main()
