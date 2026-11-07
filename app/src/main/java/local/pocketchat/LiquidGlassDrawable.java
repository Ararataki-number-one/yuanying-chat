package local.pocketchat;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.ColorFilter;
import android.graphics.LinearGradient;
import android.graphics.Outline;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.PixelFormat;
import android.graphics.Rect;
import android.graphics.RectF;
import android.graphics.Shader;
import android.graphics.drawable.Drawable;

/**
 * Shared native glass for the address capsule and both navigation surfaces.
 *
 * The light material has a nearly clear white tint. Its volume comes only from
 * a thin paired contour, a shallow inner bevel and local white reflections.
 * This is static native chrome, not a sample or refraction of Gecko content.
 * Text and icons remain separate native foregrounds with their normal palette.
 *
 * Geometry and shaders are cached on bounds/theme changes. Drawing has no
 * snapshots, timers, allocations or APIs newer than the app's minimum SDK.
 */
class LiquidGlassDrawable extends Drawable {
  static final int INSET_DP=2;
  private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
  private final RectF body=new RectF(),outer=new RectF(),near=new RectF(),innerEdge=new RectF(),bevelInner=new RectF(),corner=new RectF();
  private final Path farShadow=new Path(),nearShadow=new Path(),bevelRing=new Path(),mainReflection=new Path(),oppositeReflection=new Path();
  private final float density,requestedRadius,edgeWidth;
  private float radius,innerRadius;
  private Shader fill,bevel,outerLine,innerLine,mainGlint,oppositeGlint,farShade,nearShade;
  private int alpha=255;
  private boolean dark;

  LiquidGlassDrawable(Context context,int radiusDp){
    density=context.getResources().getDisplayMetrics().density;
    requestedRadius=Math.max(0,radiusDp*density);
    edgeWidth=.6f*density;
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

    // Both shadow bands exclude the body. Their combined peak is below 9%,
    // leaving the center clear instead of filling it with an elevation shadow.
    outer.set(bounds);outer.inset(.2f*density,.2f*density);
    near.set(bounds);near.inset(.9f*density,.9f*density);
    outsideBand(farShadow,outer,Math.max(0,requestedRadius-.2f*density));
    outsideBand(nearShadow,near,Math.max(0,requestedRadius-.9f*density));
    farShade=new LinearGradient(0,outer.top,0,outer.bottom,
      new int[]{0x00000000,0x00000000,0x07000000},
      new float[]{0f,.42f,1f},Shader.TileMode.CLAMP);
    nearShade=new LinearGradient(0,near.top,0,near.bottom,
      new int[]{0x00000000,0x00000000,0x10000000},
      new float[]{0f,.55f,1f},Shader.TileMode.CLAMP);

    // Light mode is only 11-14% white: no smoke, blue-gray backing or broad
    // colored reflection. Dark mode has its own quiet translucent neutral tint.
    fill=new LinearGradient(body.left,body.top,body.left,body.bottom,
      dark?new int[]{0x42222934,0x30202630,0x3d1e252f}
          :new int[]{0x23ffffff,0x1fffffff,0x1cffffff},
      new float[]{0f,.48f,1f},Shader.TileMode.CLAMP);

    // Restrict the bevel to the inner 2.5 dp. In light mode its upper face is
    // 35% white and its lower face only 4.7% black; neither reaches the center.
    float bevelInset=Math.min(2.5f*density,Math.min(body.width(),body.height())/4f);
    bevelInner.set(body);bevelInner.inset(bevelInset,bevelInset);
    float bevelRadius=Math.max(0,radius-bevelInset);
    bevelRing.rewind();bevelRing.setFillType(Path.FillType.EVEN_ODD);
    bevelRing.addRoundRect(body,radius,radius,Path.Direction.CW);
    bevelRing.addRoundRect(bevelInner,bevelRadius,bevelRadius,Path.Direction.CW);
    bevel=new LinearGradient(body.left,body.top,body.left,body.bottom,
      dark?new int[]{0x30ffffff,0x00ffffff,0x00000000,0x08000000}
          :new int[]{0x59ffffff,0x00ffffff,0x00000000,0x0c000000},
      new float[]{0f,.24f,.68f,1f},Shader.TileMode.CLAMP);

    // The complete contour is deliberately very fine: a 0.6 dp dark outside
    // line and a 0.5 dp white inside line, rather than a thick white frame.
    outerLine=new LinearGradient(body.left,body.top,body.left,body.bottom,
      dark?new int[]{0x30ffffff,0x18ffffff}:new int[]{0x1a000000,0x1e000000},
      null,Shader.TileMode.CLAMP);
    innerLine=new LinearGradient(body.left,body.top,body.left,body.bottom,
      dark?new int[]{0x2effffff,0x2effffff}:new int[]{0x40ffffff,0x40ffffff},
      null,Shader.TileMode.CLAMP);
    float innerInset=Math.min(density,Math.min(body.width(),body.height())/4f);
    innerEdge.set(body);innerEdge.inset(innerInset,innerInset);
    innerRadius=Math.max(0,radius-innerInset);

    // Local glints sit on the inner edge. Both fade out before forming a ring.
    float straight=Math.max(0,innerEdge.width()-2*innerRadius);
    float topEnd=innerEdge.left+innerRadius+straight*.28f;
    mainReflection.rewind();
    mainReflection.moveTo(innerEdge.left,innerEdge.top+innerRadius);
    corner.set(innerEdge.left,innerEdge.top,innerEdge.left+2*innerRadius,innerEdge.top+2*innerRadius);
    mainReflection.arcTo(corner,180,90,false);
    mainReflection.lineTo(topEnd,innerEdge.top);
    mainGlint=new LinearGradient(innerEdge.left,innerEdge.top,Math.max(innerEdge.left+density,topEnd),innerEdge.top,
      dark?new int[]{0x00ffffff,0xb8ffffff,0x70ffffff,0x00ffffff}
          :new int[]{0x00ffffff,0xd4ffffff,0x88ffffff,0x00ffffff},
      new float[]{0f,.34f,.68f,1f},Shader.TileMode.CLAMP);

    float bottomStart=innerEdge.left+innerRadius+straight*.42f;
    oppositeReflection.rewind();
    oppositeReflection.moveTo(bottomStart,innerEdge.bottom);
    oppositeReflection.lineTo(innerEdge.right-innerRadius,innerEdge.bottom);
    corner.set(innerEdge.right-2*innerRadius,innerEdge.bottom-2*innerRadius,innerEdge.right,innerEdge.bottom);
    oppositeReflection.arcTo(corner,90,-90,false);
    oppositeGlint=new LinearGradient(Math.min(bottomStart,innerEdge.right-density),innerEdge.bottom,innerEdge.right,innerEdge.bottom,
      new int[]{0x00ffffff,0x70ffffff,0x38ffffff,0x00ffffff},
      new float[]{0f,.58f,.88f,1f},Shader.TileMode.CLAMP);
  }

