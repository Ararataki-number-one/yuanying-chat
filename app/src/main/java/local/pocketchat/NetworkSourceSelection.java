package local.pocketchat;

import org.json.*;
import java.io.IOException;
import java.util.*;

/** Stable source and node identities; display names are never node credentials. */
final class NetworkSourceSelection {
  static List<String> keys(JSONArray values){LinkedHashSet<String> out=new LinkedHashSet<>();if(values!=null)for(int i=0;i<values.length();i++){String key=values.optString(i);if(!key.isEmpty())out.add(key);}return new ArrayList<>(out);}
  private static final Map<JSONObject,NodeIndex> indexes=Collections.synchronizedMap(new WeakHashMap<>());
  private static final class NodeIndex {
    final JSONArray nodes,details;final long revision;final List<String> names=new ArrayList<>();final Map<String,JSONObject> byName=new LinkedHashMap<>();final Map<String,List<JSONObject>> byKey=new LinkedHashMap<>();
    NodeIndex(JSONObject source){nodes=source.optJSONArray("nodes");details=source.optJSONArray("nodeDetails");revision=source.optLong("revision");String prefix=NetworkCatalog.EXIT.equals(source.optString("role"))?"Exit|":"Entry|";Set<String> allowed=new LinkedHashSet<>();if(nodes!=null)for(int i=0;i<nodes.length();i++){String name=nodes.optString(i);if(name.startsWith(prefix))allowed.add(name);}names.addAll(allowed);if(details!=null)for(int i=0;i<details.length();i++){JSONObject node=details.optJSONObject(i);if(node==null||!allowed.contains(node.optString("name")))continue;byName.put(node.optString("name"),node);String key=node.optString("configFingerprint");if(!key.isEmpty())byKey.computeIfAbsent(key,x->new ArrayList<>()).add(node);}}
    boolean matches(JSONObject source){return nodes==source.optJSONArray("nodes")&&details==source.optJSONArray("nodeDetails")&&revision==source.optLong("revision");}
  }
  private static NodeIndex index(JSONObject source){if(source==null)return null;synchronized(indexes){NodeIndex value=indexes.get(source);if(value==null||!value.matches(source)){value=new NodeIndex(source);indexes.put(source,value);}return value;}}
  static JSONObject byName(JSONObject source,String name){NodeIndex index=index(source);return index==null?null:index.byName.get(name);}
  static JSONObject node(JSONObject source,String key){return node(source,key,"");}
  static JSONObject node(JSONObject source,String key,String preferredName){NodeIndex index=index(source);if(index==null||key.isEmpty())return null;JSONObject preferred=index.byName.get(preferredName);if(preferred!=null&&key.equals(preferred.optString("configFingerprint")))return preferred;List<JSONObject> matches=index.byKey.get(key);return matches!=null&&matches.size()==1?matches.get(0):null;}
  static boolean ambiguous(JSONObject source,String key){NodeIndex index=index(source);List<JSONObject> matches=index==null?null:index.byKey.get(key);return matches!=null&&matches.size()>1;}
  static boolean socks5(JSONObject node){return node!=null&&"socks5".equalsIgnoreCase(node.optString("type"));}
  static String fingerprint(JSONObject source,String name){JSONObject node=byName(source,name);return node==null?"":node.optString("configFingerprint");}
  static List<String> names(JSONObject source){NodeIndex index=index(source);return index==null?new ArrayList<>():new ArrayList<>(index.names);}
  static JSONObject source(NetworkCatalog catalog,String role,JSONObject config)throws IOException{
    boolean entry=NetworkCatalog.ENTRY.equals(role);String prefix=entry?"entry":"exit",id=config.optString(prefix+"SubscriptionId"),url=config.optString(entry?"subscriptionUrl":"exitSubscriptionUrl");
    JSONObject row=catalog.subscription(role,id.isEmpty()?NativeNetwork.hash(url):id);
    if(row==null)throw new IOException((entry?"入口":"出口")+"订阅已删除，请重新选择");
    if(!url.equals(row.optString("url"))||config.has(prefix+"SubscriptionAddressRevision")&&config.optLong(prefix+"SubscriptionAddressRevision")!=row.optLong("addressRevision"))throw new IOException((entry?"入口":"出口")+"订阅地址已变化，请重新选择");
    // UI candidate validation reads the already-loaded catalogue only. Payload
    // existence and decryption belong to resolve(), on the background worker.
    if(row.optBoolean("stale")||row.optLong("cacheAddressRevision")!=row.optLong("addressRevision"))throw new IOException("请先更新所选"+(entry?"入口":"出口")+"订阅，再保存");return row;
  }
  static void sourceMetadata(JSONObject config,String role,JSONObject row){boolean entry=NetworkCatalog.ENTRY.equals(role);String prefix=entry?"entry":"exit";NetworkCatalog.put(config,prefix+"SubscriptionId",row.optString("id"));NetworkCatalog.put(config,prefix+"SubscriptionAddressRevision",row.optLong("addressRevision"));NetworkCatalog.put(config,entry?"subscriptionUrl":"exitSubscriptionUrl",row.optString("url"));NetworkCatalog.put(config,entry?"subscriptionName":"exitSubscriptionName",row.optString("name"));}
  /** Refresh a saved reference by identity. A renamed node is retained; a replacement with the same name is not. */
  static void normalizeEntries(JSONObject config,JSONObject row)throws IOException{normalizeEntries(config,row,true);}
  static void normalizeEntries(JSONObject config,JSONObject row,boolean validate)throws IOException{
    List<String> names=names(row);String mode=config.optString("entryMode"),chosen=config.optString("entry"),key=config.optString("entryNodeKey");
    if(!key.isEmpty()){JSONObject current=node(row,key,chosen);if(current==null){if(ambiguous(row,key))throw new IOException("入口别名已变化，请重新选择入口");chosen="";key="";}else chosen=current.optString("name");}
    else if(!chosen.isEmpty()&&!config.has("entryNodeKey")){key=fingerprint(row,chosen);}
    else if(!chosen.isEmpty())throw new IOException("当前入口缺少有效身份，请重新选择");
    LinkedHashSet<String> retained=new LinkedHashSet<>(),retainedKeys=new LinkedHashSet<>();JSONObject retainedRefs=new JSONObject();
    if(config.has("entryPoolKeys")){
      Set<String> allowed=new LinkedHashSet<>(keys(config.optJSONArray("entryPoolKeys")));JSONObject refs=config.optJSONObject("entryPoolNodeKeys");
      if(refs!=null){for(String name:EntrySelection.strings(config.optJSONArray("entryPool"))){String identity=refs.optString(name);if(identity.isEmpty()||!allowed.contains(identity))throw new IOException("入口池身份不完整，请重新选择入口");JSONObject current=node(row,identity,name);if(current==null){if(ambiguous(row,identity))throw new IOException("入口池别名已变化，请重新选择入口");continue;}String currentName=current.optString("name");if(!retained.contains(currentName))retained.add(currentName);if(!retainedKeys.contains(identity))retainedKeys.add(identity);NetworkCatalog.put(retainedRefs,currentName,identity);}}
      else{for(String identity:allowed){boolean exact=false;for(String previous:EntrySelection.strings(config.optJSONArray("entryPool"))){JSONObject current=byName(row,previous);if(current!=null&&identity.equals(current.optString("configFingerprint"))){if(!retained.contains(previous))retained.add(previous);NetworkCatalog.put(retainedRefs,previous,identity);exact=true;}}if(!exact){JSONObject current=node(row,identity);if(current==null){if(ambiguous(row,identity))throw new IOException("入口池别名已变化，请重新选择入口");continue;}String currentName=current.optString("name");if(!retained.contains(currentName))retained.add(currentName);NetworkCatalog.put(retainedRefs,currentName,identity);}if(!retainedKeys.contains(identity))retainedKeys.add(identity);}}
      NetworkCatalog.put(config,"entryPool",new JSONArray(retained));NetworkCatalog.put(config,"entryPoolKeys",new JSONArray(retainedKeys));NetworkCatalog.put(config,"entryPoolNodeKeys",retainedRefs);
    }else{
      retained=new LinkedHashSet<>(EntrySelection.strings(config.optJSONArray("entryPool")));retained.retainAll(new HashSet<>(names));NetworkCatalog.put(config,"entryPool",new JSONArray(retained));boolean complete=!retained.isEmpty();for(String name:retained){String identity=fingerprint(row,name);if(identity.isEmpty())complete=false;else{if(!retainedKeys.contains(identity))retainedKeys.add(identity);NetworkCatalog.put(retainedRefs,name,identity);}}if(complete){NetworkCatalog.put(config,"entryPoolKeys",new JSONArray(retainedKeys));NetworkCatalog.put(config,"entryPoolNodeKeys",retainedRefs);}
    }
    if(NetworkOptimizationPolicy.pooled(mode)&&!EntrySelection.strings(config.optJSONArray("entryPool")).contains(chosen)){chosen="";key="";}
    NetworkCatalog.put(config,"entry",chosen);if(!key.isEmpty()||config.has("entryNodeKey"))NetworkCatalog.put(config,"entryNodeKey",key);if(validate)EntrySelection.validate(config,names);
  }
  static final class Sources {
    final JSONObject entry,exit;final byte[] entryBytes,exitBytes;
    Sources(JSONObject entry,JSONObject exit,byte[] entryBytes,byte[] exitBytes){this.entry=entry;this.exit=exit;this.entryBytes=entryBytes;this.exitBytes=exitBytes;}
  }
  static final class References {
    final JSONObject entry,exit;
    References(JSONObject entry,JSONObject exit){this.entry=entry;this.exit=exit;}
  }
  /** Pure reference validation: no cache lookup, SecretStore read, or payload decryption. */
  static References validateRefs(NetworkCatalog catalog,JSONObject config)throws Exception{
    if(!catalog.readError().isEmpty())throw new IOException(catalog.readError());
    JSONObject entry=source(catalog,NetworkCatalog.ENTRY,config);normalizeEntries(config,entry);sourceMetadata(config,NetworkCatalog.ENTRY,entry);
    // Legacy names acquire identities only after the real cached provider has
    // been previewed. Preserve the old mode and permitted pool during upgrade.
    List<String> required=config.optString("entryMode").isEmpty()?names(entry):"manual".equals(config.optString("entryMode"))?Collections.singletonList(config.optString("entry")):EntrySelection.strings(config.optJSONArray("entryPool"));
    for(String name:required)if(fingerprint(entry,name).isEmpty())throw new IOException("请先读取入口订阅的节点，再保存；原连接继续使用");
    JSONObject exit=null;
    if("subscription".equals(config.optString("exitSource"))){exit=source(catalog,NetworkCatalog.EXIT,config);String key=config.optString("exitNodeKey");JSONObject selected=node(exit,key,config.optString("exitNodeName"));if(key.isEmpty()||!socks5(selected))throw new IOException("固定出口已变化或不支持，请重新选择 SOCKS5 出口");NetworkCatalog.put(config,"exitNodeName",selected.optString("name"));NetworkCatalog.put(config,"exitName",selected.optString("name"));sourceMetadata(config,NetworkCatalog.EXIT,exit);}
    else{
      String id=config.optString("exitLibraryId",NetworkCatalog.exitId(config));JSONObject manual=catalog.exit(id);if(manual==null)throw new IOException("固定出口已删除，请重新选择");
      if(!manual.optString("host").equals(config.optString("exitHost"))||manual.optInt("port")!=config.optInt("exitPort")||!manual.optString("user").equals(config.optString("exitUser"))||!manual.optString("password").equals(config.optString("exitPassword")))throw new IOException("固定出口已编辑，请重新选择");
      NetworkCatalog.put(config,"exitSource","manual");NetworkCatalog.put(config,"exitLibraryId",manual.optString("id"));NetworkCatalog.put(config,"exitName",manual.optString("name"));NetworkCatalog.put(config,"exitRegion",manual.optString("region"));
    }
    NativeNetwork.validate(config);return new References(entry,exit);
  }
  /** Worker-only payload resolution; metadata alone never admits a missing provider. */
  static Sources resolve(NetworkCatalog catalog,JSONObject config)throws Exception{
    References refs=validateRefs(catalog,config);byte[] entryBytes=catalog.cache(refs.entry),exitBytes=refs.exit==null?null:catalog.cache(refs.exit);
    if(entryBytes==null||entryBytes.length==0||refs.exit!=null&&(exitBytes==null||exitBytes.length==0))throw new IOException("所选订阅缓存不可用，请更新后重试");return new Sources(refs.entry,refs.exit,entryBytes,exitBytes);
  }
  static String payloadHash(byte[] bytes){try{byte[] hash=java.security.MessageDigest.getInstance("SHA-256").digest(bytes);StringBuilder value=new StringBuilder();for(byte b:hash)value.append(String.format(java.util.Locale.ROOT,"%02x",b&255));return value.toString();}catch(java.security.NoSuchAlgorithmException impossible){throw new IllegalStateException(impossible);}}
  interface SourceAction<T>{T run(Sources sources)throws Exception;}
  interface SnapshotAction<T>{T run()throws Exception;}
  private static final Map<String,java.util.concurrent.locks.ReentrantLock> snapshotLocks=new java.util.concurrent.ConcurrentHashMap<>();
  /** Eight private profile directories have independent, reentrant local leases. */
  static <T>T withActiveSnapshot(android.content.Context context,SnapshotAction<T> action)throws Exception{
    java.io.File directory=context.getNoBackupFilesDir();String identity=directory.getCanonicalPath();java.util.concurrent.locks.ReentrantLock local=snapshotLocks.computeIfAbsent(identity,x->new java.util.concurrent.locks.ReentrantLock());local.lockInterruptibly();
    try{
      // Provider transactions may surround write + preferences + rollback with
      // one outer lease. FileChannel locks themselves are not reentrant.
      if(local.getHoldCount()>1)return action.run();
      try(java.io.RandomAccessFile handle=new java.io.RandomAccessFile(new java.io.File(directory,"network-snapshot.lock"),"rw");java.nio.channels.FileLock lease=handle.getChannel().lock()){return action.run();}
    }finally{local.unlock();}
  }
  /** Keep source publication and profile snapshot publication in one short lease. */
  static <T>T withSources(android.content.Context context,JSONObject candidate,SourceAction<T> action)throws Exception{
    synchronized(NetworkCatalog.lock){try(java.io.RandomAccessFile handle=new java.io.RandomAccessFile(NetworkCatalog.lockFile(context),"rw");java.nio.channels.FileLock lease=handle.getChannel().lock()){return action.run(resolve(new NetworkCatalog(context),candidate));}}
  }
  static final class ActiveSnapshot {
    static final String[] RECORDS={"network","subscription","subscription-meta","subscription-ui","exit-subscription","exit-subscription-meta","exit-subscription-ui"};
    final SecretStore vault;final Map<String,byte[]> before=new LinkedHashMap<>(),after=new LinkedHashMap<>();boolean writing;
    ActiveSnapshot(SecretStore vault)throws Exception{this.vault=vault;withActiveSnapshot(vault.context,()->{readInto(before);return null;});}
    void readInto(Map<String,byte[]> target)throws Exception{target.clear();for(String key:RECORDS)target.put(key,vault.get(key));}
    boolean matches(Map<String,byte[]> expected)throws Exception{for(String key:RECORDS)if(!Arrays.equals(expected.get(key),vault.get(key)))return false;return true;}
    void write(Sources sources,JSONObject candidate)throws Exception{
      withActiveSnapshot(vault.context,()->{
        if(writing||!matches(before))throw new IOException("环境网络快照已变化，请重新保存");
        writing=true;try{
          vault.put("subscription",sources.entryBytes);vault.put("subscription-meta",metadata(sources.entry,sources.entryBytes).toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));vault.put("subscription-ui",uiMetadata(sources.entry,sources.entryBytes).toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));
          if(sources.exit!=null){vault.put("exit-subscription",sources.exitBytes);vault.put("exit-subscription-meta",metadata(sources.exit,sources.exitBytes).toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));vault.put("exit-subscription-ui",uiMetadata(sources.exit,sources.exitBytes).toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));}
          else for(String key:new String[]{"exit-subscription","exit-subscription-meta","exit-subscription-ui"})restore(vault,key,null);
          vault.save(candidate);readInto(after);
        }catch(Exception failure){
          // Readers cannot acquire the lease between a partial write and its
          // restoration. An outer transaction can still roll back a full write.
          try{restoreBefore();writing=false;}catch(Exception restoration){failure.addSuppressed(restoration);try{readInto(after);}catch(Exception unavailable){failure.addSuppressed(unavailable);}}
          throw failure;
        }return null;
      });
    }
    void restoreBefore()throws Exception{Exception failure=null;for(Map.Entry<String,byte[]> previous:before.entrySet())try{restore(vault,previous.getKey(),previous.getValue());}catch(Exception error){if(failure==null)failure=error;}if(failure!=null)throw failure;}
    void rollback()throws Exception{withActiveSnapshot(vault.context,()->{if(!writing)return null;if(after.isEmpty()||!matches(after))throw new IOException("环境网络快照已变化，未覆盖较新的设置");restoreBefore();writing=false;return null;});}
  }
  static void restore(SecretStore vault,String slot,byte[] bytes)throws Exception{if(bytes==null)vault.remove(slot);else vault.put(slot,bytes);}
  static JSONObject metadata(JSONObject row){return J.obj("sourceId",row.optString("id"),"sourceUrl",row.optString("url"),"role",row.optString("role"),"urlHash",NativeNetwork.hash(row.optString("url")),"addressRevision",row.optLong("addressRevision"),"updatedAt",row.optLong("updatedAt"));}
  static String snapshotGeneration(String role,String id,long addressRevision,byte[] bytes){
    NetworkSubscriptionCatalogPolicy.role(role);if(id==null||id.isEmpty()||addressRevision<1||bytes==null||bytes.length==0)throw new IllegalArgumentException("来源快照身份不完整");
    return "snapshot-"+payloadHash((role+"|"+id+"|"+addressRevision+"|"+payloadHash(bytes)).getBytes(java.nio.charset.StandardCharsets.UTF_8));
  }
  static void snapshotMetadata(JSONObject value,JSONObject row,byte[] bytes){NetworkCatalog.put(value,"payloadHash",payloadHash(bytes));NetworkCatalog.put(value,"cacheGeneration",snapshotGeneration(row.optString("role"),row.optString("id"),row.optLong("addressRevision"),bytes));NetworkCatalog.put(value,"sourceCacheGeneration",row.optString("cacheSlot"));}
  static JSONObject metadata(JSONObject row,byte[] bytes){JSONObject value=metadata(row);snapshotMetadata(value,row,bytes);return value;}
  static JSONObject uiMetadata(JSONObject row,byte[] bytes){JSONObject value=uiMetadata(row);snapshotMetadata(value,row,bytes);return value;}
  static JSONObject uiMetadata(JSONObject row){JSONObject value=metadata(row);NetworkCatalog.put(value,"nodes",NetworkCatalog.copy(row.optJSONArray("nodes")));NetworkCatalog.put(value,"nodeDetails",NetworkCatalog.copy(row.optJSONArray("nodeDetails")));return value;}
}
