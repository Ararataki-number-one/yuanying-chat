package local.pocketchat;

import android.app.*;
import android.content.*;
import android.content.pm.ServiceInfo;
import android.os.*;

public class ChatService extends Service {
  @Override protected void attachBaseContext(Context base){super.attachBaseContext(new ProfileContext(base,Profiles.processSlot()));}
  static boolean running=false;static String lastText="";PowerManager.WakeLock wake;
  static final String WAIT="chat-wait",DONE="chat-replies";
  static void channels(Context c){NotificationManager m=c.getSystemService(NotificationManager.class);m.createNotificationChannel(new NotificationChannel(WAIT,"后台等待回复",NotificationManager.IMPORTANCE_LOW));m.createNotificationChannel(new NotificationChannel(DONE,"回复完成",NotificationManager.IMPORTANCE_DEFAULT));}
  static String waitingIdentity(){ChatSession s=ChatSession.peek();String id=s==null?"":s.pending==null?s.activeDeliveryId:s.pending.optString("id");return "wait:"+id;}
  static PendingIntent open(Context c,String url){return open(c,url,"page:"+String.valueOf(url));}
  static PendingIntent open(Context c,String url,String identity){Intent i=new Intent(c,Profiles.activity(Profiles.slot(c))).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP|Intent.FLAG_ACTIVITY_CLEAR_TOP).setData(android.net.Uri.parse("pocketchat://notification/"+android.net.Uri.encode("env"+Profiles.slot(c)+":"+identity)));if(MainActivity.chatUrl(url))i.putExtra("openConversation",url);return PendingIntent.getActivity(c,0,i,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);}
  static Notification notification(Context c,String channel,String title,String text,String url,boolean ongoing){return notification(c,channel,title,text,url,ongoing,ongoing?waitingIdentity():channel+":"+String.valueOf(url));}
  static Notification notification(Context c,String channel,String title,String text,String url,boolean ongoing,String identity){return new Notification.Builder(c,channel).setSmallIcon(android.R.drawable.ic_dialog_info).setContentTitle(title).setContentText(text).setContentIntent(open(c,url,identity)).setCategory(Notification.CATEGORY_STATUS).setVisibility(Notification.VISIBILITY_PRIVATE).setOnlyAlertOnce(ongoing).setOngoing(ongoing).setAutoCancel(!ongoing).build();}

  static void begin(Context c){if(!AppPrefs.enabled(c,"backgroundWait"))return;try{channels(c);c.startForegroundService(new Intent(c,Profiles.service(c)));}catch(Exception e){ChatSession s=ChatSession.peek();if(s!=null)s.setStatus("后台服务未启动，保持应用在前台等待回复");}}
  static void end(Context c){c.stopService(new Intent(c,Profiles.service(c)));}
  static void update(Context c,String text){if(!running||text.equals(lastText))return;lastText=text;try{c.getSystemService(NotificationManager.class).notify(Profiles.notification(c,4101),notification(c,WAIT,"元婴期院士正在等待回复",text,null,true));}catch(Exception ignored){}}
  static void completed(Context c,String id,String url){android.content.SharedPreferences p=c.getSharedPreferences("chat",0);if(id.equals(p.getString("notifiedJob","")))return;p.edit().putString("notifiedJob",id).commit();if(!AppPrefs.enabled(c,"replyNotice"))return;channels(c);try{c.getSystemService(NotificationManager.class).notify(Profiles.notification(c,4102),notification(c,DONE,"ChatGPT 已回复","点击查看完整回复",url,false,"done:"+id));}catch(Exception ignored){}}
  static void needsAttention(Context c,String text){channels(c);try{c.getSystemService(NotificationManager.class).notify(Profiles.notification(c,4103),notification(c,DONE,"元婴期院士需要你处理",text,null,false));}catch(Exception ignored){}}
  static void networkLost(Context c){if(!AppPrefs.enabled(c,"networkNotice"))return;android.content.SharedPreferences p=c.getSharedPreferences("chat",0);long now=System.currentTimeMillis();if(now-p.getLong("networkAlertAt",0)<30000)return;p.edit().putLong("networkAlertAt",now).apply();channels(c);try{c.getSystemService(NotificationManager.class).notify(Profiles.notification(c,4105),notification(c,DONE,"应用网络已中断","受保护连接已暂停，草稿和发送状态保留",null,false,"network:"+now));}catch(Exception ignored){}}
  static PendingIntent downloadIntent(Context c,String id){Intent i=new Intent(c,Profiles.activity(Profiles.slot(c))).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP|Intent.FLAG_ACTIVITY_CLEAR_TOP).setData(android.net.Uri.parse("pocketchat://download/env"+Profiles.slot(c)+"/"+android.net.Uri.encode(id))).putExtra("openDownload",id);return PendingIntent.getActivity(c,0,i,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);}
  static void downloaded(Context c,String id,String name){if(!AppPrefs.enabled(c,"downloadNotice"))return;channels(c);NotificationManager manager=c.getSystemService(NotificationManager.class);manager.createNotificationChannel(new NotificationChannel("chat-files","文件保存完成",NotificationManager.IMPORTANCE_DEFAULT));Notification n=new Notification.Builder(c,"chat-files").setSmallIcon(android.R.drawable.stat_sys_download_done).setContentTitle("文件已保存").setContentText(name).setContentIntent(downloadIntent(c,id)).setVisibility(Notification.VISIBILITY_PRIVATE).setAutoCancel(true).build();try{manager.notify(Profiles.notification(c,4104),n);}catch(Exception ignored){}}
  @Override public void onCreate(){super.onCreate();channels(this);}
  @Override public int onStartCommand(Intent i,int flags,int id){if(!AppPrefs.enabled(this,"backgroundWait")){stopSelf();return START_NOT_STICKY;}Notification n=notification(this,WAIT,"元婴期院士正在等待回复","切换应用后继续检测回复",null,true);if(Build.VERSION.SDK_INT>=29)startForeground(Profiles.notification(this,4101),n,ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC);else startForeground(Profiles.notification(this,4101),n);running=true;ChatSession s=ChatSession.get(this);s.updateBrowserActivity();if(wake==null){wake=((PowerManager)getSystemService(POWER_SERVICE)).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,"PocketChat:reply");wake.setReferenceCounted(false);}if(!wake.isHeld())wake.acquire(6*60*60*1000L);if(s.pending==null&&!s.submitting)stopSelf();return START_NOT_STICKY;}
  @Override public void onTimeout(int startId,int fgsType){ChatSession s=ChatSession.peek();if(s!=null)s.timeout();stopSelf();}
  @Override public void onDestroy(){running=false;lastText="";if(wake!=null&&wake.isHeld())wake.release();stopForeground(STOP_FOREGROUND_REMOVE);ChatSession s=ChatSession.peek();if(s!=null)s.updateBrowserActivity();super.onDestroy();}
  @Override public IBinder onBind(Intent i){return null;}
}
