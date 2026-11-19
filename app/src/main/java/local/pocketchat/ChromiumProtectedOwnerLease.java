package local.pocketchat;

import android.content.ContentProviderClient;
import android.content.Context;
import android.content.SharedPreferences;
import android.net.ConnectivityManager;
import android.net.LinkProperties;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.os.Binder;
import android.os.Bundle;
import android.os.IBinder;
import android.os.Looper;
import android.os.Parcel;
import android.os.RemoteException;
import android.os.SystemClock;
import java.io.IOException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

/** A one-generation route fence in the source environment process, held until the relay stops. */
final class ChromiumProtectedOwnerLease implements AutoCloseable {
  static final String ACQUIRE="chromiumOwnerAcquire", CHECK="chromiumOwnerCheck", RELEASE="chromiumOwnerRelease";
  private static final String DESCRIPTOR="local.pocketchat.ChromiumProtectedOwnerLease";
  private static final int REVOKE=IBinder.FIRST_CALL_TRANSACTION;
  private static final java.util.concurrent.Executor RELEASE_WORK=Executors.newSingleThreadExecutor(task->{
    Thread thread=new Thread(task,"chromium-owner-release");thread.setDaemon(true);return thread;
  });
  private final ContentProviderClient provider;
  private final Request request;
  private final ClientBinder client;
  private final IBinder owner;
  private final String token;
  private final int proxyPort;
  private final AtomicBoolean closed=new AtomicBoolean();
  private final IBinder.DeathRecipient ownerDeath;

  static ChromiumProtectedOwnerLease acquire(Context context, EnvironmentSpec.Identity identity, Runnable onRevoked)throws IOException {
    return acquire(context,new Request(identity,true,"",false,""),onRevoked);
  }

  static ChromiumProtectedOwnerLease acquireExternal(Context context,EnvironmentSpec.Identity identity,
      String proxyPreference,boolean requireVpn,String expectedNetwork,Runnable onRevoked)throws IOException {
    return acquire(context,new Request(identity,false,proxyPreference,requireVpn,expectedNetwork),onRevoked);
  }

  private static ChromiumProtectedOwnerLease acquire(Context context, Request requested,Runnable onRevoked)throws IOException {
    requireWorker();
    ContentProviderClient provider=null;
    ChromiumProtectedOwnerLease lease=null;
    ClientBinder callback=new ClientBinder(onRevoked);
    String token=null;
    boolean acquired=false;
    try{
      provider=Profiles.global(context).getContentResolver().acquireUnstableContentProviderClient(NetworkBridge.uri(context,requested.identity.slot));
      if(provider==null)throw unavailable();
      Bundle received=provider.call(ACQUIRE,null,requested.bundle(callback,null));
      if(received==null||!received.getBoolean("accepted"))throw unavailable();
      token=received.getString("ownerToken");
      IBinder owner=received.getBinder("ownerBinder");
      int port=received.getInt("proxyPort",-1);
      if(!requested.identity.equals(Request.identity(received))||token==null||token.isEmpty()||owner==null
          ||(requested.internal?(port<1||port>65535):port!=0))throw unavailable();
      lease=new ChromiumProtectedOwnerLease(provider,requested,callback,owner,token,port);
      owner.linkToDeath(lease.ownerDeath,0);
      if(!lease.recheck())throw unavailable();
      acquired=true;return lease;
    }catch(RemoteException|RuntimeException failure){throw unavailable();}
    finally{
      if(!acquired){
        if(lease!=null)lease.close();
        else if(provider!=null)release(provider,requested,callback,token);
      }
    }
  }

  private ChromiumProtectedOwnerLease(ContentProviderClient provider,Request request,ClientBinder client,
      IBinder owner,String token,int proxyPort){
    this.provider=provider;this.request=request;this.client=client;this.owner=owner;
    this.token=token;this.proxyPort=proxyPort;ownerDeath=()->{if(!closed.get())client.revoke();};
  }

