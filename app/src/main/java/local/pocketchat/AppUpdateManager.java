package local.pocketchat;

import android.Manifest;
import android.app.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.net.Uri;
import android.os.*;
import org.json.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/** One owner in the default process. Release-bound partial files survive jobs and process restarts. */
final class AppUpdateManager {
  interface LegacyQuery {Cursor query(long owned);}
  private static AppUpdateManager instance;
  static synchronized AppUpdateManager get(Context c){if(instance==null)instance=new AppUpdateManager(Profiles.global(c));return instance;}
  static ExecutorService backgroundExecutor(String name){return Executors.newSingleThreadExecutor(task->new Thread(()->{android.os.Process.setThreadPriority(android.os.Process.THREAD_PRIORITY_BACKGROUND);task.run();},name));}
  final Context context;final SharedPreferences prefs;final DownloadManager downloads;
  volatile LegacyQuery legacyQuery;
  final ExecutorService worker=backgroundExecutor("app-update-status"),transferWorker=backgroundExecutor("app-update-transfer");final AtomicBoolean polling=new AtomicBoolean();
  final AtomicLong generation=new AtomicLong(),verifySerial=new AtomicLong();
  final File root;volatile long id;volatile AppUpdateInfo info;
  volatile AppUpdateInfo latestInfo;volatile ReleaseNotes latestNotes=ReleaseNotes.legacy("");long latestRevision,latestCheckedAt;
  String state="idle",message="",raw="";long received,total,verifiedSerial,bytesPerSecond,packageStoredBytes;
  volatile AppUpdateTransfer transfer;volatile AppUpdateTransfer.ConnectionFactory transferFactory=AppUpdateTransfer.OFFICIAL;volatile AppUpdateRoute.Opener routeOpener=AppUpdateRoute.OFFICIAL;
  boolean transferRunning,downloadRequested,userPaused,discardAfterTransfer;java.util.function.BooleanSupplier transferOwner;
  AppUpdateManager(Context c){context=c;prefs=c.getSharedPreferences("app-updates",0);downloads=(DownloadManager)c.getSystemService(Context.DOWNLOAD_SERVICE);legacyQuery=owned->downloads.query(new DownloadManager.Query().setFilterById(owned));root=new File(c.getNoBackupFilesDir(),"app-updates");root.mkdirs();
    raw=prefs.getString("metadata","");try{info=new AppUpdateInfo(new JSONObject(raw));}catch(Exception ignored){raw="";}
    String latest=prefs.getString("latestMetadata",raw);try{latestInfo=new AppUpdateInfo(new JSONObject(latest));latestCheckedAt=prefs.getLong("latestCheckedAt",prefs.getLong("checkedAt",0));final AppUpdateInfo restored=latestInfo;worker.execute(()->{ReleaseNotes notes=ReleaseNotes.parse(restored.notes,restored.technicalDetails,restored.userNotes);synchronized(this){if(latestInfo==restored){latestNotes=notes;latestRevision++;}}});if(!prefs.contains("latestMetadata"))prefs.edit().putString("latestMetadata",latest).putLong("latestCheckedAt",latestCheckedAt).apply();}catch(Exception ignored){/* Descriptive cache never grants download/install eligibility. */}
    id=prefs.getLong("downloadId",-1);state=prefs.getString("state","idle");message=prefs.getString("message","");downloadRequested=prefs.getBoolean("downloadRequested",false);userPaused=prefs.getBoolean("userPaused",false);
    // Cleanup and its final status are persisted separately. Recheck an
    // interrupted deletion even if death followed the cleanup-marker write.
    if("deleting".equals(state))prefs.edit().putBoolean("discardPending",true).putBoolean("packageDeletePending",true).apply();
    boolean deleting=prefs.getBoolean("packageDeletePending",false);
    if(prefs.getBoolean("discardPending",false))try{clearCancelledFiles();if(deleting){state=info==null?"idle":"available";message="安装包已删除，可以随时重新下载";save();}}catch(IOException error){downloadRequested=false;userPaused=false;state=info==null?"idle":"available";message=deleting?"安装包暂未能完全删除，请重试":error.getMessage();save();}
    if(info!=null&&info.code<=AppUpdateFiles.installed(c)){removeDownload();clearFiles();info=null;raw="";downloadRequested=false;userPaused=false;state="idle";message="";save();}
    if("checking".equals(state)||"verifying".equals(state))state=id>0?"downloading":downloadRequested?(userPaused?"paused":"waiting"):"verifying".equals(state)&&info!=null&&file().isFile()&&file().length()==info.bytes?"ready":info==null?"idle":"available";
    if("ready".equals(state)&&!file().isFile()){state=info==null?"idle":"available";downloadRequested=false;}
    if(info!=null){total=info.bytes;if("ready".equals(state))received=info.bytes;}
    if(info!=null&&id<=0&&downloadRequested&&!"ready".equals(state)){try{AppUpdateTransfer existing=newTransfer(null);received=existing.received();total=info.bytes;}catch(IOException ignored){}state=userPaused?"paused":"waiting";message=userPaused?"下载已暂停，已保留进度":"等待可用网络，连接后继续下载";if(!userPaused)AppUpdates.scheduleTransfer(context,wifiOnly(),0);}refreshStoredBytes();
  }
  File file(){return new File(root,info==null?"missing.apk":"update-"+info.code+"-"+info.sha+".apk");}
  long downloadId(){return id;}
  synchronized Bundle snapshot(){Bundle b=new Bundle();b.putInt("originSlot",prefs.getInt("originSlot",-1));b.putInt("routeSlot",prefs.getInt("routeSlot",-1));b.putString("sourceType",prefs.getString("routeSource",""));b.putString("state",state);b.putString("message",message);b.putLong("received",received);b.putLong("total",total);b.putLong("bytesPerSecond",bytesPerSecond);b.putLong("packageStoredBytes",packageStoredBytes);b.putBoolean("packageDeleteRetry",prefs.getBoolean("packageDeletePending",false)&&!"deleting".equals(state));b.putLong("remainingSeconds",bytesPerSecond>0&&total>received?(total-received+bytesPerSecond-1)/bytesPerSecond:-1);b.putBoolean("canResume",info!=null&&received>0&&!"ready".equals(state));b.putBoolean("downloadRequested",downloadRequested);b.putLong("verifiedSerial",verifiedSerial);b.putLong("verifyRequestedSerial",verifySerial.get());b.putLong("checkedAt",prefs.getLong("checkedAt",0));b.putBoolean("autoCheck",AppSettings.bool(context,"updateAutoCheck",true));b.putBoolean("autoDownload",AppSettings.bool(context,"updateAutoDownload",false));b.putBoolean("wifiOnly",AppSettings.bool(context,"updateWifiOnly",true));
    if(latestInfo!=null){b.putString("latestVersion",latestInfo.version);b.putLong("latestCode",latestInfo.code);b.putLong("latestCheckedAt",latestCheckedAt);b.putLong("latestRevision",latestRevision);}
    if(info!=null){b.putString("version",info.version);b.putString("notes",info.notes);b.putLong("bytes",info.bytes);b.putLong("code",info.code);b.putString("packageUri",packageUri());if("ready".equals(state))b.putString("uri",packageUri());}return b;}
  void rememberLatest(AppUpdateInfo candidate,String json,long checked){ReleaseNotes notes=ReleaseNotes.parse(candidate.notes,candidate.technicalDetails,candidate.userNotes);synchronized(this){latestInfo=candidate;latestNotes=notes;latestCheckedAt=checked;latestRevision++;prefs.edit().putString("latestMetadata",json).putLong("latestCheckedAt",checked).apply();}}
  String packageUri(){return AppUpdates.uri(context).buildUpon().appendPath(file().getName()).build().toString();}
  synchronized void refreshStoredBytes(){File apk=file();long bytes=apk.isFile()?apk.length():0;if(info!=null){File part=new File(root,"transfer-"+info.code+"-"+info.sha+"-"+info.bytes+".part");if(part.isFile())bytes+=part.length();}packageStoredBytes=bytes;}
  synchronized void change(String next,String detail){state=next;message=detail;save();}
  static String readable(Exception error,String fallback){String text=error.getMessage();return text!=null&&text.matches("(?s).*[\\u4e00-\\u9fff].*")?text:fallback;}
  synchronized void save(){if(!state.equals(prefs.getString("state",""))||!message.equals(prefs.getString("message",""))||!raw.equals(prefs.getString("metadata",""))||id!=prefs.getLong("downloadId",-1)||downloadRequested!=prefs.getBoolean("downloadRequested",false)||userPaused!=prefs.getBoolean("userPaused",false))prefs.edit().putString("state",state).putString("message",message).putString("metadata",raw).putLong("downloadId",id).putBoolean("downloadRequested",downloadRequested).putBoolean("userPaused",userPaused).apply();String label=info==null?"当前版本 "+AppVersion.name(context):"ready".equals(state)?"新版 "+info.version+" 已下载":"downloading".equals(state)?"正在下载 "+info.version:"可更新至 "+info.version;if(!label.equals(AppSettings.get(context,"updateLabel","")))AppSettings.put(context,"updateLabel",label);}
  void rememberOrigin(int slot){if(AppUpdates.validSlot(slot))worker.execute(()->setOrigin(slot));}
  void setOrigin(int slot){if(AppUpdates.validSlot(slot))prefs.edit().putInt("originSlot",slot).apply();}
  void check(boolean automatic,Runnable done){check(automatic,-1,done);}
  void check(boolean automatic,int origin,Runnable done){worker.execute(()->{try{setOrigin(origin);checkNow(automatic);}finally{if(done!=null)done.run();}});}
  void checkNow(boolean automatic){
    if(automatic&&!AppSettings.bool(context,"updateAutoCheck",true))return;
    long now=System.currentTimeMillis(),interval=prefs.getLong("checkedAt",0)>=prefs.getLong("attemptedAt",0)?AppUpdatePolicy.DAY:6L*60*60*1000;
    if(automatic&&!AppUpdatePolicy.due(now,prefs.getLong("attemptedAt",0),interval)){pollNow();return;}
    String previous;synchronized(this){if(id>0||downloadRequested||transferRunning||"verifying".equals(state)||"deleting".equals(state))previous=null;else{previous=state;change("checking","正在检查更新");prefs.edit().putLong("attemptedAt",now).apply();}}
    if(previous==null){pollNow();return;}
    try{
      String text=readFeed();JSONObject json=new JSONObject(text);AppUpdateInfo candidate=new AppUpdateInfo(json);
      boolean supported=java.util.Arrays.asList(Build.SUPPORTED_ABIS).contains("arm64-v8a")&&Build.VERSION.SDK_INT>=candidate.minSdk;
      if(!supported)throw new IOException("暂无适合这台设备的更新安装包");
      if(info!=null&&(candidate.code<info.code||candidate.code==info.code&&(!candidate.sha.equals(info.sha)||candidate.bytes!=info.bytes)))throw new IOException("发布信息暂未同步，请稍后重新检查");
      rememberLatest(candidate,json.toString(),now);
      long installed=AppUpdateFiles.installed(context);if(candidate.code<=installed){info=null;raw="";clearFiles();change("idle","已是最新版本");}
      else{
        boolean same=info!=null&&info.code==candidate.code&&info.sha.equals(candidate.sha)&&info.bytes==candidate.bytes;
        if(!same){clearFiles();forgetScope();}info=candidate;raw=json.toString();change(same&&"ready".equals(previous)?"ready":"available","");
        if(prefs.getLong("notifiedCode",0)!=candidate.code){/* Update availability stays in the settings label and update page. */prefs.edit().putLong("notifiedCode",candidate.code).apply();}
        if(automatic&&AppSettings.bool(context,"updateAutoDownload",false)&&prefs.getLong("cancelledCode",0)!=candidate.code&&!"ready".equals(state))downloadNow(true);
      }
      prefs.edit().putLong("checkedAt",now).apply();
    }catch(Exception error){change(info==null?"error":"ready".equals(previous)?"ready":"available",readable(error,"暂时无法检查更新，请检查所选环境的网络后重试"));}
  }
  AppUpdateRoute.Scope savedScope(AppUpdateInfo release)throws IOException {if(release==null||!(release.code+":"+release.sha+":"+release.bytes).equals(prefs.getString("routeIdentity","")))return null;return new AppUpdateRoute.Scope(prefs.getInt("routeSlot",-1),prefs.getInt("routeGeneration",-1),prefs.getString("routeSource",""));}
  AppUpdateRoute.Selection selection(AppUpdateInfo release)throws IOException {AppUpdateRoute.Scope scope=savedScope(release);int slot=scope==null?prefs.getInt("originSlot",-1):scope.slot;if(!AppUpdates.validSlot(slot))throw new AppUpdateRoute.Unavailable("请从正在使用的环境打开应用更新");return AppUpdateRoute.select(context,slot,scope);}
  void saveScope(AppUpdateInfo release,AppUpdateRoute.Scope scope){prefs.edit().putString("routeIdentity",release.code+":"+release.sha+":"+release.bytes).putInt("routeSlot",scope.slot).putInt("routeGeneration",scope.generation).putString("routeSource",scope.source).apply();}
  void forgetScope(){prefs.edit().remove("routeIdentity").remove("routeSlot").remove("routeGeneration").remove("routeSource").apply();}
  AppUpdateTransfer.ConnectionFactory connectionFactory(AppUpdateRoute.Selection route,String origin)throws IOException {if(AppUpdateRoute.INTERNAL.equals(route.scope.source)&&route.lease==null)throw new AppUpdateRoute.Unavailable("恢复环境网络后继续下载");return new AppUpdateRoute.Factory(context,route,routeOpener,transferFactory,origin);}
  String readFeed()throws IOException {
    AppUpdateTransfer.ConnectionFactory factory=connectionFactory(selection(null),AppUpdatePolicy.FEED);try{
    String url=AppUpdatePolicy.FEED;for(int redirects=0;redirects<4;redirects++){
      if(!AppUpdatePolicy.feedRedirect(url))throw new IOException("更新地址无效");
      HttpURLConnection connection=factory.open(url);connection.setConnectTimeout(15000);connection.setReadTimeout(15000);connection.setInstanceFollowRedirects(false);connection.setUseCaches(false);connection.setRequestProperty("Accept","application/json");connection.setRequestProperty("User-Agent","PocketChat-update/"+AppVersion.name(context));
      try{int code=connection.getResponseCode();factory.check();if(code>=300&&code<400){String location=connection.getHeaderField("Location");if(location==null)throw new IOException("更新服务器响应异常");url=new URL(new URL(url),location).toString();continue;}if(code!=200)throw new IOException("暂时无法获取更新（"+code+"），请稍后重试");
        try(InputStream in=connection.getInputStream();ByteArrayOutputStream out=new ByteArrayOutputStream()){byte[] buffer=new byte[4096];int size;while((size=in.read(buffer))!=-1){factory.check();if(out.size()+size>65536)throw new IOException("更新信息过大");out.write(buffer,0,size);}return out.toString(StandardCharsets.UTF_8.name());}
      }finally{connection.disconnect();}
    }throw new IOException("更新服务器跳转次数过多");
    }catch(IOException error){factory.check();throw error;}finally{factory.finished();}
  }
  boolean wifiOnly(){return prefs.getBoolean("transferAutomatic",false)||prefs.getBoolean("transferWifiOnly",AppSettings.bool(context,"updateWifiOnly",true));}
  AppUpdateTransfer newTransfer(AppUpdateTransfer.Listener listener)throws IOException {AppUpdateInfo release=info;if(release==null)throw new IOException("请先检查更新");return new AppUpdateTransfer(root,new AppUpdateTransfer.Request(release.code,release.sha,release.bytes,release.url),transferFactory,listener);}
  void download(){download(-1);}
  void download(int origin){long requestedGeneration=generation.get();worker.execute(()->{if(generation.get()!=requestedGeneration)return;setOrigin(origin);downloadNow(false,requestedGeneration);});}
  void resume(){download();}
  void retry(){download();}
  void downloadNow(boolean automatic){downloadNow(automatic,generation.get());}
  void downloadNow(boolean automatic,long requestedGeneration){final AppUpdateInfo release;
    synchronized(this){if(generation.get()!=requestedGeneration||info==null||info.code<=AppUpdateFiles.installed(context)||id>0||"ready".equals(state)||automatic&&prefs.getLong("cancelledCode",0)==info.code||transferRunning&&(transfer==null||!transfer.cancelled))return;release=info;}
    try{
      synchronized(this){if(generation.get()!=requestedGeneration||info!=release)return;if(prefs.getBoolean("discardPending",false)&&!transferRunning){clearCancelledFiles();discardAfterTransfer=false;}}
      AppUpdateRoute.Selection selected=selection(downloadRequested?release:null);
      AppUpdateTransfer prepared=new AppUpdateTransfer(root,new AppUpdateTransfer.Request(release.code,release.sha,release.bytes,release.url),transferFactory,null);long have=discardAfterTransfer?0:prepared.received();if(root.getUsableSpace()<release.bytes-have+release.bytes+32L*1024*1024)throw new IOException("存储空间不足，请至少留出 "+((release.bytes-have+release.bytes)/1024/1024+32)+" MB 后重试");
      synchronized(this){if(generation.get()!=requestedGeneration||info!=release)return;saveScope(release,selected.scope);boolean originalAutomatic=downloadRequested?prefs.getBoolean("transferAutomatic",automatic):automatic;downloadRequested=true;userPaused=false;received=have;total=release.bytes;bytesPerSecond=0;prefs.edit().putLong("cancelledCode",0).putInt("transferFailures",0).putBoolean("transferAutomatic",originalAutomatic).putBoolean("transferWifiOnly",AppSettings.bool(context,"updateWifiOnly",true)).apply();change("waiting",AppUpdateRoute.INTERNAL.equals(selected.scope.source)&&selected.lease==null?"恢复环境网络后继续下载":selected.message+" · "+(have>0?"已保留进度，等待继续下载":"等待开始下载"));if(!transferRunning)AppUpdates.scheduleTransfer(context,wifiOnly(),0);}
    }catch(Exception error){synchronized(this){if(generation.get()==requestedGeneration&&info==release)change("available",readable(error,"下载未能开始，请稍后重试"));}}
  }
  void pause(){
    synchronized(this){if(info==null||"ready".equals(state))return;generation.incrementAndGet();downloadRequested=true;userPaused=true;bytesPerSecond=0;AppUpdateTransfer current=transfer;if(current!=null){current.cancel();received=current.received();}if(id>0){/* Legacy DownloadManager tasks cannot be paused safely. Leave them owned by Android. */downloadRequested=false;userPaused=false;change("downloading","此下载由 Android 管理，可在系统下载通知中暂停");return;}change("paused","下载已暂停，已保留下载进度");}
    AppUpdates.cancelTransfer(context);
  }
  void cancel(){discard(false);}
  Bundle deletePackage(long code,String expectedUri){synchronized(this){boolean retry=prefs.getBoolean("packageDeletePending",false)&&"available".equals(state);if(info==null||info.code!=code||!packageUri().equals(expectedUri)||!("ready".equals(state)||retry)||transferRunning||downloadRequested||id>0){Bundle result=snapshot();result.putBoolean("deleteAccepted",false);result.putString("deleteError","安装包状态已变化，请重新查看后再删除");return result;}discard(true);Bundle result=snapshot();result.putBoolean("deleteAccepted",true);return result;}}
  void discard(boolean deleting){AppUpdateTransfer current;long owned,serial;AppUpdateInfo release;synchronized(this){serial=generation.incrementAndGet();release=info;if(deleting){verifySerial.incrementAndGet();verifiedSerial=0;}current=transfer;owned=id;id=-1;downloadRequested=false;userPaused=false;forgetScope();discardAfterTransfer=transferRunning;received=0;total=info==null?0:info.bytes;bytesPerSecond=0;prefs.edit().putBoolean("discardPending",true).putBoolean("packageDeletePending",deleting).putLong("cancelledCode",info==null?0:info.code).apply();change(info==null?"idle":deleting?"deleting":"available",deleting?"正在删除安装包":"下载已取消，可以随时重新下载");}if(current!=null)current.cancel();AppUpdates.cancelTransfer(context);if(owned>0)downloads.remove(owned);worker.execute(()->{synchronized(this){removeDownload();if(!transferRunning){try{clearCancelledFiles();discardAfterTransfer=false;if(deleting&&generation.get()==serial&&info==release)change(info==null?"idle":"available","安装包已删除，可以随时重新下载");}catch(IOException error){if(!deleting||generation.get()==serial&&info==release)change(info==null?"idle":"available",deleting?"安装包暂未能完全删除，请重试":error.getMessage());}}save();}});}
  void runTransferJob(Runnable done){runTransferJob(()->false,done);}
  void runTransferJob(java.util.function.BooleanSupplier stopped,Runnable done){worker.execute(()->{
    final long serial;final AppUpdateInfo release;final AppUpdateTransfer current;final AppUpdateRoute.Selection selected;
    synchronized(this){if(stopped.getAsBoolean()||!downloadRequested||userPaused||info==null||id>0||"ready".equals(state)||transferRunning){if(done!=null)done.run();return;}release=info;serial=generation.incrementAndGet();}
    AppUpdateTransfer.ConnectionFactory preparedFactory=null;
    try{selected=selection(release);if(generation.get()!=serial||stopped.getAsBoolean()){if(done!=null)done.run();return;}preparedFactory=connectionFactory(selected,release.url);current=new AppUpdateTransfer(root,new AppUpdateTransfer.Request(release.code,release.sha,release.bytes,release.url),preparedFactory,(have,size,speed)->{synchronized(AppUpdateManager.this){if(generation.get()!=serial||transfer==null||transfer.cancelled)return;received=have;total=size;bytesPerSecond=speed;}});}catch(IOException|RuntimeException error){if(preparedFactory!=null)preparedFactory.finished();synchronized(this){if(generation.get()==serial){if(error instanceof AppUpdateRoute.Unavailable){prefs.edit().putInt("transferFailures",Math.min(6,prefs.getInt("transferFailures",0)+1)).apply();change("waiting",error.getMessage());}else{downloadRequested=false;change("available",readable(error,"无法恢复下载，请重试"));}}}if(done!=null)done.run();synchronized(this){if(generation.get()==serial&&downloadRequested&&!userPaused)AppUpdates.scheduleTransfer(context,wifiOnly(),retryDelay());}return;}
    synchronized(this){if(stopped.getAsBoolean()||generation.get()!=serial||info!=release||!downloadRequested||userPaused||transferRunning){current.factory.finished();if(done!=null)done.run();return;}saveScope(release,selected.scope);transfer=current;transferOwner=stopped;transferRunning=true;received=current.received();total=release.bytes;bytesPerSecond=0;change("downloading",selected.message+" · "+(received>0?"正在续传":"可继续使用聊天"));}
    transferWorker.execute(()->{try{
      current.run(()->generation.get()!=serial||stopped.getAsBoolean());if(generation.get()!=serial||stopped.getAsBoolean())return;
      synchronized(AppUpdateManager.this){if(generation.get()!=serial)return;bytesPerSecond=0;change("verifying","下载完成，正在核验安装包");}
      File verified=new File(root,"verified-"+serial+".part");try{
        try(InputStream in=new FileInputStream(current.partial())){AppUpdatePolicy.copyVerified(in,verified,release.bytes,release.sha,()->generation.get()!=serial);}
        AppUpdateFiles.archive(context,verified,release.code,release.version);
        synchronized(AppUpdateManager.this){if(generation.get()!=serial)throw new AppUpdateTransfer.Stopped();File target=file();if(target.exists()&&!target.delete()||!verified.renameTo(target))throw new IOException("无法保存更新安装包，请重试");current.clear();downloadRequested=false;userPaused=false;received=release.bytes;total=release.bytes;refreshStoredBytes();prefs.edit().putInt("transferFailures",0).apply();change("ready","");}
        notice("新版 "+release.version+" 已下载","点击查看更新并确认安装");
      }catch(AppUpdateTransfer.Stopped pausedTransfer){throw pausedTransfer;}catch(Exception invalid){if(generation.get()!=serial||stopped.getAsBoolean())throw new AppUpdateTransfer.Stopped();current.clear();synchronized(AppUpdateManager.this){if(generation.get()==serial){downloadRequested=false;received=0;change("available",readable(invalid,"安装包核验失败，请重新下载"));}}}finally{verified.delete();}
    }catch(AppUpdateTransfer.Stopped pausedTransfer){/* Pause, OS stop and cancellation already record their own state. */}
    catch(Exception error){synchronized(AppUpdateManager.this){if(generation.get()==serial){bytesPerSecond=0;received=current.received();if(error instanceof AppUpdateTransfer.InvalidResponse){current.clear();received=0;downloadRequested=false;change("available",readable(error,"更新服务器续传响应无效，请重试"));}else{int failures=Math.min(6,prefs.getInt("transferFailures",0)+1);prefs.edit().putInt("transferFailures",failures).apply();change("waiting",readable(error,"网络暂时中断，已保留进度，稍后自动续传"));}}}}
    finally{synchronized(AppUpdateManager.this){if(transfer==current){if(discardAfterTransfer){try{clearCancelledFiles();discardAfterTransfer=false;}catch(IOException error){downloadRequested=false;change("available",error.getMessage());}}transfer=null;transferOwner=null;transferRunning=false;bytesPerSecond=0;}}if(done!=null)done.run();synchronized(AppUpdateManager.this){if(downloadRequested&&!userPaused&&!transferRunning&&!"ready".equals(state))AppUpdates.scheduleTransfer(context,wifiOnly(),retryDelay());}}
    });
  });}
  long retryDelay(){int failures=prefs.getInt("transferFailures",0);return failures==0?0:Math.min(300000L,10000L<<Math.min(5,failures-1));}
  void stopTransferJob(){stopTransferJob(null);}
  void stopTransferJob(java.util.function.BooleanSupplier owner){synchronized(this){if(!transferRunning||owner!=null&&transferOwner!=owner)return;AppUpdateTransfer current=transfer;if(current!=null&&current.cancelled)return;generation.incrementAndGet();if(current!=null){current.cancel();received=current.received();}bytesPerSecond=0;if(downloadRequested&&!userPaused)change("waiting","下载暂时中断，已保留进度，网络恢复后继续下载");}}
  void refresh(Runnable done){if(!polling.compareAndSet(false,true)){if(done!=null)done.run();return;}worker.execute(()->{try{pollNow();}finally{polling.set(false);if(done!=null)done.run();}});}
  void pollNow(){refreshStoredBytes();final long serial,owned;final AppUpdateInfo release;
    synchronized(this){serial=generation.get();owned=id;release=info;if(owned<=0||release==null)return;}
    try(Cursor cursor=legacyQuery.query(owned)){
      if(cursor==null||!cursor.moveToFirst()){synchronized(this){if(generation.get()==serial&&id==owned&&info==release){id=-1;change("available","下载记录已移除，请重新下载");}}return;}
      int status=cursor.getInt(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS)),reason=cursor.getInt(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_REASON));long downloaded=cursor.getLong(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_BYTES_DOWNLOADED_SO_FAR));
      synchronized(this){if(generation.get()!=serial||id!=owned||info!=release)return;received=downloaded;total=release.bytes;
        if(status==DownloadManager.STATUS_FAILED){removeDownload();change("available",reason==DownloadManager.ERROR_INSUFFICIENT_SPACE?"存储空间不足，请清理后重试":"下载失败，请检查网络后重新下载");return;}
        if(status!=DownloadManager.STATUS_SUCCESSFUL){change("downloading",status==DownloadManager.STATUS_PENDING?"等待下载开始":status==DownloadManager.STATUS_PAUSED?(reason==DownloadManager.PAUSED_WAITING_FOR_NETWORK||reason==DownloadManager.PAUSED_QUEUED_FOR_WIFI?"等待可用网络，连接后继续下载":"下载暂停，系统会自动重试"):"正在下载，可继续使用聊天");return;}
      }
      finalizeDownload(serial,owned,release);
    }catch(Exception e){synchronized(this){if(generation.get()==serial&&id==owned&&info==release)change("downloading","暂时无法读取下载进度，稍后会再次检查");}}
  }
  void finalizeDownload(){final long serial,owned;final AppUpdateInfo release;
    synchronized(this){serial=generation.get();owned=id;release=info;}finalizeDownload(serial,owned,release);
  }
  void finalizeDownload(long serial,long owned,AppUpdateInfo release){
    synchronized(this){if(owned<=0||release==null||generation.get()!=serial||id!=owned||info!=release)return;change("verifying","下载完成，正在核验安装包");}
    File partial=new File(root,"verified-legacy-"+serial+".part");try{
      if(release.code<=AppUpdateFiles.installed(context))throw new IOException("当前应用已更新，无需重复安装");
      try(ParcelFileDescriptor descriptor=downloads.openDownloadedFile(owned);InputStream in=new ParcelFileDescriptor.AutoCloseInputStream(descriptor)){AppUpdatePolicy.copyVerified(in,partial,release.bytes,release.sha,()->generation.get()!=serial||id!=owned||info!=release);}
      AppUpdateFiles.archive(context,partial,release.code,release.version);
      synchronized(this){if(generation.get()!=serial||id!=owned||info!=release)return;File target=file();if(target.exists()&&!target.delete()||!partial.renameTo(target))throw new IOException("无法保存更新安装包，请重试");removeDownload();downloadRequested=false;userPaused=false;received=release.bytes;total=release.bytes;refreshStoredBytes();change("ready","");}
      if(generation.get()==serial)notice("新版 "+release.version+" 已下载","点击查看更新并确认安装");
    }catch(Exception error){synchronized(this){if(generation.get()==serial&&id==owned&&info==release){removeDownload();change("available",readable(error,"安装包核验失败，请重新下载"));}}}finally{partial.delete();}
  }
  long verify(){final long request=verifySerial.incrementAndGet(),serial;final AppUpdateInfo release;final File source;
    synchronized(this){serial=generation.get();release=info;source=file();}
    worker.execute(()->{synchronized(this){if(release==null||verifySerial.get()!=request||generation.get()!=serial||info!=release||transferRunning||downloadRequested||!("ready".equals(state)||"verifying".equals(state)))return;change("verifying","正在核验安装包");}
      File temp=new File(root,"install-check-"+request+".part");try{
        if(release.code<=AppUpdateFiles.installed(context))throw new IOException("当前应用已更新，无需重复安装");
        try(InputStream in=new FileInputStream(source)){AppUpdatePolicy.copyVerified(in,temp,release.bytes,release.sha,()->verifySerial.get()!=request||generation.get()!=serial||info!=release);}
        AppUpdateFiles.archive(context,temp,release.code,release.version);
        synchronized(this){if(verifySerial.get()!=request||generation.get()!=serial||info!=release)return;verifiedSerial=request;change("ready","");}
      }catch(Exception error){synchronized(this){if(verifySerial.get()==request&&generation.get()==serial&&info==release){clearFiles();downloadRequested=false;received=0;change("available",readable(error,"安装包核验失败，请重新下载"));}}}finally{temp.delete();}
    });return request;
  }
  void settings(Bundle extras){if(extras==null)return;for(String key:new String[]{"autoCheck","autoDownload","wifiOnly"})if(extras.containsKey(key))AppSettings.put(context,"autoCheck".equals(key)?"updateAutoCheck":"autoDownload".equals(key)?"updateAutoDownload":"updateWifiOnly",String.valueOf(extras.getBoolean(key)));AppUpdates.schedule(context);if(extras.containsKey("wifiOnly")){prefs.edit().putBoolean("transferWifiOnly",extras.getBoolean("wifiOnly")).apply();synchronized(this){if(downloadRequested&&!userPaused){stopTransferJob();AppUpdates.cancelTransfer(context);AppUpdates.scheduleTransfer(context,wifiOnly(),0);}}}if(extras.containsKey("autoDownload")&&extras.getBoolean("autoDownload")&&AppSettings.bool(context,"updateAutoCheck",true)){long requestedGeneration=generation.get();worker.execute(()->downloadNow(true,requestedGeneration));}}
  void removeDownload(){long owned=id;id=-1;if(owned>0)try{downloads.remove(owned);}catch(Exception ignored){}String external=prefs.getString("external","");if(!external.isEmpty())try{File base=context.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS);File file=new File(external).getCanonicalFile();if(base!=null&&new File(base,"app-updates").getCanonicalFile().equals(file.getParentFile()))file.delete();}catch(Exception ignored){}prefs.edit().remove("external").putLong("downloadId",-1).apply();}
  void clearFiles(){File[] files=root.listFiles();if(files!=null)for(File file:files)if(file.isFile())file.delete();refreshStoredBytes();}
  void clearCancelledFiles()throws IOException {clearFiles();File[] files=root.listFiles();if(files==null&&root.exists())throw new IOException("取消下载后的文件暂未清理完成，请重试");if(files!=null)for(File file:files)if(file.isFile())throw new IOException("取消下载后的文件暂未清理完成，请重试");prefs.edit().putBoolean("discardPending",false).putBoolean("packageDeletePending",false).apply();}
  void notice(String title,String detail){if(!QuietNotifications.backgroundCompletionAllowed(context))return;if(Build.VERSION.SDK_INT>=33&&context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED)return;NotificationManager nm=(NotificationManager)context.getSystemService(Context.NOTIFICATION_SERVICE);if(nm==null)return;nm.createNotificationChannel(new NotificationChannel("app-updates","应用更新",NotificationManager.IMPORTANCE_LOW));PendingIntent open=PendingIntent.getActivity(context,4102,new Intent(context,AppUpdateActivity.class).putExtra("originSlot",prefs.getInt("routeSlot",prefs.getInt("originSlot",-1))),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);nm.notify(9002,new Notification.Builder(context,"app-updates").setSmallIcon(android.R.drawable.stat_sys_download_done).setContentTitle(title).setContentText(detail).setContentIntent(open).setAutoCancel(true).setOnlyAlertOnce(true).build());}
}
