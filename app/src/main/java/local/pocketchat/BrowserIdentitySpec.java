package local.pocketchat;

import org.json.*;
import java.util.*;

/** Versioned desired identity. No arbitrary UA/hardware or JavaScript emulation. */
final class BrowserIdentitySpec {
  static final int SCHEMA=1;
  static final String MOBILE="standard-mobile", DESKTOP="standard-desktop", COMPATIBLE="compatibility-mobile", COMPATIBLE_DESKTOP="compatibility-desktop", RFP="native-rfp-experimental", RFP_DESKTOP="native-rfp-desktop-experimental";
  final String templateId,display,privacy,timezoneStrategy;
  final List<String> locales;
  BrowserIdentitySpec(String template,String display,String privacy,List<String> locales,String zone){
    this.templateId=template;this.display=display;this.privacy=privacy;
    this.locales=Collections.unmodifiableList(new ArrayList<>(locales));this.timezoneStrategy=zone;
  }
  static BrowserIdentitySpec preset(String id){
    if(DESKTOP.equals(id))return new BrowserIdentitySpec(id,"desktop","standard",Collections.emptyList(),"system");
    if(COMPATIBLE.equals(id))return new BrowserIdentitySpec(id,"mobile","compatibility",Collections.emptyList(),"system");
    if(COMPATIBLE_DESKTOP.equals(id))return new BrowserIdentitySpec(id,"desktop","compatibility",Collections.emptyList(),"system");
    if(RFP.equals(id))return new BrowserIdentitySpec(id,"mobile","native-rfp",Collections.emptyList(),"native-standardized");
    if(RFP_DESKTOP.equals(id))return new BrowserIdentitySpec(id,"desktop","native-rfp",Collections.emptyList(),"native-standardized");
    if(!MOBILE.equals(id))throw new IllegalArgumentException("未知环境模板");
    return new BrowserIdentitySpec(id,"mobile","standard",Collections.emptyList(),"system");
  }
  static BrowserIdentitySpec from(JSONObject value){
    if(value==null)return preset(MOBILE);
    if(value.has("schema")&&value.optInt("schema",-1)!=SCHEMA)throw new IllegalArgumentException("当前版本不支持此指纹配置版本");
    for(String field:Arrays.asList("ua","userAgent","timezone","canvas","webgl","audio","fonts","hardware"))if(value.has(field))throw new IllegalArgumentException("当前官方内核不支持自定义 "+field);
    ArrayList<String> locales=new ArrayList<>();JSONArray array=value.optJSONArray("locales");
    if(array!=null)for(int i=0;i<array.length();i++)locales.add(array.optString(i));
    return new BrowserIdentitySpec(value.optString("templateId",MOBILE),value.optString("display","mobile"),value.optString("privacy","standard"),locales,value.optString("timezoneStrategy","system"));
  }
  static BrowserIdentitySpec legacy(boolean desktop,int level){
    String privacy=level>=2?"native-rfp":level==0?"compatibility":"standard";
    return new BrowserIdentitySpec(level>=2?desktop?RFP_DESKTOP:RFP:level==0?desktop?COMPATIBLE_DESKTOP:COMPATIBLE:desktop?DESKTOP:MOBILE,desktop?"desktop":"mobile",privacy,Collections.emptyList(),level>=2?"native-standardized":"system");
  }
  boolean desktop(){return "desktop".equals(display);}
  int protectionLevel(){return "native-rfp".equals(privacy)?2:"compatibility".equals(privacy)?0:1;}
  String validate(){
    if(!Arrays.asList(MOBILE,DESKTOP,COMPATIBLE,COMPATIBLE_DESKTOP,RFP,RFP_DESKTOP).contains(templateId))return "当前版本不支持此模板";
    if(!"mobile".equals(display)&&!"desktop".equals(display))return "请选择真实 Firefox 手机版或电脑版显示";
    if(!Arrays.asList("standard","compatibility","native-rfp").contains(privacy))return "当前版本不支持此隐私策略";
    if(locales.size()>3)return "语言列表最多三项";
    for(String locale:locales)if(locale==null||locale.length()>64||!locale.matches("[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*")||Locale.forLanguageTag(locale).getLanguage().isEmpty())return "语言必须使用有效 BCP 47 标签，例如 zh-CN";
    Set<String> distinct=new HashSet<>();for(String locale:locales)if(!distinct.add(locale.toLowerCase(Locale.ROOT)))return "语言列表包含重复项";
    if(!"system".equals(timezoneStrategy)&&!"native-standardized".equals(timezoneStrategy))return "独立时区尚未实现；本版使用系统或原生标准化策略";
    if("native-standardized".equals(timezoneStrategy)&&!"native-rfp".equals(privacy))return "原生标准化时区仅随原生抗指纹策略启用";
    BrowserIdentitySpec expected=preset(templateId);
    if(!display.equals(expected.display)||!privacy.equals(expected.privacy)||!timezoneStrategy.equals(expected.timezoneStrategy))return "模板与显示、保护或时区策略不一致，请重新选择完整模板";
    return "";
  }
  JSONObject json(){return J.obj("schema",SCHEMA,"templateId",templateId,"display",display,"privacy",privacy,"locales",new JSONArray(locales),"timezoneStrategy",timezoneStrategy);}
  BrowserIdentitySpec withLocales(List<String> selected){return new BrowserIdentitySpec(templateId,display,privacy,selected,timezoneStrategy);}
  String label(){return "native-rfp".equals(privacy)?"Firefox 原生强化"+(desktop()?"电脑版":"手机版")+"（兼容性待验证）":"compatibility".equals(privacy)?"Firefox 兼容"+(desktop()?"电脑版":"手机版"):desktop()?"Firefox 标准电脑版":"Android / Firefox 标准手机版";}
}
