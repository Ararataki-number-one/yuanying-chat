package local.pocketchat.chromiumfixture;

import java.io.BufferedInputStream;
import java.io.EOFException;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.net.SocketException;
import java.net.SocketTimeoutException;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;
import javax.net.ssl.SSLContext;
import javax.net.ssl.SSLSocket;

/** A confined upstream endpoint. It never resolves IP addresses or opens outbound sockets. */
final class LoopbackProxy implements AutoCloseable {
    static final int ORIGIN_PORT = 8081;
    private static final int MAX_LINE = 8192;
    private static final int MAX_CONNECTIONS = 16;
    private static final byte[] LOOPBACK = {127, 0, 0, 1};

    enum Kind {
        HTTP("http"), HTTPS("https"), SOCKS("socks"), INTERNAL("internal");

        final String scheme;

        Kind(String scheme) { this.scheme = scheme; }
    }

    interface Response { boolean serve(String request, String cookies, OutputStream output) throws IOException; }

    private final Kind kind;
    private final Response response;
    private final String host;
    private final String nonce;
    private final String title;
    private final ServerSocket listener;
    private final Set<Socket> clients = ConcurrentHashMap.newKeySet();
    private final AtomicReference<IOException> invalid = new AtomicReference<>();
    private final AtomicBoolean stopping = new AtomicBoolean();
    private final AtomicBoolean switching = new AtomicBoolean();
    private final CountDownLatch held = new CountDownLatch(1);
    private final CountDownLatch retired = new CountDownLatch(1);
    private final AtomicInteger connections = new AtomicInteger();
    final AtomicInteger handshakes = new AtomicInteger();
    final AtomicInteger tlsHandshakes = new AtomicInteger();
    final AtomicInteger pages = new AtomicInteger();
    final AtomicInteger heldRequests = new AtomicInteger();
    final AtomicInteger heldConnectionsClosed = new AtomicInteger();

    LoopbackProxy(Kind kind, String nonce, String title, SSLContext tls) throws IOException {
        this(kind, nonce, title, tls, null);
    }

    LoopbackProxy(Kind kind, String nonce, String title, SSLContext tls, Response response) throws IOException {
        if (response != null && kind != Kind.HTTP) throw new IOException("Only the confined HTTP fixture supplies extra pages");
        this.kind = kind;
        this.response = response;
        this.nonce = nonce;
        this.title = title;
        host = "pocketchat-" + kind.scheme + "-" + nonce + ".invalid";
        if ((kind == Kind.HTTPS) != (tls != null)) throw new IOException("TLS fixture does not match proxy mode");
        listener = listener(tls);
        daemon(this::accept, "pocketchat-proxy-fixture").start();
    }

    int listenPort() { return listener.getLocalPort(); }
    String host() { return host; }
    String endpoint() { return kind.scheme + "://127.0.0.1:" + listenPort(); }
    String origin() { return "http://" + host + ":" + ORIGIN_PORT; }
    String page() { return origin() + "/page-" + nonce; }
    String heldPath() { return "/held-" + nonce; }

    void awaitHeld() throws Exception {
        if (!held.await(45, TimeUnit.SECONDS)) throw new IOException("No incomplete upstream response was observed");
        validate();
        if (heldRequests.get() != 1 || heldConnectionsClosed.get() != 0) {
            throw new IOException("Expected one live upstream response before route switch");
        }
    }

    void beginSwitch() { switching.set(true); }

    void awaitRetired() throws Exception {
        if (!retired.await(45, TimeUnit.SECONDS)) throw new IOException("Upstream socket did not close after route switch");
        validate();
        if (heldConnectionsClosed.get() != 1) throw new IOException("Unexpected retired upstream socket count");
    }

    void validate() throws IOException {
        IOException failure = invalid.get();
        if (failure != null) throw failure;
    }

    private void accept() {
        try {
            while (!stopping.get()) {
                Socket client = listener.accept();
                clients.add(client);
                if (stopping.get() || connections.incrementAndGet() > MAX_CONNECTIONS) {
                    close(client);
                    clients.remove(client);
                    if (!stopping.get()) reject("Too many connections to the confined upstream mock");
                    continue;
                }
                daemon(() -> serve(client), "pocketchat-proxy-fixture-client").start();
            }
        } catch (IOException failure) {
            if (!stopping.get()) invalid.compareAndSet(null, failure);
        }
    }

