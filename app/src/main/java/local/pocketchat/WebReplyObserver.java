package local.pocketchat;

import android.net.Uri;
import androidx.webkit.WebViewCompat;
import androidx.webkit.WebViewFeature;
import java.io.InputStream;
import java.util.Collections;
import org.json.JSONArray;
import org.json.JSONObject;

/** One read-only observation task, using the existing persisted request lifecycle. */
final class WebReplyObserver {
  final ChatSession session;
  String script = "", completionJob = "", completionSignature = "";
  long completionSince;
  int completionSamples;
  boolean supported;

  WebReplyObserver(ChatSession session) { this.session = session; }

  void install() {
    try {
      
      try (InputStream in = session.context.getAssets().open("web-reply-observer.js")) {
        script = J.text(in, 128 * 1024);
      }
      try (InputStream in = session.context.getAssets().open("web-performance.js")) { script = J.text(in, 128 * 1024) + "\n" + script; }
      script += "\nwindow.__pocketReadDriver=(action,arg)=>" + session.driver.replace("__ACTION__", "action").replace("__ARG__", "arg") + ";\nwindow.__pocketReadDriver('observe-install',{});";
      if(GeckoWebView.active(session.web)){supported=true;return;}
      if (!WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)) return;
      WebViewCompat.addWebMessageListener(session.web, "PocketWebReply", Collections.singleton("https://chatgpt.com"),
        (view, message, origin, mainFrame, reply) -> {
          if (!mainFrame || !MainActivity.chatUrl(origin.toString())) return;
          String text = message.getData();
          if (text != null && text.length() <= 2 * 1024 * 1024) receive(J.parse(text));
        });
      supported = true;
      if (WebViewFeature.isFeatureSupported(WebViewFeature.DOCUMENT_START_SCRIPT))
        WebViewCompat.addDocumentStartJavaScript(session.web, script, Collections.singleton("https://chatgpt.com"));
    } catch (Exception ignored) { supported = false; }
  }

  void pageReady() {
    if (!script.isEmpty() && MainActivity.chatUrl(session.web.getUrl())) session.web.evaluateJavascript(script, null);
  }

  void restorePending() {
    JSONObject job = session.pending;
    if (!webJob(job)) return;
    JSONObject receipt = session.deliveries.get(job.optString("id"));
    String state = receipt == null ? "" : receipt.optString("state");
    if ("completed".equals(state) || "stopped".equals(state)) {
      session.pending = null;
      session.activeDeliveryId = "";
      session.prefs.edit().remove("pending").commit();
      if ("completed".equals(state)) session.handler.post(() -> ChatService.completed(session.context,
        job.optString("id"), job.optString("confirmedUrl", job.optString("expectedUrl"))));
    } else if (!job.optBoolean("confirmed")) suspendUnconfirmed("网页已重新打开，请核对之前的发送结果");
  }

  void suspendUnconfirmed(String reason) {
    JSONObject job = session.pending;
    if (!webJob(job) || job.optBoolean("confirmed")) return;
    try { job.put("webSuspended", true); } catch (Exception ignored) {}
    session.prefs.edit().putString("pending", job.toString()).commit();
    session.delivery(job.optString("id"), "uncertain", reason, true, "", "");
    ChatService.end(session.context);
  }

  static boolean stable(String key) { return key.startsWith("id:") || key.startsWith("unit:"); }
  static boolean same(String a, String b) {
    return MainActivity.chatUrl(a) && MainActivity.chatUrl(b) && Uri.parse(a).getPath().equals(Uri.parse(b).getPath());
  }
  static boolean bindingRoute(String from, String to) {
    if (same(from, to)) return true;
    if (!MainActivity.chatUrl(from) || !MainActivity.chatUrl(to)) return false;
    return Uri.parse(from).getPath().matches("/(g/[^/]+/?)?") &&
      Uri.parse(to).getPath().matches("/(g/[^/]+/)?c/[^/]+");
  }
  static boolean webJob(JSONObject job) { return job != null && "web".equals(job.optString("kind")); }

  void receive(JSONObject event) {
    String url = event.optString("url"), token = event.optString("token"), document = event.optString("documentId");
    if (!MainActivity.chatUrl(url) || !MainActivity.chatUrl(session.web.getUrl()) ||
        !document.matches("[a-zA-Z0-9-]{16,80}")) return;
    String type = event.optString("type");
    if ("ready".equals(type)) {
      if (session.webPerformance() && session.networkReady && !session.offline &&
          session.navigating && session.targetMatches(url)) session.wakePolling();
      return;
    }
    try {
      if ("intent".equals(type)) {
        if (!session.prefs.getBoolean("pageMode", false) || session.submitting || session.operation ||
            !token.matches("[a-zA-Z0-9-]{16,80}") || event.optString("prompt").length() > 300000 ||
            Math.abs(System.currentTimeMillis() - event.optLong("capturedAt")) > 60000) return;
        JSONArray before = event.optJSONArray("beforeKeys");
        if (before == null || before.length() > 4000) return;
        String identity = document + ":" + token;
        if (identity.equals(session.prefs.getString("lastWebGesture", ""))) return;
        if (session.pending != null && !webJob(session.pending)) return;
        if (session.pending != null) session.delivery(session.pending.optString("id"), "uncertain",
          "网页已开始另一条提问，原等待记录已保留，请在原对话核对", true, "", "");
        JSONArray names = new JSONArray();
        for (int i = 0; i < session.attachments.length(); i++) names.put(session.attachments.optJSONObject(i).optString("name"));
        String id = session.deliveries.begin(url, event.optString("prompt"), names, "web", null);
        JSONObject job = J.obj("id", id, "kind", "web", "webToken", token, "webDocument", document,
          "prompt", event.optString("prompt"), "beforeUserKeys", before, "attachmentNames", names,
          "attachmentOnly", event.optString("prompt").trim().isEmpty(), "expectedUrl", url,
          "export", true, "attempted", true, "startedAt", System.currentTimeMillis());
        if (!session.prefs.edit().putString("pending", job.toString()).putString("lastWebGesture", identity).commit())
          throw new IllegalStateException("无法保存网页发送记录，请保留原网页核对");
        session.pending = job;
        session.activeDeliveryId = id;
        session.stableReply = "";
        session.stableTicks = 0;
        session.delivery(id, "sending", "已观察到网页发送操作，正在核对新消息", true, "", url);
        ChatService.begin(session.context);
        session.setStatus("正在核对网页发送 · 不会重复发送");session.wakePolling();
        return;
      }
      JSONObject job = session.pending;
      if (!webJob(job)) return;
      boolean matching = token.equals(job.optString("webToken")) && document.equals(job.optString("webDocument"));
      if ("stop".equals(type)) {
        boolean bound = job.optBoolean("confirmed") && same(job.optString("confirmedUrl"), url) &&
          job.optString("userKey").equals(event.optString("userKey"));
        if (bound || (matching && !job.optBoolean("confirmed"))) finishStopped(job);
        return;
      }
      if (!matching || job.optBoolean("confirmed") || job.optBoolean("webSuspended")) return;
      if ("uncertain".equals(type)) {
        job.put("webSuspended", true);
        session.prefs.edit().putString("pending", job.toString()).commit();
        session.delivery(job.optString("id"), "uncertain", event.optString("reason"), true, "", "");
        ChatService.end(session.context);
        session.setStatus(event.optString("reason") + " · 不会自动重发");
        return;
      }
      if (!"bound".equals(type) || !bindingRoute(job.optString("expectedUrl"), url)) return;
      String key = event.optString("userKey"), prompt = event.optString("prompt");
      if (!stable(key) || key.length() > 1024 || prompt.length() > 300000) return;
      JSONArray before = job.optJSONArray("beforeUserKeys");
      for (int i = 0; before != null && i < before.length(); i++) if (key.equals(before.optString(i))) return;
      JSONObject confirmed = J.parse(job.toString());
      confirmed.put("userKey", key).put("prompt", prompt).put("confirmed", true).put("confirmedUrl", url);
      if (!session.prefs.edit().putString("pending", confirmed.toString()).commit())
        throw new IllegalStateException("网页消息标识保存失败，请保留原网页核对");
      session.pending = confirmed;
      session.delivery(job.optString("id"), "confirmed", "已确认网页中新出现的提问", true, key, url);
      session.webConfirmationVersion++;
      session.setStatus("网页已确认 · 正在等待回复");session.wakePolling();
    } catch (Exception e) {
      session.setStatus(e.getMessage() == null ? "网页发送状态保存失败，请核对原网页" : e.getMessage());
    }
  }

  void finishStopped(JSONObject job) {
    session.delivery(job.optString("id"), "stopped", "已观察到网页停止操作，已停止完成提醒", true, job.optString("userKey"), "");
    session.pending = null;
    session.activeDeliveryId = "";
    session.prefs.edit().remove("pending").commit();
    ChatService.end(session.context);
    session.setStatus("已停止等待这条网页回复");
  }

  boolean mayComplete(JSONObject job, JSONObject poll) {
    if (!webJob(job)) return true;
    if (!job.optBoolean("confirmed") || !poll.optBoolean("submitted") || !poll.optBoolean("terminal") ||
        poll.optBoolean("busy") || poll.optBoolean("bindingLost") || poll.optBoolean("otherQuestion") ||
        !poll.optString("error").isEmpty() || !job.optString("userKey").equals(poll.optString("userKey")) ||
        !same(job.optString("confirmedUrl"), poll.optString("url"))) {
      completionSamples = 0; completionSignature = ""; return false;
    }
    String signature = poll.optString("replyKey") + "|" + poll.optString("markdown") + "|" + poll.optBoolean("hasFiles");
    if (!job.optString("id").equals(completionJob) || !signature.equals(completionSignature)) {
      completionJob = job.optString("id"); completionSignature = signature;
      completionSince = System.currentTimeMillis(); completionSamples = 0;
    }
    return ++completionSamples >= 3 && System.currentTimeMillis() - completionSince >= 2000;
  }
}
