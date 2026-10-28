package local.pocketchat;

import android.app.AlertDialog;
import android.content.pm.PackageInfo;
import android.os.Build;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import java.util.Arrays;
import java.util.concurrent.RejectedExecutionException;
import org.json.JSONArray;
import org.json.JSONObject;

/** Explicit, owner-bound identity readout. Reading never starts a probe or navigation. */
final class EnvironmentIdentityUi {
  private EnvironmentIdentityUi() {}

  static boolean current(MainActivity activity, ChatSession session) {
    return !activity.destroyed && !activity.isDestroyed() && !activity.isFinishing()
        && activity.session == session && !session.deleted;
  }

  static JSONObject runtime(ChatSession session) {
    GeckoSettings settings = session.web.getSettings();
    EnvironmentAudit audit = session.audit;
    String page = session.web.getUrl();
    boolean pagePresent = !session.deleted && !session.navigating && session.web.hasVisibleDocument();
    JSONObject report = audit.report;
    boolean reportCurrent = pagePresent && !audit.running && report != null
        && audit.observationCurrent(report) && report.optString("policy").equals(audit.policyStamp())
        && report.optString("route").equals(audit.routeStamp());
    JSONObject result = J.obj(
        "environmentId", session.environmentId,
        "environmentGeneration", session.environmentGeneration,
        "slot", Profiles.slot(session.context),
        "engineVersion", GeckoWebView.VERSION,
        "policyAcknowledged", settings.policyAcknowledged,
        "acceptedBrowserIdentity", settings.acceptedBrowserIdentity,
        "requestedLocales", new JSONArray(Arrays.asList(settings.requestedLocales)),
        "expectedSdkLocales", new JSONArray(Arrays.asList(settings.expectedSdkLocales)),
        "expectedLocales", new JSONArray(Arrays.asList(settings.expectedSdkLocales)),
        "protectionStatus", session.web.protectionStatus(),
        "nativeProtection", session.web.protectionStatus(),
        "routeAdmitted", session.identity.actualRouteAdmitted() && session.web.protectionAllowsNetwork(),
        "queuePending", session.identity.pendingWork(),
        "queueUnavailable", session.identity.queueUnavailable,
        "pagePresent", pagePresent,
        "navigationEpoch", session.navigationEpoch,
        "sourcePageHash", page == null || page.isEmpty() ? "" : EnvironmentAudit.hash(page),
        "sourceOrigin", FingerprintObservationHistory.origin(page),
        "reportCurrent", reportCurrent,
        "report", report == null ? new JSONObject() : report);
    try {
      PackageInfo installed = session.context.getPackageManager().getPackageInfo(session.context.getPackageName(), 0);
      result.put("appVersion", installed.versionName == null ? "" : installed.versionName);
      result.put("appVersionCode", Build.VERSION.SDK_INT >= 28 ? installed.getLongVersionCode() : installed.versionCode);
    } catch (Exception unavailable) {
      // Missing package evidence stays missing, rather than borrowing a report's version.
    }
    return result;
  }

  static void show(MainActivity activity, ChatSession edited) {
    if (!current(activity, edited)) return;
    LinearLayout body = new LinearLayout(activity);
    body.setOrientation(LinearLayout.VERTICAL);
    body.setPadding(activity.dp(18), activity.dp(10), activity.dp(18), activity.dp(16));
    TextView info = activity.label("正在读取当前环境配置…", 14, Ui.INK);
    info.setLineSpacing(activity.dp(4), 1);
    body.addView(info);
    Button refresh = EnvironmentAuditUi.button(activity, body, "重新读取身份状态");
    Button retry = EnvironmentAuditUi.button(activity, body, "重试强化保护确认");
    ScrollView scroll = new ScrollView(activity);
    scroll.addView(body);
    AlertDialog dialog = AppAppearance.dialog(activity).setTitle("当前环境身份")
        .setView(scroll).setPositiveButton("关闭", null).create();
    long[] revision = {0};
    Runnable read = () -> {
      if (!current(activity, edited) || !dialog.isShowing()) return;
      long ticket = ++revision[0];
      refresh.setEnabled(false);
      retry.setEnabled(false);
      try { edited.environmentIo.execute(() -> {
        EnvironmentSpec loaded = null;
        try { loaded = new EnvironmentSpecRepository(edited.context).load(); }
        catch (Exception unavailable) { /* Preserve unknown state; no write or implicit retry. */ }
        EnvironmentSpec specification = loaded;
        edited.handler.post(() -> {
          if (!current(activity, edited) || !dialog.isShowing() || ticket != revision[0]) return;
          EnvironmentSpec cached = edited.identity.cached;
          if (specification != null && cached != null && cached.identity.equals(specification.identity)
              && cached.desiredRevision > specification.desiredRevision) {
            info.setText("配置在读取期间已变化，请重新读取身份状态。");
            refresh.setEnabled(true);
            return;
          }
          info.setText(EnvironmentIdentityStatus.summary(EnvironmentIdentityStatus.project(specification, runtime(edited))));
          refresh.setEnabled(true);
          retry.setEnabled(!edited.audit.running && edited.privacy.level() >= 2
              && edited.web.protectionStatus().optBoolean("retryAvailable"));
        });
      }); } catch (RejectedExecutionException retired) {
        if (current(activity, edited) && dialog.isShowing()) {
          info.setText("当前环境的配置读取已结束，请关闭后重新打开。");
          refresh.setEnabled(true);
        }
      }
    };
    refresh.setOnClickListener(view -> read.run());
    retry.setOnClickListener(view -> {
      if (!current(activity, edited) || !dialog.isShowing() || edited.audit.running) return;
      boolean started = edited.web.retryProtection();
      info.setText(started ? "已请求有限重试。点按重新读取查看当前结果。" : "当前没有可执行的保护重试，请重新读取状态。");
      retry.setEnabled(false);
    });
    dialog.setOnDismissListener(ignored -> revision[0]++);
    dialog.show();
    read.run();
  }
}
