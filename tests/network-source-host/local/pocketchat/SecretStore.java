package local.pocketchat;
import android.content.Context;import java.io.*;import java.nio.file.*;import java.nio.charset.StandardCharsets;import org.json.*;
/** Host fixture uses atomic plain files, not Android encryption or its keystore. */
final class SecretStore {
  final Context c,context;static boolean failCatalogOnce;static String failSlotOnce="",pauseSlot="";static int reads;
  SecretStore(Context c){this.c=c;this.context=c;}
  File file(String name){if(!name.matches("[a-z-]+"))throw new IllegalArgumentException(name);return new File(c.getNoBackupFilesDir(),name+".sealed");}
  byte[] get(String name)throws Exception{reads++;Path p=file(name).toPath();return Files.exists(p)?Files.readAllBytes(p):null;}
  void put(String name,byte[] data)throws Exception{if(name.equals(failSlotOnce)){failSlotOnce="";throw new IOException("Synthetic snapshot write failure");}if(failCatalogOnce&&"network-catalog".equals(name)){failCatalogOnce=false;throw new IOException("Synthetic catalogue publication failure");}Path target=file(name).toPath(),temporary=Files.createTempFile(target.getParent(),"write-",".tmp");try{Files.write(temporary,data);Files.move(temporary,target,StandardCopyOption.REPLACE_EXISTING,StandardCopyOption.ATOMIC_MOVE);}finally{Files.deleteIfExists(temporary);}if(name.equals(pauseSlot)){pauseSlot="";Files.writeString(c.root.toPath().resolve("snapshot-writer-paused"),"paused");long deadline=System.nanoTime()+30_000_000_000L;while(!Files.exists(c.root.toPath().resolve("snapshot-writer-resume"))){if(System.nanoTime()>deadline)throw new IOException("Snapshot fixture release timed out");Thread.sleep(5);}}}
  JSONObject settings(){try{byte[] bytes=get("network");return bytes==null?new JSONObject():new JSONObject(new String(bytes,StandardCharsets.UTF_8));}catch(Exception ignored){return new JSONObject();}}
  void save(JSONObject value)throws Exception{put("network",value.toString().getBytes(StandardCharsets.UTF_8));}
  void remove(String slot)throws Exception{Files.deleteIfExists(file(slot).toPath());}
}
