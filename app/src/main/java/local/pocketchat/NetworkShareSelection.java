package local.pocketchat;

import android.content.Context;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.json.*;

/** Private per-side selections, published while save/apply already owns the full config.
 * Sharing reads only a head and requested sides, never network/pending-network. */
final class NetworkShareSelection {
  static final String SAVED="share-saved-head",RUNNING="share-running-head";
  static String headSlot(String source){return "running".equals(source)?RUNNING:SAVED;}
  static JSONObject object(byte[] bytes)throws Exception {
    if(bytes==null||bytes.length==0||bytes.length>1024*1024)throw NetworkSharePreparation.fail("CONFIG_READ","UNREADABLE","");
    Object value=NetworkShareJson.decode(new String(bytes,StandardCharsets.UTF_8),1024*1024);
    if(!(value instanceof JSONObject))throw NetworkSharePreparation.fail("CONFIG_READ","MALFORMED","");return (JSONObject)value;
  }
  static void write(SecretStore vault,String slot,JSONObject value)throws Exception {vault.put(slot,NetworkShareJson.encode(value,1024*1024).getBytes(StandardCharsets.UTF_8));}
  static String id(){return NetworkChanges.snapshotId();}
  static EnvironmentSpec.Identity owner(JSONObject head)throws Exception {JSONObject o=head.getJSONObject("owner");return new EnvironmentSpec.Identity(o.getInt("slot"),o.getInt("generation"),o.getString("environmentId"));}
  static JSONObject readHead(Context c,String source)throws Exception {return object(new SecretStore(c).get(headSlot(source)));}
  static void requireOwner(Context c,EnvironmentSpec.Identity expected)throws Exception {if(!ProfileCatalog.get(c).identity(Profiles.slot(c)).equals(expected))throw NetworkSharePreparation.fail("CONFIG_READ","OWNER_CHANGED","");}
  static boolean current(Context c,NetworkSharePreparation.Request request){try{requireOwner(c,request.owner);JSONObject h=readHead(c,request.source);if(!owner(h).equals(request.owner)||!h.optBoolean("available")||!request.version.equals(h.optString("version")))return false;if("saved".equals(request.source)){EnvironmentSpec spec=EnvironmentSpec.read(new SecretStore(c).get("environment-spec"));if(!spec.identity.equals(request.owner)||spec.desiredRevision!=h.optLong("savedRevision")||!spec.desired().network.entryConfigRevision.equals(h.optString("configurationFingerprint")))return false;}return true;}catch(Exception unavailable){return false;}}
  static boolean runningMatches(Context c,NetworkSharePreparation.Request request,NetworkCoreApplication proof)throws Exception {
    if(!"running".equals(request.source)||proof==null||!request.owner.equals(proof.identity)||!current(c,request))return false;
    JSONObject h=readHead(c,"running"),core=h.optJSONObject("core"),actual=proof.json();if(core==null||!proof.configuration.equals(h.optString("configurationFingerprint")))return false;
    for(String key:new String[]{"coreGeneration","corePid","servicePid","routeSerial","configurationFingerprint"})if(!String.valueOf(core.opt(key)).equals(String.valueOf(actual.opt(key))))return false;return true;
  }
  static void invalidateSaved(Context c,EnvironmentSpec.Identity expected)throws Exception {NetworkSourceSelection.withActiveSnapshot(c,()->{requireOwner(c,expected);write(new SecretStore(c),SAVED,J.obj("schema",1,"owner",expected.json(),"available",false));return null;});}
  static void clear(Context c)throws Exception {NetworkSourceSelection.withActiveSnapshot(c,()->{SecretStore v=new SecretStore(c);v.remove(SAVED);v.remove(RUNNING);cleanup(v);return null;});}
  static void clearOwner(Context c,EnvironmentSpec.Identity expected)throws Exception {NetworkSourceSelection.withActiveSnapshot(c,()->{requireOwner(c,expected);SecretStore v=new SecretStore(c);v.remove(SAVED);v.remove(RUNNING);cleanup(v);return null;});}
  static void migrate(Context c,EnvironmentSpec.Identity expected,JSONObject alreadyLoadedConfig,String alreadyReadPendingSnapshot,EnvironmentSpec spec)throws Exception {
    if(alreadyReadPendingSnapshot!=null&&!alreadyReadPendingSnapshot.isEmpty()&&!"{}".equals(alreadyReadPendingSnapshot))savedIntent(c,expected,alreadyReadPendingSnapshot,spec);else savedActive(c,expected,alreadyLoadedConfig,spec);
  }
  static void savedIntent(Context c,EnvironmentSpec.Identity expected,String pendingSnapshot,EnvironmentSpec spec)throws Exception {
    JSONObject pending=new JSONObject(pendingSnapshot);if(!NetworkChanges.identityMatches(pending,expected.json()))throw NetworkSharePreparation.fail("CONFIG_READ","OWNER_CHANGED","");
    JSONObject marker=NetworkChanges.intent(pending);if(marker!=null&&!"ready".equals(marker.optString("state")))throw NetworkSharePreparation.fail("CONFIG_READ","UNREADABLE","");
    if(!"apply".equals(pending.optString("action"))){invalidateSaved(c,expected);return;}
    String candidate=marker==null?NativeNetwork.hash(pendingSnapshot):marker.optString("id");
    publish(c,expected,"saved",candidate,spec.desiredRevision,pending.getJSONObject("config"),pending.optString("entrySnapshot"),pending.optJSONObject("entrySnapshotMeta"),pending.optString("exitSnapshot"),pending.optJSONObject("exitSnapshotMeta"),"",null);
  }
  static void savedActive(Context c,EnvironmentSpec.Identity expected,JSONObject config,EnvironmentSpec spec)throws Exception {
    if(config==null||!"internal".equals(spec.desired().network.mode)){invalidateSaved(c,expected);return;}
    publish(c,expected,"saved","active",spec.desiredRevision,config,"subscription",null,"exit-subscription",null,"",null);
  }
  static void runningApplied(Context c,NetworkCoreApplication proof)throws Exception {
    NativeNetwork n=NativeNetwork.peek();if(n==null||!proof.current(n))throw NetworkSharePreparation.fail("CONFIG_READ","VERSION_CHANGED","");
    publish(c,proof.identity,"running",proof.candidateId,proof.savedRevision,n.settings,"subscription",null,"exit-subscription",null,proof.route.entry,proof);
  }
  static void publish(Context c,EnvironmentSpec.Identity expected,String source,String candidate,long revision,JSONObject config,String entrySlot,JSONObject entryMeta,String exitSlot,JSONObject exitMeta,String actualEntry,NetworkCoreApplication proof)throws Exception {
    NetworkSourceSelection.withActiveSnapshot(c,()->{
      requireOwner(c,expected);
      // Publication already owns full source data. Recheck inside this lease so
      // a newer saved provider cannot be attached to a retained old-core proof.
      // Read-only share capture never performs this whole-authority check.
      if(proof!=null){NativeNetwork n=NativeNetwork.peek();if(n==null||!proof.current(n)||!n.authoritySourcesCurrent())throw NetworkSharePreparation.fail("CONFIG_READ","VERSION_CHANGED","");}
      SecretStore v=new SecretStore(c);String configuration=NativeNetwork.transportFingerprint(config);
      String stamp=NativeNetwork.hash(expected.json()+"|"+source+"|"+candidate+"|"+revision+"|"+configuration+"|"+actualEntry+(proof==null?"":"|"+proof.route.generation+"|"+proof.route.serial));
      try{JSONObject old=readHead(c,source);if(old.optBoolean("available")&&stamp.equals(old.optString("stamp"))&&owner(old).equals(expected))return null;}catch(Exception absent){}
      String version=id(),entry="share-entry-selection-"+version,exit="share-exit-selection-"+version;
      JSONObject common=J.obj("schema",1,"owner",expected.json(),"source",source,"version",version,"stamp",stamp,"savedRevision",revision,"candidateId",candidate,"configurationFingerprint",configuration,"available",true);
      JSONObject entryPart=J.obj("schema",1,"owner",expected.json(),"version",version,"side","entry","choices",choices(config,actualEntry),"name",actualEntry.isEmpty()?config.optString("entry"):actualEntry);
      attach(v,entryPart,entrySlot,entryMeta,"entry",version);
      if(entryPart.getJSONArray("choices").length()==0&&"subscription".equals(entrySlot)){JSONObject ui=null;try{byte[] b=v.get("subscription-ui");if(b!=null)ui=object(b);}catch(Exception ignored){}if(ui!=null&&!entryPart.optString("payloadHash").isEmpty()&&entryPart.optString("payloadHash").equals(ui.optString("payloadHash"))){JSONArray rows=ui.optJSONArray("nodeDetails");JSONArray options=new JSONArray();if(rows!=null)for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);if(row!=null&&row.optString("name").startsWith("Entry|")&&row.optString("configFingerprint").matches("[0-9a-f]{64}")&&(actualEntry.isEmpty()? !"manual".equals(config.optString("entryMode"))||config.optString("entry").equals(row.optString("name")):actualEntry.equals(row.optString("name"))))options.put(J.obj("name",row.optString("name"),"key",row.optString("configFingerprint")));}entryPart.put("choices",options);}}
      JSONObject exitPart=J.obj("schema",1,"owner",expected.json(),"version",version,"side","exit");
      if(NativeNetwork.subscribedExit(config)){exitPart.put("name",config.optString("exitNodeName"));exitPart.put("key",config.optString("exitNodeKey"));attach(v,exitPart,exitSlot,exitMeta,"exit",version);}
      else exitPart.put("manual",J.obj("name",config.optString("exitName"),"host",config.optString("exitHost"),"port",config.optInt("exitPort"),"user",config.optString("exitUser"),"password",config.optString("exitPassword")));
      write(v,entry,entryPart);write(v,exit,exitPart);common.put("entry",entry);common.put("exit",exit);if(proof!=null){if(!proof.current(NativeNetwork.peek()))throw NetworkSharePreparation.fail("CONFIG_READ","VERSION_CHANGED","");common.put("core",proof.json());}
      requireOwner(c,expected);write(v,headSlot(source),common);cleanup(v);return null;
    });
  }
  static JSONArray choices(JSONObject config,String actualEntry)throws Exception {
    JSONArray out=new JSONArray();JSONObject keys=config.optJSONObject("entryPoolNodeKeys");String chosen=actualEntry.isEmpty()?config.optString("entry"):actualEntry;
    if(!actualEntry.isEmpty()||"manual".equals(config.optString("entryMode"))){String key=chosen.equals(config.optString("entry"))?config.optString("entryNodeKey"):keys==null?"":keys.optString(chosen);if(!chosen.isEmpty()&&key.matches("[0-9a-f]{64}"))out.put(J.obj("name",chosen,"key",key));return out;}
    List<String> pool=EntrySelection.strings(config.optJSONArray("entryPool"));for(String name:pool){String key=keys==null?"":keys.optString(name);if(key.isEmpty()&&name.equals(chosen))key=config.optString("entryNodeKey");if(key.matches("[0-9a-f]{64}"))out.put(J.obj("name",name,"key",key));}return out;
  }
  static void attach(SecretStore v,JSONObject part,String origin,JSONObject metadata,String side,String version)throws Exception {
    String hash=metadata==null?"":metadata.optString("payloadHash");part.put("origin",origin);String slot="share-"+side+"-provider-"+version;part.put("provider",slot);
    try{if(!validOrigin(origin,side))throw NetworkSharePreparation.fail("SUBSCRIPTION_CACHE","ABSENT",side);byte[] bytes=v.get(origin);if(bytes==null||bytes.length==0||bytes.length>NetworkSharePreparation.SOURCE_LIMIT)throw NetworkSharePreparation.fail("SUBSCRIPTION_CACHE","UNREADABLE",side);
      String actual=NetworkShareSnapshot.hash(bytes);if(!hash.isEmpty()&&!hash.equals(actual))throw NetworkSharePreparation.fail("SUBSCRIPTION_CACHE","HASH_MISMATCH",side);hash=actual;v.put(slot,bytes);
    }catch(Exception unreadable){part.put("failure",(unreadable instanceof NetworkSharePreparation.Failure?(NetworkSharePreparation.Failure)unreadable:NetworkSharePreparation.fail("SUBSCRIPTION_CACHE","UNREADABLE",side)).json());}
    part.put("payloadHash",hash);
  }
  static boolean validOrigin(String slot,String side){return ("entry".equals(side)?"subscription":"exit-subscription").equals(slot)||slot.matches("pending-"+side+"-subscription-[a-p]{32}");}
  static JSONArray describe(Context c,EnvironmentSpec.Identity expected){JSONArray out=new JSONArray();for(String source:new String[]{"saved","running"})try{JSONObject h=readHead(c,source);if(owner(h).equals(expected)&&h.optBoolean("available"))out.put(J.obj("source",source,"version",h.getString("version"),"savedRevision",h.optLong("savedRevision"),"configurationFingerprint",h.optString("configurationFingerprint")));}catch(Exception ignored){}return out;}
  static JSONObject selection(Context c,NetworkSharePreparation.Request request,int side)throws Exception {
    requireOwner(c,request.owner);JSONObject h=readHead(c,request.source);if(!owner(h).equals(request.owner)||!request.version.equals(h.optString("version"))||!h.optBoolean("available"))throw NetworkSharePreparation.fail("CONFIG_READ","VERSION_CHANGED",side==0?"entry":"exit");
    String field=side==0?"entry":"exit",slot=h.optString(field);if(!slot.matches("share-"+field+"-selection-[a-p]{32}"))throw NetworkSharePreparation.fail("CONFIG_READ","MALFORMED",field);JSONObject part=object(new SecretStore(c).get(slot));
    if(!owner(part).equals(request.owner)||!request.version.equals(part.optString("version"))||!field.equals(part.optString("side")))throw NetworkSharePreparation.fail("CONFIG_READ","VERSION_CHANGED",field);return part;
  }
  static JSONArray entryChoices(Context c,NetworkSharePreparation.Request request)throws Exception {return NetworkSourceSelection.withActiveSnapshot(c,()->{JSONObject p=selection(c,request,0);return p.optJSONArray("choices")==null?new JSONArray():p.getJSONArray("choices");});}
  static NetworkSharePreparation.Frozen capture(Context c,NetworkSharePreparation.Request request)throws Exception {
    return NetworkSourceSelection.withActiveSnapshot(c,()->{requireOwner(c,request.owner);if(!current(c,request))throw NetworkSharePreparation.fail("CONFIG_READ","VERSION_CHANGED","");NetworkSharePreparation.Frozen frozen=new NetworkSharePreparation.Frozen(request,"网络配置");for(int i=0;i<2;i++)if(request.wants(i))frozen.parts[i]=part(c,request,i);requireOwner(c,request.owner);return frozen;});
  }
  static NetworkSharePreparation.Part retryPart(Context c,NetworkSharePreparation.Request request,int side)throws Exception {return NetworkSourceSelection.withActiveSnapshot(c,()->part(c,request,side));}
  static NetworkSharePreparation.Part part(Context c,NetworkSharePreparation.Request request,int index){String side=index==0?"entry":"exit";JSONObject p=null;try{
    try{p=selection(c,request,index);}catch(Exception read){throw read instanceof NetworkSharePreparation.Failure?(NetworkSharePreparation.Failure)read:NetworkSharePreparation.fail("CONFIG_READ","UNREADABLE",side);}if(index==0){JSONArray options=p.getJSONArray("choices");JSONObject found=null;for(int i=0;i<options.length();i++){JSONObject row=options.optJSONObject(i);if(row!=null&&(request.entry.equals(row.optString("name"))||request.entry.isEmpty()&&options.length()==1))found=row;}
      if(found==null)throw NetworkSharePreparation.fail("CONFIG_READ","ENTRY_SELECTION_REQUIRED",side);p.put("name",found.getString("name"));p.put("key",found.getString("key"));}
    if(p.optJSONObject("manual")!=null)return new NetworkSharePreparation.Part(p,null,null);
    SecretStore v=new SecretStore(c);String hash=p.optString("payloadHash"),slot=p.optString("provider");if(!slot.matches("share-"+side+"-provider-[a-p]{32}"))throw NetworkSharePreparation.fail("CONFIG_READ","MALFORMED",side);byte[] bytes=null;try{bytes=v.get(slot);}catch(Exception ignored){}
    if(bytes==null&&hash.matches("[0-9a-f]{64}")&&validOrigin(p.optString("origin"),side))bytes=v.get(p.getString("origin"));
    if(bytes==null||bytes.length==0||bytes.length>NetworkSharePreparation.SOURCE_LIMIT)throw NetworkSharePreparation.fail("SUBSCRIPTION_CACHE","UNREADABLE",side);if(!hash.equals(NetworkShareSnapshot.hash(bytes)))throw NetworkSharePreparation.fail("SUBSCRIPTION_CACHE","HASH_MISMATCH",side);
    return new NetworkSharePreparation.Part(p,bytes,null);
    }catch(Exception error){NetworkSharePreparation.Failure f=error instanceof NetworkSharePreparation.Failure?(NetworkSharePreparation.Failure)error:NetworkSharePreparation.fail("SUBSCRIPTION_CACHE","UNREADABLE",side);return new NetworkSharePreparation.Part(p,null,f);}}
  static void cleanup(SecretStore v){try{Set<String> keep=new HashSet<>();for(String source:new String[]{"saved","running"})try{JSONObject h=readHead(v.context,source);for(String side:new String[]{"entry","exit"}){String slot=h.optString(side);keep.add(slot);if(slot.matches("share-(entry|exit)-selection-[a-p]{32}")){JSONObject p=object(v.get(slot));keep.add(p.optString("provider"));}}}catch(Exception ignored){}
    File[] files=v.context.getNoBackupFilesDir().listFiles();if(files!=null)for(File f:files){String name=f.getName();if(name.matches("share-(entry|exit)-(selection|provider)-[a-p]{32}[.]sealed([.](bak|new))?")){String slot=name.replaceFirst("[.]sealed([.](bak|new))?$","");if(!keep.contains(slot))try{v.remove(slot);}catch(Exception ignored){}}}
    }catch(Exception ignored){}}
}
