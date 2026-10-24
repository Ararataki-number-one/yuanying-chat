package local.pocketchat;

import android.os.SystemClock;
import org.json.*;
import java.io.IOException;
import java.util.*;
import java.util.concurrent.*;

/** Test-only reservation candidate. Android execution remains required.
 * A real start waiter reserves the original worker; no recovery/busy bit is set.
 * A preparation that never returns keeps that real worker reserved. At the
 * original deadline the fixture must fail and admit no next case; thread
 * cancellation is not promised. Identity-bound failure-only process cleanup
 * remains a separate proof obligation before this can be called a repair.
 */
final class SourceRouteStartReservation {
  interface Gate {
    boolean onUiThread();
    Object owner();
    boolean connecting();
    JSONObject contacts();
    void claim(SourceRouteStartReservation reservation)throws Exception;
    default void completed(SourceRouteStartReservation reservation,boolean ok,String message)throws Exception{}
  }
  interface Preparation {JSONObject run()throws Exception;}
  static final long BUDGET_NS=TimeUnit.SECONDS.toNanos(75);
  final NativeNetwork network;final SourceRouteStartObservation observer;final Gate gate;
  final Object scopeToken;final String caseId,source,nonce;
  final long beganAtNs=now(),deadlineNs=beganAtNs+BUDGET_NS;
  final JSONObject evidence;
  final Preparation preparation;
  final NativeNetwork.Callback callback=this::completed;
  final CompletableFuture<Boolean> actualCallback=new CompletableFuture<>();
  volatile SourceRouteStartObservation.Root root;
  volatile Throwable failure;
  volatile boolean prepared;
  volatile int preparations,delegations,callbackCount;
  volatile String state="waiting";
  JSONObject admissionContacts;
  long invocationId;

  SourceRouteStartReservation(NativeNetwork network,SourceRouteStartObservation observer,Gate gate,
      Object scopeToken,String caseId,String source,String nonce,Preparation preparation){
    this.network=network;this.observer=observer;this.gate=gate;this.scopeToken=scopeToken;
    this.caseId=caseId;this.source=source;this.nonce=nonce;this.preparation=preparation;
    evidence=J.obj("schema",1,"prototypeOnly",true,"caseId",caseId,"sourceCommit",source,"runNonce",nonce,
      "beganAtNs",beganAtNs,"deadlineNs",deadlineNs,"budgetNs",BUDGET_NS,"acceptedAsRepair",false);
  }
  static long now(){return SystemClock.elapsedRealtimeNanos();}
  static void require(boolean value,String message)throws IOException{if(!value)throw new IOException("Reservation prototype: "+message);}
  synchronized void put(String key,Object value){try{evidence.put(key,value);}catch(Throwable error){if(failure==null)failure=error;}}
  synchronized void fail(Throwable error){if(failure==null){failure=error;put("failure",error.getClass().getName()+": "+String.valueOf(error.getMessage()));}}
  synchronized JSONObject snapshot(){
    put("prepared",prepared);put("preparationCount",preparations);put("delegationCount",delegations);
    put("callbackCount",callbackCount);put("failed",failure!=null);put("state",state);return copy(evidence);
  }
  long remaining()throws IOException{long value=deadlineNs-now();require(value>0,"original 75s budget exhausted");return value;}
  static JSONObject copy(JSONObject value){return SourceRouteStartObservation.copy(value);}
  static boolean same(JSONObject first,JSONObject second){
    if(first==null||second==null||first.length()!=second.length())return false;
    for(Iterator<String> keys=first.keys();keys.hasNext();){String key=keys.next();if(!second.has(key)||!Objects.equals(first.opt(key),second.opt(key)))return false;}return true;
  }

