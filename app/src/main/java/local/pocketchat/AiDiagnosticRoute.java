package local.pocketchat;

import android.content.Context;
import android.net.ConnectivityManager;
import android.net.LinkProperties;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.Uri;
import java.io.IOException;
import java.net.HttpURLConnection;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.Proxy;
import java.net.URI;
import java.net.URL;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

/** One AI request owns one admitted route. Never adopts a replacement network or falls back.
 * Bound external connections cannot migrate to a new default Network. Revocation stops future
 * checks and disconnects in-flight I/O; Android callbacks cannot retract bytes already sent. */
final class AiDiagnosticRoute implements AutoCloseable {
  final ChatSession session;
  final EnvironmentSpec.Identity environment;
  final long epoch;
  final String mode,configuredProxy;
  final boolean requireVpn;
  final NativeNetwork internal;
  final NativeNetwork.ExitRouteReceipt receipt;
  final ConnectivityManager connectivity;
  final Network bound;
  final LinkProperties links;
  final NetworkPoolIdentity.NetworkSnapshot network;
  final Proxy proxy;
  final Set<HttpURLConnection> active=ConcurrentHashMap.newKeySet();
  final ScheduledExecutorService watcher=Executors.newSingleThreadScheduledExecutor(task->{Thread t=new Thread(task,"ai-route-watch");t.setDaemon(true);return t;});
  volatile IOException failure;
  volatile boolean closed;
  private boolean registered;
  final ConnectivityManager.NetworkCallback callback=new ConnectivityManager.NetworkCallback(){
    @Override public void onAvailable(Network n){if(!bound.equals(n))lose();}
    @Override public void onLost(Network n){if(bound.equals(n))lose();}
    @Override public void onCapabilitiesChanged(Network n,NetworkCapabilities c){if(bound.equals(n)&&!capabilitiesMatch(c))lose();}
    @Override public void onLinkPropertiesChanged(Network n,LinkProperties p){if(bound.equals(n)&&!links.equals(p))lose();}
  };

