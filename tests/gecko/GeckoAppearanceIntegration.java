package local.pocketchat;

import android.os.SystemClock;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.IdentityHashMap;
import java.util.Map;
import java.util.function.Consumer;
import org.json.*;
import org.mozilla.geckoview.GeckoSession;
import org.mozilla.geckoview.WebExtension;

/** Integration-only actual Gecko/isolated-world/native receipts on synthetic CSS. */
final class GeckoAppearanceIntegration {
  static final String PREFIX="http://127.0.0.1:8765/appearance-sync/";
  static final Map<GeckoIntegrationTestActivity,State> STATES=new java.util.WeakHashMap<>();
  static final String SNAPSHOT="(()=>{const root=document.documentElement,input=document.getElementById('prompt-textarea'),main=document.querySelector('main');const color=e=>{const c=getComputedStyle(e),r=e.getBoundingClientRect();return {background:c.backgroundColor,foreground:c.color,rect:{x:r.x,y:r.y,width:r.width,height:r.height}}};return {url:location.href,fixtureDocument:root.dataset.fixtureDocument,mainWorldHelper:root.dataset.mainWorldHelper,isolatedHelper:typeof globalThis.PocketAppearance?.synchronize==='function',isolatedNativeBridge:typeof browser?.runtime?.connectNative==='function',rootClass:root.className,colorScheme:root.style.colorScheme,draft:input.value,selectionStart:input.selectionStart,selectionEnd:input.selectionEnd,cookie:document.cookie,storageFault:globalThis.__appearanceFixtureStorage?.fault||'',main:color(main),composer:color(input)}})()";
  static final class State {
    String suite,target,baselineDocument,baselineCookie;JSONObject assets;
    GeckoSession initial,popup;WebExtension.Port reloadPort,popupPort;JSONObject reloadReceipt,popupReceipt;
    final JSONArray wire=new JSONArray();
    final IdentityHashMap<WebExtension.Port,WebExtension.PortDelegate> originals=new IdentityHashMap<>();
    void watch(WebExtension.Port port)throws Exception {
      if(port==null)throw new IllegalStateException("Actual appearance port unavailable");
      if(originals.containsKey(port))return;
      WebExtension.PortDelegate original=null;
      try{Method method=port.getClass().getMethod("getDelegate");original=(WebExtension.PortDelegate)method.invoke(port);}
      catch(NoSuchMethodException unavailable){
        // Some SDK versions expose only setDelegate. Observe the existing delegate;
        // its production validation remains the only native receipt consumer.
        for(Field field:port.getClass().getDeclaredFields())if(WebExtension.PortDelegate.class.isAssignableFrom(field.getType())){field.setAccessible(true);if(original!=null)throw new IllegalStateException("Ambiguous actual port delegate");original=(WebExtension.PortDelegate)field.get(port);}
      }
      if(original==null)throw new IllegalStateException("Actual production port delegate unavailable");
      final WebExtension.PortDelegate forward=original;originals.put(port,forward);
      port.setDelegate(new WebExtension.PortDelegate(){
        @Override public void onPortMessage(Object message,WebExtension.Port incoming){
          if(message instanceof JSONObject&&"appearanceReceipt".equals(((JSONObject)message).optString("kind"))){
            if(wire.length()>=384)throw new IllegalStateException("Bounded appearance wire trace exceeded");
            wire.put(J.obj("elapsed",SystemClock.elapsedRealtime(),"port",System.identityHashCode(incoming),"receipt",J.parse(message.toString())));
          }
          forward.onPortMessage(message,incoming);
        }
        @Override public void onDisconnect(WebExtension.Port incoming){forward.onDisconnect(incoming);}
      });
    }
    JSONObject findObserved(WebExtension.Port port,int version){
      for(int i=wire.length()-1;i>=0;i--){JSONObject point=wire.optJSONObject(i),receipt=point.optJSONObject("receipt");if(point.optInt("port")==System.identityHashCode(port)&&receipt.optInt("version")==version&&"observed".equals(receipt.optString("stage")))return J.parse(receipt.toString());}
      return null;
    }
    JSONObject observed(WebExtension.Port port,int version){
      JSONObject value=findObserved(port,version);if(value!=null)return value;
      throw new IllegalStateException("No genuine observed receipt captured for current version");
    }
  }
  final GeckoIntegrationTestActivity activity;final ChatSession owner;final GeckoIntegrationTestActivity.FixtureView web;
  final long serial,started=SystemClock.elapsedRealtime();final String phase;final State state;final JSONArray checks=new JSONArray(),replays=new JSONArray();
  final int wireStart;JSONObject beforeAppearance,beforePage,beforeReceipt,storageInjection;WebExtension.Port beforePort;GeckoSession beforeSession;
  boolean finished;long deadline;int minimumVersion;
  GeckoAppearanceIntegration(GeckoIntegrationTestActivity a,long command,State s){activity=a;owner=a.session;web=(GeckoIntegrationTestActivity.FixtureView)owner.web;serial=command;state=s;phase=a.getIntent().getStringExtra("appearancePhase");wireStart=s.wire.length();}
  static void run(GeckoIntegrationTestActivity a,long command){
    String phase=a.getIntent().getStringExtra("appearancePhase");State state=STATES.get(a);
    if("prepare".equals(phase)){state=new State();STATES.put(a,state);}
    if(state==null){a.event(command,"error",J.obj("error","Appearance prepare phase required"));return;}
    GeckoAppearanceIntegration test=new GeckoAppearanceIntegration(a,command,state);test.step(test::start);
  }
  boolean current(){return !finished&&serial==activity.run;}
  void step(Runnable task){if(!current())return;try{task.run();}catch(Exception error){finish(error,null);}}
  void later(Runnable task,long delay){owner.handler.postDelayed(()->step(task),delay);}
  void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));if(!pass)throw new IllegalStateException(name);}
  void eval(String source,Consumer<JSONObject> next){web.evaluateJavascript(source,raw->step(()->{JSONObject value=J.parse(raw);if(value.length()==0)throw new IllegalStateException("Actual isolated-world evaluator unavailable");next.accept(value);}));}
  void snapshot(Consumer<JSONObject> next){eval(SNAPSHOT,next);}
  void start(){
    String suite=activity.getIntent().getStringExtra("appearanceSuiteNonce");
    check("Owned test package and appearance invocation","local.pocketchat.test".equals(activity.getPackageName())&&suite!=null&&suite.matches("[0-9a-f]{32}")&&"appearanceSync".equals(activity.action));
    if("prepare".equals(phase)){
      state.suite=suite;state.target=PREFIX+"?runNonce="+suite;state.initial=web.current;
      try(java.io.InputStream input=activity.getAssets().open("pocketchat-appearance-fixture.json")){state.assets=new JSONObject(J.text(input,16384));}catch(Exception error){throw new IllegalStateException("Missing exact integration overlay receipt",error);}
      JSONObject transform=state.assets.optJSONObject("transform");
      check("Fixture asset explicitly declares the controlled origin",state.assets.optBoolean("integrationOnly")&&transform!=null&&transform.optString("additionalOrigin").equals("http://127.0.0.1:8765")&&transform.optString("additionalPathPrefix").equals("/appearance-sync/"));
      AppAppearance.choose(activity,"light");web.loadUrl(state.target);deadline=SystemClock.elapsedRealtime()+20000;later(this::prepare,100);return;
    }
    check("All phases belong to the same controlled suite",suite.equals(state.suite));
    check("Production network guard remains admitted",owner.guard.allowed()&&owner.networkReady&&!owner.internalNetwork());
    check("Current native URL is the owned fixture",web.getUrl()!=null&&web.getUrl().startsWith(PREFIX)&&state.suite.equals(android.net.Uri.parse(web.getUrl()).getQueryParameter("runNonce")));
    beforePort=web.ports.get(web.current);beforeSession=web.current;
    try{state.watch(beforePort);}catch(Exception error){throw new IllegalStateException(error);}
    deadline=SystemClock.elapsedRealtime()+10000;waitBefore();
  }
  void waitBefore(){
    beforeAppearance=web.appearanceReport();
    beforeReceipt=state.findObserved(beforePort,beforeAppearance.optInt("version"));
    // Returning the Activity to the foreground can legitimately issue a fresh
    // appearanceVisible request. Observe that real version before replacing it.
    if(beforeReceipt==null||"pending".equals(beforeAppearance.optString("status"))){
      if(SystemClock.elapsedRealtime()>deadline)throw new IllegalStateException("No current real appearance receipt before phase "+phase+": "+beforeAppearance);
      later(this::waitBefore,100);return;
    }
    minimumVersion=beforeAppearance.optInt("version")+1;snapshot(page->{beforePage=page;dispatch();});
  }
  void prepare(){
    WebExtension.Port port=web.ports.get(web.current);
    if(!state.target.equals(web.getUrl())||!web.hasVisibleDocument()||port==null){if(SystemClock.elapsedRealtime()>deadline)throw new IllegalStateException("Controlled Gecko fixture did not become visible");later(this::prepare,100);return;}
    try{state.watch(port);}catch(Exception error){throw new IllegalStateException(error);}
    eval("(()=>{const input=document.getElementById('prompt-textarea');if(!input)return {ready:false};input.value='unsent appearance fixture draft';input.setSelectionRange(7,17);return {ready:true}})()",ready->{
      check("Real fixture composer exists",ready.optBoolean("ready"));
      minimumVersion=web.appearanceReport().optInt("version")+1;AppAppearance.choose(activity,"light");await("confirmed",false,page->{
        state.baselineDocument=page.optString("fixtureDocument");state.baselineCookie=page.optString("cookie");
        check("Actual isolated world owns helper and bridge",page.optBoolean("isolatedHelper")&&page.optBoolean("isolatedNativeBridge")&&"undefined".equals(page.optString("mainWorldHelper")));
        check("Nonempty fixture document, unsent draft, selection and owned cookie",state.baselineDocument.length()>=16&&page.optString("draft").equals("unsent appearance fixture draft")&&page.optInt("selectionStart")==7&&page.optInt("selectionEnd")==17&&state.baselineCookie.contains("appearance-fixture=controlled"));
        finish(null,page);
      });
    });
  }
  void dispatch(){
    switch(phase){
      case "dark":case "light":case "same":
        choose(phase.equals("light")?"light":"dark","confirmed",!phase.equals("light"),page->{preserved(page,true);if(phase.equals("same"))replay(beforePort,beforeReceipt,"Prior same-document version");finish(null,page);});return;
      case "spa":
        eval("(()=>{history.pushState({},'',location.pathname+'?runNonce="+state.suite+"&spa=1');return {ready:true}})()",unused->choose("light","confirmed",false,page->{preserved(page,true);check("SPA keeps original document and native session",state.baselineDocument.equals(page.optString("fixtureDocument"))&&web.current==state.initial);finish(null,page);}));return;
      case "reload":
        state.reloadPort=beforePort;state.reloadReceipt=beforeReceipt;state.target=beforePage.optString("url");web.current.reload();minimumVersion=0;deadline=SystemClock.elapsedRealtime()+20000;later(this::afterReload,100);return;
      case "white":
        eval("(()=>{document.getElementById('fixed-white').textContent='html.dark main,html.dark #prompt-textarea{background:rgb(255,255,255)!important;color:rgb(24,24,24)!important}';return {ready:true}})()",unused->choose("dark","failed",true,page->{
          JSONObject report=web.appearanceReport();check("White visible CSS cannot confirm native dark request",report.optBoolean("received")&&report.optBoolean("applied")&&"mismatch".equals(report.optString("colorStatus"))&&report.optInt("attempt")==WebAppearanceSync.MAX_ATTEMPTS);
          check("Actual main and composer remain visibly white",page.optJSONObject("main").optString("background").equals("rgb(255, 255, 255)")&&page.optJSONObject("composer").optString("background").equals("rgb(255, 255, 255)"));preserved(page,true);finish(null,page);
        }));return;
      case "restore":
        eval("(()=>{document.getElementById('fixed-white').textContent='';return {ready:true}})()",unused->choose("dark","confirmed",true,page->{preserved(page,true);finish(null,page);}));return;
      case "storageRead":case "storageWrite":
        String method=phase.equals("storageRead")?"getItem":"setItem";
        eval("(()=>{if(globalThis.__appearanceFixtureStorage){for(const [k,d] of Object.entries(globalThis.__appearanceFixtureStorage.saved))Object.defineProperty(Storage.prototype,k,d)}localStorage.setItem('theme','light');const saved={getItem:Object.getOwnPropertyDescriptor(Storage.prototype,'getItem'),setItem:Object.getOwnPropertyDescriptor(Storage.prototype,'setItem')};if(!saved.getItem||!saved.setItem)return {ready:false,reason:'prototype-descriptor-unavailable'};globalThis.__appearanceFixtureStorage={saved,fault:'"+method+"'};Object.defineProperty(Storage.prototype,'"+method+"',{configurable:true,writable:true,value:function(key,...args){if(key==='theme')throw new DOMException('Controlled fixture API injection','SecurityError');return globalThis.__appearanceFixtureStorage.saved."+method+".value.call(this,key,...args)}});try{localStorage['"+method+"']('theme','dark');return {ready:false,reason:'injected-method-not-observed'}}catch(error){return {ready:true,method:'"+method+"',errorName:error.name,errorMessage:error.message,scope:'Controlled isolated-world Storage API injection; not real quota exhaustion'}}})()",injection->{
          storageInjection=injection;check("Actual isolated-world Storage calls observe the controlled API fault",injection.optBoolean("ready")&&method.equals(injection.optString("method"))&&"SecurityError".equals(injection.optString("errorName"))&&"Controlled fixture API injection".equals(injection.optString("errorMessage")));
          choose("dark","partial",true,page->{
          JSONObject report=web.appearanceReport();check("Controlled storage API failure remains partial despite correct visible CSS",report.optBoolean("received")&&report.optBoolean("applied")&&"verified".equals(report.optString("colorStatus"))&&report.optInt("attempt")==WebAppearanceSync.MAX_ATTEMPTS&&(phase.equals("storageRead")?"unavailable":"failed").equals(report.optString("storage")));preserved(page,true);finish(null,page);
        });});return;
      case "storageRestore":
        restoreStorage(()->choose("dark","confirmed",true,page->{check("Controlled Storage prototype restored",page.optString("storageFault").isEmpty());preserved(page,true);finish(null,page);}));return;
      case "newSession":
        state.reloadPort=beforePort;state.reloadReceipt=beforeReceipt;
        // Controlled native invocation of the unmodified production popup delegate.
        // Its URL/network guard runs normally, then Gecko creates an actual session.
        int popupsBefore=web.popups.size();
        org.mozilla.geckoview.GeckoResult<GeckoSession> created=web.current.getNavigationDelegate().onNewSession(web.current,state.target);
        check("Production popup delegate admits actual controlled session",created!=null&&web.popups.size()==popupsBefore+1);
        // Open before the production delegate's posted activate() runs, as Gecko
        // does when it consumes an ordinary onNewSession result.
        state.popup=web.popups.get(popupsBefore);state.popup.open(web.runtime);state.popup.loadUri(state.target);
        created.accept(popup->step(()->{
          check("Production delegate returns the actual newly opened session",popup==state.popup&&popup!=beforeSession&&popup.isOpen());minimumVersion=0;deadline=SystemClock.elapsedRealtime()+20000;later(this::afterNewSession,100);
        }),error->step(()->{throw new IllegalStateException("Actual native popup failed",error);}));return;
      case "oldSession":
        state.popupPort=beforePort;state.popupReceipt=beforeReceipt;
        check("Production popup close returns to retained old native session",web.current==state.popup&&web.closePopup()&&web.current==state.initial&&!state.popup.isOpen());
        minimumVersion=web.appearanceReport().optInt("version")+1;choose("dark","confirmed",true,page->{
          preserved(page,true);replay(state.popupPort,state.popupReceipt,"Retired native Gecko session");check("Original native Gecko session is retained",web.current==state.initial);finish(null,page);
        });return;
      case "cleanup":
        restoreStorage(()->eval("(()=>{document.cookie='appearance-fixture=;Max-Age=0;path=/appearance-sync/';return {ready:true}})()",unused->snapshot(page->{check("Only owned fixture cookie is retired",!page.optString("cookie").contains("appearance-fixture=")&&withoutMarker(page.optString("cookie")).equals(withoutMarker(state.baselineCookie)));finish(null,page);STATES.remove(activity);})));return;
      default:throw new IllegalStateException("Unknown appearance phase: "+phase);
    }
  }
  void afterReload(){
    if(!state.target.equals(web.getUrl())||!web.hasVisibleDocument()||web.ports.get(web.current)==null||web.ports.get(web.current)==state.reloadPort){if(SystemClock.elapsedRealtime()>deadline)throw new IllegalStateException("Same-URL reload did not create new bridge document");later(this::afterReload,100);return;}
    try{state.watch(web.ports.get(web.current));}catch(Exception error){throw new IllegalStateException(error);}
    // A reload may discard a page draft. Seed its new document; theme-only
    // continuity is asserted separately without any reload or form reseeding.
    eval("(()=>{const input=document.getElementById('prompt-textarea');input.value='unsent appearance fixture draft';input.setSelectionRange(7,17);return {ready:true}})()",unused->{minimumVersion=web.appearanceReport().optInt("version")+1;choose("light","confirmed",false,page->{
      check("Same URL reload gets a different real document and port",!state.baselineDocument.equals(page.optString("fixtureDocument"))&&state.target.equals(page.optString("url"))&&web.current==state.initial&&web.ports.get(web.current)!=state.reloadPort);
      replay(state.reloadPort,state.reloadReceipt,"Prior same-URL document");state.baselineDocument=page.optString("fixtureDocument");preserved(page,true);finish(null,page);
    });});
  }
  void afterNewSession(){
    if(web.current!=state.popup||!state.target.equals(web.getUrl())||!web.hasVisibleDocument()||web.ports.get(web.current)==null){if(SystemClock.elapsedRealtime()>deadline)throw new IllegalStateException("New actual native session did not become visible");later(this::afterNewSession,100);return;}
    try{state.watch(web.ports.get(web.current));}catch(Exception error){throw new IllegalStateException(error);}
    minimumVersion=web.appearanceReport().optInt("version")+1;choose("light","confirmed",false,page->{
      check("New native session has its own observed document",web.current!=state.initial&&!state.baselineDocument.equals(page.optString("fixtureDocument"))&&web.appearanceReport().optInt("version")>state.reloadReceipt.optInt("version"));
      // The old still-live page may update only its own coordinator entry.
      replay(state.reloadPort,state.reloadReceipt,"Old live native Gecko session");finish(null,page);
    });
  }
  void choose(String mode,String status,boolean dark,Consumer<JSONObject> next){AppAppearance.choose(activity,mode);await(status,dark,next);}
  void await(String status,boolean dark,Consumer<JSONObject> next){deadline=SystemClock.elapsedRealtime()+16000;poll(status,dark,next);}
  void poll(String status,boolean dark,Consumer<JSONObject> next){
    JSONObject report=web.appearanceReport();
    if(report.optInt("version")>=minimumVersion&&status.equals(report.optString("status"))&&report.opt("desiredDark") instanceof Boolean&&report.optBoolean("desiredDark")==dark){
      snapshot(page->{check("Requested native theme reaches its actual document",AppAppearance.dark()==dark&&page.optString("colorScheme").equals(dark?"dark":"light")&&report.optBoolean("received")&&report.optBoolean("applied"));verifyWire();next.accept(page);});return;
    }
    if(SystemClock.elapsedRealtime()>deadline)throw new IllegalStateException("Actual appearance phase timed out: "+phase+" expected "+status+" got "+report);
    later(()->poll(status,dark,next),100);
  }
  void verifyWire(){
    JSONObject report=web.appearanceReport();WebExtension.Port port=web.ports.get(web.current);int version=report.optInt("version");
    boolean received=false,applied=false,observed=false;String document=web.appearanceDocuments.get(port);
    for(int i=wireStart;i<state.wire.length();i++){JSONObject point=state.wire.optJSONObject(i),receipt=point.optJSONObject("receipt");if(point.optInt("port")!=System.identityHashCode(port)||receipt.optInt("version")!=version||!receipt.optString("documentId").equals(document))continue;String stage=receipt.optString("stage");received|=stage.equals("received");applied|=stage.equals("applied");observed|=stage.equals("observed");}
    check("Actual port carries document-bound received, applied and observed receipts",received&&applied&&observed&&document!=null&&document.length()>=16);
    if("confirmed".equals(report.optString("status"))){
      JSONObject receipt=state.observed(port,version);boolean main=false,composer=false;
      JSONArray samples=receipt.optJSONArray("samples");for(int i=0;i<samples.length();i++){JSONObject sample=samples.optJSONObject(i);if(sample.optString("region").equals("main"))main=sample.optBoolean("visible");if(sample.optString("region").equals("composer"))composer=sample.optBoolean("visible");}
      check("Confirmation comes from both actual visible computed regions",main&&composer&&"verified".equals(receipt.optString("colorStatus"))&&"verified".equals(report.optString("colorStatus")));
    }
  }
  void replay(WebExtension.Port port,JSONObject raw,String label){
    JSONObject active=J.parse(web.appearanceReport().toString());
    check(label+" uses a previously captured real wire receipt",port!=null&&raw!=null&&state.originals.containsKey(port));
    state.originals.get(port).onPortMessage(J.parse(raw.toString()),port);
    // This direct API check is explicitly a controlled stale-receipt injection.
    // Snapshot equality alone would miss acceptance of an identical old theme.
    boolean accepted=web.appearanceSync.receive(port,J.parse(raw.toString()));
    replays.put(J.obj("label",label,"port",System.identityHashCode(port),"receipt",J.parse(raw.toString()),"nativeAccepted",accepted,"injection","Captured real raw receipt, original native PortDelegate then direct production coordinator rejection check"));
    check(label+" receipt is rejected by the production coordinator",!accepted);
    check(label+" receipt cannot overwrite current confirmation",active.toString().equals(web.appearanceReport().toString()));
  }
  void preserved(JSONObject page,boolean original){
    check("Appearance event preserves unsent draft and selection",page.optString("draft").equals("unsent appearance fixture draft")&&page.optInt("selectionStart")==7&&page.optInt("selectionEnd")==17);
    check("Appearance event preserves actual document cookies",page.optString("cookie").equals(state.baselineCookie));
    if(original)check("Appearance event retains native session and document",web.current==state.initial&&page.optString("fixtureDocument").equals(state.baselineDocument));
  }
  void restoreStorage(Runnable next){eval("(()=>{if(globalThis.__appearanceFixtureStorage){for(const [key,descriptor] of Object.entries(globalThis.__appearanceFixtureStorage.saved))Object.defineProperty(Storage.prototype,key,descriptor);delete globalThis.__appearanceFixtureStorage}const theme=localStorage.getItem('theme');localStorage.setItem('theme',theme);return {ready:localStorage.getItem('theme')===theme,faultAbsent:!globalThis.__appearanceFixtureStorage}})()",probe->{check("Restored Storage API accepts actual theme reads and writes",probe.optBoolean("ready")&&probe.optBoolean("faultAbsent"));next.run();});}
  static String withoutMarker(String cookie){return cookie.replaceAll("(^|; )appearance-fixture=controlled(?=; |$)","").replaceAll("^; |; $","");}
  void finish(Exception error,JSONObject page){
    if(finished)return;finished=true;
    JSONArray wire=new JSONArray();for(int i=wireStart;i<state.wire.length();i++)wire.put(state.wire.optJSONObject(i));
    JSONObject result=J.obj("schema",1,"status",error==null?"passed":"failed","phase",phase,"suiteNonce",state.suite==null?"":state.suite,"actualAndroidExecution",true,"actualGeckoExecution",true,"synthetic",true,"checks",checks,"checkCount",checks.length(),"page",page==null?new JSONObject():page,"appearance",web.appearanceReport(),"wireReceipts",wire,"staleReceiptReplays",replays,"assets",state.assets==null?new JSONObject():state.assets,"elapsedMillis",SystemClock.elapsedRealtime()-started,"nativeSession",System.identityHashCode(web.current),"nativePort",System.identityHashCode(web.ports.get(web.current)),"scope","Actual Gecko native send, extension isolated-world apply, visible computed main/composer CSS and production WebAppearanceSync. Controlled synthetic loopback page, not the official ChatGPT website; Storage faults and stale raw-receipt replay are controlled API injections; popup creation invokes the production native delegate, not an Android click.");
    if(beforeAppearance!=null)NetworkCatalog.put(result,"beforeAppearance",beforeAppearance);
    if(storageInjection!=null)NetworkCatalog.put(result,"storageInjection",storageInjection);
    if(error!=null)NetworkCatalog.put(result,"error",error.toString());
    activity.event(serial,"appearanceSync",result);
  }
}
