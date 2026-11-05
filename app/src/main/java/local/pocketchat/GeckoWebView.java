package local.pocketchat;

import android.content.*;
import android.graphics.Rect;
import android.graphics.Matrix;
import android.net.Uri;
import android.os.*;
import android.view.*;
import android.webkit.*;
import android.widget.FrameLayout;
import org.json.*;
import org.mozilla.geckoview.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.*;
import java.util.concurrent.*;

/** Keeps the existing session/business API while Gecko owns the real remote page. */
@SuppressWarnings("deprecation")
class GeckoWebView extends FrameLayout {
  final GeckoSettings metadata=new GeckoSettings();
  BrowserIdentitySpec identityPolicy;
  final MutableContextWrapper displayContext;
  static boolean wantsGecko(ChatSession session){return BrowserRuntimePolicy.usesGecko();}
  GeckoSettings getSettings(){return metadata;}
  Object nativeRuntimeIdentity(){return destroyed||!enabled||owner.deleted?null:runtime;}
  JSONObject nativeRuntimeCapabilities(){
    JSONObject value=GeckoPolicyAdapter.runtimeCapabilityStatus((GeckoRuntime)nativeRuntimeIdentity(),Build.VERSION.SDK_INT);
    try{value.put("environmentId",owner.environmentId);value.put("environmentGeneration",owner.environmentGeneration);value.put("configurationRevision",owner.identityAuditAppliedRevision());value.put("identityPolicyRevision",identityPolicyRevision);value.put("requestHeaderPolicy",J.parse(metadata.requestHeaderPolicy.toString()));value.put("timeZonePolicy",timeZoneStatus());value.put("cpuPolicy",owner.cpu.status());}catch(JSONException ignored){}
    return value;
  }
  void setHost(android.app.Activity activity){if(activity==null)closeExitIpPage();displayContext.setBaseContext(activity==null?owner.context:activity);}
  OnTouchListener touches;
  @Override public void setOnTouchListener(OnTouchListener listener){touches=listener;}
  @Override public boolean dispatchTouchEvent(MotionEvent event){
    if(zoomTarget!=null&&event.getActionMasked()==MotionEvent.ACTION_DOWN)cancelZoom();
    Context host=displayContext.getBaseContext();DesignChrome chrome=host instanceof MainActivity?((MainActivity)host).designChrome:null;
    // BrowserReading and the temporary network input fence keep ownership and priority.
    if(touches!=null&&touches.onTouch(this,event)){if(chrome!=null)chrome.cancelWebGesture();return true;}
    syncSurfaceOrigin();boolean handled=super.dispatchTouchEvent(event);
    if(chrome!=null){if(readingOwnerVisible())chrome.webTouch(event);else chrome.cancelWebGesture();}return handled;
  }
  void destroy(){
    if(destroyed)return;destroyed=true;owner.cpu.retire(runtime);retireTimeZones();requestHeadersInstalled=false;retireRequestHeaderPolicy();generalRestore=null;ChromiumRouteLease.removeListener(routeLeaseChanged);releaseGeneralRoutes();generalSessions.clear();deferredGeneralLoads.clear();closeExitIpPage();if(contentPermissions!=null)contentPermissions.close();
    cancelZoom();cancelProtectionTasks();nativeProtection.closed();protectionRestore=null;owner.handler.removeCallbacks(recovery);owner.handler.removeCallbacks(checkpoint);saveCheckpoint();
    callbacks.clear();cookieCallbacks.clear();appearanceSync.clear();
    appearanceLoads.clear();appearanceConnections.clear();appearanceDocuments.clear();staleAppearanceConnections.clear();
    if(surface!=null&&surface.getSession()!=null)surface.releaseSession();
    for(GeckoSession session:new ArrayList<>(locations.keySet()))if(session.isOpen())session.close();
    if(primary!=null&&primary.isOpen())primary.close();
    ports.clear();popups.clear();locations.clear();backStates.clear();pageScales.clear();measuredCompositors.clear();viewportWidths.clear();loadingTargets.clear();pendingLoads.clear();painted.clear();usable.clear();crashed.clear();states.clear();stateDraftRevisions.clear();
    routePort=null;ready=false;
    uploadWorker.execute(()->{for(GeckoUploadFiles.Selection files:uploadFiles)files.delete();uploadFiles.clear();});uploadWorker.shutdown();
  }

  static final String VERSION="GeckoView 157.0.1 · 输入同步修正";
  final ChatSession owner;
  GeckoView surface;GeckoRuntime runtime;WebExtension extension;GeckoSession primary,current;
  boolean addonDisabled;long addonStateSerial;
  GeckoCpuController.Boot cpuBoot;boolean cpuStartupRequested;
  interface ExitIpPageListener{void changed(String message);void closed();}
  ExitIpPageSession exitIpPage;int exitIpTopInset;
  boolean hasExitIpPage(){return exitIpPage!=null;}
  boolean readingOwnerVisible(){return exitIpPage==null&&surface!=null&&current!=null&&surface.getSession()==current;}
  String openExitIpPage(ExitIpPageListener listener){
    if(exitIpPage!=null)return "";String unavailable=ExitIpPageSession.unavailable(this);if(!unavailable.isEmpty())return unavailable;
    ExitIpPageSession page;try{page=new ExitIpPageSession(this,listener);}catch(RuntimeException unavailablePage){return "IP 查询页暂时无法打开，原聊天已保留。";}exitIpPage=page;
    try{
      cancelZoom();owner.reading.hideDisplay();page.aux.open(runtime);
      if(!page.fresh()){closeExitIpPage();return "当前环境已变化，请重新查询。";}
      if(surface.getSession()!=null)surface.releaseSession();surface.setScaleX(1);surface.setScaleY(1);surface.setSession(page.aux);
      current.setActive(true);page.aux.setActive(true);originKnown=false;requestLayout();
      prepareTimeZone(page.aux,ok->{if(exitIpPage!=page||!page.fresh())return;if(ok){page.aux.loadUri(ExitIpPageSession.URL);owner.handler.post(page.watch);}else closeExitIpPage();});return "";
    }catch(RuntimeException unavailablePage){closeExitIpPage();return "IP 查询页暂时无法打开，原聊天已保留。";}
  }
  boolean closeExitIpPage(){
    ExitIpPageSession page=exitIpPage;if(page==null)return false;exitIpPage=null;page.closed=true;owner.handler.removeCallbacks(page.watch);
    retireTimeZone(page.aux);
    if(surface!=null&&surface.getSession()==page.aux)surface.releaseSession();
    try{if(page.aux.isOpen()){page.aux.stop();page.aux.setActive(false);page.aux.close();}}catch(RuntimeException alreadyClosed){}
    exitIpTopInset=0;
    if(!destroyed&&surface!=null&&surface.getSession()==null&&runtime==page.runtime&&current==page.original&&current.isOpen()){
      surface.setPivotX(0);surface.setPivotY(0);surface.setScaleX(readingLayout);surface.setScaleY(readingLayout);
      if(getWidth()>0&&getHeight()>0){surface.measure(MeasureSpec.makeMeasureSpec(Math.round(getWidth()/readingLayout),MeasureSpec.EXACTLY),MeasureSpec.makeMeasureSpec(Math.round(getHeight()/readingLayout),MeasureSpec.EXACTLY));surface.layout(0,0,surface.getMeasuredWidth(),surface.getMeasuredHeight());}
      surface.setSession(current);current.setActive(!owner.browserPaused);
    }
    boolean changed=owner.reading.displayPageChanged;if(destroyed){owner.reading.displayHidden=false;owner.reading.displayPageChanged=false;}else owner.reading.showDisplay();
    if(!destroyed&&changed&&readingOwnerVisible())owner.reading.viewportMeasured(viewportWidths.getOrDefault(current,0f)*readingLayout);
    originKnown=false;requestLayout();page.listener.closed();return true;
  }
  GeckoContentPermissions contentPermissions;
  final ArrayList<GeckoSession> popups=new ArrayList<>();
  final Set<GeckoSession> generalSessions=Collections.newSetFromMap(new IdentityHashMap<>());
  final Map<GeckoSession,ChromiumRouteLease.Handle> generalRoutes=new IdentityHashMap<>();
  final Map<GeckoSession,String> deferredGeneralLoads=new IdentityHashMap<>();
  final Runnable routeLeaseChanged=this::queueGeneralRouteRetry;
  boolean generalRouteRetryQueued;ProtectionRestore generalRestore;
  boolean requestHeadersInstalled;
  HeaderPolicyRead headerPolicyRead;
  final Map<GeckoSession,TimeZoneGate> timeZoneGates=new IdentityHashMap<>();
  final Map<GeckoSession,String> timeZoneLoads=new IdentityHashMap<>();
  final Map<GeckoSession,Object> timeZoneIntents=new IdentityHashMap<>();
  final Map<GeckoSession,Object> nativeTimeZoneIntents=new IdentityHashMap<>();
  static final class TimeZoneGate {
    final String epoch=UUID.randomUUID().toString();long documentSerial;boolean preparing,ready,revalidating;
    final ArrayList<java.util.function.Consumer<Boolean>> waiting=new ArrayList<>();
    final ArrayList<java.util.function.Consumer<Boolean>> proofWaiting=new ArrayList<>();
    final ArrayList<java.util.function.Consumer<Boolean>> networkWaiting=new ArrayList<>();
  }
  static final class HeaderPolicyRead {
    final GeckoSession session;final WebExtension.Port port;final long revision,epoch,protection;
    final GeckoResult<String> userAgent;boolean observed;
    HeaderPolicyRead(GeckoSession session,WebExtension.Port port,long revision,long epoch,long protection,GeckoResult<String> userAgent){this.session=session;this.port=port;this.revision=revision;this.epoch=epoch;this.protection=protection;this.userAgent=userAgent;}
  }
  final Map<GeckoSession,WebExtension.Port> ports=new IdentityHashMap<>();
  final Map<GeckoSession,String> locations=new IdentityHashMap<>();
  final Map<GeckoSession,Boolean> backStates=new IdentityHashMap<>();
  final Map<GeckoSession,Float> pageScales=new IdentityHashMap<>(),viewportWidths=new IdentityHashMap<>();
  // Native scale belongs to the open compositor, not a DOM document. A new
  // document at the same scale need not produce another scroll notification.
  final Set<GeckoSession> measuredCompositors=Collections.newSetFromMap(new IdentityHashMap<>());
  final Map<GeckoSession,String> loadingTargets=new IdentityHashMap<>();
  final Set<GeckoSession> pendingLoads=Collections.newSetFromMap(new IdentityHashMap<>());
  final Set<GeckoSession> painted=Collections.newSetFromMap(new IdentityHashMap<>());
  final Set<GeckoSession> usable=Collections.newSetFromMap(new IdentityHashMap<>());
  final Set<GeckoSession> crashed=Collections.newSetFromMap(new IdentityHashMap<>());
  final Map<GeckoSession,GeckoSession.SessionState> states=new IdentityHashMap<>();
  final BrowserSessionStore sessionStore;final NetworkPoolIdentity connectionPool=new NetworkPoolIdentity();
  final ExecutorService uploadWorker=Executors.newSingleThreadExecutor();
  final List<GeckoUploadFiles.Selection> uploadFiles=new ArrayList<>();
  volatile GeckoUploadFiles.Cleanup lastUploadCleanup;
  void retireUnhandedUpload(GeckoUploadFiles.Selection files){new Thread(()->lastUploadCleanup=files.delete(),"upload-cleanup").start();}
  GeckoSession.SessionState startupState;long startupDraftRevision;final Map<GeckoSession,Long> stateDraftRevisions=new IdentityHashMap<>();
  boolean checkpointReady,checkpointRequested,routePrepared,identityPrepared,resourceDeferred;float readingLayout=1;long zoomEpoch,recoveryWindow;int contentRecoveries;
  ResourcePressureController.Admission resourceAdmission=ResourcePressureController.Admission.START;
  JSONObject sdkBuildIdentity;
  GeckoSession zoomTarget;long zoomStarted;float zoomX,zoomY,zoomRadius;int readingFocusScrolls;boolean readingFocusHadClipping;float readingFocusScrollDelta;
  final Runnable recovery=()->recoverClosed();
  final Runnable checkpoint=this::saveCheckpoint;
  final int[] surfaceOrigin=new int[2];
  final Matrix readingMatrix=new Matrix();final float[] readingValues=new float[9];
  private View originView;private GeckoSession originSession;
  private boolean originKnown;private int originX,originY,insetTop,insetRight,insetBottom,insetLeft;
  boolean nativePerfEnabled;long surfaceOriginChecks,surfaceOriginSyncs;
  final BrowserBridgeRequests callbacks,cookieCallbacks;WebExtension.Port routePort;String cookieStamp="";
  final WebAppearanceSync appearanceSync;
  final Map<GeckoSession,Long> appearanceLoads=new IdentityHashMap<>();
  final Map<WebExtension.Port,Long> appearanceConnections=new IdentityHashMap<>();
  final Map<WebExtension.Port,String> appearanceDocuments=new IdentityHashMap<>();
  final Set<WebExtension.Port> staleAppearanceConnections=Collections.newSetFromMap(new IdentityHashMap<>());
  long appearanceLoadSerial;
  interface ResponseDownload {void receive(WebResponse response);}
  ResponseDownload responseDownload;
  WebViewClient client;WebChromeClient chrome;DownloadListener download;
  final boolean enabled=true;
  boolean ready,failed,desktop,canBack,destroyed,privacyReady,fingerprintingProtected;int protectionLevel=-1,configuredProtection=-1,requestedProtection=-1;long identityPolicyRevision,protectionRequest;String url="",queued="";float scale=1;
  final NativeProtectionState nativeProtection=new NativeProtectionState();
  Runnable protectionTimeout,protectionRetry;
  ProtectionRestore protectionRestore;
  static final class ProtectionRestore {
    final GeckoSession session;final GeckoSession.SessionState state;final String url;final long draftRevision,navigation;
    ProtectionRestore(GeckoSession s,GeckoSession.SessionState value,String target,long draft,long epoch){session=s;state=value;url=target;draftRevision=draft;navigation=epoch;}
  }

