package local.pocketchat;

import java.io.BufferedInputStream;
import java.io.ByteArrayOutputStream;
import java.io.EOFException;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.ArrayList;
import java.util.Base64;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.RejectedExecutionException;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.BooleanSupplier;
import java.util.regex.Pattern;

/** Per-route, authenticated loopback access. The only nonlocal connection is supplied by the admitted route. */
final class CefriumProxyRelay implements AutoCloseable {
    interface Upstream {
        /** Register before connect or handshake. A layered TLS handle can join its registered raw socket. */
        Socket openTunnel(String canonicalHost, int port, SocketRegistry owner) throws IOException;
    }

    /** The socket is closed and rejected if this flow has already been revoked. */
    interface SocketRegistry extends ChromiumRouteSocketOwner {}

    private static final int MAX_CONNECTIONS = 16;
    private static final int MAX_UPSTREAM_HANDLES = 2;
    private static final int HEADER_TIMEOUT_MS = 5000;
    private static final int IDLE_TIMEOUT_MS = 120_000;
    private static final int MAX_HEADER_BYTES = 24 * 1024;
    private static final int MAX_HEADER_LINE = 8192;
    private static final int MAX_HEADERS = 96;
    private static final long MAX_HTTP_BODY = 512L * 1024 * 1024;
    private static final String HOST = "127.0.0.1";
    private static final Pattern TOKEN = Pattern.compile("[!#$%&'*+.^_`|~0-9A-Za-z-]+");
    private static final Pattern AUTHORITY = Pattern.compile("(?:[^:/?#@%\\[\\]\\\\]+|\\[[0-9A-Fa-f:.]+]):[0-9]{1,5}");
    private static final Pattern IPV4 = Pattern.compile("(?:0|[1-9][0-9]{0,2})(?:[.](?:0|[1-9][0-9]{0,2})){3}");
    private static final SecureRandom RANDOM = new SecureRandom();

    private final Object lock = new Object();
    private final ServerSocket listener;
    private final InetAddress loopback;
    private final Upstream upstream;
    private final BooleanSupplier routeCurrent;
    private final ThreadPoolExecutor workers;
    private final Set<Flow> flows = new HashSet<>();
    private final String username = credential();
    private final String password = credential();
    private final byte[] expectedAuth = Base64.getEncoder().encode((username + ":" + password).getBytes(StandardCharsets.US_ASCII));
    private volatile boolean closed;

    CefriumProxyRelay(Upstream upstream, BooleanSupplier routeCurrent) throws IOException {
        if (upstream == null || routeCurrent == null) throw new IllegalArgumentException("Route is required");
        this.upstream = upstream;
        this.routeCurrent = routeCurrent;
        loopback = InetAddress.getByAddress(new byte[]{127, 0, 0, 1});
        listener = new ServerSocket();
        try {
            listener.bind(new InetSocketAddress(loopback, 0), MAX_CONNECTIONS);
        } catch (IOException | RuntimeException failure) {
            closeSocket(listener);
            throw failure;
        }
        workers = new ThreadPoolExecutor(MAX_CONNECTIONS * 2, MAX_CONNECTIONS * 2, 20, TimeUnit.SECONDS,
                new ArrayBlockingQueue<>(MAX_CONNECTIONS), task -> daemon(task, "cefrium-proxy-io"));
        workers.allowCoreThreadTimeOut(true);
        daemon(this::accept, "cefrium-proxy-listener").start();
    }

    String endpoint() { return HOST + ":" + listener.getLocalPort(); }
    String username() { return username; }
    String password() { return password; }
    boolean isOpen() { return !closed && !listener.isClosed(); }

    private static String credential() {
        byte[] bytes = new byte[21];
        RANDOM.nextBytes(bytes);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }

    private static Thread daemon(Runnable target, String name) {
        Thread thread = new Thread(target, name);
        thread.setDaemon(true);
        return thread;
    }

    private boolean admitted() {
        if (!isOpen()) return false;
        try {
            if (routeCurrent.getAsBoolean()) return isOpen();
        } catch (RuntimeException | LinkageError unavailable) {
            // A missing route observation has the same effect as a revoked route.
        }
        close();
        return false;
    }

    private void accept() {
        try {
            while (isOpen()) {
                Socket client = listener.accept();
                Flow flow = attach(client);
                if (flow == null) {
                    closeSocket(client);
                    continue;
                }
                try {
                    workers.execute(() -> serve(flow));
                } catch (RejectedExecutionException busy) {
                    flow.close();
                }
            }
        } catch (IOException failure) {
            // Listener failure retires all in-flight streams on this route.
        } finally {
            close();
        }
    }

