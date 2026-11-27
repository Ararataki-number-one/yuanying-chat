package local.pocketchat;

import android.app.Activity;
import android.content.*;
import android.net.Uri;
import android.webkit.*;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import java.util.*;
import org.json.JSONObject;

/** Only the official website requests files; Gecko owns their loading/upload UI. */
final class Attachments {
  // Separate from browser permissions (0x3000), Chromium files (0x5000),
  // default-browser selection (0x2800) and the fixed download/export codes.
  // Never reuse a code while this process can still receive an old result.
  static final int FIRST_REQUEST=0x1000,LAST_REQUEST=0x27ff;
  private static int nextRequest=FIRST_REQUEST;
  private static synchronized int nextRequestCode(){return nextRequest>LAST_REQUEST?-1:nextRequest++;}
  private static final class Pending {
    ValueCallback<Uri[]> callback;
    final int request;final String url;final long epoch;
    Pending(ValueCallback<Uri[]> callback,int request,String url,long epoch){this.callback=callback;this.request=request;this.url=url;this.epoch=epoch;}
  }
  final MainActivity a;
  // Compatibility references for retired native controls. Never instantiated.
  final LinearLayout rows=null;final HorizontalScrollView view=null;
  private Pending pending;boolean destroyed;
  Attachments(MainActivity activity){a=activity;}

