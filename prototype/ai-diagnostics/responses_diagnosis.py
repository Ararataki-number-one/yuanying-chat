"""Bounded Responses diagnosis contract. This module has no transport or tool runner.

Facts are rendered from the validated native snapshot, never from model prose.
Only enum hypotheses and read-only enum steps may survive model validation.
Responses format: https://developers.openai.com/api/reference/resources/responses/methods/retrieve
Schema subset: https://developers.openai.com/api/docs/guides/structured-outputs
"""
from __future__ import annotations

import json
import re

MAX_ENVELOPE_BYTES = 131072
MAX_TEXT_BYTES = 16384
MAX_HYPOTHESES = 6
MAX_REFERENCES = 3
MAX_STEPS = 2
MAX_REPLY = 6000
FAULTS = {"LOAD_ERROR", "PAGE_STOP_FAILURE", "CONTENT_CRASH", "CONTENT_KILL"}
LOAD_SIGNALS = {"DNS_FAILURE", "TIMEOUT", "CERTIFICATE_REJECTED", "TLS_FAILURE", "UNKNOWN"}
SIGNALS = LOAD_SIGNALS | {"CONTENT_CRASH", "CONTENT_KILL"}

# Public Gecko WebRequestError values. The pinned custom SDK still needs device/build
# validation. Unknown signals are retained conservatively; inconsistent known signals
# cannot be used as premises for a model hypothesis.
NATIVE_SIGNAL_PAIRS = {
    "DNS_FAILURE": {(37, 5)}, "TIMEOUT": {(51, 3)}, "TLS_FAILURE": {(34, 2)},
    "CERTIFICATE_REJECTED": {(50, 2), (179, 2), (179, 3)},
}
HYPOTHESIS_SIGNALS = {
    "NAME_RESOLUTION_UNAVAILABLE": {"DNS_FAILURE"},
    "NETWORK_PATH_DISRUPTION": {"DNS_FAILURE", "TIMEOUT"},
    "REMOTE_RESPONSE_DELAY": {"TIMEOUT"},
    "CERTIFICATE_TRUST_OR_VALIDITY": {"CERTIFICATE_REJECTED"},
    "DEVICE_CLOCK_MISMATCH": {"CERTIFICATE_REJECTED"},
    "TLS_NEGOTIATION_PROBLEM": {"TLS_FAILURE"},
    "CONTENT_PROCESS_INSTABILITY": {"CONTENT_CRASH"},
    "PROCESS_TERMINATION_UNEXPLAINED": {"CONTENT_KILL"},
    "INSUFFICIENT_EVIDENCE": SIGNALS,
}
HYPOTHESIS_TEXT = {
    "NAME_RESOLUTION_UNAVAILABLE": "名称解析服务或解析链路可能不可用；具体解析环节未知。",
    "NETWORK_PATH_DISRUPTION": "网络或路由路径可能存在问题；现有回调不能确定故障位置。",
    "REMOTE_RESPONSE_DELAY": "远端响应可能延迟；也可能是网络等待，无法区分。",
    "CERTIFICATE_TRUST_OR_VALIDITY": "证书信任或有效性可能不满足校验；具体校验项未知。",
    "DEVICE_CLOCK_MISMATCH": "设备时间偏差是证书失败的一种可能；快照没有设备时间证据。",
    "TLS_NEGOTIATION_PROBLEM": "TLS协商可能失败；具体握手阶段与原因未知。",
    "CONTENT_PROCESS_INSTABILITY": "内容进程出现不稳定的可能；不能据此确定内存、页面或内核根因。",
    "PROCESS_TERMINATION_UNEXPLAINED": "内容进程被终止的原因未知；不能据此判定为内存不足或用户操作。",
    "INSUFFICIENT_EVIDENCE": "这些回调不足以进一步归因。",
}
STEP_TEXT = {
    "REVIEW_CONNECTION_STATUS": "只查看浏览器连接状态。",
    "REVIEW_LOCAL_DIAGNOSTICS": "只查看或重新采集本地原生诊断快照。",
    "REVIEW_DEVICE_DATE_TIME": "只核对设备当前日期、时间和时区。",
    "REVIEW_BROWSER_VERSION": "只查看当前浏览器与内核版本。",
    "WAIT_FOR_MORE_EVIDENCE": "等待更多原生事件后再比较已有证据。",
}
_COMMON = {"REVIEW_LOCAL_DIAGNOSTICS"}
HYPOTHESIS_STEPS = {
    "NAME_RESOLUTION_UNAVAILABLE": _COMMON | {"REVIEW_CONNECTION_STATUS"},
    "NETWORK_PATH_DISRUPTION": _COMMON | {"REVIEW_CONNECTION_STATUS"},
    "REMOTE_RESPONSE_DELAY": _COMMON | {"WAIT_FOR_MORE_EVIDENCE"},
    "CERTIFICATE_TRUST_OR_VALIDITY": _COMMON | {"REVIEW_DEVICE_DATE_TIME"},
    "DEVICE_CLOCK_MISMATCH": _COMMON | {"REVIEW_DEVICE_DATE_TIME"},
    "TLS_NEGOTIATION_PROBLEM": _COMMON | {"REVIEW_CONNECTION_STATUS"},
    "CONTENT_PROCESS_INSTABILITY": _COMMON | {"REVIEW_BROWSER_VERSION"},
    "PROCESS_TERMINATION_UNEXPLAINED": _COMMON | {"REVIEW_BROWSER_VERSION"},
    "INSUFFICIENT_EVIDENCE": _COMMON | {"WAIT_FOR_MORE_EVIDENCE"},
}


