package local.pocketchat;

import java.util.*;
import org.json.*;

/** Pure configuration/report tests. These do not certify Android engine execution. */
public final class FingerprintTemplateTest {
  static int checks;static final JSONArray assertions=new JSONArray();
  static void check(String text,boolean pass){assertions.put(J.obj("name",text,"pass",pass));if(!pass)throw new AssertionError(text);checks++;}
  static JSONObject row(JSONObject report,String key){JSONArray rows=report.optJSONArray("rows");for(int i=0;i<rows.length();i++)if(key.equals(rows.optJSONObject(i).optString("key")))return rows.optJSONObject(i);throw new AssertionError("Missing row "+key);}
  static boolean state(JSONObject report,String key,String expected){return expected.equals(row(report,key).optString("state"));}
  public static void main(String[] args)throws Exception{
    for(String id:Arrays.asList(BrowserIdentitySpec.MOBILE,BrowserIdentitySpec.DESKTOP,BrowserIdentitySpec.COMPATIBLE,BrowserIdentitySpec.COMPATIBLE_DESKTOP,BrowserIdentitySpec.RFP,BrowserIdentitySpec.RFP_DESKTOP)){
      BrowserIdentitySpec preset=BrowserIdentitySpec.preset(id);check("Coherent preset "+id,preset.validate().isEmpty());check("Roundtrip "+id,BrowserIdentitySpec.from(preset.json()).json().toString().equals(preset.json().toString()));
    }
    for(boolean desktop:new boolean[]{false,true})for(int level=0;level<=2;level++){BrowserIdentitySpec migrated=BrowserIdentitySpec.legacy(desktop,level);check("Legacy display/privacy retained",migrated.desktop()==desktop&&migrated.protectionLevel()==level&&migrated.validate().isEmpty());}
    check("Contradictory desktop preset rejected",!new BrowserIdentitySpec(BrowserIdentitySpec.DESKTOP,"mobile","standard",Collections.emptyList(),"system").validate().isEmpty());
    check("Contradictory privacy rejected",!new BrowserIdentitySpec(BrowserIdentitySpec.MOBILE,"mobile","native-rfp",Collections.emptyList(),"native-standardized").validate().isEmpty());
    check("Independent timezone not fabricated",!new BrowserIdentitySpec(BrowserIdentitySpec.MOBILE,"mobile","standard",Collections.emptyList(),"Asia/Tokyo").validate().isEmpty());
    check("Native language tags accepted",BrowserIdentitySpec.preset(BrowserIdentitySpec.MOBILE).withLocales(Arrays.asList("zh-CN","en-US")).validate().isEmpty());
    for(List<String> invalid:Arrays.asList(Arrays.asList("en_US"),Arrays.asList("en-US","en-us"),Arrays.asList("en-US","zh-CN","ja-JP","fr-FR"),Arrays.asList(""),Arrays.asList("<script>"),Arrays.asList("zh-Hant-TW","zh-TW"),Arrays.asList("iw-IL","he-IL"),Arrays.asList("de-DE-1996","de-DE")))check("Invalid languages rejected "+invalid,!BrowserIdentitySpec.preset(BrowserIdentitySpec.MOBILE).withLocales(invalid).validate().isEmpty());
    ArrayList<String> input=new ArrayList<>(Arrays.asList("en-US"));BrowserIdentitySpec defensive=BrowserIdentitySpec.preset(BrowserIdentitySpec.MOBILE).withLocales(input);input.clear();check("Identity captures immutable locale list",defensive.locales.size()==1);
    boolean customRejected=false;try{BrowserIdentitySpec.from(J.obj("ua","Mozilla Chrome/157"));}catch(IllegalArgumentException expected){customRejected=true;}check("Unsupported custom UA rejected",customRejected);
    check("Script and region are predicted separately from preserved request",BrowserIdentitySpec.expectedSdkLocales(Arrays.asList("zh-Hant-TW","en-US-u-mu-celsius","de-DE-1996")).equals(Arrays.asList("zh-TW","en-US","de-DE")));
    check("Legacy language aliases follow SDK normalization",BrowserIdentitySpec.expectedSdkLocales(Arrays.asList("iw-IL","in-ID","ji")).equals(Arrays.asList("he-IL","id-ID","yi")));
    BrowserIdentitySpec scripted=BrowserIdentitySpec.preset(BrowserIdentitySpec.MOBILE).withLocales(Collections.singletonList("zh-Hant-TW"));
    check("Desired language retains script for honest requested-versus-observed distinction",scripted.validate().isEmpty()&&"zh-Hant-TW".equals(scripted.json().getJSONArray("locales").getString(0)));
    boolean policyMessage=false;try{BrowserIdentitySpec.from(J.obj("userAgent","Mozilla"));}catch(IllegalArgumentException rejected){policyMessage=rejected.getMessage().contains("模板")&&!rejected.getMessage().contains("内核不支持");}check("Custom UA rejection describes product template scope",policyMessage);
    boolean futureRejected=false;try{BrowserIdentitySpec.from(J.obj("schema",2));}catch(IllegalArgumentException expected){futureRejected=true;}check("Future browser schema rejected",futureRejected);
    String ua="Mozilla/5.0 (Android 14; Mobile; rv:157.0) Gecko/157.0 Firefox/157.0";
    JSONObject signal=J.obj("ua",ua,"language","en-US","languages",new JSONArray(Arrays.asList("en-US")),"cpu",8,"memory",JSONObject.NULL,"offset",-540,"zone","Asia/Tokyo","rtc","absent");
    JSONObject expected=J.obj("engine","gecko","ua",ua,"major",157,"level",1,"offset",-540,"language","en-US","timezoneStrategy","system","rfpAcknowledged",true);
    JSONObject sample=J.obj("parent",signal,"frame",new JSONObject(signal.toString()),"worker",new JSONObject(signal.toString()),"provenance","page-main-world","mainWorld",J.obj("observed",true));
    JSONObject observed=AuditReport.build(sample,new JSONObject(),expected,false,true);
    check("Main-world observation identified",state(observed,"provenance",AuditReport.VERIFIED));check("Matching public UA observation",state(observed,"ua",AuditReport.VERIFIED));
    check("Matching language observation",state(observed,"language",AuditReport.VERIFIED));
    check("Complete same-origin fields can be compared",state(observed,"frame",AuditReport.VERIFIED));
    check("Complete Dedicated Worker fields can be compared",state(observed,"worker",AuditReport.VERIFIED));
    check("Matching Worker JS fields do not certify Worker HTTP headers",state(observed,"worker",AuditReport.VERIFIED)&&state(observed,"worker-header",AuditReport.UNCOVERED));
    check("Matching browser fields cannot claim full desktop UA or fingerprint acceptance",Boolean.FALSE.equals(observed.opt("fullDesktopUaConsistency"))&&Boolean.FALSE.equals(observed.opt("fingerprintTemplateAcceptance")));
    for(String context:Arrays.asList("frame","worker")){
      JSONObject onlyUa=new JSONObject(sample.toString());onlyUa.put(context,J.obj("ua",ua));
      check("UA-only context cannot verify "+context,state(AuditReport.build(onlyUa,new JSONObject(),expected,false,true),context,AuditReport.UNCOVERED));
      for(String field:AuditReport.CONTEXT_FIELDS){JSONObject missing=new JSONObject(sample.toString());missing.getJSONObject(context).remove(field);JSONObject result=AuditReport.build(missing,new JSONObject(),expected,false,true);check("Missing field cannot verify "+context+" "+field,state(result,context,AuditReport.UNCOVERED)&&result.getJSONObject("contextCoverage").getJSONObject(context).getJSONArray("missingOrInvalid").toString().contains(field));}
      for(String field:Arrays.asList("cpu","memory","offset","language","languages","zone")){JSONObject malformed=new JSONObject(sample.toString());malformed.getJSONObject(context).put(field,J.obj("invalid",true));check("Wrong type cannot verify "+context+" "+field,state(AuditReport.build(malformed,new JSONObject(),expected,false,true),context,AuditReport.UNCOVERED));}
    }
    JSONObject listDifference=new JSONObject(sample.toString());listDifference.getJSONObject("worker").put("languages",new JSONArray(Arrays.asList("en-US","ja-JP")));check("Additional Worker language is a real observed difference",state(AuditReport.build(listDifference,new JSONObject(),expected,false,true),"worker",AuditReport.ISSUE));
    JSONObject timezoneDifference=new JSONObject(sample.toString());timezoneDifference.getJSONObject("frame").put("zone","Europe/London");check("Equal offset cannot hide a different timezone name",state(AuditReport.build(timezoneDifference,new JSONObject(),expected,false,true),"frame",AuditReport.ISSUE));
    JSONObject invalidOffset=new JSONObject(sample.toString());invalidOffset.getJSONObject("parent").put("offset","-540");check("String offset cannot become a verified numeric timezone",state(AuditReport.build(invalidOffset,new JSONObject(),expected,false,true),"zone",AuditReport.UNCOVERED));
    JSONObject rawExpected=new JSONObject(expected.toString());rawExpected.put("language","zh-TW");JSONObject normalizedSample=new JSONObject(sample.toString());normalizedSample.getJSONObject("parent").put("language","zh-TW");check("SDK normalized language compared against page rather than raw script tag",state(AuditReport.build(normalizedSample,new JSONObject(),rawExpected,false,true),"language",AuditReport.VERIFIED));
    for(String path:Arrays.asList("cross-origin","shared-worker","service-worker","dns","udp"))check("Unobserved path remains uncovered "+path,state(observed,path,AuditReport.UNCOVERED));
    JSONObject isolated=new JSONObject(sample.toString());isolated.put("provenance","extension-isolated-world-fallback");isolated.put("mainWorld",J.obj("observed",false));
    JSONObject fallback=AuditReport.build(isolated,new JSONObject(),expected,false,true);
    for(String path:Arrays.asList("ua","frame","worker","rtc","zone","language"))check("Isolated fallback cannot prove page field "+path,state(fallback,path,AuditReport.UNCOVERED));
    JSONObject rfp=new JSONObject(expected.toString());rfp.put("timezoneStrategy","native-standardized");rfp.put("offset",0);check("Native-standardized offset never falsely compared with phone",state(AuditReport.build(sample,new JSONObject(),rfp,false,true),"zone",AuditReport.UNCOVERED));
    JSONObject stale=AuditReport.build(sample,new JSONObject(),expected,false,false);check("Changed environment invalidates UA",state(stale,"ua",AuditReport.UNCOVERED));
    JSONObject workerDifference=new JSONObject(sample.toString());workerDifference.getJSONObject("worker").put("language","ja-JP");check("Cross-context language difference remains visible",state(AuditReport.build(workerDifference,new JSONObject(),expected,false,true),"worker",AuditReport.ISSUE));
    JSONObject network=new JSONObject(sample.toString());network.put("network",J.obj("headers",J.obj("headers",J.obj("User-Agent",ua,"Accept-Language","en-US,en;q=0.5"))));
    JSONObject headerReport=AuditReport.build(network,new JSONObject(),expected,true,true);check("Real echo UA compared only when main-world known",state(headerReport,"header",AuditReport.VERIFIED));check("Echo language compared",state(headerReport,"header-language",AuditReport.VERIFIED));check("Headers scope admits content request limitation",row(headerReport,"header-language").optString("detail").contains("Gecko 内容脚本"));
    check("Matching echo does not cover Worker HTTP or complete desktop UA",state(headerReport,"header",AuditReport.VERIFIED)&&state(headerReport,"worker-header",AuditReport.UNCOVERED)&&Boolean.FALSE.equals(headerReport.opt("fullDesktopUaConsistency")));
    JSONObject differingEcho=new JSONObject(network.toString());differingEcho.getJSONObject("network").getJSONObject("headers").getJSONObject("headers").put("User-Agent","Observed different HTTP UA");
    check("A real HTTP echo difference stays visible rather than inheriting matching JS",state(AuditReport.build(differingEcho,new JSONObject(),expected,true,true),"header",AuditReport.ISSUE));
    System.out.println(J.obj("schema",1,"status","passed","passed",checks,"total",checks,"checks",assertions,"actualAndroidExecution",false,"scope","Production template validation and AuditReport on JVM; no Gecko or Android execution").toString());
  }
}