  GeckoWebView(Context context,ChatSession session){
    super(context);owner=session;displayContext=new MutableContextWrapper(context);sessionStore=new BrowserSessionStore(context);
    setBackgroundColor(ReferenceUi.CHAT_BG);
    BrowserBridgeRequests.Timer timer=new BrowserBridgeRequests.Timer(){
      public void schedule(Runnable task,long delay){owner.handler.postDelayed(task,delay);}
      public void cancel(Runnable task){owner.handler.removeCallbacks(task);}
    };
    callbacks=new BrowserBridgeRequests(timer,"null");cookieCallbacks=new BrowserBridgeRequests(timer,null);
    appearanceSync=new WebAppearanceSync(timer,(port,message)->((WebExtension.Port)port).postMessage(message));
    ChromiumRouteLease.addListener(routeLeaseChanged);
    owner.handler.post(this::initialize);
  }
  boolean generalRouteReady(){return generalRoutes.keySet().containsAll(generalSessions);}
  boolean retainGeneralRoute(GeckoSession session,String target){
    if(session==null||destroyed||failed||crashed.contains(session))return false;
    if(GeckoNavigationPolicy.publicWeb(target)&&!MainActivity.chatUrl(target))generalSessions.add(session);
    if(!generalSessions.contains(session)||generalRoutes.containsKey(session))return true;
    if(destroyed||!owner.guard.allowed()||!protectionAllowsNetwork())return false;
    ChromiumRouteLease.Handle lease=ChromiumRouteLease.acquireSurface();if(lease==null)return false;
    generalRoutes.put(session,lease);return true;
  }
  void forgetGeneralRoute(GeckoSession session){generalSessions.remove(session);deferredGeneralLoads.remove(session);ChromiumRouteLease.Handle lease=generalRoutes.remove(session);if(lease!=null)lease.close();}
  void releaseGeneralRoutes(){ArrayList<ChromiumRouteLease.Handle> leases=new ArrayList<>(generalRoutes.values());generalRoutes.clear();for(ChromiumRouteLease.Handle lease:leases)lease.close();}
  void routeAdmissionChanged(){if(destroyed)return;if(owner.guard.blocked||!owner.guard.routeProtected())releaseGeneralRoutes();else queueGeneralRouteRetry();}
  void queueGeneralRouteRetry(){if(Looper.myLooper()!=owner.handler.getLooper()){owner.handler.post(this::queueGeneralRouteRetry);return;}if(destroyed||generalRouteRetryQueued)return;generalRouteRetryQueued=true;owner.handler.post(()->{generalRouteRetryQueued=false;retryGeneralRoutes();});}
  void retryGeneralRoutes(){
    if(destroyed||!owner.guard.allowed()||!protectionAllowsNetwork())return;
    for(GeckoSession session:new ArrayList<>(generalSessions))if(locations.containsKey(session)&&!crashed.contains(session)&&!retainGeneralRoute(session,locations.getOrDefault(session,"")))return;
    if(!generalRouteReady())return;
    ProtectionRestore restore=generalRestore;generalRestore=null;
    if(restore!=null&&restore.navigation==owner.navigationEpoch&&restore.session==current&&current.isOpen())restoreCheckpoint(current,restore.state,restore.url,restore.draftRevision);
    for(Map.Entry<GeckoSession,String> entry:new ArrayList<>(deferredGeneralLoads.entrySet())){
      GeckoSession session=entry.getKey();String target=entry.getValue();if(!target.equals(deferredGeneralLoads.remove(session)))continue;
      if(locations.containsKey(session)&&session.isOpen()&&!crashed.contains(session))loadSessionUri(session,target);
    }
    if(!queued.isEmpty()&&ready)loadUrl(queued);
  }
  boolean timeZoneSessionAlive(GeckoSession session){return !destroyed&&!owner.deleted&&session!=null&&session.isOpen()&&(locations.containsKey(session)||exitIpPage!=null&&exitIpPage.aux==session);}
  boolean timeZoneAllows(GeckoSession session){
    if(!timeZoneSessionAlive(session))return false;
    if(popups.contains(session))return owner.timeZone.popupAllowed();
    TimeZoneGate gate=timeZoneGates.get(session);return gate!=null&&gate.ready&&owner.timeZone.allowed(session,gate.epoch);
  }
  JSONObject timeZoneStatus(){
    TimeZoneGate gate=timeZoneGates.get(current);JSONObject value=J.parse((gate==null?owner.timeZone.status():owner.timeZone.status(current,gate.epoch)).toString());boolean prepared=timeZoneAllows(current);
    try{value.put("currentSessionPrepared",prepared);value.put("popupScope","custom-zone-popups-blocked");if(!prepared||popups.contains(current))value.put("nativeSettingReadback",false);}catch(JSONException ignored){}
    return value;
  }
  void retireTimeZone(GeckoSession session){
    timeZoneLoads.remove(session);timeZoneIntents.remove(session);nativeTimeZoneIntents.remove(session);TimeZoneGate gate=timeZoneGates.remove(session);if(gate==null)return;completeTimeZoneProofs(gate,false);completeTimeZoneRequests(gate,false);owner.timeZone.retire(session,gate.epoch);metadata.timeZonePolicy=timeZoneStatus();
    ArrayList<java.util.function.Consumer<Boolean>> waiting=new ArrayList<>(gate.waiting);gate.waiting.clear();for(java.util.function.Consumer<Boolean> callback:waiting)callback.accept(false);
  }
  void retireTimeZones(){for(GeckoSession session:new ArrayList<>(timeZoneGates.keySet()))retireTimeZone(session);}
  void finishTimeZone(GeckoSession session,TimeZoneGate gate,boolean success){
    if(timeZoneGates.get(session)!=gate)return;gate.preparing=false;gate.revalidating=false;gate.ready=success&&timeZoneSessionAlive(session)&&owner.timeZone.allowed(session,gate.epoch);
    metadata.timeZonePolicy=timeZoneStatus();if(!gate.ready){String issue=metadata.timeZonePolicy.optString("issue");owner.setStatus(issue.isEmpty()?"当前原生时区尚未确认，网页请求已暂停；请检查独立时区设置":issue);}ArrayList<java.util.function.Consumer<Boolean>> waiting=new ArrayList<>(gate.waiting);gate.waiting.clear();
    completeTimeZoneProofs(gate,gate.ready);completeTimeZoneRequests(gate,gate.ready);
    for(java.util.function.Consumer<Boolean> callback:waiting)callback.accept(gate.ready);owner.changed();
  }
  void sendTimeZone(WebExtension.Port port,GeckoSession session,TimeZoneGate gate,String kind,String zone,String token,java.util.function.Consumer<String> ok,java.util.function.Consumer<Throwable> fail){
    if(!timeZoneSessionAlive(session)||timeZoneGates.get(session)!=gate||routePort!=port){fail.accept(new IOException("时区浏览器上下文已变化"));return;}
    int id=cookieCallbacks.add(port,value->{if(!timeZoneSessionAlive(session)||timeZoneGates.get(session)!=gate||routePort!=port||value==null||"null".equals(value)){fail.accept(new IOException("原生时区通道未确认"));return;}ok.accept(value);},6000);
    try{JSONObject message=J.obj("kind",kind,"id",id,"sessionId",AppSessionIdentity.id(session),"requestToken",token);if("timezoneApply".equals(kind))message.put("zoneId",zone);port.postMessage(message);}catch(Exception unavailable){cookieCallbacks.complete(port,id,null);}
  }
  void prepareTimeZone(GeckoSession session,java.util.function.Consumer<Boolean> done){
    startTimeZone(session,done,false);
  }
  void revalidateTimeZone(GeckoSession session){
    if(!timeZoneSessionAlive(session)||popups.contains(session))return;
    startTimeZone(session,ignored->{},true);
  }
  private void startTimeZone(GeckoSession session,java.util.function.Consumer<Boolean> done,boolean revalidate){
    if(!timeZoneSessionAlive(session)){done.accept(false);return;}if(!revalidate&&timeZoneAllows(session)){done.accept(true);return;}
    if(popups.contains(session)){done.accept(owner.timeZone.popupAllowed());return;}
    TimeZoneGate existing=timeZoneGates.get(session);if(existing==null){existing=new TimeZoneGate();timeZoneGates.put(session,existing);}final TimeZoneGate gate=existing;
    if(revalidate){completeTimeZoneProofs(gate,false);completeTimeZoneRequests(gate,false);gate.documentSerial++;gate.preparing=false;gate.ready=false;gate.revalidating=true;}
    gate.waiting.add(done);if(gate.preparing)return;gate.preparing=true;gate.ready=false;final WebExtension.Port port=routePort;final long document=gate.documentSerial;
    final GeckoResult<Boolean> window=new GeckoResult<>();
    java.util.concurrent.atomic.AtomicBoolean once=new java.util.concurrent.atomic.AtomicBoolean();
    final Runnable[] deadline={null};
    java.util.function.Consumer<Boolean> windowReady=ready->{
      if(!once.compareAndSet(false,true))return;if(deadline[0]!=null)owner.handler.removeCallbacks(deadline[0]);
      window.complete(ready&&timeZoneSessionAlive(session)&&timeZoneGates.get(session)==gate&&gate.documentSerial==document&&port!=null&&routePort==port);
    };
    GeckoTimeZoneController.NativeAccess access=new GeckoTimeZoneController.NativeAccess(){
      public boolean current(){return timeZoneSessionAlive(session)&&timeZoneGates.get(session)==gate&&gate.documentSerial==document&&port!=null&&routePort==port;}
      void request(String kind,String zone,String token,java.util.function.Consumer<String> ok,java.util.function.Consumer<Throwable> fail){
        window.accept(ready->{if(!ready||!current()){fail.accept(new IOException("浏览器窗口或文档已变化，时区尚未确认"));return;}sendTimeZone(port,session,gate,kind,zone,token,ok,fail);},fail::accept);
      }
      public void read(String token,java.util.function.Consumer<String> ok,java.util.function.Consumer<Throwable> fail){request("timezoneRead","",token,ok,fail);}
      public void apply(String zone,String token,java.util.function.Consumer<String> ok,java.util.function.Consumer<Throwable> fail){request("timezoneApply",zone,token,ok,fail);}
    };
    java.util.function.Consumer<Boolean> finished=ok->{if(timeZoneGates.get(session)==gate&&gate.documentSerial==document)finishTimeZone(session,gate,ok);};
    if(revalidate){
      try{owner.timeZone.revalidate(session,AppSessionIdentity.id(session),gate.epoch,access,finished);}
      catch(RuntimeException unavailable){finished.accept(false);windowReady.accept(false);return;}
    }else{
      window.accept(ready->{
        if(!access.current()){finished.accept(false);return;}
        try{owner.timeZone.prepare(session,AppSessionIdentity.id(session),gate.epoch,access,finished);}catch(RuntimeException unavailable){finished.accept(false);}
      },error->finished.accept(false));
    }
    deadline[0]=()->windowReady.accept(false);owner.handler.postDelayed(deadline[0],5000);
    try{session.getUserAgent().accept(value->windowReady.accept(true),error->windowReady.accept(false));}catch(RuntimeException unavailable){windowReady.accept(false);}
    metadata.timeZonePolicy=timeZoneStatus();
  }
  void completeTimeZoneRequests(TimeZoneGate gate,boolean ready){
    ArrayList<java.util.function.Consumer<Boolean>> pending=new ArrayList<>(gate.networkWaiting);gate.networkWaiting.clear();
    for(java.util.function.Consumer<Boolean> waiting:pending)try{waiting.accept(ready);}catch(RuntimeException ignored){}
  }
  void completeTimeZoneProofs(TimeZoneGate gate,boolean ready){
    ArrayList<java.util.function.Consumer<Boolean>> pending=new ArrayList<>(gate.proofWaiting);gate.proofWaiting.clear();
    for(java.util.function.Consumer<Boolean> waiting:pending)try{waiting.accept(ready);}catch(RuntimeException ignored){}
  }
  Object identityAuditNativeOpen(){return timeZoneSessionAlive(current)?timeZoneGates.get(current):null;}
  void awaitIdentityAuditDocumentProof(String expectedUrl,long navigation,Object expectedSession,Object expectedRuntime,Object expectedOpen,java.util.function.Consumer<Boolean> done){
    GeckoSession session=current;TimeZoneGate gate=timeZoneGates.get(session);
    if(expectedSession!=session||expectedRuntime==null||expectedRuntime!=runtime||expectedOpen==null||expectedOpen!=gate||expectedUrl==null||expectedUrl.isEmpty()||session==null||gate==null||!Objects.equals(expectedUrl,getUrl())||owner.navigationEpoch!=navigation||!timeZoneSessionAlive(session)){done.accept(false);return;}
    final WebExtension.Port port=routePort;final long document=gate.documentSerial,identity=identityPolicyRevision,connection=owner.connectionEpoch,protection=nativeProtection.token();
    final long desired=owner.timeZone.status().optLong("desiredRevision",-1);
    java.util.concurrent.atomic.AtomicBoolean once=new java.util.concurrent.atomic.AtomicBoolean();
    final Runnable[] deadline={null};final java.util.function.Consumer<Boolean>[] finished=new java.util.function.Consumer[1];
    finished[0]=ready->{
      if(!once.compareAndSet(false,true))return;gate.proofWaiting.remove(finished[0]);if(deadline[0]!=null)owner.handler.removeCallbacks(deadline[0]);
      done.accept(ready&&current==session&&runtime==expectedRuntime&&Objects.equals(expectedUrl,getUrl())&&owner.navigationEpoch==navigation&&timeZoneSessionAlive(session)
          &&timeZoneGates.get(session)==gate&&gate.documentSerial==document&&port!=null&&routePort==port&&identityPolicyRevision==identity&&owner.connectionEpoch==connection&&nativeProtection.token()==protection
          &&owner.timeZone.status().optLong("desiredRevision",-1)==desired&&timeZoneAllows(session)&&owner.timeZone.status(session,gate.epoch).optBoolean("nativeSettingReadback"));
    };
    if(timeZoneAllows(session)&&owner.timeZone.status(session,gate.epoch).optBoolean("nativeSettingReadback")){finished[0].accept(true);return;}
    if(!gate.preparing||!gate.revalidating||gate.proofWaiting.size()>=128){finished[0].accept(false);return;}
    gate.proofWaiting.add(finished[0]);deadline[0]=()->finished[0].accept(false);owner.handler.postDelayed(deadline[0],6000);
  }
  boolean waitForDocumentTimeZone(java.util.function.Consumer<Boolean> resumed){
    // A committed document may immediately request scripts and frame resources.
    // Hold only this short native revalidation; bootstrap and invalid settings
    // retain their existing closed admission path.
    GeckoSession session=current;TimeZoneGate gate=timeZoneGates.get(session);
    if(gate==null||!gate.preparing||!gate.revalidating)return false;
    if(gate.networkWaiting.size()>=128){resumed.accept(false);return true;}
    final WebExtension.Port port=routePort;final long document=gate.documentSerial,navigation=owner.navigationEpoch,connection=owner.connectionEpoch,identity=identityPolicyRevision,protection=nativeProtection.token();
    final long desired=owner.timeZone.status().optLong("desiredRevision",-1);
    java.util.concurrent.atomic.AtomicBoolean once=new java.util.concurrent.atomic.AtomicBoolean();
    final Runnable[] deadline={null};final java.util.function.Consumer<Boolean>[] finished=new java.util.function.Consumer[1];
    finished[0]=ready->{
      if(!once.compareAndSet(false,true))return;gate.networkWaiting.remove(finished[0]);if(deadline[0]!=null)owner.handler.removeCallbacks(deadline[0]);
      resumed.accept(ready&&current==session&&timeZoneSessionAlive(session)&&timeZoneGates.get(session)==gate&&gate.documentSerial==document&&port!=null&&routePort==port
          &&owner.navigationEpoch==navigation&&owner.connectionEpoch==connection&&identityPolicyRevision==identity&&nativeProtection.token()==protection
          &&owner.timeZone.status().optLong("desiredRevision",-1)==desired&&timeZoneAllows(session));
    };
    gate.networkWaiting.add(finished[0]);deadline[0]=()->finished[0].accept(false);owner.handler.postDelayed(deadline[0],4000);return true;
  }
  GeckoResult<Object> guardedRoute(String target){
    GeckoResult<Object> result=new GeckoResult<>();
    if(waitForDocumentTimeZone(ready->result.complete((ready?route(target):blocked()).toString())))return result;
    return GeckoResult.fromValue(route(target).toString());
  }
  GeckoResult<Object> guardedRequestHeaderPolicy(String target){
    GeckoResult<Object> result=new GeckoResult<>();
    if(waitForDocumentTimeZone(ready->{if(!ready){result.complete(J.obj("allowed",false).toString());return;}requestHeaderPolicy(target).accept(result::complete,error->result.complete(J.obj("allowed",false).toString()));}))return result;
    return requestHeaderPolicy(target);
  }
  void loadSessionUri(GeckoSession session,String target){
    if(rejectDisabledNavigation(session,target))return;
    boolean blob=target!=null&&target.startsWith("blob:")&&allowedUrl(target.substring(5));
    if(!timeZoneSessionAlive(session)||!identityRequestAllowed(target)||!(allowedUrl(target)||blob)||!owner.guard.allowed()||!protectionAllowsNetwork())return;
    final Object intent=new Object();nativeTimeZoneIntents.put(session,intent);
    if(timeZoneAllows(session)){timeZoneLoads.remove(session);nativeTimeZoneIntents.remove(session);session.loadUri(target);return;}
    TimeZoneGate existing=timeZoneGates.get(session);if(existing==null){existing=new TimeZoneGate();timeZoneGates.put(session,existing);}final TimeZoneGate gate=existing;final long document=gate.documentSerial,navigation=owner.navigationEpoch;final boolean foreground=session==current;
    // Secondary sessions own their native load, independent of progress in the
    // selected page. A newer explicit intent, open gate or document wins.
    timeZoneLoads.put(session,target);prepareTimeZone(session,ok->{
      if(nativeTimeZoneIntents.get(session)!=intent||!target.equals(timeZoneLoads.get(session)))return;
      if(!ok){timeZoneLoads.remove(session);nativeTimeZoneIntents.remove(session);return;}
      if(timeZoneSessionAlive(session)&&timeZoneGates.get(session)==gate&&gate.documentSerial==document&&(!foreground||session!=current||navigation==owner.navigationEpoch)&&owner.guard.allowed()&&protectionAllowsNetwork()&&identityRequestAllowed(target)&&timeZoneAllows(session)){
        timeZoneLoads.remove(session);nativeTimeZoneIntents.remove(session);session.loadUri(target);
      }else{timeZoneLoads.remove(session);nativeTimeZoneIntents.remove(session);}
    });
  }
  Object claimTimeZoneIntent(GeckoSession session,boolean restore){
    Object intent=new Object();timeZoneIntents.put(session,intent);nativeTimeZoneIntents.remove(session);timeZoneLoads.remove(session);if(restore&&session==current)queued="";return intent;
  }
  boolean hasTimeZoneIntent(GeckoSession session){return timeZoneIntents.containsKey(session)||session==current&&!queued.isEmpty();}
  void clearTimeZoneIntent(GeckoSession session,Object intent){if(timeZoneIntents.get(session)==intent)timeZoneIntents.remove(session);}
  void timezoneConfigurationChanged(){
    if(destroyed||current==null)return;String target=getUrl();if(!allowedUrl(target))target=allowedUrl(queued)?queued:owner.resumeUrl();GeckoSession.SessionState saved=states.get(current);long revision=stateDraftRevisions.getOrDefault(current,-1L);
    closeExitIpPage();retireTimeZones();for(GeckoSession popup:new ArrayList<>(popups))closePopup(popup);
    if(current==null||!allowedUrl(target))return;owner.beginNavigation(target,"正在应用当前环境时区…");queued=target;
    if(!reopenCurrent())return;
    if(saved!=null&&saved.size()>0&&target.equals(stateUrl(saved))){startupState=saved;startupDraftRevision=revision;}loadUrl(target);
  }
  static boolean active(Object web){return web instanceof GeckoWebView&&((GeckoWebView)web).enabled;}
  private void initialize(){
    if(!enabled||destroyed||owner.deleted||runtime!=null||failed)return;
    if(!checkpointReady){if(!checkpointRequested){checkpointRequested=true;long draftRevision=LocalDraftPolicy.revision(owner.context);sessionStore.read(value->owner.handler.post(()->{if(destroyed)return;try{startupState=value==null?null:GeckoSession.SessionState.fromString(value);startupDraftRevision=draftRevision;}catch(RuntimeException invalid){startupState=null;}checkpointReady=true;initialize();}));}return;}
    ResourcePressureController.MemorySample memory=resourceMemory();
    resourceAdmission=owner.resources.request(runtime!=null,startupState!=null||owner.resourceRestoreWork(),memory);
    if(resourceAdmission==ResourcePressureController.Admission.DEFER){resourceDeferred=true;owner.setStatus(ResourcePressureController.DEFERRED_MESSAGE);return;}
    resourceDeferred=false;
    if(cpuBoot==null){
      if(!cpuStartupRequested){cpuStartupRequested=true;owner.cpu.prepareStartup(value->{
        if(destroyed||owner.deleted)return;if(value==null){failure("CPU 冷启动配置未能安全准备，请重新打开当前环境");return;}cpuBoot=value;initialize();
      });}return;
    }
    try{
      if(sdkBuildIdentity==null)sdkBuildIdentity=NormalCaretSdkReceipt.read(owner.context);
      File directory=cpuBoot.profile,config=cpuBoot.config;
      if(!owner.cpu.claimRuntime(cpuBoot))throw new IOException("CPU cold runtime ownership changed");
      runtime=GeckoRuntime.create(new GeckoEnvironmentContext(owner.context),new GeckoRuntimeSettings.Builder()
        .arguments(new String[]{"-profile",directory.getAbsolutePath()}).configFilePath(config.getAbsolutePath())
        .isolatedProcessEnabled(Build.VERSION.SDK_INT>=29).appZygoteProcessEnabled(false)
        .remoteDebuggingEnabled(false).consoleOutput(false).trustedRecursiveResolverMode(GeckoRuntimeSettings.TRR_MODE_DISABLED)
        .preferredColorScheme(AppAppearance.dark()?GeckoRuntimeSettings.COLOR_SCHEME_DARK:GeckoRuntimeSettings.COLOR_SCHEME_LIGHT)
        .forceUserScalableEnabled(true).inputAutoZoomEnabled(true).build());
      owner.resources.runtimeCreated();
      GeckoRuntime cpuRuntime=runtime;
      owner.cpu.attachRuntime(cpuBoot,cpuRuntime,new GeckoCpuNative(()->!destroyed&&!owner.deleted&&runtime==cpuRuntime),accepted->{
        if(destroyed||runtime!=cpuRuntime)return;if(!accepted){failure("原生 CPU 配置未确认，请重新打开当前环境");return;}maybeOpen();
      });
      final GeckoRuntime created=runtime;final long addonSerial=addonStateSerial;
      created.getWebExtensionController().setAddonManagerDelegate(new WebExtensionController.AddonManagerDelegate(){
        @Override public void onDisabled(WebExtension value){addonStateChanged(created,value,true);}
        @Override public void onEnabled(WebExtension value){addonStateChanged(created,value,false);}
      });
      created.getWebExtensionController().ensureBuiltIn("resource://android/assets/gecko/","browser@pocketchat.local")
        .accept(value->acceptBuiltinAddon(created,value,addonSerial),error->{if(!destroyed&&runtime==created&&addonStateSerial==addonSerial)failure("浏览器初始化失败，请重新打开当前环境重试");});
    }catch(Exception error){failure("新内核未能启动，请重新打开当前环境重试");}
  }
  ResourcePressureController.MemorySample resourceMemory(){return owner.resources.sample();}
  boolean resourcePage(String target){return MainActivity.chatUrl(target);}
  boolean resourceSamePage(String a,String b){return WebReplyObserver.same(a,b);}
  boolean retryResourceStart(){if(!resourceDeferred||destroyed||runtime!=null)return false;String target=queued.isEmpty()?owner.navigationTarget:queued;if(!target.isEmpty()&&allowedUrl(target)&&owner.guard.allowed())queued=target;initialize();if(!resourceDeferred&&!failed&&runtime!=null){if(!target.isEmpty())owner.beginNavigation(target,"正在打开当前环境");else owner.setStatus("正在打开当前环境");owner.wakePolling();}return true;}
  boolean hasOpenPopup(){return !popups.isEmpty();}
  boolean builtinAddonCurrent(GeckoRuntime expected,WebExtension value,boolean disabled){
    return !destroyed&&runtime==expected&&expected!=null&&value!=null&&value.isBuiltIn&&"browser@pocketchat.local".equals(value.id)&&value.metaData!=null&&value.metaData.enabled!=disabled;
  }
  void acceptBuiltinAddon(GeckoRuntime expected,WebExtension value,long serial){
    if(addonStateSerial!=serial||value==null||value.metaData==null||!builtinAddonCurrent(expected,value,!value.metaData.enabled))return;
    applyAddonState(expected,value,!value.metaData.enabled,serial);
  }
  void addonStateChanged(GeckoRuntime expected,WebExtension value,boolean disabled){
    if(!builtinAddonCurrent(expected,value,disabled))return;
    applyAddonState(expected,value,disabled,++addonStateSerial);
  }
  void applyAddonState(GeckoRuntime expected,WebExtension value,boolean disabled,long serial){
    if(addonStateSerial!=serial||!builtinAddonCurrent(expected,value,disabled))return;
    extension=value;addonDisabled=disabled;
    if(!disabled){extension.setMessageDelegate(routeMessages,"pocketroute");maybeOpen();return;}
    closeExitIpPage();WebExtension.Port previous=routePort;routePort=null;
    requestHeadersInstalled=false;routePrepared=false;privacyReady=false;fingerprintingProtected=false;
    cancelProtectionTasks();nativeProtection.disconnected();protectionRequest=nativeProtection.token();metadata.policyAcknowledged=false;metadata.rfpAcknowledged=false;
    retireTimeZones();retireRequestHeaderPolicy();releaseGeneralRoutes();deferredGeneralLoads.clear();generalRestore=null;protectionRestore=null;startupState=null;
    String attempted=queued;queued="";
    for(GeckoSession session:new ArrayList<>(locations.keySet()))if(session.isOpen())try{session.stop();}catch(RuntimeException alreadyClosed){}
    if(previous!=null){cookieCallbacks.cancel(previous);try{previous.disconnect();}catch(RuntimeException alreadyDisconnected){}}
    if(!attempted.isEmpty()||owner.navigating)nativeNavigationFailure(current,attempted.isEmpty()?owner.navigationTarget:attempted,"浏览器安全扩展已停用，无法加载网页；请重新启用后重试");
    else owner.setStatus("浏览器安全扩展已停用，新的网页请求已暂停；请重新启用后重试");
    owner.changed();
  }
  boolean rejectDisabledNavigation(GeckoSession session,String target){
    if(!addonDisabled)return false;
    timeZoneLoads.remove(session);timeZoneIntents.remove(session);nativeTimeZoneIntents.remove(session);deferredGeneralLoads.remove(session);
    if(session==current){queued="";nativeNavigationFailure(session,target,"浏览器安全扩展已停用，无法加载网页；请重新启用后重试");}
    return true;
  }
  GeckoResult<String> nativeNavigationFailure(GeckoSession session,String target,String message){
    if(!destroyed&&session==current&&owner.audit!=null&&owner.audit.identityPageFailed(target,"检测服务连接或安全校验未完成"))return GeckoResult.fromValue(null);
    if(!destroyed&&session==current&&!"about:blank".equals(target)){owner.pageError=message;owner.finishNavigation(owner.pageError,false);}
    return null;
  }
  private final WebExtension.MessageDelegate routeMessages=new WebExtension.MessageDelegate(){
    @Override public void onConnect(WebExtension.Port port){
      if(destroyed||port.sender.environmentType!=WebExtension.MessageSender.ENV_TYPE_EXTENSION)return;
      if(addonDisabled){port.disconnect();return;}
      WebExtension.Port previous=routePort;
      routePort=port;retireTimeZones();requestHeadersInstalled=false;retireRequestHeaderPolicy();port.setDelegate(new WebExtension.PortDelegate(){
        @Override public void onPortMessage(Object message,WebExtension.Port incoming){
          if(!(message instanceof JSONObject)||incoming!=routePort)return;JSONObject data=(JSONObject)message;
          if("requestHeadersPrepared".equals(data.optString("kind"))){requestHeadersInstalled=Boolean.TRUE.equals(data.opt("installed"));retireRequestHeaderPolicy();if(requestHeadersInstalled){maybeOpen();resumeProtectedLoads();}else owner.setStatus("浏览器请求身份保护未能安装，已暂停新的网页请求");owner.changed();return;}
          if("protectionReady".equals(data.optString("kind"))){
            boolean typed=data.opt("acknowledged") instanceof Boolean&&data.opt("fingerprinting") instanceof Boolean;
            if(requestedProtection==owner.privacy.level()&&nativeProtection.receive(protectionCounter(data,"token"),protectionCounter(data,"generation"),protectionReceiptLevel(data),typed&&Boolean.TRUE.equals(data.opt("acknowledged")),Boolean.TRUE.equals(data.opt("fingerprinting")),typed?data.optString("reason"):"invalid-setting-receipt")){cancelProtectionTasks();protectionAttemptFinished(incoming);}return;
          }
          if("protectionChanged".equals(data.optString("kind"))){
            if(requestedProtection==owner.privacy.level()&&nativeProtection.changed(protectionCounter(data,"token"),protectionCounter(data,"generation"),protectionReceiptLevel(data))){cancelProtectionTasks();retireRequestHeaderPolicy();protectionAttemptFinished(incoming);}return;
          }
          if("ready".equals(data.optString("kind"))||"cookiePrepared".equals(data.optString("kind"))){routePrepared=true;maybeOpen();return;}
          if("cookieRecoveryError".equals(data.optString("kind"))){failure("登录状态暂未恢复，请重新打开当前环境");return;}
          if("cookies".equals(data.optString("kind")))cookieCallbacks.complete(incoming,data.optInt("id"),data.optBoolean("error")?null:data.optString("value"));
          if("requestIdentityScopeResult".equals(data.optString("kind")))cookieCallbacks.complete(incoming,data.optInt("id"),data.optString("result","null"));
          if("timezoneReady".equals(data.optString("kind")))cookieCallbacks.complete(incoming,data.optInt("id"),data.optString("result","null"));
        }
        @Override public void onDisconnect(WebExtension.Port incoming){if(routePort==incoming){closeExitIpPage();routePort=null;retireTimeZones();requestHeadersInstalled=false;retireRequestHeaderPolicy();routePrepared=false;cancelProtectionTasks();nativeProtection.disconnected();protectionRequest=nativeProtection.token();privacyReady=false;fingerprintingProtected=false;metadata.policyAcknowledged=false;metadata.rfpAcknowledged=false;if(owner.privacy.level()>=2)owner.setStatus(protectionSummary());owner.changed();}cookieCallbacks.cancel(incoming);}
      });
      if(previous!=null&&previous!=port)cookieCallbacks.cancel(previous);
      prepareProtectionBridge(port);
    }
    @Override public GeckoResult<Object> onMessage(String app,Object message,WebExtension.MessageSender sender){
      if(addonDisabled||!"pocketroute".equals(app)||!(message instanceof JSONObject)||sender.environmentType!=WebExtension.MessageSender.ENV_TYPE_EXTENSION)return GeckoResult.fromValue(blocked().toString());
      JSONObject request=(JSONObject)message;
      if("requestHeaderPolicy".equals(request.optString("kind")))return guardedRequestHeaderPolicy(request.optString("url"));
      if("ready".equals(request.optString("kind"))){routePrepared=true;maybeOpen();return GeckoResult.fromValue(null);}
      if("cookieRecoveryError".equals(request.optString("kind"))){failure("登录状态暂未恢复，请重新打开当前环境");return GeckoResult.fromValue(null);}
      if(!"route".equals(request.optString("kind")))return GeckoResult.fromValue(blocked().toString());
      // Native callbacks accept primitive values; Port.postMessage performs its own bundle conversion.
      return guardedRoute(request.optString("url"));
    }
  };
  static boolean validRequestUserAgent(String value){
    if(value==null||value.isEmpty()||value.length()>1024)return false;
    for(int i=0;i<value.length();i++)if(value.charAt(i)<32||value.charAt(i)>126)return false;
    return true;
  }
  void retireRequestHeaderPolicy(){
    headerPolicyRead=null;
    metadata.requestHeaderPolicy=J.obj("installed",requestHeadersInstalled,"nativeReadback",false,"revision",identityPolicyRevision,"scope","public-http-request-ua-only","privateAdmission","unchanged-original-headers","sharedWorkerWireVerified",false,"serviceWorkerWireVerified",false);
    if(routePort!=null&&identityPolicyRevision>0)try{routePort.postMessage(J.obj("kind","requestHeaderPolicyChanged","revision",identityPolicyRevision));}catch(RuntimeException disconnected){requestHeadersInstalled=false;metadata.requestHeaderPolicy=J.obj("installed",false,"nativeReadback",false,"scope","public-http-request-ua-only","privateAdmission","unchanged-original-headers","sharedWorkerWireVerified",false,"serviceWorkerWireVerified",false);}
  }
  boolean requestHeaderContextCurrent(HeaderPolicyRead read,String target){
    if(read==null||destroyed||failed||!enabled||owner.deleted||!requestHeadersInstalled||current!=read.session||!current.isOpen()||routePort!=read.port||read.port==null||identityPolicyRevision!=read.revision||owner.navigationEpoch!=read.epoch||nativeProtection.token()!=read.protection||!protectionAllowsNetwork()||!identityRequestAllowed(target)||!allowedUrl(target))return false;
    if(GeckoNavigationPolicy.publicWeb(target)&&(!privacyReady||!metadata.localesRequestAcknowledged||!metadata.rfpAcknowledged||!nativeProtection.confirmed()))return false;
    JSONObject selected=route(target);
    return !("socks".equals(selected.optString("type"))&&"127.0.0.1".equals(selected.optString("host"))&&selected.optInt("port")==9);
  }
  GeckoResult<Object> requestHeaderPolicy(String target){
    final GeckoResult<Object> result=new GeckoResult<>();
    try{
      HeaderPolicyRead read=headerPolicyRead;
      if(!requestHeaderContextCurrent(read,target)){
        if(current==null||!current.isOpen()||routePort==null){result.complete(J.obj("allowed",false).toString());return result;}
        // One actual SDK read is shared by requests in this exact native
        // context. Every caller still rechecks its own target and guard below.
        read=new HeaderPolicyRead(current,routePort,identityPolicyRevision,owner.navigationEpoch,nativeProtection.token(),null);
        if(!requestHeaderContextCurrent(read,target)){result.complete(J.obj("allowed",false).toString());return result;}
      }
      // Internal admissions may extend the URL set; they are not public website
      // identity policies. Their existing SDK headers and guard remain intact.
      if(!GeckoNavigationPolicy.publicWeb(target)){result.complete(J.obj("allowed",true,"scope","private-admission-unchanged","revision",read.revision).toString());return result;}
      if(read.userAgent==null){read=new HeaderPolicyRead(current,routePort,identityPolicyRevision,owner.navigationEpoch,nativeProtection.token(),current.getUserAgent());headerPolicyRead=read;}
      final HeaderPolicyRead selected=read;
      read.userAgent.accept(value->{
        try{
          if(headerPolicyRead!=selected||!requestHeaderContextCurrent(selected,target)||!validRequestUserAgent(value)){if(headerPolicyRead==selected)headerPolicyRead=null;result.complete(J.obj("allowed",false).toString());return;}
          if(!selected.observed){selected.observed=true;metadata.requestHeaderPolicy=J.obj("installed",true,"nativeReadback",true,"revision",selected.revision,"userAgent",value,"scope","public-http-request-ua-only","privateAdmission","unchanged-original-headers","sharedWorkerWireVerified",false,"serviceWorkerWireVerified",false);}
          result.complete(J.obj("allowed",true,"userAgent",value,"revision",selected.revision).toString());
        }catch(RuntimeException unavailable){if(headerPolicyRead==selected)headerPolicyRead=null;result.complete(J.obj("allowed",false).toString());}
      },error->{if(headerPolicyRead==selected)headerPolicyRead=null;result.complete(J.obj("allowed",false).toString());});
    }catch(RuntimeException unavailable){result.complete(J.obj("allowed",false).toString());}
    return result;
  }
  JSONObject blocked(){return J.obj("type","socks","host","127.0.0.1","port",9,"proxyDNS",true,"failoverTimeout",1);}
  JSONObject route(String target){
    if(exitIpPage!=null&&!exitIpPage.fresh())closeExitIpPage();
    if(current!=null&&!timeZoneAllows(current))return blocked();
    if(destroyed||!enabled||!requestHeadersInstalled||!protectionAllowsNetwork()||!identityRequestAllowed(target)||owner.guard==null||!owner.guard.allowed()||!generalRouteReady()||!allowedUrl(target.startsWith("wss://")?"https"+target.substring(3):target.startsWith("ws://")?"http"+target.substring(2):target))return blocked();
    if(owner.internalNetwork()){
      NativeNetwork n=NativeNetwork.get(owner.context);NativeNetwork.ExitRouteReceipt receipt=n.verifiedRoute;String pool=internalPoolKey(n);
      if(pool==null||receipt==null||receipt!=n.verifiedRoute||!n.ready||n.starting||n.recoveryBlocked||n.transport==null||!receipt.matches(n,n.transport.state))return blocked();
      return J.obj("type","http","host","127.0.0.1","port",receipt.proxy,"failoverTimeout",1,"connectionIsolationKey",pool);
    }
    String proxy=owner.prefs.getString("proxy","").trim();
    if(proxy.isEmpty())return J.obj("type","direct");
    if(!MainActivity.validProxy(proxy))return blocked();
    Uri address=Uri.parse(proxy);String scheme=address.getScheme();
    String pool="environment-"+Profiles.slot(owner.context)+"-"+owner.connectionEpoch;
    JSONObject result=J.obj("type","socks".equals(scheme)?"socks":scheme,"host",address.getHost(),"port",address.getPort(),"failoverTimeout",1,"connectionIsolationKey",pool);
    if("socks".equals(scheme))try{result.put("proxyDNS",true);}catch(Exception ignored){}
    return result;
  }
  String internalPoolKey(NativeNetwork n){
    NativeNetwork.ExitRouteReceipt receipt=n.verifiedRoute;JSONObject state=n.transport==null?null:n.transport.state;
    // Only the already verified, currently pushed service lifetime is admitted.
    // This path neither waits for service IPC nor opens a diagnostic connection.
    if(!n.ready||n.starting||n.recoveryBlocked||receipt==null||state==null||!receipt.matches(n,state))return connectionPool.key(null,owner.browserDefaultNetwork.snapshot());
    NetworkPoolIdentity.Route route=new NetworkPoolIdentity.Route(Profiles.slot(owner.context),receipt.generation,receipt.pid,receipt.servicePid,receipt.configuration,receipt.entry,receipt.fingerprint,receipt.serial,receipt.controller,receipt.proxy,receipt.token);
    String pool=connectionPool.key(route,owner.browserDefaultNetwork.snapshot());
    if(n.verifiedRoute!=receipt||!n.ready||n.starting||n.recoveryBlocked||!receipt.matches(n,n.transport.state))return connectionPool.key(null,owner.browserDefaultNetwork.snapshot());
    return pool;
  }
  private void open(){
    if(!enabled||destroyed)return;
    // Choose the official transform-capable backend once. Changing a live SDK
    // surface backend can leave its surface callback detached (157.0 SDK).
    if(surface==null){surface=new GeckoView(displayContext);surface.setViewBackend(GeckoView.BACKEND_TEXTURE_VIEW);surface.coverUntilFirstPaint(ReferenceUi.CHAT_BG);addView(surface,new FrameLayout.LayoutParams(-1,-1));}
    primary=newSession();current=primary;primary.open(runtime);surface.setSession(primary);configure(desktop,owner.privacy.level());ready=true;
    if(!queued.isEmpty()){String target=queued;queued="";loadUrl(target);}
  }
  void identityConfigurationReady(){identityPrepared=true;maybeOpen();}
  private void maybeOpen(){if(!destroyed&&!failed&&!addonDisabled&&!ready&&extension!=null&&checkpointReady&&identityPrepared&&routePrepared&&requestHeadersInstalled&&privacyReady&&protectionAllowsNetwork())open();}
  GeckoSession newSession(){
    // Isolation comes from existing Android processes and distinct profile directories.
    // Default cookie storage remains usable by the official cookie API in this runtime.
    GeckoSession session=new GeckoSession(new GeckoSessionSettings.Builder()
      .userAgentMode(desktop?GeckoSessionSettings.USER_AGENT_MODE_DESKTOP:GeckoSessionSettings.USER_AGENT_MODE_MOBILE)
      .viewportMode(GeckoSessionSettings.VIEWPORT_MODE_MOBILE).build());
    locations.put(session,"");backStates.put(session,false);
    session.setCompositorScrollDelegate(new GeckoSession.CompositorScrollDelegate(){
      @Override public void onScrollChanged(GeckoSession source,GeckoSession.ScrollPositionUpdate update){
        if(destroyed||!locations.containsKey(source)||!Float.isFinite(update.zoom)||update.zoom<=0)return;
        measuredCompositors.add(source);
        Float measured=pageScales.get(source);boolean first=measured==null;
        if(!first&&Math.abs(measured-update.zoom)<.00001f)return;
        pageScales.put(source,update.zoom);
        if(source==current){float previous=scale;scale=update.zoom*readingLayout;if(readingOwnerVisible()){if(client!=null&&Math.abs(scale-previous)>.0001f)client.onScaleChanged(null,previous,scale);if(first)owner.reading.nativeScaleMeasured();}}
      }
    });
    session.getWebExtensionController().setMessageDelegate(extension,pageMessages,"pocketpage");
    session.setNavigationDelegate(new GeckoSession.NavigationDelegate(){
      @Override public GeckoResult<AllowOrDeny> onLoadRequest(GeckoSession s,LoadRequest request){
        if(rejectDisabledNavigation(s,request.uri))return GeckoResult.fromValue(AllowOrDeny.DENY);
        boolean blob=request.uri!=null&&request.uri.startsWith("blob:")&&allowedUrl(request.uri.substring(5));
        boolean allowed=!destroyed&&("about:blank".equals(request.uri)||protectionAllowsNetwork()&&identityRequestAllowed(request.uri)&&owner.guard.allowed()&&(allowedUrl(request.uri)||blob));
        if(allowed&&!"about:blank".equals(request.uri)&&!timeZoneAllows(s)){if(!hasTimeZoneIntent(s))loadSessionUri(s,request.uri);allowed=false;owner.setStatus("正在确认当前环境时区…");}
        if(allowed&&!"about:blank".equals(request.uri)&&!retainGeneralRoute(s,blob?request.uri.substring(5):request.uri)){deferredGeneralLoads.put(s,request.uri);allowed=false;owner.setStatus("线路正在更新，完成后继续打开网页");}
        else if(allowed)deferredGeneralLoads.remove(s);
        if(!allowed&&s==current)owner.setStatus(timeZoneLoads.containsKey(s)?"正在确认当前环境时区…":deferredGeneralLoads.containsKey(s)?"线路正在更新，完成后继续打开网页":!protectionAllowsNetwork()?protectionSummary():!identityRequestAllowed(request.uri)?"检测地址已失效，请重新开始身份检查":"连接尚未受保护，或地址不是公共网页");
        return GeckoResult.fromValue(allowed?AllowOrDeny.ALLOW:AllowOrDeny.DENY);
      }
      @Override public void onLocationChange(GeckoSession s,String target,List<GeckoSession.PermissionDelegate.ContentPermission> permissions,Boolean gesture){
        if(destroyed||addonDisabled||!locations.containsKey(s))return;boolean committed=pendingLoads.remove(s);locations.put(s,target);
        if(committed){painted.remove(s);usable.remove(s);pageScales.remove(s);viewportWidths.remove(s);loadingTargets.put(s,target);appearanceCommitted(s);if(!"about:blank".equals(target))revalidateTimeZone(s);}
        else{WebExtension.Port page=ports.get(s);if(page!=null)appearance(page);}
        if(MainActivity.chatUrl(target))forgetGeneralRoute(s);else if(GeckoNavigationPolicy.publicWeb(target))retainGeneralRoute(s,target);
        if(s!=current)return;url=target;owner.rememberBrowserLocation(target);
        if(committed&&!"about:blank".equals(target)){cancelZoom();if(client!=null)client.onPageStarted(null,target,null);}if(MainActivity.chatUrl(target)&&!LoginPagePolicy.login(target))owner.prefs.edit().putString("url",target).apply();
      }
      @Override public void onCanGoBack(GeckoSession s,boolean value){if(destroyed||!locations.containsKey(s))return;backStates.put(s,value);if(s==current)canBack=value;}
      @Override public GeckoResult<GeckoSession> onNewSession(GeckoSession s,String target){
        if(destroyed||failed||addonDisabled||crashed.contains(s)||s!=current||popups.size()>=8||!protectionAllowsNetwork()||!identityRequestAllowed(target)||!owner.guard.allowed()||!(target==null||target.isEmpty()||"about:blank".equals(target)||allowedUrl(target)))return GeckoResult.fromValue(null);
        if(!owner.timeZone.popupAllowed()){owner.setStatus("独立时区暂不支持新窗口；请在当前页手动打开目标网址");return GeckoResult.fromValue(null);}
        ChromiumRouteLease.Handle lease=null;if(GeckoNavigationPolicy.publicWeb(target)&&!MainActivity.chatUrl(target)){lease=ChromiumRouteLease.acquireSurface();if(lease==null){owner.setStatus("线路正在更新，请稍后重试打开链接");return GeckoResult.fromValue(null);}}
        GeckoSession popup;try{popup=newSession();}catch(RuntimeException unavailable){if(lease!=null)lease.close();owner.setStatus("新网页暂时无法打开，请稍后重试");return GeckoResult.fromValue(null);}popups.add(popup);if(lease!=null){generalSessions.add(popup);generalRoutes.put(popup,lease);}
        locations.put(popup,target==null?"":target);
        owner.handler.post(()->{if(destroyed||!popups.contains(popup))return;activate(popup);});
        return GeckoResult.fromValue(popup);
      }
      @Override public GeckoResult<String> onLoadError(GeckoSession s,String target,WebRequestError error){
        return nativeNavigationFailure(s,target,"网页连接失败，请检查当前环境网络或重新加载");
      }
    });
    session.setProgressDelegate(new GeckoSession.ProgressDelegate(){
      // A download starts a network load without replacing the current document.
      // Only an authoritative location commit may invalidate its state or bridge.
      @Override public void onPageStart(GeckoSession s,String target){if(destroyed||addonDisabled||!locations.containsKey(s))return;appearanceLoads.put(s,++appearanceLoadSerial);loadingTargets.put(s,target);pendingLoads.add(s);}

      @Override public void onPageStop(GeckoSession s,boolean success){String target=loadingTargets.get(s);boolean uncommitted=pendingLoads.remove(s);if(uncommitted&&usable.contains(s)){loadingTargets.put(s,locations.get(s));return;}if(destroyed||addonDisabled||s!=current||target==null||"about:blank".equals(target)||crashed.contains(s))return;if(success&&client!=null){if(MainActivity.chatUrl(url))readCookies(MainActivity.ORIGIN,value->{if(value!=null)cookieStamp=NativeNetwork.hash(value);});pageVisible(s);client.onPageFinished(null,url);}else if(!success&&owner.pageError.isEmpty()){owner.pageError="网页暂时未能加载，请重新加载或检查网络";owner.finishNavigation(owner.pageError,false);}}
      @Override public void onSessionStateChange(GeckoSession s,GeckoSession.SessionState state){if(destroyed||!locations.containsKey(s)||state.size()==0)return;states.put(s,new GeckoSession.SessionState(state));stateDraftRevisions.put(s,LocalDraftPolicy.revision(owner.context));if(s==primary){owner.handler.removeCallbacks(checkpoint);owner.handler.postDelayed(checkpoint,300);}}
    });
    session.setContentDelegate(new GeckoSession.ContentDelegate(){
      @Override public void onCloseRequest(GeckoSession s){closePopup(s);}
      @Override public void onCrash(GeckoSession s){contentStopped(s,"网页进程已退出，点按重新加载可恢复当前环境");}
      @Override public void onKill(GeckoSession s){contentStopped(s,"网页被系统关闭，点按重新加载可恢复当前环境");}
      @Override public void onFirstContentfulPaint(GeckoSession s){pageVisible(s);}
      @Override public void onExternalResponse(GeckoSession s,WebResponse response){
        if(!destroyed&&s==current&&owner.guard.allowed()&&responseDownload!=null){pendingLoads.remove(s);loadingTargets.put(s,locations.get(s));responseDownload.receive(response);return;}
        if(response.body!=null)try{response.body.close();}catch(IOException ignored){}
      }
    });
    session.setPromptDelegate(new GeckoSession.PromptDelegate(){
      @Override public GeckoResult<PromptResponse> onFilePrompt(GeckoSession s,FilePrompt prompt){
        GeckoResult<PromptResponse> result=new GeckoResult<>();
        final WebChromeClient requestChrome=chrome;
        if(destroyed||requestChrome==null||s!=current){result.complete(prompt.dismiss());return result;}
        WebChromeClient.FileChooserParams params=new WebChromeClient.FileChooserParams(){
          @Override public int getMode(){return prompt.type==FilePrompt.Type.MULTIPLE?MODE_OPEN_MULTIPLE:MODE_OPEN;}
          @Override public String[] getAcceptTypes(){return prompt.mimeTypes;}
          @Override public boolean isCaptureEnabled(){return false;}
          @Override public CharSequence getTitle(){return prompt.title;}
          @Override public String getFilenameHint(){return "";}
          @Override public Intent createIntent(){return new Intent(Intent.ACTION_OPEN_DOCUMENT).setType("*/*").addCategory(Intent.CATEGORY_OPENABLE);}
        };
        final long uploadEpoch=owner.navigationEpoch;owner.resourceFileWork(true,true);
        java.util.concurrent.atomic.AtomicBoolean selected=new java.util.concurrent.atomic.AtomicBoolean();
        java.util.concurrent.atomic.AtomicBoolean cancelled=new java.util.concurrent.atomic.AtomicBoolean();
        ValueCallback<Uri[]> selection=uris->{
          if(!selected.compareAndSet(false,true))return;
          if(uris==null||uris.length==0||destroyed||cancelled.get()||prompt.isComplete()){
            owner.resourceFileWork(true,false);if(!prompt.isComplete())result.complete(prompt.dismiss());return;
          }
          // The picker puts the Activity in the background. Transfer ownership
          // before releasing it so Gecko never briefly becomes inactive here.
          owner.resourceFileWork(false,true);
          owner.resourceFileWork(true,false);
          final String beforePreparation=owner.status;owner.setStatus("准备附件…");
          try{uploadWorker.execute(()->{try{
            GeckoUploadFiles.Selection files=GeckoUploadFiles.prepare(owner.context,uris,cancelled::get);
            owner.handler.post(()->{try{
              if(destroyed||cancelled.get()||s!=current||!s.isOpen()||uploadEpoch!=owner.navigationEpoch||prompt.isComplete()){retireUnhandedUpload(files);if(!prompt.isComplete())result.complete(prompt.dismiss());return;}
              PromptResponse response;
              try{response=prompt.confirm(owner.context,files.files);}
              catch(RuntimeException error){retireUnhandedUpload(files);if(!prompt.isComplete())result.complete(prompt.dismiss());owner.setStatus("附件未能交给网页，请重新选择");return;}
              uploadFiles.add(files);owner.resourceFilesPrepared(files.files,uploadEpoch);result.complete(response);
            }finally{uploadPreparationFinished(beforePreparation);}});
          }catch(IOException error){if(error instanceof GeckoUploadFiles.Cancelled)lastUploadCleanup=((GeckoUploadFiles.Cancelled)error).cleanup;owner.handler.post(()->{uploadPreparationFinished(beforePreparation);if(!prompt.isComplete())result.complete(prompt.dismiss());if(!destroyed&&!cancelled.get())owner.setStatus(error.getMessage());});}});}
          catch(RejectedExecutionException error){uploadPreparationFinished(beforePreparation);if(!prompt.isComplete())result.complete(prompt.dismiss());if(!destroyed)owner.setStatus("附件读取已结束，请重新打开文件选择器");}
        };
        prompt.setDelegate(new PromptInstanceDelegate(){
          @Override public void onPromptDismiss(BasePrompt ignored){
            cancelled.set(true);
            // Gecko dismisses an obsolete prompt without completing BasePrompt.
            // Complete it once and close only the picker belonging to this request.
            if(requestChrome instanceof Attachments.Chrome)((Attachments.Chrome)requestChrome).dismissFilePrompt(selection);
            selection.onReceiveValue(null);
            if(!prompt.isComplete())result.complete(prompt.dismiss());
          }
        });
        boolean handled;
        try{handled=requestChrome.onShowFileChooser(null,selection,params);}
        catch(RuntimeException error){selection.onReceiveValue(null);owner.setStatus("文件选择器未能打开，请重试");return result;}
        if(!handled)selection.onReceiveValue(null);return result;
      }
    });
    session.setPermissionDelegate(new GeckoSession.PermissionDelegate(){
      @Override public GeckoResult<Integer> onContentPermissionRequest(GeckoSession s,ContentPermission permission){if(contentPermissions==null)contentPermissions=new GeckoContentPermissions(GeckoWebView.this);return contentPermissions.request(s,permission);}
      @Override public void onAndroidPermissionsRequest(GeckoSession s,String[] permissions,Callback callback){callback.reject();}
      @Override public void onMediaPermissionRequest(GeckoSession s,String origin,MediaSource[] video,MediaSource[] audio,MediaCallback callback){callback.reject();}
    });
    return session;
  }
  final WebExtension.MessageDelegate pageMessages=new WebExtension.MessageDelegate(){
    @Override public void onConnect(WebExtension.Port port){
      GeckoSession source=port.sender.session;
      if(destroyed||source==null||!locations.containsKey(source)||!port.sender.isTopLevel()||!"pocketpage".equals(port.name))return;
      WebExtension.Port previous=ports.put(source,port);appearanceConnections.put(port,appearanceLoads.getOrDefault(source,0L));port.setDelegate(new WebExtension.PortDelegate(){
        @Override public void onPortMessage(Object message,WebExtension.Port incoming){
          if(!(message instanceof JSONObject)||incoming!=ports.get(source)||staleAppearanceConnections.contains(incoming))return;
          JSONObject data=(JSONObject)message;String kind=data.optString("kind");
          if("ready".equals(kind)||"documentReady".equals(kind))appearanceReady(port,data,"documentReady".equals(kind));
          if("appearanceVisible".equals(kind)){appearanceReady(port,data,true);return;}
          if("appearanceReceipt".equals(kind)){if(!staleAppearanceConnections.contains(incoming))appearanceSync.receive(incoming,data);return;}
          if("scale".equals(kind)){
            // Page DPR can be masked by Firefox privacy protection. Only the
            // compositor's CSS-to-surface ratio may drive native zoom.
            float width=(float)data.optDouble("width",0);
            if(Float.isFinite(width)&&width>0)viewportWidths.put(source,width);
            if(source==current&&readingOwnerVisible()){getScale();owner.reading.viewportMeasured(width*readingLayout);}return;
          }
          if(source!=current)return;
          if("documentReady".equals(kind)&&data.optString("url").equals(getUrl())&&!crashed.contains(source)){
            usable.add(source);pageVisible(source);
            owner.changed();return;
          }
          if("result".equals(kind))callbacks.complete(incoming,data.optInt("id"),data.optString("result","null"));
          else if("auditResult".equals(kind)){String value=data.optString("result","null");if(value.length()<=64000)callbacks.complete(incoming,data.optInt("id"),value);}
          else if("reply".equals(kind)&&MainActivity.chatUrl(port.sender.url)&&MainActivity.chatUrl(getUrl())&&owner.webObserver!=null){String text=data.optString("text");if(text.length()<=2*1024*1024)owner.webObserver.receive(J.parse(text),incoming);}
          else if("ready".equals(kind)&&owner.webObserver!=null)owner.webObserver.pageReady();
        }
        @Override public void onDisconnect(WebExtension.Port incoming){if(ports.get(source)==incoming)ports.remove(source);retireAppearance(incoming);if(source==current)owner.resourceObserverDisconnected(incoming);callbacks.cancel(incoming);}
      });
      if(previous!=null&&previous!=port){callbacks.cancel(previous);retireAppearance(previous);}
      if(source==current)owner.resourceObserverConnected(port);
    }
  };
  /** Native appearance events do not navigate, restart Gecko, or touch browser identity. */
  void applyAppearance(){
    if(destroyed)return;
    setBackgroundColor(ReferenceUi.CHAT_BG);
    if(runtime!=null)runtime.getSettings().setPreferredColorScheme(AppAppearance.dark()?GeckoRuntimeSettings.COLOR_SCHEME_DARK:GeckoRuntimeSettings.COLOR_SCHEME_LIGHT);
    for(GeckoSession s:locations.keySet())if(s.isOpen())s.getCompositorController().setClearColor(ReferenceUi.CHAT_BG);
    for(WebExtension.Port port:new ArrayList<>(ports.values()))appearance(port);
  }
  private void appearance(WebExtension.Port port){
    if(!appearancePage(port.sender.url)||staleAppearanceConnections.contains(port))return;
    appearanceSync.request(port,AppAppearance.dark());
  }
  private void appearanceReady(WebExtension.Port port,JSONObject data,boolean documentReady){
    if(!appearancePage(port.sender.url)||staleAppearanceConnections.contains(port)||!(data.opt("appearanceProtocol") instanceof Number)||data.optDouble("appearanceProtocol")!=1)return;
    Object value=data.opt("appearanceDocument");if(!(value instanceof String)||!((String)value).matches("[a-zA-Z0-9-]{16,80}"))return;
    String document=(String)value,previous=appearanceDocuments.get(port);if(previous!=null&&!previous.equals(document))return;
    appearanceDocuments.put(port,document);
    if(appearanceSync.connect(port,document,AppAppearance.dark())&&documentReady&&previous!=null)appearance(port);
  }
  private void appearanceCommitted(GeckoSession source){
    WebExtension.Port port=ports.get(source);if(port==null)return;
    appearanceSync.disconnect(port);
    // A document port may connect before the location callback. Its load ticket
    // distinguishes it from the old document, including a reload at the same URL.
    if(!Objects.equals(appearanceConnections.get(port),appearanceLoads.getOrDefault(source,0L))){
      appearanceDocuments.remove(port);staleAppearanceConnections.add(port);callbacks.cancel(port);return;
    }
    String document=appearanceDocuments.get(port);if(document!=null)appearanceSync.connect(port,document,AppAppearance.dark());
  }
  private void retireAppearance(WebExtension.Port port){if(port==null)return;appearanceSync.disconnect(port);appearanceConnections.remove(port);appearanceDocuments.remove(port);staleAppearanceConnections.remove(port);}
  JSONObject appearanceReport(){return appearanceSync.snapshot(current==null?null:ports.get(current));}
  protected boolean appearancePage(String target){return MainActivity.chatUrl(target);}
  protected boolean allowedUrl(String target){return target!=null&&BrowserNetworkGuard.publicWeb(Uri.parse(target));}
  boolean readingPage(String target){return BrowserReadingPolicy.chat(target)&&!LoginPagePolicy.login(target);}
  static String header(WebResponse response,String name){for(Map.Entry<String,String> entry:response.headers.entrySet())if(name.equalsIgnoreCase(entry.getKey()))return entry.getValue();return "";}
  void readCookies(String target,ValueCallback<String> callback){
    if(destroyed||!enabled||routePort==null||!allowedUrl(target)){callback.onReceiveValue(null);return;}
    WebExtension.Port port=routePort;int id=cookieCallbacks.add(port,callback::onReceiveValue,5000);
    try{port.postMessage(J.obj("kind","cookies","id",id,"url",target));}catch(Exception error){cookieCallbacks.complete(port,id,null);}
  }
  String downloadCookies(String target)throws IOException{
    if(Looper.myLooper()==Looper.getMainLooper())throw new IOException("不能在界面线程等待 Cookie");
    CountDownLatch completed=new CountDownLatch(1);String[] result={null};
    owner.handler.post(()->readCookies(target,value->{result[0]=value;completed.countDown();}));
    try{if(!completed.await(7,TimeUnit.SECONDS)||result[0]==null)throw new IOException("当前环境的登录信息暂不可用，请重试下载");return result[0];}
    catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException("下载已暂停");}
  }
  private void failure(String message){failed=true;owner.pageError=message;owner.finishNavigation(message,false);}
  boolean hasVisibleDocument(){return enabled&&current!=null&&current.isOpen()&&!failed&&!crashed.contains(current)&&usable.contains(current);}
  boolean canChooseFiles(){return hasVisibleDocument()&&!pendingLoads.contains(current)&&(!owner.navigating||owner.navigationDispatched&&owner.targetMatches(getUrl()));}
  private void uploadPreparationFinished(String previousStatus){owner.resourceFileWork(false,false);if(!destroyed&&owner.resourceFilePreparations==0&&owner.status.equals("准备附件…"))owner.setStatus(previousStatus.equals("准备附件…")?"":previousStatus);}
  private void pageVisible(GeckoSession session){
    String target=loadingTargets.get(session);
    if(destroyed||addonDisabled||session!=current||target==null||"about:blank".equals(target)||crashed.contains(session)||!painted.add(session))return;
    if(client!=null)client.onPageCommitVisible(null,url);
  }
  private void contentStopped(GeckoSession session,String message){
    if(session==current)closeExitIpPage();
    if(destroyed||!locations.containsKey(session))return;
    retireTimeZone(session);
    crashed.add(session);pendingLoads.remove(session);painted.remove(session);usable.remove(session);WebExtension.Port port=ports.remove(session);if(port!=null){callbacks.cancel(port);retireAppearance(port);}
    forgetGeneralRoute(session);
    if(session==current){cancelZoom();failed=true;owner.webObserver.suspendUnconfirmed("网页进程已关闭，原发送结果需要核对");
      if(owner.uiVisible&&owner.guard.allowed()&&canRecoverAutomatically()){owner.manualAttention=false;owner.beginNavigation(url,"正在恢复当前网页…");owner.handler.removeCallbacks(recovery);owner.handler.postDelayed(recovery,250);}
      else if(owner.uiVisible)failure(message);
    }
  }
  private void saveCheckpoint(){GeckoSession.SessionState state=states.get(primary);if(state!=null)sessionStore.write(state::toString,stateDraftRevisions.getOrDefault(primary,-1L));}
  void checkpointState(){if(!enabled||destroyed)return;for(GeckoSession session:new ArrayList<>(locations.keySet()))if(session.isOpen())session.flushSessionState();saveCheckpoint();}
  private boolean canRecoverAutomatically(){long now=SystemClock.elapsedRealtime();if(now-recoveryWindow>60000){recoveryWindow=now;contentRecoveries=0;}return contentRecoveries<2;}
  boolean recoverClosed(){
    if(destroyed||!enabled||current==null||!crashed.contains(current)||!owner.uiVisible||!protectionAllowsNetwork()||!owner.guard.allowed())return false;
    owner.handler.removeCallbacks(recovery);contentRecoveries++;
    String target=locations.getOrDefault(current,owner.resumeUrl());
    if(!allowedUrl(target))target=owner.resumeUrl();
    if(!identityRequestAllowed(target))return false;
    GeckoSession.SessionState state=states.get(current);
    if(!reopenCurrent())return false;
    owner.pageMemory.restorePending=true;
    owner.pageError="";owner.manualAttention=false;owner.beginNavigation(target,"正在恢复当前网页…");
    if(state!=null&&state.size()>0)restoreCheckpoint(current,state,target,stateDraftRevisions.getOrDefault(current,-1L));else loadSessionUri(current,target);
    return true;
  }
  private boolean reopenCurrent(){try{
    retireTimeZone(current);
    measuredCompositors.remove(current);pageScales.remove(current);
    if(surface.getSession()!=null)surface.releaseSession();if(current.isOpen())current.close();current.open(runtime);surface.setSession(current);
    current.setActive(!owner.browserPaused);crashed.remove(current);failed=false;configure(desktop,owner.privacy.level());return true;
  }catch(Exception error){failure("网页暂未恢复，请重新打开当前环境");return false;}}
  private void activate(GeckoSession session){
    closeExitIpPage();
    cancelZoom();
    GeckoSession previous=current;
    if(surface.getSession()!=null)surface.releaseSession();
    if(previous!=null){if(previous.isOpen())previous.setActive(false);WebExtension.Port port=ports.get(previous);if(port!=null)callbacks.cancel(port);}
    current=session;metadata.timeZonePolicy=timeZoneStatus();owner.resourceObserverConnected(ports.get(session));url=locations.getOrDefault(session,"");canBack=backStates.getOrDefault(session,false);scale=pageScales.getOrDefault(session,1f)*readingLayout;
    failed=crashed.contains(session);
    if(!failed){surface.setSession(session);session.setActive(!owner.browserPaused);}
    configure(desktop,owner.privacy.level());
    if(!url.isEmpty()&&!"about:blank".equals(url)){
      owner.reading.started(url);owner.reading.viewportMeasured(viewportWidths.getOrDefault(session,0f)*readingLayout);if(painted.contains(session))owner.reading.visible(url);
    }
  }
  void configure(boolean desktop,int protection){
    closeExitIpPage();
    if(configuredProtection!=protection)retireTimeZones();this.desktop=desktop;configuredProtection=protection;long revision=++identityPolicyRevision;
    retireRequestHeaderPolicy();
    metadata.desktop=desktop;metadata.policyAcknowledged=false;metadata.userAgent="";metadata.acceptedBrowserIdentity=new JSONObject();
    GeckoPolicyAdapter.applyRuntime(runtime,protection);
    applyIdentityLocales();
    if(routePort!=null&&(requestedProtection!=protection||protection<2&&privacyReady&&!metadata.rfpAcknowledged))requestProtection(routePort,"protection",protection);
    for(GeckoSession session:new ArrayList<>(locations.keySet()))GeckoPolicyAdapter.applySession(session,desktop,protection);
    if(current!=null&&current.isOpen()){GeckoSession source=current;source.getUserAgent().accept(value->{if(!destroyed&&source==current&&this.desktop==desktop&&identityPolicyRevision==revision){metadata.userAgent=value;acknowledgeIdentity();}},error->{});}
  }
  void acknowledgeIdentity(){
    metadata.policyAcknowledged=runtime!=null&&current!=null&&current.isOpen()&&privacyReady&&protectionLevel==configuredProtection&&!metadata.userAgent.isEmpty()&&metadata.rfpAcknowledged&&metadata.localesRequestAcknowledged&&(protectionLevel<2||fingerprintingProtected);
    metadata.policyError=metadata.policyAcknowledged?"":protectionLevel>=2&&!fingerprintingProtected?"原生强化请求尚未取得设置回读":"等待 SDK 请求或设置回读";
    if(metadata.policyAcknowledged){metadata.acceptedBrowserIdentity=BrowserIdentitySpec.legacy(desktop,configuredProtection).withLocales(identityPolicy==null?Collections.emptyList():identityPolicy.locales).json();owner.identityPolicyAcknowledged();}
  }
  private void requestProtection(WebExtension.Port port,String kind,int level){
    owner.cpu.protectionWillChange();closeExitIpPage();
    cancelProtectionTasks();nativeProtection.begin(level);requestedProtection=level;
    if(level<0||level>2){privacyReady=fingerprintingProtected=false;metadata.rfpAcknowledged=metadata.policyAcknowledged=false;owner.setStatus("保护等级无效，请主动重新选择保护等级");owner.changed();return;}
    sendProtectionAttempt(port,kind);
  }
  private void prepareProtectionBridge(WebExtension.Port port){routePrepared=false;requestProtection(port,"prepare",owner.privacy.level());}
  private void sendProtectionAttempt(WebExtension.Port port,String kind){
    if(destroyed||port!=routePort||requestedProtection!=owner.privacy.level())return;
    privacyReady=false;fingerprintingProtected=false;metadata.rfpAcknowledged=false;metadata.policyAcknowledged=false;
    long token=nativeProtection.request(),generation=nativeProtection.generation();int level=requestedProtection;protectionRequest=token;
    retireRequestHeaderPolicy();
    protectionTimeout=()->{if(!destroyed&&port==routePort&&level==owner.privacy.level()&&nativeProtection.timeout(token,generation,level)){protectionTimeout=null;protectionAttemptFinished(port);}};
    owner.handler.postDelayed(protectionTimeout,NativeProtectionState.WAIT_MS);
    try{port.postMessage(J.obj("kind",kind,"level",level,"token",token,"generation",generation,"timeoutMs",NativeProtectionState.WAIT_MS));}
    catch(RuntimeException error){cancelProtectionTasks();nativeProtection.fail("bridge-send-failed");protectionAttemptFinished(port);}
    if(level>=2&&!nativeProtection.confirmed())owner.setStatus(protectionSummary());
    owner.changed();
  }
  private void cancelProtectionTasks(){
    if(protectionTimeout!=null)owner.handler.removeCallbacks(protectionTimeout);
    if(protectionRetry!=null)owner.handler.removeCallbacks(protectionRetry);
    protectionTimeout=protectionRetry=null;
  }
  private void protectionAttemptFinished(WebExtension.Port port){
    protectionLevel=requestedProtection;fingerprintingProtected=nativeProtection.confirmed()&&nativeProtection.fingerprinting();
    metadata.rfpAcknowledged=nativeProtection.confirmed();privacyReady=requestedProtection<2||nativeProtection.confirmed();
    owner.cpu.refreshNative();acknowledgeIdentity();
    if(!privacyReady&&nativeProtection.canRetry()){
      nativeProtection.awaitingRetry();long generation=nativeProtection.generation();
      protectionRetry=()->{protectionRetry=null;if(!destroyed&&port==routePort&&generation==nativeProtection.generation()&&requestedProtection==owner.privacy.level())sendProtectionAttempt(port,"protection");};
      owner.handler.postDelayed(protectionRetry,NativeProtectionState.RETRY_MS);
    }
    if(requestedProtection>=2&&!nativeProtection.confirmed())owner.setStatus(protectionSummary());
    owner.changed();if(privacyReady){resumeProtectedLoads();maybeOpen();}
  }
  private void resumeProtectedLoads(){
    if(!ready||!protectionAllowsNetwork())return;
    if(current!=null&&!timeZoneAllows(current)){prepareTimeZone(current,ok->{if(ok)resumeProtectedLoads();});return;}
    ProtectionRestore restore=protectionRestore;protectionRestore=null;
    if(restore!=null&&restore.session==current&&restore.navigation==owner.navigationEpoch&&(queued.isEmpty()||queued.equals(restore.url))){queued="";restoreCheckpoint(restore.session,restore.state,restore.url,restore.draftRevision);return;}
    if(!queued.isEmpty()){String target=queued;queued="";loadUrl(target);}
  }
  boolean protectionAllowsNetwork(){return owner.cpu.readyFor(runtime)&&nativeProtection.allows(owner.privacy.level());}
  boolean protectionBootstrapBlocked(){return !destroyed&&!failed&&!ready&&surface==null&&current==null&&primary==null&&locations.isEmpty()&&popups.isEmpty()&&owner.privacy.level()>=2&&nativeProtection.level()==owner.privacy.level()&&"failed".equals(nativeProtection.state());}
  boolean retryProtection(){
    if(destroyed||nativeProtection.level()==owner.privacy.level()&&("pending".equals(nativeProtection.state())||nativeProtection.confirmed()))return false;
    if(routePort==null){owner.setStatus("浏览器保护通道未连接，正在等待重新连接");return false;}
    requestProtection(routePort,"protection",owner.privacy.level());return true;
  }
  JSONObject protectionStatus(){boolean current=nativeProtection.level()==owner.privacy.level();return J.obj("state",current?nativeProtection.state():"pending","desiredLevel",owner.privacy.level(),"level",nativeProtection.level(),"generation",nativeProtection.generation(),"token",nativeProtection.token(),"attempt",nativeProtection.attempt(),"maxAttempts",NativeProtectionState.MAX_ATTEMPTS,"reason",current?nativeProtection.reason():"configuration-changed","received",current&&nativeProtection.received(),"settingsReadbackConfirmed",current&&nativeProtection.confirmed(),"observedFingerprinting",nativeProtection.fingerprinting(),"newRequestsBlocked",!protectionAllowsNetwork(),"retryAvailable",!destroyed&&routePort!=null&&(!current||"failed".equals(nativeProtection.state())),"scope","native-setting-new-request-admission","fullApiProtectionAttested",false);}
  String protectionSummary(){
    if(nativeProtection.level()!=owner.privacy.level())return owner.privacy.level()>=2?"强化保护等待当前配置确认，确认前暂停新网页请求":"当前保护配置尚待确认";
    String state=nativeProtection.state();if("confirmed".equals(state))return owner.privacy.level()>=2?"强化保护已确认（原生设置回读）":"原生保护设置已确认";
    if("pending".equals(state))return owner.privacy.level()>=2?"强化保护确认中（"+Math.max(1,nativeProtection.attempt())+"/"+NativeProtectionState.MAX_ATTEMPTS+"），确认前暂停新网页请求":"原生保护设置确认中";
    String reason=nativeProtection.reason(),detail="setting-timeout".equals(reason)?"设置回读超时":"bridge-disconnected".equals(reason)||"bridge-send-failed".equals(reason)?"浏览器保护通道未连接":"setting-unavailable".equals(reason)?"内核未提供原生设置接口":"setting-changed".equals(reason)?"原生设置已变化":"原生设置未取得一致回读";
    return owner.privacy.level()>=2?"强化保护失败："+detail+"；新网页请求已暂停，可重试或主动选择标准模式":"原生保护设置未确认："+detail;
  }
  private static long protectionCounter(JSONObject data,String key){
    Object value=data.opt(key);if(!(value instanceof Number))return -1;
    double number=((Number)value).doubleValue();return Double.isFinite(number)&&number>=0&&number<=9007199254740991d&&number==Math.rint(number)?((Number)value).longValue():-1;
  }
  private static int protectionReceiptLevel(JSONObject data){long level=protectionCounter(data,"level");return level>=0&&level<=2?(int)level:-1;}
  private boolean identityRequestAllowed(String target){return !RequestIdentityAudit.diagnosticUrl(target)||owner.audit!=null&&owner.audit.requestIdentityAllowsRequest(target);}
  void configureIdentity(BrowserIdentitySpec specification){
    closeExitIpPage();
    String issue=specification.validate();if(!issue.isEmpty())throw new IllegalArgumentException(issue);
    identityPolicyRevision++;identityPolicy=specification;metadata.policyAcknowledged=false;metadata.acceptedBrowserIdentity=new JSONObject();applyIdentityLocales();
  }
  private void applyIdentityLocales(){
    ArrayList<String> selected=new ArrayList<>();
    if(identityPolicy!=null&&!identityPolicy.locales.isEmpty())selected.addAll(identityPolicy.locales);
    else{android.os.LocaleList system=owner.context.getResources().getConfiguration().getLocales();for(int i=0;i<system.size()&&i<3;i++)selected.add(system.get(i).toLanguageTag());}
    if(selected.isEmpty())selected.add(Locale.getDefault().toLanguageTag());
    String[] locales=selected.toArray(new String[0]);
    metadata.expectedSdkLocales=BrowserIdentitySpec.expectedSdkLocales(selected).toArray(new String[0]);
    try{metadata.localesRequestAcknowledged=GeckoPolicyAdapter.applyLocales(runtime,locales);metadata.requestedLocales=metadata.localesRequestAcknowledged?runtime.getSettings().getLocales().clone():new String[0];}
    catch(Exception failure){metadata.localesRequestAcknowledged=false;metadata.requestedLocales=new String[0];}
  }
  String identityLanguage(){return metadata.localesRequestAcknowledged&&metadata.expectedSdkLocales.length>0?metadata.expectedSdkLocales[0]:"";}
  void useEngine(boolean value){if(!value)throw new IllegalStateException("正式应用仅使用 Firefox 内核");}
  boolean closePopup(){
    return closePopup(current);
  }
  private boolean closePopup(GeckoSession old){
    if(destroyed||!popups.remove(old))return false;
    retireTimeZone(old);
    if(old==current){activate(popups.isEmpty()?primary:popups.get(popups.size()-1));owner.pageError="";if(crashed.contains(current))contentStopped(current,"上一页被系统关闭，点按重新加载可恢复");else{owner.beginNavigation(url,"正在返回上一页…");owner.resourceObserverConnected(ports.get(current));if(client!=null&&painted.contains(current)){client.onPageCommitVisible(null,url);client.onPageFinished(null,url);}}}
    forgetGeneralRoute(old);WebExtension.Port port=ports.remove(old);if(port!=null){callbacks.cancel(port);retireAppearance(port);}appearanceLoads.remove(old);
    locations.remove(old);backStates.remove(old);pageScales.remove(old);measuredCompositors.remove(old);viewportWidths.remove(old);loadingTargets.remove(old);pendingLoads.remove(old);painted.remove(old);usable.remove(old);crashed.remove(old);states.remove(old);stateDraftRevisions.remove(old);
    if(old.isOpen())old.close();return true;
  }
  boolean hasWebsitePages(){return !generalSessions.isEmpty()||GeckoNavigationPolicy.publicWeb(getUrl())&&!MainActivity.chatUrl(getUrl());}
  void closeWebsitePages(){
    closeExitIpPage();
    generalRestore=null;queued="";deferredGeneralLoads.clear();
    for(GeckoSession popup:new ArrayList<>(popups))closePopup(popup);
    if(current==null)return;
    WebExtension.Port port=ports.remove(current);if(port!=null){callbacks.cancel(port);retireAppearance(port);}
    current.stop();states.remove(current);stateDraftRevisions.remove(current);painted.remove(current);usable.remove(current);loadingTargets.remove(current);pendingLoads.remove(current);startupState=null;
    locations.put(current,"");url="";canBack=false;forgetGeneralRoute(current);
    if(current.isOpen())reopenCurrent();
  }
  public void loadUrl(String target){
    closeExitIpPage();
    if(destroyed)return;if(!allowedUrl(target)){owner.setStatus("仅支持公共 HTTP 或 HTTPS 网页");return;}if(!identityRequestAllowed(target)){owner.setStatus("检测地址已失效，请重新开始身份检查");return;}if(rejectDisabledNavigation(current,target))return;queued=target;
    if(!ready||!privacyReady||!requestHeadersInstalled||current==null||!protectionAllowsNetwork()||!owner.guard.allowed())return;
    if(crashed.contains(current)){
      if(!reopenCurrent())return;
    }
    final GeckoSession source=current;final Object intent=claimTimeZoneIntent(source,false);
    if(!timeZoneAllows(current)){prepareTimeZone(current,ok->{if(timeZoneIntents.get(source)!=intent||current!=source)return;if(!ok){clearTimeZoneIntent(source,intent);return;}if(!queued.isEmpty())loadUrl(queued);});return;}
    if(!retainGeneralRoute(current,target)||!generalRouteReady()){owner.setStatus("线路正在更新，完成后继续打开网页");return;}
    GeckoSession.SessionState saved=startupState;startupState=null;
    if(current==primary&&saved!=null&&target.equals(stateUrl(saved))){queued="";states.put(primary,saved);stateDraftRevisions.put(primary,startupDraftRevision);restoreCheckpoint(current,saved,target,startupDraftRevision);return;}
    queued="";clearTimeZoneIntent(source,intent);current.loadUri(target);
  }
  void restoreCheckpoint(GeckoSession target,GeckoSession.SessionState state,String url,long savedRevision){
    if(rejectDisabledNavigation(target,url)||!identityRequestAllowed(url))return;
    final Object intent=claimTimeZoneIntent(target,true);
    if(!timeZoneAllows(target)){final long navigation=owner.navigationEpoch;prepareTimeZone(target,ok->{if(ok&&timeZoneIntents.get(target)==intent&&current==target&&navigation==owner.navigationEpoch)restoreCheckpoint(target,state,url,savedRevision);});return;}
    if(!retainGeneralRoute(target,url)||!generalRouteReady()){generalRestore=new ProtectionRestore(target,state,url,savedRevision,owner.navigationEpoch);return;}
    if(!protectionAllowsNetwork()){protectionRestore=new ProtectionRestore(target,state,url,savedRevision,owner.navigationEpoch);return;}
    if(LocalDraftPolicy.enabled(owner.context)&&savedRevision==LocalDraftPolicy.revision(owner.context)){clearTimeZoneIntent(target,intent);target.restoreState(state);return;}
    final long epoch=owner.navigationEpoch;
    // SDK serialization stays on the existing worker. Only form data is removed;
    // navigation history and scroll are still restored through the SDK itself.
    sessionStore.io.execute(()->{
      String value;try{value=LocalDraftPolicy.checkpoint(state.toString(),false);}catch(RuntimeException invalid){value=null;}
      final String filtered=value;
      owner.handler.post(()->{
        if(destroyed||owner.deleted||timeZoneIntents.get(target)!=intent||current!=target||owner.navigationEpoch!=epoch||!target.isOpen()||!owner.guard.allowed())return;
        if(!identityRequestAllowed(url))return;
        if(!timeZoneAllows(target)){prepareTimeZone(target,ok->{if(ok&&timeZoneIntents.get(target)==intent&&current==target&&epoch==owner.navigationEpoch)restoreCheckpoint(target,state,url,savedRevision);});return;}
        if(!protectionAllowsNetwork()){protectionRestore=new ProtectionRestore(target,state,url,savedRevision,epoch);return;}
        GeckoSession.SessionState safe=filtered==null?null:GeckoSession.SessionState.fromString(filtered);
        clearTimeZoneIntent(target,intent);if(safe!=null&&safe.size()>0)target.restoreState(safe);else target.loadUri(url);
      });
    });
  }
  static String stateUrl(GeckoSession.SessionState state){try{return state.get(state.getCurrentIndex()).getUri();}catch(Exception ignored){return "";}}
  public String getUrl(){return url;}
  public void evaluateJavascript(String code,ValueCallback<String> callback){
    if(destroyed){if(callback!=null)callback.onReceiveValue("null");return;}
    WebExtension.Port port=ports.get(current);if(port==null||staleAppearanceConnections.contains(port)){if(callback!=null)callback.onReceiveValue("null");return;}
    int id=callbacks.add(port,callback==null?null:callback::onReceiveValue,10000);
    try{port.postMessage(J.obj("kind","evaluate","id",id,"code",code));}catch(Exception error){callbacks.complete(port,id,"null");}
  }
  void runEnvironmentAudit(JSONObject configuration,ValueCallback<String> callback){
    WebExtension.Port port=ports.get(current);
    if(destroyed||port==null||staleAppearanceConnections.contains(port)){callback.onReceiveValue("null");return;}
    int request=callbacks.add(port,callback::onReceiveValue,14000);
    try{port.postMessage(J.obj("kind","audit","id",request,"configuration",configuration));}
    catch(Exception error){callbacks.complete(port,request,"null");}
  }
  void requestIdentityScope(JSONObject configuration,ValueCallback<String> callback){
    WebExtension.Port port=routePort;
    if(destroyed||port==null){callback.onReceiveValue("null");return;}
    int request=cookieCallbacks.add(port,callback::onReceiveValue,8000);
    try{port.postMessage(J.obj("kind","requestIdentityScope","id",request,"configuration",configuration));}
    catch(RuntimeException error){cookieCallbacks.complete(port,request,"null");}
  }
  void cancelEnvironmentAudit(){WebExtension.Port port=ports.get(current);if(port!=null)try{port.postMessage(J.obj("kind","auditCancel"));}catch(Exception ignored){}}
  public void stopLoading(){queued="";protectionRestore=null;generalRestore=null;if(current!=null){deferredGeneralLoads.remove(current);loadingTargets.remove(current);pendingLoads.remove(current);current.stop();if(MainActivity.chatUrl(locations.get(current)))forgetGeneralRoute(current);}}
  public void setWebViewClient(WebViewClient value){client=value;}
  public void setWebChromeClient(WebChromeClient value){chrome=value;}
  public void setDownloadListener(DownloadListener value){download=value;}
  public void onPause(){closeExitIpPage();checkpointState();if(current!=null&&current.isOpen())current.setActive(false);}
  public void onResume(){
    if(current!=null&&crashed.contains(current)&&canRecoverAutomatically())owner.handler.post(recovery);
    else{
      if(current!=null&&current.isOpen())current.setActive(true);
      if(!destroyed&&failed&&owner.uiVisible&&current!=null&&crashed.contains(current)&&owner.pageError.isEmpty()){
        // This foreground notice must not start or replace a network retry.
        owner.navigating=false;owner.navigationFailed=true;
        owner.pageError="网页多次退出，自动恢复已暂停；请检查连接后点按重新加载";
        owner.status=owner.pageError;owner.changed();
      }
    }
  }
  public void pauseTimers(){}
  public void resumeTimers(){}
  public boolean canGoBack(){return hasExitIpPage()||canBack||!popups.isEmpty();}
  public void goBack(){if(closeExitIpPage())return;if(canBack&&current!=null){if(!protectionAllowsNetwork()){owner.setStatus(protectionSummary());return;}current.goBack();}else closePopup();}
  public float getScale(){
    if(readingOwnerVisible()&&current!=null&&current.isOpen()&&measuredCompositors.contains(current)){
      current.getClientToSurfaceMatrix(readingMatrix);readingMatrix.getValues(readingValues);
      float value=readingValues[Matrix.MSCALE_X];
      if(Float.isFinite(value)&&value>0){pageScales.put(current,value);scale=value*readingLayout;}
    }
    return scale;
  }
  boolean readingScaleMeasured(){return readingOwnerVisible()&&current!=null&&measuredCompositors.contains(current);}
  boolean readingZoomActive(){return zoomTarget!=null;}
  int readingTouchSlop(){return ViewConfiguration.get(getContext()).getScaledTouchSlop();}
  float readingScrollY(){
    if(!readingOwnerVisible()||destroyed||failed||current==null||!current.isOpen()||!readingScaleMeasured())return Float.NaN;
    current.getClientToSurfaceMatrix(readingMatrix);readingMatrix.getValues(readingValues);
    float zoom=readingValues[Matrix.MSCALE_X],clientTop=readingValues[Matrix.MTRANS_Y];
    if(!Float.isFinite(zoom)||zoom<=0)return Float.NaN;
    current.getPageToSurfaceMatrix(readingMatrix);readingMatrix.getValues(readingValues);
    return (clientTop-readingValues[Matrix.MTRANS_Y])/zoom;
  }
  void alignReadingLeft(float savedY){
    if(!readingOwnerVisible()||destroyed||failed||current==null||!current.isOpen()||surface==null)return;
    float y=Float.isFinite(savedY)?savedY:readingScrollY();if(!Float.isFinite(y))return;
    // This public API scrolls Gecko's visual viewport, including APZ offsets.
    // Retain the current reading position rather than returning to page top.
    current.getPanZoomController().scrollTo(ScreenLength.zero(),ScreenLength.fromPixels(Math.max(0,y)),PanZoomController.SCROLL_BEHAVIOR_AUTO);
  }
  Rect readingFocusBounds(){
    Rect visible=new Rect();if(!getGlobalVisibleRect(visible))return visible;int[] rootOrigin=new int[2];getRootView().getLocationOnScreen(rootOrigin);visible.offset(rootOrigin[0],rootOrigin[1]);
    WindowInsets window=getRootWindowInsets();if(Build.VERSION.SDK_INT>=30&&window!=null&&window.isVisible(WindowInsets.Type.ime())){
      WindowManager manager=displayContext.getSystemService(WindowManager.class);if(manager==null)return new Rect();visible.bottom=Math.min(visible.bottom,manager.getCurrentWindowMetrics().getBounds().bottom-window.getInsets(WindowInsets.Type.ime()).bottom);
    }
    return visible;
  }
  void revealReadingFocus(String expectedUrl,java.util.function.BooleanSupplier stillCurrent){
    final GeckoSession target=current;final GeckoView focusSurface=surface;if(!readingOwnerVisible()||destroyed||failed||target==null||!target.isOpen()||focusSurface==null||!readingPage(expectedUrl)||!expectedUrl.equals(getUrl())||!stillCurrent.getAsBoolean())return;
    final long focusZoomEpoch=zoomEpoch;final float layout=readingLayout;final int viewWidth=getWidth(),viewHeight=getHeight(),surfaceWidth=focusSurface.getWidth(),surfaceHeight=focusSurface.getHeight();final Rect visible=readingFocusBounds();final int[] origin=new int[2];focusSurface.getLocationOnScreen(origin);if(visible.isEmpty())return;
    evaluateJavascript(BrowserReadingPolicy.focusScript(expectedUrl),raw->{
      if(!readingOwnerVisible()||destroyed||failed||current!=target||!target.isOpen()||surface!=focusSurface||surface.getSession()!=target||!surface.isShown()||!expectedUrl.equals(getUrl()))return;
      WindowInsets window=getRootWindowInsets();if(Build.VERSION.SDK_INT>=30&&(window==null||!window.isVisible(WindowInsets.Type.ime())))return;
      int[] now=new int[2];focusSurface.getLocationOnScreen(now);if(focusZoomEpoch!=zoomEpoch||layout!=readingLayout||viewWidth!=getWidth()||viewHeight!=getHeight()||surfaceWidth!=focusSurface.getWidth()||surfaceHeight!=focusSurface.getHeight()||origin[0]!=now[0]||origin[1]!=now[1]||!visible.equals(readingFocusBounds()))return;
      JSONObject measured=J.parse(raw),rect=measured.optJSONObject("rect");if(!measured.optBoolean("ok")||!expectedUrl.equals(measured.optString("url"))||rect==null||!stillCurrent.getAsBoolean())return;
      Matrix matrix=new Matrix();target.getPageToSurfaceMatrix(matrix);float[] values=new float[9];matrix.getValues(values);float factor=values[Matrix.MSCALE_Y]*layout;
      float[] points={(float)rect.optDouble("left",Double.NaN),(float)rect.optDouble("top",Double.NaN),(float)rect.optDouble("right",Double.NaN),(float)rect.optDouble("bottom",Double.NaN)};matrix.mapPoints(points);
      float visibleTop=visible.top-origin[1],caretTop=Float.NaN,caretBottom=Float.NaN;JSONObject caret=measured.optJSONObject("caret");if(caret!=null){float[] cp={(float)caret.optDouble("left",Double.NaN),(float)caret.optDouble("top",Double.NaN),(float)caret.optDouble("right",Double.NaN),(float)caret.optDouble("bottom",Double.NaN)};matrix.mapPoints(cp);caretTop=cp[1]*layout-visibleTop;caretBottom=cp[3]*layout-visibleTop;}
      float margin=8*getResources().getDisplayMetrics().density;float delta=BrowserReadingPolicy.focusScroll(points[1]*layout-visibleTop,points[3]*layout-visibleTop,caretTop,caretBottom,visible.height(),margin,factor);
      if(delta!=0&&Float.isFinite(delta)){target.getPanZoomController().scrollBy(ScreenLength.zero(),ScreenLength.fromPixels(delta),PanZoomController.SCROLL_BEHAVIOR_AUTO);readingFocusScrolls++;readingFocusScrollDelta=delta;readingFocusHadClipping|=points[1]*layout<visibleTop||points[3]*layout>visible.bottom-origin[1];}
    });
  }
  boolean requiresViewportMeasurement(){return true;}
  public void setInitialScale(int percent){}
  boolean setReadingLayout(float choice){
    if(!readingOwnerVisible())return false;
    if(!enabled)return false;float next=Math.min(1,BrowserReadingPolicy.bounded(choice));if(Math.abs(next-readingLayout)<.001f)return false;
    cancelZoom();float previous=readingLayout;readingLayout=next;scale=scale/previous*next;
    if(surface!=null){surface.setPivotX(0);surface.setPivotY(0);surface.setScaleX(next);surface.setScaleY(next);}
    requestLayout();return true;
  }
  public void zoomBy(float factor){
    if(!readingOwnerVisible()||destroyed||failed||current==null||!current.isOpen()||surface==null||factor<=0||!Float.isFinite(factor))return;
    cancelZoom();final GeckoSession target=current;final long started=SystemClock.uptimeMillis(),epoch=zoomEpoch;
    final float x=surface.getWidth()/2f,y=surface.getHeight()/2f,radius=Math.min(surface.getWidth()/5f,48*getResources().getDisplayMetrics().density);
    final float amount=Math.max(.1f,Math.min(10f,factor));
    if(radius<=0)return;
    zoomTarget=target;zoomStarted=started;zoomX=x;zoomY=y;zoomRadius=radius;
    pinch(target,started,MotionEvent.ACTION_DOWN,1,x,y,radius);
    pinch(target,started,MotionEvent.ACTION_POINTER_DOWN|(1<<MotionEvent.ACTION_POINTER_INDEX_SHIFT),2,x,y,radius);
    // ScaleGestureDetector consumes the movement that crosses touch slop as
    // its starting span. Establish that span before applying the requested ratio.
    final float primed=radius*1.6f;
    for(int step=0;step<12;step++){final int n=step;owner.handler.postDelayed(()->{
      if(!readingOwnerVisible()||target!=current||!enabled||destroyed||failed||epoch!=zoomEpoch||!target.isOpen())return;
      float next=primed*(1+(amount-1)*Math.max(0,n-1)/10f);pinch(target,started,MotionEvent.ACTION_MOVE,2,x,y,next);
      if(n==11){pinch(target,started,MotionEvent.ACTION_POINTER_UP|(1<<MotionEvent.ACTION_POINTER_INDEX_SHIFT),2,x,y,next);pinch(target,started,MotionEvent.ACTION_UP,1,x,y,next);zoomTarget=null;owner.reading.nativeZoomFinished();}
    },(step+1)*16L);}
  }
  private void cancelZoom(){zoomEpoch++;if(zoomTarget!=null&&zoomTarget.isOpen())pinch(zoomTarget,zoomStarted,MotionEvent.ACTION_CANCEL,1,zoomX,zoomY,zoomRadius);zoomTarget=null;}
  private void pinch(GeckoSession target,long start,int action,int count,float x,float y,float radius){
    MotionEvent.PointerProperties[] properties=new MotionEvent.PointerProperties[count];MotionEvent.PointerCoords[] coordinates=new MotionEvent.PointerCoords[count];
    int[] origin=new int[2];if(surface!=null)surface.getLocationOnScreen(origin);
    for(int i=0;i<count;i++){properties[i]=new MotionEvent.PointerProperties();properties[i].id=i;properties[i].toolType=MotionEvent.TOOL_TYPE_FINGER;coordinates[i]=new MotionEvent.PointerCoords();coordinates[i].x=origin[0]+x+(i==0?-radius:radius);coordinates[i].y=origin[1]+y;coordinates[i].pressure=1;coordinates[i].size=1;}
    MotionEvent event=MotionEvent.obtain(start,SystemClock.uptimeMillis(),action,count,properties,coordinates,0,0,1,1,0,0,InputDevice.SOURCE_TOUCHSCREEN,0);
    event.offsetLocation(-origin[0],-origin[1]);
    target.getPanZoomController().onTouchEvent(event);event.recycle();
  }
  @Override protected void onFocusChanged(boolean gain,int direction,Rect previous){super.onFocusChanged(gain,direction,previous);if(enabled&&gain&&surface!=null)surface.requestFocus();}
  @Override public boolean onInterceptTouchEvent(MotionEvent event){return !enabled&&super.onInterceptTouchEvent(event);}
  @Override protected void onMeasure(int width,int height){super.onMeasure(width,height);float layout=hasExitIpPage()?1:readingLayout;int inset=hasExitIpPage()?exitIpTopInset:0;if(surface!=null)surface.measure(MeasureSpec.makeMeasureSpec(Math.round(getMeasuredWidth()/layout),MeasureSpec.EXACTLY),MeasureSpec.makeMeasureSpec(Math.round(Math.max(0,getMeasuredHeight()-inset)/layout),MeasureSpec.EXACTLY));}
  private void syncSurfaceOrigin(){
    if(surface==null||!surface.isAttachedToWindow())return;WindowInsets window=surface.getRootWindowInsets();if(window==null)return;
    if(nativePerfEnabled)surfaceOriginChecks++;
    // The SDK's manual gather updates both origin and safe-area native state.
    // It does not deduplicate safe-area values, so doing it for every MOVE used
    // to add a compositor call to every scroll sample. Use the same actual
    // Surface/Texture child as the SDK and retain immediate geometry updates.
    View child=surface.getChildCount()>0?surface.getChildAt(0):surface;child.getLocationOnScreen(surfaceOrigin);
    int top=0,right=0,bottom=0,left=0;
    if(Build.VERSION.SDK_INT>=30){android.graphics.Insets safe=window.getInsets(WindowInsets.Type.systemBars()|WindowInsets.Type.displayCutout());top=safe.top;right=safe.right;bottom=safe.bottom;left=safe.left;}
    else if(Build.VERSION.SDK_INT>=28){DisplayCutout cutout=window.getDisplayCutout();if(cutout!=null){top=cutout.getSafeInsetTop();right=cutout.getSafeInsetRight();bottom=cutout.getSafeInsetBottom();left=cutout.getSafeInsetLeft();}}
    GeckoSession attached=surface.getSession();
    if(originKnown&&originView==child&&originSession==attached&&originX==surfaceOrigin[0]&&originY==surfaceOrigin[1]&&insetTop==top&&insetRight==right&&insetBottom==bottom&&insetLeft==left)return;
    originKnown=true;originView=child;originSession=attached;originX=surfaceOrigin[0];originY=surfaceOrigin[1];insetTop=top;insetRight=right;insetBottom=bottom;insetLeft=left;
    if(nativePerfEnabled)surfaceOriginSyncs++;surface.gatherTransparentRegion(null);
  }
  @Override protected void onAttachedToWindow(){originKnown=false;super.onAttachedToWindow();}
  @Override protected void onDetachedFromWindow(){originKnown=false;super.onDetachedFromWindow();}
  @Override protected void onLayout(boolean changed,int l,int t,int r,int b){super.onLayout(changed,l,t,r,b);if(surface!=null){int inset=hasExitIpPage()?exitIpTopInset:0;surface.layout(0,inset,surface.getMeasuredWidth(),inset+surface.getMeasuredHeight());syncSurfaceOrigin();}}
}
