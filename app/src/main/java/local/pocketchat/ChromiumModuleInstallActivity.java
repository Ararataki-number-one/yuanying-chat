package local.pocketchat;

import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;

/** Native install window runs in the app's main process for the system confirmation callback. */
public final class ChromiumModuleInstallActivity extends ThemedActivity {
  private final Handler handler = new Handler(Looper.getMainLooper());
  private final Runnable refresh = this::refresh;
  private TextView status;
  private ProgressBar progress;
  private Button action;
  private EnvironmentSpec.Identity expected;
  private boolean active;
  private String localMessage = "";

  @Override public void onCreate(Bundle state) {
    super.onCreate(state);
    expected = ChromiumModuleInstaller.requestedOwner(getIntent());
    if (state != null) localMessage = state.getString("localMessage", "");

    LinearLayout root = DesignUi.screen(this);
    LinearLayout body = DesignUi.body(this, root, "安装 Chromium 内核", this::finish);
    LinearLayout card = DesignUi.card(this);
    status = DesignUi.text(this, "", 15, DesignUi.TEXT);
    status.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
    card.addView(status);
    progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
    progress.setMax(1000);
    card.addView(progress);
    action = DesignUi.button(this, "下载并安装", true, this::act);
    card.addView(action);
    DesignUi.note(card, "首次下载使用此环境的联网方式。Android 安装组件时可能会重新打开应用。");
    DesignUi.addCard(body, card);
    setContentView(root);
  }

  @Override protected void onResume() {
    super.onResume();
    active = true;
    refresh();
  }

  @Override protected void onPause() {
    active = false;
    handler.removeCallbacks(refresh);
    super.onPause();
  }

  @Override protected void onSaveInstanceState(Bundle state) {
    state.putString("localMessage", localMessage);
    super.onSaveInstanceState(state);
  }

  private void refresh() {
    ChromiumModuleInstaller.Operation work = ChromiumModuleInstaller.current();
    boolean running = work != null && !work.done;
    boolean sameEnvironment = work != null && work.expected.equals(expected);
    boolean current = ChromiumModuleInstaller.ownerCurrent(this, expected);
    boolean eligible = current && ChromiumModuleInstaller.available(this);
    boolean installed = ChromiumModuleInstaller.installed(this);
    String label = statusText(work, sameEnvironment, current, eligible, installed);
    if (!label.contentEquals(status.getText())) status.setText(label);
    progress.setVisibility(running && sameEnvironment ? View.VISIBLE : View.GONE);
    if (running && sameEnvironment) {
      long total = work.total, read = work.read;
      progress.setIndeterminate(total <= 0);
      if (total > 0) progress.setProgress((int) Math.min(1000, read * 1000 / total));
    }
    boolean mayCancel = running && sameEnvironment && !work.submitted && !work.cancelled;
    boolean confirmation = running && sameEnvironment && work.hasConfirmation();
    action.setVisibility(eligible && !installed && (!running || mayCancel || confirmation) ? View.VISIBLE : View.GONE);
    if (mayCancel) action.setText("取消下载");
    else if (confirmation) action.setText("打开 Android 安装界面");
    else action.setText(getPackageManager().canRequestPackageInstalls() ? "下载并安装" : "前往 Android 安装权限设置");
    handler.removeCallbacks(refresh);
    if (active && running) handler.postDelayed(refresh, 300);
  }

  private String statusText(ChromiumModuleInstaller.Operation work, boolean sameEnvironment,
      boolean current, boolean eligible, boolean installed) {
    if (!current) return "原环境已变化，请返回环境列表重新打开。";
    if (installed) return "Chromium 组件已安装。返回此环境即可打开。";
    if (!ChromiumModuleInstaller.supported(this)) return "此设备需要 Android 10 或更新版本及受支持的 64 位架构。";
    if (!eligible) return "当前安装版本暂未提供 Chromium 组件。";
    if (work != null && !work.done && !sameEnvironment) return "另一个环境正在下载或安装 Chromium 组件。";
    if (!localMessage.isEmpty()) return localMessage;
    if (sameEnvironment) {
      String bytes = !work.done && work.total > 0 && !work.submitted
          ? "\n" + AppUpdateActivity.mb(work.read) + " / " + AppUpdateActivity.mb(work.total) + " MB" : "";
      return work.message + bytes;
    }
    return "确认后会下载与当前 PocketChat 版本匹配的 Chromium 组件。";
  }

  private void act() {
    if (!ChromiumModuleInstaller.ownerCurrent(this, expected)
        || !ChromiumModuleInstaller.available(this) || ChromiumModuleInstaller.installed(this)) { refresh(); return; }
    localMessage = "";
    ChromiumModuleInstaller.Operation work = ChromiumModuleInstaller.current();
    if (work != null && !work.done) {
      if (!work.expected.equals(expected)) return;
      Intent approval = work.takeConfirmation();
      if (approval != null) {
        try { startActivity(approval); }
        catch (RuntimeException unavailable) {
          work.askForConfirmation(approval);
          localMessage = "无法打开 Android 安装界面，请再试一次。";
        }
      } else work.cancel();
    } else if (!getPackageManager().canRequestPackageInstalls()) {
      try {
        startActivity(new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
            Uri.parse("package:" + getPackageName())));
        localMessage = "允许安装组件后，请返回并点击下载。";
      } catch (RuntimeException unavailable) {
        localMessage = "请在 Android 系统设置中允许 PocketChat 安装应用。";
      }
    } else {
      if (ChromiumModuleInstaller.begin(this, expected) == null) localMessage = "原环境已变化，请返回后重试。";
    }
    refresh();
  }
}
