package local.pocketchat;

import android.os.SystemClock;
import org.json.*;
import java.io.IOException;
import java.util.*;
import java.util.concurrent.*;

/** Fixture-only observation. Never starts, stops, or cancels a production recovery. */
final class SourceRouteTerminalObserver {
  final NetworkSourcesRouteIntegrationActivity test;
  final ExecutorService reader=Executors.newSingleThreadExecutor();
  volatile Scope active;
  SourceRouteTerminalObserver(NetworkSourcesRouteIntegrationActivity test){this.test=test;}
  static long now(){return SystemClock.elapsedRealtimeNanos();}
  static JSONObject copy(JSONObject value){return value==null?new JSONObject():J.parse(value.toString());}
  static void require(boolean value,String message)throws IOException{if(!value)throw new IOException("Negative terminal evidence: "+message);}
  static long remaining(Scope scope)throws IOException{long value=scope.deadlineNs-now();require(value>0,"original case phase deadline expired");return value;}
  static final class Recovery {
    final JSONObject record;final CompletableFuture<JSONObject> done=new CompletableFuture<>();
    Recovery(JSONObject record){this.record=record;}
  }
  static final class Scope {
    final String name,id;final JSONObject evidence,contacts;
    final ArrayList<Recovery> recoveries=new ArrayList<>();final JSONArray stops=new JSONArray();
    volatile long deadlineNs;JSONObject restartTerminal;volatile SourceRouteStartObservation.Root startupRoot;
    Scope(String name,String nonce,JSONObject contacts){this.name=name;id=UUID.randomUUID().toString();this.contacts=copy(contacts);evidence=J.obj("schema",1,"case",name,"caseId",id,"runNonce",nonce,"startedAtNs",now(),"status","collecting","fetchBudgetMs",22000,"stopObservations",stops);}
  }
  Scope begin(String name,JSONObject contacts)throws Exception{
    Scope scope=new Scope(name,test.runNonce,contacts);long began=now();scope.deadlineNs=began+TimeUnit.SECONDS.toNanos(75);NetworkCatalog.put(scope.evidence,"restartBeganAtNs",began);NetworkCatalog.put(scope.evidence,"restartDeadlineAtNs",scope.deadlineNs);NetworkCatalog.put(scope.evidence,"sourceCommit",test.expectedSource);
    return ui(scope,()->{require(active==null&&!test.network.starting&&!test.session.connecting,"a previous operation remains active");active=scope;return scope;});
  }
  void beginFetch(Scope scope){long began=now();scope.deadlineNs=began+TimeUnit.SECONDS.toNanos(22);NetworkCatalog.put(scope.evidence,"fetchBeganAtNs",began);NetworkCatalog.put(scope.evidence,"deadlineAtNs",scope.deadlineNs);}
  <T>T ui(Scope scope,NetworkSourcesRouteIntegrationActivity.Work<T> work)throws Exception{
    CompletableFuture<T> future=new CompletableFuture<>();test.runOnUiThread(()->{try{if(now()>=scope.deadlineNs)throw new IOException("Negative terminal evidence: original case phase deadline expired");future.complete(work.run());}catch(Throwable error){future.completeExceptionally(error);}});
    return future.get(remaining(scope),TimeUnit.NANOSECONDS);
  }
  JSONObject eval(Scope scope,String script)throws Exception{
    CompletableFuture<JSONObject> future=new CompletableFuture<>();test.runOnUiThread(()->{try{if(now()>=scope.deadlineNs)throw new IOException("Negative terminal evidence: original fetch deadline expired");test.view.evaluateJavascript(script,value->future.complete(J.parse(value)));}catch(Throwable error){future.completeExceptionally(error);}});
    return future.get(remaining(scope),TimeUnit.NANOSECONDS);
  }
  JSONObject fence(Scope scope){
    return J.obj("caseId",active==null?"":active.id,"sourceCommit",test.expectedSource,"runNonce",test.runNonce,
      "environmentId",test.session.environmentId,"environmentGeneration",test.session.environmentGeneration,"slot",Profiles.slot(test),
      "sessionIdentity",System.identityHashCode(test.session),"browserIdentity",System.identityHashCode(test.view),"transportIdentity",System.identityHashCode(test.network.transport),
      "connectionEpoch",test.session.connectionEpoch,"recoveryToken",test.session.recoveryToken,"recoveryRequestSerial",test.recoveryRequestSerial,"routeSerial",test.network.routeSerial,
      "starting",test.network.starting,"connecting",test.session.connecting,"ready",test.network.ready,"hasVerifiedReceipt",test.network.verifiedRoute!=null);
  }
  JSONObject cache(){return copy(test.network.transport==null?null:test.network.transport.state);}
  void restartDone(boolean ok){Scope scope=active;if(scope!=null)synchronized(scope){scope.restartTerminal=J.obj("ok",ok,"atNs",now(),"cache",cache());}}
  Recovery recoveryStarted(int request){Scope scope=active;if(scope==null)return null;Recovery item=new Recovery(J.obj("request",request,"caseId",scope.id,"recoveryToken",test.session.recoveryToken,"connectionEpoch",test.session.connectionEpoch,"requestedAtNs",now()));synchronized(scope){scope.recoveries.add(item);}return item;}
  void recoveryFinished(Recovery item,NativeNetwork.RecoveryOutcome outcome){if(item==null)return;Scope scope=active;try{require(scope!=null&&scope.id.equals(item.record.getString("caseId")),"recovery callback crossed cases");synchronized(scope){NetworkCatalog.put(item.record,"completedAtNs",now());NetworkCatalog.put(item.record,"outcome",outcome.state.name());NetworkCatalog.put(item.record,"hasReceipt",outcome.receipt!=null);NetworkCatalog.put(item.record,"terminalCache",cache());NetworkCatalog.put(item.record,"terminalFence",fence(scope));}item.done.complete(copy(item.record));}catch(Exception error){item.done.completeExceptionally(error);}}
  JSONObject stopBefore(NativeNetwork.ExitRouteReceipt owned,NetworkDiagnostics.Reason reason){Scope scope=active;if(scope==null||owned==null)return null;JSONObject row=J.obj("caseId",scope.id,"beganAtNs",now(),"recoveryRequestSerial",test.recoveryRequestSerial,"reason",reason.name(),"owned",J.obj("pid",owned.pid,"servicePid",owned.servicePid,"generation",owned.generation,"configuration",owned.configuration),"beforeCache",cache());synchronized(scope){scope.stops.put(row);}return row;}
  void stopAfter(JSONObject row){if(row!=null){NetworkCatalog.put(row,"endedAtNs",now());NetworkCatalog.put(row,"afterRequestSerial",test.recoveryRequestSerial);NetworkCatalog.put(row,"afterCache",cache());NetworkCatalog.put(row,"observation","client cache after original stopOwnedCore returned; not exit proof");}}
  static void snapshot(JSONObject value)throws Exception{
    for(String key:new String[]{"alive"})require(value.opt(key) instanceof Boolean,"unknown snapshot "+key);
    for(String key:new String[]{"slot","pid","servicePid"})require(value.opt(key) instanceof Integer||value.opt(key) instanceof Long,"unknown snapshot "+key);
    require(value.getInt("slot")>=0&&value.getInt("pid")>=0&&value.getInt("servicePid")>0,"invalid process identity");
    for(String key:new String[]{"state","generation","configuration"})require(value.opt(key) instanceof String&&!value.getString(key).isEmpty(),"unknown snapshot "+key);
    require(value.getString("generation").matches("[0-9a-fA-F-]{36}")&&value.getString("configuration").matches("[0-9a-f]{64}"),"invalid generation/configuration");
  }
  static void closed(JSONObject value)throws Exception{snapshot(value);require(!value.getBoolean("alive")&&value.getInt("pid")==0&&value.getString("state").equals("closed"),"service did not prove a closed process");}
  static boolean sameSnapshot(JSONObject a,JSONObject b)throws Exception{for(String key:new String[]{"slot","pid","servicePid","state","alive","generation","configuration"})if(!Objects.equals(a.get(key),b.get(key)))return false;return true;}
  boolean stopBelongsToRecovery(Scope scope,JSONObject stop,int request)throws Exception{
    if(stop.getInt("recoveryRequestSerial")==request)return true;
    if(stop.getInt("afterRequestSerial")!=request||request!=stop.getInt("recoveryRequestSerial")+1||scope.startupRoot==null)return false;
    JSONObject recovery=null;synchronized(scope){for(Recovery item:scope.recoveries)if(item.record.getInt("request")==request){require(recovery==null,"duplicate joined request");recovery=item.record;}}
    require(recovery!=null&&recovery.getString("caseId").equals(scope.id)&&recovery.getLong("requestedAtNs")>=stop.getLong("beganAtNs")&&recovery.getLong("requestedAtNs")<=stop.getLong("endedAtNs")&&recovery.getLong("completedAtNs")>=stop.getLong("endedAtNs"),"joined request does not overlap this owned stop");
    JSONObject proof=test.network.startObservation.joinFor(request,stop);require(proof.getString("caseId").equals(scope.id)&&proof.getString("sourceCommit").equals(test.expectedSource)&&proof.getString("runNonce").equals(test.runNonce),"joined startup identity changed");NetworkCatalog.put(stop,"joinedRecovery",proof);return true;
  }
  void awaitJoinedWorker(Scope scope)throws Exception{
    require(scope.startupRoot!=null,"crossed stop has no registered restart");JSONObject wait=J.obj("method","actual-start-worker-observer-completion","requestedAtNs",now());NetworkCatalog.put(scope.evidence,"startObservationWait",wait);
    test.network.startObservation.workerCompletion(scope.startupRoot).get(remaining(scope),TimeUnit.NANOSECONDS);NetworkCatalog.put(wait,"completedAtNs",now());
  }
  void finish(Scope scope,JSONObject negative)throws Exception{
    NetworkCatalog.put(negative,"terminalEvidence",scope.evidence);
    try{
      JSONObject immediate=J.obj("atNs",negative.getLong("postFetchObservedAtNs"),"coreAlive",negative.getBoolean("coreAliveAfter"),"ready",negative.getBoolean("readyAfter"),"message",negative.getString("message"));
      final ArrayList<Recovery> selected=new ArrayList<>();JSONObject cut=ui(scope,()->{synchronized(scope){selected.addAll(scope.recoveries);}return J.obj("cutAtNs",now(),"cache",cache(),"fence",fence(scope));});for(Iterator<String> keys=cut.keys();keys.hasNext();){String key=keys.next();NetworkCatalog.put(immediate,key,cut.get(key));}
      synchronized(scope){NetworkCatalog.put(scope.evidence,"postFetchCache",immediate);}require(!immediate.getBoolean("ready"),"post-fetch network was ready");
      JSONArray callbacks=new JSONArray();for(Recovery item:selected)callbacks.put(item.done.get(remaining(scope),TimeUnit.NANOSECONDS));NetworkCatalog.put(scope.evidence,"recoveries",callbacks);
      boolean crossed=false;synchronized(scope){for(int i=0;i<scope.stops.length();i++){JSONObject stop=scope.stops.getJSONObject(i);crossed|=stop.getInt("recoveryRequestSerial")!=stop.getInt("afterRequestSerial");}}
      if(crossed)awaitJoinedWorker(scope);
      if(immediate.getBoolean("coreAlive")){boolean overlapping=false;long observed=immediate.getLong("atNs");for(int i=0;i<callbacks.length();i++){JSONObject callback=callbacks.getJSONObject(i);overlapping|=callback.getLong("requestedAtNs")<=observed&&observed<callback.getLong("completedAtNs");}require(overlapping,"live post-fetch cache has no overlapping recovery");}
      JSONObject before=ui(scope,()->{synchronized(scope){require(active==scope&&scope.recoveries.size()==selected.size(),"a new recovery crossed the terminal selection");}JSONObject f=fence(scope);require(!f.getBoolean("starting")&&!f.getBoolean("connecting")&&!f.getBoolean("ready")&&!f.getBoolean("hasVerifiedReceipt"),"operation has no rejected terminal callback");return f;});
      NetworkCatalog.put(scope.evidence,"fenceBefore",before);
      JSONObject anchor;synchronized(scope){require(scope.restartTerminal!=null&&!scope.restartTerminal.getBoolean("ok"),"missing rejected restart callback");NetworkCatalog.put(scope.evidence,"restartTerminal",copy(scope.restartTerminal));anchor=copy(scope.restartTerminal.getJSONObject("cache"));}
      for(int i=0;i<callbacks.length();i++){JSONObject cb=callbacks.getJSONObject(i);require(cb.getString("caseId").equals(scope.id)&&cb.getString("outcome").equals("FAILED")&&!cb.getBoolean("hasReceipt"),"recovery did not fail for this case");anchor=cb.getJSONObject("terminalCache");}
      closed(anchor);NetworkCatalog.put(scope.evidence,"terminalAnchor",copy(anchor));
      JSONObject cutCache=immediate.getJSONObject("cache");snapshot(cutCache);require(cutCache.getInt("slot")==anchor.getInt("slot")&&cutCache.getInt("servicePid")==anchor.getInt("servicePid")&&cutCache.getString("configuration").equals(anchor.getString("configuration")),"cut cache changed service or configuration");
      Set<Integer> activeAtCut=new HashSet<>();long cutAt=immediate.getLong("cutAtNs");for(int i=0;i<callbacks.length();i++){JSONObject cb=callbacks.getJSONObject(i);if(cb.getLong("requestedAtNs")<=cutAt&&cutAt<cb.getLong("completedAtNs"))activeAtCut.add(cb.getInt("request"));}
      if(activeAtCut.isEmpty())require(sameSnapshot(cutCache,anchor),"cut cache has no matching terminal callback");
      else if(cutCache.getBoolean("alive")){int ownedAtCut=0;synchronized(scope){for(int i=0;i<scope.stops.length();i++){JSONObject stop=scope.stops.getJSONObject(i),owned=stop.getJSONObject("owned");boolean requestOwned=false;for(int request:activeAtCut)requestOwned|=stopBelongsToRecovery(scope,stop,request);if(requestOwned&&cutAt<=stop.getLong("endedAtNs")&&owned.getInt("pid")==cutCache.getInt("pid")&&owned.getInt("servicePid")==cutCache.getInt("servicePid")&&owned.getString("generation").equals(cutCache.getString("generation"))&&owned.getString("configuration").equals(cutCache.getString("configuration")))ownedAtCut++;}}require(ownedAtCut==1,"live cut cache has no unique observed recovery owner");}
      else closed(cutCache);
      NetworkTransportClient transport=test.network.transport;require(transport!=null,"missing transport");
      JSONObject read=J.obj("method","NetworkTransportClient.call(snapshot)","requestedAtNs",now());NetworkCatalog.put(scope.evidence,"freshRead",read);
      Future<JSONObject> future=reader.submit(()->transport.call("snapshot",""));JSONObject fresh;
      try{fresh=future.get(remaining(scope),TimeUnit.NANOSECONDS);}catch(Exception error){future.cancel(true);throw error;}
      NetworkCatalog.put(read,"receivedAtNs",now());NetworkCatalog.put(read,"snapshot",copy(fresh));closed(fresh);
      require(sameSnapshot(anchor,fresh),"fresh service generation differs from callback closure");require(fresh.getInt("slot")==before.getInt("slot"),"fresh service belongs to another environment");
      synchronized(scope){
        for(int i=0;i<scope.stops.length();i++){
          JSONObject stop=scope.stops.getJSONObject(i),owned=stop.getJSONObject("owned"),prior=stop.getJSONObject("beforeCache"),ended=stop.getJSONObject("afterCache");snapshot(prior);closed(ended);
          require(stop.getString("caseId").equals(scope.id),"stop observation crossed cases");
          require(stop.getInt("recoveryRequestSerial")==stop.getInt("afterRequestSerial")||stopBelongsToRecovery(scope,stop,stop.getInt("afterRequestSerial")),"stop observation crossed a recovery without exact startup registration");
          require(owned.getInt("pid")>0&&prior.getBoolean("alive")&&owned.getInt("pid")==prior.getInt("pid")&&owned.getInt("servicePid")==prior.getInt("servicePid")&&owned.getString("generation").equals(prior.getString("generation"))&&owned.getString("configuration").equals(prior.getString("configuration")),"stop owner was not the observed live process");
          require(!owned.getString("generation").equals(ended.getString("generation"))&&owned.getInt("servicePid")==ended.getInt("servicePid")&&owned.getString("configuration").equals(ended.getString("configuration")),"stop did not retain a distinguishable closure identity");
        }
        if(scope.name.startsWith("same-name-")){require(scope.stops.length()>0,"missing owned startup rejection");require(sameSnapshot(scope.stops.getJSONObject(scope.stops.length()-1).getJSONObject("afterCache"),fresh),"terminal IPC is not the last owned closure");}
      }
      JSONObject after=ui(scope,()->{synchronized(scope){require(scope.recoveries.size()==selected.size(),"a new recovery crossed the IPC read");}require(active==scope&&test.network.transport==transport,"case or transport changed");JSONObject f=fence(scope);require(before.toString().equals(f.toString()),"terminal identity changed across IPC");JSONObject finalCache=cache();NetworkCatalog.put(scope.evidence,"finalCache",finalCache);closed(finalCache);require(sameSnapshot(fresh,finalCache),"pushed service identity changed after terminal IPC");JSONObject contacts=test.contacts();NetworkCatalog.put(scope.evidence,"contactsBefore",scope.contacts);NetworkCatalog.put(scope.evidence,"contactsAfter",contacts);require(scope.contacts.toString().equals(contacts.toString()),"a target was contacted while awaiting closure");NetworkCatalog.put(scope.evidence,"completedAtNs",now());active=null;return f;});NetworkCatalog.put(scope.evidence,"fenceAfter",after);
      NetworkCatalog.put(negative,"coreAliveAfter",fresh.getBoolean("alive"));NetworkCatalog.put(negative,"readyAfter",after.getBoolean("ready"));NetworkCatalog.put(scope.evidence,"status","passed");
    }catch(Exception error){NetworkCatalog.put(scope.evidence,"status","failed");NetworkCatalog.put(scope.evidence,"error",error.getClass().getName()+": "+String.valueOf(error.getMessage()));throw error;}
    finally{if(scope.startupRoot!=null)NetworkCatalog.put(scope.evidence,"startObservation",test.network.startObservation.snapshot(scope.startupRoot));if(active==scope)active=null;}
  }
  void close(){active=null;reader.shutdownNow();}
}
