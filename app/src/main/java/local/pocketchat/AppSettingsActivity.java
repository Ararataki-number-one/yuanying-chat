package local.pocketchat;

import android.os.Build;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.widget.FrameLayout;
import android.widget.LinearLayout;

/** Opening app-wide settings from the manager requires no WebView or account session. */
public class AppSettingsActivity extends ThemedActivity {
  LinearLayout root,box,navigationBar;
  GlassBackdrop backdrop;
  SettingsWorkspaceUi workspace;
  @Override public void onCreate(Bundle state){
    super.onCreate(state);
    if(Build.VERSION.SDK_INT>=30)getWindow().setDecorFitsSystemWindows(false);
    root=DesignUi.screen(this);root.setClipChildren(false);root.setClipToPadding(false);
    FrameLayout stage=new FrameLayout(this);stage.setClipChildren(false);stage.setClipToPadding(false);
    FrameLayout viewport=new FrameLayout(this);stage.addView(viewport,new FrameLayout.LayoutParams(-1,-1));
    backdrop=new GlassBackdrop(this);viewport.addView(backdrop,new FrameLayout.LayoutParams(-1,-1));
    workspace=new SettingsWorkspaceUi(this,backdrop);workspace.show();box=workspace.box;
    navigationBar=DesignUi.workspaceNav(this,AppHub.SETTINGS,page->WorkspaceNavigation.selectPage(this,AppHub.SETTINGS,page),null);
    navigationBar.setBackground(EnvironmentWorkspaceStyle.scrollEdge(this));navigationBar.setClickable(true);navigationBar.setFocusable(false);
    stage.addView(navigationBar,new FrameLayout.LayoutParams(-1,-2,Gravity.BOTTOM));
    backdrop.bindControls(navigationBar);backdrop.setScrollEdge(navigationBar);
    navigationBar.addOnLayoutChangeListener((v,l,t,r,b,ol,ot,or,ob)->workspace.setBottomInset(navigationBar.getHeight()));
    root.addView(stage,new LinearLayout.LayoutParams(-1,0,1));setContentView(root);
    if(Build.VERSION.SDK_INT>=30)root.setFitsSystemWindows(false);
    ReferenceUi.insets(this,root,keyboard->{navigationBar.setVisibility(keyboard?View.GONE:View.VISIBLE);workspace.setBottomInset(keyboard?0:navigationBar.getHeight());});
  }
  void refresh(){if(workspace!=null)workspace.refresh();}
  @Override protected void onResume(){super.onResume();if(backdrop!=null)backdrop.setGlassActive(true);AppUpdates.schedule(this);refresh();}
  @Override protected void onPause(){if(backdrop!=null)backdrop.setGlassActive(false);super.onPause();}
  @Override protected void onDestroy(){if(backdrop!=null)backdrop.setGlassActive(false);super.onDestroy();}
}
