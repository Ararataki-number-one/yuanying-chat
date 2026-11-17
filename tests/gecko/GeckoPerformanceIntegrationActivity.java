package local.pocketchat;

import android.app.Activity;
import android.content.Context;
import android.os.*;
import android.util.Log;
import android.view.Choreographer;
import android.view.WindowInsets;
import android.view.inputmethod.InputMethodManager;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.LinearLayout;
import android.widget.TextView;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import org.mozilla.geckoview.*;
import org.json.*;

/** Integration-only comparison: actual Gecko document and native extension bridge, no account. */
public final class GeckoPerformanceIntegrationActivity extends Activity {
  static final String ORIGIN="http://127.0.0.1:8767",PATH="/performance";
  static final String BASELINE="835d59991218eda70c7a4fdd73ea9d7ae6052688",INPUT_MARKER="-user-typed";
  final Handler handler=new Handler(Looper.getMainLooper());
  final FrameSample frames=new FrameSample();
  ChatSession session;String variant,driver,performanceSource;JSONObject before,known,firstFull,baselineMetrics,currentMetrics;
  int checkCount,samples,inputFocusSamples;boolean finished,inputRequested;long deadline,payloadBytes,payloadChars,callbackMs,scriptChars;
  String originalDriver,manualDraft,manualRoute,inputDraft;long manualEpoch,manualConnection;int manualLoads,manualStops;
  String inputReadinessKey="";long inputReadySince;int inputTraceOffset,inputReadinessSequence;boolean inputImeSettled;
  GeckoInputTrace nativeInputTrace;GeckoInputTrace.Buffered bufferedInputTrace;boolean inputDiagnostics,inputNativeDiagnostics;
  final JSONArray scrollDiagnosticPhases=new JSONArray();ScrollPhase scrollPhase,scrollDomTail;String scrollDiagnosticRun;
  static final class ScrollPhase {
    final String variant,url;final long navigationEpoch,started=SystemClock.elapsedRealtime();final GeckoSession sdk;final android.view.View surface;
    final GeckoSession.CompositorScrollDelegate prior;final JSONArray samples=new JSONArray(),nativeUpdates=new JSONArray(),domEvents=new JSONArray(),domObservation=new JSONArray();
    String run="";long expiresElapsedMs;
    int updates,sampleCount,touchPublished;float scrollX,scrollY,zoom;double beforeScrollTop;boolean hasBefore;
    ScrollPhase(String value,ChatSession owner){variant=value;url=owner.web.getUrl();navigationEpoch=owner.navigationEpoch;sdk=owner.web.current;surface=owner.web.surface;prior=sdk.getCompositorScrollDelegate();}
  }
  CountDownLatch archiveEntered,archiveRelease;
  @Override protected void attachBaseContext(Context c){super.attachBaseContext(new ProfileContext(c,Profiles.processSlot()));}
  static final class FixtureView extends GeckoWebView {
    boolean semanticRoute,inputTracing,quietTracking,holdNextInspection;JSONObject productionInspect;android.webkit.ValueCallback<String> heldInspection;String heldInspectionRaw;int pageStateReads,inputEvaluateSequence,quietStops,quietLoads;String pageStateDraft="",navigationError="",semanticUrl=MainActivity.ORIGIN+"c/performance-fixture";
    // Scalar observations exist only while the two manual-recovery races run.
    boolean manualSnapshotDiagnostics;JSONObject manualSnapshotLast=new JSONObject();
    FixtureView(Context c,ChatSession owner){super(c,owner);}
    boolean scrollTracing;int scrollTouchCount;JSONArray scrollTouches=new JSONArray();
    @Override public boolean dispatchTouchEvent(android.view.MotionEvent motion){
      boolean trace=scrollTracing;boolean handled=super.dispatchTouchEvent(motion);
      if(trace){scrollTouchCount++;if(scrollTouches.length()<64)scrollTouches.put(J.obj("sequence",scrollTouchCount,"action",motion.getActionMasked(),"pointers",motion.getPointerCount(),"eventTime",motion.getEventTime(),"downTime",motion.getDownTime(),"uptimeMs",SystemClock.uptimeMillis(),"x",motion.getX(),"y",motion.getY(),"rawX",motion.getRawX(),"rawY",motion.getRawY(),"source",motion.getSource(),"superHandled",handled));}
      return handled;
    }
    @Override public void stopLoading(){if(quietTracking)quietStops++;super.stopLoading();}
    @Override public void loadUrl(String url){if(quietTracking)quietLoads++;super.loadUrl(url);}
    @Override public String getUrl(){return semanticRoute?semanticUrl:super.getUrl();}
    @Override public void evaluateJavascript(String code,android.webkit.ValueCallback<String> callback){
      JSONObject observedManualIssue=null;
      if(manualSnapshotDiagnostics&&semanticRoute&&code.contains("window.__pocketReadDriver(\"page-state\","))try{observedManualIssue=manualSnapshotState(owner);}catch(RuntimeException ignored){}
      final JSONObject manualIssue=observedManualIssue;
      int inputSequence=inputTracing?inputEvaluateSequence++:-1;
      if(inputSequence>=0)inputEvaluation("begin",inputSequence,code);
      super.evaluateJavascript(code,raw->{
      if(inputSequence>=0)inputEvaluation("end",inputSequence,code);
      if(semanticRoute&&code.contains("window.__pocketReadDriver(\"web-inspect\","))productionInspect=J.parse(raw);
      if(semanticRoute&&code.contains("window.__pocketReadDriver(\"page-state\",")){pageStateReads++;pageStateDraft=J.parse(raw).optString("draft");}
      if(manualSnapshotDiagnostics&&semanticRoute&&code.contains("window.__pocketReadDriver(\"page-state\",")){
        try{manualSnapshotLast=J.obj("issueObserved",manualIssue!=null,"issue",manualIssue==null?JSONObject.NULL:manualIssue,"callback",manualSnapshotState(owner),"callbackStage","before-production-consumer","shape",manualSnapshotShape(J.parse(raw)));}catch(RuntimeException ignored){}
      }
      if(holdNextInspection&&code.contains("window.__pocketReadDriver(\"web-inspect\",")){holdNextInspection=false;heldInspection=callback;heldInspectionRaw=raw;return;}
      if(callback!=null)callback.onReceiveValue(raw);
    });}
    static JSONObject manualSnapshotState(ChatSession owner){
      JSONObject job=owner.pending;
      return J.obj("at",SystemClock.elapsedRealtime(),"networkReady",owner.networkReady,"guardPresent",owner.guard!=null,"guardBlocked",owner.guard!=null&&owner.guard.blocked,"guardScope","cached-blocked-field-only","websiteRecovering",owner.websiteRecovering,"navigating",owner.navigating,"epoch",owner.navigationEpoch,"connection",owner.connectionEpoch,"pendingPresent",job!=null,"pendingObject",job==null?0:System.identityHashCode(job),"pendingIdHash",Sha256.hash(job==null?"":job.optString("id")),"documentHash",Sha256.hash(owner.lastDocumentId));
    }
    static JSONObject manualSnapshotShape(JSONObject value){
      Object draft=value.opt("draft");String text=draft instanceof String?(String)draft:"";
      return J.obj("readable",value.optBoolean("ok"),"complete",PageMemory.completeDraft(value),"draftComplete",value.optBoolean("draftComplete",true),"draftString",draft instanceof String,"draftLength",text.length(),"draftHash",Sha256.hash(text),"reportedDraftLength",value.optLong("draftLength",-1),"reportedLengthNumeric",value.opt("draftLength") instanceof Number,"documentPresent",!value.optString("documentId").isEmpty(),"documentHash",Sha256.hash(value.optString("documentId")),"urlHash",Sha256.hash(value.optString("url")),"reasonHash",Sha256.hash(value.optString("reason")));
    }
    void manualSnapshotFailure(int index,String expected,long epoch,long connection){
      try{
        JSONObject value=J.obj("schema",1,"race",index,"current",manualSnapshotState(owner),"expectedEpoch",epoch,"expectedConnection",connection,"pageStateReads",pageStateReads,"expectedDraftLength",expected.length(),"expectedDraftHash",Sha256.hash(expected),"observedDraftLength",pageStateDraft.length(),"observedDraftHash",Sha256.hash(pageStateDraft),"draftMatches",expected.equals(pageStateDraft),"lastPageState",manualSnapshotLast,"scope","failure-only-existing-callback-observation; no new bridge or route probe");
        String raw=J.obj("kind","manualSnapshotFailureDiagnostic","value",value).toString();
        if(raw.getBytes(StandardCharsets.UTF_8).length<=3500)Log.i("PocketGeckoPerformance",raw);
        else Log.i("PocketGeckoPerformance",J.obj("kind","manualSnapshotFailureDiagnostic","value",J.obj("schema",1,"race",index,"payloadOmitted",true)).toString());
      }catch(RuntimeException ignored){}
    }
    void inputEvaluation(String phase,int sequence,String code){
      String action=code.contains("__fixtureInputTrace={")?"input-trace-install":code.contains("trace?.events||[]")?"input-snapshot":
        code.contains("__pocketReadDriver(\"page-state\"")?"page-state":code.contains("__pocketReadDriver(\"restore-draft\"")?"restore-draft":
        code.contains("__pocketReadDriver(\"fill\"")?"fill":code.contains("scrollIntoView")?"reveal-focus":code.contains("setSelectionRange")?"selection-script":"other";
      Log.i("PocketGeckoPerformance",J.obj("kind","inputEvaluation","value",J.obj("sequence",sequence,"phase",phase,"elapsedRealtime",SystemClock.elapsedRealtime(),"wallTimeMillis",System.currentTimeMillis(),"action",action,"characters",code.length(),"hash",Integer.toHexString(code.hashCode()),"prefix",action.equals("other")?code.substring(0,Math.min(180,code.length())):"","inFlight",owner.inFlight,"pending",owner.pending!=null,"thread",Thread.currentThread().getName())).toString());
    }
    @Override protected boolean allowedUrl(String target){return target!=null&&target.startsWith(ORIGIN+"/");}
    @Override boolean readingPage(String target){return target!=null&&target.startsWith(ORIGIN+PATH);}
    @Override JSONObject route(String target){
      // Observe the real guard/proxy decision; never substitute a permitted route.
      JSONObject decision=super.route(target);
      Log.i("PocketGeckoPerformance",J.obj("kind","route","value",J.obj("url",target,"decision",decision,"guardAllowed",owner.guard.allowed(),"offline",owner.offline,"networkReady",owner.networkReady)).toString());
      return decision;
    }
    @Override GeckoSession newSession(){
      GeckoSession sdk=super.newSession();GeckoSession.NavigationDelegate original=sdk.getNavigationDelegate();
      sdk.setNavigationDelegate(new GeckoSession.NavigationDelegate(){
        @Override public GeckoResult<AllowOrDeny> onLoadRequest(GeckoSession s,LoadRequest r){return original.onLoadRequest(s,r);}
        @Override public GeckoResult<AllowOrDeny> onSubframeLoadRequest(GeckoSession s,LoadRequest r){return original.onSubframeLoadRequest(s,r);}
        @Override public void onLocationChange(GeckoSession s,String target,List<GeckoSession.PermissionDelegate.ContentPermission> permissions,Boolean gesture){original.onLocationChange(s,target,permissions,gesture);}
        @Override public void onCanGoBack(GeckoSession s,boolean value){original.onCanGoBack(s,value);}
        @Override public void onCanGoForward(GeckoSession s,boolean value){original.onCanGoForward(s,value);}
        @Override public GeckoResult<GeckoSession> onNewSession(GeckoSession s,String target){return original.onNewSession(s,target);}
        @Override public GeckoResult<String> onLoadError(GeckoSession s,String target,WebRequestError error){
          if(target!=null&&target.startsWith(ORIGIN+PATH)){
            navigationError="Controlled Gecko load error category="+error.category+" code="+error.code+" uri="+target;
            Log.i("PocketGeckoPerformance",J.obj("kind","loadError","value",J.obj("url",target,"category",error.category,"code",error.code,"guardAllowed",owner.guard.allowed(),"offline",owner.offline,"networkReady",owner.networkReady)).toString());
          }
          return original.onLoadError(s,target,error);
        }
      });return sdk;
    }
  }
  interface Step {void run()throws Exception;}
  interface Result {void accept(JSONObject value)throws Exception;}
  void attempt(Step step){if(finished)return;try{step.run();}catch(Exception error){fail(error);}}
  void later(Step step,long delay){handler.postDelayed(()->attempt(step),delay);}
  void event(String kind,JSONObject value){Log.i("PocketGeckoPerformance",J.obj("kind",kind,"value",value).toString());
    if("gestureDeadline".equals(kind)&&scrollPhase!=null&&(scrollPhase.variant+"-scroll").equals(value.optString("id"))){scrollPhase.expiresElapsedMs=value.optLong("expiresElapsedMs",0);scrollPhase.run=scrollDiagnosticRun==null?"":scrollDiagnosticRun;}
  }
  void check(String name,boolean pass){checkCount++;event("check",J.obj("name",name,"pass",pass));if(!pass)throw new IllegalStateException(name);}
  void fail(Exception error){if(finished)return;finishScrollDiagnostics("failed");finished=true;frames.stop();if(archiveRelease!=null)archiveRelease.countDown();stopInputTrace(()->event("report",J.obj("status","failed","actualAndroidExecution",true,"actualGeckoExecution",true,"inputDiagnosticsEnabled",inputDiagnostics,"inputNativeDiagnosticsEnabled",inputNativeDiagnostics,"checkCount",checkCount,"error",error.toString())));}
  String asset(String name)throws Exception{try(InputStream in=getAssets().open(name)){return J.text(in,512*1024);}}
  @Override public void onCreate(Bundle saved){super.onCreate(saved);attempt(()->{
    if(!getPackageName().endsWith(".test"))throw new SecurityException("Only isolated integration package may run this fixture");
    inputDiagnostics=getIntent().getBooleanExtra("inputDiagnostics",false);
    inputNativeDiagnostics=getIntent().getBooleanExtra("inputNativeDiagnostics",false);
    scrollDiagnosticRun=getIntent().getStringExtra("scrollDiagnosticRun");
    if(inputDiagnostics&&inputNativeDiagnostics)throw new IllegalArgumentException("Input diagnostics must use one independent mode");
    getSharedPreferences("chat",0).edit().putString("browserEngine","gecko").putString("networkMode","external")
      .putString("proxy","socks://127.0.0.1:1087").putBoolean("requireExternalVpn",false).putBoolean("networkConfigured",false)
      .putBoolean("pageMode",true).putBoolean("desktopMode",true).putInt("privacyLevel",1)
      .putBoolean("backgroundWait",false).putBoolean("replyNotice",false).commit();
    ProfileCatalog.get(this).created(Profiles.slot(this));ChatSession.browserFactory=FixtureView::new;session=ChatSession.get(this);
    session.handler.removeCallbacks(session.tick);session.networkReady=true;session.guard.setBlocked(false);session.uiVisible=true;
    session.web.setWebViewClient(new WebViewClient(){
      @Override public void onPageStarted(WebView view,String url,android.graphics.Bitmap icon){session.handler.removeCallbacks(session.tick);}
      @Override public void onPageFinished(WebView view,String url){session.navigating=false;session.navigationFailed=false;session.reading.visible(url);session.handler.removeCallbacks(session.tick);}
    });
    LinearLayout root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);root.setFitsSystemWindows(true);
    TextView label=new TextView(this);label.setText("长会话实际 Gecko 性能回归 · 受控内容");root.addView(label);
    session.web.setHost(this);root.addView(session.web,new LinearLayout.LayoutParams(-1,0,1));setContentView(root);
    deadline=SystemClock.elapsedRealtime()+60000;waitRuntime();
  });}
  void waitRuntime(){attempt(()->{
    if(session.web.failed)throw new IllegalStateException("Gecko runtime failed");
    if(!session.web.ready||!session.web.privacyReady){if(SystemClock.elapsedRealtime()>deadline)throw new IllegalStateException("Gecko runtime timeout");later(this::waitRuntime,100);return;}
    session.web.configure(true,session.privacy.level());load("baseline");
  });}
  void load(String mode)throws Exception{
    variant=mode;String prefix="baseline".equals(mode)?"performance-baseline/":"";
    driver=asset(prefix+"page-driver.js");performanceSource=asset(prefix+"web-performance.js");
    boolean baseline="baseline".equals(mode);
    String guard=baseline?"location.protocol !== 'https:' || location.hostname !== 'chatgpt.com'":"window !== window.top || location.origin !== 'https://chatgpt.com'";
    int first=driver.indexOf(guard);if(first<0||driver.indexOf(guard,first+guard.length())>=0)throw new IllegalStateException("Unexpected production origin guard");
    // Each original asset has its own exact guard. Preserve current top-frame admission.
    driver=driver.replace(guard,baseline?"location.protocol !== 'http:' || location.hostname !== '127.0.0.1' || location.port !== '8767'":"window !== window.top || location.origin !== 'http://127.0.0.1:8767'");
    ((FixtureView)session.web).navigationError="";
    event("load",J.obj("variant",variant,"guardAllowed",session.guard.allowed(),"offline",session.offline,"networkReady",session.networkReady,"proxy",session.prefs.getString("proxy","")));
    session.web.loadUrl(ORIGIN+PATH+"?variant="+mode);deadline=SystemClock.elapsedRealtime()+30000;later(this::waitDocument,100);
  }
  void evaluate(String code,boolean measured,Result result){
    if(finished)return;long began=SystemClock.elapsedRealtime();
    session.web.evaluateJavascript(code,raw->attempt(()->{
      if(raw==null||"null".equals(raw))throw new IllegalStateException("No actual Gecko bridge result for "+variant);
      if(measured){payloadChars+=raw.length();payloadBytes+=raw.getBytes(StandardCharsets.UTF_8).length;scriptChars+=code.length();callbackMs+=SystemClock.elapsedRealtime()-began;}
      JSONObject value=J.parse(raw);if(value.length()==0)throw new IllegalStateException("Invalid bridge object");result.accept(value);
    }));
  }
  void waitDocument(){attempt(()->{
    if(!((FixtureView)session.web).navigationError.isEmpty())throw new IllegalStateException(((FixtureView)session.web).navigationError);
    if(SystemClock.elapsedRealtime()>deadline)throw new IllegalStateException("Controlled Gecko document timeout");
    // An unavailable extension port briefly returns null before DOMContentLoaded.
    session.web.evaluateJavascript("(()=>({ready:location.pathname==='/performance'&&location.search==="+JSONObject.quote("?variant="+variant)+"&&!!document.getElementById('fixture-ready')}))()",raw->attempt(()->{
      if(!J.parse(raw).optBoolean("ready")){later(this::waitDocument,100);return;}
      String runtime=performanceSource+"\nwindow.__fixtureReadDriver=(action,arg)=>"+driver.replace("__ACTION__","action").replace("__ARG__","arg")+";\n({installed:true})";
      evaluate(runtime,false,v->{check(variant+" installs its real versioned observation assets",v.optBoolean("installed"));snapshot(new JSONObject(),value->{
        check(variant+" loads all 242 messages including the 105k latest reply",value.optBoolean("ok")&&value.optJSONArray("order")!=null&&value.optJSONArray("order").length()==242);
        evaluate(telemetryInstall(),false,ready->{before=ready;samples=0;payloadBytes=payloadChars=callbackMs=scriptChars=0;frames.start();sample();});
      });});
    }));
  });}
  JSONObject baselineArgs(){return J.obj("kind","web","confirmed",true,"userKey","id:current-question","prompt","bound performance prompt","confirmedUrl",ORIGIN+PATH+"?variant="+variant,"expectedUrl",ORIGIN+PATH+"?variant="+variant,"export",true,"lightObservation",true);}
  void snapshot(JSONObject arg,Result result){evaluate("window.__fixtureReadDriver('web-transcript',"+arg+")",false,result);}
  boolean noResultTask(){return session.pending==null&&!session.prefs.contains("pending")&&!ChatService.running;}
  void sample(){attempt(()->{
    boolean current="current".equals(variant);
    evaluate("window.__fixtureReadDriver("+JSONObject.quote(current?"web-inspect":"poll")+","+(current?new JSONObject():baselineArgs())+")",true,value->{
      if(current){
        check("Current browser inspection sample "+samples+" reads page readiness without a result task",value.optBoolean("busy")&&value.optBoolean("composer")&&value.optBoolean("hasMessages")&&noResultTask());
        check("Current browser inspection sample "+samples+" transfers no reply body or completion fields",!value.has("markdown")&&!value.has("text")&&!value.has("prompt")&&!value.has("submitted")&&!value.has("terminal")&&!value.has("bindingLost"));
      }else{
        check("Historical baseline sample "+samples+" executes its original bound polling workload",value.optBoolean("busy")&&value.optBoolean("submitted")&&!value.optBoolean("bindingLost"));
        check("Baseline sample "+samples+" actually transfers its long body",value.optString("markdown").length()>105000&&value.optString("text").length()>105000);
      }
      int done=++samples;
      if(done==4||done==8){evaluate("document.getElementById('long-body').append(' streamed-"+done+"');({mutated:true})",false,v->later(done==4?this::scrollGesture:this::nextSample,80));return;}
      later(this::nextSample,80);
    });
  });}
  void beginScrollDiagnostics(){
    FixtureView web=(FixtureView)session.web;ScrollPhase phase=new ScrollPhase(variant,session);scrollPhase=phase;web.scrollTouches=new JSONArray();web.scrollTouchCount=0;web.scrollTracing=true;
    phase.sdk.setCompositorScrollDelegate(new GeckoSession.CompositorScrollDelegate(){@Override public void onScrollChanged(GeckoSession sdk,GeckoSession.ScrollPositionUpdate update){
      if(phase.prior!=null)phase.prior.onScrollChanged(sdk,update);
      if(scrollPhase==phase&&sdk==phase.sdk){phase.scrollX=update.scrollX;phase.scrollY=update.scrollY;phase.zoom=update.zoom;phase.updates++;if(phase.nativeUpdates.length()<64)phase.nativeUpdates.put(J.obj("sequence",phase.updates,"uptimeMs",SystemClock.uptimeMillis(),"scrollX",update.scrollX,"scrollY",update.scrollY,"zoom",update.zoom));}
    }});
  }
  String scrollSnapshotScript(boolean begin){return "(()=>{"+(begin?
    "{const trace={active:true,cancelled:false,events:[],count:0,initial:document.scrollingElement.scrollTop,run:"+JSONObject.quote(scrollDiagnosticRun)+",phase:"+JSONObject.quote(variant)+",traceId:"+scrollPhase.started+",document:performance.timeOrigin,url:location.href};const types=['touchstart','touchmove','touchend','touchcancel','wheel','scroll'];const listener=e=>{if(!trace.active)return;if(trace.document!==performance.timeOrigin||trace.url!==location.href){trace.cancel();return;}trace.count++;if(trace.count>64)return;const p=e.touches?.[0]||e.changedTouches?.[0],v=visualViewport;trace.events.push({sequence:trace.count,type:e.type,trusted:e.isTrusted,time:performance.now(),eventPhase:e.eventPhase,touches:e.touches?.length||0,x:p?.clientX??null,y:p?.clientY??null,deltaX:e.deltaX??null,deltaY:e.deltaY??null,scrollTop:document.scrollingElement.scrollTop,scrollY,pageTop:v?.pageTop??null,offsetTop:v?.offsetTop??null});};trace.stop=()=>{trace.active=false;for(const type of types)window.removeEventListener(type,listener,true);window.removeEventListener('pagehide',trace.cancel,true);};trace.cancel=()=>{trace.cancelled=true;trace.stop();};for(const type of types)window.addEventListener(type,listener,{passive:true,capture:true});window.addEventListener('pagehide',trace.cancel,{once:true,capture:true});window.__fixtureScrollDiagnostics=trace;}":"")+
    "const trace=window.__fixtureScrollDiagnostics,v=visualViewport,d=document.scrollingElement,events=trace?.events||[];if(trace)trace.events=[];const top=d.scrollTop;return {scrollTop:top,scrollLeft:d.scrollLeft,scrollY,scrollX,pageTop:v?.pageTop??null,pageLeft:v?.pageLeft??null,offsetTop:v?.offsetTop??null,offsetLeft:v?.offsetLeft??null,visualHeight:v?.height??null,visualWidth:v?.width??null,visualScale:v?.scale??null,innerHeight,innerWidth,clientHeight:d.clientHeight,clientWidth:d.clientWidth,scrollHeight:d.scrollHeight,scrollWidth:d.scrollWidth,url:location.href,document:performance.timeOrigin,visibility:document.visibilityState,documentFocused:document.hasFocus(),activeElement:document.activeElement?.id||document.activeElement?.tagName||'',eventCount:trace?.count||0,eventsDropped:Math.max(0,(trace?.count||0)-64),listenersActive:trace?.active||false,events};})()";}
  String scrollTelemetryScript(ScrollPhase phase){
    if(phase==null)return "window.__fixtureTelemetry()";
    JSONObject first=phase.samples.optJSONObject(0),dom=first==null?null:first.optJSONObject("dom");double document=dom==null?Double.NaN:dom.optDouble("document",Double.NaN);
    return "(()=>{const telemetry=window.__fixtureTelemetry();const trace=window.__fixtureScrollDiagnostics;const same=!!trace&&trace.run==="+JSONObject.quote(phase.run)+"&&trace.phase==="+JSONObject.quote(phase.variant)+"&&trace.traceId==="+phase.started+"&&trace.document==="+document+"&&trace.url==="+JSONObject.quote(phase.url)+"&&performance.timeOrigin==="+document+"&&location.href==="+JSONObject.quote(phase.url)+";"+
      "telemetry.scrollDomTail={run:trace?.run||'',phase:trace?.phase||'',traceId:trace?.traceId??null,document:performance.timeOrigin,url:location.href,cancelled:!same||!!trace?.cancelled,eventCount:trace?.count||0,eventsDropped:Math.max(0,(trace?.count||0)-64),events:same&&!trace.cancelled?trace.events:[]};if(same){trace.events=[];trace.stop();}return telemetry;})()";
  }
  JSONObject scrollNativeSnapshot(){
    try{GeckoWebView web=session.web;ScrollPhase phase=scrollPhase;android.graphics.Matrix matrix=new android.graphics.Matrix();web.current.getPageToSurfaceMatrix(matrix);float[] numbers=new float[9];matrix.getValues(numbers);JSONArray values=new JSONArray();for(float number:numbers)values.put(Float.valueOf(number));
      android.view.View root=web.getRootView(),surface=web.surface;int[] webOrigin=new int[2],surfaceOrigin=new int[2],rootOrigin=new int[2];web.getLocationOnScreen(webOrigin);surface.getLocationOnScreen(surfaceOrigin);root.getLocationOnScreen(rootOrigin);android.graphics.Rect visible=new android.graphics.Rect();boolean visibleRect=web.getGlobalVisibleRect(visible);visible.offset(rootOrigin[0],rootOrigin[1]);android.graphics.Rect frame=new android.graphics.Rect();root.getWindowVisibleDisplayFrame(frame);android.graphics.Rect window=Build.VERSION.SDK_INT>=30?getWindowManager().getCurrentWindowMetrics().getBounds():frame;
      WindowInsets insets=web.getRootWindowInsets();boolean ime=Build.VERSION.SDK_INT>=30&&insets!=null&&insets.isVisible(WindowInsets.Type.ime());int imeBottom=ime?insets.getInsets(WindowInsets.Type.ime()).bottom:0;
      return J.obj("uptimeMs",SystemClock.uptimeMillis(),"elapsedMs",SystemClock.elapsedRealtime()-phase.started,"navigationEpoch",session.navigationEpoch,"sameNavigation",session.navigationEpoch==phase.navigationEpoch,"url",web.getUrl(),"nativeUrl",web.locations.get(web.current),"sameUrl",phase.url.equals(web.getUrl()),"sdkOpen",web.current.isOpen(),"sessionIdentity",System.identityHashCode(web.current),"surfaceIdentity",System.identityHashCode(surface),"sameSession",web.current==phase.sdk,"sameSurface",surface==phase.surface,"attachedSessionIdentity",System.identityHashCode(web.surface.getSession()),"windowFocused",hasWindowFocus(),"webFocused",web.hasFocus(),"surfaceFocused",surface.hasFocus(),"webShown",web.isShown(),"surfaceShown",surface.isShown(),"surfaceAttached",surface.isAttachedToWindow(),"browserPaused",session.browserPaused,"readingDesktop",session.reading.desktop,"readingKeyboard",session.reading.keyboard,"readingLayout",web.readingLayout,"zoomActive",web.readingZoomActive(),"nativeMeasured",web.readingScaleMeasured(),"nativeScale",numbers[android.graphics.Matrix.MSCALE_Y]*web.readingLayout,"sdk",GeckoWebView.VERSION,"nativeUpdates",phase.updates,"nativeScrollX",phase.updates>0?phase.scrollX:JSONObject.NULL,"nativeScrollY",phase.updates>0?phase.scrollY:JSONObject.NULL,"nativeZoom",phase.updates>0?phase.zoom:JSONObject.NULL,"pageToSurfaceMatrix",values,"web",J.obj("x",webOrigin[0],"y",webOrigin[1],"width",web.getWidth(),"height",web.getHeight()),"surface",J.obj("x",surfaceOrigin[0],"y",surfaceOrigin[1],"width",surface.getWidth(),"height",surface.getHeight()),"root",J.obj("x",rootOrigin[0],"y",rootOrigin[1],"width",root.getWidth(),"height",root.getHeight()),"visibleRectAvailable",visibleRect,"visibleRect",scrollRect(visible),"windowBounds",scrollRect(window),"windowVisibleFrame",scrollRect(frame),"imeVisible",ime,"imeBottom",imeBottom);
    }catch(Exception error){return J.obj("diagnosticError",error.toString());}
  }
  static JSONObject scrollRect(android.graphics.Rect rect){return J.obj("left",rect.left,"top",rect.top,"right",rect.right,"bottom",rect.bottom);}
  void recordScrollSample(String stage,JSONObject dom){
    ScrollPhase phase=scrollPhase;if(phase==null)return;phase.sampleCount++;JSONArray events=dom.optJSONArray("events");dom.remove("events");if(events!=null)for(int i=0;i<events.length();i++){JSONObject item=events.optJSONObject(i);phase.domEvents.put(item);event("scrollDomEvent",J.obj("phase",phase.variant,"event",item));}
    FixtureView web=(FixtureView)session.web;while(phase.touchPublished<web.scrollTouches.length()){JSONObject item=web.scrollTouches.optJSONObject(phase.touchPublished++);event("scrollNativeTouch",J.obj("phase",phase.variant,"event",item));}
    JSONObject sample=J.obj("phase",phase.variant,"stage",stage,"sequence",phase.sampleCount,"beforeScrollTop",phase.hasBefore?phase.beforeScrollTop:JSONObject.NULL,"dom",dom,"native",scrollNativeSnapshot());if(phase.samples.length()<256)phase.samples.put(sample);event("scrollSample",sample);
  }
  void finishScrollDiagnostics(String outcome){
    if(!"passed".equals(outcome))cancelScrollDomTail(outcome);
    ScrollPhase phase=scrollPhase;if(phase==null)return;FixtureView web=(FixtureView)session.web;web.scrollTracing=false;phase.sdk.setCompositorScrollDelegate(phase.prior);scrollPhase=null;
    if("passed".equals(outcome)){cancelScrollDomTail("superseded");scrollDomTail=phase;}
    scrollDiagnosticPhases.put(J.obj("phase",phase.variant,"outcome",outcome,"url",phase.url,"navigationEpoch",phase.navigationEpoch,"sampleCount",phase.sampleCount,"samplesDropped",Math.max(0,phase.sampleCount-256),"samples",phase.samples,"nativeUpdates",phase.nativeUpdates,"nativeUpdatesCount",phase.updates,"nativeUpdatesDropped",Math.max(0,phase.updates-64),"nativeTouches",web.scrollTouches,"nativeTouchCount",web.scrollTouchCount,"nativeTouchesDropped",Math.max(0,web.scrollTouchCount-64),"domEvents",phase.domEvents,"domObservation",phase.domObservation));
    writeScrollDiagnostics();
  }
  void cancelScrollDomTail(String reason){
    ScrollPhase phase=scrollDomTail;if(phase==null)return;scrollDomTail=null;
    JSONObject observation=J.obj("status","cancelled","reason",reason,"added",0);phase.domObservation.put(observation);event("scrollDomObservation",J.obj("phase",phase.variant,"observation",observation));writeScrollDiagnostics();
  }
  void finishScrollDomTail(ScrollPhase phase,JSONObject tail){
    if(phase==null||scrollDomTail!=phase)return;scrollDomTail=null;String reason="";JSONArray events=tail==null?null:tail.optJSONArray("events");
    JSONObject first=phase.samples.optJSONObject(0),dom=first==null?null:first.optJSONObject("dom");double document=dom==null?Double.NaN:dom.optDouble("document",Double.NaN);
    if(finished||scrollPhase!=null||!phase.run.equals(scrollDiagnosticRun)||!phase.variant.equals(variant))reason="phase-cancelled";
    else if(session==null||session.web.current!=phase.sdk||session.web.surface!=phase.surface||session.navigationEpoch!=phase.navigationEpoch||!phase.url.equals(session.web.getUrl()))reason="navigation-changed";
    else if(phase.expiresElapsedMs<=0||SystemClock.elapsedRealtime()>phase.expiresElapsedMs)reason="deadline-expired";
    else if(tail==null||tail.optBoolean("cancelled",true))reason="trace-cancelled";
    else if(!phase.run.equals(tail.optString("run"))||!phase.variant.equals(tail.optString("phase"))||tail.optDouble("traceId",Double.NaN)!=phase.started||!Double.isFinite(document)||tail.optDouble("document",Double.NaN)!=document||!phase.url.equals(tail.optString("url")))reason="document-changed";
    else if(events==null||events.length()+phase.domEvents.length()>64)reason="invalid-tail";
    else{
      JSONObject last=phase.domEvents.optJSONObject(phase.domEvents.length()-1);int previous=phase.domEvents.length()==0?0:last==null?-1:last.optInt("sequence",-1);
      if(previous<0)reason="invalid-tail";
      for(int i=0;i<events.length();i++){
        JSONObject item=events.optJSONObject(i);Object sequence=item==null?null:item.opt("sequence");
        if(item==null||!(sequence instanceof Number)||((Number)sequence).doubleValue()!=previous+1||previous>=64||!(item.opt("trusted") instanceof Boolean)
          ||!java.util.Arrays.asList("touchstart","touchmove","touchend","touchcancel","wheel","scroll").contains(item.optString("type"))){reason="invalid-tail";break;}previous++;
      }
      Object count=tail.opt("eventCount"),dropped=tail.opt("eventsDropped");
      if(!(count instanceof Number)||((Number)count).doubleValue()!=tail.optLong("eventCount",-1)||previous!=Math.min(64,tail.optLong("eventCount",-1))
        ||!(dropped instanceof Number)||((Number)dropped).doubleValue()!=Math.max(0,tail.optLong("eventCount",-1)-64))reason="invalid-tail";
    }
    int added=0;if(reason.isEmpty())for(int i=0;i<events.length();i++){JSONObject item=events.optJSONObject(i);phase.domEvents.put(item);event("scrollDomEvent",J.obj("phase",phase.variant,"event",item));added++;}
    JSONObject observation=J.obj("status",reason.isEmpty()?"complete":"cancelled","reason",reason,"added",added,"eventCount",tail==null?JSONObject.NULL:tail.opt("eventCount"),"eventsDropped",tail==null?JSONObject.NULL:tail.opt("eventsDropped"));
    phase.domObservation.put(observation);event("scrollDomObservation",J.obj("phase",phase.variant,"observation",observation));writeScrollDiagnostics();
  }
  void writeScrollDiagnostics(){
    try{J.write(new java.io.File(getFilesDir(),"gecko-scroll-diagnostics.json"),J.obj("schema",1,"run",scrollDiagnosticRun,"scope","Read-only scroll-phase diagnostics; native sampling still ends at first scroll growth. The same passive DOM listener remains through the existing measured telemetry RPC, which drains once after the original telemetry calculation and stops it; DOM tails outside the original 20s deadline or document are discarded. No polling, timeout, assertion, gesture, frame boundary or typing changes. Added work and passive touch listeners may affect APZ touch dispatch, scroll-phase scheduling and frame timing; first four busy samples are unchanged.","phases",scrollDiagnosticPhases).toString());}catch(Exception error){event("scrollDiagnosticError",J.obj("error",error.toString()));}
  }
  void scrollGesture(){beginScrollDiagnostics();evaluate(scrollSnapshotScript(true),false,beforeScroll->{
    scrollPhase.beforeScrollTop=beforeScroll.optDouble("scrollTop");scrollPhase.hasBefore=true;recordScrollSample("before",beforeScroll);
    int[] position=new int[2];session.web.getLocationOnScreen(position);int x=position[0]+session.web.getWidth()/2;
    event("gestureNeeded",J.obj("id",variant+"-scroll","action","scroll","x",x,"startY",position[1]+session.web.getHeight()*3/4,"endY",position[1]+session.web.getHeight()/4));
    long deadlineSampleElapsed=SystemClock.elapsedRealtime(),deadlineSampleUptime=SystemClock.uptimeMillis();
    long expires=deadlineSampleElapsed+20000;
    event("gestureDeadline",J.obj("id",variant+"-scroll","sampledElapsedMs",deadlineSampleElapsed,"sampledUptimeMs",deadlineSampleUptime,"expiresElapsedMs",expires,"expiresUptimeMs",deadlineSampleUptime+(expires-deadlineSampleElapsed)));
    waitScroll(beforeScroll.optDouble("scrollTop"),expires);
  });}
  void waitScroll(double previous,long expires){evaluate(scrollSnapshotScript(false),false,afterScroll->{
    recordScrollSample("after",afterScroll);
    if(afterScroll.optDouble("scrollTop")<=previous){if(SystemClock.elapsedRealtime()>expires)throw new IllegalStateException("Actual Android scroll gesture did not reach Gecko");later(()->waitScroll(previous,expires),100);return;}
    finishScrollDiagnostics("passed");check(variant+" accepts an actual Android scroll while its versioned read workload is active",true);later(this::nextSample,80);
  });}
  void nextSample(){if(samples<12)sample();else measured();}
  void measured(){attempt(()->{
    JSONObject nativeFrames=frames.stop();ScrollPhase domPhase=scrollDomTail;evaluate(scrollTelemetryScript(domPhase),false,telemetry->{
      finishScrollDomTail(domPhase,telemetry.optJSONObject("scrollDomTail"));
      JSONObject metrics=J.obj("variant",variant,"action","current".equals(variant)?"web-inspect":"historical-poll","samples",samples,"bridgeResponseBytes",payloadBytes,"bridgeResponseChars",payloadChars,"bridgeScriptChars",scriptChars,"evaluateCallbackMs",callbackMs,"domReadChars",telemetry.optLong("readChars"),"domReadCalls",telemetry.optLong("readCalls"),"cloneCalls",telemetry.optLong("clones"),"elapsedJsMs",telemetry.optDouble("elapsedMs"),"raf",telemetry.optJSONObject("raf"),"androidChoreographer",nativeFrames,"observationBefore",before.optJSONObject("observation"),"observationAfter",telemetry.optJSONObject("observation"));
      event("measurement",metrics);
      check(variant+" preserves the draft, synthetic session cookie and send count",telemetry.optBoolean("draftPreserved")&&telemetry.optBoolean("cookiePreserved")&&telemetry.optInt("sendCount")==0);
      if("baseline".equals(variant)){baselineMetrics=metrics;load("current");return;}
      currentMetrics=metrics;
      check("Current browser inspection bridge payload is at least 95 percent below the historical polling workload",payloadBytes*20<baselineMetrics.optLong("bridgeResponseBytes"));
      check("Current browser inspection DOM reads are at least 95 percent below the historical polling workload",telemetry.optLong("readChars")*20<baselineMetrics.optLong("domReadChars"));
      JSONObject initial=before.optJSONObject("observation"),after=telemetry.optJSONObject("observation");
      check("Browser readiness inspection never rebuilds markdown or files",after.optLong("derivedBuilt")==initial.optLong("derivedBuilt"));
      check("Text mutations preserve the cached message topology",after.optLong("messageListsBuilt")==initial.optLong("messageListsBuilt"));
      terminal();
    });
  });}
  void terminal(){
    evaluate("document.getElementById('stop-button').remove();({stopped:true})",false,v->later(()->snapshot(snapshotCursor(before),changed->{
      check("Two streaming mutations rebuild only the current transcript entry",changed.optJSONArray("changes")!=null&&changed.optJSONArray("changes").length()==1&&currentEntry(changed).optString("id").equals("id:current-answer"));
      firstFull=changed;known=snapshotCursor(changed);JSONObject entry=currentEntry(changed);String body=entry.optString("text");
      check("On-demand transcript keeps the entire 105k reply, both stream tails, code and file",body.length()>105000&&body.startsWith("preserved reply line ".repeat(5000).trim())&&body.contains("streamed-4 streamed-8")&&body.contains("```js\nconst keep = 1;")&&download(entry,"result.csv")&&noResultTask());
      evaluate("({stats:window.__pocketWebPerformance.stats()})",false,stats->snapshot(known,stable->{
        check("An unchanged on-demand transcript returns no repeated message bodies",stable.optBoolean("ok")&&!stable.optBoolean("changed")&&!stable.has("changes")&&stable.optLong("revision")==changed.optLong("revision"));
        evaluate("({stats:window.__pocketWebPerformance.stats()})",false,after->{
          check("An unchanged transcript reuses cached markdown and file metadata",after.optJSONObject("stats").optLong("derivedBuilt")==stats.optJSONObject("stats").optLong("derivedBuilt"));mutateAfterTerminal();
        });
      }));
    }),100));
  }
  void mutateAfterTerminal(){evaluate("document.getElementById('long-body').append(' final-tail-after-done');({mutated:true})",false,v->later(()->snapshot(known,full->{
    check("Later text changes invalidate the on-demand transcript cursor",currentEntry(full).optString("text").contains("final-tail-after-done")&&full.optLong("revision")>known.optLong("revision"));known=snapshotCursor(full);
    evaluate("(()=>{const previous=document.getElementById('current-answer'),next=previous.cloneNode(true);next.querySelector('#long-body').textContent='replacement with same stable message ID';previous.replaceWith(next);return {replaced:true};})()",false,w->later(()->snapshot(known,replaced->{
      check("Reusing a stable message ID on a new node cannot retain the previous body",currentEntry(replaced).optString("id").equals("id:current-answer")&&currentEntry(replaced).optString("text").startsWith("replacement with same stable message ID")&&replaced.optLong("revision")>known.optLong("revision"));known=snapshotCursor(replaced);
      evaluate("(()=>{const file=document.getElementById('generated-file');file.download='new-result.csv';file.textContent='new-result.csv';return {fileChanged:true};})()",false,x->later(()->snapshot(known,file->{
        check("Generated file changes invalidate on-demand attachment metadata",download(currentEntry(file),"new-result.csv")&&!download(currentEntry(file),"result.csv")&&file.optLong("revision")>known.optLong("revision"));siblingFiles(file);
      }),100));
    }),100));
  }),100));}
  JSONObject snapshotCursor(JSONObject snapshot){return J.obj("documentId",snapshot.optString("documentId"),"revision",snapshot.optLong("revision"));}
  JSONObject currentEntry(JSONObject snapshot){JSONArray rows=snapshot.optJSONArray("changes");for(int i=0;rows!=null&&i<rows.length();i++){JSONObject entry=rows.optJSONObject(i);if(entry!=null&&"id:current-answer".equals(entry.optString("id")))return entry;}return new JSONObject();}
  boolean download(JSONObject entry,String name){JSONArray files=entry.optJSONArray("downloads");for(int i=0;files!=null&&i<files.length();i++)if(name.equals(files.optJSONObject(i).optString("name")))return true;return false;}
  void siblingFiles(JSONObject prior)throws Exception{
    known=snapshotCursor(prior);evaluate("document.getElementById('current-answer').parentElement.insertAdjacentHTML('beforeend','<a id=\"sibling-file\" download=\"sibling.csv\" href=\"/backend-api/files/sibling\">sibling.csv</a>');({fileAdded:true})",false,v->later(()->snapshot(known,added->{
      check("Sibling generated file cards invalidate the actual Gecko transcript revision",added.optLong("revision")>prior.optLong("revision"));
      check("Sibling file cards appear in incremental transcript downloads",download(currentEntry(added),"sibling.csv"));known=snapshotCursor(added);
      evaluate("(()=>{const file=document.getElementById('sibling-file');file.download='renamed-sibling.csv';file.textContent='renamed-sibling.csv';return {fileRenamed:true};})()",false,w->later(()->snapshot(known,renamed->{
        check("Renaming a sibling file card refreshes actual Gecko metadata and transcript downloads",renamed.optLong("revision")>added.optLong("revision")&&download(currentEntry(renamed),"renamed-sibling.csv")&&!download(currentEntry(renamed),"sibling.csv"));known=snapshotCursor(renamed);
        evaluate("document.getElementById('sibling-file').remove();({fileRemoved:true})",false,x->later(()->snapshot(known,removed->{
          check("Removing a sibling file card invalidates the actual Gecko transcript metadata",removed.optLong("revision")>renamed.optLong("revision")&&!download(currentEntry(removed),"renamed-sibling.csv")&&download(currentEntry(removed),"new-result.csv"));detachedBody(removed);
        }),100));
      }),100));
    }),100));
  }
  void detachedBody(JSONObject cursor){evaluate("(()=>{const body=document.querySelector('#current-answer > .markdown');window.__fixtureDetachedBody=body;body.remove();return {detached:true};})()",false,v->later(()->{
    evaluate("(()=>{const body=window.__fixtureDetachedBody;body.querySelector('#long-body').textContent='detached existing body edited while outside the document';document.getElementById('current-answer').append(body);delete window.__fixtureDetachedBody;return {reattached:true};})()",false,w->later(()->snapshot(snapshotCursor(cursor),after->{
      check("Reattaching an edited cached body refreshes the actual Gecko transcript",currentEntry(after).optString("text").startsWith("detached existing body edited while outside the document")&&after.optLong("revision")>cursor.optLong("revision"));
      evaluate("window.__fixtureTelemetry()",false,end->{check("Semantic checks preserve the synthetic login, draft and no-send invariant",end.optBoolean("draftPreserved")&&end.optBoolean("cookiePreserved")&&end.optInt("sendCount")==0&&noResultTask());productionLifecycle();});
    }),100));
  },100));}
  void productionLifecycle(){attempt(()->{
    String canonical=MainActivity.ORIGIN+"c/performance-fixture",actual=ORIGIN+PATH+"?variant=current";
    String code="(()=>{document.getElementById('long-body').textContent='preserved reply line '.repeat(5000)+' Java retained final tail';"+
      "window.__pocketReadDriver=(action,arg)=>{const mapped={...arg};for(const key of ['confirmedUrl','expectedUrl'])if(mapped[key]==="+JSONObject.quote(canonical)+")mapped[key]="+JSONObject.quote(actual)+";"+
      "const value=window.__fixtureReadDriver(action,mapped);if(value?.url)value.url="+JSONObject.quote(canonical)+";return value;};return {adapted:true};})()";
    evaluate(code,false,ready->{
      ((FixtureView)session.web).semanticRoute=true;session.state=J.obj("composer",true);session.navigating=false;session.navigationFailed=false;session.webMirror.reset();session.entries=new JSONArray();session.conversation=canonical;
      later(()->inspectProduction(value->{
        check("Production browser inspection has no send or result task",value.optBoolean("composer")&&noResultTask()&&!value.has("submitted")&&!value.has("terminal"));
        check("Production inspection keeps the full 242-message transcript",session.entries.length()==242&&session.entries.optJSONObject(241).optString("text").length()>105000&&session.entries.optJSONObject(241).optString("text").contains("Java retained final tail"));
        waitStored(SystemClock.elapsedRealtime()+10000);
      }),100);
    });
  });}
  void inspectProduction(Result result){attempt(()->{
    session.handler.removeCallbacks(session.tick);session.inFlight=false;((FixtureView)session.web).productionInspect=null;
    session.sync();awaitInspection(result,SystemClock.elapsedRealtime()+10000);
  });}
  void awaitInspection(Result result,long expires){attempt(()->{
    if(session.inFlight){if(SystemClock.elapsedRealtime()>expires)throw new IllegalStateException("Production browser inspection timeout");later(()->awaitInspection(result,expires),50);return;}
    JSONObject observed=((FixtureView)session.web).productionInspect;
    if(observed==null)throw new IllegalStateException("Production ChatSession did not use the actual Gecko inspection runtime");result.accept(observed);
  });}
  void waitStored(long expires){session.webStore.worker.execute(()->{
    JSONArray saved=session.cache.messages(MainActivity.ORIGIN+"c/performance-fixture");handler.post(()->attempt(()->{
      if(saved.length()!=242){if(SystemClock.elapsedRealtime()>expires)throw new IllegalStateException("Browser transcript was not durably stored");later(()->waitStored(expires),100);return;}
      check("The complete final body is durably saved by the production transcript worker",saved.optJSONObject(241).optString("text").length()>105000&&saved.optJSONObject(241).optString("text").contains("Java retained final tail"));
      evaluate("window.__fixtureTelemetry()",false,end->{check("Production browser snapshots preserve document login, unsent draft and no-send invariant",end.optBoolean("draftPreserved")&&end.optBoolean("cookiePreserved")&&end.optInt("sendCount")==0&&noResultTask());inputGesture();});
    }));
  });}
  String inputTraceInstall(){
    // The release regression retains the original passive listeners. Additional
    // observation can perturb a timing race and must be explicitly requested.
    if(!inputDiagnostics)return "(()=>{const composer=document.getElementById('prompt-textarea'),trace=window.__fixtureInputTrace={events:[],overflow:false};"+
      "for(const type of ['focus','blur','keydown','keyup','beforeinput','input','compositionstart','compositionupdate','compositionend','select'])composer.addEventListener(type,event=>{"+
      "if(trace.events.length>=256){trace.overflow=true;return;}trace.events.push({type:event.type,key:event.key||'',data:event.data??'',inputType:event.inputType||'',trusted:event.isTrusted,composing:!!event.isComposing,time:performance.now(),draft:composer.value,start:composer.selectionStart,end:composer.selectionEnd});});return {installed:true};})()";
    return "(()=>{const composer=document.getElementById('prompt-textarea'),trace=window.__fixtureInputTrace={events:[],overflow:false};"+
    "const record=(type,extra={})=>{if(trace.events.length>=512){trace.overflow=true;return;}trace.events.push({type,time:performance.now(),timeOrigin:performance.timeOrigin,draft:composer.value,start:composer.selectionStart,end:composer.selectionEnd,...extra});};"+
    "for(const type of ['focus','blur','keydown','keyup','beforeinput','input','compositionstart','compositionupdate','compositionend','select'])composer.addEventListener(type,event=>"+
    "record(event.type,{key:event.key||'',data:event.data??'',inputType:event.inputType||'',trusted:event.isTrusted,composing:!!event.isComposing}));"+
    "document.addEventListener('selectionchange',event=>{if(document.activeElement===composer||event.target===composer)record('selectionchange',{target:event.target===composer?'composer':'document',trusted:event.isTrusted});},true);"+
    // Passive diagnostics around the original methods/setters: no focus or selection writes.
    "const caller=()=>String(new Error().stack||'').slice(0,360);"+
    "for(const name of ['setSelectionRange','setRangeText','select','focus','blur']){const original=composer[name];if(typeof original!=='function')continue;Object.defineProperty(composer,name,{configurable:true,writable:true,value:function(...args){record('script-call',{method:name,arguments:args.map(value=>typeof value==='string'?value.slice(0,90):typeof value==='object'?'[object]':value),stack:caller()});const value=original.apply(this,args);record('script-return',{method:name});return value;}});}"+
    "for(const name of ['selectionStart','selectionEnd','selectionDirection','value']){let prototype=composer,descriptor;while(prototype&&!(descriptor=Object.getOwnPropertyDescriptor(prototype,name)))prototype=Object.getPrototypeOf(prototype);if(!descriptor?.get||!descriptor?.set||!descriptor.configurable)continue;Object.defineProperty(composer,name,{...descriptor,get(){return descriptor.get.call(this);},set(value){record('script-setter',{property:name,value:typeof value==='string'?value.slice(0,90):value,stack:caller()});descriptor.set.call(this,value);record('script-setter-return',{property:name});}});}"+
    "return {installed:true};})()";}
  String inputSnapshot(){return "(()=>{const composer=document.getElementById('prompt-textarea'),r=composer.getBoundingClientRect(),vp=visualViewport,trace=window.__fixtureInputTrace;"+
    "return {draft:composer.value,composerFocused:document.activeElement===composer,cookie:document.cookie,sendCount:Number(document.getElementById('send-count').textContent),"+
    "start:composer.selectionStart,end:composer.selectionEnd,x:r.left+r.width/2,y:r.top+r.height/2,width:innerWidth,height:innerHeight,"+
    "bounds:{left:r.left,top:r.top,width:r.width,height:r.height},viewport:{width:vp?.width??innerWidth,height:vp?.height??innerHeight,offsetLeft:vp?.offsetLeft??0,offsetTop:vp?.offsetTop??0,scale:vp?.scale??1,innerWidth,innerHeight},"+
    "inputEvents:trace?.events||[],traceOverflow:!!trace?.overflow};})()";}
  void inputGesture(){attempt(()->{
    if(inputNativeDiagnostics)bufferedInputTrace=GeckoInputTrace.attachBuffered(((FixtureView)session.web).current);
    if(inputDiagnostics){
      nativeInputTrace=GeckoInputTrace.attach(((FixtureView)session.web).current,value->event("nativeInputTrace",value));
      ((FixtureView)session.web).inputTracing=true;
    }
    evaluate(inputTraceInstall()+";\n"+inputSnapshot(),false,point->{
    inputDraft=point.optString("draft");if(inputDraft.contains(INPUT_MARKER))throw new IllegalStateException("Input fixture draft already contains the synthetic marker");
    inputRequested=false;inputFocusSamples=0;inputReadinessKey="";inputReadySince=0;inputTraceOffset=inputReadinessSequence=0;inputImeSettled=false;
    int[] position=new int[2];session.web.getLocationOnScreen(position);
    int x=position[0]+(int)(point.optDouble("x")*session.web.getWidth()/point.optDouble("width"));
    int y=position[1]+(int)(point.optDouble("y")*session.web.getHeight()/point.optDouble("height"));
    event("gestureNeeded",J.obj("id","current-input","action","input","x",x,"y",y,"text",INPUT_MARKER));waitInput(SystemClock.elapsedRealtime()+30000);
  });});}
  void stopInputTrace(){stopInputTrace(null);}
  void stopInputTrace(Runnable next){if(session!=null&&session.web instanceof FixtureView)((FixtureView)session.web).inputTracing=false;if(nativeInputTrace!=null){nativeInputTrace.stop();nativeInputTrace=null;}if(bufferedInputTrace!=null){GeckoInputTrace.Buffered trace=bufferedInputTrace;bufferedInputTrace=null;trace.stopAndFlush(handler,value->event("nativeInputTrace",value),next);}else if(next!=null)next.run();}
  void recordInputTrace(JSONObject value)throws Exception{
    JSONArray events=value.optJSONArray("inputEvents");if(events==null)return;
    while(inputTraceOffset<events.length()){
      int offset=inputTraceOffset;JSONArray batch=new JSONArray();while(inputTraceOffset<events.length()&&batch.length()<(inputDiagnostics?2:4))batch.put(events.optJSONObject(inputTraceOffset++));
      event("inputEvents",J.obj("id","current-input","offset",offset,"events",batch));
    }
  }
  void waitInput(long expires){evaluate(inputSnapshot(),false,value->{
    InputMethodManager keyboard=(InputMethodManager)getSystemService(INPUT_METHOD_SERVICE);
    boolean nativeFocused=session.web.hasFocus(),acceptingText=keyboard!=null&&keyboard.isAcceptingText();
    WindowInsets insets=session.web.getRootWindowInsets();boolean imeVisible=Build.VERSION.SDK_INT>=30&&insets!=null&&insets.isVisible(WindowInsets.Type.ime());
    int imeBottom=Build.VERSION.SDK_INT>=30&&insets!=null?insets.getInsets(WindowInsets.Type.ime()).bottom:0;
    int[] position=new int[2];session.web.getLocationOnScreen(position);
    JSONObject nativeBounds=J.obj("left",position[0],"top",position[1],"width",session.web.getWidth(),"height",session.web.getHeight());
    boolean inputReady=value.optBoolean("composerFocused")&&nativeFocused&&acceptingText&&imeVisible&&imeBottom>0&&value.optInt("start",-1)>=0&&value.optInt("start",-1)==value.optInt("end",-2);
    String readiness=value.optInt("start")+"|"+value.optInt("end")+"|"+value.optJSONObject("bounds")+"|"+value.optJSONObject("viewport")+"|"+nativeBounds+"|"+imeBottom;
    long now=SystemClock.elapsedRealtime();
    if(!inputRequested){
      if(!inputReady){inputFocusSamples=0;inputReadySince=0;inputReadinessKey="";}
      else if(!readiness.equals(inputReadinessKey)){inputFocusSamples=1;inputReadySince=now;inputReadinessKey=readiness;}
      else inputFocusSamples++;
    }
    recordInputTrace(value);
    long settledMs=inputReadySince==0?0:now-inputReadySince;
    event("inputReadiness",J.obj("id","current-input","sequence",inputReadinessSequence++,"requested",inputRequested,"composerFocused",value.optBoolean("composerFocused"),"nativeFocused",nativeFocused,"acceptingText",acceptingText,"imeVisible",imeVisible,"imeBottom",imeBottom,"stableFocusSamples",inputFocusSamples,"settledMs",settledMs,"start",value.optInt("start"),"end",value.optInt("end"),"draft",value.optString("draft"),"bounds",value.optJSONObject("bounds"),"viewport",value.optJSONObject("viewport"),"nativeBounds",nativeBounds));
    if(!inputRequested&&inputReady&&inputFocusSamples>=3&&settledMs>=600){
      if(bufferedInputTrace!=null&&!bufferedInputTrace.childAttached){
        if(!bufferedInputTrace.childError.isEmpty())throw new IllegalStateException("Native diagnostic focused-child installation failed: "+bufferedInputTrace.childError);
        bufferedInputTrace.prepareFocusedChild(handler,()->attempt(()->waitInput(expires)));return;
      }
      if(!value.optString("draft").equals(inputDraft))throw new IllegalStateException("The draft changed before the single Android input burst");
      inputRequested=true;inputImeSettled=true;
      check("Actual Android input waits for visible IME and unchanged viewport, composer and caret",imeVisible&&imeBottom>0&&settledMs>=600&&inputFocusSamples>=3);
      event("textNeeded",J.obj("id","current-input","text",INPUT_MARKER,"composerFocused",true,"nativeFocused",true,"acceptingText",true,"imeVisible",true,"imeBottom",imeBottom,"stableFocusSamples",inputFocusSamples,"settledMs",settledMs,"start",value.optInt("start"),"end",value.optInt("end"),"draft",inputDraft,"bounds",value.optJSONObject("bounds"),"viewport",value.optJSONObject("viewport"),"nativeBounds",nativeBounds));
    }
    String actual=value.optString("draft");int inserted=actual.indexOf(INPUT_MARKER);
    if(inserted<0){
      if(SystemClock.elapsedRealtime()>expires){JSONObject failure=new JSONObject(value.toString());JSONArray recorded=failure.optJSONArray("inputEvents");failure.remove("inputEvents");failure.put("inputEventCount",recorded==null?0:recorded.length());throw new IllegalStateException("Actual Android keyboard input did not reach Gecko: "+failure+" nativeFocused="+nativeFocused+" acceptingText="+acceptingText+" imeVisible="+imeVisible+" textRequested="+inputRequested);}
      later(()->waitInput(expires),100);return;
    }
    // A real tap can put the caret anywhere. Require exactly one actual insertion
    // and every pre-existing character, rather than assuming an end-of-line caret.
    check("Actual Android tap and keyboard input preserve the existing composer draft",inputRequested&&actual.indexOf(INPUT_MARKER,inserted+INPUT_MARKER.length())<0&&(actual.substring(0,inserted)+actual.substring(inserted+INPUT_MARKER.length())).equals(inputDraft));
    JSONArray recorded=value.optJSONArray("inputEvents");StringBuilder keys=new StringBuilder();int inputs=0;boolean trusted=recorded!=null&&!value.optBoolean("traceOverflow");
    if(recorded!=null)for(int i=0;i<recorded.length();i++){JSONObject item=recorded.optJSONObject(i);String type=item.optString("type");if(type.equals("keydown")&&item.optString("key").length()==1)keys.append(item.optString("key"));if(type.equals("input"))inputs++;if(type.equals("keydown")||type.equals("keyup")||type.equals("beforeinput")||type.equals("input"))trusted&=item.optBoolean("trusted");}
    check("The single Android input burst delivers exact ordered trusted keys and real input events",trusted&&inputs>0&&keys.toString().equals(INPUT_MARKER));
    check("Actual user input neither sends a message nor changes the synthetic login",value.optInt("sendCount")==0&&value.optString("cookie").contains("session=synthetic-performance"));stopInputTrace(this::browserLifecycle);
  });}
  // Browser-only lifecycle checks follow the exact original native gesture/input oracle.
  void browserLifecycle(){attempt(()->{
    ((FixtureView)session.web).semanticUrl=MainActivity.ORIGIN+"c/browser-fixture";
    String code="(()=>{history.replaceState(null,'','/c/browser-fixture');window.__browserDraft=document.getElementById('prompt-textarea').value;"+
      "window.__pocketReadDriver=(action,arg)=>{const mapped={...arg};for(const key of ['confirmedUrl','expectedUrl'])if(mapped[key]){const address=new URL(mapped[key]);if(address.origin==="+JSONObject.quote(MainActivity.ORIGIN.substring(0,MainActivity.ORIGIN.length()-1))+")mapped[key]="+JSONObject.quote(ORIGIN)+"+address.pathname+address.search+address.hash;}"+
      "const value=window.__fixtureReadDriver(action,mapped);if(value?.url)value.url="+JSONObject.quote(MainActivity.ORIGIN.substring(0,MainActivity.ORIGIN.length()-1))+"+new URL(value.url).pathname;return value;};return {adapted:true};})()";
    evaluate(code,false,ready->inspectProduction(first->{
      check("Actual browser lifecycle starts with the existing document and no result task",first.optBoolean("composer")&&first.optBoolean("hasMessages")&&noResultTask());
      browserMutate("(()=>{window.__browserMain=document.querySelector('main');window.__browserChildren=[...window.__browserMain.childNodes];window.__browserMain.replaceChildren();return {detached:true};})()",empty->{
        check("Same-route empty DOM does not create a native send or result task",!empty.optBoolean("hasMessages")&&noResultTask());
        browserMutate("window.__browserMain.replaceChildren(...window.__browserChildren);({restored:true})",restored->{
          check("Restoring the same document preserves browser readiness without task binding",restored.optBoolean("hasMessages")&&noResultTask());browserVirtualizedUser();
        });
      });
    }));
  });}
  void browserMutate(String code,Result result){evaluate(code,false,unused->later(()->inspectProduction(result),100));}
  void browserVirtualizedUser(){browserMutate("(()=>{window.__browserUser=document.querySelector('[data-message-id=\"current-question\"]');window.__browserUserNext=window.__browserUser.nextSibling;window.__browserUser.remove();return {virtualized:true};})()",missing->{
    check("Virtualizing one user message does not create a pending result check",missing.optBoolean("hasMessages")&&noResultTask());
    browserMutate("window.__browserMain.insertBefore(window.__browserUser,window.__browserUserNext);({restored:true})",restored->{
      check("Restoring a virtualized user message leaves website send ownership unchanged",restored.optBoolean("hasMessages")&&noResultTask());browserRoute("/",home->{
        check("An actual homepage route has no native send binding",home.optBoolean("composer")&&noResultTask());browserRoute("/c/allocated-fixture",allocated->{
          check("Website conversation allocation remains browser navigation without a result task",allocated.optString("url").endsWith("/c/allocated-fixture")&&noResultTask());
          browserRoute("/c/a-different-conversation",other->{check("A different official conversation creates no native result task",other.optString("url").endsWith("/c/a-different-conversation")&&noResultTask());browserSocketError();});
        });
      });
    });
  });}
  void browserRoute(String path,Result result){((FixtureView)session.web).semanticUrl=MainActivity.ORIGIN.substring(0,MainActivity.ORIGIN.length()-1)+path;browserMutate("history.replaceState(null,'',"+JSONObject.quote(path)+");({routeChanged:true})",result);}
  void browserSocketError(){browserMutate("document.querySelector('[data-message-id=\"old-answer-0\"] .markdown p').append(' Browser app server websocket closed');({historicalText:true})",ordinary->{
    check("Websocket error words in ordinary historical text remain ordinary browser content",ordinary.optString("error").isEmpty()&&!ordinary.optBoolean("websiteSocketClosed")&&noResultTask());
    browserMutate("document.querySelector('[data-message-id=\"old-answer-0\"]').parentElement.insertAdjacentHTML('beforeend','<div id=\"historical-socket-error\" role=\"alert\">Browser app server websocket failed <button aria-label=\"Retry\">Retry</button></div>');({historicalAlert:true})",historical->{
      check("A rendered historical socket alert does not become the current browser error",!historical.optBoolean("websiteSocketClosed")&&noResultTask());
      browserMutate("document.getElementById('historical-socket-error').remove();document.getElementById('current-answer').parentElement.insertAdjacentHTML('beforeend','<div id=\"socket-error\" role=\"alert\">Browser app server websocket closed</div>');({siteError:true})",closed->{
        check("Actual native inspection reports a current socket fault without monitoring a reply",closed.optBoolean("websiteSocketClosed")&&"website_socket_closed".equals(closed.optString("errorCode"))&&session.websiteConnectionIssue&&noResultTask());
        browserMutate("document.getElementById('socket-error').textContent='Browser app server websocket failed';({siteFailed:true})",failed->{
          check("A current websocket-failed alert remains a page error without a result task",failed.optBoolean("websiteSocketClosed")&&session.websiteConnectionIssue&&noResultTask());
          browserMutate("document.getElementById('socket-error').remove();({restored:true})",restored->{
            check("Clearing a page socket alert clears the browser error without creating a task",!restored.optBoolean("websiteSocketClosed")&&!session.websiteConnectionIssue&&noResultTask());
            evaluate("({sendCount:Number(document.getElementById('send-count').textContent),draft:document.getElementById('prompt-textarea').value,savedDraft:window.__browserDraft,cookie:document.cookie})",false,end->{
              check("SPA restoration and socket faults preserve typed draft, login and no-send state",end.optInt("sendCount")==0&&end.optString("draft").equals(end.optString("savedDraft"))&&end.optString("cookie").contains("session=synthetic-performance"));staleInspection();
            });
          });
        });
      });
    });
  });}
  void staleInspection(){attempt(()->{
    FixtureView view=(FixtureView)session.web;view.holdNextInspection=true;view.heldInspection=null;view.heldInspectionRaw=null;
    session.runDriver("web-inspect",new JSONObject(),result->attempt(()->{
      check("A real late Gecko inspection callback is cancelled after navigation changes",result.optBoolean("cancelled")&&!result.has("composer")&&noResultTask());manualRecoveryRaces();
    }));
    awaitHeldInspection(SystemClock.elapsedRealtime()+10000);
  });}
  void awaitHeldInspection(long expires){attempt(()->{
    FixtureView view=(FixtureView)session.web;
    if(view.heldInspection==null){if(SystemClock.elapsedRealtime()>expires)throw new IllegalStateException("Actual Gecko inspection callback was not captured");later(()->awaitHeldInspection(expires),50);return;}
    check("The late-callback race captures an actual readable Gecko response",J.parse(view.heldInspectionRaw).optBoolean("composer")&&J.parse(view.heldInspectionRaw).optBoolean("hasMessages"));
    evaluate("history.replaceState(null,'','/c/newer-browser-route');({path:location.pathname})",false,value->{
      check("The late-callback race changes the actual document route",value.optString("path").equals("/c/newer-browser-route"));
      view.semanticUrl=MainActivity.ORIGIN+"c/newer-browser-route";session.navigationEpoch++;
      android.webkit.ValueCallback<String> callback=view.heldInspection;String raw=view.heldInspectionRaw;view.heldInspection=null;view.heldInspectionRaw=null;callback.onReceiveValue(raw);
    });
  });}
  void manualRecoveryRaces()throws Exception{
    originalDriver=session.driver;((FixtureView)session.web).manualSnapshotDiagnostics=true;((FixtureView)session.web).quietTracking=true;
    session.driver="window.__pocketReadDriver(__ACTION__, __ARG__)";manualRace(1);
  }
  void manualRace(int index){attempt(()->{
    manualDraft=index==1?"manual recovery first draft":"manual recovery navigation draft";
    evaluate("document.getElementById('prompt-textarea').value="+JSONObject.quote(manualDraft)+";({draftSet:true})",false,unused->{
      session.handler.removeCallbacks(session.tick);manualEpoch=session.navigationEpoch;manualConnection=session.connectionEpoch;manualRoute=session.web.getUrl();
      FixtureView view=(FixtureView)session.web;view.pageStateReads=0;view.pageStateDraft="";view.manualSnapshotLast=new JSONObject();manualLoads=view.quietLoads;manualStops=view.quietStops;
      archiveEntered=new CountDownLatch(1);archiveRelease=new CountDownLatch(1);CountDownLatch entered=archiveEntered,release=archiveRelease;
      session.webStore.worker.execute(()->{entered.countDown();try{release.await(30,TimeUnit.SECONDS);}catch(InterruptedException error){Thread.currentThread().interrupt();}});
      waitArchiveWorker(index,SystemClock.elapsedRealtime()+10000);
    });
  });}
  void waitArchiveWorker(int index,long expires){attempt(()->{
    if(archiveEntered.getCount()!=0){if(SystemClock.elapsedRealtime()>expires)throw new IllegalStateException("Archive worker did not enter controlled pause");later(()->waitArchiveWorker(index,expires),50);return;}
    session.recoverWebsiteConnection();waitRecoverySnapshot(index,expires);
  });}
  void waitRecoverySnapshot(int index,long expires){attempt(()->{
    FixtureView view=(FixtureView)session.web;
    if(view.pageStateReads<1){if(SystemClock.elapsedRealtime()>expires)throw new IllegalStateException("Manual recovery did not capture the real Gecko page state");later(()->waitRecoverySnapshot(index,expires),50);return;}
    if(!session.websiteRecovering||!manualDraft.equals(view.pageStateDraft)){view.manualSnapshotFailure(index,manualDraft,manualEpoch,manualConnection);throw new IllegalStateException("Manual recovery snapshot failed before the controlled race");}
    if(index==1){evaluate("document.getElementById('prompt-textarea').value='new typing while archive waits';({draftChanged:true})",false,unused->{archiveRelease.countDown();waitRecoveryRace(index,SystemClock.elapsedRealtime()+10000);});}
    else{evaluate("history.replaceState(null,'','/c/navigation-during-archive');({path:location.pathname})",false,value->{
      check("The recovery race navigates the actual Gecko document while its archive is pending",value.optString("path").equals("/c/navigation-during-archive"));
      view.semanticUrl=MainActivity.ORIGIN+"c/navigation-during-archive";session.navigationEpoch++;archiveRelease.countDown();waitRecoveryRace(index,SystemClock.elapsedRealtime()+10000);
    });}
  });}
  void waitRecoveryRace(int index,long expires){attempt(()->{
    if(session.websiteRecovering){if(SystemClock.elapsedRealtime()>expires)throw new IllegalStateException("Manual recovery did not abort the stale operation");later(()->waitRecoveryRace(index,expires),50);return;}
    String route=manualRoute,captured=manualDraft;
    session.webStore.worker.execute(()->{
      JSONArray drafts=DraftArchive.get(session.context).list(route);boolean stored=false;for(int i=0;i<drafts.length();i++)if(captured.equals(drafts.optJSONObject(i).optString("body")))stored=true;
      final boolean persisted=stored;handler.post(()->attempt(()->{
        check(index==1?"Manual website recovery durably archives its captured draft before checking newer typing":"Manual website recovery durably archives the old route draft before rejecting a later navigation",persisted);
        evaluate("({draft:document.getElementById('prompt-textarea').value,sendCount:Number(document.getElementById('send-count').textContent),cookie:document.cookie})",false,end->{
          FixtureView view=(FixtureView)session.web;boolean noReload=view.quietLoads==manualLoads&&view.quietStops==manualStops&&session.navigationEpoch==manualEpoch+(index==2?1:0)&&session.connectionEpoch==manualConnection&&!session.navigating&&session.networkReady&&session.guard.allowed()&&noResultTask();
          check(index==1?"Typing during manual recovery prevents reload and preserves the newer browser draft":"Navigation during manual recovery prevents a stale reload and preserves the new route",noReload&&end.optString("draft").equals(index==1?"new typing while archive waits":captured)&&end.optInt("sendCount")==0&&end.optString("cookie").contains("session=synthetic-performance")&&view.pageStateReads==(index==1?2:1));
          if(index==1)manualRace(2);else{
            view.manualSnapshotDiagnostics=false;session.driver=originalDriver;session.invalidateConnection();
            evaluate("({draft:document.getElementById('prompt-textarea').value,sendCount:Number(document.getElementById('send-count').textContent),cookie:document.cookie})",false,after->{
              check("Connection invalidation preserves browser draft and login without result state",!session.networkReady&&session.guard.blocked&&noResultTask()&&after.optInt("sendCount")==0&&after.optString("draft").equals(captured)&&after.optString("cookie").contains("session=synthetic-performance"));
              session.networkReady=true;session.guard.setBlocked(false);originalOnlyBridge();
            });
          }
        });
      }));
    });
  });}
  // Additional scope checks run only after every existing capture, exact input
  // burst and recovery assertion. Neither input pacing nor its oracle changes.
  final String[] retiredActions={"poll","latest","fill","submit","model-open","model-select","message-regenerate-submit","page-navigate"};
  void originalOnlyBridge(){evaluate("(()=>{const e=document.getElementById('prompt-textarea');window.__originalOnlyWebsite={dom:document.documentElement.outerHTML,url:location.href,draft:e.value,start:e.selectionStart,end:e.selectionEnd,cookie:document.cookie,sent:Number(document.getElementById('send-count').textContent)};return {captured:true};})()",false,value->{
    check("Original-only bridge starts with the actual existing Gecko document",value.optBoolean("captured")&&session.web.enabled&&session.web.current.isOpen());originalOnlyAction(0);
  });}
  void originalOnlyAction(int index){
    if(index==retiredActions.length){evaluate("(()=>{const e=document.getElementById('prompt-textarea'),s=window.__originalOnlyWebsite;return {dom:s.dom===document.documentElement.outerHTML,url:s.url===location.href,draft:s.draft===e.value,selection:s.start===e.selectionStart&&s.end===e.selectionEnd,cookie:s.cookie===document.cookie,noSend:s.sent===Number(document.getElementById('send-count').textContent)&&s.sent===0};})()",false,value->{
      check("Retired native actions leave the entire website DOM, composer, selection, route and login unchanged",value.optBoolean("dom")&&value.optBoolean("url")&&value.optBoolean("draft")&&value.optBoolean("selection")&&value.optBoolean("cookie")&&value.optBoolean("noSend"));quietNavigation();
    });return;}
    String action=retiredActions[index];JSONObject args=J.obj("text","must remain unsent","prompt","must remain unsent","url",MainActivity.ORIGIN+"c/must-not-navigate");
    session.runDriver(action,args,nativeResult->attempt(()->{
      check("Public native bridge rejects retired action "+action,!nativeResult.optBoolean("ok")&&"请在 ChatGPT 原网页中操作".equals(nativeResult.optString("reason")));
      evaluate("window.__fixtureReadDriver("+JSONObject.quote(action)+","+args+")",false,direct->{
        check("Actual Gecko observation asset rejects retired action "+action,!direct.optBoolean("ok")&&"请在 ChatGPT 原网页中操作".equals(direct.optString("reason")));originalOnlyAction(index+1);
      });
    }));
  }
  void quietInspect(String path,Result result){
    ((FixtureView)session.web).semanticUrl=MainActivity.ORIGIN.substring(0,MainActivity.ORIGIN.length()-1)+path;
    evaluate("history.replaceState(null,'',"+JSONObject.quote(path)+");({path:location.pathname})",false,actual->{
      if(!path.equals(actual.optString("path")))throw new IllegalStateException("Browser navigation did not reach the actual Gecko SPA route");
      evaluate("window.__pocketReadDriver('web-inspect',{})",false,result);
    });
  }
  void quietNavigation()throws Exception{
    session.handler.removeCallbacks(session.tick);FixtureView view=(FixtureView)session.web;view.quietTracking=true;view.quietLoads=view.quietStops=0;session.inFlight=false;
    quietRoute(0);
  }
  void quietRoute(int index){
    String[] paths={"/c/quiet-A","/c/quiet-B","/auth/login","/","/c/quiet-A"};
    if(index==paths.length){quietEmptyHome();return;}
    quietInspect(paths[index],actual->{
      check("Actual browser route "+index+" does not create or restore a reply task",actual.optString("url").equals(((FixtureView)session.web).semanticUrl)&&noResultTask());
      String document=actual.optString("documentId");
      for(String type:new String[]{"intent","bound","uncertain","stop"}){
        session.webObserver.receive(J.obj("type",type,"url",((FixtureView)session.web).semanticUrl,"documentId",document,"confirmed",true,"userKey","id:current-question","prompt","must stay browser-owned"));
        check("Retired document event "+type+" on route "+index+" cannot create a result task",noResultTask());
      }
      quietRoute(index+1);
    });
  }
  void quietEmptyHome(){evaluate("(()=>{window.__quietMain=document.querySelector('main');window.__quietChildren=[...window.__quietMain.childNodes];window.__quietMain.replaceChildren();document.getElementById('composer').hidden=true;return {shell:true};})()",false,unused->quietInspect("/",shell->{
    check("An empty homepage hydration shell has no native result observation",!shell.optBoolean("composer")&&!shell.optBoolean("hasMessages")&&noResultTask());
    evaluate("document.getElementById('composer').hidden=false;document.getElementById('composer').insertAdjacentHTML('beforeend','<button id=\"stop-button\" data-testid=\"stop-button\" aria-label=\"Stop\">Stop</button>');({busyHome:true})",false,ready->quietInspect("/",busy->{
      check("A busy website composer remains browser-owned without a pending result task",busy.optBoolean("composer")&&busy.optBoolean("busy")&&noResultTask());
      evaluate("document.getElementById('stop-button').remove();({idleHome:true})",false,idle->quietInspect("/",home->{
        check("An interactive empty homepage creates no send completion state",home.optBoolean("composer")&&!home.optBoolean("hasMessages")&&!home.optBoolean("busy")&&noResultTask());
        evaluate("window.__quietMain.replaceChildren(...window.__quietChildren);({draft:document.getElementById('prompt-textarea').value,saved:window.__originalOnlyWebsite.draft,cookie:document.cookie,sent:Number(document.getElementById('send-count').textContent)})",false,end->{
          check("Browser navigation never stops, reloads, resubmits or changes draft and login",((FixtureView)session.web).quietStops==0&&((FixtureView)session.web).quietLoads==0&&end.optInt("sent")==0&&end.optString("draft").equals(end.optString("saved"))&&end.optString("cookie").contains("session=synthetic-performance")&&noResultTask());success();
        });
      }));
    }));
  }));}
  boolean appearanceChecked;
  void appearanceRegression(){
    final GeckoSession original=session.web.current;final long epoch=session.navigationEpoch;final String oldMode=AppAppearance.mode();
    final int loads=((FixtureView)session.web).quietLoads,stops=((FixtureView)session.web).quietStops;
    String snapshot="({draft:document.getElementById('prompt-textarea').value,cookie:document.cookie,url:location.href,marker:window.__appearanceDocument,dark:matchMedia('(prefers-color-scheme: dark)').matches})";
    evaluate("window.__appearanceDocument='appearance-document-'+Math.random();"+snapshot,false,before->{
      AppAppearance.choose(this,"dark");handler.postDelayed(()->evaluate(snapshot,false,night->{
        check("Dark appearance applies the official Gecko runtime preference",session.web.runtime.getSettings().getPreferredColorScheme()==GeckoRuntimeSettings.COLOR_SCHEME_DARK&&night.optBoolean("dark"));
        check("Dark appearance preserves actual document login draft and URL",night.optString("draft").equals(before.optString("draft"))&&night.optString("cookie").equals(before.optString("cookie"))&&night.optString("url").equals(before.optString("url"))&&night.optString("marker").equals(before.optString("marker")));
        AppAppearance.choose(this,"light");handler.postDelayed(()->evaluate(snapshot,false,day->{
          check("Light appearance applies the official Gecko runtime preference",session.web.runtime.getSettings().getPreferredColorScheme()==GeckoRuntimeSettings.COLOR_SCHEME_LIGHT&&!day.optBoolean("dark"));
          check("Theme roundtrip preserves the same browser session and navigation epoch",session.web.current==original&&session.navigationEpoch==epoch&&((FixtureView)session.web).quietLoads==loads&&((FixtureView)session.web).quietStops==stops);
          check("Light appearance preserves actual document login and unsent draft",day.optString("draft").equals(before.optString("draft"))&&day.optString("cookie").equals(before.optString("cookie"))&&day.optString("marker").equals(before.optString("marker")));
          AppAppearance.choose(this,oldMode);success();
        }),300);
      }),300);
    });
  }
  void success(){if(!appearanceChecked){appearanceChecked=true;appearanceRegression();return;}finished=true;event("report",J.obj("status","passed","actualAndroidExecution",true,"actualGeckoExecution",true,"actualAndroidTouchExecution",true,"browserObservationContract",2,"actualGeckoBrowserLifecycleExecution",true,"actualAppearanceRoundtrip",true,"actualInputImeSettled",inputImeSettled,"actualSingleInputBurst",true,"inputDiagnosticsEnabled",inputDiagnostics,"inputNativeDiagnosticsEnabled",inputNativeDiagnostics,"baselineSource",BASELINE,"checkCount",checkCount,"scope","Actual GeckoView 157, real extension payload and DOM work: immutable historical polling workload compared with current browser readiness inspection, 12 samples each. Original Android scroll and exact keyboard input retained; 240 historical messages and 105k current reply. Explicit transcript/file metadata, durable offline snapshots, browser navigation, real socket surfaces, delayed actual bridge callback and manual-recovery archive races; no send-result tasks, real account or external site. RAF/Choreographer remain descriptive, no cross-device FPS threshold.","measurements",J.arr(baselineMetrics,currentMetrics)));}
  String telemetryInstall(){return "(()=>{const data={readChars:0,readCalls:0,clones:0,started:performance.now(),rafCount:0,rafSum:0,rafMax:0,rafOver32:0,previous:0};"+
    "for(const [prototype,key] of [[HTMLElement.prototype,'innerText'],[Node.prototype,'textContent'],[Node.prototype,'nodeValue']]){const original=Object.getOwnPropertyDescriptor(prototype,key);if(original?.get&&original.configurable)Object.defineProperty(prototype,key,{...original,get(){const value=original.get.call(this);data.readCalls++;if(typeof value==='string')data.readChars+=value.length;return value;}});}"+
    "const clone=Node.prototype.cloneNode;Node.prototype.cloneNode=function(...args){data.clones++;return clone.apply(this,args);};"+
    "const originalCookie=document.cookie,originalDraft=document.getElementById('prompt-textarea').value;"+
    "const frame=time=>{if(data.previous){const gap=time-data.previous;data.rafCount++;data.rafSum+=gap;data.rafMax=Math.max(data.rafMax,gap);if(gap>32)data.rafOver32++;}data.previous=time;requestAnimationFrame(frame);};requestAnimationFrame(frame);"+
    "window.__fixtureTelemetry=()=>({readChars:data.readChars,readCalls:data.readCalls,clones:data.clones,elapsedMs:performance.now()-data.started,raf:{frames:data.rafCount,averageGapMs:data.rafCount?data.rafSum/data.rafCount:0,maxGapMs:data.rafMax,gapsOver32Ms:data.rafOver32},draftPreserved:document.getElementById('prompt-textarea').value===originalDraft,cookiePreserved:document.cookie===originalCookie&&document.cookie.includes('session=synthetic-performance'),sendCount:Number(document.getElementById('send-count').textContent),observation:window.__pocketWebPerformance.stats()});"+
    "const meta=window.__pocketWebPerformance.meta();return {documentId:meta.documentId,revision:meta.revision,observation:window.__pocketWebPerformance.stats()};})()";}
  static final class FrameSample implements Choreographer.FrameCallback {
    boolean active;long previous,count,sum,max,over32;
    void start(){previous=count=sum=max=over32=0;active=true;Choreographer.getInstance().postFrameCallback(this);}
    @Override public void doFrame(long time){if(!active)return;if(previous>0){long gap=time-previous;count++;sum+=gap;max=Math.max(max,gap);if(gap>32000000L)over32++;}previous=time;Choreographer.getInstance().postFrameCallback(this);}
    JSONObject stop(){active=false;Choreographer.getInstance().removeFrameCallback(this);return J.obj("frames",count,"averageGapMs",count>0?sum/1000000.0/count:0,"maxGapMs",max/1000000.0,"gapsOver32Ms",over32);}
  }
  @Override protected void onDestroy(){finishScrollDiagnostics("destroyed");stopInputTrace();frames.stop();if(archiveRelease!=null)archiveRelease.countDown();handler.removeCallbacksAndMessages(null);if(session!=null)session.handler.removeCallbacks(session.tick);super.onDestroy();}
}
