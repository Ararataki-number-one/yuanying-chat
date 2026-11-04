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
  static void save(WebTranscriptStore store,String url,CountedArray rows)throws Exception{store.offer(url,rows);store.flush();finish(store);}
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
      CountedArray same=entries(99);save(streaming,A,same);
      check("Unchanged snapshot produces no duplicate cache write",session.cache.writes==cacheWrites);
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
      WebTranscriptStore departed=store(A);CountedArray departing=entries(25);departed.offer(A,departing);departed.flush();departed.session.handler.runReady();barrier(departed);departed.current(B);departed.session.conversation=B;departed.session.handler.runReady();
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

      System.out.println(J.obj("status","passed","passed",checks.size(),"total",checks.size(),"baseline",baseline,"streamingSnapshots",100,"streamingCacheWrites",cacheWrites,"streamingSerializations",serialized,"transcriptPreferenceWrites",transcriptPuts,"transcriptPreferenceCharacters",transcriptCharacters,"conversationCursorWrites",cursorPuts,"burstOffers",40,"burstSerializations",burstSerializations,"burstCacheWrites",burst.session.cache.writes,"staleQueuedSerializations",staleSerializations,"mainHistorySerializations",CountedArray.mainSerializations.get(),"checks",new JSONArray(checks)));
    }finally{for(WebTranscriptStore store:stores){store.worker.shutdownNow();store.worker.awaitTermination(5,TimeUnit.SECONDS);}}
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
  final Map<String,String> values=new ConcurrentHashMap<>(),titles=new ConcurrentHashMap<>();int writes,reads,mainWrites,mainReads;boolean failNext;
  void saveSerializedMessages(String url,String serial,String title){if(failNext){failNext=false;throw new IllegalStateException("controlled cache failure");}writes++;if(Thread.currentThread()==TranscriptStorePerformanceHost.mainThread)mainWrites++;values.put(url,serial);titles.put(url,title);}
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
