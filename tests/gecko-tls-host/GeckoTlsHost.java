package local.pocketchat;

import android.content.Context;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import org.json.*;

/** Actual desired-state source, real files/locks/processes; explicit Android I/O boundaries. */
public final class GeckoTlsHost {
  static final String ID="00000000-0000-0000-0000-000000000002",OTHER="00000000-0000-0000-0000-000000000003";
  static final List<String> checks=new ArrayList<>();static Path root;
  interface Checked {void run()throws Exception;}
  static void check(String name,boolean pass){if(!pass)throw new AssertionError(name);checks.add(name);}
  static void rejects(String name,Checked action)throws Exception{boolean failed=false;try{action.run();}catch(Exception expected){failed=true;}check(name,failed);}
  static TestContext context(String name)throws Exception{return new TestContext(root.resolve(name),new EnvironmentSpec.Identity(2,4,ID));}
  static byte[] raw(TestContext c)throws Exception{return new SecretStore(c).get(GeckoTlsStore.STORE);}
  static JSONObject object(TestContext c)throws Exception{return new JSONObject(new String(raw(c),StandardCharsets.UTF_8));}
  static void writeRaw(TestContext c,byte[] raw)throws Exception{Files.write(new SecretStore(c).file(GeckoTlsStore.STORE),raw);}
  static void unchanged(String name,TestContext c,byte[] original)throws Exception{check(name,Arrays.equals(raw(c),original));}

  static void specifications()throws Exception{
    GeckoTlsSpec defaults=GeckoTlsSpec.defaults(),strict=GeckoTlsSpec.of("tls13");
    check("New environment defaults to kernel policy without a guessed numeric range",defaults.isDefault()&&!defaults.requiresTls13()&&defaults.mode.equals("default")&&defaults.json().length()==3);
    check("Only strict TLS13 mode requests a restricted protocol",strict.requiresTls13()&&!strict.isDefault()&&strict.mode.equals("tls13"));
    check("Visible labels distinguish default from TLS13 only",defaults.label().equals("内核默认")&&strict.label().equals("仅 TLS 1.3"));
    for(String invalid:new String[]{null,"","0","1","2","3","4","3/4","4/4","tls12","TLS13"," tls13","tls13 ","auto","system","default\0"})rejects("Unsupported or ambiguous TLS mode rejected "+String.valueOf(invalid),()->GeckoTlsSpec.of(invalid));
    for(String mode:new String[]{"default","tls13"}){GeckoTlsSpec value=GeckoTlsSpec.of(mode);check("Exact immutable spec round trip "+mode,GeckoTlsSpec.from(value.json()).equals(value)&&GeckoTlsSpec.from(value.json()).hashCode()==value.hashCode());}
    JSONObject detached=strict.json();detached.put("mode","default");check("Caller JSON cannot mutate an immutable TLS selection",strict.requiresTls13());
    for(JSONObject bad:new JSONObject[]{J.obj("schema",2,"engine","gecko","mode","tls13"),J.obj("schema",true,"engine","gecko","mode","tls13"),J.obj("schema",1.0,"engine","gecko","mode","tls13"),J.obj("schema",1,"engine","chromium","mode","tls13"),J.obj("schema",1,"engine","gecko","mode",4),J.obj("schema",1,"engine","gecko","mode",JSONObject.NULL),J.obj("schema",1,"engine","gecko","mode","tls13","min",4),J.obj("schema",1,"engine","gecko","mode","tls13","wireVerified",true)})rejects("Strict schema rejects mixed/coerced/arbitrary-pref/native claims",()->GeckoTlsSpec.from(bad));
  }

