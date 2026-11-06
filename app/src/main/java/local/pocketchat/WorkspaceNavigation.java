package local.pocketchat;

import android.app.Activity;
import android.content.Intent;

/** Native workspace tabs keep one secondary screen above their caller. */
final class WorkspaceNavigation {
  static final int NONE=-1,ENVIRONMENTS=0,NETWORK=1,DOWNLOADS=2,READING=3;
  static void select(Activity a,int current,int target){
    if(target<ENVIRONMENTS||target>READING||target==current)return;
    if(a instanceof WindowHomeActivity&&(target==NETWORK||target==READING)){
      WindowHomeActivity home=(WindowHomeActivity)a;
      int slot=home.lastWindow();
      if(slot<0){home.showProblem("请先创建或选择一个环境");return;}
      home.openWindow(slot,target==NETWORK?"network":"reading");return;
    }
    Intent intent;
    if(target==ENVIRONMENTS)intent=new Intent(a,WindowHomeActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
    else if(target==DOWNLOADS)intent=new Intent(a,DownloadCenterActivity.class);
    else {int slot=AppSettings.recentSlot(a);intent=slot<0?new Intent(a,WindowHomeActivity.class):new Intent(a,Profiles.activity(slot)).putExtra("openWindowAction",target==NETWORK?"network":"reading");intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);}
    a.startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT));
    if(!(a instanceof WindowHomeActivity))a.finish();
  }
}
