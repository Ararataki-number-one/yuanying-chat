package local.pocketchat;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.app.Instrumentation;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.os.Process;
import android.os.SystemClock;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ListView;
import android.widget.TextView;
import java.lang.reflect.Field;
import java.util.concurrent.Callable;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.json.JSONArray;
import org.json.JSONObject;

/**
 * Native-dialog tests for a standalone, INTERNET-denied fixture APK.
 * AiDiagnosticUi/Gateway/Reply/Evidence/Json/J are copied without edits by the runner.
 * Only the fixture route/session/activity/appearance are synthetic. This is not an
 * original-APK, Gecko, TLS, device-network or provider acceptance receipt.
 * Reflection reads the two dialog handles; all product actions use native controls.
 * No body, endpoint, token, UUID, exception message or stack is reported.
 */
public final class AiDiagnosticInstrumentation extends Instrumentation {
  private static final long STEP_MS = 8000;
  private static final long OVERALL_MS = 90000;
  private static final String ENDPOINT = "https://diagnostic-fixture.test/v1/diagnose";
  private static final String TOKEN = "pocketchat-instrumentation-synthetic-token-0001";
  private static final Pattern REQUEST_ID = Pattern.compile(
      "请求编号 ([0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})\\n");
  private final AtomicBoolean finished = new AtomicBoolean();
  private final Bundle results = new Bundle();
  private volatile String stage = "starting";
  private MainActivity activity;

  @Override public void onCreate(Bundle arguments) {
    super.onCreate(arguments);
    start();
  }

  @Override public void onStart() {
    super.onStart();
    Thread watchdog = new Thread(() -> {
      SystemClock.sleep(OVERALL_MS);
      Bundle failure = new Bundle();
      failure.putString("result", "failed");
      failure.putString("failure", "instrumentation_timeout");
      complete(Activity.RESULT_CANCELED, failure);
    }, "ai-dialog-test-watchdog");
    watchdog.setDaemon(true);
    watchdog.start();
    try {
      stage = "internet_permission";
      check("local.pocketchat.aidiagnostics".equals(getTargetContext().getPackageName()));
      check(getTargetContext().checkPermission(Manifest.permission.INTERNET,
          Process.myPid(), Process.myUid()) == PackageManager.PERMISSION_DENIED);
      results.putString("internet_permission_denied", "true");
      cancelPreview();
      staleConfirmation();
      validReply();
      rejectedReply();
      deniedReply();
      stopWaiting();
      results.putString("result", "passed");
      closeActivity();
      complete(Activity.RESULT_OK, results);
    } catch (Throwable ignored) {
      // Fixed stage only: upstream/JSON/platform exceptions can include input data.
      results.putString("result", "failed");
      results.putString("failure", stage);
      try { closeActivity(); } catch (Throwable alsoIgnored) { }
      complete(Activity.RESULT_CANCELED, results);
    }
  }

  private void complete(int code, Bundle values) {
    if (finished.compareAndSet(false, true)) finish(code, values);
  }

  private void cancelPreview() throws Exception {
    stage = "cancel_setup";
    open(AiDiagnosticRoute.Scenario.VALID);
    Preview preview = preparePreview();
    stage = "cancel_preview";
    clickDialog(preview.dialog, AlertDialog.BUTTON_NEGATIVE, "关闭");
    await(() -> child() == null);
    check(AiDiagnosticRoute.snapshot().calls == 0);
    clickDialog(dialog(), AlertDialog.BUTTON_NEGATIVE, "关闭");
    await(() -> dialog() == null);
    check(AiDiagnosticRoute.snapshot().calls == 0);
    check(AiDiagnosticRoute.snapshot().captures == 0);
    results.putString("cancel_calls", "0");
    closeActivity();
  }

  private void staleConfirmation() throws Exception {
    stage = "stale_setup";
    open(AiDiagnosticRoute.Scenario.VALID);
    Preview preview = preparePreview();
    stage = "stale_confirmation";
    main(() -> { activity.session.connectionEpoch++; return null; });
    confirmTwice(preview);
    awaitText("线路、网关或标签页已变化，请重新预览。");
    check(AiDiagnosticRoute.snapshot().calls == 0);
    check(AiDiagnosticRoute.snapshot().captures == 0);
    results.putString("stale_calls", "0");
    results.putString("stale_confirmation_rejected", "true");
    closeActivity();
  }

