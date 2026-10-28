package local.pocketchat;

import org.json.*;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.*;

/** Two explicitly saved local observations, never a protection score or phone attestation. */
final class FingerprintReportComparison {
  static final int SCHEMA=1,MAX_BYTES=65536,MAX_SNAPSHOT_BYTES=28672,MAX_EXPORT_BYTES=90112;
  static final String KIND="local-standard-enhanced-observation-pair";
  static final String SNAPSHOT_KIND="explicit-mode-deep-observation";
  static final String[] SLOTS={"standard","enhanced"};
  static final String[] CONTEXTS={"main","worker","frame","crossOriginFrame"};
  static final String[] MANUAL_KEYS={"login","input","attachment","drawing","recovery","restart","background"};
  static final String[] MANUAL_STATES={"not-tested","pass","fail","not-applicable"};
  static final String[] GROUP={"environmentId","environmentGeneration","configurationRevision","engineVersion","appVersion","appVersionCode","sourceOrigin","executionId"};
  private static final long MAX_COUNTER=9007199254740991L;

  static JSONObject object(JSONObject o,String key){return FingerprintObservationHistory.object(o,key);}
  static void put(JSONObject o,String key,Object value){FingerprintObservationHistory.put(o,key,value);}
  static JSONObject copy(JSONObject o){return FingerprintObservationHistory.copy(o);}
  static boolean integer(Object value,long min,long max){return FingerprintObservationHistory.integer(value,min,max);}
  static boolean text(Object value,int max){return value instanceof String&&!((String)value).isEmpty()&&((String)value).length()<=max;}
  static boolean member(String value,String[] allowed){return Arrays.asList(allowed).contains(value);}
  static boolean bounded(JSONObject value,int max){try{return value!=null&&value.toString()!=null&&value.toString().getBytes(StandardCharsets.UTF_8).length<=max;}catch(RuntimeException invalid){return false;}}
  static boolean owner(String id,int generation){return id!=null&&id.matches("[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")&&generation>=0;}
  static JSONObject empty(String id,int generation){return owner(id,generation)?J.obj("schema",SCHEMA,"kind",KIND,"environmentId",id,"environmentGeneration",generation,"slots",new JSONObject(),"protectionVerified",false,"leakVerdict",false,"physicalPhoneAcceptance",false):new JSONObject();}
  static JSONObject group(JSONObject value){JSONObject out=new JSONObject();for(String key:GROUP)put(out,key,value.opt(key));return out;}
  static boolean same(Object a,Object b){return FingerprintObservationHistory.same(a,b);}
  static String slotLabel(String slot){return "enhanced".equals(slot)?"强化":"标准";}
  static String contextLabel(String value){switch(value){case "worker":return "Dedicated Worker";case "frame":return "同源 iframe";case "crossOriginFrame":return "跨源 iframe";default:return "主页面";}}
  static String manualLabel(String value){switch(value){case "login":return "登录";case "input":return "输入法与输入（含百度输入法）";case "attachment":return "附件";case "drawing":return "绘图";case "recovery":return "页面恢复";case "restart":return "重启";default:return "后台返回";}}
  static String manualStateLabel(String value){switch(value){case "pass":return "人工记录正常";case "fail":return "人工记录异常";case "not-applicable":return "人工记录不适用";default:return "未测试";}}
  static String confirmationLabel(JSONObject value){switch(value.optString("state")){case "confirmed":return "设置回读已确认";case "failed":return "设置确认失败";default:return "设置尚未确认";}}