  /** UI hint only. capture() repeats all checks and verifies fresh internal service evidence. */
  static String issue(ChatSession session){
    try{
      if(session==null||session.deleted||ChatSession.peek()!=session||session.offline||!session.networkReady||session.connecting||!session.guard.allowed())return "当前环境的受保护连接尚未就绪";
      String mode=session.prefs.getString("networkMode","external");
      if("internal".equals(mode))return "";
      if(!"external".equals(mode))return "网络模式无法核实";
      String configured=session.prefs.getString("proxy","");
      // Existing BrowserNetworkGuard policy gives explicit external proxy priority.
      if(!configured.isEmpty()){numericHttpProxy(configured);return "";}
      if(!session.guard.requiresVpn())return "AI 请求不支持普通直连，请使用已核验的应用内线路或完整覆盖的 VPN";
      if(!session.guard.vpnDefaultRouteIssue().isEmpty())return "VPN 路由覆盖尚未核实";
      return "";
    }catch(Exception unsupported){return "AI 请求仅支持数值地址的 HTTP 代理；域名、HTTPS 和 SOCKS 代理暂不可用";}
  }
  static AiDiagnosticRoute capture(ChatSession session,long expectedEpoch)throws IOException {
    String problem=issue(session);if(!problem.isEmpty())throw new IOException(problem);
    AiDiagnosticRoute route=new AiDiagnosticRoute(session,expectedEpoch);
    try{
      route.check();route.verifyInternal();route.check();
      route.connectivity.registerDefaultNetworkCallback(route.callback);route.registered=true;
      route.check();
      route.watcher.scheduleWithFixedDelay(route::watch,250,250,TimeUnit.MILLISECONDS);
      return route;
    }catch(Exception error){route.close();throw unavailable();}
  }
  private AiDiagnosticRoute(ChatSession session,long expectedEpoch)throws IOException {
    this.session=session;epoch=expectedEpoch;
    environment=new EnvironmentSpec.Identity(Profiles.slot(session.context),session.environmentGeneration,session.environmentId);
    mode=session.prefs.getString("networkMode","external");configuredProxy=session.prefs.getString("proxy","");requireVpn=session.guard.requiresVpn();
    internal="internal".equals(mode)?NativeNetwork.get(session.context):null;receipt=internal==null?null:internal.verifiedRoute;
    connectivity=(ConnectivityManager)session.context.getSystemService(Context.CONNECTIVITY_SERVICE);
    bound=connectivity==null?null:connectivity.getActiveNetwork();
    links=bound==null?null:connectivity.getLinkProperties(bound);
    network=session.browserDefaultNetwork.snapshot();
    if(bound==null||links==null||!network.usable())throw unavailable();
    if(internal!=null){
      if(receipt==null||receipt.proxy<1||receipt.proxy>65535)throw unavailable();
      proxy=new Proxy(Proxy.Type.HTTP,new InetSocketAddress(InetAddress.getByAddress(new byte[]{127,0,0,1}),receipt.proxy));
    }else if(!configuredProxy.isEmpty())proxy=numericHttpProxy(configuredProxy);
    else if(requireVpn)proxy=Proxy.NO_PROXY;
    else throw unavailable();
  }
  static IOException unavailable(){return new IOException("受保护线路或环境已变化，本次 AI 请求已停止，请重新预览后发送");}
  private boolean capabilitiesMatch(NetworkCapabilities caps){
    return caps!=null&&caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)&&network.internet==caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)&&network.vpn==caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN);
  }
  void check()throws IOException {
    if(failure!=null)throw failure;if(closed)throw unavailable();
    try{
      if(Thread.currentThread().isInterrupted()||session.deleted||ChatSession.peek()!=session||Profiles.slot(session.context)!=environment.slot||session.environmentGeneration!=environment.generation||!environment.environmentId.equals(session.environmentId)||session.connectionEpoch!=epoch||session.offline||!session.networkReady||session.connecting||!session.guard.allowed()
          ||!mode.equals(session.prefs.getString("networkMode","external"))||!configuredProxy.equals(session.prefs.getString("proxy",""))||requireVpn!=session.guard.requiresVpn()
          ||!network.equals(session.browserDefaultNetwork.snapshot())||!environment.equals(ProfileCatalog.get(session.context).identity(environment.slot)))throw unavailable();
      if(!bound.equals(connectivity.getActiveNetwork())||!capabilitiesMatch(connectivity.getNetworkCapabilities(bound))||!links.equals(connectivity.getLinkProperties(bound)))throw unavailable();
      if(requireVpn&&(!network.vpn||proxy!=Proxy.NO_PROXY||!session.guard.vpnDefaultRouteIssue().isEmpty()))throw unavailable();
      if(internal!=null&&(Profiles.slot(internal.context)!=environment.slot||receipt==null||receipt!=internal.verifiedRoute||!internal.connectionAdmission().usable()||internal.starting||!receipt.matches(internal,internal.transport==null?null:internal.transport.state)))throw unavailable();
    }catch(Exception changed){lose();throw failure==null?unavailable():failure;}
    if(failure!=null)throw failure;if(closed)throw unavailable();
  }
  private void verifyInternal()throws IOException {
    if(internal!=null&&(!internal.verifiedRouteCurrent()||receipt!=internal.verifiedRoute)){lose();throw unavailable();}
  }
  HttpURLConnection open(String gateway)throws IOException {
    HttpURLConnection connection=null;
    try{
      URI target=new URI(gateway);
      if(!"https".equals(target.getScheme())||target.getHost()==null||target.getUserInfo()!=null||target.getRawQuery()!=null||target.getRawFragment()!=null||!"/v1/diagnose".equals(target.getRawPath())||!BrowserNetworkGuard.publicHttps(Uri.parse(gateway)))throw new IOException("AI 网关必须是获准的 HTTPS 诊断地址");
      check();verifyInternal();check();
      // Internal proxy address is constructed from bytes. CONNECT leaves gateway DNS to it.
      // All external traffic and its DNS use the exact verified Network, never the default.
      connection=(HttpURLConnection)(internal==null?bound.openConnection(new URL(gateway),proxy):new URL(gateway).openConnection(proxy));
      connection.setInstanceFollowRedirects(false);active.add(connection);check();return connection;
    }catch(Exception error){if(connection!=null)AppUpdateTransfer.disconnectLater(connection);lose();throw error instanceof IOException?(IOException)error:unavailable();}
  }
  void released(HttpURLConnection connection){active.remove(connection);}
  private void watch(){if(closed||failure!=null)return;try{check();}catch(IOException ignored){}}
  private synchronized void lose(){
    if(closed||failure!=null)return;failure=unavailable();watcher.shutdownNow();
    for(HttpURLConnection connection:active)AppUpdateTransfer.disconnectLater(connection);
  }
  @Override public synchronized void close(){
    if(closed)return;closed=true;watcher.shutdownNow();
    if(registered){registered=false;try{connectivity.unregisterNetworkCallback(callback);}catch(Exception ignored){}}
    for(HttpURLConnection connection:active)AppUpdateTransfer.disconnectLater(connection);active.clear();
  }
  /** Parsing never invokes a hostname resolver, including for malformed input. */
  static Proxy numericHttpProxy(String value)throws IOException {
    try{
      URI uri=new URI(value);
      if(!"http".equals(uri.getScheme())||uri.getHost()==null||uri.getUserInfo()!=null||uri.getRawQuery()!=null||uri.getRawFragment()!=null||uri.getPort()<1||uri.getPort()>65535||!(uri.getRawPath().isEmpty()||"/".equals(uri.getRawPath())))throw unavailable();
      return new Proxy(Proxy.Type.HTTP,new InetSocketAddress(InetAddress.getByAddress(numericAddress(uri.getHost())),uri.getPort()));
    }catch(Exception malformed){throw new IOException("AI 请求仅支持数值地址的 HTTP 代理；域名、HTTPS 和 SOCKS 代理暂不可用");}
  }
  static byte[] numericAddress(String host)throws IOException {
    if(host==null||host.length()>47)throw unavailable();
    if(host.startsWith("[")&&host.endsWith("]"))host=host.substring(1,host.length()-1);
    if(host.indexOf(':')<0)return ipv4(host);
    if(!host.matches("[0-9a-fA-F:.]+")||host.indexOf('.')>=0&&host.lastIndexOf(':')>host.indexOf('.'))throw unavailable();
    int compression=host.indexOf("::");
    if(compression>=0&&host.indexOf("::",compression+2)>=0)throw unavailable();
    List<Integer> left=groups(compression<0?host:host.substring(0,compression));
    List<Integer> right=compression<0?new ArrayList<>():groups(host.substring(compression+2));
    int missing=8-left.size()-right.size();
    if(compression<0?missing!=0:missing<1)throw unavailable();
    byte[] result=new byte[16];int at=0;
    for(int group:left){result[at++]=(byte)(group>>8);result[at++]=(byte)group;}
    at+=missing*2;
    for(int group:right){result[at++]=(byte)(group>>8);result[at++]=(byte)group;}
    return result;
  }
  private static List<Integer> groups(String side)throws IOException {
    List<Integer> result=new ArrayList<>();if(side.isEmpty())return result;
    String[] parts=side.split(":",-1);
    for(int i=0;i<parts.length;i++){
      String group=parts[i];
      if(group.indexOf('.')>=0){if(i!=parts.length-1)throw unavailable();byte[] v4=ipv4(group);result.add(((v4[0]&255)<<8)|(v4[1]&255));result.add(((v4[2]&255)<<8)|(v4[3]&255));}
      else{if(group.isEmpty()||group.length()>4||!group.matches("[0-9a-fA-F]+"))throw unavailable();result.add(Integer.parseInt(group,16));}
    }
    return result;
  }
  private static byte[] ipv4(String host)throws IOException {
    String[] parts=host.split("\\.",-1);if(parts.length!=4)throw unavailable();byte[] result=new byte[4];
    for(int i=0;i<4;i++){String p=parts[i];if(!p.matches("0|[1-9][0-9]{0,2}"))throw unavailable();int n=Integer.parseInt(p);if(n>255)throw unavailable();result[i]=(byte)n;}
    return result;
  }
}
