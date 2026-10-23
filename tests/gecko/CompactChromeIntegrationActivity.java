package local.pocketchat;

import android.content.*;
import android.graphics.*;
import android.os.*;
import android.util.Log;
import android.view.*;
import android.widget.*;
import java.lang.reflect.*;
import org.json.*;

/** Test-only: actual production chrome, native hit regions and trusted Android taps. */
public final class CompactChromeIntegrationActivity extends MainActivity {
  boolean reporting;
  String command="";
  int actionCount;
  JSONObject performance=new JSONObject();
  boolean reloadFixture;String reloadBefore="",reloadArchivedDraft="";int reloadDocuments;
  ChromeCollapseIntegration collapse;
  static class ReloadView extends GeckoWebView {
    static final String LOCAL="http://127.0.0.1:8765/";boolean tracking;int stops,loads;String requested="";
    ReloadView(Context c,ChatSession owner){super(c,owner);}
    String rawUrl(){return super.getUrl();}
    @Override protected boolean allowedUrl(String target){return target!=null&&target.startsWith(LOCAL+"c/reload-");}
    @Override public String getUrl(){String raw=super.getUrl();return raw!=null&&raw.startsWith(LOCAL)?MainActivity.ORIGIN+raw.substring(LOCAL.length()):raw;}
    @Override public void loadUrl(String target){if(tracking){loads++;requested=target;}super.loadUrl(target.startsWith(MainActivity.ORIGIN)?LOCAL+target.substring(MainActivity.ORIGIN.length()):target);}
    @Override public void stopLoading(){if(tracking)stops++;super.stopLoading();}
    // Android JSONObject escapes URL slashes; translate both forms to keep real same-origin guards.
    @Override public void evaluateJavascript(String code,android.webkit.ValueCallback<String> callback){super.evaluateJavascript(code.replace(MainActivity.ORIGIN,LOCAL).replace(MainActivity.ORIGIN.replace("/","\\/"),LOCAL.replace("/","\\/")).replace("location.protocol !== 'https:' || location.hostname !== 'chatgpt.com'","location.protocol !== 'http:' || location.hostname !== '127.0.0.1' || location.port !== '8765'"),raw->{
      String output=raw;try{JSONObject value=new JSONObject(raw);String url=value.optString("url");if(url.startsWith(LOCAL)){value.put("url",MainActivity.ORIGIN+url.substring(LOCAL.length()));output=value.toString();}}catch(Exception ignored){}if(callback!=null)callback.onReceiveValue(output);
    });}
  }

  @Override public void onCreate(Bundle state){
    if(!getPackageName().endsWith(".test"))throw new SecurityException();
    reloadFixture="reloadStart".equals(getIntent().getStringExtra("compactAction"));if(reloadFixture)ChatSession.browserFactory=ReloadView::new;
    boolean collapseFixture="collapseStart".equals(getIntent().getStringExtra("compactAction"));if(collapseFixture)ChatSession.browserFactory=ChromeCollapseIntegration.CollapseView::new;
    ProfileCatalog.get(this).created(0);
    Profiles.rename(this,0,getIntent().getBooleanExtra("longName",true)?"长文阅读与文件整理和日常会话测试环境":"默认环境");
    getSharedPreferences("chat",0).edit().putString("browserEngine","system").putString("networkMode","external").putBoolean("networkConfigured",false).putBoolean("environmentInitialized",true).putBoolean("pageMode",false).remove("pending").commit();
    AppSettings.put(this,"brandSeen","true");
    AppSettings.put(this,"updateAutoCheck","false");
    getIntent().putExtra("openWindowAction",collapseFixture?"chat":"native-smoke");
    // This layout fixture does not open a website or make synthetic state a real connection.
    ChatSession.get(this).manualAttention=true;
    super.onCreate(state);
    command=getIntent().getStringExtra("compactCommand");
    if(collapseFixture){collapse=new ChromeCollapseIntegration(this,getIntent().getStringExtra("eventNonce"));collapse.start();return;}
    // Historical geometry/touch assertions explicitly inspect expanded chrome.
    designChrome.reveal();
    if(reloadFixture){
      handler.removeCallbacks(ticker);session.remove(sessionObserver);session.handler.removeCallbacks(session.tick);
      session.prefs.edit().putBoolean("networkConfigured",true).putString("proxy","socks://127.0.0.1:1080").putBoolean("requireExternalVpn",false).commit();session.networkReady=true;session.offline=false;session.guard.setBlocked(false);
      android.webkit.WebViewClient original=remote.client;remote.setWebViewClient(new android.webkit.WebViewClient(){@Override public void onPageFinished(android.webkit.WebView view,String url){if(original!=null)original.onPageFinished(view,url);if(url.startsWith(ReloadView.LOCAL)){session.handler.removeCallbacks(session.tick);session.navigating=false;session.navigationFailed=false;reloadDocuments++;waitReloadDocument(SystemClock.elapsedRealtime()+15000);}}});
      remote.loadUrl(ReloadView.LOCAL+"c/reload-A");return;
    }
    handler.postDelayed(()->{
      handler.removeCallbacks(ticker);
      session.remove(sessionObserver);
      reporting=true;
      status("对话已改变，请检查上次发送；不会自动重发");
      if(status.getVisibility()!=View.GONE||status.isClickable())throw new AssertionError("Conversation change banner must be quiet");
      status("发送失败，请检查网络");
      if(status.getVisibility()!=View.VISIBLE||!status.isClickable())throw new AssertionError("Real send errors must remain visible");
      status("");
      snapshot("ready");
    },600);
  }

