package local.pocketchat;

import android.content.*;
import org.json.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

/** Encrypted desired route; writing this record never changes a running route. */
final class NetworkChanges {
  static String hash(Context c){SharedPreferences p=c.getSharedPreferences("chat",0);return NativeNetwork.hash(new SecretStore(c).settings()+"|"+p.getString("networkMode","external")+"|"+p.getString("proxy","")+"|"+p.getBoolean("requireExternalVpn",true));}
  static JSONObject pending(Context c){try{byte[] value=new SecretStore(c).get("pending-network");return value==null?new JSONObject():J.parse(new String(value,StandardCharsets.UTF_8));}catch(Exception e){return new JSONObject();}}
  /** Transaction code must distinguish an absent intent from unreadable data. */
  static JSONObject pendingStrict(Context c)throws Exception{
    byte[] value=new SecretStore(c).get("pending-network");if(value==null)return new JSONObject();
    if(value.length==0||value.length>16*1024*1024)throw new java.io.IOException("待应用网络设置无法读取，原文件已保留");
    String text=StandardCharsets.UTF_8.newDecoder().onMalformedInput(java.nio.charset.CodingErrorAction.REPORT).onUnmappableCharacter(java.nio.charset.CodingErrorAction.REPORT).decode(java.nio.ByteBuffer.wrap(value)).toString();
    JSONTokener parser=new JSONTokener(text);Object parsed=parser.nextValue();if(!(parsed instanceof JSONObject)||parser.nextClean()!=0)throw new java.io.IOException("待应用网络设置无法读取，原文件已保留");return (JSONObject)parsed;
  }
  interface IntentGuard{void verify()throws Exception;}
  static final class IntentReceipt {
    final String staged;final JSONObject previous;String ready="";
    IntentReceipt(JSONObject record){staged=record.toString();previous=J.parse(record.optJSONObject("previousPending").toString());}
    boolean matches(JSONObject current){String value=current.toString();return staged.equals(value)||!ready.isEmpty()&&ready.equals(value);}
  }
  static JSONObject intent(JSONObject record)throws java.io.IOException{
    if(!record.has("environmentIntent"))return null;JSONObject value=record.optJSONObject("environmentIntent");
    if(value==null||!Integer.valueOf(1).equals(value.opt("schema"))||!value.optString("id").matches("[0-9a-f]{32}")||value.optJSONObject("identity")==null||!("staged".equals(value.optString("state"))||"ready".equals(value.optString("state"))))throw new java.io.IOException("网络意图版本无效，原文件已保留");
    JSONObject identity=value.optJSONObject("identity");if(!NetworkCatalog.integer(identity.opt("slot"))||identity.optInt("slot",-1)<0||identity.optLong("slot",8)>=8||!NetworkCatalog.integer(identity.opt("generation"))||identity.optLong("generation",-1)<0||identity.optLong("generation")>Integer.MAX_VALUE||!(identity.opt("environmentId") instanceof String)||!identity.optString("environmentId").matches("[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"))throw new java.io.IOException("网络意图身份无效，原文件已保留");return value;
  }
  static boolean identityMatches(JSONObject record,JSONObject identity)throws java.io.IOException{
    JSONObject marker=intent(record);if(marker==null)return true;JSONObject saved=marker.optJSONObject("identity");return saved.optInt("slot",-1)==identity.optInt("slot",-2)&&saved.optInt("generation",-1)==identity.optInt("generation",-2)&&saved.optString("environmentId").equals(identity.optString("environmentId"));
  }
  /** Staging keeps the prior intent and its private snapshots until promotion.
   * A crash therefore never turns an unacknowledged model write into an apply. */
  static IntentReceipt stageIntent(Context c,String action,JSONObject config,String baseline,JSONObject lineage,JSONObject identity,IntentGuard guard)throws Exception{
    if("apply".equals(action))return NetworkSourceSelection.withSources(c,config,sources->stageIntent(c,action,config,baseline,lineage,identity,guard,sources));
    return stageIntent(c,action,config,baseline,lineage,identity,guard,null);
  }
  private static IntentReceipt stageIntent(Context c,String action,JSONObject config,String baseline,JSONObject lineage,JSONObject identity,IntentGuard guard,NetworkSourceSelection.Sources sources)throws Exception{
    return NetworkSourceSelection.withActiveSnapshot(c,()->{
      guard.verify();JSONObject before=pendingStrict(c);JSONObject oldMarker=intent(before);if(oldMarker!=null&&"staged".equals(oldMarker.optString("state")))throw new java.io.IOException("上次网络保存尚未恢复");
      JSONObject record=J.obj("action",action,"config",config,"baseline",baseline,"applicationPolicy","unselected","savedAt",System.currentTimeMillis(),"previousPending",before,"environmentIntent",J.obj("schema",1,"id",UUID.randomUUID().toString().replace("-",""),"identity",J.parse(identity.toString()),"state","staged"));
      if(lineage!=null&&lineage.length()>0)NetworkCatalog.put(record,"baselineLineage",J.parse(lineage.toString()));SecretStore vault=new SecretStore(c);List<String> written=new ArrayList<>();IntentReceipt receipt=null;
      try{
        if(sources!=null){String suffix=snapshotId(),entry="pending-entry-subscription-"+suffix;vault.put(entry,sources.entryBytes);written.add(entry);NetworkCatalog.put(record,"entrySnapshot",entry);NetworkCatalog.put(record,"entrySnapshotMeta",NetworkSourceSelection.metadata(sources.entry,sources.entryBytes));if(sources.exit!=null){String exit="pending-exit-subscription-"+suffix;vault.put(exit,sources.exitBytes);written.add(exit);NetworkCatalog.put(record,"exitSnapshot",exit);NetworkCatalog.put(record,"exitSnapshotMeta",NetworkSourceSelection.metadata(sources.exit,sources.exitBytes));}}
        guard.verify();receipt=new IntentReceipt(record);byte[] encoded=receipt.staged.getBytes(StandardCharsets.UTF_8);if(encoded.length>16*1024*1024)throw new java.io.IOException("网络候选和恢复记录过大，旧设置已保留");vault.put("pending-network",encoded);return receipt;
      }catch(Exception failure){
        // Publication may have completed before an AtomicFile error was reported.
        // Only this exact receipt is withdrawn, even in that case.
        if(receipt!=null)try{rollbackIntent(c,receipt,guard);}catch(Exception rollback){failure.addSuppressed(rollback);}
        for(String slot:written)try{if(receipt==null||!receipt.matches(pendingStrict(c)))vault.remove(slot);}catch(Exception cleanup){failure.addSuppressed(cleanup);}throw failure;
      }
    });
  }
  static String promoteIntent(Context c,IntentReceipt receipt,IntentGuard guard)throws Exception{return NetworkSourceSelection.withActiveSnapshot(c,()->{
    guard.verify();JSONObject current=pendingStrict(c);if(!receipt.staged.equals(current.toString()))throw new java.io.IOException("网络设置已由较新的候选替换");JSONObject marker=intent(current);marker.put("state","ready");current.remove("previousPending");receipt.ready=current.toString();new SecretStore(c).put("pending-network",receipt.ready.getBytes(StandardCharsets.UTF_8));guard.verify();
    // Cleanup cannot turn a successfully committed intent into a reported failure.
    try{deleteSnapshots(new SecretStore(c),receipt.previous);}catch(Exception ignored){}return receipt.ready;
  });}
  static boolean readyReceipt(Context c,IntentReceipt receipt,IntentGuard guard)throws Exception{return NetworkSourceSelection.withActiveSnapshot(c,()->{guard.verify();return !receipt.ready.isEmpty()&&receipt.ready.equals(pendingStrict(c).toString());});}
  /** Use only after verifying the corresponding model outside all source/active
   * leases. A durable ready commit can succeed even if its write lost the ack. */
  static String confirmIntent(Context c,IntentReceipt receipt,IntentGuard guard)throws Exception{return NetworkSourceSelection.withActiveSnapshot(c,()->{guard.verify();if(receipt.ready.isEmpty()||!receipt.ready.equals(pendingStrict(c).toString()))throw new java.io.IOException("网络候选已变化，旧保存结果未确认");try{deleteSnapshots(new SecretStore(c),receipt.previous);}catch(Exception ignored){}return receipt.ready;});}
  static boolean rollbackIntent(Context c,IntentReceipt receipt,IntentGuard guard)throws Exception{return NetworkSourceSelection.withActiveSnapshot(c,()->{
    guard.verify();JSONObject current=pendingStrict(c);if(!receipt.matches(current))return false;restoreIntent(c,current,receipt.previous);return true;
  });}
  static void restoreIntent(Context c,JSONObject staged,JSONObject previous)throws Exception{
    SecretStore vault=new SecretStore(c);if(previous.length()==0)vault.remove("pending-network");else vault.put("pending-network",previous.toString().getBytes(StandardCharsets.UTF_8));try{deleteSnapshots(vault,staged);}catch(Exception ignored){}
  }
  /** Caller owns the per-profile intent lease, so a live stage cannot be mistaken
   * for an interrupted save. Legacy v24 intents remain committed candidates. */
  static void recoverIntent(Context c,JSONObject identity,IntentGuard guard)throws Exception{NetworkSourceSelection.withActiveSnapshot(c,()->{
    guard.verify();JSONObject current=pendingStrict(c),marker=intent(current);if(marker==null)return null;
    if(!identityMatches(current,identity)){restoreIntent(c,current,new JSONObject());JSONObject previous=current.optJSONObject("previousPending");if(previous!=null)try{deleteSnapshots(new SecretStore(c),previous);}catch(Exception ignored){}return null;}
    if("staged".equals(marker.optString("state"))){JSONObject previous=current.optJSONObject("previousPending");if(previous==null||intent(previous)!=null&&"staged".equals(intent(previous).optString("state")))throw new java.io.IOException("网络意图恢复记录无效，原文件已保留");if(!identityMatches(previous,identity))previous=new JSONObject();restoreIntent(c,current,previous);}return null;
  });}
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
    }finally{if(!published)for(String slot:written)vault.remove(slot);}
  }
  static boolean snapshotSlot(String slot){return slot.matches("pending-(entry|exit)-subscription-[a-p]{32}");}
  static void deleteSnapshots(SecretStore vault,JSONObject record)throws Exception{for(String key:new String[]{"entrySnapshot","exitSnapshot"}){String slot=record.optString(key);if(snapshotSlot(slot))vault.remove(slot);}}
  static void clear(Context c){try{NetworkSourceSelection.withActiveSnapshot(c,()->{SecretStore vault=new SecretStore(c);JSONObject before=pending(c);vault.remove("pending-network");deleteSnapshots(vault,before);return null;});}catch(Exception failure){throw new IllegalStateException("待应用网络设置未能取消",failure);}}
  /** A completed older apply must never clear a later saved candidate. */
  static boolean clearIfCurrent(Context c,String expected)throws Exception{return NetworkSourceSelection.withActiveSnapshot(c,()->{JSONObject current=pendingStrict(c);if(expected==null||expected.isEmpty()||current.length()==0||!expected.equals(current.toString()))return false;clear(c);return true;});}
  static JSONObject lineage(String transition,String writtenHash,String restoredHash,int generation){return J.obj("transition",transition,"writtenHash",writtenHash,"restoredHash",restoredHash,"generation",generation);}
  /** Rebase only a proven descendant of this exact, rolled-back unpublished transition. */
  static boolean rebase(Context c,JSONObject expected)throws Exception{return NetworkSourceSelection.withActiveSnapshot(c,()->{
    JSONObject current=pending(c),lineage=current.optJSONObject("baselineLineage");String written=expected.optString("writtenHash"),restored=expected.optString("restoredHash");
    if(lineage==null||expected.optString("transition").isEmpty()||written.isEmpty()||restored.isEmpty()||written.equals(restored)||!written.equals(current.optString("baseline"))||!restored.equals(hash(c))||!expected.optString("transition").equals(lineage.optString("transition"))||!written.equals(lineage.optString("writtenHash"))||!restored.equals(lineage.optString("restoredHash"))||expected.optInt("generation",-1)!=lineage.optInt("generation",-2))return false;
    NetworkCatalog.put(current,"baseline",restored);current.remove("baselineLineage");new SecretStore(c).put("pending-network",current.toString().getBytes(StandardCharsets.UTF_8));return true;
  });}
  /** Read-only validation of a saved candidate and its encrypted source bytes. */
  static void validateSaved(Context context,JSONObject saved)throws Exception{
    JSONObject original=saved.getJSONObject("config"),detached=J.parse(original.toString());String action=saved.optString("action");
    if("external".equals(action)){validate(context,action,detached);return;}
    if(!"apply".equals(action))throw new java.io.IOException("网络候选操作无效");
    withSavedSources(context,saved,sources->null);
  }
  static <T>T withSavedSources(Context context,JSONObject saved,NetworkSourceSelection.SourceAction<T> action)throws Exception{
    JSONObject original=saved.getJSONObject("config"),detached=J.parse(original.toString());
    return NetworkSourceSelection.withSources(context,detached,sources->{
      if(!original.toString().equals(detached.toString()))throw new java.io.IOException("所选来源已变化，请重新编辑待应用设置");
      savedSource(context,saved,"entry",sources.entryBytes);
      if(sources.exitBytes!=null)savedSource(context,saved,"exit",sources.exitBytes);
      return action.run(sources);
    });
  }
  private static void savedSource(Context context,JSONObject saved,String role,byte[] actual)throws Exception{
    String slot=saved.optString(role+"Snapshot");JSONObject metadata=saved.optJSONObject(role+"SnapshotMeta");
    if(!snapshotSlot(slot)||metadata==null||!NetworkSourceSelection.payloadHash(actual).equals(metadata.optString("payloadHash")))throw new java.io.IOException("所选订阅版本已变化，请重新编辑待应用设置");
    byte[] retained=new SecretStore(context).get(slot);
    if(retained==null||!Arrays.equals(retained,actual))throw new java.io.IOException("待应用订阅快照无法确认，原设置已保留");
  }
  static void validate(Context c,String action,JSONObject value)throws Exception{
    if("external".equals(action)){String proxy=value.optString("proxy");if(!proxy.isEmpty()&&!MainActivity.validProxy(proxy))throw new java.io.IOException("代理地址无效");return;}
    NetworkSourceSelection.resolve(new NetworkCatalog(c),value);
  }
}
