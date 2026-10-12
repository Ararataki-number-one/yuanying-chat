package local.pocketchat;

import android.app.*;
import android.content.*;
import android.content.pm.ServiceInfo;
import android.os.*;

public class ChatService extends Service {
  @Override protected void attachBaseContext(Context base){super.attachBaseContext(new ProfileContext(base,Profiles.processSlot()));}
  static boolean running=false;static String lastText="";PowerManager.WakeLock wake;
  static final String WAIT=QuietNotifications.REPLY_BACKGROUND,DONE="chat-replies",FILES="chat-download-complete";
  static void channels(Context c){QuietNotifications.backgroundChannel(c,WAIT,"后台回复服务 · 静默");NotificationManager m=c.getSystemService(NotificationManager.class);m.createNotificationChannel(new NotificationChannel(DONE,"后台回复完成",NotificationManager.IMPORTANCE_DEFAULT));m.createNotificationChannel(new NotificationChannel(FILES,"后台文件下载完成",NotificationManager.IMPORTANCE_DEFAULT));}
  static String waitingIdentity(){ChatSession s=ChatSession.peek();String id=s==null?"":s.pending==null?s.activeDeliveryId:s.pending.optString("id");return "wait:"+id;}
  static PendingIntent open(Context c,String url){return open(c,url,"page:"+String.valueOf(url));}
  static PendingIntent open(Context c,String url,String identity){Intent i=new Intent(c,Profiles.activity(Profiles.slot(c))).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP|Intent.FLAG_ACTIVITY_CLEAR_TOP).setData(android.net.Uri.parse("pocketchat://notification/"+android.net.Uri.encode("env"+Profiles.slot(c)+":"+identity)));if(MainActivity.chatUrl(url))i.putExtra("openConversation",url);return PendingIntent.getActivity(c,0,i,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);}
  static Notification notification(Context c,String channel,String title,String text,String url,boolean ongoing){return notification(c,channel,title,text,url,ongoing,ongoing?waitingIdentity():channel+":"+String.valueOf(url));}
  static Notification notification(Context c,String channel,String title,String text,String url,boolean ongoing,String identity){return new Notification.Builder(c,channel).setSmallIcon(android.R.drawable.ic_dialog_info).setContentTitle(title).setContentText(text).setContentIntent(open(c,url,identity)).setCategory(Notification.CATEGORY_STATUS).setVisibility(Notification.VISIBILITY_PRIVATE).setOnlyAlertOnce(ongoing).setOngoing(ongoing).setAutoCancel(!ongoing).build();}

  static void begin(Context c){if(!AppPrefs.enabled(c,"backgroundWait"))return;try{channels(c);c.startForegroundService(new Intent(c,Profiles.service(c)));}catch(Exception e){ChatSession s=ChatSession.peek();if(s!=null)s.setStatus("后台服务未启动，保持应用在前台等待回复");}}
  static void end(Context c){c.stopService(new Intent(c,Profiles.service(c)));}
  // Progress stays in the app. Reposting the foreground notification on every
  // page poll would resurface a card the user deliberately dismissed.
  static void update(Context c,String text){}
  static synchronized void completed(Context c,String id,String url){
    if(id==null||id.isEmpty())return;
    android.content.SharedPreferences p=c.getSharedPreferences("chat",0);
    try(ReplyNoticeLedger ledger=new ReplyNoticeLedger(c)){
      ledger.migrate(p);if(ledger.contains(id))return;
      // A foreground completion was already visible to the user. Record it so
      // later page polling cannot turn it into a delayed background reminder.
      if(QuietNotifications.appForeground(c)){ledger.record(id);return;}
      if(!AppPrefs.enabled(c,"replyNotice")||!QuietNotifications.backgroundCompletionAllowed(c))return;
      channels(c);NotificationManager manager=c.getSystemService(NotificationManager.class);
      if(manager.getNotificationChannel(DONE).getImportance()==NotificationManager.IMPORTANCE_NONE)return;
      String name=Profiles.display(c,Profiles.slot(c));
      manager.notify(Profiles.notification(c,4102),notification(c,DONE,"ChatGPT 已回复",name+" · 点击查看完整回复",url,false,"done:"+id));
      ledger.record(id);
    }catch(Exception ignored){}
  }
  static void needsAttention(Context c,String text){QuietNotifications.migrate(c);}
  static void networkLost(Context c){QuietNotifications.migrate(c);}
  static PendingIntent downloadIntent(Context c,String id){Intent i=new Intent(c,Profiles.activity(Profiles.slot(c))).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP|Intent.FLAG_ACTIVITY_CLEAR_TOP).setData(android.net.Uri.parse("pocketchat://download/env"+Profiles.slot(c)+"/"+android.net.Uri.encode(id))).putExtra("openDownload",id);return PendingIntent.getActivity(c,0,i,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);}
  static synchronized void downloaded(Context c,String id,String name){
    if(id==null||id.isEmpty())return;QuietNotifications.migrate(c);
    try(ReplyNoticeLedger ledger=new ReplyNoticeLedger(c)){
      String identity="download:"+id;if(ledger.contains(identity))return;
      if(QuietNotifications.appForeground(c)){ledger.record(identity);return;}
      if(!QuietNotifications.backgroundCompletionAllowed(c))return;
      channels(c);NotificationManager manager=c.getSystemService(NotificationManager.class);if(manager.getNotificationChannel(FILES).getImportance()==NotificationManager.IMPORTANCE_NONE)return;
      manager.notify(Profiles.notification(c,4104),new Notification.Builder(c,FILES).setSmallIcon(android.R.drawable.stat_sys_download_done).setContentTitle("文件已下载").setContentText(name+" · 点击查看").setContentIntent(downloadIntent(c,id)).setAutoCancel(true).setVisibility(Notification.VISIBILITY_PRIVATE).build());ledger.record(identity);
    }catch(Exception ignored){}
  }
  @Override public void onCreate(){super.onCreate();channels(this);}
  @Override public int onStartCommand(Intent i,int flags,int id){if(!AppPrefs.enabled(this,"backgroundWait")){stopSelf();return START_NOT_STICKY;}Notification n=QuietNotifications.background(this,WAIT,"后台回复检测",open(this,null,waitingIdentity()));if(Build.VERSION.SDK_INT>=29)startForeground(Profiles.notification(this,4101),n,ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC);else startForeground(Profiles.notification(this,4101),n);running=true;ChatSession s=ChatSession.get(this);s.updateBrowserActivity();if(wake==null){wake=((PowerManager)getSystemService(POWER_SERVICE)).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,"PocketChat:reply");wake.setReferenceCounted(false);}if(!wake.isHeld())wake.acquire(6*60*60*1000L);if(s.pending==null&&!s.submitting)stopSelf();return START_NOT_STICKY;}
  @Override public void onTimeout(int startId,int fgsType){ChatSession s=ChatSession.peek();if(s!=null)s.timeout();stopSelf();}
  @Override public void onDestroy(){running=false;lastText="";if(wake!=null&&wake.isHeld())wake.release();stopForeground(STOP_FOREGROUND_REMOVE);ChatSession s=ChatSession.peek();if(s!=null)s.updateBrowserActivity();super.onDestroy();}
  @Override public IBinder onBind(Intent i){return null;}
}
