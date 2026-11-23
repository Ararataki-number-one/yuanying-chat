"""Synthetic, in-memory checks for the device driver's summary validation.

No Android/emulator, filesystem payload, account, network or provider is used.
These checks validate the oracle, not Android text rendering or real callbacks.
"""
import copy
import json
import unittest
import xml.etree.ElementTree as ET

import ui

HEADER = "本机观察（Gecko 回调）\n具体导航归属未知。"


def event(identifier="E7", *, kind="LOAD_ERROR", signal="UNKNOWN", code=None, category=None):
    return dict(id=identifier, kind=kind, signal=signal, code=code,
                category=category, elapsedMs=19)


def entry(events):
    return dict(schema=1, engine="GECKO", tabEvidenceId="T3",
                scope="TAB_CALLBACK_OBSERVATIONS", navigationAttribution="UNKNOWN",
                events=events)


def hierarchy(record, summary, *, configured=False, marker=None):
    envelope = dict(version=1, provider="openai", evidence=[record]) if configured else dict(evidence=[record])
    heading = ("网关 https://gateway-failure.test/v1/diagnose\n供应商 GPT\n"
               "请求编号 12345678-1234-4234-8234-123456789abc\n"
               "这是新请求。若先前已送达，启用付费的网关可能再次计费。\n") if configured else ""
    availability = "" if configured else "配置网关后可发送给 AI。\n\n"
    raw_marker = marker or ("将发送的证据" if configured else "本地证据")
    content = (heading + "标签页 3 · T3\n\n" + availability + summary
               + "\n\n" + raw_marker + "\n" + json.dumps(envelope, ensure_ascii=False, indent=2))
    tree = ET.Element("hierarchy")
    ET.SubElement(tree, "node", {"package": ui.PACKAGE, "class": "android.widget.TextView",
                                "enabled": "true", "visible-to-user": "true", "text": content})
    return tree


