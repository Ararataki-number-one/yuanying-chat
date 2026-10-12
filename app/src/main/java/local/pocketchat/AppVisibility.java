package local.pocketchat;

import android.app.Activity;
import android.app.Application;
import android.os.Bundle;
import android.os.Process;
import android.os.SystemClock;
import java.util.Collections;
import java.util.IdentityHashMap;
import java.util.Set;

/** Actual visible Activities, independent of Gecko or foreground-service process priority. */
final class AppVisibility {
  private static final Set<Activity> started=Collections.newSetFromMap(new IdentityHashMap<>());
  private static boolean installed;private static long revision,starts,stops,lastEventAt;
  static synchronized void install(Application application){
    if(installed)return;
    application.registerActivityLifecycleCallbacks(new Application.ActivityLifecycleCallbacks(){
      @Override public void onActivityStarted(Activity activity){start(activity);}
      @Override public void onActivityStopped(Activity activity){stop(activity);}
      @Override public void onActivityDestroyed(Activity activity){stop(activity);}
      @Override public void onActivityCreated(Activity activity,Bundle state){}
      @Override public void onActivityResumed(Activity activity){}
      @Override public void onActivityPaused(Activity activity){}
      @Override public void onActivitySaveInstanceState(Activity activity,Bundle state){}
    });installed=true;
  }
  private static synchronized void start(Activity activity){if(started.add(activity)){starts++;revision++;lastEventAt=SystemClock.elapsedRealtime();}}
  private static synchronized void stop(Activity activity){if(started.remove(activity)){stops++;revision++;lastEventAt=SystemClock.elapsedRealtime();}}
  static synchronized Bundle snapshot(){Bundle value=new Bundle();value.putInt("schema",1);value.putBoolean("known",installed);value.putInt("pid",Process.myPid());value.putInt("uid",Process.myUid());value.putInt("slot",Profiles.processSlot());value.putInt("actualActivityStartedCount",started.size());value.putLong("activityStarts",starts);value.putLong("activityStops",stops);value.putLong("revision",revision);value.putLong("lastEventAt",lastEventAt);return value;}
}
