package local.pocketchat;
import org.json.*;
public final class NetworkApplicationProviderTest {
 static final JSONArray checks=new JSONArray();static void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));if(!pass)throw new AssertionError(name);}
 static NetworkUiProvider provider;static ChatSession session;static NativeNetwork network;
 static void setup(boolean internal)throws Exception{SystemClock.now=0;session=new ChatSession();ChatSession.instance=session;session.internal=internal;network=new NativeNetwork();provider=new NetworkUiProvider();EnvironmentSpec.Identity id=new EnvironmentSpec.Identity(0,3,session.environmentId);provider.profile.identity=id;EnvironmentSpec.NetworkBinding route=EnvironmentSpecRuntime.binding(id,internal?"internal":"external",internal?network.settings:new JSONObject(),"");EnvironmentSpec model=EnvironmentSpec.initial(id,new EnvironmentSpec.Configuration(session.web.metadata.acceptedBrowserIdentity,route));provider.profile.model=model.withApplied(1,GeckoWebView.VERSION,1);NetworkApplicationReceipt receipt=NetworkApplicationReceipt.saved(id,"candidate-a",model,route);provider.bindings.put("save",new NetworkUiProvider.RequestBinding(id,"candidate",receipt));provider.activeTransition=new NetworkUiProvider.Transition();provider.activeTransition.session=session;}
 static void begin(){provider.waitConnection("save",session,network,true,SystemClock.now);}
 static void drive(){for(int i=0;i<100&&!provider.completed;i++){boolean ran=provider.main.one(false);ran|=provider.io.one(true);if(!ran)throw new AssertionError("No queued continuation");}if(!provider.completed)throw new AssertionError("Waiter did not finish");}
 static boolean applied(){return provider.ok&&provider.result!=null&&"applied".equals(provider.result.optString("applicationState"));}
 static void workerThen(){provider.main.one(false);if(provider.io.tasks.size()!=1)throw new AssertionError("Proof not on worker");provider.io.one(true);}
 public static void main(String[] args)throws Exception{
  setup(true);begin();drive();check("Exact current candidate and fresh core/model proof publish applied once",applied()&&provider.result.optLong("appliedRevision")==1&&provider.completions==1&&network.freshCalls==1);check("Fresh core verification runs only on the worker adapter",network.workerOnly);
  setup(true);provider.profile.model=EnvironmentSpec.initial(provider.profile.identity,provider.profile.model.desired());begin();drive();check("Old ready core without model acknowledgement never publishes applied",!applied()&&!provider.ok&&network.freshCalls>0);
  setup(true);network.fresh=false;begin();drive();check("A cached valid receipt cannot replace failed fresh IPC verification",!applied()&&!provider.ok&&network.freshCalls>0);
  setup(true);network.admission=NetworkHealthPolicy.Admission.DEGRADED_VERIFICATION;begin();drive();check("Retained old admission is not a successful new application",!applied()&&!provider.ok&&network.freshCalls==0);
  setup(true);network.settings=J.obj("entry","old","exit","fixed");begin();drive();check("Different actual transport fingerprint rejects old ready flag",!applied()&&network.freshCalls==0);
  setup(true);network.transport=null;begin();drive();check("Missing production transport cannot fabricate actual core evidence",!applied());
  setup(true);session.guard.allowed=false;begin();drive();check("A blocked webpage route cannot be reported applied",!applied());
  setup(true);session.networkIssue="exit verification unavailable";begin();drive();check("Uncertain verification message remains distinct from recovered",!applied());
  setup(true);begin();session.connectionEpoch++;drive();check("A newer connection cannot satisfy an older settings operation",!applied()&&network.freshCalls==0);
  setup(true);begin();session.web.current=new Object();drive();check("A replaced Gecko session cannot borrow a pending result",!applied());
  setup(true);begin();session.environmentGeneration++;drive();check("Environment generation changes reject the old operation",!applied());
  setup(true);begin();session.environmentId="22222222-2222-2222-2222-222222222222";drive();check("Reused slot with different UUID rejects the old operation",!applied());
  setup(true);begin();ChatSession.instance=new ChatSession();drive();check("A different current ChatSession cannot inherit the result",!applied());
  setup(true);begin();provider.saveRevision++;drive();check("Newer settings request supersedes old apply continuation",!applied());
  setup(true);provider.profile.pending="new-candidate";begin();drive();check("A different saved candidate rejects otherwise exact model and core",!applied());
  setup(true);provider.profile.active="new-active";begin();drive();check("Changed active configuration rejects a stale publication receipt",!applied());
  setup(true);provider.profile.model=provider.profile.model.withDesired(1,new EnvironmentSpec.Configuration(J.obj("desktop",true),provider.profile.model.desired().network));begin();drive();check("A newer desired browser revision is not confirmed by the old model version",!applied());
  setup(true);begin();workerThen();network.verifiedRoute=new NativeNetwork.ExitRouteReceipt();provider.main.one(false);check("Core replacement cannot use the previous background proof",!provider.completed&&network.freshCalls==1);drive();check("A replacement core needs its own fresh exact proof",applied()&&network.freshCalls==2);
  setup(true);begin();workerThen();session.web.identityPolicyRevision++;drive();check("Policy changes during background proof reject its late completion",!applied());
  setup(true);begin();workerThen();session.identity.editSerial++;drive();check("A new browser edit retires the pending application receipt",!applied());
  setup(true);begin();workerThen();session.web.metadata.acceptedBrowserIdentity=J.obj("desktop",true);drive();check("Accepted browser state must still match at main-thread handoff",!applied());
  setup(true);session.web.metadata.policyAcknowledged=false;begin();provider.main.one(false);session.web.metadata.policyAcknowledged=true;drive();check("A real later policy acknowledgement can satisfy the same operation",applied());
  setup(false);begin();drive();check("External proxy application uses the same exact model and policy proof",applied()&&network.freshCalls==0);
  setup(false);session.prefs.proxy="different-proxy";begin();drive();check("A different external route cannot inherit an old applied revision",!applied());
  setup(true);network.admission=NetworkHealthPolicy.Admission.DEGRADED_VERIFICATION;provider.waitConnection("save",session,network,false,0);drive();check("Ordinary reconnect also keeps retained admission separate from success",!provider.ok);
  setup(true);network.settings.put("subscriptionName","actual-source");network.settings.put("exitName","actual-exit");network.settings.put("exitPassword","do-not-publish");JSONObject running=WindowNetworkState.running(session,network);check("Running summary comes from the exact admitted core settings",running.optString("entry").equals("Entry|new")&&running.optString("exitName").equals("actual-exit")&&running.optString("subscriptionName").equals("actual-source")&&running.optBoolean("verified"));
  check("Running summary binds stable environment identity and excludes credentials",running.optString("environmentId").equals(session.environmentId)&&running.optInt("generation")==3&&!running.toString().contains("do-not-publish")&&!running.has("exitPassword"));
  network.settings.put("entry","pending-new");check("A newer settings object without its real core receipt is not a running route",WindowNetworkState.running(session,network).length()==0);
  setup(true);network.admission=NetworkHealthPolicy.Admission.DEGRADED_VERIFICATION;check("Retained route summary does not claim fresh exit verification",!WindowNetworkState.running(session,network).optBoolean("verified"));
  setup(true);session.guard.allowed=false;check("Blocked session has no admitted running summary",WindowNetworkState.running(session,network).length()==0);
  setup(true);check("A core without a live session is not reported as browser applied",WindowNetworkState.running(null,network).length()==0);
  setup(false);session.prefs.proxy="http://user:secret@proxy.invalid:8080";running=WindowNetworkState.running(session,network);check("External running summary includes only proxy presence and hashed identity",running.optBoolean("proxy")&&!running.toString().contains("secret")&&!running.toString().contains("proxy.invalid"));
  setup(true);NetworkUiProvider.RequestBinding binding=provider.bindings.get("save");NetworkUiProvider.Transition transition=provider.activeTransition;transition.confirmed=false;
  check("An unconfirmed saved transition reports pending",NetworkUiProvider.operationOutcome(binding,transition,"save","waiting").optString("applicationState").equals("pending"));
  transition.cancelledByUser=true;check("Requested cancellation without durable completion cannot claim cancelled",NetworkUiProvider.operationOutcome(binding,transition,"save","cancel read failed").optString("applicationState").equals("saved-unconfirmed"));
  transition.cancellationConfirmed=true;check("Only durable exact cancellation reports cancelled",NetworkUiProvider.operationOutcome(binding,transition,"save","cancelled").optString("applicationState").equals("cancelled"));
  transition.cancelledByUser=false;transition.cancellationConfirmed=false;transition.confirmed=true;transition.session=null;check("A confirmed core-only transition remains next-session and unconfirmed",NetworkUiProvider.operationOutcome(binding,transition,"save","next session").optString("scope").equals("next-session")&&NetworkUiProvider.operationOutcome(binding,transition,"save","next session").optString("applicationState").equals("saved-unconfirmed"));
  check("Non-save operations publish no misleading save failure",NetworkUiProvider.operationOutcome(new NetworkUiProvider.RequestBinding(binding.identity,""),null,"measure","measured")==null);
  check("Pre-save failure has no durable save acknowledgement",NetworkUiProvider.operationOutcome(new NetworkUiProvider.RequestBinding(binding.identity,"",null,true),null,"save","failed").optString("saveState").equals("failed"));
  binding.outcome=J.obj("applicationState","applied","candidateId","frozen");check("Confirmed immutable operation outcome survives pending cleanup",NetworkUiProvider.operationOutcome(binding,transition,"save","done")==binding.outcome);
  System.out.println(J.obj("status","passed","passed",checks.length(),"checks",checks,"actualAndroidExecution",false,"actualCoreVerification",false,"productionWaiterMethods",true));
 }
}
