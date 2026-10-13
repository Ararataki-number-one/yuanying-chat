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
  static final List<String> CONTEXT_FIELDS=Collections.unmodifiableList(Arrays.asList("ua","cpu","memory","language","languages","offset","zone"));
  static boolean observedField(JSONObject signal,String field){
    if(!signal.has(field))return false;Object value=signal.opt(field);
    if("cpu".equals(field)||"memory".equals(field))return value==JSONObject.NULL||value instanceof Number&&Double.isFinite(((Number)value).doubleValue())&&((Number)value).doubleValue()>0;
    if("offset".equals(field))return value instanceof Number&&Double.isFinite(((Number)value).doubleValue())&&((Number)value).doubleValue()==((Number)value).intValue()&&Math.abs(((Number)value).intValue())<=1440;
    if("languages".equals(field)){if(!(value instanceof JSONArray)||((JSONArray)value).length()==0)return false;JSONArray list=(JSONArray)value;for(int i=0;i<list.length();i++)if(!(list.opt(i) instanceof String)||list.optString(i).isEmpty())return false;return true;}
    return value instanceof String&&!((String)value).isEmpty();
  }
  static boolean fieldSame(JSONObject first,JSONObject second,String field){
    Object a=first.opt(field),b=second.opt(field);
    if("languages".equals(field))return ((JSONArray)a).toString().equals(((JSONArray)b).toString());
    if(a instanceof Number&&b instanceof Number)return Double.compare(((Number)a).doubleValue(),((Number)b).doubleValue())==0;
    return Objects.equals(a,b);
  }
  static JSONObject contextCoverage(JSONObject parent,JSONObject child){
    JSONArray covered=new JSONArray(),missing=new JSONArray(),different=new JSONArray();
    for(String field:CONTEXT_FIELDS){
      if(!observedField(parent,field)||!observedField(child,field)){missing.put(field);continue;}
      covered.put(field);if(!fieldSame(parent,child,field))different.put(field);
    }
    return J.obj("compared",covered,"missingOrInvalid",missing,"different",different,"state",different.length()>0?ISSUE:missing.length()>0?UNCOVERED:VERIFIED);
  }
  static JSONObject build(JSONObject sample,JSONObject nativeResult,JSONObject expected,boolean network,boolean fresh){
    JSONArray rows=new JSONArray();JSONObject parent=sample.optJSONObject("parent"),frame=sample.optJSONObject("frame"),worker=sample.optJSONObject("worker"),net=sample.optJSONObject("network");if(parent==null)parent=new JSONObject();if(frame==null)frame=new JSONObject();if(worker==null)worker=new JSONObject();if(net==null)net=new JSONObject();
    boolean gecko="gecko".equals(expected.optString("engine")),mainObserved="page-main-world".equals(sample.optString("provenance"))&&sample.optJSONObject("mainWorld")!=null&&Boolean.TRUE.equals(sample.optJSONObject("mainWorld").opt("observed"));
    row(rows,"provenance","网页执行环境与来源",mainObserved?VERIFIED:UNCOVERED,mainObserved?"本次在页面主执行环境采集公开字段；页面可修改或伪造这些值，结果不是独立身份认证":"未取得页面主执行环境结果；隔离扩展世界的回退值仅作诊断，不能代表网页实际读取值");
    String ua=parent.optString("ua"),wanted=expected.optString("ua");int actual=major(ua),engine=expected.optInt("major",-1);boolean basic=!ua.isEmpty()&&ua.equals(wanted)&&actual>0&&engine>0&&actual==engine;
    row(rows,"ua","浏览器版本与网页信息",ua.isEmpty()||engine<=0||actual<=0?UNCOVERED:basic?VERIFIED:ISSUE,ua.isEmpty()||engine<=0?"未取得可核验的网页或内核版本":basic?"检查页面的 UA 与应用设置及已安装内核主版本一致":"观察到 UA 与应用设置或内核主版本不一致");
    JSONObject hints=parent.optJSONObject("hints");boolean hintsKnown=false;if(hints!=null){JSONArray brands=hints.optJSONArray("brands");if(brands!=null)for(int i=0;i<brands.length();i++)if(brands.optJSONObject(i)!=null&&brands.optJSONObject(i).optString("brand").matches("(?i).*(?:Chromium|Chrome|WebView).*"))hintsKnown=true;}row(rows,"hints","Client Hints 浏览器信息",!hintsKnown||engine<=0?UNCOVERED:hintsMatch(hints,engine)?VERIFIED:ISSUE,!hintsKnown?"当前页面未提供可核验的 Client Hints 品牌，不能据此认定所有来源一致":"仅核对返回的浏览器主版本；不是完整设备身份校验");
    JSONObject frameCoverage=contextCoverage(parent,frame),workerCoverage=contextCoverage(parent,worker);
    row(rows,"frame","同源嵌入页面一致性",frameCoverage.optString("state"),frameCoverage.optString("state").equals(VERIFIED)?"同源 srcdoc 的 UA、线程数、内存接口、语言列表及时区观测与主页面一致；不代表其他 API 已覆盖":frameCoverage.optString("state").equals(ISSUE)?"同源子页面存在已观测差异："+frameCoverage.optJSONArray("different"):"同源子页面采集不完整，未覆盖或类型无效："+frameCoverage.optJSONArray("missingOrInvalid"));
    boolean rendererComparable=observedField(parent,"renderer")&&observedField(worker,"renderer")&&!"unavailable".equals(parent.optString("renderer"))&&!"unavailable".equals(worker.optString("renderer"));
    boolean rendererSame=!rendererComparable||parent.optString("renderer").equals(worker.optString("renderer"));
    row(rows,"worker","Dedicated Worker 一致性",rendererSame?workerCoverage.optString("state"):ISSUE,!rendererSame?"页面与 Dedicated Worker 图形观测不同；已保留差异":workerCoverage.optString("state").equals(VERIFIED)?"Dedicated Worker 的 UA、线程数、内存接口、语言列表及时区观测与主页面一致；图形、联网及其他 API 另有覆盖范围":workerCoverage.optString("state").equals(ISSUE)?"Dedicated Worker 存在已观测差异："+workerCoverage.optJSONArray("different"):"Dedicated Worker 采集不完整，未覆盖或类型无效："+workerCoverage.optJSONArray("missingOrInvalid"));
    boolean early=parent.optBoolean("early")&&frame.optBoolean("early");row(rows,"early","加载前保护覆盖",gecko||expected.optInt("level")==0?UNCOVERED:early?VERIFIED:ISSUE,gecko?"Firefox 使用内核保护；此项脚本保护检测不适用":expected.optInt("level")==0?"兼容模式未启用此保护":early?"检查页面与子页面的首个脚本前已有保护":"未在检查页面和子页面全部观察到加载前保护");
    String rtc=parent.optString("rtc");row(rows,"rtc","WebRTC 本机接口限制",rtc.equals("restricted")||rtc.equals("absent")?VERIFIED:expected.optInt("level")>0&&rtc.equals("available")?ISSUE:UNCOVERED,rtc.equals("restricted")||rtc.equals("absent")?"本地检查未能创建 RTC 连接；没有进行 STUN 公网候选或全部协议抓包测试":"RTC 接口可用或结果不明确，不能证明公网地址不会泄漏");
    boolean standardized="native-standardized".equals(expected.optString("timezoneStrategy"));
    row(rows,"zone",standardized?"原生标准化时区观测":"网页与手机时区偏移",standardized?UNCOVERED:observedField(parent,"offset")&&observedField(expected,"offset")?parent.optInt("offset")==expected.optInt("offset")?VERIFIED:ISSUE:UNCOVERED,standardized?"强化模式采用 Firefox 原生标准化策略；没有承诺独立时区值，不与手机时区差异作错误比较。页面与 Worker 的一致性另行检查":"只核对当前手机与页面偏移；不把时区与 IP 地区差异当作账号危险");
    String language=parent.optString("language"),wantedLanguage=expected.optString("language");
    row(rows,"language","网页语言与原生设置",!observedField(parent,"language")||!observedField(expected,"language")?UNCOVERED:language.equalsIgnoreCase(wantedLanguage)?VERIFIED:ISSUE,language.isEmpty()||wantedLanguage.isEmpty()?"未取得可核对的语言值":"核对本次 navigator.language 与官方 SDK 的 language-region 规范化预测；SDK 回读仅表示请求，强化策略可能继续标准化，实际差异会保留");
    if(network){String browserIp=ip(net.optJSONObject("ipv4")),nativeIp=ip(nativeResult),workerIp=ip(worker.optJSONObject("ip"));boolean have=v4(browserIp)&&v4(nativeIp);boolean mismatch=have&&!browserIp.equals(nativeIp)||have&&v4(workerIp)&&!browserIp.equals(workerIp);boolean all=have&&v4(workerIp)&&browserIp.equals(nativeIp)&&browserIp.equals(workerIp);String expectedIp=expected.optString("exitIp");boolean fixedMismatch=have&&v4(expectedIp)&&!browserIp.equals(expectedIp);String state=!fresh?UNCOVERED:mismatch||fixedMismatch?ISSUE:all?VERIFIED:UNCOVERED;
      row(rows,"ipv4","实际 IPv4 出口核对",state,!fresh?"检查期间连接发生变化，结果已作废":!have?"网页或原生查询未返回有效地址；查询失败不代表没有泄漏":mismatch||fixedMismatch?"观察到本次请求出口不同，或与已核实固定出口不同；需要检查线路":all?"网页、Worker 与原生 HTTPS 查询观察到同一出口"+(v4(expectedIp)?"，且符合固定出口记录":"；没有独立固定出口基线"):"Gecko 内容脚本请求与原生查询已返回相同地址；Worker 出口路径尚未覆盖，因此完整出口核对未通过");
      String observed6=ip(net.optJSONObject("ipv6"));row(rows,"ipv6","实际 IPv6 观察",UNCOVERED,v6(observed6)?"观察到 IPv6 出口，但尚无获准的固定 IPv6 基线，不能断言是否泄漏":"IPv6 查询未返回有效结果；不把失败当作已阻断或无泄漏");
      JSONObject echo=net.optJSONObject("headers");JSONObject headers=echo==null?null:echo.optJSONObject("headers");String headerUa="";if(headers!=null){Iterator<String> keys=headers.keys();while(keys.hasNext()){String key=keys.next();if(key.equalsIgnoreCase("User-Agent"))headerUa=headers.optString(key);}}
      row(rows,"header","实际请求 UA 与页面核对",!fresh||headerUa.isEmpty()?UNCOVERED:headerUa.equals(ua)?VERIFIED:ISSUE,!fresh?"连接已变化，结果作废":headerUa.isEmpty()?"公开回显服务未返回可核对的 UA":headerUa.equals(ua)?"本次检查请求的回显 UA 与页面一致":"本次回显请求的 UA 与页面字段不同");
      String acceptLanguage="";if(headers!=null){Iterator<String> keys=headers.keys();while(keys.hasNext()){String key=keys.next();if(key.equalsIgnoreCase("Accept-Language"))acceptLanguage=headers.optString(key);}}
      String first=acceptLanguage.split(",",2)[0].split(";",2)[0].trim();
      row(rows,"header-language","实际请求语言与页面核对",!fresh||first.isEmpty()||language.isEmpty()?UNCOVERED:first.equalsIgnoreCase(language)?VERIFIED:ISSUE,"仅核对本次 Gecko 内容脚本请求的服务回显与页面值；不是 ChatGPT 主文档请求的服务端日志，也不是 Java 客户端的模拟请求头");
    }else row(rows,"network","实际网络出口",UNCOVERED,"本次只检查浏览器信息，没有访问网络检测服务");
    row(rows,"cross-origin","跨源 iframe",UNCOVERED,"本次仅创建同源 srcdoc 子页面，没有已验证的跨源页面探针");
    row(rows,"shared-worker","Shared Worker",UNCOVERED,"本次仅创建 Dedicated Worker，没有 Shared Worker 观测");
    row(rows,"service-worker","Service Worker",UNCOVERED,"没有注册或改变网站 Service Worker；该执行环境未覆盖");
    row(rows,"native-setting","原生抗指纹设置回读",expected.optBoolean("rfpAcknowledged")?VERIFIED:UNCOVERED,expected.optBoolean("rfpAcknowledged")?(expected.optInt("level")>=2?"当前强化请求要求开启抗指纹，设置回读一致":"当前请求未开启抗指纹，设置回读一致")+"；这不证明具体指纹 API 保护或网页兼容性":"尚未取得与请求值一致的原生设置回读");
    row(rows,"dns","DNS 网络泄漏",UNCOVERED,"可查看内置加密 DNS 配置，但未进行权威 DNS 探针或网络抓包，不能证明解析没有绕行");row(rows,"udp","UDP / QUIC / TLS 等路径",UNCOVERED,"本次 HTTPS 查询不能覆盖所有协议或识别全部浏览器网络指纹");
    if(gecko&&!mainObserved)for(int i=0;i<rows.length();i++){JSONObject r=rows.optJSONObject(i);if(Arrays.asList("ua","hints","frame","worker","rtc","zone","language","header","header-language").contains(r.optString("key")))try{r.put("state",UNCOVERED);r.put("detail","页面主执行环境采集未完成；隔离扩展世界的值不能用于验证网页实际表现");}catch(Exception ignored){}}
    if(!fresh)for(int i=0;i<rows.length();i++){JSONObject r=rows.optJSONObject(i);if(!UNCOVERED.equals(r.optString("state")))try{r.put("state",UNCOVERED);r.put("detail","检查期间环境变化，结果已作废，请在连接稳定后重测");}catch(Exception ignored){}}
    return J.obj("at",System.currentTimeMillis(),"network",network,"fresh",fresh,"rows",rows,"signals",sample,"native",nativeResult,"contextCoverage",J.obj("requiredFields",new JSONArray(CONTEXT_FIELDS),"frame",frameCoverage,"worker",workerCoverage),"expected",expected,"scope",gecko?"页面主执行环境（若 CSP 允许）、同源 srcdoc、Dedicated Worker 及明确标注的 Gecko 内容请求；公开字段可被页面伪造":"本机检查页面及指定公开检测服务");
  }
}
