package local.pocketchat;

import android.app.Activity;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageInfo;
import android.content.pm.PackageInstaller;
import android.content.pm.PackageManager;
import android.content.pm.Signature;
import android.net.ConnectivityManager;
import android.net.NetworkCapabilities;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Process;
import android.os.SystemClock;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FilterInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.URL;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Arrays;
import java.util.UUID;
import java.util.concurrent.ExecutorService;

/** Downloads an original-signed feature into one inherit-existing package transaction. */
final class ChromiumModuleInstaller {
  static final String SLOT = "chromiumInstallSlot";
  static final String STATUS_ACTION = "local.pocketchat.CHROMIUM_INSTALL_STATUS";
  private static final String DELIVERY = "local.pocketchat.CHROMIUM_DELIVERY";
  private static final String STATE = "chromium-module-install";
  private static final String OLD_SESSION = "sessionId";
  private static final ExecutorService WORKER = AppUpdateManager.backgroundExecutor("chromium-install");
  private static volatile Operation current;

  private ChromiumModuleInstaller() {}

  static boolean supported(Context context) {
    return Build.VERSION.SDK_INT >= ChromiumModulePolicy.MIN_ANDROID && deviceAbi() != null;
  }

  static boolean available(Context context) {
    if (!supported(context) || !ChromiumModulePolicy.PACKAGE_NAME.equals(context.getPackageName())) return false;
    try {
      Bundle flags = AppVersion.metadata(context);
      if (flags == null || !flags.getBoolean(DELIVERY)) return false;
      PackageInfo info = packageInfo(context);
      trustedCertificate(info);
      return ChromiumModulePolicy.officialOrigin(ChromiumModulePolicy.metadata(identity(context, info, ""), false));
    } catch (IOException | RuntimeException unavailable) {
      return false;
    }
  }

  static boolean installed(Context context) {
    if (!supported(context)) return false;
    try {
      PackageInfo info = context.getPackageManager().getPackageInfo(context.getPackageName(), 0);
      return info.splitNames != null && Arrays.asList(info.splitNames).contains(ChromiumModulePolicy.MODULE)
          && info.applicationInfo != null && info.applicationInfo.nativeLibraryDir != null
          && new File(info.applicationInfo.nativeLibraryDir, "libcef.so").isFile();
    } catch (PackageManager.NameNotFoundException | RuntimeException unavailable) {
      return false;
    }
  }

  static void show(Activity activity, int slot) {
    activity.startActivity(new Intent(activity, ChromiumModuleInstallActivity.class).putExtra(SLOT, slot));
  }

  static Operation current() { return current; }

  static synchronized Operation begin(Context context, int slot) {
    if (current != null && !current.done) return current;
    Operation work = new Operation(Profiles.global(context), slot);
    current = work;
    WORKER.execute(work::run);
    return work;
  }

  static void receive(Context context, Intent status) {
    if (!STATUS_ACTION.equals(status.getAction())) return;
    Operation work = current;
    if (work == null || work.done || status.getIntExtra(PackageInstaller.EXTRA_SESSION_ID, -1) != work.sessionId
        || work.senderToken == null || !work.senderToken.equals(status.getData())) return;
    String target = status.getStringExtra(PackageInstaller.EXTRA_PACKAGE_NAME);
    if (target != null && !context.getPackageName().equals(target)) return;
    int result = status.getIntExtra(PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_FAILURE);
    if (result == PackageInstaller.STATUS_PENDING_USER_ACTION) {
      Intent confirmation = status.getParcelableExtra(Intent.EXTRA_INTENT);
      if (confirmation != null) work.askForConfirmation(confirmation);
      else work.finish("Android 未返回安装确认，请重试。");
      return;
    }
    forgetSession(context, work.sessionId);
    if (result == PackageInstaller.STATUS_SUCCESS && installed(context)) {
      work.finish("Chromium 组件已安装。返回环境设置后即可选择内核。");
    } else if (result == PackageInstaller.STATUS_FAILURE_ABORTED) {
      work.finish("安装已取消，可以重新下载。");
    } else {
      work.finish("Android 未能安装组件，请稍后重试。");
    }
  }

