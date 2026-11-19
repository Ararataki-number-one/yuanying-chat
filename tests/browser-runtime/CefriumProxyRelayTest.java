package local.pocketchat;

import java.io.ByteArrayOutputStream;
import java.io.EOFException;
import java.io.IOException;
import java.io.InputStream;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.net.SocketException;
import java.net.SocketTimeoutException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Base64;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

/** Uses only in-process TCP loopback fixtures. Destination host text is never resolved. */
public final class CefriumProxyRelayTest {
    private static final String HOST = "127.0.0.1";
    private static final int WAIT_MS = 4000;
    private static int checks;

    public static void main(String[] args) throws Exception {
        rejectsUnauthenticatedAndUnsafeRequests();
        tunnelsInBothDirections();
        forwardsOnlyOneFramedHttpRequest();
        cutsPendingHandshake();
        cutsUnadmittedTraffic();
        rejectsLateRegistration();
        tracksLayeredUpstreamHandles();
        limitsConcurrentRequests();
        System.out.println("Chromium proxy loopback checks passed: " + checks);
    }

    private static void rejectsUnauthenticatedAndUnsafeRequests() throws Exception {
        AtomicInteger opened = new AtomicInteger();
        CefriumProxyRelay.Upstream unused = (host, port, owner) -> {
            opened.incrementAndGet();
            throw new IOException("Unexpected tunnel");
        };
        try (CefriumProxyRelay relay = new CefriumProxyRelay(unused, () -> true);
             CefriumProxyRelay other = new CefriumProxyRelay(unused, () -> true)) {
            check(relay.endpoint().startsWith(HOST + ":") && !relay.endpoint().equals(other.endpoint()), "distinct loopback endpoints");
            check(!relay.username().equals(other.username()) && !relay.password().equals(other.password()), "independent credentials");
            String request = "CONNECT public.example:443 HTTP/1.1\r\nHost: public.example:443\r\n";
            String challenge = exchange(relay, request + "\r\n");
            check(challenge.startsWith("HTTP/1.1 407") && challenge.contains("Proxy-Authenticate: Basic"), "challenge without opening a tunnel");
            check(exchange(relay, request + credentials(other) + "\r\n").startsWith("HTTP/1.1 407"), "reject another session's credentials");
            String auth = credentials(relay);
            check(exchange(relay, request + auth + auth + "\r\n").startsWith("HTTP/1.1 400"), "reject duplicate authorization");
            check(exchange(relay, "CONNECT 127.0.0.1:443 HTTP/1.1\r\nHost: 127.0.0.1\r\n" + auth + "\r\n").startsWith("HTTP/1.1 403"), "reject private loopback target");
            check(exchange(relay, "CONNECT [::1]:443 HTTP/1.1\r\nHost: [::1]:443\r\n" + auth + "\r\n").startsWith("HTTP/1.1 403"), "reject private IPv6 target");
            check(exchange(relay, "CONNECT public.example:443 HTTP/1.1\r\nHost: different.example:443\r\n" + auth + "\r\n").startsWith("HTTP/1.1 400"), "target and Host must match");
            check(exchange(relay, request + auth + "Content-Length: 1\r\n\r\nx").startsWith("HTTP/1.1 400"), "CONNECT body prohibited");
            check(exchange(relay, request + auth + "X-Long: " + repeat('x', 9000) + "\r\n\r\n").startsWith("HTTP/1.1 431"), "bounded request header line");
            String post = "POST http://public.example/upload HTTP/1.1\r\nHost: public.example\r\n" + auth;
            check(exchange(relay, post + "Content-Length: 1\r\nContent-Length: 1\r\n\r\nx").startsWith("HTTP/1.1 400"), "reject duplicate framing");
            check(exchange(relay, post + "Transfer-Encoding: chunked\r\n\r\n0\r\n\r\n").startsWith("HTTP/1.1 501"), "reject unsupported transfer framing");
            check(exchange(relay, post + "Connection: upgrade\r\nUpgrade: websocket\r\n\r\n").startsWith("HTTP/1.1 400"), "reject plaintext socket upgrade");
            check(opened.get() == 0, "no upstream connection for disallowed traffic");
        }
    }

