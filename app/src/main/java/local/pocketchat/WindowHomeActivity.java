package local.pocketchat;

import android.app.*;
import android.content.*;
import android.os.*;
import android.text.*;
import android.view.*;
import android.widget.*;
import org.json.*;
import java.util.*;

/** Native environment workspace. Metadata management never needs an account session. */
public class WindowHomeActivity extends ThemedActivity {
  LinearLayout root,cards,filters,selectionBar;
  TextView count,selectionCount,problem;
  EditText search;
  Button groupButton,sortButton,selectionButton,visibleSelectionButton;
  Button batchGroupButton,favoriteSelectedButton,unfavoriteSelectedButton;
  Button createButton,filterOptions,viewsButton;
  LinearLayout inbox;
  final EnvironmentSavedViews savedViews=new EnvironmentSavedViews();
  String activeView="",inboxSignature="";
  LinearLayout preparation;
  int filter,sort;
  String selectedGroup;
  boolean selecting,preparing;
  final Set<Integer> selectedIds=new LinkedHashSet<>();
  final List<Integer> visibleIds=new ArrayList<>();
  final Handler handler=new Handler(Looper.getMainLooper());
  String maintenanceSignature="",emptySignature="";
  static final String SNAPSHOT_READ_PROBLEM="环境记录暂时无法读取，请稍后重试";
  boolean workspaceVisible,snapshotReadIssue;
  EnvironmentHomeSnapshot snapshot;
  EnvironmentRefreshQueue<EnvironmentHomeSnapshot> snapshotQueue;
  final java.util.concurrent.ExecutorService snapshotWorker=java.util.concurrent.Executors.newSingleThreadExecutor(r->{Thread thread=new Thread(r,"environment-workspace-read");thread.setDaemon(true);return thread;});
  LinearLayout environmentList,maintenanceRows,emptyRows;
  final Map<String,EnvironmentRow> rowViews=new LinkedHashMap<>();
  final Button[] filterButtons=new Button[5];
  final Runnable update=new Runnable(){public void run(){if(!workspaceVisible)return;if(snapshotQueue!=null)snapshotQueue.request();handler.postDelayed(this,3000);}};
  void requestSnapshot(){if(snapshotQueue!=null)snapshotQueue.request();}
  void renderCached(){if(workspaceVisible&&snapshot!=null)renderSnapshot(snapshot);}
  final Runnable searchRender=this::renderCached;
  void scheduleSearch(){if(!workspaceVisible)return;handler.removeCallbacks(searchRender);handler.postDelayed(searchRender,48);}


  int dp(int n){return DesignUi.dp(this,n);}
  void showProblem(String message){snapshotReadIssue=SNAPSHOT_READ_PROBLEM.equals(message);problem.setText(message);problem.setVisibility(message.isEmpty()?View.GONE:View.VISIBLE);}

  @Override public void onCreate(Bundle state){
    super.onCreate(state);
    root=DesignUi.screen(this);
    LinearLayout box=DesignUi.body(this,root,"环境管理",null);
    LinearLayout tools=DesignUi.row(this);
    count=DesignUi.text(this,"",13,DesignUi.MUTED);
    boolean largeText=getResources().getConfiguration().fontScale>=1.4f;
    if(largeText){LinearLayout.LayoutParams cp=new LinearLayout.LayoutParams(-1,-2);cp.bottomMargin=dp(6);box.addView(count,cp);tools.setGravity(Gravity.END|Gravity.CENTER_VERTICAL);}
    else tools.addView(count,new LinearLayout.LayoutParams(0,-2,1));
    Button actionSearch=ReferenceUi.iconButton(this,"search","搜索操作",()->ActionSearchUi.show(this));if(!largeText)tools.addView(actionSearch,new LinearLayout.LayoutParams(dp(48),dp(48)));
    selectionButton=DesignUi.button(this,"多选",false,()->setSelecting(!selecting));
    tools.addView(selectionButton,new LinearLayout.LayoutParams(DesignUi.actionWidth(selectionButton,64),dp(48)));
    LinearLayout.LayoutParams createParams=new LinearLayout.LayoutParams(dp(112),dp(48));
    createParams.leftMargin=dp(8);
    createButton=DesignUi.button(this,"＋ 新建环境",true,()->createWindow());createParams.width=DesignUi.actionWidth(createButton,112);tools.addView(createButton,createParams);
    box.addView(tools);
    LinearLayout shortcuts=DesignUi.row(this);
    Button switcher=DesignUi.button(this,"快速切换环境",false,()->EnvironmentSwitcherUi.show(this));
    viewsButton=DesignUi.button(this,"工作视图",false,this::chooseView);
    Button commands=DesignUi.button(this,"搜索操作",false,()->ActionSearchUi.show(this));
    for(Button action:largeText?new Button[]{switcher,viewsButton,commands}:new Button[]{switcher,viewsButton}){LinearLayout.LayoutParams shortcut=new LinearLayout.LayoutParams(largeText?-1:0,-2,largeText?0:1);if(shortcuts.getChildCount()>0){if(largeText)shortcut.topMargin=dp(6);else shortcut.leftMargin=dp(8);}shortcuts.addView(action,shortcut);}
    if(largeText)shortcuts.setOrientation(LinearLayout.VERTICAL);
    box.addView(shortcuts);
    inbox=DesignUi.column(this);box.addView(inbox);
    preparation=DesignUi.progress(this,"正在创建环境…","完成后会打开新环境，请稍候。");
    preparation.setVisibility(View.GONE);DesignUi.addCard(box,preparation);
    LinearLayout searchRow=DesignUi.row(this),searchBox=DesignUi.column(this);
    search=DesignUi.searchInput(searchBox,largeText?"搜索环境":"搜索名称、分组或备注");
    search.setFilters(new InputFilter[]{new InputFilter.LengthFilter(120)});
    search.setContentDescription("搜索环境");searchRow.addView(searchBox,new LinearLayout.LayoutParams(0,-2,1));
    filterOptions=DesignUi.button(this,"筛选",false,this::chooseFilters);LinearLayout.LayoutParams op=new LinearLayout.LayoutParams(DesignUi.actionWidth(filterOptions,72),dp(48));op.leftMargin=dp(8);searchRow.addView(filterOptions,op);
    LinearLayout.LayoutParams sp=new LinearLayout.LayoutParams(-1,-2);sp.topMargin=dp(8);box.addView(searchRow,sp);
    search.addTextChangedListener(new TextWatcher(){
      public void beforeTextChanged(CharSequence s,int x,int c,int f){}
      public void onTextChanged(CharSequence s,int x,int b,int c){scheduleSearch();}
      public void afterTextChanged(Editable e){}
    });
    groupButton=DesignUi.button(this,"全部分组 ▾",false,this::chooseGroup);
    sortButton=DesignUi.button(this,"编号排序 ▾",false,this::chooseSort);
    HorizontalScrollView filterScroll=new HorizontalScrollView(this);
    filterScroll.setHorizontalScrollBarEnabled(false);
    filterScroll.setHorizontalFadingEdgeEnabled(true);filterScroll.setFadingEdgeLength(dp(12));
    filters=DesignUi.row(this);filterScroll.addView(filters);
    String[] filterNames={"全部","收藏","运行中","等待回复","需处理"};
    for(int i=0;i<filterButtons.length;i++){final int target=i;Button button=ReferenceUi.link(this,filterNames[i]+" 0",()->{filter=target;renderCached();});button.setTextSize(12);button.setSingleLine(true);filterButtons[i]=button;LinearLayout.LayoutParams params=new LinearLayout.LayoutParams(DesignUi.actionWidth(button,i==3?100:88),dp(48));params.rightMargin=dp(6);filters.addView(button,params);}

    LinearLayout.LayoutParams fp=new LinearLayout.LayoutParams(-1,dp(48));
    fp.topMargin=dp(8);box.addView(filterScroll,fp);
    problem=DesignUi.text(this,"",13,DesignUi.RED);problem.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);problem.setVisibility(View.GONE);box.addView(problem);
    cards=DesignUi.column(this);box.addView(cards);
    maintenanceRows=DesignUi.column(this);cards.addView(maintenanceRows);
    environmentList=DesignUi.group(this);DesignUi.addCard(cards,environmentList);
    emptyRows=DesignUi.column(this);cards.addView(emptyRows);

