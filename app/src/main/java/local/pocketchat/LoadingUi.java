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
    cover=new LinearLayout(a);cover.setOrientation(1);cover.setGravity(Gravity.CENTER);cover.setPadding(a.dp(28),a.dp(16),a.dp(28),a.dp(16));cover.setBackgroundColor(Ui.PAPER);cover.setClickable(true);cover.setVisibility(View.GONE);
    wheel=spinner(32);cover.addView(wheel,new LinearLayout.LayoutParams(a.dp(32),a.dp(32)));title=a.label("",16,Ui.INK);title.setGravity(Gravity.CENTER);title.setPadding(0,a.dp(20),0,a.dp(8));title.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);cover.addView(title);
    hint=a.label("",13,Ui.MUTED);hint.setGravity(Gravity.CENTER);cover.addView(hint);retry=DesignUi.button(a,"重新加载",true,()->a.session.retryCurrent());cover.addView(retry);
    website=DesignUi.button(a,"查看原网页",false,()->a.showPage(true));cover.addView(website);
  }
  ProgressBar spinner(int size){ProgressBar p=new ProgressBar(a);p.setIndeterminate(true);p.setIndeterminateTintList(ColorStateList.valueOf(DesignUi.BLUE));return p;}
  void update(){ChatSession s=a.session;if(s==null)return;boolean failed=s.navigationFailed;boolean raw=GeckoWebView.active(s.web)&&a.pageMode;boolean waiting=raw&&(s.connecting||!s.networkReady||s.web.getUrl()==null||s.web.getUrl().isEmpty());boolean show=raw?waiting||failed:(s.navigating||failed)&&!s.showingCache;
    if(show){if(!failed)a.status.setVisibility(View.GONE);cover.animate().cancel();cover.setAlpha(1);cover.setVisibility(View.VISIBLE);coverShown=true;String value=failed?"暂时没有加载完成":waiting?"正在准备网页":s.navigationLabel;if(!value.equals(lastTitle)){title.setText(value);lastTitle=value;}boolean attention=failed||raw&&!s.connecting&&!s.networkReady;hint.setText(attention?s.status:(System.currentTimeMillis()-s.navigationStarted>8000?"网络有些慢，仍在加载…":"加载完成后会自动显示"));wheel.setVisibility(attention?View.GONE:View.VISIBLE);retry.setVisibility(attention?View.VISIBLE:View.GONE);website.setText(raw?"选择浏览器内核":"查看原网页");website.setOnClickListener(v->{if(raw)BrowserEngineUi.show(a);else a.showPage(true);});website.setVisibility(attention?View.VISIBLE:View.GONE);
    }else if(coverShown){coverShown=false;cover.animate().alpha(0).setDuration(180).withEndAction(()->{if(!coverShown)cover.setVisibility(View.GONE);}).start();}
    String message=s.status;boolean error=message.matches(".*(失败|错误|超时|请|待确认|未完成|解除等待|已到).*"),working=!error&&(s.submitting||s.pending!=null||message.startsWith("正在")||message.startsWith("准备连接"));
    boolean small=(working||taskRunning)&&!show&&taskDialog==null;
    bandText.setText(taskRunning?taskMessage+" · 点按查看":(s.submitting?"正在发送…":message)+(s.pending==null?"":" · "+ReplyState.elapsedSeconds(s.pending)+"秒 · 查看状态"));
    band.setContentDescription(taskRunning?"任务仍在进行，点按查看":"回复状态，点按检查或恢复连接");
    band.setVisibility(small?View.VISIBLE:View.GONE);if(small)a.status.setVisibility(View.GONE);
  }
  void task(String message){dismissTask();if(a.destroyed||a.isFinishing())return;taskMessage=message;taskRunning=true;showTask();}
  void showTask(){
    if(!taskRunning||a.destroyed||a.isFinishing()||taskDialog!=null)return;
    LinearLayout box=DesignUi.progress(a,taskMessage,"收起或返回后任务继续，完成时会提示结果。");
    AlertDialog dialog=new AlertDialog.Builder(a).setTitle("正在处理").setView(box).setNegativeButton("收起",null).create();
    taskDialog=dialog;dialog.setCanceledOnTouchOutside(false);
    dialog.setOnDismissListener(d->{if(taskDialog==dialog)taskDialog=null;if(!a.destroyed){update();if(a.hub!=null&&a.hub.page!=AppHub.CHAT)a.hub.refresh();}});
    dialog.show();update();
  }
  void dismissTask(){taskRunning=false;taskMessage="";Dialog d=taskDialog;taskDialog=null;if(d!=null&&d.isShowing())d.dismiss();if(!a.destroyed)update();}

}