    private static void tunnelsInBothDirections() throws Exception {
        AtomicReference<String> destination = new AtomicReference<>();
        ExecutorService upstreamThread = Executors.newSingleThreadExecutor();
        try (ServerSocket remote = peer();
             CefriumProxyRelay relay = new CefriumProxyRelay((host, port, owner) -> {
                 destination.set(host + ":" + port);
                 return localTunnel(remote, owner);
             }, () -> true)) {
            Future<String> observed = upstreamThread.submit(() -> {
                try (Socket upstream = remote.accept()) {
                    upstream.setSoTimeout(WAIT_MS);
                    String payload = exact(upstream.getInputStream(), 5);
                    if (upstream.getInputStream().read() != -1) throw new AssertionError("Leaked headers or no half close");
                    write(upstream, "world");
                    upstream.shutdownOutput();
                    return payload;
                }
            });
            try (Socket browser = browser(relay)) {
                // Simulate an optimistic client whose first payload shares the header read buffer.
                write(browser, "CONNECT Public.Example:00443 HTTP/1.1\r\nHost: public.example:443\r\n"
                        + credentials(relay) + "\r\nhello");
                check(headers(browser.getInputStream()).startsWith("HTTP/1.1 200 Connection Established"), "successful CONNECT");
                browser.shutdownOutput();
                check(exact(browser.getInputStream(), 5).equals("world") && browser.getInputStream().read() == -1, "upstream response survived half-close");
                check(observed.get(WAIT_MS, TimeUnit.MILLISECONDS).equals("hello"), "only tunnel payload reached upstream");
                check("public.example:443".equals(destination.get()), "canonical host and port passed to protected route");
            }
        } finally {
            upstreamThread.shutdownNow();
        }
    }

    private static void forwardsOnlyOneFramedHttpRequest() throws Exception {
        AtomicReference<String> destination = new AtomicReference<>();
        ExecutorService upstreamThread = Executors.newSingleThreadExecutor();
        try (ServerSocket remote = peer();
             CefriumProxyRelay relay = new CefriumProxyRelay((host, port, owner) -> {
                 destination.set(host + ":" + port);
                 return localTunnel(remote, owner);
             }, () -> true)) {
            Future<String> observed = upstreamThread.submit(() -> {
                try (Socket upstream = remote.accept()) {
                    upstream.setSoTimeout(WAIT_MS);
                    InputStream input = upstream.getInputStream();
                    String request = headers(input) + exact(input, 4);
                    upstream.setSoTimeout(250);
                    try {
                        if (input.read() != -1) throw new AssertionError("A pipelined request crossed the proxy");
                    } catch (SocketTimeoutException expected) {}
                    write(upstream, "HTTP/1.1 200 OK\r\nConnection: close\r\nContent-Length: 2\r\n\r\nok");
                    return request;
                }
            });
            try (Socket browser = browser(relay)) {
                write(browser, "POST http://Public.Example/form?q=1 HTTP/1.1\r\nHost: public.example\r\n"
                        + credentials(relay) + "Proxy-Connection: keep-alive\r\n"
                        + "Connection: X-Drop\r\nX-Drop: secret-hop\r\nX-Keep: end-to-end\r\nContent-Length: 4\r\n\r\n"
                        + "bodyGET http://different.example/ HTTP/1.1\r\nHost: different.example\r\n\r\n");
                check(headers(browser.getInputStream()).startsWith("HTTP/1.1 200 OK") && exact(browser.getInputStream(), 2).equals("ok"), "framed HTTP response is returned");
                String request = observed.get(WAIT_MS, TimeUnit.MILLISECONDS).toLowerCase(Locale.ROOT);
                check(request.startsWith("post /form?q=1 http/1.1\r\nhost: public.example\r\n"), "origin-form request and regenerated Host");
                check(request.contains("x-keep: end-to-end") && request.endsWith("\r\n\r\nbody"), "end-to-end headers and exact body retained");
                check(!request.contains("proxy-") && !request.contains("x-drop") && request.contains("connection: close"), "strip proxy credentials and hop headers");
                check("public.example:80".equals(destination.get()), "ordinary HTTP uses admitted target port");
            }
        } finally {
            upstreamThread.shutdownNow();
        }
    }

    private static void cutsPendingHandshake() throws Exception {
        CountDownLatch connected = new CountDownLatch(1);
        AtomicReference<Socket> registered = new AtomicReference<>();
        try (ServerSocket remote = peer();
             CefriumProxyRelay relay = new CefriumProxyRelay((host, port, owner) -> {
                 Socket upstream = localTunnel(remote, owner);
                 registered.set(upstream);
                 connected.countDown();
                 upstream.getInputStream().read();      // No completed protected handshake yet.
                 return upstream;
             }, () -> true);
             Socket browser = browser(relay)) {
            write(browser, "CONNECT public.example:443 HTTP/1.1\r\nHost: public.example:443\r\n" + credentials(relay) + "\r\n");
            try (Socket upstreamPeer = remote.accept()) {
                upstreamPeer.setSoTimeout(WAIT_MS);
                check(connected.await(WAIT_MS, TimeUnit.MILLISECONDS), "pending protected handshake registered");
                relay.close();
                check(!relay.isOpen() && registered.get().isClosed(), "revoke synchronously closes registered pending upstream");
                check(browser.getInputStream().read() == -1 && upstreamPeer.getInputStream().read() == -1, "revoke cuts both endpoints");
            }
        }
    }