  private void validReply() throws Exception {
    stage = "valid_setup";
    open(AiDiagnosticRoute.Scenario.VALID);
    Preview preview = preparePreview();
    stage = "valid_confirm";
    confirmTwice(preview);
    awaitText("已收到诊断回复。");
    stage = "valid_binding";
    AiDiagnosticRoute.Snapshot snapshot = AiDiagnosticRoute.snapshot();
    check(snapshot.calls == 1 && snapshot.bodyWrites == 1);
    check(preview.body.equals(snapshot.body) && preview.id.equals(snapshot.requestId));
    check(snapshot.post && snapshot.authorizationMatches && snapshot.noAmbientHeaders
        && snapshot.redirectsDisabled && snapshot.cachesDisabled);
    JSONObject selected = new JSONObject(preview.body).getJSONArray("evidence").getJSONObject(0);
    check("T1".equals(selected.getString("tabEvidenceId")));
    JSONArray events = selected.getJSONArray("events");
    boolean fault = false;
    for (int i = 0; i < events.length(); i++) {
      JSONObject event = events.getJSONObject(i);
      if ("E2".equals(event.getString("id"))) {
        fault = "LOAD_ERROR".equals(event.getString("kind"))
            && "CERTIFICATE_REJECTED".equals(event.getString("signal"))
            && event.getInt("code") == 50 && event.getInt("category") == 2;
      }
    }
    check(fault);
    String visible = main(() -> text(dialog().getWindow().getDecorView()));
    check(visible.contains("本机观察") && visible.contains("[T1/E2] 收到证书拒绝回调")
        && visible.contains("错误码 50/2") && visible.contains("具体导航归属未知。")
        && visible.contains("远端建议（待核实）")
        && visible.contains("证书信任关系或有效期可能存在问题。")
        && visible.contains("查看设备的日期、时间和时区。"));
    check(!visible.contains("[T99/") && !visible.contains("/E999]"));
    results.putString("valid_calls", "1");
    results.putString("valid_preview_match", "true");
    results.putString("valid_evidence_bound", "true");
    closeActivity();
  }

  private void rejectedReply() throws Exception {
    stage = "invalid_setup";
    open(AiDiagnosticRoute.Scenario.WRONG_REFERENCE);
    Preview preview = preparePreview();
    stage = "invalid_confirm";
    confirmTwice(preview);
    awaitText("网关回复无法与本次证据核对。");
    check(AiDiagnosticRoute.snapshot().calls == 1);
    String visible = main(() -> text(dialog().getWindow().getDecorView()));
    check(!visible.contains("已收到诊断回复。") && !visible.contains("诊断结果")
        && !visible.contains("本机观察") && !visible.contains("远端建议（待核实）"));
    results.putString("invalid_calls", "1");
    results.putString("invalid_reply_rejected", "true");
    closeActivity();
  }

  private void deniedReply() throws Exception {
    stage = "denial_setup";
    open(AiDiagnosticRoute.Scenario.HTTP_403);
    Preview preview = preparePreview();
    stage = "denial_confirm";
    confirmTwice(preview);
    awaitText("网关拒绝访问，请核对配置。");
    check(AiDiagnosticRoute.snapshot().calls == 1);
    String visible = main(() -> text(dialog().getWindow().getDecorView()));
    check(!visible.contains("已收到诊断回复。") && !visible.contains("诊断结果")
        && !visible.contains("本机观察"));
    results.putString("denial_calls", "1");
    results.putString("http_denial_shown", "true");
    closeActivity();
  }

  private void stopWaiting() throws Exception {
    stage = "stop_setup";
    open(AiDiagnosticRoute.Scenario.HOLD_AFTER_BODY);
    Preview preview = preparePreview();
    stage = "stop_inflight";
    confirmTwice(preview);
    check(AiDiagnosticRoute.awaitBodyWritten(STEP_MS));
    check(AiDiagnosticRoute.awaitResponseRequested(STEP_MS));
    clickDialog(dialog(), AlertDialog.BUTTON_POSITIVE, "停止等待");
    awaitText("已停止等待。 网关可能已收到请求。");
    await(() -> AiDiagnosticRoute.snapshot().activeRoutes == 0);
    AiDiagnosticRoute.releaseHold();
    waitForIdleSync();
    check(AiDiagnosticRoute.snapshot().calls == 1);
    String visible = main(() -> text(dialog().getWindow().getDecorView()));
    check(!visible.contains("已收到诊断回复。") && !visible.contains("诊断结果"));
    results.putString("stop_waiting_cancelled", "true");
    closeActivity();
  }

