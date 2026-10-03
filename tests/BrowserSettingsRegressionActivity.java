package local.pocketchat;

import android.os.*;
import android.widget.EditText;
import org.json.*;
import java.io.File;

/** Device regression using intercepted test pages, never a real account or proxy. */
public class BrowserSettingsRegressionActivity extends ContinuityFixtureActivity {
  final JSONArray checks=new JSONArray();int attempts;JSONObject original;
  void check(String label,boolean ok){checks.put(J.obj("name",label,"pass",ok));}
  @Override public void onCreate(Bundle state){getSharedPreferences("chat",0).edit().clear().putBoolean("networkConfigured",true).putString("networkMode","external").putBoolean("requireExternalVpn",false).putBoolean("pageMode",true).putBoolean("webNotificationAsked",true).putString("conversation",ORIGIN+"c/settings-regression").commit();super.onCreate(state);handler.postDelayed(this::begin,100);}
  void begin(){if(session.navigating||!session.state.optBoolean("composer")){if(attempts++<80){handler.postDelayed(this::begin,100);return;}check("Fixture became ready",false);write();return;}original=EnvironmentEditorUi.current(this);JSONObject candidate=J.parse(original.toString());try{candidate.put("desktopSite",!original.optBoolean("desktopSite"));}catch(Exception ignored){}
    JSONObject pending=session.pending;session.pending=J.obj("id","fixture-protected");boolean refused=!EnvironmentEditorUi.apply(this,candidate,new EditText(this));check("Pending question blocks configuration without being cleared",refused&&session.pending!=null&&session.privacy.wantsDesktop()==original.optBoolean("desktopSite"));session.pending=pending;
    JSONObject stale=session.state;long priorEpoch=session.stateEpoch;session.state=J.obj("busy",true,"url",remote.getUrl());session.stateEpoch=session.navigationEpoch-1;check("Busy result from an earlier document is ignored",!EnvironmentEditorUi.browserBusy(session));session.state=stale;session.stateEpoch=priorEpoch;
    try{session.state.put("busy",true);}catch(Exception ignored){}session.stateEpoch=session.navigationEpoch;session.navigating=true;session.connecting=true;session.recoveryScheduled=true;long connection=session.connectionEpoch,recovery=session.recoveryToken;android.webkit.WebView same=remote;
    EnvironmentEditorUi.applySafely(this,candidate,new EditText(this),ok->{
      check("Fresh idle inspection permits save despite cached busy and transient work",ok);
      check("Display mode was saved for the selected environment",session.privacy.wantsDesktop()==candidate.optBoolean("desktopSite"));
      check("Cancelled connection and retry callbacks become stale",session.connectionEpoch>connection&&session.recoveryToken>recovery);
      check("Settings reuse the existing WebView",remote==same&&session.web==same);check("Reservation is released after save",!session.operation);write();
    });
  }
  void write(){try{J.write(new File(getFilesDir(),"browser-settings-regression.json"),J.obj("checks",checks).toString(2));}catch(Exception ignored){}}
}
