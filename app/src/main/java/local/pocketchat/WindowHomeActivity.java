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
public class WindowHomeActivity extends Activity {
  LinearLayout root,cards,filters,selectionBar;
  TextView count,selectionCount;
  EditText search;
  Button groupButton,sortButton,selectionButton,visibleSelectionButton;
  Button batchGroupButton,favoriteSelectedButton,unfavoriteSelectedButton;
  Button createButton,filterOptions;
  LinearLayout preparation;
  int filter,sort;
  String selectedGroup;
  boolean selecting,preparing;
  final Set<Integer> selectedIds=new LinkedHashSet<>();
  final List<Integer> visibleIds=new ArrayList<>();
  final Handler handler=new Handler(Looper.getMainLooper());
  String lastSignature="";
  final Runnable update=()->{refresh();handler.postDelayed(this.update,3000);};
  int dp(int n){return DesignUi.dp(this,n);}

  @Override public void onCreate(Bundle state){
    super.onCreate(state);
    root=DesignUi.screen(this);
    LinearLayout box=DesignUi.body(this,root,"环境管理",null);
    LinearLayout tools=DesignUi.row(this);
    count=DesignUi.text(this,"",13,DesignUi.MUTED);
    tools.addView(count,new LinearLayout.LayoutParams(0,-2,1));
    selectionButton=DesignUi.button(this,"多选",false,()->setSelecting(!selecting));
    tools.addView(selectionButton,new LinearLayout.LayoutParams(dp(64),dp(48)));
    LinearLayout.LayoutParams createParams=new LinearLayout.LayoutParams(dp(112),dp(48));
    createParams.leftMargin=dp(8);
    createButton=DesignUi.button(this,"＋ 新建环境",true,()->createWindow());tools.addView(createButton,createParams);
    box.addView(tools);
    preparation=DesignUi.progress(this,"正在创建环境…","完成后会打开新环境，请稍候。");
    preparation.setVisibility(View.GONE);DesignUi.addCard(box,preparation);
    LinearLayout searchRow=DesignUi.row(this),searchBox=DesignUi.column(this);
    search=DesignUi.input(searchBox,"","","搜索环境名称、分组或备注");
    search.setContentDescription("搜索环境");searchRow.addView(searchBox,new LinearLayout.LayoutParams(0,-2,1));
    filterOptions=DesignUi.button(this,"筛选",false,this::chooseFilters);LinearLayout.LayoutParams op=new LinearLayout.LayoutParams(dp(72),dp(48));op.leftMargin=dp(8);searchRow.addView(filterOptions,op);
    LinearLayout.LayoutParams sp=new LinearLayout.LayoutParams(-1,-2);sp.topMargin=dp(8);box.addView(searchRow,sp);
    search.addTextChangedListener(new TextWatcher(){
      public void beforeTextChanged(CharSequence s,int x,int c,int f){}
      public void onTextChanged(CharSequence s,int x,int b,int c){lastSignature="";refresh();}
      public void afterTextChanged(Editable e){}
    });
    groupButton=DesignUi.button(this,"全部分组 ▾",false,this::chooseGroup);
    sortButton=DesignUi.button(this,"编号排序 ▾",false,this::chooseSort);
    HorizontalScrollView filterScroll=new HorizontalScrollView(this);
    filterScroll.setHorizontalScrollBarEnabled(false);
    filters=DesignUi.row(this);filterScroll.addView(filters);
    LinearLayout.LayoutParams fp=new LinearLayout.LayoutParams(-1,dp(48));
    fp.topMargin=dp(8);box.addView(filterScroll,fp);
    cards=DesignUi.column(this);box.addView(cards);
    selectionBar=DesignUi.column(this);
    selectionBar.setPadding(dp(14),dp(8),dp(14),dp(10));
    selectionBar.setBackground(DesignUi.surface(this,DesignUi.CARD,0,DesignUi.LINE));
    LinearLayout selectionTools=DesignUi.row(this);
    selectionCount=DesignUi.text(this,"",13,DesignUi.TEXT);
    selectionTools.addView(selectionCount,new LinearLayout.LayoutParams(0,-2,1));
    visibleSelectionButton=DesignUi.button(this,"全选当前结果",false,()->selectVisible());
    visibleSelectionButton.setTextSize(12);
    selectionTools.addView(visibleSelectionButton,new LinearLayout.LayoutParams(dp(128),dp(48)));
    selectionBar.addView(selectionTools);
    LinearLayout batchActions=DesignUi.row(this);
    batchActions.setPadding(0,dp(8),0,0);
    batchGroupButton=DesignUi.button(this,"批量分组",true,()->batchGroup());
    favoriteSelectedButton=DesignUi.button(this,"收藏",false,()->batchFavorite(true));
    unfavoriteSelectedButton=DesignUi.button(this,"取消收藏",false,()->batchFavorite(false));
    Button[] actions={batchGroupButton,favoriteSelectedButton,unfavoriteSelectedButton};
    for(int i=0;i<actions.length;i++){
      actions[i].setTextSize(13);
      LinearLayout.LayoutParams params=new LinearLayout.LayoutParams(0,dp(48),1);
      if(i>0)params.leftMargin=dp(6);
      batchActions.addView(actions[i],params);
    }
    selectionBar.addView(batchActions);root.addView(selectionBar);
    root.addView(DesignUi.nav(this,1,n->WorkspaceNavigation.select(this,1,n),null));
    setContentView(root);
    if(state!=null){
      filter=Math.max(0,Math.min(4,state.getInt("filter")));
      sort=Math.max(0,Math.min(2,state.getInt("sort")));
      selectedGroup=state.getString("group");selecting=state.getBoolean("selecting");
      int[] ids=state.getIntArray("selectedIds");
      if(selecting&&ids!=null)for(int id:ids)selectedIds.add(id);
      search.setText(state.getString("query",""));
    }
    refresh();
  }
  @Override protected void onSaveInstanceState(Bundle state){
    super.onSaveInstanceState(state);
    state.putInt("filter",filter);state.putInt("sort",sort);state.putString("group",selectedGroup);
    state.putString("query",search.getText().toString());state.putBoolean("selecting",selecting);
    state.putIntArray("selectedIds",selectedIds.stream().mapToInt(Integer::intValue).toArray());
  }
  @Override protected void onResume(){super.onResume();lastSignature="";handler.removeCallbacks(update);handler.post(update);}
  @Override protected void onPause(){handler.removeCallbacks(update);super.onPause();}
  @Override protected void onNewIntent(Intent intent){super.onNewIntent(intent);setIntent(intent);lastSignature="";refresh();}
  @Override public void onBackPressed(){if(selecting){setSelecting(false);return;}super.onBackPressed();}
  Set<Integer> live(){
    Set<Integer> out=new HashSet<>();
    try{
      List<ActivityManager.RunningAppProcessInfo> rows=getSystemService(ActivityManager.class).getRunningAppProcesses();
      if(rows!=null)for(ActivityManager.RunningAppProcessInfo r:rows)out.add(r.pid);
    }catch(Exception ignored){}
    return out;
  }
  int lastWindow(){return AppSettings.recentSlot(this);}
  void chooseFilters(){
    LinearLayout choices=DesignUi.column(this);choices.setPadding(dp(18),dp(8),dp(18),dp(16));
    groupButton=DesignUi.button(this,(selectedGroup==null?"全部分组":selectedGroup.isEmpty()?"未分组":selectedGroup)+" ▾",false,this::chooseGroup);
    sortButton=DesignUi.button(this,new String[]{"编号排序 ▾","最近使用 ▾","名称排序 ▾"}[sort],false,this::chooseSort);
    choices.addView(groupButton,new LinearLayout.LayoutParams(-1,dp(48)));LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,dp(48));p.topMargin=dp(8);choices.addView(sortButton,p);
    new AlertDialog.Builder(this).setTitle("筛选与排序").setView(choices).setPositiveButton("完成",null).show();
  }
  void chooseGroup(){
    List<String> groups=new ArrayList<>();groups.add(null);groups.add("");
    JSONArray rows=ProfileCatalog.get(this).list();
    for(int i=0;i<rows.length();i++){
      JSONObject row=rows.optJSONObject(i);String group=row.optString("group");
      if(row.optBoolean("created")&&!group.isEmpty()&&!groups.contains(group))groups.add(group);
    }
    String[] names=new String[groups.size()];
    for(int i=0;i<names.length;i++)names[i]=groups.get(i)==null?"全部分组":groups.get(i).isEmpty()?"未分组":groups.get(i);
    new AlertDialog.Builder(this).setTitle("按分组查看")
      .setSingleChoiceItems(names,groups.indexOf(selectedGroup),(d,n)->{
        selectedGroup=groups.get(n);d.dismiss();lastSignature="";refresh();
      }).setNegativeButton("取消",null).show();
  }
  void chooseSort(){
    new AlertDialog.Builder(this).setTitle("环境排序")
      .setSingleChoiceItems(new String[]{"编号排序","最近使用","名称排序"},sort,(d,n)->{
        sort=n;d.dismiss();lastSignature="";refresh();
      }).setNegativeButton("取消",null).show();
  }
  static boolean matches(JSONObject row,String query,String group){
    if(group!=null&&!group.equals(row.optString("group")))return false;
    String text=row.optString("name")+" "+String.format(Locale.ROOT,"%02d",row.optInt("slot")+1)+" "+row.optString("group")+" "+row.optString("notes");
    return text.toLowerCase(Locale.ROOT).contains(query.toLowerCase(Locale.ROOT));
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
  static String networkStatus(JSONObject row,boolean active,boolean fresh){
    String mode=row.optString("mode");
    if(mode.isEmpty())return "网络 · 暂无记录";
    if(!active)return "网络 · "+mode;
    if(!fresh)return "网络 · "+mode+" · 状态待核对";
    String problem=row.optString("problem");
    return "网络 · "+mode+" · "+(!problem.isEmpty()?problem:row.optBoolean("connected")?"已连接":"待连接");
  }
  void refresh(){
    if(cards==null||selectionBar==null)return;
    JSONArray rows=ProfileCatalog.get(this).list();Set<Integer> running=live(),created=new HashSet<>();
    int[] counts=new int[5];List<JSONObject> ordered=new ArrayList<>();
    for(int i=0;i<rows.length();i++){
      JSONObject row=rows.optJSONObject(i);if(!row.optBoolean("created"))continue;
      ordered.add(row);created.add(row.optInt("slot"));counts[0]++;
      if(row.optBoolean("favorite"))counts[1]++;
      if(running.contains(row.optInt("pid")))counts[2]++;
      if(row.optBoolean("waiting")&&running.contains(row.optInt("pid")))counts[3]++;
      if(!row.optString("problem").isEmpty())counts[4]++;
    }
    selectedIds.retainAll(created);
    String query=search.getText().toString().trim();long now=System.currentTimeMillis();
    String signature=rows.toString()+running+filter+query+selectedGroup+sort+AppSettings.defaultSlot(this)+selecting+selectedIds+now/60000;
    if(signature.equals(lastSignature))return;lastSignature=signature;
    groupButton.setText((selectedGroup==null?"全部分组":selectedGroup.isEmpty()?"未分组":selectedGroup)+" ▾");
    sortButton.setText(new String[]{"编号排序 ▾","最近使用 ▾","名称排序 ▾"}[sort]);
    filterOptions.setText(selectedGroup!=null||sort!=0?"筛选 ●":"筛选");filterOptions.setContentDescription("筛选与排序，当前分组："+(selectedGroup==null?"全部":selectedGroup.isEmpty()?"未分组":selectedGroup));
    filters.removeAllViews();String[] labels={"全部","收藏","运行中","等待回复","需处理"};
    for(int i=0;i<labels.length;i++){
      final int n=i;
      Button button=DesignUi.button(this,labels[i]+" "+counts[i],false,()->{filter=n;lastSignature="";refresh();});
      button.setTextSize(12);button.setSelected(i==filter);
      if(i==filter){button.setTextColor(DesignUi.BLUE);button.setBackground(DesignUi.surface(this,0xffeaf1ff,8,0xffb6cdfa));}
      LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(dp(i==3?100:88),dp(48));
      p.rightMargin=dp(6);filters.addView(button,p);
    }
    if(sort==1)ordered.sort((l,r)->Long.compare(r.optLong("opened"),l.optLong("opened")));
    if(sort==2)ordered.sort((l,r)->l.optString("name").compareToIgnoreCase(r.optString("name")));
    cards.removeAllViews();visibleIds.clear();
    for(JSONObject row:ordered){
      boolean active=running.contains(row.optInt("pid"));
      boolean fresh=row.optLong("seen")>0&&now-row.optLong("seen")<60000;
      if(filter==1&&!row.optBoolean("favorite")||filter==2&&!active||filter==3&&!(row.optBoolean("waiting")&&active)||filter==4&&row.optString("problem").isEmpty()||!matches(row,query,selectedGroup))continue;
      int id=row.optInt("slot");visibleIds.add(id);
      LinearLayout card=DesignUi.card(this);
      card.setContentDescription((selecting?"选择环境：":"打开环境：")+row.optString("name"));
      card.setClickable(true);card.setFocusable(true);
      card.setOnClickListener(v->{if(selecting)toggleSelection(id);else openWindow(id,"chat");});
      card.setOnLongClickListener(v->{toggleSelection(id);return true;});
      if(selecting&&selectedIds.contains(id))card.setBackground(DesignUi.surface(this,0xfff0f5ff,12,DesignUi.BLUE));
      LinearLayout head=DesignUi.row(this);
      if(selecting){
        CheckBox check=new CheckBox(this);check.setChecked(selectedIds.contains(id));
        check.setContentDescription("选择环境 "+String.format(Locale.ROOT,"%02d",id+1)+" "+row.optString("name"));
        check.setOnCheckedChangeListener((b,selected)->toggleSelection(id));
        head.addView(check,new LinearLayout.LayoutParams(dp(48),dp(48)));
      }else head.addView(DesignUi.badge(this,String.format(Locale.ROOT,"%02d",id+1),DesignUi.BLUE));
      LinearLayout title=DesignUi.column(this);title.setPadding(dp(10),0,dp(6),0);
      TextView name=DesignUi.text(this,(row.optBoolean("favorite")?"★ ":"")+row.optString("name"),16,DesignUi.TEXT);
      name.setSingleLine();name.setEllipsize(TextUtils.TruncateAt.END);title.addView(name);
      String group=row.optString("group").isEmpty()?"未分组":row.optString("group");
      TextView sub=DesignUi.text(this,(selecting?String.format(Locale.ROOT,"%02d",id+1)+" · ":"")+group+(id==AppSettings.defaultSlot(this)?" · 默认":"")+(!row.optString("draft").isEmpty()?" · 草稿":""),12,DesignUi.MUTED);
      sub.setSingleLine();sub.setEllipsize(TextUtils.TruncateAt.END);title.addView(sub);
      head.addView(title,new LinearLayout.LayoutParams(0,-2,1));
      boolean problem=!row.optString("problem").isEmpty();
      String status=problem?(active?"需处理":"上次异常"):active?(row.optBoolean("waiting")?"等待回复":fresh?"运行中":"待核对"):"未运行";
      head.addView(DesignUi.badge(this,status,problem?DesignUi.RED:active?DesignUi.GREEN:DesignUi.MUTED));card.addView(head);
      TextView network=DesignUi.text(this,networkStatus(row,active,fresh),12,problem?DesignUi.RED:DesignUi.MUTED);
      network.setMaxLines(2);network.setEllipsize(TextUtils.TruncateAt.END);network.setPadding(0,dp(8),0,dp(4));card.addView(network);
      TextView recent=DesignUi.text(this,"最近使用 · "+recentUse(row.optLong("opened"),now),11,DesignUi.MUTED);
      if(selecting)card.addView(recent);
      else{
        LinearLayout actions=DesignUi.row(this);actions.setPadding(0,dp(4),0,0);
        actions.addView(recent,new LinearLayout.LayoutParams(0,-2,1));
        Button open=DesignUi.button(this,"打开环境",true,()->openWindow(id,"chat"));open.setContentDescription("打开环境 "+row.optString("name"));open.setTextSize(13);open.setPadding(dp(4),0,dp(4),0);
        actions.addView(open,new LinearLayout.LayoutParams(dp(96),dp(48)));
        Button more=DesignUi.button(this,"更多",false,()->menu(id));more.setTextSize(12);more.setPadding(dp(4),0,dp(4),0);more.setContentDescription("更多操作 "+row.optString("name"));
        LinearLayout.LayoutParams moreParams=new LinearLayout.LayoutParams(dp(48),dp(48));moreParams.leftMargin=dp(6);actions.addView(more,moreParams);card.addView(actions);
      }
      DesignUi.addCard(cards,card);
    }
    count.setText(visibleIds.size()==counts[0]?counts[0]+" 个环境":"显示 "+visibleIds.size()+" / "+counts[0]);
    if(visibleIds.isEmpty()){
      DesignUi.empty(cards,"没有匹配的环境","试试其他关键词，或重置分组与状态筛选。","重置筛选",()->{filter=0;selectedGroup=null;search.setText("");lastSignature="";refresh();});
    }
    updateSelectionBar(rows);
  }
  void setSelecting(boolean value){
    selecting=value;if(!value)selectedIds.clear();lastSignature="";refresh();
  }
  void toggleSelection(int id){
    if(!ProfileCatalog.get(this).item(id).optBoolean("created"))return;
    selecting=true;if(!selectedIds.remove(id))selectedIds.add(id);lastSignature="";refresh();
  }
  void selectVisible(){
    if(visibleIds.isEmpty())return;
    selecting=true;
    if(selectedIds.containsAll(visibleIds))selectedIds.removeAll(visibleIds);else selectedIds.addAll(visibleIds);
    lastSignature="";refresh();
  }
  void updateSelectionBar(JSONArray rows){
    selectionButton.setText(selecting?"完成":"多选");selectionButton.setSelected(selecting);
    selectionBar.setVisibility(selecting?View.VISIBLE:View.GONE);
    int hidden=0;boolean hasFavorite=false,hasUnfavorite=false;
    for(int id:selectedIds)if(!visibleIds.contains(id))hidden++;
    for(int i=0;i<rows.length();i++){
      JSONObject row=rows.optJSONObject(i);
      if(selectedIds.contains(row.optInt("slot"))){if(row.optBoolean("favorite"))hasFavorite=true;else hasUnfavorite=true;}
    }
    selectionCount.setText("已选 "+selectedIds.size()+" 个"+(hidden>0?"\n筛选外 "+hidden+" 个":""));
    visibleSelectionButton.setText(!visibleIds.isEmpty()&&selectedIds.containsAll(visibleIds)?"取消当前结果选中":"全选当前结果");
    visibleSelectionButton.setEnabled(!visibleIds.isEmpty());
    batchGroupButton.setEnabled(!selectedIds.isEmpty());
    favoriteSelectedButton.setEnabled(hasUnfavorite);unfavoriteSelectedButton.setEnabled(hasFavorite);
    for(Button button:new Button[]{visibleSelectionButton,batchGroupButton,favoriteSelectedButton,unfavoriteSelectedButton})button.setAlpha(button.isEnabled()?1f:.45f);
  }
  void batchFavorite(boolean favorite){
    if(selectedIds.isEmpty())return;
    int changed=ProfileCatalog.get(this).favorites(new ArrayList<>(selectedIds),favorite);
    lastSignature="";refresh();SavedFileActions.toast(this,changed+" 个环境已"+(favorite?"收藏":"取消收藏"));
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
    if(!groups.isEmpty())DesignUi.action(box,"选择已有分组",false,()->new AlertDialog.Builder(this).setTitle("已有分组")
      .setItems(groups.toArray(new String[0]),(d,n)->group.setText(groups.get(n))).setNegativeButton("取消",null).show());
    AlertDialog dialog=new AlertDialog.Builder(this).setTitle("批量分组").setView(box)
      .setPositiveButton("保存分组",null).setNegativeButton("取消",null).create();
    dialog.show();
    dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{
      int changed=catalog.group(ids,group.getText().toString());dialog.dismiss();lastSignature="";refresh();
      SavedFileActions.toast(this,"已更新 "+changed+" 个环境的分组");
    });
    return dialog;
  }
  void menu(int id){
    JSONObject row=ProfileCatalog.get(this).item(id);
    String[] labels={"编辑环境","分组与备注",row.optBoolean("favorite")?"取消收藏":"收藏环境",id==AppSettings.defaultSlot(this)?"当前默认环境":"设为默认启动环境","网络配置","选择此环境"};
    new AlertDialog.Builder(this).setTitle(row.optString("name")).setItems(labels,(d,n)->{
      if(n==0)openWindow(id,"edit");if(n==1)metadata(id);
      if(n==2){ProfileCatalog.get(this).favorite(id,!row.optBoolean("favorite"));lastSignature="";refresh();}
      if(n==3){AppSettings.defaultSlot(this,id);lastSignature="";refresh();}
      if(n==4)openWindow(id,"network");if(n==5)toggleSelection(id);
    }).setNegativeButton("关闭",null).show();
  }
  void metadata(int id){
    JSONObject row=ProfileCatalog.get(this).item(id);LinearLayout box=DesignUi.column(this);
    box.setPadding(dp(18),0,dp(18),dp(16));
    EditText group=DesignUi.input(box,"分组",row.optString("group"),"留空为未分组");
    EditText notes=DesignUi.input(box,"备注",row.optString("notes"),"环境用途说明");
    group.setFilters(new InputFilter[]{new InputFilter.LengthFilter(12)});
    notes.setFilters(new InputFilter[]{new InputFilter.LengthFilter(120)});
    AlertDialog dialog=new AlertDialog.Builder(this).setTitle("分组与备注 · "+row.optString("name")).setView(box)
      .setPositiveButton("保存",(d,w)->{
        ProfileCatalog.get(this).details(id,group.getText().toString(),notes.getText().toString());lastSignature="";refresh();DesignUi.feedback(this,"分组与备注已保存");
      }).setNegativeButton("取消",null).show();
    DesignUi.protectEdits(this,dialog,()->!group.getText().toString().equals(row.optString("group"))||!notes.getText().toString().equals(row.optString("notes")));
  }
  void openWindow(int id,String action){
    if(id<0||id>=Profiles.MAX)return;
    if(id>0&&Build.VERSION.SDK_INT<28){SavedFileActions.toast(this,"独立环境需要 Android 9 或更新版本");return;}
    ProfileCatalog.get(this).opened(id);
    startActivity(new Intent(this,Profiles.activity(id)).putExtra("openWindowAction",action)
      .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_REORDER_TO_FRONT));
  }
  void createWindow(){
    if(preparing)return;
    if(Build.VERSION.SDK_INT<28){SavedFileActions.toast(this,"独立环境需要 Android 9 或更新版本");return;}
    JSONArray rows=ProfileCatalog.get(this).list();int next=-1;
    for(int i=1;i<rows.length();i++)if(!rows.optJSONObject(i).optBoolean("created")){next=i;break;}
    if(next<0){SavedFileActions.toast(this,"已达到 8 个环境");return;}
    new Wizard(next,rows).show();
  }
  final class Wizard {
    final int id;final JSONArray windows;final Dialog dialog;
    LinearLayout body,actions;EditText name;AlertDialog exitPrompt;
    int step,sourceType,sourceSlot;String title,group="";boolean makeDefault;
    Wizard(int id,JSONArray windows){
      this.id=id;this.windows=windows;title="环境 "+(id+1);sourceSlot=AppSettings.defaultSlot(WindowHomeActivity.this);
      dialog=new Dialog(WindowHomeActivity.this){@Override public void onBackPressed(){Wizard.this.back();}};
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
      boolean dirty=!title.equals("环境 "+(id+1))||!group.isEmpty()||sourceType!=0||makeDefault;
      if(!dirty){dialog.dismiss();return;}
      if(exitPrompt!=null&&exitPrompt.isShowing())return;
      exitPrompt=new AlertDialog.Builder(WindowHomeActivity.this).setTitle("放弃创建环境？")
        .setMessage("退出后，本次填写的名称、分组和网络来源不会保存。")
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
      DesignUi.field(body,"网络来源",sourceType==2?"创建后手动配置":Profiles.display(WindowHomeActivity.this,sourceType==0?AppSettings.defaultSlot(WindowHomeActivity.this):sourceSlot));
      CheckBox selected=new CheckBox(WindowHomeActivity.this);selected.setText("设为默认环境");selected.setTextColor(DesignUi.TEXT);selected.setMinHeight(dp(48));
      DesignUi.note(body,sourceType==2?"创建后会打开网络配置页。保存网络方式后，再登录 ChatGPT。":"创建后会使用复制的网络配置打开会话，请在新环境单独登录 ChatGPT。");
      selected.setChecked(makeDefault);selected.setOnCheckedChangeListener((b,c)->makeDefault=c);body.addView(selected);
    }
    void next(){
      if(step==0){if(title.trim().isEmpty()||title.trim().length()>24){name.setError("名称需要 1–24 字");name.requestFocus();return;}title=title.trim();}
      if(step<2){step++;render();}else create();
    }
    void create(){
      if(preparing)return;preparing=true;createButton.setEnabled(false);preparation.setVisibility(View.VISIBLE);
      Context source=Profiles.context(WindowHomeActivity.this,sourceType==0?AppSettings.defaultSlot(WindowHomeActivity.this):sourceSlot);
      boolean clone=sourceType!=2;dialog.dismiss();
      new Thread(()->{
        String error="";try{Profiles.prepare(source,id,clone);Profiles.rename(source,id,title);ProfileCatalog.get(source).details(id,group,"");if(makeDefault)AppSettings.defaultSlot(source,id);}
        catch(Exception e){error="环境准备失败，请重试";}
        String failure=error;handler.post(()->{
          preparing=false;if(isFinishing()||isDestroyed())return;createButton.setEnabled(true);preparation.setVisibility(View.GONE);lastSignature="";refresh();
          if(failure.isEmpty())openWindow(id,sourceType==2?"network":"chat");else DesignUi.feedback(WindowHomeActivity.this,failure);
        });
      },"window-create").start();
    }
  }
}
