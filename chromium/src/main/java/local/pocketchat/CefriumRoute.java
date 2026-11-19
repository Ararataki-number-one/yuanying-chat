package local.pocketchat;

import android.content.Context;
import android.content.SharedPreferences;
import android.database.ContentObserver;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.LinkProperties;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;

import com.cefrium.Cefrium;
import com.cefrium.CefriumBrowser;
import com.cefrium.CefriumProfile;
import com.cefrium.CefriumProxyMode;
import com.cefrium.CefriumResourceInterceptor;
import com.cefrium.CefriumWebRtcIpPolicy;
import java.io.IOException;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.Executors;
import java.util.concurrent.RejectedExecutionException;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import java.util.function.BooleanSupplier;
import java.util.function.Consumer;

/** One foreground Chromium session bound to an explicit environment and route. */
final class CefriumRoute implements AutoCloseable {
    private static final long RECHECK_MS = 1000;
    private static final long MAX_EVIDENCE_AGE_MS = 2500;
    private static final String ROUTE_LOST = "环境或系统网络已变化，请重新打开网页";
    private static final String VERIFYING = "正在核验此环境的网络线路";
    private static final String PROXY_REALM = "PocketChat";
    private static final Map<String, CefriumRoute> PROFILE_OWNERS = new HashMap<>();
    private static final CefriumResourceInterceptor DENY = new CefriumResourceInterceptor() {
        @Override public boolean shouldBlockRequest(CefriumBrowser.ResourceRequest request) {
            return true;
        }
    };

    private final Context context;
    private final EnvironmentSpec.Identity identity;
    private final Runnable onLoss;
    private final ConnectivityManager connectivity;
    private final Handler main = new Handler(Looper.getMainLooper());
    private final ScheduledExecutorService reader = Executors.newSingleThreadScheduledExecutor(task -> {
        Thread thread = new Thread(task, "cefrium-route-check");
        thread.setPriority(Thread.NORM_PRIORITY - 1);
        return thread;
    });
    private final NetworkPoolIdentity.DefaultNetwork network = new NetworkPoolIdentity.DefaultNetwork();
    private final AtomicReference<Grant> grant = new AtomicReference<>();
    private volatile Grant attached;
    private volatile String failure = "";
    private volatile boolean closed;
    private SharedPreferences observedPreferences;
    private boolean observingNetwork;
    private boolean observingCatalog;
    private boolean watching;
    private CefriumProfile profile;
    private CefriumBrowser browser;

    private static final class Evidence {
        final CefriumRoutePolicy.Selection setting;
        final Network bound;
        final NetworkPoolIdentity.NetworkSnapshot connection;

        Evidence(CefriumRoutePolicy.Selection setting, Network bound,
                 NetworkPoolIdentity.NetworkSnapshot connection) {
            this.setting = setting;
            this.bound = bound;
            this.connection = connection;
        }
    }

    private static final class Grant {
        volatile Evidence evidence;
        volatile long verifiedAt;
        volatile boolean ready;
        volatile ChromiumProtectedOwnerLease owner;
        volatile CefriumProxyRelay relay;
        boolean disposed;
        boolean coreStartRequested;
        Consumer<Boolean> opened;

        Grant(Consumer<Boolean> opened) {
            this.opened = opened;
        }

        synchronized boolean adopt(ChromiumProtectedOwnerLease value) {
            if (disposed) return false;
            owner = value;
            return true;
        }

        synchronized boolean adopt(CefriumProxyRelay value) {
            if (disposed) return false;
            relay = value;
            return true;
        }

        void dispose() {
            final ChromiumProtectedOwnerLease ownerLease;
            final CefriumProxyRelay socketRelay;
            synchronized (this) {
                if (disposed) return;
                disposed = true;
                socketRelay = relay;
                ownerLease = owner;
                relay = null;
                owner = null;
            }
            // A slow binder release must never delay closing the traffic path.
            try {
                if (socketRelay != null) socketRelay.close();
            } finally {
                if (ownerLease != null) NetworkBridge.worker.execute(ownerLease::close);
            }
        }
    }

