package local.pocketchat;

import android.app.Activity;
import android.content.Context;
import android.content.ContextWrapper;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.util.AtomicFile;
import android.util.Log;
import android.webkit.ValueCallback;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.LinearLayout;
import android.widget.TextView;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.lang.reflect.Field;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Base64;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import org.json.JSONArray;
import org.json.JSONObject;
import org.mozilla.geckoview.AllowOrDeny;
import org.mozilla.geckoview.GeckoResult;
import org.mozilla.geckoview.GeckoSession;
import org.mozilla.geckoview.WebExtension;
import org.mozilla.geckoview.WebRequestError;

/** Actual test-APK Gecko/HTTPS observations; never a real ChatGPT or phone verdict. */
public final class FingerprintFollowupIntegrationActivity extends Activity {
  static final String FILE="fingerprint-followup-results.json",TAG="PocketFingerprintFollowup";
  static final String SOURCE_DRIVER_GUARD="if (location.protocol !== 'https:' || location.hostname !== 'chatgpt.com') return false;";
  final Handler handler=new Handler(Looper.getMainLooper());
  final ExecutorService worker=Executors.newSingleThreadExecutor();
  final AtomicBoolean concluded=new AtomicBoolean();
  final JSONArray checks=new JSONArray(),cases=new JSONArray(),events=new JSONArray(),routes=new JSONArray(),normalizations=new JSONArray(),loads=new JSONArray(),preflightDriverResults=new JSONArray();
  String source,nonce,origin,redirectOrigin,chat,semanticChat;int routeDrops,eventDrops,normalizationDrops,preflightDriverDrops;
  JSONObject build=new JSONObject(),sdk=new JSONObject(),sourceDriverAdapter=new JSONObject();
  String stage="created";boolean sourceDriverGuardRecorded;
  ChatSession owner;FixtureView view;
  WebExtension.Port heldRoutePort;WebExtension.PortDelegate originalRouteDelegate;JSONObject heldProtectionReply;
  int droppedProtectionReplies;boolean dropProtectionReplies;