    selectionBar=DesignUi.column(this);
    selectionBar.setPadding(dp(14),dp(8),dp(14),dp(10));
    selectionBar.setBackground(DesignUi.surface(this,DesignUi.CARD,0,DesignUi.LINE));
    LinearLayout selectionTools=DesignUi.row(this);
    selectionCount=DesignUi.text(this,"",13,DesignUi.TEXT);
    if(largeText)selectionTools.setOrientation(LinearLayout.VERTICAL);
    selectionTools.addView(selectionCount,new LinearLayout.LayoutParams(largeText?-1:0,-2,largeText?0:1));
    visibleSelectionButton=DesignUi.button(this,"全选当前结果",false,()->selectVisible());
    visibleSelectionButton.setTextSize(12);
    LinearLayout.LayoutParams visibleParams=new LinearLayout.LayoutParams(largeText?-1:dp(128),-2);if(largeText)visibleParams.topMargin=dp(6);
    selectionTools.addView(visibleSelectionButton,visibleParams);
    selectionBar.addView(selectionTools);
    LinearLayout batchActions=DesignUi.row(this);
    batchActions.setPadding(0,dp(8),0,0);
    batchGroupButton=DesignUi.button(this,"批量分组",true,()->batchGroup());
    favoriteSelectedButton=DesignUi.button(this,"收藏",false,()->batchFavorite(true));
    unfavoriteSelectedButton=DesignUi.button(this,"取消收藏",false,()->batchFavorite(false));
    Button[] actions={batchGroupButton,favoriteSelectedButton,unfavoriteSelectedButton};
    if(largeText)batchActions.setOrientation(LinearLayout.VERTICAL);
    for(int i=0;i<actions.length;i++){
      actions[i].setTextSize(13);
      LinearLayout.LayoutParams params=new LinearLayout.LayoutParams(largeText?-1:0,-2,largeText?0:1);
      if(i>0){if(largeText)params.topMargin=dp(6);else params.leftMargin=dp(6);}
      batchActions.addView(actions[i],params);
    }
    selectionBar.addView(batchActions);root.addView(selectionBar);
    root.addView(DesignUi.nav(this,WorkspaceNavigation.ENVIRONMENTS,n->WorkspaceNavigation.select(this,WorkspaceNavigation.ENVIRONMENTS,n),null));
    setContentView(root);
    Context workspaceContext=Profiles.global(this);
    snapshotQueue=new EnvironmentRefreshQueue<>(snapshotWorker,task->handler.post(task),()->EnvironmentHomeSnapshot.read(workspaceContext),this::acceptSnapshot,error->{if(workspaceVisible)showProblem(SNAPSHOT_READ_PROBLEM);});

