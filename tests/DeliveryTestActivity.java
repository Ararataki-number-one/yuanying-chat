package local.pocketchat;

import org.json.*;

/** The old delivery ledger test is replaced by the browser-only retirement contract. */
public class DeliveryTestActivity extends WebReplyFixtureActivity {
  @Override void begin(){
    String draft=prefs.getString("draft","");
    for(boolean confirmed:new boolean[]{false,true}){
      JSONObject old=J.obj("id","legacy-delivery-"+confirmed,"kind","web","confirmed",confirmed,"prompt","old record");
      session.pending=old;prefs.edit().putString("pending",old.toString()).commit();session.webObserver.restorePending();
      check("Old delivery observation is retired: "+confirmed,session.pending==null&&!prefs.contains("pending")&&J.parse(prefs.getString("retiredWebObservation","{}")).optString("id").equals(old.optString("id")));
    }
    check("Retirement preserves the independent draft",draft.equals(prefs.getString("draft","")));
    check("No native delivery action is admitted",!BrowserRuntimePolicy.allows("submit")&&!BrowserRuntimePolicy.allows("regenerate")&&!BrowserRuntimePolicy.allows("poll")&&!BrowserRuntimePolicy.allows("latest"));
    check("Retirement produces no completion notice or service",completionPost()==0&&!ChatService.running);
    noResend("Legacy delivery migration never sends",0,()->report("delivery-results.json"));
  }
}
