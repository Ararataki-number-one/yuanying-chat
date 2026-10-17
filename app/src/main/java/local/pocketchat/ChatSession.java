package local.pocketchat;

import android.content.*;
import android.os.*;
import android.webkit.*;
import android.view.*;
import org.json.*;
import java.io.*;
import java.lang.ref.WeakReference;
import java.util.*;

final class ChatSession {
  interface Observer{void changed();}
  interface Result{void accept(JSONObject value);}
  private static ChatSession instance;
  interface BrowserFactory{GeckoWebView create(Context context,ChatSession owner);}
  static BrowserFactory browserFactory=GeckoWebView::new;
  static ChatSession get(Context c){if(instance==null)instance=new ChatSession(c);return instance;}
  static ChatSession peek(){return instance;}
  final Context context;final SharedPreferences prefs;final Handler handler=new Handler(Looper.getMainLooper());final GeckoWebView web;final BrowserReading reading;final BrowserPrivacy privacy;final BrowserNetworkGuard guard;EnvironmentAudit audit;final WebReplyObserver webObserver;long webConfirmationVersion=0;
  final List<WeakReference<Observer>> observers=new ArrayList<>();String driver="",attachmentDriver="",attachmentOwner="",conversation="",status="准备连接",pageError="",confirmedPrompt="";long confirmationVersion=0;
  JSONObject draftConflict,approvedDraft;JSONObject sentAttachments=new JSONObject();JSONObject state=new JSONObject();long stateEpoch=-1;boolean googleLoginBlocked;volatile JSONObject pending;JSONArray entries=new JSONArray(),attachments=new JSONArray();boolean networkReady=false,uiVisible=false,submitting=false,operation=false,inFlight=false;
  boolean showingCache=false,offline=false,connecting=false,recoveryScheduled=false,manualAttention=false;int recoveryAttempt=0;long recoveryToken=0;volatile long connectionEpoch=0;String networkIdentity="",networkIssue="",connectionStage="未连接";final ConversationStore cache;final WebTranscriptMirror webMirror=new WebTranscriptMirror();final WebTranscriptStore webStore;long lastWebSnapshot=0,syncRun=0;String lastWebUrl="",lastDeliverySignature="";final DeliveryStore deliveries;String activeDeliveryId="";volatile boolean transferActive=false;
  boolean deleted=false,configurationCapture=false;long lastDeferredBrowserAttempt=0;final int environmentGeneration;boolean navigating=false,navigationFailed=false;String navigationTarget="",navigationLabel="";long navigationEpoch=0,navigationStarted=0;long connectionStarted=0,proxyReadyAt=0,navigationMono=0,firstPageVisible=0,pageUsableAt=0;
  final IdentityTemplateController identity;boolean identityApplicationPending;
  final java.util.concurrent.ExecutorService environmentIo=java.util.concurrent.Executors.newSingleThreadExecutor();String environmentSpecIssue="";
  final ConnectionTrace trace=new ConnectionTrace();final PageMemory pageMemory=new PageMemory(this);final NetworkPoolIdentity.DefaultNetwork browserDefaultNetwork=new NetworkPoolIdentity.DefaultNetwork();String appliedIdentity="",requestedConversation="";boolean keepPageCandidate=false,browserPaused=false,spaTransition=false,documentNavigationSeen=false,backgroundAttachmentCheck=false;String spaBefore="",spaSignature="",lastDocumentId="",priorDocumentId="";boolean navigationDispatched=true,awaitNewDocument=false;int spaStable=0,backgroundAttachmentStable=0;
  String stableReply="",progressJob="",progressSignature="";long lastReplyProgress=0;int stableTicks=0;long operationGeneration=0;boolean websiteConnectionIssue,websiteRecovering;
  String observedReplyJob="",observedReplyUrl="",observedReplyKey="",observedReplyRevision="",observedReplyMarkdown="";boolean observedReplyHasFiles;
  ChatSession(Context c){context=c.getApplicationContext();environmentGeneration=ProfileCatalog.get(context).item(Profiles.slot(context)).optInt("generation");cache=new ConversationStore(context);webStore=new WebTranscriptStore(this);deliveries=new DeliveryStore(context);prefs=context.getSharedPreferences("chat",0);sentAttachments=J.parse(prefs.getString("sentAttachments","{}"));pending=J.parse(prefs.getString("pending","{}"));if(pending.length()==0)pending=null;deliveries.recover(pending);
    if(pending!=null&&!BrowserRuntimePolicy.restoresPending(prefs.getString("browserEngine",""),pending.optString("engine"),pending.optString("kind"))){
      // Preserve the original record and draft bytes. A former native/system
      // task is never replayed or bound to a different browser profile.
      prefs.edit().putString("legacyPending",pending.toString()).commit();
      JSONObject receipt=deliveries.get(pending.optString("id"));String previous=receipt==null?"":receipt.optString("state");
      if(!previous.equals("completed")&&!previous.equals("stopped"))deliveries.update(pending.optString("id"),"uncertain","旧版发送结果需要在原网页核对；输入已保留，不会自动重发",pending.optBoolean("attempted"),pending.optString("userKey"),"");
      pending=null;
    }
    if(pending!=null)activeDeliveryId=pending.optString("id");try{entries=new JSONArray();try(InputStream in=context.getAssets().open("page-driver.js")){driver=J.text(in,512*1024);}}catch(Exception ignored){}conversation=prefs.getString("conversation","");
    try(InputStream in=context.getAssets().open("attachment-driver.js")){attachmentDriver=J.text(in,512*1024);}catch(Exception ignored){}
    guard=new BrowserNetworkGuard(this);web=browserFactory.create(context,this);reading=new BrowserReading(this);privacy=new BrowserPrivacy(this);webObserver=new WebReplyObserver(this);webObserver.install();webObserver.restorePending();web.setWebViewClient(client());web.setWebChromeClient(new WebChromeClient());int width=Math.max(400,context.getResources().getDisplayMetrics().widthPixels),height=Math.max(800,context.getResources().getDisplayMetrics().heightPixels);web.measure(View.MeasureSpec.makeMeasureSpec(width,View.MeasureSpec.EXACTLY),View.MeasureSpec.makeMeasureSpec(height,View.MeasureSpec.EXACTLY));web.layout(0,0,width,height);audit=new EnvironmentAudit(this);identity=new IdentityTemplateController(this);identity.load();handler.post(tick);watchNetwork();
  }
  WebViewClient client(){return new WebViewClient(){
    @Override public void onScaleChanged(WebView v,float oldScale,float newScale){reading.scaled(newScale);}
    @Override public WebResourceResponse shouldInterceptRequest(WebView v,WebResourceRequest r){return guard.intercept(r.getUrl());}
    @Override public boolean shouldOverrideUrlLoading(WebView v,WebResourceRequest r){if(!guard.allowed()||!BrowserNetworkGuard.publicHttps(r.getUrl())){setStatus("连接尚未受保护，或地址属于不安全的网络");return true;}return false;}
    @Override public void onPageStarted(WebView v,String url,android.graphics.Bitmap icon){reading.started(url);webObserver.suspendUnconfirmed("网页发生重新加载，原发送结果需要核对");pageError="";googleLoginBlocked=false;if(navigating&&targetMatches(url)){documentNavigationSeen=true;spaTransition=false;awaitNewDocument=!priorDocumentId.isEmpty();trace.mode="网页加载";}if(!navigating)beginNavigation(url,"正在加载对话…");}
    @Override public void onPageCommitVisible(WebView v,String url){reading.visible(url);if(navigating&&targetMatches(url)){if(firstPageVisible==0)firstPageVisible=SystemClock.elapsedRealtime();trace.visible=SystemClock.elapsedRealtime();webObserver.pageReady();wakePolling();}}
    @Override public void onPageFinished(WebView v,String url){if(!url.equals(web.getUrl()))return;reading.visible(url);webObserver.pageReady();if(LoginPagePolicy.login(url)){if(pageError.isEmpty()){awaitLogin("请在网页中完成登录");if(LoginPagePolicy.google(url))checkGoogleLogin(url);}return;}if(!MainActivity.chatUrl(url))finishNavigation("请在原网页中完成登录",false);if(MainActivity.chatUrl(url)){prefs.edit().putString("url",url).apply();if(targetMatches(url))wakePolling();}}
    @Override public void onReceivedError(WebView v,WebResourceRequest r,WebResourceError e){if(r.isForMainFrame()){pageError="连接失败，请检查应用专用网络";finishNavigation(pageError);}}
    @Override public void onReceivedHttpError(WebView v,WebResourceRequest r,WebResourceResponse r2){if(r.isForMainFrame()&&r2.getStatusCode()>=400){if(LoginPagePolicy.login(r.getUrl().toString())&&r2.getStatusCode()<500){awaitLogin("登录未完成，请查看网页登录提示");return;}pageError="网站返回 HTTP "+r2.getStatusCode()+"，请检查网络或登录状态";finishNavigation(pageError,r2.getStatusCode()>=500);}}
  };}
  void awaitLogin(String message){navigating=false;navigationFailed=false;pageError="";recoveryScheduled=false;recoveryToken++;if(networkReady&&!offline&&guard.allowed()){networkIssue="";connectionStage="等待登录";}setStatus(message);}
  void checkGoogleLogin(String url){final long epoch=navigationEpoch;web.evaluateJavascript(LoginPagePolicy.blockedScript(),raw->{
    if(epoch!=navigationEpoch||!url.equals(web.getUrl())||!"true".equals(raw))return;googleLoginBlocked=true;awaitLogin("Google 暂不接受应用内浏览器登录，可打开登录帮助");
  });}
  void applyIdentityTemplate(MainActivity activity,BrowserIdentitySpec specification,java.util.function.Consumer<String> done){identity.apply(activity,specification,done);}
  void identityPolicyAcknowledged(){if(identity!=null)identity.acknowledge();}
  void identityObserved(JSONObject report){if(identity!=null)identity.observe(report);}
  long identityAuditAppliedRevision(){return identity==null?0:identity.appliedRevision();}
  void browserIdentitySaved(int level,boolean desktop){identity.legacySaved(level,desktop);}
  void applyBrowserSettings(boolean protectionChanged){
    identityApplicationPending=false;identity.prepareRuntime();
    // A confirmed user task was checked before entering this method. Replace only
    // idle navigation/retry work, and invalidate callbacks belonging to it.
    boolean reconnect=protectionChanged||connecting||!networkReady;
    recoveryToken++;recoveryScheduled=false;manualAttention=false;recoveryAttempt=0;
    navigationEpoch++;syncRun++;inFlight=false;navigating=false;navigationFailed=false;googleLoginBlocked=false;web.stopLoading();
    if(reconnect){audit.cancel();invalidateConnection();privacy.apply();if(!offline)openConnection(false,protectionChanged);}
    else{privacy.apply();if(!offline)navigate(resumeUrl(),"正在应用网页设置…");}
  }
  void beginNavigation(String url,String label){resetReplyStability();websiteConnectionIssue=false;navigationEpoch++;navigating=true;navigationFailed=false;navigationTarget=url;navigationLabel=label;spaTransition=false;documentNavigationSeen=false;navigationDispatched=true;priorDocumentId=lastDocumentId;awaitNewDocument=!priorDocumentId.isEmpty();spaStable=0;spaSignature="";navigationStarted=System.currentTimeMillis();trace.page("网页加载");navigationMono=SystemClock.elapsedRealtime();firstPageVisible=0;pageUsableAt=0;long epoch=navigationEpoch;setStatus(label);handler.postDelayed(()->{if(navigating&&navigationEpoch==epoch)finishNavigation("加载时间较长，请重试或查看原网页");},45000);}
  void navigate(String url,String label){
    if(!MainActivity.chatUrl(url)){setStatus("对话地址无效");return;}
    requestedConversation="";String source=web.getUrl();
    webStore.flush();webStore.current(url);webMirror.reset();lastWebSnapshot=0;lastWebUrl="";
    if(offline||!WebReplyObserver.same(conversation,url)||!WebReplyObserver.same(source,url))entries=webPerformance()?new JSONArray():cache.messages(url);conversation=url;showingCache=entries.length()>0;
    beginNavigation(url,label);navigationDispatched=false;pageMemory.restorePending=true;long epoch=navigationEpoch;if(MainActivity.chatUrl(source))web.evaluateJavascript("window.__pocketNavigationToken="+epoch,null);
    if(offline){finishNavigation("当前离线 · 草稿与本地内容已保留");return;}
    pageMemory.capture(()->{if(epoch!=navigationEpoch)return;String savedDocument=pageMemory.document(source);if(!savedDocument.isEmpty())priorDocumentId=savedDocument;loadNavigation(url,epoch);});wakePolling();
  }

