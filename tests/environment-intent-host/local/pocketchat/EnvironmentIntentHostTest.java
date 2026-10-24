package local.pocketchat;
import android.content.Context;import org.json.*;import java.io.*;import java.nio.file.*;import java.nio.charset.StandardCharsets;import java.util.*;import java.util.concurrent.*;

/** Runs production staged intent/CAS recovery with plain-file repository doubles. */
public final class EnvironmentIntentHostTest {
  static final JSONArray checks=new JSONArray();static boolean crossProcess;
  interface Work{void run()throws Exception;}
  static void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));if(!pass)throw new AssertionError(name);}
  static void rejects(String name,Work work)throws Exception{boolean rejected=false;try{work.run();}catch(Exception expected){rejected=true;}check(name,rejected);}
  static Context fresh()throws Exception{Context c=new Context(Files.createTempDirectory("environment-intent-").toFile(),2);ProfileCatalog.create(c,3);c.getSharedPreferences("chat",0).values.put("proxy","socks://active.example:1080");new EnvironmentSpecRepository(c).load();return c;}
  static JSONObject external(String host){return J.obj("proxy","socks://"+host+":1080","requireExternalVpn",true);}
  static EnvironmentSpec.Identity identity(Context c)throws Exception{return ProfileCatalog.get(c).identity(c.slot);}
  static JSONObject pending(Context c)throws Exception{return NetworkChanges.pendingStrict(c);}
  static String save(Context c,String host)throws Exception{return EnvironmentSpecRuntime.saveNetworkIntent(c,identity(c),"external",external(host),NetworkChanges.hash(c),new JSONObject());}
  static EnvironmentSpec model(Context c)throws Exception{return new EnvironmentSpecRepository(c).load();}
  static String modelProxy(Context c)throws Exception{return model(c).desired().network.credentialRevision;}
  static void browser(Context c,String text)throws Exception{EnvironmentSpec value=model(c);JSONObject browser=value.desired().browser();browser.put("fixtureBrowser",text);new SecretStore(c).put("environment-spec",value.withDesired(value.desiredRevision,new EnvironmentSpec.Configuration(browser,value.desired().network)).bytes());}
  static String snapshot(){return "pending-entry-subscription-"+"abcdefghijklmnopabcdefghijklmnop";}
  static void addPrivateSnapshot(Context c)throws Exception{JSONObject row=pending(c);row.put("entrySnapshot",snapshot());new SecretStore(c).put(snapshot(),"prior private subscription".getBytes(StandardCharsets.UTF_8));new SecretStore(c).put("pending-network",row.toString().getBytes(StandardCharsets.UTF_8));}

  static void protocolValidation(){
    check("Production validator accepts documented HTTP proxy",MainActivity.validProxy("http://proxy.synthetic.example:8080"));
    check("Production validator accepts documented HTTPS proxy",MainActivity.validProxy("https://proxy.synthetic.example:8443"));
    check("Production validator accepts documented SOCKS proxy",MainActivity.validProxy("socks://proxy.synthetic.example:1080"));
    check("Production validator rejects unsupported socks5 alias",!MainActivity.validProxy("socks5://proxy.synthetic.example:1080"));
    check("Production validator rejects proxy credentials",!MainActivity.validProxy("socks://user:password@proxy.synthetic.example:1080"));
    check("Production validator rejects proxy paths",!MainActivity.validProxy("socks://proxy.synthetic.example:1080/path"));
    check("Production validator rejects proxy query",!MainActivity.validProxy("socks://proxy.synthetic.example:1080?query=1"));
    check("Production validator rejects proxy fragments",!MainActivity.validProxy("socks://proxy.synthetic.example:1080#fragment"));
    check("Production validator rejects out of range ports",!MainActivity.validProxy("socks://proxy.synthetic.example:0")&&!MainActivity.validProxy("socks://proxy.synthetic.example:65536"));
    check("Production validator rejects a missing host",!MainActivity.validProxy("socks://:1080"));
  }

  static void successAndFailure()throws Exception{
    Context c=fresh();EnvironmentSpec before=model(c);browser(c,"new browser edit");String ready=save(c,"queued.example");JSONObject record=pending(c);
    check("Successful save commits a ready intent",ready.equals(record.toString())&&"ready".equals(NetworkChanges.intent(record).optString("state")));
    check("Ready intent retains full environment identity",NetworkChanges.identityMatches(record,identity(c).json()));
    check("Ready intent has a unique receipt and no recovery predecessor",NetworkChanges.intent(record).optString("id").matches("[0-9a-f]{32}")&&!record.has("previousPending"));
    check("Model mirrors committed pending route",modelProxy(c).equals(NativeNetwork.hash("socks://queued.example:1080")));
    check("Network save preserves latest browser edit",model(c).desired().browser().optString("fixtureBrowser").equals("new browser edit"));
    check("Saving desired does not acknowledge runtime application",model(c).appliedRevision==before.appliedRevision&&model(c).observedRevision==before.observedRevision);
    addPrivateSnapshot(c);String prior=pending(c).toString();EnvironmentSpecRepository.failUpdate=true;
    rejects("Model publication failure is reported after intent staging",()->save(c,"rejected.example"));
    check("Failed mirror restores exact previous pending receipt",pending(c).toString().equals(prior));
    check("Failed mirror preserves previous private source snapshot",Arrays.equals(new SecretStore(c).get(snapshot()),"prior private subscription".getBytes(StandardCharsets.UTF_8)));
    check("Failed mirror reconciles model to restored prior intent",modelProxy(c).equals(NativeNetwork.hash("socks://queued.example:1080")));
    check("Failed mirror still preserves browser JSON",model(c).desired().browser().optString("fixtureBrowser").equals("new browser edit"));
    Context absent=fresh();EnvironmentSpecRepository.failUpdate=true;rejects("Failed first model save is reported",()->save(absent,"rejected.example"));
    check("Failed first save leaves no drainable pending intent",pending(absent).length()==0);
    check("Failed first save keeps active route as desired",modelProxy(absent).equals(NativeNetwork.hash("socks://active.example:1080")));
    SecretStore.failSlotOnce="pending-network";String retained=pending(c).toString();rejects("Intent publication failure is reported",()->save(c,"unpublished.example"));
    check("Failed intent publication retains original pending",pending(c).toString().equals(retained));
  }
  static void newerAndBrowserCas()throws Exception{
    Context c=fresh();save(c,"older.example");EnvironmentSpecRepository.beforeUpdate=()->{try{NetworkChanges.save(c,"external",external("newer.example"),NetworkChanges.hash(c));EnvironmentSpecRepository.failUpdate=true;}catch(Exception e){throw new RuntimeException(e);}};
    rejects("Older model failure cannot succeed over a newer publication",()->save(c,"failed.example"));
    check("Exact rollback never clears a newer pending intent",pending(c).getJSONObject("config").optString("proxy").contains("newer.example"));
    check("Recovery mirrors newer authoritative pending",modelProxy(c).equals(NativeNetwork.hash("socks://newer.example:1080")));
    String old=pending(c).toString();NetworkChanges.save(c,"external",external("newest.example"),NetworkChanges.hash(c));boolean removed=EnvironmentSpecRuntime.cancelNetworkIntent(c,identity(c),old);
    check("Cancellation CAS refuses a superseded receipt",!removed&&pending(c).getJSONObject("config").optString("proxy").contains("newest.example"));
    check("Superseded cancellation aligns model with newest pending",modelProxy(c).equals(NativeNetwork.hash("socks://newest.example:1080")));
    int updates=EnvironmentSpecRepository.updates;EnvironmentSpecRepository.beforeUpdate=()->{try{browser(c,"concurrent browser");}catch(Exception e){throw new RuntimeException(e);}};save(c,"cas.example");
    check("Network mirror retries a real desired-revision CAS conflict",EnvironmentSpecRepository.updates>=updates+2);
    check("CAS retry preserves concurrent browser edit",model(c).desired().browser().optString("fixtureBrowser").equals("concurrent browser"));
    check("CAS retry commits the requested network",modelProxy(c).equals(NativeNetwork.hash("socks://cas.example:1080")));
  }
  static void interruptedStagesAndCancel()throws Exception{
    Context c=fresh();save(c,"prior.example");addPrivateSnapshot(c);String prior=pending(c).toString();EnvironmentSpec.Identity id=identity(c);NetworkChanges.IntentGuard guard=()->EnvironmentSpecRuntime.requireIdentity(c,id);
    NetworkChanges.IntentReceipt stage=NetworkChanges.stageIntent(c,"external",external("interrupted.example"),NetworkChanges.hash(c),new JSONObject(),id.json(),guard);
    check("Staged intent retains recovery predecessor",pending(c).getJSONObject("previousPending").toString().equals(prior));
    check("Private predecessor snapshot survives staging",new SecretStore(c).get(snapshot())!=null);
    EnvironmentSpecRuntime.desireNetwork(c,id,"external",external("interrupted.example"));browser(c,"edited during interruption");
    EnvironmentSpecRuntime.Reconciled recovered=EnvironmentSpecRuntime.reconcileNetwork(c,id,"");
    check("Crash before ready restores previous committed intent",recovered.pending.toString().equals(prior));
    check("Crash after model write restores desired prior network",modelProxy(c).equals(NativeNetwork.hash("socks://prior.example:1080")));
    check("Crash recovery preserves browser edit",model(c).desired().browser().optString("fixtureBrowser").equals("edited during interruption"));
    check("Recovered predecessor payload remains readable",new SecretStore(c).get(snapshot())!=null);
    Context first=fresh();EnvironmentSpec.Identity firstId=identity(first);NetworkChanges.stageIntent(first,"external",external("unacknowledged.example"),NetworkChanges.hash(first),new JSONObject(),firstId.json(),()->EnvironmentSpecRuntime.requireIdentity(first,firstId));EnvironmentSpecRuntime.desireNetwork(first,firstId,"external",external("unacknowledged.example"));EnvironmentSpecRuntime.reconcileNetwork(first,firstId,"");
    check("Interrupted first stage is never considered a committed candidate",pending(first).length()==0&&modelProxy(first).equals(NativeNetwork.hash("socks://active.example:1080")));
    String ready=save(c,"cancel.example");browser(c,"browser retained on cancel");EnvironmentSpecRepository.failUpdate=true;
    rejects("Cancellation model failure is reported without resurrecting intent",()->EnvironmentSpecRuntime.cancelNetworkIntent(c,id,ready));
    check("Cancellation remains authoritative despite model failure",pending(c).length()==0);
    EnvironmentSpecRuntime.reconcileNetwork(c,id,"");
    check("Startup repairs crash or failure after candidate removal",modelProxy(c).equals(NativeNetwork.hash("socks://active.example:1080")));
    check("Cancellation recovery preserves browser JSON",model(c).desired().browser().optString("fixtureBrowser").equals("browser retained on cancel"));
    save(c,"cleanup.example");check("Committed replacement releases predecessor source snapshot",new SecretStore(c).get(snapshot())==null);
  }
  static void identityAndStrictReads()throws Exception{
    Context c=fresh();String oldSnapshot=save(c,"old-environment.example");EnvironmentSpec.Identity old=identity(c);ProfileCatalog.create(c,old.generation);new SecretStore(c).remove("environment-spec");NetworkChanges.save(c,"external",external("new-environment.example"),NetworkChanges.hash(c));String fresh=pending(c).toString();
    rejects("Deleted/reused UUID rejects old save even at equal generation",()->EnvironmentSpecRuntime.saveNetworkIntent(c,old,"external",external("stale.example"),NetworkChanges.hash(c),new JSONObject()));
    rejects("Deleted/reused UUID rejects old cancellation",()->EnvironmentSpecRuntime.cancelNetworkIntent(c,old,oldSnapshot));
    rejects("Deleted/reused UUID rejects old model reconciliation",()->EnvironmentSpecRuntime.reconcileNetwork(c,old,""));
    check("Old callbacks preserve replacement environment intent",pending(c).toString().equals(fresh));
    EnvironmentSpecRuntime.reconcileNetwork(c,identity(c),"");check("Replacement environment receives only its own desired route",modelProxy(c).equals(NativeNetwork.hash("socks://new-environment.example:1080")));
    Context stale=fresh();String staleReady=save(stale,"deleted.example");ProfileCatalog.create(stale,4);new SecretStore(stale).remove("environment-spec");EnvironmentSpecRuntime.reconcileNetwork(stale,identity(stale),"");
    check("Recovery discards a committed intent owned by deleted identity",pending(stale).length()==0&&modelProxy(stale).equals(NativeNetwork.hash("socks://active.example:1080")));
    Context corrupt=fresh();byte[] invalid="{broken".getBytes(StandardCharsets.UTF_8);new SecretStore(corrupt).put("pending-network",invalid);rejects("Malformed authoritative pending blocks recovery",()->EnvironmentSpecRuntime.reconcileNetwork(corrupt,identity(corrupt),""));
    check("Malformed pending bytes are retained rather than treated as absent",Arrays.equals(invalid,new SecretStore(corrupt).get("pending-network")));
    Context legacy=fresh();NetworkChanges.save(legacy,"external",external("legacy.example"),NetworkChanges.hash(legacy));String legacyBytes=pending(legacy).toString();EnvironmentSpecRuntime.reconcileNetwork(legacy,identity(legacy),"");
    check("Legacy v24 pending remains committed and byte stable",pending(legacy).toString().equals(legacyBytes)&&NetworkChanges.intent(pending(legacy))==null);
    check("Legacy pending is mirrored without resetting browser/model applied state",modelProxy(legacy).equals(NativeNetwork.hash("socks://legacy.example:1080"))&&model(legacy).appliedRevision==0);
    JSONObject future=pending(legacy);future.put("environmentIntent",J.obj("schema",99,"id","a".repeat(32),"identity",identity(legacy).json(),"state","ready"));new SecretStore(legacy).put("pending-network",future.toString().getBytes(StandardCharsets.UTF_8));String unchanged=pending(legacy).toString();rejects("Future intent schema blocks recovery",()->EnvironmentSpecRuntime.reconcileNetwork(legacy,identity(legacy),""));check("Future intent schema is not overwritten",pending(legacy).toString().equals(unchanged));
  }
  static void commitAcknowledgement()throws Exception{
    Context c=fresh();save(c,"predecessor.example");browser(c,"browser through commit fault");SecretStore.resetOutcomeFaults();SecretStore.failReadyAfterWrite=true;SecretStore.failReadsAfterReady=1;SecretStore.failRollbackOnce=true;
    String ready=save(c,"committed.example");
    check("Ready commit with lost ack and failed withdrawal returns verified success",ready.equals(pending(c).toString()));
    check("Fault control actually throws after ready bytes commit",SecretStore.readyWriteFailures==1);
    check("Fault control actually fails exact predecessor withdrawal",SecretStore.rollbackFailures==1&&SecretStore.readFailures==1);
    check("Verified commit retains matching desired network",modelProxy(c).equals(NativeNetwork.hash("socks://committed.example:1080")));
    check("Verified commit preserves current browser JSON",model(c).desired().browser().optString("fixtureBrowser").equals("browser through commit fault"));
    check("Verified durable intent does not claim runtime application",model(c).appliedRevision==0&&model(c).observedRevision==0);
    SecretStore.resetOutcomeFaults();SecretStore.failReadyAfterWrite=true;SecretStore.failReadsAfterReady=3;boolean uncertain=false;
    try{save(c,"unknown.example");}catch(EnvironmentSpecRuntime.IntentRecoveryRequired required){uncertain=true;}
    check("Unreadable commit and withdrawal is classified as uncertain",uncertain);
    check("Unknown outcome control prevents all three readback attempts",SecretStore.readFailures==3&&SecretStore.readyWriteFailures==1);
    SecretStore.resetOutcomeFaults();String retained=pending(c).toString();EnvironmentSpecRuntime.Reconciled recovered=EnvironmentSpecRuntime.reconcileNetwork(c,identity(c),"");
    check("Unknown outcome preserves authoritative committed receipt",retained.equals(recovered.pending.toString()));
    check("Recovered unknown outcome verifies matching model",modelProxy(c).equals(NativeNetwork.hash("socks://unknown.example:1080")));
  }
  static void cacheInvalidation()throws Exception{
    Context c=fresh();save(c,"cached.example");EnvironmentSpec.Identity id=identity(c);EnvironmentSpecRuntime.Reconciled initial=EnvironmentSpecRuntime.reconcileNetwork(c,id,"");int updates=EnvironmentSpecRepository.updates;
    EnvironmentSpecRuntime.Reconciled unchanged=EnvironmentSpecRuntime.reconcileNetwork(c,id,initial.proof);
    check("Confirmed unchanged authority and model bytes skip model writer",unchanged.spec==null&&EnvironmentSpecRepository.updates==updates);
    EnvironmentSpec current=model(c);JSONObject browser=current.desired().browser();browser.put("fixtureBrowser","cross-instance browser");EnvironmentSpec.NetworkBinding foreign=EnvironmentSpecRuntime.binding(id,"external",new JSONObject(),"socks://foreign.example:1080");new EnvironmentSpecRepository(c).updateDesired(id,current.desiredRevision,new EnvironmentSpec.Configuration(browser,foreign));EnvironmentSpecRuntime.Reconciled aligned=EnvironmentSpecRuntime.reconcileNetwork(c,id,initial.proof);
    check("Cross-instance network model mutation invalidates cache",aligned.spec!=null&&modelProxy(c).equals(NativeNetwork.hash("socks://cached.example:1080")));
    check("Cross-instance cache repair preserves latest browser",model(c).desired().browser().optString("fixtureBrowser").equals("cross-instance browser"));
    byte[] valid=model(c).bytes();JSONObject future=model(c).json();future.put("schema",99);new SecretStore(c).put("environment-spec",future.toString().getBytes(StandardCharsets.UTF_8));byte[] futureBytes=new SecretStore(c).get("environment-spec");
    rejects("Future model schema invalidates previously confirmed idle cache",()->EnvironmentSpecRuntime.reconcileNetwork(c,id,aligned.proof));
    check("Future model bytes remain intact after cached recovery attempt",Arrays.equals(futureBytes,new SecretStore(c).get("environment-spec")));
    byte[] corrupt="{invalid model".getBytes(StandardCharsets.UTF_8);new SecretStore(c).put("environment-spec",corrupt);
    rejects("Corrupt model invalidates previously confirmed idle cache",()->EnvironmentSpecRuntime.reconcileNetwork(c,id,aligned.proof));
    check("Corrupt model bytes remain intact after cache miss",Arrays.equals(corrupt,new SecretStore(c).get("environment-spec")));
    new SecretStore(c).put("environment-spec",valid);EnvironmentSpecRuntime.Reconciled repaired=EnvironmentSpecRuntime.reconcileNetwork(c,id,aligned.proof);
    check("Restored exact model bytes permit the verified idle cache",repaired.spec==null);
    String prior=pending(c).toString();EnvironmentSpecRuntime.cancelNetworkIntent(c,id,prior);EnvironmentSpecRuntime.Reconciled cancelled=EnvironmentSpecRuntime.reconcileNetwork(c,id,aligned.proof);
    check("Cancellation invalidates old authority cache",cancelled.spec!=null&&cancelled.pending.length()==0&&modelProxy(c).equals(NativeNetwork.hash("socks://active.example:1080")));
    NetworkChanges.save(c,"external",external("replacement.example"),NetworkChanges.hash(c));EnvironmentSpecRuntime.Reconciled replaced=EnvironmentSpecRuntime.reconcileNetwork(c,id,cancelled.proof);
    check("Cross-instance pending replacement invalidates authority cache",replaced.spec!=null&&modelProxy(c).equals(NativeNetwork.hash("socks://replacement.example:1080")));
    ProfileCatalog.create(c,id.generation+1);new SecretStore(c).remove("environment-spec");rejects("Deleted identity cannot reuse confirmed cache",()->EnvironmentSpecRuntime.reconcileNetwork(c,id,replaced.proof));EnvironmentSpecRuntime.Reconciled reused=EnvironmentSpecRuntime.reconcileNetwork(c,identity(c),replaced.proof);
    check("Reused UUID and generation force fresh model reconciliation",reused.spec!=null&&!reused.proof.equals(replaced.proof));
  }
  static boolean reuse(Context c,EnvironmentSpec.Identity expected,String receipt)throws Exception{
    JSONObject row=new JSONObject(receipt);return EnvironmentSpecRuntime.reuseNetworkIntent(c,expected,row.getString("action"),row.getJSONObject("config"),row.getString("baseline"),receipt);
  }
  static void reuseStableReceipt()throws Exception{
    Context c=fresh();SecretStore vault=new SecretStore(c);String receipt=save(c,"reuse.example");EnvironmentSpec.Identity id=identity(c);JSONObject before=pending(c);
    byte[] pendingBytes=vault.get("pending-network"),modelBytes=vault.get("environment-spec");long writes=SecretStore.putCalls.get(),removes=SecretStore.removeCalls.get();int updates=EnvironmentSpecRepository.updates;boolean accepted=true;
    for(int i=0;i<30;i++)accepted&=reuse(c,id,receipt);
    check("Repeated production reuse accepts one committed exact receipt",accepted);
    check("Repeated reuse preserves exact pending and model bytes",Arrays.equals(pendingBytes,vault.get("pending-network"))&&Arrays.equals(modelBytes,vault.get("environment-spec")));
    check("Repeated reuse preserves original intent ID and savedAt",NetworkChanges.intent(before).getString("id").equals(NetworkChanges.intent(pending(c)).getString("id"))&&before.getLong("savedAt")==pending(c).getLong("savedAt"));
    check("Repeated reuse performs zero store puts removals or model updates",writes==SecretStore.putCalls.get()&&removes==SecretStore.removeCalls.get()&&updates==EnvironmentSpecRepository.updates);
    check("Reuse never acknowledges runtime application",model(c).appliedRevision==0&&model(c).observedRevision==0);

    // Hold the production reuse inside its first authoritative read while a
    // different thread updates browser JSON; no model hook or reuse is mocked.
    CountDownLatch readEntered=new CountDownLatch(1);java.util.concurrent.atomic.AtomicBoolean productionReadHeld=new java.util.concurrent.atomic.AtomicBoolean();CompletableFuture<Void> edited=new CompletableFuture<>();Thread writer=new Thread(()->{try{if(!readEntered.await(10,TimeUnit.SECONDS))throw new IOException("Reuse read barrier missing");for(int i=0;i<20;i++)browser(c,"parallel browser "+i);edited.complete(null);}catch(Throwable error){edited.completeExceptionally(error);}},"intent-reuse-browser-writer");
    SecretStore.beforePendingRead=()->{productionReadHeld.set(true);readEntered.countDown();try{edited.get(10,TimeUnit.SECONDS);}catch(Exception failure){throw new IllegalStateException("Browser writer barrier failed",failure);}};
    writes=SecretStore.putCalls.get();removes=SecretStore.removeCalls.get();updates=EnvironmentSpecRepository.updates;writer.start();accepted=true;try{for(int i=0;i<60;i++)accepted&=reuse(c,id,receipt);}finally{SecretStore.beforePendingRead=null;readEntered.countDown();}edited.get(10,TimeUnit.SECONDS);writer.join(10000);
    check("Independent browser writes occur inside a production reuse read",productionReadHeld.get()&&edited.isDone()&&!edited.isCompletedExceptionally());
    check("Reuse and concurrent browser edits retain the original network receipt",accepted&&receipt.equals(pending(c).toString())&&modelProxy(c).equals(NativeNetwork.hash("socks://reuse.example:1080")));
    check("Concurrent browser writer is the only source of model writes",SecretStore.putCalls.get()==writes+20&&SecretStore.removeCalls.get()==removes&&EnvironmentSpecRepository.updates==updates&&model(c).desired().browser().optString("fixtureBrowser").equals("parallel browser 19"));

    Context legacy=fresh();NetworkChanges.save(legacy,"external",external("reuse-legacy.example"),NetworkChanges.hash(legacy));String legacyReceipt=pending(legacy).toString();byte[] legacyModel=new SecretStore(legacy).get("environment-spec");writes=SecretStore.putCalls.get();removes=SecretStore.removeCalls.get();
    check("Legacy committed candidate can be reused without inventing an intent",reuse(legacy,identity(legacy),legacyReceipt)&&NetworkChanges.intent(pending(legacy))==null&&legacyReceipt.equals(pending(legacy).toString()));
    check("Legacy reuse performs no migration or model writes",writes==SecretStore.putCalls.get()&&removes==SecretStore.removeCalls.get()&&Arrays.equals(legacyModel,new SecretStore(legacy).get("environment-spec")));
  }
  static void reuseRejectsStaleOrInvalid()throws Exception{
    Context c=fresh();SecretStore vault=new SecretStore(c);EnvironmentSpec.Identity id=identity(c);String old=save(c,"reuse-old.example"),fresh=save(c,"reuse-new.example");long writes=SecretStore.putCalls.get(),removes=SecretStore.removeCalls.get();
    check("Superseded reuse returns false without replacing the newer candidate",!reuse(c,id,old)&&fresh.equals(pending(c).toString()));
    check("Superseded reuse makes no store mutation",writes==SecretStore.putCalls.get()&&removes==SecretStore.removeCalls.get());
    JSONObject current=pending(c);rejects("Reuse refuses an action not bound by the saved receipt",()->EnvironmentSpecRuntime.reuseNetworkIntent(c,id,"apply",current.getJSONObject("config"),current.getString("baseline"),fresh));
    rejects("Reuse refuses different caller candidate bytes",()->EnvironmentSpecRuntime.reuseNetworkIntent(c,id,"external",external("not-saved.example"),current.getString("baseline"),fresh));
    c.getSharedPreferences("chat",0).values.put("proxy","socks://changed-active.example:1080");rejects("Reuse rejects a changed active baseline",()->reuse(c,id,fresh));
    check("Rejected reuse preserves the saved candidate and makes no writes",fresh.equals(pending(c).toString())&&writes==SecretStore.putCalls.get()&&removes==SecretStore.removeCalls.get());

    Context replaced=fresh();String removedReceipt=save(replaced,"removed.example");EnvironmentSpec.Identity removed=identity(replaced);ProfileCatalog.create(replaced,removed.generation);new SecretStore(replaced).remove("environment-spec");String replacement=save(replaced,"replacement.example");writes=SecretStore.putCalls.get();removes=SecretStore.removeCalls.get();
    rejects("Reuse rejects an old UUID even when the generation is equal",()->reuse(replaced,removed,removedReceipt));
    check("Old identity reuse does not touch replacement pending or model",replacement.equals(pending(replaced).toString())&&modelProxy(replaced).equals(NativeNetwork.hash("socks://replacement.example:1080"))&&writes==SecretStore.putCalls.get()&&removes==SecretStore.removeCalls.get());

    Context staged=fresh();save(staged,"predecessor.example");EnvironmentSpec.Identity stagedId=identity(staged);NetworkChanges.stageIntent(staged,"external",external("unready.example"),NetworkChanges.hash(staged),new JSONObject(),stagedId.json(),()->EnvironmentSpecRuntime.requireIdentity(staged,stagedId));String unready=pending(staged).toString();byte[] stagedModel=new SecretStore(staged).get("environment-spec");writes=SecretStore.putCalls.get();removes=SecretStore.removeCalls.get();
    rejects("Reuse cannot promote or recover a staged intent",()->reuse(staged,stagedId,unready));
    check("Rejected staged reuse preserves predecessor record and model bytes",unready.equals(pending(staged).toString())&&Arrays.equals(stagedModel,new SecretStore(staged).get("environment-spec"))&&writes==SecretStore.putCalls.get()&&removes==SecretStore.removeCalls.get());

    Context corrupt=fresh();String valid=save(corrupt,"valid.example");SecretStore corruptStore=new SecretStore(corrupt);byte[] malformed="{broken reuse record".getBytes(StandardCharsets.UTF_8);corruptStore.put("pending-network",malformed);writes=SecretStore.putCalls.get();removes=SecretStore.removeCalls.get();
    rejects("Reuse distinguishes unreadable pending from a replaced receipt",()->reuse(corrupt,identity(corrupt),valid));
    check("Malformed reuse record remains byte exact with no cleanup",Arrays.equals(malformed,corruptStore.get("pending-network"))&&writes==SecretStore.putCalls.get()&&removes==SecretStore.removeCalls.get());
    JSONObject future=new JSONObject(valid);future.getJSONObject("environmentIntent").put("schema",99);corruptStore.put("pending-network",future.toString().getBytes(StandardCharsets.UTF_8));String futureReceipt=future.toString();writes=SecretStore.putCalls.get();removes=SecretStore.removeCalls.get();
    rejects("Reuse rejects a future intent schema",()->reuse(corrupt,identity(corrupt),futureReceipt));
    check("Future intent reuse preserves all authoritative bytes",futureReceipt.equals(pending(corrupt).toString())&&writes==SecretStore.putCalls.get()&&removes==SecretStore.removeCalls.get());
    JSONObject invalid=new JSONObject(valid);invalid.getJSONObject("config").put("proxy","socks://user:password@invalid.example:1080");corruptStore.put("pending-network",invalid.toString().getBytes(StandardCharsets.UTF_8));String invalidReceipt=invalid.toString();writes=SecretStore.putCalls.get();removes=SecretStore.removeCalls.get();
    rejects("Reuse validates saved proxy syntax rather than trusting ready state",()->reuse(corrupt,identity(corrupt),invalidReceipt));
    check("Invalid saved proxy remains available for reediting without writes",invalidReceipt.equals(pending(corrupt).toString())&&writes==SecretStore.putCalls.get()&&removes==SecretStore.removeCalls.get());
  }
  static void parseSource(NetworkCatalog catalog,String role,String id,String payload,String name,String key,String type)throws Exception{
    catalog.parsed(catalog.beginRefresh(role,id),J.arr(name),J.arr(J.obj("name",name,"configFingerprint",key,"configFingerprintVersion",1,"type",type)),payload.getBytes(StandardCharsets.UTF_8),System.currentTimeMillis());
  }
  static void reusePrivateSnapshots()throws Exception{
    Context c=fresh();SecretStore vault=new SecretStore(c);NetworkCatalog catalog=new NetworkCatalog(c);String entryKey=NativeNetwork.hash("reuse-entry"),exitKey=NativeNetwork.hash("reuse-exit");
    JSONObject entry=catalog.addSubscription("entry","Reuse entry","https://fixture.invalid/reuse-entry"),exit=catalog.addSubscription("exit","Reuse exit","https://fixture.invalid/reuse-exit");
    parseSource(catalog,"entry",entry.getString("id"),"entry-reuse-v1","Entry|A",entryKey,"VLESS");parseSource(catalog,"exit",exit.getString("id"),"exit-reuse-v1","Exit|Fixed",exitKey,"Socks5");
    JSONObject candidate=J.obj("subscriptionUrl",entry.getString("url"),"entrySubscriptionId",entry.getString("id"),"entryMode","manual","entry","Entry|A","entryNodeKey",entryKey,"entryPool",J.arr("Entry|A"),"exitSource","subscription","exitSubscriptionId",exit.getString("id"),"exitSubscriptionUrl",exit.getString("url"),"exitNodeName","Exit|Fixed","exitNodeKey",exitKey);
    NetworkChanges.validate(c,"apply",candidate);String receipt=EnvironmentSpecRuntime.saveNetworkIntent(c,identity(c),"apply",candidate,NetworkChanges.hash(c),new JSONObject());JSONObject record=pending(c);String entrySlot=record.getString("entrySnapshot"),exitSlot=record.getString("exitSnapshot");byte[] entryBytes=vault.get(entrySlot),exitBytes=vault.get(exitSlot),modelBytes=vault.get("environment-spec");long writes=SecretStore.putCalls.get(),removes=SecretStore.removeCalls.get();boolean accepted=true;
    for(int i=0;i<12;i++)accepted&=reuse(c,identity(c),receipt);
    check("Internal reuse validates both saved private provider snapshots",accepted&&receipt.equals(pending(c).toString())&&Arrays.equals(entryBytes,vault.get(entrySlot))&&Arrays.equals(exitBytes,vault.get(exitSlot)));
    check("Internal reuse does not rewrite source snapshots pending or model",writes==SecretStore.putCalls.get()&&removes==SecretStore.removeCalls.get()&&Arrays.equals(modelBytes,vault.get("environment-spec")));
    catalog.editSubscription("entry",entry.getString("id"),"Renamed while waiting",entry.getString("url"));JSONObject supplied=new JSONObject(record.getJSONObject("config").toString());String suppliedBefore=supplied.toString();writes=SecretStore.putCalls.get();removes=SecretStore.removeCalls.get();
    rejects("Reuse rejects source normalization changes instead of silently resaving",()->EnvironmentSpecRuntime.reuseNetworkIntent(c,identity(c),"apply",supplied,record.getString("baseline"),receipt));
    check("Rejected normalization mutates neither caller config nor persisted receipt",suppliedBefore.equals(supplied.toString())&&receipt.equals(pending(c).toString())&&writes==SecretStore.putCalls.get()&&removes==SecretStore.removeCalls.get());catalog.editSubscription("entry",entry.getString("id"),"Reuse entry",entry.getString("url"));
    byte[] altered="private entry changed".getBytes(StandardCharsets.UTF_8);vault.put(entrySlot,altered);writes=SecretStore.putCalls.get();removes=SecretStore.removeCalls.get();
    rejects("Reuse rejects altered retained private provider bytes",()->reuse(c,identity(c),receipt));
    check("Private snapshot rejection does not replace or clean the user's candidate",receipt.equals(pending(c).toString())&&Arrays.equals(altered,vault.get(entrySlot))&&Arrays.equals(exitBytes,vault.get(exitSlot))&&writes==SecretStore.putCalls.get()&&removes==SecretStore.removeCalls.get());
    vault.put(entrySlot,entryBytes);parseSource(catalog,"entry",entry.getString("id"),"entry-reuse-v2","Entry|A",entryKey,"VLESS");writes=SecretStore.putCalls.get();removes=SecretStore.removeCalls.get();
    rejects("Reuse rejects changed shared payload even when the chosen node key is stable",()->reuse(c,identity(c),receipt));
    check("Shared payload mismatch preserves saved intent and original private bytes",receipt.equals(pending(c).toString())&&Arrays.equals(entryBytes,vault.get(entrySlot))&&Arrays.equals(exitBytes,vault.get(exitSlot))&&writes==SecretStore.putCalls.get()&&removes==SecretStore.removeCalls.get());
  }
  static void lease()throws Exception{
    Context c=fresh();String java=new File(System.getProperty("java.home"),"bin/java").getAbsolutePath();Process child=new ProcessBuilder(java,"-XX:ActiveProcessorCount=2","-cp",System.getProperty("java.class.path"),EnvironmentIntentHostTest.class.getName(),"hold",c.root.getAbsolutePath()).redirectError(ProcessBuilder.Redirect.INHERIT).start();Path held=c.root.toPath().resolve("held"),release=c.root.toPath().resolve("release");long deadline=System.nanoTime()+10_000_000_000L;while(!Files.exists(held)){if(System.nanoTime()>deadline)throw new IOException("Child lease not acquired");Thread.sleep(5);}
    File leaseFile=new File(c.getNoBackupFilesDir(),"network-intent.lock");try(RandomAccessFile handle=new RandomAccessFile(leaseFile,"rw")){java.nio.channels.FileLock blocked=handle.getChannel().tryLock();check("Actual cross-JVM lease denies an independent OS tryLock",blocked==null);if(blocked!=null)blocked.close();}
    CompletableFuture<Boolean> entered=new CompletableFuture<>();Thread waiter=new Thread(()->{try{EnvironmentSpecRuntime.withIntent(c,()->{entered.complete(true);return null;});}catch(Exception failure){entered.completeExceptionally(failure);}});waiter.start();Thread.sleep(100);check("Another JVM retains the production OS intent lease",!entered.isDone());Files.writeString(release,"release");check("Contender proceeds only after cross-JVM lease release",entered.get(10,TimeUnit.SECONDS));check("Lease-holder JVM exits successfully",child.waitFor(10,TimeUnit.SECONDS)&&child.exitValue()==0);waiter.join(10000);try(RandomAccessFile handle=new RandomAccessFile(leaseFile,"rw");java.nio.channels.FileLock released=handle.getChannel().tryLock()){check("Released OS lease admits the independent negative control",released!=null);}crossProcess=true;
  }
  public static void main(String[] args)throws Exception{
    if(args.length>0&&args[0].equals("hold")){Context c=new Context(new File(args[1]),2);EnvironmentSpecRuntime.withIntent(c,()->{Files.writeString(c.root.toPath().resolve("held"),"held");long deadline=System.nanoTime()+10_000_000_000L;while(!Files.exists(c.root.toPath().resolve("release"))){if(System.nanoTime()>deadline)throw new IOException("Lease release missing");Thread.sleep(5);}return null;});return;}
    try{protocolValidation();successAndFailure();newerAndBrowserCas();interruptedStagesAndCancel();identityAndStrictReads();commitAcknowledgement();cacheInvalidation();reuseStableReceipt();reuseRejectsStaleOrInvalid();reusePrivateSnapshots();lease();fixtureBootstrapReconciliation();System.out.println(J.obj("schema",1,"status","passed","passed",checks.length(),"total",checks.length(),"executed",checks.length(),"checks",checks,"actualCrossProcessIntentLease",crossProcess,"actualAndroidExecution",false,"actualNativeExecution",false,"scope","production proxy validation, staged intent/CAS rollback/reconciliation, read-only receipt reuse and OS locks; URI syntax adapter and plain JVM repository/preferences doubles, no SQLite/Keystore/Gecko/WAN"));}
    catch(Throwable failure){System.out.println(J.obj("schema",1,"status","failed","passed",checks.length()-1,"total",checks.length(),"checks",checks,"error",failure.toString(),"actualAndroidExecution",false));throw failure;}
  }
  static void fixtureBootstrapReconciliation()throws Exception{
    Context c=new Context(Files.createTempDirectory("settings-bootstrap-").toFile(),0);ProfileCatalog.create(c,0);
    EnvironmentSpec migrated=EnvironmentSpecRuntime.desireActiveNetwork(c);
    c.getSharedPreferences("chat",0).values.put("proxy","http://127.0.0.1:18080");
    JSONObject accepted=migrated.desired().browser();accepted.put("fixtureBrowser","actual accepted desktop policy");
    EnvironmentSpec browserOnly=EnvironmentSpecRuntime.desireBrowser(c,accepted);
    EnvironmentSpec.NetworkBinding actual=EnvironmentSpecRuntime.binding(c,"external",new JSONObject(),"http://127.0.0.1:18080");
    check("Browser-only update retains earlier empty-proxy migration",migrated.desired().network.credentialRevision.isEmpty()&&browserOnly.desired().network.credentialRevision.isEmpty()&&!EnvironmentSpecRuntime.routeMatches(browserOnly,actual));
    EnvironmentSpec reconciled=EnvironmentSpecRuntime.desireActiveNetwork(c);
    check("Production reconciliation aligns fixture route and preserves accepted browser",reconciled.desired().equals(new EnvironmentSpec.Configuration(accepted,actual))&&reconciled.desiredRevision>browserOnly.desiredRevision);
    check("Fixture reconciliation cannot fabricate applied or observed revision",browserOnly.appliedRevision==0&&reconciled.appliedRevision==0&&reconciled.observedRevision==0);
    String candidate=save(c,"saved-candidate.example");long revision=model(c).desiredRevision;
    c.getSharedPreferences("chat",0).values.put("proxy","http://127.0.0.1:18081");
    EnvironmentSpec pendingAuthority=EnvironmentSpecRuntime.desireActiveNetwork(c);
    check("Reconciliation never replaces a saved candidate with current proxy preferences",candidate.equals(pending(c).toString())&&pendingAuthority.desiredRevision==revision&&pendingAuthority.desired().network.credentialRevision.equals(NativeNetwork.hash("socks://saved-candidate.example:1080")));
    check("Saved candidate reconciliation retains browser and remains unapplied",pendingAuthority.desired().browser().optString("fixtureBrowser").equals("actual accepted desktop policy")&&pendingAuthority.appliedRevision==0);
  }
}