  private static JSONArray locales(Object input){
    if(!(input instanceof JSONArray)||((JSONArray)input).length()>8)return null;
    JSONArray out=new JSONArray();Set<String> seen=new HashSet<>();JSONArray list=(JSONArray)input;
    for(int i=0;i<list.length();i++){Object raw=list.opt(i);if(!text(raw,64)||!((String)raw).matches("[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*")||!seen.add(((String)raw).toLowerCase(Locale.ROOT)))return null;out.put(raw);}
    return out;
  }
  private static JSONObject template(JSONObject metadata,String slot){
    String id=metadata.optString("templateId"),display=metadata.optString("display");
    String wanted="enhanced".equals(slot)?"native-rfp":"standard";
    BrowserIdentitySpec spec;try{spec=BrowserIdentitySpec.preset(id);}catch(RuntimeException invalid){return null;}
    if(!wanted.equals(spec.privacy)||!display.equals(spec.display))return null;
    JSONArray requested=locales(metadata.opt("requestedLocales")),expected=locales(metadata.opt("expectedLocales"));if(requested==null||expected==null)return null;
    return J.obj("templateId",id,"display",display,"requestedLocales",requested,"expectedLocales",expected);
  }
  private static JSONObject settings(JSONObject raw,int desired){
    if(raw==null||!integer(raw.opt("desiredLevel"),desired,desired)||!integer(raw.opt("level"),-1,2)
        ||!integer(raw.opt("generation"),0,MAX_COUNTER)||!integer(raw.opt("token"),0,MAX_COUNTER)
        ||!integer(raw.opt("attempt"),0,3)||!integer(raw.opt("maxAttempts"),3,3)
        ||!"native-setting-new-request-admission".equals(raw.optString("scope"))||!Boolean.FALSE.equals(raw.opt("fullApiProtectionAttested")))return null;
    String state=raw.optString("state"),reason=raw.optString("reason");
    if(!Arrays.asList("confirmed","pending","failed").contains(state)||!(raw.opt("reason") instanceof String)||!reason.isEmpty()&&!reason.matches("[a-z][a-z0-9-]{0,63}"))return null;
    for(String key:new String[]{"received","settingsReadbackConfirmed","observedFingerprinting","newRequestsBlocked"})if(!(raw.opt(key) instanceof Boolean))return null;
    boolean confirmed="confirmed".equals(state);
    if(confirmed!=raw.optBoolean("settingsReadbackConfirmed")||confirmed&&(!raw.optBoolean("received")||raw.optInt("level")!=desired
        ||raw.optBoolean("observedFingerprinting")!=(desired>=2)||raw.optLong("generation")<1||raw.optLong("token")<1||raw.optInt("attempt")<1))return null;
    JSONObject out=J.obj("scope","native-setting-new-request-admission","fullApiProtectionAttested",false);
    for(String key:new String[]{"state","desiredLevel","level","generation","token","attempt","maxAttempts","reason","received","settingsReadbackConfirmed","observedFingerprinting","newRequestsBlocked"})put(out,key,raw.opt(key));
    return out;
  }
  private static boolean metadataMatches(JSONObject report,JSONObject metadata){
    JSONObject original=report.optJSONObject("observationMetadata");if(original==null)return false;
    for(String key:GROUP){Object a=original.opt(key),b=metadata.opt(key);if("sourceOrigin".equals(key)){if(!FingerprintObservationHistory.origin(a).equals(FingerprintObservationHistory.origin(b)))return false;}else if(!same(a,b))return false;}
    for(String key:new String[]{"templateId","display","requestedLocales","expectedLocales"})if(original.has(key)&&!same(original.opt(key),metadata.opt(key)))return false;
    JSONObject expected=object(report,"expected");
    if(expected.has("requestedLocales")&&!same(expected.opt("requestedLocales"),metadata.opt("requestedLocales")))return false;
    if(expected.has("expectedSdkLocales")&&!same(expected.opt("expectedSdkLocales"),metadata.opt("expectedLocales")))return false;
    if(expected.has("templateId")&&!same(expected.opt("templateId"),metadata.opt("templateId")))return false;
    return true;
  }
  private static JSONObject candidate(JSONObject report,JSONObject metadata,String slot,long savedAt){
    if(!member(slot,SLOTS)||report==null||metadata==null||!integer(savedAt,1,Long.MAX_VALUE)
        ||!metadataMatches(report,metadata)||!Boolean.TRUE.equals(report.opt("fresh")))return null;
    for(String flag:new String[]{"apiProtectionVerified","fingerprintTemplateAcceptance","physicalPhoneAcceptance"})if(report.has(flag)&&!Boolean.FALSE.equals(report.opt(flag)))return null;
    int level="enhanced".equals(slot)?2:1;
    if(!integer(object(report,"expected").opt("level"),level,level)||!integer(report.opt("identityAppliedRevision"),1,MAX_COUNTER)||!integer(metadata.opt("appVersionCode"),1,MAX_COUNTER)
        ||!same(report.opt("identityAppliedRevision"),metadata.opt("configurationRevision"))
        ||!text(report.opt("executionId"),128)||!same(report.opt("executionId"),metadata.opt("executionId")))return null;
    JSONObject descriptor=template(metadata,slot),nativeSettings=settings(report.optJSONObject("nativeProtection"),level);
    if(descriptor==null||nativeSettings==null)return null;
    JSONObject contexts=new JSONObject();
    for(String context:CONTEXTS){JSONObject observation=FingerprintContextBaselines.contextSnapshot(report,metadata,context);if(observation!=null&&observation.length()>0)put(contexts,context,observation);}
    JSONObject main=contexts.optJSONObject("main");if(main==null)return null;
    JSONObject manual=new JSONObject(),manualTimes=new JSONObject();for(String key:MANUAL_KEYS){put(manual,key,"not-tested");put(manualTimes,key,0);}
    JSONObject out=J.obj("schema",SCHEMA,"kind",SNAPSHOT_KIND,"slot",slot,"savedAt",savedAt,"group",group(object(main,"observation")),
        "template",descriptor,"nativeSettings",nativeSettings,"contexts",contexts,"publicValues",FingerprintObservationHistory.core(object(object(report,"signals"),"parent")),
        "compatibility",manual,"compatibilityUpdatedAt",manualTimes,"compatibilitySource","user-entered-not-independent-verification",
        "samePhysicalPhoneVerified",false,"protectionVerified",false,"leakVerdict",false,"physicalPhoneAcceptance",false);
    if(report.has("route")){Object hash=report.opt("route");if(!(hash instanceof String)||!((String)hash).matches("[0-9a-f]{64}"))return null;put(out,"routeHash",hash);}
    return bounded(out,MAX_SNAPSHOT_BYTES)?out:null;
  }
  static String captureIssue(JSONObject report,JSONObject metadata,String slot){
    if(!member(slot,SLOTS))return "请选择标准或强化报告槽位";
    if(report==null||metadata==null||!Boolean.TRUE.equals(report.opt("fresh")))return "请先完成当前网页的有效图形与音频深检";
    int level="enhanced".equals(slot)?2:1;
    if(!integer(object(report,"expected").opt("level"),level,level))return "本次实际保护模式与"+slotLabel(slot)+"槽位不一致，请切换模式并重新深检";
    return candidate(report,metadata,slot,1)==null?"本次报告的来源、配置、执行环境或设置回执不完整，未保存对照":"";
  }
  static JSONObject record(JSONObject saved,String slot,JSONObject report,JSONObject metadata,long now){
    JSONObject value=candidate(report,metadata,slot,now);if(value==null)return null;
    JSONObject owner=object(value,"group");
    if(saved!=null&&saved.length()>0&&(!same(saved.opt("environmentId"),owner.opt("environmentId"))||!same(saved.opt("environmentGeneration"),owner.opt("environmentGeneration"))))return null;
    JSONObject out=restore(saved,owner.optString("environmentId"),owner.optInt("environmentGeneration",-1));
    if(out.length()==0)return null;put(object(out,"slots"),slot,value);return bounded(out,MAX_BYTES)?out:null;
  }
  private static JSONObject restoreSnapshot(JSONObject saved,String slot,String environmentId,int generation){
    if(!bounded(saved,MAX_SNAPSHOT_BYTES)||!integer(saved.opt("schema"),SCHEMA,SCHEMA)||!SNAPSHOT_KIND.equals(saved.optString("kind"))
        ||!slot.equals(saved.optString("slot"))||!integer(saved.opt("savedAt"),1,Long.MAX_VALUE)
        ||!Boolean.FALSE.equals(saved.opt("protectionVerified"))||!Boolean.FALSE.equals(saved.opt("leakVerdict"))
        ||!Boolean.FALSE.equals(saved.opt("physicalPhoneAcceptance"))||!Boolean.FALSE.equals(saved.opt("samePhysicalPhoneVerified"))
        ||!"user-entered-not-independent-verification".equals(saved.optString("compatibilitySource")))return null;
    JSONObject stored=saved.optJSONObject("contexts");if(stored==null||stored.length()>CONTEXTS.length)return null;
    for(Iterator<String> i=stored.keys();i.hasNext();)if(!member(i.next(),CONTEXTS))return null;
    JSONObject contexts=new JSONObject();for(String context:CONTEXTS)if(stored.has(context)){
      JSONObject clean=FingerprintContextBaselines.restoreContextSnapshot(stored.optJSONObject(context),environmentId,generation,context);
      if(clean==null||clean.length()==0)return null;put(contexts,context,clean);
    }
    JSONObject main=contexts.optJSONObject("main");if(main==null)return null;
    JSONObject identity=group(object(main,"observation"));if(!same(identity,saved.optJSONObject("group"))||!integer(identity.opt("configurationRevision"),1,MAX_COUNTER)||!integer(identity.opt("appVersionCode"),1,MAX_COUNTER)||!text(identity.opt("executionId"),128))return null;
    for(String context:CONTEXTS){JSONObject other=contexts.optJSONObject(context);if(other==null)continue;JSONObject meta=object(other,"observation");for(String key:GROUP)if(!"sourceOrigin".equals(key)&&!same(identity.opt(key),meta.opt(key)))return null;}
    JSONObject nativeSettings=settings(saved.optJSONObject("nativeSettings"),"enhanced".equals(slot)?2:1),descriptor=template(object(saved,"template"),slot);
    if(nativeSettings==null||descriptor==null)return null;
    JSONObject manual=saved.optJSONObject("compatibility"),times=saved.optJSONObject("compatibilityUpdatedAt");if(manual==null||times==null)return null;
    JSONObject cleanManual=new JSONObject(),cleanTimes=new JSONObject();for(String key:MANUAL_KEYS){Object state=manual.opt(key),time=times.opt(key);if(!(state instanceof String)||!member((String)state,MANUAL_STATES)||!integer(time,"not-tested".equals(state)?0:1,Long.MAX_VALUE)||"not-tested".equals(state)&&((Number)time).longValue()!=0)return null;put(cleanManual,key,state);put(cleanTimes,key,time);}
    JSONObject values=saved.optJSONObject("publicValues");if(values==null)return null;
    // Restore through the public-field whitelist, including its normalized screen shape.
    JSONObject parent=copy(values),screen=values.optJSONObject("screen");if(screen!=null)put(parent,"screen",J.obj("width",screen.opt("short"),"height",screen.opt("long"),"depth",screen.opt("depth")));
    put(parent,"viewport",J.obj("pixelRatio",values.opt("pixelRatio"),"touch",values.opt("touch")));
    JSONObject cleanValues=FingerprintObservationHistory.core(parent);if(!same(values,cleanValues))return null;
    JSONObject out=J.obj("schema",SCHEMA,"kind",SNAPSHOT_KIND,"slot",slot,"savedAt",saved.optLong("savedAt"),"group",identity,
        "template",descriptor,"nativeSettings",nativeSettings,"contexts",contexts,"publicValues",cleanValues,
        "compatibility",cleanManual,"compatibilityUpdatedAt",cleanTimes,"compatibilitySource","user-entered-not-independent-verification",
        "samePhysicalPhoneVerified",false,"protectionVerified",false,"leakVerdict",false,"physicalPhoneAcceptance",false);
    if(saved.has("routeHash")){Object hash=saved.opt("routeHash");if(!(hash instanceof String)||!((String)hash).matches("[0-9a-f]{64}"))return null;put(out,"routeHash",hash);}
    return bounded(out,MAX_SNAPSHOT_BYTES)?out:null;
  }
  static JSONObject restore(JSONObject saved,String environmentId,int generation){
    JSONObject out=empty(environmentId,generation);if(out.length()==0||saved==null||saved.length()==0)return out;
    if(!bounded(saved,MAX_BYTES)||!integer(saved.opt("schema"),SCHEMA,SCHEMA)||!KIND.equals(saved.optString("kind"))
        ||!environmentId.equals(saved.optString("environmentId"))||!integer(saved.opt("environmentGeneration"),generation,generation)
        ||!Boolean.FALSE.equals(saved.opt("protectionVerified"))||!Boolean.FALSE.equals(saved.opt("leakVerdict"))||!Boolean.FALSE.equals(saved.opt("physicalPhoneAcceptance")))return out;
    JSONObject input=saved.optJSONObject("slots");if(input==null||input.length()>2)return out;
    for(Iterator<String> i=input.keys();i.hasNext();)if(!member(i.next(),SLOTS))return out;
    for(String slot:SLOTS){JSONObject clean=restoreSnapshot(input.optJSONObject(slot),slot,environmentId,generation);if(clean!=null)put(object(out,"slots"),slot,clean);}
    return bounded(out,MAX_BYTES)?out:empty(environmentId,generation);
  }
  static JSONObject manual(JSONObject saved,String slot,String key,String state,String environmentId,int generation){return manual(saved,slot,key,state,environmentId,generation,System.currentTimeMillis());}
  static JSONObject manual(JSONObject saved,String slot,String key,String state,String environmentId,int generation,long now){
    if(!member(slot,SLOTS)||!member(key,MANUAL_KEYS)||!member(state,MANUAL_STATES)||!integer(now,1,Long.MAX_VALUE))return null;
    JSONObject out=restore(saved,environmentId,generation),value=object(out,"slots").optJSONObject(slot);if(value==null)return null;
    put(object(value,"compatibility"),key,state);put(object(value,"compatibilityUpdatedAt"),key,"not-tested".equals(state)?0:now);
    return bounded(out,MAX_BYTES)?out:null;
  }
  static JSONObject clear(JSONObject saved,String slot,String environmentId,int generation){
    if(slot!=null&&!slot.isEmpty()&&!member(slot,SLOTS))return null;
    JSONObject out=restore(saved,environmentId,generation);if(slot==null||slot.isEmpty())return empty(environmentId,generation);object(out,"slots").remove(slot);return out;
  }
  /** Manual progress is a display of user entries, never an acceptance result. */
  static JSONObject manualChecklist(JSONObject saved,String slot,String environmentId,int generation){
    JSONObject value=member(slot,SLOTS)?object(restore(saved,environmentId,generation),"slots").optJSONObject(slot):null;
    JSONObject states=object(value,"compatibility"),times=object(value,"compatibilityUpdatedAt");
    JSONArray items=new JSONArray();int recorded=0,failed=0,notApplicable=0;
    for(String key:MANUAL_KEYS){
      String state=value==null?"not-tested":states.optString(key,"not-tested");
      if(!member(state,MANUAL_STATES))state="not-tested";
      long at="not-tested".equals(state)?0:times.optLong(key,0);
      if(!"not-tested".equals(state)){recorded++;if("fail".equals(state))failed++;if("not-applicable".equals(state))notApplicable++;}
      items.put(J.obj("key",key,"label",manualLabel(key),"state",state,"labelState",manualStateLabel(state),"recordedAt",at));
    }
    return J.obj("saved",value!=null,"items",items,"total",MANUAL_KEYS.length,"recorded",recorded,
        "notTested",MANUAL_KEYS.length-recorded,"reportedFailures",failed,"notApplicable",notApplicable,
        "allItemsRecorded",value!=null&&recorded==MANUAL_KEYS.length,"source","user-entered-not-independent-verification",
        "physicalPhoneAcceptance",false,"protectionVerified",false,"leakVerdict",false);
  }
  static String manualState(JSONObject saved,String slot,String key,String environmentId,int generation){
    if(!member(key,MANUAL_KEYS))return "not-tested";
    JSONArray items=manualChecklist(saved,slot,environmentId,generation).optJSONArray("items");
    for(int i=0;i<items.length();i++){JSONObject item=items.optJSONObject(i);if(key.equals(item.optString("key")))return item.optString("state","not-tested");}
    return "not-tested";
  }
  static String manualProgress(JSONObject saved,String slot,String environmentId,int generation){
    JSONObject value=manualChecklist(saved,slot,environmentId,generation);
    if(!value.optBoolean("saved"))return "尚无报告；人工兼容项目未测试";
    return "人工记录 "+value.optInt("recorded")+"/"+value.optInt("total")+" · 未测试 "+value.optInt("notTested")
        +" · 异常 "+value.optInt("reportedFailures")+" · 不适用 "+value.optInt("notApplicable")+"（仅自行记录）";
  }
  private static JSONObject slotView(JSONObject value){
    if(value==null)return J.obj("saved",false);JSONObject out=J.obj("saved",true,"savedAt",value.optLong("savedAt"),"group",copy(object(value,"group")),"template",copy(object(value,"template")),"nativeSettings",copy(object(value,"nativeSettings")),"compatibility",copy(object(value,"compatibility")),"compatibilityUpdatedAt",copy(object(value,"compatibilityUpdatedAt")),"compatibilitySource","user-entered-not-independent-verification");
    return out;
  }
  static JSONObject comparison(JSONObject saved,String environmentId,int generation){
    JSONObject restored=restore(saved,environmentId,generation),slots=object(restored,"slots"),first=slots.optJSONObject("standard"),second=slots.optJSONObject("enhanced");
    JSONObject out=J.obj("schema",SCHEMA,"state",first==null&&second==null?"no-observations":first==null||second==null?"one-observation":"comparable",
        "slots",J.obj("standard",slotView(first),"enhanced",slotView(second)),"contexts",new JSONObject(),"conditionsChanged",new JSONArray(),"separationReasons",new JSONArray(),
        "samePhysicalPhoneVerified",false,"protectionVerified",false,"leakVerdict",false,"physicalPhoneAcceptance",false,
        "scope","Two user-selected local observations. Setting confirmation and manual compatibility are separate from API output differences.");
    if(first==null||second==null)return out;
    JSONArray separation=new JSONArray(),conditions=new JSONArray();JSONObject a=object(first,"group"),b=object(second,"group"),ta=object(first,"template"),tb=object(second,"template");
    for(String key:new String[]{"sourceOrigin","engineVersion","appVersion","appVersionCode"})if(!same(a.opt(key),b.opt(key)))separation.put(key);
    for(String key:new String[]{"display","requestedLocales","expectedLocales"})if(!same(ta.opt(key),tb.opt(key)))separation.put(key);
    for(String key:new String[]{"configurationRevision","executionId"})if(!same(a.opt(key),b.opt(key)))conditions.put(key);
    if(!same(ta.opt("templateId"),tb.opt("templateId")))conditions.put("templateId");
    if(first.has("routeHash")&&second.has("routeHash")&&!same(first.opt("routeHash"),second.opt("routeHash")))separation.put("routeHash");
    if(!same(object(object(object(first,"contexts"),"main"),"checks").opt("probeVersion"),object(object(object(second,"contexts"),"main"),"checks").opt("probeVersion")))separation.put("probeVersion");
    put(out,"conditionsChanged",conditions);put(out,"separationReasons",separation);
    boolean confirmed="confirmed".equals(object(first,"nativeSettings").optString("state"))&&"confirmed".equals(object(second,"nativeSettings").optString("state"));
    if(separation.length()>0)put(out,"state","separate-conditions");else if(!confirmed)put(out,"state","settings-unconfirmed");
    put(out,"settingsBothConfirmed",confirmed);put(out,"routeObservedInBoth",first.has("routeHash")&&second.has("routeHash"));
    put(out,"publicFieldDifferences",FingerprintObservationHistory.differences(object(first,"publicValues"),object(second,"publicValues")));
    put(out,"publicFieldDifferencesDiagnosticOnly",true);
    JSONObject contextResults=new JSONObject();
    for(String context:CONTEXTS){
      JSONObject ca=object(object(first,"contexts"),context),cb=object(object(second,"contexts"),context),aa=object(ca,"checks"),bb=object(cb,"checks");
      boolean present=ca.length()>0&&cb.length()>0,probeSame=present&&same(aa.opt("probeVersion"),bb.opt("probeVersion")),sourceSame=present&&same(object(ca,"observation").opt("sourceOrigin"),object(cb,"observation").opt("sourceOrigin"));
      JSONObject results=new JSONObject();for(String api:FingerprintObservationHistory.APIS){
        JSONObject pa=object(object(aa,"probes"),api),pb=object(object(bb,"probes"),api);
        String sa=pa.optString("state","uncovered"),sb=pb.optString("state","uncovered"),ha=FingerprintObservationHistory.apiHash(J.obj(api,pa),api),hb=FingerprintObservationHistory.apiHash(J.obj(api,pb),api);
        boolean compare=present&&probeSame&&sourceSame&&separation.length()==0&&confirmed&&!ha.isEmpty()&&!hb.isEmpty();
        String reason=!present?"execution-context-missing":!probeSame?"probe-version-differs":!sourceSame?"context-origin-differs":separation.length()>0?"observation-conditions-differ":!confirmed?"native-setting-unconfirmed":ha.isEmpty()||hb.isEmpty()?"hash-unavailable":"same-context-inputs";
        boolean stateCompared=present&&probeSame&&sourceSame&&separation.length()==0;
        JSONObject value=J.obj("standardState",sa,"enhancedState",sb,"operationStateCompared",stateCompared,"hashCompared",compare,"reason",reason);
        if(stateCompared)put(value,"operationStateChanged",!sa.equals(sb));
        if(compare)put(value,"hashChanged",!ha.equals(hb));
        String ra=pa.optString("readbackHash"),rb=pb.optString("readbackHash");boolean readback=present&&probeSame&&sourceSame&&separation.length()==0&&confirmed&&"sha256".equals(pa.optString("readbackHashAlgorithm"))&&"sha256".equals(pb.optString("readbackHashAlgorithm"))&&ra.matches("[0-9a-f]{64}")&&rb.matches("[0-9a-f]{64}");
        put(value,"readbackHashCompared",readback);if(readback)put(value,"readbackHashChanged",!ra.equals(rb));put(results,api,value);
      }
      put(contextResults,context,J.obj("observedInBoth",present,"probeVersionSame",probeSame,"sourceOriginSame",sourceSame,"probes",results,"crossExecutionContextComparison",false));
    }
    put(out,"contexts",contextResults);return out;
  }
  static String slotSummary(JSONObject saved,String slot,String environmentId,int generation){
    JSONObject value=object(restore(saved,environmentId,generation),"slots").optJSONObject(slot);if(value==null)return "尚未保存";
    JSONObject identity=object(value,"group");return new SimpleDateFormat("MM-dd HH:mm:ss",Locale.getDefault()).format(new Date(value.optLong("savedAt")))+" · "+confirmationLabel(object(value,"nativeSettings"))+"\n"+identity.optString("sourceOrigin")+"\n"+BrowserIdentitySpec.preset(object(value,"template").optString("templateId")).label()+" · 配置 "+identity.optLong("configurationRevision")+"\n"+identity.optString("engineVersion")+" · 应用 "+identity.optString("appVersion")+"\n"+manualProgress(saved,slot,environmentId,generation);
  }
  private static String conditionLabel(String value){switch(value){case "display":return "手机版／电脑版";case "requestedLocales":return "请求语言";case "expectedLocales":return "SDK语言预测";case "routeHash":return "线路记录";case "templateId":return "模板";case "executionId":return "运行记录";default:return FingerprintDeepBaseline.label(value);}}
  private static String conditionNames(JSONArray value){StringJoiner out=new StringJoiner("、");if(value!=null)for(int i=0;i<value.length();i++)out.add(conditionLabel(value.optString(i)));return out.toString();}
  static String summary(JSONObject saved,String environmentId,int generation){
    JSONObject result=comparison(saved,environmentId,generation);StringBuilder text=new StringBuilder("本地标准／强化双报告（每环境两份，本地加密保存）");
    for(String slot:SLOTS)text.append("\n\n").append(slotLabel(slot)).append("：").append(slotSummary(saved,slot,environmentId,generation));
    String state=result.optString("state");if("no-observations".equals(state)||"one-observation".equals(state))return text.append("\n\n请分别在实际标准与强化模板中完成深检，再主动保存对应槽位；不会自动切换模板或替你填写兼容结果。").toString();
    if("separate-conditions".equals(state))text.append("\n\n来源、版本或测试条件不同，仅并列保留，未直接比较哈希：").append(conditionNames(result.optJSONArray("separationReasons"))).append("。线路记录变化不直接证明配置或出口改变。");
    else if("settings-unconfirmed".equals(state))text.append("\n\n至少一份原生设置未确认，不能作为已生效模式的效果对照；操作状态保留，未比较哈希。");
    else text.append("\n\n仅比较相同执行环境、来源与探针的有效输出；输出变化不代表保护有效或泄漏。");
    if(result.optJSONArray("conditionsChanged").length()>0)text.append("\n分别保留的配置／运行差异：").append(conditionNames(result.optJSONArray("conditionsChanged")));
    JSONObject contexts=object(result,"contexts");for(String context:CONTEXTS){JSONObject block=object(contexts,context);if(!block.optBoolean("observedInBoth"))continue;text.append("\n\n").append(contextLabel(context));for(String api:FingerprintObservationHistory.APIS){JSONObject value=object(object(block,"probes"),api);text.append("\n").append(FingerprintDeepBaseline.label(api)).append("：").append(FingerprintDeepBaseline.stateLabel(value.optString("standardState"))).append(" ／ ").append(FingerprintDeepBaseline.stateLabel(value.optString("enhancedState")));if(value.optBoolean("hashCompared"))text.append(value.optBoolean("hashChanged")?" · 哈希有变化":" · 已比较哈希未变");else text.append(" · 哈希未比较");if(value.optBoolean("readbackHashCompared"))text.append(value.optBoolean("readbackHashChanged")?" · 读回输出有变化":" · 读回输出未变");}}
    JSONObject slots=object(result,"slots");text.append("\n\n人工兼容记录（用户填写，不是自动或独立验收）");for(String key:MANUAL_KEYS)text.append("\n").append(manualLabel(key)).append("：").append(manualStateLabel(object(object(slots,"standard"),"compatibility").optString(key))).append(" ／ ").append(manualStateLabel(object(object(slots,"enhanced"),"compatibility").optString(key)));
    return text.append("\n\n同一真实手机和网络需人工确认；本地记录不认证设备身份、全部指纹保护或账号安全。不同执行环境不要求哈希相同，完整原始字段仅在主动导出中提供。").toString();
  }
  static String export(JSONObject saved,String environmentId,int generation){JSONObject out=J.obj("schema",SCHEMA,"kind",KIND+"-export","observations",restore(saved,environmentId,generation),"comparison",comparison(saved,environmentId,generation),"currentDocumentVerified",false,"samePhysicalPhoneVerified",false,"physicalPhoneAcceptance",false,"protectionVerified",false,"leakVerdict",false);return bounded(out,MAX_EXPORT_BYTES)?out.toString():J.obj("schema",SCHEMA,"kind",KIND+"-export","status","unavailable","reason","export-size-limit","physicalPhoneAcceptance",false,"protectionVerified",false,"leakVerdict",false).toString();}
}
