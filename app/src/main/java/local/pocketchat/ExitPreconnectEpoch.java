package local.pocketchat;

import android.content.Context;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.UUID;

/** Private, opaque default-network generation for unused fixed-exit sockets. */
final class ExitPreconnectEpoch implements AutoCloseable {
  static final String FILE="preconnect-network-epoch";
  interface Changed { void run(); }
  final ConnectivityManager manager;
  final Context context;
  final NetworkPoolIdentity.DefaultNetwork network=new NetworkPoolIdentity.DefaultNetwork();
  final Changed changed;
  NetworkPoolIdentity.NetworkSnapshot previous;
  String value="blocked:"+UUID.randomUUID();
  boolean closed;
  final ConnectivityManager.NetworkCallback callback=new ConnectivityManager.NetworkCallback(){
    @Override public void onAvailable(Network n){update(()->network.available(n.toString()));}
    @Override public void onLost(Network n){update(()->network.lost(n.toString()));}
    @Override public void onCapabilitiesChanged(Network n,NetworkCapabilities c){update(()->network.capabilities(n.toString(),c.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET),c.hasTransport(NetworkCapabilities.TRANSPORT_VPN)));}
  };
  ExitPreconnectEpoch(Context c,Changed changed){
    this.context=c;this.changed=changed;manager=(ConnectivityManager)c.getSystemService(Context.CONNECTIVITY_SERVICE);
    try{
      Network n=manager.getActiveNetwork();NetworkCapabilities caps=n==null?null:manager.getNetworkCapabilities(n);
      if(caps!=null)network.initial(n.toString(),caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET),caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN));
      previous=network.snapshot();value=(previous.usable()?"ready:":"blocked:")+UUID.randomUUID();
      manager.registerDefaultNetworkCallback(callback);
    }catch(Exception unavailable){network.unknown();previous=network.snapshot();value="blocked:"+UUID.randomUUID();}
  }
  synchronized void update(Runnable event){
    if(closed)return;event.run();NetworkPoolIdentity.NetworkSnapshot current=network.snapshot();
    if(current.equals(previous))return;previous=current;value=(current.usable()?"ready:":"blocked:")+UUID.randomUUID();changed.run();
  }
  synchronized void write(File directory)throws IOException{
    if(!directory.isDirectory()&&!directory.mkdirs())throw new IOException("Cannot prepare private network epoch");
    writeExisting(directory);
  }
  synchronized void writeExisting(File directory)throws IOException{
    // Creating the temporary file in an existing directory never recreates a
    // removed environment when a network callback races with deletion.
    Path temporary=Files.createTempFile(directory.toPath(),"preconnect-",".tmp");
    try{
      String output=value;
      if(output.startsWith("ready:")&&!ResourcePressureController.automaticWarmup(ResourcePressureController.read(context),android.os.SystemClock.elapsedRealtime()))output="blocked:pressure:"+output.substring(6);
      try(FileOutputStream stream=new FileOutputStream(temporary.toFile())){stream.write(output.getBytes(StandardCharsets.US_ASCII));stream.getFD().sync();}
      Files.move(temporary,new File(directory,FILE).toPath(),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
    }finally{Files.deleteIfExists(temporary);}
  }
  @Override public synchronized void close(){
    if(closed)return;closed=true;value="blocked:"+UUID.randomUUID();
    try{manager.unregisterNetworkCallback(callback);}catch(Exception ignored){}changed.run();
  }
}
