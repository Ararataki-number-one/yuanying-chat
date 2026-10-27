package local.pocketchat;

import org.json.*;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.*;

/** One explicitly pinned, local observation. It never attests protection or leakage. */
final class FingerprintDeepBaseline {
  static final int SCHEMA=1,MAX_BYTES=16384;
  static final String KIND="pinned-main-world-deep-observation";
  static final String[] APIS={"canvas","audio","fonts","webgl"};

  private static final class Candidate {
    String issue="";
    JSONObject observation=new JSONObject(),checks=new JSONObject();
    Candidate fail(String value){issue=value;return this;}
  }
  static JSONObject object(JSONObject value,String key){return FingerprintObservationHistory.object(value,key);}
  static JSONObject copy(JSONObject value){return FingerprintObservationHistory.copy(value);}
  static void put(JSONObject value,String key,Object item){FingerprintObservationHistory.put(value,key,item);}
  static boolean integer(Object value,long minimum,long maximum){return FingerprintObservationHistory.integer(value,minimum,maximum);}
  static boolean text(Object value,int maximum){return value instanceof String&&!((String)value).isEmpty()&&((String)value).length()<=maximum;}
  static boolean bounded(JSONObject value){try{String encoded=value==null?null:value.toString();return encoded!=null&&encoded.getBytes(StandardCharsets.UTF_8).length<=MAX_BYTES;}catch(RuntimeException invalid){return false;}}
  static String hash(JSONObject probe){return FingerprintObservationHistory.apiHash(J.obj("value",probe),"value");}

  /** Empty means the caller may offer an explicit pin action, after its live document checks. */
  static String captureIssue(JSONObject report,JSONObject metadata){return candidate(report,metadata,true).issue;}

  static JSONObject capture(JSONObject report,JSONObject metadata,long pinnedAt){
    Candidate selected=candidate(report,metadata,true);
    if(!selected.issue.isEmpty()||pinnedAt<=0)return new JSONObject();
    JSONObject value=J.obj("schema",SCHEMA,"kind",KIND,"pinnedAt",pinnedAt,
        "observation",selected.observation,"checks",selected.checks,"protectionVerified",false,"leakVerdict",false);
    return bounded(value)?value:new JSONObject();
  }

  private static Candidate candidate(JSONObject report,JSONObject metadata,boolean requireMeaningful){
    Candidate out=new Candidate();
    if(report==null||metadata==null||!Boolean.TRUE.equals(report.opt("fresh")))return out.fail("请先完成当前页面的有效深检，再固定参照");
    if(report.has("apiProtectionVerified")&&!Boolean.FALSE.equals(report.opt("apiProtectionVerified")))return out.fail("本机操作观测不能作为全部指纹保护的认证，未固定该结果");
    JSONObject observation=FingerprintObservationHistory.entry(report,metadata);
    if(observation==null||!FingerprintObservationHistory.completeGroup(observation))return out.fail("深检的环境、配置、来源或版本信息不完整，不能固定参照");
    for(String name:new String[]{"engineVersion","appVersion"})if(!text(metadata.opt(name),128))return out.fail("深检版本信息无效，不能固定参照");
    if(report.has("identityAppliedRevision")&&(!integer(report.opt("identityAppliedRevision"),1,Long.MAX_VALUE)||report.optLong("identityAppliedRevision")!=observation.optLong("configurationRevision")))return out.fail("深检所属配置已变化，不能用新配置重标旧结果");
    if(report.has("executionId")&&metadata.has("executionId")&&!Objects.equals(report.opt("executionId"),metadata.opt("executionId")))return out.fail("深检所属运行已变化，请重新检查后固定");
    JSONObject expected=object(report,"expected");
    if(expected.has("environmentId")&&!observation.optString("environmentId").equals(expected.optString("environmentId")))return out.fail("深检不属于当前环境");
    if(expected.has("environmentGeneration")&&(!integer(expected.opt("environmentGeneration"),0,Integer.MAX_VALUE)||expected.optInt("environmentGeneration")!=observation.optInt("environmentGeneration")))return out.fail("深检所属环境代次已变化");
    JSONObject raw=object(object(report,"signals"),"apiChecks");
    String issue=checksIssue(raw,requireMeaningful);
    if(!issue.isEmpty())return out.fail(issue);
    out.checks=cleanChecks(raw);out.observation=copy(observation);
    // Rebuild the hash view from the same validated operation evidence.
    put(out.observation,"apis",FingerprintObservationHistory.probes(J.obj("apiChecks",out.checks)));
    JSONObject stored=J.obj("schema",SCHEMA,"kind",KIND,"pinnedAt",Long.MAX_VALUE,"observation",out.observation,"checks",out.checks,"protectionVerified",false,"leakVerdict",false);
    if(!bounded(stored))return out.fail("深检参照超过本地保存上限，未固定");
    return out;
  }

