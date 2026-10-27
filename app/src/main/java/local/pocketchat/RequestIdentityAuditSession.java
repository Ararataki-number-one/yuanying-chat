package local.pocketchat;

import android.os.SystemClock;
import org.json.*;
import java.util.*;

/** One explicit, bounded navigation on the existing session. It never returns automatically. */
final class RequestIdentityAuditSession {
  final EnvironmentAudit audit;final ChatSession session;
  boolean active,opening,navigated,collecting,scopeRegistered,scopeRequested,webDone,controlDone,frameEnabled,frameScopeRequested,frameScopeRegistered;
  long id,connectionEpoch,originalEpoch,pageEpoch,deadline,fileGeneration;
  String originalUrl="",documentUrl="",endpoint="",nonce="",route="",policy="",originalDocument="",frameEndpoint="";
  String returnUrl="",returnPage="";long returnEpoch=-1;
  JSONObject expected=new JSONObject(),browser=new JSONObject(),server=new JSONObject();
  RequestIdentityAuditSession(EnvironmentAudit audit){this.audit=audit;session=audit.session;}
  String configuredEndpoint(){return session.prefs.getString("requestIdentityEndpoint","");}
  String configure(String value){
    if(audit.running)return "检查进行中，请结束后再修改检测地址";
    String issue=RequestIdentityAudit.endpointIssue(value);if(!issue.isEmpty())return issue;
    String normalized=value==null||value.trim().isEmpty()?"":RequestIdentityAudit.endpoint(value);
    String previous=configuredEndpoint();
    if(!session.prefs.edit().putString("requestIdentityEndpoint",normalized).commit()){session.prefs.edit().putString("requestIdentityEndpoint",previous).commit();return "检测地址未可靠保存，请重试";}
    return "";
  }
  String configuredFrameEndpoint(){return session.prefs.getString("requestIdentityFrameEndpoint","");}
  static String serviceOrigin(String endpoint){try{java.net.URI uri=new java.net.URI(endpoint);int port=uri.getPort();return uri.getScheme().toLowerCase(Locale.ROOT)+"://"+uri.getHost().toLowerCase(Locale.ROOT)+(port==-1||port==443?"":":"+port);}catch(Exception error){return "";}}
  String configureFrame(String value){
    if(audit.running)return "检查进行中，请结束后再修改检测地址";
    String issue=RequestIdentityAudit.endpointIssue(value);if(!issue.isEmpty())return issue;
    String normalized=value==null||value.trim().isEmpty()?"":RequestIdentityAudit.endpoint(value);
    if(!normalized.isEmpty()&&serviceOrigin(normalized).equals(serviceOrigin(configuredEndpoint())))return "跨源检查需要你信任的第二个 HTTPS 来源";
    String previous=configuredFrameEndpoint();if(!session.prefs.edit().putString("requestIdentityFrameEndpoint",normalized).commit()){session.prefs.edit().putString("requestIdentityFrameEndpoint",previous).commit();return "第二检测地址未可靠保存，请重试";}return "";
  }
  boolean start(Runnable completed){return start(completed,false);}
  boolean startFrame(Runnable completed){return start(completed,true);}
  boolean start(Runnable completed,boolean requestedFrame){
    if(audit.running)return false;audit.lastError="";
    endpoint=RequestIdentityAudit.endpoint(configuredEndpoint());
    if(endpoint.isEmpty())return refused("请先配置你信任的 HTTPS 请求身份检测服务；尚未发出请求");
    if(session.deleted||!GeckoWebView.active(session.web)||!session.web.hasVisibleDocument()||session.navigating||!MainActivity.chatUrl(session.web.getUrl())||LoginPagePolicy.login(session.web.getUrl()))return refused("请在已显示、空闲的 ChatGPT 聊天网页打开检测");
    if(ProfileUi.working(session)||session.currentReplyActive()||session.resourceFilesUncertain())return refused("当前回复或文件状态尚未结束或确认，请完成后再打开检测页");
    if(!session.networkReady||!session.guard.allowed()||!session.privacy.canNavigate()||!session.web.protectionAllowsNetwork())return refused("当前连接或浏览器保护尚未确认，检测页没有打开");
    String selectedFrame=requestedFrame?RequestIdentityAudit.endpoint(configuredFrameEndpoint()):"";
    if(requestedFrame&&(selectedFrame.isEmpty()||serviceOrigin(selectedFrame).equals(serviceOrigin(endpoint))||!audit.serviceProbe.supportsCrossOriginFrame(selectedFrame)))return refused("请先检查服务能力，并确认已配置的第二 HTTPS 来源与服务声明一致");
    frameEnabled=requestedFrame;frameEndpoint=selectedFrame;
    originalUrl=session.web.getUrl();originalEpoch=session.navigationEpoch;connectionEpoch=session.connectionEpoch;fileGeneration=session.fileWorkGeneration;
    route=audit.routeStamp();policy=audit.policyStamp();expected=audit.expected();
    try{expected.put("environmentId",session.environmentId).put("environmentGeneration",session.environmentGeneration).put("configurationRevision",session.identityAuditAppliedRevision()).put("templateId",session.web.getSettings().acceptedBrowserIdentity.optString("templateId"));if(frameEnabled)expected.put("crossOriginFrame",true).put("frameEndpoint",frameEndpoint);}catch(JSONException ignored){}
    nonce=UUID.randomUUID().toString().replace("-","");documentUrl=RequestIdentityAudit.documentUrl(endpoint,nonce,frameEnabled);
    active=true;opening=navigated=collecting=scopeRegistered=scopeRequested=webDone=controlDone=frameScopeRequested=frameScopeRegistered=false;browser=server=new JSONObject();originalDocument="";
    audit.running=true;audit.networkRun=true;audit.geckoRun=true;audit.completed=completed;id=++audit.serial;deadline=SystemClock.elapsedRealtime()+20000;
    audit.identityAppliedRevision=session.identityAuditAppliedRevision();session.updateBrowserActivity();
    long request=id;
    session.handler.postDelayed(()->{if(current(request)){if(!navigated){abort("检测准备超时，原聊天没有离开");return;}audit.lastError="请求身份检测超时；检测页不会自动返回原聊天";finish();}},20500);
    session.asyncDriver("web-inspect",new JSONObject(),2000,inspection->{
      if(!preflightFresh(request))return;
      if(!(inspection.opt("busy")instanceof Boolean)||inspection.optBoolean("busy")||!originalUrl.equals(inspection.optString("url"))){abort("当前网页状态尚未可靠确认，检测页没有打开");return;}
      inspectDraft(request,null);
    });return true;
  }
  boolean refused(String message){audit.lastError=message;return false;}
  boolean current(long request){return active&&audit.current(request)&&request==id;}
  boolean routeFresh(){return !session.deleted&&endpoint.equals(RequestIdentityAudit.endpoint(configuredEndpoint()))&&(!frameEnabled||frameEndpoint.equals(RequestIdentityAudit.endpoint(configuredFrameEndpoint())))&&connectionEpoch==session.connectionEpoch&&route.equals(audit.routeStamp())&&policy.equals(audit.policyStamp())&&session.networkReady&&session.guard.allowed()&&session.privacy.canNavigate()&&session.web.protectionAllowsNetwork()&&fileGeneration==session.fileWorkGeneration&&session.identityAuditAppliedRevision()==expected.optLong("configurationRevision");}
  boolean preflightFresh(long request){
    if(!current(request))return false;
    if(!routeFresh()||originalEpoch!=session.navigationEpoch||!originalUrl.equals(session.web.getUrl())||ProfileUi.working(session)||session.currentReplyActive()||session.resourceFilesUncertain()){
      abort("检查准备期间网页、输入任务或连接已变化，检测页没有打开");return false;
    }
    return true;
  }
  boolean completePage(JSONObject page){return page!=null&&Boolean.TRUE.equals(page.opt("ok"))&&originalUrl.equals(page.optString("url"))&&page.optString("documentId").matches("[a-zA-Z0-9-]{16,80}")&&Boolean.TRUE.equals(page.opt("draftComplete"))&&page.opt("draftLength") instanceof Number&&((Number)page.opt("draftLength")).doubleValue()==page.optString("draft").length()&&PageMemory.completeDraft(page);}
  void inspectDraft(long request,JSONObject previous){
    session.asyncDriver("page-state",J.obj("expectedUrl",originalUrl),2000,page->{
      if(!preflightFresh(request))return;
      if(!completePage(page)){
        abort("无法完整核对当前输入，检测页没有打开；请先手动保留草稿");return;
      }
      if(!page.optString("draft").isEmpty()){abort("当前输入框有未发送内容，请先手动保留或清空后再打开检测页");return;}
      if(previous==null){inspectDraft(request,page);return;}
      if(!previous.optString("documentId").equals(page.optString("documentId"))||!previous.optString("draft").equals(page.optString("draft"))){abort("当前页面或输入已变化，检测页没有打开");return;}
      String namespace=session.pageMemory.scope();if(namespace.isEmpty()){abort("当前环境的页面保存范围尚未确认，检测页没有打开");return;}
      originalDocument=page.optString("documentId");session.pageMemory.remember(namespace,originalUrl,page);
      String registeredNonce=nonce,registeredEndpoint=endpoint;scopeRequested=true;
      JSONObject registration=J.obj("action","register","endpoint",endpoint,"nonce",nonce,"purpose","identity");if(frameEnabled)try{registration.put("crossOriginFrame",true).put("frameEndpoint",frameEndpoint);}catch(JSONException ignored){}
      session.web.requestIdentityScope(registration,raw->{
        JSONObject accepted=raw!=null&&raw.length()<4096?J.parse(raw):new JSONObject();
        boolean registered=accepted.optBoolean("ok")&&registeredNonce.equals(accepted.optString("nonce"));
        if(!current(request)){if(registered)session.web.requestIdentityScope(J.obj("action","cancel","endpoint",registeredEndpoint,"nonce",registeredNonce),ignored->{});return;}
        scopeRegistered=registered;
        if(!preflightFresh(request))return;
        if(!accepted.optBoolean("ok")||!nonce.equals(accepted.optString("nonce"))||!accepted.optBoolean("credentialFilter")||!accepted.optBoolean("redirectsBlocked")||frameEnabled&&(!"identity".equals(accepted.optString("purpose"))||!accepted.optBoolean("crossOriginFrame"))){
          abort("检测请求的凭据过滤尚未确认，检测页没有打开");return;
        }
        scopeRegistered=true;
        if(frameEnabled)registerFrame(request,namespace);else openAfterProtection(request,namespace);
      });
    });
  }
  void registerFrame(long request,String namespace){
    String registeredEndpoint=frameEndpoint,registeredNonce=nonce;frameScopeRequested=true;
    session.web.requestIdentityScope(J.obj("action","register","endpoint",registeredEndpoint,"nonce",registeredNonce,"purpose","frame","parentEndpoint",endpoint),raw->{
      JSONObject accepted=raw!=null&&raw.length()<4096?J.parse(raw):new JSONObject();boolean registered=accepted.optBoolean("ok")&&registeredNonce.equals(accepted.optString("nonce"));
      if(!current(request)){if(registered)session.web.requestIdentityScope(J.obj("action","cancel","endpoint",registeredEndpoint,"nonce",registeredNonce),ignored->{});return;}
      frameScopeRegistered=registered;
      if(!preflightFresh(request))return;
      if(!registered||!"frame".equals(accepted.optString("purpose"))||!accepted.optBoolean("credentialFilter")||!accepted.optBoolean("redirectsBlocked")){abort("第二检测来源的凭据与重定向保护未确认，没有离开聊天");return;}
      openAfterProtection(request,namespace);
    });
  }
  void openAfterProtection(long request,String namespace){
    session.asyncDriver("page-state",J.obj("expectedUrl",originalUrl),2000,latest->{
      if(!preflightFresh(request))return;
      if(!completePage(latest)||!originalDocument.equals(latest.optString("documentId"))||!latest.optString("draft").isEmpty()||!namespace.equals(session.pageMemory.scope())){abort("等待检测保护确认期间页面或输入已变化，检测页没有打开");return;}
      session.pageMemory.remember(namespace,originalUrl,latest);opening=true;session.web.loadUrl(documentUrl);
    });
  }
  /** Called before ChatSession's ordinary chat navigation handlers. */
  boolean pageStarted(String target){
    if(!active){if(!returnPage.isEmpty()&&!returnPage.equals(target))clearReturn();return false;}
    if(!opening||!documentUrl.equals(target)||!routeFresh()||originalEpoch!=session.navigationEpoch){abort("检测页面已变化，本次检查已取消");return false;}
    opening=false;navigated=true;returnUrl=originalUrl;returnPage=documentUrl;
    session.beginNavigation(documentUrl,"正在打开请求身份检测页…");pageEpoch=session.navigationEpoch;returnEpoch=pageEpoch;
    audit.auditUrl=documentUrl;audit.auditNavigation=pageEpoch;return true;
  }
  boolean pageFinished(String target){
    if(!navigated||!documentUrl.equals(target)||!pageOwned())return false;
    if(active&&!collecting){session.finishNavigation("",false);waitDocument(id,SystemClock.elapsedRealtime()+3000);}
    return true;
  }
  boolean pageFailed(String target,String reason){
    if(!active||!documentUrl.equals(target)||!(opening||pageOwned()))return false;
    audit.lastError="请求身份检测服务暂不可用，未作一致性判断";
    session.finishNavigation("请求身份检测服务暂不可用",false);finish();return true;
  }
  boolean allowsRequest(String target){if(!active||!scopeRegistered)return false;return RequestIdentityAudit.controlledRequestAllowed(target,endpoint,nonce,active,scopeRegistered,routeFresh()&&(opening||pageOwned()),SystemClock.elapsedRealtime(),deadline,frameEnabled,frameEndpoint,frameScopeRegistered);}
  boolean pageOwned(){return navigated&&pageEpoch==session.navigationEpoch&&documentUrl.equals(session.web.getUrl());}
  boolean pageSelected(){return !session.deleted&&!returnPage.isEmpty()&&returnPage.equals(session.web.getUrl());}
  boolean pageActive(){return pageSelected()&&returnEpoch==session.navigationEpoch;}
  boolean fresh(){return active&&routeFresh()&&pageOwned()&&SystemClock.elapsedRealtime()<=deadline;}
  void waitDocument(long request,long until){
    if(!current(request)||collecting)return;
    if(!fresh()){abort("检测期间页面或连接已变化，结果没有更新");return;}
    if(!session.web.hasVisibleDocument()){
      if(SystemClock.elapsedRealtime()<until){session.handler.postDelayed(()->waitDocument(request,until),100);return;}
      audit.lastError="检测页面通信暂未就绪";finish();return;
    }
    collecting=true;
    JSONObject identity=J.obj("endpoint",endpoint,"nonce",nonce);if(frameEnabled)try{identity.put("crossOriginFrame",true).put("frameEndpoint",frameEndpoint);}catch(JSONException ignored){}
    session.web.runEnvironmentAudit(J.obj("id",String.valueOf(request),"network",false,"apiChecks",false,"requestIdentity",identity),raw->{
      if(!current(request))return;
      JSONObject result=raw!=null&&raw.length()<=64000?J.parse(raw):new JSONObject();
      if(String.valueOf(request).equals(result.optString("id")))browser=result;
      webDone=true;finishIfReady();
    });
    pollServer(request);
  }
  void pollServer(long request){
    if(!current(request))return;
    if(!fresh()){abort("检测期间页面、配置或连接已变化，结果没有更新");return;}
    String requestNonce=nonce,requestEndpoint=endpoint;
    session.web.requestIdentityScope(J.obj("action","evidence","endpoint",requestEndpoint,"nonce",requestNonce),raw->{
      if(!current(request))return;
      if(!fresh()){abort("独立服务端记录返回时环境已变化，结果没有更新");return;}
      JSONObject control=raw!=null&&raw.length()<=64000?J.parse(raw):new JSONObject();
      if(!Boolean.TRUE.equals(control.opt("ok"))||!requestNonce.equals(control.optString("nonce"))||!"extension-background-control".equals(control.optString("source"))||control.optJSONObject("server")==null){
        String issue=control.optString("error");audit.lastError="detector-response-too-large".equals(issue)?"检测服务返回超过 32KB，未采信结果":"bounded-stream-unavailable".equals(issue)?"当前内核没有有界响应读取能力，未采信结果":"diagnostic-scope-expired".equals(issue)||"evidence-cancelled".equals(issue)?"本次检测保护已到期或取消，请手动重新检查":"独立服务端记录未能完整取得，未作身份一致判断";
        server=new JSONObject();controlDone=true;finishIfReady();return;
      }
      JSONObject response=control.optJSONObject("server");
      if(control.optInt("httpStatus")==202&&"pending".equals(response.optString("status"))&&SystemClock.elapsedRealtime()+150<deadline){session.handler.postDelayed(()->pollServer(request),150);return;}
      server=response;controlDone=true;finishIfReady();
    });
  }
  void finishIfReady(){if(webDone&&controlDone)finish();}
  void finish(){
    if(!active)return;
    boolean fresh=fresh();JSONObject checked=RequestIdentityAudit.evaluate(browser.optJSONObject("requestIdentity"),server,expected,nonce,endpoint,fresh);
    JSONObject report=AuditReport.build(browser,new JSONObject(),expected,false,fresh);
    try{
      report.put("identityAppliedRevision",audit.identityAppliedRevision).put("policy",policy).put("route",route).put("connectionEpoch",connectionEpoch).put("executionId",EnvironmentAudit.OBSERVATION_EXECUTION_ID).put("requestIdentityNetwork",true).put("requestIdentityControlSource","extension-background-control").put("requestIdentity",checked);
      report.put("scope","受控顶层检测页的网页公开字段，与单独列出的文档／Dedicated Worker 服务端 HTTP 记录；结果由扩展后台独立读取，不代表 ChatGPT 官网、其他执行环境或全部指纹保护");
      JSONArray rows=report.optJSONArray("rows"),extra=checked.optJSONArray("rows");if(rows!=null&&extra!=null)for(int i=0;i<extra.length();i++)rows.put(extra.get(i));
      if(rows!=null)for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);if(row!=null&&"worker-header".equals(row.optString("key")))row.put("name","普通信息自检的 Worker 请求头覆盖").put("detail","普通公开字段采样不核对 Worker HTTP 头；本次受控检测页的独立服务端对照已另列，两种来源不合并为全站结论");}
    }catch(JSONException ignored){}
    try{checked.put("at",System.currentTimeMillis()).put("environmentId",session.environmentId).put("environmentGeneration",session.environmentGeneration).put("configurationRevision",audit.identityAppliedRevision).put("policy",policy).put("route",route).put("connectionEpoch",connectionEpoch).put("executionId",EnvironmentAudit.OBSERVATION_EXECUTION_ID).put("fresh",fresh).put("crossOriginFrameRequested",frameEnabled).put("frameEndpoint",frameEnabled?frameEndpoint:"");}catch(JSONException ignored){}
    audit.requestIdentityReport=checked;
    audit.report=report;audit.decorateObservation(report,documentUrl,pageEpoch);if(fresh){session.identityObserved(report);audit.recordObservation(report,documentUrl);}
    cleanup();audit.refresh(true);audit.save();complete();
  }
  void abort(String message){if(!active)return;audit.lastError=message;cleanup();complete();}
  void cancel(){abort("请求身份检查已取消，没有更新报告；检测页不会自动跳回聊天");}
  void cleanup(){
    active=opening=false;
    if(scopeRequested||scopeRegistered){scopeRequested=scopeRegistered=false;session.web.requestIdentityScope(J.obj("action","cancel","endpoint",endpoint,"nonce",nonce),ignored->{});}
    if(frameScopeRequested||frameScopeRegistered){frameScopeRequested=frameScopeRegistered=false;session.web.requestIdentityScope(J.obj("action","cancel","endpoint",frameEndpoint,"nonce",nonce),ignored->{});}
    audit.cleanup();
  }
  void complete(){Runnable callback=audit.completed;audit.completed=null;if(callback!=null)callback.run();}
  boolean canReturn(){return pageSelected()&&!returnUrl.isEmpty()&&MainActivity.chatUrl(returnUrl);}
  boolean back(){
    if(!canReturn())return refused("当前已不是本次检测页，没有覆盖你后来打开的页面");
    if(ProfileUi.working(session)||session.resourceFilesUncertain()||!session.networkReady||!session.guard.allowed()||!session.privacy.canNavigate()||!session.web.protectionAllowsNetwork())return refused("当前网页任务或连接尚未就绪，请恢复后再返回原聊天");
    String target=returnUrl;if(active)cancel();clearReturn();session.navigate(target,"正在返回原聊天…");return true;
  }
  void clearReturn(){returnUrl=returnPage="";returnEpoch=-1;}
  String summary(boolean redact){
    JSONObject value=audit.requestIdentityReport;if(value==null||value.length()==0)return configuredEndpoint().isEmpty()?"请求身份检测：未配置受控 HTTPS 服务，尚未覆盖":"请求身份检测：尚未执行";
    String state=value.optString("status");StringBuilder text=new StringBuilder("请求身份检测：").append("observed".equals(state)?"已采集":"issue".equals(state)?"存在差异":"未覆盖").append("\n来源：受控 HTTPS 顶层检测文档与 Dedicated Worker，不代表 ChatGPT 官网");
    if(!value.optBoolean("fresh")||!audit.observationCurrent(value)||!value.optString("policy").equals(audit.policyStamp())||!value.optString("route").equals(audit.routeStamp())||!value.optString("endpoint").equals(configuredEndpoint())||value.optLong("configurationRevision")!=session.identityAuditAppliedRevision()||value.optBoolean("crossOriginFrameRequested")&&!value.optString("frameEndpoint").equals(RequestIdentityAudit.endpoint(configuredFrameEndpoint())))text.append("\n这是历史结果，当前环境或检测配置已变化，请重新检查。");
    JSONArray comparisons=value.optJSONArray("rows");if(comparisons!=null)for(int i=0;i<comparisons.length();i++){JSONObject row=comparisons.optJSONObject(i);if(row!=null)text.append("\n\n").append(AuditReport.stateLabel(row.optString("state"))).append(" · ").append(row.optString("name")).append("\n").append(row.optString("detail"));}
    JSONObject javascript=value.optJSONObject("browser");if(javascript!=null)for(String source:Arrays.asList("document","worker")){JSONObject signal=javascript.optJSONObject(source);if(signal!=null)text.append("\n\n").append(source).append(" JavaScript UA：").append(signal.optString("ua")).append("\nJavaScript 语言：").append(signal.optString("language")).append(" · ").append(signal.optJSONArray("languages"));}
    JSONObject nativeConfiguration=value.optJSONObject("expected");if(nativeConfiguration!=null)text.append("\n\n原生 UA 请求：").append(nativeConfiguration.optString("ua")).append("\n原生语言请求：").append(nativeConfiguration.optString("language")).append("\n模板：").append(nativeConfiguration.optString("templateId").isEmpty()?"尚未确认":nativeConfiguration.optString("templateId")).append(" · 配置版本 ").append(nativeConfiguration.optLong("configurationRevision"));
    JSONObject server=value.optJSONObject("server");JSONArray events=server==null?null:server.optJSONArray("events");if(events!=null)for(int i=0;i<events.length();i++){
      JSONObject event=events.optJSONObject(i),headers=event==null?null:event.optJSONObject("headers"),peer=event==null?null:event.optJSONObject("peer");if(headers==null||peer==null)continue;
      text.append("\n\n").append(event.optString("source")).append("\nHTTP UA：").append(headers.optString("userAgent")).append("\nHTTP 语言：").append(headers.optString("acceptLanguage")).append("\n服务端对端：").append(redact?"[地址已隐藏]":peer.optString("address"));
    }
    return text.append("\n检测服务是独立的信任来源；反代部署时 socket 对端不等于实际出口。").toString();
  }
}
