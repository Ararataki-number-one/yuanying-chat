package local.pocketchat;

import android.app.*;
import android.content.*;
import android.content.pm.ProviderInfo;
import android.net.Uri;
import android.os.*;
import android.webkit.*;
import java.io.*;
import java.net.URL;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Consumer;
import org.json.*;

/** One-shot website file requests and Chromium downloads, separate from Gecko tasks. */
final class BrowserFiles {
  static final int FIRST_REQUEST=0x5000,LAST_REQUEST=0x7fff,MAX_FILES=64;
  static final AtomicInteger NEXT_REQUEST=new AtomicInteger(FIRST_REQUEST);
  final Activity activity;final Consumer<String> status;final ChromiumRuntime runtime;
  final Handler main=new Handler(Looper.getMainLooper());
  final ExecutorService worker=Executors.newSingleThreadExecutor(task->{Thread t=new Thread(task,"chromium-files");t.setPriority(Thread.MIN_PRIORITY);return t;});
  final ExecutorService metadata=Executors.newSingleThreadExecutor(task->{Thread t=new Thread(task,"chromium-file-list");t.setPriority(Thread.MIN_PRIORITY);return t;});
  final BrowserDownloadStore store;
  Pending pending;long choiceGeneration;volatile boolean destroyed;
  volatile BrowserDownloadTransfer transfer;
  AlertDialog externalDialog,downloadsDialog;
  static final class Pending {
    final WebView owner;final ValueCallback<Uri[]> callback;final int request;final String url;final boolean multiple;
    Pending(WebView owner,ValueCallback<Uri[]> callback,int request,String url,boolean multiple){this.owner=owner;this.callback=callback;this.request=request;this.url=url;this.multiple=multiple;}
  }
  BrowserFiles(Activity activity,Consumer<String> status){this(activity,status,null);}
  BrowserFiles(Activity activity,Consumer<String> status,ChromiumRuntime runtime){this.activity=activity;this.status=status;this.runtime=runtime;store=new BrowserDownloadStore(activity);}
  void message(String text){if(!destroyed)status.accept(text);}
  static void deliver(ValueCallback<Uri[]> callback,Uri[] value){try{callback.onReceiveValue(value);}catch(RuntimeException ignored){}}
  void clear(Pending selected,boolean finish){
    if(pending!=selected||selected==null)return;pending=null;
    if(finish)try{activity.finishActivity(selected.request);}catch(RuntimeException ignored){}
    deliver(selected.callback,null);
  }
  boolean choose(WebView source,ValueCallback<Uri[]> callback,WebChromeClient.FileChooserParams params){
    if(callback==null)return false;
    long generation=++choiceGeneration;clear(pending,true);
    // Cancellation callbacks can synchronously request another picker or close
    // the activity. Never overwrite that newer request with this outer call.
    if(destroyed||generation!=choiceGeneration){deliver(callback,null);return true;}
    String page;int mode;
    try{page=source==null?null:source.getUrl();mode=params==null?-1:params.getMode();}
    catch(RuntimeException unavailable){deliver(callback,null);message("网页文件请求已失效");return true;}
    if(!webAddress(page)){deliver(callback,null);message("请等待网页加载后再选择文件");return true;}
    if(mode!=WebChromeClient.FileChooserParams.MODE_OPEN&&mode!=WebChromeClient.FileChooserParams.MODE_OPEN_MULTIPLE){deliver(callback,null);message("此网页请求的文件选择模式暂不支持");return true;}
    int request=NEXT_REQUEST.getAndIncrement();if(request>LAST_REQUEST){deliver(callback,null);message("本次浏览已打开过多文件选择器，请重新打开浏览器");return true;}
    Pending selected=new Pending(source,callback,request,page,mode==WebChromeClient.FileChooserParams.MODE_OPEN_MULTIPLE);pending=selected;
    try{activity.startActivityForResult(chooserIntent(params),request);}
    catch(ActivityNotFoundException unavailable){clear(selected,false);message("设备没有可用的系统文件选择器");}
    catch(SecurityException denied){clear(selected,false);message("系统未允许打开文件选择器");}
    catch(RuntimeException failure){clear(selected,false);message("文件选择器暂时无法打开");}
    return true;
  }
  static Intent chooserIntent(WebChromeClient.FileChooserParams params){
    LinkedHashSet<String> types=new LinkedHashSet<>();String[] groups=params.getAcceptTypes();
    if(groups!=null)for(String group:groups){if(group==null||group.length()>4096)continue;for(String raw:group.split(",")){String type=raw.trim().toLowerCase(Locale.ROOT);if(type.startsWith("."))type=MimeTypeMap.getSingleton().getMimeTypeFromExtension(type.substring(1));if(type!=null&&type.matches("(?:[a-z0-9.+-]+/(?:[a-z0-9.+-]+|\\*)|\\*/\\*)")&&types.size()<32)types.add(type);}}
    String type=types.size()==1?types.iterator().next():"*/*";
    Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType(type).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
    if(types.size()>1)intent.putExtra(Intent.EXTRA_MIME_TYPES,types.toArray(new String[0]));
    intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE,params.getMode()==WebChromeClient.FileChooserParams.MODE_OPEN_MULTIPLE);return intent;
  }
  boolean result(int request,int result,Intent data){
    if(request<FIRST_REQUEST||request>LAST_REQUEST)return false;
    Pending selected=pending;if(selected==null||selected.request!=request)return true;
    pending=null;
    if(destroyed||result!=Activity.RESULT_OK||data==null){deliver(selected.callback,null);return true;}
    try{if(!Objects.equals(selected.url,selected.owner.getUrl())){deliver(selected.callback,null);message("网页已变化，未交付所选文件");return true;}}
    catch(RuntimeException gone){deliver(selected.callback,null);message("原网页已关闭，未交付所选文件");return true;}
    LinkedHashSet<Uri> uris=new LinkedHashSet<>();
    try{ClipData clip=data.getClipData();
      if(clip!=null){if(clip.getItemCount()>MAX_FILES){deliver(selected.callback,null);message("一次最多选择 64 个文件");return true;}for(int i=0;i<clip.getItemCount();i++){Uri uri=clip.getItemAt(i).getUri();if(uri!=null)uris.add(uri);}}
      if(uris.isEmpty()&&data.getData()!=null)uris.add(data.getData());
    }catch(RuntimeException malformed){deliver(selected.callback,null);message("系统返回的文件信息无效，请重新选择");return true;}
    if(uris.isEmpty()||!selected.multiple&&uris.size()!=1){deliver(selected.callback,null);message("请按网页要求重新选择文件");return true;}
    for(Uri uri:uris)if(!selectable(uri)){deliver(selected.callback,null);message("请选择系统文件选择器中已授权的文件");return true;}
    deliver(selected.callback,uris.toArray(new Uri[0]));return true;
  }
  boolean selectable(Uri uri){
    try{
      if(uri==null||!"content".equals(uri.getScheme())||uri.getAuthority()==null||uri.toString().length()>16384)return false;
      ProviderInfo provider=activity.getPackageManager().resolveContentProvider(uri.getAuthority(),0);
      // A forged picker result must not turn our private config/history providers
      // into an upload. No private provider is part of DocumentsUI's catalog.
      if(provider==null||provider.applicationInfo==null||provider.applicationInfo.uid==android.os.Process.myUid())return false;
      return activity.checkUriPermission(uri,android.os.Process.myPid(),android.os.Process.myUid(),Intent.FLAG_GRANT_READ_URI_PERMISSION)==android.content.pm.PackageManager.PERMISSION_GRANTED;
    }catch(RuntimeException failure){return false;}
  }
  void cancelFor(WebView owner){if(pending!=null&&pending.owner==owner)cancel();}
  void cancel(){++choiceGeneration;clear(pending,true);}
  boolean hasActiveDownload(){return transfer!=null;}
  void cancelActiveDownload(){BrowserDownloadTransfer selected=transfer;if(selected!=null)selected.cancel();}
  static boolean webAddress(String url){try{BrowserDownloadTransfer.address(url);return true;}catch(IOException invalid){return false;}}
  void download(String url,String agent,String disposition,String mime,long size){download(null,url,agent,disposition,mime,size);}
  void download(WebView source,String url,String agent,String disposition,String mime,long size){
    if(destroyed)return;
    if(!webAddress(url)){handoff(source,source==null?"":source.getUrl(),"此临时文件不能直接保存。可在外部浏览器打开原网页后重新下载。");return;}
    if(transfer!=null){message("已有文件正在下载，可在浏览器下载列表中取消");return;}
    try{AppPrefs.requireDownloadNetwork(activity);}catch(IOException restricted){message(restricted.getMessage());return;}
    ChromiumRuntime.DownloadRoute route=runtime==null?null:runtime.downloadRoute();
    if(route==null||!route.current()){message("浏览器连接尚未确认，未开始下载");return;}
    BrowserDownloadTransfer selected=new BrowserDownloadTransfer();transfer=selected;message("开始下载文件…");
    try{worker.execute(()->{
      BrowserDownloadTransfer.Result result=null;ChromiumRouteLease.Handle lease=ChromiumRouteLease.acquireDownload();
      try{
        if(lease==null)throw new IOException("正在应用环境线路，下载尚未开始");
        BrowserDownloadTransfer.Route protectedRoute=new BrowserDownloadTransfer.Route(){
          public boolean current(){if(destroyed||!route.current())return false;try{AppPrefs.requireDownloadNetwork(activity);return true;}catch(IOException restricted){return false;}}
          public java.net.HttpURLConnection open(URL target)throws IOException{return route.open(target);}
        };
        result=selected.fetch(url,agent,disposition,mime,size,activity.getCacheDir(),protectedRoute,target->CookieManager.getInstance().getCookie(target),(received,total)->main.post(()->{if(!destroyed&&transfer==selected)message("正在下载 · "+bytes(received)+(total>0?" / "+bytes(total):""));}));
        String name=BrowserDownloadStore.safeName(URLUtil.guessFileName(result.url,result.disposition,result.mime));
        JSONObject saved=store.save(result,name,()->!destroyed&&!selected.cancelled&&protectedRoute.current());
        main.post(()->{if(transfer==selected){transfer=null;message("已保存 · "+saved.optString("name")+" · 可在浏览器下载列表打开");}});
      }catch(Exception error){String reason=selected.cancelled&&!(error instanceof BrowserDownloadStore.Unconfirmed)?"下载已取消":error.getMessage()==null?"下载失败，未保存文件":error.getMessage();main.post(()->{if(transfer==selected){transfer=null;message(reason);}});}
      finally{try{if(result!=null)result.file.delete();}finally{if(lease!=null)lease.close();}}
    });}catch(RejectedExecutionException closed){transfer=null;message("浏览器已关闭，下载未开始");}
  }
  static String bytes(long value){if(value<1024)return value+" B";return String.format(Locale.ROOT,value<1048576?"%.1f KB":"%.1f MB",value/(value<1048576?1024.0:1048576.0));}
  void handoff(WebView source,String url,String explanation){
    if(!webAddress(url)){message("此临时下载地址无法交给其他浏览器，请在原网页选择可导出的文件");return;}
    String owner=source==null?null:source.getUrl();if(externalDialog!=null)externalDialog.dismiss();
    externalDialog=new AlertDialog.Builder(activity).setTitle("交给外部浏览器").setMessage(explanation+"\n\n外部浏览器使用自己的登录状态和网络设置，不使用本应用的线路；不会转交 Cookie。")
      .setNegativeButton("取消",null).setPositiveButton("打开外部浏览器",(dialog,which)->{
        if(destroyed||source!=null&&!Objects.equals(owner,source.getUrl())){message("原网页已变化，未移交");return;}
        try{
          Intent target=new Intent(Intent.ACTION_VIEW,Uri.parse(url)).addCategory(Intent.CATEGORY_BROWSABLE);
          Intent chooser=Intent.createChooser(target,"选择外部浏览器").putExtra(Intent.EXTRA_EXCLUDE_COMPONENTS,new ComponentName[]{new ComponentName(activity,BrowserActivity.class)});
          activity.startActivity(chooser);message("请选择外部浏览器继续");
        }catch(ActivityNotFoundException unavailable){message("设备没有可用的外部浏览器");}
        catch(SecurityException denied){message("系统未允许打开外部浏览器");}
      }).show();
  }
  void showDownloads(){
    if(destroyed)return;
    try{metadata.execute(()->{JSONArray rows;try{rows=store.rows();}catch(RuntimeException unavailable){main.post(()->message("下载索引暂时无法读取，请稍后重试"));return;}JSONArray saved=rows;main.post(()->{
      if(destroyed)return;if(downloadsDialog!=null)downloadsDialog.dismiss();
      String[] labels=new String[saved.length()];for(int i=0;i<labels.length;i++){JSONObject row=saved.optJSONObject(i);long size=DownloadMetadataValues.bytes(row);labels[i]=row.optString("name")+" · "+(size>=0?bytes(size):row.has("bytes")?bytes(row.optLong("bytes")):"大小未知");}
      AlertDialog.Builder builder=new AlertDialog.Builder(activity).setTitle("浏览器下载");
      if(labels.length==0)builder.setMessage(transfer==null?"暂无已保存文件":"文件正在下载，完成后会显示在这里");
      else builder.setItems(labels,(dialog,index)->open(saved.optJSONObject(index)));
      builder.setPositiveButton("关闭",null);if(transfer!=null)builder.setNegativeButton("取消当前下载",(dialog,which)->{BrowserDownloadTransfer active=transfer;if(active!=null){active.cancel();message("正在取消下载…");}});downloadsDialog=builder.show();
    });});}catch(RejectedExecutionException ignored){}
  }
  void open(JSONObject row){if(row==null)return;try{Uri uri=Uri.parse(row.optString("uri"));if(!"content".equals(uri.getScheme())){message("文件地址不可用");return;}Intent intent=new Intent(Intent.ACTION_VIEW).setDataAndType(uri,row.optString("mime","application/octet-stream")).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);intent.setClipData(ClipData.newRawUri(row.optString("name","文件"),uri));activity.startActivity(intent);}catch(ActivityNotFoundException unavailable){message("没有可打开此类文件的应用，文件仍保留在下载目录");}catch(SecurityException denied){message("文件无法访问，可能已被移除");}}
  void destroy(){destroyed=true;cancel();BrowserDownloadTransfer active=transfer;if(active!=null)active.cancel();worker.shutdownNow();metadata.shutdownNow();main.removeCallbacksAndMessages(null);if(externalDialog!=null)externalDialog.dismiss();if(downloadsDialog!=null)downloadsDialog.dismiss();}
}
