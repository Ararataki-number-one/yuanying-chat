package local.pocketchat;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BlurMaskFilter;
import android.graphics.Canvas;
import android.graphics.ColorFilter;
import android.graphics.LinearGradient;
import android.graphics.Outline;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.PixelFormat;
import android.graphics.PorterDuff;
import android.graphics.PorterDuffXfermode;
import android.graphics.Rect;
import android.graphics.RectF;
import android.graphics.Shader;
import android.graphics.drawable.Drawable;

/**
 * Thin native glass for the address capsule and both navigation surfaces.
 *
 * A nearly clear center, fine contour and two short reflections sit over a
 * single soft exterior shadow. There is no continuous bevel or inner frame.
 * This is static native chrome, not a sample or refraction of Gecko content.
 * Text and icons remain separate native foregrounds with their normal palette.
 *
 * Paths, shaders and the software-blurred shadow are prepared only when bounds
 * or appearance change. Drawing has no snapshots, timers or allocations and
 * keeps the view hardware accelerated on every supported API level.
 */
class LiquidGlassDrawable extends Drawable {
  static final int INSET_DP=4;
  private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
  private final RectF body=new RectF(),reflectionEdge=new RectF(),corner=new RectF();
  private final Path mainReflection=new Path(),oppositeReflection=new Path();
  private final float density,requestedRadius,edgeWidth;
  private float radius;
  private Shader fill,outerLine,mainGlint,oppositeGlint;
  private Bitmap shadowBitmap;
  private int alpha=255;
  private boolean dark;

  LiquidGlassDrawable(Context context,int radiusDp){
    density=context.getResources().getDisplayMetrics().density;
    requestedRadius=Math.max(0,radiusDp*density);
    edgeWidth=.5f*density;
    dark=AppAppearance.dark();
  }

  /** Invoked by the existing event-driven appearance dispatcher. */
  void refresh(){
    boolean next=AppAppearance.dark();
    if(dark==next)return;
    dark=next;prepare();invalidateSelf();
  }

  @Override protected void onBoundsChange(Rect bounds){prepare();}

  private void prepare(){
    Rect bounds=getBounds();
    float inset=INSET_DP*density;
    if(bounds.width()<=2*inset||bounds.height()<=2*inset){
      body.setEmpty();shadowBitmap=null;return;
    }
    body.set(bounds);body.inset(inset,inset);
    radius=Math.min(Math.max(0,requestedRadius-inset),Math.min(body.width(),body.height())/2f);
    prepareShadow(bounds);

    // Light mode has only an 11-14% white tint, with no gray or colored backing.
    fill=new LinearGradient(body.left,body.top,body.left,body.bottom,
      dark?new int[]{0x42222934,0x30202630,0x3d1e252f}
          :new int[]{0x23ffffff,0x1fffffff,0x1cffffff},
      new float[]{0f,.48f,1f},Shader.TileMode.CLAMP);

    // A half-dp contour defines the surface without making a hard gray frame.
    outerLine=new LinearGradient(body.left,body.top,body.left,body.bottom,
      dark?new int[]{0x16ffffff,0x10ffffff}:new int[]{0x0c000000,0x10000000},
      null,Shader.TileMode.CLAMP);
    float reflectionInset=Math.min(.75f*density,Math.min(body.width(),body.height())/4f);
    reflectionEdge.set(body);reflectionEdge.inset(reflectionInset,reflectionInset);
    float reflectionRadius=Math.max(0,radius-reflectionInset);

    // Short local glints replace the old continuous white inner line and bevel.
    float straight=Math.max(0,reflectionEdge.width()-2*reflectionRadius);
    float topEnd=reflectionEdge.left+reflectionRadius+straight*.18f;
    mainReflection.rewind();
    mainReflection.moveTo(reflectionEdge.left,reflectionEdge.top+reflectionRadius);
    corner.set(reflectionEdge.left,reflectionEdge.top,reflectionEdge.left+2*reflectionRadius,reflectionEdge.top+2*reflectionRadius);
    mainReflection.arcTo(corner,180,90,false);
    mainReflection.lineTo(topEnd,reflectionEdge.top);
    mainGlint=new LinearGradient(reflectionEdge.left,reflectionEdge.top,Math.max(reflectionEdge.left+density,topEnd),reflectionEdge.top,
      dark?new int[]{0x00ffffff,0x98ffffff,0x58ffffff,0x00ffffff}
          :new int[]{0x00ffffff,0xb8ffffff,0x70ffffff,0x00ffffff},
      new float[]{0f,.34f,.68f,1f},Shader.TileMode.CLAMP);

    float bottomStart=reflectionEdge.left+reflectionRadius+straight*.78f;
    oppositeReflection.rewind();
    oppositeReflection.moveTo(bottomStart,reflectionEdge.bottom);
    oppositeReflection.lineTo(reflectionEdge.right-reflectionRadius,reflectionEdge.bottom);
    corner.set(reflectionEdge.right-2*reflectionRadius,reflectionEdge.bottom-2*reflectionRadius,reflectionEdge.right,reflectionEdge.bottom);
    oppositeReflection.arcTo(corner,90,-90,false);
    oppositeGlint=new LinearGradient(Math.min(bottomStart,reflectionEdge.right-density),reflectionEdge.bottom,reflectionEdge.right,reflectionEdge.bottom,
      new int[]{0x00ffffff,0x60ffffff,0x30ffffff,0x00ffffff},
      new float[]{0f,.58f,.88f,1f},Shader.TileMode.CLAMP);
  }

