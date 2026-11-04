package local.pocketchat;

import android.app.*;
import android.content.*;
import android.content.pm.PackageInfo;
import android.graphics.Bitmap;
import android.net.Uri;
import android.net.http.SslError;
import android.os.*;
import android.text.*;
import android.view.*;
import android.view.inputmethod.*;
import android.webkit.*;
import android.widget.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.json.*;

/** General Chromium browsing stays separate from the ChatGPT automation bridge. */
@SuppressWarnings("deprecation")
public class BrowserActivity extends ThemedActivity {
  static final int MAX_TABS=8;
  final ArrayList<Tab> tabs=new ArrayList<>();
  LinearLayout root,findBar;FrameLayout content;EditText address,findText;TextView caption,notice,findCount;Button back,forward,tabCount,reload;
  ProgressBar progress;ChromiumRuntime runtime;BrowserFiles files;BrowserLibrary library;BrowserPermissions permissions;
  final ExecutorService cookieWorker=Executors.newSingleThreadExecutor(r->new Thread(r,"browser-cookie-save"));final AtomicBoolean flushingCookies=new AtomicBoolean();
  Tab selected;View customView;WebChromeClient.CustomViewCallback customCallback;boolean foreground,destroyed,createdSurface;
  static final class Tab {
    WebView web;Bundle saved;String url,title="";boolean loading,desktop,failed;long generation;
    Tab(String url){this.url=url;}
  }
  public static class Profile1 extends BrowserActivity {}
  public static class Profile2 extends BrowserActivity {}
  public static class Profile3 extends BrowserActivity {}
  public static class Profile4 extends BrowserActivity {}
  public static class Profile5 extends BrowserActivity {}
  public static class Profile6 extends BrowserActivity {}
  public static class Profile7 extends BrowserActivity {}
  static Class<?> activity(int slot){return new Class<?>[]{BrowserActivity.class,Profile1.class,Profile2.class,Profile3.class,Profile4.class,Profile5.class,Profile6.class,Profile7.class}[slot];}
  static void open(Activity host,String url){host.startActivity(new Intent(host,activity(Profiles.slot(host))).putExtra("url",url).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_REORDER_TO_FRONT));}
  @Override protected void attachBaseContext(Context base){super.attachBaseContext(new ProfileContext(base,Profiles.processSlot()));}
  @Override protected void onCreate(Bundle state){
    super.onCreate(state);
    if(!ProfileCatalog.get(this).available(Profiles.slot(this))){finish();return;}
    library=new BrowserLibrary(this);
    buildUi();runtime=new ChromiumRuntime(this,this::routeChanged);files=new BrowserFiles(this,this::message,runtime);permissions=new BrowserPermissions(this,this::web,this::message);
    String initial=intentAddress(getIntent());
    if(state!=null&&state.getStringArrayList("browser.urls")!=null){
      ArrayList<String> urls=state.getStringArrayList("browser.urls");int at=state.getInt("browser.selected");
      for(String url:urls)if(tabs.size()<MAX_TABS&&BrowserAddressPolicy.allowed(url))tabs.add(new Tab(url));
      if(!tabs.isEmpty())select(tabs.get(Math.max(0,Math.min(at,tabs.size()-1))));
    }
    if(tabs.isEmpty())newTab(initial==null?BrowserPreferences.home(this):initial);
    if(tabs.isEmpty())newTab(BrowserAddressPolicy.home());
    runtime.start();
  }
  static String intentAddress(Intent intent){return Intent.ACTION_VIEW.equals(intent.getAction())&&intent.getData()!=null?intent.getData().toString():intent.getStringExtra("url");}
  @Override protected void onNewIntent(Intent intent){super.onNewIntent(intent);setIntent(intent);String url=intentAddress(intent);if(url!=null){for(Tab tab:tabs)if(url.equals(tab.url)){select(tab);return;}newTab(url);}}
  int dp(int value){return ReferenceUi.dp(this,value);}
  void buildUi(){
    root=DesignUi.column(this);root.setBackgroundColor(ReferenceUi.CHAT_BG);
    LinearLayout location=DesignUi.row(this);location.setPadding(dp(8),dp(4),dp(8),dp(4));
    Button engine=ReferenceUi.iconButton(this,"globe","当前内核：Chromium；查看内核信息",this::engineInfo);location.addView(engine,new LinearLayout.LayoutParams(dp(48),dp(48)));
    address=new EditText(this);address.setSingleLine(true);address.setTextSize(15);address.setSelectAllOnFocus(true);address.setHint("搜索或输入网址");address.setContentDescription("网址或搜索词");address.setInputType(android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_VARIATION_URI);address.setImeOptions(EditorInfo.IME_ACTION_GO);
    address.setBackground(ReferenceUi.surface(this,ReferenceUi.WHITE,14,ReferenceUi.LINE));address.setPadding(dp(12),0,dp(8),0);location.addView(address,new LinearLayout.LayoutParams(0,dp(48),1));
    address.setOnEditorActionListener((view,action,event)->{if(action==EditorInfo.IME_ACTION_GO||event!=null&&event.getKeyCode()==KeyEvent.KEYCODE_ENTER&&event.getAction()==KeyEvent.ACTION_DOWN){go(address.getText().toString());return true;}return false;});
    reload=ReferenceUi.iconButton(this,"refresh","刷新网页",this::reloadOrStop);location.addView(reload,new LinearLayout.LayoutParams(dp(48),dp(48)));root.addView(location);
    progress=new ProgressBar(this,null,android.R.attr.progressBarStyleHorizontal);progress.setMax(100);progress.setVisibility(View.INVISIBLE);root.addView(progress,new LinearLayout.LayoutParams(-1,dp(2)));
    caption=ReferenceUi.text(this,"Chromium · 默认首页 ChatGPT",12,ReferenceUi.MUTED,false);caption.setSingleLine(true);caption.setEllipsize(TextUtils.TruncateAt.END);caption.setPadding(dp(12),dp(3),dp(12),dp(3));root.addView(caption);
    notice=ReferenceUi.text(this,"正在准备浏览器网络…",13,ReferenceUi.TEXT,false);notice.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);notice.setPadding(dp(12),dp(8),dp(12),dp(8));notice.setOnClickListener(v->{if(runtime!=null)runtime.refresh();});root.addView(notice);
    findBar=DesignUi.row(this);findText=new EditText(this);findText.setSingleLine(true);findText.setHint("在网页中查找");findText.setContentDescription("页内查找文字");findBar.addView(findText,new LinearLayout.LayoutParams(0,dp(48),1));
    findCount=ReferenceUi.text(this,"",12,ReferenceUi.MUTED,false);findBar.addView(findCount);
    findBar.addView(ReferenceUi.iconButton(this,"back","上一个匹配",()->{if(web()!=null)web().findNext(false);}),new LinearLayout.LayoutParams(dp(48),dp(48)));
    findBar.addView(ReferenceUi.iconButton(this,"chevron-right","下一个匹配",()->{if(web()!=null)web().findNext(true);}),new LinearLayout.LayoutParams(dp(48),dp(48)));
    findBar.addView(ReferenceUi.iconButton(this,"close","关闭页内查找",this::closeFind),new LinearLayout.LayoutParams(dp(48),dp(48)));findBar.setVisibility(View.GONE);root.addView(findBar);
    findText.addTextChangedListener(new TextWatcher(){public void beforeTextChanged(CharSequence s,int a,int c,int n){}public void onTextChanged(CharSequence s,int a,int b,int c){if(web()!=null)web().findAllAsync(s.toString());}public void afterTextChanged(Editable e){}});
    content=new FrameLayout(this);root.addView(content,new LinearLayout.LayoutParams(-1,0,1));
    LinearLayout nav=DesignUi.row(this);nav.setBackgroundColor(ReferenceUi.WHITE);
    back=ReferenceUi.iconButton(this,"back","后退",()->history(-1));forward=ReferenceUi.iconButton(this,"chevron-right","前进",()->history(1));
    nav.addView(back,new LinearLayout.LayoutParams(0,dp(52),1));nav.addView(forward,new LinearLayout.LayoutParams(0,dp(52),1));
    nav.addView(ReferenceUi.iconButton(this,"globe","打开主页",()->go(BrowserPreferences.home(this))),new LinearLayout.LayoutParams(0,dp(52),1));
    tabCount=ReferenceUi.link(this,"1",this::showTabs);tabCount.setContentDescription("标签页");nav.addView(tabCount,new LinearLayout.LayoutParams(0,dp(52),1));
    nav.addView(ReferenceUi.iconButton(this,"more","浏览器菜单",this::menu),new LinearLayout.LayoutParams(0,dp(52),1));root.addView(nav);
    setContentView(root);ReferenceUi.insets(this,root);
  }
  WebView web(){return selected==null?null:selected.web;}
  boolean live(Tab tab,WebView source){return !destroyed&&tabs.contains(tab)&&tab.web==source;}
  void message(String text){if(destroyed)return;notice.setText(text==null?"":text);notice.setVisibility(text==null||text.isEmpty()?View.GONE:View.VISIBLE);}
  void routeChanged(boolean ready,String reason){
    if(destroyed)return;message(ready?"":reason);
    if(!ready){hideCustomView();for(Tab tab:tabs)retire(tab);content.removeAllViews();}
    else if(selected!=null)showSelected();
    updateChrome();
  }
  void newTab(String input){
    if(tabs.size()>=MAX_TABS){message("最多打开 8 个标签页，请先关闭一个标签页");showTabs();return;}
    try{Tab tab=new Tab(BrowserAddressPolicy.normalizeInput(input));tabs.add(tab);select(tab);}catch(IllegalArgumentException invalid){message(invalid.getMessage());}
  }
  void select(Tab tab){
    if(selected==tab)return;hideCustomView();closeFind();if(selected!=null&&selected.web!=null){files.cancelFor(selected.web);permissions.onNavigation(selected.web);selected.web.onPause();}
    selected=tab;content.removeAllViews();showSelected();address.clearFocus();updateChrome();
  }
  void showSelected(){
    if(selected==null||runtime==null||!runtime.allowed())return;
    Tab tab=selected;if(tab.web==null)createSurface(tab);
    WebView view=tab.web;if(view==null)return;
    if(view.getParent()!=content){content.removeAllViews();if(view.getParent() instanceof android.view.ViewGroup)((android.view.ViewGroup)view.getParent()).removeView(view);content.addView(view,new FrameLayout.LayoutParams(-1,-1));}
    if(foreground)view.onResume();else view.onPause();
  }
  void createSurface(Tab tab){
    WebView view;
    try{view=new WebView(this);}catch(RuntimeException failure){message("系统 Chromium 组件无法启动，请更新 Android System WebView 或 Chrome 后重试");return;}
    tab.web=view;createdSurface=true;
    WebSettings settings=view.getSettings();settings.setBlockNetworkLoads(true);settings.setJavaScriptEnabled(true);settings.setDomStorageEnabled(true);settings.setAllowFileAccess(false);settings.setAllowContentAccess(false);settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);settings.setMediaPlaybackRequiresUserGesture(true);settings.setSupportMultipleWindows(true);settings.setJavaScriptCanOpenWindowsAutomatically(false);settings.setBuiltInZoomControls(true);settings.setDisplayZoomControls(false);settings.setLoadWithOverviewMode(true);settings.setUseWideViewPort(true);settings.setOffscreenPreRaster(false);settings.setSafeBrowsingEnabled(true);
    CookieManager.getInstance().setAcceptThirdPartyCookies(view,false);applyDesktop(tab);
    view.setWebViewClient(new WebViewClient(){
      @Override public boolean shouldOverrideUrlLoading(WebView source,WebResourceRequest request){
        if(!live(tab,source))return true;String url=request.getUrl().toString();
        if(BrowserAddressPolicy.allowed(url))return !runtime.allowed();
        if(request.isForMainFrame()&&request.hasGesture())external(url);return true;
      }
      @Override public WebResourceResponse shouldInterceptRequest(WebView source,WebResourceRequest request){
        String scheme=request.getUrl().getScheme();
        if(!runtime.allowed()||("http".equals(scheme)||"https".equals(scheme))&&!BrowserAddressPolicy.allowed(request.getUrl().toString()))return new WebResourceResponse("text/plain","UTF-8",503,"Network unavailable",Collections.emptyMap(),new java.io.ByteArrayInputStream(new byte[0]));return null;
      }
      @Override public void onPageStarted(WebView source,String url,Bitmap icon){
        if(!live(tab,source))return;files.cancelFor(source);permissions.onNavigation(source);tab.generation++;tab.loading=true;tab.failed=false;if(BrowserAddressPolicy.allowed(url))tab.url=url;
        if(!runtime.allowed()||!BrowserAddressPolicy.allowed(url)&&!"about:blank".equals(url)){source.stopLoading();tab.loading=false;tab.failed=true;if(tab==selected){message("已阻止不支持的网页地址");updateChrome();}return;}if(tab==selected){message("");updateChrome();}
      }
      @Override public void onPageFinished(WebView source,String url){
        if(!live(tab,source)||!url.equals(source.getUrl()))return;tab.loading=false;
        if(!tab.failed&&BrowserAddressPolicy.allowed(url)){tab.url=url;library.remember("history",url,tab.title,200);}
        if(tab==selected)updateChrome();
      }
      @Override public void doUpdateVisitedHistory(WebView source,String url,boolean reload){if(live(tab,source)&&BrowserAddressPolicy.allowed(url)){tab.url=url;if(tab==selected)updateChrome();}}
      @Override public void onReceivedError(WebView source,WebResourceRequest request,WebResourceError error){if(live(tab,source)&&request.isForMainFrame()&&request.getUrl().toString().equals(source.getUrl())){tab.loading=false;tab.failed=true;if(tab==selected){message("网页暂时无法打开，检查网络后可刷新重试");updateChrome();}}}
      @Override public void onReceivedSslError(WebView source,SslErrorHandler handler,SslError error){handler.cancel();if(live(tab,source)){tab.failed=true;if(tab==selected)message("网站证书无法验证，已停止连接");}}
      @Override public boolean onRenderProcessGone(WebView source,RenderProcessGoneDetail detail){if(live(tab,source)){retire(tab);if(tab==selected){content.removeAllViews();message("网页进程已退出，点击刷新恢复这个标签页");updateChrome();}}return true;}
    });
    view.setWebChromeClient(new WebChromeClient(){
      @Override public void onProgressChanged(WebView source,int value){if(live(tab,source)&&tab==selected){progress.setProgress(value);progress.setVisibility(value<100?View.VISIBLE:View.INVISIBLE);}}
      @Override public void onReceivedTitle(WebView source,String title){if(live(tab,source)){tab.title=BrowserLibrary.title(title,tab.url);if(tab==selected)updateChrome();}}
      @Override public boolean onShowFileChooser(WebView source,ValueCallback<Uri[]> callback,FileChooserParams params){if(!live(tab,source)||selected!=tab||!foreground||!runtime.allowed()){callback.onReceiveValue(null);return true;}return files.choose(source,callback,params);}
      @Override public boolean onCreateWindow(WebView source,boolean dialog,boolean gesture,Message result){
        if(!live(tab,source)||!gesture||!runtime.allowed()||tabs.size()>=MAX_TABS)return false;
        Tab popup=new Tab(BrowserPreferences.home(BrowserActivity.this));tabs.add(popup);createSurface(popup);if(popup.web==null){tabs.remove(popup);return false;}
        WebView.WebViewTransport transport=(WebView.WebViewTransport)result.obj;transport.setWebView(popup.web);result.sendToTarget();select(popup);return true;
      }
      @Override public void onCloseWindow(WebView source){if(live(tab,source))closeTab(tab);}
      @Override public void onPermissionRequest(PermissionRequest request){if(live(tab,view)&&tab==selected&&runtime.allowed())permissions.request(view,request);else request.deny();}
      @Override public void onPermissionRequestCanceled(PermissionRequest request){permissions.cancel(request);}
      @Override public void onGeolocationPermissionsShowPrompt(String origin,GeolocationPermissions.Callback callback){if(live(tab,view)&&tab==selected&&runtime.allowed())permissions.geolocation(view,origin,callback);else callback.invoke(origin,false,false);}
      @Override public void onGeolocationPermissionsHidePrompt(){permissions.hideGeolocation();}
      @Override public void onShowCustomView(View custom,CustomViewCallback callback){if(live(tab,view)&&tab==selected)showCustomView(custom,callback);else callback.onCustomViewHidden();}
      @Override public void onHideCustomView(){hideCustomView();}
    });
    view.setFindListener((index,count,done)->{if(live(tab,view)&&tab==selected)findCount.setText(count==0?"0/0":(index+1)+"/"+count);});
    view.setDownloadListener((url,ua,disposition,mime,bytes)->{if(live(tab,view)&&runtime.allowed())files.download(view,url,ua,disposition,mime,bytes);});
    view.setOnLongClickListener(v->{WebView.HitTestResult hit=view.getHitTestResult();String target=hit==null?null:hit.getExtra();if(target!=null&&BrowserAddressPolicy.allowed(target)){linkMenu(target);return true;}return false;});
    settings.setBlockNetworkLoads(!runtime.allowed());
    if(tab.saved!=null){Bundle saved=tab.saved;tab.saved=null;if(view.restoreState(saved)!=null)return;}
    // Popups are supplied their target by WebViewTransport, so do not load a placeholder.
    if(!tabs.contains(tab)||selected==tab)view.loadUrl(tab.url);
  }
  void applyDesktop(Tab tab){if(tab.web==null)return;WebSettings s=tab.web.getSettings();String ua=WebSettings.getDefaultUserAgent(this);int version=ua.indexOf("Chrome/");String chromium=version<0?"":ua.substring(version).split(" ")[0];s.setUserAgentString(tab.desktop?"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "+chromium+" Safari/537.36":null);s.setUseWideViewPort(true);}
  void go(String input){
    try{String url=BrowserAddressPolicy.normalizeInput(input);hideKeyboard();closeFind();
      if(selected==null){newTab(url);return;}selected.url=url;selected.saved=null;
      if(web()!=null&&runtime.allowed()){files.cancelFor(web());permissions.onNavigation(web());web().loadUrl(url);}else{if(runtime!=null)runtime.refresh();showSelected();}updateChrome();
    }catch(IllegalArgumentException invalid){message(invalid.getMessage());}
  }
  void history(int direction){if(web()==null||!runtime.allowed())return;closeFind();files.cancelFor(web());permissions.onNavigation(web());if(direction<0&&web().canGoBack())web().goBack();else if(direction>0&&web().canGoForward())web().goForward();}
  void reloadOrStop(){if(selected==null)return;if(selected.loading&&web()!=null){web().stopLoading();selected.loading=false;updateChrome();return;}if(runtime==null)return;if(runtime.allowed()){if(web()==null)showSelected();else{files.cancelFor(web());permissions.onNavigation(web());web().reload();}}else runtime.refresh();}
  void updateChrome(){
    if(selected==null)return;if(!address.hasFocus()&&!selected.url.contentEquals(address.getText()))address.setText(selected.url);
    String safety=selected.url.startsWith("https://")?"HTTPS":"HTTP · 不安全";caption.setText("Chromium · "+safety+" · "+(selected.title.isEmpty()?Profiles.display(this,Profiles.slot(this)):selected.title));
    back.setEnabled(web()!=null&&web().canGoBack());forward.setEnabled(web()!=null&&web().canGoForward());tabCount.setText(String.valueOf(tabs.size()));tabCount.setContentDescription(tabs.size()+" 个标签页，点击管理");reload.setContentDescription(selected.loading?"停止加载":"刷新网页");progress.setVisibility(selected.loading?View.VISIBLE:View.INVISIBLE);
  }
  void retire(Tab tab){
    WebView view=tab.web;if(view==null)return;tab.web=null;tab.loading=false;tab.generation++;files.cancelFor(view);permissions.onNavigation(view);
    try{tab.saved=new Bundle();view.saveState(tab.saved);}catch(RuntimeException gone){tab.saved=null;}
    try{view.stopLoading();view.getSettings().setBlockNetworkLoads(true);view.onPause();}catch(RuntimeException gone){}
    finally{if(view.getParent() instanceof android.view.ViewGroup)((android.view.ViewGroup)view.getParent()).removeView(view);try{view.setWebChromeClient(null);view.destroy();}catch(RuntimeException gone){}}
  }
  void closeTab(Tab tab){if(!tabs.contains(tab))return;int index=tabs.indexOf(tab);boolean active=tab==selected;retire(tab);tabs.remove(tab);if(active){selected=null;if(tabs.isEmpty())newTab(BrowserPreferences.home(this));else select(tabs.get(Math.min(index,tabs.size()-1)));}updateChrome();}
  void showTabs(){ReferenceUi.Modal dialog=new ReferenceUi.Modal(this,"标签页 · "+tabs.size()+"/8").asSheet();for(Tab tab:new ArrayList<>(tabs)){LinearLayout row=DesignUi.row(this);Button open=ReferenceUi.link(this,(tab==selected?"● ":"")+(tab.title.isEmpty()?tab.url:tab.title),()->{dialog.dismiss();select(tab);});open.setMaxLines(2);row.addView(open,new LinearLayout.LayoutParams(0,-2,1));row.addView(ReferenceUi.iconButton(this,"close","关闭标签页 "+tab.url,()->{dialog.dismiss();closeTab(tab);}),new LinearLayout.LayoutParams(dp(48),dp(48)));dialog.body.addView(row);}dialog.buttons("返回",dialog::dismiss,"新标签页",()->{dialog.dismiss();newTab(BrowserPreferences.home(this));focusAddress();});dialog.show();}
  void menu(){
    ReferenceUi.Modal dialog=new ReferenceUi.Modal(this,"浏览器").asSheet();
    action(dialog,"新标签页",()->{newTab(BrowserPreferences.home(this));focusAddress();});
    action(dialog,library.bookmarked(selected.url)?"取消收藏此页":"收藏此页",()->{if(library.bookmarked(selected.url))library.remove("bookmarks",selected.url);else library.remember("bookmarks",selected.url,selected.title,100);message(library.bookmarked(selected.url)?"已收藏此页":"已取消收藏");});
    action(dialog,"收藏夹",()->showLibrary("bookmarks","收藏夹"));action(dialog,"浏览历史",()->showLibrary("history","浏览历史"));
    action(dialog,"网页内查找",()->{findBar.setVisibility(View.VISIBLE);findText.requestFocus();((InputMethodManager)getSystemService(INPUT_METHOD_SERVICE)).showSoftInput(findText,InputMethodManager.SHOW_IMPLICIT);});
    action(dialog,selected.desktop?"切换手机版网站":"请求桌面版网站",()->{selected.desktop=!selected.desktop;applyDesktop(selected);if(web()!=null){files.cancelFor(web());permissions.onNavigation(web());web().reload();}});
    action(dialog,"分享当前网址",this::share);action(dialog,"复制当前网址",()->{((android.content.ClipboardManager)getSystemService(CLIPBOARD_SERVICE)).setPrimaryClip(ClipData.newPlainText("网址",selected.url));message("已复制网址");});
    action(dialog,"下载文件",files::showDownloads);
    action(dialog,"当前网站权限",this::sitePermissions);
    action(dialog,"此环境的网络设置",()->startActivity(new Intent(this,Profiles.activity(Profiles.slot(this))).putExtra("openWindowAction","network").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_REORDER_TO_FRONT)));
    action(dialog,"首页与启动界面",()->BrowserSettingsUi.show(this,()->{}));
    action(dialog,"设为系统默认浏览器",this::defaultBrowser);action(dialog,"ChatGPT 增强界面 · Gecko",this::openChat);action(dialog,"内核信息",this::engineInfo);dialog.show();
  }
  void action(ReferenceUi.Modal dialog,String title,Runnable run){ReferenceUi.menuAction(dialog,title,()->{dialog.dismiss();run.run();});}
  void linkMenu(String url){ReferenceUi.Modal dialog=new ReferenceUi.Modal(this,"链接").asSheet();dialog.body.addView(ReferenceUi.secondary(this,url));action(dialog,"在新标签页打开",()->newTab(url));action(dialog,"在当前标签页打开",()->go(url));action(dialog,"复制链接",()->((android.content.ClipboardManager)getSystemService(CLIPBOARD_SERVICE)).setPrimaryClip(ClipData.newPlainText("链接",url)));dialog.show();}
  void showLibrary(String key,String title){JSONArray rows=library.list(key);String[] labels=new String[rows.length()];for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);labels[i]=row.optString("title")+"\n"+row.optString("url");}AlertDialog.Builder dialog=AppAppearance.dialog(this).setTitle(title).setNegativeButton("关闭",null);if(labels.length==0)dialog.setMessage("暂无记录");else dialog.setItems(labels,(d,index)->go(rows.optJSONObject(index).optString("url")));if("history".equals(key)&&rows.length()>0)dialog.setNeutralButton("清空",(d,w)->AppAppearance.dialog(this).setTitle("清空浏览历史？").setMessage("只删除网址记录，网站登录状态会保留。").setNegativeButton("取消",null).setPositiveButton("清空",(c,n)->library.clearHistory()).show());dialog.show();}
  void engineInfo(){PackageInfo provider=WebView.getCurrentWebViewPackage();String version=provider==null?"组件信息暂不可用":provider.packageName+" · "+provider.versionName;DesignUi.message(this,"Chromium 内核","Blink / V8 · "+version+"\n\n由 Android System WebView 或 Chrome 提供，随系统组件更新。默认首页为 ChatGPT，地址栏可访问其他网站。\n\nChromium 与 Gecko 分别保存网站登录状态。此界面没有接入 ChatGPT 专用读取和自动操作；Gecko 的指纹保护、WebRTC 限制和后台回复提醒不适用于此内核。\n\n网页 HTTP 请求使用此环境的线路；WebRTC 可能使用系统网络。如需覆盖这些连接，请使用设备级完整 VPN。应用不会自动开启 VPN。\n\n摄像头、麦克风和大致位置按网站逐次授权。Chrome 扩展尚不支持。");}
  void sitePermissions(){String url=selected==null?"":selected.url;AppAppearance.dialog(this).setTitle("当前网站权限").setMessage(url+"\n\n摄像头、麦克风和大致位置在网站请求时逐次确认。Android 系统授权不等于自动允许网站。\n\n结束当前网页可停止此页已开始的媒体访问；未提交的网页输入可能丢失。").setNegativeButton("返回",null).setPositiveButton("结束网页并重载",(d,w)->{Tab tab=selected;if(tab==null)return;hideCustomView();retire(tab);tab.saved=null;showSelected();updateChrome();}).show();}
  void defaultBrowser(){try{if(Build.VERSION.SDK_INT>=29){android.app.role.RoleManager roles=getSystemService(android.app.role.RoleManager.class);if(roles!=null&&roles.isRoleAvailable(android.app.role.RoleManager.ROLE_BROWSER)){if(roles.isRoleHeld(android.app.role.RoleManager.ROLE_BROWSER)){message("当前已是系统默认浏览器");return;}startActivityForResult(roles.createRequestRoleIntent(android.app.role.RoleManager.ROLE_BROWSER),0x2800);return;}}startActivity(new Intent(android.provider.Settings.ACTION_MANAGE_DEFAULT_APPS_SETTINGS));}catch(ActivityNotFoundException unavailable){message("请在系统设置中选择默认浏览器");}}
  void openChat(){startActivity(new Intent(this,Profiles.activity(Profiles.slot(this))).putExtra("legacyChat",true).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_REORDER_TO_FRONT));}
  void external(String url){
    Uri uri;try{uri=Uri.parse(url);}catch(RuntimeException invalid){return;}String scheme=uri.getScheme();
    if(!"mailto".equalsIgnoreCase(scheme)&&!"tel".equalsIgnoreCase(scheme)&&!"sms".equalsIgnoreCase(scheme)){message("已阻止此链接类型");return;}
    AppAppearance.dialog(this).setTitle("打开外部应用？").setMessage(url).setNegativeButton("取消",null).setPositiveButton("打开",(d,w)->{try{startActivity(new Intent(Intent.ACTION_VIEW,uri).addCategory(Intent.CATEGORY_BROWSABLE));}catch(ActivityNotFoundException missing){message("没有可以打开此链接的应用");}}).show();
  }
  void share(){try{startActivity(Intent.createChooser(new Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT,selected.url),"分享网址"));}catch(ActivityNotFoundException missing){message("暂无可用的分享应用");}}
  void focusAddress(){address.requestFocus();address.selectAll();((InputMethodManager)getSystemService(INPUT_METHOD_SERVICE)).showSoftInput(address,InputMethodManager.SHOW_IMPLICIT);}
  void hideKeyboard(){address.clearFocus();((InputMethodManager)getSystemService(INPUT_METHOD_SERVICE)).hideSoftInputFromWindow(address.getWindowToken(),0);}
  void closeFind(){if(findBar==null)return;findBar.setVisibility(View.GONE);findText.setText("");if(web()!=null)web().clearMatches();}
  void showCustomView(View view,WebChromeClient.CustomViewCallback callback){hideCustomView();customView=view;customCallback=callback;((android.view.ViewGroup)getWindow().getDecorView()).addView(view,new android.view.ViewGroup.LayoutParams(-1,-1));}
  void hideCustomView(){if(customView==null)return;View view=customView;customView=null;if(view.getParent() instanceof android.view.ViewGroup)((android.view.ViewGroup)view.getParent()).removeView(view);WebChromeClient.CustomViewCallback callback=customCallback;customCallback=null;if(callback!=null)callback.onCustomViewHidden();}
  @Override protected void onActivityResult(int request,int result,Intent data){if(files!=null&&files.result(request,result,data))return;super.onActivityResult(request,result,data);}
  @Override public void onRequestPermissionsResult(int request,String[] names,int[] grants){if(permissions!=null&&permissions.result(request,names,grants))return;super.onRequestPermissionsResult(request,names,grants);}
  @Override protected void onResume(){super.onResume();foreground=true;if(runtime!=null)runtime.refresh();if(web()!=null)web().onResume();if(permissions!=null)permissions.resume();}
  @Override protected void onStop(){if(permissions!=null)permissions.stopped();super.onStop();}
  void saveCookies(){if(!createdSurface||!flushingCookies.compareAndSet(false,true))return;cookieWorker.execute(()->{try{CookieManager.getInstance().flush();}catch(RuntimeException unavailable){}finally{flushingCookies.set(false);}});}
  @Override protected void onPause(){foreground=false;hideCustomView();if(web()!=null)web().onPause();saveCookies();super.onPause();}
  @Override protected void onSaveInstanceState(Bundle state){ArrayList<String> urls=new ArrayList<>();for(Tab tab:tabs)urls.add(tab.url);state.putStringArrayList("browser.urls",urls);state.putInt("browser.selected",tabs.indexOf(selected));super.onSaveInstanceState(state);}
  void leaveBrowser(){super.onBackPressed();}
  @Override public void onBackPressed(){if(customView!=null){hideCustomView();return;}if(findBar!=null&&findBar.getVisibility()==View.VISIBLE){closeFind();return;}if(web()!=null&&web().canGoBack()){history(-1);return;}if(files!=null&&files.hasActiveDownload()){AppAppearance.dialog(this).setTitle("退出并取消下载？").setMessage("退出浏览器会取消当前下载。留在此页或切到后台可继续下载。").setNegativeButton("继续下载",null).setPositiveButton("退出并取消",(d,w)->leaveBrowser()).show();return;}leaveBrowser();}
  @Override public boolean dispatchKeyEvent(KeyEvent event){if(event.getAction()==KeyEvent.ACTION_DOWN&&event.isCtrlPressed()){switch(event.getKeyCode()){case KeyEvent.KEYCODE_L:focusAddress();return true;case KeyEvent.KEYCODE_T:newTab(BrowserPreferences.home(this));focusAddress();return true;case KeyEvent.KEYCODE_W:if(selected!=null)closeTab(selected);return true;case KeyEvent.KEYCODE_F:findBar.setVisibility(View.VISIBLE);findText.requestFocus();return true;case KeyEvent.KEYCODE_R:reloadOrStop();return true;}}return super.dispatchKeyEvent(event);}
  @Override protected void onDestroy(){destroyed=true;hideCustomView();if(runtime!=null)runtime.close();for(Tab tab:tabs)retire(tab);if(permissions!=null)permissions.close();if(files!=null)files.destroy();saveCookies();cookieWorker.shutdown();super.onDestroy();}
}
