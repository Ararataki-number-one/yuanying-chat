package local.pocketchat;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.ColorFilter;
import android.graphics.LinearGradient;
import android.graphics.Matrix;
import android.graphics.Outline;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.PixelFormat;
import android.graphics.RadialGradient;
import android.graphics.Rect;
import android.graphics.RectF;
import android.graphics.Shader;
import android.graphics.drawable.Drawable;

/**
 * One native lens material for the address capsule and both navigation surfaces.
 *
 * A clear center, weak environmental color and two directional reflections follow
 * Lens's material contract. These are static optical cues, not a sample or a
 * refraction of the separate Gecko compositor. Labels are drawn by their native
 * views above this surface and are never blurred or colored by the material.
 *
 * Geometry and shaders are cached on bounds/theme changes. There are no snapshots,
 * timers, allocations inside draw(), or APIs newer than the app's minimum SDK.
 */
class LiquidGlassDrawable extends Drawable {
  static final int INSET_DP=2;
  private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
  private final RectF body=new RectF(),outer=new RectF(),near=new RectF(),corner=new RectF();
  private final Path farShadow=new Path(),nearShadow=new Path(),mainReflection=new Path(),oppositeReflection=new Path();
  private final Matrix reflectionMatrix=new Matrix();
  private final float density,requestedRadius,edgeWidth;
  private float radius;
  private Shader fill,coolReflection,warmReflection,broadReflection,edgeTint,mainGlint,oppositeGlint,farShade,nearShade;
  private int alpha=255;
  private boolean dark;

  LiquidGlassDrawable(Context context,int radiusDp){
    density=context.getResources().getDisplayMetrics().density;
    requestedRadius=Math.max(0,radiusDp*density);
    edgeWidth=Math.max(1f,.65f*density);
    refresh();
  }

  /** Invoked by the existing event-driven appearance dispatcher. */
  void refresh(){dark=AppAppearance.dark();prepare();invalidateSelf();}

  @Override protected void onBoundsChange(Rect bounds){prepare();}

  private void prepare(){
    Rect bounds=getBounds();
    float inset=INSET_DP*density;
    if(bounds.width()<=2*inset||bounds.height()<=2*inset){body.setEmpty();return;}
    body.set(bounds);body.inset(inset,inset);
    radius=Math.min(Math.max(0,requestedRadius-inset),Math.min(body.width(),body.height())/2f);

    // Shadow belongs outside the lens. A normal elevation shadow also fills its
    // interior, and shows through a transparent center as an opaque gray plate.
    outer.set(bounds);outer.inset(.2f*density,.2f*density);
    near.set(bounds);near.inset(.9f*density,.9f*density);
    outsideBand(farShadow,outer,Math.max(0,requestedRadius-.2f*density));
    outsideBand(nearShadow,near,Math.max(0,requestedRadius-.9f*density));
    farShade=new LinearGradient(0,outer.top,0,outer.bottom,
      dark?new int[]{0x00121b2a,0x00121b2a,0x10121b2a}:new int[]{0x00465770,0x00465770,0x08465770},
      new float[]{0f,.42f,1f},Shader.TileMode.CLAMP);
    nearShade=new LinearGradient(0,near.top,0,near.bottom,
      dark?new int[]{0x00040810,0x00040810,0x20040810}:new int[]{0x00465770,0x00465770,0x0c465770},
      new float[]{0f,.55f,1f},Shader.TileMode.CLAMP);

    // Low-density tint lets the native surface show through the center. Color
    // comes from quiet cyan/blue and peach reflections, not from a gray backing.
    fill=new LinearGradient(body.left,body.top,body.left,body.bottom,
      dark?new int[]{0x3a26344c,0x10202a3c,0x2626354c}
          :new int[]{0x30ffffff,0x12f7fbff,0x20eef6ff},
      new float[]{0f,.48f,1f},Shader.TileMode.CLAMP);
    coolReflection=reflection(body.left+body.width()*.12f,body.bottom+body.height()*.12f,
      Math.max(body.width()*.58f,body.height()),body.height()*.92f,
      dark?0x326a9cdb:0x289db7dc);
    warmReflection=reflection(body.right-body.width()*.08f,body.top-body.height()*.1f,
      Math.max(body.width()*.4f,body.height()*.8f),body.height()*.95f,
      dark?0x1fc99bc2:0x2ceccbc1);
    broadReflection=reflection(body.left+body.width()*.35f,body.top-body.height()*.25f,
      Math.max(body.width()*.72f,body.height()),body.height()*1.25f,
      dark?0x147db9e2:0x26ffffff);

    // Only the lit shoulders shine. Their paths fade before completing a ring.
    float straight=Math.max(0,body.width()-2*radius);
    float topEnd=body.left+radius+straight*.68f;
    mainReflection.rewind();
    mainReflection.moveTo(body.left,body.top+radius+Math.min(body.height()*.12f,radius*.2f));
    mainReflection.lineTo(body.left,body.top+radius);
    corner.set(body.left,body.top,body.left+2*radius,body.top+2*radius);
    mainReflection.arcTo(corner,180,90,false);
    mainReflection.lineTo(topEnd,body.top);
    mainGlint=new LinearGradient(body.left,body.top,Math.max(body.left+density,topEnd),body.top,
      dark?new int[]{0x00e5f6ff,0xb8e5f6ff,0x52c2e7fa,0x00c2e7fa}
          :new int[]{0x00ffffff,0xb3ffffff,0x8cffffff,0x00ffffff},
      new float[]{0f,.2f,.64f,1f},Shader.TileMode.CLAMP);

    float bottomStart=body.left+radius+straight*.36f;
    oppositeReflection.rewind();
    oppositeReflection.moveTo(bottomStart,body.bottom);
    oppositeReflection.lineTo(body.right-radius,body.bottom);
    corner.set(body.right-2*radius,body.bottom-2*radius,body.right,body.bottom);
    oppositeReflection.arcTo(corner,90,-90,false);
    oppositeGlint=new LinearGradient(Math.min(bottomStart,body.right-density),body.bottom,body.right,body.bottom,
      dark?new int[]{0x006e9fc7,0x5578b2df,0x298e9fcf,0x008e9fcf}
          :new int[]{0x009bc6e2,0x759bc6e2,0x42e4c6cd,0x00e4c6cd},
      new float[]{0f,.58f,.88f,1f},Shader.TileMode.CLAMP);
    edgeTint=new LinearGradient(body.left,body.top,body.right,body.bottom,
      dark?new int[]{0x0c95cbe4,0x0095cbe4,0x007c9bbd,0x297c9bbd}
          :new int[]{0x1297bfd8,0x0097bfd8,0x00839fbf,0x21839fbf},
      new float[]{0f,.35f,.7f,1f},Shader.TileMode.CLAMP);
  }

