package local.pocketchat;

import android.app.AlertDialog;
import android.content.Context;
import android.text.InputType;
import android.view.View;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import org.json.JSONArray;
import org.json.JSONObject;

/** Window-scoped, explicit review and delivery of browser evidence. */
final class AiDiagnosticUi {
  private static final int MAX_SELECTED = 3;
  private static final long DEADLINE_MS = 35000;
  private final MainActivity activity;
  private final ExecutorService worker = Executors.newSingleThreadExecutor(task -> {
    Thread thread = new Thread(task, "browser-ai-diagnostics");
    thread.setDaemon(true);
    return thread;
  });
  private ChatSession owner;
  private AiDiagnosticGateway.Settings settings;
  private AlertDialog dialog;
  private AlertDialog child;
  private TextView status;
  private TextView answer;
  private View choose;
  private View configure;
  private final List<AiDiagnosticEvidence.Entry> selected = new ArrayList<>();
  private Attempt active;
  private Attempt uncertain;
  private String feedback = "";
  private String reply = "";
  private boolean closed;

  private static final class Attempt {
    final AiDiagnosticGateway.Settings settings;
    final ChatSession owner;
    final long epoch;
    final String body, preview, id;
    final boolean reusedId;
    final AiDiagnosticGateway.Transfer transfer = new AiDiagnosticGateway.Transfer();
    final List<AiDiagnosticEvidence.Entry> entries;
    Future<?> future;
    Runnable deadline;

    Attempt(ChatSession owner, AiDiagnosticGateway.Settings settings,
            List<AiDiagnosticEvidence.Entry> entries, String body, String preview, Attempt previous) {
      this.owner = owner;
      this.settings = settings;
      this.epoch = owner.connectionEpoch;
      this.entries = new ArrayList<>(entries);
      this.body = body;
      this.preview = preview;
      reusedId = previous != null && previous.owner == owner && previous.settings == settings
          && previous.body.equals(body);
      id = reusedId ? previous.id : UUID.randomUUID().toString();
    }
    String confirmationText() {
      return reusedId ? "沿用上一次状态不确定的请求编号。"
          : "这是新请求。若先前已送达，启用付费的网关可能再次计费。";
    }
    String confirmationButton() {
      return reusedId ? "沿用编号发送" : "确认新请求并发送";
    }
    boolean currentEvidence() {
      for (AiDiagnosticEvidence.Entry entry : entries) if (!entry.current()) return false;
      return true;
    }
  }

  static boolean enabled(Context context) {
    return "local.pocketchat.aidiagnostics".equals(context.getPackageName());
  }

  AiDiagnosticUi(MainActivity activity) { this.activity = activity; }

  private boolean current() {
    return !closed && GeckoAddressUi.available(activity) && owner != null
        && activity.session == owner && ChatSession.peek() == owner;
  }

  void show() {
    if (closed || !enabled(activity) || !GeckoAddressUi.available(activity)) return;
    if (dialog != null && dialog.isShowing()) return;
    if (owner != activity.session) {
      owner = activity.session;
      settings = null;
      uncertain = null;
      selected.clear();
      reply = feedback = "";
    }
    LinearLayout box = panel();
    choose = DesignUi.button(activity, "选择标签页证据", false, this::choose);
    configure = DesignUi.button(activity, "配置 AI 网关", false, this::configure);
    box.addView(choose);
    box.addView(configure);
    status = DesignUi.text(activity, "", 14, DesignUi.TEXT);
    status.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
    answer = DesignUi.text(activity, "", 14, DesignUi.TEXT);
    answer.setTextIsSelectable(true);
    box.addView(status);
    box.addView(answer);
    AlertDialog opened = AppAppearance.dialog(activity).setTitle("AI 助手 · 浏览器诊断")
        .setView(scroll(box)).setNegativeButton("关闭", null)
        .setPositiveButton("预览证据", null).create();
    dialog = opened;
    opened.setOnDismissListener(ignored -> {
      if (dialog != opened) return;
      dialog = null;
      if (child != null) child.dismiss();
      if (active != null) stop(active, "已关闭助手。");
    });
    opened.show();
    opened.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(ignored -> {
      if (active == null) preview();
      else stop(active, "已停止等待。");
    });
    update();
  }

  private LinearLayout panel() {
    LinearLayout box = DesignUi.column(activity);
    box.setPadding(activity.dp(18), activity.dp(8), activity.dp(18), activity.dp(12));
    return box;
  }