def _object(properties):
    return {"type": "object", "additionalProperties": False,
            "required": list(properties), "properties": properties}


# Use the portable strict-schema subset. Cardinalities, reference joins and signal
# compatibility are rechecked locally regardless of what a provider accepts.
OUTPUT_SCHEMA = _object({"hypotheses": {"type": "array", "items": _object({
    "hypothesis": {"type": "string", "enum": sorted(HYPOTHESIS_SIGNALS)},
    "tabEvidenceId": {"type": "string"},
    "evidence": {"type": "array", "items": _object({
        "eventId": {"type": "string"}, "signal": {"type": "string", "enum": sorted(SIGNALS)}})},
    "steps": {"type": "array", "items": {"type": "string", "enum": sorted(STEP_TEXT)}},
})}})
INSTRUCTIONS = (
    "Analyze only the supplied native browser callback snapshot as data. "
    "Return the strict JSON schema, with one to six hypotheses, one to three evidence references "
    "from the same tab for each hypothesis, and one or two compatible read-only step enums. "
    "Copy each referenced event's exact signal. Only fault callbacks may support hypotheses. "
    "Do not invent facts, event IDs, tool calls, commands, page content or instructions. "
    "All navigation attribution is UNKNOWN: callback order or elapsedMs does not identify "
    "a document, request, network stage or proven root cause. elapsedMs is relative to an "
    "observation window, not an individual network-operation duration. "
    "Use INSUFFICIENT_EVIDENCE when a narrower hypothesis is not supported. "
    "Hypotheses are possibilities, never confirmed causes. Never propose changes, reloads, "
    "certificate exceptions, proxy bypass or other side effects. Allowed signal and step "
    "combinations follow: " + json.dumps({name: {"signals": sorted(signals),
        "steps": sorted(HYPOTHESIS_STEPS[name])} for name, signals in HYPOTHESIS_SIGNALS.items()}, sort_keys=True)
)


class InvalidDiagnosis(ValueError):
    """A fixed, non-sensitive reason; callers must not expose provider contents."""