  void loadNavigation(String url,long epoch){if(epoch!=navigationEpoch)return;if(privacy.desktop!=privacy.wantsDesktop()){privacy.apply();if(!privacy.canNavigate()){finishNavigation("浏览器设置暂未应用，请重新打开当前环境",true);return;}}navigationDispatched=true;awaitNewDocument=!priorDocumentId.isEmpty();spaTransition=false;trace.mode="网页加载";web.stopLoading();web.loadUrl(url);wakePolling();}

  void watchNetwork(){try{
    android.net.ConnectivityManager cm=(android.net.ConnectivityManager)context.getSystemService(Context.CONNECTIVITY_SERVICE);android.net.Network initial=cm.getActiveNetwork();android.net.NetworkCapabilities initialCaps=initial==null?null:cm.getNetworkCapabilities(initial);offline=initial==null;networkIdentity=initial==null?"":initial.toString();
    if(initialCaps==null)browserDefaultNetwork.unknown();else browserDefaultNetwork.initial(networkIdentity,initialCaps.hasCapability(android.net.NetworkCapabilities.NET_CAPABILITY_INTERNET),initialCaps.hasTransport(android.net.NetworkCapabilities.TRANSPORT_VPN));
    Runnable refresh=()->{android.net.Network n=cm.getActiveNetwork();android.net.NetworkCapabilities caps=n==null?null:cm.getNetworkCapabilities(n);if(caps==null)browserDefaultNetwork.unknown();else browserDefaultNetwork.initial(n.toString(),caps.hasCapability(android.net.NetworkCapabilities.NET_CAPABILITY_INTERNET),caps.hasTransport(android.net.NetworkCapabilities.TRANSPORT_VPN));boolean available=n!=null&&caps!=null&&caps.hasCapability(android.net.NetworkCapabilities.NET_CAPABILITY_INTERNET);String identity=available?n.toString():"";boolean switched=available&&!networkIdentity.isEmpty()&&!identity.equals(networkIdentity);networkIdentity=identity;if(guard.requiresVpn()&&!guard.vpnActive()){invalidateConnection();manualAttention=true;networkIssue="手机 VPN 未连接，已暂停网页联网；连接 VPN 后点按重连";connectionStage="等待手机 VPN";setStatus(networkIssue);return;}if(manualAttention&&"等待手机 VPN".equals(connectionStage)){manualAttention=false;recoveryAttempt=0;scheduleRecovery();}connectivity(available);if(switched&&!offline)networkChanged();};
    cm.registerDefaultNetworkCallback(new android.net.ConnectivityManager.NetworkCallback(){
      void queue(){handler.removeCallbacks(refresh);handler.post(refresh);}
      public void onAvailable(android.net.Network n){browserDefaultNetwork.available(n.toString());queue();}
      public void onLost(android.net.Network n){browserDefaultNetwork.lost(n.toString());queue();}
      public void onCapabilitiesChanged(android.net.Network n,android.net.NetworkCapabilities c){browserDefaultNetwork.capabilities(n.toString(),c.hasCapability(android.net.NetworkCapabilities.NET_CAPABILITY_INTERNET),c.hasTransport(android.net.NetworkCapabilities.TRANSPORT_VPN));queue();}
    });
  }catch(Exception ignored){browserDefaultNetwork.unknown();}}
  void invalidateConnection(){resetReplyStability();if(pageUsableAt>0)pageMemory.capture(()->{});connectionEpoch++;navigationEpoch++;recoveryToken++;recoveryScheduled=false;connecting=false;networkReady=false;web.stopLoading();guard.setBlocked(true);inFlight=false;}
  void connectivity(boolean available){boolean was=offline;offline=!available;if(offline){if(networkReady)ChatService.networkLost(context);invalidateConnection();navigating=false;navigationFailed=true;showingCache=entries.length()>0;connectionStage="手机网络不可用";networkIssue="当前离线 · 草稿与附件已保留，联网后继续核对";setStatus(networkIssue);}else if(was){manualAttention=false;recoveryAttempt=0;networkIssue="手机网络已恢复";scheduleRecovery();}}
  void networkChanged(){invalidateConnection();manualAttention=false;recoveryAttempt=0;networkIssue="手机网络已切换，正在重新核对连接";scheduleRecovery();}
  static long retryDelay(int attempt){long[] delays={1000,2000,5000,10000,20000};return delays[Math.min(Math.max(attempt,0),delays.length-1)];}
  boolean internalNetwork(){return "internal".equals(prefs.getString("networkMode","external"));}
  String resumeUrl(){if(pending!=null){String confirmed=pending.optString("confirmedUrl");if(resumable(confirmed))return confirmed;String expected=pending.optString("expectedUrl");if(resumable(expected)&&android.net.Uri.parse(expected).getPath().contains("/c/"))return expected;}if(resumable(requestedConversation))return requestedConversation;if(resumable(conversation))return conversation;String saved=prefs.getString("conversation","");if(resumable(saved))return saved;saved=prefs.getString("url",MainActivity.ORIGIN);return resumable(saved)?saved:MainActivity.ORIGIN;}
  static boolean resumable(String url){return MainActivity.chatUrl(url)&&!LoginPagePolicy.login(url);}
  void scheduleRecovery(){if(offline||recoveryScheduled||connecting||manualAttention||!prefs.getBoolean("networkConfigured",false))return;if(internalNetwork()&&NativeNetwork.get(context).recoveryBlocked){manualAttention=true;connectionStage="固定出口需要检查";setStatus(NativeNetwork.get(context).message);return;}if(recoveryAttempt>=5){connectionStage="需要手动重连";networkIssue="自动重连暂未成功 · 点按查看连接状态";setStatus(networkIssue);return;}recoveryScheduled=true;long token=++recoveryToken,delay=retryDelay(recoveryAttempt);connectionStage="等待重连";setStatus("连接中断 · "+(delay/1000)+" 秒后重试（"+(recoveryAttempt+1)+"/5）");handler.postDelayed(()->runRecovery(token),delay);}
  void runRecovery(long token){if(token!=recoveryToken||offline||manualAttention)return;if(submitting||operation){handler.postDelayed(()->runRecovery(token),500);return;}recoveryScheduled=false;recoveryAttempt++;openConnection(true,false);}
  void finishNavigation(String error){finishNavigation(error,true);}
  void finishNavigation(String error,boolean retry){navigating=false;navigationFailed=!error.isEmpty();if(navigationFailed){status=error;networkIssue=error;if(!retry){manualAttention=true;recoveryToken++;recoveryScheduled=false;}else if(!offline)scheduleRecovery();}changed();}
  boolean targetMatches(String url){try{return android.net.Uri.parse(url).getPath().equals(android.net.Uri.parse(navigationTarget).getPath());}catch(Exception e){return false;}}
  void add(Observer o){remove(o);observers.add(new WeakReference<>(o));o.changed();}
  void remove(Observer o){observers.removeIf(w->w.get()==null||w.get()==o);}
  void changed(){if(internalNetwork()){NativeNetwork n=NativeNetwork.get(context);n.pauseBackgroundWhenBusy();}try{ProfileCatalog.get(context).heartbeat(this,false);NetworkJournal.record(this);}catch(Exception ignored){}for(WeakReference<Observer> w:new ArrayList<>(observers)){Observer o=w.get();if(o!=null)o.changed();}if(ChatService.running)ChatService.update(context,status);}
  void delivery(String id,String stage,String detail,boolean attempted,String key,String url){String signature=id+"|"+stage+"|"+detail+"|"+attempted+"|"+key+"|"+url;if(webPerformance()&&signature.equals(lastDeliverySignature))return;try{deliveries.update(id,stage,detail,attempted,key,url);lastDeliverySignature=signature;}catch(Exception ignored){}}
  void sendFailure(String message){submitting=false;ChatService.end(context);delivery(activeDeliveryId,"failed",message==null?"发送前检查失败":message,false,"","");setStatus(message);}
  void setStatus(String text){status=text==null?"网络连接未完成":text;changed();}
  boolean uploading(){for(int i=0;i<attachments.length();i++){JSONObject file=attachments.optJSONObject(i);if(file!=null&&"uploading".equals(file.optString("state")))return true;}return false;}
  boolean currentReplyActive(){return BrowserSettingsPolicy.currentReply(MainActivity.chatUrl(web.getUrl()),WebReplyObserver.same(web.getUrl(),state.optString("url")),state.optBoolean("busy"),stateEpoch,navigationEpoch);}
  boolean browserWorkActive(){
    boolean reply=currentReplyActive();
    boolean maintenance=DeferredBrowserSettings.pending(this)||audit!=null&&audit.running||ChatService.running||configurationCapture;
    // Pause activity while retaining the live session; this never destroys a
    // process, discards a draft, or claims a durable eviction checkpoint.
    return !deleted&&EnvironmentResourcePolicy.keepActivityRunning(uiVisible,pending!=null||submitting||operation||reply,uploading(),transferActive,connecting||navigating,maintenance);
  }
  void updateBrowserActivity(){boolean active=browserWorkActive();if(active&&browserPaused){web.resumeTimers();web.onResume();browserPaused=false;}else if(!active&&!browserPaused){web.onPause();web.pauseTimers();browserPaused=true;}if(active)wakePolling();else handler.removeCallbacks(tick);}
  void foreground(boolean value){uiVisible=value;if(!value){pageMemory.capture(()->{});web.checkpointState();webStore.flush();}else{if(web.enabled&&web.failed)web.onResume();if(pending!=null&&!pending.optBoolean("webSuspended"))ChatService.begin(context);}updateBrowserActivity();}
  void checkBackgroundAttachments(){if(backgroundAttachmentCheck||uiVisible||!uploading()||offline||!networkReady)return;backgroundAttachmentCheck=true;long epoch=navigationEpoch;String owner=attachmentOwner;JSONArray names=new JSONArray();for(int i=0;i<attachments.length();i++)names.put(attachments.optJSONObject(i).optString("name"));
    asyncDriver("attachment-state",J.obj("names",names,"url",owner),2500,result->{backgroundAttachmentCheck=false;if(epoch!=navigationEpoch||!owner.equals(attachmentOwner))return;JSONArray observed=result.optJSONArray("files");if(observed==null)return;boolean allReady=observed.length()==attachments.length();for(int i=0;i<observed.length();i++)allReady&="ready".equals(observed.optJSONObject(i).optString("state"));backgroundAttachmentStable=allReady?backgroundAttachmentStable+1:0;
      for(int i=0;i<attachments.length();i++){JSONObject file=attachments.optJSONObject(i);for(int j=0;j<observed.length();j++){JSONObject item=observed.optJSONObject(j);if(file.optString("name").equals(item.optString("name")))try{String value=item.optString("state","unknown");if("ready".equals(value)&&backgroundAttachmentStable<2)value="uploading";file.put("state",value);file.put("progress",item.optInt("progress",-1));}catch(Exception ignored){}}}
      prefs.edit().putString("files:"+conversation,attachments.toString()).apply();updateBrowserActivity();
    });
  }

