package local.pocketchat;

import android.animation.Animator;
import android.animation.AnimatorListenerAdapter;
import android.animation.ValueAnimator;
import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.ColorFilter;
import android.graphics.Outline;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.PathMeasure;
import android.graphics.PixelFormat;
import android.graphics.Rect;
import android.graphics.RectF;
import android.graphics.drawable.Drawable;
import android.os.Build;
import android.util.Log;
import android.view.View;
import android.view.animation.DecelerateInterpolator;
import android.view.animation.LinearInterpolator;
import java.lang.ref.WeakReference;

/** Curved optical coating. Only the material moves; native labels and hit areas stay fixed. */
class LiquidGlassDrawable extends Drawable {
  static final int INSET_DP=4;
  private static final int SAMPLES=128;
  private final Context context;
  private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG|Paint.FILTER_BITMAP_FLAG);
  private final RectF body=new RectF();
  private final Path outlinePath=new Path();
  private final PathMeasure rim=new PathMeasure();
  private final float[] baseX=new float[SAMPLES],baseY=new float[SAMPLES],point=new float[2];
  private final float density,requestedRadius;
  private float radius,perimeter,restPhase,phase,targetPhase,strength,bend,gatherFraction;
  private float hotspotX,hotspotY,bumpX,bumpY,lightX=-.72f,lightY=-.69f,travelDirection=1f;
  private ValueAnimator animation;
  private int alpha=255;
  private boolean dark,pressed,gpuBroken,rasterDeformed;
  private GlassLensRenderer renderer;
  private Bitmap restingRaster,pressedRaster;
  private ColorFilter colorFilter;
  private WeakReference<GlassBackdrop> backdrop;
  private WeakReference<View> owner;

  LiquidGlassDrawable(Context context,int radiusDp){
    this.context=context.getApplicationContext();
    density=context.getResources().getDisplayMetrics().density;
    requestedRadius=Math.max(0,radiusDp*density);dark=AppAppearance.dark();
  }

  /** Bind only an independent native content sibling, never the chat document. */
  void setBackdrop(GlassBackdrop source,View host){
    if(backdrop!=null&&backdrop.get()==source&&owner!=null&&owner.get()==host)return;
    backdrop=source==null?null:new WeakReference<>(source);
    owner=host==null?null:new WeakReference<>(host);
    discardRecording();invalidateSelf();
  }

  void refresh(){
    boolean next=AppAppearance.dark();if(dark==next)return;
    dark=next;stopAnimation();pressed=false;strength=bend=0f;prepare();invalidateSelf();
  }

  @Override protected void onBoundsChange(Rect bounds){
    stopAnimation();pressed=false;strength=bend=0f;prepare();
  }

  private void prepare(){
    restingRaster=pressedRaster=null;discardRecording();
    Rect bounds=getBounds();float inset=INSET_DP*density;
    if(bounds.width()<=2*inset||bounds.height()<=2*inset){body.setEmpty();perimeter=0f;return;}
    body.set(bounds);body.inset(inset,inset);
    radius=Math.min(Math.max(0,requestedRadius-inset),Math.min(body.width(),body.height())/2f);
    outlinePath.rewind();outlinePath.addRoundRect(body,radius,radius,Path.Direction.CW);
    rim.setPath(outlinePath,true);perimeter=rim.getLength();
    for(int i=0;i<SAMPLES;i++){
      rim.getPosTan(perimeter*i/SAMPLES,point,null);baseX[i]=point[0];baseY[i]=point[1];
    }
    restPhase=nearestPhase(body.left+body.width()*.26f,body.top-body.height()*.4f);
    phase=targetPhase=restPhase;hotspotX=body.centerX();hotspotY=body.centerY();
    updateOptics();
  }

  @Override public boolean isStateful(){return true;}

  @Override protected boolean onStateChange(int[] state){
    boolean enabled=false,down=false;
    for(int value:state){if(value==android.R.attr.state_enabled)enabled=true;if(value==android.R.attr.state_pressed)down=true;}
    down&=enabled;
    if(!enabled){boolean changed=pressed||strength!=0f;resetMotion();return changed;}
    if(down==pressed)return false;
    pressed=down;
    if(body.isEmpty()||!isVisible()||getCallback()==null){resetMotion();return true;}
    if(down){
      pressedRaster=null;targetPhase=lightPhase();
      if(strength==0f)phase=targetPhase;
      strength=Math.max(strength,.65f);bend=Math.max(bend,.65f);
      updateOptics();invalidateSelf();gather(110);
    }else release();
    return true;
  }

  @Override public void setHotspot(float x,float y){
    if(body.isEmpty()||!isVisible())return;
    float nextX=clamp(x,body.left,body.right),nextY=clamp(y,body.top,body.bottom);
    if(Math.abs(nextX-hotspotX)+Math.abs(nextY-hotspotY)<.2f*density)return;
    hotspotX=nextX;hotspotY=nextY;if(!pressed)return;
    float next=lightPhase(),delta=shortest(next-targetPhase);
    if(Math.abs(delta)>.4f*density)travelDirection=delta<0f?-1f:1f;
    targetPhase=next;
    // Retarget a live animation instead of resetting its clock on every MOVE.
    if(animation==null||!ValueAnimator.areAnimatorsEnabled())gather(85);
  }

  private float lightPhase(){
    return nearestPhase(hotspotX+(hotspotX-body.centerX())*.12f,hotspotY-body.height()*.72f);
  }

  private void gather(long duration){
    stopAnimation();
    if(!ValueAnimator.areAnimatorsEnabled()){
      phase=targetPhase;strength=1f;bend=0f;updateOptics();invalidateSelf();return;
    }
    final float startStrength=strength,startBend=bend;gatherFraction=0f;
    ValueAnimator run=ValueAnimator.ofFloat(0f,1f);animation=run;
    run.setDuration(duration);run.setInterpolator(new DecelerateInterpolator(1.5f));
    run.addUpdateListener(value->{
      if(animation!=value)return;
      if(!ValueAnimator.areAnimatorsEnabled()){stopAnimation();phase=targetPhase;strength=1f;bend=0f;updateOptics();invalidateSelf();return;}
      float t=(float)value.getAnimatedValue();
      float step=gatherFraction>=1f?1f:clamp((t-gatherFraction)/(1f-gatherFraction),0f,1f);
      phase+=shortest(targetPhase-phase)*step;gatherFraction=t;
      strength=startStrength+(1f-startStrength)*t;bend=startBend+(1f-startBend)*t;
      updateOptics();invalidateSelf();
    });
    run.addListener(new AnimatorListenerAdapter(){
      @Override public void onAnimationEnd(Animator animator){if(animation==animator)animation=null;}
    });
    run.start();
  }

  private void release(){
    stopAnimation();if(strength==0f||!ValueAnimator.areAnimatorsEnabled()){resetMotion();return;}
    final float startPhase=phase,startStrength=strength,startBend=bend;
    final float travel=travelDirection*Math.min(32f*density,perimeter*.19f);
    ValueAnimator run=ValueAnimator.ofFloat(0f,1f);animation=run;
    run.setDuration(480);run.setInterpolator(new LinearInterpolator());
    run.addUpdateListener(value->{
      if(animation!=value)return;
      if(!ValueAnimator.areAnimatorsEnabled()){resetMotion();return;}
      float t=(float)value.getAnimatedValue(),remaining=1f-t;
      phase=startPhase+travel*(1f-remaining*remaining);strength=startStrength*remaining;
      bend=startBend*remaining*remaining*(float)Math.cos(Math.PI*1.2f*t);
      updateOptics();invalidateSelf();
    });
    run.addListener(new AnimatorListenerAdapter(){
      @Override public void onAnimationEnd(Animator animator){if(animation==animator){animation=null;resetMotion();}}
    });
    run.start();
  }

  private void stopAnimation(){ValueAnimator old=animation;animation=null;if(old!=null)old.cancel();}
  private void resetMotion(){
    stopAnimation();pressed=false;strength=bend=0f;phase=targetPhase=restPhase;travelDirection=1f;
    if(!body.isEmpty())updateOptics();invalidateSelf();
  }
  @Override public void jumpToCurrentState(){resetMotion();}
  @Override public boolean setVisible(boolean visible,boolean restart){
    boolean changed=super.setVisible(visible,restart);
    if(!visible){resetMotion();discardRecording();}return changed;
  }
  private void discardRecording(){if(renderer!=null)renderer.discard();}

  private void updateOptics(){
    if(body.isEmpty()||perimeter<=0f)return;
    rim.getPosTan(wrap(phase,perimeter),point,null);bumpX=point[0];bumpY=point[1];
    float x=(bumpX-body.centerX())/Math.max(body.width()*.5f,1f);
    float y=(bumpY-body.centerY())/Math.max(body.height()*.5f,1f);
    float len=(float)Math.hypot(x,y);if(len>.001f){x/=len;y/=len;}
    float energy=.82f*strength;
    lightX=-.72f*(1f-energy)+x*energy;lightY=-.69f*(1f-energy)+y*energy;
    len=(float)Math.hypot(lightX,lightY);
    if(len>.001f){lightX/=len;lightY/=len;}else{lightX=-.72f;lightY=-.69f;}
  }

  private float nearestPhase(float x,float y){
    float best=Float.MAX_VALUE,result=0f;
    for(int i=0;i<SAMPLES;i++){
      int next=(i+1)%SAMPLES;float dx=baseX[next]-baseX[i],dy=baseY[next]-baseY[i],square=dx*dx+dy*dy;
      float t=square==0f?0f:clamp(((x-baseX[i])*dx+(y-baseY[i])*dy)/square,0f,1f);
      float ex=baseX[i]+dx*t-x,ey=baseY[i]+dy*t-y,distance=ex*ex+ey*ey;
      if(distance<best){best=distance;result=(i+t)*perimeter/SAMPLES;}
    }
    return result;
  }
  private float shortest(float distance){return perimeter<=0f?0f:wrap(distance+perimeter*.5f,perimeter)-perimeter*.5f;}
  private static float wrap(float value,float length){return length<=0f?0f:(value%length+length)%length;}
  private static float clamp(float value,float low,float high){return Math.max(low,Math.min(high,value));}

  @Override public void draw(Canvas canvas){
    if(body.isEmpty()||alpha==0)return;
    if(Build.VERSION.SDK_INT>=33&&canvas.isHardwareAccelerated()&&colorFilter==null&&!gpuBroken){
      try{
        if(renderer==null)renderer=new GlassLensRenderer(context,density);
        if(renderer.draw(canvas,getBounds(),radius,strength,bend,lightX,lightY,bumpX,bumpY,
            alpha,dark,backdrop==null?null:backdrop.get(),owner==null?null:owner.get()))return;
      }catch(Exception|LinkageError error){
        gpuBroken=true;renderer=null;Log.w("GlassLens","AGSL unavailable; using cached material",error);
      }
    }
    Rect bounds=getBounds();
    if(restingRaster==null)restingRaster=GlassMaterialRaster.create(bounds.width(),bounds.height(),density,radius,dark,-.72f,-.69f,body.centerX()-bounds.left,body.top-bounds.top,0f,0f);
    boolean deform=ValueAnimator.areAnimatorsEnabled();
    if(strength>0f&&(pressedRaster==null||rasterDeformed!=deform)){
      pressedRaster=GlassMaterialRaster.create(bounds.width(),bounds.height(),density,radius,dark,lightX,lightY,bumpX-bounds.left,bumpY-bounds.top,1f,deform?1f:0f);rasterDeformed=deform;
    }
    paint.setColorFilter(colorFilter);paint.setAlpha(Math.round(alpha*(1-strength)));
    if(paint.getAlpha()>0)canvas.drawBitmap(restingRaster,null,bounds,paint);
    if(pressedRaster!=null&&strength>0){paint.setAlpha(Math.round(alpha*strength));canvas.drawBitmap(pressedRaster,null,bounds,paint);}
    paint.setAlpha(alpha);
  }

  @Override public void getOutline(Outline outline){
    Rect bounds=getBounds();if(bounds.isEmpty()){outline.setEmpty();return;}
    outline.setRoundRect(bounds,Math.min(requestedRadius,Math.min(bounds.width(),bounds.height())/2f));outline.setAlpha(0f);
  }
  @Override public void setAlpha(int value){int next=Math.max(0,Math.min(255,value));if(alpha!=next){alpha=next;invalidateSelf();}}
  @Override public int getAlpha(){return alpha;}
  @Override public void setColorFilter(ColorFilter filter){colorFilter=filter;invalidateSelf();}
  @Override public int getOpacity(){return PixelFormat.TRANSLUCENT;}
}
