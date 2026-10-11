package local.pocketchat;

import android.app.job.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.function.BooleanSupplier;

public class AppUpdateJob extends JobService {
  static final class Running {final AtomicBoolean stopped=new AtomicBoolean();final BooleanSupplier gate=stopped::get;}
  final ConcurrentHashMap<JobParameters,Running> active=new ConcurrentHashMap<>();
  @Override public boolean onStartJob(JobParameters params){Running running=new Running();active.put(params,running);Runnable done=()->{if(active.remove(params,running))jobFinished(params,false);};AppUpdateManager manager=AppUpdateManager.get(this);if(params.getJobId()==AppUpdates.TRANSFER)manager.runTransferJob(running.gate,done);else manager.check(true,done);return true;}
  @Override public boolean onStopJob(JobParameters params){Running running=active.remove(params);if(running!=null){running.stopped.set(true);if(params.getJobId()==AppUpdates.TRANSFER)AppUpdateManager.get(this).stopTransferJob(running.gate);}return true;}
}
