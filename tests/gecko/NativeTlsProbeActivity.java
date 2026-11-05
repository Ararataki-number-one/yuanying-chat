package local.pocketchat;

import android.app.Activity;
import android.os.*;
import android.util.AtomicFile;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.function.Consumer;
import org.json.*;
import org.mozilla.geckoview.*;

/** Integration-only standalone native protocol capability; not production browser admission. */
public final class NativeTlsProbeActivity extends Activity {
  static final String MIN="security.tls.version.min",MAX="security.tls.version.max";
  static final String RFP="privacy.resistFingerprinting",H2="network.http.http2.enabled",H3="network.http.http3.enable";
  static final List<String> KEYS=Arrays.asList(MIN,MAX,RFP,H2,H3);
  static final String[] TRIALS={"default-tls12","strict-tls12","strict-tls13","restored-tls12"};
  static final int[] PORTS={41441,41442,41443,41444};
  final Handler handler=new Handler(Looper.getMainLooper());
  final JSONArray observations=new JSONArray();
  GeckoRuntime runtime;GeckoSession session;GeckoView view;
  JSONObject build,original,strict,restored,currentTrial;
  String nonce,source,leaf,stage="initial",failure="";
  File profile,config;boolean closed,done,restoring,prefsTouched,restoreSucceeded,initialEnterpriseRoots;
  int trial=-1;long started,operation;
  @Override public void onCreate(Bundle ignored){super.onCreate(null);try{
    if(!"local.pocketchat.test".equals(getPackageName()))throw new SecurityException("IntegrationOnly");
    nonce=getIntent().getStringExtra("runNonce");source=getIntent().getStringExtra("sourceCommit");leaf=getIntent().getStringExtra("expectedLeafSha256");
    if(nonce==null||!nonce.matches("[0-9a-f]{32}")||source==null||!source.matches("[0-9a-f]{40}")||leaf==null||!leaf.matches("[0-9a-f]{64}")||getIntent().getIntExtra("fixturePort",-1)!=18776)throw new SecurityException("ExactBindingRequired");
    build=IntegrationBuildIdentity.read(this);if(!source.equals(build.getString("sourceCommit")))throw new SecurityException("SelectedSourceMismatch");
    started=SystemClock.elapsedRealtime();profile=new File(getNoBackupFilesDir(),"native-tls-"+nonce);if(!profile.mkdirs())throw new IOException("FreshProfileRequired");
    config=new File(getFilesDir(),"native-tls-"+nonce+".yaml");
    String yaml="prefs:\n  network.proxy.type: 1\n  network.proxy.http: '127.0.0.1'\n  network.proxy.http_port: 18776\n  network.proxy.ssl: '127.0.0.1'\n  network.proxy.ssl_port: 18776\n  network.proxy.no_proxies_on: '127.0.0.1,localhost'\n  network.trr.mode: 5\n  network.dns.disablePrefetch: true\n  network.prefetch-next: false\n  network.http.speculative-parallel-limit: 0\n  network.captive-portal-service.enabled: false\n  network.connectivity-service.enabled: false\n  datareporting.healthreport.uploadEnabled: false\n  toolkit.telemetry.enabled: false\n";
    try(FileOutputStream output=new FileOutputStream(config)){output.write(yaml.getBytes(StandardCharsets.UTF_8));}
    runtime=GeckoRuntime.create(this,new GeckoRuntimeSettings.Builder().arguments(new String[]{"-profile",profile.getAbsolutePath()}).configFilePath(config.getAbsolutePath()).remoteDebuggingEnabled(false).consoleOutput(false).build());
    initialEnterpriseRoots=runtime.getSettings().getEnterpriseRootsEnabled();runtime.getSettings().setEnterpriseRootsEnabled(true);
    view=new GeckoView(this);setContentView(view);stage="reading-original";publish();
    handler.postDelayed(()->fail("DiagnosticDeadline"),150000);
    read(value->{try{original=value;validateOriginal();startTrial(0);}catch(Exception invalid){fail("InvalidOriginalPreference");}});
  }catch(Throwable error){fail(error instanceof SecurityException?"InvalidBinding":"BootstrapFailure");}}
  void validateOriginal()throws Exception{
    for(String key:Arrays.asList(MIN,MAX)){
      JSONObject value=original.getJSONObject(key);if(!(value.opt("default") instanceof Integer)||value.getInt("default")<3||value.getInt("default")>4)throw new IOException();
      Object user=value.opt("user");if(user!=JSONObject.NULL&&(!(user instanceof Integer)||(Integer)user<3||(Integer)user>4))throw new IOException();
    }
    if(original.getJSONObject(MIN).getInt("default")>3||original.getJSONObject(MAX).getInt("default")<4||original.getJSONObject(MIN).getInt("effective")>3||original.getJSONObject(MAX).getInt("effective")<4)throw new IOException();
    for(String key:Arrays.asList(RFP,H2,H3))if(!(original.getJSONObject(key).opt("effective") instanceof Boolean))throw new IOException();
  }
  void read(Consumer<JSONObject> accepted){final long token=++operation;try{
    GeckoPreferenceController.getGeckoPrefs(KEYS).accept(values->{if(closed||done||token!=operation)return;try{
      if(values==null||values.size()!=KEYS.size())throw new IOException();JSONObject result=new JSONObject();
      for(GeckoPreferenceController.GeckoPreference<?> value:values){if(value==null||!KEYS.contains(value.pref)||result.has(value.pref))throw new IOException();
        result.put(value.pref,new JSONObject().put("default",value.defaultValue==null?JSONObject.NULL:value.defaultValue).put("user",value.userValue==null?JSONObject.NULL:value.userValue).put("effective",value.getValue()==null?JSONObject.NULL:value.getValue()).put("hasUserValue",value.getHasUserChangedValue()));}
      for(String key:KEYS)if(!result.has(key))throw new IOException();accepted.accept(result);
    }catch(Exception invalid){preferenceFailure();}},error->{if(token==operation)preferenceFailure();});
  }catch(Exception invalid){preferenceFailure();}}
  void writeDefault(String key,int value,Runnable next){write(key,value,GeckoPreferenceController.PREF_BRANCH_DEFAULT,next);}
  void write(String key,int value,int branch,Runnable next){if(!Arrays.asList(MIN,MAX).contains(key)||value<3||value>4){fail("ForbiddenPreferenceWrite");return;}
    final long token=++operation;prefsTouched=true;try{GeckoPreferenceController.setGeckoPref(key,Integer.valueOf(value),branch).accept(ignored->{if(!closed&&!done&&token==operation)next.run();},error->{if(token==operation)preferenceFailure();});}catch(Exception invalid){preferenceFailure();}}
  void clearUser(String key,Runnable next){if(!Arrays.asList(MIN,MAX).contains(key)){fail("ForbiddenPreferenceWrite");return;}final long token=++operation;prefsTouched=true;
    try{GeckoPreferenceController.clearGeckoUserPref(key).accept(ignored->{if(!closed&&!done&&token==operation)next.run();},error->{if(token==operation)preferenceFailure();});}catch(Exception invalid){preferenceFailure();}}
  void preferenceFailure(){if(restoring){failure=failure.isEmpty()?"RestorePreferenceFailure":failure;terminal(false);}else fail("NativePreferenceFailure");}
  void strictRange(){stage="applying-strict";publish();clearUser(MIN,()->clearUser(MAX,()->writeDefault(MAX,4,()->writeDefault(MIN,4,()->read(value->{try{
    strict=value;for(String key:Arrays.asList(MIN,MAX)){JSONObject row=value.getJSONObject(key);if(row.getInt("default")!=4||row.getBoolean("hasUserValue")||row.getInt("effective")!=4)throw new IOException();}
    unchangedProtected(value);startTrial(1);
  }catch(Exception invalid){fail("StrictReadbackMismatch");}})))));}
  void unchangedProtected(JSONObject value)throws Exception{for(String key:Arrays.asList(RFP,H2,H3))if(!original.getJSONObject(key).toString().equals(value.getJSONObject(key).toString()))throw new IOException();}
  String target(int index){return "https://fp-a.pocketchat.test:"+PORTS[index]+"/tls-probe?run="+nonce+"&source="+source+"&trial="+TRIALS[index];}
  /** A stop has no URL. It is diagnostic only and never proves target completion. */
  static final class TrialNavigation {
    static final int NONE=0,TLS_READY=1,SSL_REJECTED=2,INVALID=3;
    final Object owner;final int index,securityCategory,sslCode;final String target,expectedLeaf,expectedTitle;final JSONObject row;
    String issue="";int stops,successfulStops;
    TrialNavigation(Object owner,int index,String trial,String target,String leaf,String nonce,int category,int code)throws Exception{
      this.owner=owner;this.index=index;this.target=target;expectedLeaf=leaf;expectedTitle="Native TLS "+trial+":"+nonce;securityCategory=category;sslCode=code;
      row=new JSONObject().put("trial",trial).put("target",target).put("started",false).put("located",false).put("targetError",false).put("leafVerified",false).put("securityExceptionUsed",false)
        .put("titleMatched",false).put("nativeTargetTlsReady",false).put("stopCallbacks",0).put("successfulStopCallbacks",0).put("nativeStopOwnershipVerified",false);
    }
    boolean owns(Object supplied,int callbackIndex,Object active,int activeIndex,boolean open,boolean done,boolean closed,boolean restoring){
      return !done&&!closed&&!restoring&&open&&supplied==owner&&active==owner&&callbackIndex==index&&activeIndex==index;
    }
    int invalid(String reason){issue=reason;return INVALID;}
    int ready()throws Exception{boolean matched=row.optBoolean("started")&&row.optBoolean("located")&&row.optBoolean("leafVerified")&&row.optBoolean("titleMatched")&&!row.optBoolean("targetError");row.put("nativeTargetTlsReady",matched);return matched?TLS_READY:NONE;}
    int start(String url)throws Exception{if(target.equals(url)){row.put("started",true);return ready();}return "about:blank".equals(url)?NONE:invalid("UncontrolledNavigation");}
    int location(String url)throws Exception{if(target.equals(url)){row.put("located",true);return ready();}return "about:blank".equals(url)?NONE:invalid("UncontrolledNavigation");}
    int title(String value)throws Exception{if(expectedTitle.equals(value)){row.put("titleMatched",true);return ready();}return NONE;}
    int security(String host,boolean secure,boolean exception,String actual)throws Exception{
      if(!"fp-a.pocketchat.test".equals(host))return NONE;
      row.put("secure",secure).put("securityExceptionUsed",exception).put("leafSha256",actual);
      if(exception||secure&&!expectedLeaf.equals(actual))return invalid("ControlledCertificateMismatch");
      if(secure){row.put("leafVerified",true);return ready();}return NONE;
    }
    int stop(boolean success)throws Exception{stops++;if(success)successfulStops++;row.put("stopCallbacks",stops).put("successfulStopCallbacks",successfulStops);return NONE;}
    int error(String url,int category,int code)throws Exception{
      if(!target.equals(url))return invalid("UnownedLoadError");
      row.put("targetError",true).put("errorCategory",category).put("errorCode",code).put("nativeErrorUrlMatched",true);
      return index==1&&category==securityCategory&&code==sslCode?SSL_REJECTED:invalid("UnexpectedNativeLoadError");
    }
  }
  TrialNavigation navigation;
  boolean current(GeckoSession value,int index){return navigation!=null&&navigation.owns(value,index,session,trial,value!=null&&value.isOpen(),done,closed,restoring);}
  void callback(TrialNavigation actual,int index,int action){if(actual!=navigation||done||closed||restoring||trial!=index)return;publish();
    if(action==TrialNavigation.INVALID)fail(actual.issue);
    else if(action==TrialNavigation.TLS_READY){if(index==1)fail("StrictTls12UnexpectedSuccess");else completeTrial(index);}
    else if(action==TrialNavigation.SSL_REJECTED)completeTrial(index);
  }
  void startTrial(int index){if(done||closed)return;try{
    if(session!=null&&session.isOpen())session.close();trial=index;stage=TRIALS[index];final String url=target(index);
    GeckoSession next=new GeckoSession();session=next;final TrialNavigation actual=new TrialNavigation(next,index,TRIALS[index],url,leaf,nonce,WebRequestError.ERROR_CATEGORY_SECURITY,WebRequestError.ERROR_SECURITY_SSL);navigation=actual;
    currentTrial=actual.row;observations.put(currentTrial);
    next.setNavigationDelegate(new GeckoSession.NavigationDelegate(){
      @Override public void onLocationChange(GeckoSession value,String location,List<GeckoSession.PermissionDelegate.ContentPermission> permissions,Boolean gesture){if(!current(value,index))return;try{callback(actual,index,actual.location(location));}catch(Exception invalid){fail("CallbackFailure");}}
      @Override public GeckoResult<String> onLoadError(GeckoSession value,String location,WebRequestError error){if(!current(value,index))return null;try{callback(actual,index,actual.error(location,error.category,error.code));}catch(Exception invalid){fail("CallbackFailure");}return null;}
    });
    next.setContentDelegate(new GeckoSession.ContentDelegate(){
      @Override public void onTitleChange(GeckoSession value,String title){if(!current(value,index))return;try{callback(actual,index,actual.title(title));}catch(Exception invalid){fail("CallbackFailure");}}
    });
    next.setProgressDelegate(new GeckoSession.ProgressDelegate(){
      @Override public void onPageStart(GeckoSession value,String location){if(!current(value,index))return;try{callback(actual,index,actual.start(location));}catch(Exception invalid){fail("CallbackFailure");}}
      @Override public void onSecurityChange(GeckoSession value,SecurityInformation info){if(!current(value,index))return;try{String actualLeaf=info.certificate==null?"":BrowserFingerprintFixture.sha(info.certificate.getEncoded());callback(actual,index,actual.security(info.host,info.isSecure,info.isException,actualLeaf));}catch(Exception invalid){fail("CallbackFailure");}}
      @Override public void onPageStop(GeckoSession value,boolean success){if(!current(value,index))return;try{callback(actual,index,actual.stop(success));}catch(Exception invalid){fail("CallbackFailure");}}
    });next.open(runtime);view.setSession(next);next.setActive(true);publish();next.loadUri(url);
    handler.postDelayed(()->{if(current(next,index))fail("TrialDeadline");},25000);
  }catch(Exception invalid){fail("TrialSetupFailure");}}
  void completeTrial(int index){if(trial!=index||restoring||done||closed)return;trial=-1;if(session!=null&&session.isOpen())session.close();session=null;publish();
    if(index==0)strictRange();else if(index==1)startTrial(2);else if(index==2)restore(()->startTrial(3));else terminal(true);}
  void restore(Runnable after){if(original==null){terminal(false);return;}restoring=true;stage="restoring-original";publish();try{
    writeDefault(MIN,original.getJSONObject(MIN).getInt("default"),()->writeDefault(MAX,original.optJSONObject(MAX).optInt("default"),()->restoreUser(MIN,()->restoreUser(MAX,()->read(value->{try{
      restored=value;for(String key:KEYS)if(!original.getJSONObject(key).toString().equals(value.getJSONObject(key).toString()))throw new IOException();
      restoreSucceeded=true;restoring=false;after.run();
    }catch(Exception invalid){failure=failure.isEmpty()?"RestoreReadbackMismatch":failure;terminal(false);}})))));
  }catch(Exception invalid){failure=failure.isEmpty()?"RestoreSetupFailure":failure;terminal(false);}}
  void restoreUser(String key,Runnable next){Object value=original.optJSONObject(key).opt("user");if(value==JSONObject.NULL)clearUser(key,next);else if(value instanceof Integer)write(key,(Integer)value,GeckoPreferenceController.PREF_BRANCH_USER,next);else{failure="RestoreUserTypeMismatch";terminal(false);}}
  void fail(String code){if(done||closed)return;if(failure.isEmpty())failure=code;if(restoring){terminal(false);return;}trial=-1;if(session!=null&&session.isOpen())session.close();session=null;
    if(original!=null&&prefsTouched)restore(()->terminal(false));else terminal(false);}
  void terminal(boolean success){if(done)return;done=true;stage=success&&failure.isEmpty()&&restoreSucceeded?"complete":"failed";
    if(runtime!=null)runtime.getSettings().setEnterpriseRootsEnabled(initialEnterpriseRoots);publish();}
  void publish(){if(build==null||nonce==null)return;try{
    JSONObject report=new JSONObject().put("schema",1).put("status",done?("complete".equals(stage)?"observed":"failed"):"running").put("stage",stage).put("failureCode",failure)
      .put("runNonce",nonce).put("sourceCommit",source).put("sourceTree",build.getString("sourceTree")).put("buildIdentity",build).put("pid",android.os.Process.myPid())
      .put("actualAndroidExecution",true).put("actualGeckoExecution",runtime!=null).put("standaloneSessionCapabilityOnly",true).put("diagnosticOnly",true).put("releaseQualification",false)
      .put("nativeOriginal",original==null?JSONObject.NULL:original).put("nativeStrict",strict==null?JSONObject.NULL:strict).put("nativeRestored",restored==null?JSONObject.NULL:restored).put("nativeRestoreSucceeded",restoreSucceeded)
      .put("observations",observations).put("nativeSettingReadbackIsWireProof",false).put("fullTlsFingerprintEmulation",false).put("quicWireVerified",false).put("debuggingEndpointUsed",false).put("javascriptTlsOverrideUsed",false)
      .put("rfpModified",false).put("h2OrH3PrefsModified",false).put("enterpriseRootsInitiallyEnabled",initialEnterpriseRoots).put("enterpriseRootsRestored",done&&runtime!=null&&runtime.getSettings().getEnterpriseRootsEnabled()==initialEnterpriseRoots)
      .put("elapsedMs",SystemClock.elapsedRealtime()-started);
    byte[] raw=(report.toString()+"\n").getBytes(StandardCharsets.UTF_8);if(raw.length>131072)throw new IOException();AtomicFile file=new AtomicFile(new File(getFilesDir(),"native-tls-"+nonce+".json"));FileOutputStream output=null;
    try{output=file.startWrite();output.write(raw);file.finishWrite(output);}catch(Exception invalid){if(output!=null)file.failWrite(output);}
  }catch(Exception invalid){}}
  @Override protected void onDestroy(){closed=true;handler.removeCallbacksAndMessages(null);if(session!=null&&session.isOpen())session.close();if(runtime!=null){runtime.getSettings().setEnterpriseRootsEnabled(initialEnterpriseRoots);runtime.shutdown();}super.onDestroy();}
}
