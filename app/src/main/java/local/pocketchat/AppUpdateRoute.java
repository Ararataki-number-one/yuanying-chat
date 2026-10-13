package local.pocketchat;

import android.content.Context;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.os.Bundle;
import android.os.Looper;
import org.json.JSONObject;
import java.io.IOException;
import java.net.HttpURLConnection;
import java.net.InetSocketAddress;
import java.net.Proxy;
import java.net.URL;
import java.util.UUID;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

/** Update bytes use an explicitly chosen environment's existing verified route, without its cookies. */
final class AppUpdateRoute {
  static final String DIRECT="direct",INTERNAL="internal";
  static final class Unavailable extends IOException {Unavailable(String message){super(message);}}
  static final class Scope {
    final int slot,generation;final String source;
    Scope(int slot,int generation,String source)throws IOException {
      if(slot<0||slot>=Profiles.MAX||generation<0||!DIRECT.equals(source)&&!INTERNAL.equals(source))throw new Unavailable("请从正在使用的环境打开应用更新");
      this.slot=slot;this.generation=generation;this.source=source;
    }
    Bundle arguments(){Bundle b=new Bundle();b.putInt("slot",slot);b.putInt("environmentGeneration",generation);b.putString("sourceType",source);return b;}
  }
  static final class Lease {
    final Scope scope;final int port;final String identity;
    Lease(Bundle b)throws IOException {scope=new Scope(b.getInt("slot",-1),b.getInt("environmentGeneration",-1),b.getString("sourceType",""));port=b.getInt("proxyPort");identity=b.getString("lease","");if(!INTERNAL.equals(scope.source)||port<1||port>65535||!identity.matches("[a-f0-9]{64}"))throw new Unavailable("环境网络尚未核验，连接后继续下载");}
    Bundle arguments(){Bundle b=scope.arguments();b.putInt("proxyPort",port);b.putString("lease",identity);return b;}
  }
  static final class Selection {final Scope scope;final Lease lease;final String message;Selection(Scope scope,Lease lease,String message){this.scope=scope;this.lease=lease;this.message=message;}}
  static Bundle call(Context c,int slot,String action,Bundle b)throws IOException {
    if(Looper.myLooper()==Looper.getMainLooper())throw new Unavailable("更新联网操作需要后台执行");
    try{Bundle result=Profiles.global(c).getContentResolver().call(NetworkBridge.uri(c,slot),action,null,b);if(result==null||result.getInt("slot",-1)!=slot)throw new Unavailable("环境网络暂时无法读取，恢复后继续下载");return result;}catch(Unavailable e){throw e;}catch(Exception failure){throw new Unavailable("环境网络暂时无法读取，恢复后继续下载");}
  }
  static Selection select(Context c,int slot,Scope expected)throws IOException {
    Bundle request=new Bundle();request.putInt("slot",slot);if(expected!=null){if(expected.slot!=slot)throw new Unavailable("更新将继续使用原环境的网络");request=expected.arguments();}
    Bundle result=call(c,slot,"updateRoute",request);
    if(!result.getBoolean("valid"))throw new Unavailable(result.getString("message","此环境已变化，请重新打开应用更新"));
    Scope scope=new Scope(slot,result.getInt("environmentGeneration",-1),result.getString("sourceType",""));
    if(expected!=null&&(scope.generation!=expected.generation||!scope.source.equals(expected.source)))throw new Unavailable("原环境已变化，请取消下载后重新开始");
    Lease lease=INTERNAL.equals(scope.source)&&result.getBoolean("ready")?new Lease(result):null;
    return new Selection(scope,lease,result.getString("message",""));
  }
  static boolean validScope(Context c,Scope scope)throws IOException {Bundle result=call(c,scope.slot,"validateUpdateRoute",scope.arguments());return result.getBoolean("valid")&&result.getBoolean("ready")&&result.getInt("environmentGeneration",-1)==scope.generation&&scope.source.equals(result.getString("sourceType"));}
  static boolean valid(Context c,Lease lease)throws IOException {Bundle result=call(c,lease.scope.slot,"validateUpdateRoute",lease.arguments());return result.getBoolean("valid")&&result.getBoolean("ready")&&lease.identity.equals(result.getString("lease"));}

