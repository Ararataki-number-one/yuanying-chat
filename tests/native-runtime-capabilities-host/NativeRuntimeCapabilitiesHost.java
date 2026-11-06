package local.pocketchat;
import java.util.*;import java.net.HttpURLConnection;import org.json.*;import org.mozilla.geckoview.*;
/** Exact production adapter/members with controlled SDK setting objects; no native-process proof. */
public class NativeRuntimeCapabilitiesHost {
 static final JSONArray checks=new JSONArray();
 static final JSONArray cpuBoundaryResults=new JSONArray();
 static void cpuBoundaryCheck(String name,boolean pass){cpuBoundaryResults.put(J.obj("name",name,"pass",pass));if(!pass)throw new AssertionError(name);}
 static boolean cpuBoundaryUnobserved(JSONObject value){
  if(!"unobserved".equals(value.optString("status"))||!"synthetic-unobserved-cpu-metadata-boundary".equals(value.optString("scope")))return false;
  for(String key:new String[]{"nativeSettingReadback","currentSessionPrepared","nativeApplied","pageApplied","pageObservationVerified","workerApplied","workerCoverageVerified","serviceWorkerApplied","serviceWorkerCoverageVerified"})if(!Boolean.FALSE.equals(value.opt(key)))return false;
  return true;
 }
 static void verifyCpuBoundary()throws Exception{
  UnobservedCpuMetadataBoundary cpu=new UnobservedCpuMetadataBoundary();JSONObject value=cpu.status();
  cpuBoundaryCheck("The CPU metadata collaborator is explicitly unobserved",value.optString("status").equals("unobserved")&&value.optString("scope").equals("synthetic-unobserved-cpu-metadata-boundary"));
  cpuBoundaryCheck("Unobserved CPU metadata grants no native readback preparation or application",Boolean.FALSE.equals(value.opt("nativeSettingReadback"))&&Boolean.FALSE.equals(value.opt("currentSessionPrepared"))&&Boolean.FALSE.equals(value.opt("nativeApplied")));
  cpuBoundaryCheck("Unobserved CPU metadata grants no page or Worker application",Boolean.FALSE.equals(value.opt("pageApplied"))&&Boolean.FALSE.equals(value.opt("pageObservationVerified"))&&Boolean.FALSE.equals(value.opt("workerApplied"))&&Boolean.FALSE.equals(value.opt("workerCoverageVerified"))&&Boolean.FALSE.equals(value.opt("serviceWorkerApplied"))&&Boolean.FALSE.equals(value.opt("serviceWorkerCoverageVerified")));
  boolean noValues=true;for(String key:new String[]{"configuredCap","defaultCap","hardwareConcurrency","desiredMode","desiredRevision","requestToken","nativeReceipt","receipt","ack"})noValues&=!value.has(key);
  cpuBoundaryCheck("Unobserved CPU metadata fabricates no preference count revision or acknowledgement",noValues);
  cpuBoundaryCheck("Serialized CPU boundary metadata retains only unobserved false claims",cpuBoundaryUnobserved(new JSONObject(value.toString())));
  ChatSession owner=route();JSONObject captured=owner.web.nativeRuntimeCapabilities().getJSONObject("cpuPolicy");
  cpuBoundaryCheck("The actual capability reader receives only the unobserved CPU metadata boundary",owner.cpu.statusCalls>0&&cpuBoundaryUnobserved(captured));
  value.put("nativeApplied",true);
  cpuBoundaryCheck("A caller cannot mutate a later CPU boundary observation",cpuBoundaryUnobserved(cpu.status()));
 }
 static void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));if(!pass)throw new AssertionError(name);}
 static JSONObject item(JSONObject value,String key){return value.optJSONObject("settings").optJSONObject(key);}
 static boolean unknown(JSONObject value,String key){JSONObject v=item(value,key);return v.optString("status").equals("unavailable")&&v.opt("value")==JSONObject.NULL;}
 static boolean scalar(JSONObject value,String key,Object wanted){JSONObject v=item(value,key);return v.optString("status").equals("sdk-value")&&Objects.equals(v.opt("value"),wanted);}
 static boolean unproven(JSONObject value){return value.opt("processUidVerified")==Boolean.FALSE&&value.opt("siteIsolationVerified")==Boolean.FALSE&&value.opt("statePartitionVerified")==Boolean.FALSE&&value.opt("fullSandboxVerified")==Boolean.FALSE&&"not-collected".equals(value.optString("processEvidence"))&&"not-collected".equals(value.optString("siteIsolationEvidence"))&&"not-collected".equals(value.optString("statePartitionEvidence"))&&"not-collected".equals(value.optString("sandboxEvidence"));}
 static ChatSession route(){ChatSession s=new ChatSession();s.web=new GeckoWebView(s);s.web.runtime=new GeckoRuntime();return s;}
 public static void main(String[] args)throws Exception{
  int creates=GeckoRuntime.created;JSONObject v=GeckoPolicyAdapter.runtimeCapabilityStatus(null,29);
  check("Null runtime does not create or open a runtime",GeckoRuntime.created==creates&&!v.optBoolean("runtimeAvailable"));
  check("Android 29 isolated renderer request is distinct from availability",v.optBoolean("isolatedRenderingRequested")&&unknown(v,"isolatedProcessEnabled"));
  for(String key:new String[]{"isolatedProcessEnabled","fissionEnabled","webContentIsolationStrategy","cookieBehavior","cookieBehaviorPrivateMode","cookieOptInPartitioning","cookieOptInPartitioningPrivateMode"})check("Null runtime leaves "+key+" unavailable",unknown(v,key));
  check("Unknown runtime never grants any process or sandbox proof",unproven(v));
  check("Android 28 does not invent an isolated renderer request",!GeckoPolicyAdapter.runtimeCapabilityStatus(null,28).optBoolean("isolatedRenderingRequested"));
  GeckoRuntime r=new GeckoRuntime();r.settings=null;v=GeckoPolicyAdapter.runtimeCapabilityStatus(r,29);
  check("Null SDK settings keep fixed unavailable states",v.optBoolean("runtimeAvailable")&&unknown(v,"fissionEnabled")&&unproven(v));
  r.failSettings=true;v=GeckoPolicyAdapter.runtimeCapabilityStatus(r,29);check("Settings exception text never enters diagnostic JSON",unknown(v,"isolatedProcessEnabled")&&!v.toString().contains("PRIVATE")&&!v.toString().contains("https://"));
  r=new GeckoRuntime();v=GeckoPolicyAdapter.runtimeCapabilityStatus(r,35);
  check("Nullable Fission preserves SDK default without treating it as disabled",item(v,"fissionEnabled").optString("status").equals("sdk-default-unobserved")&&item(v,"fissionEnabled").opt("value")==JSONObject.NULL);
  check("Nullable isolation strategy preserves SDK default",item(v,"webContentIsolationStrategy").optString("status").equals("sdk-default-unobserved")&&item(v,"webContentIsolationStrategy").opt("value")==JSONObject.NULL);
  check("Actual isolated-process setting is recorded only as SDK value",scalar(v,"isolatedProcessEnabled",true)&&unproven(v));
  check("Native cookie policy SDK number is preserved",scalar(v,"cookieBehavior",5)&&scalar(v,"cookieBehaviorPrivateMode",5));
  check("Opt-in partition flag is not confused with overall storage isolation",scalar(v,"cookieOptInPartitioning",false)&&scalar(v,"cookieOptInPartitioningPrivateMode",false)&&unproven(v));
  r.settings.fission=false;r.settings.isolation=0;v=GeckoPolicyAdapter.runtimeCapabilityStatus(r,35);
  check("Explicit false Fission is distinguished from SDK default",scalar(v,"fissionEnabled",false));
  check("Explicit zero strategy is not replaced by a guessed default",scalar(v,"webContentIsolationStrategy",0));
  r.settings.failFission=true;v=GeckoPolicyAdapter.runtimeCapabilityStatus(r,35);
  check("One getter failure only leaves its own fixed unavailable status",unknown(v,"fissionEnabled")&&scalar(v,"cookieBehavior",5));
  check("Getter exceptions do not export messages or URLs",!v.toString().contains("PRIVATE")&&!v.toString().contains("https://"));
  r.settings.failFission=false;r.settings.linkageFission=true;v=GeckoPolicyAdapter.runtimeCapabilityStatus(r,35);
  check("Missing linked getter stays unavailable without escaping",unknown(v,"fissionEnabled")&&scalar(v,"isolatedProcessEnabled",true));
  r.settings.content=null;v=GeckoPolicyAdapter.runtimeCapabilityStatus(r,35);
  check("Missing content-blocking object cannot invent cookie policy values",unknown(v,"cookieBehavior")&&unknown(v,"cookieBehaviorPrivateMode")&&scalar(v,"cookieOptInPartitioning",false));
  check("Read-only capture makes no runtime or content policy setter call",GeckoRuntimeSettings.writes==0&&ContentBlocking.Settings.writes==0);
  String text=GeckoPolicyAdapter.runtimeCapabilitySummary(GeckoPolicyAdapter.runtimeCapabilityStatus(new GeckoRuntime(),35));
  check("Advanced summary explicitly identifies SDK defaults and missing process evidence",text.contains("沿用 SDK 默认")&&text.contains("没有采集当前渲染进程 UID")&&text.contains("不代表完整沙箱已验证"));
  ChatSession s=route();GeckoWebView web=s.web;creates=GeckoRuntime.created;v=web.nativeRuntimeCapabilities();
  check("Owner access does not construct a replacement runtime",creates==GeckoRuntime.created&&web.nativeRuntimeIdentity()==web.runtime);
  check("Captured values retain exact environment and configuration ownership",v.optString("environmentId").equals("environment-a")&&v.optInt("environmentGeneration")==4&&v.optLong("configurationRevision")==11&&v.optLong("identityPolicyRevision")==7);
  check("Owner access does not mutate native or claimed security state",unproven(v)&&GeckoRuntimeSettings.writes==0&&ContentBlocking.Settings.writes==0);
  web.enabled=false;v=web.nativeRuntimeCapabilities();check("Disabled browser never reads a leftover runtime as current",web.nativeRuntimeIdentity()==null&&!v.optBoolean("runtimeAvailable")&&unknown(v,"fissionEnabled"));
  web.enabled=true;web.destroyed=true;v=web.nativeRuntimeCapabilities();check("Destroyed browser never reads a leftover runtime as current",web.nativeRuntimeIdentity()==null&&!v.optBoolean("runtimeAvailable"));
  web.destroyed=false;s.deleted=true;v=web.nativeRuntimeCapabilities();check("Deleted environment never reads its retired runtime",web.nativeRuntimeIdentity()==null&&!v.optBoolean("runtimeAvailable"));
  s=route();Audit a=new Audit(s);JSONObject expected=a.localExpected();
  check("Network identity expected fields do not inherit local native settings",!a.expected().has("nativeRuntimeCapabilities"));
  check("Existing expected report carries only current owner-bound native setting data",expected.getJSONObject("nativeRuntimeCapabilities").optLong("configurationRevision")==11&&expected.getJSONObject("nativeRuntimeCapabilities").optString("environmentId").equals("environment-a"));
  check("Same runtime and unchanged document retain the original freshness path",a.fresh());
  s.applied++;check("Applied configuration revision changes invalidate captured native settings",!a.fresh());s.applied--;
  s.web.runtime=new GeckoRuntime();check("Runtime replacement invalidates same-URL same-navigation report",!a.fresh());
  a.nativeRuntimeIdentity=s.web.nativeRuntimeIdentity();check("Capturing the current runtime restores only runtime freshness",a.fresh());
  s.web.enabled=false;check("Disabling the runtime invalidates a captured observation",!a.fresh());s.web.enabled=true;s.web.destroyed=true;check("Destroying the runtime invalidates a captured observation",!a.fresh());s.web.destroyed=false;s.deleted=true;check("Deleting the owner invalidates a captured observation",!a.fresh());s.deleted=false;
  s.navigationEpoch++;check("Existing navigation epoch freshness stays required",!a.fresh());s.navigationEpoch--;s.web.url="https://chatgpt.com/c/other";check("Existing document URL freshness stays required",!a.fresh());s.web.url=a.auditUrl;
  s.connectionEpoch++;check("Existing connection epoch freshness stays required",!a.fresh());s.connectionEpoch--;a.actualPolicy="changed";check("Existing identity policy freshness stays required",!a.fresh());a.actualPolicy=a.policy;a.actualRoute="changed";check("Existing route freshness stays required",!a.fresh());a.actualRoute=a.stamp;
  a.networkRun=true;s.networkReady=false;check("Network checks still require the admitted current network",!a.fresh());s.networkReady=true;s.guard.allowed=false;check("Network checks still require the existing network guard",!a.fresh());s.guard.allowed=true;s.web.protection=false;check("Network checks still require native protection admission",!a.fresh());
  a.cleanup();check("Completed or cancelled checks release the captured runtime reference",a.nativeRuntimeIdentity==null&&!a.running);
  check("All captures made no native policy setter call",GeckoRuntimeSettings.writes==0&&ContentBlocking.Settings.writes==0);
  verifyCpuBoundary();
  System.out.println(J.obj("status","passed","checks",checks.length(),"results",checks,"actualAndroidExecution",false,"actualGeckoExecution",false,"actualSdkApiCompile",false,"physicalPhoneAcceptance",false,"sandboxAcceptance",false,"cpuBoundaryChecks",cpuBoundaryResults.length(),"cpuBoundaryResults",cpuBoundaryResults,"actualCpuPolicyExecution",false,"actualCpuControllerExecution",false,"actualCpuNativeReadback",false,"actualCpuPageObservation",false,"actualCpuWorkerObservation",false));
 }
}
class ChatSession {Object context=new Object();String environmentId="environment-a";int environmentGeneration=4;long applied=11,navigationEpoch=3,connectionEpoch=9;boolean deleted,networkReady=true,offline;GeckoWebView web;Guard guard=new Guard();Privacy privacy=new Privacy();final SystemTimeZoneBoundary timeZone=new SystemTimeZoneBoundary();final UnobservedCpuMetadataBoundary cpu=new UnobservedCpuMetadataBoundary();long identityAuditAppliedRevision(){return applied;}boolean internalNetwork(){return false;}void updateBrowserActivity(){}}
/** Metadata-only collaborator for this capability reader. It instantiates no
 * CPU controller, native preference access, write, readback or acknowledgement.
 * Actual CPU policy/getter/Worker effects belong to their independent gates. */
