package local.pocketchat;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.Principal;
import java.security.cert.Certificate;
import java.util.UUID;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import javax.net.ssl.HttpsURLConnection;

/** Test APK only. Controlled in-memory connection, with no DNS/socket/TLS/provider I/O.
 *
 * This replaces route admission for isolated UI/gateway contract tests. It does
 * not verify the original installed APK, real protected routes, or HTTPS trust.
 * Production AiDiagnosticUi/Gateway/Reply sources are compiled without edits.
 */
final class AiDiagnosticRoute implements AutoCloseable {
  static final String ENDPOINT = "https://diagnostic-fixture.test/v1/diagnose";
  static final String TOKEN = "pocketchat-instrumentation-synthetic-token-0001";
  private static final int MAX_BODY = 16 * 1024;
  private static final long HOLD_MS = 10000;
  private static final String VALID_REPLY = "{\"version\":2,\"diagnosis\":{\"hypotheses\":[{"
      + "\"hypothesis\":\"CERTIFICATE_TRUST_OR_VALIDITY\",\"tabEvidenceId\":\"T1\","
      + "\"evidence\":[{\"eventId\":\"E2\",\"signal\":\"CERTIFICATE_REJECTED\"}],"
      + "\"steps\":[\"REVIEW_DEVICE_DATE_TIME\"]}]}}";

  enum Scenario { VALID, WRONG_REFERENCE, WRONG_TAB, HTTP_403, HOLD_BEFORE_BODY, HOLD_AFTER_BODY }

  /** Snapshot fields contain only this test's synthetic request, never device/browser data. */
  static final class Snapshot {
    final int calls, captures, closes, bodyWrites, responseReads, disconnects, activeRoutes;
    final String body, requestId;
    final boolean post, authorizationMatches, noAmbientHeaders, redirectsDisabled, cachesDisabled;
    Snapshot(Run run) {
      synchronized (run) {
        calls = run.calls;
        captures = run.captures;
        closes = run.closes;
        bodyWrites = run.bodyWrites;
        responseReads = run.responseReads;
        disconnects = run.disconnects;
        activeRoutes = run.activeRoutes;
        body = run.body;
        requestId = run.requestId;
        post = run.post;
        authorizationMatches = run.authorizationMatches;
        noAmbientHeaders = run.noAmbientHeaders;
        redirectsDisabled = run.redirectsDisabled;
        cachesDisabled = run.cachesDisabled;
      }
    }
  }

  private static final class Run {
    final Scenario scenario;
    final CountDownLatch outputOpened = new CountDownLatch(1);
    final CountDownLatch bodyWritten = new CountDownLatch(1);
    final CountDownLatch responseRequested = new CountDownLatch(1);
    // One gate per scenario invocation; reset() starts a fresh hold case.
    final CountDownLatch release = new CountDownLatch(1);
    int calls, captures, closes, bodyWrites, responseReads, disconnects, activeRoutes;
    String body = "", requestId = "";
    boolean post, authorizationMatches, noAmbientHeaders, redirectsDisabled, cachesDisabled;
    Run(Scenario scenario) { this.scenario = scenario; }
  }

  private static volatile Run currentRun = new Run(Scenario.VALID);
  private final ChatSession owner;
  private final long epoch;
  private final Run run;
  private boolean closed;
  private FakeConnection connection;

  private AiDiagnosticRoute(ChatSession owner, long epoch, Run run) {
    this.owner = owner;
    this.epoch = epoch;
    this.run = run;
  }

  static synchronized void reset(Scenario scenario) {
    if (scenario == null) throw new IllegalArgumentException("fixture scenario required");
    synchronized (currentRun) {
      if (currentRun.activeRoutes != 0) throw new IllegalStateException("fixture route still active");
    }
    // Each route keeps its own Run, so a late old callback cannot pollute a new case.
    currentRun = new Run(scenario);
  }

  static Snapshot snapshot() { return new Snapshot(currentRun); }
  static void releaseHold() { currentRun.release.countDown(); }
  static boolean awaitOutputOpened(long timeoutMs) throws InterruptedException {
    return await(currentRun.outputOpened, timeoutMs);
  }
  static boolean awaitBodyWritten(long timeoutMs) throws InterruptedException {
    return await(currentRun.bodyWritten, timeoutMs);
  }
  static boolean awaitResponseRequested(long timeoutMs) throws InterruptedException {
    return await(currentRun.responseRequested, timeoutMs);
  }
  private static boolean await(CountDownLatch signal, long timeoutMs) throws InterruptedException {
    if (timeoutMs < 1 || timeoutMs > HOLD_MS) throw new IllegalArgumentException("fixture wait bound");
    return signal.await(timeoutMs, TimeUnit.MILLISECONDS);
  }

  static String issue(ChatSession session) { return session == null ? "测试会话不可用" : ""; }

  static synchronized AiDiagnosticRoute capture(ChatSession owner, long epoch) throws IOException {
    if (owner == null || epoch != owner.connectionEpoch || Thread.currentThread().isInterrupted())
      throw unavailable();
    Run selected = currentRun;
    synchronized (selected) {
      if (selected.captures >= 16) throw new IOException("fixture request limit");
      selected.captures++;
      selected.activeRoutes++;
    }
    return new AiDiagnosticRoute(owner, epoch, selected);
  }

  synchronized void check() throws IOException {
    if (closed || owner.connectionEpoch != epoch || Thread.currentThread().isInterrupted())
      throw unavailable();
  }

