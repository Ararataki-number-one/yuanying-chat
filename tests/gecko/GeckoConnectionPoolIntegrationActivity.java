package local.pocketchat;

import android.app.Activity;
import android.content.Context;
import android.os.Bundle;
import android.os.SystemClock;
import android.util.Log;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.LinearLayout;
import android.widget.TextView;
import org.json.*;
import org.mozilla.geckoview.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import java.util.*;
import java.util.concurrent.*;
import javax.net.ssl.*;

/** Real Gecko HTTP/2 pooling over the formal managed Mihomo + two loopback SOCKS hops. */
public final class GeckoConnectionPoolIntegrationActivity extends Activity {
  static final String ORIGIN="https://127.0.0.1:9877",TAG="PocketGeckoPool";
  static final String PAYLOAD="pool-payload-".repeat(700);
  final JSONArray checks=new JSONArray(),requests=new JSONArray(),routes=new JSONArray(),transitions=new JSONArray();
  volatile boolean finished;ChatSession session;FixtureView view;
  NetworkOptimizationIntegrationActivity.TestNetwork network;
  NetworkOptimizationIntegrationActivity.HttpFixture site,plain;
  NetworkOptimizationIntegrationActivity.Socks fixed,entryA,entryB;
  final ExecutorService runner=Executors.newSingleThreadExecutor();
  interface Work<T>{T run()throws Exception;}
  <T>T ui(Work<T> work)throws Exception{
    CompletableFuture<T> done=new CompletableFuture<>();runOnUiThread(()->{try{done.complete(work.run());}catch(Throwable error){done.completeExceptionally(error);}});
    return done.get(20,TimeUnit.SECONDS);
  }
  void event(String kind,JSONObject value){Log.i(TAG,J.obj("kind",kind,"value",value).toString());}
  void check(String name,boolean passed){checks.put(J.obj("name",name,"pass",passed));event("check",J.obj("name",name,"pass",passed));if(!passed)throw new AssertionError(name);}
  JSONObject eval(String code)throws Exception{
    CompletableFuture<JSONObject> done=new CompletableFuture<>();ui(()->{view.evaluateJavascript(code,raw->done.complete(J.parse(raw)));return null;});
    return done.get(15,TimeUnit.SECONDS);
  }
  void await(String name,Work<Boolean> condition,long millis)throws Exception{
    long limit=SystemClock.elapsedRealtime()+millis;
    while(!condition.run()){if(SystemClock.elapsedRealtime()>limit)throw new IOException(name+" timed out");Thread.sleep(80);}
  }
  static final class FixtureView extends GeckoWebView {
    final GeckoConnectionPoolIntegrationActivity test;boolean legacyEpoch,poolInstance;int certificateExceptions;
    final NetworkPoolIdentity secondPool=new NetworkPoolIdentity();
    FixtureView(Context c,ChatSession owner,GeckoConnectionPoolIntegrationActivity test){super(c,owner);this.test=test;}
    @Override protected boolean allowedUrl(String target){return target!=null&&target.startsWith(ORIGIN+"/");}
    @Override JSONObject route(String target){
      JSONObject actual=super.route(target);
      String key=actual.optString("connectionIsolationKey");
      if(!key.isEmpty()&&legacyEpoch)NetworkCatalog.put(actual,"connectionIsolationKey","environment-"+Profiles.slot(owner.context)+"-"+owner.connectionEpoch);
      if(!key.isEmpty()&&poolInstance){
        NativeNetwork n=test.network;NativeNetwork.ExitRouteReceipt r=n.verifiedRoute;
        if(r==null)actual=blocked();else{
          NetworkPoolIdentity.Route value=new NetworkPoolIdentity.Route(1,r.generation,r.pid,r.servicePid,r.configuration,r.entry,r.fingerprint,r.serial,r.controller,r.proxy,r.token);
          String isolated=secondPool.key(value,owner.browserDefaultNetwork.snapshot());
          if(isolated==null)actual=blocked();else NetworkCatalog.put(actual,"connectionIsolationKey",isolated);
        }
      }
      JSONObject record=J.obj("url",target,"route",actual,"guardAllowed",owner.guard.allowed(),"epoch",owner.connectionEpoch,
        "legacyEpochCounterfactual",legacyEpoch,"alternatePoolInstance",poolInstance,"at",SystemClock.elapsedRealtime());
      synchronized(test.routes){test.routes.put(record);}test.event("route",record);return actual;
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
          if(ORIGIN.concat("/pool").equals(target)&&certificateExceptions==0&&error.category==WebRequestError.ERROR_CATEGORY_SECURITY&&error.code==WebRequestError.ERROR_SECURITY_BAD_CERT){
            certificateExceptions++;test.event("certificateException",J.obj("target",target,"category",error.category,"code",error.code,"temporary",true));
            // Official SDK error-document API, only in this isolated test package
            // and only for its newly generated loopback certificate. Production
            // navigation delegates and HTTPS verification remain unchanged.
            String html="<!doctype html><title>Controlled certificate exception</title><script>"
              +"document.addCertException(true).then(()=>location.replace("+JSONObject.quote(target)+"))"
              +".catch(()=>document.body.textContent='fixture certificate exception failed')</script>";
            return GeckoResult.fromValue("data:text/html;base64,"+Base64.getEncoder().encodeToString(html.getBytes(StandardCharsets.UTF_8)));
          }
          test.event("loadError",J.obj("target",target,"category",error.category,"code",error.code));return original.onLoadError(s,target,error);
        }
      });return sdk;
    }
  }
  @Override public void onCreate(Bundle state){super.onCreate(state);if(!getPackageName().endsWith(".test"))throw new SecurityException("Only the isolated regression APK may run this fixture");runner.execute(this::run);}
  SSLContext fixtureTls()throws Exception{
    KeyStore store=KeyStore.getInstance("PKCS12");try(InputStream in=getAssets().open("network-fixture.p12")){store.load(in,"network-fixture".toCharArray());}
    KeyManagerFactory keys=KeyManagerFactory.getInstance(KeyManagerFactory.getDefaultAlgorithm());keys.init(store,"network-fixture".toCharArray());
    TrustManagerFactory trust=TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm());trust.init(store);
    SSLContext tls=SSLContext.getInstance("TLS");tls.init(keys.getKeyManagers(),trust.getTrustManagers(),null);return tls;
  }
  JSONObject identity()throws Exception{
    JSONObject state=network.transport.call("snapshot","");
    return J.obj("pid",state.optInt("pid"),"servicePid",state.optInt("servicePid"),"generation",state.optString("generation"),
      "configuration",state.optString("configuration"),"proxyPort",network.proxyPort,"controllerPort",network.controllerPort,
      "entry",network.currentEntry,"routeSerial",network.routeSerial,"fixedExitHash",network.fingerprint,
      "verified",network.verifiedRouteCurrent(),"epoch",ui(()->session.connectionEpoch),"poolKey",ui(()->view.internalPoolKey(network)));
  }
  void trace(String name,JSONObject before,JSONObject after){JSONObject record=J.obj("name",name,"before",before,"after",after);transitions.put(record);event("transition",record);}
  JSONObject fetch(String id,boolean expected)throws Exception{
    int fixedBefore=fixed.connections,aBefore=entryA.connections,bBefore=entryB.connections;
    String actualEntry=network.currentEntry;int proxyPort=network.proxyPort;
    // The formal bridge evaluates in the MV2 extension sandbox. Gecko's official
    // content.fetch is bound to the page window, preserving its TLS exception,
    // cookies and browser pool; extension-global fetch has different semantics.
    String quoted=JSONObject.quote(id),target=JSONObject.quote(ORIGIN+"/bytes?id="+id);JSONObject begun=eval("(()=>{window.__poolResults??={};if(typeof content==='undefined'||typeof content.fetch!=='function')return {started:false,error:'page content.fetch unavailable'};const began=performance.now();content.fetch("+target+",{cache:'no-store',credentials:'same-origin'})"
      +".then(async r=>{const v=await r.json();window.__poolResults["+quoted+"]={ok:r.ok,...v,durationMs:performance.now()-began}})"
      +".catch(e=>window.__poolResults["+quoted+"]={ok:false,error:String(e)});return {started:true}})()");
    check(id+" starts one explicit actual Gecko request",begun.optBoolean("started"));
    final JSONObject[] result={null};await(id+" real response",()->{JSONObject value=eval("window.__poolResults?.["+quoted+"]||({})");if(!value.has("ok"))return false;result[0]=value;return true;},15000);
    JSONObject value=result[0];
    JSONObject safe=J.obj("id",id,"ok",value.optBoolean("ok"),"protocol",value.optString("protocol"),"connection",value.optInt("connection"),"streamId",value.optLong("streamId"),"durationMs",value.optDouble("durationMs",-1),"bodyBytes",value.optString("body").getBytes(StandardCharsets.UTF_8).length,"bodyHash",NativeNetwork.hash(value.optString("body")),"error",value.optString("error"),
      "requestRealm","page-content-fetch","entry",actualEntry,"proxyPort",proxyPort,"fixedConnectionsBefore",fixedBefore,"fixedConnectionsAfter",fixed.connections,"entryAConnectionsBefore",aBefore,"entryAConnectionsAfter",entryA.connections,"entryBConnectionsBefore",bBefore,"entryBConnectionsAfter",entryB.connections);
    // Preserve actual failure details before an assertion terminates the run.
    requests.put(safe);event("request",safe);
    check(id+" completes with the expected guarded outcome",value.optBoolean("ok")==expected);
    if(expected){check(id+" negotiates genuine HTTP/2 and preserves the entire response",value.optString("protocol").equals("h2")&&value.optLong("streamId")>0&&value.optInt("connection")>0&&PAYLOAD.equals(value.optString("body"))&&id.equals(value.optString("id")));}
    return safe;
  }
  void callbackRecover()throws Exception{
    CountDownLatch done=new CountDownLatch(1);final boolean[] success={false};ui(()->{network.recover((ok,message)->{success[0]=ok;done.countDown();});return null;});
    check("The existing asynchronous network recovery succeeds",done.await(25,TimeUnit.SECONDS)&&success[0]);
    network.worker.submit(()->{}).get(5,TimeUnit.SECONDS);
  }
  void checkNewConnection(String name,JSONObject before,JSONObject after){check(name,before.optInt("connection")!=after.optInt("connection")&&after.optInt("connection")>0);}
  void stopThreads(NativeNetwork value){if(value==null)return;try{value.stopNow();}catch(Exception ignored){}value.worker.shutdownNow();value.probes.shutdownNow();value.closers.shutdownNow();value.traffic.reader.shutdownNow();}
  void run(){JSONObject report=J.obj("status","failed","actualAndroidExecution",true,"actualGeckoExecution",true,"actualMihomoExecution",true,
      "protocol","h2","defaultNetworkCases","Injected event values through the production DefaultNetwork state, not a physical Wi-Fi handover",
      "environmentCase","Separate pool instance with slot 1 in the same Gecko runtime; private-profile/login isolation is exercised by the existing multi-process suite",
      "recoveryCase","Real NativeNetwork.recover with an advanced asynchronous ChatSession epoch; no document navigation or resend",
      "testOnlyCertificateException",true,"publicNetworkTraffic",false,"requestRealm","page-content-fetch","webSocketRealm","page-content-WebSocket");
    try{
      site=new NetworkOptimizationIntegrationActivity.HttpFixture(fixtureTls());plain=new NetworkOptimizationIntegrationActivity.HttpFixture(null);
      fixed=new NetworkOptimizationIntegrationActivity.Socks(0);entryA=new NetworkOptimizationIntegrationActivity.Socks(0);entryB=new NetworkOptimizationIntegrationActivity.Socks(0);
      site.start();plain.start();fixed.start();entryA.start();entryB.start();
      // Pool mode admits both test entries; manual mode exposes only A.
      // TestNetwork has no health monitor, so every transition below is explicit.
      JSONObject config=J.obj("subscriptionUrl","https://synthetic.invalid/gecko-pool","exitHost","127.0.0.1","exitPort",fixed.port(),"entryMode","random","entryPool",J.arr("Entry|a","Entry|b"),"entry","");
      String yaml="proxies:\n  - {name: a, type: socks5, server: 127.0.0.1, port: "+entryA.port()+"}\n  - {name: b, type: socks5, server: 127.0.0.1, port: "+entryB.port()+"}\n";
      SecretStore vault=new SecretStore(this);vault.save(config);vault.put("subscription",yaml.getBytes(StandardCharsets.UTF_8));vault.put("subscription-meta",J.obj("urlHash",NativeNetwork.hash(config.getString("subscriptionUrl")),"updatedAt",System.currentTimeMillis()).toString().getBytes(StandardCharsets.UTF_8));
      getSharedPreferences("chat",0).edit().putString("lastGoodEntry","Entry|a").putString("browserEngine","gecko").putString("networkMode","internal")
        .putBoolean("networkConfigured",true).putBoolean("requireExternalVpn",false).putBoolean("pageMode",true).putInt("privacyLevel",0).putBoolean("backgroundWait",false).putBoolean("replyNotice",false).commit();
      network=new NetworkOptimizationIntegrationActivity.TestNetwork(this,site,plain,true);
      // Replace only this freshly cleared test process's singleton, so production
      // route()/guard consult the actual controlled managed service.
      java.lang.reflect.Field singleton=NativeNetwork.class.getDeclaredField("instance");singleton.setAccessible(true);singleton.set(null,network);network.startNow();
      check("The formal managed service starts a genuinely verified two-hop chain",network.ready&&network.transport!=null&&network.verifiedRouteCurrent()&&network.currentEntry.equals("Entry|a")&&fixed.connections>0&&entryA.connections>0);
      ui(()->{
        ProfileCatalog.get(this).created(Profiles.slot(this));ChatSession.browserFactory=(c,owner)->new FixtureView(c,owner,this);session=ChatSession.get(this);view=(FixtureView)session.web;
        session.handler.removeCallbacks(session.tick);session.networkReady=true;session.uiVisible=true;session.guard.setBlocked(false);
        view.setWebViewClient(new WebViewClient(){@Override public void onPageStarted(WebView ignored,String url,android.graphics.Bitmap icon){session.handler.removeCallbacks(session.tick);}@Override public void onPageFinished(WebView ignored,String url){session.navigating=false;session.handler.removeCallbacks(session.tick);}});
        LinearLayout root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);root.setFitsSystemWindows(true);TextView label=new TextView(this);label.setText("真实 Gecko HTTP/2 连接复用回归 · 仅受控流量");root.addView(label);view.setHost(this);root.addView(view,new LinearLayout.LayoutParams(-1,0,1));setContentView(root);return null;
      });
      await("Gecko initialization",()->ui(()->view.ready&&view.privacyReady&&session.browserDefaultNetwork.snapshot().usable()),60000);
      check("A fresh runtime obtains the real Android default-network snapshot",ui(()->session.browserDefaultNetwork.snapshot().usable()));
      ui(()->{view.loadUrl(ORIGIN+"/pool");return null;});
      await("Actual controlled TLS document",()->eval("({ready:location.href==="+JSONObject.quote(ORIGIN+"/pool")+"&&!!document.getElementById('pool-ready')})").optBoolean("ready"),35000);
      check("The test certificate exception is scoped to one localhost document",view.certificateExceptions==1);
      JSONObject pageApis=eval("({pageFetch:typeof content!=='undefined'&&typeof content.fetch==='function',pageWebSocket:typeof content!=='undefined'&&typeof content.WebSocket==='function'})");
      event("pageApis",pageApis);
      check("The official MV2 sandbox exposes page-bound fetch and WebSocket",pageApis.optBoolean("pageFetch")&&pageApis.optBoolean("pageWebSocket"));
      JSONObject first=fetch("initial",true),warm=fetch("warm",true);check("Warm actual Gecko HTTP/2 requests reuse one TLS/TCP connection",first.optInt("connection")==warm.optInt("connection")&&warm.optLong("streamId")>first.optLong("streamId"));
      eval("(()=>{window.__poolSocket={echoes:0,connection:0,closed:false};const ws=new content.WebSocket("+JSONObject.quote("wss://127.0.0.1:9877/ws")+");window.__poolSocket.ws=ws;let n=0;ws.onopen=()=>{window.__poolSocket.timer=setInterval(()=>{if(ws.readyState===1)ws.send('frame-'+(++n))},80)};ws.onmessage=e=>{const v=JSON.parse(e.data);window.__poolSocket.echoes++;window.__poolSocket.connection=v.connection;window.__poolSocket.last=v.payload};ws.onclose=()=>window.__poolSocket.closed=true;return {started:true}})()");
      await("Actual protected WSS frames",()->eval("({echoes:window.__poolSocket?.echoes||0})").optInt("echoes")>=5,15000);
      JSONObject framesBefore=eval("({echoes:window.__poolSocket.echoes,connection:window.__poolSocket.connection,closed:window.__poolSocket.closed})");
      JSONObject stableBefore=identity();ui(()->{session.connectionEpoch++;return null;});callbackRecover();JSONObject stableAfter=identity();trace("healthy-managed-recovery",stableBefore,stableAfter);
      check("Healthy actual recovery preserves the verified core lifetime, entry and browser pool",stableBefore.optString("poolKey").equals(stableAfter.optString("poolKey"))&&!stableBefore.optString("poolKey").isEmpty()&&stableBefore.optInt("pid")==stableAfter.optInt("pid")&&stableBefore.optLong("routeSerial")==stableAfter.optLong("routeSerial")&&stableAfter.optLong("epoch")==stableBefore.optLong("epoch")+1&&stableAfter.optBoolean("verified"));
      JSONObject recovered=fetch("healthy-recovery",true);check("The new pool identity reuses the same actual HTTP/2 TLS connection after healthy recovery",warm.optInt("connection")==recovered.optInt("connection"));
      await("WSS survives healthy recovery",()->eval("({echoes:window.__poolSocket.echoes})").optInt("echoes")>framesBefore.optInt("echoes")+3,10000);
      JSONObject framesAfter=eval("({echoes:window.__poolSocket.echoes,connection:window.__poolSocket.connection,closed:window.__poolSocket.closed})");NetworkCatalog.put(report,"webSocketBefore",framesBefore);NetworkCatalog.put(report,"webSocketAfter",framesAfter);
      check("Actual WSS frames survive recovery without reconnect or resend",framesBefore.optInt("connection")==framesAfter.optInt("connection")&&!framesAfter.optBoolean("closed")&&framesAfter.optInt("echoes")>framesBefore.optInt("echoes"));
      ui(()->{view.legacyEpoch=true;return null;});JSONObject legacyBefore=fetch("legacy-before",true),legacyIdentityBefore=identity();ui(()->{session.connectionEpoch++;return null;});callbackRecover();JSONObject legacyIdentityAfter=identity(),legacyAfter=fetch("legacy-after",true);trace("legacy-counterfactual-healthy-recovery",legacyIdentityBefore,legacyIdentityAfter);
      check("The legacy counterfactual recovery changes only the asynchronous epoch",legacyIdentityBefore.optString("poolKey").equals(legacyIdentityAfter.optString("poolKey"))&&legacyIdentityBefore.optInt("pid")==legacyIdentityAfter.optInt("pid")&&legacyIdentityBefore.optLong("routeSerial")==legacyIdentityAfter.optLong("routeSerial")&&legacyIdentityAfter.optLong("epoch")==legacyIdentityBefore.optLong("epoch")+1);
      checkNewConnection("The exact old epoch-key counterfactual opens another real TLS connection for the same route",legacyBefore,legacyAfter);ui(()->{view.legacyEpoch=false;return null;});
      JSONObject routeA=fetch("route-a",true),aIdentity=identity();network.selectNow("Entry|b");network.verifyExit();JSONObject bIdentity=identity();JSONObject routeB=fetch("route-b",true);trace("real-entry-a-to-b",aIdentity,bIdentity);
      checkNewConnection("A real entry change starts a separate actual HTTP/2 connection",routeA,routeB);check("The B request opens both real SOCKS hops through the second entry and the same fixed exit",routeB.optInt("entryBConnectionsAfter")>routeB.optInt("entryBConnectionsBefore")&&routeB.optInt("fixedConnectionsAfter")>routeB.optInt("fixedConnectionsBefore")&&network.currentEntry.equals("Entry|b")&&network.exitIp.equals("203.0.113.8"));
      network.selectNow("Entry|a");network.verifyExit();JSONObject returnedIdentity=identity(),returnedA=fetch("returned-a",true);trace("real-entry-b-to-a",bIdentity,returnedIdentity);
      checkNewConnection("Returning to entry A cannot reuse its previous lifetime's actual connection",routeA,returnedA);check("A to B to A creates new opaque identities while retaining the fixed exit",!aIdentity.optString("poolKey").equals(returnedIdentity.optString("poolKey"))&&returnedIdentity.optLong("routeSerial")>aIdentity.optLong("routeSerial"));
      JSONObject coreBefore=identity();network.stopNow();network.startNow();JSONObject coreAfter=identity();trace("real-core-restart",coreBefore,coreAfter);JSONObject restarted=fetch("core-restarted",true);
      check("Restarting the real managed core changes its generation and admitted pool",coreBefore.optInt("pid")!=coreAfter.optInt("pid")&&!coreBefore.optString("generation").equals(coreAfter.optString("generation"))&&!coreBefore.optString("poolKey").equals(coreAfter.optString("poolKey")));
      checkNewConnection("A new real core lifetime cannot reuse the old TLS connection",returnedA,restarted);
      NetworkPoolIdentity.NetworkSnapshot actual=ui(()->session.browserDefaultNetwork.snapshot());JSONObject beforeNetwork=identity();ui(()->{session.browserDefaultNetwork.available("controlled-network-b");session.browserDefaultNetwork.capabilities("controlled-network-b",true,false);return null;});JSONObject afterNetwork=identity();trace("injected-default-network-a-to-b",beforeNetwork,afterNetwork);JSONObject differentNetwork=fetch("network-b",true);
      checkNewConnection("A changed admitted default-network event partitions real Gecko connections",restarted,differentNetwork);ui(()->{session.browserDefaultNetwork.available(actual.identity);session.browserDefaultNetwork.capabilities(actual.identity,true,actual.vpn);return null;});JSONObject returnNetwork=fetch("network-return-a",true);
      checkNewConnection("A to B to A default-network event cannot resurrect an earlier connection",restarted,returnNetwork);
      ui(()->{view.poolInstance=true;return null;});JSONObject alternate=fetch("alternate-pool",true);checkNewConnection("A second environment pool instance cannot share the first pool's actual connection",returnNetwork,alternate);ui(()->{view.poolInstance=false;return null;});
      ui(()->{session.guard.setBlocked(true);return null;});fetch("guard-blocked",false);ui(()->{session.guard.setBlocked(false);return null;});
      NativeNetwork.ExitRouteReceipt saved=network.verifiedRoute;network.verifiedRoute=null;fetch("receipt-blocked",false);network.verifiedRoute=saved;
      ui(()->{session.browserDefaultNetwork.unknown();return null;});fetch("unknown-network-blocked",false);ui(()->{session.browserDefaultNetwork.initial(actual.identity,true,actual.vpn);return null;});
      JSONObject restored=fetch("guard-restored",true);checkNewConnection("Restoring admission after an unknown network uses a fresh actual TLS connection",returnNetwork,restored);
      check("The app's actual fixture keeps the same unsent draft and performs no send",eval("({draft:document.getElementById('prompt-textarea').value,sends:Number(document.getElementById('send-count').textContent)})").optString("draft").equals("unsent pool draft")&&eval("({sends:Number(document.getElementById('send-count').textContent)})").optInt("sends")==0);
      NetworkCatalog.put(report,"fixedExitConnections",fixed.connections);NetworkCatalog.put(report,"entryAConnections",entryA.connections);NetworkCatalog.put(report,"entryBConnections",entryB.connections);NetworkCatalog.put(report,"status","passed");
    }catch(Throwable error){NetworkCatalog.put(report,"error",error.toString());}
    finally{
      if(view!=null)try{ui(()->{session.handler.removeCallbacks(session.tick);view.destroy();return null;});}catch(Exception ignored){}
      stopThreads(network);for(AutoCloseable fixture:new AutoCloseable[]{site,plain,fixed,entryA,entryB})if(fixture!=null)try{fixture.close();}catch(Exception ignored){}
    }
    finished=true;NetworkCatalog.put(report,"checks",checks);NetworkCatalog.put(report,"requests",requests);NetworkCatalog.put(report,"routes",routes);NetworkCatalog.put(report,"transitions",transitions);
    try{J.write(new File(getFilesDir(),"gecko-pool-results.json"),report.toString(2));}catch(Exception ignored){}
    JSONObject result=J.obj("status",report.optString("status"),"checkCount",checks.length(),"requestCount",requests.length(),"routeCount",routes.length(),"transitionCount",transitions.length(),"error",report.optString("error"));event("report",result);runOnUiThread(this::finish);runner.shutdown();
  }
}