  private static String deviceAbi() {
    if (!Process.is64Bit()) return null;
    String arch = System.getProperty("os.arch", "");
    if ("aarch64".equals(arch) || "arm64".equals(arch)) return "arm64-v8a";
    if ("x86_64".equals(arch) || "amd64".equals(arch)) return "x86_64";
    return null;
  }

  private static PackageInfo packageInfo(Context context) throws IOException {
    try {
      return context.getPackageManager().getPackageInfo(context.getPackageName(), AppUpdateFiles.flags());
    } catch (PackageManager.NameNotFoundException failure) {
      throw new IOException("无法核对 PocketChat 当前安装版本", failure);
    }
  }

  private static byte[] trustedCertificate(PackageInfo info) throws IOException {
    Signature[] certificates = info.signingInfo == null ? null : info.signingInfo.getApkContentsSigners();
    if (certificates == null || certificates.length != 1) throw invalidPackage();
    byte[] certificate = certificates[0].toByteArray();
    if (!AppUpdatePolicy.SIGNER.equals(AppUpdatePolicy.hash(certificate))) throw invalidPackage();
    return certificate;
  }

  private static ChromiumModulePolicy.Installed identity(Context context, PackageInfo info, String baseSha256) throws IOException {
    String version = info.versionName;
    if (!AppUpdatePolicy.version(version) || AppUpdateFiles.code(info) <= 0) throw invalidPackage();
    String tag = AppUpdatePolicy.tag(version, AppVersion.channel(context), AppVersion.candidateNumber(context));
    return new ChromiumModulePolicy.Installed(version, AppUpdateFiles.code(info), tag, deviceAbi(), baseSha256);
  }

  private static IOException invalidPackage() {
    return new IOException("当前 PocketChat 版本无法验证选装组件");
  }

  private static SharedPreferences sessionState(Context context) {
    return context.getSharedPreferences(STATE, Context.MODE_PRIVATE);
  }

  private static void forgetSession(Context context, int id) {
    SharedPreferences state = sessionState(context);
    if (state.getInt(OLD_SESSION, -1) == id) state.edit().remove(OLD_SESSION).apply();
  }

  private static void discardPreviousSession(Context context, PackageInstaller installer) {
    int old = sessionState(context).getInt(OLD_SESSION, -1);
    if (old < 0) return;
    abandon(installer, old);
    forgetSession(context, old);
  }

  private static void abandon(PackageInstaller installer, int id) {
    try { installer.abandonSession(id); }
    catch (IllegalArgumentException | SecurityException ignored) {
      // Android already retired the session or took ownership at commit.
    }
  }

  static final class Operation {
    final Context context;
    final int slot;
    volatile boolean cancelled, submitted, done;
    volatile long read, total;
    volatile String message = "正在核对已安装版本与环境网络…";
    volatile int sessionId = -1;
    volatile Uri senderToken;
    volatile ChromiumModuleRoute transfer;
    private Intent confirmation;
    private boolean wifiOnly;
    private long lastWifiCheck;

    Operation(Context context, int slot) {
      this.context = context;
      this.slot = slot;
    }

    synchronized void cancel() {
      if (done || submitted || cancelled) return;
      cancelled = true;
      message = "正在取消下载…";
      ChromiumModuleRoute active = transfer;
      if (active != null) active.close();
    }

    synchronized void finish(String title) {
      if (done) return;
      confirmation = null;
      message = title;
      done = true;
    }

    synchronized void askForConfirmation(Intent request) {
      if (!done) {
        confirmation = new Intent(request);
        message = "请在 Android 安装界面确认。";
      }
    }

    synchronized Intent takeConfirmation() {
      Intent request = confirmation;
      confirmation = null;
      return request;
    }

    synchronized boolean hasConfirmation() { return confirmation != null; }

    synchronized void commit(PackageInstaller.Session session) throws IOException {
      checkStopped();
      intentSender(session);
      submitted = true;
      message = "已交给 Android 安装，请在系统界面确认。";
    }

