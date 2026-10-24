package local.pocketchat;

import android.content.Context;
import android.os.Debug;
import android.os.Looper;
import android.os.Process;
import android.os.SystemClock;
import java.io.File;
import java.io.FileInputStream;
import java.security.MessageDigest;
import org.json.JSONObject;

/** Test-only, post-benchmark stack sampling. It never wraps a formal timed save. */
final class ExperienceSaveSampling {
  static final int BUFFER_BYTES=16*1024*1024,MAX_FILE_BYTES=32*1024*1024,INTERVAL_US=1000;
  final String nonce;
  final File file;
  final int pid=Process.myPid(),mainTid=Process.myTid();
  final String mainThreadName=Thread.currentThread().getName();
  boolean active;
  JSONObject started,receipt;
  ExperienceSaveSampling(Context context,String value)throws Exception{
    if(!"local.pocketchat.test".equals(context.getPackageName())||Profiles.slot(context)!=0)throw new SecurityException("Synthetic diagnostic only");
    requireMain();nonce=value;file=path(context,nonce);
  }
  static File path(Context context,String nonce)throws java.io.IOException{
    if(nonce==null||!nonce.matches("[0-9a-f]{32}"))throw new SecurityException("Owned diagnostic nonce required");
    File directory=new File(Profiles.global(context).getFilesDir(),"experience-sampling-traces").getCanonicalFile();
    File result=new File(directory,"history-save-"+nonce+".trace").getCanonicalFile();
    if(!directory.equals(result.getParentFile()))throw new SecurityException("Invalid diagnostic path");
    return result;
  }
  static void requireMain(){if(Looper.myLooper()!=Looper.getMainLooper()||Looper.getMainLooper().getThread()!=Thread.currentThread()||Process.myTid()!=Process.myPid())throw new IllegalStateException("Android process main thread required");}
  static JSONObject clocks(){return J.obj("elapsedRealtimeNs",SystemClock.elapsedRealtimeNanos(),"uptimeMs",SystemClock.uptimeMillis(),"nanoTimeNs",System.nanoTime());}
  void start()throws Exception{
    requireMain();if(active||started!=null||file.exists())throw new IllegalStateException("Never replace or replay a sampling capture");
    File directory=file.getParentFile();if(!directory.isDirectory()&&!directory.mkdirs()&&!directory.isDirectory())throw new java.io.IOException("Diagnostic directory unavailable");
    started=clocks();Debug.startMethodTracingSampling(file.getAbsolutePath(),BUFFER_BYTES,INTERVAL_US);active=true;
  }
  JSONObject stop(JSONObject verification)throws Exception{
    requireMain();boolean sameName=mainThreadName.equals(Thread.currentThread().getName());if(receipt!=null){if(!sameName)throw new IllegalStateException("Main thread name changed during sampling");return receipt;}
    if(started==null)throw new IllegalStateException("Sampling was never started");
    JSONObject stopping=clocks();
    if(active){try{Debug.stopMethodTracing();}finally{active=false;}}
    JSONObject stopped=clocks();
    if(!sameName)throw new IllegalStateException("Main thread name changed during sampling; profiler stopped");
    if(!file.isFile()||file.length()<=0||file.length()>MAX_FILE_BYTES)throw new java.io.IOException("Missing or oversized original trace");
    MessageDigest digest=MessageDigest.getInstance("SHA-256");long bytes=0;
    try(FileInputStream in=new FileInputStream(file)){byte[] block=new byte[65536];int count;while((count=in.read(block))!=-1){bytes+=count;if(bytes>MAX_FILE_BYTES)throw new java.io.IOException("Trace exceeded bound");digest.update(block,0,count);}}
    StringBuilder hash=new StringBuilder();for(byte part:digest.digest())hash.append(String.format(java.util.Locale.ROOT,"%02x",part&255));
    receipt=J.obj("schema",1,"diagnosticOnly",true,"performanceComparisonAllowed",false,"runNonce",nonce,
      "pid",pid,"mainTid",mainTid,"mainThreadName",mainThreadName,"bufferBytes",BUFFER_BYTES,"intervalUs",INTERVAL_US,
      "startRequested",started,"stopRequested",stopping,"stopped",stopped,
      "traceBytes",bytes,"traceSha256",hash.toString(),"traceUri","content://local.pocketchat.test.evidence/experience-sampling/"+nonce,
      "completedEightSaves",verification!=null,"verification",verification==null?JSONObject.NULL:verification,
      "scope","Extra post-benchmark ART sampling of the main process; nominal 1ms sampling, with profiler/scheduling/GC overhead retained. Not exact method durations, exact sample cadence, complete native stacks, or a performance comparison.");
    return receipt;
  }
}
