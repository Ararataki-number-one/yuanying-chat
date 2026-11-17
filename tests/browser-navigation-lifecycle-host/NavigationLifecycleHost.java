package local.pocketchat;

import java.io.*;
import java.net.URI;
import java.util.*;
import java.util.function.Consumer;
import org.json.*;

/** The classes under test are compiled whole; only their external collaborators are modeled. */
public final class NavigationLifecycleHost {
  static final String CHAT="https://chatgpt.com/c/current",OTHER="https://chatgpt.com/c/other";
  static final String DOCUMENT="document-current-0001",TOKEN="trusted-gesture-0001";
  static final JSONArray checks=new JSONArray();
  static void check(String name,boolean value){checks.put(J.obj("name",name,"pass",value));if(!value)throw new AssertionError(name);}
  static JSONObject snapshot(String text){return J.obj("ok",true,"url",CHAT,"documentId",DOCUMENT,"draft",text,"draftComplete",true,"draftLength",text.length());}
  static JSONObject job(String url,boolean confirmed){return J.obj("id","original-job","kind","web","engine","gecko","confirmed",confirmed,"confirmedUrl",confirmed?url:"","expectedUrl",url,"prompt","original prompt","webToken",TOKEN,"webDocument",DOCUMENT,"userKey","id:original");}
  static JSONObject event(String type){return J.obj("type",type,"url",CHAT,"documentId",DOCUMENT,"resourceBinding","binding-current","token",TOKEN,"capturedAt",System.currentTimeMillis(),"prompt","new prompt","beforeKeys",new JSONArray(),"userKey","id:new");}
  static ChatSession fresh(){ChatSession s=new ChatSession();s.web.ports.put(s.web.current,s.resourceObserverPort);return s;}

  static void snapshots(){
    ChatSession s=fresh();PageMemory memory=new PageMemory(s);int[] calls={0};
    memory.captureForNavigation(()->calls[0]++);
    s.handler.advance(199);check("The page capture may complete within its small navigation budget",calls[0]==0);
    s.results.remove(0).accept(snapshot("draft"));s.handler.advance(1);
    check("A successful capture saves its draft and runs navigation exactly once",calls[0]==1&&memory.pages.size()==1&&memory.document(CHAT).equals(DOCUMENT)&&s.handler.pending()==0);

    s=fresh();memory=new PageMemory(s);calls[0]=0;memory.captureForNavigation(()->calls[0]++);
    s.handler.advance(200);check("A hung page bridge cannot delay navigation beyond 200 milliseconds",calls[0]==1&&memory.pages.isEmpty());
    s.results.remove(0).accept(snapshot("late old draft"));s.handler.advance(200);
    check("A late timed-out capture neither writes memory nor repeats navigation",calls[0]==1&&memory.pages.isEmpty());

    s=fresh();memory=new PageMemory(s);int[] first={0},second={0};
    memory.captureForNavigation(()->first[0]++);Consumer<JSONObject> old=s.results.remove(0);
    s.navigationEpoch++;memory.captureForNavigation(()->second[0]++);old.accept(snapshot("retired"));
    check("An older command cannot navigate or write a snapshot in a newer epoch",first[0]==0&&second[0]==0&&memory.pages.isEmpty());
    s.results.remove(0).accept(snapshot("new draft"));s.handler.advance(200);
    check("The newer command remains live after the old callback completes",first[0]==0&&second[0]==1&&memory.pages.size()==1&&memory.pages.values().iterator().next().optString("draft").equals("new draft"));

    s=fresh();memory=new PageMemory(s);first[0]=second[0]=0;
    memory.captureForNavigation(()->first[0]++);s.handler.advance(100);memory.captureForNavigation(()->second[0]++);
    s.handler.advance(100);s.results.remove(1).accept(snapshot("second snapshot"));
    check("An older timeout never retires a newer capture request",first[0]==1&&second[0]==1&&memory.pages.values().iterator().next().optString("draft").equals("second snapshot"));
    s.results.remove(0).accept(snapshot("obsolete"));check("An obsolete capture cannot overwrite the retained newer draft",memory.pages.values().iterator().next().optString("draft").equals("second snapshot"));

    for(String change:new String[]{"deleted","identity","epoch","url"}){
      s=fresh();memory=new PageMemory(s);calls[0]=0;memory.captureForNavigation(()->calls[0]++);
      if(change.equals("deleted"))s.deleted=true;else if(change.equals("identity"))s.appliedIdentity="new environment";else if(change.equals("epoch"))s.navigationEpoch++;else s.web.url=OTHER;
      s.results.remove(0).accept(snapshot("stale"));
      check("Snapshot memory rejects changed "+change,memory.pages.isEmpty());
      if(change.equals("deleted")||change.equals("epoch"))check("Navigation completion rejects changed "+change,calls[0]==0);
    }
    s=fresh();s.web.url="https://example.com/";memory=new PageMemory(s);calls[0]=0;memory.captureForNavigation(()->calls[0]++);
    check("An ordinary website requires no ChatGPT capture or delayed navigation",calls[0]==1&&s.results.isEmpty()&&s.handler.pending()==0);
    s=fresh();memory=new PageMemory(s);calls[0]=0;memory.capture(()->calls[0]++);s.handler.advance(1000);
    check("Non-navigation capture keeps its existing completion contract",calls[0]==0&&s.handler.pending()==0);s.results.remove(0).accept(snapshot("ordinary"));
    check("Non-navigation capture still completes when its result arrives",calls[0]==1&&memory.pages.size()==1);
  }

