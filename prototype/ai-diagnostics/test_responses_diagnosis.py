"""Synthetic Responses boundary tests; no HTTP, credentials or model calls."""
import copy
import json
import unittest
from pathlib import Path

import diagnostic_gateway as gateway
import responses_diagnosis as diagnosis


def fixture(signal="DNS_FAILURE", provider="openai", tab="T1", eid="E2"):
    if signal in diagnosis.NATIVE_SIGNAL_PAIRS:
        code, category = sorted(diagnosis.NATIVE_SIGNAL_PAIRS[signal])[0]
        kind = "LOAD_ERROR"
    else:
        code = category = None
        kind = signal if signal in ("CONTENT_CRASH", "CONTENT_KILL") else "PAGE_STOP_FAILURE"
    return {"version": 1, "provider": provider, "evidence": [{
        "schema": 1, "engine": "GECKO", "tabEvidenceId": tab,
        "scope": "TAB_CALLBACK_OBSERVATIONS", "navigationAttribution": "UNKNOWN",
        "events": [{"id": "E1", "kind": "LOAD_START", "signal": "UNKNOWN",
                    "code": None, "category": None, "elapsedMs": 0},
                   {"id": eid, "kind": kind, "signal": signal,
                    "code": code, "category": category, "elapsedMs": 25}]}]}


def item(name="NAME_RESOLUTION_UNAVAILABLE", signal="DNS_FAILURE", tab="T1", eid="E2", steps=None):
    return {"hypothesis": name, "tabEvidenceId": tab,
            "evidence": [{"eventId": eid, "signal": signal}],
            "steps": steps or [sorted(diagnosis.HYPOTHESIS_STEPS[name])[0]]}


def model(value=None):
    return {"hypotheses": [item()] if value is None else value}


def envelope(result=None):
    return {"id": "resp_synthetic", "status": "completed", "error": None, "incomplete_details": None,
            "output": [{"id": "msg_synthetic", "type": "message", "role": "assistant",
                        "status": "completed", "content": [{"type": "output_text",
                        "text": json.dumps(model() if result is None else result), "annotations": []}]}]}


