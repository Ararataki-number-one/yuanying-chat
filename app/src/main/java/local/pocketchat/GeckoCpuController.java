package local.pocketchat;

import java.io.File;
import java.util.*;
import java.util.function.*;
import org.json.JSONObject;

/** Desired state and a single immutable cold-boot configuration. Saving a new
 * revision never changes this process's existing runtime, pages or workers. */
final class GeckoCpuController {
  interface NativeAccess {
    boolean current();
    void configure(Integer cap,Consumer<Readback> success,Consumer<Throwable> failure);
    void read(Consumer<Readback> success,Consumer<Throwable> failure);
  }
  static final class Readback {
    final int configuredCap,defaultCap;final boolean hasUserValue,rfpPriority;
    Readback(int configuredCap,int defaultCap,boolean hasUserValue,boolean rfpPriority){this.configuredCap=configuredCap;this.defaultCap=defaultCap;this.hasUserValue=hasUserValue;this.rfpPriority=rfpPriority;}
  }
  static final class Boot {
    final GeckoCpuStore.State desired;final String runtimeNonce=nonce();
    final boolean startupReconciled;final File profile,config;
    Boot(GeckoCpuStore.State desired,File root){this.desired=desired;startupReconciled=true;profile=new File(root,"gecko-browser");config=new File(root,"gecko-browser.yaml");}
  }
  private static final String PROCESS_NONCE=nonce();
  private static final Set<String> STARTUP_REASONS=new HashSet<>(Arrays.asList("CPU environment process mismatch","CPU environment changed","CPU cold snapshot changed",
    "CPU storage anchor","CPU profile root path",
    "CPU profile root link","CPU profile path","CPU profile directory","CPU profile link","CPU profile temporary exists","CPU profile changed",
    "CPU profile preference link","CPU profile preference bound","CPU profile preference ambiguous","CPU user.js override unsupported","CPU config link","CPU config temporary exists"));
  private static volatile boolean runtimeEverCreated;
  final ChatSession session;
  private final Set<Runnable> listeners=new HashSet<>();
  private GeckoCpuStore.State desired;private Boot boot;private Object runtime;private NativeAccess access;
  private Readback readback;private boolean preparing,retired,ready,refreshPending;private String issue="",failureCode="";private long operation,refreshSerial;
  GeckoCpuController(ChatSession session){this.session=session;}
  GeckoCpuStore.State snapshot(){return desired;}
  void addListener(Runnable listener){listeners.add(listener);}
  void removeListener(Runnable listener){listeners.remove(listener);}
  private void changed(){for(Runnable listener:new ArrayList<>(listeners))listener.run();}
  private boolean identity(GeckoCpuStore.State state){return state!=null&&!session.deleted&&state.identity.slot==Profiles.slot(session.context)&&state.identity.generation==session.environmentGeneration&&state.identity.environmentId.equals(session.environmentId);}
  void desiredSaved(GeckoCpuStore.State state){
    if(!identity(state)||desired!=null&&state.revision<desired.revision)return;
    // No native call, page reload, task cancellation or process restart here.
    desired=state;changed();
  }
  void prepareStartup(Consumer<Boot> completed){
    if(preparing||boot!=null||retired||runtimeEverCreated){completed.accept(null);return;}
    preparing=true;long serial=++operation;changed();
    session.environmentIo.execute(()->{
      Boot prepared=null;String preparationFailure="";try{
        if(Profiles.processSlot()!=Profiles.slot(session.context))throw new IllegalStateException("CPU environment process mismatch");
        File root=GeckoCpuProfile.storage(session.context).root;
        GeckoCpuStore.State state=GeckoCpuStore.load(session.context);
        if(!identity(state))throw new IllegalStateException("CPU environment changed");
        prepared=GeckoCpuStore.withCurrent(session.context,state.identity,state.revision,()->{
          if(runtimeEverCreated)throw new IllegalStateException("CPU cold snapshot changed");
          if(!root.equals(GeckoCpuProfile.storage(session.context).root))throw new IllegalStateException("CPU cold snapshot changed");
          GeckoCpuProfile.prepare(root,new File(root,"gecko-browser"),state.spec);return new Boot(state,root);
        });
      }catch(Exception unavailable){String message=unavailable.getMessage();preparationFailure=STARTUP_REASONS.contains(message)?message.substring(4).replace(' ','-').toLowerCase(Locale.ROOT):"desired-or-profile-prepare-failed";}
      Boot result=prepared;String safeFailure=preparationFailure;session.handler.post(()->{
        if(retired||session.deleted||serial!=operation)return;preparing=false;
        if(result==null||!identity(result.desired)||runtimeEverCreated){failureCode=safeFailure.isEmpty()?"cold-identity-retired":safeFailure;issue="CPU 冷启动配置无法安全准备；原文件保留，尚未启动新引擎";changed();completed.accept(null);return;}
        boot=result;if(desired==null||desired.revision<=result.desired.revision)desired=result.desired;changed();completed.accept(result);
      });
    });
  }
  /** Called immediately before the sole native runtime creation in this process. */
  boolean claimRuntime(Boot expected){
    if(expected==null||retired||runtimeEverCreated||boot!=expected||!identity(expected.desired))return false;
    runtimeEverCreated=true;return true;
  }
  void attachRuntime(Boot expected,Object actual,NativeAccess nativeAccess,Consumer<Boolean> completed){
    if(expected==null||retired||boot!=expected||actual==null||runtime!=null||!identity(expected.desired)||nativeAccess==null){completed.accept(false);return;}
    runtime=actual;access=nativeAccess;long serial=++operation;preparing=true;changed();
    session.handler.postDelayed(()->{if(current(expected,actual,serial)&&!ready)fail("原生 CPU 偏好确认超时，已暂停打开新网页",completed);},15000);
    try{nativeAccess.configure(expected.desired.spec.capOrNull(),value->session.handler.post(()->{
      if(!current(expected,actual,serial)||!preparing)return;
      if(!valid(expected,value)){fail("原生 CPU 偏好与冷启动配置不一致，已暂停打开新网页",completed);return;}
      // A later desired revision remains pending. Only the immutable boot
      // revision is acknowledged; UUID/generation and native runtime stay fenced.
      session.environmentIo.execute(()->{
        boolean valid=false;try{valid=ProfileCatalog.get(session.context).withIdentity(expected.desired.identity,()->true);}catch(Exception unavailable){}
        boolean admitted=valid;session.handler.post(()->{
          if(!current(expected,actual,serial)||!preparing)return;
          if(!admitted){fail("CPU 配置所属环境已变化，已暂停打开新网页",completed);return;}
          readback=value;preparing=false;ready=true;issue="";failureCode="";changed();if(refreshPending)refreshNative();completed.accept(true);
        });
      });
    }),error->session.handler.post(()->{if(current(expected,actual,serial))fail("当前内核未确认 CPU 原生偏好，已暂停打开新网页",completed);}));}
    catch(RuntimeException unavailable){fail("当前内核未提供 CPU 原生偏好接口，已暂停打开新网页",completed);}
  }
  private boolean accessCurrent(){try{return access!=null&&access.current();}catch(RuntimeException unavailable){return false;}}
  private boolean current(Boot expected,Object actual,long serial){return expected!=null&&!retired&&!session.deleted&&boot==expected&&runtime==actual&&serial==operation&&identity(expected.desired)&&accessCurrent();}
  private boolean valid(Boot expected,Readback value){return value!=null&&value.defaultCap>0&&value.configuredCap==value.defaultCap&&!value.hasUserValue&&(expected.desired.spec.isAutomatic()||value.defaultCap==expected.desired.spec.cap);}
  private void fail(String message,Consumer<Boolean> completed){if(!preparing)return;preparing=false;ready=false;readback=null;issue=message;failureCode="native-startup-unconfirmed";++operation;changed();completed.accept(false);}
  boolean readyFor(Object actual){return ready&&readback!=null&&!retired&&runtime==actual&&boot!=null&&identity(boot.desired)&&accessCurrent();}
  void protectionWillChange(){refreshPending=true;++refreshSerial;changed();}
  void refreshNative(){
    Boot expected=boot;Object actual=runtime;long serial=operation,readSerial=++refreshSerial;
    refreshPending=true;changed();if(!readyFor(actual))return;
    try{access.read(value->session.handler.post(()->{
      if(!current(expected,actual,serial)||!ready||readSerial!=refreshSerial)return;
      if(!valid(expected,value)){ready=false;readback=null;issue="当前原生 CPU 偏好已变化，尚未确认当前运行时";}else{readback=value;refreshPending=false;}changed();
    }),error->session.handler.post(()->{if(current(expected,actual,serial)&&readSerial==refreshSerial){ready=false;readback=null;issue="原生 CPU 偏好暂未回读，已暂停新的网页请求";changed();}}));}catch(RuntimeException unavailable){ready=false;readback=null;issue="原生 CPU 偏好接口暂不可用，已暂停新的网页请求";changed();}
  }
  void retire(Object actual){if(runtime!=null&&runtime!=actual)return;retired=true;ready=false;readback=null;++operation;changed();}
  JSONObject status(){
    boolean verified=readback!=null&&readyFor(runtime),pending=desired!=null&&boot!=null&&(desired.revision!=boot.desired.revision||!desired.identity.equals(boot.desired.identity));
    return J.obj("schema",1,"engine","gecko","desiredRevision",desired==null?0:desired.revision,"desiredMode",desired==null?JSONObject.NULL:desired.spec.mode,
      "activeBootRevision",boot==null?0:boot.desired.revision,"activeBootMode",boot==null?JSONObject.NULL:boot.desired.spec.mode,
      "state",retired?"retired":!issue.isEmpty()?"failed":ready?"ready":preparing?"preparing":"loading","issue",issue,"failureCode",failureCode,"pendingColdStart",pending,
      "configuredCap",verified?readback.configuredCap:JSONObject.NULL,"defaultCap",verified?readback.defaultCap:JSONObject.NULL,
      "hasUserValue",verified?readback.hasUserValue:JSONObject.NULL,"rfpPriority",verified&&!refreshPending?readback.rfpPriority:JSONObject.NULL,
      "nativeSettingReadback",verified,"startupReconciled",boot!=null&&boot.startupReconciled,"scope","runtime-wide",
      "processNonce",PROCESS_NONCE,"pid",android.os.Process.myPid(),"runtimeNonce",boot==null?JSONObject.NULL:boot.runtimeNonce,
      "environmentId",session.environmentId,"environmentGeneration",session.environmentGeneration,"slot",Profiles.slot(session.context),
      "pageObservationVerified",false,"workerCoverageVerified",false,"serviceWorkerCoverageVerified",false,"persistentWorkerColdStartVerified",false);
  }
  private static String nonce(){return UUID.randomUUID().toString().replace("-","");}
}
