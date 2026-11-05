package local.pocketchat;

import android.content.Context;
import android.net.ConnectivityManager;
import android.net.LinkProperties;
import android.net.Network;
import android.net.NetworkCapabilities;

/** Observed default-network/DNS identity; readers perform no service or file I/O. */
final class GeckoIpRouteWatch implements AutoCloseable {
  static final class Snapshot {
    final String network,links;final long serial;
    Snapshot(String network,String links,long serial){this.network=network;this.links=links;this.serial=serial;}
    boolean ready(String expected){return !network.isEmpty()&&!links.isEmpty()&&network.equals(expected);}
  }
  private final Runnable changed;private ConnectivityManager manager;private volatile boolean closed;
  private volatile Snapshot state=new Snapshot("","",0);
  private final ConnectivityManager.NetworkCallback callback=new ConnectivityManager.NetworkCallback(){
    @Override public void onAvailable(Network value){update(value.toString(),"");}
    @Override public void onLinkPropertiesChanged(Network value,LinkProperties links){updateLinks(value.toString(),NativeNetwork.hash(links.toString()));}
    @Override public void onCapabilitiesChanged(Network value,NetworkCapabilities capabilities){if(!closed)changed.run();}
    @Override public void onLost(Network value){if(state.network.equals(value.toString()))update("","");}
  };
  GeckoIpRouteWatch(Context context,Runnable changed){
    this.changed=changed;
    try{manager=(ConnectivityManager)context.getSystemService(Context.CONNECTIVITY_SERVICE);if(manager!=null)manager.registerDefaultNetworkCallback(callback);}catch(RuntimeException unavailable){manager=null;}
  }
  private void update(String network,String links){
    synchronized(this){if(closed)return;Snapshot before=state;if(before.network.equals(network)&&before.links.equals(links))return;state=new Snapshot(network,links,before.serial+1);}changed.run();
  }
  private void updateLinks(String network,String links){
    synchronized(this){if(closed||!state.network.equals(network)||state.links.equals(links))return;state=new Snapshot(network,links,state.serial+1);}changed.run();
  }
  Snapshot snapshot(){return state;}
  @Override public void close(){closed=true;if(manager!=null)try{manager.unregisterNetworkCallback(callback);}catch(RuntimeException alreadyClosed){}manager=null;}
}
