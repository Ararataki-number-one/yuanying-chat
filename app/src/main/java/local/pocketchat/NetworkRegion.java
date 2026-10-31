package local.pocketchat;

import android.content.Context;
import org.json.*;
import java.net.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.*;

/** Lookups use this environment's guarded route. Names never substitute for exit geolocation. */
final class NetworkRegion {
  static final ExecutorService worker=Executors.newSingleThreadExecutor();
  static volatile boolean running;static long attempted;
  static final ExecutorService snapshots=Executors.newSingleThreadExecutor();
  static final FileSnapshotCache<JSONObject> cache=new FileSnapshotCache<>(snapshots,JSONObject::new);
  static final android.os.Handler main=new android.os.Handler(android.os.Looper.getMainLooper());
  static final java.util.Map<Context,RegionPaths[]> paths=new java.util.IdentityHashMap<>();
  static final class RegionPaths {volatile File region,latency;boolean queued;final Object resolving=new Object();}
  static RegionPaths paths(Context c){Context root=Profiles.global(c);int slot=Profiles.slot(c);synchronized(paths){RegionPaths[] entries=paths.computeIfAbsent(root,key->new RegionPaths[Profiles.MAX]);if(entries[slot]==null)entries[slot]=new RegionPaths();return entries[slot];}}
  static void notifySnapshot(Context c){main.post(()->{ChatSession s=ChatSession.peek();if(s!=null&&!s.deleted&&Profiles.slot(s.context)==Profiles.slot(c))s.changed();});}
  static void resolvePaths(Context c,RegionPaths entry){synchronized(entry.resolving){if(entry.region!=null)return;File base=Profiles.global(c).getNoBackupFilesDir();int slot=Profiles.slot(c);if(slot>0)base=new File(base,"profiles/env"+slot);entry.latency=new File(base,"route-latency.sealed");entry.region=new File(base,"exit-region.sealed");}}
  static File path(Context c,String name){RegionPaths entry=paths(c);File known="exit-region".equals(name)?entry.region:entry.latency;if(known!=null)return known;if(android.os.Looper.myLooper()!=android.os.Looper.getMainLooper()){resolvePaths(c,entry);return "exit-region".equals(name)?entry.region:entry.latency;}synchronized(entry){if(!entry.queued){entry.queued=true;snapshots.execute(()->{try{resolvePaths(c,entry);notifySnapshot(c);}finally{synchronized(entry){entry.queued=false;}}});}}return null;}
  static final ExecutorService latencyWorker=Executors.newSingleThreadExecutor();
  static volatile boolean latencyRunning;static long latencyAttempted;static String latencyAttemptRoute="";
  static JSONObject snapshot(Context c,String name){File file=path(c,name);if(file==null)return new JSONObject();SecretStore vault=new SecretStore(c);return cache.read(file,android.os.Looper.myLooper()==android.os.Looper.getMainLooper(),()->{byte[] raw=vault.get(name);return raw==null?new JSONObject():J.parse(new String(raw,StandardCharsets.UTF_8));},()->notifySnapshot(c));}
  static boolean ready(Context c,String name){RegionPaths entry=paths(c);File file="exit-region".equals(name)?entry.region:entry.latency;return file!=null&&cache.ready(file);}
  static JSONObject read(Context c){return snapshot(c,"exit-region");}
  static String region(Context c,String ip){JSONObject value=read(c);return ip.equals(value.optString("ip"))&&System.currentTimeMillis()-value.optLong("at")<7*86400000L?value.optString("region"):"";}
  static String exitIp(Context c,ChatSession s){JSONObject value=read(c);return s!=null&&s.networkIdentity().equals(value.optString("route"))&&System.currentTimeMillis()-value.optLong("at")<7*86400000L?value.optString("ip"):"";}
  static JSONObject readLatency(Context c){return snapshot(c,"route-latency");}
  static String latencyRoute(ChatSession s){return s.networkIdentity()+"|"+s.networkIdentity;}
  static JSONObject latency(Context c,ChatSession s){JSONObject value=readLatency(c);return s!=null&&latencyRoute(s).equals(value.optString("route"))?value:new JSONObject();}
  static long latencyRemaining(ChatSession s,long now){
    if(s==null)return 0;
    long left=LatencyRefreshPolicy.remaining(latency(s.context,s).optLong("at"),now),mono=android.os.SystemClock.elapsedRealtime();
    if(latencyRoute(s).equals(latencyAttemptRoute)&&mono>=latencyAttempted)left=Math.max(left,Math.max(0,LatencyRefreshPolicy.INTERVAL-(mono-latencyAttempted)));
    return left;
  }
  static Proxy proxy(String value)throws Exception{if(value.isEmpty())return Proxy.NO_PROXY;URI address=new URI(value);return new Proxy("socks".equals(address.getScheme())?Proxy.Type.SOCKS:Proxy.Type.HTTP,new InetSocketAddress(address.getHost(),address.getPort()));}
  static boolean backgroundBusy(ChatSession s){return s!=null&&(s.pending!=null||s.submitting||s.operation||s.transferActive||s.fileWorkActive()||s.navigating||s.state.optBoolean("busy"));}
  static void latencyGate(ChatSession s,long epoch,String route)throws IOException{if(s.deleted||s.internalNetwork()||!s.prefs.getBoolean("networkConfigured",false)||s.offline||!s.networkReady||s.connecting||epoch!=s.connectionEpoch||!s.guard.allowed()||!route.equals(latencyRoute(s)))throw new IOException("连接已变化");}
  static void latencyGate(ChatSession s,long epoch,String route,boolean automatic)throws IOException{latencyGate(s,epoch,route);}
  /** Native-proxy quality and external connection response use different measurement sources. */
  static synchronized void refreshLatency(ChatSession s,NativeNetwork.Callback callback){
    if(s==null||s.internalNetwork()){if(callback!=null&&s!=null)s.handler.post(()->callback.done(false,"请先打开此窗口的会话"));return;}
    if(callback==null&&!s.uiVisible)return;
    String route=latencyRoute(s);long epoch=s.connectionEpoch;
    try{latencyGate(s,epoch,route);}catch(IOException unavailable){if(callback!=null)s.handler.post(()->callback.done(false,"请先恢复此窗口的网络连接"));return;}
    // Local regression fixtures never cause background requests to public services.
    if(!BrowserNetworkGuard.publicHttps(s.web.getUrl()==null?null:android.net.Uri.parse(s.web.getUrl()))){if(callback!=null)s.handler.post(()->callback.done(false,"网页连接尚未就绪"));return;}
    if(latencyRunning){if(callback!=null)s.handler.post(()->callback.done(false,"正在测量，请稍后再试"));return;}
    long now=System.currentTimeMillis(),mono=android.os.SystemClock.elapsedRealtime();JSONObject old=latency(s.context,s);long at=old.optLong("at");
    // The first UI read schedules a background cache load; do not probe over a valid saved sample.
    if(callback==null&&!ready(s.context,"route-latency"))return;
    if(callback==null&&(NativeNetwork.freshLatency(at,now)||route.equals(latencyAttemptRoute)&&mono>=latencyAttempted&&mono-latencyAttempted<LatencyRefreshPolicy.INTERVAL))return;
    android.net.Network bound=s.guard.requiresVpn()?s.context.getSystemService(android.net.ConnectivityManager.class).getActiveNetwork():null;
    if(s.guard.requiresVpn()&&bound==null){if(callback!=null)s.handler.post(()->callback.done(false,"请先连接手机 VPN"));return;}
    final Proxy transport;try{transport=proxy(s.prefs.getString("proxy",""));}catch(Exception invalid){if(callback!=null)s.handler.post(()->callback.done(false,"代理地址无效"));return;}
    latencyRunning=true;
    latencyWorker.execute(()->{try{
      // This only opens a probe connection; it never touches the website or changes its route.
      if(callback==null&&NativeNetwork.freshLatency(latency(s.context,s).optLong("at"),System.currentTimeMillis()))return;
      synchronized(NetworkRegion.class){latencyAttempted=android.os.SystemClock.elapsedRealtime();latencyAttemptRoute=route;}
      int delay=-1;try{delay=RouteLatency.measure(NativeNetwork.PROBE,transport,bound,()->latencyGate(s,epoch,route,callback==null));}catch(IOException ignored){}
      final int measured=delay;final JSONObject sample=J.obj("route",route,"at",System.currentTimeMillis(),"delay",measured,"kind","response","target",NativeNetwork.PROBE);
      boolean stored=false;try{latencyGate(s,epoch,route,callback==null);SecretStore vault=new SecretStore(s.context);vault.put("route-latency",sample.toString().getBytes(StandardCharsets.UTF_8));cache.publish(vault.file("route-latency"),sample);stored=true;}catch(Exception changed){}
      final boolean saved=stored;s.handler.post(()->{try{latencyGate(s,epoch,route);if(!saved)throw new IOException();WindowNetworkState.save(s.context,s,NativeNetwork.get(s.context));s.changed();if(callback!=null)callback.done(measured>0,measured>0?"连接响应 "+measured+" ms":"线路暂未通过探测，可稍后再试");}catch(Exception changed){if(callback!=null)callback.done(false,"连接已变化，请重新测量");}});
    }finally{synchronized(NetworkRegion.class){latencyRunning=false;}}
    });
  }
  /** IP display queries now open ip123 inside the guarded environment browser.
   * No undocumented data endpoint is used; cached observations keep their age. */
  static void refresh(ChatSession s){refreshLatency(s,null);}
  static JSONObject request(String target,Proxy proxy,android.net.Network bound,ChatSession s,long epoch,String route)throws Exception{if(s.deleted||epoch!=s.connectionEpoch||!s.guard.allowed()||!route.equals(s.networkIdentity())||s.guard.requiresVpn()&&bound==null||backgroundBusy(s))throw new IOException();HttpURLConnection c=(HttpURLConnection)(bound==null?new URL(target).openConnection(proxy):bound.openConnection(new URL(target),proxy));c.setConnectTimeout(4000);c.setReadTimeout(4000);c.setInstanceFollowRedirects(false);try{if(c.getResponseCode()!=200)throw new IOException();try(InputStream in=c.getInputStream()){return J.parse(J.text(in,8192));}}finally{c.disconnect();}}
}
