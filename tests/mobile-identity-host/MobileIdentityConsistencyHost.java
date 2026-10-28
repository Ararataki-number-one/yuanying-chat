package local.pocketchat;

import org.json.*;

/** Production report methods on labelled host observations; no browser execution. */
public final class MobileIdentityConsistencyHost {
  static int checks;
  static void check(String name,boolean pass){if(!pass)throw new AssertionError(name);checks++;}
  static JSONObject copy(JSONObject value)throws Exception{return new JSONObject(value.toString());}
  static JSONObject signal(){return J.obj("ua","Mozilla/5.0 (Android 14; Mobile; rv:157.0) Gecko/157.0 Firefox/157.0","platform","Linux armv8l","appVersion","5.0 (Android 14)","language","en-US","languages",new JSONArray().put("en-US"),"cpu",8,"memory",JSONObject.NULL,"offset",0,"zone","UTC","rtc","absent","screen",J.obj("width",412,"height",915),"viewport",J.obj("width",412,"height",800,"pixelRatio",2.625,"touch",5));}
  static JSONObject sample(JSONObject parent)throws Exception{return J.obj("provenance","page-main-world","mainWorld",J.obj("observed",true),"parent",parent,"frame",copy(parent),"worker",copy(parent));}
  static JSONObject report(JSONObject sample,String display,boolean fresh){JSONObject parent=sample.optJSONObject("parent");return AuditReport.build(sample,new JSONObject(),J.obj("engine","gecko","ua",parent.optString("ua"),"major",157,"level",1,"language","en-US","offset",0,"display",display),false,fresh);}
  static JSONObject row(JSONObject report,String key){JSONArray rows=report.optJSONArray("rows");for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);if(key.equals(row.optString("key")))return row;}throw new AssertionError("Missing row "+key);}
  static boolean state(JSONObject value,String wanted){return wanted.equals(value.optString("state"));}
  public static void main(String[] args)throws Exception{
    JSONObject parent=signal(),input=sample(parent);String original=input.toString();
    JSONObject result=report(input,"mobile",true),identity=result.getJSONObject("mobileIdentityCoverage");
    check("Current main-world frame navigator fields compare",state(row(result,"navigator-frame"),AuditReport.VERIFIED));
    check("Current main-world Worker navigator fields compare",state(row(result,"navigator-worker"),AuditReport.VERIFIED));
    check("Mobile configuration is labelled without inventing a phone model","mobile".equals(identity.optString("display"))&&!identity.optBoolean("deviceModelVerified",true));
    check("Navigator equality does not certify request headers or protection",!identity.optBoolean("httpHeadersVerified",true)&&!identity.optBoolean("protectionVerified",true)&&Boolean.FALSE.equals(result.opt("fingerprintTemplateAcceptance")));
    for(String context:new String[]{"frame","worker"})for(String field:new String[]{"platform","appVersion"}){
      JSONObject changed=copy(input);changed.getJSONObject(context).put(field,"different actual public value");JSONObject observation=report(changed,"mobile",true).getJSONObject("mobileIdentityCoverage").getJSONObject(context);
      check("Public difference is retained "+context+" "+field,state(observation,AuditReport.ISSUE)&&observation.getJSONArray("different").toString().contains(field));
    }
    for(String field:new String[]{"platform","appVersion"}){
      Object[] invalid={JSONObject.NULL,true,42,"","   ","line\nfeed",new JSONArray().put("unexpected")};
      for(Object raw:invalid){JSONObject changed=copy(input);changed.getJSONObject("worker").put(field,raw);JSONObject value=report(changed,"mobile",true).getJSONObject("mobileIdentityCoverage").getJSONObject("worker");check("Malformed field cannot verify "+field+" "+String.valueOf(raw),state(value,AuditReport.UNCOVERED)&&value.getJSONArray("missingOrInvalid").toString().contains(field));}
      JSONObject missing=copy(input);missing.getJSONObject("worker").remove(field);JSONObject missingResult=report(missing,"mobile",true).getJSONObject("mobileIdentityCoverage").getJSONObject("worker");check("Missing Worker field is not copied from parent "+field,state(missingResult,AuditReport.UNCOVERED)&&!missing.getJSONObject("worker").has(field));
      int limit="platform".equals(field)?128:1024;StringBuilder exact=new StringBuilder();for(int i=0;i<limit;i++)exact.append('a');JSONObject a=signal(),b=signal();a.put(field,exact.toString());b.put(field,exact.toString());check("Exact text boundary remains observable "+field,state(AuditReport.navigatorIdentityCoverage(a,b,true,true),AuditReport.VERIFIED));b.put(field,exact.toString()+"a");check("Oversized text remains uncovered "+field,state(AuditReport.navigatorIdentityCoverage(a,b,true,true),AuditReport.UNCOVERED));
    }
    JSONObject stale=report(input,"mobile",false).getJSONObject("mobileIdentityCoverage");check("Stale input cannot confirm platform/version",state(stale.getJSONObject("frame"),AuditReport.UNCOVERED)&&!stale.getJSONObject("frame").optBoolean("current",true)&&stale.getJSONObject("frame").getJSONArray("compared").length()==0);
    JSONObject fallback=copy(input);fallback.put("provenance","extension-isolated-world-fallback").put("mainWorld",J.obj("observed",false));JSONObject isolated=report(fallback,"mobile",true).getJSONObject("mobileIdentityCoverage");check("Isolated world is not page evidence",state(isolated.getJSONObject("worker"),AuditReport.UNCOVERED)&&isolated.getJSONObject("worker").getJSONArray("compared").length()==0);
    JSONObject viewport=copy(input);viewport.getJSONObject("frame").getJSONObject("viewport").put("width",100).put("height",50);check("Keyboard and iframe viewport sizes do not change navigator or display equality",state(row(report(viewport,"mobile",true),"navigator-frame"),AuditReport.VERIFIED)&&state(row(report(viewport,"mobile",true),"display-frame"),AuditReport.VERIFIED));
    JSONObject rotation=copy(input);rotation.getJSONObject("frame").getJSONObject("screen").put("width",915).put("height",412);check("Existing display comparison preserves rotation normalization",state(row(report(rotation,"mobile",true),"display-frame"),AuditReport.VERIFIED));
    JSONObject dpr=copy(input);dpr.getJSONObject("frame").getJSONObject("viewport").put("pixelRatio",3);JSONObject dprReport=report(dpr,"mobile",true);check("Actual DPR differences remain separate from matching navigator values",state(row(dprReport,"display-frame"),AuditReport.ISSUE)&&state(row(dprReport,"navigator-frame"),AuditReport.VERIFIED));
    JSONObject touch=copy(input);touch.getJSONObject("frame").getJSONObject("viewport").put("touch",1.5);check("Fractional touch count is uncovered",state(row(report(touch,"mobile",true),"display-frame"),AuditReport.UNCOVERED));
    JSONObject worker=copy(input);worker.getJSONObject("worker").remove("screen");worker.getJSONObject("worker").remove("viewport");JSONObject workerReport=report(worker,"mobile",true);check("Worker absent window APIs do not become navigator mismatches",state(row(workerReport,"display-worker"),AuditReport.UNCOVERED)&&state(row(workerReport,"navigator-worker"),AuditReport.VERIFIED));
    JSONObject desktop=signal();desktop.put("platform","Win32").put("appVersion","5.0 (Windows)");JSONObject desktopReport=report(sample(desktop),"desktop",true);check("Desktop display remains supported without forced Android fields","desktop".equals(desktopReport.getJSONObject("mobileIdentityCoverage").optString("display"))&&state(row(desktopReport,"navigator-worker"),AuditReport.VERIFIED));
    check("Unknown display mode is explicit","unspecified".equals(report(input,"invented",true).getJSONObject("mobileIdentityCoverage").optString("display")));
    check("Legacy network scope is retained",state(row(result,"worker-header"),AuditReport.UNCOVERED)&&!result.optBoolean("fullDesktopUaConsistency",true));
    check("Report creation does not mutate or synthesize input",original.equals(input.toString()));
    System.out.println(J.obj("status","passed","passed",checks,"actualAndroidExecution",false,"actualGeckoExecution",false,"actualNetworkExecution",false,"scope","Production AuditReport over synthetic host observations; no phone, webpage, HTTP identity or privacy-effectiveness acceptance"));
  }
}
