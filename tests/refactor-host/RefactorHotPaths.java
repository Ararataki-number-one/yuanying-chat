package local.pocketchat;

import android.content.Context;
import java.nio.file.Files;
import java.util.*;
import org.json.*;

/** Comparative host workload; baseline classes come from the requested git commit. */
public final class RefactorHotPaths {
  interface Work { void run() throws Exception; }
  static volatile Object sink;
  static int checks;
  static void check(boolean condition) { if(!condition)throw new AssertionError("Baseline behavior differs");checks++; }
  static JSONObject sample(String name,Work old,Work next,int repeats)throws Exception {
    for(int i=0;i<3;i++){old.run();next.run();}
    long[] before=new long[7],after=new long[7];
    for(int sample=0;sample<7;sample++) {
      // Alternate order to reduce warmup and scheduling bias.
      if(sample%2==0){before[sample]=time(old,repeats);after[sample]=time(next,repeats);}
      else {after[sample]=time(next,repeats);before[sample]=time(old,repeats);}
    }
    JSONObject result=J.obj("workload",name,"iterationsPerSample",repeats,"baselineSamplesNs",new JSONArray(before),"currentSamplesNs",new JSONArray(after));
    Arrays.sort(before);Arrays.sort(after);
    result.put("baselineMedianNsPerOperation",before[3]/repeats).put("currentMedianNsPerOperation",after[3]/repeats);
    return result;
  }
  static long time(Work task,int repeats)throws Exception {long begin=System.nanoTime();for(int i=0;i<repeats;i++)task.run();return System.nanoTime()-begin;}
  static JSONArray downloads(int count,Random random) {
    JSONArray rows=new JSONArray();String[] states={"saved","preparing","downloading","saving","choosing","failed","paused","cancelled",""};
    for(int i=0;i<count;i++) {
      if(i%19==0){rows.put(JSONObject.NULL);continue;}
      rows.put(J.obj("id",i%7==0?"":"file-"+i,"slot",random.nextInt(8),"uri",i%5==0?"":"content://fixture/"+i,"state",states[random.nextInt(states.length)],"time",random.nextInt(20)-2));
    }
    return rows;
  }
  public static void main(String[] args)throws Exception {
    JSONArray timings=new JSONArray();Random random=new Random(207);
    for(int n=0;n<160;n++) {
      JSONArray files=downloads(n,random),tasks=downloads(n/2,random);
      String unchanged=files.toString()+tasks.toString();
      JSONArray old=BaselineDownloadListPolicy.ordered(files,tasks),next=DownloadListPolicy.ordered(files,tasks);
      check(old.length()==next.length());
      for(int i=0;i<old.length();i++)check(old.get(i)==next.get(i));
      check(unchanged.equals(files.toString()+tasks.toString()));
    }
    for(int count:new int[]{8,100,1000}) {
      JSONArray files=downloads(count,random),tasks=downloads(count/4,random);
      timings.put(sample("download-list-"+count,()->sink=BaselineDownloadListPolicy.ordered(files,tasks),()->sink=DownloadListPolicy.ordered(files,tasks),count==1000?100:1000));
    }
    byte[] digest=new byte[32];random.nextBytes(digest);
    check(BaselineAppUpdatePolicy.hex(digest).equals(AppUpdatePolicy.hex(digest)));
    timings.put(sample("sha256-hex-32-bytes",()->sink=BaselineAppUpdatePolicy.hex(digest),()->sink=AppUpdatePolicy.hex(digest),10000));
    for(int size:new int[]{64,65536,1048576}) {
      byte[] bytes=new byte[size];random.nextBytes(bytes);
      check(BaselineAppUpdatePolicy.hash(bytes).equals(AppUpdatePolicy.hash(bytes)));
      timings.put(sample("sha256-"+size,()->sink=BaselineAppUpdatePolicy.hash(bytes),()->sink=AppUpdatePolicy.hash(bytes),size==1048576?50:1000));
    }
    Context context=new Context(Files.createTempDirectory("snapshot-refactor-").toFile(),0);
    SecretStore vault=new SecretStore(context);JSONObject candidate=J.obj("fixture",true);
    JSONObject source=J.obj("id","fixture-source","role","entry","url","https://fixture.invalid/subscription","addressRevision",3,"updatedAt",123,"cacheSlot","source-pool-entry-abc","nodes",J.arr("Entry|A"),"nodeDetails",J.arr(J.obj("name","Entry|A","type","VLESS")));
    byte[] bytes=new byte[1048576];random.nextBytes(bytes);
    BaselineNetworkSourceSelection.Sources oldSources=new BaselineNetworkSourceSelection.Sources(source,null,bytes,null);
    NetworkSourceSelection.Sources newSources=new NetworkSourceSelection.Sources(source,null,bytes,null);
    Work old=()->new BaselineNetworkSourceSelection.ActiveSnapshot(vault).write(oldSources,candidate);
    Work next=()->new NetworkSourceSelection.ActiveSnapshot(vault).write(newSources,candidate);
    old.run();Map<String,byte[]> expected=new LinkedHashMap<>();for(String key:NetworkSourceSelection.ActiveSnapshot.RECORDS)expected.put(key,vault.get(key));
    next.run();for(String key:expected.keySet())check(Arrays.equals(expected.get(key),vault.get(key)));
    timings.put(sample("snapshot-write-1MiB-host-plain-file-fixture",old,next,8));
    System.out.println(J.obj("status","passed","compatibilityChecks",checks,"actualAndroidExecution",false,"actualWanMeasurement",false,"scope","Host differential and microbenchmarks; not phone frame times or network latency","timings",timings));
  }
}