  private static String checksIssue(JSONObject value,boolean requireMeaningful){
    if(!integer(value.opt("schema"),SCHEMA,SCHEMA)||!Boolean.TRUE.equals(value.opt("requested"))
        ||!Boolean.FALSE.equals(value.opt("protectionVerified"))||!"page-main-world".equals(value.optString("source"))
        ||!integer(value.opt("probeVersion"),1,100000))return "本次不是当前页面主执行环境的有效图形与音频深检";
    JSONObject limits=object(value,"limits"),probes=value.optJSONObject("probes");
    if(!integer(limits.opt("canvasPixels"),4096,4096)||!integer(limits.opt("audioFrames"),2048,2048)
        ||!integer(limits.opt("fontCandidates"),5,5)||!integer(limits.opt("totalBudgetMs"),1200,1200)
        ||probes==null||!FingerprintObservationHistory.number(value.opt("durationMs"),0,60000))return "深检操作预算或时间字段无效，不能固定参照";
    boolean meaningful=false,partial=false;
    for(String name:APIS){
      JSONObject probe=probes.optJSONObject(name);if(probe==null)return "深检操作结果不完整，不能固定参照";
      String state=probe.optString("state");
      if(!Arrays.asList("available","restricted","failed","uncovered").contains(state)||!text(probe.opt("reason"),96))return "深检操作状态或原因无效，不能固定参照";
      partial|="uncovered".equals(state);
      boolean observed="available".equals(state)||"restricted".equals(state);
      if("available".equals(state)&&!AuditReport.apiOperationComplete(name,probe))return "深检操作证据不完整，不能只凭可用标签固定参照";
      if(probe.has("hash")||probe.has("hashAlgorithm")){
        if(!(probe.opt("hash") instanceof String)||!(probe.opt("hashAlgorithm") instanceof String)||!observed||hash(probe).isEmpty()||!AuditReport.apiOperationComplete(name,probe)||Boolean.TRUE.equals(probe.opt("hashUnavailable")))return "深检哈希或其操作证据无效，未固定参照";
      }else if("available".equals(state)&&!Boolean.TRUE.equals(probe.opt("hashUnavailable")))return "深检缺少有效哈希或明确的哈希不可用说明";
      if(probe.has("hashUnavailable")&&!(probe.opt("hashUnavailable") instanceof Boolean))return "深检哈希状态类型无效，未固定参照";
      meaningful|=observed;
    }
    if(!(partial?"partial":"completed").equals(value.optString("status")))return "深检完成状态与逐项结果不一致，未固定参照";
    return requireMeaningful&&!meaningful?"本次全部操作失败或未覆盖，尚无可固定的有效操作参照":"";
  }

  private static JSONObject cleanChecks(JSONObject raw){
    JSONObject probes=new JSONObject();
    for(String name:APIS){
      JSONObject old=object(object(raw,"probes"),name),value=J.obj("state",old.optString("state"),"reason",old.optString("reason"));
      if(!hash(old).isEmpty()){put(value,"hash",old.optString("hash"));put(value,"hashAlgorithm","sha256");}
      if(old.opt("hashUnavailable") instanceof Boolean)put(value,"hashUnavailable",old.optBoolean("hashUnavailable"));
      if(AuditReport.apiOperationComplete(name,old)){
        String[] fields="canvas".equals(name)?new String[]{"pixels"}:"audio".equals(name)?new String[]{"frames","sampleRate","peak"}:"fonts".equals(name)?new String[]{"candidateCount"}:new String[]{"version","shadingLanguageVersion","vendor","renderer","maxTextureSize","maxRenderbufferSize","maxVertexAttribs","extensionCount"};
        for(String field:fields)put(value,field,old.opt(field));
        if("fonts".equals(name)){JSONArray samples=new JSONArray(),input=old.optJSONArray("samples");for(int i=0;i<input.length();i++){JSONObject sample=input.optJSONObject(i);samples.put(J.obj("name",sample.optString("name"),"faceCheck",sample.opt("faceCheck"),"monospaceWidth",sample.opt("monospaceWidth"),"sansSerifWidth",sample.opt("sansSerifWidth")));}put(value,"samples",samples);}
        if("webgl".equals(name)){try{put(value,"extensions",new JSONArray(old.optJSONArray("extensions").toString()));}catch(JSONException ignored){}if(text(old.opt("unmaskedRenderer"),256))put(value,"unmaskedRenderer",old.optString("unmaskedRenderer"));}
      }
      put(probes,name,value);
    }
    return J.obj("schema",SCHEMA,"requested",true,"source","page-main-world","probeVersion",raw.optInt("probeVersion"),
        "status",raw.optString("status"),"durationMs",raw.optDouble("durationMs"),"limits",J.obj("canvasPixels",4096,"audioFrames",2048,"fontCandidates",5,"totalBudgetMs",1200),"probes",probes,"protectionVerified",false);
  }

