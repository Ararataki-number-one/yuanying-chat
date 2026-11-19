package local.pocketchat;

import java.io.BufferedInputStream;
import java.io.ByteArrayOutputStream;
import java.io.EOFException;
import java.io.IOException;
import java.io.InputStream;
import java.net.Socket;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import javax.net.ssl.SSLParameters;
import javax.net.ssl.SSLSocket;
import javax.net.ssl.SSLSocketFactory;

/** One TLS-verified release GET on a socket already opened on the selected environment line. */
final class ChromiumModuleHttp {
    private static final int IO_TIMEOUT_MS = 20_000;
    private static final int MAX_HEADERS = 32 * 1024;
    private static final int MAX_LINE = 8192;

    private ChromiumModuleHttp() {}

    static Response get(ChromiumModuleRoute route, String origin, String target) throws IOException {
        requireTarget(origin, target);
        URI uri = URI.create(target);
        String host = uri.getHost();
        if (host == null) throw invalid();
        Socket raw = route.connect(host, 443);
        SSLSocketFactory factory = (SSLSocketFactory) SSLSocketFactory.getDefault();
        SSLSocket socket = (SSLSocket) factory.createSocket(raw, host, 443, true);
        route.register(socket);
        socket.setSoTimeout(IO_TIMEOUT_MS);
        SSLParameters parameters = socket.getSSLParameters();
        parameters.setEndpointIdentificationAlgorithm("HTTPS");
        socket.setSSLParameters(parameters);
        route.requireVerified();
        socket.startHandshake();
        route.requireVerified();
        String path = uri.getRawPath();
        if (path == null || path.isEmpty()) path = "/";
        if (uri.getRawQuery() != null) path += "?" + uri.getRawQuery();
        socket.getOutputStream().write(("GET " + path + " HTTP/1.1\r\nHost: " + host
                + "\r\nConnection: close\r\nAccept-Encoding: identity\r\nUser-Agent: PocketChat-chromium-module\r\n\r\n")
                .getBytes(StandardCharsets.US_ASCII));
        socket.getOutputStream().flush();
        Response response = read(new BufferedInputStream(socket.getInputStream()));
        route.requireVerified();
        return response;
    }

    static void requireTarget(String origin, String target) throws IOException {
        if (!ChromiumModulePolicy.officialOrigin(origin) || !AppUpdateTransfer.trusted(target, origin)) {
            throw new IOException("Chromium 组件下载地址不受信任");
        }
        URI uri = URI.create(target);
        String path = uri.getRawPath();
        String query = uri.getRawQuery();
        if (path == null || !path.matches("/[!-~]*") || (query != null && !query.matches("[!-~]*"))) throw invalid();
    }

    static Response read(InputStream input) throws IOException {
        for (int interim = 0; interim < 4; interim++) {
            int remaining = MAX_HEADERS;
            String status = line(input, MAX_LINE);
            if (!status.matches("HTTP/1\\.[01] [1-5][0-9]{2}(?: [ -~]*)?")) throw invalid();
            int code = Integer.parseInt(status.substring(9, 12));
            Map<String, String> headers = new HashMap<>();
            while (true) {
                String field = line(input, Math.min(MAX_LINE, remaining));
                remaining -= field.length() + 2;
                if (field.isEmpty()) break;
                int separator = field.indexOf(':');
                if (separator <= 0 || !field.substring(0, separator).matches("[!#$%&'*+.^_`|~0-9A-Za-z-]+")) throw invalid();
                String name = field.substring(0, separator).toLowerCase(Locale.ROOT);
                if (name.equals("transfer-encoding") || name.equals("content-length")
                        || name.equals("content-encoding") || name.equals("location")) {
                    if (headers.put(name, field.substring(separator + 1).trim()) != null) throw invalid();
                }
            }
            if (code == 101) throw invalid();
            if (code >= 200) return new Response(code, headers, input);
        }
        throw invalid();
    }

    static final class Response {
        final int status;
        final String location;
        final InputStream body;

        Response(int status, Map<String, String> headers, InputStream input) throws IOException {
            this.status = status;
            location = headers.get("location");
            String encoding = headers.get("content-encoding");
            String transfer = headers.get("transfer-encoding");
            String length = headers.get("content-length");
            if (status == 200 && encoding != null && !"identity".equalsIgnoreCase(encoding)) throw invalid();
            if (transfer != null && (length != null || !"chunked".equalsIgnoreCase(transfer))) throw invalid();
            if (length != null && !length.matches("[0-9]{1,12}")) throw invalid();
            body = transfer != null ? new FramedBody(input, -1) : length == null ? input
                    : new FramedBody(input, Long.parseLong(length));
        }
    }

    /** Length or chunked framing only. The outer signed-asset checks still verify all payload bytes. */
    private static final class FramedBody extends InputStream {
        private final InputStream input;
        private final boolean chunks;
        private long remaining;
        private boolean chunkBody;
        private boolean end;

        FramedBody(InputStream input, long length) {
            this.input = input;
            chunks = length < 0;
            remaining = chunks ? 0 : length;
        }

        @Override public int read() throws IOException {
            byte[] single = new byte[1];
            return read(single, 0, 1) < 0 ? -1 : single[0] & 255;
        }

        @Override public int read(byte[] buffer, int offset, int length) throws IOException {
            if (buffer == null) throw new NullPointerException();
            if (offset < 0 || length < 0 || offset > buffer.length - length) throw new IndexOutOfBoundsException();
            if (length == 0) return 0;
            if (end) return -1;
            if (remaining == 0 && chunks) nextChunk();
            if (end || remaining == 0) return -1;
            int count = input.read(buffer, offset, (int) Math.min(length, remaining));
            if (count < 0) throw new EOFException("Chromium 下载响应未完整结束");
            remaining -= count;
            return count;
        }

        private void nextChunk() throws IOException {
            if (chunkBody && (input.read() != '\r' || input.read() != '\n')) throw invalid();
            String header = line(input, 128);
            int extension = header.indexOf(';');
            String length = extension < 0 ? header : header.substring(0, extension);
            if (!length.matches("[0-9A-Fa-f]{1,12}")) throw invalid();
            remaining = Long.parseLong(length, 16);
            chunkBody = remaining != 0;
            if (remaining > AppUpdatePolicy.MAX_APK) throw invalid();
            if (remaining != 0) return;
            int space = MAX_HEADERS;
            while (true) {
                String trailer = line(input, Math.min(MAX_LINE, space));
                if (trailer.isEmpty()) break;
                if (trailer.indexOf(':') <= 0) throw invalid();
                space -= trailer.length() + 2;
            }
            end = true;
        }

        @Override public void close() throws IOException { input.close(); }
    }

    private static String line(InputStream input, int maximum) throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        while (bytes.size() + 2 <= maximum) {
            int value = input.read();
            if (value == '\r' && input.read() == '\n') return new String(bytes.toByteArray(), StandardCharsets.ISO_8859_1);
            if (value < 32 && value != '\t' || value == 127) throw invalid();
            bytes.write(value);
        }
        throw invalid();
    }

    private static IOException invalid() { return new IOException("Chromium 组件下载响应无效"); }
}
