package local.pocketchat;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.ColorFilter;
import android.graphics.LinearGradient;
import android.graphics.Outline;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.PixelFormat;
import android.graphics.RadialGradient;
import android.graphics.Rect;
import android.graphics.RectF;
import android.graphics.Shader;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.GradientDrawable;
import android.view.View;

/** Quiet native content surfaces; the shared navigation owns the glass material. */
final class EnvironmentWorkspaceStyle {
  private EnvironmentWorkspaceStyle() {}

  static Drawable card(Context context,boolean featured,boolean selected) {
    GradientDrawable mask=new GradientDrawable();
    mask.setColor(Color.WHITE);
    mask.setCornerRadius(24f*context.getResources().getDisplayMetrics().density);
    // This wrapper also supplies a theme-aware native ripple for non-glass
    // content. It does not add an optical layer to this opaque card surface.
    return new AppAppearance.GlassRipple(new CardSurface(context,featured,selected),mask);
  }

  static Drawable scrollEdge(Context context) {
    return new ScrollEdge();
  }

  /** Shared by the visible footer and its separately recorded native backdrop. */
  private static final class ScrollEdge extends Drawable {
    private final Paint paint=new Paint(Paint.DITHER_FLAG);
    private Shader gradient;
    private int background;
    private boolean dark;
    private int alpha=255;

    @Override protected void onBoundsChange(Rect bounds){prepare();}

    private void prepare() {
      Rect bounds=getBounds();background=DesignUi.BG;dark=AppAppearance.dark();
      if(bounds.isEmpty()){gradient=null;return;}
      int rgb=background&0x00ffffff;
      gradient=new LinearGradient(bounds.left,bounds.top,bounds.left,bounds.bottom,
          new int[]{rgb,0x59000000|rgb,0xd9000000|rgb},
          new float[]{0f,.52f,1f},Shader.TileMode.CLAMP);
    }

    @Override public void draw(Canvas canvas) {
      if(background!=DesignUi.BG||dark!=AppAppearance.dark())prepare();
      if(gradient==null||alpha==0)return;
      paint.setShader(gradient);paint.setAlpha(alpha);canvas.drawRect(getBounds(),paint);
    }

    @Override public void setAlpha(int value) {
      int next=Math.max(0,Math.min(255,value));
      if(alpha!=next){alpha=next;invalidateSelf();}
    }
    @Override public int getAlpha(){return alpha;}
    @Override public void setColorFilter(ColorFilter filter){paint.setColorFilter(filter);invalidateSelf();}
    @Override public int getOpacity(){return PixelFormat.TRANSLUCENT;}
  }

  private static final class CardSurface extends Drawable {
    private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG|Paint.DITHER_FLAG);
    private final RectF face=new RectF(),edge=new RectF();
    private final Path clip=new Path();
    private final float density;
    private final boolean featured,selected;
    private Shader blueWash,mintWash;
    private boolean dark;
    private float radius;
    private int alpha=255;

    CardSurface(Context context,boolean featured,boolean selected) {
      density=context.getResources().getDisplayMetrics().density;
      this.featured=featured;this.selected=selected;dark=AppAppearance.dark();
    }

    @Override protected void onBoundsChange(Rect bounds) {
      face.set(bounds);
      radius=Math.min(24f*density,Math.min(face.width(),face.height())*.5f);
      edge.set(face);edge.inset(.5f*density,.5f*density);
      clip.rewind();
      if(!face.isEmpty())clip.addRoundRect(face,radius,radius,Path.Direction.CW);
      prepareWashes();
    }

    private void prepareWashes() {
      blueWash=mintWash=null;
      if(!featured||face.isEmpty())return;
      // The white center stays almost neutral. Color lives in two broad, faint
      // corners rather than a shiny top-to-bottom bevel or a raised shadow.
      float spread=Math.max(96f*density,face.width()*.67f);
      blueWash=new RadialGradient(face.right-face.width()*.08f,face.top-face.height()*.12f,
          spread,dark?0x204f83cc:0x185f9fea,0x005f9fea,Shader.TileMode.CLAMP);
      mintWash=new RadialGradient(face.right+face.width()*.04f,face.bottom+face.height()*.14f,
          spread*.83f,dark?0x183b9688:0x163bb59f,0x003bb59f,Shader.TileMode.CLAMP);
    }

