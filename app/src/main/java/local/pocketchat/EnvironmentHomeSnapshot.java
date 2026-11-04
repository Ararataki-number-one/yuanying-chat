package local.pocketchat;

import android.app.ActivityManager;
import android.content.Context;
import java.util.*;
import org.json.*;

/** One worker-owned catalog/process read; search and rendering consume its immutable snapshot. */
final class EnvironmentHomeSnapshot {
  final EnvironmentSearchIndex search;final JSONArray rows;final Set<Integer> running;final int defaultSlot;final boolean stars;
  EnvironmentHomeSnapshot(JSONArray rows,Set<Integer> running,int defaultSlot,boolean stars){this.stars=stars;this.rows=rows;search=new EnvironmentSearchIndex(rows);this.running=Collections.unmodifiableSet(new HashSet<>(running));this.defaultSlot=defaultSlot;}
  static EnvironmentHomeSnapshot read(Context context){
    JSONArray rows=ProfileCatalog.get(context).list();Set<Integer> running=new HashSet<>();
    try{ActivityManager manager=context.getSystemService(ActivityManager.class);List<ActivityManager.RunningAppProcessInfo> processes=manager==null?null:manager.getRunningAppProcesses();if(processes!=null)for(ActivityManager.RunningAppProcessInfo process:processes)running.add(process.pid);}catch(RuntimeException unavailable){}
    return new EnvironmentHomeSnapshot(rows,running,AppSettings.defaultSlot(context),AppSettings.bool(context,"starBackground",false));
  }
}
