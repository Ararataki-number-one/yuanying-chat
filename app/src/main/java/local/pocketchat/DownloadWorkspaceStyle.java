package local.pocketchat;

import android.content.Context;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.InsetDrawable;
import android.graphics.drawable.RippleDrawable;
import android.os.Build;
import android.view.Gravity;
import android.view.View;
import android.widget.*;
import java.util.Locale;

/** Quiet native surfaces shared by the download list and its empty state. */
final class DownloadWorkspaceStyle {
  private DownloadWorkspaceStyle(){}

  static TextView text(Context context,String value,int size,int color,boolean strong){
    TextView view=ReferenceUi.text(context,value,size,color,strong);
    readable(view);return view;
  }

  static void readable(TextView view){
    view.setIncludeFontPadding(true);
    if(Build.VERSION.SDK_INT>=28)view.setFallbackLineSpacing(true);
  }

  static Drawable card(Context context){
    return EnvironmentWorkspaceStyle.card(context,false,false);
  }

  static LinearLayout tabs(Context context,int selected,java.util.function.IntConsumer choose){
    LinearLayout bar=DesignUi.row(context);
    boolean overflow=context.getResources().getConfiguration().fontScale>=1.4f
        ||context.getResources().getConfiguration().screenWidthDp<360;
    String[] labels={"全部","进行中","已完成","失败"};
    for(int i=0;i<labels.length;i++){
      final int index=i;boolean active=i==selected;
      Button tab=ReferenceUi.link(context,labels[i],()->choose.accept(index));
      tab.setTextSize(13);tab.setTextColor(active?DesignUi.BLUE:DesignUi.MUTED);
      tab.setTypeface(Typeface.create("sans-serif-medium",Typeface.NORMAL));
      tab.setSelected(active);tab.setContentDescription(labels[i]);readable(tab);
      tab.setSingleLine(false);tab.setMaxLines(1);tab.setHorizontallyScrolling(false);tab.setEllipsize(null);
      tab.setMinWidth(0);tab.setMinimumWidth(0);tab.setMinHeight(DesignUi.dp(context,48));tab.setMinimumHeight(DesignUi.dp(context,48));
      Drawable face=DesignUi.surface(context,active?ReferenceUi.BLUE_SOFT:Color.TRANSPARENT,20,Color.TRANSPARENT);
      tab.setBackground(new RippleDrawable(ColorStateList.valueOf(AppAppearance.dark()?0x227faeff:0x140067d8),
          new InsetDrawable(face,0,DesignUi.dp(context,4),0,DesignUi.dp(context,4)),null));
      tab.setPadding(DesignUi.dp(context,overflow?16:4),DesignUi.dp(context,8),DesignUi.dp(context,overflow?16:4),DesignUi.dp(context,8));
      LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(overflow?-2:0,-2,overflow?0:1);
      if(i>0)p.leftMargin=DesignUi.dp(context,4);bar.addView(tab,p);
    }
    if(!overflow)return bar;
    HorizontalScrollView scroll=new HorizontalScrollView(context);scroll.setHorizontalScrollBarEnabled(false);scroll.addView(bar);
    scroll.post(()->scroll.smoothScrollTo(Math.max(0,bar.getChildAt(selected).getLeft()-DesignUi.dp(context,12)),0));
    LinearLayout host=DesignUi.column(context);host.addView(scroll,new LinearLayout.LayoutParams(-1,-2));return host;
  }

  static void search(EditText input){
    Context context=input.getContext();readable(input);input.setTextSize(14);
    input.setMinHeight(DesignUi.dp(context,48));input.setMinimumHeight(DesignUi.dp(context,48));
    input.setBackground(DesignUi.surface(context,DesignUi.CARD,18,Color.TRANSPARENT));
    input.setOnFocusChangeListener((view,focused)->view.setBackground(DesignUi.surface(context,DesignUi.CARD,18,focused?DesignUi.BLUE:Color.TRANSPARENT)));
    input.setPadding(DesignUi.dp(context,14),DesignUi.dp(context,11),DesignUi.dp(context,input.length()==0?14:52),DesignUi.dp(context,11));
  }

  /** Decorative type marks use the effective name already tracked by row binding. */
  static String savedGlyph(String name){
    String lower=name.toLowerCase(Locale.ROOT);int dot=lower.lastIndexOf('.');
    String extension=dot<0?"":lower.substring(dot+1);
    switch(extension){case "png":case "jpg":case "jpeg":case "gif":case "webp":case "heic":case "heif":case "bmp":case "svg":case "avif":return "image";default:return "file";}
  }

  static int savedColor(String name){
    if("image".equals(savedGlyph(name)))return DesignUi.GREEN;
    return name.toLowerCase(Locale.ROOT).endsWith(".pdf")?ReferenceUi.ORANGE:DesignUi.CYAN;
  }

  static void empty(LinearLayout box,String title,String detail,String action,Runnable run){
    Context context=box.getContext();
    LinearLayout state=DesignUi.column(context);state.setGravity(Gravity.CENTER_HORIZONTAL);
    state.setPadding(DesignUi.dp(context,24),DesignUi.dp(context,42),DesignUi.dp(context,24),DesignUi.dp(context,36));
    ImageView symbol=DesignUi.icon(context,"tray",DesignUi.BLUE,56);
    symbol.setPadding(DesignUi.dp(context,15),DesignUi.dp(context,15),DesignUi.dp(context,15),DesignUi.dp(context,15));
    symbol.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);state.addView(symbol);
    TextView heading=text(context,title,18,DesignUi.TEXT,true);heading.setGravity(Gravity.CENTER);
    heading.setPadding(0,DesignUi.dp(context,18),0,0);state.addView(heading);
    TextView explanation=text(context,detail,13,DesignUi.MUTED,false);explanation.setGravity(Gravity.CENTER);
    explanation.setPadding(0,DesignUi.dp(context,7),0,0);state.addView(explanation);
    if(run!=null){Button button=ReferenceUi.link(context,action,run);readable(button);LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-2,-2);p.topMargin=DesignUi.dp(context,14);state.addView(button,p);}
    box.addView(state,new LinearLayout.LayoutParams(-1,-2));
  }
}