class RequestTests(unittest.TestCase):
    def test_provider_specific_requests_and_strict_schema_subset(self):
        for provider in ("openai", "deepseek"):
            value = fixture(provider=provider)
            request = diagnosis.build_responses_request(value, "synthetic-model")
            self.assertEqual(request["tools"], [])
            self.assertEqual(request["tool_choice"], "none")
            self.assertFalse(request["stream"])
            self.assertEqual("store" in request, provider == "openai")
            if provider == "openai":
                self.assertFalse(request["store"])
                self.assertIs(request["text"]["format"]["strict"], True)
            else:
                self.assertNotIn("strict", request["text"]["format"])
            self.assertEqual(json.loads(request["input"][0]["content"][0]["text"]), {"evidence": value["evidence"]})
            def walk(node):
                if node.get("type") == "object":
                    self.assertIs(node["additionalProperties"], False)
                    self.assertEqual(set(node["required"]), set(node["properties"]))
                    for child in node["properties"].values():
                        walk(child)
                if node.get("type") == "array":
                    walk(node["items"])
                self.assertNotIn("anyOf", node)
            walk(request["text"]["format"]["schema"])
            request["text"]["format"]["schema"]["required"].clear()
            self.assertEqual(diagnosis.OUTPUT_SCHEMA["required"], ["hypotheses"])

    def test_invalid_model_and_empty_faults_fail_before_provider(self):
        for name in (None, "", "bad model", "a" * 101, [], True):
            with self.subTest(name=name), self.assertRaisesRegex(diagnosis.InvalidDiagnosis, "invalid_model"):
                diagnosis.build_responses_request(fixture(), name)
        for events in ([], fixture()["evidence"][0]["events"][:1]):
            value = fixture(); value["evidence"][0]["events"] = events
            with self.assertRaisesRegex(diagnosis.InvalidDiagnosis, "insufficient_evidence"):
                diagnosis.build_responses_request(value, "synthetic")
            local = diagnosis.render_reply(value, {"hypotheses": []})
            self.assertEqual(set(local), {"reply"})
            self.assertIn("未调用模型", local["reply"])
            self.assertIn("不能证明页面无故障", local["reply"])
            with self.assertRaises(diagnosis.InvalidDiagnosis):
                diagnosis.parse_response(envelope({"hypotheses": []}), value)

    def test_snapshot_privacy_and_native_signal_consistency(self):
        for key in ("url", "domain", "pageText", "cookies", "token", "environmentId"):
            value = fixture(); value[key] = "synthetic-private-marker"
            with self.subTest(key=key), self.assertRaisesRegex(diagnosis.InvalidDiagnosis, "invalid_snapshot"):
                diagnosis.build_responses_request(value, "synthetic")
        for code, category in ((1, 2), (37, 2), (None, None), (51, 3)):
            value = fixture(); value["evidence"][0]["events"][1].update(code=code, category=category)
            with self.subTest(code=code), self.assertRaises(diagnosis.InvalidDiagnosis):
                diagnosis.build_responses_request(value, "synthetic")
        for code, category in ((None, None), (2147483647, 2147483647)):
            value = fixture(); value["evidence"][0]["events"][1].update(signal="UNKNOWN", code=code, category=category)
            self.assertTrue(diagnosis.build_responses_request(value, "synthetic"))

    def test_java_journal_fixture_still_valid_and_mapping_preserved(self):
        value = json.loads((Path(__file__).parent / "fixtures/java-wire.json").read_text())
        result = model([item(), item("CERTIFICATE_TRUST_OR_VALIDITY", "CERTIFICATE_REJECTED", "T3")])
        diagnosis.build_responses_request(value, "synthetic")
        parsed = diagnosis.parse_response(envelope(result), value)
        rendered = diagnosis.render_reply(value, parsed)["reply"]
        self.assertIn("T1/E2", rendered); self.assertIn("T3/E2", rendered)
        self.assertNotIn("T2/", rendered)


