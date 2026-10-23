package local.pocketchat;

import android.content.*;
import android.app.Activity;
import android.os.*;
import android.view.*;
import org.json.*;
import java.util.ArrayList;

/** Integration-only observations around the unchanged production MainActivity handlers.
 * The only browser substitution is the existing loopback URL/document-ready adapter.
 * No production timer, observer, connection, navigation or input handler is disabled.
 */
public final class ExperienceBenchmarkActivity extends MainActivity {
  static final String ACTION="local.pocketchat.test.EXPERIENCE_BENCHMARK";
  static final String TARGET=MainActivity.ORIGIN+"c/reload-collapse";
  static final String SNAPSHOT="(()=>{const e=document.getElementById('prompt-textarea'),r=document.getElementById('benchmark-reply');if(!window.__experienceRaf){const data=window.__experienceRaf={frames:0,sumMs:0,maxMs:0,over32:0,visibilityResets:0};let previous=0;document.addEventListener('visibilitychange',()=>{previous=0;data.visibilityResets++;});function frame(t){if(document.hidden){previous=0;}else{if(previous){const gap=t-previous;data.frames++;data.sumMs+=gap;data.maxMs=Math.max(data.maxMs,gap);if(gap>32)data.over32++;}previous=t;}requestAnimationFrame(frame);}requestAnimationFrame(frame);}const text=r?.textContent||'';let hash=2166136261;for(let i=0;i<text.length;i++)hash=Math.imul(hash^text.charCodeAt(i),16777619);return {ready:!!e&&!!r,document:document.documentElement.dataset.reloadDocument,draft:e?.value,cookie:document.cookie,replyFingerprint:{length:text.length,fnv32:hash>>>0},sendCount:Number(document.getElementById('send-count')?.textContent||0),path:location.pathname,theme:matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light',themeBackground:getComputedStyle(document.documentElement).backgroundColor,themeObservation:'fixture-css-prefers-color-scheme',documentHidden:document.hidden,raf:window.__experienceRaf};})()";
  final ArrayList<Double> choreographerGaps=new ArrayList<>();
  final ArrayList<Double> windowFrameMs=new ArrayList<>();
  final ArrayList<JSONObject> windowFrameRaw=new ArrayList<>();
  final java.util.HashMap<Window,Window.Callback> dialogCallbacks=new java.util.HashMap<>();
  final ArrayList<JSONObject> measurements=new ArrayList<>();
  final long createdAt=SystemClock.elapsedRealtimeNanos();
  IntegrationEventStore events;
  String nonce,armedName="",armedTarget="";
  long armedAt,inputDown,inputUp,lastFrame,drawAt;
  int choreographerStart,windowStart;
  boolean benchmarkReady,benchmarkClosed,completing;
  JSONObject initial;
  JSONObject buildIdentity;
  ViewTreeObserver.OnDrawListener drawListener;
  Window.OnFrameMetricsAvailableListener windowListener;
  final Choreographer.FrameCallback frameCallback=new Choreographer.FrameCallback(){
    @Override public void doFrame(long value){
      if(benchmarkClosed)return;
      if(active&&lastFrame>0&&choreographerGaps.size()<30000)choreographerGaps.add((value-lastFrame)/1000000.0);
      lastFrame=active?value:0;Choreographer.getInstance().postFrameCallback(this);
    }
  };
  final BroadcastReceiver control=new BroadcastReceiver(){@Override public void onReceive(Context c,Intent i){
    if(!nonce.equals(i.getStringExtra("eventNonce")))return;
    try{
      String command=i.getStringExtra("benchmarkCommand"),name=i.getStringExtra("sampleName");
      if(name==null||!name.matches("[A-Za-z0-9_-]{1,80}"))throw new IllegalArgumentException("Owned measurement name required");
      if("arm".equals(command))arm(name,i.getStringExtra("target"));
      else if("snapshot".equals(command))snapshot(name,null);
      else if("finish".equals(command))snapshot(name,()->handler.postDelayed(()->emit("finished",J.obj("samples",new JSONArray(measurements),"allNativeHwuiFrames",new JSONArray(windowFrameRaw),"allChoreographerGapsMs",new JSONArray(choreographerGaps),"scope",scope())),100));
      else throw new IllegalArgumentException("Unknown benchmark command");
    }catch(Exception failure){fail(failure);}
  }};