  /** Internal core proxy port. External leases fence the network but do not supply a proxy. */
  int proxyPort(){return proxyPort;}

  /** Sticky fail-closed hint, usable without a binder round trip on the hot path. */
  boolean current(){return !closed.get()&&!client.revoked.get()&&owner.isBinderAlive();}

  /** For a worker: validate just before dial and again after dial before sending bytes. */
  boolean recheck(){
    if(Looper.myLooper()==Looper.getMainLooper())return false;
    if(!current()){if(!closed.get())client.revoke();return false;}
    try{
      Bundle checked=provider.call(CHECK,null,request.bundle(client,token));
      if(checked!=null&&checked.getBoolean("accepted")&&current())return true;
    }catch(RemoteException|RuntimeException unavailable){}
    client.revoke();return false;
  }

  /** Call only after the relay has denied new traffic and closed its socket pairs. */
  @Override public void close(){
    if(!closed.compareAndSet(false,true))return;
    try{owner.unlinkToDeath(ownerDeath,0);}catch(RuntimeException ignored){}
    Runnable relinquish=()->release(provider,request,client,token);
    if(Looper.myLooper()==Looper.getMainLooper())RELEASE_WORK.execute(relinquish);else relinquish.run();
  }

  private static void release(ContentProviderClient provider,Request request,IBinder client,String token){
    try{if(token!=null)provider.call(RELEASE,null,request.bundle(client,token));}
    catch(RemoteException|RuntimeException ignored){}
    finally{provider.close();}
  }

  private static void requireWorker()throws IOException {
    if(Looper.myLooper()==Looper.getMainLooper())throw unavailable();
  }
  private static IOException unavailable(){return new IOException("Chromium 的环境线路尚未确认");}

  private static final class ClientBinder extends Binder {
    final AtomicBoolean revoked=new AtomicBoolean();
    final Runnable callback;
    ClientBinder(Runnable callback){this.callback=callback;}
    void revoke(){if(revoked.compareAndSet(false,true)&&callback!=null)try{callback.run();}catch(RuntimeException ignored){}}
    @Override protected boolean onTransact(int code,Parcel data,Parcel reply,int flags)throws RemoteException {
      if(code!=REVOKE)return super.onTransact(code,data,reply,flags);
      if(getCallingUid()!=android.os.Process.myUid())throw new SecurityException();
      data.enforceInterface(DESCRIPTOR);revoke();return true;
    }
  }

  private static final class Request {
    final EnvironmentSpec.Identity identity;
    final boolean internal, requireVpn;
    final String proxy, network;
    Request(EnvironmentSpec.Identity identity,boolean internal,String proxy,boolean requireVpn,String network)throws IOException {
      if(identity==null||proxy==null||proxy.length()>4096||network==null||network.length()>128||(!internal&&network.isEmpty()))throw unavailable();
      this.identity=identity;this.internal=internal;this.proxy=proxy.trim();this.requireVpn=requireVpn;this.network=network;
    }
    static EnvironmentSpec.Identity identity(Bundle value){
      return new EnvironmentSpec.Identity(value.getInt("slot",-1),value.getInt("environmentGeneration",-1),value.getString("environmentId"));
    }
    static Request parse(Bundle value)throws IOException {
      return new Request(identity(value),value.getBoolean("internal"),value.getString("proxy",""),
          value.getBoolean("requireVpn"),value.getString("expectedNetwork",""));
    }
    Bundle bundle(IBinder client,String token){
      Bundle out=new Bundle();out.putInt("slot",identity.slot);out.putInt("environmentGeneration",identity.generation);
      out.putString("environmentId",identity.environmentId);out.putBoolean("internal",internal);out.putString("proxy",proxy);
      out.putBoolean("requireVpn",requireVpn);out.putString("expectedNetwork",network);out.putBinder("clientBinder",client);
      if(token!=null)out.putString("ownerToken",token);return out;
    }
  }

