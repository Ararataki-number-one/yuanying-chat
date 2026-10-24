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
    @Override void runStartOperation(int mode){observer.workerBefore("workerBefore".equals(fault)?null:this,mode);try{super.runStartOperation(mode);}finally{if(holdFinally){beforeFinally.countDown();try{await(releaseFinally);}catch(Exception failure){throw new RuntimeException(failure);}}observer.workerAfter("workerAfter".equals(fault)?null:this,mode);}}
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
      n.join(true,false);n.finish(1);JSONObject snapshot=n.observer.snapshot(n.root);JSONArray workers=snapshot.getJSONArray("workerInvocations");
      check("Both worker invocations reuse the exact original root callback",workers.getJSONObject(0).getInt("rootCallbackId")==workers.getJSONObject(1).getInt("rootCallbackId")&&workers.getJSONObject(0).getLong("invocationId")!=workers.getJSONObject(1).getLong("invocationId"));
      boolean specific=false;try{n.observer.joinFor(1,n.stops.get(1));}catch(IOException failure){specific=failure.getMessage().contains("crossed worker invocations");}
      check("Queued restart ABA is rejected by actual invocation identity",specific);
      check("Rejecting observation preserves all original queued callbacks",n.rootCallbacks.get()==1&&n.queuedCallbacks.get()==1&&n.recoverCallbacks.get()==1&&!n.rootOk&&n.recoveryOutcome.state==NativeNetwork.RecoveryState.FAILED);
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
  public static void main(String[] args)throws Exception{JSONObject report=J.obj("status","failed","syntheticControlledHost",true,"checks",checks);try{report.put("joined",joined());report.put("queuedRestart",queued());report.put("callbacksBeforeFinally",callbacksBeforeFinally());wrongBindings();hookFailures();report.put("status","passed");}finally{report.put("total",checks.length());Files.writeString(Path.of(args[0]),report.toString(2));}System.out.println("Start observation checks: "+checks.length());}
}

class NativeNetwork {
  /* ACTUAL_NATIVE_START_MEMBERS */
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
}
class Dispatcher {final BlockingQueue<Runnable> queue=new LinkedBlockingQueue<>();void post(Runnable value){queue.add(value);}}
class NetworkDiagnostics {enum Event{RECONNECT_ATTEMPT,FAILURE}enum Reason{REQUESTED,REPLACE,EXIT_MISMATCH,START_FAILED}enum Stage{RECOVER}}
