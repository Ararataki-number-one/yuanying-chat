"""Synthetic-only contract tests. No outbound requests, sockets or real credentials."""
import copy
import io
import json
import threading
import unittest
from email.message import Message
from pathlib import Path
from types import SimpleNamespace

import diagnostic_gateway as g

KEY = "12345678-1234-4234-8234-123456789abc"
OTHER_KEY = "12345678-1234-4234-8234-123456789abd"


def fixture(provider="openai"):
    return {"version": 1, "provider": provider, "evidence": [{
        "schema": 1, "engine": "GECKO", "tabEvidenceId": "T1",
        "scope": "TAB_CALLBACK_OBSERVATIONS", "navigationAttribution": "UNKNOWN",
        "events": [{"id": "E1", "kind": "LOAD_START", "signal": "UNKNOWN",
                    "code": None, "category": None, "elapsedMs": 0},
                   {"id": "E2", "kind": "LOAD_ERROR", "signal": "DNS_FAILURE",
                    "code": 1, "category": 2, "elapsedMs": 123}]}]}


def raw(value):
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode()


def headers(body, key=KEY, token=g.DEMO_TOKEN):
    return [("Authorization", "Bearer " + token), ("Idempotency-Key", key),
            ("Content-Type", "application/json"), ("Content-Length", str(len(body)))]


def request(gateway, value=None, key=KEY):
    body = raw(fixture() if value is None else value)
    return gateway.dispatch("POST", "/v1/diagnose", headers(body, key), body)


