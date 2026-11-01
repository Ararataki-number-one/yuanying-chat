package local.pocketchat;

import android.net.Uri;
import java.text.SimpleDateFormat;
import java.util.*;
import org.json.*;

/** Read-only presentation. Saved settings, native receipts and page observations stay distinct. */
final class EnvironmentOverviewInfo {
  static String clean(String value){return value==null?"":value.replaceAll("[\\p{Cntrl}]"," ").trim();}
  static String time(long at){return at<=0?"时间未记录":new SimpleDateFormat("MM-dd HH:mm:ss",Locale.getDefault()).format(new Date(at));}
  static final class Snapshot {
    String ip="",ipLabel="出口 IP",ipValue="尚未观测",ipSource="",ipTime="",region="",regionSource="",regionTime="";
    String browser="等待浏览器确认",language="等待浏览器确认",pageLanguage="尚未观测",zone="尚未观测",observedAt="",connection="正在准备环境";
    boolean verified,observed,current;
  }
  static Snapshot read(ChatSession s){
    Snapshot value=new Snapshot();if(s==null)return value;
    NativeNetwork n=NativeNetwork.peek();
    if(s.internalNetwork()){
      String ip=n==null?"":n.exitIp;value.verified=n!=null&&s.networkReady&&!s.offline&&!s.connecting&&s.guard.allowed()&&s.appliedIdentity.equals(s.networkIdentity())&&!n.starting&&n.connectionAdmission()==NetworkHealthPolicy.Admission.VERIFIED;
      value.ipLabel="固定出口 IP";value.ipValue=ip.isEmpty()||n==null||n.lastVerified<=0?"尚未核验":(value.verified?"":"上次核实 ")+clean(ip);
      if(n!=null&&!ip.isEmpty()&&n.lastVerified>0){value.ip=clean(ip);String host=Uri.parse(n.exitCheckUrl()).getHost();value.ipSource="固定出口核验 · "+(host==null?"来源未记录":host);value.ipTime=time(n.lastVerified);}
    }else{
      JSONObject ip=NetworkRegion.read(s.context);String address=ip.optString("ip");boolean owned=s.networkIdentity().equals(ip.optString("route"));
      value.ipValue=!owned||address.isEmpty()?"尚未观测":"上次观测 "+clean(address);
      if(owned&&!address.isEmpty()){value.ip=clean(address);value.ipSource=ip.optString("source").isEmpty()?"未记录":clean(ip.optString("source"));value.ipTime=time(ip.optLong("at"));}
    }
    JSONObject regionRecord=NetworkRegion.read(s.context);value.region=value.ip.isEmpty()?"":clean(NetworkRegion.region(s.context,value.ip));
    if(!value.region.isEmpty()){value.regionSource=regionRecord.optString("regionSource").isEmpty()?"未记录":clean(regionRecord.optString("regionSource"));value.regionTime=time(regionRecord.optLong("at"));}
    GeckoSettings settings=s.web.getSettings();JSONObject accepted=settings.acceptedBrowserIdentity;
    try{value.browser=settings.policyAcknowledged&&accepted.length()>0?BrowserIdentitySpec.from(accepted).label():"等待浏览器确认";}catch(Exception unavailable){value.browser="尚未确认";}
    value.language=settings.requestedLocales.length==0?"等待浏览器确认":android.text.TextUtils.join("、",settings.requestedLocales);
    JSONObject report=s.audit.report,metadata=report.optJSONObject("observationMetadata"),signals=report.optJSONObject("signals");
    JSONObject main=signals==null?null:signals.optJSONObject("mainWorld"),page=signals==null?null:signals.optJSONObject("parent");
    boolean owned=metadata!=null&&s.environmentId.equals(metadata.opt("environmentId"))&&FingerprintObservationHistory.integer(metadata.opt("environmentGeneration"),s.environmentGeneration,s.environmentGeneration);
    boolean observed=owned&&signals!=null&&"page-main-world".equals(signals.optString("provenance"))&&main!=null&&Boolean.TRUE.equals(main.opt("observed"))&&page!=null;
    value.observed=observed;value.current=observed&&s.audit.deepObservationCurrent();String label=value.current?"网页观测":"上次网页观测";
    value.pageLanguage=observed&&AuditReport.observedField(page,"language")?clean(page.optString("language"))+"（"+label+"）":"尚未观测";
    value.zone=observed&&AuditReport.observedField(page,"zone")?clean(page.optString("zone"))+"（"+label+"）":"尚未观测";
    if(observed)value.observedAt=time(report.optLong("at"));value.connection=clean(s.connectionStage);return value;
  }
  static String text(ChatSession s){
    Snapshot v=read(s);StringBuilder out=new StringBuilder(v.ipLabel+"："+v.ipValue);
    if(!v.ip.isEmpty())out.append("\n来源：").append(v.ipSource).append(v.ipLabel.equals("固定出口 IP")?"\n核验时间：":"\n观测时间：").append(v.ipTime);
    out.append("\n出口地区：").append(v.region.isEmpty()?"未取得":"上次 IP 定位 "+v.region);
    if(!v.region.isEmpty())out.append("\n地区来源：").append(v.regionSource).append("\n地区观测时间：").append(v.regionTime);
    out.append("\n\n浏览器模板：").append(v.browser).append("\n请求语言：").append(v.language);
    out.append("\n网页实际语言：").append(v.pageLanguage).append("\n网页实际时区：").append(v.zone);
    if(v.observed)out.append("\n网页观测时间：").append(v.observedAt);
    out.append("\n\n连接进度：").append(v.connection);
    return out.toString();
  }
}
