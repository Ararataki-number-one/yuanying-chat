package local.pocketchat;

import android.content.Context;
import android.graphics.Color;
import android.graphics.drawable.Drawable;
import android.os.Build;
import android.view.Gravity;
import android.view.View;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

/** Presentation only; each settings row retains its existing action and summary. */
final class SettingsWorkspaceStyle {
  private SettingsWorkspaceStyle() {}

  static TextView text(Context context,String value,int size,int color,boolean strong){
    return ReferenceUi.workspaceText(context,value,size,color,strong);
  }

  static void section(LinearLayout parent,String title,String scope){
    Context context=parent.getContext();
    LinearLayout heading=DesignUi.row(context);
    heading.setPadding(DesignUi.dp(context,4),DesignUi.dp(context,parent.getChildCount()==0?6:18),
        DesignUi.dp(context,4),DesignUi.dp(context,8));
    TextView name=text(context,title,ReferenceUi.ACTION_SIZE,DesignUi.MUTED,true);
    name.setPadding(0,0,DesignUi.dp(context,8),0);
    if(Build.VERSION.SDK_INT>=28)name.setAccessibilityHeading(true);
    heading.addView(name,new LinearLayout.LayoutParams(0,-2,1));
    if(!scope.isEmpty()){
      TextView hint=text(context,scope,ReferenceUi.STATUS_SIZE,DesignUi.MUTED,false);
      heading.addView(hint,new LinearLayout.LayoutParams(-2,-2));
    }
    parent.addView(heading,new LinearLayout.LayoutParams(-1,-2));
  }

  static LinearLayout group(Context context){
    LinearLayout group=DesignUi.column(context);
    group.setBackground(EnvironmentWorkspaceStyle.card(context,false,false));
    group.setClipToOutline(true);
    return group;
  }

  static void row(Context context,LinearLayout group,String title,String detail,String glyph,Runnable action){
    if(group.getChildCount()>0){
      View line=new View(context);line.setBackgroundColor(DesignUi.LINE);line.setAlpha(.55f);
      line.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
      LinearLayout.LayoutParams divider=new LinearLayout.LayoutParams(-1,Math.max(1,DesignUi.dp(context,1)/2));
      divider.leftMargin=DesignUi.dp(context,68);divider.rightMargin=DesignUi.dp(context,16);
      group.addView(line,divider);
    }

    LinearLayout row=DesignUi.row(context);row.setGravity(Gravity.CENTER_VERTICAL);
    row.setMinimumHeight(DesignUi.dp(context,68));
    row.setPadding(DesignUi.dp(context,16),DesignUi.dp(context,10),DesignUi.dp(context,16),DesignUi.dp(context,10));

    ImageView icon=DesignUi.icon(context,glyph,DesignUi.BLUE,36);
    Drawable face=DesignUi.surface(context,ReferenceUi.BLUE_SOFT,11,Color.TRANSPARENT);face.setAlpha(150);
    icon.setBackground(face);icon.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
    row.addView(icon);

    LinearLayout labels=DesignUi.column(context);
    labels.setPadding(DesignUi.dp(context,16),0,DesignUi.dp(context,12),0);
    TextView name=text(context,title,ReferenceUi.CARD_TITLE_SIZE,DesignUi.TEXT,true);
    name.setBreakStrategy(android.text.Layout.BREAK_STRATEGY_BALANCED);
    labels.addView(name);
    if(!detail.isEmpty()){
      String display=context.getResources().getConfiguration().fontScale>=1.4f?detail.replace(" · ","\n"):detail;
      TextView summary=text(context,display,ReferenceUi.SECONDARY_SIZE,DesignUi.MUTED,false);
      summary.setContentDescription(detail);
      summary.setBreakStrategy(android.text.Layout.BREAK_STRATEGY_BALANCED);
      summary.setPadding(0,DesignUi.dp(context,2),0,0);labels.addView(summary);
    }
    row.addView(labels,new LinearLayout.LayoutParams(0,-2,1));

    if(action!=null){
      ImageView arrow=new ImageView(context);arrow.setImageDrawable(new Ui.Icon("chevron-right",DesignUi.MUTED));
      arrow.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
      row.addView(arrow,new LinearLayout.LayoutParams(DesignUi.dp(context,12),DesignUi.dp(context,18)));
      row.setBackground(new AppAppearance.GlassRipple(null,DesignUi.surface(context,Color.WHITE,0,Color.TRANSPARENT)));
      row.setClickable(true);row.setFocusable(true);row.setOnClickListener(v->action.run());
    }
    group.addView(row,new LinearLayout.LayoutParams(-1,-2));
  }
}
