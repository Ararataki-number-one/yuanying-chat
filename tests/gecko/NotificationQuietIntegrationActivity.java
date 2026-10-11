package local.pocketchat;

import android.app.*;
import android.content.*;
import android.os.*;
import android.service.notification.StatusBarNotification;
import android.service.notification.NotificationListenerService;
import android.util.Log;
import android.widget.TextView;
import org.json.*;
import java.util.*;

/** Real Android channels and foreground services; only synthetic completion data. */
public final class NotificationQuietIntegrationActivity extends Activity {
  final Handler handler=new Handler(Looper.getMainLooper());final JSONArray checks=new JSONArray();
  NotificationManager manager;ChatSession session;Context owner,other;JSONObject job;
  boolean started,leftApp,finished;long deadline;String prefix=UUID.randomUUID().toString();
  @Override protected void attachBaseContext(Context c){super.attachBaseContext(new ProfileContext(c,Profiles.processSlot()));}
  @Override public void onCreate(Bundle state){super.onCreate(state);if(!getPackageName().endsWith(".test")||Profiles.processSlot()!=7)throw new SecurityException("Isolated test profile required");TextView label=new TextView(this);label.setText("后台通知与完成提醒回归");setContentView(label);manager=getSystemService(NotificationManager.class);}
  @Override protected void onResume(){super.onResume();if(!started){started=true;handler.postDelayed(this::begin,300);}}
  @Override protected void onPause(){super.onPause();leftApp=true;}
  void check(String name,boolean pass)throws Exception{JSONObject value=J.obj("name",name,"pass",pass);checks.put(value);event("check",value);if(!pass)throw new IllegalStateException(name);}
  void event(String kind,JSONObject result){Log.i("PocketQuietNotifications",J.obj("kind",kind,"value",result).toString());}
  void report(String status,String error){Log.i("PocketQuietNotifications",J.obj("status",status,"actualAndroidExecution",true,"checkCount",checks.length(),"error",error,"scope","Android channels, real foreground services, real Home, production stable-terminal gate and persisted profile-local completion reminders; no real account").toString());}
  StatusBarNotification notice(int id){for(StatusBarNotification n:manager.getActiveNotifications())if(n.getId()==id)return n;return null;}
  interface Condition {boolean ready()throws Exception;}
  interface Step {void run()throws Exception;}
  void await(String name,Condition condition,Step next){await(name,condition,next,false);}
  void awaitQuiet(String name,Condition condition,Step next){await(name,condition,next,true);}
  void await(String name,Condition condition,Step next,boolean stable){
    long expires=SystemClock.elapsedRealtime()+5000;
    handler.post(new Runnable(){long readySince;
      @Override public void run(){if(finished)return;try{
        long now=SystemClock.elapsedRealtime();boolean ready=condition.ready();
        if(ready){if(readySince==0)readySince=now;if(!stable||now-readySince>=500){next.run();return;}}else readySince=0;
        if(now>=expires)throw new IllegalStateException("Android notification state did not settle: "+name);
        handler.postDelayed(this,100);
      }catch(Exception e){fail(e);}}
    });
  }
  boolean completionVisible(Context c,String id){StatusBarNotification n=notice(Profiles.notification(c,4102));return n!=null&&ChatService.open(c,job.optString("confirmedUrl"),"done:"+id).equals(n.getNotification().contentIntent);}
  void seed(String channel,int id){manager.createNotificationChannel(new NotificationChannel(channel,"旧版本状态提醒",NotificationManager.IMPORTANCE_DEFAULT));manager.notify(id,new Notification.Builder(this,channel).setSmallIcon(android.R.drawable.ic_dialog_info).setContentTitle("旧版提示").build());}
  void begin(){try{
    owner=Profiles.context(this,7);other=Profiles.context(this,6);
    for(int slot:new int[]{6,7}){Context c=Profiles.context(this,slot);c.getSharedPreferences("chat",0).edit().putBoolean("replyNotice",true).commit();manager.cancel(Profiles.notification(c,4102));}
    owner.getSharedPreferences("chat",0).edit().putStringSet("notifiedJobs",Collections.singleton(prefix+"-aggregate-legacy")).commit();
    seed("chat-wait",Profiles.notification(owner,4101));seed("network-transport",NetworkTransportService.NOTICE);
    seed("chat-files",Profiles.notification(owner,4104));seed(ChatService.DONE,Profiles.notification(other,4103));seed(ChatService.DONE,Profiles.notification(owner,4105));
    ChatService.channels(owner);QuietNotifications.backgroundChannel(this,QuietNotifications.NETWORK_BACKGROUND,"后台连接服务 · 静默");
    check("Upgrade removes old noisy foreground channels",manager.getNotificationChannel("chat-wait")==null&&manager.getNotificationChannel("network-transport")==null);
    check("Upgrade removes non-completion regular notifications across profiles",notice(Profiles.notification(owner,4104))==null&&notice(Profiles.notification(owner,4105))==null&&notice(Profiles.notification(other,4103))==null);
    owner.getSharedPreferences("chat",0).edit().putString("browserEngine","system").putString("networkMode","external").putBoolean("requireExternalVpn",false).putBoolean("pageMode",true).commit();
    session=ChatSession.get(owner);session.networkReady=false;session.guard.setBlocked(true);session.foreground(false);
    String url=MainActivity.ORIGIN+"c/synthetic-notification";
    String id=session.deliveries.begin(url,"synthetic waiting question",new JSONArray(),"web",null);
    job=J.obj("id",id,"kind","web","confirmed",true,"userKey","id:synthetic-question","confirmedUrl",url,"expectedUrl",url,"prompt","synthetic waiting question");
    session.pending=job;session.activeDeliveryId=id;session.prefs.edit().putString("pending",job.toString()).commit();
    check("Waiting and disconnected states do not post completion alerts",notice(Profiles.notification(owner,4102))==null);
    ChatService.begin(owner);startForegroundService(new Intent(this,NetworkTransportService.class));
    deadline=SystemClock.elapsedRealtime()+15000;handler.postDelayed(this::waiting,200);
  }catch(Exception e){fail(e);}}
  void quiet(String channel)throws Exception{
    NotificationChannel c=manager.getNotificationChannel(channel);
    // Android may promote MIN foreground channels to LOW; never demand an
    // unsupported hidden-service trick merely to make this assertion pass.
    // Android resets app-supplied channel visibility to its app-wide default.
    // The actual foreground notifications must still use SECRET (checked below).
    check(channel+" remains silent at MIN or system-required LOW",c!=null&&c.getImportance()<=NotificationManager.IMPORTANCE_LOW&&c.getSound()==null&&!c.shouldVibrate()&&!c.canShowBadge()&&(c.getLockscreenVisibility()==Notification.VISIBILITY_SECRET||c.getLockscreenVisibility()==NotificationListenerService.Ranking.VISIBILITY_NO_OVERRIDE));
  }
  void waiting(){try{
    StatusBarNotification wait=notice(Profiles.notification(owner,4101)),network=notice(NetworkTransportService.NOTICE);
    if(!ChatService.running||wait==null||network==null){if(SystemClock.elapsedRealtime()>deadline)throw new IllegalStateException("Foreground notifications did not start");handler.postDelayed(this::waiting,200);return;}
    quiet(ChatService.WAIT);quiet(QuietNotifications.NETWORK_BACKGROUND);
    check("Reply service keeps a legitimate foreground notification",(wait.getNotification().flags&Notification.FLAG_FOREGROUND_SERVICE)!=0);
    check("Network service keeps a legitimate foreground notification",(network.getNotification().flags&Notification.FLAG_FOREGROUND_SERVICE)!=0);
    check("Foreground statuses no longer contain waiting or environment-count messages",!wait.getNotification().extras.getCharSequence(Notification.EXTRA_TITLE,"").toString().contains("等待")&&!network.getNotification().extras.getCharSequence(Notification.EXTRA_TEXT,"").toString().contains("个环境"));
    check("Both foreground notices stay off the lock screen",wait.getNotification().visibility==Notification.VISIBILITY_SECRET&&network.getNotification().visibility==Notification.VISIBILITY_SECRET);
    long posted=wait.getPostTime();ChatService.update(owner,"思考中 · 状态不断变化");
    handler.postDelayed(()->{try{check("Progress polling does not repost a notification",notice(Profiles.notification(owner,4101)).getPostTime()==posted);event("homeNeeded",J.obj("id","notification-background-"+prefix));deadline=SystemClock.elapsedRealtime()+15000;handler.postDelayed(this::background,500);}catch(Exception e){fail(e);}},300);
  }catch(Exception e){fail(e);}}
  void background(){try{
    if(!leftApp){if(SystemClock.elapsedRealtime()>deadline)throw new IllegalStateException("Runner did not send Home");handler.postDelayed(this::background,200);return;}
    check("Home preserves the pending reply and background observation service",session.pending==job&&ChatService.running&&session.browserWorkActive()&&!session.browserPaused);
    JSONObject poll=J.obj("submitted",true,"terminal",true,"busy",true,"userKey",job.optString("userKey"),"url",job.optString("confirmedUrl"),"replyKey","id:synthetic-reply","markdown","synthetic completed reply");
    check("Busy replies cannot trigger a completion notice",!session.webObserver.mayComplete(job,poll)&&notice(Profiles.notification(owner,4102))==null);
    poll.put("busy",false);check("A first terminal observation cannot alert early",!session.webObserver.mayComplete(job,poll));
    handler.postDelayed(()->{try{check("A second terminal observation remains quiet",!session.webObserver.mayComplete(job,poll));handler.postDelayed(()->finishReply(poll),1200);}catch(Exception e){fail(e);}},1200);
  }catch(Exception e){fail(e);}}
  void finishReply(JSONObject poll){try{
    check("Stable terminal reply is accepted only after repeated observations",session.webObserver.mayComplete(job,poll));
    session.completeReply(job,poll);handler.postDelayed(this::completed,500);
  }catch(Exception e){fail(e);}}
  void completed(){await("completed reply and stopped foreground service",()->completionVisible(owner,job.optString("id"))&&!ChatService.running&&notice(Profiles.notification(owner,4101))==null,this::firstCompletion);}
  void firstCompletion()throws Exception{
    StatusBarNotification first=notice(Profiles.notification(owner,4102));
    check("A detected complete reply produces the one regular reminder",first!=null&&ChatService.DONE.equals(first.getNotification().getChannelId())&&(first.getNotification().flags&Notification.FLAG_ONGOING_EVENT)==0);
    check("Completion ends the waiting foreground service",session.pending==null&&!ChatService.running&&notice(Profiles.notification(owner,4101))==null);
    String b=prefix+"-second";
    ChatService.completed(owner,b,job.optString("confirmedUrl"));
    await("second reply replaces the first notice",()->completionVisible(owner,b),()->{
      manager.cancel(Profiles.notification(owner,4102));
      await("second notice removed by Android",()->notice(Profiles.notification(owner,4102))==null,()->{
        ChatService.completed(owner,job.optString("id"),job.optString("confirmedUrl"));
        awaitQuiet("older reply remains deduplicated",()->notice(Profiles.notification(owner,4102))==null,this::olderCompletion);
      });
    });
  }
  void olderCompletion()throws Exception{
    check("An older completed reply cannot re-alert after another reply",notice(Profiles.notification(owner,4102))==null);
    ChatService.completed(owner,prefix+"-aggregate-legacy",MainActivity.ORIGIN);
    awaitQuiet("aggregate legacy receipt remains quiet",()->notice(Profiles.notification(owner,4102))==null,this::aggregateLegacy);
  }
  void aggregateLegacy()throws Exception{
    check("Aggregate legacy receipts migrate to the indexed ledger without re-alerting",notice(Profiles.notification(owner,4102))==null&&ReplyNoticeLedger.notified(owner,prefix+"-aggregate-legacy")&&!owner.getSharedPreferences("chat",0).contains("notifiedJobs"));
    owner.getSharedPreferences("chat",0).edit().putString("notifiedJob",prefix+"-legacy").commit();ChatService.completed(owner,prefix+"-legacy",MainActivity.ORIGIN);
    awaitQuiet("single-job legacy receipt remains quiet",()->notice(Profiles.notification(owner,4102))==null,this::singleLegacy);
  }
  void singleLegacy()throws Exception{
    check("Existing single-job notification records are respected",notice(Profiles.notification(owner,4102))==null);
    String a=job.optString("id");
    ChatService.completed(other,a,job.optString("confirmedUrl"));
    await("another environment posts its independent completion",()->completionVisible(other,a),this::independentCompletion);
  }
  void independentCompletion()throws Exception{
    String a=job.optString("id");
    check("The same completion identity in another environment remains independent",notice(Profiles.notification(other,4102))!=null&&ReplyNoticeLedger.notified(other,a));
    AppPrefs.apply(owner,J.obj("replyNotice",false));String retry=prefix+"-retry";ChatService.completed(owner,retry,MainActivity.ORIGIN);
    awaitQuiet("disabled reminders stay absent",()->notice(Profiles.notification(owner,4102))==null,this::disabledCompletion);
  }
  void disabledCompletion()throws Exception{
    String retry=prefix+"-retry";
    check("A disabled reminder is not posted or incorrectly marked delivered",notice(Profiles.notification(owner,4102))==null&&!ReplyNoticeLedger.notified(owner,retry));
    AppPrefs.apply(owner,J.obj("replyNotice",true));ChatService.completed(owner,retry,MainActivity.ORIGIN);
    // The retry uses the home URL, so match its actual PendingIntent separately.
    await("enabled completion retry becomes visible",()->{StatusBarNotification n=notice(Profiles.notification(owner,4102));return n!=null&&ChatService.open(owner,MainActivity.ORIGIN,"done:"+retry).equals(n.getNotification().contentIntent);},this::retriedCompletion);
  }
  void retriedCompletion()throws Exception{
    check("A completion can be retried after reminders are enabled",notice(Profiles.notification(owner,4102))!=null);
    ChatService.needsAttention(owner,"synthetic attention");ChatService.networkLost(owner);ChatService.downloaded(owner,"synthetic-file","synthetic.png");
    awaitQuiet("non-completion events remain quiet",()->notice(Profiles.notification(owner,4103))==null&&notice(Profiles.notification(owner,4104))==null&&notice(Profiles.notification(owner,4105))==null,this::quietEvents);
  }
  void quietEvents()throws Exception{
    check("Attention network and download events remain in-app without separate reminders",notice(Profiles.notification(owner,4103))==null&&notice(Profiles.notification(owner,4104))==null&&notice(Profiles.notification(owner,4105))==null);
    check("Background observation remains enabled by default",AppPrefs.enabled(owner,"backgroundWait"));
    finished=true;handler.removeCallbacksAndMessages(null);cleanup();report("passed","");
  }
  void cleanup(){if(owner!=null)ChatService.end(owner);stopService(new Intent(this,NetworkTransportService.class));if(session!=null){session.pending=null;session.prefs.edit().remove("pending").commit();session.handler.removeCallbacks(session.tick);session.web.destroy();}for(Context c:new Context[]{owner,other})if(c!=null)manager.cancel(Profiles.notification(c,4102));}
  void fail(Exception e){if(finished)return;finished=true;handler.removeCallbacksAndMessages(null);cleanup();report("failed",e.toString());}
}
