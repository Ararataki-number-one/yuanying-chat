package local.pocketchat;

import android.database.sqlite.SQLiteDatabase;
import org.json.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/** Executes the complete production AppSettings class against explicit host adapters. */
public final class BackgroundReplyPolicyHost {
  static final JSONArray checks=new JSONArray();
  static void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));}
  static ProfileCatalog setup(){ProfileCatalog fixture=new ProfileCatalog();ProfileCatalog.instance=fixture;return fixture;}
  static void await(CountDownLatch gate){try{if(!gate.await(5,TimeUnit.SECONDS))throw new AssertionError("Synthetic thread gate timed out");}catch(InterruptedException failure){Thread.currentThread().interrupt();throw new AssertionError(failure);}}
  static void join(Thread thread)throws InterruptedException{thread.join(5000);if(thread.isAlive())throw new AssertionError("Synthetic worker did not finish: "+thread.getName());}
  static Map<String,String> valid(boolean enabled,long revision,int pending){Map<String,String> values=new LinkedHashMap<>();values.put(AppSettings.REPLY_POLICY_VERSION,"1");values.put(AppSettings.REPLY_POLICY_ENABLED,String.valueOf(enabled));values.put(AppSettings.REPLY_POLICY_REVISION,String.valueOf(revision));values.put(AppSettings.REPLY_POLICY_PENDING,String.valueOf(pending));return values;}
  static boolean matches(BackgroundReplyPolicy.Snapshot value,boolean enabled,long revision,int pending){return value.known&&value.enabled==enabled&&value.revision==revision&&value.legacyPendingMask==pending;}
  static boolean rejected(Runnable action){try{action.run();return false;}catch(IllegalArgumentException|IllegalStateException expected){return true;}}

  static void initialization()throws Exception {
    ProfileCatalog fixture=setup();SQLiteDatabase db=fixture.db;
    BackgroundReplyPolicy.Snapshot missing=AppSettings.readBackgroundReplyPolicy(fixture.root);
    check("Missing authority is unknown and disabled",!missing.known&&!missing.enabled);
    CountDownLatch go=new CountDownLatch(1);List<Thread> threads=new ArrayList<>();
    List<BackgroundReplyPolicy.Snapshot> values=Collections.synchronizedList(new ArrayList<>());AtomicReference<Throwable> error=new AtomicReference<>();
    for(int worker=0;worker<16;worker++){Thread thread=new Thread(()->{await(go);try{values.add(AppSettings.initializeBackgroundReplyPolicy(fixture.root));}catch(Throwable failure){error.compareAndSet(null,failure);}},"initializer-"+worker);threads.add(thread);thread.start();}
    go.countDown();for(Thread thread:threads)join(thread);
    check("Concurrent initializers create one disabled revision and full compatibility mask",error.get()==null&&values.size()==16&&values.stream().allMatch(value->matches(value,false,1,255))&&db.snapshot().equals(valid(false,1,255)));
    check("Concurrent initialization writes the four authority fields once",db.writeAttempts==4&&db.balanced());
    int queries=db.queries;BackgroundReplyPolicy.Snapshot once=AppSettings.readBackgroundReplyPolicy(fixture.root);
    check("Authority read obtains all fields with one query",matches(once,false,1,255)&&db.queries==queries+1);
  }

  static void explicitDecisionAndCompatibility()throws Exception {
    ProfileCatalog fixture=setup();SQLiteDatabase db=fixture.db;AppSettings.initializeBackgroundReplyPolicy(fixture.root);
    check("Explicit enable advances the decision revision",matches(AppSettings.setBackgroundReplyPolicy(fixture.root,true),true,2,255));
    check("Repeated explicit enable is idempotent",matches(AppSettings.setBackgroundReplyPolicy(fixture.root,true),true,2,255));
    CountDownLatch go=new CountDownLatch(1);List<Thread> threads=new ArrayList<>();AtomicReference<Throwable> error=new AtomicReference<>();
    for(int slot=0;slot<8;slot++){final int owned=slot;Thread thread=new Thread(()->{await(go);try{AppSettings.backgroundReplyLegacyCommitted(fixture.root,owned);}catch(Throwable failure){error.compareAndSet(null,failure);}},"compatibility-"+slot);threads.add(thread);thread.start();}
    go.countDown();for(Thread thread:threads)join(thread);
    check("Late concurrent compatibility acknowledgments preserve explicit enable and revision",error.get()==null&&matches(AppSettings.readBackgroundReplyPolicy(fixture.root),true,2,0)&&db.balanced());
    check("A late initializer cannot reset a later explicit enable",matches(AppSettings.initializeBackgroundReplyPolicy(fixture.root),true,2,0));
    check("Repeated compatibility acknowledgment leaves policy unchanged",!rejected(()->AppSettings.backgroundReplyLegacyCommitted(fixture.root,7))&&matches(AppSettings.readBackgroundReplyPolicy(fixture.root),true,2,0));
    check("Invalid compatibility slots cannot touch authority",rejected(()->AppSettings.backgroundReplyLegacyCommitted(fixture.root,-1))&&rejected(()->AppSettings.backgroundReplyLegacyCommitted(fixture.root,8))&&matches(AppSettings.readBackgroundReplyPolicy(fixture.root),true,2,0));
    check("Explicit disable advances revision without repopulating compatibility mask",matches(AppSettings.setBackgroundReplyPolicy(fixture.root,false),false,3,0));
  }

  static void writerOrdering()throws Exception {
    for(boolean enableFirst:new boolean[]{false,true}){
      ProfileCatalog fixture=setup();SQLiteDatabase db=fixture.db;AppSettings.initializeBackgroundReplyPolicy(fixture.root);
      CountDownLatch held=new CountDownLatch(1),release=new CountDownLatch(1),contender=new CountDownLatch(1);AtomicReference<Throwable> error=new AtomicReference<>();
      String first=enableFirst?"enable-first":"ack-first",second=enableFirst?"ack-second":"enable-second";
      db.beforeWrite=()->{if(Thread.currentThread().getName().equals(first)){held.countDown();await(release);}};
      db.beforeBegin=()->{if(Thread.currentThread().getName().equals(second))contender.countDown();};
      Runnable enable=()->{try{AppSettings.setBackgroundReplyPolicy(fixture.root,true);}catch(Throwable failure){error.compareAndSet(null,failure);}};
      Runnable ack=()->{try{AppSettings.backgroundReplyLegacyCommitted(fixture.root,7);}catch(Throwable failure){error.compareAndSet(null,failure);}};
      Thread owner=new Thread(enableFirst?enable:ack,first),waiting=new Thread(enableFirst?ack:enable,second);
      owner.start();await(held);waiting.start();await(contender);release.countDown();join(owner);join(waiting);db.beforeWrite=null;db.beforeBegin=null;
      check("Writer serialization preserves enable and acknowledged mask when "+(enableFirst?"enable":"compatibility")+" owns the transaction first",error.get()==null&&matches(AppSettings.readBackgroundReplyPolicy(fixture.root),true,2,127)&&db.balanced());
    }
  }

  static void failures(){
    ProfileCatalog fixture=setup();SQLiteDatabase db=fixture.db;db.failWriteKey=AppSettings.REPLY_POLICY_REVISION;
    check("A mid-initialization write failure rolls back every authority field",rejected(()->AppSettings.initializeBackgroundReplyPolicy(fixture.root))&&db.snapshot().isEmpty()&&db.balanced());
    BackgroundReplyPolicy.Snapshot missing=AppSettings.readBackgroundReplyPolicy(fixture.root);
    check("A failed initialization leaves reads disabled and unknown",!missing.known&&!missing.enabled);
    db.failWriteKey=null;check("Initialization can retry after a rolled back write",matches(AppSettings.initializeBackgroundReplyPolicy(fixture.root),false,1,255));
    Map<String,String> before=db.snapshot();db.failWriteKey=AppSettings.REPLY_POLICY_REVISION;
    check("A failed revision write rolls back the preceding enabled write",rejected(()->AppSettings.setBackgroundReplyPolicy(fixture.root,true))&&db.snapshot().equals(before)&&matches(AppSettings.readBackgroundReplyPolicy(fixture.root),false,1,255)&&db.balanced());
    db.failWriteKey=AppSettings.REPLY_POLICY_PENDING;
    check("Failed compatibility acknowledgment retains its retry bit",rejected(()->AppSettings.backgroundReplyLegacyCommitted(fixture.root,3))&&db.snapshot().equals(before)&&db.balanced());
    db.failWriteKey=null;db.failQuery=true;
    check("A transaction query failure propagates without committing partial state",rejected(()->AppSettings.setBackgroundReplyPolicy(fixture.root,true))&&db.snapshot().equals(before)&&db.balanced());
    db.failQuery=false;db.seed(valid(false,Long.MAX_VALUE,255));before=db.snapshot();
    check("Decision revision overflow is rejected without wrapping or changing authority",rejected(()->AppSettings.setBackgroundReplyPolicy(fixture.root,true))&&db.snapshot().equals(before)&&db.balanced());
  }

  static void malformed(){
    String[][] corrupt={{AppSettings.REPLY_POLICY_VERSION,"2"},{AppSettings.REPLY_POLICY_ENABLED,"TRUE"},{AppSettings.REPLY_POLICY_ENABLED,"1"},{AppSettings.REPLY_POLICY_REVISION,"0"},{AppSettings.REPLY_POLICY_REVISION,"-1"},{AppSettings.REPLY_POLICY_REVISION,"not-a-revision"},{AppSettings.REPLY_POLICY_REVISION,"9223372036854775808"},{AppSettings.REPLY_POLICY_PENDING,"-1"},{AppSettings.REPLY_POLICY_PENDING,"256"},{AppSettings.REPLY_POLICY_PENDING,"not-a-mask"}};
    for(String[] change:corrupt){ProfileCatalog fixture=setup();Map<String,String> values=valid(true,7,255);values.put(change[0],change[1]);fixture.db.seed(values);BackgroundReplyPolicy.Snapshot read=AppSettings.readBackgroundReplyPolicy(fixture.root),init=AppSettings.initializeBackgroundReplyPolicy(fixture.root);boolean blocked=rejected(()->AppSettings.setBackgroundReplyPolicy(fixture.root,true));AppSettings.backgroundReplyLegacyCommitted(fixture.root,2);check("Malformed "+change[0]+" value "+change[1]+" remains disabled without rewriting authority",!read.known&&!read.enabled&&!init.known&&!init.enabled&&blocked&&fixture.db.snapshot().equals(values)&&fixture.db.balanced());}
    for(String key:new String[]{AppSettings.REPLY_POLICY_ENABLED,AppSettings.REPLY_POLICY_REVISION,AppSettings.REPLY_POLICY_PENDING}){ProfileCatalog fixture=setup();Map<String,String> values=valid(true,7,255);values.remove(key);fixture.db.seed(values);BackgroundReplyPolicy.Snapshot read=AppSettings.readBackgroundReplyPolicy(fixture.root),init=AppSettings.initializeBackgroundReplyPolicy(fixture.root);check("Incomplete authority with missing "+key+" stays disabled and cannot masquerade as a new migration",!read.known&&!read.enabled&&!init.known&&!init.enabled&&rejected(()->AppSettings.setBackgroundReplyPolicy(fixture.root,true))&&fixture.db.snapshot().equals(values)&&fixture.db.balanced());}
    ProfileCatalog fixture=setup();Map<String,String> uninitialized=valid(true,99,0);uninitialized.remove(AppSettings.REPLY_POLICY_VERSION);fixture.db.seed(uninitialized);
    check("An absent migration marker establishes disabled revision one despite stray legacy fields",matches(AppSettings.initializeBackgroundReplyPolicy(fixture.root),false,1,255));
  }

  static void genericPut(){
    ProfileCatalog fixture=setup();AppSettings.initializeBackgroundReplyPolicy(fixture.root);Map<String,String> before=fixture.db.snapshot();
    for(String key:before.keySet())check("Generic settings writes cannot bypass policy key "+key,rejected(()->AppSettings.put(fixture.root,key,"true"))&&fixture.db.snapshot().equals(before));
    AppSettings.put(fixture.root,"ordinary-option","chosen");check("The policy guard preserves unrelated settings writes","chosen".equals(AppSettings.get(fixture.root,"ordinary-option","missing"))&&matches(AppSettings.readBackgroundReplyPolicy(fixture.root),false,1,255));
  }

  public static void main(String[] args)throws Exception {
    initialization();explicitDecisionAndCompatibility();writerOrdering();failures();malformed();genericPut();
    int passed=0;for(int i=0;i<checks.length();i++)if(checks.optJSONObject(i).optBoolean("pass"))passed++;
    System.out.println(J.obj("status",passed==checks.length()?"passed":"failed","passed",passed,"total",checks.length(),"checks",checks));
    if(passed!=checks.length())System.exit(1);
  }
}
