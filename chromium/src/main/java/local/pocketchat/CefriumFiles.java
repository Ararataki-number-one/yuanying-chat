package local.pocketchat;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Handler;
import android.os.Looper;
import android.webkit.MimeTypeMap;
import com.cefrium.CefriumBrowser;
import com.cefrium.CefriumDownloadClient;
import com.cefrium.CefriumFileChooserCallback;
import com.cefrium.CefriumFileChooserParams;
import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.util.Collections;
import java.util.IdentityHashMap;
import java.util.Objects;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.RejectedExecutionException;
import java.util.function.BooleanSupplier;
import java.util.function.Consumer;
import java.util.function.Predicate;
import org.json.JSONObject;

/** Keeps a file request bound to its browser, current page and admitted environment. */
final class CefriumFiles implements AutoCloseable {
  private final Activity activity;
  private final Context scoped;
  private final Predicate<String> allows;
  private final BooleanSupplier foreground;
  private final Consumer<String> status;
  private final BrowserDownloadStore store;
  private final Handler main = new Handler(Looper.getMainLooper());
  private final Set<CefriumBrowser> browsers = Collections.newSetFromMap(new IdentityHashMap<>());
  private final ExecutorService publishing = Executors.newSingleThreadExecutor(task -> {
    Thread thread = new Thread(task, "cefrium-file-publication");
    thread.setPriority(Thread.MIN_PRIORITY);
    return thread;
  });
  private Pick picker;
  private long pickerGeneration;
  private Transfer transfer;
  private volatile boolean closed;

  CefriumFiles(Activity activity, Context scoped, Predicate<String> allows,
               BooleanSupplier foreground, Consumer<String> status) {
    this.activity = activity;
    this.scoped = scoped;
    this.allows = allows;
    this.foreground = foreground;
    this.status = status;
    store = new BrowserDownloadStore(scoped);
  }

  /** Register before the browser can navigate. Missing a handler enables SDK auto-save. */
  void bind(CefriumBrowser browser) {
    browser.setDownloadClient(new CefriumDownloadClient() {
      @Override public void onBeforeDownload(CefriumBrowser source, CefriumBrowser.DownloadItem item,
                                             CefriumBrowser.BeforeDownloadCallback callback) {
        onMain(() -> beginDownload(source, item, callback));
      }

      @Override public void onDownloadUpdated(CefriumBrowser source, CefriumBrowser.DownloadItem item) {
        onMain(() -> downloadUpdated(source, item));
      }
    });
    if (!closed) browsers.add(browser);
  }

  boolean choose(CefriumBrowser source, CefriumFileChooserParams params, CefriumFileChooserCallback callback) {
    if (callback != null) onMain(() -> beginPicker(source, params, callback));
    return true;
  }

  private void beginPicker(CefriumBrowser source, CefriumFileChooserParams params,
                           CefriumFileChooserCallback callback) {
    long generation = ++pickerGeneration;
    clearPicker();
    String page = page(source);
    if (generation != pickerGeneration || !canBegin(source, page)) {
      cancelPicker(callback);
      if (generation == pickerGeneration) message("当前网页连接尚未确认，未打开文件选择器");
      return;
    }
    CefriumFileChooserParams.Mode mode = params == null ? null : params.getMode();
    boolean multiple = mode == CefriumFileChooserParams.Mode.OPEN_MULTIPLE;
    if (!multiple && mode != CefriumFileChooserParams.Mode.OPEN) {
      cancelPicker(callback);
      message("此网页请求的文件选择模式暂不支持");
      return;
    }
    int request = BrowserFiles.NEXT_REQUEST.getAndIncrement();
    if (request > BrowserFiles.LAST_REQUEST) {
      cancelPicker(callback);
      message("本次浏览已打开过多文件选择器，请重新打开浏览器");
      return;
    }
    Pick selected = new Pick(source, page, request, multiple, callback);
    picker = selected;
    try {
      activity.startActivityForResult(BrowserFiles.chooserIntent(params.getAcceptTypes().toArray(new String[0]), multiple), request);
    } catch (ActivityNotFoundException unavailable) {
      pickerFailed(selected, "设备没有可用的系统文件选择器");
    } catch (RuntimeException unavailable) {
      pickerFailed(selected, "文件选择器暂时无法打开");
    }
  }

