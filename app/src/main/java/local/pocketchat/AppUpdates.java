package local.pocketchat;

import android.app.job.*;
import android.content.*;
import android.net.Uri;
import android.os.Bundle;

/** Cross-process entry: app updates never inherit a browser profile or its cookies. */
final class AppUpdates {
  static final int ON_OPEN=4100,PERIODIC=4101;
  static Uri uri(Context c){return Uri.parse("content://"+c.getPackageName()+".app-updates");}
  static Bundle call(Context c,String action,Bundle extras){try{Bundle out=c.getContentResolver().call(uri(c),action,null,extras);return out==null?new Bundle():out;}catch(Exception e){Bundle out=new Bundle();out.putString("state","error");out.putString("message","更新服务暂时无法打开，请重新进入更新页");return out;}}
  static void schedule(Context context){Context c=Profiles.global(context);try{
    JobScheduler jobs=(JobScheduler)c.getSystemService(Context.JOB_SCHEDULER_SERVICE);if(jobs==null)return;
    if(!AppSettings.bool(c,"updateAutoCheck",true)){jobs.cancel(ON_OPEN);jobs.cancel(PERIODIC);return;}
    ComponentName service=new ComponentName(c,AppUpdateJob.class);
    if(jobs.getPendingJob(PERIODIC)==null)jobs.schedule(new JobInfo.Builder(PERIODIC,service).setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY).setPeriodic(AppUpdatePolicy.DAY).setPersisted(true).build());
    if(jobs.getPendingJob(ON_OPEN)==null)jobs.schedule(new JobInfo.Builder(ON_OPEN,service).setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY).setMinimumLatency(1000).build());
  }catch(Exception ignored){/* Manual checks remain available if the OS restricts scheduled work. */}}
  static void open(android.app.Activity a){a.startActivity(new Intent(a,AppUpdateActivity.class));}
}
