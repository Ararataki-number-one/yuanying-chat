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
  final RouteQuality quality,websiteQuality;final NetworkDns dns;volatile JSONObject websiteResult=new JSONObject();volatile int webProbePort;int scanCursor;volatile String activeDns="";final TrafficMonitor traffic;volatile boolean measuringLatency=false;volatile long lastManualProbe=-5000;final File root;volatile boolean ready=false,starting=false;volatile String message="未连接",currentEntry="",exitIp="",observedExitIp="";volatile JSONArray results=new JSONArray();
  volatile boolean recoveryBlocked=false;boolean restartQueued=false;final List<Callback> startWaiters=new ArrayList<>();volatile long lastVerified=0,lastObserved=0;
  java.lang.Process process;JSONObject settings;volatile int controllerPort,proxyPort;int failures;volatile String token="";String fingerprint="";List<String> names=new ArrayList<>();long lastScan=0;int totalEntries=0;volatile long startupDuration=0;volatile String startupPath="";volatile long startupBeganAt=0,coreDuration=0,providerDuration=0,exitCheckDuration=0;volatile boolean startupCached=false;
  static final String MEASUREMENT_PROFILE="unified-delay-v1";volatile long lastProbeDuration=0,lastProbeDurationAt=0;volatile String lastProbeEntry="";
  static final String PROBE="https://www.gstatic.com/generate_204";
  NativeNetwork(Context c){this(c,new File(c.getNoBackupFilesDir(),"network-runtime"),true);}
  NativeNetwork(Context c,File directory,boolean monitor){context=c.getApplicationContext();quality=new RouteQuality(context);websiteQuality=new RouteQuality(context,"website-quality");dns=new NetworkDns(context);traffic=new TrafficMonitor(this);secrets=new SecretStore(c);root=directory;root.mkdirs();if(monitor)worker.scheduleWithFixedDelay(()->runHealth(),30,30,TimeUnit.SECONDS);}
  static void validate(JSONObject s)throws Exception{URI u=new URI(s.optString("subscriptionUrl"));if(!"https".equals(u.getScheme())||u.getHost()==null||u.getUserInfo()!=null)throw new IOException("请填写 HTTPS 格式的 Clash / Mihomo 订阅地址");String host=s.optString("exitHost");if(host.isEmpty()||host.matches(".*[\\s/\\\\@].*"))throw new IOException("请填写有效的固定出口地址");int port=s.optInt("exitPort");if(port<1||port>65535)throw new IOException("固定出口端口应为 1–65535");}
  void report(String text){message=text;ChatSession s=ChatSession.peek();WindowNetworkState.save(context,s,this);if(s!=null)main.post(()->s.networkStatus(text,ready));}
  String proxy(){return "http://127.0.0.1:"+proxyPort;}
  static int freePort()throws Exception{try(ServerSocket s=new ServerSocket(0,0,InetAddress.getByName("127.0.0.1"))){return s.getLocalPort();}}
  boolean coreAlive(){return process!=null&&process.isAlive();}
  static class ExitMismatch extends IOException{ExitMismatch(){super("出口 IP 与保存记录不一致，连接已停止；请检查固定出口设置");}}
  void start(Callback callback){startOperation(callback,0);}
  void restart(Callback callback){recoveryBlocked=false;startOperation(callback,2);}
  void recover(Callback callback){if(recoveryBlocked){main.post(()->callback.done(false,message));return;}startOperation(callback,1);}
  synchronized void startOperation(Callback callback,int mode){if(mode==0&&ready&&coreAlive()){main.post(()->callback.done(true,message));return;}startWaiters.add(callback);if(starting){if(mode==2)restartQueued=true;return;}starting=true;cancelMaintenance();worker.execute(()->runStartOperation(mode));
  }
  void runStartOperation(int mode){boolean ok=false;try{if(mode==1&&recoveryBlocked)throw new ExitMismatch();if(mode==1&&ready&&coreAlive()&&configurationMatches()){report("正在检查代理链与固定出口…");try{verifyExit();ok=true;report("手机独立网络已连接 · "+display(currentEntry));}catch(ExitMismatch e){throw e;}catch(Exception transientFailure){ok=false;}}
      if(!ok){stopNow();startNow();ok=true;}
    }catch(Exception e){stopNow();if(e instanceof ExitMismatch)recoveryBlocked=true;report(e instanceof IOException&&e.getMessage()!=null?e.getMessage():"应用网络连接失败，请检查节点与固定出口");}
    final boolean success=ok;final String detail=message;final List<Callback> callbacks;synchronized(this){if(restartQueued){restartQueued=false;worker.execute(()->runStartOperation(2));return;}starting=false;callbacks=new ArrayList<>(startWaiters);startWaiters.clear();}main.post(()->{for(Callback cb:callbacks)cb.done(success,detail);});
  }
  void startNow()throws Exception{
    long startupBegan=android.os.SystemClock.elapsedRealtime();startupBeganAt=startupBegan;startupDuration=coreDuration=providerDuration=0;startupPath="";
    settings=secrets.settings();validate(settings);cleanupOwnedPid();token=UUID.randomUUID().toString()+UUID.randomUUID();controllerPort=freePort();proxyPort=freePort();webProbePort=freePort();
    fingerprint=hash(settings.optString("exitHost")+":"+settings.optInt("exitPort")+":"+settings.optString("exitUser")+":"+settings.optString("exitPassword"));
    String scope=fingerprint+":"+hash(settings.optString("subscriptionUrl"));quality.configure(MEASUREMENT_PROFILE+":"+scope);websiteQuality.configure("chatgpt-head-v1:"+scope);dns.configure(scope);activeDns=dns.primary(System.currentTimeMillis());byte[] cached=secrets.get("subscription");JSONObject meta=J.parse(new String(Optional.ofNullable(secrets.get("subscription-meta")).orElse(new byte[0]),StandardCharsets.UTF_8));
    boolean fromCache=cached!=null&&meta.optString("urlHash").equals(hash(settings.optString("subscriptionUrl")));startupCached=fromCache;
    if(fromCache)try(FileOutputStream out=new FileOutputStream(new File(root,"subscription.yaml"))){out.write(cached);}
    J.write(new File(root,"config.json"),config(true,!fromCache).toString().replace("\\/","/"));
    report(fromCache?"正在从加密缓存启动手机独立网络…":"正在下载订阅并启动手机独立网络…");
    launchCore();
    coreDuration=android.os.SystemClock.elapsedRealtime()-startupBegan;long providerBegan=android.os.SystemClock.elapsedRealtime();
    JSONArray nodes=readProvider();names=new ArrayList<>(providerNames(nodes));
    long updated=fromCache?meta.optLong("updatedAt"):System.currentTimeMillis();
    File provider=new File(root,"subscription.yaml");if(provider.exists())try(FileInputStream in=new FileInputStream(provider)){secrets.put("subscription",J.read(in,16*1024*1024));secrets.put("subscription-meta",J.obj("urlHash",hash(settings.optString("subscriptionUrl")),"updatedAt",updated).toString().getBytes(StandardCharsets.UTF_8));}
    secrets.put("subscription-ui",J.obj("urlHash",hash(settings.optString("subscriptionUrl")),"nodes",new JSONArray(names)).toString().getBytes(StandardCharsets.UTF_8));
    EntrySelection.validate(settings,names);names=EntrySelection.allowed(settings,names);if(lowLatency())names=rankedRoutes();
    String remembered=context.getSharedPreferences("chat",0).getString("lastGoodEntry","");if(names.remove(remembered))names.add(0,remembered);totalEntries=names.size();if(names.isEmpty())throw new IOException("订阅未读到可用节点；请确认它是 Clash / Mihomo 格式");if(names.size()>64)names=new ArrayList<>(names.subList(0,64));
    J.write(new File(root,"config.json"),config(false,false).toString().replace("\\/","/"));api("PUT","/configs?force=true",J.obj("path",new File(root,"config.json").getAbsolutePath()),5000);
    providerDuration=android.os.SystemClock.elapsedRealtime()-providerBegan;chooseStartupRoute();ready=true;recoveryBlocked=false;failures=0;startupDuration=android.os.SystemClock.elapsedRealtime()-startupBegan;report("手机独立网络已连接 · "+display(currentEntry));
  }

  // A successful HTTPS exit check already proves that the entire selected chain works.
  // Keep the persisted exit-IP gate, and avoid probing every entry before trying it.
  void chooseStartupRoute()throws Exception{
    results=new JSONArray();String remembered=context.getSharedPreferences("chat",0).getString("lastGoodEntry","");
    if(names.contains(remembered)){
      report("正在恢复上次可用入口并核实固定出口…");
      try{selectNow(remembered);verifyExit();startupPath="remembered";lastScan=System.currentTimeMillis();return;}
      catch(ExitMismatch mismatch){throw mismatch;}
      catch(Exception unavailable){quality.record(remembered,-1,System.currentTimeMillis());}
    }
    firstVerifiedRoute(remembered);
  }
  static final class RouteProbe{final String name;final int delay;RouteProbe(String n,int d){name=n;delay=d;}}
  RouteProbe startupProbe(String name,int index,String epoch){
    if(!epoch.equals(token)||Thread.currentThread().isInterrupted())return new RouteProbe(name,-1);
    try{api("PUT","/proxies/ProbeEntry"+index,J.obj("name",name),3000);if(!epoch.equals(token)||Thread.currentThread().isInterrupted())return new RouteProbe(name,-1);return new RouteProbe(name,probe("ProbeExit"+index));}catch(Exception unavailable){return new RouteProbe(name,-1);}
  }
  void firstVerifiedRoute(String rejected)throws Exception{
    report("正在寻找可用入口并核实固定出口…");
    final List<String> candidates=new ArrayList<>(names);final String epoch=token;
    CompletionService<RouteProbe> completed=new ExecutorCompletionService<>(probes);List<Future<RouteProbe>> active=new ArrayList<>();
    JSONArray measured=new JSONArray();int next=0,running=0;long deadline=android.os.SystemClock.elapsedRealtime()+startupSearchBudgetMs();
    try{
      while(next<candidates.size()||running>0){maintenanceCheck();
        while(running<4&&next<candidates.size()){
          final int index=next++;final String name=candidates.get(index);if(name.equals(rejected))continue;
          Future<RouteProbe> task=completed.submit(()->startupProbe(name,index,epoch));active.add(task);NetworkWork work=maintenance.get();if(work!=null)work.add(task);running++;
        }
        if(running==0)break;
        long remaining=deadline-android.os.SystemClock.elapsedRealtime();Future<RouteProbe> finished=remaining>0?completed.poll(remaining,TimeUnit.MILLISECONDS):null;
        if(finished==null)throw new IOException("入口检查超时，请重试；不会改为直连");
        active.remove(finished);RouteProbe r=finished.get();running--;maintenanceCheck();
        if(!epoch.equals(token))throw new IOException("网络连接已改变，请重试");
        long now=System.currentTimeMillis();quality.record(r.name,r.delay,now);measured.put(J.obj("name",display(r.name),"internalName",r.name,"delay",r.delay));results=measured;
        if(r.delay<=0)continue;
        try{selectNow(r.name);verifyExit();startupPath="first-verified";lastScan=System.currentTimeMillis();return;}
        catch(ExitMismatch mismatch){throw mismatch;}
        catch(Exception unavailable){quality.record(r.name,-1,System.currentTimeMillis());}
      }
      throw new IOException("全部入口的完整代理链均不可用；不会改为直连");
    }finally{for(Future<RouteProbe> task:active)task.cancel(true);}
  }
  long startupSearchBudgetMs(){return 45000;}
  void launchCore()throws Exception{
    File binary=new File(context.getApplicationInfo().nativeLibraryDir,"libmihomo.so");if(!binary.isFile())throw new IOException("该手机架构没有可用的内置网络内核");
    process=new ProcessBuilder("/system/bin/sh","-c","umask 077; echo $$ > \"$1/core.pid\"; exec \"$2\" -d \"$1\" -f \"$1/config.json\"","pocket-core",root.getAbsolutePath(),binary.getAbsolutePath()).redirectErrorStream(true).start();
    final java.lang.Process owned=process;new Thread(()->{try(InputStream in=owned.getInputStream()){byte[] b=new byte[4096];while(in.read(b)>=0){}}catch(Exception ignored){}},"core-output-discard").start();
    long deadline=System.currentTimeMillis()+20000;for(int i=0;i<100;i++){if(System.currentTimeMillis()>deadline)throw new IOException("内置代理启动超时");if(!process.isAlive())throw new IOException("安卓代理内核启动后退出");try{api("GET","/version",null,2000);return;}catch(Exception e){Thread.sleep(150);}}throw new IOException("内置代理控制服务未就绪");
  }
  JSONArray readProvider()throws Exception{
    long deadline=System.currentTimeMillis()+35000;for(int i=0;i<60&&System.currentTimeMillis()<deadline;i++){if(process==null||!process.isAlive())throw new IOException("订阅解析进程已退出");try{JSONArray nodes=api("GET","/providers/proxies/Subscription",null,3000).optJSONArray("proxies");if(nodes!=null&&nodes.length()>0)return nodes;}catch(Exception ignored){}Thread.sleep(500);}throw new IOException("订阅未读到可用节点，请检查订阅格式或网络");
  }
  static List<String> providerNames(JSONArray nodes){List<String> out=new ArrayList<>();for(int i=0;i<nodes.length();i++){JSONObject p=nodes.optJSONObject(i);if(p!=null&&p.optString("name").startsWith("Entry|")&&!out.contains(p.optString("name")))out.add(p.optString("name"));}return out;}
  interface PreviewCallback{void done(boolean ok,String message,JSONArray names,byte[] provider);}
  static void previewSubscription(Context c,String url,byte[] cache,PreviewCallback callback){
    // A short-lived parser instance has no listener, account document, or active route.
    NativeNetwork reader=new NativeNetwork(c,new File(c.getNoBackupFilesDir(),"subscription-preview-"+UUID.randomUUID()),false);
    reader.worker.execute(()->{JSONArray nodes=new JSONArray();byte[] provider=null;String error="";try{
      reader.settings=J.obj("subscriptionUrl",url);reader.token=UUID.randomUUID().toString();reader.controllerPort=freePort();reader.proxyPort=freePort();
      if(cache!=null)try(FileOutputStream out=new FileOutputStream(new File(reader.root,"subscription.yaml"))){out.write(cache);}
      JSONObject config=reader.config(true,cache==null);config.put("proxies",new JSONArray());config.put("proxy-groups",new JSONArray());
      J.write(new File(reader.root,"config.json"),config.toString().replace("\\/","/"));reader.launchCore();nodes=new JSONArray(providerNames(reader.readProvider()));if(nodes.length()==0)throw new IOException("订阅没有可选入口");
      try(FileInputStream in=new FileInputStream(new File(reader.root,"subscription.yaml"))){provider=J.read(in,16*1024*1024);}
    }catch(Exception e){error=e instanceof IOException&&e.getMessage()!=null?e.getMessage():"订阅读取失败，已保留原配置";}finally{reader.stopNow();reader.probes.shutdownNow();reader.closers.shutdownNow();reader.traffic.reader.shutdownNow();reader.worker.shutdown();deletePreview(reader.root);}
      final JSONArray result=nodes;final byte[] bytes=provider;final String reason=error;reader.main.post(()->callback.done(reason.isEmpty(),reason,result,bytes));
    });
  }
  static void deletePreview(File directory){File[] files=directory.listFiles();if(files!=null)for(File f:files){if(f.isDirectory())deletePreview(f);else f.delete();}directory.delete();}
  void configureProbeEntries()throws Exception{for(int i=0;i<names.size();i++)api("PUT","/proxies/ProbeEntry"+i,J.obj("name",names.get(i)),3000);}

  boolean configurationMatches(){try{if(settings==null)return false;JSONObject now=secrets.settings();for(String key:new String[]{"subscriptionUrl","exitHost","exitPort","exitUser","exitPassword","entryMode","entryPool","entry"})if(!settings.optString(key).equals(now.optString(key)))return false;return true;}catch(Exception e){return false;}}
  synchronized void cancelMaintenance(){maintenanceGeneration++;lastMaintenanceAt=android.os.SystemClock.elapsedRealtime();NetworkWork work=backgroundWork;if(work!=null)work.cancel(closers);}
  synchronized NetworkWork beginMaintenance(long expected){if(starting||expected!=maintenanceGeneration)return null;NetworkWork work=new NetworkWork();backgroundWork=work;maintenance.set(work);return work;}
  void finishMaintenance(NetworkWork work){work.finish();maintenance.remove();synchronized(this){if(backgroundWork==work)backgroundWork=null;}Thread.interrupted();}
  void maintenanceCheck()throws InterruptedIOException{NetworkWork work=maintenance.get();if(work!=null){if(routeBusy())work.cancel(closers);work.check();}}
  boolean maintenanceCancelled(){NetworkWork work=maintenance.get();return work!=null&&work.cancelled;}
  void track(HttpURLConnection c)throws InterruptedIOException{NetworkWork work=maintenance.get();if(work!=null)work.add(c);}
  void untrack(HttpURLConnection c){NetworkWork work=maintenance.get();if(work!=null)work.remove(c);}
  boolean backgroundIdle(){ChatSession s=ChatSession.peek();return s!=null&&!s.uiVisible&&!s.browserWorkActive();}
  void runHealth(){
    if(!ready||starting)return;
    if(!coreAlive()){stopNow();report("内置网络进程已退出，请重新连接");return;}
    if(routeBusy()){cancelMaintenance();return;}
    long now=android.os.SystemClock.elapsedRealtime();if(now-lastMaintenanceAt<(backgroundIdle()?NetworkOptimizationPolicy.BACKGROUND_INTERVAL:NetworkOptimizationPolicy.ACTIVE_INTERVAL))return;
    NetworkWork work=beginMaintenance(maintenanceGeneration);if(work==null)return;lastMaintenanceAt=now;
    try{health();}finally{finishMaintenance(work);WindowNetworkState.save(context,ChatSession.peek(),this);}
  }
  JSONObject group(String name,String filter){JSONObject g=J.obj("name",name,"type","select","proxies",J.arr("REJECT"),"use",J.arr("Subscription"),"empty-fallback","REJECT","interval",0,"hidden",true);if(filter!=null)try{g.put("filter",filter);}catch(Exception ignored){}return g;}
  JSONObject exit(String name,String group){return J.obj("name",name,"type","socks5","server",settings.optString("exitHost"),"port",settings.optInt("exitPort"),"username",settings.optString("exitUser"),"password",settings.optString("exitPassword"),"udp",false,"dialer-proxy",group);}
  static String literalRegex(String s){StringBuilder b=new StringBuilder();for(char c:s.toCharArray()){if("\\.+*?()|[]{}^$".indexOf(c)>=0)b.append('\\');b.append(c);}return b.toString();}
  JSONObject config(boolean bootstrap,boolean download){
    JSONObject provider=J.obj("type",download?"http":"file","path","./subscription.yaml","health-check",J.obj("enable",false),"override",J.obj("additional-prefix","Entry|"));
    if(download)try{provider.put("url",settings.optString("subscriptionUrl"));provider.put("interval",0);provider.put("proxy","DIRECT");provider.put("size-limit",16*1024*1024);provider.put("header",J.obj("User-Agent",J.arr("mihomo")));}catch(Exception ignored){}
    JSONArray proxies=J.arr(exit("FixedExit","EntryChoice")),groups=J.arr(group("EntryChoice",!bootstrap&&!settings.optString("entryMode").isEmpty()?EntrySelection.filter(names):null));if(!bootstrap){groups.put(group("WebProbeEntry",EntrySelection.filter(names)));proxies.put(exit("WebProbeExit","WebProbeEntry"));}if(!bootstrap)for(int i=0;i<names.size();i++){groups.put(group("ProbeEntry"+i,"^(?:"+literalRegex(names.get(i))+")$"));proxies.put(exit("ProbeExit"+i,"ProbeEntry"+i));}
    return J.obj("port",0,"socks-port",0,"mixed-port",0,"redir-port",0,"tproxy-port",0,"allow-lan",false,"bind-address","127.0.0.1","mode","rule","unified-delay",true,"tcp-concurrent",true,"log-level","silent","ipv6",false,"external-controller","127.0.0.1:"+controllerPort,"secret",token,
      "external-controller-cors",J.obj("allow-origins",new JSONArray(),"allow-private-network",false),"profile",J.obj("store-selected",false,"store-fake-ip",false),"tun",J.obj("enable",false),"sniffer",J.obj("enable",false),"geo-auto-update",false,
      "dns",J.obj("enable",true,"listen","127.0.0.1:0","ipv6",false,"enhanced-mode","redir-host","cache-algorithm","arc","default-nameserver",J.arr("https://223.5.5.5/dns-query","https://223.6.6.6/dns-query"),"nameserver",bootstrap?J.arr(NetworkDns.SERVERS[0],NetworkDns.SERVERS[1]):J.arr(dns.primary(System.currentTimeMillis())+"#FixedExit",dns.backup(System.currentTimeMillis())+"#FixedExit"),"proxy-server-nameserver",J.arr("https://dns.alidns.com/dns-query","https://doh.pub/dns-query")),
      "proxy-providers",J.obj("Subscription",provider),"proxies",proxies,"proxy-groups",groups,"rules",J.arr("MATCH,REJECT"),"listeners",bootstrap?new JSONArray():J.arr(J.obj("name","PocketOnly","type","mixed","listen","127.0.0.1","port",proxyPort,"udp",false,"proxy","FixedExit"),J.obj("name","WebsiteCheck","type","mixed","listen","127.0.0.1","port",webProbePort,"udp",false,"proxy","WebProbeExit")));
  }
  JSONObject api(String method,String path,JSONObject body,int timeout)throws Exception{
    maintenanceCheck();if(Thread.currentThread().isInterrupted())throw new InterruptedIOException("网络检查已取消");
    HttpURLConnection c=(HttpURLConnection)new URL("http://127.0.0.1:"+controllerPort+path).openConnection(Proxy.NO_PROXY);track(c);
    try{c.setRequestMethod(method);c.setConnectTimeout(timeout);c.setReadTimeout(timeout);c.setInstanceFollowRedirects(false);c.setRequestProperty("Authorization","Bearer "+token);
      if(body!=null){c.setDoOutput(true);c.setRequestProperty("Content-Type","application/json");try(OutputStream out=c.getOutputStream()){out.write(body.toString().getBytes(StandardCharsets.UTF_8));}}
      int code=c.getResponseCode();maintenanceCheck();if(code<200||code>=300)throw new IOException("内置网络控制请求失败");try(InputStream in=c.getInputStream()){return J.parse(J.text(in,8*1024*1024));}
    }finally{untrack(c);c.disconnect();}
  }
  int probe(String name){long began=System.currentTimeMillis(),monotonic=android.os.SystemClock.elapsedRealtime();String entry=currentEntry,epoch=token,target=probeUrl();try{int delay=api("GET","/proxies/"+URLEncoder.encode(name,"UTF-8")+"/delay?timeout=8000&expected=204&url="+URLEncoder.encode(target,"UTF-8"),null,11000).optInt("delay",-1);if(!epoch.equals(token)||Thread.currentThread().isInterrupted())return -1;long duration=android.os.SystemClock.elapsedRealtime()-monotonic;JSONObject info=api("GET","/proxies/"+URLEncoder.encode(name,"UTF-8"),null,3000).optJSONObject("extra");JSONObject p=info==null?null:info.optJSONObject(target);JSONArray history=p==null?null:p.optJSONArray("history");if(delay<=0||p==null||!p.optBoolean("alive")||history==null||history.length()==0)return -1;JSONObject latest=history.getJSONObject(history.length()-1);if(Instant.parse(latest.getString("time")).toEpochMilli()<began-1500)return -1;if(name.equals("FixedExit")&&entry.equals(currentEntry)&&epoch.equals(token)){lastProbeEntry=entry;lastProbeDuration=duration;lastProbeDurationAt=System.currentTimeMillis();}return delay;}catch(Exception e){return -1;}}
  String probeUrl(){return PROBE;}
  String exitCheckUrl(){return "https://api.ipify.org?format=json";}
  boolean lowLatency(){return settings!=null&&"latency".equals(settings.optString("entryMode"));}
  boolean routeBusy(){ChatSession s=ChatSession.peek();return s!=null&&(s.pending!=null||s.submitting||s.operation||s.transferActive||s.uploading()||s.navigating||s.state.optBoolean("busy"));}
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
      maintenanceCheck();List<Future<Integer>> tasks=new ArrayList<>();List<String> round=batch.subList(offset,Math.min(offset+2,batch.size()));
      try{for(String name:round){final int index=names.indexOf(name);if(index<0)throw new IOException("入口池已变化");api("PUT","/proxies/ProbeEntry"+index,J.obj("name",name),3000);Future<Integer> task=probes.submit(()->{if(work!=null)maintenance.set(work);try{return probe("ProbeExit"+index);}finally{maintenance.remove();}});tasks.add(task);if(work!=null)work.add(task);}
        for(int i=0;i<tasks.size();i++){int delay=tasks.get(i).get();maintenanceCheck();String name=round.get(i);long now=System.currentTimeMillis();quality.record(name,delay,now);JSONObject stats=quality.stats(name,now);measured.put(J.obj("name",display(name),"internalName",name,"delay",delay,"samples",stats.optInt("samples"),"successRate",stats.optDouble("rate"),"mean",stats.optLong("mean"),"jitter",stats.optLong("jitter"),"score",stats.optDouble("score")));if(delay>0)good++;}
      }finally{for(Future<Integer> task:tasks)if(!task.isDone())task.cancel(true);}
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
  void selectNow(String name)throws Exception{api("PUT","/proxies/EntryChoice",J.obj("name",name),3000);if(!name.equals(api("GET","/proxies/EntryChoice",null,3000).optString("now")))throw new IOException("入口切换未得到确认");currentEntry=name;quality.selected(name,System.currentTimeMillis());websiteQuality.selected(name,System.currentTimeMillis());websiteResult=new JSONObject();}
  String verifyExit()throws Exception{long began=android.os.SystemClock.elapsedRealtime();try{return verifyExitRequest();}finally{exitCheckDuration=android.os.SystemClock.elapsedRealtime()-began;}}
  String verifyExitRequest()throws Exception{maintenanceCheck();HttpURLConnection c=(HttpURLConnection)new URL(exitCheckUrl()).openConnection(new Proxy(Proxy.Type.HTTP,new InetSocketAddress("127.0.0.1",proxyPort)));track(c);c.setConnectTimeout(10000);c.setReadTimeout(10000);String ip;boolean reusable=false;try{if(c.getResponseCode()!=200)throw new IOException();try(InputStream in=c.getInputStream()){ip=new JSONObject(J.text(in,4096)).optString("ip");}reusable=true;}finally{untrack(c);if(!reusable)c.disconnect();}maintenanceCheck();if(!ip.matches("[0-9.]+")&&!ip.matches("[0-9a-fA-F:]+"))throw new IOException("无法核实固定出口 IP");observedExitIp=ip;lastObserved=System.currentTimeMillis();byte[] stored=secrets.get("exit-baseline");JSONObject old=stored==null?new JSONObject():J.parse(new String(stored,StandardCharsets.UTF_8));if(fingerprint.equals(old.optString("fingerprint"))&&!ip.equals(old.optString("ip"))){recoveryBlocked=true;if(exitIp.isEmpty())exitIp=old.optString("ip");throw new ExitMismatch();}if(!fingerprint.equals(old.optString("fingerprint")))secrets.put("exit-baseline",J.obj("fingerprint",fingerprint,"ip",ip).toString().getBytes(StandardCharsets.UTF_8));exitIp=ip;lastVerified=System.currentTimeMillis();context.getSharedPreferences("chat",0).edit().putString("lastGoodEntry",currentEntry).apply();return ip;}
  synchronized void measureLatency(Callback cb){
    long now=android.os.SystemClock.elapsedRealtime();if(measuringLatency||now-lastManualProbe<5000){main.post(()->cb.done(false,"请稍后再测"));return;}if(!ready||starting||!coreAlive()){main.post(()->cb.done(false,"请先恢复应用网络"));return;}
    measuringLatency=true;lastManualProbe=now;cancelMaintenance();long generation=maintenanceGeneration;
    worker.execute(()->{boolean ok=false;String text="线路暂未通过探测，可稍后再试";NetworkWork work=beginMaintenance(generation);
      try{if(work==null)throw new IOException("连接已变化");if(ready&&!starting&&coreAlive()){String entry=currentEntry,epoch=token;int delay=probe("FixedExit");maintenanceCheck();if(ready&&entry.equals(currentEntry)&&epoch.equals(token)){quality.record(entry,delay,System.currentTimeMillis());ok=delay>0;if(ok){JSONObject site=measureWebsite(entry);text="线路 "+delay+" ms · "+WebsiteProbe.line(site,System.currentTimeMillis());}}}}
      catch(Exception cancelled){ok=false;text="测速已暂停，当前操作继续进行";}finally{if(work!=null)finishMaintenance(work);measuringLatency=false;WindowNetworkState.save(context,ChatSession.peek(),this);}
      final boolean success=ok;final String message=text;main.post(()->cb.done(success,message));});
  }
  void checkExit(Callback cb){cancelMaintenance();worker.execute(()->{try{if(!ready||!coreAlive())throw new IOException("请先恢复应用网络");verifyExit();main.post(()->cb.done(true,"出口已核实"));}catch(Exception e){stopNow();if(e instanceof ExitMismatch)recoveryBlocked=true;report(e.getMessage()==null?"出口核实失败":e.getMessage());main.post(()->cb.done(false,message));}});}
  void beforeSend(Callback cb){cancelMaintenance();worker.execute(()->{try{if(!ready||process==null||!process.isAlive())throw new IOException("内置网络尚未连接");verifyExit();main.post(()->cb.done(true,""));}catch(Exception e){stopNow();if(e instanceof ExitMismatch)recoveryBlocked=true;report(e instanceof IOException?e.getMessage():"固定出口验证失败");main.post(()->cb.done(false,message));}});}
  void rescan(Callback cb){long generation=maintenanceGeneration;worker.execute(()->{NetworkWork work=beginMaintenance(generation);if(work==null){main.post(()->cb.done(false,"测速已让位于连接恢复，请稍后再测"));return;}try{if(!ready)throw new IOException("请先连接内置网络");scanAndSelect(false);verifyExit();report("测速完成 · "+display(currentEntry));main.post(()->cb.done(true,message));}catch(Exception e){if(work.cancelled&&!(e instanceof ExitMismatch)){main.post(()->cb.done(false,"测速已让位于连接恢复，请稍后再测"));}else{stopNow();if(e instanceof ExitMismatch)recoveryBlocked=true;report("测速或出口验证失败，连接已停止；不会改为直连");main.post(()->cb.done(false,message));}}finally{finishMaintenance(work);}});}

  void refresh(Callback cb){cancelMaintenance();worker.execute(()->{try{JSONObject current=secrets.settings();validate(current);HttpURLConnection c=(HttpURLConnection)new URL(current.optString("subscriptionUrl")).openConnection(Proxy.NO_PROXY);c.setConnectTimeout(15000);c.setReadTimeout(20000);c.setRequestProperty("User-Agent","mihomo");byte[] data;try{if(c.getResponseCode()!=200)throw new IOException();try(InputStream in=c.getInputStream()){data=J.read(in,16*1024*1024);}}finally{c.disconnect();}String text=new String(data,StandardCharsets.UTF_8);if(!text.contains("proxies:")&&!text.trim().startsWith("{"))throw new IOException();byte[] old=secrets.get("subscription");secrets.put("subscription",data);secrets.put("subscription-meta",J.obj("urlHash",hash(current.optString("subscriptionUrl"))).toString().getBytes(StandardCharsets.UTF_8));stopNow();try{startNow();main.post(()->cb.done(true,"订阅更新成功，独立网络已连接"));}catch(Exception error){if(old!=null)secrets.put("subscription",old);stopNow();throw error;}}catch(Exception e){main.post(()->cb.done(false,"订阅更新失败；旧缓存已保留，请重新连接"));}});}
  void select(String name,Callback cb){cancelMaintenance();worker.execute(()->{String old=currentEntry;try{if(!ready||!names.contains(name))throw new IOException();selectNow(name);if(probe("FixedExit")<0)throw new IOException();verifyExit();report("已切换入口 · "+display(currentEntry));main.post(()->cb.done(true,message));}catch(Exception e){try{if(old.isEmpty())throw new IOException();selectNow(old);verifyExit();report("该入口不可用，已恢复原入口");}catch(Exception restore){stopNow();report("出口无法通过核实，连接已停止");}main.post(()->cb.done(false,message));}});}
  void health(){
    if(!ready||starting)return;
    try{
      maintenanceCheck();if(!coreAlive())throw new IOException("内置网络进程已退出");
      int delay=probe("FixedExit");maintenanceCheck();long now=System.currentTimeMillis();quality.record(currentEntry,delay,now);
      if(delay<0){if(++failures>=2){if(settings!=null&&"manual".equals(settings.optString("entryMode")))throw new IOException("指定入口暂不可用，请重连或编辑网络");firstVerifiedRoute(currentEntry);maintenanceCheck();if(routeBusy())return;verifyExit();failures=0;report("已自动恢复入口 · "+display(currentEntry));}return;}
      failures=0;if(now-lastVerified>=NetworkOptimizationPolicy.ACTIVE_INTERVAL)verifyExit();
      if((lowLatency()||settings!=null&&settings.optString("entryMode").isEmpty())&&now-lastScan>=NetworkOptimizationPolicy.SCAN_INTERVAL&&!backgroundIdle()){
        List<String> batch=NetworkOptimizationPolicy.batch(names,rankedRoutes(),currentEntry,scanCursor++);scanSubset(batch,false,true);
      }
      maintenanceCheck();if(lowLatency()&&!backgroundIdle()){String server=dns.next(System.currentTimeMillis());if(!server.isEmpty()){int ms=-1;try{ms=NetworkDns.measure(this,server);}catch(IOException unavailable){maintenanceCheck();}maintenanceCheck();dns.record(server,ms,System.currentTimeMillis());}}
    }catch(Exception e){if(maintenanceCancelled()&&!(e instanceof ExitMismatch))return;stopNow();if(e instanceof ExitMismatch)recoveryBlocked=true;report(e instanceof IOException?e.getMessage():"内置网络已停止；请检查节点与固定出口");}
  }
  void stop(){cancelMaintenance();worker.execute(()->stopNow());}
  void stopNow(){ready=false;websiteResult=new JSONObject();lastProbeDuration=0;lastProbeDurationAt=0;lastProbeEntry="";if(process!=null){process.destroy();process=null;}cleanupOwnedPid();}
  void cleanupOwnedPid(){try{File pidFile=new File(root,"core.pid");if(!pidFile.exists())return;int pid;try(FileInputStream in=new FileInputStream(pidFile)){pid=Integer.parseInt(J.text(in,32).trim());}if(pid<=1||pid==android.os.Process.myPid())return;String cmd,status;try(FileInputStream in=new FileInputStream("/proc/"+pid+"/cmdline")){cmd=J.text(in,8192);}try(FileInputStream in=new FileInputStream("/proc/"+pid+"/status")){status=J.text(in,8192);}if(cmd.contains("libmihomo.so")&&cmd.contains(root.getAbsolutePath())&&status.matches("(?s).*Uid:\\s+"+android.os.Process.myUid()+"\\s+.*"))android.os.Process.killProcess(pid);pidFile.delete();}catch(Exception ignored){}}
  static String display(String name){return name.startsWith("Entry|")?name.substring(6):name;}
  static String hash(String s){try{byte[] b=MessageDigest.getInstance("SHA-256").digest(s.getBytes(StandardCharsets.UTF_8));StringBuilder out=new StringBuilder();for(byte x:b)out.append(String.format(Locale.ROOT,"%02x",x&255));return out.toString();}catch(java.security.NoSuchAlgorithmException impossible){throw new IllegalStateException(impossible);}}
}
