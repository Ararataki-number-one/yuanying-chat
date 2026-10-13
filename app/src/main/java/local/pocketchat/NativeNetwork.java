package local.pocketchat;

import android.content.Context;
import android.os.Handler;
import android.os.Looper;
import org.json.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.*;

class NativeNetwork {
  interface Callback{void done(boolean ok,String message);}
  private static NativeNetwork instance;
  static synchronized NativeNetwork get(Context c){if(instance==null)instance=new NativeNetwork(c);return instance;}
  final Context context;final SecretStore secrets;final Handler main=new Handler(Looper.getMainLooper());
  final ScheduledExecutorService worker=Executors.newSingleThreadScheduledExecutor();final ExecutorService probes=Executors.newFixedThreadPool(4);final ExecutorService closers=Executors.newFixedThreadPool(4);final ThreadLocal<NetworkWork> maintenance=new ThreadLocal<>();volatile NetworkWork backgroundWork;volatile long maintenanceGeneration=0,lastMaintenanceAt=0;
  final NetworkTransportClient transport;final RouteQuality quality,websiteQuality;final NetworkDns dns;volatile JSONObject websiteResult=new JSONObject();volatile int webProbePort;int scanCursor;volatile String activeDns="";final TrafficMonitor traffic;volatile boolean measuringLatency=false;volatile long lastManualProbe=-5000;final File root;volatile boolean ready=false,starting=false;volatile String message="未连接",currentEntry="",exitIp="",observedExitIp="";volatile JSONArray results=new JSONArray();
  volatile boolean recoveryBlocked=false;boolean restartQueued=false;final List<Callback> startWaiters=new ArrayList<>();volatile long lastVerified=0,lastObserved=0;
  java.lang.Process process;JSONObject settings;volatile int controllerPort,proxyPort;int failures;volatile String token="";String fingerprint="";List<String> names=new ArrayList<>();long lastScan=0;int totalEntries=0;volatile long startupDuration=0;volatile String startupPath="";volatile long startupBeganAt=0,coreDuration=0,providerDuration=0,exitCheckDuration=0;volatile boolean startupCached=false;
  static final String MEASUREMENT_PROFILE="unified-delay-trace-v2";volatile long lastProbeDuration=0,lastProbeDurationAt=0;volatile String lastProbeEntry="";
  final java.util.concurrent.atomic.AtomicLong probeSequence=new java.util.concurrent.atomic.AtomicLong();final ThreadLocal<ProbeTicket> probeTicket=new ThreadLocal<>();volatile ProbeResult currentProbe;
  static final class ProbeTicket {final LatencyProbePolicy.Binding binding;LatencyProbePolicy.Trace trace;long duration;ProbeTicket(LatencyProbePolicy.Binding binding){this.binding=binding;}}
  static final class ProbeResult {
    final LatencyProbePolicy.Binding binding;final int delay;final long at,duration;final LatencyProbePolicy.Trace trace;
    ProbeResult(LatencyProbePolicy.Binding binding,int delay,long at,long duration,LatencyProbePolicy.Trace trace){this.binding=binding;this.delay=delay;this.at=at;this.duration=duration;this.trace=trace;}
    String kind(){return trace==null?"unknown":trace.kind;}
    JSONObject publicSummary(){return J.obj("schema",1,"measurement",binding.measurement,"routeSerial",binding.route,"at",at,"delay",delay,"kind",kind(),"comparable",trace!=null&&trace.comparable(),"probe",trace==null?new JSONObject():new JSONObject(trace.values()));}
  }
  ProbeResult probeMeasured(String proxy,String exactEntry){
    LatencyProbePolicy.Binding binding=new LatencyProbePolicy.Binding(proxy,exactEntry,token,routeSerial,probeSequence.incrementAndGet(),controllerPort);ProbeTicket ticket=new ProbeTicket(binding);probeTicket.set(ticket);
    try{int delay=probe(proxy);if(!binding.matches(token,routeSerial,controllerPort,currentEntry)||Thread.currentThread().isInterrupted())delay=-1;return new ProbeResult(binding,delay,System.currentTimeMillis(),ticket.duration,delay>0?ticket.trace:null);}finally{probeTicket.remove();}
  }
  static LatencyProbePolicy.Trace probeTrace(JSONObject value,int delay){
    if(value==null)return null;Map<String,Object> safe=new LinkedHashMap<>();for(String key:LatencyProbePolicy.FIELDS)if(value.has(key))safe.put(key,value.opt(key));return LatencyProbePolicy.parse(safe,delay);
  }
  boolean probeCurrent(ProbeResult result){return result!=null&&result.binding.matches(token,routeSerial,controllerPort,currentEntry);}
  synchronized void publishCurrentProbe(ProbeResult result){
    if(!probeCurrent(result)||!result.binding.current||currentProbe!=null&&currentProbe.binding.measurement>result.binding.measurement)return;
    currentProbe=result;latencyReading=J.obj("entry",result.binding.entry,"generation",result.binding.epoch,"routeSerial",result.binding.route,"measurement",result.binding.measurement,"at",result.at,"delay",result.delay,"kind",result.kind(),"probe",result.trace==null?new JSONObject():new JSONObject(result.trace.values()));
    lastProbeEntry=result.binding.entry;lastProbeDuration=result.duration;lastProbeDurationAt=result.at;
  }
  private String probeRouteEpoch="",cachedProbeRoute="";private long probeRouteSerial=-1;private int probeRouteController=-1;
  synchronized String probeRouteKey(){String epoch=token;long serial=routeSerial;int controller=controllerPort;if(!epoch.equals(probeRouteEpoch)||serial!=probeRouteSerial||controller!=probeRouteController){probeRouteEpoch=epoch;probeRouteSerial=serial;probeRouteController=controller;cachedProbeRoute=hash(epoch+"|"+serial+"|"+controller);}return cachedProbeRoute;}
  void recordProbe(ProbeResult result,long now){if(probeCurrent(result))quality.record(result.binding.entry,result.delay,now,result.kind(),result.trace==null?new JSONObject():new JSONObject(result.trace.values()),J.obj("route",hash(result.binding.epoch+"|"+result.binding.route+"|"+result.binding.controller),"measurement",result.binding.measurement,"origin",result.binding.current?"current":"candidate"));}
  /** Already sanitized immutable values; no controller secret, URL, node or raw error. */
  JSONObject probeSnapshot(){ProbeResult result=currentProbe;if(!probeCurrent(result)||!result.binding.current)return new JSONObject();JSONObject value=result.publicSummary();return probeCurrent(result)?value:new JSONObject();}
  volatile boolean latencyRefreshQueued;volatile JSONObject latencyReading=new JSONObject();long latencyRefreshAttempted=-60000;String latencyRefreshRoute="";
  // A detector outage can retain connections only for this exact, previously
  // verified route and core lifetime. A saved IP alone is never admission proof.
  volatile ExitRouteReceipt verifiedRoute;volatile long routeSerial,nextExitCheckAt;volatile int exitCheckFailures;
  volatile NetworkHealthPolicy.Admission admission=NetworkHealthPolicy.Admission.BLOCKED;
  volatile String healthStatus="unknown";volatile int healthTargetCode;volatile long healthObservedAt;
  static final class ExitRouteReceipt {
    final String fingerprint,token,entry,configuration,generation;final long serial;final int controller,proxy,pid,servicePid;final java.lang.Process process;
    ExitRouteReceipt(NativeNetwork n,JSONObject state){fingerprint=n.fingerprint;token=n.token;entry=n.currentEntry;serial=n.routeSerial;controller=n.controllerPort;proxy=n.proxyPort;process=n.process;configuration=state==null?"":state.optString("configuration");generation=state==null?"":state.optString("generation");pid=state==null?0:state.optInt("pid");servicePid=state==null?0:state.optInt("servicePid");}
    boolean matches(NativeNetwork n,JSONObject state){
      if(fingerprint.isEmpty()||token.isEmpty()||entry.isEmpty()||serial!=n.routeSerial||!fingerprint.equals(n.fingerprint)||!token.equals(n.token)||!entry.equals(n.currentEntry)||controller!=n.controllerPort||proxy!=n.proxyPort)return false;
      if(n.transport==null)return process!=null&&process==n.process&&process.isAlive();
      return state!=null&&state.optBoolean("alive")&&!generation.isEmpty()&&pid>1&&servicePid>1&&generation.equals(state.optString("generation"))&&pid==state.optInt("pid")&&servicePid==state.optInt("servicePid")&&configuration.equals(state.optString("configuration"))&&controller==state.optInt("controllerPort")&&proxy==state.optInt("proxyPort");
    }
  }
  static final String PROBE="https://www.gstatic.com/generate_204";
  NativeNetwork(Context c){this(c,new File(c.getNoBackupFilesDir(),"network-runtime"),true);}
  NativeNetwork(Context c,File directory,boolean monitor){context=c.getApplicationContext();quality=new RouteQuality(context);websiteQuality=new RouteQuality(context,"website-quality");dns=new NetworkDns(context);traffic=new TrafficMonitor(this);secrets=new SecretStore(c);root=directory;root.mkdirs();transport=root.getName().equals("network-runtime")?new NetworkTransportClient(context,this::transportChanged):null;if(monitor)worker.scheduleWithFixedDelay(()->runHealth(),30,30,TimeUnit.SECONDS);}
  static void validateSourceUrl(String url,String role)throws Exception{URI u=new URI(url);if(!"https".equals(u.getScheme())||u.getHost()==null||u.getUserInfo()!=null)throw new IOException("请填写 HTTPS 格式的"+role+"订阅地址");}
  static boolean subscribedExit(JSONObject s){return "subscription".equals(s.optString("exitSource"));}
  static void validate(JSONObject s)throws Exception{
    validateSourceUrl(s.optString("subscriptionUrl"),"入口");
    if(subscribedExit(s)){validateSourceUrl(s.optString("exitSubscriptionUrl"),"出口");if(s.optString("exitSubscriptionId").isEmpty()||!s.optString("exitNodeKey").matches("[0-9a-f]{64}")||!s.optString("exitNodeName").startsWith("Exit|")||s.optString("exitNodeName").length()<=5)throw new IOException("请选择出口订阅中的固定 SOCKS5 节点");return;}
    String host=s.optString("exitHost");if(host.isEmpty()||host.matches(".*[\\s/\\\\@].*"))throw new IOException("请填写有效的固定出口地址");int port=s.optInt("exitPort");if(port<1||port>65535)throw new IOException("固定出口端口应为 1–65535");
  }
  static String exitIdentity(JSONObject s){return subscribedExit(s)?hash("subscription|"+s.optString("exitSubscriptionId")+"|"+s.optString("exitNodeKey")):NetworkCatalog.exitId(s);}
  /** Legacy entry caches remain readable; new snapshots bind bytes and source address. */
  static boolean sourceCacheMatches(JSONObject s,String role,JSONObject meta,byte[] bytes){
    boolean entry=NetworkCatalog.ENTRY.equals(role);String prefix=entry?"entry":"exit",url=s.optString(entry?"subscriptionUrl":"exitSubscriptionUrl"),id=s.optString(prefix+"SubscriptionId");
    if(bytes==null||bytes.length==0||!hash(url).equals(meta.optString("urlHash")))return false;
    if(meta.has("payloadHash")&&!NetworkSourceSelection.payloadHash(bytes).equals(meta.optString("payloadHash")))return false;
    if(meta.has("role")&&!role.equals(meta.optString("role")))return false;
    if(!id.isEmpty()&&(!id.equals(meta.optString("sourceId"))||!role.equals(meta.optString("role"))||!url.equals(meta.optString("sourceUrl"))||!meta.has("payloadHash")||!meta.has("addressRevision")||meta.optLong("addressRevision")<1||meta.optLong("addressRevision")!=s.optLong(prefix+"SubscriptionAddressRevision")||!NetworkSourceSelection.snapshotGeneration(role,id,meta.optLong("addressRevision"),bytes).equals(meta.optString("cacheGeneration"))))return false;
    return entry||!id.isEmpty()&&meta.has("payloadHash");
  }
  JSONObject sourceMeta(String slot)throws Exception{byte[] bytes=secrets.get(slot);return bytes==null?new JSONObject():J.parse(new String(bytes,StandardCharsets.UTF_8));}
  void prepareExitSnapshot()throws Exception{
    File file=new File(root,"exit-subscription.yaml");if(!subscribedExit(settings)){if(file.exists()&&!file.delete())throw new IOException("旧出口缓存无法清理");return;}
    byte[] bytes=secrets.get("exit-subscription");if(!sourceCacheMatches(settings,NetworkCatalog.EXIT,sourceMeta("exit-subscription-meta"),bytes))throw new IOException("固定出口缓存与所选订阅不一致，请重新保存网络");
    try(FileOutputStream out=new FileOutputStream(file)){out.write(bytes);}
  }
  void report(String text){message=text;ChatSession s=ChatSession.peek();WindowNetworkState.save(context,s,this);if(s!=null)main.post(()->s.networkStatus(text,ready));}
  String proxy(){return "http://127.0.0.1:"+proxyPort;}
  static int freePort()throws Exception{try(ServerSocket s=new ServerSocket(0,0,InetAddress.getByName("127.0.0.1"))){return s.getLocalPort();}}
  boolean coreAlive(){return transport!=null?transport.alive():process!=null&&process.isAlive();}
  void transportChanged(JSONObject state){if(!state.optBoolean("alive")){verifiedRoute=null;admission=NetworkHealthPolicy.Admission.BLOCKED;if(ready){ready=false;cancelMaintenance();report("独立网络服务暂时退出，请重新连接");}}}
  static class ExitMismatch extends IOException{ExitMismatch(){super("出口 IP 与保存记录不一致，连接已停止；请检查固定出口设置");}}
  static final class ExitCheckUnavailable extends IOException {
    final String reason;
    ExitCheckUnavailable(String reason,Throwable cause){super("出口核验服务暂时不可用，请稍后再试",cause);this.reason=reason;}
  }
  void invalidateVerifiedRoute(){verifiedRoute=null;admission=NetworkHealthPolicy.Admission.BLOCKED;routeSerial++;exitCheckFailures=0;nextExitCheckAt=0;failures=0;healthStatus="unknown";healthTargetCode=0;healthObservedAt=0;}
  /** Nonblocking read for UI/fast admission; worker retention checks fresh IPC state. */
  NetworkHealthPolicy.Admission connectionAdmission(){ExitRouteReceipt receipt=verifiedRoute;return ready&&!recoveryBlocked&&receipt!=null&&receipt.matches(this,transport==null?null:transport.state)?admission:NetworkHealthPolicy.Admission.BLOCKED;}
  ExitRouteReceipt exitRouteReceipt()throws Exception{JSONObject state=transport==null?null:transport.call("snapshot","");ExitRouteReceipt receipt=new ExitRouteReceipt(this,state);if(!receipt.matches(this,state))throw new IOException("内置网络实例已变化，请重新连接");return receipt;}
  /** Worker-only: fresh service state prevents stale IPC liveness retaining a dead core. */
  boolean verifiedRouteCurrent(){ExitRouteReceipt receipt=verifiedRoute;if(!ready||recoveryBlocked||receipt==null)return false;try{JSONObject state=transport==null?null:transport.call("snapshot","");return verifiedRoute==receipt&&ready&&receipt.matches(this,state);}catch(Exception unavailable){return false;}}
  boolean cancelledVerifiedRouteCurrent(){
    // NetworkWork's cancellation interrupts this worker. It already owns the
    // cancelled flag; clear that interrupt before checking actual service life.
    Thread.interrupted();return verifiedRouteCurrent();
  }
  static long exitRetryDelayMs(int failures){return failures<=3?60000L<<(Math.max(1,failures)-1):15*60000L;}
  boolean retainVerifiedRoute(Exception failure){
    boolean detectorUnavailable=failure instanceof ExitCheckUnavailable;
    NetworkHealthPolicy.Admission result=NetworkHealthPolicy.afterFailure(detectorUnavailable,detectorUnavailable&&verifiedRouteCurrent());
    if(!result.usable())return false;admission=result;
    exitCheckFailures=Math.min(4,exitCheckFailures+1);nextExitCheckAt=android.os.SystemClock.elapsedRealtime()+exitRetryDelayMs(exitCheckFailures);
    report("出口核验暂不可用 · 已核验的原线路保持连接");return true;
  }
  void start(Callback callback){startOperation(callback,0);}
  void restart(Callback callback){recoveryBlocked=false;startOperation(callback,2);}
  void recover(Callback callback){if(recoveryBlocked){main.post(()->callback.done(false,message));return;}startOperation(callback,1);}
  synchronized void startOperation(Callback callback,int mode){if(mode==0&&connectionAdmission().usable()&&coreAlive()){main.post(()->callback.done(true,message));return;}startWaiters.add(callback);if(starting){if(mode==2)restartQueued=true;return;}starting=true;cancelMaintenance();worker.execute(()->runStartOperation(mode));
  }
  void runStartOperation(int mode){boolean ok=false;try{if(mode==1&&recoveryBlocked)throw new ExitMismatch();if(mode==1&&ready&&coreAlive()&&configurationMatches()){report("正在检查代理链与固定出口…");try{verifyExit();ok=true;report("手机独立网络已连接 · "+display(currentEntry));}catch(ExitMismatch e){throw e;}catch(ExitCheckUnavailable unavailable){throw unavailable;}catch(Exception transientFailure){ok=false;}}
      if(!ok&&mode!=2)ok=adoptTransport();
      if(!ok){stopNow();startNow();ok=true;}
    }catch(Exception e){ok=retainVerifiedRoute(e);if(!ok){stopNow();if(e instanceof ExitMismatch)recoveryBlocked=true;report(e instanceof IOException&&e.getMessage()!=null?e.getMessage():"应用网络连接失败，请检查节点与固定出口");}}
    final boolean success=ok;final String detail=message;final List<Callback> callbacks;synchronized(this){if(restartQueued){restartQueued=false;worker.execute(()->runStartOperation(2));return;}starting=false;callbacks=new ArrayList<>(startWaiters);startWaiters.clear();}main.post(()->{for(Callback cb:callbacks)cb.done(success,detail);});
  }
  static String transportFingerprint(JSONObject s){List<String> pool=EntrySelection.strings(s.optJSONArray("entryPool"));Collections.sort(pool);JSONObject route=J.obj("subscription",s.optString("subscriptionUrl"),"host",s.optString("exitHost"),"port",s.optInt("exitPort"),"user",s.optString("exitUser"),"password",s.optString("exitPassword"),"mode",s.optString("entryMode"),"pool",new JSONArray(pool),"entry",s.optString("entry"));if(s.has("entrySubscriptionId")||subscribedExit(s)){for(String key:new String[]{"entrySubscriptionId","entrySubscriptionAddressRevision","entryNodeKey","exitSource","exitSubscriptionId","exitSubscriptionUrl","exitSubscriptionAddressRevision","exitNodeKey","exitNodeName"})NetworkCatalog.put(route,key,s.opt(key));List<String> keys=NetworkSourceSelection.keys(s.optJSONArray("entryPoolKeys"));Collections.sort(keys);NetworkCatalog.put(route,"entryPoolKeys",new JSONArray(keys));JSONObject refs=s.optJSONObject("entryPoolNodeKeys"),ordered=new JSONObject();for(String name:pool)if(refs!=null)NetworkCatalog.put(ordered,name,refs.optString(name));NetworkCatalog.put(route,"entryPoolNodeKeys",ordered);}return hash(route.toString());}
  boolean adoptTransport()throws Exception{
    if(transport==null)return false;JSONObject state=transport.call("snapshot","");JSONObject value=secrets.settings();
    if(!state.optBoolean("alive")||!transportFingerprint(value).equals(state.optString("configuration")))return false;JSONObject meta=J.parse(new String(new android.util.AtomicFile(new File(root,"transport.json")).readFully(),StandardCharsets.UTF_8));if(!meta.optBoolean("ready"))return false;
    invalidateVerifiedRoute();validate(value);settings=value;JSONObject config=J.parse(new String(java.nio.file.Files.readAllBytes(new File(root,"config.json").toPath()),StandardCharsets.UTF_8));
    token=config.optString("secret");controllerPort=state.optInt("controllerPort");proxyPort=state.optInt("proxyPort");webProbePort=state.optInt("webProbePort");
    if(token.isEmpty()||controllerPort<=0||proxyPort<=0)return false;
    fingerprint=exitIdentity(settings);
    String scope=fingerprint+":"+hash(settings.optString("subscriptionUrl"));quality.configure(MEASUREMENT_PROFILE+":"+scope);websiteQuality.configure("chatgpt-head-v1:"+scope);dns.configure(scope);activeDns=dns.primary(System.currentTimeMillis());
    JSONArray restoredNodes=readProvider();validateEntryIdentities(restoredNodes);if(subscribedExit(settings))validateExitProvider("ExitSource","FixedExit");List<String> provider=providerNames(restoredNodes);EntrySelection.validate(settings,provider);names=EntrySelection.strings(meta.optJSONArray("names"));if(names.isEmpty()||!provider.containsAll(names))return false;totalEntries=names.size();
    JSONObject selected=api("GET","/proxies/EntryChoice",null,3000);currentEntry=selected.optString("now");List<String> configured=EntrySelection.strings(selected.optJSONArray("all"));if(!configured.isEmpty())names.retainAll(configured);activeDns=config.getJSONObject("dns").getJSONArray("nameserver").getString(0).replace("#FixedExit","");if(!names.contains(currentEntry))return false;
    report("正在恢复独立网络连接并核实固定出口…");verifyExit();ready=true;recoveryBlocked=false;startupPath="service-adopted";return true;
  }
  void startNow()throws Exception{
    invalidateVerifiedRoute();long startupBegan=android.os.SystemClock.elapsedRealtime();startupBeganAt=startupBegan;startupDuration=coreDuration=providerDuration=0;startupPath="";
    settings=secrets.settings();validate(settings);if(transport==null)cleanupOwnedPid();token=UUID.randomUUID().toString()+UUID.randomUUID();controllerPort=freePort();proxyPort=freePort();webProbePort=freePort();
    fingerprint=exitIdentity(settings);
    String scope=fingerprint+":"+hash(settings.optString("subscriptionUrl"));quality.configure(MEASUREMENT_PROFILE+":"+scope);websiteQuality.configure("chatgpt-head-v1:"+scope);dns.configure(scope);activeDns=dns.primary(System.currentTimeMillis());byte[] cached=secrets.get("subscription");JSONObject meta=J.parse(new String(Optional.ofNullable(secrets.get("subscription-meta")).orElse(new byte[0]),StandardCharsets.UTF_8));
    boolean fromCache=sourceCacheMatches(settings,NetworkCatalog.ENTRY,meta,cached);startupCached=fromCache;
    if(!settings.optString("entrySubscriptionId").isEmpty()&&!fromCache)throw new IOException("入口缓存与所选订阅不一致，请重新保存网络");prepareExitSnapshot();
    if(fromCache)try(FileOutputStream out=new FileOutputStream(new File(root,"subscription.yaml"))){out.write(cached);}
    J.write(new File(root,"config.json"),config(true,!fromCache).toString().replace("\\/","/"));
    report(fromCache?"正在从加密缓存启动手机独立网络…":"正在下载订阅并启动手机独立网络…");
    launchCore();
    coreDuration=android.os.SystemClock.elapsedRealtime()-startupBegan;long providerBegan=android.os.SystemClock.elapsedRealtime();
    JSONArray nodes=readProvider();names=new ArrayList<>(providerNames(nodes));
    long updated=fromCache?meta.optLong("updatedAt"):System.currentTimeMillis();
    validateEntryIdentities(nodes);if(subscribedExit(settings))validateExitProvider("ExitSource","FixedExit");
    File provider=new File(root,"subscription.yaml");if(provider.exists())try(FileInputStream in=new FileInputStream(provider)){byte[] raw=J.read(in,16*1024*1024);if(fromCache&&!Arrays.equals(raw,cached))throw new IOException("入口缓存已变化，请重新保存网络");secrets.put("subscription",raw);NetworkCatalog.put(meta,"urlHash",hash(settings.optString("subscriptionUrl")));NetworkCatalog.put(meta,"updatedAt",updated);NetworkCatalog.put(meta,"payloadHash",NetworkSourceSelection.payloadHash(raw));secrets.put("subscription-meta",meta.toString().getBytes(StandardCharsets.UTF_8));}
    JSONObject ui=J.parse(meta.toString());NetworkCatalog.put(ui,"nodes",new JSONArray(names));NetworkCatalog.put(ui,"nodeDetails",safeNodeDetails(nodes));secrets.put("subscription-ui",ui.toString().getBytes(StandardCharsets.UTF_8));
    EntrySelection.validate(settings,names);names=EntrySelection.allowed(settings,names);if(lowLatency())names=rankedRoutes();
    String remembered=context.getSharedPreferences("chat",0).getString("lastGoodEntry","");if(names.remove(remembered))names.add(0,remembered);totalEntries=names.size();if(names.isEmpty())throw new IOException("订阅未读到可用节点；请确认它是 Clash / Mihomo 格式");if(names.size()>64&&!lowLatency())names=new ArrayList<>(names.subList(0,64));
    J.write(new File(root,"config.json"),config(false,false).toString().replace("\\/","/"));api("PUT","/configs?force=true",J.obj("path",new File(root,"config.json").getAbsolutePath()),5000);
    providerDuration=android.os.SystemClock.elapsedRealtime()-providerBegan;chooseStartupRoute();writeTransportMetadata(true);ready=true;recoveryBlocked=false;failures=0;startupDuration=android.os.SystemClock.elapsedRealtime()-startupBegan;report("手机独立网络已连接 · "+display(currentEntry));
  }