  static void storage()throws Exception{
    TestContext c=context("storage");Path old=c.directory.resolve("environment-spec.host-vault");Files.write(old,new byte[]{7,4,1});
    GeckoTlsStore.State initial=GeckoTlsStore.load(c);check("Missing desired sidecar defaults to kernel policy at revision one",initial.identity.equals(c.catalog.current)&&initial.revision==1&&initial.spec.isDefault());
    check("TLS sidecar never rewrites existing environment schema",Arrays.equals(Files.readAllBytes(old),new byte[]{7,4,1}));
    check("Desired-only schema has no applied/native/worker acknowledgement fields",object(c).length()==5&&!object(c).has("appliedRevision")&&!object(c).has("nativeSettingReadback")&&!object(c).has("receipt"));
    byte[] untouched=raw(c);rejects("Saving without expected owner identity cannot adopt current slot implicitly",()->GeckoTlsStore.save(c,null,1,GeckoTlsSpec.of("tls13")));unchanged("Missing expected identity never changes desired bytes",c,untouched);
    rejects("Native admission without expected owner identity fails closed",()->GeckoTlsStore.stillCurrent(c,null,1));
    long writes=c.vault.writes;GeckoTlsStore.State same=GeckoTlsStore.save(c,initial.identity,1,GeckoTlsSpec.defaults());check("Unchanged selection neither increments revision nor writes",same.revision==1&&writes==c.vault.writes);
    GeckoTlsStore.State one=GeckoTlsStore.save(c,initial.identity,1,GeckoTlsSpec.of("tls13"));check("Desired save is durable with its own monotonic revision",one.revision==2&&object(c).getJSONObject("spec").getString("mode").equals("tls13"));
    check("Exact current identity/revision may admit its boot snapshot",GeckoTlsStore.stillCurrent(c,one.identity,one.revision));
    check("Old and nonpositive revisions cannot admit native boot work",!GeckoTlsStore.stillCurrent(c,one.identity,1)&&!GeckoTlsStore.stillCurrent(c,one.identity,0)&&!GeckoTlsStore.stillCurrent(c,one.identity,-1));
    rejects("Stale revision cannot overwrite newer desired state",()->GeckoTlsStore.save(c,initial.identity,1,GeckoTlsSpec.of("default")));
    byte[] bytes=raw(c);c.vault.failPut=true;rejects("Failed desired publication is surfaced",()->GeckoTlsStore.save(c,one.identity,2,GeckoTlsSpec.of("default")));unchanged("Write failure preserves exact previous desired bytes",c,bytes);check("Failed publication leaves prior revision current",GeckoTlsStore.stillCurrent(c,one.identity,2));
    c.vault.failRead=true;rejects("Read/decryption failure is not reset to kernel default",()->GeckoTlsStore.load(c));rejects("Read failure cannot admit an old native snapshot",()->GeckoTlsStore.stillCurrent(c,one.identity,2));c.vault.failRead=false;unchanged("Read failure retains original bytes",c,bytes);
    GeckoTlsStore.State reset=GeckoTlsStore.save(c,one.identity,2,GeckoTlsSpec.defaults());check("Kernel default intent stores no guessed protocol numbers",reset.revision==3&&reset.spec.isDefault()&&object(c).getJSONObject("spec").getString("mode").equals("default"));
    check("Old desired native preparation is revoked by a new revision",!GeckoTlsStore.stillCurrent(c,one.identity,2));
    JSONObject ceiling=object(c);ceiling.put("revision",Long.MAX_VALUE);writeRaw(c,ceiling.toString().getBytes(StandardCharsets.UTF_8));bytes=raw(c);rejects("Revision overflow refuses changed settings",()->GeckoTlsStore.save(c,reset.identity,Long.MAX_VALUE,GeckoTlsSpec.of("tls13")));unchanged("Revision overflow preserves old bytes",c,bytes);
  }

  static void identities()throws Exception{
    TestContext c=context("identity");GeckoTlsStore.State initial=GeckoTlsStore.load(c),saved=GeckoTlsStore.save(c,initial.identity,1,GeckoTlsSpec.of("tls13"));
    c.catalog.current=new EnvironmentSpec.Identity(2,5,ID);GeckoTlsStore.State next=GeckoTlsStore.load(c);check("Generation rebind retains desired policy and revision only",next.identity.generation==5&&next.revision==2&&next.spec.requiresTls13()&&object(c).length()==5);
    rejects("Previous generation cannot save after reset",()->GeckoTlsStore.save(c,saved.identity,2,GeckoTlsSpec.defaults()));rejects("Previous generation cannot admit a cold native snapshot",()->GeckoTlsStore.stillCurrent(c,saved.identity,2));
    c.catalog.current=new EnvironmentSpec.Identity(2,0,OTHER);GeckoTlsStore.State reused=GeckoTlsStore.load(c);check("Reused slot never inherits deleted environment strict TLS policy",reused.identity.environmentId.equals(OTHER)&&reused.revision==1&&reused.spec.isDefault());
    rejects("Deleted UUID cannot save into replacement owner",()->GeckoTlsStore.save(c,next.identity,2,GeckoTlsSpec.of("tls13")));rejects("Deleted UUID cannot admit boot despite matching numeric revision",()->GeckoTlsStore.stillCurrent(c,next.identity,1));
    JSONObject future=object(c);future.getJSONObject("identity").put("generation",9);writeRaw(c,future.toString().getBytes(StandardCharsets.UTF_8));byte[] bytes=raw(c);rejects("Future generation cannot migrate backwards",()->GeckoTlsStore.load(c));unchanged("Future generation bytes retained",c,bytes);
    TestContext other=new TestContext(root.resolve("other-slot"),new EnvironmentSpec.Identity(3,0,OTHER));GeckoTlsStore.State first=GeckoTlsStore.load(other);GeckoTlsStore.save(other,first.identity,1,GeckoTlsSpec.of("tls13"));
    TestContext independent=context("independent");GeckoTlsStore.State baseline=GeckoTlsStore.load(independent);check("Independent environments retain different desired policy files",GeckoTlsStore.load(other).spec.requiresTls13()&&baseline.spec.isDefault()&&baseline.revision==1&&GeckoTlsStore.load(other).revision==2);
    rejects("Identity from another slot cannot overwrite desired TLS",()->GeckoTlsStore.save(other,baseline.identity,1,GeckoTlsSpec.defaults()));
  }

