package local.pocketchat;

import android.app.*;import android.content.*;import android.graphics.Color;import android.os.*;import android.text.InputType;import android.view.*;import android.widget.*;
import org.json.*;import java.util.*;import java.util.concurrent.*;

/** Three native tabs over the existing per-window network implementation. */
final class NetworkWorkspaceUi {
  private static final ExecutorService libraryWorker=Executors.newSingleThreadExecutor();
  final Activity a;final FrameLayout host;final Handler main=new Handler(Looper.getMainLooper());final ExecutorService reader=Executors.newSingleThreadExecutor();
  LinearLayout root,box,tabHost;Button filterButton;ScrollView scroll;NetworkCatalog catalog;JSONArray windows=new JSONArray();int tab,filter,focus=-1;boolean focusPending,reading,closed;long lastRead;String lastRendered="";Runnable afterRead;
  NetworkWorkspaceUi(Activity a,FrameLayout host){this.a=a;this.host=host;}
  int dp(int n){return ReferenceUi.dp(a,n);}
  void show(int requested){tab=Math.max(0,Math.min(2,requested));if(root==null)layout();else{if(root.getParent()!=host){host.removeAllViews();host.addView(root,new FrameLayout.LayoutParams(-1,-1));}render();}fetch();}
  void layout(){lastRendered="";root=DesignUi.column(a);root.setBackgroundColor(ReferenceUi.BG);LinearLayout head=DesignUi.row(a);head.setPadding(dp(16),dp(5),dp(16),dp(5));head.addView(ReferenceUi.text(a,"网络",20,ReferenceUi.TEXT,true),new LinearLayout.LayoutParams(0,dp(48),1));filterButton=ReferenceUi.link(a,"筛选",this::filters);head.addView(filterButton,new LinearLayout.LayoutParams(dp(64),dp(48)));Button refresh=ReferenceUi.button(a,"↻",false,()->{lastRead=0;fetch();});refresh.setTextSize(android.util.TypedValue.COMPLEX_UNIT_DIP,24);refresh.setContentDescription("刷新网络状态");head.addView(refresh,new LinearLayout.LayoutParams(dp(48),dp(48)));root.addView(head);
    tabHost=DesignUi.column(a);tabHost.setPadding(dp(16),0,dp(16),dp(6));root.addView(tabHost);scroll=new ScrollView(a);scroll.setFillViewport(false);box=DesignUi.column(a);box.setPadding(dp(16),0,dp(16),dp(14));scroll.addView(box);root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));host.removeAllViews();host.addView(root,new FrameLayout.LayoutParams(-1,-1));render();}
  void select(int next){tab=next;if(a instanceof MainActivity)((MainActivity)a).hub.networkTab=next;filter=0;scroll.scrollTo(0,0);render();}
  static void readUiMetadata(Context c,JSONArray list){for(int i=0;i<list.length();i++){JSONObject item=list.optJSONObject(i),row=item.optJSONObject("row");Context profile=Profiles.context(c,row.optInt("slot"));NetworkRegion.read(profile);JSONObject pending=NetworkChanges.pending(profile);NetworkCatalog.put(item,"pendingNetwork",pending.length()>0);NetworkCatalog.put(item,"pendingConfig","apply".equals(pending.optString("action"))?pending.optJSONObject("config"):null);}}
  void fetch(){if(closed||reading||SystemClock.elapsedRealtime()-lastRead<1800)return;reading=true;lastRead=SystemClock.elapsedRealtime();background(()->{NetworkCatalog next=new NetworkCatalog(a);JSONArray list=WindowNetworkState.windows(a);readUiMetadata(a,list);main.post(()->{reading=false;if(closed)return;catalog=next;windows=list;if(root!=null&&root.getParent()==host)render();if(afterRead!=null){Runnable done=afterRead;afterRead=null;done.run();}});});}
  void reload(){lastRead=0;fetch();}
  void close(){closed=true;reader.shutdownNow();main.removeCallbacksAndMessages(null);}
  WindowNetworkState state(JSONObject item){JSONObject runtime=item.optJSONObject("runtime");boolean live=item.optBoolean("live");if(a instanceof MainActivity){MainActivity chat=(MainActivity)a;if(chat.session!=null&&item.optJSONObject("row").optInt("slot")==Profiles.slot(a)){runtime=WindowNetworkState.live(chat.session,NativeNetwork.get(chat));live=true;}}return new WindowNetworkState(a,item.optJSONObject("row"),item.optJSONObject("config"),runtime,live,System.currentTimeMillis());}
  void render(){if(box==null)return;StringBuilder key=new StringBuilder(tab+"|"+filter+"|"+focus+"|");if(catalog!=null){key.append(catalog.readError()).append(catalog.data.toString());for(int i=0;i<windows.length();i++){JSONObject item=windows.optJSONObject(i);WindowNetworkState s=state(item);key.append(s.name).append(s.state).append(s.mainline()).append(s.subline()).append(NativeNetwork.hash(s.config.toString())).append(item.optBoolean("pendingNetwork"));}}if(key.toString().equals(lastRendered)&&!focusPending)return;lastRendered=key.toString();boolean locate=focusPending;int y=scroll.getScrollY();filterButton.setVisibility(tab==0?View.VISIBLE:View.GONE);filterButton.setText(filter==0?"筛选":"筛选 ·");tabHost.removeAllViews();tabHost.addView(ReferenceUi.tabs(a,new String[]{"窗口网络","入口","出口"},tab,this::select));box.removeAllViews();if(catalog==null){TextView t=ReferenceUi.text(a,"正在读取窗口网络…",13,ReferenceUi.MUTED,false);box.addView(t);return;}if(!catalog.readError().isEmpty()){empty("网络库暂时无法读取",catalog.readError());box.addView(ReferenceUi.link(a,"重新读取",this::reload),new LinearLayout.LayoutParams(-1,dp(48)));if(tab==0)renderWindows();}else if(tab==0)renderWindows();else if(tab==1)renderSubscriptions();else renderExits();scroll.post(()->{if(!locate)scroll.scrollTo(0,y);});}
  void focus(int slot){focus=slot;focusPending=true;filter=0;tab=0;}
  void renderWindows(){
    LinearLayout summary=DesignUi.row(a);summary.setMinimumHeight(dp(24));int count=0;for(int i=0;i<windows.length();i++)if(matches(state(windows.optJSONObject(i))))count++;summary.addView(ReferenceUi.text(a,count+" 个窗口",13,ReferenceUi.MUTED,false),new LinearLayout.LayoutParams(0,-2,1));box.addView(summary);
    for(int i=0;i<windows.length();i++){JSONObject item=windows.optJSONObject(i);WindowNetworkState s=state(item);if(!matches(s))continue;LinearLayout card=ReferenceUi.card(a);LinearLayout head=DesignUi.row(a);TextView name=ReferenceUi.text(a,s.name,17,ReferenceUi.TEXT,true);ReferenceUi.single(name);head.addView(name,new LinearLayout.LayoutParams(0,-2,1));TextView status=ReferenceUi.text(a,"● "+s.state,11,s.color(),true);status.setPadding(dp(8),0,0,0);head.addView(status);card.addView(head);
      TextView line=ReferenceUi.text(a,s.mainline(),14,ReferenceUi.TEXT,false);line.setMaxLines(2);line.setPadding(0,dp(9),0,0);card.addView(line);TextView route=ReferenceUi.secondary(a,windowSubline(s));route.setSingleLine(false);route.setMaxLines(2);card.addView(route);if(item.optBoolean("pendingNetwork"))card.addView(ReferenceUi.secondary(a,"配置已保存，当前连接继续使用原线路"));LinearLayout actions=DesignUi.row(a);actions.setPadding(0,dp(6),0,0);
      actions.addView(ReferenceUi.small(a,"编辑网络",true,()->edit(item)),new LinearLayout.LayoutParams(-2,dp(48)));Button measure=ReferenceUi.small(a,"测速",false,()->operate(s.slot,"measure"));LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-2,dp(48));p.leftMargin=dp(8);actions.addView(measure,p);actions.addView(new View(a),new LinearLayout.LayoutParams(0,1,1));actions.addView(ReferenceUi.more(a,()->more(item)),new LinearLayout.LayoutParams(dp(44),dp(48)));card.addView(actions);ReferenceUi.add(box,card);
      if(s.slot==focus){card.setBackground(ReferenceUi.surface(a,ReferenceUi.WHITE,16,0xff94b8ff));if(focusPending){focusPending=false;card.post(()->scroll.smoothScrollTo(0,card.getTop()));}}
    }
    if(count==0)empty("没有匹配的窗口",filter==0?"创建环境后会在这里显示网络。":"调整筛选即可查看其他窗口。");
  }
  String windowSubline(WindowNetworkState state){
    if(!state.internal)return state.subline();String entrance=state.entry.isEmpty()?"入口待选择":nodeName(state.entry),exit=state.config.optString("exitName");
    if("subscription".equals(state.config.optString("exitSource")))exit=nodeName(state.config.optString("exitNodeName",exit));
    return entryModeLabel(state.config.optString("entryMode"))+" · "+entrance+" → "+(exit.isEmpty()?"出口待选择":exit);
  }
  static String entryModeLabel(String mode){return "latency".equals(mode)?"自动优选":NetworkOptimizationPolicy.label(mode);}
  boolean matches(WindowNetworkState s){return filter==0||filter==1&&s.connected||filter==2&&!s.connected;}
  void filters(){ReferenceUi.Modal d=new ReferenceUi.Modal(a,"筛选窗口");String[] choices={"全部窗口","已连接","待连接 / 未配置"};for(int i=0;i<choices.length;i++){final int n=i;choice(d,choices[i],"",filter==i,()->{filter=n;focus=-1;d.dismiss();scroll.scrollTo(0,0);render();});}d.show();}
  void empty(String title,String detail){LinearLayout c=ReferenceUi.card(a);c.addView(ReferenceUi.text(a,title,16,ReferenceUi.TEXT,true));c.addView(ReferenceUi.secondary(a,detail));ReferenceUi.add(box,c);}
  void listHeader(String name,Runnable add){LinearLayout head=DesignUi.row(a);head.addView(ReferenceUi.text(a,name,18,ReferenceUi.TEXT,true),new LinearLayout.LayoutParams(0,dp(48),1));head.addView(ReferenceUi.small(a,"＋ 添加",true,add),new LinearLayout.LayoutParams(-2,dp(48)));box.addView(head);}
  void renderSubscriptions(){renderSources(NetworkCatalog.ENTRY);}
  void renderExits(){
    renderSources(NetworkCatalog.EXIT);
    listHeader("手动固定出口",()->exitForm(null));
    JSONArray all=catalog.exits();
    for(int i=0;i<all.length();i++){
      JSONObject e=all.optJSONObject(i);LinearLayout row=ReferenceUi.card(a);
      TextView name=ReferenceUi.text(a,e.optString("name"),16,ReferenceUi.TEXT,true);ReferenceUi.single(name);row.addView(name);
      String ip=e.optString("verifiedIp");row.addView(ReferenceUi.secondary(a,ip.isEmpty()?"IP 待核验":ip));
      row.addView(ReferenceUi.secondary(a,(ip.isEmpty()?"待核验":"上次已核验")+" · "+uses(e.optString("id"))+" 个窗口使用"));
      libraryCard(row,()->exitDetail(e),e.optString("name")+"，查看固定出口详情");ReferenceUi.add(box,row);
    }
    if(all.length()==0&&catalog.subscriptions(NetworkCatalog.EXIT).length()==0)empty("还没有固定出口","添加出口订阅或已有的 SOCKS5 出口，每个窗口单独选择。");
  }
  void renderSources(String role){
    listHeader(roleName(role)+"订阅",()->subscriptionForm(role,null,null));
    JSONArray all=catalog.subscriptions(role);
    for(int i=0;i<all.length();i++){
      JSONObject source=all.optJSONObject(i);LinearLayout card=ReferenceUi.card(a);LinearLayout head=DesignUi.row(a);
      TextView name=ReferenceUi.text(a,source.optString("name"),16,ReferenceUi.TEXT,true);ReferenceUi.single(name);
      head.addView(name,new LinearLayout.LayoutParams(0,-2,1));
      head.addView(ReferenceUi.more(a,()->subscriptionDetail(source)),new LinearLayout.LayoutParams(dp(40),dp(40)));card.addView(head);
      card.addView(ReferenceUi.secondary(a,sourceSummary(source,role)));
      card.addView(ReferenceUi.secondary(a,"更新于 "+updated(source.optLong("lastSuccessAt",source.optLong("updatedAt")))));
      libraryCard(card,()->subscriptionDetail(source),source.optString("name")+"，查看"+roleName(role)+"订阅详情");ReferenceUi.add(box,card);
    }
    if(all.length()==0&&NetworkCatalog.ENTRY.equals(role))empty("还没有入口订阅","添加已有的 Clash / Mihomo 订阅地址。");
    if(all.length()==0&&NetworkCatalog.EXIT.equals(role)&&catalog.exits().length()>0){TextView note=ReferenceUi.secondary(a,"也可以添加出口订阅，再为窗口指定其中的 SOCKS5 节点。");note.setSingleLine(false);box.addView(note);}
  }
  void libraryCard(View card,Runnable open,String description){card.setBackground(new android.graphics.drawable.RippleDrawable(android.content.res.ColorStateList.valueOf(0x182468f2),ReferenceUi.surface(a,ReferenceUi.WHITE,15,ReferenceUi.LINE),null));card.setOnClickListener(v->open.run());card.setFocusable(true);card.setContentDescription(description);}
  static String roleName(String role){return NetworkCatalog.EXIT.equals(role)?"出口":"入口";}
  static String nodeName(String name){return name.startsWith("Entry|")?name.substring(6):name.startsWith("Exit|")?name.substring(5):name;}
  int selectableExitNodes(JSONObject source){
    int count=0;Set<String> names=new HashSet<>(NetworkSourceSelection.names(source));JSONArray details=source.optJSONArray("nodeDetails");
    if(details!=null)for(int i=0;i<details.length();i++){JSONObject node=details.optJSONObject(i);if(node!=null&&names.contains(node.optString("name"))&&NetworkSourceSelection.socks5(node)&&!node.optString("configFingerprint").isEmpty())count++;}return count;
  }
  String sourceSummary(JSONObject source,String role){
    int n=NetworkSourceSelection.names(source).size(),usable=NetworkCatalog.EXIT.equals(role)?selectableExitNodes(source):n;
    String count=NetworkCatalog.EXIT.equals(role)?n+" 个节点 · "+usable+" 个 SOCKS5":n+" 个入口";
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
  void more(JSONObject item){WindowNetworkState s=state(item);ReferenceUi.Modal d=new ReferenceUi.Modal(a,s.name);String[] labels={"窗口详情","重新连接","网络方式","打开会话"};Runnable[] actions={()->details(item),()->operate(s.slot,"reconnect"),()->networkMode(s.slot),()->openChat(s.slot)};for(int i=0;i<labels.length;i++){final int n=i;Button b=ReferenceUi.link(a,labels[i],()->{d.dismiss();actions[n].run();});b.setTextColor(ReferenceUi.TEXT);b.setGravity(Gravity.START|Gravity.CENTER_VERTICAL);d.body.addView(b,new LinearLayout.LayoutParams(-1,dp(48)));}d.show();}
  void openChat(int slot){if(a instanceof MainActivity&&slot==Profiles.slot(a)){((MainActivity)a).hub.select(AppHub.CHAT);return;}a.startActivity(new Intent(a,Profiles.activity(slot)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_REORDER_TO_FRONT));}
  void details(JSONObject item){WindowNetworkState s=state(item);ReferenceUi.Modal d=new ReferenceUi.Modal(a,"窗口详情 · "+s.name);field(d,"网络状态",s.state);field(d,"出口地区",s.region.isEmpty()?"未标注":s.region);field(d,"出口 IP",s.ip.isEmpty()?"未核验":s.ip);field(d,s.internal?"完整线路延迟":"连接响应",s.latency);if(s.internal){JSONObject site=s.runtime.optJSONObject("website");field(d,"ChatGPT 网站响应",site!=null&&s.entry.equals(site.optString("entry"))?WebsiteProbe.line(site,System.currentTimeMillis()):"网站响应未测");}field(d,"入口订阅",s.subscription);if(s.internal){field(d,"入口选择",s.entryMode);field(d,"当前入口",s.entry.isEmpty()?"未选择":NativeNetwork.display(s.entry));field(d,"固定出口",s.config.optString("exitName",s.config.optString("exitHost")));field(d,"出口核验",updated(s.runtime.optLong("verifiedAt")));}if(NetworkChanges.pending(Profiles.context(a,s.slot)).length()>0){d.note("有待应用的网络设置，当前回复继续使用原线路。");final boolean[] cancelling={false};final Button[] cancel={null};TextView cancelError=ReferenceUi.text(a,"",12,ReferenceUi.RED,false);cancelError.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);cancelError.setVisibility(View.GONE);DesignUi.action(d.body,"取消待应用设置",false,()->{if(cancelling[0])return;cancelling[0]=true;cancel[0].setEnabled(false);cancel[0].setText("正在取消…");NetworkBridge.run(a,s.slot,"cancelPending",null,null,(ok,message,snapshot)->{if(!active())return;cancelling[0]=false;reload();if(ok){d.dismiss();return;}if(d.isShowing()){cancelError.setVisibility(View.VISIBLE);cancelError.setText(message==null||message.isEmpty()?"暂时无法取消，请重试。":message);cancel[0].setEnabled(true);cancel[0].setText("取消待应用设置");d.resize();}});});cancel[0]=(Button)d.body.getChildAt(d.body.getChildCount()-1);d.body.addView(cancelError);}if(!s.runtime.optString("issue").isEmpty())d.note(s.runtime.optString("issue"));d.buttons("关闭",d::dismiss,"编辑网络",()->{d.dismiss();edit(item);});d.show();}
  void field(ReferenceUi.Modal d,String name,String value){DesignUi.field(d.body,name,value);}
  void choice(ReferenceUi.Modal d,String name,String detail,boolean selected,Runnable run){LinearLayout row=DesignUi.row(a);row.setPadding(dp(12),dp(9),dp(12),dp(9));row.setMinimumHeight(dp(58));row.setBackground(ReferenceUi.surface(a,selected?0xfff7faff:ReferenceUi.WHITE,14,selected?0xff94b8ff:ReferenceUi.LINE));TextView mark=ReferenceUi.text(a,selected?"◉":"○",20,selected?ReferenceUi.BLUE:ReferenceUi.MUTED,false);row.addView(mark,new LinearLayout.LayoutParams(dp(30),-2));LinearLayout labels=DesignUi.column(a);TextView title=ReferenceUi.text(a,name,15,ReferenceUi.TEXT,true);ReferenceUi.single(title);labels.addView(title);if(!detail.isEmpty())labels.addView(ReferenceUi.secondary(a,detail));row.addView(labels,new LinearLayout.LayoutParams(0,-2,1));row.setOnClickListener(v->run.run());row.setFocusable(true);row.setContentDescription(name+(selected?"，已选择":""));ReferenceUi.add(d.body,row);}
  void routeRow(ReferenceUi.Modal d,String key,String value,Runnable select){LinearLayout row=DesignUi.row(a);row.setMinimumHeight(dp(66));LinearLayout labels=DesignUi.column(a);labels.addView(ReferenceUi.text(a,key,13,ReferenceUi.MUTED,false));TextView title=ReferenceUi.text(a,value,15,ReferenceUi.TEXT,true);ReferenceUi.single(title);title.setPadding(0,dp(4),0,0);labels.addView(title);row.addView(labels,new LinearLayout.LayoutParams(0,-2,1));row.addView(ReferenceUi.text(a,"›",22,ReferenceUi.MUTED,false));row.setOnClickListener(v->select.run());row.setFocusable(true);row.setBackground(Ui.ripple(a,Color.TRANSPARENT,0));d.body.addView(row);View line=new View(a);line.setBackgroundColor(0xffeef2f7);d.body.addView(line,new LinearLayout.LayoutParams(-1,dp(1)));}
  static final class EditorSession {final ReferenceUi.Modal dialog;final NetworkDraft draft;final Runnable refresh;EditorSession(ReferenceUi.Modal dialog,NetworkDraft draft,Runnable refresh){this.dialog=dialog;this.draft=draft;this.refresh=refresh;}}
  EditorSession edit(JSONObject item){if(catalog==null)return null;WindowNetworkState current=state(item);JSONObject queued=NetworkChanges.pending(Profiles.context(a,current.slot));String action=queued.optString("action");if("external".equals(action)||action.isEmpty()&&!current.internal){SharedPreferences p=Profiles.context(a,current.slot).getSharedPreferences("chat",0);external(current.slot,"external".equals(action)?!queued.optJSONObject("config").optString("proxy").isEmpty():!p.getString("proxy","").isEmpty());return null;}return editInternal(item);}
  EditorSession editInternal(JSONObject item){
    if(catalog==null)return null;WindowNetworkState state=state(item);JSONObject pending=NetworkChanges.pending(Profiles.context(a,state.slot));
    NetworkDraft draft=new NetworkDraft(state.slot,"apply".equals(pending.optString("action"))?pending.optJSONObject("config"):state.config,catalog);
    if(!"apply".equals(pending.optString("action"))&&state.connected&&NetworkOptimizationPolicy.pooled(draft.mode)){
      JSONObject source=catalog.subscription(NetworkCatalog.ENTRY,draft.subscriptionId);String key=NetworkSourceSelection.fingerprint(source,state.entry);
      // A runtime name alone cannot adopt a replacement node with different credentials.
      if(!key.isEmpty()&&draft.entryPoolKeys.contains(key))draft.chooseEntry(state.entry,catalog);
    }
    ReferenceUi.Modal d=new ReferenceUi.Modal(a,"编辑网络 · "+state.name);final Runnable[] render={null};final boolean[] saving={false},preparing={false};
    TextView error=ReferenceUi.text(a,"",12,ReferenceUi.RED,false);error.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
    render[0]=()->{
      draft.normalize(catalog);d.body.removeAllViews();JSONObject source=catalog.subscription(NetworkCatalog.ENTRY,draft.subscriptionId),manual=catalog.exit(draft.exitId),exitSource=catalog.subscription(NetworkCatalog.EXIT,draft.exitSubscriptionId);
      routeRow(d,"入口订阅",source==null?"请选择订阅":source.optString("name"),()->{if(!saving[0]&&!preparing[0])selectSubscription(draft,render[0]);});
      String entrance=entryModeLabel(draft.mode)+(draft.entry.isEmpty()?("latency".equals(draft.mode)?" · 连接后优选":" · 待选择"):" · "+nodeName(draft.entry));
      routeRow(d,"入口选择",entrance,()->{if(!saving[0]&&!preparing[0])selectEntry(draft,render[0]);});
      String exit=!draft.exitSubscriptionId.isEmpty()?(exitSource==null?"出口订阅已删除":exitSource.optString("name")+" · "+(draft.exitNodeName.isEmpty()?"请选择节点":nodeName(draft.exitNodeName))):(manual==null?"请选择固定出口":manual.optString("name"));
      routeRow(d,"固定出口",exit,()->{if(!saving[0]&&!preparing[0])selectExit(draft,render[0]);});d.body.addView(error);d.resize();
    };
    d.buttons("取消",d::dismiss,"保存并应用",()->{
      if(saving[0]||preparing[0])return;final JSONObject candidate;
      try{candidate=draft.candidate(catalog);}catch(Exception invalid){error.setText(invalid.getMessage());error.setTextColor(ReferenceUi.RED);d.resize();return;}
      saving[0]=true;d.primary().setEnabled(false);d.primary().setText("正在应用…");((Button)d.footer.getChildAt(0)).setText("收起");
      for(int i=0;i<d.body.getChildCount();i++)d.body.getChildAt(i).setEnabled(false);
      error.setText("正在保存并应用，收起后操作仍会继续…");error.setTextColor(ReferenceUi.MUTED);d.resize();
      NetworkBridge.run(a,draft.slot,"apply",candidate,draft.baseline,(ok,message,snapshot)->{
        if(!active())return;saving[0]=false;reload();
        if(ok){d.dismiss();return;}if(!d.isShowing())return;
        error.setText(message);error.setTextColor(ReferenceUi.RED);
        if(message.startsWith("配置已保存"))d.buttons("关闭",d::dismiss,"重新连接",()->{d.dismiss();operate(draft.slot,"reconnect");});
        else{d.primary().setEnabled(true);d.primary().setText("保存并应用");((Button)d.footer.getChildAt(0)).setText("取消");for(int i=0;i<d.body.getChildCount();i++)d.body.getChildAt(i).setEnabled(true);}
        d.resize();
      });
    });render[0].run();d.show();prepareLegacySources(d,draft,error,preparing,render[0]);return new EditorSession(d,draft,render[0]);
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
    EditText name=DesignUi.input(d.body,"订阅名称",editing?existing.optString("name"):"","例如：工作"+roleName(role)),url=DesignUi.input(d.body,"订阅地址",editing?existing.optString("url"):"","HTTPS · Clash / Mihomo");url.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_URI);
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
    port.setInputType(InputType.TYPE_CLASS_NUMBER);password.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_PASSWORD);
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
    ReferenceUi.Modal d=new ReferenceUi.Modal(a,roleName(role)+"订阅详情");field(d,"名称",source.optString("name"));field(d,"状态",sourceSummary(source,role));
    field(d,"订阅地址",source.optString("url"));field(d,"更新于",updated(source.optLong("lastSuccessAt",source.optLong("updatedAt"))));field(d,"使用窗口",sourceUses(role,id)+" 个");
    if(!source.optString("lastError").isEmpty())d.note(source.optString("lastError"));
    if(source.optBoolean("stale"))d.note("以下是上次成功读取的节点。更新当前地址后，才能用于新的窗口配置。");
    DesignUi.action(d.body,"查看节点 · "+NetworkSourceSelection.names(source).size()+" 个",false,()->new ExitNodePickerUi(a,source,null,null).show());
    DesignUi.action(d.body,"编辑订阅",false,()->{d.dismiss();subscriptionForm(role,source,null);});
    DesignUi.action(d.body,"删除订阅",false,()->{d.dismiss();deleteSource(role,source);});
    d.buttons("关闭",d::dismiss,"更新订阅",()->{d.dismiss();loadPool(role,source,true,null);});d.show();
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
  void operate(int slot,String action){boolean internal="internal".equals(Profiles.context(a,slot).getSharedPreferences("chat",0).getString("networkMode","external"));ReferenceUi.Modal d=new ReferenceUi.Modal(a,action.equals("measure")?internal?"完整线路测速":"连接响应测速":action.equals("verify")?"核验出口":"重新连接");d.body.addView(DesignUi.progress(a,action.equals("measure")?internal?"正在测量入口与固定出口的完整线路…":"正在测量当前连接的响应…":"正在检查此窗口网络…",""));d.buttons("收起",d::dismiss,"",()->{});d.show();NetworkBridge.run(a,slot,action,null,null,(ok,message,snapshot)->{if(closed||a.isDestroyed())return;reload();if(d.isShowing()){d.body.removeAllViews();TextView result=ReferenceUi.text(a,message,15,ok?ReferenceUi.GREEN:ReferenceUi.RED,true);d.body.addView(result);d.buttons("关闭",d::dismiss,"",()->{});d.resize();}});}
  void networkMode(int slot){if(catalog==null){afterRead=()->networkMode(slot);reload();return;}ReferenceUi.Modal d=new ReferenceUi.Modal(a,"网络方式 · "+Profiles.display(a,slot));choice(d,"订阅入口 + 固定出口","",false,()->{d.dismiss();for(int i=0;i<windows.length();i++)if(windows.optJSONObject(i).optJSONObject("row").optInt("slot")==slot){editInternal(windows.optJSONObject(i));return;}});choice(d,"手机网络 / 手机 VPN","",false,()->{d.dismiss();external(slot,false);});choice(d,"应用专用代理","",false,()->{d.dismiss();external(slot,true);});d.show();}
  void external(int slot,boolean proxy){ReferenceUi.Modal d=new ReferenceUi.Modal(a,proxy?"应用专用代理":"手机网络 / VPN");SharedPreferences prefs=Profiles.context(a,slot).getSharedPreferences("chat",0);EditText address=proxy?DesignUi.input(d.body,"代理地址",prefs.getString("proxy",""),"填写代理地址"):null;if(proxy)d.note("HTTP：http://主机:端口\nSOCKS：socks://主机:端口");CheckBox vpn=new CheckBox(a);vpn.setText("手机 VPN 断开时暂停联网");vpn.setTextSize(13);vpn.setChecked(prefs.getBoolean("requireExternalVpn",true));if(!proxy){d.body.addView(vpn);d.note("开启后，未连接手机 VPN 就会暂停此环境的所有网页请求；关闭后使用手机当前网络。");}else d.note("代理不可用时暂停联网，不自动切换手机直连。");JSONObject queued=NetworkChanges.pending(Profiles.context(a,slot));if("external".equals(queued.optString("action"))){JSONObject candidate=queued.optJSONObject("config");if(address!=null)address.setText(candidate.optString("proxy"));vpn.setChecked(candidate.optBoolean("requireExternalVpn",true));d.note("显示的是已保存、等待应用的配置。");}TextView error=ReferenceUi.text(a,"",12,ReferenceUi.RED,false);d.body.addView(error);String baseline=NetworkChanges.hash(Profiles.context(a,slot));d.buttons("取消",d::dismiss,"保存并应用",()->{String value=proxy?address.getText().toString().trim():"";if(proxy&&!MainActivity.validProxy(value)){address.setError("填写有效的 HTTP / SOCKS 代理地址");return;}d.primary().setEnabled(false);NetworkBridge.run(a,slot,"external",J.obj("proxy",value,"requireExternalVpn",vpn.isChecked()),baseline,(ok,message,state)->{if(closed||a.isDestroyed())return;reload();if(ok){d.dismiss();}else{error.setText(message);d.primary().setEnabled(true);d.resize();}});});d.show();}
}