  /** Caller retries only non-admitted busy observations inside this same budget. */
  boolean tryReserve()throws Exception{
    try{return tryReserveChecked();}
    catch(Throwable error){fail(error);state="failed";if(error instanceof Exception)throw (Exception)error;throw new IOException("Admission observation failed",error);}
  }
  private boolean tryReserveChecked()throws Exception{
    require(gate.onUiThread(),"admission must use the actual UI turn");
    synchronized(network){
      remaining();require(state.equals("waiting")&&root==null,"reservation replay");
      require(gate.owner()==null,"another fixture scope is active");
      if(network.starting||gate.connecting()){put("busyObservedAtNs",now());return false;}
      require(!network.restartQueued&&network.startWaiters.isEmpty(),"idle flags hide queued waiters");
      put("admission",J.obj("atNs",now(),"onUiThread",gate.onUiThread(),"monitorHeld",Thread.holdsLock(network),
          "ownerWasEmpty",gate.owner()==null,"starting",network.starting,"connecting",gate.connecting(),
          "restartQueued",network.restartQueued,"pendingWaiters",network.startWaiters.size()));
      admissionContacts=copy(gate.contacts());put("admissionContacts",copy(admissionContacts));
      try{
        gate.claim(this);require(gate.owner()==scopeToken,"fixture claim did not bind this scope");
        root=observer.root(callback,caseId,source,nonce);require(root!=null,"missing observed root");
        remaining();state="reserved";put("admittedAtNs",now());
        network.restart(callback); // Original mode2: actual waiter + original worker.
        require(network.starting&&network.startWaiters.size()==1&&network.startWaiters.get(0)==callback
            &&!network.restartQueued,"real restart did not reserve the isolated original waiter");
        synchronized(observer){
          require(root.registration!=null&&root.registration.optBoolean("monitorHeldBefore")
              &&root.registration.optBoolean("monitorHeldAfter")&&root.registration.optBoolean("exactAppend")
              &&root.registration.optInt("mode")==2&&!root.registration.optBoolean("startingBefore"),
              "actual restart registration proof missing");
        }
        put("realRegistration",observer.snapshot(root).optJSONObject("rootRegistration"));return true;
      }catch(Throwable error){fail(error);state="failed";if(error instanceof Exception)throw (Exception)error;throw new IOException("Admission observation failed",error);}
    }
  }

  /** Called with the real native monitor and observation monitor held. */
  private void requireAllowedAdmissions()throws Exception{
    require(root!=null&&root.errors.length()==0,"reservation observation is incomplete");
    for(int i=0;i<root.admissions.length();i++){
      JSONObject joined=root.admissions.getJSONObject(i);
      require(joined.getInt("mode")==1&&joined.getString("callbackKind").equals("recovery")
          &&joined.getString("caseId").equals(caseId)&&joined.getBoolean("adapterCallbackMatches")
          &&joined.getBoolean("monitorHeldBefore")&&joined.getBoolean("monitorHeldAfter")
          &&joined.getBoolean("startingBefore")&&joined.getBoolean("startingAfter")
          &&joined.getBoolean("exactAppend")&&joined.getBoolean("rootCallbackRetained")
          &&!joined.getBoolean("restartQueuedBefore")&&!joined.getBoolean("restartQueuedAfter"),
          "unexpected start admission in the reserved operation");
    }
  }

  void prepareAtWorkerEntry(int mode)throws Exception{
    synchronized(network){synchronized(observer){
      remaining();require(gate.owner()==scopeToken&&state.equals("reserved"),"worker crossed scope or reservation state");
      SourceRouteStartObservation.Invocation invocation=observer.current.get();
      require(root!=null&&invocation!=null&&invocation.root==root&&root.running==invocation
          &&root.invocations.length()==1&&mode==2&&invocation.record.optInt("mode")==2,
          "not the one actual reserved mode2 invocation");
      require(network.starting&&!network.restartQueued&&network.startWaiters.contains(callback)
          &&root.errors.length()==0,"reservation was queued, replaced, or incomplete");
      requireAllowedAdmissions();
      invocationId=invocation.record.getLong("invocationId");state="preparing";preparations++;
      put("invocationId",invocationId);put("prepareBeganAtNs",now());
    }}
    // No network monitor or UI dispatcher is held during the actual private IO.
    put("prepareMonitorHeld",Thread.holdsLock(network));put("prepareThreadId",Thread.currentThread().getId());
    require(!Thread.holdsLock(network),"preparation would run under the network monitor");
    JSONObject result=null;
    try{
      result=preparation.run();require(result!=null&&result.optBoolean("managedCoreStopped"),"original managed-core-stopped check missing");
      JSONObject contacts=copy(gate.contacts());put("actualPreparationContacts",contacts);
      require(same(result.optJSONObject("contacts"),contacts)&&same(admissionContacts,contacts),"preparation changed real target contacts");
      synchronized(network){synchronized(observer){
        remaining();require(gate.owner()==scopeToken&&network.starting&&!network.restartQueued
            &&network.startWaiters.contains(callback)&&observer.current.get()==root.running
            &&root.running!=null&&root.running.record.optLong("invocationId")==invocationId,
            "preparation lost the actual reserved operation");
        requireAllowedAdmissions();
      }}
      prepared=true;state="prepared";put("preparationResult",copy(result));
    }finally{put("prepareEndedAtNs",now());put("actualPreparationContacts",copy(gate.contacts()));}
  }

