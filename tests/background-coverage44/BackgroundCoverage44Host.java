package local.pocketchat;

import org.json.*;
import java.util.*;

/** Actual models and summary, controlled JSON/session adapters only. */
public final class BackgroundCoverage44Host {
  static final JSONArray checks=new JSONArray();
  static void check(String name,boolean pass){checks.put(J.obj("name",name,"passed",pass));if(!pass)throw new AssertionError(name);}
  static boolean uncovered(JSONObject value)throws Exception{
    if(value==null||!"client-coverage-policy".equals(value.optString("source"))||!Boolean.FALSE.equals(value.opt("registeredOrClearedSiteWorkers")))return false;
    for(String key:Arrays.asList("sharedWorker","serviceWorker")){JSONObject row=value.optJSONObject(key);if(row==null||!"not-covered".equals(row.optString("state"))||!Boolean.FALSE.equals(row.opt("requestHeadersObserved"))||!Boolean.FALSE.equals(row.opt("cacheLifecycleObserved")))return false;}
    return true;
  }
  static JSONObject statement(Object shared,Object service){return J.obj("sharedWorker",shared,"serviceWorker",service);}
  static String state(JSONObject coverage,String key){return coverage.optJSONObject(key).optString("serviceStatement");}
  public static void main(String[] args)throws Exception{
    JSONObject missing=RequestIdentityAudit.backgroundCoverage(null);
    check("Absent legacy service declarations remain unknown and not covered",uncovered(missing)&&state(missing,"sharedWorker").equals("unknown")&&state(missing,"serviceWorker").equals("unknown"));
    for(boolean support:new boolean[]{false,true}){
      JSONObject value=RequestIdentityAudit.backgroundCoverage(statement(support,support));
      check("Service booleans never become observed client coverage: "+support,uncovered(value));
      check("Service support is only a typed declaration: "+support,state(value,"sharedWorker").equals(support?"declared-supported":"declared-unsupported")&&state(value,"serviceWorker").equals(support?"declared-supported":"declared-unsupported"));
      String summary=RequestIdentityAudit.backgroundCoverageSummary(value);
      check("Summary separates client not-covered from service self-report: "+support,summary.contains("Shared Worker：客户端尚未覆盖")&&summary.contains("Service Worker：客户端尚未覆盖")&&summary.contains(support?"服务自述支持，客户端未验证":"服务自述未支持")&&summary.contains("未注册或清理站点 Worker"));
    }
    Object[] unknown={JSONObject.NULL,"true","verified",1,0,new JSONArray(),J.obj("state","verified"),2.0};
    for(Object raw:unknown){JSONObject value=RequestIdentityAudit.backgroundCoverage(statement(raw,raw));check("Malformed optional service declaration cannot be interpreted as support: "+String.valueOf(raw),uncovered(value)&&state(value,"sharedWorker").equals("unknown")&&state(value,"serviceWorker").equals("unknown"));}
    JSONObject mixed=RequestIdentityAudit.backgroundCoverage(statement(true,false));
    check("The two service declarations stay independent",state(mixed,"sharedWorker").equals("declared-supported")&&state(mixed,"serviceWorker").equals("declared-unsupported"));
    JSONObject forged=RequestIdentityAudit.backgroundCoverage(J.obj("sharedWorker",true,"serviceWorker",true,"source","SECRET-SOURCE","state","verified","requestHeadersObserved",true,"registeredOrClearedSiteWorkers",true,"extra","SECRET"));
    check("Server extras cannot forge client observation or expose arbitrary fields",uncovered(forged)&&!forged.toString().contains("SECRET"));
    JSONObject hostileSummary=J.obj("source","server","sharedWorker",J.obj("state","verified","serviceStatement","SECRET-VERIFIED"),"serviceWorker",J.obj("state","observed","serviceStatement",true));
    String text=RequestIdentityAudit.backgroundCoverageSummary(hostileSummary);
    check("A malformed or historical summary never adopts its stored client state",text.contains("Shared Worker：客户端尚未覆盖")&&text.contains("Service Worker：客户端尚未覆盖")&&text.contains("服务支持情况未知")&&!text.contains("SECRET")&&!text.contains("已验证"));
    check("Missing historical coverage has an explicit safe summary",RequestIdentityAudit.backgroundCoverageSummary(null).contains("服务支持情况未知"));
    String nonce=RequestIdentityAuditHost.NONCE,base=RequestIdentityAuditHost.BASE;
    JSONObject old=RequestIdentityServiceProbeHost.control(nonce,false),legacy=RequestIdentityServiceProbe.evaluate(old,nonce,base);
    check("The legacy service protocol stays ready without optional declarations",legacy.optString("status").equals("ready")&&uncovered(legacy.optJSONObject("backgroundCoverage")));
    check("Legacy service support remains unknown rather than unsupported",state(legacy.optJSONObject("backgroundCoverage"),"sharedWorker").equals("unknown"));
    for(boolean support:new boolean[]{false,true}){
      JSONObject control=RequestIdentityServiceProbeHost.control(nonce,false);control.getJSONObject("service").put("backgroundCoverage",statement(support,support));JSONObject parsed=RequestIdentityServiceProbe.evaluate(control,nonce,base);
      check("Preflight cannot certify unimplemented worker paths from a service claim: "+support,parsed.optString("status").equals("ready")&&uncovered(parsed.optJSONObject("backgroundCoverage")));
      EnvironmentAudit audit=RequestIdentityServiceProbeHost.audit();audit.serviceProbe.result=parsed;String ui=audit.serviceProbe.summary(true);
      check("Actual service summary clearly displays unimplemented client coverage: "+support,ui.contains("Shared Worker：客户端尚未覆盖")&&ui.contains("Service Worker：客户端尚未覆盖")&&ui.contains(support?"服务自述支持，客户端未验证":"服务自述未支持"));
    }
    JSONObject server=RequestIdentityAuditHost.server(),browser=RequestIdentityAuditHost.browser();server.put("backgroundCoverage",statement(true,true));browser.put("backgroundCoverage",J.obj("sharedWorker",J.obj("state","verified"),"serviceWorker",J.obj("state","verified")));
    JSONObject report=RequestIdentityAudit.evaluate(browser,server,RequestIdentityAuditHost.expected(),nonce,base,true);
    check("A complete Dedicated Worker result does not imply other worker coverage",uncovered(report.optJSONObject("backgroundCoverage")));
    check("Shared Worker has a separate uncovered row",RequestIdentityAuditHost.state(report,"request-shared-worker","uncovered"));
    check("Service Worker has a separate uncovered row",RequestIdentityAuditHost.state(report,"request-service-worker","uncovered"));
    check("The old document and Dedicated Worker evidence remains evaluated",RequestIdentityAuditHost.state(report,"request-document-ua","verified")&&RequestIdentityAuditHost.state(report,"request-worker-ua","verified"));
    check("Server self-reported worker support is not imported as formal observation",state(report.optJSONObject("backgroundCoverage"),"sharedWorker").equals("unknown")&&state(report.optJSONObject("backgroundCoverage"),"serviceWorker").equals("unknown"));
    for(String operation:Arrays.asList("shared-worker.js","service-worker.js","sw.js","shared.js","register","unregister","cache"))check("No native request admission added for "+operation,!RequestIdentityAudit.requestAllowed(base+operation+"?nonce="+nonce,base,nonce,true,true,true,10,20));
    System.out.println(J.obj("status","passed","passed",checks.length(),"total",checks.length(),"checks",checks,"actualAndroidExecution",false,"actualGeckoExecution",false,"actualHttpExecution",false,"scope","Actual request/preflight coverage models and service summary on controlled JSON plus existing Android/session doubles; no Worker APIs executed."));
  }
}
