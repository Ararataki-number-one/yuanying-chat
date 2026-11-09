package local.pocketchat;

import android.app.*;import android.content.*;import android.os.*;import android.view.*;import android.widget.*;

/** Cross-window downloads stay native and preserve the current filter and scroll. */
public class DownloadCenterActivity extends ThemedActivity {
  LinearLayout root,box,navigationBar,workspaceFooter;TextView problem;SavedFileActions actions;DesignDownloads.Controller downloadsView;int filter;
  GlassBackdrop backdrop;
  final Handler handler=new Handler(Looper.getMainLooper());
  final Runnable tick=()->{refresh();handler.postDelayed(this.tick,2000);};
  @Override public void onCreate(Bundle state){
    super.onCreate(state);filter=state==null?0:Math.max(0,Math.min(3,state.getInt("filter")));
    actions=new SavedFileActions(this);
    if(Build.VERSION.SDK_INT>=30)getWindow().setDecorFitsSystemWindows(false);
    root=DesignUi.screen(this);root.setClipChildren(false);root.setClipToPadding(false);
    root.addView(DesignDownloads.header(this),new LinearLayout.LayoutParams(-1,-2));
    problem=DownloadWorkspaceStyle.text(this,"",ReferenceUi.BODY_SIZE,DesignUi.RED,false);problem.setPadding(dp(20),dp(6),dp(20),dp(6));problem.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);problem.setVisibility(View.GONE);root.addView(problem,new LinearLayout.LayoutParams(-1,-2));
    FrameLayout workspace=new FrameLayout(this);workspace.setClipChildren(false);workspace.setClipToPadding(false);
    FrameLayout viewport=new FrameLayout(this);workspace.addView(viewport,new FrameLayout.LayoutParams(-1,-1));
    backdrop=new GlassBackdrop(this);backdrop.setBackground(new DesignUi.Stars(this));viewport.addView(backdrop,new FrameLayout.LayoutParams(-1,-1));
    ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);scroll.setClipToPadding(false);
    box=DesignUi.column(this);box.setPadding(dp(20),dp(4),dp(20),dp(20));scroll.addView(box,new ScrollView.LayoutParams(-1,-2));backdrop.addView(scroll,new FrameLayout.LayoutParams(-1,-1));
    navigationBar=DesignUi.workspaceNav(this,AppHub.DOWNLOADS,page->WorkspaceNavigation.selectPage(this,AppHub.DOWNLOADS,page),null);
    navigationBar.setBackground(EnvironmentWorkspaceStyle.scrollEdge(this));navigationBar.setClickable(true);navigationBar.setFocusable(false);
    workspaceFooter=DesignUi.column(this);workspaceFooter.setClipChildren(false);workspaceFooter.setClipToPadding(false);workspaceFooter.setClickable(true);workspaceFooter.addView(navigationBar,new LinearLayout.LayoutParams(-1,-2));
    workspace.addView(workspaceFooter,new FrameLayout.LayoutParams(-1,-2,Gravity.BOTTOM));backdrop.bindControls(navigationBar);backdrop.setScrollEdge(navigationBar);
    workspaceFooter.addOnLayoutChangeListener((v,l,t,r,b,ol,ot,or,ob)->{if(b-t!=ob-ot)updateWorkspaceInsets();});root.addView(workspace,new LinearLayout.LayoutParams(-1,0,1));
    setContentView(root);if(Build.VERSION.SDK_INT>=30)root.setFitsSystemWindows(false);
    ReferenceUi.insets(this,root,keyboard->{navigationBar.setVisibility(keyboard?View.GONE:View.VISIBLE);updateWorkspaceInsets();});
    downloadsView=new DesignDownloads.Controller(this,box,filter,n->{if(n==filter)return;filter=n;render(false);},actions);downloadsView.restoreState(state);
  }
  int dp(int value){return DesignUi.dp(this,value);}
  void updateWorkspaceInsets(){if(box==null||workspaceFooter==null)return;int bottom=dp(20)+workspaceFooter.getHeight();if(box.getPaddingBottom()!=bottom)box.setPadding(dp(20),dp(4),dp(20),bottom);}
  void attachRefreshPanel(LinearLayout panel){panel.setBackground(DownloadWorkspaceStyle.card(this));LinearLayout.LayoutParams params=new LinearLayout.LayoutParams(-1,-2);params.setMargins(dp(20),dp(6),dp(20),dp(4));workspaceFooter.addView(panel,0,params);}
  void showProblem(String message){problem.setText(message);problem.setVisibility(message.isEmpty()?android.view.View.GONE:android.view.View.VISIBLE);}
  int recentSlot(){return AppSettings.recentSlot(this);}
  void refresh(){render(true);}
  void render(boolean preserveScroll){if(downloadsView!=null)downloadsView.refresh(filter);}
  @Override protected void onSaveInstanceState(Bundle state){super.onSaveInstanceState(state);state.putInt("filter",filter);if(downloadsView!=null)downloadsView.saveState(state);}
  @Override protected void onResume(){super.onResume();if(backdrop!=null)backdrop.setGlassActive(true);if(downloadsView!=null)downloadsView.setVisible(true);handler.removeCallbacks(tick);handler.post(tick);}
  @Override protected void onPause(){if(backdrop!=null)backdrop.setGlassActive(false);if(downloadsView!=null)downloadsView.setVisible(false);handler.removeCallbacks(tick);super.onPause();}
  @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(request==SavedFileActions.EXPORT)actions.result(result,data);}
  @Override protected void onDestroy(){if(downloadsView!=null)downloadsView.setVisible(false);handler.removeCallbacks(tick);if(actions!=null)actions.close();super.onDestroy();}
}
