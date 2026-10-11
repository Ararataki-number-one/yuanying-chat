package local.pocketchat;

import android.content.Context;
import android.util.AtomicFile;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.*;
import java.util.function.Consumer;
import java.util.function.Supplier;
import java.util.concurrent.atomic.AtomicLong;

/** Private SDK session checkpoint. Never exported, backed up, or written to diagnostics. */
final class BrowserSessionStore {
  static final int LIMIT=2*1024*1024;
  final AtomicFile file;
  final ExecutorService io=Executors.newSingleThreadExecutor(task->{Thread t=new Thread(task,"browser-session-store");t.setDaemon(true);return t;});
  private Supplier<String> pending;
  private boolean writing;
  // Only the isolated Android regression enables these counters. No session
  // contents, cookies, or paths are retained in diagnostics.
  static final class Probe {
    final AtomicLong offered=new AtomicLong(),coalesced=new AtomicLong(),serialized=new AtomicLong(),mainSerialized=new AtomicLong(),written=new AtomicLong(),serializeNanos=new AtomicLong(),bytes=new AtomicLong();
  }
  volatile Probe probe;
  BrowserSessionStore(Context context){file=new AtomicFile(new File(context.getNoBackupFilesDir(),"gecko-session.json"));}
  void read(Consumer<String> done){io.execute(()->{
    String value=null;
    try(InputStream in=file.openRead();ByteArrayOutputStream out=new ByteArrayOutputStream()){
      byte[] buffer=new byte[8192];int n;while((n=in.read(buffer))!=-1){if(out.size()+n>LIMIT)throw new IOException("Session too large");out.write(buffer,0,n);}value=new String(out.toByteArray(),StandardCharsets.UTF_8);
    }catch(IOException ignored){}done.accept(value);
  });}
  void write(String value){if(value!=null&&value.length()<=LIMIT)write(()->value);}
  synchronized void write(Supplier<String> snapshot){
    if(snapshot==null)return;Probe p=probe;if(p!=null){p.offered.incrementAndGet();if(pending!=null)p.coalesced.incrementAndGet();}
    // Keep at most one waiting SDK snapshot instead of an unbounded queue of
    // serialized histories. The running write is followed by the newest one.
    pending=snapshot;if(writing)return;writing=true;io.execute(this::drain);
  }
  private void drain(){
    byte[] valid=null;long validAt=0;
    for(;;){
      Supplier<String> snapshot;synchronized(this){snapshot=pending;pending=null;if(snapshot==null){writing=false;return;}}
      try{
        Probe p=probe;long started=p==null?0:System.nanoTime();
        if(p!=null){p.serialized.incrementAndGet();if(android.os.Looper.myLooper()==android.os.Looper.getMainLooper())p.mainSerialized.incrementAndGet();}
        String value=snapshot.get();
        if(value!=null&&value.length()<=LIMIT){byte[] data=value.getBytes(StandardCharsets.UTF_8);if(p!=null){p.serializeNanos.addAndGet(System.nanoTime()-started);p.bytes.addAndGet(data.length);}if(data.length<=LIMIT){if(valid==null)validAt=System.nanoTime();valid=data;}}
      }catch(RuntimeException ignored){/* A bad checkpoint must not strand later snapshots. */}
      // Keep one validated result while coalescing newer SDK states. A null,
      // malformed or oversized newer state cannot discard the last valid one.
      // Continuous scrolling/form changes must still leave a durable checkpoint.
      // Bound coalescing to about one second without ever flushing on the UI.
      synchronized(this){if(pending!=null&&(valid==null||System.nanoTime()-validAt<1000000000L))continue;}
      if(valid!=null){FileOutputStream out=null;try{out=file.startWrite();out.write(valid);file.finishWrite(out);Probe p=probe;if(p!=null)p.written.incrementAndGet();}catch(IOException error){if(out!=null)file.failWrite(out);}valid=null;}
    }
  }
}