  @Override public void onCreate(Bundle state){
    if(!"local.pocketchat.test".equals(getPackageName()))throw new SecurityException("Integration package only");
    nonce=getIntent().getStringExtra("eventNonce");
    try{
      try(java.io.InputStream in=new java.io.FileInputStream(new java.io.File(Profiles.global(this).getFilesDir(),"experience-benchmark-identity.json"))){buildIdentity=new JSONObject(J.text(in,65536));}
      events=new IntegrationEventStore(this,0,nonce,"experienceBenchmark",1,buildIdentity);
      ChatSession.browserFactory=ChromeCollapseIntegration.CollapseView::new;
      super.onCreate(state);
      if(Build.VERSION.SDK_INT>=33)registerReceiver(control,new IntentFilter(ACTION),Context.RECEIVER_EXPORTED);else registerReceiver(control,new IntentFilter(ACTION));
      windowListener=(window,metrics,dropped)->{if(windowFrameMs.size()<30000){double duration=metrics.getMetric(FrameMetrics.TOTAL_DURATION)/1000000.0;windowFrameMs.add(duration);windowFrameRaw.add(J.obj("intendedVsyncUptimeMs",metrics.getMetric(FrameMetrics.INTENDED_VSYNC_TIMESTAMP)/1000000.0,"durationMs",duration,"droppedReports",dropped));}};
      getWindow().addOnFrameMetricsAvailableListener(windowListener,handler);
      drawListener=()->{if(!armedName.isEmpty()&&inputUp>0&&!completing&&targetVisible()){drawAt=SystemClock.uptimeMillis();completing=true;handler.post(this::complete);}};
      getWindow().getDecorView().getViewTreeObserver().addOnDrawListener(drawListener);
      Choreographer.getInstance().postFrameCallback(frameCallback);
      waitReady(SystemClock.elapsedRealtime()+45000);
    }catch(Exception failure){fail(failure);}
  }
  String scope(){return "Actual production MainActivity/AppHub and Gecko with an integration-only localhost URL/document-ready adapter. Normal production timers and observers remain enabled. Native response ends at a View draw callback, not compositor presentation. Choreographer gaps and HWUI frame durations are descriptive; Gecko compositor is not represented by HWUI alone. Fixture theme observes actual Gecko color preference through CSS media query, not the ChatGPT-only appearance bridge. Static replies do not exercise ChatGPT-origin-only reply/resource event forwarding. No real account, physical-phone, vendor-IME or WAN latency acceptance.";}
  void waitReady(long deadline){
    if(benchmarkClosed)return;
    remote.evaluateJavascript(SNAPSHOT,raw->{
      try{
        JSONObject value=J.parse(raw);
        if(!value.optBoolean("ready")||!remote.hasVisibleDocument()||loading.cover.getVisibility()!=View.GONE||session.navigating){
          if(SystemClock.elapsedRealtime()>deadline)throw new IllegalStateException("Normal production page readiness timeout: "+J.obj("snapshot",value,"visibleDocument",remote.hasVisibleDocument(),"loading",loading.cover.getVisibility(),"navigating",session.navigating,"status",session.status));
          handler.postDelayed(()->waitReady(deadline),100);return;
        }
        initial=value;benchmarkReady=true;double observedReadyMs=(SystemClock.elapsedRealtimeNanos()-createdAt)/1000000.0;
        snapshot("ready",()->emit("ready",J.obj("activityCreateToReadyMs",observedReadyMs,
          "productionPageUsableFromActivityCreateMs",session.pageUsableAt>0?session.pageUsableAt-createdAt/1000000.0:JSONObject.NULL,
          "readinessObservation","Production ready state observed through a 100 ms bounded probe; provisioning/hash excluded", "buildIdentity",buildIdentity,"scope",scope())));
      }catch(Exception failure){fail(failure);}
    });
  }
  void arm(String name,String target){
    if(!benchmarkReady||!armedName.isEmpty())throw new IllegalStateException("Benchmark is not idle");
    if(target==null||!target.matches("chat|network|settings|downloads|expanded|collapsed|dark|light|resume"))throw new IllegalArgumentException("Unknown target");
    armedName=name;armedTarget=target;armedAt=SystemClock.uptimeMillis();inputDown=inputUp=drawAt=0;completing=false;
    choreographerStart=choreographerGaps.size();windowStart=windowFrameMs.size();
    if("dark".equals(target)||"light".equals(target))observeDialogTouch();
    emit("armed",J.obj("name",name,"target",target));
    handler.postDelayed(()->{if(name.equals(armedName))fail(new IllegalStateException("Measured action timed out: "+name));},15000);
  }
  @Override public boolean dispatchTouchEvent(MotionEvent event){
    observeTouch(event);
    return super.dispatchTouchEvent(event);
  }
  void observeTouch(MotionEvent event){
    if(!armedName.isEmpty()){
      if(event.getActionMasked()==MotionEvent.ACTION_DOWN&&inputDown==0)inputDown=event.getEventTime();
      if(event.getActionMasked()==MotionEvent.ACTION_UP&&inputUp==0)inputUp=event.getEventTime();
    }
  }
  void observeDialogTouch(){try{
    java.lang.reflect.Field field=AppAppearance.class.getDeclaredField("dialogs");field.setAccessible(true);
    for(Object value:new ArrayList<>((java.util.Set<?>)field.get(null))){android.app.Dialog dialog=(android.app.Dialog)value;if(!dialog.isShowing())continue;
      Window window=dialog.getWindow();Window.Callback original=window.getCallback();dialogCallbacks.put(window,original);
      window.setCallback((Window.Callback)java.lang.reflect.Proxy.newProxyInstance(Window.Callback.class.getClassLoader(),new Class<?>[]{Window.Callback.class},(proxy,method,args)->{
        if("dispatchTouchEvent".equals(method.getName())&&args!=null&&args.length==1)observeTouch((MotionEvent)args[0]);
        try{return method.invoke(original,args);}catch(java.lang.reflect.InvocationTargetException failure){throw failure.getCause();}
      }));
    }
    if(dialogCallbacks.isEmpty())throw new IllegalStateException("No visible appearance dialog");
  }catch(ReflectiveOperationException failure){throw new IllegalStateException("Visible appearance dialog observation unavailable",failure);}}
  void restoreDialogCallbacks(){for(java.util.Map.Entry<Window,Window.Callback> entry:dialogCallbacks.entrySet())entry.getKey().setCallback(entry.getValue());dialogCallbacks.clear();}
  @Override protected void onResume(){if("resume".equals(armedTarget)&&!armedName.isEmpty()){inputDown=inputUp=SystemClock.uptimeMillis();}super.onResume();lastFrame=0;Choreographer.getInstance().removeFrameCallback(frameCallback);Choreographer.getInstance().postFrameCallback(frameCallback);}
  @Override protected void onPause(){lastFrame=0;Choreographer.getInstance().removeFrameCallback(frameCallback);super.onPause();}
  boolean targetVisible(){
    if(hub==null)return false;
    switch(armedTarget){
      case "chat":case "resume":return hub.page==AppHub.CHAT&&remote.isShown()&&remote.hasVisibleDocument()&&loading.cover.getVisibility()==View.GONE;
      case "network":return hub.page==AppHub.NETWORK&&hub.networkWorkspace.catalog!=null&&!hub.networkWorkspace.reading&&hub.networkWorkspace.windows.length()>0&&hub.networkWorkspace.box.getHeight()>0;
      case "settings":return hub.page==AppHub.SETTINGS&&hub.panel.getChildCount()>0&&hub.panel.getChildAt(0).getHeight()>0;
      case "downloads":return hub.page==AppHub.DOWNLOADS&&hub.downloadScreen!=null&&hub.downloadScreen.getHeight()>0;
      case "expanded":return designChrome.expanded()&&designChrome.top.getVisibility()==View.VISIBLE&&designChrome.top.getHeight()>0;
      case "collapsed":return !designChrome.expanded()&&designChrome.compact.getVisibility()==View.VISIBLE&&designChrome.compact.getHeight()>0;
      case "dark":case "light":return armedTarget.equals(AppAppearance.mode());
      default:return false;
    }
  }
  void complete(){
    if(armedName.isEmpty())return;
    JSONObject measured=J.obj("name",armedName,"target",armedTarget,"responseToDrawMs",drawAt-inputUp,"inputDurationMs",inputUp-inputDown,
      "inputUpUptimeMs",inputUp,"drawUptimeMs",drawAt,"observedAtUptimeMs",SystemClock.uptimeMillis(),
      "choreographerGapsMs",slice(choreographerGaps,choreographerStart),"nativeHwuiFrameMs",slice(windowFrameMs,windowStart),
      "start","actual Android ACTION_UP (resume uses onResume)","end","first actual MainActivity view draw satisfying the destination predicate");
    measurements.add(measured);String name=armedName;armedName="";armedTarget="";completing=false;
    restoreDialogCallbacks();
    emit("measurement",measured);snapshot(name,null);
  }
  JSONArray slice(ArrayList<Double> values,int start){JSONArray result=new JSONArray();for(int i=start;i<values.size();i++)result.put(values.get(i));return result;}
  JSONArray center(View v){int[] p=new int[2];v.getLocationOnScreen(p);return J.arr(p[0]+v.getWidth()/2,p[1]+v.getHeight()/2);}
  void snapshot(String name,Runnable done){snapshot(name,done,SystemClock.uptimeMillis()+3000);}
  void snapshot(String name,Runnable done,long deadline){
    remote.evaluateJavascript(SNAPSHOT,raw->{
      try{
        JSONObject page=J.parse(raw);if(!page.optBoolean("ready"))throw new IllegalStateException("Controlled document unavailable");
        String expectedTheme="theme-dark".equals(name)?"dark":"theme-light".equals(name)?"light":"";
        String expectedBackground="dark".equals(expectedTheme)?"rgb(16, 16, 16)":"rgb(255, 255, 255)";
        if(!expectedTheme.isEmpty()&&(!expectedTheme.equals(page.optString("theme"))||!expectedBackground.equals(page.optString("themeBackground")))){if(SystemClock.uptimeMillis()>=deadline)throw new IllegalStateException("Fixture CSS color preference did not follow the actual native selection");handler.postDelayed(()->snapshot(name,done,deadline),20);return;}
        if(initial!=null)for(String key:new String[]{"document","draft","cookie","replyFingerprint","sendCount","path"})
          if(!String.valueOf(initial.opt(key)).equals(String.valueOf(page.opt(key))))throw new IllegalStateException("Page preservation failed: "+key);
        JSONObject points=J.obj("chat",center(hub.tabs[0]),"downloads",center(hub.tabs[2]),"network",center(hub.tabs[3]),"settings",center(hub.tabs[4]),"compact",center(designChrome.compact));
        int[] p=new int[2];remote.getLocationOnScreen(p);
        points.put("swipeFrom",J.arr(p[0]+remote.getWidth()/2,p[1]+remote.getHeight()*3/4));
        points.put("swipeTo",J.arr(p[0]+remote.getWidth()/2,p[1]+remote.getHeight()/4));
        JSONObject value=J.obj("name",name,"page",page,"points",points,"hubPage",hub.page,"expanded",designChrome.expanded(),"mode",AppAppearance.mode(),
          "surface",System.identityHashCode(remote.surface),"session",System.identityHashCode(remote.current),"attachedSession",System.identityHashCode(remote.surface.getSession()),
          "visibleDocument",remote.hasVisibleDocument(),"networkReady",session.networkReady,"loadingVisibility",loading.cover.getVisibility(),
          "productionObserverCount",session.observers.size(),"scope",scope());
        if(!expectedTheme.isEmpty())for(JSONObject measured:measurements)if(name.equals(measured.optString("name")))value.put("webThemeResponseUpperBoundMs",SystemClock.uptimeMillis()-measured.getLong("inputUpUptimeMs"));
        emit("snapshot",value);if(done!=null)done.run();
      }catch(Exception failure){fail(failure);}
    });
  }
  void emit(String kind,JSONObject value){try{if(events!=null)events.emit(kind,value);}catch(Exception failure){events.failure(failure);}}
  void fail(Exception failure){if(benchmarkClosed)return;emit("error",J.obj("error",failure.toString()));benchmarkClosed=true;}
  @Override protected void onDestroy(){benchmarkClosed=true;try{unregisterReceiver(control);}catch(IllegalArgumentException ignored){}
    restoreDialogCallbacks();
    Choreographer.getInstance().removeFrameCallback(frameCallback);if(windowListener!=null)getWindow().removeOnFrameMetricsAvailableListener(windowListener);
    if(drawListener!=null&&getWindow().getDecorView().getViewTreeObserver().isAlive())getWindow().getDecorView().getViewTreeObserver().removeOnDrawListener(drawListener);super.onDestroy();}

