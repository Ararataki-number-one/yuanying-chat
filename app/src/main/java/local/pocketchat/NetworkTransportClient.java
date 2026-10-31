package local.pocketchat;

import android.content.*;
import android.os.*;
import org.json.*;
import java.io.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.Consumer;

/** Private, correlated command replies and pushed process state. No browser objects cross IPC. */
final class NetworkTransportClient {
  final Context context;final int slot;final Consumer<JSONObject> changed;final Handler main=new Handler(Looper.getMainLooper());
  final NetworkDiagnostics diagnostics;
  volatile Messenger service;volatile JSONObject state=new JSONObject();volatile CountDownLatch connected=new CountDownLatch(1);boolean bound;
  final Map<String,Pending> requests=new ConcurrentHashMap<>();Binding connection;
  final class Epoch {
    final Binding binding;final CountDownLatch gate=new CountDownLatch(1);final Messenger replies;
    Messenger target;
    Epoch(Binding binding){this.binding=binding;replies=new Messenger(new Handler(Looper.getMainLooper()){public void handleMessage(Message message){receive(Epoch.this,message);}});}
  }
  final class Binding implements ServiceConnection {
    Epoch epoch=new Epoch(this);boolean attempted,finished,accepted,retired,unbindPosted,unbound;
    boolean current(){return connection==this&&bound&&!retired;}
    public void onServiceConnected(ComponentName name,IBinder binder){synchronized(NetworkTransportClient.this){
      if(!current()||epoch.target!=null)return;
      note(NetworkDiagnostics.Event.IPC_CONNECTED,NetworkDiagnostics.Stage.BIND,0);epoch.target=new Messenger(binder);
      // A synchronous Context adapter may callback before bindService returns.
      // A failed bind must never make its cached callback usable by a caller.
      if(finished&&accepted){service=epoch.target;epoch.gate.countDown();}
    }}
    public void onServiceDisconnected(ComponentName name){synchronized(NetworkTransportClient.this){
      if(!current())return;note(NetworkDiagnostics.Event.IPC_DISCONNECTED,NetworkDiagnostics.Stage.IPC,requests.size());
      Epoch previous=epoch;epoch=new Epoch(this);service=null;connected=epoch.gate;previous.gate.countDown();lost(previous);
      // Android owns reconnecting a disconnected binding; do not bind it again.
    }}
    public void onBindingDied(ComponentName name){synchronized(NetworkTransportClient.this){
      if(!current())return;note(NetworkDiagnostics.Event.IPC_BINDING_DIED,NetworkDiagnostics.Stage.BIND,requests.size());retire(this,true);
    }}
    public void onNullBinding(ComponentName name){synchronized(NetworkTransportClient.this){
      if(!current())return;note(NetworkDiagnostics.Event.IPC_NULL_BINDING,NetworkDiagnostics.Stage.BIND,requests.size());retire(this,true);
    }}
  }
  static final class Pending {
    final Epoch epoch;final CompletableFuture<JSONObject> result=new CompletableFuture<>();
    Pending(Epoch epoch){this.epoch=epoch;}
  }
  final class Reply {
    final Binding binding;final JSONObject state;
    Reply(Binding binding,JSONObject state){this.binding=binding;this.state=state;}
  }
  NetworkTransportClient(Context c,Consumer<JSONObject> changed){context=c.getApplicationContext();slot=Profiles.slot(c);this.changed=changed;diagnostics=NetworkDiagnosticStore.forContext(c,NetworkDiagnostics.Source.CONTROL);}
  void note(NetworkDiagnostics.Event event,NetworkDiagnostics.Stage stage,long value){diagnostics.record(event,state.optString("generation",NetworkDiagnostics.UNKNOWN),event==NetworkDiagnostics.Event.IPC_CONNECTED||event==NetworkDiagnostics.Event.IPC_DETACH?NetworkDiagnostics.Reason.UNKNOWN:event==NetworkDiagnostics.Event.IPC_BIND_INTERRUPTED||event==NetworkDiagnostics.Event.IPC_REPLY_INTERRUPTED?NetworkDiagnostics.Reason.CANCELLED:NetworkDiagnostics.Reason.CONTROL_UNAVAILABLE,stage,value);}
  void publish(JSONObject value){if(value.optInt("slot",slot)!=slot)return;state=value;changed.accept(value);}
  void failRequests(Epoch epoch){for(Map.Entry<String,Pending> entry:requests.entrySet()){Pending pending=entry.getValue();if(pending.epoch==epoch&&requests.remove(entry.getKey(),pending))pending.result.completeExceptionally(new IOException("网络服务暂时退出"));}}
  void lost(Epoch epoch){failRequests(epoch);publish(J.obj("slot",slot,"alive",false,"state","failed"));}
  void receive(Epoch epoch,Message message){synchronized(this){
    if(!epoch.binding.current()||epoch.binding.epoch!=epoch||epoch.target==null||service!=epoch.target)return;
    JSONObject result=J.parse(message.getData().getString("json","{}"));
    if(message.what==NetworkTransportService.EVENT)publish(result);
    else if(message.what==NetworkTransportService.REPLY){String id=message.getData().getString("id");Pending pending=requests.get(id);
      if(pending!=null&&pending.epoch==epoch&&requests.remove(id,pending)){JSONObject snapshot=result.optJSONObject("state");if(snapshot!=null)publish(snapshot);pending.result.complete(result);}
    }
  }}
  void retire(Binding binding,boolean announce){
    if(!binding.current())return;binding.retired=true;bound=false;connection=null;service=null;connected=new CountDownLatch(1);
    binding.epoch.gate.countDown();failRequests(binding.epoch);scheduleUnbind(binding);
    if(announce)publish(J.obj("slot",slot,"alive",false,"state","failed"));
  }
  void scheduleUnbind(Binding binding){
    if(!binding.finished||!binding.attempted||!binding.retired||binding.unbindPosted)return;
    binding.unbindPosted=true;main.post(()->unbind(binding));
  }
  void unbind(Binding binding){
    synchronized(this){if(!binding.finished||!binding.attempted||!binding.retired||binding.unbound)return;binding.unbound=true;}
    try{context.unbindService(binding);}catch(Exception ignored){}
  }
  synchronized Binding bind(){
    if(bound)return connection;Binding binding=new Binding();connection=binding;bound=true;service=null;connected=binding.epoch.gate;
    main.post(()->{
      synchronized(NetworkTransportClient.this){if(!binding.current())return;}
      boolean accepted=false;
      try{Intent intent=new Intent(context,NetworkTransportService.class);
        synchronized(NetworkTransportClient.this){if(!binding.current())return;binding.attempted=true;}
        accepted=context.bindService(intent,binding,Context.BIND_AUTO_CREATE);if(!accepted)note(NetworkDiagnostics.Event.IPC_BIND_REJECTED,NetworkDiagnostics.Stage.BIND,0);}
      catch(Exception failed){note(NetworkDiagnostics.Event.IPC_BIND_EXCEPTION,NetworkDiagnostics.Stage.BIND,0);}
      synchronized(NetworkTransportClient.this){
        binding.finished=true;binding.accepted=accepted;
        if(!accepted&&binding.current())retire(binding,false);
        // Context retains a ServiceDispatcher even for false/SecurityException.
        // A synchronous terminal callback may already have retired this owner.
        if(binding.retired)scheduleUnbind(binding);
        else if(accepted&&binding.current()&&binding.epoch.target!=null){service=binding.epoch.target;binding.epoch.gate.countDown();}
      }
    });return binding;
  }
  JSONObject call(String action,String configuration)throws Exception{
    return call(action,configuration,NetworkDiagnostics.Reason.UNKNOWN);
  }
  JSONObject call(String action,String configuration,NetworkDiagnostics.Reason stopReason)throws Exception{
    return call(action,configuration,stopReason,"");
  }
  JSONObject call(String action,String configuration,NetworkDiagnostics.Reason stopReason,String expectedGeneration)throws Exception{
    return performCall(action,configuration,stopReason,expectedGeneration).state;
  }
  JSONObject callBound(String action,String configuration,NetworkDiagnostics.Reason reason,String expectedGeneration,EnvironmentSpec.Identity expectedOwner)throws Exception{
    if(expectedOwner==null||expectedOwner.slot!=slot)throw new IOException("网络环境身份不匹配");return performCall(action,configuration,reason,expectedGeneration,true,expectedOwner).state;
  }
  Reply performCall(String action,String configuration,NetworkDiagnostics.Reason stopReason,String expectedGeneration)throws Exception{return performCall(action,configuration,stopReason,expectedGeneration,false,null);}
  Reply performCall(String action,String configuration,NetworkDiagnostics.Reason stopReason,String expectedGeneration,boolean guardGeneration,EnvironmentSpec.Identity expectedOwner)throws Exception{

    if(Looper.myLooper()==Looper.getMainLooper())throw new IOException("网络服务操作需要后台线程");NetworkDiagnosticStore.bind(diagnostics,context);Binding binding=bind();Epoch epoch;
    synchronized(this){epoch=binding.epoch;}CountDownLatch gate=epoch.gate;boolean connectedInTime;
    try{connectedInTime=gate.await(10,TimeUnit.SECONDS);}catch(InterruptedException cancelled){note(NetworkDiagnostics.Event.IPC_BIND_INTERRUPTED,NetworkDiagnostics.Stage.BIND,0);throw cancelled;}
    synchronized(this){if(!connectedInTime||!binding.current()||binding.epoch!=epoch||service==null||service!=epoch.target){note(NetworkDiagnostics.Event.IPC_BIND_TIMEOUT,NetworkDiagnostics.Stage.BIND,0);throw new IOException("网络服务未就绪");}}
    if(action.equals("launch")){try{context.startForegroundService(new Intent(context,NetworkTransportService.class));}catch(RuntimeException e){note(NetworkDiagnostics.Event.IPC_FOREGROUND_REJECTED,NetworkDiagnostics.Stage.START,0);throw new IOException("请在应用打开时连接网络",e);}}
    String id=UUID.randomUUID().toString();Pending waiting=new Pending(epoch);
    Message request=Message.obtain(null,NetworkTransportService.COMMAND);request.replyTo=epoch.replies;Bundle data=new Bundle();data.putString("id",id);data.putInt("slot",slot);data.putString("action",action);data.putString("configuration",configuration);data.putString("generation",state.optString("generation"));data.putString("stopReason",(stopReason==null?NetworkDiagnostics.Reason.UNKNOWN:stopReason).name());data.putString("expectedGeneration",expectedGeneration==null?"":expectedGeneration);if(guardGeneration){if(expectedOwner==null||expectedOwner.slot!=slot)throw new IOException("网络环境身份不匹配");data.putBoolean("guardGeneration",true);data.putString("expectedOwner",expectedOwner.json().toString());}request.setData(data);
    try{
      try{Messenger target;synchronized(this){if(!binding.current()||binding.epoch!=epoch||service!=epoch.target||service==null)throw new IOException("网络服务暂时退出");requests.put(id,waiting);target=epoch.target;}target.send(request);}catch(Exception failed){note(NetworkDiagnostics.Event.IPC_SEND_FAILED,NetworkDiagnostics.Stage.SEND,0);throw failed;}
      JSONObject result;try{result=waiting.result.get(15,TimeUnit.SECONDS);}catch(TimeoutException timeout){note(NetworkDiagnostics.Event.IPC_REPLY_TIMEOUT,NetworkDiagnostics.Stage.REPLY,0);throw timeout;}catch(ExecutionException failed){note(NetworkDiagnostics.Event.IPC_REPLY_FAILED,NetworkDiagnostics.Stage.REPLY,0);throw failed;}catch(InterruptedException cancelled){note(NetworkDiagnostics.Event.IPC_REPLY_INTERRUPTED,NetworkDiagnostics.Stage.REPLY,0);throw cancelled;}
      if(!result.optBoolean("ok")){note(NetworkDiagnostics.Event.IPC_REMOTE_REJECTED,NetworkDiagnostics.Stage.REPLY,0);throw new IOException("网络服务操作失败");}return new Reply(binding,result.optJSONObject("state"));
    }finally{requests.remove(id,waiting);}
  }
  void detach()throws Exception{Binding binding=performCall("detach","",NetworkDiagnostics.Reason.UNKNOWN,"").binding;note(NetworkDiagnostics.Event.IPC_DETACH,NetworkDiagnostics.Stage.IPC,0);CountDownLatch done=new CountDownLatch(1);main.post(()->{try{synchronized(this){retire(binding,false);}unbind(binding);}finally{done.countDown();}});if(!done.await(5,TimeUnit.SECONDS))throw new IOException("网络客户端尚未断开");}
  boolean alive(){return state.optBoolean("alive");}
}