class ContractTests(unittest.TestCase):
    def test_both_provider_fixtures(self):
        for provider in ("openai", "deepseek"):
            value = fixture(provider)
            payload = g.build_responses_request(value)
            self.assertEqual(payload["tools"], [])
            self.assertEqual(payload["tool_choice"], "none")
            self.assertTrue(payload["text"]["format"]["strict"])
            self.assertNotIn("evidence", payload["instructions"])
            self.assertEqual("store" in payload, provider == "openai")
            self.assertNotIn("api_key", payload)
            result = request(g.Gateway(), value)
            self.assertEqual(result.status, 200)
            self.assertEqual(set(result.body), {"reply"})
            self.assertIn("T1/E2", result.body["reply"])
            self.assertIn("导航归属 UNKNOWN", result.body["reply"])
            self.assertIn("可能原因（未证实", result.body["reply"])

    def test_production_java_journal_wire_fixture(self):
        fixture_path = Path(__file__).parent / "fixtures" / "java-wire.json"
        value = json.loads(fixture_path.read_text(encoding="utf-8"))
        g.validate_request(value)
        result = request(g.Gateway(), value)
        self.assertEqual(result.status, 200)
        self.assertIn("[T1]", result.body["reply"])
        self.assertIn("[T3]", result.body["reply"])
        self.assertNotIn("[T2]", result.body["reply"])
        self.assertLessEqual(len(result.body["reply"]), 6000)

    def test_empty_event_list_is_not_proof_of_success(self):
        value = fixture()
        value["evidence"][0]["events"] = []
        result = request(g.Gateway(), value)
        self.assertEqual(result.status, 200)
        self.assertIn("不能证明页面无故障", result.body["reply"])

    def test_extra_keys_privacy_and_schema_are_rejected(self):
        values = []
        for key in ("url", "domain", "pageText", "cookies", "environmentId", "endpoint"):
            value = fixture()
            value[key] = "synthetic-private-placeholder"
            values.append(value)
        value = fixture()
        value["evidence"][0]["title"] = "synthetic-title"
        values.append(value)
        value = fixture()
        value["evidence"][0]["events"][0]["message"] = "synthetic-page-instruction"
        values.append(value)
        for value in values:
            with self.subTest(value=value):
                self.assertEqual(request(g.Gateway(), value).status, 400)

    def test_strict_type_and_enum_matrix(self):
        changes = [(("version",), True), (("provider",), []),
                   (("evidence",), []), (("evidence", 0, "schema"), True),
                   (("evidence", 0, "engine"), "CHROMIUM"),
                   (("evidence", 0, "navigationAttribution"), "CONFIRMED"),
                   (("evidence", 0, "tabEvidenceId"), "T2147483648"),
                   (("evidence", 0, "tabEvidenceId"), "T01"),
                   (("evidence", 0, "events", 1, "elapsedMs"), 3600001),
                   (("evidence", 0, "events", 1, "elapsedMs"), True),
                   (("evidence", 0, "events", 1, "code"), -1),
                   (("evidence", 0, "events", 1, "category"), None),
                   (("evidence", 0, "events", 1, "code"), 2**31),
                   (("evidence", 0, "events", 1, "signal"), "CONTENT_CRASH"),
                   (("evidence", 0, "events", 0, "signal"), "TIMEOUT"),
                   (("evidence", 0, "events", 0, "code"), 1),
                   (("evidence", 0, "events", 1, "id"), "E0")]
        for path, replacement in changes:
            value = fixture()
            target = value
            for part in path[:-1]:
                target = target[part]
            target[path[-1]] = replacement
            with self.subTest(path=path, replacement=replacement):
                self.assertEqual(request(g.Gateway(), value).status, 400)

    def test_missing_native_code_requires_unknown_signal(self):
        value = fixture()
        event = value["evidence"][0]["events"][1]
        event["code"] = event["category"] = None
        self.assertEqual(request(g.Gateway(), value).status, 400)
        event["signal"] = "UNKNOWN"
        self.assertEqual(request(g.Gateway(), value).status, 200)

    def test_duplicates_and_limits(self):
        value = fixture()
        value["evidence"] *= 2
        self.assertEqual(request(g.Gateway(), value).status, 400)
        value = fixture()
        value["evidence"][0]["events"].append(copy.deepcopy(value["evidence"][0]["events"][0]))
        self.assertEqual(request(g.Gateway(), value).status, 400)
        value = fixture()
        value["evidence"][0]["events"] *= 9
        self.assertEqual(request(g.Gateway(), value).status, 400)
        value = fixture()
        value["evidence"] = [dict(copy.deepcopy(value["evidence"][0]), tabEvidenceId=f"T{i}") for i in range(1, 5)]
        self.assertEqual(request(g.Gateway(), value).status, 400)

    def test_same_event_id_on_different_tabs_is_unambiguous(self):
        value = fixture()
        value["evidence"].append(dict(copy.deepcopy(value["evidence"][0]), tabEvidenceId="T2"))
        result = request(g.Gateway(), value)
        self.assertEqual(result.status, 200)
        self.assertIn("T1/E2", result.body["reply"])
        self.assertIn("[T2]", result.body["reply"])
        self.assertEqual(result.body["reply"].count("[E2]"), 2)

    def test_largest_legal_snapshot_reply_bound(self):
        value = fixture()
        value["evidence"] = []
        for tab in range(2147483645, 2147483648):
            entry = fixture()["evidence"][0]
            entry["tabEvidenceId"] = f"T{tab}"
            entry["events"] = [{"id": f"E{9999999999999999980+i}", "kind": "LOAD_ERROR",
                "signal": sorted(g.LOAD_SIGNALS)[i % 5], "code": 2147483647,
                "category": 2147483647, "elapsedMs": 3600000} for i in range(16)]
            value["evidence"].append(entry)
        result = request(g.Gateway(), value)
        self.assertEqual(result.status, 200)
        self.assertLessEqual(len(result.body["reply"]), 6000)

    def test_malformed_json_never_reaches_client(self):
        called = []
        gateway = g.Gateway(client=lambda *_: called.append(True))
        for body in (b'{"version":1,"version":1}', b'\xff', b'{"version":NaN}', b'['*1200):
            self.assertEqual(gateway.dispatch("POST", "/v1/diagnose", headers(body), body).status, 400)
        self.assertFalse(called)

    def test_invalid_response_no_refusal_tool_incomplete_or_wrong_evidence(self):
        value = fixture()
        good = g.SyntheticResponses()("openai", g.build_responses_request(value))
        variants = [None, {"status": "incomplete", "output": []}]
        for part in ({"type": "refusal", "refusal": "synthetic"}, {"type": "function_call", "name": "anything"}):
            response = copy.deepcopy(good)
            response["output"][0]["content"] = [part]
            variants.append(response)
        response = copy.deepcopy(good)
        response["output"].append({"type": "function_call"})
        variants.append(response)
        for ref in ({"tabEvidenceId": "T99", "eventId": "E2", "assessment": "DNS_FAILURE"},
                    {"tabEvidenceId": "T1", "eventId": "E2", "assessment": "TIMEOUT"}):
            response = copy.deepcopy(good)
            response["output"][0]["content"][0]["text"] = json.dumps({"observations": [ref]})
            variants.append(response)
        for response in variants:
            with self.subTest(response=response):
                result = request(g.Gateway(client=lambda *_, r=response: r), value)
                self.assertEqual(result, g.error(502, "invalid_response"))


