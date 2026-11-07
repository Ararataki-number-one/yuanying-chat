package local.pocketchat;

import android.content.*;
import android.view.*;
import android.widget.*;
import java.util.WeakHashMap;

/** Navigation preserves the live chat document while displaying native workspaces. */
final class AppHub {
  static final int CHAT=0, DOWNLOADS=1, ENVIRONMENTS=2, SETTINGS=3, NETWORK=4;
  private static final int[] DESTINATIONS={ENVIRONMENTS,NETWORK,DOWNLOADS};
  final MainActivity a;
  final LinearLayout root,bar,feedbackBar,footer;
  final TextView feedbackText;
  final View chat,divider;
  final FrameLayout workspace;
  final GlassBackdrop panel;
  int page,settingsTab,networkTab,downloadFilter;
  long navigation;
  String rendered="";
  private int markedPage=-1;private boolean markedFocus,markedDark,marked;
  private final WeakHashMap<ScrollView,ScrollPadding> scrollPadding=new WeakHashMap<>();
  final Button[] tabs=new Button[DesignUi.NAV.length];
  final NetworkWorkspaceUi networkWorkspace;
  DesignDownloads.Controller downloadController;
  View downloadScreen;
  final Runnable tick=this::updateTick;

  AppHub(MainActivity a,LinearLayout root,View chat){
    this.a=a;this.root=root;this.chat=chat;
    workspace=new FrameLayout(a);
    panel=new GlassBackdrop(a);panel.setVisibility(View.GONE);
    workspace.addView(panel,new FrameLayout.LayoutParams(-1,-1));
    footer=DesignUi.column(a);
    workspace.addView(footer,new FrameLayout.LayoutParams(-1,-2,Gravity.BOTTOM));
    // Chat keeps its original measured navigation slot. Only native pages put
    // their content behind the same footer; controls never change their parent.
    root.addView(workspace,new LinearLayout.LayoutParams(-1,-2));
    feedbackBar=DesignUi.row(a);feedbackBar.setPadding(a.dp(14),a.dp(4),a.dp(14),a.dp(4));feedbackBar.setVisibility(View.GONE);
    // This opaque notice now overlays page content; its empty area must not
    // activate an obscured row beneath it. The close button keeps its action.
    feedbackBar.setClickable(true);feedbackBar.setFocusable(false);
    feedbackText=DesignUi.text(a,"",13,DesignUi.TEXT);feedbackText.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
    feedbackBar.addView(feedbackText,new LinearLayout.LayoutParams(0,-2,1));
    Button close=DesignUi.button(a,"×",false,()->feedbackBar.setVisibility(View.GONE));close.setTextSize(20);close.setContentDescription("关闭提示");
    LinearLayout.LayoutParams cp=new LinearLayout.LayoutParams(a.dp(48),a.dp(48));cp.leftMargin=a.dp(8);feedbackBar.addView(close,cp);
    footer.addView(feedbackBar,new LinearLayout.LayoutParams(-1,-2));
    divider=new View(a);footer.addView(divider,new LinearLayout.LayoutParams(-1,0));
    bar=ReferenceUi.nav(a,-1,n->{if(n==WorkspaceNavigation.READING)a.setFocusReading(!a.focusActive());else select(DESTINATIONS[n]);},tabs);
    footer.addView(bar,new LinearLayout.LayoutParams(-1,-2));panel.bindControls(bar);
    footer.addOnLayoutChangeListener((v,l,t,r,b,ol,ot,or,ob)->{if(b-t!=ob-ot)updateNativeInsets();});
    networkWorkspace=new NetworkWorkspaceUi(a,panel);mark();
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
    page=target;downloadsVisible(a.active);chat.setVisibility(page==CHAT?View.VISIBLE:View.GONE);if(page!=CHAT)a.designChrome.cancelWebGesture();
    if(a.chatDownloadProgress!=null)a.chatDownloadProgress.update();
    a.status.setVisibility(View.GONE);workspaceMode();
    a.session.foreground(a.active);mark();a.updateReadingLayout();a.handler.removeCallbacks(tick);
    if(page!=CHAT){a.hideKeyboard();refresh();a.handler.postDelayed(tick,2500);}
    else{a.status(a.session.status);a.session.pageMemory.restorePending=true;if(a.session.networkReady&&MainActivity.chatUrl(a.remote.getUrl()))a.session.pageMemory.restore(a.remote.getUrl(),a.session.navigationEpoch);a.session.wakePolling();}
  }
  private void workspaceMode(){
    boolean nativePage=page!=CHAT;
    LinearLayout.LayoutParams layout=(LinearLayout.LayoutParams)workspace.getLayoutParams();
    int height=nativePage?0:ViewGroup.LayoutParams.WRAP_CONTENT;float weight=nativePage?1f:0f;
    if(layout.height!=height||layout.weight!=weight){layout.height=height;layout.weight=weight;workspace.setLayoutParams(layout);}
    panel.setVisibility(nativePage?View.VISIBLE:View.GONE);panel.setGlassActive(nativePage);
  }

