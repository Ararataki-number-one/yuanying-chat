package local.pocketchat;

import android.content.Context;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.Uri;
import java.io.IOException;
import java.net.HttpURLConnection;
import java.net.InetSocketAddress;
import java.net.InetAddress;
import java.net.Inet6Address;
import java.net.Proxy;
import java.net.URL;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

/** A single download keeps its admitted environment and route until it finishes.
 * Losing either pauses this attempt; this class never adopts a replacement route. */
final class NativeDownloadRoute implements AutoCloseable {
  interface Opener {HttpURLConnection open(String url,Proxy proxy)throws Exception;}
  final ChatSession session;
  final EnvironmentSpec.Identity environment;
  final long epoch;
  final String mode,configuredProxy;
  final boolean requireVpn;
  final Proxy proxy;
  final NativeNetwork internal;
  final NativeNetwork.ExitRouteReceipt receipt;
  final ConnectivityManager connectivity;
  final Network bound;
  final NetworkPoolIdentity.NetworkSnapshot network;
  final Set<HttpURLConnection> active=ConcurrentHashMap.newKeySet();
  final ScheduledExecutorService watcher;
  volatile IOException failure;
  volatile boolean closed;

  NativeDownloadRoute(ChatSession session,Proxy proxy)throws IOException {
    this.session=session;this.proxy=proxy;epoch=session.connectionEpoch;
    environment=new EnvironmentSpec.Identity(Profiles.slot(session.context),session.environmentGeneration,session.environmentId);
    mode=session.prefs.getString("networkMode","external");configuredProxy=session.prefs.getString("proxy","");requireVpn=session.guard.requiresVpn();
    if(!"internal".equals(mode)&&!"external".equals(mode))throw unavailable();
    internal=session.internalNetwork()?NativeNetwork.get(session.context):null;receipt=internal==null?null:internal.verifiedRoute;
    connectivity=(ConnectivityManager)session.context.getSystemService(Context.CONNECTIVITY_SERVICE);
    network=session.browserDefaultNetwork.snapshot();
    bound=requireVpn&&connectivity!=null?connectivity.getActiveNetwork():null;
    verifyProxy();checkCurrent();verifyInternal();checkCurrent();
    watcher=Executors.newSingleThreadScheduledExecutor(task->{Thread thread=new Thread(task,"download-route-watch");thread.setDaemon(true);thread.setPriority(Thread.MIN_PRIORITY);return thread;});
    watcher.scheduleWithFixedDelay(this::watch,1000,1000,TimeUnit.MILLISECONDS);
  }
  static IOException unavailable(){return new IOException("受保护连接已变化，下载已暂停；本地进度已保留");}
  /** Cheap stream gate. Fresh catalog/network checks run before opens and once a second. */
  void check()throws IOException {
    if(failure!=null)throw failure;if(closed)throw unavailable();
    if(session.deleted||ChatSession.peek()!=session||Profiles.slot(session.context)!=environment.slot||session.environmentGeneration!=environment.generation||!environment.environmentId.equals(session.environmentId)||session.connectionEpoch!=epoch||session.offline||!session.networkReady||session.connecting||!session.guard.allowed()
        ||!mode.equals(session.prefs.getString("networkMode","external"))||!configuredProxy.equals(session.prefs.getString("proxy",""))||requireVpn!=session.guard.requiresVpn()
        ||!network.usable()||!network.equals(session.browserDefaultNetwork.snapshot()))throw unavailable();
    AppPrefs.requireDownloadNetwork(session.context);
    if(internal!=null&&(Profiles.slot(internal.context)!=environment.slot||receipt==null||receipt!=internal.verifiedRoute||!internal.connectionAdmission().usable()||internal.starting||!receipt.matches(internal,internal.transport==null?null:internal.transport.state)))throw unavailable();
  }
  void checkCurrent()throws IOException {
    check();
    if(!environment.equals(ProfileCatalog.get(session.context).identity(environment.slot))||connectivity==null)throw unavailable();
    Network current=connectivity.getActiveNetwork();NetworkCapabilities capabilities=current==null?null:connectivity.getNetworkCapabilities(current);
    if(current==null||capabilities==null||!network.identity.equals(current.toString())||network.internet!=capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)||network.vpn!=capabilities.hasTransport(NetworkCapabilities.TRANSPORT_VPN))throw unavailable();
    if(requireVpn&&(bound==null||!bound.equals(current)||!network.vpn||proxy!=Proxy.NO_PROXY||!session.guard.vpnDefaultRouteIssue().isEmpty()))throw unavailable();
    check();
  }
  /** route() and this capture may straddle a settings change. Never freeze old direct/proxy bytes under new settings. */
  void verifyProxy()throws IOException {
    if(proxy==null)throw unavailable();
    if(internal==null&&configuredProxy.isEmpty()){if(proxy!=Proxy.NO_PROXY)throw unavailable();return;}
    if(!(proxy.address() instanceof InetSocketAddress))throw unavailable();
    InetSocketAddress actual=(InetSocketAddress)proxy.address();
    if(internal!=null){
      if(receipt==null||proxy.type()!=Proxy.Type.HTTP||!"127.0.0.1".equals(actual.getHostString())||actual.getPort()!=receipt.proxy)throw unavailable();return;
    }
    if(!MainActivity.validProxy(configuredProxy))throw unavailable();
    Uri expected=Uri.parse(configuredProxy);String scheme=expected.getScheme();
    if("https".equals(scheme)||proxy.type()!=("socks".equals(scheme)?Proxy.Type.SOCKS:Proxy.Type.HTTP)||!sameProxyHost(expected.getHost(),actual)||expected.getPort()!=actual.getPort())throw unavailable();
  }
  static boolean sameProxyHost(String expected,InetSocketAddress actual){
    if(expected.equalsIgnoreCase(actual.getHostString()))return true;
    if(expected.indexOf(':')<0||actual.getAddress()==null)return false;
    // Only an IPv6 literal reaches getByName; a proxy hostname is never resolved here.
    try{InetAddress literal=InetAddress.getByName(expected);if(!literal.equals(actual.getAddress()))return false;
      return !(literal instanceof Inet6Address)||actual.getAddress() instanceof Inet6Address&&((Inet6Address)literal).getScopeId()==((Inet6Address)actual.getAddress()).getScopeId();
    }catch(Exception invalid){return false;}
  }
  /** New connections also require a fresh service receipt, without probing or selecting a route. */
  void verifyInternal()throws IOException {
    if(internal!=null&&(!internal.verifiedRouteCurrent()||receipt!=internal.verifiedRoute))throw unavailable();
  }
  void watch(){if(closed||failure!=null)return;try{checkCurrent();}catch(Exception changed){lose();}}
  synchronized void lose(){
    if(closed||failure!=null)return;failure=unavailable();watcher.shutdown();
    for(HttpURLConnection connection:active)AppUpdateTransfer.disconnectLater(connection);
  }
  HttpURLConnection open(String target,Opener opener)throws Exception {
    try{
      checkCurrent();verifyInternal();checkCurrent();
      // A required VPN is bound to the verified Network, never the changing default.
      HttpURLConnection connection=bound==null?opener.open(target,proxy):(HttpURLConnection)bound.openConnection(new URL(target),proxy);
      active.add(connection);
      try{checkCurrent();}catch(Exception changed){AppUpdateTransfer.disconnectLater(connection);throw changed;}
      return connection;
    }catch(Exception changed){lose();throw failure==null?unavailable():failure;}
  }
  void released(HttpURLConnection connection){active.remove(connection);}
  @Override public synchronized void close(){
    if(closed)return;closed=true;watcher.shutdownNow();
    for(HttpURLConnection connection:active)AppUpdateTransfer.disconnectLater(connection);active.clear();
  }
}