  static void malformed()throws Exception{
    TestContext c=context("malformed");GeckoTlsStore.load(c);byte[] original=raw(c);List<byte[]> invalid=new ArrayList<>();
    for(String raw:new String[]{"", "null", "[]", "{}{}", "{\"schema\":1,"+new String(original,StandardCharsets.UTF_8).substring(1)})invalid.add(raw.getBytes(StandardCharsets.UTF_8));invalid.add(new byte[]{(byte)255});invalid.add(new byte[GeckoTlsStore.MAX_BYTES+1]);
    for(String field:new String[]{"schema","engine","identity","revision","spec"}){JSONObject value=new JSONObject(new String(original,StandardCharsets.UTF_8));value.remove(field);invalid.add(value.toString().getBytes(StandardCharsets.UTF_8));}
    for(String field:new String[]{"receipt","appliedRevision","activeBootRevision","nativeSettingReadback","workerCoverageVerified"}){JSONObject value=new JSONObject(new String(original,StandardCharsets.UTF_8));value.put(field,true);invalid.add(value.toString().getBytes(StandardCharsets.UTF_8));}
    for(Object revision:new Object[]{0,-1,true,"1",1.5,JSONObject.NULL}){JSONObject value=new JSONObject(new String(original,StandardCharsets.UTF_8));value.put("revision",revision);invalid.add(value.toString().getBytes(StandardCharsets.UTF_8));}
    JSONObject value=new JSONObject(new String(original,StandardCharsets.UTF_8));value.put("schema",2);invalid.add(value.toString().getBytes(StandardCharsets.UTF_8));value=new JSONObject(new String(original,StandardCharsets.UTF_8));value.put("engine","chromium");invalid.add(value.toString().getBytes(StandardCharsets.UTF_8));
    value=new JSONObject(new String(original,StandardCharsets.UTF_8));value.getJSONObject("identity").put("slot",3);invalid.add(value.toString().getBytes(StandardCharsets.UTF_8));
    value=new JSONObject(new String(original,StandardCharsets.UTF_8));value.getJSONObject("identity").put("generation",true);invalid.add(value.toString().getBytes(StandardCharsets.UTF_8));
    value=new JSONObject(new String(original,StandardCharsets.UTF_8));value.getJSONObject("identity").put("environmentId",OTHER).put("extra","unknown");invalid.add(value.toString().getBytes(StandardCharsets.UTF_8));
    value=new JSONObject(new String(original,StandardCharsets.UTF_8));value.getJSONObject("spec").put("mode",0);invalid.add(value.toString().getBytes(StandardCharsets.UTF_8));
    int index=0;for(byte[] bytes:invalid){writeRaw(c,bytes);rejects("Malformed or overclaimed raw desired record rejected "+index,()->GeckoTlsStore.load(c));unchanged("Malformed desired file is never overwritten "+index,c,bytes);index++;}writeRaw(c,original);
    check("Successful read resumes after caller repairs test boundary file",GeckoTlsStore.load(c).spec.isDefault());
  }