    private Flow attach(Socket client) {
        if (!loopback.equals(client.getInetAddress())) return null;
        synchronized (lock) {
            if (closed || flows.size() >= MAX_CONNECTIONS) return null;
            Flow flow = new Flow(client);
            flows.add(flow);
            return flow;
        }
    }

    private void serve(Flow flow) {
        boolean pumping = false;
        boolean mayAnswer = true;
        try {
            if (!flow.current()) return;
            flow.client.setSoTimeout(HEADER_TIMEOUT_MS);
            BufferedInputStream input = new BufferedInputStream(flow.client.getInputStream());
            OutputStream output = flow.client.getOutputStream();
            Request request = readRequest(input);
            if (!authorized(request.authorization)) {
                respond(output, 407, "Proxy Authentication Required", true);
                return;
            }
            request.validateTarget();
            if (!flow.current()) return;
            Socket remote = upstream.openTunnel(request.target.host, request.target.port, flow);
            if (!flow.owns(remote)) {
                closeSocket(remote);
                throw new IOException("Unregistered upstream socket");
            }
            if (!remote.isConnected() || remote.isClosed() || !flow.current()) throw new IOException("Upstream unavailable");
            remote.setSoTimeout(IDLE_TIMEOUT_MS);
            flow.client.setSoTimeout(IDLE_TIMEOUT_MS);
            InputStream response = remote.getInputStream();
            OutputStream outbound = remote.getOutputStream();
            if (request.connect) {
                mayAnswer = false;
                if (!flow.current()) return;
                output.write("HTTP/1.1 200 Connection Established\r\n\r\n".getBytes(StandardCharsets.US_ASCII));
                output.flush();
                workers.execute(() -> pump(flow, response, output, flow.client));
                pumping = true;
                pump(flow, input, outbound, remote);
            } else {
                forwardRequest(flow, request, input, outbound);
                mayAnswer = false;
                transfer(flow, response, output, -1);
            }
        } catch (RequestFailure invalid) {
            if (mayAnswer && flow.current()) replyIfOpen(flow.client, invalid.status, invalid.reason);
        } catch (IOException | RuntimeException failure) {
            if (mayAnswer && flow.current()) replyIfOpen(flow.client, 502, "Proxy upstream unavailable");
        } finally {
            if (!pumping) flow.close();
        }
    }

    private boolean authorized(String value) {
        if (value == null || !value.regionMatches(true, 0, "Basic ", 0, 6)) return false;
        return MessageDigest.isEqual(expectedAuth, value.substring(6).getBytes(StandardCharsets.ISO_8859_1));
    }

    private static Request readRequest(InputStream input) throws IOException {
        HeaderReader reader = new HeaderReader(input);
        String first = reader.line(false);
        String[] tokens = first.split(" ", -1);
        if (tokens.length != 3 || !TOKEN.matcher(tokens[0]).matches() || !"HTTP/1.1".equals(tokens[2])) throw bad();
        Request request = new Request(tokens[0], tokens[1]);
        for (String line = reader.line(true); !line.isEmpty(); line = reader.line(true)) {
            if (request.headers.size() >= MAX_HEADERS) throw tooLarge();
            int colon = line.indexOf(':');
            if (colon <= 0 || !TOKEN.matcher(line.substring(0, colon)).matches()) throw bad();
            String name = line.substring(0, colon).toLowerCase(Locale.ROOT), value = line.substring(colon + 1).trim();
            request.accept(name, value);
        }
        return request;
    }

    private static void forwardRequest(Flow flow, Request request, InputStream input, OutputStream outbound) throws IOException {
        StringBuilder headers = new StringBuilder(request.method).append(' ').append(request.path).append(" HTTP/1.1\r\n")
                .append("Host: ").append(request.target.hostHeader()).append("\r\nConnection: close\r\n");
        if (request.bodyLength >= 0) headers.append("Content-Length: ").append(request.bodyLength).append("\r\n");
        for (Header header : request.headers) {
            if (!request.connectionOptions.contains(header.name) && !hop(header.name)) {
                headers.append(header.name).append(": ").append(header.value).append("\r\n");
            }
        }
        if (!flow.current()) throw new IOException("Route closed");
        outbound.write(headers.append("\r\n").toString().getBytes(StandardCharsets.ISO_8859_1));
        if (request.bodyLength > 0) transfer(flow, input, outbound, request.bodyLength);
        outbound.flush();
    }

    private static boolean hop(String name) {
        switch (name) {
            case "host": case "content-length": case "connection": case "proxy-connection":
            case "proxy-authorization": case "proxy-authenticate": case "keep-alive": case "te":
            case "trailer": case "transfer-encoding": case "upgrade": case "expect":
                return true;
            default:
                return false;
        }
    }