    private void serve(Socket client) {
        try (Socket socket = client) {
            socket.setSoTimeout(30_000);
            if (kind == Kind.HTTPS) {
                requireTls(socket);
                tlsHandshakes.incrementAndGet();
            }
            BufferedInputStream input = new BufferedInputStream(socket.getInputStream());
            OutputStream output = socket.getOutputStream();
            if (kind != Kind.INTERNAL) {
                if (kind == Kind.SOCKS) expectSocks(input, output);
                else expectConnect(input, output);
                handshakes.incrementAndGet();
            }
            String request = line(input);
            Headers headers = headers(input);
            String authority = host + ":" + ORIGIN_PORT;
            if (!authority.equals(headers.host) || headers.proxyAuthorization) {
                throw new IOException("Upstream HTTP request used a different authority or leaked proxy credentials");
            }
            if (response != null && response.serve(request, headers.cookies, output)) return;
            if (("GET /page-" + nonce + " HTTP/1.1").equals(request)) {
                pages.incrementAndGet();
                page(output);
            } else if (("GET " + heldPath() + " HTTP/1.1").equals(request)) {
                heldResponse(socket, input, output);
            } else if ("GET /favicon.ico HTTP/1.1".equals(request)) {
                write(output, "HTTP/1.1 404 Not Found\r\nConnection: close\r\nContent-Length: 0\r\n\r\n");
            } else {
                throw new IOException("Unexpected HTTP request to the confined upstream mock");
            }
        } catch (IOException failure) {
            if (!stopping.get()) invalid.compareAndSet(null, failure);
        } finally {
            clients.remove(client);
        }
    }

    private void expectConnect(InputStream input, OutputStream output) throws IOException {
        String authority = host + ":" + ORIGIN_PORT;
        String request = line(input);
        Headers headers = headers(input);
        if (!("CONNECT " + authority + " HTTP/1.1").equals(request)
                || !authority.equals(headers.host) || headers.proxyAuthorization) {
            throw new IOException("HTTP mock requires exact fixture-target CONNECT without relay credentials");
        }
        write(output, "HTTP/1.1 200 Connection Established\r\n\r\n");
    }

    private void expectSocks(InputStream input, OutputStream output) throws IOException {
        if (octet(input) != 5 || octet(input) != 1 || octet(input) != 0) {
            throw new IOException("SOCKS5 mock requires only no-auth negotiation");
        }
        output.write(new byte[]{5, 0});
        output.flush();
        if (octet(input) != 5 || octet(input) != 1 || octet(input) != 0 || octet(input) != 3) {
            throw new IOException("SOCKS5 mock requires a domain-based CONNECT");
        }
        byte[] domain = new byte[octet(input)];
        for (int i = 0; i < domain.length; i++) domain[i] = (byte)octet(input);
        int port = (octet(input) << 8) | octet(input);
        if (!host.equals(new String(domain, StandardCharsets.US_ASCII)) || port != ORIGIN_PORT) {
            throw new IOException("SOCKS5 mock was asked to connect outside the fixture origin");
        }
        output.write(new byte[]{5, 0, 0, 1, 127, 0, 0, 1, 0, 0});
        output.flush();
    }

    private void page(OutputStream output) throws IOException {
        String body = "<!doctype html><title>" + title + "</title><h1 id=\"proof\">" + title + "</h1>";
        byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
        write(output, "HTTP/1.1 200 OK\r\nConnection: close\r\nCache-Control: no-store\r\n"
                + "Content-Type: text/html; charset=utf-8\r\nContent-Length: " + bytes.length + "\r\n\r\n");
        output.write(bytes);
        output.flush();
    }

    private void heldResponse(Socket socket, InputStream input, OutputStream output) throws IOException {
        if (heldRequests.incrementAndGet() != 1) throw new IOException("Unexpected duplicate incomplete response request");
        socket.setSoTimeout(100_000);
        write(output, "HTTP/1.1 200 OK\r\nConnection: close\r\nContent-Type: text/plain\r\nContent-Length: 4096\r\n\r\nx");
        held.countDown();
        try {
            if (input.read() != -1) throw new IOException("Unexpected bytes after the fixture request");
        } catch (SocketTimeoutException timeout) {
            throw new IOException("Route did not close the held upstream response", timeout);
        } catch (SocketException reset) {
            if (!switching.get()) throw reset;
        }
        if (!switching.get()) throw new IOException("Upstream socket closed before the controlled switch");
        heldConnectionsClosed.incrementAndGet();
        retired.countDown();
    }

