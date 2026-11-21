"""Real TLS only on 127.0.0.1, with temporary synthetic certificates and payloads.

No device trust changes, production credentials, provider imports or external
connections. A custom CA is loaded only into this test client's SSLContext.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

import acceptance_https_gateway as acceptance

TOKEN = "synthetic-acceptance-token-00000000000001"
HOST = "synthetic.acceptance.invalid"
ENDPOINT = "https://" + HOST + "/v1/diagnose"
KEY = "12345678-1234-4234-8234-123456789abc"
OTHER_KEY = "12345678-1234-4234-8234-123456789abd"
ROOT = Path(__file__).resolve().parent


def fixture():
    return json.loads((ROOT / "fixtures/java-wire.json").read_text(encoding="utf-8"))


def body(value=None):
    return json.dumps(fixture() if value is None else value, separators=(",", ":")).encode("utf-8")


def headers(raw, host=HOST, token=TOKEN, key=KEY):
    return [("Host", host), ("Authorization", "Bearer " + token), ("Idempotency-Key", key),
            ("Content-Type", "application/json"), ("Content-Length", str(len(raw)))]


def packet(raw=None, path="/v1/diagnose", method="POST", selected_headers=None):
    raw = body() if raw is None else raw
    lines = [method + " " + path + " HTTP/1.1"]
    lines += [name + ": " + value for name, value in (headers(raw) if selected_headers is None else selected_headers)]
    return ("\r\n".join(lines) + "\r\n\r\n").encode("ascii") + raw


@contextlib.contextmanager
def running(cert, key, gateway=None, connections=8):
    gateway = gateway or acceptance.AcceptanceGateway(TOKEN, ENDPOINT)
    context = acceptance.tls_context(cert, key, HOST)
    server = acceptance.AcceptanceServer(0, gateway, context, max_connections=connections)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=3)


def trusted(cert):
    context = ssl.create_default_context(cafile=str(cert))
    assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
    return context


def connect(server, context, hostname=HOST):
    raw = socket.create_connection(("127.0.0.1", server.server_port), timeout=3)
    try:
        return context.wrap_socket(raw, server_hostname=hostname)
    except Exception:
        raw.close()
        raise


def exchange(server, context, request=None):
    with connect(server, context) as connection:
        connection.sendall(packet() if request is None else request)
        chunks = []
        while True:
            chunk = connection.recv(8192)
            if not chunk:
                break
            chunks.append(chunk)
    wire = b"".join(chunks)
    head, raw = wire.split(b"\r\n\r\n", 1)
    status = int(head.split(b" ", 2)[1])
    return status, json.loads(raw), head


class ProtocolTests(unittest.TestCase):
    def test_authority_and_exact_path_configuration(self):
        self.assertEqual(acceptance.approved_authority(ENDPOINT), (HOST, 443))
        self.assertEqual(acceptance.approved_authority("https://SYNTHETIC.acceptance.invalid:443/v1/diagnose"), (HOST, 443))
        for endpoint in ("http://" + HOST + "/v1/diagnose", ENDPOINT + "?x=1", ENDPOINT + "/",
                "https://user@" + HOST + "/v1/diagnose", "https://api.openai.com/v1/diagnose",
                "https://api.deepseek.com/v1/diagnose", "https://" + HOST + ":0/v1/diagnose",
                "https://" + HOST + ":65536/v1/diagnose", "https://bad..invalid/v1/diagnose"):
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                acceptance.approved_authority(endpoint)

    def test_version_two_fixed_enum_reply_no_model(self):
        gate = acceptance.AcceptanceGateway(TOKEN, ENDPOINT)
        for provider in ("openai", "deepseek"):
            value = fixture(); value["provider"] = provider; raw = body(value)
            result = gate.dispatch("POST", "/v1/diagnose", headers(raw, key=KEY if provider == "openai" else OTHER_KEY), raw)
            self.assertEqual(result.status, 200)
            self.assertEqual(set(result.body), {"version", "diagnosis"})
            self.assertEqual(result.body["version"], 2)
            choices = result.body["diagnosis"]["hypotheses"]
            self.assertEqual([entry["tabEvidenceId"] for entry in choices], ["T1", "T3"])
            for choice in choices:
                self.assertEqual(choice["hypothesis"], "INSUFFICIENT_EVIDENCE")
                self.assertEqual(choice["steps"], ["REVIEW_LOCAL_DIAGNOSTICS"])
        value = fixture()
        for entry in value["evidence"]:
            entry["events"] = []
        raw = body(value); gate = acceptance.AcceptanceGateway(TOKEN, ENDPOINT)
        self.assertEqual(gate.dispatch("POST", "/v1/diagnose", headers(raw), raw).body,
                         {"version": 2, "diagnosis": {"hypotheses": []}})

    def test_whitelist_auth_host_and_replay_limits(self):
        raw = body(); gate = acceptance.AcceptanceGateway(TOKEN, ENDPOINT, capacity=1)
        first = gate.dispatch("POST", "/v1/diagnose", headers(raw), raw)
        self.assertEqual(first.status, 200)
        first.body["diagnosis"]["hypotheses"].clear()
        self.assertTrue(gate.dispatch("POST", "/v1/diagnose", headers(raw), raw).body["diagnosis"]["hypotheses"])
        self.assertEqual(gate.counts()["replayed"], 1)
        self.assertEqual(gate.dispatch("POST", "/v1/diagnose", headers(raw, key=OTHER_KEY), raw).status, 503)
        changed = body(dict(fixture(), provider="deepseek"))
        self.assertEqual(gate.dispatch("POST", "/v1/diagnose", headers(changed), changed).status, 409)
        self.assertEqual(gate.dispatch("POST", "/v1/diagnose", headers(raw, host="other.invalid"), raw).status, 421)
        self.assertEqual(gate.dispatch("POST", "/v1/diagnose", headers(raw, token="invalid"), raw).status, 401)
        self.assertEqual(gate.dispatch("POST", "/v1/diagnose", headers(raw)+[("Host", HOST)], raw).status, 400)
        for key in ("url", "pageText", "cookie", "deviceId", "environmentId", "instructions"):
            private = fixture(); private[key] = "synthetic-private-not-loggable"
            raw_private = body(private)
            self.assertEqual(gate.dispatch("POST", "/v1/diagnose", headers(raw_private), raw_private).status, 400)

    def test_bounded_delay_and_in_progress_and_counts_only(self):
        received = threading.Event(); release = threading.Event(); counts = []
        gate = acceptance.AcceptanceGateway(TOKEN, ENDPOINT, response_delay_ms=1500, count_sink=counts.append)
        raw = body(); results = []
        def pause(seconds):
            self.assertEqual(seconds, 1.5)
            received.set(); self.assertTrue(release.wait(3))
        with mock.patch.object(acceptance.time, "sleep", side_effect=pause):
            worker = threading.Thread(target=lambda: results.append(gate.dispatch("POST", "/v1/diagnose", headers(raw), raw)))
            worker.start(); self.assertTrue(received.wait(3))
            self.assertEqual(gate.dispatch("POST", "/v1/diagnose", headers(raw), raw).status, 409)
            release.set(); worker.join(3)
        self.assertEqual(results[0].status, 200)
        for count in counts:
            self.assertEqual(set(count), {"received", "completed", "replayed", "rejected"})
            self.assertTrue(all(type(n) is int for n in count.values()))
        text = io.StringIO()
        with contextlib.redirect_stdout(text):
            acceptance.print_counts(gate.counts())
        self.assertNotIn(TOKEN, text.getvalue()); self.assertNotIn(KEY, text.getvalue())
        for delay in (-1, 3001, True, 0.5):
            with self.assertRaises(ValueError):
                acceptance.AcceptanceGateway(TOKEN, ENDPOINT, response_delay_ms=delay)

    def test_private_token_file_no_env_or_demo_default(self):
        with tempfile.TemporaryDirectory(prefix="acceptance-token-") as directory:
            token = Path(directory)/"test.token"; token.write_text(TOKEN + "\n"); token.chmod(0o600)
            self.assertEqual(acceptance.read_test_token(token), TOKEN)
            token.chmod(0o644)
            with self.assertRaises(ValueError):
                acceptance.read_test_token(token)
            token.chmod(0o600); token.write_text(acceptance.DEMO_TOKEN)
            with self.assertRaises(ValueError):
                acceptance.read_test_token(token)
            link = Path(directory)/"link"; link.symlink_to(token)
            with self.assertRaises(OSError):
                acceptance.read_test_token(link)

    def test_import_and_dispatch_cannot_load_paid_modules_or_make_outbound_connections(self):
        script = r"""
