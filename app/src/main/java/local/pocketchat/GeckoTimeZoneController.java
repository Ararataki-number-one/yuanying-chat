package local.pocketchat;

import java.util.*;
import java.util.function.*;
import org.json.*;

/** App-owned desired/native state. Storage runs only on the environment writer;
 * native callbacks are fenced to their exact session, open epoch and revision. */
final class GeckoTimeZoneController {
  interface NativeAccess {
    boolean current();
    void read(String requestToken,Consumer<String> success,Consumer<Throwable> failure);
    void apply(String zoneId,String requestToken,Consumer<String> success,Consumer<Throwable> failure);
  }
  final ChatSession session;
  volatile GeckoTimeZoneStore.State cached;
  private final Map<Object,Operation> operations=new IdentityHashMap<>();
  private final Set<Runnable> listeners=new HashSet<>();
  private String loadIssue="";private long editSerial;
  private final String auditInstance=token();private volatile long auditSerial,configurationSerial;
  private static final class Operation {
    final Object nativeSession;final String sessionId,epoch;final NativeAccess access;
    final List<Consumer<Boolean>> waiters=new ArrayList<>();
    GeckoTimeZoneStore.State desired;GeckoTimeZoneStore.Ticket ticket;
    volatile boolean retired,finished;boolean started,ready,verified,unsupported;String issue="";
    Operation(Object nativeSession,String sessionId,String epoch,NativeAccess access){this.nativeSession=nativeSession;this.sessionId=sessionId;this.epoch=epoch;this.access=access;}
  }
  GeckoTimeZoneController(ChatSession session){this.session=session;}
  void load(){refresh(null);}
  void refresh(Consumer<GeckoTimeZoneStore.State> done){session.environmentIo.execute(()->{
    GeckoTimeZoneStore.State state=null;String error="";
    try{state=GeckoTimeZoneStore.load(session.context);if(!identity(state))throw new IllegalStateException("Environment changed");}
    catch(Exception unavailable){error="独立时区记录无法读取，原文件保留；尚未应用时区设置";}
    GeckoTimeZoneStore.State loaded=state;String failure=error;
    session.handler.post(()->{
      if(session.deleted)return;
      if(!failure.isEmpty()){configurationChanged();loadIssue=failure;invalidate();}
      else if(identity(loaded)){
        GeckoTimeZoneStore.State previous=cached;if(previous==null||!previous.identity.equals(loaded.identity)||previous.revision!=loaded.revision||!previous.spec.equals(loaded.spec)||!loadIssue.isEmpty())configurationChanged();cached=loaded;loadIssue="";
        if(previous!=null&&(!previous.identity.equals(loaded.identity)||previous.revision!=loaded.revision||!previous.spec.equals(loaded.spec)))invalidate();
        for(Operation op:new ArrayList<>(operations.values()))if(!op.started)begin(op);
      }
      changed();if(done!=null)done.accept(failure.isEmpty()?loaded:null);
    });
  });}
  private boolean identity(GeckoTimeZoneStore.State state){return state!=null&&!session.deleted&&state.identity.slot==Profiles.slot(session.context)&&state.identity.generation==session.environmentGeneration&&state.identity.environmentId.equals(session.environmentId);}
  private boolean desiredCurrent(GeckoTimeZoneStore.State state){GeckoTimeZoneStore.State desired=cached;return identity(desired)&&loadIssue.isEmpty()&&desired.revision==state.revision&&desired.identity.equals(state.identity)&&desired.spec.equals(state.spec);}
  void addListener(Runnable listener){listeners.add(listener);}
  void removeListener(Runnable listener){listeners.remove(listener);}
  private void changed(){for(Runnable listener:new ArrayList<>(listeners))listener.run();}
  /** Memory-only stamp: changing back to the same desired zone or native ID
   * cannot resurrect an earlier page/Worker observation. */
  String auditStamp(){return auditSerial+"|"+auditConfigurationStamp();}
  /** Configuration identity for one explicitly owned navigation. It never
   * admits page observations or replaces the full native/document stamp. */
  String auditConfigurationStamp(){GeckoTimeZoneStore.State desired=cached;return auditInstance+"|"+configurationSerial+"|"+(desired==null?"unloaded":desired.identity.environmentId+":"+desired.identity.generation+":"+desired.revision+":"+desired.spec.zoneId)+"|"+loadIssue.isEmpty();}
  private void boundaryChanged(){auditSerial++;if(session.audit!=null)session.audit.retirePageCheck();}
  private void configurationChanged(){configurationSerial++;boundaryChanged();}
  JSONObject auditExpected(JSONObject expected){
    GeckoTimeZoneStore.State desired=cached;
    if(desired!=null&&!desired.spec.followsSystem()&&session.privacy.level()<2)try{
      expected.put("offset",JSONObject.NULL).put("timezoneStrategy","native-independent").put("timezoneRequestedZone",desired.spec.zoneId)
          .put("timezoneNativeReadback",status().optBoolean("nativeSettingReadback")).put("timezoneObservationStartedAt",System.currentTimeMillis());
    }catch(JSONException ignored){}return expected;
  }
  boolean popupAllowed(){return identity(cached)&&loadIssue.isEmpty()&&cached.spec.followsSystem();}
  boolean allowed(Object nativeSession,String epoch){Operation op=operations.get(nativeSession);return alive(op)&&op.epoch.equals(epoch)&&op.finished&&op.ready&&accessCurrent(op)&&!GeckoTimeZonePolicy.protectionConflict(session.privacy.level(),cached.spec);}
  private boolean accessCurrent(Operation op){try{return op.access.current();}catch(RuntimeException unavailable){return false;}}
  private boolean alive(Operation op){return op!=null&&!op.retired&&!session.deleted&&operations.get(op.nativeSession)==op&&identity(cached)&&loadIssue.isEmpty()&&(op.desired==null||op.desired.revision==cached.revision&&op.desired.identity.equals(cached.identity)&&op.desired.spec.equals(cached.spec));}
  private boolean pending(Operation op){if(!alive(op)||op.finished||!accessCurrent(op))return false;if(GeckoTimeZonePolicy.protectionConflict(session.privacy.level(),op.desired.spec)){fail(op,false,"强化保护优先使用自己的时区策略，独立时区尚未应用");return false;}return true;}
  void prepare(Object nativeSession,String sessionId,String epoch,NativeAccess access,Consumer<Boolean> gate){
    prepare(nativeSession,sessionId,epoch,access,gate,false);
  }
  /** A new native document can replace its top BC without reopening the SDK
   * session. Drop the old confirmation before any asynchronous native read.
   * The caller's access also fences this exact document-validation generation. */
  void revalidate(Object nativeSession,String sessionId,String epoch,NativeAccess access,Consumer<Boolean> gate){
    Operation old=operations.get(nativeSession);boolean current=false;try{current=access!=null&&access.current();}catch(RuntimeException unavailable){}
    if(old==null||old.retired||!old.sessionId.equals(sessionId)||!old.epoch.equals(epoch)||!current){gate.accept(false);return;}
    prepare(nativeSession,sessionId,epoch,access,gate,true);
  }
  private void prepare(Object nativeSession,String sessionId,String epoch,NativeAccess access,Consumer<Boolean> gate,boolean revalidate){
    if(session.deleted||nativeSession==null||access==null||!GeckoTimeZonePolicy.validSession(sessionId)||!GeckoTimeZonePolicy.validSession(epoch)){gate.accept(false);return;}
    Operation old=operations.get(nativeSession);
    if(!revalidate&&old!=null&&!old.retired&&(alive(old)||old.desired==null&&cached==null&&loadIssue.isEmpty())&&old.sessionId.equals(sessionId)&&old.epoch.equals(epoch)&&accessCurrent(old)){
      if(old.finished)gate.accept(allowed(nativeSession,epoch));else old.waiters.add(gate);return;
    }
    if(old!=null)retire(nativeSession,old.epoch);
    boundaryChanged();Operation op=new Operation(nativeSession,sessionId,epoch,access);op.waiters.add(gate);operations.put(nativeSession,op);
    if(!loadIssue.isEmpty())fail(op,false,loadIssue);else if(cached!=null)begin(op);
  }
  private void begin(Operation op){
    if(!alive(op)||op.started)return;op.started=true;op.desired=cached;
    if(GeckoTimeZonePolicy.protectionConflict(session.privacy.level(),op.desired.spec)){fail(op,false,"强化保护优先使用自己的时区策略；请明确切换模板后再应用独立时区，强化保护保持不变");return;}
    session.handler.postDelayed(()->{if(alive(op)&&!op.finished)fail(op,false,"原生时区准备未完成；独立时区尚未应用");},15000);
    String bootstrap=token();
    try{op.access.read(bootstrap,raw->session.handler.post(()->{
      if(!pending(op))return;
      try{
        JSONObject context=GeckoTimeZonePolicy.contextReadback(raw,bootstrap,op.sessionId);String contextId=context.getString("contextId");
        GeckoTimeZoneStore.Binding binding=new GeckoTimeZoneStore.Binding(GeckoWebView.VERSION,op.sessionId,op.epoch,contextId);
        session.environmentIo.execute(()->{
          GeckoTimeZoneStore.Ticket ticket=null;try{if(!op.retired)ticket=GeckoTimeZoneStore.activate(session.context,op.desired.identity,op.desired.revision,binding);}catch(Exception unavailable){}
          GeckoTimeZoneStore.Ticket active=ticket;
          session.handler.post(()->{if(!pending(op)){retireTicket(active);return;}if(active==null){fail(op,false,"时区配置或环境已变化，尚未应用");return;}op.ticket=active;apply(op);});
        });
      }catch(Exception rejected){fail(op,unsupported(raw),unsupported(raw)?"当前内核未确认独立时区支持，未应用独立覆盖":"原生时区归属或设置回读不一致，未应用独立覆盖");}
    }),error->session.handler.post(()->{if(pending(op))fail(op,error instanceof UnsupportedOperationException,"当前内核未提供可确认的独立时区，未应用独立覆盖");}));}
    catch(RuntimeException unavailable){fail(op,unavailable instanceof UnsupportedOperationException,"当前内核未提供可确认的独立时区，未应用独立覆盖");}
  }
  private void apply(Operation op){
    try{op.access.apply(op.desired.spec.zoneId,op.ticket.requestToken,raw->session.handler.post(()->{
      if(!pending(op))return;
      try{GeckoTimeZonePolicy.nativeReadback(raw,op.desired.spec,op.ticket.requestToken,op.sessionId,op.ticket.binding.contextId);}
      catch(Exception invalid){fail(op,unsupported(raw),"原生时区设置未被当前上下文确认，独立时区尚未应用");return;}
      session.environmentIo.execute(()->{
        boolean saved=false;try{if(!op.retired&&!op.finished){GeckoTimeZoneStore.record(session.context,op.ticket,raw);saved=true;}}catch(Exception unavailable){}
        boolean recorded=saved;session.handler.post(()->{if(!pending(op)){retireTicket(op.ticket);return;}if(!recorded){fail(op,false,"原生时区确认未保存，独立时区尚未确认");return;}op.ready=true;op.verified=true;finish(op);});
      });
    }),error->session.handler.post(()->{if(pending(op))fail(op,error instanceof UnsupportedOperationException,"原生时区设置失败，未确认独立覆盖");}));}
    catch(RuntimeException unavailable){fail(op,unavailable instanceof UnsupportedOperationException,"原生时区设置失败，未确认独立覆盖");}
  }
  private static boolean unsupported(String raw){if(raw==null||raw.length()>GeckoTimeZonePolicy.ACK_BYTES)return false;try{return "unsupported".equals(GeckoTimeZonePolicy.object(raw.getBytes(java.nio.charset.StandardCharsets.UTF_8),GeckoTimeZonePolicy.ACK_BYTES).optString("status"));}catch(Exception invalid){return false;}}
  private void fail(Operation op,boolean unsupported,String message){
    if(op==null||op.retired||op.finished)return;op.unsupported=unsupported;op.issue=message;op.ready=op.desired!=null&&GeckoTimeZonePolicy.legacySystemMayContinue(op.desired.spec)&&accessCurrent(op);op.verified=false;retireTicket(op.ticket);finish(op);
  }
  private void finish(Operation op){boundaryChanged();op.finished=true;List<Consumer<Boolean>> waiters=new ArrayList<>(op.waiters);op.waiters.clear();changed();for(Consumer<Boolean> waiter:waiters)waiter.accept(op.ready);}
  void retire(Object nativeSession,String epoch){Operation op=operations.get(nativeSession);if(op==null||!op.epoch.equals(epoch))return;boundaryChanged();operations.remove(nativeSession);op.retired=true;retireTicket(op.ticket);if(!op.finished){op.ready=false;finish(op);}changed();}
  private void retireTicket(GeckoTimeZoneStore.Ticket ticket){if(ticket!=null)session.environmentIo.execute(()->{try{GeckoTimeZoneStore.retire(session.context,ticket);}catch(Exception ignored){}});}
  private void invalidate(){for(Operation op:new ArrayList<>(operations.values()))retire(op.nativeSession,op.epoch);}
  void saveConfirmed(GeckoTimeZoneStore.State expected,GeckoTimeZoneSpec selected,BooleanSupplier stillSafe,Consumer<String> done){
    saveConfirmed(expected,selected,stillSafe,checked->checked.accept(true),done);
  }
  void saveConfirmed(GeckoTimeZoneStore.State expected,GeckoTimeZoneSpec selected,BooleanSupplier stillSafe,Consumer<Consumer<Boolean>> finalDraftCheck,Consumer<String> done){
    if(!identity(expected)||!stillSafe.getAsBoolean()){done.accept("当前网页或环境已变化，时区未保存");return;}
    if(GeckoTimeZonePolicy.protectionConflict(session.privacy.level(),selected)){done.accept("强化保护优先使用自己的时区策略；请先明确切换模板，强化保护保持不变");return;}
    long edit=++editSerial;
    session.environmentIo.execute(()->{
      GeckoTimeZoneStore.State state=null;try{state=GeckoTimeZoneStore.save(session.context,expected.identity,expected.revision,selected);}catch(Exception unavailable){}
      GeckoTimeZoneStore.State saved=state;session.handler.post(()->{
        if(edit!=editSerial||session.deleted){done.accept("本次时区修改已失效");return;}
        if(saved==null||!identity(saved)){done.accept("时区未保存，原配置保留；请重新打开设置");return;}
        configurationChanged();cached=saved;loadIssue="";invalidate();changed();
        if(!desiredCurrent(saved)||!stillSafe.getAsBoolean()||GeckoTimeZonePolicy.protectionConflict(session.privacy.level(),selected)){done.accept("时区已保存；网页或保护模板已变化，尚未重载或应用");return;}
        java.util.concurrent.atomic.AtomicBoolean once=new java.util.concurrent.atomic.AtomicBoolean();
        try{finalDraftCheck.accept(unchanged->{
          if(!once.compareAndSet(false,true))return;
          if(!unchanged||edit!=editSerial||!desiredCurrent(saved)||!stillSafe.getAsBoolean()||GeckoTimeZonePolicy.protectionConflict(session.privacy.level(),selected)){done.accept("时区已保存；输入、配置或网页已变化，当前网页保留，尚未应用");return;}
          if(session.web.hasVisibleDocument()&&MainActivity.chatUrl(session.web.getUrl())){
            session.requestTaskGuardStatus("timezone-saved",guard->{
              if(edit!=editSerial||!desiredCurrent(saved)||!stillSafe.getAsBoolean()||GeckoTimeZonePolicy.protectionConflict(session.privacy.level(),selected)||!guard.known||guard.replyBusy||guard.fileBusy||guard.submitting||guard.downloading){done.accept("时区已保存；网页任务或保护模板发生变化，当前网页保留，尚未应用");return;}
              session.web.timezoneConfigurationChanged();done.accept("");
            });
          }else{session.web.timezoneConfigurationChanged();done.accept("");}
        });}catch(RuntimeException unavailable){done.accept("时区已保存；最终网页核对未完成，尚未应用");}
      });
    });
  }
  JSONObject status(){Object current=session.web==null?null:session.web.current;Operation op=operations.get(current);return status(current,op==null?"":op.epoch);}
  JSONObject status(Object nativeSession,String epoch){
    GeckoTimeZoneStore.State desired=cached;Operation op=operations.get(nativeSession);boolean current=alive(op)&&op.epoch.equals(epoch)&&accessCurrent(op),verified=current&&op.verified&&allowed(nativeSession,epoch),conflict=desired!=null&&GeckoTimeZonePolicy.protectionConflict(session.privacy.level(),desired.spec);
    String state=desired==null?"loading":!loadIssue.isEmpty()?"failed":conflict?"conflict":verified?"native-readback":current&&op.unsupported?"unsupported":current&&!op.issue.isEmpty()?"failed":"saved";
    return J.obj("schema",1,"engine","gecko","loaded",desired!=null,"desiredZone",desired==null?JSONObject.NULL:desired.spec.zoneId,"desiredRevision",desired==null?0:desired.revision,"state",state,
        "nativeSettingReadback",verified,"scope","top-browsing-context","appliedScope",verified?"top-browsing-context":"","pageObservationVerified",false,"workerCoverageVerified",false,"serviceWorkerCoverageVerified",false,"issue",!loadIssue.isEmpty()?loadIssue:conflict?"强化保护优先使用自己的时区策略，独立设置尚未生效":current?op.issue:"");
  }
  private static String token(){return UUID.randomUUID().toString().replace("-","")+UUID.randomUUID().toString().replace("-","");}
}
