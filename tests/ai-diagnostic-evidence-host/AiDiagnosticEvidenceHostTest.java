package local.pocketchat;

import java.util.Arrays;
import java.util.HashSet;
import java.util.Iterator;
import java.util.Set;
import org.json.JSONArray;
import org.json.JSONObject;

public final class AiDiagnosticEvidenceHostTest {
  private static int checks;
  private static long clock;
  private static void check(boolean ok,String message){checks++;if(!ok)throw new AssertionError(message);}
  private static JSONObject event(AiDiagnosticEvidence.Entry entry,int i){return entry.json().optJSONArray("events").optJSONObject(i);}
  private static AiDiagnosticEvidence.Entry capture(AiDiagnosticEvidence.Journal journal,Object tab){return journal.snapshot(tab,()->true);}
  private static void keys(JSONObject object,String... allowed){
    Set<String> expected=new HashSet<>(Arrays.asList(allowed));
    for(Iterator<String> i=object.keys();i.hasNext();)check(expected.remove(i.next()),"unexpected or duplicate key");
    check(expected.isEmpty(),"missing required key");
  }
  public static void main(String[] args)throws Exception {
    AiDiagnosticEvidence.Journal journal=new AiDiagnosticEvidence.Journal(()->clock);
    Object first=new Object(){public String toString(){return "https://private.invalid/chat?token=SECRET";}};
    Object second=new Object(),third=new Object();
    journal.register(first);journal.register(second);journal.register(third);
    AiDiagnosticEvidence.Entry initial=capture(journal,first);
    check(initial.current(),"initial snapshot current");
    check(initial.json().optJSONArray("events").length()==0,"no fabricated native observation");
    check(initial.label().equals("标签页 1"),"local anonymous label");
    AiDiagnosticEvidence subset=new AiDiagnosticEvidence(Arrays.asList(capture(journal,third)));
    check(subset.entries().get(0).json().optString("tabEvidenceId").equals("T3"),"selecting third tab does not renumber to T1");
    check(subset.entries().get(0).label().equals("标签页 3"),"label and transmitted evidence maintain mapping");
    try{subset.entries().clear();throw new AssertionError("mutable entry list");}catch(UnsupportedOperationException expected){checks++;}

    clock=100;journal.start(first);check(!initial.current(),"same native tab new load retires old snapshot even without URL");
    clock=125;journal.error(first,AiDiagnosticEvidence.Signal.DNS_FAILURE,37,5);
    AiDiagnosticEvidence.Entry dns=capture(journal,first);
    check(event(dns,1).optInt("code")==37&&event(dns,1).optInt("category")==5,"native code/category preserved");
    check(event(dns,1).optLong("elapsedMs")==25,"relative monotonic delta, not wall timestamp");
    check(event(dns,1).optString("signal").equals("DNS_FAILURE"),"DNS signal");
    check(dns.json().optString("navigationAttribution").equals("UNKNOWN"),"no invented request token attribution");
    check(dns.json().optString("scope").equals("TAB_CALLBACK_OBSERVATIONS"),"native observation scope explicit");
    clock=130;journal.stop(first,false);
    AiDiagnosticEvidence.Entry stopped=capture(journal,first);
    check(!dns.current(),"new terminal callback invalidates pre-confirmation evidence");
    check(event(stopped,1).optInt("code")==37,"generic stop does not replace structured DNS code");
    check(event(stopped,2).isNull("code")&&event(stopped,2).isNull("category"),"uncoded stop uses null instead of fabricated zero");
    JSONObject poisoned=stopped.json();poisoned.put("url","private");poisoned.optJSONArray("events").optJSONObject(1).put("code",999);
    check(!stopped.json().has("url")&&event(stopped,1).optInt("code")==37,"JSON getter returns fresh deep copy");

    clock=200;journal.location(first);check(!stopped.current(),"BFCache/location without page start invalidates snapshot");
    check(capture(journal,first).json().optJSONArray("events").length()==1,"location without pending load retires previous error window");
    clock=210;journal.start(first);
    clock=220;journal.error(first,AiDiagnosticEvidence.Signal.TIMEOUT,51,3);
    AiDiagnosticEvidence.Entry timeout=capture(journal,first);
    check(event(timeout,1).optString("signal").equals("TIMEOUT"),"timeout native code path");
    check(event(timeout,0).optString("id").equals("E5"),"event IDs stay stable across resets");
    journal.start(first);
    check(!timeout.current(),"same-URL reload cannot retain old selection");
    check(capture(journal,first).json().optJSONArray("events").length()==1,"new start does not inherit previous error");
    journal.error(first,AiDiagnosticEvidence.Signal.CERTIFICATE_REJECTED,50,2);
    check(event(capture(journal,first),1).optString("signal").equals("CERTIFICATE_REJECTED"),"certificate enum preserved");
    journal.error(first,AiDiagnosticEvidence.Signal.TLS_FAILURE,34,2);
    check(event(capture(journal,first),2).optString("signal").equals("TLS_FAILURE"),"TLS enum distinct from certificate failure");
    journal.error(first,AiDiagnosticEvidence.Signal.DNS_FAILURE,-1,2);
    check(event(capture(journal,first),3).isNull("code")&&event(capture(journal,first),3).optString("signal").equals("UNKNOWN"),"invalid code fails closed to unknown pair");
    journal.error(first,AiDiagnosticEvidence.Signal.DNS_FAILURE,37,null);
    check(event(capture(journal,first),4).isNull("code")&&event(capture(journal,first),4).isNull("category"),"partial native errors cannot masquerade as complete native errors");
    journal.error(first,AiDiagnosticEvidence.Signal.CONTENT_KILL,999,1);
    check(event(capture(journal,first),5).optString("signal").equals("UNKNOWN"),"load-error mapper cannot claim unrelated process event");
    journal.contentStopped(first,false);journal.stop(first,false);
    check(event(capture(journal,first),6).optString("signal").equals("CONTENT_CRASH"),"generic stop preserves crash observation");
    journal.contentStopped(first,true);
    check(event(capture(journal,first),8).optString("signal").equals("CONTENT_KILL"),"kill is distinct from crash; no OOM diagnosis");
    AiDiagnosticEvidence.Entry beforeReopen=capture(journal,first);journal.reset(first);
    check(!beforeReopen.current()&&capture(journal,first).json().optJSONArray("events").length()==0,"native reopen clears stale failure and selection");

    AiDiagnosticEvidence.Entry firstQuiet=capture(journal,first);
    journal.start(second);journal.error(second,AiDiagnosticEvidence.Signal.UNKNOWN,1234,7);
    check(firstQuiet.current(),"background tab events do not contaminate first tab journal");
    check(capture(journal,second).json().optString("tabEvidenceId").equals("T2"),"background callback belongs to stable second tab");
    check(capture(journal,first).json().optJSONArray("events").length()==0,"no background error copied to current tab");
    boolean[] ownerCurrent={true};AiDiagnosticEvidence.Entry fenced=journal.snapshot(second,()->ownerCurrent[0]);ownerCurrent[0]=false;
    check(!fenced.current(),"environment/host fence revokes evidence");
    AiDiagnosticEvidence.Entry closed=capture(journal,second);journal.forget(second);
    check(!closed.current()&&capture(journal,second)==null,"closed tab revoked");
    journal.error(second,AiDiagnosticEvidence.Signal.DNS_FAILURE,37,5);
    check(capture(journal,second)==null,"late callback cannot resurrect closed tab");
    Object replacement=new Object();journal.register(replacement);
    check(capture(journal,replacement).json().optString("tabEvidenceId").equals("T4"),"closed anonymous IDs are not reused");

    AiDiagnosticEvidence.Entry beforeReplace=capture(journal,first);
    journal.start(first);journal.error(first,AiDiagnosticEvidence.Signal.TIMEOUT,51,3);
    AiDiagnosticEvidence.Entry failedBeforeReplace=capture(journal,first);
    Object reopened=new Object();journal.register(reopened);journal.replace(first,reopened);
    check(!beforeReplace.current()&&!failedBeforeReplace.current(),"replaced native session revokes old entry");
    check(capture(journal,reopened).json().optString("tabEvidenceId").equals("T1"),"logical tab anonymous number survives native session replacement");
    check(capture(journal,reopened).json().optJSONArray("events").length()==0,"replacement cannot inherit former session error");
    journal.start(reopened);check(!event(capture(journal,reopened),0).optString("id").equals("E1"),"replacement does not reuse prior per-tab evidence IDs");

    clock=1000;journal.start(third);
    for(int i=1;i<=30;i++){clock+=10;journal.error(third,AiDiagnosticEvidence.Signal.UNKNOWN,i,0);}
    AiDiagnosticEvidence.Entry bounded=capture(journal,third);
    check(bounded.json().optJSONArray("events").length()==16,"bounded 16 native events per tab");
    check(event(bounded,0).optString("id").equals("E16"),"bounded window retains original evidence identifiers");
    clock+=7200000;journal.stop(third,false);
    check(event(capture(journal,third),15).optLong("elapsedMs")==3600000,"elapsed duration capped");
    journal.reset(third);clock=50;journal.error(third,AiDiagnosticEvidence.Signal.UNKNOWN,99,3);
    check(event(capture(journal,third),0).optLong("elapsedMs")==0,"first unpaired error starts relative window at zero");
    clock=40;journal.stop(third,true);
    check(event(capture(journal,third),1).optLong("elapsedMs")==0,"monotonic-clock regression cannot expose negative duration");
    JSONObject projection=capture(journal,third).json();
    keys(projection,"schema","engine","tabEvidenceId","scope","navigationAttribution","events");
    JSONArray values=projection.optJSONArray("events");for(int i=0;i<values.length();i++)keys(values.optJSONObject(i),"id","kind","signal","code","category","elapsedMs");
    check(!projection.toString().contains("private")&&!projection.toString().contains("SECRET"),"opaque native key/string never serialized");
    AiDiagnosticEvidence.Entry retired=capture(journal,third);journal.clear();check(!retired.current(),"destroy revokes all evidence");
    if(args.length==1){
      AiDiagnosticEvidence.Journal wire=new AiDiagnosticEvidence.Journal(()->clock);
      Object one=new Object(),two=new Object(),three=new Object();wire.register(one);wire.register(two);wire.register(three);
      clock=0;wire.start(one);clock=30;wire.error(one,AiDiagnosticEvidence.Signal.DNS_FAILURE,37,5);wire.stop(one,false);
      clock=50;wire.start(three);clock=65;wire.error(three,AiDiagnosticEvidence.Signal.CERTIFICATE_REJECTED,50,2);wire.stop(three,false);
      JSONObject body=J.obj("version",1,"provider","openai","evidence",J.arr(capture(wire,one).json(),capture(wire,three).json()));
      java.nio.file.Path file=java.nio.file.Path.of(args[0]);java.nio.file.Files.createDirectories(file.toAbsolutePath().getParent());
      java.nio.file.Files.writeString(file,body.toString()+"\n");
    }
    System.out.println("{\"status\":\"passed\",\"checks\":"+checks+",\"actualGeckoExecution\":false,\"actualApiExecution\":false}");
  }
}
