package local.pocketchat;

import android.app.*;
import android.content.*;
import android.content.res.ColorStateList;
import android.graphics.*;
import android.graphics.drawable.*;
import android.os.Build;
import android.text.Layout;
import android.text.TextUtils;
import android.view.*;
import android.widget.*;

/** Shared native controls: grouped surfaces, compact navigation and floating panels. */
final class ReferenceUi {
  static int BG=DesignUi.BG,CHAT_BG=0xfff9fbfe,WHITE=0xffffffff,TEXT=DesignUi.TEXT,
    MUTED=DesignUi.MUTED,LINE=DesignUi.LINE,BLUE=DesignUi.BLUE,BLUE_SOFT=0xffedf4ff,
    GREEN=DesignUi.GREEN,ORANGE=0xffa96c0a,RED=DesignUi.RED;
  // Page identities deliberately differ from visual positions in this bar.
  private static final int[] WORKSPACE_PAGES={AppHub.CHAT,AppHub.ENVIRONMENTS,AppHub.DOWNLOADS,AppHub.NETWORK,AppHub.SETTINGS};
  private static final String[] WORKSPACE_LABELS={"会话","环境","下载","网络","设置"},WORKSPACE_GLYPHS={"chat","window","download","globe","settings"};
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
  static Button menuAction(Modal panel,String label,Runnable run){
    Context c=panel.a;
    if(panel.body.getChildCount()>0){View line=new View(c);line.setBackgroundColor(LINE);LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,Math.max(1,dp(c,1)/2));p.leftMargin=dp(c,12);p.rightMargin=dp(c,12);panel.body.addView(line,p);}
    Button b=link(c,label,run);boolean destructive=label.startsWith("删除")||label.startsWith("清空");b.setTextSize(16);b.setTextColor(destructive?RED:TEXT);b.setGravity(Gravity.START|Gravity.CENTER_VERTICAL);b.setPadding(dp(c,12),dp(c,14),dp(c,12),dp(c,14));b.setMinHeight(dp(c,54));b.setMinimumHeight(dp(c,54));
    String glyph=destructive?"trash":label.contains("分享")?"share":label.contains("复制")?"clipboard":label.contains("另存")||label.contains("保存位置")?"download":label.contains("会话")?"chat":label.equals("打开")?"file":label.contains("编辑")?"new":label.contains("网络")?"globe":label.contains("下载")?"download":label.contains("环境")?"window":label.contains("刷新")||label.contains("重新连接")?"refresh":"info";
    Ui.Icon icon=new Ui.Icon(glyph,destructive?RED:BLUE);icon.setBounds(0,0,dp(c,21),dp(c,21));b.setCompoundDrawables(icon,null,null,null);b.setCompoundDrawablePadding(dp(c,14));
    panel.body.addView(b,new LinearLayout.LayoutParams(-1,-2));return b;
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
    LinearLayout bar=DesignUi.row(c);bar.setPadding(dp(c,4),0,dp(c,4),0);bar.setBackground(surface(c,0xfff0f2f6,13,Color.TRANSPARENT));
    boolean large=c.getResources().getConfiguration().fontScale>=1.4f;
    for(int i=0;i<labels.length;i++){
      final int n=i;Button b=button(c,labels[i],false,()->click.accept(n));
      b.setTextColor(i==selected?TEXT:MUTED);b.setSelected(i==selected);b.setSingleLine(true);
      b.setTypeface(Typeface.create("sans-serif-medium",Typeface.NORMAL));
      b.setBackground(new RippleDrawable(ColorStateList.valueOf(0x182468f2),new InsetDrawable(surface(c,i==selected?WHITE:Color.TRANSPARENT,10,Color.TRANSPARENT),0,dp(c,4),0,dp(c,4)),null));
      b.setPadding(dp(c,large?12:4),0,dp(c,large?12:4),0);
      LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(large?-2:0,dp(c,48),large?0:1);if(i>0)p.leftMargin=dp(c,4);bar.addView(b,p);
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
    LinearLayout bar=DesignUi.column(a);bar.setPadding(dp(a,12),dp(a,10),dp(a,12),dp(a,12));
    bar.setClipChildren(false);bar.setClipToPadding(false);
    int heightDp=navHeightDp(a),radius=(heightDp+1)/2;
    GlassDock dock=new GlassDock(a,true);dock.setPadding(dp(a,5),dp(a,2),dp(a,5),dp(a,2));
    dock.setBackground(DesignUi.glass(a,radius));GlassMotion.press(dock,false);
    for(int i=0;i<WORKSPACE_PAGES.length;i++){
      final int destination=WORKSPACE_PAGES[i];
      Button b=link(a,WORKSPACE_LABELS[i],()->action.accept(destination));b.setTextSize(12);b.setGravity(Gravity.CENTER);
      b.setSingleLine(false);b.setMaxLines(1);b.setHorizontallyScrolling(false);b.setEllipsize(null);
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
    bar.addView(dock,new LinearLayout.LayoutParams(-1,dp(a,heightDp)));markWorkspaceNav(buttons,page);return bar;
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
    final Activity a;final LinearLayout root,body,footer,head;final ScrollView scroll;final ColorDrawable footerBoundaryColor;final Drawable footerBoundary;boolean sheet;Runnable cancel=this::dismiss;
    Modal(Activity a,String title){super(a);this.a=a;root=DesignUi.column(a);root.setPadding(dp(a,16),dp(a,12),dp(a,16),dp(a,16));root.setBackground(surface(a,WHITE,24,Color.TRANSPARENT));head=DesignUi.row(a);TextView heading=text(a,title,18,TEXT,true);heading.setMaxLines(3);heading.setGravity(Gravity.CENTER_VERTICAL);heading.setMinimumHeight(dp(a,48));heading.setContentDescription(title);if(Build.VERSION.SDK_INT>=28)heading.setAccessibilityHeading(true);head.addView(heading,new LinearLayout.LayoutParams(0,-2,1));Button close=iconButton(a,"close","关闭"+title,()->cancel.run());head.addView(close,new LinearLayout.LayoutParams(dp(a,48),dp(a,48)));root.addView(head);body=DesignUi.column(a);scroll=new ScrollView(a);scroll.setFillViewport(false);scroll.addView(body);root.addView(scroll,new LinearLayout.LayoutParams(-1,-2));footer=DesignUi.row(a);footer.setPadding(0,dp(a,12),0,0);footerBoundaryColor=new ColorDrawable(LINE);LayerDrawable edge=new LayerDrawable(new Drawable[]{footerBoundaryColor});edge.setLayerSize(0,-1,Math.max(1,dp(a,1)/2));edge.setLayerGravity(0,Gravity.TOP);footerBoundary=edge;root.addView(footer);setContentView(root);setCanceledOnTouchOutside(false);getWindow().setBackgroundDrawable(new ColorDrawable(Color.TRANSPARENT));getWindow().setDimAmount(.28f);getWindow().addFlags(WindowManager.LayoutParams.FLAG_DIM_BEHIND);getWindow().setGravity(Gravity.CENTER);getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE|WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_HIDDEN);if(Build.VERSION.SDK_INT>=30)root.setOnApplyWindowInsetsListener((v,in)->{v.post(this::resize);return in;});}
    Modal asSheet(){
      if(sheet)return this;sheet=true;
      FrameLayout grip=new FrameLayout(a);View mark=new View(a);mark.setBackground(surface(a,LINE,2,Color.TRANSPARENT));
      FrameLayout.LayoutParams p=new FrameLayout.LayoutParams(dp(a,36),dp(a,4),Gravity.TOP|Gravity.CENTER_HORIZONTAL);p.topMargin=dp(a,2);grip.addView(mark,p);
      grip.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);root.addView(grip,0,new LinearLayout.LayoutParams(-1,dp(a,14)));
      getWindow().setGravity(Gravity.BOTTOM|Gravity.CENTER_HORIZONTAL);WindowManager.LayoutParams attrs=getWindow().getAttributes();attrs.y=dp(a,12);getWindow().setAttributes(attrs);
      getWindow().setWindowAnimations(R.style.FloatingPanelAnimation);return this;
    }
    void buttons(String secondary,Runnable back,String primary,Runnable save){
      footer.removeAllViews();boolean stacked=a.getResources().getConfiguration().fontScale>=1.4f;
      footer.setOrientation(stacked?LinearLayout.VERTICAL:LinearLayout.HORIZONTAL);
      if(!secondary.isEmpty())footer.addView(button(a,secondary,false,back),new LinearLayout.LayoutParams(stacked?-1:0,-2,stacked?0:1));
      if(!primary.isEmpty()){
        Button b=button(a,primary,true,save);LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(stacked?-1:0,-2,stacked?0:1.5f);
        if(footer.getChildCount()>0){if(stacked)p.topMargin=dp(a,8);else p.leftMargin=dp(a,8);}footer.addView(b,p);
      }
    }
    Button primary(){return footer.getChildCount()==0?null:(Button)footer.getChildAt(footer.getChildCount()-1);}
    void resize(){if(!isShowing())return;Rect visible=new Rect();getWindow().getDecorView().getWindowVisibleDisplayFrame(visible);int width=Math.min(dp(a,sheet?480:420),Math.max(dp(a,200),visible.width()-dp(a,sheet?20:32))),available=visible.height();if(available<=0)available=a.getResources().getDisplayMetrics().heightPixels;int max=Math.max(dp(a,160),(int)(available*.82)),inner=width-dp(a,32);body.measure(View.MeasureSpec.makeMeasureSpec(inner,View.MeasureSpec.EXACTLY),View.MeasureSpec.makeMeasureSpec(0,View.MeasureSpec.UNSPECIFIED));footer.measure(View.MeasureSpec.makeMeasureSpec(inner,View.MeasureSpec.EXACTLY),View.MeasureSpec.makeMeasureSpec(0,View.MeasureSpec.UNSPECIFIED));head.measure(View.MeasureSpec.makeMeasureSpec(inner,View.MeasureSpec.EXACTLY),View.MeasureSpec.makeMeasureSpec(0,View.MeasureSpec.UNSPECIFIED));int cap=Math.max(dp(a,48),max-root.getPaddingTop()-root.getPaddingBottom()-head.getMeasuredHeight()-footer.getMeasuredHeight()-(sheet?dp(a,14):0));if(footerBoundaryColor.getColor()!=LINE)footerBoundaryColor.setColor(LINE);Drawable edge=body.getMeasuredHeight()>cap&&footer.getChildCount()>0?footerBoundary:null;if(footer.getBackground()!=edge){footer.setBackground(edge);footer.setPadding(0,dp(a,12),0,0);}scroll.getLayoutParams().height=Math.min(cap,body.getMeasuredHeight());scroll.requestLayout();getWindow().setLayout(width,-2);}
    @Override public void show(){super.show();resize();}
    @Override public void onBackPressed(){cancel.run();}
    void note(String s){TextView t=text(a,"",13,MUTED,false);DesignUi.readable(t,s,"重新加载","配色");t.setPadding(0,dp(a,8),0,dp(a,8));body.addView(t);}
  }
  static Modal message(Activity a,String title,String value){Modal d=new Modal(a,title);d.note(value);d.buttons("关闭",d::dismiss,"",()->{});d.show();return d;}
}
