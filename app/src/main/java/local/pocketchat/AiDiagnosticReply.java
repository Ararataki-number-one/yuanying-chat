package local.pocketchat;

import java.io.IOException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

/** Binds every remote suggestion to the exact evidence reviewed for this request. */
final class AiDiagnosticReply {
  private static final String DIAGNOSTICS = "REVIEW_LOCAL_DIAGNOSTICS";
  private static final String CONNECTION = "REVIEW_CONNECTION_STATUS";
  private static final String WAIT = "WAIT_FOR_MORE_EVIDENCE";
  private static final String CLOCK = "REVIEW_DEVICE_DATE_TIME";
  private static final String VERSION = "REVIEW_BROWSER_VERSION";

  static String localPreview(JSONArray evidence) throws JSONException {
    Map<String, JSONObject> facts = facts(evidence);
    StringBuilder text = new StringBuilder("本机观察（Gecko 回调）\n具体导航归属未知。");
    if (facts.isEmpty()) return text.append("\n所选快照没有记录到故障回调。").toString();
    for (Map.Entry<String, JSONObject> fact : facts.entrySet()) {
      JSONObject event = fact.getValue();
      text.append("\n[").append(fact.getKey()).append("] ")
          .append(observed(event.optString("signal"), event.optString("kind")));
      Object code = event.opt("code");
      Object category = event.opt("category");
      if (code instanceof Number && category instanceof Number) {
        text.append(" · 错误码 ").append(code).append('/').append(category);
      }
    }
    return text.toString();
  }

  static String render(byte[] bytes, String confirmedBody) throws IOException {
    Map<?, ?> envelope = AiDiagnosticJson.object(AiDiagnosticJson.decode(bytes), "version", "diagnosis");
    if (!Integer.valueOf(2).equals(envelope.get("version"))) throw AiDiagnosticJson.invalid();
    Map<?, ?> diagnosis = AiDiagnosticJson.object(envelope.get("diagnosis"), "hypotheses");
    Map<String, JSONObject> facts = facts(confirmedBody);
    List<?> hypotheses = AiDiagnosticJson.array(diagnosis.get("hypotheses"), facts.isEmpty() ? 0 : 1,
        facts.isEmpty() ? 0 : 6);

    StringBuilder text = new StringBuilder("本机观察");
    for (Map.Entry<String, JSONObject> fact : facts.entrySet()) {
      JSONObject event = fact.getValue();
      text.append("\n[").append(fact.getKey()).append("] ")
          .append(observed(event.optString("signal"), event.optString("kind")))
          .append(" · 错误码 ").append(event.opt("code")).append('/').append(event.opt("category"))
          .append(" · +").append(event.optInt("elapsedMs")).append("ms");
    }
    if (facts.isEmpty()) return text.append("\n所选快照没有故障回调，证据不足。本次未调用模型。").toString();
    text.append("\n具体导航归属未知。\n\n远端建议（待核实）");

    Set<String> used = new HashSet<>();
    for (Object item : hypotheses) {
      Map<?, ?> hypothesis = AiDiagnosticJson.object(item, "hypothesis", "tabEvidenceId", "evidence", "steps");
      String name = AiDiagnosticJson.text(hypothesis.get("hypothesis"));
      String tab = AiDiagnosticJson.text(hypothesis.get("tabEvidenceId"));
      Plan plan = plan(name);
      if (!used.add(tab + "/" + name)) throw AiDiagnosticJson.invalid();
      List<String> references = new ArrayList<>();
      for (Object candidate : AiDiagnosticJson.array(hypothesis.get("evidence"), 1, 3)) {
        Map<?, ?> ref = AiDiagnosticJson.object(candidate, "eventId", "signal");
        String reference = tab + "/" + AiDiagnosticJson.text(ref.get("eventId"));
        String signal = AiDiagnosticJson.text(ref.get("signal"));
        JSONObject event = facts.get(reference);
        if (event == null || references.contains(reference) || !signal.equals(event.optString("signal"))
            || !plan.supports(signal)) throw AiDiagnosticJson.invalid();
        references.add(reference);
      }
      List<String> steps = new ArrayList<>();
      for (Object value : AiDiagnosticJson.array(hypothesis.get("steps"), 1, 2)) {
        String step = AiDiagnosticJson.text(value);
        if ((!DIAGNOSTICS.equals(step) && !plan.secondary.equals(step)) || steps.contains(step))
          throw AiDiagnosticJson.invalid();
        steps.add(step);
      }
      text.append("\n[").append(String.join("、", references)).append("] ").append(plan.label);
      for (String step : steps) text.append("\n  · ").append(stepLabel(step));
    }
    if (text.length() > 6000) throw AiDiagnosticJson.invalid();
    return text.toString();
  }

