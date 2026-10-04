package local.pocketchat;

import android.app.job.*;
import java.util.*;

public class AppUpdateJob extends JobService {
  final Set<JobParameters> active=Collections.synchronizedSet(new HashSet<>());
  @Override public boolean onStartJob(JobParameters params){active.add(params);AppUpdateManager.get(this).check(true,()->{if(active.remove(params))jobFinished(params,false);});return true;}
  @Override public boolean onStopJob(JobParameters params){active.remove(params);return true;}
}