  /** The binder endpoint lives beside the existing updater proof and route mutations. */
  static final class Server {
    private static final int MAX_HOLDERS=8;
    private final Context profile;
    private final AppUpdateRoute.Server routes;
    private final SharedPreferences preferences;
    private final IBinder lifetime=new Binder();
    private final Map<String,Entry> entries=new HashMap<>();
    private final AtomicBoolean wakePosted=new AtomicBoolean();
    private final ScheduledExecutorService monitor=Executors.newSingleThreadScheduledExecutor(task->{
      Thread thread=new Thread(task,"chromium-owner-watch");thread.setDaemon(true);return thread;
    });
    private final SharedPreferences.OnSharedPreferenceChangeListener settings=(prefs,key)->{
      if("networkMode".equals(key)||"networkConfigured".equals(key)||"proxy".equals(key)||"requireExternalVpn".equals(key))revokeAll();
    };
    private volatile boolean maintenance;
    private boolean watching;
    private NativeNetwork watchedNative;

    Server(Context profile,AppUpdateRoute.Server routes){
      this.profile=profile;this.routes=routes;preferences=profile.getSharedPreferences("chat",Context.MODE_PRIVATE);
    }
    static boolean handles(String method){return ACQUIRE.equals(method)||CHECK.equals(method)||RELEASE.equals(method);}

    Bundle call(String method,Bundle values){
      Bundle denied=new Bundle();
      try{
        requireWorker();
        if(values==null)return denied;
        IBinder client=values.getBinder("clientBinder");
        Request requested=Request.parse(values);
        if(client==null||requested.identity.slot!=Profiles.slot(profile)||Profiles.processSlot()!=requested.identity.slot)return denied;
        if(ACQUIRE.equals(method))return admit(requested,client);
        Entry entry;
        synchronized(entries){entry=entries.get(values.getString("ownerToken"));}
        if(entry==null||!entry.client.equals(client)||!entry.request.identity.equals(requested.identity))return denied;
        if(RELEASE.equals(method)){releaseEntry(entry);return accepted(entry);}
        if(CHECK.equals(method)&&check(entry))return accepted(entry);
      }catch(IOException|RemoteException|RuntimeException unavailable){}
      return denied;
    }

    private Bundle admit(Request requested,IBinder client)throws IOException,RemoteException {
      if(maintenance||!client.isBinderAlive())throw unavailable();
      ensureWatch(requested.internal);
      ChromiumRouteLease.Handle handle=ChromiumRouteLease.acquireSurface();
      if(handle==null)throw unavailable();
      Entry entry=null;
      try{
        Stamp stamp=capture(requested,null);
        entry=new Entry(requested,client,stamp,handle);
        client.linkToDeath(entry.death,0);
        synchronized(entries){
          if(maintenance||entries.size()>=MAX_HOLDERS||entry.released.get()||!client.isBinderAlive())throw unavailable();
          entries.put(entry.token,entry);
        }
        if(!check(entry))throw unavailable();
        return accepted(entry);
      }catch(IOException|RemoteException|RuntimeException unavailable){
        if(entry!=null)releaseEntry(entry);
        throw unavailable;
      }finally{if(entry==null)handle.close();}
    }

    private Bundle accepted(Entry entry){
      Bundle out=entry.request.bundle(null,entry.token);out.putBinder("ownerBinder",lifetime);
      out.putInt("proxyPort",entry.stamp.internal==null?0:entry.stamp.internal.port);out.putBoolean("accepted",true);return out;
    }

    private boolean check(Entry entry){
      if(maintenance||entry.released.get()||entry.revoked.get()||!entry.client.isBinderAlive())return false;
      try{capture(entry.request,entry.stamp);return !maintenance&&!entry.released.get()&&!entry.revoked.get();}
      catch(IOException|RuntimeException unavailable){revoke(entry);return false;}
    }