    private static void pump(Flow flow, InputStream input, OutputStream output, Socket destination) {
        try {
            transfer(flow, input, output, -1);
            if (flow.current()) destination.shutdownOutput();
        } catch (IOException | RuntimeException stopped) {
            flow.close();
        } finally {
            if (flow.pumps.decrementAndGet() == 0) flow.close();
        }
    }

    private static void transfer(Flow flow, InputStream input, OutputStream output, long remaining) throws IOException {
        byte[] bytes = new byte[16 * 1024];
        boolean framed = remaining >= 0;
        while (!framed || remaining > 0) {
            if (!flow.current()) throw new IOException("Route closed");
            int size = input.read(bytes, 0, framed ? (int) Math.min(remaining, bytes.length) : bytes.length);
            if (size < 0) {
                if (framed) throw new EOFException("Incomplete HTTP request body");
                break;
            }
            if (!flow.current()) throw new IOException("Route closed");
            output.write(bytes, 0, size);
            if (framed) remaining -= size;
        }
    }

    private static void replyIfOpen(Socket client, int status, String reason) {
        try {
            respond(client.getOutputStream(), status, reason, false);
        } catch (IOException ignored) {
            // Client may already have closed the connection.
        }
    }

    private static void respond(OutputStream output, int status, String reason, boolean authenticate) throws IOException {
        String headers = "HTTP/1.1 " + status + " " + reason + "\r\nConnection: close\r\nContent-Length: 0\r\n"
                + (authenticate ? "Proxy-Authenticate: Basic realm=\"PocketChat\"\r\n" : "") + "\r\n";
        output.write(headers.getBytes(StandardCharsets.US_ASCII));
        output.flush();
    }

    @Override public void close() {
        synchronized (lock) {
            if (closed) return;
            closed = true;
            closeSocket(listener);
            for (Flow flow : flows) flow.closeLocked();
            flows.clear();
        }
        workers.shutdownNow();
    }

    private static void closeSocket(AutoCloseable socket) {
        if (socket == null) return;
        try { socket.close(); } catch (Exception ignored) {}
    }

    private final class Flow implements SocketRegistry {
        private final Socket client;
        private final AtomicInteger pumps = new AtomicInteger(2);
        private final List<Socket> upstreamHandles = new ArrayList<>(MAX_UPSTREAM_HANDLES);
        private volatile boolean retired;

        Flow(Socket client) { this.client = client; }

        @Override public boolean current() { return !retired && admitted() && !retired; }

        @Override public void register(Socket socket) throws IOException {
            if (socket == null || socket == client || socket.isClosed()) throw new IOException("Invalid upstream socket");
            try {
                // Route revocation must not wait for queued writes to flush.
                socket.setSoLinger(false, 0);
            } catch (IOException invalid) {
                closeSocket(socket);
                throw invalid;
            }
            if (current()) {
                synchronized (lock) {
                    if (!closed && !retired) {
                        upstreamHandles.removeIf(Socket::isClosed);
                        if (upstreamHandles.contains(socket)) return;
                        if (upstreamHandles.size() < MAX_UPSTREAM_HANDLES) {
                            upstreamHandles.add(socket);
                            return;
                        }
                    }
                }
            }
            closeSocket(socket);
            throw new IOException("Upstream route is no longer open");
        }

        boolean owns(Socket socket) {
            synchronized (lock) { return !retired && socket != null && upstreamHandles.contains(socket); }
        }

        void close() {
            synchronized (lock) {
                closeLocked();
                flows.remove(this);
            }
        }

        void closeLocked() {
            if (retired) return;
            retired = true;
            closeSocket(client);
            // Closing the raw socket first stops traffic before a TLS wrapper can flush.
            for (Socket socket : upstreamHandles) closeSocket(socket);
            upstreamHandles.clear();
        }
    }

    private static final class HeaderReader {
        private final InputStream input;
        private final long deadline = System.nanoTime() + TimeUnit.MILLISECONDS.toNanos(HEADER_TIMEOUT_MS);
        private int total;

        HeaderReader(InputStream input) { this.input = input; }

        String line(boolean header) throws IOException {
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            while (true) {
                int next = next();
                if (next == '\r') {
                    if (next() != '\n') throw bad();
                    return new String(bytes.toByteArray(), StandardCharsets.ISO_8859_1);
                }
                if (next == 127 || next < 32 && !(header && next == '\t') || !header && next >= 128) throw bad();
                if (bytes.size() >= MAX_HEADER_LINE) throw tooLarge();
                bytes.write(next);
            }
        }

        private int next() throws IOException {
            if (System.nanoTime() - deadline >= 0) throw new IOException("Proxy headers timed out");
            if (++total > MAX_HEADER_BYTES) throw tooLarge();
            int value = input.read();
            if (value < 0) throw new EOFException();
            return value;
        }
    }