    private static void cutsUnadmittedTraffic() throws Exception {
        AtomicBoolean admitted = new AtomicBoolean(true);
        try (ServerSocket remote = peer();
             CefriumProxyRelay relay = new CefriumProxyRelay((host, port, owner) -> localTunnel(remote, owner), admitted::get);
             Socket browser = browser(relay)) {
            write(browser, "CONNECT public.example:443 HTTP/1.1\r\nHost: public.example:443\r\n" + credentials(relay) + "\r\n");
            try (Socket upstreamPeer = remote.accept()) {
                upstreamPeer.setSoTimeout(WAIT_MS);
                check(headers(browser.getInputStream()).startsWith("HTTP/1.1 200"), "admitted route is initially active");
                admitted.set(false);
                write(upstreamPeer, "new payload after route loss");
                check(browser.getInputStream().read() == -1 && upstreamPeer.getInputStream().read() == -1,
                        "no upstream bytes are forwarded after route loss");
            }
        }
    }

    private static void rejectsLateRegistration() throws Exception {
        AtomicBoolean live = new AtomicBoolean(true);
        CountDownLatch entered = new CountDownLatch(1), proceed = new CountDownLatch(1), checked = new CountDownLatch(1);
        AtomicBoolean closed = new AtomicBoolean();
        try (CefriumProxyRelay relay = new CefriumProxyRelay((host, port, owner) -> {
            entered.countDown();
            try {
                if (!proceed.await(WAIT_MS, TimeUnit.MILLISECONDS)) throw new IOException("Test deadline");
            } catch (InterruptedException interrupted) {
                Thread.currentThread().interrupt();
            }
            Socket socket = new Socket();
            try {
                owner.register(socket);
                throw new AssertionError("Accepted a revoked owner");
            } catch (IOException revoked) {
                closed.set(socket.isClosed());
                checked.countDown();
                throw revoked;
            }
        }, live::get);
             Socket browser = browser(relay)) {
            write(browser, "CONNECT public.example:443 HTTP/1.1\r\nHost: public.example:443\r\n" + credentials(relay) + "\r\n");
            check(entered.await(WAIT_MS, TimeUnit.MILLISECONDS), "registered request waits for upstream allocation");
            live.set(false);
            proceed.countDown();
            check(checked.await(WAIT_MS, TimeUnit.MILLISECONDS) && closed.get(), "closed route rejects and closes late allocation");
            check(!relay.isOpen() && browser.getInputStream().read() == -1, "failed route validator retires listener and client");
        }
    }

    private static void tracksLayeredUpstreamHandles() throws Exception {
        CountDownLatch registered = new CountDownLatch(1), retire = new CountDownLatch(1);
        AtomicReference<Socket> raw = new AtomicReference<>(), layered = new AtomicReference<>(), excess = new AtomicReference<>();
        AtomicBoolean rejectedExcess = new AtomicBoolean();
        List<String> closed = java.util.Collections.synchronizedList(new ArrayList<>());
        try (CefriumProxyRelay relay = new CefriumProxyRelay((host, port, owner) -> {
            Socket failedAttempt = new Socket();
            owner.register(failedAttempt);
            failedAttempt.close();
            raw.set(recordClosure(closed, "raw"));
            layered.set(recordClosure(closed, "layered"));
            owner.register(raw.get());
            owner.register(layered.get());
            excess.set(new Socket());
            try { owner.register(excess.get()); }
            catch (IOException bounded) { rejectedExcess.set(excess.get().isClosed()); }
            registered.countDown();
            try { retire.await(WAIT_MS, TimeUnit.MILLISECONDS); }
            catch (InterruptedException interrupted) { Thread.currentThread().interrupt(); }
            throw new IOException("Synthetic upstream stopped");
        }, () -> true);
             Socket browser = browser(relay)) {
            write(browser, "CONNECT public.example:443 HTTP/1.1\r\nHost: public.example:443\r\n" + credentials(relay) + "\r\n");
            check(registered.await(WAIT_MS, TimeUnit.MILLISECONDS) && rejectedExcess.get(), "allow a replacement and bound raw plus layered handles");
            relay.close();
            check(raw.get().isClosed() && layered.get().isClosed() && closed.equals(java.util.Arrays.asList("raw", "layered")),
                    "raw transport closes synchronously before its TLS layer");
        } finally {
            retire.countDown();
        }
    }

