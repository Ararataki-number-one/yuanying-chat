package local.pocketchat;

import android.animation.ValueAnimator;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.InsetDrawable;
import android.graphics.drawable.LayerDrawable;
import android.os.SystemClock;
import android.util.Log;
import android.view.View;
import android.view.ViewGroup;
import android.view.ViewTreeObserver;
import android.widget.TextView;
import java.lang.reflect.Field;
import java.util.ArrayList;
import java.util.IdentityHashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.json.JSONArray;
import org.json.JSONObject;

/** Test-only attribution after a measured idle gate has already failed. */
final class ChromeIdleDrawObservation {
  static final int MAX_VIEWS=320,MAX_CALLBACKS=160,MAX_FRAMES=16,MAX_STACKS=12,MAX_COUNTS=96;
  final MainActivity a;
  final JSONObject identity;
  final String nonce,request,phase;
  final List<View> views=new ArrayList<>();
  final List<ForwardingCallback> callbacks=new ArrayList<>();
  final IdentityHashMap<Drawable,Boolean> instrumented=new IdentityHashMap<>();
  final List<JSONObject> frames=new ArrayList<>(),stacks=new ArrayList<>();
  final Map<String,Integer> counts=new LinkedHashMap<>();
  final Map<String,Boolean> stackKeys=new LinkedHashMap<>();
  boolean active,previousPerf;
  long started;
  int preDraws,draws,droppedFrames,droppedStacks,droppedCounts,sequence;
  final Runnable expiry=()->stop("deadline");
  ViewTreeObserver observer;
  final ViewTreeObserver.OnPreDrawListener preDraw=()->{sampleFrame();return true;};
  final ViewTreeObserver.OnDrawListener onDraw=()->{if(active)draws++;};
  JSONObject initialPerf,initialState;

  ChromeIdleDrawObservation(MainActivity activity,JSONObject build,String nonce,String request,String phase){
    a=activity;identity=build;this.nonce=nonce;this.request=request;this.phase=phase;
  }

  void start(){
    if(active||!"local.pocketchat.test".equals(a.getPackageName()))return;
    active=true;started=SystemClock.elapsedRealtime();previousPerf=UiPerfStats.enabled;
    initialPerf=perf();UiPerfStats.enabled=true;
    try{
      collect(a.getWindow().getDecorView());
      observer=a.getWindow().getDecorView().getViewTreeObserver();
      observer.addOnPreDrawListener(preDraw);observer.addOnDrawListener(onDraw);
      initialState=state();
      emit("start",J.obj("elapsedMs",started,"views",views.size(),"callbacks",callbacks.size(),
        "maximumDurationMs",4000,"state",initialState));
      // This bounds observation/cleanup only. It never requests a frame or
      // changes any production timer, drawable state, input or rendering flag.
      a.handler.postDelayed(expiry,4000);
    }catch(Throwable failure){stop("start-failed-"+failure.getClass().getSimpleName());}
  }

  private void collect(View view){
    if(view==null||views.size()>=MAX_VIEWS)return;
    views.add(view);wrap(view.getBackground(),view,"background");
    if(view instanceof TextView){Drawable[] icons=((TextView)view).getCompoundDrawables();
      for(int i=0;i<icons.length;i++)wrap(icons[i],view,"compound"+i);}
    if(view instanceof ViewGroup){ViewGroup group=(ViewGroup)view;
      for(int i=0;i<group.getChildCount()&&views.size()<MAX_VIEWS;i++)collect(group.getChildAt(i));}
  }

  private void wrap(Drawable drawable,View view,String kind){
    if(drawable==null||callbacks.size()>=MAX_CALLBACKS||instrumented.containsKey(drawable))return;
    Drawable.Callback original=drawable.getCallback();if(original==null)return;
    instrumented.put(drawable,true);ForwardingCallback wrapper=new ForwardingCallback(drawable,original,view,kind);
    callbacks.add(wrapper);drawable.setCallback(wrapper);
  }

  private final class ForwardingCallback implements Drawable.Callback {
    final Drawable drawable;final Drawable.Callback original;final View view;final String kind;
    ForwardingCallback(Drawable drawable,Drawable.Callback original,View view,String kind){
      this.drawable=drawable;this.original=original;this.view=view;this.kind=kind;}
    @Override public void invalidateDrawable(Drawable who){
      note("drawable-invalidate-"+kind,view,0);original.invalidateDrawable(who);
    }
    @Override public void scheduleDrawable(Drawable who,Runnable what,long when){
      note("drawable-schedule-"+kind,view,when);original.scheduleDrawable(who,what,when);
    }
    @Override public void unscheduleDrawable(Drawable who,Runnable what){
      note("drawable-unschedule-"+kind,view,0);original.unscheduleDrawable(who,what);
    }
  }

