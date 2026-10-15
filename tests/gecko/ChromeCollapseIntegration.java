package local.pocketchat;

import android.content.*;
import android.os.*;
import android.view.*;
import org.json.*;

/** Test-only observation of the real chrome and SDK. All gestures come from adb input. */
final class ChromeCollapseIntegration {
  static final String ACTION="local.pocketchat.test.CHROME_COLLAPSE";
  static final String TARGET=MainActivity.ORIGIN+"c/reload-collapse";
  final CompactChromeIntegrationActivity a;
  final String nonce;
  final IntegrationEventStore events;
  String task="";
  int documents;
  final BroadcastReceiver receiver=new BroadcastReceiver(){@Override public void onReceive(Context c,Intent intent){
    if(!nonce.equals(intent.getStringExtra("eventNonce")))return;
    String command=intent.getStringExtra("collapseCommand");
    if(command==null||!command.matches("[a-zA-Z0-9_-]{1,80}"))return;
    if("clear".equals(command)){web().touchesObserved=new JSONArray();return;}
    a.handler.postDelayed(()->snapshot(command),150);
  }};
  ChromeCollapseIntegration(CompactChromeIntegrationActivity activity,String runNonce){
    a=activity;nonce=runNonce;
    try{events=new IntegrationEventStore(a,Profiles.slot(a),nonce,"chromeCollapse",1,IntegrationBuildIdentity.read(Profiles.global(a)));}
    catch(Exception failure){throw new IllegalStateException("Owned collapse evidence required",failure);}
  }
  static final class CollapseView extends CompactChromeIntegrationActivity.ReloadView {
    JSONArray touchesObserved=new JSONArray();
    CollapseView(Context context,ChatSession owner){super(context,owner);}
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
    a.remote.evaluateJavascript("({ready:!!document.getElementById('prompt-textarea')&&!!document.documentElement.dataset.reloadDocument})",raw->{
      if(!J.parse(raw).optBoolean("ready")||!a.remote.hasVisibleDocument()){if(SystemClock.elapsedRealtime()>deadline){emit("error",J.obj("error","Controlled chrome document timeout"));return;}a.handler.postDelayed(()->ready(deadline),100);return;}
      task=a.session.deliveries.begin(TARGET,"already sent fixture question",new JSONArray(),"web",null);
      // This owned task measures retention, not the independent reply worker.
      a.session.pending=J.obj("id",task,"kind","web","engine","gecko","confirmed",true,"webSuspended",true,"userKey","id:reload-user","prompt","already sent fixture question","confirmedUrl",TARGET,"expectedUrl",TARGET);
      a.session.conversation=TARGET;a.session.prefs.edit().putString("pending",a.session.pending.toString()).putString("conversation",TARGET).commit();
      // Only the actual usable SDK document dismisses the production loading cover.
      a.session.manualAttention=false;a.loading.update();web().tracking=true;a.designChrome.reveal();a.handler.postDelayed(()->snapshot("ready"),300);
    });
  }
  void snapshot(String command){
    pauseObservers();
    a.remote.evaluateJavascript("({draft:document.getElementById('prompt-textarea').value,cookie:document.cookie,sendCount:Number(document.getElementById('send-count').textContent),path:location.pathname,document:document.documentElement.dataset.reloadDocument,scrollY:scrollY,innerWidth:innerWidth,innerHeight:innerHeight,trusted:window.__chromeTouches||[]})",raw->{
      JSONObject result=J.parse(raw);int[] location=new int[2];a.remote.getLocationOnScreen(location);
      try{result.put("command",command).put("expanded",a.designChrome.expanded()).put("toolbarVisibility",a.toolbar.getVisibility()).put("toolbarHeight",a.toolbar.getHeight())
        .put("webWidth",a.remote.getWidth()).put("webHeight",a.remote.getHeight()).put("webX",location[0]).put("webY",location[1])
        .put("surface",System.identityHashCode(a.remote)).put("sdkSession",System.identityHashCode(a.remote.current)).put("attachedSession",System.identityHashCode(a.remote.surface.getSession()))
        .put("loads",web().loads).put("stops",web().stops).put("documents",documents).put("page",a.hub.page).put("keyboard",a.keyboardVisible)
        .put("visibleDocument",a.remote.hasVisibleDocument()).put("loadingCoverVisibility",a.loading.cover.getVisibility())
        .put("pending",a.session.pending==null?JSONObject.NULL:new JSONObject(a.session.pending.toString())).put("pendingStored",a.session.prefs.getString("pending",""))
        .put("touches",web().touchesObserved).put("chatTap",a.center(a.hub.tabs[0])).put("settingsTap",a.center(a.hub.tabs[4]));
        emit("collapseSnapshot",result);
      }catch(Exception failure){emit("error",J.obj("error",failure.toString()));}
    });
  }
  void emit(String kind,JSONObject result){try{events.emit(kind,result);}catch(Exception failure){events.failure(failure);}}
  void close(){try{a.unregisterReceiver(receiver);}catch(IllegalArgumentException ignored){}}
}
