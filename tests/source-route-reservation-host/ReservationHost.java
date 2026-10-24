package local.pocketchat;

import org.json.*;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import android.os.SystemClock;

/** Controlled host contracts. Failure containment is separate from external cleanup proof. */
public final class ReservationHost {
  static final JSONArray checks=new JSONArray(),cases=new JSONArray();
  static final String SOURCE="ec196a4394a3172e7ed2558a00fc4f2b0a75e2de",NONCE="0123456789abcdef0123456789abcdef";
  static JSONObject blockedEvidence;
  static void check(String name,boolean pass)throws Exception{checks.put(J.obj("name",name,"pass",pass));if(!pass)throw new AssertionError(name);}
  interface Case {JSONObject run()throws Exception;}
  static void run(String name,Case work){android.os.SystemClock.set(1000000000L);try{cases.put(J.obj("case",name,"result",work.run()));}catch(Throwable error){cases.put(J.obj("case",name,"error",error.toString()));try{checks.put(J.obj("name",name+" completes its declared host contract","pass",false));}catch(Throwable ignored){}}}
  static void await(CountDownLatch latch)throws Exception{if(!latch.await(3,TimeUnit.SECONDS))throw new IOException("Host watchdog: barrier missing");}
  static boolean rejects(Case work){try{work.run();return false;}catch(Exception expected){return true;}}