  private void open(AiDiagnosticRoute.Scenario scenario) throws Exception {
    closeActivity();
    AiDiagnosticRoute.reset(scenario);
    Intent intent = new Intent(getTargetContext(), MainActivity.class)
        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
    activity = (MainActivity) startActivitySync(intent);
    await(() -> activity != null && !activity.isFinishing());
    main(() -> {
      Button tools = button(activity.getWindow().getDecorView(), "网页工具");
      check(tools != null && tools.isEnabled());
      check(tools.performLongClick());
      return null;
    });
    await(() -> dialog() != null && dialog().isShowing());
    assertTitle(dialog(), "AI 助手 · 浏览器诊断");
  }

  private Preview preparePreview() throws Exception {
    clickText(dialog(), "选择标签页证据");
    await(() -> child() != null && child().isShowing());
    AlertDialog selection = child();
    assertTitle(selection, "选择标签页证据（最多 3 个）");
    await(() -> selection.getListView() != null && selection.getListView().getChildAt(0) != null);
    main(() -> {
      ListView list = selection.getListView();
      check(list.getCount() == 1 && !list.isItemChecked(0));
      check(list.performItemClick(list.getChildAt(0), 0, list.getAdapter().getItemId(0)));
      check(list.isItemChecked(0));
      return null;
    });
    clickDialog(selection, AlertDialog.BUTTON_POSITIVE, "选入");
    await(() -> child() == null);
    awaitText("已选 1 份证据。");
    clickText(dialog(), "配置 AI 网关");
    await(() -> child() != null && child().isShowing());
    AlertDialog provider = child();
    assertTitle(provider, "选择 AI 供应商");
    clickDialog(provider, AlertDialog.BUTTON_POSITIVE, "继续");
    await(() -> child() != null && child() != provider && child().isShowing());
    AlertDialog config = child();
    assertTitle(config, "GPT 网关");
    main(() -> {
      EditText endpoint = input(config.getWindow().getDecorView(), "已授权的 HTTPS 网关");
      EditText token = input(config.getWindow().getDecorView(), "本窗口访问令牌");
      check(endpoint != null && token != null);
      endpoint.setText(ENDPOINT);
      token.setText(TOKEN);
      return null;
    });
    clickDialog(config, AlertDialog.BUTTON_POSITIVE, "使用");
    await(() -> child() == null);
    awaitText("已选择 GPT。");
    clickDialog(dialog(), AlertDialog.BUTTON_POSITIVE, "预览证据");
    await(() -> child() != null && child().isShowing());
    AlertDialog review = child();
    assertTitle(review, "确认发送脱敏证据");
    String details = main(() -> previewText(review.getWindow().getDecorView()));
    check(details != null);
    Matcher id = REQUEST_ID.matcher(details);
    check(id.find());
    String requestId = id.group(1);
    int begin = details.indexOf("将发送的证据\n");
    check(begin >= 0);
    JSONObject body = new JSONObject(details.substring(begin + "将发送的证据\n".length()));
    check(body.getInt("version") == 1 && "openai".equals(body.getString("provider"))
        && body.getJSONArray("evidence").length() == 1);
    check(AiDiagnosticRoute.snapshot().calls == 0);
    return new Preview(review, body.toString(), requestId);
  }

  private void confirmTwice(Preview preview) throws Exception {
    main(() -> {
      check(preview.dialog.isShowing());
      Button send = preview.dialog.getButton(AlertDialog.BUTTON_POSITIVE);
      check(send != null && send.isEnabled() && "确认新请求并发送".contentEquals(send.getText()));
      check(send.performClick());
      // Deliberately invoke the same retained native control twice in one UI turn.
      // The production listener must reject the dismissed/stale second confirmation.
      send.performClick();
      return null;
    });
  }