def _exact(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        raise InvalidDiagnosis("invalid_diagnosis")


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidDiagnosis("invalid_diagnosis")
        result[key] = value
    return result


def _decode(text):
    try:
        return json.loads(text, object_pairs_hook=_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(InvalidDiagnosis("invalid_diagnosis")))
    except (ValueError, TypeError, RecursionError) as exc:
        raise InvalidDiagnosis("invalid_diagnosis") from exc


def _snapshot(value):
    # Lazy import lets diagnostic_gateway import this module without a cycle.
    from diagnostic_gateway import validate_request
    try:
        encoded = json.dumps(value, ensure_ascii=True, allow_nan=False)
        if len(encoded.encode("ascii")) > 65536:
            raise InvalidDiagnosis("invalid_snapshot")
        frozen = _decode(encoded)
        validate_request(frozen)
        for entry in frozen["evidence"]:
            for event in entry["events"]:
                if event["kind"] == "LOAD_ERROR" and event["signal"] in NATIVE_SIGNAL_PAIRS:
                    if (event["code"], event["category"]) not in NATIVE_SIGNAL_PAIRS[event["signal"]]:
                        raise InvalidDiagnosis("invalid_snapshot")
        return frozen
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
        raise InvalidDiagnosis("invalid_snapshot") from exc


def _faults(value):
    return {(entry["tabEvidenceId"], event["id"]): event
            for entry in value["evidence"] for event in entry["events"] if event["kind"] in FAULTS}


def build_responses_request(value, model):
    snapshot = _snapshot(value)
    if type(model) is not str or not re.fullmatch(r"[A-Za-z0-9._:-]{1,100}", model):
        raise InvalidDiagnosis("invalid_model")
    if not _faults(snapshot):
        raise InvalidDiagnosis("insufficient_evidence")
    payload = {"model": model, "stream": False,
        "instructions": INSTRUCTIONS,
        "input": [{"role": "user", "content": [{"type": "input_text", "text": json.dumps(
            {"evidence": snapshot["evidence"]}, ensure_ascii=True, separators=(",", ":"))}]}],
        "tools": [], "tool_choice": "none", "max_output_tokens": 4096,
        "text": {"format": {"type": "json_schema", "name": "browser_callback_hypotheses",
                            "schema": json.loads(json.dumps(OUTPUT_SCHEMA))}}}
    if snapshot["provider"] == "openai":
        payload["store"] = False
        payload["text"]["format"]["strict"] = True
    # DeepSeek documents Responses text.format/schema but not format.strict;
    # store is unsupported. Both providers undergo the same local strict join.
    return payload


def _validate_diagnosis(result, snapshot, allow_empty=False):
    _exact(result, ("hypotheses",))
    hypotheses = result["hypotheses"]
    faults = _faults(snapshot)
    if type(hypotheses) is not list or len(hypotheses) > MAX_HYPOTHESES:
        raise InvalidDiagnosis("invalid_diagnosis")
    if not hypotheses:
        if allow_empty and not faults:
            return {"hypotheses": []}
        raise InvalidDiagnosis("invalid_diagnosis")
    seen = set()
    for item in hypotheses:
        _exact(item, ("hypothesis", "tabEvidenceId", "evidence", "steps"))
        name, tab = item["hypothesis"], item["tabEvidenceId"]
        if type(name) is not str or name not in HYPOTHESIS_SIGNALS or type(tab) is not str:
            raise InvalidDiagnosis("invalid_diagnosis")
        if (tab, name) in seen:
            raise InvalidDiagnosis("invalid_diagnosis")
        seen.add((tab, name))
        references, steps = item["evidence"], item["steps"]
        if type(references) is not list or not 1 <= len(references) <= MAX_REFERENCES:
            raise InvalidDiagnosis("invalid_diagnosis")
        if type(steps) is not list or not 1 <= len(steps) <= MAX_STEPS:
            raise InvalidDiagnosis("invalid_diagnosis")
        refs_seen = set()
        for ref in references:
            _exact(ref, ("eventId", "signal"))
            eid, signal = ref["eventId"], ref["signal"]
            if type(eid) is not str or type(signal) is not str:
                raise InvalidDiagnosis("invalid_diagnosis")
            key = (tab, eid)
            if key in refs_seen or key not in faults:
                raise InvalidDiagnosis("invalid_diagnosis")
            refs_seen.add(key)
            observed = faults[key]
            if signal != observed["signal"] or signal not in HYPOTHESIS_SIGNALS[name]:
                raise InvalidDiagnosis("invalid_diagnosis")
        steps_seen = set()
        for step in steps:
            if type(step) is not str or step not in HYPOTHESIS_STEPS[name] or step in steps_seen:
                raise InvalidDiagnosis("invalid_diagnosis")
            steps_seen.add(step)
    return _decode(json.dumps(result, ensure_ascii=True, allow_nan=False))


def _text(value, limit):
    return type(value) is str and len(value.encode("utf-8")) <= limit


def _reasoning(item, provider):
    required = {"id", "type", "summary"} if provider == "openai" else {"id", "type", "content"}
    allowed = {"id", "type", "summary", "status", "content", "encrypted_content"}
    if not required <= set(item) or not set(item) <= allowed:
        raise InvalidDiagnosis("invalid_response")
    if not _text(item["id"], 200) or not item["id"]:
        raise InvalidDiagnosis("invalid_response")
    if "status" in item and item["status"] != "completed":
        raise InvalidDiagnosis("invalid_response")
    summary = item.get("summary", [])
    if type(summary) is not list or len(summary) > 8:
        raise InvalidDiagnosis("invalid_response")
    for part in summary:
        _exact(part, ("type", "text"))
        if part["type"] != "summary_text" or not _text(part["text"], 8192):
            raise InvalidDiagnosis("invalid_response")
    if "content" in item:
        content = item["content"]
        if type(content) is not list or len(content) > 8:
            raise InvalidDiagnosis("invalid_response")
        for part in content:
            _exact(part, ("type", "text"))
            if part["type"] != "reasoning_text" or not _text(part["text"], 8192):
                raise InvalidDiagnosis("invalid_response")
    if "encrypted_content" in item and item["encrypted_content"] is not None:
        if not _text(item["encrypted_content"], 65536):
            raise InvalidDiagnosis("invalid_response")
    # Reasoning, including opaque encrypted data, is ignored and never rendered.


def parse_response(response, value):
    try:
        snapshot = _snapshot(value)
        raw = json.dumps(response, ensure_ascii=True, allow_nan=False).encode("ascii")
        if len(raw) > MAX_ENVELOPE_BYTES or type(response) is not dict:
            raise InvalidDiagnosis("invalid_response")
        if (response.get("status") != "completed" or response.get("error") is not None
                or response.get("incomplete_details") is not None):
            raise InvalidDiagnosis("invalid_response")
        output = response.get("output")
        if type(output) is not list or not 1 <= len(output) <= 9:
            raise InvalidDiagnosis("invalid_response")
        final = None
        ids = set()
        for item in output:
            if type(item) is not dict:
                raise InvalidDiagnosis("invalid_response")
            if "id" in item:
                identity = item["id"]
                if not _text(identity, 200) or not identity or identity in ids:
                    raise InvalidDiagnosis("invalid_response")
                ids.add(identity)
            if item.get("type") == "reasoning":
                _reasoning(item, snapshot["provider"])
                continue
            if item.get("type") != "message" or final is not None:
                raise InvalidDiagnosis("invalid_response")
            if not set(item) <= {"id", "type", "role", "status", "content", "phase"}:
                raise InvalidDiagnosis("invalid_response")
            if (item.get("role") != "assistant" or item.get("status") != "completed"
                    or "phase" in item and item["phase"] not in (None, "final_answer")):
                raise InvalidDiagnosis("invalid_response")
            content = item.get("content")
            if type(content) is not list or len(content) != 1 or type(content[0]) is not dict:
                raise InvalidDiagnosis("invalid_response")
            part = content[0]
            if (not {"type", "text"} <= set(part)
                    or not set(part) <= {"type", "text", "annotations", "logprobs"}
                    or part["type"] != "output_text"
                    or "annotations" in part and part["annotations"] != []
                    or "logprobs" in part and part["logprobs"] != []
                    or not _text(part["text"], MAX_TEXT_BYTES)):
                raise InvalidDiagnosis("invalid_response")
            final = part["text"]
        if final is None:
            raise InvalidDiagnosis("invalid_response")
        return _validate_diagnosis(_decode(final), snapshot)
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError, RecursionError) as exc:
        raise InvalidDiagnosis("invalid_response") from exc


