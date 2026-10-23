package local.pocketchat;
import org.json.*;
public final class NetworkApplyHostTest {
  static final JSONArray checks=new JSONArray();
  static void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));if(!pass)throw new AssertionError(name);}
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
    System.out.println(J.obj("status","passed","passed",checks.length(),"checks",checks,"actualAndroidExecution",false,"actualProviderInvocation",false,"productionRetryClass",true,"productionJobMethodsExtractedVerbatim",true));
  }
}