  @Override void startNetwork(){}

  @Override protected void onDestroy(){if(collapse!=null)collapse.close();super.onDestroy();}

  @Override public boolean dispatchTouchEvent(MotionEvent event){boolean handled=super.dispatchTouchEvent(event);if(collapse!=null)collapse.nativeTouch(event);return handled;}

  @Override protected void onNewIntent(Intent intent){
    super.onNewIntent(intent);
    command=intent.getStringExtra("compactCommand");
    if(collapse!=null)return;
    if(reloadFixture){reloadCommand(intent.getStringExtra("compactAction"));return;}
    if("snapshot".equals(intent.getStringExtra("compactAction")))handler.post(()->snapshot("snapshot"));
    if("performance".equals(intent.getStringExtra("compactAction")))handler.post(this::performance);
  }
  void waitReloadDocument(long deadline){
    remote.evaluateJavascript("({ready:!!document.getElementById('prompt-textarea'),path:location.pathname})",raw->{JSONObject ready=J.parse(raw);if(!ready.optBoolean("ready")){if(SystemClock.elapsedRealtime()>deadline){reloadEvent("error",J.obj("error","Controlled reload document timeout"));return;}handler.postDelayed(()->waitReloadDocument(deadline),100);return;}
      String script=session.driver.replace("__ACTION__","action").replace("__ARG__","arg");remote.evaluateJavascript("window.__pocketReadDriver=(action,arg)=>"+script+";({installed:true})",unused->{session.handler.removeCallbacks(session.tick);if(reloadDocuments==1){((ReloadView)remote).tracking=true;reloadCommand("prepareBusy");}else reloadSnapshot("reloaded");});
    });
  }
  void reloadCommand(String action){
    session.handler.removeCallbacks(session.tick);handler.removeCallbacks(ticker);
    if("prepareBusy".equals(action)){
      String url=MainActivity.ORIGIN+"c/reload-A",id=session.deliveries.begin(url,"already sent fixture question",new JSONArray(),"web",null);session.pending=J.obj("id",id,"kind","web","engine","gecko","confirmed",true,"userKey","id:reload-user","prompt","already sent fixture question","confirmedUrl",url,"expectedUrl",url);session.conversation=url;session.prefs.edit().putString("pending",session.pending.toString()).putString("conversation",url).commit();
      remote.evaluateJavascript("history.replaceState(null,'','/c/reload-B');document.getElementById('composer').insertAdjacentHTML('beforeend','<button id=\"stop-button\" data-testid=\"stop-button\" aria-label=\"Stop\">Stop</button>');({ready:true})",raw->reloadSnapshot("reloadReady"));return;
    }
    if("requestReload".equals(action)){requestReload();waitReloadModal(SystemClock.elapsedRealtime()+10000);return;}
    if("reloadSnapshot".equals(action)){reloadSnapshot("reloadSnapshot");return;}
    if("changeRoute".equals(action)){remote.evaluateJavascript("history.replaceState(null,'','/c/reload-C');({changed:true})",raw->reloadSnapshot("routeChanged"));return;}
    if("restoreRoute".equals(action)){remote.evaluateJavascript("history.replaceState(null,'','/c/reload-B');({changed:true})",raw->reloadSnapshot("routeRestored"));return;}
    if("idleReload".equals(action)){session.pending=null;session.prefs.edit().remove("pending").commit();session.state=new JSONObject();remote.evaluateJavascript("document.getElementById('stop-button')?.remove();document.getElementById('prompt-textarea').value='   ';({idle:true})",raw->{requestReload();});}
  }
  void waitReloadModal(long deadline){
    if(reloadDialog!=null&&reloadDialog.isShowing()){
      JSONArray controls=new JSONArray();boolean laidOut=true;
      for(int i=0;i<reloadDialog.footer.getChildCount();i++){View view=reloadDialog.footer.getChildAt(i);if(view instanceof Button){Rect visible=new Rect();Rect bounds=screenBounds(view);laidOut&=view.isShown()&&view.getGlobalVisibleRect(visible)&&visible.width()>0&&visible.height()>0&&bounds.width()>0&&bounds.height()>0&&view.isEnabled()&&view.isClickable();controls.put(J.obj("label",((Button)view).getText().toString(),"bounds",J.arr(bounds.left,bounds.top,bounds.right,bounds.bottom),"x",bounds.centerX(),"y",bounds.centerY(),"enabled",view.isEnabled(),"clickable",view.isClickable()));}}
      if(laidOut&&controls.length()==2){reloadEvent("reloadModal",J.obj("centered",reloadDialog.getWindow().getAttributes().gravity==Gravity.CENTER,"controls",controls));return;}
    }
    if(SystemClock.elapsedRealtime()>deadline){reloadEvent("error",J.obj("error","Reload confirmation did not appear"));return;}handler.postDelayed(()->waitReloadModal(deadline),50);
  }
  void reloadSnapshot(String event){remote.evaluateJavascript("({body:document.documentElement.outerHTML,draft:document.getElementById('prompt-textarea').value,cookie:document.cookie,sendCount:Number(document.getElementById('send-count').textContent),path:location.pathname,document:document.documentElement.getAttribute('data-reload-document')})",raw->{
    JSONObject result=J.parse(raw);ReloadView web=(ReloadView)remote;try{result.put("documents",reloadDocuments).put("stops",web.stops).put("loads",web.loads).put("requested",web.requested).put("currentUrl",web.getUrl()).put("cachedResumeUrl",session.resumeUrl()).put("modal",reloadDialog!=null&&reloadDialog.isShowing());}catch(Exception ignored){}
    if("reloadReady".equals(event)){reloadBefore=result.toString();reloadArchivedDraft=result.optString("draft");}
    if("reloaded".equals(event))session.webStore.worker.execute(()->{boolean saved=false;JSONArray rows=DraftArchive.get(session.context).list(MainActivity.ORIGIN+"c/reload-B");for(int i=0;i<rows.length();i++)saved|=reloadArchivedDraft.equals(rows.optJSONObject(i).optString("body"));boolean archived=saved;handler.post(()->{try{result.put("draftArchived",archived);}catch(Exception ignored){}reloadEvent(event,result);});});else reloadEvent(event,result);
  });}
  void reloadEvent(String event,JSONObject value){Log.i("PocketCompactChrome",J.obj("command",command,"event",event,"reload",value).toString());}

