package local.pocketchat;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.CookieHandler;
import java.net.CookieManager;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.Principal;
import java.security.cert.Certificate;
import javax.net.ssl.HttpsURLConnection;

final class GatewayHost {
  private static final String ENDPOINT = "https://mock.example/v1/diagnose";
  private static final String TOKEN = "pocketchat-local-synthetic-token-0001";
  private static final String REQUEST_ID = "904c5e3d-9d11-46f2-889e-ac10944566cc";
  private static final String BODY = "{\"version\":1,\"provider\":\"openai\",\"evidence\":[{\"schema\":1,\"engine\":\"GECKO\",\"tabEvidenceId\":\"T3\",\"scope\":\"TAB_CALLBACK_OBSERVATIONS\",\"navigationAttribution\":\"UNKNOWN\",\"events\":[{\"id\":\"E1\",\"kind\":\"LOAD_ERROR\",\"signal\":\"DNS_FAILURE\",\"code\":37,\"category\":5,\"elapsedMs\":17}]}]}";
  private static final String REPLY = "{\"version\":2,\"diagnosis\":{\"hypotheses\":[{\"hypothesis\":\"NAME_RESOLUTION_UNAVAILABLE\",\"tabEvidenceId\":\"T3\",\"evidence\":[{\"eventId\":\"E1\",\"signal\":\"DNS_FAILURE\"}],\"steps\":[\"REVIEW_CONNECTION_STATUS\"]}]}}";
  private static final AiDiagnosticGateway.Settings SETTINGS = new AiDiagnosticGateway.Settings(ENDPOINT, TOKEN, "openai");
  private static int passed;

  interface Action { void run() throws Exception; }

  private static void check(boolean condition) {
    if (!condition) throw new AssertionError("check " + (passed + 1));
    passed++;
  }

  private static void rejects(Action action) throws Exception {
    try { action.run(); }
    catch (IOException | IllegalArgumentException expected) { passed++; return; }
    throw new AssertionError("unexpected acceptance");
  }

  private static String send(AiDiagnosticGateway.Transfer transfer) throws IOException {
    return AiDiagnosticGateway.send(new ChatSession(), 7, SETTINGS, REQUEST_ID, BODY, transfer);
  }

  public static void main(String[] args) throws Exception {
    FakeConnection success = new FakeConnection(200, REPLY);
    AiDiagnosticRoute.reset(success);
    AiDiagnosticGateway.Transfer completed = new AiDiagnosticGateway.Transfer();
    String explanation = send(completed);
    check(explanation.contains("本机观察") && explanation.contains("[T3/E1]") && explanation.contains("远端建议（待核实）"));
    check(explanation.contains("错误码 37/5") && explanation.contains("名称解析服务可能暂时不可用"));
    check(completed.possiblySent());
    check(success.written.toString(StandardCharsets.UTF_8.name()).equals(BODY));
    check(success.getRequestProperty("Authorization").equals("Bearer " + TOKEN));
    check(success.getRequestProperty("Idempotency-Key").equals(REQUEST_ID));
    check(success.getRequestProperty("Cookie") == null && success.getRequestProperty("Proxy-Authorization") == null);
    check(!success.getInstanceFollowRedirects() && !success.getUseCaches());
    check(AiDiagnosticRoute.captures == 1 && AiDiagnosticRoute.opens == 1 && AiDiagnosticRoute.closes == 1);

    FakeConnection redirect = new FakeConnection(307, "");
    AiDiagnosticRoute.reset(redirect);
    rejects(() -> send(new AiDiagnosticGateway.Transfer()));
    check(AiDiagnosticRoute.opens == 1 && !redirect.responseRead);

    for (String invalid : new String[]{
        "{\"reply\":\"unverified\",\"reply\":\"second\"}",
        REPLY + "{}",
        REPLY.replace("\"version\":2", "\"version\":2,\"version\":2"),
        REPLY.replace("\"eventId\":\"E1\"", "\"eventId\":\"E1\",\"eventId\":\"E1\""),
        REPLY.replace("\"T3\"", "\"T4\""),
        REPLY.replace("\"E1\"", "\"E2\""),
        REPLY.replace("DNS_FAILURE", "TIMEOUT"),
        REPLY.replace("NAME_RESOLUTION_UNAVAILABLE", "DEVICE_CLOCK_MISMATCH"),
        REPLY.replace("REVIEW_CONNECTION_STATUS", "REVIEW_DEVICE_DATE_TIME"),
        REPLY.replace("REVIEW_CONNECTION_STATUS", "free remote text"),
        "{\"version\":2,\"diagnosis\":{\"hypotheses\":[]}}",
        " ".repeat(32769) + REPLY
    }) {
      AiDiagnosticRoute.reset(new FakeConnection(200, invalid));
      rejects(() -> send(new AiDiagnosticGateway.Transfer()));
    }
    FakeConnection invalidUtf8 = new FakeConnection(200, REPLY);
    invalidUtf8.reply[3] = (byte) 0xff;
    AiDiagnosticRoute.reset(invalidUtf8);
    rejects(() -> send(new AiDiagnosticGateway.Transfer()));
    String empty = AiDiagnosticReply.render("{\"version\":2,\"diagnosis\":{\"hypotheses\":[]}}".getBytes(StandardCharsets.UTF_8),
        "{\"version\":1,\"provider\":\"openai\",\"evidence\":[{\"tabEvidenceId\":\"T1\",\"events\":[]}]}");
    check(empty.contains("本次未调用模型") && !empty.contains("远端建议"));

    AiDiagnosticRoute.reset(new FakeConnection(409, "{\"reason\":\"result_not_retained\"}"));
    try { send(new AiDiagnosticGateway.Transfer()); throw new AssertionError("unexpected cached response"); }
    catch (AiDiagnosticGateway.DeliveryException expected) { check(expected.getMessage().contains("结果没有保留")); }

    AiDiagnosticRoute.reset(new FakeConnection(200, REPLY));
    AiDiagnosticRoute.networkLostBeforeBody = true;
    AiDiagnosticGateway.Transfer noWrite = new AiDiagnosticGateway.Transfer();
    rejects(() -> send(noWrite));
    check(!noWrite.possiblySent() && AiDiagnosticRoute.next.written.size() == 0);

    AiDiagnosticRoute.reset(new FakeConnection(200, REPLY));
    AiDiagnosticRoute.networkLostAfterBody = true;
    AiDiagnosticGateway.Transfer uncertain = new AiDiagnosticGateway.Transfer();
    rejects(() -> send(uncertain));
    check(uncertain.possiblySent() && AiDiagnosticRoute.next.written.size() > 0);

    AiDiagnosticRoute.reset(new FakeConnection(200, REPLY));
    AiDiagnosticGateway.Transfer stopped = new AiDiagnosticGateway.Transfer();
    stopped.cancel();
    rejects(() -> send(stopped));
    check(!stopped.possiblySent() && AiDiagnosticRoute.captures == 0);
    CookieHandler.setDefault(new CookieManager());
    try {
      rejects(() -> send(new AiDiagnosticGateway.Transfer()));
      check(AiDiagnosticRoute.captures == 0);
    } finally { CookieHandler.setDefault(null); }

    rejects(() -> new AiDiagnosticGateway.Settings("http://mock.example/v1/diagnose", TOKEN, "openai"));
    rejects(() -> new AiDiagnosticGateway.Settings("https://mock.example/v1/diagnose?x=y", TOKEN, "openai"));
    rejects(() -> new AiDiagnosticGateway.Settings("https://x:y@mock.example/v1/diagnose", TOKEN, "openai"));
    rejects(() -> new AiDiagnosticGateway.Settings("https://localhost/v1/diagnose", TOKEN, "openai"));
    rejects(() -> new AiDiagnosticGateway.Settings(ENDPOINT, TOKEN, "unknown"));
    rejects(() -> new AiDiagnosticGateway.Settings("https://api.openai.com/v1/diagnose", TOKEN, "openai"));
    rejects(() -> new AiDiagnosticGateway.Settings("https://api.deepseek.com/v1/diagnose", TOKEN, "deepseek"));
    check(new AiDiagnosticGateway.Settings(ENDPOINT, TOKEN, "deepseek").providerLabel().equals("DeepSeek"));
    if (args.length == 2) {
      byte[] actualResponse = java.nio.file.Files.readAllBytes(java.nio.file.Paths.get(args[1]));
      String confirmed = new String(java.nio.file.Files.readAllBytes(java.nio.file.Paths.get(args[0])), StandardCharsets.UTF_8);
      String rendered = AiDiagnosticReply.render(actualResponse, confirmed);
      check(rendered.contains("[T1/E2]") && rendered.contains("[T3/E2]") && rendered.contains("远端建议（待核实）"));
    }
    System.out.println(passed + " diagnostic HTTP client checks passed (JVM doubles only)");
  }

