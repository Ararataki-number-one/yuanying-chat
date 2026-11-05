package local.pocketchat;

import android.content.Context;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import org.json.*;

/** Executes the complete store with real temp files/locks and explicit vault/catalog boundaries. */
public final class ChromiumFingerprintStoreHost {
  static final String ID="00000000-0000-0000-0000-000000000002",OTHER="00000000-0000-0000-0000-000000000003";
  static final List<String> checks=new ArrayList<>();
  static Path root;
  interface Checked {void run()throws Exception;}
  static void check(String name,boolean value){if(!value)throw new AssertionError(name);checks.add(name);}
  static void rejects(String name,Checked action)throws Exception{boolean rejected=false;try{action.run();}catch(Exception expected){rejected=true;}check(name,rejected);}
  static TestContext context(String name)throws Exception{return new TestContext(root.resolve(name),new EnvironmentSpec.Identity(2,4,ID));}
  static JSONObject spec(String name){return J.obj("schema",1,"engine","chromium","profile",name,"locale","zh-CN","display","mobile");}
  static JSONObject fields(){return J.obj("ua",J.obj("state","native-readback","value","Host Chromium UA"),"timezone",J.obj("state","unsupported"),"worker",J.obj("state","requested"));}
  static ChromiumFingerprintStore.Binding binding(){return new ChromiumFingerprintStore.Binding("com.host.webview","157.0.1","runtime-0123456789abcdef",3,7);}
  static byte[] raw(TestContext context)throws Exception{return new SecretStore(context).get(ChromiumFingerprintStore.STORE);}
  static void writeRaw(TestContext context,byte[] value)throws Exception{new SecretStore(context).raw(value);}
  static JSONObject rawObject(TestContext context)throws Exception{return new JSONObject(new String(raw(context),StandardCharsets.UTF_8));}
  static void unchanged(String name,TestContext context,byte[] before){check(name,Arrays.equals(before,readUnchecked(context)));}
  static byte[] readUnchecked(TestContext context){try{return raw(context);}catch(Exception error){throw new AssertionError(error);}}
  static String canonical(JSONObject value){return sorted(value);}
  static String sorted(Object value){
    if(value instanceof JSONObject){JSONObject object=(JSONObject)value;List<String> keys=new ArrayList<>();Iterator<String> it=object.keys();while(it.hasNext())keys.add(it.next());Collections.sort(keys);List<String> result=new ArrayList<>();for(String key:keys)result.add(JSONObject.quote(key)+":"+sorted(object.opt(key)));return "{"+String.join(",",result)+"}";}
    if(value instanceof JSONArray){JSONArray array=(JSONArray)value;List<String> result=new ArrayList<>();for(int i=0;i<array.length();i++)result.add(sorted(array.opt(i)));return "["+String.join(",",result)+"]";}
    if(value==null||value==JSONObject.NULL)return "null";return value instanceof String?JSONObject.quote((String)value):value.toString();
  }
  static void generationAndOwner()throws Exception{
    TestContext context=context("generation");ChromiumFingerprintStore.State initial=ChromiumFingerprintStore.load(context);
    ChromiumFingerprintStore.State saved=ChromiumFingerprintStore.save(context,initial.identity,initial.revision,spec("preserved-desired"));
    ChromiumFingerprintStore.Binding binding=binding();ChromiumFingerprintStore.activate(context,saved.identity,saved.revision,binding);ChromiumFingerprintStore.record(context,saved.identity,saved.revision,binding,fields());
    byte[] beforeRebound=raw(context);context.catalog.current=new EnvironmentSpec.Identity(2,5,ID);context.vault.failPut=true;
    rejects("Generation rebound publication failure is surfaced",()->ChromiumFingerprintStore.load(context));unchanged("Failed rebound preserves previous generation bytes",context,beforeRebound);
    ChromiumFingerprintStore.State renewed=ChromiumFingerprintStore.load(context);
    check("Login generation reset keeps exact desired configuration and revision",renewed.revision==saved.revision&&canonical(renewed.spec()).equals(canonical(saved.spec())));
    check("Login generation reset binds new generation and rotates seed",renewed.identity.generation==5&&renewed.identity.environmentId.equals(ID)&&!renewed.seed.equals(saved.seed));
    check("Login generation reset clears durable receipt",rawObject(context).getJSONObject("receipt").length()==0);
    rejects("Previous generation cannot save",()->ChromiumFingerprintStore.save(context,saved.identity,saved.revision,spec("stale")));
    rejects("Previous generation cannot activate",()->ChromiumFingerprintStore.activate(context,saved.identity,saved.revision,binding));
    rejects("Previous generation cannot record",()->ChromiumFingerprintStore.record(context,saved.identity,saved.revision,binding,fields()));
    byte[] beforeOwner=raw(context);context.catalog.current=new EnvironmentSpec.Identity(2,5,OTHER);context.vault.failPut=true;
    rejects("New owner default publication failure is surfaced",()->ChromiumFingerprintStore.load(context));unchanged("Failed owner replacement preserves old bytes",context,beforeOwner);
    ChromiumFingerprintStore.State replacement=ChromiumFingerprintStore.load(context);
    check("Reused slot starts a new owner's default config",replacement.identity.environmentId.equals(OTHER)&&replacement.revision==1&&replacement.spec().length()==2&&replacement.spec().optString("engine").equals("chromium"));
    check("Reused slot never inherits old seed or receipt",!replacement.seed.equals(renewed.seed)&&rawObject(context).getJSONObject("receipt").length()==0);
    byte[] own=raw(context);rejects("Previous UUID cannot save",()->ChromiumFingerprintStore.save(context,renewed.identity,renewed.revision,spec("foreign")));unchanged("Rejected foreign save preserves new owner's bytes",context,own);
    rejects("Previous UUID cannot activate",()->ChromiumFingerprintStore.activate(context,renewed.identity,renewed.revision,binding));rejects("Previous UUID cannot record",()->ChromiumFingerprintStore.record(context,renewed.identity,renewed.revision,binding,fields()));
    TestContext future=context("future-generation");ChromiumFingerprintStore.load(future);byte[] futureBytes=raw(future);future.catalog.current=new EnvironmentSpec.Identity(2,3,ID);
    rejects("Stored future generation is not downgraded",()->ChromiumFingerprintStore.load(future));unchanged("Future-generation state bytes retained",future,futureBytes);
  }
  static void malformed()throws Exception{
    TestContext context=context("malformed");ChromiumFingerprintStore.load(context);byte[] good=raw(context);
    List<byte[]> invalid=new ArrayList<>();invalid.add("{broken".getBytes(StandardCharsets.UTF_8));invalid.add("{} trailing".getBytes(StandardCharsets.UTF_8));invalid.add(new byte[]{(byte)0xc3,(byte)0x28});
    for(String mutation:new String[]{"future","engine","slot","revision","seed","unknown"}){
      JSONObject value=new JSONObject(new String(good,StandardCharsets.UTF_8));
      if(mutation.equals("future"))value.put("schema",2);if(mutation.equals("engine"))value.put("engine","gecko");if(mutation.equals("slot"))value.getJSONObject("identity").put("slot",1);if(mutation.equals("revision"))value.put("revision",1.0);if(mutation.equals("seed"))value.put("seed","invalid");if(mutation.equals("unknown"))value.put("futureField",true);
      invalid.add(mutation.equals("revision")?new String(good,StandardCharsets.UTF_8).replaceFirst("\"revision\":1([,}])","\"revision\":1.0$1").getBytes(StandardCharsets.UTF_8):value.toString().getBytes(StandardCharsets.UTF_8));
    }
    int index=0;for(byte[] value:invalid){writeRaw(context,value);final int sequence=index++;rejects("Malformed/future storage fails closed "+sequence,()->ChromiumFingerprintStore.load(context));unchanged("Malformed/future storage bytes retained "+sequence,context,value);}
    writeRaw(context,good);context.vault.failRead=true;rejects("Vault read/decryption boundary failure is surfaced",()->ChromiumFingerprintStore.load(context));context.vault.failRead=false;unchanged("Read failure does not replace stored config",context,good);
    ChromiumFingerprintStore.State state=ChromiumFingerprintStore.load(context);ChromiumFingerprintStore.Binding binding=binding();ChromiumFingerprintStore.activate(context,state.identity,state.revision,binding);ChromiumFingerprintStore.record(context,state.identity,state.revision,binding,fields());byte[] receiptGood=raw(context);
    for(String mutation:new String[]{"claim","process","activation","binding","identity","revision","state","unknown"}){
      JSONObject value=new JSONObject(new String(receiptGood,StandardCharsets.UTF_8)),receipt=value.getJSONObject("receipt");
      if(mutation.equals("claim"))receipt.put("fingerprintProtectionVerified",true);if(mutation.equals("process"))receipt.put("processNonce","invalid");if(mutation.equals("activation"))receipt.put("activationNonce","invalid");if(mutation.equals("binding"))receipt.put("surfaceGeneration",-1);if(mutation.equals("identity"))receipt.getJSONObject("identity").put("environmentId",OTHER);if(mutation.equals("revision"))receipt.put("desiredRevision",state.revision+1);if(mutation.equals("state"))receipt.getJSONObject("fields").getJSONObject("ua").put("state","fully-protected");if(mutation.equals("unknown"))receipt.put("futureReceipt",true);
      byte[] changed=value.toString().getBytes(StandardCharsets.UTF_8);writeRaw(context,changed);rejects("Malformed receipt fails closed "+mutation,()->ChromiumFingerprintStore.load(context));unchanged("Malformed receipt bytes retained "+mutation,context,changed);
    }
  }
  static void run()throws Exception{
    TestContext context=context("basic");ChromiumFingerprintStore.State initial=ChromiumFingerprintStore.load(context);
    check("Fresh state has exact environment identity and revision1",initial.identity.equals(context.catalog.current)&&initial.revision==1);
    check("Fresh state has strong64hex seed",initial.seed.matches("[0-9a-f]{64}"));
    check("Fresh state has minimal unconfirmed Chromium config",initial.spec().length()==2&&Integer.valueOf(1).equals(initial.spec().opt("schema"))&&initial.spec().optString("engine").equals("chromium")&&rawObject(context).getJSONObject("receipt").length()==0);
    check("Production creates actual lock file",Files.isRegularFile(context.directory.resolve("chromium-fingerprint.lock")));
    ChromiumFingerprintStore.State loaded=ChromiumFingerprintStore.load(context);check("Repeated load keeps seed/revision and bytes",loaded.seed.equals(initial.seed)&&loaded.revision==1);
    JSONObject supplied=spec("first");ChromiumFingerprintStore.State saved=ChromiumFingerprintStore.save(context,initial.identity,initial.revision,supplied);supplied.put("profile","caller-mutation");
    check("Save increments revision and retains stable seed",saved.revision==2&&saved.seed.equals(initial.seed));check("Saved config is detached from caller",saved.spec().optString("profile").equals("first"));
    JSONObject detached=saved.spec();detached.put("profile","returned-mutation");check("State.spec returns detached values",saved.spec().optString("profile").equals("first")&&ChromiumFingerprintStore.load(context).spec().optString("profile").equals("first"));
    byte[] sameBefore=raw(context);long writes=context.vault.puts;JSONObject reordered=J.obj("display","mobile","locale","zh-CN","profile","first","engine","chromium","schema",1);ChromiumFingerprintStore.State same=ChromiumFingerprintStore.save(context,saved.identity,saved.revision,reordered);
    check("Canonical identical config is a no-op",same.revision==saved.revision&&same.seed.equals(saved.seed)&&context.vault.puts==writes);unchanged("Canonical no-op retains exact storage bytes",context,sameBefore);
    rejects("Stale configuration revision is rejected",()->ChromiumFingerprintStore.save(context,saved.identity,1,spec("stale")));unchanged("Stale CAS preserves predecessor",context,sameBefore);
    for(Object schema:new Object[]{"1",1.0,true,2}){JSONObject bad=spec("bad");bad.put("schema",schema);rejects("Spec schema is strict integer1 "+schema,()->ChromiumFingerprintStore.save(context,saved.identity,saved.revision,bad));}
    JSONObject other=spec("bad");other.put("engine","gecko");rejects("Foreign-engine spec is rejected",()->ChromiumFingerprintStore.save(context,saved.identity,saved.revision,other));
    StringBuilder large=new StringBuilder();for(int i=0;i<17000;i++)large.append('x');JSONObject huge=spec("huge");huge.put("payload",large.toString());rejects("Spec size is bounded",()->ChromiumFingerprintStore.save(context,saved.identity,saved.revision,huge));unchanged("Invalid specs leave exact stored bytes",context,sameBefore);
    JSONObject deep=spec("deep"),nested=deep;for(int i=0;i<30;i++){JSONObject child=new JSONObject();nested.put("nested",child);nested=child;}rejects("Spec nesting is bounded",()->ChromiumFingerprintStore.save(context,saved.identity,saved.revision,deep));unchanged("Over-deep spec preserves predecessor",context,sameBefore);
    context.vault.failPut=true;rejects("Save publication error is surfaced",()->ChromiumFingerprintStore.save(context,saved.identity,saved.revision,spec("failed")));unchanged("Failed save preserves previous published bytes",context,sameBefore);
    ChromiumFingerprintStore.State retried=ChromiumFingerprintStore.save(context,saved.identity,saved.revision,spec("retry"));check("Failed save leaves CAS available for retry",retried.revision==3&&retried.seed.equals(saved.seed));

    TestContext race=context("race");ChromiumFingerprintStore.State base=ChromiumFingerprintStore.load(race);CountDownLatch start=new CountDownLatch(1);ExecutorService racers=Executors.newFixedThreadPool(2);AtomicInteger successes=new AtomicInteger(),conflicts=new AtomicInteger();List<Future<?>> pending=new ArrayList<>();
    try{for(int i=0;i<2;i++){final int number=i;pending.add(racers.submit(()->{try{start.await();ChromiumFingerprintStore.save(race,base.identity,base.revision,spec("winner-"+number));successes.incrementAndGet();}catch(Exception stale){conflicts.incrementAndGet();}}));}start.countDown();for(Future<?> task:pending)task.get(5,TimeUnit.SECONDS);}finally{racers.shutdownNow();}
    ChromiumFingerprintStore.State winner=ChromiumFingerprintStore.load(race);check("Two concurrent same-revision saves produce one winner",successes.get()==1&&conflicts.get()==1&&winner.revision==2&&winner.seed.equals(base.seed));

    ChromiumFingerprintStore.Binding binding=binding();check("No receipt exists before runtime activation",ChromiumFingerprintStore.lastReceipt(context,retried.identity,retried.revision,binding).length()==0);
    rejects("Record requires current runtime activation",()->ChromiumFingerprintStore.record(context,retried.identity,retried.revision,binding,fields()));
    byte[] beforeActivate=raw(context);ChromiumFingerprintStore.activate(context,retried.identity,retried.revision,binding);unchanged("Activate alone never creates persistent acknowledgement",context,beforeActivate);
    JSONObject receipt=ChromiumFingerprintStore.record(context,retried.identity,retried.revision,binding,fields());
    check("Receipt binds exact identity/revision/provider/runtime/page",receipt.getJSONObject("identity").optString("environmentId").equals(ID)&&receipt.optLong("desiredRevision")==retried.revision&&receipt.optString("engine").equals("chromium")&&receipt.optString("providerPackage").equals("com.host.webview")&&receipt.optString("providerVersion").equals("157.0.1")&&receipt.optString("runtimeEpoch").equals("runtime-0123456789abcdef")&&receipt.optLong("surfaceGeneration")==3&&receipt.optLong("navigationGeneration")==7);
    check("Receipt explicitly refuses full fingerprint-protection attestation",Boolean.FALSE.equals(receipt.opt("fingerprintProtectionVerified"))&&!receipt.optString("processNonce").isEmpty());
    check("Receipt has actual runtime activation nonce",receipt.optString("activationNonce").matches("[0-9a-f]{64}"));
    receipt.getJSONObject("fields").getJSONObject("ua").put("value","caller-overwrite");JSONObject current=ChromiumFingerprintStore.lastReceipt(context,retried.identity,retried.revision,binding);
    check("Recorded and returned receipts are detached",current.getJSONObject("fields").getJSONObject("ua").optString("value").equals("Host Chromium UA"));
    byte[] beforeRepeatedActivation=raw(context);ChromiumFingerprintStore.activate(context,retried.identity,retried.revision,binding);
    check("Repeated activate of current exact binding is idempotent",ChromiumFingerprintStore.lastReceipt(context,retried.identity,retried.revision,binding).optString("activationNonce").equals(current.optString("activationNonce")));unchanged("Repeated activation does not rewrite vault",context,beforeRepeatedActivation);
    for(String state:new String[]{"saved","requested","native-readback","page-observed","unsupported","failed"}){
      JSONObject value=ChromiumFingerprintStore.record(context,retried.identity,retried.revision,binding,J.obj("field",J.obj("state",state)));
      check("Known field state remains exact "+state,value.getJSONObject("fields").getJSONObject("field").optString("state").equals(state));
    }
    rejects("Unknown receipt field state is rejected",()->ChromiumFingerprintStore.record(context,retried.identity,retried.revision,binding,J.obj("ua",J.obj("state","fully-protected"))));
    byte[] validReceiptBytes=raw(context);JSONObject tooMany=new JSONObject();for(int i=0;i<97;i++)tooMany.put("field"+i,J.obj("state","requested"));
    rejects("Receipt field count is bounded",()->ChromiumFingerprintStore.record(context,retried.identity,retried.revision,binding,tooMany));
    rejects("Receipt field names are restricted",()->ChromiumFingerprintStore.record(context,retried.identity,retried.revision,binding,J.obj("1invalid",J.obj("state","requested"))));
    rejects("Receipt cannot be empty",()->ChromiumFingerprintStore.record(context,retried.identity,retried.revision,binding,new JSONObject()));
    StringBuilder fieldBody=new StringBuilder();for(int i=0;i<25000;i++)fieldBody.append('x');JSONObject fieldLarge=J.obj("ua",J.obj("state","native-readback","value",fieldBody.toString()));
    rejects("Receipt field payload is bounded",()->ChromiumFingerprintStore.record(context,retried.identity,retried.revision,binding,fieldLarge));unchanged("Invalid receipt attempts preserve exact acknowledged bytes",context,validReceiptBytes);
    context.vault.failPut=true;rejects("Receipt publication failure is surfaced",()->ChromiumFingerprintStore.record(context,retried.identity,retried.revision,binding,fields()));unchanged("Failed receipt write preserves predecessor",context,validReceiptBytes);
    check("Receipt publication failure keeps active scope retryable",ChromiumFingerprintStore.record(context,retried.identity,retried.revision,binding,fields()).length()>0);
    ChromiumFingerprintStore.Binding newer=new ChromiumFingerprintStore.Binding("com.host.webview","157.0.1","runtime-0123456789abcdef",3,8);
    check("Navigation mismatch does not return current receipt",ChromiumFingerprintStore.lastReceipt(context,retried.identity,retried.revision,newer).length()==0);
    rejects("Inactive navigation cannot publish receipt",()->ChromiumFingerprintStore.record(context,retried.identity,retried.revision,newer,fields()));
    ChromiumFingerprintStore.retire(context,retried.identity,newer);check("Retiring stale binding preserves active scope",ChromiumFingerprintStore.lastReceipt(context,retried.identity,retried.revision,binding).length()>0);
    ChromiumFingerprintStore.retire(context,retried.identity,binding);check("Retiring matching runtime clears current receipt",ChromiumFingerprintStore.lastReceipt(context,retried.identity,retried.revision,binding).length()==0);
    rejects("Retired runtime cannot publish receipt",()->ChromiumFingerprintStore.record(context,retried.identity,retried.revision,binding,fields()));
    ChromiumFingerprintStore.activate(context,retried.identity,retried.revision,binding);check("Same binding reactivated after retire cannot revive old receipt",ChromiumFingerprintStore.lastReceipt(context,retried.identity,retried.revision,binding).length()==0);
    JSONObject reactivated=ChromiumFingerprintStore.record(context,retried.identity,retried.revision,binding,fields());check("Reactivated runtime gets a new activation nonce",!reactivated.getString("activationNonce").equals(current.getString("activationNonce")));
    byte[] beforeRotate=raw(context);context.vault.failPut=true;
    rejects("Rotation publication failure is surfaced",()->ChromiumFingerprintStore.rotate(context,retried.identity,retried.revision));unchanged("Failed rotation leaves old durable state unchanged",context,beforeRotate);
    check("Failed rotation retains current acknowledgement",ChromiumFingerprintStore.lastReceipt(context,retried.identity,retried.revision,binding).length()>0);
    ChromiumFingerprintStore.State rotated=ChromiumFingerprintStore.rotate(context,retried.identity,retried.revision);
    check("Explicit rotation keeps desired fields and changes seed/revision",rotated.revision==retried.revision+1&&!rotated.seed.equals(retried.seed)&&canonical(rotated.spec()).equals(canonical(retried.spec())));
    check("Rotation clears durable and runtime receipt",rawObject(context).getJSONObject("receipt").length()==0&&ChromiumFingerprintStore.lastReceipt(context,rotated.identity,rotated.revision,binding).length()==0);
    rejects("Rotated runtime needs fresh activation",()->ChromiumFingerprintStore.record(context,rotated.identity,rotated.revision,binding,fields()));rejects("Rotation has exact revision CAS",()->ChromiumFingerprintStore.rotate(context,retried.identity,retried.revision));
    for(String[] parts:new String[][]{{"","1","runtime"},{"pkg","","runtime"},{"pkg","1",""}})rejects("Binding requires provider and runtime identity "+Arrays.toString(parts),()->new ChromiumFingerprintStore.Binding(parts[0],parts[1],parts[2],1,1));
    rejects("Binding rejects negative surface generation",()->new ChromiumFingerprintStore.Binding("pkg","1","runtime",-1,1));rejects("Binding rejects negative navigation generation",()->new ChromiumFingerprintStore.Binding("pkg","1","runtime",1,-1));
    StringBuilder longProvider=new StringBuilder();for(int i=0;i<257;i++)longProvider.append('p');rejects("Binding provider descriptor is bounded",()->new ChromiumFingerprintStore.Binding(longProvider.toString(),"1","runtime",1,1));
    generationAndOwner();malformed();
  }
  static void restart(String phase)throws Exception{
    TestContext context=context("restart");ChromiumFingerprintStore.Binding binding=binding();
    if(phase.equals("restart-seed")){
      ChromiumFingerprintStore.State initial=ChromiumFingerprintStore.load(context),saved=ChromiumFingerprintStore.save(context,initial.identity,initial.revision,spec("durable-restart"));ChromiumFingerprintStore.activate(context,saved.identity,saved.revision,binding);JSONObject receipt=ChromiumFingerprintStore.record(context,saved.identity,saved.revision,binding,fields());
      Files.write(root.resolve("restart-oracle.json"),J.obj("seed",saved.seed,"revision",saved.revision,"spec",saved.spec(),"processNonce",receipt.getString("processNonce")).toString().getBytes(StandardCharsets.UTF_8));check("First JVM stores exact current receipt",ChromiumFingerprintStore.lastReceipt(context,saved.identity,saved.revision,binding).length()>0);
    }else{
      JSONObject oracle=new JSONObject(new String(Files.readAllBytes(root.resolve("restart-oracle.json")),StandardCharsets.UTF_8));ChromiumFingerprintStore.State state=ChromiumFingerprintStore.load(context);
      check("Second JVM retains exact durable desired config and seed",state.seed.equals(oracle.getString("seed"))&&state.revision==oracle.getLong("revision")&&canonical(state.spec()).equals(canonical(oracle.getJSONObject("spec"))));
      check("Restart cannot expose old-process receipt before activation",ChromiumFingerprintStore.lastReceipt(context,state.identity,state.revision,binding).length()==0);
      ChromiumFingerprintStore.activate(context,state.identity,state.revision,binding);check("Even identical reactivated binding cannot revive old process receipt",ChromiumFingerprintStore.lastReceipt(context,state.identity,state.revision,binding).length()==0);
      JSONObject fresh=ChromiumFingerprintStore.record(context,state.identity,state.revision,binding,fields());check("Fresh second JVM acknowledgement has different process nonce",!fresh.getString("processNonce").equals(oracle.getString("processNonce"))&&ChromiumFingerprintStore.lastReceipt(context,state.identity,state.revision,binding).length()>0);
    }
  }
  public static void main(String[] args)throws Exception{root=Paths.get(args[1]);Files.createDirectories(root);if(args[0].equals("main"))run();else restart(args[0]);System.out.println(J.obj("status","passed","passed",checks.size(),"total",checks.size(),"phase",args[0],"checks",new JSONArray(checks)));}
}

