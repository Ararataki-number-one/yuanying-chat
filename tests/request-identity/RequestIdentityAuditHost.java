package local.pocketchat;

import org.json.*;

/** Real production parser/comparator, controlled JSON inputs, no browser or HTTP. */
public final class RequestIdentityAuditHost {
  static final String NONCE="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",BASE="https://audit.example/pocketchat-identity/v1/",UA="Mozilla/5.0 Firefox/157.0";
  static final JSONArray checks=new JSONArray();static int passed;
  interface Change {void apply(JSONObject value)throws Exception;}
  static void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));if(pass)passed++;}
  static JSONObject copy(JSONObject value){return J.parse(value.toString());}
  static JSONObject signal(){return J.obj("ua",UA,"language","ja-JP","languages",J.arr("ja-JP","en-US"));}
  static JSONObject browser(){return J.obj("schema",1,"nonce",NONCE,"status","complete","source","controlled-top-level-document","document",signal(),"worker",signal());}
  static JSONObject expected(){return J.obj("ua",UA,"language","ja-JP","environmentId","controlled-environment","configurationRevision",9);}
  static JSONObject event(int index,String source,String destination){
    String kind="document".equals(source)?"document":"worker-script".equals(source)?"worker.js":"worker-fetch".equals(source)?"observe":"result";
    return J.obj("index",index,"source",source,"at",1700000000000L+index,"method","GET","path",RequestIdentityAudit.PATH+kind,
      "headers",J.obj("userAgent",UA,"acceptLanguage","ja-JP,en-US;q=0.5","secFetchDest",destination,"secFetchSite","same-origin"),
      "peer",J.obj("address","203.0.113.9","source","socket-peer"),
      "sensitiveHeaders",J.obj("cookie",false,"authorization",false,"proxyAuthorization",false,"referer",false,"origin",false));
  }
  static JSONObject server(){return J.obj("schema",1,"protocol",RequestIdentityAudit.PROTOCOL,"nonce",NONCE,"status","ready","createdAt",1700000000000L,"expiresAt",1700000030000L,"credentialObserved",false,
    "events",J.arr(event(1,"document","document"),event(2,"control-result",""),event(3,"worker-script","worker"),event(4,"worker-fetch","empty")),
    "source","independent-https-server-records","peerMeaning","Direct TLS socket peer only; forwarded headers are not trusted");}
  static JSONObject evaluate(JSONObject b,JSONObject s,JSONObject e,boolean fresh){return RequestIdentityAudit.evaluate(b,s,e,NONCE,BASE,fresh);}
  static JSONObject row(JSONObject result,String key){JSONArray rows=result.optJSONArray("rows");if(rows!=null)for(int i=0;i<rows.length();i++){JSONObject value=rows.optJSONObject(i);if(value!=null&&key.equals(value.optString("key")))return value;}return new JSONObject();}
  static boolean state(JSONObject result,String key,String value){return value.equals(row(result,key).optString("state"));}
  static JSONObject headers(JSONObject value,int index)throws Exception{return value.getJSONArray("events").getJSONObject(index).getJSONObject("headers");}
  static void invalidServer(String name,Change change)throws Exception{JSONObject value=server();change.apply(value);check(name,"uncovered".equals(evaluate(browser(),value,expected(),true).optString("status")));}
  static void invalidBrowser(String name,Change change)throws Exception{JSONObject value=browser();change.apply(value);check(name,"uncovered".equals(evaluate(value,server(),expected(),true).optString("status")));}
  static String repeat(char value,int length){StringBuilder text=new StringBuilder();for(int i=0;i<length;i++)text.append(value);return text.toString();}
  static boolean allowed(String target){return RequestIdentityAudit.requestAllowed(target,BASE,NONCE,true,true,true,10,20);}
  static void coldStartAdmissionControls(){
    for(String target:new String[]{BASE+"document?nonce="+NONCE,BASE+"worker.js?nonce="+NONCE,BASE+"observe?nonce="+NONCE+"&source=worker",BASE+"result?nonce="+NONCE,BASE+"unexpected",BASE.substring(0,BASE.length()-1),
      "http://audit.example/pocketchat-identity/v1/document","https://audit.example/pocketchat-identity///v1//document","https://audit.example/pocketchat-identity/x/../v1/document","https://audit.example/route/../pocketchat-identity/v1/document",
      "https://audit.example/%70ocketchat-identity/v1/document","https://audit.example/%2fpocketchat-identity%2fv1%2fdocument","https://audit.example/%2570ocketchat-identity/v1/document","https://audit.example/%252570ocketchat-identity/v1/document","https://audit.example/%25252570ocketchat-identity/v1/document",
      "https://audit.example/%50OCKETCHAT-IDENTITY/V1/document","https://audit.example/pocketchat-identity/x/%2e%2e/v1/document","https://audit.example/another/%2e%2e//pocketchat-identity/v1/document"})check("Stored detector namespace is conservatively recognized: "+target,RequestIdentityAudit.diagnosticUrl(target));
    for(String target:new String[]{"https://chatgpt.com/c/ordinary","https://chatgpt.com/backend-api/conversation?return=%2Fpocketchat-identity%2Fv1%2Fdocument","https://chatgpt.com/c/ordinary?next=https://audit.example/pocketchat-identity/v1/document","https://chatgpt.com/c/ordinary#pocketchat-identity/v1/","https://pocketchat-identity.example/chat","https://audit.example/pocketchat-identity/v10/document","https://audit.example/safe/pocketchat-identity/v1/document","https://audit.example/pocketchat-identity-not/v1/document"})check("Ordinary URL or query-only namespace does not become a detector: "+target,!RequestIdentityAudit.diagnosticUrl(target));
    check("Null namespace target is not a diagnostic URL",!RequestIdentityAudit.diagnosticUrl(null));
    for(String target:new String[]{BASE+"document?nonce="+NONCE,BASE+"worker.js?nonce="+NONCE,BASE+"observe?nonce="+NONCE+"&source=worker",BASE+"result?nonce="+NONCE})check("Active acknowledged fresh exact detector request is allowed: "+target,allowed(target));
    String document=BASE+"document?nonce="+NONCE;
    check("HTTPS default port canonicalization retains the same origin",allowed(document.replace("audit.example/","audit.example:443/")));
    check("Scheme and host case do not invent a different origin",allowed(document.replace("https://audit.example/","HTTPS://AUDIT.EXAMPLE/")));
    check("Explicit nondefault port is allowed only when both endpoint and request match",RequestIdentityAudit.requestAllowed(document.replace("audit.example/","audit.example:9443/"),BASE.replace("audit.example/","audit.example:9443/"),NONCE,true,true,true,10,20));
    check("Deadline equality remains within the existing budget",RequestIdentityAudit.requestAllowed(document,BASE,NONCE,true,true,true,20,20));
    check("Requests beyond the unchanged deadline are denied",!RequestIdentityAudit.requestAllowed(document,BASE,NONCE,true,true,true,21,20));
    check("Inactive, cold-restored or cancelled URL cannot reuse its old authority",!RequestIdentityAudit.requestAllowed(document,BASE,NONCE,false,true,true,10,20));
    check("A missing registration acknowledgement denies the request",!RequestIdentityAudit.requestAllowed(document,BASE,NONCE,true,false,true,10,20));
    check("Changed configuration, document or route freshness denies the request",!RequestIdentityAudit.requestAllowed(document,BASE,NONCE,true,true,false,10,20));
    check("Empty endpoint never authorizes a stored detector URL",!RequestIdentityAudit.requestAllowed(document,"",NONCE,true,true,true,10,20));
    check("A null nonce never authorizes a stored detector URL",!RequestIdentityAudit.requestAllowed(document,BASE,null,true,true,true,10,20));
    check("Malformed current nonce never authorizes its matching-looking URL",!RequestIdentityAudit.requestAllowed(BASE+"document?nonce=invalid",BASE,"invalid",true,true,true,10,20));
    String control=BASE+"result?nonce="+NONCE;
    check("Cold restoration cannot authorize the result control request",!RequestIdentityAudit.requestAllowed(control,BASE,NONCE,false,true,true,10,20));
    check("A missing scope acknowledgement cannot authorize result control",!RequestIdentityAudit.requestAllowed(control,BASE,NONCE,true,false,true,10,20));
    check("Stale configuration or route cannot authorize result control",!RequestIdentityAudit.requestAllowed(control,BASE,NONCE,true,true,false,10,20));
    check("Expired authority cannot authorize result control",!RequestIdentityAudit.requestAllowed(control,BASE,NONCE,true,true,true,21,20));
    for(String target:new String[]{BASE+"document?nonce="+repeat('b',32),document.replace("audit.example/","other.example/"),document.replace("audit.example/","audit.example:9443/"),document.replace("https://","https://name:password@"),document.replace("https://","http://"),
      BASE+"result?nonce="+repeat('b',32),BASE+"unknown?nonce="+NONCE,document+"&redirect=https://other.example/",document+"&nonce="+NONCE,document+"#fragment",BASE+"observe?source=worker&nonce="+NONCE,BASE+"observe?nonce="+NONCE,BASE+"observe?nonce="+NONCE+"&source=document",
      BASE+"document?nonce=%61"+NONCE.substring(1),BASE+"document/?nonce="+NONCE,BASE.replace("/pocketchat", "/%70ocketchat")+"document?nonce="+NONCE,BASE.replace("/v1/","//v1/")+"document?nonce="+NONCE,BASE.replace("/v1/","/x/../v1/")+"document?nonce="+NONCE,
      "https://chatgpt.com/c/ordinary","not a URI"})check("Unacknowledged equivalent, redirect, old nonce or foreign request remains denied: "+target,!allowed(target));
    check("Null request URL is denied without a crash",!allowed(null));
  }
  public static void main(String[] args)throws Exception{
    check("Canonical endpoint preserves HTTPS host and fixed protocol path",BASE.equals(RequestIdentityAudit.endpoint(" HTTPS://AUDIT.EXAMPLE:443/pocketchat-identity/v1 ")));
    check("Explicit TLS port remains in the endpoint",RequestIdentityAudit.endpoint("https://audit.example:9443/pocketchat-identity/v1/").contains(":9443/"));
    for(String value:new String[]{"http://audit.example/pocketchat-identity/v1/","https://name:password@audit.example/pocketchat-identity/v1/","https://audit.example/pocketchat-identity/v1/?nonce=unexpected","https://audit.example/pocketchat-identity/v1/#fragment","https://audit.example/other/","https://audit.example:0/pocketchat-identity/v1/","https://audit.example:65536/pocketchat-identity/v1/","https://audit.example/%70ocketchat-identity/v1/"})check("Unsafe endpoint rejected: "+value,RequestIdentityAudit.endpoint(value).isEmpty());
    check("Empty endpoint can explicitly disable the detector",RequestIdentityAudit.endpointIssue("").isEmpty());
    check("Document URL carries only its fresh opaque nonce",RequestIdentityAudit.url(BASE,"document",NONCE).equals(BASE+"document?nonce="+NONCE));
    boolean invalid=false;try{RequestIdentityAudit.url(BASE,"observe",NONCE);}catch(IllegalArgumentException expected){invalid=true;}check("Native URL builder cannot invent a Worker-source request",invalid);
    invalid=false;try{RequestIdentityAudit.url(BASE,"document","invalid");}catch(IllegalArgumentException expected){invalid=true;}check("Native URL builder rejects malformed nonce",invalid);

    JSONObject good=evaluate(browser(),server(),expected(),true);
    check("Reference server shape yields observation, not full acceptance","observed".equals(good.optString("status")));
    for(String key:new String[]{"request-document-ua","request-document-language","request-worker-ua","request-worker-language","request-context-headers","request-native-ua","request-peer"})check("Matching independently typed evidence: "+key,state(good,key,"verified"));
    check("Full desktop UA consistency remains explicitly unaccepted",good.opt("fullDesktopUaConsistency") instanceof Boolean&&!good.optBoolean("fullDesktopUaConsistency"));
    check("Full fingerprint template remains explicitly unaccepted",good.opt("fingerprintTemplateAcceptance") instanceof Boolean&&!good.optBoolean("fingerprintTemplateAcceptance"));
    check("Template/environment revision is local comparison context",good.getJSONObject("expected").optLong("configurationRevision")==9&&"controlled-environment".equals(good.getJSONObject("expected").optString("environmentId")));
    check("Scope does not substitute the ChatGPT site",good.optString("scope").contains("不能代表 ChatGPT"));
    check("Worker script download UA is compared separately against document HTTP",state(good,"request-worker-script-ua","verified"));
    check("Worker script download language has its own HTTP comparison",state(good,"request-worker-script-language","verified"));
    check("Worker execution request label explicitly identifies fetch",row(good,"request-worker-ua").optString("name").contains("fetch"));

    JSONObject changed=server();headers(changed,3).put("userAgent","IndependentWorker/157");JSONObject result=evaluate(browser(),changed,expected(),true);
    check("Actual Worker HTTP UA mismatch remains visible",state(result,"request-worker-ua","issue"));
    check("Document versus Worker HTTP difference remains separate",state(result,"request-context-headers","issue"));
    check("Native UA request is compared against both real HTTP sources",state(result,"request-native-ua","issue"));
    check("Matching script download UA cannot conceal a different Worker fetch UA",state(result,"request-worker-script-ua","verified")&&"issue".equals(result.optString("status"))&&!result.optBoolean("fullDesktopUaConsistency"));
    check("Script and fetch raw HTTP values remain independently preserved",UA.equals(headers(result.getJSONObject("server"),2).optString("userAgent"))&&"IndependentWorker/157".equals(headers(result.getJSONObject("server"),3).optString("userAgent")));
    JSONObject scriptChanged=server();headers(scriptChanged,2).put("userAgent","IndependentScript/157");JSONObject scriptResult=evaluate(browser(),scriptChanged,expected(),true);
    check("A different script download UA remains an independent issue",state(scriptResult,"request-worker-script-ua","issue")&&"issue".equals(scriptResult.optString("status")));
    check("A script issue does not rewrite the document or Worker fetch comparison",state(scriptResult,"request-document-ua","verified")&&state(scriptResult,"request-worker-ua","verified")&&state(scriptResult,"request-context-headers","verified"));
    scriptChanged=server();headers(scriptChanged,2).put("acceptLanguage","");scriptResult=evaluate(browser(),scriptChanged,expected(),true);
    check("Missing script language stays uncovered instead of borrowing another request",state(scriptResult,"request-worker-script-language","uncovered")&&state(scriptResult,"request-document-language","verified")&&state(scriptResult,"request-worker-language","verified"));
    scriptChanged=server();headers(scriptChanged,2).put("acceptLanguage","en-US,ja-JP;q=0.5");
    check("Script HTTP language differences remain separately visible",state(evaluate(browser(),scriptChanged,expected(),true),"request-worker-script-language","issue"));
    JSONObject workerJsChanged=browser();workerJsChanged.getJSONObject("worker").put("ua","WorkerJS/157");
    check("Script download has no invented Worker JavaScript context",state(evaluate(workerJsChanged,server(),expected(),true),"request-worker-script-ua","verified"));
    changed=browser();changed.getJSONObject("worker").put("ua","WorkerJS/157");check("JS Worker equality cannot replace real request headers",state(evaluate(changed,server(),expected(),true),"request-worker-ua","issue"));
    changed=server();headers(changed,3).put("acceptLanguage","en-US,ja;q=0.5");check("Worker request language mismatch is preserved",state(evaluate(browser(),changed,expected(),true),"request-worker-language","issue"));
    changed=server();headers(changed,0).put("acceptLanguage","");check("Absent effective request language stays uncovered",state(evaluate(browser(),changed,expected(),true),"request-document-language","uncovered"));
    changed=server();headers(changed,0).put("acceptLanguage","JA-jp");check("Language comparison accepts case-equivalent first language",state(evaluate(browser(),changed,expected(),true),"request-document-language","verified"));
    changed=server();changed.getJSONArray("events").getJSONObject(3).getJSONObject("peer").put("address","203.0.113.10");check("Different server socket peers are reported without leak attestation",state(evaluate(browser(),changed,expected(),true),"request-peer","issue"));
    check("No native UA request does not create a native-match verdict",state(evaluate(browser(),server(),new JSONObject(),true),"request-native-ua","uncovered"));
    check("A changed page/policy/route invalidates otherwise complete evidence","uncovered".equals(evaluate(browser(),server(),expected(),false).optString("status")));
    check("Null server input cannot produce verified results","uncovered".equals(evaluate(browser(),null,expected(),true).optString("status")));

    invalidServer("Missing credential observation cannot imply no credentials",value->value.remove("credentialObserved"));
    for(Object value:new Object[]{JSONObject.NULL,"false",0,new JSONObject()})invalidServer("Nonboolean credential marker rejected: "+String.valueOf(value),input->input.put("credentialObserved",value));
    changed=server();changed.put("credentialObserved",true);result=evaluate(browser(),changed,expected(),true);
    check("Explicit credential observation prevents a consistency pass","issue".equals(result.optString("status"))&&result.optBoolean("credentialObserved"));
    check("Credential issue does not retain raw server records",!result.has("server")&&!result.has("browser"));
    changed=server();changed.getJSONArray("events").getJSONObject(0).getJSONObject("sensitiveHeaders").put("cookie",true);result=evaluate(browser(),changed,expected(),true);
    check("An event contradicting the clean credential marker is not accepted",!"observed".equals(result.optString("status")));

    invalidServer("Wrong response nonce is stale evidence",value->value.put("nonce",repeat('b',32)));
    invalidServer("Wrong server protocol is not silently upgraded",value->value.put("protocol","different-protocol"));
    invalidServer("String server schema is not a typed version",value->value.put("schema","1"));
    invalidServer("Fractional server schema cannot be truncated to version1",value->value.put("schema",1.5));
    invalidServer("Pending response cannot be treated as ready",value->value.put("status","pending"));
    invalidServer("Partial event set remains uncovered",value->value.put("events",J.arr(event(1,"document","document"),event(2,"worker-fetch","empty"))));
    invalidServer("Missing event array remains uncovered",value->value.remove("events"));
    invalidServer("Too many event records fail bounded parsing",value->{JSONArray events=new JSONArray();for(int i=0;i<13;i++)events.put(event(i+1,"document","document"));value.put("events",events);});
    invalidServer("String event index cannot masquerade as integer",value->value.getJSONArray("events").getJSONObject(0).put("index","1"));
    invalidServer("Fractional event index is not truncated",value->value.getJSONArray("events").getJSONObject(0).put("index",1.5));
    invalidServer("Unknown source cannot replace Dedicated Worker evidence",value->value.getJSONArray("events").getJSONObject(3).put("source","content-script"));
    invalidServer("Duplicate source cannot replace missing request path",value->{JSONObject event=value.getJSONArray("events").getJSONObject(3);event.put("source","document");event.put("path",RequestIdentityAudit.PATH+"document");});
    invalidServer("A differently routed path is not equivalent server evidence",value->value.getJSONArray("events").getJSONObject(3).put("path","/other"));
    invalidServer("NonGET arrival cannot satisfy the declared probe",value->value.getJSONArray("events").getJSONObject(3).put("method","POST"));
    invalidServer("An embedded document is not a top-level document request",value->headers(value,0).put("secFetchDest","iframe"));
    invalidServer("Worker script purpose must actually be worker",value->headers(value,2).put("secFetchDest","script"));
    invalidServer("A document navigation is not a Worker fetch",value->headers(value,3).put("secFetchDest","document"));
    invalidServer("Missing language header type is not an empty string",value->headers(value,0).remove("acceptLanguage"));
    invalidServer("Numeric language header is not coerced to text",value->headers(value,0).put("acceptLanguage",5));
    invalidServer("Numeric destination header is not coerced to text",value->headers(value,0).put("secFetchDest",5));
    invalidServer("Missing request UA cannot satisfy real header equality",value->headers(value,0).remove("userAgent"));
    invalidServer("Oversized request UA fails bounded parsing",value->headers(value,0).put("userAgent",repeat('x',2049)));

    invalidBrowser("Different browser nonce cannot borrow the server record",value->value.put("nonce",repeat('c',32)));
    invalidBrowser("String browser schema is not accepted",value->value.put("schema","1"));
    invalidBrowser("Content-script output cannot replace the controlled top-level page",value->value.put("source","content-script"));
    invalidBrowser("A failed browser sample stays uncovered",value->value.put("status","failed"));
    invalidBrowser("Missing Worker JS sample stays uncovered",value->value.remove("worker"));
    invalidBrowser("Numeric JavaScript UA cannot be coerced",value->value.getJSONObject("worker").put("ua",42));
    invalidBrowser("JavaScript languages must be a list",value->value.getJSONObject("worker").put("languages","ja-JP"));
    invalidBrowser("JavaScript language list cannot be empty",value->value.getJSONObject("worker").put("languages",new JSONArray()));
    invalidBrowser("JavaScript language members must be bounded strings",value->value.getJSONObject("worker").put("languages",J.arr(42)));

    JSONObject b=browser(),s=server(),e=expected();b.put("Cookie","fixture-secret-do-not-save");b.getJSONObject("document").put("password","fixture-secret-do-not-save");
    s.put("credentials","fixture-secret-do-not-save");headers(s,0).put("Cookie","fixture-secret-do-not-save");s.getJSONArray("events").getJSONObject(0).getJSONObject("peer").put("authorization","fixture-secret-do-not-save");e.put("password","fixture-secret-do-not-save");
    result=evaluate(b,s,e,true);check("Unknown sensitive input fields are never copied to persisted comparison",!result.toString().contains("fixture-secret-do-not-save"));
    check("Unknown input fields cannot enable full fingerprint acceptance",Boolean.FALSE.equals(result.opt("fullDesktopUaConsistency"))&&Boolean.FALSE.equals(result.opt("fingerprintTemplateAcceptance")));
    coldStartAdmissionControls();
    for(Object value:new Object[]{JSONObject.NULL,"false",true}){
      JSONObject origin=server();origin.getJSONArray("events").getJSONObject(0).getJSONObject("sensitiveHeaders").put("origin",value);
      check("Missing, malformed or positive Origin observation prevents a clean verdict: "+String.valueOf(value),!"observed".equals(evaluate(browser(),origin,expected(),true).optString("status")));
    }
    JSONObject report=J.obj("status",passed==checks.length()?"passed":"failed","passed",passed,"total",checks.length(),"checks",checks,
      "actualAndroidExecution",false,"actualGeckoExecution",false,"actualHttpExecution",false,"physicalPhoneAcceptance",false,"fullFingerprintAcceptance",false,
      "scope","Production J and RequestIdentityAudit parser/comparator on controlled JSON; no browser, network, Android, phone or privacy-effectiveness verdict");
    System.out.println(report.toString());if(passed!=checks.length())System.exit(1);
  }
}
