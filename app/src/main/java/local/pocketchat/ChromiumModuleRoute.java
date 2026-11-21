package local.pocketchat;

import android.content.Context;
import android.net.ConnectivityManager;
import android.net.Network;

import java.io.IOException;
import java.net.Socket;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.function.BooleanSupplier;

/** Holds the selected environment route from the first metadata byte through install submission. */
final class ChromiumModuleRoute implements ChromiumRouteSocketOwner, AutoCloseable {
    private final Context profile;
    private final EnvironmentSpec.Identity identity;
    private final CefriumRoutePolicy.Selection selection;
    private final BooleanSupplier stopped;
    // TCP, optional TLS to an HTTPS proxy, then separately verified origin TLS.
    private final List<Socket> sockets = new ArrayList<>(3);
    private volatile ChromiumProtectedOwnerLease lease;
    private volatile boolean closed;
    private CefriumProtectedEndpoint endpoint;

    private ChromiumModuleRoute(Context profile, EnvironmentSpec.Identity identity,
                                CefriumRoutePolicy.Selection selection, BooleanSupplier stopped) {
        this.profile = profile;
        this.identity = identity;
        this.selection = selection;
        this.stopped = stopped;
    }

    static ChromiumModuleRoute acquire(Context context, EnvironmentSpec.Identity identity, BooleanSupplier stopped) throws IOException {
        if (stopped.getAsBoolean() || !ChromiumModuleInstaller.ownerCurrent(context, identity)) throw unavailable();
        Context profile = Profiles.context(context, identity.slot);
        CefriumRoutePolicy.Selection selected;
        try {
            selected = ProfileCatalog.get(profile).withIdentity(identity, () -> {
                if (stopped.getAsBoolean() || !BrowserPreferences.startBrowser(profile)) throw unavailable();
                return selection(profile);
            });
        } catch (IOException unavailable) {
            throw unavailable;
        } catch (Exception unavailable) {
            throw new IOException("下载 Chromium 的原环境已变化，未连接网络", unavailable);
        }
        if (selected == null) throw new IOException("请先在此环境配置用于下载 Chromium 的网络线路");
        ChromiumModuleRoute route = new ChromiumModuleRoute(profile, identity, selected, stopped);
        try {
            route.open();
            return route;
        } catch (IOException | RuntimeException failure) {
            route.close();
            throw failure;
        }
    }

    private void open() throws IOException {
        if (!configurationCurrent()) throw unavailable();
        if (selection.mode == CefriumRoutePolicy.Mode.INTERNAL) {
            ChromiumProtectedOwnerLease selected;
            try {
                selected = ChromiumProtectedOwnerLease.acquire(profile, identity, this::close);
            } catch (IOException unavailable) {
                if (closed || !configurationCurrent()) throw unavailable;
                startInternal();
                selected = ChromiumProtectedOwnerLease.acquire(profile, identity, this::close);
            }
            adopt(selected);
            endpoint = CefriumProtectedEndpoint.internal(selected.proxyPort(), this::verified);
        } else {
            ConnectivityManager manager = profile.getSystemService(ConnectivityManager.class);
            Network network = manager == null ? null : manager.getActiveNetwork();
            if (network == null || !configurationCurrent()) throw unavailable();
            adopt(ChromiumProtectedOwnerLease.acquireExternal(profile, identity, selection.proxyPreference,
                    selection.requireVpn, network.toString(), this::close));
            switch (selection.mode) {
                case FIXED_PROXY:
                    endpoint = CefriumProtectedEndpoint.fixed(network, selection.proxyEndpoint, this::verified);
                    break;
                case VPN:
                case DIRECT:
                    endpoint = CefriumProtectedEndpoint.onNetwork(network, this::verified);
                    break;
                default:
                    throw unavailable();
            }
        }
        requireVerified();
    }

    private void startInternal() throws IOException {
        CountDownLatch finished = new CountDownLatch(1);
        boolean[] started = {false};
        NetworkBridge.startChromiumInternal(profile, identity, (ok, message, state) -> {
            started[0] = ok;
            finished.countDown();
        });
        try {
            for (int wait = 0; wait < 180 && !closed && configurationCurrent(); wait++) {
                if (finished.await(1, TimeUnit.SECONDS)) {
                    if (started[0] && configurationCurrent()) return;
                    break;
                }
            }
        } catch (InterruptedException cancelled) {
            Thread.currentThread().interrupt();
        }
        throw new IOException("环境内置线路未能连接，Chromium 下载未开始");
    }

    private void adopt(ChromiumProtectedOwnerLease selected) throws IOException {
        synchronized (sockets) {
            if (!closed && !stopped.getAsBoolean()) {
                lease = selected;
                return;
            }
        }
        selected.close();
        throw unavailable();
    }

    private static CefriumRoutePolicy.Selection selection(Context context) {
        return CefriumRoutePolicy.selection(context.getSharedPreferences("chat", Context.MODE_PRIVATE).getAll());
    }

    private boolean configurationCurrent() {
        try {
            return !stopped.getAsBoolean() && ChromiumModuleInstaller.ownerCurrent(profile, identity)
                    && selection.equals(selection(profile)) && ChromiumModuleInstaller.ownerCurrent(profile, identity);
        } catch (RuntimeException unavailable) {
            return false;
        }
    }

    boolean verified() {
        ChromiumProtectedOwnerLease selected = lease;
        return current() && configurationCurrent() && selected != null && selected.recheck() && current();
    }

    void requireVerified() throws IOException {
        if (!verified()) {
            close();
            throw unavailable();
        }
    }

    Socket connect(String host, int port) throws IOException {
        requireVerified();
        return endpoint.openTunnel(host, port, this);
    }

    @Override public boolean current() {
        ChromiumProtectedOwnerLease selected = lease;
        return !closed && !stopped.getAsBoolean() && selected != null && selected.current();
    }

    @Override public void register(Socket socket) throws IOException {
        try {
            socket.setSoLinger(false, 0);
            synchronized (sockets) {
                if (current()) {
                    sockets.removeIf(Socket::isClosed);
                    if (sockets.contains(socket)) return;
                    if (sockets.size() < 3) {
                        sockets.add(socket);
                        return;
                    }
                }
            }
        } catch (IOException | RuntimeException failure) {
            closeSocket(socket);
            throw failure;
        }
        closeSocket(socket);
        throw unavailable();
    }

    void closeConnection() {
        synchronized (sockets) {
            // A raw close cuts writes before either TLS layer can send an alert or flush.
            for (Socket socket : sockets) closeSocket(socket);
            sockets.clear();
        }
    }

    @Override public void close() {
        ChromiumProtectedOwnerLease held;
        synchronized (sockets) {
            if (closed) return;
            closed = true;
            closeConnection();
            held = lease;
            lease = null;
        }
        if (held != null) NetworkBridge.worker.execute(held::close);
    }

    private static void closeSocket(Socket socket) {
        try { socket.close(); } catch (IOException | RuntimeException ignored) {}
    }

    private static IOException unavailable() {
        return new IOException("环境网络已变化，Chromium 下载已停止");
    }
}
