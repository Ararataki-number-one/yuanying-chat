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

/** Presentation tokens for the two reference pages; other workspaces keep their styles. */
final class ReferenceUi {
  static final int BG=0xfff4f7fb,CHAT_BG=0xfff9fbfe,WHITE=0xffffffff,TEXT=0xff172033,
    MUTED=0xff7a8799,LINE=0xffe0e7f0,BLUE=0xff2468f2,BLUE_SOFT=0xffedf4ff,
    GREEN=0xff16a36a,ORANGE=0xffa96c0a,RED=0xffdf5555;
  static int dp(Context c,int n){return Ui.dp(c,n);}
  static TextView text(Context c,String value,int size,int color,boolean strong){TextView v=DesignUi.text(c,value,size,color);if(strong)v.setTypeface(Typeface.create("sans-serif-medium",Typeface.NORMAL));return v;}
  static void single(TextView v){v.setSingleLine(true);v.setEllipsize(TextUtils.TruncateAt.END);}
  static Drawable surface(Context c,int color,int radius,int border){return DesignUi.surface(c,color,radius,border);}
  static Button button(Context c,String label,boolean primary,Runnable run){Button b=DesignUi.button(c,label,primary,run);b.setTextColor(primary?WHITE:TEXT);b.setTextSize(13);b.setBackground(new RippleDrawable(ColorStateList.valueOf(primary?0x33ffffff:0x182468f2),surface(c,primary?BLUE:WHITE,13,primary?BLUE:LINE),null));return b;}
  static Button small(Context c,String label,boolean primary,Runnable run){Button b=button(c,label,false,run);b.setTextColor(primary?BLUE:TEXT);b.setPadding(dp(c,13),0,dp(c,13),0);b.setBackground(new RippleDrawable(ColorStateList.valueOf(0x182468f2),new InsetDrawable(surface(c,primary?BLUE_SOFT:WHITE,10,primary?0xffcfe0ff:LINE),0,dp(c,6),0,dp(c,6)),null));b.setPadding(dp(c,13),0,dp(c,13),0);return b;}
  static Button link(Context c,String label,Runnable run){Button b=button(c,label,false,run);b.setTextColor(BLUE);b.setPadding(dp(c,4),0,dp(c,4),0);b.setBackground(Ui.ripple(c,Color.TRANSPARENT,9));return b;}
  static Button more(Context c,Runnable run){Button b=link(c,"⋮",run);b.setTextSize(25);b.setTextColor(MUTED);b.setContentDescription("更多");return b;}
  static LinearLayout card(Context c){LinearLayout box=DesignUi.column(c);box.setPadding(dp(c,14),dp(c,13),dp(c,14),dp(c,10));box.setBackground(surface(c,WHITE,16,LINE));return box;}
  static void add(LinearLayout box,View card){LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);p.bottomMargin=dp(box.getContext(),10);box.addView(card,p);}
  static TextView secondary(Context c,String value){TextView t=text(c,value,12,MUTED,false);single(t);t.setPadding(0,dp(c,5),0,0);return t;}
  static LinearLayout tabs(Context c,String[] labels,int selected,java.util.function.IntConsumer click){LinearLayout bar=DesignUi.row(c);for(int i=0;i<labels.length;i++){final int n=i;Button b=button(c,labels[i],i==selected,()->click.accept(n));b.setSingleLine(true);b.setPadding(dp(c,4),0,dp(c,4),0);b.setTypeface(Typeface.create("sans-serif-medium",0));b.setBackground(new RippleDrawable(ColorStateList.valueOf(0x182468f2),new InsetDrawable(surface(c,i==selected?BLUE:WHITE,12,i==selected?BLUE:LINE),0,dp(c,4),0,dp(c,4)),null));LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(0,dp(c,48),1);if(i>0)p.leftMargin=dp(c,8);bar.addView(b,p);}return bar;}
  static LinearLayout nav(Activity a,int selected,java.util.function.IntConsumer action,Button[] buttons){LinearLayout bar=DesignUi.row(a);bar.setPadding(dp(a,6),0,dp(a,6),0);bar.setBackgroundColor(WHITE);for(int i=0;i<5;i++){final int n=i;Button b=link(a,DesignUi.NAV[i],()->action.accept(n));b.setTextSize(11);b.setPadding(0,dp(a,7),0,dp(a,7));Ui.Icon icon=new Ui.Icon(DesignUi.GLYPHS[i],MUTED);icon.setBounds(0,0,dp(a,21),dp(a,21));b.setCompoundDrawables(null,icon,null,null);b.setCompoundDrawablePadding(dp(a,4));bar.addView(b,new LinearLayout.LayoutParams(0,dp(a,68),1));buttons[i]=b;}markNav(buttons,selected);return bar;}
  static void markNav(Button[] tabs,int selected){for(int i=0;i<tabs.length;i++){Button b=tabs[i];b.setSelected(i==selected);b.setTextColor(i==selected?BLUE:MUTED);b.setBackground(Ui.ripple(b.getContext(),WHITE,0));Drawable icon=b.getCompoundDrawables()[1];if(icon instanceof Ui.Icon)((Ui.Icon)icon).color=i==selected?BLUE:MUTED;b.invalidate();}}
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

  static final class Modal extends Dialog {
    final Activity a;final LinearLayout root,body,footer,head;final ScrollView scroll;Runnable cancel=this::dismiss;
    Modal(Activity a,String title){super(a);this.a=a;root=DesignUi.column(a);root.setPadding(dp(a,18),dp(a,12),dp(a,18),dp(a,18));root.setBackground(surface(a,WHITE,22,WHITE));head=DesignUi.row(a);TextView heading=text(a,title,20,TEXT,true);single(heading);head.addView(heading,new LinearLayout.LayoutParams(0,dp(a,48),1));Button close=link(a,"×",()->cancel.run());close.setContentDescription("关闭"+title);close.setTextSize(24);close.setTextColor(MUTED);head.addView(close,new LinearLayout.LayoutParams(dp(a,48),dp(a,48)));root.addView(head);body=DesignUi.column(a);scroll=new ScrollView(a);scroll.setFillViewport(false);scroll.addView(body);root.addView(scroll,new LinearLayout.LayoutParams(-1,-2));footer=DesignUi.row(a);footer.setPadding(0,dp(a,12),0,0);root.addView(footer);setContentView(root);setCanceledOnTouchOutside(false);getWindow().setBackgroundDrawable(new ColorDrawable(Color.TRANSPARENT));getWindow().setDimAmount(.38f);getWindow().addFlags(WindowManager.LayoutParams.FLAG_DIM_BEHIND);getWindow().setGravity(Gravity.CENTER);getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE|WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_HIDDEN);if(Build.VERSION.SDK_INT>=30)root.setOnApplyWindowInsetsListener((v,in)->{v.post(this::resize);return in;});}
    void buttons(String secondary,Runnable back,String primary,Runnable save){footer.removeAllViews();if(!secondary.isEmpty())footer.addView(button(a,secondary,false,back),new LinearLayout.LayoutParams(0,dp(a,48),1));if(!primary.isEmpty()){Button b=button(a,primary,true,save);LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(0,dp(a,48),1.5f);if(footer.getChildCount()>0)p.leftMargin=dp(a,8);footer.addView(b,p);}}
    Button primary(){return footer.getChildCount()==0?null:(Button)footer.getChildAt(footer.getChildCount()-1);}
    void resize(){if(!isShowing())return;Rect visible=new Rect();getWindow().getDecorView().getWindowVisibleDisplayFrame(visible);int width=Math.min(dp(a,420),Math.max(dp(a,200),visible.width()-dp(a,36))),available=visible.height();if(available<=0)available=a.getResources().getDisplayMetrics().heightPixels;int max=Math.max(dp(a,160),(int)(available*.82)),inner=width-dp(a,36);body.measure(View.MeasureSpec.makeMeasureSpec(inner,View.MeasureSpec.EXACTLY),View.MeasureSpec.makeMeasureSpec(0,View.MeasureSpec.UNSPECIFIED));footer.measure(View.MeasureSpec.makeMeasureSpec(inner,View.MeasureSpec.EXACTLY),View.MeasureSpec.makeMeasureSpec(0,View.MeasureSpec.UNSPECIFIED));int cap=Math.max(dp(a,48),max-dp(a,78)-footer.getMeasuredHeight());scroll.getLayoutParams().height=Math.min(cap,body.getMeasuredHeight());scroll.requestLayout();getWindow().setLayout(width,-2);}
    @Override public void show(){super.show();resize();}
    @Override public void onBackPressed(){cancel.run();}
    void note(String s){TextView t=text(a,s,12,MUTED,false);t.setPadding(0,dp(a,8),0,dp(a,8));body.addView(t);}
  }
  static Modal message(Activity a,String title,String value){Modal d=new Modal(a,title);d.note(value);d.buttons("关闭",d::dismiss,"",()->{});d.show();return d;}
}
