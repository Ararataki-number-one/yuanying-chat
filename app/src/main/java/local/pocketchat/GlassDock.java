package local.pocketchat;

import android.animation.Animator;
import android.animation.AnimatorListenerAdapter;
import android.animation.ValueAnimator;
import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.RectF;
import android.view.Gravity;
import android.view.View;
import android.view.animation.PathInterpolator;
import android.widget.LinearLayout;

/** One selection wash underneath the native destination buttons. */
final class GlassDock extends LinearLayout {
  private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
  private final RectF highlight=new RectF(),target=new RectF(),origin=new RectF();
  private final int inset;
  private final float radius;
  private View selected;
  private ValueAnimator transition;
  private float opacity;
  private int layoutWidth=-1,layoutHeight=-1;
  private int[] childBounds=new int[0];

  GlassDock(Context context){
    super(context);setOrientation(HORIZONTAL);setGravity(Gravity.CENTER_VERTICAL);
    inset=Ui.dp(context,LiquidGlassDrawable.INSET_DP+1);radius=Ui.dp(context,23);
  }

  @Override protected int[] onCreateDrawableState(int extraSpace){return GlassMotion.childState(this,super.onCreateDrawableState(extraSpace+1));}

  /** Called after all Button.selected values have been updated. */
  void selectionChanged(){
    View next=selectedButton();
    if(next==selected){
      if(transition!=null&&!ValueAnimator.areAnimatorsEnabled())settle();
      else invalidate();
      return;
    }
    selected=next;
    cancelTransition();
    boundsFor(selected,target);
    if(!isAttachedToWindow()||!isLaidOut()||!isShown()||getWindowVisibility()!=VISIBLE||!ValueAnimator.areAnimatorsEnabled()){
      settle();return;
    }
    float destination=target.isEmpty()?0f:1f;
    if(destination==0f&&opacity==0f){highlight.setEmpty();invalidate();return;}
    // The first selection fades in at its own location, never from a fake tab.
    if(destination>0f&&(highlight.isEmpty()||opacity==0f))highlight.set(target);
    origin.set(highlight);
    if(destination==0f)target.set(highlight);
    final float startOpacity=opacity;
    ValueAnimator run=ValueAnimator.ofFloat(0f,1f);
    transition=run;run.setDuration(240);
    run.setInterpolator(new PathInterpolator(.2f,0f,0f,1f));
    run.addUpdateListener(value->{
      if(transition!=value)return;
      if(!ValueAnimator.areAnimatorsEnabled()){settle();return;}
      float fraction=(float)value.getAnimatedValue();
      highlight.set(origin.left+(target.left-origin.left)*fraction,
        origin.top+(target.top-origin.top)*fraction,
        origin.right+(target.right-origin.right)*fraction,
        origin.bottom+(target.bottom-origin.bottom)*fraction);
      opacity=startOpacity+(destination-startOpacity)*fraction;invalidate();
    });
    run.addListener(new AnimatorListenerAdapter(){
      @Override public void onAnimationEnd(Animator animation){
        if(transition!=animation)return;
        transition=null;opacity=destination;
        if(destination==0f)highlight.setEmpty();else highlight.set(target);
        invalidate();
      }
    });
    run.start();
  }

  private View selectedButton(){
    for(int i=0;i<getChildCount();i++){View child=getChildAt(i);if(child.isSelected())return child;}
    return null;
  }

  private void boundsFor(View child,RectF result){
    if(child==null||child.getParent()!=this||child.getWidth()<=2*inset||child.getHeight()<=2*inset){result.setEmpty();return;}
    result.set(child.getLeft()+inset,child.getTop()+inset,child.getRight()-inset,child.getBottom()-inset);
  }

  private void cancelTransition(){
    ValueAnimator previous=transition;transition=null;
    if(previous!=null)previous.cancel();
  }

  private void settle(){
    cancelTransition();selected=selectedButton();boundsFor(selected,target);
    highlight.set(target);opacity=target.isEmpty()?0f:1f;invalidate();
  }

  @Override protected void dispatchDraw(Canvas canvas){
    if(opacity>0f&&!highlight.isEmpty()){
      // Read the live palette so an appearance change never restarts the motion.
      paint.setColor(DesignUi.BLUE);paint.setAlpha(Math.round(14*opacity));
      float corner=Math.min(radius,Math.min(highlight.width(),highlight.height())/2f);
      canvas.drawRoundRect(highlight,corner,corner,paint);
    }
    super.dispatchDraw(canvas);
  }

  @Override protected void onLayout(boolean changed,int left,int top,int right,int bottom){
    super.onLayout(changed,left,top,right,bottom);
    // A routine re-layout must not interrupt a running selection transition.
    if(geometryChanged()||selectedButton()!=selected)settle();
  }

  private boolean geometryChanged(){
    boolean changed=layoutWidth!=getWidth()||layoutHeight!=getHeight();
    layoutWidth=getWidth();layoutHeight=getHeight();
    int count=getChildCount();
    if(childBounds.length!=count*4){childBounds=new int[count*4];changed=true;}
    for(int i=0;i<count;i++){
      View child=getChildAt(i);int offset=i*4;
      if(childBounds[offset]!=child.getLeft()||childBounds[offset+1]!=child.getTop()
          ||childBounds[offset+2]!=child.getRight()||childBounds[offset+3]!=child.getBottom())changed=true;
      childBounds[offset]=child.getLeft();childBounds[offset+1]=child.getTop();
      childBounds[offset+2]=child.getRight();childBounds[offset+3]=child.getBottom();
    }
    return changed;
  }

  @Override public void onVisibilityAggregated(boolean visible){super.onVisibilityAggregated(visible);if(!visible){settle();GlassMotion.reset(this);}}
  @Override protected void onWindowVisibilityChanged(int visibility){super.onWindowVisibilityChanged(visibility);if(visibility!=VISIBLE){settle();GlassMotion.reset(this);}}
  @Override protected void onAttachedToWindow(){super.onAttachedToWindow();settle();}
  @Override protected void onDetachedFromWindow(){settle();super.onDetachedFromWindow();}
}