  private ScrollView scroll(View content) {
    ScrollView scroll = new ScrollView(activity);
    scroll.addView(content);
    return scroll;
  }

  private void setChild(AlertDialog secondary) {
    child = secondary;
    secondary.setOnDismissListener(ignored -> {
      if (child == secondary) child = null;
      update();
    });
    secondary.show();
    update();
  }

  private void choose() {
    if (!current() || child != null || active != null) return;
    List<AiDiagnosticEvidence.Entry> entries = owner.web.aiDiagnosticEvidence().entries();
    if (entries.isEmpty()) {
      feedback = "当前环境没有可以归属到标签页的原生错误记录。";
      update();
      return;
    }
    String[] labels = new String[entries.size()];
    boolean[] checked = new boolean[entries.size()];
    for (int i = 0; i < labels.length; i++) labels[i] = entries.get(i).label();
    AlertDialog selection = AppAppearance.dialog(activity).setTitle("选择标签页证据（最多 3 个）")
        .setMultiChoiceItems(labels, checked, (ignored, which, value) -> checked[which] = value)
        .setNegativeButton("取消", null).setPositiveButton("选入", null).create();
    setChild(selection);
    selection.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(ignored -> {
      if (!current() || child != selection || active != null) return;
      List<AiDiagnosticEvidence.Entry> next = new ArrayList<>();
      for (int i = 0; i < checked.length; i++) if (checked[i]) next.add(entries.get(i));
      if (next.isEmpty() || next.size() > MAX_SELECTED) {
        selection.setTitle("请选择 1 至 3 个标签页");
        return;
      }
      selected.clear();
      selected.addAll(next);
      feedback = "已选 " + selected.size() + " 份证据。";
      selection.dismiss();
    });
  }

  private void configure() {
    if (!current() || child != null || active != null) return;
    String[] providers = {"GPT", "DeepSeek"};
    int[] selection = {settings != null && "deepseek".equals(settings.provider) ? 1 : 0};
    AlertDialog provider = AppAppearance.dialog(activity).setTitle("选择 AI 供应商")
        .setSingleChoiceItems(providers, selection[0], (ignored, which) -> selection[0] = which)
        .setNegativeButton("取消", null).setPositiveButton("继续", null).create();
    setChild(provider);
    provider.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(ignored -> {
      if (child != provider || !current()) return;
      provider.dismiss();
      if (child == provider) child = null;
      endpoint(selection[0] == 0 ? "openai" : "deepseek");
    });
  }

  private void endpoint(String provider) {
    if (!current() || active != null) return;
    LinearLayout box = panel();
    EditText url = DesignUi.input(box, "已授权的 HTTPS 网关", settings == null ? "" : settings.endpoint,
        "https://…/v1/diagnose");
    url.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
    EditText token = DesignUi.input(box, "本窗口访问令牌", "", "由自控网关发放");
    token.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
    token.setSaveEnabled(false);
    AlertDialog config = AppAppearance.dialog(activity)
        .setTitle("openai".equals(provider) ? "GPT 网关" : "DeepSeek 网关")
        .setView(box).setNegativeButton("取消", null).setPositiveButton("使用", null).create();
    setChild(config);
    config.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(ignored -> {
      if (child != config || !current()) return;
      try {
        settings = new AiDiagnosticGateway.Settings(url.getText().toString(), token.getText().toString(), provider);
        feedback = "已选择 " + settings.providerLabel() + "。";
        token.setText("");
        config.dismiss();
      } catch (IllegalArgumentException invalid) {
        token.setError(invalid.getMessage());
      }
    });
  }

