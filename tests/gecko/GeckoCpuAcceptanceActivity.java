package local.pocketchat;

import android.content.*;
import android.os.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;
import org.mozilla.geckoview.*;

/** Test-only real MainActivity/ChatSession cold CPU admission workload. */
public class GeckoCpuAcceptanceActivity extends MainActivity {
  static final int PORT=18766;
  final Handler poll=new Handler(Looper.getMainLooper());
  final ExecutorService observer=Executors.newSingleThreadExecutor();
  final JSONArray events=new JSONArray();
  JSONObject build,host=new JSONObject();String run,invocation,mode,target,stage="seed",failure="";
  JSONObject tls=new JSONObject();String expectedLeaf;boolean enterpriseRoots;
  boolean rfp,retain,staleUser,terminal,started,located,stopped,loadError,currentOwned,observerBusy,targetDispatched;
  long deadline,templatePolicyBefore;int slot;boolean identityApplyInvoked,identityApplyCompleted;
  @Override public void onCreate(Bundle state){try{
    if(!"local.pocketchat.test".equals(getPackageName()))throw new SecurityException("Integration package only");
    run=getIntent().getStringExtra("runNonce");invocation=getIntent().getStringExtra("caseNonce");mode=getIntent().getStringExtra("cpuMode");
    String source=getIntent().getStringExtra("sourceCommit");rfp=getIntent().getBooleanExtra("rfp",false);retain=getIntent().getBooleanExtra("retain",false);staleUser=getIntent().getBooleanExtra("staleUser",false);slot=Profiles.slot(this);
    if(run==null||!run.matches("[0-9a-f]{32}")||invocation==null||!invocation.matches("[0-9a-f]{32}")||source==null||!source.matches("[0-9a-f]{40}")||!Arrays.asList("automatic","1","2").contains(mode)||slot<1||slot>2)throw new SecurityException("Exact cold workload binding required");
    build=IntegrationBuildIdentity.read(this);if(!source.equals(build.getString("sourceCommit")))throw new SecurityException("Selected APK source differs");
    expectedLeaf=getIntent().getStringExtra("expectedLeafSha256");if(expectedLeaf==null||!expectedLeaf.matches("[0-9a-f]{64}"))throw new SecurityException("Controlled TLS leaf binding required");
    target="https://fp-a.pocketchat.test/cpu/slot"+slot+"/page?run="+run+"&case="+invocation;
    // This test seeds a normal encrypted desired record before any production
    // ChatSession/GeckoRuntime exists. The real production cold admission owns
    // every native preference operation and first session creation below.
    final Throwable[] seedError={null};Thread seed=new Thread(()->{try{
      ProfileCatalog.get(this).created(slot);
      BrowserFingerprintIntegrationActivity.configure(this,PORT,target);
      getSharedPreferences("chat",0).edit().putInt("privacyLevel",rfp?2:1).putBoolean("pageMode",true).commit();
      EnvironmentSpecRepository repository=new EnvironmentSpecRepository(this);EnvironmentSpec before=repository.load();
      JSONObject browser=BrowserIdentitySpec.preset(rfp?BrowserIdentitySpec.RFP:BrowserIdentitySpec.MOBILE).json();
      if(!before.desired().browser().toString().equals(browser.toString()))repository.updateDesired(before.identity,before.desiredRevision,new EnvironmentSpec.Configuration(browser,before.desired().network));
      GeckoCpuStore.State saved=GeckoCpuStore.load(this);
      if(retain){if(!mode.equals(saved.spec.mode))throw new IOException("Retained CPU record differs");}
      else GeckoCpuStore.save(this,saved.identity,saved.revision,GeckoCpuSpec.of(mode));
      if(staleUser){
        File profile=new File(getNoBackupFilesDir(),"gecko-browser"),preferences=new File(profile,"prefs.js");
        if(!profile.isDirectory()||java.nio.file.Files.isSymbolicLink(profile.toPath())||java.nio.file.Files.isSymbolicLink(preferences.toPath())||preferences.length()>4*1024*1024)throw new IOException("StaleUserFixtureUnavailable");
        try(FileOutputStream out=new FileOutputStream(preferences,true)){out.write("\nuser_pref(\"dom.maxHardwareConcurrency\", 2);\n".getBytes(StandardCharsets.US_ASCII));}
      }
    }catch(Throwable error){seedError[0]=error;}},"cpu-acceptance-desired-writer");seed.start();seed.join(8000);if(seed.isAlive()||seedError[0]!=null)throw new IOException("Desired record seed failed",seedError[0]);
    ChatSession.browserFactory=(context,owner)->new ObservedGecko(context,owner);getIntent().putExtra("legacyChat",true);
    super.onCreate(null);deadline=SystemClock.elapsedRealtime()+120000;stage="production-cold-bootstrap";publish();poll.post(this::tick);
  }catch(Throwable error){fail(error);}}
  @Override protected void onNewIntent(Intent next){
    try{
      boolean template=next.getBooleanExtra("templateApply",false),resample=next.getBooleanExtra("resample",false);
      String fresh=next.getStringExtra("caseNonce"),requested=next.getStringExtra("cpuMode");boolean nextRfp=next.getBooleanExtra("rfp",false);
      if(!terminal||session==null||remote==null||(!template&&!resample)||template&&resample||!run.equals(next.getStringExtra("runNonce"))
          ||!build.getString("sourceCommit").equals(next.getStringExtra("sourceCommit"))||fresh==null||!fresh.matches("[0-9a-f]{32}")||fresh.equals(invocation)
          ||!mode.equals(requested)||Profiles.slot(this)!=slot||!template&&nextRfp!=rfp)throw new SecurityException("Same runtime resample binding differs");
      super.onNewIntent(next);setIntent(next);invocation=fresh;rfp=nextRfp;retain=false;staleUser=false;terminal=false;failure="";
      started=located=stopped=loadError=currentOwned=false;observerBusy=false;targetDispatched=false;host=new JSONObject();while(events.length()>0)events.remove(events.length()-1);
      target="https://fp-a.pocketchat.test/cpu/slot"+slot+"/page?run="+run+"&case="+invocation;
      identityApplyInvoked=template;identityApplyCompleted=false;templatePolicyBefore=remote.identityPolicyRevision;
      deadline=SystemClock.elapsedRealtime()+120000;stage=template?"normal-template-apply":"same-runtime-resample";publish();
      if(template)session.identity.apply(this,BrowserIdentitySpec.preset(rfp?BrowserIdentitySpec.RFP:BrowserIdentitySpec.MOBILE),error->{
        if(error==null||!error.isEmpty()){fail(new IOException("NormalTemplateApplyFailed"));return;}awaitTemplate();
      });else{targetDispatched=true;session.browse(target,"CPU 原生观察");poll.post(this::tick);}
    }catch(Throwable error){fail(error);}
  }
  void awaitTemplate(){if(terminal)return;try{
    if(SystemClock.elapsedRealtime()>deadline)throw new IOException("NormalTemplateApplyTimeout");
    if(!session.identityApplicationPending&&!DeferredBrowserSettings.pending(session)&&session.privacy.level()==(rfp?2:1)
        &&remote.metadata.policyAcknowledged&&remote.nativeProtection.confirmed()&&remote.identityPolicyRevision>templatePolicyBefore){
      identityApplyCompleted=true;targetDispatched=true;session.browse(target,"模板应用后的 CPU 原生观察");poll.post(this::tick);return;
    }
    poll.postDelayed(this::awaitTemplate,100);
  }catch(Throwable error){fail(error);}}
  final class ObservedGecko extends GeckoWebView {
    ObservedGecko(Context context,ChatSession owner){super(context,owner);}
    @Override GeckoSession newSession(){
      runtime.getSettings().setEnterpriseRootsEnabled(true);enterpriseRoots=runtime.getSettings().getEnterpriseRootsEnabled();
      GeckoSession sdk=super.newSession();GeckoSession.ProgressDelegate progress=sdk.getProgressDelegate();
      sdk.setProgressDelegate(new GeckoSession.ProgressDelegate(){
        public void onPageStart(GeckoSession s,String url){currentOwned=target.equals(url);if(currentOwned)started=true;event("start",currentOwned,null,null,null);progress.onPageStart(s,url);}
        public void onPageStop(GeckoSession s,boolean success){event("stop",currentOwned,success,null,null);if(currentOwned&&started&&located&&success)stopped=true;progress.onPageStop(s,success);}
        public void onProgressChange(GeckoSession s,int value){progress.onProgressChange(s,value);}
        public void onSessionStateChange(GeckoSession s,GeckoSession.SessionState saved){progress.onSessionStateChange(s,saved);}
        public void onSecurityChange(GeckoSession s,SecurityInformation info){progress.onSecurityChange(s,info);try{
          if(!"fp-a.pocketchat.test".equals(info.host))return;
          String leaf=info.certificate==null?"":BrowserFingerprintFixture.sha(info.certificate.getEncoded());
          tls=J.obj("isSecure",info.isSecure,"isException",info.isException,"leafSha256",leaf,"enterpriseRootsReadback",enterpriseRoots);
          if(!info.isSecure||info.isException||!expectedLeaf.equals(leaf))fail(new SecurityException("ControlledTlsMismatch"));
        }catch(Exception error){fail(error);}}
      });
      GeckoSession.NavigationDelegate navigation=sdk.getNavigationDelegate();
      sdk.setNavigationDelegate(new GeckoSession.NavigationDelegate(){
        public GeckoResult<AllowOrDeny> onLoadRequest(GeckoSession s,LoadRequest request){return navigation.onLoadRequest(s,request);}
        public GeckoResult<AllowOrDeny> onSubframeLoadRequest(GeckoSession s,LoadRequest request){return navigation.onSubframeLoadRequest(s,request);}
        public void onLocationChange(GeckoSession s,String url,List<GeckoSession.PermissionDelegate.ContentPermission> permissions,Boolean gesture){if(target.equals(url))located=true;event("location",target.equals(url),null,null,null);navigation.onLocationChange(s,url,permissions,gesture);}
        public void onCanGoBack(GeckoSession s,boolean value){navigation.onCanGoBack(s,value);}
        public void onCanGoForward(GeckoSession s,boolean value){navigation.onCanGoForward(s,value);}
        public GeckoResult<GeckoSession> onNewSession(GeckoSession s,String url){return navigation.onNewSession(s,url);}
        public GeckoResult<String> onLoadError(GeckoSession s,String url,WebRequestError error){if(target.equals(url))loadError=true;event("load-error",target.equals(url),null,error.category,error.code);return navigation.onLoadError(s,url,error);}
      });return sdk;
    }
  }
  void event(String name,boolean owned,Boolean success,Integer category,Integer code){if(events.length()<128)events.put(J.obj("event",name,"targetOwned",owned,"success",success==null?JSONObject.NULL:success,"errorCategory",category==null?JSONObject.NULL:category,"errorCode",code==null?JSONObject.NULL:code,"nativeUrlAvailable",!"stop".equals(name)));}
  void tick(){if(terminal)return;try{
    if(SystemClock.elapsedRealtime()>deadline)throw new IOException("WorkloadTimeout");
    if(loadError)throw new IOException("OwnedTargetLoadError");
    if(session!=null&&remote instanceof ObservedGecko&&remote.ready&&session.networkReady&&!session.connecting){
      JSONObject cpu=session.cpu.status();if("failed".equals(cpu.optString("state")))throw new IOException("ProductionCpuFailed");
      // Production may first restore the preserved SDK checkpoint's older URL.
      // Keep that checkpoint/profile/SW intact and use the ordinary browse path
      // once admission is ready to request this fresh bound observation case.
      if(!targetDispatched){targetDispatched=true;if(!target.equals(remote.getUrl()))session.browse(target,"CPU 冷启动后的原生观察");}
      if(!observerBusy){observerBusy=true;final String observedCase=invocation;observer.execute(()->{JSONObject value=null;try{
        URL endpoint=new URL("http://127.0.0.1:"+PORT+"/__cpu-evidence?run="+run+"&case="+observedCase);
        HttpURLConnection connection=(HttpURLConnection)endpoint.openConnection(Proxy.NO_PROXY);connection.setConnectTimeout(2000);connection.setReadTimeout(2000);connection.setUseCaches(false);
        try{if(connection.getResponseCode()==200)try(InputStream in=connection.getInputStream()){value=new JSONObject(new String(BrowserFingerprintFixture.read(in,65536),StandardCharsets.UTF_8));}}finally{connection.disconnect();}
      }catch(Exception ignored){}final JSONObject actual=value;poll.post(()->{if(!observedCase.equals(invocation)||terminal)return;observerBusy=false;if(actual!=null&&invocation.equals(actual.optJSONObject("binding")==null?"":actual.optJSONObject("binding").optString("caseNonce")))host=actual;});});}
      JSONArray rows=host.optJSONArray("observations");
      if(rows!=null&&rows.length()==5&&started&&located&&stopped&&tls.optBoolean("isSecure")&&!tls.optBoolean("isException",true)&&target.equals(remote.getUrl())&&"ready".equals(cpu.optString("state"))&&cpu.optBoolean("nativeSettingReadback")&&cpu.optBoolean("startupReconciled")&&cpu.opt("rfpPriority") instanceof Boolean&&cpu.getBoolean("rfpPriority")==rfp){
        for(int i=0;i<rows.length();i++){JSONObject row=rows.getJSONObject(i);if(!"observed".equals(row.getString("status")))throw new IOException("WorkerContextUnavailable");}
        terminal=true;stage="complete";publish();return;
      }
    }
    publish();poll.postDelayed(this::tick,100);
  }catch(Throwable error){fail(error);}}
  void fail(Throwable error){if(terminal)return;terminal=true;stage="failed";failure=error instanceof IOException&&Arrays.asList("WorkloadTimeout","OwnedTargetLoadError","ProductionCpuFailed","WorkerContextUnavailable").contains(error.getMessage())?error.getMessage():error.getClass().getSimpleName();try{publish();}catch(Exception ignored){}}
  void publish()throws Exception{if(build==null)return;
    JSONObject cpu=session==null?new JSONObject():session.cpu.status(),runtime=remote==null?new JSONObject():remote.nativeRuntimeCapabilities().optJSONObject("cpuPolicy");
    JSONObject report=J.obj("schema",1,"fixtureType","gecko-production-cpu-v1","status",terminal?(failure.isEmpty()?"passed":"failed"):"running","stage",stage,"failure",failure,"diagnosticOnly",true,"releaseAcceptance",false,"sourceCommit",build.getString("sourceCommit"),"sourceTree",build.getString("sourceTree"),"runNonce",run,"caseNonce",invocation,"slot",slot,"mode",mode,"rfpRequested",rfp,"retainedProfile",retain,"staleUserPrefSeeded",staleUser,"identityApplyInvoked",identityApplyInvoked,"identityApplyCompleted",identityApplyCompleted,"identityPolicyRevision",remote==null?0:remote.identityPolicyRevision,"identityPolicyBefore",templatePolicyBefore,"buildIdentity",build,"process",J.obj("pid",android.os.Process.myPid(),"uid",android.os.Process.myUid(),"name",android.app.Application.getProcessName()),"tls",tls,"cpuPolicy",cpu,"runtimeCpuPolicy",runtime==null?new JSONObject():runtime,"navigation",J.obj("targetStarted",started,"targetLocation",located,"targetStopSuccessful",stopped,"loadError",loadError,"targetPath","/cpu/slot"+slot+"/page"),"nativeEvents",events,"observations",host.optJSONArray("observations")==null?new JSONArray():host.getJSONArray("observations"),"actualAndroidExecution",true,"actualGeckoExecution",remote!=null&&remote.runtime!=null,"productionChatSession",session!=null&&session.web==remote&&remote instanceof ObservedGecko,"productionCpuBootstrap",cpu.optBoolean("nativeSettingReadback")&&cpu.optBoolean("startupReconciled"),"navigatorGetterOverrideUsed",false,"debuggingEndpointUsed",false,"workerCoverageVerified",false,"fingerprintProtectionVerified",false);
    byte[] raw=(report.toString()+"\n").getBytes(StandardCharsets.UTF_8);if(raw.length>262144)throw new IOException("ReportBound");BrowserFingerprintIntegrationActivity.write(this,"cpu-acceptance-"+invocation+".json",report);
  }
  @Override protected void onDestroy(){poll.removeCallbacksAndMessages(null);observer.shutdownNow();super.onDestroy();}
  public static final class Profile1 extends GeckoCpuAcceptanceActivity {}
  public static final class Profile2 extends GeckoCpuAcceptanceActivity {}
}
