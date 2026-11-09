package local.pocketchat;

import android.app.Activity;
import android.os.Build;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

/** One settings presentation for the independent activity and the live-chat hub. */
final class SettingsWorkspaceUi {
  final Activity activity;
  final FrameLayout host;
  LinearLayout root,box,feedbackHost;
  ScrollView scroll;
  int bottomInset;

  SettingsWorkspaceUi(Activity activity,FrameLayout host){this.activity=activity;this.host=host;}
  int dp(int value){return ReferenceUi.dp(activity,value);}

  void show(){
    if(root==null)layout();
    if(root.getParent()!=host){
      if(root.getParent() instanceof ViewGroup)((ViewGroup)root.getParent()).removeView(root);
      host.removeAllViews();host.addView(root,new FrameLayout.LayoutParams(-1,-1));
    }
    refresh();
  }

  private void layout(){
    root=DesignUi.column(activity);root.setBackgroundColor(ReferenceUi.BG);
    root.setClipChildren(false);root.setClipToPadding(false);
    LinearLayout heading=DesignUi.row(activity);heading.setPadding(dp(22),dp(14),dp(18),dp(14));
    heading.setClipChildren(false);heading.setClipToPadding(false);
    LinearLayout copy=DesignUi.column(activity);
    TextView title=ReferenceUi.workspaceText(activity,"设置",ReferenceUi.PAGE_TITLE_SIZE,DesignUi.TEXT,true);
    title.setContentDescription("应用设置");
    if(Build.VERSION.SDK_INT>=28)title.setAccessibilityHeading(true);
    copy.addView(title);
    TextView subtitle=ReferenceUi.workspaceText(activity,"启动、外观与应用偏好",ReferenceUi.SECONDARY_SIZE,DesignUi.MUTED,false);
    subtitle.setPadding(0,dp(3),dp(6),0);copy.addView(subtitle);
    heading.addView(copy,new LinearLayout.LayoutParams(0,-2,1));
    Button search=ReferenceUi.iconButton(activity,"search","搜索设置与操作",()->ActionSearchUi.show(activity));
    search.setBackground(DesignUi.glass(activity,25));GlassMotion.press(search,true);
    heading.addView(search,new LinearLayout.LayoutParams(dp(50),dp(50)));
    root.addView(heading,new LinearLayout.LayoutParams(-1,-2));
    feedbackHost=DesignUi.column(activity);root.addView(feedbackHost,new LinearLayout.LayoutParams(-1,-2));
    scroll=new ScrollView(activity);scroll.setFillViewport(true);scroll.setClipToPadding(false);
    box=DesignUi.column(activity);box.setPadding(dp(20),dp(4),dp(20),dp(20));
    scroll.addView(box,new ScrollView.LayoutParams(-1,-2));
    root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
  }

  void refresh(){
    if(box==null)return;
    DesignUi.rebuild(box,true,()->DesignSettingsUi.render(activity,box,this::refresh));
    setBottomInset(bottomInset);
    // A hub page can be detached while the app theme changes elsewhere.
    AppAppearance.apply(root);
  }

  void setBottomInset(int height){
    bottomInset=Math.max(0,height);if(box==null)return;
    // The scrolling child owns its safe end so even a short final group can
    // be dragged completely above the floating navigation.
    int bottom=dp(20)+bottomInset;
    if(box.getPaddingBottom()!=bottom)box.setPadding(dp(20),dp(4),dp(20),bottom);
    if(scroll.getPaddingBottom()!=0)scroll.setPadding(scroll.getPaddingLeft(),scroll.getPaddingTop(),scroll.getPaddingRight(),0);
  }
}