  final class Chrome extends WebChromeClient {
    @Override public void onPermissionRequest(PermissionRequest request){request.deny();}
    @Override public void onGeolocationPermissionsShowPrompt(String origin,GeolocationPermissions.Callback result){result.invoke(origin,false,false);}
    @Override public boolean onShowFileChooser(WebView ignored,ValueCallback<Uri[]> result,FileChooserParams params){
      if(!live()){deliver(result,null);return true;}
      String url=a.remote.getUrl();long epoch=a.session.navigationEpoch;
      if(!MainActivity.chatUrl(url)||!a.remote.canChooseFiles()){reject(result,AttachmentIssue.PAGE_NOT_READY);return true;}
      int code=nextRequestCode();
      if(code<0){reject(result,AttachmentIssue.PICKER_LIMIT);return true;}
      Pending request=new Pending(result,code,url,epoch),previous=pending;
      // Reserve before calling out: cancellation can synchronously open another
      // prompt, replace this document, or destroy its Activity.
      pending=request;cancel(previous);
      if(!current(request)){cancel(request);return true;}
      try{
        if(a.loading!=null)a.loading.dismissTask();
        if(!current(request)){cancel(request);return true;}
        Intent intent=chooserIntent(params,"file");
        if(!current(request)){cancel(request);return true;}
        a.startActivityForResult(intent,request.request);
      }
      catch(ActivityNotFoundException failure){fail(request,AttachmentIssue.NO_PICKER);}
      catch(SecurityException failure){fail(request,AttachmentIssue.PICKER_ACCESS);}
      catch(RuntimeException failure){android.util.Log.w("PocketChat","File chooser launch failed",failure);fail(request,AttachmentIssue.PICKER_FAILED);}
      return true;
    }
    void dismissFilePrompt(ValueCallback<Uri[]> recipient){Pending request=pending;if(request!=null&&request.callback==recipient)cancel(request);}
  }
  WebChromeClient chrome(){return new Chrome();}
  static Intent chooserIntent(WebChromeClient.FileChooserParams params,String kind){
    LinkedHashSet<String> types=new LinkedHashSet<>();String[] accepted=params.getAcceptTypes();if(accepted!=null)for(String group:accepted)if(group!=null)for(String raw:group.split(",")){String type=raw.trim().toLowerCase(Locale.ROOT);if(type.startsWith("."))type=MimeTypeMap.getSingleton().getMimeTypeFromExtension(type.substring(1));if(type!=null&&type.matches("[a-z0-9.+-]+/[a-z0-9.+*-]+"))types.add(type);}
    String type="image".equals(kind)&&types.isEmpty()?"image/*":"*/*";if(types.size()==1)type=types.iterator().next();else if(!types.isEmpty()){boolean images=true;for(String t:types)images&=t.startsWith("image/");if(images)type="image/*";}
    Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType(type).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);if(types.size()>1)intent.putExtra(Intent.EXTRA_MIME_TYPES,types.toArray(new String[0]));intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE,params.getMode()==WebChromeClient.FileChooserParams.MODE_OPEN_MULTIPLE);return intent;
  }
  private boolean live(){return !destroyed&&!a.destroyed&&a.remote.displayContext.getBaseContext()==a;}
  private boolean samePage(Pending request){return request.epoch==a.session.navigationEpoch&&MainActivity.chatUrl(a.remote.getUrl())&&Objects.equals(Uri.parse(request.url).getPath(),Uri.parse(a.remote.getUrl()).getPath());}
  private boolean current(Pending request){return pending==request&&live()&&samePage(request);}
  boolean result(int requestCode,int code,Intent data){
    if(requestCode<FIRST_REQUEST||requestCode>LAST_REQUEST)return false;
    Pending request=pending;if(request==null||request.request!=requestCode)return true;
    try{
      if(!live()||code!=Activity.RESULT_OK||data==null){cancel(request);return true;}
      if(!samePage(request)){fail(request,AttachmentIssue.SELECTION_MOVED);return true;}
      LinkedHashSet<Uri> selected=new LinkedHashSet<>();ClipData clip=data.getClipData();
      if(clip!=null)for(int i=0;i<clip.getItemCount();i++){Uri uri=clip.getItemAt(i).getUri();if(uri!=null)selected.add(uri);}
      if(selected.isEmpty()&&data.getData()!=null)selected.add(data.getData());
      if(!current(request)||selected.isEmpty()){cancel(request);return true;}
      for(Uri uri:selected){
        // DocumentsUI may return our exported DownloadsProvider. Keep accepting
        // its granted stream; provider identity is not a readability check.
        if(uri==null||!"content".equals(uri.getScheme())||uri.getAuthority()==null){fail(request,AttachmentIssue.INVALID_SELECTION);return true;}
      }
      for(Uri uri:selected){
        if(!current(request)){cancel(request);return true;}
        try{a.getContentResolver().takePersistableUriPermission(uri,Intent.FLAG_GRANT_READ_URI_PERMISSION);}catch(SecurityException ignored){}
      }
      if(!current(request)){cancel(request);return true;}
      deliver(detach(request),selected.toArray(new Uri[0]));
    }catch(RuntimeException failure){android.util.Log.w("PocketChat","File chooser result failed",failure);fail(request,AttachmentIssue.READ_FAILED);}
    return true;
  }
  private ValueCallback<Uri[]> detach(Pending request){
    if(request==null)return null;
    ValueCallback<Uri[]> callback=request.callback;request.callback=null;
    if(pending==request)pending=null;
    return callback;
  }
  private static void deliver(ValueCallback<Uri[]> callback,Uri[] files){
    if(callback==null)return;
    try{callback.onReceiveValue(files);}catch(RuntimeException failure){android.util.Log.w("PocketChat","File chooser callback failed",failure);}
  }
  private void cancel(Pending request){
    ValueCallback<Uri[]> callback=detach(request);if(callback==null)return;
    // Close the captured picker before invoking native callbacks. A callback
    // can install a newer picker, which owns a different request code.
    try{a.finishActivity(request.request);}catch(RuntimeException failure){android.util.Log.w("PocketChat","File chooser dismissal failed",failure);}
    deliver(callback,null);
  }
  private void fail(Pending request,AttachmentIssue issue){
    boolean owned=pending==request;long epoch=a.session.navigationEpoch;
    cancel(request);
    if(owned&&live()&&pending==null&&epoch==a.session.navigationEpoch)a.attachmentStatus(issue);
  }
  private void reject(ValueCallback<Uri[]> callback,AttachmentIssue issue){
    Pending before=pending;long epoch=a.session.navigationEpoch;
    deliver(callback,null);
    if(live()&&pending==before&&epoch==a.session.navigationEpoch)a.attachmentStatus(issue);
  }
  void cancelChooser(){cancel(pending);}
  void destroy(){destroyed=true;cancelChooser();}

  void preview(String message,String name){
    JSONObject file=null;
    if(message.isEmpty()){
      for(int i=0;i<a.session.attachments.length();i++){
        JSONObject entry=a.session.attachments.optJSONObject(i);
        if(entry!=null&&name.equals(entry.optString("name")))file=entry;
      }
    }else file=J.parse(a.prefs.getString("preview:"+a.conversation+"|"+message+"|"+name,"{}"));
    if(file==null||file.optString("uri").isEmpty()){
      a.status("此历史附件尚无本地副本，请在原网页点按附件查看");
      a.showPage(true);
      return;
    }
    try{
      a.startActivity(SavedFileActions.openIntent(Uri.parse(file.optString("uri")),file.optString("mime"),name));
    }catch(ActivityNotFoundException e){
      a.status("手机尚未安装支持此格式的查看器");
    }catch(RuntimeException e){
      a.status("附件无法打开，可能已移动或访问权限已失效");
    }
  }
  static String sizeLabel(long bytes){if(bytes<0)return "大小未知";if(bytes<1024)return bytes+" B";return String.format(Locale.ROOT,bytes<1048576?"%.1f KB":"%.1f MB",bytes/(bytes<1048576?1024.0:1048576.0));}
  static String stateLabel(JSONObject f){String state=f.optString("state");int progress=f.optInt("progress",-1);return "ready".equals(state)?"网页已接收":"error".equals(state)?"上传失败，点按处理":"unknown".equals(state)?"网页接收待核对":progress>=0?"上传 "+progress+"%":"上传或处理中…";}
  // Old native attachment controls cannot create overlays, click the website,
  // restore its file queue or overwrite the archived files:<conversation> data.
  void persist(){}void restore(){}void refresh(){}void render(){}void sent(){}
  boolean hasFiles(){return false;}
  boolean blocked(){return pending!=null;}
  void open(String kind){a.status(BrowserRuntimePolicy.websiteActionMessage());}
  void remove(String name){a.status(BrowserRuntimePolicy.websiteActionMessage());}
  boolean beforeSend(){a.status(BrowserRuntimePolicy.websiteActionMessage());return false;}
  boolean allowNavigation(Runnable action){if(pending==null)return true;a.status("请先关闭文件选择器");return false;}
}