    private static final class Request {
        private final String method;
        private final String rawTarget;
        private final boolean connect;
        private final List<Header> headers = new ArrayList<>();
        private final Set<String> connectionOptions = new HashSet<>();
        private String authorization;
        private String host;
        private long bodyLength = -1;
        private Target target;
        private String path;

        Request(String method, String rawTarget) {
            this.method = method;
            this.rawTarget = rawTarget;
            this.connect = "CONNECT".equals(method);
        }

        void accept(String name, String value) throws RequestFailure {
            switch (name) {
                case "proxy-authorization":
                    if (authorization != null) throw bad();
                    authorization = value;
                    break;
                case "host":
                    if (host != null || value.isEmpty()) throw bad();
                    host = value;
                    break;
                case "content-length":
                    if (bodyLength >= 0 || !value.matches("(?:0|[1-9][0-9]{0,9})")) throw bad();
                    bodyLength = Long.parseLong(value);
                    if (bodyLength > MAX_HTTP_BODY) throw new RequestFailure(413, "Proxy request body too large");
                    break;
                case "transfer-encoding": case "trailer": case "upgrade": case "expect":
                    throw new RequestFailure(501, "Proxy request framing unsupported");
                case "connection": case "proxy-connection":
                    for (String token : value.split(",", -1)) {
                        String option = token.trim().toLowerCase(Locale.ROOT);
                        if (!TOKEN.matcher(option).matches() || "upgrade".equals(option)
                                || "content-length".equals(option) || "host".equals(option)) throw bad();
                        connectionOptions.add(option);
                    }
                    break;
                default:
                    break;
            }
            headers.add(new Header(name, value));
        }

        void validateTarget() throws RequestFailure {
            if (host == null || "TRACE".equalsIgnoreCase(method)) throw bad();
            if (connect) {
                if (bodyLength > 0 || !AUTHORITY.matcher(rawTarget).matches()) throw bad();
                target = target(authority(rawTarget), -1);
            } else {
                if (!rawTarget.regionMatches(true, 0, "http://", 0, 7)) throw bad();
                URI url = publicAddress(rawTarget);
                if (url.getRawFragment() != null) throw bad();
                target = target(url, 80);
                path = url.getRawPath();
                if (path == null || path.isEmpty() || path.startsWith("//")) throw bad();
                if (url.getRawQuery() != null) path += "?" + url.getRawQuery();
            }
            Target header = target(authority(host), connect ? target.port : 80);
            if (target.port != header.port || !target.host.equals(header.host)) throw bad();
        }
    }

    private static URI authority(String raw) throws RequestFailure {
        if (raw.indexOf('/') >= 0 || raw.indexOf('?') >= 0 || raw.indexOf('#') >= 0) throw bad();
        return publicAddress("https://" + raw + "/");
    }

    private static URI publicAddress(String address) throws RequestFailure {
        try {
            return URI.create(BrowserAddressPolicy.normalizeInput(address));
        } catch (IllegalArgumentException blocked) {
            throw new RequestFailure(403, "Proxy target rejected");
        }
    }

    private static Target target(URI url, int defaultPort) throws RequestFailure {
        String host = url.getHost();
        int port = url.getPort() == -1 ? defaultPort : url.getPort();
        if (host == null || port < 1 || port > 65535) throw bad();
        if (host.startsWith("[") && host.endsWith("]")) {
            host = host.substring(1, host.length() - 1);
            // BrowserAddressPolicy has already accepted only numeric IPv6 on this branch.
            try { host = InetAddress.getByName(host).getHostAddress(); }
            catch (IOException malformed) { throw bad(); }
        } else if (host.matches("[0-9.]+") && !IPV4.matcher(host).matches()) {
            // Never let a proxy and browser disagree over a legacy spelling of a numeric host.
            throw bad();
        }
        return new Target(host.toLowerCase(Locale.ROOT), port);
    }

    private static final class Target {
        private final String host;
        private final int port;
        Target(String host, int port) { this.host = host; this.port = port; }
        String hostHeader() { return (host.indexOf(':') < 0 ? host : "[" + host + "]") + (port == 80 ? "" : ":" + port); }
    }

    private static final class Header {
        private final String name;
        private final String value;
        Header(String name, String value) { this.name = name; this.value = value; }
    }

    private static RequestFailure bad() { return new RequestFailure(400, "Malformed proxy request"); }
    private static RequestFailure tooLarge() { return new RequestFailure(431, "Proxy headers too large"); }

    private static final class RequestFailure extends IOException {
        private final int status;
        private final String reason;
        RequestFailure(int status, String reason) { this.status = status; this.reason = reason; }
    }
}
