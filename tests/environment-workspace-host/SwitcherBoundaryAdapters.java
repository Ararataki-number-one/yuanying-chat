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
}
