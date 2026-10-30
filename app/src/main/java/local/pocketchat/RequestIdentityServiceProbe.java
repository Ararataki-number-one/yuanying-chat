package local.pocketchat;

import android.os.SystemClock;
import org.json.*;
import java.net.URI;
import java.util.*;

/** One user-requested, anonymous capability fetch. It never navigates or inspects a draft. */
final class RequestIdentityServiceProbe {
  static final long DEADLINE_MS=10000,RESULT_TTL_MS=60000;
  final EnvironmentAudit audit;final ChatSession session;
  boolean active,scopeRequested,scopeRegistered;
  long id,deadline,connectionEpoch,navigationEpoch,fileGeneration,configurationRevision;
  String endpoint="",nonce="",route="",policy="",sourceUrl="",phase="idle";
  Runnable watchdog;
  JSONObject result=new JSONObject();
  RequestIdentityServiceProbe(EnvironmentAudit value){audit=value;session=value.session;}
  boolean refused(String detail){audit.lastError=detail;return false;}
  boolean start(Runnable completed){
    if(audit.running)return false;audit.lastError="";
    endpoint=RequestIdentityAudit.endpoint(audit.requestIdentity.configuredEndpoint());
    if(endpoint.isEmpty())return refused("请先配置你信任的 HTTPS 检测服务；尚未发出请求");
    if(session.deleted||!GeckoWebView.active(session.web)||!session.web.hasVisibleDocument()||session.navigating||!MainActivity.chatUrl(session.web.getUrl()))return refused("请等当前聊天网页显示后再检查服务；页面不会离开");
    if(ProfileUi.working(session)||session.currentReplyActive()||session.resourceFilesUncertain())return refused("请先完成回复或文件任务，再检查检测服务");
    if(!session.networkReady||!session.guard.allowed()||!session.privacy.canNavigate()||!session.web.protectionAllowsNetwork())return refused("当前连接或浏览器保护尚未确认，没有发出服务检查请求");
    sourceUrl=session.web.getUrl();if(sourceUrl.length()>8192)return refused("当前页面地址过长，尚未开始服务检查");
    connectionEpoch=session.connectionEpoch;navigationEpoch=session.navigationEpoch;fileGeneration=session.fileWorkGeneration;configurationRevision=session.identityAuditAppliedRevision();
    route=audit.routeStamp();policy=audit.policyStamp();nonce=UUID.randomUUID().toString().replace("-","");
    active=scopeRequested=true;scopeRegistered=false;phase="registering";deadline=SystemClock.elapsedRealtime()+DEADLINE_MS;
    audit.running=audit.networkRun=true;audit.geckoRun=false;audit.completed=completed;id=++audit.serial;session.updateBrowserActivity();
    long request=id;String requestNonce=nonce,requestEndpoint=endpoint;
    watchdog=()->{if(current(request))abort("service-deadline","服务检查已超时，没有离开当前聊天");};session.handler.postDelayed(watchdog,DEADLINE_MS+50);
    session.web.requestIdentityScope(J.obj("action","register","purpose","capabilities","endpoint",endpoint,"nonce",nonce),raw->{
      JSONObject accepted=bounded(raw,4096);boolean acceptedScope=Boolean.TRUE.equals(accepted.opt("ok"))&&requestNonce.equals(accepted.optString("nonce"));boolean registered=acceptedScope&&"capabilities".equals(accepted.optString("purpose"));
      if(!current(request)){if(acceptedScope)closeScope(requestEndpoint,requestNonce);return;}
      scopeRegistered=registered;
      if(!fresh()){abort("environment-changed","检查准备期间网页、配置或连接已变化，服务检查已取消");return;}
      if(!registered||!Boolean.TRUE.equals(accepted.opt("credentialFilter"))||!Boolean.TRUE.equals(accepted.opt("redirectsBlocked"))){
        finish(error("scope-unconfirmed","服务请求的凭据过滤或禁止重定向尚未确认，没有开始连接检查",0));return;
      }
      phase="fetching";
      session.web.requestIdentityScope(J.obj("action","capabilities","endpoint",endpoint,"nonce",nonce),reply->{
        if(!current(request))return;
        if(!fresh()){abort("environment-changed","服务回执到达时网页、配置或连接已变化，结果没有采信");return;}
        finish(evaluate(bounded(reply,24000),requestNonce,requestEndpoint));
      });
    });return true;
  }
  static JSONObject bounded(String raw,int max){return raw!=null&&raw.length()<=max?J.parse(raw):new JSONObject();}
  boolean current(long request){return active&&id==request&&audit.current(request);}
  boolean fresh(){return active&&!session.deleted&&endpoint.equals(RequestIdentityAudit.endpoint(audit.requestIdentity.configuredEndpoint()))&&connectionEpoch==session.connectionEpoch&&navigationEpoch==session.navigationEpoch&&sourceUrl.equals(session.web.getUrl())&&fileGeneration==session.fileWorkGeneration&&configurationRevision==session.identityAuditAppliedRevision()&&route.equals(audit.routeStamp())&&policy.equals(audit.policyStamp())&&session.networkReady&&session.guard.allowed()&&session.privacy.canNavigate()&&session.web.protectionAllowsNetwork()&&!ProfileUi.working(session)&&!session.currentReplyActive()&&!session.resourceFilesUncertain()&&SystemClock.elapsedRealtime()<=deadline;}
  boolean allowsRequest(String target){return RequestIdentityAudit.serviceRequestAllowed(target,endpoint,nonce,active,scopeRegistered,fresh(),SystemClock.elapsedRealtime(),deadline);}
  void closeScope(String base,String token){session.web.requestIdentityScope(J.obj("action","cancel","endpoint",base,"nonce",token),ignored->{});}
  void finish(JSONObject value){
    if(!active)return;boolean valid=fresh();
    result=stamp(valid?value:error("environment-changed","检查期间环境已变化，服务结果没有采信",0),valid);
    if(!"ready".equals(result.optString("status")))audit.lastError=result.optString("detail");
    cleanup();audit.save();complete();
  }
  void abort(String reason,String detail){if(!active)return;result=stamp(error(reason,detail,0),false);audit.lastError=detail;cleanup();audit.save();complete();}
  void cancel(){abort("cancelled","服务检查已取消，当前聊天没有离开");}
  void cleanup(){active=false;phase="idle";if(watchdog!=null){session.handler.removeCallbacks(watchdog);watchdog=null;}if(scopeRequested||scopeRegistered){scopeRequested=scopeRegistered=false;closeScope(endpoint,nonce);}audit.cleanup();}
  void complete(){Runnable callback=audit.completed;audit.completed=null;if(callback!=null)callback.run();}
  JSONObject stamp(JSONObject value,boolean fresh){
    try{return new JSONObject(value.toString()).put("schema",1).put("at",System.currentTimeMillis()).put("source","extension-background-control").put("environmentId",session.environmentId).put("environmentGeneration",session.environmentGeneration).put("endpoint",endpoint).put("nonce",nonce).put("configurationRevision",configurationRevision).put("connectionEpoch",connectionEpoch).put("navigationEpoch",navigationEpoch).put("fileGeneration",fileGeneration).put("sourceUrl",sourceUrl).put("route",route).put("policy",policy).put("executionId",EnvironmentAudit.OBSERVATION_EXECUTION_ID).put("fresh",fresh);}catch(JSONException invalid){return new JSONObject();}
  }
  void restore(JSONObject saved){
    if(saved==null||saved.toString().length()>24000||saved.optInt("schema")!=1||!session.environmentId.equals(saved.optString("environmentId"))||session.environmentGeneration!=saved.optInt("environmentGeneration",-1)||!"extension-background-control".equals(saved.optString("source"))||!Arrays.asList("ready","failed","unavailable").contains(saved.optString("status")))return;
    if(RequestIdentityAudit.endpoint(saved.optString("endpoint")).isEmpty()||!RequestIdentityAudit.endpoint(saved.optString("endpoint")).equals(saved.optString("endpoint"))||!saved.optString("nonce").matches("[0-9a-f]{32}")||!integer(saved.opt("at"),1,Long.MAX_VALUE)||!integer(saved.opt("configurationRevision"),0,Long.MAX_VALUE)||!integer(saved.opt("connectionEpoch"),0,Long.MAX_VALUE)||!integer(saved.opt("navigationEpoch"),0,Long.MAX_VALUE)||!integer(saved.opt("fileGeneration"),0,Long.MAX_VALUE)||saved.optString("sourceUrl").length()>8192||saved.optString("detail").length()>512)return;
    if("ready".equals(saved.optString("status"))&&!requiredCapabilities(safeCapabilities(saved.optJSONObject("capabilities"),saved.optString("endpoint"))))return;
    try{result=new JSONObject(saved.toString());}catch(JSONException ignored){}
  }
  boolean resultCurrent(){
    long at=result.optLong("at"),now=System.currentTimeMillis();
    return !active&&"ready".equals(result.optString("status"))&&Boolean.TRUE.equals(result.opt("fresh"))&&at>0&&now>=at&&now-at<=RESULT_TTL_MS&&EnvironmentAudit.OBSERVATION_EXECUTION_ID.equals(result.optString("executionId"))&&!session.deleted&&session.environmentId.equals(result.optString("environmentId"))&&session.environmentGeneration==result.optInt("environmentGeneration",-1)&&result.optString("endpoint").equals(RequestIdentityAudit.endpoint(audit.requestIdentity.configuredEndpoint()))&&result.optLong("configurationRevision",-1)==session.identityAuditAppliedRevision()&&result.optLong("connectionEpoch",-1)==session.connectionEpoch&&result.optLong("navigationEpoch",-1)==session.navigationEpoch&&result.optLong("fileGeneration",-1)==session.fileWorkGeneration&&result.optString("sourceUrl").equals(session.web.getUrl())&&result.optString("route").equals(audit.routeStamp())&&result.optString("policy").equals(audit.policyStamp())&&session.networkReady&&session.guard.allowed()&&session.privacy.canNavigate()&&session.web.protectionAllowsNetwork()&&requiredCapabilities(safeCapabilities(result.optJSONObject("capabilities"),result.optString("endpoint")));
  }
  JSONObject currentCapabilities(){return resultCurrent()?safeCapabilities(result.optJSONObject("capabilities"),result.optString("endpoint")):new JSONObject();}
  boolean supportsCrossOriginFrame(String trustedEndpoint){JSONObject caps=currentCapabilities();String trusted=RequestIdentityAudit.endpoint(trustedEndpoint);return !trusted.isEmpty()&&Boolean.TRUE.equals(caps.opt("crossOriginFrame"))&&trusted.equals(caps.optString("frameEndpoint"));}
  static boolean integer(Object value,long min,long max){return value instanceof Number&&Double.isFinite(((Number)value).doubleValue())&&((Number)value).doubleValue()==((Number)value).longValue()&&((Number)value).longValue()>=min&&((Number)value).longValue()<=max;}
  static String origin(String endpoint){try{URI value=new URI(endpoint);return value.getScheme()+"://"+value.getRawAuthority();}catch(Exception invalid){return "";}}
  static JSONObject safeCapabilities(JSONObject caps,String endpoint){
    if(caps==null)return null;
    for(String key:Arrays.asList("topLevelDocument","dedicatedWorker","boundedWorkerReply","crossOriginFrame"))if(!(caps.opt(key)instanceof Boolean))return null;
    JSONObject out=J.obj("topLevelDocument",caps.optBoolean("topLevelDocument"),"dedicatedWorker",caps.optBoolean("dedicatedWorker"),"boundedWorkerReply",caps.optBoolean("boundedWorkerReply"),"crossOriginFrame",caps.optBoolean("crossOriginFrame"));
    if(caps.optBoolean("crossOriginFrame")){
      String advertised=caps.optString("frameEndpoint"),normalized=RequestIdentityAudit.endpoint(advertised),parent=caps.optString("frameParentOrigin");
      if(normalized.isEmpty()||!normalized.equals(advertised)||origin(normalized).equals(origin(endpoint))||!origin(endpoint).equals(parent))return null;
      try{out.put("frameEndpoint",advertised).put("frameParentOrigin",parent);}catch(JSONException ignored){return null;}
    }return out;
  }
  static boolean requiredCapabilities(JSONObject caps){return caps!=null&&caps.optBoolean("topLevelDocument")&&caps.optBoolean("dedicatedWorker")&&caps.optBoolean("boundedWorkerReply");}
  static JSONObject error(String reason,String detail,int status){return J.obj("status","failed","reason",reason,"detail",detail,"httpStatus",status,"scope","所选服务的连通性与固定协议能力；不代表网页身份一致或指纹保护效果");}
  static JSONObject evaluate(JSONObject control,String nonce,String endpoint){
    if(control==null||!nonce.equals(control.optString("nonce"))||!"extension-background-control".equals(control.optString("source")))return error("control-unconfirmed","没有取得与本次服务检查一致的后台回执",0);
    int status=control.optInt("httpStatus");
    if(status==429||status==503)return J.obj("status","unavailable","reason","service-capacity","detail","检测服务当前容量不足或暂不可用（HTTP "+status+"），未作指纹结论","httpStatus",status);
    if(status==404||status==405||status==501)return error("protocol-unavailable","服务不支持固定检测能力地址（HTTP "+status+"），请核对服务部署和协议版本",status);
    if(!Boolean.TRUE.equals(control.opt("ok"))){
      String reason=control.optString("error"),detail;
      switch(reason){case "service-timeout":detail="检测服务在三秒内没有完成响应；当前聊天没有离开";break;case "service-response-too-large":detail="检测服务响应超过 16KB，已停止读取且未采信";break;case "bounded-stream-unavailable":detail="当前内核没有有界响应读取能力，未采信服务结果";break;case "service-json-invalid":detail="检测服务没有返回有效的 UTF-8 JSON，可能是协议或部署不匹配";break;case "service-cancelled":case "diagnostic-scope-cancelled":case "diagnostic-scope-expired":detail="本次服务检查已取消或到期，请手动重试";break;default:reason="service-connection-or-certificate-unavailable";detail="服务连接、证书验证或禁止重定向请求失败；内核未提供可区分原因，请核对 HTTPS 服务";}
      return error(reason,detail,status);
    }
    JSONObject service=control.optJSONObject("service");
    if(!integer(control.opt("responseBytes"),1,16384))return error("response-size-unconfirmed","没有取得有界响应字节数，未采信服务能力",status);
    if(service==null||!integer(service.opt("schema"),1,1)||!RequestIdentityAudit.PROTOCOL.equals(service.optString("protocol"))||!nonce.equals(service.optString("nonce"))||!"controlled-service-capabilities".equals(service.optString("source")))return error("protocol-mismatch","服务返回的协议、来源或随机标识不匹配，未采信能力声明",status);
    if(status==403&&"credential-header-observed".equals(service.optString("reason")))return error("credentials-observed","检测服务报告收到凭据或来源标记；检查未通过，未保存其内容",status);
    if(status==409&&"header-value-too-long".equals(service.optString("reason")))return error("header-rejected","检测服务拒绝过长请求头，未作身份判断",status);
    if(status!=200||!"ready".equals(service.optString("status")))return error("service-rejected","检测服务未就绪或拒绝本次能力请求（HTTP "+status+"）",status);
    JSONObject caps=safeCapabilities(service.optJSONObject("capabilities"),endpoint),limits=service.optJSONObject("limits");
    if(caps==null||limits==null||!integer(limits.opt("checkTtlMs"),1,120000)||!integer(limits.opt("maxConcurrentChecks"),1,1024)||!integer(limits.opt("maxCheckEvents"),3,64)||!integer(limits.opt("workerResponseBytes"),1,65536))return error("capabilities-incomplete","服务能力或资源上限字段缺失、类型不符或超出客户端范围，未采信",status);
    JSONObject safeLimits=J.obj("checkTtlMs",limits.optLong("checkTtlMs"),"maxConcurrentChecks",limits.optInt("maxConcurrentChecks"),"maxCheckEvents",limits.optInt("maxCheckEvents"),"workerResponseBytes",limits.optInt("workerResponseBytes"));
    boolean ready=requiredCapabilities(caps);
    return J.obj("status",ready?"ready":"unavailable","reason",ready?"capabilities-confirmed":"required-capability-unavailable","detail",ready?"所选 HTTPS 服务的固定协议与必要能力已确认；仅对应此次后台请求，不代表文档或 Worker 身份已一致":"服务缺少文档、Dedicated Worker 或有界回复支持，尚不适合完整身份检查","httpStatus",status,"responseBytes",control.optInt("responseBytes"),"capabilities",caps,"limits",safeLimits,"backgroundCoverage",RequestIdentityAudit.backgroundCoverage(service.optJSONObject("backgroundCoverage")),"scope","所选服务的连通性与固定协议能力；不代表网页身份一致或指纹保护效果");
  }
  String summary(boolean redact){
    if(active)return "正在检查所选服务的连通性与协议能力；当前聊天不会离开…";
    if(result.length()==0)return "检测服务：尚未检查；需要你主动允许后才连接所选服务";
    StringBuilder text=new StringBuilder("检测服务：").append("ready".equals(result.optString("status"))?"协议能力已确认":"unavailable".equals(result.optString("status"))?"暂不可用":"未确认").append("\n").append(result.optString("detail"));
    text.append("\n原因代码：").append(result.optString("reason"));
    if(!resultCurrent())text.append("\n这是失败或历史结果；配置、页面、线路或一分钟有效期变化后需要重新检查。");
    if(!redact)text.append("\n服务：").append(result.optString("endpoint"));
    JSONObject caps=result.optJSONObject("capabilities");if(caps!=null)text.append("\n跨源 iframe：").append(caps.optBoolean("crossOriginFrame")?"服务声明支持；仍需单独信任并确认第二来源":"未声明支持");
    text.append("\n").append(RequestIdentityAudit.backgroundCoverageSummary(result.optJSONObject("backgroundCoverage")));
    return text.append("\n服务错误不等于指纹保护失败；证书或连接原因未分清时不会作确定归因。").toString();
  }
}