    private static Headers headers(InputStream input) throws IOException {
        Headers result = new Headers();
        int bytes = 0;
        for (String text = line(input); !text.isEmpty(); text = line(input)) {
            bytes += text.length() + 2;
            int colon = text.indexOf(':');
            if (colon < 1 || bytes > 24576) throw new IOException("Invalid or oversized HTTP fixture header");
            String name = text.substring(0, colon).toLowerCase(Locale.ROOT);
            if ("host".equals(name)) {
                if (result.host != null) throw new IOException("Duplicate fixture Host header");
                result.host = text.substring(colon + 1).trim();
            } else if ("proxy-authorization".equals(name)) {
                result.proxyAuthorization = true;
            } else if ("cookie".equals(name)) {
                if (!result.cookies.isEmpty()) result.cookies += "; ";
                result.cookies += text.substring(colon + 1).trim();
            }
        }
        return result;
    }

    private static String line(InputStream input) throws IOException {
        StringBuilder value = new StringBuilder();
        while (value.length() < MAX_LINE) {
            int next = octet(input);
            if (next == '\r' && octet(input) == '\n') return value.toString();
            if ((next < 32 && next != '\t') || next > 126) throw new IOException("Invalid HTTP fixture line");
            value.append((char)next);
        }
        throw new IOException("HTTP fixture line exceeded its bound");
    }

    private static int octet(InputStream input) throws IOException {
        int value = input.read();
        if (value < 0) throw new EOFException("Upstream fixture request was incomplete");
        return value;
    }

    private static void write(OutputStream output, String value) throws IOException {
        output.write(value.getBytes(StandardCharsets.US_ASCII));
        output.flush();
    }

    private static void requireTls(Socket socket) throws IOException {
        if (!(socket instanceof SSLSocket)) throw new IOException("Expected a TLS-protected proxy socket");
        ((SSLSocket)socket).startHandshake();
    }

    private static ServerSocket listener(SSLContext tls) throws IOException {
        ServerSocket result = tls == null ? new ServerSocket() : tls.getServerSocketFactory().createServerSocket();
        try {
            result.bind(new InetSocketAddress(InetAddress.getByAddress(LOOPBACK), 0), MAX_CONNECTIONS);
            return result;
        } catch (IOException failure) {
            close(result);
            throw failure;
        }
    }

    private static Thread daemon(Runnable work, String name) {
        Thread result = new Thread(work, name);
        result.setDaemon(true);
        return result;
    }

    private void reject(String message) {
        invalid.compareAndSet(null, new IOException(message));
    }

    private static void close(AutoCloseable closeable) {
        try {
            closeable.close();
        } catch (Exception ignored) {
            // The fixture is already tearing down.
        }
    }

    @Override public void close() {
        stopping.set(true);
        close(listener);
        for (Socket client : clients) close(client);
    }

    private static final class Headers {
        String host;
        String cookies = "";
        boolean proxyAuthorization;
    }

    /** An independent listener counts attempts to bypass the relay and reach a private origin. */
    static final class PrivateTrap implements AutoCloseable {
        private final ServerSocket listener = listener(null);
        private final AtomicReference<IOException> failed = new AtomicReference<>();
        final AtomicInteger accepted = new AtomicInteger();

        PrivateTrap() throws IOException {
            daemon(this::accept, "pocketchat-proxy-bypass-trap").start();
        }

        String url(String nonce) { return "http://127.0.0.1:" + listener.getLocalPort() + "/bypass-" + nonce; }

        void validate() throws IOException {
            if (failed.get() != null) throw failed.get();
        }

        private void accept() {
            while (!listener.isClosed()) {
                try (Socket ignored = listener.accept()) {
                    accepted.incrementAndGet();
                } catch (IOException failure) {
                    if (!listener.isClosed()) failed.compareAndSet(null, failure);
                    return;
                }
            }
        }

        @Override public void close() { LoopbackProxy.close(listener); }
    }
}
