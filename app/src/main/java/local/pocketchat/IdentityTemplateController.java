package local.pocketchat;

import android.widget.EditText;
import java.util.function.Consumer;
import org.json.JSONObject;

/** UI, native policy, and website observations have independent acknowledgements.
 * Repository work runs on the session's single environment writer, never the UI. */
final class IdentityTemplateController {
  final ChatSession session;
  volatile EnvironmentSpec cached;
  volatile long editSerial;
  IdentityTemplateController(ChatSession session){this.session=session;}
  void load(){session.environmentIo.execute(()->{
    try{
      EnvironmentSpec spec=new EnvironmentSpecRepository(session.context).load();
      session.handler.post(()->{
        if(session.deleted||spec.identity.generation!=session.environmentGeneration)return;
        cached=spec;restorePendingIntent(spec);prepareRuntime();session.privacy.apply();session.web.identityConfigurationReady();
      });
    }catch(Exception error){session.handler.post(()->{if(!session.deleted){session.environmentSpecIssue="环境配置记录无法读取，原文件已保留";session.web.configureIdentity(BrowserIdentitySpec.legacy(session.privacy.wantsDesktop(),session.privacy.level()));session.privacy.apply();session.web.identityConfigurationReady();}});}
  });}
  void issue(String message){session.handler.post(()->{if(!session.deleted)session.environmentSpecIssue=message;});}
  long appliedRevision(){EnvironmentSpec value=cached;return value==null?0:value.appliedRevision;}
  void restorePendingIntent(EnvironmentSpec value){
    if(DeferredBrowserSettings.pending(session))return;
    try{
      JSONObject active=value.applied()==null?BrowserIdentitySpec.legacy(session.privacy.wantsDesktop(),session.privacy.level()).json():value.applied().browser();
      if(!new EnvironmentSpec.Configuration(active,value.desired().network).equals(value.desired())){
        BrowserIdentitySpec requested=BrowserIdentitySpec.from(value.desired().browser());
        session.identityApplicationPending=true;
        if(requested.validate().isEmpty()&&DeferredBrowserSettings.save(session,requested.protectionLevel(),requested.desktop()))session.identityApplicationPending=true;
        else session.environmentSpecIssue="期望模板已保存，应用排队未恢复，请重新保存模板";
      }
    }catch(Exception error){session.environmentSpecIssue="期望模板无法恢复，原配置文件保留";}
  }
  void prepareRuntime(){
    EnvironmentSpec value=cached;if(value==null||session.deleted)return;
    try{
      JSONObject browser=(DeferredBrowserSettings.pending(session)||session.identityApplicationPending)
          ?value.applied()==null?BrowserIdentitySpec.legacy(session.privacy.wantsDesktop(),session.privacy.level()).json():value.applied().browser()
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
        session.handler.post(()->{
          if(ticket!=editSerial||session.deleted||activity.session!=session){done.accept("本次修改已由较新的配置替换");return;}
          if(!DeferredBrowserSettings.save(session,specification.protectionLevel(),specification.desktop())){done.accept("期望配置已保存，应用排队失败，请重新保存模板");return;}
          if(activity.isDestroyed()||activity.isFinishing()){done.accept("配置已保存，空闲后应用；请在当前环境重新查看");return;}
          cached=spec;session.environmentSpecIssue="";session.identityApplicationPending=true;
          JSONObject values=EnvironmentEditorUi.current(activity);
          try{values.put("privacyLevel",specification.protectionLevel());values.put("desktopSite",specification.desktop());}catch(Exception impossible){done.accept("模板内容无效");return;}
          EditText name=new EditText(activity);name.setText(values.optString("name"));
          EnvironmentEditorUi.applySafely(activity,values,name,()->ticket==editSerial&&!session.deleted&&activity.session==session&&cached!=null&&cached.identity.equals(spec.identity)&&cached.desiredRevision==spec.desiredRevision,ok->{
            if(!ok){
              if(ticket!=editSerial||session.deleted){done.accept("本次修改已由较新的配置替换");return;}
              boolean queued=DeferredBrowserSettings.save(session,specification.protectionLevel(),specification.desktop());
              done.accept(queued?"期望配置已保存；网页状态未确认，空闲后重试应用":"期望配置已保存，未能排队应用，请重新保存模板");return;
            }
            session.identityApplicationPending=DeferredBrowserSettings.pending(session);done.accept("");
          });
        });
      }catch(Exception error){session.handler.post(()->done.accept("环境配置未保存，原文件与当前设置保留"));}
    });
  }
  void legacySaved(int level,boolean desktop){editSerial++;session.environmentIo.execute(()->{
    try{
      EnvironmentSpecRepository repository=new EnvironmentSpecRepository(session.context);
      EnvironmentSpec before=repository.load();
      BrowserIdentitySpec prior=BrowserIdentitySpec.from(before.desired().browser());
      BrowserIdentitySpec selected=BrowserIdentitySpec.legacy(desktop,level).withLocales(prior.locales);
      EnvironmentSpec next=repository.updateDesired(before.identity,before.desiredRevision,
          new EnvironmentSpec.Configuration(selected.json(),before.desired().network));
      session.handler.post(()->{if(!session.deleted){cached=next;acknowledge();}});
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
    final EnvironmentSpec.NetworkBinding network;
    try{network=route();}catch(Exception error){return;}
    session.environmentIo.execute(()->{
      try{
        if(!actualRouteAdmitted()||connection!=session.connectionEpoch||policy!=session.web.identityPolicyRevision)return;
        if(session.internalNetwork()&&!NativeNetwork.get(session.context).verifiedRouteCurrent())return;
        EnvironmentSpecRepository repository=new EnvironmentSpecRepository(session.context);
        EnvironmentSpec spec=repository.load();
        if(!new EnvironmentSpec.Configuration(accepted,network).equals(spec.desired()))return;
        if(connection!=session.connectionEpoch||policy!=session.web.identityPolicyRevision||!actualRouteAdmitted())return;
        EnvironmentSpec result=repository.markApplied(spec.identity,spec.desiredRevision,GeckoWebView.VERSION);
        session.handler.post(()->{if(!session.deleted&&connection==session.connectionEpoch&&policy==session.web.identityPolicyRevision)cached=result;});
      }catch(Exception error){issue("运行配置确认未记录，设置与观测仍分别保留");}
    });
  }
  void observe(JSONObject report){
    long observedRevision=report.optLong("identityAppliedRevision");
    if(observedRevision<=0||!actualRouteAdmitted()||!session.web.getSettings().policyAcknowledged)return;
    String stamp=report.optString("policy"),routeStamp=report.optString("route");
    if(!stamp.equals(session.audit.policyStamp())||!routeStamp.equals(session.audit.routeStamp()))return;
    final JSONObject observation=J.parse(report.toString()),accepted=J.parse(session.web.getSettings().acceptedBrowserIdentity.toString());
    final long connection=session.connectionEpoch,policy=session.web.identityPolicyRevision;
    final EnvironmentSpec.NetworkBinding network;
    try{network=route();}catch(Exception error){return;}
    session.environmentIo.execute(()->{
      try{
        if(session.deleted||connection!=session.connectionEpoch||policy!=session.web.identityPolicyRevision||!actualRouteAdmitted())return;
        EnvironmentSpecRepository repository=new EnvironmentSpecRepository(session.context);EnvironmentSpec spec=repository.load();
        if(spec.appliedRevision!=observedRevision||spec.applied()==null
            ||!new EnvironmentSpec.Configuration(accepted,network).equals(spec.applied()))return;
        EnvironmentSpec result=repository.recordObservation(spec.identity,observedRevision,observation);
        session.handler.post(()->{if(!session.deleted&&connection==session.connectionEpoch&&policy==session.web.identityPolicyRevision)cached=result;});
      }catch(Exception error){issue("网页观测未记录为当前版本，原自检报告保留");}
    });
  }
}
