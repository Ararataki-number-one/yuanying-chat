package local.pocketchat;

import android.os.SystemClock;
import org.json.*;
import org.mozilla.geckoview.GeckoSession;

/** Actual retained SDK document; controlled timeout/probe faults, no ChatGPT account. */
final class ChatPageContinuityIntegration {
  final GeckoIntegrationTestActivity activity;final ChatSession owner;
  final GeckoIntegrationTestActivity.FixtureView web;final long serial;
  final JSONArray checks=new JSONArray(),snapshots=new JSONArray();final JSONObject previousPending,previousState;
  final String previousDriver,previousIdentity,previousRawPending;final boolean previousConfigured,previousPendingStored,previousTransfer,previousCapture;
  final int previousChoosers,previousPreparations;final long previousStateEpoch;
  GeckoSession sdk;JSONObject before;String target,pendingBytes;boolean finished,finishing,cookieCleaned;
  long deadline;int stage;
  ChatPageContinuityIntegration(GeckoIntegrationTestActivity a,long command){
    activity=a;owner=a.session;web=(GeckoIntegrationTestActivity.FixtureView)owner.web;serial=command;
    previousPending=owner.pending;previousState=owner.state;previousDriver=owner.driver;
    previousIdentity=owner.appliedIdentity;previousConfigured=owner.prefs.getBoolean("networkConfigured",false);
    previousRawPending=owner.prefs.getString("pending",null);previousPendingStored=owner.prefs.contains("pending");
    previousTransfer=owner.transferActive;previousCapture=owner.configurationCapture;
    previousChoosers=owner.resourceChoosers;previousPreparations=owner.resourceFilePreparations;previousStateEpoch=owner.stateEpoch;
  }
  static void run(GeckoIntegrationTestActivity a,long command){new ChatPageContinuityIntegration(a,command).start();}
  boolean current(){return !finished&&serial==activity.run;}
  void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));if(!pass)throw new IllegalStateException(name);}
  void step(Runnable work){if(!current())return;try{work.run();}catch(Exception error){finish(error);}}
  void later(Runnable work,long delay){owner.handler.postDelayed(()->step(work),delay);}
  void eval(String code,java.util.function.Consumer<JSONObject> next){web.evaluateJavascript(code,raw->step(()->{JSONObject value=J.parse(raw);if(value.length()==0)throw new IllegalStateException("Actual continuity bridge unavailable");next.accept(value);}));}
  String snapshot(){return "(()=>({url:location.href,document:window.__continuityDocument,draft:document.getElementById('prompt-textarea')?.value||'',cookie:document.cookie,sends:window.__continuitySends||0,busy:!document.getElementById('stop').hidden}))()";}
  void record(String phase,JSONObject document){snapshots.put(J.obj("phase",phase,"elapsed",SystemClock.elapsedRealtime(),"document",document,"session",System.identityHashCode(web.current),"nativeUrl",web.locations.get(web.current),"open",web.current!=null&&web.current.isOpen(),"visible",web.hasVisibleDocument(),"loads",web.continuityLoads,"stops",web.continuityStops,"connectionEpoch",owner.connectionEpoch,"navigationEpoch",owner.navigationEpoch,"recoveryScheduled",owner.recoveryScheduled,"networkReady",owner.networkReady,"guardAllowed",owner.guard.allowed(),"choosers",owner.resourceChoosers,"preparations",owner.resourceFilePreparations,"transfer",owner.transferActive,"configurationCapture",owner.configurationCapture));}
  void start(){step(()->{
    target="http://127.0.0.1:8765/browser-continuity?command="+serial;
    web.loadUrl(target);deadline=SystemClock.elapsedRealtime()+20000;later(this::ready,100);
  });}
  void ready(){
    if(!target.equals(web.getUrl())||!web.hasVisibleDocument()||web.ports.get(web.current)==null){if(SystemClock.elapsedRealtime()>deadline)throw new IllegalStateException("Continuity SDK document did not become usable");later(this::ready,100);return;}
    eval("(()=>{document.getElementById('prompt-textarea').value='preserve unsent continuity draft';document.cookie='continuity-token=controlled;path=/';window.__continuityDocument=String(performance.timeOrigin)+'-'+Math.random();return "+snapshot()+";})()",value->{
      before=value;sdk=web.current;record("before",value);check("Continuity starts in an actual visible Gecko document",web.hasVisibleDocument()&&sdk.isOpen()&&target.equals(value.optString("url")));
      owner.driver=ContinuityDriverAdapter.adapt(owner.driver,target);
      web.continuityUrl=target;web.chooserOrigin=true;web.continuityTracing=true;web.continuityResults=new JSONArray();web.continuityLoads=web.continuityStops=0;
      owner.prefs.edit().putBoolean("networkConfigured",true).commit();owner.appliedIdentity=owner.networkIdentity();
      owner.manualAttention=false;owner.recoveryScheduled=false;owner.recoveryAttempt=0;
      owner.beginNavigation(MainActivity.ORIGIN,"controlled DOM readiness wait");long epoch=owner.navigationEpoch;
      owner.navigationTimeout(epoch);owner.handler.removeCallbacks(owner.tick);
      check("Visible readiness timeout schedules no reconnect or new document",owner.navigating&&!owner.navigationFailed&&!owner.recoveryScheduled&&!owner.manualAttention&&owner.networkReady&&web.continuityLoads==0&&web.continuityStops==0);
      owner.navigationTimeout(epoch-1);check("Stale readiness timeout leaves the current document epoch unchanged",owner.navigationEpoch==epoch&&web.current==sdk);
      recover(0);
    });
  }
  void recover(int index){
    stage=index;
    owner.pending=J.obj("id","continuity-"+serial,"kind","web","engine","gecko","expectedUrl",MainActivity.ORIGIN,"confirmedUrl",MainActivity.ORIGIN,"prompt","controlled task","attempted",true);pendingBytes=owner.pending.toString();
    owner.prefs.edit().putString("pending",pendingBytes).commit();
    owner.state=J.obj("url",MainActivity.ORIGIN,"busy",index==0);owner.stateEpoch=owner.navigationEpoch;
    owner.transferActive=true;owner.resourceChoosers=1;owner.resourceFilePreparations=1;owner.configurationCapture=true;
    eval("(()=>{document.getElementById('stop').hidden="+(index!=0)+";return {ready:true}})()",unused->{
      owner.openConnection(true,false);owner.handler.removeCallbacks(owner.tick);
      check((index==0?"Busy":"Unavailable HEAD")+" recovery keeps admission and the current native document",owner.networkReady&&!owner.connecting&&owner.guard.allowed()&&!owner.navigating&&!owner.recoveryScheduled&&web.current==sdk&&web.continuityLoads==0&&web.continuityStops==0);
      deadline=SystemClock.elapsedRealtime()+6000;later(this::afterProbe,3800);
    });
  }
  void afterProbe(){
    owner.handler.removeCallbacks(owner.tick);
    if(stage==1&&owner.trace.recoveryProbe<0&&SystemClock.elapsedRealtime()<deadline){later(this::afterProbe,100);return;}
    if(stage==1)check("Failed HEAD ran through the actual Gecko fetch probe",owner.trace.recoveryProbe>=0);
    eval(snapshot(),after->{
      record(stage==0?"after-busy":"after-head-failure",after);
      check((stage==0?"Busy":"Failed HEAD")+" retains actual document, unsent text, cookies and persisted task",before.optString("document").equals(after.optString("document"))&&before.optString("draft").equals(after.optString("draft"))&&after.optString("cookie").contains("continuity-token=controlled")&&after.optInt("sends")==0&&pendingBytes.equals(owner.pending.toString())&&pendingBytes.equals(owner.prefs.getString("pending",""))&&web.current==sdk&&web.continuityLoads==0&&web.continuityStops==0);
      check("Recovery retains chooser, preparation, transfer and edit ownership "+stage,owner.transferActive&&owner.resourceChoosers==1&&owner.resourceFilePreparations==1&&owner.configurationCapture);
      if(stage==0){recover(1);return;}
      JSONObject busyProbe=web.continuityResults.length()>0?web.continuityResults.optJSONObject(0).optJSONObject("result"):null;
      JSONObject headProbe=web.continuityResults.length()>1?web.continuityResults.optJSONObject(1).optJSONObject("result"):null;
      check("Both fault results are real failed observations, with only HEAD carrying connection timing",web.continuityResults.length()==2&&busyProbe!=null&&headProbe!=null&&!busyProbe.optBoolean("ok")&&!busyProbe.has("probeMs")&&!headProbe.optBoolean("ok")&&headProbe.optDouble("probeMs",-1)>=0);
      // A genuinely empty SDK document still offers explicit retry, without
      // converting a DOM deadline into automatic network reconstruction.
      eval("(()=>{document.cookie='continuity-token=;Max-Age=0;path=/';return {cookie:document.cookie}})()",clean->{
        cookieCleaned=!clean.optString("cookie").contains("continuity-token=");check("Only the owned continuity cookie is retired",cookieCleaned&&clean.optString("cookie").equals(before.optString("cookie").replaceAll("(^|; )continuity-token=controlled(?=; |$)","").replaceAll("^; |; $","")));
        web.chooserOrigin=false;web.continuityTracing=false;web.current.loadUri("about:blank");deadline=SystemClock.elapsedRealtime()+10000;later(this::empty,100);
      });
    });
  }
  void empty(){
    if(!"about:blank".equals(web.getUrl())||web.hasVisibleDocument()){if(SystemClock.elapsedRealtime()>deadline)throw new IllegalStateException("Real empty SDK document not observed");later(this::empty,100);return;}
    owner.beginNavigation(MainActivity.ORIGIN,"controlled empty readiness wait");owner.navigationTimeout(owner.navigationEpoch);owner.handler.removeCallbacks(owner.tick);
    check("Empty readiness timeout requires user retry without blocking the verified network",owner.navigationFailed&&!owner.navigating&&owner.manualAttention&&!owner.recoveryScheduled&&owner.networkReady&&owner.guard.allowed());
    finish(null);
  }
  void finish(Exception error){
    if(finished||finishing)return;finishing=true;
    if(!cookieCleaned&&target!=null&&target.equals(web.locations.get(web.current))&&web.ports.get(web.current)!=null){
      web.evaluateJavascript("(()=>{document.cookie='continuity-token=;Max-Age=0;path=/';return {cleaned:!document.cookie.includes('continuity-token=')}})()",raw->{cookieCleaned=J.parse(raw).optBoolean("cleaned");complete(error);});
      owner.handler.postDelayed(()->complete(error==null?new IllegalStateException("Owned cookie cleanup did not finish"):error),6000);
    }else complete(error);
  }
  void complete(Exception error){
    if(finished)return;finished=true;web.continuityTracing=false;web.continuityUrl="";web.chooserOrigin=false;
    owner.pending=previousPending;owner.state=previousState;owner.driver=previousDriver;owner.appliedIdentity=previousIdentity;
    owner.transferActive=previousTransfer;owner.resourceChoosers=previousChoosers;owner.resourceFilePreparations=previousPreparations;owner.configurationCapture=previousCapture;owner.stateEpoch=previousStateEpoch;
    owner.navigating=false;owner.navigationFailed=false;owner.manualAttention=false;owner.recoveryScheduled=false;owner.recoveryToken++;
    android.content.SharedPreferences.Editor editor=owner.prefs.edit().putBoolean("networkConfigured",previousConfigured);if(previousPendingStored)editor.putString("pending",previousRawPending);else editor.remove("pending");editor.commit();owner.handler.removeCallbacks(owner.tick);
    JSONObject result=J.obj("schema",1,"status",error==null?"passed":"failed","actualAndroidExecution",true,"actualGeckoExecution",true,"checks",checks,"checkCount",checks.length(),"snapshots",snapshots,"probeResults",web.continuityResults,"ownedCookieCleaned",cookieCleaned,"resourcesRestored",owner.resourceChoosers==previousChoosers&&owner.resourceFilePreparations==previousPreparations&&owner.transferActive==previousTransfer&&owner.configurationCapture==previousCapture,"persistedPendingRestored",owner.prefs.contains("pending")==previousPendingStored&&java.util.Objects.equals(previousRawPending,owner.prefs.getString("pending",null)),"readinessNoReload",error==null,"busyRecoveryPreserved",error==null,"failedProbePreserved",error==null,"emptyTimeoutManualOnly",error==null,"faults",J.obj("readinessDeadline","direct invocation of production navigationTimeout; no elapsed-time claim","busy","rendered stop button in actual controlled DOM","head","controlled server lacks HEAD support (HTTP 501); actual Gecko fetch"),"scope","Actual SDK document/cookie/draft and production ChatSession paths. Timeout invoked directly; external route and busy/HEAD fault are controlled. No real ChatGPT login, WAN speed or physical-device acceptance.");
    if(error!=null)DownloadTasks.put(result,"error",error.toString());
    activity.event(serial,error==null?"pageContinuity":"error",result);
  }
}
