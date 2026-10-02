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
    tools.addView(DesignUi.button(this,"＋ 新建环境",true,()->createWindow()),createParams);
    box.addView(tools);
    search=DesignUi.input(box,"查找环境","","名称、编号、分组或备注");
    search.addTextChangedListener(new TextWatcher(){
      public void beforeTextChanged(CharSequence s,int x,int c,int f){}
      public void onTextChanged(CharSequence s,int x,int b,int c){lastSignature="";refresh();}
      public void afterTextChanged(Editable e){}
    });
    LinearLayout controls=DesignUi.row(this);
    controls.setPadding(0,dp(10),0,dp(4));
    groupButton=DesignUi.button(this,"全部分组 ▾",false,()->chooseGroup());
    sortButton=DesignUi.button(this,"编号排序 ▾",false,()->chooseSort());
    controls.addView(groupButton,new LinearLayout.LayoutParams(0,dp(44),1));
    LinearLayout.LayoutParams right=new LinearLayout.LayoutParams(0,dp(44),1);
    right.leftMargin=dp(8);
    controls.addView(sortButton,right);box.addView(controls);
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
    selectionTools.addView(visibleSelectionButton,new LinearLayout.LayoutParams(dp(128),dp(44)));
    selectionBar.addView(selectionTools);
    LinearLayout batchActions=DesignUi.row(this);
    batchActions.setPadding(0,dp(8),0,0);
    batchGroupButton=DesignUi.button(this,"批量分组",true,()->batchGroup());
    favoriteSelectedButton=DesignUi.button(this,"收藏",false,()->batchFavorite(true));
    unfavoriteSelectedButton=DesignUi.button(this,"取消收藏",false,()->batchFavorite(false));
    Button[] actions={batchGroupButton,favoriteSelectedButton,unfavoriteSelectedButton};
    for(int i=0;i<actions.length;i++){
      actions[i].setTextSize(13);
      LinearLayout.LayoutParams params=new LinearLayout.LayoutParams(0,dp(44),1);
      if(i>0)params.leftMargin=dp(6);
      batchActions.addView(actions[i],params);
    }
    selectionBar.addView(batchActions);root.addView(selectionBar);
    root.addView(DesignUi.nav(this,1,n->{
      if(n==1)return;
      if(n==2)startActivity(new Intent(this,DownloadCenterActivity.class));
      else if(n==4)startActivity(new Intent(this,AppSettingsActivity.class));
      else openWindow(lastWindow(),n==3?"network":"chat");
    },null));
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
    if(mode.isEmpty())return "网络状态尚未记录";
    if(!active)return "网络 · "+mode+" · 未运行";
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
    filters.removeAllViews();String[] labels={"全部","收藏","运行中","等待回复","需处理"};
    for(int i=0;i<labels.length;i++){
      final int n=i;
      Button button=DesignUi.button(this,labels[i]+" "+counts[i],false,()->{filter=n;lastSignature="";refresh();});
      button.setTextSize(12);button.setSelected(i==filter);
      if(i==filter){button.setTextColor(DesignUi.BLUE);button.setBackground(DesignUi.surface(this,0xffeaf1ff,8,0xffb6cdfa));}
      LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(dp(i==3?100:88),dp(44));
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
      TextView sub=DesignUi.text(this,(selecting?String.format(Locale.ROOT,"%02d",id+1)+" · ":"")+group,12,DesignUi.MUTED);
      sub.setSingleLine();sub.setEllipsize(TextUtils.TruncateAt.END);title.addView(sub);
      head.addView(title,new LinearLayout.LayoutParams(0,-2,1));
      boolean problem=!row.optString("problem").isEmpty();
      String status=problem?(active?"需处理":"上次异常"):active?(row.optBoolean("waiting")?"等待回复":fresh?"运行中":"待核对"):"未运行";
      head.addView(DesignUi.badge(this,status,problem?DesignUi.RED:active?DesignUi.GREEN:DesignUi.MUTED));card.addView(head);
      DesignUi.note(card,networkStatus(row,active,fresh));
      TextView recent=DesignUi.text(this,"最近使用 · "+recentUse(row.optLong("opened"),now),12,DesignUi.MUTED);
      card.addView(recent);
      LinearLayout tags=DesignUi.row(this);
      if(id==AppSettings.defaultSlot(this))tags.addView(DesignUi.badge(this,"默认启动",DesignUi.BLUE));
      if(!row.optString("draft").isEmpty())tags.addView(DesignUi.badge(this,"有配置草稿",DesignUi.MUTED));
      if(tags.getChildCount()>0){tags.setPadding(0,dp(8),0,0);card.addView(tags);}
      if(!row.optString("notes").isEmpty()){
        TextView note=DesignUi.text(this,row.optString("notes"),12,DesignUi.MUTED);
        note.setSingleLine();note.setEllipsize(TextUtils.TruncateAt.END);note.setPadding(0,dp(6),0,0);card.addView(note);
      }
      if(!selecting){
        LinearLayout actions=DesignUi.row(this);actions.setPadding(0,dp(10),0,0);
        Button open=DesignUi.button(this,"打开环境",true,()->openWindow(id,"chat"));
        open.setContentDescription("打开环境 "+row.optString("name"));
        actions.addView(open,new LinearLayout.LayoutParams(0,dp(48),1));
        Button more=DesignUi.button(this,"更多",false,()->menu(id));
        more.setContentDescription("更多操作 "+row.optString("name"));
        LinearLayout.LayoutParams moreParams=new LinearLayout.LayoutParams(dp(88),dp(48));
        moreParams.leftMargin=dp(8);actions.addView(more,moreParams);card.addView(actions);
      }
      DesignUi.addCard(cards,card);
    }
    count.setText("环境 "+counts[0]+" / 8\n当前显示 "+visibleIds.size());
    if(visibleIds.isEmpty()){
      DesignUi.note(cards,"没有符合条件的环境。可修改关键词或重置筛选。");
      DesignUi.action(cards,"重置筛选",false,()->{filter=0;selectedGroup=null;search.setText("");lastSignature="";refresh();});
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
    new AlertDialog.Builder(this).setTitle("分组与备注 · "+row.optString("name")).setView(box)
      .setPositiveButton("保存",(d,w)->{
        ProfileCatalog.get(this).details(id,group.getText().toString(),notes.getText().toString());lastSignature="";refresh();
      }).setNegativeButton("取消",null).show();
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
    final int id;final JSONArray windows;final Dialog dialog=new Dialog(WindowHomeActivity.this);LinearLayout body;int step,sourceType;String title;String group="";int sourceSlot;boolean makeDefault;Wizard(int id,JSONArray windows){this.id=id;this.windows=windows;title="环境 "+(id+1);sourceSlot=AppSettings.defaultSlot(WindowHomeActivity.this);}
    void show(){LinearLayout screen=DesignUi.screen(WindowHomeActivity.this);body=DesignUi.body(WindowHomeActivity.this,screen,"创建环境",()->dialog.dismiss());dialog.setContentView(screen);dialog.show();dialog.getWindow().setBackgroundDrawableResource(android.R.color.transparent);dialog.getWindow().setLayout(-1,-1);render();}
    void render(){body.removeAllViews();body.addView(DesignUi.tabs(WindowHomeActivity.this,new String[]{"基本信息","网络来源","确认创建"},step,n->{if(n<step){step=n;render();}}));if(step==0){EditText name=DesignUi.input(body,"环境名称",title,"例如：工作号、研究专用");name.addTextChangedListener(new TextWatcher(){public void beforeTextChanged(CharSequence s,int a,int c,int f){}public void onTextChanged(CharSequence s,int a,int b,int c){title=s.toString();}public void afterTextChanged(Editable e){}});EditText groupInput=DesignUi.input(body,"分组（可选）",group,"最多 12 字，留空为未分组");groupInput.setFilters(new InputFilter[]{new InputFilter.LengthFilter(12)});groupInput.addTextChangedListener(new TextWatcher(){public void beforeTextChanged(CharSequence s,int a,int c,int f){}public void onTextChanged(CharSequence s,int a,int b,int c){group=s.toString().trim();}public void afterTextChanged(Editable e){}});DesignUi.field(body,"选择平台","ChatGPT · chatgpt.com");DesignUi.note(body,"当前支持 ChatGPT，创建后需单独登录。");DesignUi.action(body,"下一步：配置来源 →",true,()->{if(title.trim().isEmpty()||title.trim().length()>24){name.setError("名称需要 1–24 字");return;}title=title.trim();step=1;render();});}
      if(step==1){String[] choices={"复制默认环境网络","复制指定环境网络","创建后手动配置"};for(int i=0;i<3;i++){final int n=i;LinearLayout card=DesignUi.card(WindowHomeActivity.this);RadioButton radio=new RadioButton(WindowHomeActivity.this);radio.setText(choices[i]);radio.setTextColor(DesignUi.TEXT);radio.setChecked(sourceType==i);card.addView(radio);card.addView(DesignUi.text(WindowHomeActivity.this,i==0?"复制默认环境的网络配置":i==1?"选择一个环境，只复制网络设置":"新环境内手动设置网络",12,DesignUi.MUTED));radio.setOnClickListener(v->{sourceType=n;render();});DesignUi.addCard(body,card);}if(sourceType==1){String[] names=new String[windows.length()];java.util.List<Integer> ids=new ArrayList<>();java.util.List<String> labels=new ArrayList<>();for(int i=0;i<windows.length();i++)if(windows.optJSONObject(i).optBoolean("created")){ids.add(i);labels.add(windows.optJSONObject(i).optString("name"));}Spinner spinner=new Spinner(WindowHomeActivity.this);spinner.setAdapter(new ArrayAdapter<>(WindowHomeActivity.this,android.R.layout.simple_spinner_dropdown_item,labels));int selected=ids.indexOf(sourceSlot);spinner.setSelection(selected>=0?selected:0);spinner.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener(){public void onItemSelected(android.widget.AdapterView<?> p,View v,int pos,long item){sourceSlot=ids.get(pos);}public void onNothingSelected(android.widget.AdapterView<?> p){}});body.addView(spinner);}DesignUi.note(body,"登录、Cookie、聊天、草稿和环境自检基线分别保存。这里的复制只涉及网络配置。");DesignUi.action(body,"下一步：确认创建 →",true,()->{step=2;render();});}
      if(step==2){DesignUi.field(body,"环境名称",title);DesignUi.field(body,"平台","ChatGPT");DesignUi.field(body,"分组",group.isEmpty()?"未分组":group);DesignUi.field(body,"网络来源",sourceType==2?"自定义配置":Profiles.display(WindowHomeActivity.this,sourceType==0?AppSettings.defaultSlot(WindowHomeActivity.this):sourceSlot));CheckBox selected=new CheckBox(WindowHomeActivity.this);selected.setText("设为默认环境");selected.setChecked(makeDefault);selected.setOnCheckedChangeListener((b,c)->makeDefault=c);body.addView(selected);DesignUi.action(body,"创建并打开",true,()->create());}}
    void create(){if(preparing)return;preparing=true;Context source=Profiles.context(WindowHomeActivity.this,sourceType==0?AppSettings.defaultSlot(WindowHomeActivity.this):sourceSlot);boolean clone=sourceType!=2;dialog.dismiss();new Thread(()->{String error="";try{Profiles.prepare(source,id,clone);Profiles.rename(source,id,title);ProfileCatalog.get(source).details(id,group,"");if(makeDefault)AppSettings.defaultSlot(source,id);}catch(Exception e){error="环境准备失败，请重试";}String failure=error;handler.post(()->{preparing=false;if(isFinishing()||isDestroyed())return;lastSignature="";refresh();if(failure.isEmpty())openWindow(id,sourceType==2?"network":"chat");else SavedFileActions.toast(WindowHomeActivity.this,failure);});},"window-create").start();}
  }
}
