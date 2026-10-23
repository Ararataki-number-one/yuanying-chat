package local.pocketchat;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

/** Executes the unmodified production journal; no Android/core claims. */
public final class NetworkDiagnosticsHostTest {
  static int checks;static final List<String> names=new ArrayList<>();
  static final String ENV="11111111-1111-4111-8111-111111111111",NEXT="22222222-2222-4222-8222-222222222222";
  static final String CORE="33333333-3333-4333-8333-333333333333",OTHER="44444444-4444-4444-8444-444444444444";
  static final String SECRET="https://user:private-password@example.invalid/?token=subscription-token\n\u001b[31m raw-configuration";
  static void check(String name,boolean yes){if(!yes)throw new AssertionError(name);checks++;names.add(name);}
  static void flush()throws Exception{check("bounded writer completes",NetworkDiagnostics.flushForTest(10000));}
  static NetworkDiagnostics logger(File directory,String identity,long generation){return NetworkDiagnostics.forRoot(directory,0,NetworkDiagnostics.Source.CONTROL,identity,generation);}
  static void event(NetworkDiagnostics d,NetworkDiagnostics.Event e,String generation,long value){d.record(e,generation,NetworkDiagnostics.Reason.REQUESTED,NetworkDiagnostics.Stage.CORE,value);}
  static String summary(File root,String identity,long generation){return NetworkDiagnostics.readSummary(root,0,identity,generation);}
  static String file(File root)throws Exception{return new String(Files.readAllBytes(new File(root,"control.events").toPath()),StandardCharsets.UTF_8);}
  public static void main(String[] args)throws Exception{
    File root=new File(args[0]);root.mkdirs();
    if(args.length>1&&args[1].equals("restart")){
      String before=summary(new File(root,"restart"),ENV,4);check("fresh JVM reads prior persisted generation",before.contains("CORE_START")&&before.contains(CORE));
      NetworkDiagnostics n=logger(new File(root,"restart"),ENV,4);event(n,NetworkDiagnostics.Event.CORE_EXIT,CORE,137);flush();
      String after=summary(new File(root,"restart"),ENV,4);check("fresh JVM appends without replacing prior events",after.contains("CORE_START")&&after.contains("CORE_EXIT")&&after.contains("\t137\n"));
      report();return;
    }
    File basic=new File(root,"basic");NetworkDiagnostics n=logger(basic,ENV,1);
    check("constructor performs no filesystem writes",!basic.exists());
    event(n,NetworkDiagnostics.Event.CORE_START,CORE,7);event(n,NetworkDiagnostics.Event.CORE_EXIT,CORE,137);flush();
    String text=summary(basic,ENV,1);check("exact exit status and fixed stop reason survive",text.contains("CORE_EXIT\tREQUESTED\tCORE\t137"));
    check("display numbering is one based",text.contains("环境编号：1"));
    check("core generation and environment identity are distinct",text.contains(CORE)&&text.contains(ENV));
    event(n,NetworkDiagnostics.Event.FAILURE,SECRET,9);flush();text=file(basic);
    check("untrusted generation cannot enter storage",!text.contains("private-password")&&!text.contains("example.invalid")&&!text.contains("raw-configuration")&&text.contains("unknown\tFAILURE"));
    check("unknown stop reason never accepts raw text",NetworkDiagnostics.reason(SECRET)==NetworkDiagnostics.Reason.UNKNOWN);
    boolean rejected=false;try{logger(new File(root,"invalid"),SECRET,0);}catch(IllegalArgumentException expected){rejected=true;}
    check("untrusted environment identity is rejected",rejected&&!new File(root,"invalid").exists());
    NetworkDiagnostics.Output output=n.output(CORE);output.add(4096);output.add(17);output.add(-1);output.close();output.close();flush();
    text=summary(basic,ENV,1);check("core output stores only total bytes",text.contains("CORE_OUTPUT\tUNKNOWN\tOUTPUT\t4113"));
    check("output close emits once",text.split("CORE_OUTPUT",-1).length==2);
    File delayed=new File(root,"unbound");NetworkDiagnostics late=NetworkDiagnostics.unbound(0,NetworkDiagnostics.Source.CONTROL);
    event(late,NetworkDiagnostics.Event.FAILURE,CORE,100);late.bind(delayed,ENV,2);event(late,NetworkDiagnostics.Event.CORE_START,CORE,101);flush();
    text=summary(delayed,ENV,2);check("events before identity capture are dropped",!text.contains("FAILURE")&&text.contains("CORE_START"));
    check("bound logger cannot acquire a recreated environment",!late.bind(delayed,NEXT,0));
    NetworkDiagnostics newer=logger(delayed,NEXT,0);event(newer,NetworkDiagnostics.Event.CORE_START,OTHER,102);event(late,NetworkDiagnostics.Event.CORE_EXIT,CORE,103);flush();
    String current=summary(delayed,NEXT,0),old=summary(delayed,ENV,2);
    check("late old exit never appears in recreated slot",current.contains(OTHER)&&!current.contains(CORE)&&!current.contains("CORE_EXIT"));
    check("old logger retains original identity after attempted rebind",old.contains(CORE)&&old.contains("CORE_EXIT")&&!old.contains(OTHER));
    NetworkDiagnostics reset=logger(delayed,NEXT,1);event(reset,NetworkDiagnostics.Event.ROLLBACK,OTHER,104);flush();
    check("environment generation also isolates reset history",summary(delayed,NEXT,1).contains("ROLLBACK")&&!summary(delayed,NEXT,1).contains("CORE_START"));
    File cap=new File(root,"capacity");NetworkDiagnostics bounded=logger(cap,ENV,3);
    for(int i=0;i<240;i++){event(bounded,NetworkDiagnostics.Event.RECONNECT_ATTEMPT,CORE,i);if(i%16==15)NetworkDiagnostics.flushForTest(10000);}flush();
    List<String> rows=Files.readAllLines(new File(cap,"control.events").toPath());
    check("persistent history has a fixed event bound",rows.size()==NetworkDiagnostics.MAX_EVENTS+1);
    check("persistent history has a fixed byte bound",new File(cap,"control.events").length()<=NetworkDiagnostics.MAX_BYTES);
    check("rotation keeps the latest bounded event",rows.get(rows.size()-1).endsWith("\t239"));
    for(int i=0;i<2000;i++)event(bounded,NetworkDiagnostics.Event.RECONNECT_ATTEMPT,CORE,i);flush();
    check("burst remains bounded",new File(cap,"control.events").length()<=NetworkDiagnostics.MAX_BYTES&&Files.readAllLines(new File(cap,"control.events").toPath()).size()<=NetworkDiagnostics.MAX_EVENTS+1);
    File tampered=new File(root,"tampered");tampered.mkdirs();
    String good=Files.readAllLines(new File(basic,"control.events").toPath()).get(1);
    Files.write(new File(tampered,"control.events").toPath(),(NetworkDiagnostics.HEADER+SECRET+"\n"+good+"\n"+good.replace("CORE_START",SECRET)+"\n").getBytes(StandardCharsets.UTF_8));
    text=summary(tampered,ENV,1);check("export revalidates and discards hostile stored rows",text.contains("CORE_START")&&!text.contains("private-password")&&!text.contains("subscription-token")&&!text.contains("example.invalid"));
    Files.write(new File(tampered,"control.events").toPath(),new byte[NetworkDiagnostics.MAX_BYTES+1]);
    check("oversized journal is not read into export",summary(tampered,ENV,1).contains("暂无事件记录"));
    File blocked=new File(root,"not-directory");Files.write(blocked.toPath(),new byte[]{1});NetworkDiagnostics broken=logger(blocked,ENV,0);
    event(broken,NetworkDiagnostics.Event.CORE_EXIT,CORE,1);flush();check("storage failure does not throw into caller",blocked.isFile());
    File restart=new File(root,"restart");event(logger(restart,ENV,4),NetworkDiagnostics.Event.CORE_START,CORE,55);flush();
    report();
  }
  static void report(){StringBuilder out=new StringBuilder("{\"passed\":").append(checks).append(",\"actualAndroidExecution\":false,\"checks\":[");for(int i=0;i<names.size();i++){if(i>0)out.append(',');out.append('"').append(names.get(i)).append('"');}System.out.println(out.append("]}"));}
}
