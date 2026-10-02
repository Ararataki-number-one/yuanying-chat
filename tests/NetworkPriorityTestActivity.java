package local.pocketchat;

import android.app.Activity;
import android.content.Context;
import android.os.Bundle;
import android.os.SystemClock;
import org.json.*;
import java.io.*;
import java.net.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

public class NetworkPriorityTestActivity extends Activity {
  final JSONArray checks=new JSONArray();long recoveryMs;
  void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));}
  static class FixtureNetwork extends NativeNetwork {
    boolean alive=true,mismatch=false;int starts=0,stops=0,verifications=0;final AtomicInteger closedSockets=new AtomicInteger();
    final CountDownLatch accepted=new CountDownLatch(2);ServerSocket server;final ExecutorService servers=Executors.newCachedThreadPool();
    FixtureNetwork(Context c)throws Exception{super(c);ready=true;token="fixture-token";currentEntry="Entry|primary";names=new ArrayList<>(Arrays.asList("Entry|primary","Entry|backup"));quality.configure("priority-fixture-"+System.nanoTime());server=new ServerSocket(0,0,InetAddress.getByName("127.0.0.1"));controllerPort=server.getLocalPort();
      servers.execute(()->{while(!server.isClosed())try{Socket socket=server.accept();servers.execute(()->serve(socket));}catch(Exception ignored){}});
    }
    void serve(Socket socket){try(Socket s=socket){s.setSoTimeout(6000);BufferedReader in=new BufferedReader(new InputStreamReader(s.getInputStream()));String line;while((line=in.readLine())!=null&&!line.isEmpty()){}accepted.countDown();if(in.read()==-1)closedSockets.incrementAndGet();}catch(Exception ignored){}}
    @Override boolean coreAlive(){return alive;}
    @Override boolean configurationMatches(){return true;}
    @Override void report(String text){message=text;}
    @Override void startNow(){starts++;alive=true;ready=true;}
    @Override void stopNow(){stops++;alive=false;ready=false;}
    @Override void selectNow(String name){currentEntry=name;}
    @Override JSONObject api(String method,String path,JSONObject body,int timeout)throws Exception{if(path.equals("/blocked"))return super.api(method,path,body,timeout);maintenanceCheck();return new JSONObject();}
    @Override int probe(String name){try{api("GET","/blocked",null,5000);}catch(Exception ignored){}return -1;}
    @Override String verifyExit()throws Exception{verifications++;Thread.sleep(60);if(mismatch)throw new ExitMismatch();return "fixture-verified-exit";}
    @Override void health(){}
    void close(){worker.shutdownNow();probes.shutdownNow();closers.shutdownNow();servers.shutdownNow();try{server.close();}catch(Exception ignored){}}
  }
  @Override public void onCreate(Bundle b){super.onCreate(b);new Thread(()->runTests(),"priority-tests").start();}
  void runTests(){FixtureNetwork n=null;try{
    n=new FixtureNetwork(this);final FixtureNetwork net=n;CountDownLatch scanDone=new CountDownLatch(1),recovered=new CountDownLatch(1);AtomicBoolean scanCancelled=new AtomicBoolean(),success=new AtomicBoolean();
    net.rescan((ok,text)->{scanCancelled.set(!ok&&text.contains("让位"));scanDone.countDown();});
    check("Full scan opens both actual local probe sockets",net.accepted.await(3,TimeUnit.SECONDS));long start=SystemClock.elapsedRealtime();
    net.recover((ok,text)->{success.set(ok);recoveryMs=SystemClock.elapsedRealtime()-start;recovered.countDown();});
    check("Priority recovery callback arrives",recovered.await(2,TimeUnit.SECONDS));
    check("Recovery is not queued behind five-second socket probes",success.get()&&recoveryMs<800);
    check("Cancelled scan returns a clear result",scanDone.await(1,TimeUnit.SECONDS)&&scanCancelled.get());
    check("Intentional scan cancellation leaves core running",net.ready&&net.alive&&net.stops==0&&net.starts==0);
    check("Priority recovery still verifies the fixed exit",net.verifications==1);
    check("Cancelled probes do not become route failures",net.quality.stats("Entry|primary",System.currentTimeMillis()).optInt("samples")==0);
    long until=SystemClock.elapsedRealtime()+1800;while(net.closedSockets.get()<2&&SystemClock.elapsedRealtime()<until)Thread.sleep(20);
    check("Cancellation releases actual blocked probe sockets",net.closedSockets.get()==2);
    Future<Integer> available=net.probes.submit(()->7);check("Probe pool remains usable after cancellation",available.get(1,TimeUnit.SECONDS)==7);
    check("Current entry is preserved during recovery",net.currentEntry.equals("Entry|primary"));
    check("Cancelled maintenance clears ownership",net.backgroundWork==null);
    check("Cancellation does not leave control worker interrupted",!net.worker.submit(()->Thread.currentThread().isInterrupted()).get(1,TimeUnit.SECONDS));

    net.mismatch=true;CountDownLatch mismatchDone=new CountDownLatch(1);AtomicBoolean rejected=new AtomicBoolean();
    net.recover((ok,text)->{rejected.set(!ok);mismatchDone.countDown();});mismatchDone.await(2,TimeUnit.SECONDS);
    check("Priority path still blocks an exit-IP mismatch",rejected.get()&&net.recoveryBlocked&&!net.ready);
    check("Exit mismatch never starts a replacement core",net.starts==0);
    CountDownLatch manualRestart=new CountDownLatch(1);net.restart((ok,text)->manualRestart.countDown());manualRestart.await(2,TimeUnit.SECONDS);
    check("Explicit restart can retry after a blocked exit",net.starts==1&&!net.recoveryBlocked&&net.ready);
    JSONObject timing=J.obj("priorityRecoveryMs",recoveryMs,"fixtureProbeTimeoutMs",5000);
    J.write(new File(getFilesDir(),"network-priority-results.json"),J.obj("checks",checks,"timing",timing).toString(2));
  }catch(Exception e){try{J.write(new File(getFilesDir(),"network-priority-results.json"),J.obj("checks",checks,"error",e.toString()).toString(2));}catch(Exception ignored){}}finally{if(n!=null)n.close();}}
}
