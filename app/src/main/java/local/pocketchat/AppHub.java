package local.pocketchat;

import android.content.*;
import android.view.*;
import android.widget.*;

/** Navigation preserves the live chat document while displaying native workspaces. */
final class AppHub {
  static final int CHAT=0, DOWNLOADS=1, ENVIRONMENTS=2, SETTINGS=3, NETWORK=4;
  private static final int[] DESTINATIONS={CHAT,ENVIRONMENTS,DOWNLOADS,NETWORK,SETTINGS};
  final MainActivity a;
  final LinearLayout root,bar,feedbackBar;
  final TextView feedbackText;
  final View chat,divider;
  final FrameLayout panel;
  int page,settingsTab,networkTab,downloadFilter;
  long navigation;
  String rendered="";
  final Button[] tabs=new Button[5];
  final NetworkWorkspaceUi networkWorkspace;
  DesignDownloads.Controller downloadController;
  View downloadScreen;
  final Runnable tick=this::updateTick;

  AppHub(MainActivity a,LinearLayout root,View chat){
    this.a=a;this.root=root;this.chat=chat;
    panel=new FrameLayout(a);panel.setVisibility(View.GONE);
    root.addView(panel,new LinearLayout.LayoutParams(-1,0,1));
    feedbackBar=DesignUi.row(a);feedbackBar.setPadding(a.dp(14),a.dp(4),a.dp(14),a.dp(4));feedbackBar.setVisibility(View.GONE);
    feedbackText=DesignUi.text(a,"",13,DesignUi.TEXT);feedbackText.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
    feedbackBar.addView(feedbackText,new LinearLayout.LayoutParams(0,-2,1));
    Button close=DesignUi.button(a,"×",false,()->feedbackBar.setVisibility(View.GONE));close.setTextSize(20);close.setContentDescription("关闭提示");
    LinearLayout.LayoutParams cp=new LinearLayout.LayoutParams(a.dp(48),a.dp(48));cp.leftMargin=a.dp(8);feedbackBar.addView(close,cp);
    root.addView(feedbackBar,new LinearLayout.LayoutParams(-1,-2));
    divider=new View(a);divider.setBackgroundColor(ReferenceUi.LINE);root.addView(divider,new LinearLayout.LayoutParams(-1,a.dp(1)));
    bar=ReferenceUi.nav(a,0,n->select(DESTINATIONS[n]),tabs);root.addView(bar,new LinearLayout.LayoutParams(-1,-2));networkWorkspace=new NetworkWorkspaceUi(a,panel);mark();
  }
  void updateTick(){if(!a.active||a.destroyed||page==CHAT)return;if(page==DOWNLOADS||page==NETWORK)refresh();a.handler.postDelayed(tick,2500);}
  void select(int target){
    if(target<CHAT||target>NETWORK)return;
    if(target==ENVIRONMENTS){a.startActivity(new Intent(a,WindowHomeActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_REORDER_TO_FRONT));return;}
    long token=++navigation;
    if(target==CHAT){a.designChrome.reveal();if(page==CHAT)return;}
    if(page==CHAT&&target!=CHAT)a.session.pageMemory.capture(()->{if(token==navigation)show(target);});else show(target);
  }
  void show(int target){
    if(target!=page||target==CHAT)feedbackBar.setVisibility(View.GONE);
    page=target;chat.setVisibility(page==CHAT?View.VISIBLE:View.GONE);if(page==CHAT)a.toolbar.setVisibility(View.VISIBLE);else{a.designChrome.cancelWebGesture();a.toolbar.setVisibility(View.GONE);}
    a.status.setVisibility(View.GONE);panel.setVisibility(page==CHAT?View.GONE:View.VISIBLE);
    a.session.foreground(a.active);mark();a.updateReadingLayout();a.handler.removeCallbacks(tick);
    if(page!=CHAT){a.hideKeyboard();refresh();a.handler.postDelayed(tick,2500);}
    else{a.status(a.session.status);a.session.pageMemory.restorePending=true;if(a.session.networkReady&&MainActivity.chatUrl(a.remote.getUrl()))a.session.pageMemory.restore(a.remote.getUrl(),a.session.navigationEpoch);a.session.wakePolling();}
  }
  void keyboard(){boolean hide=BrowserReadingPolicy.hideNavigation(page==CHAT,true,a.keyboardVisible);bar.setVisibility(hide?View.GONE:View.VISIBLE);divider.setVisibility(hide?View.GONE:View.VISIBLE);}
  void mark(){int selected=0;for(int i=0;i<DESTINATIONS.length;i++)if(DESTINATIONS[i]==page)selected=i;ReferenceUi.markNav(tabs,selected);}
  LinearLayout layout(String title){
    String identity=page+"|"+settingsTab+"|"+networkTab+"|"+downloadFilter+"|"+title;int oldY=0;
    if(identity.equals(rendered)&&panel.getChildCount()>0){ViewGroup old=(ViewGroup)panel.getChildAt(0);if(old.getChildCount()>1&&old.getChildAt(1) instanceof ScrollView)oldY=old.getChildAt(1).getScrollY();}
    rendered=identity;final int restoreY=oldY;LinearLayout screen=DesignUi.screen(a),box=DesignUi.body(a,screen,title,()->select(CHAT));
    panel.removeAllViews();panel.addView(screen,new FrameLayout.LayoutParams(-1,-1));
    if(screen.getChildCount()>1&&screen.getChildAt(1) instanceof ScrollView){ScrollView scroll=(ScrollView)screen.getChildAt(1);scroll.post(()->scroll.scrollTo(0,restoreY));}return box;
  }
  void action(LinearLayout box,String label,Runnable run){DesignUi.action(box,label,false,run);}
  void note(LinearLayout box,String text){DesignUi.note(box,text);}
  void feedback(String message,boolean error){
    if(page==CHAT)return;feedbackText.setText(message);feedbackText.setTextColor(error?DesignUi.RED:DesignUi.TEXT);
    feedbackBar.setBackgroundColor(AppAppearance.color(error?0xfffff1f2:0xffedf5ff));feedbackBar.setVisibility(View.VISIBLE);
  }
  void refresh(){if(page==DOWNLOADS)downloads();if(page==SETTINGS)settings();if(page==NETWORK)networkWorkspace.show(networkTab);}
  void downloads(){
    if(downloadController==null||panel.getChildCount()==0||panel.getChildAt(0)!=downloadScreen){
      LinearLayout box=layout("下载中心");downloadScreen=panel.getChildAt(0);
      downloadController=new DesignDownloads.Controller(a,box,downloadFilter,n->{downloadFilter=n;downloads();},a.downloads.savedActions);
    }else downloadController.refresh(downloadFilter);
  }
  void settings(){DesignSettingsUi.render(a,layout("应用设置"),settingsTab);}
  void network(){show(NETWORK);}
  void networkFor(int slot){networkTab=0;networkWorkspace.focus(slot);select(NETWORK);}
  void text(String title,String value){DesignUi.message(a,title,value);}
  void about(){
    LinearLayout box=layout("关于元婴期院士");note(box,"Android ChatGPT 网页客户端\nv"+AppVersion.name(a));
    action(box,"功能介绍",()->text("功能介绍","最多 8 个独立环境，支持分组、备注和收藏；官方 ChatGPT 网页、图片与文件上传、下载、固定出口、隐私保护与环境自检。"));
    action(box,"使用帮助",()->text("使用帮助","在环境列表新建或编辑环境。编辑页分为基本信息、网络配置、浏览器与使用偏好。\n\n环境分别登录。网络页显示所属环境；应用设置控制默认入口与系统权限。下载页汇总全部环境文件。\n\n保护等级改变后会重新加载连接。草稿保存不会应用设置。尚未开放的能力列在功能支持范围。"));
    action(box,"第三方许可",()->text("第三方许可","源码和许可随源码包提供。内置 GeckoView、Mihomo、AndroidX 等组件保留原有许可说明。"));
    action(box,"隐私说明",()->text("隐私说明","没有广告或遥测。网络配置与检查基线按环境加密保存。联网自检每次需要授权，结果只覆盖对应路径。"));
    action(box,"复制本机耗时诊断",()->{ChatSession owner=a.session;owner.trace.copyTextAsync(a,GeckoWebView.active(a.remote),text->{
      if(a.isDestroyed()||a.isFinishing()||a.session!=owner||owner.deleted)return;
      ClipboardManager clipboard=(ClipboardManager)a.getSystemService(Context.CLIPBOARD_SERVICE);
      if(clipboard!=null){clipboard.setPrimaryClip(ClipData.newPlainText("耗时诊断",text));a.status("已复制本机耗时诊断");}
    });});
  }
}
