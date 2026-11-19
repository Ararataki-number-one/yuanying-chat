package local.pocketchat.chromiumfixture;

import android.app.Activity;
import android.app.Instrumentation;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageInfo;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.ParcelFileDescriptor;
import android.os.SystemClock;
import android.util.Log;
import android.widget.TextView;
import org.json.JSONArray;
import org.json.JSONObject;

import com.cefrium.Cefrium;
import com.cefrium.CefriumBrowser;
import com.cefrium.CefriumContentResponse;
import com.cefrium.CefriumProfile;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.InputStream;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.net.InetAddress;
import java.security.KeyStore;
import java.security.MessageDigest;
import java.util.Locale;
import java.util.concurrent.Callable;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.FutureTask;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;
import javax.net.ssl.KeyManagerFactory;
import javax.net.ssl.SSLContext;
import javax.net.ssl.TrustManagerFactory;

/** Local, same-signer test for the production app's installed Chromium activity. */
public final class RouteFixture extends Instrumentation {
    private static final String TAG = "PocketChatCefriumRouteFixture";
    private static final String PACKAGE = "local.pocketchat";
    private static final String INTEGRATION_PACKAGE = PACKAGE + ".test";
    private static final String VPN_FIXTURE_IP = "2001:2::cafe";
    private static final String ENTRY = PACKAGE + ".MainActivity";
    private static final String CHROMIUM = PACKAGE + ".CefriumBrowserActivity";
    private static final String ORIGIN = "https://pocketchat-route-fixture.invalid";
    private Bundle arguments;

    @Override public void onCreate(Bundle arguments) {
        super.onCreate(arguments);
        this.arguments = arguments;
        start();
    }

    @Override public void onStart() {
        Bundle result = new Bundle();
        result.putString("scope", "production-debug-synthetic-signing-local-content");
        result.putBoolean("publicNetworkRouteVerified", false);
        result.putBoolean("tlsFixtureVerified", false);
        result.putBoolean("originTlsVerified", false);
        result.putBoolean("vpnRouteVerified", false);
        result.putBoolean("internalRouteVerified", false);
        result.putBoolean("inFlightPublicTrafficVerified", false);
        result.putBoolean("androidInstallerConfirmationVerified", false);
        result.putBoolean("geckoRenderingVerified", false);
        try {
            Context target = getTargetContext();
            PackageInfo info = verifyInstalledCandidate(target, result);
            String nonce = arguments.getString("runNonce", "");
            require(nonce.matches("[0-9a-f]{32}"), "Missing fixture nonce");
            result.putString("runNonce", nonce);
            String fixtureMode = arguments.getString("fixtureMode", "standard");
            require(noSystemWebView(), "A system WebView provider is active");
            result.putBoolean("noSystemWebViewProvider", true);
            require(hasInternetCapableNetwork(target), "Fixture needs a test-guest default Internet network");
            result.putBoolean("defaultNetworkInitiallyPresent", true);
            result.putInt("sdk", Build.VERSION.SDK_INT);
            result.putString("abi", Build.SUPPORTED_ABIS[0]);
            result.putLong("versionCode", info.getLongVersionCode());
            if (INTEGRATION_PACKAGE.equals(target.getPackageName())) {
                String source = verifyIntegrationSource(target, result);
                if ("vpn".equals(fixtureMode)) {
                    result.putString("scope", "integration-clean-source-android-tun");
                    exerciseVpn(target, result, nonce, source);
                } else if ("internal".equals(fixtureMode)) {
                    result.putString("scope", "integration-clean-source-android-internal");
                    exerciseInternal(target, result, nonce);
                } else {
                    throw new IllegalArgumentException("An explicit integration fixture mode is required");
                }
                result.putBoolean("androidExecution", true);
                require(noSystemWebView(), "The WebView provider changed during integration test");
                finish(Activity.RESULT_OK, result);
                return;
            }
            require("standard".equals(fixtureMode), "Unexpected production fixture mode");

            exerciseProtectedProxy(target, result, nonce, LoopbackProxy.Kind.HTTP, null);
            exerciseProtectedProxy(target, result, nonce, LoopbackProxy.Kind.SOCKS, null);
            exerciseTlsProxy(target, result, nonce);

            AtomicInteger served = new AtomicInteger();
            String title = "PocketChatRoute-" + nonce;
            CefriumProfile profile = onMain(() -> registerFixture(target, title, served));
            try {
                Activity activity = launchNormalEntry(target, ORIGIN + "/");
                require(activity.getClass().getName().equals(CHROMIUM), "Normal base entry did not open Chromium");
                CefriumBrowser browser = awaitBrowser(activity);
                awaitRenderedTitle(browser, title);
                require(served.get() > 0, "Registered no-socket fixture was never served");
                int renderers = onMain(CefriumBrowser::activeRenderProcessCount);
                require(renderers > 0, "No active native Chromium renderer");
                result.putString("chromiumVersion", onMain(Cefrium::getChromiumVersion));
                result.putInt("nativeRenderers", renderers);
                result.putBoolean("localContentRendered", true);

                disconnectGuestNetwork();
                long cutoff = SystemClock.elapsedRealtime() + 45_000;
                while (hasInternetCapableNetwork(target) && SystemClock.elapsedRealtime() < cutoff) {
                    SystemClock.sleep(250);
                }
                require(!hasInternetCapableNetwork(target), "Default network did not become unavailable");
                cutoff = SystemClock.elapsedRealtime() + 45_000;
                while (onMain(() -> field(activity, "browser")) != null && SystemClock.elapsedRealtime() < cutoff) {
                    SystemClock.sleep(250);
                }
                require(onMain(() -> field(activity, "browser")) == null, "The Chromium route was not retired");
                result.putBoolean("defaultNetworkLost", true);
                result.putBoolean("chromiumBrowserRetired", true);

                int requestsAtLoss = served.get();
                String blocked = onMain(() -> {
                    invoke(activity.getClass(), activity, "navigate", new Class<?>[]{String.class}, ORIGIN + "/after-loss");
                    return ((TextView)field(activity, "status")).getText().toString();
                });
                SystemClock.sleep(1_500);
                require(!blocked.isEmpty() && served.get() == requestsAtLoss
                        && onMain(() -> field(activity, "browser")) == null,
                        "Navigation after network loss did not remain closed");
                result.putString("visibleRouteStatus", blocked);
                result.putBoolean("navigationAfterLossWasBlocked", true);
                require(noSystemWebView(), "The WebView provider changed during Chromium test");
                result.putBoolean("androidExecution", true);
            } finally {
                onMain(() -> {
                    profile.unregisterContentServer(ORIGIN);
                    return null;
                });
            }
            finish(Activity.RESULT_OK, result);
        } catch (Exception | LinkageError failure) {
            Log.e(TAG, "Local Chromium route fixture failed", failure);
            result.putString("failure", failure.toString());
            finish(Activity.RESULT_CANCELED, result);
        }
    }

