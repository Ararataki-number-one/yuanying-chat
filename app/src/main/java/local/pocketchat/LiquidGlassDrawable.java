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
 * A smoke-gray center, quiet shoulder reflections and a narrow cyan return keep
 * light labels readable on either appearance. These are static optical cues, not a sample or a
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
  private Shader fill,coolReflection,shoulderReflection,broadReflection,edgeTint,mainGlint,oppositeGlint,farShade,nearShade;
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
      dark?new int[]{0x00080d14,0x00080d14,0x24080d14}:new int[]{0x00212e3b,0x00212e3b,0x0f212e3b},
      new float[]{0f,.42f,1f},Shader.TileMode.CLAMP);
    nearShade=new LinearGradient(0,near.top,0,near.bottom,
      dark?new int[]{0x00040810,0x00040810,0x2a040810}:new int[]{0x00212e3b,0x00212e3b,0x15212e3b},
      new float[]{0f,.55f,1f},Shader.TileMode.CLAMP);

    // A stable 84-88% smoke tint supports white foregrounds even over a white
    // page. Reflection colors stay neutral; cyan is limited to a weak return.
    fill=new LinearGradient(body.left,body.top,body.left,body.bottom,
      dark?new int[]{0xe0343f4c,0xdc26313e,0xe0212b37}
          :new int[]{0xd82c3745,0xdc202a36,0xe0212a35},
      new float[]{0f,.48f,1f},Shader.TileMode.CLAMP);
    coolReflection=reflection(body.left+body.width()*.12f,body.bottom+body.height()*.12f,
      Math.max(body.width()*.58f,body.height()),body.height()*.92f,
      dark?0x1c73bac9:0x1473bac9);
    shoulderReflection=reflection(body.right-body.width()*.08f,body.top-body.height()*.1f,
      Math.max(body.width()*.4f,body.height()*.8f),body.height()*.95f,
      dark?0x28a8b2be:0x22a8b2be);
    broadReflection=reflection(body.left+body.width()*.35f,body.top-body.height()*.25f,
      Math.max(body.width()*.72f,body.height()),body.height()*1.25f,
      dark?0x30a8b5c2:0x2aa8b5c2);

    // Keep the short highlight inside the dark surface so its full width stays
    // visible on a pale canvas. It fades after the left shoulder, never a ring.
    float straight=Math.max(0,body.width()-2*radius);
    float highlightInset=Math.min(density,radius*.25f);
    float highlightLeft=body.left+highlightInset,highlightTop=body.top+highlightInset;
    float highlightRadius=Math.max(0,radius-highlightInset);
    float topEnd=highlightLeft+highlightRadius+straight*.28f;
    mainReflection.rewind();
    mainReflection.moveTo(highlightLeft,highlightTop+highlightRadius);
    corner.set(highlightLeft,highlightTop,highlightLeft+2*highlightRadius,highlightTop+2*highlightRadius);
    mainReflection.arcTo(corner,180,90,false);
    mainReflection.lineTo(topEnd,highlightTop);
    mainGlint=new LinearGradient(highlightLeft,highlightTop,Math.max(highlightLeft+density,topEnd),highlightTop,
      new int[]{0x00f0f6fc,0xc8f6fbff,0x78eaf4fc,0x00eaf4fc},
      new float[]{0f,.34f,.68f,1f},Shader.TileMode.CLAMP);

    float bottomStart=body.left+radius+straight*.36f;
    oppositeReflection.rewind();
    oppositeReflection.moveTo(bottomStart,body.bottom);
    oppositeReflection.lineTo(body.right-radius,body.bottom);
    corner.set(body.right-2*radius,body.bottom-2*radius,body.right,body.bottom);
    oppositeReflection.arcTo(corner,90,-90,false);
    oppositeGlint=new LinearGradient(Math.min(bottomStart,body.right-density),body.bottom,body.right,body.bottom,
      dark?new int[]{0x008dc3d0,0x508dc3d0,0x26becdd9,0x00becdd9}
          :new int[]{0x008dc3d0,0x3d8dc3d0,0x20becdd9,0x00becdd9},
      new float[]{0f,.58f,.88f,1f},Shader.TileMode.CLAMP);
    edgeTint=new LinearGradient(body.left,body.top,body.right,body.bottom,
      dark?new int[]{0x14c7d4e2,0x00c7d4e2,0x0088a4b5,0x1888a4b5}
          :new int[]{0x12c7d4e2,0x00c7d4e2,0x0088a4b5,0x1288a4b5},
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
    paint.setShader(shoulderReflection);canvas.drawRoundRect(body,radius,radius,paint);
    paint.setShader(broadReflection);canvas.drawRoundRect(body,radius,radius,paint);
    paint.setStyle(Paint.Style.STROKE);paint.setStrokeWidth(edgeWidth);
    paint.setShader(edgeTint);canvas.drawRoundRect(body,radius,radius,paint);
    paint.setStrokeCap(Paint.Cap.ROUND);paint.setStrokeWidth(Math.max(1f,density));
    paint.setShader(mainGlint);canvas.drawPath(mainReflection,paint);
    paint.setStrokeWidth(Math.max(1f,.55f*density));
    paint.setShader(oppositeGlint);canvas.drawPath(oppositeReflection,paint);
    paint.setShader(null);
  }

  @Override public void getOutline(Outline outline){
    Rect bounds=getBounds();
    if(bounds.isEmpty()){outline.setEmpty();return;}
    outline.setRoundRect(bounds,Math.min(requestedRadius,Math.min(bounds.width(),bounds.height())/2f));
    // Keep the useful rounded outline, but never cast a filled shadow under the
    // lens. The two cached exterior bands above supply its contact shadow.
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
