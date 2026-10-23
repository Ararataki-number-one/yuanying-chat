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
  final Map<String,CompletableFuture<JSONObject>> requests=new ConcurrentHashMap<>();
  final Messenger replies=new Messenger(new Handler(Looper.getMainLooper()){public void handleMessage(Message m){JSONObject result=J.parse(m.getData().getString("json","{}"));if(m.what==NetworkTransportService.EVENT){publish(result);}else if(m.what==NetworkTransportService.REPLY){CompletableFuture<JSONObject> waiting=requests.remove(m.getData().getString("id"));if(waiting!=null){JSONObject snapshot=result.optJSONObject("state");if(snapshot!=null)publish(snapshot);waiting.complete(result);}}}});
  final ServiceConnection connection=new ServiceConnection(){
    public void onServiceConnected(ComponentName name,IBinder binder){note(NetworkDiagnostics.Event.IPC_CONNECTED,NetworkDiagnostics.Stage.BIND,0);service=new Messenger(binder);connected.countDown();}
    public void onServiceDisconnected(ComponentName name){note(NetworkDiagnostics.Event.IPC_DISCONNECTED,NetworkDiagnostics.Stage.IPC,requests.size());service=null;connected=new CountDownLatch(1);lost();}
    public void onBindingDied(ComponentName name){note(NetworkDiagnostics.Event.IPC_BINDING_DIED,NetworkDiagnostics.Stage.BIND,requests.size());service=null;connected=new CountDownLatch(1);synchronized(NetworkTransportClient.this){bound=false;}try{context.unbindService(this);}catch(Exception ignored){}lost();}
    public void onNullBinding(ComponentName name){note(NetworkDiagnostics.Event.IPC_NULL_BINDING,NetworkDiagnostics.Stage.BIND,requests.size());lost();connected.countDown();}
  };
  NetworkTransportClient(Context c,Consumer<JSONObject> changed){context=c.getApplicationContext();slot=Profiles.slot(c);this.changed=changed;diagnostics=NetworkDiagnosticStore.forContext(c,NetworkDiagnostics.Source.CONTROL);}
  void note(NetworkDiagnostics.Event event,NetworkDiagnostics.Stage stage,long value){diagnostics.record(event,state.optString("generation",NetworkDiagnostics.UNKNOWN),event==NetworkDiagnostics.Event.IPC_CONNECTED||event==NetworkDiagnostics.Event.IPC_DETACH?NetworkDiagnostics.Reason.UNKNOWN:event==NetworkDiagnostics.Event.IPC_BIND_INTERRUPTED||event==NetworkDiagnostics.Event.IPC_REPLY_INTERRUPTED?NetworkDiagnostics.Reason.CANCELLED:NetworkDiagnostics.Reason.CONTROL_UNAVAILABLE,stage,value);}
  void publish(JSONObject value){if(value.optInt("slot",slot)!=slot)return;state=value;changed.accept(value);}
  void lost(){publish(J.obj("slot",slot,"alive",false,"state","failed"));for(CompletableFuture<JSONObject> request:requests.values())request.completeExceptionally(new IOException("网络服务暂时退出"));requests.clear();}
  synchronized void bind(){if(bound)return;bound=true;main.post(()->{try{if(!context.bindService(new Intent(context,NetworkTransportService.class),connection,Context.BIND_AUTO_CREATE)){note(NetworkDiagnostics.Event.IPC_BIND_REJECTED,NetworkDiagnostics.Stage.BIND,0);bound=false;connected.countDown();}}catch(Exception e){note(NetworkDiagnostics.Event.IPC_BIND_EXCEPTION,NetworkDiagnostics.Stage.BIND,0);bound=false;connected.countDown();}});}
  JSONObject call(String action,String configuration)throws Exception{
    return call(action,configuration,NetworkDiagnostics.Reason.UNKNOWN);
  }
  JSONObject call(String action,String configuration,NetworkDiagnostics.Reason stopReason)throws Exception{
    return call(action,configuration,stopReason,"");
  }
  JSONObject call(String action,String configuration,NetworkDiagnostics.Reason stopReason,String expectedGeneration)throws Exception{
    if(Looper.myLooper()==Looper.getMainLooper())throw new IOException("网络服务操作需要后台线程");NetworkDiagnosticStore.bind(diagnostics,context);bind();CountDownLatch gate=connected;boolean connectedInTime;
    try{connectedInTime=gate.await(10,TimeUnit.SECONDS);}catch(InterruptedException cancelled){note(NetworkDiagnostics.Event.IPC_BIND_INTERRUPTED,NetworkDiagnostics.Stage.BIND,0);throw cancelled;}
    if(!connectedInTime||service==null){note(NetworkDiagnostics.Event.IPC_BIND_TIMEOUT,NetworkDiagnostics.Stage.BIND,0);throw new IOException("网络服务未就绪");}
    if(action.equals("launch")){try{context.startForegroundService(new Intent(context,NetworkTransportService.class));}catch(RuntimeException e){note(NetworkDiagnostics.Event.IPC_FOREGROUND_REJECTED,NetworkDiagnostics.Stage.START,0);throw new IOException("请在应用打开时连接网络",e);}}
    String id=UUID.randomUUID().toString();CompletableFuture<JSONObject> waiting=new CompletableFuture<>();requests.put(id,waiting);
    Message request=Message.obtain(null,NetworkTransportService.COMMAND);request.replyTo=replies;Bundle data=new Bundle();data.putString("id",id);data.putInt("slot",slot);data.putString("action",action);data.putString("configuration",configuration);data.putString("generation",state.optString("generation"));data.putString("stopReason",(stopReason==null?NetworkDiagnostics.Reason.UNKNOWN:stopReason).name());data.putString("expectedGeneration",expectedGeneration==null?"":expectedGeneration);request.setData(data);
    try{
      try{Messenger target=service;if(target==null)throw new IOException("网络服务暂时退出");target.send(request);}catch(Exception failed){note(NetworkDiagnostics.Event.IPC_SEND_FAILED,NetworkDiagnostics.Stage.SEND,0);throw failed;}
      JSONObject result;try{result=waiting.get(15,TimeUnit.SECONDS);}catch(TimeoutException timeout){note(NetworkDiagnostics.Event.IPC_REPLY_TIMEOUT,NetworkDiagnostics.Stage.REPLY,0);throw timeout;}catch(ExecutionException failed){note(NetworkDiagnostics.Event.IPC_REPLY_FAILED,NetworkDiagnostics.Stage.REPLY,0);throw failed;}catch(InterruptedException cancelled){note(NetworkDiagnostics.Event.IPC_REPLY_INTERRUPTED,NetworkDiagnostics.Stage.REPLY,0);throw cancelled;}
      if(!result.optBoolean("ok")){note(NetworkDiagnostics.Event.IPC_REMOTE_REJECTED,NetworkDiagnostics.Stage.REPLY,0);throw new IOException("网络服务操作失败");}return result.optJSONObject("state");
    }finally{requests.remove(id);}
  }
  void detach()throws Exception{call("detach","");note(NetworkDiagnostics.Event.IPC_DETACH,NetworkDiagnostics.Stage.IPC,0);CountDownLatch done=new CountDownLatch(1);main.post(()->{try{context.unbindService(connection);}finally{synchronized(this){bound=false;}service=null;connected=new CountDownLatch(1);done.countDown();}});if(!done.await(5,TimeUnit.SECONDS))throw new IOException("网络客户端尚未断开");}
  boolean alive(){return state.optBoolean("alive");}
}
