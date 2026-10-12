package local.pocketchat;
import android.content.Context;import java.io.*;import java.nio.file.*;import java.nio.charset.StandardCharsets;import org.json.*;
/** Host fixture uses atomic plain files, not Android encryption or its keystore. */
final class SecretStore {
  final Context c;static boolean failCatalogOnce;
  SecretStore(Context c){this.c=c;}
  File file(String name){if(!name.matches("[a-z-]+"))throw new IllegalArgumentException(name);return new File(c.getNoBackupFilesDir(),name+".sealed");}
  byte[] get(String name)throws Exception{Path p=file(name).toPath();return Files.exists(p)?Files.readAllBytes(p):null;}
  void put(String name,byte[] data)throws Exception{if(failCatalogOnce&&"network-catalog".equals(name)){failCatalogOnce=false;throw new IOException("Synthetic catalogue publication failure");}Path target=file(name).toPath(),temporary=Files.createTempFile(target.getParent(),"write-",".tmp");try{Files.write(temporary,data);Files.move(temporary,target,StandardCopyOption.REPLACE_EXISTING,StandardCopyOption.ATOMIC_MOVE);}finally{Files.deleteIfExists(temporary);}}
  JSONObject settings(){try{byte[] bytes=get("network");return bytes==null?new JSONObject():new JSONObject(new String(bytes,StandardCharsets.UTF_8));}catch(Exception ignored){return new JSONObject();}}
  void save(JSONObject value)throws Exception{put("network",value.toString().getBytes(StandardCharsets.UTF_8));}
}
