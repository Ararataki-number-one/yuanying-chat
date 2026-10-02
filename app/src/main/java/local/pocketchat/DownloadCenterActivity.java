package local.pocketchat;
import android.app.*;import android.content.*;import android.os.*;import android.widget.*;import org.json.*;

/** Cross-window downloads stay native and do not start a browser until a task is selected. */
public class DownloadCenterActivity extends Activity {
  LinearLayout root,box;SavedFileActions actions;int filter;String last="";final Handler handler=new Handler(Looper.getMainLooper());final Runnable tick=()->{String next=DesignDownloads.rows(this).toString();if(!next.equals(last)){last=next;refresh();}handler.postDelayed(this.tick,2000);};
  @Override public void onCreate(Bundle state){super.onCreate(state);actions=new SavedFileActions(this);root=DesignUi.screen(this);box=DesignUi.body(this,root,"下载中心",()->finish());root.addView(DesignUi.nav(this,2,n->{if(n==2)return;if(n==4){startActivity(new Intent(this,AppSettingsActivity.class));return;}if(n==1){startActivity(new Intent(this,WindowHomeActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_REORDER_TO_FRONT));finish();}else{startActivity(new Intent(this,Profiles.activity(recentSlot())).putExtra("openWindowAction",n==3?"network":n==4?"settings":"chat").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_REORDER_TO_FRONT));}},null));setContentView(root);refresh();}
  int recentSlot(){return AppSettings.recentSlot(this);}
  void refresh(){box.removeAllViews();DesignDownloads.render(this,box,filter,n->{filter=n;refresh();},actions);}
  @Override protected void onResume(){super.onResume();last="";handler.removeCallbacks(tick);handler.post(tick);}
  @Override protected void onPause(){handler.removeCallbacks(tick);super.onPause();}
  @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(request==SavedFileActions.EXPORT)actions.result(result,data);}
  @Override protected void onDestroy(){actions.close();super.onDestroy();}
}
