package local.pocketchat;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;

/** Checks only release-origin policy and wire framing. No network or Android objects are used. */
public final class ChromiumModuleHttpTest {
    private static int checks;

    public static void main(String[] args) throws Exception {
        ChromiumModulePolicy.Installed installed = new ChromiumModulePolicy.Installed(
                "2.1.13", 115, "v2.1.13-gecko", "arm64-v8a", "");
        String origin = ChromiumModulePolicy.metadata(installed, false);
        String cdn = "https://release-assets.githubusercontent.com/github-production-release-asset-123/abc?sig=abc%2Fdef%3D";
        ChromiumModuleHttp.requireTarget(origin, origin);
        ChromiumModuleHttp.requireTarget(origin, cdn);
        checks += 2;
        reject(() -> ChromiumModuleHttp.requireTarget(origin, "https://attacker.invalid/"));
        reject(() -> ChromiumModuleHttp.requireTarget(origin, cdn.replace("https://", "http://")));
        reject(() -> ChromiumModuleHttp.requireTarget(origin, cdn.replace(".com/", ".com.attacker.invalid/")));
        reject(() -> ChromiumModuleHttp.requireTarget(origin, cdn.replace(".com/", ".com:444/")));
        reject(() -> ChromiumModuleHttp.requireTarget(origin, cdn + "#x"));
        reject(() -> ChromiumModuleHttp.requireTarget(origin, origin.replace("2.1.13", "2.1.14")));
        reject(() -> ChromiumModuleHttp.requireTarget(origin.replace("github.com", "different.invalid"), cdn));

        ChromiumModuleHttp.Response redirect = parse("HTTP/1.1 302 Found\r\nLocation: " + cdn + "\r\nContent-Length: 0\r\n\r\n");
        check(redirect.status == 302 && cdn.equals(redirect.location), "official CDN redirect");
        check(read("HTTP/1.1 200 OK\r\nContent-Length: 4\r\n\r\nfileUNRELATED").equals("file"), "verified body respects framing");
        check(read("HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n2\r\nfi\r\n2;sample=1\r\nle\r\n0\r\nAfter: ignored\r\n\r\n").equals("file"),
                "dechunk release metadata without trailer bytes");
        check(read("HTTP/1.1 103 Early Hints\r\nLink: </a>\r\n\r\nHTTP/1.1 200 OK\r\n\r\nsignature").equals("signature"),
                "skip bounded early hints");
        reject(() -> read("HTTP/1.1 200 OK\r\nContent-Length: 4\r\n\r\nfil"));
        reject(() -> read("HTTP/1.1 200 OK\r\nContent-Length: 4\r\ncontent-length: 4\r\n\r\nfile"));
        reject(() -> read("HTTP/1.1 200 OK\r\nContent-Length: 4\r\nTransfer-Encoding: chunked\r\n\r\n0\r\n\r\n"));
        reject(() -> read("HTTP/1.1 200 OK\r\nContent-Encoding: gzip\r\n\r\nfile"));
        reject(() -> read("HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n20000001\r\na"));
        reject(() -> read("HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n1\r\na\r\n0\r\n"));
        reject(() -> read("HTTP/1.1 200 OK\nContent-Length: 4\n\nfile"));
        reject(() -> parse("HTTP/1.1 302 Found\r\nLocation: " + cdn + "\r\nLocation: https://attacker.invalid\r\n\r\n"));
        System.out.println("Chromium component origin and HTTP framing checks passed: " + checks);
    }

    private static ChromiumModuleHttp.Response parse(String raw) throws IOException {
        return ChromiumModuleHttp.read(new ByteArrayInputStream(raw.getBytes(StandardCharsets.US_ASCII)));
    }

    private static String read(String raw) throws IOException {
        try (InputStream input = parse(raw).body; ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[3];
            for (int count; (count = input.read(buffer)) != -1;) output.write(buffer, 0, count);
            return new String(output.toByteArray(), StandardCharsets.US_ASCII);
        }
    }

    private static void check(boolean valid, String detail) {
        if (!valid) throw new AssertionError(detail);
        checks++;
    }

    private static void reject(Io test) throws IOException {
        try { test.run(); }
        catch (IOException expected) { checks++; return; }
        throw new AssertionError("Unexpectedly accepted bad release response or URL");
    }

    private interface Io { void run() throws IOException; }
}