    private Stamp capture(Request requested,Stamp expected)throws IOException {
      if(maintenance||!ProfileCatalog.get(profile).identity(requested.identity.slot).equals(requested.identity))throw unavailable();
      Map<String,?> prefs=preferences.getAll();
      if(!Boolean.TRUE.equals(prefs.get("networkConfigured")))throw unavailable();
      AppUpdateRoute.Lease proof=null;
      if(requested.internal){
        if(!"internal".equals(prefs.get("networkMode"))||!internalUsable())throw unavailable();
        Bundle args=expected==null?new AppUpdateRoute.Scope(requested.identity.slot,requested.identity.generation,AppUpdateRoute.INTERNAL).arguments():expected.internal.arguments();
        Bundle result=routes.response(args,expected!=null);
        if(!result.getBoolean("valid")||!result.getBoolean("ready"))throw unavailable();
        proof=new AppUpdateRoute.Lease(result);
        if(proof.scope.slot!=requested.identity.slot||proof.scope.generation!=requested.identity.generation||!internalUsable()
            ||(expected!=null&&(!proof.identity.equals(expected.internal.identity)||proof.port!=expected.internal.port)))throw unavailable();
      }else{
        CefriumRoutePolicy.Selection configured=CefriumRoutePolicy.selection(prefs);
        if(configured==null||configured.mode==CefriumRoutePolicy.Mode.INTERNAL
            ||!requested.proxy.equals(configured.proxyPreference)||requested.requireVpn!=configured.requireVpn)throw unavailable();
      }
      ConnectivityManager manager=routes.connectivity;
      Network active=manager.getActiveNetwork();
      LinkProperties links=active==null?null:manager.getLinkProperties(active);
      routes.refresh();NetworkPoolIdentity.NetworkSnapshot network=routes.network.snapshot();
      if(active==null||links==null||!network.usable()||!active.toString().equals(network.identity)
          ||!active.equals(manager.getActiveNetwork())||(!requested.internal&&!requested.network.equals(network.identity))
          ||(!requested.internal&&requested.proxy.isEmpty()&&requested.requireVpn&&!network.vpn)
          ||!ProfileCatalog.get(profile).identity(requested.identity.slot).equals(requested.identity))throw unavailable();
      if(!requested.internal&&requested.proxy.isEmpty()&&requested.requireVpn&&!BrowserNetworkGuard.vpnDefaultRouteIssue(profile).isEmpty())throw unavailable();
      if(!active.equals(manager.getActiveNetwork())||!links.equals(manager.getLinkProperties(active))||!sameSettings(prefs,preferences.getAll()))throw unavailable();
      if(expected!=null&&(!expected.network.equals(network)||!expected.linkFingerprint.equals(linkFingerprint(links))))throw unavailable();
      return new Stamp(proof,network,links);
    }

    private static boolean sameSettings(Map<String,?> before,Map<String,?> after){
      for(String key:new String[]{"networkMode","networkConfigured","proxy","requireExternalVpn"})
        if(!java.util.Objects.equals(before.get(key),after.get(key)))return false;
      return true;
    }

    private boolean internalUsable(){
      NativeNetwork nativeNetwork=NativeNetwork.peek();
      return nativeNetwork!=null&&Profiles.slot(nativeNetwork.context)==Profiles.slot(profile)
          &&nativeNetwork.connectionAdmission().usable();
    }

