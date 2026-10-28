package local.pocketchat;

import org.json.*;
import java.util.*;
import java.util.regex.*;

/** Evidence states describe only the observed path, never account risk or anonymity. */
final class AuditReport {
  static final String VERIFIED="verified",ISSUE="issue",UNCOVERED="uncovered",AVAILABLE="available",RESTRICTED="restricted",FAILED="failed";
  static String stateLabel(String state){switch(state){case VERIFIED:return "已验证";case ISSUE:return "发现差异";case AVAILABLE:return "可用";case RESTRICTED:return "受限";case FAILED:return "失败";default:return "未覆盖";}}
  static void row(JSONArray rows,String key,String name,String state,String detail){rows.put(J.obj("key",key,"name",name,"state",state,"detail",detail));}
  static int major(String ua){Matcher m=Pattern.compile("(?:Chrome|Chromium|Firefox)/([0-9]+)").matcher(ua);try{return m.find()?Integer.parseInt(m.group(1)):-1;}catch(Exception e){return -1;}}
  static boolean v4(String ip){if(!ip.matches("[0-9]{1,3}(?:\\.[0-9]{1,3}){3}"))return false;for(String s:ip.split("\\."))if(Integer.parseInt(s)>255)return false;return !BrowserNetworkGuard.localHost(ip);}
  static boolean v6(String ip){return ip.contains(":")&&ip.matches("[0-9a-fA-F:.]+")&&!BrowserNetworkGuard.localHost(ip);}
  static String ip(JSONObject result){return result==null?"":result.optString("ip");}
  static boolean hintsMatch(JSONObject hints,int wanted){if(hints==null)return true;JSONArray brands=hints.optJSONArray("brands");if(brands==null)return true;for(int i=0;i<brands.length();i++){JSONObject b=brands.optJSONObject(i);if(b!=null&&b.optString("brand").matches("(?i).*(?:Chromium|Chrome|WebView).*"))try{if(Integer.parseInt(b.optString("version").split("\\.")[0])!=wanted)return false;}catch(Exception e){return false;}}return true;}
  static final List<String> CONTEXT_FIELDS=Collections.unmodifiableList(Arrays.asList("ua","cpu","memory","language","languages","offset","zone"));
  static final List<String> NAVIGATOR_IDENTITY_FIELDS=Collections.unmodifiableList(Arrays.asList("platform","appVersion"));
  static boolean identityTextObserved(JSONObject signal,String field){
    if(signal==null)return false;Object raw=signal.opt(field);int limit="platform".equals(field)?128:1024;
    if(!(raw instanceof String))return false;String value=(String)raw;
    if(value.trim().isEmpty()||value.length()>limit)return false;
    for(int i=0;i<value.length();i++)if(Character.isISOControl(value.charAt(i)))return false;
    return true;
  }
  /** Compare only the exact public values captured in the same observation.
   * WorkerNavigator does not expose every window API. Missing values remain
   * uncovered; no mobile/desktop value is invented or matched to a device model. */
  static JSONObject navigatorIdentityCoverage(JSONObject parent,JSONObject child,boolean mainObserved,boolean fresh){
    JSONArray compared=new JSONArray(),missing=new JSONArray(),different=new JSONArray();
    boolean current=mainObserved&&fresh;
    if(current)for(String field:NAVIGATOR_IDENTITY_FIELDS){
      if(!identityTextObserved(parent,field)||!identityTextObserved(child,field)){missing.put(field);continue;}
      compared.put(field);if(!parent.optString(field).equals(child.optString(field)))different.put(field);
    }
    return J.obj("state",!current?UNCOVERED:different.length()>0?ISSUE:missing.length()>0?UNCOVERED:VERIFIED,
        "compared",compared,"missingOrInvalid",missing,"different",different,"current",current,
        "reason",!mainObserved?"page-main-world-unavailable":!fresh?"stale-observation":missing.length()>0?"missing-or-invalid-fields":"observed-public-fields",
        "operationOnly",true,"deviceModelVerified",false,"httpHeadersVerified",false,"protectionVerified",false);
  }
  static String navigatorIdentityDetail(JSONObject value){
    if(!value.optBoolean("current"))return "stale-observation".equals(value.optString("reason"))?"页面或配置已变化，本次平台与版本字段未比较":"未取得页面主执行环境；隔离世界的值不能代替网页观测";
    if(ISSUE.equals(value.optString("state")))return "本次平台或版本公开字段存在差异："+value.optJSONArray("different")+"；只保留观察，不直接判断泄漏或设备身份";
    if(UNCOVERED.equals(value.optString("state")))return "平台或版本字段缺失、类型无效或超出边界："+value.optJSONArray("missingOrInvalid")+"；不从主页面补齐 Worker 值";
    return "本次 platform 与 appVersion 的可比公开值一致；不验证手机型号、HTTP 请求头或全部指纹保护";
  }
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
  static boolean finite(Object value,double minimum,double maximum){return value instanceof Number&&Double.isFinite(((Number)value).doubleValue())&&((Number)value).doubleValue()>=minimum&&((Number)value).doubleValue()<=maximum;}
  static boolean exactNumber(Object value,int expected){return finite(value,expected,expected);}
  static boolean boundedText(Object value,int maximum){return value instanceof String&&!((String)value).isEmpty()&&((String)value).length()<=maximum;}
  static boolean apiOperationComplete(String name,JSONObject value){
    if("canvas".equals(name))return exactNumber(value.opt("pixels"),4096);
    if("audio".equals(name))return exactNumber(value.opt("frames"),2048)&&exactNumber(value.opt("sampleRate"),44100)&&finite(value.opt("peak"),0,1);
    if("fonts".equals(name)){JSONArray samples=value.optJSONArray("samples");if(!exactNumber(value.opt("candidateCount"),5)||samples==null||samples.length()!=5)return false;Set<String> names=new HashSet<>(Arrays.asList("Arial","Times New Roman","Courier New","Noto Sans","Noto Sans CJK SC"));for(int i=0;i<samples.length();i++){JSONObject sample=samples.optJSONObject(i);if(sample==null||!names.remove(sample.optString("name"))||!finite(sample.opt("monospaceWidth"),0,100000)||!finite(sample.opt("sansSerifWidth"),0,100000)||!(sample.opt("faceCheck") instanceof Boolean||sample.opt("faceCheck")==JSONObject.NULL))return false;}return names.isEmpty();}
    if("webgl".equals(name)){for(String field:new String[]{"version","shadingLanguageVersion","vendor","renderer"})if(!boundedText(value.opt(field),256))return false;for(String field:new String[]{"maxTextureSize","maxRenderbufferSize","maxVertexAttribs"}){Object item=value.opt(field);if(!finite(item,1,Integer.MAX_VALUE)||((Number)item).doubleValue()!=((Number)item).intValue())return false;}JSONArray extensions=value.optJSONArray("extensions");Object count=value.opt("extensionCount");if(!finite(count,0,4096)||((Number)count).doubleValue()!=((Number)count).intValue()||extensions==null||extensions.length()>7||((Number)count).intValue()<extensions.length())return false;Set<String> unique=new HashSet<>();for(int i=0;i<extensions.length();i++){Object extension=extensions.opt(i);if(!boundedText(extension,128)||!unique.add((String)extension))return false;}return true;}
    return false;
  }
  static Object displayValue(JSONObject value,String field){
    JSONObject viewport=value.optJSONObject("viewport");if(viewport==null)viewport=new JSONObject();
    if("pixelRatio".equals(field))return finite(viewport.opt(field),.01,32)?viewport.opt(field):null;
    if("touch".equals(field)){Object touch=viewport.opt(field);return finite(touch,0,64)&&((Number)touch).doubleValue()==((Number)touch).intValue()?touch:null;}
    JSONObject screen=value.optJSONObject("screen");if(screen==null||!finite(screen.opt("width"),1,65536)||!finite(screen.opt("height"),1,65536))return null;
    double width=screen.optDouble("width"),height=screen.optDouble("height");if(width!=Math.rint(width)||height!=Math.rint(height))return null;
    return J.obj("short",Math.min(width,height),"long",Math.max(width,height));
  }
  static JSONObject displayCoverage(JSONObject parent,JSONObject child){
    JSONArray compared=new JSONArray(),missing=new JSONArray(),different=new JSONArray();
    for(String field:new String[]{"screen","pixelRatio","touch"}){Object a=displayValue(parent,field),b=displayValue(child,field);if(a==null||b==null){missing.put(field);continue;}compared.put(field);boolean equal=a instanceof Number&&b instanceof Number?Double.compare(((Number)a).doubleValue(),((Number)b).doubleValue())==0:a.toString().equals(b.toString());if(!equal)different.put(field);}
    return J.obj("compared",compared,"missingOrInvalid",missing,"different",different,"state",different.length()>0?ISSUE:missing.length()>0?UNCOVERED:VERIFIED);
  }
  static JSONObject apiCoverage(JSONArray rows,JSONObject sample,boolean mainObserved,boolean fresh){
    JSONObject checks=sample.optJSONObject("apiChecks"),probes=checks==null?null:checks.optJSONObject("probes");boolean requested=checks!=null&&Boolean.TRUE.equals(checks.opt("requested"));
    JSONObject limits=checks==null?null:checks.optJSONObject("limits");boolean valid=requested&&fresh&&mainObserved&&exactNumber(checks.opt("schema"),1)&&exactNumber(checks.opt("probeVersion"),1)&&"page-main-world".equals(checks.optString("source"))&&Boolean.FALSE.equals(checks.opt("protectionVerified"))&&limits!=null&&exactNumber(limits.opt("canvasPixels"),4096)&&exactNumber(limits.opt("audioFrames"),2048)&&exactNumber(limits.opt("fontCandidates"),5)&&exactNumber(limits.opt("totalBudgetMs"),1200);
    JSONObject coverage=new JSONObject();String[] names={"canvas","audio","fonts","webgl"},labels={"Canvas 绘制与像素读回","离线音频处理","有限字体可见性与测量","WebGL 可观察能力"};
    for(int i=0;i<names.length;i++){
      String name=names[i];JSONObject probe=probes==null?null:probes.optJSONObject(name);String state=valid&&probe!=null?probe.optString("state"):UNCOVERED;boolean incomplete=AVAILABLE.equals(state)&&!apiOperationComplete(name,probe);if(!Arrays.asList(AVAILABLE,RESTRICTED,FAILED,UNCOVERED).contains(state)||incomplete)state=UNCOVERED;
      String detail=!requested?"本次未主动运行此项；可选择“检查图形与音频（本机）”":!fresh?"检查期间环境变化，本次操作结果已作废":!valid?"未取得当前页面主执行环境的有效操作结果；扩展隔离世界不代替页面":incomplete?"操作结果字段不完整或类型无效，尚未覆盖":AVAILABLE.equals(state)?"本次有限操作已完成，只表示可用，不证明原生保护有效":RESTRICTED.equals(state)?"本次操作受到浏览器或页面限制；受限本身不代表泄漏":FAILED.equals(state)?"本次操作失败，尚不能核验其结果":"接口不可用、采集超时或未覆盖，不能作通过判断";
      if(valid&&probe!=null&&!incomplete){String reason=probe.optString("reason");if(!reason.isEmpty())detail+="（"+reason.substring(0,Math.min(96,reason.length()))+"）";}
      if("audio".equals(name))detail+="；使用离线音频，不向扬声器播放";if("fonts".equals(name))detail+="；只检查有限候选字体，不代表完整安装字体列表";
      row(rows,"api-"+name,labels[i],state,detail);try{coverage.put(name,J.obj("state",state,"operationOnly",true));}catch(JSONException ignored){}
    }
    return J.obj("requested",requested,"source",valid?"page-main-world":"unavailable","probes",coverage,"protectionVerified",false,"scope","Current main-page operations; additional frame and Worker operations are reported separately");
  }
  static JSONObject apiContextCoverage(JSONArray rows,JSONObject sample,boolean mainObserved,boolean fresh){
    JSONObject contexts=sample.optJSONObject("apiContexts"),result=new JSONObject();if(contexts==null||!Boolean.TRUE.equals(contexts.opt("requested")))return J.obj("requested",false,"protectionVerified",false);
    boolean envelope=mainObserved&&fresh&&exactNumber(contexts.opt("schema"),1);String[] names={"canvas","audio","fonts","webgl"},labels={"Canvas 绘制与读回","离线音频","有限字体测量","WebGL 能力与读回"};
    for(String context:new String[]{"frame","worker"}){
      boolean worker="worker".equals(context);String source=worker?"dedicated-worker":"same-origin-srcdoc",title=worker?"Dedicated Worker":"同源 iframe";JSONObject checks=contexts.optJSONObject(context),limits=checks==null?null:checks.optJSONObject("limits"),probes=checks==null?null:checks.optJSONObject("probes");
      boolean valid=envelope&&checks!=null&&Boolean.TRUE.equals(checks.opt("requested"))&&Boolean.FALSE.equals(checks.opt("protectionVerified"))&&exactNumber(checks.opt("schema"),1)&&exactNumber(checks.opt("probeVersion"),1)&&source.equals(checks.optString("source"))&&limits!=null&&exactNumber(limits.opt("canvasPixels"),4096)&&exactNumber(limits.opt("audioFrames"),worker?0:2048)&&exactNumber(limits.opt("fontCandidates"),worker?0:5)&&exactNumber(limits.opt("totalBudgetMs"),1200);JSONObject operations=new JSONObject();
      for(int i=0;i<names.length;i++){
        String name=names[i];JSONObject probe=probes==null?null:probes.optJSONObject(name);String state=valid&&probe!=null?probe.optString("state"):UNCOVERED;
        if(!Arrays.asList(AVAILABLE,RESTRICTED,FAILED,UNCOVERED).contains(state)||AVAILABLE.equals(state)&&!apiOperationComplete(name,probe))state=UNCOVERED;
        if(worker&&("audio".equals(name)||"fonts".equals(name)))state=UNCOVERED;
        if(worker&&"webgl".equals(name)&&AVAILABLE.equals(state)&&(!exactNumber(probe.opt("readbackPixels"),256)||!exactNumber(probe.opt("readbackBytes"),1024)||!(Boolean.TRUE.equals(probe.opt("readbackHashUnavailable"))||"sha256".equals(probe.optString("readbackHashAlgorithm"))&&probe.opt("readbackHash") instanceof String&&probe.optString("readbackHash").matches("[0-9a-f]{64}"))))state=UNCOVERED;
        String detail=!fresh?"当前文档或配置已变化，本次结果作废":!valid?"未取得该执行环境的完整结果；不使用主页面值代替":worker&&("audio".equals(name)||"fonts".equals(name))?"本次 Dedicated Worker 未运行此接口，标为不适用／未覆盖":AVAILABLE.equals(state)?"该执行环境的有限操作已完成；不同环境的哈希不要求相同":RESTRICTED.equals(state)?"该执行环境的操作受到限制；不能据此判断泄漏":FAILED.equals(state)?"该执行环境操作失败，未作为保护效果通过":"接口缺失、CSP 限制、取消、超时或结果不完整，尚未覆盖";
        if(valid&&probe!=null&&!probe.optString("reason").isEmpty())detail+="（"+probe.optString("reason").substring(0,Math.min(96,probe.optString("reason").length()))+"）";
        row(rows,"api-"+context+"-"+name,title+" · "+("webgl".equals(name)&&!worker?"WebGL 可观察能力":labels[i]),state,detail);try{operations.put(name,J.obj("state",state,"operationOnly",true));}catch(JSONException ignored){}
      }
      try{result.put(context,J.obj("source",source,"probeVersion",valid?1:0,"probes",operations,"protectionVerified",false));}catch(JSONException ignored){}
    }
    try{result.put("requested",true).put("protectionVerified",false).put("scope","Each context is observed independently; no cross-context hash equality or full protection assertion");}catch(JSONException ignored){}return result;
  }
  static JSONObject build(JSONObject sample,JSONObject nativeResult,JSONObject expected,boolean network,boolean fresh){
    JSONArray rows=new JSONArray();JSONObject parent=sample.optJSONObject("parent"),frame=sample.optJSONObject("frame"),worker=sample.optJSONObject("worker"),net=sample.optJSONObject("network");if(parent==null)parent=new JSONObject();if(frame==null)frame=new JSONObject();if(worker==null)worker=new JSONObject();if(net==null)net=new JSONObject();
    boolean gecko="gecko".equals(expected.optString("engine")),mainObserved="page-main-world".equals(sample.optString("provenance"))&&sample.optJSONObject("mainWorld")!=null&&Boolean.TRUE.equals(sample.optJSONObject("mainWorld").opt("observed"));
    row(rows,"provenance","网页执行环境与来源",mainObserved?VERIFIED:UNCOVERED,mainObserved?"本次在页面主执行环境采集公开字段；页面可修改或伪造这些值，结果不是独立身份认证":"未取得页面主执行环境结果；隔离扩展世界的回退值仅作诊断，不能代表网页实际读取值");
    String ua=parent.optString("ua"),wanted=expected.optString("ua");int actual=major(ua),engine=expected.optInt("major",-1);boolean basic=!ua.isEmpty()&&ua.equals(wanted)&&actual>0&&engine>0&&actual==engine;
    row(rows,"ua","浏览器版本与网页信息",ua.isEmpty()||engine<=0||actual<=0?UNCOVERED:basic?VERIFIED:ISSUE,ua.isEmpty()||engine<=0?"未取得可核验的网页或内核版本":basic?"检查页面的 UA 与应用设置及已安装内核主版本一致":"观察到 UA 与应用设置或内核主版本不一致");
    JSONObject hints=parent.optJSONObject("hints");boolean hintsKnown=false;if(hints!=null){JSONArray brands=hints.optJSONArray("brands");if(brands!=null)for(int i=0;i<brands.length();i++)if(brands.optJSONObject(i)!=null&&brands.optJSONObject(i).optString("brand").matches("(?i).*(?:Chromium|Chrome|WebView).*"))hintsKnown=true;}row(rows,"hints","Client Hints 浏览器信息",!hintsKnown||engine<=0?UNCOVERED:hintsMatch(hints,engine)?VERIFIED:ISSUE,!hintsKnown?"当前页面未提供可核验的 Client Hints 品牌，不能据此认定所有来源一致":"仅核对返回的浏览器主版本；不是完整设备身份校验");
    JSONObject frameCoverage=contextCoverage(parent,frame),workerCoverage=contextCoverage(parent,worker);
    JSONObject navigatorFrame=navigatorIdentityCoverage(parent,frame,mainObserved,fresh),navigatorWorker=navigatorIdentityCoverage(parent,worker,mainObserved,fresh);
    row(rows,"navigator-frame","同源页面的平台与版本字段",navigatorFrame.optString("state"),navigatorIdentityDetail(navigatorFrame));
    row(rows,"navigator-worker","Dedicated Worker 的平台与版本字段",navigatorWorker.optString("state"),navigatorIdentityDetail(navigatorWorker));
    row(rows,"frame","同源嵌入页面一致性",frameCoverage.optString("state"),frameCoverage.optString("state").equals(VERIFIED)?"同源 srcdoc 的 UA、线程数、内存接口、语言列表及时区观测与主页面一致；不代表其他 API 已覆盖":frameCoverage.optString("state").equals(ISSUE)?"同源子页面存在已观测差异："+frameCoverage.optJSONArray("different"):"同源子页面采集不完整，未覆盖或类型无效："+frameCoverage.optJSONArray("missingOrInvalid"));
    boolean rendererComparable=observedField(parent,"renderer")&&observedField(worker,"renderer")&&!"unavailable".equals(parent.optString("renderer"))&&!"unavailable".equals(worker.optString("renderer"));
    boolean rendererSame=!rendererComparable||parent.optString("renderer").equals(worker.optString("renderer"));
    row(rows,"worker","Dedicated Worker 公开 JS 字段核对",rendererSame?workerCoverage.optString("state"):ISSUE,!rendererSame?"页面与 Dedicated Worker 图形观测不同；已保留差异":workerCoverage.optString("state").equals(VERIFIED)?"Dedicated Worker 的 UA、线程数、内存接口、语言列表及时区观测与主页面一致；这不验证 Worker 的 HTTP 请求头、图形或其他 API":workerCoverage.optString("state").equals(ISSUE)?"Dedicated Worker 存在已观测差异："+workerCoverage.optJSONArray("different"):"Dedicated Worker 采集不完整，未覆盖或类型无效："+workerCoverage.optJSONArray("missingOrInvalid"));
    JSONObject frameDisplay=displayCoverage(parent,frame),workerDisplay=displayCoverage(parent,worker);
    if(!mainObserved||!fresh)for(JSONObject display:new JSONObject[]{frameDisplay,workerDisplay})try{display.put("state",UNCOVERED);display.put("invalidated",true);}catch(JSONException ignored){}
    for(String context:new String[]{"frame","worker"}){JSONObject display="frame".equals(context)?frameDisplay:workerDisplay;String state=mainObserved?display.optString("state"):UNCOVERED;row(rows,"display-"+context,"frame".equals(context)?"同源页面的屏幕、DPR 与触摸信息":"Dedicated Worker 显示接口覆盖",state,!mainObserved?"未取得页面主执行环境结果":VERIFIED.equals(state)?"本次可比显示字段一致；旋转按屏幕长短边归一化，未比较视口宽高":ISSUE.equals(state)?"本次显示字段存在观测差异："+display.optJSONArray("different")+"；缩放或窗口状态也可能影响，不作泄漏判断":"接口未提供或采集不完整："+display.optJSONArray("missingOrInvalid")+"；Worker 通常不提供 screen / window 接口，不作错误判断");}
    JSONObject apiCoverage=apiCoverage(rows,sample,mainObserved,fresh);JSONObject apiContexts=apiContextCoverage(rows,sample,mainObserved,fresh);
    if(gecko)row(rows,"worker-header","Worker HTTP 请求 UA",UNCOVERED,"本次自检未采集 Worker 的服务端请求头。当前 Firefox SDK 的电脑版页面与 Worker 联网 UA 不保证一致；页面和 Worker 的 JS 字段相同不能验证这一项");
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
      row(rows,"header","内容脚本请求 UA 与网页核对",!fresh||headerUa.isEmpty()?UNCOVERED:headerUa.equals(ua)?VERIFIED:ISSUE,!fresh?"连接已变化，结果作废":headerUa.isEmpty()?"公开回显服务未返回可核对的 UA":headerUa.equals(ua)?"本次 Gecko 内容脚本请求的回显 UA 与页面一致；不包括 ChatGPT 主文档或 Worker 请求":"本次内容脚本回显 UA 与页面不同；这不是 ChatGPT 主文档或 Worker 的服务端日志");
      String acceptLanguage="";if(headers!=null){Iterator<String> keys=headers.keys();while(keys.hasNext()){String key=keys.next();if(key.equalsIgnoreCase("Accept-Language"))acceptLanguage=headers.optString(key);}}
      String first=acceptLanguage.split(",",2)[0].split(";",2)[0].trim();
      row(rows,"header-language","实际请求语言与页面核对",!fresh||first.isEmpty()||language.isEmpty()?UNCOVERED:first.equalsIgnoreCase(language)?VERIFIED:ISSUE,"仅核对本次 Gecko 内容脚本请求的服务回显与页面值；不是 ChatGPT 主文档请求的服务端日志，也不是 Java 客户端的模拟请求头");
    }else row(rows,"network","实际网络出口",UNCOVERED,"本次只检查浏览器信息，没有访问网络检测服务");
    row(rows,"cross-origin","跨源 iframe",UNCOVERED,"普通本机检查不访问跨源页面；主动受控检测页的跨源探针另行列出");
    row(rows,"shared-worker","Shared Worker",UNCOVERED,"本次仅创建 Dedicated Worker，没有 Shared Worker 观测");
    row(rows,"service-worker","Service Worker",UNCOVERED,"没有注册或改变网站 Service Worker；该执行环境未覆盖");
    row(rows,"native-setting","原生抗指纹设置回读",expected.optBoolean("rfpAcknowledged")?VERIFIED:UNCOVERED,expected.optBoolean("rfpAcknowledged")?(expected.optInt("level")>=2?"当前强化请求要求开启抗指纹，设置回读一致":"当前请求未开启抗指纹，设置回读一致")+"；这不证明具体指纹 API 保护或网页兼容性":"尚未取得与请求值一致的原生设置回读");
    row(rows,"dns","DNS 网络泄漏",UNCOVERED,"可查看内置加密 DNS 配置，但未进行权威 DNS 探针或网络抓包，不能证明解析没有绕行");row(rows,"udp","UDP / QUIC / TLS 等路径",UNCOVERED,"本次 HTTPS 查询不能覆盖所有协议或识别全部浏览器网络指纹");
    if(gecko&&!mainObserved)for(int i=0;i<rows.length();i++){JSONObject r=rows.optJSONObject(i);if(Arrays.asList("ua","hints","frame","worker","rtc","zone","language","header","header-language").contains(r.optString("key")))try{r.put("state",UNCOVERED);r.put("detail","页面主执行环境采集未完成；隔离扩展世界的值不能用于验证网页实际表现");}catch(Exception ignored){}}
    if(!fresh)for(int i=0;i<rows.length();i++){JSONObject r=rows.optJSONObject(i);if(!UNCOVERED.equals(r.optString("state")))try{r.put("state",UNCOVERED);r.put("detail","检查期间环境变化，结果已作废，请在连接稳定后重测");}catch(Exception ignored){}}
    String display=expected.optString("display");if(!"mobile".equals(display)&&!"desktop".equals(display))display="unspecified";
    JSONObject mobileIdentity=J.obj("schema",1,"display",display,"fields",new JSONArray(NAVIGATOR_IDENTITY_FIELDS),"frame",navigatorFrame,"worker",navigatorWorker,
        "scope","Current page-main-world platform/appVersion and the existing independent display observations; not a claimed phone model or HTTP identity proof",
        "deviceModelVerified",false,"httpHeadersVerified",false,"protectionVerified",false);
    return J.obj("at",System.currentTimeMillis(),"network",network,"fresh",fresh,"rows",rows,"signals",sample,"native",nativeResult,"contextCoverage",J.obj("requiredFields",new JSONArray(CONTEXT_FIELDS),"frame",frameCoverage,"worker",workerCoverage,"display",J.obj("fresh",fresh,"pageMainWorldObserved",mainObserved,"frame",frameDisplay,"worker",workerDisplay)),"mobileIdentityCoverage",mobileIdentity,"apiOperationCoverage",apiCoverage,"apiContextOperationCoverage",apiContexts,"apiProtectionVerified",false,"fullDesktopUaConsistency",false,"fingerprintTemplateAcceptance",false,"expected",expected,"scope",gecko?"页面主执行环境（若 CSP 允许）、同源 srcdoc、Dedicated Worker 公开 JS 字段及明确标注的 Gecko 内容脚本请求；没有 Worker HTTP 请求头观测或完整桌面指纹承诺，公开字段可被页面伪造":"本机检查页面及指定公开检测服务");
  }
}
