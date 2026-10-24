package local.pocketchat;

import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicReference;
import org.json.*;

/** Runs the complete fixture observer; UI/IPC are explicit controllable host adapters. */
public final class TerminalObserverTest {
  static final String OPEN="11111111-1111-1111-1111-111111111111",CLOSED="22222222-2222-2222-2222-222222222222",HASH=String.join("",Collections.nCopies(64,"a"));
  static int total;static JSONArray results=new JSONArray();
  interface Case{void run()throws Exception;}
  static void check(String name,Case body)throws Exception{body.run();total++;results.put(J.obj("name",name,"pass",true));}
  static void require(boolean ok){if(!ok)throw new AssertionError();}
  static JSONObject snapshot(boolean alive){return J.obj("slot",0,"state",alive?"starting":"closed","alive",alive,"generation",alive?OPEN:CLOSED,"pid",alive?41:0,"servicePid",30,"configuration",HASH);}
  static final class Fixture implements AutoCloseable {
    final NetworkSourcesRouteIntegrationActivity app=new NetworkSourcesRouteIntegrationActivity();final SourceRouteTerminalObserver observer=new SourceRouteTerminalObserver(app);final SourceRouteTerminalObserver.Scope scope;final JSONObject negative=J.obj("coreAliveAfter",false,"readyAfter",false);
    Fixture(String name)throws Exception{app.network.transport.state=snapshot(false);app.network.transport.answer=snapshot(false);scope=observer.begin(name,app.contacts());observer.restartDone(false);observer.beginFetch(scope);}
    void stopped(){app.network.transport.state=snapshot(true);NativeNetwork.ExitRouteReceipt owned=new NativeNetwork.ExitRouteReceipt();JSONObject stop=observer.stopBefore(owned,NetworkDiagnostics.Reason.START_FAILED);app.network.transport.state=snapshot(false);observer.stopAfter(stop);observer.restartDone(false);}
    void finish()throws Exception{negative.put("postFetchObservedAtNs",System.nanoTime());negative.put("coreAliveAfter",app.network.coreAlive());negative.put("readyAfter",app.network.ready);negative.put("message",app.network.message);observer.finish(scope,negative);}
    void rejected()throws Exception{boolean failed=false;try{finish();}catch(Exception expected){failed=true;}require(failed&&scope.evidence.getString("status").equals("failed"));}
    public void close(){observer.close();}
  }
  public static void main(String[] args)throws Exception{
    check("No recovery uses one fresh terminal IPC without waiting for a future retry",()->{try(Fixture f=new Fixture("invalid-entry-snapshot-sha")){f.finish();require(f.app.network.transport.reads==1&&!f.negative.getBoolean("coreAliveAfter")&&f.scope.evidence.getJSONArray("recoveries").length()==0);}});
    check("Owned process closure records different live and closed generations",()->{try(Fixture f=new Fixture("same-name-changed-entry")){f.stopped();f.finish();require(f.app.network.transport.reads==1&&f.scope.evidence.getJSONArray("stopObservations").length()==1);}});
    check("Real callback completion preserves the earlier alive cache and waits only for that request",()->{
      try(Fixture f=new Fixture("same-name-changed-entry")){
        f.stopped();f.app.recoveryRequestSerial=1;f.app.session.recoveryToken=1;f.app.session.connectionEpoch=1;f.app.session.connecting=true;f.app.network.starting=true;f.app.network.transport.state=snapshot(true);
        SourceRouteTerminalObserver.Recovery request=f.observer.recoveryStarted(1);AtomicReference<Throwable> error=new AtomicReference<>();
        Thread completion=new Thread(()->{try{long until=System.nanoTime()+TimeUnit.SECONDS.toNanos(3);for(;;){synchronized(f.scope){if(f.scope.evidence.has("postFetchCache"))break;}if(System.nanoTime()>until)throw new AssertionError("post-fetch cut absent");Thread.onSpinWait();}JSONObject stop=f.observer.stopBefore(new NativeNetwork.ExitRouteReceipt(),NetworkDiagnostics.Reason.START_FAILED);f.app.network.transport.state=snapshot(false);f.observer.stopAfter(stop);f.app.session.connecting=false;f.app.network.starting=false;f.app.session.recoveryToken=2;f.observer.recoveryFinished(request,new NativeNetwork.RecoveryOutcome());}catch(Throwable failure){error.set(failure);request.done.completeExceptionally(failure);}});
        completion.start();f.finish();completion.join(3000);require(!completion.isAlive()&&error.get()==null&&f.scope.evidence.getJSONObject("postFetchCache").getBoolean("coreAlive")&&f.scope.evidence.getJSONArray("recoveries").length()==1&&f.app.network.transport.reads==1&&!f.negative.getBoolean("coreAliveAfter"));
      }
    });
    check("A fresh alive process is rejected without another sample",()->{try(Fixture f=new Fixture("invalid-entry-snapshot-sha")){f.app.network.transport.answer=snapshot(true);f.rejected();require(f.app.network.transport.reads==1);}});
    check("Missing fresh alive is unknown and rejected",()->{try(Fixture f=new Fixture("invalid-entry-snapshot-sha")){f.app.network.transport.answer.remove("alive");f.rejected();}});
    check("Boolean PID cannot masquerade as a process number",()->{try(Fixture f=new Fixture("invalid-entry-snapshot-sha")){f.app.network.transport.answer.put("pid",false);f.rejected();}});
    check("A different closed generation is rejected",()->{try(Fixture f=new Fixture("invalid-entry-snapshot-sha")){f.app.network.transport.answer.put("generation",OPEN);f.rejected();}});
    check("A replacement service PID is rejected",()->{try(Fixture f=new Fixture("invalid-entry-snapshot-sha")){f.app.network.transport.answer.put("servicePid",31);f.rejected();}});
    check("A nonzero closed PID is rejected",()->{try(Fixture f=new Fixture("invalid-entry-snapshot-sha")){f.app.network.transport.answer.put("pid",41);f.rejected();}});
    check("A new recovery during the read fails instead of resampling",()->{try(Fixture f=new Fixture("invalid-entry-snapshot-sha")){f.app.network.transport.during=()->{f.app.recoveryRequestSerial++;f.observer.recoveryStarted(f.app.recoveryRequestSerial);};f.rejected();require(f.app.network.transport.reads==1);}});
    check("A new environment generation during the read is rejected",()->{try(Fixture f=new Fixture("invalid-entry-snapshot-sha")){f.app.network.transport.during=()->f.app.session.environmentGeneration++;f.rejected();}});
    check("A target reached during terminal observation is rejected",()->{try(Fixture f=new Fixture("invalid-entry-snapshot-sha")){f.app.network.transport.during=()->f.app.targets++;f.rejected();}});
    check("Owned rejection cannot pass without ownership evidence",()->{try(Fixture f=new Fixture("same-name-changed-entry")){f.rejected();}});
    check("A different live PID cannot be attributed to the owned process",()->{try(Fixture f=new Fixture("same-name-changed-entry")){f.stopped();f.scope.stops.getJSONObject(0).getJSONObject("beforeCache").put("pid",42);f.rejected();}});
    check("An expired original fetch deadline performs no IPC",()->{try(Fixture f=new Fixture("invalid-entry-snapshot-sha")){f.scope.deadlineNs=System.nanoTime()-1;f.rejected();require(f.app.network.transport.reads==0);}});
    check("A late callback cannot close another case",()->{try(Fixture f=new Fixture("invalid-entry-snapshot-sha")){SourceRouteTerminalObserver.Recovery request=f.observer.recoveryStarted(1);f.observer.active=null;f.observer.recoveryFinished(request,new NativeNetwork.RecoveryOutcome());require(request.done.isCompletedExceptionally());f.observer.active=f.scope;f.rejected();}});
    check("Terminal IPC executes off the caller thread",()->{try(Fixture f=new Fixture("invalid-entry-snapshot-sha")){Thread caller=Thread.currentThread();f.app.network.transport.during=()->require(Thread.currentThread()!=caller);f.finish();}});
    check("An IPC timeout interrupts only the read adapter and never retries",()->{try(Fixture f=new Fixture("invalid-entry-snapshot-sha")){CountDownLatch interrupted=new CountDownLatch(1);f.scope.deadlineNs=System.nanoTime()+TimeUnit.MILLISECONDS.toNanos(80);f.app.network.transport.during=()->{try{new CountDownLatch(1).await();}catch(InterruptedException expected){interrupted.countDown();Thread.currentThread().interrupt();}};f.rejected();require(f.app.network.transport.reads==1&&interrupted.await(1,TimeUnit.SECONDS));}});
    check("An IPC exception remains unknown and cannot become closed",()->{try(Fixture f=new Fixture("invalid-entry-snapshot-sha")){f.app.network.transport.during=()->{throw new IllegalStateException("controlled IPC failure");};f.rejected();require(f.app.network.transport.reads==1);}});
    check("A successful recovery is not rejected-startup terminal evidence",()->{try(Fixture f=new Fixture("invalid-entry-snapshot-sha")){f.app.recoveryRequestSerial=1;SourceRouteTerminalObserver.Recovery request=f.observer.recoveryStarted(1);NativeNetwork.RecoveryOutcome outcome=new NativeNetwork.RecoveryOutcome();outcome.state=NativeNetwork.RecoveryState.RECOVERED;f.observer.recoveryFinished(request,outcome);f.rejected();require(f.app.network.transport.reads==0);}});
    check("A pushed replacement service cache after the correlated reply is rejected",()->{try(Fixture f=new Fixture("invalid-entry-snapshot-sha")){f.app.network.transport.during=()->f.app.network.transport.state=J.obj("slot",0,"state","closed","alive",false,"generation",OPEN,"pid",0,"servicePid",31,"configuration",HASH);f.rejected();require(f.app.network.transport.reads==1);}});
    check("An immediate ready result cannot be overwritten by a later blocked fence",()->{try(Fixture f=new Fixture("invalid-entry-snapshot-sha")){f.app.network.ready=true;f.app.beforeUi=()->f.app.network.ready=false;f.rejected();require(f.scope.evidence.getJSONObject("postFetchCache").getBoolean("ready")&&f.app.network.transport.reads==0);}});
    check("An immediate live cache without an overlapping recovery remains failure",()->{try(Fixture f=new Fixture("invalid-entry-snapshot-sha")){f.app.network.transport.state=snapshot(true);f.app.beforeUi=()->f.app.network.transport.state=snapshot(false);f.rejected();require(f.scope.evidence.getJSONObject("postFetchCache").getBoolean("coreAlive")&&f.app.network.transport.reads==0);}});
    check("A live cache at the UI selection cut needs a recovery owner",()->{try(Fixture f=new Fixture("invalid-entry-snapshot-sha")){f.app.beforeUi=()->f.app.network.transport.state=snapshot(true);f.app.network.transport.during=()->f.app.network.transport.state=snapshot(false);f.rejected();require(!f.scope.evidence.getJSONObject("postFetchCache").getBoolean("coreAlive")&&f.scope.evidence.getJSONObject("postFetchCache").getJSONObject("cache").getBoolean("alive")&&f.app.network.transport.reads==0);}});
    check("A target reached while the final UI callback is queued remains failure",()->{try(Fixture f=new Fixture("invalid-entry-snapshot-sha")){f.app.beforeUi=new Runnable(){int count;public void run(){if(++count<3)f.app.beforeUi=this;else f.app.targets++;}};f.rejected();require(f.app.network.transport.reads==1&&f.scope.evidence.getJSONObject("contactsAfter").getInt("fixedTarget")==1);}});
    check("A case change during read cannot be attributed to the old case",()->{try(Fixture f=new Fixture("invalid-entry-snapshot-sha")){f.app.network.transport.during=()->f.observer.active=null;f.rejected();}});
    java.nio.file.Files.writeString(java.nio.file.Path.of(args[0]),J.obj("status","passed","actualAndroidExecution",false,"actualFreshServiceIpc",false,"actualFixtureObserverExecution",true,"scope","Complete fixture observer with explicit host UI/IPC adapters; not Android or process-exit acceptance","total",total,"checks",results).toString(2)+"\n");
    System.out.println("terminal observer host: "+total+" passed");
  }
}

