package local.pocketchat;

import android.net.Network;

import java.io.ByteArrayOutputStream;
import java.io.EOFException;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.Objects;
import java.util.function.BooleanSupplier;
import javax.net.ssl.SSLParameters;
import javax.net.ssl.SSLSocket;
import javax.net.ssl.SSLSocketFactory;

/** Opens only a tunnel through the selected endpoint or a socket on the captured VPN. */
final class CefriumProtectedEndpoint {
    private static final int CONNECT_TIMEOUT_MS = 8000;
    private static final int HANDSHAKE_TIMEOUT_MS = 12000;
    private static final int MAX_PROXY_HEADER = 16 * 1024;
    private static final byte[] LOOPBACK = {127, 0, 0, 1};

    private enum Kind { INTERNAL, HTTP, HTTPS, SOCKS, VPN }

    private final Kind kind;
    private final Network network;
    private final String host;
    private final int port;
    private final BooleanSupplier ownerStillCurrent;

    private CefriumProtectedEndpoint(Kind kind, Network network, String host, int port,
                                    BooleanSupplier ownerStillCurrent) {
        this.kind = kind;
        this.network = network;
        this.host = host;
        this.port = port;
        this.ownerStillCurrent = Objects.requireNonNull(ownerStillCurrent);
    }

    static CefriumProtectedEndpoint internal(int port, BooleanSupplier ownerStillCurrent) throws IOException {
        if (!validPort(port)) throw new IOException("内置线路端口无效");
        return new CefriumProtectedEndpoint(Kind.INTERNAL, null, "127.0.0.1", port, ownerStillCurrent);
    }

    static CefriumProtectedEndpoint fixed(Network network, String specification,
                                            BooleanSupplier ownerStillCurrent) throws IOException {
        if (network == null || specification == null) throw unavailable();
        final URI proxy;
        try { proxy = URI.create(specification); }
        catch (IllegalArgumentException invalid) { throw new IOException("固定代理地址无效", invalid); }
        String proxyHost = proxy.getHost();
        if (proxyHost == null || proxyHost.isEmpty() || proxyHost.indexOf('%') >= 0
                || !validPort(proxy.getPort()) || proxy.getRawUserInfo() != null
                || proxy.getRawQuery() != null || proxy.getRawFragment() != null
                || proxy.getRawPath() == null || !proxy.getRawPath().isEmpty()) {
            throw new IOException("固定代理地址无效");
        }
        final Kind proxyKind;
        if ("http".equals(proxy.getScheme())) proxyKind = Kind.HTTP;
        else if ("https".equals(proxy.getScheme())) proxyKind = Kind.HTTPS;
        else if ("socks5".equals(proxy.getScheme()) || "socks".equals(proxy.getScheme())) proxyKind = Kind.SOCKS;
        else throw new IOException("固定代理协议无效");
        if (proxyHost.startsWith("[")) proxyHost = proxyHost.substring(1, proxyHost.length() - 1);
        return new CefriumProtectedEndpoint(proxyKind, network, proxyHost, proxy.getPort(), ownerStillCurrent);
    }

    static CefriumProtectedEndpoint onNetwork(Network network, BooleanSupplier ownerStillCurrent) throws IOException {
        if (network == null) throw unavailable();
        return new CefriumProtectedEndpoint(Kind.VPN, network, "", 0, ownerStillCurrent);
    }

    Socket openTunnel(String destination, int destinationPort, ChromiumRouteSocketOwner owner) throws IOException {
        if (!validPort(destinationPort) || !publicDestination(destination)) {
            throw new IOException("Chromium 仅允许公开网站地址");
        }
        verifyOwner(owner);
        Socket socket = null;
        try {
            if (kind == Kind.VPN) {
                socket = openBound(destination, destinationPort, owner, true);
            } else {
                socket = kind == Kind.INTERNAL ? openInternal(owner) : openBound(host, port, owner, false);
                // A stopped core might release its port while the connection is opening.
                verifyOwner(owner);
                if (kind == Kind.HTTPS) {
                    socket = tlsProxy(socket, owner);
                    verifyOwner(owner);
                }
                if (kind == Kind.SOCKS) socksTunnel(socket, destination, destinationPort);
                else connectTunnel(socket, destination, destinationPort);
            }
            verifyOwner(owner);
            socket.setSoTimeout(0);
            return socket;
        } catch (IOException | RuntimeException failure) {
            close(socket);
            if (failure instanceof IOException) throw (IOException) failure;
            throw new IOException("线路连接失败", failure);
        }
    }

    private Socket openInternal(ChromiumRouteSocketOwner owner) throws IOException {
        Socket socket = new Socket();
        try {
            owner.register(socket);
            requireCurrent(owner);
            socket.connect(new InetSocketAddress(InetAddress.getByAddress(LOOPBACK), port), CONNECT_TIMEOUT_MS);
            socket.setSoTimeout(HANDSHAKE_TIMEOUT_MS);
            requireCurrent(owner);
            return socket;
        } catch (IOException | RuntimeException failure) {
            close(socket);
            throw failure;
        }
    }