    private static Socket recordClosure(List<String> closed, String layer) {
        return new Socket() {
            @Override public void close() throws IOException {
                closed.add(layer);
                super.close();
            }
        };
    }

    private static void limitsConcurrentRequests() throws Exception {
        CountDownLatch active = new CountDownLatch(16), exit = new CountDownLatch(1);
        List<Socket> browsers = new ArrayList<>();
        try (CefriumProxyRelay relay = new CefriumProxyRelay((host, port, owner) -> {
            active.countDown();
            try {
                exit.await(WAIT_MS, TimeUnit.MILLISECONDS);
            } catch (InterruptedException interrupted) {
                Thread.currentThread().interrupt();
            }
            throw new IOException("Test route stopped");
        }, () -> true)) {
            for (int count = 0; count < 16; count++) {
                Socket browser = browser(relay);
                browsers.add(browser);
                write(browser, "CONNECT public.example:443 HTTP/1.1\r\nHost: public.example:443\r\n" + credentials(relay) + "\r\n");
            }
            check(active.await(WAIT_MS, TimeUnit.MILLISECONDS), "all bounded slots reached the protected callback");
            try (Socket overflow = browser(relay)) {
                boolean closed;
                try { closed = overflow.getInputStream().read() == -1; }
                catch (SocketException rejected) { closed = true; }
                check(closed, "excess client is closed while transport is busy");
            }
        } finally {
            exit.countDown();
            for (Socket browser : browsers) browser.close();
        }
    }

    private static ServerSocket peer() throws IOException {
        ServerSocket server = new ServerSocket(0, 1, InetAddress.getByAddress(new byte[]{127, 0, 0, 1}));
        server.setSoTimeout(WAIT_MS);
        return server;
    }

    private static Socket localTunnel(ServerSocket peer, CefriumProxyRelay.SocketRegistry owner) throws IOException {
        Socket socket = new Socket();
        owner.register(socket);
        socket.connect(new InetSocketAddress(HOST, peer.getLocalPort()), WAIT_MS);
        return socket;
    }

    private static Socket browser(CefriumProxyRelay relay) throws IOException {
        Socket socket = new Socket();
        socket.connect(new InetSocketAddress(HOST, Integer.parseInt(relay.endpoint().substring(HOST.length() + 1))), WAIT_MS);
        socket.setSoTimeout(WAIT_MS);
        return socket;
    }

    private static String credentials(CefriumProxyRelay relay) {
        String value = relay.username() + ":" + relay.password();
        return "Proxy-Authorization: Basic " + Base64.getEncoder().encodeToString(value.getBytes(StandardCharsets.US_ASCII)) + "\r\n";
    }

    private static String exchange(CefriumProxyRelay relay, String request) throws IOException {
        try (Socket socket = browser(relay)) {
            write(socket, request);
            return headers(socket.getInputStream());
        }
    }

    private static String headers(InputStream input) throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        int tail = 0;
        while (bytes.size() < 32768) {
            int next = input.read();
            if (next < 0) throw new EOFException();
            bytes.write(next);
            tail = tail << 8 | next;
            if (tail == 0x0d0a0d0a) return new String(bytes.toByteArray(), StandardCharsets.ISO_8859_1);
        }
        throw new IOException("Fixture headers too large");
    }

    private static String exact(InputStream input, int count) throws IOException {
        byte[] bytes = new byte[count];
        for (int offset = 0; offset < bytes.length;) {
            int read = input.read(bytes, offset, bytes.length - offset);
            if (read < 0) throw new EOFException();
            offset += read;
        }
        return new String(bytes, StandardCharsets.ISO_8859_1);
    }

    private static void write(Socket target, String value) throws IOException {
        target.getOutputStream().write(value.getBytes(StandardCharsets.ISO_8859_1));
        target.getOutputStream().flush();
    }

    private static String repeat(char ch, int count) {
        StringBuilder value = new StringBuilder(count);
        for (int i = 0; i < count; i++) value.append(ch);
        return value.toString();
    }

    private static void check(boolean result, String name) {
        if (!result) throw new AssertionError(name);
        checks++;
    }
}
