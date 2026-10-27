package local.pocketchat;

import org.json.*;

/** Actual production parsing/admission on controlled inputs, not browser execution. */
public final class RequestIdentityCoverageHost {
  static final String N=RequestIdentityAuditHost.NONCE,B=RequestIdentityAuditHost.BASE,F="https://frame.example/pocketchat-identity/v1/",H="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
  static final JSONArray checks=new JSONArray();static int passed;
  static void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));if(pass)passed++;}
  static JSONObject copy(JSONObject value){return J.parse(value.toString());}
  static JSONObject language(String h,String primary,String... list){return RequestIdentityLanguages.compare(h,new JSONArray(java.util.Arrays.asList(list)),primary);}
  static boolean state(JSONObject value,String wanted){return wanted.equals(value.optString("state"));}
  static boolean row(JSONObject value,String key,String wanted){return RequestIdentityAuditHost.state(value,key,wanted);}
  static boolean service(String target,boolean active,boolean registered,boolean fresh,long now){return RequestIdentityAudit.serviceRequestAllowed(target,B,N,active,registered,fresh,now,20);}
  static boolean frame(String target,boolean enabled,boolean registered){return RequestIdentityAudit.controlledRequestAllowed(target,B,N,true,true,true,10,20,enabled,F,registered);}
  static JSONObject expected(){try{return RequestIdentityAuditHost.expected().put("languages",J.arr("ja-JP","en-US"));}catch(JSONException error){throw new RuntimeException(error);}}
  static JSONObject evaluate(JSONObject browser,JSONObject expected){return RequestIdentityAudit.evaluate(browser,RequestIdentityAuditHost.server(),expected,N,B,true);}
  static JSONObject frameValue(){
    JSONObject canvas=J.obj("state","available","reason","draw-and-pixel-readback-completed","pixels",4096,"hash",H,"hashAlgorithm","sha256"),webgl=J.obj("state","restricted","reason","unmasked-renderer-extension-unavailable","readbackPixels",256,"readbackBytes",1024,"hash",H,"hashAlgorithm","sha256","readbackHash",H,"readbackHashAlgorithm","sha256","version","WebGL 1.0","renderer","controlled","maxTextureSize",4096);
    return J.obj("status","complete","nonce",N,"source","controlled-cross-origin-iframe","origin","https://frame.example","apiChecks",J.obj("schema",1,"requested",true,"source","controlled-cross-origin-iframe","probeVersion",1,"status","completed","protectionVerified",false,"limits",J.obj("canvasPixels",4096,"audioFrames",0,"fontCandidates",0,"totalBudgetMs",1200),"probes",J.obj("canvas",canvas,"webgl",webgl,"audio",J.obj("state","uncovered"),"fonts",J.obj("state","uncovered"))));
  }
  static JSONObject frameExpected(){try{return expected().put("crossOriginFrame",true).put("frameEndpoint",F);}catch(JSONException error){throw new RuntimeException(error);}}
  static JSONObject frameBrowser(){try{return RequestIdentityAuditHost.browser().put("crossOriginFrame",frameValue());}catch(JSONException error){throw new RuntimeException(error);}}
  static JSONObject pendingWithout(String absent)throws Exception{
    JSONObject server=RequestIdentityAuditHost.server();JSONArray records=server.getJSONArray("events"),kept=new JSONArray();
    for(int i=0;i<records.length();i++){JSONObject event=copy(records.getJSONObject(i));if(!absent.equals(event.optString("source"))){event.put("index",kept.length()+1);kept.put(event);}}
    return server.put("status","pending").put("events",kept);
  }
  static JSONObject pendingResult(JSONObject server){return RequestIdentityAudit.evaluate(RequestIdentityAuditHost.browser(),server,expected(),N,B,true);}
  static boolean uncredited(JSONObject result){return "uncovered".equals(result.optString("status"))&&!result.optBoolean("sourcePresenceKnown",true)&&result.optJSONArray("reportedSources")!=null&&result.optJSONArray("reportedSources").length()==0;}
  static void pendingSourceControls()throws Exception{
    for(String missing:new String[]{"document","worker-script","worker-fetch"}){
      JSONObject result=pendingResult(pendingWithout(missing));String category=missing.equals("document")?"request-document-missing":missing.equals("worker-script")?"request-worker-script-missing":"request-worker-fetch-missing";
      check("Pending source diagnostics separate exactly one missing phase: "+missing,"uncovered".equals(result.optString("status"))&&result.optBoolean("sourcePresenceKnown")&&category.equals(result.optString("errorCategory"))&&result.getJSONArray("missingSources").length()==1&&missing.equals(result.getJSONArray("missingSources").optString(0))&&result.getJSONArray("reportedSources").length()==2);
    }
    JSONObject docOnly=pendingWithout("worker-script");JSONArray records=docOnly.getJSONArray("events"),kept=new JSONArray();for(int i=0;i<records.length();i++){JSONObject event=records.getJSONObject(i);if(!"worker-fetch".equals(event.optString("source")))kept.put(event);}
    JSONObject result=pendingResult(docOnly.put("events",kept));check("Document-only pending data retains both missing Worker stages",result.getJSONArray("missingSources").length()==2&&"worker-script".equals(result.getJSONArray("missingSources").optString(0))&&"worker-fetch".equals(result.getJSONArray("missingSources").optString(1))&&result.getJSONArray("reportedSources").length()==1);
    result=pendingResult(pendingWithout("not-present"));check("Pending service never becomes ready merely because all typed source records exist","uncovered".equals(result.optString("status"))&&"request-sources-pending".equals(result.optString("errorCategory"))&&result.getJSONArray("missingSources").length()==0);
    result=pendingResult(pendingWithout("not-present").put("events",new JSONArray()));check("Empty pending records show every required phase missing without claiming arrivals",result.optBoolean("sourcePresenceKnown")&&result.getJSONArray("reportedSources").length()==0&&result.getJSONArray("missingSources").length()==3);
    result=pendingResult(pendingWithout("not-present").put("status","rejected").put("reason","fixture-secret-not-for-display"));check("Rejected service status stays distinct and uncovered without echoing arbitrary reason",uncredited(result)&&"detector-service-rejected".equals(result.optString("errorCategory"))&&"rejected".equals(result.optString("serviceStatus"))&&!result.toString().contains("fixture-secret-not-for-display"));
    result=pendingResult(pendingWithout("not-present").put("status","unexpected-service-status"));check("Unknown service status is not mislabeled as a missing Worker",uncredited(result)&&"detector-service-status-unknown".equals(result.optString("errorCategory"))&&"unknown".equals(result.optString("serviceStatus")));
    result=pendingResult(pendingWithout("not-present").put("status",5));check("Non-string service status cannot become a known pending phase",uncredited(result)&&"unknown".equals(result.optString("serviceStatus")));
    for(String malformed:new String[]{"ua-type","worker-destination","sensitive-contradiction","index-type"}){
      JSONObject server=pendingWithout("worker-fetch"),event=server.getJSONArray("events").getJSONObject(2);
      if(malformed.equals("ua-type"))event.getJSONObject("headers").put("userAgent",5);else if(malformed.equals("worker-destination"))event.getJSONObject("headers").put("secFetchDest","empty");else if(malformed.equals("sensitive-contradiction"))event.getJSONObject("sensitiveHeaders").put("cookie",true);else event.put("index","3");
      result=pendingResult(server);check("Malformed pending evidence cannot certify any arrival: "+malformed,uncredited(result)&&"detector-source-records-unusable".equals(result.optString("errorCategory")));
    }
    JSONObject excessive=pendingWithout("not-present");JSONArray many=excessive.getJSONArray("events");while(many.length()<13)many.put(copy(many.getJSONObject(0)));result=pendingResult(excessive);check("Oversized pending event list is not partially counted as received",uncredited(result));
    JSONObject absent=pendingWithout("not-present");absent.remove("events");check("Missing pending event array is not treated as a reliable empty set",uncredited(pendingResult(absent)));
    JSONObject duplicate=pendingWithout("worker-fetch");JSONArray repeated=duplicate.getJSONArray("events");repeated.put(copy(repeated.getJSONObject(2)).put("index",4));check("Duplicate pending source ambiguity is not reported as a genuine extra arrival",uncredited(pendingResult(duplicate)));
  }
  public static void main(String[] args)throws Exception{
    String capabilities=B+"capabilities?nonce="+N,frameUrl=F+"frame?nonce="+N,doc=B+"document?nonce="+N+"&frame=1";
    check("Service URL builder stays canonical",capabilities.equals(RequestIdentityAudit.url(B,"capabilities",N)));
    check("Ordinary identity admission does not open service capability requests",!RequestIdentityAudit.requestAllowed(capabilities,B,N,true,true,true,10,20));
    check("Explicit fresh acknowledged service probe admits only its capabilities request",service(capabilities,true,true,true,10));
    for(int mask=0;mask<7;mask++)check("Any missing service ownership bit closes capability route: "+mask,!service(capabilities,(mask&1)!=0,(mask&2)!=0,(mask&4)!=0,10));
    check("Expired service deadline denies capability route",!service(capabilities,true,true,true,21));
    for(String target:new String[]{B+"result?nonce="+N,B+"document?nonce="+N,capabilities+"&extra=1",capabilities+"#x",B+"capabilities?nonce="+N+"&nonce="+N,B+"capabilities?nonce="+N.toUpperCase(),"https://other.example/pocketchat-identity/v1/capabilities?nonce="+N,"http://audit.example/pocketchat-identity/v1/capabilities?nonce="+N,B+"%63apabilities?nonce="+N})check("Service scope denies nonexact diagnostic URL: "+target,!service(target,true,true,true,10));
    check("Cross-frame URL flag is explicit",doc.equals(RequestIdentityAudit.documentUrl(B,N,true)));
    check("Old identity flow remains nonce-only",RequestIdentityAudit.documentUrl(B,N,false).equals(B+"document?nonce="+N));
    check("Old request admission denies explicit frame flag without new owner",!RequestIdentityAudit.requestAllowed(doc,B,N,true,true,true,10,20));
    check("Both acknowledged scopes admit opted-in primary document",frame(doc,true,true));
    check("Both acknowledged scopes admit only exact secondary frame",frame(frameUrl,true,true));
    check("No frame consent denies primary flag",!frame(doc,false,true));check("No secondary registration denies primary flag",!frame(doc,true,false));
    check("No frame consent denies secondary request",!frame(frameUrl,false,true));check("No secondary registration denies secondary request",!frame(frameUrl,true,false));
    for(String target:new String[]{frameUrl+"&parent=https://audit.example",frameUrl+"&source=worker",F+"observe?nonce="+N+"&source=worker",F+"worker.js?nonce="+N,F+"document?nonce="+N,frameUrl+"#fragment",B+"document?frame=1&nonce="+N,doc+"&frame=1"})check("Frame admission denies pollution or unrelated secondary paths: "+target,!frame(target,true,true));
    check("Same-origin endpoint cannot masquerade as cross-origin frame",!RequestIdentityAudit.controlledRequestAllowed(B+"frame?nonce="+N,B,N,true,true,true,10,20,true,B,true));
    check("Expired frame ownership denies new frame",!RequestIdentityAudit.controlledRequestAllowed(frameUrl,B,N,true,true,true,21,20,true,F,true));
    check("HTTP case and optional whitespace normalize full language order",state(language(" EN-us ; q=1.000 , JA-jp ;q=0.5 ","en-US","en-US","ja-JP"),"verified"));
    JSONObject weighted=language("en-US;q=0.2,ja-JP;q=1","ja-JP","ja-JP","en-US");check("HTTP q weights determine preference before comparison",state(weighted,"verified")&&weighted.getJSONObject("http").getJSONArray("effectiveLanguages").getString(0).equals("ja-jp"));
    check("Equal q weights preserve explicit wire preference",state(language("en-US;q=0.5,ja-JP;q=0.5","ja-JP","ja-JP","en-US"),"issue"));
    JSONObject zero=language("ja-JP,fr;q=0,en-US;q=0.5","ja-JP","ja-JP","en-US");check("q zero is excluded and retained as typed evidence",state(zero,"verified")&&zero.getJSONObject("http").getJSONArray("ranges").getJSONObject(1).getBoolean("excluded"));
    check("All q zero ranges cannot imply a JavaScript agreement",state(language("ja-JP;q=0","ja-JP","ja-JP"),"uncovered"));
    check("Positive wildcard is not silently equated with an explicit language list",state(language("ja-JP,*;q=0.2","ja-JP","ja-JP"),"uncovered"));
    check("A disabled wildcard does not invent accepted languages",state(language("ja-JP,*;q=0","ja-JP","ja-JP"),"verified"));
    for(String bad:new String[]{"ja_JP","ja-JP;q=1.1","ja-JP;q=.5","ja-JP;q=0.1234","ja-JP;q=-1","ja-JP;q=1;q=1","ja-JP,JA-jp","ja-JP,ja-JP;q=0","ja-JP,","ja-JP\r","ja-JP\n","ja-JP;foo=1"})check("Malformed or ambiguous full language header never passes: "+bad,state(language(bad,"ja-JP","ja-JP"),"uncovered"));
    check("Missing header remains uncovered",state(language("","ja-JP","ja-JP"),"uncovered"));
    check("Duplicate JavaScript languages do not yield a comparison pass",state(language("ja-JP","ja-JP","ja-JP","JA-jp"),"uncovered"));
    check("Primary JavaScript language must agree with its own ordered list",state(language("ja-JP,en-US;q=0.5","en-US","ja-JP","en-US"),"issue"));
    check("No primary language does not manufacture language consistency",state(language("ja-JP","","ja-JP"),"uncovered"));
    check("Secondary language differences remain observable",state(language("ja-JP,en-US;q=0.5","ja-JP","ja-JP","fr"),"issue"));
    check("A language divergence remains an observation, not a leak verdict",Boolean.FALSE.equals(language("ja-JP","en-US","en-US").opt("leakVerdict")));
    check("Equivalent HTTP formatting and default q normalize",state(RequestIdentityLanguages.compareHeaders("ja-JP,en-US;q=0.5","JA-jp;q=1.000,EN-us;q=0.500"),"verified"));
    check("HTTP weight differences are observed even if order stays the same",state(RequestIdentityLanguages.compareHeaders("ja-JP,en-US;q=0.5","ja-JP,en-US;q=0.4"),"issue"));
    check("Reordered wire ranges with unambiguous weights compare semantically",state(RequestIdentityLanguages.compareHeaders("en-US;q=0.2,ja-JP","ja-JP,en-US;q=0.2"),"verified"));
    check("HTTP wildcard agreement does not become a complete language verdict",state(RequestIdentityLanguages.compareHeaders("*","*"),"uncovered"));
    JSONObject complete=evaluate(RequestIdentityAuditHost.browser(),expected());check("Complete JavaScript list is compared against document HTTP",row(complete,"request-document-language-list","verified"));
    check("Complete native list is compared against both HTTP sources",row(complete,"request-native-document-language-list","verified")&&row(complete,"request-native-worker-language-list","verified"));
    JSONObject incomplete=evaluate(RequestIdentityAuditHost.browser(),RequestIdentityAuditHost.expected());check("A missing native language list is not synthesized from its first item",row(incomplete,"request-native-document-language-list","uncovered"));
    JSONObject changed=RequestIdentityAuditHost.browser();changed.getJSONObject("worker").put("languages",J.arr("ja-JP","fr"));JSONObject mismatch=evaluate(changed,expected());
    check("Matching first language cannot hide a full Worker list difference",row(mismatch,"request-worker-language","verified")&&row(mismatch,"request-worker-language-list","issue"));
    check("Raw HTTP list remains separate from normalized semantics",complete.getJSONObject("server").getJSONArray("events").getJSONObject(0).getJSONObject("headers").getString("acceptLanguage").equals("ja-JP,en-US;q=0.5"));
    check("An unsolicited frame sample does not invent a requested frame verdict",!evaluate(frameBrowser(),expected()).getJSONObject("browser").has("crossOriginFrame"));
    JSONObject frame=evaluate(frameBrowser(),frameExpected());check("Controlled cross-origin Canvas operation is independently available",row(frame,"request-cross-origin-frame-canvas","available"));
    check("Restricted WebGL capability plus actual readback remains independently restricted",row(frame,"request-cross-origin-frame-webgl","restricted"));
    check("Cross-origin result is retained outside the three HTTP source records",frame.getJSONObject("browser").has("crossOriginFrame")&&frame.getJSONObject("server").getJSONArray("events").length()==4);
    check("Frame result never attests whole fingerprint protection",Boolean.FALSE.equals(frame.getJSONObject("browser").getJSONObject("crossOriginFrame").opt("protectionVerified"))&&!frame.optBoolean("fingerprintTemplateAcceptance",true));
    changed=frameBrowser();changed.getJSONObject("crossOriginFrame").getJSONObject("apiChecks").getJSONObject("probes").getJSONObject("canvas").put("hash","b"+H.substring(1));
    check("Different cross-context hash is not automatically judged abnormal",row(evaluate(changed,frameExpected()),"request-cross-origin-frame-canvas","available"));
    for(String field:new String[]{"nonce","origin","source"}){changed=frameBrowser();changed.getJSONObject("crossOriginFrame").put(field,"wrong");JSONObject result=evaluate(changed,frameExpected());check("Frame correlation mismatch stays uncovered: "+field,row(result,"request-cross-origin-frame","uncovered")&&row(result,"request-document-ua","verified"));}
    changed=frameBrowser();changed.remove("crossOriginFrame");check("Missing optional frame stays uncovered without erasing HTTP identity evidence",row(evaluate(changed,frameExpected()),"request-cross-origin-frame","uncovered"));
    changed=frameBrowser();changed.getJSONObject("crossOriginFrame").put("status","uncovered").put("reason","frame-timeout-or-csp");check("CSP or frame timeout reason remains visible",RequestIdentityAuditHost.row(evaluate(changed,frameExpected()),"request-cross-origin-frame").optString("detail").contains("frame-timeout-or-csp"));
    for(String field:new String[]{"schema","probeVersion","requested","protectionVerified"}){changed=frameBrowser();changed.getJSONObject("crossOriginFrame").getJSONObject("apiChecks").put(field,"wrong");check("Wrong typed frame probe contract stays uncovered: "+field,row(evaluate(changed,frameExpected()),"request-cross-origin-frame","uncovered"));}
    changed=frameBrowser();changed.getJSONObject("crossOriginFrame").getJSONObject("apiChecks").getJSONObject("limits").put("canvasPixels",8192);check("Expanded frame operation budget is not accepted as the bounded probe",row(evaluate(changed,frameExpected()),"request-cross-origin-frame","uncovered"));
    changed=frameBrowser();changed.getJSONObject("crossOriginFrame").getJSONObject("apiChecks").getJSONObject("probes").getJSONObject("canvas").put("pixels",8192);JSONObject partial=evaluate(changed,frameExpected());check("Malformed Canvas does not pass while valid WebGL remains separately available",row(partial,"request-cross-origin-frame-canvas","uncovered")&&row(partial,"request-cross-origin-frame-webgl","restricted"));
    changed=frameBrowser();changed.getJSONObject("crossOriginFrame").getJSONObject("apiChecks").getJSONObject("probes").getJSONObject("webgl").put("readbackBytes",2048);check("WebGL readback size contract is checked",row(evaluate(changed,frameExpected()),"request-cross-origin-frame-webgl","uncovered"));
    changed=frameBrowser();JSONObject canvas=changed.getJSONObject("crossOriginFrame").getJSONObject("apiChecks").getJSONObject("probes").getJSONObject("canvas");canvas.remove("hash");canvas.remove("hashAlgorithm");canvas.put("hashUnavailable",true);check("Missing digest API does not erase an actual bounded Canvas operation",row(evaluate(changed,frameExpected()),"request-cross-origin-frame-canvas","available"));
    changed=frameExpected();changed.put("frameEndpoint",B);check("Same-origin frame cannot be reported as controlled cross-origin evidence",row(evaluate(frameBrowser(),changed),"request-cross-origin-frame","uncovered"));
    pendingSourceControls();
    JSONObject report=J.obj("status",passed==checks.length()?"passed":"failed","passed",passed,"total",checks.length(),"checks",checks,"actualAndroidExecution",false,"actualGeckoExecution",false,"actualHttpExecution",false,"fullFingerprintAcceptance",false,"scope","Actual Java admission and language/frame parsing with controlled JSON; no device, browser, network or protection-effectiveness attestation");System.out.println(report);if(passed!=checks.length())System.exit(1);
  }
}
