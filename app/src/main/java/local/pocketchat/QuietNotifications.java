package local.pocketchat;

import android.app.*;
import android.content.Context;
import android.os.Build;
import android.os.Process;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.List;

/** Required services stay silent. Completion reminders are an explicit background option. */
final class QuietNotifications {
  static final String REPLY_BACKGROUND="reply-background-quiet-v2";
  static final String NETWORK_BACKGROUND="network-background-quiet-v2";
  private static boolean migrated;

  // Only these processes host our Activities. Gecko child processes and the
  // managed network service must not masquerade as a visible application.
  static boolean uiProcess(String name,String app){if(app.equals(name))return true;for(int slot=1;slot<Profiles.MAX;slot++)if((app+":profile"+slot).equals(name))return true;return false;}
  static boolean visibleImportance(int importance){return importance==ActivityManager.RunningAppProcessInfo.IMPORTANCE_FOREGROUND||importance==ActivityManager.RunningAppProcessInfo.IMPORTANCE_VISIBLE;}
  static JSONObject foregroundEvidence(Context c){
    JSONArray owners=new JSONArray();boolean foreground=false;
    try{ActivityManager manager=c.getSystemService(ActivityManager.class);List<ActivityManager.RunningAppProcessInfo> processes=manager==null?null:manager.getRunningAppProcesses();if(processes==null)return J.obj("known",false,"foreground",true,"processes",owners);
      for(ActivityManager.RunningAppProcessInfo process:processes)if(process.uid==Process.myUid()&&uiProcess(process.processName,c.getPackageName())){boolean visible=visibleImportance(process.importance);foreground|=visible;owners.put(J.obj("process",process.processName,"pid",process.pid,"importance",process.importance,"visible",visible));}
      return J.obj("known",owners.length()>0,"foreground",owners.length()==0||foreground,"processes",owners);
    }catch(Exception unavailable){return J.obj("known",false,"foreground",true,"processes",owners);}
  }
  static boolean appForeground(Context c){return foregroundEvidence(c).optBoolean("foreground",true);}
  static boolean backgroundCompletionAllowed(Context c){
    if(!AppSettings.backgroundCompletionNotice(c)||appForeground(c))return false;
    NotificationManager manager=c.getSystemService(NotificationManager.class);
    return manager!=null&&manager.areNotificationsEnabled()&&(Build.VERSION.SDK_INT<33||c.checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS)==android.content.pm.PackageManager.PERMISSION_GRANTED);
  }
  static void clearCompletions(Context c){NotificationManager manager=c.getSystemService(NotificationManager.class);if(manager==null)return;for(int slot=0;slot<Profiles.MAX;slot++)for(int id:new int[]{4102,4104})manager.cancel(id+slot*100);manager.cancel(9002);}

  static void backgroundChannel(Context c,String id,String name){
    NotificationManager manager=c.getSystemService(NotificationManager.class);
    NotificationChannel channel=new NotificationChannel(id,name,NotificationManager.IMPORTANCE_MIN);
    channel.setDescription("Android 要求后台服务保留运行提示；此渠道不播放声音或振动。");
    channel.setSound(null,null);channel.enableVibration(false);channel.enableLights(false);
    channel.setShowBadge(false);channel.setLockscreenVisibility(Notification.VISIBILITY_SECRET);
    manager.createNotificationChannel(channel);
    migrate(c);
  }

  static synchronized void migrate(Context c){
    if(migrated)return;
    NotificationManager manager=c.getSystemService(NotificationManager.class);
    // Channel importance cannot be lowered by recreating an existing channel.
    // Versioned channels also remove old status notifications after an upgrade.
    for(String old:new String[]{"chat-wait","network-transport","chat-files"})manager.deleteNotificationChannel(old);
    // Deleting chat-files removes its old cards; do not cancel a newly opted-in
    // download completion posted by another profile under the same numeric ID.
    for(int slot=0;slot<Profiles.MAX;slot++)for(int id:new int[]{4103,4105})manager.cancel(id+slot*100);
    if(!AppSettings.backgroundCompletionNotice(c))clearCompletions(c);
    migrated=true;
  }

  static Notification background(Context c,String channel,String detail,PendingIntent open){
    Notification.Builder builder=new Notification.Builder(c,channel)
      .setSmallIcon(android.R.drawable.ic_dialog_info).setContentTitle("元婴期院士")
      .setContentText(detail).setContentIntent(open).setCategory(Notification.CATEGORY_SERVICE)
      .setVisibility(Notification.VISIBILITY_SECRET).setOnlyAlertOnce(true).setOngoing(true)
      .setShowWhen(false).setLocalOnly(true).setBadgeIconType(Notification.BADGE_ICON_NONE)
      .setPriority(Notification.PRIORITY_MIN).setSound(null).setVibrate(new long[0]);
    if(Build.VERSION.SDK_INT>=31)builder.setForegroundServiceBehavior(Notification.FOREGROUND_SERVICE_DEFERRED);
    return builder.build();
  }
}
