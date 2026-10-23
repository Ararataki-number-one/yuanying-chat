package local.pocketchat;
import java.util.*;import org.json.*;
/** Exact production reload/archival members; callbacks and widgets are controlled host adapters. */
public class ReloadRequestHost {
 static final JSONArray checks=new JSONArray();
 static void check(String name,boolean passed){checks.put(J.obj("name",name,"passed",passed));}
 static ChatSession route(){ProfileCatalog.generation=4;ProfileCatalog.environmentId="environment-one";ProfileCatalog.available=true;ProfileCatalog.deleting=false;ProfileCatalog.resetting=false;Profiles.slot=2;ChatService.ends=0;return new ChatSession();}
 static JSONObject job(String id,String path){return J.obj("id",id,"kind","web","confirmed",true,"confirmedUrl","https://chatgpt.com/c/"+path,"expectedUrl","https://chatgpt.com/c/"+path,"prompt","already sent fixture question","userKey","id:user");}
 static JSONObject inspect(ChatSession s){return J.obj("url",s.web.url,"composer",true,"hasMessages",true,"busy",true);}
 static JSONObject snapshot(ChatSession s){return J.obj("ok",true,"url",s.web.url,"documentId",s.lastDocumentId,"draft","unsent controlled browser draft","draftComplete",true,"draftLength",31);}
 static void inspect(MainActivity a){a.session.driverResult.accept(inspect(a.session));}
 static void page(MainActivity a){if(a.session.lastAction.equals("page-state"))a.session.driverResult.accept(snapshot(a.session));}
 static void mutate(ChatSession s,int n){switch(n){case 0:s.navigationEpoch++;break;case 1:s.web.url="https://chatgpt.com/c/C";break;case 2:s.lastDocumentId="replacement-document";break;case 3:s.web.current=new Object();break;case 4:s.appliedIdentity="route-other";break;case 5:s.fileWorkGeneration++;s.fileBusy=true;break;case 6:s.replyBusy=true;break;case 7:ProfileCatalog.generation++;break;case 8:ProfileCatalog.environmentId="environment-other";break;case 9:ProfileCatalog.deleting=true;break;case 10:ProfileCatalog.resetting=true;break;case 11:Profiles.slot++;break;case 12:s.deleted=true;break;case 13:s.pending=job("new-job","B");break;case 14:s.pending=job("old-job","B");break;}}
 public static void main(String[] args)throws Exception{
  ChatSession s=route();s.pending=job("old-job","A");JSONObject old=s.pending;MainActivity a=new MainActivity(s);a.requestReload();inspect(a);page(a);
  JSONObject reproduction=J.obj("currentUrl",s.web.url,"cachedConversation",s.conversation,"oldJob",old.optString("id"),"pendingAfter",s.pending==null?JSONObject.NULL:s.pending.optString("id"),"lastAction",s.lastAction,"modalPresent",a.reloadDialog!=null,"reloadChecking",a.reloadChecking,"reloadCalls",a.reloadCalls,"archiveCommits",s.prefs.commits,"deliveryState",s.deliveryState);
  check("Production requestReload archives old A observation and still confirms current B",a.reloadDialog!=null&&a.reloadDialog.shown&&a.reloadDialog.positiveLabel.equals("重新加载")&&a.reloadDialog.negativeLabel.equals("取消")&&s.pending==null&&s.prefs.commits==1&&s.deliveryState.equals("uncertain")&&a.reloadCalls==0);
  check("Archival preserves original old job and cached resume URL",s.prefs.values.get("archivedWebObservation").equals(old.toString())&&s.conversation.endsWith("/A")&&s.web.url.endsWith("/B"));
  if(a.reloadDialog!=null)a.reloadDialog.negative.run();check("Host cancel keeps draft and performs no reload",a.reloadDialog==null&&a.reloadCalls==0&&s.draft.equals("unsent controlled browser draft"));
  for(int mutation=0;mutation<15;mutation++){s=route();s.pending=job("old-job","A");a=new MainActivity(s);a.requestReload();mutate(s,mutation);inspect(a);page(a);check("Stale target before inspect is rejected field "+mutation,a.reloadDialog==null&&a.reloadCalls==0&&s.prefs.commits==0);}
  for(int mutation=0;mutation<15;mutation++){s=route();s.pending=job("old-job","A");final ChatSession owner=s;final int changed=mutation;s.prefs.listener=()->mutate(owner,changed);a=new MainActivity(s);a.requestReload();inspect(a);page(a);check("Archival listener change cannot rebind confirmation field "+mutation,a.reloadDialog==null&&a.reloadCalls==0&&(mutation<13||s.pending!=null));}
  for(String id:new String[]{"new-job","old-job"}){s=route();s.pending=job("old-job","A");final ChatSession owner=s;JSONObject replacement=job(id,"B");s.prefs.listener=()->{owner.pending=replacement;owner.activeDeliveryId=id;owner.prefs.edit().putString("pending",replacement.toString()).commit();};a=new MainActivity(s);a.requestReload();inspect(a);page(a);check("Reentrant persisted replacement survives without ending its service "+id,s.pending==replacement&&s.prefs.values.get("pending").equals(replacement.toString())&&s.activeDeliveryId.equals(id)&&s.deliveryState.isEmpty()&&ChatService.ends==0&&a.reloadDialog==null&&a.reloadCalls==0);}
  s=route();a=new MainActivity(s);a.requestReload();inspect(a);page(a);check("No pending job uses the original confirmation without archival",a.reloadDialog!=null&&s.prefs.commits==0);
  s=route();s.pending=job("old-job","B");a=new MainActivity(s);a.requestReload();inspect(a);page(a);check("Current B pending job retains original busy confirmation without archival",a.reloadDialog!=null&&s.pending!=null&&s.prefs.commits==0);
  s=route();s.pending=job("old-job","A");s.prefs.commitOk=false;a=new MainActivity(s);a.requestReload();inspect(a);page(a);check("Failed archive does not clear pending or bypass ordinary confirmation",a.reloadDialog!=null&&s.pending!=null&&s.deliveryState.isEmpty());
  s=route();s.pending=job("old-job","A");a=new MainActivity(s);final MainActivity reentrant=a;s.prefs.listener=reentrant::requestReload;a.requestReload();inspect(a);page(a);check("Reentrant reload request cannot start another inspection",s.asyncCalls==2&&a.reloadDialog!=null&&s.prefs.commits==1);
  for(int mutation=0;mutation<15;mutation++){s=route();s.pending=job("old-job","A");a=new MainActivity(s);a.requestReload();inspect(a);mutate(s,mutation);page(a);check("Rebound target still rejects changes before page callback field "+mutation,a.reloadDialog==null&&a.reloadCalls==0);}
  s=route();s.pending=job("old-job","A");a=new MainActivity(s);a.requestReload();inspect(a);a.destroyed=true;page(a);check("Activity destruction rejects page callback",a.reloadDialog==null&&a.reloadCalls==0);
  boolean pass=true;for(int i=0;i<checks.length();i++)pass&=checks.getJSONObject(i).getBoolean("passed");System.out.println(J.obj("status",pass?"passed":"failed","checks",checks.length(),"results",checks,"reproduction",reproduction));if(!pass)System.exit(1);
 }
}
class ChatSession {
 final Object context=new Object();final int environmentGeneration=4;final String environmentId="environment-one";final Web web=new Web();final Prefs prefs=new Prefs();final WebReplyObserver webObserver=new WebReplyObserver(this);final Store webStore=new Store();
 long navigationEpoch=7,fileWorkGeneration;boolean fileBusy,replyBusy,deleted,observedReplyHasFiles;String lastDocumentId="document-one",appliedIdentity="route-one",conversation="https://chatgpt.com/c/A",activeDeliveryId="old-job",observedReplyJob="",observedReplyUrl="",observedReplyKey="",observedReplyRevision="",observedReplyMarkdown="",status="",deliveryState="",draft="unsent controlled browser draft",lastAction="";JSONObject pending;Result driverResult;int asyncCalls;
 interface Result{void accept(JSONObject value);}void asyncDriver(String action,JSONObject args,long ms,Result callback){lastAction=action;asyncCalls++;driverResult=callback;}boolean fileWorkActive(){return fileBusy;}boolean currentReplyActive(){return replyBusy;}boolean resourceFilesUncertain(){return false;}void setStatus(String s){status=s;}void resetReplyStability(){}void delivery(String id,String state,String detail,boolean attempted,String key,String url){deliveryState=state;}
 /* CHAT */
}
class MainActivity {
 ChatSession session;Web remote;boolean destroyed,reloadChecking;ReferenceUi.Modal reloadDialog;int reloadCalls;MainActivity(ChatSession s){session=s;remote=s.web;}static boolean chatUrl(String u){return u!=null&&u.startsWith("https://chatgpt.com/");}void reloadCurrent(ChatSession.ReloadTarget t,JSONObject p){if(reloadMatches(t)&&t.matchesSnapshot(p))reloadCalls++;}
 /* MAIN */
}
class WebReplyObserver {final ChatSession session;WebReplyObserver(ChatSession s){session=s;}/* OBSERVER */}
class BrowserRuntimePolicy {/* POLICY */}
class PageMemory {/* MEMORY */}
class ReferenceUi {static class Modal{Runnable positive,negative;String positiveLabel,negativeLabel;boolean shown;java.util.function.Consumer<Object> dismiss;Modal(Object c,String title){}void note(String s){}void setOnDismissListener(java.util.function.Consumer<Object> c){dismiss=c;}void dismiss(){shown=false;if(dismiss!=null)dismiss.accept(this);}void buttons(String a,Runnable x,String b,Runnable y){negativeLabel=a;negative=x;positiveLabel=b;positive=y;}void show(){shown=true;}}}
class Web{String url="https://chatgpt.com/c/B";Object current=new Object();String getUrl(){return url;}boolean hasVisibleDocument(){return true;}}
class Profiles{static int slot=2;static int slot(Object c){return slot;}}
class ProfileCatalog{static int generation=4;static String environmentId="environment-one";static boolean available=true,deleting,resetting;static ProfileCatalog get(Object c){return new ProfileCatalog();}JSONObject item(int slot){return J.obj("created",available,"generation",generation,"environmentId",environmentId,"deleting",deleting,"resetting",resetting);}}
class Prefs{final Map<String,String>values=new HashMap<>();Runnable listener;boolean commitOk=true;int commits;Prefs edit(){return this;}Prefs putString(String k,String v){values.put(k,v);return this;}Prefs remove(String k){values.remove(k);return this;}boolean commit(){commits++;if(listener!=null){Runnable once=listener;listener=null;once.run();}return commitOk;}}
class Store{final java.util.concurrent.Executor worker=r->{};}
class DraftArchive{static DraftArchive get(Object c){return new DraftArchive();}boolean save(String u,String t,String k){return true;}}
class ChatService{static int ends;static void end(Object c){ends++;}}
class ProfileUi{static boolean working(ChatSession s){return s.pending!=null||s.fileWorkActive()||s.currentReplyActive();}}
class LoginPagePolicy{static boolean login(String u){return false;}}
class J{static JSONObject obj(Object...v){JSONObject o=new JSONObject();try{for(int i=0;i<v.length;i+=2)o.put((String)v[i],v[i+1]);}catch(Exception e){throw new RuntimeException(e);}return o;}}