  private void pickerFailed(Pick selected, String reason) {
    if (picker != selected) return;
    picker = null;
    cancelPicker(selected.callback);
    message(reason);
  }

  boolean result(int request, int result, Intent data) {
    if (request < BrowserFiles.FIRST_REQUEST || request > BrowserFiles.LAST_REQUEST) return false;
    Pick selected = picker;
    if (selected == null || selected.request != request) return true;
    picker = null;
    if (result != Activity.RESULT_OK || data == null) {
      cancelPicker(selected.callback);
      return true;
    }
    if (!samePage(selected)) {
      cancelPicker(selected.callback);
      message("网页或连接已变化，未交付所选文件");
      return true;
    }
    String[] files;
    try {
      Uri[] uris = BrowserFiles.selectedUris(data, selected.multiple, uri -> BrowserFiles.selectable(activity, uri));
      files = new String[uris.length];
      for (int i = 0; i < uris.length; i++) files[i] = uris[i].toString();
    } catch (IOException invalid) {
      cancelPicker(selected.callback);
      message(invalid.getMessage());
      return true;
    }
    if (!samePage(selected)) {
      cancelPicker(selected.callback);
      message("网页或连接已变化，未交付所选文件");
      return true;
    }
    try { selected.callback.select(files); }
    catch (RuntimeException unavailable) { message("原网页已关闭，未交付所选文件"); }
    return true;
  }

  private boolean samePage(Pick selected) {
    return browsers.contains(selected.source) && Objects.equals(selected.page, page(selected.source)) && allowed(selected.page);
  }

  void navigation(CefriumBrowser browser) {
    if (picker != null && picker.source == browser) {
      pickerGeneration++;
      clearPicker();
    }
  }

  private void clearPicker() {
    Pick selected = picker;
    if (selected == null) return;
    picker = null;
    try { activity.finishActivity(selected.request); }
    catch (RuntimeException ignored) {}
    cancelPicker(selected.callback);
  }

  private static void cancelPicker(CefriumFileChooserCallback callback) {
    try { callback.cancel(); }
    catch (RuntimeException ignored) {}
  }

  private static final class Pick {
    final CefriumBrowser source;
    final String page;
    final int request;
    final boolean multiple;
    final CefriumFileChooserCallback callback;

    Pick(CefriumBrowser source, String page, int request, boolean multiple, CefriumFileChooserCallback callback) {
      this.source = source;
      this.page = page;
      this.request = request;
      this.multiple = multiple;
      this.callback = callback;
    }
  }

  private void beginDownload(CefriumBrowser source, CefriumBrowser.DownloadItem item,
                             CefriumBrowser.BeforeDownloadCallback callback) {
    String page = page(source);
    String target = item.getUrl();
    String destination = downloadAddress(page, target);
    if (transfer != null) {
      callback.cancel();
      message("已有文件正在下载");
      return;
    }
    if (!canBegin(source, page) || !allowed(destination)) {
      callback.cancel();
      message(destination == null ? "文件地址无法在此网页保存" : "浏览器连接尚未确认，未开始下载");
      return;
    }
    long expected = item.getTotalBytes();
    ChromiumRouteLease.Handle lease = ChromiumRouteLease.acquireDownload();
    if (lease == null) {
      callback.cancel();
      message("正在应用环境线路，下载尚未开始");
      return;
    }
    Transfer job = null;
    try {
      AppPrefs.requireDownloadNetwork(scoped);
      if (expected > BrowserDownloadTransfer.MAX_BYTES) throw new IOException("文件超过 512 MB 下载限额");
      File cache = scoped.getCacheDir().getCanonicalFile();
      if (cache.getUsableSpace() < BrowserDownloadTransfer.RESERVE_BYTES + Math.max(expected, 0))
        throw new IOException("可用存储空间不足");
      File directory = Files.createTempDirectory(cache.toPath(), "cefrium-download-").toFile();
      job = new Transfer(source, item.getId(), page, target, destination, directory, lease,
          item.getSuggestedName(), item.getMimeType());
      if (!downloadCurrent(job)) throw new IOException("浏览器连接已变化，未开始下载");
      transfer = job;
      callback.allow(job.payload.getAbsolutePath());
      if (transfer == job && !job.saving) main.postDelayed(job.monitor, 500);
      message("开始下载文件…");
    } catch (IOException | RuntimeException failure) {
      if (job == null) lease.close();
      else cancel(job);
      callback.cancel();
      message(failure instanceof IOException ? failure.getMessage() : "下载暂时无法开始");
    }
  }