  @Override void showDrawer(){
    super.showDrawer();
    // The environment menu now opens the real environment Activity. Its
    // startActivity event is the single observable action, not a second drawer.
  }

  @Override void chooseEnvironment(){super.chooseEnvironment();if(reporting)event("environment");}
  @Override void moreSheet(){
    if(collapse!=null)collapse.menuOpens++;
    super.moreSheet();
    if(reporting)event("more");
  }

  @Override void showPage(boolean show){
    super.showPage(show);
  }

  @Override public void startActivity(Intent intent){
    if(collapse!=null)collapse.activityStarts++;
    super.startActivity(intent);
    if(reporting)event("activity:"+(intent.getComponent()==null?"":intent.getComponent().getClassName()));
  }

  void event(String action){
    actionCount++;
    Log.i("PocketCompactChrome",J.obj("command",command,"event","action","action",action,"actions",actionCount,"page",hub.page).toString());
  }

  void performance(){
    try{
      handler.removeCallbacks(ticker);session.handler.removeCallbacks(session.tick);session.remove(sessionObserver);
      // Settle legitimate initial state changes before measuring repeated updates.
      NetworkMetricsUi.update(this);designChrome.update();
      handler.postDelayed(()->{
        UiPerfStats.begin();
        for(int i=0;i<100;i++){NetworkMetricsUi.update(this);designChrome.update();}
        handler.postDelayed(()->{
          JSONObject burst=UiPerfStats.end();
          try{
            if(burst.optLong("metricsRefreshes")!=1||burst.optLong("chromeUpdates")!=1||burst.optLong("chromeTextChanges")!=0||burst.optLong("chromeBackgroundChanges")!=0)throw new AssertionError("Repeated chrome requests did not merge: "+burst);
            noUiIo(burst);performance.put("burst",burst);
            backgroundPerformance();
            boolean oldMode=session.internalNetwork();
            session.prefs.edit().putString("networkMode","internal").apply();
            // A real encrypted configuration read must run on audit.worker,
            // while UI counters stay free of that I/O.
            NetworkMetricsUi.update(this);
            handler.postDelayed(()->{session.audit.lastRefresh=0;UiPerfStats.begin();periodicPerformance(0,oldMode);},200);
          }catch(Throwable error){performanceFailure(error);}
        },200);
      },200);
    }catch(Throwable error){performanceFailure(error);}
  }

