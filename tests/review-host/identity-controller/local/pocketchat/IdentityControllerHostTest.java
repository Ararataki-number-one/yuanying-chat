package local.pocketchat;

import java.util.Collections;
import org.json.JSONObject;

/** Actual controller execution with deterministic Android/UI/I/O doubles. */
public final class IdentityControllerHostTest {
  static int checks;
  static void check(boolean condition,String message){checks++;if(!condition)throw new AssertionError(message);}
  static EnvironmentSpec.NetworkBinding route(String id){return new EnvironmentSpec.NetworkBinding("external","","","",id,"manual","", "", "");}
  static ChatSession fixture() {
    ChatSession session=new ChatSession();EnvironmentSpec.NetworkBinding route=route("fixed");session.context.actual=route;
    BrowserIdentitySpec browser=BrowserIdentitySpec.preset(BrowserIdentitySpec.MOBILE);
    EnvironmentSpec.Identity id=new EnvironmentSpec.Identity(0,0,"00000000-0000-0000-0000-000000000001");
    EnvironmentSpecRepository.value=EnvironmentSpec.initial(id,new EnvironmentSpec.Configuration(browser.json(),route));
    EnvironmentSpecRepository.readFailure=false;
    EnvironmentSpecRepository.appliedWrites=EnvironmentSpecRepository.observedWrites=EnvironmentEditorUi.writes=0;EnvironmentEditorUi.pending.clear();
    NativeNetwork.instance.exactReceipt=true;NativeNetwork.instance.admission=NetworkHealthPolicy.Admission.VERIFIED;
    session.web.settings.acceptedBrowserIdentity=browser.json();session.identity=new IdentityTemplateController(session);session.identity.cached=EnvironmentSpecRepository.value;
    return session;
  }
  static void settle(ChatSession session){session.environmentIo.run();session.handler.run();}
  static void staleEditorCompletion(){
    ChatSession session=fixture();MainActivity activity=new MainActivity(session);
    session.identity.apply(activity,BrowserIdentitySpec.preset(BrowserIdentitySpec.DESKTOP),issue->{});settle(session);
    EnvironmentEditorUi.Pending older=EnvironmentEditorUi.pending.get(0);
    session.identity.apply(activity,BrowserIdentitySpec.preset(BrowserIdentitySpec.RFP),issue->{});settle(session);
    check(!older.current.getAsBoolean(),"new desired configuration revokes old precommit guard");older.finish();
    check(EnvironmentEditorUi.writes==0,"old draft capture completion cannot write browser preferences");
    EnvironmentEditorUi.pending.get(1).finish();check(EnvironmentEditorUi.writes==1,"latest guarded edit can commit");
  }
  static void newerEditBeforeMainCallback(){
    ChatSession session=fixture();MainActivity activity=new MainActivity(session);
    session.identity.apply(activity,BrowserIdentitySpec.preset(BrowserIdentitySpec.DESKTOP),issue->{});
    session.environmentIo.run();
    session.identity.apply(activity,BrowserIdentitySpec.preset(BrowserIdentitySpec.RFP),issue->{});
    session.environmentIo.run();session.handler.run();
    check(EnvironmentEditorUi.pending.size()==1,"stale UI completion never starts application");
    check(session.queuedSaves==1,"stale worker completion never overwrites deferred preferences");
    check(session.queuedLevel==2&&!session.queuedDesktop,"deferred queue contains the latest desired browser policy");
  }
  static void legacyAndSessionSupersession(){
    ChatSession session=fixture();MainActivity activity=new MainActivity(session);
    session.identity.apply(activity,BrowserIdentitySpec.preset(BrowserIdentitySpec.DESKTOP),issue->{});settle(session);
    EnvironmentEditorUi.Pending old=EnvironmentEditorUi.pending.get(0);
    session.identity.legacySaved(0,false);check(!old.current.getAsBoolean(),"legacy settings invalidate prior template capture");old.finish();
    check(EnvironmentEditorUi.writes==0,"superseded template cannot commit after legacy edit");
    settle(session);
    check("compatibility".equals(EnvironmentSpecRepository.value.desired().browser().optString("privacy")),"latest legacy settings become desired configuration");
    session=fixture();activity=new MainActivity(session);
    session.identity.apply(activity,BrowserIdentitySpec.preset(BrowserIdentitySpec.DESKTOP),issue->{});session.environmentIo.run();activity.session=new ChatSession();session.handler.run();
    check(EnvironmentEditorUi.pending.isEmpty(),"changed activity session cannot receive an old environment edit");
  }
  static void pendingStartupPolicy()throws Exception{
    ChatSession session=fixture();EnvironmentSpec base=EnvironmentSpecRepository.value;
    EnvironmentSpec applied=base.withApplied(1,"host-only",1);
    BrowserIdentitySpec next=BrowserIdentitySpec.preset(BrowserIdentitySpec.DESKTOP).withLocales(Collections.singletonList("en-US"));
    session.identity.cached=applied.withDesired(1,new EnvironmentSpec.Configuration(next.json(),applied.desired().network));session.deferred=true;
    session.identity.prepareRuntime();check(BrowserIdentitySpec.MOBILE.equals(session.web.configured.templateId),"pending startup retains last applied template");
    session.deferred=false;session.identity.prepareRuntime();check(BrowserIdentitySpec.DESKTOP.equals(session.web.configured.templateId),"idle policy preparation selects desired template");
  }
  static void interruptedDesiredPersistence()throws Exception{
    ChatSession session=fixture();EnvironmentSpec base=EnvironmentSpecRepository.value;
    EnvironmentSpec applied=base.withApplied(1,"host-only",1);
    BrowserIdentitySpec future=BrowserIdentitySpec.preset(BrowserIdentitySpec.DESKTOP).withLocales(Collections.singletonList("en-US"));
    EnvironmentSpecRepository.value=applied.withDesired(1,new EnvironmentSpec.Configuration(future.json(),applied.desired().network));
    // Simulate a process exit after sealed desired write but before preference
    // queue write. A restart must recover the intent without applying it early.
    session.deferred=false;session.identity.cached=null;session.identity.load();settle(session);
    check(session.deferred,"restart restores deferred browser intent from sealed desired/applied separation");
    check(BrowserIdentitySpec.MOBILE.equals(session.web.configured.templateId),"interrupted save restart retains applied browser until safe drain");
    check(session.queuedDesktop&&session.queuedLevel==1,"recovered intent keeps the saved target display and policy");
  }
  static void startupConfigurationGate(){
    ChatSession session=fixture();session.identity.cached=null;session.identity.load();
    check(!session.web.identityPrepared,"native opening waits for environment configuration I/O");
    session.environmentIo.run();check(!session.web.identityPrepared,"queued main callback is required before identity gate opens");
    session.handler.run();check(session.web.identityPrepared&&session.privacy.applications==1,"configuration and privacy application precede opening acknowledgement");
    session=fixture();session.identity.cached=null;session.privacy.protection=0;session.privacy.desktop=true;EnvironmentSpecRepository.readFailure=true;
    session.identity.load();settle(session);
    check(session.web.identityPrepared&&BrowserIdentitySpec.COMPATIBLE_DESKTOP.equals(session.web.configured.templateId),"unreadable sealed configuration opens only with actual legacy policy");
    check(session.identity.cached==null&&EnvironmentSpecRepository.appliedWrites==0,"read failure fallback never claims persisted environment applied");
    EnvironmentSpecRepository.readFailure=false;
    session=fixture();session.identity.load();session.deleted=true;settle(session);
    check(!session.web.identityPrepared,"deleted environment cannot open after late configuration callback");
  }
  static void failedQueueRestoration()throws Exception{
    ChatSession session=fixture();EnvironmentSpec base=EnvironmentSpecRepository.value;
    EnvironmentSpec applied=base.withApplied(1,"host-only",1);
    BrowserIdentitySpec desired=BrowserIdentitySpec.preset(BrowserIdentitySpec.DESKTOP).withLocales(Collections.singletonList("en-US"));
    EnvironmentSpecRepository.value=applied.withDesired(1,new EnvironmentSpec.Configuration(desired.json(),applied.desired().network));
    session.failQueue=true;session.identity.cached=null;session.identity.load();settle(session);
    check(session.web.identityPrepared&&BrowserIdentitySpec.MOBILE.equals(session.web.configured.templateId),"failed queue restoration opens only the actual applied browser policy");
    check(BrowserIdentitySpec.DESKTOP.equals(session.identity.cached.desired().browser().optString("templateId")),"failed queue restoration retains desired configuration for later retry");
  }
  static void acknowledgements()throws Exception{
    ChatSession session=fixture();session.context.actual=route("different");session.identity.acknowledge();settle(session);
    check(EnvironmentSpecRepository.appliedWrites==0,"browser acceptance cannot acknowledge a different actual route");
    session=fixture();session.identity.acknowledge();session.connectionEpoch++;settle(session);
    check(EnvironmentSpecRepository.appliedWrites==0,"changed connection epoch rejects queued acknowledgement");
    session=fixture();session.identity.acknowledge();session.web.identityPolicyRevision++;settle(session);
    check(EnvironmentSpecRepository.appliedWrites==0,"changed native policy generation rejects queued acknowledgement");
    session=fixture();session.prefs.mode="internal";NativeNetwork.instance.exactReceipt=false;session.identity.acknowledge();settle(session);
    check(EnvironmentSpecRepository.appliedWrites==0,"unverified service route never receives full environment acknowledgement");
    session=fixture();session.identity.acknowledge();settle(session);
    check(EnvironmentSpecRepository.appliedWrites==1&&session.identity.appliedRevision()==1,"matching admitted route and accepted browser are acknowledged");
    session.guard.allowed=false;session.identity.acknowledge();settle(session);check(EnvironmentSpecRepository.appliedWrites==1,"blocked route cannot add acknowledgement");
  }
  static void observations()throws Exception{
    ChatSession session=fixture();session.identity.acknowledge();settle(session);
    JSONObject report=J.obj("identityAppliedRevision",1,"policy","policy","route","route","fresh",true);
    session.identity.observe(report);settle(session);check(EnvironmentSpecRepository.observedWrites==1,"matching observation records its captured applied revision");
    report.put("identityAppliedRevision",2);session.identity.observe(report);settle(session);check(EnvironmentSpecRepository.observedWrites==1,"observation cannot invent a newer applied revision");
    report.put("identityAppliedRevision",1);report.put("policy","old-policy");session.identity.observe(report);settle(session);check(EnvironmentSpecRepository.observedWrites==1,"stale page policy observation is rejected");
    report.put("policy","policy");session.identity.observe(report);session.connectionEpoch++;settle(session);check(EnvironmentSpecRepository.observedWrites==1,"connection changes reject queued observation persistence");
  }
  public static void main(String[] arguments)throws Exception{
    staleEditorCompletion();newerEditBeforeMainCallback();legacyAndSessionSupersession();pendingStartupPolicy();interruptedDesiredPersistence();startupConfigurationGate();failedQueueRestoration();acknowledgements();observations();
    System.out.println("{\"passed\":"+checks+",\"actualAndroidExecution\":false,\"scope\":\"Production IdentityTemplateController/model/template with queued Android UI, binder and persistence doubles; no Gecko, Keystore or real draft capture\"}");
  }
}