    private void intentSender(PackageInstaller.Session session) {
      senderToken = Uri.parse("pocketchat://chromium-install/" + UUID.randomUUID());
      Intent callback = new Intent(context, ChromiumModuleReceiver.class).setAction(STATUS_ACTION).setData(senderToken);
      // Package Installer inserts status extras, which requires a mutable explicit PendingIntent.
      int flags = PendingIntent.FLAG_CANCEL_CURRENT;
      if (Build.VERSION.SDK_INT >= 31) flags |= PendingIntent.FLAG_MUTABLE;
      PendingIntent result = PendingIntent.getBroadcast(context, sessionId, callback, flags);
      session.commit(result.getIntentSender());
    }

    void run() {
      PackageInstaller installer = null;
      try {
        installer = context.getPackageManager().getPackageInstaller();
        if (!available(context) || !AppUpdates.validSlot(slot)) throw invalidPackage();
        if (!context.getPackageManager().canRequestPackageInstalls()) throw new IOException("请先允许 PocketChat 安装组件");
        if (installed(context)) {
          finish("Chromium 组件已安装，返回设置后即可选择。");
          return;
        }
        discardPreviousSession(context, installer);
        wifiOnly = AppSettings.bool(context, "updateWifiOnly", true);
        checkStopped();
        try (ChromiumModuleRoute route = ChromiumModuleRoute.acquire(context, slot, () -> cancelled)) {
          transfer = route;
          checkStopped();
          PackageInfo before = packageInfo(context);
          File base = new File(before.applicationInfo.sourceDir);
          byte[] certificate = trustedCertificate(before);
          ChromiumModulePolicy.Installed identity = identity(context, before, hash(base));
          byte[] metadata = readSmall(route, ChromiumModulePolicy.metadata(identity, false), ChromiumModulePolicy.MAX_METADATA);
          byte[] signature = readSmall(route, ChromiumModulePolicy.metadata(identity, true), ChromiumModulePolicy.MAX_SIGNATURE);
          ChromiumModulePolicy.Release release = ChromiumModulePolicy.verify(metadata, signature, certificate, identity);
          total = release.totalBytes;
          message = "正在下载并核验 Chromium 组件…";
          stage(installer, route, base, identity, release);
        } finally {
          transfer = null;
        }
      } catch (IOException | RuntimeException failure) {
        if (installer != null && sessionId >= 0 && !submitted) {
          abandon(installer, sessionId);
          forgetSession(context, sessionId);
        }
        finish(cancelled ? "下载已取消。" : AppUpdateManager.readable(failure, "Chromium 组件未能安装，请稍后重试。"));
      }
    }

    private void stage(PackageInstaller installer, ChromiumModuleRoute route, File base,
        ChromiumModulePolicy.Installed identity, ChromiumModulePolicy.Release release) throws IOException {
      PackageInstaller.SessionParams params = new PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_INHERIT_EXISTING);
      params.setAppPackageName(context.getPackageName());
      params.setSize(release.totalBytes);
      if (Build.VERSION.SDK_INT >= 31) params.setRequireUserAction(PackageInstaller.SessionParams.USER_ACTION_REQUIRED);
      sessionId = installer.createSession(params);
      if (!sessionState(context).edit().putInt(OLD_SESSION, sessionId).commit()) {
        throw new IOException("无法保存安装进度，请检查存储空间");
      }
      try (PackageInstaller.Session session = installer.openSession(sessionId)) {
        for (ChromiumModulePolicy.Split split : release.splits) stageSplit(session, route, identity, split);
        PackageInfo after = packageInfo(context);
        trustedCertificate(after);
        if (!base.getPath().equals(after.applicationInfo.sourceDir) || AppUpdateFiles.code(after) != identity.code
            || !identity.baseSha256.equals(hash(base)) || installed(context)) throw invalidPackage();
        if (!context.getPackageManager().canRequestPackageInstalls()) {
          throw new IOException("Android 安装权限已变化，请重新下载安装");
        }
        route.requireVerified();
        commit(session);
      }
    }

