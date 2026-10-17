package local.pocketchat;

import android.app.Activity;
import android.content.Context;
import android.content.ContextWrapper;
import android.os.*;
import android.util.Log;
import android.widget.LinearLayout;
import android.widget.TextView;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;
import org.mozilla.geckoview.*;

/** Test-only official-SDK observations; never an applied fingerprint-template receipt. */
public class GeckoIdentityPrototypeIntegrationActivity extends Activity {
  static final String TAG="PocketIdentityPrototype",FILE="gecko-identity-prototype-results.json";
  static final String SDK="org.mozilla.geckoview:geckoview:157.0.20261005135250";
  // SDK is the upstream reference; actual AAR identity comes from the installed SDK asset.
  final Handler handler=new Handler(Looper.getMainLooper());
  final ExecutorService storage=Executors.newSingleThreadExecutor();
  final JSONArray checks=new JSONArray(),cases=new JSONArray(),routes=new JSONArray(),navigation=new JSONArray();
  final Map<String,JSONObject> received=new LinkedHashMap<>(),nativeAgents=new LinkedHashMap<>();
  final Map<String,JSONObject> rawObservations=new LinkedHashMap<>();
  final Map<String,GeckoSession> targets=new LinkedHashMap<>();
  JSONObject buildIdentity=new JSONObject(),sdkUserAgentBaseline=new JSONObject(),sdkBuildIdentity=new JSONObject();ChatSession owner;FixtureView view;LocalSite site;
  String source,run,origin;int caseIndex=-1,serial;boolean finished,announced;
  String[] requestedLocales;String normalizedLanguage;boolean desktop;
  long requestedAt;Runnable caseDeadline;int navigationDropped;
  GeckoSession guardSession;String guardNonce,guardDocument,guardFetchUrl,guardWorkerUrl;
  JSONObject guardEvidence=new JSONObject();final JSONArray guardRoutes=new JSONArray();int guardRoutesDropped;