  private void downloadUpdated(CefriumBrowser source, CefriumBrowser.DownloadItem item) {
    Transfer job = transfer;
    if (job == null || job.source != source || job.id != item.getId() || job.saving) return;
    long count = item.getReceivedBytes();
    long total = item.getTotalBytes();
    String target = item.getUrl();
    String destination = downloadAddress(job.page, target);
    if (!downloadCurrent(job) || !allowed(destination) || downgrade(job.originalTarget, target)) {
      cancel(job);
      message("下载连接已变化，文件未保存");
      return;
    }
    if (item.isCanceled() || item.isInterrupted()) {
      cancel(job);
      message("下载未完成，文件未保存");
      return;
    }
    if (count > BrowserDownloadTransfer.MAX_BYTES || total > BrowserDownloadTransfer.MAX_BYTES) {
      cancel(job);
      message("文件超过 512 MB 下载限额");
      return;
    }
    if (!item.isComplete()) {
      message("正在下载 · " + BrowserFiles.bytes(Math.max(count, 0)) + (total > 0 ? " / " + BrowserFiles.bytes(total) : ""));
      return;
    }
    if (count < 0 || total >= 0 && total != count || !job.payload.getAbsolutePath().equals(item.getFullPath())) {
      cancel(job);
      message("文件未下载完整，未保存");
      return;
    }
    CefriumDownloadFormat format;
    try {
      MimeTypeMap types = MimeTypeMap.getSingleton();
      format = CefriumDownloadFormat.resolve(job.suggestedName, job.suggestedMime,
          item.getSuggestedName(), item.getMimeType(), types::getMimeTypeFromExtension,
          types::getExtensionFromMimeType);
    } catch (IOException mismatch) {
      cancel(job);
      message(mismatch.getMessage());
      return;
    }
    job.saving = true;
    main.removeCallbacks(job.monitor);
    String fileName = format.name == null ? unnamedFile(format.mime) : format.name;
    BrowserDownloadTransfer.Result completed = new BrowserDownloadTransfer.Result(job.payload, target, "", format.mime, count);
    try {
      publishing.execute(() -> publish(job, completed, fileName, destination));
    } catch (RejectedExecutionException unavailable) {
      job.saving = false;
      cancel(job);
    }
  }

  private void publish(Transfer job, BrowserDownloadTransfer.Result completed, String fileName, String destination) {
    String result;
    try {
      if (!Files.isRegularFile(job.payload.toPath(), LinkOption.NOFOLLOW_LINKS) || Files.size(job.payload.toPath()) != completed.bytes
          || !job.payload.getCanonicalFile().equals(job.payload)) throw new IOException("文件未下载完整，未保存");
      BooleanSupplier valid = () -> downloadCurrent(job) && allowed(destination);
      if (!valid.getAsBoolean()) throw new IOException("下载连接已变化，文件未保存");
      JSONObject saved = store.save(completed, fileName, valid);
      result = "已保存 · " + saved.optString("name") + " · 可在下载中心打开";
    } catch (Exception failure) {
      result = failure instanceof IOException ? failure.getMessage() : "下载失败，文件未保存";
    } finally {
      cleanup(job);
      job.lease.close();
    }
    String notice = result;
    main.post(() -> {
      if (transfer != job) return;
      transfer = null;
      message(notice);
    });
  }

  private static String unnamedFile(String mime) {
    String extension = MimeTypeMap.getSingleton().getExtensionFromMimeType(mime);
    return extension == null ? "文件" : BrowserDownloadStore.safeName("文件." + extension);
  }

  /** Chromium handles blob bytes in their authenticated browser. Confirm the blob's owning origin first. */
  static String downloadAddress(String page, String target) {
    if (BrowserAddressPolicy.allowed(target)) return target;
    if (!BrowserAddressPolicy.allowed(page) || target == null || !target.startsWith("blob:")) return null;
    String inner = target.substring(5);
    if (!BrowserAddressPolicy.allowed(inner)) return null;
    Uri owner = Uri.parse(BrowserAddressPolicy.normalizeInput(page));
    Uri blob = Uri.parse(BrowserAddressPolicy.normalizeInput(inner));
    return Objects.equals(owner.getScheme(), blob.getScheme()) && Objects.equals(owner.getHost(), blob.getHost())
        && effectivePort(owner) == effectivePort(blob) ? page : null;
  }

