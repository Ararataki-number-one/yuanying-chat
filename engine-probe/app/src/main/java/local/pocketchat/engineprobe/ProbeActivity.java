package local.pocketchat.engineprobe;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import org.json.JSONObject;
import org.mozilla.geckoview.*;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;

/** Isolated SDK experiment, deliberately not a production browser replacement. */
public final class ProbeActivity extends Activity {
    private static final String TAG = "PocketEngineProbe";
    private static GeckoRuntime runtime;
    private static WebExtension extension;
    private final GeckoSession[] sessions = new GeckoSession[2];
    private final String[] fixtureUris = new String[2];
    private GeckoView view;
    private TextView status;
    private int selected;

    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(12), dp(8), dp(12), dp(8));
        root.setFitsSystemWindows(true);
        TextView title = new TextView(this);
        title.setText("GeckoView 内核验证");
        title.setTextSize(20);
        root.addView(title);
        TextView note = new TextView(this);
        note.setText("独立实验包，不读取正式应用账号。\n当前只开放受控测试线路；尚未通过登录与每环境代理验收。");
        note.setTextSize(13);
        root.addView(note);
        LinearLayout buttons = new LinearLayout(this);
        for (int i = 0; i < 2; i++) {
            final int index = i;
            Button button = new Button(this);
            button.setText("测试环境 " + (i + 1));
            button.setOnClickListener(v -> select(index));
            buttons.addView(button, new LinearLayout.LayoutParams(0, dp(44), 1));
        }
        root.addView(buttons);
        status = new TextView(this);
        status.setTextSize(12);
        status.setTextColor(Color.DKGRAY);
        status.setText("正在初始化官方预编译内核…");
        root.addView(status);
        view = new GeckoView(this);
        root.addView(view, new LinearLayout.LayoutParams(-1, 0, 1));
        setContentView(root);
        try {
            if (runtime == null) {
                File profile = new File(getNoBackupFilesDir(), "gecko-probe");
                profile.mkdirs();
                File config = new File(getNoBackupFilesDir(), "probe-runtime.yaml");
                // Fixed local SOCKS route also covers startup before extension readiness.
                // Never disable TLS validation or use a DIRECT fallback.
                String yaml = "prefs:\n"
                    + "  network.proxy.type: 1\n"
                    + "  network.proxy.socks: '127.0.0.1'\n"
                    + "  network.proxy.socks_port: 1080\n"
                    + "  network.proxy.socks_version: 5\n"
                    + "  network.proxy.socks_remote_dns: true\n"
                    + "  network.proxy.no_proxies_on: ''\n"
                    + "  network.proxy.allow_hijacking_localhost: true\n"
                    + "  network.trr.mode: 5\n"
                    + "  network.dns.disablePrefetch: true\n"
                    + "  network.prefetch-next: false\n"
                    + "  network.http.speculative-parallel-limit: 0\n";
                Files.write(config.toPath(), yaml.getBytes(StandardCharsets.UTF_8));
                runtime = GeckoRuntime.create(getApplicationContext(),
                    new GeckoRuntimeSettings.Builder()
                        .arguments(new String[]{"-profile", profile.getAbsolutePath()})
                        .configFilePath(config.getAbsolutePath())
                        .remoteDebuggingEnabled(false).consoleOutput(false)
                        .trustedRecursiveResolverMode(5)
                        .build());
            }
            runtime.getWebExtensionController().ensureBuiltIn(
                "resource://android/assets/probe/", "engine-probe@pocketchat.local")
                .accept(value -> { extension = value; attach(); },
                    error -> record("error", error.toString()));
        } catch (Exception error) { record("error", error.toString()); }
    }

    private final WebExtension.MessageDelegate messages = new WebExtension.MessageDelegate() {
        @Override public GeckoResult<Object> onMessage(String app, Object message,
                                                       WebExtension.MessageSender sender) {
            try {
                if (!"probe".equals(app) || !(message instanceof JSONObject)) return GeckoResult.fromValue(null);
                JSONObject data = (JSONObject) message;
                if ("fixture".equals(data.optString("kind"))) {
                    // Content native messages must come from one of our own sessions.
                    int index = sender.session == sessions[0] ? 0 : sender.session == sessions[1] ? 1 : -1;
                    if (index < 0 || sender.url == null || !sender.url.startsWith("http://127.0.0.1:8765/"))
                        return GeckoResult.fromValue(null);
                    data.put("nativeContext", "environment-" + (index + 1));
                }
                Log.i(TAG, data.toString());
                if ("fixture".equals(data.optString("kind")))
                    status.setText("环境 " + (selected + 1) + " · 已收到真实内核测试结果");
                return GeckoResult.fromValue(null);
            } catch (Exception error) { record("error", error.toString()); return GeckoResult.fromValue(null); }
        }
    };

    private void attach() {
        extension.setMessageDelegate(messages, "probe");
        for (int i = 0; i < sessions.length; i++) {
            GeckoSession session = new GeckoSession(new GeckoSessionSettings.Builder()
                .contextId("environment-" + (i + 1))
                .userAgentMode(GeckoSessionSettings.USER_AGENT_MODE_DESKTOP)
                .viewportMode(GeckoSessionSettings.VIEWPORT_MODE_DESKTOP).build());
            sessions[i] = session;
            session.setContentDelegate(new GeckoSession.ContentDelegate() {
                @Override public void onTitleChange(GeckoSession s, String title) {
                    int index = s == sessions[0] ? 0 : s == sessions[1] ? 1 : -1;
                    String prefix = "PocketEngineFixture:";
                    if (index < 0 || fixtureUris[index] == null || title == null || !title.startsWith(prefix)) return;
                    try {
                        JSONObject data = new JSONObject();
                        data.put("kind", "fixture");
                        data.put("result", new JSONObject(title.substring(prefix.length())));
                        data.put("nativeContext", "environment-" + (index + 1));
                        Log.i(TAG, data.toString());
                        status.setText("环境 " + (index + 1) + " · 已收到真实内核测试结果");
                    } catch (Exception error) { record("error", error.toString()); }
                }
            });
            session.setNavigationDelegate(new GeckoSession.NavigationDelegate() {
                @Override public GeckoResult<AllowOrDeny> onLoadRequest(GeckoSession s, LoadRequest request) {
                    // This proof package must not expose an unvalidated route to real accounts.
                    return GeckoResult.fromValue(request.uri.startsWith("http://127.0.0.1:8765/")
                        || request.uri.equals("about:blank") ? AllowOrDeny.ALLOW : AllowOrDeny.DENY);
                }
                @Override public GeckoResult<String> onLoadError(GeckoSession s, String uri, WebRequestError error) {
                    record("loadError", "code=" + error.code);
                    return null;
                }
            });
            session.open(runtime);
            session.getWebExtensionController().setMessageDelegate(extension, messages, "probe");
        }
        status.setText("两个存储环境已建立 · 受控代理未启动时保持断网");
        select(0);
        command(getIntent());
        record("initialized", "GeckoView 157.0.20260924084938");
    }

    private void select(int index) {
        selected = index;
        if (sessions[index] == null) return;
        if (view.getSession() != null) view.releaseSession();
        view.setSession(sessions[index]);
        sessions[index].setActive(true);
        status.setText("测试环境 " + (index + 1) + " · 官方 GeckoView");
    }

    @Override protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent); setIntent(intent); if (extension != null) command(intent);
    }

    private void command(Intent intent) {
        int index = intent.getIntExtra("context", 0);
        if (index < 0 || index > 1) return;
        String action = intent.getStringExtra("fixtureAction");
        if (!"seed".equals(action) && !"read".equals(action) && !"clear".equals(action)
            && !"network".equals(action)) return;
        select(index);
        if ("clear".equals(action)) {
            // The SDK's context-scoped API has no completion result. The fixture
            // reload and process restart verify its actual observable outcome.
            runtime.getStorageController().clearDataForSessionContext("environment-" + (index + 1));
            record("nativeClearRequested", "environment-" + (index + 1));
        }
        fixtureUris[index] = "http://127.0.0.1:8765/fixture?context=" + (index + 1) + "&action=" + action;
        sessions[index].loadUri(fixtureUris[index]);
    }

    private void record(String kind, String detail) {
        Log.i(TAG, "{\"kind\":\"" + kind + "\",\"detail\":" + JSONObject.quote(detail) + "}");
        status.setText(detail);
    }
    private int dp(int value) { return Math.round(value * getResources().getDisplayMetrics().density); }
    @Override protected void onDestroy() {
        if (view != null && view.getSession() != null) view.releaseSession();
        for (GeckoSession s : sessions) if (s != null && s.isOpen()) s.close();
        super.onDestroy();
    }
}
