package local.pocketchat;

import android.app.*;
import android.content.*;
import android.os.*;
import android.view.*;
import android.widget.*;
import org.json.*;

/** Native saved-file page available from the launcher, including all independent windows. */
public class DownloadCenterActivity extends Activity {
  LinearLayout box;SavedFileActions actions;
  @Override public void onCreate(Bundle state){super.onCreate(state);actions=new SavedFileActions(this);LinearLayout root=new LinearLayout(this);root.setOrientation(1);root.setFitsSystemWindows(true);root.setBackgroundColor(Ui.PAPER);Button back=new Button(this);back.setText("返回窗口");back.setOnClickListener(v->finish());root.addView(back);ScrollView scroll=new ScrollView(this);box=new LinearLayout(this);box.setOrientation(1);box.setPadding(Ui.dp(this,18),Ui.dp(this,12),Ui.dp(this,18),Ui.dp(this,20));scroll.addView(box);root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));setContentView(root);}
  @Override protected void onResume(){super.onResume();refresh();}
  void refresh(){box.removeAllViews();TextView title=new TextView(this);title.setText("下载文件");title.setTextSize(24);title.setTextColor(Ui.INK);box.addView(title);TextView info=new TextView(this);info.setText("默认位置："+(Build.VERSION.SDK_INT>=29?"Download/元婴期院士/窗口编号":"各窗口的应用内文件目录")+"\n点文件可打开、分享、另存为或查看位置。");info.setTextSize(14);info.setTextColor(Ui.MUTED);info.setPadding(0,Ui.dp(this,12),0,Ui.dp(this,16));box.addView(info);Button refresh=new Button(this);refresh.setText("刷新文件列表");refresh.setOnClickListener(v->refresh());box.addView(refresh);JSONArray rows=DownloadLibrary.get(this).list();for(int i=0;i<rows.length();i++){JSONObject r=rows.optJSONObject(i);Button item=new Button(this);item.setAllCaps(false);item.setGravity(Gravity.START|Gravity.CENTER_VERTICAL);item.setText(r.optString("name")+"\n"+Profiles.display(this,r.optInt("slot"))+" · "+android.text.format.DateFormat.format("MM-dd HH:mm",r.optLong("time"))+"\n"+r.optString("location"));item.setTextSize(14);item.setPadding(Ui.dp(this,12),Ui.dp(this,12),Ui.dp(this,12),Ui.dp(this,12));box.addView(item,new LinearLayout.LayoutParams(-1,-2));item.setOnClickListener(v->actions.show(r));}if(rows.length()==0){TextView empty=new TextView(this);empty.setText("还没有已保存的文件。下载完成后会自动出现在这里。");empty.setTextSize(15);empty.setPadding(0,Ui.dp(this,24),0,0);box.addView(empty);}}
  @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(request==SavedFileActions.EXPORT)actions.result(result,data);}
  @Override protected void onDestroy(){actions.close();super.onDestroy();}
}
