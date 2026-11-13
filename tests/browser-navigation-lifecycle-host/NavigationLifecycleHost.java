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
    ChatSession s=fresh();WebReplyObserver observer=new WebReplyObserver(s);Object port=s.resourceObserverPort;
    observer.receive(event("intent"),port);
    check("A current document gesture still creates one observed request",s.pending!=null&&s.deliveries.begins==1&&s.context.serviceBegins==1);
    observer.receive(event("intent"),port);check("Duplicate gesture remains deduplicated",s.deliveries.begins==1);
    for(String change:new String[]{"epoch","capture","port","binding","document","route","deleted"}){
      s=fresh();observer=new WebReplyObserver(s);port=s.resourceObserverPort;JSONObject intent=event("intent");
      if(change.equals("epoch"))s.navigationEpoch++;else if(change.equals("capture"))s.navigationDispatched=false;else if(change.equals("port"))s.web.ports.put(s.web.current,new Object());else if(change.equals("binding"))intent=J.obj("type","intent","url",CHAT,"documentId",DOCUMENT,"resourceBinding","stale-binding","token",TOKEN,"capturedAt",System.currentTimeMillis(),"prompt","old","beforeKeys",new JSONArray());else if(change.equals("document"))s.resourceObserverDocument="document-newer-0002";else if(change.equals("route"))s.web.url=OTHER;else s.deleted=true;
      observer.receive(intent,port);check("A stale "+change+" event cannot resurrect a webpage observation",s.pending==null&&s.deliveries.begins==0&&s.context.serviceBegins==0);
    }
    for(String type:new String[]{"bound","stop","uncertain"}){
      s=fresh();observer=new WebReplyObserver(s);s.pending=job(CHAT,type.equals("stop"));JSONObject original=s.pending;String bytes=original.toString();s.navigationEpoch++;
      JSONObject action=type.equals("stop")?J.obj("type","stop","url",CHAT,"documentId",DOCUMENT,"resourceBinding","binding-current","token",TOKEN,"userKey","id:original"):event(type);
      observer.receive(action,s.resourceObserverPort);
      check("Late "+type+" cannot modify the pending record after navigation",s.pending==original&&bytes.equals(original.toString())&&s.context.serviceEnds==0&&s.deliveries.updates.isEmpty());
    }
    s=fresh();observer=new WebReplyObserver(s);s.pending=job(CHAT,false);observer.receive(event("bound"),s.resourceObserverPort);
    check("A correctly bound receipt still confirms the current request",s.pending.optBoolean("confirmed")&&s.pending.optString("userKey").equals("id:new"));
    observer.receive(event("stop"),s.resourceObserverPort);
    check("A current-page stop gesture still retires its matching local observation",s.pending==null&&s.context.serviceEnds==1&&s.deliveries.updates.get(s.deliveries.updates.size()-1).optString("state").equals("stopped"));
    s=fresh();observer=new WebReplyObserver(s);s.navigationEpoch++;s.resourceObserverEpoch=s.navigationEpoch;observer.receive(event("intent"),s.resourceObserverPort);
    check("A newly bound observer remains usable after navigation",s.pending!=null&&s.deliveries.begins==1);
  }

  static void observationRetirement(){
    ChatSession s=fresh();WebReplyObserver observer=new WebReplyObserver(s);s.pending=job(CHAT,true);JSONObject original=s.pending;String bytes=original.toString();
    observer.navigationStarted(CHAT+"?model=auto");
    check("A same-conversation reload keeps its confirmed observation",s.pending==original&&s.context.serviceEnds==0&&s.deliveries.updates.isEmpty());
    s.transferActive=true;s.resourceChoosers=1;s.resourceFilePreparations=1;observer.navigationStarted("https://example.com/article");
    check("Leaving the route archives the exact task record without claiming completion",s.pending==null&&bytes.equals(s.prefs.getString("archivedWebObservation",""))&&s.deliveries.updates.size()==1&&s.deliveries.updates.get(0).optString("state").equals("uncertain"));
    check("The original prompt stays recoverable and native file work is untouched",s.context.drafts.size()==1&&s.context.drafts.get(0).optString("text").equals("original prompt")&&s.transferActive&&s.resourceChoosers==1&&s.resourceFilePreparations==1);
    check("Only the local observer reminder ends; no website script is sent",s.context.serviceEnds==1&&s.web.scripts.isEmpty()&&observer.lastNavigationArchivedJob==original&&observer.navigationArchiveSequence==1);
    observer.navigationStarted(OTHER);check("An already retired observation cannot be archived twice",s.deliveries.updates.size()==1&&s.context.serviceEnds==1);

    s=fresh();observer=new WebReplyObserver(s);s.pending=job("https://chatgpt.com/",false);original=s.pending;observer.navigationStarted(CHAT);
    check("The website first-send route transition keeps its unconfirmed binding",s.pending==original&&s.context.serviceEnds==0);
    observer.navigationStarted("https://example.com/");check("Leaving an unconfirmed first send still permits navigation and retains its record",s.pending==null&&s.prefs.getString("archivedWebObservation","").equals(original.toString()));

    s=fresh();observer=new WebReplyObserver(s);s.pending=J.obj("id","native-task","kind","native");original=s.pending;observer.navigationStarted(OTHER);
    check("A native task is not owned or cancelled by webpage navigation",s.pending==original&&s.prefs.values.isEmpty()&&s.context.serviceEnds==0);
    s=fresh();observer=new WebReplyObserver(s);s.pending=job(CHAT,true);original=s.pending;s.prefs.fail=true;observer.navigationStarted(OTHER);
    check("Failed archival keeps the original task instead of losing its record",s.pending==original&&s.deliveries.updates.isEmpty()&&s.context.serviceEnds==0);
    s=fresh();observer=new WebReplyObserver(s);s.pending=job(CHAT,true);ChatSession changing=s;JSONObject replacement=job(OTHER,true);s.prefs.onCommit=()->changing.pending=replacement;observer.navigationStarted(OTHER);
    check("A synchronous storage listener cannot have its newer task cleared",s.pending==replacement&&s.context.serviceEnds==0);
    s=fresh();observer=new WebReplyObserver(s);s.pending=job(CHAT,true);original=s.pending;ChatSession returning=s;s.prefs.onCommit=()->returning.navigationEpoch++;observer.navigationStarted(OTHER);
    check("A listener navigating back to the same task keeps its exact pending record",s.pending==original&&s.prefs.getString("pending","").equals(original.toString())&&s.context.serviceEnds==0&&s.deliveries.updates.isEmpty());
    s=fresh();observer=new WebReplyObserver(s);s.pending=job(CHAT,true);ChatSession newer=s;s.prefs.onCommit=()->{newer.navigationEpoch++;newer.prefs.values.put("pending","newer persisted record");};observer.navigationStarted(OTHER);
    check("Retiring an older observation never overwrites a newer persisted record",s.prefs.getString("pending","").equals("newer persisted record")&&s.context.serviceEnds==0);
  }

  public static void main(String[] args){snapshots();eventOwnership();observationRetirement();System.out.println(J.obj("status","passed","passed",checks.length(),"checks",checks,"actualAndroidExecution",false,"actualGeckoExecution",false,"actualNetworkExecution",false));}
}

