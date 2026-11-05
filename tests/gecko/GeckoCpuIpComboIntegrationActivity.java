package local.pocketchat;

import android.os.*;
import android.util.AtomicFile;
import java.io.*;
import java.lang.reflect.Field;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;
import org.mozilla.geckoview.*;

/** One independent production cold-bootstrap combination, never a replacement
 * for the ten CPU cases or eleven IP cases. Only the page samples its getters. */
public final class GeckoCpuIpComboIntegrationActivity extends MainActivity {
  static final String TARGET="https://fp-a.pocketchat.test/env-policy?phase=gecko-new-york";
  static final String FILE="gecko-cpu-ip-combo-activity.json";
  final Handler probe=new Handler(Looper.getMainLooper());
  final ExecutorService writer=Executors.newSingleThreadExecutor();
  final JSONArray checks=new JSONArray(),events=new JSONArray();
  final Map<GeckoSession,JSONObject> securities=new IdentityHashMap<>();
  JSONObject build,setup=new JSONObject(),cpuSetup=new JSONObject(),page=new JSONObject(),nativeProof=new JSONObject(),freshCpu=new JSONObject(),cpuStored=new JSONObject();
  String nonce,stage="startup",failure="";long deadline;boolean terminal,capturing,roots;

  @Override public void onCreate(Bundle saved){try{
    deadline=SystemClock.elapsedRealtime()+120000;BrowserFingerprintIntegrationActivity.validateIntent(this);
    nonce=getIntent().getStringExtra("runNonce");build=IntegrationBuildIdentity.read(this);
    if(!build.getString("sourceCommit").equals(getIntent().getStringExtra("sourceCommit")))throw new SecurityException("Installed source differs");
    IpTimeZoneFixtureScopes.requireArmed(this,build.getString("sourceCommit"),nonce);
    setup=IpTimeZoneFixtureScopes.read(this,IpTimeZoneFixtureScopes.SETUP);
    if(ChatSession.peek()!=null)throw new SecurityException("Cold session precondition lost");
    Future<JSONObject[]> prepared=writer.submit(()->{
      if(new SecretStore(this).get(GeckoTimeZoneStore.STORE)!=null||new SecretStore(this).get(GeckoCpuStore.STORE)!=null)throw new IOException("Fresh stores required");
      GeckoTimeZoneStore.State zone=GeckoTimeZoneStore.load(this);GeckoCpuStore.State cpu=GeckoCpuStore.load(this);
      if(zone.revision!=1||!zone.spec.followsIp()||zone.identity.slot!=6||cpu.revision!=1||!cpu.spec.isAutomatic()||!zone.identity.equals(cpu.identity))throw new IOException("Actual missing-store defaults differ");
      GeckoCpuStore.State selected=GeckoCpuStore.save(this,cpu.identity,cpu.revision,GeckoCpuSpec.of("1"));
      if(selected.revision!=2||!"1".equals(selected.spec.mode))throw new IOException("Actual cold CPU desired save failed");
      return new JSONObject[]{J.obj("defaultSpec",zone.spec.json(),"defaultRevision",zone.revision,"loadedIdentity",zone.identity.json()),
        J.obj("cpuSealedRecordMissingBefore",true,"actualColdStoreSave",true,"loadedMode",cpu.spec.mode,"loadedRevision",cpu.revision,
          "savedMode",selected.spec.mode,"savedRevision",selected.revision,"identity",selected.identity.json(),"sessionAbsentBeforeSetup",ChatSession.peek()==null)};
    });
    JSONObject[] loaded=prepared.get(10000,TimeUnit.MILLISECONDS);for(Iterator<String> keys=loaded[0].keys();keys.hasNext();){String key=keys.next();setup.put(key,loaded[0].get(key));}setup.put("actualDefaultStoreLoadYet",true);cpuSetup=loaded[1];
    getSharedPreferences("chat",0).edit().clear().putBoolean("environmentInitialized",true).putString("networkMode","external")
      .putString("proxy","socks://127.0.0.1:18766").putBoolean("networkConfigured",true).putBoolean("requireExternalVpn",false)
      .putString("geckoBrowserUrl",TARGET).putString("url",TARGET).putInt("privacyLevel",1).putBoolean("saveDraft",true).commit();
    ChatSession.browserFactory=(context,owner)->new Observed(context,owner);getIntent().putExtra("legacyChat",true);
    super.onCreate(null);stage="production-cold-bootstrap";publish();probe.post(this::tick);
  }catch(Throwable error){failed(error);}}