  static void concurrency()throws Exception{
    TestContext c=context("threads");GeckoTlsStore.State initial=GeckoTlsStore.load(c);ExecutorService pool=Executors.newFixedThreadPool(12);CountDownLatch ready=new CountDownLatch(12),start=new CountDownLatch(1);AtomicInteger winners=new AtomicInteger();List<Future<?>> calls=new ArrayList<>();
    try{for(int i=0;i<12;i++){final String mode="tls13";calls.add(pool.submit(()->{ready.countDown();try{start.await();GeckoTlsStore.save(c,initial.identity,1,GeckoTlsSpec.of(mode));winners.incrementAndGet();}catch(IOException expected){}catch(Exception failure){throw new RuntimeException(failure);}}));}check("All independent caller threads reach the CAS barrier",ready.await(5,TimeUnit.SECONDS));start.countDown();for(Future<?> call:calls)call.get(5,TimeUnit.SECONDS);check("Concurrent actual production CAS has exactly one winner",winners.get()==1&&GeckoTlsStore.load(c).revision==2);}finally{start.countDown();pool.shutdownNow();}
    TestContext held=context("identity-held");GeckoTlsStore.State state=GeckoTlsStore.load(held);held.vault.entered=new CountDownLatch(1);held.vault.release=new CountDownLatch(1);CountDownLatch entered=held.vault.entered,attempted=new CountDownLatch(1),changed=new CountDownLatch(1);ExecutorService race=Executors.newFixedThreadPool(2);
    try{Future<?> saving=race.submit(()->{try{GeckoTlsStore.save(held,state.identity,1,GeckoTlsSpec.of("tls13"));}catch(Exception failure){throw new RuntimeException(failure);}});check("Writer reaches real publication while catalog identity gate is held",entered.await(5,TimeUnit.SECONDS));Future<?> replacing=race.submit(()->{attempted.countDown();synchronized(held.catalog.gate){held.catalog.current=new EnvironmentSpec.Identity(2,0,OTHER);changed.countDown();}});check("Replacement actually attempts protected catalog identity transition",attempted.await(5,TimeUnit.SECONDS));check("Owner replacement cannot pass active writer transaction",!changed.await(50,TimeUnit.MILLISECONDS));held.vault.release.countDown();saving.get(5,TimeUnit.SECONDS);replacing.get(5,TimeUnit.SECONDS);check("Replacement owner uses kernel default after protected old write completes",GeckoTlsStore.load(held).spec.isDefault());}finally{held.vault.release.countDown();race.shutdownNow();}
  }