class NetworkSourcesRouteIntegrationActivity {
  interface Work<T>{T run()throws Exception;}
  final NativeNetwork network=new NativeNetwork();final Session session=new Session();final View view=new View();
  final String expectedSource=String.join("",Collections.nCopies(40,"a")),runNonce=String.join("",Collections.nCopies(32,"b"));int recoveryRequestSerial,targets;Runnable beforeUi;
  <T>T ui(Work<T> work)throws Exception{return work.run();}void runOnUiThread(Runnable work){Runnable before=beforeUi;beforeUi=null;if(before!=null)before.run();work.run();}
  JSONObject contacts(){return J.obj("fixedTarget",targets,"decoyTarget",0,"ip",0,"plainProbe",0,"fixedAllConnected",0,"decoyAllConnected",0);}
}
class Session {String environmentId="33333333-3333-3333-3333-333333333333";long environmentGeneration,connectionEpoch,recoveryToken;boolean connecting;}
class View {void evaluateJavascript(String script,java.util.function.Consumer<String> done){done.accept("{}");}}
class Profiles {static int slot(Object context){return 0;}}
class NetworkCatalog {static void put(JSONObject o,String key,Object value){try{o.put(key,value);}catch(JSONException e){throw new RuntimeException(e);}}}
class NetworkDiagnostics {enum Reason{START_FAILED}}
class NativeNetwork {
  final SourceRouteStartObservation startObservation=new SourceRouteStartObservation();
  final List<Callback> startWaiters=new ArrayList<>();boolean restartQueued;
  interface Callback{void done(boolean ok,String message);}
  interface RecoveryCallback{void done(RecoveryOutcome outcome);}
  static class RecoveryAdapter implements Callback {final RecoveryCallback callback;RecoveryAdapter(RecoveryCallback callback){this.callback=callback;}public void done(boolean ok,String message){callback.done(new RecoveryOutcome());}}
  NetworkTransportClient transport=new NetworkTransportClient();boolean starting,ready;Object verifiedRoute;long routeSerial;String message="fixture";
  boolean coreAlive(){return transport.state.optBoolean("alive");}
  enum RecoveryState{FAILED,RECOVERED}
  static class RecoveryOutcome {RecoveryState state=RecoveryState.FAILED;Object receipt;}
  static class ExitRouteReceipt {int pid=41,servicePid=30;String generation=TerminalObserverTest.OPEN,configuration=TerminalObserverTest.HASH;}
}
class NetworkTransportClient {
  volatile JSONObject state,answer;int reads;Runnable during;
  JSONObject call(String action,String config){TerminalObserverTest.require(action.equals("snapshot")&&config.isEmpty());reads++;if(during!=null)during.run();return J.parse(answer.toString());}
}
