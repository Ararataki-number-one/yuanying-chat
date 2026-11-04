package local.pocketchat;

import android.content.Context;
import android.os.SystemClock;
import android.util.AtomicFile;
import android.util.Log;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;
import org.json.JSONArray;
import org.json.JSONObject;

/** Integration-only full result handoff; logcat carries a bounded receipt, never the payload. */
final class IntegrationEventStore {
  static final int MAX_BYTES=2*1024*1024;
  static final int MAX_JOURNAL_BYTES=4*1024*1024;
  static final Object IO_GATE=new Object();static int pendingBytes;
  static final ThreadPoolExecutor IO=new ThreadPoolExecutor(1,1,0,TimeUnit.MILLISECONDS,new ArrayBlockingQueue<>(128),task->{Thread thread=new Thread(task,"integration-event-io");thread.setPriority(Thread.MIN_PRIORITY);return thread;},new ThreadPoolExecutor.AbortPolicy());
  final Context root;final int slot;final String nonce,action;final long command;
  final JSONObject buildIdentity;int sequence;
  final JSONArray receipts=new JSONArray();volatile boolean publicationFailed;
  IntegrationEventStore(Context context,int slot,String nonce,String action,long command,JSONObject identity)throws Exception {
    root=Profiles.global(context);this.slot=slot;this.nonce=nonce;this.action=action;this.command=command;
    if(!"local.pocketchat.test".equals(root.getPackageName())||slot<0||slot>=Profiles.MAX||nonce==null||!nonce.matches("[0-9a-f]{32}")||action==null||!action.matches("[A-Za-z0-9_-]{1,80}")||command<=0)
      throw new SecurityException("Owned synthetic invocation required");
    buildIdentity=new JSONObject(identity.toString());
  }
  static File file(Context context,int slot,String nonce,int sequence)throws java.io.IOException {
    if(slot<0||slot>=Profiles.MAX||nonce==null||!nonce.matches("[0-9a-f]{32}")||sequence<1||sequence>4096)
      throw new SecurityException("Invalid synthetic event path");
    File directory=new File(Profiles.global(context).getFilesDir(),"integration-events");
    File base=directory.getCanonicalFile(),result=new File(directory,"env"+slot+"-"+nonce+"-"+sequence+".json").getCanonicalFile();
    if(!base.equals(result.getParentFile()))throw new SecurityException("Invalid synthetic event directory");
    return result;
  }
  static File journalFile(Context context,int slot,String nonce)throws java.io.IOException {
    File directory=file(context,slot,nonce,1).getParentFile();
    File result=new File(directory,"env"+slot+"-"+nonce+"-receipts.json").getCanonicalFile();
    if(!directory.equals(result.getParentFile()))throw new SecurityException("Invalid synthetic receipt directory");
    return result;
  }
  synchronized void emit(String kind,JSONObject result)throws Exception {
    if(publicationFailed)throw new IllegalStateException("Synthetic invocation publication failed");
    try{
    int index=++sequence;if(index>4096)throw new IllegalStateException("Synthetic event count exceeded");
    JSONObject event=J.obj("kind",kind,"result",result,"nativeContext","environment-"+(slot+1),"processSlot",slot);
    JSONObject value=J.obj("schema",1,"sourceCommit",buildIdentity.getString("sourceCommit"),"buildIdentity",buildIdentity,
      "runNonce",nonce,"fixtureAction",action,"command",command,"sequence",index,"nativeContext","environment-"+(slot+1),"processSlot",slot,
      "observedAtElapsedRealtime",SystemClock.elapsedRealtime(),"event",event);
    byte[] bytes=(value.toString()+"\n").getBytes(StandardCharsets.UTF_8);
    if(bytes.length>MAX_BYTES)throw new IllegalStateException("Synthetic event payload exceeded bound");
    File target=file(root,slot,nonce,index);
    StringBuilder digest=new StringBuilder();for(byte part:MessageDigest.getInstance("SHA-256").digest(bytes))digest.append(String.format(java.util.Locale.ROOT,"%02x",part&255));
    JSONObject receipt=J.obj("kind","eventReceipt","schema",1,"runNonce",nonce,"fixtureAction",action,"command",command,"sequence",index,
      "nativeContext","environment-"+(slot+1),"processSlot",slot,"eventKind",kind,"payloadBytes",bytes.length,"payloadSha256",digest.toString());
    String marker=receipt.toString();
    // Do not add disk fsync to input/geometry measurements. Immutable payloads publish in order on one bounded test-only worker.
    synchronized(IO_GATE){if(pendingBytes>8*1024*1024-bytes.length)throw new IllegalStateException("Synthetic event byte queue exceeded");pendingBytes+=bytes.length;}
    try{IO.execute(()->{
      try{if(publicationFailed)throw new java.io.IOException("Synthetic invocation publication failed");File directory=target.getParentFile();if(!directory.isDirectory()&&!directory.mkdirs()&&!directory.isDirectory())throw new java.io.IOException("Synthetic event directory unavailable");
        AtomicFile atomic=new AtomicFile(target);FileOutputStream out=null;
        try{out=atomic.startWrite();out.write(bytes);atomic.finishWrite(out);}catch(Exception error){if(out!=null)atomic.failWrite(out);throw error;}
        if(publicationFailed)throw new java.io.IOException("Synthetic invocation publication failed");
        // Persist the exact native marker, never derive a receipt from a payload
        // on the host. One worker publishes immutable, ordered prefix snapshots.
        receipts.put(marker);
        byte[] journal=(J.obj("schema",1,"status","committed","runNonce",nonce,"processSlot",slot,"fixtureAction",action,"command",command,"receipts",receipts).toString()+"\n").getBytes(StandardCharsets.UTF_8);
        if(journal.length>MAX_JOURNAL_BYTES)throw new java.io.IOException("Synthetic receipt journal exceeded bound");
        AtomicFile committed=new AtomicFile(journalFile(root,slot,nonce));FileOutputStream journalOut=null;
        try{journalOut=committed.startWrite();journalOut.write(journal);committed.finishWrite(journalOut);}catch(Exception error){if(journalOut!=null)committed.failWrite(journalOut);throw error;}
        // Logcat carries the small pointer only after all exact payload bytes have been durably published.
        Log.i("PocketGeckoIntegration",marker);
      }catch(Exception failure){publicationFailed=true;failure(failure);}finally{synchronized(IO_GATE){pendingBytes-=bytes.length;}}
    });}catch(RuntimeException failure){synchronized(IO_GATE){pendingBytes-=bytes.length;}throw failure;}
    }catch(Exception failure){publicationFailed=true;throw failure;}
  }
  void failure(Exception error){Log.e("PocketGeckoIntegration",J.obj("kind","eventTransportError","error",error.toString(),"runNonce",nonce,"fixtureAction",action,"command",command,"nativeContext","environment-"+(slot+1),"processSlot",slot).toString());}
}