  /** The fixture's Gecko container forwards the original invalidation unchanged. */
  void note(String kind,View view,long when){
    if(!active)return;
    try{
      String key=kind+":"+role(view);
      if(!counts.containsKey(key)&&counts.size()>=MAX_COUNTS){droppedCounts++;return;}
      counts.put(key,counts.getOrDefault(key,0)+1);
      if(stackKeys.containsKey(key))return;
      if(stacks.size()>=MAX_STACKS){droppedStacks++;return;}
      stackKeys.put(key,true);JSONArray trace=new JSONArray();StackTraceElement[] all=new Throwable().getStackTrace();
      for(int i=1;i<Math.min(all.length,11);i++)trace.put(all[i].toString());
      stacks.add(J.obj("elapsedMs",SystemClock.elapsedRealtime(),"kind",kind,"view",viewState(view),
        "scheduledUptimeMs",when,"stack",trace));
    }catch(Throwable ignored){/* Observation must not intercept the original callback. */}
  }

  private void sampleFrame(){
    if(!active)return;preDraws++;
    try{
      if(frames.size()>=MAX_FRAMES){droppedFrames++;return;}
      JSONArray dirty=new JSONArray(),animations=new JSONArray();int dirtyCount=0,layoutCount=0;
      for(View view:views){
        if(view.isDirty())dirtyCount++;if(view.isLayoutRequested())layoutCount++;
        if((view.isDirty()||view.isLayoutRequested())&&dirty.length()<6)dirty.put(viewState(view));
        material(view.getBackground(),view,animations);
      }
      frames.add(J.obj("elapsedMs",SystemClock.elapsedRealtime(),"dirtyViews",dirtyCount,"layoutViews",layoutCount,
        "dirtySample",dirty,"activeGlassAnimations",animations,"state",state()));
    }catch(Throwable failure){frames.add(J.obj("observationError",failure.getClass().getName()));}
  }

  private void material(Drawable drawable,View view,JSONArray output){
    if(drawable==null||output.length()>=4)return;
    if(drawable instanceof LiquidGlassDrawable){
      Object value=field(drawable,"animation");
      if(value instanceof ValueAnimator){ValueAnimator animation=(ValueAnimator)value;
        output.put(J.obj("view",role(view),"shown",view.isShown(),"drawableVisible",drawable.isVisible(),
          "running",animation.isRunning(),"started",animation.isStarted(),"durationMs",animation.getDuration(),
          "playTimeMs",animation.getCurrentPlayTime(),"pressed",field(drawable,"pressed"),
          "strength",field(drawable,"strength"),"bend",field(drawable,"bend")));}
    }else if(drawable instanceof LayerDrawable){LayerDrawable layers=(LayerDrawable)drawable;
      for(int i=0;i<layers.getNumberOfLayers();i++)material(layers.getDrawable(i),view,output);
    }else if(drawable instanceof InsetDrawable)material(((InsetDrawable)drawable).getDrawable(),view,output);
  }

  private JSONObject state(){
    return J.obj("toolbarShown",a.toolbar!=null&&a.toolbar.isShown(),"dockShown",a.hub!=null&&a.hub.bar.isShown(),
      "readingRequested",a.focusReading,"focusExitShown",a.focusExit!=null&&a.focusExit.isShown(),
      "tickerQueued",a.handler.hasCallbacks(a.ticker),"sessionTickQueued",a.session!=null&&a.session.handler.hasCallbacks(a.session.tick),
      "presentationQueued",a.sessionUi!=null&&a.sessionUi.pending!=null,
      "chromeRenderQueued",field(a.designChrome,"queued"),"activityActive",a.active);
  }

  private JSONObject viewState(View view){return view==null?new JSONObject():J.obj("role",role(view),
    "class",view.getClass().getSimpleName(),"shown",view.isShown(),"dirty",view.isDirty(),
    "layoutRequested",view.isLayoutRequested(),"focused",view.isFocused());}