class ProtocolTests(unittest.TestCase):
    def test_auth_path_method_uuid_and_size(self):
        body = raw(fixture())
        gateway = g.Gateway()
        self.assertEqual(gateway.dispatch("POST", "/v1/diagnose", headers(body, token="bad"), body).status, 401)
        self.assertEqual(gateway.dispatch("POST", "/v1/diagnose?x=1", headers(body), body).status, 404)
        self.assertEqual(gateway.dispatch("GET", "/v1/diagnose", headers(body), body).status, 405)
        self.assertEqual(gateway.dispatch("POST", "/v1/diagnose", headers(body, key=KEY.upper()), body).status, 400)
        self.assertEqual(gateway.dispatch("POST", "/v1/diagnose", headers(body) + [("Authorization", "other")], body).status, 400)
        self.assertEqual(gateway.dispatch("POST", "/v1/diagnose", headers(body) + [("Transfer-Encoding", "chunked")], body).status, 400)
        large = b" " * (g.MAX_BODY + 1)
        self.assertEqual(gateway.dispatch("POST", "/v1/diagnose", headers(large), large).status, 413)
        with self.assertRaises(ValueError):
            g.Gateway(token="short")

    def test_same_id_exact_body_only_once_provider_change_conflicts(self):
        calls = []
        def client(*args):
            calls.append(args[0])
            return g.SyntheticResponses()(*args)
        gateway = g.Gateway(client=client)
        first = request(gateway)
        self.assertEqual(first, request(gateway))
        first.body["reply"] = "caller mutation"
        self.assertNotEqual(request(gateway).body["reply"], "caller mutation")
        self.assertEqual(request(gateway, fixture("deepseek")).status, 409)
        body = json.dumps(fixture(), indent=2).encode()
        self.assertEqual(gateway.dispatch("POST", "/v1/diagnose", headers(body), body).status, 409)
        self.assertEqual(calls, ["openai"])

    def test_deadline_is_terminal_even_after_late_result(self):
        entered, release = threading.Event(), threading.Event()
        calls = []
        def client(*args):
            calls.append(True)
            entered.set()
            release.wait(1)
            return g.SyntheticResponses()(*args)
        gateway = g.Gateway(client=client, deadline_seconds=0.02)
        try:
            result = request(gateway)
            self.assertTrue(entered.is_set())
            self.assertEqual(result, g.error(504, "deadline_exceeded"))
            self.assertEqual(request(gateway), result)
            release.set()
            self.assertEqual(request(gateway), result)
            self.assertEqual(len(calls), 1)
        finally:
            release.set()

    def test_inflight_and_capacity_are_bounded(self):
        entered, release = threading.Event(), threading.Event()
        def client(*args):
            entered.set()
            release.wait(1)
            return g.SyntheticResponses()(*args)
        gateway = g.Gateway(client=client, deadline_seconds=0.5, capacity=1, workers=1)
        results = []
        thread = threading.Thread(target=lambda: results.append(request(gateway)))
        thread.start()
        try:
            self.assertTrue(entered.wait(0.3))
            self.assertEqual(request(gateway), g.error(409, "request_in_progress"))
            self.assertEqual(request(gateway, key=OTHER_KEY), g.error(503, "capacity_reached"))
        finally:
            release.set()
            thread.join(1)
        self.assertEqual(results[0].status, 200)
        self.assertEqual(request(gateway, key=OTHER_KEY), g.error(503, "capacity_reached"))

    def test_client_exception_is_cached_and_not_echoed(self):
        calls = []
        def bad(*_):
            calls.append(1)
            raise RuntimeError("synthetic-secret-do-not-echo")
        gateway = g.Gateway(client=bad)
        self.assertEqual(request(gateway), g.error(502, "invalid_response"))
        self.assertEqual(request(gateway), g.error(502, "invalid_response"))
        self.assertEqual(len(calls), 1)

    def test_http_handler_without_network(self):
        body = raw(fixture())
        handler = g.Handler.__new__(g.Handler)
        handler.server = SimpleNamespace(gateway=g.Gateway())
        handler.path = "/v1/diagnose"
        handler.command = "POST"
        handler.request_version = "HTTP/1.1"
        handler.requestline = "POST /v1/diagnose HTTP/1.1"
        handler.headers = Message()
        for key, value in headers(body):
            handler.headers[key] = value
        handler.rfile = io.BytesIO(body)
        handler.wfile = io.BytesIO()
        handler.do_POST()
        response = handler.wfile.getvalue()
        self.assertIn(b"200 OK", response)
        self.assertIn(b"Cache-Control: no-store", response)
        self.assertIn(b"Connection: close", response)
        self.assertEqual(set(json.loads(response.split(b"\r\n\r\n", 1)[1])), {"reply"})


if __name__ == "__main__":
    unittest.main()
