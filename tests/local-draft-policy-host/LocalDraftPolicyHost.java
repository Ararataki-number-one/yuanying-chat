package local.pocketchat;
import android.content.*;import org.json.*;import org.mozilla.geckoview.GeckoSession;import java.io.*;import java.nio.file.*;import java.util.*;import java.util.concurrent.*;import java.util.function.*;
public final class LocalDraftPolicyHost {
 static final JSONArray checks=new JSONArray();static final List<BrowserSessionStore> stores=new ArrayList<>();
 static void check(String name,boolean passed){checks.put(J.obj("name",name,"pass",passed));}
 static Context context()throws Exception{return new Context(Files.createTempDirectory("draft-policy-context-").toFile());}
 static void toggle(Context c,boolean value){AppPrefs.apply(c,J.obj("saveDraft",value));}
 static String url="https://chatgpt.com/c/owned";
 static JSONObject snapshot(String draft){return J.obj("ok",true,"url",url,"documentId","doc-1","contentKey","content-1","draft",draft,"hasDraft",!draft.isEmpty(),"draftComplete",true,"draftLength",draft.length(),"selectionStart",1,"selectionEnd",2,"scrollX",10,"scrollY",90);}
 static String sdk(){return J.obj("history",J.obj("entries",new JSONArray().put(J.obj("url",url,"title","Keep history")),"index",1),"scrolldata",J.obj("scroll","0,450","children",new JSONArray().put(J.obj("scroll","2,75"))),"formdata",J.obj("url",url,"id",J.obj("prompt","private draft"),"children",new JSONArray().put(J.obj("url",url+"/frame","innerHTML","child draft"))),"unrelated",J.obj("keep",true)).toString();}
 static BrowserSessionStore store(Context c){BrowserSessionStore s=new BrowserSessionStore(c);stores.add(s);return s;}
 static void flush(BrowserSessionStore s)throws Exception{s.io.submit(()->{}).get(5,TimeUnit.SECONDS);}
 static String diskBytes(Context c)throws Exception{return Files.readString(new File(c.getNoBackupFilesDir(),"gecko-session.json").toPath());}
 static String bytes(Context c)throws Exception{String raw=diskBytes(c);return raw.startsWith("PocketChat-Session-")?raw.substring(raw.indexOf('\n')+1):raw;}
 static String read(BrowserSessionStore s)throws Exception{CompletableFuture<String> value=new CompletableFuture<>();s.read(value::complete);return value.get(5,TimeUnit.SECONDS);}
 static boolean forms(String value){return value!=null&&J.parse(value).has("formdata");}
 static boolean sameWithoutForms(String value,String original){if(value==null)return false;JSONObject got=J.parse(value),wanted=J.parse(original);wanted.remove("formdata");return canonical(got).equals(canonical(wanted));}
 static String canonical(Object value){if(value instanceof JSONObject){JSONObject o=(JSONObject)value;List<String> keys=new ArrayList<>();Iterator<?> iter=o.keys();while(iter.hasNext())keys.add((String)iter.next());Collections.sort(keys);StringBuilder s=new StringBuilder("{");for(String k:keys)s.append(JSONObject.quote(k)).append(':').append(canonical(o.opt(k))).append(',');return s.append('}').toString();}if(value instanceof JSONArray){JSONArray a=(JSONArray)value;StringBuilder s=new StringBuilder("[");for(int i=0;i<a.length();i++)s.append(canonical(a.opt(i))).append(',');return s.append(']').toString();}return String.valueOf(value);}
 static void policy()throws Exception{
  Context c=context();check("Default draft saving remains enabled at revision zero",LocalDraftPolicy.enabled(c)&&LocalDraftPolicy.revision(c)==0);
  AppPrefs.apply(c,J.obj("restoreScroll",false));check("Unrelated preference does not change draft revision",LocalDraftPolicy.revision(c)==0);
  AppPrefs.apply(c,J.obj("saveDraft","false"));check("Nonboolean setting cannot change draft policy",LocalDraftPolicy.enabled(c)&&LocalDraftPolicy.revision(c)==0);
  JSONObject original=snapshot("retain current input"),on=LocalDraftPolicy.snapshot(c,original);check("Enabled snapshot retains draft and exact revision",on.optString("draft").equals("retain current input")&&LocalDraftPolicy.mayRestore(c,on));
  toggle(c,false);long off=LocalDraftPolicy.revision(c);check("Disabling advances revision once",off==1&&!LocalDraftPolicy.enabled(c));toggle(c,false);check("Repeated disabled save does not advance revision",LocalDraftPolicy.revision(c)==off);
  JSONObject redacted=LocalDraftPolicy.snapshot(c,original);check("Disabled snapshot omits text and selection but keeps scroll and draft presence",redacted.isNull("draft")&&!redacted.optBoolean("draftComplete")&&!redacted.has("selectionStart")&&!redacted.has("selectionEnd")&&redacted.optInt("scrollY")==90&&redacted.optBoolean("hasDraft"));
  JSONObject selection=snapshot("selected draft").put("selectionDirection","backward").put("draftSelection",J.obj("schema",1,"kind","contenteditable","anchor",9,"focus",2,"length",14));
  JSONObject privateRange=LocalDraftPolicy.snapshot(c,selection);check("Disabled snapshots omit both editor selection descriptors",!privateRange.has("selectionDirection")&&!privateRange.has("draftSelection")&&selection.has("draftSelection"));
  check("Snapshot policy never alters original visible draft object",original.optString("draft").equals("retain current input")&&original.optInt("selectionStart")==1);
  check("Disabled does not treat unknown draft as empty or complete",!PageMemory.completeDraft(redacted)&&PageMemory.hasDraft(redacted));
  toggle(c,true);check("Off on cycle invalidates pre-disable snapshot",LocalDraftPolicy.revision(c)==2&&!LocalDraftPolicy.mayRestore(c,on));
  JSONObject late=LocalDraftPolicy.snapshot(c,original,0);check("Late pre-disable capture stays redacted after enabling",late.isNull("draft")&&!PageMemory.completeDraft(late));
  check("New enabled snapshot can restore new draft",LocalDraftPolicy.mayRestore(c,LocalDraftPolicy.snapshot(c,snapshot("new input"))));
  String state=sdk(),filtered=LocalDraftPolicy.checkpoint(state,false);check("SDK disabled filter removes complete form tree only",sameWithoutForms(filtered,state)&&!forms(filtered));check("SDK enabled filter keeps original serialized bytes",state.equals(LocalDraftPolicy.checkpoint(state,true)));
  check("SDK disabled malformed JSON fails closed",LocalDraftPolicy.checkpoint("not-json-private-draft",false)==null);
 }
 static void archive()throws Exception{
  Context c=context();DraftArchive a=new DraftArchive(c);check("Enabled archive stores unsent draft",a.save(url,"existing history","before")&&a.list(url).length()==1);
  toggle(c,false);check("Disabled archive rejects nonempty new draft without deleting old history",!a.save(url,"new forbidden text","off")&&a.list(url).length()==1&&a.list(url).optJSONObject(0).optString("body").equals("existing history"));
  check("Disabled empty draft creates no archive row",a.save(url,"","empty")&&a.list(url).length()==1);
  toggle(c,true);check("Reenabled archive accepts newly supplied draft",a.save(url,"new allowed text","on")&&a.list(url).length()==2);
  toggle(c,false);check("Explicit clear is separate and removes archive history",Boolean.TRUE.equals(DraftArchive.class.getDeclaredMethod("clear").invoke(a))&&a.list(url).length()==0);
 }
 static void memory()throws Exception{
  Context c=context();ChatSession s=new ChatSession(c);PageMemory m=new PageMemory(s);toggle(c,false);m.remember(m.scope(),url,snapshot("disabled remember"));m.restorePending=true;m.restore(url,s.navigationEpoch);check("Disabled remember and restore never send a draft restoration",s.restore!=null&&!s.restore.optBoolean("allowDraft")&&s.restore.optJSONObject("state").isNull("draft")&&s.restore.optBoolean("allowScroll"));
  s.restoreCallback.accept(J.obj("conflict",true));check("Disabled restore conflict cannot queue archive write",s.webStore.worker.tasks.isEmpty());
  toggle(c,true);m.capture(()->s.done++);Consumer<JSONObject> late=s.capture;toggle(c,false);toggle(c,true);late.accept(snapshot("stale captured input"));m.restorePending=true;m.restore(url,s.navigationEpoch);check("Production capture callback across off on cannot restore old text",s.done==1&&!s.restore.optBoolean("allowDraft")&&s.restore.optJSONObject("state").isNull("draft"));
  m.capture(()->s.done++);s.capture.accept(snapshot("current allowed input"));m.restorePending=true;m.restore(url,s.navigationEpoch);check("Production fresh capture after enabling restores allowed text",s.restore.optBoolean("allowDraft")&&s.restore.optJSONObject("state").optString("draft").equals("current allowed input"));
  s.restoreCallback.accept(J.obj("conflict",true));toggle(c,false);toggle(c,true);s.webStore.worker.runAll();check("Queued conflict archive across off on must not persist old draft",DraftArchive.get(c).list(url).length()==0);
  m.capture(()->s.done++);Consumer<JSONObject> old=s.capture;m.remember(m.scope(),url,snapshot("newer snapshot"));old.accept(snapshot("older late snapshot"));m.restorePending=true;m.restore(url,s.navigationEpoch);check("Existing capture serial still protects newer snapshot",s.restore.optJSONObject("state").optString("draft").equals("newer snapshot"));
 }
 static void sessionStore()throws Exception{
  Context c=context();BrowserSessionStore s=store(c);String state=sdk();s.write(state);flush(s);check("Enabled session store writes complete current SDK snapshot",forms(bytes(c)));
  toggle(c,false);check("Read of preexisting SDK checkpoint filters old formdata",sameWithoutForms(read(s),state));check("Read filtering does not silently delete original checkpoint history",forms(bytes(c)));
  s.write(state);flush(s);check("Disabled session store writes only history scroll and unrelated fields",sameWithoutForms(bytes(c),state));s.write("invalid-private-snapshot");flush(s);check("Malformed disabled snapshot cannot replace safe checkpoint with raw data",sameWithoutForms(bytes(c),state));
  Context later=context();BrowserSessionStore queued=store(later);CountDownLatch started=new CountDownLatch(1),release=new CountDownLatch(1);queued.io.execute(()->{started.countDown();try{release.await(5,TimeUnit.SECONDS);}catch(InterruptedException e){throw new RuntimeException(e);}});if(!started.await(5,TimeUnit.SECONDS))throw new AssertionError("worker barrier");queued.write(state);toggle(later,false);toggle(later,true);release.countDown();flush(queued);check("Queued SDK snapshot across off on must not persist pre-disable forms",sameWithoutForms(bytes(later),state));
  queued.write(state);flush(queued);check("Fresh post-enable SDK checkpoint can persist forms",forms(bytes(later)));
  CountDownLatch reading=new CountDownLatch(1),readRelease=new CountDownLatch(1);queued.io.execute(()->{reading.countDown();try{readRelease.await(5,TimeUnit.SECONDS);}catch(InterruptedException e){throw new RuntimeException(e);}});if(!reading.await(5,TimeUnit.SECONDS))throw new AssertionError("read barrier");CompletableFuture<String> readResult=new CompletableFuture<>();queued.read(readResult::complete);toggle(later,false);toggle(later,true);readRelease.countDown();check("Queued SDK read across off on cannot expose old formdata",sameWithoutForms(readResult.get(5,TimeUnit.SECONDS),state));
  Context coalesced=context();BrowserSessionStore merging=store(coalesced);merging.write(()->{merging.write(()->{toggle(coalesced,false);toggle(coalesced,true);return null;});return state;});flush(merging);check("Coalesced valid bytes are filtered again after later snapshot toggles",sameWithoutForms(bytes(coalesced),state));

 }
 static void diskPolicy()throws Exception{
  String state=sdk();Context legacy=context();File file=new File(legacy.getNoBackupFilesDir(),"gecko-session.json");Files.writeString(file.toPath(),state);
  check("Legacy unstamped SDK checkpoint preserves default revision zero",read(store(legacy)).equals(state));
  toggle(legacy,false);toggle(legacy,true);String restored=read(store(legacy));
  check("Legacy disk forms cannot return after an off on cycle",sameWithoutForms(restored,state)&&diskBytes(legacy).equals(state));
  Context written=context();BrowserSessionStore first=store(written);first.write(state);flush(first);
  check("New checkpoint persists its write-time revision outside the exact SDK payload",diskBytes(written).equals("PocketChat-Session-1:0\n"+state));
  toggle(written,false);check("Disabled read of stamped disk retains only SDK history and scroll",sameWithoutForms(read(first),state));toggle(written,true);
  String cold=read(store(written));check("Cold new store rejects committed forms from an earlier enabled revision",sameWithoutForms(cold,state)&&forms(bytes(written)));
  GeckoWebView view=new GeckoWebView(written);view.restoreCheckpoint(view.current,GeckoSession.SessionState.fromString(cold),url,LocalDraftPolicy.revision(written));
  check("Actual SDK restore consumer cannot rebind filtered cold disk forms to current policy",view.current.restores==1&&sameWithoutForms(view.current.last.toString(),state));
  BrowserSessionStore fresh=store(written);fresh.write(state);flush(fresh);check("A fresh post-enable write is cold-restorable under its persisted new revision",diskBytes(written).startsWith("PocketChat-Session-1:2\n")&&read(store(written)).equals(state));
  for(String header:new String[]{"PocketChat-Session-1:-1","PocketChat-Session-1:9223372036854775808","PocketChat-Session-1:garbled","PocketChat-Session-2:2"}){
   Files.writeString(new File(written.getNoBackupFilesDir(),"gecko-session.json").toPath(),header+"\n"+state);check("Invalid or unsupported disk header cannot enable forms: "+header,sameWithoutForms(read(store(written)),state));
  }
  check("Truncated checkpoint header fails closed",LocalDraftPolicy.readCheckpoint("PocketChat-Session-1:2",true,2)==null);
  Context maximum=context();BrowserSessionStore bounded=store(maximum);String limit="x".repeat(BrowserSessionStore.LIMIT);bounded.write(limit);flush(bounded);check("Header does not reduce the existing SDK payload size limit",read(bounded).equals(limit)&&diskBytes(maximum).length()<=BrowserSessionStore.LIMIT+65);
  Files.writeString(new File(maximum.getNoBackupFilesDir(),"gecko-session.json").toPath(),limit+"x");check("Oversized legacy raw payload still fails the original bound",read(bounded)==null);
  Files.writeString(new File(maximum.getNoBackupFilesDir(),"gecko-session.json").toPath(),"PocketChat-Session-1:0\n"+limit+"x");check("Header allowance cannot expand SDK payload size",read(bounded)==null);
 }
 static void restore()throws Exception{
  String state=sdk();Context c=context();GeckoWebView view=new GeckoWebView(c);GeckoSession target=view.current;GeckoSession.SessionState snapshot=GeckoSession.SessionState.fromString(state);view.restoreCheckpoint(target,snapshot,url,LocalDraftPolicy.revision(c));check("Enabled SDK restore keeps existing synchronous path",target.restores==1&&forms(target.last.toString()));
  Context cycled=context();GeckoWebView old=new GeckoWebView(cycled);long previous=LocalDraftPolicy.revision(cycled);toggle(cycled,false);toggle(cycled,true);old.restoreCheckpoint(old.current,GeckoSession.SessionState.fromString(state),url,previous);flush(old.sessionStore);old.owner.handler.runAll();check("Reenabled SDK restore rejects forms from an older policy revision",old.current.restores==1&&sameWithoutForms(old.current.last.toString(),state));
  for(String invalid:new String[]{"none","target","epoch","guard","deleted","destroyed","closed"}){
   Context off=context();toggle(off,false);GeckoWebView v=new GeckoWebView(off);GeckoSession owned=v.current;v.restoreCheckpoint(owned,GeckoSession.SessionState.fromString(state),url,LocalDraftPolicy.revision(off));flush(v.sessionStore);
   switch(invalid){case "target":v.current=new GeckoSession();break;case "epoch":v.owner.navigationEpoch++;break;case "guard":v.owner.guard.allowed=false;break;case "deleted":v.owner.deleted=true;break;case "destroyed":v.destroyed=true;break;case "closed":owned.open=false;break;}
   v.owner.handler.runAll();check("SDK filtered restore respects "+invalid+" lifecycle",invalid.equals("none")?owned.restores==1&&sameWithoutForms(owned.last.toString(),state):owned.restores==0&&owned.loads==0);
  }
  Context bad=context();toggle(bad,false);GeckoWebView v=new GeckoWebView(bad);v.restoreCheckpoint(v.current,new GeckoSession.SessionState("bad-json"),url,LocalDraftPolicy.revision(bad));flush(v.sessionStore);v.owner.handler.runAll();check("Invalid disabled SDK state falls back to load without raw restore",v.current.restores==0&&v.current.loads==1&&v.current.loaded.equals(url));
 }
 static void baseline()throws Exception{Context c=context();DraftArchive a=new DraftArchive(c);check("Before enabled archive sanity",a.save(url,"retained history","on")&&a.list(url).length()==1);toggle(c,false);check("Disabled production archive must reject new persistent text",!a.save(url,"forbidden disabled text","off")&&a.list(url).length()==1);ChatSession session=new ChatSession(c);PageMemory memory=new PageMemory(session);JSONObject input=snapshot("unsent live draft");memory.remember(memory.scope(),url,input);memory.restorePending=true;memory.restore(url,session.navigationEpoch);check("Disabled production PageMemory must not restore captured draft",session.restore!=null&&!session.restore.optBoolean("allowDraft"));check("Before reproduction leaves supplied live draft unchanged",input.optString("draft").equals("unsent live draft"));}
 static void navigationArchive()throws Exception{
  for(String mode:new String[]{"enabled","off-on","off-then-on","disabled"}){
   // Each context models a separate environment process, including its static archive singleton.
   java.lang.reflect.Field singleton=DraftArchive.class.getDeclaredField("instance");singleton.setAccessible(true);singleton.set(null,null);
   Context c=context();if(mode.equals("off-then-on"))toggle(c,false);ChatSession s=new ChatSession(c);
   JSONObject job=J.obj("kind","web","id","owned-navigation-job","expectedUrl",url,"prompt","retired observation prompt");s.pending=job;
   boolean retired=new WebReplyObserver(s).archiveNavigation(job);
   if(mode.equals("off-on")){toggle(c,false);toggle(c,true);}else if(mode.equals("off-then-on"))toggle(c,true);else if(mode.equals("disabled"))toggle(c,false);
   s.webStore.worker.runAll();int expected=mode.equals("enabled")?1:0;
   check("Queued navigation archive respects captured draft policy "+mode,retired&&s.pending==null&&DraftArchive.get(c).list(url).length()==expected);
   check("Draft policy never drops the independent archived send observation "+mode,c.getSharedPreferences("chat",0).getString("archivedWebObservation","").contains("owned-navigation-job"));
  }
 }
 public static void main(String[] args)throws Exception{try{if(Boolean.getBoolean("draft.before"))baseline();else{policy();archive();memory();sessionStore();diskPolicy();restore();navigationArchive();}}finally{for(BrowserSessionStore s:stores)s.io.shutdownNow();}int passed=0;for(int i=0;i<checks.length();i++)if(checks.optJSONObject(i).optBoolean("pass"))passed++;System.out.println(J.obj("status",passed==checks.length()?"passed":"failed","passed",passed,"total",checks.length(),"checks",checks));if(passed!=checks.length())System.exit(1);}
}
class J{static JSONObject obj(Object... pairs){JSONObject out=new JSONObject();try{for(int i=0;i<pairs.length;i+=2)out.put((String)pairs[i],pairs[i+1]);}catch(JSONException e){throw new RuntimeException(e);}return out;}static JSONObject parse(String value){try{return new JSONObject(value);}catch(Exception e){return new JSONObject();}}}
class AppPrefs{/* APPPREFS */}
class Queue implements Executor{final ArrayDeque<Runnable> tasks=new ArrayDeque<>();public void execute(Runnable r){tasks.add(r);}void post(Runnable r){tasks.add(r);}void runAll(){while(!tasks.isEmpty())tasks.remove().run();}}
class ChatSession{final Context context;final SharedPreferences prefs;final Queue handler=new Queue();final Store webStore=new Store();final Web web=new Web();final Guard guard=new Guard();String appliedIdentity="identity",status="",activeDeliveryId="",observedReplyJob="",observedReplyUrl="",observedReplyKey="",observedReplyRevision="",observedReplyMarkdown="";JSONObject pending;boolean submitting,operation,deleted,observedReplyHasFiles;long navigationEpoch=1;int done;JSONObject restore;Consumer<JSONObject> capture,restoreCallback;ChatSession(Context c){context=c;prefs=c.getSharedPreferences("chat",0);}void runDriver(String action,JSONObject args,Consumer<JSONObject> callback){capture=callback;}void asyncDriver(String action,JSONObject args,int timeout,Consumer<JSONObject> callback){restore=args;restoreCallback=callback;}void setStatus(String value){status=value;}void resetReplyStability(){}void delivery(String id,String status,String reason,boolean website,String user,String url){}}
class Store{final Queue worker=new Queue();}class Web{String cookieStamp="cookies",url=LocalDraftPolicyHost.url;String getUrl(){return url;}}class Guard{boolean allowed=true;boolean allowed(){return allowed;}}class NativeNetwork{static String hash(String text){return text;}}class WebReplyObserver{final ChatSession session;JSONObject lastNavigationArchivedJob;long navigationArchiveSequence;WebReplyObserver(ChatSession s){session=s;}static boolean same(String a,String b){return Objects.equals(a,b);}/* ARCHIVE_OBSERVER */}class MainActivity{static boolean chatUrl(String url){return url.startsWith("https://chatgpt.com/");}}
class ChatService{static void end(Context context){}}
class GeckoWebView{
 final ChatSession owner;final BrowserSessionStore sessionStore;GeckoSession current=new GeckoSession();boolean destroyed,protectionAllowed=true,identityAllowed=true;ProtectionRestore protectionRestore;
 static final class ProtectionRestore{final GeckoSession session;final GeckoSession.SessionState state;final String url;final long draftRevision,navigation;ProtectionRestore(GeckoSession session,GeckoSession.SessionState state,String url,long draftRevision,long navigation){this.session=session;this.state=state;this.url=url;this.draftRevision=draftRevision;this.navigation=navigation;}}
 boolean protectionAllowsNetwork(){return protectionAllowed;}boolean identityRequestAllowed(String url){return identityAllowed;}
 GeckoWebView(Context c){owner=new ChatSession(c);sessionStore=LocalDraftPolicyHost.store(c);}/* RESTORE */
}
