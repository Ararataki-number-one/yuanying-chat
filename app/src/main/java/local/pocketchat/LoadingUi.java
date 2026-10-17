package local.pocketchat;

import android.app.*;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.view.*;
import android.widget.*;

/** Small, real-state progress indicators; never invent a completion percentage. */
final class LoadingUi {
  final MainActivity a;final LinearLayout band,cover;final TextView bandText,title,hint;final ProgressBar wheel;final Button retry,website;
  Dialog taskDialog;boolean taskRunning,coverShown=false;String taskMessage="",lastTitle="";
  LoadingUi(MainActivity activity){a=activity;
    band=new LinearLayout(a);band.setGravity(Gravity.CENTER_VERTICAL);band.setPadding(a.dp(22),a.dp(4),a.dp(22),a.dp(9));band.setVisibility(View.GONE);
    band.addView(spinner(16),new LinearLayout.LayoutParams(a.dp(16),a.dp(16)));bandText=a.label("",12,Ui.MUTED);bandText.setPadding(a.dp(10),0,0,0);band.addView(bandText);band.setOnClickListener(v->{if(taskRunning)showTask();else ReplyState.show(a);});band.setContentDescription("回复状态，点按检查或恢复连接");band.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
    cover=new LinearLayout(a);cover.setOrientation(LinearLayout.VERTICAL);cover.setGravity(Gravity.CENTER);cover.setPadding(a.dp(28),a.dp(16),a.dp(28),a.dp(16));cover.setBackgroundColor(Ui.PAPER);cover.setClickable(true);cover.setVisibility(View.GONE);
    wheel=spinner(32);cover.addView(wheel,new LinearLayout.LayoutParams(a.dp(32),a.dp(32)));title=a.label("",16,Ui.INK);title.setGravity(Gravity.CENTER);title.setPadding(0,a.dp(20),0,a.dp(8));title.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);cover.addView(title);
    hint=a.label("",13,Ui.MUTED);hint.setGravity(Gravity.CENTER);cover.addView(hint);retry=DesignUi.button(a,"重新加载",true,()->a.session.retryCurrent());cover.addView(retry);
    website=DesignUi.button(a,"检查网络",false,()->NetworkStatusUi.show(a));cover.addView(website);
  }
  ProgressBar spinner(int size){ProgressBar p=new ProgressBar(a);p.setIndeterminate(true);p.setIndeterminateTintList(ColorStateList.valueOf(DesignUi.BLUE));return p;}
  void update(){
    ChatSession s=a.session;if(s==null)return;
    boolean visible=s.web.hasVisibleDocument();
    boolean waiting=s.connecting||!s.networkReady||s.web.getUrl()==null||s.web.getUrl().isEmpty();
    // A live document always remains usable, including while the site is
    // loading or rendering a reply. Only an empty surface needs our cover.
    boolean show=!visible&&(waiting||s.navigationFailed);
    if(show){
      a.status.setVisibility(View.GONE);cover.animate().cancel();cover.setAlpha(1);cover.setVisibility(View.VISIBLE);coverShown=true;
      boolean error=s.navigationFailed||!s.connecting&&!s.networkReady;
      String value=error?"网页暂时无法打开":"正在打开网页";if(!value.equals(lastTitle)){title.setText(value);lastTitle=value;}
      hint.setText(error?s.status:"加载完成后自动显示");wheel.setVisibility(error?View.GONE:View.VISIBLE);
      retry.setVisibility(error?View.VISIBLE:View.GONE);website.setVisibility(error?View.VISIBLE:View.GONE);
    }else if(coverShown){coverShown=false;cover.animate().alpha(0).setDuration(180).withEndAction(()->{if(!coverShown)cover.setVisibility(View.GONE);}).start();}
    // Official reply progress is part of the website, never a duplicate band.
    band.setVisibility(View.GONE);
  }
  void task(String message){dismissTask();if(a.destroyed||a.isFinishing())return;taskMessage=message;taskRunning=true;showTask();}
  void showTask(){
    if(!taskRunning||a.destroyed||a.isFinishing()||taskDialog!=null)return;
    LinearLayout box=DesignUi.progress(a,taskMessage,"可收起这个窗口，任务会继续。");
    AlertDialog dialog=new AlertDialog.Builder(a).setTitle("正在处理").setView(box).setNegativeButton("收起",null).create();
    taskDialog=dialog;dialog.setCanceledOnTouchOutside(false);
    dialog.setOnDismissListener(d->{if(taskDialog==dialog)taskDialog=null;if(!a.destroyed){update();if(a.hub!=null&&a.hub.page!=AppHub.CHAT)a.hub.refresh();}});
    dialog.show();update();
  }
  void dismissTask(){taskRunning=false;taskMessage="";Dialog d=taskDialog;taskDialog=null;if(d!=null&&d.isShowing())d.dismiss();if(!a.destroyed)update();}

}
