package local.pocketchat;

import android.animation.Animator;
import android.animation.AnimatorListenerAdapter;
import android.animation.ValueAnimator;
import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BlurMaskFilter;
import android.graphics.Canvas;
import android.graphics.ColorFilter;
import android.graphics.LinearGradient;
import android.graphics.Matrix;
import android.graphics.Outline;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.PathMeasure;
import android.graphics.PixelFormat;
import android.graphics.PorterDuff;
import android.graphics.PorterDuffXfermode;
import android.graphics.Rect;
import android.graphics.RectF;
import android.graphics.Shader;
import android.graphics.drawable.Drawable;
import android.view.animation.DecelerateInterpolator;
import android.view.animation.LinearInterpolator;

/**
 * Clear native glass whose light and optical edge respond to the touch point.
 * The foreground and hit target stay fixed. This does not sample Gecko content.
 * Only bounded input-driven animations run; there is no idle animation loop.
 * Geometry and shader matrices are reused during motion. The software-blurred
 * exterior shadow is rebuilt only when bounds or the appearance change.
 */
class LiquidGlassDrawable extends Drawable {
  static final int INSET_DP=4;
  private static final int SAMPLES=128;
  private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
  private final RectF body=new RectF(),innerBody=new RectF();
  private final Path restingShape=new Path(),restingInner=new Path(),shape=new Path(),innerShape=new Path();
  private final PathMeasure rim=new PathMeasure(),innerRim=new PathMeasure();
  private final float[] baseX=new float[SAMPLES],baseY=new float[SAMPLES],normalX=new float[SAMPLES],normalY=new float[SAMPLES];
  private final float[] shapeX=new float[SAMPLES],shapeY=new float[SAMPLES],position=new float[2],tangent=new float[2],matrixValues=new float[9];
  private final Band ambient=new Band(),ambientCounter=new Band(),moving=new Band(),movingCounter=new Band();
  private final float density,requestedRadius,edgeWidth;
  private float radius,perimeter,restPhase,bandLength,hotspotX,hotspotY;
  private float phase,targetPhase,strength,bend,gatherFraction,travelDirection=1f;
  private Shader fill,outerLine;
  private Bitmap shadowBitmap;
  private ValueAnimator animation;
  private int alpha=255;
  private boolean dark,pressed;

  private final class Band {
    final Path edge=new Path(),caustic=new Path();
    final Matrix fade=new Matrix();
    Shader bright,shade;
    void prepare(){
      bright=new LinearGradient(0,0,1,0,
        new int[]{0x00ffffff,dark?0xc8ffffff:0xf0ffffff,0xb8ffffff,0x00ffffff},
        new float[]{0f,.25f,.65f,1f},Shader.TileMode.CLAMP);
      shade=new LinearGradient(0,0,1,0,
        dark?new int[]{0x00000000,0x38000000,0x18000000,0x00000000}
            :new int[]{0x003e4b5e,0x283e4b5e,0x1c3e4b5e,0x003e4b5e},
        new float[]{0f,.3f,.7f,1f},Shader.TileMode.CLAMP);
    }
  }

  LiquidGlassDrawable(Context context,int radiusDp){
    density=context.getResources().getDisplayMetrics().density;
    requestedRadius=Math.max(0,radiusDp*density);edgeWidth=.5f*density;
    dark=AppAppearance.dark();
  }

  /** The existing event-driven appearance dispatcher calls this method. */
  void refresh(){
    boolean next=AppAppearance.dark();if(dark==next)return;
    dark=next;stopAnimation();pressed=false;strength=bend=0f;prepare();invalidateSelf();
  }

  @Override protected void onBoundsChange(Rect bounds){
    stopAnimation();pressed=false;strength=bend=0f;prepare();
  }

