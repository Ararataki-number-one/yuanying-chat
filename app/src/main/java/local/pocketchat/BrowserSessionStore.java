package local.pocketchat;

import android.content.Context;
import android.util.AtomicFile;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.*;
import java.util.function.Consumer;

/** Private SDK session checkpoint. Never exported, backed up, or written to diagnostics. */
final class BrowserSessionStore {
  static final int LIMIT=2*1024*1024;
  final AtomicFile file;
  final ExecutorService io=Executors.newSingleThreadExecutor(task->{Thread t=new Thread(task,"browser-session-store");t.setDaemon(true);return t;});
  BrowserSessionStore(Context context){file=new AtomicFile(new File(context.getNoBackupFilesDir(),"gecko-session.json"));}
  void read(Consumer<String> done){io.execute(()->{
    String value=null;
    try(InputStream in=file.openRead();ByteArrayOutputStream out=new ByteArrayOutputStream()){
      byte[] buffer=new byte[8192];int n;while((n=in.read(buffer))!=-1){if(out.size()+n>LIMIT)throw new IOException("Session too large");out.write(buffer,0,n);}value=out.toString(StandardCharsets.UTF_8);
    }catch(IOException ignored){}done.accept(value);
  });}
  void write(String value){if(value==null||value.length()>LIMIT)return;byte[] data=value.getBytes(StandardCharsets.UTF_8);if(data.length>LIMIT)return;io.execute(()->{
    FileOutputStream out=null;try{out=file.startWrite();out.write(data);file.finishWrite(out);}catch(IOException error){if(out!=null)file.failWrite(out);}
  });}
}
