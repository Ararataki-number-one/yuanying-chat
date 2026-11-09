package local.pocketchat;

import android.app.Activity;
import android.content.Intent;

/** Native workspace tabs keep one secondary screen above their caller. */
final class WorkspaceNavigation {
  // Compact conversation controls retain their original identities.
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
  /** Five-item native navigation uses AppHub page IDs, never compact indices. */
  static void selectPage(Activity a,int current,int target){
    if(target<AppHub.CHAT||target>AppHub.NETWORK||target==current)return;
    if(a instanceof MainActivity&&((MainActivity)a).hub!=null){((MainActivity)a).hub.select(target);return;}
    if(a instanceof WindowHomeActivity&&(target==AppHub.CHAT||target==AppHub.NETWORK)){
      WindowHomeActivity home=(WindowHomeActivity)a;int slot=home.lastWindow();
      if(slot<0){home.showProblem("请先创建或选择一个环境");return;}
      home.openWindow(slot,target==AppHub.NETWORK?"network":"chat");return;
    }
    Intent intent;
    if(target==AppHub.ENVIRONMENTS)intent=new Intent(a,WindowHomeActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
    else if(target==AppHub.DOWNLOADS)intent=new Intent(a,DownloadCenterActivity.class);
    else if(target==AppHub.SETTINGS)intent=new Intent(a,AppSettingsActivity.class);
    else{
      int slot=AppSettings.recentSlot(a);
      intent=slot<0?new Intent(a,WindowHomeActivity.class):target==AppHub.CHAT?EnvironmentOverviewUi.opening(a,slot):new Intent(a,Profiles.activity(slot)).putExtra("openWindowAction","network");
      intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
    }
    a.startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT));
    if(!(a instanceof WindowHomeActivity))a.finish();
  }
}
