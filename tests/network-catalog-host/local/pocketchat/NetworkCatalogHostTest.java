package local.pocketchat;

import android.content.Context;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

public final class NetworkCatalogHostTest {
  static JSONArray checks=new JSONArray();
  static void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));if(!pass)throw new AssertionError(name);}
  interface Throwing{void run()throws Exception;}
  static void rejects(String name,Throwing action)throws Exception{boolean denied=false;try{action.run();}catch(IOException|IllegalArgumentException e){denied=true;}check(name,denied);}
  static byte[] bytes(String s){return s.getBytes(StandardCharsets.UTF_8);}
  static JSONArray names(String name){return J.arr(name);}
  static JSONArray details(String name){return J.arr(J.obj("name",name,"type","Socks5","fingerprint","stable-configuration-fingerprint"));}
  static void parsed(NetworkCatalog c,NetworkCatalog.RefreshToken token,String name,String data,long at)throws Exception{c.parsed(token,names(name),details(name),bytes(data),at);}
  static String cache(NetworkCatalog c,JSONObject row){byte[] raw=c.cache(row);return raw==null?"":new String(raw,StandardCharsets.UTF_8);}
  static String good(NetworkCatalog c,JSONObject row){byte[] raw=c.lastGoodCache(row);return raw==null?"":new String(raw,StandardCharsets.UTF_8);}
  static NetworkCatalog fresh(Context c){return new NetworkCatalog(c);}
  static void readOnly(String label,byte[] raw)throws Exception{
    Context c=new Context(Files.createTempDirectory("network-catalog-format-").toFile(),0);SecretStore vault=new SecretStore(c);NetworkCatalog stale=fresh(c);vault.put("network-catalog",raw);NetworkCatalog current=fresh(c);
    check(label+" is explicitly read only",!current.readError().isEmpty());
    rejects(label+" cannot be changed by a freshly loaded writer",()->current.addSubscription("entry","Do not overwrite","https://fixture.invalid/new"));
    rejects(label+" cannot be changed by an older writer",()->stale.save());
    check(label+" preserves exact saved bytes",Arrays.equals(raw,vault.get("network-catalog")));
  }

  public static void main(String[] args)throws Exception{
    if(args.length>0&&"child-add".equals(args[0])){Context c=new Context(new File(args[1]),0);for(int i=0;i<16;i++)fresh(c).addSubscription(i%2==0?"entry":"exit","Child "+args[2]+" "+i,"https://fixture.invalid/"+args[2]+"/"+i);return;}
    if(args.length>0&&"child-old-save".equals(args[0])){Context c=new Context(new File(args[1]),0);NetworkCatalog old=fresh(c);Files.writeString(c.root.toPath().resolve("child-loaded"),"ready");long until=System.nanoTime()+10_000_000_000L;while(!Files.exists(c.root.toPath().resolve("child-save"))){if(System.nanoTime()>until)throw new AssertionError("Parent barrier timed out");Thread.sleep(5);}old.save();return;}
    Path root=Files.createTempDirectory("network-catalog-host-");Context context=new Context(root.toFile(),0);NetworkCatalog c=fresh(context);
    check("New library has independent empty role arrays",c.subscriptions("entry").length()==0&&c.subscriptions("exit").length()==0);
    String same="https://fixture.invalid/same";
    JSONObject entry=c.addSubscription("entry","入口 A",same),exit=c.addSubscription("exit","出口 A",same);String eid=entry.getString("id"),xid=exit.getString("id");
    check("Same URL can belong independently to both roles",!eid.equals(xid)&&c.subscriptions().length()==1&&c.subscriptions("exit").length()==1);
    check("Legacy URL-hash lookup delegates to entry only",c.subscription(NativeNetwork.hash(same)).getString("id").equals(eid));
    rejects("Unknown role is rejected",()->c.addSubscription("other","Invalid",same));
    rejects("Empty name is rejected",()->c.addSubscription("entry"," ","https://fixture.invalid/empty"));
    NetworkCatalog.RefreshToken et=c.beginRefresh("entry",eid),xt=c.beginRefresh("exit",xid);
    check("Refresh token captures source, role, URL and address generation",et.id.equals(eid)&&et.role.equals("entry")&&et.url.equals(same)&&et.addressRevision==1&&!et.refreshToken.isEmpty());
    parsed(c,et,"Entry|A","entry-one",100);parsed(c,xt,"Exit|A","exit-one",200);
    check("Role caches cannot collide",cache(c,c.subscription("entry",eid)).equals("entry-one")&&cache(c,c.subscription("exit",xid)).equals("exit-one"));
    check("Successful parse records independent node metadata and timestamp",c.subscription(eid).optJSONArray("nodeDetails").getJSONObject(0).getString("fingerprint").equals("stable-configuration-fingerprint")&&c.subscription(eid).getLong("lastSuccessAt")==100);
    check("Cache files fit the SecretStore restricted namespace",c.subscription(eid).getString("cacheSlot").matches("[a-z-]+"));
    rejects("A completed token cannot publish twice",()->parsed(c,et,"Entry|dup","dup",300));

    NetworkCatalog.RefreshToken old=c.beginRefresh("entry",eid),newer=fresh(context).beginRefresh("entry",eid);
    rejects("An older refresh cannot overwrite a newer in-flight refresh",()->parsed(c,old,"Entry|old","old",999));
    rejects("An older failed callback cannot change the newer operation",()->c.failed(old,"timeout private-token",999));
    parsed(fresh(context),newer,"Entry|new","entry-new",50);
    final NetworkCatalog active=fresh(context);
    check("Operation identity wins despite wall-clock rollback",cache(active,active.subscription(eid)).equals("entry-new")&&active.subscription(eid).getLong("lastSuccessAt")==50);
    NetworkCatalog.RefreshToken rename=active.beginRefresh("entry",eid);fresh(context).editSubscription("entry",eid,"Renamed",same);parsed(active,rename,"Entry|kept","kept",60);
    check("Rename preserves refresh validity and latest display name",active.subscription(eid).getString("name").equals("Renamed"));
    NetworkCatalog.RefreshToken addressOld=active.beginRefresh("entry",eid);String alternate="https://fixture.invalid/alternate";JSONObject edited=fresh(context).editSubscription("entry",eid,"Edited",alternate);
    check("Address edit preserves stable ID",edited.getString("id").equals(eid));
    check("Address edit marks old cache stale instead of pretending success",edited.optBoolean("stale")&&active.cache(edited)==null&&good(active,edited).equals("kept"));
    rejects("Address edit invalidates an old success callback",()->parsed(active,addressOld,"Entry|old-url","old-url",500));
    rejects("Address edit invalidates an old failure callback",()->active.failed(addressOld,"timeout",500));
    NetworkCatalog.RefreshToken aba=fresh(context).beginRefresh("entry",eid);fresh(context).editSubscription("entry",eid,"A",same);fresh(context).editSubscription("entry",eid,"B",alternate);
    rejects("Address A-B-A cannot revalidate an old callback",()->parsed(active,aba,"Entry|ABA","aba",800));
    NetworkCatalog current=fresh(context);NetworkCatalog.RefreshToken failed=current.beginRefresh("entry",eid);current.failed(failed,"https://private.invalid/key?secret=x parser failed",900);
    check("Failure preserves good cache and sanitizes private error text",good(current,current.subscription(eid)).equals("kept")&&!current.subscription(eid).getString("lastError").contains("private")&&!current.subscription(eid).getString("lastError").contains("secret")&&current.subscription(eid).getLong("lastFailureAt")==900);
    check("Entry failures leave the exit source unchanged",cache(current,current.subscription("exit",xid)).equals("exit-one")&&current.subscription("exit",xid).getLong("lastSuccessAt")==200);
    NetworkCatalog stale=fresh(context);NetworkCatalog.RefreshToken deleted=current.beginRefresh("entry",eid);fresh(context).deleteSubscription("entry",eid);stale.save();
    check("A stale instance cannot resurrect a deleted subscription",fresh(context).subscription(eid)==null);
    rejects("Deleted source invalidates success callback",()->parsed(current,deleted,"Entry|deleted","deleted",1000));
    rejects("Deleted source invalidates failure callback",()->current.failed(deleted,"timeout",1000));
    JSONObject readded=fresh(context).addSubscription("entry","Explicit re-add",alternate);
    check("Explicit re-add creates a new identity rather than revalidating old tokens",!readded.getString("id").equals(eid));
    rejects("Re-add cannot let old source callback publish into the new source",()->parsed(current,deleted,"Entry|old-readd","old-readd",1200));

    NetworkCatalog fault=fresh(context);String freshId=readded.getString("id");parsed(fault,fault.beginRefresh("entry",freshId),"Entry|safe","safe-cache",1);
    NetworkCatalog.RefreshToken publication=fault.beginRefresh("entry",freshId);SecretStore.failCatalogOnce=true;
    rejects("Atomic catalogue publication failure is surfaced",()->parsed(fault,publication,"Entry|candidate","candidate-cache",2));
    NetworkCatalog afterFault=fresh(context);
    check("Failed pointer publication preserves previous bytes and nodes",cache(afterFault,afterFault.subscription(freshId)).equals("safe-cache")&&afterFault.subscription(freshId).getJSONArray("nodes").getString(0).equals("Entry|safe"));
    parsed(afterFault,publication,"Entry|retry","retry-cache",3);
    check("The same live operation may retry after publication failure",cache(afterFault,afterFault.subscription(freshId)).equals("retry-cache"));
    JSONArray detachedNames=names("Entry|detached"),detachedDetails=details("Entry|detached");afterFault.parsed(afterFault.beginRefresh("entry",freshId),detachedNames,detachedDetails,bytes("detached-cache"),4);detachedNames.put("Entry|extra");detachedDetails.getJSONObject(0).put("fingerprint","caller-mutated");
    check("Published names and identity details are detached from caller mutation",afterFault.subscription(freshId).getJSONArray("nodes").length()==1&&afterFault.subscription(freshId).getJSONArray("nodeDetails").getJSONObject(0).getString("fingerprint").equals("stable-configuration-fingerprint"));
    for(int i=0;i<6;i++)parsed(afterFault,afterFault.beginRefresh("entry",freshId),"Entry|bounded","bounded-"+i,10+i);
    String keepCurrent=afterFault.subscription(freshId).getString("cacheSlot"),keepPrevious=afterFault.subscription(freshId).getString("previousCacheSlot");
    check("Current and previous successful cache generations survive cleanup",new SecretStore(context).file(keepCurrent).exists()&&new SecretStore(context).file(keepPrevious).exists());
    int sourceFiles=0;for(File file:context.getNoBackupFilesDir().listFiles())if(file.getName().startsWith("source-pool-"))sourceFiles++;
    check("Repeated refreshes and failed publication do not accumulate unbounded blobs",sourceFiles<=4);
    rejects("An invalid empty parsed pool does not replace cached nodes",()->afterFault.parsed(afterFault.beginRefresh("entry",freshId),new JSONArray(),new JSONArray(),bytes("empty"),4));

    // Existing environments are never edited by catalogue migration, CRUD or refresh.
    JSONObject config=J.obj("subscriptionUrl","https://fixture.invalid/legacy","exitHost","127.0.0.1","exitPort",18080,"exitUser","fixture","exitPassword","fixture");
    Context profile=Profiles.context(context,7);SecretStore vault=new SecretStore(profile);vault.save(config);byte[] sealedBefore=vault.get("network");vault.put("subscription",bytes("legacy-provider"));vault.put("subscription-meta",bytes(J.obj("urlHash",NativeNetwork.hash(config.optString("subscriptionUrl")),"updatedAt",10).toString()));vault.put("subscription-ui",bytes(J.obj("urlHash",NativeNetwork.hash(config.optString("subscriptionUrl")),"nodes",J.arr("Entry|legacy")).toString()));vault.put("exit-baseline",bytes(J.obj("fingerprint",NetworkCatalog.exitId(config),"ip","203.0.113.10").toString()));Files.writeString(root.resolve("profiles.json"),J.arr(J.obj("slot",7,"created",true)).toString());
    NetworkCatalog legacy=fresh(context);String legacyId=NativeNetwork.hash(config.optString("subscriptionUrl")),manualId=NetworkCatalog.exitId(config);
    check("Legacy environment subscription and manual fixed exit are migrated",legacy.subscription(legacyId)!=null&&legacy.exit(manualId)!=null&&cache(legacy,legacy.subscription(legacyId)).equals("legacy-provider"));legacy.save();
    NetworkCatalog legacyStale=fresh(context);legacy.editSubscription("entry",legacyId,"Edited legacy","https://fixture.invalid/legacy-new");
    check("Editing a legacy address keeps a detached last-good provider",good(fresh(context),fresh(context).subscription(legacyId)).equals("legacy-provider"));
    check("Old environment URL imports resolve aliases without duplicating edited sources",fresh(context).subscription(legacyId).getString("url").equals("https://fixture.invalid/legacy-new"));
    legacy.deleteSubscription("entry",legacyId);legacyStale.save();
    check("Tombstones prevent collect from resurrecting a deleted legacy source",fresh(context).subscription(legacyId)==null);
    JSONObject changedManual=legacy.editExit(manualId,"New endpoint","","127.0.0.2",18080,"fixture","new-fixture");
    check("Manual exit edits retain stable identity and old fingerprint lookup",changedManual.getString("id").equals(manualId)&&fresh(context).exit(manualId).getString("host").equals("127.0.0.2"));
    check("Old environment verification cannot mark an edited endpoint as verified",fresh(context).exit(manualId).optString("verifiedIp").isEmpty());
    NetworkCatalog manualStale=fresh(context);legacy.deleteExit(manualId);manualStale.save();
    check("Deleted manual exits cannot return through environment import",fresh(context).exit(manualId)==null);
    JSONObject explicitManual=fresh(context).addExit("Re-add","","127.0.0.1",18080,"fixture","fixture");check("Explicitly re-added manual exit has a new identity",!explicitManual.getString("id").equals(manualId));
    check("All library operations preserved the environment's saved configuration bytes",Arrays.equals(sealedBefore,vault.get("network")));

    // Old fingerprints are references, not duplicates of a row's current endpoint.
    Context manualContext=new Context(Files.createTempDirectory("network-catalog-manual-alias-").toFile(),0);NetworkCatalog manual=fresh(manualContext);
    JSONObject endpointA=manual.addExit("A","","exit-a.invalid",1080,"fixture","fixture"),endpointB=manual.editExit(endpointA.getString("id"),"B","","exit-b.invalid",1080,"fixture","fixture");
    JSONObject newA=manual.addExit("New A","","exit-a.invalid",1080,"fixture","fixture");
    check("Re-adding an old manual endpoint creates the requested endpoint",newA.optString("host").equals("exit-a.invalid")&&manual.exits().length()==2);
    check("Occupied historical fingerprint IDs are not reused",!newA.getString("id").equals(endpointB.getString("id")));
    check("Adding the old endpoint preserves the edited endpoint and its label",fresh(manualContext).exit(endpointB.getString("id")).optString("host").equals("exit-b.invalid")&&fresh(manualContext).exit(endpointB.getString("id")).optString("name").equals("B"));
    check("Explicit selection of the new endpoint survives a fresh catalog load",fresh(manualContext).exit(newA.getString("id")).optString("host").equals("exit-a.invalid"));
    JSONObject repeated=manual.addExit("Renamed A","","exit-a.invalid",1080,"fixture","fixture");check("Actual current endpoint duplicates retain the new endpoint ID",repeated.getString("id").equals(newA.getString("id"))&&manual.exits().length()==2);
    rejects("Editing to another current endpoint still rejects duplicates",()->manual.editExit(newA.getString("id"),"Duplicate B","","exit-b.invalid",1080,"fixture","fixture"));
    manual.editExit(endpointB.getString("id"),"C","","exit-c.invalid",1080,"fixture","fixture");JSONObject reclaimed=manual.editExit(newA.getString("id"),"Reclaimed B","","exit-b.invalid",1080,"fixture","fixture");
    check("Editing to another row's historical endpoint is allowed",reclaimed.optString("host").equals("exit-b.invalid")&&fresh(manualContext).exit(endpointB.getString("id")).optString("host").equals("exit-c.invalid"));
    JSONObject colonOne=manual.addExit("Colon one","","colon.invalid",1080,"user:token","secret"),colonTwo=manual.addExit("Colon two","","colon.invalid",1080,"user","token:secret");
    check("Different credentials sharing a legacy colon-delimited hash stay distinct",!colonOne.getString("id").equals(colonTwo.getString("id"))&&colonTwo.optString("user").equals("user")&&colonTwo.optString("password").equals("token:secret"));

    // Validate before migration: normalization must not erase corrupt or future data.
    JSONObject empty=J.obj("schemaVersion",2,"subscriptions",new JSONArray(),"exitSubscriptions",new JSONArray(),"exits",new JSONArray(),"subscriptionTombstones",new JSONArray(),"exitTombstones",new JSONArray());
    JSONObject future=NetworkCatalog.copy(empty);future.put("schemaVersion",999);readOnly("Future catalog version",bytes(future.toString()));
    JSONObject fractional=NetworkCatalog.copy(empty);fractional.put("schemaVersion",2.5);readOnly("Fractional catalog version",bytes(fractional.toString()));
    JSONObject typed=NetworkCatalog.copy(empty);typed.put("subscriptions",J.obj("recoverableSource","keep"));readOnly("Wrong-typed source list",bytes(typed.toString()));
    JSONObject missing=NetworkCatalog.copy(empty);missing.remove("exits");readOnly("Missing current-schema list",bytes(missing.toString()));
    JSONObject nullRow=NetworkCatalog.copy(empty);nullRow.put("subscriptions",J.arr(JSONObject.NULL));readOnly("Null source row",bytes(nullRow.toString()));
    JSONObject duplicateRow=NetworkCatalog.copy(empty);JSONObject sourceRow=J.obj("id","fixture-source","url","https://fixture.invalid/source","nodes",new JSONArray());duplicateRow.put("subscriptions",J.arr(sourceRow,NetworkCatalog.copy(sourceRow)));readOnly("Duplicate source identity",bytes(duplicateRow.toString()));
    JSONObject wrongRole=NetworkCatalog.copy(empty);JSONObject roleRow=NetworkCatalog.copy(sourceRow);roleRow.put("role","exit");wrongRole.put("subscriptions",J.arr(roleRow));readOnly("Wrong-role source row",bytes(wrongRole.toString()));
    JSONObject wrongNodes=NetworkCatalog.copy(empty);JSONObject nodesRow=NetworkCatalog.copy(sourceRow);nodesRow.put("nodes",J.arr(123));wrongNodes.put("subscriptions",J.arr(nodesRow));readOnly("Wrong-typed node name",bytes(wrongNodes.toString()));
    JSONObject wrongPort=NetworkCatalog.copy(empty);wrongPort.put("exits",J.arr(J.obj("id","fixture-exit","host","exit.invalid","port","1080")));readOnly("Wrong-typed exit port",bytes(wrongPort.toString()));
    readOnly("Trailing document content",bytes(empty.toString()+" trailing"));readOnly("Malformed UTF-8",new byte[]{'{',(byte)0xc3,(byte)0x28,'}'});
    readOnly("Unsupported draft catalog format",bytes(J.obj("schema",2,"subscriptions",new JSONArray(),"exits",new JSONArray(),"exitSources",new JSONArray()).toString()));
    for(boolean versioned:new boolean[]{false,true}){
      Context oldContext=new Context(Files.createTempDirectory("network-catalog-valid-legacy-").toFile(),0);SecretStore oldVault=new SecretStore(oldContext);
      JSONObject oldSource=J.obj("id","legacy-source","name","Legacy","url","https://fixture.invalid/old","owner",0,"nodes",J.arr("Entry|legacy")),oldExit=J.obj("id","legacy-exit","host","exit.invalid","port",1080,"user","fixture","password","fixture");
      JSONObject document=J.obj("subscriptions",J.arr(oldSource),"exits",J.arr(oldExit));if(versioned)document.put("schemaVersion",1);byte[] original=bytes(document.toString());oldVault.put("network-catalog",original);oldVault.put(NetworkCatalog.cacheSlot(oldSource.getString("url")),bytes("legacy-private-provider"));
      NetworkCatalog migrated=fresh(oldContext);check("Valid legacy "+versioned+" loads without rewriting bytes",migrated.readError().isEmpty()&&Arrays.equals(original,oldVault.get("network-catalog")));
      migrated.addSubscription("entry","Another","https://fixture.invalid/another");NetworkCatalog reread=fresh(oldContext);check("Valid legacy "+versioned+" keeps source/exit identities on version-2 save",reread.data.optInt("schemaVersion")==2&&reread.subscription("legacy-source")!=null&&reread.exit("legacy-exit")!=null);
      check("Valid legacy "+versioned+" retains its private provider bytes",Arrays.equals(bytes("legacy-private-provider"),oldVault.get(NetworkCatalog.cacheSlot(oldSource.getString("url")))));
    }

    // Independent JVMs share only the real file lock and atomic on-disk fixture.
    List<Process> processes=new ArrayList<>();String java=new File(System.getProperty("java.home"),"bin/java").getAbsolutePath(),cp=System.getProperty("java.class.path");
    for(int i=0;i<4;i++)processes.add(new ProcessBuilder(java,"-cp",cp,NetworkCatalogHostTest.class.getName(),"child-add",root.toString(),"p"+i).inheritIO().start());
    for(Process p:processes)check("Independent catalogue writer process exits successfully",p.waitFor()==0);
    NetworkCatalog concurrent=fresh(context);int childRows=0;for(String role:new String[]{"entry","exit"})for(int i=0;i<concurrent.subscriptions(role).length();i++)if(concurrent.subscriptions(role).getJSONObject(i).getString("name").startsWith("Child "))childRows++;
    check("Cross-process file locks preserve all 64 distinct concurrent additions",childRows==64);
    Process oldProcess=new ProcessBuilder(java,"-cp",cp,NetworkCatalogHostTest.class.getName(),"child-old-save",root.toString()).inheritIO().start();long barrier=System.nanoTime()+10_000_000_000L;while(!Files.exists(root.resolve("child-loaded"))){if(System.nanoTime()>barrier)throw new AssertionError("Child barrier timed out");Thread.sleep(5);}fresh(context).deleteSubscription("exit",xid);Files.writeString(root.resolve("child-save"),"save");check("Stale child save completed",oldProcess.waitFor()==0);
    check("Cross-process stale save cannot resurrect another process's deletion",fresh(context).subscription("exit",xid)==null);
    Context corrupt=new Context(Files.createTempDirectory("network-catalog-corrupt-").toFile(),0);SecretStore corruptStore=new SecretStore(corrupt);corruptStore.put("network-catalog",bytes("invalid JSON"));NetworkCatalog unreadable=fresh(corrupt);rejects("Unreadable catalogue fails closed instead of replacing saved data",()->unreadable.addSubscription("entry","Do not overwrite","https://fixture.invalid/new"));check("Unreadable saved catalogue bytes remain intact",new String(corruptStore.get("network-catalog"),StandardCharsets.UTF_8).equals("invalid JSON"));
    JSONObject result=J.obj("passed",checks.length(),"total",checks.length(),"checks",checks,"actualAndroidExecution",false,"actualEncryptionExecution",false,"actualCrossProcessFileLocks",true,"scope","Production NetworkCatalog with host Context/SecretStore fixtures; actual file locks, immutable cache generations, atomic pointer publication, migration and independent JVM races. Android keystore and public proxy connectivity are not tested.");
    System.out.println(result.toString(2));
  }
}
