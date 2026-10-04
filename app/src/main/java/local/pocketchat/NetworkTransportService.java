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
  final Handler main=new Handler(Looper.getMainLooper());final Node[] nodes=new Node[Profiles.MAX];
  final Messenger endpoint=new Messenger(new Handler(Looper.getMainLooper()){public void handleMessage(Message message){receive(message);}});
  static final class Node {
    final int slot;final ExecutorService commands=Executors.newSingleThreadExecutor();final Map<IBinder,Messenger> subscribers=new ConcurrentHashMap<>();
    volatile java.lang.Process process;volatile String state="closed",generation="",configHash="";volatile int pid,controllerPort,proxyPort,webProbePort;
    Node(int slot){this.slot=slot;}
    boolean alive(){java.lang.Process p=process;return p!=null&&p.isAlive();}
    JSONObject snapshot(){return J.obj("slot",slot,"state",state,"alive",alive(),"generation",generation,"pid",pid,"servicePid",android.os.Process.myPid(),"configuration",configHash,"controllerPort",controllerPort,"proxyPort",proxyPort,"webProbePort",webProbePort);}
  }
  @Override public void onCreate(){super.onCreate();for(int slot=0;slot<nodes.length;slot++)nodes[slot]=new Node(slot);getSystemService(NotificationManager.class).createNotificationChannel(new NotificationChannel("network-transport","独立环境网络",NotificationManager.IMPORTANCE_LOW));}
  @Override public IBinder onBind(Intent intent){return endpoint.getBinder();}
  @Override public int onStartCommand(Intent intent,int flags,int startId){notification();return START_NOT_STICKY;}
  void notification(){
    int count=0;for(Node n:nodes)if(n.alive())count++;
    PendingIntent open=PendingIntent.getActivity(this,NOTICE,new Intent(this,WindowHomeActivity.class),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
    Notification notice=new Notification.Builder(this,"network-transport").setSmallIcon(android.R.drawable.stat_sys_upload_done).setContentTitle("网络连接").setContentText(count==0?"正在连接…":count+" 个环境保持连接").setContentIntent(open).setOnlyAlertOnce(true).setOngoing(true).build();
    if(Build.VERSION.SDK_INT>=34)startForeground(NOTICE,notice,ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);else startForeground(NOTICE,notice);
  }
  void updateNotification(){main.post(()->{boolean live=false;for(Node n:nodes)live|=n.alive();if(live)notification();else{stopForeground(STOP_FOREGROUND_REMOVE);stopSelf();}});}
  void receive(Message request){
    if(request.what!=COMMAND||request.sendingUid!=android.os.Process.myUid()||request.replyTo==null)return;
    Bundle data=request.getData();int slot=data.getInt("slot",-1);if(slot<0||slot>=nodes.length)return;
    Node n=nodes[slot];Messenger reply=request.replyTo;String id=data.getString("id",""),action=data.getString("action","");
    n.subscribers.put(reply.getBinder(),reply);
    n.commands.execute(()->{JSONObject result;try{
      if("launch".equals(action)){launch(n,data.getString("configuration",""));}
      else if("stop".equals(action))stop(n);
      else if("ready".equals(action)){if(!n.generation.equals(data.getString("generation"))||!n.alive())throw new IOException("网络实例已变化");n.state="running";event(n);}
      else if("detach".equals(action))n.subscribers.remove(reply.getBinder());
      else if(!"snapshot".equals(action))throw new IOException("未知网络命令");
      result=J.obj("ok",true,"state",n.snapshot());
    }catch(Exception e){result=J.obj("ok",false,"message",e.getMessage()==null?"网络服务操作失败":e.getMessage(),"state",n.snapshot());}
      Message response=Message.obtain(null,REPLY);Bundle body=new Bundle();body.putString("id",id);body.putString("json",result.toString());response.setData(body);try{reply.send(response);}catch(RemoteException dead){n.subscribers.remove(reply.getBinder());}
    });
  }
  File root(Node n){return new File(Profiles.context(this,n.slot).getNoBackupFilesDir(),"network-runtime");}
  void launch(Node n,String configuration)throws Exception{
    stop(n,false);File directory=root(n),configFile=new File(directory,"config.json");JSONObject config=J.parse(new String(java.nio.file.Files.readAllBytes(configFile.toPath()),StandardCharsets.UTF_8));
    if(config.optString("secret").isEmpty()||!config.optString("external-controller").startsWith("127.0.0.1:"))throw new IOException("网络配置尚未就绪");
    n.controllerPort=Integer.parseInt(config.getString("external-controller").substring("127.0.0.1:".length()));n.proxyPort=n.webProbePort=0;
    JSONArray listeners=config.optJSONArray("listeners");if(listeners!=null)for(int i=0;i<listeners.length();i++){JSONObject listener=listeners.getJSONObject(i);if(!"127.0.0.1".equals(listener.optString("listen")))throw new IOException("网络监听器必须为本机回环");if("PocketOnly".equals(listener.optString("name")))n.proxyPort=listener.getInt("port");if("WebsiteCheck".equals(listener.optString("name")))n.webProbePort=listener.getInt("port");}
    // Bootstrap has no listeners; the selected ports are supplied by the private caller.
    JSONObject transport=J.parse(new String(java.nio.file.Files.readAllBytes(new File(directory,"transport.json").toPath()),StandardCharsets.UTF_8));n.proxyPort=transport.getInt("proxyPort");n.webProbePort=transport.getInt("webProbePort");
    File binary=new File(getApplicationInfo().nativeLibraryDir,"libmihomo.so");if(!binary.isFile())throw new IOException("该手机没有可用网络内核");
    n.generation=UUID.randomUUID().toString();n.configHash=configuration;n.state="starting";final String generation=n.generation;
    java.lang.Process p=new ProcessBuilder("/system/bin/sh","-c","umask 077; echo $$ > \"$1/core.pid\"; exec \"$2\" -d \"$1\" -f \"$1/config.json\"","network-transport",directory.getAbsolutePath(),binary.getAbsolutePath()).redirectErrorStream(true).start();n.process=p;
    new Thread(()->{try(InputStream in=p.getInputStream()){byte[] bytes=new byte[4096];while(in.read(bytes)>=0){}}catch(IOException ignored){}},"network-output-"+n.slot).start();
    new Thread(()->{try{p.waitFor();n.commands.execute(()->{if(n.process==p&&n.generation.equals(generation)){n.process=null;n.state="failed";event(n);updateNotification();}});}catch(InterruptedException ignored){Thread.currentThread().interrupt();}catch(RejectedExecutionException ignored){}},"network-supervisor-"+n.slot).start();
    try{for(int i=0;i<20;i++){File pidFile=new File(directory,"core.pid");if(pidFile.isFile()){n.pid=Integer.parseInt(new String(java.nio.file.Files.readAllBytes(pidFile.toPath()),StandardCharsets.US_ASCII).trim());break;}Thread.sleep(10);}}catch(Exception ignored){}
    event(n);main.post(this::notification);
  }
  void stop(Node n)throws Exception{stop(n,true);}
  void stop(Node n,boolean announce)throws Exception{
    java.lang.Process p=n.process;n.process=null;n.state="closed";n.generation=UUID.randomUUID().toString();
    if(p==null)cleanupOrphan(n);
    if(p!=null){p.destroy();if(!p.waitFor(2,TimeUnit.SECONDS)){p.destroyForcibly();if(!p.waitFor(2,TimeUnit.SECONDS))throw new IOException("网络内核尚未停止");}}
    File pidFile=new File(root(n),"core.pid");if(pidFile.exists()&&!pidFile.delete())throw new IOException("网络运行记录无法清理");n.pid=0;event(n);if(announce)updateNotification();
  }
  void cleanupOrphan(Node n)throws Exception{
    File record=new File(root(n),"core.pid");if(!record.isFile())return;
    int pid=Integer.parseInt(new String(java.nio.file.Files.readAllBytes(record.toPath()),StandardCharsets.US_ASCII).trim());if(pid<=1||pid==android.os.Process.myPid())throw new IOException("无效网络运行记录");
    File statusFile=new File("/proc/"+pid+"/status");if(!statusFile.isFile())return;
    String status=new String(java.nio.file.Files.readAllBytes(statusFile.toPath()),StandardCharsets.US_ASCII),cmd=new String(java.nio.file.Files.readAllBytes(new File("/proc/"+pid+"/cmdline").toPath()),StandardCharsets.UTF_8);
    if(!status.matches("(?s).*Uid:\\s+"+android.os.Process.myUid()+"\\s+.*")||!cmd.contains("libmihomo.so")||!cmd.contains(root(n).getAbsolutePath()))throw new IOException("网络运行记录不属于此环境");
    android.os.Process.killProcess(pid);
  }
  void event(Node n){Message message=Message.obtain(null,EVENT);Bundle data=new Bundle();data.putString("json",n.snapshot().toString());message.setData(data);for(Map.Entry<IBinder,Messenger> entry:n.subscribers.entrySet())try{entry.getValue().send(Message.obtain(message));}catch(RemoteException dead){n.subscribers.remove(entry.getKey());}}
  @Override public void onDestroy(){for(Node n:nodes){try{stop(n,false);}catch(Exception ignored){}n.commands.shutdownNow();}super.onDestroy();}
}
