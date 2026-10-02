package local.pocketchat;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.widget.LinearLayout;

/** Opening app-wide settings from the manager requires no WebView or account session. */
public class AppSettingsActivity extends Activity {
  LinearLayout box;
  @Override public void onCreate(Bundle state){
    super.onCreate(state);LinearLayout root=DesignUi.screen(this);box=DesignUi.body(this,root,"应用设置",()->finish());
    root.addView(DesignUi.nav(this,4,n->{
      if(n==4)return;
      if(n==1)startActivity(new Intent(this,WindowHomeActivity.class).addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT));
      else if(n==2)startActivity(new Intent(this,DownloadCenterActivity.class));
      else startActivity(new Intent(this,Profiles.activity(AppSettings.recentSlot(this))).putExtra("openWindowAction",n==3?"network":"chat").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_REORDER_TO_FRONT));
    },null));setContentView(root);refresh();
  }
  void refresh(){box.removeAllViews();DesignSettingsUi.render(this,box,()->refresh());}
  @Override protected void onResume(){super.onResume();if(box!=null)refresh();}
}