  void networkStatus(String text,boolean ready){if(audit!=null)audit.refresh(false);if(!internalNetwork())return;NativeNetwork n=NativeNetwork.get(context);if(!ready&&!n.starting&&!connecting){if(networkReady)ChatService.networkLost(context);networkReady=false;guard.setBlocked(true);networkIssue=text;connectionStage="代理连接中断";setStatus(text);if(uiVisible||ChatService.running)scheduleRecovery();}else if(!ready||pending==null)setStatus(text);}
  void connect(){if(offline){setStatus("当前离线 · 草稿与附件已保留");return;}if(connecting||recoveryScheduled||manualAttention)return;if(networkReady&&(!internalNetwork()||NativeNetwork.get(context).ready&&NativeNetwork.get(context).coreAlive())){changed();return;}openConnection(false,false);}
  void retryCurrent(){manualAttention=false;recoveryAttempt=0;recoveryToken++;recoveryScheduled=false;if(!networkReady||offline||!guard.allowed())reconnect();else if(!web.recoverClosed())navigate(resumeUrl(),"正在重新加载…");}
  /** Explicit user reload stays on the captured current document, not an older pending chat. */
  void retryCurrent(String target){
    if(target==null||target.isEmpty()){retryCurrent();return;}
    if(!BrowserRuntimePolicy.sameDocument(target,web.getUrl()))return;
    if(!networkReady||offline||!guard.allowed()){setStatus("当前环境网络未就绪，请先检查网络后重新加载");return;}
    manualAttention=false;recoveryAttempt=0;recoveryToken++;recoveryScheduled=false;
    if(web.recoverClosed())return;
    if(MainActivity.chatUrl(target))navigate(target,"正在重新加载…");
    else if(web.current!=null&&web.current.isOpen())web.current.reload();
  }
  void recoverWebsiteConnection(){
    if(websiteRecovering)return;
    if(submitting||operation||transferActive||uploading()){setStatus("正在处理文件或发送，请稍后恢复网页连接");return;}
    if(offline||!networkReady||!guard.allowed()){reconnect();return;}
    String url=web.getUrl(),job=pending==null?"":pending.optString("id");long epoch=navigationEpoch;
    websiteRecovering=true;
    runDriver("page-state",J.obj("expectedUrl",url),snapshot->{
      if(epoch!=navigationEpoch||!WebReplyObserver.same(url,web.getUrl())){websiteRecovering=false;return;}
      if(!snapshot.optBoolean("ok")||!WebReplyObserver.same(url,snapshot.optString("url"))){websiteRecovering=false;setStatus("网页正在变化，请稍后再恢复连接");return;}
      String draft=snapshot.optString("draft");
      webStore.worker.execute(()->{
        boolean saved=DraftArchive.get(context).save(url,draft,"恢复网页连接前草稿");
        handler.post(()->{
          if(epoch!=navigationEpoch||!WebReplyObserver.same(url,web.getUrl())||!job.equals(pending==null?"":pending.optString("id"))||submitting||operation||transferActive||uploading()){websiteRecovering=false;return;}
          if(!saved){websiteRecovering=false;setStatus("草稿暂存失败，网页尚未重新加载");return;}
          // Typing can continue while the archive is written. Never replace a
          // newer draft merely because the route and pending task stayed equal.
          runDriver("page-state",J.obj("expectedUrl",url),latest->{websiteRecovering=false;
            if(epoch!=navigationEpoch||!WebReplyObserver.same(url,web.getUrl())||!job.equals(pending==null?"":pending.optString("id"))||submitting||operation||transferActive||uploading())return;
            if(!latest.optBoolean("ok")||!snapshot.optString("documentId").equals(latest.optString("documentId"))||!draft.equals(latest.optString("draft"))){setStatus("草稿已变化，继续编辑；需要时再恢复网页连接");return;}
            retryCurrent();
          });
        });
      });
    });
  }
  void reconnect(){manualAttention=false;recoveryAttempt=0;recoveryToken++;recoveryScheduled=false;invalidateConnection();if(offline){setStatus("当前离线，请先连接手机网络");return;}openConnection(true,internalNetwork()&&NativeNetwork.get(context).recoveryBlocked);}
  void openConnection(boolean recover,boolean force){if(offline||connecting)return;if(!privacy.canNavigate()){guard.setBlocked(true);manualAttention=true;setStatus("当前浏览器保护尚未就绪，请重新打开当前环境");return;}keepPageCandidate=recover&&!force&&pending==null&&!submitting&&!operation&&pageUsableAt>0&&MainActivity.chatUrl(web.getUrl())&&WebReplyObserver.same(web.getUrl(),resumeUrl());if(recover)pageMemory.capture(()->{});trace.begin();connecting=true;networkReady=false;updateBrowserActivity();connectionStarted=SystemClock.elapsedRealtime();proxyReadyAt=0;web.stopLoading();guard.setBlocked(true);pageError="";long epoch=++connectionEpoch;connectionStage=internalNetwork()?"检查应用专用代理":"检查网页连接";setStatus(recover?"正在恢复连接，草稿与发送记录已保留…":"正在连接…");
    try{new SecretStore(context).importPrivateProvision();}catch(Exception e){connectionFailed(epoch,"私有网络配置导入失败，请在设置中重新填写",false);return;}
    if(internalNetwork()){NativeNetwork n=NativeNetwork.get(context);NativeNetwork.Callback callback=(ok,message)->{if(epoch!=connectionEpoch||offline)return;if(ok)applyProxy(n.proxy(),epoch);else connectionFailed(epoch,message,!n.recoveryBlocked);};if(force)n.restart(callback);else if(recover)n.recover(callback);else n.start(callback);return;}
    if(!prefs.getBoolean("networkConfigured",false)){connectionFailed(epoch,"请先配置手机独立网络",false);return;}applyProxy(prefs.getString("proxy",""),epoch);
  }
  void connectionFailed(long epoch,String message,boolean retry){if(epoch!=connectionEpoch)return;connecting=false;networkReady=false;guard.setBlocked(true);networkIssue=message==null?"网络连接失败":message;connectionStage="连接未完成";setStatus(networkIssue);if(!retry)manualAttention=true;else scheduleRecovery();}
  void applyProxy(String proxy){applyProxy(proxy,connectionEpoch);}
  String networkIdentity(){try{if(internalNetwork()){NativeNetwork n=NativeNetwork.get(context);return "internal:"+n.fingerprint+":"+NativeNetwork.hash(n.settings==null?"":n.settings.optString("subscriptionUrl"));}return "external:"+prefs.getString("proxy","");}catch(Exception e){return "";}}
  void applyProxy(String proxy,long epoch){if(guard.requiresVpn()&&!guard.vpnActive()){connectionFailed(epoch,"手机 VPN 未连接，已暂停网页联网；请先连接 VPN 后重连",false);connectionStage="等待手机 VPN";return;}String identity=networkIdentity();boolean keep=keepPageCandidate&&!appliedIdentity.isEmpty()&&appliedIdentity.equals(identity);Runnable done=()->{
      if(epoch!=connectionEpoch||offline)return;if(!guard.routeProtected()){connectionFailed(epoch,"受保护连接已中断，网页联网已暂停",false);return;}connecting=false;networkReady=true;proxyReadyAt=SystemClock.elapsedRealtime();trace.network(internalNetwork()?NativeNetwork.get(context):null);appliedIdentity=identity;connectionStage="正在核对网页";guard.setBlocked(false);identityPolicyAcknowledged();audit.refresh(true);
      String target=resumeUrl();if(!keep||pending!=null){navigate(target,"正在恢复 ChatGPT 对话…");return;}
      asyncDriver("page-recover",J.obj("expectedUrl",target),3200,result->{if(epoch!=connectionEpoch||offline)return;trace.recoveryProbe=(long)ConnectionTrace.bounded(result.optDouble("probeMs",-1));
        if(result.optBoolean("ok")&&pending==null&&!submitting&&!operation&&WebReplyObserver.same(target,web.getUrl())){
          navigating=false;navigationFailed=false;manualAttention=false;recoveryAttempt=0;recoveryScheduled=false;recoveryToken++;connectionStage="已连接";networkIssue="";pageError="";navigationMono=SystemClock.elapsedRealtime();firstPageVisible=pageUsableAt=navigationMono;trace.page("保留现有网页");trace.visible=trace.usable=SystemClock.elapsedRealtime();setStatus("已连接 · 网页已保留");wakePolling();
        }else navigate(target,"正在恢复 ChatGPT 对话…");
      });
    };
    if(!proxy.isEmpty()&&!MainActivity.validProxy(proxy)){connectionFailed(epoch,"代理地址无效，已停止网络加载",false);return;}
    done.run();
  }

