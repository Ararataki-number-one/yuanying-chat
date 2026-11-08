package local.pocketchat;

import android.animation.Animator;
import android.animation.AnimatorListenerAdapter;
import android.animation.ValueAnimator;
import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.LinearGradient;
import android.graphics.Matrix;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.Shader;
import android.view.Gravity;
import android.view.View;
import android.view.animation.LinearInterpolator;
import android.view.animation.PathInterpolator;
import android.widget.LinearLayout;

/** One elastic glass selection underneath the unchanged native destination buttons. */
final class GlassDock extends LinearLayout {
  private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
  private final RectF highlight=new RectF(),target=new RectF(),origin=new RectF(),rim=new RectF();
  private final LinearGradient sheen=new LinearGradient(0f,0f,1f,0f,
    new int[]{0x00ffffff,Color.WHITE,0x00ffffff},new float[]{0f,.5f,1f},Shader.TileMode.CLAMP);
  private final Matrix sheenMatrix=new Matrix();
  private final int inset;
  private final float radius,stretchLimit,density;
  private final PathInterpolator travelEase=new PathInterpolator(.2f,0f,0f,1f);
  private View selected;
  private ValueAnimator transition;
  private float opacity,flow,sheenX;
  private int layoutWidth=-1,layoutHeight=-1;
  private int[] childBounds=new int[0];

  GlassDock(Context context){
    super(context);setOrientation(HORIZONTAL);setGravity(Gravity.CENTER_VERTICAL);
    density=context.getResources().getDisplayMetrics().density;
    inset=Ui.dp(context,LiquidGlassDrawable.INSET_DP+1);radius=Ui.dp(context,23);stretchLimit=Ui.dp(context,22);
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
    if(destination==0f&&opacity==0f){highlight.setEmpty();flow=0f;invalidate();return;}
    // The first selection fades in at its own location, never from a fake tab.
    if(destination>0f&&(highlight.isEmpty()||opacity==0f))highlight.set(target);
    origin.set(highlight);
    if(destination==0f)target.set(highlight);
    final float startOpacity=opacity;
    final float startFlow=flow;
    final float direction=target.centerX()>=origin.centerX()?1f:-1f;
    final float startSheen=flow>0f?sheenX:direction>0f?origin.left-12f*density:origin.right+12f*density;
    final float endSheen=direction>0f?target.right+12f*density:target.left-12f*density;
    final float maximumWidth=Math.max(origin.width(),target.width()+stretchLimit);
    final float minimumWidth=Math.min(origin.width(),target.width())*.9f;
    ValueAnimator run=ValueAnimator.ofFloat(0f,1f);
    transition=run;run.setDuration(destination==0f?180:440);run.setInterpolator(new LinearInterpolator());
    run.addUpdateListener(value->{
      if(transition!=value)return;
      if(!isAttachedToWindow()||!isShown()||getWindowVisibility()!=VISIBLE||!ValueAnimator.areAnimatorsEnabled()){settle();return;}
      float time=(float)value.getAnimatedValue(),fraction=travelEase.getInterpolation(time);
      // The leading edge leaves first; the trailing edge catches up and both
      // settle with one small damped rebound. Retarget from these drawn edges,
      // never from a previous tab's fixed rectangle or a changed hit region.
      float leading=settling(Math.min(1f,time/.9f));
      float trailing=settling(Math.max(0f,(time-.09f)/.91f));
      float left=origin.left+(target.left-origin.left)*(direction>0f?trailing:leading);
      float right=origin.right+(target.right-origin.right)*(direction>0f?leading:trailing);
      float width=Math.min(getWidth()-2f*inset,Math.max(minimumWidth,Math.min(maximumWidth,right-left)));
      float center=Math.max(inset+width*.5f,Math.min((left+right)*.5f,getWidth()-inset-width*.5f));
      float ordinaryWidth=origin.width()+(target.width()-origin.width())*fraction;
      float squash=Math.max(-.75f*density,Math.min(1.8f*density,(width-ordinaryWidth)*.07f));
      highlight.set(center-width*.5f,Math.max(inset,origin.top+(target.top-origin.top)*fraction+squash),
        center+width*.5f,Math.min(getHeight()-inset,origin.bottom+(target.bottom-origin.bottom)*fraction-squash));
      opacity=startOpacity+(destination-startOpacity)*fraction;
      flow=Math.min(1f,startFlow*(1f-fraction)+(destination==0f?0f:(float)Math.sin(Math.PI*time)));
      sheenX=startSheen+(endSheen-startSheen)*fraction;
      invalidate();
    });
    run.addListener(new AnimatorListenerAdapter(){
      @Override public void onAnimationEnd(Animator animation){
        if(transition!=animation)return;
        transition=null;opacity=destination;flow=0f;
        if(destination==0f)highlight.setEmpty();else highlight.set(target);
        invalidate();
      }
    });
    run.start();
  }

  /** Zero initial velocity, about 3.5% overshoot, and an exact resting endpoint. */
  private static float settling(float time){
    if(time<=0f)return 0f;if(time>=1f)return 1f;
    return (float)(1d-Math.exp(-7.5d*time)*(Math.cos(7d*time)+(7.5d/7d)*Math.sin(7d*time)));
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
    highlight.set(target);opacity=target.isEmpty()?0f:1f;flow=0f;invalidate();
  }

  @Override protected void dispatchDraw(Canvas canvas){
    if(opacity>0f&&!highlight.isEmpty()){
      // Read the live palette so an appearance change never restarts the motion.
      paint.setStyle(Paint.Style.FILL);paint.setShader(null);
      paint.setColor(DesignUi.BLUE);paint.setAlpha(Math.round((16f+6f*flow)*opacity));
      float corner=Math.min(radius,Math.min(highlight.width(),highlight.height())/2f);
      canvas.drawRoundRect(highlight,corner,corner,paint);
      if(flow>0f){
        // One broad reflection crosses the travelling lens; it stops completely
        // at rest and stays behind the native glyphs rather than moving them.
        float width=Math.max(16f*density,Math.min(36f*density,highlight.width()*.42f));
        sheenMatrix.setScale(width,1f);sheenMatrix.postTranslate(sheenX-width*.5f,0f);
        sheen.setLocalMatrix(sheenMatrix);paint.setShader(sheen);paint.setColor(Color.WHITE);
        paint.setAlpha(Math.round((AppAppearance.dark()?36f:150f)*flow*opacity));
        canvas.drawRoundRect(highlight,corner,corner,paint);paint.setShader(null);
      }
      float stroke=.65f*density;
      rim.set(highlight);rim.inset(stroke*.5f,stroke*.5f);
      paint.setStyle(Paint.Style.STROKE);paint.setStrokeWidth(stroke);paint.setColor(Color.WHITE);
      paint.setAlpha(Math.round((AppAppearance.dark()?16f+26f*flow:42f+104f*flow)*opacity));
      canvas.drawRoundRect(rim,Math.max(0f,corner-stroke*.5f),Math.max(0f,corner-stroke*.5f),paint);
      paint.setStyle(Paint.Style.FILL);
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
