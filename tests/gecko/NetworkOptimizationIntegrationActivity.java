package local.pocketchat;

import android.app.Activity;
import android.content.Context;
import android.os.Bundle;
import android.util.Log;
import org.json.*;
import java.io.*;
import java.net.*;
import java.security.KeyStore;
import javax.net.ssl.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;

/** Actual Android/Mihomo with two loopback SOCKS hops. Never uses personal or public routes. */
public final class NetworkOptimizationIntegrationActivity extends Activity {
  final JSONArray checks=new JSONArray();
  void check(String name,boolean passed){JSONObject value=J.obj("name",name,"pass",passed);checks.put(value);Log.i("PocketNetworkPerformance",J.obj("kind","check","value",value).toString());if(!passed)throw new AssertionError(name);}
  @Override public void onCreate(Bundle state){super.onCreate(state);if(!getPackageName().endsWith(".test"))throw new SecurityException();new Thread(this::run,"network-optimization-fixture").start();}
  static class TestNetwork extends NativeNetwork {
    final HttpFixture site,plain;final SSLSocketFactory trustFactory;boolean busy;
    TestNetwork(Context c,HttpFixture site,HttpFixture plain){this(c,site,plain,false);}
    TestNetwork(Context c,HttpFixture site,HttpFixture plain,boolean isolated){super(c,new File(c.getNoBackupFilesDir(),isolated?"network-runtime":"network-performance-test"),false);this.site=site;this.plain=plain;trustFactory=site.tls.getSocketFactory();}
    @Override HttpURLConnection openProbeConnection(String target,int port)throws IOException{HttpURLConnection c=super.openProbeConnection(target,port);if(c instanceof HttpsURLConnection){if(!target.startsWith(site.url("/")))throw new IOException("Only controlled TLS endpoints are allowed");((HttpsURLConnection)c).setSSLSocketFactory(trustFactory);}return c;}
    @Override String websiteUrl(){return site.url("/website");}
    @Override String probeUrl(){return plain.url("/probe");}
    @Override String exitCheckUrl(){return site.url("/ip");}
    @Override boolean routeBusy(){return busy;}
    @Override boolean backgroundIdle(){return false;}
    @Override void report(String value){message=value;}
  }
  void run(){JSONObject report=J.obj("status","failed","actualAndroidExecution",true,"actualMihomoExecution",true);TestNetwork n=null;
    try(HttpFixture site=new HttpFixture(tlsContext());HttpFixture plain=new HttpFixture(null);Socks fixed=new Socks(0);Socks slow=new Socks(100);Socks fast=new Socks(5)){
      site.start();plain.start();fixed.start();slow.start();fast.start();
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
      n.busy=true;int requests=site.requests;n.runHealth();Thread.sleep(100);check("Busy maintenance makes no extra website or DNS requests",requests==site.requests&&n.ready);n.busy=false;
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
      site.ip="203.0.113.8";testTransport(site,plain,config,yaml);
      NetworkCatalog.put(report,"independentNetworkService","passed");NetworkCatalog.put(report,"status","passed");
    }catch(Throwable error){NetworkCatalog.put(report,"error",error.toString());}
    finally{if(n!=null){n.stopNow();n.worker.shutdownNow();n.probes.shutdownNow();n.closers.shutdownNow();n.traffic.reader.shutdownNow();}}
    NetworkCatalog.put(report,"checks",checks);try{J.write(new File(getFilesDir(),"network-performance-results.json"),report.toString(2));}catch(Exception ignored){}
    report.remove("checks");NetworkCatalog.put(report,"checkCount",checks.length());Log.i("PocketNetworkPerformance",report.toString());runOnUiThread(this::finish);
  }
  void testTransport(HttpFixture site,HttpFixture plain,JSONObject config,String yaml)throws Exception{
    TestNetwork first=null,second=null,adopted=null;
    try{
      first=new TestNetwork(this,site,plain,true);first.startNow();JSONObject a=first.transport.call("snapshot","");
      check("Proxy data plane has an independent Android process",a.getInt("servicePid")!=android.os.Process.myPid()&&a.getInt("pid")>0);
      check("The independent service owns a live real proxy core",a.getBoolean("alive")&&first.coreAlive());int pid=a.getInt("pid"),port=first.proxyPort;
      first.transport.detach();adopted=new TestNetwork(this,site,plain,true);check("A new control client adopts the running tunnel",adopted.adoptTransport());
      JSONObject attached=adopted.transport.call("snapshot","");check("Client recreation keeps the exact core and port",attached.getInt("pid")==pid&&adopted.proxyPort==port&&adopted.startupPath.equals("service-adopted"));check("Adoption rechecks the fixed exit",adopted.exitIp.equals("203.0.113.8")&&adopted.lastVerified>0);
      Context one=Profiles.context(this,1);SecretStore vault=new SecretStore(one);JSONObject other=J.parse(config.toString());NetworkCatalog.put(other,"subscriptionUrl","https://synthetic.invalid/environment-one");vault.save(other);vault.put("subscription",yaml.getBytes(StandardCharsets.UTF_8));vault.put("subscription-meta",J.obj("urlHash",NativeNetwork.hash(other.getString("subscriptionUrl")),"updatedAt",System.currentTimeMillis()).toString().getBytes(StandardCharsets.UTF_8));
      second=new TestNetwork(one,site,plain,true);second.startNow();JSONObject b=second.transport.call("snapshot","");
      check("Concurrent environments own different kernels and ports",b.getInt("pid")!=pid&&second.proxyPort!=adopted.proxyPort&&b.getInt("servicePid")==a.getInt("servicePid"));
      CountDownLatch observed=new CountDownLatch(1);final JSONObject[] child={null};android.os.Messenger reply=new android.os.Messenger(new android.os.Handler(android.os.Looper.getMainLooper()){public void handleMessage(android.os.Message m){child[0]=J.parse(m.getData().getString("json"));observed.countDown();}});
      runOnUiThread(()->startActivity(new android.content.Intent(this,NetworkTransportLifecycleActivity.class).putExtra("reply",reply).addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK)));
      check("A separate environment control process observes its tunnel",observed.await(10,TimeUnit.SECONDS)&&child[0]!=null&&child[0].optInt("corePid")==b.getInt("pid")&&child[0].optInt("clientPid")!=android.os.Process.myPid());
      Thread.sleep(500);check("Killing the environment control process keeps its proxy kernel",second.transport.call("snapshot","").getInt("pid")==b.getInt("pid")&&second.coreAlive());
      android.os.Process.killProcess(pid);long deadline=android.os.SystemClock.elapsedRealtime()+5000;while(adopted.coreAlive()&&android.os.SystemClock.elapsedRealtime()<deadline)Thread.sleep(25);
      check("Actual core exit is pushed to the control client",!adopted.coreAlive()&&!adopted.ready);check("One core exiting leaves the other environment usable",second.coreAlive()&&second.verifyExit().equals("203.0.113.8"));
      adopted.stopNow();check("Stopping one environment does not stop the other",second.coreAlive());second.stopNow();check("The last tunnel stops through the service",!second.coreAlive());
    }finally{for(TestNetwork net:new TestNetwork[]{first,second,adopted})if(net!=null){net.stopNow();net.worker.shutdownNow();net.probes.shutdownNow();net.closers.shutdownNow();net.traffic.reader.shutdownNow();}}
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
    volatile int status=200,requests,websiteDelay;volatile CountDownLatch delayedRequest;volatile String ip="203.0.113.8";volatile boolean credentialsSeen,redirectSeen;final List<Integer> headConnections=Collections.synchronizedList(new ArrayList<>());
    HttpFixture(SSLContext tls)throws IOException{super(tls);}String url(String path){return (tls==null?"http":"https")+"://127.0.0.1:"+port()+path;}
    byte[] dnsAnswer(){byte[] q=NetworkDns.query(),answer=Arrays.copyOf(q,q.length+16);answer[2]=(byte)0x81;answer[3]=(byte)0x80;answer[7]=1;byte[] rr={(byte)0xc0,12,0,1,0,1,0,0,0,60,0,4,(byte)203,0,113,1};System.arraycopy(rr,0,answer,q.length,rr.length);return answer;}
    void handle(Socket socket)throws Exception{
      socket.setSoTimeout(15000);BufferedReader in=new BufferedReader(new InputStreamReader(socket.getInputStream(),StandardCharsets.ISO_8859_1));OutputStream out=socket.getOutputStream();String request;
      while((request=in.readLine())!=null){String[] parts=request.split(" ");if(parts.length<2)return;String method=parts[0],path=parts[1];String header;while((header=in.readLine())!=null&&!header.isEmpty()){String lower=header.toLowerCase(Locale.ROOT);if(lower.startsWith("cookie:")||lower.startsWith("authorization:"))credentialsSeen=true;}
        requests++;byte[] body=new byte[0];int code=200;String type="text/plain",extra="";
        if(path.startsWith("/website")){int wait=websiteDelay;if(wait>0){if(delayedRequest!=null)delayedRequest.countDown();Thread.sleep(wait);}code=status;headConnections.add(socket.getPort());if(code==302)extra="Location: "+url("/redirect")+"\r\n";}
        else if(path.startsWith("/probe"))code=204;
        else if(path.startsWith("/ip"))body=("{\"ip\":\""+ip+"\"}").getBytes(StandardCharsets.UTF_8);
        else if(path.startsWith("/dns")){body=dnsAnswer();type="application/dns-message";}
        else if(path.startsWith("/redirect"))redirectSeen=true;
        String response="HTTP/1.1 "+code+" Fixture\r\nContent-Length: "+body.length+"\r\nContent-Type: "+type+"\r\nConnection: keep-alive\r\n"+extra+"\r\n";out.write(response.getBytes(StandardCharsets.US_ASCII));if(!method.equals("HEAD"))out.write(body);out.flush();
      }
    }
  }
}
