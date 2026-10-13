package local.pocketchat;

import java.util.function.Consumer;
import org.json.JSONObject;

/** UI, native policy, and website observations have independent acknowledgements.
 * Repository work runs on the session's single environment writer, never the UI. */
final class IdentityTemplateController {
  final ChatSession session;
  volatile EnvironmentSpec cached;
  volatile long editSerial;
  // A durable desired edit with failed queue persistence remains reviewable, but
  // must not keep an idle browser awake or be applied by an older queue entry.
  volatile boolean queueUnavailable;
  boolean pendingWork(){return !queueUnavailable&&(session.identityApplicationPending||DeferredBrowserSettings.pending(session));}
  IdentityTemplateController(ChatSession session){this.session=session;}
  void load(){session.environmentIo.execute(()->{
    try{
      EnvironmentSpec spec=new EnvironmentSpecRepository(session.context).load();
      session.handler.post(()->{
        if(session.deleted||!currentIdentity(spec))return;
        cached=spec;restorePendingIntent(spec);prepareRuntime();session.privacy.apply();session.web.identityConfigurationReady();session.updateBrowserActivity();
      });
    }catch(Exception error){session.handler.post(()->{if(!session.deleted){session.environmentSpecIssue="环境配置记录无法读取，原文件已保留";session.web.configureIdentity(BrowserIdentitySpec.legacy(session.privacy.desktop,session.privacy.level()));session.privacy.apply();session.web.identityConfigurationReady();}});}
  });}
  void issue(String message){session.handler.post(()->{if(!session.deleted)session.environmentSpecIssue=message;});}
  boolean currentIdentity(EnvironmentSpec spec){EnvironmentSpec prior=cached;return spec.identity.generation==session.environmentGeneration&&(prior==null||prior.identity.equals(spec.identity));}
  long appliedRevision(){EnvironmentSpec value=cached;return value==null?0:value.appliedRevision;}
  void restorePendingIntent(EnvironmentSpec value){
    try{
      JSONObject active=value.applied()==null?BrowserIdentitySpec.legacy(session.privacy.desktop,session.privacy.level()).json():value.applied().browser();
      if(!new EnvironmentSpec.Configuration(active,value.desired().network).equals(value.desired())){
        BrowserIdentitySpec requested=BrowserIdentitySpec.from(value.desired().browser());
        JSONObject queued=DeferredBrowserSettings.desired(session);
        boolean matches=DeferredBrowserSettings.pending(session)&&queued.optInt("privacyLevel")==requested.protectionLevel()&&queued.optBoolean("desktopSite")==requested.desktop();
        boolean saved=requested.validate().isEmpty()&&(matches||DeferredBrowserSettings.save(session,requested.protectionLevel(),requested.desktop()));
        queueUnavailable=!saved;session.identityApplicationPending=saved;
        if(!saved)session.environmentSpecIssue="期望模板已保存，应用排队未恢复，请重新保存模板";
      }else{queueUnavailable=false;session.identityApplicationPending=DeferredBrowserSettings.pending(session);}
    }catch(Exception error){queueUnavailable=true;session.identityApplicationPending=false;session.environmentSpecIssue="期望模板无法恢复，原配置文件保留";}
  }
  void prepareRuntime(){
    EnvironmentSpec value=cached;if(value==null||session.deleted)return;
    try{
      JSONObject browser=(DeferredBrowserSettings.pending(session)||session.identityApplicationPending||queueUnavailable)
          ?value.applied()==null?BrowserIdentitySpec.legacy(session.privacy.desktop,session.privacy.level()).json():value.applied().browser()
          :value.desired().browser();
      BrowserIdentitySpec selected=BrowserIdentitySpec.from(browser);
      if(selected.validate().isEmpty())session.web.configureIdentity(selected);
    }catch(Exception error){session.environmentSpecIssue="模板无法应用，当前真实设置保持可用";}
  }
  void apply(MainActivity activity,BrowserIdentitySpec specification,Consumer<String> done){
    String invalid=specification.validate();if(!invalid.isEmpty()){done.accept(invalid);return;}
    if(session.deleted||activity.session!=session){done.accept("当前环境已改变");return;}
    long ticket=++editSerial;
    session.environmentIo.execute(()->{
      try{
        EnvironmentSpec spec=EnvironmentSpecRuntime.desireBrowser(session.context,specification.json());
        final long connection=session.connectionEpoch,policy=session.web.identityPolicyRevision;
        final boolean internal=session.internalNetwork();
        final NativeNetwork.ExitRouteReceipt receipt=internal?NativeNetwork.get(session.context).verifiedRoute:null;
        // Exact receipt validation may use service IPC, so evaluate it on the
        // environment writer and recheck its lifetime before the UI fast path.
        final boolean unchanged=alreadyApplied(spec,specification);
        session.handler.post(()->{
          if(ticket!=editSerial||session.deleted||activity.session!=session||!currentIdentity(spec)){done.accept("本次修改已由较新的配置替换");return;}
          if(unchanged&&connection==session.connectionEpoch&&policy==session.web.identityPolicyRevision
              &&internal==session.internalNetwork()&&(!internal||receipt==NativeNetwork.get(session.context).verifiedRoute)
              &&!DeferredBrowserSettings.pending(session)&&!session.identityApplicationPending
              &&actualRouteAdmitted()&&session.web.getSettings().policyAcknowledged){cached=spec;session.environmentSpecIssue="";done.accept("");return;}
          if(!DeferredBrowserSettings.save(session,specification.protectionLevel(),specification.desktop())){cached=spec;queueUnavailable=true;session.identityApplicationPending=false;session.environmentSpecIssue="期望配置已保存，应用排队失败，请重新保存模板";session.updateBrowserActivity();done.accept(session.environmentSpecIssue);return;}
          // A retained background session also drains this queue. Publish the exact
          // desired snapshot before Activity teardown can stop the editor path.
          cached=spec;queueUnavailable=false;session.environmentSpecIssue="";session.identityApplicationPending=true;
          session.updateBrowserActivity();
          // The existing deferred flow owns draft capture and safe application.
          // A template never rewrites the profile name, preferences or editor
          // draft, nor reads the SQLite catalogue on its UI completion path.
          done.accept("");
        });
      }catch(Exception error){session.handler.post(()->done.accept("环境配置未保存，原文件与当前设置保留"));}
    });
  }
  boolean alreadyApplied(EnvironmentSpec spec,BrowserIdentitySpec requested){
    if(queueUnavailable||DeferredBrowserSettings.pending(session)||session.identityApplicationPending||!actualRouteAdmitted()
        ||!session.web.getSettings().policyAcknowledged||spec.applied()==null||spec.pending()
        ||!GeckoWebView.VERSION.equals(spec.engineVersion))return false;
    try{
      if(session.internalNetwork()&&!NativeNetwork.get(session.context).verifiedRouteCurrent())return false;
      EnvironmentSpec.Configuration actual=new EnvironmentSpec.Configuration(session.web.getSettings().acceptedBrowserIdentity,route());
      return actual.equals(spec.desired())&&new EnvironmentSpec.Configuration(requested.json(),actual.network).equals(actual);
    }catch(Exception unavailable){return false;}
  }
  void legacySaved(int level,boolean desktop){editSerial++;session.environmentIo.execute(()->{
    try{
      EnvironmentSpecRepository repository=new EnvironmentSpecRepository(session.context);
      EnvironmentSpec before=repository.load();
      if(!currentIdentity(before))throw new IllegalStateException("Environment identity changed");
      BrowserIdentitySpec prior=BrowserIdentitySpec.from(before.desired().browser());
      BrowserIdentitySpec selected=BrowserIdentitySpec.legacy(desktop,level).withLocales(prior.locales);
      EnvironmentSpec next=repository.updateDesired(before.identity,before.desiredRevision,
          new EnvironmentSpec.Configuration(selected.json(),before.desired().network));
      session.handler.post(()->{if(!session.deleted){cached=next;queueUnavailable=false;acknowledge();}});
    }catch(Exception error){issue("网页设置已保存，但环境配置记录未同步，请重新保存模板");}
  });}
  EnvironmentSpec.NetworkBinding route()throws Exception{
    String mode=session.prefs.getString("networkMode","external");
    JSONObject config="internal".equals(mode)?NativeNetwork.get(session.context).settings:new JSONObject();
    return EnvironmentSpecRuntime.binding(session.context,mode,config==null?new JSONObject():J.parse(config.toString()),session.prefs.getString("proxy",""));
  }
  boolean actualRouteAdmitted(){
    return !session.deleted&&session.networkReady&&!session.offline&&session.guard.allowed()
        &&(!session.internalNetwork()||NativeNetwork.get(session.context).connectionAdmission().usable());
  }
  void acknowledge(){
    if(!actualRouteAdmitted()||!session.web.getSettings().policyAcknowledged)return;
    final long connection=session.connectionEpoch,policy=session.web.identityPolicyRevision;
    final JSONObject accepted=J.parse(session.web.getSettings().acceptedBrowserIdentity.toString());
    session.environmentIo.execute(()->{
      try{
        if(!actualRouteAdmitted()||connection!=session.connectionEpoch||policy!=session.web.identityPolicyRevision)return;
        if(session.internalNetwork()&&!NativeNetwork.get(session.context).verifiedRouteCurrent())return;
        EnvironmentSpec.NetworkBinding network=route();
        EnvironmentSpecRepository repository=new EnvironmentSpecRepository(session.context);
        EnvironmentSpec spec=repository.load();
        if(!currentIdentity(spec))return;
        if(!new EnvironmentSpec.Configuration(accepted,network).equals(spec.desired()))return;
        if(connection!=session.connectionEpoch||policy!=session.web.identityPolicyRevision||!actualRouteAdmitted())return;
        EnvironmentSpec result=repository.markApplied(spec.identity,spec.desiredRevision,GeckoWebView.VERSION);
        session.handler.post(()->{if(!session.deleted&&connection==session.connectionEpoch&&policy==session.web.identityPolicyRevision)cached=result;});
      }catch(Exception error){issue("运行配置确认未记录，设置与观测仍分别保留");}
    });
  }
  void observe(JSONObject report){
    long observedRevision=report.optLong("identityAppliedRevision");
    if(!report.optBoolean("fresh")||observedRevision<=0||!actualRouteAdmitted()||!session.web.getSettings().policyAcknowledged)return;
    String stamp=report.optString("policy"),routeStamp=report.optString("route");
    if(!stamp.equals(session.audit.policyStamp())||!routeStamp.equals(session.audit.routeStamp()))return;
    final JSONObject observation=J.parse(report.toString()),accepted=J.parse(session.web.getSettings().acceptedBrowserIdentity.toString());
    final long connection=session.connectionEpoch,policy=session.web.identityPolicyRevision;
    session.environmentIo.execute(()->{
      try{
        if(session.deleted||connection!=session.connectionEpoch||policy!=session.web.identityPolicyRevision||!actualRouteAdmitted())return;
        if(session.internalNetwork()&&!NativeNetwork.get(session.context).verifiedRouteCurrent())return;
        EnvironmentSpec.NetworkBinding network=route();
        EnvironmentSpecRepository repository=new EnvironmentSpecRepository(session.context);EnvironmentSpec spec=repository.load();
        if(!currentIdentity(spec)||spec.appliedRevision!=observedRevision||spec.applied()==null
            ||!new EnvironmentSpec.Configuration(accepted,network).equals(spec.applied()))return;
        if(session.deleted||connection!=session.connectionEpoch||policy!=session.web.identityPolicyRevision||!actualRouteAdmitted()||!stamp.equals(session.audit.policyStamp())||!routeStamp.equals(session.audit.routeStamp()))return;
        EnvironmentSpec result=repository.recordObservation(spec.identity,observedRevision,observation);
        session.handler.post(()->{if(!session.deleted&&connection==session.connectionEpoch&&policy==session.web.identityPolicyRevision)cached=result;});
      }catch(Exception error){issue("网页观测未记录为当前版本，原自检报告保留");}
    });
  }
}
