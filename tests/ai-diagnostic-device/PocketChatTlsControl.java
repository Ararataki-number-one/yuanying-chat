import java.io.IOException;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.Proxy;
import java.net.URL;
import java.net.UnknownHostException;
import java.security.cert.CertPathValidatorException;
import java.security.cert.CertificateException;
import java.util.concurrent.FutureTask;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import javax.net.ssl.HttpsURLConnection;
import javax.net.ssl.SSLException;

/** Fixed synthetic control for the host JVM and temporary Android shell process. */
public final class PocketChatTlsControl {
    private static final String HOST = "fixture-control.test";

    public static void main(String[] args) {
        if (args.length != 1) throw new IllegalArgumentException("control mode required");
        switch (args[0]) {
            case "host":
                System.out.println(probeTls("127.0.0.1"));
                return;
            case "android":
                System.out.println(probeTls("10.0.2.2"));
                return;
            case "android-dns":
                System.out.println(probeDns());
                return;
            default:
                throw new IllegalArgumentException("unknown control mode");
        }
    }

    private static String probeDns() {
        FutureTask<String> task = new FutureTask<>(() -> {
            try {
                return InetAddress.getAllByName(HOST).length > 0 ? "DNS_RESOLVED" : "DNS_NOT_RESOLVED";
            } catch (UnknownHostException rejected) {
                return "DNS_NOT_RESOLVED";
            }
        });
        Thread worker = new Thread(task, "fixed-control-dns");
        worker.setDaemon(true);
        worker.start();
        try {
            return task.get(5, TimeUnit.SECONDS);
        } catch (TimeoutException timedOut) {
            return "DNS_TIMEOUT";
        } catch (Exception failed) {
            return "DNS_PROBE_FAILED";
        } finally {
            task.cancel(true);
        }
    }

    private static String probeTls(String proxyHost) {
        HttpsURLConnection connection = null;
        try {
            Proxy proxy = new Proxy(Proxy.Type.HTTP, new InetSocketAddress(proxyHost, 37891));
            URL origin = new URL("https://" + HOST + "/");
            connection = (HttpsURLConnection) origin.openConnection(proxy);
            connection.setConnectTimeout(5000);
            connection.setReadTimeout(5000);
            connection.setInstanceFollowRedirects(false);
            // The default socket factory and hostname verifier are intentionally
            // untouched. A temporary self-signed leaf must fail before HTTP.
            connection.connect();
            return "TLS_UNEXPECTEDLY_TRUSTED";
        } catch (SSLException failed) {
            for (Throwable detail = failed; detail != null; detail = detail.getCause()) {
                if (detail instanceof CertificateException || detail instanceof CertPathValidatorException) {
                    return "TLS_CERTIFICATE_REJECTED";
                }
            }
            return "TLS_OTHER_FAILURE";
        } catch (IOException failed) {
            return "PROXY_OR_NETWORK_FAILED";
        } finally {
            if (connection != null) connection.disconnect();
        }
    }
}