  static void eventOwnership(){
    for(String type:new String[]{"intent","bound","uncertain","stop"}){
      ChatSession s=fresh();WebReplyObserver observer=new WebReplyObserver(s);
      observer.receive(event(type),s.resourceObserverPort);
      check("Retired "+type+" cannot create a native task or notification",s.pending==null&&s.context.serviceBegins==0&&s.context.serviceEnds==0&&s.prefs.values.isEmpty());
      s.pending=job(CHAT,true);JSONObject original=s.pending;String bytes=original.toString();
      observer.receive(event(type),s.resourceObserverPort);
      check("Retired "+type+" never changes an existing record",s.pending==original&&bytes.equals(original.toString())&&s.prefs.values.isEmpty()&&s.context.serviceBegins==0);
    }
    ChatSession s=fresh();WebReplyObserver observer=new WebReplyObserver(s);s.navigating=true;
    observer.receive(event("ready"),s.resourceObserverPort);
    observer.receive(event("resource-route"),s.resourceObserverPort);
    observer.receive(event("resource-work"),s.resourceObserverPort);
    check("Page readiness and resource events retain their existing owners",s.readyEvents==2&&s.resourceEvents==1&&s.wakes==1&&s.pending==null);
    for(String invalid:new String[]{"https://example.com/c/current","http://chatgpt.com/c/current"}){
      JSONObject value=event("resource-work");try{value.put("url",invalid);}catch(Exception e){throw new AssertionError(e);}
      observer.receive(value,s.resourceObserverPort);
    }
    JSONObject invalid=event("resource-work");try{invalid.put("documentId","short");}catch(Exception e){throw new AssertionError(e);}observer.receive(invalid,s.resourceObserverPort);
    check("Foreign origins and malformed document identities still reject resource reports",s.resourceEvents==1);
  }

