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
  long speedFirstReceived=-1,speedLastReceived=-1,speedFirstSampleNanos,speedLastSampleNanos,speedSamplePairs;boolean speedMeasuring;
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
    manager=AppUpdateManager.get(this);manager.setOrigin(0);AppSettings.put(this,"updateAutoCheck","false");AppUpdates.schedule(this);
    if("verifyAccess".equals(action)){try{Bundle status=AppUpdates.call(this,"status",null);Uri uri=Uri.parse(status.getString("uri"));try(InputStream in=getContentResolver().openInputStream(uri);ByteArrayOutputStream out=new ByteArrayOutputStream()){byte[] buf=new byte[4096];int n;while((n=in.read(buf))!=-1)out.write(buf,0,n);if(!AppUpdatePolicy.hash(out.toByteArray()).equals(manager.info.sha))throw new IOException("Provider bytes differ");}
      boolean readOnly=false,traversal=false;try{getContentResolver().openFileDescriptor(uri,"rw");}catch(FileNotFoundException e){readOnly=true;}try{getContentResolver().openFileDescriptor(AppUpdates.uri(this).buildUpon().appendPath("..").appendPath("chat.db").build(),"r");}catch(FileNotFoundException e){traversal=true;}
      event(J.obj("readOnly",readOnly,"traversalRejected",traversal,"sameSigner",true,"installedVersion",AppVersion.name(this),"packageVersion",AppUpdateFiles.installed(this)));
    }catch(Exception e){event(J.obj("error",String.valueOf(e)));}return;}
    try{
      hash=intent.getStringExtra("updateHash");long bytes=intent.getLongExtra("updateBytes",0);if(hash==null||bytes<=0)throw new IOException("Missing synthetic fixture identity");
      JSONObject metadata=J.obj("schema",1,"package","local.pocketchat","version","99.0.0","versionCode",AppUpdateFiles.installed(this)+1,"bytes",bytes,"sha256",hash,"signerSha256",AppUpdatePolicy.SIGNER,"downloadUrl",AppUpdatePolicy.asset("99.0.0"),"abi","arm64-v8a","minSdk",26,"notes","受控安装包；测试不会实际安装。");
      manager.worker.execute(()->{try{manager.removeDownload();manager.clearFiles();manager.info=new AppUpdateInfo(metadata);manager.raw=metadata.toString();File external=new File(getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS),"fixture-"+action+".download");external.delete();String path="good".equals(action)?"/update-apk":"badSigner".equals(action)?"/update-wrong-signer":"badHash".equals(action)?"/update-corrupt":"/update-wait";
        DownloadManager.Request request=new DownloadManager.Request(Uri.parse("http://127.0.0.1:8765"+path)).setDestinationUri(Uri.fromFile(external)).setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE);manager.generation.incrementAndGet();manager.id=manager.downloads.enqueue(request);manager.change("downloading","");if("cancelDuringQuery".equals(action)){cancelDuringQuery();return;}handler.post(()->{started=SystemClock.elapsedRealtime();if("cancel".equals(action))AppUpdates.call(this,"cancel",null);waitResult();});
      }catch(Exception e){handler.post(()->event(J.obj("error",String.valueOf(e))));}});
    }catch(Exception e){event(J.obj("error",String.valueOf(e)));}
  }
  void waitResult(){Bundle status=AppUpdates.call(this,"status",null);String state=status.getString("state");if("ready".equals(state)||"available".equals(state)){event(J.obj("action",action,"state",state,"message",status.getString("message"),"uri",status.getString("uri",""),"downloadId",manager.downloadId()));return;}if(SystemClock.elapsedRealtime()-started>60000){event(J.obj("error","DownloadManager did not finish","state",state,"message",status.getString("message")));return;}handler.postDelayed(this::waitResult,200);}
  void cancelDuringQuery(){final AppUpdateManager.LegacyQuery actualQuery=manager.legacyQuery;final long owned=manager.id,beforeGeneration=manager.generation.get();final AppUpdateInfo release=manager.info;
    final java.util.concurrent.CountDownLatch cancelled=new java.util.concurrent.CountDownLatch(1);final JSONObject evidence=J.obj("action","cancelDuringQuery","actualSystemQuery",false,"ownedDownloadId",owned,"generationBeforeCancel",beforeGeneration,"releaseCode",release.code,"releaseSha",release.sha,"pid",android.os.Process.myPid());
    manager.legacyQuery=queried->{android.database.Cursor cursor=actualQuery.query(queried);try{
      // This is the real system DownloadManager cursor, already materialized.
      // Hold its delivery to production until the real provider cancels its ID.
      if(queried!=owned||cursor==null||!cursor.moveToFirst())throw new IllegalStateException("Actual owned DownloadManager row was not returned");
      int status=cursor.getInt(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS));String uri=cursor.getString(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_URI));long actualId=cursor.getLong(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_ID));
      if(actualId!=owned||!"http://127.0.0.1:8765/update-wait".equals(uri))throw new IllegalStateException("Real query did not describe the controlled legacy request");
      evidence.put("actualSystemQuery",true);evidence.put("cursorClass",cursor.getClass().getName());evidence.put("cursorStatusBeforeCancel",status);evidence.put("systemRowId",actualId);evidence.put("queriedUri",uri);evidence.put("queryHeldAfterReturn",true);cursor.moveToPosition(-1);
      handler.post(()->{try{Bundle result=AppUpdates.call(this,"cancel",null);evidence.put("productionProviderCancel","available".equals(result.getString("state"))&&result.getString("message","").contains("取消"));evidence.put("cancelState",result.getString("state"));evidence.put("generationAfterCancel",manager.generation.get());evidence.put("cancelledDownloadId",manager.downloadId());}catch(Exception error){try{evidence.put("error",error.toString());}catch(JSONException ignored){}}finally{cancelled.countDown();}});
      if(!cancelled.await(20,java.util.concurrent.TimeUnit.SECONDS))throw new IllegalStateException("Actual provider cancellation did not finish while query was held");
      evidence.put("queryReturnedAfterCancel",true);return cursor;
    }catch(Exception error){try{evidence.put("error",error.toString());}catch(JSONException ignored){}if(cursor!=null)cursor.close();throw new IllegalStateException(error);}finally{manager.legacyQuery=actualQuery;}};
    try{manager.pollNow();evidence.put("productionPollDrained",true);
      // cancel() queued actual cleanup while pollNow was blocked. This real
      // worker checkpoint runs after both cursor consumption and that cleanup.
      manager.worker.execute(()->{try{
        manager.pollNow();Bundle status=manager.snapshot();boolean removed;try(android.database.Cursor cursor=actualQuery.query(owned)){removed=cursor==null||!cursor.moveToFirst();}
        android.app.job.JobScheduler jobs=(android.app.job.JobScheduler)getSystemService(JOB_SCHEDULER_SERVICE);
        evidence.put("cleanupWorkerDrained",true);evidence.put("systemRecordRemoved",removed);evidence.put("sameRelease",manager.info==release);evidence.put("finalPid",android.os.Process.myPid());evidence.put("state",status.getString("state"));evidence.put("message",status.getString("message"));evidence.put("uri",status.getString("uri",""));evidence.put("received",status.getLong("received"));evidence.put("downloadId",manager.downloadId());evidence.put("downloadRequested",status.getBoolean("downloadRequested"));evidence.put("pendingTransferJob",jobs!=null&&jobs.getPendingJob(AppUpdates.TRANSFER)!=null);evidence.put("finalFilePresent",manager.file().isFile());
        handler.post(()->event(evidence));
      }catch(Exception error){handler.post(()->event(J.obj("error",error.toString())));}});
    }catch(Exception error){manager.legacyQuery=actualQuery;handler.post(()->event(J.obj("error",error.toString())));}
  }
  void event(JSONObject result){Log.i("PocketAppUpdateIntegration",result.toString());}
  void transferEvent(JSONObject result){Log.i("PocketUpdateTransfer",result.toString());}
  void transferCommand(Intent intent){try{
    if(!getPackageName().endsWith(".test"))throw new SecurityException("Only isolated integration package may map a controlled update URL");
    transferScenario=intent.getStringExtra("transferScenario");transferToken=intent.getStringExtra("transferToken");
    if(transferScenario==null||!transferScenario.matches("cut|pause|ignore-range|bad-range|changed-etag|short-length|oversize|bad-hash|bad-signer|queued-cancel|cancel-restart"))throw new IOException("Unknown controlled update scenario");
    commandQueueDrained=false;preparationGuardReached=false;
    manager=AppUpdateManager.get(this);manager.setOrigin(0);AppSettings.put(this,"updateAutoCheck","false");AppSettings.put(this,"updateWifiOnly","false");AppUpdates.schedule(this);
    final String target="http://127.0.0.1:8765/update-transfer/"+transferScenario;
    manager.transferFactory=official->{if(manager.info==null||!manager.info.url.equals(official))throw new IOException("Fixture refused a different official update identity");return (HttpURLConnection)new URL(target).openConnection();};
    if("transferQueuedPause".equals(action)||"transferQueuedCancel".equals(action)){queuedAdmission(intent,"transferQueuedCancel".equals(action));return;}
    if("transferDelayedPause".equals(action)){delayedPreparation(intent);return;}
    if("transferCancelBeforeCleanup".equals(action)){cancelBeforeCleanup();return;}
    if("transferLocatePause".equals(action)||"transferLocateResume".equals(action)){locateTransferAction("transferLocatePause".equals(action)?"暂停下载":"继续下载",SystemClock.elapsedRealtime()+5000);return;}
    if("transferRecreate".equals(action)){setIntent(new Intent(intent).putExtra("updateAction","transferInspect"));recreate();return;}
    if("transferStart".equals(action)){
      speedFirstReceived=speedLastReceived=-1;speedFirstSampleNanos=speedLastSampleNanos=speedSamplePairs=0;speedMeasuring=false;
      hash=intent.getStringExtra("updateHash");long bytes=intent.getLongExtra("updateBytes",0);if(hash==null||bytes<1024*1024)throw new IOException("Signed transfer fixture must contain at least one MiB");
      JSONObject metadata=J.obj("schema",1,"package","local.pocketchat","version","99.0.0","versionCode",AppUpdateFiles.installed(this)+1,"bytes",bytes,"sha256",hash,"signerSha256",AppUpdatePolicy.SIGNER,"downloadUrl",AppUpdatePolicy.asset("99.0.0"),"abi","arm64-v8a","minSdk",26,"notes","受控真实 HTTP 续传；不实际安装。");
      manager.worker.execute(()->{try{AppUpdates.cancelTransfer(this);manager.generation.incrementAndGet();manager.removeDownload();manager.clearFiles();manager.info=new AppUpdateInfo(metadata);manager.raw=metadata.toString();manager.downloadRequested=false;manager.userPaused=false;manager.received=0;manager.total=bytes;manager.change("available","");manager.downloadNow(false);handler.post(()->{started=SystemClock.elapsedRealtime();waitTransfer(intent);});}catch(Exception error){handler.post(()->transferEvent(J.obj("token",transferToken,"error",error.toString())));}});return;
    }
    started=SystemClock.elapsedRealtime();if("transferResume".equals(action))manager.resume();else if("transferPause".equals(action))manager.pause();waitTransfer(intent);
  }catch(Exception error){transferEvent(J.obj("token",transferToken,"error",error.toString()));}}
  static android.view.View labelledAction(android.view.View view,String label){if(view instanceof TextView&&label.contentEquals(((TextView)view).getText())&&view.isClickable())return view;if(view instanceof android.view.ViewGroup){android.view.ViewGroup group=(android.view.ViewGroup)view;for(int i=0;i<group.getChildCount();i++){android.view.View found=labelledAction(group.getChildAt(i),label);if(found!=null)return found;}}return null;}
  void locateTransferAction(String label,long deadline){try{
    // Read the actual production button after its normal render/layout. Progress
    // keeps refreshing; a usable button does not require the entire UI to idle.
    refresh();android.view.View button=labelledAction(box,label);android.graphics.Rect visible=new android.graphics.Rect();Bundle status=manager.snapshot();String phase=status.getString("state","");
    boolean expected="暂停下载".equals(label)?"downloading".equals(phase)||"waiting".equals(phase):"paused".equals(phase);
    if(expected&&hasWindowFocus()&&button!=null&&button.isAttachedToWindow()&&button.isShown()&&button.isEnabled()&&button.isClickable()&&button.getGlobalVisibleRect(visible)&&visible.width()>0&&visible.height()>0){
      int[] origin=new int[2];button.getRootView().getLocationOnScreen(origin);visible.offset(origin[0],origin[1]);
      transferEvent(J.obj("token",transferToken,"action",action,"scenario",transferScenario,"state",phase,"label",label,"actualNativeView",true,"enabled",button.isEnabled(),"clickable",button.isClickable(),"windowFocused",hasWindowFocus(),"bounds",J.obj("left",visible.left,"top",visible.top,"right",visible.right,"bottom",visible.bottom),"x",visible.centerX(),"y",visible.centerY(),"pid",android.os.Process.myPid()));return;
    }
    if(SystemClock.elapsedRealtime()>deadline)throw new IOException("Actual visible update action not ready: "+label+" phase="+phase);
    handler.postDelayed(()->locateTransferAction(label,deadline),50);
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
  static boolean durableCancel(File prefs,long code)throws Exception{if(!prefs.isFile())return false;boolean discard=false,notRequested=false,available=false,identity=false;
    try(InputStream in=new FileInputStream(prefs)){org.xmlpull.v1.XmlPullParser parser=android.util.Xml.newPullParser();parser.setInput(in,"UTF-8");int type;
      while((type=parser.next())!=org.xmlpull.v1.XmlPullParser.END_DOCUMENT){if(type!=org.xmlpull.v1.XmlPullParser.START_TAG)continue;String name=parser.getAttributeValue(null,"name"),value=parser.getAttributeValue(null,"value");
        if("discardPending".equals(name))discard="true".equals(value);else if("downloadRequested".equals(name))notRequested="false".equals(value);else if("cancelledCode".equals(name))identity=String.valueOf(code).equals(value);else if("state".equals(name))available="available".equals(parser.nextText());
      }
    }return discard&&notRequested&&available&&identity;
  }
  void cancelBeforeCleanup(){final String token=transferToken,scenario=transferScenario;final AppUpdateInfo release=manager.info;
    // Hold the real cleanup queue after a real paused HTTP transfer. The runner
    // kills the actual process only after the cancellation marker is on disk.
    manager.worker.execute(()->{java.util.concurrent.CountDownLatch killedBeforeCleanup=new java.util.concurrent.CountDownLatch(1);handler.post(()->{try{
      Bundle before=manager.snapshot();if(!"paused".equals(before.getString("state"))||manager.transferRunning)throw new IOException("Cancellation death fixture requires the real paused partial");
      AppUpdates.call(this,"cancel",null);Bundle cancelled=manager.snapshot();
      new Thread(()->{try{
        File disk=new File(manager.context.getApplicationInfo().dataDir,"shared_prefs/app-updates.xml");long deadline=SystemClock.elapsedRealtime()+15000;boolean durable=false;
        while(SystemClock.elapsedRealtime()<deadline){try{durable=durableCancel(disk,release.code);}catch(Exception writingInProgress){}if(durable)break;Thread.sleep(25);}
        if(!durable)throw new IOException("Real cancellation marker was not persisted before process death");
        File part=new File(manager.root,"transfer-"+release.code+"-"+release.sha+"-"+release.bytes+".part"),meta=new File(part.getPath().replace(".part",".resume"));long bytes=part.length();if(bytes<=0||!meta.isFile())throw new IOException("Blocked cleanup did not retain the real partial and metadata");
        JSONObject result=J.obj("token",token,"action","transferCancelBeforeCleanup","scenario",scenario,"state",cancelled.getString("state"),"uri",cancelled.getString("uri",""),"downloadRequested",cancelled.getBoolean("downloadRequested"),"userPaused",manager.userPaused,"partialBytes",bytes,"partialSha",fileHash(part),"partialIdentity",meta.isFile(),"discardPending",manager.prefs.getBoolean("discardPending",false),"durableDiscardPending",durable,"cleanupWorkerBlocked",true,"writerWasActive",false,"pid",android.os.Process.myPid());transferEvent(result);
      }catch(Exception error){transferEvent(J.obj("token",token,"error",error.toString()));}},"fixture-cancel-durability").start();
    }catch(Exception error){transferEvent(J.obj("token",token,"error",error.toString()));}});
      try{if(!killedBeforeCleanup.await(120,java.util.concurrent.TimeUnit.SECONDS))handler.post(()->transferEvent(J.obj("token",token,"error","Actual process was not killed before cleanup deadline")));}catch(InterruptedException error){Thread.currentThread().interrupt();}
    });
  }
  Bundle measuredStatus(){StrictMode.ThreadPolicy previous=StrictMode.getThreadPolicy();
    if(Build.VERSION.SDK_INT>=28)StrictMode.setThreadPolicy(new StrictMode.ThreadPolicy.Builder().detectDiskReads().detectDiskWrites().detectNetwork().penaltyListener(Runnable::run,violation->statusIo++).build());
    long begin=System.nanoTime();try{Bundle b=AppUpdates.call(this,"status",null);long sampledAt=System.nanoTime();statusReads++;maxStatusNs=Math.max(maxStatusNs,sampledAt-begin);measureDownload(b,sampledAt);return b;}finally{StrictMode.setThreadPolicy(previous);}
  }
  void measureDownload(Bundle b,long sampledAt){long received=b.getLong("received"),total=b.getLong("total");
    if(!"downloading".equals(b.getString("state"))||total<=0||received>=total){speedMeasuring=false;return;}
    // Measure real provider byte counters against the monotonic clock. A new
    // transfer, restart-from-zero or paused interval starts a separate window.
    if(!speedMeasuring||speedLastReceived<0||received<speedLastReceived){speedFirstReceived=received;speedFirstSampleNanos=sampledAt;speedSamplePairs=0;speedMeasuring=true;}
    else if(received>speedLastReceived)speedSamplePairs++;
    speedLastReceived=received;speedLastSampleNanos=sampledAt;
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
    final long speedBeginBytes=speedFirstReceived,speedEndBytes=speedLastReceived,speedBeginNanos=speedFirstSampleNanos,speedEndNanos=speedLastSampleNanos,speedPairs=speedSamplePairs;
    final String progressText=downloadDetails==null?"":downloadDetails.getText().toString();
    manager.worker.execute(()->{try{
      AppUpdateInfo info=manager.info;File part=new File(manager.root,"transfer-"+info.code+"-"+info.sha+"-"+info.bytes+".part"),meta=new File(part.getPath().replace(".part",".resume"));
      long partialBytes=part.isFile()?part.length():0;String partialSha=partialBytes>0?fileHash(part):"";boolean identity=false;
      if(meta.isFile())try(InputStream in=new FileInputStream(meta)){java.util.Properties p=new java.util.Properties();p.load(in);identity=(info.code+":"+info.sha+":"+info.bytes).equals(p.getProperty("identity"));}
      boolean ready="ready".equals(b.getString("state"));String finalSha="";long finalBytes=0;int apkCount=0;boolean signer=false;
      File[] files=manager.root.listFiles();if(files!=null)for(File file:files)if(file.getName().endsWith(".apk"))apkCount++;
      if(ready){finalBytes=manager.file().length();finalSha=fileHash(manager.file());AppUpdateFiles.archive(this,manager.file(),info.code,info.version);signer=true;}
      JSONObject result=J.obj("token",token,"action",command,"scenario",scenario,"state",b.getString("state"),"message",b.getString("message"),"uri",b.getString("uri",""),"received",b.getLong("received"),"total",b.getLong("total"),"partialBytes",partialBytes,"partialSha",partialSha,"partialIdentity",identity,"finalBytes",finalBytes,"finalSha",finalSha,"finalApks",apkCount,"sameSigner",signer,"running",running,"downloadRequested",b.getBoolean("downloadRequested"),"userPaused",manager.userPaused,"statusReads",reads,"statusMainThreadIo",io,"maxStatusMs",maxNs/1000000.0,"nativeRenders",renderCount,"progressIdentityPairs",pairs,"pid",android.os.Process.myPid());
      result.put("bytesPerSecond",b.getLong("bytesPerSecond"));result.put("remainingSeconds",b.getLong("remainingSeconds",-1));result.put("downloadDetailsText",progressText);
      result.put("speedFirstReceived",speedBeginBytes);result.put("speedLastReceived",speedEndBytes);result.put("speedFirstSampleNanos",speedBeginNanos);result.put("speedLastSampleNanos",speedEndNanos);result.put("speedSamplePairs",speedPairs);
      result.put("speedSampleDeltaBytes",speedBeginBytes>=0?Math.max(0,speedEndBytes-speedBeginBytes):0);result.put("speedSampleDurationMillis",speedBeginBytes>=0?Math.max(0,speedEndNanos-speedBeginNanos)/1000000.0:0);
      result.put("commandQueueDrained",commandQueueDrained);result.put("preparationGuardReached",preparationGuardReached);result.put("discardPending",manager.prefs.getBoolean("discardPending",false));android.app.job.JobScheduler scheduler=(android.app.job.JobScheduler)getSystemService(JOB_SCHEDULER_SERVICE);result.put("pendingTransferJob",scheduler!=null&&scheduler.getPendingJob(AppUpdates.TRANSFER)!=null);
      handler.post(()->transferEvent(result));
    }catch(Exception error){handler.post(()->transferEvent(J.obj("token",token,"error",error.toString())));}});
  }
  @Override protected void onDestroy(){handler.removeCallbacksAndMessages(null);super.onDestroy();}
}