    @Override public void draw(Canvas canvas) {
      if(face.isEmpty()||alpha==0)return;
      boolean next=AppAppearance.dark();
      if(next!=dark){dark=next;prepareWashes();}
      paint.setShader(null);paint.setStyle(Paint.Style.FILL);
      paint.setColor(withAlpha(selected?(dark?0xff202f46:0xfff0f6ff)
          :dark?(featured?0xff202226:0xff1c1c1e):Color.WHITE,alpha));
      canvas.drawRoundRect(face,radius,radius,paint);
      if(featured){
        int save=canvas.save();canvas.clipPath(clip);
        paint.setColor(Color.WHITE);paint.setAlpha(alpha);
        paint.setShader(blueWash);canvas.drawRect(face,paint);
        paint.setShader(mintWash);canvas.drawRect(face,paint);
        paint.setShader(null);canvas.restoreToCount(save);
      }
      paint.setStyle(Paint.Style.STROKE);
      paint.setStrokeWidth((selected?1f:.65f)*density);
      int rim=selected?(dark?0x9989b5ff:0x660067d8)
          :featured?(dark?0x18ffffff:0xe6ffffff):(dark?0x08ffffff:0x070d263f);
      paint.setColor(withAlpha(rim,alpha));
      float edgeRadius=Math.max(0f,radius-.5f*density);
      canvas.drawRoundRect(edge,edgeRadius,edgeRadius,paint);
      paint.setStyle(Paint.Style.FILL);
    }

    @Override public void getOutline(Outline outline) {
      if(getBounds().isEmpty()){outline.setEmpty();return;}
      outline.setRoundRect(getBounds(),radius);outline.setAlpha(alpha/255f);
    }

    @Override public void setAlpha(int value) {
      int next=Math.max(0,Math.min(255,value));
      if(alpha!=next){alpha=next;invalidateSelf();}
    }
    @Override public int getAlpha(){return alpha;}
    @Override public void setColorFilter(ColorFilter filter){paint.setColorFilter(filter);invalidateSelf();}
    @Override public int getOpacity(){return PixelFormat.TRANSLUCENT;}
  }

  /** Decorative identity mark; the parent row supplies the accessible name. */
  static final class Emblem extends View {
    private static final int[] LIGHT={0xff326ec9,0xff2e857d,0xff7865ad,0xffa77c3c,
        0xffa46180,0xff5a7d95,0xff62856e,0xff626eb0};
    private static final int[] DARK={0xff98b9ef,0xff8fc9bd,0xffc0abe3,0xffdec49c,
        0xffdfa8c0,0xffa4bfce,0xffaac8b1,0xffadb8ec};
    private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
    private final RectF body=new RectF(),edge=new RectF();
    private final Ui.Icon icon=new Ui.Icon("window",LIGHT[0]);
    private final float density;
    private final boolean large;
    private int slot;

    Emblem(Context context,boolean large) {
      super(context);this.large=large;
      density=context.getResources().getDisplayMetrics().density;
      setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
      setFocusable(false);setClickable(false);
    }

    void bind(int value) {
      int next=Math.max(0,Math.min(LIGHT.length-1,value));
      if(slot!=next){slot=next;invalidate();}
    }

    @Override protected void onMeasure(int widthSpec,int heightSpec) {
      int desired=Math.round((large?56f:44f)*density);
      setMeasuredDimension(resolveSize(desired,widthSpec),resolveSize(desired,heightSpec));
    }

    @Override protected void onSizeChanged(int width,int height,int oldWidth,int oldHeight) {
      body.set(0,0,width,height);edge.set(body);edge.inset(.5f*density,.5f*density);
      int size=Math.round(Math.min(Math.min(width,height)*.56f,(large?29f:24f)*density));
      int left=(width-size)/2,top=Math.round((height-size)*.5f-.65f*density);
      icon.setBounds(left,top,left+size,top+size);
    }

    @Override protected void onDraw(Canvas canvas) {
      super.onDraw(canvas);
      boolean dark=AppAppearance.dark();int accent=(dark?DARK:LIGHT)[slot];
      float radius=Math.min((large?17f:14f)*density,Math.min(body.width(),body.height())*.5f);
      paint.setStyle(Paint.Style.FILL);
      paint.setColor(mix(dark?0xff202226:Color.WHITE,accent,dark?.12f:large?.095f:.075f));
      canvas.drawRoundRect(body,radius,radius,paint);
      paint.setStyle(Paint.Style.STROKE);paint.setStrokeWidth(.6f*density);
      paint.setColor((accent&0x00ffffff)|(dark?0x15000000:0x10000000));
      float edgeRadius=Math.max(0f,radius-.5f*density);
      canvas.drawRoundRect(edge,edgeRadius,edgeRadius,paint);
      paint.setStyle(Paint.Style.FILL);icon.color=accent;icon.draw(canvas);
    }
  }

  private static int withAlpha(int color,int alpha) {
    return (color&0x00ffffff)|(((color>>>24)*alpha+127)/255<<24);
  }

  private static int mix(int background,int foreground,float amount) {
    float rest=1f-amount;
    return Color.rgb(Math.round(Color.red(background)*rest+Color.red(foreground)*amount),
        Math.round(Color.green(background)*rest+Color.green(foreground)*amount),
        Math.round(Color.blue(background)*rest+Color.blue(foreground)*amount));
  }
}