  void backgroundPerformance()throws Exception{
    DesignUi.Stars background=new DesignUi.Stars(this);background.setBounds(0,0,16,32);background.enabled=true;
    Bitmap pixels=Bitmap.createBitmap(16,32,Bitmap.Config.ARGB_8888);Canvas canvas=new Canvas(pixels);
    background.draw(canvas);int[] first=new int[16*32],last=new int[16*32];pixels.getPixels(first,0,16,0,0,16,32);
    UiPerfStats.begin();for(int i=0;i<100;i++)background.draw(canvas);JSONObject result=UiPerfStats.end();
    pixels.getPixels(last,0,16,0,0,16,32);boolean same=java.util.Arrays.equals(first,last);
    background.enabled=false;background.draw(canvas);boolean plain=pixels.getPixel(8,16)==DesignUi.BG;pixels.recycle();
    noUiIo(result);if(result.optLong("starDraws")!=100||!same||!plain)throw new AssertionError("Background draw cache changed output: "+result);
    performance.put("background",result.put("stablePixels",same).put("plainBackground",plain));
  }

  void periodicPerformance(int count,boolean oldMode){
    if(count<5){NetworkMetricsUi.update(this);handler.postDelayed(()->periodicPerformance(count+1,oldMode),1200);return;}
    try{
      JSONObject result=UiPerfStats.end();noUiIo(result);
      if(result.optLong("metricsRefreshes")!=5||result.optLong("chromeTextChanges")!=0||result.optLong("chromeBackgroundChanges")!=0)throw new AssertionError("Idle chrome performed repeated mutations: "+result);
      performance.put("periodic",result.put("durationMs",6000));
      session.prefs.edit().putString("networkMode",oldMode?"internal":"external").apply();
      String original=designChrome.title.getText().toString();Profiles.rename(this,0,"性能回归新名称");
      waitForRename(original,SystemClock.uptimeMillis()+6000);
    }catch(Throwable error){performanceFailure(error);}
  }

