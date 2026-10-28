package local.pocketchat;

import org.json.*;

/** Read-only, credential-free view of the existing configuration acknowledgements.
 * The caller supplies current process/page facts; a stored setting or old report
 * can never stand in for a current native or document acknowledgement. */
final class EnvironmentIdentityStatus {
  static final int SCHEMA=1;
  private static final long MAX_COUNTER=9007199254740991L;

  private static boolean integer(Object value,long min,long max){
    if(!(value instanceof Number))return false;double number=((Number)value).doubleValue();
    return Double.isFinite(number)&&number>=min&&number<=max&&number==((Number)value).longValue();
  }
  private static boolean yes(JSONObject value,String key){return value!=null&&Boolean.TRUE.equals(value.opt(key));}
  private static JSONObject object(JSONObject value,String key){JSONObject selected=value==null?null:value.optJSONObject(key);return selected==null?new JSONObject():selected;}
  private static void put(JSONObject value,String key,Object item){try{value.put(key,item);}catch(JSONException invalid){throw new IllegalArgumentException(invalid);}}
  private static JSONObject initial(){return J.obj("schema",SCHEMA,"state","configuration-unavailable","observationState","unavailable","identityMatched",false,
      "desiredRevision",0,"appliedRevision",0,"observedRevision",0,"pageConfigurationRevision",0,"navigationEpoch",0,
      "browserConfirmed",false,"nativeProtectionConfirmed",false,"routeAdmitted",false,"pageObservationCurrent",false,
      "observedFields",0,"differentFields",0,"uncoveredFields",0,"fullApiProtectionAttested",false,"leakVerdict",false);}
  private static BrowserIdentitySpec browser(JSONObject raw){
    try{BrowserIdentitySpec value=BrowserIdentitySpec.from(raw);return raw!=null&&value.validate().isEmpty()?value:null;}catch(RuntimeException invalid){return null;}
  }
  private static JSONObject descriptor(BrowserIdentitySpec value){
    return J.obj("templateId",value.templateId,"display",value.display,"privacy",value.privacy,
        "languageStrategy",value.locales.isEmpty()?"system":"explicit","locales",new JSONArray(value.locales),"timezoneStrategy",value.timezoneStrategy);
  }
  private static boolean nativeConfirmed(JSONObject protection,int level){
    return "confirmed".equals(protection.optString("state"))&&yes(protection,"received")&&yes(protection,"settingsReadbackConfirmed")
        &&integer(protection.opt("desiredLevel"),level,level)&&integer(protection.opt("level"),level,level)
        &&protection.opt("observedFingerprinting")instanceof Boolean&&protection.optBoolean("observedFingerprinting")== (level>=2)
        &&integer(protection.opt("generation"),1,MAX_COUNTER)&&integer(protection.opt("token"),1,MAX_COUNTER);
  }

