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
  @Override public boolean dispatchTouchEvent(MotionEvent event){if(zoomTarget!=null&&event.getActionMasked()==MotionEvent.ACTION_DOWN)cancelZoom();if(touches!=null&&touches.onTouch(this,event))return true;boolean handled=super.dispatchTouchEvent(event);syncSurfaceOrigin();return handled;}
  void destroy(){
    if(destroyed)return;destroyed=true;
    cancelZoom();owner.handler.removeCallbacks(recovery);owner.handler.removeCallbacks(checkpoint);saveCheckpoint();
    callbacks.clear();cookieCallbacks.clear();
    if(surface!=null&&surface.getSession()!=null)surface.releaseSession();
    for(GeckoSession session:new ArrayList<>(locations.keySet()))if(session.isOpen())session.close();
    if(primary!=null&&primary.isOpen())primary.close();
    ports.clear();popups.clear();locations.clear();backStates.clear();pageScales.clear();viewportWidths.clear();loadingTargets.clear();pendingLoads.clear();painted.clear();usable.clear();crashed.clear();states.clear();
    routePort=null;ready=false;
    uploadWorker.execute(()->{for(GeckoUploadFiles.Selection files:uploadFiles)files.delete();uploadFiles.clear();});uploadWorker.shutdown();
    if(legacy!=null)legacy.destroy();
  }

  static final String VERSION="GeckoView 157.0";
  final ChatSession owner;
  GeckoView surface;GeckoRuntime runtime;WebExtension extension;GeckoSession primary,current;
  final ArrayList<GeckoSession> popups=new ArrayList<>();
  final Map<GeckoSession,WebExtension.Port> ports=new IdentityHashMap<>();
  final Map<GeckoSession,String> locations=new IdentityHashMap<>();
  final Map<GeckoSession,Boolean> backStates=new IdentityHashMap<>();
  final Map<GeckoSession,Float> pageScales=new IdentityHashMap<>(),viewportWidths=new IdentityHashMap<>();
  final Map<GeckoSession,String> loadingTargets=new IdentityHashMap<>();
  final Set<GeckoSession> pendingLoads=Collections.newSetFromMap(new IdentityHashMap<>());
  final Set<GeckoSession> painted=Collections.newSetFromMap(new IdentityHashMap<>());
  final Set<GeckoSession> usable=Collections.newSetFromMap(new IdentityHashMap<>());
  final Set<GeckoSession> crashed=Collections.newSetFromMap(new IdentityHashMap<>());
  final Map<GeckoSession,GeckoSession.SessionState> states=new IdentityHashMap<>();
  final BrowserSessionStore sessionStore;
  final ExecutorService uploadWorker=Executors.newSingleThreadExecutor();
  final List<GeckoUploadFiles.Selection> uploadFiles=new ArrayList<>();
  GeckoSession.SessionState startupState;
  boolean checkpointReady,routePrepared;float readingLayout=1;long zoomEpoch,recoveryWindow;int contentRecoveries;
  GeckoSession zoomTarget;long zoomStarted;float zoomX,zoomY,zoomRadius;
  final Runnable recovery=()->recoverClosed();
  final Runnable checkpoint=this::saveCheckpoint;
  final BrowserBridgeRequests callbacks,cookieCallbacks;WebExtension.Port routePort;String cookieStamp="";
  interface ResponseDownload {void receive(WebResponse response);}
  ResponseDownload responseDownload;
  WebViewClient client;WebChromeClient chrome;DownloadListener download;
  boolean enabled,ready,failed,desktop,canBack,destroyed;String url="",queued="";float scale=1;

  GeckoWebView(Context context,ChatSession session){
    super(context);owner=session;displayContext=new MutableContextWrapper(context);sessionStore=new BrowserSessionStore(context);
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
      sessionStore.read(value->owner.handler.post(()->{if(destroyed)return;startupState=value==null?null:GeckoSession.SessionState.fromString(value);checkpointReady=true;maybeOpen();}));
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
        .accept(value->{if(destroyed)return;extension=value;extension.setMessageDelegate(routeMessages,"pocketroute");maybeOpen();},error->{if(!destroyed)failure("浏览器初始化失败，可切换系统内核重试");});
    }catch(Exception error){failure("新内核未能启动，可切换系统内核重试");}
  }
  private final WebExtension.MessageDelegate routeMessages=new WebExtension.MessageDelegate(){
    @Override public void onConnect(WebExtension.Port port){
      if(destroyed||port.sender.environmentType!=WebExtension.MessageSender.ENV_TYPE_EXTENSION)return;
      WebExtension.Port previous=routePort;
      routePort=port;port.setDelegate(new WebExtension.PortDelegate(){
        @Override public void onPortMessage(Object message,WebExtension.Port incoming){
          if(!(message instanceof JSONObject)||incoming!=routePort)return;JSONObject data=(JSONObject)message;
          if("ready".equals(data.optString("kind"))){routePrepared=true;maybeOpen();return;}
          if("cookieRecoveryError".equals(data.optString("kind"))){failure("登录状态暂未恢复，请重新打开当前环境");return;}
          if("cookies".equals(data.optString("kind")))cookieCallbacks.complete(incoming,data.optInt("id"),data.optBoolean("error")?null:data.optString("value"));
        }
        @Override public void onDisconnect(WebExtension.Port incoming){if(routePort==incoming)routePort=null;cookieCallbacks.cancel(incoming);}
      });
      if(previous!=null&&previous!=port)cookieCallbacks.cancel(previous);
      port.postMessage(J.obj("kind","prepare"));
    }
    @Override public GeckoResult<Object> onMessage(String app,Object message,WebExtension.MessageSender sender){
      if(!"pocketroute".equals(app)||!(message instanceof JSONObject)||sender.environmentType!=WebExtension.MessageSender.ENV_TYPE_EXTENSION)return GeckoResult.fromValue(blocked().toString());
      JSONObject request=(JSONObject)message;
      if("ready".equals(request.optString("kind"))){routePrepared=true;maybeOpen();return GeckoResult.fromValue(null);}
      if("cookieRecoveryError".equals(request.optString("kind"))){failure("登录状态暂未恢复，请重新打开当前环境");return GeckoResult.fromValue(null);}
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
    // Choose the official transform-capable backend once. Changing a live SDK
    // surface backend can leave its surface callback detached (157.0 SDK).
    if(surface==null){surface=new GeckoView(displayContext);surface.setViewBackend(GeckoView.BACKEND_TEXTURE_VIEW);addView(surface,new FrameLayout.LayoutParams(-1,-1));}
    primary=newSession();current=primary;primary.open(runtime);surface.setSession(primary);configure(desktop,owner.privacy.level());ready=true;
    if(!queued.isEmpty()){String target=queued;queued="";loadUrl(target);}
  }
  private void maybeOpen(){if(!destroyed&&!failed&&!ready&&extension!=null&&checkpointReady&&routePrepared)open();}
  GeckoSession newSession(){
    // Isolation comes from existing Android processes and distinct profile directories.
    // Default cookie storage remains usable by the official cookie API in this runtime.
    GeckoSession session=new GeckoSession(new GeckoSessionSettings.Builder()
      .userAgentMode(desktop?GeckoSessionSettings.USER_AGENT_MODE_DESKTOP:GeckoSessionSettings.USER_AGENT_MODE_MOBILE)
      .viewportMode(GeckoSessionSettings.VIEWPORT_MODE_MOBILE).build());
    locations.put(session,"");backStates.put(session,false);
    session.getWebExtensionController().setMessageDelegate(extension,pageMessages,"pocketpage");
    session.setNavigationDelegate(new GeckoSession.NavigationDelegate(){
      @Override public GeckoResult<AllowOrDeny> onLoadRequest(GeckoSession s,LoadRequest request){
        boolean blob=request.uri!=null&&request.uri.startsWith("blob:")&&allowedUrl(request.uri.substring(5));
        boolean allowed=!destroyed&&("about:blank".equals(request.uri)||owner.guard.allowed()&&(allowedUrl(request.uri)||blob));
        if(!allowed&&s==current)owner.setStatus("连接尚未受保护，网页已暂停加载");
        return GeckoResult.fromValue(allowed?AllowOrDeny.ALLOW:AllowOrDeny.DENY);
      }
      @Override public void onLocationChange(GeckoSession s,String target,List<GeckoSession.PermissionDelegate.ContentPermission> permissions,Boolean gesture){
        if(destroyed||!locations.containsKey(s))return;boolean committed=pendingLoads.remove(s);locations.put(s,target);
        if(committed){painted.remove(s);usable.remove(s);pageScales.remove(s);viewportWidths.remove(s);loadingTargets.put(s,target);}
        if(s!=current)return;url=target;
        if(committed&&!"about:blank".equals(target)){cancelZoom();if(client!=null)client.onPageStarted(null,target,null);}if(MainActivity.chatUrl(target)&&!LoginPagePolicy.login(target))owner.prefs.edit().putString("url",target).apply();
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
      // A download starts a network load without replacing the current document.
      // Only an authoritative location commit may invalidate its state or bridge.
      @Override public void onPageStart(GeckoSession s,String target){if(destroyed||!locations.containsKey(s))return;loadingTargets.put(s,target);pendingLoads.add(s);}

      @Override public void onPageStop(GeckoSession s,boolean success){String target=loadingTargets.get(s);boolean uncommitted=pendingLoads.remove(s);if(uncommitted&&usable.contains(s)){loadingTargets.put(s,locations.get(s));return;}if(destroyed||s!=current||target==null||"about:blank".equals(target)||crashed.contains(s))return;if(success&&client!=null){if(MainActivity.chatUrl(url))readCookies(MainActivity.ORIGIN,value->{if(value!=null)cookieStamp=NativeNetwork.hash(value);});pageVisible(s);client.onPageFinished(null,url);}else if(!success&&owner.pageError.isEmpty()){owner.pageError="网页暂时未能加载，请重新加载或检查网络";owner.finishNavigation(owner.pageError,false);}}
      @Override public void onSessionStateChange(GeckoSession s,GeckoSession.SessionState state){if(destroyed||!locations.containsKey(s)||state.size()==0)return;states.put(s,new GeckoSession.SessionState(state));if(s==primary){owner.handler.removeCallbacks(checkpoint);owner.handler.postDelayed(checkpoint,300);}}
    });
    session.setContentDelegate(new GeckoSession.ContentDelegate(){
      @Override public void onCloseRequest(GeckoSession s){closePopup(s);}
      @Override public void onCrash(GeckoSession s){contentStopped(s,"网页进程已退出，点按重新加载可恢复当前环境");}
      @Override public void onKill(GeckoSession s){contentStopped(s,"网页被系统关闭，点按重新加载可恢复当前环境");}
      @Override public void onFirstContentfulPaint(GeckoSession s){pageVisible(s);}
      @Override public void onExternalResponse(GeckoSession s,WebResponse response){
        if(!destroyed&&s==current&&owner.guard.allowed()&&responseDownload!=null){pendingLoads.remove(s);loadingTargets.put(s,locations.get(s));responseDownload.receive(response);return;}
        if(response.body!=null)try{response.body.close();}catch(IOException ignored){}
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
        final long uploadEpoch=owner.navigationEpoch;
        java.util.concurrent.atomic.AtomicBoolean selected=new java.util.concurrent.atomic.AtomicBoolean();
        boolean handled=chrome.onShowFileChooser(null,uris->{
          if(!selected.compareAndSet(false,true))return;
          if(uris==null||destroyed){if(!prompt.isComplete())result.complete(prompt.dismiss());return;}
          uploadWorker.execute(()->{try{
            GeckoUploadFiles.Selection files=GeckoUploadFiles.prepare(owner.context,uris);
            owner.handler.post(()->{if(destroyed||s!=current||!s.isOpen()||uploadEpoch!=owner.navigationEpoch||prompt.isComplete()){new Thread(files::delete,"upload-cleanup").start();if(!prompt.isComplete())result.complete(prompt.dismiss());return;}uploadFiles.add(files);result.complete(prompt.confirm(owner.context,files.files));});
          }catch(IOException error){owner.handler.post(()->{if(!prompt.isComplete())result.complete(prompt.dismiss());if(!destroyed){owner.setStatus(error.getMessage());android.widget.Toast.makeText(displayContext,error.getMessage(),android.widget.Toast.LENGTH_LONG).show();}});}});
        },params);
        if(!handled&&selected.compareAndSet(false,true)&&!prompt.isComplete())result.complete(prompt.dismiss());return result;
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
          if(!(message instanceof JSONObject)||incoming!=ports.get(source))return;
          JSONObject data=(JSONObject)message;String kind=data.optString("kind");
          if("scale".equals(kind)){
            float next=(float)data.optDouble("value",0),width=(float)data.optDouble("width",0);
            if(Float.isFinite(next)&&next>0)pageScales.put(source,next);
            if(Float.isFinite(width)&&width>0)viewportWidths.put(source,width);
            if(source==current&&Float.isFinite(next)&&next>0){float old=scale;scale=next*readingLayout;owner.reading.viewportMeasured(width*readingLayout);if(client!=null)client.onScaleChanged(null,old,scale);}return;
          }
          if(source!=current)return;
          if("documentReady".equals(kind)&&data.optString("url").equals(getUrl())&&!crashed.contains(source)){
            usable.add(source);pageVisible(source);
            owner.changed();return;
          }
          if("result".equals(kind))callbacks.complete(incoming,data.optInt("id"),data.optString("result","null"));
          else if("reply".equals(kind)&&MainActivity.chatUrl(port.sender.url)&&MainActivity.chatUrl(getUrl())&&owner.webObserver!=null){String text=data.optString("text");if(text.length()<=2*1024*1024)owner.webObserver.receive(J.parse(text));}
          else if("ready".equals(kind)&&owner.webObserver!=null)owner.webObserver.pageReady();
        }
        @Override public void onDisconnect(WebExtension.Port incoming){if(ports.get(source)==incoming)ports.remove(source);callbacks.cancel(incoming);}
      });
      if(previous!=null&&previous!=port)callbacks.cancel(previous);
    }
  };
  protected boolean allowedUrl(String target){return target!=null&&BrowserNetworkGuard.publicHttps(Uri.parse(target));}
  boolean readingPage(String target){return BrowserReadingPolicy.chat(target)&&!LoginPagePolicy.login(target);}
  static String header(WebResponse response,String name){for(Map.Entry<String,String> entry:response.headers.entrySet())if(name.equalsIgnoreCase(entry.getKey()))return entry.getValue();return "";}
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
  boolean hasVisibleDocument(){return enabled&&current!=null&&current.isOpen()&&!failed&&!crashed.contains(current)&&usable.contains(current);}
  private void pageVisible(GeckoSession session){
    String target=loadingTargets.get(session);
    if(destroyed||session!=current||target==null||"about:blank".equals(target)||crashed.contains(session)||!painted.add(session))return;
    if(client!=null)client.onPageCommitVisible(null,url);
  }
  private void contentStopped(GeckoSession session,String message){
    if(destroyed||!locations.containsKey(session))return;
    crashed.add(session);pendingLoads.remove(session);painted.remove(session);usable.remove(session);WebExtension.Port port=ports.remove(session);if(port!=null)callbacks.cancel(port);
    if(session==current){cancelZoom();failed=true;owner.webObserver.suspendUnconfirmed("网页进程已关闭，原发送结果需要核对");
      if(owner.uiVisible&&owner.guard.allowed()&&canRecoverAutomatically()){owner.manualAttention=false;owner.beginNavigation(url,"正在恢复当前网页…");owner.handler.removeCallbacks(recovery);owner.handler.postDelayed(recovery,250);}
      else if(owner.uiVisible)failure(message);
    }
  }
  private void saveCheckpoint(){GeckoSession.SessionState state=states.get(primary);if(state!=null)sessionStore.write(state.toString());}
  void checkpointState(){if(!enabled||destroyed)return;for(GeckoSession session:new ArrayList<>(locations.keySet()))if(session.isOpen())session.flushSessionState();saveCheckpoint();}
  private boolean canRecoverAutomatically(){long now=SystemClock.elapsedRealtime();if(now-recoveryWindow>60000){recoveryWindow=now;contentRecoveries=0;}return contentRecoveries<2;}
  boolean recoverClosed(){
    if(destroyed||!enabled||current==null||!crashed.contains(current)||!owner.uiVisible||!owner.guard.allowed())return false;
    owner.handler.removeCallbacks(recovery);contentRecoveries++;
    String target=locations.getOrDefault(current,owner.resumeUrl());
    if(!allowedUrl(target))target=owner.resumeUrl();
    GeckoSession.SessionState state=states.get(current);
    if(!reopenCurrent())return false;
    owner.pageMemory.restorePending=true;
    owner.pageError="";owner.manualAttention=false;owner.beginNavigation(target,"正在恢复当前网页…");
    if(state!=null&&state.size()>0)current.restoreState(state);else current.loadUri(target);
    return true;
  }
  private boolean reopenCurrent(){try{
    if(surface.getSession()!=null)surface.releaseSession();if(current.isOpen())current.close();current.open(runtime);surface.setSession(current);
    current.setActive(!owner.browserPaused);crashed.remove(current);failed=false;configure(desktop,owner.privacy.level());return true;
  }catch(Exception error){failure("网页暂未恢复，请重新打开当前环境");return false;}}
  private void activate(GeckoSession session){
    cancelZoom();
    GeckoSession previous=current;
    if(surface.getSession()!=null)surface.releaseSession();
    if(previous!=null){if(previous.isOpen())previous.setActive(false);WebExtension.Port port=ports.get(previous);if(port!=null)callbacks.cancel(port);}
    current=session;url=locations.getOrDefault(session,"");canBack=backStates.getOrDefault(session,false);scale=pageScales.getOrDefault(session,1f)*readingLayout;
    failed=crashed.contains(session);
    if(!failed){surface.setSession(session);session.setActive(!owner.browserPaused);}
    configure(desktop,owner.privacy.level());
    if(!url.isEmpty()&&!"about:blank".equals(url)){
      owner.reading.started(url);owner.reading.viewportMeasured(viewportWidths.getOrDefault(session,0f)*readingLayout);if(painted.contains(session))owner.reading.visible(url);
    }
  }
  void configure(boolean desktop,int protection){
    this.desktop=desktop;
    for(GeckoSession session:new ArrayList<>(locations.keySet())){session.getSettings().setUserAgentMode(desktop?GeckoSessionSettings.USER_AGENT_MODE_DESKTOP:GeckoSessionSettings.USER_AGENT_MODE_MOBILE);session.getSettings().setViewportMode(GeckoSessionSettings.VIEWPORT_MODE_MOBILE);session.getSettings().setUseTrackingProtection(protection>0);}
    if(current!=null&&current.isOpen()){GeckoSession source=current;source.getUserAgent().accept(value->{if(!destroyed&&source==current&&this.desktop==desktop)metadata.userAgent=value;},error->{});}
  }
  void useEngine(boolean value){if(value!=enabled)throw new IllegalStateException("切换内核需要重新打开当前环境");}
  boolean closePopup(){
    return closePopup(current);
  }
  private boolean closePopup(GeckoSession old){
    if(destroyed||!popups.remove(old))return false;
    if(old==current){activate(popups.isEmpty()?primary:popups.get(popups.size()-1));owner.pageError="";if(crashed.contains(current))contentStopped(current,"上一页被系统关闭，点按重新加载可恢复");else{owner.beginNavigation(url,"正在返回上一页…");if(client!=null&&painted.contains(current)){client.onPageCommitVisible(null,url);client.onPageFinished(null,url);}}}
    WebExtension.Port port=ports.remove(old);if(port!=null)callbacks.cancel(port);
    locations.remove(old);backStates.remove(old);pageScales.remove(old);viewportWidths.remove(old);loadingTargets.remove(old);pendingLoads.remove(old);painted.remove(old);usable.remove(old);crashed.remove(old);states.remove(old);
    if(old.isOpen())old.close();return true;
  }
  public void loadUrl(String target){
    if(destroyed)return;if(!enabled){system().loadUrl(target);return;}queued=target;
    if(!ready||current==null||!owner.guard.allowed())return;
    if(crashed.contains(current)){
      if(!reopenCurrent())return;
    }
    GeckoSession.SessionState saved=startupState;startupState=null;
    if(current==primary&&saved!=null&&target.equals(stateUrl(saved))){queued="";states.put(primary,saved);current.restoreState(saved);return;}
    queued="";current.loadUri(target);
  }
  static String stateUrl(GeckoSession.SessionState state){try{return state.get(state.getCurrentIndex()).getUri();}catch(Exception ignored){return "";}}
  public String getUrl(){return enabled?url:system().getUrl();}
  public void evaluateJavascript(String code,ValueCallback<String> callback){
    if(destroyed){if(callback!=null)callback.onReceiveValue("null");return;}
    if(!enabled){system().evaluateJavascript(code,callback);return;}
    WebExtension.Port port=ports.get(current);if(port==null){if(callback!=null)callback.onReceiveValue("null");return;}
    int id=callbacks.add(port,callback==null?null:callback::onReceiveValue,10000);
    try{port.postMessage(J.obj("kind","evaluate","id",id,"code",code));}catch(Exception error){callbacks.complete(port,id,"null");}
  }
  public void stopLoading(){
    if(enabled){queued="";if(current!=null){loadingTargets.remove(current);pendingLoads.remove(current);current.stop();}}
    else system().stopLoading();
  }
  public void setWebViewClient(WebViewClient value){client=value;if(!enabled)system().setWebViewClient(value);}
  public void setWebChromeClient(WebChromeClient value){chrome=value;if(!enabled)system().setWebChromeClient(value);}
  public void setDownloadListener(DownloadListener value){download=value;if(!enabled)system().setDownloadListener(value);}
  public void onPause(){if(enabled){checkpointState();if(current!=null&&current.isOpen())current.setActive(false);}else system().onPause();}
  public void onResume(){if(enabled){if(current!=null&&crashed.contains(current)&&canRecoverAutomatically())owner.handler.post(recovery);else if(current!=null&&current.isOpen())current.setActive(true);}else system().onResume();}
  public void pauseTimers(){if(!enabled)system().pauseTimers();}
  public void resumeTimers(){if(!enabled)system().resumeTimers();}
  public boolean canGoBack(){return enabled?canBack||!popups.isEmpty():system().canGoBack();}
  public void goBack(){if(enabled){if(canBack)current.goBack();else closePopup();}else system().goBack();}
  public float getScale(){return enabled?scale:system().getScale();}
  boolean requiresViewportMeasurement(){return enabled;}
  public void setInitialScale(int percent){if(!enabled)system().setInitialScale(percent);}
  /** Below native fit, reflow the same document into a larger, uniformly scaled surface. */
  boolean setReadingLayout(float choice){
    if(!enabled)return false;float next=Math.min(1,BrowserReadingPolicy.bounded(choice));if(Math.abs(next-readingLayout)<.001f)return false;
    cancelZoom();float previous=readingLayout;readingLayout=next;scale=scale/previous*next;
    if(surface!=null){surface.setPivotX(0);surface.setPivotY(0);surface.setScaleX(next);surface.setScaleY(next);}
    requestLayout();return true;
  }
  public void zoomBy(float factor){
    if(!enabled){system().zoomBy(factor);return;}
    if(destroyed||failed||current==null||!current.isOpen()||surface==null||factor<=0||!Float.isFinite(factor))return;
    cancelZoom();final GeckoSession target=current;final long started=SystemClock.uptimeMillis(),epoch=zoomEpoch;
    final float x=surface.getWidth()/2f,y=surface.getHeight()/2f,radius=Math.min(surface.getWidth()/5f,48*getResources().getDisplayMetrics().density);
    final float amount=Math.max(.1f,Math.min(10f,factor));
    if(radius<=0)return;
    zoomTarget=target;zoomStarted=started;zoomX=x;zoomY=y;zoomRadius=radius;
    pinch(target,started,MotionEvent.ACTION_DOWN,1,x,y,radius);
    pinch(target,started,MotionEvent.ACTION_POINTER_DOWN|(1<<MotionEvent.ACTION_POINTER_INDEX_SHIFT),2,x,y,radius);
    // ScaleGestureDetector consumes the movement that crosses touch slop as
    // its starting span. Establish that span before applying the requested ratio.
    final float primed=radius*1.6f;
    for(int step=0;step<12;step++){final int n=step;owner.handler.postDelayed(()->{
      if(target!=current||!enabled||destroyed||failed||epoch!=zoomEpoch||!target.isOpen())return;
      float next=primed*(1+(amount-1)*Math.max(0,n-1)/10f);pinch(target,started,MotionEvent.ACTION_MOVE,2,x,y,next);
      if(n==11){pinch(target,started,MotionEvent.ACTION_POINTER_UP|(1<<MotionEvent.ACTION_POINTER_INDEX_SHIFT),2,x,y,next);pinch(target,started,MotionEvent.ACTION_UP,1,x,y,next);zoomTarget=null;}
    },(step+1)*16L);}
  }
  private void cancelZoom(){zoomEpoch++;if(zoomTarget!=null&&zoomTarget.isOpen())pinch(zoomTarget,zoomStarted,MotionEvent.ACTION_CANCEL,1,zoomX,zoomY,zoomRadius);zoomTarget=null;}
  private void pinch(GeckoSession target,long start,int action,int count,float x,float y,float radius){
    MotionEvent.PointerProperties[] properties=new MotionEvent.PointerProperties[count];MotionEvent.PointerCoords[] coordinates=new MotionEvent.PointerCoords[count];
    int[] origin=new int[2];if(surface!=null)surface.getLocationOnScreen(origin);
    for(int i=0;i<count;i++){properties[i]=new MotionEvent.PointerProperties();properties[i].id=i;properties[i].toolType=MotionEvent.TOOL_TYPE_FINGER;coordinates[i]=new MotionEvent.PointerCoords();coordinates[i].x=origin[0]+x+(i==0?-radius:radius);coordinates[i].y=origin[1]+y;coordinates[i].pressure=1;coordinates[i].size=1;}
    MotionEvent event=MotionEvent.obtain(start,SystemClock.uptimeMillis(),action,count,properties,coordinates,0,0,1,1,0,0,InputDevice.SOURCE_TOUCHSCREEN,0);
    event.offsetLocation(-origin[0],-origin[1]);
    target.getPanZoomController().onTouchEvent(event);event.recycle();
  }
  @Override protected void onFocusChanged(boolean gain,int direction,Rect previous){super.onFocusChanged(gain,direction,previous);if(enabled&&gain&&surface!=null)surface.requestFocus();}
  @Override public boolean onInterceptTouchEvent(MotionEvent event){return !enabled&&super.onInterceptTouchEvent(event);}
  @Override protected void onMeasure(int width,int height){super.onMeasure(width,height);if(surface!=null)surface.measure(MeasureSpec.makeMeasureSpec(Math.round(getMeasuredWidth()/readingLayout),MeasureSpec.EXACTLY),MeasureSpec.makeMeasureSpec(Math.round(getMeasuredHeight()/readingLayout),MeasureSpec.EXACTLY));}
  private void syncSurfaceOrigin(){if(surface!=null&&surface.isAttachedToWindow()&&surface.getRootWindowInsets()!=null)surface.gatherTransparentRegion(null);}
  @Override protected void onLayout(boolean changed,int l,int t,int r,int b){super.onLayout(changed,l,t,r,b);if(surface!=null){surface.layout(0,0,surface.getMeasuredWidth(),surface.getMeasuredHeight());syncSurfaceOrigin();}}
}
