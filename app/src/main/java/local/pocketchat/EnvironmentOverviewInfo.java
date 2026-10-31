package local.pocketchat;

import android.net.Uri;
import java.text.SimpleDateFormat;
import java.util.*;
import org.json.*;

/** Read-only presentation. Saved settings, native receipts and page observations stay distinct. */
final class EnvironmentOverviewInfo {
  static String clean(String value){return value==null?"":value.replaceAll("[\\p{Cntrl}]"," ").trim();}
  static String time(long at){return at<=0?"时间未记录":new SimpleDateFormat("MM-dd HH:mm:ss",Locale.getDefault()).format(new Date(at));}
  static String text(ChatSession s){
    StringBuilder out=new StringBuilder();NativeNetwork n=NativeNetwork.peek();String displayedIp="";
    if(s.internalNetwork()){
      String ip=n==null?"":n.exitIp;boolean verified=n!=null&&s.networkReady&&!s.offline&&!s.connecting&&s.guard.allowed()&&s.appliedIdentity.equals(s.networkIdentity())&&!n.starting&&n.connectionAdmission()==NetworkHealthPolicy.Admission.VERIFIED;
      out.append("固定出口 IP：").append(ip.isEmpty()||n==null||n.lastVerified<=0?"尚未核验":(verified?"":"上次核实 ")+clean(ip));
      if(n!=null&&!ip.isEmpty()&&n.lastVerified>0){displayedIp=ip;String host=Uri.parse(n.exitCheckUrl()).getHost();out.append("\n来源：固定出口核验 · ").append(host==null?"来源未记录":host).append("\n核验时间：").append(time(n.lastVerified));}
    }else{
      JSONObject ip=NetworkRegion.read(s.context);String address=ip.optString("ip");boolean owned=s.networkIdentity().equals(ip.optString("route"));
      out.append("出口 IP：").append(!owned||address.isEmpty()?"尚未观测":"上次观测 "+clean(address));
      if(owned&&!address.isEmpty()){displayedIp=address;out.append("\n来源：").append(ip.optString("source").isEmpty()?"未记录":clean(ip.optString("source"))).append("\n观测时间：").append(time(ip.optLong("at")));}
    }
    JSONObject regionRecord=NetworkRegion.read(s.context);String region=displayedIp.isEmpty()?"":NetworkRegion.region(s.context,displayedIp);
    out.append("\n出口地区：").append(region.isEmpty()?"未取得":"上次 IP 定位 "+clean(region));
    if(!region.isEmpty())out.append("\n地区来源：").append(regionRecord.optString("regionSource").isEmpty()?"未记录":clean(regionRecord.optString("regionSource"))).append("\n地区观测时间：").append(time(regionRecord.optLong("at")));
    GeckoSettings settings=s.web.getSettings();JSONObject accepted=settings.acceptedBrowserIdentity;
    out.append("\n\n浏览器模板：");
    try{out.append(settings.policyAcknowledged&&accepted.length()>0?BrowserIdentitySpec.from(accepted).label():"等待浏览器确认");}catch(Exception unavailable){out.append("尚未确认");}
    out.append("\n请求语言：").append(settings.requestedLocales.length==0?"等待浏览器确认":android.text.TextUtils.join("、",settings.requestedLocales));
    JSONObject report=s.audit.report,metadata=report.optJSONObject("observationMetadata"),signals=report.optJSONObject("signals");
    JSONObject main=signals==null?null:signals.optJSONObject("mainWorld"),page=signals==null?null:signals.optJSONObject("parent");
    boolean owned=metadata!=null&&s.environmentId.equals(metadata.opt("environmentId"))&&FingerprintObservationHistory.integer(metadata.opt("environmentGeneration"),s.environmentGeneration,s.environmentGeneration);
    boolean observed=owned&&signals!=null&&"page-main-world".equals(signals.optString("provenance"))&&main!=null&&Boolean.TRUE.equals(main.opt("observed"))&&page!=null;
    boolean current=observed&&s.audit.deepObservationCurrent();String label=current?"网页观测":"上次网页观测";
    out.append("\n网页实际语言：").append(observed&&AuditReport.observedField(page,"language")?clean(page.optString("language"))+"（"+label+"）":"尚未观测");
    out.append("\n网页实际时区：").append(observed&&AuditReport.observedField(page,"zone")?clean(page.optString("zone"))+"（"+label+"）":"尚未观测");
    if(observed)out.append("\n网页观测时间：").append(time(report.optLong("at")));
    out.append("\n\n连接进度：").append(clean(s.connectionStage));
    return out.toString();
  }
}