  /** Runtime is not persisted. Required ownership facts are environmentId,
   * environmentGeneration and slot. reportCurrent must be computed by the live
   * audit controller (execution/connection/policy/route); it is not a page claim.
   * Navigation, owner, engine and configuration are independently checked here. */
  static JSONObject project(EnvironmentSpec spec,JSONObject runtime){
    JSONObject out=initial();if(spec==null||runtime==null)return out;
    if(!spec.identity.environmentId.equals(runtime.opt("environmentId"))
        ||!integer(runtime.opt("environmentGeneration"),spec.identity.generation,spec.identity.generation)
        ||!integer(runtime.opt("slot"),spec.identity.slot,spec.identity.slot)){
      put(out,"state","environment-changed");return out;
    }
    put(out,"identityMatched",true);put(out,"slot",spec.identity.slot);put(out,"environmentGeneration",spec.identity.generation);
    put(out,"desiredRevision",spec.desiredRevision);put(out,"appliedRevision",spec.appliedRevision);put(out,"observedRevision",spec.observedRevision);
    if(integer(runtime.opt("navigationEpoch"),0,MAX_COUNTER))put(out,"navigationEpoch",runtime.optLong("navigationEpoch"));
    BrowserIdentitySpec desired=browser(spec.desired().browser());
    if(desired==null){put(out,"state","configuration-invalid");return out;}
    put(out,"desired",descriptor(desired));put(out,"networkMode",spec.desired().network.mode);
    put(out,"entrySelection",spec.desired().network.selectionMode);
    boolean route= yes(runtime,"routeAdmitted");put(out,"routeAdmitted",route);
    JSONObject protection=object(runtime,"protectionStatus");boolean nativeConfirmed=nativeConfirmed(protection,desired.protectionLevel());
    put(out,"nativeProtectionConfirmed",nativeConfirmed);
    String protectionState=protection.optString("state");put(out,"protectionState",("confirmed".equals(protectionState)||"failed".equals(protectionState))?protectionState:"pending");
    boolean accepted=false;
    if(spec.applied()!=null&&yes(runtime,"policyAcknowledged")&&spec.engineVersion.equals(runtime.opt("engineVersion"))){
      JSONObject raw=runtime.optJSONObject("acceptedBrowserIdentity");BrowserIdentitySpec actual=browser(raw);
      if(actual!=null){
        try{accepted=new EnvironmentSpec.Configuration(raw,spec.applied().network).equals(spec.applied());}catch(RuntimeException invalid){}
        if(accepted)put(out,"applied",descriptor(actual));
      }
    }
    put(out,"browserConfirmed",accepted&&nativeConfirmed);
    if(yes(runtime,"queueUnavailable")){put(out,"state","saved-queue-failed");return out;}
    if(spec.pending()||yes(runtime,"queuePending")){put(out,"state","pending-application");return out;}
    if("failed".equals(protectionState)&&!nativeConfirmed){put(out,"state","protection-failed");return out;}
    if(!accepted||!nativeConfirmed){put(out,"state","awaiting-browser-confirmation");return out;}
    if(!route){put(out,"state","route-unconfirmed");return out;}
    put(out,"state","browser-confirmed");
    JSONObject report=runtime.optJSONObject("report");
    if(report==null||report.length()==0){put(out,"observationState","not-observed");return out;}
    put(out,"observationState","historical");
    JSONObject metadata=object(report,"observationMetadata");
    if(!yes(runtime,"reportCurrent")||!yes(runtime,"pagePresent")||!yes(report,"fresh")
        ||!spec.identity.environmentId.equals(metadata.opt("environmentId"))
        ||!integer(metadata.opt("environmentGeneration"),spec.identity.generation,spec.identity.generation)
        ||!integer(metadata.opt("configurationRevision"),spec.appliedRevision,spec.appliedRevision)
        ||!spec.engineVersion.equals(metadata.opt("engineVersion"))
        ||!integer(report.opt("identityAppliedRevision"),spec.appliedRevision,spec.appliedRevision)
        ||!integer(runtime.opt("navigationEpoch"),0,MAX_COUNTER)
        ||!integer(report.opt("navigationEpoch"),runtime.optLong("navigationEpoch"),runtime.optLong("navigationEpoch"))
        ||!(runtime.opt("sourcePageHash")instanceof String)||runtime.optString("sourcePageHash").isEmpty()
        ||!runtime.optString("sourcePageHash").equals(report.opt("sourcePageHash")))return out;
    JSONObject signals=object(report,"signals");
    boolean pageObserved="page-main-world".equals(signals.opt("provenance"))&&yes(object(signals,"mainWorld"),"observed");
    if(!pageObserved)put(out,"observationState","page-unavailable");
    JSONArray rows=report.optJSONArray("rows");
    if(rows==null||rows.length()==0||rows.length()>256){if(pageObserved)put(out,"observationState","incomplete");return out;}
    int observed=0,different=0,uncovered=0;
    for(int i=0;i<rows.length();i++){
      JSONObject row=rows.optJSONObject(i);String state=row==null?"":row.optString("state");
      if("issue".equals(state)){observed++;different++;}
      else if("verified".equals(state)||"available".equals(state)||"restricted".equals(state))observed++;
      else uncovered++;
    }
    put(out,"observedFields",observed);put(out,"differentFields",different);put(out,"uncoveredFields",uncovered);
    // Fresh diagnostic rows can include native/network facts even when CSP
    // prevented page-world sampling. Keep those counts, never promote them to
    // a current page observation using isolated-world fallback values.
    if(!pageObserved)return out;
    put(out,"pageObservationCurrent",true);put(out,"pageConfigurationRevision",spec.appliedRevision);
    put(out,"observationState",different>0?"different":"observed");put(out,"state",different>0?"observed-difference":"observed");return out;
  }

