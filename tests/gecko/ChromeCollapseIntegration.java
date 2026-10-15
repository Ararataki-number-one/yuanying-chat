package local.pocketchat;

import android.content.*;
import android.os.*;
import android.view.*;
import org.json.*;
import org.mozilla.geckoview.*;

/** Test-only observation of the real chrome and SDK. All gestures come from adb input. */
final class ChromeCollapseIntegration {
  static final String ACTION="local.pocketchat.test.CHROME_COLLAPSE";
  static final String TARGET=MainActivity.ORIGIN+"c/reload-collapse";
  static final String TELEMETRY="JSON.parse(document.documentElement.dataset.chromeInputEvidence||'null')";
  static final String TELEMETRY_READY="t?.schema===1&&t.realm==='page-main-world'&&t.document===document.documentElement.dataset.reloadDocument&&Array.isArray(t.events)&&t.listenerTypes?.includes('touchend')";
  final CompactChromeIntegrationActivity a;
  final String nonce;
  final IntegrationEventStore events;
  String task="";
  int documents;
  int activityStarts,menuOpens;
  JSONArray nativeTouches=new JSONArray();
  final BroadcastReceiver receiver=new BroadcastReceiver(){@Override public void onReceive(Context c,Intent intent){
    if(!nonce.equals(intent.getStringExtra("eventNonce")))return;
    String command=intent.getStringExtra("collapseCommand");
    if(command==null||!command.matches("[a-zA-Z0-9_-]{1,80}"))return;
    if("clear".equals(command)){web().touchesObserved=new JSONArray();nativeTouches=new JSONArray();return;}
    a.handler.postDelayed(()->snapshot(command),150);
  }};
  ChromeCollapseIntegration(CompactChromeIntegrationActivity activity,String runNonce){
    a=activity;nonce=runNonce;
    try{events=new IntegrationEventStore(a,Profiles.slot(a),nonce,"chromeCollapse",1,IntegrationBuildIdentity.read(Profiles.global(a)));}
    catch(Exception failure){throw new IllegalStateException("Owned collapse evidence required",failure);}
  }
  static final class CollapseView extends CompactChromeIntegrationActivity.ReloadView {
    JSONArray touchesObserved=new JSONArray();
    JSONObject documentReadyEvidence=new JSONObject();
    CollapseView(Context context,ChatSession owner){super(context,owner);}
    @Override GeckoSession newSession(){
      GeckoSession sdk=super.newSession();
      sdk.getWebExtensionController().setMessageDelegate(extension,new WebExtension.MessageDelegate(){
        @Override public void onConnect(WebExtension.Port port){
          pageMessages.onConnect(port);
          final WebExtension.PortDelegate original;
          try{java.lang.reflect.Field field=WebExtension.Port.class.getDeclaredField("delegate");field.setAccessible(true);Object value=field.get(port);if(!(value instanceof WebExtension.PortDelegate))return;original=(WebExtension.PortDelegate)value;}
          catch(ReflectiveOperationException failure){throw new IllegalStateException("Pinned SDK test delegate unavailable",failure);}
          port.setDelegate(new WebExtension.PortDelegate(){
            @Override public void onPortMessage(Object message,WebExtension.Port incoming){
              Object forwarded=message;boolean mapped=false;
              if(message instanceof JSONObject){JSONObject data=(JSONObject)message;
                mapped=ChromeCollapseDocumentReadyAdapter.maps(data.optString("kind"),data.optString("url"),rawUrl(),port.sender.url,getUrl(),incoming==port&&port.sender.session==sdk&&sdk==current,port.sender.isTopLevel(),port.sender.environmentType==WebExtension.MessageSender.ENV_TYPE_CONTENT_SCRIPT);
                if(mapped)try{
                  JSONObject normalized=new JSONObject(data.toString());normalized.put("url",ChromeCollapseDocumentReadyAdapter.VIRTUAL);forwarded=normalized;
                  documentReadyEvidence=J.obj("rawMessage",new JSONObject(data.toString()),"senderUrl",port.sender.url,"actualUrl",rawUrl(),"visibleUrl",getUrl(),"nativeSession",System.identityHashCode(port.sender.session),"currentSession",System.identityHashCode(current),"topLevel",port.sender.isTopLevel(),"contentScript",true,"normalizedMessage",new JSONObject(normalized.toString()));
                }catch(JSONException failure){throw new IllegalStateException(failure);}
              }
              // The original production delegate alone may mark the real SDK usable.
              original.onPortMessage(forwarded,incoming);
              if(mapped)try{documentReadyEvidence.put("acceptedByProduction",hasVisibleDocument());}catch(JSONException failure){throw new IllegalStateException(failure);}
            }
            @Override public void onDisconnect(WebExtension.Port incoming){original.onDisconnect(incoming);}
          });
        }
      },"pocketpage");
      return sdk;
    }
    @Override public boolean dispatchTouchEvent(MotionEvent event){
      boolean handled=super.dispatchTouchEvent(event);
      Context host=displayContext.getBaseContext();
      if(tracking&&host instanceof MainActivity&&touchesObserved.length()<256){MainActivity activity=(MainActivity)host;
        touchesObserved.put(J.obj("action",event.getActionMasked(),"pointers",event.getPointerCount(),"eventTime",event.getEventTime(),"x",event.getX(),"y",event.getY(),"height",getHeight(),"width",getWidth(),"expanded",activity.designChrome.expanded(),"toolbarVisibility",activity.toolbar.getVisibility()));}
      return handled;
    }
  }
  CollapseView web(){return (CollapseView)a.remote;}
  void pauseObservers(){a.handler.removeCallbacks(a.ticker);a.session.remove(a.sessionObserver);a.session.handler.removeCallbacks(a.session.tick);}
  void start(){
    pauseObservers();
    if(Build.VERSION.SDK_INT>=33)a.registerReceiver(receiver,new IntentFilter(ACTION),Context.RECEIVER_EXPORTED);else a.registerReceiver(receiver,new IntentFilter(ACTION));
    a.session.prefs.edit().putBoolean("networkConfigured",true).putString("proxy","socks://127.0.0.1:1080").putBoolean("requireExternalVpn",false).commit();
    a.session.networkReady=true;a.session.offline=false;a.session.guard.setBlocked(false);
    android.webkit.WebViewClient original=a.remote.client;
    a.remote.setWebViewClient(new android.webkit.WebViewClient(){@Override public void onPageFinished(android.webkit.WebView view,String url){
      if(original!=null)original.onPageFinished(view,url);
      if(url.equals(CompactChromeIntegrationActivity.ReloadView.LOCAL+"c/reload-collapse")){
        documents++;a.session.navigating=false;a.session.navigationFailed=false;pauseObservers();ready(SystemClock.elapsedRealtime()+15000);
      }
    }});
    a.remote.loadUrl(CompactChromeIntegrationActivity.ReloadView.LOCAL+"c/reload-collapse");
  }
  void ready(long deadline){
    a.remote.evaluateJavascript("(()=>{const t="+TELEMETRY+";return {ready:!!document.getElementById('prompt-textarea')&&!!document.documentElement.dataset.reloadDocument,telemetryReady:"+TELEMETRY_READY+"};})()",raw->{
      if(!J.parse(raw).optBoolean("ready")||!J.parse(raw).optBoolean("telemetryReady")||!a.remote.hasVisibleDocument()){if(SystemClock.elapsedRealtime()>deadline){emit("error",J.obj("error","Controlled chrome document or shared-DOM telemetry timeout"));return;}a.handler.postDelayed(()->ready(deadline),100);return;}
      task=a.session.deliveries.begin(TARGET,"already sent fixture question",new JSONArray(),"web",null);
      // This owned task measures retention, not the independent reply worker.
      a.session.pending=J.obj("id",task,"kind","web","engine","gecko","confirmed",true,"webSuspended",true,"userKey","id:reload-user","prompt","already sent fixture question","confirmedUrl",TARGET,"expectedUrl",TARGET);
      a.session.conversation=TARGET;a.session.prefs.edit().putString("pending",a.session.pending.toString()).putString("conversation",TARGET).commit();
      // Only the actual usable SDK document dismisses the production loading cover.
      a.session.manualAttention=false;a.loading.update();web().tracking=true;a.handler.postDelayed(()->snapshot("ready"),300);
    });
  }
  void snapshot(String command){
    pauseObservers();
    a.remote.evaluateJavascript("(()=>{const t="+TELEMETRY+";return {draft:document.getElementById('prompt-textarea').value,cookie:document.cookie,sendCount:Number(document.getElementById('send-count').textContent),path:location.pathname,document:document.documentElement.dataset.reloadDocument,scrollY:scrollY,innerWidth:innerWidth,innerHeight:innerHeight,trusted:t?.events||[],fixtureInputTelemetry:t,telemetryReady:"+TELEMETRY_READY+"};})()",raw->{
      JSONObject result=J.parse(raw);int[] location=new int[2];a.remote.getLocationOnScreen(location);
      try{result.put("command",command).put("expanded",a.designChrome.expanded()).put("toolbarVisibility",a.toolbar.getVisibility()).put("toolbarHeight",a.toolbar.getHeight())
        .put("webWidth",a.remote.getWidth()).put("webHeight",a.remote.getHeight()).put("webX",location[0]).put("webY",location[1])
        .put("surface",System.identityHashCode(a.remote)).put("sdkSession",System.identityHashCode(a.remote.current)).put("attachedSession",System.identityHashCode(a.remote.surface.getSession()))
        .put("loads",web().loads).put("stops",web().stops).put("documents",documents).put("page",a.hub.page).put("keyboard",a.keyboardVisible)
        .put("visibleDocument",a.remote.hasVisibleDocument()).put("loadingCoverVisibility",a.loading.cover.getVisibility())
        .put("documentReadyEvidence",web().documentReadyEvidence)
        .put("pending",a.session.pending==null?JSONObject.NULL:new JSONObject(a.session.pending.toString())).put("pendingStored",a.session.prefs.getString("pending",""))
        .put("activityStarts",activityStarts).put("menuOpens",menuOpens).put("windowFocus",a.hasWindowFocus())
        .put("touches",web().touchesObserved).put("nativeTouches",nativeTouches).put("toolbarBounds",a.bounds(a.toolbar)).put("chatTap",a.center(a.hub.tabs[0])).put("settingsTap",a.center(a.hub.tabs[4]));
        if(a.designChrome.expanded()){
          java.lang.reflect.Method method=DesignChrome.class.getDeclaredMethod("touchBounds",View.class);method.setAccessible(true);
          android.graphics.Rect target=(android.graphics.Rect)method.invoke(a.designChrome,a.designChrome.title);int[] origin=new int[2];a.toolbar.getLocationOnScreen(origin);target.offset(origin[0],origin[1]);
          result.put("headerSwipeFrom",J.arr(target.centerX(),target.bottom-2)).put("headerSwipeTo",J.arr(target.centerX(),origin[1]+a.dp(1))).put("headerButtonTouch",a.rect(target));
        }
        emit("collapseSnapshot",result);
      }catch(Exception failure){emit("error",J.obj("error",failure.toString()));}
    });
  }
  void emit(String kind,JSONObject result){try{events.emit(kind,result);}catch(Exception failure){events.failure(failure);}}
  void nativeTouch(MotionEvent event){if(web().tracking&&nativeTouches.length()<256)nativeTouches.put(J.obj("action",event.getActionMasked(),"pointers",event.getPointerCount(),"height",a.remote.getHeight(),"expanded",a.designChrome.expanded()));}
  void close(){try{a.unregisterReceiver(receiver);}catch(IllegalArgumentException ignored){}}
}