  // A successful HTTPS exit check already proves that the entire selected chain works.
  // Keep the persisted exit-IP gate, and avoid probing every entry before trying it.
  void chooseStartupRoute()throws Exception{
    results=new JSONArray();String remembered=context.getSharedPreferences("chat",0).getString("lastGoodEntry","");
    if(names.contains(remembered)){
      report("正在恢复上次可用入口并核实固定出口…");
      try{selectNow(remembered);verifyExit();startupPath="remembered";lastScan=System.currentTimeMillis();return;}
      catch(ExitMismatch mismatch){throw mismatch;}
      catch(ExitCheckUnavailable unavailable){throw unavailable;}
      catch(Exception unavailable){quality.record(remembered,-1,System.currentTimeMillis());}
    }
    firstVerifiedRoute(remembered);
  }
  static final class RouteProbe{final String name;final int delay;final ProbeResult sample;RouteProbe(String n,int d){name=n;delay=d;sample=null;}RouteProbe(String n,ProbeResult result){name=n;delay=result.delay;sample=result;}}
  RouteProbe startupProbe(String name,int index,String epoch){
    if(!epoch.equals(token)||Thread.currentThread().isInterrupted())return new RouteProbe(name,-1);
    try{api("PUT","/proxies/ProbeEntry"+index,J.obj("name",name),3000);if(!epoch.equals(token)||Thread.currentThread().isInterrupted())return new RouteProbe(name,-1);return new RouteProbe(name,probeMeasured("ProbeExit"+index,name));}catch(Exception unavailable){return new RouteProbe(name,-1);}
  }
  void firstVerifiedRoute(String rejected)throws Exception{
    report("正在寻找可用入口并核实固定出口…");
    final List<String> candidates=new ArrayList<>(names);final String epoch=token;
    // Startup normally has no parent maintenance scope. Own every candidate's
    // controller socket until the search ends, including successful searches.
    final NetworkWork parent=maintenance.get(),search=new NetworkWork(true);search.owner=null;
    CompletionService<RouteProbe> completed=new ExecutorCompletionService<>(probes);List<Future<RouteProbe>> active=new ArrayList<>();
    JSONArray measured=new JSONArray();int next=0,running=0;long deadline=android.os.SystemClock.elapsedRealtime()+startupSearchBudgetMs();
    try{
      while(next<candidates.size()||running>0){maintenanceCheck();
        while(running<4&&next<candidates.size()){
          final int index=next++;final String name=candidates.get(index);if(name.equals(rejected))continue;
          Future<RouteProbe> task=completed.submit(()->{maintenance.set(search);try{return startupProbe(name,index,epoch);}finally{maintenance.remove();}});
          active.add(task);search.add(task);if(parent!=null)parent.add(task);running++;
        }
        if(running==0)break;
        long remaining=deadline-android.os.SystemClock.elapsedRealtime();Future<RouteProbe> finished=remaining>0?completed.poll(remaining,TimeUnit.MILLISECONDS):null;
        if(finished==null)throw new IOException("入口检查超时，请重试；不会改为直连");
        active.remove(finished);RouteProbe r=finished.get();running--;maintenanceCheck();
        if(!epoch.equals(token))throw new IOException("网络连接已改变，请重试");
        long now=System.currentTimeMillis();if(r.sample!=null)recordProbe(r.sample,now);else quality.record(r.name,r.delay,now,"unknown",new JSONObject());measured.put(J.obj("name",display(r.name),"internalName",r.name,"delay",r.delay,"probe",r.sample==null?new JSONObject():r.sample.publicSummary()));results=measured;
        if(r.delay<=0)continue;
        try{selectNow(r.name);verifyExit();startupPath="first-verified";lastScan=System.currentTimeMillis();return;}
        catch(ExitMismatch mismatch){throw mismatch;}
        catch(ExitCheckUnavailable unavailable){throw unavailable;}
        catch(Exception unavailable){quality.record(r.name,-1,System.currentTimeMillis());}
      }
      throw new IOException("全部入口的完整代理链均不可用；不会改为直连");
    }finally{search.cancel(closers);search.finish();}
  }
  long startupSearchBudgetMs(){return 45000;}
  void writeTransportMetadata(boolean active)throws IOException{
    if(transport==null)return;android.util.AtomicFile file=new android.util.AtomicFile(new File(root,"transport.json"));FileOutputStream out=file.startWrite();try{out.write(J.obj("proxyPort",proxyPort,"webProbePort",webProbePort,"ready",active,"names",new JSONArray(names)).toString().getBytes(StandardCharsets.UTF_8));file.finishWrite(out);}catch(Exception e){file.failWrite(out);throw new IOException("网络运行状态未能保存",e);}
  }
  void launchCore()throws Exception{
    File binary=new File(context.getApplicationInfo().nativeLibraryDir,"libmihomo.so");if(!binary.isFile())throw new IOException("该手机架构没有可用的内置网络内核");
    if(transport!=null){writeTransportMetadata(false);transport.call("launch",transportFingerprint(settings));}
    else{
    process=new ProcessBuilder("/system/bin/sh","-c","umask 077; echo $$ > \"$1/core.pid\"; exec \"$2\" -d \"$1\" -f \"$1/config.json\"","pocket-core",root.getAbsolutePath(),binary.getAbsolutePath()).redirectErrorStream(true).start();
    final java.lang.Process owned=process;new Thread(()->{try(InputStream in=owned.getInputStream()){byte[] b=new byte[4096];while(in.read(b)>=0){}}catch(Exception ignored){}},"core-output-discard").start();
    }
    long deadline=System.currentTimeMillis()+20000;for(int i=0;i<100;i++){if(System.currentTimeMillis()>deadline)throw new IOException("内置代理启动超时");if(!coreAlive())throw new IOException("安卓代理内核启动后退出");try{api("GET","/version",null,2000);if(transport!=null)transport.call("ready","");return;}catch(Exception e){Thread.sleep(150);}}throw new IOException("内置代理控制服务未就绪");
  }
  JSONArray readProvider()throws Exception{
    long deadline=System.currentTimeMillis()+35000;for(int i=0;i<60&&System.currentTimeMillis()<deadline;i++){if(!coreAlive())throw new IOException("订阅解析进程已退出");try{JSONArray nodes=api("GET","/providers/proxies/Subscription",null,3000).optJSONArray("proxies");if(nodes!=null&&nodes.length()>0)return nodes;}catch(Exception ignored){}Thread.sleep(500);}throw new IOException("订阅未读到可用节点，请检查订阅格式或网络");
  }
  static List<String> providerNames(JSONArray nodes){List<String> out=new ArrayList<>();for(int i=0;i<nodes.length();i++){JSONObject p=nodes.optJSONObject(i);if(p!=null&&p.optString("name").startsWith("Entry|")&&!out.contains(p.optString("name")))out.add(p.optString("name"));}return out;}
  static JSONArray safeNodeDetails(JSONArray nodes){JSONArray out=new JSONArray();for(int i=0;i<nodes.length();i++){JSONObject node=nodes.optJSONObject(i);if(node!=null&&node.optString("configFingerprint").matches("[0-9a-f]{64}")&&node.optInt("configFingerprintVersion")==1)out.put(J.obj("name",node.optString("name"),"type",node.optString("type"),"configFingerprint",node.optString("configFingerprint"),"configFingerprintVersion",1));}return out;}
  void validateEntryIdentities(JSONArray nodes)throws Exception{validateEntryIdentities(settings,nodes);}
  static void validateEntryIdentities(JSONObject settings,JSONArray nodes)throws Exception{
    Map<String,String> actual=new HashMap<>();for(int i=0;i<nodes.length();i++){JSONObject node=nodes.optJSONObject(i);if(node!=null)actual.put(node.optString("name"),node.optString("configFingerprint"));}
    String chosen=settings.optString("entry"),key=settings.optString("entryNodeKey");if(!key.isEmpty()&&!key.equals(actual.get(chosen)))throw new IOException("当前入口与保存的节点不同，请重新选择");
    JSONObject refs=settings.optJSONObject("entryPoolNodeKeys");List<String> keys=NetworkSourceSelection.keys(settings.optJSONArray("entryPoolKeys"));if(settings.has("entryPoolKeys"))for(String name:EntrySelection.strings(settings.optJSONArray("entryPool"))){String expected=refs==null?actual.get(name):refs.optString(name);if(expected==null||expected.isEmpty()||!keys.contains(expected)||!expected.equals(actual.get(name)))throw new IOException("入口池与保存的节点不同，请重新选择");}
  }
  static void validateSnapshotSelection(JSONObject settings,String role,JSONObject ui)throws Exception{JSONArray nodes=ui.optJSONArray("nodeDetails");if(nodes==null)throw new IOException("订阅快照缺少节点信息，请重新保存网络");if(NetworkCatalog.ENTRY.equals(role)){validateEntryIdentities(settings,nodes);return;}for(int i=0;i<nodes.length();i++){JSONObject node=nodes.optJSONObject(i);if(node!=null&&settings.optString("exitNodeName").equals(node.optString("name"))&&settings.optString("exitNodeKey").equals(node.optString("configFingerprint"))&&"socks5".equalsIgnoreCase(node.optString("type")))return;}throw new IOException("固定出口快照与所选节点不一致，请重新保存网络");}
  void validateExitProvider(String provider,String expectedName)throws Exception{JSONArray nodes=api("GET","/providers/proxies/"+provider,null,3000).optJSONArray("proxies");if(nodes==null||nodes.length()!=1)throw new IOException("固定出口不是唯一节点，请重新选择");JSONObject node=nodes.getJSONObject(0);if(!expectedName.equals(node.optString("name"))||!"socks5".equalsIgnoreCase(node.optString("type"))||!settings.optString("exitNodeKey").equals(node.optString("configFingerprint")))throw new IOException("固定出口已变化，请重新选择");}
  interface PreviewCallback{void done(boolean ok,String message,JSONArray names,byte[] provider);}
  interface SourcePreviewCallback{void done(boolean ok,String message,JSONArray names,JSONArray nodeDetails,byte[] provider);}
  static void previewSubscription(Context c,String url,byte[] cache,PreviewCallback callback){
    previewSubscription(c,NetworkCatalog.ENTRY,url,cache,(ok,message,names,details,provider)->callback.done(ok,message,names,provider));
  }
  static void previewSubscription(Context c,String role,String url,byte[] cache,SourcePreviewCallback callback){
    // A short-lived parser instance has no listener, account document, or active route.
    NativeNetwork reader=new NativeNetwork(c,new File(c.getNoBackupFilesDir(),"subscription-preview-"+UUID.randomUUID()),false);
    reader.worker.execute(()->{JSONArray nodes=new JSONArray(),details=new JSONArray();byte[] provider=null;String error="";try{
      if(!NetworkCatalog.ENTRY.equals(role)&&!NetworkCatalog.EXIT.equals(role))throw new IOException("订阅类型无效");
      reader.settings=J.obj("subscriptionUrl",url);reader.token=UUID.randomUUID().toString();reader.controllerPort=freePort();reader.proxyPort=freePort();
      if(cache!=null)try(FileOutputStream out=new FileOutputStream(new File(reader.root,"subscription.yaml"))){out.write(cache);}
      JSONObject config=reader.config(true,cache==null);config.put("proxies",new JSONArray());config.put("proxy-groups",new JSONArray());String prefix=NetworkCatalog.EXIT.equals(role)?"Exit|":"Entry|";
      config.getJSONObject("proxy-providers").getJSONObject("Subscription").getJSONObject("override").put("additional-prefix",prefix);
      J.write(new File(reader.root,"config.json"),config.toString().replace("\\/","/"));reader.launchCore();JSONArray parsed=reader.readProvider();
      Set<String> seen=new HashSet<>();for(int i=0;i<parsed.length();i++){JSONObject node=parsed.optJSONObject(i);if(node==null||!node.optString("name").startsWith(prefix))continue;String name=node.optString("name"),key=node.optString("configFingerprint");if(!key.matches("[0-9a-f]{64}")||node.optInt("configFingerprintVersion")!=1)throw new IOException("内核未能识别节点，请更新后重试");if(!seen.add(name))throw new IOException("订阅内有同名节点，请先整理订阅");nodes.put(name);details.put(J.obj("name",name,"type",node.optString("type"),"configFingerprint",key,"configFingerprintVersion",1));}
      if(nodes.length()==0)throw new IOException(NetworkCatalog.EXIT.equals(role)?"订阅没有可读取的出口节点":"订阅没有可选入口");
      try(FileInputStream in=new FileInputStream(new File(reader.root,"subscription.yaml"))){provider=J.read(in,16*1024*1024);}
    }catch(Exception e){error=e instanceof IOException&&e.getMessage()!=null?e.getMessage():"订阅读取失败，已保留原配置";}finally{reader.stopNow();reader.probes.shutdownNow();reader.closers.shutdownNow();reader.traffic.reader.shutdownNow();reader.worker.shutdown();deletePreview(reader.root);}
      final JSONArray result=nodes,metadata=details;final byte[] bytes=provider;final String reason=error;reader.main.post(()->callback.done(reason.isEmpty(),reason,result,metadata,bytes));
    });
  }
  static void deletePreview(File directory){File[] files=directory.listFiles();if(files!=null)for(File f:files){if(f.isDirectory())deletePreview(f);else f.delete();}directory.delete();}
  void configureProbeEntries()throws Exception{for(int i=0;i<names.size();i++)api("PUT","/proxies/ProbeEntry"+i,J.obj("name",names.get(i)),3000);}

