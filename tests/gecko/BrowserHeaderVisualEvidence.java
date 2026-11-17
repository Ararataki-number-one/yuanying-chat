package local.pocketchat;

import android.app.Activity;
import android.app.Application;
import android.graphics.Rect;
import android.graphics.RegionIterator;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.util.Log;
import android.view.View;
import android.view.ViewGroup;
import org.json.JSONArray;
import org.json.JSONObject;

/** Test-only reader of the live production header and its installed touch delegate. */
final class BrowserHeaderVisualEvidence implements Application.ActivityLifecycleCallbacks,Runnable {
  final Application application;final String nonce;final Handler handler=new Handler(Looper.getMainLooper());
  final long began=SystemClock.uptimeMillis();Activity activity;long resumedAt;boolean closed;
  BrowserHeaderVisualEvidence(Activity launcher,String nonce){
    if(!"local.pocketchat.test".equals(launcher.getPackageName())||nonce==null||!nonce.matches("[0-9a-f]{32}"))throw new IllegalArgumentException("Owned visual invocation required");
    application=launcher.getApplication();this.nonce=nonce;application.registerActivityLifecycleCallbacks(this);handler.postDelayed(this,100);
  }
  @Override public void onActivityResumed(Activity value){if(value instanceof MainActivity||value instanceof BrowserActivity){activity=value;resumedAt=SystemClock.uptimeMillis();}}
  @Override public void run(){
    if(closed)return;
    try{
      if(SystemClock.uptimeMillis()-began>12000)throw new IllegalStateException("Actual production header did not settle");
      if(activity==null||SystemClock.uptimeMillis()-resumedAt<1800||!activity.hasWindowFocus()){handler.postDelayed(this,100);return;}
      View host,top,network,environment,face,page;Rect toolbar;String engine;
      if(activity instanceof MainActivity){MainActivity a=(MainActivity)activity;if(a.designChrome==null||a.remote==null){handler.postDelayed(this,100);return;}
        host=a.toolbar;top=a.designChrome.top;network=a.designChrome.networkRow;environment=face=a.designChrome.title;page=a.remote;toolbar=screen(host);engine="gecko";
      }else{BrowserActivity a=(BrowserActivity)activity;if(a.root==null||a.environmentTouch==null||a.content==null){handler.postDelayed(this,100);return;}
        host=a.root;top=(View)a.environmentTouch.getParent();network=a.networkLine;environment=a.environmentTouch;face=a.environmentName;page=a.content;Rect root=screen(host),band=screen((View)network.getParent());toolbar=new Rect(root.left,screen(top).top,root.right,band.bottom);engine="chromium";
      }
      if(!host.isLaidOut()||host.isLayoutRequested()||!network.isShown()||network.isLayoutRequested()||!page.isLaidOut()||page.getHeight()==0){handler.postDelayed(this,100);return;}
      if(!(host.getTouchDelegate() instanceof BrowserHeaderTouchDelegate))throw new IllegalStateException("Production header has no installed shared touch delegate");
      BrowserHeaderTouchDelegate delegate=(BrowserHeaderTouchDelegate)host.getTouchDelegate();
      if(delegate.targets[0]!=environment||delegate.targets[1]!=network)throw new IllegalStateException("Native header delegate belongs to different views");
      Rect origin=screen(host),capsule=new Rect(delegate.bounds[0]),touch=new Rect(delegate.bounds[1]);capsule.offset(origin.left,origin.top);touch.offset(origin.left,origin.top);
      JSONArray regions=new JSONArray();RegionIterator iterator=new RegionIterator(delegate.region(1));Rect region=new Rect();while(iterator.next(region)){Rect measured=new Rect(region);measured.offset(origin.left,origin.top);regions.put(rect(measured));}
      double density=activity.getResources().getDisplayMetrics().density;
      JSONObject layout=J.obj("headerContract",5,"actualAndroidLayout",true,"density",density,"viewportDp",toolbar.width()/density,
        "toolbar",rect(toolbar),"topBounds",rect(screen(top)),"webBounds",rect(screen(page)),"networkInHeader",true,"networkShown",network.isShown(),
        "controls",J.arr(J.obj("name","environment","touch",rect(capsule),"visible",rect(screen(face)))),
        "networkMetrics",J.obj("bounds",rect(screen(network)),"touchBounds",rect(touch),"effectiveTouchRegions",regions,"clickable",network.isClickable(),"focusable",network.isFocusable()));
      JSONObject value=J.obj("schema",1,"headerContract",5,"status","observed","scene","chat","nonce",nonce,
        "sourceCommit",DownloadLocationLayoutEvidence.cleanSource(activity),"actualAndroidLayout",true,"engine",engine,
        "fontScale",activity.getResources().getConfiguration().fontScale,"density",density,
        "windowBounds",rect(android.os.Build.VERSION.SDK_INT>=30?activity.getWindowManager().getCurrentWindowMetrics().getBounds():screen(activity.getWindow().getDecorView())),"activityClass",activity.getClass().getName(),"activityIdentity",System.identityHashCode(activity),"delegateIdentity",System.identityHashCode(delegate),
        "windowFocused",activity.hasWindowFocus(),"layoutRequested",host.isLayoutRequested(),"capsuleAccessibilityBounds",rect(screen(environment)),
        "startedUptimeMs",began,"observedUptimeMs",SystemClock.uptimeMillis(),"layout",layout);
      String raw=value.toString();if(raw.getBytes(java.nio.charset.StandardCharsets.UTF_8).length>3500)throw new IllegalStateException("Header observation too large");
      close();Log.i("PocketBrowserHeader",raw);
    }catch(Exception error){close();Log.e("PocketBrowserHeader",J.obj("schema",1,"nonce",nonce,"status","failed","error",error.getClass().getSimpleName()).toString());}
  }
  static Rect screen(View view){int[] position=new int[2];view.getLocationOnScreen(position);return new Rect(position[0],position[1],position[0]+view.getWidth(),position[1]+view.getHeight());}
  static JSONArray rect(Rect value){return J.arr(value.left,value.top,value.right,value.bottom);}
  void close(){if(closed)return;closed=true;handler.removeCallbacks(this);application.unregisterActivityLifecycleCallbacks(this);}
  @Override public void onActivityCreated(Activity a,Bundle b){}
  @Override public void onActivityStarted(Activity a){}
  @Override public void onActivityPaused(Activity a){}
  @Override public void onActivityStopped(Activity a){}
  @Override public void onActivitySaveInstanceState(Activity a,Bundle b){}
  @Override public void onActivityDestroyed(Activity a){if(activity==a)activity=null;}
}
