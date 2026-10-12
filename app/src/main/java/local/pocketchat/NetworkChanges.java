package local.pocketchat;

import android.content.*;
import org.json.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

/** Encrypted desired route; writing this record never changes a running route. */
final class NetworkChanges {
  static String hash(Context c){SharedPreferences p=c.getSharedPreferences("chat",0);return NativeNetwork.hash(new SecretStore(c).settings()+"|"+p.getString("networkMode","external")+"|"+p.getString("proxy","")+"|"+p.getBoolean("requireExternalVpn",true));}
  static JSONObject pending(Context c){try{byte[] value=new SecretStore(c).get("pending-network");return value==null?new JSONObject():J.parse(new String(value,StandardCharsets.UTF_8));}catch(Exception e){return new JSONObject();}}
  static String snapshotId(){String value=UUID.randomUUID().toString().replace("-","");StringBuilder encoded=new StringBuilder();for(char x:value.toCharArray())encoded.append("abcdefghijklmnop".charAt(Character.digit(x,16)));return encoded.toString();}
  static void save(Context c,String action,JSONObject config,String baseline)throws Exception{save(c,action,config,baseline,new JSONObject());}
  static void save(Context c,String action,JSONObject config,String baseline,JSONObject lineage)throws Exception{
    if("apply".equals(action)){NetworkSourceSelection.withSources(c,config,sources->{publish(c,action,config,baseline,sources,lineage);return null;});}
    else publish(c,action,config,baseline,null,lineage);
  }
  static void publish(Context c,String action,JSONObject config,String baseline,NetworkSourceSelection.Sources sources,JSONObject lineage)throws Exception{NetworkSourceSelection.withActiveSnapshot(c,()->{publishLocked(c,action,config,baseline,sources,lineage);return null;});}
  static void publishLocked(Context c,String action,JSONObject config,String baseline,NetworkSourceSelection.Sources sources,JSONObject lineage)throws Exception{
    SecretStore vault=new SecretStore(c);JSONObject before=pending(c),record=J.obj("action",action,"config",config,"baseline",baseline,"savedAt",System.currentTimeMillis());List<String> written=new ArrayList<>();boolean published=false;if(lineage!=null&&lineage.length()>0)NetworkCatalog.put(record,"baselineLineage",J.parse(lineage.toString()));
    try{
      if(sources!=null){String suffix=snapshotId(),entry="pending-entry-subscription-"+suffix;vault.put(entry,sources.entryBytes);written.add(entry);NetworkCatalog.put(record,"entrySnapshot",entry);NetworkCatalog.put(record,"entrySnapshotMeta",NetworkSourceSelection.metadata(sources.entry,sources.entryBytes));
        if(sources.exit!=null){String exit="pending-exit-subscription-"+suffix;vault.put(exit,sources.exitBytes);written.add(exit);NetworkCatalog.put(record,"exitSnapshot",exit);NetworkCatalog.put(record,"exitSnapshotMeta",NetworkSourceSelection.metadata(sources.exit,sources.exitBytes));}
      }
      vault.put("pending-network",record.toString().getBytes(StandardCharsets.UTF_8));published=true;deleteSnapshots(vault,before);
    }finally{if(!published)for(String slot:written)new android.util.AtomicFile(vault.file(slot)).delete();}
  }
  static boolean snapshotSlot(String slot){return slot.matches("pending-(entry|exit)-subscription-[a-p]{32}");}
  static void deleteSnapshots(SecretStore vault,JSONObject record){for(String key:new String[]{"entrySnapshot","exitSnapshot"}){String slot=record.optString(key);if(snapshotSlot(slot))new android.util.AtomicFile(vault.file(slot)).delete();}}
  static void clear(Context c){try{NetworkSourceSelection.withActiveSnapshot(c,()->{SecretStore vault=new SecretStore(c);JSONObject before=pending(c);new android.util.AtomicFile(vault.file("pending-network")).delete();deleteSnapshots(vault,before);return null;});}catch(Exception failure){throw new IllegalStateException("待应用网络设置未能取消",failure);}}
  /** A completed older apply must never clear a later saved candidate. */
  static boolean clearIfCurrent(Context c,String expected)throws Exception{return NetworkSourceSelection.withActiveSnapshot(c,()->{JSONObject current=pending(c);if(expected==null||expected.isEmpty()||current.length()==0||!expected.equals(current.toString()))return false;clear(c);return true;});}
  static JSONObject lineage(String transition,String writtenHash,String restoredHash,int generation){return J.obj("transition",transition,"writtenHash",writtenHash,"restoredHash",restoredHash,"generation",generation);}
  /** Rebase only a proven descendant of this exact, rolled-back unpublished transition. */
  static boolean rebase(Context c,JSONObject expected)throws Exception{return NetworkSourceSelection.withActiveSnapshot(c,()->{
    JSONObject current=pending(c),lineage=current.optJSONObject("baselineLineage");String written=expected.optString("writtenHash"),restored=expected.optString("restoredHash");
    if(lineage==null||expected.optString("transition").isEmpty()||written.isEmpty()||restored.isEmpty()||written.equals(restored)||!written.equals(current.optString("baseline"))||!restored.equals(hash(c))||!expected.optString("transition").equals(lineage.optString("transition"))||!written.equals(lineage.optString("writtenHash"))||!restored.equals(lineage.optString("restoredHash"))||expected.optInt("generation",-1)!=lineage.optInt("generation",-2))return false;
    NetworkCatalog.put(current,"baseline",restored);current.remove("baselineLineage");new SecretStore(c).put("pending-network",current.toString().getBytes(StandardCharsets.UTF_8));return true;
  });}
  static void validate(Context c,String action,JSONObject value)throws Exception{
    if("external".equals(action)){String proxy=value.optString("proxy");if(!proxy.isEmpty()&&!MainActivity.validProxy(proxy))throw new java.io.IOException("代理地址无效");return;}
    NetworkSourceSelection.resolve(new NetworkCatalog(c),value);
  }
}