class LocalSummaryTest(unittest.TestCase):
    def assertAccepts(self, record, summary):
        before = copy.deepcopy(record)
        for configured in (False, True):
            with self.subTest(configured=configured):
                self.assertEqual(ui._preview(hierarchy(record, summary, configured=configured),
                                             configured=configured), [record])
        self.assertEqual(record, before)

    def assertRejects(self, record, summary, code="local-summary-evidence-mismatch"):
        for configured in (False, True):
            with self.subTest(configured=configured):
                with self.assertRaises(ui.UiBlocked) as failure:
                    ui._preview(hierarchy(record, summary, configured=configured), configured=configured)
                self.assertEqual(str(failure.exception), code)

    def test_certificate_signal_with_code_50(self):
        record = entry([event(signal="CERTIFICATE_REJECTED", code=50, category=2)])
        self.assertAccepts(record, HEADER + "\n[T3/E7] 收到证书拒绝回调 · 错误码 50/2")

    def test_unknown_code_50_is_not_certificate_inference(self):
        record = entry([event(code=50, category=2)])
        self.assertAccepts(record, HEADER + "\n[T3/E7] 收到未细分的加载错误回调 · 错误码 50/2")
        self.assertRejects(record, HEADER + "\n[T3/E7] 收到证书拒绝回调 · 错误码 50/2")

    def test_supported_signals(self):
        cases = (
            ("LOAD_ERROR", "DNS_FAILURE", 37, 5, "收到名称解析失败回调 · 错误码 37/5"),
            ("LOAD_ERROR", "TIMEOUT", 1, 3, "收到超时回调 · 错误码 1/3"),
            ("LOAD_ERROR", "TLS_FAILURE", 2, 6, "收到 TLS 失败回调 · 错误码 2/6"),
            ("CONTENT_CRASH", "CONTENT_CRASH", None, None, "收到内容进程崩溃回调"),
            ("CONTENT_KILL", "CONTENT_KILL", None, None, "收到内容进程终止回调"),
        )
        for kind, signal, code, category, expected in cases:
            with self.subTest(signal=signal):
                self.assertAccepts(entry([event(kind=kind, signal=signal, code=code, category=category)]),
                                   HEADER + "\n[T3/E7] " + expected)

    def test_unknown_missing_codes_are_omitted(self):
        self.assertAccepts(entry([event()]), HEADER + "\n[T3/E7] 收到未细分的加载错误回调")
        self.assertRejects(entry([event()]), HEADER + "\n[T3/E7] 收到未细分的加载错误回调 · 错误码 null/null")
        self.assertRejects(entry([event()]), HEADER + "\n[T3/E7] 收到未细分的加载错误回调 · 错误码 0/0")

    def test_failure_stop_is_generic_and_event_order_is_exact(self):
        record = entry([event("E1", kind="LOAD_START"),
                        event("E8", signal="CERTIFICATE_REJECTED", code=50, category=2),
                        event("E9", kind="PAGE_STOP_FAILURE")])
        first = "[T3/E8] 收到证书拒绝回调 · 错误码 50/2"
        second = "[T3/E9] 收到加载失败回调"
        self.assertAccepts(record, HEADER + "\n" + first + "\n" + second)
        self.assertRejects(record, HEADER + "\n" + second + "\n" + first)
        self.assertRejects(record, HEADER + "\n" + first)

    def test_no_fault_summary_does_not_claim_health(self):
        record = entry([event("E1", kind="LOAD_START"), event("E2", kind="LOCATION_CHANGED"),
                        event("E3", kind="PAGE_STOP_SUCCESS")])
        self.assertAccepts(record, HEADER + "\n所选快照没有记录到故障回调。")
        self.assertRejects(record, HEADER + "\n当前网页正常。")

    def test_wrong_tab_event_and_error_code_fail(self):
        record = entry([event(signal="CERTIFICATE_REJECTED", code=50, category=2)])
        correct = HEADER + "\n[T3/E7] 收到证书拒绝回调 · 错误码 50/2"
        for changed in (correct.replace("T3", "T4"), correct.replace("E7", "E8"),
                        correct.replace("50/2", "51/2"), correct.replace(" · 错误码 50/2", "")):
            self.assertRejects(record, changed)

    def test_missing_duplicate_header_and_unknown_attribution_fail(self):
        record = entry([event()])
        line = "[T3/E7] 收到未细分的加载错误回调"
        self.assertRejects(record, line, "local-summary-unavailable")
        self.assertRejects(record, HEADER + "\n" + HEADER + "\n" + line, "local-summary-unavailable")
        self.assertRejects(record, "本机观察（Gecko 回调）\n" + line)

    def test_invented_advice_or_extra_fault_is_rejected(self):
        record = entry([event()])
        summary = HEADER + "\n[T3/E7] 收到未细分的加载错误回调"
        self.assertRejects(record, summary + "\n远端建议（待核实）\n证书可能已过期。")
        self.assertRejects(record, summary + "\n[T3/E8] 收到证书拒绝回调")

    def test_exact_local_and_confirmation_raw_markers(self):
        record = entry([event()])
        summary = HEADER + "\n[T3/E7] 收到未细分的加载错误回调"
        for configured in (False, True):
            wrong = "本地证据" if configured else "将发送的证据"
            with self.assertRaises(ui.UiBlocked) as failure:
                ui._preview(hierarchy(record, summary, configured=configured, marker=wrong),
                            configured=configured)
            self.assertEqual(str(failure.exception), "preview-json-marker-invalid")

    def test_summary_in_another_textview_cannot_satisfy_the_assertion(self):
        record = entry([event()])
        summary = HEADER + "\n[T3/E7] 收到未细分的加载错误回调"
        tree = hierarchy(record, "")
        ET.SubElement(tree, "node", {"package": ui.PACKAGE, "class": "android.widget.TextView",
                                    "text": summary})
        with self.assertRaises(ui.UiBlocked) as failure:
            ui._preview(tree)
        self.assertEqual(str(failure.exception), "local-summary-unavailable")

    def test_json_cannot_hide_an_extra_field(self):
        record = entry([event()])
        record["url"] = "https://synthetic-only.test/"
        self.assertRejects(record, HEADER + "\n[T3/E7] 收到未细分的加载错误回调",
                           "preview-fields-not-whitelisted")


if __name__ == "__main__":
    unittest.main()
