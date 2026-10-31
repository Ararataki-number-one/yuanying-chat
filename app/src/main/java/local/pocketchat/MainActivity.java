package local.pocketchat;

import android.app.*;
import android.os.*;
import android.content.*;
import android.database.Cursor;
import android.graphics.Color;
import android.net.Uri;
import android.view.*;
import android.view.inputmethod.InputMethodManager;
import android.webkit.*;
import android.widget.*;
import android.text.TextUtils;
import org.json.*;
import java.io.*;
import java.util.*;

/** The app manages environments; Gecko displays the official ChatGPT document. */
public class MainActivity extends ThemedActivity {
  static final String ORIGIN="https://chatgpt.com/";
  final Handler handler=new Handler(Looper.getMainLooper());
  GeckoWebView remote;
  // The Android regression asserts that retired native surfaces are absent.
  // These references remain null; recovery reads data without creating editors.
  WebView reader; EditText input; Button send; LinearLayout composer;
  TextView nativeTab,webTab;
  DesignChrome designChrome; AppHub hub; ChatSession session;EnvironmentOverviewUi environmentOverview;
  final ChatSession.Observer sessionObserver=()->applySession();
  SharedPreferences prefs; JSONObject pending; JSONArray entries=new JSONArray();
  String conversation="";
  boolean keyboardVisible,active,submitting,destroyed,networkReady,legacyDraftLoading;
  boolean pageMode=true;
  String pageError="",lastUiStatus="";
  long shownGoogleLoginNotice=-1;
  LoadingUi loading; Attachments attachments; FileDownloads downloads;
  TextView status,exitIpLine,networkLine; LinearLayout toolbar;
  AlertDialog networkDialog; Ui.IconButton navigation; Dialog drawer;
  ReferenceUi.Modal reloadDialog;boolean reloadChecking;
  interface Result {void accept(JSONObject value);}
  void chooseEnvironment(){ProfileUi.show(this);}
  void showStatusDetails(){
    if(session==null||!NetworkStatusUi.current(this,session))return;
    if(session.pending!=null||session.websiteConnectionIssue||session.replyStalled||!session.pageError.isEmpty())ReplyState.show(this);
    else NetworkStatusUi.show(this);
  }
  int dp(int n){return (int)(getResources().getDisplayMetrics().density*n+.5f);}

