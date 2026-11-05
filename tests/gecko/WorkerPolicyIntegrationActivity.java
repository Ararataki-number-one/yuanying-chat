package local.pocketchat;

import android.content.Context;
import android.os.*;
import android.view.inputmethod.EditorInfo;
import android.webkit.WebView;
import java.io.IOException;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.Consumer;
import org.json.*;

/** Real production policy saves, native SW network readback and HTTPS Worker execution.
 * Only synthetic fixed-host metadata is exported; no privileged production endpoint. */
public final class WorkerPolicyIntegrationActivity extends BrowserActivity {
  static final String URL="https://"+BrowserFingerprintFixture.A+"/worker-document";
  final Handler poll=new Handler(Looper.getMainLooper());final ExecutorService evidence=Executors.newSingleThreadExecutor();
  final JSONArray checks=new JSONArray(),samples=new JSONArray(),nativeSetups=new JSONArray();
  BrowserFingerprintFixture fixture;JSONObject build,staleProof=new JSONObject(),routeProof=new JSONObject(),currentSelfTest=new JSONObject();
  String invocation,phase="initial",failure="";boolean done;long deadline,staleOperation=-1;int staleCallbacks;
  ChromiumFingerprintStore.State original;ChromiumFingerprintStore.Binding originalBinding;Tab originalTab;WebView originalWeb;long originalToken;
  String previousDocument="";
  final CountDownLatch staleRelease=new CountDownLatch(1);
  interface Ready{boolean get()throws Exception;}interface Step{void run()throws Exception;}

