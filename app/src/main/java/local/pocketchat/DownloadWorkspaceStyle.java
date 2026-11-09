package local.pocketchat;

import android.content.Context;
import android.graphics.Color;
import android.graphics.drawable.Drawable;
import android.view.Gravity;
import android.view.View;
import android.widget.*;
import java.util.Locale;

/** Quiet native surfaces shared by the download list and its empty state. */
final class DownloadWorkspaceStyle {
  private DownloadWorkspaceStyle(){}

  static TextView text(Context context,String value,int size,int color,boolean strong){
    return ReferenceUi.workspaceText(context,value,size,color,strong);
  }

  static void readable(TextView view){
    ReferenceUi.readable(view);
  }

  static Drawable card(Context context){
    return EnvironmentWorkspaceStyle.card(context,false,false);
  }

  static LinearLayout tabs(Context context,int selected,java.util.function.IntConsumer choose){
    return ReferenceUi.workspaceTabs(context,new String[]{"全部","进行中","已完成","失败"},selected,choose);
  }

  static void search(EditText input){
    Context context=input.getContext();readable(input);input.setTextSize(ReferenceUi.BODY_SIZE);
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
    TextView heading=text(context,title,ReferenceUi.EMPTY_TITLE_SIZE,DesignUi.TEXT,true);heading.setGravity(Gravity.CENTER);
    heading.setPadding(0,DesignUi.dp(context,18),0,0);state.addView(heading);
    TextView explanation=text(context,detail,ReferenceUi.SECONDARY_SIZE,DesignUi.MUTED,false);explanation.setGravity(Gravity.CENTER);
    explanation.setPadding(0,DesignUi.dp(context,7),0,0);state.addView(explanation);
    if(run!=null){Button button=ReferenceUi.link(context,action,run);button.setTextSize(ReferenceUi.ACTION_SIZE);readable(button);LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-2,-2);p.topMargin=DesignUi.dp(context,14);state.addView(button,p);}
    box.addView(state,new LinearLayout.LayoutParams(-1,-2));
  }
}
