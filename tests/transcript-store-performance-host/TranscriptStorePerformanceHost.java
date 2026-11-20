package local.pocketchat;

import android.net.Uri;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import org.json.*;

/** Entire production store runs with its real worker; only main, cache and preferences are adapters. */
public final class TranscriptStorePerformanceHost {
  static final boolean baseline=Boolean.getBoolean("baseline");
  static final Thread mainThread=Thread.currentThread();
  static final List<String> checks=new ArrayList<>();
  static final List<WebTranscriptStore> stores=new ArrayList<>();
  static final String A="https://chatgpt.com/c/host-first",B="https://chatgpt.com/c/host-second";
  static void check(String name,boolean value){if(!value)throw new AssertionError(name);checks.add(name);}
  static WebTranscriptStore store(String url){ChatSession session=new ChatSession();session.conversation=url;WebTranscriptStore store=new WebTranscriptStore(session);stores.add(store);return store;}
  static String repeat(String text,int count){StringBuilder out=new StringBuilder();for(int i=0;i<count;i++)out.append(text);return out.toString();}
  static CountedArray entries(int version)throws JSONException{
    CountedArray rows=new CountedArray();
    for(int i=0;i<64;i++)rows.put(J.obj("id","message-"+i,"role",i%2==0?"user":"assistant","text",i==0?"  Prompt \n version"+version+" 😀  ":"Version "+version+" row "+i+"\n"+repeat("quoted \"text\" \\ code\n汉字 😀 ",24),"attachments",new JSONArray().put(J.obj("name","file-"+i+".txt","size",i+1))));
    return rows;
  }
  static String expected(CountedArray rows){return rows.plainSerial();}
  static void barrier(WebTranscriptStore store)throws Exception{store.worker.submit(()->{}).get(5,TimeUnit.SECONDS);}
  static void ready(WebTranscriptStore store)throws Exception{store.session.handler.runReady();barrier(store);store.session.handler.runReady();}
  static void finish(WebTranscriptStore store)throws Exception{
    for(int step=0;step<30;step++){
      ready(store);
      if(!store.writing&&!store.scheduled&&store.latest==null&&store.session.handler.empty())return;
      store.session.handler.advance();
    }
    throw new AssertionError("Controlled store did not become idle");
  }
  static void save(WebTranscriptStore store,String url,JSONArray rows)throws Exception{store.offer(url,rows);store.flush();finish(store);}
  public static void main(String[] args)throws Exception{
    try{
      WebTranscriptStore streaming=store(A);ChatSession session=streaming.session;session.prefs.values.put("transcript","retained-legacy-value");
      String last="";int serialized=0;
      for(int version=0;version<100;version++){
        CountedArray rows=entries(version);last=expected(rows);save(streaming,A,rows);serialized+=rows.serializations.get();
        check("Streaming snapshot "+version+" preserves exact cache body",last.equals(session.cache.values.get(A)));
      }
      check("100 changed snapshots retain100 cache writes",session.cache.writes==100);
      check("100 changed snapshots serialize100 immutable histories",serialized==100);
      check("Transcript preference assignment reduction",session.prefs.transcriptPuts==(baseline?100:0));
      check("Conversation cursor assignment reduction",session.prefs.conversationPuts==(baseline?100:1));
      check("Latest conversation cursor is preserved",A.equals(session.prefs.getString("conversation","")));
      check("Existing legacy transcript is retained without migration",baseline?last.equals(session.prefs.getString("transcript","")):session.prefs.getString("transcript","").equals("retained-legacy-value"));
      check("Titles retain original whitespace normalization and Unicode",session.cache.titles.get(A).equals("Prompt version99 😀"));
      check("Cache writes happen off main",session.cache.mainWrites==0);
      check("Preference edits happen on main delivery",session.prefs.workerApplies==0);
      int transcriptPuts=session.prefs.transcriptPuts,cursorPuts=session.prefs.conversationPuts,cacheWrites=session.cache.writes;
      long transcriptCharacters=session.prefs.transcriptCharacters;
      int strictReads=session.cache.strictReads;
      CountedArray same=entries(99);save(streaming,A,same);
      check("Unchanged snapshot produces no duplicate cache write",session.cache.writes==cacheWrites);
      check("Unchanged snapshot produces no duplicate durable read",session.cache.strictReads==strictReads);
      check("Unchanged snapshot produces no preference write",session.prefs.transcriptPuts==transcriptPuts&&session.prefs.conversationPuts==cursorPuts);
      check("Unchanged snapshot still serializes for existing equality check",same.serializations.get()==1);

      WebTranscriptStore burst=store(A);List<CountedArray> burstRows=new ArrayList<>();
      for(int version=0;version<40;version++){CountedArray rows=entries(version);burstRows.add(rows);burst.offer(A,rows);}
      check("40 offers queue one main drain",burst.session.handler.size()==1&&burst.scheduled);
      burst.flush();finish(burst);int burstSerializations=0;for(CountedArray rows:burstRows)burstSerializations+=rows.serializations.get();
      check("40 offers serialize only final snapshot",burstSerializations==1&&burstRows.get(39).serializations.get()==1);
      check("40 offers write only final history",burst.session.cache.writes==1&&expected(burstRows.get(39)).equals(burst.session.cache.values.get(A)));
      check("40 offer drain leaves no queued snapshots",!burst.writing&&!burst.scheduled&&burst.latest==null&&burst.queued.isEmpty());

      WebTranscriptStore stale=store(A);Gate gate=new Gate(stale);CountedArray old=entries(1),newest=entries(2);
      stale.offer(A,old);stale.flush();stale.session.handler.runReady();
      check("Stale test has writer queued behind controlled worker gate",stale.writing&&old.serializations.get()==0);
      stale.nativeSnapshot(A);stale.offer(A,newest);gate.release();barrier(stale);stale.session.handler.runReady();
      int staleSerializations=old.serializations.get();
      check("Invalidated queued history serialization reduction",staleSerializations==(baseline?1:0));
      check("Invalidated queued history never reaches cache or prefs",stale.session.cache.writes==0&&stale.session.prefs.applies==0);
      finish(stale);
      check("Newest snapshot survives stale worker cancellation",stale.session.cache.writes==1&&expected(newest).equals(stale.session.cache.values.get(A))&&newest.serializations.get()==1);
      check("Stale worker releases writer for trailing snapshot",!stale.writing&&!stale.scheduled&&stale.latest==null);

      WebTranscriptStore nativeOnly=store(A);Gate nativeGate=new Gate(nativeOnly);CountedArray cancelled=entries(3);
      nativeOnly.offer(A,cancelled);nativeOnly.flush();nativeOnly.session.handler.runReady();nativeOnly.nativeSnapshot(A);nativeGate.release();finish(nativeOnly);
      check("Native-only cancellation performs no overwrite",nativeOnly.session.cache.writes==0&&nativeOnly.session.prefs.applies==0&&!nativeOnly.writing);
      check("Native-only cancellation skips stale serialization",cancelled.serializations.get()==(baseline?1:0));

      WebTranscriptStore two=store(B);CountedArray first=entries(10),second=entries(20);two.offer(A,first);two.offer(B,second);two.flush();finish(two);
      check("Two conversations each preserve their own exact history",two.session.cache.writes==2&&expected(first).equals(two.session.cache.values.get(A))&&expected(second).equals(two.session.cache.values.get(B)));
      check("Only current conversation updates cursor",two.session.prefs.conversationPuts==1&&two.session.prefs.cursorValues.equals(Collections.singletonList(B)));
      check("Only current conversation can write legacy transcript",two.session.prefs.transcriptPuts==(baseline?1:0));
      WebTranscriptStore delivered=store(A);Gate deliveryGate=new Gate(delivered);CountedArray delivering=entries(24);delivered.offer(A,delivering);delivered.flush();delivered.session.handler.runReady();
      check("Early-delivery writer waits behind controlled worker gate",delivered.writing&&delivering.serializations.get()==0&&delivered.session.cache.writes==0&&delivered.session.prefs.applies==0);
      deliveryGate.release();barrier(delivered);
      check("Early preference delivery waits for explicit main dispatch",delivered.writing&&delivered.session.cache.writes==1&&delivered.session.prefs.applies==0&&delivered.session.handler.size()==2);
      delivered.session.handler.runReady();
      check("Delivery before conversation switch may persist the current cursor",delivered.session.prefs.applies==1&&delivered.session.prefs.cursorValues.equals(Collections.singletonList(A))&&!delivered.writing);
      delivered.current(B);delivered.session.conversation=B;delivered.session.handler.runReady();
      check("A later conversation switch does not rewrite an already delivered cursor",delivered.session.prefs.applies==1&&delivered.session.prefs.cursorValues.equals(Collections.singletonList(A)));

      WebTranscriptStore departed=store(A);Gate departureGate=new Gate(departed);CountedArray departing=entries(25);departed.offer(A,departing);departed.flush();departed.session.handler.runReady();
      check("Late-delivery writer waits behind controlled worker gate",departed.writing&&departing.serializations.get()==0&&departed.session.cache.writes==0&&departed.session.prefs.applies==0);
      departureGate.release();barrier(departed);
      check("Late preference callback is pending before conversation switch",departed.writing&&departed.session.cache.writes==1&&departed.session.prefs.applies==0&&departed.session.handler.size()==2);
      departed.current(B);departed.session.conversation=B;departed.session.handler.runReady();
      check("Late preference delivery respects conversation switch",departed.session.cache.writes==1&&departed.session.prefs.applies==0&&!departed.writing);

      session.entries=new JSONArray();session.offline=true;int previousReads=session.cache.reads;Gate offlineGate=new Gate(streaming);streaming.loadIfNeeded();
      check("Offline load does not synchronously read cache",session.cache.reads==previousReads&&session.entries.length()==0);
      offlineGate.release();barrier(streaming);session.handler.runReady();
      check("Offline load publishes exact cached content",last.equals(session.entries.toString())&&session.showingCache&&session.changes==1);
      check("Offline cache read happens off main",session.cache.reads==previousReads+1&&session.cache.mainReads==0);
      streaming.loadIfNeeded();barrier(streaming);session.handler.runReady();check("Existing in-memory entries suppress cache reload",session.cache.reads==previousReads+1);
      session.entries=new JSONArray();session.conversation="https://chatgpt.com/";streaming.loadIfNeeded();barrier(streaming);session.handler.runReady();check("Non-conversation URL suppresses cache load",session.cache.reads==previousReads+1);
      session.conversation=A;Gate loadGate=new Gate(streaming);streaming.loadIfNeeded();session.conversation=B;loadGate.release();barrier(streaming);session.handler.runReady();
      check("Late cached content cannot cross conversations",session.entries.length()==0&&session.changes==1);
      session.conversation=A;Gate replacementGate=new Gate(streaming);streaming.loadIfNeeded();JSONArray replacement=new JSONArray().put(J.obj("id","new-live","text","new website content"));session.entries=replacement;replacementGate.release();barrier(streaming);session.handler.runReady();
      check("Late cache read cannot replace newer live entries",session.entries==replacement&&session.changes==1);

      WebTranscriptStore failed=store(A);failed.session.cache.failNext=true;CountedArray retry=entries(31);save(failed,A,retry);
      check("Cache save failure is delivered as existing recovery status",failed.session.status.equals("本地记录保存失败，请保留原网页核对")&&failed.session.statusWrites==1);
      check("Save failure releases writer and does not advance saved signature",!failed.writing&&!failed.scheduled&&failed.savedSerial.isEmpty()&&failed.session.cache.writes==0&&failed.session.prefs.applies==0);
      save(failed,A,retry);check("Same snapshot can retry after failed save",failed.session.cache.writes==1&&expected(retry).equals(failed.session.cache.values.get(A))&&!failed.writing);
      WebTranscriptStore broken=store(A);CountedArray bad=entries(40);bad.failNext=true;save(broken,A,bad);CountedArray recovered=entries(41);save(broken,A,recovered);
      check("Serialization failure cannot strand later valid snapshot",broken.session.statusWrites==1&&broken.session.cache.writes==1&&expected(recovered).equals(broken.session.cache.values.get(A))&&!broken.writing);
      check("All counted full-history serializations happen off main",CountedArray.mainSerializations.get()==0);
      if(!baseline) verifyOfflineHistory();

      System.out.println(J.obj("status","passed","passed",checks.size(),"total",checks.size(),"baseline",baseline,"streamingSnapshots",100,"streamingCacheWrites",cacheWrites,"streamingSerializations",serialized,"transcriptPreferenceWrites",transcriptPuts,"transcriptPreferenceCharacters",transcriptCharacters,"conversationCursorWrites",cursorPuts,"burstOffers",40,"burstSerializations",burstSerializations,"burstCacheWrites",burst.session.cache.writes,"staleQueuedSerializations",staleSerializations,"mainHistorySerializations",CountedArray.mainSerializations.get(),"checks",new JSONArray(checks)));
    }finally{for(WebTranscriptStore store:stores){store.worker.shutdownNow();store.worker.awaitTermination(5,TimeUnit.SECONDS);}}
  }
  static JSONObject row(String id,String role,String text){return J.obj("id",id,"role",role,"text",text);}
  static JSONArray history(JSONObject... rows){return new JSONArray(Arrays.asList(rows));}
  static JSONArray mounted(WebTranscriptMirror mirror,JSONArray previous,String document,int revision,JSONObject... rows){
    JSONArray order=new JSONArray();for(JSONObject row:rows)order.put(row.optString("id"));
    JSONObject delta=J.obj("ok",true,"changed",true,"reset",revision==1,"url",A,"documentId",document,
        "revision",revision,"changes",history(rows),"order",order);
    return mirror.accept(delta,previous,A);
  }
  static boolean hasHistory(WebTranscriptStore store,JSONArray rows){return rows.toString().equals(store.session.cache.values.get(A));}
  static void verifyOfflineHistory()throws Exception{
    JSONObject u1=row("id:u1","user","Question one"),a1=row("id:a1","assistant","The long first answer"),
        u2=row("id:u2","user","Question two"),a2=row("id:a2","assistant","The second answer"),
        u3=row("id:u3","user","A new question"),a3=row("id:a3","assistant","A new answer");
    JSONObject a1Edit=row("id:a1","assistant","Short edit"),a2Edit=row("id:a2","assistant","Another legitimate edit");
    JSONArray complete=history(u1,a1,u2,a2),edited=history(u1,a1Edit,u2,a2);
    WebTranscriptStore current=store(A);
    WebTranscriptMirror mirror=new WebTranscriptMirror();
    save(current,A,mounted(mirror,new JSONArray(),"same-document",1,u1,a1,u2,a2));
    save(current,A,mounted(mirror,complete,"same-document",2,u1,a1));
    check("A virtualized prefix never truncates the existing offline copy",hasHistory(current,complete)&&current.session.cache.writes==1);
    int heldReads=current.session.cache.strictReads;
    save(current,A,history(u1,a1));
    check("An unchanged held observation does not reread or rewrite the durable copy",current.session.cache.strictReads==heldReads&&current.session.cache.writes==1);
    save(current,A,mounted(mirror,complete,"same-document",3,a1,u2));
    check("A virtualized middle window never drops the saved suffix",hasHistory(current,complete)&&current.session.cache.writes==1);
    save(current,A,history(u1,a1Edit,u3,a3));
    check("An edited prefix with novel IDs cannot attach to a missing saved tail",hasHistory(current,complete)&&current.session.cache.writes==1);
    save(current,A,history(u2,u3,a2,a3));
    check("An insertion inside a partial overlap does not establish a tail match",hasHistory(current,complete)&&current.session.cache.writes==1);
    save(current,A,history(a2,u2,u3));
    check("Reordered shared identities preserve the existing copy",hasHistory(current,complete)&&current.session.cache.writes==1);
    save(current,A,history(u3,a3));
    check("A non-overlapping observation preserves the existing copy",hasHistory(current,complete)&&current.session.cache.writes==1);
    save(current,A,history(u2,a2,a2,a3));
    check("Duplicate identities cannot authorize a tail match",hasHistory(current,complete)&&current.session.cache.writes==1);
    save(current,A,history(u2,row("id:a2","user","A role change cannot identify an edit"),a3));
    check("Conflicting roles cannot authorize a tail match",hasHistory(current,complete)&&current.session.cache.writes==1);
    save(current,A,mounted(mirror,complete,"same-document",4,u1,a1Edit,u2,a2));
    check("A shorter edit with complete ordered coverage is saved exactly",hasHistory(current,edited)&&current.session.cache.writes==2);

    WebTranscriptStore freshProcess=store(A);
    freshProcess.session.cache.values.put(A,complete.toString());
    save(freshProcess,A,mounted(new WebTranscriptMirror(),new JSONArray(),"cold-start",1,u2,a2));
    check("A cold-start observation preserves the saved prefix without requiring an earlier UI read",hasHistory(freshProcess,complete)&&freshProcess.session.cache.writes==0&&freshProcess.session.cache.reads==0);

    WebTranscriptStore cold=store(A);
    cold.session.cache.values.put(A,complete.toString());
    Gate coldRead=new Gate(cold);
    try{
      cold.loadIfNeeded();
      cold.session.entries=mounted(new WebTranscriptMirror(),new JSONArray(),"reload",1,u2,a2);
      cold.offer(A,cold.session.entries);cold.flush();cold.session.handler.runReady();
    }finally{coldRead.release();}
    finish(cold);
    check("First live rows win the prior UI read race without truncating durable history",cold.session.entries.length()==2&&cold.session.changes==0&&hasHistory(cold,complete)&&cold.session.cache.writes==0);
    save(cold,A,history(u2,a2Edit,u3,a3));
    JSONArray appended=history(u1,a1,u2,a2Edit,u3,a3);
    check("A contiguous stable tail retains the old prefix and appends genuine new messages",hasHistory(cold,appended)&&cold.session.cache.writes==1);
    check("The durable safety reads happen off the main thread",cold.session.cache.strictMainReads==0&&cold.session.cache.strictReads>=2);

    WebTranscriptStore weak=store(A);
    JSONObject fallback=row("turn:conversation-turn-2","assistant","A positional ID");
    JSONArray weakHistory=history(u1,fallback);
    save(weak,A,weakHistory);save(weak,A,history(fallback,u3,a3));
    check("A positional identity is not a durable tail anchor",hasHistory(weak,weakHistory)&&weak.session.cache.writes==1);
    save(weak,A,history(u1,fallback,u3,a3));
    check("Full ordered coverage permits new rows beside an old positional ID",hasHistory(weak,history(u1,fallback,u3,a3))&&weak.session.cache.writes==2);

    WebTranscriptStore storageFailure=store(A);
    storageFailure.session.cache.values.put(A,complete.toString());
    storageFailure.session.cache.failNextRead=true;
    save(storageFailure,A,edited);
    check("A failed durable read preserves the old bytes and allows an exact retry",hasHistory(storageFailure,complete)&&storageFailure.session.cache.writes==0&&storageFailure.savedSerial.isEmpty()&&storageFailure.session.statusWrites==1);
    save(storageFailure,A,edited);
    check("The unchanged input can succeed after storage recovery",hasHistory(storageFailure,edited)&&storageFailure.session.cache.writes==1);
    WebTranscriptStore corrupt=store(A);
    corrupt.session.cache.values.put(A,"[incomplete storage record");
    save(corrupt,A,history(u2,a2));
    check("Unreadable durable bytes are preserved rather than treated as a new row",corrupt.session.cache.writes==0&&corrupt.session.cache.values.get(A).equals("[incomplete storage record")&&corrupt.session.statusWrites==1);

    WebTranscriptStore concurrent=store(A);
    concurrent.session.cache.values.put(A,complete.toString());
    CountDownLatch entered=new CountDownLatch(1),allowRead=new CountDownLatch(1);
    concurrent.session.cache.beforeStrictRead=()->{
      entered.countDown();
      try{if(!allowRead.await(5,TimeUnit.SECONDS))throw new AssertionError("Durable read gate timed out");}
      catch(InterruptedException interrupted){Thread.currentThread().interrupt();throw new AssertionError(interrupted);}
    };
    concurrent.offer(A,edited);concurrent.flush();concurrent.session.handler.runReady();
    CompletableFuture<Void> nativeSave;
    try{
      if(!entered.await(5,TimeUnit.SECONDS))throw new AssertionError("Durable read did not enter");
      concurrent.nativeSnapshot(A);
      nativeSave=CompletableFuture.runAsync(()->concurrent.session.cache.saveSerializedMessages(A,appended.toString(),"new native copy"));
    }finally{allowRead.countDown();}
    finish(concurrent);nativeSave.get(5,TimeUnit.SECONDS);
    check("A native save retiring an in-flight durable read is never overwritten by the stale writer",hasHistory(concurrent,appended)&&concurrent.session.cache.writes==1);
  }
  static final class Gate {
    final CountDownLatch entered=new CountDownLatch(1),allow=new CountDownLatch(1);
    Gate(WebTranscriptStore store)throws Exception{store.worker.execute(()->{entered.countDown();try{if(!allow.await(5,TimeUnit.SECONDS))throw new AssertionError("Worker gate timed out");}catch(InterruptedException interrupted){Thread.currentThread().interrupt();}});if(!entered.await(5,TimeUnit.SECONDS))throw new AssertionError("Worker gate did not start");}
    void release(){allow.countDown();}
  }
}

