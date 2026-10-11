package local.pocketchat;

import android.app.*;
import android.content.*;
import android.net.Uri;
import android.os.*;
import android.util.Log;
import android.widget.TextView;
import org.json.*;
import java.io.*;
import java.net.*;
import java.security.MessageDigest;

/** Test-only synthetic APK over loopback. Production update URLs are never overridden. */
public class AppUpdateIntegrationActivity extends AppUpdateActivity {
  final Handler handler=new Handler(Looper.getMainLooper());String action;AppUpdateManager manager;long started;String hash;
  String transferScenario,transferToken;long statusReads,statusIo,maxStatusNs,firstReceived=-1,lastReceived=-1,progressPairs;int renders,lastRender;TextView previousDetails;String previousProgress="";
  volatile boolean commandQueueDrained,preparationGuardReached;
  @Override public void onCreate(Bundle state){super.onCreate(state);command(getIntent());}
  @Override protected void onNewIntent(Intent intent){super.onNewIntent(intent);setIntent(intent);command(intent);}
  @Override void render(Bundle b){renders++;super.render(b);}
  @Override void updateProgress(Bundle b){super.updateProgress(b);if(transferScenario==null)return;
    String signature=b.getString("state","")+"|"+b.getString("message","")+"|"+b.getBoolean("canResume");long received=b.getLong("received");
    if("downloading".equals(b.getString("state"))&&signature.equals(previousProgress)&&lastReceived>=0&&received!=lastReceived&&previousDetails==downloadDetails&&lastRender==renders)progressPairs++;
    previousProgress=signature;lastReceived=received;previousDetails=downloadDetails;lastRender=renders;
  }
  void command(Intent intent){handler.removeCallbacksAndMessages(null);action=intent.getStringExtra("updateAction");if(action!=null&&action.startsWith("transfer")){transferCommand(intent);return;}if("showUi".equals(action)){AppUpdates.open(this);event(J.obj("opened",true));return;}
    manager=AppUpdateManager.get(this);AppSettings.put(this,"updateAutoCheck","false");AppUpdates.schedule(this);
    if("verifyAccess".equals(action)){try{Bundle status=AppUpdates.call(this,"status",null);Uri uri=Uri.parse(status.getString("uri"));try(InputStream in=getContentResolver().openInputStream(uri);ByteArrayOutputStream out=new ByteArrayOutputStream()){byte[] buf=new byte[4096];int n;while((n=in.read(buf))!=-1)out.write(buf,0,n);if(!AppUpdatePolicy.hash(out.toByteArray()).equals(manager.info.sha))throw new IOException("Provider bytes differ");}
      boolean readOnly=false,traversal=false;try{getContentResolver().openFileDescriptor(uri,"rw");}catch(FileNotFoundException e){readOnly=true;}try{getContentResolver().openFileDescriptor(AppUpdates.uri(this).buildUpon().appendPath("..").appendPath("chat.db").build(),"r");}catch(FileNotFoundException e){traversal=true;}
      event(J.obj("readOnly",readOnly,"traversalRejected",traversal,"sameSigner",true,"installedVersion",AppVersion.name(this),"packageVersion",AppUpdateFiles.installed(this)));
    }catch(Exception e){event(J.obj("error",String.valueOf(e)));}return;}
    try{
      hash=intent.getStringExtra("updateHash");long bytes=intent.getLongExtra("updateBytes",0);if(hash==null||bytes<=0)throw new IOException("Missing synthetic fixture identity");
      JSONObject metadata=J.obj("schema",1,"package","local.pocketchat","version","99.0.0","versionCode",AppUpdateFiles.installed(this)+1,"bytes",bytes,"sha256",hash,"signerSha256",AppUpdatePolicy.SIGNER,"downloadUrl",AppUpdatePolicy.asset("99.0.0"),"abi","arm64-v8a","minSdk",26,"notes","受控安装包；测试不会实际安装。");
      manager.worker.execute(()->{try{manager.removeDownload();manager.clearFiles();manager.info=new AppUpdateInfo(metadata);manager.raw=metadata.toString();File external=new File(getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS),"fixture-"+action+".download");external.delete();String path="good".equals(action)?"/update-apk":"badSigner".equals(action)?"/update-wrong-signer":"badHash".equals(action)?"/update-corrupt":"/update-wait";
        DownloadManager.Request request=new DownloadManager.Request(Uri.parse("http://127.0.0.1:8765"+path)).setDestinationUri(Uri.fromFile(external)).setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE);manager.generation.incrementAndGet();manager.id=manager.downloads.enqueue(request);manager.change("downloading","");handler.post(()->{started=SystemClock.elapsedRealtime();if("cancel".equals(action))AppUpdates.call(this,"cancel",null);waitResult();});
      }catch(Exception e){handler.post(()->event(J.obj("error",String.valueOf(e))));}});
    }catch(Exception e){event(J.obj("error",String.valueOf(e)));}
  }
  void waitResult(){Bundle status=AppUpdates.call(this,"status",null);String state=status.getString("state");if("ready".equals(state)||"available".equals(state)){event(J.obj("action",action,"state",state,"message",status.getString("message"),"uri",status.getString("uri",""),"downloadId",manager.downloadId()));return;}if(SystemClock.elapsedRealtime()-started>60000){event(J.obj("error","DownloadManager did not finish","state",state,"message",status.getString("message")));return;}handler.postDelayed(this::waitResult,200);}
  void event(JSONObject result){Log.i("PocketAppUpdateIntegration",result.toString());}
  void transferEvent(JSONObject result){Log.i("PocketUpdateTransfer",result.toString());}
  void transferCommand(Intent intent){try{
    if(!getPackageName().endsWith(".test"))throw new SecurityException("Only isolated integration package may map a controlled update URL");
    transferScenario=intent.getStringExtra("transferScenario");transferToken=intent.getStringExtra("transferToken");
    if(transferScenario==null||!transferScenario.matches("cut|pause|ignore-range|bad-range|changed-etag|short-length|oversize|bad-hash|bad-signer|queued-cancel"))throw new IOException("Unknown controlled update scenario");
    commandQueueDrained=false;preparationGuardReached=false;
    manager=AppUpdateManager.get(this);AppSettings.put(this,"updateAutoCheck","false");AppSettings.put(this,"updateWifiOnly","false");AppUpdates.schedule(this);
    final String target="http://127.0.0.1:8765/update-transfer/"+transferScenario;
    manager.transferFactory=official->{if(manager.info==null||!manager.info.url.equals(official))throw new IOException("Fixture refused a different official update identity");return (HttpURLConnection)new URL(target).openConnection();};
    if("transferQueuedPause".equals(action)||"transferQueuedCancel".equals(action)){queuedAdmission(intent,"transferQueuedCancel".equals(action));return;}
    if("transferDelayedPause".equals(action)){delayedPreparation(intent);return;}
    if("transferRecreate".equals(action)){setIntent(new Intent(intent).putExtra("updateAction","transferInspect"));recreate();return;}
    if("transferStart".equals(action)){
      hash=intent.getStringExtra("updateHash");long bytes=intent.getLongExtra("updateBytes",0);if(hash==null||bytes<1024*1024)throw new IOException("Signed transfer fixture must contain at least one MiB");
      JSONObject metadata=J.obj("schema",1,"package","local.pocketchat","version","99.0.0","versionCode",AppUpdateFiles.installed(this)+1,"bytes",bytes,"sha256",hash,"signerSha256",AppUpdatePolicy.SIGNER,"downloadUrl",AppUpdatePolicy.asset("99.0.0"),"abi","arm64-v8a","minSdk",26,"notes","受控真实 HTTP 续传；不实际安装。");
      manager.worker.execute(()->{try{AppUpdates.cancelTransfer(this);manager.generation.incrementAndGet();manager.removeDownload();manager.clearFiles();manager.info=new AppUpdateInfo(metadata);manager.raw=metadata.toString();manager.downloadRequested=false;manager.userPaused=false;manager.received=0;manager.total=bytes;manager.change("available","");manager.downloadNow(false);handler.post(()->{started=SystemClock.elapsedRealtime();waitTransfer(intent);});}catch(Exception error){handler.post(()->transferEvent(J.obj("token",transferToken,"error",error.toString())));}});return;
    }
    started=SystemClock.elapsedRealtime();if("transferResume".equals(action))manager.resume();else if("transferPause".equals(action))manager.pause();waitTransfer(intent);
  }catch(Exception error){transferEvent(J.obj("token",transferToken,"error",error.toString()));}}
  void queuedAdmission(Intent intent,boolean cancel){final String token=transferToken;started=SystemClock.elapsedRealtime();java.util.concurrent.CountDownLatch released=new java.util.concurrent.CountDownLatch(1);
    manager.worker.execute(()->{handler.post(()->{try{
      // This callback runs only once the actual production worker is blocked.
      // Both commands still enter through the real cross-process provider API.
      AppUpdates.call(this,"resume",null);AppUpdates.call(this,cancel?"cancel":"pause",null);
      manager.worker.execute(()->{commandQueueDrained=true;handler.post(()->waitTransfer(intent));});
    }catch(Exception error){transferEvent(J.obj("token",token,"error",error.toString()));}finally{released.countDown();}});
      try{if(!released.await(20,java.util.concurrent.TimeUnit.SECONDS))throw new IOException("Actual queued command handshake timed out");}catch(Exception error){handler.post(()->transferEvent(J.obj("token",token,"error",error.toString())));}
    });
  }
  void delayedPreparation(Intent intent){final String token=transferToken;started=SystemClock.elapsedRealtime();final File actualRoot=manager.root;
    manager.worker.execute(()->{try{java.lang.reflect.Field field=AppUpdateManager.class.getDeclaredField("root");field.setAccessible(true);
      File controlledRoot=new File(actualRoot.getPath()){
        final java.util.concurrent.atomic.AtomicBoolean once=new java.util.concurrent.atomic.AtomicBoolean();
        @Override public long getUsableSpace(){if(once.compareAndSet(false,true)){preparationGuardReached=true;java.util.concurrent.CountDownLatch paused=new java.util.concurrent.CountDownLatch(1);
          handler.post(()->{try{AppUpdates.call(AppUpdateIntegrationActivity.this,"pause",null);}finally{paused.countDown();}});
          try{if(!paused.await(20,java.util.concurrent.TimeUnit.SECONDS))throw new IllegalStateException("Actual preparation ownership handshake timed out");}catch(InterruptedException error){Thread.currentThread().interrupt();throw new IllegalStateException(error);}
        }return actualRoot.getUsableSpace();}
      };
      // The exact same real files are used. Only this test-only filesystem
      // callback pauses preparation before its final ownership/commit check.
      field.set(manager,controlledRoot);handler.post(()->{AppUpdates.call(this,"resume",null);manager.worker.execute(()->{try{field.set(manager,actualRoot);commandQueueDrained=true;handler.post(()->waitTransfer(intent));}catch(Exception error){handler.post(()->transferEvent(J.obj("token",token,"error",error.toString())));}});});
    }catch(Exception error){handler.post(()->transferEvent(J.obj("token",token,"error",error.toString())));}});
  }
  Bundle measuredStatus(){StrictMode.ThreadPolicy previous=StrictMode.getThreadPolicy();
    if(Build.VERSION.SDK_INT>=28)StrictMode.setThreadPolicy(new StrictMode.ThreadPolicy.Builder().detectDiskReads().detectDiskWrites().detectNetwork().penaltyListener(Runnable::run,violation->statusIo++).build());
    long begin=System.nanoTime();try{Bundle b=AppUpdates.call(this,"status",null);statusReads++;maxStatusNs=Math.max(maxStatusNs,System.nanoTime()-begin);return b;}finally{StrictMode.setThreadPolicy(previous);}
  }
  void waitTransfer(Intent intent){try{
    Bundle b=measuredStatus();String state=b.getString("state","");String target=intent.getStringExtra("transferTarget");if(target==null)target="inspect";
    long received=b.getLong("received");if(firstReceived<0)firstReceived=received;
    boolean running;synchronized(manager){running=manager.transferRunning;}
    boolean complete="inspect".equals(target)||target.equals(state)&&(!running||"downloading".equals(target)&&received>=Math.max(1,b.getLong("bytes")/8));
    if("waiting".equals(target)&&received<=0)complete=false;
    if(complete){emitTransferResult(b,running);return;}
    if(SystemClock.elapsedRealtime()-started>90000)throw new IOException("Controlled transfer timed out: "+state+" received="+received+" target="+target+" running="+running);
    handler.postDelayed(()->waitTransfer(intent),200);
  }catch(Exception error){transferEvent(J.obj("token",transferToken,"error",error.toString()));}}
  static String fileHash(File file)throws Exception{MessageDigest digest=MessageDigest.getInstance("SHA-256");try(InputStream in=new FileInputStream(file)){byte[] buffer=new byte[65536];int n;while((n=in.read(buffer))!=-1)digest.update(buffer,0,n);}StringBuilder hex=new StringBuilder();for(byte value:digest.digest())hex.append(String.format(java.util.Locale.ROOT,"%02x",value&255));return hex.toString();}
  void emitTransferResult(Bundle b,boolean running){final String token=transferToken,scenario=transferScenario,command=action;
    final long reads=statusReads,io=statusIo,maxNs=maxStatusNs,pairs=progressPairs;final int renderCount=renders;
    manager.worker.execute(()->{try{
      AppUpdateInfo info=manager.info;File part=new File(manager.root,"transfer-"+info.code+"-"+info.sha+"-"+info.bytes+".part"),meta=new File(part.getPath().replace(".part",".resume"));
      long partialBytes=part.isFile()?part.length():0;String partialSha=partialBytes>0?fileHash(part):"";boolean identity=false;
      if(meta.isFile())try(InputStream in=new FileInputStream(meta)){java.util.Properties p=new java.util.Properties();p.load(in);identity=(info.code+":"+info.sha+":"+info.bytes).equals(p.getProperty("identity"));}
      boolean ready="ready".equals(b.getString("state"));String finalSha="";long finalBytes=0;int apkCount=0;boolean signer=false;
      File[] files=manager.root.listFiles();if(files!=null)for(File file:files)if(file.getName().endsWith(".apk"))apkCount++;
      if(ready){finalBytes=manager.file().length();finalSha=fileHash(manager.file());AppUpdateFiles.archive(this,manager.file(),info.code,info.version);signer=true;}
      JSONObject result=J.obj("token",token,"action",command,"scenario",scenario,"state",b.getString("state"),"message",b.getString("message"),"uri",b.getString("uri",""),"received",b.getLong("received"),"total",b.getLong("total"),"partialBytes",partialBytes,"partialSha",partialSha,"partialIdentity",identity,"finalBytes",finalBytes,"finalSha",finalSha,"finalApks",apkCount,"sameSigner",signer,"running",running,"downloadRequested",b.getBoolean("downloadRequested"),"userPaused",manager.userPaused,"statusReads",reads,"statusMainThreadIo",io,"maxStatusMs",maxNs/1000000.0,"nativeRenders",renderCount,"progressIdentityPairs",pairs,"pid",android.os.Process.myPid());
      result.put("commandQueueDrained",commandQueueDrained);result.put("preparationGuardReached",preparationGuardReached);android.app.job.JobScheduler scheduler=(android.app.job.JobScheduler)getSystemService(JOB_SCHEDULER_SERVICE);result.put("pendingTransferJob",scheduler!=null&&scheduler.getPendingJob(AppUpdates.TRANSFER)!=null);
      handler.post(()->transferEvent(result));
    }catch(Exception error){handler.post(()->transferEvent(J.obj("token",token,"error",error.toString())));}});
  }
  @Override protected void onDestroy(){handler.removeCallbacksAndMessages(null);super.onDestroy();}
}
