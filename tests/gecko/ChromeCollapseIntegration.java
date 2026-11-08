package local.pocketchat;

import android.content.*;
import android.os.*;
import android.view.*;
import org.json.*;
import org.mozilla.geckoview.*;

/** Test-only observation of the real chrome and SDK. All gestures come from adb input. */
final class ChromeCollapseIntegration {
  static final String ACTION="local.pocketchat.test.CHROME_COLLAPSE";
  static final String TARGET=MainActivity.ORIGIN+"c/reload-collapse";
  static final String TELEMETRY="JSON.parse(document.documentElement.dataset.chromeInputEvidence||'null')";
  static final String TELEMETRY_READY="t?.schema===1&&t.realm==='page-main-world'&&t.document===document.documentElement.dataset.reloadDocument&&Array.isArray(t.events)&&t.listenerTypes?.includes('touchend')";
  final CompactChromeIntegrationActivity a;
  final String nonce;
  final IntegrationEventStore events;
  String task="";
  int documents;
  int activityStarts,menuOpens;
  int diagnosticSequence,diagnosticTicks,readyEvaluations,readyCallbacks,snapshotEvaluations,snapshotCallbacks,inputReadinessSequence;
  boolean diagnosticReady;
  final Runnable diagnosticTick=new Runnable(){public void run(){
    if(diagnosticReady||diagnosticTicks>=32)return;
    diagnosticTicks++;diagnostic("waiting");a.handler.postDelayed(this,1000);
  }};
  // Synthetic fixture only. These values are direct memory observations, never
  // readiness authority, extra route calls, database reads, or SDK commands.
  void diagnostic(String stage){
    if(diagnosticReady||diagnosticSequence>=80)return;
    CollapseView w=web();
    android.util.Log.i("PocketCollapseTrace",J.obj("schema",1,"sequence",++diagnosticSequence,"runNonce",nonce,
      "sourceCommit",events.buildIdentity.optString("sourceCommit"),"sourceTree",events.buildIdentity.optString("sourceTree"),
      "stage",stage,"elapsedMs",SystemClock.elapsedRealtime(),"diagnosticOnly",true,
      "checkpointReady",w.checkpointReady,"runtimePresent",w.runtime!=null,"extensionPresent",w.extension!=null,
      "identityPrepared",w.identityPrepared,"routePrepared",w.routePrepared,"privacyReady",w.privacyReady,
      "ready",w.ready,"failed",w.failed,"destroyed",w.destroyed,"resourceDeferred",w.resourceDeferred,
      "sessionPresent",w.current!=null,"surfacePresent",w.surface!=null,"portPresent",w.ports.get(w.current)!=null,
      "usable",w.usable.contains(w.current),"queuedTarget",(CompactChromeIntegrationActivity.ReloadView.LOCAL+"c/reload-collapse").equals(w.queued),
      "routePortPresent",w.routePort!=null,"guardBlocked",a.session.guard.blocked,"networkReady",a.session.networkReady,
      "browserPaused",a.session.browserPaused,"uiVisible",a.session.uiVisible,"navigating",a.session.navigating,
      "requestedProtection",w.requestedProtection,"protectionRequest",w.protectionRequest,"protectionLevel",w.protectionLevel,
      "documents",documents,"readyEvaluations",readyEvaluations,"readyCallbacks",readyCallbacks,
      "snapshotEvaluations",snapshotEvaluations,"snapshotCallbacks",snapshotCallbacks,"eventSequence",events.sequence,
      "routeCalls",w.routeCalls,"fixtureRoutes",w.fixtureRoutes,"blockedRoutes",w.blockedRoutes,"otherRoutes",w.otherRoutes).toString());
  }
  JSONArray nativeTouches=new JSONArray();
  final java.util.Set<String> glassObservationCommands=new java.util.HashSet<>();
  final BroadcastReceiver receiver=new BroadcastReceiver(){@Override public void onReceive(Context c,Intent intent){
    if(!nonce.equals(intent.getStringExtra("eventNonce")))return;
    String glassCommand=intent.getStringExtra("glassObserveCommand");
    if(glassCommand!=null){
      if(glassCommand.matches("[a-zA-Z0-9_-]{1,80}")&&glassObservationCommands.size()<64&&glassObservationCommands.add(glassCommand))observeGlassOwners(glassCommand);
      return;
    }
    String readiness=intent.getStringExtra("collapseReadiness");
    if(readiness!=null){if(readiness.matches(nonce+"-[1-9][0-9]{0,2}"))inputReadiness(readiness);return;}
    String command=intent.getStringExtra("collapseCommand");
    if(command==null||!command.matches("[a-zA-Z0-9_-]{1,80}"))return;
    if("clear".equals(command)){web().touchesObserved=new JSONArray();nativeTouches=new JSONArray();return;}
    a.handler.postDelayed(()->snapshot(command),150);
  }};
  /** One synchronous read on the receiver's UI thread; no observer or UI mutation. */
  void observeGlassOwners(String command){
    JSONObject value=J.obj("schema",1,"command",command,"status","started",
      "sourceCommit",events.buildIdentity.optString("sourceCommit"),"sourceTree",events.buildIdentity.optString("sourceTree"),
      "apkSha256",events.buildIdentity.optString("apkSha256"),"runNonce",nonce,
      "pid",android.os.Process.myPid(),"uid",android.os.Process.myUid(),"activityRef",System.identityHashCode(a),
      "activityClass",a.getClass().getName(),"decorRef",System.identityHashCode(a.getWindow().getDecorView()),
      "active",a.active,"windowFocus",a.hasWindowFocus(),"capturedAtElapsedRealtimeNanos",SystemClock.elapsedRealtimeNanos(),
      "readOnly",true,"pausesObservers",false);
    try{
      if(!"local.pocketchat.test".equals(a.getPackageName())||a.hub==null)throw new IllegalStateException("Current test Activity glass roots unavailable");
      value.put("owners",GlassOwnerObservation.read(a.toolbar,a.hub.bar,a.hub.panel)).put("status","observed");
    }catch(Exception error){try{value.put("status","failed").put("errorClass",error.getClass().getName()).put("error",String.valueOf(error.getMessage()));}catch(Exception ignored){}}
    // Unlike snapshot(), this path does not pause session observers or evaluate
    // a browser script. The original process-frame threshold remains decisive.
    try{events.emit("glassOwnerObservation",value);}catch(Exception error){events.failure(error);}
  }

