package local.pocketchat;

import android.app.Activity;
import android.content.*;
import android.database.ContentObserver;
import android.net.*;
import android.os.*;
import android.webkit.*;
import androidx.webkit.ProxyConfig;
import androidx.webkit.ProxyController;
import androidx.webkit.WebViewFeature;
import java.io.*;
import java.net.*;
import java.net.Proxy;
import java.util.concurrent.*;

/** One HTTP(S) request route for system WebViews in an environment process.
 * ProxyController is not a WebRTC/ICE/STUN/UDP control or a device VPN; public
 * Android WebView APIs do not expose Gecko's native WebRTC-disable policy.
 * This process request gate is not a Gecko identity policy or kernel switch. */
final class ChromiumRuntime implements AutoCloseable {
  interface Listener {void changed(boolean ready,String reason);}
  static volatile ChromiumRuntime owner;
  static final ChromiumRoutePolicy.ProxyQueue proxyQueue=new ChromiumRoutePolicy.ProxyQueue();
  final Activity activity;final Context context;final Listener listener;final SharedPreferences prefs;
  final Handler main=new Handler(Looper.getMainLooper());
  final ExecutorService reader=Executors.newSingleThreadExecutor(r->{Thread t=new Thread(r,"chromium-route");t.setPriority(Thread.NORM_PRIORITY-1);return t;});
  final ChromiumRoutePolicy policy=new ChromiumRoutePolicy();
  final ConnectivityManager connectivity;final NativeNetwork network;
  final SharedPreferences.OnSharedPreferenceChangeListener preferenceListener=(p,key)->{if("networkMode".equals(key)||"proxy".equals(key)||"requireExternalVpn".equals(key)||"networkConfigured".equals(key))changedRoute();};
  final Runnable nativeListener=this::nativeChanged;
  final Runnable leaseListener=this::leaseChanged;
  final ConnectivityManager.NetworkCallback networkListener=new ConnectivityManager.NetworkCallback(){
    public void onAvailable(Network value){defaultNetworkChanged();}
    public void onLost(Network value){defaultNetworkChanged();}
    public void onCapabilitiesChanged(Network value,NetworkCapabilities capabilities){defaultNetworkChanged();}
    public void onLinkPropertiesChanged(Network value,LinkProperties properties){defaultNetworkChanged();}
  };
  final ContentObserver catalogListener=new ContentObserver(main){public void onChange(boolean self){checkIdentity();}};
  volatile Route route;volatile boolean closed,observing;volatile String message="浏览器网络尚未就绪";
  boolean refreshQueued,protectionReady,surfaceDeferred;int leaseChanges;String observedNetworkKey="";volatile EnvironmentSpec.Identity identity;
  ChromiumRuntime(Activity activity,Listener listener){
    this.activity=activity;this.listener=listener;context=Profiles.context(activity,Profiles.processSlot());
    prefs=context.getSharedPreferences("chat",0);connectivity=(ConnectivityManager)context.getSystemService(Context.CONNECTIVITY_SERVICE);network=NativeNetwork.get(context);
  }
  void start(){onMain(()->{
    if(closed)return;if(owner==this&&protectionReady){refresh();return;}if(owner!=null&&owner!=this)owner.close();owner=this;
    if(!observing){observing=true;prefs.registerOnSharedPreferenceChangeListener(preferenceListener);network.addRouteListener(nativeListener);leaseChanges=ChromiumRouteLease.snapshot().changes;ChromiumRouteLease.addListener(leaseListener);
      try{if(connectivity==null)throw new IllegalStateException();observedNetworkKey=defaultNetworkKey();connectivity.registerDefaultNetworkCallback(networkListener);}catch(RuntimeException unavailable){block("无法监测当前网络，浏览器已暂停");return;}
      context.getContentResolver().registerContentObserver(DownloadLibraryChanges.uri(context),false,catalogListener);
    }
    try{ServiceWorkerController workers=ServiceWorkerController.getInstance();workers.getServiceWorkerWebSettings().setBlockNetworkLoads(true);workers.getServiceWorkerWebSettings().setAllowContentAccess(false);workers.getServiceWorkerWebSettings().setAllowFileAccess(false);
      workers.setServiceWorkerClient(new ServiceWorkerClient(){@Override public WebResourceResponse shouldInterceptRequest(WebResourceRequest request){ChromiumRuntime active=owner;return active!=null&&active.allowed()&&publicWeb(request.getUrl())?null:BrowserNetworkGuard.denied();}});
    }catch(RuntimeException unavailable){block("当前 Chromium 无法建立后台请求保护，请更新系统 WebView");return;}
    protectionReady=true;refresh();
  });}
  void refresh(){onMain(()->{
    if(closed||owner!=this)return;
    if(!protectionReady){block("浏览器请求保护尚未建立，请重新打开浏览器");return;}
    Route retained=route;if(retained!=null&&policy.retain(retained.ticket,retained.evidenceCurrent()))return;
    block("正在准备浏览器线路…");ChromiumRoutePolicy.Ticket ticket=policy.begin();
    try{if(!WebViewFeature.isFeatureSupported(WebViewFeature.PROXY_OVERRIDE)){block("系统 WebView 不支持受控代理，请更新 Android System WebView");return;}}catch(RuntimeException unavailable){block("系统 WebView 不可用，请安装或更新 Android System WebView");return;}
    try{reader.execute(()->prepare(ticket));}catch(RejectedExecutionException ignored){}
  });}
  void prepare(ChromiumRoutePolicy.Ticket ticket){
    try{
      EnvironmentSpec.Identity expected=ProfileCatalog.get(context).identity(Profiles.slot(context));
      if(identity!=null&&!identity.equals(expected))throw new IOException("环境身份已变化，请重新打开浏览器");identity=expected;
      if(!policy.pending(ticket))return;
      String mode=prefs.getString("networkMode","external"),proxy=prefs.getString("proxy","").trim();
      boolean required=prefs.getBoolean("requireExternalVpn",true),configured=prefs.getBoolean("networkConfigured",false);
      if(!configured)throw new IOException("请先在环境网络中配置浏览器线路");
      if("internal".equals(mode)){
        if(network.recoveryBlocked)throw new IOException("固定出口尚未确认，请先检查环境网络");
        main.post(()->{if(!policy.pending(ticket)||closed)return;network.start((ok,text)->{if(!policy.pending(ticket)||closed)return;if(!ok){block(text);return;}try{reader.execute(()->prepareInternal(ticket,expected,mode,proxy,required));}catch(RejectedExecutionException ignored){}});});return;
      }
      if(!"external".equals(mode))throw new IOException("网络模式无效，浏览器已暂停");
      if(!proxy.isEmpty()&&!validProxy(proxy))throw new IOException("代理地址无效，浏览器已暂停");
      Network vpn=null;
      if(BrowserNetworkGuard.needsVpn(false,proxy,required)){
        if(!BrowserNetworkGuard.vpnDefaultRouteIssue(context).isEmpty())throw new IOException("VPN 路由覆盖尚未确认，请使用完整覆盖的 VPN、应用内线路或显式代理");
        vpn=connectivity.getActiveNetwork();if(vpn==null)throw new IOException("VPN 已断开");
      }
      Route selected=new Route(ticket,expected,mode,proxy,required,null,vpn);apply(selected);
    }catch(Exception error){fail(ticket,error);}
  }
  void prepareInternal(ChromiumRoutePolicy.Ticket ticket,EnvironmentSpec.Identity expected,String mode,String proxy,boolean required){
    try{EnvironmentSpecRuntime.requireIdentity(context,expected);NativeNetwork.ExitRouteReceipt receipt=network.verifiedRoute;
      if(!internalCurrent(receipt))throw new IOException("内置网络尚未通过线路核验");
      apply(new Route(ticket,expected,mode,proxy,required,receipt,null));
    }catch(Exception error){fail(ticket,error);}
  }
  void apply(Route selected){main.post(()->{
    if(closed||owner!=this||!policy.pending(selected.ticket))return;
    if(!selected.evidenceCurrent()){block("线路已变化，请重新连接");return;}
    proxyQueue.submit(()->applyProxy(selected));
  });}
  void applyProxy(Route selected){
    if(closed||owner!=this||!policy.pending(selected.ticket)||!selected.evidenceCurrent()){proxyQueue.complete();return;}
    try{
      Runnable applied=()->{
        proxyQueue.complete();
        if(closed||owner!=this||!policy.pending(selected.ticket))return;
        try{
          if(!selected.evidenceCurrent()||!policy.admit(selected.ticket,true)){block("线路已变化，请重新连接");return;}
          identity=selected.identity;route=selected;
          ServiceWorkerController.getInstance().getServiceWorkerWebSettings().setBlockNetworkLoads(false);
          message=selected.receipt!=null?"Chromium · 已核验应用内线路":selected.proxyAddress.isEmpty()?selected.vpn!=null?"Chromium · 已确认 VPN 路由":"Chromium · 系统网络":"Chromium · 显式代理";
          listener.changed(true,message);
        }catch(RuntimeException unavailable){block("浏览器后台请求保护暂时不可用，联网已暂停");}
      };
      if(selected.proxyRule().isEmpty()){
        // This branch is only an explicit external-system-route setting. An
        // unavailable internal/proxy route never falls back to clear/direct.
        ProxyController.getInstance().clearProxyOverride(main::post,applied);
      }else ProxyController.getInstance().setProxyOverride(new ProxyConfig.Builder().addProxyRule(selected.proxyRule()).removeImplicitRules().build(),main::post,applied);
    }catch(RuntimeException unavailable){proxyQueue.complete();if(policy.pending(selected.ticket))block("浏览器代理应用失败，联网已暂停");}
  }
  static boolean validProxy(String value){try{Uri uri=Uri.parse(value);String scheme=uri.getScheme();return ("http".equals(scheme)||"https".equals(scheme)||"socks".equals(scheme))&&uri.getHost()!=null&&uri.getPort()>0&&uri.getPort()<65536&&uri.getUserInfo()==null&&(uri.getPath()==null||uri.getPath().isEmpty())&&uri.getQuery()==null&&uri.getFragment()==null;}catch(RuntimeException invalid){return false;}}
  static boolean publicWeb(Uri uri){return uri!=null&&BrowserAddressPolicy.allowed(uri.toString());}
  boolean internalCurrent(NativeNetwork.ExitRouteReceipt receipt){
    NativeNetwork.ExitRouteReceipt admitted=network.verifiedRoute;
    if(receipt==null||admitted==null||!network.ready||network.starting||network.recoveryBlocked||!network.connectionAdmission().usable())return false;
    org.json.JSONObject state=network.transport==null?null:network.transport.state;
    // Routine exit verification renews the receipt object. Preserve a page and
    // its download lease when both proofs bind the identical live core, route
    // serial, entry and proxy; any actual replacement fails matches().
    return admitted.matches(network,state)&&receipt.matches(network,state)&&admitted==network.verifiedRoute&&network.ready&&!network.starting&&!network.recoveryBlocked;
  }
  boolean allowed(){Route selected=route;boolean valid=!closed&&owner==this&&selected!=null&&policy.current(selected.ticket)&&selected.evidenceCurrent();if(!valid&&selected!=null)onMain(()->{if(route==selected)block("浏览器线路已中断，已暂停联网");});return valid;}
  String status(){return message;}
  Object routeStamp(){Route selected=route;return allowed()?selected.ticket:null;}
  boolean current(Object stamp){Route selected=route;return selected!=null&&stamp==selected.ticket&&allowed();}
  Proxy verifiedProxy(){DownloadRoute lease=downloadRoute();return lease==null?null:lease.proxy();}
  DownloadRoute downloadRoute(){Route selected=route;return allowed()?new DownloadRoute(selected):null;}
  String defaultNetworkKey(){Network active=connectivity==null?null:connectivity.getActiveNetwork();NetworkCapabilities caps=active==null?null:connectivity.getNetworkCapabilities(active);return active==null||caps==null?"unavailable":active.toString()+"|"+caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)+"|"+caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN);}
  void defaultNetworkChanged(){onMain(()->{if(closed||owner!=this)return;String key;try{key=defaultNetworkKey();}catch(RuntimeException unavailable){key="unavailable";}if(key.equals(observedNetworkKey)){Route selected=route;if(selected!=null&&!selected.evidenceCurrent())changedRoute();return;}observedNetworkKey=key;changedRoute();});}
  void changedRoute(){onMain(()->{if(closed||owner!=this)return;block("网络设置或默认线路已变化，正在重新连接…");if(refreshQueued)return;refreshQueued=true;main.post(()->{refreshQueued=false;if(!closed)refresh();});});}
  void nativeChanged(){onMain(()->{if(closed||owner!=this)return;Route selected=route;if(selected!=null&&selected.receipt!=null&&!selected.evidenceCurrent())block("应用内线路已变化，浏览器已暂停");if(route==null&&"internal".equals(prefs.getString("networkMode","external"))&&network.ready&&!network.starting&&!network.recoveryBlocked)changedRoute();});}
  void surfaceDeferred(){surfaceDeferred=true;if(ChromiumRouteLease.snapshot().changes==0)main.post(this::leaseChanged);}
  void leaseChanged(){int changes=ChromiumRouteLease.snapshot().changes;onMain(()->{boolean finished=changes==0&&(leaseChanges>0||surfaceDeferred);leaseChanges=changes;if(finished&&!closed&&owner==this){surfaceDeferred=false;if(allowed())listener.changed(true,message);else refresh();}});}
  void checkIdentity(){try{reader.execute(()->{try{EnvironmentSpec.Identity expected=identity;if(expected!=null&&!expected.equals(ProfileCatalog.get(context).identity(Profiles.slot(context))))onMain(()->close());}catch(Exception removed){onMain(()->close());}});}catch(RejectedExecutionException ignored){}}
  void fail(ChromiumRoutePolicy.Ticket ticket,Exception error){main.post(()->{if(policy.pending(ticket))block(error.getMessage()==null?"浏览器线路尚未就绪":error.getMessage());});}
  void block(String reason){policy.block();route=null;message=reason==null?"浏览器线路尚未就绪":reason;try{ServiceWorkerController.getInstance().getServiceWorkerWebSettings().setBlockNetworkLoads(true);}catch(RuntimeException ignored){}if(!closed)listener.changed(false,message);}
  static void stopProcess(){ChromiumRuntime active=owner;if(active!=null)active.close();}
  @Override public void close(){onMain(()->{
    if(closed)return;block("浏览器已停止联网");closed=true;policy.close();if(owner==this)owner=null;
    if(observing){observing=false;ChromiumRouteLease.removeListener(leaseListener);prefs.unregisterOnSharedPreferenceChangeListener(preferenceListener);network.removeRouteListener(nativeListener);try{connectivity.unregisterNetworkCallback(networkListener);}catch(RuntimeException ignored){}try{context.getContentResolver().unregisterContentObserver(catalogListener);}catch(RuntimeException ignored){}}
    reader.shutdownNow();
    // Keep the last proxy override in place. Clearing here could expose another
    // system WebView or a persisted worker to the default direct route.
  });}
  void onMain(Runnable task){if(Looper.myLooper()==Looper.getMainLooper())task.run();else main.post(task);}
  final class Route {
    final ChromiumRoutePolicy.Ticket ticket;final EnvironmentSpec.Identity identity;final String mode,proxyAddress;final boolean requireVpn;final NativeNetwork.ExitRouteReceipt receipt;final Network vpn;
    Route(ChromiumRoutePolicy.Ticket ticket,EnvironmentSpec.Identity identity,String mode,String proxy,boolean required,NativeNetwork.ExitRouteReceipt receipt,Network vpn){this.ticket=ticket;this.identity=identity;this.mode=mode;proxyAddress=proxy;requireVpn=required;this.receipt=receipt;this.vpn=vpn;}
    boolean evidenceCurrent(){
      if(closed||!policy.pending(ticket)||!mode.equals(prefs.getString("networkMode","external"))||!proxyAddress.equals(prefs.getString("proxy","").trim())||requireVpn!=prefs.getBoolean("requireExternalVpn",true)||!prefs.getBoolean("networkConfigured",false))return false;
      if(receipt!=null)return internalCurrent(receipt);
      if(vpn!=null)return vpn.equals(connectivity.getActiveNetwork())&&BrowserNetworkGuard.vpnDefaultRouteIssue(context).isEmpty();
      return !BrowserNetworkGuard.needsVpn(false,proxyAddress,requireVpn);
    }
    String proxyRule(){return receipt!=null?"http://127.0.0.1:"+receipt.proxy:proxyAddress;}
    Proxy javaProxy(){if(receipt!=null)return new Proxy(Proxy.Type.HTTP,new InetSocketAddress("127.0.0.1",receipt.proxy));if(proxyAddress.isEmpty())return Proxy.NO_PROXY;Uri uri=Uri.parse(proxyAddress);return new Proxy("socks".equals(uri.getScheme())?Proxy.Type.SOCKS:Proxy.Type.HTTP,InetSocketAddress.createUnresolved(uri.getHost(),uri.getPort()));}
  }
  final class DownloadRoute {
    final Route selected;DownloadRoute(Route selected){this.selected=selected;}
    Proxy proxy(){return selected.javaProxy();}
    boolean current(){return ChromiumRuntime.this.current(selected.ticket);}
    HttpURLConnection open(URL url)throws IOException{
      if(!current())throw new IOException("下载线路已变化，请重新下载");
      if(!publicWeb(Uri.parse(url.toExternalForm())))throw new IOException("下载地址必须是公共 HTTP(S) 网址");
      if(selected.proxyAddress.startsWith("https://"))throw new IOException("当前 HTTPS 代理暂不支持原生下载，请改用应用内线路或 HTTP 代理");
      if(selected.proxyAddress.startsWith("socks://"))throw new IOException("当前 SOCKS 代理暂不支持受控原生下载，请改用应用内线路或 HTTP 代理");
      URLConnection connection=selected.vpn!=null?selected.vpn.openConnection(url):url.openConnection(proxy());
      if(!(connection instanceof HttpURLConnection))throw new IOException("下载连接类型无效");HttpURLConnection http=(HttpURLConnection)connection;
      if(!current()){http.disconnect();throw new IOException("下载线路已变化，请重新下载");}return http;
    }
  }
}