import builtins, json, socket, sys
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in {'provider_gateway','responses_transport','responses_ledger'}:
        raise AssertionError('paid module import attempted')
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
def denied(*args, **kwargs):
    raise AssertionError('outbound connection attempted')
socket.create_connection = denied
socket.socket.connect = denied
socket.socket.connect_ex = denied
socket.getfqdn = denied
socket.gethostbyaddr = denied
socket.gethostbyname = denied
socket.getaddrinfo = denied
import acceptance_https_gateway as a
value = json.loads(open('fixtures/java-wire.json', encoding='utf-8').read())
raw = json.dumps(value).encode()
headers = [('Host','synthetic.acceptance.invalid'),('Authorization','Bearer synthetic-acceptance-token-00000000000001'),
    ('Idempotency-Key','12345678-1234-4234-8234-123456789abc'),('Content-Type','application/json'),('Content-Length',str(len(raw)))]
result = a.AcceptanceGateway('synthetic-acceptance-token-00000000000001','https://synthetic.acceptance.invalid/v1/diagnose').dispatch('POST','/v1/diagnose',headers,raw)
assert result.status == 200
import ssl
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
server = a.AcceptanceServer(0, a.AcceptanceGateway('synthetic-acceptance-token-00000000000001','https://synthetic.acceptance.invalid/v1/diagnose'), context)
assert server.server_address[0] == server.server_name == '127.0.0.1'
server.server_close()
assert not {'provider_gateway' ,'responses_transport','responses_ledger'} & set(sys.modules)
print('synthetic-only')
"""
        result = subprocess.run([sys.executable, "-B", "-c", script], cwd=ROOT, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "synthetic-only")


class RealLoopbackTlsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        openssl = shutil.which("openssl")
        if openssl is None:
            raise RuntimeError("openssl is required for real loopback TLS acceptance")
        cls.temp = tempfile.TemporaryDirectory(prefix="acceptance-tls-")
        cls.cert, cls.key = cls.make_certificate(openssl, "correct", HOST)
        cls.wrong_cert, cls.wrong_key = cls.make_certificate(openssl, "wrong", "other.synthetic.invalid")

    @classmethod
    def make_certificate(cls, openssl, name, hostname):
        directory = Path(cls.temp.name); cert = directory/(name + ".pem"); key = directory/(name + ".key")
        completed = subprocess.run([openssl, "req", "-x509", "-newkey", "rsa:2048", "-sha256", "-nodes", "-days", "1",
            "-subj", "/CN="+hostname, "-addext", "subjectAltName=DNS:"+hostname,
            "-keyout", str(key), "-out", str(cert)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        if completed.returncode:
            raise RuntimeError("synthetic TLS certificate generation failed")
        key.chmod(0o600)
        return cert, key

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_real_tls_requires_trusted_certificate(self):
        with running(self.cert, self.key) as server:
            self.assertEqual(server.server_address[0], "127.0.0.1")
            with self.assertRaises(ssl.SSLCertVerificationError):
                connect(server, ssl.create_default_context())
            status, result, head = exchange(server, trusted(self.cert))
            self.assertEqual(status, 200); self.assertEqual(result["version"], 2)
            self.assertIn(b"X-PocketChat-Acceptance: synthetic-no-provider", head)
            self.assertIn(b"Cache-Control: no-store", head)

    def test_real_tls_wrong_certificate_hostname_is_rejected(self):
        # SNI matches the pinned name; the trusted certificate SAN intentionally
        # does not. This proves actual client hostname verification, not SNI denial.
        with running(self.wrong_cert, self.wrong_key) as server:
            with self.assertRaises(ssl.SSLCertVerificationError):
                connect(server, trusted(self.wrong_cert))

    def test_real_tls_sni_host_duplicate_headers_and_raw_path(self):
        with running(self.cert, self.key) as server:
            with self.assertRaises(ssl.SSLError):
                connect(server, trusted(self.cert), hostname="other.synthetic.invalid")
            raw = body()
            cases = [(packet(selected_headers=headers(raw, host="other.invalid")), 421),
                     (packet(selected_headers=headers(raw)+[("Host", HOST)]), 400),
                     (packet(selected_headers=headers(raw)+[("Authorization", "Bearer " + TOKEN)]), 400),
                     (packet(selected_headers=headers(raw)+[("Content-Length", str(len(raw)))]), 400),
                     (packet(selected_headers=headers(raw)+[("Transfer-Encoding", "chunked")]), 400),
                     (packet(path="//v1/diagnose"), 404), (packet(path="/v1/diagnose?x=1"), 404),
                     (packet(path="https://"+HOST+"/v1/diagnose"), 404), (packet(method="GET"), 405)]
            for request, expected in cases:
                with self.subTest(expected=expected):
                    self.assertEqual(exchange(server, trusted(self.cert), request)[0], expected)

    def test_slow_handshake_does_not_block_accept_loop(self):
        with running(self.cert, self.key, connections=2) as server:
            slow = socket.create_connection(("127.0.0.1", server.server_port), timeout=3)
            try:
                status, _, _ = exchange(server, trusted(self.cert))
                self.assertEqual(status, 200)
            finally:
                slow.close()

    def test_cancelled_tls_client_no_body_or_authorization_logs(self):
        gate = acceptance.AcceptanceGateway(TOKEN, ENDPOINT, response_delay_ms=80)
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            with running(self.cert, self.key, gateway=gate) as server:
                connection = connect(server, trusted(self.cert))
                connection.sendall(packet()); connection.close()
                deadline = time.monotonic() + 3
                while gate.counts()["completed"] == 0 and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertEqual(gate.counts()["completed"], 1)
                # Local processing can finish after caller cancellation; no delivery claim.
                status, _, _ = exchange(server, trusted(self.cert))
                self.assertEqual(status, 200); self.assertEqual(gate.counts()["replayed"], 1)
        self.assertEqual(output.getvalue(), ""); self.assertEqual(errors.getvalue(), "")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {"status": "passed" if result.wasSuccessful() else "failed", "tests": result.testsRun,
              "failures": len(result.failures), "errors": len(result.errors), "actualLoopbackTlsExecution": True if result.wasSuccessful() else None,
              "defaultTrustRejectedSyntheticCertificate": result.wasSuccessful(),
              "clientOnlyCaTrustAndHostnameChecks": result.wasSuccessful(),
              "actualDeviceExecution": False, "actualProviderExecution": False,
              "paidClientImported": False if result.wasSuccessful() else None,
              "externalNetworkRequests": False if result.wasSuccessful() else None, "deviceTrustModified": False}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
