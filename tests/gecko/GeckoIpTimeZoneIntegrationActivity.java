package local.pocketchat;

import android.app.AlertDialog;
import android.os.*;
import android.view.*;
import android.widget.*;
import java.io.*;
import java.lang.reflect.Field;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.Consumer;
import org.json.*;
import org.mozilla.geckoview.*;

/** Actual canonical MainActivity/:profile6. All geo responses are controlled
 * synthetic HTTPS fixtures, never evidence of public geolocation accuracy. */
public final class GeckoIpTimeZoneIntegrationActivity extends MainActivity {
  static final String ORIGIN="https://fp-a.pocketchat.test", ROOT=ORIGIN+"/env-policy?phase=";
  static final String GEO="https://ipwho.is/?fields=success,ip,timezone.id";
  final Handler probe=new Handler(Looper.getMainLooper());
  final ExecutorService io=Executors.newSingleThreadExecutor();
  final JSONArray checks=new JSONArray(),events=new JSONArray();
  final JSONObject cases=new JSONObject();
  final Map<GeckoSession,JSONObject> securities=new IdentityHashMap<>();
  JSONObject build,setup,lastPage=new JSONObject(),lastSample=new JSONObject();
  String nonce,stage="startup",failure="",failedStage="";
  long deadline,wholeDeadline;boolean terminal,roots;GeckoTimeZoneStore.Ticket originalTicket;
  GeckoWebView.IpLookup isolationClaim;ChromiumRouteLease.Handle observedLease;
  JSONObject applyLeaseProof=new JSONObject();
  final JSONArray diagnosticHistory=new JSONArray();long lastDiagnosticAt=-1000;String lastDiagnosticSignature="";
  final java.util.concurrent.atomic.AtomicIntegerArray routingCounters=new java.util.concurrent.atomic.AtomicIntegerArray(15);
  JSONObject extensionDiagnostic=new JSONObject();int extensionDiagnosticAccepted,extensionDiagnosticRejected;WebExtension diagnosticExtension;GeckoRuntime diagnosticRuntime;
  interface Ready{boolean get()throws Exception;}interface Step{void run()throws Exception;}

  @Override public void onCreate(Bundle saved){try{
    BrowserFingerprintIntegrationActivity.validateIntent(this);nonce=getIntent().getStringExtra("runNonce");
    build=IntegrationBuildIdentity.read(this);if(!build.getString("sourceCommit").equals(getIntent().getStringExtra("sourceCommit")))throw new SecurityException("Installed source differs");
    IpTimeZoneFixtureScopes.requireArmed(this,build.getString("sourceCommit"),nonce);
    setup=IpTimeZoneFixtureScopes.read(this,IpTimeZoneFixtureScopes.SETUP);
    // Actual vault/default loader on a separate test writer before the real
    // MainActivity can construct a session. No native admission is fabricated.
    Future<GeckoTimeZoneStore.State> first=io.submit(()->{
      if(new SecretStore(this).get(GeckoTimeZoneStore.STORE)!=null)throw new IOException("Missing-store default precondition lost");
      return GeckoTimeZoneStore.load(this);
    });
    GeckoTimeZoneStore.State initial=first.get(5,TimeUnit.SECONDS);
    if(initial.revision!=1||!initial.spec.followsIp()||initial.identity.slot!=6)throw new IOException("Actual missing store did not select default IP");
    setup.put("actualDefaultStoreLoadYet",true).put("defaultSpec",initial.spec.json()).put("defaultRevision",initial.revision).put("loadedIdentity",initial.identity.json());
    getSharedPreferences("chat",0).edit().clear().putBoolean("environmentInitialized",true).putString("networkMode","external")
        .putString("proxy",proxy("socks")).putBoolean("networkConfigured",true).putBoolean("requireExternalVpn",false)
        .putString("geckoBrowserUrl",ROOT+"gecko-new-york").putString("url",ROOT+"gecko-new-york").putInt("privacyLevel",1).putBoolean("saveDraft",true).commit();
    getSharedPreferences("universal-browser",0).edit().clear().commit();
    ChatSession.browserFactory=(context,owner)->new Observed(context,owner);
    getIntent().putExtra("legacyChat",true);super.onCreate(null);
    wholeDeadline=SystemClock.elapsedRealtime()+900000;deadline=SystemClock.elapsedRealtime()+90000;publish();
    waitFor("actual main default IP",this::ready,()->capture("default-socks","America/New_York",true,value->{try{
      originalTicket=ticket();check("default.actual-main-profile6",remote instanceof Observed&&geckoAddress!=null&&geckoAddress.address.isShown()&&Profiles.slot(this)==6);
      check("default.missing-store-ip",setup.getBoolean("timezoneSealedRecordMissing")&&initial.spec.followsIp());
      routeSwitch();
    }catch(Throwable error){failed(error);}}));
  }catch(Throwable error){failed(error);}}

