package local.pocketchat;

import android.app.*;
import android.os.Build;
import android.text.*;
import android.widget.*;
import org.json.*;
import java.util.*;

/** One editor owns profile identity, browser policy and preferences. Network connects separately. */
final class EnvironmentEditorUi {
  static final int BASIC=0, NETWORK=1, BROWSER=2, PREFERENCES=3;
  static final String[] SECTIONS={"基本信息","网络配置","浏览器","使用偏好"};

  static JSONObject current(MainActivity a){
    JSONObject values=AppPrefs.values(a),meta=ProfileCatalog.get(a).item(Profiles.slot(a));
    try{values.put("name",Profiles.display(a,Profiles.slot(a)));values.put("group",meta.optString("group"));values.put("notes",meta.optString("notes"));values.put("privacyLevel",a.session.privacy.level());}catch(Exception ignored){}
    return values;
  }
  static void show(MainActivity a){editTab(a,BASIC);}
  static void editTab(MainActivity a,int tab){
    JSONObject draft=J.parse(ProfileCatalog.get(a).item(Profiles.slot(a)).optString("draft"));
    if(draft.length()>0)new AlertDialog.Builder(a).setTitle("有未应用的环境草稿").setMessage("继续编辑可恢复上次填写的内容；草稿不会改变运行中的环境。")
      .setPositiveButton("继续草稿",(d,w)->edit(a,draft,tab)).setNeutralButton("编辑已保存配置",(d,w)->edit(a,current(a),tab)).setNegativeButton("取消",null).show();
    else edit(a,current(a),tab);
  }
  static void edit(MainActivity a,JSONObject value){edit(a,value,BASIC);}
  static void edit(MainActivity a,JSONObject initial,int tab){
    // Old drafts may lack newly introduced metadata; inherit its current value.
    JSONObject existing=current(a);final Runnable[] exit={null};final Dialog dialog=new Dialog(a){@Override public void onBackPressed(){if(exit[0]!=null)exit[0].run();else super.onBackPressed();}};
    LinearLayout root=DesignUi.screen(a),outer=DesignUi.body(a,root,"编辑环境",()->{if(exit[0]!=null)exit[0].run();});
    DesignUi.note(outer,"环境 "+String.format(Locale.ROOT,"%02d",Profiles.slot(a)+1)+" · "+Profiles.display(a,Profiles.slot(a)));
    LinearLayout tabs=DesignUi.row(a);outer.addView(tabs);
    LinearLayout basic=DesignUi.column(a),network=DesignUi.column(a),browser=DesignUi.column(a),preferences=DesignUi.column(a);
    FrameLayoutHost host=new FrameLayoutHost(a,basic,network,browser,preferences);outer.addView(host);

    DesignUi.section(basic,"环境资料","名称、分组和备注用于整理环境，不包含账号密码。");
    LinearLayout info=DesignUi.card(a);
    EditText name=DesignUi.input(info,"环境名称",initial.optString("name",existing.optString("name")),"例如：工作账号");name.setFilters(new InputFilter[]{new InputFilter.LengthFilter(24)});
    EditText group=DesignUi.input(info,"分组",initial.optString("group",existing.optString("group")),"例如：工作、个人；留空为未分组");group.setFilters(new InputFilter[]{new InputFilter.LengthFilter(12)});
    EditText notes=DesignUi.input(info,"备注",initial.optString("notes",existing.optString("notes")),"用途说明，最多 120 字");notes.setFilters(new InputFilter[]{new InputFilter.LengthFilter(120)});
    DesignUi.field(info,"平台","ChatGPT · chatgpt.com");DesignUi.addCard(basic,info);
    DesignUi.section(basic,"环境隔离","每个环境分别保存登录、Cookie、聊天、草稿和网络配置。最多 8 个环境。");
    DesignUi.note(basic,"平台版本和设备信息可在浏览器页核对。");

    DesignUi.section(network,"连接配置","网络参数通过独立表单保存并连接。这里显示当前已生效的配置。");
    LinearLayout net=DesignUi.card(a);DesignUi.field(net,"网络方式",DesignNetworkUi.mode(a));
    DesignUi.field(net,"连接状态",a.session.offline?"手机离线":a.session.networkReady?"已连接":"待连接");
    DesignUi.note(net,"前往网络配置时，未应用的编辑内容会保存为草稿。");DesignUi.addCard(network,net);

    DesignUi.section(browser,"隐私保护","使用 Android System WebView 的实际浏览器环境。");
    LinearLayout protection=DesignUi.card(a);Spinner privacy=new Spinner(a);
    privacy.setAdapter(new ArrayAdapter<>(a,android.R.layout.simple_spinner_dropdown_item,new String[]{"兼容 · 保留系统行为","标准 · 限制部分设备读取","强化 · 增加 Canvas / 音频限制"}));
    privacy.setSelection(Math.max(0,Math.min(2,initial.optInt("privacyLevel",a.session.privacy.level()))));protection.addView(privacy);
    DesignUi.note(protection,"标准保护需要支持加载前脚本的 WebView。强化可能影响图片、音频和验证。调整后保存会重新加载连接。");
    DesignUi.field(protection,"加载前保护",a.session.privacy.earlyInstalled?"已安装":"未安装，以自检结果为准");DesignUi.action(protection,"查看保护详情",false,()->DesignUi.message(a,"当前保护详情",a.session.privacy.summary()));DesignUi.addCard(browser,protection);
    DesignUi.action(browser,"查看环境自检",false,()->EnvironmentAuditUi.show(a));
    DesignUi.section(browser,"实际设备信息","以下信息来自当前设备，供核对；独立 UA、语言、时区和指纹参数尚未开放。");
    LinearLayout identity=DesignUi.card(a);DesignUi.field(identity,"内核版本",EnvironmentAudit.packageVersion());
    DesignUi.field(identity,"User-Agent",a.remote.getSettings().getUserAgentString());
    android.util.DisplayMetrics metrics=a.getResources().getDisplayMetrics();DesignUi.field(identity,"屏幕",metrics.widthPixels+" × "+metrics.heightPixels);
    DesignUi.field(identity,"系统","Android "+Build.VERSION.RELEASE+" / API "+Build.VERSION.SDK_INT);
    DesignUi.field(identity,"语言 / 时区",Locale.getDefault().toLanguageTag()+" / "+TimeZone.getDefault().getID());
    DesignUi.field(identity,"定位权限","不向网页授权");DesignUi.addCard(browser,identity);

    CheckBox[] options=new CheckBox[AppPrefs.KEYS.length];
    String[] headings={"会话与恢复","后台与通知","下载与存储"};int[][] ranges={{0,3},{3,7},{7,9}};
    for(int section=0;section<ranges.length;section++){
      DesignUi.section(preferences,headings[section],"");LinearLayout card=DesignUi.card(a);
      for(int i=ranges[section][0];i<ranges[section][1];i++){
        options[i]=new CheckBox(a);options[i].setText(AppPrefs.LABELS[i]);options[i].setTextColor(DesignUi.TEXT);options[i].setTextSize(14);
        options[i].setChecked(initial.has(AppPrefs.KEYS[i])?initial.optBoolean(AppPrefs.KEYS[i]):AppPrefs.enabled(a,AppPrefs.KEYS[i]));card.addView(options[i]);
      }DesignUi.addCard(preferences,card);
    }
    DesignUi.note(preferences,"自动历史同步只处理可见列表；后台等待关闭后不撤销提问。自动清理只处理无任务引用的旧中间文件。");
    DesignUi.field(preferences,"该环境下载目录",DefaultDownloads.description(a));
    DesignUi.action(preferences,"数据与临时文件",false,()->storage(a));

    java.util.function.Supplier<JSONObject> read=()->{
      JSONObject value=J.obj("name",name.getText().toString().trim(),"group",group.getText().toString().trim(),"notes",notes.getText().toString().trim(),"privacyLevel",privacy.getSelectedItemPosition());
      for(int i=0;i<options.length;i++)try{value.put(AppPrefs.KEYS[i],options[i].isChecked());}catch(Exception ignored){}return value;
    };
    final JSONObject baseline=read.get();
    exit[0]=()->{
      JSONObject value=read.get();boolean dirty=false;java.util.Iterator<String> keys=value.keys();while(keys.hasNext()){String key=keys.next();if(!java.util.Objects.equals(value.opt(key),baseline.opt(key))){dirty=true;break;}}
      if(!dirty){dialog.dismiss();return;}
      new AlertDialog.Builder(a).setTitle("保存未应用的修改？").setMessage("草稿只保存填写内容，不改变运行中的环境。")
        .setPositiveButton("存草稿并退出",(d,w)->{ProfileCatalog.get(a).draft(Profiles.slot(a),value);dialog.dismiss();})
        .setNeutralButton("放弃本次修改",(d,w)->dialog.dismiss()).setNegativeButton("继续编辑",null).show();
    };
    DesignUi.action(net,"配置网络 →",true,()->{
      ProfileCatalog.get(a).draft(Profiles.slot(a),read.get());dialog.dismiss();a.status("编辑内容已保存为草稿");a.hub.select(4);
    });
    updateTabs(a,tabs,host,tab);
    LinearLayout actions=DesignUi.row(a);actions.setPadding(a.dp(12),a.dp(10),a.dp(12),a.dp(10));
    for(Button button:new Button[]{DesignUi.button(a,"取消",false,()->exit[0].run()),DesignUi.button(a,"存草稿",false,()->{ProfileCatalog.get(a).draft(Profiles.slot(a),read.get());dialog.dismiss();a.status("环境草稿已保存，尚未应用");}),DesignUi.button(a,"保存环境",true,()->{if(apply(a,read.get(),name))dialog.dismiss();})}){
      LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(0,a.dp(48),1);p.setMargins(a.dp(3),0,a.dp(3),0);actions.addView(button,p);
    }
    root.addView(actions);dialog.setContentView(root);dialog.show();dialog.getWindow().setBackgroundDrawableResource(android.R.color.transparent);dialog.getWindow().setLayout(-1,-1);
  }
  static void updateTabs(MainActivity a,LinearLayout tabs,FrameLayoutHost host,int selected){int n=Math.max(0,Math.min(SECTIONS.length-1,selected));host.page(n);tabs.removeAllViews();tabs.addView(DesignUi.tabs(a,SECTIONS,n,i->updateTabs(a,tabs,host,i)),new LinearLayout.LayoutParams(-1,-2));}
  static boolean apply(MainActivity a,JSONObject value,EditText name){
    String title=value.optString("name").trim();if(title.isEmpty()||title.length()>24){name.setError("请输入 1–24 字名称");return false;}
    if(value.optString("group").length()>12||value.optString("notes").length()>120){a.status("分组最多 12 字，备注最多 120 字");return false;}
    ChatSession s=a.session;int level=value.optInt("privacyLevel",s.privacy.level());if(level<0||level>2){a.status("请选择有效的保护等级");return false;}boolean change=level!=s.privacy.level();
    if(change&&ProfileUi.working(s)){a.status("当前有未完成任务，结束后再调整保护等级");return false;}
    if(change&&level>0&&(!s.privacy.earlySupported()||!s.guard.workerProtection)){a.status("请更新 Android System WebView，设置未应用");return false;}
    Profiles.rename(a,Profiles.slot(a),title);ProfileCatalog.get(a).details(Profiles.slot(a),value.optString("group"),value.optString("notes"));AppPrefs.apply(a,value);s.prefs.edit().putInt("privacyLevel",level).commit();ProfileCatalog.get(a).draft(Profiles.slot(a),null);
    if(!AppPrefs.enabled(a,"backgroundWait"))ChatService.end(a);if(change){s.audit.cancel();s.invalidateConnection();s.privacy.apply();s.openConnection(true,true);}
    s.audit.refresh(true);ProfileCatalog.get(a).heartbeat(s,true);if(a.hub!=null)a.hub.refresh();if(a.designChrome!=null)a.designChrome.update();a.status("环境配置已保存");return true;
  }
  static void storage(MainActivity a){
    JSONObject scan=AppPrefs.temporaryCache(a,System.currentTimeMillis(),false);
    new AlertDialog.Builder(a).setTitle("数据与存储 · "+Profiles.display(a,Profiles.slot(a))).setMessage("可清理旧临时文件："+scan.optInt("count")+" 个 / "+NetworkMetricsUi.amount(scan.optLong("bytes"))+"\n任务引用的中间文件："+scan.optInt("protected")+" 个\n\n清理仅处理超过 30 天且未被任务引用的中间文件。聊天、草稿、登录与已保存文件保留。").setPositiveButton("清理旧临时文件",(d,w)->{JSONObject result=AppPrefs.temporaryCache(a,System.currentTimeMillis(),true);a.status("已清理 "+result.optInt("removed")+" 个旧临时文件");}).setNegativeButton("关闭",null).show();
  }
  static final class FrameLayoutHost extends android.widget.FrameLayout {
    final LinearLayout[] pages;FrameLayoutHost(MainActivity a,LinearLayout... views){super(a);pages=views;for(LinearLayout v:views)addView(v);}
    void page(int n){for(int i=0;i<pages.length;i++)pages[i].setVisibility(i==n?android.view.View.VISIBLE:android.view.View.GONE);}
  }
}
