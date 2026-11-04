package local.pocketchat;

import java.util.*;
import java.util.concurrent.*;

/** Deterministic executor queues expose work counts without invented timing claims. */
final class EnvironmentRefreshQueueHost {
  static final List<String> checks=new ArrayList<>();
  static void check(String name,boolean value){if(!value)throw new AssertionError(name);checks.add(name);}
  static final class Tasks implements Executor {
    final Deque<Runnable> waiting=new ArrayDeque<>();int submitted,maxWaiting;boolean reject;
    public void execute(Runnable job){if(reject)throw new RejectedExecutionException("controlled rejection");submitted++;waiting.addLast(job);maxWaiting=Math.max(maxWaiting,waiting.size());}
    void one(){if(waiting.isEmpty())throw new AssertionError("Expected queued task");waiting.removeFirst().run();}
  }
  static final class Fixture {
    final Tasks worker=new Tasks(),main=new Tasks();final List<Integer> shown=new ArrayList<>();final List<Exception> errors=new ArrayList<>();int reads;Exception nextError;
    final EnvironmentRefreshQueue<Integer> queue=new EnvironmentRefreshQueue<>(worker,main,()->{reads++;if(nextError!=null){Exception failure=nextError;nextError=null;throw failure;}return reads;},shown::add,errors::add);
  }
  public static void main(String[] args){
    Fixture f=new Fixture();f.queue.request();
    check("Hidden requests schedule zero work",f.worker.submitted==0&&f.main.submitted==0);
    f.queue.visible(true);
    check("Visible transition automatically requests one snapshot",f.worker.submitted==1&&f.worker.waiting.size()==1);
    f.queue.visible(true);
    check("Repeated visible state does not add a refresh",f.worker.submitted==1);
    for(int i=0;i<100;i++)f.queue.request();
    check("100 requests while queued keep only one active worker",f.worker.submitted==1&&f.worker.waiting.size()==1);
    f.worker.one();
    check("Read completion waits for the UI executor",f.reads==1&&f.shown.isEmpty()&&f.main.waiting.size()==1);
    for(int i=0;i<100;i++)f.queue.request();
    check("Requests awaiting UI completion cannot queue parallel reads",f.worker.submitted==1);
    f.main.one();
    check("Same-lifetime snapshot paints without starvation",f.shown.equals(Arrays.asList(1)));
    check("Burst produces exactly one trailing read",f.worker.submitted==2&&f.worker.waiting.size()==1);
    f.worker.one();f.main.one();
    check("Fresh trailing result follows the readable snapshot",f.shown.equals(Arrays.asList(1,2)));
    check("200 coalesced requests total only two reads",f.reads==2&&f.worker.submitted==2&&f.worker.maxWaiting==1);
    check("Each read posts a single UI completion",f.main.submitted==2&&f.main.maxWaiting==1);

    f=new Fixture();f.queue.visible(true);f.worker.one();f.queue.visible(false);f.main.one();
    check("Pause discards an already-completed queued result",f.shown.isEmpty()&&f.errors.isEmpty());
    for(int i=0;i<100;i++)f.queue.request();
    check("Hidden request burst performs no extra read",f.worker.submitted==1);
    f.queue.visible(true);f.worker.one();f.main.one();
    check("Resume reads fresh metadata",f.shown.equals(Arrays.asList(2))&&f.reads==2);

    f=new Fixture();f.queue.visible(true);f.queue.visible(false);f.queue.visible(true);
    for(int i=0;i<100;i++)f.queue.request();
    check("Resume while old read exists keeps one worker",f.worker.submitted==1);
    f.worker.one();f.main.one();
    check("Old lifecycle result does not paint after resume",f.shown.isEmpty());
    check("Old read completion schedules one current-lifetime read",f.worker.submitted==2&&f.worker.waiting.size()==1);
    f.worker.one();f.main.one();
    check("Current lifetime result survives old generation",f.shown.equals(Arrays.asList(2)));

    f=new Fixture();f.queue.visible(true);f.queue.request();f.queue.visible(false);f.worker.one();f.main.one();
    check("Pause clears the trailing request",f.worker.submitted==1&&f.worker.waiting.isEmpty());
    f.queue.close();f.queue.close();f.queue.visible(true);f.queue.request();
    check("Close is terminal and idempotent",f.worker.submitted==1&&f.shown.isEmpty());

    f=new Fixture();f.queue.visible(true);f.worker.one();f.queue.close();f.main.one();
    check("Close discards a pending UI completion",f.shown.isEmpty()&&f.errors.isEmpty());

    f=new Fixture();Exception expected=new Exception("controlled read failure");f.nextError=expected;f.queue.visible(true);f.worker.one();
    check("Read error never calls UI from worker",f.errors.isEmpty());f.main.one();
    check("Read failure is delivered once on main executor",f.errors.equals(Arrays.asList(expected))&&f.shown.isEmpty());
    f.queue.request();f.worker.one();f.main.one();
    check("Read can recover after a failure",f.shown.equals(Arrays.asList(2)));

    f=new Fixture();f.nextError=new Exception("superseded error");f.queue.visible(true);f.queue.request();f.worker.one();f.main.one();
    check("Same-lifetime read error remains visible while retry queues",f.errors.size()==1&&f.worker.submitted==2);
    f.worker.one();f.main.one();check("Trailing read recovers after preceding error",f.shown.equals(Arrays.asList(2)));

    f=new Fixture();f.worker.reject=true;f.queue.visible(true);
    check("Worker rejection is marshalled to UI executor",f.errors.isEmpty()&&f.main.waiting.size()==1);f.main.one();
    check("Worker rejection reports controlled failure",f.errors.size()==1&&f.errors.get(0) instanceof RejectedExecutionException);
    f.worker.reject=false;f.queue.request();f.worker.one();f.main.one();
    check("Explicit refresh recovers from rejected worker",f.shown.equals(Arrays.asList(1)));

    f=new Fixture();f.main.reject=true;f.queue.visible(true);f.worker.one();
    check("Rejected UI executor never paints from worker",f.shown.isEmpty()&&f.errors.isEmpty());
    f.main.reject=false;f.queue.request();f.worker.one();f.main.one();
    check("Explicit refresh recovers after rejected UI delivery",f.shown.equals(Arrays.asList(2)));

    Tasks worker=new Tasks(),main=new Tasks();List<Integer> values=new ArrayList<>();int[] reads={0};EnvironmentRefreshQueue<Integer>[] reference=new EnvironmentRefreshQueue[1];
    reference[0]=new EnvironmentRefreshQueue<>(worker,main,()->++reads[0],value->{values.add(value);if(value==1){for(int i=0;i<100;i++)reference[0].request();}},failure->{throw new AssertionError(failure);});
    reference[0].visible(true);worker.one();main.one();
    check("Reentrant UI requests coalesce into one trailing read",worker.submitted==2&&worker.waiting.size()==1);
    worker.one();main.one();check("Reentrant requests preserve order without recursion",values.equals(Arrays.asList(1,2)));

    Tasks throwingWorker=new Tasks(),throwingMain=new Tasks();int[] applied={0};EnvironmentRefreshQueue<Integer> throwing=new EnvironmentRefreshQueue<>(throwingWorker,throwingMain,()->1,value->{if(++applied[0]==1)throw new IllegalStateException("controlled consumer failure");},failure->{});
    throwing.visible(true);throwingWorker.one();boolean threw=false;try{throwingMain.one();}catch(IllegalStateException expectedFailure){threw=true;}
    check("Consumer error is not misreported as a storage failure",threw);throwing.request();throwingWorker.one();throwingMain.one();
    check("Consumer error cannot strand refresh state",applied[0]==2);

    System.out.print("{\"status\":\"passed\",\"passed\":"+checks.size()+",\"total\":"+checks.size()+",\"burstRequests\":100,\"burstWorkerReads\":2,\"checks\":[");
    for(int i=0;i<checks.size();i++){if(i>0)System.out.print(",");System.out.print("{\"name\":\""+checks.get(i)+"\",\"pass\":true}");}System.out.println("]}");
  }
}
