package local.pocketchat;

import android.app.NotificationManager;
import android.os.Bundle;
import org.json.*;
import java.io.File;

public class ProfileSessionTestActivity extends ContinuityFixtureActivity {
  final JSONArray checks=new JSONArray();int attempts;
  void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));}
  @Override public void onCreate(Bundle b){getSharedPreferences("chat",0).edit().putBoolean("networkConfigured",true).putString("networkMode","external").putBoolean("requireExternalVpn",false).putString("proxy","").putBoolean("pageMode",true).putBoolean("webNotificationAsked",true).putString("conversation",ORIGIN+"c/one").commit();super.onCreate(b);handler.postDelayed(()->ready(),100);}
  void ready(){if((session.navigating||session.entries.length()!=2)&&attempts++<100){handler.postDelayed(()->ready(),100);return;}check("An independent environment creates a real usable session",session.networkReady&&!session.navigating&&session.entries.length()==2);check("Session data and runtime folders are scoped to environment one",Profiles.slot(session.context)==1&&session.context.getFilesDir().getAbsolutePath().contains("profiles/env1")&&NativeNetwork.get(this).root.getAbsolutePath().contains("profiles/env1"));
    session.pending=J.obj("id","profile-service-fixture","expectedUrl",ORIGIN+"c/one","confirmedUrl",ORIGIN+"c/one","confirmed",true,"userKey","id:one-user");ChatService.begin(this);attempts=0;waiting();
  }
  void waiting(){boolean own=false;for(android.service.notification.StatusBarNotification n:getSystemService(NotificationManager.class).getActiveNotifications())if(n.getId()==4201)own=true;if((!ChatService.running||!own)&&attempts++<150){handler.postDelayed(()->waiting(),100);return;}check("Waiting service runs in the independent environment process",ChatService.running&&android.app.Application.getProcessName().endsWith(":profile1"));check("Independent environment uses a separate foreground notification",own);session.pending=null;ChatService.end(this);attempts=0;stopped();}
  void stopped(){if(ChatService.running&&attempts++<40){handler.postDelayed(()->stopped(),100);return;}check("Independent environment stops its own waiting service",!ChatService.running);try{J.write(new File(Profiles.global(this).getFilesDir(),"profile-session-results.json"),J.obj("checks",checks).toString(2));}catch(Exception ignored){}finish();}
}
