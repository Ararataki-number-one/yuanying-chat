package local.pocketchat;

import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.json.*;

/** Host-only main-loop, observer, view and route boundaries. No Android execution. */
class Looper {static final Object MAIN=new Object();static Object myLooper(){return MAIN;}static Object getMainLooper(){return MAIN;}}
class SystemClock {static long elapsedRealtime(){return 1;}}
class Handler {void post(Runnable work){work.run();}}
class View {
  interface Touch {boolean onTouch(View view,Object event);}interface Key {boolean onKey(View view,int key,Object event);}
  void setOnKeyListener(Key key){}void cancelPendingInputEvents(){}
}
class Web extends View {
  View.Touch touches;long identityPolicyRevision;View surface=new View();
  String getUrl(){return "https://fixture.invalid/controlled";}void setOnTouchListener(View.Touch listener){touches=listener;}
  void checkpointState(){}
}
class Guard {boolean blocked;void setBlocked(boolean value){blocked=value;}}
class Identity {long editSerial;}
class Memory {String scope(){return "controlled";}void remember(String scope,String url,JSONObject state){}}
class Store {java.util.concurrent.Executor worker=Runnable::run;}
class ChatSession {
  static ChatSession current;static ChatSession peek(){return current;}
  final Web web=new Web();final Guard guard=new Guard();final Identity identity=new Identity();
  final Memory pageMemory=new Memory();final Store webStore=new Store();final Object context=new Object();
  boolean configurationCapture,operation,deleted,connecting;long navigationEpoch;int wakes,changes;
  Runnable nextObservation;final Queue<Runnable> observations=new ArrayDeque<>();
  void wakePolling(){wakes++;}void changed(){changes++;if(nextObservation!=null)observations.add(nextObservation);}
  void asyncDriver(String name,JSONObject args,int timeout,java.util.function.Consumer<JSONObject> callback){throw new AssertionError("ChatGPT path outside this host adapter");}
}
class MainActivity {static boolean chatUrl(String url){return false;}}
class NativeNetwork {static NativeNetwork peek(){return null;}}
class WindowNetworkState {static void save(Object profile,ChatSession session,NativeNetwork network){throw new AssertionError("No network supplied");}}
class PageMemory {static boolean completeDraft(JSONObject value){throw new AssertionError("ChatGPT draft branch not executed");}}
class WebReplyObserver {static boolean same(String a,String b){return Objects.equals(a,b);}}
class LocalDraftPolicy {static long revision(Object context){return 0;}static boolean enabled(Object context){return false;}static String unavailable(Object context){return "unused";}}
class DraftArchive {static DraftArchive get(Object context){throw new AssertionError("Draft branch not executed");}boolean save(String url,String draft,String title,long revision){throw new AssertionError("Draft branch not executed");}}
class NetworkCatalog {static void put(JSONObject value,String key,Object field){try{value.put(key,field);}catch(JSONException e){throw new IllegalArgumentException(e);}}}
class NetworkUiProvider {
  final Map<String,RequestBinding> bindings=new HashMap<>();final Map<String,Object> choices=new HashMap<>(),manualRetries=new HashMap<>();
  final ConcurrentHashMap<String,JSONObject> jobs=new ConcurrentHashMap<>();final Handler main=new Handler();final Object profile=new Object();
  final java.util.concurrent.Executor io=Runnable::run;boolean maintenanceStopped,applying;String activeApply="";Transition activeTransition;
  static class RequestBinding {JSONObject outcome;RequestBinding(JSONObject value){outcome=value;}}
  static class Transition {
    final String id;final ChatSession session;Transition(String id,ChatSession session){this.id=id;this.session=session;}
    ChromiumRouteLease.Handle routeChange;boolean confirmed,cancelled,capture,fenced,rollbackFailed,previousBlocked,immediate;
    long browserPolicy,identityEdit,epoch;String url="",scope="",waitReason="";JSONObject page;View.Touch previousTouch,touchFence;View keyTarget;
  }
  static JSONObject operationOutcome(RequestBinding binding,Transition transition,String id,String message){return binding.outcome;}
  boolean currentEnvironment(Transition transition){return true;}
  boolean fenceIdle(Transition transition){return activeTransition==transition&&!transition.cancelled;}
  boolean inspectionIdle(Transition transition,JSONObject inspected,JSONObject page){throw new AssertionError("ChatGPT branch not executed");}
  void deferTransition(Transition transition){throw new AssertionError("Admission unexpectedly denied");}
  void commitTransition(Transition transition){}
  static final class DeferredTransition extends Exception {}
  @PRODUCTION_INTERNAL@
  @PRODUCTION_RECORD@
  @PRODUCTION_CAPTURE@
  @PRODUCTION_GATE@
  @PRODUCTION_RELEASE@
  @PRODUCTION_FINISH@
}
class NetworkSafeIdleIntegrationActivity {
  final ChatSession session=new ChatSession();final Web view=session.web;final PhaseProvider provider=new PhaseProvider();
  final Map<String,NetworkUiProvider.Transition> caseOwners=new LinkedHashMap<>();final Map<String,JSONObject> caseCompletions=new LinkedHashMap<>();
  final JSONArray applicationResults=new JSONArray(),applicationDirectJobs=new JSONArray(),applicationCallbackEvents=new JSONArray();
  final Set<String> applicationDirectIds=new LinkedHashSet<>();int applicationCallbackCount;String caseName="complete-late-save",job="";
  final JSONArray events=new JSONArray();boolean settingsInternalMode,settingsApplicationMode;
  void event(String kind,JSONObject value){events.put(J.obj("kind",kind,"value",J.parse(value.toString())));}
  final class PhaseProvider extends NetworkUiProvider {
    @FIXTURE_RECORD@
  }
  @FIXTURE_INTERNAL@
  @FIXTURE_OWNER@
  @FIXTURE_COMPLETION@
  @FIXTURE_CURRENT@
  @FIXTURE_REQUIRE@
}
class FenceCompletionHost {
  static int checks;
  static void check(String name,boolean value){checks++;if(!value)throw new AssertionError(name);}
  static void rejected(String name,Runnable action){boolean refused=false;try{action.run();}catch(IllegalStateException error){refused=true;}check(name,refused);}
  static NetworkUiProvider.Transition acquire(NetworkSafeIdleIntegrationActivity a,String id)throws Exception{
    NetworkUiProvider.Transition t=new NetworkUiProvider.Transition(id,a.session);
    a.provider.activeTransition=t;a.provider.activeApply=id;a.provider.applying=true;
    // Execute both complete production methods verbatim. Non-chat host document
    // bypasses JS capture only; capture flags and the real Java fences still run.
    a.provider.captureTransition(t);a.provider.commitGate(t);return t;
  }
  static NetworkSafeIdleIntegrationActivity setup()throws Exception{
    NetworkSafeIdleIntegrationActivity a=new NetworkSafeIdleIntegrationActivity();ChatSession.current=a.session;
    a.job="d78123d5-6172-4d73-9b90-3387794fb48c";
    NetworkUiProvider.Transition original=acquire(a,a.job);a.caseOwners.put(a.job,original);
    a.provider.jobs.put(a.job,J.obj("done",false));a.provider.bindings.put(a.job,new NetworkUiProvider.RequestBinding(J.obj("savedRevision",6)));
    check("production capture established",a.session.operation&&a.session.configurationCapture&&original.capture);
    check("production touch fence established",original.fenced&&a.view.touches==original.touchFence);
    a.session.nextObservation=()->{try{acquire(a,"internal:9496c6ac-b736-4665-a8dd-b99d569a8571");}catch(Exception error){throw new IllegalStateException(error);}};
    a.provider.finish(a.job,true,"saved pending");
    check("production finish queued later observer",a.session.observations.size()==1);
    check("production finish closed route barrier",original.routeChange==null&&ChromiumRouteLease.snapshot().changes==0);
    check("completion callback saw finished direct receipt",a.caseCompletions.get(a.job).getJSONObject("job").getBoolean("done"));
    return a;
  }
  static JSONObject proof(NetworkSafeIdleIntegrationActivity a){return a.caseCompletions.get(a.job);}
  static void oldPredicate(JSONObject state){check("complete-late-save: capture and touch fence released",@ORIGINAL_PREDICATE@);}
  static void validate(NetworkSafeIdleIntegrationActivity a,JSONObject completion,JSONObject current){NetworkSafeIdleIntegrationActivity.requireCompletionOwner(a.job,System.identityHashCode(a.caseOwner(a.job)),completion,current);}
  static void cleanup(NetworkSafeIdleIntegrationActivity a){NetworkUiProvider.Transition t=a.provider.activeTransition;if(t!=null){a.provider.releaseCapture(t,true);if(t.routeChange!=null)t.routeChange.close();a.provider.activeTransition=null;}}
  public static void main(String[] args)throws Exception{
    String mode=args.length==0?"interleave":args[0];NetworkSafeIdleIntegrationActivity a=setup();NetworkUiProvider.Transition original=a.caseOwner(a.job);
    try{
      JSONObject completion=proof(a);
      if(mode.equals("closed")){JSONObject current=a.currentOwnership(a.caseOwner(a.job));validate(a,completion,current);oldPredicate(completion);}
      else if(mode.equals("interleave")){
        a.session.observations.remove().run();JSONObject current=a.currentOwnership(a.caseOwner(a.job));
        check("later internal owns actual capture",current.getBoolean("operation")&&current.getBoolean("configurationCapture")&&current.getBoolean("touchOwned"));
        validate(a,completion,current);oldPredicate(completion);
        check("old listener absent or legitimately reused by distinct new owner",current.getBoolean("originalTouchRestored")||current.getBoolean("touchFenceSharedWithCurrent"));
        check("original receipt not replaced",completion.getJSONObject("job").getJSONObject("operationResult").getInt("savedRevision")==6);
      }else if(mode.equals("wrong-owner")){NetworkCatalog.put(completion,"ownerId","internal:wrong");rejected("wrong owner rejected",()->validate(a,completion,a.currentOwnership(a.caseOwner(a.job))));}
      else if(mode.equals("missing-proof")){rejected("missing proof rejected",()->validate(a,null,a.currentOwnership(a.caseOwner(a.job))));}
      else if(mode.equals("unowned-global")){a.session.operation=true;rejected("unowned capture rejected",()->validate(a,completion,a.currentOwnership(a.caseOwner(a.job))));}
      else if(mode.equals("direct-later")){acquire(a,"unregistered-direct");rejected("unknown later direct rejected",()->validate(a,completion,a.currentOwnership(a.caseOwner(a.job))));}
      else if(mode.equals("touch-mutant")){a.session.observations.remove().run();oldPredicate(completion);}
      else if(mode.equals("capture-mutant")){validate(a,completion,a.currentOwnership(a.caseOwner(a.job)));oldPredicate(completion);}
      else if(mode.equals("callbacks")){
        a.settingsInternalMode=true;a.caseOwners.clear();a.caseCompletions.clear();
        for(int i=0;i<4;i++){String id="direct-"+i;a.applicationDirectIds.add(id);a.applicationDirectJobs.put(id);a.provider.jobs.put(id,J.obj("done",false));a.provider.recordResult(id,i<2,"controlled",J.obj("savedRevision",i==3?6:i+1));}
        a.provider.recordResult("internal:later",true,"controlled",J.obj("savedRevision",8));
        check("all callbacks retained",a.applicationCallbackCount==5&&a.applicationCallbackEvents.length()==5);
        check("only admitted direct receipts canonical",a.applicationResults.length()==4);
        check("later revision cannot backdate direct",a.applicationResults.getJSONObject(3).getJSONObject("operationResult").getInt("savedRevision")==6);
        a.provider.recordResult("unknown-direct",false,"controlled",null);check("unknown direct remains raw evidence",a.applicationCallbackCount==6&&a.applicationResults.length()==4);
        a.provider.recordResult("direct-0",true,"controlled",J.obj("savedRevision",99));check("duplicate direct not deduplicated",a.applicationResults.length()==5);
      }else throw new AssertionError("Unknown mode");
      System.out.println(J.obj("status","passed","mode",mode,"checks",checks,"completionProof",completion,"callbackEvents",a.applicationCallbackEvents,"currentOwnership",a.currentOwnership(original)));
    }finally{cleanup(a);}
  }
}
