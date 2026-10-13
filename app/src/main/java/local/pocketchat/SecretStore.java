package local.pocketchat;
import android.content.Context;
import android.security.keystore.*;
import java.io.*;
import java.security.KeyStore;
import javax.crypto.*;
import javax.crypto.spec.GCMParameterSpec;
import java.nio.charset.StandardCharsets;
import org.json.*;

final class SecretStore {
  final Context context;
  SecretStore(Context c){context=c.getApplicationContext();}
  // Serialize containsAlias + generateKey across instances/processes. put() obtains
  // the key before publication; get() releases the payload lease before key().
  // Keeping key and payload leases separate avoids a key/stripe lock cycle.
  javax.crypto.SecretKey key()throws Exception{return SealedFileIo.lease(new File(context.getNoBackupFilesDir(),"network-keystore-key"),()->{KeyStore ks=KeyStore.getInstance("AndroidKeyStore");ks.load(null);String alias="pocket-network-v1"+(Profiles.slot(context)==0?"":"-env"+Profiles.slot(context));if(!ks.containsAlias(alias)){KeyGenerator g=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore");g.init(new KeyGenParameterSpec.Builder(alias,KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT).setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build());g.generateKey();}return (javax.crypto.SecretKey)ks.getKey(alias,null);});}
  File file(String slot){if(!slot.matches("[a-z-]+"))throw new IllegalArgumentException();return new File(context.getNoBackupFilesDir(),slot+".sealed");}
  void put(String slot,byte[] data)throws Exception{put(slot,data,null);}
  void put(String slot,byte[] data,SealedFileIo.BeforeCommit barrier)throws Exception{UiPerfStats.sealedWrite();Cipher c=Cipher.getInstance("AES/GCM/NoPadding");c.init(Cipher.ENCRYPT_MODE,key());c.updateAAD(slot.getBytes(StandardCharsets.UTF_8));byte[] encrypted=c.doFinal(data),iv=c.getIV(),prefix=new byte[iv.length+1];prefix[0]=(byte)iv.length;System.arraycopy(iv,0,prefix,1,iv.length);SealedFileIo.publish(file(slot),prefix,encrypted,barrier);}
  byte[] get(String slot)throws Exception{UiPerfStats.sealedRead();byte[] bytes=SealedFileIo.read(file(slot));if(bytes==null)return null;if(bytes.length<30)throw new IOException("保存的加密配置无效");int n=bytes[0]&255;if(n!=12||bytes.length<n+17)throw new IOException("保存的加密配置无效");Cipher c=Cipher.getInstance("AES/GCM/NoPadding");c.init(Cipher.DECRYPT_MODE,key(),new GCMParameterSpec(128,java.util.Arrays.copyOfRange(bytes,1,n+1)));c.updateAAD(slot.getBytes(StandardCharsets.UTF_8));return c.doFinal(bytes,n+1,bytes.length-n-1);}
  void remove(String slot)throws Exception{SealedFileIo.remove(file(slot));}
  JSONObject settings(){try{byte[] b=get("network");return b==null?new JSONObject():new JSONObject(new String(b,StandardCharsets.UTF_8));}catch(Exception e){return new JSONObject();}}
  void save(JSONObject o)throws Exception{put("network",o.toString().getBytes(StandardCharsets.UTF_8));}
  boolean hasBundledDefaults(){try(InputStream in=context.getAssets().open("personal-network.json")){return true;}catch(IOException e){return false;}}
  boolean importDefaults(InputStream in,boolean force)throws Exception{JSONObject existing=settings();if(!force&&existing.length()>0)return false;JSONObject o=new JSONObject(J.text(in,16*1024*1024));NativeNetwork.validate(o);String provider=o.optString("provider");if(!provider.isEmpty()){put("subscription",provider.getBytes(StandardCharsets.UTF_8));put("subscription-meta",J.obj("urlHash",NativeNetwork.hash(o.optString("subscriptionUrl"))).toString().getBytes(StandardCharsets.UTF_8));o.remove("provider");}save(o);context.getSharedPreferences("chat",0).edit().putString("networkMode","internal").putBoolean("networkConfigured",true).putBoolean("personalDefaultsInstalled",true).commit();return true;}
  boolean restoreBundledDefaults()throws Exception{try(InputStream in=context.getAssets().open("personal-network.json")){return importDefaults(in,true);}}
  void ensureBundledDefaults()throws Exception{android.content.SharedPreferences p=context.getSharedPreferences("chat",0);if(settings().length()>0||(p.getBoolean("networkConfigured",false)&&"external".equals(p.getString("networkMode","external")))||!hasBundledDefaults())return;try(InputStream in=context.getAssets().open("personal-network.json")){importDefaults(in,false);}}
  void importPrivateProvision()throws Exception{File f=new File(context.getFilesDir(),"network-import.json");if(!f.exists()){ensureBundledDefaults();return;}try(FileInputStream in=new FileInputStream(f)){importDefaults(in,true);}finally{if(!f.delete())f.deleteOnExit();}}
}
