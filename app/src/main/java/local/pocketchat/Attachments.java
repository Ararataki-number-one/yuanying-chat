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
  final MainActivity a;
  // Compatibility references for retired native controls. Never instantiated.
  final LinearLayout rows=null;final HorizontalScrollView view=null;
  ValueCallback<Uri[]> callback;String pickerUrl="";long pickerEpoch;boolean destroyed;
  Attachments(MainActivity activity){a=activity;}

  final class Chrome extends WebChromeClient {
    @Override public void onPermissionRequest(PermissionRequest request){request.deny();}
    @Override public void onGeolocationPermissionsShowPrompt(String origin,GeolocationPermissions.Callback result){result.invoke(origin,false,false);}
    @Override public boolean onShowFileChooser(WebView ignored,ValueCallback<Uri[]> result,FileChooserParams params){
      if(destroyed){result.onReceiveValue(null);return true;}
      if(!MainActivity.chatUrl(a.remote.getUrl())||!a.remote.canChooseFiles()){result.onReceiveValue(null);a.status("网页正在切换或尚未就绪，请稍后再添加附件");return true;}
      cancelChooser();callback=result;pickerUrl=a.remote.getUrl();pickerEpoch=a.session.navigationEpoch;
      if(a.loading!=null)a.loading.dismissTask();
      try{a.startActivityForResult(chooserIntent(params,"file"),74);}
      catch(ActivityNotFoundException failure){cancelChooser();a.status("设备没有可用的文件选择器");}
      catch(SecurityException failure){cancelChooser();a.status("无法打开文件选择器，请检查系统文件访问设置");}
      return true;
    }
    void dismissFilePrompt(ValueCallback<Uri[]> recipient){if(callback!=recipient)return;cancelChooser();try{a.finishActivity(74);}catch(RuntimeException ignored){}}
  }
  WebChromeClient chrome(){return new Chrome();}
  static Intent chooserIntent(WebChromeClient.FileChooserParams params,String kind){
    LinkedHashSet<String> types=new LinkedHashSet<>();String[] accepted=params.getAcceptTypes();if(accepted!=null)for(String group:accepted)if(group!=null)for(String raw:group.split(",")){String type=raw.trim().toLowerCase(Locale.ROOT);if(type.startsWith("."))type=MimeTypeMap.getSingleton().getMimeTypeFromExtension(type.substring(1));if(type!=null&&type.matches("[a-z0-9.+-]+/[a-z0-9.+*-]+"))types.add(type);}
    String type="image".equals(kind)&&types.isEmpty()?"image/*":"*/*";if(types.size()==1)type=types.iterator().next();else if(!types.isEmpty()){boolean images=true;for(String t:types)images&=t.startsWith("image/");if(images)type="image/*";}
    Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType(type).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);if(types.size()>1)intent.putExtra(Intent.EXTRA_MIME_TYPES,types.toArray(new String[0]));intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE,params.getMode()==WebChromeClient.FileChooserParams.MODE_OPEN_MULTIPLE);return intent;
  }
  boolean samePage(){return pickerEpoch==a.session.navigationEpoch&&MainActivity.chatUrl(a.remote.getUrl())&&Uri.parse(pickerUrl).getPath().equals(Uri.parse(a.remote.getUrl()).getPath());}
  void result(int code,Intent data){
    ValueCallback<Uri[]> recipient=callback;if(recipient==null)return;
    if(destroyed||code!=Activity.RESULT_OK||data==null){cancelChooser();return;}
    if(!samePage()){cancelChooser();a.status("对话已改变，未添加附件");return;}
    LinkedHashSet<Uri> selected=new LinkedHashSet<>();
    if(data.getClipData()!=null)for(int i=0;i<data.getClipData().getItemCount();i++)selected.add(data.getClipData().getItemAt(i).getUri());
    else if(data.getData()!=null)selected.add(data.getData());
    if(selected.isEmpty()){cancelChooser();return;}
    for(Uri uri:selected){
      if(uri==null||!"content".equals(uri.getScheme())||uri.getAuthority()==null||uri.getAuthority().startsWith(a.getPackageName()+".")){cancelChooser();a.status("请选择系统文件选择器中的文件");return;}
      try{a.getContentResolver().takePersistableUriPermission(uri,Intent.FLAG_GRANT_READ_URI_PERMISSION);}catch(SecurityException ignored){}
    }
    callback=null;recipient.onReceiveValue(selected.toArray(new Uri[0]));
  }
  void cancelChooser(){ValueCallback<Uri[]> old=callback;callback=null;if(old!=null)old.onReceiveValue(null);}
  void destroy(){destroyed=true;cancelChooser();}

  void preview(String message,String name){JSONObject file=null;if(message.isEmpty()){for(int i=0;i<a.session.attachments.length();i++){JSONObject f=a.session.attachments.optJSONObject(i);if(name.equals(f.optString("name")))file=f;}}else file=J.parse(a.prefs.getString("preview:"+a.conversation+"|"+message+"|"+name,"{}"));if(file!=null&&!file.optString("uri").isEmpty()){a.startActivity(new Intent(a,Profiles.preview(a)).putExtra("uri",file.optString("uri")).putExtra("name",name).putExtra("mime",file.optString("mime")));}else{a.status("此历史附件尚无本地副本，请在原网页点按附件查看");a.showPage(true);}}
  static String sizeLabel(long bytes){if(bytes<0)return "大小未知";if(bytes<1024)return bytes+" B";return String.format(Locale.ROOT,bytes<1048576?"%.1f KB":"%.1f MB",bytes/(bytes<1048576?1024.0:1048576.0));}
  static String stateLabel(JSONObject f){String state=f.optString("state");int progress=f.optInt("progress",-1);return "ready".equals(state)?"网页已接收":"error".equals(state)?"上传失败，点按处理":"unknown".equals(state)?"网页接收待核对":progress>=0?"上传 "+progress+"%":"上传或处理中…";}
  // Old native attachment controls cannot create overlays, click the website,
  // restore its file queue or overwrite the archived files:<conversation> data.
  void persist(){}void restore(){}void refresh(){}void render(){}void sent(){}
  boolean hasFiles(){return false;}
  boolean blocked(){return callback!=null;}
  void open(String kind){a.status(BrowserRuntimePolicy.websiteActionMessage());}
  void remove(String name){a.status(BrowserRuntimePolicy.websiteActionMessage());}
  boolean beforeSend(){a.status(BrowserRuntimePolicy.websiteActionMessage());return false;}
  boolean allowNavigation(Runnable action){if(callback==null)return true;a.status("请先关闭文件选择器");return false;}
}
