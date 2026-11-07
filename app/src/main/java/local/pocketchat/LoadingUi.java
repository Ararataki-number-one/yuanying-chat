package local.pocketchat;

import android.app.*;
import android.content.res.ColorStateList;
import android.view.*;
import android.widget.*;

/** Small, real-state progress indicators; never invent a completion percentage. */
final class LoadingUi {
  final MainActivity a;final LinearLayout band,cover,actions;final TextView bandText,title,hint;final ProgressBar wheel;final ImageView symbol;final Button retry,website;
  final PageLoadingWait wait=new PageLoadingWait();
  Dialog taskDialog;boolean taskRunning,coverShown=false,hintBound;String taskMessage="",lastTitle="",lastHint;
  LoadingUi(MainActivity activity){a=activity;
    band=new LinearLayout(a);band.setGravity(Gravity.CENTER_VERTICAL);band.setPadding(a.dp(22),a.dp(4),a.dp(22),a.dp(9));band.setVisibility(View.GONE);
    band.addView(spinner(16),new LinearLayout.LayoutParams(a.dp(16),a.dp(16)));bandText=a.label("",12,Ui.MUTED);bandText.setPadding(a.dp(10),0,0,0);band.addView(bandText);band.setOnClickListener(v->{if(taskRunning)showTask();else ReplyState.show(a);});band.setContentDescription("回复状态，点按检查或恢复连接");band.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
    cover=new LinearLayout(a);cover.setOrientation(LinearLayout.VERTICAL);cover.setGravity(Gravity.CENTER);cover.setPadding(a.dp(24),a.dp(24),a.dp(24),a.dp(24));cover.setBackgroundColor(ReferenceUi.CHAT_BG);cover.setClickable(true);cover.setVisibility(View.GONE);
    // Short windows scroll the empty-page explanation instead of squeezing buttons.
    LinearLayout content=new LinearLayout(a){
      @Override protected void onMeasure(int widthSpec,int heightSpec){
        int available=MeasureSpec.getMode(widthSpec)==MeasureSpec.UNSPECIFIED?a.dp(300):MeasureSpec.getSize(widthSpec);
        super.onMeasure(MeasureSpec.makeMeasureSpec(Math.min(a.dp(300),available),MeasureSpec.EXACTLY),heightSpec);
      }
    };
    content.setOrientation(LinearLayout.VERTICAL);content.setGravity(Gravity.CENTER);
    ScrollView overflow=new ScrollView(a);overflow.setFillViewport(true);overflow.setVerticalScrollBarEnabled(false);
    overflow.addView(content,new ScrollView.LayoutParams(-2,-2,Gravity.CENTER_HORIZONTAL));cover.addView(overflow,new LinearLayout.LayoutParams(-1,-1));
    FrameLayout emblem=new FrameLayout(a);emblem.setBackground(Ui.shape(a,ReferenceUi.BLUE_SOFT,30));emblem.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
    content.addView(emblem,new LinearLayout.LayoutParams(a.dp(60),a.dp(60)));
    symbol=new ImageView(a);symbol.setImageDrawable(new Ui.Icon("globe",DesignUi.BLUE));symbol.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);symbol.setVisibility(View.GONE);
    emblem.addView(symbol,new FrameLayout.LayoutParams(a.dp(28),a.dp(28),Gravity.CENTER));
    wheel=spinner(28);wheel.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);emblem.addView(wheel,new FrameLayout.LayoutParams(a.dp(28),a.dp(28),Gravity.CENTER));
    title=a.label("",20,Ui.INK);title.setGravity(Gravity.CENTER);title.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
    LinearLayout.LayoutParams heading=new LinearLayout.LayoutParams(-1,-2);heading.topMargin=a.dp(18);heading.bottomMargin=a.dp(8);content.addView(title,heading);
    hint=a.label("",13,Ui.MUTED);hint.setGravity(Gravity.CENTER);hint.setLineSpacing(a.dp(3),1.1f);content.addView(hint,new LinearLayout.LayoutParams(-1,-2));
    retry=DesignUi.button(a,"重新加载",true,()->a.session.retryCurrent());retry.setPadding(a.dp(16),a.dp(8),a.dp(16),a.dp(8));
    website=ReferenceUi.link(a,"检查网络",()->NetworkStatusUi.show(a));website.setTextSize(13);website.setPadding(a.dp(16),a.dp(8),a.dp(16),a.dp(8));
    for(Button action:new Button[]{retry,website}){action.setSingleLine(false);action.setEllipsize(null);}
    actions=new LinearLayout(a){
      @Override protected void onMeasure(int widthSpec,int heightSpec){
        int available=MeasureSpec.getMode(widthSpec)==MeasureSpec.UNSPECIFIED?a.dp(300):MeasureSpec.getSize(widthSpec);
        // Keep one compact primary action, but allow enlarged labels to use the
        // full content width and wrap vertically instead of being truncated.
        int desired=Math.max(a.dp(200),Math.max(DesignUi.actionWidth(retry,48),DesignUi.actionWidth(website,48)));
        super.onMeasure(MeasureSpec.makeMeasureSpec(Math.min(desired,available),MeasureSpec.EXACTLY),heightSpec);
      }
    };
    actions.setOrientation(LinearLayout.VERTICAL);actions.setGravity(Gravity.CENTER_HORIZONTAL);
    LinearLayout.LayoutParams actionBlock=new LinearLayout.LayoutParams(-2,-2);actionBlock.topMargin=a.dp(18);content.addView(actions,actionBlock);
    actions.addView(retry,new LinearLayout.LayoutParams(-1,-2));
    LinearLayout.LayoutParams secondary=new LinearLayout.LayoutParams(-2,-2);secondary.topMargin=a.dp(2);actions.addView(website,secondary);
    title.setTypeface(android.graphics.Typeface.create("sans-serif-medium",android.graphics.Typeface.NORMAL));
  }
  private void loadingSymbol(boolean spinning){MainActivity.chromeVisibility(wheel,spinning);MainActivity.chromeVisibility(symbol,!spinning);}
  ProgressBar spinner(int size){ProgressBar p=new ProgressBar(a);p.setIndeterminate(true);p.setIndeterminateTintList(ColorStateList.valueOf(DesignUi.BLUE));return p;}
  static void text(TextView view,String value){if(!android.text.TextUtils.equals(view.getText(),value))view.setText(value);}
  void hint(String value){if(hintBound&&android.text.TextUtils.equals(lastHint,value))return;hintBound=true;lastHint=value;DesignUi.readable(hint,value,"重新加载");}
  void showCover(){
    if(coverShown)return;
    cover.animate().cancel();if(cover.getAlpha()!=1f)cover.setAlpha(1f);MainActivity.chromeVisibility(cover,true);coverShown=true;
  }
  void hideCover(){
    if(!coverShown)return;coverShown=false;
    if(android.animation.ValueAnimator.areAnimatorsEnabled())cover.animate().alpha(0).setDuration(180).withEndAction(()->{if(!coverShown)MainActivity.chromeVisibility(cover,false);}).start();
    else{if(cover.getAlpha()!=0f)cover.setAlpha(0);MainActivity.chromeVisibility(cover,false);}
  }
  void update(){
    ChatSession s=a.session;if(s==null)return;
    a.applyFocusLayout();
    boolean visible=s.web.hasVisibleDocument();
    boolean slow=wait.update(!visible&&!s.web.resourceDeferred,android.os.SystemClock.elapsedRealtime());
    MainActivity.chromeVisibility(band,false);
    // A live document always remains usable, including while the site is
    // loading or rendering a reply. Only an empty surface needs our cover.
    if(visible){hideCover();return;}
    MainActivity.chromeVisibility(a.status,false);showCover();
    if(s.web.resourceDeferred){lastTitle="稍后打开当前环境";text(title,lastTitle);hint(ResourcePressureController.DEFERRED_MESSAGE);loadingSymbol(false);text(retry,"重试打开");MainActivity.chromeVisibility(retry,true);MainActivity.chromeVisibility(website,false);return;}
    text(retry,"重新加载");
    {
      boolean error=s.navigationFailed||!s.connecting&&!s.networkReady;
      String value=error?"网页暂时无法打开":slow?"连接时间较长":s.connecting||!s.networkReady?"正在连接当前线路":"正在加载网页";text(title,value);lastTitle=value;
      String detail=s.status;
      if(error&&"已应用保存的网页显示和保护设置".equals(detail)){
        if(s.navigationFailed&&!android.text.TextUtils.isEmpty(s.pageError))detail=s.pageError;
        else if(!s.networkReady&&!android.text.TextUtils.isEmpty(s.networkIssue))detail=s.networkIssue;
        else detail="网页尚未打开。请重新加载或检查当前环境网络。";
      }
      String stage=s.connectionStage==null||s.connectionStage.isEmpty()?"等待当前环境连接":s.connectionStage;
      hint(error?detail:stage+(slow?"\n可检查当前线路；登录和草稿会保留，不会自动重发消息。":"\n网页可见后自动显示"));loadingSymbol(!(error||slow));
      MainActivity.chromeVisibility(retry,error);MainActivity.chromeVisibility(website,error||slow);
    }
  }
  void task(String message){dismissTask();if(a.destroyed||a.isFinishing())return;taskMessage=message;taskRunning=true;showTask();}
  void showTask(){
    if(!taskRunning||a.destroyed||a.isFinishing()||taskDialog!=null)return;
    LinearLayout box=DesignUi.progress(a,taskMessage,"可收起这个窗口，任务会继续。");
    AlertDialog dialog=AppAppearance.dialog(a).setTitle("正在处理").setView(box).setNegativeButton("收起",null).create();
    taskDialog=dialog;dialog.setCanceledOnTouchOutside(false);
    dialog.setOnDismissListener(d->{if(taskDialog==dialog)taskDialog=null;if(!a.destroyed){update();if(a.hub!=null&&a.hub.page!=AppHub.CHAT)a.hub.refresh();}});
    dialog.show();update();
  }
  void dismissTask(){taskRunning=false;taskMessage="";Dialog d=taskDialog;taskDialog=null;if(d!=null&&d.isShowing())d.dismiss();if(!a.destroyed)update();}

}
