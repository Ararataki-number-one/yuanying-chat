package local.pocketchat;

import org.json.*;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import android.os.SystemClock;
import android.os.Looper;

/** Actual Activity ownership/negative-case members with explicit host IO adapters. */
public final class ActivityReservationHost {
  static final String SOURCE="ec196a4394a3172e7ed2558a00fc4f2b0a75e2de",NONCE="0123456789abcdef0123456789abcdef";
  static final JSONArray checks=new JSONArray(),cases=new JSONArray();
  static void check(String name,boolean pass)throws Exception{checks.put(J.obj("name",name,"pass",pass));if(!pass)throw new AssertionError(name);}
  interface Injection{void tick(NetworkSourcesRouteIntegrationActivity app)throws Exception;}
  static void await(CountDownLatch latch)throws Exception{if(!latch.await(3,TimeUnit.SECONDS))throw new IOException("Host barrier missing");}
  static Throwable run(NetworkSourcesRouteIntegrationActivity app,NetworkSourcesRouteIntegrationActivity.Work<Void> mutation,Injection injection)throws Exception{
    Future<?> future=app.runner.submit(()->{try{app.reject("invalid-entry-snapshot-sha",mutation);}catch(Throwable error){throw new CompletionException(error);}});
    long until=System.nanoTime()+TimeUnit.SECONDS.toNanos(5);
    while(!future.isDone()){
      app.uiQueue.drain();app.network.main.drain();injection.tick(app);
      if(System.nanoTime()>until)throw new IOException("Host fixture watchdog");Thread.sleep(1);
    }
    app.uiQueue.drain();app.network.main.drain();app.network.worker.submit(()->{}).get(3,TimeUnit.SECONDS);
    try{future.get();return null;}catch(ExecutionException error){return error.getCause();}
  }
  static JSONObject evidence(NetworkSourcesRouteIntegrationActivity app){return J.obj("reservationDiagnostics",app.reservationDiagnostics,"businessChecksExecuted",app.checks,"finishAdapterCalls",app.finishCalls,"fetchAdapterCalls",app.fetchCalls,"launches",app.network.launches,"callbacks",app.network.callbacks,"contacts",app.contacts(),"failure",String.valueOf(app.reservationFailure));}
  static void simple()throws Exception{
    try(NetworkSourcesRouteIntegrationActivity app=new NetworkSourcesRouteIntegrationActivity()){
      Throwable error=run(app,()->{app.network.order.add("mutation");return null;},a->{});
      check("Actual Activity reject completes with one real reserved body and explicit scoped callback",error==null&&app.finishCalls==1&&app.fetchCalls==1&&app.network.launches==1&&app.reservedStart.delegations==1&&app.reservedStart.callbackCount==1&&app.reservationFailure==null);
      check("Actual Activity preserves publish-stop-mutation order without fake session busy or retry cancellation",app.network.order.indexOf("publishOriginal")<app.network.order.indexOf("mutation")&&app.network.order.indexOf("mutation")<app.network.order.indexOf("startNow")&&!app.session.operation&&!app.session.submitting&&app.session.recoveryToken==7);
      check("Actual Activity uses one original75s reservation and original22s fetch budget",app.reservedStart.deadlineNs-app.reservedStart.beganAtNs==TimeUnit.SECONDS.toNanos(75)&&app.reservationDiagnostics.getJSONObject(0).getLong("deadlineAtNs")-app.reservationDiagnostics.getJSONObject(0).getLong("fetchBeganAtNs")==TimeUnit.SECONDS.toNanos(22));
      check("Actual scoped callback records original false outcome and matching callback identity",app.lastScope.restartCallback==app.reservedStart.callback&&app.lastScope.startupRoot==app.reservedStart.root&&!app.lastScope.restartTerminal.getBoolean("ok"));
      cases.put(J.obj("name","actual Activity successful negative", "evidence",evidence(app)));
    }
  }
  static void joined()throws Exception{
    CountDownLatch entered=new CountDownLatch(1),release=new CountDownLatch(1);AtomicBoolean injected=new AtomicBoolean();
    try(NetworkSourcesRouteIntegrationActivity app=new NetworkSourcesRouteIntegrationActivity()){
      Throwable error=run(app,()->{entered.countDown();await(release);return null;},a->{if(entered.getCount()==0&&injected.compareAndSet(false,true)){a.session.recoveryScheduled=true;a.session.runRecovery(7);release.countDown();}});
      check("Actual Activity keeps genuine default runRecovery mode1 join and both callbacks",error==null&&injected.get()&&app.session.opens==1&&app.session.callbacks==1&&app.reservedStart.callbackCount==1&&app.network.launches==1&&app.reservedStart.root.admissions.getJSONObject(0).getInt("mode")==1);
      check("Actual Activity joined retry retains original token and never manufactures busy",app.session.recoveryToken==7&&!app.session.operation&&!app.session.submitting&&app.reservationFailure==null);
      cases.put(J.obj("name","actual Activity natural mode1", "evidence",evidence(app)));
    }finally{release.countDown();}
  }
  static void prepFailure()throws Exception{
    try(NetworkSourcesRouteIntegrationActivity app=new NetworkSourcesRouteIntegrationActivity()){
      app.network.startupSucceeds=true;Throwable error=run(app,()->{throw new IOException("controlled private IO failure");},a->{});
      check("Actual Activity preparation failure still delegates original body and captures true callback",error!=null&&app.reservedStart.delegations==1&&app.reservedStart.callbackCount==1&&app.reservedStart.snapshot().getJSONObject("actualCallback").getBoolean("ok")&&app.terminalObserver.active.restartTerminal.getBoolean("ok"));
      check("Actual Activity cannot turn failed preparation and real controlled side effects into acceptance",app.reservationFailure!=null&&app.fetchCalls==0&&app.finishCalls==0&&app.network.contacts.get()==1&&app.reservedStart.snapshot().getJSONObject("actualContactsAfterOriginal").getInt("fixedTarget")==1);
      int launches=app.network.launches;Throwable next=run(app,()->null,a->{});check("Actual Activity permanently refuses next negative case after failure",next!=null&&app.network.launches==launches&&app.reservationDiagnostics.length()==1);
      cases.put(J.obj("name","actual Activity preparation exception", "evidence",evidence(app)));
    }
  }
  static void competing(int mode,boolean duringPrep)throws Exception{
    CountDownLatch entered=new CountDownLatch(1),release=new CountDownLatch(1);AtomicBoolean injected=new AtomicBoolean();AtomicInteger otherCallbacks=new AtomicInteger();
    try(NetworkSourcesRouteIntegrationActivity app=new NetworkSourcesRouteIntegrationActivity()){
      if(!duringPrep)app.network.startBlock=release;
      Throwable error=run(app,()->{if(duringPrep){entered.countDown();await(release);}return null;},a->{if((duringPrep?entered:a.network.startEntered).getCount()==0&&injected.compareAndSet(false,true)){if(mode==2)a.network.restart((ok,message)->otherCallbacks.incrementAndGet());else a.network.startOperation((ok,message)->otherCallbacks.incrementAndGet(),0);release.countDown();}});
      check("Actual Activity rejects "+mode+" admission "+(duringPrep?"during prep":"during body")+" without dropping original callbacks",error!=null&&injected.get()&&app.reservationFailure!=null&&app.fetchCalls==0&&app.finishCalls==0&&otherCallbacks.get()==1&&app.reservedStart.callbackCount==1&&!app.network.starting&&app.network.startWaiters.isEmpty());
      check("Actual Activity preserves queued-mode2 original delegation count for "+mode+"/"+duringPrep,app.network.launches==(mode==2?2:1)&&app.reservedStart.delegations==(mode==2?2:1));
      cases.put(J.obj("name","actual Activity competing "+mode+"/"+duringPrep, "evidence",evidence(app)));
    }finally{release.countDown();}
  }
  static void contacts()throws Exception{
    try(NetworkSourcesRouteIntegrationActivity app=new NetworkSourcesRouteIntegrationActivity()){
      Throwable error=run(app,()->{app.network.contacts.incrementAndGet();app.network.connections.incrementAndGet();return null;},a->{});
      check("Actual Activity's returned post-mutation contacts cannot rebase real admission contacts",error!=null&&app.reservationFailure!=null&&app.reservedStart.snapshot().getJSONObject("admissionContacts").getInt("fixedTarget")==0&&app.reservedStart.snapshot().getJSONObject("actualPreparationContacts").getInt("fixedTarget")==1&&app.fetchCalls==0);
      cases.put(J.obj("name","actual Activity contacts changed", "evidence",evidence(app)));
    }
  }
  static void lateCallback()throws Exception{
    try(NetworkSourcesRouteIntegrationActivity app=new NetworkSourcesRouteIntegrationActivity()){
      check("Actual Activity first scoped negative completes before stale callback control",run(app,()->null,a->{})==null);
      SourceRouteTerminalObserver.Scope old=app.lastScope,newer=new SourceRouteTerminalObserver.Scope("replacement",NONCE,app.contacts());newer.restartCallback=(ok,message)->{};app.terminalObserver.active=newer;
      app.reservedStart.callback.done(true,"late old callback");boolean rejected=false;try{app.terminalObserver.restartDone(old,old.restartCallback,true);}catch(Exception expected){rejected=true;}
      check("Actual Activity callback and actual observer reject old scope without modifying replacement",rejected&&app.reservedStart.failure!=null&&newer.restartTerminal==null&&app.terminalObserver.active==newer&&!old.restartTerminal.getBoolean("ok"));
      cases.put(J.obj("name","actual Activity late callback", "evidence",evidence(app)));
    }
  }
  public static void main(String[] args)throws Exception{
    Looper.getMainLooper();simple();joined();prepFailure();competing(2,true);competing(0,true);competing(0,false);contacts();lateCallback();
    JSONObject report=J.obj("status","host-controls-passed-android-candidate","passed",checks.length(),"total",checks.length(),"checks",checks,"cases",cases,"actualAndroidExecution",false,"actualNetworkExecution",false,"actualTerminalFreshIpcExecuted",false,"originalBusiness77Executed",false,"acceptedAsRepair",false,"scope","Complete selected actual Activity Gate/reject/worker hooks and scoped terminal callback plus actual native scheduling/session retry methods. Private preparation/transport/Gecko fetch/terminal finish/main/clock are explicit controlled host adapters, not Android qualification.");Files.writeString(Path.of(args[0]),report.toString(2));System.out.println("Activity reservation host: "+checks.length());
  }
}

