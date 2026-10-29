package local.pocketchat;

import android.os.SystemClock;
import android.view.MotionEvent;
import org.json.JSONObject;
import org.mozilla.geckoview.GeckoSession;

/** Integration-only window-tap preparation. Focus is checked before the event is
 * emitted, not atomically with the runner's later Android input injection. */
final class GeckoWindowTapReadiness {
  final GeckoIntegrationTestActivity activity;
  final ChatSession session;
  final GeckoIntegrationTestActivity.FixtureView web;
  final GeckoSession nativeSession;
  final Object port;
  final long serial,deadline,load,navigation,connection,started;
  final String target;
  boolean boundsPending,boundsAccepted,tapEmitted,retired;
  int polls,boundsRequests,down,up,downForwarded,upForwarded;
  boolean overflow,activityFocused,webFocused,webShown,webAttached,surfaceFocused,surfaceShown,surfaceAttached;
  boolean sameOwner,sameSession,samePort,sameDocument,beforeBoundsReady,afterBoundsReady;
  boolean downActivityFocused,downWebFocused,upActivityFocused,upWebFocused,downHandled,upHandled;
  long sampledAt,emittedAt,downAt,upAt;
  int tapX,tapY;

  static void begin(GeckoIntegrationTestActivity activity,long serial,GeckoSession parent,long deadline){
    GeckoIntegrationTestActivity.FixtureView web=(GeckoIntegrationTestActivity.FixtureView)activity.session.web;
    if(web.windowTapReadiness!=null)web.windowTapReadiness.retired=true;
    GeckoWindowTapReadiness gate=new GeckoWindowTapReadiness(activity,serial,parent,deadline);
    web.windowTapReadiness=gate;gate.poll();
  }
  GeckoWindowTapReadiness(GeckoIntegrationTestActivity activity,long serial,GeckoSession parent,long deadline){
    this.activity=activity;session=activity.session;web=(GeckoIntegrationTestActivity.FixtureView)session.web;
    this.serial=serial;this.deadline=deadline;nativeSession=parent;started=SystemClock.elapsedRealtime();
    port=web.ports.get(parent);load=web.appearanceLoads.getOrDefault(parent,0L);
    navigation=session.navigationEpoch;connection=session.connectionEpoch;target=activity.windowUrl("two",serial);
  }
  boolean invocation(){
    boolean current=activity.run==serial&&activity.session==session&&session.web==web&&web.windowTapReadiness==this
        &&("windows".equals(activity.action)||"lostParent".equals(activity.action));
    if(!current)retired=true;return current;
  }
  boolean sample(){
    sampledAt=SystemClock.elapsedRealtime();
    sameOwner=invocation()&&!activity.isDestroyed()&&!activity.isFinishing()&&!session.deleted;
    sameSession=web.current==nativeSession&&nativeSession!=null&&nativeSession.isOpen()
        &&web.surface!=null&&web.surface.getSession()==nativeSession;
    samePort=port!=null&&web.ports.get(nativeSession)==port;
    sameDocument=load>0&&web.appearanceLoads.getOrDefault(nativeSession,0L)==load
        &&target.equals(web.getUrl())&&target.equals(web.locations.get(nativeSession))
        &&!web.pendingLoads.contains(nativeSession)&&web.painted.contains(nativeSession)
        &&session.navigationEpoch==navigation&&session.connectionEpoch==connection;
    activityFocused=activity.hasWindowFocus();webFocused=web.hasWindowFocus();webShown=web.isShown();webAttached=web.isAttachedToWindow();
    surfaceFocused=web.surface!=null&&web.surface.hasWindowFocus();surfaceShown=web.surface!=null&&web.surface.isShown();surfaceAttached=web.surface!=null&&web.surface.isAttachedToWindow();
    sampledAt=SystemClock.elapsedRealtime();
    if(!sameOwner||!sameSession||!samePort||!sameDocument||sampledAt>=deadline)retired=true;
    return !retired&&activityFocused&&webFocused&&webShown&&webAttached&&surfaceFocused&&surfaceShown&&surfaceAttached&&!session.browserPaused;
  }
  void later(){
    long remaining=deadline-SystemClock.elapsedRealtime();
    if(retired||remaining<=0){retired=true;return;}
    session.handler.postDelayed(this::poll,Math.min(100,remaining));
  }
  void poll(){
    if(!invocation()||retired||tapEmitted||boundsAccepted||boundsPending)return;
    if(polls==256){overflow=retired=true;return;}polls++;
    if(!sample()){later();return;}
    beforeBoundsReady=true;boundsPending=true;boundsRequests++;
    activity.tapElement(serial,"popup");
  }
  boolean acceptBounds(long value,String id){
    if(value!=serial||!"popup".equals(id)||!boundsPending||boundsAccepted||tapEmitted||retired)return false;
    boundsPending=false;
    if(!sample()){later();return false;}
    afterBoundsReady=true;boundsAccepted=true;return true;
  }
  boolean beforeEvent(long value,String kind,JSONObject result){
    if(value==serial&&"tapNeeded".equals(kind)&&("popup-"+serial).equals(result.optString("id"))){
      if(!boundsAccepted||tapEmitted||retired)return false;
      if(!sample()){boundsAccepted=false;later();return false;}
      tapEmitted=true;emittedAt=sampledAt;tapX=result.optInt("x");tapY=result.optInt("y");
      NetworkCatalog.put(result,"windowTapReadiness",snapshot());return true;
    }
    if(invocation()&&value==serial&&("error".equals(kind)||"windowFlow".equals(kind)))NetworkCatalog.put(result,"windowTapReadiness",snapshot());
    return true;
  }
  static boolean beforeEvent(GeckoIntegrationTestActivity activity,long serial,String kind,JSONObject result){
    boolean popup="tapNeeded".equals(kind)&&("popup-"+serial).equals(result.optString("id"));
    if(activity.session!=null&&activity.session.web instanceof GeckoIntegrationTestActivity.FixtureView){
      GeckoWindowTapReadiness gate=((GeckoIntegrationTestActivity.FixtureView)activity.session.web).windowTapReadiness;
      if(gate!=null){if(popup&&(gate.serial!=serial||gate.activity!=activity))return false;return gate.beforeEvent(serial,kind,result);}
    }
    // The popup marker is reserved by windowFlow; a missing owner cannot admit it.
    return !popup;
  }
  boolean observeTouch(MotionEvent event){
    if(!tapEmitted||retired||!invocation())return false;
    int action=event.getActionMasked();
    float rawX=event.getRawX(),rawY=event.getRawY();
    if((action!=MotionEvent.ACTION_DOWN&&action!=MotionEvent.ACTION_UP)||!Float.isFinite(rawX)||!Float.isFinite(rawY)||Math.abs(rawX-tapX)>2||Math.abs(rawY-tapY)>2)return false;
    sample();if(retired)return false;
    if(action==MotionEvent.ACTION_DOWN){if(down==8){overflow=true;return false;}down++;downAt=sampledAt;downActivityFocused=activityFocused;downWebFocused=webFocused;}
    else{if(up==8){overflow=true;return false;}up++;upAt=sampledAt;upActivityFocused=activityFocused;upWebFocused=webFocused;}
    return true;
  }
  void forwarded(int action,boolean handled){
    if(action==MotionEvent.ACTION_DOWN){downForwarded=Math.min(8,downForwarded+1);downHandled=handled;}
    else if(action==MotionEvent.ACTION_UP){upForwarded=Math.min(8,upForwarded+1);upHandled=handled;}
  }
  JSONObject snapshot(){
    long now=SystemClock.elapsedRealtime();
    return J.obj("schema",1,"windowOnly",true,"preEmitOnly",true,"injectionFocusGuaranteed",false,"upIsDomClick",false,
        "originalBudgetMs",15000,"elapsedMs",Math.max(0,now-started),"remainingMs",Math.max(0,deadline-now),"lastSampleAgeMs",Math.max(0,now-sampledAt),"focusSampleCached",true,
        "polls",polls,"boundsRequests",boundsRequests,"boundsPending",boundsPending,"beforeBoundsReady",beforeBoundsReady,"afterBoundsReady",afterBoundsReady,
        "tapEmitted",tapEmitted,"retired",retired,"overflow",overflow,"activityFocused",activityFocused,"webFocused",webFocused,"webShown",webShown,"webAttached",webAttached,
        "surfaceFocused",surfaceFocused,"surfaceShown",surfaceShown,"surfaceAttached",surfaceAttached,"sameOwner",sameOwner,"sameSession",sameSession,"samePort",samePort,"sameDocument",sameDocument,
        "nativeDown",down,"nativeUp",up,"downForwarded",downForwarded,"upForwarded",upForwarded,"downHandled",downHandled,"upHandled",upHandled,
        "downActivityFocused",downActivityFocused,"downWebFocused",downWebFocused,"upActivityFocused",upActivityFocused,"upWebFocused",upWebFocused,
        "downDelayMs",downAt==0?0:Math.max(0,downAt-emittedAt),"upDelayMs",upAt==0?0:Math.max(0,upAt-emittedAt),
        "applicationAcceptance",false,"releaseAcceptance",false,"physicalPhoneAcceptance",false);
  }
}