class DiagnosisTests(unittest.TestCase):
    def test_all_permitted_hypothesis_signal_step_pairs(self):
        for name, signals in diagnosis.HYPOTHESIS_SIGNALS.items():
            for signal in signals:
                for step in diagnosis.HYPOTHESIS_STEPS[name]:
                    with self.subTest(name=name, signal=signal, step=step):
                        result = model([item(name, signal, steps=[step])])
                        self.assertEqual(diagnosis.parse_response(envelope(result), fixture(signal)), result)

    def test_unsupported_hypothesis_signal_pairs(self):
        for name, allowed in diagnosis.HYPOTHESIS_SIGNALS.items():
            for signal in diagnosis.SIGNALS - allowed:
                with self.subTest(name=name, signal=signal), self.assertRaises(diagnosis.InvalidDiagnosis):
                    diagnosis.parse_response(envelope(model([item(name, signal)])), fixture(signal))

    def test_safe_steps_bound_to_hypothesis_and_no_free_instructions(self):
        for name, allowed in diagnosis.HYPOTHESIS_STEPS.items():
            signal = sorted(diagnosis.HYPOTHESIS_SIGNALS[name])[0]
            for step in set(diagnosis.STEP_TEXT) - allowed | {"RUN_COMMAND", "DISABLE_TLS", "RELOAD", "synthetic free text"}:
                result = model([item(name, signal, steps=[step])])
                with self.subTest(name=name, step=step), self.assertRaises(diagnosis.InvalidDiagnosis):
                    diagnosis.parse_response(envelope(result), fixture(signal))
        for path in ((), ("hypotheses", 0), ("hypotheses", 0, "evidence", 0)):
            result = model(); cursor = result
            for part in path:
                cursor = cursor[part]
            cursor["instruction"] = "synthetic untrusted text"
            with self.assertRaises(diagnosis.InvalidDiagnosis):
                diagnosis.parse_response(envelope(result), fixture())

    def test_no_fact_fields_or_claims_of_known_navigation(self):
        for extra in ("facts", "rootCause", "navigationAttribution", "confidence", "command", "reply"):
            result = model(); result["hypotheses"][0][extra] = "CONFIRMED"
            with self.subTest(extra=extra), self.assertRaises(diagnosis.InvalidDiagnosis):
                diagnosis.parse_response(envelope(result), fixture())

    def test_wrong_tab_wrong_event_wrong_signal_and_nonfault_references(self):
        variants = [item(tab="T9"), item(eid="E9"), item(signal="TIMEOUT"),
                    item("INSUFFICIENT_EVIDENCE", "UNKNOWN", eid="E1")]
        value = fixture(); value["evidence"].append(fixture("TIMEOUT", tab="T2")["evidence"][0])
        variants.append(item(tab="T2"))
        for hypothesis in variants:
            with self.subTest(hypothesis=hypothesis), self.assertRaises(diagnosis.InvalidDiagnosis):
                diagnosis.parse_response(envelope(model([hypothesis])), value)
        # Same event number in separate tabs is valid only with its own exact signal.
        good = model([item(), item("REMOTE_RESPONSE_DELAY", "TIMEOUT", tab="T2")])
        self.assertEqual(diagnosis.parse_response(envelope(good), value), good)

    def test_every_reference_must_support_same_hypothesis(self):
        value = fixture(); value["evidence"][0]["events"].append(fixture("CONTENT_CRASH", eid="E3")["evidence"][0]["events"][1])
        bad = model(); bad["hypotheses"][0]["evidence"].append({"eventId": "E3", "signal": "CONTENT_CRASH"})
        with self.assertRaises(diagnosis.InvalidDiagnosis):
            diagnosis.parse_response(envelope(bad), value)
        good = model([item("INSUFFICIENT_EVIDENCE")]); good["hypotheses"][0]["evidence"].append({"eventId": "E3", "signal": "CONTENT_CRASH"})
        self.assertEqual(diagnosis.parse_response(envelope(good), value), good)

    def test_cardinality_duplicates_and_types(self):
        variants = [None, [], {}, {"hypotheses": None}, {"hypotheses": []}, {"hypotheses": [item()] * 7},
                    {"hypotheses": [item(), item()]}, {"hypotheses": [None]}]
        for field, values in {"hypothesis": ([], True, "UNKNOWN"), "tabEvidenceId": ([], True),
                "evidence": ([], None, [None], [item()["evidence"][0]] * 2, [item()["evidence"][0]] * 4),
                "steps": ([], None, [True], ["REVIEW_LOCAL_DIAGNOSTICS"] * 2, ["REVIEW_LOCAL_DIAGNOSTICS"] * 3)}.items():
            for replacement in values:
                bad = model(); bad["hypotheses"][0][field] = replacement; variants.append(bad)
        for result in variants:
            # Explicit envelope(None) means the default fixture; set the JSON directly.
            response = envelope(); response["output"][0]["content"][0]["text"] = json.dumps(result)
            with self.subTest(result=result), self.assertRaises(diagnosis.InvalidDiagnosis):
                diagnosis.parse_response(response, fixture())
        with self.assertRaises(diagnosis.InvalidDiagnosis):
            diagnosis.render_reply(fixture(), {"hypotheses": []})

    def test_render_uses_snapshot_facts_and_selected_enum_hypotheses(self):
        original = fixture(); original["evidence"][0]["events"][1]["elapsedMs"] = 777
        parsed = diagnosis.parse_response(envelope(), original)
        reply = diagnosis.render_reply(original, parsed)["reply"]
        self.assertIn("37/5", reply); self.assertIn("+777ms", reply)
        self.assertIn("导航归属 UNKNOWN", reply); self.assertIn("均未证实", reply)
        self.assertIn(diagnosis.HYPOTHESIS_TEXT["NAME_RESOLUTION_UNAVAILABLE"], reply)
        alternative = model([item("INSUFFICIENT_EVIDENCE")])
        alternate_reply = diagnosis.render_reply(original, diagnosis.parse_response(envelope(alternative), original))["reply"]
        self.assertNotEqual(reply, alternate_reply)
        self.assertIn(diagnosis.HYPOTHESIS_TEXT["INSUFFICIENT_EVIDENCE"], alternate_reply)
        # A later/mismatching snapshot cannot reuse the old diagnosis.
        with self.assertRaises(diagnosis.InvalidDiagnosis):
            diagnosis.render_reply(fixture("TIMEOUT"), parsed)

    def test_largest_legal_snapshot_and_all_references_are_rendered(self):
        value = {"version": 1, "provider": "openai", "evidence": []}; hypotheses = []
        for t in range(2147483645, 2147483648):
            entry = fixture("TIMEOUT", tab=f"T{t}")["evidence"][0]
            entry["events"] = [dict(entry["events"][1], id=f"E{9999999999999999980+i}", elapsedMs=3600000) for i in range(16)]
            value["evidence"].append(entry)
            for index, name in enumerate(("NETWORK_PATH_DISRUPTION", "REMOTE_RESPONSE_DELAY")):
                choice = item(name, "TIMEOUT", tab=entry["tabEvidenceId"])
                choice["evidence"] = [{"eventId": event["id"], "signal": "TIMEOUT"} for event in entry["events"][10+index*3:13+index*3]]
                choice["steps"] = sorted(diagnosis.HYPOTHESIS_STEPS[name]); hypotheses.append(choice)
        parsed = diagnosis.parse_response(envelope(model(hypotheses)), value)
        reply = diagnosis.render_reply(value, parsed)["reply"]
        self.assertLessEqual(len(reply), diagnosis.MAX_REPLY)
        self.assertIn("未展开", reply)
        for choice in hypotheses:
            for ref in choice["evidence"]:
                self.assertIn(f"[{choice['tabEvidenceId']}/{ref['eventId']}]", reply)