    private PackageInfo verifyInstalledCandidate(Context target, Bundle result) throws Exception {
        String packageName = target.getPackageName();
        require((PACKAGE.equals(packageName) || INTEGRATION_PACKAGE.equals(packageName))
                && "ranchu".equals(Build.HARDWARE)
                && "x86_64".equals(Build.SUPPORTED_ABIS[0]), "Only the disposable x86_64 emulator is supported");
        PackageInfo info = target.getPackageManager().getPackageInfo(packageName, 0);
        ApplicationInfo app = info.applicationInfo;
        require(INTEGRATION_PACKAGE.equals(packageName) || (app.flags & ApplicationInfo.FLAG_DEBUGGABLE) != 0,
                "Only the separate debug or integration candidates are supported");
        String baseSha = sha256(app.sourceDir);
        String featureSha = null;
        require(info.splitNames != null && app.splitSourceDirs != null
                && info.splitNames.length == app.splitSourceDirs.length, "Installed Chromium APK is missing");
        for (int i = 0; i < info.splitNames.length; i++) {
            if ("chromium".equals(info.splitNames[i])) featureSha = sha256(app.splitSourceDirs[i]);
        }
        require(baseSha.equals(arguments.getString("baseSha256"))
                && featureSha != null && featureSha.equals(arguments.getString("featureSha256")),
                "Installed APK digests differ from the expected synthetic candidate");
        result.putString("package", packageName);
        result.putString("baseSha256", baseSha);
        result.putString("featureSha256", featureSha);
        return info;
    }

    private String verifyIntegrationSource(Context target, Bundle result) throws Exception {
        JSONObject source;
        try (InputStream stream = target.getAssets().open("pocketchat-integration-build.json")) {
            source = new JSONObject(readBounded(stream, 8192));
        }
        String commit = arguments.getString("sourceCommit", "");
        String tree = arguments.getString("sourceTree", "");
        require(Build.VERSION.SDK_INT >= 33 && commit.matches("[0-9a-f]{40}") && tree.matches("[0-9a-f]{40}")
                && source.optInt("schema") == 1 && Boolean.FALSE.equals(source.opt("dirtySource"))
                && commit.equals(source.optString("sourceCommit")) && tree.equals(source.optString("sourceTree")),
                "Exact clean integration source and inspectable Android VPN required");
        result.putString("sourceCommit", commit);
        result.putString("sourceTree", tree);
        return commit;
    }