  /** Lives in the selected profile process. It never starts, adopts or changes a network core. */
  static final class Server {
    final Context profile;final String lifetime=UUID.randomUUID().toString();final NetworkPoolIdentity.DefaultNetwork network=new NetworkPoolIdentity.DefaultNetwork();
    ConnectivityManager connectivity;boolean watching;
    Server(Context profile){this.profile=profile;}
    synchronized void watch()throws IOException {
      if(watching)return;
      try{connectivity=(ConnectivityManager)profile.getSystemService(Context.CONNECTIVITY_SERVICE);if(connectivity==null)throw new IOException();
        connectivity.registerDefaultNetworkCallback(new ConnectivityManager.NetworkCallback(){
          @Override public void onAvailable(Network n){network.available(n.toString());}
          @Override public void onLost(Network n){network.lost(n.toString());}
          @Override public void onCapabilitiesChanged(Network n,NetworkCapabilities c){network.capabilities(n.toString(),c.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET),c.hasTransport(NetworkCapabilities.TRANSPORT_VPN));}
        });watching=true;refresh();
      }catch(Exception error){network.unknown();throw new Unavailable("手机网络尚未连接，恢复后继续下载");}
    }
    void refresh(){Network active=connectivity.getActiveNetwork();NetworkCapabilities caps=active==null?null:connectivity.getNetworkCapabilities(active);if(caps==null)network.unknown();else network.initial(active.toString(),caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET),caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN));}
    void currentScope(int slot,int generation,String source)throws IOException {JSONObject row=ProfileCatalog.get(profile).item(slot);String mode=profile.getSharedPreferences("chat",0).getString("networkMode","external");if(!row.optBoolean("created")||(row.optBoolean("deleting")||row.optBoolean("resetting"))||row.optInt("generation")!=generation||!(INTERNAL.equals(source)?"internal":"external").equals(mode))throw new Unavailable("原环境网络已变化，恢复后继续下载");}
    boolean sessionAllows(ChatSession session){return session==null||!session.deleted&&Profiles.slot(session.context)==Profiles.slot(profile)&&session.internalNetwork()&&session.networkReady&&!session.connecting&&!session.offline&&session.guard!=null&&session.guard.allowed();}
    Bundle response(Bundle request,boolean validate){
      Bundle out=new Bundle();int slot=Profiles.slot(profile);out.putInt("slot",slot);
      try{
        if(Looper.myLooper()==Looper.getMainLooper()||request==null||request.getInt("slot",-1)!=slot||Profiles.processSlot()!=slot)throw new Unavailable("更新环境不匹配，已停止联网");
        JSONObject row=ProfileCatalog.get(profile).item(slot);int generation=row.optInt("generation");
        if(!row.optBoolean("created")||(row.optBoolean("deleting")||row.optBoolean("resetting"))||request.containsKey("environmentGeneration")&&request.getInt("environmentGeneration")!=generation)throw new Unavailable("原环境已删除或重新创建，请重新开始下载");
        out.putInt("environmentGeneration",generation);String mode=profile.getSharedPreferences("chat",0).getString("networkMode","external");
        if(!"internal".equals(mode)&&!"external".equals(mode))throw new Unavailable("环境网络方式暂时无法读取，请重新检查设置");
        // ChatSession.internalNetwork follows mode, including legacy records without the configured flag.
        String source="internal".equals(mode)?INTERNAL:DIRECT;out.putString("sourceType",source);
        if(request.containsKey("sourceType")&&!source.equals(request.getString("sourceType")))throw new Unavailable("原环境的网络方式已变化，请取消下载后重新开始");
        if(DIRECT.equals(source)){if(validate&&!DIRECT.equals(request.getString("sourceType")))throw new Unavailable("原环境网络已中断，恢复后继续下载");currentScope(slot,generation,source);out.putBoolean("valid",true);out.putBoolean("ready",true);out.putString("message","通过手机网络下载");return out;}
        out.putBoolean("valid",true);out.putString("message","恢复环境网络后继续下载");
        NativeNetwork n=NativeNetwork.get(profile);if(Profiles.slot(n.context)!=slot)throw new Unavailable("更新环境不匹配，已停止联网");NativeNetwork.ExitRouteReceipt receipt=n.verifiedRoute;
        ChatSession session=ChatSession.peek();
        if(!n.ready||n.starting||n.recoveryBlocked||receipt==null||n.transport==null||!sessionAllows(session))return out;
        watch();refresh();NetworkPoolIdentity.NetworkSnapshot before=network.snapshot();if(!before.usable())return out;
        JSONObject state=n.transport.call("snapshot","");
        if(!receipt.matches(n,state)||!n.ready||n.starting||n.recoveryBlocked||n.verifiedRoute==null||!n.verifiedRoute.matches(n,state))return out;
        NetworkPoolIdentity.Route route=new NetworkPoolIdentity.Route(slot,receipt.generation,receipt.pid,receipt.servicePid,receipt.configuration,receipt.entry,receipt.fingerprint,receipt.serial,receipt.controller,receipt.proxy,receipt.token);
        if(!route.usable())return out;
        refresh();if(!before.equals(network.snapshot())||!receipt.matches(n,n.transport.state)||!n.ready||n.starting||n.recoveryBlocked||!sessionAllows(ChatSession.peek()))return out;
        currentScope(slot,generation,source);
        String identity=NativeNetwork.hash(lifetime+"|"+generation+"|"+receipt.generation+"|"+receipt.pid+"|"+receipt.servicePid+"|"+receipt.configuration+"|"+receipt.entry+"|"+receipt.fingerprint+"|"+receipt.serial+"|"+receipt.controller+"|"+receipt.proxy+"|"+receipt.token+"|"+before.identity+"|"+before.revision+"|"+before.internet+"|"+before.vpn);
        if(validate&&(!identity.equals(request.getString("lease"))||receipt.proxy!=request.getInt("proxyPort")))return out;
        out.putString("lease",identity);out.putInt("proxyPort",receipt.proxy);out.putBoolean("ready",true);out.putString("message","通过"+row.optString("name","当前环境")+"下载");return out;
      }catch(Exception error){out.putBoolean("valid",false);out.putBoolean("ready",false);out.putString("message",error.getMessage()!=null&&error.getMessage().matches("(?s).*[\\u4e00-\\u9fff].*")?error.getMessage():"环境网络暂时不可用，恢复后继续下载");return out;}
    }
  }
  interface Opener {HttpURLConnection open(String url,Proxy proxy)throws IOException;}
  static final Opener OFFICIAL=(url,proxy)->(HttpURLConnection)new URL(url).openConnection(proxy);
  static final class Factory implements AppUpdateTransfer.ConnectionFactory {
    final Context context;final Scope scope;final Lease lease;final Opener opener;final AppUpdateTransfer.ConnectionFactory direct;final String origin;
    final AtomicReference<HttpURLConnection> active=new AtomicReference<>();
    final ScheduledExecutorService watcher=Executors.newSingleThreadScheduledExecutor(r->{Thread t=new Thread(r,"update-route-watch");t.setPriority(Thread.MIN_PRIORITY);return t;});
    volatile IOException failure;volatile boolean closed;
    Factory(Context context,Selection selected,Opener opener,AppUpdateTransfer.ConnectionFactory direct,String origin){this.context=Profiles.global(context);this.scope=selected.scope;this.lease=selected.lease;this.opener=opener;this.direct=direct;this.origin=origin;watcher.scheduleWithFixedDelay(this::watch,1000,1000,TimeUnit.MILLISECONDS);}
    boolean admitted()throws IOException {return lease==null?DIRECT.equals(scope.source)&&validScope(context,scope):valid(context,lease);}
    void watch(){if(closed||failure!=null)return;try{if(!admitted())lose();}catch(IOException unavailable){lose();}}
    synchronized void lose(){if(closed||failure!=null)return;failure=new Unavailable("环境网络已变化，恢复后继续下载");watcher.shutdown();HttpURLConnection connection=active.get();if(connection!=null)AppUpdateTransfer.disconnectLater(connection);}
    @Override public void check()throws IOException {if(failure!=null)throw failure;if(closed)throw new Unavailable("下载已暂停，进度已保留");if(lease==null)direct.check();}
    @Override public HttpURLConnection open(String url)throws IOException {
      if(!(AppUpdatePolicy.FEED.equals(origin)?AppUpdatePolicy.feedRedirect(url):AppUpdateTransfer.officialOrigin(origin)&&AppUpdateTransfer.trusted(url,origin)))throw new AppUpdateTransfer.InvalidResponse("更新下载地址不受信任，已停止下载");
      check();if(!admitted()){lose();throw failure;}check();
      HttpURLConnection connection=lease==null?direct.open(url):opener.open(url,new Proxy(Proxy.Type.HTTP,new InetSocketAddress("127.0.0.1",lease.port)));active.set(connection);
      if(closed||failure!=null){AppUpdateTransfer.disconnectLater(connection);check();}return connection;
    }
    @Override public synchronized void finished(){if(closed)return;closed=true;watcher.shutdownNow();active.set(null);if(lease==null)direct.finished();}
  }
}
