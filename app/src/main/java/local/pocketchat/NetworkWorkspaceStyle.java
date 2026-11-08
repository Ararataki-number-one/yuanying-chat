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

/** Presentation only: network state and configuration stay in NetworkWorkspaceUi. */
final class NetworkWorkspaceStyle {
  private NetworkWorkspaceStyle(){}

  static TextView text(Context context,String value,int size,int color,boolean strong){
    TextView view=ReferenceUi.text(context,value,size,color,strong);readable(view);return view;
  }

  static void readable(TextView view){
    view.setIncludeFontPadding(true);
    if(Build.VERSION.SDK_INT>=28)view.setFallbackLineSpacing(true);
  }

  static Drawable card(Context context,boolean focused){
    return EnvironmentWorkspaceStyle.card(context,false,focused);
  }

  static Button glassAction(Context context,String glyph,String label,Runnable action){
    Button button=ReferenceUi.iconButton(context,glyph,label,action);
    button.setBackground(DesignUi.glass(context,25));GlassMotion.press(button,true);return button;
  }

  static LinearLayout tabs(Context context,int selected,java.util.function.IntConsumer choose){
    LinearLayout bar=DesignUi.row(context);
    bar.setPadding(DesignUi.dp(context,4),0,DesignUi.dp(context,4),0);
    bar.setBackground(DesignUi.surface(context,DesignUi.FIELD,24,Color.TRANSPARENT));
    boolean overflow=context.getResources().getConfiguration().fontScale>=1.4f
        ||context.getResources().getConfiguration().screenWidthDp<360;
    String[] labels={"环境网络","入口","出口"};
    for(int i=0;i<labels.length;i++){
      final int index=i;boolean active=i==selected;
      Button button=ReferenceUi.link(context,labels[i],()->choose.accept(index));
      button.setTextSize(14);button.setTextColor(active?DesignUi.BLUE:DesignUi.MUTED);
      button.setTypeface(Typeface.create("sans-serif-medium",Typeface.NORMAL));
      button.setSelected(active);button.setContentDescription(labels[i]);readable(button);
      button.setSingleLine(false);button.setMaxLines(1);button.setHorizontallyScrolling(false);button.setEllipsize(null);
      button.setMinWidth(0);button.setMinimumWidth(0);
      button.setMinHeight(DesignUi.dp(context,48));button.setMinimumHeight(DesignUi.dp(context,48));
      Drawable face=DesignUi.surface(context,active?DesignUi.CARD:Color.TRANSPARENT,20,Color.TRANSPARENT);
      button.setBackground(new RippleDrawable(ColorStateList.valueOf(0x140067d8),
          new InsetDrawable(face,0,DesignUi.dp(context,4),0,DesignUi.dp(context,4)),null));
      button.setPadding(DesignUi.dp(context,overflow?18:4),DesignUi.dp(context,8),DesignUi.dp(context,overflow?18:4),DesignUi.dp(context,8));
      LinearLayout.LayoutParams params=new LinearLayout.LayoutParams(overflow?-2:0,-2,overflow?0:1);
      if(i>0)params.leftMargin=DesignUi.dp(context,4);bar.addView(button,params);
    }
    if(!overflow)return bar;
    HorizontalScrollView scroll=new HorizontalScrollView(context);scroll.setHorizontalScrollBarEnabled(false);scroll.addView(bar);
    scroll.post(()->scroll.smoothScrollTo(Math.max(0,bar.getChildAt(selected).getLeft()-DesignUi.dp(context,12)),0));
    LinearLayout host=DesignUi.column(context);host.addView(scroll,new LinearLayout.LayoutParams(-1,-2));return host;
  }

  static TextView status(Context context,String label,int color){
    TextView view=text(context,label,11,color,false);view.setGravity(Gravity.CENTER);
    view.setPadding(DesignUi.dp(context,9),DesignUi.dp(context,3),DesignUi.dp(context,9),DesignUi.dp(context,3));
    view.setBackground(DesignUi.surface(context,(color&0x00ffffff)|0x10000000,12,Color.TRANSPARENT));return view;
  }

  static Button smallAction(Context context,String label,Runnable action){
    Button button=ReferenceUi.link(context,label,action);button.setTextSize(13);readable(button);
    button.setBackground(new RippleDrawable(ColorStateList.valueOf(0x140067d8),
        new InsetDrawable(DesignUi.surface(context,ReferenceUi.BLUE_SOFT,16,Color.TRANSPARENT),0,DesignUi.dp(context,6),0,DesignUi.dp(context,6)),null));
    button.setPadding(DesignUi.dp(context,12),DesignUi.dp(context,8),DesignUi.dp(context,12),DesignUi.dp(context,8));return button;
  }

  static Button rowAction(Context context,String label,Runnable action){
    Button button=smallAction(context,label,action);
    button.setBackground(new RippleDrawable(ColorStateList.valueOf(0x140067d8),
        new InsetDrawable(DesignUi.surface(context,ReferenceUi.BLUE_SOFT,16,Color.TRANSPARENT),0,DesignUi.dp(context,8),0,DesignUi.dp(context,8)),null));
    return button;
  }

  static LinearLayout sourceCard(Context context){
    LinearLayout card=DesignUi.column(context);
    card.setPadding(DesignUi.dp(context,16),DesignUi.dp(context,8),DesignUi.dp(context,12),DesignUi.dp(context,14));
    card.setBackground(card(context,false));return card;
  }

  static TextView secondary(Context context,String value){
    TextView view=text(context,value,12,DesignUi.MUTED,false);
    view.setLineSpacing(DesignUi.dp(context,2),1);view.setPadding(0,DesignUi.dp(context,3),DesignUi.dp(context,4),0);return view;
  }

  static void empty(LinearLayout box,String title,String detail){
    Context context=box.getContext();LinearLayout state=DesignUi.row(context);state.setGravity(Gravity.TOP);
    state.setPadding(DesignUi.dp(context,18),DesignUi.dp(context,22),DesignUi.dp(context,18),DesignUi.dp(context,22));
    state.setBackground(card(context,false));
    ImageView symbol=DesignUi.icon(context,"globe",DesignUi.BLUE,44);
    symbol.setPadding(DesignUi.dp(context,11),DesignUi.dp(context,11),DesignUi.dp(context,11),DesignUi.dp(context,11));
    symbol.setBackground(DesignUi.surface(context,ReferenceUi.BLUE_SOFT,14,Color.TRANSPARENT));
    symbol.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);state.addView(symbol);
    LinearLayout copy=DesignUi.column(context);
    copy.addView(text(context,title,16,DesignUi.TEXT,true));
    TextView explanation=secondary(context,detail);explanation.setPadding(0,DesignUi.dp(context,5),0,0);copy.addView(explanation);
    LinearLayout.LayoutParams params=new LinearLayout.LayoutParams(0,-2,1);params.leftMargin=DesignUi.dp(context,14);state.addView(copy,params);
    ReferenceUi.add(box,state);
  }
}
