package local.pocketchat;
import android.app.Activity;import android.os.Build;import android.content.*;import android.database.*;import android.database.sqlite.*;import org.json.*;import java.util.*;
public final class DefaultEnvironmentHost{
 static final JSONArray checks=new JSONArray();static void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));}
 static ProfileCatalog setup(int selected,int...created){Profiles.lastActivity=-1;android.os.Build.VERSION.SDK_INT=35;ProfileCatalog c=new ProfileCatalog();ProfileCatalog.instance=c;Set<Integer> set=new HashSet<>();for(int n:created)set.add(n);for(int n=0;n<8;n++){Map<String,Object> row=new LinkedHashMap<>();for(String k:new String[]{"slot","created","pid","seen","connected","waiting","mode","opened","favorite","privacy","desktop","generation","deleting","resetting"})row.put(k,0);for(String k:new String[]{"name","draft","problem","page","group_name","notes","environment_id"})row.put(k,"");row.put("slot",n);row.put("created",set.contains(n)?1:0);row.put("generation",10+n);row.put("environment_id",UUID.nameUUIDFromBytes(("environment-"+n).getBytes()).toString());row.put("name","Environment "+n);c.db.rows.put(n,row);}c.db.settings.put("defaultSlot",String.valueOf(selected));return c;}
 static void baseline()throws Exception{ProfileCatalog c=setup(2,0,1,2);c.beginDelete(2);check("Deleting nonzero default durably reassigns remaining slot",AppSettings.defaultSlot(c.root)==0&&"0".equals(c.db.settings.get("defaultSlot")));c=setup(2,1,2);c.beginDelete(2);check("Deleted zero slot cannot be used as fallback for another deleted default",AppSettings.defaultSlot(c.root)==1);c=setup(5,5);boolean rejected=false;try{c.beginDelete(5);}catch(java.io.IOException expected){rejected=true;}check("Existing last-environment guard remains",rejected&&c.item(5).optBoolean("created"));}
 static void await(java.util.concurrent.CountDownLatch latch){try{if(!latch.await(5,java.util.concurrent.TimeUnit.SECONDS))throw new AssertionError("thread gate timeout");}catch(InterruptedException error){throw new AssertionError(error);}}
 static void concurrency()throws Exception{
  final ProfileCatalog owner=setup(1,0,1);final EnvironmentSpec.Identity kept=owner.identity(0);java.util.concurrent.CountDownLatch updating=new java.util.concurrent.CountDownLatch(1),release=new java.util.concurrent.CountDownLatch(1),selecting=new java.util.concurrent.CountDownLatch(1);java.util.concurrent.atomic.AtomicReference<Throwable> error=new java.util.concurrent.atomic.AtomicReference<>();java.util.concurrent.atomic.AtomicBoolean selected=new java.util.concurrent.atomic.AtomicBoolean(true);
  owner.db.beforeUpdate=()->{updating.countDown();await(release);};owner.db.beforeBegin=()->{if(Thread.currentThread().getName().equals("select-deleting"))selecting.countDown();};
  Thread deletion=new Thread(()->{try{owner.beginDelete(1);}catch(Throwable e){error.set(e);}},"delete-default");deletion.start();await(updating);
  Thread selection=new Thread(()->{try{selected.set(AppSettings.defaultSlot(owner.root,1));}catch(Throwable e){error.set(e);}},"select-deleting");selection.start();await(selecting);release.countDown();deletion.join(5000);selection.join(5000);
  check("Concurrent default setter cannot reinstall the deleted slot",!deletion.isAlive()&&!selection.isAlive()&&error.get()==null&&!selected.get()&&AppSettings.defaultSlot(owner.root)==0&&owner.identity(0).equals(kept));
  final ProfileCatalog race=setup(0,0,1);java.util.concurrent.CountDownLatch go=new java.util.concurrent.CountDownLatch(1);java.util.concurrent.atomic.AtomicInteger deleted=new java.util.concurrent.atomic.AtomicInteger(),rejected=new java.util.concurrent.atomic.AtomicInteger();List<Thread> threads=new ArrayList<>();
  for(int slot=0;slot<2;slot++){final int id=slot;Thread thread=new Thread(()->{await(go);try{race.beginDelete(id);deleted.incrementAndGet();}catch(java.io.IOException expected){rejected.incrementAndGet();}},"delete-slot-"+slot);threads.add(thread);thread.start();}go.countDown();for(Thread thread:threads)thread.join(5000);
  int survivors=(race.item(0).optBoolean("created")?1:0)+(race.item(1).optBoolean("created")?1:0);check("Concurrent deletions retain exactly one usable original environment",threads.stream().noneMatch(Thread::isAlive)&&deleted.get()==1&&rejected.get()==1&&survivors==1&&race.available(AppSettings.defaultSlot(race.root)));
 }
 static void routing()throws Exception{
  ProfileCatalog c=setup(3);BrandLaunchActivity brand=new BrandLaunchActivity();brand.route();check("Direct launch with no available environment routes to manager without indexing Profiles",brand.launched!=null&&brand.launched.target==WindowHomeActivity.class&&Profiles.lastActivity==-1&&brand.finished);
  c=setup(2,1,2);EnvironmentSpec.Identity identity=c.identity(2);brand=new BrandLaunchActivity();brand.route();check("Valid default launch keeps exact selected environment identity",Profiles.lastActivity==2&&brand.launched!=null&&Boolean.TRUE.equals(brand.launched.extras.get("forceWebMode"))&&c.identity(2).equals(identity));
  c=setup(7);Activity downloads=new DownloadCenterActivity();WorkspaceNavigation.select(downloads,2,0);check("Conversation tab with no available environment opens existing manager",downloads.launched!=null&&downloads.launched.target==WindowHomeActivity.class&&Profiles.lastActivity==-1);
  WindowHomeActivity home=new WindowHomeActivity();WorkspaceNavigation.select(home,1,3);check("Manager with no available environment does not pass an invalid slot to Profiles",home.launched==null&&Profiles.lastActivity==-1);
  c=setup(2,1,2);WorkspaceNavigation.select(new DownloadCenterActivity(),2,0);check("Conversation navigation retains valid default fallback",Profiles.lastActivity==2);
 }
 static void current()throws Exception{
  for(int selected=0;selected<8;selected++){int other=(selected+1)%8;ProfileCatalog c=setup(selected,selected,other);EnvironmentSpec.Identity keep=c.identity(other),gone=c.identity(selected);c.beginDelete(selected);check("Default deletion chooses actual remaining environment "+selected,AppSettings.defaultSlot(c.root)==other&&String.valueOf(other).equals(c.db.settings.get("defaultSlot")));check("Only deleted generation advances; remaining UUID and generation stay exact "+selected,c.identity(other).equals(keep)&&c.item(selected).optInt("generation")==gone.generation+1&&c.item(selected).optString("environmentId").equals(gone.environmentId)&&!c.item(selected).optBoolean("created")&&c.item(selected).optBoolean("deleting"));int generation=c.item(selected).optInt("generation");c.beginDelete(selected);check("Repeated deletion does not reassign or advance generation "+selected,c.item(selected).optInt("generation")==generation&&AppSettings.defaultSlot(c.root)==other);boolean last=false;try{c.beginDelete(other);}catch(java.io.IOException expected){last=true;}check("Every slot retains the existing last-environment guard "+other,last&&c.identity(other).equals(keep));}
  ProfileCatalog c=setup(2,0,1,2);EnvironmentSpec.Identity kept=c.identity(2);c.beginDelete(1);check("Deleting nondefault preserves actual selected identity",AppSettings.defaultSlot(c.root)==2&&c.identity(2).equals(kept));
  c=setup(2,1,2,3);c.db.rows.get(1).put("resetting",1);c.beginDelete(2);check("Fallback excludes reset-in-progress environment",AppSettings.defaultSlot(c.root)==3);
  c=setup(2,1,2);c.db.rows.get(1).put("resetting",1);c.beginDelete(2);check("Existing created-count guard permits deletion but no unavailable default is invented",AppSettings.defaultSlot(c.root)==-1&&"-1".equals(c.db.settings.get("defaultSlot"))&&c.item(1).optBoolean("created"));c.db.rows.get(1).put("resetting",0);check("A completed reset becomes an actual available fallback",AppSettings.defaultSlot(c.root)==1);
  c=setup(0,0,1);c.db.rows.get(0).put("resetting",1);check("Temporary reset fallback does not replace the saved logical default",AppSettings.defaultSlot(c.root)==1&&"0".equals(c.db.settings.get("defaultSlot")));c.beginDelete(1);check("Deleting a temporary fallback preserves the resetting default identity",AppSettings.defaultSlot(c.root)==-1&&"0".equals(c.db.settings.get("defaultSlot"))&&c.item(0).optBoolean("created"));c.db.rows.get(0).put("resetting",0);check("Completing reset returns to the same saved default",AppSettings.defaultSlot(c.root)==0);
  c=setup(6,1,2);check("Legacy deleted default is repaired durably",AppSettings.defaultSlot(c.root)==1&&"1".equals(c.db.settings.get("defaultSlot")));c.db.rows.get(6).put("created",1);c.db.rows.get(6).put("environment_id",UUID.randomUUID().toString());check("Reused old slot cannot inherit a repaired default",AppSettings.defaultSlot(c.root)==1);
  for(String invalid:new String[]{"not-a-slot","-1","99"}){c=setup(0,3);c.db.settings.put("defaultSlot",invalid);check("Malformed or missing default selects current available row "+invalid,AppSettings.defaultSlot(c.root)==3&&"3".equals(c.db.settings.get("defaultSlot")));}
  c=setup(3,3);c.db.rows.get(3).put("deleting",1);check("No available row is explicit absence",AppSettings.defaultSlot(c.root)==-1&&AppSettings.recentSlot(c.root)==-1);
  c=setup(0,0,1);c.db.rows.get(1).put("resetting",1);check("Setter rejects resetting default without changing selection",!AppSettings.defaultSlot(c.root,1)&&AppSettings.defaultSlot(c.root)==0);c.db.rows.get(1).put("resetting",0);c.db.rows.get(1).put("deleting",1);check("Setter rejects deleting default",!AppSettings.defaultSlot(c.root,1));check("Setter rejects absent slot",!AppSettings.defaultSlot(c.root,6));
  c=setup(0,0,1);android.os.Build.VERSION.SDK_INT=27;check("Legacy Android only selects supported slot zero",!AppSettings.defaultSlot(c.root,1)&&AppSettings.defaultSlot(c.root)==0);c.db.rows.get(0).put("created",0);check("Legacy Android does not route an unsupported fallback",AppSettings.defaultSlot(c.root)==-1);android.os.Build.VERSION.SDK_INT=35;
  c=setup(2,1,2);String before=c.db.rows.toString();c.db.failDefaultWrite=true;boolean failed=false;try{c.beginDelete(2);}catch(java.io.IOException expected){failed=true;}check("Default write failure rolls back deletion and generation",failed&&before.equals(c.db.rows.toString())&&"2".equals(c.db.settings.get("defaultSlot"))&&c.db.begins==c.db.ends);
  c=setup(2,1,2);c.db.rows.get(2).put("generation",Integer.MAX_VALUE);failed=false;try{c.beginDelete(2);}catch(java.io.IOException expected){failed=true;}check("Deletion cannot wrap stable identity generation",failed&&c.item(2).optBoolean("created")&&c.item(2).optInt("generation")==Integer.MAX_VALUE);
  c=setup(99,0,1);before=c.db.rows.toString();c.db.failDefaultWrite=true;failed=false;try{c.beginDelete(1);}catch(java.io.IOException expected){failed=true;}check("Failed stale-default repair aborts deletion without a false success",failed&&before.equals(c.db.rows.toString())&&"99".equals(c.db.settings.get("defaultSlot")));
  c=setup(0,0,1);c.db.rows.get(1).put("opened",999L);c.db.rows.get(1).put("resetting",1);check("Recent navigation excludes unavailable row",AppSettings.recentSlot(c.root)==0);
 }
 public static void main(String[]args)throws Exception{if(Boolean.getBoolean("before"))baseline();else {current();concurrency();routing();}int passed=0;for(int i=0;i<checks.length();i++)if(checks.optJSONObject(i).optBoolean("pass"))passed++;System.out.println(J.obj("status",passed==checks.length()?"passed":"failed","passed",passed,"total",checks.length(),"checks",checks));if(passed!=checks.length())System.exit(1);}
}
class ProfileCatalog{static ProfileCatalog instance;final Context root=new Context();final SQLiteDatabase db=new SQLiteDatabase();static ProfileCatalog get(Context c){return instance;}SQLiteDatabase getReadableDatabase(){return db;}SQLiteDatabase getWritableDatabase(){return db;}/* CATALOG */}
class EnvironmentSpec{static JSONObject object(Object...x){return J.obj(x);}/* IDENTITY */}
class Profiles{static final int MAX=8;static int lastActivity=-1;static Class<?> activity(int slot){if(slot<0||slot>=MAX)throw new AssertionError("Invalid profile index");lastActivity=slot;return MainActivity.class;}}class UiPerfStats{static void catalogRead(){}}class DesignUi{static class Stars{static void setting(boolean b){}}}class QuietNotifications{static void clearCompletions(Context c){}}
class J{static JSONObject obj(Object...x){JSONObject o=new JSONObject();try{for(int i=0;i<x.length;i+=2)o.put((String)x[i],x[i+1]);}catch(Exception e){throw new RuntimeException(e);}return o;}}

