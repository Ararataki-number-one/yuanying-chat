package local.pocketchat;

import org.json.*;
import java.util.*;
import java.util.regex.*;

/** Evidence states describe only the observed path, never account risk or anonymity. */
final class AuditReport {
  static final String VERIFIED="verified",ISSUE="issue",UNCOVERED="uncovered";
  static void row(JSONArray rows,String key,String name,String state,String detail){rows.put(J.obj("key",key,"name",name,"state",state,"detail",detail));}
  static int major(String ua){Matcher m=Pattern.compile("(?:Chrome|Chromium|Firefox)/([0-9]+)").matcher(ua);try{return m.find()?Integer.parseInt(m.group(1)):-1;}catch(Exception e){return -1;}}
  static boolean v4(String ip){if(!ip.matches("[0-9]{1,3}(?:\\.[0-9]{1,3}){3}"))return false;for(String s:ip.split("\\."))if(Integer.parseInt(s)>255)return false;return !BrowserNetworkGuard.localHost(ip);}
  static boolean v6(String ip){return ip.contains(":")&&ip.matches("[0-9a-fA-F:.]+")&&!BrowserNetworkGuard.localHost(ip);}
  static String ip(JSONObject result){return result==null?"":result.optString("ip");}
  static boolean hintsMatch(JSONObject hints,int wanted){if(hints==null)return true;JSONArray brands=hints.optJSONArray("brands");if(brands==null)return true;for(int i=0;i<brands.length();i++){JSONObject b=brands.optJSONObject(i);if(b!=null&&b.optString("brand").matches("(?i).*(?:Chromium|Chrome|WebView).*"))try{if(Integer.parseInt(b.optString("version").split("\\.")[0])!=wanted)return false;}catch(Exception e){return false;}}return true;}
  static JSONObject build(JSONObject sample,JSONObject nativeResult,JSONObject expected,boolean network,boolean fresh){
    JSONArray rows=new JSONArray();JSONObject parent=sample.optJSONObject("parent"),frame=sample.optJSONObject("frame"),worker=sample.optJSONObject("worker"),net=sample.optJSONObject("network");if(parent==null)parent=new JSONObject();if(frame==null)frame=new JSONObject();if(worker==null)worker=new JSONObject();if(net==null)net=new JSONObject();
    String ua=parent.optString("ua"),wanted=expected.optString("ua");int actual=major(ua),engine=expected.optInt("major",-1);boolean basic=!ua.isEmpty()&&ua.equals(wanted)&&actual>0&&engine>0&&actual==engine;
    row(rows,"ua","浏览器版本与网页信息",ua.isEmpty()||engine<=0||actual<=0?UNCOVERED:basic?VERIFIED:ISSUE,ua.isEmpty()||engine<=0?"未取得可核验的网页或内核版本":basic?"检查页面的 UA 与应用设置及已安装内核主版本一致":"观察到 UA 与应用设置或内核主版本不一致");
    JSONObject hints=parent.optJSONObject("hints");boolean hintsKnown=false;if(hints!=null){JSONArray brands=hints.optJSONArray("brands");if(brands!=null)for(int i=0;i<brands.length();i++)if(brands.optJSONObject(i)!=null&&brands.optJSONObject(i).optString("brand").matches("(?i).*(?:Chromium|Chrome|WebView).*"))hintsKnown=true;}row(rows,"hints","Client Hints 浏览器信息",!hintsKnown||engine<=0?UNCOVERED:hintsMatch(hints,engine)?VERIFIED:ISSUE,!hintsKnown?"当前页面未提供可核验的 Client Hints 品牌，不能据此认定所有来源一致":"仅核对返回的浏览器主版本；不是完整设备身份校验");
    boolean frameKnown=frame.has("ua"),frameSame=frameKnown&&ua.equals(frame.optString("ua"))&&Objects.equals(parent.opt("cpu"),frame.opt("cpu"))&&Objects.equals(parent.opt("memory"),frame.opt("memory"));
    row(rows,"frame","嵌入页面一致性",frameKnown?frameSame?VERIFIED:ISSUE:UNCOVERED,frameKnown?frameSame?"本地子页面的 UA、线程数和内存字段与主页面一致":"本地子页面返回了不同的 UA 或硬件字段":"未取得嵌入页面结果");
    boolean workerKnown=worker.has("ua"),rendererComparable=parent.has("renderer")&&worker.has("renderer")&&!parent.optString("renderer").equals("unavailable")&&!worker.optString("renderer").equals("unavailable"),rendererSame=!rendererComparable||parent.optString("renderer").equals(worker.optString("renderer"));boolean workerSame=workerKnown&&ua.equals(worker.optString("ua"))&&Objects.equals(parent.opt("cpu"),worker.opt("cpu"))&&Objects.equals(parent.opt("memory"),worker.opt("memory"))&&parent.optString("language").equals(worker.optString("language"))&&parent.optInt("offset")==worker.optInt("offset")&&rendererSame;
    row(rows,"worker","后台脚本一致性",workerKnown?workerSame?VERIFIED:ISSUE:UNCOVERED,workerKnown?workerSame?"本地 Worker 的已核对字段与页面一致；不代表全部 API 已覆盖":"页面与 Worker 的设备字段不同（线程数："+parent.optString("cpu","未知")+" / "+worker.optString("cpu","未知")+"，图形字段："+(rendererSame?"未发现可核验差异":"覆盖不同")+"）。当前页面保护未完整覆盖后台脚本":"无法运行本地 Worker，覆盖范围尚未确认");
    boolean gecko="gecko".equals(expected.optString("engine"));boolean early=parent.optBoolean("early")&&frame.optBoolean("early");row(rows,"early","加载前保护覆盖",gecko||expected.optInt("level")==0?UNCOVERED:early?VERIFIED:ISSUE,gecko?"Firefox 使用内核保护；此项脚本保护检测不适用":expected.optInt("level")==0?"兼容模式未启用此保护":early?"检查页面与子页面的首个脚本前已有保护":"未在检查页面和子页面全部观察到加载前保护");
    String rtc=parent.optString("rtc");row(rows,"rtc","WebRTC 本机接口限制",rtc.equals("restricted")||rtc.equals("absent")?VERIFIED:expected.optInt("level")>0&&rtc.equals("available")?ISSUE:UNCOVERED,rtc.equals("restricted")||rtc.equals("absent")?"本地检查未能创建 RTC 连接；没有进行 STUN 公网候选或全部协议抓包测试":"RTC 接口可用或结果不明确，不能证明公网地址不会泄漏");
    row(rows,"zone","网页与手机时区偏移",parent.has("offset")?parent.optInt("offset")==expected.optInt("offset")?VERIFIED:ISSUE:UNCOVERED,"只核对当前手机与页面偏移；不把时区与 IP 地区差异当作账号危险");
    if(network){String browserIp=ip(net.optJSONObject("ipv4")),nativeIp=ip(nativeResult),workerIp=ip(worker.optJSONObject("ip"));boolean have=v4(browserIp)&&v4(nativeIp);boolean mismatch=have&&!browserIp.equals(nativeIp)||have&&v4(workerIp)&&!browserIp.equals(workerIp);boolean all=have&&v4(workerIp)&&browserIp.equals(nativeIp)&&browserIp.equals(workerIp);String expectedIp=expected.optString("exitIp");boolean fixedMismatch=have&&v4(expectedIp)&&!browserIp.equals(expectedIp);String state=!fresh?UNCOVERED:mismatch||fixedMismatch?ISSUE:all?VERIFIED:UNCOVERED;
      row(rows,"ipv4","实际 IPv4 出口核对",state,!fresh?"检查期间连接发生变化，结果已作废":!have?"网页或原生查询未返回有效地址；查询失败不代表没有泄漏":mismatch||fixedMismatch?"观察到本次请求出口不同，或与已核实固定出口不同；需要检查线路":all?"网页、Worker 与原生 HTTPS 查询观察到同一出口"+(v4(expectedIp)?"，且符合固定出口记录":"；没有独立固定出口基线"):"网页与原生查询已返回；Worker 路径尚未覆盖");
      String observed6=ip(net.optJSONObject("ipv6"));row(rows,"ipv6","实际 IPv6 观察",UNCOVERED,v6(observed6)?"观察到 IPv6 出口，但尚无获准的固定 IPv6 基线，不能断言是否泄漏":"IPv6 查询未返回有效结果；不把失败当作已阻断或无泄漏");
      JSONObject echo=net.optJSONObject("headers");JSONObject headers=echo==null?null:echo.optJSONObject("headers");String headerUa="";if(headers!=null){Iterator<String> keys=headers.keys();while(keys.hasNext()){String key=keys.next();if(key.equalsIgnoreCase("User-Agent"))headerUa=headers.optString(key);}}
      row(rows,"header","实际请求 UA 与页面核对",!fresh||headerUa.isEmpty()?UNCOVERED:headerUa.equals(ua)?VERIFIED:ISSUE,!fresh?"连接已变化，结果作废":headerUa.isEmpty()?"公开回显服务未返回可核对的 UA":headerUa.equals(ua)?"本次检查请求的回显 UA 与页面一致":"本次回显请求的 UA 与页面字段不同");
    }else row(rows,"network","实际网络出口",UNCOVERED,"本次只检查浏览器信息，没有访问网络检测服务");
    row(rows,"dns","DNS 网络泄漏",UNCOVERED,"可查看内置加密 DNS 配置，但未进行权威 DNS 探针或网络抓包，不能证明解析没有绕行");row(rows,"udp","UDP / QUIC / TLS 等路径",UNCOVERED,"本次 HTTPS 查询不能覆盖所有协议或识别全部浏览器网络指纹");
    if(!fresh)for(int i=0;i<rows.length();i++){JSONObject r=rows.optJSONObject(i);if(!UNCOVERED.equals(r.optString("state")))try{r.put("state",UNCOVERED);r.put("detail","检查期间环境变化，结果已作废，请在连接稳定后重测");}catch(Exception ignored){}}
    return J.obj("at",System.currentTimeMillis(),"network",network,"fresh",fresh,"rows",rows,"signals",sample,"native",nativeResult,"scope","gecko".equals(expected.optString("engine"))?"当前 Firefox 页面内的浏览器公共信息及指定检测服务":"本机检查页面及指定公开检测服务");
  }
}
