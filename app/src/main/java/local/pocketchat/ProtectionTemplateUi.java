package local.pocketchat;

import android.app.AlertDialog;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import java.util.concurrent.RejectedExecutionException;
import org.json.JSONObject;

/** Native capability and user-recorded compatibility guidance; never changes a template. */
final class ProtectionTemplateUi {
  private ProtectionTemplateUi() {}

  static JSONObject assessment(ChatSession session, EnvironmentSpec specification) {
    JSONObject runtime = EnvironmentIdentityUi.runtime(session);
    BrowserIdentitySpec requested = null;
    boolean owner = specification != null
        && specification.identity.environmentId.equals(session.environmentId)
        && specification.identity.generation == session.environmentGeneration
        && specification.identity.slot == Profiles.slot(session.context);
    if (owner) {
      try { requested = BrowserIdentitySpec.from(specification.desired().browser()); }
      catch (RuntimeException invalid) { /* Invalid desired evidence remains unavailable. */ }
    }
    GeckoSettings settings = session.web.getSettings();
    EnvironmentSpec cached = session.identity.cached;
    boolean stale = owner && cached != null && cached.identity.equals(specification.identity)
        && (cached.desiredRevision != specification.desiredRevision || cached.appliedRevision != specification.appliedRevision);
    boolean applied = owner && !stale && requested != null && requested.validate().isEmpty()
        && cached != null && cached.identity.equals(specification.identity)
        && specification.appliedRevision == session.identityAuditAppliedRevision()
        && !specification.pending() && specification.appliedRevision > 0
        && !session.identity.pendingWork() && !session.identity.queueUnavailable
        && settings.policyAcknowledged && specification.engineVersion.equals(GeckoWebView.VERSION)
        && FingerprintObservationHistory.same(specification.desired().browser(), settings.acceptedBrowserIdentity);
    try {
      runtime.put("configurationRevision", owner ? specification.appliedRevision : 0);
      runtime.put("templateApplied", applied);
    } catch (org.json.JSONException invalid) {
      throw new IllegalStateException(invalid);
    }
    return ProtectionTemplateAssessment.assess(requested, runtime, session.audit.fingerprintComparison);
  }

  static void show(MainActivity activity, ChatSession edited) {
    if (!EnvironmentIdentityUi.current(activity, edited)) return;
    LinearLayout body = new LinearLayout(activity);
    body.setOrientation(LinearLayout.VERTICAL);
    body.setPadding(activity.dp(18), activity.dp(10), activity.dp(18), activity.dp(16));
    TextView text = activity.label("正在读取模板能力…", 14, Ui.INK);
    text.setLineSpacing(activity.dp(4), 1);
    body.addView(text);
    Button refresh = EnvironmentAuditUi.button(activity, body, "重新读取能力与兼容记录");
    ScrollView scroll = new ScrollView(activity);
    scroll.addView(body);
    AlertDialog dialog = AppAppearance.dialog(activity).setTitle("原生保护模板能力")
        .setView(scroll).setPositiveButton("关闭", null).create();
    long[] revision = {0};
    Runnable read = () -> {
      if (!EnvironmentIdentityUi.current(activity, edited) || !dialog.isShowing()) return;
      long ticket = ++revision[0];
      refresh.setEnabled(false);
      try { edited.environmentIo.execute(() -> {
        EnvironmentSpec loaded = null;
        try { loaded = new EnvironmentSpecRepository(edited.context).load(); }
        catch (Exception unavailable) { /* Do not turn a read failure into capability confirmation. */ }
        EnvironmentSpec specification = loaded;
        edited.handler.post(() -> {
          if (!EnvironmentIdentityUi.current(activity, edited) || !dialog.isShowing() || ticket != revision[0]) return;
          text.setText(ProtectionTemplateAssessment.summary(assessment(edited, specification)));
          refresh.setEnabled(true);
        });
      }); } catch (RejectedExecutionException retired) {
        if (EnvironmentIdentityUi.current(activity, edited) && dialog.isShowing()) {
          text.setText("当前环境的配置读取已结束，请关闭后重新打开。");
          refresh.setEnabled(true);
        }
      }
    };
    refresh.setOnClickListener(view -> read.run());
    dialog.setOnDismissListener(ignored -> revision[0]++);
    dialog.show();
    read.run();
  }
}
