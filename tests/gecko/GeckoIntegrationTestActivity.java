package local.pocketchat;

import android.app.Activity;
import android.content.*;
import android.os.*;
import android.util.Log;
import android.webkit.WebView;
import android.widget.*;
import org.json.*;

/** Test-only controlled HTTP exception; this class and manifest are absent from release. */
public class GeckoIntegrationTestActivity extends Activity {
  ChatSession session;int slot;long run;String action;boolean closedSessionRecovery,blockedRecoveryPreservesClosed,pendingFailureRetained;
  long paintStarted,paintVisible,paintFinished;
  @Override protected void attachBaseContext(Context context){super.attachBaseContext(new ProfileContext(context,Profiles.processSlot()));}
  static final class FixtureView extends GeckoWebView {
    FixtureView(Context context,ChatSession owner){super(context,owner);}
    @Override protected boolean allowedUrl(String target){
      return target.startsWith("http://127.0.0.1:8765/")||target.startsWith("http://remote-probe.invalid:8765/")||super.allowedUrl(target);
    }
  }
  @Override public void onCreate(Bundle state){
    super.onCreate(state);slot=Profiles.slot(this);
    getSharedPreferences("chat",0).edit().putString("browserEngine","systemProbe".equals(getIntent().getStringExtra("fixtureAction"))?"system":"gecko").putString("networkMode","external")
      .putString("proxy",(slot==0?"socks":"http")+"://127.0.0.1:"+(1080+slot)).putBoolean("requireExternalVpn",false)
      .putBoolean("networkConfigured",false).putBoolean("pageMode",true).commit();
    ChatSession.browserFactory=FixtureView::new;session=ChatSession.get(this);
    android.webkit.WebViewClient original=session.client();
    session.web.setWebViewClient(new android.webkit.WebViewClient(){
      @Override public void onPageStarted(WebView view,String target,android.graphics.Bitmap icon){if(target.contains("/browser-loading")){paintStarted=SystemClock.elapsedRealtime();paintVisible=paintFinished=0;}original.onPageStarted(view,target,icon);}
      @Override public void onPageCommitVisible(WebView view,String target){if(target.contains("/browser-loading")&&paintVisible==0)paintVisible=SystemClock.elapsedRealtime();original.onPageCommitVisible(view,target);}
      @Override public void onPageFinished(WebView view,String target){if(target.contains("/browser-loading"))paintFinished=SystemClock.elapsedRealtime();if(target.startsWith("http://127.0.0.1:8765/")){session.navigating=false;session.navigationFailed=false;}else original.onPageFinished(view,target);}
    });
    session.guard.setBlocked(false);session.networkReady=true;session.foreground(true);
    LinearLayout root=new LinearLayout(this);root.setOrientation(1);root.setFitsSystemWindows(true);
    TextView label=new TextView(this);label.setText("正式应用内核回归 · 环境 "+(slot+1));label.setTextSize(16);root.addView(label);
    if(session.web.getParent() instanceof android.view.ViewGroup)((android.view.ViewGroup)session.web.getParent()).removeView(session.web);
    session.web.setHost(this);root.addView(session.web,new LinearLayout.LayoutParams(-1,0,1));setContentView(root);command(getIntent());
  }
  @Override protected void onNewIntent(Intent intent){super.onNewIntent(intent);setIntent(intent);command(intent);}
  void command(Intent intent){
    action=intent.getStringExtra("fixtureAction");if(action==null)return;long serial=++run;
    waitReady(serial);
  }
  void waitReady(long serial){
    if(serial!=run)return;GeckoWebView web=(GeckoWebView)session.web;
    if("systemProbe".equals(action)){event("engineSwitch",J.obj("gecko",web.enabled));return;}
    if(web.failed){event("error",J.obj("error","Gecko startup failed"));return;}
    if("switchGecko".equals(action)&&!web.enabled){web.useEngine(true);action="read";}
    if(!web.ready){session.handler.postDelayed(()->waitReady(serial),200);return;}
    if("reading".equals(action)){web.configure(true,session.privacy.level());web.loadUrl("http://127.0.0.1:8765/browser-reading?command="+serial);session.handler.postDelayed(()->readingResult(serial,SystemClock.elapsedRealtime()+15000),200);return;}
    if("windows".equals(action)||"lostParent".equals(action)){windowFlow(serial);return;}
    if("earlyPaint".equals(action)||"cancelLoad".equals(action)){web.loadUrl("http://127.0.0.1:8765/browser-loading?command="+serial);session.handler.postDelayed(()->paintResult(serial),300);return;}
    if("closedSession".equals(action)){
      // Inject the exact SDK onKill contract (closed session), then render through the real SDK again.
      JSONObject previous=session.pending;session.pending=J.obj("kind","web","confirmed",true);
      org.mozilla.geckoview.GeckoSession stopped=web.current;stopped.close();stopped.getContentDelegate().onKill(stopped);
      String failure=session.status;session.sync();pendingFailureRetained=failure.equals(session.status)&&web.callbacks.size()==0;session.pending=previous;
      closedSessionRecovery=web.failed&&!stopped.isOpen();session.guard.setBlocked(true);web.loadUrl("http://127.0.0.1:8765/fixture");
      blockedRecoveryPreservesClosed=!stopped.isOpen();session.guard.setBlocked(false);loadFixture(serial);return;
    }
    if("switchSystem".equals(action)){web.useEngine(false);event("engineSwitch",J.obj("gecko",web.enabled));return;}
    if("switchGecko".equals(action)){web.useEngine(true);action="read";}
    if("clear".equals(action)){web.runtime.getStorageController().clearData(org.mozilla.geckoview.StorageController.ClearFlags.ALL)
      .accept(value->loadFixture(serial),error->event("error",J.obj("error","native profile clear failed")));return;}
    if("block".equals(action))session.guard.setBlocked(true);
    if("disableExtension".equals(action)){
      web.runtime.getWebExtensionController().disable(web.extension,1).accept(value->{web.current.loadUri("http://127.0.0.1:8765/fixture?context="+(slot+1)+"&action=read");session.handler.postDelayed(()->event("bootstrapCheck",J.obj("navigationFailed",session.navigationFailed)),5000);},error->event("error",J.obj("error","disable failed")));return;
    }
    loadFixture(serial);
  }
  void loadFixture(long serial){
    if(serial!=run)return;GeckoWebView web=(GeckoWebView)session.web;
    String target="http://127.0.0.1:8765/fixture?context="+(slot+1)+"&action="+action+"&command="+serial;
    if("popup".equals(action))target="http://127.0.0.1:8765/popup-main";
    web.loadUrl(target);session.handler.postDelayed(()->poll(serial),500);
  }
  void poll(long serial){
    if(serial!=run)return;
    if("block".equals(action)){event("blocked",J.obj("guard",session.guard.allowed(),"route",((GeckoWebView)session.web).route("http://127.0.0.1:8765/fixture")));return;}
    session.web.evaluateJavascript("(()=>{const text=document.getElementById('result')?.textContent;if(!text||text==='测试中…')return null;try{return JSON.parse(text)}catch{return null}})()",raw->{
      if(serial!=run)return;JSONObject result=J.parse(raw);
      if(result.length()>0&&action.equals(result.optString("action"))&&String.valueOf(slot+1).equals(result.optString("context"))&&String.valueOf(serial).equals(result.optString("command"))){((GeckoWebView)session.web).readCookies("http://127.0.0.1:8765/fixture",value->{
        if(serial!=run)return;
        try{result.put("nativeCookies",value==null?JSONObject.NULL:value);if("closedSession".equals(action)){result.put("closedSessionRecovery",closedSessionRecovery&&((GeckoWebView)session.web).current.isOpen()&&!((GeckoWebView)session.web).failed);result.put("blockedRecoveryPreservesClosed",blockedRecoveryPreservesClosed);result.put("pendingFailureRetained",pendingFailureRetained);result.put("recoveryMethod","injected SDK onKill contract; real close/open/render");}}catch(Exception ignored){}event("fixture",result);
      });return;}
      if(session.navigationFailed)event("loadError",J.obj("failed",true,"url",session.web.getUrl(),"error",session.pageError,"guard",session.guard.allowed()));
      else session.handler.postDelayed(()->poll(serial),300);
    });
  }
  void windowFlow(long serial){
    GeckoWebView web=session.web;web.loadUrl(windowUrl("one",serial));
    waitWindow(serial,"one",SystemClock.elapsedRealtime()+15000,()->{
      org.mozilla.geckoview.GeckoSession parent=web.current;web.loadUrl(windowUrl("two",serial));
      waitWindow(serial,"two",SystemClock.elapsedRealtime()+15000,()->{
        if(!web.canBack){event("error",J.obj("error","parent history missing before popup"));return;}
        tapElement(serial,"popup");
        waitWindow(serial,"three",SystemClock.elapsedRealtime()+15000,()->{
          if(web.current==parent||web.popups.size()!=1){event("error",J.obj("error","real popup did not become active"));return;}
          if("lostParent".equals(action)){parent.close();parent.getContentDelegate().onKill(parent);web.closePopup();
            if(!web.failed||web.current!=parent){event("error",J.obj("error","closed parent state was not restored"));return;}
            web.loadUrl(windowUrl("two",serial));
            waitWindow(serial,"two",SystemClock.elapsedRealtime()+15000,()->event("windowFlow",J.obj("lostParentRecovery",!web.failed&&parent.isOpen(),"popups",web.popups.size(),"url",web.getUrl())));return;
          }
          web.loadUrl(windowUrl("four",serial));
          waitWindow(serial,"four",SystemClock.elapsedRealtime()+15000,()->{
            if(!web.canBack){event("error",J.obj("error","popup history missing"));return;}
            web.goBack();waitWindow(serial,"three",SystemClock.elapsedRealtime()+15000,()->{
              web.evaluateJavascript("window.close();null",null);
              waitWindow(serial,"two",SystemClock.elapsedRealtime()+15000,()->{
                if(web.current!=parent||!web.canBack||!web.popups.isEmpty()){event("error",J.obj("error","parent history was lost after closing popup"));return;}
                web.goBack();waitWindow(serial,"one",SystemClock.elapsedRealtime()+15000,()->event("windowFlow",J.obj("realPopup",true,"parentHistoryRestored",true,"popups",web.popups.size(),"url",web.getUrl(),"pendingCallbacks",web.callbacks.size())));
              });
            });
          });
        });
      });
    });
  }
  String windowUrl(String step,long serial){return "http://127.0.0.1:8765/browser-window?step="+step+"&command="+serial;}
  void tapElement(long serial,String id){
    session.web.evaluateJavascript("(()=>{const r=document.getElementById("+JSONObject.quote(id)+").getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2}})()",raw->{
      if(serial!=run)return;JSONObject rect=J.parse(raw);if(!rect.has("x")){event("error",J.obj("error","tap element not available"));return;}
      android.graphics.Matrix transform=new android.graphics.Matrix();session.web.current.getClientToScreenMatrix(transform);
      float[] point={(float)rect.optDouble("x"),(float)rect.optDouble("y")};transform.mapPoints(point);
      event("tapNeeded",J.obj("id",id+"-"+serial,"x",Math.round(point[0]),"y",Math.round(point[1]),"shown",session.web.isShown(),"width",session.web.getWidth(),"height",session.web.getHeight(),"scale",session.web.getScale(),"paused",session.browserPaused));
    });
  }
  void waitWindow(long serial,String step,long deadline,Runnable done){
    if(serial!=run)return;
    session.web.evaluateJavascript("document.getElementById('window-step')?.textContent||null",raw->{
      if(serial!=run)return;
      if(JSONObject.quote(step).equals(raw)&&session.web.getUrl().contains("step="+step)&&session.web.painted.contains(session.web.current)){done.run();return;}
      if(SystemClock.elapsedRealtime()>deadline){event("error",J.obj("error","window flow timed out at "+step,"url",session.web.getUrl(),"failed",session.web.failed,"painted",session.web.painted.contains(session.web.current),"paused",session.browserPaused,"shown",session.web.isShown()));return;}
      session.handler.postDelayed(()->waitWindow(serial,step,deadline,done),150);
    });
  }
  void paintResult(long serial){
    if(serial!=run)return;
    if("cancelLoad".equals(action)&&paintVisible>0&&paintFinished==0){
      session.web.stopLoading();session.handler.postDelayed(()->{
        if(serial!=run)return;
        session.web.evaluateJavascript("document.querySelector('h1')?.textContent||null",raw->event("cancelledLoad",J.obj("reportedFailure",session.navigationFailed,"pageError",session.pageError,"visibleDocumentRetained",JSONObject.quote("Visible before slow resource").equals(raw))));
      },400);return;
    }
    if(paintFinished>0){event("paint",J.obj("started",paintStarted,"visible",paintVisible,"finished",paintFinished,"firstPaintBeforeComplete",paintVisible>0&&paintVisible>=paintStarted&&paintFinished-paintVisible>500));return;}
    if(paintStarted>0&&SystemClock.elapsedRealtime()-paintStarted>15000){event("error",J.obj("error","slow-resource fixture did not complete"));return;}
    session.handler.postDelayed(()->paintResult(serial),200);
  }
  void readingResult(long serial,long deadline){
    if(serial!=run)return;
    session.web.evaluateJavascript("(()=>{if(!document.getElementById('composer'))return null;const box=document.getElementById('composer').getBoundingClientRect();return {command:new URL(location.href).searchParams.get('command'),viewport:document.documentElement.clientWidth,density:devicePixelRatio,scale:visualViewport.scale,sidebarHidden:getComputedStyle(document.getElementById('sidebar')).display==='none',composerWidth:box.width,userAgent:navigator.userAgent,draft:document.getElementById('composer').value}})()",raw->{
      if(serial!=run)return;JSONObject result=J.parse(raw);
      if(String.valueOf(serial).equals(result.optString("command"))&&result.optInt("viewport")>0&&Math.abs(result.optDouble("viewport")*result.optDouble("density")-session.web.getWidth())<5&&session.web.painted.contains(session.web.current)){
        try{result.put("nativeWidth",session.web.getWidth());result.put("mobileViewport",session.web.current.getSettings().getViewportMode()==org.mozilla.geckoview.GeckoSessionSettings.VIEWPORT_MODE_MOBILE);result.put("desktopIdentity",session.web.current.getSettings().getUserAgentMode()==org.mozilla.geckoview.GeckoSessionSettings.USER_AGENT_MODE_DESKTOP);}catch(Exception ignored){}
        event("reading",result);return;
      }
      if(SystemClock.elapsedRealtime()>deadline){event("error",J.obj("error","responsive fixture not painted","paused",session.browserPaused,"shown",session.web.isShown()));return;}
      session.handler.postDelayed(()->readingResult(serial,deadline),200);
    });
  }
  void event(String kind,JSONObject result){Log.i("PocketGeckoIntegration",J.obj("kind",kind,"result",result,"nativeContext","environment-"+(slot+1),"processSlot",slot).toString());}
  @Override protected void onResume(){super.onResume();if(session!=null)session.foreground(true);}
  @Override protected void onPause(){if(session!=null)session.foreground(false);super.onPause();}
  @Override protected void onDestroy(){run++;super.onDestroy();}
}
