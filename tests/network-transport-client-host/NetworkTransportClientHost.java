package local.pocketchat;

import android.content.*;import android.os.*;import java.io.*;import java.lang.reflect.*;
import java.util.*;import java.util.concurrent.*;import java.util.function.*;import org.json.*;

/** Full production Client against explicit synthetic Android API adapters. */
public final class NetworkTransportClientHost {
 static final Looper MAIN=Looper.getMainLooper();static final ComponentName NAME=new ComponentName("synthetic-service");
 static final JSONArray checks=new JSONArray(),cases=new JSONArray();static JSONObject timeoutObservation=new JSONObject();static int failures;
 static void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));if(!pass)failures++;}
 interface Work{void run()throws Exception;}
 static void runCase(String name,Work work){MAIN.reset();int before=failures;try{work.run();}catch(Throwable failure){check(name+" completed without unexpected host exception",false);cases.put(J.obj("case",name,"error",failure.toString()));}cases.put(J.obj("case",name,"failedChecks",failures-before));MAIN.reset();}
 static Object field(Object target,String name)throws Exception{Class<?> type=target.getClass();while(type!=null){try{Field f=type.getDeclaredField(name);f.setAccessible(true);return f.get(target);}catch(NoSuchFieldException ignored){type=type.getSuperclass();}}throw new NoSuchFieldException(name);}
 static ServiceConnection connection(NetworkTransportClient client)throws Exception{return (ServiceConnection)field(client,"connection");}
 static CountDownLatch gate(NetworkTransportClient client)throws Exception{return (CountDownLatch)field(client,"connected");}
 static boolean bound(NetworkTransportClient client)throws Exception{return (Boolean)field(client,"bound");}
 static void callback(Runnable task){Looper.onMain(task);}
 static boolean until(BooleanSupplier condition,boolean pump,long millis)throws Exception{long deadline=System.nanoTime()+TimeUnit.MILLISECONDS.toNanos(millis);while(!condition.getAsBoolean()){if(pump)MAIN.drain();if(System.nanoTime()>=deadline)return false;Thread.sleep(1);}return true;}
 static void waitFor(BooleanSupplier condition,boolean pump,String reason)throws Exception{if(!until(condition,pump,2000))throw new AssertionError(reason);}
 static void disconnect(ServiceConnection connection){callback(()->connection.onServiceDisconnected(NAME));}
 static void nullBinding(ServiceConnection connection){callback(()->connection.onNullBinding(NAME));}
 static void died(ServiceConnection connection){callback(()->connection.onBindingDied(NAME));}
 static void connected(ServiceConnection connection,Remote remote){callback(()->connection.onServiceConnected(NAME,remote));}
 static JSONObject state(String generation){return J.obj("slot",1,"alive",true,"state","running","generation",generation);}
 static final class Call implements AutoCloseable {
  final Thread thread;volatile JSONObject result;volatile Throwable error;volatile boolean finished;
  Call(NetworkTransportClient client,String action){thread=new Thread(()->{try{result=client.call(action,"");}catch(Throwable failure){error=failure;}finally{finished=true;}},"host-call-"+action);thread.setDaemon(true);thread.start();}
  Call(NetworkTransportClient client,boolean detach){thread=new Thread(()->{try{client.detach();}catch(Throwable failure){error=failure;}finally{finished=true;}},"host-detach");thread.setDaemon(true);thread.start();}
  void awaiting()throws Exception{waitFor(()->thread.getState()==Thread.State.TIMED_WAITING||thread.getState()==Thread.State.WAITING||finished,false,"call reached actual production wait");}
  public void close()throws Exception{if(!finished)thread.interrupt();thread.join(1000);if(thread.isAlive())throw new AssertionError("Host call thread did not stop");}
 }
 static final class HostContext extends Context {
  final List<ServiceConnection> bindings=new ArrayList<>(),unbindings=new ArrayList<>();final Set<ServiceConnection> registered=Collections.newSetFromMap(new IdentityHashMap<>());
  boolean nextAccepted=true,insideBind,failUnbindOnce;RuntimeException nextException;Consumer<ServiceConnection> duringBind;int foreground,prematureUnbinds;
  public boolean bindService(Intent intent,ServiceConnection connection,int flags){
   if(Looper.myLooper()!=MAIN)throw new AssertionError("bind must execute on simulated main");
   bindings.add(connection);boolean accepted=nextAccepted;RuntimeException failure=nextException;Consumer<ServiceConnection> hook=duringBind;
   // ContextImpl allocates LoadedApk's ServiceDispatcher before the AMS result.
   // False/SecurityException still need unbindService to forget that dispatcher.
   nextAccepted=true;nextException=null;duringBind=null;registered.add(connection);insideBind=true;
   try{if(hook!=null)hook.accept(connection);if(failure!=null)throw failure;return accepted;}finally{insideBind=false;}
  }
  public void unbindService(ServiceConnection connection){unbindings.add(connection);if(insideBind)prematureUnbinds++;if(failUnbindOnce){failUnbindOnce=false;throw new IllegalArgumentException("Synthetic dispatcher release failure");}if(!registered.remove(connection))throw new IllegalArgumentException("Host connection not registered");}
  public ComponentName startForegroundService(Intent intent){foreground++;return NAME;}
  ServiceConnection latest(){return bindings.get(bindings.size()-1);}
 }
 static final class Remote implements Messenger.Endpoint {
  final List<Message> received=Collections.synchronizedList(new ArrayList<>());boolean failSend;
  public void send(Message message)throws RemoteException{if(failSend)throw new RemoteException("Synthetic dead endpoint");received.add(message);}
  void reply(int index,JSONObject state,boolean ok)throws Exception{replyTo(received.get(index).replyTo,received.get(index).getData().getString("id"),state,ok);}
  void event(int index,JSONObject state)throws Exception{Message event=Message.obtain(null,NetworkTransportService.EVENT);Bundle data=new Bundle();data.putString("json",state.toString());event.setData(data);received.get(index).replyTo.send(event);}
 }
 static void replyTo(Messenger target,String id,JSONObject state,boolean ok)throws Exception{Message reply=Message.obtain(null,NetworkTransportService.REPLY);Bundle data=new Bundle();data.putString("id",id);data.putString("json",J.obj("ok",ok,"state",state).toString());reply.setData(data);target.send(reply);}
 static final class Fixture {
  final HostContext context=new HostContext();final List<JSONObject> changes=new ArrayList<>();final NetworkTransportClient client=new NetworkTransportClient(context,changes::add);Remote remote;
  ServiceConnection bind()throws Exception{client.bind();MAIN.drain();return context.latest();}
  ServiceConnection open()throws Exception{ServiceConnection connection=bind();remote=new Remote();connected(connection,remote);MAIN.drain();return connection;}
 }
 static void nullLifecycle()throws Exception{
  Fixture f=new Fixture();Call a=new Call(f.client,"snapshot"),b=new Call(f.client,"snapshot"),c=new Call(f.client,"snapshot");
  try{waitFor(()->!f.context.bindings.isEmpty(),true,"initial bind requested");a.awaiting();b.awaiting();c.awaiting();CountDownLatch old=gate(f.client);ServiceConnection owner=f.context.latest();nullBinding(owner);MAIN.drain();
   check("Null binding releases the captured gate",old.getCount()==0);
   check("Null binding wakes all actual bind waiters",until(()->a.finished&&b.finished&&c.finished,true,1000)&&a.error!=null&&b.error!=null&&c.error!=null);
   check("Null binding releases framework binding exactly once",f.context.unbindings.size()==1&&f.context.unbindings.get(0)==owner);
   check("Null binding retires bound state",!bound(f.client)&&f.client.service==null&&!f.client.alive());
   f.client.bind();MAIN.drain();check("Next explicit demand performs a new bind after null",f.context.bindings.size()==2);
   check("Next bind owns a fresh waiting gate",gate(f.client)!=old&&gate(f.client).getCount()==1);
   if(f.context.bindings.size()>1)check("Next bind owns a distinct ServiceConnection",f.context.latest()!=owner);else check("Next bind owns a distinct ServiceConnection",false);
  }finally{a.close();b.close();c.close();}
 }
 static void disconnectPendingBind()throws Exception{
  Fixture f=new Fixture();try(Call call=new Call(f.client,"snapshot")){waitFor(()->!f.context.bindings.isEmpty(),true,"bind queued");call.awaiting();CountDownLatch old=gate(f.client);ServiceConnection owner=f.context.latest();disconnect(owner);
   check("Disconnect releases the already captured gate",old.getCount()==0);
   check("Disconnect wakes existing bind waiter without ten second wait",until(()->call.finished,true,1000)&&call.error!=null);
   check("Disconnect keeps accepted binding for Android reconnection",bound(f.client)&&f.context.unbindings.isEmpty());
   CountDownLatch next=gate(f.client);f.client.bind();MAIN.drain();check("Disconnected binding does not explicitly bind again",f.context.bindings.size()==1&&gate(f.client)==next&&next!=old&&next.getCount()==1);
   Remote remote=new Remote();connected(owner,remote);check("Same connection can finish a new system reconnection gate",gate(f.client)==next&&next.getCount()==0&&f.client.service!=null);
  }
 }
 static void bindingDied()throws Exception{
  Fixture f=new Fixture();try(Call call=new Call(f.client,"snapshot")){waitFor(()->!f.context.bindings.isEmpty(),true,"bind queued");call.awaiting();CountDownLatch old=gate(f.client);ServiceConnection owner=f.context.latest();died(owner);MAIN.drain();
   check("Binding death releases captured gate",old.getCount()==0);
   check("Binding death completes actual old bind waiter",until(()->call.finished,true,1000)&&call.error!=null);
   check("Binding death retires and unbinds once",!bound(f.client)&&f.context.unbindings.size()==1&&f.client.service==null);
   died(owner);nullBinding(owner);MAIN.drain();check("Repeated terminal callbacks do not repeat unbind",f.context.unbindings.size()==1);
   f.client.bind();MAIN.drain();check("Demand after binding death creates new binding and pending gate",f.context.bindings.size()==2&&gate(f.client).getCount()==1);
  }
 }
 static void staleCallbacks()throws Exception{
  Fixture f=new Fixture();ServiceConnection old=f.open();died(old);MAIN.drain();ServiceConnection active=f.bind();Remote remote=new Remote();connected(active,remote);f.client.publish(state("current"));Object target=f.client.service;CountDownLatch currentGate=gate(f.client);int changes=f.changes.size(),unbinds=f.context.unbindings.size();
  connected(old,new Remote());check("Retired onServiceConnected cannot replace new target",f.client.service==target);
  disconnect(old);check("Retired disconnect cannot clear new target or gate",f.client.service==target&&gate(f.client)==currentGate);
  nullBinding(old);died(old);MAIN.drain();check("Retired null/death callbacks do not retire current binding",bound(f.client)&&f.client.service==target&&gate(f.client)==currentGate);
  check("Retired callbacks do not publish failures or repeat old unbind",f.changes.size()==changes&&f.context.unbindings.size()==unbinds&&f.client.state.optString("generation").equals("current"));
 }
 static void pendingRequestsAndReplies()throws Exception{
  Fixture f=new Fixture();ServiceConnection owner=f.open();Remote old=f.remote;
  try(Call a=new Call(f.client,"snapshot");Call b=new Call(f.client,"snapshot")){
   waitFor(()->old.received.size()==2,true,"two actual IPC commands sent");disconnect(owner);MAIN.drain();
   check("Disconnect fails all actual in-flight request futures",until(()->a.finished&&b.finished,true,1000)&&a.error!=null&&b.error!=null&&f.client.requests.isEmpty());
   Remote next=new Remote();connected(owner,next);
   try(Call fresh=new Call(f.client,"snapshot")){waitFor(()->next.received.size()==1,true,"fresh reconnect command");
    old.event(0,state("stale-event"));MAIN.drain();check("Old reply endpoint cannot publish stale pushed state",!f.client.state.optString("generation").equals("stale-event"));
    replyTo(old.received.get(0).replyTo,next.received.get(0).getData().getString("id"),state("stale-reply"),true);MAIN.drain();
    check("Old reply endpoint cannot complete a new epoch request",!fresh.finished&&f.client.requests.size()==1&&!f.client.state.optString("generation").equals("stale-reply"));
    next.reply(0,state("new-epoch"),true);check("Current epoch reply completes its own request",until(()->fresh.finished,true,1000)&&fresh.error==null&&fresh.result!=null&&fresh.result.optString("generation").equals("new-epoch"));
    check("Completed request leaves no pending future",f.client.requests.isEmpty());
   }
  }
 }
 static void terminalPendingRequests()throws Exception{
  for(boolean nullCallback:new boolean[]{true,false}){
   String kind=nullCallback?"Null binding":"Binding death";Fixture f=new Fixture();ServiceConnection owner=f.open();Remote old=f.remote;
   try(Call a=new Call(f.client,"snapshot");Call b=new Call(f.client,"snapshot")){
    waitFor(()->old.received.size()==2,true,"two terminal-owner IPC commands sent");if(nullCallback)nullBinding(owner);else died(owner);MAIN.drain();
    check(kind+" fails all actual pending request futures",until(()->a.finished&&b.finished,true,1000)&&a.error!=null&&b.error!=null&&f.client.requests.isEmpty());
    check(kind+" clears endpoint and accepted binding",f.client.service==null&&!bound(f.client)&&f.context.unbindings.size()==1);
    f.client.bind();MAIN.drain();ServiceConnection fresh=f.context.latest();Remote current=new Remote();connected(fresh,current);f.client.publish(state("terminal-current"));
    old.event(0,state("terminal-old"));old.reply(0,state("terminal-old-reply"),true);MAIN.drain();
    check(kind+" old pushed event and reply cannot publish after rebind",f.client.state.optString("generation").equals("terminal-current"));
   }
  }
 }
 static void rejectedAndExceptionalBinds()throws Exception{
  for(boolean throwing:new boolean[]{false,true}){Fixture f=new Fixture();if(throwing)f.context.nextException=new IllegalStateException("synthetic bind failure");else f.context.nextAccepted=false;
   f.client.bind();CountDownLatch old=gate(f.client);MAIN.drain();check((throwing?"Exception":"False return")+" retires old binding, releases original gate and forgets dispatcher once",!bound(f.client)&&old.getCount()==0&&f.client.service==null&&f.context.unbindings.size()==1&&f.context.registered.isEmpty());
   ServiceConnection retired=f.context.latest();connected(retired,new Remote());check((throwing?"Exception":"False return")+" ignores late onServiceConnected",f.client.service==null&&!bound(f.client));
   f.client.bind();MAIN.drain();check((throwing?"Exception":"False return")+" allows fresh pending gate on next demand",f.context.bindings.size()==2&&gate(f.client)!=old&&gate(f.client).getCount()==1);
  }
 }
 static void synchronousCallbacks()throws Exception{
  Fixture f=new Fixture();final boolean[] withheld={false};f.context.duringBind=owner->{connected(owner,new Remote());try{withheld[0]=f.client.service==null&&gate(f.client).getCount()==1;}catch(Exception e){throw new IllegalStateException(e);}};
  f.bind();check("Synchronous connected callback does not expose unaccepted binder",withheld[0]);check("Accepted synchronous connected callback activates only after true return",f.client.service!=null&&gate(f.client).getCount()==0&&bound(f.client));
  Fixture nullCase=new Fixture();nullCase.context.duringBind=NetworkTransportClientHost::nullBinding;ServiceConnection owner=nullCase.bind();
  check("Synchronous null followed by true is retired and unbound once",!bound(nullCase.client)&&nullCase.client.service==null&&nullCase.context.unbindings.size()==1&&nullCase.context.unbindings.get(0)==owner);
  check("Synchronous null cleanup waits for bindService to return",nullCase.context.prematureUnbinds==0&&nullCase.context.registered.isEmpty());
  Fixture diedCase=new Fixture();diedCase.context.duringBind=NetworkTransportClientHost::died;ServiceConnection dead=diedCase.bind();
  check("Synchronous death followed by true is retired and unbound once",!bound(diedCase.client)&&diedCase.client.service==null&&diedCase.context.unbindings.size()==1&&diedCase.context.unbindings.get(0)==dead&&diedCase.context.registered.isEmpty());
  check("Synchronous death cleanup waits for bindService to return",diedCase.context.prematureUnbinds==0);
  for(boolean throwing:new boolean[]{false,true}){Fixture rejected=new Fixture();final CountDownLatch[] captured={null};rejected.context.duringBind=c->{try{captured[0]=gate(rejected.client);}catch(Exception error){throw new IllegalStateException(error);}connected(c,new Remote());};if(throwing)rejected.context.nextException=new IllegalStateException("after synchronous callback");else rejected.context.nextAccepted=false;rejected.bind();
   check((throwing?"Thrown":"Rejected")+" bind cannot activate synchronous connected callback and releases dispatcher",!bound(rejected.client)&&rejected.client.service==null&&captured[0].getCount()==0&&rejected.context.unbindings.size()==1&&rejected.context.registered.isEmpty());
  }
  for(boolean nullCallback:new boolean[]{true,false})for(boolean throwing:new boolean[]{false,true}){
   Fixture terminal=new Fixture();final CountDownLatch[] captured={null};terminal.context.duringBind=c->{try{captured[0]=gate(terminal.client);}catch(Exception error){throw new IllegalStateException(error);}if(nullCallback)nullBinding(c);else died(c);};
   if(throwing)terminal.context.nextException=new IllegalStateException("synchronous terminal then throw");else terminal.context.nextAccepted=false;ServiceConnection retired=terminal.bind();
   check("Synchronous "+(nullCallback?"null":"death")+" with "+(throwing?"exception":"false return")+" releases waiter and dispatcher once",captured[0].getCount()==0&&!bound(terminal.client)&&terminal.client.service==null&&terminal.context.unbindings.size()==1&&terminal.context.registered.isEmpty());
   check("Synchronous "+(nullCallback?"null":"death")+" with "+(throwing?"exception":"false return")+" defers dispatcher release until bindService finishes",terminal.context.prematureUnbinds==0);
   connected(retired,new Remote());check("Late connect after synchronous "+(nullCallback?"null":"death")+" and "+(throwing?"exception":"false return")+" stays retired",!bound(terminal.client)&&terminal.client.service==null);
  }
 }
 static void failedAttemptDispatchers()throws Exception{
  for(boolean security:new boolean[]{false,true}){
   Fixture f=new Fixture();for(int i=0;i<20;i++){if(security)f.context.nextException=new SecurityException("Synthetic AMS bind denial");else f.context.nextAccepted=false;f.client.bind();MAIN.drain();}
   String kind=security?"SecurityException":"False return";
   check(kind+" twenty explicit attempts all execute without automatic retry",f.context.bindings.size()==20);
   check(kind+" twenty failed attempts each release their own dispatcher once",f.context.unbindings.size()==20&&new HashSet<>(f.context.unbindings).size()==20);
   check(kind+" repeated failed attempts leave no retained framework dispatcher",f.context.registered.isEmpty()&&!bound(f.client)&&f.client.service==null);
  }
 }
 static void unattemptedQueuedOwner()throws Exception{
  Fixture f=new Fixture();f.client.bind();ServiceConnection skipped=connection(f.client);nullBinding(skipped);f.client.bind();MAIN.drain();ServiceConnection active=f.context.latest();
  check("Retired queued generation never executes its bindService call",f.context.bindings.size()==1&&active!=skipped);
  check("A queued generation never actually attempted is not unbound",f.context.unbindings.isEmpty()&&f.context.registered.size()==1&&f.context.registered.contains(active));
  Remote remote=new Remote();connected(active,remote);died(active);MAIN.drain();
  check("Only the actually attempted replacement dispatcher is released",f.context.unbindings.size()==1&&f.context.unbindings.get(0)==active&&f.context.registered.isEmpty());
 }
 static void failedUnbindIsBounded()throws Exception{
  Fixture f=new Fixture();ServiceConnection old=f.open();f.context.failUnbindOnce=true;nullBinding(old);MAIN.drain();died(old);nullBinding(old);MAIN.drain();
  check("An unbind exception still permits only one cleanup attempt",f.context.unbindings.size()==1&&!bound(f.client)&&f.client.service==null);
  ServiceConnection active=f.bind();Remote remote=new Remote();connected(active,remote);died(old);nullBinding(old);MAIN.drain();
  check("A prior cleanup exception cannot unbind the replacement owner",f.context.unbindings.size()==1&&f.context.bindings.size()==2&&f.context.registered.contains(active)&&bound(f.client)&&f.client.service!=null);
 }
 static void detachFencing()throws Exception{
  Fixture f=new Fixture();ServiceConnection old=f.open();try(Call detach=new Call(f.client,true)){
   waitFor(()->f.remote.received.size()==1,false,"detach command sent");f.remote.reply(0,state("detach-response"),true);if(!MAIN.runOne())throw new AssertionError("detach reply queued");
   waitFor(()->MAIN.pending()>0||detach.finished,false,"detach cleanup posted");Runnable delayed=MAIN.take();if(delayed==null)throw new AssertionError("no deferred detach cleanup");
   died(old);MAIN.drain();ServiceConnection active=f.bind();Remote remote=new Remote();connected(active,remote);Object target=f.client.service;CountDownLatch current=gate(f.client);int unbinds=f.context.unbindings.size();Looper.onMain(delayed);MAIN.drain();
   check("Late detach cleanup completes its own caller",until(()->detach.finished,true,1000)&&detach.error==null);
   check("Late detach cleanup leaves new binding and endpoint intact",bound(f.client)&&f.client.service==target&&gate(f.client)==current);
   check("Late detach cleanup does not unbind a new registered connection",f.context.registered.contains(active)&&f.context.unbindings.size()==unbinds);
  }
 }
 static void normalCallAndErrors()throws Exception{
  Fixture f=new Fixture();f.open();try(Call call=new Call(f.client,"launch")){waitFor(()->f.remote.received.size()==1,true,"launch IPC sent");Message sent=f.remote.received.get(0);
   check("Normal launch starts existing foreground service once",f.context.foreground==1);
   check("Normal command retains slot action generation reason and expected generation fields",sent.what==NetworkTransportService.COMMAND&&sent.replyTo!=null&&sent.getData().getInt("slot",-1)==1&&sent.getData().getString("action").equals("launch")&&sent.getData().getString("stopReason").equals("UNKNOWN")&&sent.getData().getString("expectedGeneration").equals(""));
   f.remote.reply(0,state("normal"),true);check("Normal correlated reply completes and publishes",until(()->call.finished,true,1000)&&call.error==null&&f.client.alive()&&f.client.state.optString("generation").equals("normal"));
  }
  try(Call observed=new Call(f.client,"snapshot")){waitFor(()->f.remote.received.size()==2,true,"slot-fence observation command");int changes=f.changes.size();f.remote.event(1,J.obj("slot",2,"alive",true,"generation","foreign-slot"));MAIN.drain();check("Pushed state from another slot remains rejected",f.changes.size()==changes&&f.client.state.optString("generation").equals("normal"));f.remote.reply(1,state("own-slot"),true);check("Correct own-slot reply still completes after ignored foreign event",until(()->observed.finished,true,1000)&&observed.error==null&&observed.result.optString("generation").equals("own-slot"));}
  try(Call rejected=new Call(f.client,"snapshot")){waitFor(()->f.remote.received.size()==3,true,"rejected command sent");f.remote.reply(2,state("rejected"),false);check("Remote rejection remains an error and cleans pending request",until(()->rejected.finished,true,1000)&&rejected.error instanceof IOException&&f.client.requests.isEmpty());}
  f.remote.failSend=true;try(Call failed=new Call(f.client,"snapshot")){check("Send failure remains an error with no leaked future",until(()->failed.finished,true,1000)&&failed.error instanceof RemoteException&&f.client.requests.isEmpty());}
  final Throwable[] mainError={null};callback(()->{try{f.client.call("snapshot","");}catch(Throwable error){mainError[0]=error;}});check("Main thread call rejection remains enforced",mainError[0] instanceof IOException);
 }
 static void interruptions()throws Exception{
  Fixture waiting=new Fixture();try(Call call=new Call(waiting.client,"snapshot")){waitFor(()->!waiting.context.bindings.isEmpty(),true,"initial bind requested");call.awaiting();call.thread.interrupt();check("Interrupted binding waiter remains interrupted failure",until(()->call.finished,true,1000)&&call.error instanceof InterruptedException);check("Bind interruption does not add automatic retry",waiting.context.bindings.size()==1);}
  Fixture connected=new Fixture();connected.open();try(Call call=new Call(connected.client,"snapshot")){waitFor(()->connected.remote.received.size()==1,true,"reply wait reached");call.thread.interrupt();check("Interrupted reply waiter removes only its own pending request",until(()->call.finished,true,1000)&&call.error instanceof InterruptedException&&connected.client.requests.isEmpty());check("Reply interruption preserves accepted service binding",bound(connected.client)&&connected.context.unbindings.isEmpty()&&connected.client.service!=null);}
 }
 static void replyTimeoutAndDuplicate()throws Exception{
  Fixture f=new Fixture();f.open();f.client.publish(state("before-timeout"));long started=System.nanoTime();
  try(Call expired=new Call(f.client,"snapshot")){
   waitFor(()->f.remote.received.size()==1,true,"unanswered production command sent");
   boolean completed=until(()->expired.finished,true,17000);long elapsed=System.nanoTime()-started;
   timeoutObservation=J.obj("configuredTimeoutSeconds",15,"observedElapsedNanos",elapsed,
     "exceptionClass",expired.error==null?"":expired.error.getClass().getName(),
     "requestId",f.remote.received.get(0).getData().getString("id"));
   check("Actual unanswered request uses original real fifteen second reply timeout",completed&&expired.error instanceof TimeoutException&&elapsed>=14900000000L);
   check("Reply timeout removes its pending future",f.client.requests.isEmpty());
   check("Reply timeout preserves accepted binding and endpoint",bound(f.client)&&f.client.service!=null);
   check("Reply timeout does not bind or unbind automatically",f.context.bindings.size()==1&&f.context.unbindings.isEmpty());
   try(Call fresh=new Call(f.client,"snapshot")){
    waitFor(()->f.remote.received.size()==2,true,"new request after timeout sent");
    check("Fresh request after timeout has distinct correlation and pending future",!fresh.finished&&f.client.requests.size()==1&&!f.remote.received.get(0).getData().getString("id").equals(f.remote.received.get(1).getData().getString("id")));
    int before=f.changes.size();f.remote.reply(0,state("late-expired"),true);MAIN.drain();
    check("Late expired reply neither publishes nor completes a fresh request",!fresh.finished&&f.client.requests.size()==1&&f.changes.size()==before&&f.client.state.optString("generation").equals("before-timeout"));
    f.remote.reply(1,state("current-once"),true);check("Current reply after timeout completes its own request",until(()->fresh.finished,true,1000)&&fresh.error==null&&fresh.result.optString("generation").equals("current-once"));
    int after=f.changes.size();f.remote.reply(1,state("duplicate-current"),true);MAIN.drain();
    check("Duplicate completed reply cannot publish or complete again",f.changes.size()==after&&f.client.state.optString("generation").equals("current-once")&&fresh.result.optString("generation").equals("current-once")&&f.client.requests.isEmpty());
   }
  }
 }
 public static void main(String[]args){
  runCase("null lifecycle",NetworkTransportClientHost::nullLifecycle);runCase("disconnect during bind wait",NetworkTransportClientHost::disconnectPendingBind);runCase("binding death",NetworkTransportClientHost::bindingDied);runCase("stale callbacks",NetworkTransportClientHost::staleCallbacks);runCase("pending requests and reply epochs",NetworkTransportClientHost::pendingRequestsAndReplies);runCase("terminal pending requests",NetworkTransportClientHost::terminalPendingRequests);runCase("false and exceptional binds",NetworkTransportClientHost::rejectedAndExceptionalBinds);runCase("synchronous callbacks",NetworkTransportClientHost::synchronousCallbacks);runCase("detach fencing",NetworkTransportClientHost::detachFencing);runCase("normal call and errors",NetworkTransportClientHost::normalCallAndErrors);runCase("interruptions",NetworkTransportClientHost::interruptions);
  runCase("real reply timeout and duplicate completion",NetworkTransportClientHost::replyTimeoutAndDuplicate);
  runCase("failed attempt dispatcher cleanup",NetworkTransportClientHost::failedAttemptDispatchers);runCase("unattempted queued owner",NetworkTransportClientHost::unattemptedQueuedOwner);runCase("failed unbind is bounded",NetworkTransportClientHost::failedUnbindIsBounded);
  System.out.println(J.obj("status",failures==0?"passed":"failed","checkCount",checks.length(),"failedCount",failures,"checks",checks,"cases",cases,"replyTimeoutObservation",timeoutObservation,"actualAndroidExecution",false,"actualBinderExecution",false,"actualServiceExecution",false));if(failures!=0)System.exit(1);
 }
}
