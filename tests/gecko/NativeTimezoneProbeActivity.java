package local.pocketchat;

import android.app.Activity;
import android.os.*;
import android.util.AtomicFile;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.json.*;
import org.mozilla.geckoview.*;

/** Test-only native BrowsingContext setting and unmodified page/worker observations. */
public final class NativeTimezoneProbeActivity extends Activity {
  static final String EXTENSION="timezone-probe@pocketchat.local",HOST="pockettimezoneprobe";
  static final List<String> ZONES=Arrays.asList("UTC","America/New_York","Asia/Kathmandu");
  final Handler handler=new Handler(Looper.getMainLooper());
  final Map<String,JSONObject> observations=new LinkedHashMap<>();
  final JSONArray events=new JSONArray();
  /** Progress stop has no URL; it can describe a cancelled preceding document.
   * A stop alone never establishes ownership of the measurement document. */
  static final class NavigationState {
    final String bootstrapUrl,probeUrl;
    String activePath="initial",locationPath="initial";int generation,failedStops;
    boolean bootstrapStart,bootstrapDocument,bootstrapStop,probeRequested,probeStart,probeDocument,probeStop,targetError;
    NavigationState(String bootstrapUrl,String probeUrl){this.bootstrapUrl=bootstrapUrl;this.probeUrl=probeUrl;}
    String path(String url){return bootstrapUrl.equals(url)?"bootstrap":probeUrl.equals(url)?"probe":"about:blank".equals(url)?"initial":"other";}
    void start(String path){generation++;activePath=path;if("bootstrap".equals(path))bootstrapStart=true;
      if("probe".equals(path)&&probeRequested)probeStart=true;}
    void location(String path){locationPath=path;}
    void document(String path){if("bootstrap".equals(path))bootstrapDocument=true;
      if("probe".equals(path)&&probeRequested)probeDocument=true;}
    void stop(boolean success){if(!success){failedStops++;return;}
      if("bootstrap".equals(activePath)&&!probeRequested)bootstrapStop=true;
      if("probe".equals(activePath)&&probeRequested)probeStop=true;}
    boolean bootstrapReady(){return bootstrapStart&&bootstrapDocument&&bootstrapStop&&"bootstrap".equals(activePath)&&"bootstrap".equals(locationPath);}
    void requestProbe(){if(probeRequested)throw new IllegalStateException("Repeated target navigation");probeRequested=true;}
    boolean loadError(String path,boolean applied){if("probe".equals(path)&&probeRequested){targetError=true;return true;}
      return "other".equals(path)||("bootstrap".equals(path)&&!applied);}
    boolean probeReady(){return probeRequested&&probeStart&&probeDocument&&probeStop&&!targetError
      &&"probe".equals(activePath)&&"probe".equals(locationPath);}
  }
  NavigationState navigation;
  GeckoRuntime runtime;GeckoSession session;GeckoView view;WebExtension extension;WebExtension.Port port;
  NativeTimezoneProbeServer server;JSONObject build,applied,readback,nativeFailure;
  String nonce,zone,javaZone,icuZone,processTz,stage="initial",failure="";
  boolean ready,bootstrapStarted,bootstrapCompleted,applySent,readSent,done,closed;
  long started;
  @Override public void onCreate(Bundle state){super.onCreate(null);try{
    if(!"local.pocketchat.test".equals(getPackageName()))throw new SecurityException("Integration only");
    nonce=getIntent().getStringExtra("runNonce");zone=getIntent().getStringExtra("zoneId");
    if(nonce==null||!nonce.matches("[0-9a-f]{32}")||!ZONES.contains(zone))throw new SecurityException("Fresh controlled zone invocation");
    build=IntegrationBuildIdentity.read(this);
    if(!build.getString("sourceCommit").equals(getIntent().getStringExtra("sourceCommit")))throw new SecurityException("Current source only");
    started=SystemClock.elapsedRealtime();javaZone=TimeZone.getDefault().getID();
    icuZone=android.icu.util.TimeZone.getDefault().getID();processTz=System.getenv("TZ");
    server=new NativeTimezoneProbeServer(this,nonce,build.getString("sourceCommit"),packet->handler.post(()->receive(packet)));server.start();
    navigation=new NavigationState(server.url("/bootstrap"),server.url("/probe"));
    File profile=new File(getNoBackupFilesDir(),"native-timezone-"+nonce);
    if(!profile.mkdirs())throw new IOException("Fresh isolated profile required");
    File config=new File(getNoBackupFilesDir(),"native-timezone-"+nonce+".yaml");
    String prefs="prefs:\n  network.proxy.type: 1\n  network.proxy.http: '127.0.0.1'\n  network.proxy.http_port: "+server.port()+"\n"
      +"  network.proxy.ssl: '127.0.0.1'\n  network.proxy.ssl_port: "+server.port()+"\n  network.proxy.no_proxies_on: '127.0.0.1,localhost'\n"
      +"  network.trr.mode: 5\n  network.dns.disablePrefetch: true\n  network.prefetch-next: false\n  network.http.speculative-parallel-limit: 0\n"
      +"  network.captive-portal-service.enabled: false\n  network.connectivity-service.enabled: false\n"
      +"  datareporting.healthreport.uploadEnabled: false\n  toolkit.telemetry.enabled: false\n";
    try(FileOutputStream output=new FileOutputStream(config)){output.write(prefs.getBytes(StandardCharsets.UTF_8));}
    runtime=GeckoRuntime.create(this,new GeckoRuntimeSettings.Builder()
      .arguments(new String[]{"-profile",profile.getAbsolutePath()}).configFilePath(config.getAbsolutePath())
      .remoteDebuggingEnabled(false).consoleOutput(false).build());
    view=new GeckoView(this);setContentView(view);
    stage="extension";publish();
    handler.postDelayed(()->fail(new IllegalStateException("Diagnostic deadline")),120000);
    runtime.getWebExtensionController().ensureBuiltIn("resource://android/assets/native-timezone-extension/",EXTENSION).accept(value->{
      if(closed||done)return;extension=value;extension.setMessageDelegate(messages,HOST);
      session=new GeckoSession();
      session.setNavigationDelegate(new GeckoSession.NavigationDelegate(){
        @Override public void onLocationChange(GeckoSession current,String url,List<GeckoSession.PermissionDelegate.ContentPermission> permissions,Boolean gesture){
          if(current!=session||done)return;String path=navigation.path(url);navigation.location(path);navigationEvent("location",path,null,null,null);
          if("other".equals(path)){fail(new IllegalStateException("Uncontrolled top-level navigation"));return;}navigationProgress();
        }
        @Override public GeckoResult<String> onLoadError(GeckoSession current,String url,WebRequestError error){
          if(current!=session||done)return null;String path=navigation.path(url);
          navigationEvent("load-error",path,null,error.category,error.code);
          if(navigation.loadError(path,applySent))fail(new IllegalStateException("Owned controlled page load error"));
          return null;
        }
      });
      session.setProgressDelegate(new GeckoSession.ProgressDelegate(){
        @Override public void onPageStart(GeckoSession current,String url){if(current==session&&!done){String path=navigation.path(url);
          navigation.start(path);navigationEvent("page-start",path,null,null,null);
          if("other".equals(path))fail(new IllegalStateException("Uncontrolled top-level navigation"));}}
        @Override public void onPageStop(GeckoSession current,boolean success){
          if(current!=session||done)return;navigation.stop(success);
          navigationEvent(success?"page-stop":"page-failed",navigation.activePath,success,null,null);
          navigationProgress();
        }
      });
      session.open(runtime);view.setSession(session);session.setActive(true);bootstrap();
    },this::fail);
  }catch(Throwable error){fail(error);}}
  final WebExtension.MessageDelegate messages=new WebExtension.MessageDelegate(){
    @Override public void onConnect(WebExtension.Port incoming){
      if(done||closed||incoming.sender.environmentType!=WebExtension.MessageSender.ENV_TYPE_EXTENSION||!HOST.equals(incoming.name))return;
      if(port!=null){fail(new SecurityException("Duplicate private port"));return;}port=incoming;
      incoming.setDelegate(new WebExtension.PortDelegate(){
        @Override public void onPortMessage(Object message,WebExtension.Port source){
          if(done||closed||source!=port||!(message instanceof JSONObject))return;
          JSONObject value=(JSONObject)message;
          try{
            if("timezoneProbeReady".equals(value.optString("kind"))){
              if(!Boolean.TRUE.equals(value.opt("apiAvailable")))throw new IllegalStateException("Privileged experiment API unavailable");
              ready=true;bootstrap();return;
            }
            if("timezoneProbeDocumentReady".equals(value.optString("kind"))){
              if(!(value.opt("url") instanceof String))throw new SecurityException("Private document binding differs");
              String path=navigation.path(value.getString("url"));
              if(!Arrays.asList("bootstrap","probe").contains(path))throw new SecurityException("Private document binding differs");
              navigation.document(path);navigationEvent("private-document-ready",path,null,null,null);navigationProgress();return;
            }
            if(!"timezoneProbeResult".equals(value.optString("kind")))return;
            boolean setting=!(readSent);String token=nonce+(setting?"-apply":"-read");
            if(!(value.opt("schema") instanceof Integer)||value.getInt("schema")!=1
                ||!token.equals(value.opt("requestToken")))throw new SecurityException("Private receipt binding differs");
            if(!Boolean.TRUE.equals(value.opt("nativeSettingReadback"))){
              String reason=value.optString("reason");
              Set<String> safe=new HashSet<>(Arrays.asList("probe-requires-one-tab","native-timezone-api-unavailable",
                "native-timezone-call-failed","app-bundled-timezone-api-only","invalid-timezone-request-token",
                "invalid-timezone-tab","timezone-tab-unavailable","native-timezone-property-unavailable",
                "invalid-timezone-id","native-timezone-readback-unavailable"));
              nativeFailure=new JSONObject().put("status","failed")
                .put("reason",safe.contains(reason)?reason:"unrecognized-native-failure")
                .put("requestTokenMatched",true).put("nativeSettingReadback",false);
              throw new IllegalStateException("Native readback unavailable");
            }
            if(!Boolean.TRUE.equals(value.opt("nativeSettingReadback"))
                ||!Boolean.FALSE.equals(value.opt("workerCoverageVerified"))
                ||!Boolean.FALSE.equals(value.opt("serviceWorkerCoverageVerified"))
                ||!"top-browsing-context".equals(value.opt("scope"))
                ||!value.optString("contextId").matches("[1-9][0-9]{0,23}"))throw new IllegalStateException("Native readback unavailable");
            if(setting){
              if(!applySent||applied!=null||!"applied".equals(value.opt("status"))
                  ||!zone.equals(value.opt("requestedZoneId"))||!zone.equals(value.opt("nativeZoneId")))throw new IllegalStateException("Native apply failed");
              applied=new JSONObject(value.toString());navigation.requestProbe();stage="observing";publish();session.loadUri(server.url("/probe"));
            }else{
              if(applied==null||readback!=null||!"read".equals(value.opt("status"))
                  ||!zone.equals(value.opt("nativeZoneId"))||!applied.getString("contextId").equals(value.opt("contextId")))throw new IllegalStateException("Same-origin native setting did not persist");
              readback=new JSONObject(value.toString());done=true;stage="complete";publish();
            }
          }catch(Throwable error){fail(error);}
        }
        @Override public void onDisconnect(WebExtension.Port source){if(source==port){port=null;if(!done&&!closed)fail(new IllegalStateException("Private port disconnected"));}}
      });
    }
  };
  void bootstrap(){if(done||closed||bootstrapStarted||!ready||port==null||session==null||!session.isOpen())return;
    bootstrapStarted=true;stage="bootstrap";publish();session.loadUri(server.url("/bootstrap"));}
  void apply(){if(done||closed||applySent||!bootstrapCompleted||!ready||port==null)return;try{
    applySent=true;stage="native-apply";publish();
    port.postMessage(new JSONObject().put("kind","timezoneProbeApply").put("requestToken",nonce+"-apply").put("zoneId",zone));
  }catch(Throwable error){fail(error);}}
  void navigationProgress(){if(done||closed)return;
    if(!applySent&&"bootstrap".equals(stage)&&navigation.bootstrapReady()){bootstrapCompleted=true;apply();}
    maybeRead();
  }
  void receive(JSONObject packet){if(done||closed||applied==null||!"observing".equals(stage))return;try{
    String role=packet.getString("role");
    if(observations.containsKey(role))throw new SecurityException("Repeated observation");
    observations.put(role,new JSONObject(packet.toString()));publish();
    maybeRead();
  }catch(Throwable error){fail(error);}}
  void maybeRead(){if(done||closed||applied==null||!"observing".equals(stage)||!navigation.probeReady())return;try{
    if(observations.size()==NativeTimezoneProbeServer.ROLES.size()&&!readSent){
      readSent=true;stage="native-readback";publish();
      port.postMessage(new JSONObject().put("kind","timezoneProbeRead").put("requestToken",nonce+"-read"));
    }
  }catch(Throwable error){fail(error);}}
  void navigationEvent(String name,String path,Boolean success,Integer category,Integer code){try{
    if(events.length()<64)events.put(new JSONObject().put("event",name).put("stage",stage).put("path",path)
      .put("generation",navigation.generation).put("success",success==null?JSONObject.NULL:success)
      .put("errorCategory",category==null?JSONObject.NULL:category).put("errorCode",code==null?JSONObject.NULL:code)
      .put("nativeUrlAvailable",!"page-stop".equals(name)&&!"page-failed".equals(name)).put("elapsedMs",SystemClock.elapsedRealtime()-started));publish();
  }catch(Exception ignored){}}
  void fail(Throwable error){if(done||closed)return;String reason=error.getMessage();
    Set<String> safe=new HashSet<>(Arrays.asList("Integration only","Fresh controlled zone invocation","Current source only",
      "Fresh isolated profile required","Diagnostic deadline","Controlled page failed","Privileged experiment API unavailable",
      "Duplicate private port","Private receipt binding differs","Native readback unavailable","Native apply failed",
      "Same-origin native setting did not persist","Private port disconnected","Repeated observation",
      "Uncontrolled top-level navigation","Owned controlled page load error","Private document binding differs","Repeated target navigation"));
    failure=error.getClass().getSimpleName()+(safe.contains(reason)?": "+reason:"");done=true;stage="failed";publish();}
  void publish(){if(build==null||nonce==null)return;try{
    JSONArray values=new JSONArray();for(String role:NativeTimezoneProbeServer.ROLES)if(observations.containsKey(role))values.put(observations.get(role));
    JSONObject process=new JSONObject().put("pid",android.os.Process.myPid()).put("uid",android.os.Process.myUid())
      .put("javaTimezoneBefore",javaZone).put("javaTimezoneAfter",TimeZone.getDefault().getID())
      .put("icuTimezoneBefore",icuZone).put("icuTimezoneAfter",android.icu.util.TimeZone.getDefault().getID())
      .put("tzEnvironmentBefore",processTz==null?JSONObject.NULL:processTz)
      .put("tzEnvironmentAfter",System.getenv("TZ")==null?JSONObject.NULL:System.getenv("TZ"));
    JSONObject report=new JSONObject().put("schema",1).put("status",done?(failure.isEmpty()?"observed":"failed"):"running")
      .put("diagnosticOnly",true).put("releaseAcceptance",false).put("actualAndroidExecution",true)
      .put("actualGeckoExecution",session!=null&&session.isOpen()).put("sourceCommit",build.getString("sourceCommit"))
      .put("sourceTree",build.getString("sourceTree")).put("buildIdentity",build).put("runNonce",nonce).put("requestedZoneId",zone)
      .put("stage",stage).put("failure",failure).put("process",process)
      .put("nativeApply",applied==null?JSONObject.NULL:applied).put("nativeRead",readback==null?JSONObject.NULL:readback)
      .put("nativeFailure",nativeFailure==null?JSONObject.NULL:nativeFailure)
      .put("observations",values).put("nativeEvents",events).put("javaTimezoneOverrideUsed",false).put("processTimezoneEnvironmentChangedByProbe",false)
      .put("navigation",navigation==null?JSONObject.NULL:new JSONObject().put("schema",1)
        .put("targetPath","probe").put("activePath",navigation.activePath).put("locationPath",navigation.locationPath)
        .put("generation",navigation.generation).put("failedStopsWithoutNativeUrl",navigation.failedStops)
        .put("bootstrapStarted",navigation.bootstrapStart).put("bootstrapDocumentReady",navigation.bootstrapDocument)
        .put("bootstrapStoppedSuccessfully",navigation.bootstrapStop).put("probeRequested",navigation.probeRequested)
        .put("probeStarted",navigation.probeStart).put("probeDocumentReady",navigation.probeDocument)
        .put("probeStoppedSuccessfully",navigation.probeStop).put("targetLoadError",navigation.targetError)
        .put("targetOwnedCompletion",navigation.probeReady()))
      .put("server",server==null?JSONObject.NULL:server.snapshot())
      .put("debuggingEndpointUsed",false).put("dateOrIntlOverrideUsed",false)
      .put("workerCoverageVerified",false).put("serviceWorkerCoverageVerified",false).put("fingerprintProtectionVerified",false)
      .put("scope","Privileged built-in experiment sets the actual Gecko top BrowsingContext timezone before a same-origin controlled measurement document. Unmodified Date/Intl are measured independently in page and available workers; worker success is not inferred from native setting acknowledgement. Not production integration, arbitrary-site, cross-origin, full fingerprint or release acceptance.");
    byte[] bytes=(report.toString()+"\n").getBytes(StandardCharsets.UTF_8);if(bytes.length>131072)throw new IOException("Report bound");
    AtomicFile file=new AtomicFile(new File(getFilesDir(),"native-timezone-"+nonce+".json"));FileOutputStream output=null;
    try{output=file.startWrite();output.write(bytes);file.finishWrite(output);}catch(Exception error){if(output!=null)file.failWrite(output);}
  }catch(Exception ignored){}}
  @Override protected void onDestroy(){closed=true;handler.removeCallbacksAndMessages(null);if(server!=null)server.close();
    if(session!=null&&session.isOpen())session.close();if(runtime!=null)runtime.shutdown();super.onDestroy();}
}
