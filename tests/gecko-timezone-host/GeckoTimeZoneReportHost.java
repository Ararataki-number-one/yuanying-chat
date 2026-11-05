package local.pocketchat;

import java.time.Instant;
import java.util.*;
import org.json.*;

/** Full production AuditReport; native readiness and page signals are inputs,
 * never evidence that an Android/Gecko implementation was actually executed. */
public final class GeckoTimeZoneReportHost {
  static final List<String> checks=new ArrayList<>();
  static void check(String name,boolean pass){if(!pass)throw new AssertionError(name);checks.add(name);}
  static JSONObject expected(String zone,long at){return J.obj("engine","gecko","timezoneStrategy","native-independent","timezoneRequestedZone",zone,"timezoneNativeReadback",true,"timezoneObservationStartedAt",at-100);}
  static JSONObject parent(String zone,int offset,long at){return J.obj("zone",zone,"offset",offset,"observedAt",at);}
  static String coverage(JSONObject parent,JSONObject expected,boolean main,boolean fresh,long received){return AuditReport.independentTimeZoneCoverage(parent,expected,main,fresh,received).optString("state");}
  static JSONObject row(JSONObject report,String key)throws JSONException{JSONArray rows=report.getJSONArray("rows");for(int i=0;i<rows.length();i++)if(key.equals(rows.getJSONObject(i).getString("key")))return rows.getJSONObject(i);throw new AssertionError("Missing row "+key);}
  public static void main(String[] args)throws Exception{
    long before=Instant.parse("2026-03-08T06:59:59Z").toEpochMilli(),after=Instant.parse("2026-03-08T07:00:01Z").toEpochMilli();
    check("DST before transition follows sampled timestamp",coverage(parent("America/New_York",300,before),expected("America/New_York",before),true,true,before+2000).equals("verified"));
    check("DST after transition follows sampled timestamp",coverage(parent("America/New_York",240,after),expected("America/New_York",after),true,true,after+2000).equals("verified"));
    check("Sample before DST boundary stays correct when received after boundary",coverage(parent("America/New_York",300,before),expected("America/New_York",before),true,true,after+2000).equals("verified"));
    check("Matching zone with wrong seasonal offset retains actual difference",coverage(parent("America/New_York",300,after),expected("America/New_York",after),true,true,after+1000).equals("issue"));
    long winter=Instant.parse("2026-01-01T12:00:00Z").toEpochMilli();
    check("Half hour DST offset is compared exactly",coverage(parent("Australia/Lord_Howe",-660,winter),expected("Australia/Lord_Howe",winter),true,true,winter+1000).equals("verified"));
    check("Quarter hour offset is compared exactly",coverage(parent("Asia/Kathmandu",-345,winter),expected("Asia/Kathmandu",winter),true,true,winter+1000).equals("verified"));
    for(String[] alias:new String[][]{{"UTC","Etc/UTC"},{"Asia/Kathmandu","Asia/Katmandu"},{"Europe/London","Africa/Abidjan"}})
      check("Equal offsets or uncanonicalized aliases cannot verify exact requested region "+Arrays.toString(alias),coverage(parent(alias[1],0,winter),expected(alias[0],winter),true,true,winter+1000).equals("uncovered"));
    JSONObject p=parent("UTC",0,winter),e=expected("UTC",winter);
    check("Native acknowledgement alone cannot stand in for page observation",coverage(new JSONObject(),e,true,true,winter+1000).equals("uncovered"));
    check("Isolated world cannot verify page timezone",coverage(p,e,false,true,winter+1000).equals("uncovered"));
    check("Old revision or native epoch invalidates page result",coverage(p,e,true,false,winter+1000).equals("uncovered"));
    JSONObject noAck=new JSONObject(e.toString());noAck.put("timezoneNativeReadback",false);check("No exact current ACK leaves custom timezone uncovered",coverage(p,noAck,true,true,winter+1000).equals("uncovered"));
    noAck.put("timezoneNativeReadback","true");check("String native ACK cannot coerce readiness",coverage(p,noAck,true,true,winter+1000).equals("uncovered"));
    for(Object invalid:new Object[]{JSONObject.NULL,"1767268800000",true,Double.NaN,-1L,winter-5000,winter+5000}){
      JSONObject copy=new JSONObject(p.toString());if(invalid instanceof Double&&Double.isNaN((Double)invalid)){copy.remove("observedAt");}else copy.put("observedAt",invalid);
      check("Missing/invalid/out-of-window observation time is uncovered "+String.valueOf(invalid),coverage(copy,e,true,true,winter+1000).equals("uncovered"));
    }
    JSONObject wrongOffset=new JSONObject(p.toString());wrongOffset.put("offset","0");check("String offset cannot verify actual sample",coverage(wrongOffset,e,true,true,winter+1000).equals("uncovered"));
    check("Observation received outside bounded window cannot verify",coverage(p,e,true,true,winter+60001).equals("uncovered"));
    long now=System.currentTimeMillis();JSONObject sampled=parent("UTC",0,now),sample=J.obj("provenance","page-main-world","mainWorld",J.obj("observed",true),"parent",sampled),wanted=expected("UTC",now);
    JSONObject report=AuditReport.build(sample,new JSONObject(),wanted,false,true),zone=row(report,"zone");
    check("Actual full report uses independent timezone label and actual page signal",zone.getString("name").equals("网页与独立时区偏移")&&zone.getString("state").equals("verified"));
    check("Verified page item explicitly excludes Worker and full fingerprint claims",zone.getString("detail").contains("只验证本次页面观测")&&!report.optBoolean("fingerprintTemplateAcceptance")&&!report.optBoolean("fullDesktopUaConsistency"));
    check("Full report custom no ACK cannot fall back to matching phone offset",row(AuditReport.build(sample,new JSONObject(),noAck,false,true),"zone").getString("state").equals("uncovered"));
    check("Full report old epoch always downgrades timezone",row(AuditReport.build(sample,new JSONObject(),wanted,false,false),"zone").getString("state").equals("uncovered"));
    JSONObject system=J.obj("engine","gecko","timezoneStrategy","system","offset",0);
    JSONObject systemRow=row(AuditReport.build(sample,new JSONObject(),system,false,true),"zone");check("Original system timezone logic and label remain",systemRow.getString("name").equals("网页与手机时区偏移")&&systemRow.getString("state").equals("verified"));
    system.put("timezoneStrategy","native-standardized");JSONObject rfp=row(AuditReport.build(sample,new JSONObject(),system,false,true),"zone");check("Original RFP standardized timezone remains uncovered",rfp.getString("name").equals("原生标准化时区观测")&&rfp.getString("state").equals("uncovered"));
    System.out.println(J.obj("status","passed","passed",checks.size(),"total",checks.size(),"checks",new JSONArray(checks)));
  }
}

/** Only resolves AuditReport's native-IP boundary; no networking is executed. */
final class BrowserNetworkGuard {static boolean localHost(String host){return host.equals("127.0.0.1")||host.equals("::1");}}