  static void observationRetirement(){
    for(boolean confirmed:new boolean[]{false,true}){
      ChatSession s=fresh();WebReplyObserver observer=new WebReplyObserver(s);s.pending=job(CHAT,confirmed);
      String bytes=s.pending.toString();s.activeDeliveryId="original-job";s.prefs.values.put("pending",bytes);s.prefs.values.put("lastWebGesture","old-gesture");
      s.transferActive=true;s.resourceChoosers=1;s.resourceFilePreparations=1;
      observer.restorePending();
      check("Upgrade retires a "+(confirmed?"confirmed":"unconfirmed")+" website task without resuming it",s.pending==null&&s.activeDeliveryId.isEmpty()&&!s.prefs.values.containsKey("pending")&&!s.prefs.values.containsKey("lastWebGesture")&&s.prefs.getString("retiredWebObservation","").equals(bytes));
      check("Upgrade retains file ownership and never changes website input",s.transferActive&&s.resourceChoosers==1&&s.resourceFilePreparations==1&&s.web.scripts.isEmpty()&&s.context.drafts.isEmpty()&&s.context.serviceBegins==0&&s.context.serviceEnds==1);
      observer.restorePending();check("Repeating retirement with no pending record has no effect",s.context.serviceEnds==1);
    }
    ChatSession s=fresh();WebReplyObserver observer=new WebReplyObserver(s);s.pending=J.obj("id","legacy-native","kind","send","prompt","saved text");String bytes=s.pending.toString();observer.restorePending();
    check("Legacy native records remain archived without any automatic send",s.pending==null&&s.prefs.getString("legacyPending","").equals(bytes)&&s.web.scripts.isEmpty()&&s.context.serviceBegins==0);
    s=fresh();observer=new WebReplyObserver(s);s.pending=job(CHAT,true);bytes=s.pending.toString();s.prefs.values.put("pending",bytes);s.prefs.fail=true;observer.restorePending();
    check("Unavailable storage cannot reactivate result detection or erase the durable old record",s.pending==null&&s.prefs.getString("pending","").equals(bytes)&&s.context.serviceBegins==0&&s.context.serviceEnds==1);
    s=fresh();observer=new WebReplyObserver(s);s.pending=job(CHAT,true);ChatSession changing=s;JSONObject replacement=J.obj("id","new-owner","kind","explicit-native");s.prefs.onCommit=()->{changing.pending=replacement;changing.prefs.values.put("pending",replacement.toString());};observer.restorePending();
    check("A storage listener's newer record is neither cleared nor stopped",s.pending==replacement&&s.prefs.getString("pending","").equals(replacement.toString())&&s.context.serviceEnds==0);
  }

  public static void main(String[] args){snapshots();eventOwnership();observationRetirement();System.out.println(J.obj("status","passed","passed",checks.length(),"checks",checks,"actualAndroidExecution",false,"actualGeckoExecution",false,"actualNetworkExecution",false));}
}

