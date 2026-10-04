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
  static synchronized JSONObject read(Context c){SecretStore vault=new SecretStore(c);long modified=vault.file("exit-region").lastModified();if(cached==null||modified!=stamp||!vault.file("exit-region").getAbsolutePath().equals(cachePath)){try{byte[] raw=vault.get("exit-region");cached=raw==null?new JSONObject():J.parse(new String(raw,StandardCharsets.UTF_8));}catch(Exception e){cached=new JSONObject();}stamp=modified;cachePath=vault.file("exit-region").getAbsolutePath();}return cached;}
  static String region(Context c,String ip){JSONObject value=read(c);return ip.equals(value.optString("ip"))&&System.currentTimeMillis()-value.optLong("at")<7*86400000L?value.optString("region"):"";}
  static String exitIp(Context c,ChatSession s){JSONObject value=read(c);return s!=null&&s.networkIdentity().equals(value.optString("route"))&&System.currentTimeMillis()-value.optLong("at")<7*86400000L?value.optString("ip"):"";}
  static void refresh(ChatSession s){
    if(running||s.deleted||!s.networkReady||s.offline||!s.guard.allowed()||s.connecting||System.currentTimeMillis()-attempted<300000)return;
    // Controlled integration fixtures and local routes must never contact public GeoIP services.
    if(!BrowserNetworkGuard.publicHttps(s.web.getUrl()==null?null:android.net.Uri.parse(s.web.getUrl())))return;
    NativeNetwork n=NativeNetwork.get(s.context);String ip=s.internalNetwork()?n.exitIp:"",route=s.networkIdentity();JSONObject old=read(s.context);
    if(route.equals(old.optString("route"))&&(ip.isEmpty()||ip.equals(old.optString("ip")))&&System.currentTimeMillis()-old.optLong("at")<7*86400000L)return;
    long epoch=s.connectionEpoch;String proxy=s.internalNetwork()?n.proxy():s.prefs.getString("proxy","");android.net.Network bound=s.guard.requiresVpn()?s.context.getSystemService(android.net.ConnectivityManager.class).getActiveNetwork():null;running=true;attempted=System.currentTimeMillis();
    worker.execute(()->{
      try{
        Proxy transport=Proxy.NO_PROXY;if(!proxy.isEmpty()){URI address=new URI(proxy);transport=new Proxy("socks".equals(address.getScheme())?Proxy.Type.SOCKS:Proxy.Type.HTTP,new InetSocketAddress(address.getHost(),address.getPort()));}
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