  /** Provisioning and complete installed-APK hashing happen before every timed launch. */
  public static final class Seed extends Activity {
    @Override protected void attachBaseContext(Context base){super.attachBaseContext(new ProfileContext(base,0));}
    @Override public void onCreate(Bundle state){super.onCreate(state);
      if(!"local.pocketchat.test".equals(getPackageName()))throw new SecurityException("Integration package only");
      try{
        ProfileCatalog.get(this).created(0);Profiles.rename(this,0,"体验测量环境");
        getSharedPreferences("chat",0).edit().putString("networkMode","external").putString("proxy","socks://127.0.0.1:1080")
          .putBoolean("requireExternalVpn",false).putBoolean("networkConfigured",true).putBoolean("environmentInitialized",true)
          .putBoolean("pageMode",true).putString("conversation",TARGET).putString("url",TARGET).commit();
        AppSettings.put(this,"brandSeen","true");AppSettings.put(this,"updateAutoCheck","false");AppSettings.put(this,AppAppearance.KEY,"light");AppAppearance.refresh(this);
        JSONObject identity=IntegrationBuildIdentity.read(Profiles.global(this));
        J.write(new java.io.File(Profiles.global(this).getFilesDir(),"experience-benchmark-identity.json"),identity.toString());
        new IntegrationEventStore(this,0,getIntent().getStringExtra("eventNonce"),"experienceSeed",1,identity).emit("seeded",J.obj("status","passed","timed",false));
        finish();
      }catch(Exception failure){throw new IllegalStateException("Untimed benchmark provisioning failed",failure);}
    }
  }
}