    private final ConnectivityManager.NetworkCallback networkCallback = new ConnectivityManager.NetworkCallback() {
        @Override public void onAvailable(Network value) {
            changeNetwork(() -> network.available(value.toString()));
        }
        @Override public void onLost(Network value) {
            changeNetwork(() -> network.lost(value.toString()));
        }
        @Override public void onCapabilitiesChanged(Network value, NetworkCapabilities capabilities) {
            changeNetwork(() -> network.capabilities(value.toString(),
                    capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET),
                    capabilities.hasTransport(NetworkCapabilities.TRANSPORT_VPN)));
        }
        @Override public void onLinkPropertiesChanged(Network value, LinkProperties links) {
            Grant current = grant.get();
            Evidence evidence = current == null ? null : current.evidence;
            if (evidence != null && !vpnCurrent(evidence)) revoke(current, ROUTE_LOST);
            else refreshSoon();
        }
    };
    private final SharedPreferences.OnSharedPreferenceChangeListener preferencesChanged = (preferences, key) -> {
        if (key == null || BrowserPreferences.KEY_START.equals(key) || "networkConfigured".equals(key)
                || "networkMode".equals(key) || "proxy".equals(key) || "requireExternalVpn".equals(key)) {
            Grant current = grant.get();
            Evidence evidence = current == null ? null : current.evidence;
            if (evidence != null && !evidence.setting.equals(selection())) revoke(current, ROUTE_LOST);
        }
    };
    private final ContentObserver catalogObserver = new ContentObserver(main) {
        @Override public void onChange(boolean self) { refreshSoon(); }
    };

    CefriumRoute(Context context, EnvironmentSpec.Identity identity, Runnable onLoss) {
        this.context = Profiles.context(context, identity.slot);
        this.identity = identity;
        this.onLoss = onLoss;
        connectivity = this.context.getSystemService(ConnectivityManager.class);
    }

    /** These startup traffic sources do not follow a named profile's proxy. */
    static void configureEngine() {
        Cefrium.setComponentUpdatesEnabled(false);
        Cefrium.setNetworkTimeQueriesEnabled(false);
        Cefrium.setDrmPreprovisioningAtStartupEnabled(false);
        if (Cefrium.areComponentUpdatesEnabled() || Cefrium.areNetworkTimeQueriesEnabled()
                || Cefrium.isDrmPreprovisioningAtStartupEnabled()) {
            throw new IllegalStateException("Chromium 的后台联网设置未生效");
        }
    }

    void open(String url, Consumer<Boolean> opened) {
        requireMainThread();
        if (closed || !BrowserAddressPolicy.allowed(url)) {
            opened.accept(false);
            return;
        }
        Grant current = grant.get();
        if (current != null) {
            if (current.ready) {
                current.opened = null;
                opened.accept(ready(current));
            } else {
                current.opened = opened;
            }
            return;
        }
        if (profile != null || browser != null || !watch()) {
            opened.accept(false);
            return;
        }
        Grant attempt = new Grant(opened);
        grant.set(attempt);
        failure = VERIFYING;
        try {
            reader.execute(() -> acquire(attempt));
        } catch (RejectedExecutionException unavailable) {
            revoke(attempt, "无法核验本环境的网络线路");
        }
    }

    /** Reuses an acquired receipt without doing owner IPC on the UI thread. */
    boolean mayStart(String url) {
        requireMainThread();
        return BrowserAddressPolicy.allowed(url) && ready(grant.get());
    }

    private void acquire(Grant attempt) {
        try {
            CefriumRoutePolicy.Selection approved = selection();
            if (approved == null || !currentEnvironment()) throw new IOException("请先确认此环境的网络设置");
            Evidence evidence = attempt.evidence;
            if (evidence == null) {
                synchronized (network) {
                    Network bound = sampleNetwork();
                    NetworkPoolIdentity.NetworkSnapshot connection = network.snapshot();
                    if (bound == null || !connection.usable()) throw new IOException("系统网络尚未连接");
                    evidence = new Evidence(approved, bound, connection);
                    attempt.evidence = evidence;
                }
            }
            if (!baseCurrent(attempt) || !configurationCurrent(evidence)) throw new IOException(ROUTE_LOST);
            if (!acquireOwner(attempt, evidence)) return;
            if (!verify(attempt)) return;
            attempt.ready = true;
            main.post(() -> complete(attempt));
        } catch (IOException unavailable) {
            revoke(attempt, unavailable.getMessage() == null ? "环境线路未通过核验" : unavailable.getMessage());
        } catch (RuntimeException unavailable) {
            revoke(attempt, "环境线路未通过核验");
        }
    }

    private boolean acquireOwner(Grant attempt, Evidence evidence) throws IOException {
        CefriumRoutePolicy.Selection setting = evidence.setting;
        if (!vpnCurrent(evidence)) throw new IOException("当前 VPN 路由覆盖尚未通过核验");
        Runnable revoked = () -> revoke(attempt, ROUTE_LOST);
        final ChromiumProtectedOwnerLease owner;
        try {
            owner = setting.mode == CefriumRoutePolicy.Mode.INTERNAL
                    ? ChromiumProtectedOwnerLease.acquire(context, identity, revoked)
                    : ChromiumProtectedOwnerLease.acquireExternal(context, identity, setting.proxyPreference,
                            setting.requireVpn, evidence.bound.toString(), revoked);
        } catch (IOException unavailable) {
            if (setting.mode != CefriumRoutePolicy.Mode.INTERNAL || attempt.coreStartRequested
                    || !baseCurrent(attempt) || !configurationCurrent(evidence)) throw unavailable;
            attempt.coreStartRequested = true;
            failure = "正在连接此环境的应用内线路";
            NetworkBridge.startChromiumInternal(context, identity, (ok, message, state) -> {
                if (!baseCurrent(attempt)) return;
                if (!ok) {
                    revoke(attempt, message);
                    return;
                }
                try {
                    reader.execute(() -> acquire(attempt));
                } catch (RejectedExecutionException retired) {
                    revoke(attempt, ROUTE_LOST);
                }
            });
            return false;
        }
        if (!attempt.adopt(owner)) {
            owner.close();
            throw new IOException(ROUTE_LOST);
        }
        if (!setting.protectedRoute()) return true;
        // The endpoint calls this on its worker before and after socket connect/handshake.
        BooleanSupplier exactOwner =
                () -> baseCurrent(attempt) && configurationCurrent(evidence) && owner.recheck();
        final CefriumProtectedEndpoint endpoint;
        switch (setting.mode) {
            case INTERNAL: endpoint = CefriumProtectedEndpoint.internal(owner.proxyPort(), exactOwner); break;
            case FIXED_PROXY: endpoint = CefriumProtectedEndpoint.fixed(evidence.bound, setting.proxyEndpoint, exactOwner); break;
            case VPN: endpoint = CefriumProtectedEndpoint.onNetwork(evidence.bound, exactOwner); break;
            default: throw new IOException("无效的受保护线路");
        }
        CefriumProxyRelay relay = new CefriumProxyRelay(endpoint::openTunnel, () -> ready(attempt));
        if (!attempt.adopt(relay)) {
            relay.close();
            throw new IOException(ROUTE_LOST);
        }
        return true;
    }

    private void complete(Grant attempt) {
        if (closed || grant.get() != attempt) return;
        if (!ready(attempt)) return;
        Consumer<Boolean> opened = attempt.opened;
        attempt.opened = null;
        failure = "";
        if (opened != null) opened.accept(true);
    }

    void prepare(CefriumProfile candidate) {
        requireMainThread();
        Grant selected = grant.get();
        String name = ChromiumEntry.profileName(identity);
        if (!ready(selected) || profile != null || candidate == null || candidate.isIncognito()
                || !name.equals(candidate.getName()) || PROFILE_OWNERS.containsKey(name)) throw rejected();
        // Detached workers have no browser lifetime to cancel when the route is revoked.
        candidate.setResourceInterceptor(DENY);
        CefriumProxyRelay relay = selected.relay;
        boolean protectedRoute = selected.evidence.setting.protectedRoute();
        if (!candidate.setWebRtcIpHandlingPolicy(CefriumWebRtcIpPolicy.DISABLE_NON_PROXIED_UDP)
                || !(protectedRoute ? relay != null
                        && candidate.setProxy(CefriumProxyMode.FIXED, "http://" + relay.endpoint())
                        : candidate.setProxy(CefriumProxyMode.DIRECT, ""))
                || !ready(selected)) {
            revoke(selected, "Chromium 的网络设置未通过核验");
            throw rejected();
        }
        profile = candidate;
        PROFILE_OWNERS.put(name, this);
    }

    void attach(CefriumBrowser candidate) {
        requireMainThread();
        if (candidate != null) candidate.setResourceInterceptor(DENY);
        Grant selected = grant.get();
        if (!ready(selected) || profile == null || browser != null || candidate == null
                || candidate.getProfile() != profile) throw rejected();
        browser = candidate;
        candidate.setResourceInterceptor(new CefriumResourceInterceptor() {
            @Override public boolean shouldBlockRequest(CefriumBrowser.ResourceRequest request) {
                if (request == null) return true;
                String target = request.url;
                if (target != null && target.startsWith("blob:")) {
                    target = CefriumFiles.downloadAddress(request.documentUrl, target);
                } else if (target != null && target.regionMatches(true, 0, "wss://", 0, 6)) {
                    target = "https://" + target.substring(6);
                } else if (target != null && target.regionMatches(true, 0, "ws://", 0, 5)) {
                    target = "http://" + target.substring(5);
                }
                return !allows(selected, target);
            }
        });
        attached = selected;
    }

    boolean authenticate(CefriumBrowser source, String host, String realm, int port, boolean isProxy,
                         CefriumBrowser.HttpAuthCallback callback) {
        requireMainThread();
        Grant selected = attached;
        if (source == null || source != browser || callback == null
                || !isProxy || !PROXY_REALM.equals(realm) || !"127.0.0.1".equals(host)
                || !ready(selected)) return false;
        CefriumProxyRelay relay = selected.relay;
        if (relay == null || !("127.0.0.1:" + port).equals(relay.endpoint())
                || !ready(selected)) return false;
        callback.proceed(relay.username(), relay.password());
        return true;
    }

    boolean allows(String url) { return allows(attached, url); }

    private boolean allows(Grant selected, String url) {
        return attached == selected && BrowserAddressPolicy.allowed(url) && ready(selected)
                && attached == selected;
    }

    private boolean ready(Grant selected) {
        if (selected == null || !selected.ready || closed || grant.get() != selected) return false;
        CefriumProxyRelay relay = selected.relay;
        ChromiumProtectedOwnerLease owner = selected.owner;
        if (!baseCurrent(selected) || SystemClock.elapsedRealtime() - selected.verifiedAt > MAX_EVIDENCE_AGE_MS
                || owner == null || !owner.current()
                || selected.evidence.setting.protectedRoute() && (relay == null || !relay.isOpen())) {
            revoke(selected, ROUTE_LOST);
            return false;
        }
        return grant.get() == selected;
    }

    private boolean baseCurrent(Grant selected) {
        Evidence expected = selected.evidence;
        return !closed && grant.get() == selected && expected != null
                && expected.connection.equals(network.snapshot());
    }

    private SharedPreferences preferences() {
        return context.getSharedPreferences("chat", Context.MODE_PRIVATE);
    }

    private CefriumRoutePolicy.Selection selection() {
        try {
            Map<String, ?> settings = preferences().getAll();
            if (!BrowserPreferences.START_BROWSER.equals(settings.get(BrowserPreferences.KEY_START))) return null;
            return CefriumRoutePolicy.selection(settings);
        } catch (RuntimeException unavailable) {
            return null;
        }
    }

    private boolean configurationCurrent(Evidence expected) {
        return expected.setting.equals(selection()) && currentEnvironment() && vpnCurrent(expected);
    }

    private boolean vpnCurrent(Evidence expected) {
        return expected.setting.mode != CefriumRoutePolicy.Mode.VPN
                || expected.connection.vpn && expected.bound.equals(connectivity.getActiveNetwork())
                    && BrowserNetworkGuard.vpnDefaultRouteIssue(context).isEmpty();
    }

    String blockedReason() {
        if (!currentEnvironment()) return "环境已变化，请重新打开";
        if (!failure.isEmpty()) return failure;
        return selection() == null ? "请先确认此环境的网络设置" : VERIFYING;
    }

    private boolean watch() {
        if (watching) return true;
        if (connectivity == null) {
            failure = "系统网络状态不可用";
            return false;
        }
        try {
            observedPreferences = preferences();
            observedPreferences.registerOnSharedPreferenceChangeListener(preferencesChanged);
            context.getContentResolver().registerContentObserver(DownloadLibraryChanges.uri(context), false, catalogObserver);
            observingCatalog = true;
            connectivity.registerDefaultNetworkCallback(networkCallback);
            observingNetwork = true;
            reader.scheduleWithFixedDelay(this::refresh, RECHECK_MS, RECHECK_MS, TimeUnit.MILLISECONDS);
            watching = true;
            return true;
        } catch (RuntimeException unavailable) {
            unwatch();
            failure = "无法持续确认系统网络";
            return false;
        }
    }

    // Caller holds the network monitor so a callback cannot replace the captured revision.
    private Network sampleNetwork() {
        Network active = connectivity.getActiveNetwork();
        NetworkCapabilities capabilities = active == null ? null : connectivity.getNetworkCapabilities(active);
        if (active == null || capabilities == null || !active.equals(connectivity.getActiveNetwork())) {
            network.unknown();
            return null;
        }
        network.initial(active.toString(),
                capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET),
                capabilities.hasTransport(NetworkCapabilities.TRANSPORT_VPN));
        return active;
    }

    private void changeNetwork(Runnable update) {
        final Grant current;
        final boolean changed;
        synchronized (network) {
            try {
                update.run();
            } catch (RuntimeException unavailable) {
                network.unknown();
            }
            current = grant.get();
            Evidence evidence = current == null ? null : current.evidence;
            changed = evidence != null && !evidence.connection.equals(network.snapshot());
        }
        if (changed) revoke(current, ROUTE_LOST);
    }

    private void refreshSoon() {
        try {
            reader.execute(this::refresh);
        } catch (RejectedExecutionException ignored) {
            // Closing invalidates the grant before stopping the reader.
        }
    }

    private void refresh() {
        Grant current = grant.get();
        if (!closed && current != null && current.ready) verify(current);
    }

    private boolean verify(Grant selected) {
        Evidence evidence = selected.evidence;
        if (evidence == null || closed || grant.get() != selected) return false;
        changeNetwork(this::sampleNetwork);
        ChromiumProtectedOwnerLease owner = selected.owner;
        boolean stillCurrent;
        try {
            CefriumProxyRelay relay = selected.relay;
            stillCurrent = baseCurrent(selected) && configurationCurrent(evidence)
                    && (!evidence.setting.protectedRoute() || relay != null && relay.isOpen())
                    && owner != null && owner.recheck();
        } catch (RuntimeException unavailable) {
            stillCurrent = false;
        }
        if (stillCurrent && baseCurrent(selected)) {
            selected.verifiedAt = SystemClock.elapsedRealtime();
            return true;
        }
        revoke(selected, ROUTE_LOST);
        return false;
    }

    private void revoke(Grant selected, String reason) {
        if (!grant.compareAndSet(selected, null)) return;
        failure = reason;
        boolean activeRelay = selected.relay != null;
        if (activeRelay) selected.dispose();
        if (!main.post(() -> {
            try {
                Consumer<Boolean> opened = selected.opened;
                selected.opened = null;
                if (closed) return;
                if (opened != null) opened.accept(false);
                if (attached == selected && onLoss != null) onLoss.run();
            } finally {
                if (!activeRelay) selected.dispose();
            }
        }) && !activeRelay) selected.dispose();
    }

    void retire(CefriumBrowser candidate) {
        requireMainThread();
        if (browser != null && browser != candidate) return;
        Grant retired = grant.getAndSet(null);
        attached = null;
        browser = null;
        if (profile != null) {
            PROFILE_OWNERS.remove(ChromiumEntry.profileName(identity), this);
            profile = null;
        }
        if (retired != null) retired.opened = null;
        boolean activeRelay = retired != null && retired.relay != null;
        if (activeRelay) retired.dispose();
        if (candidate != null) {
            try { candidate.setResourceInterceptor(DENY); } catch (RuntimeException ignored) {}
            try { candidate.stopLoading(); } catch (RuntimeException ignored) {}
        }
        if (retired != null && !activeRelay) retired.dispose();
    }

    private void unwatch() {
        if (observedPreferences != null) {
            observedPreferences.unregisterOnSharedPreferenceChangeListener(preferencesChanged);
            observedPreferences = null;
        }
        if (observingCatalog) {
            observingCatalog = false;
            try { context.getContentResolver().unregisterContentObserver(catalogObserver); }
            catch (RuntimeException ignored) {}
        }
        if (observingNetwork) {
            observingNetwork = false;
            try { connectivity.unregisterNetworkCallback(networkCallback); }
            catch (RuntimeException ignored) {}
        }
    }

    private boolean currentEnvironment() {
        try {
            EnvironmentSpecRuntime.requireIdentity(context, identity);
            return true;
        } catch (Exception unavailable) {
            return false;
        }
    }

    private static IllegalStateException rejected() {
        return new IllegalStateException("Chromium 环境或请求保护未通过核验");
    }

    private static void requireMainThread() {
        if (Looper.myLooper() != Looper.getMainLooper()) {
            throw new IllegalStateException("Chromium 请求保护必须在界面线程配置");
        }
    }

    @Override public void close() {
        requireMainThread();
        closed = true;
        retire(browser);
        unwatch();
        reader.shutdownNow();
    }
}
