package local.pocketchat;

import android.app.AlertDialog;
import android.content.Context;
import android.os.*;
import android.util.AtomicFile;
import android.view.*;
import android.view.inputmethod.EditorInfo;
import android.webkit.*;
import android.widget.*;
import java.io.*;
import java.lang.reflect.Field;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;

/** Actual production browser controls plus first-inline observations on two synthetic HTTPS origins. */
public final class BrowserFingerprintIntegrationActivity extends BrowserActivity {
  static final String URL="https://"+BrowserFingerprintFixture.A+"/document";
  final Handler probe=new Handler(Looper.getMainLooper());final ExecutorService checksIo=Executors.newSingleThreadExecutor();
  final JSONArray checks=new JSONArray(),samples=new JSONArray(),setups=new JSONArray();
  BrowserFingerprintFixture fixture;JSONObject build;String nonce,stage="initial",failure="";boolean finished;
  ChromiumFingerprintStore.State independent;WebView auxiliary;ChromiumFingerprintRuntime.Prepared auxiliaryPolicy;
  long deadline,staleOperation=-1;int staleCallbacks;JSONObject first,currentSelfTest=new JSONObject(),staleCallbackProof=new JSONObject();String canvas;
  interface Step{void run()throws Exception;}interface Ready{boolean get()throws Exception;}
  @Override public void onCreate(Bundle state){try{
    validateIntent(this);nonce=getIntent().getStringExtra("runNonce");build=IntegrationBuildIdentity.read(this);
    if(!build.getString("sourceCommit").equals(getIntent().getStringExtra("sourceCommit")))throw new SecurityException("Source differs");
    fixture=new BrowserFingerprintFixture(this,"chromium");fixture.start();configure(this,fixture.port(),URL+"?case=primary");
    getIntent().putExtra("url",URL+"?case=primary");super.onCreate(null);deadline=SystemClock.elapsedRealtime()+90000;publish(false);
    await("first protected production surface",()->fingerprintState!=null&&selected!=null&&selected.fingerprint!=null&&ready(URL),()->{
      check("chromium.production-ui",address.isShown()&&runtime.allowed()&&web()!=null);
      checksIo.execute(()->{try{Context other=Profiles.context(this,1);ProfileCatalog.get(this).created(1);independent=ChromiumFingerprintStore.load(other);probe.post(()->sample("primary",this::primary));}catch(Exception error){probe.post(()->fail(error));}});
    });
  }catch(Throwable error){fail(error);}}
  static void validateIntent(android.app.Activity a){if(!"local.pocketchat.test".equals(a.getPackageName())||!a.getIntent().getStringExtra("runNonce").matches("[0-9a-f]{32}")||!a.getIntent().getStringExtra("sourceCommit").matches("[0-9a-f]{40}"))throw new SecurityException("Fresh integration invocation only");}
  static void configure(Context c,int port,String url){ProfileCatalog.get(c).created(Profiles.slot(c));c.getSharedPreferences("chat",MODE_PRIVATE).edit().clear().putBoolean("environmentInitialized",true).putString("networkMode","external").putString("proxy","http://127.0.0.1:"+port).putBoolean("networkConfigured",true).putBoolean("requireExternalVpn",false).putString("geckoBrowserUrl",url).putString("url",url).commit();c.getSharedPreferences("universal-browser",MODE_PRIVATE).edit().clear().commit();}
  boolean ready(String url){return runtime!=null&&runtime.allowed()&&web()!=null&&web().getProgress()==100&&web().getUrl()!=null&&web().getUrl().startsWith(url)&&!selected.loading&&selected.fingerprintBindingReady&&fixture.accepted.get()>0;}
  void await(String name,Ready condition,Step after){if(finished)return;try{if(condition.get()){after.run();return;}if(SystemClock.elapsedRealtime()>deadline)throw new IllegalStateException("Deadline: "+name);probe.postDelayed(()->await(name,condition,after),75);}catch(Throwable error){fail(error);}}
  void next(String value)throws Exception{stage=value;deadline=SystemClock.elapsedRealtime()+45000;publish(false);}
  void check(String id,boolean pass)throws Exception{checks.put(J.obj("id",id,"pass",pass));if(!pass)throw new AssertionError(id);}
  void evaluate(WebView view,String code,java.util.function.Consumer<JSONObject> after){view.evaluateJavascript("JSON.stringify(("+code+"))",raw->{try{Object outer=new JSONTokener(raw).nextValue();if(!(outer instanceof String))throw new IllegalStateException("Missing fixture document");after.accept(new JSONObject((String)outer));}catch(Throwable error){fail(error);}});}
  void sample(String label,java.util.function.Consumer<JSONObject> after){if(finished)return;if(SystemClock.elapsedRealtime()>deadline){fail(new IllegalStateException("First-inline observation deadline"));return;}
    evaluate(web(),"({early:window.__fixtureEarly||{},frames:window.__fixtureFrames||[]})",value->{try{
      JSONObject e=value.getJSONObject("early");JSONArray frames=value.getJSONArray("frames");if(!ready(URL)||!e.optBoolean("complete")||frames.length()!=2||("reload".equals(label)&&first!=null&&e.optString("documentId").equals(first.getJSONObject("early").optString("documentId")))){probe.postDelayed(()->sample(label,after),75);return;}
      if(e.has("error"))throw new IllegalStateException("Synthetic first-inline observation failed");
      if(!networkMatches(e,fingerprintSpec.desktop())){probe.postDelayed(()->sample(label,after),75);return;}
      value.put("case",label);samples.put(value);after.accept(value);
    }catch(Throwable error){fail(error);}});
  }
  void nativeSetup(String id,boolean desktop)throws Exception{
    JSONObject nativeSetup=selected.fingerprint.receipt();nativeSetup.put("case",id);setups.put(nativeSetup);
    check(id+".features",nativeSetup.getJSONObject("features").getBoolean("documentStart")&&nativeSetup.getJSONObject("features").getBoolean("userAgentMetadata")&&nativeSetup.getBoolean("documentStartRegistered")&&Integer.parseInt(nativeSetup.getString("chromiumVersion").split("\\.")[0])>=124);
    check(id+".native-metadata",nativeSetup.getJSONObject("nativeRequested").toString().equals(nativeSetup.getJSONObject("nativeReadback").toString())&&nativeSetup.getJSONObject("nativeReadback").getBoolean("mobile")==!desktop);
    Bundle certificate=android.net.http.SslCertificate.saveState(web().getCertificate());byte[] encoded=certificate==null?null:certificate.getByteArray("x509-certificate");check(id+".native-tls-certificate",encoded!=null&&BrowserFingerprintFixture.sha(encoded).equals(fixture.leafSha256));nativeSetup.put("observedLeafDerSha256",BrowserFingerprintFixture.sha(encoded));
  }
  void inspect(String id,JSONObject sample,boolean desktop)throws Exception{
    JSONObject e=sample.getJSONObject("early");check(id+".first-inline",e.getBoolean("firstInline")&&e.getBoolean("secure")&&e.getBoolean("documentGuard")&&e.getBoolean("auditAvailable"));
    check(id+".native-js-ua",e.getString("ua").equals(selected.fingerprint.receipt().getString("nativeUserAgent"))&&e.getJSONObject("low").getBoolean("mobile")==!desktop);
    check(id+".canvas",e.getString("canvas").equals(e.getString("repeat"))&&!e.getString("canvas").equals(e.getString("baseline")));
    JSONObject same=null,cross=null;JSONArray frames=sample.getJSONArray("frames");for(int i=0;i<frames.length();i++){JSONObject row=frames.getJSONObject(i);if(e.getString("origin").equals(row.getString("origin")))same=row;else cross=row;}
    check(id+".frames",same!=null&&cross!=null&&same.getBoolean("firstInline")&&cross.getBoolean("firstInline")&&same.getBoolean("documentGuard")&&cross.getBoolean("documentGuard")&&same.getBoolean("secure")&&cross.getBoolean("secure")&&same.getString("canvas").equals(e.getString("canvas"))&&!cross.getString("canvas").equals(e.getString("canvas")));
    check(id+".no-gpt-hotpath",e.getJSONObject("gpt").getString("reply").equals("undefined")&&e.getJSONObject("gpt").getString("performance").equals("undefined"));
    JSONObject worker=e.getJSONObject("worker");check(id+".worker-explicitly-unprotected",worker.getBoolean("actualExecution")&&!worker.getBoolean("protected")&&!worker.getBoolean("documentGuard")&&!worker.getBoolean("auditAvailable")&&!e.getBoolean("workerCoverageVerified")&&!e.getBoolean("serviceWorkerCoverageVerified"));
    check(id+".https-native-hints",networkMatches(e,desktop));
  }
  boolean networkMatches(JSONObject e,boolean desktop)throws Exception{
    JSONArray requests=fixture.snapshot().getJSONArray("requests");JSONObject headers=null;for(int i=requests.length()-1;i>=0;i--){JSONObject row=requests.getJSONObject(i);if(row.getString("origin").equals(e.getString("origin"))&&row.getString("path").equals("/hints")){headers=row;break;}}
    if(headers==null)return false;JSONObject high=e.getJSONObject("high"),low=e.getJSONObject("low");
    return headers.getBoolean("tls")&&headers.getString("user-agent").equals(e.getString("ua"))&&headers.getString("sec-ch-ua-mobile").equals(desktop?"?0":"?1")&&headers.getString("sec-ch-ua-platform").equals(JSONObject.quote(low.getString("platform")))&&headers.getString("sec-ch-ua-arch").equals(JSONObject.quote(high.getString("architecture")))&&headers.getString("sec-ch-ua-bitness").equals(JSONObject.quote(high.getString("bitness")))&&headers.getString("sec-ch-ua-model").equals(JSONObject.quote(high.getString("model")))&&headers.getString("sec-ch-ua-platform-version").equals(JSONObject.quote(high.getString("platformVersion")))&&headers.getString("sec-ch-ua-full-version-list").contains("Chromium");
  }
  void primary(JSONObject value){try{first=value;canvas=value.getJSONObject("early").getString("canvas");nativeSetup("primary",false);inspect("primary",value,false);
    next("same-origin-reload");web().reload();await("reload",()->ready(URL),()->sample("reload",this::reloaded));
  }catch(Throwable error){fail(error);}}
  void reloaded(JSONObject value){try{check("canvas.same-origin-reload",canvas.equals(value.getJSONObject("early").getString("canvas")));
    next("stale-document");Tab oldTab=selected;WebView oldWeb=web();ChromiumFingerprintStore.State oldState=fingerprintState;ChromiumFingerprintStore.Binding oldBinding=selected.fingerprintBinding;
    observeFingerprint();staleOperation=fingerprintObservationGeneration;check("selftest.real-observation-dispatched",fingerprintObserving);
    address.setText(URL+"?case=after-navigation");address.onEditorAction(EditorInfo.IME_ACTION_GO);
    await("actual Chromium address action and old JavaScript callback",()->ready(URL+"?case=after-navigation")&&staleCallbacks==1,()->{
      check("chromium.generic-address-ui",web()==oldWeb&&selected.url.equals(URL+"?case=after-navigation"));
      check("selftest.stale-document-rejected",oldBinding!=null&&!fingerprintCurrent(oldTab,oldWeb,oldState,oldBinding));
      check("selftest.actual-stale-callback-rejected",staleCallbackProof.optBoolean("staleBinding")&&staleCallbackProof.optBoolean("receiptUnchanged")&&!observedCanvas(fingerprintReceipt));
      checksIo.execute(()->{try{boolean rejected=false;try{ChromiumFingerprintStore.record(this,oldState.identity,oldState.revision,oldBinding,J.obj("canvas",J.obj("state","page-observed")));}catch(IOException expected){rejected=true;}final boolean refused=rejected;probe.post(()->{try{check("selftest.stale-receipt-rejected",refused);desktop();}catch(Throwable error){fail(error);}});}catch(Throwable error){probe.post(()->fail(error));}});
    });
  }catch(Throwable error){fail(error);}}
  void desktop()throws Exception{
    next("desktop-native-identity");WebView old=web();ChromiumFingerprintStore.State before=fingerprintState;JSONObject desired=ChromiumFingerprintSpec.defaults().json().put("display","desktop");saveFingerprint(before,desired,false);
    await("new native desktop surface",()->fingerprintState!=null&&fingerprintState.revision>before.revision&&web()!=null&&web()!=old&&ready(URL),()->sample("desktop",value->{try{nativeSetup("desktop",true);inspect("desktop",value,true);check("canvas.policy-edit-retains-environment-seed",canvas.equals(value.getJSONObject("early").getString("canvas")));independent();}catch(Throwable error){fail(error);}}));
  }
  void independent()throws Exception{
    next("independent-environment-policy");check("canvas.independent-saved-environment",independent!=null&&independent.identity.slot!=fingerprintState.identity.slot&&!independent.seed.equals(fingerprintState.seed));
    auxiliary=new WebView(this);auxiliary.getSettings().setJavaScriptEnabled(true);auxiliary.getSettings().setBlockNetworkLoads(true);
    auxiliaryPolicy=ChromiumFingerprintRuntime.prepare(auxiliary,ChromiumFingerprintSpec.defaults(),independent.seed,fingerprintScript);
    auxiliary.setWebViewClient(new WebViewClient(){@Override public void onPageFinished(WebView view,String url){if(!URL.equals(url))return;probe.post(()->independentSample());}});
    content.addView(auxiliary,new android.widget.FrameLayout.LayoutParams(dp(128),dp(128)));auxiliary.getSettings().setBlockNetworkLoads(false);auxiliary.loadUrl(URL);
  }
  void independentSample(){if(finished)return;evaluate(auxiliary,"({early:window.__fixtureEarly||{}})",value->{try{JSONObject e=value.getJSONObject("early");if(!e.optBoolean("complete")){if(SystemClock.elapsedRealtime()>deadline)throw new IllegalStateException("Independent policy deadline");probe.postDelayed(this::independentSample,75);return;}
    check("canvas.independent-environment-output",e.getBoolean("documentGuard")&&!canvas.equals(e.getString("canvas"))&&e.getString("canvas").equals(e.getString("repeat")));value.put("case","independent-environment-policy");samples.put(value);next("current-page-selftest");observeFingerprint();await("current document self-test",()->!fingerprintObserving&&observedCanvas(fingerprintReceipt),()->{
      ChromiumFingerprintStore.State state=fingerprintState;ChromiumFingerprintStore.Binding binding=selected.fingerprintBinding;
      checksIo.execute(()->{try{JSONObject current=ChromiumFingerprintStore.lastReceipt(this,state.identity,state.revision,binding);boolean observed=observedCanvas(current);JSONObject self=observed?current.getJSONObject("fields").getJSONObject("pageSelfTest").getJSONObject("value"):new JSONObject();probe.post(()->{try{check("selftest.current-document-observed",observed);currentSelfTest=self;finished=true;stage="complete";publish(true);}catch(Throwable error){fail(error);}});}catch(Throwable error){probe.post(()->fail(error));}});
    });
  }catch(Throwable error){fail(error);}});}
  static boolean observedCanvas(JSONObject receipt){JSONObject fields=receipt.optJSONObject("fields"),test=fields==null?null:fields.optJSONObject("pageSelfTest"),value=test==null?null:test.optJSONObject("value"),observed=value==null?null:value.optJSONObject("fields"),canvas=observed==null?null:observed.optJSONObject("canvas");return test!=null&&"page-observed".equals(test.optString("state"))&&canvas!=null&&"page-observed".equals(canvas.optString("state"));}
  @Override void finishFingerprintObservation(Tab tab,WebView view,ChromiumFingerprintStore.State state,ChromiumFingerprintStore.Binding binding,String url,long operation,JSONObject result,String error){
    boolean stale=!fingerprintCurrent(tab,view,state,binding);JSONObject before=fingerprintReceipt;super.finishFingerprintObservation(tab,view,state,binding,url,operation,result,error);
    if(operation==staleOperation){staleCallbacks++;staleCallbackProof=J.obj("actualCallback",true,"staleBinding",stale,"receiptUnchanged",before==fingerprintReceipt,"callbacks",staleCallbacks);}
  }
  void fail(Throwable error){if(finished)return;failure=error.getClass().getSimpleName()+": "+String.valueOf(error.getMessage());finished=true;stage="failed";try{publish(true);}catch(Exception ignored){}}
  void publish(boolean terminal)throws Exception{if(build==null)return;JSONObject result=J.obj("schema",1,"engine","chromium","status",terminal?(failure.isEmpty()?"passed":"failed"):"running","stage",stage,"failure",failure,"sourceCommit",build.getString("sourceCommit"),"runNonce",nonce,"buildIdentity",build,"checks",checks,"samples",samples,"nativeSetups",setups,"currentPageSelfTest",currentSelfTest,"staleCallbackProof",staleCallbackProof,"fixture",fixture==null?new JSONObject():fixture.snapshot(),"actualAndroidExecution",true,"actualAndroidWebViewExecution",web()!=null,"actualGeckoExecution",false,"actualPublicWebsiteExecution",false,"actualDevicePerformanceMeasurement",false,"fingerprintProtectionVerified",false,"workerCoverageVerified",false,"serviceWorkerCoverageVerified",false,"uaChNetworkVerified",terminal&&failure.isEmpty(),"scope","Actual production BrowserActivity controls and Chromium native settings/document-start script on two integration-only, domain-scoped user-CA-trusted synthetic HTTPS origins with an ephemeral host TLS server. Independent environment policy uses a second saved environment seed with the actual runtime; it does not claim cookie/storage/process isolation. Dedicated Worker is observed unprotected; ServiceWorker is unsupported and not executed. No public website, physical-phone speed or complete fingerprint protection claim.");write(this,"browser-fingerprint-chromium.json",result);}
  static void write(Context c,String name,JSONObject value)throws Exception{AtomicFile file=new AtomicFile(new File(c.getFilesDir(),name));FileOutputStream stream=null;try{stream=file.startWrite();stream.write((value.toString()+"\n").getBytes(StandardCharsets.UTF_8));file.finishWrite(stream);}catch(Exception error){if(stream!=null)file.failWrite(stream);throw error;}}
  @Override protected void onDestroy(){probe.removeCallbacksAndMessages(null);checksIo.shutdownNow();if(auxiliaryPolicy!=null)auxiliaryPolicy.close();if(auxiliary!=null){auxiliary.stopLoading();auxiliary.destroy();}if(fixture!=null)fixture.close();super.onDestroy();}

