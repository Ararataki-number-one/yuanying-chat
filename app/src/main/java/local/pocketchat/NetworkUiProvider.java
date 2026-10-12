package local.pocketchat;

import android.content.*;import android.database.Cursor;import android.net.Uri;import android.os.*;import android.util.AtomicFile;
import org.json.*;import java.util.*;import java.util.concurrent.*;import java.nio.charset.StandardCharsets;

/** Private UI-to-profile bridge. Each provider runs in the existing profile's own process. */
public class NetworkUiProvider extends ContentProvider {
  Context profile;AppUpdateRoute.Server updateRoutes;final Handler main=new Handler(Looper.getMainLooper());final Map<String,JSONObject> jobs=new ConcurrentHashMap<>();boolean applying,saving,drainReading;long drainRevision,saveRevision;String activeApply="";volatile Transition activeTransition;final Runnable drain=()->{drainPending();main.postDelayed(this.drain,1000);};final ExecutorService io=Executors.newSingleThreadExecutor();
  public static class Profile1 extends NetworkUiProvider{}public static class Profile2 extends NetworkUiProvider{}public static class Profile3 extends NetworkUiProvider{}public static class Profile4 extends NetworkUiProvider{}public static class Profile5 extends NetworkUiProvider{}public static class Profile6 extends NetworkUiProvider{}public static class Profile7 extends NetworkUiProvider{}
  @Override public boolean onCreate(){profile=Profiles.context(getContext(),Profiles.processSlot());updateRoutes=new AppUpdateRoute.Server(profile);main.post(drain);return true;}
  @Override public Bundle call(String method,String arg,Bundle extras){
    if(Binder.getCallingUid()!=android.os.Process.myUid())throw new SecurityException();Bundle result=new Bundle();
    if("updateRoute".equals(method)||"validateUpdateRoute".equals(method))return updateRoutes.response(extras,"validateUpdateRoute".equals(method));
    if("stopForDelete".equals(method)){
      if(!ProfileCatalog.get(profile).item(Profiles.slot(profile)).optBoolean("deleting"))throw new IllegalStateException();
      java.util.concurrent.CountDownLatch stopped=new java.util.concurrent.CountDownLatch(1);java.util.concurrent.atomic.AtomicBoolean confirmed=new java.util.concurrent.atomic.AtomicBoolean();main.post(()->{ChatSession s=ChatSession.peek();if(s!=null){s.deleted=true;s.handler.removeCallbacks(s.tick);s.guard.setBlocked(true);ChatService.end(profile);s.web.destroy();}NativeNetwork n=NativeNetwork.get(profile);n.cancelMaintenance();n.worker.execute(()->{try{confirmed.set(n.stopNow());}finally{stopped.countDown();}});});
      try{if(!stopped.await(20,java.util.concurrent.TimeUnit.SECONDS))throw new IllegalStateException("停止环境超时");}catch(InterruptedException e){Thread.currentThread().interrupt();throw new IllegalStateException(e);}if(!confirmed.get()||NativeNetwork.get(profile).coreAlive())throw new IllegalStateException("独立网络尚未停止，请重试删除");result.putBoolean("stopped",true);return result;
    }
    if("state".equals(method)){NativeNetwork n=NativeNetwork.get(profile);JSONObject state=WindowNetworkState.live(ChatSession.peek(),n);NetworkCatalog.put(state,"configurationHash",NetworkChanges.hash(profile));result.putString("json",state.toString());return result;}
    if("job".equals(method)){JSONObject status=jobs.get(arg);result.putString("json",status==null?J.obj("done",true,"ok",false,"message","操作记录已过期").toString():status.toString());return result;}
    if(!"start".equals(method))throw new IllegalArgumentException();String action=extras==null?"":extras.getString("action","");JSONObject candidate=J.parse(extras==null?"{}":extras.getString("config","{}"));String baseline=extras==null?"":extras.getString("baseline","");
    String id=UUID.randomUUID().toString();if(jobs.size()>24)jobs.entrySet().removeIf(x->x.getValue().optBoolean("done"));jobs.put(id,J.obj("done",false));main.post(()->request(id,action,candidate,baseline));result.putString("id",id);return result;
  }
  void finish(String id,boolean ok,String message){if(Looper.myLooper()!=Looper.getMainLooper()){main.post(()->finish(id,ok,message));return;}if(id.equals(activeApply)){Transition transition=activeTransition;if(transition!=null&&transition.confirmed&&!transition.pendingReleased){transition.pendingReleased=true;io.execute(()->{try{NetworkChanges.clearIfCurrent(profile,transition.expectedPendingSnapshot);}catch(Exception ignored){}main.post(()->finish(id,ok,message));});return;}applying=false;activeApply="";if(transition!=null){releaseCapture(transition,!transition.confirmed);transition.cancelled=true;activeTransition=null;}ChatSession s=ChatSession.peek();if(s!=null){if(transition==null)s.operation=false;s.changed();}}WindowNetworkState.save(profile,ChatSession.peek(),NativeNetwork.get(profile));jobs.put(id,J.obj("done",true,"ok",ok,"message",message));}
  boolean busy(ChatSession s,NativeNetwork n){return applying||n!=null&&(n.starting||n.measuringLatency)||s==null&&J.parse(profile.getSharedPreferences("chat",0).getString("pending","{}")).length()>0||s!=null&&(ProfileUi.working(s)||s.connecting);}
  void request(String id,String action,JSONObject candidate,String baseline){request(id,action,candidate,baseline,false);}
  void request(String id,String action,JSONObject candidate,String baseline,boolean deferred){request(id,action,candidate,baseline,deferred,-1,"");}
  void request(String id,String action,JSONObject candidate,String baseline,boolean deferred,int generation,String pendingSnapshot){
    drainRevision++;
    if(!"apply".equals(action)&&!"external".equals(action)){operate(id,action,candidate,baseline);return;}
    long requestRevision=++saveRevision;saving=true;
    io.execute(()->{
      String error="";boolean superseded=false,sameGeneration=false;try{
        JSONObject row=ProfileCatalog.get(profile).item(Profiles.slot(profile));sameGeneration=generation<0||generation==row.optInt("generation");
        if(!row.optBoolean("created")||!sameGeneration)throw new java.io.IOException("此环境已删除或重新创建");
        // A queued read must not put an older candidate back after a newer save.
        superseded=deferred&&!pendingSnapshot.isEmpty()&&!pendingSnapshot.equals(NetworkChanges.pending(profile).toString());
        if(!superseded){if(!baseline.equals(NetworkChanges.hash(profile)))throw new java.io.IOException("此窗口配置已变化，请重新编辑");
          NetworkChanges.validate(profile,action,candidate);Transition parent=activeTransition;JSONObject lineage=parent!=null&&!parent.confirmed&&!parent.publishedHash.isEmpty()&&parent.generation==row.optInt("generation")&&baseline.equals(parent.publishedHash)?NetworkChanges.lineage(parent.id,parent.publishedHash,parent.baseline,parent.generation):new JSONObject();NetworkChanges.save(profile,action,candidate,baseline,lineage);}
      }catch(Exception e){error=e.getMessage()==null?"配置未能保存":e.getMessage();}
      if(!error.isEmpty()&&deferred&&sameGeneration)try{JSONObject current=NetworkChanges.pending(profile);boolean unchanged=pendingSnapshot.isEmpty()?baseline.equals(current.optString("baseline"))&&candidate.toString().equals(String.valueOf(current.optJSONObject("config"))):pendingSnapshot.equals(current.toString());if(unchanged)NetworkChanges.clear(profile);}catch(Exception unavailable){/* Keep an unreadable candidate for the next idle retry. */}
      String failure=error;boolean replaced=superseded;main.post(()->{
        // A newer save owns this flag and its pending candidate. Older completion
        // must neither clear that candidate nor switch back to an older route.
        if(requestRevision!=saveRevision){if(deferred)jobs.remove(id);else jobs.put(id,J.obj("done",true,"ok",true,"message","已由较新的网络设置替换"));return;}
        saving=false;if(replaced){jobs.remove(id);return;}if(!failure.isEmpty()){if(deferred){ChatSession waiting=ChatSession.peek();if(waiting!=null)waiting.setStatus("已保存的网络设置需要重新编辑："+failure);}finish(id,false,failure);return;}
        ChatSession s=ChatSession.peek();NativeNetwork n=NativeNetwork.get(profile);
        if(saving||busy(s,n)||s!=null&&(s.navigating||s.state.optBoolean("busy"))){finish(id,true,"网络设置已保存，当前回复和文件操作结束后自动应用");return;}
        operate(id,action,candidate,baseline);
      });
    });
  }
  void operate(String id,String action,JSONObject candidate,String baseline){
    ChatSession s=ChatSession.peek();NativeNetwork n=NativeNetwork.get(profile);
    if(!ProfileCatalog.get(profile).item(Profiles.slot(profile)).optBoolean("created")){finish(id,false,"此环境已删除");return;}
    if("cancelPending".equals(action)){cancelPending(id);return;}
    if("measure".equals(action)){if("internal".equals(profile.getSharedPreferences("chat",0).getString("networkMode","external")))n.measureLatency((ok,msg)->finish(id,ok,msg));else if(s!=null)NetworkRegion.refreshLatency(s,(ok,msg)->finish(id,ok,msg));else finish(id,false,"请先打开此窗口的会话后测量连接响应");return;}
    if(busy(s,n)){finish(id,false,"当前回复继续进行，网络配置可以先编辑保存");return;}
    if("verify".equals(action)){if(!n.ready){finish(id,false,"请先连接此窗口，再核验出口");return;}applying=true;activeApply=id;if(s!=null)s.operation=true;n.checkExit((ok,msg)->finish(id,ok,msg));return;}
    if("reconnect".equals(action)){if(s!=null){s.reconnect();waitConnection(id,s,n,false,SystemClock.elapsedRealtime());}else if("internal".equals(profile.getSharedPreferences("chat",0).getString("networkMode","external")))n.restart((ok,msg)->finish(id,ok,msg));else finish(id,false,"打开此窗口的会话后可重连手机网络");return;}
    if("apply".equals(action)||"external".equals(action)){beginTransition(id,action,candidate,baseline);return;}
    finish(id,false,"未知网络操作");
  }
  /** Cancellation and confirmation share the main actor; storage work stays on IO. */
  void cancelPending(String id){
    ++saveRevision;saving=false;Transition transition=activeTransition;
    if(transition!=null&&!transition.confirmed){transition.cancelledByUser=true;transition.cancelled=true;}
    io.execute(()->{String error="";try{
      if(transition!=null&&transition.cancelledByUser){rollbackTransition(transition);if(transition.rollbackFailed)throw new java.io.IOException("原网络设置未能完整恢复，请重新编辑网络");}
      NetworkChanges.clear(profile);
    }catch(Exception failure){error=failure.getMessage()==null?"待应用网络设置未能取消":failure.getMessage();}
      String failure=error;main.post(()->{if(transition!=null&&transition.cancelledByUser&&activeTransition==transition)deferTransition(transition);finish(id,failure.isEmpty(),failure.isEmpty()?"待应用设置已取消，当前连接保持不变":failure);});
    });
  }
  void drainPending(){
    if(drainReading||saving||applying)return;
    ChatSession s=ChatSession.peek();
    if(busy(s,null)||s!=null&&(s.deleted||s.navigating||s.recoveryScheduled||s.state.optBoolean("busy")))return;
    drainReading=true;long revision=drainRevision;
    io.execute(()->{
      JSONObject readRow=new JSONObject(),readQueued=new JSONObject();try{readRow=ProfileCatalog.get(profile).item(Profiles.slot(profile));if(readRow.optBoolean("created"))readQueued=NetworkChanges.pending(profile);}catch(Exception unavailable){/* Retry on the next idle tick without changing or announcing the saved candidate. */}
      JSONObject row=readRow,queued=readQueued;
      main.post(()->{
        drainReading=false;if(revision!=drainRevision||!row.optBoolean("created")||queued.length()==0||saving||applying)return;
        ChatSession current=ChatSession.peek();NativeNetwork network=NativeNetwork.get(profile);
        if(busy(current,network)||current!=null&&(current.deleted||current.environmentGeneration!=row.optInt("generation")||current.navigating||current.recoveryScheduled||current.state.optBoolean("busy")))return;
        String id=UUID.randomUUID().toString();jobs.put(id,J.obj("done",false));
        request(id,queued.optString("action"),queued.optJSONObject("config"),queued.optString("baseline"),true,row.optInt("generation"),queued.toString());
      });
    });
  }
  static final class Transition {
    final String id,action,baseline;final JSONObject candidate;final ChatSession session;final int generation;final long revision;
    String url="",scope="",preparedProof="",expectedPendingSnapshot="",oldMode="external",oldEntry="",oldProxy="";long epoch;JSONObject page;boolean oldConfigured,oldVpn,capture,fenced,confirmed,pendingReleased,previousBlocked,rollbackFailed;
    volatile boolean cancelled,cancelledByUser;boolean rollbackComplete;volatile String publishedHash="";NetworkSourceSelection.ActiveSnapshot transaction;android.view.View.OnTouchListener previousTouch,touchFence;android.view.View keyTarget;
    Transition(String id,String action,JSONObject candidate,String baseline,ChatSession session,int generation,long revision){this.id=id;this.action=action;this.candidate=J.parse(candidate.toString());this.baseline=baseline;this.session=session;this.generation=generation;this.revision=revision;}
  }
  static final class DeferredTransition extends Exception {}
  void beginTransition(String id,String action,JSONObject candidate,String baseline){
    JSONObject row=ProfileCatalog.get(profile).item(Profiles.slot(profile));Transition transition=new Transition(id,action,candidate,baseline,ChatSession.peek(),row.optInt("generation"),saveRevision);applying=true;activeApply=id;activeTransition=transition;
    // Preparation never suppresses the real webpage's send observer or polling.
    io.execute(()->prepareTransition(transition));
  }
  static String proof(NetworkSourceSelection.Sources sources){return NetworkSourceSelection.payloadHash(sources.entryBytes)+":"+(sources.exitBytes==null?"manual":NetworkSourceSelection.payloadHash(sources.exitBytes));}
  void prepareTransition(Transition transition){
    try{
      if(transition.cancelled)throw new DeferredTransition();if(!transition.baseline.equals(NetworkChanges.hash(profile)))throw new java.io.IOException("此窗口配置已变化，请重新编辑");JSONObject pending=NetworkChanges.pending(profile);if(pending.length()==0||!transition.action.equals(pending.optString("action"))||!transition.baseline.equals(pending.optString("baseline"))||!transition.candidate.toString().equals(String.valueOf(pending.optJSONObject("config"))))throw new DeferredTransition();transition.expectedPendingSnapshot=pending.toString();
      if("apply".equals(transition.action))NetworkSourceSelection.withSources(profile,transition.candidate,sources->{transition.preparedProof=proof(sources);return null;});
      else NetworkChanges.validate(profile,transition.action,transition.candidate);
      main.post(()->captureTransition(transition));
    }catch(Exception error){main.post(()->{if(error instanceof DeferredTransition)deferTransition(transition);else failTransition(transition,error);});}
  }
  void requirePending(Transition transition)throws Exception{if(transition.cancelled||transition.expectedPendingSnapshot.isEmpty()||!transition.expectedPendingSnapshot.equals(NetworkChanges.pending(profile).toString()))throw new DeferredTransition();if(!transition.baseline.equals(NetworkChanges.hash(profile)))throw new java.io.IOException("此窗口配置已变化，请重新编辑");}
  boolean owns(Transition transition){return !transition.cancelled&&activeTransition==transition&&transition.id.equals(activeApply)&&transition.revision==saveRevision;}
  boolean currentEnvironment(Transition transition){JSONObject row=ProfileCatalog.get(profile).item(Profiles.slot(profile));return row.optBoolean("created")&&!row.optBoolean("deleting")&&row.optInt("generation")==transition.generation&&(transition.session==null||transition.session.environmentGeneration==transition.generation);}
  boolean fenceIdle(Transition transition){
    if(!owns(transition)||saving||!currentEnvironment(transition)||ChatSession.peek()!=transition.session)return false;NativeNetwork network=NativeNetwork.get(profile);if(network.starting||network.measuringLatency)return false;ChatSession session=transition.session;
    if(session==null)return J.parse(profile.getSharedPreferences("chat",0).getString("pending","{}")).length()==0;
    if(session.deleted||session.pending!=null||session.submitting||session.transferActive||session.uploading()||session.connecting||session.navigating||session.recoveryScheduled||session.operation&&!transition.capture)return false;
    if(!transition.url.isEmpty()&&(transition.epoch!=session.navigationEpoch||!WebReplyObserver.same(transition.url,session.web.getUrl())||!transition.scope.equals(session.pageMemory.scope())))return false;
    return !session.state.optBoolean("busy");
  }
  void captureTransition(Transition transition){
    if(!fenceIdle(transition)){deferTransition(transition);return;}ChatSession session=transition.session;
    if(session==null){io.execute(()->commitTransition(transition));return;}
    transition.url=session.web.getUrl();transition.epoch=session.navigationEpoch;transition.scope=session.pageMemory.scope();session.operation=true;session.configurationCapture=true;transition.capture=true;
    if(!MainActivity.chatUrl(transition.url)){io.execute(()->commitTransition(transition));return;}
    session.asyncDriver("inspect",J.obj("expectedUrl",transition.url),2500,inspected->{
      if(!inspectionIdle(transition,inspected,null)){deferTransition(transition);return;}
      session.asyncDriver("page-state",J.obj("expectedUrl",transition.url),2500,state->{
        if(!fenceIdle(transition)||!state.optBoolean("ok")||!WebReplyObserver.same(transition.url,state.optString("url"))||!state.optString("draft").equals(inspected.optString("draft"))||!state.optString("documentId").equals(inspected.optString("documentId"))){deferTransition(transition);return;}
        transition.page=state;session.pageMemory.remember(transition.scope,transition.url,state);session.web.checkpointState();
        session.webStore.worker.execute(()->{boolean saved=DraftArchive.get(session.context).save(transition.url,state.optString("draft"),"应用网络设置前的草稿");main.post(()->{
          if(!saved||!fenceIdle(transition)){deferTransition(transition);return;}
          session.asyncDriver("inspect",J.obj("expectedUrl",transition.url),2500,fresh->{if(!inspectionIdle(transition,fresh,state)){deferTransition(transition);return;}io.execute(()->commitTransition(transition));});
        });});
      });
    });
  }
  boolean inspectionIdle(Transition transition,JSONObject inspected,JSONObject page){return fenceIdle(transition)&&WebReplyObserver.same(transition.url,inspected.optString("url"))&&!inspected.optBoolean("busy")&&inspected.optString("draftRaw").length()<=300000&&(page==null||page.optString("draft").equals(inspected.optString("draft"))&&page.optString("documentId").equals(inspected.optString("documentId")));}
  /** The source/private leases wait only for this short main-thread state check, never HTTP or JS. */
  void commitGate(Transition transition)throws Exception{
    CountDownLatch gate=new CountDownLatch(1);java.util.concurrent.atomic.AtomicBoolean admitted=new java.util.concurrent.atomic.AtomicBoolean(),waiting=new java.util.concurrent.atomic.AtomicBoolean(true);
    main.post(()->{try{if(!waiting.get()||!fenceIdle(transition))return;ChatSession session=transition.session;if(session!=null){transition.previousBlocked=session.guard.blocked;transition.previousTouch=session.web.touches;transition.touchFence=(view,event)->true;session.web.cancelPendingInputEvents();session.web.setOnTouchListener(transition.touchFence);if(session.web.surface!=null){transition.keyTarget=session.web.surface;transition.keyTarget.cancelPendingInputEvents();transition.keyTarget.setOnKeyListener((view,key,event)->true);}session.guard.setBlocked(true);}transition.fenced=true;admitted.set(true);}finally{gate.countDown();}});
    if(!gate.await(3,TimeUnit.SECONDS)){waiting.set(false);throw new DeferredTransition();}waiting.set(false);if(!admitted.get())throw new DeferredTransition();
    if(transition.cancelled||transition.session!=null&&transition.session.pending!=null)throw new DeferredTransition();
  }
  void commitTransition(Transition transition){
    SharedPreferences preferences=profile.getSharedPreferences("chat",0);SecretStore vault=new SecretStore(profile);
    try{
      if(!transition.baseline.equals(NetworkChanges.hash(profile)))throw new java.io.IOException("此窗口配置已变化，请重新编辑");
      if("apply".equals(transition.action))NetworkSourceSelection.withSources(profile,transition.candidate,sources->{
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
    else if("apply".equals(transition.action))network.restart((ok,msg)->finish(transition.id,ok,ok?"配置已保存并应用":"配置已保存，"+msg));
    else finish(transition.id,true,"已保存，打开会话时应用手机网络");
  }
  void releaseCapture(Transition transition,boolean restoreGuard){ChatSession session=transition.session;if(session==null)return;if(transition.fenced&&session.web.touches==transition.touchFence)session.web.setOnTouchListener(transition.previousTouch);if(transition.keyTarget!=null){transition.keyTarget.setOnKeyListener(null);transition.keyTarget=null;}if(restoreGuard&&transition.fenced&&!transition.rollbackFailed&&!session.deleted&&!session.connecting&&ChatSession.peek()==session&&currentEnvironment(transition))session.guard.setBlocked(transition.previousBlocked);if(transition.capture&&activeTransition==transition){session.configurationCapture=false;session.operation=false;transition.capture=false;session.wakePolling();}}
  void deferTransition(Transition transition){if(activeTransition!=transition)return;if(transition.rollbackFailed){failTransition(transition,new java.io.IOException("网络设置恢复未完成，原网页未重新加载，请重新编辑网络"));return;}releaseCapture(transition,true);transition.cancelled=true;finish(transition.id,true,transition.cancelledByUser?"待应用设置已取消，当前连接保持不变":"网络设置已保存，当前回复和文件操作结束后自动应用");}
  void failTransition(Transition transition,Exception error){if(activeTransition!=transition)return;releaseCapture(transition,true);transition.cancelled=true;finish(transition.id,false,error.getMessage()==null?"网络设置未应用，原连接已保留":error.getMessage());}
  static void restore(SecretStore store,String slot,byte[] value)throws Exception{if(value==null)new AtomicFile(store.file(slot)).delete();else store.put(slot,value);}
  void waitConnection(String id,ChatSession s,NativeNetwork n,boolean saved,long began){main.postDelayed(()->{
    if(s.networkReady&&!s.offline&&(!s.internalNetwork()||n.ready&&n.coreAlive())){finish(id,true,saved?"配置已保存并应用":"连接已恢复");}
    else if(!s.connecting&&!n.starting||SystemClock.elapsedRealtime()-began>150000){finish(id,false,(saved?"配置已保存，":"")+(s.networkIssue.isEmpty()?"连接尚未完成，请检查此窗口网络":s.networkIssue));}
    else waitConnection(id,s,n,saved,began);
  },500);}
  @Override public Cursor query(Uri u,String[] p,String s,String[] a,String o){return null;}@Override public String getType(Uri u){return null;}@Override public Uri insert(Uri u,ContentValues v){throw new UnsupportedOperationException();}@Override public int delete(Uri u,String s,String[] a){throw new UnsupportedOperationException();}@Override public int update(Uri u,ContentValues v,String s,String[] a){throw new UnsupportedOperationException();}
}
