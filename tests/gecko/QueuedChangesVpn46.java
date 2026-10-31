package local.pocketchat;

import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.Uri;
import android.os.Bundle;
import android.os.SystemClock;
import java.io.IOException;
import java.util.concurrent.Callable;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import org.json.JSONArray;
import org.json.JSONObject;

/** Actual test-package VPN lifecycle; no replacement of production CM/guard state. */
final class QueuedChangesVpn46 {
  static final ExecutorService worker=Executors.newSingleThreadExecutor();
  final GeckoIntegrationTestActivity activity;final ChatSession session;final long command;final int environmentGeneration;
  final String environment,nonce,source,originalProxy,url;
  final Object sdk;final Uri endpoint=Uri.parse("content://local.pocketchat.test.queued-vpn-fixture");
  final JSONArray events=new JSONArray();volatile long generation=-1;volatile boolean aborted,stopRequested,appliedObserved,closedObserved,cleanupConfirmed;long beganAt,stopBudgetStarted;
  Runnable beforeStop=()->{};
  final Runnable watchOwner=new Runnable(){public void run(){
    if(aborted||closedObserved)return;if(!owns()){abort();return;}
    if(SystemClock.elapsedRealtime()-beganAt>=20000){fail(new IOException("Queued fixture owner budget elapsed"));return;}
    session.handler.postDelayed(this,100);
  }};
  JSONObject prepared,startState,coveredState,admission,appliedState,closedState,stopDispatch,expectedCandidate;String failure="",cleanupFailure="";
  QueuedChangesVpn46(GeckoIntegrationTestActivity a,long serial)throws IOException{
    activity=a;session=a.session;command=serial;environmentGeneration=session.environmentGeneration;environment=session.environmentId;sdk=session.web.current;source=a.eventBuildIdentity.optString("sourceCommit");nonce=a.eventStore==null?"":a.eventStore.nonce;originalProxy=session.prefs.getString("proxy","");url=session.web.getUrl();
    if(!"local.pocketchat.test".equals(a.getPackageName())||a.slot!=1||!source.matches("[0-9a-f]{40}")||!nonce.matches("[0-9a-f]{32}")||!"http://127.0.0.1:1081".equals(originalProxy))throw new IOException("Exact second-environment loopback fixture required");
    GeckoQueuedChangesObservation.validateOwner(url,a.slot);
  }
  boolean owns(){return !aborted&&activity.queuedVpn==this&&activity.run==command&&activity.session==session&&ChatSession.peek()==session&&!session.deleted&&session.environmentGeneration==environmentGeneration&&environment.equals(session.environmentId)&&session.web.current==sdk&&url.equals(session.web.getUrl());}
  <T>T ui(Callable<T> operation)throws Exception{
    CompletableFuture<T> value=new CompletableFuture<>();session.handler.post(()->{try{value.complete(operation.call());}catch(Throwable failure){value.completeExceptionally(failure);}});return value.get(3,TimeUnit.SECONDS);
  }
  JSONObject call(String method,long expected)throws Exception{
    Bundle args=new Bundle();args.putString("runNonce",nonce);args.putString("sourceCommit",source);args.putLong("generation",expected);
    Bundle result=activity.getContentResolver().call(endpoint,method,null,args);if(result==null)throw new IOException("Queued VPN IPC returned no state");JSONObject value=new JSONObject(result.getString("json",""));
    if(value.optInt("schema")!=1||!Boolean.TRUE.equals(value.opt("sameProcessServiceState"))||value.optInt("providerPid")<=0||!source.equals(value.optString("installedSource"))||value.optJSONObject("state")==null)throw new IOException("Queued VPN IPC identity unavailable");
    return value;
  }
  JSONObject network(){
    ConnectivityManager cm=activity.getSystemService(ConnectivityManager.class);Network n=cm==null?null:cm.getActiveNetwork();NetworkCapabilities caps=n==null?null:cm.getNetworkCapabilities(n);
    return J.obj("at",SystemClock.elapsedRealtime(),"network",n==null?"":n.toString(),"vpn",caps!=null&&caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN),"internet",caps!=null&&caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET),"observerNetwork",session.networkIdentity,"offline",session.offline,"connecting",session.connecting,"recoveryScheduled",session.recoveryScheduled,"guardRequiresVpn",session.guard.requiresVpn(),"guardVpnActive",session.guard.vpnActive(),"guardCoverageIssue",session.guard.vpnDefaultRouteIssue(),"guardRouteProtected",session.guard.routeProtected(),"guardAllowed",session.guard.allowed(),"networkReady",session.networkReady,"navigationEpoch",session.navigationEpoch,"connectionEpoch",session.connectionEpoch,"url",session.web.getUrl());
  }
  static boolean covered(JSONObject state){return Boolean.TRUE.equals(state.opt("vpn"))&&Boolean.TRUE.equals(state.opt("internet"))&&state.optString("network").equals(state.optString("observerNetwork"))&&!state.optString("network").isEmpty()&&Boolean.FALSE.equals(state.opt("offline"))&&Boolean.FALSE.equals(state.opt("connecting"))&&Boolean.FALSE.equals(state.opt("recoveryScheduled"))&&state.opt("guardCoverageIssue") instanceof String&&state.optString("guardCoverageIssue").isEmpty();}
  static boolean closed(JSONObject state){return Boolean.FALSE.equals(state.opt("vpn"))&&Boolean.FALSE.equals(state.opt("guardVpnActive"))&&Boolean.TRUE.equals(state.opt("guardRequiresVpn"))&&Boolean.FALSE.equals(state.opt("guardAllowed"));}
  static boolean requestedClose(JSONObject state,long generation){
    if(!QueuedChangesVpnProvider.integer(state.opt("generation"))||state.optLong("generation")!=generation||generation<=0||!Boolean.FALSE.equals(state.opt("running"))||!Boolean.TRUE.equals(state.opt("fdCloseSucceeded")))return false;
    JSONArray records=state.optJSONArray("events");if(records==null)return false;
    for(int i=0;i<records.length();i++){JSONObject row=records.optJSONObject(i);if(row!=null&&QueuedChangesVpnProvider.integer(row.opt("generation"))&&row.optLong("generation")==generation&&"tun-closed".equals(row.optString("kind"))&&"requested-stop".equals(row.optString("detail")))return true;}return false;
  }
  static long cleanupGeneration(JSONObject state,String run,String source,long known)throws IOException{
    if(state==null||!QueuedChangesVpnProvider.integer(state.opt("generation"))||!(state.opt("runNonce") instanceof String)||!(state.opt("sourceCommit") instanceof String))throw new IOException("Cleanup VPN state identity unavailable");
    long actual=state.optLong("generation");if(actual==0&&state.optString("runNonce").isEmpty()&&state.optString("sourceCommit").isEmpty())return -1;
    if(!QueuedChangesVpnProvider.matches(state,run,source,actual)||known>0&&known!=actual)throw new IOException("Cleanup refuses another VPN owner or generation");return actual;
  }
  static JSONObject expectedCandidate(JSONObject snapshot,String environment,int generation)throws IOException{
    JSONObject receipt=snapshot==null?null:snapshot.optJSONObject("operationResult");
    if(receipt==null||!environment.equals(receipt.optString("environmentId"))||!QueuedChangesVpnProvider.integer(receipt.opt("generation"))||receipt.optLong("generation")!=generation||!receipt.optString("candidateId").matches("[a-z0-9:-]{1,96}")||!QueuedChangesVpnProvider.integer(receipt.opt("savedRevision"))||receipt.optLong("savedRevision")<=0||!QueuedChangesVpnProvider.integer(receipt.opt("appliedRevision"))||receipt.optLong("appliedRevision")!=0||!"saved".equals(receipt.optString("saveState"))||!"pending".equals(receipt.optString("applicationState"))||!"session".equals(receipt.optString("scope")))throw new IOException("Exact current DEFER save receipt required");
    return J.parse(receipt.toString());
  }
  void note(String kind,JSONObject value){synchronized(events){if(events.length()<24)events.put(J.obj("kind",kind,"at",SystemClock.elapsedRealtime(),"value",value));}}
  void begin(Runnable ready){
    beganAt=SystemClock.elapsedRealtime();session.handler.post(watchOwner);worker.execute(()->{try{
      if(!ui(this::owns))throw new IOException("Queued VPN fixture owner changed before start");prepared=call("prepare",-1);if(!prepared.optBoolean("prepared"))throw new IOException("ACTIVATE_VPN test-package permission was not prepared");
      JSONObject old=prepared.getJSONObject("state");long before=old.optLong("generation",-1);if(!QueuedChangesVpnProvider.mayStart(old,nonce,source,before))throw new IOException("Another VPN fixture owner is present");
      note("before-start",prepared);startState=call("start",before);long deadline=SystemClock.elapsedRealtime()+15000;String previous="";int stable=0;
      while(SystemClock.elapsedRealtime()<deadline){
        if(!ui(this::owns))throw new IOException("Queued VPN fixture owner changed during start");JSONObject response=call("state",-1),state=response.getJSONObject("state");JSONObject cm=ui(this::network);
        if(nonce.equals(state.optString("runNonce"))&&source.equals(state.optString("sourceCommit"))&&state.optLong("generation")>before){generation=state.optLong("generation");if(!state.optString("error").isEmpty())throw new IOException("Owned VPN failed: "+state.optString("error"));}
        boolean full=generation>0&&QueuedChangesVpnProvider.matches(state,nonce,source,generation)&&state.optBoolean("running")&&"full".equals(state.optString("mode"))&&Boolean.FALSE.equals(state.opt("forwardsTraffic"))&&covered(cm);
        String observed=cm.optString("network");if(full&&observed.equals(previous))stable++;else stable=full?1:0;previous=observed;
        if(stable>=3){coveredState=J.obj("ipc",response,"network",cm);break;}Thread.sleep(100);
      }
      if(coveredState==null)throw new IOException("Actual full VPN and original observer network did not settle");note("full-vpn-settled",coveredState);
      EnvironmentSpec.Identity identity=ProfileCatalog.get(activity).identity(activity.slot);
      admission=ui(()->{
        if(!owns()||identity.generation!=environmentGeneration||!environment.equals(identity.environmentId)||!url.equals(session.web.getUrl())||!originalProxy.equals(session.prefs.getString("proxy",""))||!covered(network()))throw new IOException("Original fixture route changed before admission");
        long lease=session.beginNetworkApplication(identity);boolean accepted=session.adoptNetworkApplication(lease,null);JSONObject result=J.obj("accepted",accepted,"lease",lease,"network",network(),"scope","Existing explicit loopback route through unchanged production begin/adopt; not a normal cold-start or public website acceptance");if(!accepted)throw new IOException("Production refused the original fixture route");return result;
      });note("original-route-admission",admission);session.handler.post(()->{if(owns())ready.run();else abort();});
    }catch(Exception error){fail(error);}});
  }
  /** Called at the original Bridge callback; its original 3500ms check stays fixed. */
  void stopWhenApplied(JSONObject snapshot){
    stopBudgetStarted=SystemClock.elapsedRealtime();try{expectedCandidate=expectedCandidate(snapshot,environment,environmentGeneration);}catch(Exception error){fail(error);return;}worker.execute(()->{try{
      long deadline=stopBudgetStarted+3500;
      while(SystemClock.elapsedRealtime()<deadline){
        if(!ui(this::owns))throw new IOException("Queued fixture owner changed before application");
        JSONObject pending=NetworkChanges.pendingStrict(activity);EnvironmentSpec model=new EnvironmentSpecRepository(activity).load();
        long revision=expectedCandidate.optLong("savedRevision");if(model.identity.slot!=activity.slot||model.identity.generation!=environmentGeneration||!environment.equals(model.identity.environmentId)||model.desiredRevision!=revision)throw new IOException("Deferred configuration or environment was replaced");
        if(pending.length()>0&&!expectedCandidate.optString("candidateId").equals(NetworkApplyCoordinator.candidateId(pending)))throw new IOException("Deferred candidate was replaced");
        boolean complete=pending.length()==0&&!model.pending()&&model.appliedRevision==revision;
        if(complete&&ui(()->session.prefs.getString("proxy","x").isEmpty()&&session.prefs.getBoolean("requireExternalVpn",false)&&session.networkReady&&session.guard.allowed())){
          appliedObserved=true;appliedState=J.obj("observedAt",SystemClock.elapsedRealtime(),"pendingCount",pending.length(),"desiredRevision",model.desiredRevision,"appliedRevision",model.appliedRevision,"network",ui(this::network));note("actual-deferred-application",appliedState);ui(()->{if(!owns())throw new IOException("Queued owner changed before observer retirement");beforeStop.run();return null;});stopOwned(true);
          while(SystemClock.elapsedRealtime()<deadline){
            JSONObject response=call("state",generation),state=response.getJSONObject("state");JSONObject cm=ui(this::network);
            if(QueuedChangesVpnProvider.matches(state,nonce,source,generation)&&requestedClose(state,generation)&&closed(cm)){
              closedObserved=true;closedState=J.obj("ipc",response,"network",cm);session.handler.removeCallbacks(watchOwner);note("owned-vpn-closed-and-guard-blocked",closedState);return;
            }Thread.sleep(50);
          }
          throw new IOException("Owned VPN close and actual guard block exceeded the original check budget");
        }Thread.sleep(50);
      }
      throw new IOException("Actual deferred application was not observed within the original check budget");
    }catch(Exception error){fail(error);}});
  }
  synchronized void stopOwned(boolean requireRunning)throws Exception{
    if(generation<=0||stopRequested)return;JSONObject response=call("state",generation),state=response.getJSONObject("state");
    if(!QueuedChangesVpnProvider.matches(state,nonce,source,generation))throw new IOException("Owned VPN generation changed; refusing STOP");
    if(requireRunning&&!Boolean.TRUE.equals(state.opt("running")))throw new IOException("Owned VPN stopped before the normal STOP request");
    stopDispatch=call("stop",generation);if(requireRunning&&(!Boolean.TRUE.equals(stopDispatch.opt("stopDispatched"))||stopDispatch.optLong("stopGeneration")!=generation))throw new IOException("Actual normal STOP dispatch was not confirmed");stopRequested=true;note("owned-stop-dispatch",stopDispatch);
  }
  synchronized void abort(){if(aborted)return;aborted=true;session.handler.removeCallbacks(watchOwner);worker.execute(()->{try{
    // START is delivered asynchronously in the other process. Even when this
    // command retires before the first generation reply, stop only its actual
    // matching service generation once that start becomes observable.
    long deadline=SystemClock.elapsedRealtime()+5000;
    while(SystemClock.elapsedRealtime()<deadline){
      JSONObject response=call("state",-1),state=response.getJSONObject("state");
      long observed=cleanupGeneration(state,nonce,source,generation);
      if(observed>0){generation=observed;stopOwned(false);JSONObject after=call("state",generation),actual=after.getJSONObject("state");if(QueuedChangesVpnProvider.matches(actual,nonce,source,generation)&&Boolean.FALSE.equals(actual.opt("running"))&&Boolean.TRUE.equals(actual.opt("fdCloseSucceeded"))){cleanupConfirmed=true;note("owner-safe-abort-descriptor-closed",after);return;}}
      Thread.sleep(50);
    }
    cleanupFailure="Owned START/descriptor cleanup was not confirmed within its separate 5000ms cleanup budget";note("abort-cleanup-unconfirmed",J.obj("error",cleanupFailure));
  }catch(Exception error){cleanupFailure=error.toString();note("abort-cleanup-unconfirmed",J.obj("error",cleanupFailure));}});}
  void fail(Exception error){failure=error.toString();note("failure",J.obj("message",failure));abort();session.handler.post(()->{if(activity.run==command&&activity.session==session)activity.event(command,"error",J.obj("error",failure,"stage","queued-real-vpn","queuedVpn",report()));});}
  JSONObject report(){synchronized(events){return J.obj("scope","Actual integration-only non-forwarding full TUN, unchanged CM and guard, same-process owner-bound IPC; no public path or physical-phone acceptance","sourceCommit",source,"runNonce",nonce,"serviceGeneration",generation,"environmentId",environment,"environmentGeneration",environmentGeneration,"processSlot",activity.slot,"command",command,"actualAndroidExecution",true,"physicalPhoneAcceptance",false,"beganAt",beganAt,"stopBudgetStarted",stopBudgetStarted,"originalCheckBudgetMillis",3500,"ownerWatchBudgetMillis",20000,"originalRouteAdmission",admission,"expectedCandidate",expectedCandidate,"appliedObserved",appliedObserved,"closedObserved",closedObserved,"failure",failure,"abortCleanupConfirmed",cleanupConfirmed,"abortCleanupFailure",cleanupFailure,"events",J.parse(J.obj("rows",events).toString()).optJSONArray("rows"));}}
  JSONObject attach(JSONObject result){NetworkCatalog.put(result,"queuedVpnLifecycle",report());return result;}
}