  static final class Gate implements SourceRouteStartReservation.Gate {
    final Observed network;final ChatSession session;final long uiThread=Thread.currentThread().getId();
    volatile Object owner;volatile boolean claimedUnderMonitor;
    Gate(Observed network){this.network=network;session=new ChatSession(network);}
    public boolean onUiThread(){return Thread.currentThread().getId()==uiThread;}
    public Object owner(){return owner;}
    public boolean connecting(){return session.connecting;}
    public JSONObject contacts(){return J.obj("fixedTarget",network.contacts.get(),"decoyTarget",0,"ip",0,"plainProbe",0,"fixedAllConnected",network.connections.get(),"decoyAllConnected",network.decoyConnections.get());}
    public void claim(SourceRouteStartReservation value){claimedUnderMonitor=Thread.holdsLock(network);owner=value.scopeToken;network.pending=value;}
  }
  static final class Observed extends NativeNetwork implements AutoCloseable {
    final SourceRouteStartObservation observer=new SourceRouteStartObservation();volatile SourceRouteStartReservation pending;
    final Gate gate=new Gate(this);volatile CountDownLatch startBlock;final CountDownLatch startEntered=new CountDownLatch(1);
    @Override synchronized void startOperation(Callback callback,int mode){SourceRouteStartObservation.Registration r=observer.registrationBefore(this,callback,mode);try{super.startOperation(callback,mode);}finally{observer.registrationAfter(this,r);}}
    @Override void runStartOperation(int mode){observer.workerBefore(this,mode);try{SourceRouteStartReservation task=pending;if(task==null)super.runStartOperation(mode);else task.runReservedWorker(mode,()->super.runStartOperation(mode));}finally{observer.workerAfter(this,mode);}}
    @Override void startNow()throws Exception{startEntered.countDown();CountDownLatch barrier=startBlock;if(barrier!=null)await(barrier);super.startNow();}
    void workerOnly()throws Exception{long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(3);while(starting){if(System.nanoTime()>deadline)throw new IOException("Host watchdog: native worker still running");Thread.sleep(1);}worker.submit(()->{}).get(3,TimeUnit.SECONDS);}
    void finish()throws Exception{workerOnly();main.drain();}
    public void close(){if(startBlock!=null)startBlock.countDown();worker.shutdownNow();}
  }
  static SourceRouteStartReservation reservation(Observed network,String name,SourceRouteStartReservation.Preparation preparation){return new SourceRouteStartReservation(network,network.observer,network.gate,new Object(),name,SOURCE,NONCE,preparation);}
  static JSONObject prepare(Observed network)throws Exception{
    network.order.add("publishOriginal");boolean stopped=network.stopNow();network.order.add("mutation");network.mutated=true;network.order.add("contacts");
    return J.obj("managedCoreStopped",stopped&&!network.coreAlive(),"contacts",network.gate.contacts());
  }
  static JSONObject successfulReservation()throws Exception{
    try(Observed n=new Observed()){
      SourceRouteStartReservation task=reservation(n,"valid",()->prepare(n));check("Deadline begins with the original seventy-five-second budget",task.deadlineNs-task.beganAtNs==TimeUnit.SECONDS.toNanos(75));
      check("Actual UI reservation succeeds",task.tryReserve());n.finish();
      check("Claim uses a short real native monitor",n.gate.claimedUnderMonitor);
      check("Preparation did not manufacture session busy or cancel retry token",!n.gate.session.operation&&!n.gate.session.submitting&&n.gate.session.recoveryToken==7);
      check("Preparation invokes real stopNow and clearReadyState before actual source body",n.stops.get()==2&&n.sawMutated&&n.order.indexOf("publishOriginal")<n.order.indexOf("mutation")&&n.order.indexOf("mutation")<n.order.indexOf("startNow"));
      check("Original native body and callback execute exactly once",n.launches==1&&task.preparations==1&&task.delegations==1&&task.callbackCount==1&&!task.awaitCallback());
      task.verifyAccepted();check("Observer proves one completed original worker invocation",n.observer.snapshot(task.root).getJSONArray("workerInvocations").length()==1&&!n.starting&&n.startWaiters.isEmpty());
      return SourceRouteStartObservation.copy(task.evidence);
    }
  }
  static JSONObject oldAdmissionControl()throws Exception{
    try(Observed n=new Observed()){
      n.startBlock=new CountDownLatch(1);n.gate.session.recoveryScheduled=true;n.gate.session.runRecovery(7);await(n.startEntered);
      NetworkSourcesRouteIntegrationActivity activity=new NetworkSourcesRouteIntegrationActivity(n,n.gate.session);SourceRouteTerminalObserver original=new SourceRouteTerminalObserver(activity);
      boolean rejected=false;try{original.begin("next-negative",n.gate.contacts());}catch(Exception expected){rejected=true;}
      check("Actual original runRecovery can reach the old begin rejection",rejected&&n.starting&&n.gate.session.connecting&&n.gate.session.recoveryAttempt==1);
      check("The old-control retry token and busy fields remain unchanged",n.gate.session.recoveryToken==7&&!n.gate.session.operation&&!n.gate.session.submitting);
      n.startBlock.countDown();n.finish();return J.obj("beginRejected",rejected,"defaultRecoveryCalls",n.gate.session.opens);
    }
  }
  static JSONObject naturalJoin()throws Exception{
    CountDownLatch entered=new CountDownLatch(1),release=new CountDownLatch(1);
    try(Observed n=new Observed()){
      SourceRouteStartReservation task=reservation(n,"natural-mode1",()->{JSONObject value=prepare(n);entered.countDown();await(release);return value;});task.tryReserve();await(entered);
      n.gate.session.recoveryScheduled=true;n.gate.session.runRecovery(7);
      check("Actual runRecovery naturally appends mode1 to the reserved root",n.startWaiters.size()==2&&!n.restartQueued&&n.gate.session.opens==1&&n.gate.session.recoveryAttempt==1);
      check("Natural default retry is neither cancelled nor marked artificially busy",n.gate.session.recoveryToken==7&&!n.gate.session.operation&&!n.gate.session.submitting);
      release.countDown();n.finish();check("Joined default callback is retained by original callback loop",n.gate.session.callbacks==1&&task.callbackCount==1&&n.launches==1&&!n.gate.session.connecting);task.verifyAccepted();
      JSONObject snapshot=n.observer.snapshot(task.root);check("Actual observer records the mode1 waiter binding",snapshot.getJSONArray("admissions").getJSONObject(0).getInt("mode")==1&&snapshot.getJSONArray("admissions").getJSONObject(0).getBoolean("adapterCallbackMatches"));
      return J.obj("reservation",SourceRouteStartObservation.copy(task.evidence),"startObservation",snapshot);
    }finally{release.countDown();}
  }
  static JSONObject queuedAba()throws Exception{
    CountDownLatch entered=new CountDownLatch(1),release=new CountDownLatch(1);
    try(Observed n=new Observed()){
      SourceRouteStartReservation task=reservation(n,"queued-mode2",()->{JSONObject value=prepare(n);entered.countDown();await(release);return value;});task.tryReserve();await(entered);AtomicInteger extra=new AtomicInteger();n.restart((ok,message)->extra.incrementAndGet());
      check("A real second restart retains queued mode2 semantics",n.restartQueued&&n.startWaiters.size()==2);release.countDown();n.finish();
      check("Queued mode2 delegates both actual invocations without repeating preparation",n.launches==2&&task.delegations==2&&task.preparations==1&&task.callbackCount==1&&extra.get()==1);
      check("Queued invocation ABA remains rejected rather than accepted",task.failure!=null&&rejects(()->{task.verifyAccepted();return new JSONObject();}));
      return J.obj("reservation",SourceRouteStartObservation.copy(task.evidence),"startObservation",n.observer.snapshot(task.root));
    }finally{release.countDown();}
  }
  static JSONObject preparationFailure()throws Exception{
    try(Observed n=new Observed()){
      n.startupSucceeds=true;SourceRouteStartReservation task=reservation(n,"failed-preparation",()->{throw new IOException("controlled preparation failure");});task.tryReserve();n.finish();
      check("Preparation exception still delegates unmodified native body once",n.launches==1&&task.delegations==1&&task.callbackCount==1&&!n.starting&&n.startWaiters.isEmpty());
      check("Actual successful native callback is retained instead of rewritten",task.evidence.getJSONObject("actualCallback").getBoolean("ok")&&n.ready);
      check("Delegated controlled IO side effects stay recorded despite preparation failure",n.contacts.get()==1&&n.connections.get()==1&&task.evidence.getJSONObject("actualContactsAfterOriginal").getInt("fixedTarget")==1&&task.evidence.getJSONObject("actualContactsAfterOriginal").getInt("fixedAllConnected")==1);
      check("Preparation failure permanently rejects an otherwise successful callback",task.failure!=null&&!task.prepared&&rejects(()->{task.awaitCallback();return new JSONObject();})&&rejects(()->{task.verifyAccepted();return new JSONObject();}));
      return SourceRouteStartObservation.copy(task.evidence);
    }
  }
  static JSONObject unownedModeZero()throws Exception{
    JSONArray observations=new JSONArray();
    for(boolean duringPreparation:new boolean[]{true,false}){
      CountDownLatch entered=new CountDownLatch(1),release=new CountDownLatch(1);
      try(Observed n=new Observed()){
        if(!duringPreparation)n.startBlock=release;
        SourceRouteStartReservation task=reservation(n,duringPreparation?"mode0-during-preparation":"mode0-during-original",()->{JSONObject value=prepare(n);if(duringPreparation){entered.countDown();await(release);}return value;});task.tryReserve();await(duringPreparation?entered:n.startEntered);AtomicInteger extra=new AtomicInteger();n.start((ok,message)->extra.incrementAndGet());
        check((duringPreparation?"Preparation":"Original-body")+" mode0 bypass really appends an unowned waiter",n.startWaiters.size()==2&&!n.restartQueued&&n.observer.snapshot(task.root).getJSONArray("admissions").getJSONObject(0).getInt("mode")==0);
        release.countDown();n.finish();boolean rejected=rejects(()->{task.verifyAccepted();return new JSONObject();});
        check((duringPreparation?"Preparation":"Original-body")+" mode0 callback remains delivered while qualification is sticky rejected",extra.get()==1&&task.callbackCount==1&&n.launches==1&&task.delegations==1&&rejected&&task.failure!=null&&!n.starting&&n.startWaiters.isEmpty());observations.put(J.obj("reservation",SourceRouteStartObservation.copy(task.evidence),"startObservation",n.observer.snapshot(task.root)));
      }finally{release.countDown();}
    }
    return J.obj("unownedModeZeroObservations",observations);
  }
  static JSONObject preparationContacts()throws Exception{
    JSONArray observations=new JSONArray();
    for(boolean returnsCurrent:new boolean[]{false,true})try(Observed n=new Observed()){
      SourceRouteStartReservation task=reservation(n,returnsCurrent?"forbidden-rebaseline":"stale-returned-contacts",()->{JSONObject old=n.gate.contacts();n.stopNow();n.contacts.incrementAndGet();n.connections.incrementAndGet();return J.obj("managedCoreStopped",true,"contacts",returnsCurrent?n.gate.contacts():old);});task.tryReserve();n.finish();
      check((returnsCurrent?"A newly returned baseline":"A stale returned snapshot")+" cannot conceal actual preparation contacts",task.failure!=null&&!task.prepared&&task.evidence.getJSONObject("admissionContacts").getInt("fixedTarget")==0&&task.evidence.getJSONObject("actualPreparationContacts").getInt("fixedTarget")==1&&task.evidence.getJSONObject("actualPreparationContacts").getInt("fixedAllConnected")==1);
      check((returnsCurrent?"Rebaseline rejection":"Stale-contacts rejection")+" remains failed after original delegation and callback",task.delegations==1&&task.callbackCount==1&&rejects(()->{task.verifyAccepted();return new JSONObject();}));observations.put(SourceRouteStartObservation.copy(task.evidence));
    }
    return J.obj("controlledSideEffectObservations",observations,"actualNetworkExecution",false);
  }
  static JSONObject oldCallback()throws Exception{
    try(Observed n=new Observed()){
      SourceRouteStartReservation first=reservation(n,"old-scope",()->prepare(n));first.tryReserve();n.workerOnly();
      n.gate.owner=null;SourceRouteStartReservation second=reservation(n,"new-scope",()->prepare(n));second.tryReserve();n.finish();
      check("Late old callback binds only its own failed scope",first.failure!=null&&first.callbackCount==1&&n.gate.owner==second.scopeToken&&n.pending==second);
      second.verifyAccepted();check("Late old callback does not complete or corrupt the replacement reservation",second.failure==null&&second.callbackCount==1&&second.delegations==1);
      return J.obj("old",SourceRouteStartObservation.copy(first.evidence),"current",SourceRouteStartObservation.copy(second.evidence));
    }
  }
  static JSONObject deadlinesAndBusy()throws Exception{
    try(Observed n=new Observed()){
      n.startBlock=new CountDownLatch(1);n.restart((ok,message)->{});await(n.startEntered);SourceRouteStartReservation waiting=reservation(n,"busy",()->prepare(n));
      check("Busy observation does not reserve or mutate real pending operation",!waiting.tryReserve()&&waiting.root==null&&waiting.preparations==0&&n.startWaiters.size()==1&&n.pending==null);
      android.os.SystemClock.set(waiting.deadlineNs+1);check("Busy admission cannot acquire a fresh budget after seventy-five seconds",rejects(()->{waiting.tryReserve();return new JSONObject();})&&waiting.root==null&&waiting.failure!=null&&waiting.state.equals("failed"));
      n.startBlock.countDown();n.finish();
      android.os.SystemClock.advance(TimeUnit.SECONDS.toNanos(1));SourceRouteTerminalObserver observer=new SourceRouteTerminalObserver(new NetworkSourcesRouteIntegrationActivity(n,n.gate.session));SourceRouteTerminalObserver.Scope scope=new SourceRouteTerminalObserver.Scope("fetch",NONCE,n.gate.contacts());observer.beginFetch(scope);
      check("Actual original fetch budget remains twenty-two seconds",scope.deadlineNs-scope.evidence.getLong("fetchBeganAtNs")==TimeUnit.SECONDS.toNanos(22));android.os.SystemClock.set(scope.deadlineNs+1);
      check("Actual remaining rejects the expired original fetch phase",rejects(()->{SourceRouteTerminalObserver.remaining(scope);return new JSONObject();}));return SourceRouteStartObservation.copy(waiting.evidence);
    }
  }
  static JSONObject wrongAdmissionThread()throws Exception{
    try(Observed n=new Observed()){
      SourceRouteStartReservation task=reservation(n,"wrong-ui-thread",()->prepare(n));AtomicReference<Throwable> rejected=new AtomicReference<>();Thread other=new Thread(()->{try{task.tryReserve();}catch(Throwable failure){rejected.set(failure);}},"controlled-non-ui-admission");other.start();other.join(2000);
      check("Wrong-thread admission fails before reserving any real operation",!other.isAlive()&&rejected.get()!=null&&task.root==null&&n.pending==null&&n.gate.owner==null&&!n.starting&&n.startWaiters.isEmpty());
      check("Wrong-thread failure remains sticky on a later genuine UI attempt",task.failure==rejected.get()&&task.state.equals("failed")&&rejects(()->{task.tryReserve();return new JSONObject();})&&n.launches==0&&task.preparations==0);
      return SourceRouteStartObservation.copy(task.evidence);
    }
  }
  static JSONObject permanentlyBlockedPreparation()throws Exception{
    CountDownLatch entered=new CountDownLatch(1),release=new CountDownLatch(1);long realBegan=System.nanoTime();
    try(Observed n=new Observed()){
      SourceRouteStartReservation task=reservation(n,"non-returning-preparation",()->{JSONObject value=prepare(n);entered.countDown();for(;;){try{release.await();break;}catch(InterruptedException ignored){}}return value;});task.tryReserve();await(entered);
      synchronized(n){check("Preparation leaves the native monitor available while private IO is blocked",n.starting&&n.startWaiters.contains(task.callback));}
      android.os.SystemClock.set(task.deadlineNs+1);boolean callerRejected=rejects(()->{task.awaitCallback();return new JSONObject();});
      JSONObject atDeadline=J.obj("nowNs",android.os.SystemClock.elapsedRealtimeNanos(),"originalDeadlineNs",task.deadlineNs,"callerRejected",callerRejected,"starting",n.starting,"actualWaiters",n.startWaiters.size(),"rootWaiterRetained",n.startWaiters.contains(task.callback),"originalDelegations",task.delegations,"originalCallbacks",task.callbackCount,"actualWorkerCompletionDone",n.observer.workerCompletion(task.root).isDone());
      blockedEvidence=J.obj("atOriginalDeadline",atDeadline,"nativeOperationStillOwnedAtDeadline",callerRejected&&n.starting&&n.startWaiters.contains(task.callback)&&task.delegations==0&&task.callbackCount==0);
      check("Caller timeout rejects while the genuine original operation remains pending",blockedEvidence.getBoolean("nativeOperationStillOwnedAtDeadline"));
      SourceRouteStartReservation next=reservation(n,"forbidden-next-case",()->prepare(n));boolean noNext=rejects(()->{next.tryReserve();return new JSONObject();});
      check("Failed budget remains sticky and cannot admit another case",task.failure!=null&&noNext&&next.root==null&&next.preparations==0&&n.gate.owner==task.scopeToken&&n.startWaiters.size()==1);
      blockedEvidence.put("budgetFailureContained",task.failure!=null&&noNext);blockedEvidence.put("cleanupProofPending",true);blockedEvidence.put("externalCleanupScope","A real failure cleanup would need installed test package/source/nonce/PID-generation validation; not executed by this host probe.");
      // Teardown only: this release is explicitly after the original deadline.
      release.countDown();n.finish();boolean lateRejected=rejects(()->{task.verifyAccepted();return new JSONObject();});blockedEvidence.put("lateTeardown",J.obj("nowNs",android.os.SystemClock.elapsedRealtimeNanos(),"afterOriginalDeadline",android.os.SystemClock.elapsedRealtimeNanos()>task.deadlineNs,"starting",n.starting,"actualWaiters",n.startWaiters.size(),"originalDelegations",task.delegations,"originalCallbacks",task.callbackCount,"acceptanceStillRejected",lateRejected,"scope","Post-deadline host teardown; not original-budget completion"));
      check("Late barrier release is never counted as original-budget cleanup or acceptance",lateRejected&&task.failure!=null&&task.delegations==1&&task.callbackCount==1);
      blockedEvidence.put("realHostElapsedNanos",System.nanoTime()-realBegan);blockedEvidence.put("controlledClockNotRealSeventyFiveSecondMeasurement",true);return SourceRouteStartObservation.copy(task.evidence);
    }finally{release.countDown();}
  }
  public static void main(String[] arguments)throws Exception{
    run("valid reservation",ReservationHost::successfulReservation);run("original admission race control",ReservationHost::oldAdmissionControl);run("natural mode1",ReservationHost::naturalJoin);run("queued mode2 ABA",ReservationHost::queuedAba);run("preparation failure",ReservationHost::preparationFailure);run("unowned mode0",ReservationHost::unownedModeZero);run("preparation contacts",ReservationHost::preparationContacts);run("late old callback",ReservationHost::oldCallback);run("original budgets and busy",ReservationHost::deadlinesAndBusy);run("wrong admission thread",ReservationHost::wrongAdmissionThread);run("permanently blocked preparation",ReservationHost::permanentlyBlockedPreparation);
    int passed=0;for(int i=0;i<checks.length();i++)if(checks.getJSONObject(i).getBoolean("pass"))passed++;
    boolean contained=blockedEvidence!=null&&blockedEvidence.optBoolean("nativeOperationStillOwnedAtDeadline")&&blockedEvidence.optBoolean("budgetFailureContained");JSONObject result=J.obj("status",contained?"cleanup-proof-pending":"unresolved","hostControlsComplete",passed==checks.length(),"checks",checks,"passed",passed,"total",checks.length(),"cases",cases,"deadlineFailureEvidence",blockedEvidence,"acceptedAsRepair",false,"actualAndroidExecution",false,"actualBinderExecution",false,"actualNetworkExecution",false,"productPerformanceB",false,"scope","Actual selected production native scheduling/stop/clear and session retry methods with explicit controlled IO, main queue and clock. Original-budget failure/no-next-case is separate from source-bound external package cleanup; no application or performance acceptance.");Files.writeString(Path.of(arguments[0]),result.toString(2));System.out.println("Reservation prototype: "+result.optString("status")+", host contracts "+passed+"/"+checks.length());if(!contained||passed!=checks.length())System.exit(1);System.exit(2);
  }
}

