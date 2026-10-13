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
  static void lease()throws Exception{
    Context c=fresh();String java=new File(System.getProperty("java.home"),"bin/java").getAbsolutePath();Process child=new ProcessBuilder(java,"-XX:ActiveProcessorCount=2","-cp",System.getProperty("java.class.path"),EnvironmentIntentHostTest.class.getName(),"hold",c.root.getAbsolutePath()).redirectError(ProcessBuilder.Redirect.INHERIT).start();Path held=c.root.toPath().resolve("held"),release=c.root.toPath().resolve("release");long deadline=System.nanoTime()+10_000_000_000L;while(!Files.exists(held)){if(System.nanoTime()>deadline)throw new IOException("Child lease not acquired");Thread.sleep(5);}
    File leaseFile=new File(c.getNoBackupFilesDir(),"network-intent.lock");try(RandomAccessFile handle=new RandomAccessFile(leaseFile,"rw")){java.nio.channels.FileLock blocked=handle.getChannel().tryLock();check("Actual cross-JVM lease denies an independent OS tryLock",blocked==null);if(blocked!=null)blocked.close();}
    CompletableFuture<Boolean> entered=new CompletableFuture<>();Thread waiter=new Thread(()->{try{EnvironmentSpecRuntime.withIntent(c,()->{entered.complete(true);return null;});}catch(Exception failure){entered.completeExceptionally(failure);}});waiter.start();Thread.sleep(100);check("Another JVM retains the production OS intent lease",!entered.isDone());Files.writeString(release,"release");check("Contender proceeds only after cross-JVM lease release",entered.get(10,TimeUnit.SECONDS));check("Lease-holder JVM exits successfully",child.waitFor(10,TimeUnit.SECONDS)&&child.exitValue()==0);waiter.join(10000);try(RandomAccessFile handle=new RandomAccessFile(leaseFile,"rw");java.nio.channels.FileLock released=handle.getChannel().tryLock()){check("Released OS lease admits the independent negative control",released!=null);}crossProcess=true;
  }
  public static void main(String[] args)throws Exception{
    if(args.length>0&&args[0].equals("hold")){Context c=new Context(new File(args[1]),2);EnvironmentSpecRuntime.withIntent(c,()->{Files.writeString(c.root.toPath().resolve("held"),"held");long deadline=System.nanoTime()+10_000_000_000L;while(!Files.exists(c.root.toPath().resolve("release"))){if(System.nanoTime()>deadline)throw new IOException("Lease release missing");Thread.sleep(5);}return null;});return;}
    try{protocolValidation();successAndFailure();newerAndBrowserCas();interruptedStagesAndCancel();identityAndStrictReads();commitAcknowledgement();cacheInvalidation();lease();System.out.println(J.obj("schema",1,"status","passed","passed",checks.length(),"total",checks.length(),"executed",checks.length(),"checks",checks,"actualCrossProcessIntentLease",crossProcess,"actualAndroidExecution",false,"actualNativeExecution",false,"scope","production proxy validation, staged intent/CAS rollback/reconciliation and OS locks; URI syntax adapter and plain JVM repository/preferences doubles, no SQLite/Keystore/Gecko/WAN"));}
    catch(Throwable failure){System.out.println(J.obj("schema",1,"status","failed","passed",checks.length()-1,"total",checks.length(),"checks",checks,"error",failure.toString(),"actualAndroidExecution",false));throw failure;}
  }
}
