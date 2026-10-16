package local.pocketchat;

import android.app.Activity;
import android.content.res.Configuration;
import android.os.Bundle;
import android.view.View;
import android.view.ViewGroup;

/** Native windows change colors in place, retaining browser, form and picker state. */
public class ThemedActivity extends Activity {
  @Override protected void onCreate(Bundle state){AppAppearance.attach(this);super.onCreate(state);AppAppearance.window(getWindow());}
  @Override public void setContentView(View view){super.setContentView(view);AppAppearance.apply(view);}
  @Override public void setContentView(View view,ViewGroup.LayoutParams params){super.setContentView(view,params);AppAppearance.apply(view);}
  @Override protected void onResume(){super.onResume();AppAppearance.refresh(this);}
  @Override public void onConfigurationChanged(Configuration config){super.onConfigurationChanged(config);AppAppearance.refresh(this);}
  @Override protected void onDestroy(){AppAppearance.detach(this);super.onDestroy();}
}
