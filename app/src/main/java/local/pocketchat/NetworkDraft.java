package local.pocketchat;
import org.json.*;import java.util.*;import java.io.IOException;

/** Detached candidate. No preferences, route selection, or live connection writes occur here. */
final class NetworkDraft {
  final int slot;final String baseline;final JSONObject original;
  String subscriptionId="",exitId="",mode="random",entry="",entryNodeKey="";
  String exitSubscriptionId="",exitNodeKey="",exitNodeName="";
  final LinkedHashSet<String> pool=new LinkedHashSet<>(),entryPoolKeys=new LinkedHashSet<>();
  private final LinkedHashMap<String,String> trackedPool=new LinkedHashMap<>();private String trackedEntry="";private boolean poolIdentities;private String selectionIssue="";
  private String entrySourceUrl="",exitSourceUrl="",manualEndpointIdentity="";private long entryAddressRevision=-1,exitAddressRevision=-1;
  NetworkDraft(int slot,JSONObject original,NetworkCatalog catalog){
    this.slot=slot;this.original=J.parse(original.toString());baseline=NetworkChanges.hash(Profiles.context(catalog.c,slot));
    String url=original.optString("subscriptionUrl"),id=original.optString("entrySubscriptionId");JSONObject sub=catalog.subscription(NetworkCatalog.ENTRY,id.isEmpty()?NativeNetwork.hash(url):id);subscriptionId=sub==null?(id.isEmpty()?NativeNetwork.hash(url):id):sub.optString("id");
    mode=original.length()==0?"latency":"latency".equals(original.optString("entryMode"))?"latency":"manual".equals(original.optString("entryMode"))?"manual":"random";
    entry=original.optString("entry");entryNodeKey=original.optString("entryNodeKey");pool.addAll(EntrySelection.strings(original.optJSONArray("entryPool")));entryPoolKeys.addAll(NetworkSourceSelection.keys(original.optJSONArray("entryPoolKeys")));poolIdentities=original.has("entryPoolKeys");
    if(!original.has("entryMode")&&sub!=null)pool.addAll(NetworkSourceSelection.names(sub));
    entrySourceUrl=url;entryAddressRevision=original.has("entrySubscriptionAddressRevision")?original.optLong("entrySubscriptionAddressRevision"):-1;
    if("subscription".equals(original.optString("exitSource"))){exitSubscriptionId=original.optString("exitSubscriptionId");exitNodeKey=original.optString("exitNodeKey");exitNodeName=original.optString("exitNodeName");exitSourceUrl=original.optString("exitSubscriptionUrl");exitAddressRevision=original.has("exitSubscriptionAddressRevision")?original.optLong("exitSubscriptionAddressRevision"):-1;}
    else{manualEndpointIdentity=original.optString("exitHost").isEmpty()?"":NetworkCatalog.exitId(original);JSONObject manual=catalog.exit(original.optString("exitLibraryId",NetworkCatalog.exitId(original)));if(manual!=null)exitId=manual.optString("id");else if(!original.optString("exitHost").isEmpty())exitId=NetworkCatalog.exitId(original);}
    // Capture old identities before a refresh can turn a same-name node into a different connection.
    JSONObject savedRefs=original.optJSONObject("entryPoolNodeKeys");for(String name:pool)trackedPool.put(name,poolIdentities?(savedRefs!=null?savedRefs.optString(name):identityName(sub,name)):NetworkSourceSelection.fingerprint(sub,name));trackedEntry=entry;
    if(entryNodeKey.isEmpty()&&!original.has("entryNodeKey"))entryNodeKey=NetworkSourceSelection.fingerprint(sub,entry);
    if(!poolIdentities){boolean complete=!pool.isEmpty();for(String name:pool){String key=NetworkSourceSelection.fingerprint(sub,name);if(key.isEmpty())complete=false;else entryPoolKeys.add(key);}poolIdentities=complete;}
    normalize(catalog);
  }
  private String identityName(JSONObject sub,String name){String key=NetworkSourceSelection.fingerprint(sub,name);return entryPoolKeys.contains(key)?key:"";}
  void subscription(String id,NetworkCatalog catalog){JSONObject row=catalog.subscription(NetworkCatalog.ENTRY,id);String canonical=row==null?id:row.optString("id");if(!canonical.equals(subscriptionId)){subscriptionId=canonical;pool.clear();entryPoolKeys.clear();trackedPool.clear();entry="";entryNodeKey="";trackedEntry="";poolIdentities=false;}entrySourceUrl=row==null?"":row.optString("url");entryAddressRevision=row==null?-1:row.optLong("addressRevision");normalize(catalog);}
  void exitSubscription(String id,NetworkCatalog catalog){JSONObject row=catalog.subscription(NetworkCatalog.EXIT,id);String canonical=row==null?id:row.optString("id");if(!canonical.equals(exitSubscriptionId)||!exitId.isEmpty()){exitNodeKey="";exitNodeName="";}exitId="";manualEndpointIdentity="";exitSubscriptionId=canonical;exitSourceUrl=row==null?"":row.optString("url");exitAddressRevision=row==null?-1:row.optLong("addressRevision");normalize(catalog);}
  void exitNode(String key,NetworkCatalog catalog){exitNode(key,key.equals(exitNodeKey)?exitNodeName:"",catalog);}
  void exitNode(String key,String name,NetworkCatalog catalog){JSONObject current=NetworkSourceSelection.node(catalog.subscription(NetworkCatalog.EXIT,exitSubscriptionId),key,name);exitNodeKey=NetworkSourceSelection.socks5(current)?key:"";exitNodeName=NetworkSourceSelection.socks5(current)?current.optString("name"):"";}
  void manualExit(String id){manualEndpointIdentity="";exitId=id;exitSubscriptionId="";exitNodeKey="";exitNodeName="";exitSourceUrl="";exitAddressRevision=-1;}
  void manualExit(String id,NetworkCatalog catalog){manualExit(id);JSONObject row=catalog.exit(id);if(row!=null)manualEndpointIdentity=NetworkCatalog.exitId(J.obj("exitHost",row.optString("host"),"exitPort",row.optInt("port"),"exitUser",row.optString("user"),"exitPassword",row.optString("password")));}
  void chooseEntry(String name,NetworkCatalog catalog){JSONObject sub=catalog.subscription(NetworkCatalog.ENTRY,subscriptionId);entry=NetworkSourceSelection.names(sub).contains(name)?name:"";entryNodeKey=NetworkSourceSelection.fingerprint(sub,entry);trackedEntry=entry;}
  private void rebuildKeys(){entryPoolKeys.clear();for(String key:trackedPool.values())if(key!=null&&!key.isEmpty())entryPoolKeys.add(key);}
  void allowEntry(String name,boolean allowed,NetworkCatalog catalog){JSONObject sub=catalog.subscription(NetworkCatalog.ENTRY,subscriptionId);String key=NetworkSourceSelection.fingerprint(sub,name);if(allowed&&NetworkSourceSelection.names(sub).contains(name)){pool.add(name);trackedPool.put(name,key);}else{pool.remove(name);trackedPool.remove(name);}rebuildKeys();poolIdentities=poolIdentities||!pool.isEmpty()&&trackedPool.values().stream().noneMatch(String::isEmpty);if(!pool.contains(entry)&&NetworkOptimizationPolicy.pooled(mode)){entry="";entryNodeKey="";trackedEntry="";}}
  /** Compatibility for older UI callers: only changed choices acquire a new identity. */
  private void captureEdits(JSONObject sub){
    for(String previous:new ArrayList<>(trackedPool.keySet()))if(!pool.contains(previous))trackedPool.remove(previous);
    for(String name:pool)if(!trackedPool.containsKey(name))trackedPool.put(name,NetworkSourceSelection.fingerprint(sub,name));
    if(!entry.equals(trackedEntry))entryNodeKey=NetworkSourceSelection.fingerprint(sub,entry);
    boolean complete=!pool.isEmpty()&&trackedPool.values().stream().noneMatch(String::isEmpty);if(complete){poolIdentities=true;rebuildKeys();}else if(pool.isEmpty())entryPoolKeys.clear();
  }
  void normalize(NetworkCatalog catalog){
    JSONObject sub=catalog.subscription(NetworkCatalog.ENTRY,subscriptionId);captureEdits(sub);selectionIssue="";
    JSONObject candidate=J.obj("entryMode",mode,"entry",entry,"entryPool",new JSONArray(pool));if(!entryNodeKey.isEmpty())NetworkCatalog.put(candidate,"entryNodeKey",entryNodeKey);
    if(poolIdentities){NetworkCatalog.put(candidate,"entryPoolKeys",new JSONArray(entryPoolKeys));if(trackedPool.values().stream().noneMatch(String::isEmpty)){JSONObject refs=new JSONObject();for(Map.Entry<String,String> row:trackedPool.entrySet())NetworkCatalog.put(refs,row.getKey(),row.getValue());NetworkCatalog.put(candidate,"entryPoolNodeKeys",refs);}}
    try{NetworkSourceSelection.normalizeEntries(candidate,sub,false);pool.clear();pool.addAll(EntrySelection.strings(candidate.optJSONArray("entryPool")));entryPoolKeys.clear();entryPoolKeys.addAll(NetworkSourceSelection.keys(candidate.optJSONArray("entryPoolKeys")));poolIdentities=candidate.has("entryPoolKeys");entry=candidate.optString("entry");entryNodeKey=candidate.optString("entryNodeKey");trackedPool.clear();JSONObject refs=candidate.optJSONObject("entryPoolNodeKeys");for(String name:pool)trackedPool.put(name,refs==null?NetworkSourceSelection.fingerprint(sub,name):refs.optString(name));trackedEntry=entry;}
    catch(IOException changed){selectionIssue=changed.getMessage();}
    if(!exitSubscriptionId.isEmpty()){JSONObject source=catalog.subscription(NetworkCatalog.EXIT,exitSubscriptionId),selected=NetworkSourceSelection.node(source,exitNodeKey,exitNodeName);if(NetworkSourceSelection.socks5(selected))exitNodeName=selected.optString("name");else if(NetworkSourceSelection.ambiguous(source,exitNodeKey))selectionIssue="固定出口别名已变化，请重新选择";else exitNodeName="";}
  }
  void randomize(Random random){entry=EntrySelection.random(pool,random);entryNodeKey=trackedPool.getOrDefault(entry,"");trackedEntry=entry;}
  JSONObject candidate(NetworkCatalog catalog)throws Exception{
    normalize(catalog);if(!selectionIssue.isEmpty())throw new IOException(selectionIssue);JSONObject s=catalog.subscription(NetworkCatalog.ENTRY,subscriptionId);if(s==null)throw new IOException("请选择入口订阅");
    if(!entrySourceUrl.isEmpty()&&!entrySourceUrl.equals(s.optString("url"))||entryAddressRevision>=0&&entryAddressRevision!=s.optLong("addressRevision"))throw new IOException("入口订阅地址已变化，请重新选择");
    JSONObject value=J.parse(original.toString());for(String key:new String[]{"subscriptionUrl","subscriptionName","entrySubscriptionId","entrySubscriptionAddressRevision","exitHost","exitPort","exitUser","exitPassword","exitName","exitRegion","exitSource","exitLibraryId","exitSubscriptionId","exitSubscriptionUrl","exitSubscriptionName","exitSubscriptionAddressRevision","exitNodeKey","exitNodeName","entryMode","entryPool","entryPoolKeys","entryPoolNodeKeys","entry","entryNodeKey"})value.remove(key);
    NetworkSourceSelection.sourceMetadata(value,NetworkCatalog.ENTRY,s);NetworkCatalog.put(value,"entryMode",mode);NetworkCatalog.put(value,"entryPool",new JSONArray(pool));NetworkCatalog.put(value,"entry",entry);if(poolIdentities){NetworkCatalog.put(value,"entryPoolKeys",new JSONArray(entryPoolKeys));JSONObject refs=new JSONObject();for(Map.Entry<String,String> row:trackedPool.entrySet())NetworkCatalog.put(refs,row.getKey(),row.getValue());NetworkCatalog.put(value,"entryPoolNodeKeys",refs);}if(!entryNodeKey.isEmpty())NetworkCatalog.put(value,"entryNodeKey",entryNodeKey);
    if(!exitSubscriptionId.isEmpty()){
      JSONObject exit=catalog.subscription(NetworkCatalog.EXIT,exitSubscriptionId);if(exit==null)throw new IOException("请选择出口订阅");if(!exitSourceUrl.equals(exit.optString("url"))||exitAddressRevision>=0&&exitAddressRevision!=exit.optLong("addressRevision"))throw new IOException("出口订阅地址已变化，请重新选择");
      if(!NetworkSourceSelection.socks5(NetworkSourceSelection.node(exit,exitNodeKey,exitNodeName)))throw new IOException("请选择固定 SOCKS5 出口");NetworkCatalog.put(value,"exitSource","subscription");NetworkSourceSelection.sourceMetadata(value,NetworkCatalog.EXIT,exit);NetworkCatalog.put(value,"exitNodeKey",exitNodeKey);NetworkCatalog.put(value,"exitNodeName",exitNodeName);NetworkCatalog.put(value,"exitName",exitNodeName);
    }else{
      JSONObject e=catalog.exit(exitId);if(e==null)throw new IOException("请选择固定出口");if(!manualEndpointIdentity.isEmpty()&&!manualEndpointIdentity.equals(NetworkCatalog.exitId(J.obj("exitHost",e.optString("host"),"exitPort",e.optInt("port"),"exitUser",e.optString("user"),"exitPassword",e.optString("password")))))throw new IOException("固定出口已编辑，请重新选择");NetworkCatalog.put(value,"exitSource","manual");NetworkCatalog.put(value,"exitLibraryId",e.optString("id"));NetworkCatalog.put(value,"exitHost",e.optString("host"));NetworkCatalog.put(value,"exitPort",e.optInt("port"));NetworkCatalog.put(value,"exitUser",e.optString("user"));NetworkCatalog.put(value,"exitPassword",e.optString("password"));NetworkCatalog.put(value,"exitName",e.optString("name"));NetworkCatalog.put(value,"exitRegion",e.optString("region"));
    }
    NetworkSourceSelection.validateRefs(catalog,value);return value;
  }
}
