package local.pocketchat;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.concurrent.Callable;
import java.util.concurrent.FutureTask;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

/** Exercises actual socket bytes against local, synthetic proxy peers. */
public final class CefriumProtectedEndpointTest {
    private static int checks;

    public static void main(String[] args) throws Exception {
        httpConnect();
        postDialRevocation();
        unsafeDestination();
        socksHandshake();
        System.out.println(checks + " protected endpoint checks passed");
    }

    private static void httpConnect() throws Exception {
        try (ServerSocket synthetic = loopback(); Registry registry = new Registry()) {
            FutureTask<String> server = serve(() -> {
                try (Socket accepted = synthetic.accept()) {
                    accepted.setSoTimeout(3000);
                    String received = header(accepted.getInputStream());
                    accepted.getOutputStream().write(ascii("HTTP/1.1 200 Connection established\r\n\r\nPING"));
                    return received;
                }
            });
            AtomicInteger checksPerformed = new AtomicInteger();
            CefriumProtectedEndpoint endpoint = CefriumProtectedEndpoint.internal(synthetic.getLocalPort(),
                    () -> checksPerformed.incrementAndGet() <= 3);
            try (Socket tunnel = endpoint.openTunnel("example.com", 443, registry)) {
                check(Arrays.equals(tunnel.getInputStream().readNBytes(4), ascii("PING")), "tunnel data was consumed");
            }
            check(server.get(3, TimeUnit.SECONDS).equals("CONNECT example.com:443 HTTP/1.1\r\nHost: example.com:443\r\n\r\n"),
                    "wrong destination sent to internal proxy");
            check(checksPerformed.get() == 3, "missing owner recheck around the proxy handshake");
        }
    }

    private static void postDialRevocation() throws Exception {
        try (ServerSocket synthetic = loopback(); Registry registry = new Registry()) {
            FutureTask<Integer> server = serve(() -> {
                try (Socket accepted = synthetic.accept()) {
                    accepted.setSoTimeout(3000);
                    return accepted.getInputStream().read();
                }
            });
            AtomicInteger checksPerformed = new AtomicInteger();
            CefriumProtectedEndpoint endpoint = CefriumProtectedEndpoint.internal(synthetic.getLocalPort(),
                    () -> checksPerformed.incrementAndGet() == 1);
            reject(() -> endpoint.openTunnel("example.com", 443, registry), "owner revoked during connect");
            check(server.get(3, TimeUnit.SECONDS) == -1, "sent bytes after owner was revoked");
        }
    }

    private static void unsafeDestination() throws Exception {
        try (Registry registry = new Registry()) {
            CefriumProtectedEndpoint endpoint = CefriumProtectedEndpoint.internal(1, () -> true);
            for (String bad : new String[]{"file:///tmp/page", "example.com/path", "user@example.com", "127.0.0.1", "::1", "example.com\r\n"}) {
                reject(() -> endpoint.openTunnel(bad, 443, registry), "unsafe destination");
            }
            check(registry.sockets.isEmpty(), "opened a socket for an invalid destination");
        }
    }

    private static void socksHandshake() throws Exception {
        try (ServerSocket synthetic = loopback(); Socket client = new Socket(synthetic.getInetAddress(), synthetic.getLocalPort())) {
            FutureTask<Boolean> fixture = serve(() -> {
                try (Socket accepted = synthetic.accept()) {
                    accepted.setSoTimeout(3000);
                    InputStream input = accepted.getInputStream();
                    boolean greeting = Arrays.equals(input.readNBytes(3), new byte[]{5, 1, 0});
                    accepted.getOutputStream().write(new byte[]{5, 0});
                    boolean prefix = Arrays.equals(input.readNBytes(5), new byte[]{5, 1, 0, 3, 11});
                    boolean host = Arrays.equals(input.readNBytes(11), ascii("example.com"));
                    boolean port = Arrays.equals(input.readNBytes(2), new byte[]{1, (byte) 187});
                    accepted.getOutputStream().write(new byte[]{5, 0, 0, 1, 127, 0, 0, 1, 0, 0, 42});
                    return greeting && prefix && host && port;
                }
            });
            client.setSoTimeout(3000);
            CefriumProtectedEndpoint.socksTunnel(client, "example.com", 443);
            check(client.getInputStream().read() == 42, "SOCKS parsed past its reply");
            check(fixture.get(3, TimeUnit.SECONDS), "SOCKS did not send the destination by hostname");
        }
    }

    private static ServerSocket loopback() throws IOException {
        ServerSocket listener = new ServerSocket(0, 2, InetAddress.getByAddress(new byte[]{127, 0, 0, 1}));
        listener.setSoTimeout(3000);
        return listener;
    }
    private static <T> FutureTask<T> serve(Callable<T> test) {
        FutureTask<T> task = new FutureTask<>(test);
        Thread worker = new Thread(task, "test-loopback-proxy");
        worker.setDaemon(true);
        worker.start();
        return task;
    }
    private static byte[] ascii(String value) { return value.getBytes(StandardCharsets.US_ASCII); }
    private static String header(InputStream input) throws IOException {
        ByteArrayOutputStream result = new ByteArrayOutputStream();
        while (result.size() < 4096) {
            int next = input.read();
            if (next < 0) throw new IOException("incomplete test header");
            result.write(next);
            String value = result.toString(StandardCharsets.US_ASCII);
            if (value.endsWith("\r\n\r\n")) return value;
        }
        throw new IOException("test header too large");
    }
    private static void check(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
        checks++;
    }
    private static void reject(Callable<?> operation, String label) throws Exception {
        try { operation.call(); }
        catch (IOException expected) { checks++; return; }
        throw new AssertionError("accepted " + label);
    }
    private static final class Registry implements CefriumProxyRelay.SocketRegistry, AutoCloseable {
        final List<Socket> sockets = new ArrayList<>();
        @Override public void register(Socket socket) { sockets.add(socket); }
        @Override public boolean current() { return true; }
        @Override public void close() throws IOException { for (Socket socket : sockets) socket.close(); }
    }
}