  void waitForRename(String original,long deadline){
    designChrome.update();
    handler.postDelayed(()->{
      if("性能回归新名称".contentEquals(designChrome.title.getText())){
        try{performance.put("rename",true);}catch(Exception ignored){}
        GeckoWebView originalSurface=remote;org.mozilla.geckoview.GeckoSession sdk=remote.current;
        String url=remote.getUrl();UiPerfStats.begin();showPage(false);designChrome.update();
        handler.postDelayed(()->{
          try{
            JSONObject result=UiPerfStats.end();noUiIo(result);
            boolean originalOnly=pageMode&&remote==originalSurface&&remote.current==sdk&&java.util.Objects.equals(url,remote.getUrl())&&noNativeChat();
            if(result.optLong("chromeBackgroundChanges")!=0||!originalOnly)throw new AssertionError("Legacy display request changed the original-only surface: "+result);
            performance.put("originalOnly",result.put("sameSurface",remote==originalSurface).put("sameSdkSession",remote.current==sdk).put("sameUrl",java.util.Objects.equals(url,remote.getUrl())).put("pageMode",pageMode).put("noNativeChat",noNativeChat()));Profiles.rename(this,0,original);designChrome.update();
            Log.i("PocketCompactChrome",J.obj("command",command,"event","performance","status","passed","performance",performance).toString());
          }catch(Throwable error){performanceFailure(error);}
        },200);
      }else if(SystemClock.uptimeMillis()<deadline)waitForRename(original,deadline);
      else performanceFailure(new AssertionError("Asynchronous environment name became stale"));
    },100);
  }

  void noUiIo(JSONObject result){for(String key:new String[]{"mainSealedReads","mainSealedWrites","mainCatalogReads","mainHeartbeatWrites"})if(result.optLong(key)!=0)throw new AssertionError("UI hot path performed "+key+": "+result);}
  void performanceFailure(Throwable error){UiPerfStats.end();Log.i("PocketCompactChrome",J.obj("command",command,"event","performance","error",error.toString(),"performance",performance).toString());}

  void snapshot(String event){
    try{
      handler.removeCallbacks(ticker);
      session.remove(sessionObserver);
      long now=System.currentTimeMillis();
      JSONObject config=J.obj("subscriptionUrl","https://example.test/compact-layout","exitHost","example.test","exitPort",1080,"exitRegion","日本 · Tokyo");
      JSONObject runtime=J.obj("at",now,"mode","internal","configured",true,"connected",true,"exitId",NetworkCatalog.exitId(config),"subscriptionId",NativeNetwork.hash(config.optString("subscriptionUrl")),"ip","203.0.113.25","entry","Entry|大阪 03","delayEntry","Entry|大阪 03","latencyRemaining",120000,"latencyMeasuring",false,"delay",42,"delayAt",now);
      WindowNetworkState network=new WindowNetworkState(this,ProfileCatalog.get(this).item(0),config,runtime,true,now);
      // Invoke the production renderer with explicitly synthetic layout data.
      Method show=DesignChrome.class.getDeclaredMethod("showNetwork",WindowNetworkState.class);
      show.setAccessible(true);
      // onResume may have queued a real chrome render before this fixture took
      // control. Let it settle, then render the explicitly synthetic layout state.
      toolbar.postDelayed(()->{try{show.invoke(designChrome,network);toolbar.postDelayed(()->report(event,network),100);}catch(Exception error){Log.i("PocketCompactChrome",J.obj("command",command,"event",event,"error",error.toString()).toString());}},200);
    }catch(Exception error){Log.i("PocketCompactChrome",J.obj("command",command,"event",event,"error",error.toString()).toString());}
  }