  final class Observed extends GeckoWebView {
    Observed(android.content.Context context,ChatSession owner){super(context,owner);}
    @Override void applyAddonState(GeckoRuntime expected,WebExtension value,boolean disabled,long serial){
      try{if(!disabled&&addonStateSerial==serial&&builtinAddonCurrent(expected,value,false))installExtensionDiagnostic(expected,value);}catch(RuntimeException unavailable){extensionDiagnosticRejected=Math.min(10000,extensionDiagnosticRejected+1);}
      super.applyAddonState(expected,value,disabled,serial);
    }
    @Override boolean ipBootstrapRequest(String target,String method,String token,String stamp){
      boolean result=super.ipBootstrapRequest(target,method,token,stamp);if(geoHostVariant(target))routingCount(result?11:12);routingCount(GEO.equals(target)?result?0:1:result?2:3);return result;
    }
    @Override JSONObject protectedNetworkRoute(String target){
      JSONObject result=super.protectedNetworkRoute(target);if(geoHostVariant(target))routingCount(13);if(GEO.equals(target))routingCount(4+selectedRoute(result));return result;
    }
    @Override JSONObject route(String target){
      JSONObject result=super.route(target);if(geoHostVariant(target))routingCount(14);if(GEO.equals(target))routingCount(selectedRoute(result)==0?9:10);return result;
    }
    @Override GeckoSession newSession(){runtime.getSettings().setEnterpriseRootsEnabled(true);roots=runtime.getSettings().getEnterpriseRootsEnabled();
      GeckoSession sdk=super.newSession();GeckoSession.ProgressDelegate original=sdk.getProgressDelegate();
      sdk.setProgressDelegate(new GeckoSession.ProgressDelegate(){
        public void onPageStart(GeckoSession s,String url){event("page-start",s,url);original.onPageStart(s,url);}
        public void onPageStop(GeckoSession s,boolean ok){event(ok?"page-stop-true":"page-stop-false",s,loadingTargets.getOrDefault(s,""));original.onPageStop(s,ok);}
        public void onProgressChange(GeckoSession s,int progress){original.onProgressChange(s,progress);}
        public void onSessionStateChange(GeckoSession s,GeckoSession.SessionState state){original.onSessionStateChange(s,state);}
        public void onSecurityChange(GeckoSession s,SecurityInformation security){original.onSecurityChange(s,security);try{
          if(!Arrays.asList(BrowserFingerprintFixture.A,BrowserFingerprintFixture.B).contains(security.host))return;
          String leaf=security.certificate==null?"":BrowserFingerprintFixture.sha(security.certificate.getEncoded());
          JSONObject proof=J.obj("host",security.host,"isSecure",security.isSecure,"isException",security.isException,"leafDerSha256",leaf,"enterpriseRootsReadback",roots);
          securities.put(s,proof);if(!security.isSecure||security.isException||!leaf.equals(getIntent().getStringExtra("expectedLeafSha256")))failed(new SecurityException("Native target TLS certificate differs"));
        }catch(Throwable error){failed(error);}}
      });return sdk;
    }
    @Override void sendTimeZone(WebExtension.Port port,GeckoSession sdk,TimeZoneGate gate,String kind,String zone,String token,Consumer<String> ok,Consumer<Throwable> fail){
      super.sendTimeZone(port,sdk,gate,kind,zone,token,raw->{
        try{if("bootstrap-isolation".equals(stage)&&"timezoneApply".equals(kind)){
          // Pure observation of the real native callback. Forward its original
          // bytes immediately; no injected ACK, delay or replacement access.
          JSONObject ack=GeckoTimeZonePolicy.contextReadback(raw,token,AppSessionIdentity.id(sdk));
          ChromiumRouteLease.Handle lease=ipRouteLeases.get(gate);
          if(observedLease==null||lease!=observedLease||lease.closed)throw new IOException("Bootstrap route lease retired before native apply ACK");
          applyLeaseProof=J.obj("actualNativeAck",true,"leaseHeldBeforeNativeAckPublication",true,"controllerPreparedBeforePublication",timeZoneStatus().optBoolean("nativeSettingReadback"),"ack",ack);
        }ok.accept(raw);}catch(Throwable error){fail.accept(error);failed(error);}
      },fail);
    }
  }
  static boolean geoHostVariant(String target){try{return !GEO.equals(target)&&"ipwho.is".equals(new URI(target).getHost());}catch(Exception rejected){return false;}}
  static boolean diagnosticKeys(JSONObject value,String... names){Set<String> actual=new HashSet<>();for(Iterator<String> i=value.keys();i.hasNext();)actual.add(i.next());return actual.equals(new HashSet<>(Arrays.asList(names)));}
  static boolean extensionDiagnosticPayload(JSONObject value,String requestNonce){try{
    if(value.toString().length()>16384||!diagnosticKeys(value,"schema","diagnosticOnly","releaseAcceptance","requestNonce","runtimeManifest","helperPresence","events","omitted","invalid","bootstrapObject","bootstrapCreate","headersObject"))return false;
    if(!(value.opt("schema") instanceof Integer)||value.getInt("schema")!=1||!Boolean.TRUE.equals(value.opt("diagnosticOnly"))||!Boolean.FALSE.equals(value.opt("releaseAcceptance"))||!requestNonce.equals(value.opt("requestNonce")))return false;
    for(String key:new String[]{"omitted","invalid"})if(!(value.opt(key) instanceof Integer)||value.getInt(key)<0||value.getInt(key)>10000)return false;
    for(String key:new String[]{"bootstrapObject","bootstrapCreate","headersObject"})if(!(value.opt(key) instanceof Boolean))return false;
    JSONObject manifest=value.getJSONObject("runtimeManifest");if(!diagnosticKeys(manifest,"available","version","id","scriptCount","scripts")||!(manifest.opt("available") instanceof Boolean)||!(manifest.opt("scriptCount") instanceof Integer)||manifest.getInt("scriptCount")< -1||manifest.getInt("scriptCount")>10000)return false;
    if(!Arrays.asList("2.1.2.104","other","unavailable").contains(manifest.opt("version"))||!Arrays.asList("browser@pocketchat.local","other","unavailable").contains(manifest.opt("id")))return false;
    JSONArray scripts=manifest.getJSONArray("scripts");if(scripts.length()>8)return false;for(int i=0;i<scripts.length();i++)if(!Arrays.asList("ip-timezone-bootstrap.js","request-headers.js","request-identity-background.js","native-timezone-bridge.js","background.js","other").contains(scripts.opt(i)))return false;
    JSONObject helpers=value.getJSONObject("helperPresence");if(!diagnosticKeys(helpers,"bootstrap","headers","identity","timezone"))return false;for(String key:new String[]{"bootstrap","headers","identity","timezone"})if(!Arrays.asList("undefined","object","function","boolean","number","string","symbol","bigint").contains(helpers.opt(key)))return false;
    JSONArray rows=value.getJSONArray("events");if(rows.length()>32)return false;
    for(int i=0;i<rows.length();i++){
      JSONObject row=rows.getJSONObject(i);if(!diagnosticKeys(row,"sequence","stage","urlClass","exactGeo","get","origin","document","requestIdPresent","result","errorName")||!(row.opt("sequence") instanceof Integer)||row.getInt("sequence")!=i+1)return false;
      if(!Arrays.asList("bootstrap-loaded","create-enter","create-rejected","create-ready","lookup-received","lookup-rejected","lookup-start","fetch-start","fetch-response","fetch-rejected","deadline","finish-null","finish-observed","before-request","before-redirect","authorization","native-lookup-received","bootstrap-bound","proxy-event","proxy-authorization","header-event","header-authorization","header-listener").contains(row.opt("stage")))return false;
      if(!Arrays.asList("geo-exact","geo-host-variant","other").contains(row.opt("urlClass"))||!Arrays.asList("own","foreign","absent","invalid","unseen").contains(row.opt("origin"))||!Arrays.asList("own","foreign","absent","invalid","unseen").contains(row.opt("document")))return false;
      if(!Arrays.asList("none","ready","rejected","missing-port","runtime-url","features","registration","exception","shape-or-busy","pending","accepted","absent","invalid","closed","cancelled","observed").contains(row.opt("result"))||!Arrays.asList("none","AbortError","NetworkError","TypeError","SecurityError","TimeoutError","NotAllowedError","InvalidStateError","other").contains(row.opt("errorName")))return false;
      for(String key:new String[]{"exactGeo","get","requestIdPresent"})if(!(row.opt(key) instanceof Boolean))return false;
    }return true;
  }catch(Exception rejected){return false;}}
  void installExtensionDiagnostic(GeckoRuntime expected,WebExtension value){
    if(value==null||!value.isBuiltIn||!"browser@pocketchat.local".equals(value.id))return;diagnosticExtension=value;diagnosticRuntime=expected;
    value.setMessageDelegate(new WebExtension.MessageDelegate(){
      @Override public GeckoResult<Object> onMessage(String app,Object message,WebExtension.MessageSender sender){
        if(!terminal&&"pocketipdiagnostic".equals(app)&&sender!=null&&sender.environmentType==WebExtension.MessageSender.ENV_TYPE_EXTENSION&&sender.session==null&&sender.webExtension==value&&value==diagnosticExtension&&value.isBuiltIn&&"browser@pocketchat.local".equals(value.id)&&remote!=null&&remote.runtime==expected&&diagnosticRuntime==expected&&remote.extension==value&&message instanceof JSONObject&&extensionDiagnosticPayload((JSONObject)message,nonce)){
          extensionDiagnostic=J.parse(message.toString());extensionDiagnosticAccepted=Math.min(10000,extensionDiagnosticAccepted+1);
        }else extensionDiagnosticRejected=Math.min(10000,extensionDiagnosticRejected+1);
        return GeckoResult.fromValue(null);
      }
    },"pocketipdiagnostic");
  }
  void routingCount(int index){routingCounters.accumulateAndGet(index,1,(old,value)->Math.min(10000,old+value));}
  static int selectedRoute(JSONObject value){
    if(value==null)return 4;String type=value.optString("type"),host=value.optString("host");int port=value.optInt("port",-1);
    if("socks".equals(type)&&"127.0.0.1".equals(host)&&port==9)return 0;
    if("socks".equals(type)&&"127.0.0.1".equals(host)&&port==18766)return 1;
    if("http".equals(type)&&"127.0.0.1".equals(host)&&port==18767)return 2;
    if("https".equals(type)&&"127.0.0.1".equals(host)&&port==18768)return 3;
    return 4;
  }
  void event(String kind,GeckoSession sdk,String url){if(terminal)return;if(events.length()>=160){failed(new IOException("Native event bound exceeded"));return;}String path="other";try{URI value=new URI(url);if(Arrays.asList(BrowserFingerprintFixture.A,BrowserFingerprintFixture.B).contains(value.getHost())&&Arrays.asList("/env-policy","/env-frame").contains(value.getPath()))path=value.getPath();}catch(Exception ignored){}
    events.put(J.obj("sequence",events.length()+1,"kind",kind,"path",path,"sessionId",AppSessionIdentity.id(sdk),"navigation",session==null?0:session.navigationEpoch,"stage",stage));}
  String proxy(String route){if("socks".equals(route))return "socks://127.0.0.1:18766";if("http".equals(route))return "http://127.0.0.1:18767";if("https".equals(route))return "https://127.0.0.1:18768";throw new SecurityException("Fixed proxy route only");}
  void within()throws IOException{long now=SystemClock.elapsedRealtime();if(now>deadline||now>wholeDeadline)throw new IOException("IP timezone fixture stage deadline");}
  void waitFor(String label,Ready ready,Step after){if(terminal)return;try{transportDiagnostic(false);within();if(ready.get()){after.run();return;}probe.postDelayed(()->waitFor(label,ready,after),60);}catch(Throwable error){failed(error);}}
  static String diagnosticToken(String value){return value!=null&&value.matches("[A-Za-z0-9_.:-]{0,160}")?value:"";}
  void transportDiagnostic(boolean force){
    long now=SystemClock.elapsedRealtime();if(build==null||!force&&now-lastDiagnosticAt<1000)return;lastDiagnosticAt=now;
    try{
      if(!terminal&&remote!=null&&remote.routePort!=null&&remote.extension==diagnosticExtension&&remote.runtime==diagnosticRuntime)try{remote.routePort.postMessage(J.obj("kind","timezoneIpDiagnosticSnapshot","requestNonce",nonce));}catch(RuntimeException ignored){}
      JSONObject value=J.obj("elapsedRealtime",now,"stage",stage,"terminal",terminal,"sessionPresent",session!=null,"viewPresent",remote!=null);
      JSONObject routing=new JSONObject();String[] counterNames={"bootstrapGeoAllowed","bootstrapGeoDenied","bootstrapOtherAllowed","bootstrapOtherDenied","protectedGeoBlocked","protectedGeoFixedSocks","protectedGeoFixedHttp","protectedGeoFixedHttps","protectedGeoOther","ordinaryGeoBlocked","ordinaryGeoOther","bootstrapGeoVariantAllowed","bootstrapGeoVariantDenied","protectedGeoVariant","ordinaryGeoVariant"};boolean capped=false;for(int i=0;i<counterNames.length;i++){int count=routingCounters.get(i);routing.put(counterNames[i],count);capped|=count==10000;}routing.put("capped",capped);value.put("routingCounters",routing);
      if(session!=null){JSONObject currentPolicy=session.timeZone.status(),policy=new JSONObject();for(String name:new String[]{"schema","desiredMode","desiredRevision","state","effectiveMode","rfpPriority","ipMatched","nativeSettingReadback","issue"})policy.put(name,currentPolicy.opt(name));
        value.put("networkReady",session.networkReady).put("connecting",session.connecting).put("navigating",session.navigating).put("navigationFailed",session.navigationFailed).put("navigationEpoch",session.navigationEpoch).put("connectionEpoch",session.connectionEpoch).put("ownerDeleted",session.deleted).put("timeZonePolicy",policy);
        NetworkPoolIdentity.NetworkSnapshot network=session.browserDefaultNetwork.snapshot();if(network!=null)value.put("defaultNetwork",J.obj("known",network.known,"internet",network.internet,"vpn",network.vpn,"revision",network.revision,"identityPresent",!network.identity.isEmpty()));
      }
      if(remote!=null){
        GeckoSession current=remote.current;GeckoWebView.TimeZoneGate gate=remote.timeZoneGates.get(current);GeckoWebView.IpLookup lookup=remote.ipLookup;GeckoIpRouteWatch.Snapshot links=remote.ipRoutes.snapshot();ChromiumRouteLease.Snapshot leases=ChromiumRouteLease.snapshot();
        value.put("view",J.obj("ready",remote.ready,"failed",remote.failed,"destroyed",remote.destroyed,"privacyReady",remote.privacyReady,"addonDisabled",remote.addonDisabled,"requestHeadersInstalled",remote.requestHeadersInstalled,"routePortPresent",remote.routePort!=null,"nativeProtectionConfirmed",remote.nativeProtection.confirmed(),"protectionLevel",remote.protectionLevel,"currentSessionPresent",current!=null,"currentSessionOpen",current!=null&&current.isOpen(),"currentSessionId",current==null?"":diagnosticToken(AppSessionIdentity.id(current)),"currentPagePortPresent",remote.ports.get(current)!=null,"hasVisibleDocument",remote.hasVisibleDocument(),"ipRouteNeedsReload",remote.ipRouteNeedsReload,"routeStamp",diagnosticToken(remote.ipRouteStamp()),"guardBlocked",session==null||session.guard==null||session.guard.blocked,"generalRouteReady",remote.generalRouteReady()));
        value.put("linkWatch",J.obj("networkPresent",!links.network.isEmpty(),"linksPresent",!links.links.isEmpty(),"serial",links.serial)).put("routeLeases",J.obj("surfaces",leases.surfaces,"downloads",leases.downloads,"changes",leases.changes,"revision",leases.revision));
        value.put("gate",gate==null?J.obj("present",false):J.obj("present",true,"epoch",diagnosticToken(gate.epoch),"documentSerial",gate.documentSerial,"preparing",gate.preparing,"ready",gate.ready,"revalidating",gate.revalidating,"waiting",gate.waiting.size(),"proofWaiting",gate.proofWaiting.size(),"networkWaiting",gate.networkWaiting.size(),"routeLeasePresent",remote.ipRouteLeases.containsKey(gate)));
        value.put("lookup",lookup==null?J.obj("present",false):J.obj("present",true,"sent",lookup.sent,"id",lookup.id,"currentSession",lookup.session==current,"currentGate",lookup.gate==gate,"currentPort",lookup.port==remote.routePort,"currentRuntime",lookup.runtime==remote.runtime,"requestToken",diagnosticToken(lookup.token),"routeStamp",diagnosticToken(lookup.stamp),"remainingMs",Math.max(-120000,Math.min(8000,lookup.expires-now)),"leasePresent",lookup.lease!=null,"leaseClosed",lookup.lease!=null&&lookup.lease.closed,"documentSerial",lookup.document,"connectionEpoch",lookup.connection,"desiredRevision",lookup.revision));
        Field field=GeckoTimeZoneController.class.getDeclaredField("operations");field.setAccessible(true);Object operation=((Map<?,?>)field.get(session.timeZone)).get(current);JSONObject op=J.obj("present",operation!=null);
        if(operation!=null)for(String name:new String[]{"started","retired","finished","ready","verified","unsupported","rfpManaged"}){Field member=operation.getClass().getDeclaredField(name);member.setAccessible(true);op.put(name,member.getBoolean(operation));}
        value.put("operation",op);
      }
      // Retain state transitions, rather than losing the 8s pending lookup to
      // eighty later identical timeout samples. Clock-only changes replace the
      // latest sample. All observations still consume the original deadline.
      JSONObject signature=J.parse(value.toString());signature.remove("elapsedRealtime");if(signature.optJSONObject("lookup")!=null)signature.getJSONObject("lookup").remove("remainingMs");String key=signature.toString();
      if(key.equals(lastDiagnosticSignature)&&diagnosticHistory.length()>0)diagnosticHistory.remove(diagnosticHistory.length()-1);
      while(diagnosticHistory.length()>=16)diagnosticHistory.remove(0);diagnosticHistory.put(value);lastDiagnosticSignature=key;
      JSONObject report=J.obj("schema",1,"diagnosticOnly",true,"releaseAcceptance",false,"sourceCommit",build.getString("sourceCommit"),"sourceTree",build.getString("sourceTree"),"runNonce",nonce,"integrationApkSha256",build.getString("apkSha256"),"sdkRunId",build.getJSONObject("sdkBuildIdentity").getString("runId"),"sdkRunAttempt",build.getJSONObject("sdkBuildIdentity").getString("runAttempt"),"snapshots",diagnosticHistory,"extensionDiagnostic",J.obj("registered",diagnosticExtension!=null,"accepted",extensionDiagnosticAccepted,"rejected",extensionDiagnosticRejected,"latest",extensionDiagnostic),"actualPublicIpGeolocationVerified",false,"scope","Read-only memory fields of the actual production native gate/lookup; no readiness is forced and no raw URL, address, credential, page body or TLS material is collected.");
      android.util.AtomicFile file=new android.util.AtomicFile(new File(Profiles.global(this).getFilesDir(),"gecko-ip-timezone-transport-debug.json"));FileOutputStream out=null;try{byte[] raw=(report.toString()+"\n").getBytes(StandardCharsets.UTF_8);if(raw.length>65536)throw new IOException("Bounded native diagnostic overflow");out=file.startWrite();out.write(raw);file.finishWrite(out);}catch(Exception error){if(out!=null)file.failWrite(out);}
    }catch(Exception unavailable){/* Diagnostic failure never modifies the original workload outcome. */}
  }
  boolean ready(){return session!=null&&remote!=null&&remote.ready&&session.networkReady&&!session.connecting&&!session.navigating&&remote.hasVisibleDocument()&&remote.ports.get(remote.current)!=null&&remote.timeZoneStatus().optBoolean("nativeSettingReadback")&&roots;}
  void next(String name,Step after){try{stage=name;deadline=SystemClock.elapsedRealtime()+60000;publish();control("stage",J.obj("case",name),ignored->run(after));}catch(Throwable error){failed(error);}}
  void run(Step step){try{step.run();}catch(Throwable error){failed(error);}}
  void check(String id,boolean ok)throws Exception{checks.put(J.obj("id",id,"pass",ok));if(!ok)throw new AssertionError(id);}
  void control(String action,JSONObject extra,Consumer<JSONObject> done){io.execute(()->{try{
    JSONObject body=J.obj("sourceCommit",build.getString("sourceCommit"),"runNonce",nonce,"action",action);for(Iterator<String> keys=extra.keys();keys.hasNext();){String key=keys.next();body.put(key,extra.get(key));}
    HttpURLConnection channel=(HttpURLConnection)new URL("http://127.0.0.1:18769/__ip-control").openConnection();channel.setConnectTimeout(3000);channel.setReadTimeout(3000);channel.setInstanceFollowRedirects(false);channel.setRequestMethod("POST");channel.setDoOutput(true);byte[] bytes=body.toString().getBytes(StandardCharsets.UTF_8);channel.setFixedLengthStreamingMode(bytes.length);channel.setRequestProperty("Content-Type","application/json");
    JSONObject value;try{try(OutputStream out=channel.getOutputStream()){out.write(bytes);}if(channel.getResponseCode()!=200)throw new IOException("Controlled host command rejected");try(InputStream in=channel.getInputStream()){value=GeckoTimeZonePolicy.object(J.text(in,262144).getBytes(StandardCharsets.UTF_8),262144);}}finally{channel.disconnect();}
    probe.post(()->{if(!terminal)done.accept(value);});
  }catch(Throwable error){probe.post(()->failed(error));}});}
  void snapshot(Consumer<JSONObject> done){control("snapshot",new JSONObject(),done);}
  int geoCount(JSONObject value){int count=0;JSONArray rows=value.optJSONArray("events");if(rows!=null)for(int i=0;i<rows.length();i++)if("geo".equals(rows.optJSONObject(i).optString("kind")))count++;return count;}
  void page(Consumer<JSONObject> done){final GeckoSession sdk=remote.current;final long nav=session.navigationEpoch;
    remote.evaluateJavascript("document.documentElement.getAttribute('data-gecko-environment-policy')",raw->{if(terminal)return;try{within();if(sdk!=remote.current||nav!=session.navigationEpoch){done.accept(new JSONObject());return;}if(raw==null||raw.length()>300000)throw new IOException("Bounded controlled observation absent");JSONObject value=GeckoEnvironmentPolicyIntegrationActivity.decoded(raw);lastPage=value;done.accept(value);}catch(Throwable error){failed(error);}});}
  @SuppressWarnings("unchecked") GeckoTimeZoneStore.Ticket ticket()throws Exception{Field field=GeckoTimeZoneController.class.getDeclaredField("operations");field.setAccessible(true);Object operation=((Map<Object,Object>)field.get(session.timeZone)).get(remote.current);if(operation==null)throw new IOException("Actual controller operation absent");Field selected=operation.getClass().getDeclaredField("ticket");selected.setAccessible(true);return (GeckoTimeZoneStore.Ticket)selected.get(operation);}
  void nativeProof(Consumer<JSONObject> done)throws Exception{final GeckoSession sdk=remote.current;final long nav=session.navigationEpoch;final GeckoTimeZoneStore.Ticket actual=ticket();if(actual==null)throw new IOException("Actual native ticket absent");String token=UUID.randomUUID().toString().replace("-","")+UUID.randomUUID().toString().replace("-","");
    remote.sendTimeZone(remote.routePort,sdk,remote.timeZoneGates.get(sdk),"timezoneRead","",token,raw->{try{JSONObject fresh=GeckoTimeZonePolicy.contextReadback(raw,token,AppSessionIdentity.id(sdk));session.environmentIo.execute(()->{try{
      JSONObject receipt=GeckoTimeZoneStore.lastReceipt(session.context,actual);GeckoTimeZoneStore.State selected=GeckoTimeZoneStore.load(session.context);
      probe.post(()->{try{if(sdk!=remote.current||nav!=session.navigationEpoch||!actual.binding.contextId.equals(fresh.getString("contextId")))throw new IOException("Exact native document binding changed");done.accept(J.obj("sessionId",AppSessionIdentity.id(sdk),"sessionEpoch",actual.binding.sessionEpoch,"contextId",fresh.getString("contextId"),"freshReadback",fresh,"receipt",receipt,"desiredSpec",selected.spec.json(),"desiredRevision",selected.revision,"identity",selected.identity.json(),"status",remote.timeZoneStatus(),"routeStamp",remote.ipRouteStamp(),"nativeRfpConfirmed",remote.nativeProtection.confirmed()&&remote.fingerprintingProtected,"privacyLevel",session.privacy.level()));}catch(Throwable error){failed(error);}});
    }catch(Throwable error){probe.post(()->failed(error));}});}catch(Throwable error){failed(error);}},this::failed);
  }
  void capture(String name,String zone,boolean workers,Consumer<JSONObject> done){waitFor(name,this::ready,()->page(value->{try{
    JSONObject early=value.optJSONObject("page");JSONArray frames=value.optJSONArray("frames");if(early==null||!early.optBoolean("markerComplete")||frames==null||frames.length()!=2){probe.postDelayed(()->capture(name,zone,workers,done),60);return;}
    if(!nonce.equals(early.opt("runNonce"))||!build.getString("sourceCommit").equals(early.opt("sourceCommit")))throw new SecurityException("First-inline invocation differs");
    for(int i=0;i<frames.length();i++)if(!frames.getJSONObject(i).optBoolean("markerComplete")){probe.postDelayed(()->capture(name,zone,workers,done),60);return;}
    JSONObject measured=value.optJSONObject("workers");if(workers&&(measured==null||!measured.optBoolean("started"))){remote.evaluateJavascript("document.dispatchEvent(new CustomEvent('pocketchat-gecko-env-run-workers',{detail:"+JSONObject.quote(nonce)+"}))",ignored->{});probe.postDelayed(()->capture(name,zone,true,done),60);return;}
    if(workers&&!measured.optBoolean("complete")){if(measured.has("error"))throw new IOException("Actual native Worker observation failed");probe.postDelayed(()->capture(name,zone,true,done),60);return;}
    nativeProof(proof->{try{value.put("native",proof).put("security",securities.get(remote.current)).put("case",name);
      check(name+".first-inline-native-clock",early.getBoolean("firstInline")&&early.getBoolean("secure")&&early.getBoolean("networkAllowed")&&GeckoEnvironmentPolicyIntegrationActivity.clockMatches(value,zone));
      check(name+".exact-native-context",proof.getJSONObject("receipt").getBoolean("nativeSettingReadback")&&proof.getJSONObject("status").getBoolean("currentSessionPrepared"));
      cases.put(name,value);lastSample=value;publish();done.accept(value);
    }catch(Throwable error){failed(error);}});
  }catch(Throwable error){failed(error);}}));}