  /** Invalid or foreign saved data is not reassigned to the caller's environment. */
  static JSONObject restore(JSONObject saved,String environmentId,int generation){
    if(!bounded(saved)||!integer(saved.opt("schema"),SCHEMA,SCHEMA)||!KIND.equals(saved.optString("kind"))
        ||!integer(saved.opt("pinnedAt"),1,Long.MAX_VALUE)||!Boolean.FALSE.equals(saved.opt("protectionVerified"))
        ||!Boolean.FALSE.equals(saved.opt("leakVerdict")))return new JSONObject();
    JSONObject original=saved.optJSONObject("observation"),checks=saved.optJSONObject("checks");
    if(original==null||checks==null||!checksIssue(checks,true).isEmpty())return new JSONObject();
    JSONArray restored=FingerprintObservationHistory.restore(new JSONArray().put(original),environmentId,generation);
    if(restored.length()!=1)return new JSONObject();
    JSONObject observation=restored.optJSONObject(0);observation.remove("comparison");
    if(!FingerprintObservationHistory.completeGroup(observation))return new JSONObject();
    JSONObject clean=cleanChecks(checks),expected=FingerprintObservationHistory.probes(J.obj("apiChecks",clean));
    if(!FingerprintObservationHistory.same(object(observation,"apis"),expected))return new JSONObject();
    JSONObject out=J.obj("schema",SCHEMA,"kind",KIND,"pinnedAt",saved.optLong("pinnedAt"),"observation",observation,"checks",clean,"protectionVerified",false,"leakVerdict",false);
    return bounded(out)?out:new JSONObject();
  }