  private void prepareShadow(Rect bounds){
    Bitmap next=Bitmap.createBitmap(bounds.width(),bounds.height(),Bitmap.Config.ARGB_8888);
    // Bounds and geometry are already physical pixels; never density-scale the cache.
    next.setDensity(Bitmap.DENSITY_NONE);
    Canvas offscreen=new Canvas(next);
    Paint shadowPaint=new Paint(Paint.ANTI_ALIAS_FLAG);
    shadowPaint.setColor(dark?0x18000000:0x16000000);
    shadowPaint.setMaskFilter(new BlurMaskFilter(2.5f*density,BlurMaskFilter.Blur.NORMAL));
    RectF localBody=new RectF(body);
    localBody.offset(-bounds.left,-bounds.top);
    float drop=.75f*density;
    localBody.offset(0,drop);
    offscreen.drawRoundRect(localBody,radius,radius,shadowPaint);

    // BlurMaskFilter runs only on this software bitmap Canvas. Remove every
    // interior pixel at the actual, unshifted body so it cannot gray the center.
    localBody.offset(0,-drop);
    shadowPaint.setMaskFilter(null);
    shadowPaint.setAlpha(255);
    shadowPaint.setXfermode(new PorterDuffXfermode(PorterDuff.Mode.CLEAR));
    offscreen.drawRoundRect(localBody,radius,radius,shadowPaint);
    offscreen.setBitmap(null);
    // Do not recycle the old cache: a recorded RenderThread frame may still use it.
    shadowBitmap=next;
  }

  @Override public void draw(Canvas canvas){
    if(body.isEmpty()||alpha==0)return;
    paint.setAlpha(alpha);paint.setStyle(Paint.Style.FILL);paint.setShader(null);
    if(shadowBitmap!=null){
      Rect bounds=getBounds();
      canvas.drawBitmap(shadowBitmap,bounds.left,bounds.top,paint);
    }
    paint.setShader(fill);canvas.drawRoundRect(body,radius,radius,paint);
    paint.setStyle(Paint.Style.STROKE);paint.setStrokeWidth(edgeWidth);
    paint.setShader(outerLine);canvas.drawRoundRect(body,radius,radius,paint);
    paint.setStrokeCap(Paint.Cap.ROUND);paint.setStrokeWidth(.75f*density);
    paint.setShader(mainGlint);canvas.drawPath(mainReflection,paint);
    paint.setStrokeWidth(.55f*density);
    paint.setShader(oppositeGlint);canvas.drawPath(oppositeReflection,paint);
    paint.setShader(null);
  }

  @Override public void getOutline(Outline outline){
    Rect bounds=getBounds();
    if(bounds.isEmpty()){outline.setEmpty();return;}
    outline.setRoundRect(bounds,Math.min(requestedRadius,Math.min(bounds.width(),bounds.height())/2f));
    // The cached exterior shadow replaces the filled native elevation shadow.
    outline.setAlpha(0f);
  }

  @Override public void setAlpha(int value){
    int next=Math.max(0,Math.min(255,value));
    if(alpha!=next){alpha=next;invalidateSelf();}
  }
  @Override public int getAlpha(){return alpha;}
  @Override public void setColorFilter(ColorFilter filter){paint.setColorFilter(filter);invalidateSelf();}
  @Override public int getOpacity(){return PixelFormat.TRANSLUCENT;}
}