  /** Surround with the existing workerBefore/workerAfter observer hooks.
   * Even rejected preparation delegates the original body exactly once; its
   * actual callbacks/contacts are retained and cannot turn failure into success.
   * This finally cannot run while a preparation remains permanently blocked.
   */
  void runReservedWorker(int mode,Runnable original){
    try{try{prepareAtWorkerEntry(mode);}catch(Throwable error){fail(error);state="failed";}}
    finally{
      delegations++;put("originalDelegations",delegations);put("originalThreadId",Thread.currentThread().getId());put("originalBeganAtNs",now());
      try{original.run();}
      finally{put("originalEndedAtNs",now());try{put("actualContactsAfterOriginal",copy(gate.contacts()));}catch(Throwable error){fail(error);}}
    }
  }
  void completed(boolean ok,String message){
    try{
      callbackCount++;put("callbackCount",callbackCount);put("actualCallback",J.obj("ok",ok,"message",message,"atNs",now(),"onUiThread",gate.onUiThread(),"threadId",Thread.currentThread().getId()));
      require(gate.owner()==scopeToken&&callbackCount==1,"late, duplicate, or wrong-scope callback");
      gate.completed(this,ok,message);
      require(prepared,"unprepared callback");
      if(failure!=null)throw new IOException("preparation permanently failed",failure);
      actualCallback.complete(ok);
    }catch(Throwable error){fail(error);actualCallback.completeExceptionally(error);}
    // Never throw into the original callbacks loop and skip joined waiters.
  }
  boolean awaitCallback()throws Exception{
    try{return actualCallback.get(remaining(),TimeUnit.NANOSECONDS);}
    catch(Exception error){fail(error);throw error;}
  }
  void verifyAccepted()throws Exception{
    try{verifyAcceptedChecked();}
    catch(Throwable error){fail(error);state="failed";if(error instanceof Exception)throw (Exception)error;throw new IOException("Reservation acceptance failed",error);}
  }
  private void verifyAcceptedChecked()throws Exception{
    remaining();require(failure==null&&prepared&&preparations==1&&delegations==1&&callbackCount==1,
        "prototype has failed or incomplete preparation/delegation");
    synchronized(network){synchronized(observer){
      requireAllowedAdmissions();
      require(gate.owner()==scopeToken&&root!=null&&root.errors.length()==0&&root.invocations.length()==1
          &&root.completion.isDone()&&!root.completion.isCompletedExceptionally()
          &&!network.starting&&!network.restartQueued&&network.startWaiters.isEmpty(),
          "actual reserved operation has not uniquely retired");
      JSONObject observation=observer.snapshot(root);remaining();
      put("validation",J.obj("atNs",now(),"prepared",prepared,"preparations",preparations,
          "delegations",delegations,"callbacks",callbackCount,"failed",failure!=null,"state",state,
          "scopeOwned",gate.owner()==scopeToken,"starting",network.starting,"restartQueued",network.restartQueued,
          "pendingWaiters",network.startWaiters.size(),"workerCompleted",root.completion.isDone(),
          "workerFailed",root.completion.isCompletedExceptionally(),"rootObservation",observation));
      remaining();
    }}
  }
}