  private void closeActivity() throws Exception {
    MainActivity old = activity;
    if (old == null) return;
    main(() -> { old.finish(); return null; });
    await(old::isDestroyed);
    activity = null;
  }

  private void awaitText(String expected) throws Exception {
    await(() -> dialog() != null && text(dialog().getWindow().getDecorView()).contains(expected));
  }

  private void assertTitle(AlertDialog target, String expected) throws Exception {
    check(main(() -> text(target.getWindow().getDecorView()).contains(expected)));
  }

  private void clickText(AlertDialog target, String label) throws Exception {
    main(() -> {
      Button view = button(target.getWindow().getDecorView(), label);
      check(view != null && view.isEnabled() && view.performClick());
      return null;
    });
  }

  private void clickDialog(AlertDialog target, int which, String label) throws Exception {
    main(() -> {
      check(target != null && target.isShowing());
      Button button = target.getButton(which);
      check(button != null && button.isEnabled() && label.contentEquals(button.getText()));
      check(button.performClick());
      return null;
    });
  }

  private AlertDialog dialog() throws Exception { return handle("dialog"); }
  private AlertDialog child() throws Exception { return handle("child"); }

  private AlertDialog handle(String name) throws Exception {
    if (activity == null) return null;
    // Test-only observation; never call private product methods or set product fields.
    Field field = AiDiagnosticUi.class.getDeclaredField(name);
    field.setAccessible(true);
    return (AlertDialog) field.get(activity.diagnosticUi);
  }

  private void await(Callable<Boolean> condition) throws Exception {
    long deadline = SystemClock.uptimeMillis() + STEP_MS;
    while (SystemClock.uptimeMillis() < deadline) {
      if (main(condition)) return;
      SystemClock.sleep(25);
    }
    throw new AssertionError("fixed_test_timeout");
  }

  private <T> T main(Callable<T> action) throws Exception {
    AtomicReference<T> value = new AtomicReference<>();
    AtomicReference<Throwable> failure = new AtomicReference<>();
    runOnMainSync(() -> {
      try { value.set(action.call()); }
      catch (Throwable ignored) { failure.set(ignored); }
    });
    if (failure.get() != null) throw new AssertionError("fixed_ui_check_failed");
    return value.get();
  }

  private static String text(View root) {
    StringBuilder result = new StringBuilder();
    if (root instanceof TextView) result.append(((TextView) root).getText()).append('\n');
    if (root instanceof ViewGroup) {
      ViewGroup group = (ViewGroup) root;
      for (int i = 0; i < group.getChildCount(); i++) result.append(text(group.getChildAt(i)));
    }
    return result.toString();
  }

  private static Button button(View root, String label) {
    if (root instanceof Button && label.contentEquals(((Button) root).getText())) return (Button) root;
    if (root instanceof ViewGroup) {
      ViewGroup group = (ViewGroup) root;
      for (int i = 0; i < group.getChildCount(); i++) {
        Button value = button(group.getChildAt(i), label);
        if (value != null) return value;
      }
    }
    return null;
  }

  private static EditText input(View root, String description) {
    if (root instanceof EditText && description.contentEquals(
        root.getContentDescription() == null ? "" : root.getContentDescription())) return (EditText) root;
    if (root instanceof ViewGroup) {
      ViewGroup group = (ViewGroup) root;
      for (int i = 0; i < group.getChildCount(); i++) {
        EditText value = input(group.getChildAt(i), description);
        if (value != null) return value;
      }
    }
    return null;
  }

  private static String previewText(View root) {
    if (root instanceof TextView) {
      String value = ((TextView) root).getText().toString();
      if (value.contains("将发送的证据\n")) return value;
    }
    if (root instanceof ViewGroup) {
      ViewGroup group = (ViewGroup) root;
      for (int i = 0; i < group.getChildCount(); i++) {
        String value = previewText(group.getChildAt(i));
        if (value != null) return value;
      }
    }
    return null;
  }

  private static void check(boolean condition) {
    if (!condition) throw new AssertionError("fixed_test_check_failed");
  }

  private static final class Preview {
    final AlertDialog dialog;
    final String body, id;
    Preview(AlertDialog dialog, String body, String id) {
      this.dialog = dialog;
      this.body = body;
      this.id = id;
    }
  }
}