  boolean configurationMatches(){try{return settings!=null&&transportFingerprint(settings).equals(transportFingerprint(secrets.settings()));}catch(Exception e){return false;}}
  synchronized void pauseBackgroundWhenBusy(){NetworkWork work=backgroundWork;if(work!=null&&!work.allowBusy&&routeBusy())cancelMaintenance();}
  synchronized void cancelMaintenance(){maintenanceGeneration++;lastMaintenanceAt=android.os.SystemClock.elapsedRealtime();NetworkWork work=backgroundWork;if(work!=null)work.cancel(closers);}
  synchronized NetworkWork beginMaintenance(long expected){return beginMaintenance(expected,false);}
  synchronized NetworkWork beginMaintenance(long expected,boolean allowBusy){if(starting||expected!=maintenanceGeneration)return null;NetworkWork work=new NetworkWork(allowBusy);backgroundWork=work;maintenance.set(work);return work;}
  void finishMaintenance(NetworkWork work){work.finish();maintenance.remove();synchronized(this){if(backgroundWork==work)backgroundWork=null;}Thread.interrupted();}
  void maintenanceCheck()throws InterruptedIOException{NetworkWork work=maintenance.get();if(work!=null){if(!work.allowBusy&&routeBusy())work.cancel(closers);work.check();}}
  boolean maintenanceCancelled(){NetworkWork work=maintenance.get();return work!=null&&work.cancelled;}
  void track(HttpURLConnection c)throws InterruptedIOException{NetworkWork work=maintenance.get();if(work!=null)work.add(c);}
  void untrack(HttpURLConnection c){NetworkWork work=maintenance.get();if(work!=null)work.remove(c);}
  boolean backgroundIdle(){ChatSession s=ChatSession.peek();return s!=null&&!s.uiVisible&&!s.browserWorkActive();}
  long latestLatencyAt(String entry,String epoch){long at=quality.currentSample(entry,System.currentTimeMillis(),probeRouteKey()).optLong("at");JSONObject displayed=latencyReading;if(entry.equals(displayed.optString("entry"))&&epoch.equals(displayed.optString("generation"))&&routeSerial==displayed.optLong("routeSerial"))at=Math.max(at,displayed.optLong("at"));return at;}
  static boolean freshLatency(long at,long now){return at>0&&now>=at-60000&&now-at<60000;}
  /** One current-chain sample for the UI; never scans or changes the live route. */
  synchronized void refreshLatency(){
    if(!ready||starting||!coreAlive()||currentEntry.isEmpty()||latencyRefreshQueued||routeBusy())return;
    long now=System.currentTimeMillis(),mono=android.os.SystemClock.elapsedRealtime();long at=latestLatencyAt(currentEntry,token);
    if(freshLatency(at,now))return;
    String route=token+"|"+currentEntry;
    if(route.equals(latencyRefreshRoute)&&mono-latencyRefreshAttempted<(at>0?60000:10000))return;
    latencyRefreshAttempted=mono;latencyRefreshRoute=route;latencyRefreshQueued=true;
    final String entry=currentEntry,epoch=token;final long generation=maintenanceGeneration;
    worker.execute(()->{NetworkWork work=beginMaintenance(generation);boolean probed=false;
      try{if(work==null||!ready||starting||!entry.equals(currentEntry)||!epoch.equals(token)||routeBusy())return;
        // Health may have measured the same route while this display request waited.
        if(freshLatency(latestLatencyAt(entry,epoch),System.currentTimeMillis()))return;
        probed=true;ProbeResult result=probeMeasured("FixedExit",entry);maintenanceCheck();if(ready&&!starting&&probeCurrent(result)){publishCurrentProbe(result);if(result.delay>0)recordProbe(result,result.at);}}
      catch(Exception cancelled){/* A new user operation keeps priority; no failed sample is fabricated. */}
      finally{if(work!=null)finishMaintenance(work);synchronized(this){if(!probed&&route.equals(latencyRefreshRoute)){latencyRefreshAttempted=-60000;latencyRefreshRoute="";}latencyRefreshQueued=false;}ChatSession s=ChatSession.peek();WindowNetworkState.save(context,s,this);if(s!=null)main.post(s::changed);}
    });
  }
  void runHealth(){
    if(!ready||starting)return;
    if(!coreAlive()){stopNow();report("内置网络进程已退出，请重新连接");return;}
    if(routeBusy()){cancelMaintenance();return;}
    long now=android.os.SystemClock.elapsedRealtime();if(now-lastMaintenanceAt<(backgroundIdle()?NetworkOptimizationPolicy.BACKGROUND_INTERVAL:NetworkOptimizationPolicy.ACTIVE_INTERVAL))return;
    NetworkWork work=beginMaintenance(maintenanceGeneration);if(work==null)return;lastMaintenanceAt=now;
    try{health();}finally{finishMaintenance(work);WindowNetworkState.save(context,ChatSession.peek(),this);}
  }
  JSONObject group(String name,String filter){JSONObject g=J.obj("name",name,"type","select","proxies",J.arr("REJECT"),"use",J.arr("Subscription"),"empty-fallback","REJECT","interval",0,"hidden",true);if(filter!=null)try{g.put("filter",filter);}catch(Exception ignored){}return g;}
  JSONObject exit(String name,String group){JSONObject result=J.obj("name",name,"type","socks5","server",settings.optString("exitHost"),"port",settings.optInt("exitPort"),"username",settings.optString("exitUser"),"password",settings.optString("exitPassword"),"udp",false,"dialer-proxy",group);if("FixedExit".equals(name)){NetworkCatalog.put(result,"pocket-preconnect",true);NetworkCatalog.put(result,"pocket-preconnect-epoch-file",new File(root,ExitPreconnectEpoch.FILE).getAbsolutePath());}return result;}
  static String literalRegex(String s){StringBuilder b=new StringBuilder();for(char c:s.toCharArray()){if(c=='`'){b.append("\\x60");continue;}if("\\.+*?()|[]{}^$".indexOf(c)>=0)b.append('\\');b.append(c);}return b.toString();}
  void configuredExit(String name,String entryGroup,String providerName,JSONObject providers,JSONArray proxies,JSONArray groups){
    if(!subscribedExit(settings)){proxies.put(exit(name,entryGroup));return;}
    JSONObject override=J.obj("pocket-config-fingerprint",settings.optString("exitNodeKey"),"dialer-proxy",entryGroup,"udp",false,"proxy-name",J.arr(J.obj("pattern","^.*$","target",name)),"pocket-preconnect",name.equals("FixedExit"));
    if(name.equals("FixedExit"))NetworkCatalog.put(override,"pocket-preconnect-epoch-file",new File(root,ExitPreconnectEpoch.FILE).getAbsolutePath());
    NetworkCatalog.put(providers,providerName,J.obj("type","file","path","./exit-subscription.yaml","filter","^(?:"+literalRegex(settings.optString("exitNodeName").substring(5))+")$","health-check",J.obj("enable",false),"override",override));
    groups.put(J.obj("name",name,"type","select","proxies",new JSONArray(),"use",J.arr(providerName),"filter","^(?:"+literalRegex(name)+")$","empty-fallback","REJECT","interval",0,"hidden",true));
  }
  JSONObject config(boolean bootstrap,boolean download){
    JSONObject provider=J.obj("type",download?"http":"file","path","./subscription.yaml","health-check",J.obj("enable",false),"override",J.obj("additional-prefix","Entry|","dialer-proxy",""));
    if(download)try{provider.put("url",settings.optString("subscriptionUrl"));provider.put("interval",0);provider.put("proxy","DIRECT");provider.put("size-limit",16*1024*1024);provider.put("header",J.obj("User-Agent",J.arr("mihomo")));}catch(Exception ignored){}
    JSONObject providers=J.obj("Subscription",provider);JSONArray proxies=new JSONArray(),groups=J.arr(group("EntryChoice",!bootstrap&&!settings.optString("entryMode").isEmpty()?EntrySelection.filter(names):null));configuredExit("FixedExit","EntryChoice","ExitSource",providers,proxies,groups);if(!bootstrap){groups.put(group("WebProbeEntry",EntrySelection.filter(names)));configuredExit("WebProbeExit","WebProbeEntry","WebExitSource",providers,proxies,groups);}if(!bootstrap)for(int i=0;i<names.size();i++){groups.put(group("ProbeEntry"+i,"^(?:"+literalRegex(names.get(i))+")$"));configuredExit("ProbeExit"+i,"ProbeEntry"+i,"ProbeExitSource"+i,providers,proxies,groups);}
    return J.obj("port",0,"socks-port",0,"mixed-port",0,"redir-port",0,"tproxy-port",0,"allow-lan",false,"bind-address","127.0.0.1","mode","rule","unified-delay",true,"tcp-concurrent",true,"log-level","silent","ipv6",false,"external-controller","127.0.0.1:"+controllerPort,"secret",token,
      "external-controller-cors",J.obj("allow-origins",new JSONArray(),"allow-private-network",false),"profile",J.obj("store-selected",false,"store-fake-ip",false),"tun",J.obj("enable",false),"sniffer",J.obj("enable",false),"geo-auto-update",false,
      "dns",J.obj("enable",true,"listen","127.0.0.1:0","ipv6",false,"enhanced-mode","redir-host","cache-algorithm","arc","default-nameserver",J.arr("https://223.5.5.5/dns-query","https://223.6.6.6/dns-query"),"nameserver",bootstrap?J.arr(NetworkDns.SERVERS[0],NetworkDns.SERVERS[1]):J.arr(dns.primary(System.currentTimeMillis())+"#FixedExit",dns.backup(System.currentTimeMillis())+"#FixedExit"),"proxy-server-nameserver",J.arr("https://dns.alidns.com/dns-query","https://doh.pub/dns-query")),
      "proxy-providers",providers,"proxies",proxies,"proxy-groups",groups,"rules",J.arr("MATCH,REJECT"),"listeners",bootstrap?new JSONArray():J.arr(J.obj("name","PocketOnly","type","mixed","listen","127.0.0.1","port",proxyPort,"udp",false,"proxy","FixedExit"),J.obj("name","WebsiteCheck","type","mixed","listen","127.0.0.1","port",webProbePort,"udp",false,"proxy","WebProbeExit")));
  }
  JSONObject api(String method,String path,JSONObject body,int timeout)throws Exception{
    maintenanceCheck();if(Thread.currentThread().isInterrupted())throw new InterruptedIOException("网络检查已取消");
    HttpURLConnection c=(HttpURLConnection)new URL("http://127.0.0.1:"+controllerPort+path).openConnection(Proxy.NO_PROXY);track(c);
    try{c.setRequestMethod(method);c.setConnectTimeout(timeout);c.setReadTimeout(timeout);c.setInstanceFollowRedirects(false);c.setRequestProperty("Authorization","Bearer "+token);
      if(body!=null){c.setDoOutput(true);c.setRequestProperty("Content-Type","application/json");try(OutputStream out=c.getOutputStream()){out.write(body.toString().getBytes(StandardCharsets.UTF_8));}}
      int code=c.getResponseCode();maintenanceCheck();if(code<200||code>=300)throw new IOException("内置网络控制请求失败");try(InputStream in=c.getInputStream()){return J.parse(J.text(in,8*1024*1024));}
    }finally{untrack(c);c.disconnect();}
  }
  int probe(String name){
    long began=System.currentTimeMillis(),monotonic=android.os.SystemClock.elapsedRealtime();String entry=currentEntry,epoch=token,target=probeUrl();long serial=routeSerial;int controller=controllerPort;ProbeTicket ticket=probeTicket.get();
    try{
      JSONObject response=api("GET","/proxies/"+URLEncoder.encode(name,"UTF-8")+"/delay?timeout=8000&expected=204&url="+URLEncoder.encode(target,"UTF-8"),null,11000);int delay=response.optInt("delay",-1);
      if(!epoch.equals(token)||serial!=routeSerial||controller!=controllerPort||Thread.currentThread().isInterrupted())return -1;
      long duration=android.os.SystemClock.elapsedRealtime()-monotonic;
      JSONObject info=api("GET","/proxies/"+URLEncoder.encode(name,"UTF-8"),null,3000).optJSONObject("extra");JSONObject state=info==null?null:info.optJSONObject(target);JSONArray history=state==null?null:state.optJSONArray("history");
      if(delay<=0||state==null||!state.optBoolean("alive")||history==null||history.length()==0)return -1;
      JSONObject latest=history.getJSONObject(history.length()-1);if(Instant.parse(latest.getString("time")).toEpochMilli()<began-1500)return -1;
      if(!epoch.equals(token)||serial!=routeSerial||controller!=controllerPort||Thread.currentThread().isInterrupted())return -1;
      // The trace is from this exact controller response, not a matching history value.
      if(ticket!=null&&ticket.binding.proxy.equals(name)&&ticket.binding.matches(token,routeSerial,controllerPort,currentEntry)){ticket.trace=probeTrace(response.optJSONObject("probe"),delay);ticket.duration=duration;}
      if(name.equals("FixedExit")&&entry.equals(currentEntry)&&epoch.equals(token)){lastProbeEntry=entry;lastProbeDuration=duration;lastProbeDurationAt=System.currentTimeMillis();}
      return delay;
    }catch(Exception e){return -1;}
  }
  HttpURLConnection openProbeConnection(String target,int port)throws IOException{return (HttpURLConnection)new URL(target).openConnection(new Proxy(Proxy.Type.HTTP,new InetSocketAddress("127.0.0.1",port)));}
  String probeUrl(){return PROBE;}
  String exitCheckUrl(){return "https://api.ipify.org?format=json";}
  boolean lowLatency(){return settings!=null&&"latency".equals(settings.optString("entryMode"));}
  boolean routeBusy(){return NetworkRegion.backgroundBusy(ChatSession.peek());}
  List<String> rankedRoutes(){long now=System.currentTimeMillis();List<String> ordered=quality.ranked(names,now);if(lowLatency())ordered.sort(Comparator.comparingDouble(name->{JSONObject q=websiteQuality.stats(name,now);return q.optInt("samples")>=3&&q.optInt("latest")>0?q.optDouble("score"):1000000+quality.stats(name,now).optDouble("score");}));return ordered;}
  String websiteUrl(){return "https://chatgpt.com/";}
  void closeWebsiteConnections()throws Exception{
    JSONArray connections=api("GET","/connections",null,3000).optJSONArray("connections");if(connections==null)return;
    for(int i=0;i<connections.length();i++){JSONObject c=connections.optJSONObject(i);JSONArray chains=c==null?null:c.optJSONArray("chains");boolean probe=false;if(chains!=null)for(int j=0;j<chains.length();j++)if("WebProbeExit".equals(chains.optString(j)))probe=true;
      if(probe&&!c.optString("id").isEmpty())api("DELETE","/connections/"+URLEncoder.encode(c.optString("id"),"UTF-8"),null,3000);
    }
  }
  JSONObject measureWebsite(String entry)throws Exception{
    maintenanceCheck();if(!names.contains(entry))throw new IOException("入口不属于允许池");String epoch=token;
    // Only the probe's own tunnels are closed; the actual FixedExit never changes here.
    JSONObject value;try{closeWebsiteConnections();api("PUT","/proxies/WebProbeEntry",J.obj("name",entry),3000);value=WebsiteProbe.run(this,entry,webProbePort,websiteUrl());}catch(InterruptedIOException cancelled){maintenanceCheck();if(Thread.currentThread().isInterrupted())throw cancelled;value=J.obj("entry",entry,"at",System.currentTimeMillis(),"status","unreachable");}catch(IOException unavailable){value=J.obj("entry",entry,"at",System.currentTimeMillis(),"status","unreachable");}
    maintenanceCheck();if(!epoch.equals(token))throw new InterruptedIOException("连接已变化");
    if("ok".equals(value.optString("status")))websiteQuality.record(entry,(int)value.optLong("firstMs"),value.optLong("at"));
    // A site-side challenge is inconclusive, rather than a failed proxy sample.
    else if("unreachable".equals(value.optString("status")))websiteQuality.record(entry,-1,value.optLong("at"));
    if(entry.equals(currentEntry))websiteResult=value;return value;
  }
  void scanAndSelect(boolean force)throws Exception{scanSubset(new ArrayList<>(names),force,false);}
  void scanSubset(List<String> batch,boolean force,boolean background)throws Exception{
    maintenanceCheck();if(!background)report("正在检查线路稳定性 · "+batch.size()+" 个入口");
    JSONArray measured=new JSONArray();int good=0;final NetworkWork work=maintenance.get();
    for(int offset=0;offset<batch.size();offset+=2){
      maintenanceCheck();List<Future<ProbeResult>> tasks=new ArrayList<>();List<String> round=batch.subList(offset,Math.min(offset+2,batch.size()));
      try{for(String name:round){final int index=names.indexOf(name);if(index<0)throw new IOException("入口池已变化");api("PUT","/proxies/ProbeEntry"+index,J.obj("name",name),3000);Future<ProbeResult> task=probes.submit(()->{if(work!=null)maintenance.set(work);try{return probeMeasured("ProbeExit"+index,name);}finally{maintenance.remove();}});tasks.add(task);if(work!=null)work.add(task);}
        for(int i=0;i<tasks.size();i++){ProbeResult result=tasks.get(i).get();maintenanceCheck();String name=round.get(i);if(!probeCurrent(result)||!name.equals(result.binding.entry))throw new IOException("测速线路已变化");int delay=result.delay;long now=System.currentTimeMillis();recordProbe(result,now);JSONObject stats=quality.stats(name,now);measured.put(J.obj("name",display(name),"internalName",name,"delay",delay,"samples",stats.optInt("samples"),"successRate",stats.optDouble("rate"),"mean",stats.optLong("mean"),"jitter",stats.optLong("jitter"),"score",stats.optDouble("score"),"kind",result.kind(),"probe",result.publicSummary()));if(delay>0)good++;}
      }finally{for(Future<ProbeResult> task:tasks)if(!task.isDone())task.cancel(true);}
    }
    maintenanceCheck();results=measured;lastScan=System.currentTimeMillis();if(good==0&&background)return;if(good==0)throw new IOException("本轮入口的完整代理链均不可用；不会改为直连");
    if(lowLatency()&&!force)for(String name:batch){maintenanceCheck();if(quality.stats(name,lastScan).optInt("latest")>0)measureWebsite(name);}
    maintenanceCheck();String mode=settings==null?"":settings.optString("entryMode"),chosen=currentEntry;
    if(lowLatency()){
      JSONObject current=websiteQuality.stats(currentEntry,lastScan);boolean enough=current.optInt("samples")>=3&&current.optInt("latest")>0;
      chosen=(enough&&!force?websiteQuality:quality).choose(batch,currentEntry,force,routeBusy(),System.currentTimeMillis());
    }else if(mode.isEmpty())chosen=quality.choose(batch,currentEntry,force,routeBusy(),System.currentTimeMillis());
    else if(force&&!mode.equals("manual")){List<String> healthy=new ArrayList<>();for(String name:batch)if(quality.stats(name,lastScan).optInt("latest")>0)healthy.add(name);chosen=EntrySelection.random(healthy,new Random());}
    maintenanceCheck();if(!routeBusy()&&!chosen.isEmpty()&&!chosen.equals(currentEntry)){selectNow(chosen);verifyExit();}
  }
  void selectNow(String name)throws Exception{invalidateVerifiedRoute();api("PUT","/proxies/EntryChoice",J.obj("name",name),3000);if(!name.equals(api("GET","/proxies/EntryChoice",null,3000).optString("now")))throw new IOException("入口切换未得到确认");currentEntry=name;quality.selected(name,System.currentTimeMillis());websiteQuality.selected(name,System.currentTimeMillis());websiteResult=new JSONObject();}
  String verifyExit()throws Exception{long began=android.os.SystemClock.elapsedRealtime();try{return verifyExitRequest();}finally{exitCheckDuration=android.os.SystemClock.elapsedRealtime()-began;}}
  static boolean validExitIp(String ip){
    if(ip.matches("(?:[0-9]{1,3}\\.){3}[0-9]{1,3}")){for(String part:ip.split("\\."))if(Integer.parseInt(part)>255)return false;return true;}
    if(!ip.contains(":")||!ip.matches("[0-9a-fA-F:]+"))return false;
    try{InetAddress.getByName(ip);return true;}catch(UnknownHostException invalid){return false;}
  }
  static String exitResponse(InputStream in)throws IOException{ByteArrayOutputStream body=new ByteArrayOutputStream();byte[] bytes=new byte[1024];int count;while((count=in.read(bytes))!=-1){if(body.size()+count>4096)throw new ExitCheckUnavailable("invalid-response",null);body.write(bytes,0,count);}return new String(body.toByteArray(),StandardCharsets.UTF_8);}
  /** Only an interrupted detector exchange, never cancellation or TLS identity failure. */
  static boolean exitTransportInterrupted(IOException failure){
    boolean interrupted=false;Throwable cause=failure;
    for(int depth=0;cause!=null&&depth<8;depth++,cause=cause.getCause()){
      if(cause instanceof InterruptedIOException||cause instanceof javax.net.ssl.SSLHandshakeException||cause instanceof javax.net.ssl.SSLPeerUnverifiedException||cause instanceof java.security.cert.CertificateException||cause instanceof UnknownHostException||cause instanceof ConnectException||cause instanceof NoRouteToHostException)return false;
      String message=cause.getMessage()==null?"":cause.getMessage().toLowerCase(Locale.ROOT);
      interrupted|=cause instanceof EOFException||(cause instanceof SocketException||cause instanceof javax.net.ssl.SSLException)&&message.contains("connection reset")||message.startsWith("unexpected end of stream")||message.contains("unexpected eof");
    }
    return interrupted;
  }
  String verifyExitRequest()throws Exception{
    maintenanceCheck();ExitRouteReceipt attempted=exitRouteReceipt();HttpURLConnection c=openProbeConnection(exitCheckUrl(),proxyPort);track(c);c.setConnectTimeout(10000);c.setReadTimeout(10000);String ip;boolean reusable=false;
    try{int status=c.getResponseCode();if(status!=200)throw new ExitCheckUnavailable("http-"+status,null);
      try(InputStream in=c.getInputStream()){try{ip=new JSONObject(exitResponse(in)).optString("ip");}catch(JSONException invalid){throw new ExitCheckUnavailable("invalid-response",invalid);}}
      if(!validExitIp(ip))throw new ExitCheckUnavailable("invalid-response",null);reusable=true;
    }catch(SocketTimeoutException timeout){maintenanceCheck();if(Thread.currentThread().isInterrupted())throw timeout;throw new ExitCheckUnavailable("timeout",timeout);}
    catch(IOException interrupted){maintenanceCheck();if(Thread.currentThread().isInterrupted()||!exitTransportInterrupted(interrupted))throw interrupted;throw new ExitCheckUnavailable("transport-reset-or-eof",interrupted);}
    finally{untrack(c);if(!reusable)c.disconnect();}
    maintenanceCheck();JSONObject state=transport==null?null:transport.state;if(!attempted.matches(this,state))throw new IOException("网络实例已变化，出口核验结果未应用");
    observedExitIp=ip;lastObserved=System.currentTimeMillis();byte[] stored=secrets.get("exit-baseline");JSONObject old=stored==null?new JSONObject():J.parse(new String(stored,StandardCharsets.UTF_8));
    if(fingerprint.equals(old.optString("fingerprint"))&&!ip.equals(old.optString("ip"))){verifiedRoute=null;recoveryBlocked=true;if(exitIp.isEmpty())exitIp=old.optString("ip");throw new ExitMismatch();}
    if(!fingerprint.equals(old.optString("fingerprint")))secrets.put("exit-baseline",J.obj("fingerprint",fingerprint,"ip",ip).toString().getBytes(StandardCharsets.UTF_8));
    exitIp=ip;lastVerified=System.currentTimeMillis();verifiedRoute=attempted;admission=NetworkHealthPolicy.Admission.VERIFIED;exitCheckFailures=0;nextExitCheckAt=0;context.getSharedPreferences("chat",0).edit().putString("lastGoodEntry",currentEntry).apply();return ip;
  }
  synchronized void measureLatency(Callback cb){
    long now=android.os.SystemClock.elapsedRealtime();if(measuringLatency||now-lastManualProbe<5000){main.post(()->cb.done(false,"请稍后再测"));return;}if(!ready||starting||!coreAlive()){main.post(()->cb.done(false,"请先恢复应用网络"));return;}
    measuringLatency=true;lastManualProbe=now;cancelMaintenance();long generation=maintenanceGeneration;
    worker.execute(()->{boolean ok=false;String text="线路暂未通过探测，可稍后再试";NetworkWork work=beginMaintenance(generation,true);
      try{if(work==null)throw new IOException("连接已变化");if(ready&&!starting&&coreAlive()){String entry=currentEntry;ProbeResult result=probeMeasured("FixedExit",entry);maintenanceCheck();if(ready&&probeCurrent(result)){publishCurrentProbe(result);recordProbe(result,result.at);ok=result.delay>0;if(ok){JSONObject site=measureWebsite(entry);text="线路 "+LatencyProbePolicy.label(result.kind(),result.delay)+" · "+WebsiteProbe.line(site,System.currentTimeMillis());}}}}
      catch(Exception cancelled){ok=false;text="测速已暂停，当前操作继续进行";}finally{if(work!=null)finishMaintenance(work);measuringLatency=false;WindowNetworkState.save(context,ChatSession.peek(),this);}
      final boolean success=ok;final String message=text;main.post(()->cb.done(success,message));});
  }
  void checkExit(Callback cb){cancelMaintenance();worker.execute(()->{try{if(!ready||!coreAlive())throw new IOException("请先恢复应用网络");verifyExit();main.post(()->cb.done(true,"出口已核实"));}catch(Exception e){if(!retainVerifiedRoute(e)){stopNow();if(e instanceof ExitMismatch)recoveryBlocked=true;report(e.getMessage()==null?"出口核实失败":e.getMessage());}main.post(()->cb.done(false,message));}});}
  void beforeSend(Callback cb){cancelMaintenance();worker.execute(()->{try{if(!ready||!coreAlive())throw new IOException("内置网络尚未连接");verifyExit();main.post(()->cb.done(true,""));}catch(Exception e){boolean usable=retainVerifiedRoute(e);if(!usable){stopNow();if(e instanceof ExitMismatch)recoveryBlocked=true;report(e instanceof IOException?e.getMessage():"固定出口验证失败");}final String detail=message;main.post(()->cb.done(usable,detail));}});}
  void rescan(Callback cb){long generation=maintenanceGeneration;worker.execute(()->{NetworkWork work=beginMaintenance(generation);if(work==null){main.post(()->cb.done(false,"测速已让位于连接恢复，请稍后再测"));return;}try{if(!ready)throw new IOException("请先连接内置网络");scanAndSelect(false);verifyExit();report("测速完成 · "+display(currentEntry));main.post(()->cb.done(true,message));}catch(Exception e){if(work.cancelled&&!(e instanceof ExitMismatch)&&cancelledVerifiedRouteCurrent()){main.post(()->cb.done(false,"测速已让位于连接恢复，请稍后再测"));}else{if(!retainVerifiedRoute(e)){stopNow();if(e instanceof ExitMismatch)recoveryBlocked=true;report("测速或出口验证失败，连接已停止；不会改为直连");}main.post(()->cb.done(false,message));}}finally{finishMaintenance(work);}});}


