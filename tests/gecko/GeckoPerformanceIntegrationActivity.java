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
  ChatSession session;String variant,driver,performanceSource;JSONObject before,known,firstFull,baselineMetrics,currentMetrics,productionJob;
  int checkCount,samples,inputFocusSamples,directDeferredSamples,nativeDeferredSamples;boolean finished,inputRequested,directDeferralChecked,nativeDeferralChecked;long deadline,payloadBytes,payloadChars,callbackMs,scriptChars;
  String originalDriver,manualDraft,inputDraft;JSONObject manualJob;long manualEpoch,manualConnection;
  String inputReadinessKey="";long inputReadySince;int inputTraceOffset,inputReadinessSequence;boolean inputImeSettled;
  GeckoInputTrace nativeInputTrace;GeckoInputTrace.Buffered bufferedInputTrace;boolean inputDiagnostics,inputNativeDiagnostics;
  CountDownLatch archiveEntered,archiveRelease;
  @Override protected void attachBaseContext(Context c){super.attachBaseContext(new ProfileContext(c,Profiles.processSlot()));}
  static final class FixtureView extends GeckoWebView {
    boolean semanticRoute,inspectPending,inputTracing,quietTracking;JSONObject productionPoll,productionInspect;int pageStateReads,stableBeforeInspectedPoll=-1,completionBeforeInspectedPoll=-1,inputEvaluateSequence,quietStops,quietLoads;String pageStateDraft="",navigationError="",semanticUrl=MainActivity.ORIGIN+"c/performance-fixture";
    FixtureView(Context c,ChatSession owner){super(c,owner);}
    @Override public void stopLoading(){if(quietTracking)quietStops++;super.stopLoading();}
    @Override public void loadUrl(String url){if(quietTracking)quietLoads++;super.loadUrl(url);}
    @Override public String getUrl(){return semanticRoute?semanticUrl:super.getUrl();}
    @Override public void evaluateJavascript(String code,android.webkit.ValueCallback<String> callback){
      int inputSequence=inputTracing?inputEvaluateSequence++:-1;
      if(inputSequence>=0)inputEvaluation("begin",inputSequence,code);
      if(semanticRoute&&inspectPending&&code.contains("window.__pocketReadDriver(\"poll\",")){inspectPending=false;stableBeforeInspectedPoll=owner.stableTicks;completionBeforeInspectedPoll=owner.webObserver.completionSamples;}
      super.evaluateJavascript(code,raw->{
      if(inputSequence>=0)inputEvaluation("end",inputSequence,code);
      if(semanticRoute&&code.contains("window.__pocketReadDriver(\"poll\","))productionPoll=J.parse(raw);
      if(semanticRoute&&code.contains("window.__pocketReadDriver(\"web-inspect\","))productionInspect=J.parse(raw);
      if(semanticRoute&&code.contains("window.__pocketReadDriver(\"page-state\",")){pageStateReads++;pageStateDraft=J.parse(raw).optString("draft");}
      if(callback!=null)callback.onReceiveValue(raw);
    });}
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
  void event(String kind,JSONObject value){Log.i("PocketGeckoPerformance",J.obj("kind",kind,"value",value).toString());}
  void check(String name,boolean pass){checkCount++;event("check",J.obj("name",name,"pass",pass));if(!pass)throw new IllegalStateException(name);}
  void fail(Exception error){if(finished)return;finished=true;frames.stop();if(archiveRelease!=null)archiveRelease.countDown();stopInputTrace(()->event("report",J.obj("status","failed","actualAndroidExecution",true,"actualGeckoExecution",true,"inputDiagnosticsEnabled",inputDiagnostics,"inputNativeDiagnosticsEnabled",inputNativeDiagnostics,"checkCount",checkCount,"error",error.toString())));}
  String asset(String name)throws Exception{try(InputStream in=getAssets().open(name)){return J.text(in,512*1024);}}
  @Override public void onCreate(Bundle saved){super.onCreate(saved);attempt(()->{
    if(!getPackageName().endsWith(".test"))throw new SecurityException("Only isolated integration package may run this fixture");
    inputDiagnostics=getIntent().getBooleanExtra("inputDiagnostics",false);
    inputNativeDiagnostics=getIntent().getBooleanExtra("inputNativeDiagnostics",false);
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
    String guard="location.protocol !== 'https:' || location.hostname !== 'chatgpt.com'";
    if(!driver.contains(guard))throw new IllegalStateException("Unexpected production origin guard");
    // Adapt only the HTTPS origin in this test copy. The shipped driver retains its original guard.
    driver=driver.replace(guard,"location.protocol !== 'http:' || location.hostname !== '127.0.0.1' || location.port !== '8767'");
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
  JSONObject args(){JSONObject value=J.obj("kind","web","confirmed",true,"userKey","id:current-question","prompt","bound performance prompt", "confirmedUrl",ORIGIN+PATH+"?variant="+variant,"expectedUrl",ORIGIN+PATH+"?variant="+variant,"export",true,"lightObservation",true);if("current".equals(variant))try{value.put("incrementalObservation",true);}catch(Exception ignored){}return value;}
  void poll(JSONObject arg,boolean measured,Result result){pollObserved(arg,measured,result,SystemClock.elapsedRealtime()+10000);}
  boolean deferredBodyless(JSONObject value){return !value.optBoolean("contentObserved")&&!value.optBoolean("contentUnchanged")&&!value.has("markdown")&&!value.has("text")&&!value.has("prompt");}
  void pollObserved(JSONObject arg,boolean measured,Result result,long expires){
    evaluate("window.__fixtureReadDriver('poll',"+arg+")",measured,value->{
      if(!value.optBoolean("captureDeferred")){result.accept(value);return;}
      boolean bodyless=deferredBodyless(value);directDeferredSamples++;
      if(!directDeferralChecked){check("Actual Gecko idle deferral transfers no partial final body",bodyless);directDeferralChecked=true;}
      else if(!bodyless)throw new IllegalStateException("A deferred actual Gecko poll carried completion content");
      if(SystemClock.elapsedRealtime()>expires)throw new IllegalStateException("Actual Gecko idle capture did not become observable");
      // Preserve the real interaction clock and requestIdleCallback. Re-read
      // the same driver arguments until its actual complete capture is ready.
      later(()->pollObserved(arg,measured,result,expires),80);
    });
  }
  void verifyNativeDeferral(JSONObject value)throws Exception{
    nativeDeferredSamples++;
    boolean safe=deferredBodyless(value)&&session.pending==productionJob&&session.prefs.contains("pending")&&
      J.parse(session.prefs.getString("pending","{}")).optString("id").equals(productionJob.optString("id"))&&
      session.stableTicks==0&&session.webObserver.completionSamples==0&&
      !"completed".equals(session.deliveries.get(productionJob.optString("id")).optString("state"));
    if(!nativeDeferralChecked){check("Actual native idle deferral preserves the persisted task with zero completion samples",safe);nativeDeferralChecked=true;}
    else if(!safe)throw new IllegalStateException("A deferred native capture lost its task or accumulated terminal samples");
  }
  void snapshot(JSONObject arg,Result result){evaluate("window.__fixtureReadDriver('web-transcript',"+arg+")",false,result);}
  void sample(){attempt(()->{
    poll(args(),true,value->{
      check(variant+" busy sample "+samples+" stays bound and never completes",value.optBoolean("busy")&&value.optBoolean("submitted")&&!value.optBoolean("bindingLost"));
      if("current".equals(variant))check("Current streaming sample "+samples+" transfers only metadata",!value.optBoolean("contentObserved")&&value.optBoolean("hasReply")&&!value.has("markdown")&&!value.has("text")&&!value.has("prompt"));
      else check("Baseline sample "+samples+" actually transfers its long body",value.optString("markdown").length()>105000&&value.optString("text").length()>105000);
      int done=++samples;
      if(done==4||done==8){evaluate("document.getElementById('long-body').append(' streamed-"+done+"');({mutated:true})",false,v->later(done==4?this::scrollGesture:this::nextSample,80));return;}
      later(this::nextSample,80);
    });
  });}
  void scrollGesture(){evaluate("({scrollTop:document.scrollingElement.scrollTop})",false,beforeScroll->{
    int[] position=new int[2];session.web.getLocationOnScreen(position);int x=position[0]+session.web.getWidth()/2;
    event("gestureNeeded",J.obj("id",variant+"-scroll","action","scroll","x",x,"startY",position[1]+session.web.getHeight()*3/4,"endY",position[1]+session.web.getHeight()/4));
    waitScroll(beforeScroll.optDouble("scrollTop"),SystemClock.elapsedRealtime()+20000);
  });}
  void waitScroll(double previous,long expires){evaluate("({scrollTop:document.scrollingElement.scrollTop})",false,afterScroll->{
    if(afterScroll.optDouble("scrollTop")<=previous){if(SystemClock.elapsedRealtime()>expires)throw new IllegalStateException("Actual Android scroll gesture did not reach Gecko");later(()->waitScroll(previous,expires),100);return;}
    check(variant+" accepts an actual Android scroll while reply observation is active",true);later(this::nextSample,80);
  });}
  void nextSample(){if(samples<12)sample();else measured();}
  void measured(){attempt(()->{
    JSONObject nativeFrames=frames.stop();evaluate("window.__fixtureTelemetry()",false,telemetry->{
      JSONObject metrics=J.obj("variant",variant,"samples",samples,"bridgeResponseBytes",payloadBytes,"bridgeResponseChars",payloadChars,"bridgeScriptChars",scriptChars,"evaluateCallbackMs",callbackMs,"domReadChars",telemetry.optLong("readChars"),"domReadCalls",telemetry.optLong("readCalls"),"cloneCalls",telemetry.optLong("clones"),"elapsedJsMs",telemetry.optDouble("elapsedMs"),"raf",telemetry.optJSONObject("raf"),"androidChoreographer",nativeFrames,"observationBefore",before.optJSONObject("observation"),"observationAfter",telemetry.optJSONObject("observation"));
      event("measurement",metrics);
      check(variant+" preserves the draft, synthetic session cookie and send count",telemetry.optBoolean("draftPreserved")&&telemetry.optBoolean("cookiePreserved")&&telemetry.optInt("sendCount")==0);
      if("baseline".equals(variant)){baselineMetrics=metrics;load("current");return;}
      currentMetrics=metrics;
      check("Actual Gecko streaming bridge payload is reduced by at least 95 percent",payloadBytes*20<baselineMetrics.optLong("bridgeResponseBytes"));
      check("Actual growing-body DOM read work is reduced by at least 95 percent",telemetry.optLong("readChars")*20<baselineMetrics.optLong("domReadChars"));
      JSONObject initial=before.optJSONObject("observation"),after=telemetry.optJSONObject("observation");
      check("Streaming metadata never rebuilds markdown or files",after.optLong("derivedBuilt")==initial.optLong("derivedBuilt"));
      check("Text mutations preserve the cached message topology",after.optLong("messageListsBuilt")==initial.optLong("messageListsBuilt"));
      terminal();
    });
  });}
  void terminal(){
    evaluate("document.getElementById('stop-button').remove();({stopped:true})",false,v->later(()->snapshot(J.obj("documentId",before.optString("documentId"),"revision",before.optLong("revision")),changed->{
      check("Two streaming mutations rebuild only the current transcript entry",changed.optJSONArray("changes")!=null&&changed.optJSONArray("changes").length()==1&&changed.optJSONArray("changes").optJSONObject(0).optString("id").equals("id:current-answer"));
      evaluate("({stats:window.__pocketWebPerformance.stats()})",false,stats->poll(args(),false,full->{
        firstFull=full;String body=full.optString("markdown");
        check("First terminal capture keeps the entire 105k reply, both stream tails, code and file",full.optBoolean("terminal")&&!full.optBoolean("busy")&&full.optBoolean("contentObserved")&&full.optBoolean("hasFiles")&&body.length()>105000&&body.startsWith("preserved reply line ".repeat(5000).trim())&&body.contains("streamed-4 streamed-8")&&body.contains("```js\nconst keep = 1;")&&body.contains("result.csv"));
        evaluate("({stats:window.__pocketWebPerformance.stats()})",false,after->{
          check("Terminal poll reuses the just-built transcript markdown and file representation",after.optJSONObject("stats").optLong("derivedBuilt")==stats.optJSONObject("stats").optLong("derivedBuilt"));
          JSONObject gate=gatePoll(full);check("A first actual terminal body cannot complete prematurely",!session.webObserver.mayComplete(gateJob(),gate));
          known=args();known.put("knownReplyKey",full.optString("replyKey")).put("knownReplyContentRevision",full.optString("replyContentRevision"));
          later(()->stable(1),1100);
        });
      }));
    }),100));
  }
  JSONObject gateJob(){return J.obj("kind","web","confirmed",true,"id","controlled-gecko-performance","userKey","id:current-question","confirmedUrl",MainActivity.ORIGIN+"c/performance-fixture");}
  JSONObject gatePoll(JSONObject value)throws Exception{
    // Only adapt the fixture URL for the production HTTPS-route terminal gate.
    // The body and revision came from the actual Gecko result, never a synthetic completion string.
    return new JSONObject(value.toString()).put("url",MainActivity.ORIGIN+"c/performance-fixture").put("markdown",firstFull.optString("markdown")).put("hasFiles",firstFull.optBoolean("hasFiles"));
  }
  void stable(int index){poll(known,false,same->{
    check("Stable terminal sample "+index+" omits the 105k body using the exact content revision",same.optBoolean("contentUnchanged")&&same.optBoolean("contentObserved")&&!same.has("markdown")&&!same.has("text")&&same.optString("replyContentRevision").equals(firstFull.optString("replyContentRevision")));
    boolean complete=session.webObserver.mayComplete(gateJob(),gatePoll(same));
    check(index==1?"The second terminal sample remains incomplete":"The third stable actual body is accepted after at least two seconds",complete==(index==2));
    if(index==1)later(()->stable(2),1100);else mutateAfterTerminal();
  });}
  void mutateAfterTerminal(){evaluate("document.getElementById('long-body').append(' final-tail-after-done');({mutated:true})",false,v->later(()->poll(known,false,full->{
    check("A post-terminal mutation expires the omitted-body capture",!full.optBoolean("contentUnchanged")&&full.optString("markdown").contains("final-tail-after-done")&&!full.optString("replyContentRevision").equals(firstFull.optString("replyContentRevision")));
    firstFull=full;check("A changed terminal body resets the production stable-completion gate",!session.webObserver.mayComplete(gateJob(),gatePoll(full)));
    known.put("knownReplyKey",full.optString("replyKey")).put("knownReplyContentRevision",full.optString("replyContentRevision"));
    evaluate("(()=>{const previous=document.getElementById('current-answer'),next=previous.cloneNode(true);next.querySelector('#long-body').textContent='replacement with same stable message ID';previous.replaceWith(next);return {replaced:true};})()",false,w->later(()->poll(known,false,replaced->{
      check("Reusing a stable message ID on a new node cannot retain the previous body",replaced.optString("replyKey").equals(full.optString("replyKey"))&&!replaced.optBoolean("contentUnchanged")&&replaced.optString("markdown").startsWith("replacement with same stable message ID")&&!replaced.optString("replyContentRevision").equals(full.optString("replyContentRevision")));
      known.put("knownReplyContentRevision",replaced.optString("replyContentRevision"));
      evaluate("(()=>{const file=document.getElementById('generated-file');file.download='new-result.csv';file.textContent='new-result.csv';return {fileChanged:true};})()",false,x->later(()->poll(known,false,file->{
        check("Generated file changes invalidate terminal markdown and attachment metadata",!file.optBoolean("contentUnchanged")&&file.optBoolean("hasFiles")&&file.optString("markdown").contains("new-result.csv"));
        siblingFiles(file);
      }),100));
    }),100));
  }),100));}
  void remember(JSONObject poll)throws Exception{known.put("knownReplyKey",poll.optString("replyKey")).put("knownReplyContentRevision",poll.optString("replyContentRevision"));}
  JSONObject snapshotCursor(JSONObject snapshot){return J.obj("documentId",snapshot.optString("documentId"),"revision",snapshot.optLong("revision"));}
  JSONObject currentEntry(JSONObject snapshot){JSONArray rows=snapshot.optJSONArray("changes");for(int i=0;rows!=null&&i<rows.length();i++){JSONObject entry=rows.optJSONObject(i);if(entry!=null&&"id:current-answer".equals(entry.optString("id")))return entry;}return new JSONObject();}
  boolean download(JSONObject entry,String name){JSONArray files=entry.optJSONArray("downloads");for(int i=0;files!=null&&i<files.length();i++)if(name.equals(files.optJSONObject(i).optString("name")))return true;return false;}
  void siblingFiles(JSONObject prior)throws Exception{
    remember(prior);evaluate("document.getElementById('current-answer').parentElement.insertAdjacentHTML('beforeend','<a id=\"sibling-file\" download=\"sibling.csv\" href=\"/backend-api/files/sibling\">sibling.csv</a>');({fileAdded:true})",false,v->later(()->poll(known,false,added->{
      check("Sibling generated file cards invalidate the actual Gecko reply revision",!added.optBoolean("contentUnchanged")&&added.optBoolean("hasFiles")&&!added.optString("replyContentRevision").equals(prior.optString("replyContentRevision")));
      snapshot(new JSONObject(),withFile->{
        check("Sibling file cards appear in incremental transcript downloads",download(currentEntry(withFile),"sibling.csv"));remember(added);
        evaluate("(()=>{const file=document.getElementById('sibling-file');file.download='renamed-sibling.csv';file.textContent='renamed-sibling.csv';return {fileRenamed:true};})()",false,w->later(()->poll(known,false,renamed->{
          snapshot(snapshotCursor(withFile),withRenamed->{
            check("Renaming a sibling file card refreshes actual Gecko metadata and transcript downloads",!renamed.optBoolean("contentUnchanged")&&!renamed.optString("replyContentRevision").equals(added.optString("replyContentRevision"))&&download(currentEntry(withRenamed),"renamed-sibling.csv")&&!download(currentEntry(withRenamed),"sibling.csv"));remember(renamed);
            evaluate("document.getElementById('sibling-file').remove();({fileRemoved:true})",false,x->later(()->poll(known,false,removed->{
              snapshot(snapshotCursor(withRenamed),withoutFile->{
                check("Removing a sibling file card invalidates the actual Gecko reply metadata",!removed.optBoolean("contentUnchanged")&&!removed.optString("replyContentRevision").equals(renamed.optString("replyContentRevision"))&&!download(currentEntry(withoutFile),"renamed-sibling.csv")&&download(currentEntry(withoutFile),"new-result.csv"));remember(removed);detachedBody(withoutFile);
              });
            }),100));
          });
        }),100));
      });
    }),100));
  }
  void detachedBody(JSONObject cursor){evaluate("(()=>{const body=document.querySelector('#current-answer > .markdown');window.__fixtureDetachedBody=body;body.remove();return {detached:true};})()",false,v->later(()->{
    evaluate("(()=>{const body=window.__fixtureDetachedBody;body.querySelector('#long-body').textContent='detached existing body edited while outside the document';document.getElementById('current-answer').append(body);delete window.__fixtureDetachedBody;return {reattached:true};})()",false,w->later(()->poll(known,false,reinserted->{
      snapshot(snapshotCursor(cursor),after->{
        String expected="detached existing body edited while outside the document";
        check("Reattaching an edited cached body refreshes actual Gecko terminal text and transcript",!reinserted.optBoolean("contentUnchanged")&&reinserted.optString("markdown").startsWith(expected)&&currentEntry(after).optString("text").startsWith(expected));
        evaluate("document.getElementById('current-copy').remove();({copyRemoved:true})",false,x->later(()->poll(args(),false,old->{
          check("Earlier response copy controls cannot complete the current reply",!old.optBoolean("terminal"));
          evaluate("window.__fixtureTelemetry()",false,end->{check("Semantic checks preserve the synthetic login, draft and no-send invariant",end.optBoolean("draftPreserved")&&end.optBoolean("cookiePreserved")&&end.optInt("sendCount")==0);productionLifecycle();});
        }),100));
      });
    }),100));
  },100));}
  void productionLifecycle(){attempt(()->{
    String canonical=MainActivity.ORIGIN+"c/performance-fixture",actual=ORIGIN+PATH+"?variant=current";
    String code="(()=>{document.getElementById('long-body').textContent='preserved reply line '.repeat(5000)+' Java retained final tail';"+
      "document.getElementById('current-answer').parentElement.insertAdjacentHTML('beforeend','<button id=\"current-copy\" data-testid=\"copy-turn-action-button\" aria-label=\"Copy response\">Copy</button>');"+
      "document.getElementById('composer').insertAdjacentHTML('beforeend','<button id=\"stop-button\" data-testid=\"stop-button\" aria-label=\"Stop\">Stop</button>');"+
      "window.__pocketReadDriver=(action,arg)=>{const mapped={...arg};for(const key of ['confirmedUrl','expectedUrl'])if(mapped[key]==="+JSONObject.quote(canonical)+")mapped[key]="+JSONObject.quote(actual)+";"+
      "const value=window.__fixtureReadDriver(action,mapped);if(value?.url)value.url="+JSONObject.quote(canonical)+";return value;};return {adapted:true};})()";
    evaluate(code,false,ready->{
      ((FixtureView)session.web).semanticRoute=true;session.state=J.obj("composer",true);session.navigating=false;session.navigationFailed=false;session.webMirror.reset();session.entries=new JSONArray();session.conversation=canonical;
      String id=session.deliveries.begin(canonical,"bound performance prompt",new JSONArray(),"web",null);
      productionJob=J.obj("id",id,"kind","web","confirmed",true,"userKey","id:current-question","prompt","bound performance prompt","confirmedUrl",canonical,"expectedUrl",canonical,"export",true,"startedAt",System.currentTimeMillis());
      session.pending=productionJob;session.activeDeliveryId=id;session.prefs.edit().putString("pending",productionJob.toString()).commit();session.stableTicks=0;session.stableReply="";
      later(()->productionSample(0),100);
    });
  });}
  void productionSample(int stage){productionSample(stage,SystemClock.elapsedRealtime()+10000);}
  void productionSample(int stage,long expires){attempt(()->{
    session.inFlight=true;long serial=++session.syncRun;((FixtureView)session.web).productionPoll=null;
    session.pollSync(session.navigationEpoch,serial,true);
    awaitProduction(stage,expires);
  });}
  void awaitProduction(int stage,long expires){attempt(()->{
    if(session.inFlight){if(SystemClock.elapsedRealtime()>expires)throw new IllegalStateException("Production pollSync completion timeout at stage "+stage);later(()->awaitProduction(stage,expires),50);return;}
    JSONObject result=((FixtureView)session.web).productionPoll;if(result==null)throw new IllegalStateException("Production ChatSession did not use the actual Gecko observation runtime");
    if(stage==0){
      check("Production ChatSession keeps a streaming task pending without retaining a partial body",session.pending==productionJob&&!result.optBoolean("contentObserved")&&session.observedReplyMarkdown.isEmpty());
      evaluate("document.getElementById('stop-button').remove();({stopped:true})",false,v->later(()->productionSample(1),100));return;
    }
    if(result.optBoolean("captureDeferred")){
      verifyNativeDeferral(result);
      if(SystemClock.elapsedRealtime()>expires)throw new IllegalStateException("Production idle capture timeout at stage "+stage);
      later(()->productionSample(stage,expires),80);return;
    }
    if(stage==1){
      check("Production first terminal capture retains the entire actual Gecko body",session.pending==productionJob&&session.observedReplyMarkdown.length()>105000&&session.observedReplyMarkdown.contains("Java retained final tail")&&result.has("markdown"));
      String savedJob=session.observedReplyJob,savedUrl=session.observedReplyUrl;
      session.observedReplyJob="a different task";check("A different task cannot request reuse of the captured reply",!session.webPollArguments(productionJob).has("knownReplyContentRevision"));session.observedReplyJob=savedJob;
      session.observedReplyUrl=MainActivity.ORIGIN+"c/a-different-route";check("A different route cannot request reuse of the captured reply",!session.webPollArguments(productionJob).has("knownReplyContentRevision"));session.observedReplyUrl=savedUrl;
      later(()->productionSample(2),1100);return;
    }
    check("Production terminal sample "+stage+" uses actual metadata-only bridge output",result.optBoolean("contentUnchanged")&&!result.has("markdown")&&!result.has("text"));
    check("Production terminal sample "+stage+" restores the complete cached body in Java",session.observedReplyMarkdown.length()>105000&&session.observedReplyMarkdown.contains("Java retained final tail")&&session.stableReply.equals(session.observedReplyMarkdown));
    if(stage==2){check("Production second terminal sample still preserves the persisted pending operation",session.pending==productionJob&&session.prefs.contains("pending"));later(()->productionSample(3),1100);return;}
    check("Production stable lightweight samples finish and persist the actual reply task",session.pending==null&&!session.prefs.contains("pending")&&"completed".equals(session.deliveries.get(productionJob.optString("id")).optString("state")));
    check("Production completion keeps the full 242-message transcript",session.entries.length()==242&&session.entries.optJSONObject(241).optString("text").length()>105000&&session.entries.optJSONObject(241).optString("text").contains("Java retained final tail"));
    long storageDeadline=SystemClock.elapsedRealtime()+10000;later(()->waitStored(storageDeadline),100);
  });}
  void waitStored(long expires){session.webStore.worker.execute(()->{
    JSONArray saved=session.cache.messages(MainActivity.ORIGIN+"c/performance-fixture");handler.post(()->attempt(()->{
      if(saved.length()!=242){if(SystemClock.elapsedRealtime()>expires)throw new IllegalStateException("Completed transcript was not durably stored");later(()->waitStored(expires),100);return;}
      check("The complete final body is durably saved by the production transcript worker",saved.optJSONObject(241).optString("text").length()>105000&&saved.optJSONObject(241).optString("text").contains("Java retained final tail"));
      evaluate("window.__fixtureTelemetry()",false,end->{check("Production completion preserves the document login, unsent draft and no-send invariant",end.optBoolean("draftPreserved")&&end.optBoolean("cookiePreserved")&&end.optInt("sendCount")==0);inputGesture();});
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
    check("Actual user input neither sends a message nor changes the synthetic login",value.optInt("sendCount")==0&&value.optString("cookie").contains("session=synthetic-performance"));stopInputTrace(this::bindingLifecycle);
  });}
  // Run after both immutable measurements and all existing capture/gesture checks.
  // Preserve real SPA paths when adapting only the official host for the loopback copy.
  void bindingLifecycle(){attempt(()->{
    ((FixtureView)session.web).semanticUrl=MainActivity.ORIGIN+"c/binding-fixture";
    String code="(()=>{history.replaceState(null,'','/c/binding-fixture');window.__bindingDraft=document.getElementById('prompt-textarea').value;"+
      "window.__pocketReadDriver=(action,arg)=>{const mapped={...arg};for(const key of ['confirmedUrl','expectedUrl'])if(mapped[key]){const address=new URL(mapped[key]);if(address.origin==="+JSONObject.quote(android.net.Uri.parse(MainActivity.ORIGIN).getScheme()+"://"+android.net.Uri.parse(MainActivity.ORIGIN).getHost())+")mapped[key]="+JSONObject.quote(ORIGIN)+"+address.pathname+address.search+address.hash;}"+
      "const value=window.__fixtureReadDriver(action,mapped);if(value?.url)value.url="+JSONObject.quote(MainActivity.ORIGIN.substring(0,MainActivity.ORIGIN.length()-1))+"+new URL(value.url).pathname;return value;};return {adapted:true};})()";
    evaluate(code,false,ready->{
      String route=((FixtureView)session.web).semanticUrl,id=session.deliveries.begin(route,"bound performance prompt",new JSONArray(),"web",null);
      productionJob=J.obj("id",id,"kind","web","confirmed",true,"userKey","id:current-question","prompt","bound performance prompt","confirmedUrl",route,"expectedUrl",route,"export",true,"startedAt",System.currentTimeMillis());
      session.pending=productionJob;session.activeDeliveryId=id;session.prefs.edit().putString("pending",productionJob.toString()).commit();session.stableReply="";session.stableTicks=0;
      later(()->bindingPoll(first->{
        check("Binding regression starts with the actual full reply and one incomplete native terminal sample",first.optBoolean("submitted")&&session.pending==productionJob&&session.webObserver.completionSamples==1&&session.observedReplyMarkdown.length()>105000);
        bindingEmptyMain();
      }),100);
    });
  });}
  void bindingPoll(Result result){bindingPoll(result,SystemClock.elapsedRealtime()+10000);}
  void bindingPoll(Result result,long expires){attempt(()->{
    session.handler.removeCallbacks(session.tick);session.inFlight=true;long serial=++session.syncRun;((FixtureView)session.web).productionPoll=null;
    session.pollSync(session.navigationEpoch,serial,true);awaitBinding(result,expires);
  });}
  void bindingInspect(Result result){attempt(()->{
    session.handler.removeCallbacks(session.tick);session.inFlight=false;((FixtureView)session.web).productionPoll=null;((FixtureView)session.web).productionInspect=null;((FixtureView)session.web).inspectPending=true;
    session.sync();awaitBinding(result,SystemClock.elapsedRealtime()+10000);
  });}
  void awaitBinding(Result result,long expires){attempt(()->{
    if(session.inFlight){if(SystemClock.elapsedRealtime()>expires)throw new IllegalStateException("Binding regression production poll timeout");later(()->awaitBinding(result,expires),50);return;}
    JSONObject poll=((FixtureView)session.web).productionPoll;if(poll==null)throw new IllegalStateException("Binding regression did not execute the real Gecko driver");
    if(poll.optBoolean("captureDeferred")){
      verifyNativeDeferral(poll);
      if(SystemClock.elapsedRealtime()>expires)throw new IllegalStateException("Binding regression idle capture timeout");
      later(()->bindingPoll(result,expires),80);return;
    }
    result.accept(poll);
  });}
  boolean awaitingBinding(JSONObject value){return value.optBoolean("bindingPending")&&!value.optBoolean("bindingLost")&&!value.optBoolean("otherQuestion")&&!value.optBoolean("submitted")&&!value.optBoolean("terminal")&&!value.optBoolean("contentObserved")&&session.pending==productionJob&&session.prefs.contains("pending")&&!session.status.contains("对话已改变")&&session.stableTicks==0&&session.webObserver.completionSamples==0;}
  void bindingMutate(String code,Result result){evaluate(code,false,unused->later(()->bindingPoll(result),100));}
  void bindingEmptyMain(){bindingMutate("(()=>{window.__bindingMain=document.querySelector('main');window.__bindingChildren=[...window.__bindingMain.childNodes];window.__bindingMain.replaceChildren();return {detached:true};})()",missing->{
    check("Same-route empty DOM waits without losing the confirmed task or accumulating terminal samples",awaitingBinding(missing));
    bindingMutate("window.__bindingMain.replaceChildren(...window.__bindingChildren);({restored:true})",restored->{
      check("Restoring the original message key and prompt rebinds the real native task",restored.optBoolean("submitted")&&!restored.optBoolean("bindingPending")&&!restored.optBoolean("bindingLost")&&"id:current-question".equals(restored.optString("userKey"))&&session.pending==productionJob);
      bindingVirtualizedUser();
    });
  });}
  void bindingVirtualizedUser(){bindingMutate("(()=>{window.__bindingUser=document.querySelector('[data-message-id=\"current-question\"]');window.__bindingUserNext=window.__bindingUser.nextSibling;window.__bindingUser.remove();return {virtualized:true};})()",missing->{
    check("Virtualizing only the bound user waits even while other historical messages remain",awaitingBinding(missing));
    bindingMutate("window.__bindingMain.insertBefore(window.__bindingUser,window.__bindingUserNext);({restored:true})",restored->{
      check("Restoring a virtualized user retains its exact identity and pending operation",restored.optBoolean("submitted")&&"id:current-question".equals(restored.optString("userKey"))&&session.pending==productionJob);
      bindingHomepageAllocation();
    });
  });}
  void bindingRoute(String path,Result result){
    ((FixtureView)session.web).semanticUrl=MainActivity.ORIGIN.substring(0,MainActivity.ORIGIN.length()-1)+path;
    bindingMutate("history.replaceState(null,'',"+JSONObject.quote(path)+");({routeChanged:true})",result);
  }
  void bindingHomepageAllocation()throws Exception{
    productionJob.put("confirmedUrl",MainActivity.ORIGIN).put("expectedUrl",MainActivity.ORIGIN);session.prefs.edit().putString("pending",productionJob.toString()).commit();
    evaluate("document.getElementById('composer').insertAdjacentHTML('beforeend','<button id=\"stop-button\" data-testid=\"stop-button\" aria-label=\"Stop\">Stop</button>');({streaming:true})",false,unused->bindingRoute("/",home->{
      check("A confirmed homepage prompt remains bound before the website assigns its conversation route",home.optBoolean("submitted")&&!home.optBoolean("bindingLost")&&session.pending==productionJob);
      evaluate("window.__bindingUser.querySelector('[data-user-message-bubble]').textContent='a different prompt with the same message ID';({promptChanged:true})",false,changed->bindingRoute("/c/allocated-fixture",wrong->{
        check("Homepage allocation rejects the same user ID when its prompt no longer matches",wrong.optBoolean("bindingLost")&&!wrong.optBoolean("submitted")&&session.pending==productionJob&&productionJob.optString("confirmedUrl").equals(MainActivity.ORIGIN));
        bindingMutate("window.__bindingUser.querySelector('[data-user-message-bubble]').textContent='bound performance prompt';({promptRestored:true})",allocated->{
        check("Homepage conversation allocation preserves the exact user identity and persists the new route",allocated.optBoolean("submitted")&&allocated.optBoolean("routeAssigned")&&!allocated.optBoolean("bindingLost")&&allocated.optString("error").isEmpty()&&"id:current-question".equals(allocated.optString("userKey"))&&session.pending==productionJob&&productionJob.optString("confirmedUrl").equals(((FixtureView)session.web).semanticUrl)&&J.parse(session.prefs.getString("pending","{}")).optString("confirmedUrl").equals(((FixtureView)session.web).semanticUrl));
        bindingRoute("/c/a-different-conversation",other->{
          check("A genuine different conversation is rejected even if its visible message IDs match",other.optBoolean("bindingLost")&&!other.optBoolean("submitted")&&session.pending==productionJob&&session.stableTicks==0&&session.webObserver.completionSamples==0);
          bindingNeutralShell();
        });
        });
      }));
    }));
  }
  void bindingNeutralShell(){
    ((FixtureView)session.web).semanticUrl=MainActivity.ORIGIN;
    bindingMutate("(()=>{window.__neutralChildren=[...window.__bindingMain.childNodes];window.__bindingMain.replaceChildren();document.getElementById('composer').hidden=true;history.replaceState(null,'','/');return {neutralShell:true};})()",shell->{
      check("A neutral homepage shell during restoration waits without declaring another conversation",awaitingBinding(shell));
      evaluate("window.__bindingMain.replaceChildren(...window.__neutralChildren);document.getElementById('composer').hidden=false;({restored:true})",false,unused->bindingRoute("/c/allocated-fixture",restored->{
        check("Restoring the bound conversation after a neutral shell retains its pending task",restored.optBoolean("submitted")&&!restored.optBoolean("bindingLost")&&session.pending==productionJob);
        bindingSocketError();
      }));
    });
  }
  void bindingSocketError(){bindingMutate("document.querySelector('[data-message-id=\"old-answer-0\"] .markdown p').append(' Browser app server websocket closed');({historicalText:true})",ordinary->{
    check("Websocket error words in ordinary historical reply text do not become a website fault",ordinary.optString("error").isEmpty()&&ordinary.optString("errorCode").isEmpty()&&ordinary.optBoolean("submitted")&&session.pending==productionJob);
    bindingMutate("document.querySelector('[data-message-id=\"old-answer-0\"]').parentElement.insertAdjacentHTML('beforeend','<div id=\"historical-socket-error\" role=\"alert\">Browser app server websocket closed <button aria-label=\"Retry\">Retry</button></div>');({historicalAlert:true})",historical->{
      check("A rendered historical reply socket alert and retry control do not invalidate the current task",historical.optString("error").isEmpty()&&historical.optString("errorCode").isEmpty()&&historical.optBoolean("submitted")&&session.pending==productionJob);
    bindingMutate("document.getElementById('historical-socket-error').remove();document.getElementById('stop-button').remove();({stopped:true})",first->{
      check("The restored real reply has only one valid terminal sample before the website error",first.optBoolean("submitted")&&session.pending==productionJob&&session.webObserver.completionSamples==1);
      later(()->bindingPoll(second->{
        check("Two real terminal samples still cannot finish before a website fault intervenes",session.pending==productionJob&&session.webObserver.completionSamples==2);
        evaluate("document.getElementById('current-answer').parentElement.insertAdjacentHTML('beforeend','<div id=\"socket-error\" role=\"alert\">Browser app server websocket closed</div>');({siteError:true})",false,unused->later(()->bindingInspect(error->{
          check("Actual native inspection recognizes the website socket fault before polling and resets terminal stability",((FixtureView)session.web).productionInspect!=null&&((FixtureView)session.web).productionInspect.optBoolean("websiteSocketClosed")&&((FixtureView)session.web).stableBeforeInspectedPoll==0&&((FixtureView)session.web).completionBeforeInspectedPoll==0&&session.stableTicks==0&&session.webObserver.completionSamples==0);
          check("A rendered website websocket-closed alert has a recoverable error while preserving the original binding",error.optBoolean("recoverable")&&!error.optString("error").isEmpty()&&"website_socket_closed".equals(error.optString("errorCode"))&&error.optBoolean("websiteSocketClosed")&&error.optBoolean("submitted")&&!error.optBoolean("bindingLost")&&session.pending==productionJob&&productionJob.optString("userKey").equals(error.optString("userKey")));
          check("Website errors clear native stable samples and never finish or clear the persisted task",session.stableTicks==0&&session.webObserver.completionSamples==0&&session.websiteConnectionIssue&&session.prefs.contains("pending")&&!"completed".equals(session.deliveries.get(productionJob.optString("id")).optString("state")));
          later(()->bindingPoll(again->{
            check("Repeated website error observations cannot accumulate completion samples",!again.optString("errorCode").isEmpty()&&session.pending==productionJob&&session.stableTicks==0&&session.webObserver.completionSamples==0);
            bindingMutate("document.getElementById('socket-error').remove();({restored:true})",restored->bindingFinal(1,restored));
          }),1100);
        }),100));
      }),1100);
    });
    });
  });}
  void bindingFinal(int index,JSONObject value)throws Exception{
    check("Recovered binding terminal sample "+index+" retains the entire real final reply",value.optBoolean("submitted")&&value.optString("error").isEmpty()&&!session.websiteConnectionIssue&&session.observedReplyMarkdown.length()>105000&&session.observedReplyMarkdown.contains("Java retained final tail"));
    if(index<3){
      check("Recovered binding terminal sample "+index+" keeps the task pending until the fresh stability window passes",session.pending==productionJob&&session.prefs.contains("pending")&&session.webObserver.completionSamples==index);
      later(()->bindingPoll(next->bindingFinal(index+1,next)),1100);return;
    }
    check("A restored bound reply completes only after three fresh actual samples and two seconds",session.pending==null&&!session.prefs.contains("pending")&&"completed".equals(session.deliveries.get(productionJob.optString("id")).optString("state")));
    evaluate("({sendCount:Number(document.getElementById('send-count').textContent),draft:document.getElementById('prompt-textarea').value,savedDraft:window.__bindingDraft,cookie:document.cookie})",false,finalState->{
      check("SPA restoration and websocket faults never resubmit and preserve the typed draft and synthetic login",finalState.optInt("sendCount")==0&&finalState.optString("draft").equals(finalState.optString("savedDraft"))&&finalState.optString("cookie").contains("session=synthetic-performance"));manualRecoveryRaces();
    });
  }
  void manualRecoveryRaces()throws Exception{
    originalDriver=session.driver;
    // page-state is still the exact real asset through the test-only host adapter.
    // No fake snapshot or retry implementation substitutes for the production code.
    session.driver="window.__pocketReadDriver(__ACTION__, __ARG__)";
    String route=session.web.getUrl(),id=session.deliveries.begin(route,"bound performance prompt",new JSONArray(),"web",null);
    manualJob=J.obj("id",id,"kind","web","confirmed",true,"userKey","id:current-question","prompt","bound performance prompt","confirmedUrl",route,"expectedUrl",route,"export",true);
    session.pending=manualJob;session.activeDeliveryId=id;session.prefs.edit().putString("pending",manualJob.toString()).commit();
    manualRace(1);
  }
  void manualRace(int index){attempt(()->{
    manualDraft=index==1?"manual recovery first draft":"manual recovery pending draft";
    evaluate("document.getElementById('prompt-textarea').value="+JSONObject.quote(manualDraft)+";({draftSet:true})",false,unused->{
      session.handler.removeCallbacks(session.tick);manualEpoch=session.navigationEpoch;manualConnection=session.connectionEpoch;
      FixtureView view=(FixtureView)session.web;view.pageStateReads=0;view.pageStateDraft="";
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
    if(!session.websiteRecovering||!manualDraft.equals(view.pageStateDraft))throw new IllegalStateException("Manual recovery snapshot failed before the controlled race");
    if(index==1){
      evaluate("document.getElementById('prompt-textarea').value='new typing while archive waits';({draftChanged:true})",false,unused->{archiveRelease.countDown();waitRecoveryRace(index,SystemClock.elapsedRealtime()+10000);});
    }else{
      String id=session.deliveries.begin(session.web.getUrl(),"another pending task",new JSONArray(),"web",null);
      manualJob=new JSONObject(manualJob.toString()).put("id",id);session.pending=manualJob;session.activeDeliveryId=id;session.prefs.edit().putString("pending",manualJob.toString()).commit();
      archiveRelease.countDown();waitRecoveryRace(index,SystemClock.elapsedRealtime()+10000);
    }
  });}
  void waitRecoveryRace(int index,long expires){attempt(()->{
    if(session.websiteRecovering){if(SystemClock.elapsedRealtime()>expires)throw new IllegalStateException("Manual recovery did not abort the stale operation");later(()->waitRecoveryRace(index,expires),50);return;}
    String route=session.web.getUrl(),captured=manualDraft;
    session.webStore.worker.execute(()->{
      JSONArray drafts=DraftArchive.get(session.context).list(route);boolean stored=false;for(int i=0;i<drafts.length();i++)if(captured.equals(drafts.optJSONObject(i).optString("body")))stored=true;
      final boolean persisted=stored;handler.post(()->attempt(()->{
        check(index==1?"Manual website recovery durably archives its captured draft before checking newer typing":"Manual website recovery durably archives its captured draft even when the pending task changes",persisted);
        evaluate("({draft:document.getElementById('prompt-textarea').value,sendCount:Number(document.getElementById('send-count').textContent),cookie:document.cookie})",false,end->{
          boolean noReload=session.navigationEpoch==manualEpoch&&session.connectionEpoch==manualConnection&&!session.navigating&&session.networkReady&&session.guard.allowed()&&session.pending==manualJob&&J.parse(session.prefs.getString("pending","{}")).optString("id").equals(manualJob.optString("id"));
          check(index==1?"Typing while manual recovery saves aborts reload and preserves the newer draft and original pending task":"Changing the pending task while manual recovery saves aborts stale reload and preserves the new task",noReload&&end.optString("draft").equals(index==1?"new typing while archive waits":captured)&&end.optInt("sendCount")==0&&end.optString("cookie").contains("session=synthetic-performance")&&((FixtureView)session.web).pageStateReads==(index==1?2:1));
          if(index==1)manualRace(2);else{
            session.driver=originalDriver;session.pending=null;session.prefs.edit().remove("pending").commit();
            session.stableTicks=2;session.stableReply="pre-disconnect terminal";session.webObserver.completionSamples=2;session.invalidateConnection();
            evaluate("({draft:document.getElementById('prompt-textarea').value,sendCount:Number(document.getElementById('send-count').textContent),cookie:document.cookie})",false,after->{
              check("Connection invalidation resets native terminal samples without submitting or clearing browser data",session.stableTicks==0&&session.stableReply.isEmpty()&&session.webObserver.completionSamples==0&&after.optInt("sendCount")==0&&after.optString("draft").equals(captured)&&after.optString("cookie").contains("session=synthetic-performance"));originalOnlyBridge();
            });
          }
        });
      }));
    });
  });}
  // Additional scope checks run only after every existing capture, exact input
  // burst and recovery assertion. Neither input pacing nor its oracle changes.
  final String[] retiredActions={"fill","submit","model-open","model-select","message-regenerate-submit","page-navigate"};
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
  JSONObject quietJob(String path)throws Exception{
    String route=MainActivity.ORIGIN.substring(0,MainActivity.ORIGIN.length()-1)+path,id=session.deliveries.begin(route,"bound performance prompt",new JSONArray(),"web",null);
    JSONObject job=J.obj("id",id,"kind","web","engine","gecko","confirmed",true,"userKey","id:current-question","prompt","bound performance prompt","confirmedUrl",route,"expectedUrl",route,"export",true,"startedAt",System.currentTimeMillis());
    productionJob=job;session.pending=job;session.activeDeliveryId=id;session.prefs.edit().putString("pending",job.toString()).commit();return job;
  }
  void quietInspect(String path,Result result){
    ((FixtureView)session.web).semanticUrl=MainActivity.ORIGIN.substring(0,MainActivity.ORIGIN.length()-1)+path;
    evaluate("history.replaceState(null,'',"+JSONObject.quote(path)+");({path:location.pathname})",false,actual->{
      if(!path.equals(actual.optString("path")))throw new IllegalStateException("Quiet navigation did not reach the actual Gecko SPA route");
      evaluate("window.__pocketReadDriver('web-inspect',{})",false,result);
    });
  }
  void quietNavigation()throws Exception{
    session.handler.removeCallbacks(session.tick);((FixtureView)session.web).quietTracking=true;session.inFlight=false;
    JSONObject old=quietJob("/c/quiet-A");session.stableReply="old terminal body";session.stableTicks=2;session.webObserver.completionSamples=2;
    quietInspect("/c/quiet-B",actual->{
      ((FixtureView)session.web).productionInspect=null;session.sync();waitQuietSync(old,SystemClock.elapsedRealtime()+10000);
    });
  }
  void waitQuietSync(JSONObject old,long expires){attempt(()->{
    if(session.inFlight){if(SystemClock.elapsedRealtime()>expires)throw new IllegalStateException("Quiet navigation sync timeout");later(()->waitQuietSync(old,expires),50);return;}
    JSONObject actual=((FixtureView)session.web).productionInspect,stored=session.deliveries.get(old.optString("id"));
    check("Actual different official SPA conversation quietly archives its native observation",actual!=null&&actual.optString("url").endsWith("/c/quiet-B")&&session.pending==null&&!session.prefs.contains("pending")&&session.activeDeliveryId.isEmpty());
    check("Quiet conversation archive retains full pending body and original delivery binding",J.parse(session.prefs.getString("archivedWebObservation","{}")).toString().equals(old.toString())&&stored!=null&&stored.optString("body").equals(old.optString("prompt"))&&stored.optString("user_key").equals(old.optString("userKey"))&&stored.optString("url").equals(old.optString("confirmedUrl"))&&stored.optString("state").equals("uncertain"));
    check("Quiet conversation archive clears stale completion samples and settings busy state",session.stableTicks==0&&session.stableReply.isEmpty()&&session.webObserver.completionSamples==0&&!ProfileUi.working(session)&&!old.optString("id").equals(session.prefs.getString("lastCompletedId","")));
    quietInspect("/c/quiet-A",back->{
      check("Returning to an archived official conversation does not resurrect its old task",!session.archiveWebsiteNavigation(back)&&session.pending==null&&!session.prefs.contains("pending"));
      quietJob("/c/quiet-B");quietInspect("/c/quiet-B",same->{
        check("Matching current official conversation retains a new observation",!session.archiveWebsiteNavigation(same)&&session.pending==productionJob);
        JSONObject stale=J.parse(same.toString());stale.put("url",MainActivity.ORIGIN+"c/quiet-C");
        check("A stale inspected URL cannot archive the current task",!session.archiveWebsiteNavigation(stale)&&session.pending==productionJob);
        evaluate("document.getElementById('composer').insertAdjacentHTML('beforeend','<button id=\"stop-button\" data-testid=\"stop-button\" aria-label=\"Stop\">Stop</button>');({busy:true})",false,unused->bindingPoll(poll->{
          check("A new official conversation still monitors its exact bound user without native submission",poll.optBoolean("submitted")&&poll.optBoolean("busy")&&session.pending==productionJob&&poll.optString("userKey").equals("id:current-question"));quietLoginAndHome();
        }));
      });
    });
  });}
  void quietLoginAndHome(){quietInspect("/auth/login",login->{
    check("An actual login route retains unresolved observation and its original binding",!session.archiveWebsiteNavigation(login)&&session.pending==productionJob);
    evaluate("(()=>{window.__quietMain=document.querySelector('main');window.__quietChildren=[...window.__quietMain.childNodes];window.__quietMain.replaceChildren();document.getElementById('composer').hidden=true;return {shell:true};})()",false,unused->quietInspect("/",shell->{
      check("An actual empty homepage hydration shell does not archive a bound conversation",!shell.optBoolean("composer")&&!shell.optBoolean("hasMessages")&&!session.archiveWebsiteNavigation(shell)&&session.pending==productionJob);
      evaluate("document.getElementById('composer').hidden=false;({busyHome:true})",false,ready->quietInspect("/",busy->{
        check("An interactive homepage still displaying a busy operation retains its bound observation",busy.optBoolean("composer")&&busy.optBoolean("busy")&&!session.archiveWebsiteNavigation(busy)&&session.pending==productionJob);
        evaluate("document.getElementById('stop-button')?.remove();({idleHome:true})",false,idle->quietInspect("/",home->{
        check("An actual interactive empty official homepage quietly ends the old observation",home.optBoolean("composer")&&!home.optBoolean("hasMessages")&&session.archiveWebsiteNavigation(home)&&session.pending==null);
        evaluate("window.__quietMain.replaceChildren(...window.__quietChildren);document.getElementById('stop-button')?.remove();({restored:true})",false,restored->{
          quietJob("/c/quiet-B");quietInspect("/c/quiet-B",same->quietSameRouteError());
        });
      }));}));
    }));
  });}
  void quietSameRouteError(){bindingMutate("document.querySelector('[data-message-id=\"current-question\"] [data-user-message-bubble]').textContent='a real edited question in the same conversation';({edited:true})",error->{
    check("A genuine same-conversation edited question stays unresolved with its error",session.pending==productionJob&&session.prefs.contains("pending")&&!error.optString("error").isEmpty()&&!session.status.isEmpty()&&session.stableTicks==0&&session.webObserver.completionSamples==0);
    evaluate("document.querySelector('[data-message-id=\"current-question\"] [data-user-message-bubble]').textContent='bound performance prompt';({draft:document.getElementById('prompt-textarea').value,saved:window.__originalOnlyWebsite.draft,cookie:document.cookie,sent:Number(document.getElementById('send-count').textContent)})",false,end->{
      check("Quiet navigation never stops reloads resubmits or changes the browser draft and login",((FixtureView)session.web).quietStops==0&&((FixtureView)session.web).quietLoads==0&&end.optInt("sent")==0&&end.optString("draft").equals(end.optString("saved"))&&end.optString("cookie").contains("session=synthetic-performance"));
      session.pending=null;session.prefs.edit().remove("pending").commit();success();
    });
  });}
  void success(){finished=true;event("report",J.obj("status","passed","actualAndroidExecution",true,"actualGeckoExecution",true,"actualAndroidTouchExecution",true,"actualGeckoBindingRegressionExecution",true,"actualInputImeSettled",inputImeSettled,"actualSingleInputBurst",true,"inputDiagnosticsEnabled",inputDiagnostics,"inputNativeDiagnosticsEnabled",inputNativeDiagnostics,"baselineSource",BASELINE,"checkCount",checkCount,"directDeferredSamples",directDeferredSamples,"nativeDeferredSamples",nativeDeferredSamples,"scope","Actual GeckoView 157, real extension-to-native payload and DOM work; actual Android scroll and keyboard input; 240 historical messages and 105k current reply. Subsequent same-route DOM restoration, exact-identity SPA allocation, website socket faults and native completion-stability regression; no real account or external site. RAF and Android Choreographer timings are descriptive, no cross-device FPS threshold.","measurements",J.arr(baselineMetrics,currentMetrics)));}
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
  @Override protected void onDestroy(){stopInputTrace();frames.stop();if(archiveRelease!=null)archiveRelease.countDown();handler.removeCallbacksAndMessages(null);if(session!=null)session.handler.removeCallbacks(session.tick);super.onDestroy();}
}