class EnvelopeTests(unittest.TestCase):
    def test_reasoning_positions_optional_status_and_ignored_contents(self):
        reasoning = {"id": "rs_synthetic", "type": "reasoning", "summary": [],
                     "encrypted_content": "opaque-synthetic-not-a-diagnosis"}
        for before in (True, False):
            response = envelope(); response["output"].insert(0 if before else 1, copy.deepcopy(reasoning))
            self.assertEqual(diagnosis.parse_response(response, fixture()), model())
        reasoning["status"] = "completed"
        reasoning["summary"] = [{"type": "summary_text", "text": "synthetic untrusted instruction never render"}]
        reasoning["content"] = [{"type": "reasoning_text", "text": "synthetic reasoning not evidence"}]
        response = envelope(); response["output"].insert(0, reasoning)
        parsed = diagnosis.parse_response(response, fixture())
        self.assertNotIn("synthetic", diagnosis.render_reply(fixture(), parsed)["reply"])
        # DeepSeek documents content-only reasoning; its text is never used as output.
        response = envelope(); response["output"].insert(0, {"id": "rs_deepseek", "type": "reasoning",
            "content": [{"type": "reasoning_text", "text": "synthetic ignored content"}]})
        self.assertEqual(diagnosis.parse_response(response, fixture(provider="deepseek")), model())
        with self.assertRaises(diagnosis.InvalidDiagnosis):
            diagnosis.parse_response(response, fixture(provider="openai"))

    def test_final_message_phase_null_is_supported(self):
        for phase in (None, "final_answer"):
            response = envelope(); response["output"][0]["phase"] = phase
            self.assertEqual(diagnosis.parse_response(response, fixture()), model())

    def test_reasoning_malformed_incomplete_and_unbounded_rejected(self):
        baseline = {"id": "rs_synthetic", "type": "reasoning", "summary": []}
        changes = [("status", None), ("status", "in_progress"), ("status", "incomplete"),
                   ("summary", None), ("summary", [{"type": "output_text", "text": "x"}]),
                   ("summary", [{"type": "summary_text", "text": "x", "command": "x"}]),
                   ("content", None), ("content", [{"type": "function_call", "text": "x"}]),
                   ("encrypted_content", {}), ("encrypted_content", "x" * 65537),
                   ("summary", [{"type": "summary_text", "text": "x"}] * 9),
                   ("id", ""), ("tool_calls", [])]
        for key, value in changes:
            part = dict(baseline); part[key] = value; response = envelope(); response["output"].insert(0, part)
            with self.subTest(key=key, value=str(value)[:50]), self.assertRaises(diagnosis.InvalidDiagnosis):
                diagnosis.parse_response(response, fixture())
        response = envelope(); response["output"] += [dict(baseline, id=f"rs_{i}") for i in range(9)]
        with self.assertRaises(diagnosis.InvalidDiagnosis):
            diagnosis.parse_response(response, fixture())

    def test_any_tool_refusal_incomplete_error_or_extra_message_fails(self):
        variants = [None, [], {}, {"status": "completed", "output": []}]
        for kind in ("function_call", "custom_tool_call", "web_search_call", "code_interpreter_call", "mcp_call", "compaction", "tool_search_call"):
            response = envelope(); response["output"].insert(0, {"type": kind}); variants.append(response)
        for status in ("incomplete", "failed", "in_progress", "cancelled"):
            response = envelope(); response["status"] = status; variants.append(response)
        for key in ("error", "incomplete_details"):
            response = envelope(); response[key] = {}; variants.append(response)
        for content in ([{"type": "refusal", "refusal": "synthetic"}], [], [{"type": "output_text", "text": "{}"}] * 2):
            response = envelope(); response["output"][0]["content"] = content; variants.append(response)
        for field, value in (("status", "incomplete"), ("role", "user"), ("phase", "commentary"), ("tool_calls", [])):
            response = envelope(); response["output"][0][field] = value; variants.append(response)
        for field, value in (("annotations", [{"type": "url_citation"}]), ("logprobs", [{}])):
            response = envelope(); response["output"][0]["content"][0][field] = value; variants.append(response)
        response = envelope(); response["output"].append(copy.deepcopy(response["output"][0])); variants.append(response)
        response = envelope(); response["output"] = [{"id": "rs_only", "type": "reasoning", "summary": []}]; variants.append(response)
        for response in variants:
            with self.subTest(response=response), self.assertRaises(diagnosis.InvalidDiagnosis):
                diagnosis.parse_response(response, fixture())

    def test_duplicate_json_nan_truncation_and_text_bounds_fail_closed(self):
        texts = ['{"hypotheses":[],"hypotheses":[]}', '{"hypotheses":NaN}', '{"hypotheses":[',
                 '[]', 'null', '"free instruction"', '[' * 1500, 'x' * (diagnosis.MAX_TEXT_BYTES + 1), '\ud800']
        for text in texts:
            response = envelope(); response["output"][0]["content"][0]["text"] = text
            with self.subTest(text=text[:30]), self.assertRaises(diagnosis.InvalidDiagnosis):
                diagnosis.parse_response(response, fixture())
        response = envelope(); response["ignored_metadata"] = "x" * diagnosis.MAX_ENVELOPE_BYTES
        with self.assertRaises(diagnosis.InvalidDiagnosis):
            diagnosis.parse_response(response, fixture())

    def test_no_legacy_mock_behavior_changed(self):
        value = fixture()
        original = gateway.render_reply(value)
        response = gateway.SyntheticResponses()("openai", gateway.build_responses_request(value))
        gateway.parse_response(response, value)
        self.assertEqual(gateway.render_reply(value), original)
        self.assertIn("本地合成 mock", original["reply"])
        with self.assertRaises(diagnosis.InvalidDiagnosis):
            diagnosis.parse_response(response, value)


if __name__ == "__main__":
    unittest.main(verbosity=2)
