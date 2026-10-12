package local.pocketchat;

import android.app.*;import android.content.*;import android.os.*;import android.widget.*;

/** Cross-window downloads stay native and preserve the current filter and scroll. */
public class DownloadCenterActivity extends Activity {
  LinearLayout root,box;TextView problem;SavedFileActions actions;int filter;String last="";
  final Handler handler=new Handler(Looper.getMainLooper());
  final Runnable tick=()->{String next=DesignDownloads.rows(this).toString();if(!next.equals(last)){last=next;refresh();}handler.postDelayed(this.tick,2000);};
  @Override public void onCreate(Bundle state){
    super.onCreate(state);filter=state==null?0:Math.max(0,Math.min(3,state.getInt("filter")));
    actions=new SavedFileActions(this);root=DesignUi.screen(this);box=DesignUi.body(this,root,"下载中心",()->finish());
    problem=DesignUi.text(this,"",13,DesignUi.RED);problem.setPadding(DesignUi.dp(this,14),DesignUi.dp(this,6),DesignUi.dp(this,14),DesignUi.dp(this,6));problem.setAccessibilityLiveRegion(android.view.View.ACCESSIBILITY_LIVE_REGION_POLITE);problem.setVisibility(android.view.View.GONE);root.addView(problem,1,new LinearLayout.LayoutParams(-1,-2));
    root.addView(DesignUi.nav(this,2,n->WorkspaceNavigation.select(this,2,n),null));setContentView(root);refresh();
  }
  void showProblem(String message){problem.setText(message);problem.setVisibility(message.isEmpty()?android.view.View.GONE:android.view.View.VISIBLE);}
  int recentSlot(){return AppSettings.recentSlot(this);}
  void refresh(){render(true);}
  void render(boolean preserveScroll){DesignUi.rebuild(box,preserveScroll,()->DesignDownloads.render(this,box,filter,n->{if(n==filter)return;filter=n;render(false);},actions));}
  @Override protected void onSaveInstanceState(Bundle state){super.onSaveInstanceState(state);state.putInt("filter",filter);}
  @Override protected void onResume(){super.onResume();last="";handler.removeCallbacks(tick);handler.post(tick);}
  @Override protected void onPause(){handler.removeCallbacks(tick);super.onPause();}
  @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(request==SavedFileActions.EXPORT)actions.result(result,data);}
  @Override protected void onDestroy(){handler.removeCallbacks(tick);if(actions!=null)actions.close();super.onDestroy();}
}
