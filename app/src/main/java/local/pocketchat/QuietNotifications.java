package local.pocketchat;

import android.app.*;
import android.content.Context;
import android.os.Build;

/** Foreground services remain valid; only completed replies actively alert. */
final class QuietNotifications {
  static final String REPLY_BACKGROUND="reply-background-quiet-v2";
  static final String NETWORK_BACKGROUND="network-background-quiet-v2";
  private static boolean migrated;

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
    for(int slot=0;slot<Profiles.MAX;slot++)for(int id:new int[]{4103,4104,4105})manager.cancel(id+slot*100);
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
