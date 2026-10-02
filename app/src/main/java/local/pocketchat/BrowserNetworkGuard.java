package local.pocketchat;

import android.content.Context;
import android.net.*;
import android.webkit.*;
import java.io.*;
import java.net.InetAddress;
import java.util.*;

/** Process-local request gate. It is not a device VPN or a kernel kill switch. */
final class BrowserNetworkGuard {
  final ChatSession session;
  volatile boolean blocked=true;
  ServiceWorkerWebSettings workers;
  boolean workerProtection;
  BrowserNetworkGuard(ChatSession s){session=s;
    try{ServiceWorkerController controller=ServiceWorkerController.getInstance();workers=controller.getServiceWorkerWebSettings();workers.setBlockNetworkLoads(true);workers.setAllowFileAccess(false);workers.setAllowContentAccess(false);controller.setServiceWorkerClient(new ServiceWorkerClient(){
      @Override public WebResourceResponse shouldInterceptRequest(WebResourceRequest request){return intercept(request.getUrl());}
    });workerProtection=true;}catch(Exception ignored){}
  }
  void setBlocked(boolean value){blocked=value;session.web.getSettings().setBlockNetworkLoads(value);if(workers!=null)try{workers.setBlockNetworkLoads(value);}catch(Exception e){workerProtection=false;if(session.privacy.level()>0){blocked=true;session.web.getSettings().setBlockNetworkLoads(true);}}}
  static boolean needsVpn(boolean internal,String proxy,boolean required){return !internal&&proxy.trim().isEmpty()&&required;}
  boolean requiresVpn(){return needsVpn(session.internalNetwork(),session.prefs.getString("proxy",""),session.prefs.getBoolean("requireExternalVpn",true));}
  boolean vpnActive(){try{ConnectivityManager cm=(ConnectivityManager)session.context.getSystemService(Context.CONNECTIVITY_SERVICE);Network n=cm.getActiveNetwork();NetworkCapabilities caps=n==null?null:cm.getNetworkCapabilities(n);return caps!=null&&caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN)&&caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET);}catch(Exception e){return false;}}
  boolean routeProtected(){if(requiresVpn())return vpnActive();if(session.internalNetwork()){NativeNetwork n=NativeNetwork.get(session.context);return n.ready&&n.coreAlive();}return true;}
  boolean allowed(){return !blocked&&routeProtected();}
  WebResourceResponse intercept(Uri uri){return !allowed()||!publicHttps(uri)?denied():null;}
  static WebResourceResponse denied(){return new WebResourceResponse("text/plain","UTF-8",403,"Network protection",Collections.singletonMap("Cache-Control","no-store"),new ByteArrayInputStream(new byte[0]));}
  static boolean publicHttps(Uri uri){return uri!=null&&"https".equalsIgnoreCase(uri.getScheme())&&uri.getUserInfo()==null&&!localHost(uri.getHost());}
  static boolean localHost(String value){
    if(value==null||value.isEmpty())return true;String h=value.toLowerCase(Locale.ROOT);while(h.endsWith("."))h=h.substring(0,h.length()-1);
    if(h.startsWith("[")&&h.endsWith("]"))h=h.substring(1,h.length()-1);
    if(h.equals("localhost")||h.endsWith(".localhost")||h.endsWith(".local")||h.endsWith(".lan")||h.endsWith(".internal")||h.equals("home.arpa")||h.endsWith(".home.arpa"))return true;
    if(h.indexOf(':')>=0){
      if(!h.matches("[0-9a-f:.]+"))return true;
      try{InetAddress ip=InetAddress.getByName(h);byte[] b=ip.getAddress();return ip.isAnyLocalAddress()||ip.isLoopbackAddress()||ip.isLinkLocalAddress()||ip.isSiteLocalAddress()||ip.isMulticastAddress()||(b.length==16&&(b[0]&0xfe)==0xfc)||(b.length==4&&privateV4(b));}catch(Exception e){return true;}
    }
    // Parse numeric IPv4 forms locally; never resolve a hostname for a privacy check.
    if(h.matches("(?i)(?:0x[0-9a-f]+|[0-9]+)(?:\\.(?:0x[0-9a-f]+|[0-9]+)){0,3}")){
      try{String[] p=h.split("\\.");long ip=0;for(int i=0;i<p.length;i++){String part=p[i];int radix=part.startsWith("0x")?16:part.length()>1&&part.startsWith("0")?8:10;long n=Long.parseLong(radix==16?part.substring(2):part,radix);long max=i==p.length-1?(1L<<(8*(5-p.length)))-1:255;if(n<0||n>max)return true;ip=i==p.length-1?(ip<<(8*(5-p.length)))|n:(ip<<8)|n;}return privateV4(new byte[]{(byte)(ip>>24),(byte)(ip>>16),(byte)(ip>>8),(byte)ip});}catch(Exception e){return true;}
    }
    return false;
  }
  static boolean privateV4(byte[] b){int a=b[0]&255,c=b[1]&255;return a==0||a==10||a==127||a>=224||a==169&&c==254||a==172&&c>=16&&c<=31||a==192&&c==168||a==100&&c>=64&&c<=127;}
}
