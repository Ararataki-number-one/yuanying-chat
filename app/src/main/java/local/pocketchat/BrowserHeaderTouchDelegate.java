package local.pocketchat;

import android.annotation.TargetApi;
import android.graphics.Rect;
import android.graphics.Region;
import android.view.MotionEvent;
import android.view.TouchDelegate;
import android.view.View;
import android.view.ViewGroup;
import android.view.accessibility.AccessibilityNodeInfo;
import java.util.LinkedHashMap;
import java.util.Map;

/** Shares unused header space without letting network taps steal capsule taps. */
final class BrowserHeaderTouchDelegate extends TouchDelegate {
  final View[] targets;
  final Rect[] bounds;
  private final int[][] pixels;
  private final TouchDelegate[] delegates;
  private TouchDelegate active;

  BrowserHeaderTouchDelegate(View environment,View network,Rect environmentBounds,Rect networkBounds){
    super(new Rect(),environment);
    targets=new View[]{environment,network};bounds=new Rect[]{new Rect(environmentBounds),new Rect(networkBounds)};
    pixels=new int[][]{array(bounds[0]),array(bounds[1])};
    delegates=new TouchDelegate[]{new TouchDelegate(bounds[0],environment),new TouchDelegate(bounds[1],network)};
  }

  @Override public boolean onTouchEvent(MotionEvent event){
    int action=event.getActionMasked();
    if(action==MotionEvent.ACTION_DOWN){
      int target=BrowserHeaderLayout.targetAt(pixels[0],pixels[1],(int)event.getX(),(int)event.getY());
      active=target<0?null:delegates[target];
    }
    boolean handled=active!=null&&active.onTouchEvent(event);
    if(action==MotionEvent.ACTION_UP||action==MotionEvent.ACTION_CANCEL)active=null;
    return handled;
  }

  Region region(int index){
    Region value=new Region(bounds[index]);
    if(index==1)value.op(bounds[0],Region.Op.DIFFERENCE);
    return value;
  }

  @TargetApi(29)
  @Override public AccessibilityNodeInfo.TouchDelegateInfo getTouchDelegateInfo(){
    Map<Region,View> regions=new LinkedHashMap<>();
    for(int i=0;i<targets.length;i++)if(!bounds[i].isEmpty())regions.put(region(i),targets[i]);
    return new AccessibilityNodeInfo.TouchDelegateInfo(regions);
  }

  static Rect networkBounds(Rect visible,int headerTop,int minimum){
    int[] value=BrowserHeaderLayout.networkTouch(visible.left,visible.top,visible.right,visible.bottom,headerTop,minimum);
    return new Rect(value[0],value[1],value[2],value[3]);
  }

  /** Chromium has no existing header delegate; the Gecko header owns its own. */
  static void bind(ViewGroup root,View environment,View network){
    Runnable update=()->{
      if(!environment.isShown()||!network.isShown()||environment.getWidth()==0||network.getWidth()==0){root.setTouchDelegate(null);return;}
      Rect capsule=relativeBounds(root,environment),strip=relativeBounds(root,network);
      root.setTouchDelegate(new BrowserHeaderTouchDelegate(environment,network,capsule,
        networkBounds(strip,capsule.top,ReferenceUi.dp(root.getContext(),48))));
    };
    View.OnLayoutChangeListener layout=(v,l,t,r,b,ol,ot,or,ob)->update.run();
    root.addOnLayoutChangeListener(layout);environment.addOnLayoutChangeListener(layout);network.addOnLayoutChangeListener(layout);
    root.post(update);
  }

  private static Rect relativeBounds(View root,View child){
    int[] origin=new int[2],position=new int[2];root.getLocationOnScreen(origin);child.getLocationOnScreen(position);
    return new Rect(position[0]-origin[0],position[1]-origin[1],position[0]-origin[0]+child.getWidth(),position[1]-origin[1]+child.getHeight());
  }
  private static int[] array(Rect rect){return new int[]{rect.left,rect.top,rect.right,rect.bottom};}
}
