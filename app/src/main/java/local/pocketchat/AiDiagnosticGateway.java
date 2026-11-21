package local.pocketchat;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.CookieHandler;
import java.net.HttpURLConnection;
import java.net.URI;
import java.net.SocketTimeoutException;
import java.nio.charset.StandardCharsets;
import javax.net.ssl.HttpsURLConnection;

/** Sends the confirmed evidence envelope to exactly one configured HTTPS endpoint. */
final class AiDiagnosticGateway {
  static final class Settings {
    final String endpoint, token, provider;
    Settings(String endpoint, String token, String provider) {
      URI uri;
      try {
        uri = URI.create(endpoint.trim());
      } catch (IllegalArgumentException invalid) {
        throw new IllegalArgumentException("请填写 HTTPS 网关地址，路径为 /v1/diagnose。");
      }
      if (!"https".equals(uri.getScheme()) || BrowserNetworkGuard.localHost(uri.getHost())
          || "api.openai.com".equalsIgnoreCase(uri.getHost()) || "api.deepseek.com".equalsIgnoreCase(uri.getHost())
          || uri.getUserInfo() != null || uri.getRawQuery() != null || uri.getRawFragment() != null
          || !"/v1/diagnose".equals(uri.getRawPath()) || uri.getPort() == 0 || uri.getPort() > 65535) {
        throw new IllegalArgumentException("请填写已授权的 HTTPS 网关地址，路径为 /v1/diagnose。");
      }
      if (!token.matches("[A-Za-z0-9._~-]{32,256}")) {
        throw new IllegalArgumentException("网关访问令牌格式无效。");
      }
      if (!"openai".equals(provider) && !"deepseek".equals(provider)) {
        throw new IllegalArgumentException("请选择 GPT 或 DeepSeek。");
      }
      this.endpoint = uri.toASCIIString();
      this.token = token;
      this.provider = provider;
    }
    String providerLabel() { return "openai".equals(provider) ? "GPT" : "DeepSeek"; }
  }

  /** Errors with static text that can be shown without exposing transport details. */
  static final class DeliveryException extends IOException {
    DeliveryException(String message) { super(message); }
  }

  /** The request may have been delivered from the instant a body write is attempted. */
  static final class Transfer {
    private boolean cancelled, possiblySent;
    private AiDiagnosticRoute route;

    synchronized boolean attach(AiDiagnosticRoute active) {
      if (cancelled) return false;
      route = active;
      return true;
    }

    synchronized void check() throws IOException {
      if (cancelled || Thread.currentThread().isInterrupted()) throw new IOException("已停止等待。");
    }

    synchronized void beginBody() throws IOException {
      check();
      possiblySent = true;
    }

    synchronized boolean possiblySent() { return possiblySent; }

    void cancel() {
      AiDiagnosticRoute active;
      synchronized (this) {
        cancelled = true;
        active = route;
        route = null;
      }
      if (active != null) active.close();
    }

    synchronized void release() { route = null; }
  }

  static String send(ChatSession owner, long epoch, Settings settings, String requestId,
                     String confirmedBody, Transfer transfer) throws IOException {
    if (CookieHandler.getDefault() != null) throw new DeliveryException("当前进程启用了全局 Cookie，已停止发送诊断证据。");
    byte[] body = confirmedBody.getBytes(StandardCharsets.UTF_8);
    if (body.length == 0 || body.length > 16 * 1024) throw new DeliveryException("诊断证据超过大小上限。");
    transfer.check();
    try (AiDiagnosticRoute route = AiDiagnosticRoute.capture(owner, epoch)) {
      if (!transfer.attach(route)) throw new DeliveryException("已停止等待。");
      HttpURLConnection connection = route.open(settings.endpoint);
      try {
        if (!(connection instanceof HttpsURLConnection)) throw new DeliveryException("网关连接必须使用 HTTPS。");
        connection.setRequestMethod("POST");
        connection.setInstanceFollowRedirects(false);
        connection.setUseCaches(false);
        connection.setConnectTimeout(8000);
        connection.setReadTimeout(23000);
        connection.setDoOutput(true);
        connection.setFixedLengthStreamingMode(body.length);
        connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
        connection.setRequestProperty("Accept", "application/json");
        connection.setRequestProperty("Accept-Encoding", "identity");
        connection.setRequestProperty("Authorization", "Bearer " + settings.token);
        connection.setRequestProperty("Idempotency-Key", requestId);
        route.check();
        transfer.check();
        try (OutputStream output = connection.getOutputStream()) {
          route.check();
          transfer.beginBody();
          output.write(body);
        }
        route.check();
        transfer.check();
        int status = connection.getResponseCode();
        if (status == 401 || status == 403) throw new DeliveryException("网关拒绝访问，请核对配置。");
        if (status == 409 || status == 421 || status == 429 || status == 503 || status == 504)
          throw new DeliveryException(problem(connection, status));
        if (status != 200) throw new DeliveryException("网关未返回诊断结果。");
        String type = connection.getContentType();
        String encoding = connection.getContentEncoding();
        if (type == null || !"application/json".equalsIgnoreCase(type.split(";", 2)[0].trim())
            || (encoding != null && !"identity".equalsIgnoreCase(encoding))) {
          throw new DeliveryException("网关回复格式不受支持。");
        }

        byte[] data;
        try (InputStream input = connection.getInputStream()) {
          data = J.read(input, 32 * 1024);
        }
        String reply;
        try {
          reply = AiDiagnosticReply.render(data, confirmedBody);
        } catch (IOException invalid) {
          throw new DeliveryException("网关回复无法与本次证据核对。");
        }
        route.check();
        transfer.check();
        return reply;
      } finally {
        route.released(connection);
        AppUpdateTransfer.disconnectLater(connection);
      }
    } catch (SocketTimeoutException timeout) {
      throw new DeliveryException("网关响应超时。");
    } finally {
      transfer.release();
    }
  }
  private static String problem(HttpURLConnection connection, int status) {
    if (status == 421) return "网关地址与服务端已授权配置不匹配。";
    if (status == 429) return "达到诊断限额，请稍后重试。";
    if (status == 504) return "等待网关超时，供应商处理状态未知。";
    try (InputStream input = connection.getErrorStream()) {
      if (input != null) {
        Object reason = AiDiagnosticJson.object(AiDiagnosticJson.decode(J.read(input, 2048)), "reason").get("reason");
        if ("request_outcome_unknown".equals(reason)) return "上一请求的处理状态未知，同一编号不会重复调用。";
        if ("result_not_retained".equals(reason)) return "网关已完成同一编号的请求，结果没有保留。";
        if ("idempotency_conflict".equals(reason)) return "请求编号已用于不同的证据或模型配置。";
        if ("paid_requests_disabled".equals(reason) || "provider_not_configured".equals(reason))
          return "该供应商的真实调用尚未启用。";
      }
    } catch (IOException ignored) {
      // Respect the fixed failure message even if the error body is malformed.
    }
    return status == 409 ? "同一编号的请求可能仍在处理。" : "网关暂时无法处理诊断。";
  }

}
