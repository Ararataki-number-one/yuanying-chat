package local.pocketchat;

import android.content.Context;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.Consumer;
import org.json.*;

/** Controller/native callback model only; original production sources are compiled verbatim. */
public final class ControllerHost {
  static final List<String> checks=new ArrayList<>();static Path root;
  interface Action{void run()throws Exception;}
  static void check(String name,boolean value){if(!value)throw new AssertionError(name);checks.add(name);}
  static void rejects(String name,Action work)throws Exception{boolean rejected=false;try{work.run();}catch(Exception expected){rejected=true;}check(name,rejected);}
  static byte[] bytes(String value){return value.getBytes(StandardCharsets.UTF_8);}
  static void profiles()throws Exception{
    String original="// Mozilla User Preferences\r\nuser_pref(\"privacy.resistFingerprinting\", true);\r\nuser_pref(\"dom.maxHardwareConcurrency\", 2);\r\nuser_pref(\"unrelated\", \"unchanged\");\n";
    String expected=original.replace("user_pref(\"dom.maxHardwareConcurrency\", 2);\r\n","");
    check("CPU removal preserves every unrelated UTF8 byte and original CRLF",Arrays.equals(GeckoCpuProfile.withoutCpu(bytes(original)),bytes(expected)));
    check("No matching key leaves complete profile bytes unchanged",Arrays.equals(GeckoCpuProfile.withoutCpu(bytes(expected)),bytes(expected)));
    check("No final newline is preserved",Arrays.equals(GeckoCpuProfile.withoutCpu(bytes("user_pref(\"other\", 7);")),bytes("user_pref(\"other\", 7);")));
    for(String bad:new String[]{"user_pref(\"dom.maxHardwareConcurrency\", 1);\nuser_pref(\"dom.maxHardwareConcurrency\", 2);\n","user_pref(\"dom.maxHardwareConcurrency\", -1);","user_pref(\"dom.maxHardwareConcurrency\", true);","// dom.maxHardwareConcurrency","user_pref(\"dom.maxHardwareConcurre\\u006ecy\", 2);","user_pref(\"other\", 1);user_pref(\"dom.maxHardwareConcurre\\u006ecy\", 2);"})rejects("Ambiguous duplicate or unexpected owned CPU preference fails closed",()->GeckoCpuProfile.withoutCpu(bytes(bad)));
    String huge="user_pref(\"unrelated\", \""+String.join("",Collections.nCopies(200000,"x"))+"\");\n";check("Large single native preference remains linear and byte-preserved",Arrays.equals(GeckoCpuProfile.withoutCpu(bytes(huge)),bytes(huge)));
    rejects("Malformed UTF8 cannot be silently normalized",()->GeckoCpuProfile.withoutCpu(new byte[]{(byte)0xc3,0x28}));
    rejects("Bounded profile rejects over4MiB",()->GeckoCpuProfile.withoutCpu(new byte[GeckoCpuProfile.MAX_BYTES+1]));
    Path base=root.resolve("profile-files");Files.createDirectories(base);File profile=base.resolve("gecko-browser").toFile();GeckoCpuProfile.prepare(base.toFile(),profile,GeckoCpuSpec.of("2"));
    Path prefs=profile.toPath().resolve("prefs.js");Files.write(prefs,bytes(original));GeckoCpuProfile.prepare(base.toFile(),profile,GeckoCpuSpec.automatic());
    check("Offline automatic removes staleUSER without inventing engine default",Arrays.equals(Files.readAllBytes(prefs),bytes(expected))&&!new String(Files.readAllBytes(base.resolve("gecko-browser.yaml")),StandardCharsets.UTF_8).contains(GeckoCpuProfile.PREF));
    check("Closed route remains in complete background generated config",new String(Files.readAllBytes(base.resolve("gecko-browser.yaml")),StandardCharsets.UTF_8).contains("network.proxy.socks_port: 9"));
    Path user=profile.toPath().resolve("user.js");
    for(String bad:new String[]{"user_pref(\"dom.maxHardwareConcurrency\", 1);","user_pref(\"dom.maxHardwareConcurre\\u006ecy\", 1);","user_pref(\"other\", 1);user_pref(\"dom.maxHardwareConcurre\\u006ecy\", 2);"}){
      Files.write(user,bytes(bad));byte[] before=Files.readAllBytes(prefs);rejects("user.js CPU or extra executable call cannot override startup policy",()->GeckoCpuProfile.prepare(base.toFile(),profile,GeckoCpuSpec.of("1")));check("Rejected user.js leaves persisted prefs untouched",Arrays.equals(before,Files.readAllBytes(prefs)));
    }
    Files.delete(user);Path external=root.resolve("external.js");Files.write(external,bytes(original));Files.delete(prefs);Files.createSymbolicLink(prefs,external);rejects("Symlink prefs cannot be replaced or followed",()->GeckoCpuProfile.prepare(base.toFile(),profile,GeckoCpuSpec.of("1")));check("Symlink target preserved",Arrays.equals(Files.readAllBytes(external),bytes(original)));Files.delete(prefs);
    rejects("Different profile path rejected",()->GeckoCpuProfile.prepare(base.toFile(),root.resolve("other-profile").toFile(),GeckoCpuSpec.of("1")));
  }
  static void controller()throws Exception{
    TestContext context=new TestContext(root.resolve("controller"));ChatSession session=new ChatSession(context);GeckoCpuStore.State initial=GeckoCpuStore.load(context),cap2=GeckoCpuStore.save(context,initial.identity,initial.revision,GeckoCpuSpec.of("2"));
    GeckoCpuController controller=new GeckoCpuController(session);int[] notifications={0};Runnable listener=()->notifications[0]++;controller.addListener(listener);final GeckoCpuController.Boot[] boot={null};
    check("Null boot cannot claim runtime or throw onUI",!controller.claimRuntime(null));List<Boolean> invalidGate=new ArrayList<>();controller.attachRuntime(null,new Object(),new FakeNative(),invalidGate::add);check("Null boot attachment fails closed with explicit gate",invalidGate.equals(Arrays.asList(false)));
    MainQueue.ui=true;try{controller.prepareStartup(value->boot[0]=value);}finally{MainQueue.ui=false;}
    check("UI call only schedules cold profile work",boot[0]==null&&!Files.exists(context.directory.resolve("gecko-browser"))&&session.environmentIo.tasks.size()==1);
    session.environmentIo.drain();session.handler.drain();check("Prepared boot retains exact durable revision",boot[0]!=null&&boot[0].desired.revision==cap2.revision&&boot[0].desired.spec.cap==2);
    check("Runtime may be claimed only once",controller.claimRuntime(boot[0])&&!controller.claimRuntime(boot[0]));
    Object runtime=new Object();FakeNative nativeApi=new FakeNative();List<Boolean> gates=new ArrayList<>();controller.attachRuntime(boot[0],runtime,nativeApi,gates::add);
    check("Runtime starts blocked until actual native callback",!controller.readyFor(runtime)&&nativeApi.configureCalls==1&&nativeApi.requested==2);
    GeckoCpuStore.State cap1=GeckoCpuStore.save(context,cap2.identity,cap2.revision,GeckoCpuSpec.of("1"));controller.desiredSaved(cap1);
    check("Saving while boot ACK is pending cannot hot apply",nativeApi.configureCalls==1&&nativeApi.readCalls==0&&controller.snapshot().revision==cap1.revision);
    nativeApi.configured.accept(new GeckoCpuController.Readback(2,2,false,false));session.handler.drain();session.environmentIo.drain();session.handler.drain();
    check("Frozen boot ACK survives a later pending desired revision",gates.equals(Arrays.asList(true))&&controller.readyFor(runtime));
    JSONObject status=controller.status();check("NativeACK is bound to old boot not new desired",status.getLong("activeBootRevision")==cap2.revision&&status.getLong("desiredRevision")==cap1.revision&&status.getString("activeBootMode").equals("2")&&status.getString("desiredMode").equals("1")&&status.getBoolean("pendingColdStart"));
    check("Native setting proof never becomes page orWorker proof",status.getBoolean("nativeSettingReadback")&&!status.getBoolean("workerCoverageVerified")&&!status.getBoolean("persistentWorkerColdStartVerified"));
    nativeApi.configured.accept(new GeckoCpuController.Readback(2,2,false,false));session.handler.drain();session.environmentIo.drain();session.handler.drain();check("Duplicate native callback cannot acknowledge boot twice",gates.size()==1);
    controller.desiredSaved(cap2);check("Out-of-order desired refresh cannot roll cache backwards",controller.snapshot()==cap1&&nativeApi.configureCalls==1);
    controller.refreshNative();check("Protection change invalidates stale RFP snapshot until fresh read",controller.status().isNull("rfpPriority")&&nativeApi.readCalls==1);
    nativeApi.read.accept(new GeckoCpuController.Readback(2,2,false,true));session.handler.drain();check("Fresh RFP readback records priority without claiming exposedcap",controller.status().getBoolean("rfpPriority")&&controller.status().getInt("configuredCap")==2);
    controller.refreshNative();Consumer<GeckoCpuController.Readback> earlier=nativeApi.read;controller.protectionWillChange();controller.refreshNative();earlier.accept(new GeckoCpuController.Readback(2,2,false,false));session.handler.drain();check("Old RFP callback cannot overwrite a newer protection boundary",controller.status().isNull("rfpPriority"));nativeApi.read.accept(new GeckoCpuController.Readback(2,2,false,true));session.handler.drain();check("Newest protection observation restores only fresh RFP snapshot",controller.status().getBoolean("rfpPriority"));
    check("Wrong runtime object cannot borrow another runtime receipt",!controller.readyFor(new Object()));
    controller.refreshNative();controller.retire(runtime);nativeApi.read.accept(new GeckoCpuController.Readback(2,2,false,false));session.handler.drain();check("Retired runtime rejects delayednative receipts",!controller.status().getBoolean("nativeSettingReadback")&&controller.status().getString("state").equals("retired"));
    final boolean[] denied={false};new GeckoCpuController(session).prepareStartup(value->denied[0]=value==null);check("Warm process cannot editprofile and create replacement coldboot",denied[0]);
    check("Listeners receive explicit state changes",notifications[0]>5);controller.removeListener(listener);
  }
  public static void main(String[] args)throws Exception{root=Paths.get(args[0]);profiles();controller();System.out.println(J.obj("status","passed","passed",checks.size(),"total",checks.size(),"checks",new JSONArray(checks),"actualAndroidExecution",false,"actualGeckoExecution",false));}
  static final class FakeNative implements GeckoCpuController.NativeAccess {
    int configureCalls,readCalls;Integer requested;Consumer<GeckoCpuController.Readback> configured,read;
    public boolean current(){return true;}public void configure(Integer cap,Consumer<GeckoCpuController.Readback> success,Consumer<Throwable> failure){configureCalls++;requested=cap;configured=success;}
    public void read(Consumer<GeckoCpuController.Readback> success,Consumer<Throwable> failure){readCalls++;read=success;}
  }
}
final class TestContext extends Context {
  final Path directory;final ProfileCatalog catalog=new ProfileCatalog();TestContext(Path directory)throws IOException{this.directory=directory;Files.createDirectories(directory);}
  public Context getApplicationContext(){return this;}public File getNoBackupFilesDir(){if(MainQueue.ui)throw new AssertionError("CPU disk directory on UI");return directory.toFile();}
}
final class ChatSession {
  final TestContext context;boolean deleted;final int environmentGeneration=1;final String environmentId="00000000-0000-0000-0000-000000000001";final ManualExecutor environmentIo=new ManualExecutor();final MainQueue handler=new MainQueue();ChatSession(TestContext context){this.context=context;}
}
final class MainQueue {static boolean ui;final List<Runnable> tasks=new ArrayList<>(),delayed=new ArrayList<>();void post(Runnable task){tasks.add(task);}void postDelayed(Runnable task,long ignored){delayed.add(task);}void drain(){ui=true;try{while(!tasks.isEmpty())tasks.remove(0).run();}finally{ui=false;}}}
final class ManualExecutor extends AbstractExecutorService {
  final List<Runnable> tasks=new ArrayList<>();public void execute(Runnable work){tasks.add(work);}void drain(){while(!tasks.isEmpty())tasks.remove(0).run();}public void shutdown(){}public List<Runnable> shutdownNow(){return Collections.emptyList();}public boolean isShutdown(){return false;}public boolean isTerminated(){return false;}public boolean awaitTermination(long timeout,TimeUnit unit){return false;}
}
final class Profiles {static int slot(Context context){return 1;}static int processSlot(){return 1;}}
final class ProfileCatalog {
  final EnvironmentSpec.Identity current=new EnvironmentSpec.Identity(1,1,"00000000-0000-0000-0000-000000000001");static ProfileCatalog get(Context context){return ((TestContext)context).catalog;}EnvironmentSpec.Identity identity(int slot){return current;}
  interface IdentityAction<T>{T run()throws Exception;}synchronized <T>T withIdentity(EnvironmentSpec.Identity expected,IdentityAction<T> action)throws Exception{if(!current.equals(expected))throw new IOException("Changed owner");return action.run();}
}
final class SecretStore {
  final TestContext context;SecretStore(Context context){this.context=(TestContext)context;}
  byte[] get(String name)throws IOException{Path file=context.directory.resolve(name+".vault");return Files.exists(file)?Files.readAllBytes(file):null;}
  void put(String name,byte[] value)throws Exception{Path temporary=Files.createTempFile(context.directory,"vault-",".tmp");Files.write(temporary,value);Files.move(temporary,context.directory.resolve(name+".vault"),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);}
}