  /** Separate real Gecko UI surface, not a WebView impersonation of Gecko. */
  public static final class Gecko extends MainActivity {
    final Handler poll=new Handler(Looper.getMainLooper());final JSONArray evidence=new JSONArray();BrowserFingerprintFixture server;JSONObject identity;String invocation,error="",phase="start";boolean done;long until;
    @Override public void onCreate(Bundle state){try{validateIntent(this);identity=IntegrationBuildIdentity.read(this);invocation=getIntent().getStringExtra("runNonce");if(!identity.getString("sourceCommit").equals(getIntent().getStringExtra("sourceCommit")))throw new SecurityException("Source differs");server=new BrowserFingerprintFixture(this,"gecko");server.start();String home="http://"+BrowserFingerprintFixture.A+"/document";configure(this,server.port(),home);getIntent().putExtra("legacyChat",true);super.onCreate(null);until=SystemClock.elapsedRealtime()+90000;record(false);waitFor(()->session!=null&&session.networkReady&&remote!=null&&remote.hasVisibleDocument()&&remote.getUrl().startsWith(home)&&remote.ports.get(remote.current)!=null,this::navigate);}catch(Throwable failure){failed(failure);}}
    void waitFor(Ready condition,Step next){if(done)return;try{if(condition.get()){next.run();return;}if(SystemClock.elapsedRealtime()>until)throw new IllegalStateException("Gecko "+phase+" deadline");poll.postDelayed(()->waitFor(condition,next),75);}catch(Throwable failure){failed(failure);}}
    void assertCheck(String id,boolean pass)throws Exception{evidence.put(J.obj("id",id,"pass",pass));if(!pass)throw new AssertionError(id);}
    void navigate()throws Exception{phase="native-address";until=SystemClock.elapsedRealtime()+45000;assertCheck("gecko.production-surface",remote.current!=null&&geckoAddress!=null&&geckoAddress.address.isShown());geckoAddress.address.performClick();
      Field field=GeckoAddressUi.class.getDeclaredField("dialog");field.setAccessible(true);AlertDialog dialog=(AlertDialog)field.get(geckoAddress);assertCheck("gecko.address-dialog",dialog!=null&&dialog.isShowing());EditText input=findInput(dialog.getWindow().getDecorView());if(input==null)throw new AssertionError("Address input missing");String destination="http://"+BrowserFingerprintFixture.B+"/document";input.setText(destination);dialog.getButton(AlertDialog.BUTTON_POSITIVE).performClick();
      waitFor(()->remote.getUrl().equals(destination)&&remote.hasVisibleDocument()&&remote.ports.get(remote.current)!=null,()->inspect(destination));
    }
    static EditText findInput(View view){if(view instanceof EditText)return (EditText)view;if(view instanceof ViewGroup){ViewGroup group=(ViewGroup)view;for(int i=0;i<group.getChildCount();i++){EditText found=findInput(group.getChildAt(i));if(found!=null)return found;}}return null;}
    void inspect(String destination)throws Exception{assertCheck("gecko.generic-address-ui",destination.equals(session.web.getUrl())&&!MainActivity.chatUrl(destination));
      remote.evaluateJavascript("JSON.stringify(({url:location.href,reply:typeof window.__pocketWebReplyObserver,readDriver:typeof window.__pocketReadDriver,performance:typeof window.__pocketWebPerformance}))",raw->{try{
        Object parsed=new JSONTokener(raw).nextValue();JSONObject observation=new JSONObject(parsed instanceof String?(String)parsed:raw);
        assertCheck("gecko.no-gpt-hotpath",observation.getString("url").equals(destination)&&observation.getString("reply").equals("undefined")&&observation.getString("readDriver").equals("undefined")&&observation.getString("performance").equals("undefined"));
        session.runDriver("web-inspect",new JSONObject(),result->{try{assertCheck("gecko.gpt-driver-rejected",result.optBoolean("cancelled")&&!session.chatAutomationAllowed()&&session.driverTarget()==null);done=true;phase="complete";record(true);}catch(Throwable failure){failed(failure);}});
      }catch(Throwable failure){failed(failure);}});
    }
    void failed(Throwable failure){if(done)return;error=failure.getClass().getSimpleName()+": "+String.valueOf(failure.getMessage());done=true;phase="failed";try{record(true);}catch(Exception ignored){}}
    void record(boolean terminal)throws Exception{if(identity==null)return;write(this,"browser-fingerprint-gecko.json",J.obj("schema",1,"engine","gecko","status",terminal?(error.isEmpty()?"passed":"failed"):"running","stage",phase,"failure",error,"runNonce",invocation,"sourceCommit",identity.getString("sourceCommit"),"buildIdentity",identity,"checks",evidence,"fixture",server==null?new JSONObject():server.snapshot(),"actualAndroidExecution",true,"actualGeckoExecution",remote!=null&&remote.current!=null,"actualAndroidWebViewExecution",false,"actualPublicWebsiteExecution",false,"actualDevicePerformanceMeasurement",false,"scope","Real MainActivity/GeckoAddressUi native address dialog submits a controlled ordinary HTTP origin through the configured external loopback proxy. Actual generic document rejects ChatGPT driver dispatch and has no reply/read/performance hot-path globals. Existing original Gecko fingerprint acceptance remains separately required."));}
    @Override protected void onDestroy(){poll.removeCallbacksAndMessages(null);if(server!=null)server.close();super.onDestroy();}
  }
}