final class TestContext extends Context {
  final Path directory;final ProfileCatalog catalog;final VaultFaults vault=new VaultFaults();
  TestContext(Path directory,EnvironmentSpec.Identity identity)throws Exception{this.directory=directory;Files.createDirectories(directory);catalog=new ProfileCatalog(identity);}
  @Override public Context getApplicationContext(){return this;}@Override public File getNoBackupFilesDir(){return directory.toFile();}
}
final class VaultFaults {boolean failPut,failRead;long puts;}
final class Profiles {static int slot(Context context){return ((TestContext)context).catalog.current.slot;}}
final class ProfileCatalog {
  EnvironmentSpec.Identity current;final Object gate=new Object();ProfileCatalog(EnvironmentSpec.Identity current){this.current=current;}
  static ProfileCatalog get(Context context){return ((TestContext)context).catalog;}EnvironmentSpec.Identity identity(int slot)throws IOException{if(current.slot!=slot)throw new IOException("Wrong slot");return current;}
  interface IdentityAction<T>{T run()throws Exception;}
  <T>T withIdentity(EnvironmentSpec.Identity expected,IdentityAction<T> action)throws Exception{synchronized(gate){if(!current.equals(expected))throw new IOException("Environment identity changed");return action.run();}}
}
final class SecretStore {
  final TestContext context;SecretStore(Context context){this.context=(TestContext)context;}
  Path file(String key){if(!key.matches("[a-z-]+"))throw new IllegalArgumentException("Host vault key");return context.directory.resolve(key+".host-vault");}
  byte[] get(String key)throws IOException{if(context.vault.failRead)throw new IOException("Injected vault read/decryption boundary failure");Path file=file(key);return Files.exists(file)?Files.readAllBytes(file):null;}
  void put(String key,byte[] bytes)throws IOException{context.vault.puts++;if(context.vault.failPut){context.vault.failPut=false;throw new IOException("Injected prepublication vault failure");}Path file=file(key),temporary=Files.createTempFile(context.directory,"vault-",".tmp");try{Files.write(temporary,bytes);Files.move(temporary,file,StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);}finally{Files.deleteIfExists(temporary);}}
  void raw(byte[] bytes)throws IOException{Files.write(file(ChromiumFingerprintStore.STORE),bytes);}
}
