package local.pocketchat;

import android.app.*;
import android.content.*;
import android.content.res.ColorStateList;
import android.graphics.*;
import android.graphics.drawable.*;
import android.os.Build;
import android.text.TextUtils;
import android.view.*;
import android.widget.*;

/** Shared native controls: grouped surfaces, compact navigation and floating panels. */
final class ReferenceUi {
  static int BG=DesignUi.BG,CHAT_BG=0xfff9fbfe,WHITE=0xffffffff,TEXT=DesignUi.TEXT,
    MUTED=DesignUi.MUTED,LINE=DesignUi.LINE,BLUE=DesignUi.BLUE,BLUE_SOFT=0xffedf4ff,
    GREEN=DesignUi.GREEN,ORANGE=0xffa96c0a,RED=DesignUi.RED;
  static int dp(Context c,int n){return Ui.dp(c,n);}
  static TextView text(Context c,String value,int size,int color,boolean strong){TextView v=DesignUi.text(c,value,size,color);if(strong)v.setTypeface(Typeface.create("sans-serif-medium",Typeface.NORMAL));return v;}
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
    String glyph=destructive?"trash":label.contains("分享")?"share":label.contains("编辑")?"new":label.contains("网络")?"globe":label.contains("下载")?"download":label.contains("环境")?"window":label.contains("刷新")||label.contains("重新连接")?"refresh":"info";
    Ui.Icon icon=new Ui.Icon(glyph,destructive?RED:BLUE);icon.setBounds(0,0,dp(c,21),dp(c,21));b.setCompoundDrawables(icon,null,null,null);b.setCompoundDrawablePadding(dp(c,14));
    panel.body.addView(b,new LinearLayout.LayoutParams(-1,-2));return b;
  }
  static LinearLayout card(Context c){return DesignUi.card(c);}
  static void add(LinearLayout box,View card){LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);p.bottomMargin=dp(box.getContext(),10);box.addView(card,p);}
  static TextView secondary(Context c,String value){TextView t=text(c,value,13,MUTED,false);single(t);t.setPadding(0,dp(c,5),0,0);return t;}
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
  static LinearLayout nav(Activity a,int selected,java.util.function.IntConsumer action,Button[] buttons){if(buttons==null)buttons=new Button[5];LinearLayout bar=DesignUi.row(a);bar.setPadding(dp(a,6),0,dp(a,6),0);bar.setBackgroundColor(WHITE);for(int i=0;i<5;i++){final int n=i;Button b=link(a,DesignUi.NAV[i],()->action.accept(n));b.setTextSize(12);b.setPadding(0,dp(a,4),0,dp(a,4));Ui.Icon icon=new Ui.Icon(DesignUi.GLYPHS[i],MUTED);icon.setBounds(0,0,dp(a,21),dp(a,21));b.setCompoundDrawables(null,icon,null,null);b.setCompoundDrawablePadding(dp(a,3));bar.addView(b,new LinearLayout.LayoutParams(0,dp(a,Math.max(60,(int)(36+16*a.getResources().getConfiguration().fontScale))),1));buttons[i]=b;}markNav(buttons,selected);return bar;}
  static void markNav(Button[] tabs,int selected){if(tabs==null)return;for(int i=0;i<tabs.length;i++){Button b=tabs[i];b.setSelected(i==selected);b.setTextColor(i==selected?BLUE:MUTED);b.setBackground(new InsetDrawable(Ui.ripple(b.getContext(),i==selected?BLUE_SOFT:Color.TRANSPARENT,16),dp(b.getContext(),3),dp(b.getContext(),5),dp(b.getContext(),3),dp(b.getContext(),5)));Drawable icon=b.getCompoundDrawables()[1];if(icon instanceof Ui.Icon)((Ui.Icon)icon).color=i==selected?BLUE:MUTED;b.invalidate();}}
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
    final Activity a;final LinearLayout root,body,footer,head;final ScrollView scroll;boolean sheet;Runnable cancel=this::dismiss;
    Modal(Activity a,String title){super(a);this.a=a;root=DesignUi.column(a);root.setPadding(dp(a,16),dp(a,12),dp(a,16),dp(a,16));root.setBackground(surface(a,WHITE,24,Color.TRANSPARENT));head=DesignUi.row(a);TextView heading=text(a,title,18,TEXT,true);heading.setMaxLines(3);heading.setGravity(Gravity.CENTER_VERTICAL);heading.setMinimumHeight(dp(a,48));heading.setContentDescription(title);if(Build.VERSION.SDK_INT>=28)heading.setAccessibilityHeading(true);head.addView(heading,new LinearLayout.LayoutParams(0,-2,1));Button close=iconButton(a,"close","关闭"+title,()->cancel.run());head.addView(close,new LinearLayout.LayoutParams(dp(a,48),dp(a,48)));root.addView(head);body=DesignUi.column(a);scroll=new ScrollView(a);scroll.setFillViewport(false);scroll.addView(body);root.addView(scroll,new LinearLayout.LayoutParams(-1,-2));footer=DesignUi.row(a);footer.setPadding(0,dp(a,12),0,0);root.addView(footer);setContentView(root);setCanceledOnTouchOutside(false);getWindow().setBackgroundDrawable(new ColorDrawable(Color.TRANSPARENT));getWindow().setDimAmount(.28f);getWindow().addFlags(WindowManager.LayoutParams.FLAG_DIM_BEHIND);getWindow().setGravity(Gravity.CENTER);getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE|WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_HIDDEN);if(Build.VERSION.SDK_INT>=30)root.setOnApplyWindowInsetsListener((v,in)->{v.post(this::resize);return in;});}
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
    void resize(){if(!isShowing())return;Rect visible=new Rect();getWindow().getDecorView().getWindowVisibleDisplayFrame(visible);int width=Math.min(dp(a,sheet?480:420),Math.max(dp(a,200),visible.width()-dp(a,sheet?20:32))),available=visible.height();if(available<=0)available=a.getResources().getDisplayMetrics().heightPixels;int max=Math.max(dp(a,160),(int)(available*.82)),inner=width-dp(a,32);body.measure(View.MeasureSpec.makeMeasureSpec(inner,View.MeasureSpec.EXACTLY),View.MeasureSpec.makeMeasureSpec(0,View.MeasureSpec.UNSPECIFIED));footer.measure(View.MeasureSpec.makeMeasureSpec(inner,View.MeasureSpec.EXACTLY),View.MeasureSpec.makeMeasureSpec(0,View.MeasureSpec.UNSPECIFIED));head.measure(View.MeasureSpec.makeMeasureSpec(inner,View.MeasureSpec.EXACTLY),View.MeasureSpec.makeMeasureSpec(0,View.MeasureSpec.UNSPECIFIED));int cap=Math.max(dp(a,48),max-root.getPaddingTop()-root.getPaddingBottom()-head.getMeasuredHeight()-footer.getMeasuredHeight()-(sheet?dp(a,14):0));scroll.getLayoutParams().height=Math.min(cap,body.getMeasuredHeight());scroll.requestLayout();getWindow().setLayout(width,-2);}
    @Override public void show(){super.show();resize();}
    @Override public void onBackPressed(){cancel.run();}
    void note(String s){TextView t=text(a,s,13,MUTED,false);t.setPadding(0,dp(a,8),0,dp(a,8));body.addView(t);}
  }
  static Modal message(Activity a,String title,String value){Modal d=new Modal(a,title);d.note(value);d.buttons("关闭",d::dismiss,"",()->{});d.show();return d;}
}
