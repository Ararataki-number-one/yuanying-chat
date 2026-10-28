package local.pocketchat;

import org.json.*;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.*;

/** Four explicitly owned operation references; output changes never attest protection or leakage. */
final class FingerprintContextBaselines {
  static final int SCHEMA=1,MAX_BYTES=65536,MAX_REFERENCE_BYTES=16384;
  static final String KIND="pinned-execution-context-baselines",PIN_KIND="pinned-execution-context-deep-observation",SNAPSHOT_KIND="execution-context-deep-observation";
  static final String[] CONTEXTS={"main","worker","frame","crossOriginFrame"};
  private static final String[] APIS={"canvas","audio","fonts","webgl"};
  private static final String[] GROUP={"environmentId","environmentGeneration","configurationRevision","engineVersion","appVersion","appVersionCode","source","sourceOrigin","topLevelOrigin","probeVersion"};
  private static final class Candidate { String issue="";JSONObject observation=new JSONObject(),checks=new JSONObject();Candidate fail(String text){issue=text;return this;} }
  private static JSONObject object(JSONObject value,String key){return FingerprintObservationHistory.object(value,key);}
  private static JSONObject copy(JSONObject value){return FingerprintObservationHistory.copy(value);}
  private static void put(JSONObject value,String key,Object item){FingerprintObservationHistory.put(value,key,item);}
  private static boolean integer(Object value,long min,long max){return FingerprintObservationHistory.integer(value,min,max);}
  private static boolean text(Object value,int max){return value instanceof String&&!((String)value).isEmpty()&&((String)value).length()<=max;}
  private static boolean bounded(JSONObject value,int max){try{return value!=null&&value.toString().getBytes(StandardCharsets.UTF_8).length<=max;}catch(RuntimeException bad){return false;}}
  private static boolean context(String value){return Arrays.asList(CONTEXTS).contains(value);}
  private static String source(String context){return "main".equals(context)?"page-main-world":"worker".equals(context)?"dedicated-worker":"frame".equals(context)?"same-origin-srcdoc":"crossOriginFrame".equals(context)?"controlled-cross-origin-iframe":"";}
  static String label(String context){return "main".equals(context)?"主页面":"worker".equals(context)?"Dedicated Worker":"frame".equals(context)?"同源 iframe":"crossOriginFrame".equals(context)?"受控跨源 iframe":"未知执行环境";}
  private static boolean owner(String environment,int generation){return environment!=null&&environment.matches("[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")&&generation>=0;}
  private static String hash(JSONObject value,String field){String algorithm="readbackHash".equals(field)?"readbackHashAlgorithm":"hashAlgorithm";return value!=null&&text(value.opt(field),64)&&value.optString(field).matches("[0-9a-f]{64}")&&"sha256".equals(value.optString(algorithm))?value.optString(field):"";}
  private static boolean digest(JSONObject value,String field,boolean required){
    String algorithm="readbackHash".equals(field)?"readbackHashAlgorithm":"hashAlgorithm",missing="readbackHash".equals(field)?"readbackHashUnavailable":"hashUnavailable";
    if(value.has(missing)&&!(value.opt(missing) instanceof Boolean))return false;
    if(value.has(field)||value.has(algorithm))return !hash(value,field).isEmpty()&&!Boolean.TRUE.equals(value.opt(missing));
    return !required||Boolean.TRUE.equals(value.opt(missing));
  }
  private static boolean readback(JSONObject value){return integer(value.opt("readbackPixels"),256,256)&&integer(value.opt("readbackBytes"),1024,1024)&&digest(value,"readbackHash",true);}
  private static boolean operation(String context,String api,JSONObject value){
    if("crossOriginFrame".equals(context)){
      if("canvas".equals(api))return integer(value.opt("pixels"),4096,4096);
      if(!"webgl".equals(api)||!readback(value))return false;
      for(String field:new String[]{"version","shadingLanguageVersion","vendor","renderer","unmaskedRenderer"})if(value.has(field)&&!text(value.opt(field),256))return false;
      for(String field:new String[]{"maxTextureSize","maxRenderbufferSize","maxVertexAttribs","extensionCount"})if(value.has(field)&&!integer(value.opt(field),0,Integer.MAX_VALUE))return false;
      return true;
    }
    return AuditReport.apiOperationComplete(api,value)&&(!"worker".equals(context)||!"webgl".equals(api)||readback(value));
  }
  private static boolean inapplicable(String context,String api){return ("worker".equals(context)||"crossOriginFrame".equals(context))&&("audio".equals(api)||"fonts".equals(api));}
  private static String checksIssue(JSONObject checks,String context,boolean meaningfulRequired){
    if(!bounded(checks,MAX_REFERENCE_BYTES)||!integer(checks.opt("schema"),1,1)||!integer(checks.opt("probeVersion"),1,100000)
        ||!Boolean.TRUE.equals(checks.opt("requested"))||!Boolean.FALSE.equals(checks.opt("protectionVerified"))||!source(context).equals(checks.optString("source")))return "没有该执行环境的有效深检结果";
    JSONObject limits=object(checks,"limits"),probes=checks.optJSONObject("probes");boolean limited="worker".equals(context)||"crossOriginFrame".equals(context);
    if(probes==null||!integer(limits.opt("canvasPixels"),4096,4096)||!integer(limits.opt("audioFrames"),limited?0:2048,limited?0:2048)
        ||!integer(limits.opt("fontCandidates"),limited?0:5,limited?0:5)||!integer(limits.opt("totalBudgetMs"),1200,1200))return "该执行环境的操作预算无效";
    // The checked cross-origin transport intentionally omits raw duration; it is not invented here.
    if(checks.has("durationMs")?!FingerprintObservationHistory.number(checks.opt("durationMs"),0,60000):!"crossOriginFrame".equals(context))return "该执行环境的采样时间字段无效";
    boolean meaningful=false,partial=false;
    for(String api:APIS){
      JSONObject probe=probes.optJSONObject(api);if(probe==null)return "该执行环境的操作结果不完整";
      String state=probe.optString("state");if(!Arrays.asList("available","restricted","failed","uncovered").contains(state)||!text(probe.opt("reason"),96))return "操作状态或原因无效";
      if(inapplicable(context,api)&&!"uncovered".equals(state))return "未实现的执行环境接口不能作为已覆盖结果";
      if(!"crossOriginFrame".equals(context)||!inapplicable(context,api))partial|="uncovered".equals(state);
      boolean observed="available".equals(state)||"restricted".equals(state),completed=operation(context,api,probe);
      if("webgl".equals(api)&&probe.has("unmaskedRenderer")&&!text(probe.opt("unmaskedRenderer"),256))return "可选图形描述字段无效";
      boolean supportsReadback=("worker".equals(context)||"crossOriginFrame".equals(context))&&"webgl".equals(api);
      if(!supportsReadback)for(String field:new String[]{"readbackPixels","readbackBytes","readbackHash","readbackHashAlgorithm","readbackHashUnavailable"})if(probe.has(field))return "该执行环境没有运行这项像素读回";
      if("available".equals(state)&&(!completed||!digest(probe,"hash",true)))return "可用状态缺少完整操作证据";
      if(!digest(probe,"hash",false)||!digest(probe,"readbackHash",false))return "操作哈希或缺失标记无效";
      if((probe.has("hash")||probe.has("hashAlgorithm")||probe.has("readbackHash")||probe.has("readbackHashAlgorithm"))&&(!observed||!completed))return "哈希没有对应的完整操作证据";
      if(inapplicable(context,api)&&(probe.has("hash")||probe.has("readbackHash")))return "不适用的接口不能带入输出哈希";
      meaningful|=observed;
    }
    if(!(partial?"partial":"completed").equals(checks.optString("status")))return "整体完成状态与逐项操作不一致";
    return meaningfulRequired&&!meaningful?"全部操作失败或未覆盖，尚无可固定的有效参照":"";
  }
  private static JSONObject cleanChecks(JSONObject raw,String context){
    JSONObject probes=new JSONObject();
    for(String api:APIS){
      JSONObject old=object(object(raw,"probes"),api),value=J.obj("state",old.optString("state"),"reason",old.optString("reason"));
      for(String field:new String[]{"hash","readbackHash"})if(!hash(old,field).isEmpty()){put(value,field,old.optString(field));put(value,"readbackHash".equals(field)?"readbackHashAlgorithm":"hashAlgorithm","sha256");}
      for(String field:new String[]{"hashUnavailable","readbackHashUnavailable"})if(old.opt(field) instanceof Boolean)put(value,field,old.optBoolean(field));
      if(operation(context,api,old)){
        String[] fields="canvas".equals(api)?new String[]{"pixels"}:"audio".equals(api)?new String[]{"frames","sampleRate","peak"}:"fonts".equals(api)?new String[]{"candidateCount"}:new String[]{"version","shadingLanguageVersion","vendor","renderer","maxTextureSize","maxRenderbufferSize","maxVertexAttribs","extensionCount","unmaskedRenderer","readbackPixels","readbackBytes"};
        for(String field:fields)if(old.has(field))put(value,field,old.opt(field));
        if("fonts".equals(api)){JSONArray values=new JSONArray(),samples=old.optJSONArray("samples");for(int i=0;i<samples.length();i++){JSONObject sample=samples.optJSONObject(i);values.put(J.obj("name",sample.optString("name"),"faceCheck",sample.opt("faceCheck"),"monospaceWidth",sample.opt("monospaceWidth"),"sansSerifWidth",sample.opt("sansSerifWidth")));}put(value,"samples",values);}
        if("webgl".equals(api)&&!"crossOriginFrame".equals(context))try{put(value,"extensions",new JSONArray(old.optJSONArray("extensions").toString()));}catch(JSONException ignored){}
      }
      put(probes,api,value);
    }
    JSONObject out=J.obj("schema",1,"requested",true,"source",source(context),"probeVersion",raw.optInt("probeVersion"),"status",raw.optString("status"),"limits",copy(object(raw,"limits")),"probes",probes,"protectionVerified",false);
    // Rebuild limits so arbitrary saved fields are never persisted.
    boolean limited="worker".equals(context)||"crossOriginFrame".equals(context);put(out,"limits",J.obj("canvasPixels",4096,"audioFrames",limited?0:2048,"fontCandidates",limited?0:5,"totalBudgetMs",1200));
    if(raw.has("durationMs"))put(out,"durationMs",raw.optDouble("durationMs"));return out;
  }
  private static boolean sameOwnerConfiguration(JSONObject value,JSONObject current){
    return current.optString("environmentId").equals(value.optString("environmentId"))
        &&integer(value.opt("environmentGeneration"),current.optInt("environmentGeneration"),current.optInt("environmentGeneration"))
        &&integer(value.opt("configurationRevision"),current.optLong("configurationRevision"),current.optLong("configurationRevision"));
  }
  private static Candidate candidate(JSONObject report,JSONObject metadata,String context,boolean meaningful){
    Candidate out=new Candidate();if(!context(context))return out.fail("未知执行环境");
    if(report==null||metadata==null||!Boolean.TRUE.equals(report.opt("fresh")))return out.fail("请先完成当前文档的有效深检");
    if(report.has("apiProtectionVerified")&&!Boolean.FALSE.equals(report.opt("apiProtectionVerified")))return out.fail("操作观测不作为全部指纹保护认证");
    JSONObject base=FingerprintObservationHistory.entry(report,metadata);if(base==null||!FingerprintObservationHistory.completeGroup(base))return out.fail("环境、配置、来源或版本信息不完整");
    for(String name:new String[]{"engineVersion","appVersion"})if(!text(metadata.opt(name),128))return out.fail("版本字段无效");
    if(report.has("identityAppliedRevision")&&(!integer(report.opt("identityAppliedRevision"),1,Long.MAX_VALUE)||report.optLong("identityAppliedRevision")!=base.optLong("configurationRevision")))return out.fail("深检配置已经变化");
    if(report.has("executionId")&&metadata.has("executionId")&&!Objects.equals(report.opt("executionId"),metadata.opt("executionId")))return out.fail("深检所属运行已经变化");
    JSONObject expected=object(report,"expected");if(expected.has("environmentId")&&!base.optString("environmentId").equals(expected.optString("environmentId")))return out.fail("结果不属于当前环境");
    if(expected.has("environmentGeneration")&&(!integer(expected.opt("environmentGeneration"),0,Integer.MAX_VALUE)||expected.optInt("environmentGeneration")!=base.optInt("environmentGeneration")))return out.fail("结果所属环境代次已经变化");
    String top=base.optString("sourceOrigin"),origin=top;JSONObject raw;
    if("main".equals(context))raw=object(object(report,"signals"),"apiChecks");
    else if("crossOriginFrame".equals(context)){
      JSONObject checked=object(report,"requestIdentity"),frame=object(object(checked,"browser"),"crossOriginFrame");
      if(!Boolean.TRUE.equals(report.opt("requestIdentityNetwork"))||!"extension-background-control".equals(report.optString("requestIdentityControlSource"))
          ||!"extension-background-control".equals(checked.optString("controlSource"))||!Boolean.TRUE.equals(checked.opt("crossOriginFrameRequested"))
          ||!Boolean.TRUE.equals(checked.opt("fresh"))||!sameOwnerConfiguration(checked,base)||!sameOwnerConfiguration(object(checked,"expected"),base)
          ||!text(checked.opt("executionId"),128)||!checked.optString("executionId").equals(base.optString("executionId"))
          ||!"controlled-top-level-document".equals(checked.optString("source"))||!Arrays.asList("observed","issue").contains(checked.optString("status"))
          ||!top.equals(FingerprintObservationHistory.origin(checked.opt("endpoint")))||!"complete".equals(frame.optString("status"))
          ||!"controlled-cross-origin-iframe".equals(frame.optString("source"))||!Boolean.FALSE.equals(frame.opt("protectionVerified"))
          ||!text(checked.opt("nonce"),128)||!checked.optString("nonce").equals(frame.optString("nonce")))return out.fail("没有当前受控跨源 iframe 的完整回执");
      origin=FingerprintObservationHistory.origin(frame.opt("origin"));if(origin.isEmpty()||origin.equals(top)||!origin.equals(frame.optString("origin")))return out.fail("跨源 iframe 的实际来源无效");
      raw=object(frame,"apiChecks");
    }else{
      JSONObject contexts=object(object(report,"signals"),"apiContexts");if(!integer(contexts.opt("schema"),1,1)||!Boolean.TRUE.equals(contexts.opt("requested")))return out.fail("本次没有主动检查该执行环境");raw=object(contexts,context);
    }
    String issue=checksIssue(raw,context,meaningful);if(!issue.isEmpty())return out.fail(issue);
    JSONObject observation=J.obj("schema",1,"at",base.optLong("at"),"source",source(context),"sourceOrigin",origin,"topLevelOrigin",top,"probeVersion",raw.optInt("probeVersion"));
    for(String key:new String[]{"environmentId","environmentGeneration","configurationRevision","engineVersion","appVersion","appVersionCode","executionId"})put(observation,key,base.opt(key));
    if("crossOriginFrame".equals(context))put(observation,"controlSource","extension-background-control");
    out.observation=observation;out.checks=cleanChecks(raw,context);return out;
  }
  static String captureIssue(JSONObject report,JSONObject metadata,String context){return "main".equals(context)?FingerprintDeepBaseline.captureIssue(report,metadata):candidate(report,metadata,context,true).issue;}
  static JSONObject capture(JSONObject report,JSONObject metadata,String context,long pinnedAt){
    if("main".equals(context))return FingerprintDeepBaseline.capture(report,metadata,pinnedAt);
    Candidate value=candidate(report,metadata,context,true);if(!value.issue.isEmpty()||pinnedAt<=0)return new JSONObject();
    JSONObject out=record(value,context,PIN_KIND);put(out,"pinnedAt",pinnedAt);return bounded(out,MAX_REFERENCE_BYTES)?out:new JSONObject();
  }
  private static JSONObject record(Candidate value,String context,String kind){return J.obj("schema",1,"kind",kind,"context",context,"observation",value.observation,"checks",value.checks,"protectionVerified",false,"leakVerdict",false);}
  /** A comparison report may retain failed operations; unlike a pin it need not be a useful reference. */
  static JSONObject contextSnapshot(JSONObject report,JSONObject metadata,String context){Candidate value=candidate(report,metadata,context,false);if(!value.issue.isEmpty())return new JSONObject();JSONObject out=record(value,context,SNAPSHOT_KIND);return bounded(out,MAX_REFERENCE_BYTES)?out:new JSONObject();}
  private static JSONObject restoreRecord(JSONObject saved,String environment,int generation,String context,String kind,boolean meaningful){
    if(!owner(environment,generation)||!context(context)||!bounded(saved,MAX_REFERENCE_BYTES)||!integer(saved.opt("schema"),1,1)||!kind.equals(saved.optString("kind"))||!context.equals(saved.optString("context"))||!Boolean.FALSE.equals(saved.opt("protectionVerified"))||!Boolean.FALSE.equals(saved.opt("leakVerdict")))return new JSONObject();
    JSONObject old=saved.optJSONObject("observation"),checks=saved.optJSONObject("checks");if(old==null||checks==null||!checksIssue(checks,context,meaningful).isEmpty())return new JSONObject();
    if(!integer(old.opt("schema"),1,1)||!integer(old.opt("at"),1,Long.MAX_VALUE)||!environment.equals(old.optString("environmentId"))||!integer(old.opt("environmentGeneration"),generation,generation)
        ||!integer(old.opt("configurationRevision"),1,Long.MAX_VALUE)||!integer(old.opt("appVersionCode"),1,Long.MAX_VALUE)||!text(old.opt("engineVersion"),128)||!text(old.opt("appVersion"),128)
        ||!source(context).equals(old.optString("source"))||!integer(old.opt("probeVersion"),checks.optInt("probeVersion"),checks.optInt("probeVersion")))return new JSONObject();
    String top=FingerprintObservationHistory.origin(old.opt("topLevelOrigin")),origin=FingerprintObservationHistory.origin(old.opt("sourceOrigin"));
    if(top.isEmpty()||origin.isEmpty()||!top.equals(old.optString("topLevelOrigin"))||!origin.equals(old.optString("sourceOrigin"))||("crossOriginFrame".equals(context)?top.equals(origin):!top.equals(origin)))return new JSONObject();
    if("crossOriginFrame".equals(context)&&!"extension-background-control".equals(old.optString("controlSource")))return new JSONObject();
    JSONObject observation=new JSONObject();for(String key:new String[]{"schema","at","source","sourceOrigin","topLevelOrigin","probeVersion","environmentId","environmentGeneration","configurationRevision","engineVersion","appVersion","appVersionCode"})put(observation,key,old.opt(key));
    if(text(old.opt("executionId"),128))put(observation,"executionId",old.optString("executionId"));else put(observation,"executionId","");
    if("crossOriginFrame".equals(context))put(observation,"controlSource","extension-background-control");
    Candidate value=new Candidate();value.observation=observation;value.checks=cleanChecks(checks,context);JSONObject out=record(value,context,kind);
    if(PIN_KIND.equals(kind)){if(!integer(saved.opt("pinnedAt"),1,Long.MAX_VALUE))return new JSONObject();put(out,"pinnedAt",saved.optLong("pinnedAt"));}
    return bounded(out,MAX_REFERENCE_BYTES)?out:new JSONObject();
  }
  static JSONObject restoreContextSnapshot(JSONObject saved,String environment,int generation,String context){return restoreRecord(saved,environment,generation,context,SNAPSHOT_KIND,false);}
  static JSONObject restoreReference(JSONObject saved,String environment,int generation,String context){return "main".equals(context)?FingerprintDeepBaseline.restore(saved,environment,generation):restoreRecord(saved,environment,generation,context,PIN_KIND,true);}
  static JSONObject restore(JSONObject saved,String environment,int generation){
    if(!owner(environment,generation)||!bounded(saved,MAX_BYTES))return new JSONObject();
    JSONObject legacy=FingerprintDeepBaseline.restore(saved,environment,generation);if(legacy.length()>0)return aggregate(environment,generation,J.obj("main",legacy));
    if(!integer(saved.opt("schema"),1,1)||!KIND.equals(saved.optString("kind"))||!environment.equals(saved.optString("environmentId"))||!integer(saved.opt("environmentGeneration"),generation,generation)
        ||!Boolean.FALSE.equals(saved.opt("protectionVerified"))||!Boolean.FALSE.equals(saved.opt("leakVerdict")))return new JSONObject();
    JSONObject refs=new JSONObject(),old=object(saved,"refs");for(String context:CONTEXTS){JSONObject pin=restoreReference(object(old,context),environment,generation,context);if(pin.length()>0)put(refs,context,pin);}
    return refs.length()==0?new JSONObject():aggregate(environment,generation,refs);
  }
  private static JSONObject aggregate(String environment,int generation,JSONObject refs){return J.obj("schema",1,"kind",KIND,"environmentId",environment,"environmentGeneration",generation,"refs",refs,"protectionVerified",false,"leakVerdict",false);}
  static JSONObject reference(JSONObject saved,String environment,int generation,String context){return object(object(restore(saved,environment,generation),"refs"),context);}
  static boolean hasReference(JSONObject saved,String environment,int generation,String context){return reference(saved,environment,generation,context).length()>0;}
  static int count(JSONObject saved,String environment,int generation){return object(restore(saved,environment,generation),"refs").length();}
  static JSONObject replace(JSONObject saved,JSONObject report,JSONObject metadata,String context,long pinnedAt){
    String env=metadata==null?"":metadata.optString("environmentId");int generation=metadata==null?-1:metadata.optInt("environmentGeneration",-1);JSONObject before=restore(saved,env,generation),pin=capture(report,metadata,context,pinnedAt);if(pin.length()==0)return before;
    JSONObject refs=copy(object(before,"refs"));put(refs,context,pin);JSONObject out=aggregate(env,generation,refs);return bounded(out,MAX_BYTES)?out:before;
  }
  static JSONObject clear(JSONObject saved,String environment,int generation,String context){JSONObject before=restore(saved,environment,generation);if("all".equals(context))return new JSONObject();if(!context(context)||before.length()==0)return before;JSONObject refs=copy(object(before,"refs"));refs.remove(context);return refs.length()==0?new JSONObject():aggregate(environment,generation,refs);}
  static JSONObject comparison(JSONObject saved,JSONObject report,JSONObject metadata,String context){
    String env=metadata==null?"":metadata.optString("environmentId");int generation=metadata==null?-1:metadata.optInt("environmentGeneration",-1);JSONObject pin=reference(saved,env,generation,context);
    if("main".equals(context)){JSONObject value=FingerprintDeepBaseline.comparison(pin,report,metadata);put(value,"context","main");return value;}
    JSONObject out=J.obj("state","no-reference","context",context,"source",source(context),"apiComparisons",new JSONObject(),"hashComparedCount",0,"hashChangedCount",0,"readbackComparedCount",0,"readbackChangedCount",0,"protectionVerified",false,"leakVerdict",false,"crossExecutionContextComparison",false);
    if(pin.length()==0)return out;
    JSONObject before=object(pin,"observation");put(out,"referenceAt",before.optLong("at"));put(out,"pinnedAt",pin.optLong("pinnedAt"));put(out,"referenceGroup",group(before));
    Candidate current=candidate(report,metadata,context,false);if(!current.issue.isEmpty()){put(out,"state","current-unavailable");put(out,"reason",current.issue);return out;}
    put(out,"currentGroup",group(current.observation));JSONArray separated=new JSONArray();for(String key:GROUP)if(!FingerprintObservationHistory.same(before.opt(key),current.observation.opt(key)))separated.put(key);
    if(separated.length()>0){put(out,"state","separate-context");put(out,"separationReasons",separated);return out;}
    JSONObject operations=new JSONObject();int compared=0,changed=0,readbacks=0,readbackChanged=0;
    for(String api:APIS){
      JSONObject first=object(object(pin,"checks"),"probes").optJSONObject(api),second=object(current.checks,"probes").optJSONObject(api);
      JSONObject value=J.obj("referenceState",first.optString("state"),"currentState",second.optString("state"),"operationStateCompared",true,"operationStateChanged",!first.optString("state").equals(second.optString("state")),"compared",false);
      String a=hash(first,"hash"),b=hash(second,"hash");if(a.isEmpty()||b.isEmpty()){put(value,"state","uncompared");put(value,"reason",a.isEmpty()&&b.isEmpty()?"both-hashes-unavailable":a.isEmpty()?"reference-hash-unavailable":"current-hash-unavailable");}else{boolean difference=!a.equals(b);put(value,"state","comparable");put(value,"compared",true);put(value,"changed",difference);compared++;if(difference)changed++;}
      if("webgl".equals(api)){String x=hash(first,"readbackHash"),y=hash(second,"readbackHash");boolean valid=!x.isEmpty()&&!y.isEmpty();put(value,"readbackCompared",valid);put(value,"readbackState",valid?"comparable":"uncompared");if(valid){boolean difference=!x.equals(y);put(value,"readbackChanged",difference);readbacks++;if(difference)readbackChanged++;}}
      put(operations,api,value);
    }
    put(out,"state","comparable");put(out,"apiComparisons",operations);put(out,"hashComparedCount",compared);put(out,"hashChangedCount",changed);put(out,"readbackComparedCount",readbacks);put(out,"readbackChangedCount",readbackChanged);return out;
  }
  private static JSONObject group(JSONObject value){JSONObject out=new JSONObject();for(String key:GROUP)put(out,key,value.opt(key));return out;}
  static String summary(JSONObject saved,JSONObject report,JSONObject metadata,String context){
    String env=metadata==null?"":metadata.optString("environmentId");int generation=metadata==null?-1:metadata.optInt("environmentGeneration",-1);JSONObject pin=reference(saved,env,generation,context);
    if("main".equals(context))return FingerprintDeepBaseline.summary(pin,report,metadata);
    if(pin.length()==0)return label(context)+"尚未固定参照。请主动完成该执行环境的有效深检，再固定一份；普通检查不会替换参照。";
    JSONObject observation=object(pin,"observation"),comparison=comparison(saved,report,metadata,context);SimpleDateFormat time=new SimpleDateFormat("MM-dd HH:mm:ss",Locale.getDefault());
    StringBuilder text=new StringBuilder(label(context)).append("固定深检参照（本地加密保存）\n观测 ").append(time.format(new Date(observation.optLong("at")))).append(" · 固定 ").append(time.format(new Date(pin.optLong("pinnedAt")))).append("\n来源 ").append(observation.optString("sourceOrigin")).append("\n顶层来源 ").append(observation.optString("topLevelOrigin")).append("\n配置 ").append(observation.optLong("configurationRevision")).append(" · 探针 ").append(observation.optInt("probeVersion"));
    if("separate-context".equals(comparison.optString("state")))text.append("\n\n本次来源、配置、版本或执行环境不同，分别保留，未直接比较输出。");
    else if("current-unavailable".equals(comparison.optString("state")))text.append("\n\n本次结果不可比较，固定参照仍保留。\n").append(comparison.optString("reason"));
    JSONObject results=object(comparison,"apiComparisons");
    for(String api:APIS){JSONObject first=object(object(pin,"checks"),"probes").optJSONObject(api),value=results.optJSONObject(api);text.append("\n\n").append(FingerprintDeepBaseline.label(api)).append(" 参照：").append(FingerprintDeepBaseline.stateLabel(first.optString("state")));if(value==null)continue;text.append("\n本次：").append(FingerprintDeepBaseline.stateLabel(value.optString("currentState")));if(value.optBoolean("operationStateChanged"))text.append("；操作状态有变化");if(value.optBoolean("compared"))text.append(value.optBoolean("changed")?"；哈希有变化":"；本项已比较哈希未变");else text.append("；缺少有效哈希，输出未比较");if(value.optBoolean("readbackCompared"))text.append(value.optBoolean("readbackChanged")?"；读回像素哈希有变化":"；已比较的读回像素哈希未变");}
    return text.append("\n\n每个执行环境独立固定、替换与清除。不同页面、Worker 或 iframe 不要求哈希相同；结果变化不等于泄漏，也不证明保护有效或失效。Shared Worker 与 Service Worker 尚未覆盖。").toString();
  }
}
