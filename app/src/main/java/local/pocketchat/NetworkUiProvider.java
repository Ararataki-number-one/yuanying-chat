package local.pocketchat;

import android.content.*;import android.database.Cursor;import android.net.Uri;import android.os.*;
import org.json.*;import java.util.*;import java.util.concurrent.*;import java.nio.charset.StandardCharsets;

/** Private UI-to-profile bridge. Each provider runs in the existing profile's own process. */
public class NetworkUiProvider extends ContentProvider {
  Context profile;AppUpdateRoute.Server updateRoutes;final Handler main=new Handler(Looper.getMainLooper());final Map<String,JSONObject> jobs=new ConcurrentHashMap<>();boolean applying,saving,drainReading;volatile boolean maintenanceStopped;long drainRevision,saveRevision;String activeApply="";volatile String modelProof="";volatile Transition activeTransition;final Runnable drain=()->{pruneJobs();observeSession();drainPending();main.postDelayed(this.drain,1000);};final ExecutorService io=Executors.newSingleThreadExecutor();
  static final long JOB_RETENTION=300000;static final int MAX_JOBS=128;
  final NetworkApplyRetry retry=new NetworkApplyRetry();final Map<String,RequestBinding> bindings=new HashMap<>();
  ChatSession observedSession;final ChatSession.Observer sessionObserver=this::sessionChanged;final Runnable pendingWake=this::drainPending;
  static final class RequestBinding {
    final EnvironmentSpec.Identity identity;final String snapshot;final NetworkApplicationReceipt receipt;final boolean saveRequest;JSONObject outcome;
    RequestBinding(EnvironmentSpec.Identity identity,String snapshot){this(identity,snapshot,null,false);}
    RequestBinding(EnvironmentSpec.Identity identity,String snapshot,NetworkApplicationReceipt receipt){this(identity,snapshot,receipt,true);}
    RequestBinding(EnvironmentSpec.Identity identity,String snapshot,NetworkApplicationReceipt receipt,boolean saveRequest){this.identity=identity;this.snapshot=snapshot;this.receipt=receipt;this.saveRequest=saveRequest;}
    String key(){return identity.environmentId+":"+identity.generation+":"+NativeNetwork.hash(snapshot);}
  }
  static boolean internalJob(String id){return id.startsWith("internal:");}
  void pruneJobs(){long now=SystemClock.elapsedRealtime();jobs.entrySet().removeIf(row->row.getValue().optBoolean("done")&&row.getValue().has("finishedAt")&&now-row.getValue().optLong("finishedAt")>=JOB_RETENTION);}
  void recordResult(String id,boolean ok,String message){recordResult(id,ok,message,null);}
  void recordResult(String id,boolean ok,String message,JSONObject operationResult){
    if(internalJob(id)){jobs.remove(id);return;}
    // Binder admission may prune concurrently with a main-thread completion.
    // Update only an extant receipt atomically; a retired ID can never reappear.
    final JSONObject frozen=operationResult==null?new JSONObject():J.parse(operationResult.toString());
    jobs.computeIfPresent(id,(key,old)->old.optBoolean("done")?old:J.obj("done",true,"ok",ok,"message",message,"finishedAt",SystemClock.elapsedRealtime(),"operationResult",frozen,"recoveryRequired",frozen.optBoolean("recoveryRequired")));
  }
  void observeSession(){ChatSession current=ChatSession.peek();if(current==observedSession)return;if(observedSession!=null)observedSession.remove(sessionObserver);observedSession=current;if(current!=null)current.add(sessionObserver);}
  void sessionChanged(){
    ChatSession session=observedSession;if(session==null||session.deleted||maintenanceStopped)return;
    boolean idle=session.pending==null&&!session.submitting&&!session.transferActive&&!session.fileWorkActive()&&!session.connecting&&!session.navigating&&!session.recoveryScheduled&&!session.state.optBoolean("busy");
    boolean page=session.stateEpoch==session.navigationEpoch&&WebReplyObserver.same(session.web.getUrl(),session.state.optString("url"))&&!session.state.optString("documentId").isEmpty()&&session.state.optString("error").isEmpty();
    String event=session.environmentId+":"+session.environmentGeneration+":"+session.navigationEpoch+":"+session.resourceObserverBinding+":"+session.lastDocumentId;
    if(retry.observePage(event,idle,page,session.state.optBoolean("composer"))){main.removeCallbacks(pendingWake);main.post(pendingWake);}
  }
  public static class Profile1 extends NetworkUiProvider{}public static class Profile2 extends NetworkUiProvider{}public static class Profile3 extends NetworkUiProvider{}public static class Profile4 extends NetworkUiProvider{}public static class Profile5 extends NetworkUiProvider{}public static class Profile6 extends NetworkUiProvider{}public static class Profile7 extends NetworkUiProvider{}
  @Override public boolean onCreate(){profile=Profiles.context(getContext(),Profiles.processSlot());updateRoutes=new AppUpdateRoute.Server(profile);main.post(drain);return true;}
  @Override public Bundle call(String method,String arg,Bundle extras){
    if(Binder.getCallingUid()!=android.os.Process.myUid())throw new SecurityException();Bundle result=new Bundle();
    if("stopForDelete".equals(method)||"stopForReset".equals(method)){
      if(!ProfileCatalog.get(profile).item(Profiles.slot(profile)).optBoolean("stopForReset".equals(method)?"resetting":"deleting"))throw new IllegalStateException();
      java.util.concurrent.CountDownLatch stopped=new java.util.concurrent.CountDownLatch(1);java.util.concurrent.atomic.AtomicBoolean confirmed=new java.util.concurrent.atomic.AtomicBoolean();main.post(()->{maintenanceStopped=true;main.removeCallbacks(drain);main.removeCallbacks(pendingWake);if(observedSession!=null)observedSession.remove(sessionObserver);retry.clear();bindings.clear();jobs.clear();drainRevision++;saveRevision++;Transition transition=activeTransition;if(transition!=null)transition.cancelled=true;ChatSession s=ChatSession.peek();if(s!=null){s.deleted=true;s.handler.removeCallbacks(s.tick);s.guard.setBlocked(true);ChatService.end(profile);s.web.destroy();}NativeNetwork n=NativeNetwork.get(profile);n.cancelMaintenance();io.execute(()->n.worker.execute(()->{try{confirmed.set(n.stopNow());}finally{stopped.countDown();}}));});
      try{if(!stopped.await(20,java.util.concurrent.TimeUnit.SECONDS))throw new IllegalStateException("停止环境超时");}catch(InterruptedException e){Thread.currentThread().interrupt();throw new IllegalStateException(e);}if(!confirmed.get()||NativeNetwork.get(profile).coreAlive())throw new IllegalStateException("独立网络尚未停止，请重试删除");result.putBoolean("stopped",true);return result;
    }
    if(maintenanceStopped||!ProfileCatalog.get(profile).available(Profiles.slot(profile))){result.putInt("slot",Profiles.slot(profile));result.putBoolean("ready",false);result.putBoolean("valid",false);result.putString("message","此环境正在维护，完成后可重新打开");result.putString("json",J.obj("connected",false,"done",true,"ok",false,"message","此环境正在维护").toString());return result;}
    if("updateRoute".equals(method)||"validateUpdateRoute".equals(method))return updateRoutes.response(extras,"validateUpdateRoute".equals(method));
    if("state".equals(method)){NativeNetwork n=NativeNetwork.get(profile);JSONObject state=WindowNetworkState.live(ChatSession.peek(),n);NetworkCatalog.put(state,"configurationHash",NetworkChanges.hash(profile));result.putString("json",state.toString());return result;}
    if("job".equals(method)){JSONObject status=jobs.get(arg);result.putString("json",status==null?J.obj("done",true,"ok",false,"message","操作记录已过期").toString():status.toString());return result;}
    if(!"start".equals(method))throw new IllegalArgumentException();String action=extras==null?"":extras.getString("action","");JSONObject candidate=J.parse(extras==null?"{}":extras.getString("config","{}"));String baseline=extras==null?"":extras.getString("baseline","");
    final EnvironmentSpec.Identity expected;
    try{if(extras!=null&&extras.containsKey("expectedIdentity")){JSONObject value=new JSONObject(extras.getString("expectedIdentity",""));expected=new EnvironmentSpec.Identity(value.getInt("slot"),value.getInt("generation"),value.getString("environmentId"));EnvironmentSpecRuntime.requireIdentity(profile,expected);}else expected=null;}
    catch(Exception changed){result.putString("json",J.obj("done",true,"ok",false,"message","此环境已改变，请重新打开网络设置").toString());return result;}
    String id=UUID.randomUUID().toString();synchronized(jobs){pruneJobs();if(jobs.size()>=MAX_JOBS){result.putString("json",J.obj("done",true,"ok",false,"message","操作较多，请稍后重试；当前设置未改变").toString());return result;}jobs.put(id,J.obj("done",false));}main.post(()->request(id,action,candidate,baseline,false,-1,"",expected));result.putString("id",id);return result;
  }
  void finish(String id,boolean ok,String message){if(maintenanceStopped)return;if(Looper.myLooper()!=Looper.getMainLooper()){main.post(()->finish(id,ok,message));return;}RequestBinding binding=bindings.get(id);if(binding!=null)binding.outcome=operationOutcome(binding,activeTransition,id,message);if(id.equals(activeApply)){Transition transition=activeTransition;if(transition!=null&&transition.confirmed&&!transition.pendingReleased){transition.pendingReleased=true;io.execute(()->{try{NetworkChanges.clearIfCurrent(profile,transition.expectedPendingSnapshot);}catch(Exception ignored){}main.post(()->finish(id,ok,message));});return;}applying=false;activeApply="";if(transition!=null){releaseCapture(transition,!transition.confirmed);transition.cancelled=true;activeTransition=null;}ChatSession s=ChatSession.peek();if(s!=null){if(transition==null)s.operation=false;s.changed();}}WindowNetworkState.save(profile,ChatSession.peek(),NativeNetwork.get(profile));recordResult(id,ok,message,binding==null?null:binding.outcome);bindings.remove(id);}
  static JSONObject operationOutcome(RequestBinding binding,Transition transition,String id,String message){
    if(binding==null||!binding.saveRequest)return null;if(binding.outcome!=null)return binding.outcome;
    if(binding.receipt==null)return NetworkApplicationReceipt.failed(binding.identity,message);
    if(transition!=null&&id.equals(transition.id)){
      if(transition.cancellationConfirmed)return binding.receipt.cancelled(message);
      if(transition.cancelledByUser)return binding.receipt.unconfirmed("session",message);
      if(transition.confirmed)return binding.receipt.unconfirmed(transition.session==null?"next-session":"session",message);
    }
    return binding.receipt.pending(message);
  }
  boolean busy(ChatSession s,NativeNetwork n){return applying||n!=null&&(n.starting||n.measuringLatency)||s==null&&J.parse(profile.getSharedPreferences("chat",0).getString("pending","{}")).length()>0||s!=null&&(ProfileUi.working(s)||s.connecting);}
  void request(String id,String action,JSONObject candidate,String baseline){request(id,action,candidate,baseline,false);}
  void request(String id,String action,JSONObject candidate,String baseline,boolean deferred){request(id,action,candidate,baseline,deferred,-1,"");}
  void request(String id,String action,JSONObject candidate,String baseline,boolean deferred,int generation,String pendingSnapshot){request(id,action,candidate,baseline,deferred,generation,pendingSnapshot,null);}
  void request(String id,String action,JSONObject candidate,String baseline,boolean deferred,int generation,String pendingSnapshot,EnvironmentSpec.Identity readIdentity){
    if(maintenanceStopped||!ProfileCatalog.get(profile).available(Profiles.slot(profile))){finish(id,false,"此环境正在维护");return;}drainRevision++;
    final EnvironmentSpec.Identity expected;try{expected=readIdentity==null?ProfileCatalog.get(profile).identity(Profiles.slot(profile)):readIdentity;EnvironmentSpecRuntime.requireIdentity(profile,expected);if(generation>=0&&generation!=expected.generation)throw new java.io.IOException("此环境已删除或重新创建");}catch(Exception invalid){finish(id,false,invalid.getMessage());return;}
    bindings.put(id,new RequestBinding(expected,"",null,"apply".equals(action)||"external".equals(action)));
    if(!"apply".equals(action)&&!"external".equals(action)){operate(id,action,candidate,baseline);return;}
    long requestRevision=++saveRevision;saving=true;
    if(!deferred){modelProof="";retry.clear();}
    io.execute(()->{
      String error="",receipt="";NetworkApplicationReceipt savedResult=null;boolean superseded=false,sameGeneration=false,uncertain=false;final String[] capturedSnapshot={""};final NetworkApplicationReceipt[] capturedResult={null};final boolean[] replaced={false};try{
        JSONObject row=ProfileCatalog.get(profile).item(Profiles.slot(profile));sameGeneration=generation<0||generation==row.optInt("generation");
        EnvironmentSpecRuntime.requireIdentity(profile,expected);if(!row.optBoolean("created")||!sameGeneration)throw new java.io.IOException("此环境已删除或重新创建");
        // Save/reuse and its frozen model receipt share the existing intent lease.
        EnvironmentSpecRuntime.withIntent(profile,()->{
        // A queued read must not put an older candidate back after a newer save.
        if(deferred){replaced[0]=!EnvironmentSpecRuntime.reuseNetworkIntent(profile,expected,action,candidate,baseline,pendingSnapshot);if(!replaced[0])capturedSnapshot[0]=pendingSnapshot;}
        else{if(!baseline.equals(NetworkChanges.hash(profile)))throw new java.io.IOException("此窗口配置已变化，请重新编辑");
          NetworkChanges.validate(profile,action,candidate);Transition parent=activeTransition;JSONObject lineage=parent!=null&&!parent.confirmed&&!parent.publishedHash.isEmpty()&&parent.identity.equals(expected)&&baseline.equals(parent.publishedHash)?NetworkChanges.lineage(parent.id,parent.publishedHash,parent.baseline,parent.generation):new JSONObject();capturedSnapshot[0]=EnvironmentSpecRuntime.saveNetworkIntent(profile,expected,action,candidate,baseline,lineage);}
        if(!replaced[0])capturedResult[0]=captureSaved(expected,capturedSnapshot[0]);return null;});
        superseded=replaced[0];receipt=capturedSnapshot[0];savedResult=capturedResult[0];
      }catch(Exception e){receipt=capturedSnapshot[0];savedResult=capturedResult[0];error=!receipt.isEmpty()?"配置已保存，但版本回执暂时无法读取；可在网络面板重新检查":e.getMessage()==null?"配置未能保存":e.getMessage();uncertain=e instanceof EnvironmentSpecRuntime.IntentRecoveryRequired;}
      String observedCandidate="";if(!receipt.isEmpty())try{JSONObject pending=J.parse(receipt),marker=NetworkChanges.intent(pending);observedCandidate=marker==null?"legacy:"+NativeNetwork.hash(receipt):marker.optString("id");}catch(Exception unreadable){/* A successful write remains saved even if its version/marker cannot be reread. */}
      String failure=error,savedReceipt=receipt,savedCandidateId=observedCandidate;NetworkApplicationReceipt application=savedResult;boolean wasReplaced=superseded,recoveryRequired=uncertain;main.post(()->{
        // A newer save owns this flag and its pending candidate. Older completion
        // must neither clear that candidate nor switch back to an older route.
        if(requestRevision!=saveRevision){recordResult(id,true,"已由较新的网络设置替换",application==null?NetworkApplicationReceipt.supersededUnknown(expected,"保存状态已由较新操作替换"):application.superseded("已由较新的网络设置替换"));bindings.remove(id);return;}
        saving=false;if(wasReplaced){jobs.remove(id);bindings.remove(id);return;}if(!failure.isEmpty()){RequestBinding failedBinding=bindings.get(id);if(failedBinding!=null){if(!savedReceipt.isEmpty()){failedBinding.outcome=NetworkApplicationReceipt.savedUnconfirmed(expected,savedCandidateId,failure);}else if(recoveryRequired)failedBinding.outcome=NetworkApplicationReceipt.uncertain(expected,failure);}if(deferred){retry.defer(new RequestBinding(expected,pendingSnapshot).key(),recoveryRequired?"等待存储恢复":"待应用设置需要检查",SystemClock.elapsedRealtime());ChatSession waiting=ChatSession.peek();if(waiting!=null)waiting.setStatus(recoveryRequired?failure:"已保存的网络设置暂未应用："+failure);}finish(id,false,failure);return;}
        bindings.put(id,new RequestBinding(expected,savedReceipt,application));
        ChatSession s=ChatSession.peek();NativeNetwork n=NativeNetwork.get(profile);
        if(saving||busy(s,n)||s!=null&&(s.navigating||s.state.optBoolean("busy"))){retry.defer(bindings.get(id).key(),"等待回复和文件操作结束",SystemClock.elapsedRealtime());finish(id,true,"网络设置已保存，当前回复和文件操作结束后自动应用");return;}
        operate(id,action,candidate,baseline);
      });
    });
  }
  NetworkApplicationReceipt captureSaved(EnvironmentSpec.Identity expected,String snapshot)throws Exception{
    EnvironmentSpecRuntime.requireIdentity(profile,expected);JSONObject pending=NetworkChanges.pendingStrict(profile);
    if(snapshot.isEmpty()||!snapshot.equals(pending.toString())||!NetworkChanges.identityMatches(pending,expected.json()))throw new java.io.IOException("保存结果已变化，请重新读取网络设置");
    JSONObject marker=NetworkChanges.intent(pending),config=pending.getJSONObject("config");String candidateId=marker==null?"legacy:"+NativeNetwork.hash(snapshot):marker.getString("id");
    String mode="external".equals(pending.optString("action"))?"external":"internal";
    EnvironmentSpec model=new EnvironmentSpecRepository(profile).load();NetworkApplicationReceipt result=NetworkApplicationReceipt.saved(expected,candidateId,model,EnvironmentSpecRuntime.binding(expected,mode,config,"external".equals(mode)?config.optString("proxy"):""));
    EnvironmentSpecRuntime.requireIdentity(profile,expected);return result;
  }
  void operate(String id,String action,JSONObject candidate,String baseline){
    ChatSession s=ChatSession.peek();NativeNetwork n=NativeNetwork.get(profile);
    if(maintenanceStopped||!ProfileCatalog.get(profile).available(Profiles.slot(profile))){finish(id,false,"此环境已删除");return;}
    if("cancelPending".equals(action)){cancelPending(id,candidate);return;}
    if("measure".equals(action)){if("internal".equals(profile.getSharedPreferences("chat",0).getString("networkMode","external")))n.measureLatency((ok,msg)->finish(id,ok,msg));else if(s!=null)NetworkRegion.refreshLatency(s,(ok,msg)->finish(id,ok,msg));else finish(id,false,"请先打开此窗口的会话后测量连接响应");return;}
    if(busy(s,n)){finish(id,false,"当前回复继续进行，网络配置可以先编辑保存");return;}
    if("verify".equals(action)){if(!n.ready){finish(id,false,"请先连接此窗口，再核验出口");return;}applying=true;activeApply=id;if(s!=null)s.operation=true;n.checkExit((ok,msg)->finish(id,ok,msg));return;}
    if("reconnect".equals(action)){if(s!=null){s.reconnect();waitConnection(id,s,n,false,SystemClock.elapsedRealtime());}else if("internal".equals(profile.getSharedPreferences("chat",0).getString("networkMode","external")))n.restart((ok,msg)->finish(id,ok,msg));else finish(id,false,"打开此窗口的会话后可重连手机网络");return;}
    if("apply".equals(action)||"external".equals(action)){beginTransition(id,action,candidate,baseline);return;}
    finish(id,false,"未知网络操作");
  }
  /** Cancellation and confirmation share the main actor; storage work stays on IO. */
  void cancelPending(String id){cancelPending(id,null);}
  void cancelPending(String id,JSONObject candidate){
    final EnvironmentSpec.Identity expected;try{RequestBinding binding=bindings.get(id);expected=binding==null?ProfileCatalog.get(profile).identity(Profiles.slot(profile)):binding.identity;}catch(Exception invalid){finish(id,false,invalid.getMessage());return;}
    final boolean guarded=candidate!=null&&candidate.has("guardCandidateId");final String expectedCandidate=guarded?candidate.optString("guardCandidateId"):"";final long observedRevision=saveRevision;
    io.execute(()->{String error="",snapshot="";try{snapshot=EnvironmentSpecRuntime.withIntent(profile,()->{
      EnvironmentSpecRuntime.requireIdentity(profile,expected);JSONObject pending=NetworkChanges.pendingStrict(profile),marker=NetworkChanges.intent(pending);String current=marker==null?pending.length()==0?"":"legacy:"+NativeNetwork.hash(pending.toString()):marker.optString("id");
      if(guarded&&!expectedCandidate.equals(current))throw new java.io.IOException("待应用设置已变化，请重新打开后取消");return pending.toString();
    });}catch(Exception failure){error="待应用设置未能确认，当前配置保持不变";}
      final String failure=error,captured=snapshot;main.post(()->{if(!failure.isEmpty()){finish(id,false,failure);return;}if(observedRevision!=saveRevision){finish(id,false,"待应用设置已变化，请重新打开后取消");return;}cancelCaptured(id,expected,captured);});
    });
  }
  void cancelCaptured(String id,EnvironmentSpec.Identity expected,String snapshot){
    ++saveRevision;saving=false;retry.clear();Transition current=activeTransition;final Transition transition=current!=null&&snapshot.equals(current.expectedPendingSnapshot)?current:null;
    modelProof="";
    if(transition!=null&&!transition.confirmed){transition.cancelledByUser=true;transition.cancelled=true;}
    io.execute(()->{String error="";try{
      EnvironmentSpecRuntime.withIntent(profile,()->{EnvironmentSpecRuntime.requireIdentity(profile,expected);if(!snapshot.equals(NetworkChanges.pendingStrict(profile).toString()))throw new java.io.IOException("待应用设置已变化，请重新打开后取消");if(transition!=null&&transition.cancelledByUser){rollbackTransition(transition);if(transition.rollbackFailed)throw new java.io.IOException("原网络设置未能完整恢复，请重新编辑网络");}if(!EnvironmentSpecRuntime.cancelNetworkIntent(profile,expected,snapshot))throw new java.io.IOException("待应用设置已变化，请重新检查");return null;});
    }catch(Exception failure){error=failure.getMessage()==null?"待应用网络设置未能取消":failure.getMessage();}
      String failure=error;main.post(()->{if(transition!=null&&transition.cancelledByUser&&activeTransition==transition){transition.cancellationConfirmed=failure.isEmpty();deferTransition(transition);}finish(id,failure.isEmpty(),failure.isEmpty()?"待应用设置已取消，当前连接保持不变":failure);});
    });
  }
  void drainPending(){
    if(maintenanceStopped||drainReading||saving||applying)return;
    ChatSession s=ChatSession.peek();
    if(busy(s,null)||s!=null&&(s.deleted||s.navigating||s.recoveryScheduled||s.state.optBoolean("busy")))return;
    drainReading=true;long revision=drainRevision;
    io.execute(()->{
      JSONObject readRow=new JSONObject(),readQueued=new JSONObject();EnvironmentSpec.Identity readIdentity=null;try{readRow=ProfileCatalog.get(profile).item(Profiles.slot(profile));if(readRow.optBoolean("created")){EnvironmentSpec.Identity identity=ProfileCatalog.get(profile).identity(Profiles.slot(profile));if(!identity.environmentId.equals(readRow.optString("environmentId"))||identity.generation!=readRow.optInt("generation"))throw new java.io.IOException("环境已变化");readIdentity=identity;EnvironmentSpecRuntime.Reconciled current=EnvironmentSpecRuntime.reconcileNetwork(profile,identity,modelProof);modelProof=current.proof;readQueued=current.pending;}}catch(Exception unavailable){/* No apply is admitted until the authoritative intent/model can be reconciled. Retry quietly. */}
      JSONObject row=readRow,queued=readQueued;EnvironmentSpec.Identity identity=readIdentity;
      main.post(()->{
        drainReading=false;if(revision!=drainRevision||identity==null||!row.optBoolean("created")||queued.length()==0||saving||applying)return;if(!retry.due(new RequestBinding(identity,queued.toString()).key(),SystemClock.elapsedRealtime()))return;
        ChatSession current=ChatSession.peek();NativeNetwork network=NativeNetwork.get(profile);
        if(busy(current,network)||current!=null&&(current.deleted||current.environmentGeneration!=identity.generation||!current.environmentId.equals(identity.environmentId)||current.navigating||current.recoveryScheduled||current.state.optBoolean("busy")))return;
        String id="internal:"+UUID.randomUUID();
        request(id,queued.optString("action"),queued.optJSONObject("config"),queued.optString("baseline"),true,identity.generation,queued.toString(),identity);
      });
    });
  }
  static final class Transition {
    final String id,action,baseline;final JSONObject candidate;final ChatSession session;final EnvironmentSpec.Identity identity;final int generation;final long revision;String waitReason="等待回复和文件操作结束";
    String url="",scope="",preparedProof="",expectedPendingSnapshot="",oldMode="external",oldEntry="",oldProxy="";long epoch;JSONObject page;boolean oldConfigured,oldVpn,capture,fenced,confirmed,pendingReleased,previousBlocked,rollbackFailed,cancellationConfirmed;
    volatile boolean cancelled,cancelledByUser;boolean rollbackComplete;volatile String publishedHash="";NetworkSourceSelection.ActiveSnapshot transaction;android.view.View.OnTouchListener previousTouch,touchFence;android.view.View keyTarget;
    Transition(String id,String action,JSONObject candidate,String baseline,ChatSession session,EnvironmentSpec.Identity identity,long revision){this.identity=identity;this.id=id;this.action=action;this.candidate=J.parse(candidate.toString());this.baseline=baseline;this.session=session;this.generation=identity.generation;this.revision=revision;}
  }
  static final class DeferredTransition extends Exception {}
  void beginTransition(String id,String action,JSONObject candidate,String baseline){
    RequestBinding binding=bindings.get(id);if(binding==null){finish(id,false,"保存回执不可用，请重新检查配置");return;}Transition transition=new Transition(id,action,candidate,baseline,ChatSession.peek(),binding.identity,saveRevision);transition.expectedPendingSnapshot=binding.snapshot;applying=true;activeApply=id;activeTransition=transition;
    // Preparation never suppresses the real webpage's send observer or polling.
    io.execute(()->prepareTransition(transition));
  }
  static String proof(NetworkSourceSelection.Sources sources){return NetworkSourceSelection.payloadHash(sources.entryBytes)+":"+(sources.exitBytes==null?"manual":NetworkSourceSelection.payloadHash(sources.exitBytes));}
  void prepareTransition(Transition transition){
    try{
      if(transition.cancelled)throw new DeferredTransition();EnvironmentSpecRuntime.requireIdentity(profile,transition.identity);if(!transition.baseline.equals(NetworkChanges.hash(profile)))throw new java.io.IOException("此窗口配置已变化，请重新编辑");JSONObject pending=NetworkChanges.pendingStrict(profile);if(!transition.expectedPendingSnapshot.equals(pending.toString())||pending.length()==0||!transition.action.equals(pending.optString("action"))||!transition.baseline.equals(pending.optString("baseline"))||!transition.candidate.toString().equals(String.valueOf(pending.optJSONObject("config"))))throw new DeferredTransition();transition.expectedPendingSnapshot=pending.toString();
      if("apply".equals(transition.action))NetworkChanges.withSavedSources(profile,pending,sources->{transition.preparedProof=proof(sources);return null;});
      else NetworkChanges.validate(profile,transition.action,transition.candidate);
      main.post(()->captureTransition(transition));
    }catch(Exception error){main.post(()->{if(error instanceof DeferredTransition)deferTransition(transition);else failTransition(transition,error);});}
  }
  void requirePending(Transition transition)throws Exception{if(maintenanceStopped||transition.cancelled||transition.expectedPendingSnapshot.isEmpty()||!transition.expectedPendingSnapshot.equals(NetworkChanges.pendingStrict(profile).toString()))throw new DeferredTransition();EnvironmentSpecRuntime.requireIdentity(profile,transition.identity);if(!transition.baseline.equals(NetworkChanges.hash(profile)))throw new java.io.IOException("此窗口配置已变化，请重新编辑");}
  boolean owns(Transition transition){return !transition.cancelled&&activeTransition==transition&&transition.id.equals(activeApply)&&transition.revision==saveRevision;}
  boolean currentEnvironment(Transition transition){JSONObject row=ProfileCatalog.get(profile).item(Profiles.slot(profile));return row.optBoolean("created")&&!row.optBoolean("deleting")&&!row.optBoolean("resetting")&&row.optInt("generation")==transition.generation&&row.optString("environmentId").equals(transition.identity.environmentId)&&(transition.session==null||transition.session.environmentGeneration==transition.generation&&transition.session.environmentId.equals(transition.identity.environmentId));}
  boolean fenceIdle(Transition transition){
    if(!owns(transition)||saving||!currentEnvironment(transition)||ChatSession.peek()!=transition.session)return false;NativeNetwork network=NativeNetwork.get(profile);if(network.starting||network.measuringLatency)return false;ChatSession session=transition.session;
    if(session==null)return J.parse(profile.getSharedPreferences("chat",0).getString("pending","{}")).length()==0;
    if(session.deleted||session.pending!=null||session.submitting||session.transferActive||session.fileWorkActive()||session.connecting||session.navigating||session.recoveryScheduled||session.operation&&!transition.capture)return false;
    if(transition.capture&&(transition.epoch!=session.navigationEpoch||!(MainActivity.chatUrl(transition.url)?WebReplyObserver.same(transition.url,session.web.getUrl()):BrowserRuntimePolicy.sameDocument(transition.url,session.web.getUrl()))||!transition.scope.equals(session.pageMemory.scope())))return false;
    return !session.state.optBoolean("busy");
  }
  void captureTransition(Transition transition){
    if(!fenceIdle(transition)){deferTransition(transition);return;}ChatSession session=transition.session;
    if(session==null){io.execute(()->commitTransition(transition));return;}
    transition.url=session.web.getUrl();transition.epoch=session.navigationEpoch;transition.scope=session.pageMemory.scope();session.operation=true;session.configurationCapture=true;transition.capture=true;
    if(!MainActivity.chatUrl(transition.url)){io.execute(()->commitTransition(transition));return;}
    session.asyncDriver("inspect",J.obj("expectedUrl",transition.url),2500,inspected->{
      if(!inspectionIdle(transition,inspected,null)){transition.waitReason=inspected.optBoolean("busy")?"等待回复和文件操作结束":"等待网页恢复";deferTransition(transition);return;}
      session.asyncDriver("page-state",J.obj("expectedUrl",transition.url),2500,state->{
        if(!fenceIdle(transition)||!PageMemory.completeDraft(state)||!WebReplyObserver.same(transition.url,state.optString("url"))||!state.optString("draft").equals(inspected.optString("draft"))||!state.optString("documentId").equals(inspected.optString("documentId"))){transition.waitReason="等待网页草稿完整可读";deferTransition(transition);return;}
        if(PageMemory.hasDraft(state)&&!LocalDraftPolicy.enabled(session.context)){transition.waitReason="等待发送或清空网页草稿（本机草稿保存已关闭）";deferTransition(transition);return;}
        NetworkCatalog.put(state,"localDraftPolicyRevision",LocalDraftPolicy.revision(session.context));transition.page=state;session.pageMemory.remember(transition.scope,transition.url,state);session.web.checkpointState();
        session.webStore.worker.execute(()->{boolean saved=DraftArchive.get(session.context).save(transition.url,state.optString("draft"),"应用网络设置前的草稿",state.optLong("localDraftPolicyRevision",-1));main.post(()->{
          if(!saved||PageMemory.hasDraft(state)&&!LocalDraftPolicy.enabled(session.context)||!fenceIdle(transition)){if(!saved)transition.waitReason=LocalDraftPolicy.unavailable(session.context);deferTransition(transition);return;}
          session.asyncDriver("inspect",J.obj("expectedUrl",transition.url),2500,fresh->{if(!inspectionIdle(transition,fresh,state)){transition.waitReason="等待网页稳定";deferTransition(transition);return;}io.execute(()->commitTransition(transition));});
        });});
      });
    });
  }
  boolean inspectionIdle(Transition transition,JSONObject inspected,JSONObject page){return fenceIdle(transition)&&WebReplyObserver.same(transition.url,inspected.optString("url"))&&!inspected.optBoolean("busy")&&inspected.optString("draftRaw").length()<=300000&&(page==null||page.optString("draft").equals(inspected.optString("draft"))&&page.optString("documentId").equals(inspected.optString("documentId")));}
  /** The source/private leases wait only for this short main-thread state check, never HTTP or JS. */
  void commitGate(Transition transition)throws Exception{
    CountDownLatch gate=new CountDownLatch(1);java.util.concurrent.atomic.AtomicBoolean admitted=new java.util.concurrent.atomic.AtomicBoolean(),waiting=new java.util.concurrent.atomic.AtomicBoolean(true);
    main.post(()->{try{if(!waiting.get()||!fenceIdle(transition))return;ChatSession session=transition.session;if(session!=null&&PageMemory.hasDraft(transition.page)&&(!LocalDraftPolicy.enabled(session.context)||transition.page.optLong("localDraftPolicyRevision",-1)!=LocalDraftPolicy.revision(session.context)))return;if(session!=null){transition.previousBlocked=session.guard.blocked;transition.previousTouch=session.web.touches;transition.touchFence=(view,event)->true;session.web.cancelPendingInputEvents();session.web.setOnTouchListener(transition.touchFence);if(session.web.surface!=null){transition.keyTarget=session.web.surface;transition.keyTarget.cancelPendingInputEvents();transition.keyTarget.setOnKeyListener((view,key,event)->true);}session.guard.setBlocked(true);}transition.fenced=true;admitted.set(true);}finally{gate.countDown();}});
    if(!gate.await(3,TimeUnit.SECONDS)){waiting.set(false);throw new DeferredTransition();}waiting.set(false);if(!admitted.get())throw new DeferredTransition();
    if(transition.cancelled||transition.session!=null&&transition.session.pending!=null)throw new DeferredTransition();
  }
  void commitTransition(Transition transition){
    SharedPreferences preferences=profile.getSharedPreferences("chat",0);SecretStore vault=new SecretStore(profile);
    try{
      if(!transition.baseline.equals(NetworkChanges.hash(profile)))throw new java.io.IOException("此窗口配置已变化，请重新编辑");
      if("apply".equals(transition.action))NetworkChanges.withSavedSources(profile,J.parse(transition.expectedPendingSnapshot),sources->{
        if(!transition.preparedProof.equals(proof(sources)))throw new DeferredTransition();
        return NetworkSourceSelection.withActiveSnapshot(profile,()->{requirePending(transition);snapshotPreferences(transition,preferences);transition.transaction=new NetworkSourceSelection.ActiveSnapshot(vault);commitGate(transition);try{requirePending(transition);transition.transaction.write(sources,transition.candidate);if(!preferences.edit().putString("networkMode","internal").putBoolean("networkConfigured",true).putString("lastGoodEntry",transition.candidate.optString("entry").isEmpty()?transition.oldEntry:transition.candidate.optString("entry")).commit())throw new java.io.IOException("网络配置未能保存");transition.publishedHash=NetworkChanges.hash(profile);}catch(Exception failure){try{transition.transaction.rollback();restorePreferences(transition);}catch(Exception restoration){transition.rollbackFailed=true;failure.addSuppressed(restoration);}throw failure;}return null;});
      });
      else NetworkSourceSelection.withActiveSnapshot(profile,()->{requirePending(transition);snapshotPreferences(transition,preferences);commitGate(transition);try{requirePending(transition);if(!preferences.edit().putString("networkMode","external").putBoolean("networkConfigured",true).putString("proxy",transition.candidate.optString("proxy")).putBoolean("requireExternalVpn",transition.candidate.optBoolean("requireExternalVpn",true)).commit())throw new java.io.IOException("网络方式未能保存");transition.publishedHash=NetworkChanges.hash(profile);}catch(Exception failure){try{restorePreferences(transition);}catch(Exception restoration){transition.rollbackFailed=true;failure.addSuppressed(restoration);}throw failure;}return null;});
      main.post(()->completeTransition(transition));
    }catch(Exception error){rollbackTransition(transition);main.post(()->{if(error instanceof DeferredTransition)deferTransition(transition);else failTransition(transition,error);});}
  }
  void snapshotPreferences(Transition transition,SharedPreferences preferences){transition.oldMode=preferences.getString("networkMode","external");transition.oldEntry=preferences.getString("lastGoodEntry","");transition.oldConfigured=preferences.getBoolean("networkConfigured",false);transition.oldProxy=preferences.getString("proxy","");transition.oldVpn=preferences.getBoolean("requireExternalVpn",true);}
  void restorePreferences(Transition transition)throws Exception{if(transition.fenced&&!profile.getSharedPreferences("chat",0).edit().putString("networkMode",transition.oldMode).putBoolean("networkConfigured",transition.oldConfigured).putString("lastGoodEntry",transition.oldEntry).putString("proxy",transition.oldProxy).putBoolean("requireExternalVpn",transition.oldVpn).commit())throw new java.io.IOException("原网络设置未能完整恢复");}
  void rollbackTransition(Transition transition){if(transition.rollbackComplete)return;try{NetworkSourceSelection.withActiveSnapshot(profile,()->{
    if(transition.transaction!=null)transition.transaction.rollback();
    else if(!transition.publishedHash.isEmpty()){String current=NetworkChanges.hash(profile);if(!current.equals(transition.publishedHash)&&!current.equals(transition.baseline))throw new java.io.IOException("网络设置已被更新，未覆盖较新的配置");}
    restorePreferences(transition);
    if(!transition.publishedHash.isEmpty())NetworkChanges.rebase(profile,NetworkChanges.lineage(transition.id,transition.publishedHash,transition.baseline,transition.generation));transition.rollbackComplete=true;return null;
  });}catch(Exception ignored){transition.rollbackFailed=true;/* A newer writer is never overwritten; the old live route is not stopped. */}}
  void completeTransition(Transition transition){
    if(maintenanceStopped)return;
    if(!fenceIdle(transition)){io.execute(()->{rollbackTransition(transition);main.post(()->deferTransition(transition));});return;}ChatSession session=transition.session;
    if(session!=null&&transition.page!=null){session.asyncDriver("inspect",J.obj("expectedUrl",transition.url),2500,fresh->{if(!inspectionIdle(transition,fresh,transition.page)){io.execute(()->{rollbackTransition(transition);main.post(()->deferTransition(transition));});return;}confirmTransition(transition);});}
    else confirmTransition(transition);
  }
  void confirmTransition(Transition transition){
    if(!fenceIdle(transition)){io.execute(()->{rollbackTransition(transition);main.post(()->deferTransition(transition));});return;}
    transition.confirmed=true;releaseCapture(transition,false);ChatSession session=transition.session;NativeNetwork network=NativeNetwork.get(profile);
    if("external".equals(transition.action))network.stop();
    // Reconnect is immediate on this same main turn, after the final live-state
    // fence. Releasing capture first lets the existing draft restoration run.
    if(session!=null){session.reconnect();waitConnection(transition.id,session,network,true,SystemClock.elapsedRealtime());}
    else if("apply".equals(transition.action))network.restart((ok,msg)->finish(transition.id,ok,ok?"配置已保存，打开此环境会话后确认应用":"配置已保存；核心连接尚未确认，打开会话后检查"));
    else finish(transition.id,true,"已保存，打开会话时应用手机网络");
  }
  void releaseCapture(Transition transition,boolean restoreGuard){ChatSession session=transition.session;if(session==null)return;if(transition.fenced&&session.web.touches==transition.touchFence)session.web.setOnTouchListener(transition.previousTouch);if(transition.keyTarget!=null){transition.keyTarget.setOnKeyListener(null);transition.keyTarget=null;}if(restoreGuard&&transition.fenced&&!transition.rollbackFailed&&!session.deleted&&!session.connecting&&ChatSession.peek()==session&&currentEnvironment(transition))session.guard.setBlocked(transition.previousBlocked);if(transition.capture&&activeTransition==transition){session.configurationCapture=false;session.operation=false;transition.capture=false;session.wakePolling();}}
  void deferTransition(Transition transition){if(activeTransition!=transition)return;if(transition.rollbackFailed){failTransition(transition,new java.io.IOException("网络设置恢复未完成，原网页未重新加载，请重新编辑网络"));return;}releaseCapture(transition,true);transition.cancelled=true;if(!transition.cancelledByUser)retry.defer(transition.identity.environmentId+":"+transition.identity.generation+":"+NativeNetwork.hash(transition.expectedPendingSnapshot),transition.waitReason,SystemClock.elapsedRealtime());finish(transition.id,true,transition.cancelledByUser?transition.cancellationConfirmed?"待应用设置已取消，当前连接保持不变":"取消结果尚未确认，请重新检查待应用设置":"网络设置已保存，"+transition.waitReason+"后自动应用");}
  void failTransition(Transition transition,Exception error){if(activeTransition!=transition)return;releaseCapture(transition,true);transition.cancelled=true;retry.defer(transition.identity.environmentId+":"+transition.identity.generation+":"+NativeNetwork.hash(transition.expectedPendingSnapshot),"待应用设置需要检查",SystemClock.elapsedRealtime());finish(transition.id,false,error.getMessage()==null?"网络设置未应用，原连接已保留":error.getMessage());}
  static void restore(SecretStore store,String slot,byte[] value)throws Exception{if(value==null)store.remove(slot);else store.put(slot,value);}
  /** One saved operation follows one session/connection lifetime. It never
   * treats a retained old route or a newer connection as its application. */
  static final class ApplicationAttempt {
    final String id;final ChatSession session;final NativeNetwork network;final RequestBinding binding;
    final boolean saved;final long began,connection,policy,identityEdit;final Object browserSession;long readySince;
    ApplicationAttempt(String id,ChatSession session,NativeNetwork network,RequestBinding binding,boolean saved,long began){this.id=id;this.session=session;this.network=network;this.binding=binding;this.saved=saved;this.began=began;connection=session.connectionEpoch;policy=session.web.identityPolicyRevision;identityEdit=session.identity.editSerial;browserSession=session.web.current;}
  }
  boolean applicationCurrent(ApplicationAttempt attempt){
    ChatSession s=attempt.session;RequestBinding binding=attempt.binding;
    if(maintenanceStopped||s.deleted||ChatSession.peek()!=s||bindings.get(attempt.id)!=binding||binding==null||s.environmentGeneration!=binding.identity.generation||!s.environmentId.equals(binding.identity.environmentId)||s.connectionEpoch!=attempt.connection||s.web.current!=attempt.browserSession||s.web.identityPolicyRevision!=attempt.policy||s.identity.editSerial!=attempt.identityEdit)return false;
    if(!attempt.saved)return true;Transition transition=activeTransition;
    return binding.receipt!=null&&transition!=null&&transition.confirmed&&transition.session==s&&transition.id.equals(attempt.id)&&owns(transition)&&binding.snapshot.equals(transition.expectedPendingSnapshot);
  }
  boolean applicationRouteReady(ApplicationAttempt attempt){
    ChatSession s=attempt.session;NativeNetwork n=attempt.network;
    if(!applicationCurrent(attempt)||!s.networkReady||s.offline||s.connecting||!s.networkIssue.isEmpty()||!s.guard.allowed()||s.appliedIdentity.isEmpty()||!s.appliedIdentity.equals(s.networkIdentity()))return false;
    if(!s.internalNetwork())return true;NativeNetwork.ExitRouteReceipt receipt=n.verifiedRoute;
    return !n.starting&&n.transport!=null&&n.settings!=null&&receipt!=null&&n.connectionAdmission()==NetworkHealthPolicy.Admission.VERIFIED&&!receipt.configuration.isEmpty()&&receipt.configuration.equals(NativeNetwork.transportFingerprint(n.settings));
  }
  void waitConnection(String id,ChatSession s,NativeNetwork n,boolean saved,long began){pollApplication(new ApplicationAttempt(id,s,n,bindings.get(id),saved,began));}
  void pollApplication(ApplicationAttempt attempt){main.postDelayed(()->{
    if(!applicationCurrent(attempt)){finish(attempt.id,false,attempt.saved?"配置已保存；当前会话或配置已变化，应用结果尚未确认":"当前会话已变化，本次重连结果未确认");return;}
    ChatSession s=attempt.session;NativeNetwork n=attempt.network;long now=SystemClock.elapsedRealtime();
    if(now-attempt.began>150000){finish(attempt.id,false,attempt.saved?"配置已保存，应用回执尚未确认，请在网络面板检查":"连接回执尚未确认，请检查此窗口网络");return;}
    if(!applicationRouteReady(attempt)){
      if(!s.connecting&&!n.starting){finish(attempt.id,false,(attempt.saved?"配置已保存，":"")+(s.networkIssue.isEmpty()?"连接尚未完成，请检查此窗口网络":s.networkIssue));return;}
      pollApplication(attempt);return;
    }
    if(attempt.readySince==0)attempt.readySince=now;
    if(attempt.saved&&(!s.web.getSettings().policyAcknowledged||attempt.browserSession==null)){
      if(now-attempt.readySince>=5000){finish(attempt.id,false,"配置已保存，网页运行配置的确认尚未完成");return;}pollApplication(attempt);return;
    }
    final NativeNetwork.ExitRouteReceipt route=s.internalNetwork()?n.verifiedRoute:null;
    final JSONObject accepted=J.parse(s.web.getSettings().acceptedBrowserIdentity.toString());
    final EnvironmentSpec.NetworkBinding actual=EnvironmentSpecRuntime.binding(attempt.binding.identity,s.internalNetwork()?"internal":"external",s.internalNetwork()?J.parse(n.settings.toString()):new JSONObject(),s.prefs.getString("proxy",""));
    final Transition transition=attempt.saved?activeTransition:null;
    io.execute(()->{
      JSONObject outcome=null;boolean verified=false;try{
        EnvironmentSpecRuntime.requireIdentity(profile,attempt.binding.identity);
        if(route!=null&&(n.verifiedRoute!=route||!n.verifiedRouteCurrent()))throw new java.io.IOException("运行线路回执已变化");
        if(attempt.saved)outcome=EnvironmentSpecRuntime.withIntent(profile,()->{
          EnvironmentSpecRuntime.requireIdentity(profile,attempt.binding.identity);
          if(!attempt.binding.snapshot.equals(NetworkChanges.pendingStrict(profile).toString())||transition==null||!transition.publishedHash.equals(NetworkChanges.hash(profile)))throw new java.io.IOException("待应用配置已变化");
          EnvironmentSpec model=new EnvironmentSpecRepository(profile).load();
          if(!GeckoWebView.VERSION.equals(model.engineVersion))throw new java.io.IOException("网页运行版本尚未确认");
          JSONObject result=attempt.binding.receipt.applied(model,accepted,actual,"配置已保存并由当前会话应用");
          EnvironmentSpecRuntime.requireIdentity(profile,attempt.binding.identity);return result;
        });
        verified=true;
      }catch(Exception unavailable){/* Saved and usable remain distinct from a confirmed application. */}
      final boolean proven=verified;final JSONObject result=outcome;main.post(()->{
        if(!applicationCurrent(attempt)){finish(attempt.id,false,attempt.saved?"配置已保存；当前会话或配置已变化，应用结果尚未确认":"当前会话已变化，本次重连结果未确认");return;}
        boolean current=applicationRouteReady(attempt)&&(route==null?!s.internalNetwork():s.internalNetwork()&&route==n.verifiedRoute&&route.matches(n,n.transport.state));
        EnvironmentSpec.NetworkBinding fresh=EnvironmentSpecRuntime.binding(attempt.binding.identity,s.internalNetwork()?"internal":"external",s.internalNetwork()?n.settings:new JSONObject(),s.prefs.getString("proxy",""));
        boolean policy=!attempt.saved||s.web.getSettings().policyAcknowledged&&new EnvironmentSpec.Configuration(accepted,actual).equals(new EnvironmentSpec.Configuration(s.web.getSettings().acceptedBrowserIdentity,fresh));
        if(proven&&current&&policy){if(attempt.saved)attempt.binding.outcome=result;finish(attempt.id,true,attempt.saved?"配置已保存并由当前会话应用":"连接已恢复");return;}
        if(SystemClock.elapsedRealtime()-attempt.readySince>=5000){finish(attempt.id,false,attempt.saved?"配置已保存，实际应用回执尚未确认；当前网页保持打开":"本次重连核验尚未确认；当前网页保持打开");return;}
        pollApplication(attempt);
      });
    });
  },500);}
  @Override public Cursor query(Uri u,String[] p,String s,String[] a,String o){return null;}@Override public String getType(Uri u){return null;}@Override public Uri insert(Uri u,ContentValues v){throw new UnsupportedOperationException();}@Override public int delete(Uri u,String s,String[] a){throw new UnsupportedOperationException();}@Override public int update(Uri u,ContentValues v,String s,String[] a){throw new UnsupportedOperationException();}
}