  private void updateNativeInsets(){
    if(page!=CHAT)insetScrollViews(panel,Math.max(0,footer.getHeight()));
  }

  private void insetScrollViews(View view,int footerHeight){
    if(view.getVisibility()==View.GONE)return;
    if(view instanceof ScrollView){
      ScrollView scroll=(ScrollView)view;ScrollPadding padding=scrollPadding.get(scroll);
      if(padding==null){padding=new ScrollPadding(scroll.getPaddingBottom());scrollPadding.put(scroll,padding);}
      else if(scroll.getPaddingBottom()!=padding.applied)padding.base=scroll.getPaddingBottom();
      padding.applied=padding.base+footerHeight;
      if(scroll.getPaddingBottom()!=padding.applied)
        scroll.setPadding(scroll.getPaddingLeft(),scroll.getPaddingTop(),scroll.getPaddingRight(),padding.applied);
      if(scroll.getClipToPadding())scroll.setClipToPadding(false);
      // The outer vertical scroller owns the safe end space; nested scrollers
      // must not each add another full navigation height.
      return;
    }
    if(view instanceof ViewGroup){ViewGroup group=(ViewGroup)view;for(int i=0;i<group.getChildCount();i++)insetScrollViews(group.getChildAt(i),footerHeight);}
  }

  private static final class ScrollPadding {
    int base,applied;
    ScrollPadding(int bottom){base=applied=bottom;}
  }
  void keyboard(){a.applyFocusLayout();}
  void mark(){
    boolean focused=page==CHAT&&a.focusActive(),dark=AppAppearance.dark();
    if(marked&&markedPage==page&&markedFocus==focused&&markedDark==dark)return;
    marked=true;markedPage=page;markedFocus=focused;markedDark=dark;
    int selected=-1;for(int i=0;i<DESTINATIONS.length;i++)if(DESTINATIONS[i]==page)selected=i;
    if(focused)selected=WorkspaceNavigation.READING;
    ReferenceUi.markNav(tabs,selected);
    tabs[WorkspaceNavigation.READING].setContentDescription(focused?"退出专注阅读模式":"进入专注阅读模式");
  }
  LinearLayout layout(String title){
    String identity=page+"|"+settingsTab+"|"+networkTab+"|"+downloadFilter+"|"+title;int oldY=0;
    if(identity.equals(rendered)&&panel.getChildCount()>0){ViewGroup old=(ViewGroup)panel.getChildAt(0);if(old.getChildCount()>1&&old.getChildAt(1) instanceof ScrollView)oldY=old.getChildAt(1).getScrollY();}
    rendered=identity;final int restoreY=oldY;LinearLayout screen=DesignUi.screen(a),box=DesignUi.body(a,screen,title,()->select(CHAT));
    panel.removeAllViews();panel.addView(screen,new FrameLayout.LayoutParams(-1,-1));
    updateNativeInsets();
    if(screen.getChildCount()>1&&screen.getChildAt(1) instanceof ScrollView){ScrollView scroll=(ScrollView)screen.getChildAt(1);scroll.post(()->scroll.scrollTo(0,restoreY));}return box;
  }
  void action(LinearLayout box,String label,Runnable run){DesignUi.action(box,label,false,run);}
  void note(LinearLayout box,String text){DesignUi.note(box,text);}
  void feedback(String message,boolean error){
    if(page==CHAT)return;feedbackText.setText(message);feedbackText.setTextColor(error?DesignUi.RED:DesignUi.TEXT);
    feedbackBar.setBackgroundColor(AppAppearance.color(error?0xfffff1f2:0xffedf5ff));feedbackBar.setVisibility(View.VISIBLE);
  }
  void refresh(){if(page==DOWNLOADS)downloads();if(page==SETTINGS)settings();if(page==NETWORK)networkWorkspace.show(networkTab);updateNativeInsets();}
  void downloadsVisible(boolean foreground){if(downloadController!=null)downloadController.setVisible(foreground&&page==DOWNLOADS);}
  void downloads(){
    if(downloadController==null||panel.getChildCount()==0||panel.getChildAt(0)!=downloadScreen){
      LinearLayout box=layout("下载中心");downloadScreen=panel.getChildAt(0);
      downloadController=new DesignDownloads.Controller(a,box,downloadFilter,n->{downloadFilter=n;downloads();},a.downloads.savedActions);
      if(a.downloadUiState!=null){downloadController.restoreState(a.downloadUiState);a.downloadUiState=null;}
    }else downloadController.refresh(downloadFilter);
    downloadsVisible(a.active);
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