  void select(String name,Callback cb){cancelMaintenance();worker.execute(()->{String old=currentEntry;try{if(!ready||!names.contains(name))throw new IOException();selectNow(name);ProbeResult result=probeMeasured("FixedExit",name);if(result.delay<0||!probeCurrent(result))throw new IOException();publishCurrentProbe(result);verifyExit();report("已切换入口 · "+display(currentEntry));main.post(()->cb.done(true,message));}catch(Exception e){try{if(old.isEmpty())throw new IOException();selectNow(old);verifyExit();report("该入口不可用，已恢复原入口");}catch(Exception restore){stopNow();report("出口无法通过核实，连接已停止");}main.post(()->cb.done(false,message));}});}
  /** A bounded HEAD on the current protected route after primary failure only.
   * No cookies, redirects, candidate selection, response body or application replay. */
  NetworkHealthPolicy.TargetEvidence secondaryHealth(ProbeResult primary)throws Exception{
    maintenanceCheck();if(routeBusy()||!probeCurrent(primary)||!verifiedRouteCurrent())return NetworkHealthPolicy.TargetEvidence.INCONCLUSIVE;
    HttpURLConnection c=openProbeConnection(websiteUrl(),proxyPort);track(c);
    try{
      c.setRequestMethod("HEAD");c.setConnectTimeout(3000);c.setReadTimeout(3000);c.setInstanceFollowRedirects(false);c.setUseCaches(false);
      c.setRequestProperty("User-Agent","PocketChat-RouteHealth/1.6");int code=c.getResponseCode();
      maintenanceCheck();if(!probeCurrent(primary)||!verifiedRouteCurrent())return NetworkHealthPolicy.TargetEvidence.INCONCLUSIVE;
      healthTargetCode=code;return NetworkHealthPolicy.response(code);
    }catch(IOException unavailable){maintenanceCheck();if(Thread.currentThread().isInterrupted()||!probeCurrent(primary)||!verifiedRouteCurrent())return NetworkHealthPolicy.TargetEvidence.INCONCLUSIVE;return NetworkHealthPolicy.failure(unavailable);}
    finally{untrack(c);c.disconnect();}
  }
  void health(){
    if(!ready||starting||routeBusy())return;
    try{
      maintenanceCheck();if(!coreAlive())throw new IOException("内置网络进程已退出");
      if(exitCheckFailures>0){
        if(!verifiedRouteCurrent())throw new IOException("网络实例已变化，请重新核验出口");
        // Do not let an unrelated Google probe choose a new, unknown route while
        // the exit detector is unavailable. Its recovery is checked first.
        if(android.os.SystemClock.elapsedRealtime()<nextExitCheckAt)return;
        verifyExit();
      }
      ProbeResult result=probeMeasured("FixedExit",currentEntry);maintenanceCheck();if(!probeCurrent(result))return;int delay=result.delay;long now=System.currentTimeMillis();publishCurrentProbe(result);
      if(delay<0){
        healthTargetCode=0;NetworkHealthPolicy.TargetEvidence target=secondaryHealth(result);maintenanceCheck();
        NetworkHealthPolicy.Assessment assessed=NetworkHealthPolicy.assess(routeBusy(),probeCurrent(result)&&verifiedRouteCurrent(),false,target,failures);
        if(assessed.action==NetworkHealthPolicy.Action.DEFER)return;failures=assessed.consecutiveFailures;healthObservedAt=now;
        healthStatus=target==NetworkHealthPolicy.TargetEvidence.HTTP_RESPONSE?"primary-detector-unavailable":assessed.action==NetworkHealthPolicy.Action.SUSPECT?"suspect":"transport-unavailable";
        // Website restrictions/TLS ambiguity are not failed proxy quality samples.
        if(target==NetworkHealthPolicy.TargetEvidence.TRANSPORT_UNAVAILABLE)recordProbe(result,now);
        if(assessed.action==NetworkHealthPolicy.Action.RECOVER){if(settings!=null&&"manual".equals(settings.optString("entryMode")))throw new IOException("指定入口与目标网站连续连接失败，请重连或编辑网络");firstVerifiedRoute(currentEntry);maintenanceCheck();if(routeBusy())return;failures=0;healthStatus="recovered";report("已自动恢复入口 · "+display(currentEntry));}
        else if(assessed.action==NetworkHealthPolicy.Action.HEALTHY&&now-lastVerified>=NetworkOptimizationPolicy.ACTIVE_INTERVAL)verifyExit();return;
      }
      recordProbe(result,now);healthStatus="healthy";healthTargetCode=0;healthObservedAt=now;
      failures=0;if(now-lastVerified>=NetworkOptimizationPolicy.ACTIVE_INTERVAL)verifyExit();
      if((lowLatency()||settings!=null&&settings.optString("entryMode").isEmpty())&&now-lastScan>=NetworkOptimizationPolicy.SCAN_INTERVAL&&!backgroundIdle()){
        List<String> batch=NetworkOptimizationPolicy.batch(names,rankedRoutes(),currentEntry,scanCursor++);scanSubset(batch,false,true);
      }
      maintenanceCheck();if(lowLatency()&&!backgroundIdle()){String server=dns.next(System.currentTimeMillis());if(!server.isEmpty()){int ms=-1;try{ms=NetworkDns.measure(this,server);}catch(IOException unavailable){maintenanceCheck();}maintenanceCheck();dns.record(server,ms,System.currentTimeMillis());}}
    }catch(Exception e){if(maintenanceCancelled()&&!(e instanceof ExitMismatch)&&cancelledVerifiedRouteCurrent())return;if(!retainVerifiedRoute(e)){stopNow();if(e instanceof ExitMismatch)recoveryBlocked=true;report(e instanceof IOException?e.getMessage():"内置网络已停止；请检查节点与固定出口");}}
  }
  void stop(){cancelMaintenance();worker.execute(()->stopNow());}
  boolean stopNow(){if(maintenanceCancelled())Thread.interrupted();invalidateVerifiedRoute();ready=false;currentProbe=null;latencyReading=new JSONObject();websiteResult=new JSONObject();lastProbeDuration=0;lastProbeDurationAt=0;lastProbeEntry="";if(transport!=null){try{return !transport.call("stop","").optBoolean("alive");}catch(Exception e){message="独立网络停止尚未确认";return false;}}else{if(process!=null){process.destroy();process=null;}cleanupOwnedPid();return !coreAlive();}}
  void cleanupOwnedPid(){try{File pidFile=new File(root,"core.pid");if(!pidFile.exists())return;int pid;try(FileInputStream in=new FileInputStream(pidFile)){pid=Integer.parseInt(J.text(in,32).trim());}if(pid<=1||pid==android.os.Process.myPid())return;String cmd,status;try(FileInputStream in=new FileInputStream("/proc/"+pid+"/cmdline")){cmd=J.text(in,8192);}try(FileInputStream in=new FileInputStream("/proc/"+pid+"/status")){status=J.text(in,8192);}if(cmd.contains("libmihomo.so")&&cmd.contains(root.getAbsolutePath())&&status.matches("(?s).*Uid:\\s+"+android.os.Process.myUid()+"\\s+.*"))android.os.Process.killProcess(pid);pidFile.delete();}catch(Exception ignored){}}
  static String display(String name){return name.startsWith("Entry|")?name.substring(6):name;}
  static String hash(String s){try{byte[] b=MessageDigest.getInstance("SHA-256").digest(s.getBytes(StandardCharsets.UTF_8));StringBuilder out=new StringBuilder();for(byte x:b)out.append(String.format(Locale.ROOT,"%02x",x&255));return out.toString();}catch(java.security.NoSuchAlgorithmException impossible){throw new IllegalStateException(impossible);}}
}