    private void exerciseVpn(Context target, Bundle result, String nonce, String source) throws Exception {
        require(!activeVpn(target), "Another VPN is already active before the isolated test");
        result.putBoolean("androidVpnConsentVerified", false);
        int port = 49152 + Integer.parseInt(nonce.substring(0, 4), 16) % 16000;
        String destination = InetAddress.getByName(VPN_FIXTURE_IP).getHostAddress();
        String url = "http://[" + VPN_FIXTURE_IP + "]:" + port + "/vpn-" + nonce;
        onMain(() -> {
            Context slot = environment(target);
            selectEnvironment(slot, "", true, url);
            target.startActivity(new Intent().setClassName(target.getPackageName(), ENTRY)
                    .putExtra("openWindowAction", "settings").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
            return null;
        });
        waitForIdleSync();
        JSONObject prepared = vpnControl(target, "prepare", nonce, source, -1);
        JSONObject prior = prepared.getJSONObject("state");
        long before = prior.optLong("generation", -1);
        require(prepared.optBoolean("prepared") && before == 0 && !prior.optBoolean("running"),
                "Fresh integration VPN consent must be prepared on the disposable guest");
        vpnControl(target, "start", nonce, source, before);

        long generation = 0;
        boolean stopped = false;
        Activity activity = null;
        try {
            long deadline = SystemClock.elapsedRealtime() + 30_000;
            while (SystemClock.elapsedRealtime() < deadline) {
                JSONObject state = vpnControl(target, "state", nonce, source, -1).getJSONObject("state");
                if (nonce.equals(state.optString("runNonce")) && source.equals(state.optString("sourceCommit"))) {
                    generation = state.optLong("generation");
                    require(state.optString("error").isEmpty(), "The owned VPN did not establish its TUN");
                    if (generation > 0 && state.optBoolean("running") && "full".equals(state.optString("mode"))
                            && Boolean.FALSE.equals(state.opt("forwardsTraffic")) && activeVpn(target)) break;
                }
                SystemClock.sleep(150);
            }
            require(generation > 0 && activeVpn(target), "Owned full TUN did not become the active default route");
            long navigationAt = SystemClock.elapsedRealtime();
            activity = launchNormalEntry(target, url);
            awaitBrowser(activity);
            JSONObject packet = null;
            deadline = SystemClock.elapsedRealtime() + 30_000;
            while (packet == null && SystemClock.elapsedRealtime() < deadline) {
                JSONObject state = ownedVpnState(target, nonce, source, generation);
                require(state.optBoolean("running") && activeVpn(target), "The VPN retired before observing the CEF attempt");
                JSONArray headers = state.getJSONArray("ipHeaders");
                for (int i = 0; i < headers.length(); i++) {
                    JSONObject header = headers.getJSONObject(i);
                    if (header.optInt("version") == 6 && header.optInt("nextHeader") == 6
                            && header.optInt("destinationPort") == port && destination.equals(header.optString("to"))
                            && header.optLong("at") >= navigationAt) {
                        packet = header;
                        break;
                    }
                }
                if (packet == null) SystemClock.sleep(150);
            }
            require(packet != null, "No exact CEF destination TCP attempt reached the owned VPN TUN");

            JSONObject stop = vpnControl(target, "stop", nonce, source, generation);
            require(stop.optBoolean("stopDispatched") && stop.optLong("stopGeneration") == generation,
                    "The exact owned VPN generation did not receive STOP");
            stopped = true;
            deadline = SystemClock.elapsedRealtime() + 45_000;
            while (SystemClock.elapsedRealtime() < deadline) {
                JSONObject state = ownedVpnState(target, nonce, source, generation);
                if (!state.optBoolean("running") && state.optBoolean("fdCloseSucceeded") && !activeVpn(target)) break;
                SystemClock.sleep(150);
            }
            JSONObject finalState = ownedVpnState(target, nonce, source, generation);
            require(!activeVpn(target) && !finalState.optBoolean("running") && finalState.optBoolean("fdCloseSucceeded")
                    && requestedVpnClose(finalState, generation), "The owned VPN descriptor did not close normally");
            awaitBrowserRetired(activity);
            Activity retired = activity;
            onMain(() -> {
                invoke(retired.getClass(), retired, "navigate", new Class<?>[]{String.class}, url);
                return null;
            });
            SystemClock.sleep(2_000);
            require(onMain(() -> field(retired, "browser")) == null, "CEF restarted without the required VPN");
            result.putBoolean("vpnRouteVerified", true);
            result.putBoolean("vpnTunPacketObserved", true);
            result.putBoolean("vpnDescriptorClosed", true);
            result.putBoolean("vpnBrowserRetired", true);
            result.putBoolean("vpnLateNavigationBlocked", true);
            result.putLong("vpnGeneration", generation);
            result.putInt("vpnDestinationPort", port);
        } finally {
            if (activity != null) {
                Activity closing = activity;
                onMain(() -> {
                    closing.finish();
                    return null;
                });
            }
            if (!stopped) {
                JSONObject cleanup = vpnControl(target, "state", nonce, source, -1).getJSONObject("state");
                long observed = cleanup.optLong("generation");
                if (cleanup.optBoolean("running") && observed > 0 && (generation == 0 || generation == observed)
                        && nonce.equals(cleanup.optString("runNonce")) && source.equals(cleanup.optString("sourceCommit"))) {
                    vpnControl(target, "stop", nonce, source, observed);
                }
            }
        }
    }

    private static JSONObject vpnControl(Context target, String method, String nonce, String source, long generation)
            throws Exception {
        Bundle arguments = new Bundle();
        arguments.putString("runNonce", nonce);
        arguments.putString("sourceCommit", source);
        arguments.putLong("generation", generation);
        Bundle reply = target.getContentResolver().call(Uri.parse("content://" + INTEGRATION_PACKAGE
                + ".queued-vpn-fixture"), method, null, arguments);
        require(reply != null, "No integration-only VPN response");
        JSONObject value = new JSONObject(reply.getString("json", ""));
        require(value.optInt("schema") == 1 && Boolean.TRUE.equals(value.opt("sameProcessServiceState"))
                && source.equals(value.optString("installedSource")) && value.optInt("providerPid") > 0,
                "Integration VPN source or IPC identity changed");
        return value;
    }

    private static JSONObject ownedVpnState(Context target, String nonce, String source, long generation)
            throws Exception {
        JSONObject state = vpnControl(target, "state", nonce, source, generation).getJSONObject("state");
        require(generation > 0 && state.optLong("generation") == generation && nonce.equals(state.optString("runNonce"))
                && source.equals(state.optString("sourceCommit")) && "full".equals(state.optString("mode"))
                && Boolean.FALSE.equals(state.opt("forwardsTraffic")), "VPN generation changed");
        return state;
    }

    private static boolean requestedVpnClose(JSONObject state, long generation) throws Exception {
        JSONArray events = state.getJSONArray("events");
        for (int i = 0; i < events.length(); i++) {
            JSONObject event = events.getJSONObject(i);
            if (event.optLong("generation") == generation && "tun-closed".equals(event.optString("kind"))
                    && "requested-stop".equals(event.optString("detail"))) return true;
        }
        return false;
    }

    private void exerciseInternal(Context target, Bundle result, String nonce) throws Exception {
        require(!activeVpn(target), "Internal fixture needs its clean non-VPN default network");
        String coreSha = arguments.getString("coreSha256", "");
        require(coreSha.matches("[0-9a-f]{64}"), "Expected the base APK's native core checksum");
        String title = "PocketChatInternal-" + nonce;
        try (LoopbackProxy origin = new LoopbackProxy(LoopbackProxy.Kind.INTERNAL, nonce, title, null)) {
            Bundle setup = new Bundle();
            setup.putInt("updatePort", origin.listenPort());
            setup.putString("chromiumFixtureHost", origin.host());
            setup.putInt("chromiumFixtureOriginPort", LoopbackProxy.ORIGIN_PORT);
            setup.putInt("chromiumFixtureLoopbackPort", origin.listenPort());
            Activity activity = null;
            try {
                onMain(() -> {
                    Context profile = environment(target);
                    selectBrowser(profile, origin.page());
                    target.startActivity(new Intent().setClassName(target.getPackageName(), ENTRY)
                            .putExtra("openWindowAction", "settings").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
                    return null;
                });
                waitForIdleSync();
                internalControl(target, "setup", setup);
                long deadline = SystemClock.elapsedRealtime() + 75_000;
                JSONObject admitted = internalControl(target, "state", null);
                while ((!admitted.optBoolean("ready") || !admitted.optBoolean("verified"))
                        && SystemClock.elapsedRealtime() < deadline) {
                    SystemClock.sleep(250);
                    admitted = internalControl(target, "state", null);
                }
                require(admitted.optBoolean("ready") && admitted.optBoolean("verified")
                        && admitted.optInt("corePid") > 0 && admitted.optInt("servicePid") > 0
                        && admitted.optLong("routeSerial") > 0 && admitted.optInt("proxyPort") > 0
                        && !admitted.optString("coreGeneration").isEmpty()
                        && coreSha.equals(admitted.optString("coreSha256"))
                        && admitted.optInt("chromiumFixtureCircuits", -1) == 0,
                        "The exact internal native core did not admit the owned isolated route");

                activity = launchNormalEntry(target, origin.page());
                CefriumBrowser browser = awaitBrowser(activity);
                requireMockRender(browser, origin, title);
                require(origin.pages.get() > 0, "No internal CEF page reached the locally owned origin");
                startHeldResponse(browser, origin);
                JSONObject inFlight = internalControl(target, "state", null);
                require(inFlight.optBoolean("ready") && inFlight.optBoolean("verified")
                        && admitted.optInt("corePid") == inFlight.optInt("corePid")
                        && admitted.optString("coreGeneration").equals(inFlight.optString("coreGeneration"))
                        && admitted.optLong("routeSerial") == inFlight.optLong("routeSerial")
                        && inFlight.optInt("chromiumFixtureCircuits") >= 2
                        && inFlight.optInt("entryAuthenticated") > admitted.optInt("entryAuthenticated")
                        && inFlight.optInt("fixedExitAuthenticated") > admitted.optInt("fixedExitAuthenticated"),
                        "Native Chromium traffic did not cross the matching authenticated entry and fixed exit");

                origin.beginSwitch();
                internalControl(target, "stop", null);
                origin.awaitRetired();
                awaitBrowserRetired(activity);
                JSONObject closed = internalControl(target, "state", null);
                require(Boolean.FALSE.equals(closed.opt("ready")) && Boolean.FALSE.equals(closed.opt("verified")),
                        "The owned internal route did not retire");
                int circuits = closed.optInt("chromiumFixtureCircuits");
                Activity retired = activity;
                onMain(() -> {
                    invoke(retired.getClass(), retired, "navigate", new Class<?>[]{String.class},
                            origin.origin() + "/after-stop-" + nonce);
                    return null;
                });
                SystemClock.sleep(2_000);
                require(onMain(() -> field(retired, "browser")) == null
                        && internalControl(target, "state", null).optInt("chromiumFixtureCircuits") == circuits,
                        "Stopped built-in route handled a late Chromium navigation");
                origin.validate();

                result.putBoolean("internalRouteVerified", true);
                result.putBoolean("internalMockPageRendered", true);
                result.putBoolean("internalCoreRetired", true);
                result.putBoolean("internalHeldSocketClosed", true);
                result.putBoolean("internalBrowserRetired", true);
                result.putBoolean("internalLateNavigationBlocked", true);
                result.putInt("internalAuthorizedCircuits", circuits);
                result.putInt("internalHeldConnectionsClosed", origin.heldConnectionsClosed.get());
                result.putString("internalCoreSha256", coreSha);
            } finally {
                if (activity != null) {
                    Activity closing = activity;
                    onMain(() -> {
                        closing.finish();
                        return null;
                    });
                    waitForIdleSync();
                }
                require(internalControl(target, "close", null).optBoolean("restored"),
                        "The test-owned internal environment did not restore");
            }
        }
    }

    private static JSONObject internalControl(Context target, String operation, Bundle params) throws Exception {
        Bundle receive = target.getContentResolver().call(Uri.parse("content://" + INTEGRATION_PACKAGE
                + ".test-update-route0"), operation, null, params);
        require(receive != null, "No private integration core response");
        JSONObject state = new JSONObject(receive.getString("json", ""));
        require(!state.has("error"), "Integration core control failed: " + state.optString("error"));
        return state;
    }

    private static Context environment(Context target) throws Exception {
        return (Context)invoke(target.getClassLoader().loadClass(PACKAGE + ".Profiles"), null,
                "context", new Class<?>[]{Context.class, int.class}, target, 0);
    }

    private CefriumProfile registerFixture(Context target, String title, AtomicInteger served) throws Exception {
        ClassLoader loader = target.getClassLoader();
        Class<?> profiles = loader.loadClass(PACKAGE + ".Profiles");
        Context global = (Context)invoke(profiles, null, "global", new Class<?>[]{Context.class}, target);
        Context environment = (Context)invoke(profiles, null, "context",
                new Class<?>[]{Context.class, int.class}, target, 0);
        Class<?> catalog = loader.loadClass(PACKAGE + ".ProfileCatalog");
        Object manager = invoke(catalog, null, "get", new Class<?>[]{Context.class}, target);
        Object identity = invoke(catalog, manager, "identity", new Class<?>[]{int.class}, 0);
        String name = (String)invoke(loader.loadClass(PACKAGE + ".ChromiumEntry"), null, "profileName",
                new Class<?>[]{identity.getClass()}, identity);

        selectEnvironment(environment, "", false, ORIGIN + "/");

        invoke(loader.loadClass(PACKAGE + ".CefriumRoute"), null, "configureEngine", new Class<?>[0]);
        Cefrium.setDataDirectory(new File(global.getNoBackupFilesDir(), "cefrium-browser"));
        require(Cefrium.initialize(target.getApplicationContext()), "Chromium initialization failed");
        CefriumProfile profile = CefriumProfile.get(name);
        profile.registerContentServer(ORIGIN, request -> {
            served.incrementAndGet();
            return CefriumContentResponse.ofText("text/html", "<!doctype html><title>" + title + "</title><h1>" + title + "</h1>")
                    .setHeader("Content-Security-Policy", "default-src 'none'");
        });
        return profile;
    }

    private void exerciseTlsProxy(Context target, Bundle result, String nonce) throws Exception {
        char[] password = "network-fixture".toCharArray();
        KeyStore fixture = KeyStore.getInstance("PKCS12");
        try (InputStream input = getContext().getAssets().open("chromium-proxy-fixture.p12")) {
            fixture.load(input, password);
        }
        KeyManagerFactory keys = KeyManagerFactory.getInstance(KeyManagerFactory.getDefaultAlgorithm());
        keys.init(fixture, password);
        KeyStore anchors = KeyStore.getInstance(KeyStore.getDefaultType());
        anchors.load(null, null);
        require(fixture.size() == 1, "Expected one synthetic fixture certificate");
        anchors.setCertificateEntry("chromium-fixture", fixture.getCertificate(fixture.aliases().nextElement()));
        TrustManagerFactory trust = TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm());
        trust.init(anchors);
        SSLContext server = SSLContext.getInstance("TLS");
        server.init(keys.getKeyManagers(), null, null);
        SSLContext client = SSLContext.getInstance("TLS");
        client.init(null, trust.getTrustManagers(), null);
        SSLContext previous = SSLContext.getDefault();
        try {
            SSLContext.setDefault(client);
            exerciseProtectedProxy(target, result, nonce, LoopbackProxy.Kind.HTTPS, server);
            result.putBoolean("tlsFixtureVerified", true);
        } finally {
            SSLContext.setDefault(previous);
        }
    }

    private void exerciseProtectedProxy(Context target, Bundle result, String nonce, LoopbackProxy.Kind kind,
                                        SSLContext tls) throws Exception {
        String prefix;
        switch (kind) {
            case HTTP: prefix = "protectedHttpProxy"; break;
            case HTTPS: prefix = "protectedHttpsProxy"; break;
            case SOCKS: prefix = "protectedSocksProxy"; break;
            default: throw new IllegalArgumentException("Expected an explicit fixture proxy");
        }
        String title = "PocketChatProtected-" + kind.scheme + "-" + nonce;
        try (LoopbackProxy proxy = new LoopbackProxy(kind, nonce, title, tls);
             LoopbackProxy.PrivateTrap trap = new LoopbackProxy.PrivateTrap()) {
            Context environment = onMain(() -> {
                Context slot = environment(target);
                selectEnvironment(slot, proxy.endpoint(), false, proxy.page());
                return slot;
            });
            Activity activity = launchNormalEntry(target, proxy.page());
            try {
                CefriumBrowser browser = awaitBrowser(activity);
                requireMockRender(browser, proxy, title);
                require(proxy.handshakes.get() > 0 && proxy.pages.get() > 0, "Rendered page did not traverse the selected mock");
                proxy.validate();

                String privateTarget = trap.url(nonce);
                String rejected = onMain(() -> {
                    invoke(activity.getClass(), activity, "navigate", new Class<?>[]{String.class}, privateTarget);
                    return ((TextView)field(activity, "status")).getText().toString();
                });
                require(!rejected.isEmpty(), "Address bar accepted a private origin");
                String bypassAttempt = "(()=>{fetch(" + JSONObject.quote(privateTarget)
                        + ",{mode:'no-cors',cache:'no-store'}).catch(()=>{});return 'dispatched';})()";
                require("\"dispatched\"".equals(evaluate(browser, bypassAttempt)), "Renderer did not attempt fixture bypass check");
                SystemClock.sleep(2_000);
                trap.validate();
                require(trap.accepted.get() == 0, "Browser bypassed its route and reached a private listener");
                proxy.validate();

                startHeldResponse(browser, proxy);
                require(!activeVpn(target), "The switch test requires an unavailable VPN route");
                proxy.beginSwitch();
                onMain(() -> {
                    selectEnvironment(environment, "", true, proxy.page());
                    return null;
                });
                proxy.awaitRetired();
                awaitBrowserRetired(activity);
                int requests = proxy.handshakes.get();
                onMain(() -> {
                    invoke(activity.getClass(), activity, "navigate", new Class<?>[]{String.class},
                            proxy.origin() + "/after-switch-" + nonce);
                    return null;
                });
                SystemClock.sleep(2_000);
                require(onMain(() -> field(activity, "browser")) == null && proxy.handshakes.get() == requests,
                        "Navigation after the switch opened another browser or reached the retired proxy");
                proxy.validate();
                trap.validate();
                require(trap.accepted.get() == 0, "Browser reached the private listener after the switch");

                result.putBoolean(prefix + "Handshake", true);
                result.putBoolean(prefix + "Rendered", true);
                result.putBoolean(prefix + "Revoked", true);
                result.putBoolean(prefix + "NoPrivateBypass", true);
                result.putInt(prefix + "HandshakeCount", proxy.handshakes.get());
                result.putInt(prefix + "PageCount", proxy.pages.get());
                result.putInt(prefix + "HeldConnectionsClosed", proxy.heldConnectionsClosed.get());
                result.putInt(prefix + "PrivateTrapAccepted", trap.accepted.get());
                if (kind == LoopbackProxy.Kind.HTTPS) {
                    require(proxy.tlsHandshakes.get() >= proxy.handshakes.get() && proxy.tlsHandshakes.get() > 0,
                            "No corresponding upstream TLS handshake was observed");
                    result.putInt(prefix + "TlsHandshakeCount", proxy.tlsHandshakes.get());
                }
            } finally {
                onMain(() -> {
                    activity.finish();
                    return null;
                });
                waitForIdleSync();
            }
        }
    }

    private void selectEnvironment(Context environment, String proxy, boolean requireVpn, String url)
            throws Exception {
        SharedPreferences preferences = environment.getSharedPreferences("chat", Context.MODE_PRIVATE);
        require(preferences.edit().putBoolean("networkConfigured", true).putString("networkMode", "external")
                .putString("proxy", proxy).putBoolean("requireExternalVpn", requireVpn).commit(),
                "Controlled fixture route could not be saved");
        selectBrowser(environment, url);
    }

    private static void selectBrowser(Context environment, String url) throws Exception {
        Object chosen = invoke(environment.getClassLoader().loadClass(PACKAGE + ".BrowserPreferences"),
                null, "save", new Class<?>[]{Context.class, boolean.class, String.class}, environment, true, url);
        require(Boolean.TRUE.equals(chosen), "Controlled Chromium selection could not be saved");
    }

    private static boolean activeVpn(Context context) {
        ConnectivityManager connections = context.getSystemService(ConnectivityManager.class);
        Network active = connections.getActiveNetwork();
        NetworkCapabilities capabilities = active == null ? null : connections.getNetworkCapabilities(active);
        return capabilities != null && capabilities.hasTransport(NetworkCapabilities.TRANSPORT_VPN);
    }

    private void awaitBrowserRetired(Activity activity) throws Exception {
        long cutoff = SystemClock.elapsedRealtime() + 45_000;
        while (onMain(() -> field(activity, "browser")) != null && SystemClock.elapsedRealtime() < cutoff) {
            SystemClock.sleep(250);
        }
        require(onMain(() -> field(activity, "browser")) == null, "The revoked Chromium browser was not retired");
    }

    private Activity launchNormalEntry(Context target, String url) throws Exception {
        ActivityMonitor monitor = addMonitor(CHROMIUM, null, false);
        try {
            onMain(() -> {
                target.startActivity(new Intent().setClassName(target.getPackageName(), ENTRY)
                        .putExtra("url", url).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
                return null;
            });
            Activity activity = waitForMonitorWithTimeout(monitor, 90_000);
            require(activity != null, "Base-to-Chromium Activity launch was not observed");
            return activity;
        } finally {
            removeMonitor(monitor);
        }
    }

    private CefriumBrowser awaitBrowser(Activity activity) throws Exception {
        long cutoff = SystemClock.elapsedRealtime() + 70_000;
        while (SystemClock.elapsedRealtime() < cutoff) {
            CefriumBrowser browser = onMain(() -> (CefriumBrowser)field(activity, "browser"));
            if (browser != null) return browser;
            SystemClock.sleep(250);
        }
        throw new IllegalStateException("Native Chromium browser was not created");
    }

    private void requireMockRender(CefriumBrowser browser, LoopbackProxy mock, String title) throws Exception {
        awaitRenderedTitle(browser, title);
        String dom = "document.getElementById('proof')?.textContent===" + JSONObject.quote(title)
                + "&&location.origin===" + JSONObject.quote(mock.origin());
        require("true".equals(evaluate(browser, dom)) && onMain(CefriumBrowser::activeRenderProcessCount) > 0,
                "Native Chromium did not render the isolated mock's DOM and origin");
    }

    private void startHeldResponse(CefriumBrowser browser, LoopbackProxy mock) throws Exception {
        String hold = "(()=>{window.__pocketchatHeld=fetch(" + JSONObject.quote(mock.heldPath())
                + ",{cache:'no-store'}).then(response=>response.text()).catch(()=>{});return 'dispatched';})()";
        require("\"dispatched\"".equals(evaluate(browser, hold)), "Renderer did not begin the held fixture request");
        mock.awaitHeld();
    }

    private void awaitRenderedTitle(CefriumBrowser browser, String title) throws Exception {
        long cutoff = SystemClock.elapsedRealtime() + 90_000;
        while (SystemClock.elapsedRealtime() < cutoff) {
            if (("\"" + title + "\"").equals(evaluate(browser, "document.title"))) return;
            SystemClock.sleep(350);
        }
        throw new IllegalStateException("Controlled local page did not render");
    }

    private String evaluate(CefriumBrowser browser, String script) throws Exception {
        AtomicReference<String> value = new AtomicReference<>();
        CountDownLatch callback = new CountDownLatch(1);
        onMain(() -> {
            browser.evaluateJavaScript(script, answer -> {
                value.set(answer);
                callback.countDown();
            });
            return null;
        });
        return callback.await(5, TimeUnit.SECONDS) ? value.get() : null;
    }

    private boolean noSystemWebView() throws Exception {
        return shell("dumpsys webviewupdate")
                .matches("(?is).*Current WebView package[^\\n]*(?:null|none).*");
    }

    private void disconnectGuestNetwork() throws Exception {
        shell("cmd connectivity airplane-mode enable");
        shell("svc wifi disable");
        shell("svc data disable");
        require(shell("settings get global airplane_mode_on").trim().equals("1"), "Could not isolate guest network");
    }

    private String shell(String command) throws Exception {
        ParcelFileDescriptor output = getUiAutomation().executeShellCommand(command);
        try (ParcelFileDescriptor.AutoCloseInputStream input = new ParcelFileDescriptor.AutoCloseInputStream(output)) {
            return readBounded(input, 262144);
        }
    }

    private static String readBounded(InputStream input, int limit) throws Exception {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        byte[] buffer = new byte[4096];
        for (int length; (length = input.read(buffer)) != -1; ) {
            require(bytes.size() + length <= limit, "Guest diagnostic output exceeded the fixture limit");
            bytes.write(buffer, 0, length);
        }
        return new String(bytes.toByteArray(), java.nio.charset.StandardCharsets.UTF_8);
    }

    private static boolean hasInternetCapableNetwork(Context context) {
        ConnectivityManager connections = context.getSystemService(ConnectivityManager.class);
        Network network = connections.getActiveNetwork();
        NetworkCapabilities capabilities = network == null ? null : connections.getNetworkCapabilities(network);
        return capabilities != null && capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET);
    }

    private <T> T onMain(Callable<T> action) throws Exception {
        FutureTask<T> operation = new FutureTask<>(action);
        runOnMainSync(operation);
        return operation.get();
    }

    private static Object field(Object owner, String name) throws Exception {
        Field field = owner.getClass().getDeclaredField(name);
        field.setAccessible(true);
        return field.get(owner);
    }

    private static Object invoke(Class<?> owner, Object target, String name, Class<?>[] params, Object... args)
            throws Exception {
        Method method = owner.getDeclaredMethod(name, params);
        method.setAccessible(true);
        return method.invoke(target, args);
    }

    private static String sha256(String path) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        try (FileInputStream input = new FileInputStream(path)) {
            byte[] buffer = new byte[65536];
            for (int length; (length = input.read(buffer)) != -1; ) digest.update(buffer, 0, length);
        }
        StringBuilder hex = new StringBuilder();
        for (byte value : digest.digest()) hex.append(String.format(Locale.ROOT, "%02x", value & 0xff));
        return hex.toString();
    }

    private static void require(boolean valid, String message) {
        if (!valid) throw new IllegalStateException(message);
    }
}