  void applyZone(int selection,String zone,Step after)throws Exception{
    String before=lastSample.optJSONObject("page")==null?"":lastSample.getJSONObject("page").getString("documentId");GeckoTimeZoneUi.show(this);
    waitFor("actual zone editor",()->GeckoEnvironmentPolicyIntegrationActivity.window("应用并重新加载")!=null,()->{
      View editor=GeckoEnvironmentPolicyIntegrationActivity.window("应用并重新加载");Spinner mode=GeckoEnvironmentPolicyIntegrationActivity.first(editor,Spinner.class);EditText input=GeckoEnvironmentPolicyIntegrationActivity.first(editor,EditText.class);
      if(mode==null||mode.getCount()!=4||input==null)throw new IOException("Actual four-mode UI absent");mode.setSelection(selection);input.setText(zone);GeckoEnvironmentPolicyIntegrationActivity.button(editor,"应用并重新加载").performClick();
      confirmZone(editor,before,after);
    });
  }
  void confirmZone(View editor,String before,Step after){waitFor("actual zone confirmation",()->{
    View confirmation=GeckoEnvironmentPolicyIntegrationActivity.window("已保存输入，应用");if(confirmation!=null){GeckoEnvironmentPolicyIntegrationActivity.button(confirmation,"已保存输入，应用").performClick();return false;}
    if(!ready())return false;
    return true;
  },()->page(value->{try{if(value.optJSONObject("page")==null||before.equals(value.getJSONObject("page").optString("documentId"))){probe.postDelayed(()->confirmZone(editor,before,after),60);return;}GeckoEnvironmentPolicyIntegrationActivity.closeWindow(editor,"关闭此环境的独立时区");after.run();}catch(Throwable error){failed(error);}}));}
  void routeUi(String route,Step after)throws Exception{externalNetworkSettings();waitFor("actual proxy editor",()->GeckoEnvironmentPolicyIntegrationActivity.window("保存并连接")!=null,()->{
    View editor=GeckoEnvironmentPolicyIntegrationActivity.window("保存并连接");EditText input=GeckoEnvironmentPolicyIntegrationActivity.first(editor,EditText.class);if(input==null)throw new IOException("Actual proxy editor absent");input.setText(proxy(route));GeckoEnvironmentPolicyIntegrationActivity.button(editor,"保存并连接").performClick();waitFor("actual route connection",()->session.networkReady&&!session.connecting&&session.prefs.getString("proxy","").equals(proxy(route)),after);
  });}
  void routeSwitch(){next("route-switch-http",()->{
    String old=lastSample.getJSONObject("page").getString("documentId"),oldRoute=lastSample.getJSONObject("native").getString("routeStamp");
    routeUi("http",()->waitFor("route retires IP confirmation",()->!remote.timeZoneStatus().optBoolean("nativeSettingReadback"),()->page(before->{try{
      check("route-switch.visible-document-preserved",old.equals(before.getJSONObject("page").getString("documentId")));
      applyZone(0,"",()->capture("route-switch-http","Asia/Kathmandu",false,value->{try{
        check("route-switch.new-route-proof",!oldRoute.equals(value.getJSONObject("native").getString("routeStamp")));
        session.environmentIo.execute(()->{boolean rejected=false;try{rejected=GeckoTimeZoneStore.lastReceipt(session.context,originalTicket).length()==0;}catch(Exception oldOwner){rejected=true;}boolean result=rejected;probe.post(()->{try{check("route-switch.old-receipt-rejected",result);value.put("oldTicketReadAttempted",true).put("oldTicketRejected",result);httpsRoute();}catch(Throwable error){failed(error);}});});
      }catch(Throwable error){failed(error);}}));
    }catch(Throwable error){failed(error);}})));
  });}
  void httpsRoute(){next("https-proxy",()->routeUi("https",()->applyZone(0,"",()->capture("https-proxy","UTC",false,ignored->cancelLate()))));}

