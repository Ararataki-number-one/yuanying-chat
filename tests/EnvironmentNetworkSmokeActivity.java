package local.pocketchat;

import android.os.Bundle;
import org.json.*;
import java.io.File;

/** Opt-in real public-service smoke test; account document is still a local fixture. */
public class EnvironmentNetworkSmokeActivity extends ContinuityFixtureActivity {
  int tries;
  @Override public void onCreate(Bundle b){if(!getPackageName().endsWith(".test"))throw new IllegalStateException();getSharedPreferences("chat",0).edit().clear().putBoolean("networkConfigured",true).putString("networkMode","external").putBoolean("requireExternalVpn",false).putBoolean("pageMode",true).putBoolean("webNotificationAsked",true).putString("conversation",ORIGIN+"c/public-check-smoke").commit();super.onCreate(b);handler.postDelayed(()->ready(),100);}
  void ready(){if((!session.networkReady||session.navigating)&&tries++<80){handler.postDelayed(()->ready(),100);return;}session.audit.start(true,()->{JSONObject report=session.audit.report;JSONArray rows=report.optJSONArray("rows"),checks=new JSONArray();checks.put(J.obj("name","Real native IPv4 service returns valid address","pass",AuditReport.v4(report.optJSONObject("native").optString("ip"))));JSONObject ipv4=EnvironmentAuditTestActivity.row(report,"ipv4");checks.put(J.obj("name","Real browser, Worker and native IPv4 paths agree","pass",AuditReport.VERIFIED.equals(ipv4.optString("state"))));checks.put(J.obj("name","Public service report keeps DNS coverage honest","pass",AuditReport.UNCOVERED.equals(EnvironmentAuditTestActivity.row(report,"dns").optString("state"))));try{J.write(new File(getFilesDir(),"environment-network-smoke.json"),J.obj("checks",checks,"rows",rows,"fresh",report.optBoolean("fresh"),"scope","Real public-service reachability on test emulator; no account requests; raw IPs and device signals omitted").toString(2));}catch(Exception ignored){}if(getIntent().getBooleanExtra("showAudit",false))EnvironmentAuditUi.show(this);});}
}
