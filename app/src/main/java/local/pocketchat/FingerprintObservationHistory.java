package local.pocketchat;

import org.json.*;
import java.net.URI;
import java.text.SimpleDateFormat;
import java.util.*;

/** Bounded local observations. Differences never attest fingerprint protection or leakage. */
final class FingerprintObservationHistory {
  static final int SCHEMA=1,LIMIT=8;
  static final String[] CORE={"ua","language","languages","offset","zone","cpu","memory","renderer","screen","pixelRatio","touch"};
  static final String[] APIS={"canvas","audio","fonts","webgl"};
  static final String[] GROUP={"environmentId","environmentGeneration","configurationRevision","engineVersion","appVersion","appVersionCode","source","sourceOrigin"};
  static boolean number(Object value,double min,double max){return value instanceof Number&&Double.isFinite(((Number)value).doubleValue())&&((Number)value).doubleValue()>=min&&((Number)value).doubleValue()<=max;}
  static boolean integer(Object value,long min,long max){return number(value,min,max)&&((Number)value).doubleValue()==((Number)value).longValue();}
  static String text(Object value,int limit){return value instanceof String?((String)value).substring(0,Math.min(limit,((String)value).length())):"";}
  static JSONObject object(JSONObject value,String key){JSONObject out=value==null?null:value.optJSONObject(key);return out==null?new JSONObject():out;}
  static String origin(Object value){
    try{URI uri=new URI(text(value,2048));if(!"https".equalsIgnoreCase(uri.getScheme())||uri.getHost()==null||uri.getUserInfo()!=null)return "";String host=uri.getHost().toLowerCase(Locale.ROOT);if(host.contains(":")&&!host.startsWith("["))host="["+host+"]";return "https://"+host+(uri.getPort()<0||uri.getPort()==443?"":":"+uri.getPort());}catch(Exception ignored){return "";}
  }
  static JSONObject screen(JSONObject value){
    if(value==null||!integer(value.opt("width"),1,65536)||!integer(value.opt("height"),1,65536))return null;
    int a=value.optInt("width"),b=value.optInt("height");JSONObject out=J.obj("short",Math.min(a,b),"long",Math.max(a,b));
    if(integer(value.opt("depth"),1,128))put(out,"depth",value.optInt("depth"));return out;
  }
  static void put(JSONObject value,String name,Object item){try{value.put(name,item);}catch(JSONException ignored){}}
  static JSONObject copy(JSONObject value){try{return new JSONObject(value.toString());}catch(JSONException ignored){return new JSONObject();}}
  static JSONObject core(JSONObject parent){
    JSONObject values=new JSONObject();
    for(String key:new String[]{"ua","language","zone","renderer"}){int limit="ua".equals(key)||"renderer".equals(key)?2048:256;Object raw=parent.opt(key);if(raw instanceof String&&!((String)raw).isEmpty()&&((String)raw).length()<=limit)put(values,key,raw);}
    JSONArray input=parent.optJSONArray("languages"),languages=new JSONArray();boolean valid=input!=null&&input.length()>0&&input.length()<=8;if(valid)for(int i=0;i<input.length();i++){Object raw=input.opt(i);if(!(raw instanceof String)||((String)raw).isEmpty()||((String)raw).length()>64){valid=false;break;}languages.put(raw);}if(valid)put(values,"languages",languages);
    if(integer(parent.opt("offset"),-1440,1440))put(values,"offset",parent.optInt("offset"));
    for(String key:new String[]{"cpu","memory"})if(parent.has(key)&&(parent.opt(key)==JSONObject.NULL||number(parent.opt(key),Double.MIN_VALUE,65536)))put(values,key,parent.opt(key));
    JSONObject display=screen(parent.optJSONObject("screen"));if(display!=null)put(values,"screen",display);
    JSONObject viewport=object(parent,"viewport");if(number(viewport.opt("pixelRatio"),.01,32))put(values,"pixelRatio",viewport.optDouble("pixelRatio"));if(integer(viewport.opt("touch"),0,64))put(values,"touch",viewport.optInt("touch"));
    return values;
  }
  static JSONObject probes(JSONObject sample){
    JSONObject input=sample.optJSONObject("apiChecks"),out=new JSONObject();if(input==null||!integer(input.opt("schema"),SCHEMA,SCHEMA)||!Boolean.TRUE.equals(input.opt("requested"))||!Boolean.FALSE.equals(input.opt("protectionVerified"))||!"page-main-world".equals(input.optString("source")))return out;
    put(out,"probeVersion",integer(input.opt("probeVersion"),1,100000)?input.optInt("probeVersion"):0);
    JSONObject values=object(input,"probes");for(String name:APIS){JSONObject value=values.optJSONObject(name);if(value==null)continue;String state=value.optString("state");if(!Arrays.asList("available","restricted","failed","uncovered").contains(state))continue;JSONObject item=J.obj("state",state);String hash=value.optString("hash");if(("available".equals(state)||"restricted".equals(state))&&hash.matches("[0-9a-f]{64}")&&"sha256".equals(value.optString("hashAlgorithm"))){put(item,"hash",hash);put(item,"hashAlgorithm","sha256");}put(out,name,item);}
    return out;
  }
  static JSONObject entry(JSONObject report,JSONObject metadata){
    if(report==null||metadata==null||!Boolean.TRUE.equals(report.opt("fresh"))||!integer(report.opt("at"),1,Long.MAX_VALUE))return null;
    String environment=text(metadata.opt("environmentId"),128).toLowerCase(Locale.ROOT);if(!environment.matches("[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")||!integer(metadata.opt("environmentGeneration"),0,Integer.MAX_VALUE))return null;
    JSONObject sample=object(report,"signals"),main=object(sample,"mainWorld"),parent=sample.optJSONObject("parent");
    if(!"page-main-world".equals(sample.optString("provenance"))||!Boolean.TRUE.equals(main.opt("observed"))||parent==null)return null;
    JSONObject values=core(parent);if(values.length()==0)return null;
    JSONObject out=J.obj("schema",SCHEMA,"at",report.optLong("at"),"environmentId",environment,"environmentGeneration",metadata.optInt("environmentGeneration"),"source","page-main-world","sourceOrigin",origin(metadata.opt("sourceOrigin")),"values",values,"apis",probes(sample),"protectionVerified",false,"leakVerdict",false);
    for(String key:new String[]{"configurationRevision","appVersionCode"})put(out,key,integer(metadata.opt(key),0,Long.MAX_VALUE)?metadata.optLong(key):0);
    for(String key:new String[]{"engineVersion","appVersion","executionId"})put(out,key,text(metadata.opt(key),128));
    return out;
  }
  static boolean completeGroup(JSONObject value){return !value.optString("environmentId").isEmpty()&&integer(value.opt("environmentGeneration"),0,Integer.MAX_VALUE)&&value.optLong("configurationRevision")>0&&value.optLong("appVersionCode")>0&&!value.optString("engineVersion").isEmpty()&&!value.optString("appVersion").isEmpty()&&!value.optString("sourceOrigin").isEmpty();}
  static boolean same(Object first,Object second){
    if(first instanceof Number&&second instanceof Number)return Double.compare(((Number)first).doubleValue(),((Number)second).doubleValue())==0;
    if(first instanceof JSONObject&&second instanceof JSONObject){JSONObject a=(JSONObject)first,b=(JSONObject)second;Set<String> keys=new TreeSet<>();for(Iterator<String> i=a.keys();i.hasNext();)keys.add(i.next());Set<String> other=new TreeSet<>();for(Iterator<String> i=b.keys();i.hasNext();)other.add(i.next());if(!keys.equals(other))return false;for(String key:keys)if(!same(a.opt(key),b.opt(key)))return false;return true;}
    if(first instanceof JSONArray&&second instanceof JSONArray){JSONArray a=(JSONArray)first,b=(JSONArray)second;if(a.length()!=b.length())return false;for(int i=0;i<a.length();i++)if(!same(a.opt(i),b.opt(i)))return false;return true;}
    return Objects.equals(first,second);
  }
  static boolean sameGroup(JSONObject a,JSONObject b){if(!completeGroup(a)||!completeGroup(b))return false;for(String key:GROUP)if(!same(a.opt(key),b.opt(key)))return false;return true;}
  static boolean sameEnvironment(JSONObject a,JSONObject b){return a.optString("environmentId").equals(b.optString("environmentId"))&&a.optInt("environmentGeneration",-1)==b.optInt("environmentGeneration",-2);}
  static JSONArray differences(JSONObject before,JSONObject now){JSONArray out=new JSONArray();for(String key:CORE)if(before.has(key)&&now.has(key)&&!same(before.opt(key),now.opt(key)))out.put(key);return out;}
  static JSONObject comparison(JSONArray history,JSONObject current){
    JSONObject previous=null,apiPrevious=null;JSONObject api=object(current,"apis");int version=api.optInt("probeVersion");
    for(int i=history.length()-1;i>=0;i--){JSONObject candidate=history.optJSONObject(i);if(candidate==null||!sameGroup(candidate,current))continue;if(previous==null)previous=candidate;if(apiPrevious==null&&version>0&&object(candidate,"apis").optInt("probeVersion")==version)apiPrevious=candidate;}
    JSONArray changes=new JSONArray(),uncompared=new JSONArray(),apiChanges=new JSONArray();JSONObject now=object(current,"values");
    if(previous!=null){JSONObject before=object(previous,"values");for(String key:CORE){if(!before.has(key)||!now.has(key)){uncompared.put(key);continue;}if(!same(before.opt(key),now.opt(key)))changes.put(key);}}
    if(apiPrevious!=null){JSONObject before=object(apiPrevious,"apis");for(String name:APIS){String first=object(before,name).optString("hash"),second=object(api,name).optString("hash");if(!first.isEmpty()&&!second.isEmpty()&&!first.equals(second))apiChanges.put(name);}}
    JSONObject last=history.optJSONObject(history.length()-1);JSONArray reasons=new JSONArray(),diagnosticChanges=new JSONArray();if(previous==null&&last!=null&&sameEnvironment(last,current)){for(String key:GROUP)if(!same(last.opt(key),current.opt(key)))reasons.put(key);diagnosticChanges=differences(object(last,"values"),now);}
    return J.obj("state",previous!=null?"comparable":history.length()==0?"first-observation":"separate-context","referenceAt",previous==null?0:previous.optLong("at"),"apiReferenceAt",apiPrevious==null?0:apiPrevious.optLong("at"),"changedFields",changes,"uncomparedFields",uncompared,"apiOutputChanges",apiChanges,"acrossExecution",previous!=null&&!previous.optString("executionId").isEmpty()&&!current.optString("executionId").isEmpty()&&!previous.optString("executionId").equals(current.optString("executionId")),"separationReasons",reasons,"diagnosticChangedFields",diagnosticChanges,"diagnosticReferenceAt",previous==null&&last!=null&&sameEnvironment(last,current)?last.optLong("at"):0,"diagnosticOnly",true,"normalization","Screen rotation is normalized; viewport dimensions are excluded. API output differences may reflect randomization or standardization.","protectionVerified",false,"leakVerdict",false);
  }
  static JSONArray record(JSONArray history,JSONObject report,JSONObject metadata){
    JSONObject value=entry(report,metadata);if(value==null)return restore(history);JSONArray out=restore(history,value.optString("environmentId"),value.optInt("environmentGeneration"));put(value,"comparison",comparison(out,value));out.put(value);return last(out);
  }
  static JSONArray last(JSONArray input){JSONArray out=new JSONArray();for(int i=Math.max(0,input.length()-LIMIT);i<input.length();i++)out.put(input.optJSONObject(i));return out;}
  static JSONArray restore(JSONArray saved){
    JSONArray out=new JSONArray();if(saved==null)return out;
    for(int i=Math.max(0,saved.length()-64);i<saved.length();i++){
      JSONObject old=saved.optJSONObject(i);if(old==null||!integer(old.opt("schema"),SCHEMA,SCHEMA)||!integer(old.opt("at"),1,Long.MAX_VALUE)||!"page-main-world".equals(old.optString("source")))continue;
      JSONObject values=old.optJSONObject("values");if(values==null)continue;
      // Reconstruct through the same whitelist instead of trusting saved arbitrary objects.
      JSONObject parent=copy(values),display=values.optJSONObject("screen");if(display!=null){JSONObject normalized=J.obj("width",display.opt("short"),"height",display.opt("long"));if(display.has("depth"))put(normalized,"depth",display.opt("depth"));put(parent,"screen",normalized);}
      put(parent,"viewport",J.obj("pixelRatio",values.opt("pixelRatio"),"touch",values.opt("touch")));
      JSONObject apis=object(old,"apis"),sample=J.obj("provenance","page-main-world","mainWorld",J.obj("observed",true),"parent",parent,"apiChecks",J.obj("schema",SCHEMA,"requested",true,"source","page-main-world","probeVersion",apis.opt("probeVersion"),"protectionVerified",false,"probes",apis));
      JSONObject clean=entry(J.obj("fresh",true,"at",old.opt("at"),"signals",sample),old);if(clean!=null){put(clean,"comparison",comparison(out,clean));out.put(clean);out=last(out);}
    }
    return out;
  }
  static JSONArray restore(JSONArray saved,String environmentId,int generation){JSONArray out=new JSONArray(),clean=restore(saved);for(int i=0;i<clean.length();i++){JSONObject value=clean.optJSONObject(i);if(value.optString("environmentId").equals(environmentId)&&value.optInt("environmentGeneration",-1)==generation)out.put(value);}return out;}
  static String name(String key){switch(key){case "ua":return "UA";case "language":return "语言";case "languages":return "语言列表";case "offset":return "时区偏移";case "zone":return "时区名称";case "cpu":return "线程数";case "memory":return "内存接口";case "renderer":return "图形描述";case "screen":return "屏幕";case "pixelRatio":return "DPR";case "touch":return "触摸点数";case "configurationRevision":return "配置版本";case "engineVersion":return "内核版本";case "appVersion":case "appVersionCode":return "应用版本";case "source":case "sourceOrigin":return "检测来源";default:return key;}}
  static String names(JSONArray list){StringJoiner out=new StringJoiner("、");if(list!=null)for(int i=0;i<list.length();i++)out.add(name(list.optString(i)));return out.toString();}
  static String summary(JSONArray saved){
    JSONArray history=restore(saved);if(history.length()==0)return "尚无真实页面观测。主动检查后，最近八次记录仅保存在当前环境的本地加密存储中。";
    StringBuilder text=new StringBuilder("最近 ").append(history.length()).append(" 次页面观测（最多八次，本地加密保存）");SimpleDateFormat time=new SimpleDateFormat("MM-dd HH:mm:ss",Locale.getDefault());
    for(int i=history.length()-1;i>=0;i--){JSONObject value=history.optJSONObject(i),comparison=object(value,"comparison");text.append("\n\n").append(time.format(new Date(value.optLong("at")))).append(" · 配置 ").append(value.optLong("configurationRevision")).append("\n").append(value.optString("sourceOrigin").isEmpty()?"来源未确认":value.optString("sourceOrigin")).append("\n应用 ").append(value.optString("appVersion").isEmpty()?"未知":value.optString("appVersion")).append(" · ").append(value.optString("engineVersion"));
      String state=comparison.optString("state");if("first-observation".equals(state))text.append("\n首次记录，尚无同来源参照");else if("separate-context".equals(state)){text.append("\n来源、配置或版本不同，分别保留，未直接判断异常");JSONArray reasons=comparison.optJSONArray("separationReasons"),diagnostic=comparison.optJSONArray("diagnosticChangedFields");if(reasons!=null&&reasons.length()>0)text.append("（").append(names(reasons)).append("）");if(diagnostic!=null&&diagnostic.length()>0)text.append("\n与上一条仅作并列对照：").append(names(diagnostic)).append("有变化，不作同组校验");}else{JSONArray changes=comparison.optJSONArray("changedFields");text.append(changes!=null&&changes.length()>0?"\n观测变化："+names(changes):"\n同来源、同配置和版本的可比字段未变");if(comparison.optBoolean("acrossExecution"))text.append("（跨运行记录）");JSONArray apis=comparison.optJSONArray("apiOutputChanges");if(apis!=null&&apis.length()>0)text.append("\n图形／音频输出变化：").append(names(apis)).append("；可能与随机化或标准化有关");}
      JSONObject values=object(value,"values");for(String key:CORE)if(values.has(key))text.append("\n").append(name(key)).append("：").append(values.opt(key)==JSONObject.NULL?"接口未提供":values.opt(key));JSONObject apis=object(value,"apis");for(String api:APIS){JSONObject observation=apis.optJSONObject(api);if(observation!=null)text.append("\n").append(api).append("：").append(observation.optString("state")).append(observation.optString("hash").isEmpty()?"":" · "+observation.optString("hash"));}
    }
    return text.append("\n\n屏幕旋转已归一化，键盘和视口尺寸变化不作指纹异常；缺失字段未作通过判断。记录变化不等于泄漏，也不证明原生保护失效。").toString();
  }
}
