package local.pocketchat;

import android.app.*;
import android.content.*;
import android.content.pm.ServiceInfo;
import android.os.*;

public class ChatService extends Service {
  @Override protected void attachBaseContext(Context base){super.attachBaseContext(new ProfileContext(base,Profiles.processSlot()));}
  static boolean running=false;static String lastText="";private static ChatService active;PowerManager.WakeLock wake;
  static final String WAIT=QuietNotifications.REPLY_BACKGROUND,DONE="chat-replies",FILES="chat-download-complete";
  static void channels(Context c){NotificationManager m=c.getSystemService(NotificationManager.class);m.createNotificationChannel(new NotificationChannel(FILES,"后台文件下载完成",NotificationManager.IMPORTANCE_DEFAULT));}
  static String waitingIdentity(){ChatSession s=ChatSession.peek();String id=s==null?"":s.pending==null?s.activeDeliveryId:s.pending.optString("id");return "wait:"+id;}
  static PendingIntent open(Context c,String url){return open(c,url,"page:"+String.valueOf(url));}
  static PendingIntent open(Context c,String url,String identity){Intent i=new Intent(c,Profiles.activity(Profiles.slot(c))).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP|Intent.FLAG_ACTIVITY_CLEAR_TOP).setData(android.net.Uri.parse("pocketchat://notification/"+android.net.Uri.encode("env"+Profiles.slot(c)+":"+identity)));if(MainActivity.chatUrl(url))i.putExtra("openConversation",url);return PendingIntent.getActivity(c,0,i,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);}
  static Notification notification(Context c,String channel,String title,String text,String url,boolean ongoing){return notification(c,channel,title,text,url,ongoing,ongoing?waitingIdentity():channel+":"+String.valueOf(url));}
  static Notification notification(Context c,String channel,String title,String text,String url,boolean ongoing,String identity){return new Notification.Builder(c,channel).setSmallIcon(android.R.drawable.ic_dialog_info).setContentTitle(title).setContentText(text).setContentIntent(open(c,url,identity)).setCategory(Notification.CATEGORY_STATUS).setVisibility(Notification.VISIBILITY_PRIVATE).setOnlyAlertOnce(ongoing).setOngoing(ongoing).setAutoCancel(!ongoing).build();}

  static void end(Context c){c.stopService(new Intent(c,Profiles.service(c)));}
  static void policyChanged(Context c,BackgroundReplyPolicy.Snapshot value){if(!value.enabled){if(active!=null)active.stopDetection();else end(c);}}
  private void stopDetection(){releaseDetection();stopSelf();}
  private void releaseDetection(){running=false;lastText="";if(wake!=null&&wake.isHeld())wake.release();stopForeground(STOP_FOREGROUND_REMOVE);}
  // Progress stays in the app. Reposting the foreground notification on every
  // page poll would resurface a card the user deliberately dismissed.
  static void update(Context c,String text){}
  static void needsAttention(Context c,String text){QuietNotifications.migrate(c);}
  static void networkLost(Context c){QuietNotifications.migrate(c);}
  static PendingIntent downloadIntent(Context c,String id){Intent i=new Intent(c,Profiles.activity(Profiles.slot(c))).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP|Intent.FLAG_ACTIVITY_CLEAR_TOP).setData(android.net.Uri.parse("pocketchat://download/env"+Profiles.slot(c)+"/"+android.net.Uri.encode(id))).putExtra("openDownload",id);return PendingIntent.getActivity(c,0,i,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);}
  static synchronized void downloaded(Context c,String id,String name){
    if(id==null||id.isEmpty())return;QuietNotifications.migrate(c);
    try(ReplyNoticeLedger ledger=new ReplyNoticeLedger(c)){
      String identity="download:"+id;if(ledger.contains(identity))return;
      if(QuietNotifications.actualForeground(c)){ledger.record(identity);return;}
      if(!QuietNotifications.backgroundCompletionAllowed(c))return;
      channels(c);NotificationManager manager=c.getSystemService(NotificationManager.class);if(manager.getNotificationChannel(FILES).getImportance()==NotificationManager.IMPORTANCE_NONE)return;
      manager.notify(Profiles.notification(c,4104),new Notification.Builder(c,FILES).setSmallIcon(android.R.drawable.stat_sys_download_done).setContentTitle("文件已下载").setContentText(name+" · 点击查看").setContentIntent(downloadIntent(c,id)).setAutoCancel(true).setVisibility(Notification.VISIBILITY_PRIVATE).build());ledger.record(identity);
    }catch(Exception ignored){}
  }
  @Override public void onCreate(){super.onCreate();active=this;}
  @Override public int onStartCommand(Intent i,int flags,int id){
    // Android may restart a service registered by a previous app version.
    // Reply detection has been removed; downloads use their independent owner.
    stopDetection();return START_NOT_STICKY;
  }
  @Override public void onTimeout(int startId,int fgsType){stopSelf();}
  @Override public void onDestroy(){if(active==this)active=null;releaseDetection();BackgroundReplyPolicy.Snapshot value=BackgroundReplyPolicy.refresh(this);ChatSession s=ChatSession.peek();if(s!=null){if(!value.enabled)s.backgroundReplyPolicyChanged(value);else s.updateBrowserActivity(false);}super.onDestroy();}
  @Override public IBinder onBind(Intent i){return null;}
}
