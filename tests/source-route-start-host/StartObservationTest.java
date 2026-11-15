package local.pocketchat;

import org.json.*;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

public final class StartObservationTest {
  static final JSONArray checks=new JSONArray();
  static final String CASE="11111111-1111-4111-8111-111111111111",SOURCE="5ad586c6b99a8d14454c9589274646feea3c20cf",NONCE="0123456789abcdef0123456789abcdef";
  static void check(String name,boolean pass)throws Exception{checks.put(J.obj("name",name,"pass",pass));if(!pass)throw new AssertionError(name);}
  static void await(CountDownLatch latch)throws Exception{if(!latch.await(3,TimeUnit.SECONDS))throw new AssertionError("Controlled worker did not reach its barrier");}
  static void rejected(String name,Observed network,JSONObject row)throws Exception{boolean rejected=false;try{network.observer.joinFor(1,row);}catch(Exception expected){rejected=true;}check(name,rejected);}
  static final class Observed extends NativeNetwork implements AutoCloseable {
    final SourceRouteStartObservation observer=new SourceRouteStartObservation();
    final CountDownLatch[] entered={new CountDownLatch(1),new CountDownLatch(1)},release={new CountDownLatch(1),new CountDownLatch(1)};
    final List<JSONObject> stops=new CopyOnWriteArrayList<>();final AtomicInteger rootCallbacks=new AtomicInteger(),recoverCallbacks=new AtomicInteger(),queuedCallbacks=new AtomicInteger();
    final CountDownLatch beforeFinally=new CountDownLatch(1),releaseFinally=new CountDownLatch(1);volatile boolean holdFinally;
    SourceRouteStartObservation.Root root;volatile long callbackThread;volatile int requestSerial;volatile RecoveryOutcome rootOutcome,recoveryOutcome;volatile boolean rootOk;String fault="";
    void begin(boolean rootAdapter){Callback callback=rootAdapter?new RecoveryAdapter(outcome->{callbackThread=Thread.currentThread().getId();rootOutcome=outcome;rootOk=outcome.state==RecoveryState.RECOVERED;rootCallbacks.incrementAndGet();}):(ok,message)->{rootOk=ok;rootCallbacks.incrementAndGet();};root=observer.root(callback,CASE,SOURCE,NONCE);restart(callback);}
    void join(boolean registered,boolean wrongRoot){RecoveryCallback callback=outcome->{recoveryOutcome=outcome;recoverCallbacks.incrementAndGet();};SourceRouteStartObservation.Root selected=root;if(wrongRoot)selected=observer.root((ok,message)->{},"22222222-2222-4222-8222-222222222222",SOURCE,NONCE);if(registered)observer.recovery(callback,1,selected);requestSerial=1;recoverOutcome(callback);}
    @Override synchronized void startOperation(Callback callback,int mode){SourceRouteStartObservation.Registration value=observer.registrationBefore("registrationBefore".equals(fault)?null:this,callback,mode);try{super.startOperation(callback,mode);}finally{observer.registrationAfter("registrationAfter".equals(fault)?null:this,value);}}
    @Override boolean runStartOperation(int mode){observer.workerBefore("workerBefore".equals(fault)?null:this,mode);try{return super.runStartOperation(mode);}finally{if(holdFinally){beforeFinally.countDown();try{await(releaseFinally);}catch(Exception failure){throw new RuntimeException(failure);}}observer.workerAfter("workerAfter".equals(fault)?null:this,mode);}}
    @Override void stopOwnedCore(ExitRouteReceipt owned,NetworkDiagnostics.Reason reason){JSONObject row=J.obj("caseId",CASE,"beganAtNs",System.nanoTime(),"recoveryRequestSerial",requestSerial,"owned",J.obj("pid",owned.pid,"servicePid",owned.servicePid,"generation",owned.generation,"configuration",owned.configuration));stops.add(row);observer.stopBefore(this,row);try{super.stopOwnedCore(owned,reason);}finally{SourceRouteStartObservation.put(row,"endedAtNs",System.nanoTime());SourceRouteStartObservation.put(row,"afterRequestSerial",requestSerial);observer.stopAfter(this,row);}}
    @Override void stopTransport(int index)throws Exception{entered[index].countDown();await(release[index]);}
    void finish(int index)throws Exception{release[index].countDown();worker.submit(()->{}).get(3,TimeUnit.SECONDS);Runnable callback;while((callback=main.queue.poll())!=null)callback.run();}
    public void close(){releaseFinally.countDown();for(CountDownLatch latch:release)latch.countDown();worker.shutdownNow();}
  }
  static JSONObject joined()throws Exception{
    try(Observed n=new Observed()){
      n.begin(true);await(n.entered[0]);n.join(true,false);
      check("Original mode1 leaves the running restart queued flag false",n.starting&&!n.restartQueued&&n.startWaiters.size()==2);
      n.finish(0);JSONObject proof=n.observer.joinFor(1,n.stops.get(0)),snapshot=n.observer.snapshot(n.root);
      check("Original start worker launches exactly once for joined recovery",n.launches==1&&snapshot.getJSONArray("workerInvocations").length()==1);
      check("Original worker delivers the same immutable outcome to both adapters",n.rootCallbacks.get()==1&&n.recoverCallbacks.get()==1&&n.rootOutcome==n.recoveryOutcome&&n.recoveryOutcome.state==NativeNetwork.RecoveryState.FAILED&&n.recoveryOutcome.receipt==null&&!n.rootOk);
      check("Observed stop records the real zero-to-one request crossing",n.stops.get(0).getInt("recoveryRequestSerial")==0&&n.stops.get(0).getInt("afterRequestSerial")==1);
      check("Join proves original monitor and exact waiter append",proof.getJSONObject("admission").getBoolean("monitorHeldBefore")&&proof.getJSONObject("admission").getBoolean("monitorHeldAfter")&&proof.getJSONObject("admission").getBoolean("exactAppend"));
      check("Stop and join bind the actual worker Java thread",proof.getLong("javaThreadId")!=Thread.currentThread().getId()&&proof.getLong("javaThreadId")==snapshot.getJSONArray("workerInvocations").getJSONObject(0).getLong("javaThreadId"));
      JSONObject originalOwner=SourceRouteStartObservation.copy(n.stops.get(0).getJSONObject("owned"));n.stops.get(0).getJSONObject("owned").put("pid",999);rejected("A different owned PID cannot reuse the join",n,n.stops.get(0));n.stops.get(0).put("owned",originalOwner);
      n.stops.get(0).put("caseId","22222222-2222-4222-8222-222222222222");rejected("A different stop case cannot reuse the join",n,n.stops.get(0));n.stops.get(0).put("caseId",CASE);
      JSONObject identity=n.stops.get(0).getJSONObject("startInvocation");long id=identity.getLong("invocationIdAfter");identity.put("invocationIdAfter",id+1);rejected("A stop returning in another invocation is rejected",n,n.stops.get(0));identity.put("invocationIdAfter",id);
      long thread=identity.getLong("javaThreadIdAfter");identity.put("javaThreadIdAfter",thread+1);rejected("A stop returning on another Java thread is rejected",n,n.stops.get(0));identity.put("javaThreadIdAfter",thread);
      check("Restoring exact original observations retains the valid join",n.observer.joinFor(1,n.stops.get(0)).getInt("request")==1);
      return J.obj("startObservation",snapshot,"stop",SourceRouteStartObservation.copy(n.stops.get(0)),"join",proof);
    }
  }
  static JSONObject queued()throws Exception{
    try(Observed n=new Observed()){
      n.begin(false);await(n.entered[0]);n.restart((ok,message)->n.queuedCallbacks.incrementAndGet());
      check("Original mode2 sets restartQueued while retaining the first waiter",n.restartQueued&&n.startWaiters.size()==2);
      n.release[0].countDown();await(n.entered[1]);
      check("Original queued restart executes a second actual worker invocation",n.launches==2&&n.observer.snapshot(n.root).getJSONArray("workerInvocations").length()==2);
      check("Queued flag returns false before the second operation completes",!n.restartQueued&&n.starting&&n.rootCallbacks.get()==0&&n.startWaiters.contains(n.root.callback));
      check("Queued restart retains the actual route change lease",ChromiumRouteLease.snapshot().changes==1);
      check("Queued restart fences new pages and downloads",newWorkBlocked());
      n.join(true,false);n.finish(1);JSONObject snapshot=n.observer.snapshot(n.root);JSONArray workers=snapshot.getJSONArray("workerInvocations");
      check("Both worker invocations reuse the exact original root callback",workers.getJSONObject(0).getInt("rootCallbackId")==workers.getJSONObject(1).getInt("rootCallbackId")&&workers.getJSONObject(0).getLong("invocationId")!=workers.getJSONObject(1).getLong("invocationId"));
      boolean specific=false;try{n.observer.joinFor(1,n.stops.get(1));}catch(IOException failure){specific=failure.getMessage().contains("crossed worker invocations");}
      check("Queued restart ABA is rejected by actual invocation identity",specific);
      check("Rejecting observation preserves all original queued callbacks",n.rootCallbacks.get()==1&&n.queuedCallbacks.get()==1&&n.recoverCallbacks.get()==1&&!n.rootOk&&n.recoveryOutcome.state==NativeNetwork.RecoveryState.FAILED);
      check("A failed queued restart releases its batch and waiters",ChromiumRouteLease.snapshot().changes==0&&!n.starting&&!n.restartQueued&&n.startWaiters.isEmpty());
      return snapshot;
    }
  }
  static JSONObject callbacksBeforeFinally()throws Exception{
    ExecutorService actualMain=Executors.newSingleThreadExecutor();
    try(Observed n=new Observed()){
      n.holdFinally=true;n.begin(true);await(n.entered[0]);n.join(true,false);
      Future<?> dispatched=actualMain.submit(()->{try{Runnable message=n.main.queue.poll(3,TimeUnit.SECONDS);if(message==null)throw new AssertionError("Original main.post did not enqueue callbacks");message.run();}catch(Exception failure){throw new RuntimeException(failure);}});
      n.release[0].countDown();await(n.beforeFinally);dispatched.get(3,TimeUnit.SECONDS);
      CompletableFuture<Void> completion=n.observer.workerCompletion(n.root);
      check("Real asynchronous main can deliver both callbacks before workerAfter",n.rootCallbacks.get()==1&&n.recoverCallbacks.get()==1&&n.rootOutcome==n.recoveryOutcome&&!completion.isDone());
      check("Callback thread is separate from the actual worker and test caller",n.callbackThread!=Thread.currentThread().getId()&&n.callbackThread!=n.observer.snapshot(n.root).getJSONArray("workerInvocations").getJSONObject(0).getLong("javaThreadId"));
      rejected("Callbacks alone cannot stand in for the missing actual worker ending",n,n.stops.get(0));
      boolean timedOut=false;try{completion.get(10,TimeUnit.MILLISECONDS);}catch(TimeoutException expected){timedOut=true;}
      check("An original bounded wait rejects an unfinished observer without altering it",timedOut&&!completion.isDone()&&n.launches==1&&n.rootCallbacks.get()==1&&n.recoverCallbacks.get()==1);
      n.releaseFinally.countDown();completion.get(3,TimeUnit.SECONDS);
      check("Only actual workerAfter completes the observation future",completion.isDone()&&!completion.isCompletedExceptionally()&&n.observer.snapshot(n.root).getJSONArray("workerInvocations").getJSONObject(0).has("endedAtNs"));
      JSONObject proof=n.observer.joinFor(1,n.stops.get(0));
      check("The same asynchronously completed operation now yields a valid join",proof.getInt("request")==1&&n.launches==1&&n.rootCallbacks.get()==1&&n.recoverCallbacks.get()==1);
      return J.obj("startObservation",n.observer.snapshot(n.root),"stop",SourceRouteStartObservation.copy(n.stops.get(0)),"join",proof);
    }finally{actualMain.shutdownNow();}
  }
  static void wrongBindings()throws Exception{
    for(boolean wrongRoot:new boolean[]{false,true})try(Observed n=new Observed()){
      n.begin(false);await(n.entered[0]);n.join(wrongRoot,wrongRoot);n.finish(0);
      rejected(wrongRoot?"Another scope cannot register a joined recovery":"An unregistered adapter cannot claim a joined recovery",n,n.stops.get(0));
      check(wrongRoot?"Wrong-scope observation does not suppress original callbacks":"Unknown-adapter observation does not suppress original callbacks",n.rootCallbacks.get()==1&&n.recoverCallbacks.get()==1&&n.launches==1);
    }
  }
  static void hookFailures()throws Exception{
    for(String fault:new String[]{"registrationBefore","registrationAfter","workerBefore","workerAfter"})try(Observed n=new Observed()){
      n.fault=fault;n.begin(false);await(n.entered[0]);n.join(true,false);n.finish(0);
      check(fault+" observer failure never skips original worker or callbacks",n.launches==1&&n.rootCallbacks.get()==1&&n.recoverCallbacks.get()==1&&!n.rootOk&&n.recoveryOutcome.state==NativeNetwork.RecoveryState.FAILED);
      check(fault+" observer failure is retained as rejected evidence",n.observer.snapshot(n.root).getJSONArray("errors").length()>0);
      rejected(fault+" incomplete proof cannot pass",n,n.stops.get(0));
      check(fault+" completes the observation exceptionally instead of waiting indefinitely",n.observer.workerCompletion(n.root).isCompletedExceptionally());
    }
  }
  static boolean newWorkBlocked(){
    ChromiumRouteLease.Handle surface=ChromiumRouteLease.acquireSurface(),download=ChromiumRouteLease.acquireDownload();
    try{return surface==null&&download==null;}finally{if(surface!=null)surface.close();if(download!=null)download.close();}
  }
  static final class LeaseNetwork extends NativeNetwork implements AutoCloseable {
    final boolean[] successes;
    final CountDownLatch[] entered,release;
    final List<Integer> modes=new CopyOnWriteArrayList<>();
    int proofObservations;
    LeaseNetwork(boolean... successes){
      this.successes=successes;entered=new CountDownLatch[successes.length];release=new CountDownLatch[successes.length];
      for(int i=0;i<successes.length;i++){entered[i]=new CountDownLatch(1);release[i]=new CountDownLatch(1);}
    }
    @Override boolean runStartOperation(int mode){modes.add(mode);return super.runStartOperation(mode);}
    @Override void startNow()throws Exception{
      int index=launches++;
      if(index>=successes.length)throw new AssertionError("Unexpected extra startup");
      entered[index].countDown();await(release[index]);
      if(!successes[index])throw new IOException("Controlled startup failure");
      message="Controlled startup succeeded";
    }
    @Override void observeRunning(){proofObservations++;}
    void finish(int index)throws Exception{release[index].countDown();worker.submit(()->{}).get(3,TimeUnit.SECONDS);callbacks();}
    void callbacks(){Runnable callback;while((callback=main.queue.poll())!=null)callback.run();}
    public void close()throws Exception{
      for(CountDownLatch latch:release)latch.countDown();
      worker.shutdownNow();
      if(!worker.awaitTermination(3,TimeUnit.SECONDS))throw new AssertionError("Controlled startup worker did not finish");
    }
  }
  static void repeatedRestarts()throws Exception{
    for(boolean success:new boolean[]{true,false})try(LeaseNetwork n=new LeaseNetwork(false,true,success)){
      String label=success?"success":"failure";
      AtomicInteger first=new AtomicInteger(),second=new AtomicInteger(),third=new AtomicInteger();
      List<NativeNetwork.RecoveryOutcome> outcomes=new ArrayList<>();
      n.restart(new NativeNetwork.RecoveryAdapter(result->{first.incrementAndGet();outcomes.add(result);}));await(n.entered[0]);
      n.restart(new NativeNetwork.RecoveryAdapter(result->{second.incrementAndGet();outcomes.add(result);}));
      n.release[0].countDown();await(n.entered[1]);
      check("Repeated restart keeps the second round fenced: "+label,ChromiumRouteLease.snapshot().changes==1&&newWorkBlocked());
      n.restart(new NativeNetwork.RecoveryAdapter(result->{third.incrementAndGet();outcomes.add(result);}));
      n.release[1].countDown();await(n.entered[2]);
      check("Repeated restart keeps the third round fenced: "+label,ChromiumRouteLease.snapshot().changes==1&&newWorkBlocked());
      check("Repeated restart does not deliver an intermediate result: "+label,n.starting&&!n.restartQueued&&n.startWaiters.size()==3&&n.main.queue.isEmpty());
      n.finish(2);
      check("Repeated restart delivers the same final outcome exactly once: "+label,first.get()==1&&second.get()==1&&third.get()==1&&outcomes.size()==3&&outcomes.get(0)==outcomes.get(1)&&outcomes.get(1)==outcomes.get(2)&&outcomes.get(0).state==(success?NativeNetwork.RecoveryState.RECOVERED:NativeNetwork.RecoveryState.FAILED));
      check("Repeated restart retires its complete batch: "+label,n.launches==3&&n.modes.equals(Arrays.asList(2,2,2))&&!n.starting&&!n.restartQueued&&n.startWaiters.isEmpty()&&ChromiumRouteLease.snapshot().changes==0);
      check("Only the final successful restart publishes proof: "+label,n.proofObservations==(success?1:0));
    }
  }
  static void releasedLeaseReentry()throws Exception{
    try(LeaseNetwork n=new LeaseNetwork(true,true)){
      AtomicBoolean armed=new AtomicBoolean(true);AtomicInteger first=new AtomicInteger(),next=new AtomicInteger();
      NativeNetwork.Callback nextCallback=(ok,message)->next.incrementAndGet();
      Runnable listener=()->{if(ChromiumRouteLease.snapshot().changes==0&&armed.compareAndSet(true,false))n.restart(nextCallback);};
      ChromiumRouteLease.addListener(listener);
      try{
        n.restart((ok,message)->first.incrementAndGet());await(n.entered[0]);n.release[0].countDown();await(n.entered[1]);
        check("Released lease listener starts a separate fenced batch",n.starting&&!n.restartQueued&&n.startWaiters.size()==1&&n.startWaiters.get(0)==nextCallback&&ChromiumRouteLease.snapshot().changes==1&&newWorkBlocked());
        n.callbacks();
        check("Previous batch callback cannot consume the listener's new waiter",first.get()==1&&next.get()==0&&n.starting&&n.startWaiters.size()==1);
        n.finish(1);
        check("Listener reentry completes both batches exactly once",first.get()==1&&next.get()==1&&n.launches==2&&!n.starting&&n.startWaiters.isEmpty()&&ChromiumRouteLease.snapshot().changes==0);
      }finally{ChromiumRouteLease.removeListener(listener);}
    }
  }
  static void rejectedSubmission()throws Exception{
    try(LeaseNetwork n=new LeaseNetwork()){
      n.worker.shutdown();n.recoveryBlocked=true;
      AtomicInteger first=new AtomicInteger(),joined=new AtomicInteger(),later=new AtomicInteger();
      List<NativeNetwork.RecoveryOutcome> outcomes=new ArrayList<>();
      AtomicBoolean joinedOnce=new AtomicBoolean(),releasedOnce=new AtomicBoolean();
      Runnable join=()->{if(n.starting&&joinedOnce.compareAndSet(false,true))n.restart(new NativeNetwork.RecoveryAdapter(result->{joined.incrementAndGet();outcomes.add(result);}));};
      Runnable release=()->{if(ChromiumRouteLease.snapshot().changes==0&&releasedOnce.compareAndSet(false,true))n.restart(new NativeNetwork.RecoveryAdapter(result->{later.incrementAndGet();outcomes.add(result);}));};
      n.routeListeners.add(join);ChromiumRouteLease.addListener(release);
      try{
        n.restart(new NativeNetwork.RecoveryAdapter(result->{first.incrementAndGet();outcomes.add(result);}));
        check("Rejected startup retires its waiters before release-listener reentry",!n.starting&&!n.restartQueued&&n.startWaiters.isEmpty()&&ChromiumRouteLease.snapshot().changes==0&&releasedOnce.get());
        check("Rejected startup preserves the prior recovery block",n.recoveryBlocked&&n.launches==0);
        n.callbacks();
        check("Rejected startup reports every original and reentrant waiter once",first.get()==1&&joined.get()==1&&later.get()==1&&outcomes.size()==3&&outcomes.stream().allMatch(result->result.state==NativeNetwork.RecoveryState.FAILED&&result.receipt==null&&!result.message.isEmpty()));
        check("Rejected startup leaves no delayed callback or route barrier",n.main.queue.isEmpty()&&!n.starting&&!n.restartQueued&&n.startWaiters.isEmpty()&&ChromiumRouteLease.snapshot().changes==0);
      }finally{n.routeListeners.remove(join);ChromiumRouteLease.removeListener(release);}
    }
  }
  public static void main(String[] args)throws Exception{JSONObject report=J.obj("status","failed","syntheticControlledHost",true,"checks",checks);try{report.put("joined",joined());report.put("queuedRestart",queued());report.put("callbacksBeforeFinally",callbacksBeforeFinally());wrongBindings();hookFailures();repeatedRestarts();releasedLeaseReentry();rejectedSubmission();report.put("status","passed");}finally{report.put("total",checks.length());Files.writeString(Path.of(args[0]),report.toString(2));}System.out.println("Start observation checks: "+checks.length());}
}