class MainActivity extends Activity{}class DownloadCenterActivity extends Activity{}class AppSettingsActivity extends Activity{}class AppUpdates{static void schedule(android.content.Context c){}}
class BrandLaunchActivity extends Activity{/* BRAND */}
class WindowHomeActivity extends Activity{int lastWindow(){return AppSettings.recentSlot(this);}void showProblem(String message){}/* OPEN_WINDOW */}

/** New 46 dependencies are boundary adapters only. The original catalogue/default
 * cases do not exercise global reply-policy methods, metadata I/O, or UI rendering.
 * A reply-policy snapshot being constructed/read here is an explicit scope failure;
 * the full actual policy is exercised by background-reply-policy/runtime-host.
 */
class BackgroundReplyPolicy {
  static final class Snapshot {
    final boolean known,enabled;final long revision;final int legacyPendingMask;
    Snapshot(boolean known,boolean enabled,long revision,int legacyPendingMask){
      throw new AssertionError("Global background policy is outside the default/catalogue host");
    }
    static Snapshot unknown(){throw new AssertionError("Global background policy is outside the default/catalogue host");}
  }
}
/** Production calls this as an invalidation signal; no metadata/database work is
 * performed synchronously here. Actual download invalidation is covered elsewhere. */
class DownloadLibrary {
  static final java.util.concurrent.atomic.AtomicInteger notifications=new java.util.concurrent.atomic.AtomicInteger();
  static void changed(Context context){if(context==null)throw new AssertionError("Missing catalogue notification context");notifications.incrementAndGet();}
}
/** Manual-open marker boundary; the real nonce/owner/deadline behavior is covered
 * by experience46-overview-host. This fixture retains the original launch intent. */
class EnvironmentOverviewUi {
  static final java.util.concurrent.atomic.AtomicInteger markers=new java.util.concurrent.atomic.AtomicInteger();
  static void mark(Intent opening,Context context,int slot){if(opening==null||context==null||slot<0||slot>=Profiles.MAX)throw new AssertionError("Invalid manual overview marker");markers.incrementAndGet();}
}