  String entryTiming(){if(navigationMono==0)return "";long network=connectionStarted>0&&proxyReadyAt>=connectionStarted?proxyReadyAt-connectionStarted:-1;String detail=network>=0?"网络准备 "+String.format(Locale.ROOT,"%.1f",network/1000.0)+" 秒":"";if(pageUsableAt>0)detail+=(detail.isEmpty()?"":" · ")+"网页可操作 "+String.format(Locale.ROOT,"%.1f",(pageUsableAt-navigationMono)/1000.0)+" 秒";else if(firstPageVisible>0)detail+=(detail.isEmpty()?"":" · ")+"网页已显示";return detail.isEmpty()?"":"本次进入："+detail;}
  boolean webPerformance(){return BrowserRuntimePolicy.originalWebsite();}
  void wakePolling(){handler.removeCallbacks(tick);handler.post(tick);}
  void runDriver(String action,JSONObject args,Result cb){
    if(!BrowserRuntimePolicy.allows(action)){cb.accept(J.obj("ok",false,"reason",BrowserRuntimePolicy.websiteActionMessage()));return;}
    if(!MainActivity.chatUrl(web.getUrl())){cb.accept(J.obj("ok",false,"reason","请先登录 ChatGPT","error","页面尚未就绪"));return;}
    boolean compact=webPerformance()&&(action.equals("web-inspect")||action.equals("web-transcript")||action.equals("poll"));
    String code=compact?"typeof window.__pocketReadDriver==='function'?window.__pocketReadDriver("+JSONObject.quote(action)+","+args+"):({readRuntimeMissing:true})":driver.replace("__ACTION__",JSONObject.quote(action)).replace("__ARG__",args.toString());
    evaluateDriver(action,code,r->{if(compact&&r.optBoolean("readRuntimeMissing")&&!webObserver.script.isEmpty())evaluateDriver(action,webObserver.script+"\nwindow.__pocketReadDriver("+JSONObject.quote(action)+","+args+");",cb);else cb.accept(r);});
  }
  void evaluateDriver(String action,String code,Result cb){long start=SystemClock.elapsedRealtime();WebPerfStats.driver(action,code.length());web.evaluateJavascript(code,raw->{JSONObject result=J.parse(raw);WebPerfStats.response(action,raw.length(),SystemClock.elapsedRealtime()-start,result);cb.accept(result);});}
  void asyncDriver(String action,JSONObject args,long timeout,Result cb){if(!BrowserRuntimePolicy.allows(action)){cb.accept(J.obj("ok",false,"reason",BrowserRuntimePolicy.websiteActionMessage()));return;}if(!MainActivity.chatUrl(web.getUrl())){cb.accept(J.obj("ok",false,"reason","请先登录 ChatGPT"));return;}String key="__pocket_"+UUID.randomUUID().toString().replace("-","");String code=(action.startsWith("attachment-")?attachmentDriver:driver).replace("__ACTION__",JSONObject.quote(action)).replace("__ARG__",args.toString());web.evaluateJavascript("void(Promise.resolve("+code+").then(v=>window['"+key+"']=v).catch(()=>window['"+key+"']={ok:false,reason:'网页操作未完成'}))",unused->waitResult(key,System.currentTimeMillis()+timeout,cb));}
  void waitResult(String key,long deadline,Result cb){handler.postDelayed(()->web.evaluateJavascript("window['"+key+"']||null",r->{if("null".equals(r)){if(System.currentTimeMillis()<deadline)waitResult(key,deadline,cb);else cb.accept(J.obj("ok",false,"reason","网页操作超时，请检查原网页"));}else{web.evaluateJavascript("delete window['"+key+"']",null);cb.accept(J.parse(r));}}),120);}
  void resolveDraftConflict(JSONObject conflict){draftConflict=null;setStatus(BrowserRuntimePolicy.websiteActionMessage());}
  void rememberOwnedDraft(String url,String text){if(text.equals(prefs.getString("ownedWebDraft:"+url,null)))return;prefs.edit().putString("ownedWebDraft:"+url,text).apply();}
  // Compatibility methods for old native controls. None can replace a draft or
  // submit a message; the official composer owns user input and submission.
  void submit(String text){setStatus(BrowserRuntimePolicy.websiteActionMessage());}
  void submitChecked(String text){submit(text);}
  void submitReady(String text){submit(text);}
  final Runnable tick=new Runnable(){public void run(){if(!browserWorkActive()){if(!browserPaused){web.onPause();web.pauseTimers();browserPaused=true;}return;}if(browserPaused){web.resumeTimers();web.onResume();browserPaused=false;}
    DeferredBrowserSettings.drain(ChatSession.this);NetworkRegion.refresh(ChatSession.this);
    if(EnvironmentResourcePolicy.observePage(uiVisible,ChatService.running,pending!=null,navigating,DeferredBrowserSettings.pending(ChatSession.this),currentReplyActive())&&networkReady&&!offline&&!inFlight&&!submitting&&!operation)sync();if(!uiVisible&&uploading())checkBackgroundAttachments();
    long delay=webPerformance()&&navigating&&SystemClock.elapsedRealtime()-navigationMono<10000?250:!uiVisible&&uploading()?2000:webPerformance()&&pending==null&&!navigating&&!navigationFailed&&!state.optBoolean("busy")?4000:1200;handler.postDelayed(this,delay);
  }};