final class CountedArray extends JSONArray {
  static final AtomicInteger mainSerializations=new AtomicInteger();final AtomicInteger serializations=new AtomicInteger();boolean failNext;
  @Override public String toString(){serializations.incrementAndGet();if(Thread.currentThread()==TranscriptStorePerformanceHost.mainThread)mainSerializations.incrementAndGet();if(failNext){failNext=false;throw new IllegalStateException("controlled serialization failure");}return super.toString();}
  String plainSerial(){return super.toString();}
}
final class ChatSession {
  final Handler handler=new Handler();final Cache cache=new Cache();final Preferences prefs=new Preferences();String conversation="",status="";JSONArray entries=new JSONArray();boolean navigating,navigationFailed,offline,showingCache;int changes,statusWrites;
  void changed(){changes++;}void setStatus(String text){status=text;statusWrites++;}
}
final class Handler {
  static final class Task {final Runnable runnable;final long due,sequence;Task(Runnable runnable,long due,long sequence){this.runnable=runnable;this.due=due;this.sequence=sequence;}}
  final PriorityQueue<Task> tasks=new PriorityQueue<>((a,b)->a.due!=b.due?Long.compare(a.due,b.due):Long.compare(a.sequence,b.sequence));long now,sequence;
  synchronized void post(Runnable task){postDelayed(task,0);}synchronized void postDelayed(Runnable task,long delay){tasks.add(new Task(task,now+delay,sequence++));}
  synchronized void removeCallbacks(Runnable task){tasks.removeIf(value->value.runnable==task);}
  void runReady(){for(int count=0;count<10000;count++){Task task;synchronized(this){if(tasks.isEmpty()||tasks.peek().due>now)return;task=tasks.remove();}task.runnable.run();}throw new AssertionError("Main callback flood");}
  synchronized void advance(){if(!tasks.isEmpty())now=Math.max(now,tasks.peek().due);}synchronized boolean empty(){return tasks.isEmpty();}synchronized int size(){return tasks.size();}
}
final class Cache {
  final Map<String,String> values=new ConcurrentHashMap<>(),titles=new ConcurrentHashMap<>();int writes,reads,mainWrites,mainReads,strictReads,strictMainReads;
  boolean failNext,failNextRead;
  Runnable beforeStrictRead;
  String readSerializedMessages(String url){
    strictReads++;if(Thread.currentThread()==TranscriptStorePerformanceHost.mainThread)strictMainReads++;
    Runnable hook=beforeStrictRead;beforeStrictRead=null;if(hook!=null)hook.run();
    if(failNextRead){failNextRead=false;throw new IllegalStateException("controlled cache read failure");}
    return values.get(url);
  }
  synchronized void saveSerializedMessages(String url,String serial,String title){if(failNext){failNext=false;throw new IllegalStateException("controlled cache failure");}writes++;if(Thread.currentThread()==TranscriptStorePerformanceHost.mainThread)mainWrites++;values.put(url,serial);titles.put(url,title);}
  JSONArray messages(String url){reads++;if(Thread.currentThread()==TranscriptStorePerformanceHost.mainThread)mainReads++;try{return new JSONArray(values.getOrDefault(url,"[]"));}catch(JSONException invalid){throw new IllegalStateException(invalid);}}
}
final class Preferences {
  final Map<String,String> values=new HashMap<>();final List<String> cursorValues=new ArrayList<>();int applies,transcriptPuts,conversationPuts,workerApplies;long transcriptCharacters;
  String getString(String key,String fallback){return values.getOrDefault(key,fallback);}Editor edit(){return new Editor();}
  final class Editor {
    final Map<String,String> pending=new LinkedHashMap<>();
    Editor putString(String key,String value){if(key.equals("transcript")){transcriptPuts++;transcriptCharacters+=value.length();}if(key.equals("conversation")){conversationPuts++;cursorValues.add(value);}pending.put(key,value);return this;}
    void apply(){applies++;if(Thread.currentThread()!=TranscriptStorePerformanceHost.mainThread)workerApplies++;values.putAll(pending);}
  }
}
final class MainActivity {/* CHAT_URL_METHOD */}
final class WebReplyObserver {/* OBSERVER_METHODS */}
