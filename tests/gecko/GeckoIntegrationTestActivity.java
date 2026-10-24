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
  ChatSession session;int slot;long run;String action;boolean closedSessionRecovery,blockedRecoveryPreservesClosed,pendingFailureRetained,activityResumed;
  long paintCommand,paintRequested,paintStarted,paintVisible,paintFinished,paintFinishedBeforeCancel=-1;String paintTarget="";boolean paintCommitted,paintCancelledBeforeFinish;org.mozilla.geckoview.GeckoSession paintSession;
  String initialRouteNetwork="";long initialRouteStableSince;int initialRouteSamples;
  // Synthetic read invocations only; observes existing polls without scheduling work.
  DeviceReadinessObservation readinessObservation;Boolean readinessForeground;
  JSONObject readinessNetwork;long readinessForegroundAt;
  final int[] readingZoomSamples=new int[4];String readingZoomLast="";long readingZoomLastSample;JSONObject readingZoomReadiness;
  ReadingBoundsCase readingBoundsCase;JSONObject readingBoundsFitResult;
  static final class ReadingBoundsCase {
    int privacy;long command;boolean fingerprintingProtected;JSONObject before,pan;org.mozilla.geckoview.GeckoSession nativeSession;android.view.View surface;
    org.mozilla.geckoview.GeckoSession.CompositorScrollDelegate priorDelegate;float scrollX,scrollY,zoom;int updates;long stableSince;int stableSamples;
  }
  @Override protected void attachBaseContext(Context context){super.attachBaseContext(new ProfileContext(context,Profiles.processSlot()));}
  static final class FixtureView extends GeckoWebView {
    boolean continuityTracing;String continuityUrl="";int continuityLoads,continuityStops,resourcePauseCalls;JSONArray continuityResults=new JSONArray();
    @Override public void onPause(){resourcePauseCalls++;super.onPause();}
    @Override public void stopLoading(){if(continuityTracing)continuityStops++;super.stopLoading();}
    boolean chooserOrigin;Runnable nativeGestureComplete;int nativeGestureCount,nativeFocusRequests,nativeFocusMeasurements;long lastFocusDocument;String lastFocusUrl="";
    @Override void revealReadingFocus(String expected,java.util.function.BooleanSupplier fence){nativeFocusRequests++;final int[] checks={0};super.revealReadingFocus(expected,()->{boolean current=fence.getAsBoolean();if(current&&++checks[0]==2){nativeFocusMeasurements++;lastFocusUrl=expected;lastFocusDocument=owner.reading.document;}return current;});}
    boolean initialRouteReady;java.util.function.Consumer<String> initialRouteReporter;
    boolean nativeGeometryActive,nativeGeometrySwipes,nativeGeometryStable;JSONArray nativeGeometryTrace=new JSONArray();NativeGeometry nativeGeometryPrevious,nativeGeometryExpected;
    long nativeUnchangedTouchEvents,nativeRedundantTouchSyncs,nativeFirstTouchSyncs=-1;boolean nativeFirstTouchOriginCorrect;
    @Override public String getUrl(){return chooserOrigin?MainActivity.ORIGIN:super.getUrl();}
    @Override public void evaluateJavascript(String code,android.webkit.ValueCallback<String> callback){
      if(continuityTracing&&code.startsWith("window['__pocket_")){String request=code;super.evaluateJavascript(code,raw->{JSONObject value=J.parse(raw);if(value.length()>0)continuityResults.put(J.obj("at",SystemClock.elapsedRealtime(),"request",request,"result",value));if(callback!=null)callback.onReceiveValue(raw);});}
      else super.evaluateJavascript(code,callback);
    }
    FixtureView(Context context,ChatSession owner){super(context,owner);}
    @Override public void loadUrl(String target){if(continuityTracing)continuityLoads++;java.util.function.Consumer<String> reporter=initialRouteReporter;if(reporter!=null){initialRouteReporter=null;reporter.accept(target);}super.loadUrl(target);}
    @Override protected boolean allowedUrl(String target){
      return target.startsWith("http://127.0.0.1:8765/")||target.startsWith("http://remote-probe.invalid:8765/")||super.allowedUrl(target);
    }
    @Override boolean readingPage(String target){return target.startsWith("http://127.0.0.1:8765/browser-reading")||super.readingPage(target);}
    @Override public boolean dispatchTouchEvent(android.view.MotionEvent event){
      NativeGeometry before=nativeGeometryActive?NativeGeometry.read(this):null;long syncs=nativeGeometryActive?nativeSyncs():0;
      boolean cached=nativeGeometryActive&&NativeGeometry.cacheMatches(this,before);
      boolean handled=super.dispatchTouchEvent(event);
      if(nativeGeometryActive){
        NativeGeometry after=NativeGeometry.read(this);long added=nativeSyncs()-syncs;
        if(cached){nativeUnchangedTouchEvents++;nativeRedundantTouchSyncs+=added;}
        if(nativeFirstTouchSyncs<0&&event.getActionMasked()==android.view.MotionEvent.ACTION_DOWN){nativeFirstTouchSyncs=added;nativeFirstTouchOriginCorrect=NativeGeometry.cacheMatches(this,after);}
        recordNativeGeometry("touch-"+event.getActionMasked(),before,after,added,cached);
      }
      if(nativeGestureComplete!=null&&event.getActionMasked()==android.view.MotionEvent.ACTION_UP&&++nativeGestureCount==3){Runnable done=nativeGestureComplete;nativeGestureComplete=null;owner.handler.post(done);}return handled;
    }
    @Override protected void onLayout(boolean changed,int l,int t,int r,int b){
      NativeGeometry before=nativeGeometryActive?NativeGeometry.read(this):null;long syncs=nativeGeometryActive?nativeSyncs():0;
      boolean cached=nativeGeometryActive&&NativeGeometry.cacheMatches(this,before);super.onLayout(changed,l,t,r,b);
      if(nativeGeometryActive)recordNativeGeometry("layout",before,NativeGeometry.read(this),nativeSyncs()-syncs,cached);
    }
    long nativeSyncs(){try{return number(this,"surfaceOriginSyncs");}catch(ReflectiveOperationException missing){return -1;}}
    void recordNativeGeometry(String source,NativeGeometry before,NativeGeometry after,long added,boolean cached){
      boolean changed=before==null||!before.same(after),sincePrevious=nativeGeometryPrevious==null||!nativeGeometryPrevious.same(before);
      if(nativeGeometrySwipes&&(nativeGeometryExpected==null||!nativeGeometryExpected.same(before)||!nativeGeometryExpected.same(after)))nativeGeometryStable=false;
      if(nativeGeometryTrace.length()<32&&(changed||sincePrevious||added!=0))nativeGeometryTrace.put(J.obj("source",source,"elapsed",SystemClock.elapsedRealtime(),"before",before==null?JSONObject.NULL:before.json(),"after",after==null?JSONObject.NULL:after.json(),"syncs",added,"cacheMatchedBefore",cached,"changedDuringCall",changed,"changedSincePrevious",sincePrevious));
      nativeGeometryPrevious=after;
    }
  }
  /** Controlled-test geometry only. No production hooks or per-touch logging. */
  static final class NativeGeometry {
    android.view.View child;org.mozilla.geckoview.GeckoSession attached;
    int x,y,top,right,bottom,left,webWidth,webHeight,surfaceWidth,surfaceHeight,childWidth,childHeight,rootWidth,rootHeight,imeBottom;
    int visibleSafeTop,visibleSafeRight,visibleSafeBottom,visibleSafeLeft,navigationInsets;
    boolean imeVisible,focused,statusBarsVisible,navigationBarsVisible;
    static NativeGeometry read(FixtureView web){
      if(web.surface==null||!web.surface.isAttachedToWindow())return null;
      android.view.WindowInsets window=web.surface.getRootWindowInsets();if(window==null)return null;
      NativeGeometry value=new NativeGeometry();value.child=web.surface.getChildCount()>0?web.surface.getChildAt(0):web.surface;value.attached=web.surface.getSession();
      int[] point=new int[2];value.child.getLocationOnScreen(point);value.x=point[0];value.y=point[1];
      if(Build.VERSION.SDK_INT>=30){
        int safeTypes=android.view.WindowInsets.Type.systemBars()|android.view.WindowInsets.Type.displayCutout();android.graphics.Insets safe=window.getInsets(safeTypes);value.top=safe.top;value.right=safe.right;value.bottom=safe.bottom;value.left=safe.left;
        android.graphics.Insets normal=window.getInsetsIgnoringVisibility(safeTypes);value.visibleSafeTop=normal.top;value.visibleSafeRight=normal.right;value.visibleSafeBottom=normal.bottom;value.visibleSafeLeft=normal.left;
        android.graphics.Insets navigation=window.getInsetsIgnoringVisibility(android.view.WindowInsets.Type.navigationBars());value.navigationInsets=navigation.top+navigation.right+navigation.bottom+navigation.left;value.statusBarsVisible=window.isVisible(android.view.WindowInsets.Type.statusBars());value.navigationBarsVisible=window.isVisible(android.view.WindowInsets.Type.navigationBars());
        value.imeVisible=window.isVisible(android.view.WindowInsets.Type.ime());value.imeBottom=window.getInsets(android.view.WindowInsets.Type.ime()).bottom;
      }
      else if(Build.VERSION.SDK_INT>=28){android.view.DisplayCutout cutout=window.getDisplayCutout();if(cutout!=null){value.top=cutout.getSafeInsetTop();value.right=cutout.getSafeInsetRight();value.bottom=cutout.getSafeInsetBottom();value.left=cutout.getSafeInsetLeft();}}
      value.webWidth=web.getWidth();value.webHeight=web.getHeight();value.surfaceWidth=web.surface.getWidth();value.surfaceHeight=web.surface.getHeight();value.childWidth=value.child.getWidth();value.childHeight=value.child.getHeight();value.rootWidth=web.getRootView().getWidth();value.rootHeight=web.getRootView().getHeight();value.focused=web.hasWindowFocus();return value;
    }
    boolean normalBarsReady(){return Build.VERSION.SDK_INT<30||statusBarsVisible&&navigationBarsVisible&&navigationInsets>0&&top==visibleSafeTop&&right==visibleSafeRight&&bottom==visibleSafeBottom&&left==visibleSafeLeft;}
    boolean same(NativeGeometry other){return other!=null&&child==other.child&&attached==other.attached&&x==other.x&&y==other.y&&top==other.top&&right==other.right&&bottom==other.bottom&&left==other.left&&webWidth==other.webWidth&&webHeight==other.webHeight&&surfaceWidth==other.surfaceWidth&&surfaceHeight==other.surfaceHeight&&childWidth==other.childWidth&&childHeight==other.childHeight&&rootWidth==other.rootWidth&&rootHeight==other.rootHeight&&imeVisible==other.imeVisible&&imeBottom==other.imeBottom&&focused==other.focused&&statusBarsVisible==other.statusBarsVisible&&navigationBarsVisible==other.navigationBarsVisible&&navigationInsets==other.navigationInsets&&visibleSafeTop==other.visibleSafeTop&&visibleSafeRight==other.visibleSafeRight&&visibleSafeBottom==other.visibleSafeBottom&&visibleSafeLeft==other.visibleSafeLeft;}
    JSONObject json(){return J.obj("child",System.identityHashCode(child),"session",System.identityHashCode(attached),"x",x,"y",y,"top",top,"right",right,"bottom",bottom,"left",left,"webWidth",webWidth,"webHeight",webHeight,"surfaceWidth",surfaceWidth,"surfaceHeight",surfaceHeight,"childWidth",childWidth,"childHeight",childHeight,"rootWidth",rootWidth,"rootHeight",rootHeight,"imeVisible",imeVisible,"imeBottom",imeBottom,"focused",focused,"statusBarsVisible",statusBarsVisible,"navigationBarsVisible",navigationBarsVisible,"navigationInsets",navigationInsets,"visibleSafeTop",visibleSafeTop,"visibleSafeRight",visibleSafeRight,"visibleSafeBottom",visibleSafeBottom,"visibleSafeLeft",visibleSafeLeft);}
    static boolean cacheMatches(FixtureView web,NativeGeometry value){
      if(value==null)return false;
      try{return field(web,"originKnown").getBoolean(web)&&field(web,"originView").get(web)==value.child&&field(web,"originSession").get(web)==value.attached&&number(web,"originX")==value.x&&number(web,"originY")==value.y&&number(web,"insetTop")==value.top&&number(web,"insetRight")==value.right&&number(web,"insetBottom")==value.bottom&&number(web,"insetLeft")==value.left;}catch(ReflectiveOperationException missing){return false;}
    }
  }
  @Override public void onCreate(Bundle state){
    super.onCreate(state);slot=Profiles.slot(this);ProfileCatalog.get(this).created(slot);
    boolean legacyDisplay="legacyEnginePreference".equals(getIntent().getStringExtra("fixtureAction"));
    getSharedPreferences("chat",0).edit().putString("browserEngine",legacyDisplay?"system":"gecko").putString("networkMode","external")
      .putString("proxy",(slot==0?"socks":"http")+"://127.0.0.1:"+(1080+slot)).putBoolean("requireExternalVpn",false)
      .putBoolean("networkConfigured",false).putBoolean("pageMode",!legacyDisplay).commit();
    ChatSession.browserFactory=FixtureView::new;session=ChatSession.get(this);
    android.webkit.WebViewClient original=session.client();
    session.web.setWebViewClient(new android.webkit.WebViewClient(){
      @Override public void onPageStarted(WebView view,String target,android.graphics.Bitmap icon){if(paintCallback(target)&&!paintCommitted){paintCommitted=true;paintStarted=SystemClock.elapsedRealtime();}original.onPageStarted(view,target,icon);}
      @Override public void onPageCommitVisible(WebView view,String target){if(paintCallback(target)&&paintCommitted&&paintVisible==0)paintVisible=SystemClock.elapsedRealtime();original.onPageCommitVisible(view,target);}
      @Override public void onPageFinished(WebView view,String target){if(paintCallback(target)&&paintCommitted)paintFinished=SystemClock.elapsedRealtime();if(target.startsWith("http://127.0.0.1:8765/")){session.navigating=false;session.navigationFailed=false;session.reading.visible(target);}else original.onPageFinished(view,target);}
    });
    session.foreground(true);
    LinearLayout root=new LinearLayout(this);root.setOrientation(1);root.setFitsSystemWindows(true);
    root.setOnApplyWindowInsetsListener((v,insets)->{if(Build.VERSION.SDK_INT>=30)session.reading.keyboard(insets.isVisible(android.view.WindowInsets.Type.ime()));return v.onApplyWindowInsets(insets);});
    TextView label=new TextView(this);label.setText("正式应用内核回归 · 环境 "+(slot+1));label.setTextSize(16);root.addView(label);
    if(session.web.getParent() instanceof android.view.ViewGroup)((android.view.ViewGroup)session.web.getParent()).removeView(session.web);
    session.web.setHost(this);root.addView(session.web,new LinearLayout.LayoutParams(-1,0,1));setContentView(root);command(getIntent());
  }
  @Override protected void onNewIntent(Intent intent){super.onNewIntent(intent);setIntent(intent);command(intent);}
  synchronized void command(Intent intent){
    action=intent.getStringExtra("fixtureAction");if(action==null)return;long serial=++run;
    try{if(eventBuildIdentity==null)eventBuildIdentity=IntegrationBuildIdentity.read(Profiles.global(this));eventStore=new IntegrationEventStore(this,slot,intent.getStringExtra("eventNonce"),action,serial,eventBuildIdentity);}
    catch(Exception failure){throw new IllegalStateException("Full synthetic result transport unavailable",failure);}
    readinessObservation="read".equals(action)?new DeviceReadinessObservation(SystemClock.elapsedRealtime()):null;
    readinessForeground=null;readinessForegroundAt=0;readinessNetwork=null;
    observeReadiness(serial,"command-entered",true);
    waitReady(serial);
  }
  void waitReady(long serial){
    if(serial!=run)return;GeckoWebView web=(GeckoWebView)session.web;
    // onNewIntent arrives before onResume when bringing another task forward.
    // AndroidX publishes RESUMED in onActivityPostResumed, after Activity.onResume.
    if(!activityResumed||!processForeground()){observeReadiness(serial,"wait-lifecycle",false);session.handler.postDelayed(()->waitReady(serial),50);return;}
    if("foreignPreferences".equals(action)){event(serial,"foreignPreferences",J.obj("marker",Profiles.context(this,1).getSharedPreferences("chat",0).getString("managementMarker","")));return;}
    if(web.failed){observeReadiness(serial,"browser-failed",true);event(serial,"error",J.obj("error","Gecko startup failed"));return;}
    if(!web.ready){observeReadiness(serial,"wait-browser",false);session.handler.postDelayed(()->waitReady(serial),200);return;}
    FixtureView controlled=(FixtureView)web;
    if(!controlled.initialRouteReady){
      android.net.ConnectivityManager manager=getSystemService(android.net.ConnectivityManager.class);
      android.net.Network network=manager==null?null:manager.getActiveNetwork();android.net.NetworkCapabilities caps=network==null?null:manager.getNetworkCapabilities(network);
      String identity=network==null?"":network.toString();long now=SystemClock.elapsedRealtime();
      boolean available=caps!=null&&caps.hasCapability(android.net.NetworkCapabilities.NET_CAPABILITY_INTERNET)&&!session.offline&&identity.equals(session.networkIdentity);
      if(!available){initialRouteNetwork="";initialRouteStableSince=0;initialRouteSamples=0;}
      else if(!identity.equals(initialRouteNetwork)){initialRouteNetwork=identity;initialRouteStableSince=now;initialRouteSamples=1;}
      else initialRouteSamples++;
      observeReadinessNetwork(serial,identity,available,now);
      if(!available||initialRouteSamples<3||now-initialRouteStableSince<500){observeReadiness(serial,"wait-network",false);session.handler.postDelayed(()->waitReady(serial),100);return;}
      String expected=(slot==0?"socks":"http")+"://127.0.0.1:"+(1080+slot);
      if(session.internalNetwork()||!expected.equals(session.prefs.getString("proxy",""))||session.prefs.getBoolean("requireExternalVpn",true)){event(serial,"error",J.obj("error","Initial controlled fixture route configuration mismatch"));return;}
      // Admit this synthetic route once after the real observer has caught up.
      // Later loss/block/kill/clear behavior continues through production guards.
      session.guard.setBlocked(false);session.networkReady=true;controlled.initialRouteReady=true;
      JSONObject evidence=J.obj("actualNetwork",identity,"internet",true,"observerNetwork",session.networkIdentity,"observerOffline",session.offline,"stableMillis",now-initialRouteStableSince,"stableSamples",initialRouteSamples,"proxy",expected);
      controlled.initialRouteReporter=target->{try{evidence.put("initialTarget",target).put("startupCheckpointUri",GeckoWebView.stateUrl(web.startupState)).put("guardAllowed",session.guard.allowed()).put("networkReady",session.networkReady).put("route",web.route(target));}catch(JSONException error){throw new IllegalStateException(error);}event(serial,"initialRouteReady",evidence);};
    }
    observeReadiness(serial,"dispatch-ready",true);
    if("backgroundSettings".equals(action)){backgroundSettings(serial);return;}
    if("queuedChanges".equals(action)){queuedChanges(serial);return;}
    if("privacy".equals(action)){privacy(serial,0);return;}
    if("completion".equals(action)){completion(serial);return;}
    if("desktopImage".equals(action)){desktopImage(serial);return;}
    if("desktopOwnImage".equals(action)){desktopImage(serial,true);return;}
    if("uploadLifecycle".equals(action)){GeckoUploadLifecycleIntegration.run(this,serial);return;}
    if("localDraftPolicy".equals(action)){GeckoLocalDraftIntegration.run(this,serial);return;}
    if("pageContinuity".equals(action)){ChatPageContinuityIntegration.run(this,serial);return;}
    if("usability".equals(action)){usability(serial);return;}
    if("deleteDownloads".equals(action)){DownloadDeletionIntegration.run(this,result->{if(serial==run)event(serial,"downloadDeletion",result);});return;}
    if("reading".equals(action)){session.reading.configure(true);session.reading.choose(1);web.configure(true,session.privacy.level());web.loadUrl("http://127.0.0.1:8765/browser-reading?command="+serial);session.handler.postDelayed(()->readingResult(serial,SystemClock.elapsedRealtime()+15000),200);return;}
    if("readingZoom".equals(action)){beginReadingZoom(serial);return;}
    if("readingBounds".equals(action)||"readingBoundsProtected".equals(action)){beginReadingBounds(serial,"readingBoundsProtected".equals(action)?2:0);return;}
    if("readingBoundsGeometry".equals(action)){readingBoundsGeometry(serial,SystemClock.elapsedRealtime()+20000);return;}
    if("readingBoundsInput".equals(action)){FixtureView focus=(FixtureView)session.web;focus.nativeFocusRequests=focus.nativeFocusMeasurements=0;focus.lastFocusUrl="";focus.readingFocusScrolls=0;focus.readingFocusHadClipping=false;focus.readingFocusScrollDelta=0;session.web.evaluateJavascript("document.getElementById('composer').scrollIntoView({block:'center',behavior:'instant'})",unused->session.handler.postDelayed(()->{readingBoundsTap(serial);readingBoundsInput(serial,SystemClock.elapsedRealtime()+20000);},500));return;}
    if("readingBoundsEnd".equals(action)){session.web.current.setCompositorScrollDelegate(readingBoundsCase.priorDelegate);session.prefs.edit().putInt("privacyLevel",readingBoundsCase.privacy).commit();session.web.configure(true,readingBoundsCase.privacy);readingBoundsEnd(serial,SystemClock.elapsedRealtime()+20000);return;}
    if("readingInput".equals(action)){tapElement(serial,"composer");readingInput(serial,SystemClock.elapsedRealtime()+15000);return;}
    if("nativeSurface".equals(action)){nativeSurface(serial);return;}
    if("nativeCheckpoint".equals(action)){nativeCheckpoint(serial);return;}
    if("readingFixtureCookieCleanup".equals(action)){beginReadingFixtureCookieCleanup(serial);return;}
    if("sessionSeed".equals(action)||"sessionRead".equals(action)||"sessionLive".equals(action)||"sessionLogout".equals(action)||"killRestore".equals(action)||"resumeSaved".equals(action)){
      if("killRestore".equals(action)){
        org.mozilla.geckoview.GeckoSession stopped=web.current;stopped.close();stopped.getContentDelegate().onKill(stopped);
      }else if("resumeSaved".equals(action)){
        String target=GeckoWebView.stateUrl(web.startupState);if(!target.contains("/browser-session")){event(serial,"error",J.obj("error","private session checkpoint missing"));return;}web.loadUrl(target);
      }else if(!"sessionLive".equals(action))web.loadUrl("http://127.0.0.1:8765/browser-session?context="+(slot+1)+"&action="+action+"&command="+serial);
      sessionResult(serial,SystemClock.elapsedRealtime()+20000);return;
    }
    if("sessionCheckpoint".equals(action)){web.checkpointState();session.handler.postDelayed(()->event(serial,"checkpoint",J.obj("saved",web.states.containsKey(web.primary))),1000);return;}
    if("windows".equals(action)||"lostParent".equals(action)){windowFlow(serial);return;}
    if("earlyPaint".equals(action)||"cancelLoad".equals(action)){
      // SDK PageStart may precede the authoritative location commit callback.
      // Arm this command before loading so its first probe cannot see prior paint.
      paintCommand=serial;paintTarget="http://127.0.0.1:8765/browser-loading?command="+serial;paintSession=web.current;paintRequested=SystemClock.elapsedRealtime();paintStarted=paintVisible=paintFinished=0;paintFinishedBeforeCancel=-1;paintCommitted=paintCancelledBeforeFinish=false;
      web.loadUrl(paintTarget);session.handler.postDelayed(()->paintResult(serial),300);return;
    }
    if("closedSession".equals(action)){
      // Inject the exact SDK onKill contract (closed session), then render through the real SDK again.
      JSONObject previous=session.pending;session.pending=J.obj("kind","web","confirmed",true);
      org.mozilla.geckoview.GeckoSession stopped=web.current;stopped.close();stopped.getContentDelegate().onKill(stopped);
      String failure=session.status;session.sync();pendingFailureRetained=failure.equals(session.status)&&web.callbacks.size()==0;session.pending=previous;
      closedSessionRecovery=web.failed&&!stopped.isOpen();session.guard.setBlocked(true);web.loadUrl("http://127.0.0.1:8765/fixture");
      blockedRecoveryPreservesClosed=!stopped.isOpen();session.guard.setBlocked(false);loadFixture(serial);return;
    }
    if("switchSystem".equals(action)){web.useEngine(false);event(serial,"engineSwitch",J.obj("gecko",web.enabled));return;}
    if("switchGecko".equals(action)){web.useEngine(true);action="read";}
    if("clear".equals(action)){web.runtime.getStorageController().clearData(org.mozilla.geckoview.StorageController.ClearFlags.ALL)
      .accept(value->loadFixture(serial),error->event(serial,"error",J.obj("error","native profile clear failed")));return;}
    if("block".equals(action))session.guard.setBlocked(true);
    if("disableExtension".equals(action)){
      web.runtime.getWebExtensionController().disable(web.extension,org.mozilla.geckoview.WebExtensionController.EnableSource.USER).accept(value->{if(serial!=run)return;web.current.loadUri("http://127.0.0.1:8765/fixture?context="+(slot+1)+"&action=read");session.handler.postDelayed(()->event(serial,"bootstrapCheck",J.obj("navigationFailed",session.navigationFailed,"extensionId",value.id,"enabledAfterDisable",value.metaData.enabled,"disabledFlags",value.metaData.disabledFlags)),5000);},error->event(serial,"error",J.obj("error","disable failed")));return;
    }
    if("restoreExtension".equals(action)){restoreExtension(serial);return;}
    loadFixture(serial);
  }
  JSONObject extensionReceipt(org.mozilla.geckoview.WebExtension extension){return J.obj("id",extension.id,"version",extension.metaData.version,"enabled",extension.metaData.enabled,"disabledFlags",extension.metaData.disabledFlags);}
  void restoreExtension(long serial){
    final GeckoWebView web=(GeckoWebView)session.web;
    final org.mozilla.geckoview.WebExtensionController controller=web.runtime.getWebExtensionController();
    final org.mozilla.geckoview.WebExtension.Port previous=web.routePort;
    final String expected="browser@pocketchat.local";
    final boolean guardBefore=session.guard.allowed(),networkBefore=session.networkReady;
    // The fail-closed assertion already completed in a separate invocation.
    // USER disable survives force-stop; ensureBuiltIn does not enable an existing
    // same-version add-on. Undo only this fixture's USER disable before later tests.
    controller.ensureBuiltIn("resource://android/assets/gecko/",expected).accept(before->{
      if(serial!=run||session.web!=web)return;
      if(!expected.equals(before.id)||before.metaData.enabled||(before.metaData.disabledFlags&org.mozilla.geckoview.WebExtension.DisabledFlags.USER)==0){event(serial,"error",J.obj("error","Owned bootstrap disable was not retained","ensureBefore",extensionReceipt(before)));return;}
      controller.enable(before,org.mozilla.geckoview.WebExtensionController.EnableSource.USER).accept(enabled->{
        if(serial!=run||session.web!=web)return;
        controller.ensureBuiltIn("resource://android/assets/gecko/",expected).accept(after->{
          if(serial!=run||session.web!=web)return;
          if(!expected.equals(enabled.id)||!expected.equals(after.id)||!enabled.metaData.enabled||!after.metaData.enabled||(after.metaData.disabledFlags&org.mozilla.geckoview.WebExtension.DisabledFlags.USER)!=0){event(serial,"error",J.obj("error","Owned bootstrap extension did not re-enable","enableResult",extensionReceipt(enabled),"ensureAfter",extensionReceipt(after)));return;}
          web.extension=after;
          JSONObject result=J.obj("ensureBefore",extensionReceipt(before),"enableResult",extensionReceipt(enabled),"ensureAfter",extensionReceipt(after),"enableSource","USER","guardBefore",guardBefore,"networkReadyBefore",networkBefore);
          waitExtensionRestore(serial,web,previous,result,SystemClock.elapsedRealtime()+15000);
        },error->event(serial,"error",J.obj("error","restored extension readback failed","detail",error.toString())));
      },error->event(serial,"error",J.obj("error","bootstrap cleanup enable failed","detail",error.toString())));
    },error->event(serial,"error",J.obj("error","disabled extension readback failed","detail",error.toString())));
  }
  void waitExtensionRestore(long serial,GeckoWebView web,org.mozilla.geckoview.WebExtension.Port previous,JSONObject result,long deadline){
    if(serial!=run||session.web!=web)return;
    boolean reconnected=web.routePort!=null&&web.routePort!=previous;
    boolean protectedPolicy=web.privacyReady&&web.protectionLevel==session.privacy.level()&&web.getSettings().rfpAcknowledged;
    if(reconnected&&protectedPolicy){
      try{result.put("newNativeRoutePort",true).put("privacyReady",web.privacyReady).put("protectionLevel",web.protectionLevel).put("expectedProtectionLevel",session.privacy.level()).put("nativeProtectionAcknowledged",web.getSettings().rfpAcknowledged).put("guardAfter",session.guard.allowed()).put("networkReadyAfter",session.networkReady);}catch(JSONException error){throw new IllegalStateException(error);}
      event(serial,"bootstrapRestore",result);return;
    }
    if(SystemClock.elapsedRealtime()>deadline){event(serial,"error",J.obj("error","Restored bootstrap extension did not acknowledge native protection","newNativeRoutePort",reconnected,"privacyReady",web.privacyReady,"protectionLevel",web.protectionLevel));return;}
    session.handler.postDelayed(()->waitExtensionRestore(serial,web,previous,result,deadline),100);
  }
  void backgroundSettings(long serial){
    boolean desktop=session.privacy.wantsDesktop();session.pending=J.obj("id","synthetic-background-settings","confirmed",true);session.navigating=false;session.connecting=false;
    boolean saved=DeferredBrowserSettings.save(session,session.privacy.level(),!desktop);ChatService.begin(this);
    event(serial,"homeNeeded",J.obj("id","background-settings-"+serial));
    session.handler.postDelayed(()->{session.networkReady=false;session.guard.setBlocked(true);session.completeReply(session.pending,J.obj("url",session.web.getUrl()));session.changed();},5000);
    session.handler.postDelayed(()->event(serial,"backgroundSettings",J.obj("saved",saved,"actualBackground",!session.uiVisible&&!processForeground(),"replyFinished",session.pending==null,"automaticallyApplied",!DeferredBrowserSettings.pending(session)&&session.privacy.wantsDesktop()!=desktop&&session.privacy.desktop!=desktop)),8500);
  }
  void queuedChanges(long serial){
    session.prefs.edit().putString("managementMarker","prime-target").commit();String original=session.prefs.getString("proxy","");int level=session.privacy.level();boolean desktop=session.privacy.wantsDesktop();
    session.pending=J.obj("id","synthetic-queued-question","kind","web","confirmed",true);session.navigating=false;session.connecting=false;session.state=J.obj("busy",false);
    session.changed();boolean browserSaved=DeferredBrowserSettings.save(session,2,!desktop),livePolicyKept=session.privacy.level()==level&&session.privacy.wantsDesktop()==desktop;
    NetworkBridge.run(this,slot,"external",J.obj("proxy","","requireExternalVpn",true),NetworkChanges.hash(this),(ok,message,snapshot)->{
      boolean kept=original.equals(session.prefs.getString("proxy",""))&&NetworkChanges.pending(this).length()>0&&session.pending!=null;
      DeferredBrowserSettings.cancel(session);JSONObject job=session.pending;session.completeReply(job,J.obj("url",session.web.getUrl()));session.changed();session.state=J.obj("busy",false);session.navigating=false;
      session.handler.postDelayed(()->event(serial,"queuedChanges",J.obj("savedWhileReplying",ok,"oldRouteKept",kept,"browserSavedWithoutApplying",browserSaved&&livePolicyKept,"replyCleared",session.pending==null&&!session.prefs.contains("pending")&&!ProfileCatalog.get(this).item(slot).optBoolean("waiting"),"appliedWhenIdle",session.prefs.getString("proxy","x").isEmpty()&&NetworkChanges.pending(this).length()==0,"vpnGuardBlocksWithoutVpn",session.guard.requiresVpn()&&!session.guard.allowed(),"message",message)),3500);
    });
  }
  int priorPrivacy;
  void privacy(long serial,int stage){
    if(stage==0){priorPrivacy=session.privacy.level();session.prefs.edit().putInt("privacyLevel",2).commit();session.web.configure(session.privacy.desktop,2);session.handler.postDelayed(()->privacy(serial,1),1000);return;}
    if(!session.web.privacyReady){if(stage>15){event(serial,"error",J.obj("error","privacy acknowledgment timeout"));return;}session.handler.postDelayed(()->privacy(serial,stage+1),500);return;}
    boolean enabled=session.web.fingerprintingProtected;session.prefs.edit().putInt("privacyLevel",priorPrivacy).commit();session.web.configure(session.privacy.desktop,priorPrivacy);session.handler.postDelayed(()->event(serial,"privacy",J.obj("nativeFingerprintingEnabled",enabled,"restoredLevel",priorPrivacy)),1000);
  }
  void completion(long serial){
    String html="<main><article data-turn='user'><div data-message-author-role='user' data-message-id='synthetic-user'>guest prompt</div></article><section><div data-message-author-role='assistant' data-message-id='synthetic-answer'><div class='markdown'>guest complete reply</div></div><button aria-label='Copy message'>Copy</button></section><textarea id='prompt-textarea'></textarea></main>";
    // Only this test copy accepts the strictly bounded loopback fixture. The
    // production driver continues to require the real HTTPS ChatGPT origin.
    String code=session.driver
      .replace("location.protocol !== 'https:' || location.hostname !== 'chatgpt.com'", "location.protocol !== 'http:' || location.hostname !== '127.0.0.1' || location.port !== '8765'")
      .replace("__ACTION__",JSONObject.quote("poll"))
      .replace("__ARG__",J.obj("userKey","id:synthetic-user","prompt","guest prompt","export",true).toString());
    session.web.evaluateJavascript("document.body.innerHTML="+JSONObject.quote(html),unused->{
      session.web.evaluateJavascript(code,raw->{
        JSONObject poll=J.parse(raw);
        boolean current=poll.optBoolean("terminal")&&poll.optBoolean("submitted")&&!poll.optBoolean("busy");
        String previous="document.querySelector('section button').remove();document.querySelector('main').insertAdjacentHTML('afterbegin','<section><div data-message-author-role=\"assistant\" data-message-id=\"prior\">old</div><button aria-label=\"Copy message\">Copy</button></section>');";
        session.web.evaluateJavascript(previous,v->{
          session.web.evaluateJavascript(code,later->{
            JSONObject old=J.parse(later);
            event(serial,"completion",J.obj("guestActionsRecognized",current,"priorActionsCannotComplete",!old.optBoolean("terminal"),"nestedMessageIdRecognized","id:synthetic-user".equals(poll.optString("userKey")),"reply",poll.optString("markdown"),"poll",poll));
          });
        });
      });
    });
  }
  // Only the origin is adapted for the loopback fixture. The production chooser,
  // pending guard, SAF result and Gecko file preparation all run unchanged.
  void desktopImage(long serial){desktopImage(serial,false);}
  void desktopImage(long serial,boolean ownProvider){
    session.reading.configure(true);session.web.configure(true,session.privacy.level());
    final JSONObject held=J.obj("kind","web","confirmed",true);session.pending=held;
    FixtureView view=(FixtureView)session.web;final boolean[] chooser={false},mime={false};
    MainActivity host=new MainActivity(){
      @Override public android.view.Window getWindow(){return GeckoIntegrationTestActivity.this.getWindow();}
      @Override void status(String message){if(message.contains("失败"))event(serial,"error",J.obj("error",message));}
      @Override public void startActivityForResult(Intent intent,int request){
        chooser[0]=request==74&&Intent.ACTION_OPEN_DOCUMENT.equals(intent.getAction());mime[0]="image/*".equals(intent.getType())&&intent.getBooleanExtra(Intent.EXTRA_ALLOW_MULTIPLE,false);
        session.handler.post(()->{view.chooserOrigin=true;try{attachments.result(Activity.RESULT_OK,new Intent().setData(android.net.Uri.parse(ownProvider?"content://local.pocketchat.test.upload/image":"content://synthetic.pocket.upload/image")));}finally{view.chooserOrigin=false;}});
      }
    };
    host.attachBaseContext(this);host.session=session;host.remote=view;host.prefs=session.prefs;host.pageMode=true;host.status=new TextView(host);host.loading=new LoadingUi(host);host.attachments=new Attachments(host);
    android.webkit.WebChromeClient production=host.attachments.chrome();
    view.setWebChromeClient(new android.webkit.WebChromeClient(){@Override public boolean onShowFileChooser(WebView web,android.webkit.ValueCallback<android.net.Uri[]> callback,FileChooserParams params){view.chooserOrigin=true;try{return production.onShowFileChooser(web,callback,params);}finally{view.chooserOrigin=false;}}});
    final String target="http://127.0.0.1:8765/browser-image?command="+serial+"&nonce="+eventStore.nonce;
    view.loadUrl(target);
    session.handler.postDelayed(()->desktopImageReady(serial,SystemClock.elapsedRealtime()+25000,host,held,chooser,mime,false,target),200);
  }
  void desktopImageReady(long serial,long deadline,MainActivity host,JSONObject held,boolean[] chooser,boolean[] mime,boolean tapped,String target){
    if(serial!=run)return;
    // Both image cases share a pathname. A retained previous document can
    // still contain its successful upload while the next navigation starts.
    // Accept readiness and results only from this invocation's exact URL.
    session.web.evaluateJavascript("(()=>({ready:location.href==="+JSONObject.quote(target)+"&&!!document.getElementById('upload'),value:document.getElementById('upload-result')?.textContent||''}))()",raw->{
      JSONObject current=J.parse(raw);String value=current.optString("value");boolean touched=tapped;
      if(!touched&&current.optBoolean("ready")&&session.web.hasVisibleDocument()&&!session.navigating){tapElement(serial,"upload");touched=true;}
      final boolean next=touched;
      if(current.optBoolean("ready")&&value.startsWith("ok:")){boolean retained=session.pending==held;session.pending=null;host.attachments.destroy();event(serial,"desktopImage",J.obj("productionChooserOpened",chooser[0],"imageMimeAndMultiple",mime[0],"pendingPreserved",retained,"noPhantomUpload",session.attachments.length()==0,"upload",value,"desktop",((GeckoWebView)session.web).desktop));return;}
      if(SystemClock.elapsedRealtime()>deadline){session.pending=null;host.attachments.destroy();event(serial,"error",J.obj("error","desktop image chooser/upload failed","result",raw,"chooser",chooser[0]));return;}
      session.handler.postDelayed(()->desktopImageReady(serial,deadline,host,held,chooser,mime,next,target),100);
    });
  }
  void usability(long serial){
    session.reading.configure(false);session.web.configure(false,session.privacy.level());
    session.web.setWebChromeClient(new android.webkit.WebChromeClient(){
      @Override public boolean onShowFileChooser(WebView unused,android.webkit.ValueCallback<android.net.Uri[]> callback,FileChooserParams params){callback.onReceiveValue(new android.net.Uri[]{android.net.Uri.parse("content://local.pocketchat.test.upload/document")});return true;}
    });
    session.web.loadUrl("http://127.0.0.1:8765/browser-usability?command="+serial);
    usabilityReady(serial,SystemClock.elapsedRealtime()+20000);
  }
  void usabilityReady(long serial,long deadline){
    if(serial!=run)return;
    if(!session.web.hasVisibleDocument()){if(SystemClock.elapsedRealtime()>deadline){event(serial,"error",J.obj("error","mobile document remained blank"));return;}session.handler.postDelayed(()->usabilityReady(serial,deadline),100);return;}
    session.web.evaluateJavascript("navigator.userAgent",raw->{if(!raw.contains("Android")||!raw.contains("Firefox")){event(serial,"error",J.obj("error","mobile identity missing","ua",raw));return;}
      if(!session.audit.start(false,()->{JSONObject report=session.audit.report;session.web.evaluateJavascript("(()=>({url:location.href,body:!!document.getElementById('upload'),visible:document.body.innerText.length>0}))()",value->{JSONObject current=J.parse(value);if(!current.optBoolean("body")||!current.optBoolean("visible")||!current.optString("url").contains("browser-usability")||!report.optBoolean("fresh")||!report.optJSONObject("signals").optJSONObject("parent").optString("ua").contains("Firefox")){event(serial,"error",J.obj("error","current Firefox audit failed","report",report,"current",current));return;}tapElement(serial,"upload");usabilityUpload(serial,deadline);});}))event(serial,"error",J.obj("error",session.audit.lastError));
    });
  }
  void usabilityUpload(long serial,long deadline){
    if(serial!=run)return;
    session.web.evaluateJavascript("document.getElementById('upload-result')?.textContent",raw->{String value=raw==null?"":raw;try{value=new org.json.JSONTokener(raw).nextValue().toString();}catch(Exception ignored){}final String selectedValue=value;if(!"sample.txt:synthetic-upload".equals(value)){if(SystemClock.elapsedRealtime()>deadline){event(serial,"error",J.obj("error","SAF text upload failed","result",raw));return;}session.handler.postDelayed(()->usabilityUpload(serial,deadline),100);return;}
      final long downloadEpoch=session.navigationEpoch;final String downloadDocument=session.web.getUrl();final boolean[] csvReceived={false};session.web.responseDownload=response->{new Thread(()->{try(java.io.InputStream in=response.body){String body=new String(in.readAllBytes(),java.nio.charset.StandardCharsets.UTF_8);session.handler.post(()->{if(!"name,value\nsynthetic,42\n".equals(body)){event(serial,"error",J.obj("error","native CSV body mismatch","body",body));return;}if(!csvReceived[0]){csvReceived[0]=true;tapElement(serial,"blob");return;}if(session.navigationEpoch!=downloadEpoch||!downloadDocument.equals(session.web.getUrl())||session.navigationFailed){event(serial,"error",J.obj("error","download replaced the current document"));return;}event(serial,"usability",J.obj("documentPreserved",true,"mobileVisible",session.web.hasVisibleDocument(),"upload",selectedValue,"csv",body,"blob",body,"audit",session.audit.report));});}catch(Exception error){event(serial,"error",J.obj("error","native download failed: "+error.getMessage()));}},"fixture-download").start();};
      tapElement(serial,"csv");
    });
  }
  void loadFixture(long serial){
    if(serial!=run)return;GeckoWebView web=(GeckoWebView)session.web;
    String target="http://127.0.0.1:8765/fixture?context="+(slot+1)+"&action="+action+"&command="+serial;
    if("popup".equals(action))target="http://127.0.0.1:8765/popup-main";
    web.loadUrl(target);session.handler.postDelayed(()->poll(serial),500);
  }
  void poll(long serial){
    if(serial!=run)return;
    if("block".equals(action)){
      String target="http://127.0.0.1:8765/guard-blocked?context="+(slot+1)+"&command="+serial;
      session.web.evaluateJavascript("(()=>{window.__guardProbe='pending';const c=new AbortController();setTimeout(()=>c.abort(),4000);fetch("+JSONObject.quote(target)+",{cache:'no-store',signal:c.signal}).then(()=>window.__guardProbe='leaked',()=>window.__guardProbe='blocked');return null})()",unused->blockedProbe(serial,SystemClock.elapsedRealtime()+6000));return;
    }
    session.web.evaluateJavascript("(()=>{const text=document.getElementById('result')?.textContent;if(!text||text==='测试中…')return null;try{return JSON.parse(text)}catch{return null}})()",raw->{
      if(serial!=run)return;JSONObject result=J.parse(raw);
      if(result.length()>0&&action.equals(result.optString("action"))&&String.valueOf(slot+1).equals(result.optString("context"))&&String.valueOf(serial).equals(result.optString("command"))){((GeckoWebView)session.web).readCookies("http://127.0.0.1:8765/fixture",value->{
        if(serial!=run)return;
        try{result.put("nativeCookies",value==null?JSONObject.NULL:value);if("legacyEnginePreference".equals(action))result.put("legacyEngineCompatibility",legacyEngineCompatibility());if("closedSession".equals(action)){result.put("closedSessionRecovery",closedSessionRecovery&&((GeckoWebView)session.web).current.isOpen()&&!((GeckoWebView)session.web).failed);result.put("blockedRecoveryPreservesClosed",blockedRecoveryPreservesClosed);result.put("pendingFailureRetained",pendingFailureRetained);result.put("recoveryMethod","injected SDK onKill contract; real close/open/render");}}catch(Exception error){event(serial,"error",J.obj("error",error.toString()));return;}event(serial,"fixture",result);
      });return;}
      if(session.navigationFailed)event(serial,"loadError",J.obj("failed",true,"url",session.web.getUrl(),"error",session.pageError,"guard",session.guard.allowed()));
      else session.handler.postDelayed(()->poll(serial),300);
    });
  }
  JSONObject legacyEngineCompatibility(){
    GeckoWebView web=session.web;org.mozilla.geckoview.GeckoSession sdk=web.current;
    String url=web.getUrl(),route=web.route(url).toString();boolean refused=false;
    try{web.useEngine(false);}catch(IllegalStateException expected){refused=true;}
    return J.obj("actualGecko",web.enabled&&web.runtime!=null&&sdk!=null&&sdk.isOpen()&&web.surface.getSession()==sdk,
      "oldPreferencesPreserved","system".equals(session.prefs.getString("browserEngine",""))&&!session.prefs.getBoolean("pageMode",true),
      "systemEngineRefused",refused,"sameSdkSession",web.current==sdk,"sameSurface",session.web==web,
      "sameDocument",java.util.Objects.equals(url,web.getUrl()),"sameProtectedRoute",route.equals(web.route(url).toString()),
      "systemWebViews",CompactChromeIntegrationActivity.systemWebViews(getWindow().getDecorView()));
  }
  void blockedProbe(long serial,long deadline){
    if(serial!=run)return;session.web.evaluateJavascript("window.__guardProbe||null",raw->{
      if(serial!=run)return;
      if("\"blocked\"".equals(raw)||"\"leaked\"".equals(raw)){event(serial,"blocked",J.obj("guard",session.guard.allowed(),"route",session.web.route("http://127.0.0.1:8765/fixture"),"newFetchBlocked","\"blocked\"".equals(raw)));return;}
      if(SystemClock.elapsedRealtime()>deadline){event(serial,"error",J.obj("error","blocked fetch did not finish"));return;}session.handler.postDelayed(()->blockedProbe(serial,deadline),100);
    });
  }
  void windowFlow(long serial){
    GeckoWebView web=session.web;web.loadUrl(windowUrl("one",serial));
    waitWindow(serial,"one",SystemClock.elapsedRealtime()+15000,()->{
      org.mozilla.geckoview.GeckoSession parent=web.current;web.loadUrl(windowUrl("two",serial));
      waitWindow(serial,"two",SystemClock.elapsedRealtime()+15000,()->{
        if(!web.canBack){event(serial,"error",J.obj("error","parent history missing before popup"));return;}
        tapElement(serial,"popup");
        waitWindow(serial,"three",SystemClock.elapsedRealtime()+15000,()->{
          if(web.current==parent||web.popups.size()!=1){event(serial,"error",J.obj("error","real popup did not become active"));return;}
          if("lostParent".equals(action)){parent.close();parent.getContentDelegate().onKill(parent);web.closePopup();
            if(!web.failed||web.current!=parent){event(serial,"error",J.obj("error","closed parent state was not restored"));return;}
            web.loadUrl(windowUrl("two",serial));
            waitWindow(serial,"two",SystemClock.elapsedRealtime()+15000,()->event(serial,"windowFlow",J.obj("lostParentRecovery",!web.failed&&parent.isOpen(),"popups",web.popups.size(),"url",web.getUrl())));return;
          }
          web.loadUrl(windowUrl("four",serial));
          waitWindow(serial,"four",SystemClock.elapsedRealtime()+15000,()->{
            if(!web.canBack){event(serial,"error",J.obj("error","popup history missing"));return;}
            web.goBack();waitWindow(serial,"three",SystemClock.elapsedRealtime()+15000,()->{
              web.evaluateJavascript("window.close();null",null);
              waitWindow(serial,"two",SystemClock.elapsedRealtime()+15000,()->{
                if(web.current!=parent||!web.canBack||!web.popups.isEmpty()){event(serial,"error",J.obj("error","parent history was lost after closing popup"));return;}
                web.goBack();waitWindow(serial,"one",SystemClock.elapsedRealtime()+15000,()->event(serial,"windowFlow",J.obj("realPopup",true,"parentHistoryRestored",true,"popups",web.popups.size(),"url",web.getUrl(),"pendingCallbacks",web.callbacks.size())));
              });
            });
          });
        });
      });
    });
  }
  String windowUrl(String step,long serial){return "http://127.0.0.1:8765/browser-window?step="+step+"&command="+serial;}
  void tapElement(long serial,String id){
    session.web.evaluateJavascript("(()=>{const r=document.getElementById("+JSONObject.quote(id)+").getBoundingClientRect(),v=visualViewport;return {x:r.left+r.width/2,y:r.top+r.height/2,pixels:devicePixelRatio*(v?.scale||1),left:v?.offsetLeft||0,top:v?.offsetTop||0}})()",raw->{
      if(serial!=run)return;JSONObject rect=J.parse(raw);if(!rect.has("x")){event(serial,"error",J.obj("error","tap element not available"));return;}
      // The SDK compositor matrix can still describe the previous document at
      // first paint. Use this document's viewport and the actual Android origin.
      int[] origin=new int[2];session.web.surface.getLocationOnScreen(origin);double pixels=rect.optDouble("pixels")*session.web.readingLayout;
      float[] point={(float)(origin[0]+(rect.optDouble("x")-rect.optDouble("left"))*pixels),(float)(origin[1]+(rect.optDouble("y")-rect.optDouble("top"))*pixels)};
      event(serial,"tapNeeded",J.obj("id",id+"-"+serial,"x",Math.round(point[0]),"y",Math.round(point[1]),"shown",session.web.isShown(),"width",session.web.getWidth(),"height",session.web.getHeight(),"scale",session.web.getScale(),"paused",session.browserPaused));
    });
  }
  void waitWindow(long serial,String step,long deadline,Runnable done){
    if(serial!=run)return;
    session.web.evaluateJavascript("document.getElementById('window-step')?.textContent||null",raw->{
      if(serial!=run)return;
      if(JSONObject.quote(step).equals(raw)&&session.web.getUrl().contains("step="+step)&&session.web.painted.contains(session.web.current)){done.run();return;}
      if(SystemClock.elapsedRealtime()>deadline){event(serial,"error",J.obj("error","window flow timed out at "+step,"url",session.web.getUrl(),"failed",session.web.failed,"painted",session.web.painted.contains(session.web.current),"paused",session.browserPaused,"shown",session.web.isShown()));return;}
      session.handler.postDelayed(()->waitWindow(serial,step,deadline,done),150);
    });
  }
  boolean paintOwned(long serial){return serial==run&&serial==paintCommand&&paintSession!=null&&paintSession==session.web.current&&paintSession.isOpen();}
  boolean paintCallback(String target){return paintOwned(paintCommand)&&paintTarget.equals(target)&&paintTarget.equals(session.web.getUrl())&&paintTarget.equals(session.web.locations.get(paintSession));}
  boolean paintCurrent(long serial){return paintOwned(serial)&&paintCommitted&&paintCallback(paintTarget);}
  JSONObject paintEvidence(JSONObject value){try{return value.put("paintCase",J.obj("schema",1,"serial",paintCommand,"target",paintTarget,"requested",paintRequested,"nativeSession",System.identityHashCode(paintSession),"currentNativeSession",System.identityHashCode(session.web.current),"currentUrl",session.web.getUrl(),"committedTarget",session.web.locations.get(paintSession),"committed",paintCommitted,"currentCase",paintCurrent(paintCommand),"started",paintStarted,"visible",paintVisible,"finished",paintFinished));}catch(JSONException error){throw new IllegalStateException(error);}}
  void paintError(long serial,String message){event(serial,"error",paintEvidence(J.obj("error",message)));}
  void paintResult(long serial){
    if(serial!=run)return;
    if(!paintOwned(serial)){paintError(serial,"paint fixture session ownership changed");return;}
    if(!paintCurrent(serial)){
      if(paintCommitted){paintError(serial,"paint fixture document ownership changed");return;}
      if(SystemClock.elapsedRealtime()-paintRequested>15000){paintError(serial,"paint fixture document did not commit");return;}
      session.handler.postDelayed(()->paintResult(serial),200);return;
    }
    if("cancelLoad".equals(action)&&paintVisible>0&&paintFinished==0){
      session.web.evaluateJavascript("(()=>({command:new URL(location.href).searchParams.get('command'),heading:document.querySelector('h1')?.textContent}))()",raw->{
        if(serial!=run)return;if(!paintCurrent(serial)){paintError(serial,"paint fixture document ownership changed");return;}JSONObject value=J.parse(raw);
        if(!String.valueOf(serial).equals(value.optString("command"))||!"Visible before slow resource".equals(value.optString("heading"))){session.handler.postDelayed(()->paintResult(serial),200);return;}
        if(paintFinished>0){paintError(serial,"cancel fixture completed before its document was ready");return;}
        paintFinishedBeforeCancel=paintFinished;paintCancelledBeforeFinish=paintFinishedBeforeCancel==0;session.web.stopLoading();session.handler.postDelayed(()->{
          if(serial!=run)return;if(!paintCurrent(serial)){paintError(serial,"paint fixture document ownership changed");return;}
          session.web.evaluateJavascript("document.querySelector('h1')?.textContent||null",result->{if(serial!=run)return;if(!paintCurrent(serial)){paintError(serial,"paint fixture document ownership changed");return;}event(serial,"cancelledLoad",paintEvidence(J.obj("reportedFailure",session.navigationFailed,"pageError",session.pageError,"visibleDocumentRetained",JSONObject.quote("Visible before slow resource").equals(result),"documentReadyBeforeStop",true,"cancelledBeforeFinish",paintCancelledBeforeFinish,"finishedBeforeCancel",paintFinishedBeforeCancel,"result",result)));});
        },400);
      });return;
    }
    if("cancelLoad".equals(action)&&paintFinished>0){paintError(serial,"cancel fixture completed before its document was ready");return;}
    if(paintFinished>0){event(serial,"paint",paintEvidence(J.obj("started",paintStarted,"visible",paintVisible,"finished",paintFinished,"firstPaintBeforeComplete",paintVisible>0&&paintVisible>=paintStarted&&paintFinished-paintVisible>500)));return;}
    if(paintStarted>0&&SystemClock.elapsedRealtime()-paintStarted>15000){paintError(serial,"slow-resource fixture did not complete");return;}
    session.handler.postDelayed(()->paintResult(serial),200);
  }
  void readingResult(long serial,long deadline){
    if(serial!=run)return;
    session.web.evaluateJavascript("(()=>{if(!document.getElementById('composer'))return null;const box=document.getElementById('composer').getBoundingClientRect();return {command:new URL(location.href).searchParams.get('command'),viewport:document.documentElement.clientWidth,density:devicePixelRatio,scale:visualViewport.scale,sidebarHidden:getComputedStyle(document.getElementById('sidebar')).display==='none',composerWidth:box.width,userAgent:navigator.userAgent,draft:document.getElementById('composer').value}})()",raw->{
      if(serial!=run)return;JSONObject result=J.parse(raw);
      // Page DPR is an observable identity value, not the compositor's
      // CSS-to-surface transform. It can be rounded or privacy-protected.
      // Assert physical fit against the real transform, as reading bounds do.
      float nativeScale=session.web.getScale();
      boolean measured=session.web.readingScaleMeasured();
      try{result.put("nativeScale",nativeScale).put("nativeWidth",session.web.getWidth()).put("compositorMeasured",measured).put("painted",session.web.painted.contains(session.web.current)).put("url",session.web.getUrl()).put("requestedCommand",serial);}catch(JSONException error){throw new IllegalStateException(error);}
      if(String.valueOf(serial).equals(result.optString("command"))&&result.optInt("viewport")>0&&measured&&Float.isFinite(nativeScale)&&nativeScale>0&&Math.abs(result.optDouble("viewport")*nativeScale-session.web.getWidth())<5&&session.web.painted.contains(session.web.current)){
        try{result.put("nativeWidth",session.web.getWidth());result.put("mobileViewport",session.web.current.getSettings().getViewportMode()==org.mozilla.geckoview.GeckoSessionSettings.VIEWPORT_MODE_MOBILE);result.put("desktopIdentity",session.web.current.getSettings().getUserAgentMode()==org.mozilla.geckoview.GeckoSessionSettings.USER_AGENT_MODE_DESKTOP);}catch(Exception ignored){}
        event(serial,"reading",result);return;
      }
      if(SystemClock.elapsedRealtime()>deadline){event(serial,"error",J.obj("error","responsive fixture did not reach its requested document and physical viewport","measurement",result,"paused",session.browserPaused,"shown",session.web.isShown()));return;}
      session.handler.postDelayed(()->readingResult(serial,deadline),200);
    });
  }
  void sessionResult(long serial,long deadline){
    if(serial!=run)return;
    session.web.evaluateJavascript("(()=>{const e=document.getElementById('session-result');if(!e)return null;return {token:e.textContent,draft:document.getElementById('session-draft').value,history:history.length,action:new URL(location.href).searchParams.get('action'),command:new URL(location.href).searchParams.get('command')}})()",raw->{
      if(serial!=run)return;JSONObject result=J.parse(raw);
      boolean requested="sessionSeed".equals(action)||"sessionRead".equals(action)||"sessionLogout".equals(action);boolean sameRequest=!requested||action.equals(result.optString("action"))&&String.valueOf(serial).equals(result.optString("command"));
      if(result.has("token")&&sameRequest&&!session.web.failed&&session.web.painted.contains(session.web.current)){
        // First paint can precede the SDK's asynchronous form restoration.
        if(("killRestore".equals(action)||"resumeSaved".equals(action))&&!result.optString("draft").equals("session-draft-"+(slot+1))){
          if(SystemClock.elapsedRealtime()>deadline){org.mozilla.geckoview.GeckoSession.SessionState saved=session.web.states.get(session.web.primary);event(serial,"error",J.obj("error","SDK form restoration did not complete","measurement",result,"checkpointHasDraft",saved!=null&&saved.toString().contains("session-draft-"+(slot+1))));return;}
          session.handler.postDelayed(()->sessionResult(serial,deadline),150);return;
        }
        if("sessionSeed".equals(action)){
          session.web.evaluateJavascript("(()=>{const e=document.getElementById('session-draft');e.value='session-draft-"+(slot+1)+"';e.dispatchEvent(new Event('input',{bubbles:true}));return e.value})()",value->{session.web.checkpointState();session.handler.postDelayed(()->event(serial,"session",J.obj("token",result.optString("token"),"draft","session-draft-"+(slot+1),"checkpoint",session.web.states.containsKey(session.web.primary))),1000);});return;
        }
        event(serial,"session",J.obj("token",result.optString("token"),"draft",result.optString("draft"),"history",result.optInt("history"),"automaticRecovery",!session.web.failed&&session.web.current.isOpen(),"profileForeground",processForeground()));return;
      }
      if(SystemClock.elapsedRealtime()>deadline){event(serial,"error",J.obj("error","session fixture did not recover","failed",session.web.failed,"url",session.web.getUrl()));return;}
      session.handler.postDelayed(()->sessionResult(serial,deadline),150);
    });
  }
  boolean processForeground(){try{
    Object owner=Class.forName("androidx.lifecycle.ProcessLifecycleOwner").getMethod("get").invoke(null);
    Object lifecycle=owner.getClass().getMethod("getLifecycle").invoke(owner);
    return observeProcessForeground("RESUMED".equals(lifecycle.getClass().getMethod("getCurrentState").invoke(lifecycle).toString()));
  }catch(Exception ignored){return observeProcessForeground(false);}}
  boolean observeProcessForeground(boolean observed){
    if(readinessObservation!=null){readinessForeground=observed;readinessForegroundAt=SystemClock.elapsedRealtime();}
    return observed;
  }
  void observeReadinessNetwork(long serial,String actual,boolean available,long now){
    if(readinessObservation==null||serial!=run)return;
    readinessNetwork=J.obj("actualNetwork",actual,"observerNetwork",session.networkIdentity,"observerOffline",session.offline,
        "available",available,"stableSamples",initialRouteSamples,"stableMillis",initialRouteStableSince==0?0:now-initialRouteStableSince);
  }
  void observeReadiness(long serial,String stage,boolean terminal){
    DeviceReadinessObservation budget=readinessObservation;
    if(budget==null||serial!=run||session==null||eventStore==null||eventStore.command!=serial)return;
    long now=SystemClock.elapsedRealtime();if(!budget.sample(now,terminal))return;
    GeckoWebView web=(GeckoWebView)session.web;
    JSONObject gates=J.obj("activityResumed",activityResumed,"processForeground",readinessForeground==null?JSONObject.NULL:readinessForeground,
        "enabled",web.enabled,"destroyed",web.destroyed,"failed",web.failed,"ready",web.ready,"runtimePresent",web.runtime!=null,
        "extensionPresent",web.extension!=null,"checkpointReady",web.checkpointReady,"checkpointRequested",web.checkpointRequested,
        "identityPrepared",web.identityPrepared,"routePrepared",web.routePrepared,"privacyReady",web.privacyReady,"routePortPresent",web.routePort!=null,
        "policyAcknowledged",web.metadata.policyAcknowledged,"rfpAcknowledged",web.metadata.rfpAcknowledged,
        "requestedProtection",web.requestedProtection,"protectionLevel",web.protectionLevel,"protectionRequest",web.protectionRequest,
        "primaryPresent",web.primary!=null,"currentPresent",web.current!=null,"ownerDeleted",session.deleted,
        "networkReady",session.networkReady,"offline",session.offline,"guardBlocked",session.guard.blocked,
        "initialRouteReady",((FixtureView)web).initialRouteReady,"observerNetwork",session.networkIdentity);
    JSONObject surface=J.obj("present",web.surface!=null,"attached",web.surface!=null&&web.surface.isAttachedToWindow(),
        "width",web.surface==null?0:web.surface.getWidth(),"height",web.surface==null?0:web.surface.getHeight(),
        "webAttached",web.isAttachedToWindow(),"webWidth",web.getWidth(),"webHeight",web.getHeight());
    // Do not include increasing elapsed/sample counters in the change key.
    String key=stage+gates.toString()+surface.toString()+(readinessNetwork==null?"":readinessNetwork.optString("actualNetwork")+readinessNetwork.optBoolean("available"));
    if(!budget.emit(now,key,terminal))return;
    publishReadiness(serial,J.obj("schema",1,"diagnosticOnly",true,"acceptance",false,"stage",stage,
        "elapsedMillis",now-budget.started,"observation",budget.emitted,"maxObservations",DeviceReadinessObservation.LIMIT,"capReached",budget.emitted==DeviceReadinessObservation.LIMIT,
        "pid",android.os.Process.myPid(),"ownerSlot",slot,"displayEnvironment",slot+1,"environmentId",session.environmentId,"environmentGeneration",session.environmentGeneration,
        "run",run,"eventStoreCommand",eventStore.command,"foregroundObservedAt",readinessForegroundAt,
        "gates",gates,"surface",surface,"networkObservation",readinessNetwork==null?JSONObject.NULL:readinessNetwork,
        "scope","Read-only cached synthetic read-startup observation; no JS, reload, reconnect, new polling or admission"));
  }
  void publishReadiness(long serial,JSONObject observed){
    // Independent diagnostic channel: never consume a business event sequence.
    if(serial!=run||eventStore==null||eventStore.command!=serial)return;
    JSONObject envelope=J.obj("schema",1,"kind","readinessObservation","diagnosticOnly",true,"acceptance",false,
        "sourceCommit",eventBuildIdentity.optString("sourceCommit"),"sourceTree",eventBuildIdentity.optString("sourceTree"),
        "apkSha256",eventBuildIdentity.optString("apkSha256"),"buildStampSha256",eventBuildIdentity.optString("buildStampSha256"),
        "runNonce",eventStore.nonce,"fixtureAction",eventStore.action,"processSlot",eventStore.slot,"command",serial,
        "businessSequence",eventStore.sequence,"observedAtElapsedRealtime",SystemClock.elapsedRealtime(),"observation",observed);
    String raw=envelope.toString();
    if(raw.getBytes(java.nio.charset.StandardCharsets.UTF_8).length>3500){
      try{envelope.remove("observation");envelope.put("diagnosticError","snapshot exceeded3500byte bound");}catch(JSONException ignored){}
      raw=envelope.toString();
    }
    Log.i("PocketReadiness",raw);
  }
  void readingZoom(long serial,int step,JSONArray results,long deadline){
    if(serial!=run)return;float[] choices={.8f,.6f,1.3f,.8f};
    if(step==choices.length){event(serial,"readingZoom",J.obj("checks",results,"readiness",readingZoomReadiness));return;}
    float choice=choices[step];readingZoomLast="";session.reading.choose(choice);waitReadingZoom(serial,step,results,deadline,choice);
  }
  void beginReadingZoom(long serial){
    java.util.Arrays.fill(readingZoomSamples,0);readingZoomLast="";readingZoomLastSample=0;readingZoomReadiness=null;
    // A foreground reading surface must finish the emulator's taskbar/inset
    // transition before the first actual choice. Each choice still has its
    // original 20-second deadline and exact visual-scale assertion below.
    if(Build.VERSION.SDK_INT>=30){android.view.WindowInsetsController bars=getWindow().getInsetsController();if(bars!=null){bars.setSystemBarsBehavior(android.view.WindowInsetsController.BEHAVIOR_DEFAULT);bars.show(android.view.WindowInsets.Type.systemBars());}}
    awaitReadingZoomReady(serial,new NativeGeometryReadiness());
  }
  void awaitReadingZoomReady(long serial,NativeGeometryReadiness readiness){
    if(serial!=run)return;FixtureView web=(FixtureView)session.web;NativeGeometry geometry=NativeGeometry.read(web);long now=SystemClock.elapsedRealtime();readiness.totalFrames++;
    boolean ready=activityResumed&&!session.browserPaused&&web.isShown()&&geometry!=null&&geometry.focused&&!geometry.imeVisible&&geometry.normalBarsReady()&&geometry.attached==web.current&&web.current.isOpen()&&geometry.webWidth>0&&geometry.webHeight>0;
    boolean unchanged=readiness.previous!=null&&readiness.previous.same(geometry);
    if(!unchanged&&readiness.transitions.length()<16){JSONObject transition=J.obj("elapsedMs",now-readiness.started,"geometry",geometry==null?JSONObject.NULL:geometry.json());readiness.transitions.put(transition);event(serial,"readingZoomGeometry",transition);}
    if(!ready||!unchanged){readiness.stableSince=now;readiness.stableFrames=ready?1:0;}else readiness.stableFrames++;
    readiness.previous=geometry;
    if(ready&&readiness.stableFrames>=8&&now-readiness.stableSince>=1000){readingZoomReadiness=J.obj("stableMillis",now-readiness.stableSince,"stableFrames",readiness.stableFrames,"activityResumed",activityResumed,"browserPaused",session.browserPaused);event(serial,"readingZoomReadiness",J.obj("stableMillis",now-readiness.stableSince,"stableFrames",readiness.stableFrames,"activityResumed",activityResumed,"browserPaused",session.browserPaused,"geometry",geometry.json()));readingZoom(serial,0,new JSONArray(),now+20000);return;}
    if(now>readiness.deadline){event(serial,"error",J.obj("error","reading zoom foreground/layout did not settle","activityResumed",activityResumed,"browserPaused",session.browserPaused,"geometry",geometry==null?JSONObject.NULL:geometry.json()));return;}
    web.postOnAnimation(()->awaitReadingZoomReady(serial,readiness));
  }
  JSONObject readingZoomSample(int step,float choice,JSONObject measurement){
    GeckoWebView web=session.web;BrowserReading reading=session.reading;
    return J.obj("step",step,"uptimeMs",SystemClock.uptimeMillis(),"wallMs",System.currentTimeMillis(),"choice",choice,"layout",web.readingLayout,"measurement",measurement,"nativeScale",web.getScale(),"rawPageScale",web.pageScales.getOrDefault(web.current,0f),"readingWidth",reading.width,"viewportWidth",reading.viewportWidth,"restoreAttempts",reading.restoreAttempts,"zoomActive",web.zoomTarget!=null,"zoomEpoch",web.zoomEpoch,"activityResumed",activityResumed,"browserPaused",session.browserPaused,"webShown",web.isShown(),"windowFocused",hasWindowFocus(),"sessionOpen",web.current!=null&&web.current.isOpen(),"webWidth",web.getWidth(),"webHeight",web.getHeight(),"surfaceWidth",web.surface==null?0:web.surface.getWidth(),"surfaceHeight",web.surface==null?0:web.surface.getHeight());
  }
  void readingZoomSample(long serial,int step,float choice,JSONObject measurement,boolean force){
    JSONObject sample=readingZoomSample(step,choice,measurement);long now=SystemClock.uptimeMillis();
    String signature=measurement.optDouble("scale")+"|"+session.web.getScale()+"|"+session.reading.restoreAttempts+"|"+(session.web.zoomTarget!=null)+"|"+activityResumed+"|"+session.browserPaused+"|"+hasWindowFocus()+"|"+session.web.getWidth()+"|"+session.web.getHeight()+"|"+measurement.optString("visibility");
    if(readingZoomSamples[step]<24&&(force||!signature.equals(readingZoomLast)||now-readingZoomLastSample>=1000)){readingZoomSamples[step]++;event(serial,"readingZoomTrace",sample);readingZoomLast=signature;readingZoomLastSample=now;}
  }
  void readingInput(long serial,long deadline){
    if(serial!=run)return;session.web.evaluateJavascript("(()=>({focused:document.activeElement?.id,draft:document.getElementById('composer')?.value}))()",raw->{
      if(serial!=run)return;JSONObject result=J.parse(raw);
      if(result.optString("draft").contains("native-input-ok")){event(serial,"readingInput",J.obj("focused",result.optString("focused"),"draft",result.optString("draft"),"choice",session.reading.choice(),"layout",session.web.readingLayout));return;}
      if(SystemClock.elapsedRealtime()>deadline){event(serial,"error",J.obj("error","scaled native input did not receive keyboard text","measurement",result));return;}session.handler.postDelayed(()->readingInput(serial,deadline),200);
    });
  }
  void waitReadingZoom(long serial,int step,JSONArray results,long deadline,float choice){
    if(serial!=run)return;
    session.web.evaluateJavascript("(()=>{const e=document.getElementById('composer');if(!e)return null;return {viewport:document.documentElement.clientWidth,density:devicePixelRatio,scale:visualViewport.scale,draft:e.value,document:performance.timeOrigin,font:parseFloat(getComputedStyle(e).fontSize),visibility:document.visibilityState,documentFocused:document.hasFocus(),innerHeight,clientHeight:document.documentElement.clientHeight,scrollHeight:document.documentElement.scrollHeight,visualHeight:visualViewport.height,visualWidth:visualViewport.width}})()",raw->{
      if(serial!=run)return;JSONObject result=J.parse(raw);float factor=Math.min(1,choice);
      readingZoomSample(serial,step,choice,result,false);
      double expected=session.web.getWidth()/factor,resultWidth=result.optDouble("viewport")*result.optDouble("density");
      if(result.has("document")&&Math.abs(resultWidth-expected)<6&&Math.abs(result.optDouble("scale")-Math.max(1,choice))<.05){
        try{result.put("choice",choice);result.put("layout",session.web.readingLayout);result.put("shownFontPixels",result.optDouble("font")*result.optDouble("density")*result.optDouble("scale")*session.web.readingLayout);result.put("nativeScale",session.web.getScale());result.put("nativeWidth",session.web.getWidth());}catch(Exception ignored){}
        results.put(result);session.handler.postDelayed(()->readingZoom(serial,step+1,results,SystemClock.elapsedRealtime()+20000),200);return;
      }
      if(SystemClock.elapsedRealtime()>deadline){event(serial,"error",J.obj("error","real reading zoom did not apply","choice",choice,"layout",session.web.readingLayout,"measurement",result,"ready",session.reading.ready,"checks",results,"readiness",readingZoomReadiness,"lastNative",readingZoomSample(step,choice,result)));return;}
      session.handler.postDelayed(()->waitReadingZoom(serial,step,results,deadline,choice),150);
    });
  }
  static String readingBoundsScript(){return "(()=>{const e=document.getElementById('composer'),v=visualViewport;if(!e||!v)return null;const rect=id=>{const r=document.getElementById(id).getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom}};let hash=2166136261;for(const c of document.getElementById('reading-main').textContent)hash=Math.imul(hash^c.charCodeAt(0),16777619);const code=document.getElementById('reading-code');return {command:new URL(location.href).searchParams.get('command'),document:performance.timeOrigin,draft:e.value,cookie:document.cookie,bodyHash:(hash>>>0).toString(16),sends:Number(document.getElementById('reading-send-count').textContent),viewport:document.documentElement.clientWidth,scrollWidth:document.documentElement.scrollWidth,dpr:devicePixelRatio,scale:v.scale,visualWidth:v.width,visualHeight:v.height,offsetLeft:v.offsetLeft,offsetTop:v.offsetTop,pageLeft:v.pageLeft,pageTop:v.pageTop,innerHeight,clientHeight:document.documentElement.clientHeight,scrollX,scrollY,focused:document.activeElement?.id,blocks:[rect('reading-main'),rect('reading-paragraph'),rect('composer')],codeWidth:code.clientWidth,codeScrollWidth:code.scrollWidth,codeLeft:code.scrollLeft}})()";}
  JSONObject readingBoundsNative(JSONObject value){
    GeckoWebView web=session.web;android.graphics.Matrix matrix=new android.graphics.Matrix();web.current.getClientToSurfaceMatrix(matrix);float[] numbers=new float[9];matrix.getValues(numbers);
    try{value.put("matrixScale",numbers[android.graphics.Matrix.MSCALE_X]).put("matrixScaleY",numbers[android.graphics.Matrix.MSCALE_Y]).put("matrixX",numbers[android.graphics.Matrix.MTRANS_X]).put("matrixY",numbers[android.graphics.Matrix.MTRANS_Y]).put("nativeWidth",web.getWidth()).put("nativeHeight",web.getHeight()).put("layout",web.readingLayout).put("choice",session.reading.choice()).put("nativeScrollX",readingBoundsCase.scrollX).put("nativeScrollY",readingBoundsCase.scrollY).put("nativeUpdateZoom",readingBoundsCase.zoom).put("nativeUpdates",readingBoundsCase.updates).put("sessionIdentity",System.identityHashCode(web.current)).put("surfaceIdentity",System.identityHashCode(web.surface)).put("activityIdentity",System.identityHashCode(this)).put("privacyLevel",session.privacy.level()).put("fingerprintingProtected",web.fingerprintingProtected).put("nativeMeasured",web.readingScaleMeasured()).put("readingReady",session.reading.ready).put("rawPageScale",web.pageScales.getOrDefault(web.current,0f)).put("viewportWidth",session.reading.viewportWidth).put("restoreAttempts",session.reading.restoreAttempts).put("zoomActive",web.readingZoomActive());}catch(JSONException error){throw new IllegalStateException(error);}
    web.current.getPageToSurfaceMatrix(matrix);matrix.getValues(numbers);JSONArray pageMatrix=new JSONArray();for(float number:numbers)pageMatrix.put(Float.valueOf(number));int[] origin=new int[2];web.surface.getLocationOnScreen(origin);
    JSONObject input=value.optJSONArray("blocks")==null?null:value.optJSONArray("blocks").optJSONObject(2);if(input!=null){float[] points={(float)(input.optDouble("left")+value.optDouble("scrollX")),(float)(input.optDouble("top")+value.optDouble("scrollY")),(float)(input.optDouble("right")+value.optDouble("scrollX")),(float)(input.optDouble("bottom")+value.optDouble("scrollY"))};matrix.mapPoints(points);android.graphics.Rect visible=new android.graphics.Rect();web.getGlobalVisibleRect(visible);android.view.WindowInsets insets=web.getRootWindowInsets();int[] rootOrigin=new int[2];web.getRootView().getLocationOnScreen(rootOrigin);visible.offset(rootOrigin[0],rootOrigin[1]);int imeBottom=Build.VERSION.SDK_INT>=30&&insets!=null&&insets.isVisible(android.view.WindowInsets.Type.ime())?insets.getInsets(android.view.WindowInsets.Type.ime()).bottom:0;android.graphics.Rect windowBounds=Build.VERSION.SDK_INT>=30?getWindowManager().getCurrentWindowMetrics().getBounds():new android.graphics.Rect(rootOrigin[0],rootOrigin[1],rootOrigin[0]+web.getRootView().getWidth(),rootOrigin[1]+web.getRootView().getHeight());int imeTop=windowBounds.bottom-imeBottom;int visibleBottom=Math.min(visible.bottom,imeTop);double left=origin[0]+points[0]*web.readingLayout,top=origin[1]+points[1]*web.readingLayout,right=origin[0]+points[2]*web.readingLayout,bottom=origin[1]+points[3]*web.readingLayout;boolean physical=top>=visible.top-2&&bottom<=visibleBottom+2&&left>=visible.left-2&&right<=visible.right+2&&bottom>top;
      NetworkCatalog.put(value,"composerPhysicalRect",J.obj("left",left,"top",top,"right",right,"bottom",bottom));NetworkCatalog.put(value,"visibleSurfaceRect",J.obj("left",visible.left,"top",visible.top,"right",visible.right,"bottom",visibleBottom));NetworkCatalog.put(value,"imeTopPixels",imeTop);NetworkCatalog.put(value,"windowBounds",J.obj("left",windowBounds.left,"top",windowBounds.top,"right",windowBounds.right,"bottom",windowBounds.bottom));NetworkCatalog.put(value,"nativeComposerFits",physical);
    }
    NetworkCatalog.put(value,"pageToSurfaceMatrix",pageMatrix);NetworkCatalog.put(value,"productionKeyboardController",session.reading.keyboard&&((FixtureView)web).nativeFocusMeasurements>0&&session.reading.document==((FixtureView)web).lastFocusDocument&&web.getUrl().equals(((FixtureView)web).lastFocusUrl));NetworkCatalog.put(value,"nativeFocusRequests",((FixtureView)web).nativeFocusRequests);NetworkCatalog.put(value,"nativeFocusMeasurements",((FixtureView)web).nativeFocusMeasurements);NetworkCatalog.put(value,"nativeFocusScrolls",web.readingFocusScrolls);NetworkCatalog.put(value,"nativeFocusWasClipped",web.readingFocusHadClipping);NetworkCatalog.put(value,"nativeFocusScrollDeltaCss",web.readingFocusScrollDelta);return value;
  }
  void beginReadingBounds(long serial,int level){
    GeckoWebView web=session.web;ReadingBoundsCase test=new ReadingBoundsCase();test.privacy=session.privacy.level();test.command=serial;test.nativeSession=web.current;test.surface=web.surface;test.priorDelegate=web.current.getCompositorScrollDelegate();readingBoundsCase=test;
    // Forward every real SDK update to the unmodified production delegate.
    web.current.setCompositorScrollDelegate(new org.mozilla.geckoview.GeckoSession.CompositorScrollDelegate(){@Override public void onScrollChanged(org.mozilla.geckoview.GeckoSession own,org.mozilla.geckoview.GeckoSession.ScrollPositionUpdate update){test.scrollX=update.scrollX;test.scrollY=update.scrollY;test.zoom=update.zoom;test.updates++;if(test.priorDelegate!=null)test.priorDelegate.onScrollChanged(own,update);}});
    session.prefs.edit().putInt("privacyLevel",level).putFloat(BrowserReadingPolicy.ZOOM_KEY,4.2f).commit();session.reading.configure(true);web.configure(true,level);
    readingBoundsConfigured(serial,level,SystemClock.elapsedRealtime()+20000);
  }
  void readingBoundsConfigured(long serial,int level,long deadline){
    if(serial!=run)return;GeckoWebView web=session.web;
    if(web.privacyReady&&web.protectionLevel==level&&(level!=2||web.fingerprintingProtected)){readingBoundsCase.fingerprintingProtected=web.fingerprintingProtected;web.loadUrl("http://127.0.0.1:8765/browser-reading?command="+serial+"&bounds=1");session.handler.postDelayed(()->readingBoundsMagnified(serial,level,SystemClock.elapsedRealtime()+20000),100);return;}
    if(SystemClock.elapsedRealtime()>deadline){event(serial,"error",J.obj("error","reading bounds protection acknowledgment missing","level",level));return;}session.handler.postDelayed(()->readingBoundsConfigured(serial,level,deadline),100);
  }
  void readingBoundsMagnified(long serial,int level,long deadline){
    if(serial!=run)return;session.web.evaluateJavascript(readingBoundsScript(),raw->{
      if(serial!=run)return;JSONObject value=readingBoundsNative(J.parse(raw));double relative=value.optDouble("matrixScale")*value.optDouble("layout")*value.optDouble("viewport")/value.optInt("nativeWidth");
      if(String.valueOf(serial).equals(value.optString("command"))&&session.reading.ready&&session.web.painted.contains(session.web.current)&&Math.abs(relative-4.2)<.05&&session.web.zoomTarget==null){
        readingBoundsCase.before=value;event(serial,"readingBoundsBefore",value);session.web.current.getPanZoomController().scrollTo(org.mozilla.geckoview.ScreenLength.fromPixels(48),org.mozilla.geckoview.ScreenLength.fromPixels(320),org.mozilla.geckoview.PanZoomController.SCROLL_BEHAVIOR_AUTO);readingBoundsPanned(serial,level,SystemClock.elapsedRealtime()+20000);return;
      }
      if(SystemClock.elapsedRealtime()>deadline){event(serial,"error",J.obj("error","stored large reading zoom was not restored by real SDK","level",level,"measurement",value));return;}session.handler.postDelayed(()->readingBoundsMagnified(serial,level,deadline),100);
    });
  }
  void readingBoundsPanned(long serial,int level,long deadline){
    if(serial!=run)return;session.web.evaluateJavascript(readingBoundsScript(),raw->{
      if(serial!=run)return;JSONObject value=readingBoundsNative(J.parse(raw));
      if(Math.abs(value.optDouble("nativeScrollX")-48)<=1&&Math.abs(value.optDouble("pageLeft")-48)<=1&&Math.abs(value.optDouble("nativeScrollY")-320)<=1){readingBoundsCase.pan=value;event(serial,"readingBoundsPan",value);session.reading.fit();readingBoundsFitted(serial,level,SystemClock.elapsedRealtime()+20000);return;}
      if(SystemClock.elapsedRealtime()>deadline){event(serial,"error",J.obj("error","real SDK horizontal pan did not occur","measurement",value));return;}session.handler.postDelayed(()->readingBoundsPanned(serial,level,deadline),100);
    });
  }
  static boolean readingFits(JSONObject value){
    if(!value.has("document")||Math.abs(value.optDouble("choice")-1)>.001||Math.abs(value.optDouble("scale")-1)>.02||Math.abs(value.optDouble("matrixScale")-value.optDouble("matrixScaleY"))>.001||Math.abs(value.optInt("nativeWidth")-value.optDouble("matrixScale")*value.optDouble("layout")*value.optDouble("viewport"))>=6)return false;
    if(Math.abs(value.optDouble("nativeScrollX"))>1||Math.abs(value.optDouble("scrollX"))>1||Math.abs(value.optDouble("pageLeft"))>1||Math.abs(value.optDouble("offsetLeft"))>1||value.optInt("scrollWidth")>value.optInt("viewport")+1)return false;
    JSONArray blocks=value.optJSONArray("blocks");if(blocks==null||blocks.length()!=3)return false;double left=value.optDouble("offsetLeft"),right=left+value.optDouble("visualWidth");
    for(int i=0;i<blocks.length();i++){JSONObject block=blocks.optJSONObject(i);if(block==null||block.optDouble("left")<left-1||block.optDouble("right")>right+1||block.optDouble("right")<=block.optDouble("left"))return false;}return true;
  }
  static boolean readingIdentity(JSONObject before,JSONObject after){return before.optDouble("document")==after.optDouble("document")&&before.optString("draft").equals(after.optString("draft"))&&before.optString("cookie").equals(after.optString("cookie"))&&before.optString("bodyHash").equals(after.optString("bodyHash"))&&before.optInt("sessionIdentity")==after.optInt("sessionIdentity")&&before.optInt("surfaceIdentity")==after.optInt("surfaceIdentity")&&before.optInt("sends")==0&&after.optInt("sends")==0;}
  void readingBoundsFitted(long serial,int level,long deadline){
    if(serial!=run)return;session.web.evaluateJavascript(readingBoundsScript(),raw->{
      if(serial!=run)return;JSONObject value=readingBoundsNative(J.parse(raw));ReadingBoundsCase test=readingBoundsCase;
      boolean fit=readingFits(value)&&readingIdentity(test.before,value)&&Math.abs(value.optDouble("nativeScrollY")-test.pan.optDouble("nativeScrollY"))<=1&&session.web.zoomTarget==null;
      long now=SystemClock.elapsedRealtime();if(!fit){test.stableSamples=0;test.stableSince=now;}else {if(test.stableSamples++==0)test.stableSince=now;}
      if(fit&&test.stableSamples>=5&&now-test.stableSince>=500){
        session.web.evaluateJavascript("document.getElementById('reading-code').scrollLeft=96",unused->session.web.evaluateJavascript(readingBoundsScript(),rawCode->{
          if(serial!=run)return;JSONObject after=readingBoundsNative(J.parse(rawCode));if(!readingFits(after)||!readingIdentity(test.before,after)||after.optDouble("codeScrollWidth")<=after.optDouble("codeWidth")||after.optDouble("codeLeft")<=0){event(serial,"error",J.obj("error","fit changed content or prevented independent code scrolling","measurement",after));return;}
          boolean acknowledged=session.web.privacyReady&&session.web.protectionLevel==level;readingBoundsFitResult=after;if(level!=2){session.web.current.setCompositorScrollDelegate(test.priorDelegate);session.prefs.edit().putInt("privacyLevel",test.privacy).commit();session.web.configure(true,test.privacy);}
          event(serial,"readingBounds",J.obj("schema",1,"privacyLevel",level,"actualGeckoExecution",true,"protectionAcknowledged",acknowledged,"fingerprintingProtected",test.fingerprintingProtected,"fitUsedProductionController",true,"stableSamples",test.stableSamples,"stableMillis",now-test.stableSince,"after",after));
        }));return;
      }
      if(now>deadline){event(serial,"error",J.obj("error","fit did not restore both edges and preserve vertical reading position","measurement",value,"panY",test.pan.optDouble("nativeScrollY")));return;}session.handler.postDelayed(()->readingBoundsFitted(serial,level,deadline),100);
    });
  }
  void readingBoundsGeometry(long serial,long deadline){
    if(serial!=run)return;session.web.evaluateJavascript(readingBoundsScript(),raw->{
      if(serial!=run)return;JSONObject value=readingBoundsNative(J.parse(raw));NativeGeometry geometry=NativeGeometry.read((FixtureView)session.web);String requested=getIntent().getStringExtra("geometryPhase");boolean landscape="landscape".equals(requested);
      if(readingBoundsFitResult!=null&&geometry!=null&&!geometry.imeVisible&&geometry.normalBarsReady()&&readingFits(value)&&readingIdentity(readingBoundsFitResult,value)&&landscape==(geometry.webWidth>geometry.webHeight)){event(serial,"readingBoundsGeometry",J.obj("phase",requested,"measurement",value,"geometry",geometry.json()));return;}
      if(SystemClock.elapsedRealtime()>deadline){event(serial,"error",J.obj("error","reading fit did not survive actual Android rotation","phase",requested,"measurement",value));return;}session.handler.postDelayed(()->readingBoundsGeometry(serial,deadline),100);
    });
  }
  void readingBoundsTap(long serial){
    // Native matrix is used here too: RFP can deliberately mask page DPR.
    session.web.evaluateJavascript("(()=>{const r=document.getElementById('composer').getBoundingClientRect();return {x:r.left+r.width/2+scrollX,y:r.top+r.height/2+scrollY}})()",raw->{
      if(serial!=run)return;JSONObject box=J.parse(raw);android.graphics.Matrix matrix=new android.graphics.Matrix();session.web.current.getPageToSurfaceMatrix(matrix);float[] point={(float)box.optDouble("x"),(float)box.optDouble("y")};matrix.mapPoints(point);int[] origin=new int[2];session.web.surface.getLocationOnScreen(origin);point[0]=origin[0]+point[0]*session.web.readingLayout;point[1]=origin[1]+point[1]*session.web.readingLayout;
      if(point[0]<=origin[0]||point[0]>=origin[0]+session.web.getWidth()||point[1]<=origin[1]||point[1]>=origin[1]+session.web.getHeight()){event(serial,"error",J.obj("error","reading bounds native tap is outside the actual surface","x",point[0],"y",point[1]));return;}
      event(serial,"tapNeeded",J.obj("id","composer-bounds-"+serial,"x",Math.round(point[0]),"y",Math.round(point[1]),"nativeMatrix",true));
    });
  }
  void readingBoundsInput(long serial,long deadline){
    if(serial!=run)return;session.web.evaluateJavascript(readingBoundsScript(),raw->{
      if(serial!=run)return;JSONObject value=readingBoundsNative(J.parse(raw));NativeGeometry geometry=NativeGeometry.read((FixtureView)session.web);JSONObject input=value.optJSONArray("blocks")==null?null:value.optJSONArray("blocks").optJSONObject(2);
      if(geometry!=null&&geometry.imeVisible&&geometry.imeBottom>0&&readingFits(value)&&value.optString("draft").contains("native-input-ok")&&"composer".equals(value.optString("focused"))&&input!=null&&input.optDouble("top")>=value.optDouble("offsetTop")-1&&input.optDouble("bottom")<=value.optDouble("offsetTop")+value.optDouble("visualHeight")+1&&value.optBoolean("nativeComposerFits")&&value.optBoolean("productionKeyboardController")){event(serial,"readingBoundsInput",J.obj("measurement",value,"imeVisible",true,"imeBottom",geometry.imeBottom,"sameDocument",value.optDouble("document")==readingBoundsFitResult.optDouble("document"),"sameCookie",value.optString("cookie").equals(readingBoundsFitResult.optString("cookie")),"draftPreserved",insertedInputPreserves(readingBoundsFitResult.optString("draft"),value.optString("draft"))));return;}
      if(SystemClock.elapsedRealtime()>deadline){event(serial,"error",J.obj("error","fit composer did not stay inside the real IME viewport","measurement",value,"geometry",geometry==null?JSONObject.NULL:geometry.json()));return;}session.handler.postDelayed(()->readingBoundsInput(serial,deadline),100);
    });
  }
  void readingBoundsEnd(long serial,long deadline){
    if(serial!=run)return;boolean restored=session.web.privacyReady&&session.web.protectionLevel==readingBoundsCase.privacy&&session.privacy.level()==readingBoundsCase.privacy;
    if(restored){event(serial,"readingBoundsEnd",J.obj("productionDelegateRestored",session.web.current.getCompositorScrollDelegate()==readingBoundsCase.priorDelegate,"privacyRestored",true,"privacyLevel",session.privacy.level()));return;}
    if(SystemClock.elapsedRealtime()>deadline){event(serial,"error",J.obj("error","reading bounds did not restore the original privacy configuration"));return;}session.handler.postDelayed(()->readingBoundsEnd(serial,deadline),100);
  }
  static java.util.List<String> cookiesExceptReadingFixture(String value){
    java.util.List<String> result=new java.util.ArrayList<>();
    for(String cookie:value.split(";")){cookie=cookie.trim();if(!cookie.isEmpty()&&!cookie.equals("readingBounds=controlled-fixture"))result.add(cookie);}
    java.util.Collections.sort(result);return result;
  }
  static boolean hasReadingFixtureCookie(String value){for(String cookie:value.split(";"))if(cookie.trim().startsWith("readingBounds="))return true;return false;}
  static boolean hasExactReadingFixtureCookie(String value){int count=0;for(String cookie:value.split(";")){cookie=cookie.trim();if(cookie.startsWith("readingBounds=")){if(!cookie.equals("readingBounds=controlled-fixture"))return false;count++;}}return count==1;}
  void beginReadingFixtureCookieCleanup(long serial){
    if(!"local.pocketchat.test".equals(getPackageName())||slot!=1){event(serial,"error",J.obj("error","Reading cookie retirement requires the isolated second test environment"));return;}
    String target="http://127.0.0.1:8765/reading-cookie-retirement?runNonce="+eventStore.nonce;
    // Process-restart checks have already finished. This page has no scripts,
    // cookies or storage writes, so it cannot replace an unexpected marker.
    session.web.loadUrl(target);awaitReadingFixtureCookieCleanup(serial,target,SystemClock.elapsedRealtime()+15000);
  }
  void awaitReadingFixtureCookieCleanup(long serial,String target,long deadline){
    if(serial!=run)return;session.web.evaluateJavascript("(()=>({url:location.href,ready:document.readyState==='complete'}))()",raw->{
      if(serial!=run)return;JSONObject state=J.parse(raw);
      if(target.equals(state.optString("url"))&&state.optBoolean("ready")&&target.equals(session.web.getUrl())){removeReadingFixtureCookie(serial,new JSONObject(),"readingFixtureCookieCleanup","/reading-cookie-retirement");return;}
      if(SystemClock.elapsedRealtime()>deadline){event(serial,"error",J.obj("error","Owned reading cookie retirement page did not load"));return;}
      session.handler.postDelayed(()->awaitReadingFixtureCookieCleanup(serial,target,deadline),100);
    });
  }
  void removeReadingFixtureCookie(long serial,JSONObject checkpoint){removeReadingFixtureCookie(serial,checkpoint,"nativeCheckpoint","/browser-reading");}
  void removeReadingFixtureCookie(long serial,JSONObject checkpoint,String kind,String path){
    GeckoWebView web=session.web;org.mozilla.geckoview.GeckoSession document=web.current;String target=web.getUrl();android.net.Uri location=android.net.Uri.parse(target);
    if(!"local.pocketchat.test".equals(getPackageName())||!"http".equals(location.getScheme())||!"127.0.0.1".equals(location.getHost())||location.getPort()!=8765||!path.equals(location.getPath())||"readingFixtureCookieCleanup".equals(kind)&&!eventStore.nonce.equals(location.getQueryParameter("runNonce"))){event(serial,"error",J.obj("error","Reading cookie retirement page is not owned by this fixture invocation"));return;}
    web.readCookies("http://127.0.0.1:8765/fixture",nativeBefore->{
      if(serial!=run)return;
      if(web.current!=document||nativeBefore==null||!hasExactReadingFixtureCookie(nativeBefore)){event(serial,"error",J.obj("error","Reading cookie retirement requires one exact known native marker","nativeBefore",nativeBefore));return;}
      // The completed reading cases own exactly this loopback marker. Unknown
      // same-name values and every other cookie remain outside this retirement.
      web.evaluateJavascript("(()=>{if(location.origin!=='http://127.0.0.1:8765'||location.pathname!=="+JSONObject.quote(path)+"||location.href!=="+JSONObject.quote(target)+")return null;const before=document.cookie,markers=before.split(';').map(v=>v.trim()).filter(v=>v.startsWith('readingBounds='));if(markers.length!==1||markers[0]!=='readingBounds=controlled-fixture')return {error:'Unexpected reading fixture marker',before};const documentBefore=performance.timeOrigin;document.cookie='readingBounds=; Max-Age=0; Path=/';return {before,after:document.cookie,documentBefore,documentAfter:performance.timeOrigin}})()",raw->{
        if(serial!=run)return;JSONObject cookies=J.parse(raw);String before=cookies.optString("before"),after=cookies.optString("after");
        boolean domRemoved=!cookies.has("error")&&hasExactReadingFixtureCookie(before)&&!hasReadingFixtureCookie(after),domPreserved=cookiesExceptReadingFixture(before).equals(cookiesExceptReadingFixture(after));
        if(!domRemoved||!domPreserved){event(serial,"error",J.obj("error","Reading cookie retirement did not preserve the other DOM cookies","beforeDomCookies",before,"afterDomCookies",after,"nativeBefore",nativeBefore));return;}
        web.readCookies("http://127.0.0.1:8765/fixture",nativeAfter->{
          if(serial!=run)return;boolean nativeRemoved=nativeAfter!=null&&!hasReadingFixtureCookie(nativeAfter),nativePreserved=nativeAfter!=null&&cookiesExceptReadingFixture(nativeBefore).equals(cookiesExceptReadingFixture(nativeAfter));
          if(web.current!=document||!target.equals(web.getUrl())||!nativeRemoved||!nativePreserved){event(serial,"error",J.obj("error","Reading cookie retirement did not preserve the other native cookies","nativeBefore",nativeBefore,"nativeAfter",nativeAfter));return;}
          web.evaluateJavascript("(()=>({url:location.href,document:performance.timeOrigin,cookie:document.cookie}))()",finalRaw->{
            if(serial!=run)return;JSONObject finalPage=J.parse(finalRaw);double beforeDocument=cookies.optDouble("documentBefore",-1),afterDocument=finalPage.optDouble("document",-1);
            boolean sameSession=web.current==document,sameUrl=target.equals(web.getUrl())&&target.equals(finalPage.optString("url")),sameDocument=beforeDocument>0&&beforeDocument==cookies.optDouble("documentAfter",-1)&&beforeDocument==afterDocument;
            if(!sameSession||!sameUrl||!sameDocument||!cookiesExceptReadingFixture(after).equals(cookiesExceptReadingFixture(finalPage.optString("cookie")))||hasReadingFixtureCookie(finalPage.optString("cookie"))){event(serial,"error",J.obj("error","Reading cookie retirement lost its owned document"));return;}
            JSONObject receipt=J.obj("schema",1,"cookie","readingBounds=controlled-fixture","cookiePath","/","processSlot",slot,"runNonce",eventStore.nonce,"invocation",serial,"origin","http://127.0.0.1:8765","url",target,"sameSession",sameSession,"sameDocument",sameDocument,"sameUrl",sameUrl,"sessionBefore",System.identityHashCode(document),"sessionAfter",System.identityHashCode(web.current),"documentBefore",beforeDocument,"documentAfter",afterDocument,"beforeDomCookies",before,"afterDomCookies",finalPage.optString("cookie"),"nativeBefore",nativeBefore,"nativeAfter",nativeAfter,"readingFixtureCookieRemovedFromDom",domRemoved,"readingFixtureCookieRemovedFromNative",nativeRemoved,"otherDomCookiesPreserved",domPreserved,"otherNativeCookiesPreserved",nativePreserved);
            if("readingFixtureCookieCleanup".equals(kind)){event(serial,kind,receipt);return;}
            NetworkCatalog.put(checkpoint,"readingFixtureCookieRemovedFromDom",domRemoved);NetworkCatalog.put(checkpoint,"readingFixtureCookieRemovedFromNative",nativeRemoved);NetworkCatalog.put(checkpoint,"otherDomCookiesPreserved",domPreserved);NetworkCatalog.put(checkpoint,"otherNativeCookiesPreserved",nativePreserved);NetworkCatalog.put(checkpoint,"readingFixtureCookieCleanup",receipt);event(serial,"nativeCheckpoint",checkpoint);
          });
        });
      });
    });
  }
  static java.lang.reflect.Field field(Object object,String name)throws ReflectiveOperationException{Class<?> type=object.getClass();while(type!=null){try{java.lang.reflect.Field found=type.getDeclaredField(name);found.setAccessible(true);return found;}catch(NoSuchFieldException missing){type=type.getSuperclass();}}throw new NoSuchFieldException(name);}
  static long number(Object object,String name)throws ReflectiveOperationException{Object value=field(object,name).get(object);return value instanceof java.util.concurrent.atomic.AtomicLong?((java.util.concurrent.atomic.AtomicLong)value).get():((Number)value).longValue();}
  JSONObject nativePage(String raw){return J.parse(raw);}
  static boolean insertedInputPreserves(String before,String after){String added="native-input-ok";for(int at=after.indexOf(added);at>=0;at=after.indexOf(added,at+1))if((after.substring(0,at)+after.substring(at+added.length())).equals(before))return true;return false;}
  static final class NativeGeometryReadiness {
    final long started=SystemClock.elapsedRealtime(),deadline=started+25000;long stableSince;int stableFrames,totalFrames,changes;
    NativeGeometry previous;final JSONArray transitions=new JSONArray();
  }
  void nativeGeometryDiagnostics(long serial,String phase,JSONArray entries,int from){for(int i=from;i<entries.length();i++)event(serial,"nativeSurfaceGeometry",J.obj("phase",phase,"entry",entries.optJSONObject(i)));}
  void nativeSurface(long serial){
    FixtureView web=(FixtureView)session.web;
    // The emulator's launcher can recreate its taskbar long after returning to
    // this Activity. Request ordinary visible system bars, then require their
    // actual insets below; a temporarily absent navigation bar is not stable.
    if(Build.VERSION.SDK_INT>=30){android.view.WindowInsetsController bars=getWindow().getInsetsController();if(bars==null){event(serial,"error",J.obj("error","native surface system bar controller unavailable"));return;}bars.setSystemBarsBehavior(android.view.WindowInsetsController.BEHAVIOR_DEFAULT);bars.show(android.view.WindowInsets.Type.systemBars());}
    else getWindow().getDecorView().setSystemUiVisibility(0);
    web.evaluateJavascript("(()=>({document:performance.timeOrigin,draft:document.getElementById('composer')?.value,cookie:document.cookie}))()",raw->{
      if(serial!=run)return;JSONObject before=nativePage(raw);if(!before.has("draft")){event(serial,"error",J.obj("error","native surface test needs the existing reading fixture"));return;}
      awaitNativeGeometry(serial,before,new NativeGeometryReadiness());
    });
  }
  void awaitNativeGeometry(long serial,JSONObject before,NativeGeometryReadiness readiness){
    if(serial!=run)return;FixtureView web=(FixtureView)session.web;NativeGeometry geometry=NativeGeometry.read(web);long now=SystemClock.elapsedRealtime();readiness.totalFrames++;
    boolean unchanged=readiness.previous!=null&&readiness.previous.same(geometry);
    if(!unchanged){readiness.changes++;if(readiness.transitions.length()<16)readiness.transitions.put(J.obj("elapsed",now-readiness.started,"geometry",geometry==null?JSONObject.NULL:geometry.json()));}
    boolean ready=geometry!=null&&geometry.focused&&!geometry.imeVisible&&geometry.imeBottom==0&&geometry.normalBarsReady()&&geometry.webWidth>0&&geometry.webHeight>0&&geometry.attached==web.current;
    if(!ready||!unchanged){readiness.stableSince=now;readiness.stableFrames=ready?1:0;}else readiness.stableFrames++;
    readiness.previous=geometry;
    // A launcher/taskbar reconfiguration and the IME hide animation are legal
    // geometry changes. Isolate them before measuring an unchanged surface;
    // retain strict one-sync verification during the three real swipes.
    if(ready&&readiness.stableFrames>=8&&now-readiness.stableSince>=1000){nativeGeometryDiagnostics(serial,"readiness",readiness.transitions,0);nativeSurfaceProbe(serial,before,geometry,J.obj("imeHidden",true,"systemBarsRequested",true,"normalBarsVisible",geometry.normalBarsReady(),"stableFrames",readiness.stableFrames,"stableMillis",now-readiness.stableSince,"totalFrames",readiness.totalFrames,"waitMillis",now-readiness.started,"geometryChanges",readiness.changes,"geometry",geometry.json()));return;}
    if(now>readiness.deadline){nativeGeometryDiagnostics(serial,"readiness",readiness.transitions,0);event(serial,"error",J.obj("error","native surface geometry did not settle","stableFrames",readiness.stableFrames,"stableMillis",now-readiness.stableSince,"totalFrames",readiness.totalFrames,"geometry",geometry==null?JSONObject.NULL:geometry.json()));return;}
    web.postOnAnimation(()->awaitNativeGeometry(serial,before,readiness));
  }
  void nativeSurfaceProbe(long serial,JSONObject before,NativeGeometry baseline,JSONObject readiness){
    FixtureView web=(FixtureView)session.web;
    try{field(web,"nativePerfEnabled").setBoolean(web,true);field(web,"surfaceOriginChecks").setLong(web,0);field(web,"surfaceOriginSyncs").setLong(web,0);}catch(ReflectiveOperationException missing){event(serial,"error",J.obj("error","native geometry instrumentation missing"));return;}
    web.nativeGeometryTrace=new JSONArray();web.nativeGeometryPrevious=baseline;web.nativeUnchangedTouchEvents=web.nativeRedundantTouchSyncs=0;web.nativeFirstTouchSyncs=-1;web.nativeFirstTouchOriginCorrect=false;web.nativeGeometryActive=true;
    float x=web.getTranslationX(),y=web.getTranslationY();web.setTranslationX(x+7);web.setTranslationY(y+11);web.nativeGestureCount=0;
    NativeGeometry moved=NativeGeometry.read(web);web.nativeGeometrySwipes=false;web.recordNativeGeometry("test-translation-initial",baseline,moved,0,false);web.nativeGeometryExpected=moved;web.nativeGeometryStable=true;web.nativeGeometrySwipes=true;
    web.nativeGestureComplete=()->{
      if(serial!=run)return;
      try{
        long checks=number(web,"surfaceOriginChecks"),syncs=number(web,"surfaceOriginSyncs");
        boolean stable=web.nativeGeometryStable&&moved!=null&&moved.same(NativeGeometry.read(web));web.nativeGeometrySwipes=false;nativeGeometryDiagnostics(serial,"swipes",web.nativeGeometryTrace,0);
        JSONObject result=J.obj("originChecks",checks,"originSyncs",syncs,"actualGestureCount",web.nativeGestureCount,"stationaryGeometryDeduplicated",checks>=20&&syncs==1&&web.nativeRedundantTouchSyncs==0&&stable,"initialSurfaceMoveSynced",syncs==1&&web.nativeFirstTouchSyncs==1&&web.nativeFirstTouchOriginCorrect,"geometryReadiness",readiness,"unchangedTouchEvents",web.nativeUnchangedTouchEvents,"redundantTouchSyncs",web.nativeRedundantTouchSyncs,"firstTouchSyncs",web.nativeFirstTouchSyncs,"firstTouchOriginCorrect",web.nativeFirstTouchOriginCorrect,"stationaryGeometryTraceCount",web.nativeGeometryTrace.length(),"geometryStableDuringSwipes",stable);
        // Move without a layout pass, then use the runner's real Android tap
        // and hardware input. The first touch must see the new screen origin.
        NativeGeometry old=NativeGeometry.read(web);web.setTranslationX(x+13);web.setTranslationY(y+19);web.recordNativeGeometry("test-translation-input",old,NativeGeometry.read(web),0,false);tapElement(serial,"composer");
        nativeSurfaceInput(serial,SystemClock.elapsedRealtime()+20000,before,result,x,y);
      }catch(Exception error){event(serial,"error",J.obj("error",error.toString()));}
    };
    int[] at=new int[2];web.getLocationOnScreen(at);int touchX=at[0]+web.getWidth()/2,from=at[1]+Math.round(web.getHeight()*.7f),to=at[1]+Math.round(web.getHeight()*.35f);
    for(int i=0;i<3;i++)event(serial,"swipeNeeded",J.obj("id","native-surface-"+serial+"-"+i,"x",touchX,"fromY",from,"toY",to,"duration",500));
    session.handler.postDelayed(()->{if(serial==run&&web.nativeGestureComplete!=null){web.nativeGestureComplete=null;web.nativeGeometryActive=false;web.setTranslationX(x);web.setTranslationY(y);try{field(web,"nativePerfEnabled").setBoolean(web,false);}catch(Exception ignored){}nativeGeometryDiagnostics(serial,"swipe-timeout",web.nativeGeometryTrace,0);event(serial,"error",J.obj("error","native surface real gestures not received","gestureCount",web.nativeGestureCount));}},25000);
  }
  void nativeSurfaceInput(long serial,long deadline,JSONObject before,JSONObject result,float originalX,float originalY){
    if(serial!=run)return;FixtureView web=(FixtureView)session.web;
    web.evaluateJavascript("(()=>({document:performance.timeOrigin,draft:document.getElementById('composer')?.value,focused:document.activeElement?.id,cookie:document.cookie}))()",raw->{
      if(serial!=run)return;JSONObject after=nativePage(raw);
      if(insertedInputPreserves(before.optString("draft"),after.optString("draft"))){
        try{
          long total=number(web,"surfaceOriginSyncs");result.put("movedSurfaceSyncs",total-result.optLong("originSyncs"));result.put("movedSurfaceAcceptsRealInput",total>result.optLong("originSyncs")&&"composer".equals(after.optString("focused")));
          result.put("documentAndDraftPreserved",after.optDouble("document")==before.optDouble("document")&&after.optString("cookie").equals(before.optString("cookie"))&&insertedInputPreserves(before.optString("draft"),after.optString("draft")));
          result.put("typedCharacters",after.optString("draft").length()-before.optString("draft").length());nativeGeometryDiagnostics(serial,"input",web.nativeGeometryTrace,result.optInt("stationaryGeometryTraceCount"));result.put("finalGeometryTraceCount",web.nativeGeometryTrace.length());web.nativeGeometryActive=false;field(web,"nativePerfEnabled").setBoolean(web,false);
        }catch(Exception error){event(serial,"error",J.obj("error",error.toString()));return;}
        web.setTranslationX(originalX);web.setTranslationY(originalY);event(serial,"nativeSurface",result);return;
      }
      if(SystemClock.elapsedRealtime()>deadline){web.nativeGeometryActive=false;web.setTranslationX(originalX);web.setTranslationY(originalY);try{field(web,"nativePerfEnabled").setBoolean(web,false);}catch(Exception ignored){}nativeGeometryDiagnostics(serial,"input-timeout",web.nativeGeometryTrace,result.optInt("stationaryGeometryTraceCount"));event(serial,"error",J.obj("error","moved surface did not accept real keyboard input","result",result));return;}
      session.handler.postDelayed(()->nativeSurfaceInput(serial,deadline,before,result,originalX,originalY),100);
    });
  }
  void nativeCheckpoint(long serial){
    org.mozilla.geckoview.GeckoSession.SessionState state=session.web.states.get(session.web.primary);
    if(state==null){event(serial,"error",J.obj("error","checkpoint test needs a real SDK session state"));return;}
    new Thread(()->{
      try{
        java.io.File own=new java.io.File(getNoBackupFilesDir(),"native-checkpoint-fixture"),other=new java.io.File(Profiles.context(this,slot==0?1:0).getNoBackupFilesDir(),"native-checkpoint-fixture");if(!own.isDirectory()&&!own.mkdirs()||!other.isDirectory()&&!other.mkdirs())throw new java.io.IOException("fixture directory unavailable");
        BrowserSessionStore store=new BrowserSessionStore(new ContextWrapper(this){@Override public java.io.File getNoBackupFilesDir(){return own;}}),isolated=new BrowserSessionStore(new ContextWrapper(this){@Override public java.io.File getNoBackupFilesDir(){return other;}});
        java.lang.reflect.Method offer=BrowserSessionStore.class.getDeclaredMethod("write",java.util.function.Supplier.class);offer.setAccessible(true);
        Object probe=Class.forName("local.pocketchat.BrowserSessionStore$Probe").getDeclaredConstructor().newInstance();field(store,"probe").set(store,probe);
        java.util.concurrent.CountDownLatch release=new java.util.concurrent.CountDownLatch(1);store.io.execute(()->await(release));
        onMain(()->{for(int i=0;i<1000;i++){final int candidate=i;offer(offer,store,()->checkpointValue(state,candidate));}});release.countDown();String first=readCheckpoint(store);JSONObject firstValue=J.parse(first);
        long firstSerialized=number(probe,"serialized"),firstCoalesced=number(probe,"coalesced");
        java.util.concurrent.CountDownLatch started=new java.util.concurrent.CountDownLatch(1),finish=new java.util.concurrent.CountDownLatch(1);
        onMain(()->offer(offer,store,()->{started.countDown();await(finish);return checkpointValue(state,-1);}));await(started);
        onMain(()->{for(int i=0;i<200;i++){final int candidate=1000+i;offer(offer,store,()->checkpointValue(state,candidate));}});finish.countDown();String latest=readCheckpoint(store);JSONObject latestValue=J.parse(latest);long latestWrites=number(probe,"written");
        onMain(()->offer(offer,store,()->"中".repeat(720000)));String afterOversize=readCheckpoint(store);
        boolean[] invalidRetained=new boolean[3];String lastValid=latest;
        for(int i=0;i<3;i++){
          final int failure=i,candidate=2000+i;java.util.concurrent.CountDownLatch validStarted=new java.util.concurrent.CountDownLatch(1),validRelease=new java.util.concurrent.CountDownLatch(1);
          onMain(()->offer(offer,store,()->{validStarted.countDown();await(validRelease);return checkpointValue(state,candidate);}));await(validStarted);
          onMain(()->offer(offer,store,()->{if(failure==0)return null;if(failure==1)throw new IllegalStateException("synthetic invalid snapshot");return "中".repeat(720000);}));validRelease.countDown();lastValid=readCheckpoint(store);invalidRetained[i]=J.parse(lastValid).optInt("nativeFixtureCandidate",-2)==candidate;
        }
        int lastValidCandidate=J.parse(lastValid).optInt("nativeFixtureCandidate",-2);
        final java.util.concurrent.atomic.AtomicInteger continuousOffered=new java.util.concurrent.atomic.AtomicInteger();final java.util.concurrent.atomic.AtomicBoolean offering=new java.util.concurrent.atomic.AtomicBoolean(true);final java.util.concurrent.CountDownLatch continuousDone=new java.util.concurrent.CountDownLatch(1);long writtenBeforeContinuous=number(probe,"written"),serializedBeforeContinuous=number(probe,"serialized");
        onMain(new Runnable(){public void run(){int index=continuousOffered.getAndIncrement();if(index==200){offering.set(false);continuousDone.countDown();return;}offer(offer,store,()->{try{Thread.sleep(80);}catch(InterruptedException error){Thread.currentThread().interrupt();throw new IllegalStateException(error);}return checkpointValue(state,4000+index);});session.handler.postDelayed(this,20);}});
        long continuousDeadline=SystemClock.elapsedRealtime()+10000,continuousWrites=0;boolean persistedWhileOffering=false;
        while(SystemClock.elapsedRealtime()<continuousDeadline){continuousWrites=number(probe,"written")-writtenBeforeContinuous;if(continuousWrites>0&&offering.get()){persistedWhileOffering=true;break;}if(!offering.get())break;Thread.sleep(20);}
        await(continuousDone);String continuousLast=readCheckpoint(store);int continuousCandidate=J.parse(continuousLast).optInt("nativeFixtureCandidate",-2);
        onMain(()->offer(offer,isolated,()->"isolated-synthetic-environment"));String independent=readCheckpoint(isolated),unchanged=readCheckpoint(store);
        org.mozilla.geckoview.GeckoSession.SessionState restored=org.mozilla.geckoview.GeckoSession.SessionState.fromString(latest);
        JSONObject result=J.obj("offered",number(probe,"offered"),"coalesced",number(probe,"coalesced"),"serialized",number(probe,"serialized"),"mainSerialized",number(probe,"mainSerialized"),"written",number(probe,"written"),"serializeNanos",number(probe,"serializeNanos"),"encodedBytes",number(probe,"bytes"),"firstBurstSerialized",firstSerialized,"firstBurstCoalesced",firstCoalesced,"firstCandidate",firstValue.optInt("nativeFixtureCandidate",-2),"lastCandidate",latestValue.optInt("nativeFixtureCandidate",-2),"latestWrites",latestWrites,"lastValidCandidate",lastValidCandidate,"validAfterNullCandidate",invalidRetained[0],"validAfterThrowingCandidate",invalidRetained[1],"validAfterUtf8Oversize",invalidRetained[2],"invalidNewerKeepsValid",invalidRetained[0]&&invalidRetained[1]&&invalidRetained[2],"continuousOffered",Math.min(200,continuousOffered.get()),"continuousWritesDuringOffers",continuousWrites,"continuousOffersPersisted",persistedWhileOffering,"continuousLastCandidate",continuousCandidate,"continuousSerialized",number(probe,"serialized")-serializedBeforeContinuous,"mainSerializationZero",number(probe,"mainSerialized")==0,"pendingBounded",firstSerialized==1&&firstCoalesced==999&&firstValue.optInt("nativeFixtureCandidate",-2)==999,"latestWinsDuringSerialization",latestValue.optInt("nativeFixtureCandidate",-2)==1199&&latestWrites==2,"oversizeKeepsPrevious",latest.equals(afterOversize),"independentStore","isolated-synthetic-environment".equals(independent)&&continuousLast.equals(unchanged),"sdkSnapshotRestorable",restored!=null&&restored.size()==state.size()&&GeckoWebView.stateUrl(restored).equals(GeckoWebView.stateUrl(state)));
        store.io.shutdown();isolated.io.shutdown();runOnUiThread(()->{if(serial==run)removeReadingFixtureCookie(serial,result);});
      }catch(Exception error){runOnUiThread(()->event(serial,"error",J.obj("error","native checkpoint regression: "+error)));}
    },"checkpoint-regression").start();
  }
  static String checkpointValue(org.mozilla.geckoview.GeckoSession.SessionState state,int candidate){if(Looper.myLooper()==Looper.getMainLooper())throw new IllegalStateException("serialization ran on UI");JSONObject value=J.parse(state.toString());try{value.put("nativeFixtureCandidate",candidate);value.put("nativeFixturePadding","x".repeat(300000));}catch(JSONException error){throw new IllegalStateException(error);}return value.toString();}
  static void offer(java.lang.reflect.Method method,BrowserSessionStore store,java.util.function.Supplier<String> supplier){try{method.invoke(store,supplier);}catch(Exception error){throw new IllegalStateException(error);}}
  static void await(java.util.concurrent.CountDownLatch latch){try{if(!latch.await(15,java.util.concurrent.TimeUnit.SECONDS))throw new IllegalStateException("checkpoint fixture timed out");}catch(InterruptedException error){Thread.currentThread().interrupt();throw new IllegalStateException(error);}}
  void onMain(Runnable task){java.util.concurrent.CountDownLatch done=new java.util.concurrent.CountDownLatch(1);java.util.concurrent.atomic.AtomicReference<RuntimeException> error=new java.util.concurrent.atomic.AtomicReference<>();runOnUiThread(()->{try{task.run();}catch(RuntimeException failure){error.set(failure);}finally{done.countDown();}});await(done);if(error.get()!=null)throw error.get();}
  static String readCheckpoint(BrowserSessionStore store){java.util.concurrent.CountDownLatch done=new java.util.concurrent.CountDownLatch(1);java.util.concurrent.atomic.AtomicReference<String> value=new java.util.concurrent.atomic.AtomicReference<>();store.read(result->{value.set(result);done.countDown();});await(done);return value.get();}
  JSONObject eventBuildIdentity;IntegrationEventStore eventStore;
  synchronized void event(long serial,String kind,JSONObject result){if(serial!=run)return;try{if(eventStore==null||eventStore.command!=serial)throw new IllegalStateException("Missing invocation");eventStore.emit(kind,result);}catch(Exception failure){Log.e("PocketGeckoIntegration",J.obj("kind","eventTransportError","error",failure.toString(),"nativeContext","environment-"+(slot+1),"processSlot",slot,"fixtureAction",action,"runNonce",getIntent().getStringExtra("eventNonce"),"command",run).toString());}}
  void readingLifecycle(String phase){if("readingZoom".equals(action)&&session!=null)event(run,"readingZoomLifecycle",J.obj("phase",phase,"uptimeMs",SystemClock.uptimeMillis(),"wallMs",System.currentTimeMillis(),"activityResumed",activityResumed,"browserPaused",session.browserPaused,"nativeScale",session.web.getScale(),"zoomActive",session.web.zoomTarget!=null,"webShown",session.web.isShown(),"windowFocused",hasWindowFocus()));}
  @Override protected void onResume(){super.onResume();activityResumed=true;if(session!=null)session.foreground(true);readingLifecycle("onResume");observeReadiness(run,"onResume",true);}
  @Override protected void onPause(){activityResumed=false;if(session!=null){session.reading.keyboard(false);session.foreground(false);}readingLifecycle("onPause");observeReadiness(run,"onPause",true);super.onPause();}
  @Override protected void onDestroy(){observeReadiness(run,"onDestroy",true);run++;super.onDestroy();}
}
