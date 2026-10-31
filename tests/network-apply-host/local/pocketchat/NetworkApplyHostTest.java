package local.pocketchat;
import org.json.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicReference;
import java.util.function.BiFunction;
public final class NetworkApplyHostTest {
  static final JSONArray checks=new JSONArray();
  static void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));if(!pass)throw new AssertionError(name);}
  static void providerObservation()throws Exception{
    NetworkUiProvider provider=new NetworkUiProvider();ChatSession session=new ChatSession();ChatSession.current=session;
    provider.retry.defer("saved-before-observer","等待网页恢复",100);long initial=provider.retry.nextAttempt;
    provider.observeSession();
    check("Production synchronous first observer callback only records its baseline",provider.observedSession==session&&provider.retry.observed&&!provider.retry.event.isEmpty()&&provider.retry.nextAttempt==initial&&provider.main.queued.isEmpty());
    provider.observeSession();check("Repeated attachment retains one production observer",session.observers.size()==1&&provider.main.queued.isEmpty());
    for(int i=0;i<100;i++){session.state.put("draft","typed-"+i);provider.sessionChanged();}
    check("Full production observer ignores every-character draft changes",provider.retry.nextAttempt==initial&&provider.main.queued.isEmpty());
    session.state.put("composer",false);provider.sessionChanged();check("Unavailable composer observation retains the deferred deadline",provider.retry.nextAttempt==initial&&provider.main.queued.isEmpty());
    session.state.put("composer",true);provider.sessionChanged();check("Actual composer recovery posts exactly one pending wakeup",provider.retry.nextAttempt==0&&provider.main.queued.size()==1);
    provider.retry.defer("saved-before-observer","等待完整草稿",200);provider.main.queued.clear();long second=provider.retry.nextAttempt;
    for(int i=0;i<100;i++)provider.sessionChanged();check("A new failure on the recovered page retains its backoff",provider.retry.nextAttempt==second&&provider.main.queued.isEmpty());
    session.resourceBusy=true;session.resourceSequence++;provider.sessionChanged();session.resourceBusy=false;session.resourceSequence++;provider.sessionChanged();check("Actual busy-to-idle transition still wakes pending work",provider.retry.nextAttempt==0&&provider.main.queued.size()==1);
    provider.retry.defer("saved-before-observer","等待任务结束",300);provider.main.queued.clear();session.pending=new Object();session.state.put("busy",true);session.resourceBusy=true;session.resourceSequence++;provider.sessionChanged();session.resourceBusy=false;session.resourceSequence++;provider.sessionChanged();check("Fresh same-work idle wakes apply with stale pending and full reply state retained",provider.retry.nextAttempt==0&&provider.main.queued.size()==1&&session.pending!=null&&session.state.optBoolean("busy"));
    provider.retry.defer("saved-before-observer","等待新任务确认",400);provider.main.queued.clear();long unknownDeadline=provider.retry.nextAttempt;session.workGeneration++;session.resourceKnown=false;session.resourceSequence++;provider.sessionChanged();check("Unknown new submission never borrows a prior idle event",provider.retry.nextAttempt==unknownDeadline&&provider.main.queued.isEmpty());
    session.resourceKnown=true;session.resourceSequence++;provider.sessionChanged();check("A new bound current-work proof releases the deferred action",provider.retry.nextAttempt==0&&provider.main.queued.size()==1);
    provider.retry.clear();provider.main.queued.clear();session.state.put("composer",false);provider.sessionChanged();session.state.put("composer",true);provider.sessionChanged();check("Cancelled work cannot be woken by a later page recovery",provider.retry.key.isEmpty()&&provider.main.queued.isEmpty());
    ChatSession.current=null;provider.observeSession();check("Production detach removes the prior session observer",provider.observedSession==null&&session.observers.isEmpty());
  }
  static final class PausedMap extends ConcurrentHashMap<String,JSONObject> {
    final CountDownLatch observed=new CountDownLatch(1),resume=new CountDownLatch(1);volatile boolean barrier;String boundary="";
    void pause(String phase){if(!barrier)return;boundary=phase;observed.countDown();try{if(!resume.await(5,TimeUnit.SECONDS))throw new AssertionError("Retirement barrier timed out");}catch(InterruptedException error){throw new AssertionError(error);}}
    @Override public boolean containsKey(Object key){boolean found=super.containsKey(key);if("expired".equals(key))pause("after-containsKey");return found;}
    @Override public JSONObject computeIfPresent(String key,BiFunction<? super String,? super JSONObject,? extends JSONObject> operation){if("expired".equals(key))pause("before-atomic-update");return super.computeIfPresent(key,operation);}
  }
  static void concurrentRetirement()throws Exception{
    PausedMap rows=new PausedMap();NetworkUiProvider provider=new NetworkUiProvider(rows);android.os.SystemClock.now=400000;
    rows.put("expired",J.obj("done",true,"ok",true,"message","original","finishedAt",0));for(int i=0;i<127;i++)rows.put("retained-"+i,J.obj("done",true,"finishedAt",400000));rows.barrier=true;
    AtomicReference<Throwable> failed=new AtomicReference<>();Thread callback=new Thread(()->{try{provider.recordResult("expired",false,"late result");}catch(Throwable error){failed.set(error);}},"late-result-main-adapter");callback.start();
    try{if(!rows.observed.await(5,TimeUnit.SECONDS))throw new AssertionError("Production completion did not reach its map boundary");synchronized(rows){provider.pruneJobs();check("Concurrent prune retires only the expired external result",rows.size()==127&&rows.get("expired")==null);rows.put("new-admission",J.obj("done",false));}}finally{rows.resume.countDown();}
    callback.join(5000);if(callback.isAlive())throw new AssertionError("Late completion did not return");if(failed.get()!=null)throw new AssertionError(failed.get());
    check("Production late completion cannot resurrect a concurrently retired result",rows.get("expired")==null&&rows.size()==NetworkUiProvider.MAX_JOBS&&rows.containsKey("new-admission"));
    boolean retained=true;for(int i=0;i<127;i++)retained&=rows.get("retained-"+i).optBoolean("done")&&rows.get("retained-"+i).optLong("finishedAt")==400000;check("Concurrent late callback preserves retained results and new active work",retained&&!rows.get("new-admission").optBoolean("done"));
  }
  public static void main(String[] args)throws Exception{
    NetworkApplyRetry retry=new NetworkApplyRetry();long at=100;
    long[] delays={2000,4000,8000,16000,30000,30000};
    for(long delay:delays){retry.defer("saved-a","等待网页恢复",at);check("Retry holds before "+at+" deadline",!retry.due("saved-a",at+delay-1));check("Retry becomes due at "+at+" deadline",retry.due("saved-a",at+delay));at+=delay;}
    retry.defer("saved-a","等待网页恢复",at);check("Unavailable event does not admit a retry",!retry.observe("document-unavailable",false)&&!retry.due("saved-a",at));
    check("Real availability transition wakes pending work",retry.observe("document-ready",true)&&retry.due("saved-a",at));
    retry.defer("saved-a","等待网页恢复",at);long next=retry.nextAttempt;
    for(int i=0;i<100;i++)if(retry.observe("document-ready",true))throw new AssertionError("Repeated status reset retry");
    check("Repeated unchanged observations retain backoff",retry.nextAttempt==next&&!retry.due("saved-a",at));
    retry.observePage("same-document",true,true,false);retry.defer("saved-a","等待完整草稿",at);long composerDeadline=retry.nextAttempt;
    check("Missing composer keeps pending backoff",!retry.observePage("same-document",true,true,false)&&retry.nextAttempt==composerDeadline);
    check("Composer recovery wakes the same unchanged document",retry.observePage("same-document",true,true,true)&&retry.nextAttempt==0);
    retry.defer("saved-a","等待完整草稿",at);long draftDeadline=retry.nextAttempt;
    for(int i=0;i<100;i++)if(retry.observePage("same-document",true,true,true))throw new AssertionError("Text editing must not wake the retry");
    check("Draft text changes are not event data and preserve backoff",retry.nextAttempt==draftDeadline);
    check("Incomplete draft fallback remains bounded at thirty seconds",draftDeadline-at==30000);
    check("New candidate starts without old candidate backoff",retry.due("saved-b",at)&&retry.failures==0&&retry.reason.isEmpty());
    retry.defer("saved-b","等待回复和文件操作结束",at);retry.clear();check("Cancellation removes pending retry identity",retry.key.isEmpty()&&retry.reason.isEmpty()&&retry.nextAttempt==0);
    NetworkUiProvider provider=new NetworkUiProvider();android.os.SystemClock.now=1000;
    for(int i=0;i<40;i++){String id="external-"+i;provider.jobs.put(id,J.obj("done",false));provider.recordResult(id,true,"complete");}
    for(int i=0;i<1000;i++){provider.recordResult("internal:"+i,true,"retire");provider.recordResult("internal:"+i,false,"late");}
    check("Internal completion and late callbacks never accumulate",provider.jobs.size()==40&&provider.jobs.keySet().stream().noneMatch(id->id.startsWith("internal:")));
    provider.recordResult("unknown",true,"late");check("Unknown retired completion cannot create a record",!provider.jobs.containsKey("unknown"));
    String first=provider.jobs.get("external-0").toString();provider.recordResult("external-0",false,"late failure");check("External completion is immutable after publication",first.equals(provider.jobs.get("external-0").toString()));
    provider.jobs.put("running",J.obj("done",false));android.os.SystemClock.now=1000+NetworkUiProvider.JOB_RETENTION-1;provider.pruneJobs();
    check("Every external result remains readable through retention window",provider.jobs.size()==41);
    android.os.SystemClock.now++;provider.pruneJobs();check("Expired completions retire without deleting active work",provider.jobs.size()==1&&provider.jobs.containsKey("running"));
    provider.recordResult("external-0",true,"late after expiration");check("Expired callback cannot resurrect its result",provider.jobs.size()==1);
    check("Retention exceeds the actual 160 second bridge poll",NetworkUiProvider.JOB_RETENTION>160000);
    NetworkUiProvider receipts=new NetworkUiProvider();receipts.jobs.put("result",J.obj("done",false));JSONObject operation=J.obj("candidateId","candidate-a","savedRevision",7,"applicationState","pending");receipts.recordResult("result",true,"saved",operation);operation.put("candidateId","new-candidate");
    check("Operation outcome is frozen atomically with job completion",receipts.jobs.get("result").optBoolean("done")&&receipts.jobs.get("result").optJSONObject("operationResult").optString("candidateId").equals("candidate-a"));
    receipts.recordResult("result",false,"late",J.obj("candidateId","late"));check("Late completion cannot replace an operation outcome",receipts.jobs.get("result").optJSONObject("operationResult").optString("candidateId").equals("candidate-a"));
    receipts.jobs.remove("result");receipts.recordResult("result",true,"retired",operation);check("An outcome-bearing callback cannot resurrect a retired job",receipts.jobs.isEmpty());
    providerObservation();concurrentRetirement();
    System.out.println(J.obj("status","passed","passed",checks.length(),"checks",checks,"actualAndroidExecution",false,"actualProviderInvocation",false,"productionRetryClass",true,"productionJobMethodsExtractedVerbatim",true,"productionObserverMethodsExtractedVerbatim",true,"twoActualThreads",true));
  }
}
