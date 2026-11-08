package local.pocketchat;

import android.app.*;import android.content.*;import android.graphics.Color;import android.os.*;import android.text.InputType;import android.view.*;import android.widget.*;
import org.json.*;import java.util.*;import java.util.concurrent.*;

/** Three native tabs over the existing per-window network implementation. */
final class NetworkWorkspaceUi {
  private static final ExecutorService libraryWorker=Executors.newSingleThreadExecutor();
  final Activity a;final FrameLayout host;final Handler main=new Handler(Looper.getMainLooper());final ExecutorService reader=Executors.newSingleThreadExecutor();
  LinearLayout root,box,tabHost,feedbackHost;Button filterButton;TextView pageSummary;ScrollView scroll;NetworkCatalog catalog;JSONArray windows=new JSONArray();int tab,filter,focus=-1;boolean focusPending,reading,closed;long lastRead;String lastRendered="";Runnable afterRead;
  NetworkWorkspaceUi(Activity a,FrameLayout host){this.a=a;this.host=host;}
  int dp(int n){return ReferenceUi.dp(a,n);}
  void show(int requested){tab=Math.max(0,Math.min(2,requested));if(root==null)layout();else{if(root.getParent()!=host){host.removeAllViews();host.addView(root,new FrameLayout.LayoutParams(-1,-1));}render();}fetch();}
  void layout(){
    lastRendered="";root=DesignUi.column(a);root.setBackgroundColor(ReferenceUi.BG);
    root.setClipChildren(false);root.setClipToPadding(false);
    LinearLayout head=DesignUi.row(a);head.setPadding(dp(22),dp(14),dp(18),dp(14));head.setClipChildren(false);head.setClipToPadding(false);
    LinearLayout heading=DesignUi.column(a);heading.setGravity(Gravity.CENTER_VERTICAL);
    TextView title=NetworkWorkspaceStyle.text(a,"网络",30,ReferenceUi.TEXT,true);
    if(Build.VERSION.SDK_INT>=28)title.setAccessibilityHeading(true);heading.addView(title);
    pageSummary=NetworkWorkspaceStyle.text(a,"正在读取网络信息",12,ReferenceUi.MUTED,false);
    pageSummary.setPadding(0,dp(3),dp(6),0);pageSummary.setMaxLines(2);pageSummary.setEllipsize(android.text.TextUtils.TruncateAt.END);heading.addView(pageSummary);
    head.addView(heading,new LinearLayout.LayoutParams(0,-2,1));
    Button refresh=NetworkWorkspaceStyle.glassAction(a,"refresh","刷新网络状态",()->{lastRead=0;fetch();});
    head.addView(refresh,new LinearLayout.LayoutParams(dp(50),dp(50)));
    Button more=NetworkWorkspaceStyle.glassAction(a,"more","网络更多操作",this::networkMore);
    LinearLayout.LayoutParams menu=new LinearLayout.LayoutParams(dp(50),dp(50));menu.leftMargin=dp(8);head.addView(more,menu);root.addView(head);
    tabHost=DesignUi.column(a);tabHost.setPadding(dp(20),0,dp(20),dp(14));root.addView(tabHost);
    filterButton=NetworkWorkspaceStyle.smallAction(a,"",()->{filter=0;focus=-1;scroll.scrollTo(0,0);render();});
    filterButton.setContentDescription("清除网络筛选");filterButton.setVisibility(View.GONE);
    LinearLayout.LayoutParams filtered=new LinearLayout.LayoutParams(-2,-2);filtered.leftMargin=dp(20);filtered.rightMargin=dp(20);filtered.bottomMargin=dp(8);root.addView(filterButton,filtered);
    feedbackHost=DesignUi.column(a);root.addView(feedbackHost,new LinearLayout.LayoutParams(-1,-2));
    scroll=new ScrollView(a);scroll.setFillViewport(false);scroll.setClipToPadding(false);box=DesignUi.column(a);box.setPadding(dp(20),0,dp(20),dp(18));
    scroll.addView(box);root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));host.removeAllViews();host.addView(root,new FrameLayout.LayoutParams(-1,-1));render();
  }
  void setBottomInset(int footerHeight){
    if(box==null||scroll==null)return;
    // Make the dock's safe end part of the measured child. ScrollView's touch
    // interception can reject short content whose range is only outer padding.
    int bottom=dp(18)+Math.max(0,footerHeight);
    if(box.getPaddingBottom()!=bottom)box.setPadding(box.getPaddingLeft(),box.getPaddingTop(),box.getPaddingRight(),bottom);
    if(scroll.getPaddingBottom()!=0)scroll.setPadding(scroll.getPaddingLeft(),scroll.getPaddingTop(),scroll.getPaddingRight(),0);
  }
  void networkMore(){ReferenceUi.Modal d=new ReferenceUi.Modal(a,"网络").asSheet();if(tab==0)ReferenceUi.menuAction(d,"筛选环境",()->{d.dismiss();filters();});ReferenceUi.menuAction(d,"导入网络",()->{d.dismiss();a.startActivity(new Intent(a,NetworkImportActivity.class));});d.buttons("关闭",d::dismiss,"",()->{});d.show();}
  void select(int next){tab=next;if(a instanceof MainActivity)((MainActivity)a).hub.networkTab=next;filter=0;scroll.scrollTo(0,0);render();}
  /** Runs on the metadata reader. UI callbacks consume this captured identity only. */
  static void readUiMetadata(Context c,JSONArray list){for(int i=0;i<list.length();i++){
    JSONObject item=list.optJSONObject(i),row=item==null?null:item.optJSONObject("row");if(row==null)continue;
    NetworkCatalog.put(item,"pendingNetwork",false);item.remove("pendingConfig");item.remove("pendingAction");
    try{
      Context profile=Profiles.context(c,row.optInt("slot"));EnvironmentSpec.Identity expected=new EnvironmentSpec.Identity(row.optInt("slot"),row.optInt("generation"),row.optString("environmentId"));
      NetworkRegion.read(profile);
      JSONObject metadata=EnvironmentSpecRuntime.withIntent(profile,()->{
        EnvironmentSpecRuntime.requireIdentity(profile,expected);JSONObject pending=NetworkChanges.pendingStrict(profile);
        if(!NetworkChanges.identityMatches(pending,expected.json()))throw new java.io.IOException("Changed environment");
        if(pending.length()>0&&(!("apply".equals(pending.optString("action"))||"external".equals(pending.optString("action")))||pending.optJSONObject("config")==null))throw new java.io.IOException("Invalid saved candidate");
        EnvironmentSpec spec=new EnvironmentSpecRepository(profile).load();if(!spec.identity.equals(expected))throw new java.io.IOException("Changed environment");
        SharedPreferences preferences=profile.getSharedPreferences("chat",0);JSONObject marker=NetworkChanges.intent(pending);
        byte[] activeBytes=new SecretStore(profile).get("network");JSONObject activeConfig=activeBytes==null?new JSONObject():EnvironmentSpecRepository.strictObject(activeBytes);
        try{NetworkShareSelection.migrate(profile,expected,activeConfig,pending.toString(),spec);}catch(Exception unavailable){/* Sharing reports its own typed read failure; editing stays independent. */}
        JSONObject result=J.obj("available",true,"environmentId",expected.environmentId,"generation",expected.generation,"desiredRevision",spec.desiredRevision,"appliedRevision",spec.appliedRevision,"pending",pending,"candidateId",pendingCandidateId(pending,marker),"pendingReady",marker==null||"ready".equals(marker.optString("state")),"mode",preferences.getString("networkMode","external"),"currentConfig",activeConfig,"externalConfig",J.obj("proxy",preferences.getString("proxy",""),"requireExternalVpn",preferences.getBoolean("requireExternalVpn",true)),"baseline",NetworkChanges.hash(profile));
        EnvironmentSpecRuntime.requireIdentity(profile,expected);return result;
      });
      JSONObject pending=metadata.optJSONObject("pending");NetworkCatalog.put(item,"uiMetadata",metadata);NetworkCatalog.put(item,"config",metadata.optJSONObject("currentConfig"));NetworkCatalog.put(item,"pendingNetwork",pending.length()>0);NetworkCatalog.put(item,"pendingAction",pending.optString("action"));NetworkCatalog.put(item,"pendingConfig",pending.optJSONObject("config"));
    }catch(Exception unavailable){NetworkCatalog.put(item,"uiMetadata",J.obj("available",false,"environmentId",row.optString("environmentId"),"generation",row.optLong("generation")));}
  }}
  void fetch(){if(closed||reading||SystemClock.elapsedRealtime()-lastRead<1800)return;reading=true;lastRead=SystemClock.elapsedRealtime();background(()->{NetworkCatalog next=new NetworkCatalog(a);JSONArray list=WindowNetworkState.windows(a);readUiMetadata(a,list);main.post(()->{reading=false;if(closed)return;catalog=next;windows=list;if(root!=null&&root.getParent()==host)render();if(afterRead!=null){Runnable done=afterRead;afterRead=null;done.run();}});});}
  void reload(){lastRead=0;fetch();}
  void close(){closed=true;reader.shutdownNow();main.removeCallbacksAndMessages(null);}
  WindowNetworkState state(JSONObject item){JSONObject row=item.optJSONObject("row"),stored=item.optJSONObject("runtime"),runtime=stored==null?new JSONObject():J.parse(stored.toString());boolean live=item.optBoolean("live");if(a instanceof MainActivity){MainActivity chat=(MainActivity)a;if(chat.session!=null&&row.optInt("slot")==Profiles.slot(a)&&row.optString("environmentId").equals(chat.session.environmentId)&&row.optLong("generation")==chat.session.environmentGeneration){runtime=WindowNetworkState.live(chat.session,NativeNetwork.get(chat));live=true;}}JSONObject metadata=item.optJSONObject("uiMetadata");if(metadata!=null&&metadata.optBoolean("available")&&row.optString("environmentId").equals(metadata.optString("environmentId"))&&row.optLong("generation")==metadata.optLong("generation")){NetworkCatalog.put(runtime,"uiDesiredRevision",metadata.optLong("desiredRevision"));NetworkCatalog.put(runtime,"uiAppliedRevision",metadata.optLong("appliedRevision"));}NetworkCatalog.put(runtime,"uiLive",live);return new WindowNetworkState(a,row,item.optJSONObject("config"),runtime,live,System.currentTimeMillis());}
  void render(){if(box==null)return;StringBuilder key=new StringBuilder(tab+"|"+filter+"|"+focus+"|");if(catalog!=null){key.append(catalog.readError()).append(catalog.data.toString());for(int i=0;i<windows.length();i++){JSONObject item=windows.optJSONObject(i);WindowNetworkState s=state(item);key.append(s.name).append(s.state).append(s.connected).append(setupOnly(s,item)).append(s.mainline()).append(windowSubline(s)).append(NativeNetwork.hash(s.config.toString())).append(metadataSummary(item)).append(pendingSummary(item)).append(s.runtime.optLong("appliedRevision"));}}if(key.toString().equals(lastRendered)&&!focusPending)return;lastRendered=key.toString();boolean locate=focusPending;int y=scroll.getScrollY();filterButton.setVisibility(tab==0&&filter!=0?View.VISIBLE:View.GONE);filterButton.setText((filter==1?"已连接":"待连接 / 未配置")+" · 清除筛选");filterButton.setContentDescription((filter==1?"已连接":"待连接或未配置")+"，清除网络筛选");updatePageSummary();tabHost.removeAllViews();tabHost.addView(NetworkWorkspaceStyle.tabs(a,tab,this::select));box.removeAllViews();if(catalog==null){TextView t=NetworkWorkspaceStyle.text(a,"正在读取窗口网络…",13,ReferenceUi.MUTED,false);box.addView(t);return;}if(!catalog.readError().isEmpty()){empty("网络库暂时无法读取",catalog.readError());box.addView(ReferenceUi.link(a,"重新读取",this::reload),new LinearLayout.LayoutParams(-1,dp(48)));if(tab==0)renderWindows();}else if(tab==0)renderWindows();else if(tab==1)renderSubscriptions();else renderExits();scroll.post(()->{if(!locate)scroll.scrollTo(0,y);});}
  void focus(int slot){focus=slot;focusPending=true;filter=0;tab=0;}
  void updatePageSummary(){
    if(pageSummary==null)return;
    if(catalog==null){pageSummary.setText("正在读取网络信息");return;}
    if(!catalog.readError().isEmpty()){pageSummary.setText("网络库暂时不可用");return;}
    if(tab==0){
      int count=0,connected=0;
      for(int i=0;i<windows.length();i++){WindowNetworkState s=state(windows.optJSONObject(i));if(matches(s))count++;if(s.connected)connected++;}
      pageSummary.setText(filter==0?windows.length()+" 个环境 · "+connected+" 个已连接":count+" 个筛选结果 · 共 "+windows.length()+" 个环境");
    }else if(tab==1)pageSummary.setText(catalog.subscriptions(NetworkCatalog.ENTRY).length()+" 个入口订阅");
    else pageSummary.setText(catalog.subscriptions(NetworkCatalog.EXIT).length()+" 个出口订阅 · "+catalog.exits().length()+" 个固定出口");
  }
  void renderWindows(){
    LinearLayout group=DesignUi.column(a);int count=0;
    for(int i=0;i<windows.length();i++){
      JSONObject item=windows.optJSONObject(i);WindowNetworkState s=state(item);if(!matches(s))continue;
      TextView name=NetworkWorkspaceStyle.text(a,s.name,16,ReferenceUi.TEXT,true);name.setMaxLines(2);name.setEllipsize(android.text.TextUtils.TruncateAt.END);
      String connectionLabel=s.connected?"已连接":item.optBoolean("pendingNetwork")?"等待应用":"未运行".equals(s.state)?"未连接":s.state;
      TextView status=NetworkWorkspaceStyle.status(a,connectionLabel,s.color());status.setContentDescription("网络状态："+connectionLabel);
      LinearLayout details=DesignUi.column(a);
      boolean setup=setupOnly(s,item);
      if(setup){
        TextView hint=NetworkWorkspaceStyle.text(a,"选择连接方式",13,ReferenceUi.MUTED,false);details.addView(hint);
      }else{
        TextView line=NetworkWorkspaceStyle.text(a,compactWindowLine(s),12,s.connected?ReferenceUi.TEXT:ReferenceUi.MUTED,false);line.setLineSpacing(dp(2),1);line.setContentDescription(s.mainline());details.addView(line);
        TextView routeLabel=NetworkWorkspaceStyle.text(a,windowSubline(s),12,ReferenceUi.MUTED,false);routeLabel.setLineSpacing(dp(2),1);routeLabel.setPadding(0,dp(3),0,0);details.addView(routeLabel);
      }
      LinearLayout actions=DesignUi.row(a);actions.setGravity(Gravity.END|Gravity.CENTER_VERTICAL);
      Button edit=NetworkWorkspaceStyle.rowAction(a,setup?"配置":"编辑",()->edit(item));edit.setContentDescription("编辑网络 · "+s.name);
      actions.addView(edit,new LinearLayout.LayoutParams(DesignUi.actionWidth(edit,64),-2));
      Button more=ReferenceUi.more(a,()->more(item));more.setContentDescription(s.name+"的更多网络操作");
      actions.addView(more,new LinearLayout.LayoutParams(dp(48),dp(48)));
      WindowRow row=new WindowRow(name,status,details,actions);
      JSONObject running=runningConfiguration(s);
      if(running!=null&&"internal".equals(running.optString("mode")))runningRoute(row,running);
      if(item.optBoolean("pendingNetwork")){
        TextView pending=NetworkWorkspaceStyle.text(a,"等待应用 · "+pendingSummary(item),12,ReferenceUi.ORANGE,false);
        pending.setLineSpacing(dp(2),1);pending.setPadding(dp(10),dp(8),dp(10),dp(8));
        pending.setBackground(DesignUi.surface(a,(ReferenceUi.ORANGE&0x00ffffff)|0x10000000,12,Color.TRANSPARENT));
        LinearLayout.LayoutParams saved=new LinearLayout.LayoutParams(-1,-2);saved.topMargin=dp(8);row.addView(pending,saved);
      }
      row.setBackground(NetworkWorkspaceStyle.card(a,s.slot==focus));
      row.setOnClickListener(v->details(item));row.setFocusable(true);
      String description=s.name+"，"+connectionLabel+"，"+s.mainline()+"，"+windowSubline(s);
      if(running!=null&&"internal".equals(running.optString("mode")))description+="，入口："+displayEntry(running)+"，固定出口："+displayExit(running)+"，目的地：ChatGPT";
      if(item.optBoolean("pendingNetwork"))description+="，等待应用："+pendingSummary(item);
      row.setContentDescription(description+"，查看窗口详情");
      LinearLayout.LayoutParams card=new LinearLayout.LayoutParams(-1,-2);if(count>0)card.topMargin=dp(10);group.addView(row,card);count++;
      if(s.slot==focus){
        if(focusPending){focusPending=false;row.post(()->scroll.smoothScrollTo(0,group.getTop()+row.getTop()));}
      }
    }
    if(count==0)empty("没有匹配的窗口",filter==0?"创建环境后会在这里显示网络。":"调整筛选即可查看其他窗口。");
    else box.addView(group,new LinearLayout.LayoutParams(-1,-2));
  }
  /** Only replace empty placeholders; observations and pending work keep their full detail. */
  static boolean setupOnly(WindowNetworkState state,JSONObject item){
    JSONObject meta=metadata(item);
    return "未配置".equals(state.state)&&!state.connected&&state.ip.isEmpty()&&state.region.isEmpty()
      &&"延迟未测".equals(state.latency)&&runningConfiguration(state)==null&&!item.optBoolean("pendingNetwork")
      &&meta.optBoolean("available")&&!state.environmentId.isEmpty()&&state.environmentId.equals(meta.optString("environmentId"))
      &&state.environmentGeneration==meta.optLong("generation",-1);
  }
  static String compactWindowLine(WindowNetworkState state){
    String address=state.ip.isEmpty()?"IP 待核验":state.connected?state.ip:"上次 "+state.ip;
    String latency="延迟未测".equals(state.latency)?"未测速":state.latency;
    return (state.region.isEmpty()?"":state.region+" · ")+address+" · "+latency;
  }
  void runningRoute(LinearLayout row,JSONObject running){
    LinearLayout route=DesignUi.column(a);route.setPadding(dp(12),dp(8),dp(12),dp(8));route.setBackground(DesignUi.surface(a,DesignUi.FIELD,14,Color.TRANSPARENT));
    String[] labels={"入口","固定出口","目的地"},values={displayEntry(running),displayExit(running),"ChatGPT"};
    for(int i=0;i<labels.length;i++){
      LinearLayout stage=DesignUi.row(a);stage.setGravity(Gravity.TOP);stage.setPadding(0,dp(2),0,dp(2));
      TextView label=NetworkWorkspaceStyle.text(a,labels[i],11,ReferenceUi.MUTED,false);label.setSingleLine(true);
      int labelWidth=Math.max(dp(58),(int)Math.ceil(label.getPaint().measureText(labels[i]))+dp(8));stage.addView(label,new LinearLayout.LayoutParams(labelWidth,-2));
      TextView value=NetworkWorkspaceStyle.text(a,values[i],12,ReferenceUi.TEXT,false);value.setLineSpacing(dp(2),1);stage.addView(value,new LinearLayout.LayoutParams(0,-2,1));route.addView(stage);
    }
    LinearLayout.LayoutParams steps=new LinearLayout.LayoutParams(-1,-2);steps.topMargin=dp(8);row.addView(route,steps);
  }
  /** Compact at normal widths; full-width details and separate actions at large font sizes. */
  final class WindowRow extends LinearLayout {
    final LinearLayout head,body,details,actions;final TextView name,status;
    Boolean stackedActions,stackedHeading;
    WindowRow(TextView name,TextView status,LinearLayout details,LinearLayout actions){
      super(a);this.name=name;this.status=status;this.details=details;this.actions=actions;
      setOrientation(VERTICAL);setPadding(dp(16),dp(13),dp(12),dp(12));
      head=DesignUi.row(a);head.addView(name,new LinearLayout.LayoutParams(0,-2,1));
      LinearLayout.LayoutParams badge=new LinearLayout.LayoutParams(-2,-2);badge.leftMargin=dp(8);head.addView(status,badge);addView(head);
      body=DesignUi.row(a);body.setGravity(Gravity.CENTER_VERTICAL);body.addView(details,new LinearLayout.LayoutParams(0,-2,1));body.addView(actions,new LinearLayout.LayoutParams(-2,-2));
      LinearLayout.LayoutParams content=new LinearLayout.LayoutParams(-1,-2);content.topMargin=dp(4);addView(body,content);
    }
    @Override protected void onMeasure(int widthSpec,int heightSpec){
      int available=MeasureSpec.getMode(widthSpec)==MeasureSpec.UNSPECIFIED?Integer.MAX_VALUE:MeasureSpec.getSize(widthSpec)-getPaddingLeft()-getPaddingRight();
      float fontScale=getResources().getConfiguration().fontScale;
      boolean stackActions=available<=dp(304)||fontScale>=1.35f,stackHeading=available<dp(250)||fontScale>=1.4f;
      if(stackedActions==null||stackedActions!=stackActions){
        stackedActions=stackActions;body.setOrientation(stackActions?VERTICAL:HORIZONTAL);
        details.setLayoutParams(new LinearLayout.LayoutParams(stackActions?-1:0,-2,stackActions?0:1));
        LinearLayout.LayoutParams buttons=new LinearLayout.LayoutParams(-2,-2);buttons.gravity=stackActions?Gravity.END:Gravity.TOP;
        if(stackActions)buttons.topMargin=dp(3);else buttons.leftMargin=dp(8);actions.setLayoutParams(buttons);
      }
      if(stackedHeading==null||stackedHeading!=stackHeading){
        stackedHeading=stackHeading;head.setOrientation(stackHeading?VERTICAL:HORIZONTAL);head.setGravity(stackHeading?Gravity.START:Gravity.CENTER_VERTICAL);
        name.setMaxLines(stackHeading?3:2);name.setLayoutParams(new LinearLayout.LayoutParams(stackHeading?-1:0,-2,stackHeading?0:1));
        LinearLayout.LayoutParams badge=new LinearLayout.LayoutParams(-2,-2);if(stackHeading)badge.topMargin=dp(5);else badge.leftMargin=dp(8);status.setLayoutParams(badge);
      }
      super.onMeasure(widthSpec,heightSpec);
    }
  }
  String windowSubline(WindowNetworkState state){
    JSONObject running=runningConfiguration(state);if(running==null)return "未运行".equals(state.state)?"当前没有运行线路":"运行线路待确认";
    if(!"internal".equals(running.optString("mode")))return "运行线路 · "+externalName(running);
    return "运行线路 · "+entryModeLabel(running.optString("entryMode"))+(running.optBoolean("verified")?" · 出口已核验":" · 出口核验未完成");
  }
  static String entryModeLabel(String mode){return NetworkOptimizationPolicy.label(mode);}
  static JSONObject runningConfiguration(WindowNetworkState state){JSONObject value=state.runtime.optJSONObject("runningConfiguration");long at=state.runtime.optLong("at");return state.runtime.optBoolean("uiLive")&&at>0&&state.now>=at-60000&&state.now-at<45000&&value!=null&&!state.environmentId.isEmpty()&&state.environmentId.equals(value.optString("environmentId"))&&state.environmentGeneration==value.optLong("generation",-1)&&!value.optString("mode").isEmpty()&&!value.optString("configurationFingerprint").isEmpty()?value:null;}
  static String displayEntry(JSONObject config){String entry=config.optString("entry");return entry.isEmpty()?"入口待确认":nodeName(entry);}
  static String displayExit(JSONObject config){String exit=config.optString("exitName");if("subscription".equals(config.optString("exitSource")))exit=config.optString("exitNodeName",exit);if(exit.isEmpty())exit=config.optString("exitHost");return exit.isEmpty()?"固定出口待确认":nodeName(exit);}
  static String externalName(JSONObject config){Object proxy=config.opt("proxy");return Boolean.TRUE.equals(proxy)||proxy instanceof String&&!((String)proxy).isEmpty()?"应用专用代理":"手机网络 / VPN";}
  static JSONObject metadata(JSONObject item){JSONObject value=item==null?null:item.optJSONObject("uiMetadata");return value==null?new JSONObject():value;}
  static String version(long value){return value>0?"v"+value:"待确认";}
  static String metadataSummary(JSONObject item){JSONObject meta=metadata(item);if(!meta.optBoolean("available"))return "配置版本暂时无法读取";return "已保存 "+version(meta.optLong("desiredRevision"))+" · 网页配置已确认 "+version(meta.optLong("appliedRevision"));}
  static String pendingCandidateId(JSONObject pending,JSONObject marker){return marker==null?pending.length()==0?"":"legacy:"+NativeNetwork.hash(pending.toString()):marker.optString("id");}
  static String pendingSummary(JSONObject item){JSONObject config=item.optJSONObject("pendingConfig");if(!metadata(item).optBoolean("pendingReady",true))return "保存状态待恢复";if(config==null)return "配置待确认";return "external".equals(item.optString("pendingAction"))?externalName(config):entryModeLabel(config.optString("entryMode"))+" · "+displayEntry(config)+" → "+displayExit(config);}
  JSONObject windowItem(int slot){for(int i=0;i<windows.length();i++){JSONObject item=windows.optJSONObject(i);if(item!=null&&item.optJSONObject("row").optInt("slot",-1)==slot)return item;}return null;}
  boolean matches(WindowNetworkState s){return filter==0||filter==1&&s.connected||filter==2&&!s.connected;}
  void filters(){ReferenceUi.Modal d=new ReferenceUi.Modal(a,"筛选环境").asSheet();String[] choices={"全部环境","已连接","待连接 / 未配置"};for(int i=0;i<choices.length;i++){final int n=i;choice(d,choices[i],"",filter==i,()->{filter=n;focus=-1;d.dismiss();scroll.scrollTo(0,0);render();});}d.show();}
  void empty(String title,String detail){NetworkWorkspaceStyle.empty(box,title,detail);}
  void listHeader(String name,Runnable add){LinearLayout head=DesignUi.row(a);head.setPadding(dp(2),0,0,0);TextView title=NetworkWorkspaceStyle.text(a,name,17,ReferenceUi.TEXT,true);if(Build.VERSION.SDK_INT>=28)title.setAccessibilityHeading(true);head.addView(title,new LinearLayout.LayoutParams(0,-2,1));Button create=NetworkWorkspaceStyle.smallAction(a,"＋ 添加",add);create.setContentDescription("添加"+name);head.addView(create,new LinearLayout.LayoutParams(-2,-2));LinearLayout.LayoutParams section=new LinearLayout.LayoutParams(-1,-2);section.topMargin=box.getChildCount()==0?0:dp(8);section.bottomMargin=dp(6);box.addView(head,section);}
  void renderSubscriptions(){renderSources(NetworkCatalog.ENTRY);}
  void renderExits(){
    renderSources(NetworkCatalog.EXIT);
    listHeader("手动固定出口",()->exitForm(null));
    JSONArray all=catalog.exits();
    for(int i=0;i<all.length();i++){
      JSONObject e=all.optJSONObject(i);LinearLayout row=NetworkWorkspaceStyle.sourceCard(a);
      TextView name=NetworkWorkspaceStyle.text(a,e.optString("name"),16,ReferenceUi.TEXT,true);name.setMaxLines(2);name.setEllipsize(android.text.TextUtils.TruncateAt.END);LinearLayout head=DesignUi.row(a);head.addView(name,new LinearLayout.LayoutParams(0,-2,1));Button more=ReferenceUi.more(a,()->exitDetail(e));more.setContentDescription(e.optString("name")+"的固定出口详情");head.addView(more,new LinearLayout.LayoutParams(dp(48),dp(48)));row.addView(head);
      String ip=e.optString("verifiedIp");row.addView(NetworkWorkspaceStyle.secondary(a,ip.isEmpty()?"IP 待核验":ip));
      row.addView(NetworkWorkspaceStyle.secondary(a,(ip.isEmpty()?"待核验":"上次已核验")+" · "+uses(e.optString("id"))+" 个窗口使用"));
      libraryCard(row,()->exitDetail(e),e.optString("name")+"，查看固定出口详情");ReferenceUi.add(box,row);
    }
    if(all.length()==0)empty("还没有手动出口","添加 SOCKS5 出口，按环境单独选择。");
  }
  void renderSources(String role){
    listHeader(roleName(role)+"订阅",()->subscriptionForm(role,null,null));
    JSONArray all=catalog.subscriptions(role);
    for(int i=0;i<all.length();i++){
      JSONObject source=all.optJSONObject(i);LinearLayout card=NetworkWorkspaceStyle.sourceCard(a);LinearLayout head=DesignUi.row(a);
      TextView name=NetworkWorkspaceStyle.text(a,source.optString("name"),16,ReferenceUi.TEXT,true);name.setMaxLines(2);name.setEllipsize(android.text.TextUtils.TruncateAt.END);
      head.addView(name,new LinearLayout.LayoutParams(0,-2,1));
      Button more=ReferenceUi.more(a,()->subscriptionDetail(source));more.setContentDescription(source.optString("name")+"的"+roleName(role)+"详情");head.addView(more,new LinearLayout.LayoutParams(dp(48),dp(48)));card.addView(head);
      card.addView(NetworkWorkspaceStyle.secondary(a,sourceSummary(source,role)));
      card.addView(NetworkWorkspaceStyle.secondary(a,"更新于 "+updated(source.optLong("lastSuccessAt",source.optLong("updatedAt")))));
      libraryCard(card,()->subscriptionDetail(source),source.optString("name")+"，查看"+roleName(role)+(NetworkCatalog.local(source)?"本地节点":"订阅详情"));ReferenceUi.add(box,card);
    }
    if(all.length()==0&&NetworkCatalog.ENTRY.equals(role))empty("还没有订阅","添加 Clash / Mihomo 订阅地址。");
    if(all.length()==0&&NetworkCatalog.EXIT.equals(role))empty("还没有订阅","添加 SOCKS5 节点订阅，为环境选择出口。");
  }
  void libraryCard(View card,Runnable open,String description){card.setBackground(NetworkWorkspaceStyle.card(a,false));card.setOnClickListener(v->open.run());card.setFocusable(true);card.setContentDescription(description);}
  static String roleName(String role){return NetworkCatalog.EXIT.equals(role)?"出口":"入口";}
  static String nodeName(String name){return name.startsWith("Entry|")?name.substring(6):name.startsWith("Exit|")?name.substring(5):name;}
  int selectableExitNodes(JSONObject source){
    int count=0;Set<String> names=new HashSet<>(NetworkSourceSelection.names(source));JSONArray details=source.optJSONArray("nodeDetails");
    if(details!=null)for(int i=0;i<details.length();i++){JSONObject node=details.optJSONObject(i);if(node!=null&&names.contains(node.optString("name"))&&NetworkSourceSelection.socks5(node)&&!node.optString("configFingerprint").isEmpty())count++;}return count;
  }
  String sourceSummary(JSONObject source,String role){
    int n=NetworkSourceSelection.names(source).size(),usable=NetworkCatalog.EXIT.equals(role)?selectableExitNodes(source):n;
    String count=NetworkCatalog.EXIT.equals(role)?n+" 个节点 · "+usable+" 个 SOCKS5":n+" 个入口";
    if(NetworkCatalog.local(source))return "本地分享 · "+count;
    if(source.optBoolean("updating"))return (System.currentTimeMillis()-source.optLong("lastAttemptAt")<120000?"正在更新":"上次更新未完成")+" · "+count;
    if(source.optBoolean("stale"))return (source.optString("lastError").isEmpty()?"地址已修改":"更新失败 · 地址已修改")+" · 上次 "+count;
    if(!source.optString("lastError").isEmpty())return "更新失败 · "+(n>0?"保留 "+count:"尚无可用节点");
    return n==0?"尚未读取":usable==0?"暂不可作为出口 · "+n+" 个节点":"正常 · "+count;
  }
  boolean references(JSONObject config,String role,String id){
    if(config==null)return false;String field=NetworkCatalog.EXIT.equals(role)?"exitSubscriptionId":"entrySubscriptionId";
    if(NetworkCatalog.EXIT.equals(role)&&!"subscription".equals(config.optString("exitSource")))return false;
    String ref=config.optString(field);if(ref.isEmpty()&&NetworkCatalog.ENTRY.equals(role))ref=NativeNetwork.hash(config.optString("subscriptionUrl"));
    JSONObject source=catalog.subscription(role,ref);return source!=null&&id.equals(source.optString("id"));
  }
  boolean manualReference(JSONObject config,String id){
    if(config==null||"subscription".equals(config.optString("exitSource")))return false;
    JSONObject row=catalog.exit(config.optString("exitLibraryId",NetworkCatalog.exitId(config)));return row!=null&&id.equals(row.optString("id"));
  }
  int uses(String id){return referenceCount(null,id);}
  int sourceUses(String role,String id){return referenceCount(role,id);}
  int referenceCount(String role,String id){
    int n=0;for(int i=0;i<windows.length();i++){
      JSONObject item=windows.optJSONObject(i),config=item.optJSONObject("config"),pending=item.optJSONObject("pendingConfig");
      if(role==null?(manualReference(config,id)||manualReference(pending,id)):(references(config,role,id)||references(pending,role,id)))n++;
    }return n;
  }
  String updated(long at){if(at<=0)return "未记录";Calendar now=Calendar.getInstance(),date=Calendar.getInstance();date.setTimeInMillis(at);boolean today=now.get(Calendar.YEAR)==date.get(Calendar.YEAR)&&now.get(Calendar.DAY_OF_YEAR)==date.get(Calendar.DAY_OF_YEAR);return new java.text.SimpleDateFormat(today?"'今天' HH:mm":"MM-dd HH:mm",Locale.getDefault()).format(new Date(at));}
  void more(JSONObject item){WindowNetworkState s=state(item);ReferenceUi.Modal d=new ReferenceUi.Modal(a,s.name).asSheet();String[] labels={"测速","分享整条线路","窗口详情","重新连接","网络方式","打开会话"};Runnable[] actions={()->operate(s,"measure"),()->NetworkShareUi.route(a,s),()->details(item),()->operate(s,"reconnect"),()->networkMode(s),()->openChat(s.slot)};for(int i=0;i<labels.length;i++){final int n=i;ReferenceUi.menuAction(d,labels[i],()->{d.dismiss();actions[n].run();});}d.show();}
  void openChat(int slot){if(a instanceof MainActivity&&slot==Profiles.slot(a)){((MainActivity)a).hub.select(AppHub.CHAT);return;}a.startActivity(EnvironmentOverviewUi.opening(a,slot));}
  void details(JSONObject item){
    WindowNetworkState s=state(item);ReferenceUi.Modal d=new ReferenceUi.Modal(a,"窗口详情 · "+s.name);JSONObject running=runningConfiguration(s);
    field(d,"网络状态",s.state);field(d,"运行线路",windowSubline(s));field(d,"出口地区",s.region.isEmpty()?"未标注":s.region);field(d,"出口 IP",s.ip.isEmpty()?"未核验":s.ip);field(d,s.internal?"完整线路延迟":"连接响应",s.latency);
    if(running!=null&&"internal".equals(running.optString("mode"))){JSONObject site=s.runtime.optJSONObject("website");field(d,"ChatGPT 网站响应",site!=null&&running.optString("entry").equals(site.optString("entry"))?WebsiteProbe.line(site,System.currentTimeMillis()):"网站响应未测");field(d,"运行入口订阅",running.optString("subscriptionName","待确认"));field(d,"运行入口选择",entryModeLabel(running.optString("entryMode")));field(d,"运行入口",displayEntry(running));field(d,"运行固定出口",displayExit(running));field(d,"出口核验",running.optBoolean("verified")?updated(s.runtime.optLong("verifiedAt")):"核验未完成");}
    field(d,"配置版本",metadataSummary(item));
    if(item.optBoolean("pendingNetwork")){
      field(d,"待应用配置",pendingSummary(item));d.note("这份设置已保存，等待安全时机应用；上方显示当前运行线路。");final boolean[] cancelling={false};final Button[] cancel={null};TextView cancelError=ReferenceUi.text(a,"",12,ReferenceUi.RED,false);cancelError.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);cancelError.setVisibility(View.GONE);
      DesignUi.action(d.body,"取消待应用设置",false,()->{if(cancelling[0])return;cancelling[0]=true;cancel[0].setEnabled(false);cancel[0].setText("正在取消…");NetworkBridge.run(a,s.slot,"cancelPending",J.obj("guardCandidateId",metadata(item).optString("candidateId")),null,identity(s),(ok,message,snapshot)->{if(!active())return;cancelling[0]=false;reload();if(!d.isShowing())return;cancelError.setVisibility(View.VISIBLE);boolean current=diagnosticWindowCurrent(s);cancelError.setText(current?message==null||message.isEmpty()?"结果待确认，请刷新网络状态。":message:"环境已变化，请重新打开网络设置。");cancelError.setTextColor(current&&ok?ReferenceUi.MUTED:ReferenceUi.RED);cancel[0].setEnabled(current&&!ok);cancel[0].setText(current&&ok?"已取消待应用设置":current?"取消待应用设置":"环境已变化");d.resize();});});cancel[0]=(Button)d.body.getChildAt(d.body.getChildCount()-1);d.body.addView(cancelError);
    }
    if(!s.runtime.optString("issue").isEmpty())d.note(s.runtime.optString("issue"));DesignUi.action(d.body,"查看耗时诊断",false,()->{d.dismiss();diagnostics(item);});d.buttons("关闭",d::dismiss,"编辑网络",()->{d.dismiss();edit(item);});d.show();
  }
  void diagnostics(JSONObject item){
    WindowNetworkState window=state(item);String[] text={ConnectionTrace.windowDiagnostics(a,window)};
    ReferenceUi.Modal d=new ReferenceUi.Modal(a,"耗时诊断 · "+window.name);
    TextView content=ReferenceUi.text(a,text[0],13,ReferenceUi.TEXT,false);content.setTextIsSelectable(true);d.body.addView(content);
    d.buttons("返回",()->{d.dismiss();details(item);},"复制诊断",()->{
      ClipboardManager clipboard=(ClipboardManager)a.getSystemService(Context.CLIPBOARD_SERVICE);
      if(clipboard!=null){clipboard.setPrimaryClip(ClipData.newPlainText("窗口耗时诊断",diagnosticWindowCurrent(window)?text[0]:"环境已变化，诊断不可用"));d.primary().setText("已复制");}
    });d.show();d.primary().setEnabled(false);
    ConnectionTrace.windowDiagnosticsAsync(a,window,value->{
      if(!active()||!d.isShowing())return;
      text[0]=diagnosticWindowCurrent(window)?value:"环境已变化，诊断不可用";content.setText(text[0]);d.primary().setEnabled(true);d.resize();
    });
  }
  boolean diagnosticWindowCurrent(WindowNetworkState window){
    for(int i=0;i<windows.length();i++){
      JSONObject item=windows.optJSONObject(i),row=item==null?null:item.optJSONObject("row");
      if(row!=null&&row.optInt("slot",-1)==window.slot)return !window.environmentId.isEmpty()
        &&window.environmentId.equals(row.optString("environmentId"))&&window.environmentGeneration==row.optLong("generation")
        &&row.optBoolean("created")&&!row.optBoolean("deleting")&&!row.optBoolean("resetting");
    }return false;
  }
  void field(ReferenceUi.Modal d,String name,String value){DesignUi.field(d.body,name,value);}
  void choice(ReferenceUi.Modal d,String name,String detail,boolean selected,Runnable run){LinearLayout row=DesignUi.row(a);row.setPadding(dp(12),dp(9),dp(12),dp(9));row.setMinimumHeight(dp(58));row.setBackground(ReferenceUi.surface(a,selected?0xfff7faff:ReferenceUi.WHITE,14,selected?0xff94b8ff:ReferenceUi.LINE));TextView mark=ReferenceUi.text(a,selected?"◉":"○",20,selected?ReferenceUi.BLUE:ReferenceUi.MUTED,false);row.addView(mark,new LinearLayout.LayoutParams(dp(30),-2));LinearLayout labels=DesignUi.column(a);TextView title=ReferenceUi.text(a,name,15,ReferenceUi.TEXT,true);title.setMaxLines(3);labels.addView(title);if(!detail.isEmpty()){TextView explanation=ReferenceUi.secondary(a,detail);explanation.setSingleLine(false);labels.addView(explanation);}row.addView(labels,new LinearLayout.LayoutParams(0,-2,1));row.setOnClickListener(v->run.run());row.setFocusable(true);row.setContentDescription(name+(selected?"，已选择":""));ReferenceUi.add(d.body,row);}
  void routeRow(ReferenceUi.Modal d,String key,String value,Runnable select){LinearLayout row=DesignUi.row(a);row.setMinimumHeight(dp(66));LinearLayout labels=DesignUi.column(a);labels.addView(ReferenceUi.text(a,key,13,ReferenceUi.MUTED,false));TextView title=ReferenceUi.text(a,value,15,ReferenceUi.TEXT,true);title.setMaxLines(3);title.setPadding(0,dp(4),0,0);labels.addView(title);row.addView(labels,new LinearLayout.LayoutParams(0,-2,1));ImageView arrow=new ImageView(a);arrow.setImageDrawable(new Ui.Icon("chevron-right",ReferenceUi.MUTED));row.addView(arrow,new LinearLayout.LayoutParams(dp(18),dp(22)));row.setOnClickListener(v->select.run());row.setFocusable(true);row.setBackground(Ui.ripple(a,Color.TRANSPARENT,0));d.body.addView(row);View line=new View(a);line.setBackgroundColor(0xffeef2f7);d.body.addView(line,new LinearLayout.LayoutParams(-1,dp(1)));}
  static final class EditorSession {final ReferenceUi.Modal dialog;final NetworkDraft draft;final Runnable refresh;JSONObject operationResult;boolean completed;EditorSession(ReferenceUi.Modal dialog,NetworkDraft draft,Runnable refresh){this.dialog=dialog;this.draft=draft;this.refresh=refresh;}}
  boolean editorReady(JSONObject item){JSONObject meta=metadata(item),row=item==null?null:item.optJSONObject("row");boolean identity=row!=null&&!row.optString("environmentId").isEmpty()&&row.optString("environmentId").equals(meta.optString("environmentId"))&&row.optLong("generation")==meta.optLong("generation",-1);if(identity&&meta.optBoolean("available")&&meta.optBoolean("pendingReady",true)&&!meta.optString("baseline").isEmpty()&&diagnosticWindowCurrent(state(item)))return true;ReferenceUi.Modal d=new ReferenceUi.Modal(a,"网络设置暂不可编辑");d.note(identity&&meta.optBoolean("available")?"上次保存尚待恢复，请刷新状态后再试。":"配置暂时无法读取或环境已变化，请刷新状态后再试。");d.buttons("关闭",d::dismiss,"刷新状态",()->{d.dismiss();if(row!=null)refreshEditor(state(item));else reload();});d.show();return false;}
  void refreshEditor(WindowNetworkState expected){afterRead=()->{if(!active()||!diagnosticWindowCurrent(expected))return;JSONObject fresh=windowItem(expected.slot);if(fresh!=null)edit(fresh);};reload();}
  static String editingContext(JSONObject item,boolean pending){return (pending?"正在编辑待应用配置":"正在编辑当前已保存配置")+"\n"+metadataSummary(item)+(!pending&&item.optBoolean("pendingNetwork")?"\n另有待应用配置，保存后将替换它。":"");}
  static EnvironmentSpec.Identity identity(WindowNetworkState expected){return new EnvironmentSpec.Identity(expected.slot,(int)expected.environmentGeneration,expected.environmentId);}
  static JSONObject operationResult(WindowNetworkState expected,JSONObject snapshot){JSONObject result=snapshot==null?null:snapshot.optJSONObject("operationResult");return result!=null&&!expected.environmentId.isEmpty()&&expected.environmentId.equals(result.optString("environmentId"))&&expected.environmentGeneration==result.optLong("generation",-1)?result:null;}
  static String operationText(JSONObject result,String message){
    if(result==null)return "操作结果待确认"+(message==null||message.isEmpty()?"":"\n"+message);
    String save=result.optString("saveState"),application=result.optString("applicationState"),scope=result.optString("scope"),title;
    if("uncertain".equals(save))title="保存结果待确认";
    else if("failed".equals(save))title="未能保存";
    else if("superseded".equals(save)||"superseded".equals(application))title="已由较新的设置替换";
    else if("cancelled".equals(application))title="待应用设置已取消";
    else if("pending".equals(application))title="等待应用";
    else if("applying".equals(application))title="连接中";
    else if("applied".equals(application))title="session".equals(scope)||"core".equals(scope)?"已应用":"等待应用";
    else if("failed".equals(application))title="verified".equals(result.optString("rollbackState"))?"应用失败，仍使用原线路":"stopped".equals(result.optString("rollbackState"))?"应用失败，当前未连接":"应用失败，线路状态待确认";
    else if("saved-unconfirmed".equals(application))title="已保存 · 核验未完成";
    else title="saved".equals(save)?"已保存 · 应用状态待确认":"操作结果待确认";
    String versions="已保存 "+version(result.optLong("savedRevision"))+" · 已应用 "+version(result.optLong("appliedRevision"));String detail=result.optString("message");if(detail.isEmpty())detail=message==null?"":message;
    return title+(detail.isEmpty()||detail.equals(title)?"":"\n"+detail);
  }
  void editorResult(ReferenceUi.Modal d,TextView feedback,WindowNetworkState expected,boolean ok,String message,JSONObject snapshot,Runnable failed){
    if(!active()||!d.isShowing())return;JSONObject result=operationResult(expected,snapshot);boolean current=diagnosticWindowCurrent(expected),identityMismatch=snapshot!=null&&snapshot.optJSONObject("operationResult")!=null&&result==null;
    feedback.setText(current&&!identityMismatch?operationText(result,message):"环境已变化，请重新打开网络设置。");boolean saved=result!=null&&"saved".equals(result.optString("saveState"));feedback.setTextColor(current&&!identityMismatch&&result!=null&&(saved||"uncertain".equals(result.optString("saveState")))?("applied".equals(result.optString("applicationState"))&&saved?ReferenceUi.GREEN:ReferenceUi.ORANGE):ReferenceUi.RED);
    if(current&&!identityMismatch&&result!=null&&"failed".equals(result.optString("saveState"))){failed.run();}
    else if(current&&!identityMismatch&&result!=null&&result.optBoolean("retryAvailable"))d.buttons("关闭",d::dismiss,"重试",()->{
      d.primary().setEnabled(false);feedback.setText("正在重新应用…");
      NetworkBridge.run(a,expected.slot,"retryApplication",J.obj("guardCandidateId",result.optString("candidateId")),null,identity(expected),applicationDecision(expected),(again,text,state)->{if(!active())return;reload();editorResult(d,feedback,expected,again,text,state,failed);});
    });
    else d.buttons("关闭",d::dismiss,current&&!identityMismatch?"继续编辑":"",()->{d.dismiss();refreshEditor(expected);});
    d.resize();
  }
  NetworkBridge.Decision applicationDecision(WindowNetworkState expected){return (choice,select)->{
    if(!active()||!diagnosticWindowCurrent(expected))return;
    ReferenceUi.Modal decision=new ReferenceUi.Modal(a,"选择应用时间");
    decision.note("当前正在回复或处理文件，或任务状态暂未确认。立即切换可能中断当前任务。");
    decision.buttons("任务结束后自动应用",()->{decision.dismiss();select.accept(NetworkApplyCoordinator.DEFER);},"立即切换，可能中断当前任务",()->{decision.dismiss();select.accept(NetworkApplyCoordinator.IMMEDIATE);});decision.show();
  };}
  EditorSession edit(JSONObject item){if(catalog==null||!editorReady(item))return null;WindowNetworkState current=state(item);JSONObject meta=metadata(item),queued=meta.optJSONObject("pending");String action=queued.optString("action");if("external".equals(action)||action.isEmpty()&&!"internal".equals(meta.optString("mode"))){JSONObject external="external".equals(action)?queued.optJSONObject("config"):meta.optJSONObject("externalConfig");external(item,!external.optString("proxy").isEmpty());return null;}return editInternal(item);}
  EditorSession editInternal(JSONObject item){
    if(catalog==null||!editorReady(item))return null;WindowNetworkState state=state(item);JSONObject pending=metadata(item).optJSONObject("pending");
    NetworkDraft draft=new NetworkDraft(state.slot,"apply".equals(pending.optString("action"))?pending.optJSONObject("config"):state.config,catalog);
    if(!"apply".equals(pending.optString("action"))&&state.connected&&NetworkOptimizationPolicy.pooled(draft.mode)){
      JSONObject source=catalog.subscription(NetworkCatalog.ENTRY,draft.subscriptionId);String key=NetworkSourceSelection.fingerprint(source,state.entry);
      // A runtime name alone cannot adopt a replacement node with different credentials.
      if(!key.isEmpty()&&draft.entryPoolKeys.contains(key))draft.chooseEntry(state.entry,catalog);
    }
    ReferenceUi.Modal d=new ReferenceUi.Modal(a,"编辑网络 · "+state.name);final Runnable[] render={null};final boolean[] saving={false},preparing={false};
    EditorSession editor=new EditorSession(d,draft,()->render[0].run());TextView error=ReferenceUi.text(a,"",12,ReferenceUi.RED,false);error.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);TextView context=ReferenceUi.secondary(a,editingContext(item,"apply".equals(pending.optString("action"))));context.setSingleLine(false);
    render[0]=()->{
      draft.normalize(catalog);d.body.removeAllViews();d.body.addView(context);JSONObject source=catalog.subscription(NetworkCatalog.ENTRY,draft.subscriptionId),manual=catalog.exit(draft.exitId),exitSource=catalog.subscription(NetworkCatalog.EXIT,draft.exitSubscriptionId);
      routeRow(d,"入口订阅",source==null?"请选择订阅":source.optString("name"),()->{if(!saving[0]&&!preparing[0])selectSubscription(draft,render[0]);});
      String entrance=entryModeLabel(draft.mode)+(draft.entry.isEmpty()?("latency".equals(draft.mode)?" · 连接后优选":" · 待选择"):" · "+nodeName(draft.entry));
      routeRow(d,"入口选择",entrance,()->{if(!saving[0]&&!preparing[0])selectEntry(draft,render[0]);});
      String exit=!draft.exitSubscriptionId.isEmpty()?(exitSource==null?"出口订阅已删除":exitSource.optString("name")+" · "+(draft.exitNodeName.isEmpty()?"请选择节点":nodeName(draft.exitNodeName))):(manual==null?"请选择固定出口":manual.optString("name"));
      routeRow(d,"固定出口",exit,()->{if(!saving[0]&&!preparing[0])selectExit(draft,render[0]);});d.body.addView(error);d.resize();
    };
    d.buttons("取消",d::dismiss,"保存并应用",()->{
      if(saving[0]||preparing[0])return;final JSONObject candidate;
      try{candidate=draft.candidate(catalog);}catch(Exception invalid){error.setText(invalid.getMessage());error.setTextColor(ReferenceUi.RED);d.resize();return;}
      saving[0]=true;editor.completed=false;editor.operationResult=null;d.primary().setEnabled(false);d.primary().setText("正在保存…");((Button)d.footer.getChildAt(0)).setText("收起");
      for(int i=0;i<d.body.getChildCount();i++)d.body.getChildAt(i).setEnabled(false);
      error.setText("正在保存并应用，收起后操作仍会继续…");error.setTextColor(ReferenceUi.MUTED);d.resize();
      NetworkBridge.run(a,draft.slot,"apply",candidate,metadata(item).optString("baseline"),identity(state),applicationDecision(state),(ok,message,snapshot)->{
        if(!active())return;saving[0]=false;JSONObject receipt=operationResult(state,snapshot);editor.operationResult=receipt==null?null:J.parse(receipt.toString());editor.completed=true;reload();context.setText("本次保存结果");
        editorResult(d,error,state,ok,message,snapshot,()->{context.setText(editingContext(item,"apply".equals(pending.optString("action"))));d.primary().setEnabled(true);d.primary().setText("保存并应用");((Button)d.footer.getChildAt(0)).setText("取消");for(int i=0;i<d.body.getChildCount();i++)d.body.getChildAt(i).setEnabled(true);});
      });
    });render[0].run();d.show();prepareLegacySources(d,draft,error,preparing,render[0]);return editor;
  }
  boolean sourceNeedsRead(JSONObject source){
    if(source==null||source.optBoolean("stale"))return true;List<String> names=NetworkSourceSelection.names(source);if(names.isEmpty())return true;
    for(String name:names){JSONObject node=NetworkSourceSelection.byName(source,name);if(node==null||node.optInt("configFingerprintVersion")!=1||!node.optString("configFingerprint").matches("[0-9a-f]{64}")||node.optString("type").isEmpty())return true;}
    return !hasCurrentCacheMetadata(source);
  }
  static boolean hasCurrentCacheMetadata(JSONObject source){
    if(source==null||source.optBoolean("stale")||source.optLong("addressRevision")<=0||source.optLong("cacheAddressRevision")!=source.optLong("addressRevision"))return false;
    if(!source.optString("cacheSlot").isEmpty())return true;
    return NetworkCatalog.ENTRY.equals(source.optString("role",NetworkCatalog.ENTRY))&&source.optInt("owner",-1)>=0&&source.optString("url").equals(source.optString("cacheUrl",source.optString("url")));
  }
  void prepareLegacySources(ReferenceUi.Modal dialog,NetworkDraft draft,TextView error,boolean[] preparing,Runnable render){
    List<JSONObject> sources=new ArrayList<>();JSONObject entrance=catalog.subscription(NetworkCatalog.ENTRY,draft.subscriptionId),exit=catalog.subscription(NetworkCatalog.EXIT,draft.exitSubscriptionId);
    for(JSONObject source:new JSONObject[]{entrance,exit})if(source!=null&&!source.optBoolean("stale")&&sourceNeedsRead(source)&&hasCurrentCacheMetadata(source))sources.add(source);
    if(sources.isEmpty())return;preparing[0]=true;dialog.primary().setEnabled(false);dialog.primary().setText("正在读取…");error.setTextColor(ReferenceUi.MUTED);error.setText("正在准备已保存的节点，当前连接不受影响…");dialog.resize();
    final int[] index={0};final Runnable[] next={null};next[0]=()->{
      if(!active()||!dialog.isShowing())return;
      if(index[0]>=sources.size()){preparing[0]=false;draft.normalize(catalog);error.setText("");error.setTextColor(ReferenceUi.RED);dialog.primary().setEnabled(true);dialog.primary().setText("保存并应用");render.run();return;}
      JSONObject source=sources.get(index[0]++);loadPool(source.optString("role",NetworkCatalog.ENTRY),source,false,null,false,(ok,message)->{
        if(!active()||!dialog.isShowing())return;
        if(ok){draft.normalize(catalog);next[0].run();}
        else{preparing[0]=false;error.setText("已保存的节点暂时无法读取，请重新选择订阅后重试。");error.setTextColor(ReferenceUi.RED);dialog.primary().setEnabled(true);dialog.primary().setText("保存并应用");render.run();}
      });
    };next[0].run();
  }
  ReferenceUi.Modal selectSubscription(NetworkDraft draft,Runnable changed){
    ReferenceUi.Modal d=new ReferenceUi.Modal(a,"选择入口订阅");JSONArray all=catalog.subscriptions(NetworkCatalog.ENTRY);
    for(int i=0;i<all.length();i++){
      JSONObject source=all.optJSONObject(i);String id=source.optString("id");
      choice(d,source.optString("name"),sourceSummary(source,NetworkCatalog.ENTRY),id.equals(draft.subscriptionId),()->{
        d.dismiss();Runnable choose=()->{
          JSONObject current=catalog.subscription(NetworkCatalog.ENTRY,id);if(current==null)return;
          boolean different=!current.optString("id").equals(draft.subscriptionId);draft.subscription(current.optString("id"),catalog);
          if(different){for(String name:NetworkSourceSelection.names(current))draft.allowEntry(name,true,catalog);if("random".equals(draft.mode))draft.randomize(new Random());}
          draft.normalize(catalog);changed.run();
        };
        if(sourceNeedsRead(source))loadPool(NetworkCatalog.ENTRY,source,false,choose);else choose.run();
      });
    }
    if(all.length()==0)d.note("添加入口订阅后，可以自动优选或指定入口节点。");
    d.buttons("取消",d::dismiss,"添加订阅",()->{d.dismiss();subscriptionForm(NetworkCatalog.ENTRY,null,()->selectSubscription(draft,changed));});d.show();return d;
  }
  ReferenceUi.Modal selectExit(NetworkDraft draft,Runnable changed){
    ReferenceUi.Modal d=new ReferenceUi.Modal(a,"选择固定出口");JSONArray sources=catalog.subscriptions(NetworkCatalog.EXIT),manual=catalog.exits();
    if(sources.length()>0)d.note("出口订阅");
    for(int i=0;i<sources.length();i++){
      JSONObject source=sources.optJSONObject(i);String id=source.optString("id");
      choice(d,source.optString("name"),sourceSummary(source,NetworkCatalog.EXIT),id.equals(draft.exitSubscriptionId),()->{
        d.dismiss();Runnable choose=()->{JSONObject current=catalog.subscription(NetworkCatalog.EXIT,id);if(current!=null)selectExitNode(draft,current,changed);};
        if(sourceNeedsRead(source))loadPool(NetworkCatalog.EXIT,source,false,choose);else choose.run();
      });
    }
    if(manual.length()>0)d.note("手动出口");
    for(int i=0;i<manual.length();i++){
      JSONObject e=manual.optJSONObject(i);String ip=e.optString("verifiedIp");
      choice(d,e.optString("name"),ip.isEmpty()?"SOCKS5 · IP 待核验":ip,e.optString("id").equals(draft.exitId),()->{draft.manualExit(e.optString("id"),catalog);d.dismiss();changed.run();});
    }
    if(sources.length()==0&&manual.length()==0)d.note("添加出口订阅或手动 SOCKS5 出口，再为当前窗口指定一个固定出口。");
    d.buttons("取消",d::dismiss,"添加出口",()->{d.dismiss();addExitSource(()->selectExit(draft,changed));});d.show();return d;
  }
  ReferenceUi.Modal selectExitNode(NetworkDraft draft,JSONObject source,Runnable changed){
    return new ExitNodePickerUi(a,source,source.optString("id").equals(draft.exitSubscriptionId)?draft.exitNodeKey:"",source.optString("id").equals(draft.exitSubscriptionId)?draft.exitNodeName:"",(current,key,name)->{
      catalog=current;draft.exitSubscription(source.optString("id"),catalog);draft.exitNode(key,name,catalog);changed.run();
    }).show();
  }
  void addExitSource(Runnable next){ReferenceUi.Modal d=new ReferenceUi.Modal(a,"添加固定出口");choice(d,"出口订阅","从订阅里指定 SOCKS5 出口",false,()->{d.dismiss();subscriptionForm(NetworkCatalog.EXIT,null,next);});choice(d,"手动 SOCKS5 出口","填写服务器和认证信息",false,()->{d.dismiss();exitForm(next);});d.buttons("取消",d::dismiss,"",()->{});d.show();}
  ReferenceUi.Modal selectEntry(NetworkDraft draft,Runnable changed){
    JSONObject sub=catalog.subscription(NetworkCatalog.ENTRY,draft.subscriptionId);if(sub==null)return ReferenceUi.message(a,"选择入口","请先选择入口订阅。");
    if(sourceNeedsRead(sub)){loadPool(NetworkCatalog.ENTRY,sub,false,()->{draft.subscription(sub.optString("id"),catalog);draft.normalize(catalog);changed.run();selectEntry(draft,changed);});return null;}
    draft.normalize(catalog);return new EntryPickerUi(a,draft,NetworkSourceSelection.names(sub),catalog,changed).show();
  }

  // Kept for existing entrance callers. Role and publication token bind every async result.
  void loadPool(JSONObject subscription,boolean update,Runnable next){loadPool(NetworkCatalog.ENTRY,subscription,update,next);}
  void loadPool(String role,JSONObject subscription,boolean update,Runnable next){loadPool(role,subscription,update,next,true);}
  interface PoolCompletion{void done(boolean ok,String message);}
  void loadPool(String role,JSONObject subscription,boolean update,Runnable next,boolean present){loadPool(role,subscription,update,next,present,null);}
  void loadPool(String role,JSONObject subscription,boolean update,Runnable next,boolean present,PoolCompletion completion){
    ReferenceUi.Modal d=new ReferenceUi.Modal(a,update?"更新"+roleName(role)+"订阅":"读取"+roleName(role)+"节点");
    d.body.addView(DesignUi.progress(a,"正在读取 "+subscription.optString("name"),"当前窗口继续使用原连接。"));d.buttons("收起",d::dismiss,"",()->{});if(present)d.show();
    String id=subscription.optString("id");sourceBackground(()->{
      try{
        NetworkCatalog fresh=new NetworkCatalog(a);JSONObject row=fresh.subscription(role,id);if(row==null)throw new IllegalStateException();
        if(NetworkCatalog.local(row)){main.post(()->{if(!active())return;catalog=fresh;d.dismiss();if(completion!=null)completion.done(false,"本地节点无需更新；缓存缺失时请重新导入");else ReferenceUi.message(a,"本地分享节点","本地节点无需更新；缓存缺失时请重新导入。");});return;}
        byte[] cached=update?null:fresh.cache(row);if(completion!=null&&(cached==null||!subscription.optString("url").equals(row.optString("url"))||subscription.optLong("addressRevision")!=row.optLong("addressRevision")))throw new IllegalStateException("Saved source changed before cached parsing");long stamp=row.optLong("lastSuccessAt",row.optLong("updatedAt"));
        NetworkCatalog.RefreshToken token=fresh.beginRefresh(role,id);
        main.post(()->{if(active()){catalog=fresh;render();}});
        NativeNetwork.previewSubscription(Profiles.context(a,Profiles.slot(a)),role,token.url,cached,(ok,message,names,details,bytes)->sourceBackground(()->{
          try{
            NetworkCatalog latest=new NetworkCatalog(a);long at=System.currentTimeMillis();
            if(ok)latest.parsed(token,names,details,bytes,cached==null?at:stamp);else latest.failed(token,message,at);
            main.post(()->{
              if(!active())return;catalog=latest;reload();render();
              String failure=ok?"":latest.subscription(role,id).optString("lastError");if(completion!=null)completion.done(ok,failure);
              if(!d.isShowing())return;
              if(ok){d.dismiss();if(next!=null)next.run();}else showSourceFailure(d,role,id,update,next,failure);
            });
          }catch(Exception stale){main.post(()->{
            if(!active())return;reload();if(completion!=null)completion.done(false,"订阅已变化或无法保存");if(d.isShowing()){
              d.body.removeAllViews();d.note("这次读取结果未应用：订阅可能已修改，或缓存暂时无法保存。请重新更新当前订阅。");
              d.buttons("关闭",d::dismiss,"",()->{});d.resize();
            }
          });}
        }));
      }catch(Exception missing){main.post(()->{if(!active())return;if(completion!=null)completion.done(false,"无法读取当前订阅");if(d.isShowing()){d.body.removeAllViews();d.note("无法读取当前订阅，请检查它是否仍在列表中。");d.buttons("关闭",d::dismiss,"",()->{});d.resize();reload();}});}
    });
  }
  void showSourceFailure(ReferenceUi.Modal d,String role,String id,boolean update,Runnable next,String message){
    d.body.removeAllViews();d.note(message);JSONObject current=catalog.subscription(role,id);
    d.buttons("关闭",d::dismiss,current==null?"":"重试",()->{d.dismiss();JSONObject row=catalog.subscription(role,id);if(row!=null)loadPool(role,row,update,next);});d.resize();
  }
  boolean active(){return !closed&&!a.isDestroyed()&&!a.isFinishing();}
  void background(Runnable task){if(closed)return;try{reader.execute(task);}catch(RejectedExecutionException finished){/* Metadata reader has closed. */}}
  static void libraryWork(Runnable task){libraryWorker.execute(task);}
  void sourceBackground(Runnable task){libraryWork(task);}

  void subscriptionForm(Runnable next){subscriptionForm(NetworkCatalog.ENTRY,null,next);}
  void subscriptionForm(String role,JSONObject existing,Runnable next){
    boolean editing=existing!=null;ReferenceUi.Modal d=new ReferenceUi.Modal(a,(editing?"编辑":"添加")+roleName(role)+"订阅");
    EditText name=DesignUi.input(d.body,"订阅名称",editing?existing.optString("name"):"","例如：工作"+roleName(role)),url=DesignUi.input(d.body,"订阅地址",editing?existing.optString("url"):"","https://…");url.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_URI);
    d.note("Clash / Mihomo 格式。");
    if(NetworkCatalog.EXIT.equals(role))d.note("可指定其中的 SOCKS5 节点作为固定出口，出口不会参与随机选择。");
    TextView error=ReferenceUi.text(a,"",12,ReferenceUi.RED,false);error.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);d.body.addView(error);final boolean[] saving={false};
    d.buttons("取消",d::dismiss,"保存订阅",()->{
      if(saving[0])return;String title=name.getText().toString().trim(),address=url.getText().toString().trim();if(title.isEmpty()){name.setError("填写订阅名称");return;}
      saving[0]=true;d.primary().setEnabled(false);d.primary().setText("正在保存…");((Button)d.footer.getChildAt(0)).setText("收起");sourceBackground(()->{
        try{
          NetworkCatalog fresh=new NetworkCatalog(a);JSONObject source=editing?fresh.editSubscription(role,existing.optString("id"),title,address):fresh.addSubscription(role,title,address);
          boolean needsRead=!editing||!address.equals(existing.optString("url"))||sourceNeedsRead(source);
          main.post(()->{if(!active())return;boolean advance=d.isShowing();catalog=fresh;d.dismiss();reload();render();if(needsRead)loadPool(role,source,false,advance?next:null,advance);else if(next!=null&&advance)next.run();});
        }catch(Exception invalid){main.post(()->{if(!active()||!d.isShowing())return;saving[0]=false;error.setText(sourceEditError(invalid));d.primary().setEnabled(true);d.primary().setText("保存订阅");((Button)d.footer.getChildAt(0)).setText("取消");d.resize();});}
      });
    });d.show();
  }
  String sourceEditError(Exception error){String message=error.getMessage();return message==null||message.contains("://")?"订阅无法保存，请检查名称和 HTTPS 地址后重试。":message;}
  void exitForm(Runnable next){exitForm(null,next);}
  void exitForm(JSONObject existing,Runnable next){
    boolean editing=existing!=null;ReferenceUi.Modal d=new ReferenceUi.Modal(a,editing?"编辑固定出口":"添加固定出口");
    EditText name=DesignUi.input(d.body,"出口名称",editing?existing.optString("name"):"","例如：工作出口"),region=DesignUi.input(d.body,"地区（可选）",editing?existing.optString("region"):"","填写你已知的出口地区"),server=DesignUi.input(d.body,"SOCKS5 服务器",editing?existing.optString("host"):"","域名或 IP"),port=DesignUi.input(d.body,"端口",editing?Integer.toString(existing.optInt("port")):"","1–65535"),user=DesignUi.input(d.body,"用户名（可选）",editing?existing.optString("user"):"",""),password=DesignUi.input(d.body,"密码（可选）",editing?existing.optString("password"):"","");
    port.setInputType(InputType.TYPE_CLASS_NUMBER);DesignUi.visiblePassword(password);
    TextView error=ReferenceUi.text(a,"",12,ReferenceUi.RED,false);d.body.addView(error);final boolean[] saving={false};
    d.buttons("取消",d::dismiss,"保存出口",()->{
      if(saving[0])return;String title=name.getText().toString().trim();if(title.isEmpty()){name.setError("填写出口名称");return;}
      final int number;try{number=Integer.parseInt(port.getText().toString());if(number<1||number>65535)throw new NumberFormatException();}catch(NumberFormatException invalid){port.setError("端口应为 1–65535");return;}
      String regionValue=region.getText().toString().trim(),serverValue=server.getText().toString().trim(),userValue=user.getText().toString(),passwordValue=password.getText().toString();
      saving[0]=true;d.primary().setEnabled(false);((Button)d.footer.getChildAt(0)).setText("收起");sourceBackground(()->{try{
        NetworkCatalog fresh=new NetworkCatalog(a);if(editing)fresh.editExit(existing.optString("id"),title,regionValue,serverValue,number,userValue,passwordValue);else fresh.addExit(title,regionValue,serverValue,number,userValue,passwordValue);
        main.post(()->{if(!active())return;boolean advance=d.isShowing();catalog=fresh;d.dismiss();reload();render();if(next!=null&&advance)next.run();});
      }catch(Exception invalid){main.post(()->{if(!active()||!d.isShowing())return;saving[0]=false;error.setText(sourceEditError(invalid));d.primary().setEnabled(true);((Button)d.footer.getChildAt(0)).setText("取消");d.resize();});}});
    });d.show();
  }
  void subscriptionDetail(JSONObject selected){
    String role=selected.optString("role",NetworkCatalog.ENTRY),id=selected.optString("id");JSONObject source=catalog.subscription(role,id);if(source==null){reload();return;}
    ReferenceUi.Modal d=new ReferenceUi.Modal(a,roleName(role)+(NetworkCatalog.local(source)?"本地节点":"订阅详情"));field(d,"名称",source.optString("name"));field(d,"状态",sourceSummary(source,role));
    if(!NetworkCatalog.local(source))field(d,"订阅地址",source.optString("url"));field(d,"更新于",updated(source.optLong("lastSuccessAt",source.optLong("updatedAt"))));field(d,"使用窗口",sourceUses(role,id)+" 个");
    if(!source.optString("lastError").isEmpty())d.note(source.optString("lastError"));
    if(source.optBoolean("stale"))d.note("以下是上次成功读取的节点。更新当前地址后，才能用于新的窗口配置。");
    DesignUi.action(d.body,"查看节点 · "+NetworkSourceSelection.names(source).size()+" 个",false,()->new ExitNodePickerUi(a,source,null,null).show());
    if(!NetworkCatalog.local(source))DesignUi.action(d.body,"编辑订阅",false,()->{d.dismiss();subscriptionForm(role,source,null);});
    if(NetworkCatalog.ENTRY.equals(role)&&!NetworkCatalog.local(source))DesignUi.action(d.body,"分享入口订阅",false,()->{d.dismiss();final String address=source.optString("url");NetworkShareUi.subscription(a,()->NetworkShareSelection.subscriptionUrl(address));});
    DesignUi.action(d.body,NetworkCatalog.local(source)?"删除本地节点":"删除订阅",false,()->{d.dismiss();deleteSource(role,source);});
    d.buttons("关闭",d::dismiss,NetworkCatalog.local(source)?"":"更新订阅",()->{d.dismiss();loadPool(role,source,true,null);});d.show();
  }
  void deleteSource(String role,JSONObject source){
    String id=source.optString("id");ReferenceUi.Modal d=new ReferenceUi.Modal(a,"删除"+roleName(role)+"订阅");
    d.note("删除“"+source.optString("name")+"”？"+sourceUses(role,id)+" 个窗口引用了它。删除只移除资源库中的订阅，当前连接继续使用原线路；下次编辑时需要重新选择。");
    TextView error=ReferenceUi.text(a,"",12,ReferenceUi.RED,false);d.body.addView(error);
    d.buttons("取消",d::dismiss,"删除订阅",()->{d.primary().setEnabled(false);sourceBackground(()->{try{NetworkCatalog fresh=new NetworkCatalog(a);fresh.deleteSubscription(role,id);main.post(()->{if(!active())return;catalog=fresh;d.dismiss();reload();render();});}catch(Exception failed){main.post(()->{if(active()&&d.isShowing()){error.setText("订阅未删除，请重新读取列表后重试。");d.primary().setEnabled(true);d.resize();}});}});});d.show();
  }
  void exitDetail(JSONObject selected){
    JSONObject e=catalog.exit(selected.optString("id"));if(e==null){reload();return;}ReferenceUi.Modal d=new ReferenceUi.Modal(a,"出口详情");
    field(d,"名称",e.optString("name"));field(d,"地区",e.optString("region").isEmpty()?"未标注":e.optString("region"));field(d,"出口 IP",e.optString("verifiedIp").isEmpty()?"待核验":e.optString("verifiedIp"));field(d,"服务器",e.optString("host")+":"+e.optInt("port"));field(d,"使用窗口",uses(e.optString("id"))+" 个");
    DesignUi.action(d.body,"分享出口",false,()->{d.dismiss();NetworkShareUi.manual(a,e);});
    DesignUi.action(d.body,"编辑出口",false,()->{d.dismiss();exitForm(e,null);});DesignUi.action(d.body,"删除出口",false,()->{d.dismiss();deleteExit(e);});
    d.buttons("关闭",d::dismiss,"核验出口",()->{
      List<Integer> owners=new ArrayList<>();for(int i=0;i<windows.length();i++){WindowNetworkState s=state(windows.optJSONObject(i));if(s.internal&&s.connected&&manualReference(s.config,e.optString("id")))owners.add(s.slot);}
      if(owners.isEmpty()){d.note("此出口尚无已连接窗口。保存窗口配置并连接后即可核验。");d.resize();return;}d.dismiss();operate(owners.get(0),"verify");
    });d.show();
  }
  void deleteExit(JSONObject exit){
    String id=exit.optString("id");ReferenceUi.Modal d=new ReferenceUi.Modal(a,"删除固定出口");d.note("删除“"+exit.optString("name")+"”？"+uses(id)+" 个窗口引用了它。当前连接继续使用原线路，下次编辑时需要重新选择出口。");TextView error=ReferenceUi.text(a,"",12,ReferenceUi.RED,false);d.body.addView(error);
    d.buttons("取消",d::dismiss,"删除出口",()->{d.primary().setEnabled(false);sourceBackground(()->{try{NetworkCatalog fresh=new NetworkCatalog(a);fresh.deleteExit(id);main.post(()->{if(!active())return;catalog=fresh;d.dismiss();reload();render();});}catch(Exception failed){main.post(()->{if(active()&&d.isShowing()){error.setText("出口未删除，请重新读取列表后重试。");d.primary().setEnabled(true);d.resize();}});}});});d.show();
  }
  void operate(int slot,String action){JSONObject item=windowItem(slot);if(item==null){reload();return;}operate(state(item),action);}
  void operate(WindowNetworkState expected,String action){boolean internal=expected.internal;ReferenceUi.Modal d=new ReferenceUi.Modal(a,action.equals("measure")?internal?"完整线路测速":"连接响应测速":action.equals("verify")?"核验出口":"重新连接");d.body.addView(DesignUi.progress(a,action.equals("measure")?internal?"正在测量入口与固定出口的完整线路…":"正在测量当前连接的响应…":"正在检查此窗口网络…",""));d.buttons("收起",d::dismiss,"",()->{});d.show();NetworkBridge.run(a,expected.slot,action,null,null,identity(expected),(ok,message,snapshot)->{if(!active())return;reload();if(d.isShowing()){boolean current=diagnosticWindowCurrent(expected);d.body.removeAllViews();TextView result=ReferenceUi.text(a,current?message:"环境已变化，请重新打开网络设置。",15,current&&ok?ReferenceUi.GREEN:ReferenceUi.RED,true);d.body.addView(result);d.buttons("关闭",d::dismiss,"",()->{});d.resize();}});}
  void networkMode(int slot){if(catalog==null){afterRead=()->networkMode(slot);reload();return;}JSONObject item=windowItem(slot);if(item==null){reload();return;}networkMode(state(item));}
  void networkMode(WindowNetworkState expected){JSONObject item=windowItem(expected.slot);if(!diagnosticWindowCurrent(expected)||!editorReady(item))return;ReferenceUi.Modal d=new ReferenceUi.Modal(a,"网络方式 · "+expected.name);choice(d,"订阅入口 + 固定出口","",false,()->{d.dismiss();editInternal(item);});choice(d,"手机网络 / 手机 VPN","",false,()->{d.dismiss();external(item,false);});choice(d,"应用专用代理","",false,()->{d.dismiss();external(item,true);});d.show();}
  void external(int slot,boolean proxy){external(windowItem(slot),proxy);}
  void external(JSONObject item,boolean proxy){
    if(!editorReady(item))return;WindowNetworkState expected=state(item);int slot=expected.slot;JSONObject meta=metadata(item),queued=meta.optJSONObject("pending");boolean pending="external".equals(queued.optString("action"));JSONObject draft=pending?queued.optJSONObject("config"):meta.optJSONObject("externalConfig");
    ReferenceUi.Modal d=new ReferenceUi.Modal(a,(proxy?"应用专用代理":"手机网络 / VPN")+" · "+expected.name);TextView context=ReferenceUi.secondary(a,editingContext(item,pending));context.setSingleLine(false);d.body.addView(context);
    EditText address=proxy?DesignUi.input(d.body,"代理地址",draft.optString("proxy"),"填写代理地址"):null;if(proxy)d.note("HTTP：http://主机:端口\nSOCKS：socks://主机:端口");CheckBox vpn=new CheckBox(a);vpn.setText("手机 VPN 断开时暂停联网");vpn.setTextSize(13);vpn.setChecked(draft.optBoolean("requireExternalVpn",true));
    if(!proxy){d.body.addView(vpn);d.note("开启后，未连接手机 VPN 就会暂停此环境的所有网页请求；关闭后使用手机当前网络。");}else d.note("代理不可用时暂停联网，不自动切换手机直连。");
    TextView error=ReferenceUi.text(a,"",12,ReferenceUi.RED,false);error.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);d.body.addView(error);String baseline=meta.optString("baseline");final boolean[] saving={false};
    d.buttons("取消",d::dismiss,"保存并应用",()->{
      if(saving[0])return;String value=proxy?address.getText().toString().trim():"";if(proxy&&!MainActivity.validProxy(value)){address.setError("填写有效的 HTTP / SOCKS 代理地址");return;}
      saving[0]=true;d.primary().setEnabled(false);d.primary().setText("正在保存…");((Button)d.footer.getChildAt(0)).setText("收起");if(address!=null)address.setEnabled(false);vpn.setEnabled(false);error.setText("正在保存并应用，收起后操作仍会继续…");error.setTextColor(ReferenceUi.MUTED);d.resize();
      NetworkBridge.run(a,slot,"external",J.obj("proxy",value,"requireExternalVpn",vpn.isChecked()),baseline,identity(expected),applicationDecision(expected),(ok,message,snapshot)->{
        if(!active())return;saving[0]=false;reload();context.setText("本次保存结果");editorResult(d,error,expected,ok,message,snapshot,()->{context.setText(editingContext(item,pending));d.primary().setEnabled(true);d.primary().setText("保存并应用");((Button)d.footer.getChildAt(0)).setText("取消");if(address!=null)address.setEnabled(true);vpn.setEnabled(true);});
      });
    });d.show();
  }
}
