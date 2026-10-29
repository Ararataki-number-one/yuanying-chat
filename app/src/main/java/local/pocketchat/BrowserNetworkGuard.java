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
  final boolean workerProtection=true;
  BrowserNetworkGuard(ChatSession s){session=s;}
  void setBlocked(boolean value){blocked=value;session.web.getSettings().setBlockNetworkLoads(value);}
  static boolean needsVpn(boolean internal,String proxy,boolean required){return !internal&&proxy.trim().isEmpty()&&required;}
  boolean requiresVpn(){return needsVpn(session.internalNetwork(),session.prefs.getString("proxy",""),session.prefs.getBoolean("requireExternalVpn",true));}
  boolean vpnActive(){try{ConnectivityManager cm=(ConnectivityManager)session.context.getSystemService(Context.CONNECTIVITY_SERVICE);Network n=cm.getActiveNetwork();NetworkCapabilities caps=n==null?null:cm.getNetworkCapabilities(n);return caps!=null&&caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN)&&caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET);}catch(Exception e){return false;}}
  String vpnDefaultRouteIssue(){
    // getType() is public only from API 33. Older public snapshots cannot
    // distinguish excluded routes; never infer protection or silently downgrade.
    if(android.os.Build.VERSION.SDK_INT<33)return "vpn-route-inspection-unsupported";
    try{
      ConnectivityManager cm=(ConnectivityManager)session.context.getSystemService(Context.CONNECTIVITY_SERVICE);
      if(cm==null)return "vpn-network-unavailable";
      Network network=cm.getActiveNetwork();
      NetworkCapabilities caps=network==null?null:cm.getNetworkCapabilities(network);
      if(caps==null||!caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN)||!caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET))return "vpn-not-active";
      LinkProperties links=cm.getLinkProperties(network);
      if(links==null)return "vpn-routes-unavailable";
      List<RouteInfo> observed=links.getRoutes();
      if(observed==null)return "vpn-routes-unavailable";
      List<VpnDefaultRouteCoverage.Route> routes=new ArrayList<>();
      for(RouteInfo route:observed){
        if(route==null)return "vpn-route-unavailable";
        IpPrefix destination=route.getDestination();
        InetAddress address=destination==null?null:destination.getAddress();
        if(address==null)return "vpn-route-unavailable";
        routes.add(new VpnDefaultRouteCoverage.Route(address.getAddress().length,
          destination.getPrefixLength(),route.getType(),route.getInterface()));
      }
      String issue=VpnDefaultRouteCoverage.issue(links.getInterfaceName(),routes);
      if(!issue.isEmpty())return issue;
      NetworkCapabilities after=cm.getNetworkCapabilities(network);
      if(after==null||!after.hasTransport(NetworkCapabilities.TRANSPORT_VPN)||!after.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET))return "vpn-network-changed";
      if(!network.equals(cm.getActiveNetwork()))return "vpn-network-changed";
      return "";
    }catch(Exception error){return "vpn-route-inspection-failed";}
  }
  String vpnProtectionFailureMessage(){
    if(android.os.Build.VERSION.SDK_INT<33)return "当前系统无法确认 VPN 路由覆盖，已阻止新请求。请使用应用内线路或显式代理。";
    return "VPN 路由覆盖尚未确认，已阻止新请求。请检查 VPN 完整覆盖，或使用应用内线路／显式代理。";
  }
  boolean routeProtected(){if(requiresVpn())return vpnDefaultRouteIssue().isEmpty();if(session.internalNetwork()){NativeNetwork n=NativeNetwork.get(session.context);return n.connectionAdmission().usable();}return true;}
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
