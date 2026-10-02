package local.pocketchat;

import android.app.Activity;
import android.content.Context;
import android.os.Bundle;
import org.json.*;
import java.io.*;
import java.util.*;
import java.util.concurrent.*;

public class StartupRouteTestActivity extends Activity {
  final JSONArray checks=new JSONArray();final JSONArray timings=new JSONArray();
  void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));}
  static class FixtureNetwork extends NativeNetwork {
    final Map<String,Integer> delay=new ConcurrentHashMap<>();final List<String> selected=Collections.synchronizedList(new ArrayList<>());
    volatile int configured=0,probeCount=0,verifyCount=0;volatile boolean mismatch=false;volatile String failVerify="";long searchBudget=45000;
    FixtureNetwork(Context c,String... entries){super(c);token="fixture-epoch";names=new ArrayList<>(Arrays.asList(entries));quality.configure("fixture-entry-speed");}
    @Override void report(String text){message=text;}
    @Override JSONObject api(String method,String path,JSONObject body,int timeout)throws Exception{if(path.startsWith("/proxies/ProbeEntry")){configured++;Thread.sleep(8);}return new JSONObject();}
    @Override int probe(String name){probeCount++;int i=Integer.parseInt(name.replace("ProbeExit",""));String entry=names.get(i);int ms=delay.getOrDefault(entry,80);try{Thread.sleep(Math.abs(ms));}catch(InterruptedException e){Thread.currentThread().interrupt();return -1;}return ms<0?-1:ms;}
    @Override void selectNow(String name){currentEntry=name;selected.add(name);}
    @Override String verifyExit()throws Exception{verifyCount++;Thread.sleep(60);if(mismatch)throw new ExitMismatch();if(currentEntry.equals(failVerify))throw new IOException("Fixture exit unreachable");return "fixture-verified-exit";}
    @Override void health(){}
    @Override long startupSearchBudgetMs(){return searchBudget;}
    void close(){worker.shutdownNow();probes.shutdownNow();}
  }
  void remembered(String entry){getSharedPreferences("chat",0).edit().putString("lastGoodEntry",entry).commit();}
  long elapsed(long start){return android.os.SystemClock.elapsedRealtime()-start;}
  @Override public void onCreate(Bundle b){super.onCreate(b);new Thread(()->runTests(),"startup-route-tests").start();}
  void runTests(){try{
    remembered("Entry|known");FixtureNetwork known=new FixtureNetwork(this,"Entry|known","Entry|slow");
    long start=android.os.SystemClock.elapsedRealtime();known.chooseStartupRoute();long restored=elapsed(start);
    check("Saved route is selected first",known.selected.size()==1&&known.currentEntry.equals("Entry|known"));
    check("Saved route always verifies fixed exit",known.verifyCount==1);
    check("Saved route skips redundant delay requests",known.probeCount==0);
    check("Saved route skips all probe-group setup",known.configured==0);
    check("Saved route completes without full scan",known.startupPath.equals("remembered")&&restored<500);
    timings.put(J.obj("scenario","saved-route","durationMs",restored));known.close();

    remembered("");FixtureNetwork race=new FixtureNetwork(this,"Entry|slow","Entry|fast","Entry|dead","Entry|slower","Entry|queued");
    race.delay.put("Entry|slow",2500);race.delay.put("Entry|fast",80);race.delay.put("Entry|dead",-2400);race.delay.put("Entry|slower",2600);
    start=android.os.SystemClock.elapsedRealtime();race.chooseStartupRoute();long first=elapsed(start);
    check("Fast route wins independently of subscription order",race.currentEntry.equals("Entry|fast"));
    check("First healthy route still verifies fixed exit",race.verifyCount==1&&race.startupPath.equals("first-verified"));
    check("Startup does not wait for slow routes",first<900);
    check("Unneeded queued routes are never configured",race.configured==4);
    timings.put(J.obj("scenario","slow-first-and-healthy-alternative","durationMs",first));race.close();

    remembered("Entry|broken");FixtureNetwork fallback=new FixtureNetwork(this,"Entry|broken","Entry|backup");fallback.failVerify="Entry|broken";
    fallback.chooseStartupRoute();check("Unavailable remembered route selects verified backup",fallback.currentEntry.equals("Entry|backup")&&fallback.verifyCount==2);
    check("Failed remembered route is not probed twice",fallback.probeCount==1);fallback.close();

    remembered("");FixtureNetwork refused=new FixtureNetwork(this,"Entry|bad-check","Entry|verified");refused.delay.put("Entry|bad-check",20);refused.delay.put("Entry|verified",120);refused.failVerify="Entry|bad-check";
    refused.chooseStartupRoute();check("A delay success alone cannot release webpage",refused.verifyCount==2&&refused.currentEntry.equals("Entry|verified"));refused.close();

    remembered("Entry|changed");FixtureNetwork mismatch=new FixtureNetwork(this,"Entry|changed","Entry|backup");mismatch.mismatch=true;boolean blocked=false;
    try{mismatch.chooseStartupRoute();}catch(NativeNetwork.ExitMismatch expected){blocked=true;}
    check("Saved-route exit mismatch is surfaced",blocked);
    check("Exit mismatch never searches another entry",mismatch.selected.size()==1&&mismatch.probeCount==0);mismatch.close();

    remembered("");FixtureNetwork mismatchRace=new FixtureNetwork(this,"Entry|candidate","Entry|backup");mismatchRace.mismatch=true;blocked=false;
    try{mismatchRace.chooseStartupRoute();}catch(NativeNetwork.ExitMismatch expected){blocked=true;}
    check("Candidate exit mismatch stops selection",blocked&&mismatchRace.verifyCount==1&&mismatchRace.selected.size()==1);mismatchRace.close();

    FixtureNetwork none=new FixtureNetwork(this,"Entry|dead1","Entry|dead2");none.delay.put("Entry|dead1",-20);none.delay.put("Entry|dead2",-30);boolean unavailable=false;
    try{none.chooseStartupRoute();}catch(IOException expected){unavailable=expected.getMessage().contains("不会改为直连");}
    check("All failed chains leave network blocked",unavailable&&!none.ready&&none.selected.isEmpty()&&none.verifyCount==0);none.close();

    FixtureNetwork later=new FixtureNetwork(this,"Entry|dead0","Entry|dead1","Entry|dead2","Entry|dead3","Entry|late-good");
    for(int i=0;i<4;i++)later.delay.put("Entry|dead"+i,-20);later.chooseStartupRoute();
    check("Search continues past the first four unavailable entries",later.currentEntry.equals("Entry|late-good")&&later.verifyCount==1);later.close();

    FixtureNetwork timeout=new FixtureNetwork(this,"Entry|hung");timeout.delay.put("Entry|hung",2500);timeout.searchBudget=100;unavailable=false;start=android.os.SystemClock.elapsedRealtime();
    try{timeout.chooseStartupRoute();}catch(IOException expected){unavailable=expected.getMessage().contains("超时");}
    check("Unavailable route search has a bounded deadline",unavailable&&elapsed(start)<700);
    check("Timed out search cannot select or verify a route",timeout.selected.isEmpty()&&timeout.verifyCount==0&&!timeout.ready);timeout.close();

    FixtureNetwork stale=new FixtureNetwork(this,"Entry|stale");stale.delay.put("Entry|stale",180);new Thread(()->{try{Thread.sleep(40);stale.token="changed-epoch";}catch(Exception ignored){}}).start();unavailable=false;
    try{stale.chooseStartupRoute();}catch(IOException expected){unavailable=expected.getMessage().contains("连接已改变");}
    check("Old probe completion cannot select in a new connection",unavailable&&stale.selected.isEmpty()&&stale.verifyCount==0);stale.close();

    FixtureNetwork manual=new FixtureNetwork(this,"Entry|one","Entry|two");manual.scanAndSelect(true);
    check("Manual full scan configures every probe group",manual.configured==2);
    check("Manual full scan keeps every route result",manual.results.length()==2&&manual.probeCount==2);manual.close();

    J.write(new File(getFilesDir(),"startup-route-results.json"),J.obj("checks",checks,"controlledTimings",timings).toString(2));
  }catch(Exception e){try{J.write(new File(getFilesDir(),"startup-route-results.json"),J.obj("checks",checks,"error",e.toString()).toString(2));}catch(Exception ignored){}}}
}