  /** Reads only current native roots, including hidden descendants and coating layers. */
  static final class GlassOwnerObservation {
    static JSONObject read(View toolbar,View bar,GlassBackdrop panel)throws Exception{
      if(toolbar==null||bar==null||panel==null)throw new IllegalStateException("Missing current native glass root");
      JSONArray roots=new JSONArray(),materials=new JSONArray(),docks=new JSONArray();
      roots.put(host(toolbar)).put(host(bar));
      java.util.Set<View> seen=java.util.Collections.newSetFromMap(new java.util.IdentityHashMap<>());
      walk(toolbar,materials,docks,seen);walk(bar,materials,docks,seen);
      JSONObject backdrop=J.obj("host",host(panel),"configuredActive",field(panel,GlassBackdrop.class,"glassActive"),"isGlassActive",panel.isGlassActive());
      return J.obj("roots",roots,"materials",materials,"docks",docks,"backdrop",backdrop);
    }
    static JSONObject host(View view){
      return J.obj("viewClass",view.getClass().getName(),"viewIdentity",System.identityHashCode(view),
        "rootIdentity",System.identityHashCode(view.getRootView()),"attached",view.isAttachedToWindow(),
        "shown",view.isShown(),"visibility",view.getVisibility(),"windowVisibility",view.getWindowVisibility(),
        "windowFocus",view.hasWindowFocus(),"enabled",view.isEnabled(),"pressed",view.isPressed());
    }
    static Object field(Object object,Class<?> owner,String name)throws Exception{
      java.lang.reflect.Field field=owner.getDeclaredField(name);field.setAccessible(true);return field.get(object);
    }
    static JSONObject animation(Object value)throws Exception{
      if(value==null)return J.obj("present",false,"started",false,"running",false);
      if(!(value instanceof android.animation.ValueAnimator))throw new IllegalStateException("Unexpected native animator field type");
      android.animation.ValueAnimator animator=(android.animation.ValueAnimator)value;
      return J.obj("present",true,"started",animator.isStarted(),"running",animator.isRunning(),
        "durationMillis",animator.getDuration(),"currentPlayTimeMillis",animator.getCurrentPlayTime());
    }
    static void walk(View view,JSONArray materials,JSONArray docks,java.util.Set<View> seen)throws Exception{
      if(!seen.add(view))return;
      java.util.Set<android.graphics.drawable.Drawable> layers=java.util.Collections.newSetFromMap(new java.util.IdentityHashMap<>());
      drawable(view.getBackground(),view,materials,layers);
      if(view instanceof GlassDock)docks.put(J.obj("host",host(view),
        "transition",animation(field(view,GlassDock.class,"transition")),
        "opacity",field(view,GlassDock.class,"opacity"),"flow",field(view,GlassDock.class,"flow")));
      if(view instanceof ViewGroup){ViewGroup group=(ViewGroup)view;for(int i=0;i<group.getChildCount();i++)walk(group.getChildAt(i),materials,docks,seen);}
    }
    static void drawable(android.graphics.drawable.Drawable drawable,View view,JSONArray materials,java.util.Set<android.graphics.drawable.Drawable> seen)throws Exception{
      if(drawable==null||!seen.add(drawable))return;
      if(drawable instanceof LiquidGlassDrawable){
        JSONArray states=new JSONArray();for(int state:drawable.getState())states.put(state);
        materials.put(J.obj("host",host(view),"drawableIdentity",System.identityHashCode(drawable),
          "drawableVisible",drawable.isVisible(),"drawableAlpha",drawable.getAlpha(),"drawableState",states,
          "animation",animation(field(drawable,LiquidGlassDrawable.class,"animation")),
          "pressed",field(drawable,LiquidGlassDrawable.class,"pressed"),
          "strength",field(drawable,LiquidGlassDrawable.class,"strength"),"bend",field(drawable,LiquidGlassDrawable.class,"bend")));
      }else if(drawable instanceof android.graphics.drawable.LayerDrawable){
        android.graphics.drawable.LayerDrawable layers=(android.graphics.drawable.LayerDrawable)drawable;
        for(int i=0;i<layers.getNumberOfLayers();i++)drawable(layers.getDrawable(i),view,materials,seen);
      }else if(drawable instanceof android.graphics.drawable.InsetDrawable){
        drawable(((android.graphics.drawable.InsetDrawable)drawable).getDrawable(),view,materials,seen);
      }
    }
  }

