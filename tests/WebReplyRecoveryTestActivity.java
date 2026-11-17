package local.pocketchat;

import org.json.*;

/** Upgrade-only fixture: legacy records are archived and never resumed. */
public class WebReplyRecoveryTestActivity extends WebReplyFixtureActivity {
  @Override void begin(){if(getIntent().getBooleanExtra("restore",false)){restore();return;}
    boolean uncertain=getIntent().getBooleanExtra("uncertain",false);
    JSONObject job=J.obj("id","legacy-upgrade-fixture","kind","web","confirmed",!uncertain,"prompt","旧版检测记录","expectedUrl",ORIGIN+"c/web-test");
    prefs.edit().putString("pending",job.toString()).putString("draft","independent upgrade draft").commit();
    write("web-recovery-stage.json",J.obj("waiting",true,"uncertain",uncertain,"id",job.optString("id"),"contract","browser-result-removal-v1"));
  }
  void restore(){check("Upgrade removes the active old pending cursor",session.pending==null&&!prefs.contains("pending"));
    check("Upgrade retains the old record without result inspection",J.parse(prefs.getString("retiredWebObservation","{}")).optString("id").equals("legacy-upgrade-fixture"));
    check("Upgrade does not start a reply service or completion notice",!ChatService.running&&completionPost()==0);
    check("Upgrade preserves an independent draft",prefs.getString("draft","").equals("independent upgrade draft"));
    noResend("Upgrade performs zero website submissions",0,()->report(getIntent().getBooleanExtra("uncertain",false)?"web-uncertain-recovery-results.json":"web-recovery-results.json"));
  }
}
