package local.pocketchat;

import android.content.*;
import android.graphics.Rect;
import android.net.Uri;
import android.os.*;
import android.view.*;
import android.webkit.*;
import android.widget.AbsoluteLayout;
import org.json.*;
import org.mozilla.geckoview.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.*;

/** Keeps the existing session/business API while Gecko owns the real remote page. */
@SuppressWarnings("deprecation")
class GeckoWebView extends WebView {
  static final String VERSION="GeckoView 157.0";
  final ChatSession owner;
  GeckoView surface;GeckoRuntime runtime;WebExtension extension;GeckoSession primary,current;
  final ArrayList<GeckoSession> popups=new ArrayList<>();
  final Map<GeckoSession,WebExtension.Port> ports=new IdentityHashMap<>();
  final Map<GeckoSession,String> locations=new IdentityHashMap<>();
  final Map<Integer,ValueCallback<String>> callbacks=new HashMap<>();
  WebViewClient client;WebChromeClient chrome;DownloadListener download;
  boolean enabled,ready,failed,desktop,canBack;String url="",queued="";float scale=1;int sequence;

  GeckoWebView(Context context,ChatSession session){
    super(context);owner=session;
    enabled=!"system".equals(session.prefs.getString("browserEngine","gecko"))&&session.pending==null;
    // The retained System WebView is only loaded when explicitly selected.
    super.getSettings().setBlockNetworkLoads(true);
    if(enabled)owner.handler.post(this::initialize);
  }
  static boolean active(WebView web){return web instanceof GeckoWebView&&((GeckoWebView)web).enabled;}
  private void initialize(){
    if(!enabled||runtime!=null||failed)return;
    try{
      File directory=new File(owner.context.getNoBackupFilesDir(),"gecko-browser");
      if(!directory.isDirectory()&&!directory.mkdirs())throw new IOException("无法创建浏览器数据目录");
      File config=new File(owner.context.getNoBackupFilesDir(),"gecko-browser.yaml");
      // Closed bootstrap route. The built-in route delegate opens only the existing guarded route.
      String prefs="prefs:\n  network.proxy.type: 1\n  network.proxy.socks: '127.0.0.1'\n  network.proxy.socks_port: 9\n"
        +"  network.proxy.socks_version: 5\n  network.proxy.socks_remote_dns: true\n  network.proxy.no_proxies_on: ''\n"
        +"  network.proxy.allow_hijacking_localhost: true\n  network.trr.mode: 5\n  network.dns.disablePrefetch: true\n"
        +"  network.prefetch-next: false\n  network.http.speculative-parallel-limit: 0\n  media.peerconnection.enabled: false\n";
      Files.write(config.toPath(),prefs.getBytes(StandardCharsets.UTF_8));
      runtime=GeckoRuntime.create(new GeckoEnvironmentContext(owner.context),new GeckoRuntimeSettings.Builder()
        .arguments(new String[]{"-profile",directory.getAbsolutePath()}).configFilePath(config.getAbsolutePath())
        .isolatedProcessEnabled(Build.VERSION.SDK_INT>=29).appZygoteProcessEnabled(false)
        .remoteDebuggingEnabled(false).consoleOutput(false).trustedRecursiveResolverMode(5)
        .forceUserScalableEnabled(true).inputAutoZoomEnabled(true).build());
      runtime.getWebExtensionController().ensureBuiltIn("resource://android/assets/gecko/","browser@pocketchat.local")
        .accept(value->{extension=value;extension.setMessageDelegate(routeMessages,"pocketroute");open();},error->failure("浏览器初始化失败，可切换系统内核重试"));
    }catch(Exception error){failure("新内核未能启动，可切换系统内核重试");}
  }
  private final WebExtension.MessageDelegate routeMessages=new WebExtension.MessageDelegate(){
    @Override public GeckoResult<Object> onMessage(String app,Object message,WebExtension.MessageSender sender){
      if(!"pocketroute".equals(app)||!(message instanceof JSONObject))return GeckoResult.fromValue(blocked());
      JSONObject request=(JSONObject)message;
      if("ready".equals(request.optString("kind")))return GeckoResult.fromValue(null);
      if(!"route".equals(request.optString("kind")))return GeckoResult.fromValue(blocked());
      return GeckoResult.fromValue(route(request.optString("url")));
    }
  };
  JSONObject blocked(){return J.obj("type","socks","host","127.0.0.1","port",9,"proxyDNS",true,"failoverTimeout",1);}
  JSONObject route(String target){
    if(!enabled||owner.guard==null||!owner.guard.allowed()||!allowedUrl(target.startsWith("wss://")?"https"+target.substring(3):target.startsWith("ws://")?"http"+target.substring(2):target))return blocked();
    String proxy=owner.internalNetwork()?NativeNetwork.get(owner.context).proxy():owner.prefs.getString("proxy","").trim();
    if(proxy.isEmpty())return J.obj("type","direct");
    if(!MainActivity.validProxy(proxy))return blocked();
    Uri address=Uri.parse(proxy);String scheme=address.getScheme();
    JSONObject result=J.obj("type","socks".equals(scheme)?"socks":scheme,"host",address.getHost(),"port",address.getPort(),
      "failoverTimeout",1,"connectionIsolationKey","environment-"+Profiles.slot(owner.context)+"-"+owner.connectionEpoch);
    if("socks".equals(scheme))try{result.put("proxyDNS",true);}catch(Exception ignored){}
    return result;
  }
  private void open(){
    if(!enabled)return;
    if(surface==null){surface=new GeckoView(getContext());addView(surface,new AbsoluteLayout.LayoutParams(-1,-1,0,0));}
    primary=newSession();current=primary;primary.open(runtime);surface.setSession(primary);ready=true;
    if(!queued.isEmpty()){String target=queued;queued="";loadUrl(target);}
  }
  GeckoSession newSession(){
    GeckoSession session=new GeckoSession(new GeckoSessionSettings.Builder().contextId("environment-"+Profiles.slot(owner.context))
      .userAgentMode(desktop?GeckoSessionSettings.USER_AGENT_MODE_DESKTOP:GeckoSessionSettings.USER_AGENT_MODE_MOBILE)
      .viewportMode(desktop?GeckoSessionSettings.VIEWPORT_MODE_DESKTOP:GeckoSessionSettings.VIEWPORT_MODE_MOBILE).build());
    session.getWebExtensionController().setMessageDelegate(extension,pageMessages,"pocketpage");
    session.setNavigationDelegate(new GeckoSession.NavigationDelegate(){
      @Override public GeckoResult<AllowOrDeny> onLoadRequest(GeckoSession s,LoadRequest request){
        boolean allowed="about:blank".equals(request.uri)||owner.guard.allowed()&&allowedUrl(request.uri);
        if(!allowed&&s==current)owner.setStatus("连接尚未受保护，网页已暂停加载");
        return GeckoResult.fromValue(allowed?AllowOrDeny.ALLOW:AllowOrDeny.DENY);
      }
      @Override public void onLocationChange(GeckoSession s,String target,List<GeckoSession.PermissionDelegate.ContentPermission> permissions,Boolean gesture){
        locations.put(s,target);if(s!=current)return;url=target;if(MainActivity.chatUrl(target))owner.prefs.edit().putString("url",target).apply();
      }
      @Override public void onCanGoBack(GeckoSession s,boolean value){if(s==current)canBack=value;}
      @Override public GeckoResult<GeckoSession> onNewSession(GeckoSession s,String target){
        if(!owner.guard.allowed()||!allowedUrl(target))return GeckoResult.fromValue(null);
        GeckoSession popup=newSession();popups.add(popup);
        owner.handler.post(()->{if(!enabled)return;if(surface.getSession()!=null)surface.releaseSession();current.setActive(false);current=popup;url=target;canBack=false;surface.setSession(popup);popup.setActive(true);});
        return GeckoResult.fromValue(popup);
      }
      @Override public GeckoResult<String> onLoadError(GeckoSession s,String target,WebRequestError error){
        if(s==current){owner.pageError="网页连接失败，请检查当前环境网络或重新加载";owner.finishNavigation(owner.pageError,false);}
        return null;
      }
    });
    session.setProgressDelegate(new GeckoSession.ProgressDelegate(){
      @Override public void onPageStart(GeckoSession s,String target){if(s==current){url=target;cancelCallbacks();if(client!=null)client.onPageStarted(GeckoWebView.this,target,null);}}
      @Override public void onPageStop(GeckoSession s,boolean success){if(s!=current)return;if(success&&client!=null){client.onPageCommitVisible(GeckoWebView.this,url);client.onPageFinished(GeckoWebView.this,url);}else if(!success&&owner.pageError.isEmpty()){owner.pageError="网页暂时未能加载，请重新加载或检查网络";owner.finishNavigation(owner.pageError,false);}}
    });
    session.setContentDelegate(new GeckoSession.ContentDelegate(){
      @Override public void onCloseRequest(GeckoSession s){if(s==current)closePopup();}
      @Override public void onCrash(GeckoSession s){if(s==current)failure("网页进程已退出，请重新加载或切换系统内核");}
      @Override public void onExternalResponse(GeckoSession s,WebResponse response){
        if(s==current&&download!=null)download.onDownloadStart(response.uri,"",response.headers.get("Content-Disposition"),response.headers.get("Content-Type"),-1);
      }
    });
    session.setPromptDelegate(new GeckoSession.PromptDelegate(){
      @Override public GeckoResult<PromptResponse> onFilePrompt(GeckoSession s,FilePrompt prompt){
        GeckoResult<PromptResponse> result=new GeckoResult<>();
        if(chrome==null||s!=current){result.complete(prompt.dismiss());return result;}
        WebChromeClient.FileChooserParams params=new WebChromeClient.FileChooserParams(){
          @Override public int getMode(){return prompt.type==2?MODE_OPEN_MULTIPLE:MODE_OPEN;}
          @Override public String[] getAcceptTypes(){return prompt.mimeTypes;}
          @Override public boolean isCaptureEnabled(){return false;}
          @Override public CharSequence getTitle(){return prompt.title;}
          @Override public String getFilenameHint(){return "";}
          @Override public Intent createIntent(){return new Intent(Intent.ACTION_OPEN_DOCUMENT).setType("*/*").addCategory(Intent.CATEGORY_OPENABLE);}
        };
        boolean handled=chrome.onShowFileChooser(GeckoWebView.this,uris->result.complete(uris==null?prompt.dismiss():prompt.confirm(getContext(),uris)),params);
        if(!handled)result.complete(prompt.dismiss());return result;
      }
    });
    session.setPermissionDelegate(new GeckoSession.PermissionDelegate(){
      @Override public void onAndroidPermissionsRequest(GeckoSession s,String[] permissions,Callback callback){callback.reject();}
      @Override public void onMediaPermissionRequest(GeckoSession s,String origin,MediaSource[] video,MediaSource[] audio,MediaCallback callback){callback.reject();}
    });
    return session;
  }
  final WebExtension.MessageDelegate pageMessages=new WebExtension.MessageDelegate(){
    @Override public void onConnect(WebExtension.Port port){
      GeckoSession source=port.sender.session;
      if(source==null||!port.sender.isTopLevel()||!"pocketpage".equals(port.name))return;
      ports.put(source,port);port.setDelegate(new WebExtension.PortDelegate(){
        @Override public void onPortMessage(Object message,WebExtension.Port incoming){
          if(!(message instanceof JSONObject)||source!=current||incoming!=ports.get(source))return;
          JSONObject data=(JSONObject)message;String kind=data.optString("kind");
          if("result".equals(kind)){ValueCallback<String> callback=callbacks.remove(data.optInt("id"));if(callback!=null)callback.onReceiveValue(data.optString("result","null"));}
          else if("reply".equals(kind)&&MainActivity.chatUrl(port.sender.url)&&MainActivity.chatUrl(getUrl())&&owner.webObserver!=null){String text=data.optString("text");if(text.length()<=2*1024*1024)owner.webObserver.receive(J.parse(text));}
          else if("ready".equals(kind)&&owner.webObserver!=null)owner.webObserver.pageReady();
          else if("scale".equals(kind)){float next=(float)data.optDouble("value",scale),old=scale;if(next>0){scale=next;if(client!=null)client.onScaleChanged(GeckoWebView.this,old,next);}}
        }
        @Override public void onDisconnect(WebExtension.Port incoming){if(ports.get(source)==incoming)ports.remove(source);if(source==current)cancelCallbacks();}
      });
    }
  };
  protected boolean allowedUrl(String target){return BrowserNetworkGuard.publicHttps(Uri.parse(target));}
  private void failure(String message){failed=true;owner.pageError=message;owner.finishNavigation(message,false);}
  private void cancelCallbacks(){ArrayList<ValueCallback<String>> pending=new ArrayList<>(callbacks.values());callbacks.clear();for(ValueCallback<String> callback:pending)callback.onReceiveValue("null");}
  void configure(boolean desktop,int protection){
    this.desktop=desktop;
    if(current!=null){current.getSettings().setUserAgentMode(desktop?GeckoSessionSettings.USER_AGENT_MODE_DESKTOP:GeckoSessionSettings.USER_AGENT_MODE_MOBILE);current.getSettings().setViewportMode(desktop?GeckoSessionSettings.VIEWPORT_MODE_DESKTOP:GeckoSessionSettings.VIEWPORT_MODE_MOBILE);current.getSettings().setUseTrackingProtection(protection>0);}
  }
  void useEngine(boolean value){
    if(enabled==value)return;stopLoading();cancelCallbacks();enabled=value;owner.prefs.edit().putString("browserEngine",value?"gecko":"system").commit();
    if(value){failed=false;if(runtime==null)initialize();else open();}
    else{ready=false;if(surface!=null){if(surface.getSession()!=null)surface.releaseSession();removeView(surface);surface=null;}for(GeckoSession s:popups)if(s.isOpen())s.close();popups.clear();if(primary!=null&&primary.isOpen())primary.close();current=null;primary=null;ports.clear();}
  }
  boolean closePopup(){
    if(popups.isEmpty())return false;GeckoSession old=current;popups.remove(old);surface.releaseSession();current=popups.isEmpty()?primary:popups.get(popups.size()-1);url=locations.getOrDefault(current,"");canBack=false;surface.setSession(current);current.setActive(true);ports.remove(old);locations.remove(old);old.close();cancelCallbacks();return true;
  }
  @Override public void loadUrl(String target){if(!enabled){super.loadUrl(target);return;}queued=target;if(!ready||current==null)return;if(!owner.guard.allowed())return;queued="";current.loadUri(target);}
  @Override public String getUrl(){return enabled?url:super.getUrl();}
  @Override public void evaluateJavascript(String code,ValueCallback<String> callback){
    if(!enabled){super.evaluateJavascript(code,callback);return;}
    WebExtension.Port port=ports.get(current);if(port==null){if(callback!=null)callback.onReceiveValue("null");return;}
    int id=++sequence;if(callback!=null){callbacks.put(id,callback);owner.handler.postDelayed(()->{ValueCallback<String> cb=callbacks.remove(id);if(cb!=null)cb.onReceiveValue("null");},10000);}
    try{port.postMessage(J.obj("kind","evaluate","id",id,"code",code));}catch(Exception error){ValueCallback<String> cb=callbacks.remove(id);if(cb!=null)cb.onReceiveValue("null");}
  }
  @Override public void stopLoading(){if(enabled){queued="";if(current!=null)current.stop();}else super.stopLoading();}
  @Override public void setWebViewClient(WebViewClient value){client=value;super.setWebViewClient(value);}
  @Override public void setWebChromeClient(WebChromeClient value){chrome=value;super.setWebChromeClient(value);}
  @Override public void setDownloadListener(DownloadListener value){download=value;super.setDownloadListener(value);}
  @Override public void onPause(){if(enabled){if(current!=null)current.setActive(false);}else super.onPause();}
  @Override public void onResume(){if(enabled){if(current!=null)current.setActive(true);}else super.onResume();}
  @Override public void pauseTimers(){if(!enabled)super.pauseTimers();}
  @Override public void resumeTimers(){if(!enabled)super.resumeTimers();}
  @Override public boolean canGoBack(){return enabled?canBack||!popups.isEmpty():super.canGoBack();}
  @Override public void goBack(){if(enabled){if(canBack)current.goBack();else closePopup();}else super.goBack();}
  @Override public float getScale(){return enabled?scale:super.getScale();}
  @Override public void setInitialScale(int percent){if(!enabled)super.setInitialScale(percent);}
  @Override public void zoomBy(float factor){
    if(!enabled){super.zoomBy(factor);return;}
    if(current==null||surface==null||factor<=0||!Float.isFinite(factor))return;
    final GeckoSession target=current;final long started=SystemClock.uptimeMillis();
    final float x=getWidth()/2f,y=getHeight()/2f,radius=Math.min(getWidth()/5f,48*getResources().getDisplayMetrics().density);
    final float amount=Math.max(.1f,Math.min(10f,factor));
    if(radius<=0)return;
    pinch(target,started,MotionEvent.ACTION_DOWN,1,x,y,radius);
    pinch(target,started,MotionEvent.ACTION_POINTER_DOWN|(1<<MotionEvent.ACTION_POINTER_INDEX_SHIFT),2,x,y,radius);
    for(int step=1;step<=10;step++){final int n=step;owner.handler.postDelayed(()->{
      if(target!=current||!enabled)return;
      float next=radius*(1+(amount-1)*n/10f);pinch(target,started,MotionEvent.ACTION_MOVE,2,x,y,next);
      if(n==10){pinch(target,started,MotionEvent.ACTION_POINTER_UP|(1<<MotionEvent.ACTION_POINTER_INDEX_SHIFT),2,x,y,next);pinch(target,started,MotionEvent.ACTION_UP,1,x,y,next);}
    },step*16L);}
  }
  private void pinch(GeckoSession target,long start,int action,int count,float x,float y,float radius){
    MotionEvent.PointerProperties[] properties=new MotionEvent.PointerProperties[count];MotionEvent.PointerCoords[] coordinates=new MotionEvent.PointerCoords[count];
    for(int i=0;i<count;i++){properties[i]=new MotionEvent.PointerProperties();properties[i].id=i;properties[i].toolType=MotionEvent.TOOL_TYPE_FINGER;coordinates[i]=new MotionEvent.PointerCoords();coordinates[i].x=x+(i==0?-radius:radius);coordinates[i].y=y;coordinates[i].pressure=1;coordinates[i].size=1;}
    MotionEvent event=MotionEvent.obtain(start,SystemClock.uptimeMillis(),action,count,properties,coordinates,0,0,1,1,0,0,InputDevice.SOURCE_TOUCHSCREEN,0);
    target.getPanZoomController().onTouchEvent(event);event.recycle();
  }
  @Override protected void onFocusChanged(boolean gain,int direction,Rect previous){super.onFocusChanged(gain,direction,previous);if(enabled&&gain&&surface!=null)surface.requestFocus();}
  @Override public boolean onInterceptTouchEvent(MotionEvent event){return !enabled&&super.onInterceptTouchEvent(event);}
  @Override protected void onMeasure(int width,int height){super.onMeasure(width,height);if(surface!=null)surface.measure(MeasureSpec.makeMeasureSpec(getMeasuredWidth(),MeasureSpec.EXACTLY),MeasureSpec.makeMeasureSpec(getMeasuredHeight(),MeasureSpec.EXACTLY));}
  @Override protected void onLayout(boolean changed,int l,int t,int r,int b){super.onLayout(changed,l,t,r,b);if(surface!=null)surface.layout(0,0,r-l,b-t);}
}
