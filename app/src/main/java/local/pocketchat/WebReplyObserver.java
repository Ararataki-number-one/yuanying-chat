package local.pocketchat;

import android.net.Uri;
import java.io.InputStream;
import org.json.JSONObject;

/** Page readiness and resource safety; website send/result observation is retired. */
final class WebReplyObserver {
  final ChatSession session;
  String script = "";
  boolean supported;

  WebReplyObserver(ChatSession session) { this.session = session; }

  void install() {
    try {
      try (InputStream in = session.context.getAssets().open("web-reply-observer.js")) {
        script = J.text(in, 128 * 1024);
      }
      try (InputStream in = session.context.getAssets().open("web-performance.js")) {
        script = J.text(in, 128 * 1024) + "\n" + script;
      }
      script += "\nwindow.__pocketReadDriver=(action,arg)=>" + session.driver.replace("__ACTION__", "action").replace("__ARG__", "arg") + ";";
      supported = true;
    } catch (Exception ignored) { supported = false; }
  }

  void pageReady() {
    if (!script.isEmpty() && session.web.resourcePage(session.web.getUrl())) {
      session.web.evaluateJavascript(script + "\nwindow.__pocketReadDriver('observe-install',"
        + J.obj("resourceBinding", session.resourceObserverBinding) + ");", null);
    }
  }

  /** Preserve an old record as history, but never resume result checking after upgrade. */
  void restorePending() {
    JSONObject job = session.pending;
    if (job == null) return;
    try {
      session.prefs.edit().putString(webJob(job) ? "retiredWebObservation" : "legacyPending", job.toString())
        .remove("pending").remove("lastWebGesture").commit();
    } catch (RuntimeException unavailable) {
      // Retain the old on-disk record for a future migration attempt. It must
      // never become an active observation even when storage is unavailable.
    }
    if (session.pending == job) {
      session.pending = null;
      session.activeDeliveryId = "";
      ChatService.end(session.context);
    }
  }

  static boolean same(String a, String b) {
    return MainActivity.chatUrl(a) && MainActivity.chatUrl(b)
      && Uri.parse(a).getPath().equals(Uri.parse(b).getPath());
  }
  static boolean webJob(JSONObject job) { return job != null && "web".equals(job.optString("kind")); }

  void receive(JSONObject event) { receive(event, null); }
  void receive(JSONObject event, Object port) {
    String url = event.optString("url"), document = event.optString("documentId");
    if (!MainActivity.chatUrl(url) || !MainActivity.chatUrl(session.web.getUrl())
        || !document.matches("[a-zA-Z0-9-]{16,80}")) return;
    String type = event.optString("type");
    if ("resource-route".equals(type)) {
      session.resourceObserverRouteReady(event, port);
    } else if ("resource-work".equals(type)) {
      session.resourceWebsiteObservation(event, port);
    } else if ("ready".equals(type)) {
      session.resourceObserverRouteReady(event, port);
      if (session.webPerformance() && session.networkReady && !session.offline
          && session.navigating && session.targetMatches(url)) session.wakePolling();
    }
    // Old documents may still post intent/bound/uncertain/stop during an
    // upgrade. These events have no native task, notification or UI consumer.
  }
}