    private Socket openBound(String name, int targetPort, ChromiumRouteSocketOwner owner,
                             boolean publicOnly) throws IOException {
        requireCurrent(owner);
        InetAddress[] addresses = network.getAllByName(name);
        for (InetAddress address : addresses) {
            requireCurrent(owner);
            if (publicOnly && !publicDestination(address.getHostAddress())) continue;
            Socket socket = network.getSocketFactory().createSocket();
            try {
                owner.register(socket);
                requireCurrent(owner);
                socket.connect(new InetSocketAddress(address, targetPort), CONNECT_TIMEOUT_MS);
                socket.setSoTimeout(HANDSHAKE_TIMEOUT_MS);
                requireCurrent(owner);
                return socket;
            } catch (IOException failure) {
                close(socket);
                requireCurrent(owner);
            } catch (RuntimeException unavailable) {
                close(socket);
                throw new IOException("无法使用已确认的 Android 网络", unavailable);
            }
        }
        throw new IOException("此线路上的连接没有建立");
    }

    private Socket tlsProxy(Socket socket, ChromiumRouteSocketOwner owner) throws IOException {
        requireCurrent(owner);
        SSLSocketFactory factory = (SSLSocketFactory) SSLSocketFactory.getDefault();
        SSLSocket tls = (SSLSocket) factory.createSocket(socket, host, port, true);
        try {
            owner.register(tls);
            SSLParameters parameters = tls.getSSLParameters();
            parameters.setEndpointIdentificationAlgorithm("HTTPS");
            tls.setSSLParameters(parameters);
            requireCurrent(owner);
            tls.startHandshake();
            requireCurrent(owner);
            return tls;
        } catch (IOException | RuntimeException failure) {
            close(tls);
            throw failure;
        }
    }

    static void connectTunnel(Socket socket, String destination, int targetPort) throws IOException {
        String authority = authority(destination, targetPort);
        OutputStream output = socket.getOutputStream();
        output.write(("CONNECT " + authority + " HTTP/1.1\r\nHost: " + authority + "\r\n\r\n")
                .getBytes(StandardCharsets.US_ASCII));
        output.flush();
        InputStream input = socket.getInputStream();
        String status = readLine(input, MAX_PROXY_HEADER);
        if (!status.matches("HTTP/1\\.[01] 200(?: [ -~]*)?")) throw new IOException("固定线路未接受隧道连接");
        int remaining = MAX_PROXY_HEADER - status.length() - 2;
        while (remaining > 0) {
            String line = readLine(input, remaining);
            if (line.isEmpty()) return;
            remaining -= line.length() + 2;
        }
        throw new IOException("固定线路代理回复过长");
    }

    private static String readLine(InputStream input, int limit) throws IOException {
        StringBuilder line = new StringBuilder();
        while (line.length() + 2 <= limit) {
            int value = readByte(input);
            if (value == '\r' && readByte(input) == '\n') return line.toString();
            if ((value < 32 && value != 9) || value > 126) throw new IOException("代理回复无效");
            line.append((char) value);
        }
        throw new IOException("代理回复过长");
    }

    static void socksTunnel(Socket socket, String destination, int targetPort) throws IOException {
        InputStream input = socket.getInputStream();
        OutputStream output = socket.getOutputStream();
        output.write(new byte[]{5, 1, 0});
        output.flush();
        if (readByte(input) != 5 || readByte(input) != 0) throw new IOException("SOCKS 代理需要不支持的认证");
        byte[] address = destination.getBytes(StandardCharsets.US_ASCII);
        ByteArrayOutputStream request = new ByteArrayOutputStream();
        request.write(new byte[]{5, 1, 0});
        if (destination.indexOf(':') >= 0) {
            byte[] ipv6 = InetAddress.getByName(destination).getAddress();
            if (ipv6.length != 16) throw new IOException("不支持的 IPv6 目标");
            request.write(4);
            request.write(ipv6);
        } else {
            if (address.length < 1 || address.length > 253) throw new IOException("代理目标域名无效");
            request.write(3);
            request.write(address.length);
            request.write(address);
        }
        request.write(targetPort >> 8);
        request.write(targetPort & 255);
        request.writeTo(output);
        output.flush();
        if (readByte(input) != 5 || readByte(input) != 0 || readByte(input) != 0)
            throw new IOException("SOCKS 代理未接受隧道连接");
        int addressType = readByte(input);
        final int length;
        if (addressType == 1) length = 4;
        else if (addressType == 4) length = 16;
        else if (addressType == 3) length = readByte(input);
        else throw new IOException("SOCKS 代理回复无效");
        for (int index = 0; index < length + 2; index++) readByte(input);
    }

    private static int readByte(InputStream input) throws IOException {
        int value = input.read();
        if (value < 0) throw new EOFException("代理在建立隧道之前断开");
        return value;
    }

    private static boolean publicDestination(String name) {
        return name != null && name.matches("[A-Za-z0-9.-]{1,253}|[A-Fa-f0-9:.]{2,45}")
                && BrowserAddressPolicy.allowed("https://" + authority(name, 443) + "/");
    }

    private static String authority(String destination, int targetPort) {
        return (destination.indexOf(':') < 0 ? destination : "[" + destination + "]") + ":" + targetPort;
    }

    private static boolean validPort(int port) { return port >= 1 && port <= 65535; }

    private void verifyOwner(ChromiumRouteSocketOwner owner) throws IOException {
        requireCurrent(owner);
        if (!ownerStillCurrent.getAsBoolean()) throw unavailable();
        requireCurrent(owner);
    }

    private static void requireCurrent(ChromiumRouteSocketOwner owner) throws IOException {
        if (!owner.current()) throw unavailable();
    }

    private static IOException unavailable() { return new IOException("Chromium 受保护线路已断开"); }

    private static void close(Socket socket) {
        if (socket != null) try { socket.close(); } catch (IOException ignored) {}
    }
}