  void status(String value){
    String message=value==null?"":value;lastUiStatus=message;
    if(status==null)return;
    boolean quiet=message.isEmpty()||message.startsWith("已连接")||message.startsWith("正在")||message.startsWith("准备连接")||message.equals("回复完成")||message.equals("已停止")||message.equals("已停止生成")||message.equals("已停止回复")||message.equals("已取消");
    // Keep binding diagnostics in the delivery record, without a persistent
    // banner or off-page feedback when the conversation changes.
    quiet|=message.equals("对话已改变，请检查上次发送；不会自动重发");
    boolean current=session!=null&&TextUtils.equals(message,session.status);
    boolean sessionError=current&&(session.websiteConnectionIssue||!session.pageError.isEmpty()||!session.networkIssue.isEmpty()&&TextUtils.equals(message,session.networkIssue)&&(session.offline||!session.networkReady&&!session.connecting));
    boolean waiting=current&&session.replyStalled;
    if(waiting)quiet=false;
    boolean error=waiting||!quiet&&(sessionError||message.startsWith("网页反馈：")||message.matches(".*(失败|错误|无法|未能|不可用|未完成|待确认|断开|中断|过期|失效|未通过|请检查|请先|暂未|未添加|需要重新|没有可用).*"));
    boolean fileProgress=session!=null&&session.resourceFilePreparations>0&&message.equals("准备附件…");
    if(error||fileProgress){if(!TextUtils.equals(status.getText(),message))status.setText(message);status.setTextColor(error&&!waiting?DesignUi.RED:DesignUi.MUTED);}
    status.setClickable(error);status.setContentDescription(fileProgress?"正在准备所选附件":"网页或网络错误，点按查看详情");
    status.setVisibility((error||fileProgress)&&hub!=null&&hub.page==AppHub.CHAT?View.VISIBLE:View.GONE);
    if(error&&!waiting&&hub!=null&&hub.page!=AppHub.CHAT)hub.feedback(message,true);
  }
  @Override protected void attachBaseContext(Context base){super.attachBaseContext(new ProfileContext(base,Profiles.processSlot()));}
  @Override public void onCreate(Bundle state){
    super.onCreate(state);
    if(!ProfileCatalog.get(this).available(Profiles.slot(this))){startActivity(new Intent(this,WindowHomeActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));finish();return;}
    if(Build.VERSION.SDK_INT>=30)getWindow().setDecorFitsSystemWindows(false);
    prefs=getSharedPreferences("chat",MODE_PRIVATE);
    // Migrate only the display preference. Cookies, old drafts and engine stores
    // stay untouched, including profiles previously opened in simple mode.
    pageMode=true;if(!prefs.getBoolean("pageMode",false))prefs.edit().putBoolean("pageMode",true).apply();
    session=ChatSession.get(this);pending=session.pending;entries=session.entries;conversation=session.conversation;
    LinearLayout root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);root.setBackgroundColor(ReferenceUi.CHAT_BG);DesignUi.chrome(this);
    ReferenceUi.insets(this,root,visible->{keyboardVisible=visible;updateReadingLayout();});
    designChrome=new DesignChrome(this,root);
    status=label("",12,DesignUi.RED);status.setPadding(dp(14),dp(4),dp(14),dp(4));status.setMaxLines(2);status.setEllipsize(TextUtils.TruncateAt.END);status.setVisibility(View.GONE);status.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
    status.setContentDescription("网页或网络错误，点按查看详情");status.setOnClickListener(v->showStatusDetails());root.addView(status,new LinearLayout.LayoutParams(-1,-2));
    loading=new LoadingUi(this);FrameLayout stack=new FrameLayout(this);root.addView(stack,new LinearLayout.LayoutParams(-1,0,1));
    remote=session.web;if(remote.getParent() instanceof ViewGroup)((ViewGroup)remote.getParent()).removeView(remote);remote.setHost(this);remote.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_AUTO);
    attachments=new Attachments(this);downloads=new FileDownloads(this);remote.setWebViewClient(remoteClient());remote.setWebChromeClient(attachments.chrome());
    stack.addView(remote,new FrameLayout.LayoutParams(-1,-1));stack.addView(loading.cover,new FrameLayout.LayoutParams(-1,-1));
    hub=new AppHub(this,root,stack);setContentView(root);environmentOverview=new EnvironmentOverviewUi(this);
    session.add(sessionObserver);showPage(true);startNetwork();applySession();openNotification(getIntent());environmentOverview.consume(getIntent());
  }
  static WebResourceResponse blocked(){return new WebResourceResponse("text/plain","UTF-8",new ByteArrayInputStream(new byte[0]));}
  static boolean validProxy(String value){try{Uri u=Uri.parse(value);return Arrays.asList("http","https","socks").contains(u.getScheme())&&u.getHost()!=null&&u.getPort()>0&&u.getPort()<65536&&u.getUserInfo()==null&&(u.getPath()==null||u.getPath().isEmpty())&&u.getQuery()==null&&u.getFragment()==null;}catch(Exception e){return false;}}
  void startNetwork(){session.connect();}
  void networkSettings(){FeatureDialogs.network(this);}
  void externalNetworkSettings(){
    if(DesignNetworkUi.busy(this)){status("请等待当前操作完成，再修改网络。");return;}
    LinearLayout box=DesignUi.column(this);box.setPadding(dp(18),dp(8),dp(18),dp(16));
    DesignUi.note(box,Profiles.display(this,Profiles.slot(this))+" · 使用已配置好完整链路的应用代理。");
    String saved=prefs.getString("proxy","");
    EditText proxy=DesignUi.input(box,"代理地址",saved,"http://主机:端口 或 socks://主机:端口");proxy.setInputType(android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_VARIATION_URI);
    DesignUi.note(box,"本机代理可填写 http://127.0.0.1:7890，其中 127.0.0.1 指这部手机。保存后会重新连接此环境。");
    TextView notice=DesignUi.text(this,"",13,DesignUi.RED);notice.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);box.addView(notice);
    ScrollView scroll=new ScrollView(this);scroll.addView(box);
    AlertDialog dialog=AppAppearance.dialog(this).setTitle("应用专用代理").setView(scroll).setPositiveButton("保存并连接",null).setNegativeButton("取消",null).create();
    dialog.show();DesignUi.protectEdits(this,dialog,()->!saved.equals(proxy.getText().toString()));
    dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{
      if(DesignNetworkUi.busy(this)){notice.setText("当前操作还未完成，请稍后再保存。");return;}
      String value=proxy.getText().toString().trim();
      if(!validProxy(value)){proxy.setError("填写 http(s)://主机:端口 或 socks://主机:端口，且不含账号密码或路径");proxy.requestFocus();return;}
      prefs.edit().putBoolean("networkConfigured",true).putString("proxy",value).putString("networkMode","external").commit();dialog.dismiss();session.reconnect();
    });
  }
  static boolean chatUrl(String url){try{Uri u=Uri.parse(url);return "https".equals(u.getScheme())&&"chatgpt.com".equals(u.getHost())&&u.getUserInfo()==null&&(u.getPort()==-1||u.getPort()==443);}catch(Exception e){return false;}}
  WebViewClient remoteClient(){WebViewClient original=session.client();return new WebViewClient(){@Override public void onScaleChanged(WebView v,float oldScale,float newScale){original.onScaleChanged(v,oldScale,newScale);}@Override public WebResourceResponse shouldInterceptRequest(WebView v,WebResourceRequest r){return original.shouldInterceptRequest(v,r);}@Override public boolean shouldOverrideUrlLoading(WebView v,WebResourceRequest r){if(r.isForMainFrame()&&downloads!=null&&downloads.intercept(r.getUrl().toString()))return true;return original.shouldOverrideUrlLoading(v,r);}@Override public void onPageStarted(WebView v,String u,android.graphics.Bitmap i){original.onPageStarted(v,u,i);}@Override public void onPageCommitVisible(WebView v,String u){original.onPageCommitVisible(v,u);}@Override public void onPageFinished(WebView v,String u){original.onPageFinished(v,u);}@Override public void onReceivedError(WebView v,WebResourceRequest r,WebResourceError e){original.onReceivedError(v,r,e);}@Override public void onReceivedHttpError(WebView v,WebResourceRequest r,WebResourceResponse response){original.onReceivedHttpError(v,r,response);}};}

  /** Backward-compatible callers can reveal the page, never select an old mode. */
  void showPage(boolean ignored){
    pageMode=true;if(prefs!=null&&!prefs.getBoolean("pageMode",false))prefs.edit().putBoolean("pageMode",true).apply();
    if(hub!=null&&hub.page!=AppHub.CHAT)hub.show(AppHub.CHAT);
    if(remote!=null)remote.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_AUTO);
    if(loading!=null)loading.update();if(designChrome!=null)designChrome.update();updateReadingLayout();
    if(session!=null)session.wakePolling();
  }
  void updateReadingLayout(){if(hub!=null)hub.keyboard();if(session!=null)session.reading.keyboard(keyboardVisible&&hub!=null&&hub.page==AppHub.CHAT);}
  void hideKeyboard(){if(remote!=null)((InputMethodManager)getSystemService(INPUT_METHOD_SERVICE)).hideSoftInputFromWindow(remote.getWindowToken(),0);}
  void runDriver(String action,JSONObject args,Result cb){session.runDriver(action,args,r->cb.accept(r));}
  final Runnable ticker=new Runnable(){public void run(){if(!active||destroyed)return;NetworkMetricsUi.update(MainActivity.this);handler.postDelayed(this,1000);}};
  void applySession(){
    if(session==null||destroyed)return;pending=session.pending;networkReady=session.networkReady;submitting=session.submitting;entries=session.entries;conversation=session.conversation;
    status(session.status);NetworkMetricsUi.update(this);if(loading!=null)loading.update();if(designChrome!=null)designChrome.update();
  }
  TextView label(String text,int size,int color){TextView v=new TextView(this);v.setText(text);v.setTextSize(size);v.setTextColor(AppAppearance.text(color));return v;}
  void moreSheet(){
    ReferenceUi.Modal d=new ReferenceUi.Modal(this,"会话选项").asSheet();
    if(session.privacy.desktop&&BrowserReadingPolicy.chat(remote.getUrl()))option(d,"网页缩放",()->BrowserReadingUi.show(this));
    option(d,"重新加载网页",this::requestReload);
    if(session.websiteConnectionIssue||session.replyStalled||!session.pageError.isEmpty())option(d,"恢复网页连接",()->ReplyState.websiteConnection(this));
    option(d,"编辑当前环境",()->EnvironmentEditorUi.show(this));
    option(d,"站点权限",()->SitePermissionsUi.show(this));
    option(d,"当前环境网络",()->hub.networkFor(Profiles.slot(this)));
    option(d,"查询当前环境 IP",()->ExitIpPageUi.open(this));
    option(d,"管理全部环境",()->ProfileUi.manage(this));
    option(d,"下载管理",()->hub.select(AppHub.DOWNLOADS));
    option(d,"应用设置",()->hub.select(AppHub.SETTINGS));
    option(d,"暂存草稿",()->copyLegacyDraft());
    if(LoginPagePolicy.google(remote.getUrl()))option(d,"登录帮助",()->LoginHelpUi.show(this));
    d.show();
  }
  boolean reloadMatches(ChatSession.ReloadTarget target){return !destroyed&&session!=null&&target.matches(session)&&remote==session.web;}
  void requestReload(){
    if(reloadChecking||reloadDialog!=null||destroyed)return;
    ChatSession.ReloadTarget target=session.reloadTarget();String url=target.url;
    if(!remote.hasVisibleDocument()||!MainActivity.chatUrl(url)){confirmIndependentReload(target,"无法完整读取当前网页中的输入或表单内容。");return;}
    reloadChecking=true;
    session.asyncDriver("web-inspect",new JSONObject(),2500,state->{
      if(destroyed||session!=target.owner||remote!=session.web){reloadChecking=false;return;}
      ChatSession.ReloadTarget inspected=session.reloadTargetAfterInspection(target,state);
      if(inspected==null||!reloadMatches(inspected)){reloadChecking=false;return;}
      boolean busy=ProfileUi.working(session)||state.optBoolean("busy");
      session.asyncDriver("page-state",J.obj("expectedUrl",url),2500,page->{
        if(!reloadMatches(inspected)){reloadChecking=false;return;}
        if(!inspected.matchesSnapshot(page)){
          String why=page.optString("draftOmittedReason").equals("too-long")?"当前输入共有 "+page.optInt("draftLength")+" 个字符，超过自动暂存范围。":"网页通信暂不可用，无法完整读取当前输入。";
          confirmIndependentReload(inspected,why);return;
        }
        confirmReload(inspected,busy||ProfileUi.working(session),page);
      });
    });
  }
  void confirmReload(ChatSession.ReloadTarget target,boolean interrupted,JSONObject page){
    reloadChecking=false;if(!reloadMatches(target))return;
    boolean draft=PageMemory.hasDraft(page);
    if(draft&&!LocalDraftPolicy.enabled(session.context)){confirmIndependentReload(target,"本机草稿保存已关闭，当前输入不会自动暂存或恢复。");return;}
    if(!interrupted&&!draft){reloadCurrent(target,page);return;}
    ReferenceUi.Modal d=new ReferenceUi.Modal(this,"重新加载网页？");reloadDialog=d;
    d.note(interrupted?"重新加载可能中断正在生成的回复、上传或其他网页操作；未发送的输入可能无法自动恢复。它不会自动重发提问。":"重新加载会关闭当前网页，未发送的输入可能无法自动恢复。");
    if(draft)d.note("当前输入会先暂存。正在回复时，恢复后的网页不会自动填入这份草稿，可从暂存草稿中复制。");
    if(session.resourceFilesUncertain())d.note("附件状态待确认。请先核对网页中的附件；继续重新加载可能中断上传，需重新选择文件。");
    d.setOnDismissListener(unused->{if(reloadDialog==d)reloadDialog=null;});
    d.buttons("取消",d::dismiss,"重新加载",()->{d.dismiss();reloadCurrent(target,page);});d.show();
  }
  void confirmIndependentReload(ChatSession.ReloadTarget target,String reason){
    reloadChecking=false;if(!reloadMatches(target))return;
    ReferenceUi.Modal d=new ReferenceUi.Modal(this,"手动保存后重新加载？");reloadDialog=d;
    d.note(reason+"\n\n请先取消并复制需要保留的输入。继续会关闭当前网页，未保存的草稿、表单或正在进行的回复、上传可能丢失；不会自动重发提问。");
    if(session.resourceFilesUncertain())d.note("附件状态待确认。请先核对网页中的附件；继续重新加载可能中断上传，需重新选择文件。");
    d.setOnDismissListener(unused->{if(reloadDialog==d)reloadDialog=null;});
    d.buttons("取消，先保存",d::dismiss,"已保存，重新加载",()->{d.dismiss();if(reloadMatches(target))session.reloadConfirmed(target,null,true);});d.show();
  }
  void reloadCurrent(ChatSession.ReloadTarget target,JSONObject page){
    if(!reloadMatches(target)||!target.matchesSnapshot(page))return;
    String draft=page.optString("draft");
    if(!draft.trim().isEmpty()&&!LocalDraftPolicy.enabled(session.context)){confirmIndependentReload(target,"本机草稿保存已关闭，当前输入不会自动暂存或恢复。");return;}
    if(draft.trim().isEmpty()){verifyReloadDraft(target,page,LocalDraftPolicy.revision(session.context));return;}
    long draftRevision=LocalDraftPolicy.revision(session.context);
    session.webStore.worker.execute(()->{boolean saved=DraftArchive.get(session.context).save(target.url,draft,"重新加载网页前草稿",draftRevision);handler.post(()->{
      if(!reloadMatches(target))return;
      if(!saved){confirmIndependentReload(target,LocalDraftPolicy.unavailable(session.context)+"，网页尚未重新加载。");return;}
      verifyReloadDraft(target,page,draftRevision);
    });});
  }
  void verifyReloadDraft(ChatSession.ReloadTarget target,JSONObject page,long draftRevision){
    if(!reloadMatches(target))return;
    session.asyncDriver("page-state",J.obj("expectedUrl",target.url),2500,latest->{
      if(!reloadMatches(target))return;
      if(!target.matchesSnapshot(latest)){confirmIndependentReload(target,"无法再次核对当前输入，网页尚未重新加载。");return;}
      if(!page.optString("documentId").equals(latest.optString("documentId"))||!page.optString("draft").equals(latest.optString("draft"))){session.setStatus("当前输入已变化，请保留草稿，需要时再重新加载");return;}
      if(PageMemory.hasDraft(latest)&&(!LocalDraftPolicy.enabled(session.context)||draftRevision!=LocalDraftPolicy.revision(session.context))){confirmIndependentReload(target,"本机草稿保存设置已变化，当前输入需要手动保留。");return;}
      session.reloadConfirmed(target,latest,false);
    });
  }
  void option(ReferenceUi.Modal d,String title,Runnable action){ReferenceUi.menuAction(d,title,()->{d.dismiss();action.run();});}
  void showDrawer(){ProfileUi.manage(this);}

  /** Recovery is explicit copy-only: never replace the official page's draft. */
  void copyLegacyDraft(){
    if(legacyDraftLoading)return;legacyDraftLoading=true;loading.task("正在读取暂存草稿…");
    Thread read=new Thread(()->{
      JSONArray drafts=new JSONArray();Set<String> bodies=new LinkedHashSet<>();boolean failed=false;
      addLegacyDraft(drafts,bodies,"旧版输入草稿",prefs.getString("draft",""));
      JSONObject oldRequest=J.parse(prefs.getString("legacyPending","{}"));addLegacyDraft(drafts,bodies,"旧版待核对提问",oldRequest.optString("prompt"));
      try(ConversationStore store=new ConversationStore(this);Cursor rows=store.getReadableDatabase().query("conversations",new String[]{"title","draft"},null,null,null,null,"touched DESC,rank ASC")){while(rows.moveToNext())addLegacyDraft(drafts,bodies,rows.getString(0),rows.getString(1));}catch(Exception ignored){failed=true;}
      try(Cursor rows=DraftArchive.get(this).getReadableDatabase().query("drafts",new String[]{"origin","body"},null,null,null,null,"created DESC")){while(rows.moveToNext())addLegacyDraft(drafts,bodies,rows.getString(0),rows.getString(1));}catch(Exception ignored){failed=true;}
      for(Map.Entry<String,?> entry:prefs.getAll().entrySet())if(entry.getKey().startsWith("draftBackup:")&&entry.getValue() instanceof String)addLegacyDraft(drafts,bodies,"此前暂存草稿",(String)entry.getValue());
      final boolean incomplete=failed;handler.post(()->{legacyDraftLoading=false;if(destroyed||isFinishing())return;loading.dismissTask();showLegacyDrafts(drafts,incomplete);});
    },"LegacyDraftReader");read.setPriority(Thread.MIN_PRIORITY);read.start();
  }
  void showLegacyDrafts(JSONArray drafts,boolean incomplete){
    if(drafts.length()==0){DesignUi.message(this,"旧版暂存草稿",incomplete?"部分暂存草稿暂时无法读取，请稍后重试。原数据未修改。":"没有找到旧版暂存草稿。网页里的草稿仍由当前网页保存。");return;}
    String[] labels=new String[drafts.length()];for(int i=0;i<labels.length;i++){JSONObject row=drafts.optJSONObject(i);labels[i]=row.optString("origin")+"\n"+draftPreview(row.optString("body"));}
    AppAppearance.dialog(this).setTitle("复制旧版暂存草稿").setItems(labels,(dialog,index)->{
      JSONObject row=drafts.optJSONObject(index);ReferenceUi.Modal detail=new ReferenceUi.Modal(this,"暂存草稿");
      TextView body=label(row.optString("body"),14,ReferenceUi.TEXT);body.setTextIsSelectable(true);detail.body.addView(body,new LinearLayout.LayoutParams(-1,-2));
      detail.note("复制后可在网页输入框中粘贴。不会替换当前网页草稿，也不会发送。");
      detail.buttons("关闭",detail::dismiss,"复制",()->{((ClipboardManager)getSystemService(CLIPBOARD_SERVICE)).setPrimaryClip(ClipData.newPlainText("暂存草稿",row.optString("body")));detail.dismiss();});detail.show();
    }).setNeutralButton("清空网页暂存",(dialog,which)->clearArchivedDrafts()).setNegativeButton("关闭",null).show();
  }
  void clearArchivedDrafts(){
    AppAppearance.dialog(this).setTitle("清空此环境的网页暂存草稿？").setMessage("将删除本机为网页恢复保存的草稿副本。当前网页输入与旧版草稿仍保留；这项删除无法撤销。").setNegativeButton("保留",null).setPositiveButton("清空",(dialog,which)->session.webStore.worker.execute(()->{boolean cleared=DraftArchive.get(session.context).clear();handler.post(()->{if(destroyed||isFinishing())return;if(cleared)copyLegacyDraft();else status("暂存草稿未能清空，请稍后重试");});})).show();
  }
  static String draftPreview(String value){String text=value.replaceAll("\\s+"," ").trim();return text.codePointCount(0,text.length())>160?text.substring(0,text.offsetByCodePoints(0,160))+"…":text;}
  static void addLegacyDraft(JSONArray rows,Set<String> bodies,String origin,String body){if(body!=null&&!body.isEmpty()&&bodies.add(body))rows.put(J.obj("origin",origin==null||origin.isEmpty()?"暂存草稿":origin,"body",body));}
  void switchConversation(String url){if(!chatUrl(url))return;if(session.pending!=null||session.submitting||session.operation){status("当前有未完成请求，请先完成等待再打开其他对话");return;}session.navigate(url,"正在打开对话…");showPage(true);}
  @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(request==74&&attachments!=null)attachments.result(result,data);if(request==FileDownloads.SAVE&&downloads!=null)downloads.result(result,data);if(request==SavedFileActions.EXPORT&&downloads!=null)downloads.savedActions.result(result,data);}
  void openNotification(Intent intent){
    if(intent==null)return;if(intent.hasExtra("openConversation")||intent.hasExtra("openDownload")){intent.removeExtra(EnvironmentOverviewUi.NONCE);intent.removeExtra(EnvironmentOverviewUi.SOURCE);}String windowAction=intent.getStringExtra("openWindowAction");
    if(windowAction!=null){intent.removeExtra("openWindowAction");intent.removeExtra("forceWebMode");if(hub!=null){int target="settings".equals(windowAction)?AppHub.SETTINGS:"network".equals(windowAction)?AppHub.NETWORK:AppHub.CHAT;if(hub.page!=target)hub.show(target);if("network".equals(windowAction))hub.network();}if("edit".equals(windowAction))handler.postDelayed(()->EnvironmentEditorUi.show(this),200);}
    if(intent.getBooleanExtra("openEnvironmentEditor",false)){intent.removeExtra("openEnvironmentEditor");handler.postDelayed(()->EnvironmentEditorUi.show(this),200);}
    String download=intent.getStringExtra("openDownload");if(download!=null){intent.removeExtra("openDownload");if(hub!=null)hub.select(AppHub.DOWNLOADS);for(int i=0;i<downloads.tasks.rows.length();i++){JSONObject row=downloads.tasks.rows.optJSONObject(i);if(download.equals(row.optString("id"))){downloads.taskActions(row);break;}}return;}
    String url=intent.getStringExtra("openConversation");if(!chatUrl(url))return;intent.removeExtra("openConversation");if(hub!=null)hub.select(AppHub.CHAT);
    if(session.pending!=null||session.submitting||session.operation){status("当前有未完成请求，请先完成等待再打开其他对话");return;}
    if(session.networkReady){if(WebReplyObserver.same(url,remote.getUrl())&&!session.navigationFailed){session.sync();showPage(true);}else switchConversation(url);}
    else{session.requestedConversation=url;session.conversation=url;conversation=url;session.connect();}
  }
  @Override protected void onNewIntent(Intent intent){super.onNewIntent(intent);setIntent(intent);if(session==null){finish();return;}ExitIpPageUi.close(this);openNotification(intent);if(environmentOverview!=null)environmentOverview.consume(intent);}
  @Override protected void onResume(){super.onResume();if(!ProfileCatalog.get(this).available(Profiles.slot(this))){finish();return;}AppUpdates.schedule(this);active=true;if(hub!=null)hub.downloadsVisible(true);AppPrefs.maintainCache(this);if(session!=null){session.add(sessionObserver);session.audit.refresh(true);session.foreground(true);session.connect();}if(hub!=null&&hub.page!=AppHub.CHAT){hub.refresh();handler.removeCallbacks(hub.tick);handler.postDelayed(hub.tick,2500);}handler.removeCallbacks(ticker);handler.post(ticker);}
  @Override protected void onPause(){super.onPause();active=false;if(environmentOverview!=null)environmentOverview.close();ExitIpPageUi.close(this);if(hub!=null)hub.downloadsVisible(false);if(designChrome!=null)designChrome.cancelWebGesture();handler.removeCallbacks(ticker);if(session==null||session.deleted)return;NativeNetwork.get(this).traffic.watch(false);session.remove(sessionObserver);session.audit.cancel();session.reading.keyboard(false);session.foreground(false);}
  @Override protected void onDestroy(){destroyed=true;if(environmentOverview!=null)environmentOverview.close();ExitIpPageUi.close(this);if(hub!=null)hub.downloadsVisible(false);if(reloadDialog!=null)reloadDialog.dismiss();if(networkDialog!=null)networkDialog.dismiss();if(downloads!=null)downloads.destroy();if(attachments!=null)attachments.destroy();if(loading!=null)loading.dismissTask();if(hub!=null)hub.networkWorkspace.close();handler.removeCallbacksAndMessages(null);if(session!=null)session.remove(sessionObserver);if(remote!=null&&remote.getParent() instanceof ViewGroup)((ViewGroup)remote.getParent()).removeView(remote);if(remote!=null)remote.setHost(null);super.onDestroy();}
  @Override public void onBackPressed(){if(ExitIpPageUi.back(this)||environmentOverview!=null&&environmentOverview.back())return;if(hub!=null&&hub.page!=AppHub.CHAT){hub.select(AppHub.CHAT);return;}if(remote!=null&&remote.canGoBack()){remote.goBack();return;}moveTaskToBack(true);}
}