  private void outsideBand(Path path,RectF edge,float edgeRadius){
    path.rewind();path.setFillType(Path.FillType.EVEN_ODD);
    float r=Math.min(edgeRadius,Math.min(edge.width(),edge.height())/2f);
    path.addRoundRect(edge,r,r,Path.Direction.CW);
    path.addRoundRect(body,radius,radius,Path.Direction.CW);
  }

  private Shader reflection(float x,float y,float width,float height,int color){
    Shader shader=new RadialGradient(0,0,1,new int[]{color,color&0x00ffffff},null,Shader.TileMode.CLAMP);
    reflectionMatrix.setScale(Math.max(1,width),Math.max(1,height));
    reflectionMatrix.postTranslate(x,y);shader.setLocalMatrix(reflectionMatrix);return shader;
  }

  @Override public void draw(Canvas canvas){
    if(body.isEmpty()||alpha==0)return;
    paint.setAlpha(alpha);paint.setStyle(Paint.Style.FILL);
    paint.setShader(farShade);canvas.drawPath(farShadow,paint);
    paint.setShader(nearShade);canvas.drawPath(nearShadow,paint);
    paint.setShader(fill);canvas.drawRoundRect(body,radius,radius,paint);
    paint.setShader(coolReflection);canvas.drawRoundRect(body,radius,radius,paint);
    paint.setShader(warmReflection);canvas.drawRoundRect(body,radius,radius,paint);
    paint.setShader(broadReflection);canvas.drawRoundRect(body,radius,radius,paint);
    paint.setStyle(Paint.Style.STROKE);paint.setStrokeWidth(edgeWidth);
    paint.setShader(edgeTint);canvas.drawRoundRect(body,radius,radius,paint);
    paint.setStrokeCap(Paint.Cap.ROUND);
    paint.setShader(mainGlint);canvas.drawPath(mainReflection,paint);
    paint.setStrokeWidth(Math.max(1f,.5f*density));
    paint.setShader(oppositeGlint);canvas.drawPath(oppositeReflection,paint);
    paint.setShader(null);
  }

  @Override public void getOutline(Outline outline){
    Rect bounds=getBounds();
    if(bounds.isEmpty()){outline.setEmpty();return;}
    outline.setRoundRect(bounds,Math.min(requestedRadius,Math.min(bounds.width(),bounds.height())/2f));
    // Keep the useful rounded outline, but never cast a filled shadow under the
    // clear lens. The two cached exterior bands above supply its contact shadow.
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
