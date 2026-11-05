package local.pocketchat;

import java.io.*;
import java.util.*;
import java.util.function.*;
import org.json.*;

/** Immutable cold boot per environment. Saving desired state never mutates a live TLS runtime. */
final class GeckoTlsController {
  interface NativeAccess {
    boolean current();
    void configure(GeckoTlsSpec desired,Consumer<Readback> success,Consumer<Throwable> failure);
    void read(Consumer<Readback> success,Consumer<Throwable> failure);
  }
  static final class Readback {
    final int configuredMin,configuredMax,defaultMin,defaultMax;final boolean hasUserMin,hasUserMax,rfpPriority,h2Enabled,h3Enabled;
    Readback(int min,int max,int defMin,int defMax,boolean userMin,boolean userMax,boolean rfp,boolean h2,boolean h3){configuredMin=min;configuredMax=max;defaultMin=defMin;defaultMax=defMax;hasUserMin=userMin;hasUserMax=userMax;rfpPriority=rfp;h2Enabled=h2;h3Enabled=h3;}
  }
  static final class Boot {
    final GeckoTlsStore.State desired;final File root,profile,config;final GeckoTlsProfile.Preparation preparation;final String runtimeNonce=nonce();final boolean startupReconciled=true;private boolean claimed;
    Boot(GeckoTlsStore.State state,File root,GeckoTlsProfile.Preparation preparation){this.preparation=preparation;desired=state;this.root=root;profile=new File(root,"gecko-browser");config=new File(root,"gecko-browser.yaml");}
  }
  private static final String PROCESS_NONCE=nonce();private static volatile boolean runtimeEverCreated;
  final ChatSession session;private final Set<Runnable> listeners=new HashSet<>();
  private GeckoTlsStore.State desired;private Boot boot;private Object runtime;private NativeAccess access;private Readback readback;
  private boolean preparing,retired,ready,refreshPending;private String issue="",failureCode="";private long operation,refreshSerial;
  GeckoTlsController(ChatSession session){this.session=session;}
  GeckoTlsStore.State snapshot(){return desired;}
  void addListener(Runnable listener){listeners.add(listener);}void removeListener(Runnable listener){listeners.remove(listener);}
  private void changed(){for(Runnable listener:new ArrayList<>(listeners))listener.run();}
  private boolean identity(GeckoTlsStore.State value){return value!=null&&!session.deleted&&value.identity.slot==Profiles.slot(session.context)&&value.identity.generation==session.environmentGeneration&&value.identity.environmentId.equals(session.environmentId);}
  void desiredSaved(GeckoTlsStore.State value){if(!identity(value)||desired!=null&&value.revision<desired.revision)return;desired=value;changed();}
  void prepareStartup(Consumer<Boot> completed){
    if(preparing||boot!=null||retired||runtimeEverCreated){completed.accept(null);return;}preparing=true;long serial=++operation;changed();
    session.environmentIo.execute(()->{
      Boot prepared=null;String failure="";try{
        if(Profiles.processSlot()!=Profiles.slot(session.context))throw new IOException("TLS environment process changed");
        File root=GeckoCpuProfile.storage(session.context).root;GeckoTlsStore.State state=GeckoTlsStore.load(session.context);if(!identity(state))throw new IOException("TLS environment changed");
        prepared=GeckoTlsStore.withCurrent(session.context,state.identity,state.revision,()->{
          if(runtimeEverCreated||!root.equals(GeckoCpuProfile.storage(session.context).root))throw new IOException("TLS cold snapshot changed");
          GeckoTlsProfile.Preparation receipt=GeckoTlsProfile.prepare(root,new File(root,"gecko-browser"),state.spec);return new Boot(state,root,receipt);
        });
      }catch(Exception unavailable){String message=unavailable.getMessage();failure=message!=null&&message.matches("TLS [a-zA-Z .]+")?message.substring(4).replace(' ','-').toLowerCase(Locale.ROOT):"desired-or-profile-prepare-failed";}
      Boot result=prepared;String safe=failure;session.handler.post(()->{
        if(retired||session.deleted||serial!=operation)return;preparing=false;
        if(result==null||!identity(result.desired)||runtimeEverCreated){failureCode=safe.isEmpty()?"cold-identity-retired":safe;issue="TLS 冷启动配置未能安全准备；原配置保留，尚未启动新引擎";changed();completed.accept(null);return;}
        boot=result;if(desired==null||desired.revision<=result.desired.revision)desired=result.desired;changed();completed.accept(result);
      });
    });
  }
  boolean claimRuntime(Boot expected){if(expected==null||retired||runtimeEverCreated||boot!=expected||!identity(expected.desired))return false;runtimeEverCreated=true;expected.claimed=true;return true;}
  boolean acceptsNativeWork(Object actual){return actual!=null&&!retired&&!session.deleted&&runtime==actual&&boot!=null&&identity(boot.desired)&&(preparing||ready);}
  void attachRuntime(Boot expected,Object actual,NativeAccess nativeAccess,Consumer<Boolean> completed){
    if(expected==null||!expected.claimed||retired||boot!=expected||actual==null||runtime!=null||nativeAccess==null||!identity(expected.desired)){completed.accept(false);return;}
    runtime=actual;access=nativeAccess;preparing=true;long serial=++operation;changed();
    session.handler.postDelayed(()->{if(current(expected,actual,serial)&&!ready)fail("原生 TLS 协议确认超时，已暂停打开新网页",completed);},15000);
    try{nativeAccess.configure(expected.desired.spec,value->session.handler.post(()->{
      if(!current(expected,actual,serial)||!preparing)return;if(!valid(expected,value)){fail("原生 TLS 协议与冷启动配置不一致，已暂停打开新网页",completed);return;}
      session.environmentIo.execute(()->{boolean valid=false;try{valid=ProfileCatalog.get(session.context).withIdentity(expected.desired.identity,()->true);}catch(Exception unavailable){}
        boolean admitted=valid;session.handler.post(()->{if(!current(expected,actual,serial)||!preparing)return;if(!admitted){fail("TLS 配置所属环境已变化，已暂停打开新网页",completed);return;}
          readback=value;preparing=false;ready=true;issue="";failureCode="";changed();if(refreshPending)refreshNative();completed.accept(true);
        });
      });
    }),error->session.handler.post(()->{if(current(expected,actual,serial))fail("当前内核尚未确认原生 TLS 协议，已暂停打开新网页",completed);}));}
    catch(RuntimeException unavailable){fail("当前内核的原生 TLS 接口暂不可用，已暂停打开新网页",completed);}
  }
  private boolean accessCurrent(){try{return access!=null&&access.current();}catch(RuntimeException unavailable){return false;}}
  private boolean current(Boot expected,Object actual,long serial){return expected!=null&&!retired&&!session.deleted&&boot==expected&&runtime==actual&&serial==operation&&identity(expected.desired)&&accessCurrent();}
  private boolean valid(Boot expected,Readback value){return value!=null&&value.defaultMin>=3&&value.defaultMin<=value.defaultMax&&value.defaultMax<=4&&value.configuredMin==value.defaultMin&&value.configuredMax==value.defaultMax&&!value.hasUserMin&&!value.hasUserMax&&(expected.desired.spec.isDefault()||value.defaultMin==4&&value.defaultMax==4);}
  private void fail(String message,Consumer<Boolean> completed){if(!preparing)return;preparing=false;ready=false;readback=null;issue=message;failureCode="native-startup-unconfirmed";++operation;changed();completed.accept(false);}
  boolean readyFor(Object actual){return ready&&readback!=null&&!retired&&runtime==actual&&boot!=null&&identity(boot.desired)&&accessCurrent();}
  void protectionWillChange(){refreshPending=true;++refreshSerial;changed();}
  void refreshNative(){
    Boot expected=boot;Object actual=runtime;long serial=operation,readSerial=++refreshSerial;refreshPending=true;changed();if(!readyFor(actual))return;
    try{access.read(value->session.handler.post(()->{if(!current(expected,actual,serial)||!ready||readSerial!=refreshSerial)return;
      if(!valid(expected,value)){ready=false;readback=null;issue="原生 TLS 协议已变化，已暂停新的网页请求";}else{readback=value;refreshPending=false;}changed();
    }),error->session.handler.post(()->{if(current(expected,actual,serial)&&readSerial==refreshSerial){ready=false;readback=null;issue="原生 TLS 协议暂未回读，已暂停新的网页请求";changed();}}));}
    catch(RuntimeException unavailable){ready=false;readback=null;issue="原生 TLS 协议接口暂不可用，已暂停新的网页请求";changed();}
  }
  void retire(Object actual){if(runtime!=null&&runtime!=actual)return;retired=true;preparing=false;ready=false;readback=null;++operation;changed();}
  String summary(){return issue.isEmpty()?"正在确认当前环境的 Gecko 网页 TLS 协议，确认前暂停新请求":issue;}
  JSONObject status(){
    boolean verified=readback!=null&&readyFor(runtime),pending=desired!=null&&boot!=null&&(desired.revision!=boot.desired.revision||!desired.identity.equals(boot.desired.identity));
    return J.obj("schema",1,"engine","gecko","desiredRevision",desired==null?0:desired.revision,"desiredMode",desired==null?JSONObject.NULL:desired.spec.mode,
      "activeBootRevision",boot==null?0:boot.desired.revision,"activeBootMode",boot==null?JSONObject.NULL:boot.desired.spec.mode,"state",retired?"retired":!issue.isEmpty()?"failed":ready?"ready":preparing?"preparing":"loading","issue",issue,"failureCode",failureCode,"pendingColdStart",pending,
      "defaultMin",verified?readback.defaultMin:JSONObject.NULL,"defaultMax",verified?readback.defaultMax:JSONObject.NULL,"configuredMin",verified?readback.configuredMin:JSONObject.NULL,"configuredMax",verified?readback.configuredMax:JSONObject.NULL,"hasUserMin",verified?readback.hasUserMin:JSONObject.NULL,"hasUserMax",verified?readback.hasUserMax:JSONObject.NULL,
      "rfpPriority",verified&&!refreshPending?readback.rfpPriority:JSONObject.NULL,"h2Enabled",verified&&!refreshPending?readback.h2Enabled:JSONObject.NULL,"h3Enabled",verified&&!refreshPending?readback.h3Enabled:JSONObject.NULL,"nativeSettingReadback",verified,"startupReconciled",boot!=null&&boot.startupReconciled,"scope","runtime-wide","connectionScope","gecko-web-connections","independentDownloaderTlsCovered",false,"connectionCheckTlsCovered",false,"proxyEntranceTlsCovered",false,
      "processNonce",PROCESS_NONCE,"pid",android.os.Process.myPid(),"runtimeNonce",boot==null?JSONObject.NULL:boot.runtimeNonce,"environmentId",session.environmentId,"environmentGeneration",session.environmentGeneration,"slot",Profiles.slot(session.context),"wireObservationVerified",false,"fullTlsFingerprintEmulation",false,"quicWireVerified",false,"persistentWorkerColdStartVerified",false);
  }
  private static String nonce(){return UUID.randomUUID().toString().replace("-","");}
}
