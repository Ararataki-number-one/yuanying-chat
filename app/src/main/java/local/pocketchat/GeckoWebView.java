package local.pocketchat;

import android.content.*;
import android.graphics.Rect;
import android.net.Uri;
import android.os.*;
import android.view.*;
import android.webkit.*;
import android.widget.FrameLayout;
import org.json.*;
import org.mozilla.geckoview.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.*;
import java.util.concurrent.*;

/** Keeps the existing session/business API while Gecko owns the real remote page. */
@SuppressWarnings("deprecation")
class GeckoWebView extends FrameLayout {
  WebView legacy; final GeckoSettings metadata=new GeckoSettings();
  final MutableContextWrapper displayContext;
  static boolean wantsGecko(ChatSession session){return !"system".equals(session.prefs.getString("browserEngine","gecko"))&&(session.pending==null||session.prefs.contains("browserEngine"));}
  WebView system(){if(enabled)throw new IllegalStateException("系统内核未启用");return legacy;}
  WebSettings getSettings(){return enabled?metadata:system().getSettings();}
  void setHost(android.app.Activity activity){displayContext.setBaseContext(activity==null?owner.context:activity);}
  OnTouchListener touches;
  @Override public void setOnTouchListener(OnTouchListener listener){touches=listener;}
  @Override public boolean dispatchTouchEvent(MotionEvent event){if(touches!=null&&touches.onTouch(this,event))return true;return super.dispatchTouchEvent(event);}
  void destroy(){
    if(destroyed)return;destroyed=true;
    callbacks.clear();cookieCallbacks.clear();
    if(surface!=null&&surface.getSession()!=null)surface.releaseSession();
    for(GeckoSession session:new ArrayList<>(locations.keySet()))if(session.isOpen())session.close();
    if(primary!=null&&primary.isOpen())primary.close();
    ports.clear();popups.clear();locations.clear();backStates.clear();loadingTargets.clear();painted.clear();crashed.clear();
    routePort=null;ready=false;
    if(legacy!=null)legacy.destroy();
  }

  static final String VERSION="GeckoView 157.0";
  final ChatSession owner;
  GeckoView surface;GeckoRuntime runtime;WebExtension extension;GeckoSession primary,current;
  final ArrayList<GeckoSession> popups=new ArrayList<>();
  final Map<GeckoSession,WebExtension.Port> ports=new IdentityHashMap<>();
  final Map<GeckoSession,String> locations=new IdentityHashMap<>();
  final Map<GeckoSession,Boolean> backStates=new IdentityHashMap<>();
  final Map<GeckoSession,String> loadingTargets=new IdentityHashMap<>();
  final Set<GeckoSession> painted=Collections.newSetFromMap(new IdentityHashMap<>());
  final Set<GeckoSession> crashed=Collections.newSetFromMap(new IdentityHashMap<>());
  final BrowserBridgeRequests callbacks,cookieCallbacks;WebExtension.Port routePort;String cookieStamp="";
  WebViewClient client;WebChromeClient chrome;DownloadListener download;
  boolean enabled,ready,failed,desktop,canBack,destroyed;String url="",queued="";float scale=1;

