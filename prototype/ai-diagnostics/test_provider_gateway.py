"""Exercise the real gateway composition with a local HTTPS connection double."""
import json
from pathlib import Path
import tempfile
import threading
import unittest

from diagnostic_gateway import DEMO_TOKEN
from provider_gateway import ProviderGateway, approved_authority
from responses_ledger import Ledger
from responses_transport import ResponsesTransport
from test_responses_transport import FakeConnection, FakeResponse

TOKEN = "synthetic-private-relay-fixture-0001"
KEY = "ed3e63e8-e2e3-4926-bbd3-ccf4e5922458"
LEDGER_KEY = b"synthetic-ledger-scope-fixture-00000001"
ENDPOINT = "https://relay.fixture.invalid/v1/diagnose"
HOST = "relay.fixture.invalid"
FIXTURE = Path(__file__).with_name("fixtures") / "java-wire.json"


class ProviderGatewayTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "history.sqlite"
        self.ledger = Ledger(self.path, LEDGER_KEY, initialize=True)
        self.connections = []
        self.credentials = []
        self.wire = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.body = self.encode(self.wire)
        self.diagnosis = {"hypotheses": [{
            "hypothesis": "NAME_RESOLUTION_UNAVAILABLE",
            "tabEvidenceId": "T1",
            "evidence": [{"eventId": "E2", "signal": "DNS_FAILURE"}],
            "steps": ["REVIEW_CONNECTION_STATUS"],
        }]}
        self.factory_hook = None
        self.upstream_status = 200

    @staticmethod
    def encode(value):
        return json.dumps(value, separators=(",", ":")).encode("utf-8")

    def get_credential(self, provider):
        self.credentials.append(provider)
        return "synthetic-upstream-credential-" + provider

    def connection(self, host, port, **kwargs):
        response = {"status": "completed", "output": [{"type": "message", "role": "assistant",
            "status": "completed", "content": [{"type": "output_text", "text": json.dumps(self.diagnosis)}]}]}
        conn = FakeConnection(host, port, **kwargs,
                              response=FakeResponse(self.encode(response), self.upstream_status),
                              hook=self.factory_hook)
        self.connections.append(conn)
        return conn

    def gateway(self, *, enabled=True, accepted=True, egress=True, ledger=None, models=None, deadline=2.0):
        transport = ResponsesTransport(self.get_credential, connection_factory=self.connection)
        return ProviderGateway(TOKEN, enable_paid_requests=enabled, gateway_endpoint=ENDPOINT,
                               device_route_accepted=accepted, provider_egress_accepted=egress,
                               ledger=ledger or self.ledger,
                               transport=transport, models=models or {"openai": "gpt-fixture", "deepseek": "deepseek-fixture"},
                               deadline_seconds=deadline)

    def post(self, gateway, *, body=None, token=TOKEN, host=HOST, key=KEY):
        if body is None:
            body = self.body
        headers = [("Authorization", "Bearer " + token), ("Host", host), ("Idempotency-Key", key),
                   ("Content-Type", "application/json"), ("Content-Length", str(len(body)))]
        return gateway.dispatch("POST", "/v1/diagnose", headers, body)

    def test_default_disabled_never_obtains_credentials(self):
        result = self.post(ProviderGateway(TOKEN))
        self.assertEqual((result.status, result.body), (503, {"reason": "paid_requests_disabled"}))
        self.assertFalse(self.credentials or self.connections)
        with self.assertRaises(ValueError):
            self.gateway(accepted=False)
        with self.assertRaises(ValueError):
            self.gateway(egress=False)
        with self.assertRaises(ValueError):
            ProviderGateway(DEMO_TOKEN, enable_paid_requests=True, device_route_accepted=True, provider_egress_accepted=True)

    def test_only_operator_authority_and_auth_are_admitted(self):
        candidate = self.gateway()
        self.assertEqual(self.post(candidate, host="other.fixture.invalid").status, 421)
        self.assertEqual(self.post(candidate, token="wrong").status, 401)
        self.assertFalse(self.credentials or self.connections)
        self.assertEqual(approved_authority(ENDPOINT), (HOST, 443))
        for invalid in ("http://relay.fixture.invalid/v1/diagnose", "https://x@relay.fixture.invalid/v1/diagnose",
                        "https://relay.fixture.invalid#x/v1/diagnose", "https://relay.fixture.invalid?x=/v1/diagnose",
                        "https://relay.fixture.invalid/v1/diagnose?x=1", "https://relay.fixture.invalid:0/v1/diagnose"):
            with self.subTest(endpoint=invalid), self.assertRaises(ValueError):
                approved_authority(invalid)

    def test_both_providers_have_fixed_wires_and_structured_response(self):
        candidate = self.gateway()
        for provider, host, path, key in [
            ("openai", "api.openai.com", "/v1/responses", KEY),
            ("deepseek", "api.deepseek.com", "/responses", "e736231e-f735-415a-aa31-41679dbc04eb"),
        ]:
            with self.subTest(provider=provider):
                result = self.post(candidate, body=self.encode(dict(self.wire, provider=provider)), key=key)
                self.assertEqual((result.status, result.body), (200, {"version": 2, "diagnosis": self.diagnosis}))
                connection = self.connections[-1]
                self.assertEqual((connection.host, connection.port), (host, 443))
                self.assertEqual(len(connection.requests), 1)
                method, sent_path, sent_body, headers, chunked = connection.requests[0]
                sent = json.loads(sent_body)
                self.assertEqual((method, sent_path, chunked), ("POST", path, False))
                self.assertEqual(headers["Authorization"], "Bearer synthetic-upstream-credential-" + provider)
                self.assertEqual(sent["model"], ("gpt" if provider == "openai" else provider) + "-fixture")
                self.assertEqual(json.loads(sent["input"][0]["content"][0]["text"]), {"evidence": self.wire["evidence"]})
                self.assertEqual(sent["tools"], [])
                self.assertEqual(sent["tool_choice"], "none")
                self.assertEqual("store" in sent, provider == "openai")
                self.assertEqual("strict" in sent["text"]["format"], provider == "openai")

    def test_restart_duplicate_and_model_change_do_not_reissue(self):
        self.assertEqual(self.post(self.gateway()).status, 200)
        reopened = Ledger(self.path, LEDGER_KEY)
        self.assertEqual(self.post(self.gateway(ledger=reopened)).body, {"reason": "result_not_retained"})
        updated = self.gateway(ledger=reopened, models={"openai": "gpt-updated"})
        self.assertEqual(self.post(updated).body, {"reason": "idempotency_conflict"})
        self.assertEqual(self.credentials, ["openai"])

    def test_provider_refusal_or_invalid_ref_is_terminal(self):
        self.diagnosis["hypotheses"][0]["tabEvidenceId"] = "T2"
        candidate = self.gateway()
        self.assertEqual(self.post(candidate).body, {"reason": "invalid_provider_response"})
        self.assertEqual(self.post(candidate).body, {"reason": "request_outcome_unknown"})
        self.assertEqual(len(self.connections), 1)

    def test_redirect_is_not_followed_or_reflected(self):
        self.upstream_status = 307
        candidate = self.gateway()
        result = self.post(candidate)
        self.assertEqual((result.status, result.body), (502, {"reason": "provider_unavailable"}))
        self.assertEqual(len(self.connections), 1)
        self.assertEqual(self.connections[0].response.reads, 0)

    def test_no_fault_returns_empty_hypotheses_without_upstream(self):
        self.wire["evidence"][0]["events"] = []
        self.wire["evidence"][1]["events"] = []
        result = self.post(self.gateway(), body=self.encode(self.wire))
        self.assertEqual((result.status, result.body), (200, {"version": 2, "diagnosis": {"hypotheses": []}}))
        self.assertFalse(self.connections or self.credentials)

    def test_inflight_and_timeout_are_bounded_and_never_reissued(self):
        started, release = threading.Event(), threading.Event()

        def block_reply(phase):
            if phase == "headers":
                started.set()
                release.wait(1.5)

        self.factory_hook = block_reply
        candidate = self.gateway(deadline=0.25)
        responses = []
        worker = threading.Thread(target=lambda: responses.append(self.post(candidate)), daemon=True)
        worker.start()
        try:
            self.assertTrue(started.wait(1.0))
            self.assertEqual(self.post(candidate).body, {"reason": "request_in_progress"})
            worker.join(1.0)
            self.assertFalse(worker.is_alive())
            self.assertEqual(responses[0].body, {"reason": "deadline_exceeded"})
            self.assertEqual(self.post(candidate).body, {"reason": "request_outcome_unknown"})
            self.assertEqual(len(self.connections), 1)
        finally:
            release.set()

    def test_ledger_repeat_is_blocked_when_rate_limit_is_reached(self):
        limited = Ledger(self.path, LEDGER_KEY, rate_limit=1)
        candidate = self.gateway(ledger=limited)
        self.assertEqual(self.post(candidate).status, 200)
        self.assertEqual(self.post(candidate, key="aeb55589-f337-4d5a-803e-d61c3a05f6fd").status, 429)
        self.assertEqual(len(self.connections), 1)


if __name__ == "__main__":
    unittest.main()
