#!/usr/bin/env python3
"""Acceptance-only workers; all provider connections are in-memory doubles."""
import argparse
import hashlib
import http.client
import ipaddress
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[2]
PROTO = ROOT / "prototype/ai-diagnostics"
sys.path.insert(0, str(PROTO))
sys.path.insert(0, str(ROOT / "tests"))
PYTHON_MODULES = ("test_diagnostic_gateway", "test_responses_diagnosis", "test_responses_transport",
                  "test_responses_ledger", "test_provider_gateway")
HISTORY_TESTS = ("test_old_commit_gap_and_individual_protections_are_observed",
                 "test_exact_inverse_preserves_original_reading_guard")


class LoopbackOnly:
    """Python defense in depth; not an OS firewall or a JVM network claim."""
    def __init__(self):
        self.blocked = 0
        self.original_resolve = socket.getaddrinfo
        self.original_connect = socket.socket.connect
        self.original_connect_ex = socket.socket.connect_ex
        self.original_bind = socket.socket.bind

    def check(self, address):
        try:
            allowed = isinstance(address, tuple) and ipaddress.ip_address(address[0]).is_loopback
        except (ValueError, TypeError):
            allowed = False
        if not allowed:
            self.blocked += 1
            raise OSError("acceptance permits numeric loopback only")

    def install(self):
        owner = self
        def resolve(host, port, *args, **kwargs):
            owner.check((host, port))
            return owner.original_resolve(host, port, *args, **kwargs)
        def connect(sock, address):
            owner.check(address)
            return owner.original_connect(sock, address)
        def connect_ex(sock, address):
            owner.check(address)
            return owner.original_connect_ex(sock, address)
        def bind(sock, address):
            owner.check(address)
            return owner.original_bind(sock, address)
        socket.getaddrinfo = resolve
        socket.socket.connect = connect
        socket.socket.connect_ex = connect_ex
        socket.socket.bind = bind


