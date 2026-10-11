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
  static volatile boolean running;static long attempted;static JSONObject cached;static long stamp=-1;static String cachePath="";
  static final ExecutorService latencyWorker=Executors.newSingleThreadExecutor();
  static volatile boolean latencyRunning;static long latencyAttempted;static String latencyAttemptRoute="",latencyCachePath="";static long latencyStamp=-1;static JSONObject latencyCached;
  static synchronized JSONObject read(Context c){SecretStore vault=new SecretStore(c);long modified=vault.file("exit-region").lastModified();if(cached==null||modified!=stamp||!vault.file("exit-region").getAbsolutePath().equals(cachePath)){try{byte[] raw=vault.get("exit-region");cached=raw==null?new JSONObject():J.parse(new String(raw,StandardCharsets.UTF_8));}catch(Exception e){cached=new JSONObject();}stamp=modified;cachePath=vault.file("exit-region").getAbsolutePath();}return cached;}
  static String region(Context c,String ip){JSONObject value=read(c);return ip.equals(value.optString("ip"))&&System.currentTimeMillis()-value.optLong("at")<7*86400000L?value.optString("region"):"";}
  static String exitIp(Context c,ChatSession s){JSONObject value=read(c);return s!=null&&s.networkIdentity().equals(value.optString("route"))&&System.currentTimeMillis()-value.optLong("at")<7*86400000L?value.optString("ip"):"";}
  static synchronized JSONObject readLatency(Context c){SecretStore vault=new SecretStore(c);File file=vault.file("route-latency");long modified=file.lastModified();if(latencyCached==null||latencyStamp!=modified||!file.getAbsolutePath().equals(latencyCachePath)){try{byte[] raw=vault.get("route-latency");latencyCached=raw==null?new JSONObject():J.parse(new String(raw,StandardCharsets.UTF_8));}catch(Exception ignored){latencyCached=new JSONObject();}latencyStamp=modified;latencyCachePath=file.getAbsolutePath();}return latencyCached;}
  static String latencyRoute(ChatSession s){return s.networkIdentity()+"|"+s.networkIdentity;}
  static JSONObject latency(Context c,ChatSession s){JSONObject value=readLatency(c);return s!=null&&latencyRoute(s).equals(value.optString("route"))?value:new JSONObject();}
  static Proxy proxy(String value)throws Exception{if(value.isEmpty())return Proxy.NO_PROXY;URI address=new URI(value);return new Proxy("socks".equals(address.getScheme())?Proxy.Type.SOCKS:Proxy.Type.HTTP,new InetSocketAddress(address.getHost(),address.getPort()));}
  static void latencyGate(ChatSession s,long epoch,String route)throws IOException{if(s.deleted||s.internalNetwork()||!s.prefs.getBoolean("networkConfigured",false)||s.offline||!s.networkReady||s.connecting||epoch!=s.connectionEpoch||!s.guard.allowed()||!route.equals(latencyRoute(s)))throw new IOException("连接已变化");}
  /** Native-proxy quality and external connection response use different measurement sources. */
  static synchronized void refreshLatency(ChatSession s,NativeNetwork.Callback callback){
    if(s==null||s.internalNetwork()){if(callback!=null&&s!=null)s.handler.post(()->callback.done(false,"请先打开此窗口的会话"));return;}
    String route=latencyRoute(s);long epoch=s.connectionEpoch;
    try{latencyGate(s,epoch,route);}catch(IOException unavailable){if(callback!=null)s.handler.post(()->callback.done(false,"请先恢复此窗口的网络连接"));return;}
    // Local regression fixtures never cause background requests to public services.
    if(!BrowserNetworkGuard.publicHttps(s.web.getUrl()==null?null:android.net.Uri.parse(s.web.getUrl()))){if(callback!=null)s.handler.post(()->callback.done(false,"网页连接尚未就绪"));return;}
    if(latencyRunning){if(callback!=null)s.handler.post(()->callback.done(false,"正在测量，请稍后再试"));return;}
    long now=System.currentTimeMillis(),mono=android.os.SystemClock.elapsedRealtime();JSONObject old=latency(s.context,s);long at=old.optLong("at");
    if(callback==null&&(at>0&&now>=at-60000&&now-at<60000||route.equals(latencyAttemptRoute)&&mono-latencyAttempted<(at>0?60000:10000)))return;
    android.net.Network bound=s.guard.requiresVpn()?s.context.getSystemService(android.net.ConnectivityManager.class).getActiveNetwork():null;
    if(s.guard.requiresVpn()&&bound==null){if(callback!=null)s.handler.post(()->callback.done(false,"请先连接手机 VPN"));return;}
    final Proxy transport;try{transport=proxy(s.prefs.getString("proxy",""));}catch(Exception invalid){if(callback!=null)s.handler.post(()->callback.done(false,"代理地址无效"));return;}
    latencyRunning=true;latencyAttempted=mono;latencyAttemptRoute=route;
    latencyWorker.execute(()->{int delay=-1;try{delay=RouteLatency.measure(NativeNetwork.PROBE,transport,bound,()->latencyGate(s,epoch,route));}catch(IOException ignored){}
      final int measured=delay;final JSONObject sample=J.obj("route",route,"at",System.currentTimeMillis(),"delay",measured,"kind","response","target",NativeNetwork.PROBE);
      s.handler.post(()->{synchronized(NetworkRegion.class){latencyRunning=false;}try{latencyGate(s,epoch,route);new SecretStore(s.context).put("route-latency",sample.toString().getBytes(StandardCharsets.UTF_8));latencyCached=null;WindowNetworkState.save(s.context,s,NativeNetwork.get(s.context));s.changed();if(callback!=null)callback.done(measured>0,measured>0?"连接响应 "+measured+" ms":"线路暂未通过探测，可稍后再试");}catch(Exception changed){if(callback!=null)callback.done(false,"连接已变化，请重新测量");}});
    });
  }
  static void refresh(ChatSession s){
    refreshLatency(s,null);
    if(running||s.deleted||!s.networkReady||s.offline||!s.guard.allowed()||s.connecting||System.currentTimeMillis()-attempted<300000)return;
    // Controlled integration fixtures and local routes must never contact public GeoIP services.
    if(!BrowserNetworkGuard.publicHttps(s.web.getUrl()==null?null:android.net.Uri.parse(s.web.getUrl())))return;
    NativeNetwork n=NativeNetwork.get(s.context);String ip=s.internalNetwork()?n.exitIp:"",route=s.networkIdentity();JSONObject old=read(s.context);
    if(route.equals(old.optString("route"))&&(ip.isEmpty()||ip.equals(old.optString("ip")))&&System.currentTimeMillis()-old.optLong("at")<7*86400000L)return;
    long epoch=s.connectionEpoch;String proxy=s.internalNetwork()?n.proxy():s.prefs.getString("proxy","");android.net.Network bound=s.guard.requiresVpn()?s.context.getSystemService(android.net.ConnectivityManager.class).getActiveNetwork():null;running=true;attempted=System.currentTimeMillis();
    worker.execute(()->{
      try{
        Proxy transport=proxy(proxy);
        String actual=ip.isEmpty()?request("https://api.ipify.org?format=json",transport,bound,s,epoch,route).optString("ip"):ip;
        if(!actual.matches("[0-9.]+|[0-9a-fA-F:]+"))return;
        JSONObject answer=request("https://ipwho.is/"+actual+"?fields=success,ip,country_code,city",transport,bound,s,epoch,route);
        if(!answer.optBoolean("success")||!actual.equals(answer.optString("ip")))return;String country=NodeRegion.country(answer.optString("country_code"));if(country.isEmpty())return;
        String city=answer.optString("city").trim();if(city.length()>64||city.matches(".*[\\p{Cntrl}].*"))city="";
        JSONObject value=J.obj("ip",actual,"region",country+(city.isEmpty()?"":" · "+city),"at",System.currentTimeMillis(),"route",route);
        s.handler.post(()->{if(!s.deleted&&epoch==s.connectionEpoch&&route.equals(s.networkIdentity())&&s.guard.allowed()){try{new SecretStore(s.context).put("exit-region",value.toString().getBytes(StandardCharsets.UTF_8));cached=null;WindowNetworkState.save(s.context,s,n);s.changed();}catch(Exception ignored){}}});
      }catch(Exception ignored){}finally{running=false;}
    });
  }
  static JSONObject request(String target,Proxy proxy,android.net.Network bound,ChatSession s,long epoch,String route)throws Exception{if(s.deleted||epoch!=s.connectionEpoch||!s.guard.allowed()||!route.equals(s.networkIdentity())||s.guard.requiresVpn()&&bound==null)throw new IOException();HttpURLConnection c=(HttpURLConnection)(bound==null?new URL(target).openConnection(proxy):bound.openConnection(new URL(target),proxy));c.setConnectTimeout(4000);c.setReadTimeout(4000);c.setInstanceFollowRedirects(false);try{if(c.getResponseCode()!=200)throw new IOException();try(InputStream in=c.getInputStream()){return J.parse(J.text(in,8192));}}finally{c.disconnect();}}
}
