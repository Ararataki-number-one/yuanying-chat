package local.pocketchat;

import android.app.Activity;
import android.os.*;
import android.util.AtomicFile;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.json.*;
import org.mozilla.geckoview.*;

/** Integration-only sequential native CPU-pref and untouched navigator observations. */
public final class NativeHardwareProbeActivity extends Activity {
  static final String EXTENSION="hardware-probe@pocketchat.local",HOST="pockethardwareprobe";
  static final List<String> PHASES=NativeHardwareProbeServer.PHASES;
  static final Set<String> SAFE_NATIVE=new HashSet<>(Arrays.asList("probe-native-hardware-api-only",
    "invalid-hardware-request-token","native-hardware-pref-unavailable","native-hardware-readback-unavailable",
    "invalid-hardware-cap","native-hardware-setting-failed","native-rfp-policy-changed",
    "native-hardware-readback-mismatch","native-hardware-api-unavailable","native-hardware-call-failed"));
  static final Set<String> SAFE_ERRORS=new HashSet<>(Arrays.asList("Unavailable","TimeoutError","WorkerError","InvalidReply"));
  final Handler handler=new Handler(Looper.getMainLooper());
  final List<Phase> phases=new ArrayList<>();final JSONArray events=new JSONArray();
  static final class NavigationState {
    final String bootstrapUrl,probeUrl,targetPath;
    String activePath="initial",locationPath="initial";int generation,failedStops;
    boolean bootstrapStart,bootstrapDocument,bootstrapStop,probeRequested,probeStart,probeDocument,probeStop,targetError;
    NavigationState(String bootstrapUrl,String probeUrl,String targetPath,int generation){
      this.bootstrapUrl=bootstrapUrl;this.probeUrl=probeUrl;this.targetPath=targetPath;this.generation=generation;
    }
    void start(String path,int generation){this.generation=generation;activePath=path;
      if("bootstrap".equals(path))bootstrapStart=true;if(targetPath.equals(path)&&probeRequested)probeStart=true;}
    void location(String path){locationPath=path;}
    void document(String path){if("bootstrap".equals(path))bootstrapDocument=true;if(targetPath.equals(path)&&probeRequested)probeDocument=true;}
    void stop(boolean success){if(!success){failedStops++;return;}
      if("bootstrap".equals(activePath)&&!probeRequested)bootstrapStop=true;
      if(targetPath.equals(activePath)&&probeRequested)probeStop=true;}
    boolean bootstrapReady(){return bootstrapStart&&bootstrapDocument&&bootstrapStop&&"bootstrap".equals(activePath)&&"bootstrap".equals(locationPath);}
    void requestProbe(){if(probeRequested)throw new IllegalStateException("Repeated target navigation");probeRequested=true;}
    boolean probeReady(){return probeRequested&&probeStart&&probeDocument&&probeStop&&!targetError
      &&targetPath.equals(activePath)&&targetPath.equals(locationPath);}
    JSONObject json()throws JSONException{return new JSONObject().put("schema",1).put("targetPath",targetPath)
      .put("activePath",activePath).put("locationPath",locationPath).put("generation",generation)
      .put("failedStopsWithoutNativeUrl",failedStops).put("bootstrapStarted",bootstrapStart)
      .put("bootstrapDocumentReady",bootstrapDocument).put("bootstrapStoppedSuccessfully",bootstrapStop)
      .put("probeRequested",probeRequested).put("probeStarted",probeStart).put("probeDocumentReady",probeDocument)
      .put("probeStoppedSuccessfully",probeStop).put("targetLoadError",targetError).put("targetOwnedCompletion",probeReady());}
  }
  static final class Phase {
    final String name;final NavigationState navigation;final Map<String,JSONObject> observations=new LinkedHashMap<>();
    JSONObject nativeApply,nativeRead;
    Phase(String name,NavigationState navigation){this.name=name;this.navigation=navigation;}
    JSONObject json()throws JSONException{JSONArray values=new JSONArray();
      for(String role:NativeHardwareProbeServer.ROLES)if(observations.containsKey(role))values.put(observations.get(role));
      return new JSONObject().put("phase",name).put("nativeApply",nativeApply==null?JSONObject.NULL:nativeApply)
        .put("nativeRead",nativeRead==null?JSONObject.NULL:nativeRead).put("navigation",navigation.json()).put("observations",values);}
  }
  NavigationState navigation;GeckoRuntime runtime;GeckoSession session;GeckoView view;
  WebExtension extension;WebExtension.Port port;NativeHardwareProbeServer server;JSONObject build;
  String nonce,mode,javaZone,icuZone,processTz,stage="initial",failure="";
  boolean ready,bootstrapStarted,bootstrapCompleted,done,closed;int phaseIndex=-1,generation,baselineCap;
  long started;
  String phaseName(){return phaseIndex<0?"initial":PHASES.get(phaseIndex);}
  Phase current(){return phaseIndex>=0&&phaseIndex<phases.size()?phases.get(phaseIndex):null;}
  String path(String url){
    if("about:blank".equals(url))return "initial";
    if(server.url("/bootstrap").equals(url))return "bootstrap";
    for(String phase:PHASES)if(server.url("/"+phase+"/probe").equals(url))return phase+"/probe";
    return "other";
  }
  @Override public void onCreate(Bundle state){super.onCreate(null);try{
    if(!"local.pocketchat.test".equals(getPackageName()))throw new SecurityException("Integration only");
    nonce=getIntent().getStringExtra("runNonce");mode=getIntent().getStringExtra("mode");
    if(nonce==null||!nonce.matches("[0-9a-f]{32}")||!Arrays.asList("standard","rfp").contains(mode))throw new SecurityException("Fresh controlled mode invocation");
    build=IntegrationBuildIdentity.read(this);
    if(!build.getString("sourceCommit").equals(getIntent().getStringExtra("sourceCommit")))throw new SecurityException("Current source only");
    started=SystemClock.elapsedRealtime();javaZone=TimeZone.getDefault().getID();icuZone=android.icu.util.TimeZone.getDefault().getID();processTz=System.getenv("TZ");
    server=new NativeHardwareProbeServer(this,nonce,build.getString("sourceCommit"),packet->handler.post(()->receive(packet)));server.start();
    navigation=new NavigationState(server.url("/bootstrap"),server.url("/baseline/probe"),"baseline/probe",0);
    File profile=new File(getNoBackupFilesDir(),"native-hardware-"+nonce);if(!profile.mkdirs())throw new IOException("Fresh isolated profile required");
    File config=new File(getNoBackupFilesDir(),"native-hardware-"+nonce+".yaml");
    String prefs="prefs:\n  network.proxy.type: 1\n  network.proxy.http: '127.0.0.1'\n  network.proxy.http_port: "+server.port()+"\n"
      +"  network.proxy.ssl: '127.0.0.1'\n  network.proxy.ssl_port: "+server.port()+"\n  network.proxy.no_proxies_on: '127.0.0.1,localhost'\n"
      +"  network.trr.mode: 5\n  network.dns.disablePrefetch: true\n  network.prefetch-next: false\n  network.http.speculative-parallel-limit: 0\n"
      +"  network.captive-portal-service.enabled: false\n  network.connectivity-service.enabled: false\n"
      +"  datareporting.healthreport.uploadEnabled: false\n  toolkit.telemetry.enabled: false\n";
    // A separate fresh runtime observes RFP precedence; no command disables it.
    if("rfp".equals(mode))prefs+="  privacy.resistFingerprinting: true\n";
    try(FileOutputStream output=new FileOutputStream(config)){output.write(prefs.getBytes(StandardCharsets.UTF_8));}
    runtime=GeckoRuntime.create(this,new GeckoRuntimeSettings.Builder().arguments(new String[]{"-profile",profile.getAbsolutePath()})
      .configFilePath(config.getAbsolutePath()).remoteDebuggingEnabled(false).consoleOutput(false).build());
    view=new GeckoView(this);setContentView(view);stage="extension";publish();
    handler.postDelayed(()->fail(new IllegalStateException("Diagnostic deadline")),210000);
    runtime.getWebExtensionController().ensureBuiltIn("resource://android/assets/native-hardware-extension/",EXTENSION).accept(value->{
      if(closed||done)return;extension=value;extension.setMessageDelegate(messages,HOST);session=new GeckoSession();
      session.setNavigationDelegate(new GeckoSession.NavigationDelegate(){
        @Override public void onLocationChange(GeckoSession current,String url,List<GeckoSession.PermissionDelegate.ContentPermission> permissions,Boolean gesture){
          if(current!=session||done)return;String p=path(url);navigation.location(p);event("location",p,null,null,null);
          if("other".equals(p)){fail(new IllegalStateException("Uncontrolled top-level navigation"));return;}advance();
        }
        @Override public GeckoResult<String> onLoadError(GeckoSession current,String url,WebRequestError error){
          if(current!=session||done)return null;String p=path(url);event("load-error",p,null,error.category,error.code);
          if(navigation.targetPath.equals(p)&&navigation.probeRequested){navigation.targetError=true;fail(new IllegalStateException("Owned controlled page load error"));}
          else if("other".equals(p)||"bootstrap".equals(p)&&!bootstrapCompleted)fail(new IllegalStateException("Owned controlled page load error"));
          return null;
        }
      });
      session.setProgressDelegate(new GeckoSession.ProgressDelegate(){
        @Override public void onPageStart(GeckoSession current,String url){if(current==session&&!done){String p=path(url);navigation.start(p,++generation);event("page-start",p,null,null,null);
          if("other".equals(p))fail(new IllegalStateException("Uncontrolled top-level navigation"));}}
        @Override public void onPageStop(GeckoSession current,boolean success){if(current!=session||done)return;
          navigation.stop(success);event(success?"page-stop":"page-failed",navigation.activePath,success,null,null);advance();}
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
          if(done||closed||source!=port||!(message instanceof JSONObject))return;JSONObject value=(JSONObject)message;
          try{
            if("hardwareProbeReady".equals(value.optString("kind"))){if(!Boolean.TRUE.equals(value.opt("apiAvailable")))throw new IllegalStateException("Privileged experiment API unavailable");ready=true;bootstrap();return;}
            if("hardwareProbeDocumentReady".equals(value.optString("kind"))){
              if(!(value.opt("url") instanceof String))throw new SecurityException("Private document binding differs");String p=path(value.getString("url"));
              if("other".equals(p))throw new SecurityException("Private document binding differs");navigation.document(p);event("private-document-ready",p,null,null,null);advance();return;
            }
            if(!"hardwareProbeResult".equals(value.optString("kind")))return;
            Phase phase=current();if(phase==null)throw new SecurityException("Native phase receipt binding differs");
            boolean applying="native-apply".equals(stage),reading="native-readback".equals(stage);
            if(!applying&&!reading)throw new SecurityException("Native phase receipt binding differs");
            String token=nonce+"-"+phase.name+(applying?"-apply":"-read");
            if(!token.equals(value.opt("requestToken")))throw new SecurityException("Native phase receipt binding differs");
            if("failed".equals(value.optString("status"))){String reason=value.optString("reason");throw new IllegalStateException(SAFE_NATIVE.contains(reason)?reason:"native-hardware-call-failed");}
            validateAck(value,phase,applying);
            if(applying){phase.nativeApply=new JSONObject(value.toString());navigation.requestProbe();stage="observing";publish();session.loadUri(navigation.probeUrl);}
            else{phase.nativeRead=new JSONObject(value.toString());
              if(phaseIndex==PHASES.size()-1){done=true;stage="complete";publish();}else beginPhase(phaseIndex+1);}
          }catch(Throwable error){fail(error);}
        }
        @Override public void onDisconnect(WebExtension.Port source){if(source==port){port=null;if(!done&&!closed)fail(new IllegalStateException("Private port disconnected"));}}
      });
    }
  };
  static boolean keys(JSONObject value,String... names){Set<String> actual=new HashSet<>();Iterator<String> it=value.keys();while(it.hasNext())actual.add(it.next());return actual.equals(new HashSet<>(Arrays.asList(names)));}
  void validateAck(JSONObject value,Phase phase,boolean applying)throws Exception{
    if(!keys(value,"kind","schema","status","operation","requestToken","requestedCap","configuredCap","hasUserValue","rfpEnabled","nativePreferenceReadback","scope","workerCoverageVerified","fingerprintProtectionVerified")
        ||!(value.opt("schema") instanceof Integer)||value.getInt("schema")!=1||!(value.opt("configuredCap") instanceof Integer)
        ||value.getInt("configuredCap")<1||value.getInt("configuredCap")>65536||!(value.opt("hasUserValue") instanceof Boolean)
        ||!Boolean.valueOf("rfp".equals(mode)).equals(value.opt("rfpEnabled"))
        ||!Boolean.TRUE.equals(value.opt("nativePreferenceReadback"))||!"runtime-native-pref".equals(value.opt("scope"))
        ||!Boolean.FALSE.equals(value.opt("workerCoverageVerified"))||!Boolean.FALSE.equals(value.opt("fingerprintProtectionVerified")))throw new SecurityException("Native phase receipt binding differs");
    String operation=applying?("baseline".equals(phase.name)?"read":"reset".equals(phase.name)?"reset":"set"):"read";
    String status="set".equals(operation)?"applied":operation;
    if(!operation.equals(value.opt("operation"))||!status.equals(value.opt("status")))throw new SecurityException("Native phase receipt binding differs");
    int configured=value.getInt("configuredCap");boolean user=value.getBoolean("hasUserValue");
    if("set".equals(operation)){int cap="cap2".equals(phase.name)?2:1;
      if(!(value.opt("requestedCap") instanceof Integer)||value.getInt("requestedCap")!=cap||configured!=cap||!user)throw new IllegalStateException("Native cap readback differs");}
    else if(!value.isNull("requestedCap"))throw new SecurityException("Native phase receipt binding differs");
    if(applying&&"baseline".equals(phase.name)){if(user)throw new IllegalStateException("Fresh native CPU baseline required");baselineCap=configured;}
    if(applying&&"reset".equals(phase.name)&&(user||configured!=baselineCap))throw new IllegalStateException("Native reset readback differs");
    if(!applying&&(phase.nativeApply==null||configured!=phase.nativeApply.getInt("configuredCap")||user!=phase.nativeApply.getBoolean("hasUserValue")))throw new IllegalStateException("Native setting did not persist");
  }
  void bootstrap(){if(done||closed||bootstrapStarted||!ready||port==null||session==null||!session.isOpen())return;
    bootstrapStarted=true;stage="bootstrap";publish();session.loadUri(server.url("/bootstrap"));}
  void beginPhase(int index){if(done||closed)return;try{
    phaseIndex=index;String name=PHASES.get(index);
    if(index>0){navigation=new NavigationState(server.url("/bootstrap"),server.url("/"+name+"/probe"),name+"/probe",generation);
      navigation.bootstrapStart=true;navigation.bootstrapDocument=true;navigation.bootstrapStop=true;}
    Phase phase=new Phase(name,navigation);phases.add(phase);stage="native-apply";publish();
    String kind=index==0?"hardwareProbeRead":index==3?"hardwareProbeReset":"hardwareProbeSet";
    JSONObject command=new JSONObject().put("kind",kind).put("requestToken",nonce+"-"+name+"-apply");
    if(index==1||index==2)command.put("cap",index==1?2:1);port.postMessage(command);
  }catch(Throwable error){fail(error);}}
  void advance(){if(done||closed)return;
    if(phaseIndex<0&&"bootstrap".equals(stage)&&navigation.bootstrapReady()){bootstrapCompleted=true;beginPhase(0);return;}
    Phase phase=current();if(phase==null||!"observing".equals(stage)||phase.nativeApply==null||!navigation.probeReady()
        ||phase.observations.size()!=NativeHardwareProbeServer.ROLES.size())return;
    try{stage="native-readback";publish();port.postMessage(new JSONObject().put("kind","hardwareProbeRead").put("requestToken",nonce+"-"+phase.name+"-read"));}catch(Throwable error){fail(error);}
  }
  void receive(JSONObject value){if(done||closed)return;try{
    Phase phase=current();if(phase==null||!"observing".equals(stage)||!phase.name.equals(value.opt("phase")))throw new SecurityException("Unowned phase observation");
    String role=value.getString("role");if(phase.observations.containsKey(role))throw new SecurityException("Repeated observation");
    String status=value.getString("status");
    if("observed".equals(status)){JSONObject sample=value.getJSONObject("observation");
      if(!keys(sample,"hardwareConcurrency","nativeGetter")||!(sample.opt("hardwareConcurrency") instanceof Integer)
          ||sample.getInt("hardwareConcurrency")<1||sample.getInt("hardwareConcurrency")>65536
          ||!(sample.opt("nativeGetter") instanceof Boolean)||!value.isNull("error"))throw new SecurityException("Unbound CPU observation");}
    else if(!value.isNull("observation")||!(value.opt("error") instanceof String)||!SAFE_ERRORS.contains(value.getString("error")))throw new SecurityException("Unbound CPU observation");
    phase.observations.put(role,new JSONObject(value.toString()));publish();advance();
  }catch(Throwable error){fail(error);}}
  void event(String event,String path,Boolean success,Integer category,Integer code){try{
    if(events.length()<256)events.put(new JSONObject().put("event",event).put("stage",stage).put("phase",phaseName()).put("path",path)
      .put("generation",generation).put("success",success==null?JSONObject.NULL:success)
      .put("errorCategory",category==null?JSONObject.NULL:category).put("errorCode",code==null?JSONObject.NULL:code)
      .put("nativeUrlAvailable",!"page-stop".equals(event)&&!"page-failed".equals(event)).put("elapsedMs",SystemClock.elapsedRealtime()-started));publish();
  }catch(Exception ignored){}}
  void fail(Throwable error){if(done||closed)return;String reason=error.getMessage();
    Set<String> safe=new HashSet<>(Arrays.asList("Integration only","Fresh controlled mode invocation","Current source only","Fresh isolated profile required",
      "Diagnostic deadline","Uncontrolled top-level navigation","Owned controlled page load error","Privileged experiment API unavailable",
      "Duplicate private port","Private document binding differs","Native phase receipt binding differs","Private port disconnected",
      "Native cap readback differs","Fresh native CPU baseline required","Native reset readback differs","Native setting did not persist",
      "Repeated target navigation","Unowned phase observation","Repeated observation","Unbound CPU observation"));safe.addAll(SAFE_NATIVE);
    failure=error.getClass().getSimpleName()+(safe.contains(reason)?": "+reason:"");done=true;stage="failed";publish();}
  void publish(){if(build==null||nonce==null)return;try{
    JSONArray values=new JSONArray();for(Phase phase:phases)values.put(phase.json());
    JSONObject process=new JSONObject().put("pid",android.os.Process.myPid()).put("uid",android.os.Process.myUid())
      .put("javaTimezoneBefore",javaZone).put("javaTimezoneAfter",TimeZone.getDefault().getID())
      .put("icuTimezoneBefore",icuZone).put("icuTimezoneAfter",android.icu.util.TimeZone.getDefault().getID())
      .put("tzEnvironmentBefore",processTz==null?JSONObject.NULL:processTz)
      .put("tzEnvironmentAfter",System.getenv("TZ")==null?JSONObject.NULL:System.getenv("TZ"));
    JSONObject report=new JSONObject().put("schema",1).put("status",done?(failure.isEmpty()?"observed":"failed"):"running")
      .put("stage",stage).put("failure",failure).put("diagnosticOnly",true).put("releaseAcceptance",false)
      .put("actualAndroidExecution",true).put("actualGeckoExecution",session!=null&&session.isOpen())
      .put("sourceCommit",build.getString("sourceCommit")).put("sourceTree",build.getString("sourceTree")).put("buildIdentity",build)
      .put("runNonce",nonce).put("mode",mode).put("process",process).put("nativePreferenceOnly",true)
      .put("navigatorGetterOverrideUsed",false).put("debuggingEndpointUsed",false).put("javaTimezoneOverrideUsed",false)
      .put("processTimezoneEnvironmentChangedByProbe",false).put("workerCoverageVerified",false).put("fingerprintProtectionVerified",false)
      .put("phases",values).put("server",server==null?JSONObject.NULL:server.snapshot()).put("nativeEvents",events);
    byte[] bytes=(report.toString()+"\n").getBytes(StandardCharsets.UTF_8);if(bytes.length>262144)throw new IOException("Report bound");
    AtomicFile file=new AtomicFile(new File(getFilesDir(),"native-hardware-"+nonce+".json"));FileOutputStream output=null;
    try{output=file.startWrite();output.write(bytes);file.finishWrite(output);}catch(Exception error){if(output!=null)file.failWrite(output);}
  }catch(Exception ignored){}}
  @Override protected void onDestroy(){closed=true;handler.removeCallbacksAndMessages(null);if(server!=null)server.close();
    if(session!=null&&session.isOpen())session.close();if(runtime!=null)runtime.shutdown();super.onDestroy();}
}
