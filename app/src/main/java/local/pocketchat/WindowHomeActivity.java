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
  LinearLayout root,cards,selectionBar;
  TextView count,selectionCount,problem;
  Button selectionButton,visibleSelectionButton;
  Button batchGroupButton,favoriteSelectedButton,unfavoriteSelectedButton;
  Button createButton;
  LinearLayout preparation;
  boolean selecting,preparing;
  final Map<Integer,EnvironmentSpec.Identity> selectedEnvironments=new LinkedHashMap<>();
  final Set<Integer> selectedIds=Collections.unmodifiableSet(selectedEnvironments.keySet());
  final List<Integer> visibleIds=new ArrayList<>();
  final Handler handler=new Handler(Looper.getMainLooper());
  String maintenanceSignature="",emptySignature="";
  static final String SNAPSHOT_READ_PROBLEM="环境记录暂时无法读取，请稍后重试";
  boolean workspaceVisible,snapshotReadIssue;
  EnvironmentHomeSnapshot snapshot;
  EnvironmentRefreshQueue<EnvironmentHomeSnapshot> snapshotQueue;
  final java.util.concurrent.ExecutorService snapshotWorker=java.util.concurrent.Executors.newSingleThreadExecutor(r->{Thread thread=new Thread(r,"environment-workspace-read");thread.setDaemon(true);return thread;});
  LinearLayout environmentList,maintenanceRows,emptyRows;
  GlassBackdrop backdrop;
  ScrollView workspaceScroll;
  LinearLayout workspaceContent,workspaceFooter,navigationBar;
  Object renderPositionToken;
  final Map<String,EnvironmentRow> rowViews=new LinkedHashMap<>();
  final Runnable update=new Runnable(){public void run(){if(!workspaceVisible)return;if(snapshotQueue!=null)snapshotQueue.request();handler.postDelayed(this,3000);}};
  void requestSnapshot(){if(snapshotQueue!=null)snapshotQueue.request();}
  void renderCached(){if(workspaceVisible&&snapshot!=null)renderSnapshot(snapshot);}


  int dp(int n){return DesignUi.dp(this,n);}
  void showProblem(String message){snapshotReadIssue=SNAPSHOT_READ_PROBLEM.equals(message);problem.setText(message);problem.setVisibility(message.isEmpty()?View.GONE:View.VISIBLE);}

  @Override public void onCreate(Bundle state){
    super.onCreate(state);
    if(Build.VERSION.SDK_INT>=30)getWindow().setDecorFitsSystemWindows(false);
    root=DesignUi.screen(this);
    root.setClipChildren(false);root.setClipToPadding(false);
    boolean largeText=getResources().getConfiguration().fontScale>=1.4f;
    LinearLayout heading=DesignUi.row(this);heading.setClipChildren(false);heading.setClipToPadding(false);heading.setPadding(dp(22),dp(14),dp(18),dp(14));
    LinearLayout headingCopy=DesignUi.column(this);
    TextView title=workspaceText("环境",ReferenceUi.PAGE_TITLE_SIZE,DesignUi.TEXT,true);title.setContentDescription("环境管理");
    if(Build.VERSION.SDK_INT>=28)title.setAccessibilityHeading(true);
    headingCopy.addView(title);
    count=workspaceText("",ReferenceUi.SECONDARY_SIZE,DesignUi.MUTED,false);count.setPadding(0,dp(3),dp(6),0);headingCopy.addView(count);
    heading.addView(headingCopy,new LinearLayout.LayoutParams(0,-2,1));
    selectionButton=ReferenceUi.link(this,"多选",()->setSelecting(!selecting));selectionButton.setTextSize(ReferenceUi.ACTION_SIZE);ReferenceUi.readable(selectionButton);
    LinearLayout.LayoutParams selectionAction=new LinearLayout.LayoutParams(DesignUi.actionWidth(selectionButton,54),dp(50));selectionAction.rightMargin=dp(7);heading.addView(selectionButton,selectionAction);
    createButton=ReferenceUi.iconButton(this,"plus","新建环境",this::createWindow);
    createButton.setBackground(DesignUi.glass(this,25));GlassMotion.press(createButton,true);
    heading.addView(createButton,new LinearLayout.LayoutParams(dp(50),dp(50)));
    root.addView(heading,new LinearLayout.LayoutParams(-1,-2));

    FrameLayout workspace=new FrameLayout(this);workspace.setClipChildren(false);workspace.setClipToPadding(false);
    // Clip the scrolling source, not the floating controls. Stars fills the
    // canvas clip; an unbounded source would paint over the fixed page heading.
    FrameLayout viewport=new FrameLayout(this);viewport.setClipChildren(true);viewport.setClipToPadding(true);
    workspace.addView(viewport,new FrameLayout.LayoutParams(-1,-1));
    backdrop=new GlassBackdrop(this);backdrop.setBackground(new DesignUi.Stars(this));
    viewport.addView(backdrop,new FrameLayout.LayoutParams(-1,-1));
    workspaceScroll=new ScrollView(this);workspaceScroll.setFillViewport(true);workspaceScroll.setClipToPadding(false);
    LinearLayout box=workspaceContent=DesignUi.column(this);box.setPadding(dp(20),dp(4),dp(20),dp(20));
    workspaceScroll.addView(box,new ScrollView.LayoutParams(-1,-2));backdrop.addView(workspaceScroll,new FrameLayout.LayoutParams(-1,-1));
    root.addView(workspace,new LinearLayout.LayoutParams(-1,0,1));
    preparation=DesignUi.progress(this,"正在创建环境…","完成后会打开新环境，请稍候。");
    preparation.setVisibility(View.GONE);DesignUi.addCard(box,preparation);
    problem=workspaceText("",ReferenceUi.BODY_SIZE,DesignUi.RED,false);problem.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);problem.setVisibility(View.GONE);box.addView(problem);
    cards=DesignUi.column(this);box.addView(cards);
    maintenanceRows=DesignUi.column(this);cards.addView(maintenanceRows);
    environmentList=DesignUi.column(this);cards.addView(environmentList,new LinearLayout.LayoutParams(-1,-2));
    emptyRows=DesignUi.column(this);cards.addView(emptyRows);

    workspaceFooter=DesignUi.column(this);workspaceFooter.setClipChildren(false);workspaceFooter.setClipToPadding(false);workspaceFooter.setClickable(true);
    workspace.addView(workspaceFooter,new FrameLayout.LayoutParams(-1,-2,Gravity.BOTTOM));
    selectionBar=DesignUi.column(this);
    selectionBar.setPadding(dp(14),dp(8),dp(14),dp(10));
    selectionBar.setBackground(EnvironmentWorkspaceStyle.card(this,false,false));
    LinearLayout selectionTools=DesignUi.row(this);
    selectionCount=workspaceText("",ReferenceUi.SECONDARY_SIZE,DesignUi.TEXT,false);
    selectionTools.addView(selectionCount,new LinearLayout.LayoutParams(0,-2,1));
    visibleSelectionButton=DesignUi.button(this,"全选",false,()->selectVisible());
    visibleSelectionButton.setTextSize(ReferenceUi.ACTION_SIZE);ReferenceUi.readable(visibleSelectionButton);
    visibleSelectionButton.setMaxWidth(dp(Math.max(150,(int)((getResources().getConfiguration().screenWidthDp-28)*.64f))));
    LinearLayout.LayoutParams visibleParams=new LinearLayout.LayoutParams(-2,-2);visibleParams.leftMargin=dp(8);
    selectionTools.addView(visibleSelectionButton,visibleParams);
    selectionBar.addView(selectionTools);
    LinearLayout batchActions=DesignUi.row(this);
    batchActions.setPadding(0,dp(8),0,0);
    batchGroupButton=DesignUi.button(this,"批量分组",true,()->batchGroup());
    favoriteSelectedButton=DesignUi.button(this,"收藏",false,()->batchFavorite(true));
    unfavoriteSelectedButton=DesignUi.button(this,"取消收藏",false,()->batchFavorite(false));
    Button[] actions={batchGroupButton,favoriteSelectedButton,unfavoriteSelectedButton};
    for(int i=0;i<actions.length;i++){
      actions[i].setTextSize(ReferenceUi.ACTION_SIZE);ReferenceUi.readable(actions[i]);
      LinearLayout.LayoutParams params=new LinearLayout.LayoutParams(largeText?DesignUi.actionWidth(actions[i],64):0,-2,largeText?0:1);
      if(i>0)params.leftMargin=dp(6);
      batchActions.addView(actions[i],params);
    }
    if(largeText){HorizontalScrollView batchScroll=new HorizontalScrollView(this);batchScroll.setHorizontalScrollBarEnabled(false);batchScroll.addView(batchActions);selectionBar.addView(batchScroll,new LinearLayout.LayoutParams(-1,-2));}
    else selectionBar.addView(batchActions);
    selectionBar.setVisibility(View.GONE);selectionBar.setClickable(true);
    LinearLayout.LayoutParams selectionParams=new LinearLayout.LayoutParams(-1,-2);
    selectionParams.setMargins(dp(20),dp(6),dp(20),dp(6));workspaceFooter.addView(selectionBar,selectionParams);
    navigationBar=DesignUi.workspaceNav(this,AppHub.ENVIRONMENTS,page->WorkspaceNavigation.selectPage(this,AppHub.ENVIRONMENTS,page),null);
    navigationBar.setBackground(EnvironmentWorkspaceStyle.scrollEdge(this));navigationBar.setClickable(true);navigationBar.setFocusable(false);
    workspaceFooter.addView(navigationBar,new LinearLayout.LayoutParams(-1,-2));
    backdrop.bindControls(navigationBar);backdrop.setScrollEdge(navigationBar);
    workspaceFooter.addOnLayoutChangeListener((v,l,t,r,b,ol,ot,or,ob)->{if(b-t!=ob-ot)updateWorkspaceInsets();});
    setContentView(root);
    if(Build.VERSION.SDK_INT>=30)root.setFitsSystemWindows(false);
    ReferenceUi.insets(this,root,keyboard->{navigationBar.setVisibility(keyboard?View.GONE:View.VISIBLE);updateWorkspaceInsets();});
    Context workspaceContext=Profiles.global(this);
    snapshotQueue=new EnvironmentRefreshQueue<>(snapshotWorker,task->handler.post(task),()->EnvironmentHomeSnapshot.read(workspaceContext),this::acceptSnapshot,error->{if(workspaceVisible)showProblem(SNAPSHOT_READ_PROBLEM);});

    // This small workspace always shows every eligible environment. Old saved
    // searches and views must never silently hide a card on this page.
    if(state!=null){
      selecting=state.getBoolean("selecting");
      int[] ids=state.getIntArray("selectedIds");
      int[] generations=state.getIntArray("selectedGenerations");
      String[] environments=state.getStringArray("selectedEnvironmentIds");
      // A slot from older saved state cannot prove which environment was selected.
      if(selecting&&ids!=null&&generations!=null&&environments!=null&&ids.length==generations.length&&ids.length==environments.length){
        for(int i=0;i<ids.length;i++){
          if(environments[i]==null)continue;
          try{selectedEnvironments.put(ids[i],new EnvironmentSpec.Identity(ids[i],generations[i],environments[i]));}
          catch(IllegalArgumentException invalidIdentity){}
        }
      }
    }
    refresh();
  }
  TextView workspaceText(String value,int size,int color,boolean strong){
    return ReferenceUi.workspaceText(this,value,size,color,strong);
  }
  void updateWorkspaceInsets(){
    if(workspaceContent==null||workspaceFooter==null)return;
    // Keep dock clearance inside the scrolling child. On Android 12, padding
    // on ScrollView alone can advertise accessibility overflow while its
    // touch interceptor still sees a child shorter than the outer viewport.
    int bottom=dp(20)+workspaceFooter.getHeight();
    if(workspaceContent.getPaddingBottom()!=bottom)
      workspaceContent.setPadding(dp(20),dp(4),dp(20),bottom);
  }
  int windowTop(View view){int[] point=new int[2];view.getLocationInWindow(point);return point[1];}
  int environmentContentTop(View row,ScrollView scroll){return windowTop(row)-windowTop(scroll)+scroll.getScrollY();}
  View visibleEnvironmentAnchor(){
    if(workspaceScroll==null||workspaceScroll.getScrollY()==0)return null;
    int top=windowTop(workspaceScroll),bottom=top+workspaceScroll.getHeight()-workspaceFooter.getHeight();
    for(int i=0;i<environmentList.getChildCount();i++){View row=environmentList.getChildAt(i);if(row.getVisibility()!=View.VISIBLE)continue;int y=windowTop(row);if(y+row.getHeight()>top&&y<bottom)return row;}
    return null;
  }
  void restoreEnvironmentPosition(ScrollView scroll,View anchor,int anchorTop,Object token){
    scroll.getViewTreeObserver().addOnPreDrawListener(new ViewTreeObserver.OnPreDrawListener(){
      @Override public boolean onPreDraw(){
        if(scroll.getViewTreeObserver().isAlive())scroll.getViewTreeObserver().removeOnPreDrawListener(this);
        if(!workspaceVisible||renderPositionToken!=token)return true;
        if(anchor!=null&&anchor.getParent()==environmentList&&anchor.getVisibility()==View.VISIBLE)
          // Content coordinates cancel any drag/fling since the snapshot. Only
          // the actual row-layout delta belongs in this compensation.
          scroll.scrollBy(0,environmentContentTop(anchor,scroll)-anchorTop);
        return true;
      }
    });
  }
  @Override protected void onSaveInstanceState(Bundle state){
    super.onSaveInstanceState(state);
    state.putBoolean("selecting",selecting);
    state.putIntArray("selectedIds",selectedIds.stream().mapToInt(Integer::intValue).toArray());
    state.putIntArray("selectedGenerations",selectedEnvironments.values().stream().mapToInt(id->id.generation).toArray());
    state.putStringArray("selectedEnvironmentIds",selectedEnvironments.values().stream().map(id->id.environmentId).toArray(String[]::new));
  }
  @Override protected void onResume(){super.onResume();workspaceVisible=true;if(backdrop!=null)backdrop.setGlassActive(true);renderCached();if(snapshotQueue!=null)snapshotQueue.visible(true);handler.removeCallbacks(update);handler.postDelayed(update,3000);}
  @Override protected void onPause(){workspaceVisible=false;if(backdrop!=null)backdrop.setGlassActive(false);handler.removeCallbacks(update);if(snapshotQueue!=null)snapshotQueue.visible(false);super.onPause();}
  @Override protected void onDestroy(){workspaceVisible=false;handler.removeCallbacksAndMessages(null);if(snapshotQueue!=null)snapshotQueue.close();snapshotWorker.shutdown();super.onDestroy();}
  @Override protected void onNewIntent(Intent intent){super.onNewIntent(intent);setIntent(intent);refresh();}
  @Override public void onBackPressed(){if(selecting){setSelecting(false);return;}super.onBackPressed();}
  Set<Integer> live(){return snapshot==null?Collections.emptySet():snapshot.running;}
  int lastWindow(){return AppSettings.recentSlot(this);}
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
    View anchor=visibleEnvironmentAnchor();int anchorTop=anchor==null?0:environmentContentTop(anchor,workspaceScroll);
    Object positionToken=new Object();renderPositionToken=positionToken;
    JSONArray rows=value.rows;Set<Integer> running=value.running;long now=System.currentTimeMillis();
    Map<Integer,EnvironmentSpec.Identity> created=new HashMap<>();
    List<JSONObject> ordered=new ArrayList<>();
    for(int i=0;i<rows.length();i++){
      JSONObject row=rows.optJSONObject(i);if(!EnvironmentWorkspacePolicy.eligible(row))continue;
      ordered.add(row);EnvironmentSpec.Identity identity=selectionIdentity(row);
      if(identity!=null)created.put(identity.slot,identity);
    }
    selectedEnvironments.entrySet().removeIf(entry->!entry.getValue().equals(created.get(entry.getKey())));
    String previousMaintenance=maintenanceSignature;renderMaintenance(rows);
    boolean structure=!previousMaintenance.equals(maintenanceSignature);
    visibleIds.clear();Set<String> retained=new HashSet<>();int index=0;
    for(JSONObject row:ordered){
      String key=EnvironmentPresentation.key(row);retained.add(key);EnvironmentRow holder=rowViews.get(key);
      if(holder==null){holder=new EnvironmentRow();rowViews.put(key,holder);structure=true;}
      holder.value=row;visibleIds.add(row.optInt("slot"));holder.bind(row,running,now,value.defaultSlot);
      holder.separator.setVisibility(index==0?View.GONE:View.VISIBLE);
      if(index>=environmentList.getChildCount()||environmentList.getChildAt(index)!=holder.root){
        if(holder.root.getParent()==environmentList)environmentList.removeView(holder.root);
        environmentList.addView(holder.root,index,new LinearLayout.LayoutParams(-1,-2));structure=true;
      }
      index++;
    }
    for(Iterator<Map.Entry<String,EnvironmentRow>> it=rowViews.entrySet().iterator();it.hasNext();){
      Map.Entry<String,EnvironmentRow> entry=it.next();if(!retained.contains(entry.getKey())){
        environmentList.removeView(entry.getValue().root);it.remove();structure=true;
      }
    }
    environmentList.setVisibility(visibleIds.isEmpty()?View.GONE:View.VISIBLE);
    int maintenance=0;for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);if(row.optBoolean("resetting")||row.optBoolean("deleting"))maintenance++;}
    setText(count,ordered.isEmpty()&&maintenance>0?maintenance+" 个环境待完成维护":ordered.size()+" 个环境");
    String empty=ordered.isEmpty()?(maintenance>0?"maintenance":"empty"):"";
    if(!empty.equals(emptySignature)){
      emptySignature=empty;emptyRows.removeAllViews();
      if("maintenance".equals(empty))DesignUi.note(emptyRows,"有环境等待完成维护，请点击上方继续重置或清理。");
      else if("empty".equals(empty))DesignUi.empty(emptyRows,"还没有环境","创建一个环境，打开独立的浏览器。","新建环境",this::createWindow);
    }
    updateSelectionBar(rows);
    // Only compensate actual content-layout changes; preserve the user's drag.
    if(anchor!=null&&(structure||environmentList.isLayoutRequested()||maintenanceRows.isLayoutRequested()
        ||selectionBar.getVisibility()==View.VISIBLE&&selectionBar.isLayoutRequested()))
      restoreEnvironmentPosition(workspaceScroll,anchor,anchorTop,positionToken);
  }
  static void setText(TextView view,String text){if(!android.text.TextUtils.equals(view.getText(),text))view.setText(text);}
  void renderMaintenance(JSONArray rows){
    JSONArray signature=new JSONArray();for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);if(row.optBoolean("deleting")||row.optBoolean("resetting"))signature.put(new JSONArray().put(EnvironmentPresentation.key(row)).put(row.optString("name")).put(row.optBoolean("deleting")).put(row.optBoolean("resetting")));}
    if(signature.toString().equals(maintenanceSignature))return;maintenanceSignature=signature.toString();maintenanceRows.removeAllViews();
    for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);int id=row.optInt("slot");if(row.optBoolean("deleting"))DesignUi.action(maintenanceRows,"继续清理 · "+row.optString("name"),false,()->{try{startDelete(new EnvironmentSpec.Identity(id,row.optInt("generation"),row.getString("environmentId")));}catch(Exception invalid){showProblem("删除环境已变化，请刷新列表");}});else if(row.optBoolean("resetting"))DesignUi.action(maintenanceRows,"继续重置登录 · "+row.optString("name"),false,()->startReset(id,row.optInt("generation")-1,row.optString("environmentId")));}
  }
  final class EnvironmentRow {
    final LinearLayout root=DesignUi.column(WindowHomeActivity.this),card=DesignUi.card(WindowHomeActivity.this),head=DesignUi.row(WindowHomeActivity.this),details=DesignUi.row(WindowHomeActivity.this);
    final View separator=new View(WindowHomeActivity.this);final CheckBox check=new CheckBox(WindowHomeActivity.this);
    final EnvironmentWorkspaceStyle.Emblem emblem=new EnvironmentWorkspaceStyle.Emblem(WindowHomeActivity.this,false);
    final TextView name=workspaceText("",ReferenceUi.CARD_TITLE_SIZE,DesignUi.TEXT,true),sub=workspaceText("",ReferenceUi.SECONDARY_SIZE,DesignUi.MUTED,false),badge=workspaceText("",ReferenceUi.STATUS_SIZE,DesignUi.MUTED,false),network=workspaceText("",ReferenceUi.SECONDARY_SIZE,DesignUi.MUTED,false);
    JSONObject value;boolean syncing;
    final Button more=ReferenceUi.more(WindowHomeActivity.this,()->{if(value!=null)menu(value.optInt("slot"));});
    final EnvironmentPresentation.Binding binding=new EnvironmentPresentation.Binding();
    EnvironmentRow(){
      root.addView(separator,new LinearLayout.LayoutParams(-1,dp(10)));root.addView(card);card.setPadding(dp(16),dp(13),dp(12),dp(13));
      card.setClickable(true);card.setFocusable(true);card.setOnClickListener(v->{if(value!=null){if(selecting)toggleSelection(value);else openExpected(value,"chat",true);}});card.setOnLongClickListener(v->{if(value!=null)toggleSelection(value);return true;});
      check.setOnCheckedChangeListener((button,selected)->{if(!syncing&&value!=null)toggleSelection(value);});head.addView(check,new LinearLayout.LayoutParams(dp(48),dp(48)));head.addView(emblem,new LinearLayout.LayoutParams(dp(40),dp(40)));
      LinearLayout titles=DesignUi.column(WindowHomeActivity.this);titles.setPadding(dp(12),0,dp(4),0);name.setMaxLines(2);name.setEllipsize(TextUtils.TruncateAt.END);sub.setMaxLines(1);sub.setEllipsize(TextUtils.TruncateAt.END);sub.setPadding(0,dp(4),0,0);sub.setCompoundDrawablePadding(dp(4));titles.addView(name);titles.addView(sub);head.addView(titles,new LinearLayout.LayoutParams(0,-2,1));head.addView(more,new LinearLayout.LayoutParams(dp(48),dp(48)));card.addView(head);
      details.setPadding(0,dp(8),0,0);
      network.setMaxLines(1);network.setEllipsize(TextUtils.TruncateAt.END);network.setPadding(0,0,dp(8),0);Ui.Icon globe=new Ui.Icon("globe",DesignUi.MUTED);globe.setBounds(0,0,dp(12),dp(12));network.setCompoundDrawables(globe,null,null,null);network.setCompoundDrawablePadding(dp(5));details.addView(network,new LinearLayout.LayoutParams(0,-2,1));
      badge.setPadding(dp(7),dp(3),dp(7),dp(3));badge.setCompoundDrawablePadding(dp(5));badge.setGravity(Gravity.CENTER);details.addView(badge);card.addView(details);
    }
    void bind(JSONObject row,Set<Integer> running,long now,int defaultSlot){
      if(!binding.changed(EnvironmentPresentation.stamp(row,running,now,defaultSlot,selecting,selectedIds.contains(row.optInt("slot")))))return;
      int id=row.optInt("slot");boolean active=EnvironmentPresentation.active(row,running),fresh=EnvironmentPresentation.fresh(row,now),problem=!row.optString("problem").isEmpty();
      card.setBackground(EnvironmentWorkspaceStyle.card(WindowHomeActivity.this,id==defaultSlot,selecting&&selectedIds.contains(id)));
      syncing=true;check.setChecked(selectedIds.contains(id));syncing=false;check.setVisibility(selecting?View.VISIBLE:View.GONE);emblem.setVisibility(selecting?View.GONE:View.VISIBLE);emblem.bind(id);
      check.setContentDescription("选择环境 "+String.format(Locale.ROOT,"%02d",id+1)+" "+row.optString("name"));
      setText(name,row.optString("name"));String group=row.optString("group");
      Ui.Icon favorite=row.optBoolean("favorite")?new Ui.Icon("star",ReferenceUi.ORANGE):null;
      if(favorite!=null)favorite.setBounds(0,0,dp(11),dp(11));
      sub.setCompoundDrawables(favorite,null,null,null);
      setText(sub,String.format(Locale.ROOT,"%02d",id+1)+(group.isEmpty()?"":" · "+group)+(id==defaultSlot?" · 默认":"")+(row.optBoolean("desktopSite")?" · 电脑版":"")+(!row.optString("draft").isEmpty()?" · 草稿":""));
      int color=problem?DesignUi.RED:active?DesignUi.GREEN:DesignUi.MUTED;
      setText(badge,EnvironmentPresentation.status(row,active,fresh));badge.setTextColor(color);
      badge.setCompoundDrawables(EnvironmentWorkspaceStyle.statusDot(WindowHomeActivity.this,color),null,null,null);
      badge.setBackground(DesignUi.surface(WindowHomeActivity.this,active||problem?(color&0x00ffffff)|0x11000000:android.graphics.Color.TRANSPARENT,12,android.graphics.Color.TRANSPARENT));
      setText(network,networkStatus(row,active,fresh));network.setTextColor(DesignUi.MUTED);
      more.setVisibility(selecting?View.GONE:View.VISIBLE);more.setContentDescription("更多操作 "+row.optString("name"));
      card.setContentDescription((selecting?"选择环境：":"打开环境：")+row.optString("name")+(row.optBoolean("favorite")?"，已收藏":"")+"，"+sub.getText()+"，"+network.getText()+"，"+badge.getText());
    }
  }
  void openExpected(JSONObject expected,String action,boolean overview){
    if(!EnvironmentSwitcherUi.open(this,expected,action,overview))showProblem("环境已变化，请刷新后重新选择");
  }
  void setSelecting(boolean value){
    selecting=value;if(!value)selectedEnvironments.clear();renderCached();
  }
  static EnvironmentSpec.Identity selectionIdentity(JSONObject row){
    if(!EnvironmentWorkspacePolicy.eligible(row))return null;
    try{return new EnvironmentSpec.Identity(row.optInt("slot",-1),row.optInt("generation",-1),row.optString("environmentId"));}
    catch(IllegalArgumentException invalidIdentity){return null;}
  }
  void toggleSelection(JSONObject row){
    EnvironmentSpec.Identity identity=selectionIdentity(row);
    if(identity==null)return;
    selecting=true;
    if(identity.equals(selectedEnvironments.get(identity.slot)))selectedEnvironments.remove(identity.slot);
    else selectedEnvironments.put(identity.slot,identity);
    renderCached();
  }
  void selectVisible(){
    if(visibleIds.isEmpty()||snapshot==null)return;
    selecting=true;
    if(selectedIds.containsAll(visibleIds))selectedEnvironments.keySet().removeAll(visibleIds);
    else for(int i=0;i<snapshot.rows.length();i++){
      EnvironmentSpec.Identity identity=selectionIdentity(snapshot.rows.optJSONObject(i));
      if(identity!=null&&visibleIds.contains(identity.slot))selectedEnvironments.put(identity.slot,identity);
    }
    renderCached();
  }
  void updateSelectionBar(JSONArray rows){
    setText(selectionButton,selecting?"完成":"多选");selectionButton.setSelected(selecting);
    selectionBar.setVisibility(selecting?View.VISIBLE:View.GONE);
    boolean hasFavorite=false,hasUnfavorite=false;
    for(int i=0;i<rows.length();i++){
      JSONObject row=rows.optJSONObject(i);
      if(selectedIds.contains(row.optInt("slot"))){if(row.optBoolean("favorite"))hasFavorite=true;else hasUnfavorite=true;}
    }
    setText(selectionCount,"已选 "+selectedIds.size()+" 个");
    setText(visibleSelectionButton,!visibleIds.isEmpty()&&selectedIds.containsAll(visibleIds)?"取消全选":"全选");
    visibleSelectionButton.setEnabled(!visibleIds.isEmpty());
    batchGroupButton.setEnabled(!selectedIds.isEmpty());
    favoriteSelectedButton.setEnabled(hasUnfavorite);unfavoriteSelectedButton.setEnabled(hasFavorite);
    for(Button button:new Button[]{visibleSelectionButton,batchGroupButton,favoriteSelectedButton,unfavoriteSelectedButton})button.setAlpha(button.isEnabled()?1f:.45f);
  }
  void batchFavorite(boolean favorite){
    if(selectedIds.isEmpty())return;
    List<EnvironmentSpec.Identity> selection=new ArrayList<>(selectedEnvironments.values());
    int changed=ProfileCatalog.get(this).favorites(selection,favorite);
    finishSelectionUpdate(changed,selection.size());
  }
  void finishSelectionUpdate(int changed,int expected){
    refresh();
    if(changed<expected)showProblem(changed==0?"所选环境已变化，请刷新后重新选择":"部分环境已变化，已更新仍匹配的环境");
  }
  AlertDialog batchGroup(){
    if(selectedIds.isEmpty())return null;
    // Capture the selection when opening the form; later refreshes cannot widen its scope.
    List<EnvironmentSpec.Identity> selection=new ArrayList<>(selectedEnvironments.values());ProfileCatalog catalog=ProfileCatalog.get(this);
    String common=catalog.item(selection.get(0).slot).optString("group");boolean mixed=false;
    for(EnvironmentSpec.Identity identity:selection)if(!common.equals(catalog.item(identity.slot).optString("group")))mixed=true;
    LinearLayout box=DesignUi.column(this);box.setPadding(dp(20),dp(8),dp(20),dp(12));
    LinearLayout card=ReferenceUi.modalGroup(this);
    EditText group=ReferenceUi.modalInput(card,"目标分组",mixed?"":common,"最多 12 字，留空为未分组");
    group.setFilters(new InputFilter[]{new InputFilter.LengthFilter(12)});
    group.setImeOptions(android.view.inputmethod.EditorInfo.IME_ACTION_DONE);
    box.addView(card,new LinearLayout.LayoutParams(-1,-2));
    int hidden=0;for(EnvironmentSpec.Identity identity:selection)if(!visibleIds.contains(identity.slot))hidden++;
    ReferenceUi.modalFooterNote(box,"修改已选 "+selection.size()+" 个环境"+(hidden>0?"（含筛选外 "+hidden+" 个）":"")+"。备注和配置草稿保留。");
    List<String> groups=new ArrayList<>();JSONArray rows=catalog.list();
    for(int i=0;i<rows.length();i++){
      JSONObject row=rows.optJSONObject(i);String value=row.optString("group");
      if(row.optBoolean("created")&&!value.isEmpty()&&!groups.contains(value))groups.add(value);
    }
    if(!groups.isEmpty()){
      HorizontalScrollView chipScroll=new HorizontalScrollView(this);chipScroll.setHorizontalScrollBarEnabled(false);
      LinearLayout chips=DesignUi.row(this);chips.setPadding(dp(16),0,dp(16),dp(8));
      int limit=Math.min(groups.size(),5);
      List<Button> chipButtons=new ArrayList<>();
      List<String> chipValues=new ArrayList<>();
      int vInset=dp(6);
      Runnable syncChips=()->{
        String active=group.getText().toString().trim();
        for(int j=0;j<chipButtons.size();j++){
          Button b=chipButtons.get(j);String val=chipValues.get(j);
          boolean on=!val.isEmpty()&&val.equals(active);
          b.setSelected(on);
          b.setTextColor(on?ReferenceUi.brandBlue():ReferenceUi.inkPrimary());
          b.setTypeface(on?ReferenceUi.TYPE_SEMIBOLD:ReferenceUi.TYPE_MEDIUM);
          ReferenceUi.crisp(b);
          ReferenceUi.AdaptiveSurface pill=on
              ?new ReferenceUi.AdaptiveSurface(this,7,0xffeef4ff,0xff1b2638,0x280067d8,0x3d6da4ff)
              :new ReferenceUi.AdaptiveSurface(this,7,0xfff6f7f9,0xff232732,0x12111827,0x18ffffff);
          b.setBackground(new android.graphics.drawable.RippleDrawable(
              android.content.res.ColorStateList.valueOf(ReferenceUi.tone(0x140067d8,0x246da4ff)),
              new android.graphics.drawable.InsetDrawable(pill,0,vInset,0,vInset),
              new android.graphics.drawable.InsetDrawable(new ReferenceUi.AdaptiveSurface(this,7,android.graphics.Color.WHITE,android.graphics.Color.WHITE),0,vInset,0,vInset)));
        }
      };
      for(int i=0;i<limit;i++){
        final String value=groups.get(i);
        Button chip=ReferenceUi.link(this,value,()->{group.setText(value);group.setSelection(value.length());});
        chip.setTextSize(ReferenceUi.ACTION_SIZE);chip.setMinHeight(dp(44));chip.setMinimumHeight(dp(44));
        chip.setPadding(dp(13),dp(8),dp(13),dp(8));
        LinearLayout.LayoutParams cp=new LinearLayout.LayoutParams(-2,-2);if(i>0)cp.setMarginStart(dp(6));
        chips.addView(chip,cp);chipButtons.add(chip);chipValues.add(value);
      }
      Button clearChip=ReferenceUi.link(this,"清空分组",()->group.setText(""));
      clearChip.setTextSize(ReferenceUi.SECONDARY_SIZE);clearChip.setTextColor(ReferenceUi.secondaryInk());
      clearChip.setMinHeight(dp(44));clearChip.setMinimumHeight(dp(44));
      clearChip.setPadding(dp(10),dp(8),dp(10),dp(8));
      LinearLayout.LayoutParams clearP=new LinearLayout.LayoutParams(-2,-2);clearP.setMarginStart(dp(6));
      chips.addView(clearChip,clearP);
      Runnable syncAll=()->{syncChips.run();clearChip.setVisibility(group.getText().toString().trim().isEmpty()?View.GONE:View.VISIBLE);};
      group.addTextChangedListener(new TextWatcher(){
        public void beforeTextChanged(CharSequence s,int a,int c,int f){}
        public void onTextChanged(CharSequence s,int a,int b,int c){syncAll.run();}
        public void afterTextChanged(Editable e){}
      });
      syncAll.run();
      chipScroll.addView(chips);card.addView(chipScroll,new LinearLayout.LayoutParams(-1,-2));
      if(groups.size()>5){
        LinearLayout pickCard=ReferenceUi.modalGroup(this);
        ReferenceUi.modalRowAction(pickCard,"window","查看全部已有分组（"+groups.size()+"）",false,()->{
          ReferenceUi.Modal picker=new ReferenceUi.Modal(this,"已有分组").asSheet();
          LinearLayout list=ReferenceUi.modalGroup(this);
          String active=group.getText().toString().trim();
          for(String value:groups)ReferenceUi.modalChoice(list,value,"",value.equals(active),()->{group.setText(value);picker.dismiss();});
          picker.body.addView(list,new LinearLayout.LayoutParams(-1,-2));
          picker.buttons("取消",picker::dismiss,"",()->{});picker.show();
        });
        LinearLayout.LayoutParams pp=new LinearLayout.LayoutParams(-1,-2);pp.topMargin=dp(10);
        box.addView(pickCard,pp);
      }
    }
    AlertDialog dialog=AppAppearance.dialog(this).setTitle("批量分组").setView(box)
      .setPositiveButton("保存分组",null).setNegativeButton("取消",null).create();
    dialog.show();
    dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{
      int changed=catalog.group(selection,group.getText().toString());
      dialog.dismiss();finishSelectionUpdate(changed,selection.size());
    });
    return dialog;
  }
  void menu(int id){
    ProfileCatalog catalog=ProfileCatalog.get(this);
    JSONObject row=catalog.item(id);
    EnvironmentSpec.Identity shown=selectionIdentity(row);
    if(shown==null)return;
    String[] labels={"编辑环境","分组与备注",row.optBoolean("favorite")?"取消收藏":"收藏环境",id==AppSettings.defaultSlot(this)?"当前默认环境":"设为默认启动环境","网络配置","选择此环境","复制环境配置","环境详情","重置登录数据","删除环境"};
    ReferenceUi.Modal panel=new ReferenceUi.Modal(this,row.optString("name")).asSheet();
    for(int i=0;i<labels.length;i++){final int n=i;ReferenceUi.menuAction(panel,labels[i],()->{panel.dismiss();
      if(n==0)openWindow(id,"edit");if(n==1)metadata(row);
      if(n==2)saveMenuChoice(catalog,shown,()->catalog.favorite(shown.slot,!row.optBoolean("favorite")));
      if(n==3)saveMenuChoice(catalog,shown,()->AppSettings.defaultSlot(this,shown.slot));
      if(n==4)openWindow(id,"network");if(n==5)toggleSelection(row);if(n==6)copyEnvironment(row);if(n==7)openExpected(row,"overview",true);if(n==8)resetEnvironment(row);if(n==9)deleteEnvironment(row);
    });}
    panel.buttons("取消",panel::dismiss,"",()->{});panel.show();
  }
  void saveMenuChoice(ProfileCatalog catalog,EnvironmentSpec.Identity shown,ProfileCatalog.IdentityAction<Boolean> change){
    try{
      if(catalog.withIdentity(shown,change)){refresh();return;}
    }catch(Exception unavailable){}
    showProblem("环境已变化或暂时无法保存，请重新选择");
  }
  void startReset(int id,int generation,String environmentId){startActivity(new Intent(this,EnvironmentResetActivity.class).putExtra("slot",id).putExtra("confirmedGeneration",generation).putExtra("confirmedEnvironmentId",environmentId).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));}
  private View maintenanceImpactView(String dangerTitle,String dangerDetail,String keepTitle,String keepDetail){
    LinearLayout box=DesignUi.column(this);box.setPadding(dp(20),dp(8),dp(20),dp(8));
    box.addView(ReferenceUi.modalImpactPair(this,dangerTitle,dangerDetail,keepTitle,keepDetail),new LinearLayout.LayoutParams(-1,-2));
    ScrollView scroll=new ScrollView(this);NativeControls.prepare(scroll);scroll.addView(box);return scroll;
  }
  void resetEnvironment(JSONObject row){
    EnvironmentSpec.Identity shown=selectionIdentity(row);
    if(shown==null){showProblem("环境已变化，请刷新列表");return;}
    AlertDialog dialog=AppAppearance.dialog(this).setTitle("重置 "+row.optString("name")+" 的登录？")
      .setView(maintenanceImpactView("将关闭此环境并清理以下数据","登录、Cookie、网页存储和本地草稿、聊天缓存。正在进行的回复、上传和下载任务会中断。","以下内容会安全保留","环境名称、模板、网络与使用偏好，以及已保存的下载文件；其他环境不受影响。完成后需重新登录 ChatGPT。"))
      .setNegativeButton("取消",null).setPositiveButton("重置登录数据",null).show();
    confirmMaintenance(dialog,shown,false);
  }

  void confirmMaintenance(AlertDialog dialog,EnvironmentSpec.Identity shown,boolean deleting){
    Button confirm=dialog.getButton(AlertDialog.BUTTON_POSITIVE);
    confirm.setTextColor(ReferenceUi.redInk());
    confirm.setOnClickListener(view->{
      confirm.setEnabled(false);
      CharSequence title=confirm.getText();
      confirm.setText("正在检查…");
      new Thread(()->{
        String failure="";
        try{
          ProfileCatalog.get(this).withIdentity(shown,()->{
            DownloadLibrary.get(this).preflightRemoval(shown.slot);
            return null;
          });
        }catch(DownloadLibrary.LegacyHistoryUnreadable unreadable){
          failure="旧下载记录无法读取。此环境尚未进入维护，已保存的文件保留在原位置。";
        }catch(Exception unavailable){
          failure="环境已变化或暂时无法检查。此操作尚未开始，请刷新后重试。";
        }
        String issue=failure;
        handler.post(()->{
          if(!dialog.isShowing()||isFinishing()||isDestroyed())return;
          confirm.setText(title);
          confirm.setEnabled(true);
          if(!workspaceVisible)return;
          dialog.dismiss();
          if(!issue.isEmpty()){showProblem(issue);return;}
          try{
            if(deleting)startDelete(ProfileCatalog.get(this).beginDelete(shown));
            else startReset(shown.slot,shown.generation,shown.environmentId);
          }catch(Exception unavailable){
            String detail=unavailable.getMessage();
            showProblem(detail==null?"暂时无法进入维护，请刷新后重试。":detail);
          }
        });
      },"environment-maintenance-preflight").start();
    });
  }
  void copyEnvironment(JSONObject source){
    if(preparing)return;
    ProfileCatalog catalog=ProfileCatalog.get(this);
    EnvironmentSpec.Identity expected=selectionIdentity(source);
    if(expected==null||!expected.equals(selectionIdentity(catalog.item(expected.slot)))){
      showProblem("源环境已变化，请重试");return;
    }
    JSONObject target=firstEmptySlot(catalog.list());
    if(target==null){showProblem("环境已满，请先删除不再使用的环境");return;}
    int destination=target.optInt("slot",-1),generation=target.optInt("generation",-1);

    ReferenceUi.Modal dialog=new ReferenceUi.Modal(this,"复制环境配置");
    LinearLayout card=ReferenceUi.modalGroup(this);
    String label=source.optString("name");
    if(label.length()>20)label=label.substring(0,20);
    EditText name=ReferenceUi.modalInput(card,"新环境名称",label+" 副本","请输入 1–24 字名称",true);
    name.setFilters(new InputFilter[]{new InputFilter.LengthFilter(24)});
    name.setImeOptions(android.view.inputmethod.EditorInfo.IME_ACTION_DONE);
    dialog.body.addView(card,new LinearLayout.LayoutParams(-1,-2));
    Spinner enginePicker=BrowserSettingsUi.creationPicker(this,card,EnvironmentEngine.GECKO);
    ReferenceUi.modalFooterNote(dialog.body,"复制已保存的浏览器模板、网络和使用偏好。账号、聊天和草稿在新环境独立，不会复制。");
    dialog.buttons("取消",dialog::dismiss,"创建副本",()->{
      String title=name.getText().toString().trim();
      if(title.isEmpty()){name.setError("请输入环境名称");ReferenceUi.hapticReject(name);name.requestFocus();return;}
      if(preparing)return;
      EnvironmentEngine chosen=BrowserSettingsUi.creationSelection(enginePicker);
      preparing=true;
      dialog.dismiss();
      createButton.setEnabled(false);
      preparation.setVisibility(View.VISIBLE);
      new Thread(()->{
        String error="";
        try{
          Profiles.copyConfigurationWithEngine(Profiles.context(this,expected.slot),destination,generation,expected,title,chosen);
        }catch(Exception failure){
          error=failure.getMessage()==null?"复制未完成，请重试":failure.getMessage();
        }
        String issue=error;
        handler.post(()->{
          preparing=false;
          if(isFinishing()||isDestroyed())return;
          createButton.setEnabled(true);
          preparation.setVisibility(View.GONE);
          refresh();
          if(!issue.isEmpty())showProblem(issue);
        });
      },"environment-copy").start();
    });
    dialog.show();
  }
  void startDelete(EnvironmentSpec.Identity expected){startActivity(new Intent(this,EnvironmentDeleteActivity.class).putExtra("slot",expected.slot).putExtra("confirmedGeneration",expected.generation).putExtra("confirmedEnvironmentId",expected.environmentId).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));}
  void deleteEnvironment(JSONObject row){
    EnvironmentSpec.Identity shown=selectionIdentity(row);
    if(shown==null){showProblem("环境已变化，请刷新列表");return;}
    AlertDialog dialog=AppAppearance.dialog(this).setTitle("删除 "+row.optString("name")+"？")
      .setView(maintenanceImpactView("将关闭并永久清理此环境","此环境的登录、草稿、聊天缓存和网络配置会被删除；正在进行的回复和文件操作会中断。","以下内容会安全保留","其他环境、订阅与固定出口，以及已保存到下载目录的文件不受影响。"))
      .setNegativeButton("取消",null).setPositiveButton("删除环境",null).show();
    confirmMaintenance(dialog,shown,true);
  }
  void metadata(JSONObject row){
    EnvironmentSpec.Identity expected=selectionIdentity(row);
    if(expected==null){showProblem("环境已变化，请刷新后重新选择");return;}
    ReferenceUi.Modal dialog=new ReferenceUi.Modal(this,"分组与备注 · "+row.optString("name"));
    LinearLayout card=ReferenceUi.modalGroup(this);
    EditText group=ReferenceUi.modalInput(card,"分组",row.optString("group"),"留空为未分组");
    EditText notes=ReferenceUi.modalInput(card,"备注",row.optString("notes"),"环境用途说明");
    group.setFilters(new InputFilter[]{new InputFilter.LengthFilter(12)});
    notes.setFilters(new InputFilter[]{new InputFilter.LengthFilter(120)});
    notes.setSingleLine(false);notes.setMinLines(2);notes.setMaxLines(4);notes.setGravity(Gravity.TOP|Gravity.START);
    dialog.body.addView(card,new LinearLayout.LayoutParams(-1,-2));
    Runnable close=()->{
      boolean dirty=!group.getText().toString().equals(row.optString("group"))||!notes.getText().toString().equals(row.optString("notes"));
      if(!dirty){dialog.dismiss();return;}
      ReferenceUi.Modal confirm=new ReferenceUi.Modal(this,"保留正在填写的内容？").hideClose();
      LinearLayout descCard=ReferenceUi.modalGroup(this);descCard.setPadding(dp(16),dp(14),dp(16),dp(14));
      descCard.addView(ReferenceUi.workspaceText(this,"继续编辑可保留本次填写；放弃修改后会退出此表单。",ReferenceUi.BODY_SIZE,DesignUi.TEXT,false));
      confirm.body.addView(descCard,new LinearLayout.LayoutParams(-1,-2));
      confirm.buttons("放弃修改",()->{confirm.dismiss();dialog.dismiss();},"继续编辑",confirm::dismiss);
      confirm.show();
    };
    dialog.cancel=close;
    dialog.buttons("取消",close,"保存",()->{
      ProfileCatalog catalog=ProfileCatalog.get(this);
      try{
        boolean saved=catalog.withIdentity(expected,()->catalog.details(expected.slot,group.getText().toString(),notes.getText().toString()));
        if(saved){dialog.dismiss();refresh();return;}
      }catch(Exception unavailable){}
      notes.setError("环境已变化或暂时无法保存，请重新选择");
    });
    dialog.show();
  }
  void openWindow(int id,String action){
    if(id<0||id>=Profiles.MAX)return;
    if(!ProfileCatalog.get(this).available(id))return;
    if(id>0&&Build.VERSION.SDK_INT<28){showProblem("独立环境需要 Android 9 或更新版本");return;}
    ProfileCatalog.get(this).opened(id);
    Intent opening="chat".equals(action)?EnvironmentOverviewUi.browserOpening(this,id):new Intent(this,Profiles.activity(id)).putExtra("openWindowAction",action).putExtra("returnToEnvironmentList","edit".equals(action))
      .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_REORDER_TO_FRONT);
    startActivity(opening);
  }
  void createWindow(){
    if(preparing)return;
    if(Build.VERSION.SDK_INT<28){showProblem("独立环境需要 Android 9 或更新版本");return;}
    JSONArray rows=ProfileCatalog.get(this).list();
    JSONObject next=firstEmptySlot(rows);
    if(next==null){showProblem("已达到 8 个环境");return;}
    new Wizard(next.optInt("slot"),next.optInt("generation",-1)).show();
  }
  static JSONObject firstEmptySlot(JSONArray rows){
    for(int i=0;i<rows.length();i++){
      JSONObject row=rows.optJSONObject(i);
      if(row!=null&&!row.optBoolean("created")&&!row.optBoolean("deleting")&&!row.optBoolean("resetting"))return row;
    }
    return null;
  }
  final class Wizard {
    final int id,generation;final Dialog dialog;
    LinearLayout body,actions;TextView stepCaption;EditText name;ReferenceUi.Modal exitPrompt;
    int step,sourceType,sourceSlot;String title,group="";boolean makeDefault,desktop;
    Spinner enginePicker;EnvironmentEngine engine=EnvironmentEngine.GECKO;
    JSONObject selectedNetworkRow;
    EnvironmentSpec.Identity shownNetworkSource;
    Wizard(int id,int generation){
      this.id=id;this.generation=generation;title="环境 "+(id+1);sourceSlot=AppSettings.defaultSlot(WindowHomeActivity.this);
      dialog=new ThemedDialog(WindowHomeActivity.this){@Override public void onBackPressed(){Wizard.this.back();}};
      dialog.setCanceledOnTouchOutside(false);
    }
    void show(){
      LinearLayout screen=DesignUi.screen(WindowHomeActivity.this);
      screen.setClipChildren(false);screen.setClipToPadding(false);
      screen.setBackgroundColor(ReferenceUi.canvasBg());
      FrameLayout viewport=new FrameLayout(WindowHomeActivity.this);viewport.setClipChildren(true);viewport.setClipToPadding(true);
      ScrollView scroll=new ScrollView(WindowHomeActivity.this);scroll.setFillViewport(true);scroll.setClipToPadding(false);NativeControls.prepare(scroll);
      body=DesignUi.column(WindowHomeActivity.this);body.setPadding(dp(16),dp(8),dp(16),dp(24));
      scroll.addView(body,new ScrollView.LayoutParams(-1,-2));
      viewport.addView(scroll,new FrameLayout.LayoutParams(-1,-1));

      FrameLayout head=ReferenceUi.horologyHeader(WindowHomeActivity.this,"创建环境","步骤 1 / 3 · 基本信息",this::back,scroll);
      // Locate the subtitle TextView inside horologyHeader so step caption updates dynamically.
      View rowChild=head.getChildCount()>2?head.getChildAt(2):null;
      if(rowChild instanceof ViewGroup){
        View titlesChild=((ViewGroup)rowChild).getChildAt(((ViewGroup)rowChild).getChildCount()-1);
        if(titlesChild instanceof ViewGroup&&((ViewGroup)titlesChild).getChildCount()>1){
          View subView=((ViewGroup)titlesChild).getChildAt(1);
          if(subView instanceof TextView){stepCaption=(TextView)subView;ReferenceUi.tabular(stepCaption);}
        }
      }
      screen.addView(head,new LinearLayout.LayoutParams(-1,-2));
      screen.addView(viewport,new LinearLayout.LayoutParams(-1,0,1));

      LinearLayout dockHost=DesignUi.column(WindowHomeActivity.this);
      dockHost.setClipChildren(false);dockHost.setClipToPadding(false);
      dockHost.setBackground(EnvironmentWorkspaceStyle.scrollEdge(WindowHomeActivity.this));
      dockHost.setPadding(dp(14),dp(14),dp(14),dp(14));
      actions=DesignUi.row(WindowHomeActivity.this);actions.setClipChildren(false);actions.setClipToPadding(false);
      actions.setPadding(dp(8),dp(8),dp(8),dp(8));
      actions.setBackground(DesignUi.glass(WindowHomeActivity.this,30));
      dockHost.addView(actions,new LinearLayout.LayoutParams(-1,-2));
      screen.addView(dockHost,new LinearLayout.LayoutParams(-1,-2));

      dialog.setContentView(screen);dialog.show();
      dialog.getWindow().setBackgroundDrawableResource(android.R.color.transparent);dialog.getWindow().setLayout(-1,-1);dialog.getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);render();
    }
    void back(){if(step>0){step--;render();}else close();}
    void close(){
      if(step==0&&enginePicker!=null)engine=BrowserSettingsUi.creationSelection(enginePicker);
      boolean dirty=!title.equals("环境 "+(id+1))||!group.isEmpty()||sourceType!=0||makeDefault||desktop||engine!=EnvironmentEngine.GECKO;
      if(!dirty){dialog.dismiss();return;}
      if(exitPrompt!=null&&exitPrompt.isShowing())return;
      exitPrompt=new ReferenceUi.Modal(WindowHomeActivity.this,"放弃创建环境？").hideClose();
      exitPrompt.body.addView(ReferenceUi.modalWarning(WindowHomeActivity.this,"info","未保存的环境配置将被放弃","退出后，本次填写的环境名称、分组与网络来源选择不会保存。"),new LinearLayout.LayoutParams(-1,-2));
      exitPrompt.buttons("继续填写",exitPrompt::dismiss,"放弃创建",()->{exitPrompt.dismiss();dialog.dismiss();});
      exitPrompt.show();
    }
    void render(){
      String[] stepNames={"基本信息","网络来源","确认创建"};
      if(stepCaption!=null)stepCaption.setText(getString(R.string.environment_wizard_step,step+1,stepNames.length,stepNames[step]));
      DesignUi.rebuild(body,false,()->{
        LinearLayout tabs=DesignUi.tabs(WindowHomeActivity.this,stepNames,step,n->{if(n<step){step=n;render();}});
        LinearLayout.LayoutParams tp=new LinearLayout.LayoutParams(-1,-2);tp.bottomMargin=dp(12);
        body.addView(tabs,tp);
        if(step==0)basic();else if(step==1)network();else summary();
      });
      actions.removeAllViews();
      Button back=ReferenceUi.link(WindowHomeActivity.this,step==0?"取消创建":"上一步",this::back);
      back.setTextSize(15);back.setTextColor(DesignUi.MUTED);back.setMinHeight(dp(48));back.setMinimumHeight(dp(48));
      back.setGravity(Gravity.CENTER);back.setBackground(Ui.ripple(WindowHomeActivity.this,android.graphics.Color.TRANSPARENT,999));
      Button next=DesignUi.button(WindowHomeActivity.this,step==2?"创建并打开":"下一步",true,this::next);
      ReferenceUi.stylePill(next,true,false);
      actions.addView(back,new LinearLayout.LayoutParams(0,dp(48),1));
      LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(0,dp(48),1.35f);p.setMarginStart(dp(6));actions.addView(next,p);
    }
    void basic(){
      ReferenceUi.modalSection(body,"环境标识");
      LinearLayout form=ReferenceUi.modalGroup(WindowHomeActivity.this);
      name=ReferenceUi.modalInput(form,"环境名称",title,"例如：工作号、研究专用",true);
      name.setFilters(new InputFilter[]{new InputFilter.LengthFilter(24)});
      watch(name,()->title=name.getText().toString());
      EditText input=ReferenceUi.modalInput(form,"分组",group,"最多 12 字，留空为未分组");
      input.setFilters(new InputFilter[]{new InputFilter.LengthFilter(12)});
      input.setImeOptions(android.view.inputmethod.EditorInfo.IME_ACTION_DONE);
      watch(input,()->group=input.getText().toString().trim());
      body.addView(form,new LinearLayout.LayoutParams(-1,-2));
      enginePicker=BrowserSettingsUi.creationPicker(WindowHomeActivity.this,body,engine);
      ReferenceUi.modalSection(body,"网页显示方式");
      LinearLayout modeCard=ReferenceUi.modalGroup(WindowHomeActivity.this);
      ReferenceUi.modalChoice(modeCard,"手机版网站","默认排版，适合单手阅读与快速回复",!desktop,()->{engine=BrowserSettingsUi.creationSelection(enginePicker);desktop=false;render();});
      ReferenceUi.modalChoice(modeCard,"电脑版网站","内容更密、展示侧栏与工具，可双指缩放",desktop,()->{engine=BrowserSettingsUi.creationSelection(enginePicker);desktop=true;render();});
      body.addView(modeCard,new LinearLayout.LayoutParams(-1,-2));
    }
    void watch(EditText input,Runnable changed){input.addTextChangedListener(new TextWatcher(){
      public void beforeTextChanged(CharSequence s,int a,int c,int f){}
      public void onTextChanged(CharSequence s,int a,int b,int c){changed.run();}
      public void afterTextChanged(Editable e){}
    });}
    void network(){
      String[] choices={"使用默认环境的网络设置","使用其他环境的网络设置","自己配置网络"};
      String[] hints={"沿用当前默认环境的线路与代理规则","从已有环境复制已保存的网络配置","创建完成后自行选择或配置线路"};
      ReferenceUi.modalSection(body,"网络配置来源");
      LinearLayout choicesBox=ReferenceUi.modalGroup(WindowHomeActivity.this);
      for(int i=0;i<choices.length;i++){
        final int n=i;
        ReferenceUi.modalChoice(choicesBox,choices[i],hints[i],sourceType==i,()->{sourceType=n;render();});
      }
      body.addView(choicesBox,new LinearLayout.LayoutParams(-1,-2));
      if(sourceType==1){
        JSONArray rows=ProfileCatalog.get(WindowHomeActivity.this).list();
        List<JSONObject> sources=new ArrayList<>();
        int selected=0;
        for(int i=0;i<rows.length();i++){
          JSONObject row=rows.optJSONObject(i);
          EnvironmentSpec.Identity identity=selectionIdentity(row);
          if(identity==null)continue;
          if(identity.slot==sourceSlot)selected=sources.size();
          sources.add(row);
        }
        selectNetworkSource(sources,selected);
        if(!sources.isEmpty()){
          ReferenceUi.modalSection(body,"选择来源环境");
          LinearLayout sourceCard=ReferenceUi.modalGroup(WindowHomeActivity.this);
          for(int i=0;i<sources.size();i++){
            final int pos=i;JSONObject row=sources.get(i);String label=row.optString("name");
            ReferenceUi.modalChoice(sourceCard,label,row.optString("group"),label,true,selected==i,()->{selectNetworkSource(sources,pos);render();});
          }
          body.addView(sourceCard,new LinearLayout.LayoutParams(-1,-2));
        }
      }
      ReferenceUi.modalFooterNote(body,"只复制网络设置，账号需要在新环境单独登录。");
    }
    void selectNetworkSource(List<JSONObject> sources,int position){
      selectedNetworkRow=position>=0&&position<sources.size()?sources.get(position):null;
      sourceSlot=selectedNetworkRow==null?-1:selectedNetworkRow.optInt("slot",-1);
    }
    void summary(){
      ReferenceUi.modalSection(body,"配置核对");
      LinearLayout card=ReferenceUi.modalGroup(WindowHomeActivity.this);
      ReferenceUi.modalFieldRow(card,"环境名称",title,false);
      if(!group.isEmpty())ReferenceUi.modalFieldRow(card,"分组",group,false);
      ReferenceUi.modalFieldRow(card,"浏览器内核",engine.label,false);
      ReferenceUi.modalFieldRow(card,"网页显示方式",BrowserDisplay.label(desktop),false);
      JSONObject source=null;
      if(sourceType==0){
        int defaultSlot=AppSettings.defaultSlot(WindowHomeActivity.this);
        if(defaultSlot>=0)source=ProfileCatalog.get(WindowHomeActivity.this).item(defaultSlot);
      }else if(sourceType==1){
        source=selectedNetworkRow;
      }
      shownNetworkSource=selectionIdentity(source);
      ReferenceUi.modalFieldRow(card,"网络来源",sourceType==2?"创建后手动配置":shownNetworkSource==null?"来源环境暂不可用":source.optString("name"),false);
      body.addView(card,new LinearLayout.LayoutParams(-1,-2));
      ReferenceUi.modalSection(body,"启动偏好");
      LinearLayout prefCard=ReferenceUi.modalGroup(WindowHomeActivity.this);
      Switch selected=ReferenceUi.modalSwitchRow(prefCard,"设为默认环境",makeDefault);
      selected.setOnCheckedChangeListener((b,c)->makeDefault=c);
      body.addView(prefCard,new LinearLayout.LayoutParams(-1,-2));
      ReferenceUi.modalFooterNote(body,sourceType==2?"创建后会打开网络配置页。保存网络方式后，再登录 ChatGPT。":"创建后会使用复制的网络配置打开浏览器，请在新环境单独登录 ChatGPT。");
    }
    void next(){
      if(step==0){engine=BrowserSettingsUi.creationSelection(enginePicker);if(title.trim().isEmpty()||title.trim().length()>24){name.setError("名称需要 1–24 字");ReferenceUi.hapticReject(name);name.requestFocus();return;}title=title.trim();}
      if(step<2){step++;render();}else create();
    }
    void create(){
      // The engine is bound before publishing the new environment.
      if(preparing)return;
      boolean clone=sourceType!=2;
      EnvironmentSpec.Identity networkSource=shownNetworkSource;
      if(clone&&(networkSource==null||!networkSource.equals(selectionIdentity(ProfileCatalog.get(WindowHomeActivity.this).item(networkSource.slot))))){
        ReferenceUi.message(WindowHomeActivity.this,"来源环境暂不可用","请重新选择来源环境，或使用自己配置网络。");
        return;
      }
      showProblem("");preparing=true;createButton.setEnabled(false);preparation.setVisibility(View.VISIBLE);
      Context source=clone?Profiles.context(WindowHomeActivity.this,networkSource.slot):Profiles.global(WindowHomeActivity.this);dialog.dismiss();
      final boolean desktopSetting=desktop,setDefault=makeDefault;
      final EnvironmentEngine chosen=engine;
      final String proposedTitle=title,proposedGroup=group;
      new Thread(()->{
        EnvironmentSpec.Identity created=null;
        String error="";
        try{
          created=Profiles.create(source,id,generation,networkSource,proposedTitle,proposedGroup,desktopSetting,setDefault,chosen);
        }catch(Exception failure){
          error=failure.getMessage()==null?"环境准备失败，请重试":failure.getMessage();
        }
        EnvironmentSpec.Identity result=created;
        String issue=error;
        handler.post(()->{
          preparing=false;
          if(isFinishing()||isDestroyed())return;
          createButton.setEnabled(true);
          preparation.setVisibility(View.GONE);
          refresh();
          if(result==null){showProblem(issue);return;}
          JSONObject current=ProfileCatalog.get(WindowHomeActivity.this).item(result.slot);
          if(!result.equals(selectionIdentity(current))){showProblem("环境已变化，请刷新后重新选择");return;}
          openExpected(current,clone?"chat":"network",clone);
        });
      },"window-create").start();
    }
  }
}
