package local.pocketchat;

import java.util.*;
import java.util.concurrent.Executor;
import java.util.function.Consumer;
import org.json.JSONObject;

/** Deterministic dependencies only. The complete DeferredBrowserSettings class
 * and its delayed callback chain under test are production sources. */
final class WorkQueue implements Executor {final ArrayDeque<Runnable> jobs=new ArrayDeque<>();public void execute(Runnable work){jobs.add(work);}void post(Runnable work){jobs.add(work);}void run(){while(!jobs.isEmpty())jobs.remove().run();}}
final class FakePrefs {
  final Map<String,Object> values=new HashMap<>();boolean failCommit;
  boolean contains(String key){return values.containsKey(key);}
  int getInt(String key,int fallback){Object value=values.get(key);return value instanceof Number?((Number)value).intValue():fallback;}
  boolean getBoolean(String key,boolean fallback){Object value=values.get(key);return value instanceof Boolean?(Boolean)value:fallback;}
  Editor edit(){return new Editor();}
  final class Editor {final Map<String,Object> next=new HashMap<>();final Set<String> remove=new HashSet<>();Editor putInt(String key,int value){next.put(key,value);return this;}Editor putBoolean(String key,boolean value){next.put(key,value);return this;}Editor remove(String key){remove.add(key);return this;}boolean commit(){if(failCommit)return false;for(String key:remove)values.remove(key);values.putAll(next);return true;}}
}
final class FakeContext {boolean desktop,saved=true;int displayWrites,draftWrites;}
final class IdentityTemplateController {boolean queueUnavailable;}
final class FakePrivacy {final ChatSession session;FakePrivacy(ChatSession session){this.session=session;}int level(){return session.prefs.getInt("privacyLevel",1);}boolean wantsDesktop(){return session.context.desktop;}}
final class FakeWeb {boolean failed;int checkpoints;String url="https://chatgpt.com/c/synthetic";String getUrl(){return url;}void checkpointState(){checkpoints++;}}
final class FakePage {int remembered;String scope(){return "synthetic-draft-scope";}void remember(String scope,String url,JSONObject state){remembered++;}}
final class FakeStore {final WorkQueue worker=new WorkQueue();}
final class ChatSession {
  final FakePrefs prefs=new FakePrefs();final FakeContext context=new FakeContext();final IdentityTemplateController identity=new IdentityTemplateController();
  final FakePrivacy privacy=new FakePrivacy(this);final FakeWeb web=new FakeWeb();final FakePage pageMemory=new FakePage();final FakeStore webStore=new FakeStore();final WorkQueue handler=new WorkQueue();
  boolean deleted,connecting,navigating,recoveryScheduled,identityApplicationPending,configurationCapture,operation;long lastDeferredBrowserAttempt,navigationEpoch=1;int applied;String status;
  final ArrayDeque<Action> actions=new ArrayDeque<>();
  static final class Action {final String name;final Consumer<JSONObject> done;Action(String name,Consumer<JSONObject> done){this.name=name;this.done=done;}}
  void asyncDriver(String name,JSONObject args,long timeout,Consumer<JSONObject> done){actions.add(new Action(name,done));}
  void reply(String name,JSONObject value){Action action=actions.remove();if(!name.equals(action.name))throw new AssertionError("Unexpected pending driver action "+action.name);action.done.accept(value);}
  void applyBrowserSettings(boolean protection){applied++;}
  void setStatus(String value){status=value;}
}
final class ProfileUi {static boolean working(ChatSession session){return session.operation;}}
final class ProfileCatalog {final FakeContext context;ProfileCatalog(FakeContext context){this.context=context;}static ProfileCatalog get(FakeContext context){return new ProfileCatalog(context);}void browserDisplay(int slot,boolean desktop){context.desktop=desktop;context.displayWrites++;}}
final class Profiles {static int slot(FakeContext context){return 0;}}
final class MainActivity {static boolean chatUrl(String url){return url.startsWith("https://chatgpt.com/");}}
final class WebReplyObserver {static boolean same(String a,String b){return a.equals(b);}}
final class DraftArchive {final FakeContext context;DraftArchive(FakeContext context){this.context=context;}static DraftArchive get(FakeContext context){return new DraftArchive(context);}boolean save(String url,String draft,String label){context.draftWrites++;return context.saved;}}
