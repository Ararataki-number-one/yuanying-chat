package local.pocketchat;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.Executor;
import java.util.function.BooleanSupplier;
import java.util.function.Consumer;
import org.json.JSONObject;

/** Host doubles for Android/UI, persistence I/O and service access. The controller,
 * immutable model and template validation under test are production sources. */
final class WorkQueue implements Executor {
  static WorkQueue current;final String lane;
  WorkQueue(){this("unspecified");}WorkQueue(String lane){this.lane=lane;}
  final ArrayDeque<Runnable> tasks=new ArrayDeque<>();
  public void execute(Runnable work){tasks.add(work);}
  boolean post(Runnable work){tasks.add(work);return true;}
  void run(){WorkQueue old=current;current=this;try{while(!tasks.isEmpty())tasks.remove().run();}finally{current=old;}}
}
final class FakeContext {EnvironmentSpec.NetworkBinding actual;WorkQueue writer;int bindingReads;}
// Theme presentation is exercised on Android; keep this controller fixture's dialog double.
final class AppAppearance {static android.app.AlertDialog.Builder dialog(Object context){return new android.app.AlertDialog.Builder(context);}}
// Layout and actual touch visibility are verified by run_ui_visuals on Android.
// This double keeps the production save callback executable in controller tests.
final class ReferenceUi {
  static final class Modal {
    static Modal latest;final android.widget.LinearLayout body;final android.widget.Button positive;boolean showing;
    Modal(MainActivity activity,String title){body=new android.widget.LinearLayout(activity);positive=new android.widget.Button(activity);}
    void buttons(String secondary,Runnable close,String primary,Runnable save){positive.setText(primary);positive.setOnClickListener(view->save.run());}
    android.widget.Button primary(){return positive;}
    void show(){showing=true;latest=this;}boolean isShowing(){return showing;}void dismiss(){showing=false;}
  }
}
final class FakePrefs {
  String mode="external",proxy="";
  String getString(String name,String fallback){return "networkMode".equals(name)?mode:"proxy".equals(name)?proxy:fallback;}
}
final class FakeGuard {boolean allowed=true;boolean allowed(){return allowed;}}
final class FakeAudit {boolean running,reportCurrent=true;JSONObject report=new JSONObject();String policy="policy",route="route";String policyStamp(){return policy;}String routeStamp(){return route;}boolean observationCurrent(JSONObject ignored){return reportCurrent;}}
class GeckoSettings {boolean policyAcknowledged=true;String policyError="";JSONObject acceptedBrowserIdentity=new JSONObject();String[] requestedLocales=new String[0],expectedSdkLocales=new String[0];}
final class FakeSettings extends GeckoSettings {}
final class FakeWeb {
  long identityPolicyRevision=1;final FakeSettings settings=new FakeSettings();BrowserIdentitySpec configured;
  boolean identityPrepared,bootstrapBlocked;
  boolean protectionBootstrapBlocked(){return bootstrapBlocked;}
  String protectionSummary(){return bootstrapBlocked?"强化保护失败（未打开页面）":"原生保护设置已确认";}
  FakeSettings getSettings(){return settings;}
  void configureIdentity(BrowserIdentitySpec specification){configured=specification;}
  void identityConfigurationReady(){if(configured==null)throw new AssertionError("Identity gate opened before configuration");identityPrepared=true;}
}
final class BrowserPrivacy {
  int protection=1,applications;boolean desktop;
  int level(){return protection;}boolean wantsDesktop(){return desktop;}void apply(){applications++;}
}
final class ChatSession {
  final FakeContext context=new FakeContext();final FakePrefs prefs=new FakePrefs();
  final WorkQueue environmentIo=new WorkQueue("environmentIo"),handler=new WorkQueue("main");
  final FakeGuard guard=new FakeGuard();final FakeAudit audit=new FakeAudit();final FakeWeb web=new FakeWeb();
  final BrowserPrivacy privacy=new BrowserPrivacy();
  boolean deleted,offline,networkReady=true,identityApplicationPending,deferred,failQueue,configurationCapture,busy;
  int bootstrapApplies;
  int environmentGeneration,queuedLevel,queuedSaves;boolean queuedDesktop;
  long connectionEpoch=1;String environmentSpecIssue="";IdentityTemplateController identity;
  int activityUpdates;boolean paused,tickQueued;
  void updateBrowserActivity(){activityUpdates++;if(identity!=null&&identity.pendingWork()){paused=false;tickQueued=true;}else{paused=true;tickQueued=false;}}
  final WebStore webStore=new WebStore(environmentIo);
  void applyIdentityTemplate(MainActivity activity,BrowserIdentitySpec specification,Consumer<String> done){identity.apply(activity,specification,done);}
  boolean internalNetwork(){return "internal".equals(prefs.mode);}
}
final class WebStore {final WorkQueue worker;WebStore(WorkQueue worker){this.worker=worker;}}
final class MainActivity {
  ChatSession session;boolean destroyed,finishing;MainActivity(ChatSession session){this.session=session;}
  boolean isDestroyed(){return destroyed;}boolean isFinishing(){return finishing;}
  int dp(int value){return value;}
  android.widget.TextView label(String text,int size,int color){android.widget.TextView view=new android.widget.TextView(this);view.setText(text);return view;}
}
final class GeckoWebView {static final String VERSION="GeckoView host-controller-fixture";}
final class ProfileUi {static boolean working(ChatSession session){return session.busy;}}
final class NativeNetwork {
  static final class ExitRouteReceipt {}
  ExitRouteReceipt verifiedRoute=new ExitRouteReceipt();
  static final NativeNetwork instance=new NativeNetwork();JSONObject settings=new JSONObject();
  boolean exactReceipt=true;NetworkHealthPolicy.Admission admission=NetworkHealthPolicy.Admission.VERIFIED;
  static NativeNetwork get(FakeContext context){return instance;}
  String snapshotLane="";
  boolean verifiedRouteCurrent(){snapshotLane=WorkQueue.current==null?"unqueued":WorkQueue.current.lane;if("main".equals(snapshotLane))throw new AssertionError("Service snapshot must not run on UI lane");return exactReceipt;}
  NetworkHealthPolicy.Admission connectionAdmission(){return admission;}
}
final class DeferredBrowserSettings {
  static boolean pending(ChatSession session){return session.deferred;}
  static JSONObject desired(ChatSession session){return J.obj("privacyLevel",session.deferred?session.queuedLevel:session.privacy.level(),"desktopSite",session.deferred?session.queuedDesktop:session.privacy.wantsDesktop());}
  static boolean save(ChatSession session,int level,boolean desktop){if(session.failQueue)return false;session.deferred=true;session.queuedLevel=level;session.queuedDesktop=desktop;session.queuedSaves++;return true;}
  static void apply(ChatSession session){if(!session.deferred)throw new AssertionError("No durable desired queue");session.bootstrapApplies++;session.privacy.protection=session.queuedLevel;session.privacy.desktop=session.queuedDesktop;session.deferred=false;session.identityApplicationPending=false;}
}
final class EnvironmentSpecRepository {
  static EnvironmentSpec value;static int appliedWrites,observedWrites;
  static boolean readFailure;
  EnvironmentSpecRepository(FakeContext context){}
  EnvironmentSpec load()throws java.io.IOException{if(readFailure)throw new java.io.IOException("Synthetic encrypted read failure");return value;}
  EnvironmentSpec updateDesired(EnvironmentSpec.Identity expected,long revision,EnvironmentSpec.Configuration configuration)throws Exception{
    if(!value.identity.equals(expected))throw new java.io.IOException("Identity changed");
    return value=value.withDesired(revision,configuration);
  }
  EnvironmentSpec markApplied(EnvironmentSpec.Identity expected,long revision,String engine)throws Exception{
    if(!value.identity.equals(expected))throw new java.io.IOException("Identity changed");
    value=value.withApplied(revision,engine,1);appliedWrites++;return value;
  }
  EnvironmentSpec recordObservation(EnvironmentSpec.Identity expected,long revision,JSONObject observation)throws Exception{
    if(!value.identity.equals(expected))throw new java.io.IOException("Identity changed");
    value=value.withObservation(revision,observation,1);observedWrites++;return value;
  }
}
final class EnvironmentSpecRuntime {
  static EnvironmentSpec desireBrowser(FakeContext context,JSONObject browser)throws Exception{
    EnvironmentSpec before=EnvironmentSpecRepository.value;
    return new EnvironmentSpecRepository(context).updateDesired(before.identity,before.desiredRevision,new EnvironmentSpec.Configuration(browser,before.desired().network));
  }
  static EnvironmentSpec.NetworkBinding binding(FakeContext context,String mode,JSONObject settings,String proxy){if(WorkQueue.current!=context.writer)throw new AssertionError("Catalog binding I/O outside environment writer");context.bindingReads++;return context.actual;}
}
final class EnvironmentEditorUi {
  static int writes;static final List<Pending> pending=new ArrayList<>();
  static final class Pending {
    final MainActivity activity;final JSONObject values;final BooleanSupplier current;final Consumer<Boolean> done;
    Pending(MainActivity activity,JSONObject values,BooleanSupplier current,Consumer<Boolean> done){this.activity=activity;this.values=values;this.current=current;this.done=done;}
    void finish(){if(!current.getAsBoolean()){done.accept(false);return;}writes++;done.accept(true);}
  }
  static JSONObject current(MainActivity activity){return J.obj("name","host fixture");}
  static void applySafely(MainActivity activity,JSONObject values,android.widget.EditText name,BooleanSupplier current,Consumer<Boolean> done){pending.add(new Pending(activity,values,current,done));}
}

final class Ui {static final int INK=0,MUTED=1;}
final class DesignUi {static Object spinnerAdapter(MainActivity activity,String[] labels){return labels;}static void action(android.widget.LinearLayout box,String label,boolean primary,Runnable run){android.widget.Button button=new android.widget.Button(null);button.setText(label);button.setOnClickListener(view->run.run());box.addView(button);}}
/** Constants for the UI's evidence-state comparison only. Production AuditReport
 * validation has its own real-model suite; this double never builds a report. */
final class AuditReport {static final String VERIFIED="verified",ISSUE="issue",UNCOVERED="uncovered",AVAILABLE="available",RESTRICTED="restricted",FAILED="failed";}
final class EnvironmentAuditUi {static void show(MainActivity activity){}}
/** Entry-point boundary only; the new adapter has a separate Android-API compile check. */
final class EnvironmentIdentityUi {static void show(MainActivity activity,ChatSession session){}}
final class GeckoPolicyAdapter {static String summary(){return "host policy summary";}}
final class NativeCapabilityManifest {static NativeCapabilityManifest officialGecko(){return new NativeCapabilityManifest();}String unsupportedSummary(){return "host capability summary";}}