  static JSONObject comparison(JSONObject saved,JSONObject report,JSONObject metadata){
    String environment=metadata==null?"":metadata.optString("environmentId");int generation=metadata==null?-1:metadata.optInt("environmentGeneration",-1);
    JSONObject baseline=restore(saved,environment,generation);
    JSONObject out=J.obj("state","no-reference","source","page-main-world","apiComparisons",new JSONObject(),"hashComparedCount",0,"hashChangedCount",0,"protectionVerified",false,"leakVerdict",false,"crossExecutionContextComparison",false);
    if(baseline.length()==0)return out;
    JSONObject before=object(baseline,"observation");put(out,"referenceAt",before.optLong("at"));put(out,"pinnedAt",baseline.optLong("pinnedAt"));put(out,"referenceGroup",group(before));
    Candidate now=candidate(report,metadata,false);
    if(!now.issue.isEmpty()){put(out,"state","current-unavailable");put(out,"reason",now.issue);return out;}
    put(out,"currentGroup",group(now.observation));JSONArray separation=new JSONArray();
    for(String name:FingerprintObservationHistory.GROUP)if(!FingerprintObservationHistory.same(before.opt(name),now.observation.opt(name)))separation.put(name);
    if(object(baseline,"checks").optInt("probeVersion")!=now.checks.optInt("probeVersion"))separation.put("probeVersion");
    if(!FingerprintObservationHistory.sameGroup(before,now.observation)||separation.length()>0){put(out,"state","separate-context");put(out,"separationReasons",separation);return out;}
    JSONObject perApi=new JSONObject();int compared=0,changed=0;
    for(String name:APIS){
      JSONObject first=object(object(baseline,"checks"),"probes").optJSONObject(name),second=object(now.checks,"probes").optJSONObject(name);
      String firstHash=hash(first),secondHash=hash(second);
      JSONObject value=J.obj("referenceState",first.optString("state"),"currentState",second.optString("state"),"operationStateCompared",true,"operationStateChanged",!first.optString("state").equals(second.optString("state")),"compared",false);
      if(firstHash.isEmpty()||secondHash.isEmpty()){put(value,"state","uncompared");put(value,"reason",firstHash.isEmpty()&&secondHash.isEmpty()?"both-hashes-unavailable":firstHash.isEmpty()?"reference-hash-unavailable":"current-hash-unavailable");}
      else{boolean different=!firstHash.equals(secondHash);put(value,"state","comparable");put(value,"compared",true);put(value,"changed",different);compared++;if(different)changed++;}
      put(perApi,name,value);
    }
    put(out,"state","comparable");put(out,"apiComparisons",perApi);put(out,"hashComparedCount",compared);put(out,"hashChangedCount",changed);
    return out;
  }
  static JSONObject group(JSONObject observation){JSONObject out=new JSONObject();for(String name:FingerprintObservationHistory.GROUP)put(out,name,observation.opt(name));put(out,"probeVersion",object(observation,"apis").optInt("probeVersion"));return out;}
  static String label(String name){switch(name){case "canvas":return "Canvas";case "audio":return "离线音频";case "fonts":return "有限字体";case "webgl":return "WebGL";case "probeVersion":return "探针版本";default:return FingerprintObservationHistory.name(name);}}
  static String stateLabel(String name){switch(name){case "available":return "可用";case "restricted":return "受限";case "failed":return "失败";default:return "未覆盖";}}
  static String summary(JSONObject saved,JSONObject report,JSONObject metadata){
    JSONObject baseline=restore(saved,metadata==null?"":metadata.optString("environmentId"),metadata==null?-1:metadata.optInt("environmentGeneration",-1));
    if(baseline.length()==0)return "尚未固定深检参照。完成当前页面的图形与音频检查后，可主动固定一份；普通检查不会替换它。";
    JSONObject observation=object(baseline,"observation"),checks=object(baseline,"checks"),comparison=comparison(baseline,report,metadata);
    SimpleDateFormat time=new SimpleDateFormat("MM-dd HH:mm:ss",Locale.getDefault());
    StringBuilder text=new StringBuilder("固定深检参照（仅当前页面主执行环境，本地加密保存）\n观测 ").append(time.format(new Date(observation.optLong("at")))).append(" · 固定 ").append(time.format(new Date(baseline.optLong("pinnedAt")))).append("\n").append(observation.optString("sourceOrigin")).append("\n配置 ").append(observation.optLong("configurationRevision")).append(" · 探针 ").append(checks.optInt("probeVersion")).append("\n应用 ").append(observation.optString("appVersion")).append(" · ").append(observation.optString("engineVersion"));
    String state=comparison.optString("state");
    if("separate-context".equals(state)){StringJoiner names=new StringJoiner("、");JSONArray reasons=comparison.optJSONArray("separationReasons");for(int i=0;i<reasons.length();i++)names.add(label(reasons.optString(i)));text.append("\n\n本次与固定参照的").append(names).append("不同，分别保留，未直接比较输出或判断异常。");}
    else if("current-unavailable".equals(state))text.append("\n\n本次没有可比较的深检结果，固定参照仍保留。\n").append(comparison.optString("reason"));
    JSONObject results=object(comparison,"apiComparisons");
    for(String name:APIS){JSONObject reference=object(object(checks,"probes"),name),value=results.optJSONObject(name);text.append("\n\n").append(label(name)).append(" 参照：").append(stateLabel(reference.optString("state")));if(!hash(reference).isEmpty())text.append("\nSHA-256：").append(hash(reference));else text.append(" · 没有有效哈希");if(value==null)continue;text.append("\n本次：").append(stateLabel(value.optString("currentState")));if(value.optBoolean("operationStateChanged"))text.append("；操作状态有变化");if(value.optBoolean("compared"))text.append(value.optBoolean("changed")?"；哈希有变化":"；本项已比较哈希未变");else text.append("；缺少有效哈希，本项输出未比较");}
    return text.append("\n\n固定参照独立于最近八条观测，只有你主动替换或清除。不同页面、Worker 或 iframe 不要求哈希相同；状态或输出变化不等于泄漏，也不证明原生保护失效。").toString();
  }
}