  static final class PrivateContext extends ContextWrapper {
    final File directory;
    PrivateContext(Context context){super(context);directory=new File(context.getNoBackupFilesDir(),"identity-prototype");}
    @Override public Context getApplicationContext(){return this;}
    @Override public File getNoBackupFilesDir(){if(!directory.isDirectory()&&!directory.mkdirs())throw new IllegalStateException("Private fixture directory unavailable");return directory;}
  }
  class FixtureView extends GeckoWebView {
    FixtureView(Context context,ChatSession session){super(context,session);}
    @Override protected boolean allowedUrl(String target){return target!=null&&target.startsWith(origin+"/");}
    @Override JSONObject route(String target){
      JSONObject actual=super.route(target);
      JSONObject record=J.obj("url",target,"route",actual,"guardAllowed",owner.guard.allowed(),"at",SystemClock.elapsedRealtime());
      if(routes.length()<64)routes.put(record);
      if(target.equals(guardFetchUrl)||target.equals(guardWorkerUrl)){if(guardRoutes.length()<8)guardRoutes.put(record);else guardRoutesDropped++;}
      return actual;
    }
    @Override GeckoSession newSession(){
      GeckoSession sdk=super.newSession();
      GeckoSession.NavigationDelegate original=sdk.getNavigationDelegate();
      sdk.setNavigationDelegate(new GeckoSession.NavigationDelegate(){
        @Override public GeckoResult<AllowOrDeny> onLoadRequest(GeckoSession s,LoadRequest request){navigation(s,"loadRequest",request.uri,J.obj("directNavigation",request.isDirectNavigation,"redirect",request.isRedirect,"guardAllowed",owner.guard.allowed(),"fixtureAllowed",allowedUrl(request.uri)));return original.onLoadRequest(s,request);}
        @Override public GeckoResult<AllowOrDeny> onSubframeLoadRequest(GeckoSession s,LoadRequest request){navigation(s,"subframeLoadRequest",request.uri,null);return original.onSubframeLoadRequest(s,request);}
        @Override public void onLocationChange(GeckoSession s,String target,List<GeckoSession.PermissionDelegate.ContentPermission> permissions,Boolean gesture){original.onLocationChange(s,target,permissions,gesture);navigation(s,"locationChange",target,null);}
        @Override public void onCanGoBack(GeckoSession s,boolean value){original.onCanGoBack(s,value);}
        @Override public void onCanGoForward(GeckoSession s,boolean value){original.onCanGoForward(s,value);}
        @Override public GeckoResult<GeckoSession> onNewSession(GeckoSession s,String target){return original.onNewSession(s,target);}
        @Override public GeckoResult<String> onLoadError(GeckoSession s,String target,WebRequestError error){navigation(s,"loadError",target,J.obj("code",error.code,"category",error.category,"message",error.getMessage()));return original.onLoadError(s,target,error);}
      });
      GeckoSession.PermissionDelegate permissions=sdk.getPermissionDelegate();
      sdk.setPermissionDelegate(new GeckoSession.PermissionDelegate(){
        @Override public void onAndroidPermissionsRequest(GeckoSession s,String[] requested,Callback callback){navigation(s,"androidPermissions",null,J.obj("permissions",requested==null?JSONObject.NULL:new JSONArray(Arrays.asList(requested))));permissions.onAndroidPermissionsRequest(s,requested,callback);}
        @Override public GeckoResult<Integer> onContentPermissionRequest(GeckoSession s,ContentPermission permission){navigation(s,"contentPermission",permission.uri,J.obj("permission",permission.permission,"value",permission.value,"privateMode",permission.privateMode,"thirdPartyOrigin",permission.thirdPartyOrigin));return permissions.onContentPermissionRequest(s,permission);}
        @Override public void onMediaPermissionRequest(GeckoSession s,String target,MediaSource[] video,MediaSource[] audio,MediaCallback callback){navigation(s,"mediaPermission",target,null);permissions.onMediaPermissionRequest(s,target,video,audio,callback);}
      });
      sdk.getWebExtensionController().setMessageDelegate(extension,new WebExtension.MessageDelegate(){
        @Override public void onConnect(WebExtension.Port port){
          if(finished||guardSession!=sdk||port.sender.session!=sdk||port.sender.environmentType!=WebExtension.MessageSender.ENV_TYPE_CONTENT_SCRIPT||!port.sender.isTopLevel()||!guardDocument.equals(port.sender.url))return;
          reportPut(guardEvidence,"nativePort",J.obj("nativeSession",System.identityHashCode(port.sender.session),"senderUrl",port.sender.url,"topLevel",port.sender.isTopLevel(),"environmentType",port.sender.environmentType,"connectedAt",SystemClock.elapsedRealtime()));
          port.setDelegate(new WebExtension.PortDelegate(){
            @Override public void onPortMessage(Object message,WebExtension.Port incoming){
              if(finished||incoming!=port||view.current!=guardSession||!guardDocument.equals(view.getUrl())||!(message instanceof JSONObject))return;
              JSONObject data=(JSONObject)message;if(!"guardResult".equals(data.optString("kind")))return;
              try{JSONObject observed=data.getJSONObject("value");if(!guardNonce.equals(observed.getString("nonce")))throw new IOException("Guard event nonce mismatch");reportPut(guardEvidence,"observed",observed);reportPut(guardEvidence,"nativeCallbackAt",SystemClock.elapsedRealtime());completeGuard();}catch(Throwable failure){finish(failure);}
            }
          });
        }
      },"identityguard");
      if(!announced){announced=true;handler.post(()->{if(!finished)beginCase();});}
      return sdk;
    }
  }
  void navigation(GeckoSession sdk,String kind,String target,JSONObject detail){
    if(finished)return;
    if(navigation.length()>=64){navigationDropped++;return;}
    String name="unowned";for(Map.Entry<String,GeckoSession> item:targets.entrySet())if(item.getValue()==sdk){name=item.getKey();break;}
    navigation.put(J.obj("kind",kind,"url",target,"session",System.identityHashCode(sdk),"name",name,"case",serial,"at",SystemClock.elapsedRealtime(),"detail",detail));
  }
  FixtureView createFixtureView(Context context,ChatSession session){return new FixtureView(context,session);}
  void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));if(!pass)throw new AssertionError(name);}
  @Override public void onCreate(Bundle state){
    super.onCreate(state);
    if(!"local.pocketchat.test".equals(getPackageName()))throw new SecurityException("Integration package only");
    source=getIntent().getStringExtra("sourceCommit");run=getIntent().getStringExtra("runNonce");
    storage.execute(()->{
      try{
        if(source==null||!source.matches("[0-9a-f]{40}")||run==null||!run.matches("[0-9a-f]{32}"))throw new IOException("Exact source and run nonce required");
        JSONObject preparedIdentity=IntegrationBuildIdentity.read(this);
        JSONObject preparedSdk=NormalCaretSdkReceipt.read(this);
        NormalCaretSdkReceipt.requireInstalled(preparedSdk,preparedIdentity);
        if(!source.equals(preparedIdentity.optString("sourceCommit"))||preparedIdentity.optBoolean("dirtySource",true)||!SDK.equals(preparedIdentity.optString("sdkCoordinate")))throw new IOException("Installed clean source/SDK identity mismatch");
        JSONObject preparedBaseline=J.obj("api","GeckoSession.getDefaultUserAgent()","scope","sdk-build-mobile-default","userAgent",GeckoSession.getDefaultUserAgent(),"androidSdk",Build.VERSION.SDK_INT,"androidRelease",Build.VERSION.RELEASE,"ignoresSessionOverrides",true,"runtimeAcknowledgement",false);
        NormalCaretSdkReceipt.copySdkFields(preparedSdk,preparedBaseline);
        LocalSite preparedSite=new LocalSite();
        handler.post(()->{if(finished){preparedSite.close();return;}buildIdentity=preparedIdentity;sdkBuildIdentity=preparedSdk;sdkUserAgentBaseline=preparedBaseline;site=preparedSite;origin="http://127.0.0.1:"+site.socket.getLocalPort();site.start();openBrowser();});
      }catch(Throwable failure){handler.post(()->finish(failure));}
    });
    handler.postDelayed(()->{if(!finished&&caseIndex<0)finish(new IOException("Official Gecko startup did not become ready"));},60000);
  }
  void openBrowser(){
    if(finished)return;
    try{
      Context context=new PrivateContext(getApplicationContext());
      context.getSharedPreferences("chat",0).edit().putString("networkMode","external").putString("proxy","").putBoolean("requireExternalVpn",false).putBoolean("networkConfigured",false).putInt("privacyLevel",0).putBoolean("backgroundWait",false).commit();
      ProfileCatalog.get(context).created(Profiles.slot(context));
      ChatSession.browserFactory=(c,s)->createFixtureView(c,s);owner=ChatSession.get(context);view=(FixtureView)owner.web;
      owner.handler.removeCallbacks(owner.tick);owner.networkReady=true;owner.offline=false;owner.uiVisible=true;owner.guard.setBlocked(false);
      LinearLayout layout=new LinearLayout(this);layout.setOrientation(LinearLayout.VERTICAL);
      TextView label=new TextView(this);label.setText("Gecko SDK identity prototype · controlled local observations only");layout.addView(label);
      view.setHost(this);layout.addView(view,new LinearLayout.LayoutParams(-1,0,1));setContentView(layout);
    }catch(Throwable failure){finish(failure);}
  }
  static String normalize(String tag){Locale value=Locale.forLanguageTag(tag);return value.getLanguage()+(value.getCountry().isEmpty()?"":"-"+value.getCountry());}
  String reportFile(){return FILE;}
  String reportTag(){return TAG;}
  boolean caseDesktop(){return caseIndex==1;}
  void prepareCase(int ticket,Runnable prepared){
    // configure() may prepare production locales in 1.7. The prototype then
    // makes its own explicit SDK request, without claiming production template
    // application. The separate template fixture overrides this hook.
    view.configure(desktop,0);view.runtime.getSettings().setLocales(requestedLocales.clone());
    check("Case "+caseIndex+" retains the Java locale request",Arrays.equals(requestedLocales,view.runtime.getSettings().getLocales()));prepared.run();
  }
  void completeCase(JSONArray sessions,Runnable next){next.run();}
  void configureReport(JSONObject report){}
  /** Resource fixtures opt in separately; identity context endpoints stay unchanged. */
  String resourceFixtureDocument(String method,Map<String,String> query){return null;}
  void resourceFixtureResponse(int connection,String parsedRequestLine,String method,String target,
      Map<String,String> query,Map<String,String> headers,String document,long requestAt,long responseAt)throws IOException{}
  void beginCase(){
    if(finished)return;
    try{
      if(caseDeadline!=null)handler.removeCallbacks(caseDeadline);
      caseIndex++;if(caseIndex==4){beginGuard();return;}
      final int ticket=++serial;requestedAt=SystemClock.elapsedRealtime();received.clear();nativeAgents.clear();rawObservations.clear();targets.clear();
      requestedLocales=new String[]{caseIndex==0||caseIndex==3?"en-US":caseIndex==1?"ja-JP":"zh-Hant-TW"};
      normalizedLanguage=normalize(requestedLocales[0]);desktop=caseDesktop();
      check("Case "+caseIndex+" uses the open production Gecko bridge",view.ready&&view.privacyReady&&view.current!=null&&view.current.isOpen());
      caseDeadline=()->{if(!finished&&serial==ticket)finish(new IOException("Case "+caseIndex+" did not return complete actual context/header observations"));};handler.postDelayed(caseDeadline,15000);
      prepareCase(ticket,()->beginObservations(ticket));
    }catch(Throwable failure){finish(failure);}
  }
  void beginObservations(int ticket){
    if(finished||serial!=ticket)return;
    try{
      targets.put("primary",view.current);
      if(caseIndex==3){GeckoSession second=view.newSession();second.open(view.runtime);second.getSettings().setUserAgentMode(GeckoSessionSettings.USER_AGENT_MODE_DESKTOP);targets.put("secondary",second);}
      for(Map.Entry<String,GeckoSession> item:new ArrayList<>(targets.entrySet())){
        String name=item.getKey();GeckoSession sdk=item.getValue();
        sdk.getUserAgent().accept(ua->{
          if(finished||serial!=ticket||targets.get(name)!=sdk)return;
          nativeAgents.put(name,J.obj("userAgent",ua,"session",System.identityHashCode(sdk),"runtime",System.identityHashCode(view.runtime),"requestedLocales",new JSONArray(Arrays.asList(requestedLocales)),"getterLocales",new JSONArray(Arrays.asList(view.runtime.getSettings().getLocales())),"getterScope","Java requested value; not content acknowledgement","expectedSdkNormalizedLanguage",normalizedLanguage,"userAgentMode",sdk.getSettings().getUserAgentMode(),"viewportMode",sdk.getSettings().getViewportMode()));
          String target=origin+"/page?run="+run+"&case="+ticket+"&session="+name;
          if("primary".equals(name))view.loadUrl(target);else sdk.loadUri(target);
        },failure->{if(!finished&&serial==ticket)finish(new IOException("Official user-agent getter failed",failure));});
      }
    }catch(Throwable failure){finish(failure);}
  }
  void observed(int ticket,String name,JSONObject value){
    if(finished||ticket!=serial||!targets.containsKey(name)||received.containsKey(name))return;
    try{
      if(!run.equals(value.optString("run"))||value.optInt("case")!=ticket||!name.equals(value.optString("session")))throw new IOException("Observation ownership mismatch");
      rawObservations.put(name,value);JSONObject nativeValue=nativeAgents.get(name);if(nativeValue==null)throw new IOException("Native session request was not captured");
      received.put(name,J.obj("name",name,"native",nativeValue,"observed",value,"requestHeaders",site.records(ticket,name)));
      if(received.size()!=targets.size())return;
      // Network/Worker completion order is nondeterministic. Preserve the raw
      // arrival records, then run the same strict checks once in target order.
      JSONArray sessions=new JSONArray(),mismatches=new JSONArray();for(String targetName:targets.keySet()){JSONObject row=received.get(targetName);validateSession(row);sessions.put(row);if(row.getJSONObject("userAgentScope").getBoolean("workerFetchHeaderMismatch"))mismatches.put(targetName);}
      if(caseIndex==3)check("Two sessions share this runtime locale, not separate environment evidence",received.get("primary").getJSONObject("observed").getJSONObject("parent").getString("language").equals(received.get("secondary").getJSONObject("observed").getJSONObject("parent").getString("language")));
      cases.put(J.obj("index",caseIndex,"serial",ticket,"requestedAt",requestedAt,"completedAt",SystemClock.elapsedRealtime(),"sessions",sessions,"status","passed","workerFetchMismatchSessions",mismatches,"fullTemplateAcceptance",false));
      completeCase(sessions,()->handler.post(this::beginCase));
    }catch(Throwable failure){finish(failure);}
  }
  void validateSession(JSONObject observationRow)throws Exception{
    String name=observationRow.getString("name");JSONObject value=observationRow.getJSONObject("observed"),nativeValue=observationRow.getJSONObject("native");JSONArray wire=observationRow.getJSONArray("requestHeaders");JSONObject parent=value.getJSONObject("parent");String ua=nativeValue.getString("userAgent");
      boolean expectedDesktop=desktop||"secondary".equals(name);
      check("Case "+caseIndex+" "+name+" observes the requested official UA mode",expectedDesktop?!ua.contains("Android"):ua.contains("Android"));
      check("Case "+caseIndex+" "+name+" has all main/frame/worker fields",complete(parent)&&complete(value.getJSONObject("frame"))&&complete(value.getJSONObject("worker"))&&complete(value.getJSONObject("blobWorker")));
      for(String context:new String[]{"parent","frame","worker","blobWorker"}){
        JSONObject signal=value.getJSONObject(context);
        check("Case "+caseIndex+" "+name+" "+context+" actual UA matches native session",ua.equals(signal.getString("ua"))&&ua.contains("Firefox/157."));
        check("Case "+caseIndex+" "+name+" "+context+" observes SDK normalized language",normalizedLanguage.equalsIgnoreCase(signal.getString("language")));
        check("Case "+caseIndex+" "+name+" "+context+" agrees on observed language list",parent.getJSONArray("languages").toString().equals(signal.getJSONArray("languages").toString()));
        check("Case "+caseIndex+" "+name+" "+context+" agrees on observed timezone",parent.getString("zone").equals(signal.getString("zone"))&&parent.getInt("offset")==signal.getInt("offset"));
      }
      boolean workerMatchesSession=true;
      for(String role:new String[]{"page","frame","worker-script","page-fetch","worker-fetch","blob-worker-fetch"}){
        JSONObject header=null;for(int i=0;i<wire.length();i++){JSONObject row=wire.getJSONObject(i);if(role.equals(row.optString("role"))){if(header!=null)throw new IOException("Duplicate controlled request role "+role);header=row;}}
        boolean workerFetch="worker-fetch".equals(role)||"blob-worker-fetch".equals(role);
        String expectedHeaderUa=workerFetch?sdkUserAgentBaseline.getString("userAgent"):ua;
        check("Case "+caseIndex+" "+name+" "+role+" has real server request headers",header!=null&&expectedHeaderUa.equals(header.getString("userAgent"))&&normalizedLanguage.equalsIgnoreCase(header.getString("acceptLanguage").split(",",2)[0].split(";",2)[0].trim()));
        if(workerFetch)workerMatchesSession&=ua.equals(header.getString("userAgent"));
      }
      JSONObject userAgentScope=J.obj("documentHeadersMatchSession",true,"workerFetchHeadersMatchSdkDefault",true,"workerFetchHeadersMatchSession",workerMatchesSession,"workerFetchHeaderMismatch",!workerMatchesSession,"observedUserAgentUniform",workerMatchesSession,"fullTemplateAcceptance",false);
      observationRow.put("userAgentScope",userAgentScope);
  }
  static boolean complete(JSONObject signal){
    return signal.opt("ua") instanceof String&&!signal.optString("ua").isEmpty()&&signal.opt("language") instanceof String&&!signal.optString("language").isEmpty()&&signal.optJSONArray("languages")!=null&&signal.optJSONArray("languages").length()>0&&signal.opt("cpu") instanceof Number&&signal.optInt("cpu")>0&&signal.opt("offset") instanceof Number&&signal.opt("zone") instanceof String&&!signal.optString("zone").isEmpty()&&signal.opt("intlLocale") instanceof String&&!signal.optString("intlLocale").isEmpty();
  }
  void beginGuard(){
    try{
      guardSession=view.current;guardDocument=view.getUrl();guardNonce=UUID.randomUUID().toString().replace("-","");
      if(guardSession==null||guardSession!=targets.get("primary")||!guardSession.isOpen()||!guardDocument.equals(origin+"/page?run="+run+"&case="+serial+"&session=primary"))throw new IOException("Guard probe lost its completed native document");
      guardFetchUrl=origin+"/echo?run="+guardNonce+"&case="+serial+"&session=primary&kind=guard-fetch";guardWorkerUrl=origin+"/worker?run="+guardNonce+"&case="+serial+"&session=primary";
      guardEvidence=J.obj("nonce",guardNonce,"document",guardDocument,"nativeSession",System.identityHashCode(guardSession),"fetchUrl",guardFetchUrl,"workerUrl",guardWorkerUrl,"requestedAt",SystemClock.elapsedRealtime(),"beforeServer",site.diagnostics(),"beforeHeaderCount",site.allRecords().length(),"scope","Actual main-world fetch and Dedicated HTTP Worker attempts after closing the production guard; event results returned through a fixture-only official SDK native-message namespace");
      owner.guard.setBlocked(true);
      caseDeadline=()->{if(!finished)finish(new IOException("Closed guard did not return actual fetch/Worker terminal events"));};handler.postDelayed(caseDeadline,15000);
      JSONObject config=J.obj("nonce",guardNonce,"fetchUrl",guardFetchUrl,"workerUrl",guardWorkerUrl);
      view.evaluateJavascript("(()=>{const c="+config+";const p=browser.runtime.connectNative('identityguard');addEventListener('pocket-identity-guard-result',e=>{if(typeof e.detail!=='string')return;const v=JSON.parse(e.detail);if(v.nonce===c.nonce)p.postMessage({kind:'guardResult',value:v})},{once:true});dispatchEvent(new CustomEvent('pocket-identity-guard',{detail:JSON.stringify(c)}));return 'guard-armed'})()",raw->{
        if(finished)return;
        try{if(view.current!=guardSession||!guardDocument.equals(view.getUrl())||!"\"guard-armed\"".equals(raw))throw new IOException("Guard probe did not arm in its actual native document");reportPut(guardEvidence,"armCallback",raw);completeGuard();}catch(Throwable failure){finish(failure);}
      });
    }catch(Throwable failure){finish(failure);}
  }
  void completeGuard(){
    if(finished||!guardEvidence.has("armCallback")||!guardEvidence.has("observed"))return;
    try{
      JSONObject observed=guardEvidence.getJSONObject("observed"),before=guardEvidence.getJSONObject("beforeServer"),after=site.diagnostics();
      reportPut(guardEvidence,"blockedRoutes",guardRoutes);reportPut(guardEvidence,"blockedRoutesDropped",guardRoutesDropped);reportPut(guardEvidence,"afterServer",after);reportPut(guardEvidence,"afterHeaderCount",site.allRecords().length());
      check("Closed guard route evidence did not overflow",guardRoutesDropped==0);
      for(String target:new String[]{guardFetchUrl,guardWorkerUrl}){boolean found=false;for(int i=0;i<guardRoutes.length();i++){JSONObject row=guardRoutes.getJSONObject(i),route=row.getJSONObject("route");if(target.equals(row.optString("url"))&&!row.optBoolean("guardAllowed",true)&&"socks".equals(route.optString("type"))&&"127.0.0.1".equals(route.optString("host"))&&route.optInt("port")==9)found=true;}check("Closed guard returns the blocked actual route for "+(target.equals(guardFetchUrl)?"fetch GET":"HTTP Worker"),found);}
      check("Closed guard receives owned actual native callback",view.current==guardSession&&guardDocument.equals(view.getUrl())&&guardNonce.equals(observed.getString("nonce"))&&guardFetchUrl.equals(observed.getString("fetchUrl"))&&guardWorkerUrl.equals(observed.getString("workerUrl")));
      check("Closed guard fetch terminates in an actual network rejection","network-error".equals(observed.getJSONObject("fetch").optString("outcome"))&&!observed.getJSONObject("fetch").optString("name").isEmpty());
      check("Closed guard HTTP Worker terminates in a trusted error event","error".equals(observed.getJSONObject("worker").optString("outcome"))&&observed.getJSONObject("worker").optBoolean("trusted"));
      check("Closed guard accepts no new controlled TCP connection",after.getInt("acceptedConnections")==before.getInt("acceptedConnections"));
      check("Closed guard parses no new controlled request",after.getInt("parsedRequests")==before.getInt("parsedRequests")&&site.allRecords().length()==guardEvidence.getInt("beforeHeaderCount"));
      check("Controlled listener remains bound after actual guard rejection",after.getBoolean("bound")&&!after.getBoolean("closed"));
      reportPut(guardEvidence,"completedAt",SystemClock.elapsedRealtime());reportPut(guardEvidence,"status","passed");finish(null);
    }catch(Throwable failure){finish(failure);}
  }
  void finish(Throwable failure){
    if(finished)return;finished=true;if(caseDeadline!=null)handler.removeCallbacks(caseDeadline);
    if(guardSession!=null){reportPut(guardEvidence,"blockedRoutes",guardRoutes);reportPut(guardEvidence,"blockedRoutesDropped",guardRoutesDropped);reportPut(guardEvidence,"afterServer",site.diagnostics());reportPut(guardEvidence,"afterHeaderCount",site.allRecords().length());if(failure!=null)reportPut(guardEvidence,"status","failed");}
    JSONObject report=J.obj("schema",1,"status",failure==null?"passed":"failed","diagnosticOnly",true,"releaseAcceptance",false,"synthetic",true,"actualAndroidExecution",true,"actualGeckoExecution",view!=null&&view.ready,"publicNetworkTraffic",false,"sourceCommit",source,"runNonce",run,"buildIdentity",buildIdentity,"engineVersion",GeckoWebView.VERSION,"androidSdk",Build.VERSION.SDK_INT,"abis",new JSONArray(Arrays.asList(Build.SUPPORTED_ABIS)),"pid",android.os.Process.myPid(),"origin",origin,"cases",cases,"checks",checks,"passed",passedChecks(),"total",checks.length(),"routes",routes,"nativeRuntimeScope","Locale settings belong to one runtime shared by these sessions","environmentIsolation","Separate Android process/profile isolation is unverified by this prototype","independentTimezone","unsupported; no timezone override requested or applied","deepCustomControls","Independent timezone/Canvas/WebGL/audio/font controls not implemented","uncovered",J.arr("cross-origin frame","Shared Worker","Service Worker","RFP compatibility","real account login","native IME","separate environment isolation","restart persistence"),"scope","Actual controlled page-main/same-origin frame/Dedicated HTTP and Blob Worker readings plus first-party server request headers through the production guarded bridge. No template applied/observed repository acknowledgement.");
    try{NormalCaretSdkReceipt.copySdkFields(sdkBuildIdentity,report);}catch(Throwable identityFailure){reportPut(report,"status","failed");reportPut(report,"error",String.valueOf(identityFailure));reportPut(report,"failureType",identityFailure.getClass().getName());}
    reportPut(report,"nativeNavigation",navigation);reportPut(report,"nativeNavigationDropped",navigationDropped);
    reportPut(report,"sdkUserAgentBaseline",sdkUserAgentBaseline);
    reportPut(report,"userAgentCapability",J.obj("sessionSettingsScope","top-browsing-context","workerFetchHeaderScope","sdk-build-mobile-default","runtimeUserAgentSetterAvailable",false,"fullTemplateAcceptance",false,"description","Session UA is observed in main/frame/Dedicated Worker JavaScript and document/script/page-fetch headers. Dedicated HTTP and Blob Worker fetch headers are checked against the independent SDK build mobile default; desktop session UA consistency for these requests is unsupported. The static default getter is not a native runtime acknowledgement."));
    reportPut(report,"guardEvidence",guardEvidence);
    if(view!=null&&view.runtime!=null){GeckoRuntimeSettings settings=view.runtime.getSettings();reportPut(report,"runtimeNetworkRequests",J.obj("lnaEnabled",settings.getLnaEnabled()==null?JSONObject.NULL:settings.getLnaEnabled(),"lnaBlocking",settings.getLnaBlocking()==null?JSONObject.NULL:settings.getLnaBlocking(),"scope","Java requested values; null means no requested override and does not establish native defaults"));}
    android.security.NetworkSecurityPolicy policy=android.security.NetworkSecurityPolicy.getInstance();
    reportPut(report,"androidCleartextPolicy",J.obj("globalPermitted",policy.isCleartextTrafficPermitted(),"loopbackPermitted",policy.isCleartextTrafficPermitted("127.0.0.1"),"localhostPermitted",policy.isCleartextTrafficPermitted("localhost"),"scope","Observed Android policy only; no policy override"));
    if(site!=null){reportPut(report,"allRequestHeaders",site.allRecords());reportPut(report,"localServer",site.diagnostics());}
    if(failure!=null){reportPut(report,"error",String.valueOf(failure));reportPut(report,"failureType",failure.getClass().getName());reportPut(report,"currentCase",caseIndex);reportPut(report,"partialObservations",new JSONObject(rawObservations));reportPut(report,"nativeRequests",new JSONObject(nativeAgents));}
    // Freeze the report on the callback thread before teardown can append
    // more route observations. The storage worker must not traverse live JSON.
    configureReport(report);final String reportJson=report.toString();Log.i(reportTag(),reportJson);
    if(view!=null)view.destroy();if(owner!=null){owner.handler.removeCallbacks(owner.tick);owner.deleted=true;}if(site!=null)site.close();
    storage.execute(()->{try{File file=new File(getFilesDir(),reportFile()),tmp=new File(getFilesDir(),reportFile()+".tmp");try(FileOutputStream out=new FileOutputStream(tmp)){out.write(reportJson.getBytes(StandardCharsets.UTF_8));out.getFD().sync();}if(!tmp.renameTo(file))throw new IOException("Atomic report publication failed");}catch(Throwable error){Log.e(reportTag(),"Report export failed",error);}finally{storage.shutdown();}});
  }
  int passedChecks(){int count=0;for(int i=0;i<checks.length();i++)if(checks.optJSONObject(i).optBoolean("pass"))count++;return count;}
  static void reportPut(JSONObject object,String key,Object value){try{object.put(key,value);}catch(JSONException impossible){throw new IllegalStateException(impossible);}}
  @Override protected void onDestroy(){if(!finished)finish(new IOException("Prototype Activity destroyed before completion"));super.onDestroy();}

  final class LocalSite {
    final ServerSocket socket=new ServerSocket(0,8,InetAddress.getByName("127.0.0.1"));
    final ExecutorService clients=new ThreadPoolExecutor(4,4,0,TimeUnit.MILLISECONDS,new ArrayBlockingQueue<>(8));final List<JSONObject> wire=new ArrayList<>();
    final Set<Socket> live=Collections.synchronizedSet(new HashSet<>());volatile boolean closed;
    final List<JSONObject> failures=new ArrayList<>();int accepted,parsed,completed,rejected,failuresDropped;
    LocalSite()throws IOException{}
    void start(){new Thread(()->{while(!closed)try{Socket client=socket.accept();int connection;synchronized(this){connection=++accepted;}synchronized(live){if(closed||live.size()>=12){synchronized(this){rejected++;}client.close();continue;}live.add(client);}try{clients.execute(()->serve(client,connection));}catch(RejectedExecutionException failure){synchronized(this){rejected++;}serverFailure(connection,"dispatch","",failure);live.remove(client);client.close();}}catch(IOException failure){if(!closed){serverFailure(0,"accept","",failure);handler.post(()->finish(new IOException("Local fixture accept failed",failure)));}}},"identity-local-server").start();}
    synchronized JSONArray records(int ticket,String name){JSONArray result=new JSONArray();for(JSONObject row:wire)if(row.optInt("case")==ticket&&name.equals(row.optString("session")))result.put(row);return result;}
    synchronized JSONArray allRecords(){JSONArray result=new JSONArray();for(JSONObject row:wire)result.put(row);return result;}
    synchronized JSONObject diagnostics(){return J.obj("address",socket.getInetAddress().getHostAddress(),"port",socket.getLocalPort(),"bound",socket.isBound(),"closed",closed,"acceptedConnections",accepted,"parsedRequests",parsed,"completedConnections",completed,"rejectedConnections",rejected,"failures",new JSONArray(failures),"failuresDropped",failuresDropped,"scope","Bounded actual listener/protocol state; accepted TCP does not imply a Gecko request or context observation");}
    synchronized void serverFailure(int connection,String stage,String request,Throwable failure){if(failures.size()>=16){failuresDropped++;return;}String message=String.valueOf(failure);failures.add(J.obj("connection",connection,"stage",stage,"request",request.substring(0,Math.min(1024,request.length())),"failureType",failure.getClass().getName(),"error",message.substring(0,Math.min(1024,message.length())),"at",SystemClock.elapsedRealtime()));}
    void serve(Socket client,int connection){
      String stage="requestLine",first="";
      try(Socket ignored=client){
        client.setSoTimeout(5000);InputStream in=client.getInputStream();first=line(in);String[] request=first.split(" ");if(request.length!=3)throw new IOException("Malformed HTTP request");
        URI uri=URI.create(request[1]);Map<String,String> query=query(uri.getRawQuery()),headers=new LinkedHashMap<>();int headerBytes=first.length();
        stage="headers";
        for(String value;(value=line(in)).length()>0;){headerBytes+=value.length();if(headerBytes>16384)throw new IOException("Oversized request headers");int split=value.indexOf(':');if(split<1)throw new IOException("Malformed header");headers.put(value.substring(0,split).toLowerCase(Locale.ROOT),value.substring(split+1).trim());}
        if(headers.containsKey("transfer-encoding"))throw new IOException("Chunked fixture request unsupported");
        stage="body";
        int count=Integer.parseInt(headers.getOrDefault("content-length","0"));if(count<0||count>32768)throw new IOException("Oversized observation");byte[] body=new byte[count];new DataInputStream(in).readFully(body);
        synchronized(this){parsed++;}stage="response";
        if("/favicon.ico".equals(uri.getPath())){respond(client,404,"text/plain","");return;}
        if("/resource".equals(uri.getPath())){
          String document=resourceFixtureDocument(request[0],query);
          if(document==null){respond(client,403,"text/plain","Unknown resource fixture");return;}
          long requestAt=SystemClock.elapsedRealtime();respond(client,200,"text/html",document);
          resourceFixtureResponse(connection,first,request[0],request[1],query,headers,document,requestAt,SystemClock.elapsedRealtime());return;
        }
        if(!run.equals(query.get("run"))||!query.getOrDefault("case","").matches("[1-4]")||!Arrays.asList("primary","secondary").contains(query.get("session"))){respond(client,403,"text/plain","Unknown fixture case");return;}
        int ticket=Integer.parseInt(query.get("case"));String name=query.get("session"),path=uri.getPath();
        String role="/page".equals(path)?"page":"/frame".equals(path)?"frame":"/worker".equals(path)?"worker-script":"/echo".equals(path)?query.getOrDefault("kind",""):"";
        if(!role.isEmpty())synchronized(this){if(wire.size()>=64)throw new IOException("Too many fixture requests");wire.add(J.obj("sequence",wire.size()+1,"case",ticket,"session",name,"role",role,"method",request[0],"path",request[1],"userAgent",headers.getOrDefault("user-agent",""),"acceptLanguage",headers.getOrDefault("accept-language",""),"at",SystemClock.elapsedRealtime()));}
        String config=J.obj("run",run,"case",ticket,"session",name,"origin",origin,"query",uri.getRawQuery()).toString();
        if("GET".equals(request[0])&&"/page".equals(path))respond(client,200,"text/html",page(config));
        else if("GET".equals(request[0])&&"/frame".equals(path))respond(client,200,"text/html","<!doctype html><script>"+signal()+"parent.postMessage({kind:'identity-frame',value:read()},location.origin)</script>");
        else if("GET".equals(request[0])&&"/worker".equals(path))respond(client,200,"application/javascript",worker(config,"worker-fetch"));
        else if("GET".equals(request[0])&&"/echo".equals(path))respond(client,200,"application/json","{\"ok\":true}");
        else if("POST".equals(request[0])&&"/report".equals(path)){JSONObject value=new JSONObject(new String(body,StandardCharsets.UTF_8));respond(client,200,"application/json","{\"ok\":true}");handler.post(()->observed(ticket,name,value));}
        else respond(client,404,"text/plain","");
      }catch(Throwable failure){if(!closed){serverFailure(connection,stage,first,failure);handler.post(()->finish(failure));}}finally{synchronized(this){completed++;}live.remove(client);}
    }
    void close(){closed=true;try{socket.close();}catch(IOException ignored){}synchronized(live){for(Socket client:live)try{client.close();}catch(IOException ignored){}}clients.shutdownNow();}
  }
  static String line(InputStream input)throws IOException{ByteArrayOutputStream bytes=new ByteArrayOutputStream();for(int value;(value=input.read())!=-1;){if(value=='\n')return bytes.toString(StandardCharsets.ISO_8859_1.name()).replace("\r","");if(bytes.size()>=8192)throw new IOException("Oversized HTTP line");bytes.write(value);}throw new EOFException();}
  static Map<String,String> query(String raw)throws IOException{Map<String,String> result=new LinkedHashMap<>();if(raw!=null)for(String item:raw.split("&")){String[] pair=item.split("=",2);String key=URLDecoder.decode(pair[0],"UTF-8"),value=pair.length==2?URLDecoder.decode(pair[1],"UTF-8"):"";if(result.put(key,value)!=null)throw new IOException("Duplicate fixture query");}return result;}
  static void respond(Socket socket,int status,String type,String value)throws IOException{byte[] body=value.getBytes(StandardCharsets.UTF_8);OutputStream out=socket.getOutputStream();out.write(("HTTP/1.1 "+status+" Fixture\r\nContent-Type: "+type+"; charset=utf-8\r\nContent-Length: "+body.length+"\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n").getBytes(StandardCharsets.US_ASCII));out.write(body);out.flush();}
  static String signal(){return "function read(){const r=Intl.DateTimeFormat().resolvedOptions();return {ua:navigator.userAgent,language:navigator.language,languages:Array.from(navigator.languages),cpu:navigator.hardwareConcurrency,memory:navigator.deviceMemory??null,offset:new Date().getTimezoneOffset(),zone:r.timeZone,intlLocale:r.locale,origin:location.origin,at:performance.now()}};";}
  static String worker(String config,String role){return "const c="+config+";"+signal()+"fetch(c.origin+'/echo?'+c.query+'&kind="+role+"',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('worker echo failed');return r.json()}).then(()=>postMessage(read())).catch(e=>postMessage({error:String(e)}));";}
  static String page(String config){
    String blob=worker(config,"blob-worker-fetch");
    return "<!doctype html><meta charset=utf-8><title>Controlled identity prototype</title><h1>Official Gecko observations</h1><script>const c="+config+";"+signal()
      +"const frame=document.createElement('iframe');const fp=new Promise(resolve=>addEventListener('message',e=>{if(e.origin===c.origin&&e.source===frame.contentWindow&&e.data?.kind==='identity-frame')resolve(e.data.value)}));frame.src='/frame?'+c.query;document.body.append(frame);"
      +"function observe(w){return new Promise(resolve=>{w.onmessage=e=>{w.terminate();resolve(e.data)};w.onerror=e=>{w.terminate();resolve({error:e.message})}})}"
      +"const worker=observe(new Worker('/worker?'+c.query));const blobUrl=URL.createObjectURL(new Blob(["+JSONObject.quote(blob)+"],{type:'application/javascript'}));const blobWorker=observe(new Worker(blobUrl));"
      +"Promise.all([fp,worker,blobWorker]).then(async([frame,worker,blobWorker])=>{URL.revokeObjectURL(blobUrl);const response=await fetch('/echo?'+c.query+'&kind=page-fetch',{cache:'no-store'});if(!response.ok)throw Error('page echo failed');await response.json();return fetch('/report?'+c.query,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({run:c.run,case:c.case,session:c.session,parent:read(),frame,worker,blobWorker,provenance:'controlled-page-main-world'})})}).catch(e=>document.body.append(String(e)));"
      +"let guardStarted=false;addEventListener('pocket-identity-guard',e=>{if(guardStarted||c.case!==4||typeof e.detail!=='string')return;const g=JSON.parse(e.detail);if(!/^[0-9a-f]{32}$/.test(g.nonce)||g.nonce===c.run||g.fetchUrl!==c.origin+'/echo?run='+g.nonce+'&case=4&session='+c.session+'&kind=guard-fetch'||g.workerUrl!==c.origin+'/worker?run='+g.nonce+'&case=4&session='+c.session)return;guardStarted=true;const f=fetch(g.fetchUrl,{cache:'no-store'}).then(r=>({outcome:'http-response',status:r.status,at:performance.now()})).catch(error=>({outcome:'network-error',name:String(error.name),message:String(error.message),at:performance.now()}));const w=new Promise(resolve=>{let instance;try{instance=new Worker(g.workerUrl);instance.onmessage=e=>{instance.terminate();resolve({outcome:'message',at:performance.now()})};instance.onerror=e=>{instance.terminate();resolve({outcome:'error',trusted:e.isTrusted,message:String(e.message??''),at:performance.now()})}}catch(error){resolve({outcome:'constructor-error',name:String(error.name),at:performance.now()})}});Promise.all([f,w]).then(([fetch,worker])=>dispatchEvent(new CustomEvent('pocket-identity-guard-result',{detail:JSON.stringify({nonce:g.nonce,fetchUrl:g.fetchUrl,workerUrl:g.workerUrl,fetch,worker,at:performance.now()})})))})</script>";
  }
}
