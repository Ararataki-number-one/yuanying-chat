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
  final ExecutorService fingerprintWorker=Executors.newSingleThreadExecutor(r->new Thread(r,"chromium-fingerprint-state"));
  final Handler fingerprintMain=new Handler(Looper.getMainLooper());
  final String fingerprintRuntimeEpoch=UUID.randomUUID().toString();
  volatile ChromiumFingerprintStore.State fingerprintState;
  ChromiumFingerprintSpec fingerprintSpec;String fingerprintScript,fingerprintError="",fingerprintProvider="";
  JSONObject fingerprintReceipt=new JSONObject();
  volatile boolean fingerprintLoading,fingerprintSaving,fingerprintStateReady;
  boolean fingerprintObserving,fingerprintOpenAfterLoad;long fingerprintLoadGeneration,fingerprintSurfaceGeneration,fingerprintObservationGeneration;
  Runnable fingerprintObservationTimeout;
  FingerprintFileChoice fingerprintFileChoice;Intent fingerprintFileResult;int fingerprintFileRequest;
  Tab selected;View customView;WebChromeClient.CustomViewCallback customCallback;volatile boolean foreground,destroyed;boolean createdSurface;
  static final class Tab {
    volatile WebView web;ChromiumRouteLease.Handle routeLease;Bundle saved;String url,title="";boolean loading,desktop,failed;long generation;
    ChromiumFingerprintRuntime.Prepared fingerprint;
    volatile ChromiumFingerprintStore.State fingerprintPolicy;
    volatile ChromiumFingerprintStore.Binding fingerprintBinding;
    volatile boolean fingerprintReady;
    boolean fingerprintValidating,fingerprintStarted,fingerprintBindingPending,fingerprintBindingReady;
    long surfaceGeneration;String fingerprintProviderPackage="",fingerprintProviderVersion="",fingerprintError="",fingerprintNavigation;Message fingerprintPopup;
    Tab(String url){this.url=url;}
  }
  static final class FingerprintFileChoice {
    final BrowserFiles.Pending pending;final Tab tab;final WebView view;final ChromiumFingerprintStore.State policy;
    final long surface,navigation;final String url,providerPackage,providerVersion;
    FingerprintFileChoice(BrowserFiles.Pending pending,Tab tab){this.pending=pending;this.tab=tab;view=tab.web;policy=tab.fingerprintPolicy;surface=tab.surfaceGeneration;navigation=tab.generation;url=pending.url;providerPackage=tab.fingerprintProviderPackage;providerVersion=tab.fingerprintProviderVersion;}
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
    loadFingerprintState();
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
    notice=ReferenceUi.text(this,"正在准备浏览器网络与指纹配置…",13,ReferenceUi.TEXT,false);notice.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);notice.setPadding(dp(12),dp(8),dp(12),dp(8));notice.setOnClickListener(v->{if(selected!=null)selected.fingerprintError="";loadFingerprintState();if(runtime!=null)runtime.refresh();});root.addView(notice);
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
  static boolean sameFingerprintPolicy(ChromiumFingerprintStore.State first,ChromiumFingerprintStore.State second){return first!=null&&second!=null&&first.identity.equals(second.identity)&&first.revision==second.revision&&first.seed.equals(second.seed)&&first.spec().toString().equals(second.spec().toString());}
  String fingerprintProviderKey(){try{PackageInfo provider=WebView.getCurrentWebViewPackage();return provider==null||provider.versionName==null?"":provider.packageName+"/"+provider.versionName;}catch(RuntimeException unavailable){return "";}}
  boolean fingerprintProviderMatches(Tab tab){try{PackageInfo provider=WebView.getCurrentWebViewPackage();return provider!=null&&provider.packageName.equals(tab.fingerprintProviderPackage)&&Objects.equals(provider.versionName,tab.fingerprintProviderVersion);}catch(RuntimeException unavailable){return false;}}
  boolean fingerprintTraffic(Tab tab,WebView view){return !destroyed&&fingerprintStateReady&&!fingerprintLoading&&!fingerprintSaving&&tab!=null&&view!=null&&tab.web==view&&tab.fingerprintReady&&tab.fingerprint!=null&&fingerprintState!=null&&tab.fingerprintPolicy==fingerprintState&&runtime!=null&&runtime.allowed();}
  boolean fingerprintCurrent(Tab tab,WebView view,ChromiumFingerprintStore.State state,ChromiumFingerprintStore.Binding binding){return tab!=null&&foreground&&selected==tab&&live(tab,view)&&!fingerprintLoading&&!fingerprintSaving&&fingerprintStateReady&&fingerprintState==state&&tab.fingerprintPolicy==state&&tab.fingerprintReady&&tab.fingerprint!=null&&binding!=null&&tab.fingerprintBinding==binding&&binding.providerPackage.equals(tab.fingerprintProviderPackage)&&binding.providerVersion.equals(tab.fingerprintProviderVersion)&&binding.runtimeEpoch.equals(fingerprintRuntimeEpoch)&&binding.surfaceGeneration==tab.surfaceGeneration&&binding.navigationGeneration==tab.generation&&fingerprintProviderMatches(tab);}
  void syncFingerprintTraffic(){for(Tab tab:new ArrayList<>(tabs)){WebView view=tab.web;if(view!=null)try{view.getSettings().setBlockNetworkLoads(!fingerprintTraffic(tab,view));}catch(RuntimeException unavailable){retire(tab);}}}
  String fingerprintProblem(Exception error){String value=error.getMessage();return value==null||value.trim().isEmpty()?"配置或内核能力未确认":value.replace('\n',' ').replace('\r',' ').substring(0,Math.min(220,value.length()));}
  void loadFingerprintState(){
    if(destroyed||fingerprintLoading||fingerprintSaving)return;
    fingerprintLoading=true;fingerprintStateReady=false;long generation=++fingerprintLoadGeneration;
    invalidateFingerprintObservation();if(selected!=null)retireFingerprintBinding(selected);syncFingerprintTraffic();
    String cached=fingerprintScript;Context context=getApplicationContext();
    try{fingerprintWorker.execute(()->{
      try{
        ChromiumFingerprintStore.State state=ChromiumFingerprintStore.load(context);ChromiumFingerprintSpec spec=ChromiumFingerprintSpec.from(state.spec());
        String script=cached;if(script==null)try(java.io.InputStream input=context.getAssets().open("chromium-fingerprint.js")){script=J.text(input,256*1024);}
        final String selectedScript=script;
        fingerprintMain.post(()->{
          if(destroyed||generation!=fingerprintLoadGeneration)return;
          String provider=fingerprintProviderKey();boolean changed=!sameFingerprintPolicy(fingerprintState,state)||!provider.equals(fingerprintProvider),rebuild=changed&&fingerprintState!=null;
          if(changed){if(files!=null)files.cancelActiveDownload();for(Tab tab:new ArrayList<>(tabs)){retire(tab);tab.saved=null;tab.fingerprintError="";tab.desktop=spec.desktop();}fingerprintState=state;}
          fingerprintSpec=spec;fingerprintScript=selectedScript;fingerprintProvider=provider;fingerprintError="";fingerprintLoading=false;fingerprintStateReady=true;
          if(rebuild)for(Tab tab:new ArrayList<>(tabs))createSurface(tab);syncFingerprintTraffic();showSelected();drainFingerprintFileResult();updateChrome();if(fingerprintOpenAfterLoad){fingerprintOpenAfterLoad=false;showFingerprintSettings();}
        });
      }catch(Exception failure){fingerprintMain.post(()->{if(destroyed||generation!=fingerprintLoadGeneration)return;fingerprintLoading=false;fingerprintStateReady=false;fingerprintError="Chromium 指纹配置未确认："+fingerprintProblem(failure);syncFingerprintTraffic();cancelFingerprintFileResult("指纹配置未确认，未向网页交付所选文件");message(fingerprintError);});}
    });}catch(RejectedExecutionException closed){fingerprintLoading=false;fingerprintStateReady=false;}
  }
  JSONObject fingerprintNativeFields(JSONObject receipt){return J.obj("nativeSetup",J.obj("state","native-readback","value",receipt),
      "documentStart",J.obj("state",receipt.optBoolean("documentStartRegistered")?"requested":"saved","registered",receipt.optBoolean("documentStartRegistered"),"scope","document-start-frames"),
      "workers",J.obj("state","unsupported","detail","Worker、Service Worker、OffscreenCanvas、AudioWorklet、字体与 TLS 等未获完整覆盖确认"));}
  ChromiumFingerprintStore.Binding fingerprintBinding(Tab tab){return new ChromiumFingerprintStore.Binding(tab.fingerprintProviderPackage,tab.fingerprintProviderVersion,fingerprintRuntimeEpoch,tab.surfaceGeneration,tab.generation);}
  void retireFingerprintBinding(Tab tab){
    ChromiumFingerprintStore.Binding binding=tab.fingerprintBinding;ChromiumFingerprintStore.State state=tab.fingerprintPolicy;
    tab.fingerprintBinding=null;tab.fingerprintBindingPending=false;tab.fingerprintBindingReady=false;if(tab==selected)fingerprintReceipt=new JSONObject();
    if(binding==null||state==null)return;Context context=getApplicationContext();
    try{fingerprintWorker.execute(()->{try{ChromiumFingerprintStore.retire(context,state.identity,binding);}catch(Exception ignored){}});}catch(RejectedExecutionException ignored){}
  }
  void validateFingerprintSurface(Tab tab,WebView view){
    ChromiumFingerprintStore.State state=fingerprintState;
    if(!live(tab,view)||tab.fingerprint==null||tab.fingerprintReady||tab.fingerprintValidating||state==null||tab.fingerprintPolicy!=state||!fingerprintStateReady||fingerprintLoading||fingerprintSaving)return;
    if(!fingerprintProviderMatches(tab)){failFingerprintSurface(tab,view,new IllegalStateException("Chromium 组件已变化，请重新打开浏览器"));return;}
    tab.fingerprintValidating=true;
    ChromiumFingerprintStore.Binding binding=selected==tab&&foreground?fingerprintBinding(tab):null;
    if(binding!=null){retireFingerprintBinding(tab);tab.fingerprintBinding=binding;tab.fingerprintBindingPending=true;}
    String fields=fingerprintNativeFields(tab.fingerprint.receipt()).toString();Context context=getApplicationContext();
    try{fingerprintWorker.execute(()->{
      try{
        ChromiumFingerprintStore.State actual=ChromiumFingerprintStore.load(context);if(!sameFingerprintPolicy(actual,state))throw new java.io.IOException("指纹配置已改变，请重新读取后加载网页");
        JSONObject receipt=null;if(binding!=null){ChromiumFingerprintStore.activate(context,state.identity,state.revision,binding);receipt=ChromiumFingerprintStore.record(context,state.identity,state.revision,binding,new JSONObject(fields));}
        final JSONObject recorded=receipt;
        fingerprintMain.post(()->{
          if(!live(tab,view)||tab.fingerprintPolicy!=state)return;tab.fingerprintValidating=false;
          if(fingerprintState!=state||fingerprintLoading||fingerprintSaving||!fingerprintStateReady)return;
          if(!fingerprintProviderMatches(tab)){failFingerprintSurface(tab,view,new IllegalStateException("Chromium 组件已变化，旧确认已作废"));return;}
          tab.fingerprintReady=true;
          if(binding!=null&&fingerprintCurrent(tab,view,state,binding)){tab.fingerprintBindingPending=false;tab.fingerprintBindingReady=true;fingerprintReceipt=recorded;}
          syncFingerprintTraffic();startFingerprintSurface(tab,view);ensureFingerprintBinding(tab);drainFingerprintFileResult();
        });
      }catch(Exception failure){fingerprintMain.post(()->{if(!live(tab,view)||tab.fingerprintPolicy!=state)return;tab.fingerprintValidating=false;failFingerprintSurface(tab,view,failure);fingerprintStateReady=false;syncFingerprintTraffic();loadFingerprintState();});}
    });}catch(RejectedExecutionException closed){tab.fingerprintValidating=false;failFingerprintSurface(tab,view,closed);}
  }
  void ensureFingerprintBinding(Tab tab){
    WebView view=tab.web;ChromiumFingerprintStore.State state=fingerprintState;
    if(selected!=tab||!foreground||!fingerprintTraffic(tab,view)||!fingerprintProviderMatches(tab)||tab.fingerprintBindingPending||tab.fingerprintBindingReady)return;
    ChromiumFingerprintStore.Binding binding=fingerprintBinding(tab);tab.fingerprintBinding=binding;tab.fingerprintBindingPending=true;
    String fields=fingerprintNativeFields(tab.fingerprint.receipt()).toString();Context context=getApplicationContext();
    try{fingerprintWorker.execute(()->{try{
      ChromiumFingerprintStore.activate(context,state.identity,state.revision,binding);JSONObject receipt=ChromiumFingerprintStore.record(context,state.identity,state.revision,binding,new JSONObject(fields));
      fingerprintMain.post(()->{if(!fingerprintCurrent(tab,view,state,binding))return;tab.fingerprintBindingPending=false;tab.fingerprintBindingReady=true;fingerprintReceipt=receipt;drainFingerprintFileResult();});
    }catch(Exception failure){fingerprintMain.post(()->{if(!fingerprintCurrent(tab,view,state,binding))return;tab.fingerprintBindingPending=false;failFingerprintSurface(tab,view,failure);fingerprintStateReady=false;syncFingerprintTraffic();loadFingerprintState();});}});}catch(RejectedExecutionException closed){tab.fingerprintBindingPending=false;}
  }
  void startFingerprintSurface(Tab tab,WebView view){
    if(!fingerprintTraffic(tab,view)||tab.fingerprintStarted&&tab.fingerprintNavigation==null)return;tab.fingerprintStarted=true;
    try{
      beforeFingerprintNavigation(tab);tab.loading=true;
      if(tab.fingerprintNavigation!=null){String pending=tab.fingerprintNavigation;tab.fingerprintNavigation=null;tab.saved=null;files.cancelFor(view);permissions.onNavigation(view);view.loadUrl(pending);return;}
      if(tab.fingerprintPopup!=null){Message result=tab.fingerprintPopup;tab.fingerprintPopup=null;((WebView.WebViewTransport)result.obj).setWebView(view);result.sendToTarget();return;}
      if(tab.saved!=null){Bundle saved=tab.saved;tab.saved=null;if(view.restoreState(saved)!=null)return;}
      view.loadUrl(tab.url);
    }catch(RuntimeException failure){failFingerprintSurface(tab,view,failure);}
  }
  void denyFingerprintPopup(Tab tab){Message result=tab.fingerprintPopup;tab.fingerprintPopup=null;if(result!=null)try{((WebView.WebViewTransport)result.obj).setWebView(null);result.sendToTarget();}catch(RuntimeException ignored){}}
  void failFingerprintSurface(Tab tab,WebView view,Exception failure){if(tab.web!=view)return;String reason="Chromium 指纹未能应用，网页保持暂停："+fingerprintProblem(failure);retire(tab);tab.saved=null;tab.failed=true;tab.fingerprintError=reason;fingerprintError=reason;if(selected==tab)message(reason);}
  void invalidateFingerprintObservation(){fingerprintObservationGeneration++;fingerprintObserving=false;if(fingerprintObservationTimeout!=null){fingerprintMain.removeCallbacks(fingerprintObservationTimeout);fingerprintObservationTimeout=null;}}
  void beforeFingerprintNavigation(Tab tab){retireFingerprintBinding(tab);if(tab==selected)invalidateFingerprintObservation();tab.generation++;}
  void finishedPage(Tab tab,WebView source,String url){
        if(!live(tab,source)||!url.equals(source.getUrl()))return;tab.loading=false;
        if(!tab.failed&&BrowserAddressPolicy.allowed(url)){tab.url=url;library.remember("history",url,tab.title,200);}
        if(tab==selected)updateChrome();
  }
  boolean fingerprintFileChoiceCurrent(FingerprintFileChoice choice){return choice!=null&&files!=null&&files.pending==choice.pending&&selected==choice.tab&&live(choice.tab,choice.view)&&fingerprintState==choice.policy&&choice.tab.fingerprintPolicy==choice.policy&&choice.surface==choice.tab.surfaceGeneration&&choice.navigation==choice.tab.generation&&Objects.equals(choice.url,choice.view.getUrl())&&choice.providerPackage.equals(choice.tab.fingerprintProviderPackage)&&choice.providerVersion.equals(choice.tab.fingerprintProviderVersion)&&fingerprintProviderMatches(choice.tab);}
  void cancelFingerprintFileResult(String reason){FingerprintFileChoice choice=fingerprintFileChoice;fingerprintFileChoice=null;fingerprintFileResult=null;fingerprintFileRequest=0;if(choice!=null&&files!=null&&files.pending==choice.pending){files.cancelFor(choice.view);if(reason!=null)message(reason);}}
  void drainFingerprintFileResult(){
    if(fingerprintFileResult==null)return;
    FingerprintFileChoice choice=fingerprintFileChoice;
    if(!fingerprintFileChoiceCurrent(choice)){cancelFingerprintFileResult("原网页或指纹配置已改变，未交付所选文件");return;}
    if(!foreground||fingerprintLoading||fingerprintSaving||!fingerprintTraffic(choice.tab,choice.view)||!choice.tab.fingerprintBindingReady)return;
    Intent result=fingerprintFileResult;int request=fingerprintFileRequest;fingerprintFileChoice=null;fingerprintFileResult=null;fingerprintFileRequest=0;
    files.result(request,RESULT_OK,result);
  }
  boolean fingerprintFileResult(int request,int result,Intent data){
    if(files==null||request<BrowserFiles.FIRST_REQUEST||request>BrowserFiles.LAST_REQUEST)return false;
    if(files.pending==null||files.pending.request!=request)return files.result(request,result,data);
    if(result!=RESULT_OK||data==null){fingerprintFileChoice=null;fingerprintFileResult=null;fingerprintFileRequest=0;return files.result(request,result,data);}
    if(!fingerprintFileChoiceCurrent(fingerprintFileChoice)){cancelFingerprintFileResult("原网页或指纹配置已改变，未交付所选文件");if(files.pending!=null&&files.pending.request==request)files.result(request,RESULT_CANCELED,null);return true;}
    fingerprintFileResult=new Intent(data);fingerprintFileRequest=request;message("正在确认原网页与指纹配置，确认后交付所选文件…");fingerprintMain.post(this::drainFingerprintFileResult);return true;
  }
  void showFingerprintSettings(){
    if(fingerprintState==null||!fingerprintStateReady){fingerprintOpenAfterLoad=true;loadFingerprintState();message(fingerprintError.isEmpty()?"正在读取此环境的 Chromium 指纹配置…":fingerprintError);return;}
    ChromiumFingerprintStore.State state=fingerprintState;JSONObject receipt=fingerprintReceipt;
    ChromiumFingerprintUi.show(this,state,receipt,fingerprintObserving,new ChromiumFingerprintUi.Callback(){public void save(JSONObject spec,boolean rotateSeed){saveFingerprint(state,spec,rotateSeed);}public void observe(){observeFingerprint();}});
  }
  void saveFingerprint(ChromiumFingerprintStore.State expected,JSONObject desired,boolean rotateSeed){
    if(destroyed||expected!=fingerprintState||!fingerprintStateReady||fingerprintLoading||fingerprintSaving){message("指纹配置已改变或正在读取，请重新打开设置");return;}
    final JSONObject selectedSpec;try{selectedSpec=ChromiumFingerprintSpec.from(desired).json();if(rotateSeed&&!selectedSpec.toString().equals(ChromiumFingerprintSpec.from(expected.spec()).json().toString()))throw new IllegalArgumentException("请先保存配置，再单独更换稳定种子");}catch(Exception failure){message("指纹配置未保存："+fingerprintProblem(failure));return;}
    fingerprintSaving=true;invalidateFingerprintObservation();if(files!=null)files.cancelActiveDownload();if(selected!=null)retireFingerprintBinding(selected);syncFingerprintTraffic();Context context=getApplicationContext();
    try{fingerprintWorker.execute(()->{try{
      ChromiumFingerprintStore.State actual=rotateSeed?ChromiumFingerprintStore.rotate(context,expected.identity,expected.revision):ChromiumFingerprintStore.save(context,expected.identity,expected.revision,selectedSpec);
      ChromiumFingerprintSpec spec=ChromiumFingerprintSpec.from(actual.spec());
      fingerprintMain.post(()->{if(destroyed)return;fingerprintSaving=false;fingerprintStateReady=false;for(Tab tab:new ArrayList<>(tabs)){retire(tab);tab.saved=null;tab.fingerprintError="";tab.desktop=spec.desktop();}fingerprintState=actual;fingerprintSpec=spec;fingerprintError="";fingerprintStateReady=true;for(Tab tab:new ArrayList<>(tabs))createSurface(tab);showSelected();updateChrome();message("此环境的 Chromium 指纹配置已保存，正在按新配置重新加载全部标签页");});
    }catch(Exception failure){fingerprintMain.post(()->{if(destroyed)return;fingerprintSaving=false;fingerprintStateReady=false;fingerprintError="指纹配置保存未确认："+fingerprintProblem(failure);syncFingerprintTraffic();AppAppearance.dialog(this).setTitle("指纹配置未确认").setMessage(fingerprintError+"\n将重新读取实际保存结果；不会回退为未配置的浏览器。").setPositiveButton("知道了",null).show();loadFingerprintState();});}});}catch(RejectedExecutionException closed){fingerprintSaving=false;fingerprintStateReady=false;}
  }
  void requestFingerprintDesktop(boolean desktop){
    ChromiumFingerprintStore.State state=fingerprintState;if(state==null||fingerprintLoading||fingerprintSaving){message("请先等待指纹配置读取完成");return;}
    JSONObject spec=state.spec();try{spec.put("display",desktop?"desktop":"mobile");}catch(JSONException invalid){return;}
    AppAppearance.dialog(this).setTitle(desktop?"切换此环境为电脑版网站？":"切换此环境为手机版网站？").setMessage("将统一此环境所有标签页的 UA 与 UA-CH 身份，并重新加载全部网页。未提交的网页输入可能丢失。").setNegativeButton("取消",null).setPositiveButton("保存并重新加载",(dialog,which)->saveFingerprint(state,spec,false)).show();
  }
  void observeFingerprint(){
    Tab tab=selected;WebView view=web();ChromiumFingerprintStore.State state=fingerprintState;ChromiumFingerprintStore.Binding binding=tab==null?null:tab.fingerprintBinding;
    if(tab==null||view==null||state==null||!fingerprintCurrent(tab,view,state,binding)||!tab.fingerprintBindingReady||tab.loading||!fingerprintTraffic(tab,view)||!BrowserAddressPolicy.allowed(view.getUrl())){message("请等待当前前台网页、线路与指纹原生确认完成后再自测");return;}
    if(fingerprintObserving)return;String url=view.getUrl();long operation=++fingerprintObservationGeneration;fingerprintObserving=true;
    fingerprintObservationTimeout=()->finishFingerprintObservation(tab,view,state,binding,url,operation,null,"当前网页自测未响应");fingerprintMain.postDelayed(fingerprintObservationTimeout,8000);
    String script="JSON.stringify((()=>{const f=globalThis.__pocketchatChromiumFingerprintObserve;if(typeof f!=='function')throw new Error('Document-start self-test unavailable');return f();})())";
    try{view.evaluateJavascript(script,raw->{JSONObject result=null;String error=null;try{result=fingerprintObservation(raw);}catch(Exception invalid){error="当前网页未提供有效的文档自测确认";}finishFingerprintObservation(tab,view,state,binding,url,operation,result,error);});}catch(RuntimeException unavailable){finishFingerprintObservation(tab,view,state,binding,url,operation,null,"当前网页已不可用");}
  }
  static JSONObject fingerprintObservation(String raw)throws JSONException{
    if(raw==null||raw.length()>32768)throw new JSONException("Self-test response size");
    JSONTokener outer=new JSONTokener(raw);Object decoded=outer.nextValue();if(!(decoded instanceof String)||outer.nextClean()!=0)throw new JSONException("Self-test response missing");
    JSONTokener inner=new JSONTokener((String)decoded);Object parsed=inner.nextValue();if(!(parsed instanceof JSONObject)||inner.nextClean()!=0)throw new JSONException("Self-test JSON differs");JSONObject value=(JSONObject)parsed;
    if(!Integer.valueOf(1).equals(value.opt("schema"))||!"document-start-frames".equals(value.optString("scope"))||!Boolean.FALSE.equals(value.opt("fingerprintProtectionVerified")))throw new JSONException("Self-test scope differs");
    JSONObject fields=value.getJSONObject("fields"),safe=new JSONObject();for(String name:new String[]{"canvas","webgl","audio","webrtc"}){JSONObject field=fields.getJSONObject(name);String status=field.getString("state");if(!Arrays.asList("page-observed","unsupported","failed","not-requested").contains(status))throw new JSONException("Self-test field state differs");safe.put(name,J.obj("state",status));}
    return J.obj("schema",1,"scope","document-start-frames","fingerprintProtectionVerified",false,"fields",safe);
  }
  void finishFingerprintObservation(Tab tab,WebView view,ChromiumFingerprintStore.State state,ChromiumFingerprintStore.Binding binding,String url,long operation,JSONObject result,String error){
    if(operation!=fingerprintObservationGeneration||!fingerprintCurrent(tab,view,state,binding)||tab.loading||!Objects.equals(url,view.getUrl()))return;
    invalidateFingerprintObservation();long completedGeneration=fingerprintObservationGeneration;boolean failed=error!=null;
    if(result!=null){JSONObject observed=result.optJSONObject("fields");for(String name:new String[]{"canvas","webgl","audio","webrtc"})if(observed.optJSONObject(name).optString("state").equals("failed"))failed=true;}
    JSONObject fields=fingerprintNativeFields(tab.fingerprint.receipt());try{fields.put("pageSelfTest",J.obj("state",failed?"failed":"page-observed","value",result==null?J.obj("error",error):result));}catch(JSONException impossible){return;}
    final String encoded=fields.toString();final boolean pause=failed&&fingerprintSpec.protectedMode();final String failureReason=error;
    Context context=getApplicationContext();try{fingerprintWorker.execute(()->{try{JSONObject receipt=ChromiumFingerprintStore.record(context,state.identity,state.revision,binding,new JSONObject(encoded));fingerprintMain.post(()->{if(completedGeneration!=fingerprintObservationGeneration||!fingerprintCurrent(tab,view,state,binding)||!Objects.equals(url,view.getUrl()))return;fingerprintReceipt=receipt;if(pause){tab.fingerprintReady=false;tab.fingerprintError="当前网页的指纹自测失败，已暂停此页联网。刷新可重新应用配置。";view.stopLoading();files.cancelFor(view);files.cancelActiveDownload();syncFingerprintTraffic();}message(pause?tab.fingerprintError:failureReason==null?"当前网页自测已记录；原生确认与页内观测分开显示，不代表完整指纹保护":"网页自测失败："+failureReason);});}catch(Exception failure){fingerprintMain.post(()->{if(completedGeneration==fingerprintObservationGeneration&&fingerprintCurrent(tab,view,state,binding))message("自测结果未保存："+fingerprintProblem(failure));});}});}catch(RejectedExecutionException ignored){}
  }
  void routeChanged(boolean ready,String reason){
    if(destroyed)return;message(ready?"":reason);
    if(!ready){if(files!=null)files.cancelActiveDownload();hideCustomView();for(Tab tab:tabs)retire(tab);content.removeAllViews();}
    else if(selected!=null)showSelected();
    updateChrome();
  }
  void newTab(String input){
    if(tabs.size()>=MAX_TABS){message("最多打开 8 个标签页，请先关闭一个标签页");showTabs();return;}
    try{Tab tab=new Tab(BrowserAddressPolicy.normalizeInput(input));tabs.add(tab);select(tab);}catch(IllegalArgumentException invalid){message(invalid.getMessage());}
  }
  void select(Tab tab){
    if(selected==tab)return;hideCustomView();closeFind();invalidateFingerprintObservation();if(selected!=null){retireFingerprintBinding(selected);if(selected.web!=null){files.cancelFor(selected.web);permissions.onNavigation(selected.web);selected.web.onPause();}}
    selected=tab;content.removeAllViews();showSelected();address.clearFocus();updateChrome();
  }
  void showSelected(){
    if(selected==null||runtime==null||!runtime.allowed())return;
    if(!fingerprintStateReady||fingerprintLoading||fingerprintSaving){message(fingerprintError.isEmpty()?"正在确认此环境的 Chromium 指纹配置…":fingerprintError);return;}
    if(!selected.fingerprintError.isEmpty()){message(selected.fingerprintError);return;}
    Tab tab=selected;if(tab.web==null)createSurface(tab);
    WebView view=tab.web;if(view==null)return;
    if(view.getParent()!=content){content.removeAllViews();if(view.getParent() instanceof android.view.ViewGroup)((android.view.ViewGroup)view.getParent()).removeView(view);content.addView(view,new FrameLayout.LayoutParams(-1,-1));}
    if(foreground)view.onResume();else view.onPause();
    if(tab.fingerprintReady){ensureFingerprintBinding(tab);startFingerprintSurface(tab,view);}else validateFingerprintSurface(tab,view);
  }
  void createSurface(Tab tab){
    ChromiumFingerprintStore.State policy=fingerprintState;
    if(!fingerprintStateReady||fingerprintLoading||fingerprintSaving||policy==null||fingerprintSpec==null||fingerprintScript==null)return;
    ChromiumRouteLease.Handle lease=ChromiumRouteLease.acquireSurface();if(lease==null){runtime.surfaceDeferred();message("正在应用环境线路，完成后再打开网页");return;}
    WebView view;
    try{view=new WebView(this);}catch(RuntimeException failure){lease.close();message("系统 Chromium 组件无法启动，请更新 Android System WebView 或 Chrome 后重试");return;}
    tab.web=view;tab.routeLease=lease;createdSurface=true;
    tab.fingerprintPolicy=policy;tab.surfaceGeneration=++fingerprintSurfaceGeneration;tab.fingerprintReady=false;tab.fingerprintStarted=false;
    WebSettings settings=view.getSettings();settings.setBlockNetworkLoads(true);settings.setJavaScriptEnabled(true);settings.setDomStorageEnabled(true);settings.setAllowFileAccess(false);settings.setAllowContentAccess(false);settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);settings.setMediaPlaybackRequiresUserGesture(true);settings.setSupportMultipleWindows(true);settings.setJavaScriptCanOpenWindowsAutomatically(false);settings.setBuiltInZoomControls(true);settings.setDisplayZoomControls(false);settings.setLoadWithOverviewMode(true);settings.setUseWideViewPort(true);settings.setOffscreenPreRaster(false);settings.setSafeBrowsingEnabled(true);
    CookieManager.getInstance().setAcceptThirdPartyCookies(view,false);
    try{
      tab.fingerprint=ChromiumFingerprintRuntime.prepare(view,fingerprintSpec,policy.seed,fingerprintScript);
      JSONObject nativeReceipt=tab.fingerprint.receipt();tab.fingerprintProviderPackage=nativeReceipt.getString("providerPackage");tab.fingerprintProviderVersion=nativeReceipt.getString("providerVersion");
      tab.desktop=fingerprintSpec.desktop();if(!fingerprintProviderMatches(tab))throw new IllegalStateException("Chromium 组件已变化，请重新打开浏览器");
    }catch(Exception failure){failFingerprintSurface(tab,view,failure);return;}
    view.setWebViewClient(new WebViewClient(){
      @Override public boolean shouldOverrideUrlLoading(WebView source,WebResourceRequest request){
        if(!live(tab,source))return true;String url=request.getUrl().toString();
        if(BrowserAddressPolicy.allowed(url))return !fingerprintTraffic(tab,source);
        if(request.isForMainFrame()&&request.hasGesture())external(url);return true;
      }
      @Override public WebResourceResponse shouldInterceptRequest(WebView source,WebResourceRequest request){
        String scheme=request.getUrl().getScheme();
        if(!fingerprintTraffic(tab,source)||("http".equals(scheme)||"https".equals(scheme))&&!BrowserAddressPolicy.allowed(request.getUrl().toString()))return new WebResourceResponse("text/plain","UTF-8",503,"Network unavailable",Collections.emptyMap(),new java.io.ByteArrayInputStream(new byte[0]));return null;
      }
      @Override public void onPageStarted(WebView source,String url,Bitmap icon){
        if(!live(tab,source))return;files.cancelFor(source);permissions.onNavigation(source);retireFingerprintBinding(tab);if(tab==selected)invalidateFingerprintObservation();tab.generation++;tab.loading=true;tab.failed=false;if(BrowserAddressPolicy.allowed(url))tab.url=url;
        if(!fingerprintTraffic(tab,source)||!BrowserAddressPolicy.allowed(url)&&!"about:blank".equals(url)){source.stopLoading();tab.loading=false;tab.failed=true;if(tab==selected){message("网页地址、线路或指纹配置未确认，已暂停加载");updateChrome();}return;}ensureFingerprintBinding(tab);if(tab==selected){message("");updateChrome();}
      }
      @Override public void onPageFinished(WebView source,String url){
        finishedPage(tab,source,url);
      }
      @Override public void doUpdateVisitedHistory(WebView source,String url,boolean reload){if(live(tab,source)&&BrowserAddressPolicy.allowed(url)){if(!url.equals(tab.url)){beforeFingerprintNavigation(tab);tab.url=url;ensureFingerprintBinding(tab);}if(tab==selected)updateChrome();}}
      @Override public void onReceivedError(WebView source,WebResourceRequest request,WebResourceError error){if(live(tab,source)&&request.isForMainFrame()&&request.getUrl().toString().equals(source.getUrl())){tab.loading=false;tab.failed=true;if(tab==selected){message("网页暂时无法打开，检查网络后可刷新重试");updateChrome();}}}
      @Override public void onReceivedSslError(WebView source,SslErrorHandler handler,SslError error){handler.cancel();if(live(tab,source)){tab.failed=true;if(tab==selected)message("网站证书无法验证，已停止连接");}}
      @Override public boolean onRenderProcessGone(WebView source,RenderProcessGoneDetail detail){if(live(tab,source)){retire(tab);if(tab==selected){content.removeAllViews();message("网页进程已退出，点击刷新恢复这个标签页");updateChrome();}}return true;}
    });
    view.setWebChromeClient(new WebChromeClient(){
      @Override public void onProgressChanged(WebView source,int value){if(live(tab,source)&&tab==selected){progress.setProgress(value);progress.setVisibility(value<100?View.VISIBLE:View.INVISIBLE);}}
      @Override public void onReceivedTitle(WebView source,String title){if(live(tab,source)){tab.title=BrowserLibrary.title(title,tab.url);if(tab==selected)updateChrome();}}
      @Override public boolean onShowFileChooser(WebView source,ValueCallback<Uri[]> callback,FileChooserParams params){if(!live(tab,source)||selected!=tab||!foreground||!fingerprintTraffic(tab,source)){callback.onReceiveValue(null);message("请等待原网页、线路与指纹配置确认完成后再选择文件");return true;}cancelFingerprintFileResult(null);boolean handled=files.choose(source,callback,params);if(files.pending!=null&&files.pending.owner==source)fingerprintFileChoice=new FingerprintFileChoice(files.pending,tab);return handled;}
      @Override public boolean onCreateWindow(WebView source,boolean dialog,boolean gesture,Message result){
        if(!live(tab,source)||tab!=selected||!foreground||!gesture||!fingerprintTraffic(tab,source)||tabs.size()>=MAX_TABS||result==null||!(result.obj instanceof WebView.WebViewTransport))return false;
        Tab popup=new Tab(BrowserPreferences.home(BrowserActivity.this));popup.fingerprintPopup=result;tabs.add(popup);select(popup);return true;
      }
      @Override public void onCloseWindow(WebView source){if(live(tab,source))closeTab(tab);}
      @Override public void onPermissionRequest(PermissionRequest request){if(live(tab,view)&&tab==selected&&fingerprintTraffic(tab,view))permissions.request(view,request);else request.deny();}
      @Override public void onPermissionRequestCanceled(PermissionRequest request){permissions.cancel(request);}
      @Override public void onGeolocationPermissionsShowPrompt(String origin,GeolocationPermissions.Callback callback){if(live(tab,view)&&tab==selected&&fingerprintTraffic(tab,view))permissions.geolocation(view,origin,callback);else callback.invoke(origin,false,false);}
      @Override public void onGeolocationPermissionsHidePrompt(){permissions.hideGeolocation();}
      @Override public void onShowCustomView(View custom,CustomViewCallback callback){if(live(tab,view)&&tab==selected)showCustomView(custom,callback);else callback.onCustomViewHidden();}
      @Override public void onHideCustomView(){hideCustomView();}
    });
    view.setFindListener((index,count,done)->{if(live(tab,view)&&tab==selected)findCount.setText(count==0?"0/0":(index+1)+"/"+count);});
    view.setDownloadListener((url,ua,disposition,mime,bytes)->{if(live(tab,view)&&fingerprintTraffic(tab,view))files.download(view,url,ua,disposition,mime,bytes);});
    view.setOnLongClickListener(v->{WebView.HitTestResult hit=view.getHitTestResult();String target=hit==null?null:hit.getExtra();if(target!=null&&BrowserAddressPolicy.allowed(target)){linkMenu(target);return true;}return false;});
    validateFingerprintSurface(tab,view);
  }
  void go(String input){
    try{String url=BrowserAddressPolicy.normalizeInput(input==null||input.trim().isEmpty()?BrowserPreferences.home(this):input);hideKeyboard();closeFind();
      if(selected==null){newTab(url);return;}denyFingerprintPopup(selected);selected.url=url;selected.saved=null;
      if(web()!=null&&fingerprintTraffic(selected,web())){selected.fingerprintNavigation=null;files.cancelFor(web());permissions.onNavigation(web());beforeFingerprintNavigation(selected);selected.loading=true;web().loadUrl(url);}else{selected.fingerprintNavigation=url;if(runtime!=null)runtime.refresh();showSelected();}updateChrome();
    }catch(IllegalArgumentException invalid){message(invalid.getMessage());}
  }
  void history(int direction){if(web()==null||!fingerprintTraffic(selected,web()))return;closeFind();files.cancelFor(web());permissions.onNavigation(web());if(direction<0&&web().canGoBack()){beforeFingerprintNavigation(selected);selected.loading=true;web().goBack();}else if(direction>0&&web().canGoForward()){beforeFingerprintNavigation(selected);selected.loading=true;web().goForward();}updateChrome();}
  void reloadOrStop(){if(selected==null)return;if(selected.loading&&web()!=null){web().stopLoading();selected.loading=false;updateChrome();return;}if(!selected.fingerprintError.isEmpty()){retire(selected);selected.saved=null;selected.fingerprintError="";loadFingerprintState();return;}if(runtime==null)return;if(runtime.allowed()){if(web()==null)showSelected();else if(fingerprintTraffic(selected,web())){files.cancelFor(web());permissions.onNavigation(web());beforeFingerprintNavigation(selected);selected.loading=true;web().reload();updateChrome();}}else runtime.refresh();}
  void updateChrome(){
    if(selected==null)return;if(!address.hasFocus()&&!selected.url.contentEquals(address.getText()))address.setText(selected.url);
    String safety=selected.url.startsWith("https://")?"HTTPS":"HTTP · 不安全";caption.setText("Chromium · "+safety+" · "+(selected.title.isEmpty()?Profiles.display(this,Profiles.slot(this)):selected.title));
    back.setEnabled(web()!=null&&web().canGoBack());forward.setEnabled(web()!=null&&web().canGoForward());tabCount.setText(String.valueOf(tabs.size()));tabCount.setContentDescription(tabs.size()+" 个标签页，点击管理");reload.setContentDescription(selected.loading?"停止加载":"刷新网页");progress.setVisibility(selected.loading?View.VISIBLE:View.INVISIBLE);
  }
  void retire(Tab tab){
    retireFingerprintBinding(tab);if(tab==selected)invalidateFingerprintObservation();tab.fingerprintReady=false;tab.fingerprintValidating=false;tab.fingerprintStarted=false;
    ChromiumFingerprintRuntime.Prepared prepared=tab.fingerprint;tab.fingerprint=null;tab.fingerprintPolicy=null;denyFingerprintPopup(tab);
    WebView view=tab.web;ChromiumRouteLease.Handle lease=tab.routeLease;tab.routeLease=null;if(fingerprintFileChoice!=null&&fingerprintFileChoice.tab==tab)cancelFingerprintFileResult(null);if(view==null){if(prepared!=null)try{prepared.close();}catch(RuntimeException ignored){}if(lease!=null)lease.close();return;}try{tab.web=null;tab.loading=false;tab.generation++;files.cancelFor(view);permissions.onNavigation(view);
    try{tab.saved=new Bundle();view.saveState(tab.saved);}catch(RuntimeException gone){tab.saved=null;}
    try{view.stopLoading();view.getSettings().setBlockNetworkLoads(true);view.onPause();}catch(RuntimeException gone){}
    finally{if(prepared!=null)try{prepared.close();}catch(RuntimeException ignored){}if(view.getParent() instanceof android.view.ViewGroup)((android.view.ViewGroup)view.getParent()).removeView(view);try{view.setWebChromeClient(null);view.destroy();}catch(RuntimeException gone){}}}finally{if(lease!=null)lease.close();}
  }
  void closeTab(Tab tab){if(!tabs.contains(tab))return;int index=tabs.indexOf(tab);boolean active=tab==selected;retire(tab);tabs.remove(tab);if(active){selected=null;if(tabs.isEmpty())newTab(BrowserPreferences.home(this));else select(tabs.get(Math.min(index,tabs.size()-1)));}updateChrome();}
  void showTabs(){ReferenceUi.Modal dialog=new ReferenceUi.Modal(this,"标签页 · "+tabs.size()+"/8").asSheet();for(Tab tab:new ArrayList<>(tabs)){LinearLayout row=DesignUi.row(this);Button open=ReferenceUi.link(this,(tab==selected?"● ":"")+(tab.title.isEmpty()?tab.url:tab.title),()->{dialog.dismiss();select(tab);});open.setMaxLines(2);row.addView(open,new LinearLayout.LayoutParams(0,-2,1));row.addView(ReferenceUi.iconButton(this,"close","关闭标签页 "+tab.url,()->{dialog.dismiss();closeTab(tab);}),new LinearLayout.LayoutParams(dp(48),dp(48)));dialog.body.addView(row);}dialog.buttons("返回",dialog::dismiss,"新标签页",()->{dialog.dismiss();newTab(BrowserPreferences.home(this));focusAddress();});dialog.show();}
  void menu(){
    ReferenceUi.Modal dialog=new ReferenceUi.Modal(this,"浏览器").asSheet();
    action(dialog,"新标签页",()->{newTab(BrowserPreferences.home(this));focusAddress();});
    action(dialog,library.bookmarked(selected.url)?"取消收藏此页":"收藏此页",()->{if(library.bookmarked(selected.url))library.remove("bookmarks",selected.url);else library.remember("bookmarks",selected.url,selected.title,100);message(library.bookmarked(selected.url)?"已收藏此页":"已取消收藏");});
    action(dialog,"收藏夹",()->showLibrary("bookmarks","收藏夹"));action(dialog,"浏览历史",()->showLibrary("history","浏览历史"));
    action(dialog,"网页内查找",()->{findBar.setVisibility(View.VISIBLE);findText.requestFocus();((InputMethodManager)getSystemService(INPUT_METHOD_SERVICE)).showSoftInput(findText,InputMethodManager.SHOW_IMPLICIT);});
    action(dialog,selected.desktop?"手机版网站 · 此环境全部标签页":"电脑版网站 · 此环境全部标签页",()->requestFingerprintDesktop(!selected.desktop));
    action(dialog,"Chromium 指纹配置与当前网页自测",this::showFingerprintSettings);
    action(dialog,"分享当前网址",this::share);action(dialog,"复制当前网址",()->{((android.content.ClipboardManager)getSystemService(CLIPBOARD_SERVICE)).setPrimaryClip(ClipData.newPlainText("网址",selected.url));message("已复制网址");});
    action(dialog,"下载文件",files::showDownloads);
    action(dialog,"关闭浏览器",this::confirmCloseBrowser);
    action(dialog,"当前网站权限",this::sitePermissions);
    action(dialog,"此环境的网络设置",()->startActivity(new Intent(this,Profiles.activity(Profiles.slot(this))).putExtra("openWindowAction","network").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_REORDER_TO_FRONT)));
    action(dialog,"首页与启动界面",()->BrowserSettingsUi.show(this,()->{}));
    action(dialog,"设为系统默认浏览器",this::defaultBrowser);action(dialog,"ChatGPT 增强界面 · Gecko",this::openChat);action(dialog,"内核信息",this::engineInfo);dialog.show();
  }
  void action(ReferenceUi.Modal dialog,String title,Runnable run){ReferenceUi.menuAction(dialog,title,()->{dialog.dismiss();run.run();});}
  void linkMenu(String url){ReferenceUi.Modal dialog=new ReferenceUi.Modal(this,"链接").asSheet();dialog.body.addView(ReferenceUi.secondary(this,url));action(dialog,"在新标签页打开",()->newTab(url));action(dialog,"在当前标签页打开",()->go(url));action(dialog,"复制链接",()->((android.content.ClipboardManager)getSystemService(CLIPBOARD_SERVICE)).setPrimaryClip(ClipData.newPlainText("链接",url)));dialog.show();}
  void showLibrary(String key,String title){JSONArray rows=library.list(key);String[] labels=new String[rows.length()];for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);labels[i]=row.optString("title")+"\n"+row.optString("url");}AlertDialog.Builder dialog=AppAppearance.dialog(this).setTitle(title).setNegativeButton("关闭",null);if(labels.length==0)dialog.setMessage("暂无记录");else dialog.setItems(labels,(d,index)->go(rows.optJSONObject(index).optString("url")));if("history".equals(key)&&rows.length()>0)dialog.setNeutralButton("清空",(d,w)->AppAppearance.dialog(this).setTitle("清空浏览历史？").setMessage("只删除网址记录，网站登录状态会保留。").setNegativeButton("取消",null).setPositiveButton("清空",(c,n)->library.clearHistory()).show());dialog.show();}
  void engineInfo(){PackageInfo provider=WebView.getCurrentWebViewPackage();String version=provider==null?"组件信息暂不可用":provider.packageName+" · "+provider.versionName;String fingerprint=fingerprintState==null?"此环境指纹配置尚未确认":"此环境独立指纹配置 · 版本 "+fingerprintState.revision;DesignUi.message(this,"Chromium 内核","Blink / V8 · "+version+"\n\n由 Android System WebView 或 Chrome 提供，随系统组件更新。默认首页为 ChatGPT，地址栏可访问其他网站。\n\n"+fingerprint+"。原生 UA / UA-CH 的设置回读、文档起始脚本注册与当前网页自测分开记录；脚本已注册不等于保护已验证。可在浏览器菜单查看 Chromium 指纹配置。\n\n文档保护限已配置的页面与框架。Worker、Service Worker、OffscreenCanvas、AudioWorklet、字体、时区、硬件及 TLS 等仍不具备完整覆盖确认。Chromium 与 Gecko 的配置、种子和确认记录独立；网站登录与 Cookie 也分别保存。\n\n网页 HTTP 请求使用此环境的线路。文档 WebRTC 限制不等于设备级网络保护；完整覆盖仍需设备级 VPN，应用不会自动开启 VPN。\n\n摄像头、麦克风和大致位置按网站逐次授权。Chrome 扩展尚不支持。");}
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
  @Override protected void onActivityResult(int request,int result,Intent data){if(fingerprintFileResult(request,result,data))return;super.onActivityResult(request,result,data);}
  @Override public void onRequestPermissionsResult(int request,String[] names,int[] grants){if(permissions!=null&&permissions.result(request,names,grants))return;super.onRequestPermissionsResult(request,names,grants);}
  @Override protected void onResume(){super.onResume();foreground=true;loadFingerprintState();if(runtime!=null)runtime.refresh();if(web()!=null)web().onResume();if(permissions!=null)permissions.resume();}
  @Override protected void onStop(){if(permissions!=null)permissions.stopped();super.onStop();}
  void saveCookies(){if(!createdSurface||!flushingCookies.compareAndSet(false,true))return;cookieWorker.execute(()->{try{CookieManager.getInstance().flush();}catch(RuntimeException unavailable){}finally{flushingCookies.set(false);}});}
  @Override protected void onPause(){foreground=false;invalidateFingerprintObservation();if(selected!=null)retireFingerprintBinding(selected);hideCustomView();if(web()!=null)web().onPause();saveCookies();super.onPause();}
  @Override protected void onSaveInstanceState(Bundle state){ArrayList<String> urls=new ArrayList<>();for(Tab tab:tabs)urls.add(tab.url);state.putStringArrayList("browser.urls",urls);state.putInt("browser.selected",tabs.indexOf(selected));super.onSaveInstanceState(state);}
  void leaveBrowser(){if(runtime!=null)runtime.close();if(files!=null)files.destroy();for(Tab tab:tabs)retire(tab);finish();}
  void confirmCloseBrowser(){boolean downloading=files!=null&&files.hasActiveDownload();AppAppearance.dialog(this).setTitle("关闭浏览器？").setMessage("将关闭全部标签页，未保存的网页输入可能丢失。"+(downloading?"正在进行的下载会取消。":"")+"关闭后，此环境等待中的网络设置可以应用。").setNegativeButton("继续浏览",null).setPositiveButton(downloading?"关闭并取消下载":"关闭浏览器",(d,w)->leaveBrowser()).show();}
  @Override public void onBackPressed(){if(customView!=null){hideCustomView();return;}if(findBar!=null&&findBar.getVisibility()==View.VISIBLE){closeFind();return;}if(web()!=null&&web().canGoBack()){history(-1);return;}confirmCloseBrowser();}
  @Override public boolean dispatchKeyEvent(KeyEvent event){if(event.getAction()==KeyEvent.ACTION_DOWN&&event.isCtrlPressed()){switch(event.getKeyCode()){case KeyEvent.KEYCODE_L:focusAddress();return true;case KeyEvent.KEYCODE_T:newTab(BrowserPreferences.home(this));focusAddress();return true;case KeyEvent.KEYCODE_W:if(selected!=null)closeTab(selected);return true;case KeyEvent.KEYCODE_F:findBar.setVisibility(View.VISIBLE);findText.requestFocus();return true;case KeyEvent.KEYCODE_R:reloadOrStop();return true;}}return super.dispatchKeyEvent(event);}
  @Override protected void onDestroy(){destroyed=true;fingerprintStateReady=false;invalidateFingerprintObservation();hideCustomView();if(runtime!=null)runtime.close();for(Tab tab:tabs)retire(tab);if(permissions!=null)permissions.close();if(files!=null)files.destroy();saveCookies();fingerprintMain.removeCallbacksAndMessages(null);fingerprintWorker.shutdown();cookieWorker.shutdown();super.onDestroy();}
}
