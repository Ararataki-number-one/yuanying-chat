package local.pocketchat;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.ColorFilter;
import android.graphics.LinearGradient;
import android.graphics.Outline;
import android.graphics.Paint;
import android.graphics.PixelFormat;
import android.graphics.RadialGradient;
import android.graphics.Rect;
import android.graphics.RectF;
import android.graphics.Shader;
import android.graphics.drawable.Drawable;

/**
 * The shared glass surface treatment for native chrome.
 *
 * Its translucent center, directional rim and weak ambient reflection follow the
 * same material at both ends of the screen. This drawable does not sample or
 * refract the separate Gecko compositor. Chrome currently sits outside the web
 * viewport, so it must not pretend that a decorative shader is live page blur.
 * All geometry and gradients are cached on size/appearance changes; drawing has
 * no snapshots, timers, per-frame allocations or dependencies on newer APIs.
 */
class LiquidGlassDrawable extends Drawable {
  private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
  private final RectF body=new RectF(),inner=new RectF();
  private final float density,requestedRadius,edgeWidth;
  private float radius,innerRadius;
  private Shader fill,ambient,rim,inset;
  private int alpha=255;
  private boolean dark;

  LiquidGlassDrawable(Context context,int radiusDp){
    density=context.getResources().getDisplayMetrics().density;
    requestedRadius=Math.max(0,radiusDp*density);
    edgeWidth=Math.max(1f,.7f*density);
    refresh();
  }

  /** Invoked by the existing app-wide appearance dispatcher. */
  void refresh(){dark=AppAppearance.dark();prepare();invalidateSelf();}

  @Override protected void onBoundsChange(Rect bounds){prepare();}

  private void prepare(){
    Rect bounds=getBounds();
    if(bounds.width()<=edgeWidth||bounds.height()<=edgeWidth){body.setEmpty();return;}
    body.set(bounds);
    body.inset(edgeWidth/2f,edgeWidth/2f);
    radius=Math.min(requestedRadius,Math.min(body.width(),body.height())/2f);
    float innerEdge=Math.min(density,Math.min(body.width(),body.height())/4f);
    inner.set(body);inner.inset(innerEdge,innerEdge);
    innerRadius=Math.max(0,radius-innerEdge);

    // Keep the center clear. Opacity belongs to the surface, never its labels.
    fill=new LinearGradient(body.left,body.top,body.left,body.bottom,
      dark?new int[]{0x8a424955,0x66242b36,0x94202933}
          :new int[]{0x78ffffff,0x4df5faff,0x7aedf2f8},
      new float[]{0f,.5f,1f},Shader.TileMode.CLAMP);
    ambient=new RadialGradient(body.left+body.width()*.22f,body.top-body.height()*.4f,
      Math.max(body.width()*.85f,body.height()*1.8f),
      dark?new int[]{0x1fcbdcff,0x00cbdcff}:new int[]{0x2effffff,0x00ffffff},
      null,Shader.TileMode.CLAMP);

    // Light is directional: the middle of the rim fades, avoiding a white ring.
    rim=new LinearGradient(body.left,body.top,body.right,body.bottom,
      dark?new int[]{0x86d2dfff,0x0dd2dfff,0x0a101827,0x36a8bad7}
          :new int[]{0xe6ffffff,0x15ffffff,0x182f4b70,0x66ffffff},
      new float[]{0f,.43f,.75f,1f},Shader.TileMode.CLAMP);
    inset=new LinearGradient(body.left,body.top,body.left,body.bottom,
      dark?new int[]{0x25dbe6ff,0x00dbe6ff,0x28090f1a}
          :new int[]{0x42ffffff,0x00ffffff,0x173c5a84},
      new float[]{0f,.44f,1f},Shader.TileMode.CLAMP);
  }

  @Override public void draw(Canvas canvas){
    if(body.isEmpty()||alpha==0)return;
    paint.setAlpha(alpha);
    paint.setStyle(Paint.Style.FILL);
    paint.setShader(fill);canvas.drawRoundRect(body,radius,radius,paint);
    paint.setShader(ambient);canvas.drawRoundRect(body,radius,radius,paint);
    paint.setStyle(Paint.Style.STROKE);
    paint.setStrokeWidth(edgeWidth);
    paint.setShader(rim);canvas.drawRoundRect(body,radius,radius,paint);
    paint.setStrokeWidth(Math.max(1f,.5f*density));
    paint.setShader(inset);canvas.drawRoundRect(inner,innerRadius,innerRadius,paint);
    paint.setShader(null);
  }

  @Override public void getOutline(Outline outline){
    Rect bounds=getBounds();
    if(bounds.isEmpty()){outline.setEmpty();return;}
    outline.setRoundRect(bounds,Math.min(requestedRadius,Math.min(bounds.width(),bounds.height())/2f));
    outline.setAlpha(.42f*alpha/255f);
  }

  @Override public void setAlpha(int value){
    int next=Math.max(0,Math.min(255,value));
    if(alpha!=next){alpha=next;invalidateSelf();}
  }
  @Override public int getAlpha(){return alpha;}
  @Override public void setColorFilter(ColorFilter filter){paint.setColorFilter(filter);invalidateSelf();}
  @Override public int getOpacity(){return PixelFormat.TRANSLUCENT;}
}