    private synchronized void ensureWatch(boolean internal)throws IOException {
      routes.watch();
      if(internal&&watchedNative==null){watchedNative=NativeNetwork.peek();if(watchedNative==null)throw unavailable();watchedNative.addRouteListener(this::nativeChanged);}
      if(watching)return;
      preferences.registerOnSharedPreferenceChangeListener(settings);
      routes.connectivity.registerDefaultNetworkCallback(new ConnectivityManager.NetworkCallback(){
        @Override public void onAvailable(Network active){for(Entry entry:holders())if(!entry.stamp.network.identity.equals(active.toString()))revoke(entry);}
        @Override public void onLost(Network active){for(Entry entry:holders())if(entry.stamp.network.identity.equals(active.toString()))revoke(entry);}
        @Override public void onCapabilitiesChanged(Network active,NetworkCapabilities caps){
          for(Entry entry:holders())if(entry.stamp.network.identity.equals(active.toString())
            &&(!caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)||entry.stamp.network.vpn!=caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN)))revoke(entry);
        }
        @Override public void onLinkPropertiesChanged(Network active,LinkProperties links){
          for(Entry entry:holders())if(entry.stamp.network.identity.equals(active.toString())&&!entry.stamp.linkFingerprint.equals(linkFingerprint(links)))revoke(entry);
        }
      });
      monitor.scheduleWithFixedDelay(this::poll,500,500,TimeUnit.MILLISECONDS);
      watching=true;
    }

    private void nativeChanged(){
      if(!internalUsable())for(Entry entry:holders())if(entry.request.internal)revoke(entry);
      wake();
    }

    private List<Entry> holders(){synchronized(entries){return new ArrayList<>(entries.values());}}
    private void wake(){if(wakePosted.compareAndSet(false,true))monitor.execute(()->{wakePosted.set(false);poll();});}
    private void poll(){for(Entry entry:holders())check(entry);}
    private void revokeAll(){for(Entry entry:holders())revoke(entry);}
    private void revoke(Entry entry){
      if(entry.released.get()||!entry.revoked.compareAndSet(false,true))return;
      Parcel data=Parcel.obtain();
      try{data.writeInterfaceToken(DESCRIPTOR);entry.client.transact(REVOKE,data,null,IBinder.FLAG_ONEWAY);}
      catch(RemoteException dead){if(!entry.client.isBinderAlive())releaseEntry(entry);}
      catch(RuntimeException denied){}
      finally{data.recycle();}
      // Keep the surface fence until the client has closed its sockets and releases,
      // or until Binder observes the entire client process exiting.
    }
    private void releaseEntry(Entry entry){
      if(!entry.released.compareAndSet(false,true))return;
      try{entry.client.unlinkToDeath(entry.death,0);}catch(RuntimeException ignored){}
      entry.handle.close();
      synchronized(entries){entries.remove(entry.token,entry);entries.notifyAll();}
    }

    boolean stopForMaintenance(long timeoutMillis){
      maintenance=true;revokeAll();long deadline=SystemClock.elapsedRealtime()+timeoutMillis;
      synchronized(entries){
        while(!entries.isEmpty()){
          long remaining=deadline-SystemClock.elapsedRealtime();if(remaining<=0)return false;
          try{entries.wait(remaining);}catch(InterruptedException stopped){Thread.currentThread().interrupt();return false;}
        }
        return true;
      }
    }

    private static String linkFingerprint(LinkProperties links){return NativeNetwork.hash(links.toString());}

    private static final class Stamp {
      final AppUpdateRoute.Lease internal;
      final NetworkPoolIdentity.NetworkSnapshot network;
      final String linkFingerprint;
      Stamp(AppUpdateRoute.Lease internal,NetworkPoolIdentity.NetworkSnapshot network,LinkProperties links){
        this.internal=internal;this.network=network;this.linkFingerprint=linkFingerprint(links);
      }
    }

    private final class Entry {
      final Request request;
      final IBinder client;
      final Stamp stamp;
      final ChromiumRouteLease.Handle handle;
      final String token=UUID.randomUUID().toString();
      final AtomicBoolean revoked=new AtomicBoolean(), released=new AtomicBoolean();
      final IBinder.DeathRecipient death=()->releaseEntry(this);
      Entry(Request request,IBinder client,Stamp stamp,ChromiumRouteLease.Handle handle){
        this.request=request;this.client=client;this.stamp=stamp;this.handle=handle;
      }
    }
  }
}
