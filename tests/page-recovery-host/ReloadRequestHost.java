package local.pocketchat;
import java.util.*;import java.net.URI;import org.json.*;import android.net.Uri;
/** Exact current reload and upgrade-migration methods; controlled browser/storage/UI edges. */
public class ReloadRequestHost {
 static final JSONArray checks=new JSONArray();
 static void check(String name,boolean passed){checks.put(J.obj("name",name,"passed",passed));if(!passed)throw new AssertionError(name);}
 static JSONObject job(String kind){return J.obj("id","old-upgrade-record","kind",kind,"expectedUrl","https://chatgpt.com/c/A","confirmed",true);}
 static ChatSession route(){ReferenceUi.Modal.shows=0;LocalDraftPolicy.allowed=true;LocalDraftPolicy.revision=1;DraftArchive.saved=true;DraftArchive.writes=0;ProfileCatalog.generation=4;ProfileCatalog.environmentId="environment-one";ProfileCatalog.available=true;ProfileCatalog.deleting=false;ProfileCatalog.resetting=false;Profiles.slot=2;ChatService.ends=0;ChatSession s=new ChatSession();s.state=inspect(s,false);s.stateEpoch=s.navigationEpoch;return s;}
 static JSONObject inspect(ChatSession s,boolean busy){return J.obj("url",s.web.url,"documentId",s.lastDocumentId,"composer",true,"busy",busy);}
 static JSONObject snapshot(ChatSession s,String draft){return J.obj("ok",true,"url",s.web.url,"documentId",s.lastDocumentId,"draft",draft,"draftComplete",true,"draftLength",draft.length());}
 static void respond(ChatSession s,JSONObject value){ChatSession.Result callback=s.driverResult;s.driverResult=null;if(callback==null)throw new AssertionError("Missing production driver callback");callback.accept(value);}
 static void inspect(MainActivity a,boolean busy){respond(a.session,inspect(a.session,busy));}
 static void page(MainActivity a,String draft){if(a.session.driverResult!=null&&a.session.lastAction.equals("page-state"))respond(a.session,snapshot(a.session,draft));}
 static void start(MainActivity a,boolean busy,String draft){a.requestReload();inspect(a,busy);page(a,draft);}
 static void mutate(ChatSession s,int n){switch(n){
   case 0:s.navigationEpoch++;break;case 1:s.web.url="https://chatgpt.com/c/C";break;case 2:s.lastDocumentId="replacement-document-0002";break;case 3:s.web.current=new Browser();break;
   case 4:s.appliedIdentity="different-route";break;case 5:s.fileWorkGeneration++;s.fileBusy=true;break;case 6:s.state=inspect(s,true);s.stateEpoch=s.navigationEpoch;break;
   case 7:ProfileCatalog.generation++;break;case 8:ProfileCatalog.environmentId="different-environment";break;case 9:ProfileCatalog.deleting=true;break;case 10:ProfileCatalog.resetting=true;break;
   case 11:Profiles.slot++;break;case 12:s.deleted=true;break;case 13:s.pending=job("web");break;case 14:try{s.pending.put("id","mutated-legacy-record");}catch(Exception error){throw new RuntimeException(error);}break;
   case 15:s.webWorkGeneration++;break;case 16:s.web.ports.put(s.web.current,new Object());break;case 17:s.web.ports.clear();break;case 18:s.web.visible=false;break;
 }}
 static void migration()throws Exception {
   for(String kind:new String[]{"web","native"}){
     ChatSession s=route();JSONObject old=job(kind);s.pending=old;s.activeDeliveryId=old.optString("id");s.prefs.values.put("pending",old.toString());s.prefs.values.put("lastWebGesture","legacy-gesture");s.webObserver.restorePending();
     check("Upgrade archives old record without resuming observation "+kind,s.pending==null&&s.activeDeliveryId.isEmpty()&&s.prefs.getString(kind.equals("web")?"retiredWebObservation":"legacyPending","").equals(old.toString())&&!s.prefs.values.containsKey("pending")&&!s.prefs.values.containsKey("lastWebGesture")&&ChatService.ends==1&&s.asyncCalls==0&&s.reloads==0);
     int writes=s.prefs.commits;s.webObserver.restorePending();check("Migration is inert after active record retired "+kind,s.prefs.commits==writes&&ChatService.ends==1);
   }
   for(boolean throwsWrite:new boolean[]{false,true}){
     ChatSession s=route();s.pending=job("web");String disk=s.pending.toString();s.prefs.values.put("pending",disk);s.prefs.commitOk=false;s.prefs.throwCommit=throwsWrite;s.webObserver.restorePending();
     check("Failed upgrade storage cannot reactivate result checking "+throwsWrite,s.pending==null&&s.prefs.getString("pending","").equals(disk)&&s.asyncCalls==0&&ChatService.ends==1);
   }
   ChatSession s=route();s.pending=job("web");JSONObject replacement=job("native");final ChatSession current=s;s.prefs.listener=()->{current.pending=replacement;current.activeDeliveryId="replacement";};s.webObserver.restorePending();
   check("Synchronous storage listener keeps replacement task identity",s.pending==replacement&&s.activeDeliveryId.equals("replacement")&&ChatService.ends==0);
   s=route();for(String type:new String[]{"intent","bound","uncertain","stop","complete"})s.webObserver.receive(J.obj("type",type,"url",s.web.url,"documentId",s.lastDocumentId,"token","old-document-token"),s.web.ports.get(s.web.current));
   check("Old send events create no native task or notification",s.pending==null&&s.prefs.commits==0&&s.webWorkGeneration==0&&s.asyncCalls==0&&ChatService.ends==0);
   s.webObserver.receive(J.obj("type","resource-route","url",s.web.url,"documentId",s.lastDocumentId),s.web.ports.get(s.web.current));s.webObserver.receive(J.obj("type","resource-work","url",s.web.url,"documentId",s.lastDocumentId),s.web.ports.get(s.web.current));
   check("Resource route and file safety events remain connected",s.routeEvents==1&&s.workEvents==1&&s.pending==null);
 }
 public static void main(String[] args)throws Exception {
   migration();
   ChatSession s=route();s.state=inspect(s,true);MainActivity a=new MainActivity(s);start(a,true,"unsent draft");
   check("Busy browser page requires explicit reload confirmation",a.reloadDialog!=null&&a.reloadDialog.shown&&a.reloadDialog.positiveLabel.equals("重新加载")&&s.reloads==0&&s.pending==null&&s.prefs.commits==0);
   a.reloadDialog.negative.run();check("Cancel retains draft and original document",a.reloadDialog==null&&s.reloads==0&&s.lastDocumentId.equals("current-document-0001"));
   s=route();a=new MainActivity(s);start(a,false,"");check("Idle empty page still requires final draft verification",a.reloadDialog==null&&s.reloads==0&&s.asyncCalls==3);page(a,"");check("Current verified idle page reloads without a send task",s.reloads==1&&s.pending==null&&s.pageMemory.remembered!=null&&!s.lastCapture);
   s=route();a=new MainActivity(s);start(a,false,"keep this draft");a.reloadDialog.positive.run();page(a,"keep this draft");check("Explicit reload archives and verifies the unchanged draft",s.reloads==1&&DraftArchive.writes==1&&s.pageMemory.remembered.optString("draft").equals("keep this draft")&&s.pageMemory.restorePending);
   s=route();a=new MainActivity(s);start(a,false,"first draft");a.reloadDialog.positive.run();page(a,"changed draft");check("Changed input blocks reload after the save callback",s.reloads==0&&s.status.contains("输入已变化"));
   s=route();a=new MainActivity(s);start(a,false,"keep this draft");DraftArchive.saved=false;a.reloadDialog.positive.run();check("Failed draft archive asks for independent loss confirmation",s.reloads==0&&a.reloadDialog!=null&&a.reloadDialog.positiveLabel.equals("已保存，重新加载"));
   s=route();a=new MainActivity(s);start(a,false,"draft");a.reloadDialog.positive.run();LocalDraftPolicy.revision++;page(a,"draft");check("Changed local-draft revision cannot reuse old archive permission",s.reloads==0&&a.reloadDialog!=null&&a.reloadDialog.positiveLabel.equals("已保存，重新加载"));

   for(int phase=0;phase<3;phase++)for(int mutation=0;mutation<19;mutation++){
     s=route();s.pending=job("web");a=new MainActivity(s);a.requestReload();
     if(phase>0)inspect(a,false);
     if(phase==2)page(a,"protected draft");
     mutate(s,mutation);
     if(phase==0){if(s.driverResult!=null)inspect(a,false);page(a,"protected draft");}
     else if(phase==1)page(a,"protected draft");
     else if(a.reloadDialog!=null)a.reloadDialog.positive.run();
     check("Current reload retains identity fence phase "+phase+" field "+mutation,s.reloads==0&&(phase==2||a.reloadDialog==null)&&s.prefs.commits==0&&s.driverResult==null);
   }
   for(int phase=0;phase<2;phase++)for(int mutation=0;mutation<3;mutation++){
     s=route();a=new MainActivity(s);a.requestReload();if(phase>0)inspect(a,false);ChatSession.Result callback=s.driverResult;s.driverResult=null;
     if(mutation==0)a.destroyed=true;else if(mutation==1)a.session=route();else a.remote=route().web;
     callback.accept(phase==0?inspect(s,false):snapshot(s,"draft"));
     check("Activity and remote replacement rejects callback phase "+phase+" field "+mutation,s.reloads==0&&a.reloadDialog==null&&!a.reloadChecking);
   }
   s=route();a=new MainActivity(s);a.requestReload();a.requestReload();check("Repeated reload click coalesces the inspection",s.asyncCalls==1);inspect(a,false);page(a,"draft");a.requestReload();check("Visible confirmation blocks another reload inspection",s.asyncCalls==2);

   for(int order=0;order<2;order++)for(boolean busy:new boolean[]{false,true}){
     s=route();s.lastDocumentId="";s.state=new JSONObject();s.stateEpoch=-1;a=new MainActivity(s);a.requestReload();JSONObject first=inspect(s,busy).put("documentId","registered-document-0002");
     if(order==1){s.lastDocumentId=first.optString("documentId");s.state=first;s.stateEpoch=s.navigationEpoch;}
     respond(s,first);page(a,"draft");
     check("Initial document registration converges on exact native port order "+order+" busy "+busy,s.lastDocumentId.equals("registered-document-0002")&&a.reloadDialog!=null&&s.asyncCalls==2&&s.reloads==0);
   }
   for(int invalid=0;invalid<6;invalid++){
     s=route();s.lastDocumentId="";s.state=new JSONObject();s.stateEpoch=-1;a=new MainActivity(s);a.requestReload();JSONObject first=inspect(s,true).put("documentId","registered-document-0002");
     switch(invalid){case 0:first.put("documentId","short");break;case 1:s.web.ports.clear();break;case 2:first.put("url","https://chatgpt.com/c/C");break;case 3:s.web.visible=false;break;case 4:first.put("busy","true");break;case 5:s.resourceWebsiteEpoch=s.navigationEpoch;break;}
     respond(s,first);page(a,"draft");check("First busy observation cannot bypass document proof "+invalid,s.lastDocumentId.isEmpty()&&a.reloadDialog==null&&s.reloads==0);
   }
   s=route();a=new MainActivity(s);a.requestReload();s.state=inspect(s,true);respond(s,s.state);page(a,"draft");check("Known idle document cannot silently acquire new busy work",a.reloadDialog==null&&s.reloads==0);
   for(int order=0;order<2;order++){
     s=route();String prior=s.lastDocumentId;long epoch=s.navigationEpoch;s.beginNavigation(s.web.url,"new page");s.beginNavigation(s.web.url,"superseding page");
     check("Repeated real navigation retains original prior-document proof "+order,s.lastDocumentId.isEmpty()&&s.priorDocumentId.equals(prior)&&s.awaitNewDocument&&s.navigationEpoch==epoch+2);
     s.navigating=false;s.web.ports.put(s.web.current,new Object());a=new MainActivity(s);a.requestReload();JSONObject observed=inspect(s,false).put("documentId","new-document-observed-0003");if(order==1){s.lastDocumentId=observed.optString("documentId");s.state=observed;s.stateEpoch=s.navigationEpoch;s.awaitNewDocument=false;}
     respond(s,observed);page(a,"draft");check("Reload binds only current replacement document callback order "+order,a.reloadDialog!=null&&s.lastDocumentId.equals("new-document-observed-0003")&&s.reloads==0);
   }
   s=route();String prior=s.lastDocumentId;s.beginNavigation(s.web.url,"still waiting");a=new MainActivity(s);a.requestReload();respond(s,inspect(s,false).put("documentId",prior));page(a,"draft");check("Prior document cannot register during an unfinished navigation",a.reloadDialog==null&&s.reloads==0&&s.lastDocumentId.isEmpty()&&s.awaitNewDocument);

   for(int incomplete=0;incomplete<3;incomplete++){
     s=route();a=new MainActivity(s);a.requestReload();inspect(a,false);JSONObject page=snapshot(s,"draft");if(incomplete==0)page.put("draftComplete",false);else if(incomplete==1)page.put("draft",JSONObject.NULL).put("draftComplete",false).put("draftLength",600000).put("draftOmittedReason","too-long");else page.put("documentId","another-document-0004");respond(s,page);
     check("Unknown or incomplete input requires explicit independent confirmation "+incomplete,a.reloadDialog!=null&&a.reloadDialog.positiveLabel.equals("已保存，重新加载")&&s.reloads==0);a.reloadDialog.negative.run();check("Cancel independent confirmation retains current page "+incomplete,a.reloadDialog==null&&s.reloads==0);
   }
   s=route();LocalDraftPolicy.allowed=false;a=new MainActivity(s);start(a,false,"user draft");check("Disabled local saving requires manual loss acknowledgement",a.reloadDialog!=null&&a.reloadDialog.positiveLabel.equals("已保存，重新加载")&&DraftArchive.writes==0&&s.reloads==0);a.reloadDialog.positive.run();check("Explicit independent acknowledgement reaches actual reload",s.reloads==1&&s.pageMemory.forgot==1&&!s.pageMemory.restorePending);
   s=route();s.web.visible=false;a=new MainActivity(s);a.requestReload();check("Absent page cannot start driver capture",s.asyncCalls==0&&a.reloadDialog!=null);s.navigationEpoch++;a.reloadDialog.positive.run();check("Independent old confirmation cannot reload a replacement document",s.reloads==0);
   s=route();s.web.url="https://example.com/form";a=new MainActivity(s);a.requestReload();check("Generic webpage uses manual preservation before browser reload",s.asyncCalls==0&&a.reloadDialog!=null);a.reloadDialog.positive.run();check("Explicit generic-page reload uses existing native browser",s.web.current.reloads==1&&s.reloads==0);
   for(int blocked=0;blocked<5;blocked++){
     s=route();s.web.visible=false;a=new MainActivity(s);a.requestReload();switch(blocked){case 0:s.networkReady=false;break;case 1:s.offline=true;break;case 2:s.connecting=true;break;case 3:s.recoveryScheduled=true;break;case 4:s.guard.allowed=false;break;}a.reloadDialog.positive.run();check("Independent confirmation cannot bypass route guard "+blocked,s.reloads==0&&s.status.contains("网络未就绪"));
   }
   System.out.println(J.obj("status","passed","checks",checks.length(),"results",checks,"actualAndroidExecution",false));
 }
}
class ChatSession {
 final Object context=new Object();final int environmentGeneration=4;final String environmentId="environment-one";
 final Web web=new Web();final Prefs prefs=new Prefs();final WebReplyObserver webObserver=new WebReplyObserver(this);final Store webStore=new Store();final Memory pageMemory=new Memory();final Guard guard=new Guard();final Handler handler=new Handler();final Trace trace=new Trace();Audit audit;
 boolean deleted,uiVisible=true,navigating,navigationFailed,websiteConnectionIssue,websiteRecovering,spaTransition,documentNavigationSeen,awaitNewDocument,browserNavigationStopped;
 boolean navigationDispatched=true,networkReady=true,offline,connecting,recoveryScheduled,submitting,operation,transferActive,configurationCapture,fileBusy,inFlight,resourceUploadChecking,backgroundAttachmentCheck,resourceWebsiteBusy;
 long navigationEpoch=7,fileWorkGeneration,webWorkGeneration,stateEpoch=-1,resourceWebsiteEpoch=-1,resourceObserverEpoch=-1,resourceObservedAt,syncRun,resourceUploadCheckGeneration,resourceInspectionGeneration,navigationStarted,navigationMono,firstPageVisible,pageUsableAt;
 int spaStable,backgroundAttachmentStable,asyncCalls,reloads,routeEvents,workEvents;boolean lastCapture=true;
 String lastDocumentId="current-document-0001",appliedIdentity="route-one",conversation="https://chatgpt.com/c/A",navigationTarget="",navigationLabel="",priorDocumentId="",spaSignature="",resourceObserverBinding="",resourceObserverDocument="",resourceObserverUrl="",activeDeliveryId="",websiteProbeIssue="",status="",lastAction="";
 JSONObject pending,state=new JSONObject();Object resourceObserverPort;Result driverResult;
 interface Result{void accept(JSONObject value);}void asyncDriver(String action,JSONObject args,long ms,Result callback){lastAction=action;asyncCalls++;driverResult=callback;}
 boolean fileWorkActive(){return fileBusy;}boolean resourceFilesUncertain(){return false;}boolean resourceObservationCurrent(){return false;}boolean webPerformance(){return true;}boolean targetMatches(String url){return navigationTarget.equals(url);}void wakePolling(){}
 void resourceObserverRouteReady(JSONObject event,Object port){routeEvents++;}void resourceWebsiteObservation(JSONObject event,Object port){workEvents++;}
 void setStatus(String text){status=text;}void navigationTimeout(long epoch){}
 boolean navigate(String url,String label,boolean capture){lastCapture=capture;reloads++;return true;}
 /* CHAT */
}
class MainActivity {
 ChatSession session;Web remote;boolean destroyed,reloadChecking;ReferenceUi.Modal reloadDialog;final Handler handler=new Handler();
 MainActivity(ChatSession s){session=s;remote=s.web;}
 /* MAIN */
}
class WebReplyObserver {final ChatSession session;WebReplyObserver(ChatSession s){session=s;}/* OBSERVER */}
class BrowserRuntimePolicy {/* POLICY */}
class BrowserSettingsPolicy {/* REPLY_POLICY */}
class PageMemory {/* MEMORY */}
class ProfileUi {/* PROFILE */}
class ReferenceUi {static class Modal{static int shows;Runnable positive,negative;String positiveLabel,negativeLabel;boolean shown;java.util.function.Consumer<Object> dismiss;Modal(Object c,String title){}void note(String s){}void setOnDismissListener(java.util.function.Consumer<Object> c){dismiss=c;}void dismiss(){shown=false;if(dismiss!=null)dismiss.accept(this);}void buttons(String a,Runnable x,String b,Runnable y){negativeLabel=a;negative=x;positiveLabel=b;positive=y;}void show(){shown=true;shows++;}}}
class Browser {int reloads;boolean isOpen(){return true;}void reload(){reloads++;}}
class Web {boolean visible=true;String url="https://chatgpt.com/c/B";Browser current=new Browser();final Map<Object,Object> ports=new IdentityHashMap<>();Web(){ports.put(current,new Object());}String getUrl(){return url;}boolean resourcePage(String url){return MainActivity.chatUrl(url);}boolean hasVisibleDocument(){return visible;}}
class Profiles{static int slot=2;static int slot(Object c){return slot;}}
class ProfileCatalog{static int generation=4;static String environmentId="environment-one";static boolean available=true,deleting,resetting;static ProfileCatalog get(Object c){return new ProfileCatalog();}JSONObject item(int slot){return J.obj("created",available,"generation",generation,"environmentId",environmentId,"deleting",deleting,"resetting",resetting);}}
class Prefs{final Map<String,String> values=new HashMap<>();Runnable listener;boolean commitOk=true,throwCommit;int commits;String getString(String key,String fallback){return values.getOrDefault(key,fallback);}Editor edit(){return new Editor();}final class Editor{final Map<String,String> edits=new HashMap<>();final Set<String> removed=new HashSet<>();Editor putString(String k,String v){edits.put(k,v);return this;}Editor remove(String k){removed.add(k);return this;}boolean commit(){commits++;if(throwCommit)throw new RuntimeException("controlled unavailable storage");if(!commitOk)return false;for(String key:removed)values.remove(key);values.putAll(edits);Runnable once=listener;listener=null;if(once!=null)once.run();return true;}}}
class Memory{JSONObject remembered;int forgot;boolean restorePending;void forget(String url){forgot++;remembered=null;}void remember(String scope,String url,JSONObject state){remembered=state;}String scope(){return "environment-one";}}
class Store{final java.util.concurrent.Executor worker=Runnable::run;}
class DraftArchive{static boolean saved=true;static int writes;static DraftArchive get(Object c){return new DraftArchive();}boolean save(String url,String text,String kind,long revision){writes++;return saved;}}
class LocalDraftPolicy{static boolean allowed=true;static long revision=1;static boolean enabled(Object c){return allowed;}static long revision(Object c){return revision;}static String unavailable(Object c){return "草稿保存失败";}}
class ChatService{static int ends;static void end(Object c){ends++;}}
class Guard{boolean allowed=true;boolean allowed(){return allowed;}}
class Audit{void retirePageCheck(){}}
class Trace{void page(String label){}}
class Handler{void post(Runnable work){work.run();}void postDelayed(Runnable work,long delay){}}
class SystemClock{static long elapsedRealtime(){return 1000;}}
class J{static JSONObject obj(Object...v){JSONObject o=new JSONObject();try{for(int i=0;i<v.length;i+=2)o.put((String)v[i],v[i+1]);}catch(Exception e){throw new RuntimeException(e);}return o;}}
