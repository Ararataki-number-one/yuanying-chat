package local.pocketchat;

import android.app.*;
import android.content.*;
import android.os.*;
import android.service.notification.StatusBarNotification;
import android.service.notification.NotificationListenerService;
import android.util.Log;
import android.widget.TextView;
import org.json.*;
import java.io.*;
import java.util.*;

/** Real Android channels and foreground services; only synthetic completion data. */
public final class NotificationQuietIntegrationActivity extends Activity {
  final Handler handler=new Handler(Looper.getMainLooper());final JSONArray checks=new JSONArray();
  NotificationManager manager;ChatSession session;Context owner,other;JSONObject job;
  boolean started,leftApp,finished;long deadline;String prefix=UUID.randomUUID().toString();
  JSONObject foregroundProof,homeProof;DefaultDownloads.Target savedFile;JSONObject savedTask;
  @Override protected void attachBaseContext(Context c){super.attachBaseContext(new ProfileContext(c,Profiles.processSlot()));}
  @Override public void onCreate(Bundle state){super.onCreate(state);if(!getPackageName().endsWith(".test")||Profiles.processSlot()!=7)throw new SecurityException("Isolated test profile required");TextView label=new TextView(this);label.setText("后台通知与完成提醒回归");setContentView(label);manager=getSystemService(NotificationManager.class);}
  @Override protected void onResume(){super.onResume();if(!started){started=true;handler.postDelayed(this::begin,300);}}
  @Override protected void onPause(){super.onPause();leftApp=true;}
  void check(String name,boolean pass)throws Exception{JSONObject value=J.obj("name",name,"pass",pass);checks.put(value);event("check",value);if(!pass)throw new IllegalStateException(name);}
  void event(String kind,JSONObject result){Log.i("PocketQuietNotifications",J.obj("kind",kind,"value",result).toString());}
  void report(String status,String error){Log.i("PocketQuietNotifications",J.obj("status",status,"actualAndroidExecution",true,"checkCount",checks.length(),"error",error,"foregroundEvidence",foregroundProof,"homeEvidence",homeProof,"scope","Android activity-process importance, channels, real foreground services, real Home, production stable-terminal gate, opt-in completion reminders and a real local MediaStore save; no account or network download").toString());}
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
    // Production creation clears profile preferences. Finish it before seeding
    // reminder settings and legacy receipts in this freshly cleared test app.
    Profiles.prepare(this,7,false);Profiles.prepare(this,6,false);
    owner=Profiles.context(this,7);other=Profiles.context(this,6);
    ProfileCatalog catalog=ProfileCatalog.get(this);
    EnvironmentSpec.Identity ownerIdentity=catalog.identity(7),otherIdentity=catalog.identity(6);
    if(!catalog.available(7)||!catalog.available(6)||ownerIdentity.slot!=7||otherIdentity.slot!=6||ownerIdentity.environmentId.equals(otherIdentity.environmentId)
        ||!owner.getSharedPreferences("chat",0).getBoolean("environmentInitialized",false)||!other.getSharedPreferences("chat",0).getBoolean("environmentInitialized",false))throw new IllegalStateException("Notification fixtures require two initialized production environments");
    check("Background completion reminders are off by default",!AppSettings.backgroundCompletionNotice(owner));
    check("Browser and network child processes cannot count as visible UI",!QuietNotifications.uiProcess(getPackageName()+":gecko_env7_tab0_disable_art_image_",getPackageName())&&!QuietNotifications.uiProcess(getPackageName()+":network",getPackageName())&&QuietNotifications.uiProcess(getPackageName()+":profile7",getPackageName()));
    for(int slot:new int[]{6,7}){Context c=Profiles.context(this,slot);c.getSharedPreferences("chat",0).edit().putBoolean("replyNotice",true).commit();manager.cancel(Profiles.notification(c,4102));}
    owner.getSharedPreferences("chat",0).edit().putStringSet("notifiedJobs",Collections.singleton(prefix+"-aggregate-legacy")).commit();
    seed("chat-wait",Profiles.notification(owner,4101));seed("network-transport",NetworkTransportService.NOTICE);
    seed("chat-files",Profiles.notification(owner,4104));seed(ChatService.DONE,Profiles.notification(other,4103));seed(ChatService.DONE,Profiles.notification(owner,4105));
    // notify/cancel return before Android's notification worker completes. Prove
    // all old cards existed first, so an initially empty list cannot pass this
    // upgrade test while the fixture posts are still waiting in Android's queue.
    awaitQuiet("all legacy notification fixtures posted",()->legacyVisible(),this::migrateLegacy);
  }catch(Exception e){fail(e);}}
  int[] legacyIds(){return new int[]{Profiles.notification(owner,4101),NetworkTransportService.NOTICE,Profiles.notification(owner,4104),Profiles.notification(other,4103),Profiles.notification(owner,4105)};}
  boolean legacyVisible(){
    for(int id:legacyIds()){StatusBarNotification n=notice(id);if(n==null||!"旧版提示".contentEquals(n.getNotification().extras.getCharSequence(Notification.EXTRA_TITLE,"")))return false;}
    return true;
  }
  boolean legacyRemoved(){for(int id:legacyIds())if(notice(id)!=null)return false;return true;}
  void migrateLegacy()throws Exception{
    ChatService.channels(owner);QuietNotifications.backgroundChannel(this,QuietNotifications.NETWORK_BACKGROUND,"后台连接服务 · 静默");
    awaitQuiet("all legacy cards removed after migration",()->legacyRemoved(),this::migratedLegacy);
  }
  void migratedLegacy()throws Exception{
    check("Upgrade removes old noisy foreground channels",manager.getNotificationChannel("chat-wait")==null&&manager.getNotificationChannel("network-transport")==null);
    check("Upgrade removes non-completion regular notifications across profiles",notice(Profiles.notification(owner,4104))==null&&notice(Profiles.notification(owner,4105))==null&&notice(Profiles.notification(other,4103))==null);
    // Start the normal app-wide status owner explicitly. Visibility discovery
    // must query this already-running process, never create all eight profiles.
    AppUpdates.call(owner,"status",null);await("default process lifecycle ready",()->defaultProcessKnown(QuietNotifications.foregroundEvidence(owner)),this::foregroundCompletions);
  }
  boolean defaultProcessKnown(JSONObject proof){JSONArray rows=proof.optJSONArray("processes");if(!proof.optBoolean("known")||rows==null)return false;for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);if(getPackageName().equals(row.optString("process")))return row.optBoolean("known")&&row.optInt("pid")>0&&row.optInt("pid")!=android.os.Process.myPid()&&row.optInt("actualActivityStartedCount",-1)==0&&!row.optBoolean("visible");}return false;}
  void foregroundCompletions()throws Exception{
    foregroundProof=QuietNotifications.foregroundEvidence(owner);check("A real visible app Activity suppresses completion reminders",foregroundProof.optBoolean("known")&&foregroundProof.optBoolean("foreground")&&QuietNotifications.appForeground(owner));
    check("An already running default process exposes real zero-Activity lifecycle over private IPC",defaultProcessKnown(foregroundProof));
    check("A visible Activity is proved by real started lifecycle count",foregroundProof.optInt("actualActivityStartedCount")>0&&"activity-start-stop".equals(foregroundProof.optString("visibilitySource"))&&AppVisibility.snapshot().getInt("actualActivityStartedCount")>0);
    Bundle wrongPid=new Bundle();wrongPid.putInt("expectedPid",android.os.Process.myPid()+1);Bundle refused=getContentResolver().call(android.net.Uri.parse("content://"+getPackageName()+".lifecycle7"),"appVisibility",null,wrongPid);check("A private visibility endpoint rejects an obsolete process PID",refused!=null&&!refused.getBoolean("known")&&refused.getInt("pid")==android.os.Process.myPid());
    AppSettings.put(owner,"backgroundCompletionNotice","true");ChatService.completed(owner,prefix+"-foreground",MainActivity.ORIGIN);ChatService.downloaded(owner,prefix+"-foreground-file","visible-file.txt");
    awaitQuiet("foreground reply and download stay absent",()->notice(Profiles.notification(owner,4102))==null&&notice(Profiles.notification(owner,4104))==null,()->{
      check("Foreground replies and downloads stay quiet even after opting in",notice(Profiles.notification(owner,4102))==null&&notice(Profiles.notification(owner,4104))==null);
      check("Already visible completions are remembered without posting",ReplyNoticeLedger.notified(owner,prefix+"-foreground")&&ReplyNoticeLedger.notified(owner,"download:"+prefix+"-foreground-file"));
      AppSettings.put(owner,"backgroundCompletionNotice","false");prepareWaiting();
    });
  }
  void prepareWaiting()throws Exception{
    owner.getSharedPreferences("chat",0).edit().putString("browserEngine","gecko").putString("networkMode","external").putBoolean("requireExternalVpn",false).putBoolean("pageMode",true).commit();
    session=ChatSession.get(owner);session.networkReady=false;session.guard.setBlocked(true);session.foreground(false);
    String url=MainActivity.ORIGIN+"c/synthetic-notification";
    String id=session.deliveries.begin(url,"synthetic waiting question",new JSONArray(),"web",null);
    job=J.obj("id",id,"kind","web","confirmed",true,"userKey","id:synthetic-question","confirmedUrl",url,"expectedUrl",url,"prompt","synthetic waiting question");
    session.pending=job;session.activeDeliveryId=id;session.prefs.edit().putString("pending",job.toString()).commit();
    check("Waiting and disconnected states do not post completion alerts",notice(Profiles.notification(owner,4102))==null);
    ChatService.begin(owner);startForegroundService(new Intent(this,NetworkTransportService.class));
    deadline=SystemClock.elapsedRealtime()+15000;handler.postDelayed(this::waiting,200);
  }
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
    homeProof=QuietNotifications.foregroundEvidence(owner);if((!homeProof.optBoolean("known")||homeProof.optBoolean("foreground"))&&SystemClock.elapsedRealtime()<deadline){handler.postDelayed(this::background,100);return;}check("Real Home leaves the UI in background while required services keep running",homeProof.optBoolean("known")&&!homeProof.optBoolean("foreground")&&!QuietNotifications.appForeground(owner));
    check("Real Home is proved by stopped Activity lifecycle despite browser process priority",homeProof.optInt("actualActivityStartedCount",-1)==0&&AppVisibility.snapshot().getInt("actualActivityStartedCount")==0&&AppVisibility.snapshot().getLong("activityStops")>0&&"activity-start-stop".equals(homeProof.optString("visibilitySource"))&&defaultProcessKnown(homeProof));
    check("Home preserves the pending reply and background observation service",session.pending==job&&ChatService.running&&session.browserWorkActive()&&!session.browserPaused);
    ChatService.completed(owner,prefix+"-disabled",MainActivity.ORIGIN);ChatService.downloaded(owner,prefix+"-disabled-file","disabled-file.txt");
    awaitQuiet("background default remains quiet",()->notice(Profiles.notification(owner,4102))==null&&notice(Profiles.notification(owner,4104))==null,()->{
      check("Background completion stays quiet until the user opts in",!QuietNotifications.backgroundCompletionAllowed(owner)&&notice(Profiles.notification(owner,4102))==null&&notice(Profiles.notification(owner,4104))==null&&!ReplyNoticeLedger.notified(owner,prefix+"-disabled")&&!ReplyNoticeLedger.notified(owner,"download:"+prefix+"-disabled-file"));
      AppSettings.put(owner,"backgroundCompletionNotice","true");check("Explicit opt-in admits completion only after real Home",QuietNotifications.backgroundCompletionAllowed(owner));
      ChatService.completed(owner,prefix+"-foreground",MainActivity.ORIGIN);ChatService.downloaded(owner,prefix+"-foreground-file","visible-file.txt");
      awaitQuiet("visible completions cannot re-alert after Home",()->notice(Profiles.notification(owner,4102))==null&&notice(Profiles.notification(owner,4104))==null,()->{check("Foreground completions never become delayed background alerts",notice(Profiles.notification(owner,4102))==null&&notice(Profiles.notification(owner,4104))==null);observeTerminal();});
    });
  }catch(Exception e){fail(e);}}
  void observeTerminal()throws Exception{
    JSONObject poll=J.obj("submitted",true,"terminal",true,"busy",true,"userKey",job.optString("userKey"),"url",job.optString("confirmedUrl"),"replyKey","id:synthetic-reply","markdown","synthetic completed reply");
    check("Busy replies cannot trigger a completion notice",!session.webObserver.mayComplete(job,poll)&&notice(Profiles.notification(owner,4102))==null);
    poll.put("busy",false);check("A first terminal observation cannot alert early",!session.webObserver.mayComplete(job,poll));
    handler.postDelayed(()->{try{check("A second terminal observation remains quiet",!session.webObserver.mayComplete(job,poll));handler.postDelayed(()->finishReply(poll),1200);}catch(Exception e){fail(e);}},1200);
  }
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
    ChatService.needsAttention(owner,"synthetic attention");ChatService.networkLost(owner);
    awaitQuiet("non-completion events remain quiet",()->notice(Profiles.notification(owner,4103))==null&&notice(Profiles.notification(owner,4104))==null&&notice(Profiles.notification(owner,4105))==null,this::quietEvents);
  }
  void quietEvents()throws Exception{
    check("Attention and network events remain in-app without separate reminders",notice(Profiles.notification(owner,4103))==null&&notice(Profiles.notification(owner,4105))==null);
    check("Background observation remains enabled by default",AppPrefs.enabled(owner,"backgroundWait"));
    savedFile=DefaultDownloads.create(owner,"quiet-completion-"+prefix+".txt","text/plain");try(OutputStream out=savedFile.output()){out.write("complete local file".getBytes(java.nio.charset.StandardCharsets.UTF_8));}savedFile.publish();
    DownloadTasks tasks=new DownloadTasks(owner);savedTask=tasks.add("","",MainActivity.ORIGIN);DownloadTasks.put(savedTask,"state","saved","name",savedFile.name,"uri",savedFile.uri.toString(),"location",savedFile.location,"received",19,"total",19);tasks.save();
    ChatService.downloaded(owner,savedTask.optString("id"),savedFile.name);await("opted-in saved download completion",()->notice(Profiles.notification(owner,4104))!=null,this::downloadCompleted);
  }
  void downloadCompleted()throws Exception{
    StatusBarNotification n=notice(Profiles.notification(owner,4104));check("Opted-in background file completion opens the exact saved task",n!=null&&ChatService.FILES.equals(n.getNotification().getChannelId())&&ChatService.downloadIntent(owner,savedTask.optString("id")).equals(n.getNotification().contentIntent));
    try(InputStream in=owner.getContentResolver().openInputStream(savedFile.uri)){check("The notified local file is fully published and readable",in!=null&&"complete local file".equals(new String(J.read(in,1024),java.nio.charset.StandardCharsets.UTF_8)));}
    manager.cancel(Profiles.notification(owner,4104));awaitQuiet("download completion cleared",()->notice(Profiles.notification(owner,4104))==null,()->{
      ChatService.downloaded(owner,savedTask.optString("id"),savedFile.name);awaitQuiet("saved download remains deduplicated",()->notice(Profiles.notification(owner,4104))==null,()->{
        check("A saved download cannot re-alert after dismissal",notice(Profiles.notification(owner,4104))==null&&ReplyNoticeLedger.notified(owner,"download:"+savedTask.optString("id")));
        AppSettings.put(owner,"backgroundCompletionNotice","false");awaitQuiet("opting out clears old completion cards",()->notice(Profiles.notification(owner,4102))==null&&notice(Profiles.notification(other,4102))==null,()->{
          check("Opting out removes completion cards across environments",!QuietNotifications.backgroundCompletionAllowed(owner)&&notice(Profiles.notification(owner,4102))==null&&notice(Profiles.notification(other,4102))==null);
          finished=true;handler.removeCallbacksAndMessages(null);cleanup();report("passed","");
        });
      });
    });
  }
  void cleanup(){if(owner!=null)ChatService.end(owner);stopService(new Intent(this,NetworkTransportService.class));if(savedFile!=null)savedFile.abort();if(session!=null){session.pending=null;session.prefs.edit().remove("pending").commit();session.handler.removeCallbacks(session.tick);session.web.destroy();}for(Context c:new Context[]{owner,other})if(c!=null){manager.cancel(Profiles.notification(c,4102));manager.cancel(Profiles.notification(c,4104));}}
  void fail(Exception e){if(finished)return;finished=true;handler.removeCallbacksAndMessages(null);cleanup();report("failed",e.toString());}
}