  static String stateLabel(String state){
    switch(state){
      case "environment-changed":return "当前环境已改变，请重新打开详情";
      case "configuration-invalid":return "已保存配置无法核对，当前设置未改动";
      case "saved-queue-failed":return "已保存，应用排队失败，请重新保存模板";
      case "pending-application":return "已保存，等待安全应用";
      case "protection-failed":return "原生保护未确认，请查看保护状态";
      case "awaiting-browser-confirmation":return "已保存，等待浏览器确认";
      case "route-unconfirmed":return "浏览器设置已确认，当前连接尚未获准";
      case "browser-confirmed":return "浏览器设置已确认，页面仍需观测";
      case "observed-difference":return "设置已确认，当前页面观测存在差异";
      case "observed":return "设置已确认，当前页面已有观测";
      default:return "环境配置暂未读取";
    }
  }
  private static String label(JSONObject value){
    String mode="desktop".equals(value.optString("display"))?"电脑版":"手机版";
    String privacy=value.optString("privacy");return ("native-rfp".equals(privacy)?"强化":"compatibility".equals(privacy)?"兼容":"标准")+mode;
  }
  static String summary(JSONObject status){
    JSONObject value=status==null?initial():status;StringBuilder text=new StringBuilder("身份状态：").append(stateLabel(value.optString("state")));
    if(!yes(value,"identityMatched"))return text.toString();
    JSONObject desired=value.optJSONObject("desired");if(desired==null)return text.toString();
    text.append("\n保存模板：").append(label(desired));JSONObject applied=value.optJSONObject("applied");
    text.append("\n浏览器模板：").append(applied==null?"尚未确认":label(applied));
    text.append("\n原生保护：").append(yes(value,"nativeProtectionConfirmed")?"已确认（原生设置回读）":"failed".equals(value.optString("protectionState"))?"未确认（设置确认失败）":"等待当前配置确认");
    JSONArray locales=desired.optJSONArray("locales");text.append("\n语言策略：");
    if("system".equals(desired.optString("languageStrategy")))text.append("跟随系统语言");
    else{for(int i=0;locales!=null&&i<locales.length();i++){if(i>0)text.append("、");text.append(locales.optString(i));}}
    text.append("\n线路归属：").append("internal".equals(value.optString("networkMode"))?"当前环境的应用内线路":"当前环境的外部网络");
    text.append(yes(value,"routeAdmitted")?"（连接已获准）":"（连接待核对）");
    text.append("\n配置版本：保存 ").append(value.optLong("desiredRevision")).append(" / 应用 ").append(value.optLong("appliedRevision")).append(" / 记录观测 ").append(value.optLong("observedRevision"));
    text.append("\n当前页面关联版本：").append(value.optLong("pageConfigurationRevision")>0?String.valueOf(value.optLong("pageConfigurationRevision")):"尚未关联");
    if(yes(value,"pageObservationCurrent"))text.append("\n本次观测：").append(value.optInt("observedFields")).append(" 项已观察，").append(value.optInt("differentFields")).append(" 项差异，").append(value.optInt("uncoveredFields")).append(" 项未覆盖");
    else if("historical".equals(value.optString("observationState")))text.append("\n最近自检：历史结果，请在当前页面重新检查");
    else if("page-unavailable".equals(value.optString("observationState")))text.append("\n最近自检：未取得网页主执行环境观测，请查看诊断；原生设置确认单独保留");
    else if("incomplete".equals(value.optString("observationState")))text.append("\n最近自检：数据不完整，请重新检查");
    return text.append("\n设置确认与页面观测分别记录，不代表全部指纹保护已通过。").toString();
  }
}