  void inputReadiness(String request){
    if(!"local.pocketchat.test".equals(a.getPackageName())||!request.matches(nonce+"-[1-9][0-9]{0,2}")||inputReadinessSequence>=128)return;
    CollapseView w=web();View compact=a.designChrome.compact;android.graphics.Rect visible=new android.graphics.Rect();
    boolean globallyVisible=compact.getGlobalVisibleRect(visible);int[] rootLocation=new int[2];compact.getRootView().getLocationOnScreen(rootLocation);visible.offset(rootLocation[0],rootLocation[1]);JSONObject pending=a.session.pending;
    String url=w.getUrl(),document=w.inputDocument(nonce,events.buildIdentity.optString("sourceCommit"));InputDocumentBinding binding=w.inputBinding;
    JSONObject value=J.obj("schema",1,"kind","nativeInputReadiness","diagnosticOnly",true,"releaseAcceptance",false,
      "sourceCommit",events.buildIdentity.optString("sourceCommit"),"sourceTree",events.buildIdentity.optString("sourceTree"),"apkSha256",events.buildIdentity.optString("apkSha256"),
      "runNonce",nonce,"request",request,"fixtureAction","chromeCollapse","sequence",++inputReadinessSequence,"observedAtElapsedRealtime",SystemClock.elapsedRealtime(),
      "pid",android.os.Process.myPid(),"uid",android.os.Process.myUid(),"activityRef",System.identityHashCode(a),
      "surface",System.identityHashCode(w),"sdkSession",System.identityHashCode(w.current),"attachedSession",System.identityHashCode(w.surface==null?null:w.surface.getSession()),
      "appearanceDocument",document,"documentBinding","fixture-admitted-current-port","documentPort",System.identityHashCode(binding==null?null:binding.port),"currentPort",System.identityHashCode(w.ports.get(w.current)),
      "url",TARGET.equals(url)?url:"<outside-fixture>","visibleDocument",w.hasVisibleDocument(),
      "pendingId",pending==null?"":pending.optString("id"),"pendingConfirmed",pending!=null&&pending.optBoolean("confirmed"),
      "windowFocus",a.hasWindowFocus(),"decorFocus",a.getWindow().getDecorView().hasWindowFocus(),"attached",compact.isAttachedToWindow(),
      "shown",compact.isShown(),"enabled",compact.isEnabled(),"clickable",compact.isClickable(),"laidOut",compact.isLaidOut(),"layoutRequested",compact.isLayoutRequested(),
      "globallyVisible",globallyVisible,"expanded",a.designChrome.expanded(),"toolbarVisibility",a.toolbar.getVisibility(),"compactVisibility",compact.getVisibility(),
      "page",a.hub.page,"activityStarts",activityStarts,"menuOpens",menuOpens,"nativeTouchCount",nativeTouches.length(),
      "hostBounds",a.bounds(a.getWindow().getDecorView()),"toolbarBounds",a.bounds(a.toolbar),"compactBounds",a.bounds(compact),"visibleBounds",a.rect(visible),
      "webBounds",a.bounds(w),"point",a.center(compact));
    String raw=value.toString();if(raw.getBytes(java.nio.charset.StandardCharsets.UTF_8).length>3500)throw new IllegalStateException("Bounded native input readiness required");
    android.util.Log.i("PocketChromeInputReady",raw);
  }
  /** The loopback fixture uses its admitted message, not production appearance cache. */
  static final class InputDocumentBinding {
    final Object port,sdk;final int sdkId;final String nonce,source,document;final JSONObject evidence;
    InputDocumentBinding(Object port,Object sdk,int sdkId,String nonce,String source,String document,JSONObject evidence){this.port=port;this.sdk=sdk;this.sdkId=sdkId;this.nonce=nonce;this.source=source;this.document=document;this.evidence=evidence;}
    static boolean number(Object value,int expected){return value instanceof Number&&((Number)value).doubleValue()==expected;}
    static String document(JSONObject evidence,int sdkId,String actual,String visible,Object sender,Object sdk,boolean topLevel,boolean contentScript,boolean loadCurrent){
      String local="http://127.0.0.1:8765/c/reload-collapse";
      if(evidence==null||sdk==null||sdkId<=0||sender!=sdk||!topLevel||!contentScript||!loadCurrent||!local.equals(actual)||!TARGET.equals(visible)
          ||!Boolean.TRUE.equals(evidence.opt("acceptedByProduction"))||!Boolean.TRUE.equals(evidence.opt("topLevel"))||!Boolean.TRUE.equals(evidence.opt("contentScript"))
          ||!number(evidence.opt("nativeSession"),sdkId)||!number(evidence.opt("currentSession"),sdkId)
          ||!local.equals(evidence.optString("senderUrl"))||!local.equals(evidence.optString("actualUrl"))||!TARGET.equals(evidence.optString("visibleUrl")))return "";
      JSONObject raw=evidence.optJSONObject("rawMessage"),normalized=evidence.optJSONObject("normalizedMessage");
      if(raw==null||normalized==null||!"documentReady".equals(raw.optString("kind"))||!local.equals(raw.optString("url"))||!number(raw.opt("appearanceProtocol"),1)
          ||!"documentReady".equals(normalized.optString("kind"))||!TARGET.equals(normalized.optString("url")))return "";
      String document=raw.optString("appearanceDocument");return document.matches("[a-zA-Z0-9-]{16,80}")&&document.equals(normalized.optString("appearanceDocument"))?document:"";
    }
    static InputDocumentBinding admit(Object incoming,Object currentPort,Object sdk,int sdkId,String nonce,String source,JSONObject evidence,String actual,String visible,Object sender,boolean topLevel,boolean contentScript,boolean loadCurrent){
      if(incoming==null||incoming!=currentPort||nonce==null||!nonce.matches("[0-9a-f]{32}")||source==null||!source.matches("[0-9a-f]{40}"))return null;
      String document=document(evidence,sdkId,actual,visible,sender,sdk,topLevel,contentScript,loadCurrent);
      return document.isEmpty()?null:new InputDocumentBinding(incoming,sdk,sdkId,nonce,source,document,evidence);
    }
    String current(Object currentPort,Object currentSdk,int currentSdkId,String currentNonce,String currentSource,JSONObject currentEvidence,String actual,String visible,Object sender,boolean topLevel,boolean contentScript,boolean loadCurrent){
      if(port!=currentPort||sdk!=currentSdk||sdkId!=currentSdkId||evidence!=currentEvidence||!nonce.equals(currentNonce)||!source.equals(currentSource))return "";
      String current=document(currentEvidence,currentSdkId,actual,visible,sender,currentSdk,topLevel,contentScript,loadCurrent);return document.equals(current)?current:"";
    }
  }
  ChromeCollapseIntegration(CompactChromeIntegrationActivity activity,String runNonce){
    a=activity;nonce=runNonce;
    try{events=new IntegrationEventStore(a,Profiles.slot(a),nonce,"chromeCollapse",1,IntegrationBuildIdentity.read(Profiles.global(a)));}
    catch(Exception failure){throw new IllegalStateException("Owned collapse evidence required",failure);}
  }
  static final class CollapseView extends CompactChromeIntegrationActivity.ReloadView {
    JSONArray touchesObserved=new JSONArray();
    JSONObject documentReadyEvidence=new JSONObject();
    InputDocumentBinding inputBinding;
    String inputDocument(String nonce,String source){
      WebExtension.Port port=ports.get(current);if(inputBinding==null||port==null)return "";
      return inputBinding.current(port,current,System.identityHashCode(current),nonce,source,documentReadyEvidence,rawUrl(),getUrl(),port.sender.session,
        port.sender.isTopLevel(),port.sender.environmentType==WebExtension.MessageSender.ENV_TYPE_CONTENT_SCRIPT,
        !staleAppearanceConnections.contains(port)&&java.util.Objects.equals(appearanceConnections.get(port),appearanceLoads.getOrDefault(current,0L)));
    }
    ChromeCollapseIntegration diagnostic;
    int routeCalls,fixtureRoutes,blockedRoutes,otherRoutes;
    @Override JSONObject route(String target){
      JSONObject result=super.route(target);routeCalls++;
      if("socks".equals(result.optString("type"))&&"127.0.0.1".equals(result.optString("host"))&&result.optInt("port")==1080)fixtureRoutes++;
      else if("socks".equals(result.optString("type"))&&"127.0.0.1".equals(result.optString("host"))&&result.optInt("port")==9)blockedRoutes++;
      else otherRoutes++;
      if(diagnostic!=null&&routeCalls<=8)diagnostic.diagnostic("route-return");return result;
    }
    CollapseView(Context context,ChatSession owner){super(context,owner);}
    @Override GeckoSession newSession(){
      GeckoSession sdk=super.newSession();
      sdk.getWebExtensionController().setMessageDelegate(extension,new WebExtension.MessageDelegate(){
        @Override public void onConnect(WebExtension.Port port){
          pageMessages.onConnect(port);
          final WebExtension.PortDelegate original;
          try{java.lang.reflect.Field field=WebExtension.Port.class.getDeclaredField("delegate");field.setAccessible(true);Object value=field.get(port);if(!(value instanceof WebExtension.PortDelegate))return;original=(WebExtension.PortDelegate)value;}
          catch(ReflectiveOperationException failure){throw new IllegalStateException("Pinned SDK test delegate unavailable",failure);}
          port.setDelegate(new WebExtension.PortDelegate(){
            @Override public void onPortMessage(Object message,WebExtension.Port incoming){
              Object forwarded=message;boolean mapped=false;
              if(message instanceof JSONObject){JSONObject data=(JSONObject)message;
                mapped=ChromeCollapseDocumentReadyAdapter.maps(data.optString("kind"),data.optString("url"),rawUrl(),port.sender.url,getUrl(),incoming==port&&port.sender.session==sdk&&sdk==current,port.sender.isTopLevel(),port.sender.environmentType==WebExtension.MessageSender.ENV_TYPE_CONTENT_SCRIPT);
                if(mapped)try{
                  JSONObject normalized=new JSONObject(data.toString());normalized.put("url",ChromeCollapseDocumentReadyAdapter.VIRTUAL);forwarded=normalized;
                  documentReadyEvidence=J.obj("rawMessage",new JSONObject(data.toString()),"senderUrl",port.sender.url,"actualUrl",rawUrl(),"visibleUrl",getUrl(),"nativeSession",System.identityHashCode(port.sender.session),"currentSession",System.identityHashCode(current),"topLevel",port.sender.isTopLevel(),"contentScript",true,"normalizedMessage",new JSONObject(normalized.toString()));
                }catch(JSONException failure){throw new IllegalStateException(failure);}
              }
              // The original production delegate alone may mark the real SDK usable.
              if(mapped&&diagnostic!=null)diagnostic.diagnostic("document-ready-before");
              original.onPortMessage(forwarded,incoming);
              if(mapped)try{documentReadyEvidence.put("acceptedByProduction",hasVisibleDocument());
                if(diagnostic!=null)inputBinding=InputDocumentBinding.admit(incoming,ports.get(current),current,System.identityHashCode(current),diagnostic.nonce,
                  diagnostic.events.buildIdentity.optString("sourceCommit"),documentReadyEvidence,rawUrl(),getUrl(),port.sender.session,
                  port.sender.isTopLevel(),port.sender.environmentType==WebExtension.MessageSender.ENV_TYPE_CONTENT_SCRIPT,
                  !staleAppearanceConnections.contains(incoming)&&java.util.Objects.equals(appearanceConnections.get(incoming),appearanceLoads.getOrDefault(current,0L)));
              }catch(JSONException failure){throw new IllegalStateException(failure);}
              if(mapped&&diagnostic!=null)diagnostic.diagnostic("document-ready-after");
            }
            @Override public void onDisconnect(WebExtension.Port incoming){original.onDisconnect(incoming);}
          });
        }
      },"pocketpage");
      return sdk;
    }
    @Override public boolean dispatchTouchEvent(MotionEvent event){
      boolean handled=super.dispatchTouchEvent(event);
      Context host=displayContext.getBaseContext();
      if(tracking&&host instanceof MainActivity&&touchesObserved.length()<256){MainActivity activity=(MainActivity)host;
        touchesObserved.put(J.obj("action",event.getActionMasked(),"pointers",event.getPointerCount(),"eventTime",event.getEventTime(),"x",event.getX(),"y",event.getY(),"height",getHeight(),"width",getWidth(),"expanded",activity.designChrome.expanded(),"toolbarVisibility",activity.toolbar.getVisibility()));}
      return handled;
    }
  }
  CollapseView web(){return (CollapseView)a.remote;}
  void pauseObservers(){a.handler.removeCallbacks(a.ticker);a.session.remove(a.sessionObserver);a.session.handler.removeCallbacks(a.session.tick);}
  Object visibleCenter(View view){return view!=null&&view.isShown()&&view.getWidth()>0&&view.getHeight()>0?a.center(view):JSONObject.NULL;}
  void start(){
    // Keep the historical v1 evidence/runner intact. Its fixed six-tap path
    // cannot exercise the URL dialog and four-action dock without a new contract.
    if(a.getIntent().getIntExtra("chromeNavigationVersion",1)!=2){
      emit("error",J.obj("navigationContract",2,"error","Chrome navigation contract v2 required: the v1 collapse runner targets removed Chat/Settings tabs and assumes capsule taps only expand. Version the address-dialog/menu/back workload before running this fixture."));return;
    }
    web().diagnostic=this;diagnostic("start-before");a.handler.postDelayed(diagnosticTick,1000);
    pauseObservers();
    if(Build.VERSION.SDK_INT>=33)a.registerReceiver(receiver,new IntentFilter(ACTION),Context.RECEIVER_EXPORTED);else a.registerReceiver(receiver,new IntentFilter(ACTION));
    a.session.prefs.edit().putBoolean("networkConfigured",true).putString("proxy","socks://127.0.0.1:1080").putBoolean("requireExternalVpn",false).commit();
    a.session.networkReady=true;a.session.offline=false;a.session.guard.setBlocked(false);
    android.webkit.WebViewClient original=a.remote.client;
    a.remote.setWebViewClient(new android.webkit.WebViewClient(){@Override public void onPageFinished(android.webkit.WebView view,String url){
      diagnostic("page-finished-before");if(original!=null)original.onPageFinished(view,url);diagnostic("page-finished-after");
      if(url.equals(CompactChromeIntegrationActivity.ReloadView.LOCAL+"c/reload-collapse")){
        documents++;a.session.navigating=false;a.session.navigationFailed=false;pauseObservers();ready(SystemClock.elapsedRealtime()+15000);
      }
    }});
    diagnostic("load-before");a.remote.loadUrl(CompactChromeIntegrationActivity.ReloadView.LOCAL+"c/reload-collapse");diagnostic("load-return");
  }
  void ready(long deadline){
    readyEvaluations++;if(readyEvaluations==1)diagnostic("ready-evaluate");
    a.remote.evaluateJavascript("(()=>{const t="+TELEMETRY+";return {ready:!!document.getElementById('prompt-textarea')&&!!document.documentElement.dataset.reloadDocument,telemetryReady:"+TELEMETRY_READY+"};})()",raw->{
      readyCallbacks++;if(readyCallbacks==1)diagnostic("ready-callback");
      if(!J.parse(raw).optBoolean("ready")||!J.parse(raw).optBoolean("telemetryReady")||!a.remote.hasVisibleDocument()){if(SystemClock.elapsedRealtime()>deadline){emit("error",J.obj("error","Controlled chrome document or shared-DOM telemetry timeout"));return;}a.handler.postDelayed(()->ready(deadline),100);return;}
      task=a.session.deliveries.begin(TARGET,"already sent fixture question",new JSONArray(),"web",null);
      // This owned task measures retention, not the independent reply worker.
      a.session.pending=J.obj("id",task,"kind","web","engine","gecko","confirmed",true,"webSuspended",true,"userKey","id:reload-user","prompt","already sent fixture question","confirmedUrl",TARGET,"expectedUrl",TARGET);
      a.session.conversation=TARGET;a.session.prefs.edit().putString("pending",a.session.pending.toString()).putString("conversation",TARGET).commit();
      // Only the actual usable SDK document dismisses the production loading cover.
      a.session.manualAttention=false;a.loading.update();web().tracking=true;a.handler.postDelayed(()->snapshot("ready"),300);
    });
  }
  static final String READING_VIEWPORT="(()=>{const m=document.querySelector('main'),c=document.getElementById('composer'),v=window.visualViewport;const box=n=>{if(!n)return null;const r=n.getBoundingClientRect();return [r.left,r.top,r.right,r.bottom];};return {schema:1,coordinateSpace:'layout-viewport-css',document:document.documentElement.dataset.reloadDocument,layoutWidth:innerWidth,layoutHeight:innerHeight,visualBounds:v?[v.offsetLeft,v.offsetTop,v.offsetLeft+v.width,v.offsetTop+v.height]:null,mainBounds:box(m),composerBounds:box(c),composerTag:c?.tagName||'',composerId:c?.id||''};})()";
  void snapshot(String command){
    snapshotEvaluations++;diagnostic("snapshot-evaluate");pauseObservers();
    a.remote.evaluateJavascript("(()=>{const t="+TELEMETRY+";return {draft:document.getElementById('prompt-textarea').value,cookie:document.cookie,sendCount:Number(document.getElementById('send-count').textContent),path:location.pathname,document:document.documentElement.dataset.reloadDocument,scrollY:scrollY,innerWidth:innerWidth,innerHeight:innerHeight,readingViewport:"+READING_VIEWPORT+",trusted:t?.events||[],fixtureInputTelemetry:t,telemetryReady:"+TELEMETRY_READY+"};})()",raw->{
      snapshotCallbacks++;diagnostic("snapshot-callback");JSONObject result=J.parse(raw);int[] location=new int[2];a.remote.getLocationOnScreen(location);
      try{result.put("command",command).put("navigationContract",2).put("expanded",a.designChrome.expanded()).put("toolbarVisibility",a.toolbar.getVisibility()).put("toolbarHeight",a.toolbar.getHeight())
        .put("compactVisibility",a.designChrome.compact.getVisibility()).put("compactHeight",a.designChrome.compact.getHeight())
        .put("compactName",a.designChrome.compactTitle.getText().toString()).put("environmentName",Profiles.display(a,Profiles.slot(a)))
        .put("compactTap",visibleCenter(a.designChrome.compact)).put("topVisibility",a.designChrome.top.getVisibility()).put("networkVisibility",a.designChrome.networkRow.getVisibility())
        .put("webWidth",a.remote.getWidth()).put("webHeight",a.remote.getHeight()).put("webX",location[0]).put("webY",location[1])
        .put("surface",System.identityHashCode(a.remote)).put("sdkSession",System.identityHashCode(a.remote.current)).put("attachedSession",System.identityHashCode(a.remote.surface.getSession()))
        .put("loads",web().loads).put("stops",web().stops).put("documents",documents).put("page",a.hub.page).put("keyboard",a.keyboardVisible)
        .put("visibleDocument",a.remote.hasVisibleDocument()).put("loadingCoverVisibility",a.loading.cover.getVisibility())
        .put("documentReadyEvidence",web().documentReadyEvidence)
        .put("pending",a.session.pending==null?JSONObject.NULL:new JSONObject(a.session.pending.toString())).put("pendingStored",a.session.prefs.getString("pending",""))
        .put("activityStarts",activityStarts).put("menuOpens",menuOpens).put("windowFocus",a.hasWindowFocus())
        .put("touches",web().touchesObserved).put("nativeTouches",nativeTouches).put("toolbarBounds",a.bounds(a.toolbar))
        .put("environmentTap",visibleCenter(a.hub.tabs[WorkspaceNavigation.ENVIRONMENTS])).put("networkTap",visibleCenter(a.hub.tabs[WorkspaceNavigation.NETWORK]))
        .put("downloadsTap",visibleCenter(a.hub.tabs[WorkspaceNavigation.DOWNLOADS])).put("readingTap",visibleCenter(a.hub.tabs[WorkspaceNavigation.READING]))
        .put("addressTap",visibleCenter(a.designChrome.title)).put("moreTap",visibleCenter(a.designChrome.more))
        .put("androidSdk",Build.VERSION.SDK_INT).put("activityClass",a.getClass().getName()).put("activityRef",System.identityHashCode(a))
        .put("pid",android.os.Process.myPid()).put("uid",android.os.Process.myUid())
        .put("nativeFontScale",a.getResources().getConfiguration().fontScale).put("nativeScreenWidthDp",a.getResources().getConfiguration().screenWidthDp)
        .put("nativeDensityDpi",a.getResources().getDisplayMetrics().densityDpi).put("nativeDisplayWidth",a.getResources().getDisplayMetrics().widthPixels)
        .put("readingRequested",a.focusReading).put("readingActive",a.focusActive()).put("navigationVisibility",a.hub.bar.getVisibility())
        .put("exitVisibility",a.focusExit.getVisibility()).put("exitTap",visibleCenter(a.focusExit)).put("addressDialog",addressDialog());
        if(a.designChrome.expanded()){
          java.lang.reflect.Method method=DesignChrome.class.getDeclaredMethod("touchBounds",View.class);method.setAccessible(true);
          android.graphics.Rect target=(android.graphics.Rect)method.invoke(a.designChrome,a.designChrome.title);int[] origin=new int[2];a.toolbar.getLocationOnScreen(origin);target.offset(origin[0],origin[1]);
          result.put("headerSwipeFrom",J.arr(target.centerX(),target.bottom-2)).put("headerSwipeTo",J.arr(target.centerX(),origin[1]+a.dp(1))).put("headerButtonTouch",a.rect(target));
        }
        emit("collapseSnapshot",result);if("ready".equals(command)){diagnosticReady=true;a.handler.removeCallbacks(diagnosticTick);}
      }catch(Exception failure){emit("error",J.obj("error",failure.toString()));}
    });
  }
  /** Test-only reads of the production dialog; never opens, dismisses or edits it. */
  JSONObject addressDialog()throws Exception{
    java.lang.reflect.Field field=GeckoAddressUi.class.getDeclaredField("dialog");field.setAccessible(true);
    android.app.AlertDialog dialog=(android.app.AlertDialog)field.get(a.geckoAddress);
    if(dialog==null||!dialog.isShowing())return J.obj("visible",false);
    java.lang.reflect.Field editor=GeckoAddressUi.class.getDeclaredField("editor");editor.setAccessible(true);
    android.widget.EditText input=(android.widget.EditText)editor.get(a.geckoAddress);
    android.widget.Button cancel=dialog.getButton(android.app.AlertDialog.BUTTON_NEGATIVE);
    return J.obj("visible",true,"windowFocus",dialog.getWindow().getDecorView().hasWindowFocus(),
      "editorText",input.getText().toString(),"editorFocused",input.hasFocus(),"editorTap",visibleCenter(input),
      "cancelTap",visibleCenter(cancel),"cancelBounds",a.bounds(cancel),"cancelText",cancel.getText().toString());
  }
  void emit(String kind,JSONObject result){diagnostic("emit-before");try{events.emit(kind,result);diagnostic("emit-queued");}catch(Exception failure){events.failure(failure);}}
  void nativeTouch(MotionEvent event){if(web().tracking&&nativeTouches.length()<256)nativeTouches.put(J.obj("action",event.getActionMasked(),"pointers",event.getPointerCount(),"height",a.remote.getHeight(),"expanded",a.designChrome.expanded()));}
  void close(){a.handler.removeCallbacks(diagnosticTick);try{a.unregisterReceiver(receiver);}catch(IllegalArgumentException ignored){}}
}