class NativeNetwork {
  /* ACTUAL_NATIVE_MEMBERS */
  final ScheduledExecutorService worker=Executors.newSingleThreadScheduledExecutor();final Dispatcher main=new Dispatcher();final List<Callback> startWaiters=new ArrayList<>();
  volatile boolean starting,ready,recoveryBlocked;boolean restartQueued;String message="controlled source rejection",currentEntry="";long reconnectAttempts,routeSerial,nextExitCheckAt,healthObservedAt;int exitCheckFailures,failures,healthTargetCode;String healthStatus="unknown";NetworkHealthPolicy.Admission admission=NetworkHealthPolicy.Admission.BLOCKED;
  ExitRouteReceipt verifiedRoute;java.lang.Process process;final AtomicReference<NetworkDiagnostics.Reason> coreStopReason=new AtomicReference<>();final Transport transport=new Transport(this);
  Object currentProbe;JSONObject latencyReading=new JSONObject(),websiteResult=new JSONObject();long lastProbeDuration,lastProbeDurationAt;String lastProbeEntry="";
  final AtomicInteger stops=new AtomicInteger(),contacts=new AtomicInteger(),connections=new AtomicInteger(),decoyConnections=new AtomicInteger();final List<String> order=new CopyOnWriteArrayList<>();volatile int launches;volatile boolean mutated,sawMutated,startupSucceeds;
  static class ExitRouteReceipt{}static class ExitMismatch extends IOException{}static class ExitCheckUnavailable extends IOException{}static class RouteTransactionFailure extends IOException{}static class StartupRouteFailure extends IOException{}
  NetworkHealthPolicy.Admission connectionAdmission(){return admission;}boolean coreAlive(){return transport.alive;}void cancelMaintenance(){}void bindDiagnostics(){}void note(NetworkDiagnostics.Event event,NetworkDiagnostics.Reason reason,NetworkDiagnostics.Stage stage,long value){}
  boolean configurationMatches(){return false;}boolean verifiedRouteCurrent(){return false;}void recoverExistingRoute(){}void verifyExit()throws IOException{}String display(String value){return value;}boolean adoptTransport(){return false;}boolean retainedFailure(Exception error){return false;}boolean retainVerifiedRoute(Exception error){return false;}void report(String value){message=value;}boolean maintenanceCancelled(){return false;}void cleanupOwnedPid(){}
  void startNow()throws Exception{launches++;sawMutated=mutated;order.add("startNow");if(!startupSucceeds)throw new StartupRouteFailure();contacts.incrementAndGet();connections.incrementAndGet();ready=true;transport.alive=true;}
}
class Transport {final NativeNetwork network;volatile boolean alive;Transport(NativeNetwork network){this.network=network;}JSONObject call(String action,String value,NetworkDiagnostics.Reason reason){network.stops.incrementAndGet();network.order.add("stopNow");alive=false;return J.obj("alive",false);}}
class Dispatcher {final BlockingQueue<Runnable> queue=new LinkedBlockingQueue<>();void post(Runnable task){queue.add(task);}void postDelayed(Runnable task,long delay){queue.add(task);}void drain(){Runnable task;while((task=queue.poll())!=null)task.run();}}
class ChatSession {
  /* ACTUAL_SESSION_RETRY */
  final ReservationHost.Observed network;final Dispatcher handler=new Dispatcher();long recoveryToken=7;boolean offline,manualAttention,submitting,operation,recoveryScheduled,connecting;int recoveryAttempt,opens,callbacks;
  ChatSession(ReservationHost.Observed network){this.network=network;}
  void openConnection(boolean recover,boolean force){opens++;connecting=true;NativeNetwork.RecoveryCallback callback=outcome->{callbacks++;connecting=false;};network.observer.recovery(callback,recoveryAttempt,network.pending==null?null:network.pending.root);network.recoverOutcome(callback);}
}
class NetworkHealthPolicy {enum Admission{BLOCKED;boolean usable(){return false;}}}
class NetworkDiagnostics {enum Event{RECONNECT_ATTEMPT,FAILURE,STOP_REQUEST}enum Reason{UNKNOWN,REQUESTED,REPLACE,EXIT_MISMATCH,START_FAILED}enum Stage{RECOVER,STOP}}
class NetworkCatalog {static void put(JSONObject value,String key,Object item){try{value.put(key,item);}catch(JSONException error){throw new IllegalStateException(error);}}}
class NetworkSourcesRouteIntegrationActivity {
  interface Work<T>{T run()throws Exception;}
  final NativeNetwork network;final ChatSession session;String runNonce=ReservationHost.NONCE,expectedSource=ReservationHost.SOURCE;
  NetworkSourcesRouteIntegrationActivity(NativeNetwork network,ChatSession session){this.network=network;this.session=session;}void runOnUiThread(Runnable task){task.run();}
}
class SourceRouteTerminalObserver {
  final NetworkSourcesRouteIntegrationActivity test;volatile Scope active;
  SourceRouteTerminalObserver(NetworkSourcesRouteIntegrationActivity test){this.test=test;}
  /* ACTUAL_TERMINAL_MEMBERS */
}