class NativeNetwork {
  /* ACTUAL_NATIVE_MEMBERS */
  final ScheduledExecutorService worker=Executors.newSingleThreadScheduledExecutor();final Dispatcher main=new Dispatcher();final List<Callback> startWaiters=new ArrayList<>();
  volatile boolean starting,ready,recoveryBlocked;boolean restartQueued;String message="controlled source rejection",currentEntry="";long reconnectAttempts,routeSerial,nextExitCheckAt,healthObservedAt;int exitCheckFailures,failures,healthTargetCode;String healthStatus="unknown";NetworkHealthPolicy.Admission admission=NetworkHealthPolicy.Admission.BLOCKED;
  ExitRouteReceipt verifiedRoute;java.lang.Process process;final AtomicReference<NetworkDiagnostics.Reason> coreStopReason=new AtomicReference<>();final Transport transport=new Transport(this);
  Object currentProbe;JSONObject latencyReading=new JSONObject(),websiteResult=new JSONObject();long lastProbeDuration,lastProbeDurationAt;String lastProbeEntry="";
  final AtomicInteger stops=new AtomicInteger(),contacts=new AtomicInteger(),connections=new AtomicInteger();final List<String> order=new CopyOnWriteArrayList<>();volatile int launches,callbacks;volatile boolean startupSucceeds;
  static class ExitRouteReceipt{}static class ExitMismatch extends IOException{}static class ExitCheckUnavailable extends IOException{}static class RouteTransactionFailure extends IOException{}static class StartupRouteFailure extends IOException{}
  NetworkHealthPolicy.Admission connectionAdmission(){return admission;}boolean coreAlive(){return transport.alive;}void cancelMaintenance(){}void bindDiagnostics(){}void note(NetworkDiagnostics.Event event,NetworkDiagnostics.Reason reason,NetworkDiagnostics.Stage stage,long value){}
  boolean configurationMatches(){return false;}boolean verifiedRouteCurrent(){return false;}void recoverExistingRoute(){}void verifyExit()throws IOException{}String display(String value){return value;}boolean adoptTransport(){return false;}boolean retainedFailure(Exception error){return false;}boolean retainVerifiedRoute(Exception error){return false;}void report(String value){message=value;}boolean maintenanceCancelled(){return false;}void cleanupOwnedPid(){}
  JSONObject sourceMeta(String name){return new JSONObject();}static boolean sourceCacheMatches(JSONObject a,String b,JSONObject c,byte[] d){return false;}
  void startNow()throws Exception{launches++;order.add("startNow");if(!startupSucceeds)throw new StartupRouteFailure();contacts.incrementAndGet();connections.incrementAndGet();ready=true;transport.alive=true;}
}
class ActualNetwork extends NativeNetwork {
  final NetworkSourcesRouteIntegrationActivity test;final SourceRouteStartObservation startObservation=new SourceRouteStartObservation();volatile CountDownLatch startBlock;final CountDownLatch startEntered=new CountDownLatch(1);
  ActualNetwork(NetworkSourcesRouteIntegrationActivity test){this.test=test;}
  /* ACTUAL_ACTIVITY_WORKER_HOOKS */
  @Override void startNow()throws Exception{startEntered.countDown();if(startBlock!=null)ActivityReservationHost.await(startBlock);super.startNow();}
  @Override void recoverOutcome(RecoveryCallback callback){SourceRouteStartObservation.Root root=test.terminalObserver.active==null?null:test.terminalObserver.active.startupRoot;startObservation.recovery(callback,++test.recoveryRequestSerial,root);super.recoverOutcome(callback);}
}
class Transport {final NativeNetwork network;volatile boolean alive;JSONObject state=J.obj("alive",false);Transport(NativeNetwork network){this.network=network;}JSONObject call(String action,String value,NetworkDiagnostics.Reason reason){network.stops.incrementAndGet();network.order.add("stopNow");alive=false;state=J.obj("alive",false);return state;}}
class Dispatcher {final BlockingQueue<Runnable> queue=new LinkedBlockingQueue<>();void post(Runnable task){queue.add(task);}void postDelayed(Runnable task,long delay){queue.add(task);}void drain(){Runnable task;while((task=queue.poll())!=null)task.run();}}
class ChatSession {
  /* ACTUAL_SESSION_RETRY */
  final NativeNetwork network;final Dispatcher handler=new Dispatcher();long recoveryToken=7;boolean offline,manualAttention,submitting,operation,recoveryScheduled,connecting;int recoveryAttempt,opens,callbacks;
  ChatSession(NativeNetwork network){this.network=network;}void openConnection(boolean recover,boolean force){opens++;connecting=true;network.recoverOutcome(outcome->{callbacks++;connecting=false;});}
}
class NetworkSourcesRouteIntegrationActivity implements AutoCloseable {
  interface Work<T>{T run()throws Exception;}
  final JSONArray checks=new JSONArray(),negatives=new JSONArray(),reservationDiagnostics=new JSONArray();final ExecutorService runner=Executors.newSingleThreadExecutor();final Dispatcher uiQueue=new Dispatcher();
  final ActualNetwork network=new ActualNetwork(this);final ChatSession session=new ChatSession(network);final SourceRouteTerminalObserver terminalObserver=new SourceRouteTerminalObserver(this);final SecretStore vault=new SecretStore();
  String runNonce=ActivityReservationHost.NONCE,expectedSource=ActivityReservationHost.SOURCE;volatile SourceRouteStartReservation reservedStart;volatile Throwable reservationFailure;int recoveryRequestSerial,finishCalls,fetchCalls;SourceRouteTerminalObserver.Scope lastScope;
  void runOnUiThread(Runnable task){if(Looper.myLooper()==Looper.getMainLooper())task.run();else uiQueue.post(task);}void event(String kind,JSONObject value){}
  void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));if(!pass)throw new AssertionError(name);}static long now(){return SystemClock.elapsedRealtimeNanos();}
  void publishOriginal(){network.order.add("publishOriginal");}
  JSONObject contacts(){return J.obj("fixedTarget",network.contacts.get(),"decoyTarget",0,"ip",0,"plainProbe",0,"fixedAllConnected",network.connections.get(),"decoyAllConnected",0);}
  JSONObject fetch(String name,boolean expected,SourceRouteTerminalObserver.Scope scope){fetchCalls++;lastScope=scope;terminalObserver.beginFetch(scope);return J.obj("ok",false);}
  /* ACTUAL_ACTIVITY_GATE_AND_REJECT */
  public void close(){if(network.startBlock!=null)network.startBlock.countDown();network.worker.shutdownNow();runner.shutdownNow();}
}
class SourceRouteTerminalObserver {
  final NetworkSourcesRouteIntegrationActivity test;volatile Scope active;SourceRouteTerminalObserver(NetworkSourcesRouteIntegrationActivity test){this.test=test;}
  /* ACTUAL_TERMINAL_MEMBERS */
  JSONObject cache(){return copy(test.network.transport.state);}
  void finish(Scope scope,JSONObject negative)throws Exception{require(active==scope,"host finish received another scope");test.finishCalls++;test.lastScope=scope;NetworkCatalog.put(scope.evidence,"status","host-finish-adapter");active=null;}
}
class SecretStore {JSONObject settings(){return new JSONObject();}byte[] get(String name){return new byte[0];}}
class NetworkHealthPolicy {enum Admission{BLOCKED;boolean usable(){return false;}}}
class NetworkDiagnostics {enum Event{RECONNECT_ATTEMPT,FAILURE,STOP_REQUEST}enum Reason{UNKNOWN,REQUESTED,REPLACE,EXIT_MISMATCH,START_FAILED}enum Stage{RECOVER,STOP}}
class NetworkCatalog {static final String ENTRY="entry",EXIT="exit";static void put(JSONObject value,String key,Object item){try{value.put(key,item);}catch(JSONException error){throw new IllegalStateException(error);}}}