  private static int effectivePort(Uri uri) {
    return uri.getPort() >= 0 ? uri.getPort() : "https".equals(uri.getScheme()) ? 443 : 80;
  }

  private static boolean downgrade(String original, String current) {
    return original != null && current != null && original.regionMatches(true, 0, "https://", 0, 8)
        && current.regionMatches(true, 0, "http://", 0, 7);
  }

  private boolean downloadCurrent(Transfer job) {
    if (closed || job.cancelled || !allowed(job.page) || !allowed(job.destination)) return false;
    try { AppPrefs.requireDownloadNetwork(scoped); return true; }
    catch (IOException | RuntimeException restricted) { return false; }
  }

  private String page(CefriumBrowser browser) {
    try { return browser == null || browser.isClosed() ? null : browser.getUrl(); }
    catch (RuntimeException unavailable) { return null; }
  }

  private boolean canBegin(CefriumBrowser browser, String page) {
    return foreground.getAsBoolean() && !activity.isFinishing() && !activity.isDestroyed()
        && browsers.contains(browser) && BrowserAddressPolicy.allowed(page) && allowed(page);
  }

  private boolean allowed(String url) {
    if (closed || url == null) return false;
    try { return allows.test(url); }
    catch (RuntimeException denied) { return false; }
  }

  private void cancel(Transfer job) {
    if (job == null || job.cancelled) return;
    job.cancelled = true;
    main.removeCallbacks(job.monitor);
    try { if (!job.source.isClosed()) job.source.cancelDownload(job.id); }
    catch (RuntimeException ignored) {}
    if (job.saving) return;
    if (transfer == job) transfer = null;
    cleanup(job);
    main.postDelayed(() -> cleanup(job), 1500);
    job.lease.close();
  }

  private static void cleanup(Transfer job) {
    File[] files = job.directory.listFiles();
    if (files != null) for (File file : files) file.delete();
    job.directory.delete();
  }

  void routeLost() {
    onMain(() -> {
      pickerGeneration++;
      clearPicker();
      cancel(transfer);
    });
  }

  void retire(CefriumBrowser browser) {
    browsers.remove(browser);
    navigation(browser);
    if (transfer != null && transfer.source == browser) cancel(transfer);
  }

  boolean busy() { return picker != null || transfer != null; }

  @Override public void close() {
    if (closed) return;
    closed = true;
    browsers.clear();
    routeLost();
    publishing.shutdown();
  }

  private void onMain(Runnable action) {
    if (Looper.myLooper() == Looper.getMainLooper()) action.run();
    else main.post(action);
  }

  private void message(String text) { if (!closed && text != null) status.accept(text); }

  private final class Transfer {
    final CefriumBrowser source;
    final int id;
    final String page, originalTarget, destination, suggestedName, suggestedMime;
    final File directory, payload;
    final ChromiumRouteLease.Handle lease;
    final Runnable monitor = this::watch;
    volatile boolean cancelled;
    boolean saving;

    Transfer(CefriumBrowser source, int id, String page, String originalTarget, String destination,
             File directory, ChromiumRouteLease.Handle lease, String suggestedName, String suggestedMime) {
      this.source = source;
      this.id = id;
      this.page = page;
      this.originalTarget = originalTarget;
      this.destination = destination;
      this.directory = directory;
      this.lease = lease;
      this.suggestedName = suggestedName;
      this.suggestedMime = suggestedMime;
      payload = new File(directory, "payload.part");
    }

    private void watch() {
      if (transfer != this || saving || cancelled) return;
      if (!downloadCurrent(this)) {
        cancel(this);
        message("下载连接已变化，文件未保存");
        return;
      }
      File[] files = directory.listFiles();
      long staged = 0;
      if (files != null) for (File file : files) staged += file.length();
      if (staged > BrowserDownloadTransfer.MAX_BYTES || directory.getUsableSpace() < BrowserDownloadTransfer.RESERVE_BYTES) {
        cancel(this);
        message("文件超过下载限额或可用存储空间不足");
        return;
      }
      main.postDelayed(monitor, 500);
    }
  }
}
