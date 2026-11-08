package local.pocketchat;

import android.graphics.drawable.Drawable;
import android.graphics.drawable.InsetDrawable;
import android.graphics.drawable.LayerDrawable;
import android.view.View;
import android.view.ViewGroup;
import java.util.Collections;
import java.util.Set;
import java.util.WeakHashMap;

/** Native drawable feedback; the glass moves while its host and hit region stay fixed. */
final class GlassMotion {
  private static final Set<View> hosts=Collections.newSetFromMap(new WeakHashMap<>());
  private GlassMotion(){}

  /** Preserve the chrome's existing binding API; both shapes use the same material. */
  static void press(View view,boolean reading){
    if(materialBackground(view)==null||!hosts.add(view))return;
    view.setStateListAnimator(null);
    view.addOnAttachStateChangeListener(new View.OnAttachStateChangeListener(){
      @Override public void onViewAttachedToWindow(View v){
        Drawable background=materialBackground(v);if(background==null)return;
        background.setVisible(v.isShown()&&v.getWindowVisibility()==View.VISIBLE,false);
        background.jumpToCurrentState();
      }
      @Override public void onViewDetachedFromWindow(View v){
        Drawable background=materialBackground(v);if(background==null)return;
        background.setVisible(false,false);background.jumpToCurrentState();
      }
    });
    reset(view);
  }

  /** Only a material background is affected; ordinary form buttons are untouched. */
  static void reset(View view){
    Drawable background=materialBackground(view);
    if(background!=null)background.jumpToCurrentState();
  }

  /** Merge child press state without calling ViewGroup.setPressed on siblings. */
  static int[] childState(ViewGroup surface,int[] states){
    boolean bound=false,enabled=false,pressed=false;
    for(int i=0;i<surface.getChildCount();i++){
      View child=surface.getChildAt(i);
      if(!(child instanceof DesignUi.ActionButton)||!((DesignUi.ActionButton)child).hasPressedSurface(surface))continue;
      bound=true;
      if(child.getVisibility()!=View.VISIBLE||!child.isEnabled())continue;
      enabled=true;pressed|=child.isPressed();
    }
    if(!bound)return states;
    enabled&=surface.isEnabled();
    int count=0;
    for(int state:states){
      if(state==0||state==android.R.attr.state_pressed||state==android.R.attr.state_enabled&&!enabled)continue;
      states[count++]=state;
    }
    if(enabled&&pressed)states[count++]=android.R.attr.state_pressed;
    while(count<states.length)states[count++]=0;
    return states;
  }

  private static Drawable materialBackground(View view){
    Drawable background=view==null?null:view.getBackground();
    return hasMaterial(background)?background:null;
  }

  private static boolean hasMaterial(Drawable drawable){
    if(drawable instanceof LiquidGlassDrawable)return true;
    if(drawable instanceof LayerDrawable){
      LayerDrawable layers=(LayerDrawable)drawable;
      for(int i=0;i<layers.getNumberOfLayers();i++)if(hasMaterial(layers.getDrawable(i)))return true;
    }else if(drawable instanceof InsetDrawable)return hasMaterial(((InsetDrawable)drawable).getDrawable());
    return false;
  }
}
