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
    root.addView(DesignUi.nav(this,4,n->WorkspaceNavigation.select(this,4,n),null));setContentView(root);refresh();
  }
  void refresh(){DesignUi.rebuild(box,true,()->DesignSettingsUi.render(this,box,()->refresh()));}
  @Override protected void onResume(){super.onResume();AppUpdates.schedule(this);if(box!=null)refresh();}
}