  private static Map<String, JSONObject> facts(String confirmedBody) throws IOException {
    try {
      return facts(new JSONObject(confirmedBody).getJSONArray("evidence"));
    } catch (JSONException invalid) {
      throw AiDiagnosticJson.invalid();
    }
  }

  private static Map<String, JSONObject> facts(JSONArray evidence) throws JSONException {
    Map<String, JSONObject> facts = new LinkedHashMap<>();
    for (int i = 0; i < evidence.length(); i++) {
      JSONObject tab = evidence.getJSONObject(i);
      JSONArray events = tab.getJSONArray("events");
      for (int j = 0; j < events.length(); j++) {
        JSONObject event = events.getJSONObject(j);
        switch (event.getString("kind")) {
          case "LOAD_ERROR": case "PAGE_STOP_FAILURE": case "CONTENT_CRASH": case "CONTENT_KILL":
            facts.put(tab.getString("tabEvidenceId") + "/" + event.getString("id"), event);
            break;
          default:
            break;
        }
      }
    }
    return facts;
  }

  private static String observed(String signal, String kind) {
    switch (signal) {
      case "DNS_FAILURE": return "收到名称解析失败回调";
      case "TIMEOUT": return "收到超时回调";
      case "CERTIFICATE_REJECTED": return "收到证书拒绝回调";
      case "TLS_FAILURE": return "收到 TLS 失败回调";
      case "CONTENT_CRASH": return "收到内容进程崩溃回调";
      case "CONTENT_KILL": return "收到内容进程终止回调";
      default: return "LOAD_ERROR".equals(kind) ? "收到未细分的加载错误回调" : "收到加载失败回调";
    }
  }

  private static final class Plan {
    final String label, secondary;
    final String[] signals;
    Plan(String label, String secondary, String... signals) {
      this.label = label;
      this.secondary = secondary;
      this.signals = signals;
    }
    boolean supports(String signal) {
      for (String expected : signals) if (expected.equals(signal)) return true;
      return false;
    }
  }

  private static Plan plan(String key) throws IOException {
    switch (key) {
      case "NAME_RESOLUTION_UNAVAILABLE":
        return new Plan("名称解析服务可能暂时不可用。", CONNECTION, "DNS_FAILURE");
      case "NETWORK_PATH_DISRUPTION":
        return new Plan("当前网络路径可能中断。", CONNECTION, "DNS_FAILURE", "TIMEOUT");
      case "REMOTE_RESPONSE_DELAY":
        return new Plan("远端响应可能延迟，当前无法确认等待发生在哪一段。", WAIT, "TIMEOUT");
      case "CERTIFICATE_TRUST_OR_VALIDITY":
        return new Plan("证书信任关系或有效期可能存在问题。", CLOCK, "CERTIFICATE_REJECTED");
      case "DEVICE_CLOCK_MISMATCH":
        return new Plan("设备时间可能与有效期校验不符。", CLOCK, "CERTIFICATE_REJECTED");
      case "TLS_NEGOTIATION_PROBLEM":
        return new Plan("TLS 协商可能失败，具体阶段未知。", CONNECTION, "TLS_FAILURE");
      case "CONTENT_PROCESS_INSTABILITY":
        return new Plan("内容进程可能出现不稳定。", VERSION, "CONTENT_CRASH");
      case "PROCESS_TERMINATION_UNEXPLAINED":
        return new Plan("证据无法确定内容进程被终止的原因。", VERSION, "CONTENT_KILL");
      case "INSUFFICIENT_EVIDENCE":
        return new Plan("当前证据不足以进一步归因。", WAIT, "DNS_FAILURE", "TIMEOUT", "CERTIFICATE_REJECTED",
            "TLS_FAILURE", "CONTENT_CRASH", "CONTENT_KILL", "UNKNOWN");
      default:
        throw AiDiagnosticJson.invalid();
    }
  }

  private static String stepLabel(String step) throws IOException {
    switch (step) {
      case DIAGNOSTICS: return "查看当前环境的本地诊断记录。";
      case CONNECTION: return "查看当前环境的连接状态。";
      case WAIT: return "等待新的回调证据，再对照本次记录。";
      case CLOCK: return "查看设备的日期、时间和时区。";
      case VERSION: return "查看当前的浏览器版本。";
      default: throw AiDiagnosticJson.invalid();
    }
  }
}
