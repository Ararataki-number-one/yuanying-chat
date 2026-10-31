package local.pocketchat;

import android.app.ActivityManager;
import android.app.Application;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteDatabaseLockedException;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.os.Process;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/** Optional reply observation, independent of the browser's work and proxy ownership. */
final class BackgroundReplyPolicy {
  static final class Snapshot {
    final boolean known,enabled;final long revision;final int legacyPendingMask;
    Snapshot(boolean known,boolean enabled,long revision,int legacyPendingMask){this.known=known;this.enabled=known&&enabled;this.revision=revision;this.legacyPendingMask=legacyPendingMask;}
    static Snapshot unknown(){return new Snapshot(false,false,0,255);}
  }
  private static volatile Snapshot current=Snapshot.unknown();
  private static long latestRevision;
  private static final Handler main=new Handler(Looper.getMainLooper());
  private static boolean installed;
  static Snapshot snapshot(){return current;}
  static boolean enabledCached(){return current.enabled;}
  private static synchronized void remember(Snapshot value){
    // An I/O failure closes admission. An old queued hint cannot roll back a revision.
    if(!value.known)current=value;
    else if(value.revision>=latestRevision){latestRevision=value.revision;current=value;}
  }
  static Snapshot refresh(Context c){
    Snapshot value;
    try{value=AppSettings.readBackgroundReplyPolicy(c);if(!value.known)value=AppSettings.initializeBackgroundReplyPolicy(c);}
    catch(RuntimeException unavailable){value=Snapshot.unknown();}
    remember(value);return current;
  }
  static String action(Context c){return c.getPackageName()+".BACKGROUND_REPLY_POLICY_CHANGED";}
  static int uiSlot(String process,String app){if(app.equals(process))return 0;for(int slot=1;slot<Profiles.MAX;slot++)if((app+":profile"+slot).equals(process))return slot;return -1;}
  static String processName(Context c){
    if(Build.VERSION.SDK_INT>=28)return Application.getProcessName();
    try{ActivityManager manager=c.getSystemService(ActivityManager.class);List<ActivityManager.RunningAppProcessInfo> values=manager==null?null:manager.getRunningAppProcesses();
      if(values!=null)for(ActivityManager.RunningAppProcessInfo value:values)if(value.pid==Process.myPid())return value.processName;
    }catch(RuntimeException unknown){/* An unknown process must not acquire policy permissions. */}
    return null;
  }
  /** Runs before providers can cache profile preferences. Every UI process uses this gate. */
  static void bootstrap(Context c){
    try{
      if(uiSlot(processName(c),c.getPackageName())<0)return;
      remember(AppSettings.initializeBackgroundReplyPolicy(c));migrateLegacyPreferences(c);
    }catch(SQLiteDatabaseLockedException gateUnavailable){
      // Providers must not proceed to cache/write prefs while another process owns
      // the migration gate. Android may retry this startup after the lock is gone.
      remember(Snapshot.unknown());throw gateUnavailable;
    }catch(RuntimeException unavailable){remember(Snapshot.unknown());}
  }
  /** The SQLite writer gate also fences a newly attaching profile before its first prefs read. */
  static void migrateLegacyPreferences(Context c){
    Context root=Profiles.global(c);int owner=uiSlot(processName(root),root.getPackageName());if(owner<0)return;
    SQLiteDatabase db=ProfileCatalog.get(root).getWritableDatabase();db.beginTransaction();try{
      Snapshot value=AppSettings.readBackgroundReplyPolicy(db);if(!value.known)return;
      ActivityManager manager=root.getSystemService(ActivityManager.class);List<ActivityManager.RunningAppProcessInfo> processes=manager==null?null:manager.getRunningAppProcesses();
      Set<Integer> live=new HashSet<>();if(processes!=null)for(ActivityManager.RunningAppProcessInfo process:processes)if(process.uid==Process.myUid()){int slot=uiSlot(process.processName,root.getPackageName());if(slot>=0)live.add(slot);}
      for(int slot=0;slot<Profiles.MAX;slot++){
        if((value.legacyPendingMask&(1<<slot))==0)continue;
        // Never write a live other owner's full preference map through MODE_MULTI_PROCESS.
        // Unknown liveness permits only the process's own safe in-memory editor.
        if(slot!=owner&&(processes==null||live.contains(slot)))continue;
        if(Profiles.context(root,slot).getSharedPreferences("chat",0).edit().putBoolean("backgroundWait",false).commit())AppSettings.backgroundReplyLegacyCommitted(root,slot);
      }
      value=AppSettings.readBackgroundReplyPolicy(db);db.setTransactionSuccessful();remember(value);
    }finally{db.endTransaction();}
  }
  static void install(Application application){
    if(uiSlot(processName(application),application.getPackageName())<0)return;
    synchronized(BackgroundReplyPolicy.class){
      if(installed)return;
      BroadcastReceiver receiver=new BroadcastReceiver(){@Override public void onReceive(Context c,Intent intent){if(intent!=null&&action(c).equals(intent.getAction()))policyChanged(c,intent.getLongExtra("revision",0));}};
      IntentFilter filter=new IntentFilter(action(application));
      if(Build.VERSION.SDK_INT>=33)application.registerReceiver(receiver,filter,Context.RECEIVER_NOT_EXPORTED);else application.registerReceiver(receiver,filter);
      installed=true;
    }
    policyChanged(application,0);
  }
  static Snapshot setEnabled(Context c,boolean enabled){
    Snapshot value;
    try{value=AppSettings.setBackgroundReplyPolicy(c,enabled);remember(value);}
    catch(RuntimeException failure){remember(Snapshot.unknown());reconcileLocal(c);throw failure;}
    if(!value.enabled){stopAllReplyServices(c);QuietNotifications.clearReplyDetection(c);}
    reconcileLocal(c);
    // No manifest receiver or provider acquisition: cold profiles stay cold.
    c.sendBroadcast(new Intent(action(c)).setPackage(c.getPackageName()).putExtra("revision",value.revision));
    return value;
  }
  static void policyChanged(Context c,long hintedRevision){
    // Revision is merely an invalidation hint, never permission to enable capture.
    refresh(c);reconcileLocal(c);
  }
  static void reconcileLocal(Context c){
    Context root=Profiles.global(c);
    Runnable apply=()->{
      refresh(root);Context profile=Profiles.context(root,Profiles.processSlot());
      try{migrateLegacyPreferences(root);}catch(RuntimeException retryLater){/* The durable mask preserves failed compatibility work. */}
      Snapshot value=snapshot();
      ChatService.policyChanged(profile,value);
      ChatSession session=ChatSession.peek();if(session!=null&&!session.deleted)session.backgroundReplyPolicyChanged(value);
      if(!value.enabled)QuietNotifications.clearReplyDetection(root);
    };
    if(Looper.myLooper()==Looper.getMainLooper())apply.run();else main.post(apply);
  }
  static void stopAllReplyServices(Context c){
    Context root=Profiles.global(c);
    for(int slot=0;slot<Profiles.MAX;slot++)try{root.stopService(new Intent(root,Profiles.service(Profiles.context(root,slot))));}catch(RuntimeException retryOnOwner){/* Owner invalidation and fresh admission remain fail-closed. */}
  }
}
