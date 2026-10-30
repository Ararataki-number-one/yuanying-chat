package local.pocketchat;

import org.json.*;
import java.net.URI;
import java.net.URLDecoder;
import java.util.*;

/** Bounded comparison of an explicitly selected HTTPS service, never site-wide attestation. */
final class RequestIdentityAudit {
  static final String PATH="/pocketchat-identity/v1/",PROTOCOL="pocketchat-request-identity-v1";
  static String endpoint(String value){
    try{
      URI uri=new URI(value==null?"":value.trim());String path=uri.getRawPath();
      if(!"https".equalsIgnoreCase(uri.getScheme())||uri.getHost()==null||uri.getHost().isEmpty()||uri.getRawUserInfo()!=null||uri.getRawQuery()!=null||uri.getRawFragment()!=null||uri.getPort()==0||uri.getPort()>65535||!PATH.equals(path)&&!PATH.substring(0,PATH.length()-1).equals(path))return "";
      String host=uri.getHost().toLowerCase(Locale.ROOT);if(host.contains(":" )&&!host.startsWith("["))host="["+host+"]";
      return "https://"+host+(uri.getPort()<0||uri.getPort()==443?"":":"+uri.getPort())+PATH;
    }catch(Exception invalid){return "";}
  }
  static String endpointIssue(String value){return value!=null&&value.trim().isEmpty()||!endpoint(value).isEmpty()?"":"请输入 HTTPS 检测地址，路径须为 "+PATH+"，不能包含账号、查询参数或片段";}
  static String url(String endpoint,String kind,String nonce){if(endpoint(endpoint).isEmpty()||!nonce.matches("[0-9a-f]{32}")||!Arrays.asList("document","result","capabilities").contains(kind))throw new IllegalArgumentException("Invalid controlled diagnostic URL");return endpoint(endpoint)+kind+"?nonce="+nonce;}
  static String documentUrl(String endpoint,String nonce,boolean frameEnabled){return url(endpoint,"document",nonce)+(frameEnabled?"&frame=1":"");}
  static boolean namespace(String path){String value=path.replaceAll("/{2,}","/").toLowerCase(Locale.ROOT);return value.startsWith(PATH)||value.equals(PATH.substring(0,PATH.length()-1));}
  static boolean diagnosticUrl(String target){
    if(target==null)return false;boolean candidate=target.indexOf('%')>=0||target.contains("..");
    if(!candidate)for(int i=0;i+9<=target.length();i++)if((target.charAt(i)=='p'||target.charAt(i)=='P')&&target.regionMatches(true,i,"pocketchat",0,9)){candidate=true;break;}
    if(!candidate)return false;
    try{
      String path=new URI(target).getRawPath();if(path==null)return false;
      for(int i=0;i<4;i++){
        if(namespace(path)||namespace(new URI(null,null,path,null).normalize().getPath()))return true;
        String decoded=URLDecoder.decode(path,"UTF-8");if(decoded.equals(path))break;path=decoded;
      }
      return namespace(path)||namespace(new URI(null,null,path,null).normalize().getPath());
    }catch(Exception invalid){return target.toLowerCase(Locale.ROOT).contains(PATH);}
  }
  static boolean requestAllowed(String target,String endpoint,String nonce,boolean active,boolean registered,boolean fresh,long now,long deadline){
    if(!active||!registered||!fresh||now>deadline||nonce==null||!nonce.matches("[0-9a-f]{32}"))return false;
    String base=endpoint(endpoint);if(base.isEmpty())return false;
    try{
      URI uri=new URI(target),wanted=new URI(base);int port=uri.getPort()<0?443:uri.getPort(),expectedPort=wanted.getPort()<0?443:wanted.getPort();
      if(!"https".equalsIgnoreCase(uri.getScheme())||uri.getHost()==null||!uri.getHost().equalsIgnoreCase(wanted.getHost())||port!=expectedPort||uri.getRawUserInfo()!=null||uri.getRawFragment()!=null)return false;
      String path=uri.getRawPath(),query=uri.getRawQuery();
      return ((PATH+"document").equals(path)||(PATH+"worker.js").equals(path)||(PATH+"result").equals(path))?("nonce="+nonce).equals(query):(PATH+"observe").equals(path)&&("nonce="+nonce+"&source=worker").equals(query);
    }catch(Exception invalid){return false;}
  }
  static boolean exactOperation(String target,String endpoint,String operation,String query){
    String base=endpoint(endpoint);if(base.isEmpty())return false;
    try{
      URI uri=new URI(target),wanted=new URI(base);int port=uri.getPort()<0?443:uri.getPort(),expectedPort=wanted.getPort()<0?443:wanted.getPort();
      return "https".equalsIgnoreCase(uri.getScheme())&&uri.getHost()!=null&&uri.getHost().equalsIgnoreCase(wanted.getHost())&&port==expectedPort&&uri.getRawUserInfo()==null&&uri.getRawFragment()==null&&(PATH+operation).equals(uri.getRawPath())&&query.equals(uri.getRawQuery());
    }catch(Exception invalid){return false;}
  }
  static boolean serviceRequestAllowed(String target,String endpoint,String nonce,boolean active,boolean registered,boolean fresh,long now,long deadline){
    return active&&registered&&fresh&&now<=deadline&&nonce!=null&&nonce.matches("[0-9a-f]{32}")&&exactOperation(target,endpoint,"capabilities","nonce="+nonce);
  }
  static boolean controlledRequestAllowed(String target,String endpoint,String nonce,boolean active,boolean registered,boolean fresh,long now,long deadline,boolean frameEnabled,String frameEndpoint,boolean frameRegistered){
    if(requestAllowed(target,endpoint,nonce,active,registered,fresh,now,deadline))return true;
    if(!active||!registered||!fresh||now>deadline||!frameEnabled||!frameRegistered||nonce==null||!nonce.matches("[0-9a-f]{32}"))return false;
    String first=endpoint(endpoint),second=endpoint(frameEndpoint);if(first.isEmpty()||second.isEmpty())return false;
    try{URI a=new URI(first),b=new URI(second);if(a.getHost().equalsIgnoreCase(b.getHost())&&a.getPort()==b.getPort())return false;}catch(Exception invalid){return false;}
    return exactOperation(target,first,"document","nonce="+nonce+"&frame=1")||exactOperation(target,second,"frame","nonce="+nonce);
  }
  static boolean text(JSONObject value,String key,int max){Object raw=value.opt(key);return raw instanceof String&&!((String)raw).isEmpty()&&((String)raw).length()<=max;}
  static boolean js(JSONObject value){if(value==null||!text(value,"ua",2048)||!text(value,"language",128))return false;JSONArray list=value.optJSONArray("languages");if(list==null||list.length()<1||list.length()>8)return false;for(int i=0;i<list.length();i++)if(!(list.opt(i)instanceof String)||list.optString(i).isEmpty()||list.optString(i).length()>128)return false;return true;}
  static boolean address(String value){
    if(value.matches("[0-9]{1,3}(?:\\.[0-9]{1,3}){3}")){for(String part:value.split("\\."))if(Integer.parseInt(part)>255)return false;return true;}
    if(!value.matches("[0-9a-fA-F:]{2,64}"))return false;
    String[] compressed=value.split("::",-1);if(compressed.length>2)return false;int groups=0;
    for(String half:compressed){if(half.isEmpty())continue;for(String part:half.split(":",-1)){if(!part.matches("[0-9a-fA-F]{1,4}"))return false;groups++;}}
    return compressed.length==2?groups<8:groups==8;
  }
  static String language(String header){return header.split(",",2)[0].split(";",2)[0].trim();}
  static String origin(String endpoint){try{URI uri=new URI(endpoint(endpoint));return uri.getHost()==null?"":"https://"+uri.getHost()+(uri.getPort()<0||uri.getPort()==443?"":":"+uri.getPort());}catch(Exception invalid){return "";}}
  static boolean number(JSONObject value,String key,long min,long max){Object raw=value.opt(key);return raw instanceof Number&&Double.isFinite(((Number)raw).doubleValue())&&((Number)raw).doubleValue()==((Number)raw).longValue()&&((Number)raw).longValue()>=min&&((Number)raw).longValue()<=max;}
  static String safeReason(JSONObject value,String fallback){String reason=value==null?"":value.optString("reason");return reason.matches("[A-Za-z0-9_-]{1,96}")?reason:fallback;}
  static boolean copyHash(JSONObject raw,JSONObject out,String key,String algorithm,String unavailable){
    if(raw.has(key)){String hash=raw.optString(key);if(!(raw.opt(key) instanceof String)||!hash.matches("[0-9a-f]{64}")||!"sha256".equals(raw.optString(algorithm)))return false;try{out.put(key,hash).put(algorithm,"sha256");}catch(JSONException ignored){}return true;}
    if(!Boolean.TRUE.equals(raw.opt(unavailable)))return false;try{out.put(unavailable,true);}catch(JSONException ignored){}return true;
  }
  static JSONObject frameProbe(JSONObject raw,boolean webgl){
    if(raw==null)return J.obj("state","uncovered","reason","missing-frame-operation");String state=raw.optString("state");
    if(!Arrays.asList("available","restricted","failed","uncovered").contains(state)||!text(raw,"reason",96))return J.obj("state","uncovered","reason","invalid-frame-operation-state");
    JSONObject out=J.obj("state",state,"reason",safeReason(raw,"frame-operation-result"));
    boolean performed="available".equals(state)||"restricted".equals(state)&&(raw.has("pixels")||raw.has("readbackPixels"));
    if(!performed)return out;
    if(!webgl){if(!number(raw,"pixels",4096,4096)||!copyHash(raw,out,"hash","hashAlgorithm","hashUnavailable"))return J.obj("state","uncovered","reason","invalid-frame-canvas-readback");try{out.put("pixels",4096);}catch(JSONException ignored){}return out;}
    if(!number(raw,"readbackPixels",256,256)||!number(raw,"readbackBytes",1024,1024)||!copyHash(raw,out,"hash","hashAlgorithm","hashUnavailable")||!copyHash(raw,out,"readbackHash","readbackHashAlgorithm","readbackHashUnavailable"))return J.obj("state","uncovered","reason","invalid-frame-webgl-readback");
    try{out.put("readbackPixels",256).put("readbackBytes",1024);for(String key:Arrays.asList("version","shadingLanguageVersion","vendor","renderer","unmaskedRenderer"))if(raw.has(key)){if(!text(raw,key,256))return J.obj("state","uncovered","reason","invalid-frame-webgl-capability");out.put(key,raw.optString(key));}for(String key:Arrays.asList("maxTextureSize","maxRenderbufferSize","maxVertexAttribs","extensionCount"))if(raw.has(key)){if(!number(raw,key,0,Integer.MAX_VALUE))return J.obj("state","uncovered","reason","invalid-frame-webgl-capability");out.put(key,raw.optLong(key));}}catch(JSONException ignored){}
    return out;
  }
  static JSONObject frameObservation(JSONObject browser,JSONObject expected,String nonce,String primaryEndpoint){
    if(!Boolean.TRUE.equals(expected.opt("crossOriginFrame")))return null;
    String endpoint=endpoint(expected.optString("frameEndpoint")),wanted=origin(endpoint);JSONObject value=browser==null?null:browser.optJSONObject("crossOriginFrame");
    JSONObject missing=J.obj("status","uncovered","source","controlled-cross-origin-iframe","nonce",nonce,"origin",wanted,"reason","controlled-frame-observation-unavailable","protectionVerified",false);
    if(endpoint.isEmpty()||wanted.isEmpty()||wanted.equals(origin(primaryEndpoint))){try{missing.put("reason","invalid-cross-origin-frame-endpoint");}catch(JSONException ignored){}return missing;}
    if(value==null||!"controlled-cross-origin-iframe".equals(value.optString("source"))||!nonce.equals(value.optString("nonce"))||!wanted.equals(value.optString("origin")))return missing;
    if(!"complete".equals(value.optString("status"))){try{missing.put("reason",safeReason(value,"controlled-frame-not-completed"));}catch(JSONException ignored){}return missing;}
    JSONObject apis=value.optJSONObject("apiChecks"),limits=apis==null?null:apis.optJSONObject("limits"),probes=apis==null?null:apis.optJSONObject("probes");
    if(apis==null||limits==null||probes==null||!number(apis,"schema",1,1)||!number(apis,"probeVersion",1,1)||!Boolean.TRUE.equals(apis.opt("requested"))||!Boolean.FALSE.equals(apis.opt("protectionVerified"))||!"controlled-cross-origin-iframe".equals(apis.optString("source"))||!Arrays.asList("completed","partial").contains(apis.optString("status"))||!number(limits,"canvasPixels",4096,4096)||!number(limits,"audioFrames",0,0)||!number(limits,"fontCandidates",0,0)||!number(limits,"totalBudgetMs",1200,1200)){try{missing.put("reason","invalid-controlled-frame-probe-contract");}catch(JSONException ignored){}return missing;}
    JSONObject canvas=frameProbe(probes.optJSONObject("canvas"),false),webgl=frameProbe(probes.optJSONObject("webgl"),true),clean=J.obj("schema",1,"requested",true,"source","controlled-cross-origin-iframe","probeVersion",1,"status","uncovered".equals(canvas.optString("state"))||"uncovered".equals(webgl.optString("state"))?"partial":"completed","limits",J.obj("canvasPixels",4096,"audioFrames",0,"fontCandidates",0,"totalBudgetMs",1200),"probes",J.obj("canvas",canvas,"webgl",webgl,"audio",J.obj("state","uncovered","reason","not-covered-by-controlled-frame-graphics"),"fonts",J.obj("state","uncovered","reason","not-covered-by-controlled-frame-graphics")),"protectionVerified",false);
    return J.obj("status","complete","source","controlled-cross-origin-iframe","nonce",nonce,"origin",wanted,"apiChecks",clean,"protectionVerified",false,"scope","Only the explicitly selected secondary-origin Canvas/WebGL operations; independent context, not cross-context hash equality or protection attestation");
  }
  static void row(JSONArray rows,String key,String name,String state,String detail){rows.put(J.obj("key",key,"name",name,"state",state,"detail",detail));}
  static JSONObject backgroundCoverage(JSONObject serviceDeclaration){
    JSONObject coverage=J.obj("schema",1,"source","client-coverage-policy","registeredOrClearedSiteWorkers",false);
    for(String key:Arrays.asList("sharedWorker","serviceWorker")){
      Object value=serviceDeclaration==null?null:serviceDeclaration.opt(key);
      String statement=Boolean.TRUE.equals(value)?"declared-supported":Boolean.FALSE.equals(value)?"declared-unsupported":"unknown";
      try{coverage.put(key,J.obj("state","not-covered","serviceStatement",statement,"requestHeadersObserved",false,"cacheLifecycleObserved",false));}catch(JSONException ignored){}
    }return coverage;
  }
  static String backgroundCoverageSummary(JSONObject coverage){
    StringBuilder text=new StringBuilder();
    for(String key:Arrays.asList("sharedWorker","serviceWorker")){
      JSONObject value=coverage==null?null:coverage.optJSONObject(key);String statement=value==null?"unknown":value.optString("serviceStatement");
      String service="declared-supported".equals(statement)?"服务自述支持，客户端未验证":"declared-unsupported".equals(statement)?"服务自述未支持":"服务支持情况未知";
      if(text.length()>0)text.append('\n');text.append(key.equals("sharedWorker")?"Shared Worker":"Service Worker").append("：客户端尚未覆盖；").append(service);
    }return text.append("\n未检查这两类请求、缓存或生命周期，也未注册或清理站点 Worker。").toString();
  }
  static JSONObject uncovered(String nonce,String endpoint,String reason){return J.obj("schema",1,"nonce",nonce,"endpoint",endpoint,"status","uncovered","source","controlled-top-level-document","rows",J.arr(J.obj("key","request-identity","name","真实请求身份对照","state","uncovered","detail",reason)),"fullDesktopUaConsistency",false,"fingerprintTemplateAcceptance",false,"scope","仅对应用户选择的受控 HTTPS 检测页；不代表 ChatGPT 官网或全部请求路径");}
  static Set<String> pendingSources(JSONObject server){
    JSONArray records=server.optJSONArray("events");if(records==null||records.length()>12)return null;Set<String> found=new HashSet<>();
    for(int i=0;i<records.length();i++){
      JSONObject event=records.optJSONObject(i);if(event==null||!number(event,"index",i+1,i+1)||!"GET".equals(event.opt("method")))return null;
      Object rawSource=event.opt("source");if(!(rawSource instanceof String))return null;String source=(String)rawSource;
      String operation=source.equals("document")?"document":source.equals("worker-script")?"worker.js":source.equals("worker-fetch")?"observe":source.equals("control-result")?"result":"";
      JSONObject headers=event.optJSONObject("headers"),peer=event.optJSONObject("peer"),sensitive=event.optJSONObject("sensitiveHeaders");
      if(operation.isEmpty()||!(PATH+operation).equals(event.opt("path"))||!found.add(source)||headers==null||peer==null||sensitive==null||!text(headers,"userAgent",2048)||!(headers.opt("acceptLanguage") instanceof String)||headers.optString("acceptLanguage").length()>1024||!(headers.opt("secFetchDest") instanceof String)||headers.optString("secFetchDest").length()>64||!text(peer,"address",128)||!address(peer.optString("address"))||!"socket-peer".equals(peer.opt("source")))return null;
      for(String field:Arrays.asList("cookie","authorization","proxyAuthorization","referer","origin"))if(!Boolean.FALSE.equals(sensitive.opt(field)))return null;
      String destination=headers.optString("secFetchDest");if(source.equals("document")&&!destination.equals("document")||source.equals("worker-script")&&!destination.equals("worker")||source.equals("worker-fetch")&&!destination.equals("empty"))return null;
    }
    return found;
  }
  static JSONObject notReady(JSONObject server,String nonce,String endpoint){
    Object rawStatus=server.opt("status");String status="pending".equals(rawStatus)?"pending":"rejected".equals(rawStatus)?"rejected":"unknown",category,detail;boolean known=false;JSONArray missing=new JSONArray(),reported=new JSONArray();
    if(status.equals("rejected")){category="detector-service-rejected";detail="检测服务已拒绝本次检查；本项未覆盖，服务状态不代表原生指纹保护失败。";}
    else if(status.equals("unknown")){category="detector-service-status-unknown";detail="检测服务返回了未识别的状态；本项未覆盖，没有据此判断哪些请求已经到达。";}
    else{
      Set<String> found=server.opt("nonce") instanceof String&&Boolean.FALSE.equals(server.opt("credentialObserved"))?pendingSources(server):null;
      if(found==null){category="detector-source-records-unusable";detail="服务端待齐记录的字段不完整或互相矛盾，无法可靠区分请求阶段；未将来源标签当作实际到达证明。";}
      else{
        known=true;StringBuilder labels=new StringBuilder();category="request-sources-pending";
        for(String source:Arrays.asList("document","worker-script","worker-fetch")){
          if(found.contains(source))reported.put(source);else{missing.put(source);if(labels.length()>0)labels.append("、");labels.append(source.equals("document")?"主文档记录":source.equals("worker-script")?"Worker 脚本请求":"Worker fetch 请求");}
        }
        if(missing.length()==0)detail="服务端已报告三类字段完整的来源记录，但状态仍为 pending；尚未就绪，本项保持未覆盖。";
        else{String first=missing.optString(0);category=first.equals("document")?"request-document-missing":first.equals("worker-script")?"request-worker-script-missing":"request-worker-fetch-missing";detail="服务端尚未收齐请求，缺少"+labels+"；本项保持未覆盖，可稍后重新检查。";}
      }
    }
    JSONObject result=uncovered(nonce,endpoint,detail);try{result.put("errorCategory",category).put("serviceStatus",status).put("sourcePresenceKnown",known).put("reportedSources",reported).put("missingSources",missing).put("diagnosticOnly",true);}catch(JSONException ignored){}return result;
  }
  static JSONObject evaluate(JSONObject browser,JSONObject server,JSONObject expected,String nonce,String endpoint,boolean fresh){
    if(!fresh)return uncovered(nonce,endpoint,"检查期间环境、页面或连接发生变化，结果已作废");
    if(!nonce.matches("[0-9a-f]{32}")||server==null||!(server.opt("schema") instanceof Number)||server.optDouble("schema")!=1||!PROTOCOL.equals(server.optString("protocol"))||!nonce.equals(server.optString("nonce")))return uncovered(nonce,endpoint,"未取得与本次随机标识一致的独立服务端记录");
    if(!(server.opt("credentialObserved") instanceof Boolean))return uncovered(nonce,endpoint,"服务端没有明确报告凭据头观测状态，结果未覆盖");
    if(server.optBoolean("credentialObserved"))return J.obj("schema",1,"nonce",nonce,"endpoint",endpoint,"status","issue","source","controlled-top-level-document","rows",J.arr(J.obj("key","request-identity","name","真实请求身份对照","state","issue","detail","检测服务报告收到凭据或来源标记；本次结果未作为一致性通过，未保存其内容")),"credentialObserved",true,"fullDesktopUaConsistency",false,"fingerprintTemplateAcceptance",false);
    if(!"ready".equals(server.optString("status")))return notReady(server,nonce,endpoint);
    JSONArray raw=server.optJSONArray("events");Map<String,JSONObject> events=new HashMap<>();JSONArray safeEvents=new JSONArray();
    if(raw==null||raw.length()<3||raw.length()>12)return uncovered(nonce,endpoint,"服务端记录数量不完整或超出范围");
    for(int i=0;i<raw.length();i++){
      JSONObject event=raw.optJSONObject(i);if(event==null||!(event.opt("index") instanceof Number)||event.optDouble("index")!=i+1||!"GET".equals(event.optString("method")))return uncovered(nonce,endpoint,"服务端记录序列或请求方法无效");
      String source=event.optString("source");String path=source.equals("document")?PATH+"document":source.equals("worker-script")?PATH+"worker.js":source.equals("worker-fetch")?PATH+"observe":source.equals("control-result")?PATH+"result":"";
      JSONObject headers=event.optJSONObject("headers"),peer=event.optJSONObject("peer");
      if(path.isEmpty()||!path.equals(event.optString("path"))||events.containsKey(source)||headers==null||peer==null||!text(headers,"userAgent",2048)||!text(peer,"address",128)||!address(peer.optString("address"))||!"socket-peer".equals(peer.optString("source"))||!(headers.opt("acceptLanguage") instanceof String)||!(headers.opt("secFetchDest") instanceof String)||headers.optString("acceptLanguage").length()>1024||headers.optString("secFetchDest").length()>64)return uncovered(nonce,endpoint,"服务端来源、路径或字段不完整；不采用部分记录推断一致");
      JSONObject sensitive=event.optJSONObject("sensitiveHeaders");if(sensitive==null)return uncovered(nonce,endpoint,"服务端缺少逐请求凭据头观测标记");
      for(String field:Arrays.asList("cookie","authorization","proxyAuthorization","referer","origin"))if(!Boolean.FALSE.equals(sensitive.opt(field)))return uncovered(nonce,endpoint,"服务端逐请求凭据标记缺失、矛盾或已观察到凭据，本次未通过");
      JSONObject sanitized=J.obj("index",i+1,"source",source,"method","GET","path",path,"headers",J.obj("userAgent",headers.optString("userAgent"),"acceptLanguage",headers.optString("acceptLanguage"),"secFetchDest",headers.optString("secFetchDest")),"peer",J.obj("address",peer.optString("address"),"source","socket-peer"));events.put(source,sanitized);safeEvents.put(sanitized);
    }
    if(!events.keySet().containsAll(Arrays.asList("document","worker-script","worker-fetch")))return uncovered(nonce,endpoint,"检测文档或 Worker 的独立请求记录缺失");
    JSONObject document=events.get("document"),script=events.get("worker-script"),worker=events.get("worker-fetch");
    if(!"document".equals(document.optJSONObject("headers").optString("secFetchDest"))||!"worker".equals(script.optJSONObject("headers").optString("secFetchDest"))||!"empty".equals(worker.optJSONObject("headers").optString("secFetchDest")))return uncovered(nonce,endpoint,"没有取得文档与 Worker 脚本的请求目的标记，来源未确认");
    if(browser==null||!(browser.opt("schema") instanceof Number)||browser.optDouble("schema")!=1||!nonce.equals(browser.optString("nonce"))||!"complete".equals(browser.optString("status"))||!"controlled-top-level-document".equals(browser.optString("source"))||!js(browser.optJSONObject("document"))||!js(browser.optJSONObject("worker")))return uncovered(nonce,endpoint,"独立服务端记录已到达，但检测页或 Worker 的 JavaScript 观测尚未完整取得");
    JSONObject documentJs=browser.optJSONObject("document"),workerJs=browser.optJSONObject("worker"),docHeaders=document.optJSONObject("headers"),scriptHeaders=script.optJSONObject("headers"),workerHeaders=worker.optJSONObject("headers"),languageSemantics=new JSONObject();JSONArray rows=new JSONArray();
    boolean scriptUa=docHeaders.optString("userAgent").equals(scriptHeaders.optString("userAgent"));
    row(rows,"request-worker-script-ua","Worker 脚本下载 HTTP UA 与主文档对照",scriptUa?"verified":"issue",scriptUa?"服务端记录的脚本下载 UA 与本次主文档 HTTP UA 相同；脚本下载没有独立 JavaScript 身份，不能据此推断 Worker 内部 fetch 的 UA":"服务端记录的脚本下载 UA 与本次主文档 HTTP UA 不同；原值分别保留，Worker 内部 fetch 另行核对");
    JSONObject scriptLanguage=RequestIdentityLanguages.compareHeaders(docHeaders.optString("acceptLanguage"),scriptHeaders.optString("acceptLanguage"));try{languageSemantics.put("workerScriptHttp",scriptLanguage);}catch(JSONException ignored){}
    row(rows,"request-worker-script-language","Worker 脚本下载 HTTP 语言与主文档对照",scriptLanguage.optString("state"),RequestIdentityLanguages.detail(scriptLanguage));
    for(String source:Arrays.asList("document","worker")){
      JSONObject javascript=source.equals("document")?documentJs:workerJs,headers=source.equals("document")?docHeaders:workerHeaders;
      boolean ua=javascript.optString("ua").equals(headers.optString("userAgent"));String primary=language(headers.optString("acceptLanguage"));boolean haveLanguage=!primary.isEmpty();boolean locale=primary.equalsIgnoreCase(javascript.optString("language"));
      row(rows,"request-"+source+"-ua",source.equals("document")?"检测页主文档真实 UA":"Dedicated Worker fetch 请求 UA",ua?"verified":"issue",ua?"服务端独立记录的 User-Agent 与该执行环境 JavaScript 值一致；仅覆盖本次检测请求":"服务端收到的 User-Agent 与该执行环境 JavaScript 值不同，已保留差异");
      row(rows,"request-"+source+"-language",source.equals("document")?"检测页主文档真实语言":"Dedicated Worker fetch 请求语言",!haveLanguage?"uncovered":locale?"verified":"issue",!haveLanguage?"该请求没有可对照的 Accept-Language":"服务端 Accept-Language 第一语言与该执行环境 JavaScript "+(locale?"一致":"不同")+"；完整原值分别保留");
      JSONObject semantic=RequestIdentityLanguages.compare(headers.optString("acceptLanguage"),javascript.optJSONArray("languages"),javascript.optString("language"));
      try{languageSemantics.put(source,semantic);}catch(JSONException ignored){}
      row(rows,"request-"+source+"-language-list",source.equals("document")?"检测页完整语言顺序":"Dedicated Worker fetch 完整语言顺序",semantic.optString("state"),RequestIdentityLanguages.detail(semantic));
    }
    boolean sameUa=docHeaders.optString("userAgent").equals(workerHeaders.optString("userAgent")),sameLanguage=docHeaders.optString("acceptLanguage").equals(workerHeaders.optString("acceptLanguage"));
    boolean bothLanguages=!docHeaders.optString("acceptLanguage").isEmpty()&&!workerHeaders.optString("acceptLanguage").isEmpty();
    row(rows,"request-context-headers","主文档与 Worker fetch 请求头对照",!sameUa?"issue":!bothLanguages?"uncovered":sameLanguage?"verified":"issue",!bothLanguages&&sameUa?"本次两个 UA 已相同，但至少一个 Accept-Language 缺失，完整请求头对照未覆盖":sameUa&&sameLanguage?"本次检测文档与 Worker fetch 的服务端 UA、Accept-Language 原值相同；脚本下载另列，不代表其他网站或全部 Worker":"本次检测文档与 Worker fetch 的服务端 UA 或 Accept-Language 原值不同；脚本下载另列，差异不自动等同于泄漏");
    JSONObject headerSemantic=RequestIdentityLanguages.compareHeaders(docHeaders.optString("acceptLanguage"),workerHeaders.optString("acceptLanguage"));try{languageSemantics.put("httpContexts",headerSemantic);}catch(JSONException ignored){}
    row(rows,"request-context-language-semantics","主文档与 Worker fetch 语言权重语义",headerSemantic.optString("state"),RequestIdentityLanguages.detail(headerSemantic));
    boolean nativeUa=text(expected,"ua",2048),nativeSame=nativeUa&&expected.optString("ua").equals(docHeaders.optString("userAgent"))&&expected.optString("ua").equals(workerHeaders.optString("userAgent"));
    row(rows,"request-native-ua","主文档／Worker fetch 与原生 UA 请求",!nativeUa?"uncovered":nativeSame?"verified":"issue",!nativeUa?"未取得当前原生 UA 请求值":nativeSame?"本次主文档与 Worker fetch 的 UA 均符合原生配置请求值；脚本下载另列，不证明其他指纹保护":"本次主文档或 Worker fetch 的 UA 与原生配置请求不同，完整差异可查看");
    String nativeLanguage=expected.optString("language");boolean haveNativeLanguage=text(expected,"language",128)&&bothLanguages;
    boolean nativeLanguageSame=haveNativeLanguage&&language(docHeaders.optString("acceptLanguage")).equalsIgnoreCase(nativeLanguage)&&language(workerHeaders.optString("acceptLanguage")).equalsIgnoreCase(nativeLanguage);
    row(rows,"request-native-language","请求语言与原生配置请求",!haveNativeLanguage?"uncovered":nativeLanguageSame?"verified":"issue",!haveNativeLanguage?"原生请求语言或两个 HTTP 语言值未完整取得":nativeLanguageSame?"本次两个请求的首选语言符合 SDK 规范化请求预测；不是全部语言或指纹保护证明":"至少一个请求首选语言与 SDK 规范化请求预测不同；原生强化可能继续标准化，差异已保留");
    for(String source:Arrays.asList("document","worker")){JSONObject headers=source.equals("document")?docHeaders:workerHeaders,semantic=RequestIdentityLanguages.compare(headers.optString("acceptLanguage"),expected.optJSONArray("languages"),nativeLanguage);try{languageSemantics.put("native"+(source.equals("document")?"Document":"Worker"),semantic);}catch(JSONException ignored){}row(rows,"request-native-"+source+"-language-list",source.equals("document")?"检测页完整语言与原生请求":"Worker 完整语言与原生请求",semantic.optString("state"),RequestIdentityLanguages.detail(semantic));}
    String docPeer=document.optJSONObject("peer").optString("address"),workerPeer=worker.optJSONObject("peer").optString("address");
    row(rows,"request-peer","服务端连接对端对照",docPeer.equals(workerPeer)?"verified":"issue",docPeer.equals(workerPeer)?"检测服务观察到两个请求的 socket 对端相同；使用反向代理时该地址不等于真实出口":"检测服务观察到两个请求的 socket 对端不同；需结合检测服务部署方式核对，不能直接认定泄漏");
    JSONObject cleanBrowser=J.obj("source","controlled-top-level-document","document",J.obj("ua",documentJs.optString("ua"),"language",documentJs.optString("language"),"languages",documentJs.optJSONArray("languages")),"worker",J.obj("ua",workerJs.optString("ua"),"language",workerJs.optString("language"),"languages",workerJs.optJSONArray("languages")));
    JSONObject frame=frameObservation(browser,expected,nonce,endpoint);if(frame!=null){try{cleanBrowser.put("crossOriginFrame",frame);}catch(JSONException ignored){}JSONObject apis=frame.optJSONObject("apiChecks"),operations=apis==null?null:apis.optJSONObject("probes");if(!"complete".equals(frame.optString("status")))row(rows,"request-cross-origin-frame","受控跨源 iframe 图形检查","uncovered","受控第二来源未取得完整结果："+frame.optString("reason")+"；未把超时、CSP 或缺失当作保护通过");else for(String operation:Arrays.asList("canvas","webgl")){JSONObject value=operations.optJSONObject(operation);row(rows,"request-cross-origin-frame-"+operation,"受控跨源 iframe "+operation,value.optString("state"),"独立来源 "+frame.optString("origin")+"："+value.optString("reason")+"；不要求不同执行环境哈希相同，不表示保护已通过");}}
    for(String key:Arrays.asList("shared-worker","service-worker"))row(rows,"request-"+key,key.equals("shared-worker")?"Shared Worker 覆盖":"Service Worker 覆盖","uncovered","本客户端未运行这类请求、缓存或生命周期检查；没有注册或清理站点 Worker，不能依据检测服务就绪或接口存在认定保护已验证");
    boolean issue=false;for(int i=0;i<rows.length();i++)issue|="issue".equals(rows.optJSONObject(i).optString("state"));
    return J.obj("schema",1,"nonce",nonce,"endpoint",endpoint,"status",issue?"issue":"observed","source","controlled-top-level-document","rows",rows,"browser",cleanBrowser,"server",J.obj("schema",1,"protocol",PROTOCOL,"nonce",nonce,"events",safeEvents,"credentialObserved",false),"expected",J.obj("templateId",expected.optString("templateId"),"ua",expected.optString("ua"),"language",expected.optString("language"),"languages",expected.optJSONArray("languages"),"environmentId",expected.optString("environmentId"),"environmentGeneration",expected.optInt("environmentGeneration"),"configurationRevision",expected.optLong("configurationRevision")),"languageSemantics",languageSemantics,"crossOriginFrameRequested",frame!=null,"backgroundCoverage",backgroundCoverage(null),"fullDesktopUaConsistency",false,"fingerprintTemplateAcceptance",false,"controlSource","extension-background-control","scope","用户选定 HTTPS 检测页的真正主文档与 Dedicated Worker；可信扩展后台独立读取服务端记录，和 JavaScript 自报分开。明确请求的第二来源 iframe 图形结果单独列出，不作跨环境哈希等同判断。信任所配置检测服务，不能代表 ChatGPT 官网、其他跨源页面或其他网络协议");
  }
}
