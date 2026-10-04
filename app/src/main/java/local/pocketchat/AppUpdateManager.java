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

/** One owner in the default process. Android's download service handles background transfer. */
final class AppUpdateManager {
  private static AppUpdateManager instance;
  static synchronized AppUpdateManager get(Context c){if(instance==null)instance=new AppUpdateManager(Profiles.global(c));return instance;}
  final Context context;final SharedPreferences prefs;final DownloadManager downloads;
  final ExecutorService worker=Executors.newSingleThreadExecutor();final AtomicBoolean polling=new AtomicBoolean();
  final AtomicLong generation=new AtomicLong(),verifySerial=new AtomicLong();
  final File root;volatile long id;volatile AppUpdateInfo info;
  String state="idle",message="",raw="";long received,total,verifiedSerial;
  AppUpdateManager(Context c){context=c;prefs=c.getSharedPreferences("app-updates",0);downloads=(DownloadManager)c.getSystemService(Context.DOWNLOAD_SERVICE);root=new File(c.getNoBackupFilesDir(),"app-updates");root.mkdirs();
    raw=prefs.getString("metadata","");try{info=new AppUpdateInfo(new JSONObject(raw));}catch(Exception ignored){raw="";}
    id=prefs.getLong("downloadId",-1);state=prefs.getString("state","idle");message=prefs.getString("message","");
    if(info!=null&&info.code<=AppUpdateFiles.installed(c)){removeDownload();clearFiles();info=null;raw="";state="idle";message="";save();}
    if("checking".equals(state)||"verifying".equals(state))state=id>0?"downloading":info==null?"idle":"available";
    if("ready".equals(state)&&!file().isFile())state=info==null?"idle":"available";
  }
  File file(){return new File(root,info==null?"missing.apk":"update-"+info.code+"-"+info.sha+".apk");}
  long downloadId(){return id;}
  synchronized Bundle snapshot(){Bundle b=new Bundle();b.putString("state",state);b.putString("message",message);b.putLong("received",received);b.putLong("total",total);b.putLong("verifiedSerial",verifiedSerial);b.putLong("checkedAt",prefs.getLong("checkedAt",0));b.putBoolean("autoCheck",AppSettings.bool(context,"updateAutoCheck",true));b.putBoolean("autoDownload",AppSettings.bool(context,"updateAutoDownload",false));b.putBoolean("wifiOnly",AppSettings.bool(context,"updateWifiOnly",true));
    if(info!=null){b.putString("version",info.version);b.putString("notes",info.notes);b.putLong("bytes",info.bytes);b.putLong("code",info.code);if("ready".equals(state))b.putString("uri",AppUpdates.uri(context).buildUpon().appendPath(file().getName()).build().toString());}return b;}
  synchronized void change(String next,String detail){state=next;message=detail;save();}
  static String readable(Exception error,String fallback){String text=error.getMessage();return text!=null&&text.matches("(?s).*[\\u4e00-\\u9fff].*")?text:fallback;}
  synchronized void save(){prefs.edit().putString("state",state).putString("message",message).putString("metadata",raw).putLong("downloadId",id).apply();String label=info==null?"当前版本 "+AppVersion.name(context):"ready".equals(state)?"新版 "+info.version+" 已下载":"downloading".equals(state)?"正在下载 "+info.version:"可更新至 "+info.version;if(!label.equals(AppSettings.get(context,"updateLabel","")))AppSettings.put(context,"updateLabel",label);}
  void check(boolean automatic,Runnable done){worker.execute(()->{try{checkNow(automatic);}finally{if(done!=null)done.run();}});}
  void checkNow(boolean automatic){
    if(automatic&&!AppSettings.bool(context,"updateAutoCheck",true))return;
    long now=System.currentTimeMillis(),interval=prefs.getLong("checkedAt",0)>=prefs.getLong("attemptedAt",0)?AppUpdatePolicy.DAY:6L*60*60*1000;
    if(automatic&&!AppUpdatePolicy.due(now,prefs.getLong("attemptedAt",0),interval)){pollNow();return;}
    if(id>0||"verifying".equals(state)){pollNow();return;}
    String previous=state;change("checking","正在检查更新");prefs.edit().putLong("attemptedAt",now).apply();
    try{
      String text=readFeed();JSONObject json=new JSONObject(text);AppUpdateInfo candidate=new AppUpdateInfo(json);
      boolean supported=java.util.Arrays.asList(Build.SUPPORTED_ABIS).contains("arm64-v8a")&&Build.VERSION.SDK_INT>=candidate.minSdk;
      if(!supported)throw new IOException("暂无适合这台设备的更新安装包");
      if(info!=null&&(candidate.code<info.code||candidate.code==info.code&&!candidate.sha.equals(info.sha)))throw new IOException("发布信息暂未同步，请稍后重新检查");
      long installed=AppUpdateFiles.installed(context);if(candidate.code<=installed){info=null;raw="";clearFiles();change("idle","已是最新版本");}
      else{
        boolean same=info!=null&&info.code==candidate.code&&info.sha.equals(candidate.sha);
        if(!same)clearFiles();info=candidate;raw=json.toString();change(same&&"ready".equals(previous)?"ready":"available","");
        if(prefs.getLong("notifiedCode",0)!=candidate.code){notice("发现新版本 "+candidate.version,"查看更新内容，安装时间由你决定");prefs.edit().putLong("notifiedCode",candidate.code).apply();}
        if(automatic&&AppSettings.bool(context,"updateAutoDownload",false)&&prefs.getLong("cancelledCode",0)!=candidate.code&&!"ready".equals(state))downloadNow(true);
      }
      prefs.edit().putLong("checkedAt",now).apply();
    }catch(Exception error){change(info==null?"error":"ready".equals(previous)?"ready":"available",readable(error,"暂时无法检查更新，请检查手机网络或 VPN 后重试"));}
  }
  String readFeed()throws IOException {
    String url=AppUpdatePolicy.FEED;for(int redirects=0;redirects<4;redirects++){
      if(!AppUpdatePolicy.feedRedirect(url))throw new IOException("更新地址无效");
      HttpURLConnection connection=(HttpURLConnection)new URL(url).openConnection();connection.setConnectTimeout(15000);connection.setReadTimeout(15000);connection.setInstanceFollowRedirects(false);connection.setUseCaches(false);connection.setRequestProperty("Accept","application/json");connection.setRequestProperty("User-Agent","PocketChat-update/"+AppVersion.name(context));
      try{int code=connection.getResponseCode();if(code>=300&&code<400){String location=connection.getHeaderField("Location");if(location==null)throw new IOException("更新服务器响应异常");url=new URL(new URL(url),location).toString();continue;}if(code!=200)throw new IOException("暂时无法获取更新（"+code+"），请稍后重试");
        try(InputStream in=connection.getInputStream();ByteArrayOutputStream out=new ByteArrayOutputStream()){byte[] buffer=new byte[4096];int size;while((size=in.read(buffer))!=-1){if(out.size()+size>65536)throw new IOException("更新信息过大");out.write(buffer,0,size);}return out.toString(StandardCharsets.UTF_8.name());}
      }finally{connection.disconnect();}
    }throw new IOException("更新服务器跳转次数过多");
  }
  void download(){worker.execute(()->downloadNow(false));}
  void downloadNow(boolean automatic){
    if(info==null||info.code<=AppUpdateFiles.installed(context)||id>0||"ready".equals(state))return;
    try{
      File external=context.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS);if(external==null)throw new IOException("下载目录暂时不可用");File folder=new File(external,"app-updates");if(!folder.isDirectory()&&!folder.mkdirs())throw new IOException("无法创建更新下载目录");
      if(folder.getUsableSpace()<info.bytes*2+32L*1024*1024||root.getUsableSpace()<info.bytes+32L*1024*1024)throw new IOException("存储空间不足，请至少留出 "+(info.bytes*2/1024/1024+32)+" MB 后重试");
      clearFiles();File target=new File(folder,"update-"+info.code+".download");if(target.exists()&&!target.delete())throw new IOException("旧下载文件无法清理，请重试");
      DownloadManager.Request request=new DownloadManager.Request(Uri.parse(info.url)).setTitle("元婴期院士 "+info.version).setDescription("下载完成后，在应用更新页确认安装").setMimeType("application/octet-stream").setDestinationUri(Uri.fromFile(target)).setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE).setAllowedOverRoaming(false);
      boolean wifi=automatic||AppSettings.bool(context,"updateWifiOnly",true);request.setAllowedNetworkTypes(wifi?DownloadManager.Request.NETWORK_WIFI:DownloadManager.Request.NETWORK_WIFI|DownloadManager.Request.NETWORK_MOBILE);request.setAllowedOverMetered(!wifi);
      generation.incrementAndGet();id=downloads.enqueue(request);received=0;total=info.bytes;prefs.edit().putString("external",target.getAbsolutePath()).putLong("cancelledCode",0).apply();change("downloading",wifi?"等待 Wi-Fi，连接后自动下载":"正在下载，可继续使用聊天");
    }catch(Exception error){change("available",readable(error,"下载未能开始，请稍后重试"));}
  }
  void cancel(){generation.incrementAndGet();long owned=id;if(owned>0)downloads.remove(owned);worker.execute(()->{if(info!=null)prefs.edit().putLong("cancelledCode",info.code).apply();removeDownload();clearFiles();change(info==null?"idle":"available","下载已取消，可以随时重新下载");});}
  void refresh(Runnable done){if(!polling.compareAndSet(false,true)){if(done!=null)done.run();return;}worker.execute(()->{try{pollNow();}finally{polling.set(false);if(done!=null)done.run();}});}
  void pollNow(){if(id<=0||info==null)return;try(Cursor cursor=downloads.query(new DownloadManager.Query().setFilterById(id))){
    if(cursor==null||!cursor.moveToFirst()){id=-1;change("available","下载记录已移除，请重新下载");return;}
    int status=cursor.getInt(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS));received=cursor.getLong(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_BYTES_DOWNLOADED_SO_FAR));total=info.bytes;
    if(status==DownloadManager.STATUS_SUCCESSFUL){finalizeDownload();return;}
    if(status==DownloadManager.STATUS_FAILED){int reason=cursor.getInt(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_REASON));removeDownload();change("available",reason==DownloadManager.ERROR_INSUFFICIENT_SPACE?"存储空间不足，请清理后重试":"下载失败，请检查网络后重新下载");return;}
    int reason=cursor.getInt(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_REASON));change("downloading",status==DownloadManager.STATUS_PENDING?"等待下载开始":status==DownloadManager.STATUS_PAUSED?(reason==DownloadManager.PAUSED_WAITING_FOR_NETWORK||reason==DownloadManager.PAUSED_QUEUED_FOR_WIFI?"等待可用网络，连接后继续下载":"下载暂停，系统会自动重试"):"正在下载，可继续使用聊天");
  }catch(Exception e){change("downloading","暂时无法读取下载进度，稍后会再次检查");}}
  void finalizeDownload(){long serial=generation.get();change("verifying","下载完成，正在核验安装包");File partial=new File(root,"verified.part");try{
    if(info==null||info.code<=AppUpdateFiles.installed(context))throw new IOException("当前应用已更新，无需重复安装");
    try(ParcelFileDescriptor descriptor=downloads.openDownloadedFile(id);InputStream in=new ParcelFileDescriptor.AutoCloseInputStream(descriptor)){AppUpdatePolicy.copyVerified(in,partial,info.bytes,info.sha,()->generation.get()!=serial);}
    AppUpdateFiles.archive(context,partial,info.code,info.version);if(generation.get()!=serial)throw new IOException("下载已取消");File target=file();if(target.exists()&&!target.delete()||!partial.renameTo(target))throw new IOException("无法保存更新安装包，请重试");
    removeDownload();change("ready","");notice("新版 "+info.version+" 已下载","点击查看更新并确认安装");
  }catch(Exception error){partial.delete();removeDownload();change("available",readable(error,"安装包核验失败，请重新下载"));}}
  long verify(){long request=verifySerial.incrementAndGet();worker.execute(()->{if(info==null)return;change("verifying","正在核验安装包");File temp=new File(root,"install-check.part");try{
    if(info.code<=AppUpdateFiles.installed(context))throw new IOException("当前应用已更新，无需重复安装");
    try(InputStream in=new FileInputStream(file())){AppUpdatePolicy.copyVerified(in,temp,info.bytes,info.sha,()->verifySerial.get()!=request);}
    AppUpdateFiles.archive(context,temp,info.code,info.version);temp.delete();synchronized(this){verifiedSerial=request;change("ready","");}
  }catch(Exception error){temp.delete();clearFiles();change("available",readable(error,"安装包核验失败，请重新下载"));}});return request;}
  void settings(Bundle extras){if(extras==null)return;for(String key:new String[]{"autoCheck","autoDownload","wifiOnly"})if(extras.containsKey(key))AppSettings.put(context,"autoCheck".equals(key)?"updateAutoCheck":"autoDownload".equals(key)?"updateAutoDownload":"updateWifiOnly",String.valueOf(extras.getBoolean(key)));AppUpdates.schedule(context);if(extras.containsKey("autoDownload")&&extras.getBoolean("autoDownload")&&AppSettings.bool(context,"updateAutoCheck",true))worker.execute(()->{prefs.edit().putLong("cancelledCode",0).apply();downloadNow(true);});}
  void removeDownload(){long owned=id;id=-1;if(owned>0)try{downloads.remove(owned);}catch(Exception ignored){}String external=prefs.getString("external","");if(!external.isEmpty())try{File base=context.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS);File file=new File(external).getCanonicalFile();if(base!=null&&new File(base,"app-updates").getCanonicalFile().equals(file.getParentFile()))file.delete();}catch(Exception ignored){}prefs.edit().remove("external").putLong("downloadId",-1).apply();}
  void clearFiles(){File[] files=root.listFiles();if(files!=null)for(File file:files)if(file.isFile())file.delete();}
  void notice(String title,String detail){if(Build.VERSION.SDK_INT>=33&&context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED)return;NotificationManager nm=(NotificationManager)context.getSystemService(Context.NOTIFICATION_SERVICE);if(nm==null)return;nm.createNotificationChannel(new NotificationChannel("app-updates","应用更新",NotificationManager.IMPORTANCE_LOW));PendingIntent open=PendingIntent.getActivity(context,4102,new Intent(context,AppUpdateActivity.class),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);nm.notify(4102,new Notification.Builder(context,"app-updates").setSmallIcon(android.R.drawable.stat_sys_download_done).setContentTitle(title).setContentText(detail).setContentIntent(open).setAutoCancel(true).setOnlyAlertOnce(true).build());}
}
