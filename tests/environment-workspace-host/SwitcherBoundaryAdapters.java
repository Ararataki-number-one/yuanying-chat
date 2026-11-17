package local.pocketchat;

import android.app.Activity;
import android.content.Intent;
import org.json.JSONObject;

final class ProfileCatalog {
  static final ProfileCatalog instance=new ProfileCatalog();
  JSONObject current;JSONObject replaceOnSecondRead;
  int reads,opened,openedSlot=-1;
  static ProfileCatalog get(Activity activity){return instance;}
  JSONObject item(int slot){reads++;if(reads==2&&replaceOnSecondRead!=null)current=replaceOnSecondRead;return current;}
  void opened(int slot){opened++;openedSlot=slot;}
  void reset(JSONObject row){current=row;replaceOnSecondRead=null;reads=0;opened=0;openedSlot=-1;}
}
final class EnvironmentOverviewUi {
  static int openings;
  static Intent opening(Activity activity,int slot){
    openings++;
    return new Intent(activity,Profiles.activity(slot)).putExtra("openWindowAction","chat").putExtra("hostOverviewMarker",true).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_REORDER_TO_FRONT);
  }
  static Intent browserOpening(Activity activity,int slot){return opening(activity,slot).putExtra("openBrowserDirect",true);}
  static Intent detailsOpening(Activity activity,int slot){return opening(activity,slot).putExtra("openWindowAction","overview");}
}

/** Only engine and Activity identity; no document, reload or URI API exists. */
class BrowserActivity extends Activity {
  final int slot;BrowserActivity(int slot){this.slot=slot;}
  static final class Window1 extends BrowserActivity {Window1(){super(1);}}
  static Class<?> activity(int slot){if(slot==0)return BrowserActivity.class;if(slot==1)return Window1.class;throw new AssertionError("Unconfigured Chromium boundary");}
}