  GeckoWebView(Context context,ChatSession session){
    super(context);owner=session;displayContext=new MutableContextWrapper(context);
    BrowserBridgeRequests.Timer timer=new BrowserBridgeRequests.Timer(){
      public void schedule(Runnable task,long delay){owner.handler.postDelayed(task,delay);}
      public void cancel(Runnable task){owner.handler.removeCallbacks(task);}
    };
    callbacks=new BrowserBridgeRequests(timer,"null");cookieCallbacks=new BrowserBridgeRequests(timer,null);
    enabled=wantsGecko(session);
    // Legacy pending tasks belong to the old engine; new tasks retain their actual engine.
    owner.prefs.edit().putString("browserEngine",enabled?"gecko":"system").commit();
    // The retained System WebView is only loaded when explicitly selected.
    if(!enabled){legacy=new WebView(context);legacy.getSettings().setBlockNetworkLoads(true);addView(legacy,new FrameLayout.LayoutParams(-1,-1));}
    if(enabled)owner.handler.post(this::initialize);
  }
  static boolean active(Object web){return web instanceof GeckoWebView&&((GeckoWebView)web).enabled;}
  private void initialize(){
    if(!enabled||destroyed||runtime!=null||failed)return;
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
        .accept(value->{if(destroyed)return;extension=value;extension.setMessageDelegate(routeMessages,"pocketroute");open();},error->{if(!destroyed)failure("浏览器初始化失败，可切换系统内核重试");});
    }catch(Exception error){failure("新内核未能启动，可切换系统内核重试");}
  }
  private final WebExtension.MessageDelegate routeMessages=new WebExtension.MessageDelegate(){
    @Override public void onConnect(WebExtension.Port port){
      if(destroyed||port.sender.environmentType!=WebExtension.MessageSender.ENV_TYPE_EXTENSION)return;
      WebExtension.Port previous=routePort;
      routePort=port;port.setDelegate(new WebExtension.PortDelegate(){
        @Override public void onPortMessage(Object message,WebExtension.Port incoming){
          if(!(message instanceof JSONObject)||incoming!=routePort)return;JSONObject data=(JSONObject)message;
          if("cookies".equals(data.optString("kind")))cookieCallbacks.complete(incoming,data.optInt("id"),data.optBoolean("error")?null:data.optString("value"));
        }
        @Override public void onDisconnect(WebExtension.Port incoming){if(routePort==incoming)routePort=null;cookieCallbacks.cancel(incoming);}
      });
      if(previous!=null&&previous!=port)cookieCallbacks.cancel(previous);
    }
    @Override public GeckoResult<Object> onMessage(String app,Object message,WebExtension.MessageSender sender){
      if(!"pocketroute".equals(app)||!(message instanceof JSONObject)||sender.environmentType!=WebExtension.MessageSender.ENV_TYPE_EXTENSION)return GeckoResult.fromValue(blocked().toString());
      JSONObject request=(JSONObject)message;
      if("ready".equals(request.optString("kind")))return GeckoResult.fromValue(null);
      if(!"route".equals(request.optString("kind")))return GeckoResult.fromValue(blocked().toString());
      // Native callbacks accept primitive values; Port.postMessage performs its own bundle conversion.
      return GeckoResult.fromValue(route(request.optString("url")).toString());
    }
  };
  JSONObject blocked(){return J.obj("type","socks","host","127.0.0.1","port",9,"proxyDNS",true,"failoverTimeout",1);}
  JSONObject route(String target){
    if(destroyed||!enabled||owner.guard==null||!owner.guard.allowed()||!allowedUrl(target.startsWith("wss://")?"https"+target.substring(3):target.startsWith("ws://")?"http"+target.substring(2):target))return blocked();
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
    if(!enabled||destroyed)return;
    if(surface==null){surface=new GeckoView(displayContext);addView(surface,new FrameLayout.LayoutParams(-1,-1));}
    primary=newSession();current=primary;primary.open(runtime);surface.setSession(primary);configure(desktop,owner.privacy.level());ready=true;
    if(!queued.isEmpty()){String target=queued;queued="";loadUrl(target);}
  }
  GeckoSession newSession(){
    // Isolation comes from existing Android processes and distinct profile directories.
    // Default cookie storage remains usable by the official cookie API in this runtime.
    GeckoSession session=new GeckoSession(new GeckoSessionSettings.Builder()
      .userAgentMode(desktop?GeckoSessionSettings.USER_AGENT_MODE_DESKTOP:GeckoSessionSettings.USER_AGENT_MODE_MOBILE)
      .viewportMode(desktop?GeckoSessionSettings.VIEWPORT_MODE_DESKTOP:GeckoSessionSettings.VIEWPORT_MODE_MOBILE).build());
    locations.put(session,"");backStates.put(session,false);
    session.getWebExtensionController().setMessageDelegate(extension,pageMessages,"pocketpage");
    session.setNavigationDelegate(new GeckoSession.NavigationDelegate(){
      @Override public GeckoResult<AllowOrDeny> onLoadRequest(GeckoSession s,LoadRequest request){
        boolean blob=request.uri!=null&&request.uri.startsWith("blob:")&&MainActivity.chatUrl(request.uri.substring(5));
        boolean allowed=!destroyed&&("about:blank".equals(request.uri)||owner.guard.allowed()&&(allowedUrl(request.uri)||blob));
        if(!allowed&&s==current)owner.setStatus("连接尚未受保护，网页已暂停加载");
        return GeckoResult.fromValue(allowed?AllowOrDeny.ALLOW:AllowOrDeny.DENY);
      }
      @Override public void onLocationChange(GeckoSession s,String target,List<GeckoSession.PermissionDelegate.ContentPermission> permissions,Boolean gesture){
        if(destroyed||!locations.containsKey(s))return;locations.put(s,target);if(s!=current)return;url=target;if(MainActivity.chatUrl(target))owner.prefs.edit().putString("url",target).apply();
      }
      @Override public void onCanGoBack(GeckoSession s,boolean value){if(destroyed||!locations.containsKey(s))return;backStates.put(s,value);if(s==current)canBack=value;}
      @Override public GeckoResult<GeckoSession> onNewSession(GeckoSession s,String target){
        if(destroyed||s!=current||popups.size()>=8||!owner.guard.allowed()||!(target==null||target.isEmpty()||"about:blank".equals(target)||allowedUrl(target)))return GeckoResult.fromValue(null);
        GeckoSession popup=newSession();popups.add(popup);
        locations.put(popup,target==null?"":target);
        owner.handler.post(()->{if(destroyed||!popups.contains(popup))return;activate(popup);});
        return GeckoResult.fromValue(popup);
      }
      @Override public GeckoResult<String> onLoadError(GeckoSession s,String target,WebRequestError error){
        if(!destroyed&&s==current&&!"about:blank".equals(target)){owner.pageError="网页连接失败，请检查当前环境网络或重新加载";owner.finishNavigation(owner.pageError,false);}
        return null;
      }
    });
    session.setProgressDelegate(new GeckoSession.ProgressDelegate(){
      @Override public void onPageStart(GeckoSession s,String target){if(destroyed||!locations.containsKey(s))return;loadingTargets.put(s,target);painted.remove(s);WebExtension.Port old=ports.remove(s);if(old!=null)callbacks.cancel(old);if(s==current&&!"about:blank".equals(target)){url=target;scale=1;if(client!=null)client.onPageStarted(null,target,null);}}
      @Override public void onPageStop(GeckoSession s,boolean success){String target=loadingTargets.get(s);if(destroyed||s!=current||target==null||"about:blank".equals(target)||crashed.contains(s))return;if(success&&client!=null){if(MainActivity.chatUrl(url))readCookies(MainActivity.ORIGIN,value->{if(value!=null)cookieStamp=NativeNetwork.hash(value);});pageVisible(s);client.onPageFinished(null,url);}else if(!success&&owner.pageError.isEmpty()){owner.pageError="网页暂时未能加载，请重新加载或检查网络";owner.finishNavigation(owner.pageError,false);}}
    });
    session.setContentDelegate(new GeckoSession.ContentDelegate(){
      @Override public void onCloseRequest(GeckoSession s){closePopup(s);}
      @Override public void onCrash(GeckoSession s){contentStopped(s,"网页进程已退出，点按重新加载可恢复当前环境");}
      @Override public void onKill(GeckoSession s){contentStopped(s,"网页被系统关闭，点按重新加载可恢复当前环境");}
      @Override public void onFirstContentfulPaint(GeckoSession s){pageVisible(s);}
      @Override public void onExternalResponse(GeckoSession s,WebResponse response){
        if(s==current&&download!=null)download.onDownloadStart(response.uri,metadata.userAgent,header(response,"Content-Disposition"),header(response,"Content-Type"),-1);
      }
    });
    session.setPromptDelegate(new GeckoSession.PromptDelegate(){
      @Override public GeckoResult<PromptResponse> onFilePrompt(GeckoSession s,FilePrompt prompt){
        GeckoResult<PromptResponse> result=new GeckoResult<>();
        if(chrome==null||s!=current){result.complete(prompt.dismiss());return result;}
        WebChromeClient.FileChooserParams params=new WebChromeClient.FileChooserParams(){
          @Override public int getMode(){return prompt.type==FilePrompt.Type.MULTIPLE?MODE_OPEN_MULTIPLE:MODE_OPEN;}
          @Override public String[] getAcceptTypes(){return prompt.mimeTypes;}
          @Override public boolean isCaptureEnabled(){return false;}
          @Override public CharSequence getTitle(){return prompt.title;}
          @Override public String getFilenameHint(){return "";}
          @Override public Intent createIntent(){return new Intent(Intent.ACTION_OPEN_DOCUMENT).setType("*/*").addCategory(Intent.CATEGORY_OPENABLE);}
        };
        boolean handled=chrome.onShowFileChooser(null,uris->result.complete(uris==null?prompt.dismiss():prompt.confirm(getContext(),uris)),params);
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
      if(destroyed||source==null||!locations.containsKey(source)||!port.sender.isTopLevel()||!"pocketpage".equals(port.name))return;
      WebExtension.Port previous=ports.put(source,port);port.setDelegate(new WebExtension.PortDelegate(){
        @Override public void onPortMessage(Object message,WebExtension.Port incoming){
          if(!(message instanceof JSONObject)||source!=current||incoming!=ports.get(source))return;
          JSONObject data=(JSONObject)message;String kind=data.optString("kind");
          if("result".equals(kind))callbacks.complete(incoming,data.optInt("id"),data.optString("result","null"));
          else if("reply".equals(kind)&&MainActivity.chatUrl(port.sender.url)&&MainActivity.chatUrl(getUrl())&&owner.webObserver!=null){String text=data.optString("text");if(text.length()<=2*1024*1024)owner.webObserver.receive(J.parse(text));}
          else if("ready".equals(kind)&&owner.webObserver!=null)owner.webObserver.pageReady();
          else if("scale".equals(kind)){float next=(float)data.optDouble("value",scale),old=scale;if(next>0){scale=next;if(client!=null)client.onScaleChanged(null,old,next);}}
        }
        @Override public void onDisconnect(WebExtension.Port incoming){if(ports.get(source)==incoming)ports.remove(source);callbacks.cancel(incoming);}
      });
      if(previous!=null&&previous!=port)callbacks.cancel(previous);
    }
  };
  protected boolean allowedUrl(String target){return target!=null&&BrowserNetworkGuard.publicHttps(Uri.parse(target));}
  static String header(WebResponse response,String name){for(Map.Entry<String,String> entry:response.headers.entrySet())if(name.equalsIgnoreCase(entry.getKey()))return entry.getValue();return null;}
  void readCookies(String target,ValueCallback<String> callback){
    if(destroyed||!enabled||routePort==null||!allowedUrl(target)){callback.onReceiveValue(null);return;}
    WebExtension.Port port=routePort;int id=cookieCallbacks.add(port,callback::onReceiveValue,5000);
    try{port.postMessage(J.obj("kind","cookies","id",id,"url",target));}catch(Exception error){cookieCallbacks.complete(port,id,null);}
  }
  String downloadCookies(String target)throws IOException{
    if(Looper.myLooper()==Looper.getMainLooper())throw new IOException("不能在界面线程等待 Cookie");
    CountDownLatch completed=new CountDownLatch(1);String[] result={null};
    owner.handler.post(()->readCookies(target,value->{result[0]=value;completed.countDown();}));
    try{if(!completed.await(7,TimeUnit.SECONDS)||result[0]==null)throw new IOException("当前环境的登录信息暂不可用，请重试下载");return result[0];}
    catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException("下载已暂停");}
  }
  private void failure(String message){failed=true;owner.pageError=message;owner.finishNavigation(message,false);}
  private void pageVisible(GeckoSession session){
    String target=loadingTargets.get(session);
    if(destroyed||session!=current||target==null||"about:blank".equals(target)||crashed.contains(session)||!painted.add(session))return;
    if(client!=null)client.onPageCommitVisible(null,url);
  }
  private void contentStopped(GeckoSession session,String message){
    if(destroyed||!locations.containsKey(session))return;
    crashed.add(session);painted.remove(session);WebExtension.Port port=ports.remove(session);if(port!=null)callbacks.cancel(port);
    if(session==current){owner.webObserver.suspendUnconfirmed("网页进程已关闭，原发送结果需要核对");failure(message);}
  }
  private void activate(GeckoSession session){
    GeckoSession previous=current;
    if(surface.getSession()!=null)surface.releaseSession();
    if(previous!=null){previous.setActive(false);WebExtension.Port port=ports.get(previous);if(port!=null)callbacks.cancel(port);}
    current=session;url=locations.getOrDefault(session,"");canBack=backStates.getOrDefault(session,false);scale=1;
    failed=crashed.contains(session);
    if(!failed){surface.setSession(session);session.setActive(!owner.browserPaused);}
    configure(desktop,owner.privacy.level());
    if(!url.isEmpty()&&!"about:blank".equals(url)){
      owner.reading.started(url);if(painted.contains(session))owner.reading.visible(url);
    }
  }
  void configure(boolean desktop,int protection){
    this.desktop=desktop;
    for(GeckoSession session:new ArrayList<>(locations.keySet())){session.getSettings().setUserAgentMode(desktop?GeckoSessionSettings.USER_AGENT_MODE_DESKTOP:GeckoSessionSettings.USER_AGENT_MODE_MOBILE);session.getSettings().setViewportMode(desktop?GeckoSessionSettings.VIEWPORT_MODE_DESKTOP:GeckoSessionSettings.VIEWPORT_MODE_MOBILE);session.getSettings().setUseTrackingProtection(protection>0);}
    if(current!=null&&current.isOpen()){GeckoSession source=current;source.getUserAgent().accept(value->{if(!destroyed&&source==current)metadata.userAgent=value;},error->{});}
  }
  void useEngine(boolean value){if(value!=enabled)throw new IllegalStateException("切换内核需要重新打开当前环境");}
  boolean closePopup(){
    return closePopup(current);
  }
  private boolean closePopup(GeckoSession old){
    if(destroyed||!popups.remove(old))return false;
    if(old==current){activate(popups.isEmpty()?primary:popups.get(popups.size()-1));owner.pageError="";if(crashed.contains(current))contentStopped(current,"上一页被系统关闭，点按重新加载可恢复");else{owner.beginNavigation(url,"正在返回上一页…");if(client!=null&&painted.contains(current)){client.onPageCommitVisible(null,url);client.onPageFinished(null,url);}}}
    WebExtension.Port port=ports.remove(old);if(port!=null)callbacks.cancel(port);
    locations.remove(old);backStates.remove(old);loadingTargets.remove(old);painted.remove(old);crashed.remove(old);
    if(old.isOpen())old.close();return true;
  }
  public void loadUrl(String target){
    if(destroyed)return;if(!enabled){system().loadUrl(target);return;}queued=target;
    if(!ready||current==null||!owner.guard.allowed())return;
    if(crashed.contains(current)){
      try{if(surface.getSession()!=null)surface.releaseSession();if(current.isOpen())current.close();current.open(runtime);surface.setSession(current);current.setActive(!owner.browserPaused);crashed.remove(current);failed=false;canBack=false;backStates.put(current,false);configure(desktop,owner.privacy.level());}
      catch(Exception error){failure("网页暂未恢复，请重新打开当前环境");return;}
    }
    queued="";current.loadUri(target);
  }
  public String getUrl(){return enabled?url:system().getUrl();}
  public void evaluateJavascript(String code,ValueCallback<String> callback){
    if(destroyed){if(callback!=null)callback.onReceiveValue("null");return;}
    if(!enabled){system().evaluateJavascript(code,callback);return;}
    WebExtension.Port port=ports.get(current);if(port==null){if(callback!=null)callback.onReceiveValue("null");return;}
    int id=callbacks.add(port,callback==null?null:callback::onReceiveValue,10000);
    try{port.postMessage(J.obj("kind","evaluate","id",id,"code",code));}catch(Exception error){callbacks.complete(port,id,"null");}
  }
  public void stopLoading(){
    if(enabled){queued="";if(current!=null){loadingTargets.remove(current);current.stop();}}
    else system().stopLoading();
  }
  public void setWebViewClient(WebViewClient value){client=value;if(!enabled)system().setWebViewClient(value);}
  public void setWebChromeClient(WebChromeClient value){chrome=value;if(!enabled)system().setWebChromeClient(value);}
  public void setDownloadListener(DownloadListener value){download=value;if(!enabled)system().setDownloadListener(value);}
  public void onPause(){if(enabled){if(current!=null)current.setActive(false);}else system().onPause();}
  public void onResume(){if(enabled){if(current!=null)current.setActive(true);}else system().onResume();}
  public void pauseTimers(){if(!enabled)system().pauseTimers();}
  public void resumeTimers(){if(!enabled)system().resumeTimers();}
  public boolean canGoBack(){return enabled?canBack||!popups.isEmpty():system().canGoBack();}
  public void goBack(){if(enabled){if(canBack)current.goBack();else closePopup();}else system().goBack();}
  public float getScale(){return enabled?scale:system().getScale();}
  public void setInitialScale(int percent){if(!enabled)system().setInitialScale(percent);}
  public void zoomBy(float factor){
    if(!enabled){system().zoomBy(factor);return;}
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