    private void stageSplit(PackageInstaller.Session session, ChromiumModuleRoute route,
        ChromiumModulePolicy.Installed identity, ChromiumModulePolicy.Split split) throws IOException {
      // This single private staging file can also be overwritten after an interrupted process.
      File cache = new File(context.getCacheDir(), "chromium-module-transfer");
      if (!cache.isDirectory() && !cache.mkdirs()) throw new IOException("无法准备 Chromium 下载目录");
      File staging = new File(cache, "split.apk");
      try {
        fetch(route, ChromiumModulePolicy.artifact(identity, split), body -> {
          try (InputStream progress = new FilterInputStream(body) {
            @Override public int read(byte[] buffer, int offset, int length) throws IOException {
              int count = super.read(buffer, offset, length);
              if (count > 0) read += count;
              return count;
            }
          }) {
            AppUpdatePolicy.copyVerified(progress, staging, split.bytes, split.sha256, () -> cancelled);
            return null;
          }
        });
        try (InputStream verified = new FileInputStream(staging);
             OutputStream out = session.openWrite(split.name + ".apk", 0, split.bytes)) {
          byte[] buffer = new byte[65_536];
          for (int count; (count = verified.read(buffer)) != -1;) {
            checkStopped();
            out.write(buffer, 0, count);
          }
          session.fsync(out);
        }
      } finally {
        staging.delete();
      }
    }

    private byte[] readSmall(ChromiumModuleRoute route, String origin, int maximum) throws IOException {
      return fetch(route, origin, body -> {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        byte[] buffer = new byte[4096];
        for (int count; (count = body.read(buffer)) != -1;) {
          if (bytes.size() + count > maximum) throw new IOException("Chromium 安装清单大小无效");
          bytes.write(buffer, 0, count);
        }
        return bytes.toByteArray();
      });
    }

    private <T> T fetch(ChromiumModuleRoute route, String origin, ReadBody<T> task) throws IOException {
      String url = origin;
      for (int redirects = 0; redirects < 5; redirects++) {
        checkStopped();
        try {
          ChromiumModuleHttp.Response response = ChromiumModuleHttp.get(route, origin, url);
          int status = response.status;
          if (status == 301 || status == 302 || status == 303 || status == 307 || status == 308) {
            if (response.location == null) throw new IOException("Chromium 组件下载地址无效");
            url = new URL(new URL(url), response.location).toString();
            continue;
          }
          if (status == 404) throw new IOException("当前版本暂未提供匹配的 Chromium 组件");
          if (status != 200) throw new IOException("Chromium 组件下载暂不可用，请稍后重试");
          InputStream body = new FilterInputStream(response.body) {
            @Override public int read(byte[] buffer, int offset, int length) throws IOException {
              checkStopped();
              if (!route.current()) throw new IOException("环境网络已变化，Chromium 下载已停止");
              return super.read(buffer, offset, length);
            }
          };
          T result = task.read(body);
          checkStopped();
          route.requireVerified();
          return result;
        } finally {
          route.closeConnection();
        }
      }
      throw new IOException("Chromium 组件下载跳转次数过多");
    }

    private String hash(File file) throws IOException {
      try (InputStream in = new FileInputStream(file)) {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        byte[] buffer = new byte[65_536];
        for (int count; (count = in.read(buffer)) != -1;) {
          checkStopped();
          digest.update(buffer, 0, count);
        }
        return AppUpdatePolicy.hex(digest.digest());
      } catch (NoSuchAlgorithmException e) {
        throw new IOException(e);
      }
    }

    private void checkStopped() throws IOException {
      if (cancelled) throw new IOException("下载已取消");
      long now = SystemClock.elapsedRealtime();
      if (!wifiOnly || now - lastWifiCheck < 1000 && lastWifiCheck > 0) return;
      ConnectivityManager manager = context.getSystemService(ConnectivityManager.class);
      NetworkCapabilities network = manager == null ? null : manager.getNetworkCapabilities(manager.getActiveNetwork());
      if (network == null || !network.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)) {
        throw new AppUpdateRoute.Unavailable("当前设置要求使用 Wi-Fi 下载，请连接 Wi-Fi 后重试");
      }
      lastWifiCheck = now;
    }
  }

  private interface ReadBody<T> { T read(InputStream stream) throws IOException; }
}
