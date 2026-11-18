package local.pocketchat;

import android.os.SystemClock;
import android.util.Base64;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.util.Locale;
import java.util.Objects;
import java.util.UUID;
import org.json.JSONObject;

/** A single page-owned blob. Browser access runs on the UI thread, disk writes on the download worker. */
final class BlobDownload {
  private static final int CHUNK_BYTES = 192 * 1024;
  private static final long DISK_RESERVE = 64L * 1024 * 1024;
  private final FileDownloads downloads;
  private final MainActivity activity;
  private final long attempt, navigation, connection;
  private final String page;
  private final Object document;
  private final String key = JSONObject.quote("__pocketFile" + UUID.randomUUID().toString().replace("-", ""));
  private volatile boolean closed;
  private File file;
  private long size, offset;

  BlobDownload(FileDownloads downloads, long attempt) {
    this.downloads = downloads;
    this.activity = downloads.a;
    this.attempt = attempt;
    page = activity.remote.getUrl();
    document = activity.remote.ports.get(activity.remote.current);
    navigation = activity.session.navigationEpoch;
    connection = activity.session.connectionEpoch;
  }

  private boolean sameDocument() {
    return document != null && document == activity.remote.ports.get(activity.remote.current)
        && navigation == activity.session.navigationEpoch && Objects.equals(page, activity.remote.getUrl());
  }

  private boolean current() {
    if (closed || !downloads.valid(attempt)) return false;
    if (sameDocument() && connection == activity.session.connectionEpoch && activity.session.guard.allowed()) return true;
    downloads.fail(attempt, "文件页面已改变，请重试");
    return false;
  }

  void start(String url) {
    if (!current()) return;
    if (!GeckoNavigationPolicy.blobFrom(url, page)) {
      downloads.fail(attempt, "文件页面已改变，请重试");
      return;
    }
    try {
      if (downloads.temp != null) downloads.temp.delete();
      file = File.createTempFile("download-", ".part", activity.getCacheDir());
      downloads.temp = file;
      DownloadTasks.put(downloads.task, "partial", file.getName());
      if (!downloads.saveTask()) return;
      downloads.resumeValidator = "";
      // Install the entry synchronously. A fetch completing after close cannot recreate it.
      String script = "void((()=>{const f=window[" + key + "]={abort:new AbortController()};"
          + "fetch(" + JSONObject.quote(url) + ",{signal:f.abort.signal}).then(r=>{if(!r.ok)throw new Error();return r.blob();})"
          + ".then(b=>Object.assign(f,{blob:b,size:b.size,mime:b.type,ready:true})).catch(()=>{f.error=true;});})())";
      activity.remote.evaluateJavascript(script, ignored -> pollMetadata(SystemClock.elapsedRealtime() + 15000));
    } catch (Exception error) {
      downloads.fail(attempt, error.getMessage());
    }
  }

  private void pollMetadata(long deadline) {
    if (!current()) return;
    String script = "(()=>{const f=window[" + key + "];return f?{ready:f.ready,size:f.size,mime:f.mime,error:f.error}:{};})()";
    activity.remote.evaluateJavascript(script, raw -> {
      if (!current()) return;
      JSONObject result = J.parse(raw);
      if (result.optBoolean("error")) {
        downloads.fail(attempt, "文件链接已失效，请重新点按下载");
        return;
      }
      if (!result.optBoolean("ready")) {
        if (SystemClock.elapsedRealtime() < deadline) activity.handler.postDelayed(() -> pollMetadata(deadline), 120);
        else downloads.fail(attempt, "读取文件超时，请重试");
        return;
      }
      size = result.optLong("size", -1);
      String contentType = result.optString("mime");
      boolean pdf = "application/pdf".equalsIgnoreCase(contentType) || downloads.name.toLowerCase(Locale.ROOT).endsWith(".pdf");
      if (size < 0 || (size == 0 && pdf)) {
        downloads.fail(attempt, "网页没有提供有效的文件内容");
        return;
      }
      if (size > FileDownloads.MAX || size > activity.getCacheDir().getUsableSpace() - DISK_RESERVE) {
        downloads.fail(attempt, "文件超过 512 MB 或剩余空间不足");
        return;
      }
      downloads.totalBytes = size;
      downloads.receivedBytes = 0;
      downloads.responseMetadata(downloads.retryUrl, "", contentType);
      nextChunk();
    });
  }

  private void nextChunk() {
    if (!current()) return;
    if (offset == size) {
      downloads.clearBlob();
      downloads.choose(attempt);
      return;
    }
    long start = offset, end = Math.min(size, start + CHUNK_BYTES);
    String script = "void((async()=>{const f=window[" + key + "];if(!f)return;try{"
        + "const bytes=new Uint8Array(await f.blob.slice(" + start + "," + end + ").arrayBuffer());"
        + "let text='';for(let i=0;i<bytes.length;i+=8192)text+=String.fromCharCode(...bytes.subarray(i,i+8192));"
        + "f.chunk=btoa(text);}catch{f.error=true;}})())";
    activity.remote.evaluateJavascript(script, ignored -> readChunk(start, end, SystemClock.elapsedRealtime() + 10000));
  }

  private void readChunk(long start, long end, long deadline) {
    if (!current()) return;
    String script = "(()=>{const f=window[" + key + "];if(!f||f.error)return {error:true};"
        + "if(typeof f.chunk!=='string')return {};const chunk=f.chunk;delete f.chunk;return {chunk};})()";
    activity.remote.evaluateJavascript(script, raw -> {
      if (!current()) return;
      JSONObject result = J.parse(raw);
      if (result.optBoolean("error")) {
        downloads.fail(attempt, "读取文件失败");
      } else if (result.has("chunk")) {
        downloads.worker.execute(() -> writeChunk(start, end, result));
      } else if (SystemClock.elapsedRealtime() < deadline) {
        activity.handler.postDelayed(() -> readChunk(start, end, deadline), 100);
      } else {
        downloads.fail(attempt, "读取文件超时");
      }
    });
  }

  private void writeChunk(long start, long end, JSONObject chunk) {
    try {
      byte[] bytes = Base64.decode(chunk.getString("chunk"), Base64.DEFAULT);
      if (bytes.length != end - start) throw new IOException();
      SealedFileIo.lease(file, () -> {
        if (closed || !downloads.valid(attempt) || file.length() != start) throw new IOException();
        try (FileOutputStream out = new FileOutputStream(file, true)) { out.write(bytes); }
        return null;
      });
      activity.handler.post(() -> {
        if (!current()) return;
        offset = end;
        downloads.receivedBytes = end;
        boolean pdf = start == 0 && bytes.length >= 5 && bytes[0] == '%' && bytes[1] == 'P'
            && bytes[2] == 'D' && bytes[3] == 'F' && bytes[4] == '-';
        if (pdf && "application/octet-stream".equals(downloads.mime)) downloads.responseMetadata(downloads.retryUrl, "", "application/pdf");
        downloads.transferProgress();
        nextChunk();
      });
    } catch (Exception error) {
      if (!closed) downloads.fail(attempt, "文件片段保存失败，请重试");
    }
  }

  void close() {
    if (closed) return;
    closed = true;
    if (file != null && sameDocument()) {
      activity.remote.evaluateJavascript("void((()=>{const f=window[" + key + "];if(f)f.abort.abort();delete window[" + key + "];})())", null);
    }
  }
}