  private void outsideBand(Path path,RectF edge,float edgeRadius){
    path.rewind();path.setFillType(Path.FillType.EVEN_ODD);
    float r=Math.min(edgeRadius,Math.min(edge.width(),edge.height())/2f);
    path.addRoundRect(edge,r,r,Path.Direction.CW);
    path.addRoundRect(body,radius,radius,Path.Direction.CW);
  }

  @Override public void draw(Canvas canvas){
    if(body.isEmpty()||alpha==0)return;
    paint.setAlpha(alpha);paint.setStyle(Paint.Style.FILL);
    paint.setShader(farShade);canvas.drawPath(farShadow,paint);
    paint.setShader(nearShade);canvas.drawPath(nearShadow,paint);
    paint.setShader(fill);canvas.drawRoundRect(body,radius,radius,paint);
    paint.setShader(bevel);canvas.drawPath(bevelRing,paint);
    paint.setStyle(Paint.Style.STROKE);paint.setStrokeWidth(edgeWidth);
    paint.setShader(outerLine);canvas.drawRoundRect(body,radius,radius,paint);
    paint.setStrokeWidth(.5f*density);
    paint.setShader(innerLine);canvas.drawRoundRect(innerEdge,innerRadius,innerRadius,paint);
    paint.setStrokeCap(Paint.Cap.ROUND);paint.setStrokeWidth(density);
    paint.setShader(mainGlint);canvas.drawPath(mainReflection,paint);
    paint.setStrokeWidth(.8f*density);
    paint.setShader(oppositeGlint);canvas.drawPath(oppositeReflection,paint);
    paint.setShader(null);
  }

  @Override public void getOutline(Outline outline){
    Rect bounds=getBounds();
    if(bounds.isEmpty()){outline.setEmpty();return;}
    outline.setRoundRect(bounds,Math.min(requestedRadius,Math.min(bounds.width(),bounds.height())/2f));
    // Keep the rounded outline but suppress its filled elevation shadow.
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