  void sync(){
    if(GeckoWebView.active(web)&&web.failed)return;
    if(LoginPagePolicy.login(web.getUrl()))return;
    if(inFlight||navigating&&!navigationDispatched)return;inFlight=true;long epoch=navigationEpoch,run=++syncRun;boolean optimized=webPerformance();
    runDriver(optimized?"web-inspect":"inspect",J.obj("navigationCheck",spaTransition),s->{
      if(run!=syncRun)return;if(epoch!=navigationEpoch){inFlight=false;return;}if(navigating&&awaitNewDocument&&priorDocumentId.equals(s.optString("documentId"))){inFlight=false;return;}if(!s.optString("documentId").isEmpty()){lastDocumentId=s.optString("documentId");awaitNewDocument=false;}state=s;stateEpoch=epoch;if(WebReplyObserver.same(web.getUrl(),s.optString("url"))){websiteConnectionIssue=s.optBoolean("websiteSocketClosed");if(!s.optString("error").isEmpty())resetReplyStability();}
      archiveWebsiteNavigation(s);
      if(pending==null&&!navigating&&!navigationFailed){if(!pageError.isEmpty())status=pageError;else if(!s.optString("error").isEmpty())status=s.optString("error");else if(s.optBoolean("modelKnown"))status="已连接 · "+s.optString("model")+(s.optString("effort").isEmpty()?"":" · "+s.optString("effort"));else status="请打开登录页面完成登录";}
      // During startup the page may be an empty shell. Inspect readiness cheaply;
      // defer transcript walks until the target composer/content is actually present.
      if(optimized&&navigating){
        String error=s.optString("error");if(!error.isEmpty()&&!error.equals("页面尚未就绪"))finishNavigation(error,error.contains("无法连接"));
        if(!targetMatches(s.optString("url"))||!s.optBoolean("composer")||(android.net.Uri.parse(navigationTarget).getPath().contains("/c/")&&!s.optBoolean("hasMessages"))){pollSync(epoch,run,optimized);return;}
      }
      if(optimized&&spaTransition){String signature=s.optString("contentKey");boolean changed=!signature.equals(spaBefore)&&targetMatches(s.optString("url"))&&s.optBoolean("composer");if(changed&&signature.equals(spaSignature))spaStable++;else{spaSignature=signature;spaStable=changed?1:0;}if(spaStable<2){pollSync(epoch,run,optimized);return;}spaTransition=false;}
      long now=SystemClock.elapsedRealtime();boolean routeChanged=!lastWebUrl.equals(s.optString("url"));
      boolean needed=!optimized||routeChanged||navigating||navigationFailed||webMirror.documentId.isEmpty()||(s.optBoolean("transcriptDirty")&&now-lastWebSnapshot>=2500&&!s.optBoolean("interacting"));
      if(!needed){pollSync(epoch,run,optimized);return;}
      runDriver(optimized?"web-transcript":"transcript",optimized?webMirror.arguments():new JSONObject(),data->{
        if(run!=syncRun)return;if(epoch!=navigationEpoch){inFlight=false;return;}
        if(navigating&&!s.optString("error").isEmpty()&&!s.optString("error").equals("页面尚未就绪"))finishNavigation(s.optString("error"),s.optString("error").contains("无法连接"));
        acceptTranscript(data,s,optimized);if(optimized){lastWebSnapshot=SystemClock.elapsedRealtime();lastWebUrl=s.optString("url");}
        pollSync(epoch,run,optimized);
      });
    });
  }
  boolean archiveWebsiteNavigation(JSONObject inspected){
    JSONObject job=pending;String current=web.getUrl(),observed=inspected.optString("url");
    if(!WebReplyObserver.webJob(job)||!WebReplyObserver.same(current,observed)||LoginPagePolicy.login(current))return false;
    String bound=job.optString("confirmedUrl");if(bound.isEmpty())bound=job.optString("expectedUrl");
    if(BrowserRuntimePolicy.conversationId(android.net.Uri.parse(current).getEncodedPath()).isEmpty()&&(inspected.optBoolean("busy")||!inspected.optString("error").isEmpty()))return false;
    return BrowserRuntimePolicy.leftConversation(bound,current,inspected.optBoolean("composer"),inspected.optBoolean("hasMessages"))&&webObserver.archiveNavigation(job);
  }
  void acceptTranscript(JSONObject data,JSONObject inspect,boolean optimized){
    if(!data.optBoolean("ok"))return;String url=data.optString("url");
    if(optimized){JSONArray delta=data.optJSONArray("changes");for(int i=0;delta!=null&&i<delta.length();i++){JSONObject row=delta.optJSONObject(i);JSONArray files=sentAttachments.optJSONArray(url+"|"+row.optString("id"));if(files!=null)try{row.put("attachments",files);}catch(Exception ignored){}}}
    JSONArray incoming=optimized?webMirror.accept(data,entries,conversation):data.optJSONArray("entries");
    if(incoming==null)return;
    boolean targetReady=targetMatches(url)&&inspect.optBoolean("composer")&&(incoming.length()>0||!android.net.Uri.parse(navigationTarget).getPath().contains("/c/"));
    if((navigating||navigationFailed)&&targetReady){pageUsableAt=SystemClock.elapsedRealtime();trace.usable=pageUsableAt;navigating=false;navigationFailed=false;showingCache=false;manualAttention=false;recoveryScheduled=false;connectionStage="已连接";networkIssue="";recoveryAttempt=0;recoveryToken++;status="已连接 · "+inspect.optString("model");pageMemory.restore(url,navigationEpoch);long epoch=navigationEpoch;runDriver("page-timing",new JSONObject(),timing->{if(epoch==navigationEpoch)trace.timing(timing);});}
    if(!navigating&&!navigationFailed&&(incoming.length()>0||!url.equals(conversation))){
      if(!optimized)for(int i=0;i<incoming.length();i++){JSONObject entry=incoming.optJSONObject(i);JSONArray files=sentAttachments.optJSONArray(url+"|"+entry.optString("id"));if(files!=null)try{entry.put("attachments",files);}catch(Exception ignored){}}
      entries=optimized?incoming:cache.withEarlier(url,incoming);conversation=url;
      if(optimized)webStore.offer(url,entries);else{webStore.nativeSnapshot(url);cache.saveMessages(url,entries);prefs.edit().putString("transcript",entries.toString()).putString("conversation",conversation).apply();}
    }
  }
  JSONObject webPollArguments(JSONObject job){
    JSONObject args=J.obj("kind",job.optString("kind"),"confirmed",job.optBoolean("confirmed"),"webSuspended",job.optBoolean("webSuspended"),"expectedUrl",job.optString("expectedUrl"),"confirmedUrl",job.optString("confirmedUrl"),"prompt",job.optString("prompt"),"export",true,"lightObservation",true,"incrementalObservation",true,"attachmentOnly",job.optBoolean("attachmentOnly"),"attachmentNames",job.optJSONArray("attachmentNames"));
    if(job.optString("id").equals(observedReplyJob)&&WebReplyObserver.same(observedReplyUrl,web.getUrl()))try{args.put("knownReplyKey",observedReplyKey).put("knownReplyContentRevision",observedReplyRevision);}catch(Exception ignored){}
    try{if(!job.optString("userKey").isEmpty())args.put("userKey",job.optString("userKey"));else args.put("beforeUserKeys",job.optJSONArray("beforeUserKeys"));}catch(Exception ignored){}return args;
  }
  void pollSync(long epoch,long run,boolean optimized){
    if(pending==null||!WebReplyObserver.webJob(pending)){inFlight=false;changed();return;}JSONObject job=pending;
    runDriver("poll",optimized?webPollArguments(job):job,p->{
      if(run!=syncRun)return;if(pending!=job||epoch!=navigationEpoch){inFlight=false;return;}
      String error=p.optString("error");
      if((p.optBoolean("bindingPending")||p.optBoolean("pageLoading")||error.equals("页面尚未就绪"))&&(error.isEmpty()||error.equals("页面尚未就绪"))&&!p.optBoolean("otherQuestion")){
        resetReplyStability();setStatus("网页正在加载，继续核对原回复…");inFlight=false;return;
      }
      if(!error.isEmpty()){resetReplyStability();websiteConnectionIssue=p.optBoolean("websiteSocketClosed");delivery(job.optString("id"),"uncertain",error,true,"","");setStatus(error);inFlight=false;return;}
      if(p.optBoolean("otherQuestion")||p.optBoolean("bindingLost")){resetReplyStability();delivery(job.optString("id"),"uncertain","对话已改变，请核对原网页",true,"","");setStatus("对话已改变，请检查上次发送；不会自动重发");inFlight=false;return;}
      if(p.optBoolean("submitted"))websiteConnectionIssue=false;
      // An omitted payload is valid only for this exact task, route, reply and
      // mutation revision. Completion still sees the last fully captured text.
      if(optimized&&p.optBoolean("contentUnchanged")){
        if(!job.optString("id").equals(observedReplyJob)||!WebReplyObserver.same(observedReplyUrl,p.optString("url"))||!observedReplyKey.equals(p.optString("replyKey"))||!observedReplyRevision.equals(p.optString("replyContentRevision"))){observedReplyRevision="";stableTicks=0;webObserver.mayComplete(job,new JSONObject());inFlight=false;return;}
        try{p.put("markdown",observedReplyMarkdown).put("hasFiles",observedReplyHasFiles);}catch(Exception ignored){}
      }
      boolean contentObserved=!optimized||p.optBoolean("contentObserved",true);
      if(optimized&&contentObserved&&p.has("replyContentRevision")){
        observedReplyJob=job.optString("id");observedReplyUrl=p.optString("url");observedReplyKey=p.optString("replyKey");observedReplyRevision=p.optString("replyContentRevision");observedReplyMarkdown=p.optString("markdown");observedReplyHasFiles=p.optBoolean("hasFiles");
      }
      boolean verifiedWebCompletion;
      if(p.optBoolean("captureDeferred")){resetReplyStability();verifiedWebCompletion=false;}
      else verifiedWebCompletion=webObserver.mayComplete(job,p);
      boolean jobChanged=false,previouslyConfirmed=job.optBoolean("confirmed");
      if(p.optBoolean("submitted")){
        delivery(job.optString("id"),previouslyConfirmed?"awaiting":"confirmed",previouslyConfirmed?"网页已显示提问，正在等待回复":"对应提问已出现在网页中",true,p.optString("userKey"),p.optString("url",conversation));
        try{
          if(!job.optBoolean("confirmed")){job.put("confirmed",true);jobChanged=true;confirmedPrompt=job.optString("prompt");confirmationVersion++;}
          if(!job.optString("userKey").equals(p.optString("userKey"))){job.put("userKey",p.optString("userKey"));jobChanged=true;}
          if(MainActivity.chatUrl(p.optString("url"))){if(!job.optString("confirmedUrl").equals(p.optString("url"))){job.put("confirmedUrl",p.optString("url"));jobChanged=true;}if(!"regenerate".equals(job.optString("kind")))rememberOwnedDraft(p.optString("url"),job.optString("prompt"));}
          JSONArray names=job.optJSONArray("attachmentNames");if(names!=null&&names.length()>0&&!p.optString("userKey").isEmpty()){String fileKey=p.optString("url",conversation)+"|"+p.optString("userKey");if(!optimized||!sentAttachments.has(fileKey)){sentAttachments.put(fileKey,names);prefs.edit().putString("sentAttachments",sentAttachments.toString()).apply();}}
        }catch(Exception ignored){}
        if(jobChanged||!optimized)prefs.edit().putString("pending",job.toString()).apply();
      }
      String reply=p.optString("markdown");
      if("regenerate".equals(job.optString("kind"))&&!job.optBoolean("regenerationObserved")&&(p.optBoolean("busy")||(!p.optString("replyKey").isEmpty()&&!p.optString("replyKey").equals(job.optString("beforeReplyKey")))||(!reply.isEmpty()&&!reply.equals(job.optString("beforeReplyText"))))){try{job.put("regenerationObserved",true);}catch(Exception ignored){}prefs.edit().putString("pending",job.toString()).apply();}
      String progressId=job.optString("id"),signature=p.optString("replyKey")+"|"+(contentObserved?reply:p.optString("replyContentRevision"))+"|"+p.optBoolean("thinking")+"|"+p.optBoolean("searching");long now=System.currentTimeMillis();if(!progressId.equals(progressJob)||!signature.equals(progressSignature)){progressJob=progressId;progressSignature=signature;lastReplyProgress=now;}stableTicks=contentObserved&&reply.equals(stableReply)?stableTicks+1:0;stableReply=contentObserved?reply:"";
      if(contentObserved&&p.optBoolean("submitted")&&p.optBoolean("terminal")&&!p.optBoolean("busy")&&(!reply.trim().isEmpty()||p.optBoolean("hasFiles"))&&stableTicks>=2&&verifiedWebCompletion&&(!"regenerate".equals(job.optString("kind"))||job.optBoolean("regenerationObserved"))){
        if(optimized)runDriver("web-transcript",webMirror.arguments(),data->{if(run!=syncRun)return;if(pending!=job||epoch!=navigationEpoch){inFlight=false;return;}acceptTranscript(data,state,true);webStore.flush();completeReply(job,p);inFlight=false;changed();});
        else{completeReply(job,p);inFlight=false;changed();}
      }else{status=ReplyState.describe(p,job,stableTicks,now-lastReplyProgress);inFlight=false;changed();}
    });
  }
  void completeReply(JSONObject job,JSONObject poll){String id=job.optString("id","recovered"),url=poll.optString("url",conversation);delivery(id,"completed","回复已完成",true,poll.optString("userKey"),url);pending=null;activeDeliveryId="";prefs.edit().remove("pending").putString("lastCompletedId",id).putString("url",url).commit();status="回复完成";ChatService.completed(context,id,url);ChatService.end(context);}
  void resetReplyStability(){stableReply="";stableTicks=0;webObserver.resetCompletion();}
  void abandonWait(){if(pending!=null)delivery(pending.optString("id"),"uncertain","已解除等待，发送结果仍需在网页核对",true,"","");pending=null;activeDeliveryId="";prefs.edit().remove("pending").commit();ChatService.end(context);setStatus("已解除等待，请自行核对是否需要发送");}
  void timeout(){setStatus("安卓后台等待时间已到，请打开应用继续检测；不会自动重发");ChatService.needsAttention(context,status);}
  void escape(){}
  void nativeKey(int key){setStatus(BrowserRuntimePolicy.websiteActionMessage());}
}