  interface Work<T>{T run()throws Exception;}
  <T>T ui(Work<T> work)throws Exception{
    if(Looper.myLooper()==Looper.getMainLooper())return work.run();
    CompletableFuture<T> result=new CompletableFuture<>();
    handler.post(()->{try{result.complete(work.run());}catch(Throwable failure){result.completeExceptionally(failure);}});
    return result.get(15,TimeUnit.SECONDS);
  }
  void await(String label,Work<Boolean> condition,long budget)throws Exception{
    long end=SystemClock.elapsedRealtime()+budget;
    while(!condition.run()){
      if(concluded.get())throw new IOException("Diagnostic already concluded");
      if(SystemClock.elapsedRealtime()>=end)throw new IOException(label+" timed out");
      Thread.sleep(80);
    }
  }
  void check(String name,boolean pass)throws IOException{
    synchronized(checks){checks.put(J.obj("name",name,"pass",pass));}
    if(!pass)throw new IOException(name);
  }
  void event(String kind,JSONObject value){synchronized(events){if(events.length()<160)events.put(J.obj("kind",kind,"at",SystemClock.elapsedRealtime(),"value",value));else eventDrops++;}}
  JSONObject copy(JSONObject value){return J.parse(value.toString());}
  JSONArray copyArray(JSONArray value){synchronized(value){try{return new JSONArray(value.toString());}catch(Exception error){throw new IllegalStateException("Fixture array snapshot failed",error);}}}
  String mapped(String value){return chat!=null&&chat.equals(value)?semanticChat:value;}
  String actual(String value){return semanticChat!=null&&semanticChat.equals(value)?chat:value;}
  static String sourceDriverGuard(String sourceUrl){return "if (location.protocol !== 'https:' || location.href !== "+JSONObject.quote(sourceUrl)+") return false;";}
  static String adaptSourceDriver(String code,String sourceUrl){
    int first=code.indexOf(SOURCE_DRIVER_GUARD);if(first<0)return code;
    if(code.indexOf(SOURCE_DRIVER_GUARD,first+SOURCE_DRIVER_GUARD.length())>=0)throw new IllegalStateException("Ambiguous production page driver guard");
    return code.substring(0,first)+sourceDriverGuard(sourceUrl)+code.substring(first+SOURCE_DRIVER_GUARD.length());
  }
  static String sha256(String value){
    try{byte[] digest=MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8));StringBuilder text=new StringBuilder();for(byte b:digest)text.append(String.format(java.util.Locale.ROOT,"%02x",b&255));return text.toString();}
    catch(Exception failure){throw new IllegalStateException("Fixture source hash unavailable",failure);}
  }
  static final class PrivateContext extends ContextWrapper{
    final File directory;
    PrivateContext(Context base,String nonce){super(base);directory=new File(base.getNoBackupFilesDir(),"fingerprint-followups-"+nonce);}
    @Override public Context getApplicationContext(){return this;}
    @Override public File getNoBackupFilesDir(){if(!directory.isDirectory()&&!directory.mkdirs())throw new IllegalStateException("Fixture directory unavailable");return directory;}
  }
  final class FixtureView extends GeckoWebView{
    final Set<String> certificates=new HashSet<>();
    FixtureView(Context context,ChatSession owner){super(context,owner);}
    @Override protected boolean allowedUrl(String value){return value!=null&&(value.startsWith(origin+"/")||value.startsWith(redirectOrigin+"/"));}
    @Override public String getUrl(){return mapped(super.getUrl());}
    String rawUrl(){return super.getUrl();}
    @Override public void loadUrl(String value){synchronized(loads){loads.put(J.obj("requested",value,"actualTarget",actual(value),"at",SystemClock.elapsedRealtime(),"connectionEpoch",owner.connectionEpoch,"navigationEpoch",owner.navigationEpoch));}super.loadUrl(actual(value));}
    @Override public void evaluateJavascript(String code,ValueCallback<String> callback){
      String adapted=code.replace(semanticChat,chat).replace(semanticChat.replace("/","\\/"),chat.replace("/","\\/"));
      if(adapted.contains(SOURCE_DRIVER_GUARD)){
        if(!sourceDriverGuardRecorded){
          if(owner.driver.indexOf(SOURCE_DRIVER_GUARD)<0)throw new IllegalStateException("Production page driver guard missing");
          sourceDriverAdapter=J.obj("kind","controlled-source-page-driver-host-guard-only","sourceUrl",chat,"semanticUrl",semanticChat,"originalGuard",SOURCE_DRIVER_GUARD,"adaptedGuard",sourceDriverGuard(chat),"productionPageDriverSha256",sha256(owner.driver),"adaptedPageDriverTemplateSha256",sha256(adaptSourceDriver(owner.driver,chat)),"scope","Test-APK source fixture only. Exact HTTPS source URL replaces the official-host guard; real DOM, busy state, draft bytes/completeness and expectedUrl origin/path checks remain unchanged. Detector URLs and results are never rewritten.");
          synchronized(normalizations){if(normalizations.length()<32)normalizations.put(copy(sourceDriverAdapter));else normalizationDrops++;}
          sourceDriverGuardRecorded=true;
        }
        adapted=adaptSourceDriver(adapted,chat);
      }
      super.evaluateJavascript(adapted,raw->{
        String result=raw;
        try{JSONObject value=new JSONObject(raw);if(chat.equals(value.optString("url"))){
          JSONObject before=copy(value);value.put("url",semanticChat);result=value.toString();
          synchronized(normalizations){if(normalizations.length()<32)normalizations.put(J.obj("kind","source-page-result-url-only","raw",before,"normalized",copy(value)));else normalizationDrops++;}
          if(owner.audit.requestIdentity.active&&(value.has("draftComplete")||value.has("busy")||Boolean.FALSE.equals(value.opt("ok"))))synchronized(preflightDriverResults){if(preflightDriverResults.length()<16)preflightDriverResults.put(J.obj("stage",stage,"at",SystemClock.elapsedRealtime(),"raw",before,"normalized",copy(value)));else preflightDriverDrops++;}
        }}catch(Exception ignored){}
        if(callback!=null)callback.onReceiveValue(result);
      });
    }
    @Override JSONObject route(String value){
      JSONObject result=super.route(value);
      synchronized(routes){if(routes.length()<512)routes.put(J.obj("at",SystemClock.elapsedRealtime(),"url",value,"route",result,"protection",protectionStatus(),"connectionEpoch",owner.connectionEpoch));else routeDrops++;}
      return result;
    }
    @Override GeckoSession newSession(){
      GeckoSession session=super.newSession();GeckoSession.NavigationDelegate original=session.getNavigationDelegate();
      session.setNavigationDelegate(new GeckoSession.NavigationDelegate(){
        @Override public GeckoResult<AllowOrDeny> onLoadRequest(GeckoSession s,LoadRequest request){return original.onLoadRequest(s,request);}
        @Override public GeckoResult<AllowOrDeny> onSubframeLoadRequest(GeckoSession s,LoadRequest request){return original.onSubframeLoadRequest(s,request);}
        @Override public void onLocationChange(GeckoSession s,String url,List<GeckoSession.PermissionDelegate.ContentPermission> permissions,Boolean gesture){original.onLocationChange(s,url,permissions,gesture);}
        @Override public void onCanGoBack(GeckoSession s,boolean value){original.onCanGoBack(s,value);}
        @Override public void onCanGoForward(GeckoSession s,boolean value){original.onCanGoForward(s,value);}
        @Override public GeckoResult<GeckoSession> onNewSession(GeckoSession s,String value){return original.onNewSession(s,value);}
        @Override public GeckoResult<String> onLoadError(GeckoSession s,String target,WebRequestError error){
          String controlled=target!=null&&target.startsWith(origin+"/")?origin:target!=null&&target.startsWith(redirectOrigin+"/")?redirectOrigin:"";
          if(!controlled.isEmpty()&&!certificates.contains(controlled)&&error.category==WebRequestError.ERROR_CATEGORY_SECURITY&&error.code==WebRequestError.ERROR_SECURITY_BAD_CERT){
            certificates.add(controlled);event("temporary-fixture-certificate-exception",J.obj("origin",controlled,"target",target,"category",error.category,"code",error.code,"temporary",true));
            String html="<!doctype html><script>document.addCertException(true).then(()=>location.replace("+JSONObject.quote(target)+"))</script>";
            return GeckoResult.fromValue("data:text/html;base64,"+Base64.getEncoder().encodeToString(html.getBytes(StandardCharsets.UTF_8)));
          }
          event("load-error",J.obj("target",target,"category",error.category,"code",error.code));return original.onLoadError(s,target,error);
        }
      });
      session.getWebExtensionController().setMessageDelegate(extension,new WebExtension.MessageDelegate(){
        @Override public void onConnect(WebExtension.Port port){
          pageMessages.onConnect(port);WebExtension.PortDelegate delegate=delegate(port);
          port.setDelegate(new WebExtension.PortDelegate(){
            @Override public void onPortMessage(Object message,WebExtension.Port incoming){
              Object forwarded=message;
              if(message instanceof JSONObject){JSONObject value=(JSONObject)message;
                if("documentReady".equals(value.optString("kind"))&&chat.equals(value.optString("url"))&&chat.equals(port.sender.url)&&port.sender.session==current&&port.sender.isTopLevel()&&port.sender.environmentType==WebExtension.MessageSender.ENV_TYPE_CONTENT_SCRIPT){
                  JSONObject normalized=copy(value);try{normalized.put("url",semanticChat);}catch(Exception error){throw new IllegalStateException(error);}forwarded=normalized;
                  synchronized(normalizations){if(normalizations.length()<32)normalizations.put(J.obj("kind","controlled-source-documentReady","actualUrl",rawUrl(),"senderUrl",port.sender.url,"raw",copy(value),"normalized",normalized));else normalizationDrops++;}
                }
              }
              delegate.onPortMessage(forwarded,incoming);
            }
            @Override public void onDisconnect(WebExtension.Port incoming){delegate.onDisconnect(incoming);}
          });
        }
      },"pocketpage");return session;
    }
  }
  static WebExtension.PortDelegate delegate(WebExtension.Port port){
    try{Field f=WebExtension.Port.class.getDeclaredField("delegate");f.setAccessible(true);Object value=f.get(port);if(value instanceof WebExtension.PortDelegate)return (WebExtension.PortDelegate)value;}
    catch(ReflectiveOperationException error){throw new IllegalStateException("Pinned SDK fixture delegate unavailable",error);}
    throw new IllegalStateException("Pinned SDK fixture delegate missing");
  }
  @Override public void onCreate(Bundle state){
    super.onCreate(state);if(!"local.pocketchat.test".equals(getPackageName()))throw new SecurityException("Integration APK only");
    source=getIntent().getStringExtra("sourceCommit");nonce=getIntent().getStringExtra("runNonce");origin=getIntent().getStringExtra("origin");redirectOrigin=getIntent().getStringExtra("redirectOrigin");
    handler.postDelayed(()->finish(new IOException("Single240s native invocation deadline expired")),240000);worker.execute(this::run);
  }
  void validate()throws Exception{
    if(source==null||!source.matches("[0-9a-f]{40}")||nonce==null||!nonce.matches("[0-9a-f]{32}"))throw new IOException("Exact source/nonce required");
    for(String value:Arrays.asList(origin,redirectOrigin)){URI uri=new URI(value==null?"":value);if(!"https".equals(uri.getScheme())||!"10.0.2.2".equals(uri.getHost())||uri.getRawUserInfo()!=null||uri.getRawQuery()!=null||uri.getRawFragment()!=null||!uri.getRawPath().isEmpty()||uri.getPort()<1024||uri.getPort()>65535)throw new IOException("Controlled AVD HTTPS origins required");}
    if(origin.equals(redirectOrigin))throw new IOException("Distinct redirect origin required");
    chat=origin+"/chat?runNonce="+nonce;semanticChat=MainActivity.ORIGIN+"c/fingerprint-fixture-"+nonce;
    build=IntegrationBuildIdentity.read(this);sdk=NormalCaretSdkReceipt.read(this);NormalCaretSdkReceipt.requireInstalled(sdk,build);
    if(!source.equals(build.optString("sourceCommit"))||build.optBoolean("dirtySource",true))throw new IOException("Clean installed source mismatch");
  }
  void open()throws Exception{
    ui(()->{
      Context context=new PrivateContext(getApplicationContext(),nonce);context.getSharedPreferences("chat",0).edit().clear().putString("networkMode","external").putString("proxy","").putBoolean("requireExternalVpn",false).putBoolean("networkConfigured",false).putInt("privacyLevel",1).putBoolean("backgroundWait",false).commit();
      ProfileCatalog.get(context).created(Profiles.slot(context));ChatSession.browserFactory=(c,s)->new FixtureView(c,s);owner=ChatSession.get(context);view=(FixtureView)owner.web;
      owner.handler.removeCallbacks(owner.tick);owner.networkReady=true;owner.offline=false;owner.uiVisible=true;owner.guard.setBlocked(false);
      WebViewClient original=owner.client();view.setWebViewClient(new WebViewClient(){
        @Override public void onPageStarted(WebView ignored,String value,android.graphics.Bitmap icon){original.onPageStarted(null,mapped(value),icon);owner.handler.removeCallbacks(owner.tick);}
        @Override public void onPageCommitVisible(WebView ignored,String value){original.onPageCommitVisible(null,mapped(value));owner.handler.removeCallbacks(owner.tick);}
        @Override public void onPageFinished(WebView ignored,String value){original.onPageFinished(null,mapped(value));owner.handler.removeCallbacks(owner.tick);if(chat.equals(value)){owner.navigating=false;owner.pageError="";}}
      });
      LinearLayout layout=new LinearLayout(this);layout.setOrientation(LinearLayout.VERTICAL);TextView label=new TextView(this);label.setText("Fingerprint followups · controlled local HTTPS only");layout.addView(label);view.setHost(this);layout.addView(view,new LinearLayout.LayoutParams(-1,0,1));setContentView(layout);
      event("synthetic-bootstrap",J.obj("networkConfigured",false,"networkReady",true,"requireExternalVpn",false,"scope","Controlled origin reachability only; no production startup/preflight or fixed-exit verdict"));return null;
    });
    await("Actual Gecko/extension initialization",()->ui(()->view.ready&&view.current!=null&&view.current.isOpen()&&view.privacyReady&&view.routePrepared),60000);
    ui(()->{view.loadUrl(chat);return null;});waitChat();
    JSONObject result=document();check("Standard mode loads an actual controlled Gecko document",chat.equals(result.optString("actualUrl"))&&nonce.equals(result.optString("nonce"))&&result.optDouble("timeOrigin",0)>0);
    cases.put(J.obj("case","standard-source-control","document",result,"protection",ui(()->view.protectionStatus())));
    ui(()->{view.loadUrl(redirectOrigin+"/seed");return null;});await("Second controlled TLS origin",()->eval("({ready:document.getElementById('redirect-seed')?.textContent==="+JSONObject.quote(nonce)+"})").optBoolean("ready"),20000);
    ui(()->{view.loadUrl(chat);return null;});waitChat();
  }
  void waitChat()throws Exception{await("Controlled source and genuine native page bridge",()->ui(()->chat.equals(view.rawUrl())&&view.hasVisibleDocument())&&eval("({ready:document.getElementById('fixture-nonce')?.textContent==="+JSONObject.quote(nonce)+"})").optBoolean("ready"),25000);}
  JSONObject eval(String code)throws Exception{
    CompletableFuture<String> result=new CompletableFuture<>();ui(()->{view.evaluateJavascript(code,result::complete);return null;});return J.parse(result.get(12,TimeUnit.SECONDS));
  }
  JSONObject document()throws Exception{return eval("({actualUrl:location.href,nativeUrl:"+JSONObject.quote(ui(()->view.getUrl()))+",timeOrigin:performance.timeOrigin,nonce:document.getElementById('fixture-nonce')?.textContent||'',draft:document.getElementById('prompt-textarea')?.value||'',cookie:document.cookie,sends:Number(document.getElementById('send-count')?.textContent||0)})");}
  JSONObject audit(boolean deep)throws Exception{
    CompletableFuture<Boolean> done=new CompletableFuture<>();boolean started=ui(()->owner.audit.start(false,deep,()->done.complete(true)));if(!started)throw new IOException("Manual audit refused: "+ui(()->owner.audit.lastError));done.get(18,TimeUnit.SECONDS);return ui(()->copy(owner.audit.report));
  }
  void apiChecks()throws Exception{
    JSONObject before=document(),light=audit(false),deep=audit(true);JSONObject lightSignals=light.optJSONObject("signals"),deepSignals=deep.optJSONObject("signals");
    check("Light audit never requests graphics/audio operations",lightSignals!=null&&!lightSignals.has("apiChecks"));
    JSONObject apis=deepSignals==null?null:deepSignals.optJSONObject("apiChecks");check("Deep audit returns separately scoped manual API results",apis!=null&&apis.optBoolean("requested")&&!apis.optBoolean("protectionVerified",true)&&"page-main-world".equals(apis.optString("source")));
    JSONObject limits=apis.getJSONObject("limits");check("Deep probe budgets are bounded",limits.optInt("canvasPixels")==4096&&limits.optInt("audioFrames")==2048&&limits.optInt("fontCandidates")==5&&limits.optInt("totalBudgetMs")==1200);
    for(String key:Arrays.asList("canvas","audio","fonts","webgl")){JSONObject row=apis.getJSONObject("probes").getJSONObject(key);check("Actual "+key+" operation reports a typed state",Arrays.asList("available","restricted","failed","uncovered").contains(row.optString("state"))&&!row.optString("reason").isEmpty());}
    JSONObject after=document();check("Manual light/deep checks keep the source document and empty draft",before.optDouble("timeOrigin")==after.optDouble("timeOrigin")&&after.optString("draft").isEmpty()&&after.optInt("sends")==0&&after.optString("cookie").contains("fingerprint-preserve="+nonce));
    cases.put(J.obj("case","manual-api-checks","before",before,"light",light,"deep",deep,"after",after));
  }
  JSONObject pageFetch(String phase,String targetOrigin,String kind,String token)throws Exception{
    JSONObject config=J.obj("nonce",token,"phase",phase,"origin",targetOrigin,"kind",kind);
    eval("(()=>{document.getElementById('fixture-fetch-result').textContent='{}';dispatchEvent(new CustomEvent('pocket-fixture-fetch',{detail:"+JSONObject.quote(config.toString())+"}));return {armed:true}})()");
    final JSONObject[] observed={null};await("Controlled main-world request "+phase,()->{JSONObject row=eval("(()=>{try{return JSON.parse(document.getElementById('fixture-fetch-result').textContent)}catch{return {}}})()");if(!row.optBoolean("done")||!token.equals(row.optString("nonce")))return false;observed[0]=row;return true;},12000);return observed[0];
  }
  JSONObject scope(String action,String endpoint,String token)throws Exception{
    CompletableFuture<String> result=new CompletableFuture<>();ui(()->{view.requestIdentityScope(J.obj("action",action,"endpoint",endpoint,"nonce",token),result::complete);return null;});JSONObject value=J.parse(result.get(10,TimeUnit.SECONDS));check("Native diagnostic scope "+action+" acknowledged",value.optBoolean("ok")&&token.equals(value.optString("nonce")));return value;
  }
  String token(){return UUID.randomUUID().toString().replace("-","");}
  JSONObject isolatedNativePrecondition(String endpoint,String token)throws Exception{return ui(()->{
    if(owner.audit.running||owner.audit.requestIdentity.active)throw new IOException("Another audit owns the native scope");
    RequestIdentityAuditSession state=owner.audit.requestIdentity;state.endpoint=endpoint;state.nonce=token;state.connectionEpoch=owner.connectionEpoch;state.originalEpoch=owner.navigationEpoch;state.originalUrl=view.getUrl();state.fileGeneration=owner.fileWorkGeneration;state.route=owner.audit.routeStamp();state.policy=owner.audit.policyStamp();state.expected=owner.audit.expected();state.expected.put("environmentId",owner.environmentId).put("environmentGeneration",owner.environmentGeneration).put("configurationRevision",owner.identityAuditAppliedRevision());state.deadline=SystemClock.elapsedRealtime()+20000;state.active=true;state.opening=true;state.navigated=false;state.collecting=false;state.scopeRequested=state.scopeRegistered=true;owner.audit.running=true;owner.audit.completed=null;state.id=++owner.audit.serial;
    JSONObject actual=view.route(endpoint+"document?nonce="+token);check("Isolated component control uses the actual production native route",actual.optString("type").equals("direct"));
    return J.obj("scope","Fixture-only complete current native-state precondition to isolate credential/redirect hooks; not UI/preflight acceptance. No route/header rewriting.","endpoint",endpoint,"nonce",token,"connectionEpoch",state.connectionEpoch,"originalEpoch",state.originalEpoch,"fileGeneration",state.fileGeneration,"deadline",state.deadline,"nativeRoute",actual);
  });}
  void credentialAndRedirectControls()throws Exception{
    String base=origin+RequestIdentityAudit.PATH,other=redirectOrigin+RequestIdentityAudit.PATH;
    String baseline=token(),redirectBaseline=token(),filtered=token(),redirected=token();
    JSONObject positive=pageFetch("credential-positive",origin,"credential-probe",baseline),redirectPositive=pageFetch("redirect-positive",redirectOrigin,"redirect-control",redirectBaseline);
    check("Browser HTTPS positive controls return responses",positive.optBoolean("ok")&&redirectPositive.optBoolean("ok"));
    JSONObject register=scope("register",base,filtered),nativePrecondition=isolatedNativePrecondition(base,filtered),controlled=pageFetch("credential-filtered",origin,"document",filtered);check("Credential-filtered control reaches owned server",controlled.optBoolean("ok"));
    scope("cancel",base,filtered);ui(()->{owner.audit.cancel();return null;});JSONObject cancelled=pageFetch("scope-cancelled",origin,"document",filtered);check("Cancelled scope rejects a later browser request",!cancelled.optBoolean("ok",true));
    JSONObject redirectRegister=scope("register",other,redirected),redirectNativePrecondition=isolatedNativePrecondition(other,redirected),blocked=pageFetch("redirect-blocked",redirectOrigin,"document",redirected);check("Registered diagnostic redirect does not complete",!blocked.optBoolean("ok",true));scope("cancel",other,redirected);ui(()->{owner.audit.cancel();return null;});
    cases.put(J.obj("case","credential-and-redirect-controls","baselineNonce",baseline,"baseline",positive,"redirectBaselineNonce",redirectBaseline,"redirectBaseline",redirectPositive,"filteredNonce",filtered,"registration",register,"nativePrecondition",nativePrecondition,"filtered",controlled,"cancelled",cancelled,"redirectNonce",redirected,"redirectRegistration",redirectRegister,"redirectNativePrecondition",redirectNativePrecondition,"redirectBlocked",blocked,"scope","Main-world fetch controls only with explicit fixture native state preconditions; no route/header rewriting and not top-level/Worker/UI-preflight identity evidence. Independent Node arrivals required."));
  }
  void identityCheck()throws Exception{
    stage="identity-configure";
    ui(()->{BrowserIdentitySpec policy=BrowserIdentitySpec.preset(BrowserIdentitySpec.DESKTOP).withLocales(Arrays.asList("ja-JP"));view.configureIdentity(policy);view.configure(true,1);return null;});
    await("Desktop session UA request",()->ui(()->!view.getSettings().userAgent.isEmpty()&&!view.getSettings().userAgent.contains("Android")),8000);
    CompletableFuture<Boolean> done=new CompletableFuture<>();String issue=ui(()->owner.audit.setRequestIdentityEndpoint(origin+RequestIdentityAudit.PATH));check("Explicit controlled HTTPS detector configured",issue.isEmpty());
    JSONObject before=document();stage="identity-preflight-and-detection";boolean started=ui(()->owner.audit.startRequestIdentity(()->done.complete(true)));check("User-requested top-level identity check begins from empty source",started);done.get(25,TimeUnit.SECONDS);event("identity-preflight-terminal",ui(this::auditSnapshot));stage="identity-result-validation";
    JSONObject report=ui(()->copy(owner.audit.report)),request=report.optJSONObject("requestIdentity");check("Request audit retains a separately sourced identity result",request!=null&&"controlled-top-level-document".equals(request.optString("source"))&&Arrays.asList("observed","issue","uncovered").contains(request.optString("status")));
    String actual=ui(()->view.rawUrl());check("Identity sampling actually navigated the existing Gecko session",actual.startsWith(origin+RequestIdentityAudit.PATH+"document?nonce=")&&!actual.equals(chat));
    check("No full desktop identity or fingerprint verdict is manufactured",!request.optBoolean("fullDesktopUaConsistency",true)&&!request.optBoolean("fingerprintTemplateAcceptance",true));
    JSONObject identityCase=J.obj("case","top-level-request-identity","sourceBefore",before,"report",report,"actualDetectorUrl",actual,"nativeDetectorUrl",ui(()->view.getUrl()),"sdkDefaultUserAgent",GeckoSession.getDefaultUserAgent(),"configuredSessionUserAgent",ui(()->view.getSettings().userAgent),"independentServerRequired",true);cases.put(identityCase);
    controlledRecovery();
    check("User can explicitly return to the owned source",ui(()->owner.audit.canReturnRequestIdentity()));check("Explicit return is accepted",ui(()->owner.audit.returnRequestIdentity()));waitChat();
    JSONObject after=document();check("Returning preserves the synthetic login and no-send state",after.optString("draft").isEmpty()&&after.optInt("sends")==0&&after.optString("cookie").contains("fingerprint-preserve="+nonce));identityCase.put("sourceAfter",after);
    JSONObject refusalBefore=document();eval("(()=>{document.getElementById('prompt-textarea').value='   ';return {ok:true}})()");CompletableFuture<Boolean> refused=new CompletableFuture<>();boolean whitespace=ui(()->owner.audit.startRequestIdentity(()->refused.complete(true)));if(whitespace)refused.get(25,TimeUnit.SECONDS);JSONObject unchanged=document();check("Even a whitespace-only draft rejects leaving the source",chat.equals(unchanged.optString("actualUrl"))&&refusalBefore.optDouble("timeOrigin")==unchanged.optDouble("timeOrigin"));check("Rejected preflight leaves draft bytes intact",unchanged.optString("draft").equals("   "));eval("(()=>{document.getElementById('prompt-textarea').value='';return {ok:true}})()");
    cases.put(J.obj("case","nonempty-draft-refusal","asynchronousPreflightAccepted",whitespace,"after",unchanged,"reason",ui(()->owner.audit.lastError)));
  }
  void controlledRecovery()throws Exception{
    JSONObject before=document();int priorLoads=ui(()->loads.length()),nativeSession=ui(()->System.identityHashCode(view.current)),nativeView=System.identityHashCode(view);long epoch=ui(()->owner.connectionEpoch);
    ui(()->{check("Completed detector remains selected before controlled recovery",owner.audit.requestIdentityPageSelected());owner.prefs.edit().putBoolean("networkConfigured",true).commit();owner.invalidateConnection();check("Native invalidation retains the user-selected detector",owner.audit.requestIdentityPageSelected());owner.openConnection(true,false);return null;});
    await("Controlled explicit external route recovers through production applyProxy",()->ui(()->owner.networkReady&&!owner.connecting&&owner.guard.allowed()),12000);
    JSONObject after=document();long current=ui(()->owner.connectionEpoch);String summary=ui(()->owner.audit.requestIdentitySummary(false));
    check("Recovery does not reload or replace the selected detector",current>epoch&&priorLoads==ui(()->loads.length())&&before.optString("actualUrl").equals(after.optString("actualUrl"))&&before.optDouble("timeOrigin")==after.optDouble("timeOrigin")&&nativeSession==ui(()->System.identityHashCode(view.current))&&nativeView==System.identityHashCode(view));
    check("Recovered route does not accept old request observations as current",summary.contains("历史"));check("A fresh user return action remains available after recovery",ui(()->owner.audit.canReturnRequestIdentity()));
    cases.put(J.obj("case","controlled-diagnostic-page-recovery","before",before,"after",after,"epochBefore",epoch,"epochAfter",current,"loadsBefore",priorLoads,"loadsAfter",ui(()->loads.length()),"nativeSession",nativeSession,"nativeView",nativeView,"summary",summary,"scope","Actual production invalidateConnection/openConnection/applyProxy with an explicitly configured controlled external no-VPN route; no physical Wi-Fi/cellular or fixed-exit safety acceptance. Independent server must show no old nonce replay."));
  }
  void lateRegistrationControl()throws Exception{
    JSONObject before=document();final WebExtension.Port[] port={null};final WebExtension.PortDelegate[] original={null};final JSONObject[] held={null};final String[] token={""};final int[] cancels={0};CompletableFuture<Boolean> completed=new CompletableFuture<>();
    ui(()->{
      port[0]=view.routePort;if(port[0]==null)throw new IOException("Actual native route port absent");original[0]=delegate(port[0]);
      port[0].setDelegate(new WebExtension.PortDelegate(){
        @Override public void onPortMessage(Object message,WebExtension.Port incoming){
          if(message instanceof JSONObject){JSONObject envelope=(JSONObject)message;
            if("requestIdentityScopeResult".equals(envelope.optString("kind"))){JSONObject result=J.parse(envelope.optString("result","null"));
              if(result.optBoolean("ok")&&token[0].equals(result.optString("nonce"))){
                if(result.optBoolean("credentialFilter")&&held[0]==null){held[0]=copy(envelope);event("fixture-held-real-registration-ack",copy(envelope));return;}
                if(!result.optBoolean("credentialFilter")){cancels[0]++;event("actual-scope-cancel-ack",copy(envelope));}
              }
            }
          }
          original[0].onPortMessage(message,incoming);
        }
        @Override public void onDisconnect(WebExtension.Port incoming){original[0].onDisconnect(incoming);}
      });
      check("Late-ack control starts a real bounded preflight",owner.audit.startRequestIdentity(()->completed.complete(true)));token[0]=owner.audit.requestIdentity.nonce;return null;
    });
    await("Actual background registration acknowledgement captured",()->ui(()->held[0]!=null),6000);
    ui(()->{owner.audit.cancel();check("Cancelling before registration acknowledgement does not navigate",chat.equals(view.rawUrl()));original[0].onPortMessage(copy(held[0]),port[0]);return null;});completed.get(8,TimeUnit.SECONDS);
    await("Cancelled late registration is actually closed by the extension",()->ui(()->cancels[0]>0),6000);
    ui(()->{port[0].setDelegate(original[0]);return null;});JSONObject denied=pageFetch("late-registration-cancelled",origin,"document",token[0]);check("Old nonce cannot send a request after late registration cancellation",!denied.optBoolean("ok",true));JSONObject after=document();check("Late scope acknowledgement keeps source document and draft intact",before.optDouble("timeOrigin")==after.optDouble("timeOrigin")&&chat.equals(after.optString("actualUrl"))&&after.optString("draft").isEmpty());
    cases.put(J.obj("case","late-registration-cancellation","nonce",token[0],"heldActualAcknowledgement",held[0],"actualCancelAcknowledgements",cancels[0],"attempt",denied,"before",before,"after",after,"injection","Fixture-only pinned SDK Port.delegate delays one actual successful registration receipt; original native callback handles it after user cancellation"));
  }
  void preflightInvalidationControls()throws Exception{
    for(String mode:Arrays.asList("synthetic-epoch","browser-policy")){
      JSONObject before=document();CompletableFuture<Boolean> done=new CompletableFuture<>();final String[] token={""};final long[] old={0},next={0};
      boolean accepted=ui(()->{
        boolean started=owner.audit.startRequestIdentity(()->done.complete(true));if(!started)return false;token[0]=owner.audit.requestIdentity.nonce;
        if(mode.equals("synthetic-epoch")){old[0]=owner.connectionEpoch;next[0]=++owner.connectionEpoch;}
        else{old[0]=view.identityPolicyRevision;view.configure(view.desktop,owner.privacy.level());next[0]=view.identityPolicyRevision;}
        return true;
      });check("Preflight "+mode+" control accepted before invalidation",accepted);done.get(12,TimeUnit.SECONDS);JSONObject after=document();
      check("Changed "+mode+" fence rejects stale navigation",next[0]>old[0]&&before.optDouble("timeOrigin")==after.optDouble("timeOrigin")&&chat.equals(after.optString("actualUrl"))&&after.optString("draft").isEmpty());
      cases.put(J.obj("case",mode+"-preflight-invalidation","nonce",token[0],"prior",old[0],"current",next[0],"before",before,"after",after,"reason",ui(()->owner.audit.lastError),"scope",mode.equals("synthetic-epoch")?"Native connectionEpoch increment is fixture fault injection, not actual Wi-Fi/cellular switching":"Actual production browser configure call invalidates the policy revision; not a persisted user-template UI acceptance"));
    }
    await("Current desktop UA recovers after explicit same-policy configure",()->ui(()->!view.getSettings().userAgent.isEmpty()&&!view.getSettings().userAgent.contains("Android")),8000);
  }
  void protectionFailureControl()throws Exception{
    JSONObject before=document();String positiveNonce=token();JSONObject positive=pageFetch("strict-positive",origin,"strict-probe",positiveNonce);check("Strict request endpoint has an actual standard-mode positive control",positive.optBoolean("ok")&&positive.optInt("status")==200);ui(()->{
      heldRoutePort=view.routePort;if(heldRoutePort==null)throw new IOException("Actual native route port absent");originalRouteDelegate=delegate(heldRoutePort);dropProtectionReplies=true;
      heldRoutePort.setDelegate(new WebExtension.PortDelegate(){
        @Override public void onPortMessage(Object message,WebExtension.Port incoming){
          if(dropProtectionReplies&&message instanceof JSONObject){JSONObject value=(JSONObject)message;if("protectionReady".equals(value.optString("kind"))&&value.optInt("level")==2){heldProtectionReply=copy(value);droppedProtectionReplies++;event("fixture-dropped-native-setting-receipt",copy(value));return;}}
          originalRouteDelegate.onPortMessage(message,incoming);
        }
        @Override public void onDisconnect(WebExtension.Port incoming){originalRouteDelegate.onDisconnect(incoming);}
      });
      owner.prefs.edit().putInt("privacyLevel",2).commit();view.configure(view.desktop,2);check("Strict pending confirmation closes new native request admission immediately",view.protectionStatus().optString("state").equals("pending")&&!view.protectionAllowsNetwork()&&view.route(origin+"/strict-probe?nonce="+nonce).optInt("port")==9);return null;
    });
    String pendingNonce=token();JSONObject attempted=pageFetch("strict-pending",origin,"strict-probe",pendingNonce);check("Actual main-world request fails while native confirmation is withheld",!attempted.optBoolean("ok",true));
    await("Bounded strict confirmation attempts terminate",()->ui(()->"failed".equals(view.protectionStatus().optString("state"))&&view.protectionStatus().optInt("attempt")==3),32000);
    JSONObject failed=ui(()->view.protectionStatus());check("Strict timeout remains failed and closed",failed.optBoolean("newRequestsBlocked")&&!failed.optBoolean("settingsReadbackConfirmed")&&failed.optInt("maxAttempts")==3);
    JSONObject pendingCase=J.obj("case","strict-native-receipt-loss-control","before",before,"positiveNonce",positiveNonce,"positive",positive,"attemptNonce",pendingNonce,"attempt",attempted,"failed",failed,"withheldReplies",droppedProtectionReplies,"injection","Fixture-only pinned SDK Port.delegate wrapper drops actual level2 native replies; production code has no force switch");cases.put(pendingCase);
    ui(()->{dropProtectionReplies=false;heldRoutePort.setDelegate(originalRouteDelegate);check("Manual strict retry starts a new correlated request",view.retryProtection());JSONObject current=view.protectionStatus();if(heldProtectionReply!=null){originalRouteDelegate.onPortMessage(copy(heldProtectionReply),heldRoutePort);check("Late previous receipt cannot confirm the new retry",!view.protectionStatus().optBoolean("settingsReadbackConfirmed")&&view.protectionStatus().optLong("generation")==current.optLong("generation"));}return null;});
    await("Actual native setting retry terminal observation",()->ui(()->!"pending".equals(view.protectionStatus().optString("state"))),32000);JSONObject terminal=ui(()->view.protectionStatus());
    if("confirmed".equals(terminal.optString("state"))){check("A real strict confirmation requires matching readback and enabled fingerprint protection",terminal.optBoolean("settingsReadbackConfirmed")&&terminal.optBoolean("observedFingerprinting")&&!terminal.optBoolean("newRequestsBlocked"));String confirmedNonce=token();JSONObject confirmed=pageFetch("strict-confirmed",origin,"strict-probe",confirmedNonce);check("Confirmed strict mode permits an actual controlled request",confirmed.optBoolean("ok")&&confirmed.optInt("status")==200);pendingCase.put("confirmedProbeNonce",confirmedNonce);pendingCase.put("confirmedProbe",confirmed);JSONObject strictApi=audit(true);JSONObject api=strictApi.optJSONObject("signals")==null?null:strictApi.optJSONObject("signals").optJSONObject("apiChecks");check("Actual strict API observations do not become a full-protection verdict",api!=null&&!api.optBoolean("protectionVerified",true));pendingCase.put("strictApiObservation",strictApi);pendingCase.put("apiComparisonScope","Standard and actually confirmed native-RFP manual observations retained separately; changed outputs do not imply leakage or protection failure");}
    else{check("Unsupported or failed real strict setting remains blocked",terminal.optBoolean("newRequestsBlocked")&&!terminal.optBoolean("settingsReadbackConfirmed"));pendingCase.put("strictApiComparison","unverified: actual native strict confirmation unavailable");}
    pendingCase.put("actualRetryTerminal",terminal);pendingCase.put("actualStrictPositiveControlAvailable","confirmed".equals(terminal.optString("state")));
    ui(()->{owner.prefs.edit().putInt("privacyLevel",1).commit();view.configure(view.desktop,1);return null;});
    await("Explicit standard selection restores native route admission",()->ui(()->view.protectionAllowsNetwork()),10000);JSONObject after=document();check("Protection retry and explicit standard selection do not reload, clear login or send the page",before.optDouble("timeOrigin")==after.optDouble("timeOrigin")&&after.optInt("sends")==0&&after.optString("draft").isEmpty()&&after.optString("cookie").contains("fingerprint-preserve="+nonce));pendingCase.put("after",after);
  }
  JSONObject auditSnapshot(){
    if(owner==null)return J.obj("stage",stage,"ownerCreated",false);
    RequestIdentityAuditSession state=owner.audit.requestIdentity;
    return J.obj("stage",stage,"lastError",owner.audit.lastError,"running",owner.audit.running,"networkRun",owner.audit.networkRun,"serial",owner.audit.serial,"auditUrl",owner.audit.auditUrl,"auditNavigation",owner.audit.auditNavigation,"report",copy(owner.audit.report),"requestIdentityReport",copy(owner.audit.requestIdentityReport),"controller",J.obj("id",state.id,"active",state.active,"opening",state.opening,"navigated",state.navigated,"collecting",state.collecting,"scopeRequested",state.scopeRequested,"scopeRegistered",state.scopeRegistered,"webDone",state.webDone,"controlDone",state.controlDone,"connectionEpoch",state.connectionEpoch,"originalEpoch",state.originalEpoch,"pageEpoch",state.pageEpoch,"deadline",state.deadline,"fileGeneration",state.fileGeneration,"originalUrl",state.originalUrl,"documentUrl",state.documentUrl,"endpoint",state.endpoint,"nonce",state.nonce,"routeFresh",state.routeFresh(),"pageOwned",state.pageOwned(),"pageSelected",state.pageSelected(),"fresh",state.fresh()));
  }
  void run(){try{stage="validate";validate();stage="open-controlled-source";open();stage="manual-api-checks";apiChecks();stage="credential-and-redirect-controls";credentialAndRedirectControls();identityCheck();stage="late-registration-control";lateRegistrationControl();stage="preflight-invalidation-controls";preflightInvalidationControls();stage="protection-failure-control";protectionFailureControl();stage="completed";finish(null);}catch(Throwable error){finish(error);}}
  void finish(Throwable error){
    if(!concluded.compareAndSet(false,true))return;
    JSONObject finalState=new JSONObject();try{finalState=ui(()->J.obj("url",view==null?"":view.getUrl(),"actualUrl",view==null?"":view.rawUrl(),"protection",view==null?new JSONObject():view.protectionStatus(),"connectionEpoch",owner==null?-1:owner.connectionEpoch,"navigationEpoch",owner==null?-1:owner.navigationEpoch,"audit",auditSnapshot()));}catch(Exception failure){finalState=J.obj("stage",stage,"error",failure.getClass().getSimpleName());}
    JSONObject report=J.obj("schema",1,"status",error==null?"completed":"failed","sourceCommit",source,"sourceTree",build.optString("sourceTree"),"runNonce",nonce,"buildIdentity",build,"sdkIdentity",sdk,"actualAndroidExecution",true,"actualGeckoExecution",view!=null&&view.ready,"officialChatGptSiteTested",false,"physicalPhoneAcceptance",false,"fullFingerprintProtectionAcceptance",false,"fullDesktopUaConsistency",false,"releaseAcceptance",false,"publicNetworkTraffic",false,"origin",origin,"redirectOrigin",redirectOrigin,"actualSourceChat",chat,"semanticSourceAlias",semanticChat,"measurementEndedAtElapsedMs",SystemClock.elapsedRealtime(),"checks",copyArray(checks),"cases",copyArray(cases),"events",copyArray(events),"routes",copyArray(routes),"loads",copyArray(loads),"normalizations",copyArray(normalizations),"eventDrops",eventDrops,"routeDrops",routeDrops,"normalizationDrops",normalizationDrops,"finalState",finalState,"fixtureOnlyCertificateOrigins",view==null?new JSONArray():new JSONArray(new ArrayList<>(view.certificates)),"scope","Source-chat alias is a controlled fixture adapter only; actual detector document/Worker URLs and headers are never rewritten. Actual Gecko and independent HTTPS records must be reconciled; no real ChatGPT/login, phone, complete DNS/IPv6/Shared Worker/Service Worker or full protection verdict.","unverified",J.arr("Real ChatGPT and real accounts","Physical phone keyboard and scrolling","Shared Worker and Service Worker","Full network fingerprint/DNS/IPv6 paths","Restart/upgrade phone behavior","True current-template application during real user work"));
    try{report.put("stage",stage).put("sourceDriverAdapter",sourceDriverAdapter).put("preflightDriverResults",copyArray(preflightDriverResults)).put("preflightDriverDrops",preflightDriverDrops);}catch(Exception ignored){}
    if(error!=null)try{report.put("errorType",error.getClass().getName());report.put("error",String.valueOf(error.getMessage()));}catch(Exception ignored){}
    try{AtomicFile file=new AtomicFile(new File(getFilesDir(),FILE));FileOutputStream out=null;try{out=file.startWrite();out.write((report.toString()+"\n").getBytes(StandardCharsets.UTF_8));file.finishWrite(out);}catch(Throwable failure){if(out!=null)file.failWrite(out);throw failure;}Log.i(TAG,report.toString());}catch(Throwable failure){Log.e(TAG,"Evidence persistence failed",failure);}
    handler.post(()->{if(owner!=null){owner.handler.removeCallbacks(owner.tick);owner.audit.cancel();}if(view!=null)view.destroy();});worker.shutdown();
  }
}
