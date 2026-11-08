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
    TextView title=workspaceText("环境",30,DesignUi.TEXT,true);title.setContentDescription("环境管理");
    if(Build.VERSION.SDK_INT>=28)title.setAccessibilityHeading(true);
    headingCopy.addView(title);
    count=workspaceText("",12,DesignUi.MUTED,false);count.setPadding(0,dp(3),dp(6),0);headingCopy.addView(count);
    heading.addView(headingCopy,new LinearLayout.LayoutParams(0,-2,1));
    selectionButton=ReferenceUi.link(this,"多选",()->setSelecting(!selecting));selectionButton.setTextSize(13);selectionButton.setIncludeFontPadding(true);
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
    problem=DesignUi.text(this,"",13,DesignUi.RED);problem.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);problem.setVisibility(View.GONE);box.addView(problem);
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
    selectionCount=DesignUi.text(this,"",13,DesignUi.TEXT);
    selectionCount.setIncludeFontPadding(true);
    selectionTools.addView(selectionCount,new LinearLayout.LayoutParams(0,-2,1));
    visibleSelectionButton=DesignUi.button(this,"全选",false,()->selectVisible());
    visibleSelectionButton.setTextSize(12);visibleSelectionButton.setIncludeFontPadding(true);
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
      actions[i].setTextSize(13);actions[i].setIncludeFontPadding(true);
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
      if(selecting&&ids!=null)for(int id:ids)selectedIds.add(id);
    }
    refresh();
  }
  TextView workspaceText(String value,int size,int color,boolean strong){
    TextView text=ReferenceUi.text(this,value,size,color,strong);text.setIncludeFontPadding(true);
    if(Build.VERSION.SDK_INT>=28)text.setFallbackLineSpacing(true);
    return text;
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
    JSONArray rows=value.rows;Set<Integer> running=value.running,created=new HashSet<>();long now=System.currentTimeMillis();
    List<JSONObject> ordered=new ArrayList<>();
    for(int i=0;i<rows.length();i++){
      JSONObject row=rows.optJSONObject(i);if(!EnvironmentWorkspacePolicy.eligible(row))continue;
      ordered.add(row);created.add(row.optInt("slot"));
    }
    selectedIds.retainAll(created);
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
      else if("empty".equals(empty))DesignUi.empty(emptyRows,"还没有环境","创建一个环境，开始独立的会话。","新建环境",this::createWindow);
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
    final TextView name=workspaceText("",17,DesignUi.TEXT,false),sub=workspaceText("",11,DesignUi.MUTED,false),badge=workspaceText("",11,DesignUi.MUTED,false),network=workspaceText("",11,DesignUi.MUTED,false);
    JSONObject value;boolean syncing;
    final Button more=ReferenceUi.more(WindowHomeActivity.this,()->{if(value!=null)menu(value.optInt("slot"));});
    final EnvironmentPresentation.Binding binding=new EnvironmentPresentation.Binding();
    EnvironmentRow(){
      root.addView(separator,new LinearLayout.LayoutParams(-1,dp(12)));root.addView(card);card.setPadding(dp(16),dp(13),dp(12),dp(13));
      card.setClickable(true);card.setFocusable(true);card.setOnClickListener(v->{if(value!=null){if(selecting)toggleSelection(value.optInt("slot"));else openExpected(value,"chat",true);}});card.setOnLongClickListener(v->{if(value!=null)toggleSelection(value.optInt("slot"));return true;});
      check.setOnCheckedChangeListener((button,selected)->{if(!syncing&&value!=null)toggleSelection(value.optInt("slot"));});head.addView(check,new LinearLayout.LayoutParams(dp(48),dp(48)));head.addView(emblem,new LinearLayout.LayoutParams(dp(40),dp(40)));
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