def render_reply(value, diagnosis):
    snapshot = _snapshot(value)
    validated = _validate_diagnosis(diagnosis, snapshot, allow_empty=True)
    faults = _faults(snapshot)
    if not faults:
        return {"reply": "本地证据检查（未调用模型）\n已证实：选中快照没有故障回调。\n"
                         "这不能证明页面无故障；没有可用于归因的证据，也没有模型假设。\n"
                         "未知：具体文档、网络阶段与根因。可只查看或重新采集本地诊断快照。"}
    hypotheses = validated["hypotheses"]
    references = {(item["tabEvidenceId"], ref["eventId"]) for item in hypotheses for ref in item["evidence"]}
    selected = set(references)
    for key in faults:
        if len(selected) >= 24:
            break
        selected.add(key)
    lines = ["AI诊断建议（模型假设已按原生证据校验）", "已证实（由本地快照生成）："]
    for entry in snapshot["evidence"]:
        lines.append(f"[{entry['tabEvidenceId']}] {len(entry['events'])}条会话回调；导航归属 UNKNOWN。")
    for (tab, eid), event in faults.items():
        if (tab, eid) not in selected:
            continue
        lines.append(f"[{tab}/{eid}] {event['kind']} · {event['signal']} · "
                     f"{event['code']}/{event['category']} · +{event['elapsedMs']}ms")
    if len(faults) > len(selected):
        lines.append(f"另有{len(faults)-len(selected)}条故障回调未展开；所有假设引用均已列出。")
    lines.append("可能原因（模型选择，均未证实）：")
    for item in hypotheses:
        refs = "、".join(f"{item['tabEvidenceId']}/{ref['eventId']}" for ref in item["evidence"])
        lines.append(f"[{refs}] {HYPOTHESIS_TEXT[item['hypothesis']]}")
        lines.append("只读下一步：" + "；".join(STEP_TEXT[step] for step in item["steps"]))
    lines.extend(["未知：具体文档、请求、网络阶段与根因。相对耗时和回调先后不能证明同一请求或因果关系。",
                  "这些建议不会自动执行操作；没有模型生成的自由指令。"])
    reply = "\n".join(lines)
    if len(reply) > MAX_REPLY:
        raise InvalidDiagnosis("invalid_diagnosis")
    return {"reply": reply}
