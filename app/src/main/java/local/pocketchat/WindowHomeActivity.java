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
  LinearLayout root,cards,filters;
  TextView count;
  EditText search;
  Button groupButton,sortButton;
  int filter,sort;
  String selectedGroup;
  final Handler handler=new Handler(Looper.getMainLooper());
  boolean preparing;
  String lastSignature="";
  final Runnable update=()->{refresh();handler.postDelayed(this.update,3000);};
  int dp(int n){return DesignUi.dp(this,n);}

  @Override public void onCreate(Bundle state){
    super.onCreate(state);root=DesignUi.screen(this);LinearLayout box=DesignUi.body(this,root,"环境管理",null);
    LinearLayout tools=DesignUi.row(this);count=DesignUi.text(this,"",13,DesignUi.MUTED);
    tools.addView(count,new LinearLayout.LayoutParams(0,-2,1));
    tools.addView(DesignUi.button(this,"＋ 新建环境",true,()->createWindow()),new LinearLayout.LayoutParams(dp(120),dp(48)));box.addView(tools);
    search=DesignUi.input(box,"查找环境","","名称、编号、分组或备注");
    search.addTextChangedListener(new TextWatcher(){public void beforeTextChanged(CharSequence s,int x,int c,int f){}public void onTextChanged(CharSequence s,int x,int b,int c){lastSignature="";refresh();}public void afterTextChanged(Editable e){}});
    LinearLayout controls=DesignUi.row(this);controls.setPadding(0,dp(10),0,dp(4));
    groupButton=DesignUi.button(this,"全部分组 ▾",false,()->chooseGroup());sortButton=DesignUi.button(this,"编号排序 ▾",false,()->chooseSort());
    LinearLayout.LayoutParams left=new LinearLayout.LayoutParams(0,dp(44),1);controls.addView(groupButton,left);
    LinearLayout.LayoutParams right=new LinearLayout.LayoutParams(0,dp(44),1);right.leftMargin=dp(8);controls.addView(sortButton,right);box.addView(controls);
    HorizontalScrollView filterScroll=new HorizontalScrollView(this);filterScroll.setHorizontalScrollBarEnabled(false);filters=DesignUi.row(this);filterScroll.addView(filters);
    LinearLayout.LayoutParams fp=new LinearLayout.LayoutParams(-1,dp(48));fp.topMargin=dp(8);box.addView(filterScroll,fp);
    cards=DesignUi.column(this);box.addView(cards);
    root.addView(DesignUi.nav(this,1,n->{
      if(n==1)return;
      if(n==2)startActivity(new Intent(this,DownloadCenterActivity.class));
      else if(n==4)startActivity(new Intent(this,AppSettingsActivity.class));
      else openWindow(lastWindow(),n==3?"network":n==4?"settings":"chat");
    },null));setContentView(root);
    if(state!=null){filter=state.getInt("filter");sort=state.getInt("sort");selectedGroup=state.getString("group");search.setText(state.getString("query",""));}
    refresh();
  }
  @Override protected void onSaveInstanceState(Bundle state){super.onSaveInstanceState(state);state.putInt("filter",filter);state.putInt("sort",sort);state.putString("group",selectedGroup);state.putString("query",search.getText().toString());}
  @Override protected void onResume(){super.onResume();lastSignature="";handler.removeCallbacks(update);handler.post(update);}
  @Override protected void onPause(){handler.removeCallbacks(update);super.onPause();}
  @Override protected void onNewIntent(Intent intent){super.onNewIntent(intent);setIntent(intent);lastSignature="";refresh();}
  Set<Integer> live(){Set<Integer> out=new HashSet<>();try{List<ActivityManager.RunningAppProcessInfo> rows=getSystemService(ActivityManager.class).getRunningAppProcesses();if(rows!=null)for(ActivityManager.RunningAppProcessInfo r:rows)out.add(r.pid);}catch(Exception ignored){}return out;}
  int lastWindow(){return AppSettings.recentSlot(this);}
  void chooseGroup(){
    List<String> groups=new ArrayList<>();groups.add(null);groups.add("");JSONArray rows=ProfileCatalog.get(this).list();
    for(int i=0;i<rows.length();i++){JSONObject r=rows.optJSONObject(i);String group=r.optString("group");if(r.optBoolean("created")&&!group.isEmpty()&&!groups.contains(group))groups.add(group);}
    String[] names=new String[groups.size()];for(int i=0;i<names.length;i++)names[i]=groups.get(i)==null?"全部分组":groups.get(i).isEmpty()?"未分组":groups.get(i);
    new AlertDialog.Builder(this).setTitle("按分组查看").setSingleChoiceItems(names,groups.indexOf(selectedGroup),(d,n)->{selectedGroup=groups.get(n);d.dismiss();lastSignature="";refresh();}).setNegativeButton("取消",null).show();
  }
  void chooseSort(){new AlertDialog.Builder(this).setTitle("环境排序").setSingleChoiceItems(new String[]{"编号排序","最近使用","名称排序"},sort,(d,n)->{sort=n;d.dismiss();lastSignature="";refresh();}).setNegativeButton("取消",null).show();}
  static boolean matches(JSONObject row,String query,String group){
    if(group!=null&&!group.equals(row.optString("group")))return false;
    String text=row.optString("name")+" "+String.format(Locale.ROOT,"%02d",row.optInt("slot")+1)+" "+row.optString("group")+" "+row.optString("notes");
    return text.toLowerCase(Locale.ROOT).contains(query.toLowerCase(Locale.ROOT));
  }
  void refresh(){
    if(cards==null)return;JSONArray rows=ProfileCatalog.get(this).list();Set<Integer> running=live();int[] counts=new int[5];List<JSONObject> ordered=new ArrayList<>();
    for(int i=0;i<rows.length();i++){JSONObject r=rows.optJSONObject(i);if(!r.optBoolean("created"))continue;ordered.add(r);counts[0]++;if(r.optBoolean("favorite"))counts[1]++;if(running.contains(r.optInt("pid")))counts[2]++;if(r.optBoolean("waiting")&&running.contains(r.optInt("pid")))counts[3]++;if(!r.optString("problem").isEmpty())counts[4]++;}
    String query=search.getText().toString().trim();String signature=rows.toString()+running+filter+query+selectedGroup+sort+AppSettings.defaultSlot(this);
    if(signature.equals(lastSignature))return;lastSignature=signature;
    count.setText("环境总数 "+counts[0]+" / 8\n运行 "+counts[2]+" · 等待 "+counts[3]);
    groupButton.setText((selectedGroup==null?"全部分组":selectedGroup.isEmpty()?"未分组":selectedGroup)+" ▾");sortButton.setText(new String[]{"编号排序 ▾","最近使用 ▾","名称排序 ▾"}[sort]);
    filters.removeAllViews();String[] labels={"全部","收藏","运行中","等待回复","需处理"};
    for(int i=0;i<labels.length;i++){final int n=i;Button button=DesignUi.button(this,labels[i]+" "+counts[i],false,()->{filter=n;lastSignature="";refresh();});button.setTextSize(12);button.setSelected(i==filter);if(i==filter){button.setTextColor(DesignUi.BLUE);button.setBackground(DesignUi.surface(this,0xffeaf1ff,8,0xffb6cdfa));}LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(dp(i==3?100:88),dp(44));p.rightMargin=dp(6);filters.addView(button,p);}
    if(sort==1)ordered.sort((l,r)->Long.compare(r.optLong("opened"),l.optLong("opened")));if(sort==2)ordered.sort((l,r)->l.optString("name").compareToIgnoreCase(r.optString("name")));
    cards.removeAllViews();int shown=0;
    for(JSONObject r:ordered){
      boolean active=running.contains(r.optInt("pid")),fresh=System.currentTimeMillis()-r.optLong("seen")<60000;
      if(filter==1&&!r.optBoolean("favorite")||filter==2&&!active||filter==3&&!(r.optBoolean("waiting")&&active)||filter==4&&r.optString("problem").isEmpty()||!matches(r,query,selectedGroup))continue;
      shown++;int id=r.optInt("slot");LinearLayout card=DesignUi.card(this);card.setContentDescription("打开环境："+r.optString("name"));card.setClickable(true);card.setFocusable(true);card.setOnClickListener(v->openWindow(id,"chat"));
      LinearLayout head=DesignUi.row(this);head.addView(DesignUi.badge(this,String.format(Locale.ROOT,"%02d",id+1),DesignUi.BLUE));
      LinearLayout title=DesignUi.column(this);title.setPadding(dp(10),0,dp(6),0);title.addView(DesignUi.text(this,(r.optBoolean("favorite")?"★ ":"")+r.optString("name"),16,DesignUi.TEXT));title.addView(DesignUi.text(this,"ChatGPT · "+(r.optString("group").isEmpty()?"未分组":r.optString("group")),12,DesignUi.MUTED));head.addView(title,new LinearLayout.LayoutParams(0,-2,1));
      boolean problem=!r.optString("problem").isEmpty();String status=problem?(active?"需处理":"上次异常"):active?(r.optBoolean("waiting")?"等待回复":fresh?"运行中":"待核对"):"未运行";
      head.addView(DesignUi.badge(this,status,problem?DesignUi.RED:active?DesignUi.GREEN:DesignUi.MUTED));card.addView(head);
      String mode=r.optString("mode");if(mode.isEmpty())mode="网络状态待记录";int privacy=Math.max(0,Math.min(2,r.optInt("privacy",1)));
      DesignUi.note(card,mode+" · "+new String[]{"兼容保护","标准保护","强化保护"}[privacy]);
      LinearLayout tags=DesignUi.row(this);if(id==AppSettings.defaultSlot(this))tags.addView(DesignUi.badge(this,"默认启动",DesignUi.BLUE));
      if(!r.optString("draft").isEmpty())tags.addView(DesignUi.badge(this,"有配置草稿",DesignUi.MUTED));if(tags.getChildCount()>0)card.addView(tags);
      if(!r.optString("notes").isEmpty()){TextView note=DesignUi.text(this,r.optString("notes"),12,DesignUi.MUTED);note.setMaxLines(2);note.setEllipsize(TextUtils.TruncateAt.END);note.setPadding(0,dp(6),0,dp(6));card.addView(note);}
      LinearLayout actions=DesignUi.row(this);actions.setPadding(0,dp(10),0,0);String[] names={"打开","编辑环境","更多"};
      for(int i=0;i<names.length;i++){final int n=i;Button b=DesignUi.button(this,names[i],i==0,()->{if(n==0)openWindow(id,"chat");if(n==1)openWindow(id,"edit");if(n==2)menu(id);});b.setTextSize(13);b.setContentDescription(names[i]+" "+r.optString("name"));LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(0,dp(48),i==2?.7f:1);if(i>0)p.leftMargin=dp(6);actions.addView(b,p);}card.addView(actions);DesignUi.addCard(cards,card);
    }
    if(shown==0){DesignUi.note(cards,"没有符合条件的环境。可修改关键词或重置筛选。");DesignUi.action(cards,"重置筛选",false,()->{filter=0;selectedGroup=null;search.setText("");lastSignature="";refresh();});}
  }
  void menu(int id){
    JSONObject row=ProfileCatalog.get(this).item(id);String[] labels={"打开环境","编辑环境","分组与备注",row.optBoolean("favorite")?"取消收藏":"收藏环境",id==AppSettings.defaultSlot(this)?"当前默认环境":"设为默认启动环境","网络配置"};
    new AlertDialog.Builder(this).setTitle(row.optString("name")).setItems(labels,(d,n)->{if(n==0)openWindow(id,"chat");if(n==1)openWindow(id,"edit");if(n==2)metadata(id);if(n==3){ProfileCatalog.get(this).favorite(id,!row.optBoolean("favorite"));lastSignature="";refresh();}if(n==4){AppSettings.defaultSlot(this,id);lastSignature="";refresh();}if(n==5)openWindow(id,"network");}).setNegativeButton("关闭",null).show();
  }
  void metadata(int id){
    JSONObject row=ProfileCatalog.get(this).item(id);LinearLayout box=DesignUi.column(this);box.setPadding(dp(18),0,dp(18),dp(16));
    EditText group=DesignUi.input(box,"分组",row.optString("group"),"留空为未分组"),notes=DesignUi.input(box,"备注",row.optString("notes"),"环境用途说明");group.setFilters(new InputFilter[]{new InputFilter.LengthFilter(12)});notes.setFilters(new InputFilter[]{new InputFilter.LengthFilter(120)});
    new AlertDialog.Builder(this).setTitle("分组与备注 · "+row.optString("name")).setView(box).setPositiveButton("保存",(d,w)->{ProfileCatalog.get(this).details(id,group.getText().toString(),notes.getText().toString());lastSignature="";refresh();}).setNegativeButton("取消",null).show();
  }
  void openWindow(int id,String action){if(id<0||id>=Profiles.MAX)return;if(id>0&&Build.VERSION.SDK_INT<28){SavedFileActions.toast(this,"独立环境需要 Android 9 或更新版本");return;}ProfileCatalog.get(this).opened(id);startActivity(new Intent(this,Profiles.activity(id)).putExtra("openWindowAction",action).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_REORDER_TO_FRONT));}
  void createWindow(){if(preparing)return;if(Build.VERSION.SDK_INT<28){SavedFileActions.toast(this,"独立环境需要 Android 9 或更新版本");return;}JSONArray rows=ProfileCatalog.get(this).list();int next=-1;for(int i=1;i<rows.length();i++)if(!rows.optJSONObject(i).optBoolean("created")){next=i;break;}if(next<0){SavedFileActions.toast(this,"已达到 8 个环境");return;}new Wizard(next,rows).show();}
  final class Wizard {
    final int id;final JSONArray windows;final Dialog dialog=new Dialog(WindowHomeActivity.this);LinearLayout body;int step,sourceType;String title;String group="";int sourceSlot;boolean makeDefault;Wizard(int id,JSONArray windows){this.id=id;this.windows=windows;title="环境 "+(id+1);sourceSlot=AppSettings.defaultSlot(WindowHomeActivity.this);}
    void show(){LinearLayout screen=DesignUi.screen(WindowHomeActivity.this);body=DesignUi.body(WindowHomeActivity.this,screen,"创建环境",()->dialog.dismiss());dialog.setContentView(screen);dialog.show();dialog.getWindow().setBackgroundDrawableResource(android.R.color.transparent);dialog.getWindow().setLayout(-1,-1);render();}
    void render(){body.removeAllViews();body.addView(DesignUi.tabs(WindowHomeActivity.this,new String[]{"基本信息","网络来源","确认创建"},step,n->{if(n<step){step=n;render();}}));if(step==0){EditText name=DesignUi.input(body,"环境名称",title,"例如：工作号、研究专用");name.addTextChangedListener(new TextWatcher(){public void beforeTextChanged(CharSequence s,int a,int c,int f){}public void onTextChanged(CharSequence s,int a,int b,int c){title=s.toString();}public void afterTextChanged(Editable e){}});EditText groupInput=DesignUi.input(body,"分组（可选）",group,"最多 12 字，留空为未分组");groupInput.setFilters(new InputFilter[]{new InputFilter.LengthFilter(12)});groupInput.addTextChangedListener(new TextWatcher(){public void beforeTextChanged(CharSequence s,int a,int c,int f){}public void onTextChanged(CharSequence s,int a,int b,int c){group=s.toString().trim();}public void afterTextChanged(Editable e){}});DesignUi.field(body,"选择平台","ChatGPT · chatgpt.com");DesignUi.note(body,"当前支持 ChatGPT，创建后需单独登录。");DesignUi.action(body,"下一步：配置来源 →",true,()->{if(title.trim().isEmpty()||title.trim().length()>24){name.setError("名称需要 1–24 字");return;}title=title.trim();step=1;render();});}
      if(step==1){String[] choices={"复制默认环境网络","复制指定环境网络","创建后手动配置"};for(int i=0;i<3;i++){final int n=i;LinearLayout card=DesignUi.card(WindowHomeActivity.this);RadioButton radio=new RadioButton(WindowHomeActivity.this);radio.setText(choices[i]);radio.setTextColor(DesignUi.TEXT);radio.setChecked(sourceType==i);card.addView(radio);card.addView(DesignUi.text(WindowHomeActivity.this,i==0?"复制默认环境的网络配置":i==1?"选择一个环境，只复制网络设置":"新环境内手动设置网络",12,DesignUi.MUTED));radio.setOnClickListener(v->{sourceType=n;render();});DesignUi.addCard(body,card);}if(sourceType==1){String[] names=new String[windows.length()];java.util.List<Integer> ids=new ArrayList<>();java.util.List<String> labels=new ArrayList<>();for(int i=0;i<windows.length();i++)if(windows.optJSONObject(i).optBoolean("created")){ids.add(i);labels.add(windows.optJSONObject(i).optString("name"));}Spinner spinner=new Spinner(WindowHomeActivity.this);spinner.setAdapter(new ArrayAdapter<>(WindowHomeActivity.this,android.R.layout.simple_spinner_dropdown_item,labels));int selected=ids.indexOf(sourceSlot);spinner.setSelection(selected>=0?selected:0);spinner.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener(){public void onItemSelected(android.widget.AdapterView<?> p,View v,int pos,long item){sourceSlot=ids.get(pos);}public void onNothingSelected(android.widget.AdapterView<?> p){}});body.addView(spinner);}DesignUi.note(body,"登录、Cookie、聊天、草稿和环境自检基线分别保存。这里的复制只涉及网络配置。");DesignUi.action(body,"下一步：确认创建 →",true,()->{step=2;render();});}
      if(step==2){DesignUi.field(body,"环境名称",title);DesignUi.field(body,"平台","ChatGPT");DesignUi.field(body,"分组",group.isEmpty()?"未分组":group);DesignUi.field(body,"网络来源",sourceType==2?"自定义配置":Profiles.display(WindowHomeActivity.this,sourceType==0?AppSettings.defaultSlot(WindowHomeActivity.this):sourceSlot));CheckBox selected=new CheckBox(WindowHomeActivity.this);selected.setText("设为默认环境");selected.setChecked(makeDefault);selected.setOnCheckedChangeListener((b,c)->makeDefault=c);body.addView(selected);DesignUi.action(body,"创建并打开",true,()->create());}}
    void create(){if(preparing)return;preparing=true;Context source=Profiles.context(WindowHomeActivity.this,sourceType==0?AppSettings.defaultSlot(WindowHomeActivity.this):sourceSlot);boolean clone=sourceType!=2;dialog.dismiss();new Thread(()->{String error="";try{Profiles.prepare(source,id,clone);Profiles.rename(source,id,title);ProfileCatalog.get(source).details(id,group,"");if(makeDefault)AppSettings.defaultSlot(source,id);}catch(Exception e){error="环境准备失败，请重试";}String failure=error;handler.post(()->{preparing=false;if(isFinishing()||isDestroyed())return;lastSignature="";refresh();if(failure.isEmpty())openWindow(id,sourceType==2?"network":"chat");else SavedFileActions.toast(WindowHomeActivity.this,failure);});},"window-create").start();}
  }
}