class NativeNetwork {
  /* ACTUAL_NATIVE_START_MEMBERS */
  // This original start scheduler fixture has no concurrent configuration apply.
  // The configuration-bound admission branch is tested in its dedicated suite.
  final Object activeConfiguration=null;
  final ExecutorService worker=Executors.newSingleThreadExecutor();final Dispatcher main=new Dispatcher();final List<Callback> startWaiters=new ArrayList<>();volatile boolean starting,ready,recoveryBlocked;boolean restartQueued;String message="synthetic source rejected",currentEntry="Entry|synthetic";long reconnectAttempts;ExitRouteReceipt verifiedRoute;int launches;
  static class ExitRouteReceipt {final int pid,servicePid=900;final String generation,configuration="a".repeat(64);ExitRouteReceipt(int index){pid=900+index;generation=String.format("00000000-0000-4000-8000-%012d",index);}}
  static class ExitMismatch extends IOException{}
  static class ExitCheckUnavailable extends IOException{}
  static class RouteTransactionFailure extends IOException{}
  static class StartupRouteFailure extends IOException{}
  static class Admission{boolean usable(){return false;}}
  Admission connectionAdmission(){return new Admission();}
  boolean coreAlive(){return false;}void cancelMaintenance(){}void bindDiagnostics(){}void note(NetworkDiagnostics.Event e,NetworkDiagnostics.Reason r,NetworkDiagnostics.Stage s,long value){}
  boolean configurationMatches(){return false;}boolean verifiedRouteCurrent(){return false;}void recoverExistingRoute(){}void verifyExit()throws IOException{}String display(String text){return text;}boolean adoptTransport(){return false;}boolean retainedFailure(Exception e){return false;}boolean retainVerifiedRoute(Exception e){return false;}
  void report(String value){message=value;}void stopNow(NetworkDiagnostics.Reason reason){}
  void startNow()throws Exception{int index=launches++;stopOwnedCore(new ExitRouteReceipt(index+1),NetworkDiagnostics.Reason.START_FAILED);throw new StartupRouteFailure();}
  void stopOwnedCore(ExitRouteReceipt receipt,NetworkDiagnostics.Reason reason){try{stopTransport(launches-1);}catch(Exception failure){throw new RuntimeException(failure);}}
  void stopTransport(int index)throws Exception{}
  void observeRunning(){throw new AssertionError("Live core application is outside the start-observer fixture scope");}
}
class Dispatcher {final BlockingQueue<Runnable> queue=new LinkedBlockingQueue<>();void post(Runnable value){queue.add(value);}}
class NetworkDiagnostics {enum Event{RECONNECT_ATTEMPT,FAILURE}enum Reason{REQUESTED,REPLACE,EXIT_MISMATCH,START_FAILED}enum Stage{RECOVER}}
/** Original failure/join cases reject publication; lease cases only count this boundary call. */
class NetworkCoreApplication {static void observeRunning(NativeNetwork network){network.observeRunning();}}
