package local.pocketchat;

import android.app.Activity;
import android.content.Context;
import android.content.ContextWrapper;
import android.content.Intent;
import android.net.ConnectivityManager;
import android.net.LinkProperties;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.RouteInfo;
import android.net.VpnService;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.util.AtomicFile;
import android.util.Log;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.LinearLayout;
import android.widget.TextView;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.List;
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
import org.mozilla.geckoview.WebRequestError;

/** Test APK only. A completed measurement is deliberately not a protection pass. */
public final class NetworkProtectionIntegrationActivity extends Activity {
  static final String TAG="PocketNetworkProtection",FILE="network-protection-results.json";
  final Handler handler=new Handler(Looper.getMainLooper());
  final ExecutorService worker=Executors.newSingleThreadExecutor();
  final AtomicBoolean concluded=new AtomicBoolean();
  final JSONArray phases=new JSONArray(),routes=new JSONArray(),events=new JSONArray();
  JSONObject buildIdentity=new JSONObject(),sdkIdentity=new JSONObject(),documentIdentity=new JSONObject();
  JSONObject existingConnectionAfterRemoval=J.obj("status","unverified","reason","not-executed");
  String source,nonce,origin,page;ChatSession owner;FixtureView view;int routesDropped,eventsDropped;

  interface Work<T>{T run()throws Exception;}
  <T>T ui(Work<T> work)throws Exception{
    CompletableFuture<T> result=new CompletableFuture<>();
    handler.post(()->{try{result.complete(work.run());}catch(Throwable error){result.completeExceptionally(error);}});
    return result.get(15,TimeUnit.SECONDS);
  }
  void await(String name,Work<Boolean> condition,long timeout)throws Exception{
    long end=SystemClock.elapsedRealtime()+timeout;
    while(!condition.run()){if(concluded.get())throw new IOException("Fixture already concluded");if(SystemClock.elapsedRealtime()>=end)throw new IOException(name+" timed out");Thread.sleep(100);}
  }
  void event(String kind,JSONObject data){synchronized(events){if(events.length()<96)events.put(J.obj("kind",kind,"at",SystemClock.elapsedRealtime(),"value",data));else eventsDropped++;}}
  static final class PrivateContext extends ContextWrapper{
    final File directory;
    PrivateContext(Context base,String nonce){super(base);directory=new File(base.getNoBackupFilesDir(),"network-protection-"+nonce);}
    @Override public Context getApplicationContext(){return this;}
    @Override public File getNoBackupFilesDir(){if(!directory.isDirectory()&&!directory.mkdirs())throw new IllegalStateException("Fixture directory unavailable");return directory;}
  }
  final class FixtureView extends GeckoWebView{
    int certificateExceptions;
    FixtureView(Context context,ChatSession session){super(context,session);}
    @Override protected boolean allowedUrl(String target){return target!=null&&target.startsWith(origin+"/");}
    @Override JSONObject route(String target){
      JSONObject actual=super.route(target);
      synchronized(routes){if(routes.length()<192)routes.put(J.obj("at",SystemClock.elapsedRealtime(),"url",target,"route",actual,"blocked",owner.guard.blocked,"allowed",owner.guard.allowed(),"connectionEpoch",owner.connectionEpoch));else routesDropped++;}
      return actual;
    }
    @Override GeckoSession newSession(){
      GeckoSession sdk=super.newSession();GeckoSession.NavigationDelegate original=sdk.getNavigationDelegate();
      sdk.setNavigationDelegate(new GeckoSession.NavigationDelegate(){
        @Override public GeckoResult<AllowOrDeny> onLoadRequest(GeckoSession s,LoadRequest request){return original.onLoadRequest(s,request);}
        @Override public GeckoResult<AllowOrDeny> onSubframeLoadRequest(GeckoSession s,LoadRequest request){return original.onSubframeLoadRequest(s,request);}
        @Override public void onLocationChange(GeckoSession s,String target,List<GeckoSession.PermissionDelegate.ContentPermission> permissions,Boolean gesture){original.onLocationChange(s,target,permissions,gesture);}
        @Override public void onCanGoBack(GeckoSession s,boolean value){original.onCanGoBack(s,value);}
        @Override public void onCanGoForward(GeckoSession s,boolean value){original.onCanGoForward(s,value);}
        @Override public GeckoResult<GeckoSession> onNewSession(GeckoSession s,String target){return original.onNewSession(s,target);}
        @Override public GeckoResult<String> onLoadError(GeckoSession s,String target,WebRequestError error){
          if(page.equals(target)&&certificateExceptions==0&&error.category==WebRequestError.ERROR_CATEGORY_SECURITY&&error.code==WebRequestError.ERROR_SECURITY_BAD_CERT){
            certificateExceptions++;event("temporaryFixtureCertificateException",J.obj("url",target,"category",error.category,"code",error.code,"temporary",true));
            String html="<!doctype html><title>Controlled network certificate</title><script>document.addCertException(true).then(()=>location.replace("+JSONObject.quote(target)+")).catch(()=>document.body.textContent='fixture certificate exception failed')</script>";
            return GeckoResult.fromValue("data:text/html;base64,"+Base64.getEncoder().encodeToString(html.getBytes(StandardCharsets.UTF_8)));
          }
          event("loadError",J.obj("url",target,"category",error.category,"code",error.code));return original.onLoadError(s,target,error);
        }
      });return sdk;
    }
  }
  @Override public void onCreate(Bundle state){
    super.onCreate(state);
    if(!"local.pocketchat.test".equals(getPackageName()))throw new SecurityException("Integration package only");
    source=getIntent().getStringExtra("sourceCommit");nonce=getIntent().getStringExtra("runNonce");origin=getIntent().getStringExtra("origin");
    worker.execute(this::run);
  }
  void validateInvocation()throws Exception{
    if(source==null||!source.matches("[0-9a-f]{40}")||nonce==null||!nonce.matches("[0-9a-f]{32}"))throw new IOException("Exact source and run nonce required");
    URI uri=new URI(origin==null?"":origin);
    if(!"https".equals(uri.getScheme())||!"10.0.2.2".equals(uri.getHost())||uri.getPort()<1024||uri.getPort()>65535||uri.getRawUserInfo()!=null||uri.getRawQuery()!=null||uri.getRawFragment()!=null||!uri.getRawPath().isEmpty())throw new IOException("Only the exact controlled AVD host HTTPS origin is allowed");
    page=origin+"/page?runNonce="+nonce;
    buildIdentity=IntegrationBuildIdentity.read(this);sdkIdentity=NormalCaretSdkReceipt.read(this);NormalCaretSdkReceipt.requireInstalled(sdkIdentity,buildIdentity);
    if(!source.equals(buildIdentity.getString("sourceCommit"))||buildIdentity.optBoolean("dirtySource",true))throw new IOException("Installed source does not match clean selected source");
    if(VpnService.prepare(this)!=null)throw new IOException("VPN_PERMISSION_NOT_PREPARED: runner must prepare only the synthetic test package");
  }
  void openBrowser()throws Exception{
    ui(()->{
      Context context=new PrivateContext(getApplicationContext(),nonce);
      context.getSharedPreferences("chat",0).edit().clear().putString("networkMode","external").putString("proxy","").putBoolean("requireExternalVpn",false).putBoolean("networkConfigured",false).putInt("privacyLevel",0).putBoolean("backgroundWait",false).commit();
      ProfileCatalog.get(context).created(Profiles.slot(context));ChatSession.browserFactory=(c,s)->new FixtureView(c,s);owner=ChatSession.get(context);view=(FixtureView)owner.web;
      owner.handler.removeCallbacks(owner.tick);owner.networkReady=true;owner.offline=false;owner.uiVisible=true;owner.guard.setBlocked(false);
      // Match the existing local fixture bootstrap. No normal website preflight
      // is claimed; every actual request still uses the unmodified native route.
      event("syntheticBootstrapAdmission",J.obj("networkConfigured",false,"networkReady",true,"requireExternalVpn",false,"scope","Fixture reachability only; no production connection-preflight acceptance"));
      view.setWebViewClient(new WebViewClient(){
        @Override public void onPageStarted(WebView ignored,String url,android.graphics.Bitmap icon){owner.handler.removeCallbacks(owner.tick);}
        @Override public void onPageFinished(WebView ignored,String url){owner.navigating=false;owner.handler.removeCallbacks(owner.tick);}
      });
      LinearLayout layout=new LinearLayout(this);layout.setOrientation(LinearLayout.VERTICAL);TextView label=new TextView(this);label.setText("Network protection diagnostic · controlled traffic only");layout.addView(label);view.setHost(this);layout.addView(view,new LinearLayout.LayoutParams(-1,0,1));setContentView(layout);return null;
    });
    await("Actual Gecko initialization",()->ui(()->view.ready&&view.privacyReady&&view.identityPrepared&&view.routePrepared&&view.current!=null&&view.current.isOpen()),60000);
    ui(()->{view.loadUrl(page);return null;});
    await("Controlled page and DOM probe bridge",()->eval("({ready:location.href==="+JSONObject.quote(page)+"&&document.getElementById('network-probe-ready')?.textContent==="+JSONObject.quote(nonce)+"})").optBoolean("ready"),35000);
    documentIdentity=eval("({url:location.href,timeOrigin:performance.timeOrigin,nonce:document.getElementById('network-probe-ready')?.textContent})");
    if(!page.equals(documentIdentity.optString("url"))||!nonce.equals(documentIdentity.optString("nonce"))||documentIdentity.optDouble("timeOrigin",0)<=0)throw new IOException("Document identity unavailable");
  }
  JSONObject eval(String code)throws Exception{
    CompletableFuture<String> result=new CompletableFuture<>();ui(()->{view.evaluateJavascript(code,result::complete);return null;});
    return J.parse(result.get(12,TimeUnit.SECONDS));
  }
  void sameDocument()throws Exception{
    JSONObject actual=eval("({url:location.href,timeOrigin:performance.timeOrigin,nonce:document.getElementById('network-probe-ready')?.textContent})");
    if(!documentIdentity.optString("url").equals(actual.optString("url"))||!documentIdentity.optString("nonce").equals(actual.optString("nonce"))||documentIdentity.optDouble("timeOrigin")!=actual.optDouble("timeOrigin"))throw new IOException("Actual controlled document changed during network experiment");
  }
  JSONObject snapshot()throws Exception{return ui(()->{
    ConnectivityManager cm=getSystemService(ConnectivityManager.class);Network network=cm==null?null:cm.getActiveNetwork();NetworkCapabilities caps=network==null?null:cm.getNetworkCapabilities(network);LinkProperties links=network==null?null:cm.getLinkProperties(network);JSONArray routeRows=new JSONArray();
    if(links!=null)for(RouteInfo route:links.getRoutes())routeRows.put(J.obj("route",route.toString(),"destination",route.getDestination().toString(),"default",route.isDefaultRoute(),"type",route.getType()));
    return J.obj("at",SystemClock.elapsedRealtime(),"activeNetwork",network==null?"":network.toString(),"capabilities",caps==null?"":caps.toString(),"internet",caps!=null&&caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET),"vpnTransport",caps!=null&&caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN),"interface",links==null?"":links.getInterfaceName(),"routes",routeRows,"requiresVpn",owner.guard.requiresVpn(),"guardVpnActive",owner.guard.vpnActive(),"guardRouteProtected",owner.guard.routeProtected(),"guardBlocked",owner.guard.blocked,"guardAllowed",owner.guard.allowed(),"networkReady",owner.networkReady,"offline",owner.offline,"manualAttention",owner.manualAttention,"connectionStage",owner.connectionStage,"networkIssue",owner.networkIssue,"networkConfigured",owner.prefs.getBoolean("networkConfigured",false),"connectionEpoch",owner.connectionEpoch,"navigationEpoch",owner.navigationEpoch,"currentSession",System.identityHashCode(view.current),"nativeView",System.identityHashCode(view),"vpnFixture",NetworkProtectionFixtureVpnService.snapshot());
  });}
  void startVpn(String mode)throws Exception{
    ui(()->{owner.prefs.edit().putBoolean("requireExternalVpn",true).commit();startService(new Intent(this,NetworkProtectionFixtureVpnService.class).setAction("START").putExtra("mode",mode).putExtra("runNonce",nonce).putExtra("sourceCommit",source));return null;});
    await("Actual "+mode+" VPN service and application-visible CM state",()->{
      JSONObject s=snapshot(),v=s.getJSONObject("vpnFixture");return v.optBoolean("running")&&nonce.equals(v.optString("runNonce"))&&source.equals(v.optString("sourceCommit"))&&mode.equals(v.optString("mode"))&&s.optBoolean("guardVpnActive")&&s.optBoolean("vpnTransport")&&s.optBoolean("internet");
    },12000);
    // Allow the actual default-network callback queue to settle, without
    // removing callbacks or changing any observed CM state.
    String stable="";long since=0,end=SystemClock.elapsedRealtime()+6000;
    while(true){JSONObject s=snapshot();String value=s.optString("activeNetwork")+"/"+s.optLong("connectionEpoch");long now=SystemClock.elapsedRealtime();if(!s.optBoolean("guardVpnActive"))throw new IOException("VPN disappeared while settling");if(!value.equals(stable)){stable=value;since=now;}if(now-since>=600)break;if(now>=end)throw new IOException("VPN default network did not settle");Thread.sleep(100);}
  }
  JSONObject admitVpnRoute(String mode)throws Exception{return ui(()->{
    if(!owner.guard.requiresVpn()||!owner.guard.vpnActive()||owner.offline)throw new IOException("Actual VPN prerequisite is absent");
    JSONObject admission=J.obj("kind","syntheticRouteGateAdmission","mode",mode,"at",SystemClock.elapsedRealtime(),"connectionEpoch",owner.connectionEpoch,"guardRouteProtected",owner.guard.routeProtected(),"normalWebsitePreflightPerformed",false,"scope","Readiness is admitted only to exercise the unchanged per-request VPN route gate; not full application startup acceptance");
    owner.networkReady=true;owner.guard.setBlocked(false);event("routeGateAdmission",admission);return admission;
  });}
  JSONObject probe(String name,JSONObject admission)throws Exception{
    sameDocument();long started=SystemClock.elapsedRealtime();JSONObject before=snapshot();
    JSONObject armed=eval("(()=>{document.dispatchEvent(new CustomEvent('pocket-network-probe',{detail:"+JSONObject.quote(name)+"}));return {armed:true,url:location.href,timeOrigin:performance.timeOrigin}})()");
    if(!armed.optBoolean("armed")||!page.equals(armed.optString("url"))||armed.optDouble("timeOrigin")!=documentIdentity.optDouble("timeOrigin"))throw new IOException("Probe armed in a different document");
    final JSONObject[] value={null};await(name+" explicit probe terminal state",()->{JSONObject result=eval("(()=>{try{return JSON.parse(document.getElementById('network-probe-result')?.textContent||'{}')}catch(_){return {}}})()");if(!name.equals(result.optString("phase"))||!nonce.equals(result.optString("runNonce"))||!result.optBoolean("done"))return false;value[0]=result;return true;},6500);
    sameDocument();JSONObject row=J.obj("name",name,"phase",name,"startedAt",started,"endedAt",SystemClock.elapsedRealtime(),"admission",admission,"before",before,"after",snapshot(),"probe",value[0],"independentServerVerificationRequired",true);phases.put(row);event("phaseCompleted",J.obj("phase",name));return row;
  }
  void stopVpn()throws Exception{
    JSONObject v=NetworkProtectionFixtureVpnService.snapshot();if(!v.optBoolean("running"))return;
    if(!nonce.equals(v.optString("runNonce"))||!source.equals(v.optString("sourceCommit")))throw new IOException("Refusing to stop another fixture VPN owner");
    long generation=v.getLong("generation");ui(()->{startService(new Intent(this,NetworkProtectionFixtureVpnService.class).setAction("STOP").putExtra("runNonce",nonce).putExtra("sourceCommit",source).putExtra("generation",generation));return null;});
    long end=SystemClock.elapsedRealtime()+8000;
    while(NetworkProtectionFixtureVpnService.snapshot().optBoolean("running")){if(SystemClock.elapsedRealtime()>=end)throw new IOException("Actual owned VPN descriptor close timed out");Thread.sleep(100);}
  }
  void run(){Throwable error=null;try{
    validateInvocation();openBrowser();JSONObject warm=probe("warmup",J.obj("kind","syntheticBootstrapAdmission","protectedMode",false));
    JSONObject w=warm.getJSONObject("probe");if(!w.getJSONObject("fetch").optBoolean("ok")||!w.getJSONObject("newWebSocket").optBoolean("ok")||!w.getJSONObject("existingWebSocket").optBoolean("ok")||!w.getJSONObject("dedicatedWorker").optBoolean("ok"))throw new IOException("Warmup reachability failed; later failures cannot prove blocking");
    startVpn("full");probe("full-vpn",admitVpnRoute("full"));
    startVpn("split");JSONObject split=probe("split-vpn",admitVpnRoute("split"));
    JSONObject splitProbe=split.getJSONObject("probe"),splitSocket=splitProbe.getJSONObject("existingWebSocket");
    if(!splitProbe.optBoolean("explicitPositiveControlReseed")||splitSocket.optInt("socketGeneration")!=2||!"split-vpn".equals(splitSocket.optString("establishedPhase"))||splitSocket.optBoolean("automaticallyRecreated",true))throw new IOException("The explicit split-phase WSS seed identity is invalid");
    boolean liveSplitControl=splitSocket.optBoolean("ok")&&splitSocket.optInt("serverConnection")>0;
    if(splitSocket.optBoolean("ok")&&!liveSplitControl)throw new IOException("Reported split WSS echo has no server connection identity");
    // A fixed candidate may correctly deny every split-route request. Keep
    // testing the actual VPN removal/new-request boundary in that case, while
    // explicitly declining any conclusion about a previously live connection.
    existingConnectionAfterRemoval=J.obj("status",liveSplitControl?"observation-pending-independent-server-verification":"unverified","reason",liveSplitControl?"live-split-server-echo-control":"no-live-split-control","liveSplitControl",liveSplitControl,"socketGeneration",2,"establishedPhase","split-vpn","splitServerConnection",splitSocket.optInt("serverConnection"),"independentServerVerificationRequired",true);
    NetworkCatalog.put(split,"existingConnectionControl",J.parse(existingConnectionAfterRemoval.toString()));
    JSONObject beforeRemoval=snapshot();event("beforeActualVpnRemoval",beforeRemoval);stopVpn();
    await("Production network callback closes admission after actual VPN removal",()->{JSONObject s=snapshot();return !s.optBoolean("guardVpnActive")&&s.optBoolean("guardBlocked")&&!s.optBoolean("networkReady")&&s.optLong("connectionEpoch")>beforeRemoval.optLong("connectionEpoch");},10000);
    JSONObject removed=probe("vpn-removed",J.obj("kind","noFixtureReadinessMutation","productionCallbackObserved",true,"beforeRemoval",beforeRemoval));
    JSONObject removedProbe=removed.getJSONObject("probe"),removedSocket=removedProbe.getJSONObject("existingWebSocket");
    if(removedProbe.optBoolean("explicitPositiveControlReseed",true)||removedSocket.optInt("socketGeneration")!=2||!"split-vpn".equals(removedSocket.optString("establishedPhase"))||removedSocket.optBoolean("automaticallyRecreated",true))throw new IOException("VPN-removal observation did not preserve the explicitly seeded WSS object identity");
    if(liveSplitControl&&removedSocket.optInt("serverConnection")!=splitSocket.optInt("serverConnection"))throw new IOException("VPN-removal observation replaced the positively controlled server connection");
    NetworkCatalog.put(existingConnectionAfterRemoval,"removedServerConnection",removedSocket.optInt("serverConnection"));
    NetworkCatalog.put(existingConnectionAfterRemoval,"removedEchoObserved",removedSocket.optBoolean("ok"));
    NetworkCatalog.put(removed,"existingConnectionControl",J.parse(existingConnectionAfterRemoval.toString()));
  }catch(Throwable failure){error=failure;}finishDiagnostic(error);}
  void finishDiagnostic(Throwable failure){
    if(!concluded.compareAndSet(false,true))return;
    JSONObject finalSnapshot=new JSONObject();Throwable result=failure;
    try{if(owner!=null)finalSnapshot=snapshot();stopVpn();}catch(Throwable cleanup){if(result==null)result=cleanup;event("cleanupError",J.obj("error",String.valueOf(cleanup)));}
    JSONArray routeCopy,eventCopy;synchronized(routes){routeCopy=copyArray(routes);}synchronized(events){eventCopy=copyArray(events);}
    JSONObject report=J.obj("schema",1,"status",result==null?"completed":"failed","diagnosticOnly",true,"protectionAcceptance",false,"releaseAcceptance",false,"sourceCommit",source,"sourceTree",buildIdentity.optString("sourceTree"),"runNonce",nonce,"buildIdentity",buildIdentity,"actualAndroidExecution",true,"actualGeckoExecution",view!=null&&view.ready,"androidSdk",android.os.Build.VERSION.SDK_INT,"pid",android.os.Process.myPid(),"physicalPhoneAcceptance",false,"officialChatGptSiteTested",false,"publicNetworkTraffic",false,"origin",origin,"documentIdentity",documentIdentity,"phases",phases,"existingConnectionAfterRemoval",existingConnectionAfterRemoval,"routes",routeCopy,"routesDropped",routesDropped,"events",eventCopy,"eventsDropped",eventsDropped,"finalSnapshot",finalSnapshot,"vpnFixtureFinal",NetworkProtectionFixtureVpnService.snapshot(),"fixtureCertificateExceptions",view==null?0:view.certificateExceptions,"independentServerVerificationRequired",true,"unverified",J.arr("Physical phone","Actual Wi-Fi to cellular transition","Public IPv6 and DNS paths","Service Worker and Shared Worker","Internal Mihomo fixed-exit failure","Complete normal website connection preflight","Official ChatGPT and real account traffic"),"scope","Controlled AVD HTTPS/WSS/Dedicated Worker observations through the unchanged production route and actual CM/VpnService. A synthetic readiness admission and narrowly allowed test origin isolate only the VPN per-request gate. Node server and TUN bytes must be independently reconciled; completed is not safe/protected.");
    if(result!=null){NetworkCatalog.put(report,"error",String.valueOf(result));NetworkCatalog.put(report,"failureType",result.getClass().getName());}
    try{NormalCaretSdkReceipt.copySdkFields(sdkIdentity,report);}catch(Throwable identityError){NetworkCatalog.put(report,"status","failed");NetworkCatalog.put(report,"identityError",String.valueOf(identityError));}
    try{ui(()->{if(view!=null)view.destroy();if(owner!=null){owner.deleted=true;owner.handler.removeCallbacks(owner.tick);}return null;});}catch(Exception cleanup){NetworkCatalog.put(report,"browserCleanupError",String.valueOf(cleanup));NetworkCatalog.put(report,"status","failed");}
    try{File file=new File(getFilesDir(),FILE);AtomicFile atomic=new AtomicFile(file);FileOutputStream out=null;try{out=atomic.startWrite();out.write((report.toString()+"\n").getBytes(StandardCharsets.UTF_8));atomic.finishWrite(out);}catch(Throwable write){if(out!=null)atomic.failWrite(out);throw write;}Log.i(TAG,J.obj("status",report.optString("status"),"runNonce",nonce,"reportFile",FILE,"phaseCount",phases.length(),"protectionAcceptance",false).toString());}catch(Throwable write){Log.e(TAG,"Diagnostic export failed",write);}finally{worker.shutdown();}
  }
  static JSONArray copyArray(JSONArray value){try{return new JSONArray(value.toString());}catch(Exception impossible){throw new IllegalStateException(impossible);}}
  @Override protected void onDestroy(){
    if(!concluded.get()){event("activityDestroyed",J.obj("unfinished",true));worker.shutdownNow();}
    super.onDestroy();
  }
}