  private void prepare(){
    Rect bounds=getBounds();float inset=INSET_DP*density;
    if(bounds.width()<=2*inset||bounds.height()<=2*inset){body.setEmpty();shadowBitmap=null;perimeter=0f;return;}
    body.set(bounds);body.inset(inset,inset);
    radius=Math.min(Math.max(0,requestedRadius-inset),Math.min(body.width(),body.height())/2f);
    restingShape.rewind();restingShape.addRoundRect(body,radius,radius,Path.Direction.CW);
    float opticalInset=Math.min(2f*density,Math.min(body.width(),body.height())/6f);
    innerBody.set(body);innerBody.inset(opticalInset,opticalInset);
    restingInner.rewind();restingInner.addRoundRect(innerBody,Math.max(0,radius-opticalInset),Math.max(0,radius-opticalInset),Path.Direction.CW);
    rim.setPath(restingShape,true);perimeter=rim.getLength();
    for(int i=0;i<SAMPLES;i++){
      rim.getPosTan(perimeter*i/SAMPLES,position,tangent);
      baseX[i]=position[0];baseY[i]=position[1];normalX[i]=tangent[1];normalY[i]=-tangent[0];
    }
    restPhase=nearestPhase(body.left+body.width()*.26f,body.top-body.height()*.4f);
    phase=targetPhase=restPhase;hotspotX=body.centerX();hotspotY=body.centerY();
    bandLength=Math.max(28f*density,Math.min(64f*density,perimeter*.15f));
    fill=new LinearGradient(body.left,body.top,body.left,body.bottom,
      dark?new int[]{0x42222934,0x30202630,0x3d1e252f}:new int[]{0x23ffffff,0x1fffffff,0x1cffffff},
      new float[]{0f,.48f,1f},Shader.TileMode.CLAMP);
    outerLine=new LinearGradient(body.left,body.top,body.left,body.bottom,
      dark?new int[]{0x16ffffff,0x10ffffff}:new int[]{0x0c000000,0x10000000},null,Shader.TileMode.CLAMP);
    ambient.prepare();ambientCounter.prepare();moving.prepare();movingCounter.prepare();
    prepareShadow(bounds);updateGeometry();
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
      targetPhase=lightPhase();
      if(strength==0f)phase=targetPhase;
      // A short tap must have an optical response even before the first frame
      // of a duration animator. The remaining pressure still gathers smoothly.
      strength=Math.max(strength,.65f);bend=Math.max(bend,.65f);
      updateGeometry();invalidateSelf();
      gather(110);
    }else release();
    return true;
  }

  /** RippleDrawable must explicitly forward its hotspot to this content. */
  @Override public void setHotspot(float x,float y){
    if(body.isEmpty()||!isVisible())return;
    float nextX=clamp(x,body.left,body.right),nextY=clamp(y,body.top,body.bottom);
    if(Math.abs(nextX-hotspotX)+Math.abs(nextY-hotspotY)<.2f*density)return;
    hotspotX=nextX;hotspotY=nextY;
    if(!pressed)return;
    float next=lightPhase(),delta=shortest(next-targetPhase);
    if(Math.abs(delta)>.4f*density)travelDirection=delta<0f?-1f:1f;
    targetPhase=next;
    // Retarget the live run instead of restarting its clock on every MOVE.
    // Input is dispatched before animation frames, so repeated restarts can
    // otherwise prevent either pressure or the light from advancing at all.
    if(animation==null||!ValueAnimator.areAnimatorsEnabled())gather(85);
  }

  private float lightPhase(){
    // A light bias keeps a central tap coherent; lateral movement still follows
    // the actual point rather than stretching an entire capsule or its label.
    return nearestPhase(hotspotX+(hotspotX-body.centerX())*.12f,hotspotY-body.height()*.72f);
  }

  private void gather(long duration){
    stopAnimation();
    if(!ValueAnimator.areAnimatorsEnabled()){
      phase=targetPhase;strength=1f;bend=0f;updateGeometry();invalidateSelf();return;
    }
    final float startStrength=strength,startBend=bend;
    gatherFraction=0f;
    ValueAnimator run=ValueAnimator.ofFloat(0f,1f);animation=run;
    run.setDuration(duration);run.setInterpolator(new DecelerateInterpolator(1.5f));
    run.addUpdateListener(value->{
      if(animation!=value)return;
      if(!ValueAnimator.areAnimatorsEnabled()){stopAnimation();phase=targetPhase;strength=1f;bend=0f;updateGeometry();invalidateSelf();return;}
      float t=(float)value.getAnimatedValue();
      float step=gatherFraction>=1f?1f:clamp((t-gatherFraction)/(1f-gatherFraction),0f,1f);
      phase+=shortest(targetPhase-phase)*step;gatherFraction=t;
      strength=startStrength+(1f-startStrength)*t;bend=startBend+(1f-startBend)*t;
      updateGeometry();invalidateSelf();
    });
    run.addListener(new AnimatorListenerAdapter(){
      @Override public void onAnimationEnd(Animator animator){if(animation==animator)animation=null;}
    });
    run.start();
  }

  private void release(){
    stopAnimation();
    if(strength==0f||!ValueAnimator.areAnimatorsEnabled()){resetMotion();return;}
    final float startPhase=phase,startStrength=strength,startBend=bend;
    final float travel=travelDirection*Math.min(32f*density,perimeter*.19f);
    ValueAnimator run=ValueAnimator.ofFloat(0f,1f);animation=run;
    run.setDuration(480);run.setInterpolator(new LinearInterpolator());
    run.addUpdateListener(value->{
      if(animation!=value)return;
      if(!ValueAnimator.areAnimatorsEnabled()){resetMotion();return;}
      float t=(float)value.getAnimatedValue(),remaining=1f-t;
      // A single travelling reflection fades into the stationary light. The
      // small signed bend settles once; it never moves the foreground or hitbox.
      phase=startPhase+travel*(1f-remaining*remaining);
      strength=startStrength*remaining;
      bend=startBend*remaining*remaining*(float)Math.cos(Math.PI*1.2f*t);
      updateGeometry();invalidateSelf();
    });
    run.addListener(new AnimatorListenerAdapter(){
      @Override public void onAnimationEnd(Animator animator){if(animation==animator){animation=null;resetMotion();}}
    });
    run.start();
  }

  private void stopAnimation(){ValueAnimator old=animation;animation=null;if(old!=null)old.cancel();}

  private void resetMotion(){
    stopAnimation();pressed=false;strength=bend=0f;phase=targetPhase=restPhase;travelDirection=1f;
    if(!body.isEmpty())updateGeometry();invalidateSelf();
  }

  @Override public void jumpToCurrentState(){resetMotion();}
  @Override public boolean setVisible(boolean visible,boolean restart){
    boolean changed=super.setVisible(visible,restart);if(!visible)resetMotion();return changed;
  }

  private void updateGeometry(){
    if(body.isEmpty()||perimeter<=0f)return;
    if(Math.abs(bend)<.0001f){shape.set(restingShape);innerShape.set(restingInner);}
    else{
      float width=bandLength*.6f,opticalInset=innerBody.left-body.left;
      for(int i=0;i<SAMPLES;i++){
        float at=perimeter*i/SAMPLES,distance=shortest(at-phase)/width,opposite=shortest(at-phase-perimeter*.5f)/width;
        float displacement=bend*density*(1.8f*(float)Math.exp(-distance*distance)-.35f*(float)Math.exp(-opposite*opposite));
        shapeX[i]=baseX[i]+normalX[i]*displacement;shapeY[i]=baseY[i]+normalY[i]*displacement;
      }
      smoothPath(shape,0f);smoothPath(innerShape,opticalInset);
    }
    rim.setPath(shape,true);innerRim.setPath(innerShape,true);
    updateBand(ambient,restPhase,bandLength);
    updateBand(ambientCounter,restPhase+perimeter*.51f,bandLength*.65f);
    if(strength>0f){
      updateBand(moving,phase,bandLength*(.8f+.2f*strength));
      updateBand(movingCounter,phase+perimeter*.51f,bandLength*.58f);
    }
  }

  private void smoothPath(Path path,float inset){
    path.rewind();int last=SAMPLES-1;
    path.moveTo((shapeX[last]+shapeX[0]-(normalX[last]+normalX[0])*inset)*.5f,
      (shapeY[last]+shapeY[0]-(normalY[last]+normalY[0])*inset)*.5f);
    for(int i=0;i<SAMPLES;i++){
      int next=(i+1)%SAMPLES;
      float x=shapeX[i]-normalX[i]*inset,y=shapeY[i]-normalY[i]*inset;
      path.quadTo(x,y,(x+shapeX[next]-normalX[next]*inset)*.5f,(y+shapeY[next]-normalY[next]*inset)*.5f);
    }
    path.close();
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

  private void updateBand(Band band,float at,float width){
    float length=rim.getLength(),fraction=wrap(at,perimeter)/perimeter;
    float center=fraction*length,span=Math.min(width*length/perimeter,length*.42f);
    segment(rim,band.edge,center,span);
    float innerLength=innerRim.getLength();segment(innerRim,band.caustic,fraction*innerLength,span*innerLength/length);
    rim.getPosTan(wrap(center-span*.5f,length),position,null);float x=position[0],y=position[1];
    rim.getPosTan(wrap(center+span*.5f,length),position,null);float dx=position[0]-x,dy=position[1]-y;
    if(Math.abs(dx)+Math.abs(dy)<.01f)dx=1f;
    matrixValues[0]=dx;matrixValues[1]=-dy;matrixValues[2]=x;
    matrixValues[3]=dy;matrixValues[4]=dx;matrixValues[5]=y;
    matrixValues[6]=matrixValues[7]=0f;matrixValues[8]=1f;
    band.fade.setValues(matrixValues);band.bright.setLocalMatrix(band.fade);band.shade.setLocalMatrix(band.fade);
  }

  private static void segment(PathMeasure measure,Path result,float center,float width){
    result.rewind();float length=measure.getLength();if(length<=0f)return;
    float start=wrap(center-width*.5f,length),end=start+width;
    measure.getSegment(start,Math.min(length,end),result,true);
    if(end>length)measure.getSegment(0f,end-length,result,true);
  }

  private float shortest(float distance){if(perimeter<=0f)return 0f;return wrap(distance+perimeter*.5f,perimeter)-perimeter*.5f;}
  private static float wrap(float value,float length){return length<=0f?0f:(value%length+length)%length;}
  private static float clamp(float value,float low,float high){return Math.max(low,Math.min(high,value));}

  private void prepareShadow(Rect bounds){
    Bitmap next=Bitmap.createBitmap(bounds.width(),bounds.height(),Bitmap.Config.ARGB_8888);next.setDensity(Bitmap.DENSITY_NONE);
    Canvas offscreen=new Canvas(next);Paint shadowPaint=new Paint(Paint.ANTI_ALIAS_FLAG);
    shadowPaint.setColor(dark?0x18000000:0x16000000);
    shadowPaint.setMaskFilter(new BlurMaskFilter(2.5f*density,BlurMaskFilter.Blur.NORMAL));
    RectF localBody=new RectF(body);localBody.offset(-bounds.left,-bounds.top);
    float drop=.75f*density;localBody.offset(0,drop);offscreen.drawRoundRect(localBody,radius,radius,shadowPaint);
    localBody.offset(0,-drop);shadowPaint.setMaskFilter(null);shadowPaint.setAlpha(255);
    shadowPaint.setXfermode(new PorterDuffXfermode(PorterDuff.Mode.CLEAR));offscreen.drawRoundRect(localBody,radius,radius,shadowPaint);
    offscreen.setBitmap(null);shadowBitmap=next;
  }

  @Override public void draw(Canvas canvas){
    if(body.isEmpty()||alpha==0)return;
    paint.setAlpha(alpha);paint.setStyle(Paint.Style.FILL);paint.setShader(null);
    if(shadowBitmap!=null){
      // A moving edge must never reveal the old exterior shadow inside its face.
      int saved=canvas.save();canvas.clipOutPath(shape);Rect bounds=getBounds();
      canvas.drawBitmap(shadowBitmap,bounds.left,bounds.top,paint);canvas.restoreToCount(saved);
    }
    paint.setShader(fill);canvas.drawPath(shape,paint);
    paint.setStyle(Paint.Style.STROKE);paint.setStrokeWidth(edgeWidth);paint.setShader(outerLine);canvas.drawPath(shape,paint);
    paint.setStrokeCap(Paint.Cap.ROUND);paint.setStrokeJoin(Paint.Join.ROUND);
    int saved=canvas.save();canvas.clipPath(shape);
    drawBand(canvas,ambient,.46f*(1f-.35f*strength));drawBand(canvas,ambientCounter,.28f*(1f-.25f*strength));
    if(strength>0f){drawBand(canvas,moving,strength);drawBand(canvas,movingCounter,strength*.5f);}
    canvas.restoreToCount(saved);paint.setShader(null);paint.setAlpha(alpha);
  }

  private void drawBand(Canvas canvas,Band band,float energy){
    if(energy<=0f)return;
    paint.setAlpha(Math.round(alpha*energy));paint.setShader(band.shade);
    paint.setStrokeWidth((2.4f+1.4f*energy)*density);canvas.drawPath(band.edge,paint);
    paint.setShader(band.bright);paint.setStrokeWidth((.8f+.85f*energy)*density);canvas.drawPath(band.edge,paint);
    paint.setAlpha(Math.round(alpha*energy*.48f));paint.setStrokeWidth((.8f+.35f*energy)*density);canvas.drawPath(band.caustic,paint);
  }

  @Override public void getOutline(Outline outline){
    Rect bounds=getBounds();if(bounds.isEmpty()){outline.setEmpty();return;}
    outline.setRoundRect(bounds,Math.min(requestedRadius,Math.min(bounds.width(),bounds.height())/2f));outline.setAlpha(0f);
  }
  @Override public void setAlpha(int value){int next=Math.max(0,Math.min(255,value));if(alpha!=next){alpha=next;invalidateSelf();}}
  @Override public int getAlpha(){return alpha;}
  @Override public void setColorFilter(ColorFilter filter){paint.setColorFilter(filter);invalidateSelf();}
  @Override public int getOpacity(){return PixelFormat.TRANSLUCENT;}
}