  final class Observed extends GeckoWebView {
    Observed(android.content.Context context,ChatSession owner){super(context,owner);}
    @Override GeckoSession newSession(){
      runtime.getSettings().setEnterpriseRootsEnabled(true);roots=runtime.getSettings().getEnterpriseRootsEnabled();
      GeckoSession sdk=super.newSession();GeckoSession.ProgressDelegate progress=sdk.getProgressDelegate();
      sdk.setProgressDelegate(new GeckoSession.ProgressDelegate(){
        public void onPageStart(GeckoSession source,String url){event("page-start",source,url);progress.onPageStart(source,url);}
        public void onPageStop(GeckoSession source,boolean success){event(success?"page-stop-true":"page-stop-false",source,loadingTargets.getOrDefault(source,""));progress.onPageStop(source,success);}
        public void onProgressChange(GeckoSession source,int value){progress.onProgressChange(source,value);}
        public void onSessionStateChange(GeckoSession source,GeckoSession.SessionState state){progress.onSessionStateChange(source,state);}
        public void onSecurityChange(GeckoSession source,SecurityInformation value){progress.onSecurityChange(source,value);try{
          if(!BrowserFingerprintFixture.A.equals(value.host))return;
          String leaf=value.certificate==null?"":BrowserFingerprintFixture.sha(value.certificate.getEncoded());
          securities.put(source,J.obj("host",value.host,"isSecure",value.isSecure,"isException",value.isException,"leafDerSha256",leaf,"enterpriseRootsReadback",roots));
          if(!roots||!value.isSecure||value.isException||!leaf.equals(getIntent().getStringExtra("expectedLeafSha256")))failed(new SecurityException("Native controlled TLS differs"));
        }catch(Throwable error){failed(error);}}
      });return sdk;
    }
  }
  void event(String kind,GeckoSession sdk,String url){if(terminal)return;if(events.length()>=80){failed(new IOException("Native event bound"));return;}
    events.put(J.obj("sequence",events.length()+1,"kind",kind,"targetOwned",TARGET.equals(url),"sessionId",AppSessionIdentity.id(sdk),"navigation",session==null?0:session.navigationEpoch));}
  void within()throws IOException{if(SystemClock.elapsedRealtime()>deadline)throw new IOException("Combined cold bootstrap timeout");}
  boolean ready(){if(session==null||remote==null||!remote.ready||!session.networkReady||session.connecting||session.navigating||!TARGET.equals(remote.getUrl())||!remote.hasVisibleDocument()||remote.ports.get(remote.current)==null||!roots)return false;
    JSONObject cpu=session.cpu.status(),zone=remote.timeZoneStatus();return "ready".equals(cpu.optString("state"))&&cpu.optBoolean("nativeSettingReadback")&&cpu.optBoolean("startupReconciled")&&Boolean.FALSE.equals(cpu.opt("rfpPriority"))&&zone.optBoolean("nativeSettingReadback")&&zone.optBoolean("ipMatched");}
  void tick(){if(terminal||capturing)return;try{within();
    if(!ready()){publish();probe.postDelayed(this::tick,75);return;}
    capturing=true;GeckoSession sdk=remote.current;GeckoRuntime runtime=remote.runtime;GeckoWebView.TimeZoneGate gate=remote.timeZoneGates.get(sdk);long navigation=session.navigationEpoch,document=gate==null?-1:gate.documentSerial;
    remote.evaluateJavascript("document.documentElement.getAttribute('data-gecko-cpu-ip-combo')",raw->{try{
      within();if(!owns(sdk,runtime,gate,navigation,document))throw new IOException("Combined native document changed");
      if(raw==null||raw.length()>20000)throw new IOException("Bounded first-inline sample absent");
      JSONObject value=GeckoEnvironmentPolicyIntegrationActivity.decoded(raw);
      if(!value.optBoolean("markerComplete")){capturing=false;probe.postDelayed(this::tick,75);return;}
      page=value;check("same-document.first-inline",value.getBoolean("firstInline")&&value.getBoolean("secure")&&nonce.equals(value.getString("runNonce"))&&build.getString("sourceCommit").equals(value.getString("sourceCommit")));
      check("same-document.native-cpu-one",value.getInt("hardwareConcurrency")==1&&value.getBoolean("nativeGetter"));
      check("same-document.native-new-york",GeckoEnvironmentPolicyIntegrationActivity.clockMatches(J.obj("page",value),"America/New_York"));
      check("same-document.network-marker",value.getBoolean("networkAllowed"));
      readNative(sdk,runtime,gate,navigation,document);
    }catch(Throwable error){failed(error);}});
  }catch(Throwable error){failed(error);}}
  boolean owns(GeckoSession sdk,GeckoRuntime runtime,GeckoWebView.TimeZoneGate gate,long navigation,long document){return !terminal&&session!=null&&!session.deleted&&remote!=null&&remote.current==sdk&&remote.runtime==runtime&&sdk.isOpen()&&remote.timeZoneGates.get(sdk)==gate&&gate!=null&&gate.documentSerial==document&&session.navigationEpoch==navigation&&TARGET.equals(remote.getUrl())&&remote.timeZoneAllows(sdk);}
  @SuppressWarnings("unchecked") GeckoTimeZoneStore.Ticket ticket()throws Exception{
    Field field=GeckoTimeZoneController.class.getDeclaredField("operations");field.setAccessible(true);Object operation=((Map<Object,Object>)field.get(session.timeZone)).get(remote.current);if(operation==null)throw new IOException("Actual timezone operation absent");
    Field token=operation.getClass().getDeclaredField("ticket");token.setAccessible(true);return (GeckoTimeZoneStore.Ticket)token.get(operation);
  }
  void readNative(GeckoSession sdk,GeckoRuntime runtime,GeckoWebView.TimeZoneGate gate,long navigation,long document)throws Exception{
    final GeckoTimeZoneStore.Ticket active=ticket();if(active==null)throw new IOException("Actual timezone ticket absent");
    String token=UUID.randomUUID().toString().replace("-","")+UUID.randomUUID().toString().replace("-","");
    remote.sendTimeZone(remote.routePort,sdk,gate,"timezoneRead","",token,raw->{try{
      JSONObject fresh=GeckoTimeZonePolicy.contextReadback(raw,token,AppSessionIdentity.id(sdk));
      if(!owns(sdk,runtime,gate,navigation,document)||!active.binding.contextId.equals(fresh.getString("contextId")))throw new IOException("Fresh exact context differs");
      // Read only the real SDK preference API. The independent page value
      // above is never substituted with this native preference response.
      new GeckoCpuNative(()->owns(sdk,runtime,gate,navigation,document)).read(cpu->{try{
        if(!owns(sdk,runtime,gate,navigation,document))throw new IOException("Fresh CPU runtime changed");
        freshCpu=J.obj("configuredCap",cpu.configuredCap,"defaultCap",cpu.defaultCap,"hasUserValue",cpu.hasUserValue,"rfpPriority",cpu.rfpPriority);
        writer.execute(()->{try{
          JSONObject receipt=GeckoTimeZoneStore.lastReceipt(session.context,active);GeckoTimeZoneStore.State zone=GeckoTimeZoneStore.load(session.context);GeckoCpuStore.State desired=GeckoCpuStore.load(session.context);
          JSONObject stored=J.obj("identity",desired.identity.json(),"revision",desired.revision,"spec",desired.spec.json());
          probe.post(()->{try{within();if(!owns(sdk,runtime,gate,navigation,document))throw new IOException("Stored combined owner changed");
            cpuStored=stored;nativeProof=J.obj("sessionId",AppSessionIdentity.id(sdk),"sessionEpoch",active.binding.sessionEpoch,"contextId",fresh.getString("contextId"),"freshReadback",fresh,"receipt",receipt,"desiredSpec",zone.spec.json(),"desiredRevision",zone.revision,"identity",zone.identity.json(),"status",remote.timeZoneStatus(),"routeStamp",remote.ipRouteStamp(),"nativeRfpConfirmed",remote.nativeProtection.confirmed()&&remote.fingerprintingProtected,"privacyLevel",session.privacy.level());
            check("production.native-preferences",cpu.configuredCap==1&&cpu.defaultCap==1&&!cpu.hasUserValue&&!cpu.rfpPriority);
            check("production.default-ip-durable",zone.spec.followsIp()&&zone.revision==1&&receipt.getBoolean("nativeSettingReadback")&&remote.timeZoneStatus().optBoolean("ipMatched"));
            check("production.cpu-desired-durable",desired.revision==2&&"1".equals(desired.spec.mode)&&desired.identity.equals(zone.identity));
            check("production.generic-no-gpt",!session.chatAutomationAllowed()&&session.driverTarget()==null);
            if(securities.get(sdk)==null)throw new IOException("Actual native TLS observation absent");
            terminal=true;stage="complete";publish();
          }catch(Throwable error){failed(error);}});
        }catch(Throwable error){probe.post(()->failed(error));}});
      }catch(Throwable error){failed(error);}},this::failed);
    }catch(Throwable error){failed(error);}},this::failed);
  }
  void check(String id,boolean pass)throws Exception{checks.put(J.obj("id",id,"pass",pass));if(!pass)throw new AssertionError(id);}
  void failed(Throwable error){if(terminal)return;terminal=true;failure=error.getClass().getSimpleName();for(StackTraceElement frame:error.getStackTrace())if(frame.getClassName().startsWith(getClass().getName())){failure+="@"+frame.getMethodName()+":"+frame.getLineNumber();break;}stage="failed";try{publish();}catch(Exception ignored){}}
  void publish()throws Exception{if(build==null)return;JSONObject cpu=session==null?new JSONObject():session.cpu.status(),runtime=remote==null?new JSONObject():remote.nativeRuntimeCapabilities().optJSONObject("cpuPolicy");
    JSONObject value=J.obj("schema",1,"fixtureType","gecko-production-cpu-ip-combo-v1","status",terminal?(failure.isEmpty()?"passed":"failed"):"running","stage",stage,"failure",failure,"sourceCommit",build.getString("sourceCommit"),"sourceTree",build.getString("sourceTree"),"runNonce",nonce,"buildIdentity",build,"activityClass",getClass().getName(),"scopeAllocationActivity",IpTimeZoneFixtureScopes.ACTIVITY,
      "setup",setup,"cpuSetup",cpuSetup,"cpuStoredState",cpuStored,"process",J.obj("pid",android.os.Process.myPid(),"uid",android.os.Process.myUid(),"name",android.app.Application.getProcessName()),"page",page,"native",nativeProof,"cpuPolicy",cpu,"runtimeCpuPolicy",runtime==null?new JSONObject():runtime,"freshCpuReadback",freshCpu,"tls",remote==null||securities.get(remote.current)==null?new JSONObject():securities.get(remote.current),"checks",checks,"nativeEvents",events,"actualAndroidExecution",true,"actualGeckoExecution",remote!=null&&remote.runtime!=null,"productionChatSession",session!=null&&remote!=null&&session.web==remote&&remote instanceof Observed,
      "syntheticGeoService",true,"actualPublicIpGeolocationVerified",false,"workerCoverageVerified",false,"serviceWorkerCoverageVerified",false,"fingerprintProtectionVerified",false);
    byte[] raw=(value.toString()+"\n").getBytes(StandardCharsets.UTF_8);if(raw.length>524288)throw new IOException("Combined device report bound");
    AtomicFile file=new AtomicFile(new File(Profiles.global(this).getFilesDir(),FILE));FileOutputStream out=null;try{out=file.startWrite();out.write(raw);file.finishWrite(out);}catch(Exception error){if(out!=null)file.failWrite(out);throw error;}
  }
  @Override protected void onDestroy(){probe.removeCallbacksAndMessages(null);writer.shutdownNow();super.onDestroy();}
}
