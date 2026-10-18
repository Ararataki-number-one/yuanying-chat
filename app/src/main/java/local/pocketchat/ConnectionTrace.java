package local.pocketchat;

import android.os.Build;
import android.os.SystemClock;
import org.json.*;
import java.util.Locale;

/** Local phase durations only; no URL, cookie, message, credential or IP logging. */
final class ConnectionTrace {
  long started,networkDone,pageStarted,visible,usable;long core=-1,subscription=-1,exit=-1,recoveryProbe=-1;
  double response=-1,dns=-1,tls=-1;String mode="",source="";
  void begin(){started=SystemClock.elapsedRealtime();networkDone=pageStarted=visible=usable=0;core=subscription=exit=recoveryProbe=-1;response=dns=tls=-1;mode="";source="";}
  void network(NativeNetwork n){networkDone=SystemClock.elapsedRealtime();if(n==null)return;core=n.startupBeganAt>=started?n.coreDuration:0;subscription=n.startupBeganAt>=started?n.providerDuration:0;exit=n.exitCheckDuration;source=core==0?"沿用内核":n.startupCached?"订阅缓存":"下载订阅";}
  void page(String method){pageStarted=SystemClock.elapsedRealtime();visible=usable=0;response=dns=tls=-1;mode=method;}
  void timing(JSONObject data){if(!data.optBoolean("ok")||!data.optBoolean("fullNavigation"))return;response=bounded(data.optDouble("responseMs",-1));dns=bounded(data.optDouble("dnsMs",-1));tls=bounded(data.optDouble("tlsMs",-1));}
  static double bounded(double n){return Double.isNaN(n)||Double.isInfinite(n)||n<0||n>600000?-1:n;}
  static String seconds(double ms){return ms<0?"尚未记录":String.format(Locale.ROOT,"%.2f 秒",ms/1000.0);}
  String text(){if(started==0&&pageStarted==0)return "尚无连接耗时记录";String text="连接耗时（本机记录）";
    if(networkDone>0&&started>0)text+="\n网络准备："+seconds(networkDone-started);
    if(core>=0)text+="\n代理内核："+(core==0?"沿用现有进程":seconds(core))+"\n订阅读取与配置："+seconds(subscription);
    if(exit>=0)text+="\n固定出口核实："+seconds(exit);
    if(recoveryProbe>=0)text+="\n现有网页连通核对："+seconds(recoveryProbe);
    if(response>=0)text+="\n网页服务响应："+seconds(response)+"\n网页 DNS / TLS："+seconds(dns)+" / "+seconds(tls);
    if(visible>0&&pageStarted>0)text+="\n首屏显示："+seconds(visible-pageStarted);
    if(usable>0&&pageStarted>0)text+="\n内容可操作："+seconds(usable-pageStarted);
    if(!mode.isEmpty())text+="\n进入方式："+mode;if(!source.isEmpty())text+="\n订阅来源："+source;
    return text+"\n\n以上是阶段耗时，不是线路带宽。缓存或复用连接时，DNS / TLS 可能为零；网页内切换不会产生完整页面请求。";
  }
  String copyText(android.content.Context context,boolean gecko){String webVersion=GeckoWebView.VERSION;return "元婴期院士 "+AppVersion.name(context)+"\nAndroid "+Build.VERSION.RELEASE+" · "+webVersion+"\n\n"+text()+routeDiagnostics(context);}
  static String windowDiagnostics(android.content.Context context,WindowNetworkState window){
    String value="元婴期院士 "+AppVersion.name(context)+"\nAndroid "+Build.VERSION.RELEASE+" · "+GeckoWebView.VERSION
      +"\n窗口编号："+window.slot+"\n网络状态："+window.state+"\n线路延迟："+window.latency;
    if(!window.internal)return value+"\n线路模式：手机网络 / 外部代理\n内置代理分项不适用于此窗口。";
    JSONObject runtime=window.runtime;
    boolean matching=NativeNetwork.exitIdentity(window.config).equals(runtime.optString("exitId"))
      &&NativeNetwork.hash(window.config.optString("subscriptionUrl")).equals(runtime.optString("subscriptionId"))
      &&window.entry.equals(runtime.optString("delayEntry"));
    value+="\n线路模式：入口 → 固定出口 → 检测网站\n检测地址："+NativeNetwork.PROBE+"\n检测方式：HEAD";
    if(matching&&runtime.optLong("delayAt")>0){
      long at=runtime.optLong("delayAt");
      value+="\n测速时间："+new java.text.SimpleDateFormat("yyyy-MM-dd HH:mm:ss Z",Locale.ROOT).format(new java.util.Date(at));
      if(window.now-at>90000||window.now<at-60000)value+="（历史记录）";
      value+=NetworkMetricsUi.probeDetail(J.obj("latest",runtime.optInt("delay",-1),"lastAt",at,"probe",runtime.optJSONObject("delayProbe")));
    }else value+="\n当前线路尚无匹配的分项记录。";
    JSONObject site=runtime.optJSONObject("website");
    value+="\n\nChatGPT 网站："+(matching&&site!=null&&window.entry.equals(site.optString("entry"))?WebsiteProbe.line(site,window.now):"网站响应未测");
    return value+"\n\n上述建链和 TLS 分项属于检测网站，不是 ChatGPT 请求的分项。网站首响应不是模型生成耗时。\n此诊断不包含节点地址、订阅链接、账号、密码或聊天内容。";
  }
  static String routeDiagnostics(android.content.Context context){
    String network="尚未确认";
    try{
      android.net.ConnectivityManager cm=context.getSystemService(android.net.ConnectivityManager.class);
      android.net.Network active=cm.getActiveNetwork();android.net.NetworkCapabilities caps=active==null?null:cm.getNetworkCapabilities(active);
      network=caps==null?"不可用":caps.hasTransport(android.net.NetworkCapabilities.TRANSPORT_VPN)?"手机 VPN":caps.hasTransport(android.net.NetworkCapabilities.TRANSPORT_WIFI)?"Wi-Fi":caps.hasTransport(android.net.NetworkCapabilities.TRANSPORT_CELLULAR)?"移动数据":"其他网络";
    }catch(Exception ignored){}
    String value="\n\n手机网络："+network;ChatSession session=ChatSession.peek();
    if(session==null||!session.internalNetwork())return value+"\n线路模式：手机网络 / 外部代理";
    value+="\n线路模式：应用内置入口 → 固定出口";
    JSONObject sample=NativeNetwork.get(context).probeSnapshot();long now=System.currentTimeMillis(),at=sample.optLong("at");
    if(at<=0||now<at-60000||now-at>90000)return value+"\n当前线路测速：尚无近期记录";
    JSONObject display=new JSONObject();try{display.put("latest",sample.optInt("delay",-1));display.put("lastAt",at);display.put("probe",sample.optJSONObject("probe"));}catch(Exception ignored){}
    return value+"\n检测地址："+NativeNetwork.PROBE+"\nHEAD · 当前入口 → 固定出口 → 检测网站\n当前线路测速："+(sample.optInt("delay",-1)>0?LatencyProbePolicy.label(sample.optString("kind","unknown"),sample.optInt("delay")):"未通过")+NetworkMetricsUi.probeDetail(display);
  }
}
