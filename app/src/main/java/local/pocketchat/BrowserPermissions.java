package local.pocketchat;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.app.Application;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.webkit.GeolocationPermissions;
import android.webkit.PermissionRequest;
import android.webkit.WebView;
import java.net.URI;
import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Consumer;
import java.util.function.Supplier;

/** One-time current-site permission grants, independently bound to each document lifetime. */
final class BrowserPermissions {
  static final int FIRST_REQUEST=0x3000,LAST_REQUEST=0x4fff;
  static final AtomicInteger NEXT_REQUEST=new AtomicInteger(FIRST_REQUEST);
  final Activity activity;final Supplier<WebView> active;final Consumer<String> status;
  final WeakHashMap<WebView,Long> generations=new WeakHashMap<>();
  boolean foreground,closed;Pending pending;
  static final class Pending {
    final WebView source;final String url,origin;final long generation;final PermissionRequest request;
    final GeolocationPermissions.Callback location;final String locationOrigin;final String[] resources,permissions;
    AlertDialog dialog;int requestCode=-1;String[] runtimePermissions;boolean awaitingRuntime,resultReady,granted,finished;
    Pending(WebView source,String url,String origin,long generation,PermissionRequest request,GeolocationPermissions.Callback location,String locationOrigin,String[] resources,String[] permissions){
      this.source=source;this.url=url;this.origin=origin;this.generation=generation;this.request=request;this.location=location;this.locationOrigin=locationOrigin;this.resources=resources;this.permissions=permissions;
    }
  }
  final Application.ActivityLifecycleCallbacks lifecycle=new Application.ActivityLifecycleCallbacks(){
    public void onActivityResumed(Activity owner){if(owner==activity)resume();}
    public void onActivityPaused(Activity owner){if(owner==activity){foreground=false;Pending value=pending;if(value!=null&&!value.awaitingRuntime)finish(value,false);}}
    public void onActivityStopped(Activity owner){if(owner==activity)stopped();}
    public void onActivityDestroyed(Activity owner){if(owner==activity)close();}
    public void onActivityCreated(Activity owner,Bundle state){}
    public void onActivityStarted(Activity owner){}
    public void onActivitySaveInstanceState(Activity owner,Bundle state){}
  };
  BrowserPermissions(Activity activity,Supplier<WebView> active,Consumer<String> status){
    this.activity=activity;this.active=active;this.status=status;foreground=activity.hasWindowFocus();activity.getApplication().registerActivityLifecycleCallbacks(lifecycle);
  }
  void resume(){if(closed)return;foreground=true;Pending value=pending;if(value!=null&&value.resultReady)finish(value,value.granted&&current(value,true));}
  void stopped(){foreground=false;Pending value=pending;if(value!=null)finish(value,false);}
  void request(WebView source,PermissionRequest request){
    if(request==null)return;String[] resources=supported(request.getResources());
    if(resources.length==0){deny(request);message("此网页请求的权限暂不支持");return;}
    String requested=request.getOrigin()==null?"":request.getOrigin().toString();
    Pending value=prepare(source,requested,request,null,null,resources,androidPermissions(resources));
    if(value==null){deny(request);return;}show(value);
  }
  void cancel(PermissionRequest request){Pending value=pending;if(value!=null&&value.request==request)finish(value,false);}
  void geolocation(WebView source,String origin,GeolocationPermissions.Callback callback){
    if(callback==null)return;
    Pending value=prepare(source,origin,null,callback,origin,new String[0],new String[]{Manifest.permission.ACCESS_COARSE_LOCATION});
    if(value==null){location(callback,origin,false);return;}show(value);
  }
  void hideGeolocation(){Pending value=pending;if(value!=null&&value.location!=null)finish(value,false);}
  Pending prepare(WebView source,String requested,PermissionRequest request,GeolocationPermissions.Callback location,String locationOrigin,String[] resources,String[] permissions){
    if(closed||!foreground||activity.isFinishing()||activity.isDestroyed()||source==null||active.get()!=source)return null;
    String url=source.getUrl(),origin=origin(url);if(origin.isEmpty()||!origin.equals(origin(requested))){message("网页权限仅向当前 HTTPS 站点开放");return null;}
    Pending previous=pending;if(previous!=null)finish(previous,false);
    // Native callbacks can reenter while the older request is denied.
    if(pending!=null||closed||!foreground||active.get()!=source||!Objects.equals(url,source.getUrl()))return null;
    Pending value=new Pending(source,url,origin,generation(source),request,location,locationOrigin,resources,permissions);pending=value;return value;
  }
  void show(Pending value){
    String names=value.location!=null?"大致位置":String.join("、",labels(value.resources));
    AlertDialog dialog=new AlertDialog.Builder(activity).setTitle("允许此网站使用"+names+"？").setMessage(value.origin+"\n\n仅处理当前网页发起的这次请求。网页切换前尚未完成的授权会取消，不保存此网站的长期允许记录。")
      .setNegativeButton("拒绝",(d,which)->finish(value,false)).setPositiveButton("此次允许",(d,which)->allow(value)).create();
    value.dialog=dialog;dialog.setOnCancelListener(d->finish(value,false));dialog.setOnDismissListener(d->{if(pending==value&&!value.finished&&!value.awaitingRuntime)finish(value,false);});
    try{dialog.show();}catch(RuntimeException unavailable){finish(value,false);}
  }
  void allow(Pending value){
    if(!current(value,true)){finish(value,false);return;}
    ArrayList<String> missing=new ArrayList<>();for(String permission:value.permissions)if(activity.checkSelfPermission(permission)!=PackageManager.PERMISSION_GRANTED)missing.add(permission);
    if(missing.isEmpty()){finish(value,true);return;}
    int code=NEXT_REQUEST.getAndIncrement();if(code>LAST_REQUEST){message("权限请求次数过多，请重新打开浏览器");finish(value,false);return;}
    value.awaitingRuntime=true;value.requestCode=code;value.runtimePermissions=missing.toArray(new String[0]);
    try{activity.requestPermissions(value.runtimePermissions.clone(),code);}
    catch(RuntimeException unavailable){message("系统权限窗口无法打开，请在系统设置中检查权限");finish(value,false);}
  }
  boolean result(int requestCode,String[] permissions,int[] results){
    if(requestCode<FIRST_REQUEST||requestCode>LAST_REQUEST)return false;
    Pending value=pending;if(value==null||value.requestCode!=requestCode||!value.awaitingRuntime)return true;
    boolean granted=permissions!=null&&results!=null&&permissions.length==results.length&&permissions.length>0&&permissions.length==value.runtimePermissions.length;
    HashSet<String> seen=new HashSet<>();if(granted)for(int i=0;i<permissions.length;i++)if(!seen.add(permissions[i])||!Arrays.asList(value.runtimePermissions).contains(permissions[i])||results[i]!=PackageManager.PERMISSION_GRANTED)granted=false;
    for(String permission:value.permissions)if(activity.checkSelfPermission(permission)!=PackageManager.PERMISSION_GRANTED)granted=false;
    value.resultReady=true;value.granted=granted;
    if(!current(value,false)||!granted){if(!granted)message("系统权限未允许，网页请求已拒绝");finish(value,false);}
    else if(foreground)finish(value,true);
    // Android may deliver this callback before its permission window resumes
    // the host. Resume rechecks the exact current document before any grant.
    return true;
  }
  void onNavigation(WebView source){if(source==null)return;generations.put(source,generation(source)+1);Pending value=pending;if(value!=null&&value.source==source)finish(value,false);}
  long generation(WebView source){Long value=generations.get(source);return value==null?0:value;}
  boolean current(Pending value,boolean requireForeground){
    return !closed&&!value.finished&&pending==value&&(!requireForeground||foreground)&&!activity.isFinishing()&&!activity.isDestroyed()
      &&active.get()==value.source&&generation(value.source)==value.generation&&Objects.equals(value.url,value.source.getUrl())&&value.origin.equals(origin(value.source.getUrl()));
  }
  void finish(Pending value,boolean grant){
    if(value.finished)return;boolean permitted=grant&&current(value,true);value.finished=true;if(pending==value)pending=null;
    AlertDialog dialog=value.dialog;value.dialog=null;if(dialog!=null)try{dialog.dismiss();}catch(RuntimeException ignored){}
    if(value.request!=null){try{if(permitted)value.request.grant(value.resources.clone());else value.request.deny();}catch(RuntimeException ignored){}}
    else location(value.location,value.locationOrigin,permitted);
  }
  void close(){if(closed)return;closed=true;foreground=false;Pending value=pending;if(value!=null)finish(value,false);generations.clear();activity.getApplication().unregisterActivityLifecycleCallbacks(lifecycle);}
  void message(String text){if(!closed)status.accept(text);}
  static void deny(PermissionRequest request){try{request.deny();}catch(RuntimeException ignored){}}
  static void location(GeolocationPermissions.Callback callback,String origin,boolean grant){try{callback.invoke(origin,grant,false);}catch(RuntimeException ignored){}}
  static String origin(String address){
    if(!BrowserAddressPolicy.allowed(address))return "";
    try{URI uri=new URI(BrowserAddressPolicy.normalizeInput(address));if(!"https".equals(uri.getScheme()))return "";return "https://"+uri.getRawAuthority().toLowerCase(Locale.ROOT).replaceFirst(":443$","");}
    catch(Exception invalid){return "";}
  }
  static String[] supported(String[] requested){LinkedHashSet<String> out=new LinkedHashSet<>();if(requested!=null)for(String resource:requested)if(PermissionRequest.RESOURCE_VIDEO_CAPTURE.equals(resource)||PermissionRequest.RESOURCE_AUDIO_CAPTURE.equals(resource))out.add(resource);return out.toArray(new String[0]);}
  static String[] androidPermissions(String[] resources){ArrayList<String> out=new ArrayList<>();for(String resource:resources)out.add(PermissionRequest.RESOURCE_VIDEO_CAPTURE.equals(resource)?Manifest.permission.CAMERA:Manifest.permission.RECORD_AUDIO);return out.toArray(new String[0]);}
  static List<String> labels(String[] resources){ArrayList<String> out=new ArrayList<>();for(String resource:resources)out.add(PermissionRequest.RESOURCE_VIDEO_CAPTURE.equals(resource)?"摄像头":"麦克风");return out;}
}
