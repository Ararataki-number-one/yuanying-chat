package local.pocketchat;

import org.json.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

/** Clipboard projection only. Never serializes a source object or arbitrary source text. */
final class AuditDiagnosticExport {
  static final int SCHEMA=1,MAX_ROWS=96,MAX_OBJECT_FIELDS=128,MAX_BYTES=32768;
  static final long MAX_COUNTER=9007199254740991L;
  static final String[] CONTEXTS={"main","worker","frame","crossOriginFrame"},APIS={"canvas","audio","fonts","webgl"};
  static final String[] STATES={"verified","issue","uncovered","available","restricted","failed"};
  static final String[] MANUAL={"login","input","attachment","drawing","recovery","restart","background"};
  static final Set<String> ROW_KEYS=rows();
  private static Set<String> rows(){
    Set<String> keys=new HashSet<>(Arrays.asList("provenance","ua","hints","navigator-frame","navigator-worker","frame","worker","display-frame","display-worker","worker-header","early","rtc","zone","language","ipv4","ipv6","header","header-language","network","cross-origin","shared-worker","service-worker","native-setting","dns","udp","request-worker-script-ua","request-worker-script-language","request-context-headers","request-context-language-semantics","request-native-ua","request-native-language","request-peer","request-cross-origin-frame"));
    for(String api:APIS){keys.add("api-"+api);for(String context:new String[]{"frame","worker"})keys.add("api-"+context+"-"+api);}
    for(String context:new String[]{"document","worker"}){for(String suffix:new String[]{"ua","language","language-list"})keys.add("request-"+context+"-"+suffix);keys.add("request-native-"+context+"-language-list");}
    for(String api:new String[]{"canvas","webgl"})keys.add("request-cross-origin-frame-"+api);
    return Collections.unmodifiableSet(keys);
  }
  static JSONObject object(JSONObject parent,String key){if(parent==null||parent.length()>MAX_OBJECT_FIELDS)return new JSONObject();JSONObject value=parent.optJSONObject(key);return value==null||value.length()>MAX_OBJECT_FIELDS?new JSONObject():value;}
  static boolean integer(Object value,long min,long max){return (value instanceof Integer||value instanceof Long)&&((Number)value).longValue()>=min&&((Number)value).longValue()<=max;}
  static void number(JSONObject out,JSONObject input,String key,long min,long max){if(input!=null&&integer(input.opt(key),min,max))put(out,key,((Number)input.opt(key)).longValue());}
  static void flag(JSONObject out,JSONObject input,String key){if(input!=null&&input.opt(key) instanceof Boolean)put(out,key,input.optBoolean(key));}
  static void put(JSONObject out,String key,Object value){try{out.put(key,value);}catch(JSONException ignored){}}
  static String choice(Object value,String fallback,String... allowed){if(value instanceof String)for(String item:allowed)if(item.equals(value))return item;return fallback;}
  static boolean owner(JSONObject input,JSONObject snapshot){
    Object id=snapshot.opt("environmentId");Object generation=snapshot.opt("environmentGeneration");
    return id instanceof String&&((String)id).length()==36&&((String)id).matches("[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
      &&integer(generation,0,Integer.MAX_VALUE)&&id.equals(input.opt("environmentId"))&&integer(input.opt("environmentGeneration"),((Number)generation).longValue(),((Number)generation).longValue());
  }
  static boolean hasOwner(JSONObject input){return input.has("environmentId")||input.has("environmentGeneration");}
  static boolean requestOwner(JSONObject input,JSONObject snapshot){
    Object raw=input.opt("expected");if(input.has("expected")&&(!(raw instanceof JSONObject)||((JSONObject)raw).length()>MAX_OBJECT_FIELDS))return false;
    JSONObject expected=object(input,"expected");boolean top=hasOwner(input),nested=hasOwner(expected);
    return (top||nested)&&(!top||owner(input,snapshot))&&(!nested||owner(expected,snapshot));
  }
  static JSONObject metadata(JSONObject input){JSONObject out=new JSONObject();for(String key:new String[]{"environmentGeneration","configurationRevision","appVersionCode","probeVersion","at","savedAt","pinnedAt"})number(out,input,key,0,MAX_COUNTER);return out;}
  static JSONObject rowStates(JSONObject report){
    JSONObject states=new JSONObject();JSONArray rows=report==null?null:report.optJSONArray("rows");
    if(rows==null)return J.obj("available",false,"states",states,"omittedRows",0);
    if(rows.length()>MAX_ROWS)return J.obj("available",false,"states",states,"rowLimitExceeded",true,"omittedRows",rows.length());
    Set<String> seen=new HashSet<>(),duplicates=new HashSet<>();int omitted=0;
    for(int i=0;i<rows.length();i++){
      JSONObject row=rows.optJSONObject(i);Object key=row==null?null:row.opt("key");
      if(row==null||row.length()>MAX_OBJECT_FIELDS||!(key instanceof String)||((String)key).length()>64||!ROW_KEYS.contains(key)){omitted++;continue;}
      String name=(String)key;if(!seen.add(name)){if(duplicates.add(name))omitted++;states.remove(name);omitted++;continue;}
      String state=choice(row.opt("state"),"uncovered",STATES);put(states,name,state);
    }
    for(String duplicate:duplicates)states.remove(duplicate);
    return J.obj("available",true,"states",states,"omittedRows",omitted,"duplicateRowsRejected",duplicates.size());
  }
  static JSONObject protection(JSONObject input){
    JSONObject out=J.obj("state",choice(input.opt("state"),"unknown","confirmed","pending","failed"),"fullApiProtectionAttested",false);
    for(String key:new String[]{"received","settingsReadbackConfirmed","observedFingerprinting","newRequestsBlocked"})flag(out,input,key);
    for(String key:new String[]{"desiredLevel","level"})number(out,input,key,-1,2);
    for(String key:new String[]{"generation","token"})number(out,input,key,0,MAX_COUNTER);
    number(out,input,"attempt",0,3);number(out,input,"maxAttempts",3,3);
    if("confirmed".equals(out.optString("state"))&&(!Boolean.TRUE.equals(out.opt("received"))||!Boolean.TRUE.equals(out.opt("settingsReadbackConfirmed"))
        ||!integer(out.opt("desiredLevel"),0,2)||!Objects.equals(out.opt("desiredLevel"),out.opt("level"))
        ||!(out.opt("observedFingerprinting") instanceof Boolean)||out.optBoolean("observedFingerprinting")!=(out.optLong("desiredLevel")>=2)
        ||!Boolean.FALSE.equals(out.opt("newRequestsBlocked"))||!integer(out.opt("generation"),1,MAX_COUNTER)||!integer(out.opt("token"),1,MAX_COUNTER)
        ||!integer(out.opt("attempt"),1,3)||!integer(out.opt("maxAttempts"),3,3)))put(out,"state","unknown");
    return out;
  }
  static JSONObject checks(JSONObject input,String context){
    String source="main".equals(context)?"page-main-world":"worker".equals(context)?"dedicated-worker":"frame".equals(context)?"same-origin-srcdoc":"controlled-cross-origin-iframe";
    boolean envelope=integer(input.opt("schema"),1,1)&&integer(input.opt("probeVersion"),1,100000)&&Boolean.TRUE.equals(input.opt("requested"))&&Boolean.FALSE.equals(input.opt("protectionVerified"))&&source.equals(input.opt("source"));
    JSONObject out=J.obj("requested",envelope,"sourceEnvelopeValid",envelope,"operationEvidenceValidated",false,"protectionVerified",false),probes=new JSONObject();if(envelope)number(out,input,"probeVersion",1,100000);
    JSONObject raw=object(input,"probes");
    for(String api:APIS){JSONObject probe=object(raw,api);String state=envelope?choice(probe.opt("state"),"uncovered","available","restricted","failed","uncovered"):"uncovered";
      if(("worker".equals(context)||"crossOriginFrame".equals(context))&&("audio".equals(api)||"fonts".equals(api)))state="uncovered";
      JSONObject value=J.obj("reportedState",state);boolean observed="available".equals(state)||"restricted".equals(state);
      for(String field:new String[]{"hash","readbackHash"}){
        String algorithm="readbackHash".equals(field)?"readbackHashAlgorithm":"hashAlgorithm";Object hash=probe.opt(field);
        if(observed&&hash instanceof String&&((String)hash).length()==64&&((String)hash).matches("[0-9a-f]{64}")&&"sha256".equals(probe.opt(algorithm)))put(value,field,hash);
      }
      put(probes,api,value);
    }
    put(out,"probes",probes);return out;
  }
  static JSONObject currentContexts(JSONObject report,JSONObject request){
    JSONObject sample=object(report,"signals"),contexts=new JSONObject();put(contexts,"main",checks(object(sample,"apiChecks"),"main"));
    JSONObject others=object(sample,"apiContexts");for(String context:new String[]{"worker","frame"})put(contexts,context,checks(object(others,context),context));
    put(contexts,"crossOriginFrame",checks(object(object(object(request,"browser"),"crossOriginFrame"),"apiChecks"),"crossOriginFrame"));return contexts;
  }
  static JSONObject references(JSONObject saved,JSONObject snapshot){
    JSONObject out=new JSONObject();if(!owner(saved,snapshot))return out;JSONObject refs=object(saved,"refs");
    for(String context:CONTEXTS){JSONObject ref=object(refs,context),observation=object(ref,"observation");if(!owner(observation,snapshot))continue;
      JSONObject value=J.obj("metadata",metadata(observation),"checks",checks(object(ref,"checks"),context));number(value,ref,"pinnedAt",1,MAX_COUNTER);put(out,context,value);}
    return out;
  }
  static JSONObject comparison(JSONObject saved,JSONObject snapshot){
    JSONObject out=new JSONObject();if(!owner(saved,snapshot))return out;JSONObject slots=object(saved,"slots");
    for(String slot:new String[]{"standard","enhanced"}){JSONObject record=object(slots,slot),group=object(record,"group");if(!owner(group,snapshot))continue;
      JSONObject contexts=new JSONObject(),rawContexts=object(record,"contexts");
      for(String context:CONTEXTS){JSONObject ref=object(rawContexts,context);if(owner(object(ref,"observation"),snapshot))put(contexts,context,J.obj("metadata",metadata(object(ref,"observation")),"checks",checks(object(ref,"checks"),context)));}
      JSONObject manual=new JSONObject(),rawManual=object(record,"compatibility");for(String key:MANUAL)put(manual,key,choice(rawManual.opt(key),"not-tested","not-tested","pass","fail","not-applicable"));
      JSONObject value=J.obj("metadata",metadata(group),"nativeProtection",protection(object(record,"nativeSettings")),"contexts",contexts,"compatibility",manual,"manualResultsIndependentlyVerified",false);number(value,record,"savedAt",1,MAX_COUNTER);put(out,slot,value);
    }
    return out;
  }
  static String copy(String kind,JSONObject snapshot){
    if(!Arrays.asList("summary","deep","comparison").contains(kind)||snapshot==null||snapshot.length()>MAX_OBJECT_FIELDS)return unavailable();
    JSONObject report=object(snapshot,"report"),request=object(snapshot,"requestIdentity"),meta=object(report,"observationMetadata");
    JSONObject out=J.obj("schema",SCHEMA,"kind","redacted-local-audit-diagnostics","detail",kind,"rawTextIncluded",false,"physicalPhoneAcceptance",false,"protectionVerified",false,"leakVerdict",false,
      "running",Boolean.TRUE.equals(snapshot.opt("running")),"storageIssuePresent",Boolean.TRUE.equals(snapshot.opt("storageIssue")),"errorPresent",Boolean.TRUE.equals(snapshot.opt("error")),"nativeProtection",protection(object(snapshot,"nativeProtection")));
    number(out,snapshot,"environmentGeneration",0,Integer.MAX_VALUE);
    if(!"comparison".equals(kind)){
      boolean reportOwned=owner(meta,snapshot);JSONObject ownedReport=reportOwned?report:new JSONObject();
      boolean current=reportOwned&&Boolean.TRUE.equals(snapshot.opt("current"))&&!Boolean.TRUE.equals(snapshot.opt("running"))&&Boolean.TRUE.equals(report.opt("fresh"));
      put(out,"observation",J.obj("currentAtCopy",current,"ownerMatched",reportOwned,"metadata",metadata(reportOwned?meta:new JSONObject()),"rows",rowStates(ownedReport)));
      boolean requestOwned=requestOwner(request,snapshot);put(out,"requestIdentity",requestOwned?J.obj("status",choice(request.opt("status"),"unknown","observed","issue","uncovered"),"rows",rowStates(request)):J.obj("status","unavailable"));
      JSONObject service=object(snapshot,"service");put(out,"service",owner(service,snapshot)?J.obj("status",choice(service.opt("status"),"unknown","ready","failed","unavailable"),"currentAtCopy",Boolean.TRUE.equals(snapshot.opt("serviceCurrent"))):J.obj("status","unavailable"));
      if("deep".equals(kind)){put(out,"contexts",currentContexts(ownedReport,requestOwned?request:new JSONObject()));put(out,"fixedReferences",references(object(snapshot,"fixedReferences"),snapshot));}
    }
    if(!"summary".equals(kind))put(out,"localComparison",comparison(object(snapshot,"localComparison"),snapshot));
    String text=out.toString();return text!=null&&text.getBytes(StandardCharsets.UTF_8).length<=MAX_BYTES?text:unavailable();
  }
  static String unavailable(){return "{\"schema\":1,\"kind\":\"redacted-local-audit-diagnostics\",\"status\":\"unavailable\",\"rawTextIncluded\":false,\"protectionVerified\":false,\"physicalPhoneAcceptance\":false,\"leakVerdict\":false}";}
}