  static void currentTransaction()throws Exception{
    TestContext c=context("current-transaction");GeckoTlsStore.State state=GeckoTlsStore.load(c);AtomicInteger actions=new AtomicInteger();long writes=c.vault.writes;
    String result=GeckoTlsStore.withCurrent(c,state.identity,state.revision,()->{actions.incrementAndGet();check("Current action executes while actual catalog identity monitor is held",Thread.holdsLock(c.catalog.gate));return "prepared";});
    check("Current transaction returns the actual action result without rewriting desired",result.equals("prepared")&&actions.get()==1&&writes==c.vault.writes&&GeckoTlsStore.stillCurrent(c,state.identity,1));
    rejects("Current action requires nonnull expected identity",()->GeckoTlsStore.withCurrent(c,null,1,()->{actions.incrementAndGet();return null;}));
    rejects("Current action requires nonnull action",()->GeckoTlsStore.withCurrent(c,state.identity,1,null));
    rejects("Current action refuses stale desired revision",()->GeckoTlsStore.withCurrent(c,state.identity,2,()->{actions.incrementAndGet();return null;}));
    rejects("Current action refuses nonpositive desired revision",()->GeckoTlsStore.withCurrent(c,state.identity,0,()->{actions.incrementAndGet();return null;}));
    rejects("Current action refuses stale owner generation",()->GeckoTlsStore.withCurrent(c,new EnvironmentSpec.Identity(2,5,ID),1,()->{actions.incrementAndGet();return null;}));
    rejects("Current action refuses foreign owner UUID",()->GeckoTlsStore.withCurrent(c,new EnvironmentSpec.Identity(2,4,OTHER),1,()->{actions.incrementAndGet();return null;}));
    check("No rejected current transaction invokes the preparation callback",actions.get()==1);
    rejects("Action failure is propagated to caller",()->GeckoTlsStore.withCurrent(c,state.identity,1,()->{throw new IOException("Injected profile preparation failure");}));
    ExecutorService pool=Executors.newFixedThreadPool(2);
    try{Future<GeckoTlsStore.State> afterFailure=pool.submit(()->GeckoTlsStore.save(c,state.identity,1,GeckoTlsSpec.of("tls13")));check("Action exception releases all locks for another-thread CAS",afterFailure.get(5,TimeUnit.SECONDS).revision==2);}finally{pool.shutdownNow();}

    TestContext held=context("current-action-held");GeckoTlsStore.State heldState=GeckoTlsStore.load(held);CountDownLatch entered=new CountDownLatch(1),release=new CountDownLatch(1),saveAttempted=new CountDownLatch(1);AtomicInteger order=new AtomicInteger(),preparedOrder=new AtomicInteger(),savedOrder=new AtomicInteger();ExecutorService serial=Executors.newFixedThreadPool(2);
    try{
      Future<String> preparing=serial.submit(()->GeckoTlsStore.withCurrent(held,heldState.identity,1,()->{check("Blocking profile preparation retains catalog owner transaction",Thread.holdsLock(held.catalog.gate));entered.countDown();if(!release.await(5,TimeUnit.SECONDS))throw new IOException("Preparation fixture timed out");Files.write(held.directory.resolve("profile-prepared"),new byte[]{2});preparedOrder.set(order.incrementAndGet());return "complete";}));
      check("Actual current action reaches controlled profile-preparation boundary",entered.await(5,TimeUnit.SECONDS));
      Future<GeckoTlsStore.State> saving=serial.submit(()->{saveAttempted.countDown();GeckoTlsStore.State saved=GeckoTlsStore.save(held,heldState.identity,1,GeckoTlsSpec.of("tls13"));savedOrder.set(order.incrementAndGet());return saved;});
      check("Same-revision save actually reaches competing caller",saveAttempted.await(5,TimeUnit.SECONDS));
      check("Same-revision save cannot complete while current profile action is active",!saving.isDone()&&held.vault.writes==1);
      release.countDown();check("Profile preparation completes before competing desired publication",preparing.get(5,TimeUnit.SECONDS).equals("complete")&&saving.get(5,TimeUnit.SECONDS).revision==2&&preparedOrder.get()==1&&savedOrder.get()==2&&Files.exists(held.directory.resolve("profile-prepared")));
    }finally{release.countDown();serial.shutdownNow();}

    TestContext owner=context("current-owner-held");GeckoTlsStore.State before=GeckoTlsStore.load(owner);CountDownLatch ownerEntered=new CountDownLatch(1),ownerRelease=new CountDownLatch(1),replaceAttempted=new CountDownLatch(1),replaced=new CountDownLatch(1);ExecutorService replacement=Executors.newFixedThreadPool(2);
    try{
      Future<?> preparing=replacement.submit(()->{try{GeckoTlsStore.withCurrent(owner,before.identity,1,()->{ownerEntered.countDown();if(!ownerRelease.await(5,TimeUnit.SECONDS))throw new IOException("Owner fixture timed out");check("Owner is unchanged during preparation transaction",owner.catalog.current.equals(before.identity));return null;});}catch(Exception failure){throw new RuntimeException(failure);}});
      check("Current preparation reaches owner-change barrier",ownerEntered.await(5,TimeUnit.SECONDS));
      Future<?> changing=replacement.submit(()->{replaceAttempted.countDown();synchronized(owner.catalog.gate){owner.catalog.current=new EnvironmentSpec.Identity(2,0,OTHER);replaced.countDown();}});
      check("Owner replacement actually attempts the current action's catalog gate",replaceAttempted.await(5,TimeUnit.SECONDS));
      check("Owner reuse cannot cross an active preparation callback",!replaced.await(50,TimeUnit.MILLISECONDS));ownerRelease.countDown();preparing.get(5,TimeUnit.SECONDS);changing.get(5,TimeUnit.SECONDS);
      check("Owner reuse after preparation starts fresh kernel-default desired state",GeckoTlsStore.load(owner).spec.isDefault()&&owner.catalog.current.environmentId.equals(OTHER));
      rejects("Old owner cannot prepare after replacement completed",()->GeckoTlsStore.withCurrent(owner,before.identity,1,()->null));
    }finally{ownerRelease.countDown();replacement.shutdownNow();}
  }

