package local.pocketchat;

import android.content.Context;
import android.net.Uri;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

/** Encrypted source library. Library changes never write a running environment. */
final class NetworkCatalog {
  static final String ENTRY="entry", EXIT="exit";
  static final Object lock=new Object();
  final Context c;
  final SecretStore store;
  final JSONObject data;
  private String readError="";

  static final class RefreshToken {
    final String id,role,url,refreshToken;
    final long addressRevision;
    RefreshToken(JSONObject row){id=row.optString("id");role=row.optString("role");url=row.optString("url");addressRevision=row.optLong("addressRevision");refreshToken=row.optString("refreshToken");}
  }
  NetworkCatalog(Context c){
    this.c=c;store=new SecretStore(Profiles.context(c,0));JSONObject loaded;
    try{loaded=saved();}catch(Exception error){loaded=new JSONObject();readError="网络库无法读取或版本较新，已保留原加密文件；请使用匹配版本检查";}
    data=normalize(loaded);if(readError.isEmpty())collect();
  }
  static void put(JSONObject o,String key,Object value){try{o.put(key,value);}catch(JSONException e){throw new IllegalArgumentException(e);}}
  static JSONObject copy(JSONObject value){return J.parse(value.toString());}
  static JSONArray copy(JSONArray value){try{return value==null?new JSONArray():new JSONArray(value.toString());}catch(JSONException error){throw new IllegalArgumentException(error);}}
  static String exitId(JSONObject s){return NativeNetwork.hash(s.optString("exitHost")+":"+s.optInt("exitPort")+":"+s.optString("exitUser")+":"+s.optString("exitPassword"));}
  static String cacheSlot(String url){return encodedSlot("pool-",url);}
  static String encodedSlot(String prefix,String value){StringBuilder name=new StringBuilder(prefix);for(char x:NativeNetwork.hash(value).toCharArray())name.append("abcdefghijklmnop".charAt(Character.digit(x,16)));return name.toString();}
  static String subscriptionName(JSONObject s){String name=s.optString("subscriptionName");if(!name.isEmpty())return name;String host=Uri.parse(s.optString("subscriptionUrl")).getHost();return host==null?"未选订阅":host;}
  static String key(String role){NetworkSubscriptionCatalogPolicy.role(role);return ENTRY.equals(role)?"subscriptions":"exitSubscriptions";}
  JSONArray subscriptions(){return subscriptions(ENTRY);}
  JSONArray subscriptions(String role){return data.optJSONArray(key(role));}
  JSONArray exits(){return data.optJSONArray("exits");}
  static JSONObject find(JSONArray list,String id){if(list!=null)for(int i=0;i<list.length();i++){JSONObject x=list.optJSONObject(i);if(x!=null&&id.equals(x.optString("id")))return x;}return null;}
  static boolean contains(JSONArray values,String value){if(values!=null)for(int i=0;i<values.length();i++)if(value.equals(values.optString(i)))return true;return false;}
  static void alias(JSONObject item,String value){JSONArray aliases=item.optJSONArray("aliases");if(aliases==null){aliases=new JSONArray();put(item,"aliases",aliases);}if(!value.isEmpty()&&!contains(aliases,value))aliases.put(value);}
  static JSONObject lookup(JSONArray list,String id){JSONObject exact=find(list,id);if(exact!=null)return exact;if(list!=null)for(int i=0;i<list.length();i++){JSONObject row=list.optJSONObject(i);if(row!=null&&(id.equals(row.optString("urlHash"))||contains(row.optJSONArray("aliases"),id)))return row;}return null;}
  JSONObject subscription(String id){return subscription(ENTRY,id);}
  String readError(){return readError;}
  JSONObject subscription(String role,String id){return lookup(subscriptions(role),id);}
  JSONObject exit(String id){return lookup(exits(),id);}
  static String endpointFingerprint(JSONObject row){return NativeNetwork.hash(row.optString("host")+":"+row.optInt("port")+":"+row.optString("user")+":"+row.optString("password"));}
  /** Historical aliases resolve old references; only current endpoints deduplicate edits. */
  static JSONObject currentExit(JSONArray rows,JSONObject config){for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);if(row!=null&&row.optString("host").equals(config.optString("exitHost"))&&row.optInt("port")==config.optInt("exitPort")&&row.optString("user").equals(config.optString("exitUser"))&&row.optString("password").equals(config.optString("exitPassword")))return row;}return null;}
  static boolean removed(JSONObject catalog,String role,String id){JSONArray all=catalog.optJSONArray("subscriptionTombstones");if(all!=null)for(int i=0;i<all.length();i++){JSONObject t=all.optJSONObject(i);if(t!=null&&role.equals(t.optString("role"))&&(id.equals(t.optString("id"))||contains(t.optJSONArray("aliases"),id)))return true;}return false;}
  static boolean exitRemoved(JSONObject catalog,String id){return lookup(catalog.optJSONArray("exitTombstones"),id)!=null;}
  static JSONObject normalize(JSONObject value){
    for(String name:new String[]{"subscriptions","exitSubscriptions","exits","subscriptionTombstones","exitTombstones"})if(value.optJSONArray(name)==null)put(value,name,new JSONArray());
    for(String role:new String[]{ENTRY,EXIT}){JSONArray rows=value.optJSONArray(key(role));for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);if(row==null)continue;
      put(row,"role",role);if(row.optString("id").isEmpty())put(row,"id",UUID.randomUUID().toString());if(row.optString("urlHash").isEmpty())put(row,"urlHash",NativeNetwork.hash(row.optString("url")));alias(row,row.optString("urlHash"));
      if(!row.has("revision"))put(row,"revision",1L);if(!row.has("addressRevision"))put(row,"addressRevision",1L);if(!row.has("lastSuccessAt"))put(row,"lastSuccessAt",row.optLong("updatedAt"));
      if(row.optJSONArray("nodes")==null)put(row,"nodes",new JSONArray());if(row.optJSONArray("nodeDetails")==null)put(row,"nodeDetails",new JSONArray());
      if(!row.has("cacheAddressRevision")&&(row.has("cacheUpdatedAt")||row.optJSONArray("nodes").length()>0))put(row,"cacheAddressRevision",row.optLong("addressRevision"));
      if(!row.has("cacheUrl")&&row.optLong("cacheAddressRevision")>0)put(row,"cacheUrl",row.optString("url"));
      if(!row.has("stale"))put(row,"stale",row.optLong("cacheAddressRevision")!=row.optLong("addressRevision"));
    }}
    for(int i=0;i<value.optJSONArray("exits").length();i++){JSONObject row=value.optJSONArray("exits").optJSONObject(i);if(row!=null){if(!row.has("revision"))put(row,"revision",1L);alias(row,row.optString("id"));}}
    put(value,"schemaVersion",2);return value;
  }
  /** Read-only legacy import. Aliases and tombstones suppress old environment resurrection. */
  void collect(){
    JSONArray rows=ProfileCatalog.get(c).list();
    for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);if(row==null||!row.optBoolean("created")&&!row.optBoolean("deleting"))continue;int slot=row.optInt("slot");SecretStore vault=new SecretStore(Profiles.context(c,slot));JSONObject config=vault.settings();String url=config.optString("subscriptionUrl");
      if(!url.isEmpty()){String id=NativeNetwork.hash(url);JSONObject s=subscription(id);
        if(s==null&&!removed(data,ENTRY,id)){s=J.obj("id",id,"role",ENTRY,"name",subscriptionName(config),"url",url,"urlHash",id,"owner",slot,"nodes",new JSONArray(),"nodeDetails",new JSONArray(),"revision",1L,"addressRevision",1L,"stale",true);alias(s,id);subscriptions().put(s);}
        // An old URL must not overwrite an edited source's new address or cache.
        if(s!=null&&id.equals(s.optString("urlHash")))try{
          JSONObject meta=J.parse(new String(Optional.ofNullable(vault.get("subscription-meta")).orElse(new byte[0]),StandardCharsets.UTF_8)),ui=J.parse(new String(Optional.ofNullable(vault.get("subscription-ui")).orElse(new byte[0]),StandardCharsets.UTF_8));
          if(!s.has("cacheSlot")&&id.equals(ui.optString("urlHash"))&&s.optJSONArray("nodes").length()==0){put(s,"nodes",copy(ui.optJSONArray("nodes")));put(s,"owner",slot);put(s,"cacheAddressRevision",s.optLong("addressRevision"));put(s,"stale",false);}
          if(!s.has("cacheSlot")&&id.equals(meta.optString("urlHash"))&&vault.get("subscription")!=null){put(s,"owner",slot);put(s,"cacheAddressRevision",s.optLong("addressRevision"));put(s,"cacheUrl",url);put(s,"stale",false);}
          if(!s.has("cacheSlot")&&id.equals(meta.optString("urlHash"))&&meta.optLong("updatedAt")>s.optLong("updatedAt")){put(s,"updatedAt",meta.optLong("updatedAt"));put(s,"lastSuccessAt",meta.optLong("updatedAt"));put(s,"owner",slot);}
        }catch(Exception ignored){}
      }
      if(!config.optString("exitHost").isEmpty()){String id=exitId(config);JSONObject e=exit(id);
        if(e==null&&!exitRemoved(data,id)){e=J.obj("id",id,"name",config.optString("exitName",config.optString("exitHost")),"region",config.optString("exitRegion"),"host",config.optString("exitHost"),"port",config.optInt("exitPort"),"user",config.optString("exitUser"),"password",config.optString("exitPassword"),"revision",1L);alias(e,id);exits().put(e);}
        if(e!=null)try{JSONObject baseline=J.parse(new String(Optional.ofNullable(vault.get("exit-baseline")).orElse(new byte[0]),StandardCharsets.UTF_8));String currentFingerprint=NativeNetwork.hash(e.optString("host")+":"+e.optInt("port")+":"+e.optString("user")+":"+e.optString("password"));if(currentFingerprint.equals(id)&&id.equals(baseline.optString("fingerprint")))put(e,"verifiedIp",baseline.optString("ip"));}catch(Exception ignored){}
      }
    }
  }
  static File lockFile(Context c){return new File(Profiles.context(c,0).getNoBackupFilesDir(),"network-catalog.lock");}
  File lockFile(){return lockFile(c);}
  static IOException invalidCatalog(){return new IOException("网络库格式或版本不受支持，原加密文件已保留");}
  static boolean integer(Object value){return value instanceof Integer||value instanceof Long||value instanceof Short||value instanceof Byte;}
  static void textFields(JSONObject row,String... fields)throws IOException{for(String field:fields)if(row.has(field)&&!(row.opt(field) instanceof String))throw invalidCatalog();}
  static void numbers(JSONObject row,long minimum,String... fields)throws IOException{for(String field:fields)if(row.has(field)&&(!integer(row.opt(field))||((Number)row.opt(field)).longValue()<minimum))throw invalidCatalog();}
  static void stringList(JSONObject row,String field)throws IOException{if(!row.has(field))return;JSONArray values=row.optJSONArray(field);if(values==null)throw invalidCatalog();Set<String> seen=new HashSet<>();for(int i=0;i<values.length();i++){Object value=values.opt(i);if(!(value instanceof String)||((String)value).isEmpty()||!seen.add((String)value))throw invalidCatalog();}}
  /** Validate persisted data before normalization can add legacy defaults. */
  static JSONObject strictCatalog(byte[] raw)throws Exception{
    if(raw.length==0||raw.length>32*1024*1024)throw invalidCatalog();
    String text=StandardCharsets.UTF_8.newDecoder().onMalformedInput(java.nio.charset.CodingErrorAction.REPORT).onUnmappableCharacter(java.nio.charset.CodingErrorAction.REPORT).decode(java.nio.ByteBuffer.wrap(raw)).toString();
    JSONTokener parser=new JSONTokener(text);Object parsed=parser.nextValue();if(!(parsed instanceof JSONObject)||parser.nextClean()!=0)throw invalidCatalog();JSONObject value=(JSONObject)parsed;
    Object version=value.opt("schemaVersion");if(value.has("schemaVersion")&&(!integer(version)||((Number)version).longValue()<1||((Number)version).longValue()>2))throw invalidCatalog();
    // Published legacy catalogues have no marker (or version 1); schema 2 always
    // writes all five lists. The earlier draft exitSources format is unrelated.
    if(value.has("schema")||value.has("exitSources"))throw invalidCatalog();
    boolean current=version!=null&&((Number)version).longValue()==2;
    for(String name:new String[]{"subscriptions","exitSubscriptions","exits","subscriptionTombstones","exitTombstones"}){
      if(!value.has(name)){if(current||"subscriptions".equals(name)||"exits".equals(name))throw invalidCatalog();continue;}
      JSONArray rows=value.optJSONArray(name);if(rows==null)throw invalidCatalog();Set<String> identities=new HashSet<>();
      for(int i=0;i<rows.length();i++){
        JSONObject row=rows.optJSONObject(i);if(row==null||!(row.opt("id") instanceof String)||row.optString("id").isEmpty()||!identities.add(row.optString("id")))throw invalidCatalog();
        textFields(row,"name","role","url","urlHash","host","user","password","region","verifiedIp","cacheSlot","previousCacheSlot","shareCacheSlot","previousShareCacheSlot","cacheUrl","cacheUrlHash","refreshToken","lastError");
        numbers(row,1,"revision","addressRevision");numbers(row,0,"cacheAddressRevision","updatedAt","cacheUpdatedAt","lastSuccessAt","lastAttemptAt","lastFailureAt","deletedAt");
        for(String field:new String[]{"stale","updating"})if(row.has(field)&&!(row.opt(field) instanceof Boolean))throw invalidCatalog();
        for(String field:new String[]{"cacheSlot","previousCacheSlot"})if(row.has(field)&&!row.optString(field).matches("[a-z-]+"))throw invalidCatalog();
        for(String field:new String[]{"shareCacheSlot","previousShareCacheSlot"})if(row.has(field)&&!row.optString(field).isEmpty()&&!row.optString(field).matches("source-pool-(entry|exit)-[a-p]+"))throw invalidCatalog();
        stringList(row,"aliases");
        if("subscriptions".equals(name)||"exitSubscriptions".equals(name)){
          String role="subscriptions".equals(name)?ENTRY:EXIT;if(!(row.opt("url") instanceof String)||row.optString("url").isEmpty()||row.has("role")&&!role.equals(row.optString("role")))throw invalidCatalog();
          stringList(row,"nodes");if(row.has("nodeDetails")){JSONArray details=row.optJSONArray("nodeDetails");if(details==null)throw invalidCatalog();for(int n=0;n<details.length();n++)if(details.optJSONObject(n)==null)throw invalidCatalog();}
          if(row.has("owner")&&(!integer(row.opt("owner"))||row.optInt("owner",-1)<0||row.optInt("owner",8)>7))throw invalidCatalog();
        }else if("exits".equals(name)){
          if(!(row.opt("host") instanceof String)||row.optString("host").isEmpty()||!integer(row.opt("port"))||((Number)row.opt("port")).longValue()<1||((Number)row.opt("port")).longValue()>65535)throw invalidCatalog();
        }else if("subscriptionTombstones".equals(name)&&!ENTRY.equals(row.optString("role"))&&!EXIT.equals(row.optString("role")))throw invalidCatalog();
      }
    }
    return value;
  }
  JSONObject saved()throws Exception{byte[] raw=store.get("network-catalog");return normalize(raw==null?new JSONObject():strictCatalog(raw));}
  interface Edit<T>{T run(JSONObject latest)throws Exception;}
  private <T>T write(Edit<T> action)throws Exception{
    if(!readError.isEmpty())throw new IOException(readError);
    synchronized(lock){try(RandomAccessFile handle=new RandomAccessFile(lockFile(),"rw");java.nio.channels.FileLock held=handle.getChannel().lock()){
      JSONObject latest=saved();mergeImports(latest);T result=action.run(latest);store.put("network-catalog",latest.toString().getBytes(StandardCharsets.UTF_8));replace(latest);cleanCacheGenerations(latest);return result;
    }}
  }
  void replace(JSONObject latest){for(Iterator<String> it=data.keys();it.hasNext();){it.next();it.remove();}for(Iterator<String> it=latest.keys();it.hasNext();){String name=it.next();put(data,name,latest.opt(name));}}
  /** Stale instances may import missing rows, never overwrite current edits or deleted IDs. */
  void mergeImports(JSONObject latest){
    for(String role:new String[]{ENTRY,EXIT})for(int i=0;i<subscriptions(role).length();i++){JSONObject row=subscriptions(role).optJSONObject(i);if(row==null)continue;JSONArray all=latest.optJSONArray(key(role));boolean tombstone=removed(latest,role,row.optString("id"));JSONArray aliases=row.optJSONArray("aliases");if(aliases!=null)for(int n=0;n<aliases.length();n++)tombstone|=removed(latest,role,aliases.optString(n));
      if(!tombstone&&lookup(all,row.optString("id"))==null&&lookup(all,row.optString("urlHash"))==null)all.put(copy(row));
    }
    for(int i=0;i<exits().length();i++){JSONObject row=exits().optJSONObject(i);if(row==null)continue;boolean tombstone=exitRemoved(latest,row.optString("id"));JSONArray aliases=row.optJSONArray("aliases");if(aliases!=null)for(int n=0;n<aliases.length();n++)tombstone|=exitRemoved(latest,aliases.optString(n));if(!tombstone&&lookup(latest.optJSONArray("exits"),row.optString("id"))==null)latest.optJSONArray("exits").put(copy(row));}
  }
  void save()throws Exception{write(latest->null);}
  void saveLocked(JSONObject latest)throws Exception{if(!readError.isEmpty())throw new IOException(readError);mergeImports(normalize(strictCatalog(latest.toString().getBytes(StandardCharsets.UTF_8))));store.put("network-catalog",latest.toString().getBytes(StandardCharsets.UTF_8));replace(latest);}
  static JSONObject require(JSONObject latest,String role,String id)throws IOException{JSONObject row=lookup(latest.optJSONArray(key(role)),id);if(row==null)throw new IOException("订阅已删除，请重新选择");return row;}
  static void bump(JSONObject row){put(row,"revision",row.optLong("revision")+1);}
  static void remove(JSONArray rows,String id){for(int i=rows.length()-1;i>=0;i--)if(id.equals(rows.optJSONObject(i).optString("id")))rows.remove(i);}
  static void validateSource(String role,String name,String url)throws Exception{NetworkSubscriptionCatalogPolicy.role(role);if(name==null||name.trim().isEmpty())throw new IOException("填写订阅名称");NativeNetwork.validate(J.obj("subscriptionUrl",url,"exitHost","localhost","exitPort",1));}
  /** Current and previous successful generations are bounded per source. */
  void cleanCacheGenerations(JSONObject latest){
    Set<String> keep=new HashSet<>();for(String role:new String[]{ENTRY,EXIT}){JSONArray all=latest.optJSONArray(key(role));for(int i=0;i<all.length();i++){JSONObject row=all.optJSONObject(i);if(row!=null){keep.add(row.optString("cacheSlot"));keep.add(row.optString("previousCacheSlot"));keep.add(row.optString("shareCacheSlot"));keep.add(row.optString("previousShareCacheSlot"));}}}
    File[] files=Profiles.context(c,0).getNoBackupFilesDir().listFiles();if(files==null)return;
    for(File file:files){String name=file.getName();if(!name.matches("source-pool-(entry|exit)-[a-p]+[.]sealed([.](bak|new))?"))continue;String slot=name.replaceFirst("[.]sealed([.](bak|new))?$","");if(!keep.contains(slot))try{store.remove(slot);}catch(Exception unavailable){/* A later successful library write retries cleanup. */}}
  }
  static boolean local(JSONObject row){return row!=null&&"local".equals(row.optString("sourceType"));}
  /** Optional acceleration cannot block a validated source publication. */
  String saveShareIndex(String slot,NetworkShareSnapshot.Parts share){
    if(share.index==null)return "";
    try{store.put(slot,share.index);return slot;}catch(Exception unavailable){for(int i=0;i<share.details.length();i++){JSONObject row=share.details.optJSONObject(i);if(row!=null&&"candidate".equals(row.optString("shareAvailability")))put(row,"shareAvailability","unavailable");}return "";}
  }
  /** Immutable payloads precede one atomic library publication for both roles. */
  JSONObject importLocalSources(JSONObject entry,byte[] entryBytes,JSONObject exit,byte[] exitBytes)throws Exception{
    return write(latest->{JSONObject result=new JSONObject();
      JSONObject[] items={entry,exit};byte[][] payloads={entryBytes,exitBytes};String[] roles={ENTRY,EXIT};
      for(int n=0;n<2;n++)if(items[n]!=null){JSONObject item=items[n];byte[] bytes=payloads[n];String role=roles[n];
        if(bytes==null||bytes.length==0||bytes.length>1024*1024||item.optJSONArray("nodes")==null||item.optJSONArray("nodes").length()!=1||item.optJSONArray("nodeDetails")==null||item.optJSONArray("nodeDetails").length()!=1)throw new IOException("分享节点未完成解析");
        String hash=NativeNetwork.hash(new String(bytes,StandardCharsets.UTF_8));JSONArray rows=latest.optJSONArray(key(role));JSONObject found=null;
        for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);if(local(row)&&hash.equals(row.optString("sharePayloadHash"))){found=row;break;}}
        if(found==null){String id=UUID.randomUUID().toString(),url="pocketnet:"+id,cache=encodedSlot("source-pool-"+role+"-",id),shareCache=encodedSlot("source-pool-"+role+"-",id+"|share-v1");NetworkShareSnapshot.Parts share=NetworkShareSnapshot.split(copy(item.optJSONArray("nodeDetails")),bytes);long now=System.currentTimeMillis();store.put(cache,bytes);shareCache=saveShareIndex(shareCache,share);
          found=J.obj("id",id,"role",role,"sourceType","local","name",item.optString("name"),"url",url,"urlHash",NativeNetwork.hash(url),"sharePayloadHash",hash,"revision",1L,"addressRevision",1L,"cacheAddressRevision",1L,"cacheSlot",cache,"shareCacheSlot",shareCache,"cacheUrl",url,"nodes",copy(item.optJSONArray("nodes")),"nodeDetails",share.details,"stale",false,"updatedAt",now,"lastSuccessAt",now);rows.put(found);
        }else if(cache(found)==null){throw new IOException("已导入节点缓存不可用，请删除该本地来源后重新导入");}
        put(result,role,found.optString("id"));
      }return result;
    });
  }
  JSONObject addSubscription(String name,String url)throws Exception{return addSubscription(ENTRY,name,url);}
  JSONObject addSubscription(String role,String name,String url)throws Exception{
    String title=name==null?"":name.trim(),address=url==null?"":url.trim();validateSource(role,title,address);
    return write(latest->{JSONArray all=latest.optJSONArray(key(role));JSONObject row=null;for(int i=0;i<all.length();i++)if(address.equals(all.optJSONObject(i).optString("url"))){row=all.optJSONObject(i);break;}
      if(row==null){row=J.obj("id",UUID.randomUUID().toString(),"role",role,"name",title,"url",address,"urlHash",NativeNetwork.hash(address),"owner",Profiles.slot(c),"nodes",new JSONArray(),"nodeDetails",new JSONArray(),"revision",1L,"addressRevision",1L,"stale",true);alias(row,row.optString("urlHash"));all.put(row);}else{put(row,"name",title);bump(row);}return copy(row);
    });
  }
  JSONObject editSubscription(String role,String id,String name,String url)throws Exception{
    String title=name==null?"":name.trim(),address=url==null?"":url.trim();validateSource(role,title,address);
    return write(latest->{JSONObject row=require(latest,role,id);if(local(row))throw new IOException("本地分享节点没有订阅地址");JSONArray all=latest.optJSONArray(key(role));for(int i=0;i<all.length();i++){JSONObject other=all.optJSONObject(i);if(other!=row&&address.equals(other.optString("url")))throw new IOException("此订阅地址已存在");}
      put(row,"name",title);if(!address.equals(row.optString("url"))){
        // Detach any v1 owner cache before changing the address. The owner may
        // later update or be deleted; the library keeps its own previous bytes.
        if(row.optString("cacheSlot").isEmpty()){byte[] previous=lastGoodCache(row);if(previous!=null){String slot=encodedSlot("source-pool-"+role+"-",row.optString("id")+"|legacy|"+UUID.randomUUID());store.put(slot,previous);put(row,"cacheSlot",slot);}}
        alias(row,row.optString("urlHash"));put(row,"url",address);put(row,"urlHash",NativeNetwork.hash(address));alias(row,row.optString("urlHash"));put(row,"addressRevision",row.optLong("addressRevision")+1);put(row,"stale",true);put(row,"updating",false);put(row,"refreshToken","");put(row,"lastError","");}bump(row);return copy(row);
    });
  }
  void deleteSubscription(String role,String id)throws Exception{
    write(latest->{JSONObject row=require(latest,role,id);JSONObject tombstone=J.obj("id",row.optString("id"),"role",role,"aliases",copy(row.optJSONArray("aliases")),"deletedAt",System.currentTimeMillis(),"revision",row.optLong("revision")+1);alias(tombstone,row.optString("urlHash"));latest.optJSONArray("subscriptionTombstones").put(tombstone);remove(latest.optJSONArray(key(role)),row.optString("id"));return null;});
  }
  RefreshToken beginRefresh(String role,String id)throws Exception{
    return write(latest->{JSONObject row=require(latest,role,id);if(local(row))throw new IOException("本地分享节点无需更新订阅");put(row,"refreshToken",UUID.randomUUID().toString());put(row,"lastAttemptAt",System.currentTimeMillis());put(row,"updating",true);bump(row);return new RefreshToken(row);});
  }
  static JSONObject current(JSONObject latest,RefreshToken token)throws IOException{
    if(token==null)throw new IOException("订阅更新已失效");JSONObject row=find(latest.optJSONArray(key(token.role)),token.id);
    if(row==null||!NetworkSubscriptionCatalogPolicy.current(token.id,token.role,token.url,token.addressRevision,token.refreshToken,row.optString("id"),row.optString("role"),row.optString("url"),row.optLong("addressRevision"),row.optString("refreshToken"),row.optBoolean("updating")))throw new IOException("订阅已编辑、删除或重新更新，旧结果未应用");return row;
  }
  void parsed(RefreshToken token,JSONArray nodes,JSONArray nodeDetails,byte[] bytes,long at)throws Exception{
    if(bytes==null||bytes.length==0||bytes.length>16*1024*1024)throw new IOException("订阅缓存为空或文件过大");JSONArray names=copy(nodes);NetworkShareSnapshot.Parts share=NetworkShareSnapshot.split(copy(nodeDetails),bytes);JSONArray details=share.details;
    if(names.length()==0)throw new IOException("订阅没有可选节点");Set<String> seen=new HashSet<>();for(int i=0;i<names.length();i++){String name=names.optString(i);if(name.isEmpty()||!seen.add(name))throw new IOException("订阅节点名称无效或重复");}
    write(latest->{JSONObject row=current(latest,token);String slot=encodedSlot("source-pool-"+token.role+"-",token.id+"|"+token.refreshToken);store.put(slot,bytes);String shareSlot=encodedSlot("source-pool-"+token.role+"-",token.id+"|"+token.refreshToken+"|share-v1");shareSlot=saveShareIndex(shareSlot,share);
      if(!row.optString("shareCacheSlot").isEmpty())put(row,"previousShareCacheSlot",row.optString("shareCacheSlot"));put(row,"shareCacheSlot",shareSlot);
      // Immutable bytes precede the atomic catalogue pointer. Failed publication
      // leaves the prior cache generation valid, including after process death.
      if(!row.optString("cacheSlot").isEmpty())put(row,"previousCacheSlot",row.optString("cacheSlot"));put(row,"cacheSlot",slot);put(row,"cacheAddressRevision",token.addressRevision);put(row,"cacheUrl",token.url);put(row,"cacheUrlHash",NativeNetwork.hash(token.url));put(row,"nodes",names);put(row,"nodeDetails",details);put(row,"updatedAt",at);put(row,"lastSuccessAt",at);put(row,"cacheUpdatedAt",at);put(row,"stale",false);put(row,"lastError","");put(row,"updating",false);put(row,"refreshToken","");bump(row);return null;
    });
  }
  void failed(RefreshToken token,String error,long at)throws Exception{
    write(latest->{JSONObject row=current(latest,token);put(row,"lastError",NetworkSubscriptionCatalogPolicy.error(error));put(row,"lastFailureAt",at);put(row,"updating",false);put(row,"refreshToken","");bump(row);return null;});
  }
  /** Legacy synchronous delegate. Async callers capture beginRefresh before parsing. */
  void parsed(String id,JSONArray nodes,byte[] bytes,long updatedAt)throws Exception{
    JSONObject snapshot=subscription(id);if(snapshot==null)throw new IOException("订阅已删除");final long expected=snapshot.optLong("revision");final String address=snapshot.optString("url");
    RefreshToken token=write(latest->{JSONObject row=require(latest,ENTRY,id);if(row.optLong("revision")!=expected||!address.equals(row.optString("url"))||row.optBoolean("updating")||updatedAt<row.optLong("updatedAt"))throw new IOException("订阅已更新，请重新读取当前入口");put(row,"refreshToken",UUID.randomUUID().toString());put(row,"lastAttemptAt",System.currentTimeMillis());put(row,"updating",true);bump(row);return new RefreshToken(row);});
    try{parsed(token,nodes,new JSONArray(),bytes,updatedAt);}catch(Exception error){try{failed(token,"订阅缓存未能保存",System.currentTimeMillis());}catch(Exception ignored){}throw error;}
  }
  JSONObject shareCandidate(JSONObject row,byte[] bytes,String name,String fingerprint)throws Exception{
    if(row==null||fingerprint==null||!fingerprint.matches("[0-9a-f]{64}"))return null;
    synchronized(lock){JSONObject current=lookup(saved().optJSONArray(key(row.optString("role"))),row.optString("id"));
      if(current==null||current.optBoolean("stale")||current.optLong("cacheAddressRevision")!=current.optLong("addressRevision")||current.optLong("revision")!=row.optLong("revision")||!current.optString("cacheSlot").equals(row.optString("cacheSlot"))||!current.optString("shareCacheSlot").equals(row.optString("shareCacheSlot")))return null;
      boolean identity=false;JSONArray details=current.optJSONArray("nodeDetails");if(details!=null)for(int i=0;i<details.length();i++){JSONObject node=details.optJSONObject(i);if(node!=null&&name.equals(node.optString("name"))&&fingerprint.equals(node.optString("configFingerprint"))&&node.optInt("configFingerprintVersion")==1)identity=true;}
      String slot=current.optString("shareCacheSlot");return !identity||slot.isEmpty()?null:NetworkShareSnapshot.select(store.get(slot),bytes,name,fingerprint);
    }
  }
  byte[] cache(String role,String id){JSONObject row=subscription(role,id);return row==null?null:cache(row);}
  byte[] cache(JSONObject subscription){
    if(subscription==null||subscription.optBoolean("stale")||subscription.optLong("cacheAddressRevision")!=subscription.optLong("addressRevision"))return null;return lastGoodCache(subscription);
  }
  byte[] lastGoodCache(JSONObject subscription){
    if(subscription==null)return null;try{String slot=subscription.optString("cacheSlot");if(!slot.isEmpty())return store.get(slot);
      if(!ENTRY.equals(subscription.optString("role",ENTRY)))return null;String url=subscription.optString("cacheUrl",subscription.optString("url"));byte[] own=store.get(cacheSlot(url));if(own!=null&&subscription.optLong("cacheUpdatedAt")>=subscription.optLong("updatedAt"))return own;
      SecretStore owner=new SecretStore(Profiles.context(c,subscription.optInt("owner")));JSONObject meta=J.parse(new String(Optional.ofNullable(owner.get("subscription-meta")).orElse(new byte[0]),StandardCharsets.UTF_8));if(NativeNetwork.hash(url).equals(meta.optString("urlHash"))&&meta.optLong("updatedAt")>=subscription.optLong("updatedAt"))return owner.get("subscription");
    }catch(Exception ignored){}return null;
  }
  JSONObject addExit(String name,String region,String host,int port,String user,String password)throws Exception{
    JSONObject value=J.obj("subscriptionUrl","https://localhost/","exitHost",host,"exitPort",port,"exitUser",user,"exitPassword",password);NativeNetwork.validate(value);String fingerprint=exitId(value);
    return write(latest->{JSONArray rows=latest.optJSONArray("exits");JSONObject row=currentExit(rows,value);if(row==null){row=J.obj("id",find(rows,fingerprint)!=null||exitRemoved(latest,fingerprint)?UUID.randomUUID().toString():fingerprint,"name",name,"region",region,"host",host,"port",port,"user",user,"password",password,"revision",1L);alias(row,fingerprint);rows.put(row);}else{put(row,"name",name);put(row,"region",region);bump(row);}return copy(row);});
  }
  JSONObject editExit(String id,String name,String region,String host,int port,String user,String password)throws Exception{
    JSONObject value=J.obj("subscriptionUrl","https://localhost/","exitHost",host,"exitPort",port,"exitUser",user,"exitPassword",password);NativeNetwork.validate(value);String fingerprint=exitId(value);
    return write(latest->{JSONObject row=lookup(latest.optJSONArray("exits"),id);if(row==null)throw new IOException("出口已删除");JSONObject duplicate=currentExit(latest.optJSONArray("exits"),value);if(duplicate!=null&&duplicate!=row)throw new IOException("此出口已存在");String previous=endpointFingerprint(row);alias(row,previous);alias(row,fingerprint);if(duplicate!=row)row.remove("verifiedIp");put(row,"name",name);put(row,"region",region);put(row,"host",host);put(row,"port",port);put(row,"user",user);put(row,"password",password);bump(row);return copy(row);});
  }
  void deleteExit(String id)throws Exception{write(latest->{JSONObject row=lookup(latest.optJSONArray("exits"),id);if(row==null)throw new IOException("出口已删除");latest.optJSONArray("exitTombstones").put(J.obj("id",row.optString("id"),"aliases",copy(row.optJSONArray("aliases")),"deletedAt",System.currentTimeMillis()));remove(latest.optJSONArray("exits"),row.optString("id"));return null;});}
}
