package local.pocketchat;

import android.app.*;
import android.content.*;
import android.content.pm.ServiceInfo;
import android.os.*;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;

/** Data-plane ownership is independent of every browser and its control process. */
public final class NetworkTransportService extends Service {
  static final int COMMAND=1,REPLY=2,EVENT=3,NOTICE=23000;
  volatile boolean destroying;volatile ExitPreconnectEpoch preconnectEpoch;final Handler main=new Handler(Looper.getMainLooper());final Node[] nodes=new Node[Profiles.MAX];final Runnable idleStop=()->{if(destroying)return;for(Node n:nodes)if(n.alive()||n.pendingLaunches.get()>0)return;stopForeground(STOP_FOREGROUND_REMOVE);stopSelf();};
  final Messenger endpoint=new Messenger(new Handler(Looper.getMainLooper()){public void handleMessage(Message message){receive(message);}});
  static final class Node {
    final java.util.concurrent.atomic.AtomicInteger pendingLaunches=new java.util.concurrent.atomic.AtomicInteger();final int slot;final ExecutorService commands=Executors.newSingleThreadExecutor();final Map<IBinder,Messenger> subscribers=new ConcurrentHashMap<>();
    volatile java.lang.Process process;volatile String state="closed",generation="",configHash="";volatile int pid,controllerPort,proxyPort,webProbePort;
    volatile NetworkDiagnostics diagnostics;volatile Lifetime lifetime;
    Node(int slot){this.slot=slot;}
    boolean alive(){java.lang.Process p=process;return p!=null&&p.isAlive();}
    JSONObject snapshot(){return J.obj("slot",slot,"state",state,"alive",alive(),"generation",generation,"pid",pid,"servicePid",android.os.Process.myPid(),"configuration",configHash,"controllerPort",controllerPort,"proxyPort",proxyPort,"webProbePort",webProbePort);}
  }
  static final class Lifetime {
    final java.lang.Process process;final String generation;final NetworkDiagnostics diagnostics;
    volatile NetworkDiagnostics.Reason stopReason=NetworkDiagnostics.Reason.CORE_EXITED;
    Lifetime(java.lang.Process process,String generation,NetworkDiagnostics diagnostics){this.process=process;this.generation=generation;this.diagnostics=diagnostics;}
  }
  static final class StaleGeneration extends IOException {StaleGeneration(){super("网络实例已变化");}}
  void note(Node n,NetworkDiagnostics.Event event,NetworkDiagnostics.Reason reason,NetworkDiagnostics.Stage stage,long value){NetworkDiagnostics d=n.diagnostics;if(d!=null)d.record(event,n.generation,reason,stage,value);}
  @Override public void onCreate(){super.onCreate();for(int slot=0;slot<nodes.length;slot++)nodes[slot]=new Node(slot);preconnectEpoch=new ExitPreconnectEpoch(this,this::writePreconnectEpochs);QuietNotifications.backgroundChannel(this,QuietNotifications.NETWORK_BACKGROUND,"后台连接服务 · 静默");}
  @Override public void onTrimMemory(int level){super.onTrimMemory(level);if(destroying||nodes[0]==null)return;try{nodes[0].commands.execute(()->{if(!destroying)writePreconnectEpochs();});}catch(RejectedExecutionException ignored){}}
  @Override public void onLowMemory(){super.onLowMemory();onTrimMemory(android.content.ComponentCallbacks2.TRIM_MEMORY_COMPLETE);}
  void writePreconnectEpochs(){ExitPreconnectEpoch epoch=preconnectEpoch;if(epoch==null)return;File base=Profiles.global(this).getNoBackupFilesDir();for(Node n:nodes){File profile=n.slot==0?base:new File(base,"profiles/env"+n.slot);File directory=new File(profile,"network-runtime");android.util.AtomicFile file=new android.util.AtomicFile(new File(directory,ExitPreconnectEpoch.FILE));try{if(file.getBaseFile().isFile())epoch.writeExisting(directory);}catch(Exception unavailable){file.delete();}}}
  @Override public IBinder onBind(Intent intent){return endpoint.getBinder();}
  @Override public int onStartCommand(Intent intent,int flags,int startId){main.removeCallbacks(idleStop);notification();return START_NOT_STICKY;}
  void notification(){
    if(destroying)return;main.removeCallbacks(idleStop);
    PendingIntent open=PendingIntent.getActivity(this,NOTICE,new Intent(this,WindowHomeActivity.class),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
    Notification notice=QuietNotifications.background(this,QuietNotifications.NETWORK_BACKGROUND,"后台连接服务",open);
    if(Build.VERSION.SDK_INT>=34)startForeground(NOTICE,notice,ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);else startForeground(NOTICE,notice);
  }
  void updateNotification(){main.post(()->{boolean live=false;for(Node n:nodes)live|=n.alive();if(live)notification();else{main.removeCallbacks(idleStop);main.postDelayed(idleStop,1000);}});}
  void receive(Message request){
    if(request.what!=COMMAND||request.sendingUid!=android.os.Process.myUid()||request.replyTo==null)return;
    Bundle data=request.getData();int slot=data.getInt("slot",-1);if(slot<0||slot>=nodes.length)return;
    Node n=nodes[slot];Messenger reply=request.replyTo;String id=data.getString("id",""),action=data.getString("action","");
    n.subscribers.put(reply.getBinder(),reply);if(action.equals("launch")){main.removeCallbacks(idleStop);n.pendingLaunches.incrementAndGet();}
    n.commands.execute(()->{JSONObject result;try{
      if("launch".equals(action)){launch(n,data.getString("configuration",""));}
      else if("stop".equals(action)){String expected=data.getString("expectedGeneration","");if(!expected.isEmpty()&&!expected.equals(n.generation))throw new StaleGeneration();stop(n,true,NetworkDiagnostics.reason(data.getString("stopReason","UNKNOWN")));}
      else if("ready".equals(action)){if(!n.generation.equals(data.getString("generation"))||!n.alive())throw new IOException("网络实例已变化");n.state="running";event(n);}
      else if("detach".equals(action))n.subscribers.remove(reply.getBinder());
      else if(!"snapshot".equals(action))throw new IOException("未知网络命令");
      result=J.obj("ok",true,"state",n.snapshot());
    }catch(Exception e){note(n,NetworkDiagnostics.Event.FAILURE,"launch".equals(action)?NetworkDiagnostics.Reason.START_FAILED:NetworkDiagnostics.Reason.CONTROL_UNAVAILABLE,"launch".equals(action)?NetworkDiagnostics.Stage.START:"stop".equals(action)?NetworkDiagnostics.Stage.STOP:NetworkDiagnostics.Stage.IPC,0);result=J.obj("ok",false,"message","网络服务操作失败","failureCode",e instanceof StaleGeneration?"stale_generation":"operation_failed","state",n.snapshot());}
      if(action.equals("launch")){n.pendingLaunches.decrementAndGet();updateNotification();}
      Message response=Message.obtain(null,REPLY);Bundle body=new Bundle();body.putString("id",id);body.putString("json",result.toString());response.setData(body);try{reply.send(response);}catch(RemoteException dead){note(n,NetworkDiagnostics.Event.IPC_REPLY_SEND_FAILED,NetworkDiagnostics.Reason.CONTROL_UNAVAILABLE,NetworkDiagnostics.Stage.REPLY,0);n.subscribers.remove(reply.getBinder());}
    });
  }
  File root(Node n){return new File(Profiles.context(this,n.slot).getNoBackupFilesDir(),"network-runtime");}
  void launch(Node n,String configuration)throws Exception{
    if(destroying)throw new IOException("网络服务正在结束");stop(n,false,NetworkDiagnostics.Reason.REPLACE);
    // A slot may have been deleted and recreated. Old output/supervisor threads retain their own logger.
    NetworkDiagnostics diagnostics=NetworkDiagnosticStore.forContext(Profiles.context(this,n.slot),NetworkDiagnostics.Source.SERVICE);NetworkDiagnosticStore.bind(diagnostics,Profiles.context(this,n.slot));n.diagnostics=diagnostics;
    diagnostics.record(NetworkDiagnostics.Event.SERVICE_AVAILABLE,NetworkDiagnostics.UNKNOWN,NetworkDiagnostics.Reason.UNKNOWN,NetworkDiagnostics.Stage.CORE,android.os.Process.myPid());
    File directory=root(n),configFile=new File(directory,"config.json");ExitPreconnectEpoch epoch=preconnectEpoch;synchronized(epoch){if(destroying||epoch.closed)throw new IOException("网络服务正在结束");try{epoch.write(directory);}catch(IOException unavailable){new android.util.AtomicFile(new File(directory,ExitPreconnectEpoch.FILE)).delete();}}JSONObject config=J.parse(new String(java.nio.file.Files.readAllBytes(configFile.toPath()),StandardCharsets.UTF_8));
    if(config.optString("secret").isEmpty()||!config.optString("external-controller").startsWith("127.0.0.1:"))throw new IOException("网络配置尚未就绪");
    n.controllerPort=Integer.parseInt(config.getString("external-controller").substring("127.0.0.1:".length()));n.proxyPort=n.webProbePort=0;
    JSONArray listeners=config.optJSONArray("listeners");if(listeners!=null)for(int i=0;i<listeners.length();i++){JSONObject listener=listeners.getJSONObject(i);if(!"127.0.0.1".equals(listener.optString("listen")))throw new IOException("网络监听器必须为本机回环");if("PocketOnly".equals(listener.optString("name")))n.proxyPort=listener.getInt("port");if("WebsiteCheck".equals(listener.optString("name")))n.webProbePort=listener.getInt("port");}
    // Bootstrap has no listeners; the selected ports are supplied by the private caller.
    JSONObject transport=J.parse(new String(java.nio.file.Files.readAllBytes(new File(directory,"transport.json").toPath()),StandardCharsets.UTF_8));n.proxyPort=transport.getInt("proxyPort");n.webProbePort=transport.getInt("webProbePort");
    File binary=new File(getApplicationInfo().nativeLibraryDir,"libmihomo.so");if(!binary.isFile())throw new IOException("该手机没有可用网络内核");
    n.generation=UUID.randomUUID().toString();n.configHash=configuration;n.state="starting";final String generation=n.generation;
    diagnostics.record(NetworkDiagnostics.Event.CORE_START,generation,NetworkDiagnostics.Reason.UNKNOWN,NetworkDiagnostics.Stage.START,0);
    java.lang.Process p=new ProcessBuilder("/system/bin/sh","-c","umask 077; echo $$ > \"$1/core.pid\"; exec \"$2\" -d \"$1\" -f \"$1/config.json\"","network-transport",directory.getAbsolutePath(),binary.getAbsolutePath()).redirectErrorStream(true).start();n.process=p;
    final Lifetime lifetime=new Lifetime(p,generation,diagnostics);n.lifetime=lifetime;
    new Thread(()->{try(NetworkDiagnostics.Output output=diagnostics.output(generation);InputStream in=p.getInputStream()){byte[] bytes=new byte[4096];int count;while((count=in.read(bytes))!=-1)output.add(count);}catch(IOException ignored){diagnostics.record(NetworkDiagnostics.Event.FAILURE,generation,NetworkDiagnostics.Reason.UNKNOWN,NetworkDiagnostics.Stage.OUTPUT,0);}},"network-output-"+n.slot).start();
    new Thread(()->{try{int exit=p.waitFor();diagnostics.record(NetworkDiagnostics.Event.CORE_EXIT,generation,lifetime.stopReason,NetworkDiagnostics.Stage.CORE,exit);n.commands.execute(()->{if(n.process==p&&n.generation.equals(generation)){n.process=null;n.state="failed";event(n);updateNotification();}});}catch(InterruptedException ignored){Thread.currentThread().interrupt();}catch(RejectedExecutionException ignored){}},"network-supervisor-"+n.slot).start();
    if(destroying){lifetime.stopReason=NetworkDiagnostics.Reason.SERVICE_DESTROY;diagnostics.record(NetworkDiagnostics.Event.STOP_FORCED,generation,lifetime.stopReason,NetworkDiagnostics.Stage.STOP,0);p.destroyForcibly();throw new IOException("网络服务正在结束");}
    try{for(int i=0;i<20;i++){File pidFile=new File(directory,"core.pid");if(pidFile.isFile()){n.pid=Integer.parseInt(new String(java.nio.file.Files.readAllBytes(pidFile.toPath()),StandardCharsets.US_ASCII).trim());break;}Thread.sleep(10);}}catch(Exception ignored){}
    diagnostics.record(NetworkDiagnostics.Event.CORE_STARTED,generation,NetworkDiagnostics.Reason.UNKNOWN,NetworkDiagnostics.Stage.CORE,n.pid);
    event(n);main.post(this::notification);
  }
  void stop(Node n)throws Exception{stop(n,true,NetworkDiagnostics.Reason.REQUESTED);}
  void stop(Node n,boolean announce)throws Exception{stop(n,announce,NetworkDiagnostics.Reason.UNKNOWN);}
  void stop(Node n,boolean announce,NetworkDiagnostics.Reason reason)throws Exception{
    java.lang.Process p=n.process;n.state="stopping";
    Lifetime lifetime=n.lifetime;if(p!=null&&lifetime!=null&&lifetime.process==p){if(p.isAlive())lifetime.stopReason=reason;lifetime.diagnostics.record(NetworkDiagnostics.Event.STOP_REQUEST,lifetime.generation,reason,NetworkDiagnostics.Stage.STOP,0);}
    if(p==null)cleanupOrphan(n);
    if(p!=null){p.destroy();if(!p.waitFor(2,TimeUnit.SECONDS)){if(lifetime!=null&&lifetime.process==p)lifetime.diagnostics.record(NetworkDiagnostics.Event.STOP_FORCED,lifetime.generation,reason,NetworkDiagnostics.Stage.STOP,0);p.destroyForcibly();if(!p.waitFor(2,TimeUnit.SECONDS))throw new IOException("网络内核尚未停止");}}
    n.process=null;n.state="closed";n.generation=UUID.randomUUID().toString();
    File pidFile=new File(root(n),"core.pid");if(pidFile.exists()&&!pidFile.delete())throw new IOException("网络运行记录无法清理");n.pid=0;event(n);if(announce)updateNotification();
  }
  void cleanupOrphan(Node n)throws Exception{
    File record=new File(root(n),"core.pid");if(!record.isFile())return;
    int pid=Integer.parseInt(new String(java.nio.file.Files.readAllBytes(record.toPath()),StandardCharsets.US_ASCII).trim());if(pid<=1||pid==android.os.Process.myPid())throw new IOException("无效网络运行记录");
    File statusFile=new File("/proc/"+pid+"/status");if(!statusFile.isFile())return;
    String status=new String(java.nio.file.Files.readAllBytes(statusFile.toPath()),StandardCharsets.US_ASCII),cmd=new String(java.nio.file.Files.readAllBytes(new File("/proc/"+pid+"/cmdline").toPath()),StandardCharsets.UTF_8);
    if(!status.matches("(?s).*Uid:\\s+"+android.os.Process.myUid()+"\\s+.*")||!cmd.contains("libmihomo.so")||!cmd.contains(root(n).getAbsolutePath()))throw new IOException("网络运行记录不属于此环境");
    android.os.Process.killProcess(pid);
    long deadline=android.os.SystemClock.elapsedRealtime()+2000;while(statusFile.isFile()){
      try{String stopped=new String(java.nio.file.Files.readAllBytes(statusFile.toPath()),StandardCharsets.US_ASCII);if(stopped.matches("(?s).*State:\\s+Z.*"))return;}catch(java.nio.file.NoSuchFileException gone){return;}
      if(android.os.SystemClock.elapsedRealtime()>=deadline)throw new IOException("上次网络内核尚未停止");Thread.sleep(20);
    }
  }
  void event(Node n){Message message=Message.obtain(null,EVENT);Bundle data=new Bundle();data.putString("json",n.snapshot().toString());message.setData(data);for(Map.Entry<IBinder,Messenger> entry:n.subscribers.entrySet())try{entry.getValue().send(Message.obtain(message));}catch(RemoteException dead){note(n,NetworkDiagnostics.Event.IPC_EVENT_SEND_FAILED,NetworkDiagnostics.Reason.CONTROL_UNAVAILABLE,NetworkDiagnostics.Stage.IPC,0);n.subscribers.remove(entry.getKey());}}
  @Override public void onDestroy(){destroying=true;if(preconnectEpoch!=null)preconnectEpoch.close();main.removeCallbacks(idleStop);for(Node n:nodes){n.commands.execute(()->{note(n,NetworkDiagnostics.Event.SERVICE_DESTROY,NetworkDiagnostics.Reason.SERVICE_DESTROY,NetworkDiagnostics.Stage.CORE,0);try{stop(n,false,NetworkDiagnostics.Reason.SERVICE_DESTROY);}catch(Exception ignored){note(n,NetworkDiagnostics.Event.FAILURE,NetworkDiagnostics.Reason.SERVICE_DESTROY,NetworkDiagnostics.Stage.STOP,0);}});n.commands.shutdown();}super.onDestroy();}
}