    if(state==null)applyView(savedViews.current(this));
    if(state!=null){
      filter=Math.max(0,Math.min(4,state.getInt("filter")));
      sort=Math.max(0,Math.min(2,state.getInt("sort")));
      selectedGroup=state.getString("group");activeView=state.getString("activeView","");selecting=state.getBoolean("selecting");
      int[] ids=state.getIntArray("selectedIds");
      if(selecting&&ids!=null)for(int id:ids)selectedIds.add(id);
      search.setText(state.getString("query",""));
    }
    refresh();
  }
  @Override protected void onSaveInstanceState(Bundle state){
    super.onSaveInstanceState(state);
    state.putInt("filter",filter);state.putInt("sort",sort);state.putString("group",selectedGroup);state.putString("activeView",activeView);
    state.putString("query",search.getText().toString());state.putBoolean("selecting",selecting);
    state.putIntArray("selectedIds",selectedIds.stream().mapToInt(Integer::intValue).toArray());
  }
  @Override protected void onResume(){super.onResume();workspaceVisible=true;renderCached();if(snapshotQueue!=null)snapshotQueue.visible(true);handler.removeCallbacks(update);handler.postDelayed(update,3000);}
  @Override protected void onPause(){workspaceVisible=false;handler.removeCallbacks(update);handler.removeCallbacks(searchRender);if(snapshotQueue!=null)snapshotQueue.visible(false);if(search!=null)savedViews.remember(this,currentView(activeView));super.onPause();}
  @Override protected void onDestroy(){workspaceVisible=false;handler.removeCallbacksAndMessages(null);if(snapshotQueue!=null)snapshotQueue.close();snapshotWorker.shutdown();super.onDestroy();}
  @Override protected void onNewIntent(Intent intent){super.onNewIntent(intent);setIntent(intent);refresh();}
  @Override public void onBackPressed(){if(selecting){setSelecting(false);return;}super.onBackPressed();}
  Set<Integer> live(){return snapshot==null?Collections.emptySet():snapshot.running;}
  int lastWindow(){return AppSettings.recentSlot(this);}
  void chooseFilters(){
    LinearLayout choices=DesignUi.column(this);choices.setPadding(dp(18),dp(8),dp(18),dp(16));
    groupButton=DesignUi.button(this,(selectedGroup==null?"全部分组":selectedGroup.isEmpty()?"未分组":selectedGroup)+" ▾",false,this::chooseGroup);
    sortButton=DesignUi.button(this,new String[]{"编号排序 ▾","最近使用 ▾","名称排序 ▾"}[sort],false,this::chooseSort);
    choices.addView(groupButton,new LinearLayout.LayoutParams(-1,dp(48)));LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,dp(48));p.topMargin=dp(8);choices.addView(sortButton,p);
    AppAppearance.dialog(this).setTitle("筛选与排序").setView(choices).setPositiveButton("完成",null).show();
  }
  void chooseGroup(){
    List<String> groups=new ArrayList<>();groups.add(null);groups.add("");
    JSONArray rows=snapshot==null?new JSONArray():snapshot.rows;
    for(int i=0;i<rows.length();i++){
      JSONObject row=rows.optJSONObject(i);String group=row.optString("group");
      if(row.optBoolean("created")&&!group.isEmpty()&&!groups.contains(group))groups.add(group);
    }
    String[] names=new String[groups.size()];
    for(int i=0;i<names.length;i++)names[i]=groups.get(i)==null?"全部分组":groups.get(i).isEmpty()?"未分组":groups.get(i);
    AppAppearance.dialog(this).setTitle("按分组查看")
      .setSingleChoiceItems(names,groups.indexOf(selectedGroup),(d,n)->{
        selectedGroup=groups.get(n);d.dismiss();renderCached();
      }).setNegativeButton("取消",null).show();
  }
  void chooseSort(){
    AppAppearance.dialog(this).setTitle("环境排序")
      .setSingleChoiceItems(new String[]{"编号排序","最近使用","名称排序"},sort,(d,n)->{
        sort=n;d.dismiss();renderCached();
      }).setNegativeButton("取消",null).show();
  }
  static boolean matches(JSONObject row,String query,String group){
    if(group!=null&&!group.equals(row.optString("group")))return false;
    return EnvironmentWorkspacePolicy.matches(row,query);
  }
  static String recentUse(long opened,long now){
    if(opened<=0)return "尚未打开";
    long elapsed=Math.max(0,now-opened);
    if(elapsed<60000)return "刚刚";
    if(elapsed<3600000)return elapsed/60000+" 分钟前";
    if(elapsed<86400000)return elapsed/3600000+" 小时前";
    if(elapsed<604800000)return elapsed/86400000+" 天前";
    return new java.text.SimpleDateFormat("MM-dd HH:mm",Locale.getDefault()).format(new Date(opened));
  }
  static String networkStatus(JSONObject row,boolean active,boolean fresh){return EnvironmentPresentation.network(row,active,fresh);}
  void acceptSnapshot(EnvironmentHomeSnapshot value){
    if(!workspaceVisible||isDestroyed()||isFinishing())return;
    if(snapshotReadIssue)showProblem("");snapshot=value;DesignUi.Stars.setting(value.stars);renderSnapshot(value);
  }
  void refresh(){requestSnapshot();renderCached();}
  void renderSnapshot(EnvironmentHomeSnapshot value){
    if(cards==null||selectionBar==null)return;
    JSONArray rows=value.rows;Set<Integer> running=value.running,created=new HashSet<>();long now=System.currentTimeMillis();
    int[] counts=new int[5];List<JSONObject> ordered=new ArrayList<>();
    for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);if(!EnvironmentWorkspacePolicy.eligible(row))continue;ordered.add(row);created.add(row.optInt("slot"));counts[0]++;boolean active=EnvironmentPresentation.active(row,running);if(row.optBoolean("favorite"))counts[1]++;if(active)counts[2]++;if(row.optBoolean("waiting")&&active)counts[3]++;if(!row.optString("problem").isEmpty())counts[4]++;}
    selectedIds.retainAll(created);String query=search.getText().toString().trim();String[] searchTokens=EnvironmentSearchIndex.tokens(query);
    renderInbox(rows,running,now);updateViewLabel();
    setText(groupButton,(selectedGroup==null?"全部分组":selectedGroup.isEmpty()?"未分组":selectedGroup)+" ▾");setText(sortButton,new String[]{"编号排序 ▾","最近使用 ▾","名称排序 ▾"}[sort]);
    setText(filterOptions,selectedGroup!=null||sort!=0?"筛选 ●":"筛选");filterOptions.setContentDescription("筛选与排序，当前分组："+(selectedGroup==null?"全部":selectedGroup.isEmpty()?"未分组":selectedGroup));
    int filterWidth=DesignUi.actionWidth(filterOptions,72);if(filterOptions.getLayoutParams().width!=filterWidth){filterOptions.getLayoutParams().width=filterWidth;filterOptions.requestLayout();}
    String[] labels={"全部","收藏","运行中","等待回复","需处理"};
    for(int i=0;i<filterButtons.length;i++){Button button=filterButtons[i];setText(button,labels[i]+" "+counts[i]);boolean chosen=i==filter;if(button.isSelected()!=chosen||button.getTag()==null){button.setTag(Boolean.TRUE);button.setSelected(chosen);button.setTextColor(chosen?DesignUi.BLUE:DesignUi.MUTED);button.setBackground(chosen?DesignUi.surface(this,0xffeaf1ff,8,0xffb6cdfa):Ui.ripple(this,android.graphics.Color.TRANSPARENT,9));}int width=DesignUi.actionWidth(button,i==3?100:88);if(button.getLayoutParams().width!=width){button.getLayoutParams().width=width;button.requestLayout();}}
    if(sort==1)ordered.sort((l,r)->Long.compare(r.optLong("opened"),l.optLong("opened")));if(sort==2)ordered.sort((l,r)->l.optString("name").compareToIgnoreCase(r.optString("name")));
    renderMaintenance(rows);visibleIds.clear();Set<String> retained=new HashSet<>();int index=0;
    ScrollView scroll=cards.getParent() instanceof ScrollView?(ScrollView)cards.getParent():null; // body owns scroll; locate below when needed.
    View parent=cards;while(parent.getParent() instanceof View&&!(parent.getParent() instanceof ScrollView))parent=(View)parent.getParent();if(parent.getParent() instanceof ScrollView)scroll=(ScrollView)parent.getParent();
    final ScrollView scrolling=scroll;int oldY=scrolling==null?0:scrolling.getScrollY();boolean structure=false;
    for(JSONObject row:ordered){String key=EnvironmentPresentation.key(row);retained.add(key);EnvironmentRow holder=rowViews.get(key);if(holder==null){holder=new EnvironmentRow();rowViews.put(key,holder);structure=true;}holder.value=row;
      boolean show=EnvironmentPresentation.visible(row,running,filter,"",selectedGroup)&&value.search.matches(row,searchTokens);if(show)visibleIds.add(row.optInt("slot"));
      if(holder.root.getVisibility()!=(show?View.VISIBLE:View.GONE)){holder.root.setVisibility(show?View.VISIBLE:View.GONE);structure=true;}
      if(show)holder.bind(row,running,now,value.defaultSlot);
      if(index>=environmentList.getChildCount()||environmentList.getChildAt(index)!=holder.root){if(holder.root.getParent()==environmentList)environmentList.removeView(holder.root);environmentList.addView(holder.root,index,new LinearLayout.LayoutParams(-1,-2));structure=true;}index++;
    }
    for(Iterator<Map.Entry<String,EnvironmentRow>> it=rowViews.entrySet().iterator();it.hasNext();){Map.Entry<String,EnvironmentRow> entry=it.next();if(!retained.contains(entry.getKey())){environmentList.removeView(entry.getValue().root);it.remove();structure=true;}}
    int visibleIndex=0;for(int i=0;i<environmentList.getChildCount();i++){View child=environmentList.getChildAt(i);if(child.getVisibility()==View.VISIBLE){EnvironmentRow holder=null;for(EnvironmentRow candidate:rowViews.values())if(candidate.root==child){holder=candidate;break;}if(holder!=null)holder.separator.setVisibility(visibleIndex++==0?View.GONE:View.VISIBLE);}}
    environmentList.setVisibility(visibleIds.isEmpty()?View.GONE:View.VISIBLE);
    int maintenance=0;for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);if(row.optBoolean("resetting")||row.optBoolean("deleting"))maintenance++;}
    setText(count,counts[0]==0&&maintenance>0?maintenance+" 个环境待完成维护":visibleIds.size()==counts[0]?counts[0]+" 个环境":"显示 "+visibleIds.size()+" / "+counts[0]);
    String empty=visibleIds.isEmpty()?(counts[0]==0&&maintenance>0?"maintenance":"filtered"):"";if(!empty.equals(emptySignature)){emptySignature=empty;emptyRows.removeAllViews();if("maintenance".equals(empty))DesignUi.note(emptyRows,"有环境等待完成维护，请点击上方继续重置或清理。");else if("filtered".equals(empty))DesignUi.empty(emptyRows,"没有匹配的环境","试试其他关键词，或重置分组与状态筛选。","重置筛选",()->{filter=0;selectedGroup=null;search.setText("");renderCached();});}
    updateSelectionBar(rows);if(structure&&scrolling!=null)scrolling.post(()->{if(workspaceVisible)scrolling.scrollTo(0,oldY);});
  }
  static void setText(TextView view,String text){if(!android.text.TextUtils.equals(view.getText(),text))view.setText(text);}
  void renderMaintenance(JSONArray rows){
    JSONArray signature=new JSONArray();for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);if(row.optBoolean("deleting")||row.optBoolean("resetting"))signature.put(new JSONArray().put(EnvironmentPresentation.key(row)).put(row.optString("name")).put(row.optBoolean("deleting")).put(row.optBoolean("resetting")));}
    if(signature.toString().equals(maintenanceSignature))return;maintenanceSignature=signature.toString();maintenanceRows.removeAllViews();
    for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);int id=row.optInt("slot");if(row.optBoolean("deleting"))DesignUi.action(maintenanceRows,"继续清理 · "+row.optString("name"),false,()->{try{startDelete(new EnvironmentSpec.Identity(id,row.optInt("generation"),row.getString("environmentId")));}catch(Exception invalid){showProblem("删除环境已变化，请刷新列表");}});else if(row.optBoolean("resetting"))DesignUi.action(maintenanceRows,"继续重置登录 · "+row.optString("name"),false,()->startReset(id,row.optInt("generation")-1,row.optString("environmentId")));}
  }
  final class EnvironmentRow {
    final LinearLayout root=DesignUi.column(WindowHomeActivity.this),card=DesignUi.card(WindowHomeActivity.this),head=DesignUi.row(WindowHomeActivity.this),actions=DesignUi.row(WindowHomeActivity.this);
    final View separator=new View(WindowHomeActivity.this);final CheckBox check=new CheckBox(WindowHomeActivity.this);
    final TextView number=DesignUi.text(WindowHomeActivity.this,"",12,DesignUi.MUTED),name=DesignUi.text(WindowHomeActivity.this,"",16,DesignUi.TEXT),sub=DesignUi.text(WindowHomeActivity.this,"",12,DesignUi.MUTED),badge=DesignUi.badge(WindowHomeActivity.this,"",DesignUi.MUTED),network=DesignUi.text(WindowHomeActivity.this,"",12,DesignUi.MUTED),recent=DesignUi.text(WindowHomeActivity.this,"",12,DesignUi.MUTED);
    JSONObject value;boolean syncing;
    final Button open=ReferenceUi.small(WindowHomeActivity.this,"打开环境",true,()->openExpected(value,"chat",true)),more=ReferenceUi.more(WindowHomeActivity.this,()->{if(value!=null)menu(value.optInt("slot"));});
    final EnvironmentPresentation.Binding binding=new EnvironmentPresentation.Binding();
    EnvironmentRow(){
      separator.setBackgroundColor(DesignUi.LINE);LinearLayout.LayoutParams line=new LinearLayout.LayoutParams(-1,Math.max(1,dp(1)/2));line.leftMargin=dp(60);line.rightMargin=dp(16);root.addView(separator,line);root.addView(card);
      card.setClickable(true);card.setFocusable(true);card.setOnClickListener(v->{if(value!=null){if(selecting)toggleSelection(value.optInt("slot"));else openExpected(value,"chat",true);}});card.setOnLongClickListener(v->{if(value!=null)toggleSelection(value.optInt("slot"));return true;});
      check.setOnCheckedChangeListener((button,selected)->{if(!syncing&&value!=null)toggleSelection(value.optInt("slot"));});head.addView(check,new LinearLayout.LayoutParams(dp(48),dp(48)));number.setSingleLine(true);number.setGravity(Gravity.CENTER);head.addView(number,new LinearLayout.LayoutParams(dp(28),-2));
      LinearLayout titles=DesignUi.column(WindowHomeActivity.this);titles.setPadding(dp(10),0,dp(6),0);name.setTypeface(android.graphics.Typeface.create("sans-serif-medium",android.graphics.Typeface.NORMAL));name.setSingleLine();name.setEllipsize(TextUtils.TruncateAt.END);sub.setSingleLine();sub.setEllipsize(TextUtils.TruncateAt.END);titles.addView(name);titles.addView(sub);head.addView(titles,new LinearLayout.LayoutParams(0,-2,1));head.addView(badge);card.addView(head);network.setMaxLines(2);network.setEllipsize(TextUtils.TruncateAt.END);network.setPadding(0,dp(8),0,dp(4));card.addView(network);
      actions.setPadding(0,dp(4),0,0);actions.addView(recent,new LinearLayout.LayoutParams(0,-2,1));open.setTextSize(13);open.setSingleLine(true);open.setPadding(dp(4),0,dp(4),0);actions.addView(open,new LinearLayout.LayoutParams(DesignUi.actionWidth(open,96),dp(48)));LinearLayout.LayoutParams extra=new LinearLayout.LayoutParams(dp(48),dp(48));extra.leftMargin=dp(6);actions.addView(more,extra);card.addView(actions);
    }
    void bind(JSONObject row,Set<Integer> running,long now,int defaultSlot){
      if(!binding.changed(EnvironmentPresentation.stamp(row,running,now,defaultSlot,selecting,selectedIds.contains(row.optInt("slot")))))return;
      int id=row.optInt("slot");boolean active=EnvironmentPresentation.active(row,running),fresh=EnvironmentPresentation.fresh(row,now),problem=!row.optString("problem").isEmpty();
      card.setContentDescription((selecting?"选择环境：":"打开环境：")+row.optString("name"));card.setBackground(Ui.ripple(WindowHomeActivity.this,selecting&&selectedIds.contains(id)?0xfff0f5ff:DesignUi.CARD,0));syncing=true;check.setChecked(selectedIds.contains(id));syncing=false;check.setVisibility(selecting?View.VISIBLE:View.GONE);number.setVisibility(selecting?View.GONE:View.VISIBLE);check.setContentDescription("选择环境 "+String.format(Locale.ROOT,"%02d",id+1)+" "+row.optString("name"));setText(number,String.format(Locale.ROOT,"%02d",id+1));setText(name,(row.optBoolean("favorite")?"★ ":"")+row.optString("name"));String group=row.optString("group").isEmpty()?"未分组":row.optString("group");setText(sub,(selecting?String.format(Locale.ROOT,"%02d",id+1)+" · ":"")+(row.optBoolean("desktopSite")?"电脑版 · ":"")+group+(id==defaultSlot?" · 默认":"")+(!row.optString("draft").isEmpty()?" · 草稿":""));
      int color=problem?DesignUi.RED:active?DesignUi.GREEN:DesignUi.MUTED;setText(badge,EnvironmentPresentation.status(row,active,fresh));badge.setTextColor(color);badge.setBackground(DesignUi.surface(WindowHomeActivity.this,(color&0x00ffffff)|0x11000000,7,android.graphics.Color.TRANSPARENT));setText(network,networkStatus(row,active,fresh));network.setTextColor(problem?DesignUi.RED:DesignUi.MUTED);setText(recent,row.optLong("opened")<=0?"":"最近 "+recentUse(row.optLong("opened"),now));open.setVisibility(selecting?View.GONE:View.VISIBLE);more.setVisibility(selecting?View.GONE:View.VISIBLE);actions.setVisibility(selecting&&row.optLong("opened")<=0?View.GONE:View.VISIBLE);open.setContentDescription("打开环境 "+row.optString("name"));more.setContentDescription("更多操作 "+row.optString("name"));
    }
  }
  JSONObject currentView(String name){return EnvironmentSavedViews.view(name,search.getText().toString(),selectedGroup,filter,sort);}
  void applyView(JSONObject view){
    if(view==null)return;
    filter=view.optInt("filter");sort=view.optInt("sort");selectedGroup=view.isNull("group")?null:view.optString("group");activeView=view.optString("name");
    selecting=false;selectedIds.clear();search.setText(view.optString("query"));handler.removeCallbacks(searchRender);renderCached();
  }
  void updateViewLabel(){
    JSONObject saved=savedViews.find(this,activeView);
    boolean matches=saved!=null&&EnvironmentSavedViews.sameSettings(saved,currentView(activeView));
    setText(viewsButton,matches?"视图："+activeView:"工作视图"+(saved==null?"":" · 已修改"));
    viewsButton.setContentDescription(matches?"当前工作视图："+activeView+"，点按切换":"切换或保存工作视图");
  }
  void chooseView(){
    ReferenceUi.Modal panel=new ReferenceUi.Modal(this,"工作视图").asSheet();
    DesignUi.note(panel.body,"保存搜索、分组、状态和排序，下次一键回到同一工作范围。");
    ReferenceUi.menuAction(panel,"保存当前视图",()->{panel.dismiss();saveView();});
    ReferenceUi.menuAction(panel,"查看全部环境",()->{panel.dismiss();applyView(EnvironmentSavedViews.view("","",null,0,0));});
    JSONArray views=savedViews.list(this);
    for(int i=0;i<views.length();i++){
      JSONObject view=views.optJSONObject(i);if(view==null)continue;
      ReferenceUi.menuAction(panel,view.optString("name"),()->{panel.dismiss();applyView(view);});
    }
    if(views.length()>0)ReferenceUi.menuAction(panel,"管理已保存视图",()->{panel.dismiss();manageViews();});
    panel.show();
  }
  void saveView(){
    LinearLayout box=DesignUi.column(this);box.setPadding(dp(18),0,dp(18),dp(16));
    EditText name=DesignUi.input(box,"视图名称",activeView,"例如：工作组待处理");name.setFilters(new InputFilter[]{new InputFilter.LengthFilter(24)});
    DesignUi.note(box,"同名视图会更新为当前条件。保存视图不会更改环境配置或多选结果。");
    AlertDialog dialog=AppAppearance.dialog(this).setTitle("保存工作视图").setView(box).setNegativeButton("取消",null).setPositiveButton("保存",null).create();dialog.show();
    dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{
      String title=name.getText().toString().trim();if(title.isEmpty()){name.setError("请输入视图名称");return;}
      if(!savedViews.save(this,currentView(title))){name.setError("视图未保存；最多 8 个，请删除多余视图或重试");return;}
      activeView=title;updateViewLabel();dialog.dismiss();
    });
  }
  void manageViews(){
    JSONArray views=savedViews.list(this);String[] names=new String[views.length()];for(int i=0;i<names.length;i++)names[i]=views.optJSONObject(i).optString("name");
    AppAppearance.dialog(this).setTitle("删除已保存视图").setItems(names,(d,n)->{
      String name=names[n];AppAppearance.dialog(this).setTitle("删除视图“"+name+"”？").setMessage("只移除此筛选组合，环境和配置会保留。")
        .setNegativeButton("取消",null).setPositiveButton("删除视图",(prompt,which)->{savedViews.remove(this,name);if(name.equals(activeView))activeView="";updateViewLabel();}).show();
    }).setNegativeButton("完成",null).show();
  }
  void renderInbox(JSONArray rows,Set<Integer> running,long now){
    List<JSONObject> tasks=EnvironmentWorkspacePolicy.actionable(rows,running,now);
    int issues=0,drafts=0,waiting=0;for(JSONObject row:tasks){if(!row.optString("problem").isEmpty())issues++;if(!row.optString("draft").isEmpty())drafts++;if(row.optBoolean("waiting")&&EnvironmentWorkspacePolicy.running(row,running,now))waiting++;}
    String next=selecting+":"+tasks.size()+":"+issues+":"+drafts+":"+waiting;if(next.equals(inboxSignature))return;inboxSignature=next;
    inbox.removeAllViews();if(selecting){inbox.setVisibility(View.GONE);return;}inbox.setVisibility(View.VISIBLE);
    if(tasks.isEmpty())return;
    LinearLayout card=DesignUi.card(this);TextView title=ReferenceUi.text(this,"全部环境任务 · "+tasks.size()+" 个环境",16,DesignUi.TEXT,true);card.addView(title);
    DesignUi.note(card,(issues>0?issues+" 个连接需处理  ":"")+(drafts>0?drafts+" 个配置草稿  ":"")+(waiting>0?waiting+" 个正在等待回复":""));
    DesignUi.action(card,"查看并继续任务",true,this::showInbox);DesignUi.addCard(inbox,card);
  }
  void showInbox(){
    ReferenceUi.Modal panel=new ReferenceUi.Modal(this,"环境任务收件箱").asSheet();
    List<JSONObject> tasks=EnvironmentWorkspacePolicy.actionable(snapshot==null?new JSONArray():snapshot.rows,live(),System.currentTimeMillis());
    if(tasks.isEmpty())DesignUi.note(panel.body,"当前没有待处理的连接、配置草稿或正在等待的回复。");
    for(JSONObject row:tasks){
      LinearLayout card=DesignUi.card(this);card.addView(ReferenceUi.text(this,row.optString("name"),16,DesignUi.TEXT,true));
      boolean issue=!row.optString("problem").isEmpty(),draft=!row.optString("draft").isEmpty();
      if(issue){DesignUi.note(card,(EnvironmentWorkspacePolicy.running(row,live(),System.currentTimeMillis())?"":"上次记录 · ")+row.optString("problem"));DesignUi.action(card,"排查此环境连接",true,()->{panel.dismiss();openExpected(row,"network",false);});}
      if(draft){DesignUi.note(card,"已保存环境配置草稿，尚未应用。");DesignUi.action(card,"继续编辑配置",!issue,()->{panel.dismiss();openExpected(row,"edit",false);});}
      if(row.optBoolean("waiting")&&EnvironmentWorkspacePolicy.running(row,live(),System.currentTimeMillis()))DesignUi.note(card,"此环境正在等待回复，可切回原会话查看。");
      DesignUi.action(card,"回到原会话",!issue&&!draft,()->{panel.dismiss();openExpected(row,"chat",false);});DesignUi.addCard(panel.body,card);
    }
    DesignUi.note(panel.body,"任务来自本机环境状态；不自动重发消息或应用配置。");panel.show();
  }
  void openExpected(JSONObject expected,String action,boolean overview){
    if(!EnvironmentSwitcherUi.open(this,expected,action,overview))showProblem("环境已变化，请刷新后重新选择");
  }
  void setSelecting(boolean value){
    selecting=value;if(!value)selectedIds.clear();renderCached();
  }
  void toggleSelection(int id){
    if(snapshot==null)return;boolean created=false;for(int i=0;i<snapshot.rows.length();i++){JSONObject row=snapshot.rows.optJSONObject(i);if(row.optInt("slot")==id&&EnvironmentWorkspacePolicy.eligible(row)){created=true;break;}}if(!created)return;
    selecting=true;if(!selectedIds.remove(id))selectedIds.add(id);renderCached();
  }
  void selectVisible(){
    if(visibleIds.isEmpty())return;
    selecting=true;
    if(selectedIds.containsAll(visibleIds))selectedIds.removeAll(visibleIds);else selectedIds.addAll(visibleIds);
    renderCached();
  }
  void updateSelectionBar(JSONArray rows){
    setText(selectionButton,selecting?"完成":"多选");selectionButton.setSelected(selecting);
    selectionBar.setVisibility(selecting?View.VISIBLE:View.GONE);
    int hidden=0;boolean hasFavorite=false,hasUnfavorite=false;
    for(int id:selectedIds)if(!visibleIds.contains(id))hidden++;
    for(int i=0;i<rows.length();i++){
      JSONObject row=rows.optJSONObject(i);
      if(selectedIds.contains(row.optInt("slot"))){if(row.optBoolean("favorite"))hasFavorite=true;else hasUnfavorite=true;}
    }
    setText(selectionCount,"已选 "+selectedIds.size()+" 个"+(hidden>0?"\n筛选外 "+hidden+" 个":""));
    setText(visibleSelectionButton,!visibleIds.isEmpty()&&selectedIds.containsAll(visibleIds)?"取消当前结果选中":"全选当前结果");
    visibleSelectionButton.setEnabled(!visibleIds.isEmpty());
    batchGroupButton.setEnabled(!selectedIds.isEmpty());
    favoriteSelectedButton.setEnabled(hasUnfavorite);unfavoriteSelectedButton.setEnabled(hasFavorite);
    for(Button button:new Button[]{visibleSelectionButton,batchGroupButton,favoriteSelectedButton,unfavoriteSelectedButton})button.setAlpha(button.isEnabled()?1f:.45f);
  }
  void batchFavorite(boolean favorite){
    if(selectedIds.isEmpty())return;
    ProfileCatalog.get(this).favorites(new ArrayList<>(selectedIds),favorite);
    refresh();
  }
  AlertDialog batchGroup(){
    if(selectedIds.isEmpty())return null;
    // Capture the selection when opening the form; later refreshes cannot widen its scope.
    List<Integer> ids=new ArrayList<>(selectedIds);ProfileCatalog catalog=ProfileCatalog.get(this);
    String common=catalog.item(ids.get(0)).optString("group");boolean mixed=false;
    for(int id:ids)if(!common.equals(catalog.item(id).optString("group")))mixed=true;
    LinearLayout box=DesignUi.column(this);box.setPadding(dp(18),0,dp(18),dp(16));
    EditText group=DesignUi.input(box,"目标分组",mixed?"":common,"最多 12 字，留空为未分组");
    group.setFilters(new InputFilter[]{new InputFilter.LengthFilter(12)});
    int hidden=0;for(int id:ids)if(!visibleIds.contains(id))hidden++;
    DesignUi.note(box,"修改已选 "+ids.size()+" 个环境"+(hidden>0?"（含筛选外 "+hidden+" 个）":"")+"。备注和配置草稿保留。");
    List<String> groups=new ArrayList<>();JSONArray rows=catalog.list();
    for(int i=0;i<rows.length();i++){
      JSONObject row=rows.optJSONObject(i);String value=row.optString("group");
      if(row.optBoolean("created")&&!value.isEmpty()&&!groups.contains(value))groups.add(value);
    }
    if(!groups.isEmpty())DesignUi.action(box,"选择已有分组",false,()->AppAppearance.dialog(this).setTitle("已有分组")
      .setItems(groups.toArray(new String[0]),(d,n)->group.setText(groups.get(n))).setNegativeButton("取消",null).show());
    AlertDialog dialog=AppAppearance.dialog(this).setTitle("批量分组").setView(box)
      .setPositiveButton("保存分组",null).setNegativeButton("取消",null).create();
    dialog.show();
    dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{
      catalog.group(ids,group.getText().toString());dialog.dismiss();refresh();
    });
    return dialog;
  }
  void menu(int id){
    JSONObject row=ProfileCatalog.get(this).item(id);
    if(!ProfileCatalog.get(this).available(id))return;
    String[] labels={"编辑环境","分组与备注",row.optBoolean("favorite")?"取消收藏":"收藏环境",id==AppSettings.defaultSlot(this)?"当前默认环境":"设为默认启动环境","网络配置","选择此环境","复制环境配置","重置登录数据","删除环境"};
    ReferenceUi.Modal panel=new ReferenceUi.Modal(this,row.optString("name")).asSheet();
    for(int i=0;i<labels.length;i++){final int n=i;Button item=ReferenceUi.menuAction(panel,labels[i],()->{panel.dismiss();
      if(n==0)openWindow(id,"edit");if(n==1)metadata(id);
      if(n==2){ProfileCatalog.get(this).favorite(id,!row.optBoolean("favorite"));refresh();}
      if(n==3){AppSettings.defaultSlot(this,id);refresh();}
      if(n==4)openWindow(id,"network");if(n==5)toggleSelection(id);if(n==6)copyEnvironment(id);if(n==7)resetEnvironment(id);if(n==8)deleteEnvironment(id);
    });if(i>=7)item.setTextColor(DesignUi.RED);}
    panel.show();
  }
  void startReset(int id,int generation,String environmentId){startActivity(new Intent(this,EnvironmentResetActivity.class).putExtra("slot",id).putExtra("confirmedGeneration",generation).putExtra("confirmedEnvironmentId",environmentId).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));}
  void resetEnvironment(int id){
    JSONObject row=ProfileCatalog.get(this).item(id);if(!ProfileCatalog.get(this).available(id))return;
    AlertDialog dialog=AppAppearance.dialog(this).setTitle("重置 "+row.optString("name")+" 的登录？")
      .setMessage("将关闭此环境并清理登录、Cookie、网页存储和本地草稿、聊天缓存。正在进行的回复、上传和下载任务会中断。环境名称、模板、网络与使用偏好，以及已保存的下载文件会保留；其他环境不受影响。需要在此环境重新登录 ChatGPT。")
      .setNegativeButton("取消",null).setPositiveButton("重置登录数据",(d,w)->startReset(id,row.optInt("generation"),row.optString("environmentId"))).show();dialog.getButton(AlertDialog.BUTTON_POSITIVE).setTextColor(DesignUi.RED);
  }
  void copyEnvironment(int sourceId){
    if(preparing)return;JSONObject source=ProfileCatalog.get(this).item(sourceId);int target=-1;JSONArray rows=ProfileCatalog.get(this).list();for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);if(!row.optBoolean("created")&&!row.optBoolean("deleting")&&!row.optBoolean("resetting")){target=row.optInt("slot");break;}}
    if(target<0){showProblem("环境已满，请先删除不再使用的环境");return;}
    final int destination=target;final EnvironmentSpec.Identity expected;try{expected=new EnvironmentSpec.Identity(sourceId,source.optInt("generation"),source.getString("environmentId"));}catch(Exception invalid){showProblem("源环境已变化，请重试");return;}
    LinearLayout box=DesignUi.column(this);box.setPadding(dp(18),0,dp(18),dp(16));String label=source.optString("name");if(label.length()>20)label=label.substring(0,20);EditText name=DesignUi.input(box,"新环境名称",label+" 副本","");name.setFilters(new InputFilter[]{new InputFilter.LengthFilter(24)});DesignUi.note(box,"复制已保存的浏览器模板、网络和使用偏好。账号、聊天和草稿在新环境独立，不会复制。");
    AlertDialog dialog=AppAppearance.dialog(this).setTitle("复制环境配置").setView(box).setPositiveButton("创建副本",null).setNegativeButton("取消",null).create();dialog.show();dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{String title=name.getText().toString().trim();if(title.isEmpty()){name.setError("请输入环境名称");return;}if(preparing)return;preparing=true;dialog.dismiss();createButton.setEnabled(false);preparation.setVisibility(View.VISIBLE);new Thread(()->{String error="";try{Context origin=Profiles.context(this,sourceId);EnvironmentSpec.Identity copied=Profiles.copyConfiguration(origin,destination,expected);ProfileCatalog.get(this).withIdentity(copied,()->{Profiles.rename(this,destination,title);ProfileCatalog.get(this).details(destination,source.optString("group"),source.optString("notes"));return null;});}catch(Exception failure){error=failure.getMessage()==null?"复制未完成，请重试":failure.getMessage();}String issue=error;handler.post(()->{preparing=false;if(isFinishing()||isDestroyed())return;createButton.setEnabled(true);preparation.setVisibility(View.GONE);refresh();if(!issue.isEmpty())showProblem(issue);});},"environment-copy").start();});
  }
  void startDelete(EnvironmentSpec.Identity expected){startActivity(new Intent(this,EnvironmentDeleteActivity.class).putExtra("slot",expected.slot).putExtra("confirmedGeneration",expected.generation).putExtra("confirmedEnvironmentId",expected.environmentId).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));}
  void deleteEnvironment(int id){
    JSONObject row=ProfileCatalog.get(this).item(id);final EnvironmentSpec.Identity shown;
    try{if(!row.optBoolean("created")||row.optBoolean("deleting")||row.optBoolean("resetting"))return;shown=new EnvironmentSpec.Identity(id,row.optInt("generation"),row.getString("environmentId"));}catch(Exception invalid){showProblem("环境已变化，请刷新列表");return;}
    AlertDialog dialog=AppAppearance.dialog(this).setTitle("删除 "+row.optString("name")+"？")
      .setMessage("将关闭此环境，清理它的登录、草稿、聊天缓存和网络配置。正在进行的回复和文件操作会中断。其他环境、订阅与固定出口，以及已保存到下载目录的文件会保留。")
      .setNegativeButton("取消",null).setPositiveButton("删除环境",(d,w)->{try{startDelete(ProfileCatalog.get(this).beginDelete(shown));}catch(Exception e){showProblem(e.getMessage());}}).show();dialog.getButton(AlertDialog.BUTTON_POSITIVE).setTextColor(DesignUi.RED);
  }
  void metadata(int id){
    JSONObject row=ProfileCatalog.get(this).item(id);LinearLayout box=DesignUi.column(this);
    box.setPadding(dp(18),0,dp(18),dp(16));
    EditText group=DesignUi.input(box,"分组",row.optString("group"),"留空为未分组");
    EditText notes=DesignUi.input(box,"备注",row.optString("notes"),"环境用途说明");
    group.setFilters(new InputFilter[]{new InputFilter.LengthFilter(12)});
    notes.setFilters(new InputFilter[]{new InputFilter.LengthFilter(120)});
    AlertDialog dialog=AppAppearance.dialog(this).setTitle("分组与备注 · "+row.optString("name")).setView(box)
      .setPositiveButton("保存",(d,w)->{
        ProfileCatalog.get(this).details(id,group.getText().toString(),notes.getText().toString());refresh();
      }).setNegativeButton("取消",null).show();
    DesignUi.protectEdits(this,dialog,()->!group.getText().toString().equals(row.optString("group"))||!notes.getText().toString().equals(row.optString("notes")));
  }
  void openWindow(int id,String action){
    if(id<0||id>=Profiles.MAX)return;
    if(!ProfileCatalog.get(this).available(id))return;
    if(id>0&&Build.VERSION.SDK_INT<28){showProblem("独立环境需要 Android 9 或更新版本");return;}
    ProfileCatalog.get(this).opened(id);
    Intent opening="chat".equals(action)?EnvironmentOverviewUi.opening(this,id):new Intent(this,Profiles.activity(id)).putExtra("openWindowAction",action).putExtra("returnToEnvironmentList","edit".equals(action))
      .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_REORDER_TO_FRONT);
    startActivity(opening);
  }
  void createWindow(){
    if(preparing)return;
    if(Build.VERSION.SDK_INT<28){showProblem("独立环境需要 Android 9 或更新版本");return;}
    JSONArray rows=ProfileCatalog.get(this).list();int next=-1;
    for(int i=0;i<rows.length();i++)if(!rows.optJSONObject(i).optBoolean("created")&&!rows.optJSONObject(i).optBoolean("deleting")&&!rows.optJSONObject(i).optBoolean("resetting")){next=i;break;}
    if(next<0){showProblem("已达到 8 个环境");return;}
    new Wizard(next,rows).show();
  }
  final class Wizard {
    final int id;final JSONArray windows;final Dialog dialog;
    LinearLayout body,actions;EditText name;AlertDialog exitPrompt;
    int step,sourceType,sourceSlot;String title,group="";boolean makeDefault,desktop;Spinner displayChoice;
    Wizard(int id,JSONArray windows){
      this.id=id;this.windows=windows;title="环境 "+(id+1);sourceSlot=AppSettings.defaultSlot(WindowHomeActivity.this);
      dialog=new ThemedDialog(WindowHomeActivity.this){@Override public void onBackPressed(){Wizard.this.back();}};
      dialog.setCanceledOnTouchOutside(false);
    }
    void show(){
      LinearLayout screen=DesignUi.screen(WindowHomeActivity.this);
      body=DesignUi.body(WindowHomeActivity.this,screen,"创建环境",this::back);
      actions=DesignUi.row(WindowHomeActivity.this);actions.setPadding(dp(14),dp(10),dp(14),dp(10));
      screen.addView(actions);dialog.setContentView(screen);dialog.show();
      dialog.getWindow().setBackgroundDrawableResource(android.R.color.transparent);dialog.getWindow().setLayout(-1,-1);dialog.getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);render();
    }
    void back(){if(step>0){step--;render();}else close();}
    void close(){
      if(step==0&&displayChoice!=null)desktop=displayChoice.getSelectedItemPosition()==1;
      boolean dirty=!title.equals("环境 "+(id+1))||!group.isEmpty()||sourceType!=0||makeDefault||desktop;
      if(!dirty){dialog.dismiss();return;}
      if(exitPrompt!=null&&exitPrompt.isShowing())return;
      exitPrompt=AppAppearance.dialog(WindowHomeActivity.this).setTitle("放弃创建环境？")
        .setMessage("退出后，本次填写的环境配置不会保存。")
        .setPositiveButton("继续填写",null).setNegativeButton("放弃创建",(d,w)->dialog.dismiss()).show();
      exitPrompt.getButton(AlertDialog.BUTTON_NEGATIVE).setTextColor(DesignUi.RED);
    }
    void render(){
      DesignUi.rebuild(body,false,()->{
        body.addView(DesignUi.tabs(WindowHomeActivity.this,new String[]{"基本信息","网络来源","确认创建"},step,n->{if(n<step){step=n;render();}}));
        if(step==0)basic();else if(step==1)network();else summary();
      });
      actions.removeAllViews();
      Button back=DesignUi.button(WindowHomeActivity.this,step==0?"取消创建":"上一步",false,this::back);
      Button next=DesignUi.button(WindowHomeActivity.this,step==2?"创建并打开":"下一步",true,this::next);
      actions.addView(back,new LinearLayout.LayoutParams(0,dp(48),1));
      LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(0,dp(48),1);p.leftMargin=dp(8);actions.addView(next,p);
    }
    void basic(){
      name=DesignUi.input(body,"环境名称",title,"例如：工作号、研究专用");
      name.setFilters(new InputFilter[]{new InputFilter.LengthFilter(24)});
      watch(name,()->title=name.getText().toString());
      EditText input=DesignUi.input(body,"分组（可选）",group,"最多 12 字，留空为未分组");
      input.setFilters(new InputFilter[]{new InputFilter.LengthFilter(12)});watch(input,()->group=input.getText().toString().trim());
      displayChoice=BrowserDisplayUi.add(body,desktop);
      displayChoice.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener(){public void onItemSelected(AdapterView<?> p,View v,int pos,long item){desktop=pos==1;}public void onNothingSelected(AdapterView<?> p){}});
      DesignUi.note(body,"电脑版内容更密，可用双指缩放。");
    }
    void watch(EditText input,Runnable changed){input.addTextChangedListener(new TextWatcher(){
      public void beforeTextChanged(CharSequence s,int a,int c,int f){}
      public void onTextChanged(CharSequence s,int a,int b,int c){changed.run();}
      public void afterTextChanged(Editable e){}
    });}
    void network(){
      String[] choices={"使用默认环境的网络设置","使用其他环境的网络设置","自己配置网络"};
      LinearLayout choicesBox=DesignUi.card(WindowHomeActivity.this);
      for(int i=0;i<choices.length;i++){
        final int n=i;RadioButton radio=new RadioButton(WindowHomeActivity.this);
        radio.setText(choices[i]);radio.setTextColor(DesignUi.TEXT);radio.setChecked(sourceType==i);radio.setMinHeight(dp(48));choicesBox.addView(radio);
        radio.setOnClickListener(v->{sourceType=n;render();});
      }DesignUi.addCard(body,choicesBox);
      if(sourceType==1){
        List<Integer> ids=new ArrayList<>();List<String> labels=new ArrayList<>();
        for(int i=0;i<windows.length();i++)if(windows.optJSONObject(i).optBoolean("created")){ids.add(i);labels.add(windows.optJSONObject(i).optString("name"));}
        Spinner spinner=new Spinner(WindowHomeActivity.this);spinner.setMinimumHeight(dp(48));
        spinner.setAdapter(new ArrayAdapter<>(WindowHomeActivity.this,android.R.layout.simple_spinner_dropdown_item,labels));
        spinner.setSelection(Math.max(0,ids.indexOf(sourceSlot)));
        spinner.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener(){
          public void onItemSelected(AdapterView<?> p,View v,int pos,long item){if(pos>=0&&pos<ids.size())sourceSlot=ids.get(pos);}
          public void onNothingSelected(AdapterView<?> p){}
        });body.addView(spinner);
      }
      DesignUi.note(body,"只复制网络设置，账号需要在新环境单独登录。");
    }
    void summary(){
      DesignUi.field(body,"环境名称",title);if(!group.isEmpty())DesignUi.field(body,"分组",group);
      DesignUi.field(body,"网页显示方式",BrowserDisplay.label(desktop));
      int selectedSource=sourceType==0?AppSettings.defaultSlot(WindowHomeActivity.this):sourceSlot;
      DesignUi.field(body,"网络来源",sourceType==2?"创建后手动配置":selectedSource<0?"来源环境暂不可用":Profiles.display(WindowHomeActivity.this,selectedSource));
      CheckBox selected=new CheckBox(WindowHomeActivity.this);selected.setText("设为默认环境");selected.setTextColor(DesignUi.TEXT);selected.setMinHeight(dp(48));
      DesignUi.note(body,sourceType==2?"创建后会打开网络配置页。保存网络方式后，再登录 ChatGPT。":"创建后会使用复制的网络配置打开会话，请在新环境单独登录 ChatGPT。");
      selected.setChecked(makeDefault);selected.setOnCheckedChangeListener((b,c)->makeDefault=c);body.addView(selected);
    }
    void next(){
      if(step==0){desktop=displayChoice.getSelectedItemPosition()==1;if(title.trim().isEmpty()||title.trim().length()>24){name.setError("名称需要 1–24 字");name.requestFocus();return;}title=title.trim();}
      if(step<2){step++;render();}else create();
    }
    void create(){
      // Every new environment uses its own persistent Gecko profile.
      if(preparing)return;boolean clone=sourceType!=2;int selectedSource=sourceType==0?AppSettings.defaultSlot(WindowHomeActivity.this):sourceSlot;
      if(clone&&!AppSettings.selectable(ProfileCatalog.get(WindowHomeActivity.this).item(selectedSource))){DesignUi.message(WindowHomeActivity.this,"来源环境暂不可用","请重新选择来源环境，或使用自己配置网络。");return;}
      showProblem("");preparing=true;createButton.setEnabled(false);preparation.setVisibility(View.VISIBLE);
      Context source=clone?Profiles.context(WindowHomeActivity.this,selectedSource):Profiles.global(WindowHomeActivity.this);dialog.dismiss();
      final boolean desktopSetting=desktop;
      new Thread(()->{
        String error="";try{Profiles.prepare(source,id,clone);Profiles.rename(source,id,title);ProfileCatalog.get(source).details(id,group,"");ProfileCatalog.get(source).browserDisplay(id,desktopSetting);if(makeDefault)AppSettings.defaultSlot(source,id);}
        catch(Exception e){error="环境准备失败，请重试";}
        String failure=error;handler.post(()->{
          preparing=false;if(isFinishing()||isDestroyed())return;createButton.setEnabled(true);preparation.setVisibility(View.GONE);refresh();
          if(failure.isEmpty())openWindow(id,sourceType==2?"network":"chat");else showProblem(failure);
        });
      },"window-create").start();
    }
  }
}