  void report(String event,WindowNetworkState network){
    try{
      TextView latency=(TextView)field("latencyWord");
      View more=(View)field("more");
      View top=(View)field("top");
      Method touch=DesignChrome.class.getDeclaredMethod("touchBounds",View.class);
      touch.setAccessible(true);
      String[] names={"drawer","environment","more"};
      View[] views={navigation,designChrome.title,more};
      int[] origin=new int[2];toolbar.getLocationOnScreen(origin);
      JSONArray controls=new JSONArray();
      for(int i=0;i<views.length;i++){
        Rect hit=(Rect)touch.invoke(designChrome,views[i]);hit.offset(origin[0],origin[1]);
        controls.put(J.obj("name",names[i],"visible",bounds(views[i]),"touch",rect(hit),"widthDp",hit.width()/density(),"heightDp",hit.height()/density(),"tap",J.arr(hit.centerX(),hit.bottom-1)));
      }
      JSONArray texts=new JSONArray();
      for(TextView text:new TextView[]{designChrome.title,networkLine,latency,designChrome.stateWord}){
        Paint.FontMetrics font=text.getPaint().getFontMetrics();
        texts.put(J.obj("text",text.getText().toString(),"bounds",bounds(text),"fontHeight",font.bottom-font.top,"contentHeight",text.getHeight()-text.getPaddingTop()-text.getPaddingBottom(),"inkWidth",text.getPaint().measureText(text.getText().toString()),"contentWidth",text.getWidth()-text.getPaddingLeft()-text.getPaddingRight(),"ellipsized",text.getLayout()!=null&&text.getLayout().getLineCount()>0&&text.getLayout().getEllipsisCount(0)>0,"clickable",text.isClickable()));
      }
      Rect networkBounds=screenBounds(designChrome.networkRow);
      Rect toolbarBounds=screenBounds(toolbar);
      TextView dot=designChrome.dot;
      Paint.FontMetrics dotFont=dot.getPaint().getFontMetrics();
      JSONObject decorativeDot=J.obj("textSizeDp",dot.getTextSize()/density(),"inkWidth",dot.getPaint().measureText(dot.getText().toString()),"contentWidth",dot.getWidth()-dot.getPaddingLeft()-dot.getPaddingRight(),"fontHeight",dotFont.bottom-dotFont.top,"contentHeight",dot.getHeight()-dot.getPaddingTop()-dot.getPaddingBottom());
      Log.i("PocketCompactChrome",J.obj("command",command,"event",event,"actions",actionCount,"page",hub.page,"pageMode",pageMode,"geckoOnly",remote.enabled,"noNativeChat",noNativeChat(),"systemWebViews",systemWebViews(getWindow().getDecorView()),"viewportDp",getResources().getDisplayMetrics().widthPixels/density(),"fontScale",getResources().getConfiguration().fontScale,"toolbar",rect(toolbarBounds),"toolbarHeightDp",toolbar.getHeight()/density(),"topHeightDp",top.getHeight()/density(),"networkHeightDp",designChrome.networkRow.getHeight()/density(),"networkBounds",rect(networkBounds),"networkTap",J.arr(networkBounds.centerX(),networkBounds.centerY()),"stateTap",center(designChrome.stateWord),"networkClickable",designChrome.networkRow.isClickable(),"networkFocusable",designChrome.networkRow.isFocusable(),"networkBackground",designChrome.networkRow.getBackground()==null?"none":designChrome.networkRow.getBackground().getClass().getName(),"networkDescription",String.valueOf(designChrome.networkRow.getContentDescription()),"latency",latency.getText().toString(),"expectedLatency",network.latency+network.latencyTimer,"controls",controls,"texts",texts,"decorativeDot",decorativeDot).toString());
    }catch(Exception error){Log.i("PocketCompactChrome",J.obj("command",command,"event",event,"error",error.toString()).toString());}
  }

  boolean noNativeChat(){return reader==null&&input==null&&composer==null&&nativeTab==null&&webTab==null;}
  static int systemWebViews(View view){int count=view instanceof android.webkit.WebView?1:0;if(view instanceof ViewGroup){ViewGroup group=(ViewGroup)view;for(int i=0;i<group.getChildCount();i++)count+=systemWebViews(group.getChildAt(i));}return count;}

  Object field(String name)throws Exception{Field field=DesignChrome.class.getDeclaredField(name);field.setAccessible(true);return field.get(designChrome);}
  float density(){return getResources().getDisplayMetrics().density;}
  JSONArray bounds(View view){return rect(screenBounds(view));}
  Rect screenBounds(View view){int[] at=new int[2];view.getLocationOnScreen(at);return new Rect(at[0],at[1],at[0]+view.getWidth(),at[1]+view.getHeight());}
  JSONArray rect(Rect value){return J.arr(value.left,value.top,value.right,value.bottom);}
  JSONArray center(View view){Rect bounds=screenBounds(view);return J.arr(bounds.centerX(),bounds.centerY());}
}