  private void preview() {
    if (!current() || child != null || active != null || selected.isEmpty()) return;

    JSONArray evidence = new JSONArray();
    StringBuilder labels = new StringBuilder();
    for (AiDiagnosticEvidence.Entry entry : selected) {
      if (!entry.current()) {
        feedback = "标签页发生变化，请重新选择证据。";
        update();
        return;
      }
      JSONObject record = entry.json();
      evidence.put(record);
      labels.append(entry.label()).append(" · ").append(record.optString("tabEvidenceId")).append('\n');
    }
    AiDiagnosticGateway.Settings configured = settings;
    String issue = configured == null ? "配置网关后可发送给 AI。" : AiDiagnosticRoute.issue(owner);
    JSONObject request = configured == null ? J.obj("evidence", evidence)
        : J.obj("version", 1, "provider", configured.provider, "evidence", evidence);
    Attempt attempt = configured != null && issue.isEmpty()
        ? new Attempt(owner, configured, selected, request.toString(), labels.toString(), uncertain) : null;
    String preview, localPreview;
    try {
      preview = request.toString(2);
      localPreview = AiDiagnosticReply.localPreview(evidence);
    } catch (org.json.JSONException invalid) {
      feedback = "无法预览本次证据。";
      update();
      return;
    }
    String heading = configured == null ? "" : "网关 " + configured.endpoint + "\n供应商 "
        + configured.providerLabel() + "\n";
    if (attempt != null) heading += "请求编号 " + attempt.id + "\n" + attempt.confirmationText() + "\n";
    String availability = attempt == null ? issue + "\n\n" : "";
    String jsonHeading = attempt == null ? "本地证据\n" : "将发送的证据\n";
    LinearLayout content = panel();
    TextView details = DesignUi.text(activity, heading + labels + "\n"
        + availability + localPreview + "\n\n" + jsonHeading + preview, 14, DesignUi.TEXT);
    details.setTextIsSelectable(true);
    content.addView(details);
    AlertDialog.Builder builder = AppAppearance.dialog(activity)
        .setTitle(attempt == null ? "查看本地诊断证据" : "确认发送脱敏证据")
        .setView(scroll(content)).setNegativeButton("关闭", null);
    if (attempt != null) builder.setPositiveButton(attempt.confirmationButton(), null);
    AlertDialog review = builder.create();
    setChild(review);
    if (attempt != null) review.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(ignored -> {
      if (child != review || active != null || !current()) return;
      review.dismiss();
      send(attempt);
    });
  }

  private void send(Attempt attempt) {
    if (!current() || active != null || attempt.owner != owner || settings != attempt.settings
        || attempt.epoch != owner.connectionEpoch || !attempt.currentEvidence()) {
      feedback = "线路、网关或标签页已变化，请重新预览。";
      update();
      return;
    }
    active = attempt;
    feedback = "正在通过当前环境发送…";
    update();
    attempt.deadline = () -> stop(attempt, "等待诊断回复超时。");
    activity.handler.postDelayed(attempt.deadline, DEADLINE_MS);
    attempt.future = worker.submit(() -> {
      String result = null;
      String problem = "未收到诊断回复。";
      try {
        result = AiDiagnosticGateway.send(attempt.owner, attempt.epoch, attempt.settings, attempt.id,
            attempt.body, attempt.transfer);
      } catch (AiDiagnosticGateway.DeliveryException safe) {
        problem = safe.getMessage();
      } catch (java.io.IOException | RuntimeException unavailable) {
        // Platform and upstream exceptions can contain endpoint or transport data.
      }
      String completed = result;
      String failure = problem;
      activity.handler.post(() -> {
        if (active != attempt) return;
        if (completed == null || !current() || attempt.epoch != owner.connectionEpoch) {
          stop(attempt, failure);
          return;
        }
        activity.handler.removeCallbacks(attempt.deadline);
        active = null;
        uncertain = null;
        String title = attempt.currentEvidence() ? "已发送证据快照的诊断结果"
            : "历史诊断结果（证据快照已不可用于当前诊断）";
        reply = title + "\n仅对应当时确认发送的证据。\n\n" + attempt.preview + "\n" + completed;
        feedback = "已收到诊断回复。";
        update();
      });
    });
  }

  private void stop(Attempt attempt, String reason) {
    if (active != attempt) return;
    active = null;
    activity.handler.removeCallbacks(attempt.deadline);
    attempt.transfer.cancel();
    if (attempt.future != null) attempt.future.cancel(true);
    if (attempt.transfer.possiblySent() || (uncertain != null && attempt.id.equals(uncertain.id))) {
      uncertain = attempt;
      feedback = reason + " 网关可能已收到请求。再次确认相同证据会复用编号 " + attempt.id + "。";
    } else {
      feedback = reason + " 诊断证据未写入请求。";
    }
    update();
  }

  private void update() {
    if (dialog == null || !dialog.isShowing()) return;
    boolean ready = current() && child == null && active == null;
    choose.setEnabled(ready);
    configure.setEnabled(ready);
    status.setText(feedback);
    answer.setText(reply);
    dialog.getButton(AlertDialog.BUTTON_POSITIVE).setText(active == null ? "预览证据" : "停止等待");
    dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(active != null || (ready && !selected.isEmpty()));
  }

  void close() {
    closed = true;
    if (child != null) child.dismiss();
    if (dialog != null) dialog.dismiss();
    if (active != null) stop(active, "已关闭助手。");
    settings = null;
    uncertain = null;
    worker.shutdownNow();
  }
}
