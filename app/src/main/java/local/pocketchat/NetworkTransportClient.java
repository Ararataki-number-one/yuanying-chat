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
  volatile Messenger service;volatile JSONObject state=new JSONObject();volatile CountDownLatch connected=new CountDownLatch(1);boolean bound;
  final Map<String,CompletableFuture<JSONObject>> requests=new ConcurrentHashMap<>();
  final Messenger replies=new Messenger(new Handler(Looper.getMainLooper()){public void handleMessage(Message m){JSONObject result=J.parse(m.getData().getString("json","{}"));if(m.what==NetworkTransportService.EVENT){publish(result);}else if(m.what==NetworkTransportService.REPLY){CompletableFuture<JSONObject> waiting=requests.remove(m.getData().getString("id"));if(waiting!=null){JSONObject snapshot=result.optJSONObject("state");if(snapshot!=null)publish(snapshot);waiting.complete(result);}}}});
  final ServiceConnection connection=new ServiceConnection(){
    public void onServiceConnected(ComponentName name,IBinder binder){service=new Messenger(binder);connected.countDown();}
    public void onServiceDisconnected(ComponentName name){service=null;connected=new CountDownLatch(1);lost();}
    public void onBindingDied(ComponentName name){service=null;connected=new CountDownLatch(1);synchronized(NetworkTransportClient.this){bound=false;}try{context.unbindService(this);}catch(Exception ignored){}lost();}
    public void onNullBinding(ComponentName name){lost();connected.countDown();}
  };
  NetworkTransportClient(Context c,Consumer<JSONObject> changed){context=c.getApplicationContext();slot=Profiles.slot(c);this.changed=changed;}
  void publish(JSONObject value){if(value.optInt("slot",slot)!=slot)return;state=value;changed.accept(value);}
  void lost(){publish(J.obj("slot",slot,"alive",false,"state","failed"));for(CompletableFuture<JSONObject> request:requests.values())request.completeExceptionally(new IOException("网络服务暂时退出"));requests.clear();}
  synchronized void bind(){if(bound)return;bound=true;main.post(()->{try{if(!context.bindService(new Intent(context,NetworkTransportService.class),connection,Context.BIND_AUTO_CREATE)){bound=false;connected.countDown();}}catch(Exception e){bound=false;connected.countDown();}});}
  JSONObject call(String action,String configuration)throws Exception{
    if(Looper.myLooper()==Looper.getMainLooper())throw new IOException("网络服务操作需要后台线程");bind();CountDownLatch gate=connected;if(!gate.await(10,TimeUnit.SECONDS)||service==null)throw new IOException("网络服务未就绪");
    if(action.equals("launch")){try{context.startForegroundService(new Intent(context,NetworkTransportService.class));}catch(RuntimeException e){throw new IOException("请在应用打开时连接网络",e);}}
    String id=UUID.randomUUID().toString();CompletableFuture<JSONObject> waiting=new CompletableFuture<>();requests.put(id,waiting);
    Message request=Message.obtain(null,NetworkTransportService.COMMAND);request.replyTo=replies;Bundle data=new Bundle();data.putString("id",id);data.putInt("slot",slot);data.putString("action",action);data.putString("configuration",configuration);data.putString("generation",state.optString("generation"));request.setData(data);
    try{service.send(request);JSONObject result=waiting.get(15,TimeUnit.SECONDS);if(!result.optBoolean("ok"))throw new IOException(result.optString("message","网络服务操作失败"));return result.optJSONObject("state");}finally{requests.remove(id);}
  }
  void detach()throws Exception{call("detach","");CountDownLatch done=new CountDownLatch(1);main.post(()->{try{context.unbindService(connection);}finally{synchronized(this){bound=false;}service=null;connected=new CountDownLatch(1);done.countDown();}});if(!done.await(5,TimeUnit.SECONDS))throw new IOException("网络客户端尚未断开");}
  boolean alive(){return state.optBoolean("alive");}
}
