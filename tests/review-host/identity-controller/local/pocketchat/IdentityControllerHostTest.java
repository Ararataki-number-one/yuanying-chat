package local.pocketchat;

import java.util.Collections;
import org.json.JSONObject;

/** Actual controller execution with deterministic Android/UI/I/O doubles. */
public final class IdentityControllerHostTest {
  static int checks;static final org.json.JSONArray assertions=new org.json.JSONArray();
  static void check(boolean condition,String message){checks++;assertions.put(J.obj("name",message,"pass",condition));if(!condition)throw new AssertionError(message);}
  static EnvironmentSpec.NetworkBinding route(String id){return new EnvironmentSpec.NetworkBinding("external","","","",id,"manual","", "", "");}
  static ChatSession fixture() {
    ChatSession session=new ChatSession();session.context.writer=session.environmentIo;EnvironmentSpec.NetworkBinding route=route("fixed");session.context.actual=route;
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
    check(session.deferred&&session.queuedDesktop,"first template is saved as a deferred intent");
    session.identity.apply(activity,BrowserIdentitySpec.preset(BrowserIdentitySpec.RFP),issue->{});settle(session);
    check(session.queuedLevel==2&&!session.queuedDesktop,"newer template replaces the earlier target before safe application");
    check(EnvironmentEditorUi.pending.isEmpty()&&EnvironmentEditorUi.writes==0,"template save never rewrites editor metadata or starts inline draft application");
  }
  static void newerEditBeforeMainCallback(){
    ChatSession session=fixture();MainActivity activity=new MainActivity(session);
    session.identity.apply(activity,BrowserIdentitySpec.preset(BrowserIdentitySpec.DESKTOP),issue->{});
    session.environmentIo.run();
    session.identity.apply(activity,BrowserIdentitySpec.preset(BrowserIdentitySpec.RFP),issue->{});
    session.environmentIo.run();session.handler.run();
    check(EnvironmentEditorUi.pending.isEmpty(),"template completions do not mutate profile metadata");
    check(session.queuedSaves==1,"stale worker completion never overwrites deferred preferences");
    check(session.queuedLevel==2&&!session.queuedDesktop,"deferred queue contains the latest desired browser policy");
  }
  static void legacyAndSessionSupersession(){
    ChatSession session=fixture();MainActivity activity=new MainActivity(session);
    session.identity.apply(activity,BrowserIdentitySpec.preset(BrowserIdentitySpec.DESKTOP),issue->{});session.environmentIo.run();
    session.identity.legacySaved(0,false);session.handler.run();
    check(session.queuedSaves==0,"legacy edit invalidates prior template before deferred preference publication");
    settle(session);
    check("compatibility".equals(EnvironmentSpecRepository.value.desired().browser().optString("privacy")),"latest legacy settings become desired configuration");
    session=fixture();activity=new MainActivity(session);
    session.identity.apply(activity,BrowserIdentitySpec.preset(BrowserIdentitySpec.DESKTOP),issue->{});session.environmentIo.run();activity.session=new ChatSession();session.handler.run();
    check(session.queuedSaves==0&&EnvironmentEditorUi.pending.isEmpty(),"changed activity session cannot receive an old environment edit");
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
    check(!session.identityApplicationPending&&!session.identity.pendingWork(),"failed queue restoration cannot leave a maintenance flag without runnable work");
    check(session.identity.queueUnavailable,"failed durable queue remains blocked and explicitly retryable");
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
    session=fixture();session.identity.acknowledge();check(session.context.bindingReads==0,"acknowledgement defers catalog reads until worker execution");settle(session);
    check(session.context.bindingReads==1,"acknowledgement performs binding read on environment writer");
    check(EnvironmentSpecRepository.appliedWrites==1&&session.identity.appliedRevision()==1,"matching admitted route and accepted browser are acknowledged");
    session.guard.allowed=false;session.identity.acknowledge();settle(session);check(EnvironmentSpecRepository.appliedWrites==1,"blocked route cannot add acknowledgement");
  }
  static void observations()throws Exception{
    ChatSession session=fixture();session.identity.acknowledge();settle(session);
    JSONObject report=J.obj("identityAppliedRevision",1,"policy","policy","route","route","fresh",true);
    session.identity.observe(report);check(session.context.bindingReads==1,"observation cannot read catalog on caller UI thread");settle(session);check(EnvironmentSpecRepository.observedWrites==1,"matching observation records its captured applied revision");
    report.put("fresh",false);session.identity.observe(report);settle(session);check(EnvironmentSpecRepository.observedWrites==1,"stale observation cannot be persisted as current");report.put("fresh",true);
    report.put("identityAppliedRevision",2);session.identity.observe(report);settle(session);check(EnvironmentSpecRepository.observedWrites==1,"observation cannot invent a newer applied revision");
    report.put("identityAppliedRevision",1);report.put("policy","old-policy");session.identity.observe(report);settle(session);check(EnvironmentSpecRepository.observedWrites==1,"stale page policy observation is rejected");
    report.put("policy","policy");session.identity.observe(report);session.connectionEpoch++;settle(session);check(EnvironmentSpecRepository.observedWrites==1,"connection changes reject queued observation persistence");
  }
  static void finishedActivityPublishesAndWakes(boolean destroyed)throws Exception{
    ChatSession session=fixture();MainActivity activity=new MainActivity(session);
    EnvironmentSpecRepository.value=EnvironmentSpecRepository.value.withApplied(1,GeckoWebView.VERSION,1);
    session.identity.cached=EnvironmentSpecRepository.value;
    BrowserIdentitySpec desired=BrowserIdentitySpec.preset(BrowserIdentitySpec.MOBILE).withLocales(Collections.singletonList("ja-JP"));
    session.identity.apply(activity,desired,issue->{});session.environmentIo.run();
    activity.destroyed=destroyed;activity.finishing=!destroyed;session.paused=true;session.tickQueued=false;
    session.handler.run();
    check(session.deferred&&session.identityApplicationPending,"Activity teardown keeps a deferred browser intent");
    check(session.activityUpdates==1&&!session.paused&&session.tickQueued,"late saved intent wakes retained background session");
    check(session.identity.cached==EnvironmentSpecRepository.value,"Activity teardown publishes the persisted desired snapshot");
    session.deferred=false;session.identityApplicationPending=false;session.identity.prepareRuntime();
    check(session.web.configured.locales.equals(Collections.singletonList("ja-JP")),"background drain prepares the saved language rather than the old cache");
    check(EnvironmentEditorUi.pending.isEmpty(),"finished Activity is not used to capture website drafts");
  }
  static ChatSession acknowledgedFixture()throws Exception{
    ChatSession session=fixture();EnvironmentSpecRepository.value=EnvironmentSpecRepository.value.withApplied(1,GeckoWebView.VERSION,1);session.identity.cached=EnvironmentSpecRepository.value;return session;
  }
  static void unchangedTemplateRequiresActualAcknowledgement()throws Exception{
    ChatSession session=acknowledgedFixture();session.identity.apply(new MainActivity(session),BrowserIdentitySpec.preset(BrowserIdentitySpec.MOBILE),issue->{});settle(session);
    check(session.queuedSaves==0&&EnvironmentEditorUi.pending.isEmpty(),"unchanged admitted and acknowledged template does not reload the page");
    session=acknowledgedFixture();session.context.actual=route("different");session.identity.apply(new MainActivity(session),BrowserIdentitySpec.preset(BrowserIdentitySpec.MOBILE),issue->{});settle(session);check(session.queuedSaves==1,"route mismatch cannot use no-op fast path");
    session=acknowledgedFixture();session.prefs.mode="internal";NativeNetwork.instance.exactReceipt=false;session.identity.apply(new MainActivity(session),BrowserIdentitySpec.preset(BrowserIdentitySpec.MOBILE),issue->{});settle(session);check(session.queuedSaves==1,"internal route needs a current exact receipt for no-op");
    session=acknowledgedFixture();session.web.settings.policyAcknowledged=false;session.identity.apply(new MainActivity(session),BrowserIdentitySpec.preset(BrowserIdentitySpec.MOBILE),issue->{});settle(session);check(session.queuedSaves==1,"unacknowledged native settings cannot use no-op");
    session=acknowledgedFixture();session.deferred=true;session.identity.apply(new MainActivity(session),BrowserIdentitySpec.preset(BrowserIdentitySpec.MOBILE),issue->{});settle(session);check(session.queuedSaves==1,"existing deferred queue cannot be skipped as unchanged");
    session=acknowledgedFixture();session.guard.allowed=false;session.identity.apply(new MainActivity(session),BrowserIdentitySpec.preset(BrowserIdentitySpec.MOBILE),issue->{});settle(session);check(session.queuedSaves==1,"blocked route cannot use no-op");
    session=acknowledgedFixture();session.prefs.mode="internal";session.identity.apply(new MainActivity(session),BrowserIdentitySpec.preset(BrowserIdentitySpec.MOBILE),issue->{});session.environmentIo.run();NativeNetwork.instance.verifiedRoute=new NativeNetwork.ExitRouteReceipt();session.handler.run();check(session.queuedSaves==1,"receipt replaced after worker validation cannot use UI no-op");
    session=acknowledgedFixture();session.identity.apply(new MainActivity(session),BrowserIdentitySpec.preset(BrowserIdentitySpec.MOBILE),issue->{});session.environmentIo.run();session.connectionEpoch++;session.handler.run();check(session.queuedSaves==1,"connection changed after worker validation cannot use UI no-op");
    session=acknowledgedFixture();EnvironmentSpecRepository.value=EnvironmentSpecRepository.value.withApplied(1,"older-engine",1);session.identity.apply(new MainActivity(session),BrowserIdentitySpec.preset(BrowserIdentitySpec.MOBILE),issue->{});settle(session);check(session.queuedSaves==1,"old engine acknowledgement cannot use no-op");
  }
  static void templateDialogKeepsLatestLanguage()throws Exception{
    ChatSession session=fixture();MainActivity activity=new MainActivity(session);android.widget.Spinner.instances.clear();
    final BrowserIdentitySpec[] last={null};
    FingerprintTemplateUi.show(activity,(selected,done)->{try{EnvironmentSpec old=EnvironmentSpecRepository.value;EnvironmentSpecRepository.value=old.withDesired(old.desiredRevision,new EnvironmentSpec.Configuration(selected.json(),old.desired().network));last[0]=selected;done.accept("");}catch(Exception error){throw new AssertionError(error);}});
    settle(session);
    android.app.AlertDialog dialog=android.app.AlertDialog.latest;
    android.widget.Spinner templates=android.widget.Spinner.instances.get(0),languages=android.widget.Spinner.instances.get(1);
    languages.setSelection(4);dialog.getButton(android.app.AlertDialog.BUTTON_POSITIVE).click();settle(session);settle(session);
    check(last[0].locales.equals(Collections.singletonList("ja-JP")),"template dialog saves an explicit language");
    templates.setSelection(1);languages.setSelection(0);dialog.getButton(android.app.AlertDialog.BUTTON_POSITIVE).click();settle(session);settle(session);
    check(last[0].desktop()&&last[0].locales.equals(Collections.singletonList("ja-JP")),"keep current language uses previous save in the same open dialog");
    EnvironmentSpecRepository.readFailure=true;dialog.getButton(android.app.AlertDialog.BUTTON_POSITIVE).click();settle(session);
    check(last[0].desktop()&&last[0].locales.equals(Collections.singletonList("ja-JP")),"unreadable current language does not overwrite prior desired settings");
    check(dialog.getButton(android.app.AlertDialog.BUTTON_POSITIVE).enabled,"read failure re-enables template editing");EnvironmentSpecRepository.readFailure=false;
  }
  static void failedQueueDoesNotApplyOlderIntent()throws Exception{
    ChatSession session=acknowledgedFixture();MainActivity activity=new MainActivity(session);session.deferred=true;session.queuedLevel=0;session.queuedDesktop=false;session.failQueue=true;
    final String[] issue={""};session.identity.apply(activity,BrowserIdentitySpec.preset(BrowserIdentitySpec.DESKTOP),value->issue[0]=value);settle(session);
    check(!issue[0].isEmpty()&&session.identity.queueUnavailable,"failed new queue is actionable and cannot drain an older entry");
    check(!session.identityApplicationPending&&!session.identity.pendingWork()&&!session.tickQueued,"failed persistence does not keep idle background maintenance running");
    check(BrowserIdentitySpec.DESKTOP.equals(session.identity.cached.desired().browser().optString("templateId")),"successful desired write remains available for explicit retry");
    session.identity.prepareRuntime();check(BrowserIdentitySpec.MOBILE.equals(session.web.configured.templateId),"unqueued desired configuration never replaces actual applied policy");
    check(EnvironmentEditorUi.pending.isEmpty(),"queue failure cannot begin draft capture or webpage reconfiguration");
    session.failQueue=false;session.identity.apply(activity,BrowserIdentitySpec.preset(BrowserIdentitySpec.DESKTOP),value->issue[0]=value);settle(session);
    check(!session.identity.queueUnavailable&&session.identity.pendingWork()&&session.queuedDesktop&&session.queuedLevel==1,"explicit retry restores only the latest durable target");
  }
  static void reusedIdentityAndReceiptFences()throws Exception{
    ChatSession session=fixture();session.identity.acknowledge();EnvironmentSpec old=EnvironmentSpecRepository.value;
    EnvironmentSpecRepository.value=EnvironmentSpec.initial(new EnvironmentSpec.Identity(0,1,"00000000-0000-0000-0000-000000000002"),old.desired());settle(session);
    check(EnvironmentSpecRepository.appliedWrites==0,"old session cannot acknowledge a reused environment generation");
    session=fixture();session.identity.acknowledge();settle(session);
    JSONObject report=J.obj("identityAppliedRevision",1,"policy","policy","route","route","fresh",true);
    session.prefs.mode="internal";NativeNetwork.instance.exactReceipt=false;session.identity.observe(report);settle(session);
    check(EnvironmentSpecRepository.observedWrites==0,"observation requires the actual current internal route receipt");
    session=fixture();session.identity.acknowledge();settle(session);session.identity.observe(report);session.deleted=true;settle(session);
    check(EnvironmentSpecRepository.observedWrites==0,"deleted session cannot persist a queued observation");
  }
  static void explicitFailedOverrideMirrorsAndWakes()throws Exception{
    ChatSession session=acknowledgedFixture();EnvironmentSpec applied=EnvironmentSpecRepository.value;
    BrowserIdentitySpec failed=BrowserIdentitySpec.preset(BrowserIdentitySpec.COMPATIBLE).withLocales(Collections.singletonList("ja-JP"));
    EnvironmentSpecRepository.value=applied.withDesired(applied.desiredRevision,new EnvironmentSpec.Configuration(failed.json(),applied.desired().network));session.identity.cached=EnvironmentSpecRepository.value;
    session.identity.queueUnavailable=true;session.identityApplicationPending=false;
    // The editor has accepted an explicit B-to-current-A override and saved its
    // existing preference queue; failed C must not come back after this mirror.
    session.deferred=true;session.queuedLevel=1;session.queuedDesktop=false;session.paused=true;session.tickQueued=false;
    session.identity.legacySaved(1,false);settle(session);
    check(BrowserIdentitySpec.MOBILE.equals(EnvironmentSpecRepository.value.desired().browser().optString("templateId")),"explicit failed override replaces desired C even when display/privacy equal applied A");
    check(!session.identity.queueUnavailable&&session.identityApplicationPending&&session.identity.pendingWork(),"successful override mirror re-enables the saved safe queue");
    check(!session.paused&&session.tickQueued&&session.activityUpdates==1,"override mirror wakes the retained background environment");
    check(EnvironmentSpecRepository.value.appliedRevision==applied.appliedRevision,"override mirror cannot invent a newer applied policy");
  }
  public static void main(String[] arguments)throws Exception{
    explicitFailedOverrideMirrorsAndWakes();failedQueueDoesNotApplyOlderIntent();reusedIdentityAndReceiptFences();finishedActivityPublishesAndWakes(false);finishedActivityPublishesAndWakes(true);unchangedTemplateRequiresActualAcknowledgement();templateDialogKeepsLatestLanguage();staleEditorCompletion();newerEditBeforeMainCallback();legacyAndSessionSupersession();pendingStartupPolicy();interruptedDesiredPersistence();startupConfigurationGate();failedQueueRestoration();acknowledgements();observations();
    System.out.println(J.obj("schema",1,"status","passed","passed",checks,"total",checks,"checks",assertions,"actualAndroidExecution",false,"scope","Production IdentityTemplateController and FingerprintTemplateUi/model with queued UI/widgets/binder/persistence doubles; no Android, Gecko, Keystore or real draft capture").toString());
  }
}