  @Override public void onCreate(Bundle state){try{
    BrowserFingerprintIntegrationActivity.validateIntent(this);invocation=getIntent().getStringExtra("runNonce");build=IntegrationBuildIdentity.read(this);
    if(!build.getString("sourceCommit").equals(getIntent().getStringExtra("sourceCommit")))throw new SecurityException("Worker fixture source differs");
    fixture=new BrowserFingerprintFixture(this,"chromium");fixture.start();BrowserFingerprintIntegrationActivity.configure(this,fixture.port(),URL+"?phase=allow");
    getIntent().putExtra("url",URL+"?phase=allow");super.onCreate(null);deadline=SystemClock.elapsedRealtime()+90000;publish(false);
    await("initial native browser",this::ready,()->sample("allow","",true,this::allowed));
  }catch(Throwable error){fail(error);}}
  boolean ready(){return !done&&runtime!=null&&runtime.allowed()&&fingerprintStateReady&&!fingerprintLoading&&!fingerprintSaving&&selected!=null&&web()!=null&&selected.fingerprint!=null&&selected.fingerprintReady&&selected.fingerprintBindingReady&&!selected.loading&&!selected.failed&&web().getProgress()==100&&web().getUrl()!=null&&web().getUrl().startsWith(URL)&&fixture.accepted.get()>0;}
  void await(String name,Ready condition,Step next){if(done)return;try{if(condition.get()){next.run();return;}if(SystemClock.elapsedRealtime()>deadline)throw new IllegalStateException("Worker deadline: "+name);poll.postDelayed(()->await(name,condition,next),75);}catch(Throwable error){fail(error);}}
  void stage(String value)throws Exception{phase=value;deadline=SystemClock.elapsedRealtime()+45000;publish(false);}
  void check(String id,boolean pass)throws Exception{checks.put(J.obj("id",id,"pass",pass));if(!pass)throw new AssertionError(id);}
  void sample(String expected,String previous,boolean retain,Consumer<JSONObject> next){
    if(done)return;if(SystemClock.elapsedRealtime()>deadline){fail(new IllegalStateException("Worker first-inline "+expected+" deadline"));return;}
    if(!ready()){poll.postDelayed(()->sample(expected,previous,retain,next),75);return;}
    WebView view=web();view.evaluateJavascript("JSON.stringify({page:window.__workerPolicyPage||{},frames:window.__workerPolicyFrames||[]})",raw->{try{
      if(view!=web()||!ready()){poll.postDelayed(()->sample(expected,previous,retain,next),75);return;}
      Object decoded=new JSONTokener(raw).nextValue();if(!(decoded instanceof String))throw new IllegalStateException("Worker page result missing");JSONObject value=new JSONObject((String)decoded),page=value.getJSONObject("page");JSONArray frames=value.getJSONArray("frames");
      if(!page.optBoolean("complete")||!expected.equals(page.optString("phase"))||page.optString("documentId").equals(previous)||frames.length()!=2){poll.postDelayed(()->sample(expected,previous,retain,next),75);return;}
      if(page.has("error"))throw new IllegalStateException("Synthetic Worker page failed: "+page.getString("error"));
      for(int i=0;i<frames.length();i++)if(!frames.getJSONObject(i).optBoolean("complete")||frames.getJSONObject(i).has("error"))throw new IllegalStateException("Synthetic Worker frame failed");
      value.put("phase",expected);value.put("desiredRevision",fingerprintState.revision);value.put("nativeWorkerPolicy",runtime.workerPolicyReceipt());
      value.put("environmentIdentity",fingerprintState.identity.json());value.put("binding",J.obj("providerPackage",selected.fingerprintProviderPackage,"providerVersion",selected.fingerprintProviderVersion,"runtimeEpoch",fingerprintRuntimeEpoch,"surfaceGeneration",selected.surfaceGeneration,"navigationGeneration",selected.generation));
      if(retain)samples.put(value);next.accept(value);
    }catch(Throwable error){fail(error);}});
  }
  boolean workerCases(JSONObject page,boolean restrict)throws Exception{
    JSONObject cases=page.getJSONObject("cases");for(String name:new String[]{"dedicated","module","blob","shared","sharedBlob"}){
      JSONObject row=cases.getJSONObject(name);boolean available=row.getBoolean("available");if(!available){if(!name.startsWith("shared")||row.getBoolean("created")||row.getBoolean("executed")||row.getBoolean("denied"))return false;continue;}
      if(restrict){if(!row.getBoolean("denied")||row.getBoolean("created")||row.getBoolean("executed")||row.getBoolean("networkAllowed"))return false;}
      else if(row.getBoolean("denied")||!row.getBoolean("created")||!row.getBoolean("executed")||!row.getBoolean("networkAllowed")||row.getBoolean("documentGuard")||row.getBoolean("auditAvailable")||row.getString("nativeUserAgent").isEmpty())return false;
    }return cases.getJSONObject("shared").getBoolean("available")==cases.getJSONObject("sharedBlob").getBoolean("available");
  }
  boolean frames(JSONObject value,boolean restrict)throws Exception{
    Set<String> origins=new HashSet<>();JSONArray frames=value.getJSONArray("frames");for(int i=0;i<frames.length();i++){
      JSONObject frame=frames.getJSONObject(i),worker=frame.getJSONObject("cases").getJSONObject("dedicated");origins.add(frame.getString("origin"));
      if(!frame.getBoolean("firstInline")||!frame.getBoolean("documentGuard")||!frame.getBoolean("secure")||!invocation.equals(frame.getString("runNonce"))||!worker.getBoolean("available"))return false;
      if(restrict){if(!worker.getBoolean("denied")||worker.getBoolean("created")||worker.getBoolean("executed"))return false;}
      else if(!worker.getBoolean("executed")||!worker.getBoolean("networkAllowed")||worker.getBoolean("denied"))return false;
    }return origins.equals(new HashSet<>(Arrays.asList("https://"+BrowserFingerprintFixture.A,"https://"+BrowserFingerprintFixture.B)));
  }
  void nativeSetup(String prefix,boolean restrict)throws Exception{
    JSONObject worker=runtime.workerPolicyReceipt(),setup=selected.fingerprint.receipt();Bundle certificate=android.net.http.SslCertificate.saveState(web().getCertificate());byte[] leaf=certificate==null?null:certificate.getByteArray("x509-certificate");
    check(prefix+".native-tls",leaf!=null&&BrowserFingerprintFixture.sha(leaf).equals(fixture.leafSha256));
    check(prefix+".native-switch",worker.getBoolean("confirmed")&&worker.getBoolean("identityBound")&&worker.getBoolean("routeAdmitted")&&worker.getBoolean("nativeReadbackObserved")&&worker.getBoolean("nativeSettingMatches")&&worker.getBoolean("nativeBlockNetworkLoads")==restrict&&worker.getLong("desiredRevision")==fingerprintState.revision&&worker.getString("mode").equals(restrict?"restrict":"allow"));
    setup.put("phase",prefix).put("observedLeafDerSha256",BrowserFingerprintFixture.sha(leaf)).put("workerNetwork",worker).put("desiredRevision",fingerprintState.revision);nativeSetups.put(setup);
  }
  void inspect(String prefix,JSONObject value,boolean restrict)throws Exception{
    JSONObject page=value.getJSONObject("page");check(prefix+".first-inline",page.getBoolean("firstInline")&&page.getBoolean("secure")&&page.getBoolean("documentGuard")&&page.getString("mode").equals(restrict?"restrict":"allow")&&invocation.equals(page.getString("runNonce")));
    check(prefix+".actual-workers",workerCases(page,restrict));check(prefix+".frames-first-inline",frames(value,restrict));nativeSetup(prefix,restrict);
    JSONObject sw=page.getJSONObject("serviceWorker");check(prefix+".service-existing-cache",sw.getBoolean("available")&&sw.getBoolean("existingExecution")&&sw.getBoolean("cacheRead")&&!sw.getBoolean("workerFingerprintProtected"));
    check(prefix+".service-network",sw.getBoolean("networkAllowed")==!restrict);
    check(prefix+".service-registration",sw.getBoolean("registered")==!restrict&&sw.getBoolean("registrationDenied")==restrict);
    previousDocument=page.getString("documentId");
  }
  void allowed(JSONObject value){try{
    check("chromium.production-ui",address.isShown()&&runtime.allowed()&&fingerprintTraffic(selected,web()));check("default.allow-policy",!fingerprintState.spec().has("workers")&&!fingerprintSpec.restrictWorkers());inspect("allow",value,false);
    original=fingerprintState;originalBinding=selected.fingerprintBinding;originalTab=selected;originalWeb=web();originalToken=runtime.workerPolicyGeneration;
    stage("save-restrict");
    // A bounded test-only queue fence makes the old real JS callback arrive
    // while production saveFingerprint has blocked traffic but before CAS can
    // destroy its old WebView. No callback/result is manufactured or replaced.
    fingerprintWorker.execute(()->{try{if(!staleRelease.await(8,TimeUnit.SECONDS))poll.post(()->fail(new IllegalStateException("Actual stale JavaScript callback absent")));}catch(InterruptedException stopped){Thread.currentThread().interrupt();}});
    observeFingerprint();staleOperation=fingerprintObservationGeneration;check("stale.actual-js-dispatched",fingerprintObserving);
    JSONObject desired=ChromiumFingerprintSpec.from(original.spec()).json().put("workers","restrict");saveFingerprint(original,desired,false);
    await("saved restrict surface",()->ready()&&fingerprintState.revision>original.revision&&web()!=originalWeb,()->sample("restrict",previousDocument,true,this::restricted));
  }catch(Throwable error){fail(error);}}
  void restricted(JSONObject value){try{
    check("restrict.save-revision-rebuild",fingerprintState.revision==original.revision+1&&web()!=originalWeb&&fingerprintState.seed.equals(original.seed));inspect("restrict",value,true);
    check("stale.policy-token-rejected",!runtime.confirmWorkerPolicy(originalToken,original.identity,original.revision,false)&&!runtime.workerRequestsAllowed()&&runtime.workerPolicyReceipt().getBoolean("nativeBlockNetworkLoads"));
    await("actual stale JS callback",()->staleCallbacks==1,()->{
      check("stale.actual-js-callback-rejected",staleProof.optBoolean("actualJavaScriptResult")&&staleProof.optBoolean("bindingRejected")&&staleProof.optBoolean("receiptUnchanged")&&staleProof.optBoolean("nativeRemainedBlocked"));
      evidence.execute(()->{try{boolean rejected=false;try{ChromiumFingerprintStore.record(this,original.identity,original.revision,originalBinding,J.obj("workerCreation",J.obj("state","page-observed")));}catch(IOException expected){rejected=true;}final boolean result=rejected;poll.post(()->{try{check("stale.receipt-rejected",result);observeCurrent();}catch(Throwable error){fail(error);}});}catch(Throwable error){poll.post(()->fail(error));}});
    });
  }catch(Throwable error){fail(error);}}
  void observeCurrent()throws Exception{
    stage("current-restrict-selftest");observeFingerprint();await("current restrict observation",()->!fingerprintObserving&&currentRestrictReceipt(),()->{
      check("restrict.current-page-selftest",currentRestrictReceipt());currentSelfTest=new JSONObject(fingerprintReceipt.toString());routeAgain();
    });
  }
  boolean currentRestrictReceipt(){JSONObject fields=fingerprintReceipt.optJSONObject("fields"),row=fields==null?null:fields.optJSONObject("workerCreation"),value=row==null?null:row.optJSONObject("value");return row!=null&&"page-observed".equals(row.optString("state"))&&value!=null&&"restrict".equals(value.optString("mode"))&&fingerprintReceipt.optLong("desiredRevision")==fingerprintState.revision;}
  void routeAgain()throws Exception{
    stage("route-readmission");address.setText(URL+"?phase=restrict-route");address.onEditorAction(EditorInfo.IME_ACTION_GO);
    sample("restrict-route",previousDocument,false,before->{try{
      Object ticket=runtime.routeStamp();String document=before.getJSONObject("page").getString("documentId");WebView previous=web();runtime.changedRoute();
      await("fresh admitted native route",()->ready()&&runtime.routeStamp()!=ticket&&web()!=previous,()->sample("restrict-route",document,true,value->{try{
        check("route.actual-new-ticket",ticket!=null&&runtime.routeStamp()!=null&&runtime.routeStamp()!=ticket&&web()!=previous);inspect("restrict-route",value,true);
        routeProof=J.obj("actualRouteRefresh",true,"newTicketIdentity",true,"newNativeSurface",web()!=previous,"samePolicyRevision",fingerprintState.revision==original.revision+1,"nativeWorkerPolicy",runtime.workerPolicyReceipt());restore();
      }catch(Throwable error){fail(error);}}));
    }catch(Throwable error){fail(error);}});
  }
  void restore()throws Exception{
    stage("save-allow");ChromiumFingerprintStore.State before=fingerprintState;WebView old=web();JSONObject desired=ChromiumFingerprintSpec.from(before.spec()).json().put("workers","allow");saveFingerprint(before,desired,false);
    await("saved restored native surface",()->ready()&&fingerprintState.revision==before.revision+1&&web()!=old,()->sample("restore",previousDocument,true,value->{try{
      check("restore.save-revision-rebuild",fingerprintState.revision==original.revision+2&&web()!=old&&fingerprintState.seed.equals(original.seed));inspect("restore",value,false);
      check("coverage.honest-boundaries",!selected.fingerprint.receipt().getBoolean("workerCoverageVerified")&&!selected.fingerprint.receipt().getBoolean("fingerprintProtectionVerified")&&!runtime.workerPolicyReceipt().getBoolean("existingOrCachedExecutionControlled"));
      done=true;phase="complete";publish(true);
    }catch(Throwable error){fail(error);}}));
  }
  @Override void finishFingerprintObservation(Tab tab,WebView view,ChromiumFingerprintStore.State state,ChromiumFingerprintStore.Binding binding,String url,long operation,JSONObject result,String error){
    boolean rejected=!fingerprintCurrent(tab,view,state,binding);JSONObject before=fingerprintReceipt;super.finishFingerprintObservation(tab,view,state,binding,url,operation,result,error);
    if(operation==staleOperation){staleCallbacks++;staleProof=J.obj("actualJavaScriptResult",result!=null,"bindingRejected",rejected,"receiptUnchanged",before==fingerprintReceipt,"nativeRemainedBlocked",runtime!=null&&!runtime.workerRequestsAllowed()&&runtime.workerPolicyReceipt().optBoolean("nativeBlockNetworkLoads"),"callbacks",staleCallbacks);staleRelease.countDown();}
  }
  void fail(Throwable error){if(done)return;done=true;phase="failed";String text=String.valueOf(error.getMessage()).replace('\n',' ').replace('\r',' ');failure=error.getClass().getSimpleName()+": "+text.substring(0,Math.min(220,text.length()));try{publish(true);}catch(Exception ignored){}}
  void publish(boolean terminal)throws Exception{if(build==null)return;JSONObject result=J.obj("schema",1,"engine","chromium","status",terminal?(failure.isEmpty()?"passed":"failed"):"running","phase",phase,"failure",failure,"sourceCommit",build.getString("sourceCommit"),"runNonce",invocation,"buildIdentity",build,"checks",checks,"samples",samples,"nativeSetups",nativeSetups,"staleCallbackProof",staleProof,"routeReadmissionProof",routeProof,"currentRestrictReceipt",currentSelfTest,"fixture",fixture==null?new JSONObject():fixture.snapshot(),"actualAndroidExecution",true,"actualAndroidWebViewExecution",web()!=null,"actualGeckoExecution",false,"actualPublicWebsiteExecution",false,"actualDevicePerformanceMeasurement",false,"workerCoverageVerified",false,"serviceWorkerCoverageVerified",false,"fingerprintProtectionVerified",false,"existingExecutionControlled",false,"scope","Actual BrowserActivity save/reload allow-restrict-allow; native ServiceWorker block/readback and HTTPS page/frame creation outcomes, actual existing SW cache execution and blocked network after real route readmission. Page creation restriction is not Worker fingerprint spoofing or termination of cached/existing workers. No in-flight cancellation, public-site or performance claim.");BrowserFingerprintIntegrationActivity.write(this,"worker-policy-chromium.json",result);}
  @Override protected void onDestroy(){staleRelease.countDown();poll.removeCallbacksAndMessages(null);evidence.shutdownNow();if(fixture!=null)fixture.close();super.onDestroy();}
}