class ChatSession {
  final HostContext context=new HostContext();final Prefs prefs=new Prefs();final Queue handler=new Queue();final Web web=new Web();final Deliveries deliveries=new Deliveries();final Store webStore=new Store();final List<Consumer<JSONObject>> results=new ArrayList<>();
  String driver="",appliedIdentity="environment",resourceObserverBinding="binding-current",resourceObserverDocument=NavigationLifecycleHost.DOCUMENT,activeDeliveryId="",stableReply="",status="",observedReplyJob="",observedReplyUrl="",observedReplyKey="",observedReplyRevision="",observedReplyMarkdown="",replyHealthStatus="",conversation=NavigationLifecycleHost.CHAT;
  long navigationEpoch=1,resourceObserverEpoch=1,webWorkGeneration,resourceObservedAt,webConfirmationVersion;int stableTicks,resourceChoosers,resourceFilePreparations,readyEvents,resourceEvents,wakes;Object resourceObserverPort=new Object();JSONObject pending;JSONArray attachments=new JSONArray();
  boolean deleted,submitting,operation,configurationCapture,networkReady=true,navigationDispatched=true,offline,navigating,observedReplyHasFiles,transferActive,replyStalled;
  void runDriver(String action,JSONObject args,Consumer<JSONObject> result){if(!action.equals("page-state"))throw new AssertionError(action);results.add(result);}
  void asyncDriver(String action,JSONObject args,long timeout,Consumer<JSONObject> result){throw new AssertionError("Unexpected restoration command: "+action);}
  boolean webPerformance(){return true;}boolean replyObservationAllowed(){return true;}boolean targetMatches(String url){return url.equals(web.url);}
  boolean resourceBindingMatches(JSONObject value,Object port){return port!=null&&port==resourceObserverPort&&resourceObserverBinding.equals(value.optString("resourceBinding"));}
  void resourceObserverRouteReady(JSONObject value,Object port){readyEvents++;}void resourceWebsiteObservation(JSONObject value,Object port){resourceEvents++;}
  void wakePolling(){wakes++;}void resetReplyStability(){}void setStatus(String value){status=value;}
  void wakeDeferredBrowserSettings(){throw new AssertionError("Completed-task settings wake is outside this navigation host");}
  void delivery(String id,String state,String message,boolean attempted,String key,String url){deliveries.updates.add(J.obj("id",id,"state",state,"message",message,"url",url));}
}
class Web {String url=NavigationLifecycleHost.CHAT,cookieStamp="cookies";final Object current=new Object();final Map<Object,Object> ports=new IdentityHashMap<>();final List<String> scripts=new ArrayList<>();String getUrl(){return url;}boolean resourcePage(String value){return MainActivity.chatUrl(value);}void evaluateJavascript(String code,Object result){scripts.add(code);}}
class HostContext {int serviceBegins,serviceEnds;final List<JSONObject> drafts=new ArrayList<>();android.content.pm.ApplicationInfo getApplicationInfo(){return new android.content.pm.ApplicationInfo();}Assets getAssets(){return new Assets();}}
class Assets {InputStream open(String name)throws IOException{throw new IOException("Asset loading is not executed by this host");}}
class Queue {
  static final class Task {final Runnable value;final long at;Task(Runnable value,long at){this.value=value;this.at=at;}}
  long now;final List<Task> tasks=new ArrayList<>();void post(Runnable task){tasks.add(new Task(task,now));}void postDelayed(Runnable task,long delay){tasks.add(new Task(task,now+delay));}void removeCallbacks(Runnable task){tasks.removeIf(t->t.value==task);}int pending(){return tasks.size();}
  void advance(long delta){now+=delta;int count=0;while(true){Task next=null;for(Task t:tasks)if(t.at<=now&&(next==null||t.at<next.at))next=t;if(next==null)return;if(++count>100)throw new AssertionError("Unbounded scheduler");tasks.remove(next);next.value.run();}}
}
class Prefs {
  final Map<String,String> values=new HashMap<>();boolean fail;Runnable onCommit;
  String getString(String name,String fallback){return values.getOrDefault(name,fallback);}Editor edit(){return new Editor();}
  final class Editor {final Map<String,String> writes=new HashMap<>();final Set<String> removes=new HashSet<>();Editor putString(String key,String value){writes.put(key,value);return this;}Editor remove(String key){removes.add(key);return this;}boolean commit(){if(fail)return false;for(String key:removes)values.remove(key);values.putAll(writes);Runnable callback=onCommit;onCommit=null;if(callback!=null)callback.run();return true;}}
}
class Deliveries {
  int begins;final List<JSONObject> updates=new ArrayList<>();
  JSONObject get(String id){throw new AssertionError("Cold recovery storage is outside this navigation host");}
  String begin(String url,String prompt,JSONArray names,String kind,Object source){return "new-job-"+(++begins);}
  // Retired storage boundary retained only as a counter: current observation
  // must never call it. Upgrade archival uses the actual observer and Prefs above.
  boolean update(String id,String state,String message,boolean attempted,String key,String url){
    if(id.isEmpty()||!state.equals("stopped")||!attempted)throw new AssertionError("Unsupported terminal delivery boundary");
    updates.add(J.obj("id",id,"state",state,"message",message,"url",url));return true;
  }
}
class Store {final java.util.concurrent.Executor worker=Runnable::run;}
class MainActivity {static boolean chatUrl(String value){try{return "https".equals(URI.create(value).getScheme())&&"chatgpt.com".equals(URI.create(value).getHost());}catch(Exception invalid){return false;}}}
class NativeNetwork {static String hash(String value){return value;}}
class LocalDraftPolicy {static long revision(HostContext context){return 1;}static JSONObject snapshot(HostContext context,JSONObject value){return snapshot(context,value,1);}static JSONObject snapshot(HostContext context,JSONObject value,long revision){return J.parse(value.toString());}static boolean mayRestore(HostContext context,JSONObject value){return true;}}
class DraftArchive {final HostContext context;DraftArchive(HostContext context){this.context=context;}static DraftArchive get(HostContext context){return new DraftArchive(context);}boolean save(String url,String text,String reason,long revision){context.drafts.add(J.obj("url",url,"text",text));return true;}}
class AppPrefs {static boolean enabled(HostContext context,String key){return true;}}
class ChatService {static void begin(HostContext context){context.serviceBegins++;}static void end(HostContext context){context.serviceEnds++;}static void completed(HostContext context,String id,String url){throw new AssertionError("Navigation cannot announce a completed server task");}}
