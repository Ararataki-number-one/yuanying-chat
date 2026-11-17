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
import java.net.*;
import java.util.*;
import java.util.concurrent.*;

/** Real Android proxy/file notifications and retirement of the former reply service. */
public final class NotificationQuietIntegrationActivity extends Activity {
  final Handler handler=new Handler(Looper.getMainLooper());final JSONArray checks=new JSONArray();
  NotificationManager manager;ChatSession session;Context owner,other;
  boolean started,leftApp;volatile boolean finished;long deadline;String prefix=UUID.randomUUID().toString();
  JSONObject foregroundProof,homeProof,retirementProof;DefaultDownloads.Target savedFile;JSONObject savedTask,otherTask;
  final ExecutorService proxyWorker=Executors.newSingleThreadExecutor();
  NetworkTransportClient proxyClient;EnvironmentSpec.Identity proxyOwner;String proxyGeneration="";boolean proxyDetached;JSONObject proxyEvidence;
  @Override protected void attachBaseContext(Context c){super.attachBaseContext(new ProfileContext(c,Profiles.processSlot()));}
  @Override public void onCreate(Bundle state){super.onCreate(state);if(!getPackageName().endsWith(".test")||Profiles.processSlot()!=7)throw new SecurityException("Isolated test profile required");TextView label=new TextView(this);label.setText("浏览器后台连接与文件通知回归");setContentView(label);manager=getSystemService(NotificationManager.class);}
  @Override protected void onResume(){super.onResume();if(!started){started=true;handler.postDelayed(this::begin,300);}}
  @Override protected void onPause(){super.onPause();leftApp=true;}
  void check(String name,boolean pass)throws Exception{JSONObject value=J.obj("name",name,"pass",pass);checks.put(value);event("check",value);if(!pass)throw new IllegalStateException(name);}
  void event(String kind,JSONObject result){Log.i("PocketQuietNotifications",J.obj("kind",kind,"value",result).toString());}
  void report(String status,String error){Log.i("PocketQuietNotifications",J.obj("status",status,"notificationContract",2,"actualAndroidExecution",true,"checkCount",checks.length(),"error",error,"foregroundEvidence",foregroundProof,"homeEvidence",homeProof,"proxyEvidence",proxyEvidence,"replyRetirementEvidence",retirementProof,"scope","Real Activity lifecycle, obsolete service start, disabled legacy reply policy, owned loopback-only deny-all Mihomo core, real Home, file notification opt-in/deduplication/environment routing and a published MediaStore file; no account, remote route or network download").toString());}
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
  void seed(String channel,int id){manager.createNotificationChannel(new NotificationChannel(channel,"旧版本状态提醒",NotificationManager.IMPORTANCE_DEFAULT));manager.notify(id,new Notification.Builder(this,channel).setSmallIcon(android.R.drawable.ic_dialog_info).setContentTitle("旧版提示").build());}
  void begin(){try{
    Profiles.prepare(this,7,false);Profiles.prepare(this,6,false);
    owner=Profiles.context(this,7);other=Profiles.context(this,6);
    ProfileCatalog catalog=ProfileCatalog.get(this);
    EnvironmentSpec.Identity ownerIdentity=catalog.identity(7),otherIdentity=catalog.identity(6);
    if(!catalog.available(7)||!catalog.available(6)||ownerIdentity.slot!=7||otherIdentity.slot!=6||ownerIdentity.environmentId.equals(otherIdentity.environmentId)
        ||!owner.getSharedPreferences("chat",0).getBoolean("environmentInitialized",false)||!other.getSharedPreferences("chat",0).getBoolean("environmentInitialized",false))throw new IllegalStateException("Notification fixtures require two initialized production environments");
    check("Background file completion reminders are off by default",!AppSettings.backgroundCompletionNotice(owner));
    check("Browser and network child processes cannot count as visible UI",!QuietNotifications.uiProcess(getPackageName()+":gecko_env7_tab0_disable_art_image_",getPackageName())&&!QuietNotifications.uiProcess(getPackageName()+":network",getPackageName())&&QuietNotifications.uiProcess(getPackageName()+":profile7",getPackageName()));
    AppSettings.setBackgroundReplyPolicy(owner,true);
    check("An enabled legacy reply policy is migrated off without enabling result detection",!BackgroundReplyPolicy.refresh(owner).enabled&&!AppSettings.readBackgroundReplyPolicy(owner).enabled);
    seed("chat-wait",Profiles.notification(owner,4101));seed("network-transport",NetworkTransportService.NOTICE);
    seed("chat-files",Profiles.notification(owner,4104));seed(ChatService.DONE,Profiles.notification(other,4102));seed(ChatService.DONE,Profiles.notification(other,4103));seed(ChatService.DONE,Profiles.notification(owner,4105));
    awaitQuiet("all legacy notification fixtures posted",()->legacyVisible(),this::migrateLegacy);
  }catch(Exception e){fail(e);}}
  int[] legacyIds(){return new int[]{Profiles.notification(owner,4101),NetworkTransportService.NOTICE,Profiles.notification(owner,4104),Profiles.notification(other,4102),Profiles.notification(other,4103),Profiles.notification(owner,4105)};}
  boolean legacyVisible(){for(int id:legacyIds()){StatusBarNotification n=notice(id);if(n==null||!"旧版提示".contentEquals(n.getNotification().extras.getCharSequence(Notification.EXTRA_TITLE,"")))return false;}return true;}
  boolean legacyRemoved(){for(int id:legacyIds())if(notice(id)!=null)return false;return true;}
  void migrateLegacy()throws Exception{
    ChatService.channels(owner);QuietNotifications.backgroundChannel(this,QuietNotifications.NETWORK_BACKGROUND,"后台连接服务 · 静默");BackgroundReplyPolicy.reconcileLocal(owner);
    awaitQuiet("all legacy cards removed after migration",()->legacyRemoved(),this::migratedLegacy);
  }
  void migratedLegacy()throws Exception{
    check("Upgrade removes old noisy foreground channels",manager.getNotificationChannel("chat-wait")==null&&manager.getNotificationChannel("network-transport")==null);
    check("Upgrade removes retired reply cards across environments",notice(Profiles.notification(owner,4101))==null&&notice(Profiles.notification(other,4102))==null&&notice(Profiles.notification(owner,4105))==null&&notice(Profiles.notification(other,4103))==null);
    AppUpdates.call(owner,"status",null);await("default process lifecycle ready",()->defaultProcessKnown(QuietNotifications.foregroundEvidence(owner)),this::foregroundCompletions);
  }
  boolean defaultProcessKnown(JSONObject proof){JSONArray rows=proof.optJSONArray("processes");if(!proof.optBoolean("known")||rows==null)return false;for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);if(getPackageName().equals(row.optString("process")))return row.optBoolean("known")&&row.optInt("pid")>0&&row.optInt("pid")!=android.os.Process.myPid()&&row.optInt("actualActivityStartedCount",-1)==0&&!row.optBoolean("visible");}return false;}
  void foregroundCompletions()throws Exception{
    foregroundProof=QuietNotifications.foregroundEvidence(owner);check("A real visible app Activity suppresses file completion reminders",foregroundProof.optBoolean("known")&&foregroundProof.optBoolean("foreground")&&QuietNotifications.appForeground(owner));
    check("An already running default process exposes real zero-Activity lifecycle over private IPC",defaultProcessKnown(foregroundProof));
    check("A visible Activity is proved by real started lifecycle count",foregroundProof.optInt("actualActivityStartedCount")>0&&"activity-start-stop".equals(foregroundProof.optString("visibilitySource"))&&AppVisibility.snapshot().getInt("actualActivityStartedCount")>0);
    Bundle wrongPid=new Bundle();wrongPid.putInt("expectedPid",android.os.Process.myPid()+1);Bundle refused=getContentResolver().call(android.net.Uri.parse("content://"+getPackageName()+".lifecycle7"),"appVisibility",null,wrongPid);check("A private visibility endpoint rejects an obsolete process PID",refused!=null&&!refused.getBoolean("known")&&refused.getInt("pid")==android.os.Process.myPid());
    AppSettings.put(owner,"backgroundCompletionNotice","true");ChatService.downloaded(owner,prefix+"-foreground-file","visible-file.txt");
    awaitQuiet("foreground download stays absent",()->notice(Profiles.notification(owner,4104))==null,()->{
      check("Foreground downloads stay quiet even after opting in",notice(Profiles.notification(owner,4104))==null);
      check("Already visible file completions are remembered without posting",ReplyNoticeLedger.notified(owner,"download:"+prefix+"-foreground-file"));
      AppSettings.put(owner,"backgroundCompletionNotice","false");prepareRetiredService();
    });
  }
  boolean retiredServiceListed(){ActivityManager m=getSystemService(ActivityManager.class);for(ActivityManager.RunningServiceInfo service:m.getRunningServices(Integer.MAX_VALUE))if(service.service.getClassName().equals(Profiles.service(owner).getName()))return true;return false;}
  void prepareRetiredService()throws Exception{
    JSONObject legacy=J.obj("id",prefix+"-old-reply","kind","web","confirmed",true,"userKey","id:synthetic-question","confirmedUrl",MainActivity.ORIGIN+"c/synthetic-notification","prompt","synthetic waiting question");
    owner.getSharedPreferences("chat",0).edit().putString("browserEngine","gecko").putString("networkMode","external").putBoolean("requireExternalVpn",false).putBoolean("pageMode",true).putString("pending",legacy.toString()).commit();
    session=ChatSession.get(owner);session.networkReady=false;session.guard.setBlocked(true);session.foreground(false);session.handler.removeCallbacks(session.tick);
    check("An upgraded pending reply becomes history without a live detection task",session.pending==null&&!session.prefs.contains("pending")&&legacy.toString().equals(session.prefs.getString("retiredWebObservation","")));
    ComponentName start=owner.startService(new Intent(owner,Profiles.service(owner)));
    check("Android accepts the obsolete service restart intent for the real profile owner",start!=null&&start.getClassName().equals(Profiles.service(owner).getName()));
    retirementProof=J.obj("legacyPolicyMigratedOff",!AppSettings.readBackgroundReplyPolicy(owner).enabled,"legacyPendingArchived",session.pending==null&&!session.prefs.contains("pending"),"requestedService",start==null?"":start.flattenToShortString());
    awaitQuiet("obsolete reply service self-stops",()->!retiredServiceListed()&&!ChatService.running&&notice(Profiles.notification(owner,4101))==null,()->{
      check("An obsolete reply service restart cannot resume detection or post a foreground card",!retiredServiceListed()&&!ChatService.running&&session.pending==null&&notice(Profiles.notification(owner,4101))==null);
      retirementProof.put("serviceStopped",true);startLocalProxy();
    });
  }
  // A foreground proxy card is legitimate only while a real core is alive.
  // Starting an empty service must not defeat production's idle withdrawal.
  // This isolated, freshly cleared test app has no subscriber or real exit:
  // both listeners bind loopback, all routes reject, and DNS/TUN are disabled.
  void startLocalProxy()throws IOException{
    proxyOwner=ProfileCatalog.get(owner).identity(7);proxyClient=new NetworkTransportClient(owner,state->{});
    proxyWorker.execute(()->{try{
      JSONObject initial=proxyClient.call("snapshot","");
      if(initial.optBoolean("alive")||initial.optInt("slot",-1)!=7)throw new IOException("Quiet fixture requires an empty owned proxy slot");
      int controllerPort=NativeNetwork.freePort(),proxyPort=NativeNetwork.freePort(),probePort=NativeNetwork.freePort();
      while(proxyPort==controllerPort)proxyPort=NativeNetwork.freePort();while(probePort==controllerPort||probePort==proxyPort)probePort=NativeNetwork.freePort();
      String secret=UUID.randomUUID().toString();
      JSONObject config=J.obj("port",0,"socks-port",0,"mixed-port",0,"redir-port",0,"tproxy-port",0,"allow-lan",false,"bind-address","127.0.0.1","mode","rule","log-level","silent","ipv6",false,
        "external-controller","127.0.0.1:"+controllerPort,"secret",secret,"external-controller-cors",J.obj("allow-origins",new JSONArray(),"allow-private-network",false),
        "profile",J.obj("store-selected",false,"store-fake-ip",false),"tun",J.obj("enable",false),"sniffer",J.obj("enable",false),"dns",J.obj("enable",false),"geo-auto-update",false,
        "proxies",new JSONArray(),"proxy-groups",new JSONArray(),"rules",J.arr("MATCH,REJECT"),"listeners",J.arr(
          J.obj("name","PocketOnly","type","mixed","listen","127.0.0.1","port",proxyPort,"udp",false,"proxy","REJECT"),
          J.obj("name","WebsiteCheck","type","mixed","listen","127.0.0.1","port",probePort,"udp",false,"proxy","REJECT")));
      File directory=new File(owner.getNoBackupFilesDir(),"network-runtime");if(!directory.isDirectory()&&!directory.mkdirs())throw new IOException("Quiet proxy fixture directory unavailable");
      J.write(new File(directory,"config.json"),config.toString());J.write(new File(directory,"transport.json"),J.obj("proxyPort",proxyPort,"webProbePort",probePort,"ready",false,"names",new JSONArray()).toString());
      String configuration=NativeNetwork.hash(config.toString());
      JSONObject started=proxyClient.callBound("launch",configuration,NetworkDiagnostics.Reason.UNKNOWN,initial.optString("generation"),proxyOwner);
      proxyGeneration=started.optString("generation");
      if(proxyGeneration.isEmpty()||!started.optBoolean("alive")||started.optInt("slot",-1)!=7||started.optInt("pid")<=1||started.optInt("servicePid")==android.os.Process.myPid()
          ||!configuration.equals(started.optString("configuration"))||started.optInt("controllerPort")!=controllerPort||started.optInt("proxyPort")!=proxyPort||started.optInt("webProbePort")!=probePort)throw new IOException("Quiet proxy fixture did not acquire a real owned core");
      long expires=SystemClock.elapsedRealtime()+10000;Exception last=null;boolean controllerReady=false;
      while(!finished&&SystemClock.elapsedRealtime()<expires){
        HttpURLConnection connection=(HttpURLConnection)new URL("http://127.0.0.1:"+controllerPort+"/version").openConnection(Proxy.NO_PROXY);
        try{connection.setConnectTimeout(500);connection.setReadTimeout(500);connection.setRequestProperty("Authorization","Bearer "+secret);
          if(connection.getResponseCode()!=200)throw new IOException("Quiet proxy controller rejected its local owner");
          try(InputStream in=connection.getInputStream()){JSONObject version=new JSONObject(new String(J.read(in,4096),java.nio.charset.StandardCharsets.UTF_8));if(version.optString("version").isEmpty())throw new IOException("Quiet proxy controller has no version");}
          controllerReady=true;break;
        }catch(Exception e){last=e;}finally{connection.disconnect();}
        if(!proxyClient.call("snapshot","").optBoolean("alive"))throw new IOException("Quiet proxy fixture core exited",last);Thread.sleep(100);
      }
      if(finished)return;if(!controllerReady)throw new IOException("Quiet proxy fixture controller did not become ready",last);
      JSONObject ready=proxyClient.call("ready","");
      proxyEvidence=J.obj("owner",proxyOwner.json(),"started",started,"ready",ready,"controllerReady",true,"loopbackListenersConfigured",true,"denyAllConfigured",true,"fixtureRemoteRequests",false);
      handler.post(()->{if(finished)return;try{
        check("A real local-only deny-all core owns the proxy foreground service",ready.optBoolean("alive")&&proxyGeneration.equals(ready.optString("generation"))&&"running".equals(ready.optString("state")));
        deadline=SystemClock.elapsedRealtime()+15000;handler.postDelayed(this::waiting,200);
      }catch(Exception e){fail(e);}});
    }catch(Exception e){handler.post(()->fail(e));}});
  }
  void stopLocalProxy(Step next){proxyWorker.execute(()->{try{
    String owned=proxyGeneration;if(owned.isEmpty())throw new IOException("Quiet fixture lost its owned proxy generation");
    JSONObject stopped=proxyClient.callBound("stop","",NetworkDiagnostics.Reason.REQUESTED,owned,proxyOwner);
    if(stopped.optBoolean("alive")||stopped.optInt("pid")!=0||stopped.optInt("slot",-1)!=7||owned.equals(stopped.optString("generation")))throw new IOException("Quiet fixture proxy did not stop");
    proxyGeneration="";proxyEvidence.put("stopped",stopped);proxyClient.detach();proxyDetached=true;
    handler.post(()->{if(finished)return;try{
      check("Stopping the owned proxy generation closes the real fixture core",!stopped.optBoolean("alive")&&stopped.optInt("pid")==0);
      awaitQuiet("stopped proxy foreground card withdrawn",()->notice(NetworkTransportService.NOTICE)==null,next);
    }catch(Exception e){fail(e);}});
  }catch(Exception e){handler.post(()->fail(e));}});}
  void cleanupLocalProxy(){proxyWorker.execute(()->{try{
    if(proxyClient!=null&&!proxyDetached){if(!proxyGeneration.isEmpty()){proxyClient.callBound("stop","",NetworkDiagnostics.Reason.REQUESTED,proxyGeneration,proxyOwner);proxyGeneration="";}proxyClient.detach();proxyDetached=true;}
  }catch(Exception e){Log.w("PocketQuietProxyFixture","Owned proxy cleanup did not settle",e);}finally{proxyWorker.shutdown();}});}
  void quiet(String channel)throws Exception{
    NotificationChannel c=manager.getNotificationChannel(channel);
    // Android may promote MIN foreground channels to LOW; never demand an
    // unsupported hidden-service trick merely to make this assertion pass.
    // Android resets app-supplied channel visibility to its app-wide default.
    // The actual foreground notifications must still use SECRET (checked below).
    check(channel+" remains silent at MIN or system-required LOW",c!=null&&c.getImportance()<=NotificationManager.IMPORTANCE_LOW&&c.getSound()==null&&!c.shouldVibrate()&&!c.canShowBadge()&&(c.getLockscreenVisibility()==Notification.VISIBILITY_SECRET||c.getLockscreenVisibility()==NotificationListenerService.Ranking.VISIBILITY_NO_OVERRIDE));
  }
  void waiting(){try{
    StatusBarNotification network=notice(NetworkTransportService.NOTICE);
    if(network==null){if(SystemClock.elapsedRealtime()>deadline)throw new IllegalStateException("Real proxy foreground notification did not start");handler.postDelayed(this::waiting,200);return;}
    quiet(QuietNotifications.NETWORK_BACKGROUND);
    check("Network service keeps a legitimate foreground notification",(network.getNotification().flags&Notification.FLAG_FOREGROUND_SERVICE)!=0);
    check("The proxy foreground notice stays off the lock screen",network.getNotification().visibility==Notification.VISIBILITY_SECRET);
    check("Proxy service does not revive reply detection",!ChatService.running&&session.pending==null&&notice(Profiles.notification(owner,4101))==null&&notice(Profiles.notification(owner,4102))==null);
    event("homeNeeded",J.obj("id","notification-background-"+prefix));deadline=SystemClock.elapsedRealtime()+15000;handler.postDelayed(this::background,500);
  }catch(Exception e){fail(e);}}
  void background(){try{
    if(!leftApp){if(SystemClock.elapsedRealtime()>deadline)throw new IllegalStateException("Runner did not send Home");handler.postDelayed(this::background,200);return;}
    homeProof=QuietNotifications.foregroundEvidence(owner);if((!homeProof.optBoolean("known")||homeProof.optBoolean("foreground"))&&SystemClock.elapsedRealtime()<deadline){handler.postDelayed(this::background,100);return;}
    check("Real Home leaves the UI in background while required services keep running",homeProof.optBoolean("known")&&!homeProof.optBoolean("foreground")&&!QuietNotifications.appForeground(owner));
    check("Real Home is proved by stopped Activity lifecycle despite browser process priority",homeProof.optInt("actualActivityStartedCount",-1)==0&&AppVisibility.snapshot().getInt("actualActivityStartedCount")==0&&AppVisibility.snapshot().getLong("activityStops")>0&&"activity-start-stop".equals(homeProof.optString("visibilitySource"))&&defaultProcessKnown(homeProof));
    check("Home retains the real proxy without creating a reply observation service",proxyClient.alive()&&notice(NetworkTransportService.NOTICE)!=null&&!ChatService.running&&session.pending==null);
    ChatService.downloaded(owner,prefix+"-disabled-file","disabled-file.txt");
    awaitQuiet("background default remains quiet",()->notice(Profiles.notification(owner,4104))==null,()->{
      check("Background file completion stays quiet until the user opts in",!QuietNotifications.backgroundCompletionAllowed(owner)&&notice(Profiles.notification(owner,4104))==null&&!ReplyNoticeLedger.notified(owner,"download:"+prefix+"-disabled-file"));
      AppSettings.put(owner,"backgroundCompletionNotice","true");check("Explicit file notification opt-in is admitted after real Home",QuietNotifications.backgroundCompletionAllowed(owner));
      ChatService.downloaded(owner,prefix+"-foreground-file","visible-file.txt");
      awaitQuiet("visible file completions cannot re-alert after Home",()->notice(Profiles.notification(owner,4104))==null,()->{
        check("Foreground file completions never become delayed background alerts",notice(Profiles.notification(owner,4104))==null);
        ChatService.needsAttention(owner,"synthetic attention");ChatService.networkLost(owner);BackgroundReplyPolicy.reconcileLocal(owner);
        awaitQuiet("retired observation events remain quiet",()->notice(Profiles.notification(owner,4101))==null&&notice(Profiles.notification(owner,4102))==null&&notice(Profiles.notification(owner,4103))==null&&notice(Profiles.notification(owner,4105))==null,()->{
          check("File opt-in never enables result detection or reply notifications",!BackgroundReplyPolicy.refresh(owner).enabled&&!ChatService.running&&session.pending==null&&notice(Profiles.notification(owner,4102))==null);
          stopLocalProxy(this::emptyProxy);
        });
      });
    });
  }catch(Exception e){fail(e);}}
  void emptyProxy()throws Exception{
    check("An empty proxy service withdraws its foreground card without stopping a proxy",notice(NetworkTransportService.NOTICE)==null);
    savedFile=DefaultDownloads.create(owner,"quiet-completion-"+prefix+".txt","text/plain");try(OutputStream out=savedFile.output()){out.write("complete local file".getBytes(java.nio.charset.StandardCharsets.UTF_8));}savedFile.publish();
    DownloadTasks tasks=new DownloadTasks(owner);savedTask=tasks.add("","",MainActivity.ORIGIN);DownloadTasks.put(savedTask,"state","saved","name",savedFile.name,"uri",savedFile.uri.toString(),"location",savedFile.location,"received",19,"total",19);tasks.save();
    ChatService.downloaded(owner,savedTask.optString("id"),savedFile.name);await("opted-in saved download completion",()->notice(Profiles.notification(owner,4104))!=null,this::downloadCompleted);
  }
  void downloadCompleted()throws Exception{
    StatusBarNotification n=notice(Profiles.notification(owner,4104));check("Opted-in background file completion opens the exact saved task",n!=null&&ChatService.FILES.equals(n.getNotification().getChannelId())&&ChatService.downloadIntent(owner,savedTask.optString("id")).equals(n.getNotification().contentIntent));
    try(InputStream in=owner.getContentResolver().openInputStream(savedFile.uri)){check("The notified local file is fully published and readable",in!=null&&"complete local file".equals(new String(J.read(in,1024),java.nio.charset.StandardCharsets.UTF_8)));}
    DownloadTasks otherTasks=new DownloadTasks(other);otherTask=otherTasks.add("","",MainActivity.ORIGIN);DownloadTasks.put(otherTask,"state","saved","name",savedFile.name,"uri",savedFile.uri.toString(),"location",savedFile.location,"received",19,"total",19);otherTasks.save();
    ChatService.downloaded(other,otherTask.optString("id"),savedFile.name);
    await("independent environment file completion",()->notice(Profiles.notification(other,4104))!=null,()->{
      StatusBarNotification independent=notice(Profiles.notification(other,4104));
      check("Independent environments retain distinct file notification routes",independent!=null&&notice(Profiles.notification(owner,4104))!=null&&ChatService.downloadIntent(other,otherTask.optString("id")).equals(independent.getNotification().contentIntent)&&!independent.getNotification().contentIntent.equals(notice(Profiles.notification(owner,4104)).getNotification().contentIntent));
      manager.cancel(Profiles.notification(owner,4104));awaitQuiet("download completion cleared",()->notice(Profiles.notification(owner,4104))==null,()->{
        ChatService.downloaded(owner,savedTask.optString("id"),savedFile.name);awaitQuiet("saved download remains deduplicated",()->notice(Profiles.notification(owner,4104))==null,()->{
          check("A saved download cannot re-alert after dismissal",notice(Profiles.notification(owner,4104))==null&&ReplyNoticeLedger.notified(owner,"download:"+savedTask.optString("id")));
          AppSettings.put(owner,"backgroundCompletionNotice","false");awaitQuiet("opting out clears file cards across environments",()->notice(Profiles.notification(owner,4104))==null&&notice(Profiles.notification(other,4104))==null,()->{
            check("Opting out removes file completion cards across environments",!QuietNotifications.backgroundCompletionAllowed(owner)&&notice(Profiles.notification(owner,4104))==null&&notice(Profiles.notification(other,4104))==null);
            finished=true;handler.removeCallbacksAndMessages(null);cleanup();report("passed","");
          });
        });
      });
    });
  }
  void cleanup(){if(owner!=null)ChatService.end(owner);cleanupLocalProxy();if(savedFile!=null)savedFile.abort();if(session!=null){session.handler.removeCallbacks(session.tick);session.web.destroy();}for(Context c:new Context[]{owner,other})if(c!=null){manager.cancel(Profiles.notification(c,4102));manager.cancel(Profiles.notification(c,4104));}}
  void fail(Exception e){if(finished)return;finished=true;handler.removeCallbacksAndMessages(null);cleanup();report("failed",e.toString());}
}