  static void process(String phase,String label)throws Exception{
    TestContext c=context(phase.startsWith("restart")?"restart":"process-race");
    if(phase.equals("restart-seed")){GeckoTlsStore.State initial=GeckoTlsStore.load(c);GeckoTlsStore.State saved=GeckoTlsStore.save(c,initial.identity,1,GeckoTlsSpec.of("tls13"));check("Initial JVM durably saves desired TLS13 only",saved.revision==2&&saved.spec.requiresTls13());}
    else if(phase.equals("restart-check")){GeckoTlsStore.State state=GeckoTlsStore.load(c);check("Independent JVM retains exact desired revision and policy",state.revision==2&&state.spec.requiresTls13());check("Restart cannot turn desired state into native or wire ACK",object(c).length()==5&&!object(c).has("nativeSettingReadback")&&!object(c).has("wireObservationVerified"));}
    else if(phase.equals("race-seed")){check("Process CAS begins at revision one",GeckoTlsStore.load(c).revision==1);}
    else if(phase.equals("race-write")){boolean won=false;try{GeckoTlsStore.save(c,new EnvironmentSpec.Identity(2,4,ID),1,GeckoTlsSpec.of("tls13"));won=true;}catch(IOException expected){}Files.write(root.resolve("race-"+label+".json"),J.obj("won",won).toString().getBytes(StandardCharsets.UTF_8));check("Independent process completed actual desired CAS",true);}
    else if(phase.equals("race-check")){boolean a=new JSONObject(new String(Files.readAllBytes(root.resolve("race-A.json")),StandardCharsets.UTF_8)).getBoolean("won"),b=new JSONObject(new String(Files.readAllBytes(root.resolve("race-B.json")),StandardCharsets.UTF_8)).getBoolean("won");check("Actual file lock yields one independent JVM CAS winner",a!=b&&GeckoTlsStore.load(c).revision==2);}
  }
  public static void main(String[] args)throws Exception{root=Paths.get(args[1]);Files.createDirectories(root);if(args[0].equals("main")){specifications();storage();identities();malformed();concurrency();currentTransaction();}else process(args[0],args.length>2?args[2]:"");System.out.println(J.obj("status","passed","phase",args[0],"passed",checks.size(),"total",checks.size(),"checks",new JSONArray(checks)));}
}

final class TestContext extends Context {
  final Path directory;final ProfileCatalog catalog;final VaultFaults vault=new VaultFaults();
  TestContext(Path directory,EnvironmentSpec.Identity identity)throws Exception{this.directory=directory;Files.createDirectories(directory);catalog=new ProfileCatalog(identity);}
  @Override public Context getApplicationContext(){return this;}@Override public File getNoBackupFilesDir(){return directory.toFile();}
}
final class VaultFaults {boolean failPut,failRead;long writes;CountDownLatch entered,release;}
final class Profiles {static int slot(Context context){return ((TestContext)context).catalog.current.slot;}}
final class ProfileCatalog {
  volatile EnvironmentSpec.Identity current;final Object gate=new Object();ProfileCatalog(EnvironmentSpec.Identity current){this.current=current;}
  static ProfileCatalog get(Context context){return ((TestContext)context).catalog;}
  EnvironmentSpec.Identity identity(int slot)throws IOException{if(current.slot!=slot)throw new IOException("Wrong slot");return current;}
  interface IdentityAction<T>{T run()throws Exception;}
  <T>T withIdentity(EnvironmentSpec.Identity expected,IdentityAction<T> action)throws Exception{synchronized(gate){if(!current.equals(expected))throw new IOException("Identity changed");return action.run();}}
}
final class SecretStore {
  final TestContext context;SecretStore(Context context){this.context=(TestContext)context;}
  Path file(String name){if(!name.matches("[a-z-]+"))throw new IllegalArgumentException();return context.directory.resolve(name+".host-vault");}
  byte[] get(String name)throws IOException{if(context.vault.failRead)throw new IOException("Injected read/decrypt boundary failure");return Files.exists(file(name))?Files.readAllBytes(file(name)):null;}
  void put(String name,byte[] value)throws Exception{context.vault.writes++;if(context.vault.failPut){context.vault.failPut=false;throw new IOException("Injected atomic prepublication failure");}CountDownLatch entered=context.vault.entered,release=context.vault.release;if(entered!=null&&release!=null){context.vault.entered=null;entered.countDown();if(!release.await(5,TimeUnit.SECONDS))throw new IOException("Fixture barrier timed out");}Path temp=Files.createTempFile(context.directory,"tls-vault-",".tmp");try{Files.write(temp,value);Files.move(temp,file(name),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);}finally{Files.deleteIfExists(temp);}}
}
