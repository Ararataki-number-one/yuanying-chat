package local.pocketchat;

import android.app.Activity;
import android.content.Intent;

/** Native workspace tabs keep one secondary screen above their caller. */
final class WorkspaceNavigation {
  static void select(Activity a,int current,int target){
    if(target==current)return;
    if(a instanceof WindowHomeActivity&&(target==0||target==3)){
      WindowHomeActivity home=(WindowHomeActivity)a;
      home.openWindow(home.lastWindow(),target==3?"network":"chat");return;
    }
    Intent intent;
    if(target==1)intent=new Intent(a,WindowHomeActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
    else if(target==2)intent=new Intent(a,DownloadCenterActivity.class);
    else if(target==4)intent=new Intent(a,AppSettingsActivity.class);
    else intent=new Intent(a,Profiles.activity(AppSettings.recentSlot(a)))
      .putExtra("openWindowAction",target==3?"network":"chat").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
    a.startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT));
    if(!(a instanceof WindowHomeActivity))a.finish();
  }
}
