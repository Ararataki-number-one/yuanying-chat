package local.pocketchat;

import org.json.*;

/** Executes the production projection with synthetic native/page facts. */
public final class EnvironmentIdentityStatusHost {
  static final String ENV="00000000-0000-0000-0000-000000000001",OTHER="00000000-0000-0000-0000-000000000002",ENGINE="Gecko/test";
  static final JSONArray checks=new JSONArray();
  static void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));if(!pass)throw new AssertionError(name);}
  static JSONObject copy(JSONObject value){return J.parse(value.toString());}
  static EnvironmentSpec initial(){return EnvironmentSpec.initial(new EnvironmentSpec.Identity(0,0,ENV),new EnvironmentSpec.Configuration(BrowserIdentitySpec.preset(BrowserIdentitySpec.MOBILE).json(),
      new EnvironmentSpec.NetworkBinding("internal","SECRET_SOURCE","SECRET_NODE","SECRET_EXIT_SOURCE","SECRET_EXIT_NODE","latency","SECRET_CREDENTIAL_REVISION")));}
  static EnvironmentSpec applied()throws Exception{return initial().withApplied(1,ENGINE,100);}
  static JSONObject protection(int level){return J.obj("state","confirmed","desiredLevel",level,"level",level,"generation",1,"token",1,"received",true,"settingsReadbackConfirmed",true,"observedFingerprinting",level>=2,"newRequestsBlocked",false,
      "scope","native-setting-new-request-admission","fullApiProtectionAttested",false,"reason","SECRET_ERROR");}
  static JSONObject report(){return J.obj("fresh",true,"identityAppliedRevision",1,"navigationEpoch",12,"sourcePageHash","PAGE_HASH","at",100,
      "observationMetadata",J.obj("environmentId",ENV,"environmentGeneration",0,"configurationRevision",1,"engineVersion",ENGINE),
      "signals",J.obj("provenance","page-main-world","mainWorld",J.obj("observed",true)),
      "rows",J.arr(J.obj("state","verified","detail","SECRET_DETAIL"),J.obj("state","available"),J.obj("state","restricted"),J.obj("state","uncovered")),
      "token","SECRET_TOKEN","proxy","https://SECRET_USER:SECRET_PASSWORD@invalid.example:443");}
  static JSONObject runtime(){return J.obj("environmentId",ENV,"environmentGeneration",0,"slot",0,"engineVersion",ENGINE,
      "policyAcknowledged",true,"acceptedBrowserIdentity",BrowserIdentitySpec.preset(BrowserIdentitySpec.MOBILE).json(),"protectionStatus",protection(1),
      "routeAdmitted",true,"queuePending",false,"queueUnavailable",false,"pagePresent",true,"navigationEpoch",12,"sourcePageHash","PAGE_HASH","reportCurrent",true,"report",report());}
  static JSONObject project(JSONObject value)throws Exception{return EnvironmentIdentityStatus.project(applied(),value);}
  public static void main(String[] args)throws Exception{
    JSONObject empty=EnvironmentIdentityStatus.project(null,runtime());
    check("missing configuration stays unavailable",empty.optString("state").equals("configuration-unavailable")&&!empty.optBoolean("browserConfirmed"));
    check("missing runtime cannot confirm",EnvironmentIdentityStatus.project(applied(),null).optString("state").equals("configuration-unavailable"));
    JSONObject r=runtime();r.put("environmentId",OTHER);JSONObject value=project(r);
    check("another environment hides prior descriptor",value.optString("state").equals("environment-changed")&&!value.has("desired")&&!value.has("networkMode"));
    r=runtime();r.put("environmentGeneration",1);check("new incarnation rejects prior config",project(r).optString("state").equals("environment-changed"));
    r=runtime();r.put("slot",1);check("different slot rejects prior config",project(r).optString("state").equals("environment-changed"));
    r=runtime();r.put("environmentGeneration","0");check("coercible owner counter is rejected",project(r).optString("state").equals("environment-changed"));
    value=EnvironmentIdentityStatus.project(initial(),runtime());
    check("saved configuration remains pending until applied",value.optString("state").equals("pending-application")&&value.optLong("appliedRevision")==0);
    r=runtime();r.put("queueUnavailable",true);check("failed durable queue is not awaiting success",project(r).optString("state").equals("saved-queue-failed"));
    r=runtime();r.put("queuePending",true);check("pending safe application is explicit",project(r).optString("state").equals("pending-application"));
    r=runtime();r.put("policyAcknowledged",false);check("SDK acknowledgement is required",project(r).optString("state").equals("awaiting-browser-confirmation"));
    r=runtime();r.put("policyAcknowledged","true");check("string acknowledgement cannot confirm",!project(r).optBoolean("browserConfirmed"));
    r=runtime();r.put("engineVersion","another-engine");check("another engine cannot reuse applied receipt",!project(r).optBoolean("browserConfirmed"));
    r=runtime();r.put("acceptedBrowserIdentity",BrowserIdentitySpec.preset(BrowserIdentitySpec.DESKTOP).json());check("other browser template cannot confirm applied config",!project(r).optBoolean("browserConfirmed"));
    r=runtime();r.getJSONObject("acceptedBrowserIdentity").put("userAgent","SECRET_CUSTOM_AGENT");check("unsupported accepted identity is not echoed",!project(r).has("applied"));
    r=runtime();r.getJSONObject("protectionStatus").put("state","failed").put("settingsReadbackConfirmed",false);value=project(r);
    check("failed native protection is visible",value.optString("state").equals("protection-failed")&&!value.optBoolean("browserConfirmed"));
    check("summary keeps native confirmation failure separate",EnvironmentIdentityStatus.summary(value).contains("原生保护：未确认（设置确认失败）"));
    r=runtime();r.getJSONObject("protectionStatus").put("observedFingerprinting",true);check("opposite native setting cannot confirm",!project(r).optBoolean("nativeProtectionConfirmed"));
    r=runtime();r.getJSONObject("protectionStatus").put("desiredLevel",2);check("wrong desired native level cannot confirm",!project(r).optBoolean("nativeProtectionConfirmed"));
    r=runtime();r.getJSONObject("protectionStatus").put("token",0);check("missing positive native token cannot confirm",!project(r).optBoolean("nativeProtectionConfirmed"));
    r=runtime();r.put("routeAdmitted",false);value=project(r);
    check("browser confirmation is distinct from route admission",value.optString("state").equals("route-unconfirmed")&&value.optBoolean("browserConfirmed")&&!value.optBoolean("pageObservationCurrent"));
    r=runtime();r.remove("report");value=project(r);
    check("native confirmation does not invent a webpage observation",value.optString("state").equals("browser-confirmed")&&value.optString("observationState").equals("not-observed"));
    value=project(runtime());
    check("current owned document is associated with its applied revision",value.optString("state").equals("observed")&&value.optBoolean("pageObservationCurrent")&&value.optLong("pageConfigurationRevision")==1);
    check("limited observation counts retain uncovered fields",value.optInt("observedFields")==3&&value.optInt("differentFields")==0&&value.optInt("uncoveredFields")==1);
    check("projection never attests complete protection",Boolean.FALSE.equals(value.opt("fullApiProtectionAttested"))&&Boolean.FALSE.equals(value.opt("leakVerdict")));
    r=runtime();r.getJSONObject("report").getJSONArray("rows").put(J.obj("state","issue"));value=project(r);
    check("current differences are explicit",value.optString("state").equals("observed-difference")&&value.optInt("differentFields")==1);
    r=runtime();r.getJSONObject("report").getJSONObject("signals").put("provenance","extension-isolated-world-fallback");value=project(r);
    check("isolated-world fallback never becomes current page evidence",value.optString("state").equals("browser-confirmed")&&value.optString("observationState").equals("page-unavailable")&&!value.optBoolean("pageObservationCurrent")&&value.optLong("pageConfigurationRevision")==0);
    check("fallback keeps native confirmation and bounded diagnostics",value.optBoolean("browserConfirmed")&&value.optBoolean("nativeProtectionConfirmed")&&value.optInt("observedFields")==3&&value.optInt("uncoveredFields")==1);
    check("fallback summary states missing page-world observation",EnvironmentIdentityStatus.summary(value).contains("未取得网页主执行环境观测"));
    r=runtime();r.getJSONObject("report").remove("signals");check("missing signals cannot become current page evidence",project(r).optString("observationState").equals("page-unavailable"));
    r=runtime();r.getJSONObject("report").put("signals","page-main-world");check("wrong signals type cannot become current page evidence",project(r).optString("observationState").equals("page-unavailable"));
    r=runtime();r.getJSONObject("report").getJSONObject("signals").remove("mainWorld");check("missing main-world receipt cannot become page evidence",!project(r).optBoolean("pageObservationCurrent"));
    r=runtime();r.getJSONObject("report").getJSONObject("signals").put("mainWorld",true);check("wrong main-world receipt type cannot become page evidence",!project(r).optBoolean("pageObservationCurrent"));
    r=runtime();r.getJSONObject("report").getJSONObject("signals").getJSONObject("mainWorld").put("observed",false);check("explicit page-world sampling failure remains unavailable",!project(r).optBoolean("pageObservationCurrent"));
    r=runtime();r.getJSONObject("report").getJSONObject("signals").getJSONObject("mainWorld").put("observed","true");check("string observed flag cannot become page evidence",!project(r).optBoolean("pageObservationCurrent"));
    r=runtime();r.getJSONObject("report").getJSONObject("signals").remove("provenance");check("missing provenance cannot become page evidence",!project(r).optBoolean("pageObservationCurrent"));
    r=runtime();r.put("reportCurrent",false);value=project(r);
    check("live audit freshness is required",!value.optBoolean("pageObservationCurrent")&&value.optString("observationState").equals("historical"));
    r=runtime();r.put("pagePresent",false);check("no current visible document means no current observation",!project(r).optBoolean("pageObservationCurrent"));
    r=runtime();r.getJSONObject("report").put("fresh",false);check("stored fresh=false cannot be promoted",!project(r).optBoolean("pageObservationCurrent"));
    r=runtime();r.getJSONObject("report").getJSONObject("observationMetadata").put("environmentId",OTHER);check("foreign report cannot confirm same-revision page",!project(r).optBoolean("pageObservationCurrent"));
    r=runtime();r.getJSONObject("report").getJSONObject("observationMetadata").put("environmentGeneration",1);check("old incarnation reports are rejected",!project(r).optBoolean("pageObservationCurrent"));
    r=runtime();r.getJSONObject("report").getJSONObject("observationMetadata").put("configurationRevision",2);check("metadata revision mismatch remains historical",!project(r).optBoolean("pageObservationCurrent"));
    r=runtime();r.getJSONObject("report").put("identityAppliedRevision",2);check("report revision mismatch remains historical",!project(r).optBoolean("pageObservationCurrent"));
    r=runtime();r.getJSONObject("report").getJSONObject("observationMetadata").put("engineVersion","other");check("report engine mismatch remains historical",!project(r).optBoolean("pageObservationCurrent"));
    r=runtime();r.getJSONObject("report").put("navigationEpoch",13);check("same URL newer document cannot reuse prior observation",!project(r).optBoolean("pageObservationCurrent"));
    r=runtime();r.put("navigationEpoch",12.5);check("fractional navigation counter cannot associate",!project(r).optBoolean("pageObservationCurrent"));
    r=runtime();r.getJSONObject("report").put("sourcePageHash","OLD_PAGE");check("different page hash cannot associate",!project(r).optBoolean("pageObservationCurrent"));
    r=runtime();r.put("sourcePageHash","");r.getJSONObject("report").put("sourcePageHash","");check("empty page identity cannot associate",!project(r).optBoolean("pageObservationCurrent"));
    r=runtime();r.getJSONObject("report").remove("observationMetadata");check("missing report owner remains historical",!project(r).optBoolean("pageObservationCurrent"));
    r=runtime();r.getJSONObject("report").put("rows",new JSONArray());check("empty result does not claim an observation",project(r).optString("observationState").equals("incomplete"));
    r=runtime();JSONArray large=new JSONArray();for(int i=0;i<257;i++)large.put(J.obj("state","verified"));r.getJSONObject("report").put("rows",large);check("row traversal has a fixed bound",project(r).optString("observationState").equals("incomplete"));
    r=runtime();r.getJSONObject("report").put("rows",J.arr(JSONObject.NULL,J.obj("state","unknown")));value=project(r);
    check("unknown result states remain uncovered",value.optInt("observedFields")==0&&value.optInt("uncoveredFields")==2);
    value=project(runtime());String output=value.toString()+EnvironmentIdentityStatus.summary(value);
    check("credential node and arbitrary report detail values are not projected",!output.contains("SECRET_")&&!output.contains("PAGE_HASH")&&!output.contains("proxy")&&!output.contains("token"));
    check("summary explains finite evidence",EnvironmentIdentityStatus.summary(value).contains("不代表全部指纹保护已通过"));
    check("summary distinguishes system language",EnvironmentIdentityStatus.summary(value).contains("跟随系统语言"));
    check("summary explicitly identifies native-setting readback scope",EnvironmentIdentityStatus.summary(value).contains("原生保护：已确认（原生设置回读）"));
    EnvironmentSpec explicit=EnvironmentSpec.initial(initial().identity,new EnvironmentSpec.Configuration(BrowserIdentitySpec.preset(BrowserIdentitySpec.MOBILE).withLocales(java.util.Arrays.asList("zh-CN","en-US")).json(),initial().desired().network)).withApplied(1,ENGINE,100);
    r=runtime();r.put("acceptedBrowserIdentity",explicit.applied().browser());value=EnvironmentIdentityStatus.project(explicit,r);
    check("explicit language list retains its selected order",EnvironmentIdentityStatus.summary(value).contains("zh-CN、en-US"));
    EnvironmentSpec enhanced=EnvironmentSpec.initial(initial().identity,new EnvironmentSpec.Configuration(BrowserIdentitySpec.preset(BrowserIdentitySpec.RFP).json(),initial().desired().network)).withApplied(1,ENGINE,100);
    r=runtime();r.put("acceptedBrowserIdentity",enhanced.applied().browser()).put("protectionStatus",protection(2));
    check("strict native confirmation requires enabled protection",EnvironmentIdentityStatus.project(enhanced,r).optBoolean("browserConfirmed"));
    r.getJSONObject("protectionStatus").put("observedFingerprinting",false);check("strict disabled readback cannot confirm",!EnvironmentIdentityStatus.project(enhanced,r).optBoolean("browserConfirmed"));
    JSONObject malformed=BrowserIdentitySpec.preset(BrowserIdentitySpec.MOBILE).json();malformed.put("userAgent","SECRET_AGENT");
    EnvironmentSpec invalid=EnvironmentSpec.initial(initial().identity,new EnvironmentSpec.Configuration(malformed,initial().desired().network));value=EnvironmentIdentityStatus.project(invalid,runtime());
    check("invalid saved template is explicit and hidden",value.optString("state").equals("configuration-invalid")&&!value.has("desired"));
    JSONObject original=runtime(),originalCopy=copy(original);project(original);check("projection never mutates live facts",original.toString().equals(originalCopy.toString()));
    System.out.println(J.obj("status","passed","passed",checks.length(),"checks",checks,"actualAndroidExecution",false,"actualUiExecution",false,"actualGeckoExecution",false,"fullApiProtectionAttested",false));
  }
}