class ChatSession {
  final HostContext context=new HostContext();final Prefs prefs=new Prefs();final Queue handler=new Queue();final Web web=new Web();final Deliveries deliveries=new Deliveries();final Store webStore=new Store();final List<Consumer<JSONObject>> results=new ArrayList<>();
  String driver="",appliedIdentity="environment",resourceObserverBinding="binding-current",resourceObserverDocument=NavigationLifecycleHost.DOCUMENT,activeDeliveryId="",stableReply="",status="",observedReplyJob="",observedReplyUrl="",observedReplyKey="",observedReplyRevision="",observedReplyMarkdown="",replyHealthStatus="",conversation=NavigationLifecycleHost.CHAT;
  long navigationEpoch=1,resourceObserverEpoch=1,webWorkGeneration,resourceObservedAt,webConfirmationVersion;int stableTicks,resourceChoosers,resourceFilePreparations;Object resourceObserverPort=new Object();JSONObject pending;JSONArray attachments=new JSONArray();
  boolean deleted,submitting,operation,configurationCapture,networkReady=true,navigationDispatched=true,offline,navigating,observedReplyHasFiles,transferActive,replyStalled;
  void runDriver(String action,JSONObject args,Consumer<JSONObject> result){if(!action.equals("page-state"))throw new AssertionError(action);results.add(result);}
  void asyncDriver(String action,JSONObject args,long timeout,Consumer<JSONObject> result){throw new AssertionError("Unexpected restoration command: "+action);}
  boolean webPerformance(){return true;}boolean replyObservationAllowed(){return true;}boolean targetMatches(String url){return url.equals(web.url);}
  boolean resourceBindingMatches(JSONObject value,Object port){return port!=null&&port==resourceObserverPort&&resourceObserverBinding.equals(value.optString("resourceBinding"));}
  void resourceObserverRouteReady(JSONObject value,Object port){}void resourceWebsiteObservation(JSONObject value,Object port){}
  void wakePolling(){}void resetReplyStability(){}void setStatus(String value){status=value;}
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
  // This host acknowledges only its current-page stop cases. Storage fault and
  // recovery behavior execute against DeliveryStore in reply-task-persistence-host.
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