  private String role(View view){
    if(view==null)return "none";
    if(view==a.toolbar)return "toolbar";if(view==a.remote)return "gecko-container";
    if(a.remote!=null&&view==a.remote.surface)return "gecko-surface";
    if(view==a.focusExit)return "reading-exit";if(a.hub!=null&&view==a.hub.bar)return "dock";
    if(a.geckoAddress!=null){GeckoAddressUi ui=a.geckoAddress;
      if(view==ui.row)return "browser-row";if(view==ui.address)return "browser-address";
      if(view==ui.back)return "browser-back";if(view==ui.forward)return "browser-forward";
      if(view==ui.reload)return "browser-reload";if(view==ui.home)return "browser-home";}
    return view.getClass().getSimpleName()+"#"+Integer.toHexString(System.identityHashCode(view));
  }

  private static Object field(Object target,String name){
    if(target==null)return JSONObject.NULL;
    try{Class<?> type=target.getClass();while(type!=null){try{Field f=type.getDeclaredField(name);f.setAccessible(true);
      Object value=f.get(target);return value==null?JSONObject.NULL:value;}catch(NoSuchFieldException missing){type=type.getSuperclass();}}}
    catch(ReflectiveOperationException|RuntimeException ignored){}
    return JSONObject.NULL;
  }

  private static JSONObject perf(){
    JSONObject raw=UiPerfStats.snapshot();
    return J.obj("mainSealedReads",raw.optLong("mainSealedReads"),"mainSealedWrites",raw.optLong("mainSealedWrites"),
      "mainCatalogReads",raw.optLong("mainCatalogReads"),"mainHeartbeatWrites",raw.optLong("mainHeartbeatWrites"),
      "chromeUpdates",raw.optLong("chromeUpdates"),"chromeTextChanges",raw.optLong("chromeTextChanges"),
      "chromeBackgroundChanges",raw.optLong("chromeBackgroundChanges"),"metricsRefreshes",raw.optLong("metricsRefreshes"),
      "starDraws",raw.optLong("starDraws"));
  }

  void stop(String reason){
    if(!active)return;active=false;
    JSONObject finalPerf=new JSONObject(),finalState=new JSONObject();int restored=0,changed=0,restoreErrors=0;
    try{
      finalPerf=perf();finalState=state();
    }catch(Throwable failure){finalState=J.obj("observationError",failure.getClass().getName());
    }finally{
      a.handler.removeCallbacks(expiry);
      if(observer!=null&&observer.isAlive()){
        try{observer.removeOnPreDrawListener(preDraw);}catch(RuntimeException ignored){}
        try{observer.removeOnDrawListener(onDraw);}catch(RuntimeException ignored){}
      }
      // Restore the exact prior callback; do not overwrite a legitimate new
      // callback installed by a production background replacement/detachment.
      for(ForwardingCallback wrapper:callbacks)try{
        if(wrapper.drawable.getCallback()==wrapper){wrapper.drawable.setCallback(wrapper.original);
          if(wrapper.drawable.getCallback()==wrapper.original)restored++;else restoreErrors++;}
        else changed++;
      }catch(Throwable failure){restoreErrors++;}
      UiPerfStats.enabled=previousPerf;
    }
    for(JSONObject frame:frames)emit("frame",frame);
    for(JSONObject stack:stacks)emit("stack",stack);
    for(Map.Entry<String,Integer> count:counts.entrySet())emit("count",J.obj("key",count.getKey(),"count",count.getValue()));
    emit("end",J.obj("reason",reason,"startedElapsedMs",started,"completedElapsedMs",SystemClock.elapsedRealtime(),
      "preDraws",preDraws,"draws",draws,"droppedFrames",droppedFrames,"droppedStacks",droppedStacks,"droppedCounts",droppedCounts,
      "callbacksInstalled",callbacks.size(),"callbacksRestored",restored,"callbacksChangedByOwner",changed,
      "callbackRestoreErrors",restoreErrors,"priorPerfEnabled",previousPerf,"perfEnabledRestored",UiPerfStats.enabled==previousPerf,
      "initialPerf",initialPerf,"finalPerf",finalPerf,"state",finalState));
  }

  private void emit(String kind,JSONObject data){
    JSONObject value=J.obj("schema",1,"kind",kind,"sequence",++sequence,"sourceCommit",identity.optString("sourceCommit"),
      "sourceTree",identity.optString("sourceTree"),"apkSha256",identity.optString("apkSha256"),"runNonce",nonce,
      "request",request,"phase",phase,"diagnosticOnly",true,"applicationAcceptance",false,"data",data);
    String raw=value.toString();
    if(raw.getBytes(java.nio.charset.StandardCharsets.UTF_8).length>3500){
      value=J.obj("schema",1,"kind","record-too-large","request",request,"runNonce",nonce,"originalKind",kind,"diagnosticOnly",true);
      raw=value.toString();
    }
    Log.i("PocketIdleDraw",raw);
  }
}
