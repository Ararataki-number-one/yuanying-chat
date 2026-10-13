package local.pocketchat;

import android.content.*;
import android.os.*;
import android.webkit.*;
import android.net.Uri;
import org.json.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.*;
import java.util.concurrent.*;

/** Per-environment, encrypted local evidence. No telemetry or account-page navigation. */
class EnvironmentAudit {
  static final String ORIGIN="https://appassets.androidplatform.net/environment-check/";
  static final String IPV4="https://api.ipify.org/?format=json",IPV6="https://api6.ipify.org/?format=json",HEADERS="https://httpbin.org/headers";
  final ChatSession session;final SecretStore store;final ExecutorService worker=Executors.newSingleThreadExecutor(),closer=Executors.newSingleThreadExecutor();
  JSONObject baseline=new JSONObject(),report=new JSONObject(),observed=new JSONObject(),initial=new JSONObject();JSONArray changes=new JSONArray();String storageIssue="",lastError="";
  volatile boolean running;boolean networkRun,webDone,nativeDone,geckoRun;String auditUrl="";long auditNavigation;volatile long serial;long epoch,deadline,lastRefresh,identityAppliedRevision;String stamp="",policy="";JSONObject sample=new JSONObject(),nativeResult=new JSONObject();Runnable completed;Future<?> nativeWork;volatile HttpURLConnection connection;
  EnvironmentAudit(ChatSession s){session=s;store=new SecretStore(s.context);try{byte[] bytes=store.get("environment-audit");if(bytes!=null){JSONObject saved=J.parse(new String(bytes,StandardCharsets.UTF_8));baseline=saved.optJSONObject("baseline");report=saved.optJSONObject("report");observed=saved.optJSONObject("observed");if(baseline==null)baseline=new JSONObject();if(report==null)report=new JSONObject();if(observed==null)observed=new JSONObject();}}catch(Exception e){storageIssue="本地加密基线读取失败，尚未覆盖旧记录";}refresh(true);}
  static String hash(String value){try{return NativeNetwork.hash(value);}catch(Exception e){throw new IllegalStateException("Local SHA-256 unavailable",e);}}
  static String packageVersion(){return GeckoWebView.VERSION.replace("GeckoView ","");}
  JSONObject snapshotFields(){JSONObject o=J.obj("level",session.privacy.level(),"webview",GeckoWebView.VERSION,"android",Build.VERSION.RELEASE,"uaHash",hash(session.web.getSettings().getUserAgentString()),"timezone",TimeZone.getDefault().getID(),"locale",Locale.getDefault().toLanguageTag(),"networkMode",session.prefs.getString("networkMode","external"),"requireVpn",session.prefs.getBoolean("requireExternalVpn",true),"early",session.privacy.earlyInstalled,"workerGate",session.guard.workerProtection);
    try{NativeNetwork n=NativeNetwork.get(session.context);String ip=session.internalNetwork()&&n.lastVerified>0?n.exitIp:observed.optString("ipv4");if(AuditReport.v4(ip)&&(session.internalNetwork()||observed.optString("route").equals(routeStamp())))o.put("exitHash",hash(ip));}catch(Exception ignored){}return o;
  }
  JSONObject snapshot(){JSONObject current=snapshotFields();try{current.put("routeHash",hash(session.internalNetwork()?store.settings().toString():session.prefs.getString("proxy","")));}catch(Exception ignored){}return current;}
  static String label(String key){switch(key){case "level":return "保护等级";case "webview":return "浏览器内核版本";case "android":return "安卓版本";case "uaHash":return "浏览器 UA 设置";case "timezone":return "手机时区";case "locale":return "手机语言";case "networkMode":return "网络模式";case "requireVpn":return "VPN 断开保护";case "early":return "加载前保护能力";case "workerGate":return "后台请求保护能力";case "routeHash":return "网络配置";case "exitHash":return "已观察的 IPv4 出口";default:return key;}}
  static JSONArray differences(JSONObject old,JSONObject now){JSONArray out=new JSONArray();Iterator<String> keys=now.keys();while(keys.hasNext()){String key=keys.next();if(old.has(key)&&!Objects.equals(old.opt(key),now.opt(key)))out.put(J.obj("key",key,"name",label(key)));}return out;}
  long refreshTicket;boolean refreshQueued;volatile long saveTicket;final Object saveGate=new Object();
  void refresh(boolean force){
    long now=SystemClock.elapsedRealtime();
    if(force){refreshTicket++;refreshQueued=false;lastRefresh=now;applySnapshot(snapshot(),false);return;}
    if(running||refreshQueued||now-lastRefresh<5000)return;
    lastRefresh=now;refreshQueued=true;long ticket=++refreshTicket,connection=session.connectionEpoch;
    JSONObject current=snapshotFields();String fields=current.toString(),route=routeStamp(),proxy=session.prefs.getString("proxy","");boolean internal=session.internalNetwork();
    worker.execute(()->{
      try{current.put("routeHash",hash(internal?store.settings().toString():proxy));}catch(Exception ignored){}
      session.handler.post(()->{
        if(ticket!=refreshTicket)return;refreshQueued=false;
        if(session.deleted||connection!=session.connectionEpoch||internal!=session.internalNetwork()||!route.equals(routeStamp())||!fields.equals(snapshotFields().toString()))return;
        applySnapshot(current,true);
      });
    });
  }
  void applySnapshot(JSONObject current,boolean background){
    boolean persist=false;
    if(baseline.length()==0&&storageIssue.isEmpty()&&session.prefs.getBoolean("networkConfigured",false)){baseline=current;persist=true;}
    else if(baseline.length()>0){Iterator<String> keys=current.keys();while(keys.hasNext()){String key=keys.next();if(!baseline.has(key)){try{baseline.put(key,current.get(key));persist=true;}catch(Exception ignored){}}}persist&=storageIssue.isEmpty();}
    changes=differences(baseline,current);
    if(persist){if(background)saveLater();else save();}
  }
  boolean hasChanges(){return changes.length()>0;}
  void acceptBaseline(){if(running)return;refreshTicket++;refreshQueued=false;JSONObject old=baseline;JSONArray oldChanges=changes;baseline=snapshot();changes=new JSONArray();if(!save()){baseline=old;changes=oldChanges;}}
  byte[] savedBytes(){return J.obj("baseline",baseline,"report",report,"observed",observed).toString().getBytes(StandardCharsets.UTF_8);}
  boolean save(){long ticket=++saveTicket;byte[] bytes=savedBytes();synchronized(saveGate){if(ticket!=saveTicket)return false;try{store.put("environment-audit",bytes);storageIssue="";return true;}catch(Exception e){storageIssue="本地加密保存失败；旧基线未确认更新";return false;}}}
  void saveLater(){
    long ticket=++saveTicket;byte[] bytes=savedBytes();
    worker.execute(()->{String issue="";
      synchronized(saveGate){if(ticket!=saveTicket)return;try{store.put("environment-audit",bytes);}catch(Exception e){issue="本地加密保存失败；旧基线未确认更新";}}
      String result=issue;session.handler.post(()->{if(ticket==saveTicket)storageIssue=result;});
    });
  }
  String routeStamp(){String route=session.internalNetwork()?NativeNetwork.get(session.context).token:session.prefs.getString("proxy","");return hash(session.prefs.getString("networkMode","external")+"|"+route+"|"+session.prefs.getBoolean("requireExternalVpn",true));}
  boolean current(long id){return running&&id==serial;}
  String policyStamp(){GeckoSettings settings=session.web.getSettings();return hash(GeckoWebView.VERSION+"|"+session.privacy.level()+"|"+settings.desktop+"|"+settings.getUserAgentString()+"|"+Arrays.toString(settings.requestedLocales)+"|"+settings.policyAcknowledged+"|"+session.web.identityPolicyRevision+"|"+TimeZone.getDefault().getID()+"|"+Locale.getDefault().toLanguageTag());}
  boolean fresh(){return running&&(!geckoRun||(auditNavigation==session.navigationEpoch&&auditUrl.equals(session.web.getUrl())))&&epoch==session.connectionEpoch&&stamp.equals(routeStamp())&&policy.equals(policyStamp())&&(!networkRun||session.networkReady&&session.guard.allowed());}
  JSONObject expected(){NativeNetwork n=NativeNetwork.get(session.context);int major;try{major=Integer.parseInt((packageVersion()).split("\\.")[0]);}catch(Exception e){major=-1;}return J.obj("engine","gecko","ua",session.web.getSettings().getUserAgentString(),"major",major,"level",session.privacy.level(),"offset",-TimeZone.getDefault().getOffset(System.currentTimeMillis())/60000,"timezoneStrategy",session.privacy.level()>=2?"native-standardized":"system","language",session.web.identityLanguage(),"requestedLocales",new JSONArray(Arrays.asList(session.web.getSettings().requestedLocales)),"expectedSdkLocales",new JSONArray(Arrays.asList(session.web.getSettings().expectedSdkLocales)),"languageSource","sdk157-language-region-prediction-not-content-ack","rfpAcknowledged",session.web.getSettings().rfpAcknowledged,"exitIp",session.internalNetwork()&&n.lastVerified>0?n.exitIp:"");}
  boolean start(boolean network,Runnable done){if(running)return false;lastError="";if(network&&ProfileUi.working(session)){lastError="有未完成回复、上传或下载，请结束后再检查网络出口";return false;}if(network&&(!session.networkReady||!session.guard.allowed())){lastError="当前连接尚未受保护，请先恢复连接；没有发出检测请求";return false;}
    geckoRun=GeckoWebView.active(session.web);if(geckoRun&&!session.web.hasVisibleDocument()){lastError="请等当前网页显示后再检查";return false;}auditUrl=session.web.getUrl();auditNavigation=session.navigationEpoch;running=true;networkRun=network;completed=done;sample=new JSONObject();nativeResult=new JSONObject();webDone=false;nativeDone=!network;initial=expected();identityAppliedRevision=session.identityAuditAppliedRevision();epoch=session.connectionEpoch;stamp=routeStamp();policy=policyStamp();deadline=SystemClock.elapsedRealtime()+14000;long id=++serial;session.updateBrowserActivity();
    try{if(geckoRun){
      session.web.runEnvironmentAudit(J.obj("id",String.valueOf(id),"network",network),raw->{if(!current(id))return;JSONObject result=raw!=null&&raw.length()<=64000?J.parse(raw):new JSONObject();if(result.optString("id").equals(String.valueOf(id)))sample=result;webDone=true;finishIfReady(id);});
    }
      if(network)nativeWork=worker.submit(()->{JSONObject result;try{result=queryNative(id);}catch(Exception e){result=J.obj("error","No verifiable response");}JSONObject value=result;session.handler.post(()->{if(!current(id))return;nativeResult=value;nativeDone=true;finishIfReady(id);});});
      session.handler.postDelayed(()->{if(current(id)){webDone=nativeDone=true;finishIfReady(id);}},14500);return true;
    }catch(Exception e){webDone=nativeDone=true;lastError="本机检查页面无法启动";finishIfReady(id);return true;}
  }
  WebResourceResponse resource(WebResourceRequest request){String url=request.getUrl().toString();if(networkRun&&running&&fresh()&&(url.equals(IPV4)||url.equals(IPV6)||url.equals(HEADERS)))return null;return BrowserNetworkGuard.denied();}
  void poll(long id){if(!current(id))return;android.webkit.ValueCallback<String> callback=raw->{if(!current(id))return;JSONObject result=raw!=null&&raw.length()<64000?J.parse(raw):new JSONObject();if(result.optString("id").equals(String.valueOf(id))){sample=result;webDone=true;finishIfReady(id);}else if(SystemClock.elapsedRealtime()<deadline)session.handler.postDelayed(()->poll(id),100);else{webDone=true;finishIfReady(id);}};session.web.evaluateJavascript("window.__pocketAuditResult||null",callback);}
  Proxy proxy()throws Exception{if(!session.guard.allowed())throw new IOException("Connection unprotected");String value=session.internalNetwork()?NativeNetwork.get(session.context).proxy():session.prefs.getString("proxy","");if(value.isEmpty())return Proxy.NO_PROXY;if(!MainActivity.validProxy(value)||value.startsWith("https://"))throw new IOException("Native proxy verification unsupported");Uri uri=Uri.parse(value);return new Proxy(value.startsWith("socks:")?Proxy.Type.SOCKS:Proxy.Type.HTTP,new InetSocketAddress(uri.getHost(),uri.getPort()));}
  HttpURLConnection open(URL url,Proxy proxy)throws IOException{return (HttpURLConnection)url.openConnection(proxy);}
  JSONObject queryNative(long id)throws Exception{if(!current(id)||!fresh())throw new IOException("Connection changed");HttpURLConnection c=open(new URL(IPV4),proxy());connection=c;try{if(!current(id)||!fresh())throw new IOException("Check cancelled");c.setInstanceFollowRedirects(false);c.setConnectTimeout(5000);c.setReadTimeout(6500);c.setRequestProperty("User-Agent",initial.optString("ua"));c.setRequestProperty("Accept","application/json");c.setUseCaches(false);if(c.getResponseCode()!=200||!current(id)||!fresh())throw new IOException("Unverified response");try(InputStream in=c.getInputStream()){JSONObject data=J.parse(J.text(in,4096));return AuditReport.v4(data.optString("ip"))?J.obj("ip",data.optString("ip")):J.obj("error","Invalid response");}}finally{c.disconnect();if(connection==c)connection=null;}}
  void finishIfReady(long id){if(!current(id)||!webDone||!nativeDone)return;boolean fresh=fresh();report=AuditReport.build(sample,nativeResult,initial,networkRun,fresh);try{report.put("identityAppliedRevision",identityAppliedRevision);report.put("policy",policy);report.put("route",stamp);}catch(Exception ignored){}if(networkRun&&fresh){JSONObject net=sample.optJSONObject("network"),browser=net==null?null:net.optJSONObject("ipv4");String ip=AuditReport.ip(browser);if(AuditReport.v4(ip)&&ip.equals(nativeResult.optString("ip")))observed=J.obj("ipv4",ip,"route",stamp);}if(fresh)session.identityObserved(report);cleanup();refresh(true);save();Runnable callback=completed;completed=null;if(callback!=null)callback.run();}
  void cancel(){if(!running)return;serial++;lastError="检查已取消，没有更新报告或环境基线";cleanup();Runnable callback=completed;completed=null;if(callback!=null)callback.run();}
  void cleanup(){if(geckoRun&&auditNavigation==session.navigationEpoch&&auditUrl.equals(session.web.getUrl()))session.web.cancelEnvironmentAudit();running=false;if(nativeWork!=null){nativeWork.cancel(true);nativeWork=null;}HttpURLConnection c=connection;connection=null;if(c!=null)closer.submit(()->c.disconnect());session.updateBrowserActivity();}
  String summary(){return summary(false);}
  String summary(boolean redact){refresh(false);StringBuilder text=new StringBuilder("当前环境：").append(Profiles.display(session.context,Profiles.slot(session.context))).append("\n环境变化：").append(hasChanges()?"需要核对 "+changes.length()+" 项":"暂无已记录的变化");for(int i=0;i<changes.length();i++)text.append("\n· ").append(changes.optJSONObject(i).optString("name")).append("与基线不同");text.append("\n正常系统更新也可能产生变化，提醒不等于账号危险。");if(!storageIssue.isEmpty())text.append("\n").append(storageIssue);if(!lastError.isEmpty())text.append("\n").append(lastError);if(running)return text.append("\n\n正在检查，当前聊天页面不会重新加载…").toString();if(report.length()==0)return text.append("\n\n尚无自检结果。浏览器检查在本机运行；网络检查由你点按后进行。").toString();if(!report.optString("policy").equals(policyStamp())||(report.optBoolean("network")&&!report.optString("route").equals(routeStamp())))text.append("\n\n当前环境已变化，下面是历史结果，请重新检查。");text.append("\n\n最近检查：").append(new SimpleDateFormat("MM-dd HH:mm:ss",Locale.getDefault()).format(new Date(report.optLong("at"))));JSONArray rows=report.optJSONArray("rows");if(rows!=null)for(int i=0;i<rows.length();i++){JSONObject r=rows.optJSONObject(i);text.append("\n\n").append(AuditReport.VERIFIED.equals(r.optString("state"))?"已验证":AuditReport.ISSUE.equals(r.optString("state"))?"发现问题":"未覆盖").append(" · ").append(r.optString("name")).append("\n").append(r.optString("detail"));}if(report.optBoolean("network")){JSONObject signals=report.optJSONObject("signals"),net=signals==null?null:signals.optJSONObject("network"),nativeIp=report.optJSONObject("native"),workerSignal=signals==null?null:signals.optJSONObject("worker");String pageIp=AuditReport.ip(net==null?null:net.optJSONObject("ipv4")),workerIp=AuditReport.ip(workerSignal==null?null:workerSignal.optJSONObject("ip")),appIp=AuditReport.ip(nativeIp),ipv6=AuditReport.ip(net==null?null:net.optJSONObject("ipv6"));text.append("\n\n本次观察到的出口（仅本机保存）\n网页 IPv4：").append(address(pageIp,redact)).append("\n后台 IPv4：").append(address(workerIp,redact)).append("\n原生 IPv4：").append(address(appIp,redact)).append("\n网页 IPv6：").append(address(ipv6,redact));}return text.append("\n\n结果只对应检查当时的指定路径，不能保证 VPN 不被识别或账号不被封。").toString();}
  static String address(String ip,boolean redact){return AuditReport.v4(ip)||AuditReport.v6(ip)?redact?"[地址已隐藏]":ip:"未取得";}
  String safeCopy(){String text=summary(true);text=text.replaceAll("(?<![0-9])(?:[0-9]{1,3}\\.){3}[0-9]{1,3}(?![0-9])","[地址已隐藏]");return text;}
}
