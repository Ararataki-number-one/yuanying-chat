package local.pocketchat;

import java.io.InterruptedIOException;
import java.net.HttpURLConnection;
import java.util.*;
import java.util.concurrent.*;

/** Cancellable maintenance, with socket cancellation kept off the UI thread. */
final class NetworkWork {
  final Set<HttpURLConnection> connections=new HashSet<>();
  final Set<Future<?>> futures=new HashSet<>();
  volatile boolean cancelled;boolean active=true;Thread owner=Thread.currentThread();
  synchronized void check()throws InterruptedIOException{if(cancelled)throw new InterruptedIOException("测速已让位于连接恢复");}
  synchronized void add(HttpURLConnection c)throws InterruptedIOException{check();connections.add(c);}
  synchronized void remove(HttpURLConnection c){connections.remove(c);}
  synchronized void add(Future<?> f){if(cancelled)f.cancel(true);else futures.add(f);}
  void cancel(Executor closer){List<HttpURLConnection> sockets;List<Future<?>> tasks;
    synchronized(this){if(!active||cancelled)return;cancelled=true;sockets=new ArrayList<>(connections);tasks=new ArrayList<>(futures);if(owner!=null)owner.interrupt();}
    for(Future<?> f:tasks)f.cancel(true);
    for(HttpURLConnection c:sockets)closer.execute(()->{try{c.disconnect();}catch(Exception ignored){}});
  }
  synchronized void finish(){active=false;owner=null;futures.clear();connections.clear();}
}
