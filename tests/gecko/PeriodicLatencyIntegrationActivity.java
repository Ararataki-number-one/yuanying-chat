package local.pocketchat;

import android.app.Activity;
import android.os.*;
import android.util.Log;
import org.json.*;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.TimeUnit;

/** Real two-minute cadence on an authenticated local chain with a live WebSocket. */
public final class PeriodicLatencyIntegrationActivity extends Activity {
  final JSONArray checks=new JSONArray(),labels=new JSONArray();
  void check(String name,boolean passed){checks.put(J.obj("name",name,"pass",passed));if(!passed)throw new AssertionError(name);}
  @Override public void onCreate(Bundle saved){super.onCreate(saved);if(!getPackageName().endsWith(".test"))throw new SecurityException();new Thread(this::run,"periodic-latency-fixture").start();}
  void run(){
    JSONObject report=J.obj("status","failed","actualAndroidExecution",true,"actualMihomoExecution",true,"controlledLocalChain",true,"realChatGptAcceptance",false);
    NativeProbeIntegrationActivity.ProbeNetwork n=null;
    try{
      NativeProbeIntegrationActivity.TlsFixture tls=new NativeProbeIntegrationActivity.TlsFixture(this,"network-fixture.p12");
      try(NetworkOptimizationIntegrationActivity.HttpFixture site=new NetworkOptimizationIntegrationActivity.HttpFixture(tls.context);
          NetworkOptimizationIntegrationActivity.HttpFixture plain=new NetworkOptimizationIntegrationActivity.HttpFixture(null);
          NativeProbeIntegrationActivity.ProbeFixture target=new NativeProbeIntegrationActivity.ProbeFixture(tls.context);
          NativeProbeIntegrationActivity.AuthSocks fixed=new NativeProbeIntegrationActivity.AuthSocks("fixed-exit",site.port(),plain.port(),target.port());
          NativeProbeIntegrationActivity.AuthSocks entry=new NativeProbeIntegrationActivity.AuthSocks("entry",fixed.port())){
        site.start();plain.start();target.start();fixed.start();entry.start();
        JSONObject config=J.obj("subscriptionUrl","https://synthetic.invalid/periodic-unused","exitHost","127.0.0.1","exitPort",fixed.port(),"exitUser","fixture","exitPassword","local-only","entryMode","manual","entryPool",J.arr("Entry|only"),"entry","Entry|only");
        SecretStore vault=new SecretStore(this);vault.save(config);
        vault.put("subscription",("proxies:\n  - {name: only, type: socks5, server: 127.0.0.1, port: "+entry.port()+", username: fixture, password: local-only}\n").getBytes(StandardCharsets.UTF_8));
        vault.put("subscription-meta",J.obj("urlHash",NativeNetwork.hash(config.getString("subscriptionUrl")),"updatedAt",System.currentTimeMillis()).toString().getBytes(StandardCharsets.UTF_8));
        getSharedPreferences("chat",0).edit().putString("networkMode","internal").putBoolean("networkConfigured",true).putString("lastGoodEntry","Entry|only").commit();
        n=new NativeProbeIntegrationActivity.ProbeNetwork(this,site,plain,tls.certificate,new File(getNoBackupFilesDir(),"periodic-probe-test"));n.startNow();
        n.controlledProbeUrl=target.url("/periodic");
        try(NetworkOptimizationIntegrationActivity.WebSocketStream stream=new NetworkOptimizationIntegrationActivity.WebSocketStream(n,site)){
          check("WebSocket connected before periodic measurements",stream.awaitEchoes(0));
          NativeNetwork.ProbeResult first=n.probeMeasured("FixedExit",n.currentEntry);n.publishCurrentProbe(first);n.recordProbe(first,first.at);
          check("First reading is a real successful chain probe",first.delay>0&&first.trace!=null&&target.count("/periodic")==2);
          String route=n.probeRouteKey(),exit=n.fingerprint,selected=n.currentEntry;int echoes=stream.echoes.get();long began=SystemClock.elapsedRealtime();
          n.busy=true; // Explicit controlled busy state; the WSS above carries actual frames.
          WindowNetworkState before=state(n,config);labels.put(before.latency+before.latencyTimer);
          check("Measured latency is displayed with a two-minute countdown",!before.latency.contains("未测")&&before.latencyTimer.matches("（0[12]:[0-5][0-9]）"));
          NativeNetwork.ProbeResult second=null;
          while(SystemClock.elapsedRealtime()-began<135000){
            n.refreshLatency();NativeNetwork.ProbeResult current=n.currentProbe;
            if(current!=null&&current.binding.measurement!=first.binding.measurement){second=current;break;}
            if(SystemClock.elapsedRealtime()-began<119000)checkNoEarlyProbe(target);
            Thread.sleep(250);
          }
          long elapsed=SystemClock.elapsedRealtime()-began;
          check("Current-route probe runs after two minutes even while busy",second!=null&&second.delay>0&&elapsed>=119000&&elapsed<135000&&target.count("/periodic")==4);
          // Finish the actual worker publication before checking suppression.
          n.worker.submit(()->{}).get(10,TimeUnit.SECONDS);
          for(int i=0;i<8;i++){n.refreshLatency();Thread.sleep(250);}
          check("UI ticks do not repeat a fresh measurement",target.count("/periodic")==4&&!n.latencyRefreshQueued);
          WindowNetworkState after=state(n,config);labels.put(after.latency+after.latencyTimer);
          check("New reading restarts the visible countdown",!after.latency.contains("未测")&&after.latencyTimer.matches("（01:5[0-9]）"));
          check("Probing preserves entry fixed exit and WebSocket",route.equals(n.probeRouteKey())&&exit.equals(n.fingerprint)&&selected.equals(n.currentEntry)&&site.webSocketConnections.get()==1&&stream.awaitEchoes(echoes)&&stream.failure==null);
          NetworkCatalog.put(report,"elapsedMs",elapsed);NetworkCatalog.put(report,"wire",target.evidence());NetworkCatalog.put(report,"first",first.publicSummary());NetworkCatalog.put(report,"second",second.publicSummary());
        }
      }
      NetworkCatalog.put(report,"buildIdentity",IntegrationBuildIdentity.read(this));NetworkCatalog.put(report,"status","passed");
    }catch(Throwable failure){NetworkCatalog.put(report,"error",failure.toString());Log.e("PocketPeriodicLatency","failed",failure);}
    finally{if(n!=null){n.stopNow();n.worker.shutdownNow();n.probes.shutdownNow();n.closers.shutdownNow();n.traffic.reader.shutdownNow();}}
    NetworkCatalog.put(report,"checks",checks);NetworkCatalog.put(report,"labels",labels);
    try{File staged=new File(getFilesDir(),"periodic-latency-results.json.tmp");J.write(staged,report.toString(2));if(!staged.renameTo(new File(getFilesDir(),"periodic-latency-results.json")))throw new java.io.IOException("Could not publish periodic latency report");}catch(Exception error){Log.e("PocketPeriodicLatency","report failed",error);}
    Log.i("PocketPeriodicLatency",J.obj("status",report.optString("status"),"error",report.optString("error")).toString());runOnUiThread(this::finish);
  }
  void checkNoEarlyProbe(NativeProbeIntegrationActivity.ProbeFixture target){if(target.count("/periodic")!=2)throw new AssertionError("Unexpected probe before the two-minute deadline");}
  WindowNetworkState state(NativeNetwork n,JSONObject config){return new WindowNetworkState(this,J.obj("slot",0,"name","Periodic fixture"),config,WindowNetworkState.live(null,n),true,System.currentTimeMillis());}
}
