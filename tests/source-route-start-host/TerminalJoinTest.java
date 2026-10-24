package local.pocketchat;

import org.json.*;
import java.io.*;
import java.nio.file.*;
import java.lang.reflect.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

public final class TerminalJoinTest {
  static final String HASH="a".repeat(64),SOURCE="5ad586c6b99a8d14454c9589274646feea3c20cf",NONCE="0123456789abcdef0123456789abcdef";
  static final JSONArray checks=new JSONArray(),cases=new JSONArray();
  static void require(boolean pass){if(!pass)throw new AssertionError();}
  static void check(String name,boolean pass)throws Exception{checks.put(J.obj("name",name,"pass",pass));require(pass);}
  static void await(CountDownLatch latch)throws Exception{if(!latch.await(3,TimeUnit.SECONDS))throw new AssertionError("Controlled worker barrier missing");}
  static String generation(boolean alive,int index){return String.format(alive?"10000000-0000-4000-8000-%012d":"20000000-0000-4000-8000-%012d",index);}
  static JSONObject snapshot(boolean alive,int index){return J.obj("slot",0,"state",alive?"running":"closed","alive",alive,"generation",generation(alive,index),"pid",alive?900+index:0,"servicePid",900,"configuration",HASH);}
  static final class Observed extends NativeNetwork {
    Fixture fixture;final CountDownLatch[] entered={new CountDownLatch(1),new CountDownLatch(1)},release={new CountDownLatch(1),new CountDownLatch(1)};
    final CountDownLatch finallyEntered=new CountDownLatch(1),finallyRelease=new CountDownLatch(1);boolean holdFinally;SourceRouteStartObservation.Root root;int rootCallbacks,recoveryCallbacks,queuedCallbacks;
    @Override synchronized void startOperation(Callback callback,int mode){SourceRouteStartObservation.Registration observed=startObservation.registrationBefore(this,callback,mode);try{super.startOperation(callback,mode);}finally{startObservation.registrationAfter(this,observed);}}
    @Override void runStartOperation(int mode){startObservation.workerBefore(this,mode);try{super.runStartOperation(mode);}finally{if(holdFinally){finallyEntered.countDown();try{await(finallyRelease);}catch(Exception error){throw new RuntimeException(error);}}startObservation.workerAfter(this,mode);}}
    @Override void startNow()throws Exception{transport.state=snapshot(true,launches+1);super.startNow();}
    @Override void stopOwnedCore(ExitRouteReceipt owned,NetworkDiagnostics.Reason reason){JSONObject row=fixture.observer.stopBefore(owned,reason);startObservation.stopBefore(this,row);try{super.stopOwnedCore(owned,reason);}finally{fixture.observer.stopAfter(row);startObservation.stopAfter(this,row);}}
    @Override void stopTransport(int index)throws Exception{entered[index].countDown();await(release[index]);transport.state=snapshot(false,index+1);}
    void begin(String mismatch)throws Exception{
      final Callback[] operation=new Callback[1];Callback callback=operation[0]=(ok,message)->{rootCallbacks++;try{
        try{fixture.observer.getClass().getDeclaredMethod("restartDone",SourceRouteTerminalObserver.Scope.class,Callback.class,boolean.class).invoke(fixture.observer,fixture.scope,operation[0],ok);}
        catch(NoSuchMethodException legacy){fixture.observer.getClass().getDeclaredMethod("restartDone",boolean.class).invoke(fixture.observer,ok);}
        fixture.rootDone.complete(ok);
      }catch(Throwable failure){fixture.rootDone.completeExceptionally(failure);}};
      try{Field field=SourceRouteTerminalObserver.Scope.class.getDeclaredField("restartCallback");field.setAccessible(true);field.set(fixture.scope,callback);}catch(NoSuchFieldException beforeObserver){}
      root=startObservation.root(callback,mismatch.equals("case")?"99999999-9999-4999-8999-999999999999":fixture.scope.id,mismatch.equals("source")?"b".repeat(40):SOURCE,mismatch.equals("nonce")?"f".repeat(32):NONCE);
      try{Field field=SourceRouteTerminalObserver.Scope.class.getDeclaredField("startupRoot");field.setAccessible(true);field.set(fixture.scope,root);}catch(NoSuchFieldException beforeObserver){}
      restart(callback);
    }
    void join()throws Exception{fixture.app.ui(()->{fixture.app.recoveryRequestSerial=1;fixture.app.session.recoveryToken=1;fixture.app.session.connectionEpoch=1;fixture.app.session.connecting=true;SourceRouteTerminalObserver.Recovery observed=fixture.observer.recoveryStarted(1);RecoveryCallback callback=outcome->{recoveryCallbacks++;fixture.app.session.connecting=false;fixture.app.session.recoveryToken=2;fixture.observer.recoveryFinished(observed,outcome);fixture.recoveryDone.complete(outcome);};startObservation.recovery(callback,1,root);recoverOutcome(callback);return null;});}
  }
  static final class Fixture implements AutoCloseable {
    final Observed network=new Observed();final NetworkSourcesRouteIntegrationActivity app=new NetworkSourcesRouteIntegrationActivity(network);final SourceRouteTerminalObserver observer=new SourceRouteTerminalObserver(app);final SourceRouteTerminalObserver.Scope scope;
    final CompletableFuture<Boolean> rootDone=new CompletableFuture<>();final CompletableFuture<NativeNetwork.RecoveryOutcome> recoveryDone=new CompletableFuture<>();
    final JSONObject negative=new JSONObject();final ExecutorService finisher=Executors.newSingleThreadExecutor();
    Fixture()throws Exception{network.fixture=this;network.transport.state=snapshot(false,0);scope=observer.begin("same-name-changed-entry",app.contacts());}
    void callbacks()throws Exception{require(!rootDone.get(3,TimeUnit.SECONDS));require(recoveryDone.get(3,TimeUnit.SECONDS).state==NativeNetwork.RecoveryState.FAILED);}
    void prepareFetch()throws Exception{observer.beginFetch(scope);negative.put("postFetchObservedAtNs",System.nanoTime());negative.put("coreAliveAfter",network.coreAlive());negative.put("readyAfter",network.ready);negative.put("message",network.message);}
    void finish()throws Exception{observer.finish(scope,negative);}
    void release()throws Exception{network.release[0].countDown();callbacks();prepareFetch();}
    boolean rejected()throws Exception{boolean rejected=false;try{finish();}catch(Exception expected){rejected=true;}require(rejected&&scope.evidence.getString("status").equals("failed"));return true;}
    JSONObject report(String name){return J.obj("name",name,"negative",SourceRouteStartObservation.copy(negative),"sourceObservation",network.startObservation.snapshot(network.root),"freshReads",network.transport.reads.get(),"launches",network.launches,"rootCallbacks",network.rootCallbacks,"recoveryCallbacks",network.recoveryCallbacks);}
    public void close(){network.finallyRelease.countDown();for(CountDownLatch release:network.release)release.countDown();try{network.worker.submit(()->{}).get(3,TimeUnit.SECONDS);}catch(Exception ignored){}observer.close();network.worker.shutdownNow();app.close();finisher.shutdownNow();}
  }
  static void waitForWorkerObservation(Thread thread)throws Exception{long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(3);while(System.nanoTime()<deadline){boolean observer=false,future=false;for(StackTraceElement frame:thread.getStackTrace()){observer|=frame.getClassName().equals("local.pocketchat.SourceRouteTerminalObserver")&&frame.getMethodName().equals("awaitJoinedWorker");future|=frame.getClassName().equals("java.util.concurrent.CompletableFuture")&&(frame.getMethodName().equals("get")||frame.getMethodName().equals("timedGet"));}if(observer&&future)return;Thread.onSpinWait();}throw new AssertionError("Actual observer did not await worker completion");}
  static void valid(boolean old)throws Exception{
    try(Fixture f=new Fixture()){
      f.network.holdFinally=true;f.network.begin("");await(f.network.entered[0]);f.network.join();f.release();
      if(old){await(f.network.finallyEntered);boolean rejected=f.rejected();JSONObject record=f.report("legacy-original-observer");cases.put(record);check("Original observer rejects the same actual joined restart before the fixture fix",rejected&&f.scope.evidence.getString("error").contains("stop observation crossed a recovery")&&f.network.transport.reads.get()==1&&f.network.launches==1);return;}
      await(f.network.finallyEntered);AtomicReference<Thread> thread=new AtomicReference<>();Future<?> result=f.finisher.submit(()->{thread.set(Thread.currentThread());try{f.finish();}catch(Exception failure){throw new RuntimeException(failure);}});
      while(thread.get()==null)Thread.onSpinWait();waitForWorkerObservation(thread.get());
      check("Complete observer waits for actual workerAfter after both original callbacks",!result.isDone()&&!f.network.startObservation.workerCompletion(f.network.root).isDone()&&f.network.transport.reads.get()==0&&f.network.rootCallbacks==1&&f.network.recoveryCallbacks==1);
      f.network.finallyRelease.countDown();result.get(3,TimeUnit.SECONDS);JSONObject stop=f.scope.evidence.getJSONArray("stopObservations").getJSONObject(0),wait=f.scope.evidence.getJSONObject("startObservationWait");
      check("Complete observer accepts exact joined restart with one fresh read and unchanged raw serials",f.scope.evidence.getString("status").equals("passed")&&f.network.transport.reads.get()==1&&stop.getInt("recoveryRequestSerial")==0&&stop.getInt("afterRequestSerial")==1&&stop.getJSONObject("joinedRecovery").getInt("request")==1&&!f.negative.getBoolean("coreAliveAfter")&&!f.negative.getBoolean("readyAfter")&&f.app.targets==0);
      check("Worker completion stays inside the original fetch budget and precedes the sole fresh read",wait.getLong("requestedAtNs")<=wait.getLong("completedAtNs")&&wait.getLong("completedAtNs")<=f.scope.evidence.getJSONObject("freshRead").getLong("requestedAtNs")&&f.scope.evidence.getLong("completedAtNs")<=f.scope.deadlineNs);
      cases.put(f.report("current-complete-observer-joined"));
    }
  }
  static void mismatches()throws Exception{for(String mismatch:new String[]{"source","nonce","case"})try(Fixture f=new Fixture()){
    f.network.begin(mismatch);await(f.network.entered[0]);f.network.join();f.release();f.network.worker.submit(()->{}).get(3,TimeUnit.SECONDS);f.rejected();
    check("Complete observer rejects a joined restart with wrong "+mismatch,f.scope.evidence.getString("status").equals("failed")&&f.network.rootCallbacks==1&&f.network.recoveryCallbacks==1&&f.app.targets==0&&f.network.transport.reads.get()<=1);cases.put(f.report("wrong-"+mismatch));
  }}
  static void deadline()throws Exception{try(Fixture f=new Fixture()){
    f.network.holdFinally=true;f.network.begin("");await(f.network.entered[0]);f.network.join();f.release();await(f.network.finallyEntered);f.scope.deadlineNs=System.nanoTime()+TimeUnit.MILLISECONDS.toNanos(80);f.rejected();
    check("Original deadline rejects unfinished worker observation without fresh IPC or cancellation",f.network.transport.reads.get()==0&&!f.network.startObservation.workerCompletion(f.network.root).isDone()&&f.network.launches==1&&f.network.rootCallbacks==1&&f.network.recoveryCallbacks==1);cases.put(f.report("original-deadline"));
  }}
  static void queued()throws Exception{try(Fixture f=new Fixture()){
    f.network.begin("");await(f.network.entered[0]);f.network.restart((ok,message)->f.network.queuedCallbacks++);f.network.release[0].countDown();await(f.network.entered[1]);f.network.join();f.network.release[1].countDown();f.callbacks();f.prepareFetch();f.network.worker.submit(()->{}).get(3,TimeUnit.SECONDS);f.rejected();
    check("Complete observer rejects real queued-worker ABA despite retained root waiter and closed core",f.network.startObservation.snapshot(f.network.root).getJSONArray("workerInvocations").length()==2&&f.network.transport.reads.get()==0&&f.network.launches==2&&f.network.rootCallbacks==1&&f.network.recoveryCallbacks==1&&f.network.queuedCallbacks==1&&!f.network.coreAlive());cases.put(f.report("queued-worker-aba"));
  }}
  public static void main(String[] args)throws Exception{boolean old=args.length>1&&args[1].equals("before");JSONObject report=J.obj("status","failed","actualAndroidExecution",false,"syntheticControlledHost",true,"actualFixtureObserverExecution",true,"actualSourceStartMethodsExecution",true,"cases",cases,"checks",checks);try{valid(old);if(!old){mismatches();deadline();queued();}report.put("status",old?"baseline-rejected":"passed");}finally{report.put("total",checks.length());Files.writeString(Path.of(args[0]),report.toString(2));}System.out.println("complete joined observer: "+checks.length());}
}
class NetworkSourcesRouteIntegrationActivity {
  interface Work<T>{T run()throws Exception;}
  final NativeNetwork network;final Session session=new Session();final View view=new View();final String expectedSource=TerminalJoinTest.SOURCE,runNonce=TerminalJoinTest.NONCE;volatile int recoveryRequestSerial,targets;final ExecutorService mainThread=Executors.newSingleThreadExecutor();
  NetworkSourcesRouteIntegrationActivity(NativeNetwork network){this.network=network;mainThread.execute(()->{try{while(!Thread.currentThread().isInterrupted())network.main.queue.take().run();}catch(InterruptedException finished){Thread.currentThread().interrupt();}});}
  void runOnUiThread(Runnable action){network.main.post(action);}
  <T>T ui(Work<T> action)throws Exception{CompletableFuture<T> result=new CompletableFuture<>();runOnUiThread(()->{try{result.complete(action.run());}catch(Throwable failure){result.completeExceptionally(failure);}});return result.get(3,TimeUnit.SECONDS);}
  JSONObject contacts(){return J.obj("fixedTarget",targets,"decoyTarget",0,"ip",0,"plainProbe",0,"fixedAllConnected",0,"decoyAllConnected",0);}
  void close(){mainThread.shutdownNow();}
}
class Session {String environmentId="33333333-3333-4333-8333-333333333333";long environmentGeneration,connectionEpoch,recoveryToken;boolean connecting;}
class View {void evaluateJavascript(String script,java.util.function.Consumer<String> callback){callback.accept("{}");}}
class Profiles {static int slot(Object context){return 0;}}
class NetworkCatalog {static void put(JSONObject value,String key,Object item){SourceRouteStartObservation.put(value,key,item);}}
class NetworkTransportClient {volatile JSONObject state;final AtomicInteger reads=new AtomicInteger();JSONObject call(String method,String value){TerminalJoinTest.require(method.equals("snapshot")&&value.isEmpty());reads.incrementAndGet();return SourceRouteStartObservation.copy(state);}}
/* BASE_NATIVE_ADAPTER */