def suite(stage, history):
    loader = unittest.defaultTestLoader
    if stage == "python":
        return loader.loadTestsFromNames(PYTHON_MODULES)
    if stage == "page-bridge":
        prefix = "profile_page_bridge_lifecycle_test.PageBridgeLifecycleTests."
        names = ["test_current_primary_navigation_dispatch_boundary",
                 "test_authoritative_commit_and_other_document_orderings"]
        if history == "full":
            names += list(HISTORY_TESTS)
        return loader.loadTestsFromNames([prefix + name for name in names])
    if stage == "window-selection":
        return loader.loadTestsFromName("profile_gecko_window_selection_test")
    raise ValueError("unknown stage")


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def wire(args, guard):
    from diagnostic_gateway import LocalServer
    from provider_gateway import ProviderGateway
    from responses_ledger import Ledger
    from responses_transport import ENDPOINTS, ResponsesTransport
    from test_responses_transport import FakeConnection, FakeResponse

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=False)
    original = json.loads(args.fixture.read_text(encoding="utf-8"))
    hypothesis = {"hypotheses": [
        {"hypothesis": "NAME_RESOLUTION_UNAVAILABLE", "tabEvidenceId": "T1",
         "evidence": [{"eventId": "E2", "signal": "DNS_FAILURE"}], "steps": ["REVIEW_CONNECTION_STATUS"]},
        {"hypothesis": "CERTIFICATE_TRUST_OR_VALIDITY", "tabEvidenceId": "T3",
         "evidence": [{"eventId": "E2", "signal": "CERTIFICATE_REJECTED"}], "steps": ["REVIEW_DEVICE_DATE_TIME"]},
    ]}
    connections, credential_calls = [], []
    def credential(provider):
        credential_calls.append(provider)
        return "synthetic-upstream-credential-" + provider
    def connection(host, port, **kwargs):
        provider = next(name for name, endpoint in ENDPOINTS.items() if endpoint[:2] == (host, port))
        reasoning = {"id": "synthetic-reasoning", "type": "reasoning"}
        if provider == "openai":
            reasoning["summary"] = []
        else:
            reasoning["content"] = [{"type": "reasoning_text", "text": "synthetic-private-reasoning-must-not-render"}]
        envelope = {"status": "completed", "error": None, "incomplete_details": None, "output": [reasoning,
            {"id": "synthetic-message", "type": "message", "role": "assistant", "status": "completed",
             "content": [{"type": "output_text", "text": json.dumps(hypothesis)}]}]}
        value = FakeConnection(host, port, **kwargs, response=FakeResponse(encode(envelope)))
        connections.append(value)
        return value

    transport = ResponsesTransport(credential, connection_factory=connection)
    require(transport.connection_factory is connection, "in-memory provider factory required")
    token = "synthetic-acceptance-relay-token-0001"
    # Admission flags exercise production composition only with the explicit
    # synthetic factory above. They do not change deployment/device acceptance.
    with tempfile.TemporaryDirectory(prefix="ai-acceptance-ledger-") as folder:
        ledger = Ledger(Path(folder) / "synthetic.sqlite", b"synthetic-acceptance-ledger-key-000001", initialize=True)
        gateway = ProviderGateway(token, enable_paid_requests=True,
            gateway_endpoint="https://relay.fixture.invalid/v1/diagnose",
            device_route_accepted=True, provider_egress_accepted=True,
            ledger=ledger, transport=transport,
            models={"openai": "gpt-fixture", "deepseek": "deepseek-fixture"}, deadline_seconds=2)
        server = LocalServer(0, gateway)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        thread.start()
        cases = []
        try:
            for provider, identity in (("openai", "e2f2ac37-d254-480d-bf95-d358998ca001"),
                                       ("deepseek", "e2f2ac37-d254-480d-bf95-d358998ca002")):
                value = dict(original, provider=provider)
                body = encode(value)
                headers = {"Host": "relay.fixture.invalid", "Authorization": "Bearer " + token,
                           "Content-Type": "application/json", "Content-Length": str(len(body)),
                           "Idempotency-Key": identity}
                def post():
                    client = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                    try:
                        client.request("POST", "/v1/diagnose", body=body, headers=headers)
                        response = client.getresponse()
                        reply = response.read(65537)
                        require(len(reply) <= 65536, "bounded gateway reply")
                        return response.status, dict(response.getheaders()), reply
                    finally:
                        client.close()
                status, response_headers, reply = post()
                require(status == 200, "production loopback gateway rejected synthetic provider case")
                require(json.loads(reply) == {"version": 2, "diagnosis": hypothesis}, "structured reply differs")
                require(response_headers.get("Cache-Control") == "no-store", "gateway reply must not be cached")
                require(b"synthetic-private-reasoning" not in reply, "provider reasoning must not reach client")
                require(len(connections) == len(cases) + 1, "exactly one synthetic provider call per case")
                upstream = connections[-1]
                expected_host, expected_port, expected_path = ENDPOINTS[provider]
                require((upstream.host, upstream.port) == (expected_host, expected_port), "provider host drift")
                require(len(upstream.requests) == 1, "no provider retries")
                method, path, sent_body, sent_headers, chunked = upstream.requests[0]
                sent = json.loads(sent_body)
                require((method, path, chunked) == ("POST", expected_path, False), "provider HTTP request differs")
                require(sent_headers["Authorization"] == "Bearer synthetic-upstream-credential-" + provider,
                        "synthetic credential scope mismatch")
                require(json.loads(sent["input"][0]["content"][0]["text"]) == {"evidence": value["evidence"]},
                        "evidence changed between Java snapshot and provider input")
                require(("store" in sent) == (provider == "openai"), "provider store contract differs")
                require(("strict" in sent["text"]["format"]) == (provider == "openai"), "provider format contract differs")
                repeat_status, _, repeat_body = post()
                require(repeat_status == 409 and json.loads(repeat_body) == {"reason": "result_not_retained"},
                        "durable duplicate must not invoke provider again")
                require(len(connections) == len(cases) + 1, "duplicate reached provider")
                request_file = out / (provider + "-confirmed-request.json")
                response_file = out / (provider + "-gateway-response.json")
                request_file.write_bytes(body)
                response_file.write_bytes(reply)
                command = [sys.executable, "-B", str(ROOT / "tests/ai-diagnostic-gateway-host/run.py"),
                           "--java-home", str(args.java_home), "--json-jar", str(args.json_jar),
                           "--wire-case", str(request_file), str(response_file)]
                java = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=90)
                (out / (provider + "-java.stdout.log")).write_text(java.stdout, encoding="utf-8")
                (out / (provider + "-java.stderr.log")).write_text(java.stderr, encoding="utf-8")
                require(java.returncode == 0, "Android JVM parser rejected exact gateway wire; see Java logs")
                cases.append({"provider": provider, "providerConnection": "IN_MEMORY_HTTPS_DOUBLE",
                              "providerHost": expected_host, "providerPath": expected_path,
                              "providerCalls": 1, "gatewayHttpStatus": status, "duplicateHttpStatus": repeat_status,
                              "requestSha256": hashlib.sha256(body).hexdigest(),
                              "replySha256": hashlib.sha256(reply).hexdigest(), "javaParserPassed": True})
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
    require(credential_calls == ["openai", "deepseek"], "synthetic credentials obtained more than once")
    require(guard.blocked == 0, "unexpected non-loopback network attempt")
    report = {"schema": 1, "status": "passed", "cases": cases, "actualLoopbackHttp": True,
              "actualGatewayTls": False, "actualProviderTls": False, "actualProviderRequestsSent": False,
              "actualAndroidExecution": False, "syntheticGatewayAdmissionEnabled": True,
              "deploymentConfigurationChanged": False, "sourceFixtureSha256": hashlib.sha256(args.fixture.read_bytes()).hexdigest()}
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("python", "page-bridge", "window-selection", "cross-wire"))
    parser.add_argument("--history", choices=("current", "full"), default="current")
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--java-home", type=Path)
    parser.add_argument("--json-jar", type=Path)
    args = parser.parse_args()
    guard = LoopbackOnly()
    guard.install()
    if args.stage == "cross-wire":
        if any(value is None for value in (args.fixture, args.output_dir, args.java_home, args.json_jar)):
            parser.error("cross-wire requires fixture/output-dir/java-home/json-jar")
        wire(args, guard)
        return
    result = unittest.TextTestRunner(verbosity=2).run(suite(args.stage, args.history))
    success = result.wasSuccessful() and guard.blocked == 0 and not result.skipped
    print(json.dumps({"schema": 1, "status": "passed" if success else "failed", "tests": result.testsRun,
                      "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
                      "nonLoopbackAttemptsBlocked": guard.blocked, "actualProviderRequestsSent": False,
                      "actualAndroidExecution": False, "stage": args.stage}))
    raise SystemExit(0 if success else 1)


if __name__ == "__main__":
    main()
