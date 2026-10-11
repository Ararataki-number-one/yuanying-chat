package local.pocketchat;

import android.app.Activity;
import android.content.Context;
import android.os.Bundle;
import android.util.Log;
import org.json.*;
import java.io.*;
import java.net.*;
import java.security.KeyStore;
import java.security.MessageDigest;
import javax.net.ssl.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;

/** Actual Android/Mihomo with two loopback SOCKS hops. Never uses personal or public routes. */
public final class NetworkOptimizationIntegrationActivity extends Activity {
  final JSONArray checks=new JSONArray();
  void check(String name,boolean passed){JSONObject value=J.obj("name",name,"pass",passed);checks.put(value);Log.i("PocketNetworkPerformance",J.obj("kind","check","value",value).toString());if(!passed)throw new AssertionError(name);}
  @Override public void onCreate(Bundle state){super.onCreate(state);if(!getPackageName().endsWith(".test"))throw new SecurityException();new Thread(this::run,"network-optimization-fixture").start();}
  static class TestNetwork extends NativeNetwork {
    final HttpFixture site,plain;final SSLSocketFactory trustFactory;volatile boolean busy;volatile String exitFailureReason="";volatile boolean cancelOnMismatch;
    TestNetwork(Context c,HttpFixture site,HttpFixture plain){this(c,site,plain,false);}
    TestNetwork(Context c,HttpFixture site,HttpFixture plain,boolean isolated){this(c,site,plain,new File(c.getNoBackupFilesDir(),isolated?"network-runtime":"network-performance-test"));}
    TestNetwork(Context c,HttpFixture site,HttpFixture plain,File directory){super(c,directory,false);this.site=site;this.plain=plain;trustFactory=site.tls.getSocketFactory();}
    @Override HttpURLConnection openProbeConnection(String target,int port)throws IOException{HttpURLConnection c=super.openProbeConnection(target,port);if(c instanceof HttpsURLConnection){if(!target.startsWith(site.url("/")))throw new IOException("Only controlled TLS endpoints are allowed");((HttpsURLConnection)c).setSSLSocketFactory(trustFactory);}return c;}
    @Override String websiteUrl(){return site.url("/website");}
    @Override String probeUrl(){return plain.url("/probe");}
    @Override String exitCheckUrl(){return site.url("/ip");}
    @Override String verifyExit()throws Exception{exitFailureReason="";try{return super.verifyExit();}catch(ExitCheckUnavailable unavailable){exitFailureReason=unavailable.reason;throw unavailable;}catch(ExitMismatch mismatch){if(cancelOnMismatch)cancelMaintenance();throw mismatch;}}
    @Override boolean routeBusy(){return busy;}
    @Override boolean backgroundIdle(){return false;}
    @Override void report(String value){message=value;}
  }
  void run(){JSONObject report=J.obj("status","failed","actualAndroidExecution",true,"actualMihomoExecution",true);TestNetwork n=null;
    try(HttpFixture site=new HttpFixture(tlsContext());HttpFixture plain=new HttpFixture(null);Socks fixed=new Socks(0);Socks slow=new Socks(100);Socks fast=new Socks(5)){
      site.start();plain.start();fixed.start();slow.start();fast.start();
      regionCacheChecks();
      deferredCandidateRaceChecks();
      JSONObject config=J.obj("subscriptionUrl","https://synthetic.invalid/unused-subscription","exitHost","127.0.0.1","exitPort",fixed.port(),"entryMode","latency","entryPool",J.arr("Entry|slow","Entry|fast"),"entry","");
      SecretStore vault=new SecretStore(this);vault.save(config);String yaml="proxies:\n  - {name: slow, type: socks5, server: 127.0.0.1, port: "+slow.port()+"}\n  - {name: fast, type: socks5, server: 127.0.0.1, port: "+fast.port()+"}\n";
      vault.put("subscription",yaml.getBytes(StandardCharsets.UTF_8));vault.put("subscription-meta",J.obj("urlHash",NativeNetwork.hash(config.getString("subscriptionUrl")),"updatedAt",System.currentTimeMillis()).toString().getBytes(StandardCharsets.UTF_8));
      List<String> nodes=Arrays.asList("Entry|slow","Entry|fast","Entry|foreign");EntrySelection.validate(config,nodes);
      check("Low latency permits a pool without a preselected entry",EntrySelection.allowed(config,nodes).equals(Arrays.asList("Entry|slow","Entry|fast")));
      JSONObject wrong=J.parse(config.toString());NetworkCatalog.put(wrong,"entryPool",J.arr("Entry|other"));boolean rejected=false;try{EntrySelection.validate(wrong,nodes);}catch(IOException expected){rejected=true;}check("Foreign subscription nodes are rejected",rejected);
      NetworkCatalog.put(wrong,"entryPool",new JSONArray());rejected=false;try{EntrySelection.validate(wrong,nodes);}catch(IOException expected){rejected=true;}check("An empty optimization pool is rejected",rejected);
      NetworkCatalog library=new NetworkCatalog(this);JSONObject sub=library.addSubscription("synthetic",config.getString("subscriptionUrl"));library.parsed(sub.getString("id"),J.arr("Entry|slow","Entry|fast"),yaml.getBytes(StandardCharsets.UTF_8),System.currentTimeMillis());JSONObject exit=library.addExit("synthetic exit","","127.0.0.1",fixed.port(),"","");
      NetworkDraft draft=new NetworkDraft(0,config,library);draft.exitId=exit.getString("id");check("Draft restores the low latency mode",draft.mode.equals("latency"));check("Draft saves only the permitted pool",draft.candidate(library).getJSONArray("entryPool").length()==2);draft.subscription("missing",library);check("Changing subscription clears candidates and pool",draft.pool.isEmpty()&&draft.entry.isEmpty());
      check("Maintenance rounds stay bounded",NetworkOptimizationPolicy.batch(nodes,nodes,"Entry|slow",0).size()<=4);
      LinkedHashSet<String> explored=new LinkedHashSet<>();List<String> many=new ArrayList<>();for(int i=0;i<20;i++)many.add("Entry|"+i);for(int i=0;i<many.size();i++)explored.addAll(NetworkOptimizationPolicy.batch(many,many,"Entry|0",i));check("Round robin explores the whole allowed pool",explored.containsAll(many));

      n=new TestNetwork(this,site,plain);getSharedPreferences("chat",0).edit().putString("lastGoodEntry","Entry|slow").commit();n.startNow();
      check("Production Mihomo starts with ARC DNS and TCP concurrency",n.ready&&n.coreAlive());check("Startup verifies the same controlled fixed exit",n.exitIp.equals("203.0.113.8")&&n.currentEntry.equals("Entry|slow"));
      getSharedPreferences("chat",0).edit().putString("networkMode","internal").putBoolean("networkConfigured",true).commit();
      check("Remembered route starts without an invented delay",n.quality.stats(n.currentEntry,System.currentTimeMillis()).optInt("samples")==0);
      n.busy=true;String initialToken=n.token,initialEntry=n.currentEntry;int initialRequests=plain.probeRequests.get();WindowNetworkState.live(null,n);n.worker.submit(()->{}).get(5,TimeUnit.SECONDS);
      NetworkCatalog.put(report,"initialDisplaySampling",J.obj("busyRequests",plain.probeRequests.get()-initialRequests));
      check("Automatic display sampling makes no requests while a reply is busy",plain.probeRequests.get()==initialRequests&&n.ready&&!n.latencyRefreshQueued);
      n.busy=false;WindowNetworkState.live(null,n);n.worker.submit(()->{}).get(15,TimeUnit.SECONDS);
      JSONObject initialRuntime=WindowNetworkState.live(null,n);JSONObject row=J.obj("slot",0,"name","synthetic window");WindowNetworkState initialState=new WindowNetworkState(this,row,n.settings,initialRuntime,true,System.currentTimeMillis());
      NetworkCatalog.put(report.optJSONObject("initialDisplaySampling"),"idleRequests",plain.probeRequests.get()-initialRequests);
      check("The current route gets a real first sample after the reply becomes idle",initialRuntime.optLong("delayAt")>0&&initialRuntime.optInt("delay")>0&&initialState.latency.matches("[0-9]+ ms")&&plain.probeRequests.get()>initialRequests);
      check("Display sampling preserves entry core and fixed exit",n.ready&&n.token.equals(initialToken)&&n.currentEntry.equals(initialEntry)&&n.exitIp.equals("203.0.113.8")&&n.api("GET","/proxies/EntryChoice",null,3000).optString("now").equals(initialEntry));
      int displayRequests=plain.requests;WindowNetworkState.live(null,n);WindowNetworkState.live(null,n);n.worker.submit(()->{}).get(5,TimeUnit.SECONDS);check("Repeated UI reads do not repeatedly probe the route",plain.requests==displayRequests);
      JSONObject staleRuntime=J.parse(initialRuntime.toString());long staleNow=System.currentTimeMillis();NetworkCatalog.put(staleRuntime,"at",staleNow);NetworkCatalog.put(staleRuntime,"delayAt",staleNow-90001);WindowNetworkState staleState=new WindowNetworkState(this,row,n.settings,staleRuntime,true,staleNow);check("A stale real sample remains visible and is explicitly marked previous",staleState.latency.equals(initialRuntime.getInt("delay")+" ms（上次）"));
      NetworkCatalog.put(staleRuntime,"delayAt",staleNow);NetworkCatalog.put(staleRuntime,"delay",-1);check("A real failed sample is not mislabeled unmeasured",new WindowNetworkState(this,row,n.settings,staleRuntime,true,staleNow).latency.equals("探测未通过"));
      NetworkCatalog.put(staleRuntime,"exitId","different-fixed-exit");check("Display does not reuse a different fixed exit's sample",new WindowNetworkState(this,row,n.settings,staleRuntime,true,staleNow).latency.equals("延迟未测"));n.busy=false;
      n.quality.configure("synthetic-display-failure");NetworkCatalog.put(n.latencyReading,"at",staleNow-90001);n.latencyRefreshAttempted=-60000;plain.probeStatus=403;WindowNetworkState.live(null,n);n.worker.submit(()->{}).get(15,TimeUnit.SECONDS);
      WindowNetworkState failedDisplay=new WindowNetworkState(this,row,n.settings,WindowNetworkState.live(null,n),true,System.currentTimeMillis());
      check("A blocked display probe reports its failure while preserving the usable connection",failedDisplay.connected&&failedDisplay.state.equals("正常")&&failedDisplay.latency.equals("探测未通过")&&n.ready&&n.currentEntry.equals(initialEntry));
      check("Display-only failure does not poison route quality or trigger switching",n.quality.stats(initialEntry,System.currentTimeMillis()).optInt("samples")==0&&n.failures==0&&n.token.equals(initialToken));
      n.quality.record(initialEntry,-1,n.latencyReading.optLong("at")-1);JSONObject independentlyFailed=WindowNetworkState.live(null,n);WindowNetworkState failedHealth=new WindowNetworkState(this,row,n.settings,independentlyFailed,true,System.currentTimeMillis());
      check("A newer display-only sample cannot hide the original health failure",!independentlyFailed.optBoolean("delayHealth")&&independentlyFailed.optInt("healthDelay")==-1&&independentlyFailed.optLong("healthDelayAt")>0&&!failedHealth.connected&&failedHealth.state.equals("需检查"));
      JSONObject legacyHealth=J.parse(independentlyFailed.toString());legacyHealth.remove("healthDelay");legacyHealth.remove("healthDelayAt");NetworkCatalog.put(legacyHealth,"delayHealth",true);check("Legacy saved runtime keeps its original health failure semantics",new WindowNetworkState(this,row,n.settings,legacyHealth,true,System.currentTimeMillis()).state.equals("需检查"));
      plain.probeStatus=204;n.quality.configure("synthetic-display-recovered");n.latencyReading=new JSONObject();n.latencyRefreshAttempted=-60000;WindowNetworkState.live(null,n);n.worker.submit(()->{}).get(15,TimeUnit.SECONDS);
      Proxy exactProxy=new Proxy(Proxy.Type.HTTP,new InetSocketAddress("127.0.0.1",n.proxyPort));int responseDelay=RouteLatency.measure(plain.url("/probe"),exactProxy,null,()->{});
      check("External connection response can be measured over an explicit existing proxy",responseDelay>0&&n.currentEntry.equals(initialEntry)&&n.token.equals(initialToken)&&n.exitIp.equals("203.0.113.8"));
      JSONObject external=J.obj("at",staleNow,"mode","external","configured",true,"connected",true,"route","synthetic-proxy|network-1","delayRoute","synthetic-proxy|network-1","delayAt",staleNow,"delay",responseDelay,"delayKind","response");
      check("External measured response is shown instead of permanently unmeasured",new WindowNetworkState(this,row,new JSONObject(),external,true,staleNow).latency.equals(responseDelay+" ms"));
      NetworkCatalog.put(external,"route","synthetic-proxy|network-2");check("Switching the actual phone network invalidates the previous response",new WindowNetworkState(this,row,new JSONObject(),external,true,staleNow).latency.equals("延迟未测"));
      int guardedRequests=plain.requests;boolean gateRejected=false;try{RouteLatency.measure(plain.url("/probe"),exactProxy,null,()->{throw new IOException("route unavailable");});}catch(IOException expected){gateRejected=true;}check("A blocked external route makes no test request or direct fallback",gateRejected&&plain.requests==guardedRequests);
      JSONObject core=n.api("GET","/configs",null,3000);check("TCP concurrency is enabled by the running core",core.optBoolean("tcp-concurrent"));
      JSONObject runningConfig=J.parse(new String(java.nio.file.Files.readAllBytes(new File(n.root,"config.json").toPath()),StandardCharsets.UTF_8));check("DNS nameservers remain guarded by the fixed exit",runningConfig.getJSONObject("dns").getJSONArray("nameserver").getString(0).endsWith("#FixedExit"));
      JSONObject first=n.measureWebsite("Entry|slow");check("First and repeat website headers are measured",first.getString("status").equals("ok")&&first.getLong("firstMs")>0&&first.getLong("warmMs")>0);
      NetworkCatalog.put(report,"firstWebsiteReading",first);NetworkCatalog.put(report,"headConnectionIds",new JSONArray(site.headConnections));check("HEAD repeat reuses the same controlled HTTP connection",site.headConnections.size()>=2&&site.headConnections.get(0).equals(site.headConnections.get(1)));
      check("Website probes contain no account Cookie or Authorization",!site.credentialsSeen);
      JSONObject alternative=n.measureWebsite("Entry|fast");check("A different candidate uses a new probe connection",!site.headConnections.get(1).equals(site.headConnections.get(2)));
      check("Candidate probing leaves the live route unchanged",n.currentEntry.equals("Entry|slow")&&n.api("GET","/proxies/EntryChoice",null,3000).getString("now").equals("Entry|slow"));
      check("Both entry routes and the same fixed exit carry real requests",slow.connections>0&&fast.connections>0&&fixed.connections>=2);
      NetworkCatalog.put(report,"controlledWebsiteReadings",J.arr(first,alternative));
      site.status=403;JSONObject blocked=n.measureWebsite("Entry|slow");check("Site challenges are reported separately",blocked.getString("status").equals("restricted")&&n.ready);int before=n.websiteQuality.stats("Entry|slow",System.currentTimeMillis()).getInt("samples");n.measureWebsite("Entry|slow");check("Site challenges do not count as failed routes",n.websiteQuality.stats("Entry|slow",System.currentTimeMillis()).getInt("samples")==before);
      site.status=405;check("HEAD unsupported is explicit",n.measureWebsite("Entry|slow").getString("status").equals("unsupported"));site.status=302;site.redirectSeen=false;check("Website redirects are not followed",n.measureWebsite("Entry|slow").getInt("code")==302&&!site.redirectSeen);site.status=200;
      int dnsDelay=NetworkDns.measure(n,site.url("/dns"));check("DNS timing accepts a genuine matching A response",dnsDelay>0);check("DNS probe uses the current fixed exit",n.currentEntry.equals("Entry|slow")&&n.exitIp.equals("203.0.113.8"));
      byte[] valid=site.dnsAnswer();valid[0]^=1;check("A different DNS transaction is rejected",!NetworkDns.valid(valid));valid=site.dnsAnswer();valid[3]|=3;check("Failed DNS resolution is rejected",!NetworkDns.valid(valid));check("Truncated DNS packets are rejected",!NetworkDns.valid(NetworkDns.query()));
      long now=System.currentTimeMillis();n.dns.configure("synthetic-dns");for(int i=0;i<NetworkDns.SERVERS.length;i++)n.dns.record(NetworkDns.SERVERS[i],i==2?30:150+i,now);check("Measured DNS selects the quickest valid service",n.dns.primary(now).equals(NetworkDns.SERVERS[2]));check("Fresh DNS readings prevent repeated probes",n.dns.next(now).isEmpty());check("Expired DNS is scheduled for renewal",!n.dns.next(now+NetworkDns.TTL+1).isEmpty());check("DNS choice survives recreation",new NetworkDns(this).primary(now).equals(NetworkDns.SERVERS[2]));check("DNS measurements stay isolated by environment",new NetworkDns(Profiles.context(this,1)).primary(now).equals(NetworkDns.SERVERS[0]));check("DNS selection expires with its evidence",n.dns.primary(now+NetworkDns.TTL+1).equals(NetworkDns.SERVERS[0]));n.dns.configure("different-exit");check("A different route resets DNS choice",n.dns.primary(now).equals(NetworkDns.SERVERS[0]));
      n.busy=true;int requests=site.requests;n.runHealth();Thread.sleep(100);check("Busy maintenance makes no extra website or DNS requests",requests==site.requests&&n.ready);n.lastManualProbe=0;String manualEntry=n.currentEntry,manualToken=n.token;CountDownLatch manualDone=new CountDownLatch(1);final boolean[] manualOk={false};n.measureLatency((ok,message)->{manualOk[0]=ok;manualDone.countDown();});check("Explicit speed test runs while reply is busy",manualDone.await(20,TimeUnit.SECONDS)&&manualOk[0]);check("Busy manual speed test preserves live entry and exit",n.ready&&n.currentEntry.equals(manualEntry)&&n.token.equals(manualToken)&&n.exitIp.equals("203.0.113.8"));n.busy=false;
      site.delayedRequest=new CountDownLatch(1);site.websiteDelay=2000;final TestNetwork active=n;
      Future<Boolean> cancelled=n.worker.submit(()->{NetworkWork work=active.beginMaintenance(active.maintenanceGeneration);try{active.measureWebsite(active.currentEntry);return false;}catch(InterruptedIOException expected){return true;}finally{active.finishMaintenance(work);}});
      check("An actual website request reaches the cancellation fixture",site.delayedRequest.await(5,TimeUnit.SECONDS));long cancelAt=android.os.SystemClock.elapsedRealtime();n.busy=true;n.cancelMaintenance();
      check("Starting a user operation cancels the active probe",cancelled.get(3,TimeUnit.SECONDS)&&android.os.SystemClock.elapsedRealtime()-cancelAt<1500);
      check("Cancellation keeps the live route and core",n.ready&&n.coreAlive()&&n.currentEntry.equals("Entry|slow"));n.busy=false;site.websiteDelay=0;
      RouteQuality q=new RouteQuality(this,"performance-test-quality");q.configure("synthetic-route");for(int i=0;i<5;i++){q.record("slow",400,now+i);q.record("fast",90,now+i);q.record("unstable",i%2==0?20:-1,now+i);}q.selected("slow",now);
      check("A healthy route is held during cooldown",q.choose(Arrays.asList("slow","fast"),"slow",false,false,now+1000).equals("slow"));check("Activity prevents performance-only switching",q.choose(Arrays.asList("slow","fast"),"slow",false,true,now+RouteQuality.COOLDOWN+1000).equals("slow"));check("A consistently faster stable route wins when idle",q.choose(Arrays.asList("slow","fast"),"slow",false,false,now+RouteQuality.COOLDOWN+2000).equals("fast"));check("Failures outweigh a deceptively fast sample",q.ranked(Arrays.asList("unstable","fast"),now).get(0).equals("fast"));
      n.quality.configure("synthetic-old-modes");for(int i=0;i<5;i++){n.quality.record("Entry|slow",500,now+i);n.quality.record("Entry|fast",30,now+i);}n.quality.selected("Entry|slow",now-RouteQuality.COOLDOWN-1000);NetworkCatalog.put(n.settings,"entryMode","random");n.scanAndSelect(false);check("Healthy random mode is not silently optimized",n.currentEntry.equals("Entry|slow"));NetworkCatalog.put(n.settings,"entryMode","manual");n.scanSubset(Collections.singletonList("Entry|slow"),false,false);check("Manual mode keeps the specified entry",n.currentEntry.equals("Entry|slow"));
      NetworkCatalog.put(n.settings,"entryMode","latency");n.websiteQuality.configure("synthetic-low-latency");for(int i=0;i<5;i++){n.websiteQuality.record("Entry|slow",900,now+i);n.websiteQuality.record("Entry|fast",50,now+i);}n.websiteQuality.selected("Entry|slow",now-RouteQuality.COOLDOWN-1000);n.websiteQuality.choose(n.names,n.currentEntry,false,true,now);n.scanSubset(n.names,false,true);check("Low latency selects a proven better candidate",n.currentEntry.equals("Entry|fast"));check("Optimizing preserves the fixed exit IP",n.exitIp.equals("203.0.113.8"));
      n.ready=true;site.ip="203.0.113.9";boolean mismatch=false;try{n.verifyExit();}catch(NativeNetwork.ExitMismatch expected){mismatch=true;}check("Exit IP changes still trigger the original protection",mismatch&&n.recoveryBlocked);
      site.ip="203.0.113.8";exitVerificationContinuityChecks(n,site,plain,fixed,slow,fast);displaySchedulingChecks(n,site,plain,report);testTransport(site,plain,config,yaml);
      NetworkCatalog.put(report,"independentNetworkService","passed");NetworkCatalog.put(report,"status","passed");
    }catch(Throwable error){NetworkCatalog.put(report,"error",error.toString());}
    finally{if(n!=null){n.stopNow();n.worker.shutdownNow();n.probes.shutdownNow();n.closers.shutdownNow();n.traffic.reader.shutdownNow();}}
    NetworkCatalog.put(report,"checks",checks);try{J.write(new File(getFilesDir(),"network-performance-results.json"),report.toString(2));}catch(Exception ignored){}
    report.remove("checks");NetworkCatalog.put(report,"checkCount",checks.length());Log.i("PocketNetworkPerformance",report.toString());runOnUiThread(this::finish);
  }
  boolean awaitNetworkCallback(TestNetwork n,boolean beforeSend)throws Exception{
    CountDownLatch done=new CountDownLatch(1);final boolean[] result={false};NativeNetwork.Callback callback=(ok,message)->{result[0]=ok;done.countDown();};
    if(beforeSend)n.beforeSend(callback);else n.checkExit(callback);
    if(!done.await(25,TimeUnit.SECONDS))throw new IOException("Controlled exit callback timed out");return result[0];
  }
  int corePid(TestNetwork n)throws Exception{return Integer.parseInt(new String(java.nio.file.Files.readAllBytes(new File(n.root,"core.pid").toPath()),StandardCharsets.US_ASCII).trim());}
  void resetDisplay(TestNetwork n,String scope){n.quality.configure(scope);n.latencyReading=new JSONObject();n.latencyRefreshRoute="";n.latencyRefreshAttempted=-60000;}
  void displaySchedulingChecks(TestNetwork n,HttpFixture site,HttpFixture plain,JSONObject report)throws Exception{
    n.startNow();String entry=n.currentEntry,token=n.token;int pid=corePid(n),connections=site.webSocketConnections.get();JSONObject evidence=new JSONObject();
    try(WebSocketStream stream=new WebSocketStream(n,site)){
      check("Telemetry scheduling begins with a genuine persistent protected WebSocket",stream.awaitEchoes(0)&&n.verifiedRouteCurrent());
      resetDisplay(n,"synthetic-queued-busy");CountDownLatch parked=new CountDownLatch(1),release=new CountDownLatch(1);
      Future<?> held=n.worker.submit(()->{parked.countDown();if(!release.await(5,TimeUnit.SECONDS))throw new IOException("Display scheduling fixture timed out");return null;});
      if(!parked.await(3,TimeUnit.SECONDS))throw new IOException("Display worker did not park");int before=plain.probeRequests.get(),echoes=stream.echoes.get();
      try{n.refreshLatency();n.busy=true;}finally{release.countDown();}held.get(3,TimeUnit.SECONDS);n.worker.submit(()->{}).get(5,TimeUnit.SECONDS);
      NetworkCatalog.put(evidence,"queuedBusyRequests",plain.probeRequests.get()-before);
      check("Queued automatic sampling yields to a reply that started before execution",plain.probeRequests.get()==before&&!n.latencyRefreshQueued&&stream.awaitEchoes(echoes));
      n.busy=false;n.refreshLatency();n.worker.submit(()->{}).get(15,TimeUnit.SECONDS);NetworkCatalog.put(evidence,"idleSampleRequests",plain.probeRequests.get()-before);
      check("Deferred automatic sampling resumes idle without a fabricated failure or route change",plain.probeRequests.get()>before&&n.latencyReading.optInt("delay")>0&&entry.equals(n.currentEntry)&&token.equals(n.token)&&corePid(n)==pid);
      resetDisplay(n,"synthetic-queued-newer-sample");CountDownLatch parkedAgain=new CountDownLatch(1),releaseAgain=new CountDownLatch(1);
      held=n.worker.submit(()->{parkedAgain.countDown();if(!releaseAgain.await(5,TimeUnit.SECONDS))throw new IOException("Fresh sample fixture timed out");return null;});
      if(!parkedAgain.await(3,TimeUnit.SECONDS))throw new IOException("Fresh sample worker did not park");before=plain.probeRequests.get();echoes=stream.echoes.get();
      try{n.refreshLatency();n.quality.record(entry,77,System.currentTimeMillis());}finally{releaseAgain.countDown();}held.get(3,TimeUnit.SECONDS);n.worker.submit(()->{}).get(5,TimeUnit.SECONDS);
      NetworkCatalog.put(evidence,"newerSampleDuplicateRequests",plain.probeRequests.get()-before);
      check("Queued display sampling reuses a newer same-route health sample instead of probing twice",plain.probeRequests.get()==before&&n.quality.stats(entry,System.currentTimeMillis()).optInt("latest")==77&&n.latencyReading.length()==0&&stream.awaitEchoes(echoes));
      check("Automatic telemetry deferral preserves one WebSocket and the exact core identity",site.webSocketConnections.get()==connections+1&&stream.failure==null&&entry.equals(n.currentEntry)&&token.equals(n.token)&&corePid(n)==pid&&n.verifiedRouteCurrent());
      String mode=n.settings.optString("entryMode");NetworkCatalog.put(n.settings,"entryMode","random");n.failures=1;plain.forcedProbeFailures.set(2);site.ipDelay=250;int ipBefore=site.ipRequests.get();echoes=stream.echoes.get();long began=android.os.SystemClock.elapsedRealtime();
      try{n.health();}finally{site.ipDelay=0;plain.forcedProbeFailures.set(0);NetworkCatalog.put(n.settings,"entryMode",mode);}
      NetworkCatalog.put(evidence,"recoveryExitRequests",site.ipRequests.get()-ipBefore);NetworkCatalog.put(evidence,"recoveryMs",android.os.SystemClock.elapsedRealtime()-began);
      check("Actual failed-chain recovery performs exactly one full exit verification for the new entry",site.ipRequests.get()==ipBefore+1&&!entry.equals(n.currentEntry)&&n.verifiedRouteCurrent()&&n.ready&&n.exitIp.equals("203.0.113.8"));
      check("Removing duplicate recovery verification preserves the live WebSocket and fixed exit",stream.awaitEchoes(echoes)&&stream.failure==null&&site.webSocketConnections.get()==connections+1&&token.equals(n.token)&&corePid(n)==pid);
      NetworkCatalog.put(evidence,"webSocketConnections",site.webSocketConnections.get()-connections);NetworkCatalog.put(evidence,"webSocketEchoes",stream.echoes.get());NetworkCatalog.put(report,"telemetryScheduling",evidence);
    }finally{n.busy=false;site.ipDelay=0;plain.forcedProbeFailures.set(0);}
  }
  void exitVerificationContinuityChecks(TestNetwork n,HttpFixture site,HttpFixture plain,Socks fixed,Socks slow,Socks fast)throws Exception{
    // Restore the real core after the earlier, intentional mismatch check. All faults
    // below affect only the synthetic IP service, never the actual WebSocket endpoint.
    n.stopNow();n.startNow();String mode=n.settings.optString("entryMode");NetworkCatalog.put(n.settings,"entryMode","manual");
    final String entry=n.currentEntry,token=n.token,ip=n.exitIp;final int pid=corePid(n),port=n.proxyPort,fixedBefore=fixed.connections;final Socks selectedEntry=entry.equals("Entry|slow")?slow:fast;int entryBefore=selectedEntry.connections;long verified=n.lastVerified;
    try(WebSocketStream stream=new WebSocketStream(n,site)){
      check("A real WSS connection carries continuous frames through both Mihomo SOCKS hops",stream.awaitEchoes(0)&&site.webSocketConnections.get()==1&&fixed.connections>fixedBefore&&selectedEntry.connections>entryBefore);
      check("The live core and selected route have a successful exit verification receipt",n.verifiedRouteCurrent());
      site.ipStatus=503;n.lastVerified=0;n.nextExitCheckAt=0;int echoes=stream.echoes.get(),ipRequests=site.ipRequests.get();n.health();
      check("A temporary exit HTTP failure preserves the same WSS core and fixed route",site.ipRequests.get()>ipRequests&&n.exitFailureReason.equals("http-503")&&n.ready&&n.coreAlive()&&corePid(n)==pid&&n.proxyPort==port&&token.equals(n.token)&&entry.equals(n.currentEntry)&&ip.equals(n.exitIp)&&stream.awaitEchoes(echoes));
      check("Exit verification failure schedules bounded retry without claiming fresh success",n.exitCheckFailures==1&&n.nextExitCheckAt>android.os.SystemClock.elapsedRealtime()&&n.lastVerified==0&&n.verifiedRouteCurrent());
      int requests=site.ipRequests.get();n.health();
      check("Exit verification backoff makes no repeated IP requests or WebSocket replacement",site.ipRequests.get()==requests&&site.webSocketConnections.get()==1&&stream.failure==null);
      n.failures=1;plain.probeStatus=503;echoes=stream.echoes.get();n.health();
      check("Detector backoff prevents failed latency probes from replacing the verified WSS route",site.ipRequests.get()==requests&&n.ready&&corePid(n)==pid&&token.equals(n.token)&&entry.equals(n.currentEntry)&&n.verifiedRouteCurrent()&&stream.awaitEchoes(echoes));plain.probeStatus=204;n.failures=0;
      site.ipStatus=200;site.ipDelay=11000;n.lastVerified=0;n.nextExitCheckAt=0;echoes=stream.echoes.get();ipRequests=site.ipRequests.get();n.health();
      check("A real exit read timeout leaves the existing WSS tunnel responsive",site.ipRequests.get()>ipRequests&&n.exitFailureReason.equals("timeout")&&n.ready&&n.coreAlive()&&corePid(n)==pid&&token.equals(n.token)&&entry.equals(n.currentEntry)&&stream.awaitEchoes(echoes)&&n.exitCheckFailures==2);
      site.ipDelay=0;site.ipBody="{broken-json";n.lastVerified=0;n.nextExitCheckAt=0;echoes=stream.echoes.get();ipRequests=site.ipRequests.get();n.health();
      check("An invalid exit service response preserves only the previously verified route",site.ipRequests.get()>ipRequests&&n.exitFailureReason.equals("invalid-response")&&n.ready&&corePid(n)==pid&&ip.equals(n.exitIp)&&n.verifiedRouteCurrent()&&stream.awaitEchoes(echoes)&&n.exitCheckFailures==3);
      site.ipBody="{\"ip\":\"not-an-ip\"}";n.nextExitCheckAt=0;echoes=stream.echoes.get();ipRequests=site.ipRequests.get();n.health();
      check("A malformed exit IP cannot become a new successful verification",site.ipRequests.get()>ipRequests&&n.exitFailureReason.equals("invalid-response")&&n.ready&&n.lastVerified==0&&ip.equals(n.exitIp)&&n.verifiedRouteCurrent()&&stream.awaitEchoes(echoes));
      site.ipBody=null;site.ipStatus=503;echoes=stream.echoes.get();boolean accepted=awaitNetworkCallback(n,true);
      check("Send preflight reports unavailable verification without closing an already verified WSS",!accepted&&n.ready&&corePid(n)==pid&&token.equals(n.token)&&stream.awaitEchoes(echoes));
      echoes=stream.echoes.get();accepted=awaitNetworkCallback(n,false);
      check("Explicit exit verification reports failure while the existing verified tunnel continues",!accepted&&n.ready&&n.verifiedRouteCurrent()&&entry.equals(n.currentEntry)&&stream.awaitEchoes(echoes));
      site.ipStatus=200;n.nextExitCheckAt=0;n.health();
      check("A recovered exit service renews proof and resets the retry state",n.lastVerified>=verified&&n.exitCheckFailures==0&&n.nextExitCheckAt==0&&n.verifiedRouteCurrent()&&stream.failure==null);
      check("All temporary verification faults retain one WebSocket and one core generation",site.webSocketConnections.get()==1&&corePid(n)==pid&&token.equals(n.token)&&entry.equals(n.currentEntry)&&n.proxyPort==port&&ip.equals(n.exitIp));
      String previousToken=n.token;n.token="synthetic-unverified-generation";boolean wrongToken=n.verifiedRouteCurrent();n.token=previousToken;
      String previousFingerprint=n.fingerprint;n.fingerprint="synthetic-unverified-exit";boolean wrongExit=n.verifiedRouteCurrent();n.fingerprint=previousFingerprint;
      int previousController=n.controllerPort;n.controllerPort=previousController+1;boolean wrongController=n.verifiedRouteCurrent();n.controllerPort=previousController;
      int previousProxy=n.proxyPort;n.proxyPort=previousProxy+1;boolean wrongProxy=n.verifiedRouteCurrent();n.proxyPort=previousProxy;
      check("Exit receipts reject changed core identity exit identity or listener ports",!wrongToken&&!wrongExit&&!wrongController&&!wrongProxy&&n.verifiedRouteCurrent());
      n.selectNow(entry.equals("Entry|slow")?"Entry|fast":"Entry|slow");
      check("An actual entry change invalidates the previous route's verification receipt",!n.verifiedRouteCurrent());
      site.ipStatus=503;accepted=awaitNetworkCallback(n,false);
      check("An unverified changed route fails closed when the exit service is unavailable",!accepted&&!n.ready&&!n.coreAlive()&&stream.awaitClosed());
    }finally{site.ipStatus=200;site.ipDelay=0;site.ipBody=null;site.ip="203.0.113.8";plain.probeStatus=204;NetworkCatalog.put(n.settings,"entryMode",mode);}
    File unverifiedRoot=new File(getNoBackupFilesDir(),"network-unverified-test");TestNetwork unverified=new TestNetwork(this,site,plain,unverifiedRoot){@Override long startupSearchBudgetMs(){return 2000;}};
    try{
      check("A new core has no inherited in-memory verification receipt",!unverified.verifiedRouteCurrent());
      site.ipStatus=503;int initialExitRequests=site.ipRequests.get();CountDownLatch started=new CountDownLatch(1);final boolean[] startup={true};unverified.start((ok,message)->{startup[0]=ok;started.countDown();});
      check("First connection requires actual exit verification and never accepts an outage",started.await(20,TimeUnit.SECONDS)&&!startup[0]&&!unverified.ready&&!unverified.coreAlive()&&unverified.startupBeganAt>0&&unverified.controllerPort>0&&site.ipRequests.get()>initialExitRequests);
    }finally{site.ipStatus=200;unverified.stopNow();unverified.worker.shutdownNow();unverified.probes.shutdownNow();unverified.closers.shutdownNow();unverified.traffic.reader.shutdownNow();NativeNetwork.deletePreview(unverifiedRoot);}
    n.startNow();
    try(WebSocketStream stream=new WebSocketStream(n,site)){
      check("Cancellation fixture begins with a live verified WSS before changing the route",stream.awaitEchoes(0)&&n.verifiedRouteCurrent());
      NetworkWork work=n.beginMaintenance(n.maintenanceGeneration);
      try{if(work==null)throw new IOException("Controlled maintenance did not start");n.selectNow(n.currentEntry.equals("Entry|slow")?"Entry|fast":"Entry|slow");n.cancelMaintenance();n.health();
        check("Cancelled maintenance fails closed after an actual unverified entry change",!n.ready&&!n.coreAlive()&&!n.verifiedRouteCurrent()&&stream.awaitClosed());
      }finally{if(work!=null)n.finishMaintenance(work);}
    }
    n.startNow();
    try(WebSocketStream stream=new WebSocketStream(n,site)){
      check("Verification recovery permits a fresh real WebSocket after intentional closure",stream.awaitEchoes(0)&&n.verifiedRouteCurrent());
      site.ip="203.0.113.9";boolean accepted=awaitNetworkCallback(n,false);
      check("A confirmed exit IP mismatch still blocks recovery and closes the real WebSocket",!accepted&&n.recoveryBlocked&&!n.ready&&!n.coreAlive()&&!n.verifiedRouteCurrent()&&stream.awaitClosed());
    }finally{site.ip="203.0.113.8";site.ipStatus=200;site.ipDelay=0;site.ipBody=null;}
  }
  void regionCacheChecks()throws Exception{
    JSONObject[] first=new JSONObject[Profiles.MAX];long now=System.currentTimeMillis();
    for(int slot=0;slot<Profiles.MAX;slot++){Context context=Profiles.context(this,slot);SecretStore vault=new SecretStore(context);vault.put("exit-region",J.obj("ip","203.0.113."+(64+slot),"region","日本 · synthetic-"+slot,"at",now,"route","synthetic-region-"+slot).toString().getBytes(StandardCharsets.UTF_8));first[slot]=NetworkRegion.read(context);}
    boolean isolated=true,reused=true;
    for(int round=0;round<16;round++)for(int slot=0;slot<Profiles.MAX;slot++){JSONObject value=NetworkRegion.read(Profiles.context(this,slot));isolated&=value.optString("region").equals("日本 · synthetic-"+slot);reused&=value==first[slot];}
    check("Eight encrypted environment regions stay isolated across alternating reads",isolated);
    check("Repeated multi-window reads reuse decrypted region snapshots",reused);
    Context last=Profiles.context(this,Profiles.MAX-1);SecretStore vault=new SecretStore(last);JSONObject replacement=J.obj("ip","203.0.113.71","region","韩国 · synthetic-new","at",now,"route","synthetic-region-7");vault.put("exit-region",replacement.toString().getBytes(StandardCharsets.UTF_8));
    check("Replacing one sealed region updates only that environment",NetworkRegion.read(last).optString("region").equals("韩国 · synthetic-new")&&NetworkRegion.read(Profiles.context(this,0))==first[0]);
    if(!vault.file("exit-region").delete())throw new IOException("region fixture deletion failed");
    check("Deleting a sealed region clears its cached identity",NetworkRegion.read(last).length()==0);
    vault.put("exit-region",replacement.toString().getBytes(StandardCharsets.UTF_8));NetworkRegion.read(last);
    // The visual comparison also compiles this fixture with historical UI sources.
    // Current UI exposes the helper and must execute both unchanged assertions.
    java.lang.reflect.Method uiMetadata=null;try{uiMetadata=NetworkWorkspaceUi.class.getDeclaredMethod("readUiMetadata",Context.class,JSONArray.class);}catch(NoSuchMethodException historicalUi){}
    if(uiMetadata!=null){JSONArray list=new JSONArray();for(int slot=0;slot<Profiles.MAX;slot++)list.put(J.obj("row",J.obj("slot",slot)));
      Context queued=Profiles.context(this,6);NetworkChanges.save(queued,"external",J.obj("proxy","http://127.0.0.1:1"),"synthetic-ui-only");uiMetadata.invoke(null,this,list);
      check("Network list reads pending draft metadata on its background reader",list.optJSONObject(6).optBoolean("pendingNetwork")&&!list.optJSONObject(7).optBoolean("pendingNetwork"));
      NetworkChanges.clear(queued);uiMetadata.invoke(null,this,list);
      check("Network list refresh sees draft removal without a global pending cache",!list.optJSONObject(6).optBoolean("pendingNetwork"));
    }
    CountDownLatch complete=new CountDownLatch(1);java.util.concurrent.atomic.AtomicInteger disk=new java.util.concurrent.atomic.AtomicInteger();final boolean[] correct={true};
    runOnUiThread(()->{android.os.StrictMode.ThreadPolicy previous=android.os.StrictMode.getThreadPolicy();try{android.os.StrictMode.setThreadPolicy(new android.os.StrictMode.ThreadPolicy.Builder().detectDiskReads().detectDiskWrites().penaltyListener(Runnable::run,violation->disk.incrementAndGet()).build());for(int round=0;round<16;round++)for(int slot=0;slot<Profiles.MAX;slot++){Context context=Profiles.context(this,slot);String expected=slot==Profiles.MAX-1?"韩国 · synthetic-new":"日本 · synthetic-"+slot;correct[0]&=NetworkRegion.region(context,"203.0.113."+(64+slot)).equals(expected);NetworkRegion.readLatency(context);}}catch(Throwable error){correct[0]=false;}finally{android.os.StrictMode.setThreadPolicy(previous);complete.countDown();}});
    check("Actual Android main-thread region and cold latency reads complete",complete.await(10,TimeUnit.SECONDS)&&correct[0]);
    check("Region and latency UI snapshots cause no main-thread disk reads or writes",disk.get()==0);
    CountDownLatch coldComplete=new CountDownLatch(1);disk.set(0);final boolean[] coldOk={true};
    runOnUiThread(()->{android.os.StrictMode.ThreadPolicy previous=android.os.StrictMode.getThreadPolicy();try{synchronized(NetworkRegion.paths){NetworkRegion.paths.clear();}android.os.StrictMode.setThreadPolicy(new android.os.StrictMode.ThreadPolicy.Builder().detectDiskReads().detectDiskWrites().penaltyListener(Runnable::run,violation->disk.incrementAndGet()).build());for(int slot=0;slot<Profiles.MAX;slot++){Context context=Profiles.context(this,slot);NetworkRegion.read(context);NetworkRegion.readLatency(context);NetworkRegion.ready(context,"exit-region");NetworkRegion.ready(context,"route-latency");}}catch(Throwable error){coldOk[0]=false;}finally{android.os.StrictMode.setThreadPolicy(previous);coldComplete.countDown();}});
    check("Cold profile metadata paths resolve without Android main-thread directory access",coldComplete.await(10,TimeUnit.SECONDS)&&coldOk[0]&&disk.get()==0);
    NetworkRegion.snapshots.submit(()->{}).get(10,TimeUnit.SECONDS);boolean restored=true;for(int slot=0;slot<Profiles.MAX;slot++)restored&=NetworkRegion.read(Profiles.context(this,slot)).optString("region").equals(slot==Profiles.MAX-1?"韩国 · synthetic-new":"日本 · synthetic-"+slot);
    check("Background cold-path resolution restores the correct eight environment snapshots",restored);
  }
  /** Uses the real request worker and sealed records; only the final route operation is intercepted. */
  static final class CandidateRaceProvider extends NetworkUiProvider {
    final List<JSONObject> applied=new ArrayList<>();final CountDownLatch latestApplied=new CountDownLatch(1);final String latestProxy;int nonSavingOperations;
    CandidateRaceProvider(Context context,String latestProxy){profile=context;this.latestProxy=latestProxy;}
    @Override void operate(String id,String action,JSONObject candidate,String baseline){
      if(!"apply".equals(action)&&!"external".equals(action)){nonSavingOperations++;jobs.put(id,J.obj("done",true,"ok",true));return;}
      applied.add(J.obj("id",id,"action",action,"config",J.parse(candidate.toString())));jobs.put(id,J.obj("done",true,"ok",true));
      if(latestProxy.equals(candidate.optString("proxy")))latestApplied.countDown();
    }
  }
  void deferredCandidateRaceChecks()throws Exception{
    // The manifest starts a real provider for profile 0. Keep its pending record
    // empty and exercise the test provider in an unopened, separate private slot.
    NativeNetwork.get(this);int slot=Profiles.MAX-1;Context scope=Profiles.context(this,slot);ProfileCatalog catalog=ProfileCatalog.get(this);boolean wasCreated=catalog.item(slot).optBoolean("created");catalog.created(slot);
    String baseline=NetworkChanges.hash(scope),oldId="synthetic-deferred-old",newId="synthetic-candidate-new";
    JSONObject oldCandidate=J.obj("proxy","http://127.0.0.1:41001","requireExternalVpn",true),newCandidate=J.obj("proxy","http://127.0.0.1:41002","requireExternalVpn",true);
    NetworkChanges.save(scope,"external",oldCandidate,baseline);JSONObject queued=NetworkChanges.pending(scope);
    CandidateRaceProvider provider=new CandidateRaceProvider(scope,newCandidate.optString("proxy"));
    CountDownLatch oldWorkerFinished=new CountDownLatch(1),releaseNewWorker=new CountDownLatch(1),newWorkerFinished=new CountDownLatch(1),orchestrated=new CountDownLatch(1),inspected=new CountDownLatch(1);
    java.util.concurrent.atomic.AtomicReference<Throwable> failure=new java.util.concurrent.atomic.AtomicReference<>();
    final boolean[] oldWritten={false},newPreserved={false},savingPreserved={false},oldNotApplied={false};int generation=catalog.item(slot).optInt("generation");
    try{
      runOnUiThread(()->{try{
        provider.jobs.put(oldId,J.obj("done",false));provider.request(oldId,"external",oldCandidate,baseline,true,generation,queued.toString());
        // A's real worker posts its completion before this barrier. Keep B behind it
        // until the inspector has been placed between the two main-thread callbacks.
        provider.io.execute(()->{oldWorkerFinished.countDown();try{if(!releaseNewWorker.await(8,TimeUnit.SECONDS))failure.compareAndSet(null,new IOException("candidate race worker barrier timeout"));}catch(InterruptedException interrupted){Thread.currentThread().interrupt();failure.compareAndSet(null,interrupted);}});
        if(!oldWorkerFinished.await(6,TimeUnit.SECONDS))throw new IOException("old candidate worker did not complete");
        JSONObject storedOld=NetworkChanges.pending(scope).optJSONObject("config");oldWritten[0]=storedOld!=null&&storedOld.toString().equals(oldCandidate.toString());
        provider.jobs.put(newId,J.obj("done",false));provider.request(newId,"external",newCandidate,baseline);
        provider.request("synthetic-race-measure","measure",new JSONObject(),baseline);
        provider.main.post(()->{try{
          JSONObject stored=NetworkChanges.pending(scope).optJSONObject("config");newPreserved[0]=stored!=null&&stored.toString().equals(newCandidate.toString());
          savingPreserved[0]=provider.saving;oldNotApplied[0]=provider.applied.isEmpty();
        }catch(Throwable error){failure.compareAndSet(null,error);}finally{inspected.countDown();}});
        provider.io.execute(newWorkerFinished::countDown);releaseNewWorker.countDown();
        if(!newWorkerFinished.await(6,TimeUnit.SECONDS))throw new IOException("new candidate worker did not complete");
        // Exiting this bounded test-only runnable now releases A callback, inspector,
        // then B callback. Both sealed writes are already complete at that point.
      }catch(Throwable error){failure.compareAndSet(null,error);}finally{releaseNewWorker.countDown();orchestrated.countDown();}});
      check("Deferred callback race reaches both real encrypted candidate writes",orchestrated.await(15,TimeUnit.SECONDS)&&inspected.await(5,TimeUnit.SECONDS)&&failure.get()==null&&oldWritten[0]);
      check("An older deferred callback does not clear the newer sealed candidate",newPreserved[0]);
      check("An older deferred callback keeps the newer request saving state",savingPreserved[0]);
      check("An older deferred callback does not apply the replaced candidate",oldNotApplied[0]);
      boolean applied=provider.latestApplied.await(5,TimeUnit.SECONDS);
      check("Intervening non-saving network operations preserve the newest save ownership",provider.nonSavingOperations==1&&applied&&!provider.saving);
      check("The latest network candidate is applied once after the stale callback is ignored",applied&&provider.applied.size()==1&&newId.equals(provider.applied.get(0).optString("id"))&&newCandidate.toString().equals(provider.applied.get(0).optJSONObject("config").toString())&&!provider.saving&&NetworkChanges.pending(scope).length()==0);
    }finally{releaseNewWorker.countDown();provider.main.removeCallbacks(provider.drain);provider.io.shutdownNow();NetworkChanges.clear(scope);if(!wasCreated){android.content.ContentValues restored=new android.content.ContentValues();restored.put("created",0);catalog.getWritableDatabase().update("environments",restored,"slot=?",new String[]{String.valueOf(slot)});}}
  }
  void testTransport(HttpFixture site,HttpFixture plain,JSONObject config,String yaml)throws Exception{
    TestNetwork first=null,second=null,adopted=null;
    try{
      first=new TestNetwork(this,site,plain,true);first.startNow();JSONObject a=first.transport.call("snapshot","");
      check("Proxy data plane has an independent Android process",a.getInt("servicePid")!=android.os.Process.myPid()&&a.getInt("pid")>0);
      check("The independent service owns a live real proxy core",a.getBoolean("alive")&&first.coreAlive());int pid=a.getInt("pid"),port=first.proxyPort;
      first.transport.detach();adopted=new TestNetwork(this,site,plain,true);check("A new control client adopts the running tunnel",adopted.adoptTransport());
      JSONObject attached=adopted.transport.call("snapshot","");check("Client recreation keeps the exact core and port",attached.getInt("pid")==pid&&adopted.proxyPort==port&&adopted.startupPath.equals("service-adopted"));check("Adoption restores probe indices from the running configuration",EntrySelection.strings(adopted.api("GET","/proxies/ProbeEntry0",null,3000).optJSONArray("all")).contains(adopted.names.get(0)));check("Adoption rechecks the fixed exit",adopted.exitIp.equals("203.0.113.8")&&adopted.lastVerified>0);
      serviceExitContinuityChecks(adopted,site);
      Context one=Profiles.context(this,1);SecretStore vault=new SecretStore(one);JSONObject other=J.parse(config.toString());NetworkCatalog.put(other,"subscriptionUrl","https://synthetic.invalid/environment-one");vault.save(other);vault.put("subscription",yaml.getBytes(StandardCharsets.UTF_8));vault.put("subscription-meta",J.obj("urlHash",NativeNetwork.hash(other.getString("subscriptionUrl")),"updatedAt",System.currentTimeMillis()).toString().getBytes(StandardCharsets.UTF_8));
      second=new TestNetwork(one,site,plain,true);second.startNow();JSONObject b=second.transport.call("snapshot","");
      check("Concurrent environments own different kernels and ports",b.getInt("pid")!=pid&&second.proxyPort!=adopted.proxyPort&&b.getInt("servicePid")==a.getInt("servicePid"));
      CountDownLatch observed=new CountDownLatch(1);final JSONObject[] child={null};android.os.Messenger reply=new android.os.Messenger(new android.os.Handler(android.os.Looper.getMainLooper()){public void handleMessage(android.os.Message m){child[0]=J.parse(m.getData().getString("json"));observed.countDown();}});
      runOnUiThread(()->startActivity(new android.content.Intent(this,NetworkTransportLifecycleActivity.class).putExtra("reply",reply).addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK)));
      check("A separate environment control process observes its tunnel",observed.await(10,TimeUnit.SECONDS)&&child[0]!=null&&child[0].optInt("corePid")==b.getInt("pid")&&child[0].optInt("clientPid")!=android.os.Process.myPid());
      Thread.sleep(500);check("Killing the environment control process keeps its proxy kernel",second.transport.call("snapshot","").getInt("pid")==b.getInt("pid")&&second.coreAlive());
      android.os.Process.killProcess(pid);long deadline=android.os.SystemClock.elapsedRealtime()+5000;while(adopted.coreAlive()&&android.os.SystemClock.elapsedRealtime()<deadline)Thread.sleep(25);
      check("Actual core exit is pushed to the control client",!adopted.coreAlive()&&!adopted.ready);check("One core exiting leaves the other environment usable",second.coreAlive()&&second.verifyExit().equals("203.0.113.8"));
      adopted.startNow();JSONObject restarted=adopted.transport.call("snapshot","");Thread.sleep(250);check("Restart creates a new generation that ignores the old exit event",restarted.getInt("pid")!=pid&&!restarted.getString("generation").equals(attached.getString("generation"))&&adopted.coreAlive()&&adopted.ready);check("Restarting one tunnel keeps the other kernel and port",second.transport.call("snapshot","").getInt("pid")==b.getInt("pid")&&second.proxyPort==b.getInt("proxyPort"));
      check("A stop acknowledgement confirms the targeted core is closed",adopted.stopNow());check("Stopping one environment does not stop the other",second.coreAlive());
      android.os.Process.killProcess(b.getInt("servicePid"));deadline=android.os.SystemClock.elapsedRealtime()+5000;while(second.coreAlive()&&android.os.SystemClock.elapsedRealtime()<deadline)Thread.sleep(25);check("Service process death closes the client's network admission",!second.coreAlive()&&!second.ready);
      second.startNow();JSONObject recovered=second.transport.call("snapshot","");check("A replacement service restores and verifies the environment",recovered.getInt("servicePid")!=b.getInt("servicePid")&&recovered.getInt("pid")!=b.getInt("pid")&&second.ready&&second.exitIp.equals("203.0.113.8"));serviceMismatchCancellationChecks(second,site);check("The last tunnel stops through the service",second.stopNow()&&!second.coreAlive());
    }finally{for(TestNetwork net:new TestNetwork[]{first,second,adopted})if(net!=null){net.stopNow();net.worker.shutdownNow();net.probes.shutdownNow();net.closers.shutdownNow();net.traffic.reader.shutdownNow();}}
  }
  void serviceMismatchCancellationChecks(TestNetwork n,HttpFixture site)throws Exception{
    try(WebSocketStream stream=new WebSocketStream(n,site)){
      check("A service mismatch cancellation fixture starts from a verified live WSS",stream.awaitEchoes(0)&&n.verifiedRouteCurrent()&&n.transport.call("snapshot","").optBoolean("alive"));
      NetworkWork work=n.beginMaintenance(n.maintenanceGeneration);
      try{if(work==null)throw new IOException("Service cancellation maintenance did not start");site.ip="203.0.113.9";n.lastVerified=0;n.cancelOnMismatch=true;n.health();JSONObject stopped=n.transport.call("snapshot","");
        check("A confirmed service exit mismatch still stops the core when maintenance is concurrently cancelled",!stopped.optBoolean("alive")&&!n.ready&&!n.coreAlive()&&n.recoveryBlocked&&!n.verifiedRouteCurrent()&&stream.awaitClosed());
      }finally{n.cancelOnMismatch=false;site.ip="203.0.113.8";if(work!=null)n.finishMaintenance(work);}
    }
  }
  void serviceExitContinuityChecks(TestNetwork n,HttpFixture site)throws Exception{
    JSONObject before=n.transport.call("snapshot","");String token=n.token,entry=n.currentEntry,ip=n.exitIp,mode=n.settings.optString("entryMode");NetworkCatalog.put(n.settings,"entryMode","manual");int connections=site.webSocketConnections.get();
    try(WebSocketStream stream=new WebSocketStream(n,site)){
      String[] reasons={"http-503","timeout","invalid-response"};String[] names={"Independent network service retains the same WSS and core during exit HTTP failure","Independent network service retains the same WSS and core during a real exit timeout","Independent network service retains the same WSS and core during invalid exit response"};
      for(int fault=0;fault<reasons.length;fault++){
        site.ipStatus=fault==0?503:200;site.ipDelay=fault==1?11000:0;site.ipBody=fault==2?"{invalid-service-json":null;n.lastVerified=0;n.nextExitCheckAt=0;int requests=site.ipRequests.get(),echoes=stream.echoes.get();n.health();JSONObject after=n.transport.call("snapshot","");
        boolean same=after.optBoolean("alive");for(String field:new String[]{"pid","servicePid","generation","configuration","controllerPort","proxyPort"})same&=before.optString(field).equals(after.optString(field));
        check(names[fault],site.ipRequests.get()>requests&&reasons[fault].equals(n.exitFailureReason)&&n.ready&&n.verifiedRouteCurrent()&&same&&token.equals(n.token)&&entry.equals(n.currentEntry)&&ip.equals(n.exitIp)&&site.webSocketConnections.get()==connections+1&&stream.awaitEchoes(echoes));
      }
      site.ipStatus=200;site.ipDelay=0;site.ipBody=null;n.nextExitCheckAt=0;n.health();
      check("Independent network service renews exit proof without replacing the original WebSocket",n.verifiedRouteCurrent()&&n.lastVerified>0&&n.exitCheckFailures==0&&n.nextExitCheckAt==0&&site.webSocketConnections.get()==connections+1&&stream.failure==null&&before.optInt("pid")==n.transport.call("snapshot","").optInt("pid"));
    }finally{site.ipStatus=200;site.ipDelay=0;site.ipBody=null;site.ip="203.0.113.8";NetworkCatalog.put(n.settings,"entryMode",mode);}
  }
  SSLContext tlsContext()throws Exception{KeyStore store=KeyStore.getInstance("PKCS12");try(InputStream in=getAssets().open("network-fixture.p12")){store.load(in,"network-fixture".toCharArray());}KeyManagerFactory keys=KeyManagerFactory.getInstance(KeyManagerFactory.getDefaultAlgorithm());keys.init(store,"network-fixture".toCharArray());TrustManagerFactory trust=TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm());trust.init(store);SSLContext tls=SSLContext.getInstance("TLS");tls.init(keys.getKeyManagers(),trust.getTrustManagers(),null);return tls;}
  static abstract class LoopServer implements AutoCloseable {
    final ServerSocket listener;final SSLContext tls;final ExecutorService pool=Executors.newCachedThreadPool();final Set<Socket> sockets=ConcurrentHashMap.newKeySet();volatile boolean closed;
    LoopServer()throws IOException{this(null);}
    LoopServer(SSLContext tls)throws IOException{this.tls=tls;listener=tls==null?new ServerSocket(0,16,InetAddress.getByName("127.0.0.1")):tls.getServerSocketFactory().createServerSocket(0,16,InetAddress.getByName("127.0.0.1"));}
    int port(){return listener.getLocalPort();}
    void start(){pool.execute(()->{while(!closed)try{Socket s=listener.accept();sockets.add(s);pool.execute(()->{try{handle(s);}catch(Exception ignored){}finally{sockets.remove(s);try{s.close();}catch(Exception ignored){}}});}catch(IOException e){break;}});}
    abstract void handle(Socket s)throws Exception;
    public void close(){closed=true;try{listener.close();}catch(Exception ignored){}for(Socket s:sockets)try{s.close();}catch(Exception ignored){}pool.shutdownNow();}
  }
  static final class Socks extends LoopServer {
    final int delay;volatile int connections;Socks(int delay)throws IOException{this.delay=delay;}
    void handle(Socket client)throws Exception{
      client.setSoTimeout(12000);DataInputStream in=new DataInputStream(client.getInputStream());OutputStream out=client.getOutputStream();if(in.readUnsignedByte()!=5)return;byte[] methods=new byte[in.readUnsignedByte()];in.readFully(methods);out.write(new byte[]{5,0});out.flush();if(in.readUnsignedByte()!=5||in.readUnsignedByte()!=1)return;in.readByte();int type=in.readUnsignedByte();byte[] address=new byte[type==1?4:type==4?16:in.readUnsignedByte()];in.readFully(address);String host=type==3?new String(address,StandardCharsets.US_ASCII):InetAddress.getByAddress(address).getHostAddress();int port=in.readUnsignedShort();if(!host.equals("127.0.0.1"))return;Thread.sleep(delay);connections++;
      try(Socket upstream=new Socket(host,port)){sockets.add(upstream);out.write(new byte[]{5,0,0,1,127,0,0,1,0,0});out.flush();Future<?> back=pool.submit(()->copy(upstream,client));copy(client,upstream);back.cancel(true);sockets.remove(upstream);}
    }
    static void copy(Socket from,Socket to){try{byte[] bytes=new byte[8192];int n;while((n=from.getInputStream().read(bytes))>=0){to.getOutputStream().write(bytes,0,n);to.getOutputStream().flush();}}catch(IOException ignored){}}
  }
  static final class HttpFixture extends LoopServer {
    volatile int status=200,probeStatus=204,requests,websiteDelay,ipStatus=200,ipDelay;volatile CountDownLatch delayedRequest;volatile String ip="203.0.113.8",ipBody;volatile boolean credentialsSeen,redirectSeen;final AtomicInteger ipRequests=new AtomicInteger(),webSocketConnections=new AtomicInteger(),probeRequests=new AtomicInteger(),forcedProbeFailures=new AtomicInteger();final List<Integer> headConnections=Collections.synchronizedList(new ArrayList<>());
    HttpFixture(SSLContext tls)throws IOException{super(tls);}String url(String path){return (tls==null?"http":"https")+"://127.0.0.1:"+port()+path;}
    byte[] dnsAnswer(){byte[] q=NetworkDns.query(),answer=Arrays.copyOf(q,q.length+16);answer[2]=(byte)0x81;answer[3]=(byte)0x80;answer[7]=1;byte[] rr={(byte)0xc0,12,0,1,0,1,0,0,0,60,0,4,(byte)203,0,113,1};System.arraycopy(rr,0,answer,q.length,rr.length);return answer;}
    void handle(Socket socket)throws Exception{
      socket.setSoTimeout(15000);BufferedReader in=new BufferedReader(new InputStreamReader(socket.getInputStream(),StandardCharsets.ISO_8859_1));OutputStream out=socket.getOutputStream();String request;
      while((request=in.readLine())!=null){String[] parts=request.split(" ");if(parts.length<2)return;String method=parts[0],path=parts[1],webSocketKey="";String header;while((header=in.readLine())!=null&&!header.isEmpty()){String lower=header.toLowerCase(Locale.ROOT);if(lower.startsWith("cookie:")||lower.startsWith("authorization:"))credentialsSeen=true;if(lower.startsWith("sec-websocket-key:"))webSocketKey=header.substring(header.indexOf(':')+1).trim();}
        requests++;byte[] body=new byte[0];int code=200;String type="text/plain",extra="";
        if(path.equals("/websocket")){if(webSocketKey.isEmpty())throw new IOException("Missing WebSocket key");webSocketConnections.incrementAndGet();out.write(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: "+webSocketAccept(webSocketKey)+"\r\n\r\n").getBytes(StandardCharsets.US_ASCII));out.flush();echoWebSocket(socket.getInputStream(),out);return;}
        else if(path.startsWith("/website")){int wait=websiteDelay;if(wait>0){if(delayedRequest!=null)delayedRequest.countDown();Thread.sleep(wait);}code=status;headConnections.add(socket.getPort());if(code==302)extra="Location: "+url("/redirect")+"\r\n";}
        // A loopback HEAD can round down to 0 ms, which the real core rejects as a delay result.
        // Model a small target response time, while preserving the different entry hop delays.
        else if(path.startsWith("/probe")){probeRequests.incrementAndGet();Thread.sleep(10);code=forcedProbeFailures.getAndUpdate(left->Math.max(0,left-1))>0?503:probeStatus;}
        else if(path.startsWith("/ip")){ipRequests.incrementAndGet();int wait=ipDelay;if(wait>0)Thread.sleep(wait);code=ipStatus;body=(ipBody==null?"{\"ip\":\""+ip+"\"}":ipBody).getBytes(StandardCharsets.UTF_8);}
        else if(path.startsWith("/dns")){body=dnsAnswer();type="application/dns-message";}
        else if(path.startsWith("/redirect"))redirectSeen=true;
        String response="HTTP/1.1 "+code+" Fixture\r\nContent-Length: "+body.length+"\r\nContent-Type: "+type+"\r\nConnection: keep-alive\r\n"+extra+"\r\n";out.write(response.getBytes(StandardCharsets.US_ASCII));if(!method.equals("HEAD"))out.write(body);out.flush();
      }
    }
  }
  static String webSocketAccept(String key)throws Exception{return Base64.getEncoder().encodeToString(MessageDigest.getInstance("SHA-1").digest((key+"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").getBytes(StandardCharsets.US_ASCII)));}
  static String readHttpHeaders(InputStream in)throws IOException{
    ByteArrayOutputStream value=new ByteArrayOutputStream();int end=0;
    for(int b;(b=in.read())!=-1;){if(value.size()>=8192)throw new IOException("Fixture headers too large");value.write(b);end=(end<<8)|b;if(end==0x0d0a0d0a)return value.toString("US-ASCII");}throw new EOFException("Fixture headers ended");
  }
  static void echoWebSocket(InputStream input,OutputStream out)throws IOException{
    DataInputStream in=new DataInputStream(input);
    while(true){int first=in.read();if(first<0)return;int second=in.readUnsignedByte(),length=second&127;if((first&128)==0||(second&128)==0||length>=126)throw new IOException("Unsupported fixture WebSocket frame");int opcode=first&15;byte[] mask=new byte[4],body=new byte[length];in.readFully(mask);in.readFully(body);for(int i=0;i<body.length;i++)body[i]^=mask[i%4];if(opcode==8)return;if(opcode!=1&&opcode!=9)throw new IOException("Unexpected fixture WebSocket opcode");out.write(128|(opcode==9?10:1));out.write(body.length);out.write(body);out.flush();}
  }
  /** One genuine RFC6455 WSS stream, with no reconnection or alternate route. */
  static final class WebSocketStream implements AutoCloseable {
    final SSLSocket socket;final InputStream in;final OutputStream out;final AtomicInteger echoes=new AtomicInteger();volatile boolean running=true;volatile Throwable failure;final Thread loop;
    WebSocketStream(TestNetwork network,HttpFixture site)throws Exception{
      Socket tunnel=new Socket();tunnel.connect(new InetSocketAddress("127.0.0.1",network.proxyPort),3000);tunnel.setSoTimeout(3000);
      try{
        OutputStream connect=tunnel.getOutputStream();connect.write(("CONNECT 127.0.0.1:"+site.port()+" HTTP/1.1\r\nHost: 127.0.0.1:"+site.port()+"\r\n\r\n").getBytes(StandardCharsets.US_ASCII));connect.flush();String response=readHttpHeaders(tunnel.getInputStream());if(!response.startsWith("HTTP/1.1 200"))throw new IOException("Fixture proxy CONNECT failed");
        socket=(SSLSocket)network.trustFactory.createSocket(tunnel,"127.0.0.1",site.port(),true);socket.setSoTimeout(3000);socket.startHandshake();in=socket.getInputStream();out=socket.getOutputStream();String key="dGhlIHNhbXBsZSBub25jZQ==";
        out.write(("GET /websocket HTTP/1.1\r\nHost: 127.0.0.1:"+site.port()+"\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: "+key+"\r\nSec-WebSocket-Version: 13\r\n\r\n").getBytes(StandardCharsets.US_ASCII));out.flush();response=readHttpHeaders(in);if(!response.startsWith("HTTP/1.1 101")||!response.contains("Sec-WebSocket-Accept: "+webSocketAccept(key)))throw new IOException("Fixture WebSocket upgrade failed");
      }catch(Exception error){tunnel.close();throw error;}
      loop=new Thread(()->{try{for(int sequence=0;running;sequence++){byte[] payload=("continuity-"+sequence).getBytes(StandardCharsets.US_ASCII),mask={14,29,71,101};out.write(0x81);out.write(0x80|payload.length);out.write(mask);for(int i=0;i<payload.length;i++)out.write(payload[i]^mask[i%4]);out.flush();DataInputStream reply=new DataInputStream(in);if(reply.readUnsignedByte()!=0x81||reply.readUnsignedByte()!=payload.length)throw new IOException("Fixture WebSocket echo framing failed");byte[] received=new byte[payload.length];reply.readFully(received);if(!Arrays.equals(payload,received))throw new IOException("Fixture WebSocket echo changed");echoes.incrementAndGet();Thread.sleep(150);}}catch(Throwable error){if(running)failure=error;}},"controlled-wss-continuity");loop.setDaemon(true);loop.start();
    }
    boolean awaitEchoes(int previous)throws InterruptedException{long deadline=android.os.SystemClock.elapsedRealtime()+5000;while(echoes.get()<=previous&&failure==null&&android.os.SystemClock.elapsedRealtime()<deadline)Thread.sleep(20);return echoes.get()>previous&&failure==null;}
    boolean awaitClosed()throws InterruptedException{long deadline=android.os.SystemClock.elapsedRealtime()+5000;while(failure==null&&android.os.SystemClock.elapsedRealtime()<deadline)Thread.sleep(20);return failure!=null;}
    public void close(){running=false;try{socket.close();}catch(IOException ignored){}loop.interrupt();try{loop.join(1000);}catch(InterruptedException interrupted){Thread.currentThread().interrupt();}}
  }
}
