package local.pocketchat;
import android.content.Context;import java.io.*;import java.nio.file.*;import java.nio.charset.StandardCharsets;import org.json.*;
/** Atomic plain host bytes with explicit pre/post publication I/O faults. */
final class SecretStore {
  static final java.util.concurrent.atomic.AtomicLong putCalls=new java.util.concurrent.atomic.AtomicLong(),removeCalls=new java.util.concurrent.atomic.AtomicLong();
  static volatile Runnable beforePendingRead;
  final Context c,context;static String failSlotOnce="";static boolean failReadyAfterWrite,failRollbackOnce;static int failReadsAfterReady,readFailures,readyWriteFailures,rollbackFailures;static String failedReady="";
  SecretStore(Context c){this.c=c;context=c;}
  File file(String name){if(!name.matches("[a-z-]+"))throw new IllegalArgumentException(name);return new File(c.getNoBackupFilesDir(),name+".sealed");}
  byte[] get(String name)throws Exception{if("pending-network".equals(name)){Runnable hook=beforePendingRead;if(hook!=null){beforePendingRead=null;hook.run();}}if("pending-network".equals(name)&&!failedReady.isEmpty()&&failReadsAfterReady>0){failReadsAfterReady--;readFailures++;throw new IOException("Synthetic unreadable outcome");}Path p=file(name).toPath();return Files.exists(p)?Files.readAllBytes(p):null;}
  void put(String name,byte[] data)throws Exception{
    putCalls.incrementAndGet();
    if(name.equals(failSlotOnce)){failSlotOnce="";throw new IOException("Synthetic prepublication I/O failure");}
    String text=new String(data,StandardCharsets.UTF_8);if("pending-network".equals(name)&&failRollbackOnce&&!failedReady.isEmpty()&&!failedReady.equals(text)){failRollbackOnce=false;rollbackFailures++;throw new IOException("Synthetic predecessor withdrawal failure");}
    Path target=file(name).toPath(),temporary=Files.createTempFile(target.getParent(),"write-",".tmp");try{Files.write(temporary,data);Files.move(temporary,target,StandardCopyOption.REPLACE_EXISTING,StandardCopyOption.ATOMIC_MOVE);}finally{Files.deleteIfExists(temporary);}
    if("pending-network".equals(name)&&failReadyAfterWrite){JSONObject marker=J.parse(text).optJSONObject("environmentIntent");if(marker!=null&&"ready".equals(marker.optString("state"))){failReadyAfterWrite=false;failedReady=text;readyWriteFailures++;throw new IOException("Synthetic ready commit lost write acknowledgement");}}
  }
  JSONObject settings(){try{byte[] data=get("network");return data==null?new JSONObject():new JSONObject(new String(data,StandardCharsets.UTF_8));}catch(Exception ignored){return new JSONObject();}}
  void save(JSONObject value)throws Exception{put("network",value.toString().getBytes(StandardCharsets.UTF_8));}
  void remove(String name)throws Exception{removeCalls.incrementAndGet();if("pending-network".equals(name)&&failRollbackOnce&&!failedReady.isEmpty()){failRollbackOnce=false;rollbackFailures++;throw new IOException("Synthetic predecessor withdrawal failure");}Files.deleteIfExists(file(name).toPath());}
  static void resetOutcomeFaults(){failReadyAfterWrite=false;failRollbackOnce=false;failReadsAfterReady=0;failedReady="";readFailures=0;readyWriteFailures=0;rollbackFailures=0;}
}
