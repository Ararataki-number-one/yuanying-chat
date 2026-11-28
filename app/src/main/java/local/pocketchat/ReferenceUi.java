package local.pocketchat;

import android.animation.ObjectAnimator;
import android.animation.ValueAnimator;
import android.app.*;
import android.content.*;
import android.content.res.ColorStateList;
import android.graphics.*;
import android.graphics.drawable.*;
import android.os.Build;
import android.text.Layout;
import android.text.TextUtils;
import android.util.TypedValue;
import android.view.*;
import android.view.animation.PathInterpolator;
import android.widget.*;

/** Shared native controls: grouped surfaces, compact navigation and floating panels. */
final class ReferenceUi {
  static int BG=DesignUi.BG,CHAT_BG=0xfff9fbfe,WHITE=0xffffffff,TEXT=DesignUi.TEXT,
    MUTED=DesignUi.MUTED,LINE=DesignUi.LINE,BLUE=DesignUi.BLUE,BLUE_SOFT=0xffedf4ff,
    GREEN=DesignUi.GREEN,ORANGE=0xffa96c0a,RED=DesignUi.RED;
  // Page identities deliberately differ from visual positions in this bar.
  private static final int[] WORKSPACE_PAGES={AppHub.CHAT,AppHub.ENVIRONMENTS,AppHub.DOWNLOADS,AppHub.NETWORK,AppHub.SETTINGS};
  private static final String[] WORKSPACE_LABELS={"浏览器","环境","下载","网络","设置"},WORKSPACE_GLYPHS={"browser","window","download","globe","settings"};
  // Shared roles keep the four native surfaces in step without changing the
  // conversation's compact controls into a management-page header.
  static final int PAGE_TITLE_SIZE=30,CARD_TITLE_SIZE=16,EMPTY_TITLE_SIZE=18,
    BODY_SIZE=14,SECONDARY_SIZE=12,STATUS_SIZE=11,ACTION_SIZE=13,TAB_SIZE=14;
  static int dp(Context c,int n){return Ui.dp(c,n);}
  static TextView text(Context c,String value,int size,int color,boolean strong){TextView v=DesignUi.text(c,value,size,color);if(strong)v.setTypeface(Typeface.create("sans-serif-medium",Typeface.NORMAL));return v;}
  static TextView workspaceText(Context c,String value,int size,int color,boolean strong){
    TextView view=text(c,value,size,color,strong);readable(view);return view;
  }
  /** Include the actual CJK fallback metrics, including on enlarged labels. */
  static void readable(TextView view){
    view.setIncludeFontPadding(true);
    if(Build.VERSION.SDK_INT>=28)view.setFallbackLineSpacing(true);
    view.setLineSpacing(dp(view.getContext(),2),1f);
  }
  static void single(TextView v){v.setSingleLine(true);v.setEllipsize(TextUtils.TruncateAt.END);}
  static Drawable surface(Context c,int color,int radius,int border){return DesignUi.surface(c,color,radius,border);}
  static Button button(Context c,String label,boolean primary,Runnable run){return DesignUi.button(c,label,primary,run);}
  static Button iconButton(Context c,String glyph,String label,Runnable run){Button b=new Ui.IconButton(c,glyph,label,false);b.setOnClickListener(v->run.run());b.setMinimumHeight(dp(c,48));b.setMinimumWidth(dp(c,48));return b;}
  static Button small(Context c,String label,boolean primary,Runnable run){Button b=button(c,label,false,run);b.setTextSize(13);b.setTextColor(primary?BLUE:TEXT);b.setPadding(dp(c,13),0,dp(c,13),0);b.setBackground(new RippleDrawable(ColorStateList.valueOf(0x182468f2),new InsetDrawable(surface(c,primary?BLUE_SOFT:DesignUi.FIELD,12,Color.TRANSPARENT),0,dp(c,6),0,dp(c,6)),null));b.setPadding(dp(c,13),0,dp(c,13),0);return b;}
  static Button link(Context c,String label,Runnable run){Button b=button(c,label,false,run);b.setTextColor(BLUE);b.setPadding(dp(c,4),0,dp(c,4),0);b.setBackground(Ui.ripple(c,Color.TRANSPARENT,9));return b;}
  static Button more(Context c,Runnable run){Button b=new Ui.IconButton(c,"more","更多",false);b.setOnClickListener(v->run.run());b.setMinHeight(dp(c,48));b.setMinimumHeight(dp(c,48));return b;}
  private static final String MENU_GROUP_TAG="pocketchat.modal.menuGroup",MENU_DANGER_TAG="pocketchat.modal.menuDanger";
  static final PathInterpolator DAMPED=new PathInterpolator(0.2f,0f,0f,1f);
  static final Typeface TYPE_DISPLAY=buildType(700),TYPE_TITLE=buildType(650),TYPE_SEMIBOLD=buildType(600),
      TYPE_MEDIUM=buildType(500),TYPE_REGULAR=buildType(400),TYPE_MONO=buildMono();
  private static Typeface buildType(int weight){
    if(Build.VERSION.SDK_INT>=28)return Typeface.create(Typeface.DEFAULT,weight,false);
    return Typeface.create(weight>=600?"sans-serif-medium":"sans-serif",weight>=650?Typeface.BOLD:Typeface.NORMAL);
  }
  private static Typeface buildMono(){
    if(Build.VERSION.SDK_INT>=28)return Typeface.create(Typeface.MONOSPACE,500,false);
    return Typeface.MONOSPACE;
  }
  static Typeface type(int weight){
    if(weight>=700)return TYPE_DISPLAY;
    if(weight>=650)return TYPE_TITLE;
    if(weight>=600)return TYPE_SEMIBOLD;
    if(weight>=500)return TYPE_MEDIUM;
    return TYPE_REGULAR;
  }
  static float dpF(Context c,float n){return n*c.getResources().getDisplayMetrics().density;}
  /** Single-line titles, buttons, chips and labels: remove extra font padding for optical centering. */
  static <T extends TextView> T crisp(T view){
    view.setIncludeFontPadding(false);
    if(Build.VERSION.SDK_INT>=28)view.setFallbackLineSpacing(true);
    view.setLineSpacing(0f,1f);
    return view;
  }
  /** Multi-line CJK prose and banners: airy 1.45x line height + balanced wrapping to eliminate orphans. */
  @android.annotation.SuppressLint("InlinedApi")
  static void balancedBreaks(TextView view){
    // TextView supports this strategy since API 23; javac inlines the SDK's int constant.
    view.setBreakStrategy(android.graphics.text.LineBreaker.BREAK_STRATEGY_BALANCED);
  }
  static <T extends TextView> T prose(T view){
    view.setIncludeFontPadding(false);
    if(Build.VERSION.SDK_INT>=28)view.setFallbackLineSpacing(true);
    view.setLineSpacing(dpF(view.getContext(),3.5f),1.08f);
    balancedBreaks(view);
    view.setHyphenationFrequency(Layout.HYPHENATION_FREQUENCY_NONE);
    return view;
  }
  static <T extends TextView> T tabular(T view){view.setFontFeatureSettings("tnum");return view;}
  static <T extends TextView> T mono(T view){
    view.setTypeface(TYPE_MONO);
    view.setFontFeatureSettings("tnum, zero");
    view.setLetterSpacing(-0.015f);
    return view;
  }
  static TextView displayTitle(Context c,String value,boolean subPage){
    TextView v=new TextView(c);v.setText(value);
    v.setTextSize(TypedValue.COMPLEX_UNIT_SP,subPage?22.5f:32f);
    v.setTypeface(TYPE_DISPLAY);v.setLetterSpacing(subPage?-0.026f:-0.032f);
    v.setTextColor(inkPrimary());crisp(v);
    if(Build.VERSION.SDK_INT>=28)v.setAccessibilityHeading(true);
    return v;
  }
  static TextView heroTitle(Context c,String value){
    TextView v=new TextView(c);v.setText(value);
    v.setTextSize(TypedValue.COMPLEX_UNIT_SP,18.5f);
    v.setTypeface(TYPE_TITLE);v.setLetterSpacing(-0.020f);
    v.setTextColor(inkPrimary());crisp(v);return v;
  }
  static TextView cardTitle(Context c,String value){
    TextView v=new TextView(c);v.setText(value);
    v.setTextSize(TypedValue.COMPLEX_UNIT_SP,16.5f);
    v.setTypeface(TYPE_SEMIBOLD);v.setLetterSpacing(-0.015f);
    v.setTextColor(inkPrimary());crisp(v);return v;
  }
  static TextView subTitle(Context c,String value,boolean subPage){
    TextView v=new TextView(c);v.setText(value);
    v.setTextSize(TypedValue.COMPLEX_UNIT_SP,subPage?12.5f:13f);
    v.setTypeface(TYPE_REGULAR);v.setLetterSpacing(0.003f);
    v.setTextColor(secondaryInk());crisp(v);single(v);return v;
  }
  static void hapticTick(View v){if(v!=null)v.performHapticFeedback(HapticFeedbackConstants.CLOCK_TICK);}
  static void hapticClick(View v){if(v!=null)v.performHapticFeedback(HapticFeedbackConstants.CONTEXT_CLICK);}
  static void hapticConfirm(View v){if(v!=null)v.performHapticFeedback(Build.VERSION.SDK_INT>=30?HapticFeedbackConstants.CONFIRM:HapticFeedbackConstants.VIRTUAL_KEY);}
  static void hapticReject(View v){
    if(v==null)return;
    v.performHapticFeedback(Build.VERSION.SDK_INT>=30?HapticFeedbackConstants.REJECT:HapticFeedbackConstants.LONG_PRESS);
    if(Build.VERSION.SDK_INT>=26&&!ValueAnimator.areAnimatorsEnabled())return;
    float d=dpF(v.getContext(),5f);
    ObjectAnimator a=ObjectAnimator.ofFloat(v,View.TRANSLATION_X,0f,-d,d,-d*.6f,d*.6f,0f);
    a.setDuration(260);a.setInterpolator(DAMPED);a.start();
  }
  /** Side-by-side dual buttons in cards: tight 10dp horizontal padding + auto-size 12..14sp single line. */
  static void styleDualButton(Button b){
    if(b==null)return;Context c=b.getContext();
    b.setPadding(dp(c,10),b.getPaddingTop(),dp(c,10),b.getPaddingBottom());
    b.setSingleLine(true);crisp(b);
    if(Build.VERSION.SDK_INT>=26)b.setAutoSizeTextTypeUniformWithConfiguration(12,14,1,TypedValue.COMPLEX_UNIT_SP);
  }
  static int tone(int light,int dark){return AppAppearance.dark()?dark:light;}
  static int canvasBg(){return tone(0xfff2f3f6,0xff0d0e12);}
  static int cardBg(){return tone(0xffffffff,0xff1b1e26);}
  static int recessedBg(){return tone(0xfff3f4f8,0xff111319);}
  static int frostBg(){return tone(0xfff7f8fa,0xff13151c);}
  static int inkPrimary(){return tone(0xff141518,0xfff3f4f7);}
  static int secondaryInk(){return tone(0xff565b66,0xffa4aab6);}
  static int specKeyInk(){return tone(0xff565b66,0xffd4d8e2);}
  static int brandAccent(){return tone(0xff0067d8,0xff6da4ff);}
  static int brandBlue(){return tone(0xff0052b4,0xff8cbaff);}
  static int brandBlueSolid(){return tone(0xff16171a,0xfff6f7f9);}
  static int primaryOnSolid(){return tone(0xffffffff,0xff111216);}
  static int greenInk(){return tone(0xff15804e,0xff34d38b);}
  static int amberAccent(){return tone(0xffd97706,0xffff852e);}
  static int amberInk(){return tone(0xffb54200,0xffffaa66);}
  static int redInk(){return tone(0xffdc2626,0xffff7a82);}
  static int redSolid(){return tone(0xffdc2626,0xffd42a36);}
  static int chevronInk(){return tone(0xff8c919c,0xff787f8d);}
  static int dividerColor(){return tone(0x1a0f172a,0x1effffff);}
  static boolean isDestructiveLabel(String label){
    if(label==null||label.isEmpty())return false;
    return label.startsWith("删除")||label.startsWith("清空")||label.startsWith("放弃")||label.startsWith("重置")
        ||label.startsWith("立即切换")||label.startsWith("关闭浏览器")||label.startsWith("关闭并取消")
        ||label.startsWith("结束网页")||label.equals("取消下载")||label.equals("取消待应用设置");
  }
  static final class AdaptiveSurface extends GradientDrawable {
    final int lightFill,darkFill,lightStroke,darkStroke,strokePx;
    AdaptiveSurface(Context c,int radiusDp,int lightFill,int darkFill){this(c,radiusDp,lightFill,darkFill,0,0,0);}
    AdaptiveSurface(Context c,int radiusDp,int lightFill,int darkFill,int lightStroke,int darkStroke){
      this(c,radiusDp,lightFill,darkFill,lightStroke,darkStroke,Math.max(1,Math.round(dpF(c,0.55f))));
    }
    AdaptiveSurface(Context c,int radiusDp,int lightFill,int darkFill,int lightStroke,int darkStroke,int strokePx){
      this.lightFill=lightFill;this.darkFill=darkFill;this.lightStroke=lightStroke;this.darkStroke=darkStroke;this.strokePx=strokePx;
      setCornerRadius(dp(c,radiusDp));sync();
    }
    void sync(){
      boolean dark=AppAppearance.dark();
      setColor(dark?darkFill:lightFill);
      int stroke=dark?darkStroke:lightStroke;
      setStroke(stroke==0?0:strokePx,stroke);
    }
    @Override public void draw(Canvas canvas){sync();super.draw(canvas);}
  }
  /** Zero-elevation Horology card: 0.55dp hairline + light 1dp bottom contact line + dark 0.65dp CNC top-spine highlight. */
  static final class CardSurfaceDrawable extends Drawable {
    private final Paint fill=new Paint(Paint.ANTI_ALIAS_FLAG),rim=new Paint(Paint.ANTI_ALIAS_FLAG),spine=new Paint(Paint.ANTI_ALIAS_FLAG);
    private final RectF face=new RectF(),edge=new RectF();
    private final float density,radiusDp;
    private final int lightBg,darkBg;
    private Shader darkTopSpine;
    CardSurfaceDrawable(Context c,float radiusDp){this(c,radiusDp,0xffffffff,0xff1b1e26);}
    CardSurfaceDrawable(Context c,float radiusDp,int lightBg,int darkBg){
      density=c.getResources().getDisplayMetrics().density;this.radiusDp=radiusDp;this.lightBg=lightBg;this.darkBg=darkBg;
      fill.setStyle(Paint.Style.FILL);rim.setStyle(Paint.Style.STROKE);spine.setStyle(Paint.Style.STROKE);
    }
    @Override protected void onBoundsChange(Rect b){
      face.set(b);edge.set(face);float inset=0.28f*density;edge.inset(inset,inset);
      float r=Math.min(radiusDp*density,Math.min(face.width(),face.height())*.5f);
      if(face.width()>r*2f+2f){
        darkTopSpine=new LinearGradient(face.left+r,face.top,face.right-r,face.top,
            new int[]{0x00ffffff,0x24ffffff,0x00ffffff},new float[]{0f,0.5f,1f},Shader.TileMode.CLAMP);
      }else darkTopSpine=null;
    }
    @Override public void draw(Canvas canvas){
      if(face.isEmpty())return;
      boolean dark=AppAppearance.dark();
      float r=Math.min(radiusDp*density,Math.min(face.width(),face.height())*.5f);
      fill.setColor(dark?darkBg:lightBg);
      canvas.drawRoundRect(face,r,r,fill);
      rim.setStrokeWidth(Math.max(1f,0.55f*density));
      rim.setColor(dark?0x1affffff:0x12111827);
      canvas.drawRoundRect(edge,Math.max(0f,r-0.28f*density),Math.max(0f,r-0.28f*density),rim);
      if(face.width()>r*2f+2f){
        if(dark&&darkTopSpine!=null){
          spine.setShader(darkTopSpine);spine.setStrokeWidth(Math.max(1f,0.65f*density));
          float y=face.top+0.45f*density;
          canvas.drawLine(face.left+r,y,face.right-r,y,spine);
          spine.setShader(null);
        }else if(!dark){
          spine.setShader(null);spine.setColor(0x10111827);spine.setStrokeWidth(Math.max(1f,1f*density));
          float y=face.bottom-0.5f*density;
          canvas.drawLine(face.left+r,y,face.right-r,y,spine);
        }
      }
    }
    @Override public void getOutline(Outline outline){
      if(getBounds().isEmpty()){outline.setEmpty();return;}
      float r=Math.min(radiusDp*density,Math.min(getBounds().width(),getBounds().height())*.5f);
      outline.setRoundRect(getBounds(),r);
    }
    @Override public void setAlpha(int a){fill.setAlpha(a);rim.setAlpha(a);spine.setAlpha(a);invalidateSelf();}
    @Override public void setColorFilter(ColorFilter f){fill.setColorFilter(f);invalidateSelf();}
    @Override public int getOpacity(){return PixelFormat.TRANSLUCENT;}
  }
  /** Subtle carved 14dp recessed box: solid matte slot + 0.6dp inner-top shadow line only. */
  static class RecessedBoxDrawable extends Drawable {
    protected final Paint fill=new Paint(Paint.ANTI_ALIAS_FLAG),rim=new Paint(Paint.ANTI_ALIAS_FLAG);
    protected final RectF face=new RectF(),edge=new RectF();
    protected final float density,radiusDp;
    RecessedBoxDrawable(Context c,float radiusDp){
      density=c.getResources().getDisplayMetrics().density;this.radiusDp=radiusDp;
      fill.setStyle(Paint.Style.FILL);rim.setStyle(Paint.Style.STROKE);
    }
    @Override protected void onBoundsChange(Rect b){face.set(b);edge.set(face);edge.inset(0.35f*density,0.35f*density);}
    protected void drawBase(Canvas canvas,boolean dark,float r){
      fill.setColor(dark?0xff111319:0xfff3f4f8);
      canvas.drawRoundRect(face,r,r,fill);
      rim.setStrokeWidth(Math.max(1f,0.55f*density));
      rim.setColor(dark?0x18ffffff:0x16111827);
      canvas.drawRoundRect(edge,Math.max(0f,r-0.35f*density),Math.max(0f,r-0.35f*density),rim);
      if(face.width()>r*2f+2f){
        rim.setStrokeWidth(Math.max(1f,0.65f*density));
        rim.setColor(dark?0x48000000:0x0e111827);
        float y=face.top+0.6f*density;
        canvas.drawLine(face.left+r,y,face.right-r,y,rim);
      }
    }
    @Override public void draw(Canvas canvas){
      if(face.isEmpty())return;
      float r=Math.min(radiusDp*density,Math.min(face.width(),face.height())*.5f);
      drawBase(canvas,AppAppearance.dark(),r);
    }
    @Override public void setAlpha(int a){fill.setAlpha(a);rim.setAlpha(a);invalidateSelf();}
    @Override public void setColorFilter(ColorFilter f){fill.setColorFilter(f);invalidateSelf();}
    @Override public int getOpacity(){return PixelFormat.TRANSLUCENT;}
  }
  static class FieldWell extends RecessedBoxDrawable {
    private final boolean danger;
    private boolean focused,enabled=true;
    FieldWell(Context c){this(c,false);}
    FieldWell(Context c,boolean danger){super(c,14f);this.danger=danger;}
    @Override public boolean isStateful(){return true;}
    @Override protected boolean onStateChange(int[] states){
      boolean nextFocus=false,nextEnabled=false;
      for(int s:states){if(s==android.R.attr.state_focused)nextFocus=true;if(s==android.R.attr.state_enabled)nextEnabled=true;}
      if(nextFocus==focused&&nextEnabled==enabled)return false;
      focused=nextFocus;enabled=nextEnabled;invalidateSelf();return true;
    }
    @Override public void draw(Canvas canvas){
      if(face.isEmpty())return;
      boolean dark=AppAppearance.dark();
      float r=Math.min(radiusDp*density,Math.min(face.width(),face.height())*.5f);
      int alpha=enabled?255:140;fill.setAlpha(alpha);rim.setAlpha(alpha);
      drawBase(canvas,dark,r);
      if(focused){
        rim.setStrokeWidth(Math.max(2f,1.5f*density));
        rim.setColor(danger?(dark?0xffff5c64:0xffdc2626):(dark?0xff6da4ff:0xff0067d8));
        RectF focusRect=new RectF(face);float ins=0.75f*density;focusRect.inset(ins,ins);
        canvas.drawRoundRect(focusRect,Math.max(0f,r-ins),Math.max(0f,r-ins),rim);
      }
    }
  }
  /** Carved segmented control track: #E6E8EE light (deeper than #F2F3F6 canvas) / #111319 dark. */
  static final class SegmentedTrackDrawable extends RecessedBoxDrawable {
    SegmentedTrackDrawable(Context c){super(c,14f);}
    @Override protected void drawBase(Canvas canvas,boolean dark,float r){
      fill.setColor(dark?0xff111319:0xffe6e8ee);
      canvas.drawRoundRect(face,r,r,fill);
      rim.setStrokeWidth(Math.max(1f,0.55f*density));
      rim.setColor(dark?0x16ffffff:0x14111827);
      canvas.drawRoundRect(edge,Math.max(0f,r-0.35f*density),Math.max(0f,r-0.35f*density),rim);
      if(face.width()>r*2f+2f){
        rim.setStrokeWidth(Math.max(1f,0.75f*density));
        rim.setColor(dark?0x48000000:0x12111827);
        float y=face.top+0.6f*density;
        canvas.drawLine(face.left+r,y,face.right-r,y,rim);
      }
    }
  }
  /** Active segmented thumb: #FFFFFF light + subtle contact edge / #313644 + 0x3CFFFFFF top highlight dark. */
  static final class SegmentedThumbDrawable extends Drawable {
    private final Paint fill=new Paint(Paint.ANTI_ALIAS_FLAG),rim=new Paint(Paint.ANTI_ALIAS_FLAG);
    private final RectF face=new RectF(),edge=new RectF();
    private final float density;
    SegmentedThumbDrawable(Context c){density=c.getResources().getDisplayMetrics().density;fill.setStyle(Paint.Style.FILL);rim.setStyle(Paint.Style.STROKE);}
    @Override protected void onBoundsChange(Rect b){face.set(b);edge.set(face);edge.inset(0.28f*density,0.28f*density);}
    @Override public void draw(Canvas canvas){
      if(face.isEmpty())return;
      boolean dark=AppAppearance.dark();float r=Math.min(10f*density,Math.min(face.width(),face.height())*.5f);
      fill.setColor(dark?0xff313644:0xffffffff);canvas.drawRoundRect(face,r,r,fill);
      rim.setStrokeWidth(Math.max(1f,0.55f*density));rim.setColor(dark?0x1cffffff:0x14111827);
      canvas.drawRoundRect(edge,Math.max(0f,r-0.28f*density),Math.max(0f,r-0.28f*density),rim);
      if(face.width()>r*2f+2f){
        if(dark){
          rim.setStrokeWidth(Math.max(1f,0.65f*density));rim.setColor(0x3cffffff);
          float y=face.top+0.45f*density;canvas.drawLine(face.left+r,y,face.right-r,y,rim);
        }else{
          rim.setStrokeWidth(Math.max(1f,0.8f*density));rim.setColor(0x14111827);
          float y=face.bottom-0.45f*density;canvas.drawLine(face.left+r,y,face.right-r,y,rim);
        }
      }
    }
    @Override public void setAlpha(int a){fill.setAlpha(a);rim.setAlpha(a);invalidateSelf();}
    @Override public void setColorFilter(ColorFilter f){fill.setColorFilter(f);invalidateSelf();}
    @Override public int getOpacity(){return PixelFormat.TRANSLUCENT;}
  }
  /** Precision LED status indicator: 5.3dp solid core + 10dp 20% alpha outer halo. */
  static final class HaloDotDrawable extends Drawable {
    private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
    private final int color,sizePx;private final float coreR,haloR;
    HaloDotDrawable(Context c,int color){
      this.color=color;float d=c.getResources().getDisplayMetrics().density;
      sizePx=Math.round(10f*d);coreR=2.65f*d;haloR=5f*d;
      setBounds(0,0,sizePx,sizePx);
    }
    @Override public int getIntrinsicWidth(){return sizePx;}
    @Override public int getIntrinsicHeight(){return sizePx;}
    @Override public void draw(Canvas canvas){
      Rect b=getBounds();float cx=b.exactCenterX(),cy=b.exactCenterY();
      paint.setColor((color&0x00ffffff)|0x33000000);canvas.drawCircle(cx,cy,haloR,paint);
      paint.setColor(color);canvas.drawCircle(cx,cy,coreR,paint);
    }
    @Override public void setAlpha(int a){paint.setAlpha(a);invalidateSelf();}
    @Override public void setColorFilter(ColorFilter f){paint.setColorFilter(f);invalidateSelf();}
    @Override public int getOpacity(){return PixelFormat.TRANSLUCENT;}
  }
  /** Semantic banner: 14dp radius + left 2.7dp solid vertical bar + 0.5dp semantically tinted outer border. */
  static final class AccentBannerDrawable extends Drawable {
    private final Paint fill=new Paint(Paint.ANTI_ALIAS_FLAG),rim=new Paint(Paint.ANTI_ALIAS_FLAG);
    private final RectF face=new RectF(),edge=new RectF();
    private final Path clip=new Path();
    private final float density;private final int level;
    AccentBannerDrawable(Context c,int level){
      density=c.getResources().getDisplayMetrics().density;this.level=level;
      fill.setStyle(Paint.Style.FILL);rim.setStyle(Paint.Style.STROKE);
    }
    @Override protected void onBoundsChange(Rect b){
      face.set(b);edge.set(face);edge.inset(0.28f*density,0.28f*density);
      clip.rewind();float r=Math.min(14f*density,Math.min(face.width(),face.height())*.5f);
      if(!face.isEmpty())clip.addRoundRect(face,r,r,Path.Direction.CW);
    }
    @Override public void draw(Canvas canvas){
      if(face.isEmpty())return;
      boolean dark=AppAppearance.dark();
      float r=Math.min(14f*density,Math.min(face.width(),face.height())*.5f);
      int bg=level>0?(dark?0xff13221c:0xfff1fbf5):level==0?(dark?0xff211a12:0xfffff8f0):(dark?0xff241518:0xfffff3f4);
      int bar=level>0?(dark?0xff34d38b:0xff15804e):level==0?(dark?0xffff852e:0xffd97706):(dark?0xffff7a82:0xffdc2626);
      int border=level>0?(dark?0x3334d38b:0x2415804e):level==0?(dark?0x33ff852e:0x28d97706):(dark?0x33ff7a82:0x26dc2626);
      fill.setColor(bg);canvas.drawRoundRect(face,r,r,fill);
      float barInsetV=Math.min(11f*density,face.height()*0.22f);
      float barL=face.left+5f*density,barR=barL+3f*density;
      RectF barRect=new RectF(barL,face.top+barInsetV,barR,face.bottom-barInsetV);
      fill.setColor(bar);canvas.drawRoundRect(barRect,1.5f*density,1.5f*density,fill);
      rim.setStrokeWidth(Math.max(1f,0.5f*density));rim.setColor(border);
      canvas.drawRoundRect(edge,Math.max(0f,r-0.28f*density),Math.max(0f,r-0.28f*density),rim);
    }
    @Override public void setAlpha(int a){fill.setAlpha(a);rim.setAlpha(a);invalidateSelf();}
    @Override public void setColorFilter(ColorFilter f){fill.setColorFilter(f);invalidateSelf();}
    @Override public int getOpacity(){return PixelFormat.TRANSLUCENT;}
  }
  /** The content row determines the header height. The decorative frost fills only that area. */
  static FrameLayout horologyHeader(Activity a,String title,String subtitle,Runnable back,ScrollView scroll){
    LinearLayout row=DesignUi.row(a);
    FrameLayout header=new FrameLayout(a){
      @Override protected void onMeasure(int widthSpec,int heightSpec){
        measureChildWithMargins(row,widthSpec,0,heightSpec,0);
        int height=resolveSize(row.getMeasuredHeight(),heightSpec);
        super.onMeasure(widthSpec,View.MeasureSpec.makeMeasureSpec(height,View.MeasureSpec.EXACTLY));
      }
    };
    header.setClipChildren(false);header.setClipToPadding(false);
    View frost=new View(a);frost.setBackground(new AdaptiveSurface(a,0,0xfff7f8fa,0xff13151c));frost.setAlpha(0f);
    frost.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
    header.addView(frost,new FrameLayout.LayoutParams(-1,-1));
    View seam=new View(a);seam.setBackground(new AdaptiveSurface(a,0,0x14111827,0x1affffff));seam.setAlpha(0f);
    seam.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
    header.addView(seam,new FrameLayout.LayoutParams(-1,Math.max(1,Math.round(dpF(a,0.5f))),Gravity.BOTTOM));
    row.setClipChildren(false);row.setClipToPadding(false);
    row.setGravity(Gravity.CENTER_VERTICAL);
    row.setPadding(dp(a,14),dp(a,8),dp(a,16),dp(a,10));
    if(back!=null){
      Button backBtn=iconButton(a,"back","返回",()->{hapticClick(row);back.run();});
      backBtn.setPadding(0,0,0,0);backBtn.setElevation(0f);
      backBtn.setBackground(new AdaptiveSurface(a,22,0xfffbfcfe,0xff1c1f27,0x1a111827,0x22ffffff));
      GlassMotion.press(backBtn,true);
      LinearLayout.LayoutParams bp=new LinearLayout.LayoutParams(dp(a,44),dp(a,44));bp.setMarginEnd(dp(a,10));
      row.addView(backBtn,bp);
    }
    LinearLayout titles=DesignUi.column(a);titles.setClipChildren(false);
    TextView h=displayTitle(a,title,true);single(h);
    LinearLayout.LayoutParams hp=new LinearLayout.LayoutParams(-1,-2);
    titles.addView(h,hp);
    TextView sub=null;
    if(subtitle!=null&&!subtitle.isEmpty()){
      sub=subTitle(a,subtitle,true);
      LinearLayout.LayoutParams sp=new LinearLayout.LayoutParams(-1,-2);sp.topMargin=dp(a,2);
      titles.addView(sub,sp);
    }
    row.addView(titles,new LinearLayout.LayoutParams(0,-2,1));
    header.addView(row,new FrameLayout.LayoutParams(-1,-2));
    if(scroll!=null)bindScrollHeader(scroll,frost,seam,h,sub);
    return header;
  }
  static void bindScrollHeader(ScrollView scroll,View frost,View seam,TextView title,TextView subtitle){
    if(scroll==null)return;
    Context c=scroll.getContext();
    float frostDist=dpF(c,18f),subFadeDist=dpF(c,34f),scaleDist=dpF(c,56f),subShift=dpF(c,4f),titleCenterShift=dpF(c,7f);
    scroll.setOnScrollChangeListener((v,sx,sy,osx,osy)->{
      float f=Math.max(0f,Math.min(1f,sy/frostDist));
      if(frost!=null)frost.setAlpha(f);
      if(seam!=null)seam.setAlpha(f);
      float t=Math.max(0f,Math.min(1f,sy/scaleDist));
      float smooth=t*t*(3f-2f*t);
      if(title!=null){
        title.setPivotX(0f);title.setPivotY(title.getHeight()*0.5f);
        float s=1f-0.11f*smooth;title.setScaleX(s);title.setScaleY(s);
        if(subtitle!=null)title.setTranslationY(titleCenterShift*smooth);
      }
      if(subtitle!=null){
        float sf=Math.max(0f,Math.min(1f,sy/subFadeDist));
        subtitle.setAlpha(1f-sf);
        subtitle.setTranslationY(-subShift*sf);
      }
    });
  }
  static final class IconTileDrawable extends Drawable {
    final Context c;final Ui.Icon icon;final boolean destructive,accent,boxed;final int sizePx,radiusPx,insetPx;
    final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG),rim=new Paint(Paint.ANTI_ALIAS_FLAG);final RectF box=new RectF();final float strokePx;
    IconTileDrawable(Context c,String glyph,int sizeDp,boolean destructive,boolean accent){
      this.c=c;this.destructive=destructive;this.accent=accent;
      this.boxed=sizeDp>=32||accent;
      this.sizePx=dp(c,sizeDp);this.radiusPx=dp(c,sizeDp>=36?11:9);
      this.insetPx=boxed?dp(c,sizeDp>=36?8:6):dp(c,Math.max(2,(sizeDp-19)/2));
      this.strokePx=Math.max(1f,c.getResources().getDisplayMetrics().density*.6f);
      rim.setStyle(Paint.Style.STROKE);rim.setStrokeWidth(strokePx);
      this.icon=new Ui.Icon(glyph,Color.GRAY);
      setBounds(0,0,sizePx,sizePx);
    }
    @Override public int getIntrinsicWidth(){return sizePx;}
    @Override public int getIntrinsicHeight(){return sizePx;}
    @Override public void draw(Canvas canvas){
      Rect b=getBounds();box.set(b.left,b.top,b.right,b.bottom);
      boolean dark=AppAppearance.dark();
      int fg=destructive?(dark?0xffff7a82:0xffdc2626):accent?(dark?0xff8cbaff:0xff0052b4):(dark?0xffa4aab6:0xff565b66);
      if(boxed){
        int fill=destructive?(dark?0x22ff5c64:0x10dc2626):accent?(dark?0xff1b2638:0xffeef4ff):(dark?0xff232732:0xfff6f7f9);
        int edge=destructive?(dark?0x33ff5c64:0x22dc2626):accent?(dark?0x336da4ff:0x200067d8):(dark?0x1affffff:0x12111827);
        paint.setColor(fill);canvas.drawRoundRect(box,radiusPx,radiusPx,paint);
        box.inset(strokePx*.5f,strokePx*.5f);rim.setColor(edge);canvas.drawRoundRect(box,radiusPx,radiusPx,rim);
      }
      icon.color=fg;icon.setBounds(b.left+insetPx,b.top+insetPx,b.right-insetPx,b.bottom-insetPx);icon.draw(canvas);
    }
    @Override public void setAlpha(int a){paint.setAlpha(a);rim.setAlpha(a);icon.setAlpha(a);}
    @Override public void setColorFilter(ColorFilter f){paint.setColorFilter(f);rim.setColorFilter(f);icon.setColorFilter(f);}
    @Override public int getOpacity(){return PixelFormat.TRANSLUCENT;}
  }
  static String inferMenuGlyph(String label,boolean destructive){
    if(destructive)return label.contains("关闭")?"close":label.contains("重置")?"refresh":"trash";
    if(label.contains("分享"))return "share";
    if(label.contains("复制"))return "clipboard";
    if(label.contains("另存")||label.contains("保存位置")||label.contains("下载"))return "download";
    if(label.contains("新标签"))return "plus";
    if(label.contains("内核")||label.contains("浏览器")||label.contains("继续浏览")||label.contains("当前标签"))return "browser";
    if(label.contains("会话")||label.contains("离线"))return "chat";
    if(label.equals("打开")||label.contains("草稿")||label.contains("文档"))return "file";
    if(label.contains("编辑")||label.contains("分组与备注"))return "new";
    if(label.contains("网络")||label.contains("IP")||label.contains("线路")||label.contains("测速"))return "globe";
    if(label.contains("环境")||label.contains("窗口"))return "window";
    if(label.contains("刷新")||label.contains("重新连接"))return "refresh";
    if(label.contains("搜索")||label.contains("检索"))return "search";
    if(label.contains("指纹")||label.contains("权限")||label.contains("隐私"))return "shield";
    if(label.contains("收藏"))return "star";
    if(label.contains("设置"))return "settings";
    if(label.contains("备份"))return "backup";
    if(label.contains("历史"))return "book";
    return "info";
  }
  static LinearLayout modalGroup(Context c){
    LinearLayout group=DesignUi.column(c);
    group.setElevation(0f);
    group.setBackground(new CardSurfaceDrawable(c,20f));
    group.setClipToOutline(true);
    return group;
  }
  static LinearLayout modalActionCard(Context c){
    LinearLayout group=DesignUi.column(c);
    group.setElevation(0f);
    group.setBackground(new CardSurfaceDrawable(c,15f));
    group.setClipToOutline(true);
    return group;
  }
  static View modalDivider(Context c,int startDp){
    View line=new View(c);
    line.setBackground(new AdaptiveSurface(c,0,0x14111827,0x18ffffff));
    line.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
    LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,Math.max(1,Math.round(dpF(c,0.5f))));
    p.setMarginStart(dp(c,startDp));
    p.setMarginEnd(dp(c,16));
    line.setLayoutParams(p);
    return line;
  }
  static TextView modalSection(LinearLayout parent,String title){
    Context c=parent.getContext();
    TextView h=new TextView(c);h.setText(title);h.setTextSize(TypedValue.COMPLEX_UNIT_SP,12f);
    h.setTypeface(TYPE_SEMIBOLD);h.setLetterSpacing(0.045f);h.setTextColor(tone(0xff4e535e,0xff949ba8));crisp(h);
    h.setPadding(dp(c,16),dp(c,parent.getChildCount()==0?4:18),dp(c,16),dp(c,6));
    if(Build.VERSION.SDK_INT>=28)h.setAccessibilityHeading(true);
    parent.addView(h,new LinearLayout.LayoutParams(-1,-2));
    return h;
  }
  static TextView modalFooterNote(LinearLayout parent,String text){
    Context c=parent.getContext();
    TextView note=prose(workspaceText(c,text,SECONDARY_SIZE,secondaryInk(),false));
    note.setTypeface(TYPE_REGULAR);
    note.setPadding(dp(c,16),dp(c,8),dp(c,16),dp(c,4));
    parent.addView(note,new LinearLayout.LayoutParams(-1,-2));
    return note;
  }
  static View monogramTile(Context c,String label,int sizeDp){
    String ch="环";
    if(label!=null){String t=label.trim();if(!t.isEmpty())ch=new String(Character.toChars(t.codePointAt(0)));}
    TextView tile=new TextView(c);tile.setText(ch);tile.setTextSize(sizeDp>=32?14:13);
    tile.setTypeface(TYPE_SEMIBOLD);crisp(tile);
    tile.setTextColor(tone(0xff565b66,0xffd0d4de));tile.setGravity(Gravity.CENTER);
    tile.setBackground(new AdaptiveSurface(c,sizeDp>=32?9:8,0xfff6f7f9,0xff232732,0x12111827,0x1affffff));
    tile.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
    LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(dp(c,sizeDp),dp(c,sizeDp));
    p.setMarginEnd(dp(c,12));tile.setLayoutParams(p);
    return tile;
  }
  static LinearLayout modalChoice(LinearLayout group,String title,String detail,boolean selected,Runnable click){
    return modalChoice(group,title,detail,"",false,selected,click);
  }
  static LinearLayout modalChoice(LinearLayout group,String title,String detail,String lead,boolean monogram,boolean selected,Runnable click){
    Context c=group.getContext();
    boolean hasLead=lead!=null&&!lead.isEmpty();
    if(group.getChildCount()>0)group.addView(modalDivider(c,hasLead?58:16));
    LinearLayout row=DesignUi.row(c);row.setGravity(Gravity.CENTER_VERTICAL);
    row.setMinimumHeight(dp(c,detail==null||detail.isEmpty()?52:60));
    row.setPadding(dp(c,16),dp(c,11),dp(c,16),dp(c,11));
    row.setBackground(new RippleDrawable(ColorStateList.valueOf(tone(0x140067d8,0x2682b3ff)),new ColorDrawable(Color.TRANSPARENT),new ColorDrawable(Color.WHITE)));
    if(hasLead){
      if(monogram)row.addView(monogramTile(c,lead,30));
      else{
        ImageView icon=new ImageView(c);icon.setImageDrawable(new IconTileDrawable(c,lead,30,false,false));
        icon.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        LinearLayout.LayoutParams ip=new LinearLayout.LayoutParams(dp(c,30),dp(c,30));ip.setMarginEnd(dp(c,12));row.addView(icon,ip);
      }
    }
    LinearLayout copy=DesignUi.column(c);
    TextView name=workspaceText(c,title,15,TEXT,selected);name.setMaxLines(3);copy.addView(name);
    if(detail!=null&&!detail.isEmpty()){
      TextView sub=workspaceText(c,detail,SECONDARY_SIZE,secondaryInk(),false);
      sub.setPadding(0,dp(c,3),0,0);sub.setFontFeatureSettings("tnum");copy.addView(sub);
    }
    row.addView(copy,new LinearLayout.LayoutParams(0,-2,1));
    ImageView check=new ImageView(c);check.setImageDrawable(new Ui.Icon("check",brandBlue()));
    check.setVisibility(selected?View.VISIBLE:View.INVISIBLE);
    check.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
    LinearLayout.LayoutParams cp=new LinearLayout.LayoutParams(dp(c,18),dp(c,18));cp.setMarginStart(dp(c,10));
    row.addView(check,cp);
    row.setClickable(true);row.setFocusable(true);row.setSelected(selected);
    row.setContentDescription(title+(detail==null||detail.isEmpty()?"":"，"+detail)+(selected?"，已选择":""));
    row.setOnClickListener(v->{hapticTick(v);click.run();});
    group.addView(row,new LinearLayout.LayoutParams(-1,-2));
    return row;
  }
  static LinearLayout modalFieldRow(LinearLayout group,String key,String value,boolean selectable){
    Context c=group.getContext();
    if(group.getChildCount()>0)group.addView(modalDivider(c,16));
    boolean urlStack=value!=null&&(value.startsWith("http://")||value.startsWith("https://"))&&value.length()>24;
    boolean proseStack=value!=null&&value.length()>=28;
    boolean large=urlStack||proseStack||c.getResources().getConfiguration().fontScale>=1.4f;
    LinearLayout row=DesignUi.row(c);row.setOrientation(large?LinearLayout.VERTICAL:LinearLayout.HORIZONTAL);
    row.setGravity(Gravity.TOP);row.setBaselineAligned(!large);
    row.setPadding(dp(c,16),dp(c,11),dp(c,16),dp(c,11));
    TextView k=workspaceText(c,key,ACTION_SIZE,specKeyInk(),false);k.setTypeface(TYPE_REGULAR);
    if(!large)k.setPaddingRelative(0,0,dp(c,12),0);
    row.addView(k,new LinearLayout.LayoutParams(large?-1:dp(c,96),-2));
    TextView v=workspaceText(c,value,BODY_SIZE,inkPrimary(),false);
    boolean technical=value!=null&&(value.contains(":")||value.startsWith("http://")||value.startsWith("https://")||value.startsWith("SHA"));
    if(technical)mono(v);else{v.setTypeface(TYPE_MEDIUM);tabular(v);}
    v.setTextIsSelectable(selectable);
    if(large)v.setPadding(0,dp(c,4),0,0);
    row.addView(v,new LinearLayout.LayoutParams(large?-1:0,-2,large?0:1));
    group.addView(row,new LinearLayout.LayoutParams(-1,-2));
    return row;
  }
  static EditText modalInput(LinearLayout group,String label,String value,String hint){
    return modalInput(group,label,value,hint,false);
  }
  static EditText modalInput(LinearLayout group,String label,String value,String hint,boolean required){
    Context c=group.getContext();
    boolean first=group.getChildCount()==0;
    LinearLayout block=DesignUi.column(c);
    block.setPadding(dp(c,16),dp(c,first?14:8),dp(c,16),dp(c,12));
    EditText e=new EditText(c);e.setSingleLine(true);NativeControls.prepare(e);
    e.setText(value);e.setHint(hint);e.setTextSize(15);e.setTextColor(inkPrimary());e.setHintTextColor(secondaryInk());
    e.setPadding(dp(c,14),dp(c,11),dp(c,14),dp(c,11));e.setMinHeight(dp(c,46));
    e.setBackground(new FieldWell(c));e.setImeOptions(android.view.inputmethod.EditorInfo.IME_ACTION_NEXT);
    if(label!=null&&!label.isEmpty()){
      LinearLayout head=DesignUi.row(c);head.setPadding(dp(c,2),0,dp(c,2),dp(c,6));
      TextView heading=new TextView(c);heading.setText(label);heading.setTextSize(TypedValue.COMPLEX_UNIT_SP,13f);
      heading.setTypeface(TYPE_SEMIBOLD);heading.setLetterSpacing(0.015f);heading.setTextColor(secondaryInk());crisp(heading);
      heading.setLabelFor(e.getId());e.setContentDescription(label+(required?"，必填":""));
      head.addView(heading,new LinearLayout.LayoutParams(-2,-2));
      if(required){
        TextView req=new TextView(c);req.setText("必填");req.setTextSize(TypedValue.COMPLEX_UNIT_SP,11f);
        req.setTypeface(TYPE_SEMIBOLD);req.setLetterSpacing(0.025f);req.setTextColor(brandBlue());crisp(req);
        req.setPadding(dp(c,6),dp(c,2),dp(c,6),dp(c,2));
        req.setBackground(new AdaptiveSurface(c,5,0x140067d8,0x246da4ff));
        LinearLayout.LayoutParams rp=new LinearLayout.LayoutParams(-2,-2);rp.setMarginStart(dp(c,6));
        head.addView(req,rp);
      }
      block.addView(head,new LinearLayout.LayoutParams(-1,-2));
    }
    block.addView(e,new LinearLayout.LayoutParams(-1,-2));
    group.addView(block,new LinearLayout.LayoutParams(-1,-2));
    return e;
  }
  static void styleSwitch(Switch s){
    if(s==null)return;
    Context c=s.getContext();
    AdaptiveSurface onTrack=new AdaptiveSurface(c,999,0xff15804e,0xff2bb673);
    onTrack.setSize(dp(c,46),dp(c,26));
    AdaptiveSurface offTrack=new AdaptiveSurface(c,999,0xffd6d9e0,0xff2b2f3b,0x14111827,0x18ffffff);
    offTrack.setSize(dp(c,46),dp(c,26));
    StateListDrawable tracks=new StateListDrawable();
    tracks.addState(new int[]{android.R.attr.state_checked},onTrack);
    tracks.addState(new int[]{},offTrack);
    s.setTrackTintList(null);
    s.setTrackDrawable(tracks);
    s.setThumbTintList(ColorStateList.valueOf(Color.WHITE));
  }
  static Switch modalSwitchRow(LinearLayout group,String label,boolean checked){
    Context c=group.getContext();
    if(group.getChildCount()>0)group.addView(modalDivider(c,16));
    Switch s=new Switch(c);s.setText(label);s.setTextSize(14.5f);s.setTypeface(TYPE_MEDIUM);s.setTextColor(inkPrimary());
    s.setChecked(checked);NativeControls.prepare(s);styleSwitch(s);
    s.setPadding(dp(c,16),dp(c,12),dp(c,16),dp(c,12));s.setMinHeight(dp(c,52));
    group.addView(s,new LinearLayout.LayoutParams(-1,-2));
    return s;
  }
  static Button modalRowAction(LinearLayout group,String glyph,String label,boolean destructive,Runnable click){
    Context c=group.getContext();
    if(group.getChildCount()>0)group.addView(modalDivider(c,54));
    Button b=link(c,label,()->{hapticTick(group);click.run();});
    b.setTextSize(14.5f);b.setTextColor(destructive?redInk():inkPrimary());
    b.setTypeface(TYPE_MEDIUM);b.setLetterSpacing(0.005f);crisp(b);
    b.setGravity(Gravity.START|Gravity.CENTER_VERTICAL);
    b.setPadding(dp(c,16),dp(c,13),dp(c,14),dp(c,13));
    b.setMinHeight(dp(c,52));b.setMinimumHeight(dp(c,52));
    b.setBackground(new RippleDrawable(ColorStateList.valueOf(tone(0x10111827,0x1cffffff)),new ColorDrawable(Color.TRANSPARENT),new ColorDrawable(Color.WHITE)));
    IconTileDrawable tile=new IconTileDrawable(c,glyph,26,destructive,false);
    Drawable chevron=null;
    boolean immediateAction=label!=null&&(label.startsWith("复制")||label.startsWith("重新同步")||label.startsWith("加入本页"));
    if(!destructive&&!immediateAction){Ui.Icon arrow=new Ui.Icon("chevron-right",chevronInk());arrow.setBounds(0,0,dp(c,14),dp(c,14));chevron=arrow;}
    b.setCompoundDrawables(tile,null,chevron,null);b.setCompoundDrawablePadding(dp(c,12));
    group.addView(b,new LinearLayout.LayoutParams(-1,-2));
    return b;
  }
  static LinearLayout modalBanner(Context c,String glyph,String title,String detail,boolean positive){
    return modalBannerTone(c,glyph,title,detail,positive?1:-1);
  }
  static LinearLayout modalWarning(Context c,String glyph,String title,String detail){
    return modalBannerTone(c,glyph,title,detail,0);
  }
  private static LinearLayout modalBannerTone(Context c,String glyph,String title,String detail,int level){
    LinearLayout banner=DesignUi.row(c);banner.setGravity(Gravity.TOP);
    banner.setBackground(new AccentBannerDrawable(c,level));
    banner.setPadding(dp(c,15),dp(c,11),dp(c,13),dp(c,11));
    int ink=level>0?greenInk():level==0?amberInk():redInk();
    ImageView icon=new ImageView(c);icon.setImageDrawable(new Ui.Icon(glyph,ink));
    icon.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
    LinearLayout.LayoutParams ip=new LinearLayout.LayoutParams(dp(c,16),dp(c,16));ip.topMargin=dp(c,2);ip.setMarginEnd(dp(c,9));
    banner.addView(icon,ip);
    LinearLayout copy=DesignUi.column(c);
    if(title!=null&&!title.isEmpty()){
      TextView h=new TextView(c);h.setText(title);h.setTextSize(TypedValue.COMPLEX_UNIT_SP,13.5f);
      h.setTypeface(TYPE_SEMIBOLD);h.setTextColor(ink);crisp(h);
      copy.addView(h,new LinearLayout.LayoutParams(-1,-2));
    }
    if(detail!=null&&!detail.isEmpty()){
      TextView sub=prose(workspaceText(c,detail,SECONDARY_SIZE,title==null||title.isEmpty()?inkPrimary():secondaryInk(),false));
      sub.setTypeface(TYPE_REGULAR);
      if(title!=null&&!title.isEmpty())sub.setPadding(0,dp(c,4),0,0);
      copy.addView(sub,new LinearLayout.LayoutParams(-1,-2));
    }
    banner.addView(copy,new LinearLayout.LayoutParams(0,-2,1));
    return banner;
  }
  static LinearLayout modalEmpty(Context c,String glyph,String title,String detail){
    LinearLayout card=modalGroup(c);card.setGravity(Gravity.CENTER_HORIZONTAL);
    card.setPadding(dp(c,16),dp(c,22),dp(c,16),dp(c,22));
    ImageView icon=new ImageView(c);icon.setImageDrawable(new IconTileDrawable(c,glyph,36,false,false));
    icon.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
    card.addView(icon,new LinearLayout.LayoutParams(dp(c,36),dp(c,36)));
    TextView h=crisp(workspaceText(c,title,15,inkPrimary(),true));h.setTypeface(TYPE_SEMIBOLD);h.setGravity(Gravity.CENTER);h.setPadding(0,dp(c,12),0,0);
    card.addView(h,new LinearLayout.LayoutParams(-1,-2));
    if(detail!=null&&!detail.isEmpty()){
      TextView sub=prose(workspaceText(c,detail,SECONDARY_SIZE,secondaryInk(),false));
      sub.setGravity(Gravity.CENTER);
      sub.setPadding(0,dp(c,5),0,0);card.addView(sub,new LinearLayout.LayoutParams(-1,-2));
    }
    return card;
  }
  static LinearLayout modalImpactPair(Context c,String warnTitle,String warnDetail,String keepTitle,String keepDetail){
    LinearLayout pair=DesignUi.column(c);
    pair.addView(modalBanner(c,"info",warnTitle,warnDetail,false),new LinearLayout.LayoutParams(-1,-2));
    LinearLayout keep=modalBanner(c,"shield",keepTitle,keepDetail,true);
    LinearLayout.LayoutParams kp=new LinearLayout.LayoutParams(-1,-2);kp.topMargin=dp(c,10);
    pair.addView(keep,kp);
    return pair;
  }
  static LinearLayout modalTopicItem(LinearLayout group,String glyph,String title,String detail){
    Context c=group.getContext();
    if(group.getChildCount()>0)group.addView(modalDivider(c,56));
    LinearLayout row=DesignUi.row(c);row.setGravity(Gravity.TOP);
    row.setPadding(dp(c,16),dp(c,12),dp(c,16),dp(c,12));
    ImageView tile=new ImageView(c);tile.setImageDrawable(new IconTileDrawable(c,glyph,28,false,false));
    tile.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
    LinearLayout.LayoutParams tp=new LinearLayout.LayoutParams(dp(c,28),dp(c,28));tp.topMargin=dp(c,1);tp.setMarginEnd(dp(c,12));
    row.addView(tile,tp);
    LinearLayout copy=DesignUi.column(c);
    if(title!=null&&!title.isEmpty())copy.addView(workspaceText(c,title,ACTION_SIZE,TEXT,true),new LinearLayout.LayoutParams(-1,-2));
    if(detail!=null&&!detail.isEmpty()){
      TextView sub=workspaceText(c,detail,SECONDARY_SIZE,secondaryInk(),false);
      balancedBreaks(sub);
      sub.setTextIsSelectable(true);sub.setFontFeatureSettings("tnum");
      if(title!=null&&!title.isEmpty())sub.setPadding(0,dp(c,3),0,0);
      copy.addView(sub,new LinearLayout.LayoutParams(-1,-2));
    }
    row.addView(copy,new LinearLayout.LayoutParams(0,-2,1));
    group.addView(row,new LinearLayout.LayoutParams(-1,-2));
    return row;
  }
  static void stylePill(Button b,boolean primary,boolean destructive){
    if(b==null)return;Context c=b.getContext();
    b.setAllCaps(false);b.setTextSize(TypedValue.COMPLEX_UNIT_SP,14.5f);
    b.setTypeface(primary?TYPE_SEMIBOLD:TYPE_MEDIUM);
    b.setLetterSpacing(primary?0.015f:0.005f);crisp(b);
    b.setMinHeight(dp(c,48));b.setMinimumHeight(dp(c,48));
    b.setPadding(dp(c,16),dp(c,11),dp(c,16),dp(c,11));b.setStateListAnimator(null);
    if(primary){
      b.setTextColor(destructive?Color.WHITE:primaryOnSolid());
      AdaptiveSurface face=destructive
          ?new AdaptiveSurface(c,12,0xffdc2626,0xffd42a36,0x18ffffff,0x18ffffff)
          :new AdaptiveSurface(c,12,0xff16171a,0xfff6f7f9,0x16ffffff,0x18000000);
      b.setBackground(new RippleDrawable(ColorStateList.valueOf(destructive?0x33ffffff:tone(0x24ffffff,0x1a000000)),face,new AdaptiveSurface(c,12,Color.WHITE,Color.WHITE)));
    }else{
      b.setTextColor(destructive?redInk():inkPrimary());
      AdaptiveSurface face=new AdaptiveSurface(c,12,0xffeef0f4,0xff272c37,0x18111827,0x26ffffff);
      b.setBackground(new RippleDrawable(ColorStateList.valueOf(tone(0x12111827,0x20ffffff)),face,new AdaptiveSurface(c,12,Color.WHITE,Color.WHITE)));
    }
  }
  private static void restyleModalControls(View view){
    if(view instanceof Switch)styleSwitch((Switch)view);
    else if(view instanceof ViewGroup){
      ViewGroup group=(ViewGroup)view;
      for(int i=0;i<group.getChildCount();i++)restyleModalControls(group.getChildAt(i));
    }
  }
  static Button menuAction(Modal panel,String label,Runnable run){
    Context c=panel.a;
    boolean destructive=isDestructiveLabel(label);
    String tag=destructive?MENU_DANGER_TAG:MENU_GROUP_TAG;
    LinearLayout group=null;
    int count=panel.body.getChildCount();
    if(count>0){
      View last=panel.body.getChildAt(count-1);
      if(last instanceof LinearLayout&&tag.equals(last.getTag()))group=(LinearLayout)last;
    }
    if(group==null){
      group=modalGroup(c);group.setTag(tag);
      LinearLayout.LayoutParams gp=new LinearLayout.LayoutParams(-1,-2);
      if(count>0)gp.topMargin=dp(c,destructive?10:8);
      panel.body.addView(group,gp);
    }
    String glyph=inferMenuGlyph(label,destructive);
    return modalRowAction(group,glyph,label,destructive,run);
  }
  static LinearLayout card(Context c){return DesignUi.card(c);}
  static void add(LinearLayout box,View card){LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);p.bottomMargin=dp(box.getContext(),10);box.addView(card,p);}
  static TextView secondary(Context c,String value){TextView t=text(c,value,13,MUTED,false);t.setMaxLines(3);t.setEllipsize(TextUtils.TruncateAt.END);t.setPadding(0,dp(c,5),0,0);return t;}
  /** Downloads and network use the same type, selection surface and touch area. */
  static LinearLayout workspaceTabs(Context c,String[] labels,int selected,java.util.function.IntConsumer choose){
    LinearLayout bar=DesignUi.row(c);bar.setBackgroundColor(Color.TRANSPARENT);
    boolean overflow=c.getResources().getConfiguration().fontScale>=1.4f
        ||c.getResources().getConfiguration().screenWidthDp<360;
    for(int i=0;i<labels.length;i++){
      final int index=i;boolean active=i==selected;
      Button tab=link(c,labels[i],()->choose.accept(index));
      tab.setTextSize(TAB_SIZE);tab.setTextColor(active?BLUE:MUTED);
      tab.setTypeface(Typeface.create("sans-serif-medium",Typeface.NORMAL));
      tab.setSelected(active);tab.setContentDescription(labels[i]);readable(tab);
      tab.setSingleLine(false);tab.setMaxLines(1);tab.setHorizontallyScrolling(false);tab.setEllipsize(null);
      tab.setMinWidth(0);tab.setMinimumWidth(0);tab.setMinHeight(dp(c,48));tab.setMinimumHeight(dp(c,48));
      Drawable face=surface(c,active?BLUE_SOFT:Color.TRANSPARENT,18,Color.TRANSPARENT);
      if(active)face.setAlpha(150);
      tab.setBackground(new RippleDrawable(ColorStateList.valueOf(AppAppearance.dark()?0x227faeff:0x140067d8),
          new InsetDrawable(face,dp(c,2),dp(c,6),dp(c,2),dp(c,6)),null));
      tab.setPadding(dp(c,overflow?18:4),dp(c,8),dp(c,overflow?18:4),dp(c,8));
      LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(overflow?-2:0,-2,overflow?0:1);
      if(i>0)p.leftMargin=dp(c,4);bar.addView(tab,p);
    }
    if(!overflow)return bar;
    HorizontalScrollView scroll=new HorizontalScrollView(c);scroll.setHorizontalScrollBarEnabled(false);scroll.addView(bar);
    scroll.post(()->scroll.smoothScrollTo(Math.max(0,bar.getChildAt(selected).getLeft()-dp(c,12)),0));
    LinearLayout host=DesignUi.column(c);host.addView(scroll,new LinearLayout.LayoutParams(-1,-2));return host;
  }
  static LinearLayout tabs(Context c,String[] labels,int selected,java.util.function.IntConsumer click){
    LinearLayout bar=DesignUi.row(c);bar.setPadding(dp(c,3),dp(c,3),dp(c,3),dp(c,3));
    bar.setBackground(new SegmentedTrackDrawable(c));
    boolean large=c.getResources().getConfiguration().fontScale>=1.4f;
    for(int i=0;i<labels.length;i++){
      final int n=i;boolean active=i==selected;Button b=button(c,labels[i],false,()->{hapticTick(bar);click.accept(n);});
      b.setTextSize(TypedValue.COMPLEX_UNIT_SP,13f);b.setTextColor(active?inkPrimary():secondaryInk());b.setSelected(active);b.setSingleLine(true);
      b.setTypeface(active?TYPE_SEMIBOLD:TYPE_MEDIUM);b.setLetterSpacing(0.005f);crisp(b);
      Drawable pill=active?new SegmentedThumbDrawable(c):new ColorDrawable(Color.TRANSPARENT);
      b.setBackground(new RippleDrawable(ColorStateList.valueOf(tone(0x10111827,0x1effffff)),pill,new AdaptiveSurface(c,10,Color.WHITE,Color.WHITE)));
      b.setPadding(dp(c,large?14:6),dp(c,8),dp(c,large?14:6),dp(c,8));b.setMinHeight(dp(c,40));b.setMinimumHeight(dp(c,40));
      LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(large?-2:0,-2,large?0:1);if(i>0)p.setMarginStart(dp(c,2));bar.addView(b,p);
    }
    if(!large)return bar;
    HorizontalScrollView scroll=new HorizontalScrollView(c);scroll.setHorizontalScrollBarEnabled(false);scroll.addView(bar);scroll.post(()->scroll.smoothScrollTo(Math.max(0,bar.getChildAt(selected).getLeft()-dp(c,12)),0));
    LinearLayout host=DesignUi.column(c);host.addView(scroll,new LinearLayout.LayoutParams(-1,-2));return host;
  }
  static LinearLayout nav(Activity a,int selected,java.util.function.IntConsumer action,Button[] buttons){
    if(buttons==null)buttons=new Button[DesignUi.NAV.length];
    LinearLayout bar=DesignUi.column(a);bar.setPadding(dp(a,12),dp(a,10),dp(a,12),dp(a,12));bar.setGravity(Gravity.CENTER_HORIZONTAL);
    bar.setClipChildren(false);bar.setClipToPadding(false);
    int heightDp=navHeightDp(a),height=dp(a,heightDp),radius=(heightDp+1)/2;
    GlassDock dock=new GlassDock(a);dock.setPadding(dp(a,5),dp(a,2),dp(a,5),dp(a,2));
    dock.setBackground(DesignUi.glass(a,radius));GlassMotion.press(dock,false);
    // Destinations share one pill; reading stays an independent mode control.
    FrameLayout reading=new FrameLayout(a){
      @Override protected int[] onCreateDrawableState(int extraSpace){return GlassMotion.childState(this,super.onCreateDrawableState(extraSpace+1));}
      @Override public void onVisibilityAggregated(boolean visible){super.onVisibilityAggregated(visible);if(!visible)GlassMotion.reset(this);}
    };
    reading.setBackground(DesignUi.glass(a,radius));GlassMotion.press(reading,true);
    for(int i=0;i<DesignUi.NAV.length;i++){
      final int n=i;Button b=link(a,DesignUi.NAV[i],()->action.accept(n));b.setTextSize(12);b.setGravity(Gravity.CENTER);
      // Fixed labels use their real content width, not TextView's VERY_WIDE
      // single-line scrolling layout and its compensating horizontal offset.
      b.setSingleLine(false);b.setMaxLines(1);b.setHorizontallyScrolling(false);b.setEllipsize(null);
      // Short Chinese labels still need their fallback font's full vertical metrics.
      b.setIncludeFontPadding(true);if(Build.VERSION.SDK_INT>=28)b.setFallbackLineSpacing(true);
      b.setTypeface(Typeface.create("sans-serif",Typeface.NORMAL));
      b.setMinWidth(dp(a,48));b.setMinimumWidth(dp(a,48));
      b.setPadding(dp(a,2),dp(a,8),dp(a,2),dp(a,8));
      b.setContentDescription(i==WorkspaceNavigation.READING?"进入专注阅读模式":DesignUi.NAV[i]);
      int iconDp=i==0?20:22,iconSize=dp(a,iconDp);
      Ui.Icon icon=new Ui.Icon(DesignUi.GLYPHS[i],DesignUi.GLASS_MUTED);icon.setBounds(0,0,iconSize,iconSize);
      // Equal icon-plus-gap slots align every label while preserving optical icon sizes.
      b.setCompoundDrawables(null,icon,null,null);b.setCompoundDrawablePadding(dp(a,24-iconDp));
      b.addOnLayoutChangeListener((v,l,t,r,bottom,ol,ot,or,ob)->centerDockContents((Button)v));
      b.setBackground(navFeedback(a,i==WorkspaceNavigation.READING,radius));
      if(i==WorkspaceNavigation.READING){
        reading.addView(b,new FrameLayout.LayoutParams(-1,-1));
        ((DesignUi.ActionButton)b).pressedSurface(reading);
      }else{
        dock.addView(b,new LinearLayout.LayoutParams(0,-1,1));
        ((DesignUi.ActionButton)b).pressedSurface(dock);
      }
      buttons[i]=b;
    }
    GlassNavigationRow row=new GlassNavigationRow(a,dock,reading,height);
    bar.addView(row,new LinearLayout.LayoutParams(-1,-2));markNav(buttons,selected);return bar;
  }
  /** Native workspaces use all five destinations; callbacks carry AppHub page IDs. */
  static LinearLayout workspaceNav(Activity a,int page,java.util.function.IntConsumer action,Button[] buttons){
    if(buttons==null)buttons=new Button[WORKSPACE_PAGES.length];
    if(buttons.length!=WORKSPACE_PAGES.length)throw new IllegalArgumentException("Five workspace buttons required");
    int heightDp=navHeightDp(a),radius=(heightDp+1)/2;
    GlassDock dock=new GlassDock(a,true);dock.setPadding(dp(a,5),dp(a,2),dp(a,5),dp(a,2));
    LinearLayout bar=new WorkspaceNavBar(a,dock,dp(a,heightDp));bar.setPadding(dp(a,12),dp(a,10),dp(a,12),dp(a,12));
    bar.setClipChildren(false);bar.setClipToPadding(false);
    dock.setBackground(DesignUi.glass(a,radius));GlassMotion.press(dock,false);
    for(int i=0;i<WORKSPACE_PAGES.length;i++){
      final int destination=WORKSPACE_PAGES[i];
      Button b=link(a,WORKSPACE_LABELS[i],()->action.accept(destination));b.setTextSize(12);b.setGravity(Gravity.CENTER);
      b.setSingleLine(false);b.setMaxLines(2);b.setHorizontallyScrolling(false);b.setEllipsize(null);
      b.setIncludeFontPadding(true);if(Build.VERSION.SDK_INT>=28)b.setFallbackLineSpacing(true);
      b.setTypeface(Typeface.create("sans-serif",Typeface.NORMAL));
      b.setMinWidth(dp(a,48));b.setMinimumWidth(dp(a,48));b.setContentDescription(WORKSPACE_LABELS[i]);
      int iconDp=destination==AppHub.CHAT?20:22,iconSize=dp(a,iconDp);
      Ui.Icon icon=new Ui.Icon(WORKSPACE_GLYPHS[i],DesignUi.GLASS_MUTED);icon.setBounds(0,0,iconSize,iconSize);
      b.setCompoundDrawables(null,icon,null,null);b.setCompoundDrawablePadding(dp(a,24-iconDp));
      b.addOnLayoutChangeListener((v,l,t,r,bottom,ol,ot,or,ob)->centerDockContents((Button)v));
      b.setBackground(navFeedback(a,false,radius));b.setPadding(dp(a,2),dp(a,8),dp(a,2),dp(a,8));
      dock.addView(b,new LinearLayout.LayoutParams(0,-1,1));
      ((DesignUi.ActionButton)b).pressedSurface(dock);buttons[i]=b;
    }
    markWorkspaceNav(buttons,page);return bar;
  }
  /** Equal destinations keep the system text size and grow for wrapped labels. */
  private static final class WorkspaceNavBar extends LinearLayout {
    private final GlassDock dock;private final int minimumHeight,verticalPadding;
    WorkspaceNavBar(Context c,GlassDock dock,int minimumHeight){
      super(c);this.dock=dock;this.minimumHeight=minimumHeight;verticalPadding=dp(c,16);
      setOrientation(VERTICAL);addView(dock,new LinearLayout.LayoutParams(-1,minimumHeight));
    }
    @Override protected void onMeasure(int widthSpec,int heightSpec){
      super.onMeasure(widthSpec,heightSpec);
      int count=dock.getChildCount();if(count==0)return;
      int columnWidth=Math.max(0,(dock.getMeasuredWidth()-dock.getPaddingLeft()-dock.getPaddingRight())/count);
      int height=minimumHeight;
      for(int i=0;i<count;i++){
        View button=dock.getChildAt(i);
        button.measure(MeasureSpec.makeMeasureSpec(columnWidth,MeasureSpec.EXACTLY),
          MeasureSpec.makeMeasureSpec(0,MeasureSpec.UNSPECIFIED));
        // Centering changes padding after layout. Measure the native content
        // with its original breathing room, without accumulating that padding.
        int content=button.getMeasuredHeight()-button.getPaddingTop()-button.getPaddingBottom();
        height=Math.max(height,content+verticalPadding+dock.getPaddingTop()+dock.getPaddingBottom());
      }
      dock.getLayoutParams().height=height;
      super.onMeasure(widthSpec,heightSpec);
    }
  }
  static void markWorkspaceNav(Button[] tabs,int page){
    int position=-1;
    for(int i=0;i<WORKSPACE_PAGES.length;i++)if(WORKSPACE_PAGES[i]==page){position=i;break;}
    markNav(tabs,position);
  }
  private static int navHeightDp(Context c){return Math.max(72,(int)Math.ceil(50+22*c.getResources().getConfiguration().fontScale));}
  private static Drawable navFeedback(Context context,boolean reading,int readingRadius){
    int radius=reading?readingRadius:23;
    Drawable content;
    if(reading){
      GradientDrawable wash=new GradientDrawable();wash.setCornerRadius(dp(context,radius));
      int selectedWash=(DesignUi.BLUE&0x00ffffff)|(AppAppearance.dark()?0x16000000:0x0e000000);
      wash.setColor(new ColorStateList(new int[][]{{android.R.attr.state_selected},{}},new int[]{selectedWash,Color.TRANSPARENT}));
      // Reading shares the requested light-blue selected wash with the dock.
      content=wash;
    }else content=new ColorDrawable(Color.TRANSPARENT);
    return new InsetDrawable(content,dp(context,LiquidGlassDrawable.INSET_DP+1)){
      @Override public boolean getPadding(Rect padding){padding.setEmpty();return false;}
    };
  }
  private static void centerDockContents(Button b){
    Drawable icon=b.getCompoundDrawables()[1];Layout label=b.getLayout();
    if(icon==null||label==null||b.getHeight()==0)return;
    // TextView pins a top compound drawable to its padding. Center the complete
    // icon/label block using the laid-out fallback glyphs and font padding.
    // getLineHeight() is only standard line spacing and can truncate this Layout.
    int block=icon.getBounds().height()+b.getCompoundDrawablePadding()+label.getHeight();
    int spare=Math.max(0,b.getHeight()-block),top=spare/2,bottom=spare-top;
    if(b.getPaddingTop()!=top||b.getPaddingBottom()!=bottom)b.setPadding(dp(b.getContext(),2),top,dp(b.getContext(),2),bottom);
  }
  static void markNav(Button[] tabs,int selected){
    if(tabs==null)return;
    GlassDock dock=null;
    for(int i=0;i<tabs.length;i++){
      Button b=tabs[i];if(b==null)continue;boolean active=i==selected;
      int ink=active?DesignUi.GLASS_INK:DesignUi.GLASS_MUTED;
      b.setSelected(active);b.setTextColor(ink);
      b.setTypeface(Typeface.create(active?"sans-serif-medium":"sans-serif",Typeface.NORMAL));
      Drawable icon=b.getCompoundDrawables()[1];if(icon instanceof Ui.Icon){((Ui.Icon)icon).color=active?DesignUi.BLUE:DesignUi.GLASS_MUTED;((Ui.Icon)icon).solid=active;}b.invalidate();
      if(b.getParent() instanceof GlassDock)dock=(GlassDock)b.getParent();
    }
    if(dock!=null)dock.selectionChanged();
  }
  static void insets(Activity a,View root){insets(a,root,null);}
  static void insets(Activity a,View root,java.util.function.Consumer<Boolean> keyboard){
    a.getWindow().setStatusBarColor(CHAT_BG);a.getWindow().setNavigationBarColor(WHITE);if(Build.VERSION.SDK_INT>=29)a.getWindow().setNavigationBarContrastEnforced(false);
    if(Build.VERSION.SDK_INT>=30)root.setOnApplyWindowInsetsListener((v,ins)->{
      Insets safe=ins.getInsets(WindowInsets.Type.systemBars()|WindowInsets.Type.displayCutout()|WindowInsets.Type.ime());v.setPadding(safe.left,safe.top,safe.right,safe.bottom);
      if(keyboard!=null)keyboard.accept(ins.isVisible(WindowInsets.Type.ime())&&ins.getInsets(WindowInsets.Type.ime()).bottom>0);return WindowInsets.CONSUMED;
    });else{root.setFitsSystemWindows(true);if(keyboard!=null)root.getViewTreeObserver().addOnGlobalLayoutListener(()->{
      Rect visible=new Rect();a.getWindow().getDecorView().getWindowVisibleDisplayFrame(visible);int missing=a.getWindow().getDecorView().getHeight()-visible.bottom;
      keyboard.accept(missing>dp(a,120));
    });}root.requestApplyInsets();
  }

  static final class Modal extends ThemedDialog {
    final Activity a;final LinearLayout root,body,footer,head;final ScrollView scroll;final ColorDrawable footerBoundaryColor;final Drawable footerBoundary;final Button close;boolean sheet;Runnable cancel=this::dismiss;
    Modal(Activity a,String title){
      super(a);this.a=a;
      root=DesignUi.column(a);root.setClipChildren(false);root.setClipToPadding(false);
      root.setPadding(dp(a,18),dp(a,14),dp(a,18),dp(a,18));
      root.setBackground(new CardSurfaceDrawable(a,24f,0xfff2f3f6,0xff121318));
      head=DesignUi.row(a);head.setClipChildren(false);head.setClipToPadding(false);
      head.setPadding(0,0,0,dp(a,4));
      TextView heading=heroTitle(a,title);heading.setMaxLines(3);heading.setGravity(Gravity.CENTER_VERTICAL);heading.setMinimumHeight(dp(a,48));heading.setContentDescription(title);
      if(Build.VERSION.SDK_INT>=28)heading.setAccessibilityHeading(true);
      head.addView(heading,new LinearLayout.LayoutParams(0,-2,1));
      close=iconButton(a,"close","关闭"+title,()->{hapticTick(root);cancel.run();});
      int closeInset=dp(a,8);
      AdaptiveSurface disc=new AdaptiveSurface(a,999,0xffe8eaef,0xff252935,0x10111827,0x1cffffff);
      close.setBackground(new RippleDrawable(ColorStateList.valueOf(tone(0x14111827,0x24ffffff)),
          new InsetDrawable(disc,closeInset,closeInset,closeInset,closeInset),
          new InsetDrawable(new AdaptiveSurface(a,999,Color.WHITE,Color.WHITE),closeInset,closeInset,closeInset,closeInset)));
      close.setTranslationX(closeInset);
      head.addView(close,new LinearLayout.LayoutParams(dp(a,48),dp(a,48)));
      root.addView(head);
      body=DesignUi.column(a);scroll=new ScrollView(a);scroll.setFillViewport(false);scroll.addView(body);
      root.addView(scroll,new LinearLayout.LayoutParams(-1,-2));
      footer=DesignUi.row(a);footer.setPadding(0,dp(a,14),0,0);footer.setVisibility(View.GONE);
      footerBoundaryColor=new ColorDrawable(dividerColor());
      LayerDrawable edge=new LayerDrawable(new Drawable[]{footerBoundaryColor});edge.setLayerSize(0,-1,Math.max(1,dp(a,1)/2));edge.setLayerGravity(0,Gravity.TOP);footerBoundary=edge;
      root.addView(footer);
      setContentView(root);setCanceledOnTouchOutside(false);
      getWindow().setBackgroundDrawable(new ColorDrawable(Color.TRANSPARENT));getWindow().setDimAmount(AppAppearance.dark()?.58f:.32f);getWindow().addFlags(WindowManager.LayoutParams.FLAG_DIM_BEHIND);
      AppAppearance.dialogBlur(getWindow(),a);
      getWindow().setGravity(Gravity.CENTER);getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE|WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_HIDDEN);
      if(Build.VERSION.SDK_INT>=30)root.setOnApplyWindowInsetsListener((v,in)->{v.post(this::resize);return in;});
    }
    Modal hideClose(){close.setVisibility(View.GONE);return this;}
    Modal asSheet(){
      if(sheet)return this;sheet=true;
      root.setPadding(dp(a,18),dp(a,8),dp(a,18),dp(a,18));
      FrameLayout grip=new FrameLayout(a);View mark=new View(a);mark.setBackground(new AdaptiveSurface(a,999,0x22111827,0x2effffff));
      FrameLayout.LayoutParams p=new FrameLayout.LayoutParams(dp(a,36),dp(a,4),Gravity.TOP|Gravity.CENTER_HORIZONTAL);p.topMargin=dp(a,2);grip.addView(mark,p);
      grip.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);root.addView(grip,0,new LinearLayout.LayoutParams(-1,dp(a,12)));
      getWindow().setGravity(Gravity.BOTTOM|Gravity.CENTER_HORIZONTAL);WindowManager.LayoutParams attrs=getWindow().getAttributes();attrs.y=dp(a,12);getWindow().setAttributes(attrs);
      getWindow().setWindowAnimations(R.style.FloatingPanelAnimation);return this;
    }
    void buttons(String secondary,Runnable back,String primary,Runnable save){
      footer.removeAllViews();
      boolean stacked=a.getResources().getConfiguration().fontScale>=1.4f
          ||(!secondary.isEmpty()&&!primary.isEmpty()&&(secondary.length()+primary.length()>14||secondary.length()>8||primary.length()>8));
      footer.setOrientation(stacked?LinearLayout.VERTICAL:LinearLayout.HORIZONTAL);
      if(!secondary.isEmpty()){
        Button s=button(a,secondary,false,()->{hapticClick(footer);back.run();});stylePill(s,false,isDestructiveLabel(secondary));
        if(!stacked&&!primary.isEmpty())styleDualButton(s);
        footer.addView(s,new LinearLayout.LayoutParams(stacked?-1:0,-2,stacked?0:1));
      }
      if(!primary.isEmpty()){
        Button b=button(a,primary,true,()->{hapticClick(footer);save.run();});stylePill(b,true,isDestructiveLabel(primary));
        if(!stacked&&!secondary.isEmpty())styleDualButton(b);
        LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(stacked?-1:0,-2,stacked?0:1.25f);
        if(footer.getChildCount()>0){if(stacked)p.topMargin=dp(a,10);else p.setMarginStart(dp(a,10));}
        footer.addView(b,p);
      }
      footer.setVisibility(footer.getChildCount()==0?View.GONE:View.VISIBLE);
    }
    Button primary(){return footer.getChildCount()==0?null:(Button)footer.getChildAt(footer.getChildCount()-1);}
    void resize(){
      if(!isShowing())return;Rect visible=new Rect();getWindow().getDecorView().getWindowVisibleDisplayFrame(visible);
      footer.setVisibility(footer.getChildCount()==0?View.GONE:View.VISIBLE);
      int width=Math.min(dp(a,sheet?480:420),Math.max(dp(a,200),visible.width()-dp(a,sheet?20:32))),available=visible.height();
      if(available<=0)available=a.getResources().getDisplayMetrics().heightPixels;
      int max=Math.max(dp(a,160),(int)(available*.84)),inner=width-root.getPaddingLeft()-root.getPaddingRight();
      body.measure(View.MeasureSpec.makeMeasureSpec(inner,View.MeasureSpec.EXACTLY),View.MeasureSpec.makeMeasureSpec(0,View.MeasureSpec.UNSPECIFIED));
      footer.measure(View.MeasureSpec.makeMeasureSpec(inner,View.MeasureSpec.EXACTLY),View.MeasureSpec.makeMeasureSpec(0,View.MeasureSpec.UNSPECIFIED));
      head.measure(View.MeasureSpec.makeMeasureSpec(inner,View.MeasureSpec.EXACTLY),View.MeasureSpec.makeMeasureSpec(0,View.MeasureSpec.UNSPECIFIED));
      int footerH=footer.getVisibility()==View.VISIBLE?footer.getMeasuredHeight():0;
      int cap=Math.max(dp(a,48),max-root.getPaddingTop()-root.getPaddingBottom()-head.getMeasuredHeight()-footerH-(sheet?dp(a,12):0));
      int lineColor=dividerColor();if(footerBoundaryColor.getColor()!=lineColor)footerBoundaryColor.setColor(lineColor);
      Drawable edge=body.getMeasuredHeight()>cap&&footer.getChildCount()>0?footerBoundary:null;
      if(footer.getBackground()!=edge){footer.setBackground(edge);footer.setPadding(0,dp(a,14),0,0);}
      scroll.getLayoutParams().height=Math.min(cap,body.getMeasuredHeight());scroll.requestLayout();getWindow().setLayout(width,-2);
    }
    @Override public void show(){super.show();if(getWindow()!=null)getWindow().setDimAmount(AppAppearance.dark()?.58f:.32f);restyleModalControls(root);resize();}
    @Override public void onBackPressed(){cancel.run();}
    void note(String s){
      TextView t=workspaceText(a,"",13,secondaryInk(),false);DesignUi.readable(t,s,"重新加载","配色");
      balancedBreaks(t);
      t.setPadding(dp(a,4),dp(a,8),dp(a,4),dp(a,8));body.addView(t);
    }
  }
  static Modal message(Activity a,String title,String value){
    Modal d=new Modal(a,title);
    LinearLayout card=modalGroup(a);card.setPadding(dp(a,16),dp(a,14),dp(a,16),dp(a,14));
    TextView bodyText=workspaceText(a,value,BODY_SIZE,TEXT,false);bodyText.setTextIsSelectable(true);
    balancedBreaks(bodyText);
    card.addView(bodyText,new LinearLayout.LayoutParams(-1,-2));
    d.body.addView(card,new LinearLayout.LayoutParams(-1,-2));
    d.buttons("关闭",d::dismiss,"",()->{});d.show();return d;
  }
}