  static final class FakeConnection extends HttpsURLConnection {
    final ByteArrayOutputStream written = new ByteArrayOutputStream();
    final int status;
    final byte[] reply;
    boolean responseRead, streamOpened;

    FakeConnection(int status, String reply) throws Exception {
      super(new URL(ENDPOINT));
      this.status = status;
      this.reply = reply.getBytes(StandardCharsets.UTF_8);
    }
    @Override public OutputStream getOutputStream() { streamOpened = true; return written; }
    @Override public int getResponseCode() { return status; }
    @Override public String getContentType() { return "application/json"; }
    @Override public String getContentEncoding() { return null; }
    @Override public InputStream getInputStream() { responseRead = true; return new ByteArrayInputStream(reply); }
    @Override public InputStream getErrorStream() { return new ByteArrayInputStream(reply); }
    @Override public void disconnect() {}
    @Override public void connect() {}
    @Override public boolean usingProxy() { return true; }
    @Override public String getCipherSuite() { return "fixture"; }
    @Override public Certificate[] getLocalCertificates() { return null; }
    @Override public Certificate[] getServerCertificates() { return null; }
    @Override public Principal getPeerPrincipal() { return null; }
    @Override public Principal getLocalPrincipal() { return null; }
  }
}

final class ChatSession {}

final class BrowserNetworkGuard {
  static boolean localHost(String host) { return host == null || "localhost".equalsIgnoreCase(host); }
}

final class AppUpdateTransfer {
  static void disconnectLater(java.net.HttpURLConnection connection) { connection.disconnect(); }
}

final class AiDiagnosticRoute implements AutoCloseable {
  static GatewayHost.FakeConnection next;
  static int captures, opens, closes;
  static boolean networkLostBeforeBody, networkLostAfterBody;
  static void reset(GatewayHost.FakeConnection connection) {
    next = connection;
    captures = opens = closes = 0;
    networkLostBeforeBody = networkLostAfterBody = false;
  }
  static AiDiagnosticRoute capture(ChatSession session, long epoch) throws IOException {
    if (epoch != 7) throw new IOException("stale epoch");
    captures++;
    return new AiDiagnosticRoute();
  }
  java.net.HttpURLConnection open(String endpoint) { opens++; return next; }
  void check() throws IOException {
    if ((networkLostBeforeBody && next.streamOpened)
        || (networkLostAfterBody && next.written.size() > 0)) throw new IOException("changed route");
  }
  void released(java.net.HttpURLConnection connection) {}
  @Override public void close() { closes++; }
}
