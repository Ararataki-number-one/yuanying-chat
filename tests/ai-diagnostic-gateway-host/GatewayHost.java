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
import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

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

  private static JSONObject localEvent(String id, String kind, String signal,
                                       Integer code, Integer category) throws JSONException {
    return new JSONObject().put("id", id).put("kind", kind).put("signal", signal)
        .put("code", code == null ? JSONObject.NULL : code)
        .put("category", category == null ? JSONObject.NULL : category).put("elapsedMs", 17);
  }

  private static JSONObject localTab(String id, JSONArray events) throws JSONException {
    return new JSONObject().put("schema", 1).put("engine", "GECKO").put("tabEvidenceId", id)
        .put("scope", "TAB_CALLBACK_OBSERVATIONS").put("navigationAttribution", "UNKNOWN")
        .put("events", events);
  }

  private static String localPreviewUnchanged(JSONArray evidence) throws Exception {
    JSONObject confirmed = new JSONObject().put("version", 1).put("provider", "openai")
        .put("evidence", evidence);
    String originalBody = confirmed.toString();
    String originalEvidence = evidence.toString();
    String summary = AiDiagnosticReply.localPreview(evidence);
    check(originalBody.equals(confirmed.toString()) && originalEvidence.equals(evidence.toString()));
    check(summary.startsWith("本机观察（Gecko 回调）") && summary.contains("具体导航归属未知。"));
    return summary;
  }

  private static void localPreviewChecks() throws Exception {
    int capturesBefore = AiDiagnosticRoute.captures;
    int opensBefore = AiDiagnosticRoute.opens;
    String[][] known = {
        {"LOAD_ERROR", "DNS_FAILURE", "收到名称解析失败回调", "37", "5"},
        {"LOAD_ERROR", "TIMEOUT", "收到超时回调", "51", "3"},
        {"LOAD_ERROR", "CERTIFICATE_REJECTED", "收到证书拒绝回调", "50", "2"},
        {"LOAD_ERROR", "TLS_FAILURE", "收到 TLS 失败回调", "34", "2"},
        {"CONTENT_CRASH", "CONTENT_CRASH", "收到内容进程崩溃回调", null, null},
        {"CONTENT_KILL", "CONTENT_KILL", "收到内容进程终止回调", null, null},
    };
    for (int i = 0; i < known.length; i++) {
      String[] row = known[i];
      String eventId = "E" + (i + 1);
      Integer code = row[3] == null ? null : Integer.valueOf(row[3]);
      Integer category = row[4] == null ? null : Integer.valueOf(row[4]);
      JSONArray evidence = new JSONArray().put(localTab("T3", new JSONArray()
          .put(localEvent(eventId, row[0], row[1], code, category))));
      String summary = localPreviewUnchanged(evidence);
      check(summary.contains("[T3/" + eventId + "] " + row[2]));
      check(code == null ? !summary.contains("错误码")
          : summary.contains("错误码 " + code + "/" + category));
      check(!summary.contains("null/null") && !summary.contains("远端建议") && !summary.contains("可能"));
      if ("CERTIFICATE_REJECTED".equals(row[1])) {
        // A certificate callback alone does not establish trust, expiry, clock,
        // proxy or site ownership as its cause. Local text stays observational.
        check(!summary.contains("信任关系") && !summary.contains("有效期")
            && !summary.contains("设备时间") && !summary.contains("证书绕过"));
      }
    }

    JSONArray unknown = new JSONArray().put(localTab("T1", new JSONArray()
        .put(localEvent("E8", "LOAD_ERROR", "UNKNOWN", 1024, 9))));
    String unknownText = localPreviewUnchanged(unknown);
    check(unknownText.contains("[T1/E8] 收到未细分的加载错误回调")
        && unknownText.contains("错误码 1024/9") && !unknownText.contains("可能"));

    JSONArray missingCodes = new JSONArray().put(localTab("T1", new JSONArray()
        .put(localEvent("E9", "LOAD_ERROR", "UNKNOWN", null, null))
        .put(localEvent("E10", "PAGE_STOP_FAILURE", "UNKNOWN", null, null))));
    String missingText = localPreviewUnchanged(missingCodes);
    check(missingText.contains("[T1/E9] 收到未细分的加载错误回调")
        && missingText.contains("[T1/E10] 收到加载失败回调"));
    check(!missingText.contains("错误码") && !missingText.contains("null/null"));

    JSONArray progress = new JSONArray()
        .put(localEvent("E1", "LOAD_START", "UNKNOWN", null, null))
        .put(localEvent("E2", "LOCATION_CHANGED", "UNKNOWN", null, null))
        .put(localEvent("E3", "PAGE_STOP_SUCCESS", "UNKNOWN", null, null));
    for (JSONArray evidence : new JSONArray[]{new JSONArray(),
        new JSONArray().put(localTab("T1", new JSONArray())),
        new JSONArray().put(localTab("T1", progress))}) {
      String summary = localPreviewUnchanged(evidence);
      check(summary.contains("所选快照没有记录到故障回调。"));
      check(!summary.contains("[T1/") && !summary.contains("远端建议"));
    }

    JSONArray ordered = new JSONArray()
        .put(localTab("T7", new JSONArray()
            .put(localEvent("E1", "LOAD_START", "UNKNOWN", null, null))
            .put(localEvent("E2", "LOAD_ERROR", "TIMEOUT", 51, 3))
            .put(localEvent("E10", "LOAD_ERROR", "DNS_FAILURE", 37, 5))))
        .put(localTab("T2", new JSONArray()
            .put(localEvent("E1", "LOCATION_CHANGED", "UNKNOWN", null, null))
            .put(localEvent("E2", "LOAD_ERROR", "CERTIFICATE_REJECTED", 50, 2))
            .put(localEvent("E3", "PAGE_STOP_SUCCESS", "UNKNOWN", null, null))));
    String orderedText = localPreviewUnchanged(ordered);
    int first = orderedText.indexOf("[T7/E2]");
    int second = orderedText.indexOf("[T7/E10]");
    int third = orderedText.indexOf("[T2/E2]");
    check(first >= 0 && first < second && second < third);
    check(first == orderedText.lastIndexOf("[T7/E2]") && third == orderedText.lastIndexOf("[T2/E2]"));
    check(!orderedText.contains("[T7/E1]") && !orderedText.contains("[T2/E1]")
        && !orderedText.contains("[T2/E3]"));
    check(AiDiagnosticRoute.captures == capturesBefore && AiDiagnosticRoute.opens == opensBefore);
  }

  public static void main(String[] args) throws Exception {
    localPreviewChecks();
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
