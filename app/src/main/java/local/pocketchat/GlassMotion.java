package local.pocketchat;

import android.animation.ObjectAnimator;
import android.animation.PropertyValuesHolder;
import android.animation.StateListAnimator;
import android.animation.TimeInterpolator;
import android.view.View;
import android.view.animation.DecelerateInterpolator;
import android.view.animation.OvershootInterpolator;

/** Finite native press feedback; click, long-press and touch dispatch stay with the view. */
final class GlassMotion {
  private static final class PressStates extends StateListAnimator {}
  private GlassMotion(){}

  /** Install once when constructing a glass control or its visual surface. */
  static void press(View view,boolean reading){
    StateListAnimator motion=new PressStates();
    motion.addState(new int[]{android.R.attr.state_enabled,android.R.attr.state_pressed},
      transform(view,reading?.94f:.98f,reading?1.5f:0f,100,new DecelerateInterpolator(1.5f)));
    motion.addState(new int[]{android.R.attr.state_enabled},
      transform(view,1f,0f,reading?260:240,new OvershootInterpolator(1.5f)));
    motion.addState(new int[]{},transform(view,1f,0f,0,new DecelerateInterpolator()));
    view.addOnAttachStateChangeListener(new View.OnAttachStateChangeListener(){
      @Override public void onViewAttachedToWindow(View v){install(v,motion);}
      @Override public void onViewDetachedFromWindow(View v){
        // Finishing a pressed animator alone would leave its compressed endpoint.
        if(v.getStateListAnimator()==motion)v.setStateListAnimator(null);
        restore(v);
      }
    });
    install(view,motion);
  }

  private static ObjectAnimator transform(View view,float scale,float rotation,long duration,TimeInterpolator curve){
    // A single endpoint makes each interrupted state start at the current values.
    ObjectAnimator animator=ObjectAnimator.ofPropertyValuesHolder(view,
      PropertyValuesHolder.ofFloat(View.SCALE_X,scale),
      PropertyValuesHolder.ofFloat(View.SCALE_Y,scale),
      PropertyValuesHolder.ofFloat(View.ROTATION,rotation));
    animator.setDuration(duration);animator.setInterpolator(curve);
    // Native animators also honor the system's zero-duration animation setting.
    return animator;
  }

  private static void install(View view,StateListAnimator motion){
    view.setStateListAnimator(motion);
    reset(view);
  }

  /** Settle an outgoing surface immediately when its owner hides it. */
  static void reset(View view){
    StateListAnimator motion=view.getStateListAnimator();
    if(!(motion instanceof PressStates))return;
    motion.jumpToCurrentState();
    restore(view);
  }

  private static void restore(View view){
    view.setScaleX(1f);view.setScaleY(1f);view.setRotation(0f);
  }
}