  synchronized HttpURLConnection open(String endpoint) throws IOException {
    check();
    if (!ENDPOINT.equals(endpoint) || connection != null) throw new IOException("fixture endpoint rejected");
    connection = new FakeConnection(this);
    synchronized (run) { run.calls++; }
    return connection;
  }

  void released(HttpURLConnection released) {
    // Deliberately retain the one fake connection until close. close/disconnect
    // are idempotent and no reusable real transport exists in this test.
  }

  @Override public synchronized void close() {
    if (closed) return;
    closed = true;
    if (connection != null) connection.disconnect();
    run.release.countDown();
    // activeRoutes == 0 is a cleanup fence for reset()/test assertions.
    synchronized (run) {
      run.closes++;
      run.activeRoutes--;
    }
  }

  private static IOException unavailable() { return new IOException("synthetic route closed or changed"); }

  private void hold(Scenario phase) throws IOException {
    if (run.scenario != phase) return;
    try {
      if (!run.release.await(HOLD_MS, TimeUnit.MILLISECONDS)) throw new IOException("synthetic hold deadline");
    } catch (InterruptedException stopped) {
      Thread.currentThread().interrupt();
      throw unavailable();
    }
    check();
  }

  private static final class FakeConnection extends HttpsURLConnection {
    private final AiDiagnosticRoute route;
    private final Run run;
    private final ByteArrayOutputStream written = new ByteArrayOutputStream();
    private boolean disconnected, outputClaimed, outputClosed;
    private final OutputStream output = new OutputStream() {
      @Override public void write(int value) throws IOException { write(new byte[]{(byte) value}, 0, 1); }
      @Override public void write(byte[] bytes, int offset, int length) throws IOException {
        if (bytes == null || offset < 0 || length < 0 || offset > bytes.length - length)
          throw new IOException("synthetic body range rejected");
        route.check();
        synchronized (run) {
          if (disconnected || outputClosed || length > MAX_BODY - written.size())
            throw new IOException("synthetic body unavailable");
          written.write(bytes, offset, length);
          run.bodyWrites++;
          run.body = new String(written.toByteArray(), StandardCharsets.UTF_8);
        }
        run.bodyWritten.countDown();
      }
      @Override public void close() { synchronized (run) { outputClosed = true; } }
    };

    FakeConnection(AiDiagnosticRoute route) throws IOException {
      // Constructing a URL is parsing only. No URL.openConnection/connect call.
      super(new URL(ENDPOINT));
      this.route = route;
      this.run = route.run;
    }

    private void available() throws IOException {
      route.check();
      synchronized (run) { if (disconnected) throw unavailable(); }
    }

    @Override public OutputStream getOutputStream() throws IOException {
      available();
      synchronized (run) {
        if (outputClaimed) throw new IOException("synthetic output already opened");
        outputClaimed = true;
        run.requestId = getRequestProperty("Idempotency-Key");
        run.post = "POST".equals(getRequestMethod());
        run.authorizationMatches = ("Bearer " + TOKEN).equals(getRequestProperty("Authorization"));
        run.noAmbientHeaders = getRequestProperty("Cookie") == null && getRequestProperty("Proxy-Authorization") == null;
        run.redirectsDisabled = !getInstanceFollowRedirects();
        run.cachesDisabled = !getUseCaches();
        try {
          if (run.requestId == null || !UUID.fromString(run.requestId).toString().equals(run.requestId))
            throw new IllegalArgumentException();
        } catch (IllegalArgumentException invalid) {
          throw new IOException("synthetic request id rejected");
        }
        if (!run.post || !run.authorizationMatches || !run.noAmbientHeaders
            || !run.redirectsDisabled || !run.cachesDisabled)
          throw new IOException("synthetic request metadata rejected");
      }
      run.outputOpened.countDown();
      route.hold(Scenario.HOLD_BEFORE_BODY);
      available();
      return output;
    }

    @Override public int getResponseCode() throws IOException {
      available();
      run.responseRequested.countDown();
      route.hold(Scenario.HOLD_AFTER_BODY);
      available();
      return run.scenario == Scenario.HTTP_403 ? 403 : 200;
    }
    @Override public String getContentType() { return "application/json"; }
    @Override public String getContentEncoding() { return null; }
    @Override public InputStream getInputStream() throws IOException {
      available();
      synchronized (run) { run.responseReads++; }
      String reply = VALID_REPLY;
      if (run.scenario == Scenario.WRONG_REFERENCE) reply = reply.replace("\"E2\"", "\"E999\"");
      if (run.scenario == Scenario.WRONG_TAB) reply = reply.replace("\"T1\"", "\"T999\"");
      return new ByteArrayInputStream(reply.getBytes(StandardCharsets.UTF_8));
    }
    @Override public InputStream getErrorStream() { return new ByteArrayInputStream(new byte[0]); }
    @Override public void disconnect() {
      synchronized (run) {
        if (disconnected) return;
        disconnected = true;
        run.disconnects++;
      }
      run.release.countDown();
    }
    @Override public void connect() throws IOException { available(); }
    @Override public boolean usingProxy() { return true; }
    @Override public String getCipherSuite() { return "SYNTHETIC_NO_TLS"; }
    @Override public Certificate[] getLocalCertificates() { return null; }
    @Override public Certificate[] getServerCertificates() { return null; }
    @Override public Principal getPeerPrincipal() { return null; }
    @Override public Principal getLocalPrincipal() { return null; }
  }
}