  // Explicit fixture calls to actual production lifecycle methods. No fake
  // NativeAccess, direct callback, gate mutation or user-gesture claim.
  void actualReconfirm(){session.timeZone.ipRouteChanged();remote.retireTimeZone(remote.current);remote.prepareTimeZone(remote.current,ignored->{});}
  void held(String name,Consumer<JSONObject> pending){next(name,()->control("behavior",J.obj("route","https","behavior","hold"),ignored->{try{
    actualReconfirm();waitHostHeld(pending);
  }catch(Throwable error){failed(error);}}));}
  void waitHostHeld(Consumer<JSONObject> done){snapshot(value->{try{within();JSONArray rows=value.getJSONArray("events");for(int i=rows.length()-1;i>=0;i--){JSONObject row=rows.getJSONObject(i);if(stage.equals(row.optString("case"))&&"geo".equals(row.optString("kind"))&&"hold".equals(row.optString("behavior"))&&!row.optBoolean("responseWritten")){done.accept(value);return;}}probe.postDelayed(()->waitHostHeld(done),50);}catch(Throwable error){failed(error);}});}
  void cancelLate(){held("cancel-late",pending->{try{
    String doc=lastSample.getJSONObject("page").getString("documentId");remote.retireTimeZone(remote.current);
    check("cancel.actual-owner-retired",remote.ipLookup==null&&!remote.timeZoneStatus().optBoolean("nativeSettingReadback"));
    control("release",J.obj("route","https"),ignored->waitReleased("cancel-late",()->{try{
      check("cancel.late-not-admitted",!remote.timeZoneStatus().optBoolean("nativeSettingReadback")&&!remote.timeZoneStatus().optBoolean("ipMatched"));
      cases.put("cancel-late",J.obj("explicitProductionMethodBoundary",true,"actualUserGesture",false,"oldDocumentId",doc,"pending",pending,"after",remote.timeZoneStatus(),"lateResultAdmitted",false));
      control("behavior",J.obj("route","https","behavior","normal"),v->{actualReconfirm();waitFor("recovered exact owner",this::ready,this::manualSystem);});
    }catch(Throwable error){failed(error);}}));
  }catch(Throwable error){failed(error);}});}
  void manualSystem(){next("manual-system",()->snapshot(before->{try{int count=geoCount(before);applyZone(1,"",()->capture("manual-system",java.util.TimeZone.getDefault().getID(),false,value->snapshot(after->{try{check("manual-system.no-geo",geoCount(after)==count);value.put("geoCountBefore",count).put("geoCountAfter",geoCount(after));manualIana();}catch(Throwable error){failed(error);}})));}catch(Throwable error){failed(error);}}));}
  void manualIana(){next("manual-iana",()->snapshot(before->{try{int count=geoCount(before);applyZone(3,"Asia/Kathmandu",()->capture("manual-iana","Asia/Kathmandu",false,value->snapshot(after->{try{check("manual-iana.no-geo",geoCount(after)==count);value.put("geoCountBefore",count).put("geoCountAfter",geoCount(after));prepareRfp();}catch(Throwable error){failed(error);}})));}catch(Throwable error){failed(error);}}));}
  void template(boolean rfp,Step after)throws Exception{FingerprintTemplateUi.show(this);waitFor("actual fingerprint template",()->GeckoEnvironmentPolicyIntegrationActivity.window("保存模板")!=null,()->{
    View editor=GeckoEnvironmentPolicyIntegrationActivity.window("保存模板");Spinner selection=GeckoEnvironmentPolicyIntegrationActivity.first(editor,Spinner.class);if(selection==null)throw new IOException("Actual template spinner absent");selection.setSelection(rfp?4:0);GeckoEnvironmentPolicyIntegrationActivity.button(editor,"保存模板").performClick();
    waitFor("actual native template",()->ready()&&session.privacy.level()==(rfp?2:1)&&remote.nativeProtection.confirmed()&&!session.identityApplicationPending&&!DeferredBrowserSettings.pending(session),()->{GeckoEnvironmentPolicyIntegrationActivity.closeWindow(editor,"关闭环境模板");after.run();});
  });}
  void prepareRfp(){next("https-proxy",()->applyZone(0,"",()->next("rfp-priority",()->snapshot(before->{try{int count=geoCount(before);template(true,()->capture("rfp-priority","UTC",false,value->snapshot(after->{try{
    JSONObject status=value.getJSONObject("native").getJSONObject("status");check("rfp.auto-priority-browses",status.getBoolean("rfpPriority")&&!status.getBoolean("ipMatched")&&"rfp-priority".equals(status.getString("effectiveMode"))&&value.getJSONObject("native").getBoolean("nativeRfpConfirmed")&&geoCount(after)==count);
    value.put("geoCountBefore",count).put("geoCountAfter",geoCount(after));rfpDenied();
  }catch(Throwable error){failed(error);}})));}catch(Throwable error){failed(error);}}))));}
  void rfpDenied(){next("manual-rfp-denied",()->{long revision=session.timeZone.cached.revision;GeckoTimeZoneUi.show(this);waitFor("RFP manual editor",()->GeckoEnvironmentPolicyIntegrationActivity.window("应用并重新加载")!=null,()->{
    View editor=GeckoEnvironmentPolicyIntegrationActivity.window("应用并重新加载");GeckoEnvironmentPolicyIntegrationActivity.first(editor,Spinner.class).setSelection(3);GeckoEnvironmentPolicyIntegrationActivity.first(editor,EditText.class).setText("America/New_York");GeckoEnvironmentPolicyIntegrationActivity.button(editor,"应用并重新加载").performClick();
    waitFor("real RFP conflict",()->GeckoEnvironmentPolicyIntegrationActivity.button(editor,"应用并重新加载").isEnabled()&&GeckoEnvironmentPolicyIntegrationActivity.containsText(editor,"强化模板优先使用自己的时区策略"),()->{
      check("rfp.manual-conflict-preserves",session.timeZone.cached.revision==revision&&session.timeZone.cached.spec.followsIp()&&session.privacy.level()==2&&remote.nativeProtection.confirmed());
      cases.put("manual-rfp-denied",J.obj("actualUiAttempt",true,"revisionBefore",revision,"revisionAfter",session.timeZone.cached.revision,"manualSaveRejected",true,"status",remote.timeZoneStatus(),"privacyLevel",session.privacy.level()));GeckoEnvironmentPolicyIntegrationActivity.closeWindow(editor,"关闭此环境的独立时区");
      template(false,()->capture("bootstrap-preparation","UTC",true,value->{try{lastSample=value;cases.remove("bootstrap-preparation");bootstrapIsolation();}catch(Throwable error){failed(error);}}));
    });
  });});}
  void waitReleased(String name,Step after){snapshot(value->{try{within();JSONArray rows=value.getJSONArray("events");for(int i=rows.length()-1;i>=0;i--){JSONObject row=rows.getJSONObject(i);if(name.equals(row.optString("case"))&&"geo".equals(row.optString("kind"))&&row.optBoolean("responseAttempted")){after.run();return;}}probe.postDelayed(()->waitReleased(name,after),50);}catch(Throwable error){failed(error);}});}
  void bootstrapIsolation(){held("bootstrap-isolation",pending->{try{
    isolationClaim=remote.ipLookup;if(isolationClaim==null||!remote.ipLookupCurrent(isolationClaim)||isolationClaim.lease==null||isolationClaim.lease.closed)throw new IOException("Actual live private bootstrap capability absent");observedLease=isolationClaim.lease;
    remote.evaluateJavascript("document.dispatchEvent(new CustomEvent('pocketchat-ip-bootstrap-denial',{detail:"+JSONObject.quote(nonce)+"}))",ignored->{});
    readIsolation(pending);
  }catch(Throwable error){failed(error);}});}
  void readIsolation(JSONObject pending){remote.evaluateJavascript("document.documentElement.getAttribute('data-gecko-ip-timezone-isolation')",raw->{try{
    within();JSONObject value=GeckoEnvironmentPolicyIntegrationActivity.decoded(raw);if(!value.optBoolean("complete")){probe.postDelayed(()->readIsolation(pending),60);return;}
    if(!nonce.equals(value.opt("runNonce"))||!build.getString("sourceCommit").equals(value.opt("sourceCommit")))throw new SecurityException("Actual isolation observer differs");JSONObject roles=value.getJSONObject("roles");
    if(remote.ipLookup!=isolationClaim||!remote.ipLookupCurrent(isolationClaim)||observedLease.closed)throw new IOException("Private bootstrap capability was no longer live during negative attempts");
    for(String role:new String[]{"page","dedicated","shared","service"}){JSONObject row=roles.getJSONObject(role);check("bootstrap."+role+"-cannot-borrow",row.getBoolean("available")&&row.getBoolean("created")&&row.getBoolean("executed")&&!row.getBoolean("networkAllowed"));}
    snapshot(after->{try{check("bootstrap.exact-single-private-request",geoCount(after)==geoCount(pending));value.put("pending",pending).put("afterAttempts",after).put("explicitProductionMethodBoundary",true).put("actualUserGesture",false);cases.put("bootstrap-isolation",value);
      control("release",J.obj("route","https"),ignored->control("behavior",J.obj("route","https","behavior","normal"),v->waitFor("actual bootstrap confirmation",this::ready,()->nativeProof(proof->{try{
        check("bootstrap.lease-through-native-store-ack",applyLeaseProof.optBoolean("actualNativeAck")&&applyLeaseProof.optBoolean("leaseHeldBeforeNativeAckPublication")&&!applyLeaseProof.optBoolean("controllerPreparedBeforePublication",true)&&observedLease.closed&&proof.getJSONObject("receipt").getBoolean("nativeSettingReadback"));
        applyLeaseProof.put("leaseReleasedAfterNativeAndStoreAck",observedLease.closed);value.put("nativeApplyLease",applyLeaseProof).put("nativeAfter",proof).put("livePrivateCapabilityDuringAttempts",true);
        deniedGeo("redirect-rejected","redirect",this::invalidGeo);
      }catch(Throwable error){failed(error);}}))));
    }catch(Throwable error){failed(error);}});
  }catch(Throwable error){failed(error);}});}
  void deniedGeo(String name,String behavior,Step after){next(name,()->control("behavior",J.obj("route","https","behavior",behavior),ignored->{try{
    final String previous=lastPage.getJSONObject("page").getString("documentId");actualReconfirm();
    // The real address UI queues a new controlled document behind the failing
    // current native gate. Neither redirect nor invalid geo may open it.
    geckoAddress.address.performClick();waitFor("actual negative target address",()->GeckoEnvironmentPolicyIntegrationActivity.window("打开")!=null,()->{
      View editor=GeckoEnvironmentPolicyIntegrationActivity.window("打开");GeckoEnvironmentPolicyIntegrationActivity.first(editor,EditText.class).setText(ROOT+"gecko-restored");GeckoEnvironmentPolicyIntegrationActivity.button(editor,"打开").performClick();
      waitFor("real geo failure remains closed",()->"failed".equals(remote.timeZoneStatus().optString("state"))&&!remote.timeZoneStatus().optBoolean("nativeSettingReadback"),()->page(value->{try{
        check(name+".no-new-page",previous.equals(value.getJSONObject("page").getString("documentId"))&&!remote.timeZoneStatus().optBoolean("ipMatched"));
        snapshot(host->{try{JSONObject proof=J.obj("oldDocumentId",previous,"remainingDocumentId",value.getJSONObject("page").getString("documentId"),"status",remote.timeZoneStatus(),"host",host,"actualAddressUiAttempt",true,"fallbackApplied",false);cases.put(name,proof);after.run();}catch(Throwable error){failed(error);}});
      }catch(Throwable error){failed(error);}}));
    });
  }catch(Throwable error){failed(error);}}));}
  void invalidGeo(){next("invalid-geo-rejected",()->control("behavior",J.obj("route","https","behavior","invalid"),ignored->{try{
    final String oldDocument=lastPage.getJSONObject("page").getString("documentId");final GeckoSession previous=remote.current;
    GeckoTimeZoneUi.show(this);waitFor("actual IP retry editor",()->GeckoEnvironmentPolicyIntegrationActivity.window("应用并重新加载")!=null,()->{
      View editor=GeckoEnvironmentPolicyIntegrationActivity.window("应用并重新加载");GeckoEnvironmentPolicyIntegrationActivity.first(editor,Spinner.class).setSelection(0);GeckoEnvironmentPolicyIntegrationActivity.first(editor,EditText.class).setText("");GeckoEnvironmentPolicyIntegrationActivity.button(editor,"应用并重新加载").performClick();
      waitFor("actual IP retry consent",()->{
        View confirmation=GeckoEnvironmentPolicyIntegrationActivity.window("已保存输入，应用");if(confirmation!=null){GeckoEnvironmentPolicyIntegrationActivity.button(confirmation,"已保存输入，应用").performClick();return false;}
        return previous!=remote.current&&"failed".equals(remote.timeZoneStatus().optString("state"));
      },()->{
        GeckoEnvironmentPolicyIntegrationActivity.closeWindow(editor,"关闭此环境的独立时区");
        waitFor("blank failure stops real progress",()->!remote.hasVisibleDocument()&&!session.navigating&&session.navigationFailed&&!session.pageError.isEmpty()&&loading!=null&&loading.cover.isShown()&&loading.wheel.getVisibility()!=View.VISIBLE&&loading.retry.isShown()&&loading.hint.isShown()&&loading.hint.getText().toString().contains("未匹配"),()->snapshot(host->{try{
          check("invalid-geo-rejected.blank-error-stops-spinner",!remote.timeZoneStatus().optBoolean("nativeSettingReadback")&&!remote.timeZoneStatus().optBoolean("ipMatched"));
          JSONObject proof=J.obj("oldDocumentId",oldDocument,"newNativeSession",previous!=remote.current,"oldSessionId",AppSessionIdentity.id(previous),"failedSessionId",AppSessionIdentity.id(remote.current),"oldNativeRequestToken",applyLeaseProof.getJSONObject("ack").getString("requestToken"),"actualSpontaneousLateCallbackObserved",false,"blankBeforeRecovery",!remote.hasVisibleDocument(),"navigationStopped",!session.navigating,"navigationFailed",session.navigationFailed,"errorDisplayed",loading.cover.isShown()&&loading.hint.isShown(),"spinnerStopped",loading.wheel.getVisibility()!=View.VISIBLE,"status",remote.timeZoneStatus(),"host",host,"actualTimeZoneRetryUi",true,"fallbackApplied",false,"queuedTargetRetained",!remote.queued.isEmpty());
          int geoBefore=geoCount(host);applyZone(1,"",()->capture("invalid-geo-recovery",java.util.TimeZone.getDefault().getID(),false,recovered->snapshot(after->{try{
            check("invalid-geo-rejected.explicit-manual-recovers",session.timeZone.cached.spec.followsSystem()&&!session.timeZone.status().optBoolean("ipMatched")&&geoCount(after)==geoBefore);
            cases.remove("invalid-geo-recovery");proof.put("manualRecovery",recovered).put("actualManualUiRecovery",true).put("geoCountBeforeRecovery",geoBefore).put("geoCountAfterRecovery",geoCount(after));cases.put("invalid-geo-rejected",proof);complete();
          }catch(Throwable error){failed(error);}})));
        }catch(Throwable error){failed(error);}}));
      });
    });
  }catch(Throwable error){failed(error);}}));}
  void complete()throws Exception{check("scope.worker-and-sw-unclaimed",!session.timeZone.status().optBoolean("workerCoverageVerified",true)&&!session.timeZone.status().optBoolean("serviceWorkerCoverageVerified",true));check("scope.generic-not-gpt",!session.chatAutomationAllowed()&&session.driverTarget()==null);terminal=true;stage="complete";publish();}
  void failed(Throwable error){if(terminal)return;terminal=true;failedStage=stage;stage="failed";failure=error.getClass().getSimpleName();String message=error.getMessage();
    if(error instanceof AssertionError&&message!=null&&message.matches("[A-Za-z0-9._-]{1,160}"))failure+=":"+message;
    else for(StackTraceElement frame:error.getStackTrace())if(frame.getClassName().startsWith("local.pocketchat.GeckoIpTimeZoneIntegrationActivity")){failure+="@"+frame.getMethodName()+":"+frame.getLineNumber();break;}
    transportDiagnostic(true);try{publish();}catch(Exception ignored){}}
  void publish()throws Exception{if(build==null)return;JSONObject value=J.obj("schema",1,"fixtureType","gecko-production-ip-timezone-v1","engine","gecko","status",terminal?(failure.isEmpty()?"passed":"failed"):"running","stage",stage,"failedAtStage",failedStage,"failure",failure,"sourceCommit",build.getString("sourceCommit"),"sourceTree",build.getString("sourceTree"),"runNonce",nonce,"buildIdentity",build,"setup",setup==null?new JSONObject():setup,"checks",checks,"cases",cases,"nativeEvents",events,"lastPage",lastPage,"currentTimeZonePolicy",session==null?new JSONObject():session.timeZone.status(),"actualAndroidExecution",true,"actualGeckoExecution",remote!=null&&remote.current!=null,"syntheticGeoService",true,"actualPublicIpGeolocationVerified",false,"workerCoverageVerified",false,"serviceWorkerCoverageVerified",false,"fingerprintProtectionVerified",false,"scope","Canonical MainActivity profile6, actual production UI/native timezone/private bootstrap plus controlled HTTPS proxy responses. Geo JSON is synthetic, not public-location proof; raw Worker clocks and capability-denial observations do not establish full Worker timezone isolation.");
    android.util.AtomicFile file=new android.util.AtomicFile(new File(Profiles.global(this).getFilesDir(),"gecko-ip-timezone-results.json"));FileOutputStream out=null;try{out=file.startWrite();byte[] bytes=(value.toString()+"\n").getBytes(StandardCharsets.UTF_8);if(bytes.length>4*1024*1024)throw new IOException("Bounded IP fixture report overflow");out.write(bytes);file.finishWrite(out);}catch(Exception error){if(out!=null)file.failWrite(out);throw error;}
  }
  @Override protected void onDestroy(){probe.removeCallbacksAndMessages(null);io.shutdownNow();super.onDestroy();}
}
