package local.pocketchat;

import java.nio.file.Files;
import java.util.Arrays;
import java.util.Base64;
import static local.pocketchat.DownloadResumeHost.*;

/** Drive the complete production Blob reader through its native entry and delayed browser replies. */
final class BlobCases {
  private static final String URL = "blob:https://chatgpt.com/file-1";
  private static String metadata(int size) {
    return J.obj("size", size, "ready", true, "mime", "").toString();
  }
  private static String chunk(byte[] bytes) {
    return J.obj("chunk", Base64.getEncoder().encodeToString(bytes)).toString();
  }
  private static FileDownloads begin(String url, int holdAt, String... replies) throws Exception {
    FileDownloads d = fresh();
    row(d, "blob");
    ui(() -> {
      d.active = true;
      d.retryUrl = url;
      d.a.remote.holdAt = holdAt;
      d.a.remote.replies.addAll(Arrays.asList(replies));
      d.startBlob(d.ticket, url);
      return null;
    });
    return d;
  }
  static void run() throws Exception {
    byte[] bytes = new byte[192 * 1024 + 17];
    new java.util.Random(7).nextBytes(bytes);
    System.arraycopy(new byte[]{'%', 'P', 'D', 'F', '-'}, 0, bytes, 0, 5);
    FileDownloads pdf = begin(URL, -1, "null", metadata(bytes.length), "null",
        chunk(Arrays.copyOf(bytes, 192 * 1024)), "null", chunk(Arrays.copyOfRange(bytes, 192 * 1024, bytes.length)));
    idle(pdf);idle(pdf);
    check("Production blob fragment writes under partial lease and keeps bytes",
        Arrays.equals(Files.readAllBytes(pdf.temp.toPath()), bytes) && pdf.receivedBytes == bytes.length);
    check("Opaque preview bytes keep their content and recover PDF MIME",
        "application/pdf".equals(pdf.mime) && pdf.a.chosen == 1 && pdf.a.remote.closedEntries == 1);

    Files.write(java.nio.file.Paths.get(System.getProperty("blobScripts")),
        new org.json.JSONArray(pdf.a.remote.scripts).toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));

    for (String change : new String[]{"port","navigation","connection","guard","page"}) {
      FileDownloads d = begin(URL, 4, "null", metadata(2), "null");
      ui(() -> {
        switch(change) {
          case "port": d.a.remote.ports.put(d.a.remote.current,new Object()); break;
          case "navigation": d.a.session.navigationEpoch++; break;
          case "connection": d.a.session.connectionEpoch++; break;
          case "guard": d.a.session.guard.allowed=false; break;
          case "page": d.a.remote.page="https://chatgpt.com/c/two"; break;
        }
        d.a.remote.reply(chunk(new byte[]{5,6}));
        return null;
      });
      idle(d);
      check("Late preview bytes cannot cross a changed "+change,
          d.temp.length()==0 && d.a.chosen==0 && !d.active && d.a.message.contains("下载未完成"));
    }

    FileDownloads d = begin(URL, 2, "null");
    ui(() -> {
      java.util.function.Consumer<String> oldReply = d.a.remote.held;
      d.pause();
      d.active=true;d.cancelled=false;d.retryUrl=URL;
      d.a.remote.holdAt=-1;
      d.a.remote.replies.addAll(Arrays.asList("null",metadata(1),"null",chunk(new byte[]{9})));
      d.startBlob(d.ticket,URL);
      oldReply.accept(metadata(100));
      return null;
    });
    idle(d);
    check("Cancellation and immediate retry deliver only the new file",
        Arrays.equals(Files.readAllBytes(d.temp.toPath()), new byte[]{9}) && d.a.chosen==1 && d.a.remote.closedEntries==2);

    FileDownloads foreign=begin("blob:https://other.example/file",-1);
    idle(foreign);
    check("Cross-origin blob stops before any browser evaluation",foreign.a.remote.callbackCount==0 && foreign.a.chosen==0 && !foreign.active);
    FileDownloads shortRead=begin(URL,-1,"null",metadata(5),"null",chunk(new byte[]{1,2}));
    idle(shortRead);
    check("A truncated fragment cannot publish a damaged document",shortRead.temp.length()==0 && shortRead.a.chosen==0 && !shortRead.active);
  }
}
