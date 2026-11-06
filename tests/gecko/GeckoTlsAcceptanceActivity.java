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

/** Integration-only real MainActivity/ChatSession TLS cold admission and wire workload. */
public class GeckoTlsAcceptanceActivity extends MainActivity {
  static final int PORT=18786;
  final Handler poll=new Handler(Looper.getMainLooper());
  final ExecutorService observer=Executors.newSingleThreadExecutor();
  final JSONArray events=new JSONArray();
  JSONObject manualScope=new JSONObject();
  JSONObject build,security=new JSONObject(),host=new JSONObject(),storage=new JSONObject(),seed=new JSONObject(),uiBefore=new JSONObject(),uiAfter=new JSONObject();
  String run,invocation,mode,target,leaf,stage="seed",failure="";int slot,peerPort,loadCalls,starts,stops,successfulStops,errorCategory=-1,errorCode=-1;
  boolean rfp,retain,staleUser,service,expectSuccess,terminal,started,located,titleMatched,targetRequested,targetDispatched,admitted,observerBusy,enterpriseRoots,uiRequested,uiCompleted;
  long deadline;
  @Override public void onCreate(Bundle state){try{
    if(!"local.pocketchat.test".equals(getPackageName()))throw new SecurityException("IntegrationOnly");
    run=getIntent().getStringExtra("runNonce");build=IntegrationBuildIdentity.read(this);slot=Profiles.slot(this);bind(getIntent(),false);
    final Throwable[] error={null};Thread writer=new Thread(()->{try{
      manualScope=GeckoTlsFixtureScopes.admitCase(this,build.getString("sourceCommit"),run,slot,getClass().getName(),invocation,null);
      pauseFixtureUpdateChecks(this);
      GeckoCpuProfile.Storage anchor=GeckoCpuProfile.storage(this);storage=anchor.evidence;
      ProfileCatalog.get(this).created(slot);BrowserFingerprintIntegrationActivity.configure(this,PORT,target);
      getSharedPreferences("chat",0).edit().putInt("privacyLevel",rfp?2:1).putBoolean("pageMode",true).commit();
      EnvironmentSpecRepository repository=new EnvironmentSpecRepository(this);EnvironmentSpec old=repository.load();JSONObject browser=BrowserIdentitySpec.preset(rfp?BrowserIdentitySpec.RFP:BrowserIdentitySpec.MOBILE).json();
      if(!old.desired().browser().toString().equals(browser.toString()))repository.updateDesired(old.identity,old.desiredRevision,new EnvironmentSpec.Configuration(browser,old.desired().network));
      GeckoTlsStore.State saved=GeckoTlsStore.load(this);
      if(retain){if(!saved.spec.mode.equals(mode))throw new IOException("RetainedDesiredDiffers");}
      else GeckoTlsStore.save(this,saved.identity,saved.revision,GeckoTlsSpec.of(mode));
      if(staleUser){
        File profile=new File(anchor.root,"gecko-browser"),prefs=new File(profile,"prefs.js");
        if(!profile.isDirectory()||java.nio.file.Files.isSymbolicLink(profile.toPath())||java.nio.file.Files.isSymbolicLink(prefs.toPath())||!prefs.isFile()||prefs.length()>4*1024*1024)throw new IOException("StaleUserSeedUnavailable");
        byte[] original=java.nio.file.Files.readAllBytes(prefs.toPath()),other=GeckoTlsProfile.withoutTls(original);
        byte[] appended="\nuser_pref(\"security.tls.version.min\", 4);\nuser_pref(\"security.tls.version.max\", 4);\n".getBytes(StandardCharsets.US_ASCII);
        try(FileOutputStream out=new FileOutputStream(prefs)){out.write(other);out.write(appended);out.getFD().sync();}
        byte[] actual=java.nio.file.Files.readAllBytes(prefs.toPath());
        // The one separator newline is test setup, not a native/production ACK.
        byte[] expectedOther=Arrays.copyOf(other,other.length+1);expectedOther[other.length]='\n';
        seed=J.obj("performed",true,"min",4,"max",4,"otherBytesPreserved",Arrays.equals(GeckoTlsProfile.withoutTls(actual),expectedOther),"originalBytes",original.length,"seededBytes",actual.length,"originalSha256",BrowserFingerprintFixture.sha(original),"otherSha256",BrowserFingerprintFixture.sha(other),"testSetupOnly",true);
        if(!seed.getBoolean("otherBytesPreserved"))throw new IOException("SeedOtherBytesChanged");
      }
    }catch(Throwable unavailable){error[0]=unavailable;}},"tls-product-desired-writer");writer.start();writer.join(8000);
    if(writer.isAlive()||error[0]!=null)throw new IOException("DesiredSeedFailed",error[0]);
    ChatSession.browserFactory=(context,owner)->new ObservedGecko(context,owner);getIntent().putExtra("legacyChat",true);
    super.onCreate(null);stage="production-cold-bootstrap";deadline=SystemClock.elapsedRealtime()+120000;publish();poll.post(this::tick);
  }catch(Throwable error){fail(error);}}
  /** Closed-world TLS setup only; production and other update fixtures retain defaults. */
  static android.app.job.JobScheduler fixtureUpdateJobs(Context context)throws IOException{
    String owner=context.getClass().getName();
    if(!"local.pocketchat.test".equals(context.getPackageName())||!Arrays.asList("local.pocketchat.GeckoTlsAcceptanceActivity$Profile1","local.pocketchat.GeckoTlsAcceptanceActivity$Profile2","local.pocketchat.GeckoTlsCpuIpComboIntegrationActivity").contains(owner))throw new SecurityException("Exact TLS fixture update scope required");
    Object service=context.getSystemService(Context.JOB_SCHEDULER_SERVICE);
    if(!(service instanceof android.app.job.JobScheduler))throw new IOException("Fixture update scheduler unavailable");
    return (android.app.job.JobScheduler)service;
  }
  static void pauseFixtureUpdateChecks(Context context)throws IOException{
    if(Looper.myLooper()==Looper.getMainLooper())throw new IOException("Fixture update setup requires its bounded writer");
    android.app.job.JobScheduler jobs=fixtureUpdateJobs(context);
    AppSettings.put(context,"updateAutoCheck","false");
    if(!"false".equals(AppSettings.get(context,"updateAutoCheck","missing")))throw new IOException("Fixture update setting did not persist");
    jobs.cancel(AppUpdates.ON_OPEN);jobs.cancel(AppUpdates.PERIODIC);
    requireFixtureUpdateChecks(context);
  }
  static void requireFixtureUpdateChecks(Context context)throws IOException{
    android.app.job.JobScheduler jobs=fixtureUpdateJobs(context);
    if(!"false".equals(AppSettings.get(context,"updateAutoCheck","missing"))||jobs.getPendingJob(AppUpdates.ON_OPEN)!=null||jobs.getPendingJob(AppUpdates.PERIODIC)!=null)throw new IOException("Fixture automatic update work is not paused");
  }
  @Override protected void onResume(){
    try{requireFixtureUpdateChecks(this);}catch(Throwable error){if(terminal&&failure.isEmpty())terminal=false;fail(error);throw new IllegalStateException("TLS fixture update prerequisite failed",error);}
    super.onResume();
  }
  void bind(Intent intent,boolean resumed)throws Exception{
    String fresh=intent.getStringExtra("caseNonce"),source=intent.getStringExtra("sourceCommit"),nextMode=intent.getStringExtra("tlsMode");
    int port=intent.getIntExtra("peerPort",-1);String nextLeaf=intent.getStringExtra("expectedLeafSha256");
    if(run==null||!run.matches("[0-9a-f]{32}")||!run.equals(intent.getStringExtra("runNonce"))||fresh==null||!fresh.matches("[0-9a-f]{32}")||fresh.equals(invocation)
        ||source==null||!source.equals(build.getString("sourceCommit"))||!Arrays.asList("default","tls13").contains(nextMode)||port<42000||port>=62000||slot<1||slot>2||nextLeaf==null||!nextLeaf.matches("[0-9a-f]{64}"))throw new SecurityException("ExactCaseBinding");
    if(resumed&&(!mode.equals(nextMode)||intent.getBooleanExtra("rfp",false)!=rfp||!leaf.equals(nextLeaf)))throw new SecurityException("ImmutableBootDiffers");
    invocation=fresh;mode=nextMode;peerPort=port;leaf=nextLeaf;rfp=intent.getBooleanExtra("rfp",false);retain=intent.getBooleanExtra("retain",false);staleUser=intent.getBooleanExtra("staleUser",false);service=intent.getBooleanExtra("service",false);expectSuccess=intent.getBooleanExtra("expectSuccess",false);uiRequested=intent.getBooleanExtra("saveDefault",false);
    if(!resumed&&uiRequested)throw new SecurityException("PendingSaveRequiresExistingRuntime");
    target="https://fp-a.pocketchat.test:"+peerPort+"/tls-product/slot"+slot+"/page?run="+run+"&case="+invocation+"&source="+source;
  }
  @Override protected void onNewIntent(Intent intent){try{
    if(!terminal||session==null||remote==null||!intent.getBooleanExtra("resample",false)||Profiles.slot(this)!=slot)throw new SecurityException("LiveResampleOnly");
    bind(intent,true);
    Future<JSONObject> scoped=observer.submit(()->{JSONObject own=GeckoTlsFixtureScopes.admitCase(this,build.getString("sourceCommit"),run,slot,getClass().getName(),invocation,manualScope.getString("claimNonce"));pauseFixtureUpdateChecks(this);return own;});
    manualScope=scoped.get(8000,TimeUnit.MILLISECONDS);super.onNewIntent(intent);setIntent(intent);terminal=false;failure="";resetObservation();deadline=SystemClock.elapsedRealtime()+120000;
    if(uiRequested){
      stage="saving-pending-default";GeckoTlsStore.State expected=session.tls.snapshot();uiBefore=taskSnapshot();publish();
      GeckoTlsUi.saveDesired(this,session,expected,GeckoTlsSpec.defaults(),message->{try{
        uiAfter=taskSnapshot();GeckoTlsStore.State actual=session.tls.snapshot();
        if(actual==null||!actual.spec.isDefault()||actual.revision<=expected.revision||!session.tls.status().optBoolean("pendingColdStart")||!uiBefore.toString().equals(uiAfter.toString()))throw new IOException("UiSaveChangedLiveWork");
        uiCompleted=true;dispatch();
      }catch(Throwable error){fail(error);}});
    }else dispatch();
    poll.post(this::tick);
  }catch(Throwable error){fail(error);}}
  void resetObservation(){started=located=titleMatched=targetRequested=targetDispatched=admitted=observerBusy=uiCompleted=false;errorCategory=errorCode=-1;starts=stops=successfulStops=0;security=new JSONObject();host=new JSONObject();seed=new JSONObject();uiBefore=new JSONObject();uiAfter=new JSONObject();while(events.length()>0)events.remove(events.length()-1);}
  JSONObject taskSnapshot()throws Exception{JSONObject policy=session.tls.status();return J.obj("pid",android.os.Process.myPid(),"runtimeNonce",policy.optString("runtimeNonce"),"processNonce",policy.optString("processNonce"),"navigationEpoch",session.navigationEpoch,"connectionEpoch",session.connectionEpoch,"loadCalls",loadCalls,"urlSha256",BrowserFingerprintFixture.sha(remote.getUrl().getBytes(StandardCharsets.UTF_8)),"pendingSha256",BrowserFingerprintFixture.sha((session.pending==null?"null":session.pending.toString()).getBytes(StandardCharsets.UTF_8)),"submitting",session.submitting,"operation",session.operation,"transferActive",session.transferActive,"resourceChoosers",session.resourceChoosers,"resourceFilePreparations",session.resourceFilePreparations,"fileWorkActive",session.fileWorkActive());}
  void dispatch(){if(terminal||targetDispatched)return;stage="owned-target";targetDispatched=true;session.browse(target,"TLS 原生协议与受控网络观察");}
  final class ObservedGecko extends GeckoWebView {
    ObservedGecko(Context context,ChatSession owner){super(context,owner);}
    @Override public void loadUrl(String url){loadCalls++;super.loadUrl(url);}
    @Override GeckoSession newSession(){
      runtime.getSettings().setEnterpriseRootsEnabled(true);enterpriseRoots=runtime.getSettings().getEnterpriseRootsEnabled();
      GeckoSession sdk=super.newSession();GeckoSession.ProgressDelegate progress=sdk.getProgressDelegate();
      sdk.setProgressDelegate(new GeckoSession.ProgressDelegate(){
        public void onPageStart(GeckoSession s,String url){if(target.equals(url)){started=true;starts++;}event("start",target.equals(url),null,null);progress.onPageStart(s,url);}
        public void onPageStop(GeckoSession s,boolean success){stops++;if(success)successfulStops++;event("stop",false,null,null);progress.onPageStop(s,success);}
        public void onProgressChange(GeckoSession s,int value){progress.onProgressChange(s,value);}
        public void onSessionStateChange(GeckoSession s,GeckoSession.SessionState state){progress.onSessionStateChange(s,state);}
        public void onSecurityChange(GeckoSession s,SecurityInformation info){progress.onSecurityChange(s,info);try{
          if(s!=current||!started||!"fp-a.pocketchat.test".equals(info.host))return;
          String actual=info.certificate==null?"":BrowserFingerprintFixture.sha(info.certificate.getEncoded());
          security=J.obj("isSecure",info.isSecure,"isException",info.isException,"host",info.host,"leafSha256",actual,"enterpriseRootsReadback",enterpriseRoots,"nativeUrlAvailable",false);
          if(info.isException||info.isSecure&&!leaf.equals(actual))fail(new SecurityException("ControlledLeafMismatch"));
        }catch(Exception error){fail(error);}}
      });
      GeckoSession.NavigationDelegate navigation=sdk.getNavigationDelegate();
      sdk.setNavigationDelegate(new GeckoSession.NavigationDelegate(){
        public GeckoResult<AllowOrDeny> onLoadRequest(GeckoSession s,LoadRequest request){
          boolean owned=target.equals(request.uri);if(owned){targetRequested=true;boolean ready=owner.tls.readyFor(runtime)&&owner.cpu.readyFor(runtime)&&protectionAllowsNetwork()&&owner.guard.allowed();admitted|=ready;event("request",true,null,ready);}
          return navigation.onLoadRequest(s,request);
        }
        public GeckoResult<AllowOrDeny> onSubframeLoadRequest(GeckoSession s,LoadRequest request){return navigation.onSubframeLoadRequest(s,request);}
        public void onLocationChange(GeckoSession s,String url,List<GeckoSession.PermissionDelegate.ContentPermission> permissions,Boolean gesture){if(target.equals(url))located=true;event("location",target.equals(url),null,null);navigation.onLocationChange(s,url,permissions,gesture);}
        public void onCanGoBack(GeckoSession s,boolean value){navigation.onCanGoBack(s,value);}
        public void onCanGoForward(GeckoSession s,boolean value){navigation.onCanGoForward(s,value);}
        public GeckoResult<GeckoSession> onNewSession(GeckoSession s,String url){return navigation.onNewSession(s,url);}
        public GeckoResult<String> onLoadError(GeckoSession s,String url,WebRequestError error){if(target.equals(url)){errorCategory=error.category;errorCode=error.code;}event("error",target.equals(url),error.category+":"+error.code,null);return navigation.onLoadError(s,url,error);}
      });
      GeckoSession.ContentDelegate content=sdk.getContentDelegate();sdk.setContentDelegate(new GeckoSession.ContentDelegate(){
        public void onTitleChange(GeckoSession s,String title){content.onTitleChange(s,title);if(s==current&&("TLS product:"+invocation).equals(title))titleMatched=true;}
        public void onCloseRequest(GeckoSession s){content.onCloseRequest(s);}public void onCrash(GeckoSession s){content.onCrash(s);}public void onKill(GeckoSession s){content.onKill(s);}public void onFirstContentfulPaint(GeckoSession s){content.onFirstContentfulPaint(s);}public void onExternalResponse(GeckoSession s,WebResponse response){content.onExternalResponse(s,response);}
      });return sdk;
    }
  }
  void event(String name,boolean owned,String error,Boolean ready){if(events.length()<128)events.put(J.obj("event",name,"targetOwned",owned,"error",error==null?JSONObject.NULL:error,"admissionReady",ready==null?JSONObject.NULL:ready,"nativeUrlAvailable",!"stop".equals(name)));}
  void tick(){if(terminal)return;try{
    if(SystemClock.elapsedRealtime()>deadline)throw new IOException("WorkloadTimeout");
    if(session!=null&&remote instanceof ObservedGecko&&remote.ready&&session.networkReady&&!session.connecting){
      JSONObject policy=session.tls.status();if("failed".equals(policy.optString("state")))throw new IOException("ProductionTlsFailed");
      boolean nativeReady="ready".equals(policy.optString("state"))&&policy.optBoolean("nativeSettingReadback")&&policy.optBoolean("startupReconciled")&&policy.opt("rfpPriority") instanceof Boolean&&policy.getBoolean("rfpPriority")==rfp;
      if(nativeReady&&(!uiRequested||uiCompleted)&&!targetRequested&&!targetDispatched)dispatch();
      if(!observerBusy){observerBusy=true;final String observed=invocation;observer.execute(()->{JSONObject value=null;try{
        HttpURLConnection connection=(HttpURLConnection)new URL("http://127.0.0.1:"+PORT+"/__tls_product_evidence?run="+run+"&case="+observed).openConnection(Proxy.NO_PROXY);connection.setConnectTimeout(2000);connection.setReadTimeout(2000);connection.setUseCaches(false);
        try{if(connection.getResponseCode()==200)try(InputStream in=connection.getInputStream()){value=new JSONObject(new String(BrowserFingerprintFixture.read(in,65536),StandardCharsets.UTF_8));}}finally{connection.disconnect();}
      }catch(Exception ignored){}final JSONObject result=value;poll.post(()->{if(terminal||!observed.equals(invocation))return;observerBusy=false;if(result!=null&&observed.equals(result.optString("caseNonce")))host=result;});});}
      boolean success=started&&located&&titleMatched&&target.equals(remote.getUrl())&&security.optBoolean("isSecure")&&!security.optBoolean("isException",true)&&leaf.equals(security.optString("leafSha256"))&&(!service||host.optJSONObject("serviceObservation")!=null);
      boolean rejected=errorCategory==WebRequestError.ERROR_CATEGORY_SECURITY&&errorCode==WebRequestError.ERROR_SECURITY_SSL;
      if(errorCategory>=0&&expectSuccess)throw new IOException("OwnedTargetLoadError");
      if(nativeReady&&admitted&&(!uiRequested||uiCompleted)&&(expectSuccess?success:rejected)){terminal=true;stage="complete";publish();return;}
    }
    publish();poll.postDelayed(this::tick,100);
  }catch(Throwable error){fail(error);}}
  void fail(Throwable error){if(terminal)return;terminal=true;stage="failed";String value=error.getMessage();failure=error instanceof IOException&&value!=null&&Arrays.asList("WorkloadTimeout","ProductionTlsFailed","OwnedTargetLoadError","UiSaveChangedLiveWork").contains(value)?value:error.getClass().getSimpleName();try{publish();}catch(Exception ignored){}}
  void publish()throws Exception{if(build==null||invocation==null)return;
    JSONObject policy=session==null?new JSONObject():session.tls.status(),cpu=session==null?new JSONObject():session.cpu.status();
    JSONObject report=J.obj("schema",1,"fixtureType","gecko-production-tls-v1","status",terminal?(failure.isEmpty()?"passed":"failed"):"running","stage",stage,"failure",failure,"diagnosticOnly",true,"releaseAcceptance",false,"sourceCommit",build.getString("sourceCommit"),"sourceTree",build.getString("sourceTree"),"runNonce",run,"caseNonce",invocation,"slot",slot,"mode",mode,"peerPort",peerPort,"rfpRequested",rfp,"retainedProfile",retain,"staleUserPrefSeeded",staleUser,"serviceRequested",service,"expectedSuccess",expectSuccess,"target",target,"buildIdentity",build,"process",J.obj("pid",android.os.Process.myPid(),"uid",android.os.Process.myUid(),"name",android.app.Application.getProcessName()),"tlsPolicy",policy,"cpuPolicy",cpu,"storagePathEvidence",storage,"manualScope",manualScope,"startupPreparation",remote==null||remote.tlsBoot==null?new JSONObject():remote.tlsBoot.preparation.evidence(),"seed",seed,"security",security,"navigation",J.obj("targetStarted",started,"targetLocation",located,"titleMatched",titleMatched,"targetRequestObserved",targetRequested,"productionAdmissionReady",admitted,"targetError",errorCategory>=0,"errorCategory",errorCategory,"errorCode",errorCode,"nativeErrorUrlMatched",errorCategory>=0,"nativeStopOwnershipVerified",false,"nativeSecurityUrlOwnershipVerified",false,"stopCallbacks",stops,"successfulStopCallbacks",successfulStops),"nativeEvents",events,"uiSaveInvoked",uiRequested,"uiSaveCompleted",uiCompleted,"uiBefore",uiBefore,"uiAfter",uiAfter,"serviceObservation",host.optJSONObject("serviceObservation")==null?JSONObject.NULL:host.getJSONObject("serviceObservation"),"actualAndroidExecution",true,"actualGeckoExecution",remote!=null&&remote.runtime!=null,"productionChatSession",session!=null&&session.web==remote&&remote instanceof ObservedGecko,"productionTlsBootstrap",policy.optBoolean("nativeSettingReadback")&&policy.optBoolean("startupReconciled"),"javascriptTlsOverrideUsed",false,"debuggingEndpointUsed",false,"nativeSettingReadbackIsWireProof",false,"workerCoverageVerified",false,"serviceWorkerCoverageVerified",false,"fullTlsFingerprintEmulation",false,"quicWireVerified",false);
    if((report.toString()+"\n").getBytes(StandardCharsets.UTF_8).length>262144)throw new IOException("ReportBound");BrowserFingerprintIntegrationActivity.write(this,"tls-acceptance-"+invocation+".json",report);
  }
  @Override protected void onDestroy(){poll.removeCallbacksAndMessages(null);observer.shutdownNow();super.onDestroy();}
  public static final class Profile1 extends GeckoTlsAcceptanceActivity {}
  public static final class Profile2 extends GeckoTlsAcceptanceActivity {}
}
