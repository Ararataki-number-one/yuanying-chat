package local.pocketchat;

import android.app.Activity;
import android.content.Context;
import android.os.Bundle;
import android.os.Build;
import android.os.SystemClock;
import android.util.Log;
import org.json.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import javax.net.ssl.*;

/** Real patched Mihomo HEAD telemetry and native request cancellation, never personal routes. */
public final class NativeProbeIntegrationActivity extends Activity {
  static final String TAG="PocketNativeProbe",USER="fixture",PASSWORD="local-only";
  final JSONArray checks=new JSONArray(),measurements=new JSONArray(),cancellations=new JSONArray(),startupSearches=new JSONArray();
  ProbeFixture runningTarget,runningUntrusted,runningStartupTarget;
  void check(String name,boolean passed){JSONObject value=J.obj("name",name,"pass",passed);checks.put(value);Log.i(TAG,J.obj("kind","check","value",value).toString());if(!passed)throw new AssertionError(name);}
  @Override public void onCreate(Bundle saved){super.onCreate(saved);if(!getPackageName().endsWith(".test"))throw new SecurityException("Only the isolated integration APK may run local probe fixtures");new Thread(this::run,"native-probe-fixture").start();}

  static final class TlsFixture {
    final SSLContext context;final String certificate;
    TlsFixture(Context owner,String asset)throws Exception{
      KeyStore store=KeyStore.getInstance("PKCS12");try(InputStream in=owner.getAssets().open(asset)){store.load(in,"network-fixture".toCharArray());}
      KeyManagerFactory keys=KeyManagerFactory.getInstance(KeyManagerFactory.getDefaultAlgorithm());keys.init(store,"network-fixture".toCharArray());
      TrustManagerFactory trust=TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm());trust.init(store);
      context=SSLContext.getInstance("TLS");context.init(keys.getKeyManagers(),trust.getTrustManagers(),null);
      String alias=store.aliases().nextElement();certificate="-----BEGIN CERTIFICATE-----\n"+Base64.getMimeEncoder(64,new byte[]{'\n'}).encodeToString(store.getCertificate(alias).getEncoded())+"\n-----END CERTIFICATE-----\n";
    }
  }
  /** Only changes controlled URLs and test CA; probe(), api(), routing and selection stay real. */
  static class ProbeNetwork extends NetworkOptimizationIntegrationActivity.TestNetwork {
    final String certificate;volatile String controlledProbeUrl="";
    ProbeNetwork(Context c,NetworkOptimizationIntegrationActivity.HttpFixture site,NetworkOptimizationIntegrationActivity.HttpFixture plain,String cert){this(c,site,plain,cert,new File(c.getNoBackupFilesDir(),"native-probe-test"));}
    ProbeNetwork(Context c,NetworkOptimizationIntegrationActivity.HttpFixture site,NetworkOptimizationIntegrationActivity.HttpFixture plain,String cert,File directory){super(c,site,plain,directory);certificate=cert;}
    @Override JSONObject config(boolean bootstrap,boolean download){JSONObject result=super.config(bootstrap,download);NetworkCatalog.put(result,"tls",J.obj("custom-certifactes",J.arr(certificate)));return result;}
    @Override String probeUrl(){return controlledProbeUrl==null||controlledProbeUrl.isEmpty()?super.probeUrl():controlledProbeUrl;}
  }
  /** URL selection and timestamps only: both production search methods execute unchanged. */
  static final class StartupNetwork extends ProbeNetwork {
    final ProbeFixture target;final ThreadLocal<String> childTarget=new ThreadLocal<>();volatile String mode="";volatile long verifiedWinnerAt;
    StartupNetwork(Context c,NetworkOptimizationIntegrationActivity.HttpFixture site,NetworkOptimizationIntegrationActivity.HttpFixture plain,String cert,ProbeFixture target){super(c,site,plain,cert,new File(c.getNoBackupFilesDir(),"native-startup-test"));this.target=target;}
    @Override RouteProbe startupProbe(String name,int index,String epoch,RecoveryRoute recovery){
      String path="winner-cleanup".equals(mode)?("Entry|winner".equals(name)?"/startup-win":"/startup-loser"):("Entry|winner".equals(name)?"/startup-cancel-a":"/startup-cancel-b");
      childTarget.set(target.url(path));try{return super.startupProbe(name,index,epoch,recovery);}finally{childTarget.remove();}
    }
    @Override String probeUrl(){String value=childTarget.get();return value==null?super.probeUrl():value;}
    @Override String verifyExit()throws Exception{String ip=super.verifyExit();if("winner-cleanup".equals(mode))verifiedWinnerAt=SystemClock.elapsedRealtime();return ip;}
  }
  /** Both authentication and destination restrictions must succeed before any relay. */
  static final class AuthSocks extends NetworkOptimizationIntegrationActivity.LoopServer {
    final String role;final Set<Integer> allowed;final AtomicInteger authenticated=new AtomicInteger(),connections=new AtomicInteger(),denied=new AtomicInteger();
    AuthSocks(String role,Integer... ports)throws IOException{this.role=role;allowed=new HashSet<>(Arrays.asList(ports));}
    void handle(Socket client)throws Exception{
      client.setSoTimeout(10000);DataInputStream in=new DataInputStream(client.getInputStream());OutputStream out=client.getOutputStream();
      if(in.readUnsignedByte()!=5)return;byte[] methods=new byte[in.readUnsignedByte()];in.readFully(methods);boolean auth=false;for(byte method:methods)auth|=method==2;if(!auth){denied.incrementAndGet();out.write(new byte[]{5,(byte)255});out.flush();return;}
      Thread.sleep(10);out.write(new byte[]{5,2});out.flush();if(in.readUnsignedByte()!=1)return;byte[] user=new byte[in.readUnsignedByte()];in.readFully(user);byte[] password=new byte[in.readUnsignedByte()];in.readFully(password);
      if(!USER.equals(new String(user,StandardCharsets.US_ASCII))||!PASSWORD.equals(new String(password,StandardCharsets.US_ASCII))){denied.incrementAndGet();out.write(new byte[]{1,1});out.flush();return;}
      authenticated.incrementAndGet();Thread.sleep(10);out.write(new byte[]{1,0});out.flush();if(in.readUnsignedByte()!=5||in.readUnsignedByte()!=1)return;in.readUnsignedByte();int type=in.readUnsignedByte();byte[] address=new byte[type==1?4:type==4?16:in.readUnsignedByte()];in.readFully(address);String host=type==3?new String(address,StandardCharsets.US_ASCII):InetAddress.getByAddress(address).getHostAddress();int port=in.readUnsignedShort();
      if(!"127.0.0.1".equals(host)||!allowed.contains(port)){denied.incrementAndGet();out.write(new byte[]{5,2,0,1,0,0,0,0,0,0});out.flush();return;}
      try(Socket upstream=new Socket(host,port)){sockets.add(upstream);connections.incrementAndGet();Thread.sleep(10);out.write(new byte[]{5,0,0,1,127,0,0,1,0,0});out.flush();client.setSoTimeout(0);Future<?> reverse=pool.submit(()->NetworkOptimizationIntegrationActivity.Socks.copy(upstream,client));try{NetworkOptimizationIntegrationActivity.Socks.copy(client,upstream);}finally{reverse.cancel(true);sockets.remove(upstream);}}
    }
  }
  static final class ProbeFixture extends NetworkOptimizationIntegrationActivity.LoopServer {
    final AtomicInteger serial=new AtomicInteger(),resetCount=new AtomicInteger();final List<JSONObject> wire=Collections.synchronizedList(new ArrayList<>());
    final ConcurrentHashMap<String,AtomicInteger> requests=new ConcurrentHashMap<>();final ConcurrentHashMap<String,CountDownLatch> reached=new ConcurrentHashMap<>(),nativeClosed=new ConcurrentHashMap<>();
    final ConcurrentHashMap<String,Long> closedAt=new ConcurrentHashMap<>();volatile boolean credentialsSeen;
    ProbeFixture(SSLContext tls)throws IOException{super(tls);for(String path:new String[]{"/cancel-first","/cancel-second","/cancel-java-first","/cancel-java-second","/startup-loser","/startup-cancel-a","/startup-cancel-b"}){reached.put(path,new CountDownLatch(1));nativeClosed.put(path,new CountDownLatch(1));}}
    String url(String path){return "https://127.0.0.1:"+port()+path;}
    int count(String path){AtomicInteger count=requests.get(path);return count==null?0:count.get();}
    List<Integer> connectionIds(String path){List<Integer> ids=new ArrayList<>();synchronized(wire){for(JSONObject event:wire)if(path.equals(event.optString("path"))&&event.optString("kind").equals("head"))ids.add(event.optInt("connection"));}return ids;}
    JSONArray evidence(){synchronized(wire){return new JSONArray(wire);}}
    void handle(Socket socket)throws Exception{
      int connection=serial.incrementAndGet(),requestIndex=0;socket.setSoTimeout(8000);BufferedReader in=new BufferedReader(new InputStreamReader(socket.getInputStream(),StandardCharsets.ISO_8859_1));OutputStream out=socket.getOutputStream();String line;
      while((line=in.readLine())!=null){String[] parts=line.split(" ");if(parts.length<2)return;String method=parts[0],path=parts[1],header;while((header=in.readLine())!=null&&!header.isEmpty()){String lower=header.toLowerCase(Locale.ROOT);if(lower.startsWith("cookie:")||lower.startsWith("authorization:"))credentialsSeen=true;}
        int total=requests.computeIfAbsent(path,key->new AtomicInteger()).incrementAndGet();requestIndex++;wire.add(J.obj("kind","head","path",path,"connection",connection,"requestOnConnection",requestIndex,"totalForPath",total,"method",method,"at",SystemClock.elapsedRealtime()));
        if(!"HEAD".equals(method))throw new IOException("The native telemetry fixture accepts HEAD only");
        if((path.startsWith("/cancel-")&&path.endsWith("first")&&requestIndex==1)||(path.startsWith("/cancel-")&&path.endsWith("second")&&requestIndex==2)||(path.startsWith("/startup-")&&!path.equals("/startup-win")&&requestIndex==1)){
          reached.get(path).countDown();int next=in.read();long ended=SystemClock.elapsedRealtime();wire.add(J.obj("kind","blocked-read-ended","path",path,"connection",connection,"next",next,"at",ended));if(next==-1){closedAt.put(path,ended);nativeClosed.get(path).countDown();}return;
        }
        if(path.equals("/startup-win")&&!reached.get("/startup-loser").await(5,TimeUnit.SECONDS))throw new IOException("The real losing startup request did not arrive");
        // net/http may retry an idempotent HEAD after a reused socket fails. Every
        // subsequent request for this route must fail, including a fresh retry.
        if(path.equals("/reset-second")&&total>=2){Thread.sleep(250);resetCount.incrementAndGet();wire.add(J.obj("kind","wire-reset","path",path,"connection",connection,"waitMs",250,"at",SystemClock.elapsedRealtime()));socket.setSoLinger(true,0);return;}
        Thread.sleep(requestIndex==1?100:35);int status=path.equals("/bad-first")?403:path.equals("/bad-second")&&requestIndex==2?403:204;boolean close=path.equals("/close");
        out.write(("HTTP/1.1 "+status+" Fixture\r\nContent-Length: 0\r\nConnection: "+(close?"close":"keep-alive")+"\r\n\r\n").getBytes(StandardCharsets.US_ASCII));out.flush();wire.add(J.obj("kind","response","path",path,"connection",connection,"status",status,"close",close,"at",SystemClock.elapsedRealtime()));if(close)return;
      }
    }
  }
  static final class ProbeCall {
    final int status;final JSONObject body;final long wallMs;
    ProbeCall(int status,JSONObject body,long wallMs){this.status=status;this.body=body;this.wallMs=wallMs;}
  }
  String path(String target){return "/proxies/FixedExit/delay?timeout=6000&expected=204&url="+URLEncoder.encode(target,StandardCharsets.UTF_8);}
  ProbeCall measure(ProbeNetwork n,String target)throws Exception{
    long start=SystemClock.elapsedRealtime();HttpURLConnection c=(HttpURLConnection)new URL("http://127.0.0.1:"+n.controllerPort+path(target)).openConnection(Proxy.NO_PROXY);c.setRequestProperty("Authorization","Bearer "+n.token);c.setConnectTimeout(3000);c.setReadTimeout(9000);c.setInstanceFollowRedirects(false);
    try{int status=c.getResponseCode();try(InputStream input=status<400?c.getInputStream():c.getErrorStream()){JSONObject body=J.parse(input==null?"{}":J.text(input,16384));return new ProbeCall(status,body,SystemClock.elapsedRealtime()-start);}}finally{c.disconnect();}
  }
  int pid(ProbeNetwork n)throws Exception{return Integer.parseInt(new String(java.nio.file.Files.readAllBytes(new File(n.root,"core.pid").toPath()),StandardCharsets.US_ASCII).trim());}
  String installedCoreSha256()throws Exception{
    MessageDigest digest=MessageDigest.getInstance("SHA-256");byte[] buffer=new byte[65536];File binary=new File(getApplicationInfo().nativeLibraryDir,"libmihomo.so");
    try(InputStream input=new FileInputStream(binary)){for(int read;(read=input.read(buffer))!=-1;)digest.update(buffer,0,read);}
    StringBuilder hex=new StringBuilder(64);for(byte value:digest.digest()){hex.append(Character.forDigit((value>>>4)&15,16));hex.append(Character.forDigit(value&15,16));}return hex.toString();
  }
  JSONObject identity(ProbeNetwork n)throws Exception{return J.obj("pid",pid(n),"entry",n.currentEntry,"generationHash",NativeNetwork.hash(n.token),"exitFingerprint",n.fingerprint,"exitIp",n.exitIp,"proxyPort",n.proxyPort,"controllerPort",n.controllerPort,"verified",n.verifiedRouteCurrent());}
  void sameRoute(String stage,JSONObject original,ProbeNetwork n,NetworkOptimizationIntegrationActivity.WebSocketStream stream,NetworkOptimizationIntegrationActivity.HttpFixture site,int previous)throws Exception{check(stage+" preserves the verified PID entry and fixed exit",original.toString().equals(identity(n).toString())&&n.ready&&n.coreAlive());check(stage+" keeps the original protected WebSocket responsive",stream.awaitEchoes(previous)&&stream.failure==null&&site.webSocketConnections.get()==1);}
  JSONObject trace(ProbeCall call,String name,ProbeFixture fixture,String path,AuthSocks entry,AuthSocks fixed,int entryBefore,int fixedBefore)throws Exception{
    JSONObject telemetry=call.body.optJSONObject("probe");check(name+" includes genuine schema-1 native telemetry",telemetry!=null&&telemetry.optInt("schema")==1&&telemetry.has("firstMs")&&telemetry.has("warmMs")&&telemetry.has("totalMs")&&telemetry.has("secondConnectionReused")&&telemetry.has("warmAttempted")&&telemetry.has("warmSucceeded"));
    check(name+" reports actual native dials and request attempts",telemetry.optInt("dialCount")==entry.connections.get()-entryBefore&&telemetry.optInt("dialCount")==fixed.connections.get()-fixedBefore&&telemetry.optInt("attempts")==fixture.connectionIds(path).size());
    JSONObject evidence=J.obj("name",name,"httpStatus",call.status,"response",call.body,"controllerWallMs",call.wallMs,"wireConnectionIds",new JSONArray(fixture.connectionIds(path)),"entryCircuits",entry.connections.get()-entryBefore,"fixedExitCircuits",fixed.connections.get()-fixedBefore);measurements.put(evidence);return telemetry;
  }
  void cancel(String name,ProbeNetwork n,ProbeFixture fixture,JSONObject original,NetworkOptimizationIntegrationActivity.WebSocketStream stream,NetworkOptimizationIntegrationActivity.HttpFixture site)throws Exception{
    String target=fixture.url(name);int expectedHeads=name.equals("/cancel-first")?1:2,echoes=stream.echoes.get();long cancelAt;
    try(Socket control=new Socket()){
      control.connect(new InetSocketAddress("127.0.0.1",n.controllerPort),3000);control.getOutputStream().write(("GET "+path(target)+" HTTP/1.1\r\nHost: 127.0.0.1:"+n.controllerPort+"\r\nAuthorization: Bearer "+n.token+"\r\n\r\n").getBytes(StandardCharsets.US_ASCII));control.getOutputStream().flush();
      check(name+" reaches an actual blocked native target HEAD",fixture.reached.get(name).await(5,TimeUnit.SECONDS)&&fixture.count(name)==expectedHeads);cancelAt=SystemClock.elapsedRealtime();
    }
    boolean peerClosed=fixture.nativeClosed.get(name).await(1500,TimeUnit.MILLISECONDS);long nativeElapsed=fixture.closedAt.getOrDefault(name,0L)-cancelAt;
    check(name+" cancels the native outbound socket before its 6-second timeout",peerClosed&&nativeElapsed>=0&&nativeElapsed<1500);Thread.sleep(400);
    check(name+" makes no further native HEAD after client disconnection",fixture.count(name)==expectedHeads);
    cancellations.put(J.obj("path",name,"mechanism","raw-controller-client","expectedHeads",expectedHeads,"actualHeads",fixture.count(name),"controllerClosedAt",cancelAt,"targetObservedNativeEofAt",fixture.closedAt.getOrDefault(name,0L),"nativeCloseMs",nativeElapsed,"nativeTimeoutMs",6000,"serverClosedSocketBeforeEof",false,"javaFutureCancelled",false));sameRoute(name,original,n,stream,site,echoes);
  }
  void cancelMaintenance(String name,ProbeNetwork n,ProbeFixture fixture,JSONObject original,NetworkOptimizationIntegrationActivity.WebSocketStream stream,NetworkOptimizationIntegrationActivity.HttpFixture site)throws Exception{
    int expectedHeads=name.endsWith("first")?1:2,echoes=stream.echoes.get();n.controlledProbeUrl=fixture.url(name);long generation=n.maintenanceGeneration;
    Future<NativeNetwork.ProbeResult> completed=n.worker.submit(()->{NetworkWork work=n.beginMaintenance(generation,true);if(work==null)throw new IOException("Actual maintenance did not begin");try{return n.probeMeasured("FixedExit",n.currentEntry);}finally{n.finishMaintenance(work);}});
    check(name+" reaches HEAD through real Java maintenance and the native core",fixture.reached.get(name).await(5,TimeUnit.SECONDS)&&fixture.count(name)==expectedHeads);long cancelAt=SystemClock.elapsedRealtime();n.cancelMaintenance();
    boolean peerClosed=fixture.nativeClosed.get(name).await(1500,TimeUnit.MILLISECONDS);long nativeElapsed=fixture.closedAt.getOrDefault(name,0L)-cancelAt;
    check(name+" disconnects the actual native target before the 8-second probe timeout",peerClosed&&nativeElapsed>=0&&nativeElapsed<1500);NativeNetwork.ProbeResult result=completed.get(3,TimeUnit.SECONDS);check(name+" returns a genuine failed probe without Future.cancel",result.delay<0&&!completed.isCancelled());Thread.sleep(400);
    check(name+" does not continue a second or extra native HEAD",fixture.count(name)==expectedHeads);
    cancellations.put(J.obj("path",name,"mechanism","production-maintenance","expectedHeads",expectedHeads,"actualHeads",fixture.count(name),"controllerClosedAt",cancelAt,"targetObservedNativeEofAt",fixture.closedAt.getOrDefault(name,0L),"nativeCloseMs",nativeElapsed,"nativeTimeoutMs",8000,"serverClosedSocketBeforeEof",false,"javaFutureCancelled",completed.isCancelled(),"javaProbeDelay",result.delay));sameRoute(name,original,n,stream,site,echoes);
  }
  JSONObject startupClosure(ProbeFixture target,String path,long requestedAt){long ended=target.closedAt.getOrDefault(path,0L);return J.obj("path",path,"expectedHeads",1,"actualHeads",target.count(path),"cleanupRequestedAt",requestedAt,"targetObservedNativeEofAt",ended,"nativeCloseMs",ended-requestedAt,"nativeTimeoutMs",8000,"serverClosedSocketBeforeEof",false);}
  JSONObject startupIdentity(StartupNetwork n)throws Exception{JSONObject value=identity(n);NetworkCatalog.put(value,"routeSerial",n.routeSerial);return value;}
  void startupSearchCases(TlsFixture trusted,JSONObject report)throws Exception{
    StartupNetwork n=null;
    try(NetworkOptimizationIntegrationActivity.HttpFixture site=new NetworkOptimizationIntegrationActivity.HttpFixture(trusted.context);NetworkOptimizationIntegrationActivity.HttpFixture plain=new NetworkOptimizationIntegrationActivity.HttpFixture(null);ProbeFixture target=new ProbeFixture(trusted.context);AuthSocks fixed=new AuthSocks("startup-fixed-exit",site.port(),plain.port(),target.port());AuthSocks entry=new AuthSocks("startup-entry",fixed.port())){
      runningStartupTarget=target;site.start();plain.start();target.start();fixed.start();entry.start();
      JSONObject config=J.obj("subscriptionUrl","https://synthetic.invalid/native-startup-unused-subscription","exitHost","127.0.0.1","exitPort",fixed.port(),"exitUser",USER,"exitPassword",PASSWORD,"entryMode","random","entryPool",J.arr("Entry|winner","Entry|loser"),"entry","Entry|winner");
      SecretStore vault=new SecretStore(this);vault.save(config);String yaml="proxies:\n  - {name: winner, type: socks5, server: 127.0.0.1, port: "+entry.port()+", username: "+USER+", password: "+PASSWORD+"}\n  - {name: loser, type: socks5, server: 127.0.0.1, port: "+entry.port()+", username: "+USER+", password: "+PASSWORD+"}\n";
      vault.put("subscription",yaml.getBytes(StandardCharsets.UTF_8));vault.put("subscription-meta",J.obj("urlHash",NativeNetwork.hash(config.getString("subscriptionUrl")),"updatedAt",System.currentTimeMillis()).toString().getBytes(StandardCharsets.UTF_8));getSharedPreferences("chat",0).edit().putString("lastGoodEntry","Entry|winner").commit();
      n=new StartupNetwork(this,site,plain,trusted.certificate,target);n.startNow();final StartupNetwork active=n;
      check("An independent real startup core begins with two allowed synthetic entries",n.ready&&n.coreAlive()&&n.names.size()==2&&n.names.containsAll(Arrays.asList("Entry|winner","Entry|loser"))&&n.verifiedRouteCurrent());
      JSONObject winnerBefore=startupIdentity(n);n.mode="winner-cleanup";
      Future<JSONObject> winner=n.worker.submit(()->{boolean parentPresent=active.maintenance.get()!=null;active.starting=true;try{active.firstVerifiedRoute("");return J.obj("parentMaintenancePresent",parentPresent,"parentInterrupted",Thread.currentThread().isInterrupted(),"selectedEntry",active.currentEntry,"endedAt",SystemClock.elapsedRealtime());}finally{active.starting=false;}});
      check("The actual losing startup request is blocked before winner selection",target.reached.get("/startup-loser").await(5,TimeUnit.SECONDS)&&target.count("/startup-loser")==1);
      JSONObject result=winner.get(6,TimeUnit.SECONDS);boolean closed=target.nativeClosed.get("/startup-loser").await(1500,TimeUnit.MILLISECONDS);JSONObject closure=startupClosure(target,"/startup-loser",n.verifiedWinnerAt);JSONObject winnerAfter=startupIdentity(n);
      JSONObject success=J.obj("name","winner-cleanup","mechanism","production-firstVerifiedRoute","result",result,"parentFutureCancelled",winner.isCancelled(),"before",winnerBefore,"after",winnerAfter,"winnerPath","/startup-win","winnerHeads",target.count("/startup-win"),"losers",J.arr(closure));startupSearches.put(success);
      check("Successful startup cleanup closes the actual losing native socket before timeout",closed&&n.verifiedWinnerAt>0&&closure.optLong("nativeCloseMs")>=0&&closure.optLong("nativeCloseMs")<1500);
      check("Normal startup without parent maintenance selects its real winning entry",!result.optBoolean("parentMaintenancePresent")&&"Entry|winner".equals(result.optString("selectedEntry"))&&target.count("/startup-win")==2&&!winner.isCancelled());
      check("Winner cleanup leaves the parent worker un-interrupted and the core verified",!result.optBoolean("parentInterrupted")&&winnerBefore.optInt("pid")==winnerAfter.optInt("pid")&&winnerAfter.optBoolean("verified")&&winnerAfter.optLong("routeSerial")>winnerBefore.optLong("routeSerial"));
      Thread.sleep(400);check("A cleaned losing startup candidate sends no extra HEAD",target.count("/startup-loser")==1);
      n.mode="parent-cancellation";JSONObject cancelBefore=startupIdentity(n);long generation=n.maintenanceGeneration;CountDownLatch began=new CountDownLatch(1);
      Future<JSONObject> cancelled=n.worker.submit(()->{NetworkWork parent=active.beginMaintenance(generation,true);if(parent==null)throw new IOException("Startup parent maintenance did not begin");began.countDown();try{active.firstVerifiedRoute("");return J.obj("cancelled",false);}catch(InterruptedException|InterruptedIOException expected){return J.obj("cancelled",true,"cause",expected.getClass().getSimpleName(),"endedAt",SystemClock.elapsedRealtime());}finally{active.finishMaintenance(parent);}});
      check("Parent maintenance drives both actual blocking startup requests",began.await(3,TimeUnit.SECONDS)&&target.reached.get("/startup-cancel-a").await(5,TimeUnit.SECONDS)&&target.reached.get("/startup-cancel-b").await(5,TimeUnit.SECONDS));
      long cancelAt=SystemClock.elapsedRealtime();n.cancelMaintenance();JSONObject cancelledResult=cancelled.get(3,TimeUnit.SECONDS);JSONArray closures=new JSONArray();boolean bothClosed=true;
      for(String path:new String[]{"/startup-cancel-a","/startup-cancel-b"}){bothClosed&=target.nativeClosed.get(path).await(1500,TimeUnit.MILLISECONDS);closures.put(startupClosure(target,path,cancelAt));}
      JSONObject cancelAfter=startupIdentity(n);startupSearches.put(J.obj("name","parent-cancellation","mechanism","production-firstVerifiedRoute","parentMaintenancePresent",true,"parentFutureCancelled",cancelled.isCancelled(),"result",cancelledResult,"cancelRequestedAt",cancelAt,"before",cancelBefore,"after",cancelAfter,"losers",closures));
      check("Cancelling parent search terminates the real search without cancelling its parent Future",cancelledResult.optBoolean("cancelled")&&!cancelled.isCancelled()&&cancelledResult.optLong("endedAt")-cancelAt<1500);
      check("Parent cancellation closes both actual losing native sockets before timeout",bothClosed&&closures.getJSONObject(0).optLong("nativeCloseMs")>=0&&closures.getJSONObject(0).optLong("nativeCloseMs")<1500&&closures.getJSONObject(1).optLong("nativeCloseMs")>=0&&closures.getJSONObject(1).optLong("nativeCloseMs")<1500);
      check("Cancelled startup search preserves its verified core and route",cancelBefore.toString().equals(cancelAfter.toString())&&n.ready&&n.coreAlive());Thread.sleep(400);
      check("Cancelled startup candidates send no second or extra HEAD",target.count("/startup-cancel-a")==1&&target.count("/startup-cancel-b")==1);
      check("Startup probes retain authenticated two-hop routing and no personal headers",entry.authenticated.get()==entry.connections.get()&&fixed.authenticated.get()==fixed.connections.get()&&entry.connections.get()==fixed.connections.get()&&entry.denied.get()==0&&fixed.denied.get()==0&&!target.credentialsSeen);
      NetworkCatalog.put(report,"startupWire",target.evidence());NetworkCatalog.put(report,"startupEntryCircuits",entry.connections.get());NetworkCatalog.put(report,"startupFixedExitCircuits",fixed.connections.get());
    }finally{if(n!=null){n.stopNow();n.worker.shutdownNow();n.probes.shutdownNow();n.closers.shutdownNow();n.traffic.reader.shutdownNow();}}
  }
  void run(){JSONObject report=J.obj("status","failed","actualAndroidExecution",true,"actualMihomoExecution",true,"actualAuthenticatedSocksChain",true,"probeSchema",1);ProbeNetwork n=null;
    try{
      TlsFixture trusted=new TlsFixture(this,"network-fixture.p12"),untrusted=new TlsFixture(this,"native-probe-untrusted.p12");
      try(NetworkOptimizationIntegrationActivity.HttpFixture site=new NetworkOptimizationIntegrationActivity.HttpFixture(trusted.context);NetworkOptimizationIntegrationActivity.HttpFixture plain=new NetworkOptimizationIntegrationActivity.HttpFixture(null);ProbeFixture target=new ProbeFixture(trusted.context);ProbeFixture wrongCertificate=new ProbeFixture(untrusted.context);AuthSocks fixed=new AuthSocks("fixed-exit",site.port(),plain.port(),target.port(),wrongCertificate.port());AuthSocks entry=new AuthSocks("entry",fixed.port())){
        runningTarget=target;runningUntrusted=wrongCertificate;
        site.start();plain.start();target.start();wrongCertificate.start();fixed.start();entry.start();
        JSONObject configuration=J.obj("subscriptionUrl","https://synthetic.invalid/native-probe-unused-subscription","exitHost","127.0.0.1","exitPort",fixed.port(),"exitUser",USER,"exitPassword",PASSWORD,"entryMode","manual","entryPool",J.arr("Entry|only"),"entry","Entry|only");
        SecretStore vault=new SecretStore(this);vault.save(configuration);String yaml="proxies:\n  - {name: only, type: socks5, server: 127.0.0.1, port: "+entry.port()+", username: "+USER+", password: "+PASSWORD+"}\n";vault.put("subscription",yaml.getBytes(StandardCharsets.UTF_8));vault.put("subscription-meta",J.obj("urlHash",NativeNetwork.hash(configuration.getString("subscriptionUrl")),"updatedAt",System.currentTimeMillis()).toString().getBytes(StandardCharsets.UTF_8));getSharedPreferences("chat",0).edit().putString("lastGoodEntry","Entry|only").commit();
        n=new ProbeNetwork(this,site,plain,trusted.certificate);n.startNow();NetworkCatalog.put(report,"coreSha256",installedCoreSha256());NetworkCatalog.put(report,"coreAbi",Build.SUPPORTED_ABIS[0]);NetworkCatalog.put(report,"coreVersion",n.api("GET","/version",null,3000).optString("version"));check("A real Mihomo core starts with the authenticated fixed route",n.ready&&n.coreAlive()&&n.currentEntry.equals("Entry|only")&&n.exitIp.equals("203.0.113.8")&&n.verifiedRouteCurrent());JSONObject original=identity(n);NetworkCatalog.put(report,"originalRoute",original);
        try(NetworkOptimizationIntegrationActivity.WebSocketStream stream=new NetworkOptimizationIntegrationActivity.WebSocketStream(n,site)){
          check("A protected WSS connection carries real frames before measuring",stream.awaitEchoes(0)&&site.webSocketConnections.get()==1);
          int beforeEntry=entry.connections.get(),beforeFixed=fixed.connections.get(),echoes=stream.echoes.get();ProbeCall warm=measure(n,target.url("/warm"));JSONObject telemetry=trace(warm,"keep-alive warm",target,"/warm",entry,fixed,beforeEntry,beforeFixed);
          check("Actual authenticated chain exposes first-request phases without claiming local DNS",telemetry.optInt("phaseSchema")==1&&telemetry.optLong("chainMs",-1)>=40&&telemetry.optLong("tlsMs",-1)>=0&&telemetry.optLong("responseWaitMs",-1)>=0&&telemetry.optInt("dnsMs",0)==-1);
          check("Keep-alive delay is the successful warm response alone",warm.status==200&&telemetry.optString("kind").equals("warm")&&telemetry.optBoolean("warmAttempted")&&telemetry.optBoolean("warmSucceeded")&&telemetry.optBoolean("secondConnectionReused")&&warm.body.optInt("delay")==telemetry.optInt("warmMs")&&telemetry.optInt("firstStatus")==204&&telemetry.optInt("secondStatus")==204);
          List<Integer> warmIds=target.connectionIds("/warm");check("Native Reused=true matches two actual HEADs on one socket",warmIds.size()==2&&warmIds.get(0).equals(warmIds.get(1))&&entry.connections.get()==beforeEntry+1&&fixed.connections.get()==beforeFixed+1);check("Warm delay excludes authentication and the first response",telemetry.optInt("firstMs")>telemetry.optInt("warmMs")+40&&telemetry.optInt("totalMs")>=telemetry.optInt("firstMs")+telemetry.optInt("warmMs"));sameRoute("warm measurement",original,n,stream,site,echoes);
          n.controlledProbeUrl=target.url("/warm");NativeNetwork.ProbeResult realWarm=n.probeMeasured("FixedExit",n.currentEntry);n.publishCurrentProbe(realWarm);check("The real Java probe policy publishes warm native telemetry as comparable",realWarm.delay>0&&realWarm.trace!=null&&realWarm.trace.comparable()&&realWarm.kind().equals("warm")&&n.probeSnapshot().optBoolean("comparable"));
          beforeEntry=entry.connections.get();beforeFixed=fixed.connections.get();echoes=stream.echoes.get();ProbeCall closed=measure(n,target.url("/close"));telemetry=trace(closed,"connection-close cold retest",target,"/close",entry,fixed,beforeEntry,beforeFixed);
          check("Connection-close succeeds but is explicitly a cold retest",closed.status==200&&telemetry.optString("kind").equals("cold-retest")&&telemetry.optBoolean("warmAttempted")&&telemetry.optBoolean("warmSucceeded")&&!telemetry.optBoolean("secondConnectionReused")&&closed.body.optInt("delay")==telemetry.optInt("warmMs"));List<Integer> closedIds=target.connectionIds("/close");check("Cold retest opens two genuine authenticated routes and target sockets",closedIds.size()==2&&!closedIds.get(0).equals(closedIds.get(1))&&entry.connections.get()==beforeEntry+2&&fixed.connections.get()==beforeFixed+2);sameRoute("cold retest",original,n,stream,site,echoes);
          n.controlledProbeUrl=target.url("/close");NativeNetwork.ProbeResult realCold=n.probeMeasured("FixedExit",n.currentEntry);n.publishCurrentProbe(realCold);check("The real Java probe policy preserves cold latency without ranking it as warm",realCold.delay>0&&realCold.trace!=null&&!realCold.trace.comparable()&&realCold.kind().equals("cold-retest")&&!n.probeSnapshot().optBoolean("comparable"));
          beforeEntry=entry.connections.get();beforeFixed=fixed.connections.get();echoes=stream.echoes.get();ProbeCall reset=measure(n,target.url("/reset-second"));telemetry=trace(reset,"second-response reset fallback",target,"/reset-second",entry,fixed,beforeEntry,beforeFixed);
          List<Integer> resetIds=target.connectionIds("/reset-second");check("A real second HEAD and any bounded retry wait 250 ms then reset",target.resetCount.get()>=1&&target.count("/reset-second")>=2&&target.count("/reset-second")<=3&&resetIds.get(0).equals(resetIds.get(1))&&telemetry.optInt("warmMs")>=200&&!telemetry.optBoolean("warmSucceeded")&&entry.connections.get()-beforeEntry==fixed.connections.get()-beforeFixed&&entry.connections.get()-beforeEntry<=2);check("Failed repeat returns the first response instead of cumulative failed waiting",reset.status==200&&telemetry.optString("kind").equals("cold-fallback")&&telemetry.optString("warmError").equals("transport")&&reset.body.optInt("delay")==telemetry.optInt("firstMs")&&telemetry.optInt("totalMs")>=telemetry.optInt("firstMs")+telemetry.optInt("warmMs")&&reset.body.optInt("delay")<telemetry.optInt("totalMs")-150);sameRoute("reset fallback",original,n,stream,site,echoes);
          cancel("/cancel-first",n,target,original,stream,site);cancel("/cancel-second",n,target,original,stream,site);
          cancelMaintenance("/cancel-java-first",n,target,original,stream,site);cancelMaintenance("/cancel-java-second",n,target,original,stream,site);
          echoes=stream.echoes.get();ProbeCall invalid=measure(n,target.url("/bad-first"));JSONObject invalidProbe=invalid.body.optJSONObject("probe");check("An unexpected first HTTP status cannot become a healthy 204 measurement",invalidProbe!=null&&invalidProbe.optInt("schema")==1&&invalidProbe.optInt("firstStatus")==403&&invalidProbe.optString("error").equals("unexpected-status"));JSONObject state=n.api("GET","/proxies/FixedExit",null,3000).getJSONObject("extra").getJSONObject(target.url("/bad-first"));check("Unexpected status preserves the core's failed endpoint history",!state.optBoolean("alive")&&state.getJSONArray("history").getJSONObject(state.getJSONArray("history").length()-1).optInt("delay")==0);measurements.put(J.obj("name","bad-first-status","httpStatus",invalid.status,"response",invalid.body));sameRoute("unexpected status rejection",original,n,stream,site,echoes);
          n.controlledProbeUrl=target.url("/bad-first");check("The real Java probe rejects an unexpected native HTTP status",n.probeMeasured("FixedExit",n.currentEntry).delay<0&&n.ready&&n.verifiedRouteCurrent());
          echoes=stream.echoes.get();ProbeCall badTls=measure(n,wrongCertificate.url("/warm"));JSONObject tlsProbe=badTls.body.optJSONObject("probe");check("An untrusted TLS certificate remains a native first-request failure",badTls.status>=400&&!badTls.body.has("delay")&&tlsProbe!=null&&tlsProbe.optInt("schema")==1&&tlsProbe.optInt("firstMs")==-1&&wrongCertificate.count("/warm")==0);measurements.put(J.obj("name","untrusted-tls","httpStatus",badTls.status,"response",badTls.body));sameRoute("TLS rejection",original,n,stream,site,echoes);
          n.controlledProbeUrl=wrongCertificate.url("/warm");check("The real Java probe cannot turn a TLS failure into measured latency",n.probeMeasured("FixedExit",n.currentEntry).delay<0&&n.ready&&wrongCertificate.count("/warm")==0);
          check("Probe failures do not rotate the entry or replace the protected WebSocket",site.webSocketConnections.get()==1&&stream.failure==null&&original.toString().equals(identity(n).toString()));check("Both SOCKS layers enforce credentials and only loopback allowed destinations",entry.authenticated.get()==entry.connections.get()&&fixed.authenticated.get()==fixed.connections.get()&&entry.connections.get()>5&&fixed.connections.get()==entry.connections.get()&&entry.denied.get()==0&&fixed.denied.get()==0);check("Native website probes send no personal Cookie or Authorization",!target.credentialsSeen&&!wrongCertificate.credentialsSeen);
          NetworkCatalog.put(report,"finalRoute",identity(n));NetworkCatalog.put(report,"webSocketConnections",site.webSocketConnections.get());NetworkCatalog.put(report,"webSocketEchoes",stream.echoes.get());NetworkCatalog.put(report,"entryCircuits",entry.connections.get());NetworkCatalog.put(report,"fixedExitCircuits",fixed.connections.get());NetworkCatalog.put(report,"nativeWire",target.evidence());NetworkCatalog.put(report,"untrustedTlsWire",wrongCertificate.evidence());
        }
      }
      n.stopNow();startupSearchCases(trusted,report);
      NetworkCatalog.put(report,"status","passed");
    }catch(Throwable error){NetworkCatalog.put(report,"error",error.toString());Log.e(TAG,"Native probe fixture failed",error);}
    finally{if(runningTarget!=null)NetworkCatalog.put(report,"nativeWire",runningTarget.evidence());if(runningUntrusted!=null)NetworkCatalog.put(report,"untrustedTlsWire",runningUntrusted.evidence());if(runningStartupTarget!=null)NetworkCatalog.put(report,"startupWire",runningStartupTarget.evidence());if(n!=null){n.stopNow();n.worker.shutdownNow();n.probes.shutdownNow();n.closers.shutdownNow();n.traffic.reader.shutdownNow();}}
    NetworkCatalog.put(report,"checks",checks);NetworkCatalog.put(report,"measurements",measurements);NetworkCatalog.put(report,"cancellations",cancellations);NetworkCatalog.put(report,"startupSearches",startupSearches);try{File candidate=new File(getFilesDir(),"native-probe-results.json.tmp");J.write(candidate,report.toString(2));if(!candidate.renameTo(new File(getFilesDir(),"native-probe-results.json")))throw new IOException("Could not publish complete native probe report");}catch(Exception error){Log.e(TAG,"Could not persist complete native probe evidence",error);}Log.i(TAG,J.obj("kind","complete","status",report.optString("status"),"checkCount",checks.length(),"error",report.optString("error")).toString());runOnUiThread(this::finish);
  }
}
