package local.pocketchat;

import android.app.*;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.Build;
import android.view.*;
import android.widget.*;

/** Small, real-state progress indicators; never invent a completion percentage. */
final class LoadingUi {
  final MainActivity a;final LinearLayout band,cover,actions;final TextView bandText,title,hint;final ProgressBar wheel;final ImageView symbol;final Button retry,website;
  final PageLoadingWait wait=new PageLoadingWait();
  Dialog taskDialog;boolean taskRunning,coverShown=false,hintBound,networkFirst;String taskMessage="",lastTitle="",lastHint;
  boolean actionLayoutKnown,actionsHorizontal,actionsLandscape;int actionsAvailable;float actionsFontScale;String actionsRetryLabel="",actionsWebsiteLabel="";
  LoadingUi(MainActivity activity){a=activity;
    band=new LinearLayout(a);band.setGravity(Gravity.CENTER_VERTICAL);band.setPadding(a.dp(22),a.dp(4),a.dp(22),a.dp(9));band.setVisibility(View.GONE);
    band.addView(spinner(16),new LinearLayout.LayoutParams(a.dp(16),a.dp(16)));bandText=a.label("",12,Ui.MUTED);bandText.setPadding(a.dp(10),0,0,0);band.addView(bandText);band.setOnClickListener(v->{if(taskRunning)showTask();else ReplyState.show(a);});band.setContentDescription("回复状态，点按检查或恢复连接");band.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
    cover=new LinearLayout(a);cover.setOrientation(LinearLayout.VERTICAL);cover.setGravity(Gravity.CENTER);cover.setPadding(a.dp(28),a.dp(20),a.dp(28),a.dp(28));cover.setBackgroundColor(ReferenceUi.CHAT_BG);cover.setClickable(true);cover.setVisibility(View.GONE);
    // Short windows scroll the empty-page explanation instead of squeezing buttons.
    LinearLayout content=new LinearLayout(a){
      @Override protected void onMeasure(int widthSpec,int heightSpec){
        int available=MeasureSpec.getMode(widthSpec)==MeasureSpec.UNSPECIFIED?a.dp(288):MeasureSpec.getSize(widthSpec);
        super.onMeasure(MeasureSpec.makeMeasureSpec(Math.min(a.dp(288),available),MeasureSpec.EXACTLY),heightSpec);
      }
    };
    content.setOrientation(LinearLayout.VERTICAL);content.setGravity(Gravity.CENTER);
    ScrollView overflow=new ScrollView(a);overflow.setFillViewport(true);overflow.setVerticalScrollBarEnabled(false);
    overflow.addView(content,new ScrollView.LayoutParams(-2,-2,Gravity.CENTER_HORIZONTAL));cover.addView(overflow,new LinearLayout.LayoutParams(-1,-1));
    FrameLayout emblem=new FrameLayout(a);emblem.setBackground(Ui.shape(a,ReferenceUi.BLUE_SOFT,24));emblem.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
    content.addView(emblem,new LinearLayout.LayoutParams(a.dp(48),a.dp(48)));
    symbol=new ImageView(a);symbol.setImageDrawable(new Ui.Icon("globe",DesignUi.BLUE));symbol.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);symbol.setVisibility(View.GONE);
    emblem.addView(symbol,new FrameLayout.LayoutParams(a.dp(24),a.dp(24),Gravity.CENTER));
    wheel=spinner(24);wheel.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);emblem.addView(wheel,new FrameLayout.LayoutParams(a.dp(24),a.dp(24),Gravity.CENTER));
    title=a.label("",18,Ui.INK);title.setGravity(Gravity.CENTER);title.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
    title.setIncludeFontPadding(true);if(Build.VERSION.SDK_INT>=28)title.setFallbackLineSpacing(true);
    LinearLayout.LayoutParams heading=new LinearLayout.LayoutParams(-1,-2);heading.topMargin=a.dp(14);heading.bottomMargin=a.dp(6);content.addView(title,heading);
    hint=a.label("",13,Ui.MUTED);hint.setGravity(Gravity.CENTER);hint.setLineSpacing(a.dp(4),1f);hint.setIncludeFontPadding(true);
    if(Build.VERSION.SDK_INT>=28)hint.setFallbackLineSpacing(true);
    content.addView(hint,new LinearLayout.LayoutParams(-1,-2));
    retry=DesignUi.button(a,"重新加载",true,()->a.session.retryCurrent());retry.setPadding(a.dp(16),a.dp(8),a.dp(16),a.dp(8));
    website=ReferenceUi.link(a,"检查网络",()->NetworkStatusUi.show(a));website.setTextSize(13);website.setPadding(a.dp(16),a.dp(8),a.dp(16),a.dp(8));
    for(Button action:new Button[]{retry,website}){
      action.setSingleLine(false);action.setEllipsize(null);action.setTextSize(14);action.setIncludeFontPadding(true);
      if(Build.VERSION.SDK_INT>=28)action.setFallbackLineSpacing(true);
      action.setMinHeight(a.dp(48));action.setMinimumHeight(a.dp(48));action.setPadding(a.dp(20),a.dp(9),a.dp(20),a.dp(9));
    }
    actions=new LinearLayout(a){
      @Override protected void onMeasure(int widthSpec,int heightSpec){
        int available=MeasureSpec.getMode(widthSpec)==MeasureSpec.UNSPECIFIED?a.dp(288):MeasureSpec.getSize(widthSpec);
        // Keep one compact primary action, but allow enlarged labels to use the
        // full content width and wrap vertically instead of being truncated.
        int desired=actionsHorizontal?2*Math.max(DesignUi.actionWidth(retry,48),DesignUi.actionWidth(website,48))+a.dp(12):Math.max(a.dp(168),Math.max(DesignUi.actionWidth(retry,48),DesignUi.actionWidth(website,48)));
        super.onMeasure(MeasureSpec.makeMeasureSpec(Math.min(desired,available),MeasureSpec.EXACTLY),heightSpec);
      }
    };
    actions.setOrientation(LinearLayout.VERTICAL);actions.setGravity(Gravity.CENTER_HORIZONTAL);
    LinearLayout.LayoutParams actionBlock=new LinearLayout.LayoutParams(-2,-2);actionBlock.topMargin=a.dp(16);content.addView(actions,actionBlock);
    arrangeActions(false);
    cover.addOnLayoutChangeListener((v,l,t,r,b,ol,ot,or,ob)->layoutActions());
    TextView guidance=a.label("点按顶部输入网址，长按切换环境",11,Ui.MUTED);guidance.setGravity(Gravity.CENTER);guidance.setIncludeFontPadding(true);
    if(Build.VERSION.SDK_INT>=28)guidance.setFallbackLineSpacing(true);
    LinearLayout.LayoutParams guide=new LinearLayout.LayoutParams(-1,-2);guide.topMargin=a.dp(24);content.addView(guidance,guide);
    title.setTypeface(Typeface.create("sans-serif-medium",Typeface.NORMAL));
  }
  private void arrangeActions(boolean checkNetworkFirst){
    if(actions.getChildCount()>0&&networkFirst==checkNetworkFirst){layoutActions();return;}
    networkFirst=checkNetworkFirst;actions.removeAllViews();
    Button primary=checkNetworkFirst?website:retry,secondary=checkNetworkFirst?retry:website;
    primary.setTextColor(Color.WHITE);primary.setBackground(Ui.ripple(a,0xff1268ff,24));
    secondary.setTextColor(DesignUi.BLUE);secondary.setBackground(Ui.ripple(a,Color.TRANSPARENT,24));
    // Keep the same native buttons and callbacks when changing their visual priority.
    primary.setPadding(a.dp(20),a.dp(9),a.dp(20),a.dp(9));secondary.setPadding(a.dp(20),a.dp(9),a.dp(20),a.dp(9));
    actions.addView(primary,new LinearLayout.LayoutParams(-1,-2));
    LinearLayout.LayoutParams follow=new LinearLayout.LayoutParams(-2,-2);follow.topMargin=a.dp(4);actions.addView(secondary,follow);
    actionLayoutKnown=false;layoutActions();
  }
  void layoutActions(){
    boolean landscape=a.getResources().getConfiguration().orientation==android.content.res.Configuration.ORIENTATION_LANDSCAPE;
    int available=cover.getWidth()>0?cover.getWidth()-cover.getPaddingLeft()-cover.getPaddingRight():a.getResources().getDisplayMetrics().widthPixels-a.dp(56);
    available=Math.max(0,Math.min(a.dp(288),available));
    float fontScale=a.getResources().getConfiguration().fontScale;
    String retryLabel=retry.getText().toString(),websiteLabel=website.getText().toString();
    if(actionLayoutKnown&&actionsLandscape==landscape&&actionsAvailable==available&&actionsFontScale==fontScale&&actionsRetryLabel.equals(retryLabel)&&actionsWebsiteLabel.equals(websiteLabel))return;
    boolean horizontal=landscape&&2*Math.max(DesignUi.actionWidth(retry,48),DesignUi.actionWidth(website,48))+a.dp(12)<=available;
    boolean layoutChanged=!actionLayoutKnown||horizontal!=actionsHorizontal;
    boolean wasHorizontal=actionsHorizontal;
    actionLayoutKnown=true;actionsLandscape=landscape;actionsAvailable=available;actionsFontScale=fontScale;actionsRetryLabel=retryLabel;actionsWebsiteLabel=websiteLabel;actionsHorizontal=horizontal;
    if(!layoutChanged||!horizontal&&!wasHorizontal)return;
    actions.setOrientation(horizontal?LinearLayout.HORIZONTAL:LinearLayout.VERTICAL);
    int index=0;for(Button action:new Button[]{networkFirst?website:retry,networkFirst?retry:website}){
      LinearLayout.LayoutParams p=(LinearLayout.LayoutParams)action.getLayoutParams();p.width=horizontal?0:index==0?-1:-2;p.weight=horizontal?1:0;p.topMargin=horizontal?a.dp(12):index==0?0:a.dp(4);p.leftMargin=horizontal&&index>0?a.dp(12):0;action.setLayoutParams(p);index++;
    }
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
    if(s.web.resourceDeferred){lastTitle="稍后打开当前环境";text(title,lastTitle);hint(ResourcePressureController.DEFERRED_MESSAGE);loadingSymbol(false);text(retry,"重试打开");arrangeActions(false);MainActivity.chromeVisibility(retry,true);MainActivity.chromeVisibility(website,false);return;}
    text(retry,"重新加载");
    {
      boolean error=s.navigationFailed||!s.connecting&&!s.networkReady;
      // Match both the stage and current production error. The stage may outlive
      // a later browser-policy failure, whose diagnostic must remain visible.
      boolean waitingVpn=error&&"等待手机 VPN".equals(s.connectionStage)
        &&"手机 VPN 未连接，已暂停网页联网；连接 VPN 后，点击“重新加载”。".equals(s.status);
      String value=waitingVpn?"等待 VPN 连接":error?"网页暂时无法打开":slow?"连接时间较长":s.connecting||!s.networkReady?"正在连接当前线路":"正在加载网页";text(title,value);lastTitle=value;
      String detail=s.status;
      if(error&&"已应用保存的网页显示和保护设置".equals(detail)){
        if(s.navigationFailed&&!android.text.TextUtils.isEmpty(s.pageError))detail=s.pageError;
        else if(!s.networkReady&&!android.text.TextUtils.isEmpty(s.networkIssue))detail=s.networkIssue;
        else detail="网页尚未打开。请重新加载或检查当前环境网络。";
      }
      String stage=s.connectionStage==null||s.connectionStage.isEmpty()?"等待当前环境连接":s.connectionStage;
      hint(waitingVpn?"网页联网已暂停。\n连接手机 VPN 后，再重新加载。":error?detail:stage+(slow?"\n可检查当前线路；登录和草稿会保留，不会自动重发消息。":"\n网页可见后自动显示"));loadingSymbol(!(error||slow));
      arrangeActions(waitingVpn||!error&&slow);
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
