package local.pocketchat;

import java.util.*;
import java.util.function.Consumer;

/** Requests belong to one exact connection, not merely to its browser window. */
final class BrowserBridgeRequests {
  interface Timer {
    void schedule(Runnable task, long delay);
    void cancel(Runnable task);
  }
  private static final class Request {
    final Object connection;
    final Consumer<String> callback;
    Runnable timeout;
    Request(Object connection, Consumer<String> callback) {
      this.connection=connection;this.callback=callback;
    }
  }
  private final Timer timer;
  private final String unavailable;
  private final Map<Integer,Request> pending=new LinkedHashMap<>();
  private int sequence;

  BrowserBridgeRequests(Timer timer,String unavailable) {
    this.timer=timer;this.unavailable=unavailable;
  }
  int add(Object connection,Consumer<String> callback,long timeout) {
    int id=++sequence;
    if(callback==null)return id;
    Request request=new Request(connection,callback);
    request.timeout=()->complete(connection,id,unavailable);
    pending.put(id,request);timer.schedule(request.timeout,timeout);
    return id;
  }
  boolean complete(Object connection,int id,String value) {
    Request request=pending.get(id);
    if(request==null||request.connection!=connection)return false;
    pending.remove(id);timer.cancel(request.timeout);request.callback.accept(value);
    return true;
  }
  void cancel(Object connection) {
    for(Map.Entry<Integer,Request> entry:new ArrayList<>(pending.entrySet()))
      if(entry.getValue().connection==connection)complete(connection,entry.getKey(),unavailable);
  }
  void clear() {
    for(Map.Entry<Integer,Request> entry:new ArrayList<>(pending.entrySet()))
      complete(entry.getValue().connection,entry.getKey(),unavailable);
  }
  int size(){return pending.size();}
}
