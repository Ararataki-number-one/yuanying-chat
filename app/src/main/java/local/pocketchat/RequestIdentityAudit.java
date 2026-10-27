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
  static String url(String endpoint,String kind,String nonce){if(endpoint(endpoint).isEmpty()||!nonce.matches("[0-9a-f]{32}")||!Arrays.asList("document","result").contains(kind))throw new IllegalArgumentException("Invalid controlled diagnostic URL");return endpoint(endpoint)+kind+"?nonce="+nonce;}
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
  static void row(JSONArray rows,String key,String name,String state,String detail){rows.put(J.obj("key",key,"name",name,"state",state,"detail",detail));}
  static JSONObject uncovered(String nonce,String endpoint,String reason){return J.obj("schema",1,"nonce",nonce,"endpoint",endpoint,"status","uncovered","source","controlled-top-level-document","rows",J.arr(J.obj("key","request-identity","name","真实请求身份对照","state","uncovered","detail",reason)),"fullDesktopUaConsistency",false,"fingerprintTemplateAcceptance",false,"scope","仅对应用户选择的受控 HTTPS 检测页；不代表 ChatGPT 官网或全部请求路径");}
  static JSONObject evaluate(JSONObject browser,JSONObject server,JSONObject expected,String nonce,String endpoint,boolean fresh){
    if(!fresh)return uncovered(nonce,endpoint,"检查期间环境、页面或连接发生变化，结果已作废");
    if(!nonce.matches("[0-9a-f]{32}")||server==null||!(server.opt("schema") instanceof Number)||server.optDouble("schema")!=1||!PROTOCOL.equals(server.optString("protocol"))||!nonce.equals(server.optString("nonce")))return uncovered(nonce,endpoint,"未取得与本次随机标识一致的独立服务端记录");
    if(!(server.opt("credentialObserved") instanceof Boolean))return uncovered(nonce,endpoint,"服务端没有明确报告凭据头观测状态，结果未覆盖");
    if(server.optBoolean("credentialObserved"))return J.obj("schema",1,"nonce",nonce,"endpoint",endpoint,"status","issue","source","controlled-top-level-document","rows",J.arr(J.obj("key","request-identity","name","真实请求身份对照","state","issue","detail","检测服务报告收到凭据或来源标记；本次结果未作为一致性通过，未保存其内容")),"credentialObserved",true,"fullDesktopUaConsistency",false,"fingerprintTemplateAcceptance",false);
    if(!"ready".equals(server.optString("status")))return uncovered(nonce,endpoint,"服务端尚未收齐检测文档和 Dedicated Worker 请求；没有把失败当作身份一致");
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
    JSONObject documentJs=browser.optJSONObject("document"),workerJs=browser.optJSONObject("worker"),docHeaders=document.optJSONObject("headers"),workerHeaders=worker.optJSONObject("headers");JSONArray rows=new JSONArray();
    for(String source:Arrays.asList("document","worker")){
      JSONObject javascript=source.equals("document")?documentJs:workerJs,headers=source.equals("document")?docHeaders:workerHeaders;
      boolean ua=javascript.optString("ua").equals(headers.optString("userAgent"));String primary=language(headers.optString("acceptLanguage"));boolean haveLanguage=!primary.isEmpty();boolean locale=primary.equalsIgnoreCase(javascript.optString("language"));
      row(rows,"request-"+source+"-ua",source.equals("document")?"检测页主文档真实 UA":"Dedicated Worker 真实请求 UA",ua?"verified":"issue",ua?"服务端独立记录的 User-Agent 与该执行环境 JavaScript 值一致；仅覆盖本次检测请求":"服务端收到的 User-Agent 与该执行环境 JavaScript 值不同，已保留差异");
      row(rows,"request-"+source+"-language",source.equals("document")?"检测页主文档真实语言":"Dedicated Worker 真实请求语言",!haveLanguage?"uncovered":locale?"verified":"issue",!haveLanguage?"该请求没有可对照的 Accept-Language":"服务端 Accept-Language 第一语言与该执行环境 JavaScript "+(locale?"一致":"不同")+"；完整原值分别保留");
    }
    boolean sameUa=docHeaders.optString("userAgent").equals(workerHeaders.optString("userAgent")),sameLanguage=docHeaders.optString("acceptLanguage").equals(workerHeaders.optString("acceptLanguage"));
    boolean bothLanguages=!docHeaders.optString("acceptLanguage").isEmpty()&&!workerHeaders.optString("acceptLanguage").isEmpty();
    row(rows,"request-context-headers","文档与 Worker 请求头对照",!sameUa?"issue":!bothLanguages?"uncovered":sameLanguage?"verified":"issue",!bothLanguages&&sameUa?"本次两个 UA 已相同，但至少一个 Accept-Language 缺失，完整请求头对照未覆盖":sameUa&&sameLanguage?"本次检测文档与 Worker 的服务端 UA、Accept-Language 原值相同；不代表其他网站或全部 Worker":"本次检测文档与 Worker 的服务端 UA 或 Accept-Language 原值不同；差异不自动等同于泄漏");
    boolean nativeUa=text(expected,"ua",2048),nativeSame=nativeUa&&expected.optString("ua").equals(docHeaders.optString("userAgent"))&&expected.optString("ua").equals(workerHeaders.optString("userAgent"));
    row(rows,"request-native-ua","请求 UA 与原生模板请求",!nativeUa?"uncovered":nativeSame?"verified":"issue",!nativeUa?"未取得当前原生 UA 请求值":nativeSame?"本次两个请求的 UA 均符合原生配置请求值；不证明其他指纹保护":"本次至少一个请求 UA 与原生配置请求不同，完整差异可查看");
    String nativeLanguage=expected.optString("language");boolean haveNativeLanguage=text(expected,"language",128)&&bothLanguages;
    boolean nativeLanguageSame=haveNativeLanguage&&language(docHeaders.optString("acceptLanguage")).equalsIgnoreCase(nativeLanguage)&&language(workerHeaders.optString("acceptLanguage")).equalsIgnoreCase(nativeLanguage);
    row(rows,"request-native-language","请求语言与原生配置请求",!haveNativeLanguage?"uncovered":nativeLanguageSame?"verified":"issue",!haveNativeLanguage?"原生请求语言或两个 HTTP 语言值未完整取得":nativeLanguageSame?"本次两个请求的首选语言符合 SDK 规范化请求预测；不是全部语言或指纹保护证明":"至少一个请求首选语言与 SDK 规范化请求预测不同；原生强化可能继续标准化，差异已保留");
    String docPeer=document.optJSONObject("peer").optString("address"),workerPeer=worker.optJSONObject("peer").optString("address");
    row(rows,"request-peer","服务端连接对端对照",docPeer.equals(workerPeer)?"verified":"issue",docPeer.equals(workerPeer)?"检测服务观察到两个请求的 socket 对端相同；使用反向代理时该地址不等于真实出口":"检测服务观察到两个请求的 socket 对端不同；需结合检测服务部署方式核对，不能直接认定泄漏");
    JSONObject cleanBrowser=J.obj("source","controlled-top-level-document","document",J.obj("ua",documentJs.optString("ua"),"language",documentJs.optString("language"),"languages",documentJs.optJSONArray("languages")),"worker",J.obj("ua",workerJs.optString("ua"),"language",workerJs.optString("language"),"languages",workerJs.optJSONArray("languages")));
    boolean issue=false;for(int i=0;i<rows.length();i++)issue|="issue".equals(rows.optJSONObject(i).optString("state"));
    return J.obj("schema",1,"nonce",nonce,"endpoint",endpoint,"status",issue?"issue":"observed","source","controlled-top-level-document","rows",rows,"browser",cleanBrowser,"server",J.obj("schema",1,"protocol",PROTOCOL,"nonce",nonce,"events",safeEvents,"credentialObserved",false),"expected",J.obj("templateId",expected.optString("templateId"),"ua",expected.optString("ua"),"language",expected.optString("language"),"environmentId",expected.optString("environmentId"),"environmentGeneration",expected.optInt("environmentGeneration"),"configurationRevision",expected.optLong("configurationRevision")),"fullDesktopUaConsistency",false,"fingerprintTemplateAcceptance",false,"controlSource","extension-background-control","scope","用户选定 HTTPS 检测页的真正主文档与 Dedicated Worker；可信扩展后台独立读取服务端记录，和 JavaScript 自报分开。信任所配置检测服务，不能代表 ChatGPT 官网、跨源页面或其他网络协议");
  }
}
