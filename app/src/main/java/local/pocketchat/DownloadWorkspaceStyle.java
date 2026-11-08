package local.pocketchat;

import android.content.Context;
import android.graphics.drawable.Drawable;
import android.os.Build;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.*;

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
    LinearLayout tabs=DesignUi.tabs(context,new String[]{"全部","进行中","已完成","失败"},selected,choose);
    readableChildren(tabs);return tabs;
  }

  private static void readableChildren(View view){
    if(view instanceof TextView)readable((TextView)view);
    if(view instanceof ViewGroup){ViewGroup group=(ViewGroup)view;for(int i=0;i<group.getChildCount();i++)readableChildren(group.getChildAt(i));}
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