class UnobservedCpuMetadataBoundary {
 int statusCalls;
 JSONObject status(){statusCalls++;return J.obj("status","unobserved","scope","synthetic-unobserved-cpu-metadata-boundary","nativeSettingReadback",false,"currentSessionPrepared",false,"nativeApplied",false,"pageApplied",false,"pageObservationVerified",false,"workerApplied",false,"workerCoverageVerified",false,"serviceWorkerApplied",false,"serviceWorkerCoverageVerified",false);}
}
/** Independent default-system policy boundary only; native timezone writes,
 * readback, custom-zone page observations and lifecycle stamps are tested by
 * their separate current-policy hosts, not by this SDK capability reader. */
class SystemTimeZoneBoundary {
 final boolean followsSystem=true;int expectedCalls,statusCalls;
 JSONObject auditExpected(JSONObject expected){expectedCalls++;if(!followsSystem)throw new AssertionError("Custom timezone audit is outside this system-policy capability fixture");return expected;}
 JSONObject status(){statusCalls++;return J.obj("mode","system","scope","synthetic-system-timezone-boundary","nativeSettingReadback",false,"currentSessionPrepared",false,"workerCoverageVerified",false,"serviceWorkerCoverageVerified",false);}
}
class Privacy{int level(){return 1;}}
class Guard{boolean allowed=true;boolean allowed(){return allowed;}}
class NativeNetwork{long lastVerified=0;String exitIp="";static NativeNetwork get(Object context){return new NativeNetwork();}}
class GeckoSettings{boolean desktop,rfpAcknowledged;final JSONObject requestHeaderPolicy=J.obj("installed",false,"nativeReadback",false,"scope","public-http-request-ua-only","privateAdmission","unchanged-original-headers","sharedWorkerWireVerified",false,"serviceWorkerWireVerified",false);String[] requestedLocales={"zh-CN"},expectedSdkLocales={"zh-CN"};String getUserAgentString(){return "Firefox/157";}}
class GeckoWebView{
 static final String VERSION="GeckoView 157.0.1 · 输入同步修正";final ChatSession owner;boolean destroyed,enabled=true,protection=true;GeckoRuntime runtime;long identityPolicyRevision=7;String url="https://chatgpt.com/c/current";GeckoSettings metadata=new GeckoSettings();GeckoWebView(ChatSession s){owner=s;}GeckoSettings getSettings(){return metadata;}String getUrl(){return url;}String identityLanguage(){return "zh-CN";}void cancelEnvironmentAudit(){}boolean protectionAllowsNetwork(){return protection;}
 JSONObject timeZoneStatus(){return owner.timeZone.status();}
 /* NATIVE_OWNER */
}
class Audit{
 final ChatSession session;boolean running=true,geckoRun=true,networkRun;Object nativeRuntimeIdentity;java.util.concurrent.Future<?> nativeWork;java.net.HttpURLConnection connection;java.util.concurrent.ExecutorService closer;long auditNavigation=3,epoch=9,identityAppliedRevision=11;String auditUrl="https://chatgpt.com/c/current",stamp="route",policy="policy",actualRoute="route",actualPolicy="policy";Audit(ChatSession s){session=s;nativeRuntimeIdentity=s.web.nativeRuntimeIdentity();}String routeStamp(){return actualRoute;}String policyStamp(){return actualPolicy;}String packageVersion(){return "157.0.1";}
 /* AUDIT_FRESH */
 /* AUDIT_EXPECTED */
 /* AUDIT_LOCAL_EXPECTED */
 /* AUDIT_CLEANUP */
}
