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
    try{values.put("name",Profiles.display(a,Profiles.slot(a)));values.put("group",meta.optString("group"));values.put("notes",meta.optString("notes"));values.put("desktopSite",meta.optBoolean("desktopSite"));values.put("privacyLevel",a.session.privacy.level());JSONObject desired=DeferredBrowserSettings.desired(a.session);values.put("privacyLevel",desired.optInt("privacyLevel"));values.put("desktopSite",desired.optBoolean("desktopSite"));}catch(Exception ignored){}
    return values;
  }
  static void returnToList(MainActivity a){if(a.getIntent().getBooleanExtra("returnToEnvironmentList",false)){a.getIntent().removeExtra("returnToEnvironmentList");a.startActivity(new android.content.Intent(a,WindowHomeActivity.class).addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK|android.content.Intent.FLAG_ACTIVITY_REORDER_TO_FRONT));}}
  static void show(MainActivity a){editTab(a,BASIC);}
  static void editTab(MainActivity a,int tab){
    JSONObject draft=J.parse(ProfileCatalog.get(a).item(Profiles.slot(a)).optString("draft"));
    if(draft.length()>0)new AlertDialog.Builder(a).setTitle("有未应用的环境草稿").setMessage("继续编辑可恢复上次填写的内容；草稿不会改变运行中的环境。")
      .setPositiveButton("继续草稿",(d,w)->edit(a,draft,tab)).setNeutralButton("编辑已保存配置",(d,w)->edit(a,current(a),tab)).setNegativeButton("取消",(d,w)->returnToList(a)).setOnCancelListener(d->returnToList(a)).show();
    else edit(a,current(a),tab);
  }
  static void edit(MainActivity a,JSONObject value){edit(a,value,BASIC);}
  static void edit(MainActivity a,JSONObject initial,int tab){
    // Old drafts may lack newly introduced metadata; inherit its current value.
    JSONObject existing=current(a);final Runnable[] exit={null};final boolean[] saving={false};final Dialog dialog=new Dialog(a){@Override public void onBackPressed(){if(exit[0]!=null)exit[0].run();else super.onBackPressed();}};
    LinearLayout root=DesignUi.screen(a),outer=DesignUi.body(a,root,"编辑 · "+Profiles.display(a,Profiles.slot(a)),()->{if(exit[0]!=null)exit[0].run();});
    LinearLayout tabs=DesignUi.row(a);outer.addView(tabs);
    LinearLayout basic=DesignUi.column(a),network=DesignUi.column(a),browser=DesignUi.column(a),preferences=DesignUi.column(a);
    FrameLayoutHost host=new FrameLayoutHost(a,basic,network,browser,preferences);outer.addView(host);

    LinearLayout info=DesignUi.card(a);
    EditText name=DesignUi.input(info,"环境名称",initial.optString("name",existing.optString("name")),"例如：工作账号");name.setFilters(new InputFilter[]{new InputFilter.LengthFilter(24)});
    EditText group=DesignUi.input(info,"分组",initial.optString("group",existing.optString("group")),"例如：工作、个人；留空为未分组");group.setFilters(new InputFilter[]{new InputFilter.LengthFilter(12)});
    EditText notes=DesignUi.input(info,"备注",initial.optString("notes",existing.optString("notes")),"用途说明，最多 120 字");notes.setFilters(new InputFilter[]{new InputFilter.LengthFilter(120)});notes.setSingleLine(false);notes.setMaxLines(4);notes.setGravity(android.view.Gravity.TOP);notes.setPadding(a.dp(10),a.dp(10),a.dp(10),a.dp(10));notes.getLayoutParams().height=a.dp(96);
    DesignUi.addCard(basic,info);

    LinearLayout net=DesignUi.card(a);DesignUi.field(net,"网络方式",DesignNetworkUi.mode(a));
    DesignUi.field(net,"连接状态",a.session.offline?"手机离线":a.session.networkReady?"已连接":"待连接");
    DesignUi.addCard(network,net);

    LinearLayout display=DesignUi.card(a);Spinner displayChoice=BrowserDisplayUi.add(display,initial.optBoolean("desktopSite",existing.optBoolean("desktopSite")));
    DesignUi.note(display,"电脑版按手机宽度排版，可双指缩放。回复期间可保存，结束后自动应用。");DesignUi.addCard(browser,display);
    DesignUi.section(browser,"隐私保护","");
    LinearLayout protection=DesignUi.card(a);Spinner privacy=new Spinner(a);
    privacy.setAdapter(new ArrayAdapter<>(a,android.R.layout.simple_spinner_dropdown_item,new String[]{"兼容","标准","强化"}));
    privacy.setSelection(Math.max(0,Math.min(2,initial.optInt("privacyLevel",a.session.privacy.level()))));protection.addView(privacy);
    DesignUi.note(protection,"强化保护可能影响验证和音视频。");
    DesignUi.action(protection,"保护详情",false,()->DesignUi.message(a,"隐私保护",a.session.privacy.summary()));DesignUi.addCard(browser,protection);
    DesignUi.action(browser,"浏览器内核",false,()->BrowserEngineUi.show(a));
    DesignUi.action(browser,"查看环境自检",false,()->EnvironmentAuditUi.show(a));
    DesignUi.addCard(browser,DesignUi.setting(a,"settings","浏览器信息",(GeckoWebView.active(a.remote)?GeckoWebView.VERSION:EnvironmentAudit.packageVersion()),"",()->{
      android.util.DisplayMetrics metrics=a.getResources().getDisplayMetrics();
      DesignUi.message(a,"浏览器信息","内核："+(GeckoWebView.active(a.remote)?GeckoWebView.VERSION:EnvironmentAudit.packageVersion())+"\n网页显示："+BrowserDisplay.label(a.session.privacy.desktop)+"\n系统：Android "+Build.VERSION.RELEASE+" / API "+Build.VERSION.SDK_INT+"\n屏幕："+metrics.widthPixels+" × "+metrics.heightPixels+"\n语言："+Locale.getDefault().toLanguageTag()+"\n时区："+TimeZone.getDefault().getID()+"\n定位：不向网页授权\n\nUser-Agent\n"+a.remote.getSettings().getUserAgentString()+"\n\n网页显示方式支持手机版 / 电脑版；自定义 UA、语言、时区和指纹参数尚未开放。");
    }));

    CheckBox[] options=new CheckBox[AppPrefs.KEYS.length];
    String[] headings={"会话与恢复","后台与通知","下载与存储"};int[][] ranges={{0,3},{3,7},{7,9}};
    for(int section=0;section<ranges.length;section++){
      DesignUi.section(preferences,headings[section],"");LinearLayout card=DesignUi.card(a);
      for(int i=ranges[section][0];i<ranges[section][1];i++){
        options[i]=new CheckBox(a);options[i].setText(AppPrefs.LABELS[i]);options[i].setTextColor(DesignUi.TEXT);options[i].setTextSize(14);
        options[i].setChecked(initial.has(AppPrefs.KEYS[i])?initial.optBoolean(AppPrefs.KEYS[i]):AppPrefs.enabled(a,AppPrefs.KEYS[i]));card.addView(options[i]);
      }DesignUi.addCard(preferences,card);
    }
    DesignUi.action(preferences,"下载位置与存储",false,()->storage(a));

    java.util.function.Supplier<JSONObject> read=()->{
      JSONObject value=J.obj("name",name.getText().toString().trim(),"group",group.getText().toString().trim(),"notes",notes.getText().toString().trim(),"desktopSite",displayChoice.getSelectedItemPosition()==1,"privacyLevel",privacy.getSelectedItemPosition());
      for(int i=0;i<options.length;i++)try{value.put(AppPrefs.KEYS[i],options[i].isChecked());}catch(Exception ignored){}return value;
    };
    final JSONObject baseline=read.get();
    exit[0]=()->{
      if(saving[0]){a.status("正在保存环境，请稍候");return;}
      JSONObject value=read.get();boolean dirty=false;java.util.Iterator<String> keys=value.keys();while(keys.hasNext()){String key=keys.next();if(!java.util.Objects.equals(value.opt(key),baseline.opt(key))){dirty=true;break;}}
      if(!dirty){dialog.dismiss();return;}
      AlertDialog prompt=new AlertDialog.Builder(a).setTitle("退出前保留修改？").setMessage("草稿只保存填写内容，不改变运行中的环境。")
        .setPositiveButton("存草稿并退出",(d,w)->{ProfileCatalog.get(a).draft(Profiles.slot(a),value);dialog.dismiss();})
        .setNeutralButton("放弃本次修改",(d,w)->dialog.dismiss()).setNegativeButton("继续编辑",null).show();
      prompt.getButton(AlertDialog.BUTTON_NEUTRAL).setTextColor(DesignUi.RED);
    };
    DesignUi.action(net,"配置网络 →",true,()->{
      a.getIntent().removeExtra("returnToEnvironmentList");ProfileCatalog.get(a).draft(Profiles.slot(a),read.get());dialog.dismiss();a.status("编辑内容已保存为草稿");a.hub.select(4);
    });
    updateTabs(a,tabs,host,tab);
    TextView validation=DesignUi.text(a,"",13,DesignUi.RED);validation.setPadding(a.dp(14),a.dp(8),a.dp(14),0);validation.setVisibility(android.view.View.GONE);validation.setAccessibilityLiveRegion(android.view.View.ACCESSIBILITY_LIVE_REGION_POLITE);root.addView(validation);
    LinearLayout actions=DesignUi.row(a);actions.setPadding(a.dp(12),a.dp(10),a.dp(12),a.dp(10));
    boolean largeText=a.getResources().getConfiguration().fontScale>=1.4f;
    LinearLayout secondary=largeText?DesignUi.row(a):actions;
    if(largeText){actions.setOrientation(LinearLayout.VERTICAL);actions.addView(secondary,new LinearLayout.LayoutParams(-1,-2));}
    int actionIndex=0;
    for(Button button:new Button[]{DesignUi.button(a,"取消",false,()->exit[0].run()),DesignUi.button(a,"存草稿",false,()->{ProfileCatalog.get(a).draft(Profiles.slot(a),read.get());dialog.dismiss();a.status("环境草稿已保存，尚未应用");}),DesignUi.button(a,"保存环境",true,()->{
      if(saving[0])return;saving[0]=true;editingEnabled(root,false);validation.setText("正在保存…");validation.setTextColor(DesignUi.MUTED);validation.setVisibility(android.view.View.VISIBLE);
      JSONObject value=read.get();applySafely(a,value,name,ok->{saving[0]=false;if(a.isDestroyed())return;if(ok){dialog.dismiss();return;}
        editingEnabled(root,true);
        if(value.optString("name").isEmpty()){updateTabs(a,tabs,host,BASIC);name.requestFocus();validation.setText("先给环境填写一个名称，再保存。");}
        else{if(value.optInt("privacyLevel")!=a.session.privacy.level()||value.optBoolean("desktopSite")!=a.session.privacy.wantsDesktop())updateTabs(a,tabs,host,BROWSER);validation.setText(a.lastUiStatus);}
        validation.setTextColor(DesignUi.RED);validation.setVisibility(android.view.View.VISIBLE);
      });
    })}){
      boolean primaryRow=largeText&&actionIndex==2;
      LinearLayout.LayoutParams p=primaryRow?new LinearLayout.LayoutParams(-1,a.dp(48)):new LinearLayout.LayoutParams(0,a.dp(48),1);
      p.setMargins(a.dp(3),primaryRow?a.dp(8):0,a.dp(3),0);(primaryRow?actions:secondary).addView(button,p);actionIndex++;
    }
    root.addView(actions);dialog.setOnDismissListener(d->returnToList(a));dialog.setCanceledOnTouchOutside(false);dialog.setContentView(root);dialog.show();dialog.getWindow().setBackgroundDrawableResource(android.R.color.transparent);dialog.getWindow().setLayout(-1,-1);dialog.getWindow().setSoftInputMode(android.view.WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);
  }
  static void updateTabs(MainActivity a,LinearLayout tabs,FrameLayoutHost host,int selected){int n=Math.max(0,Math.min(SECTIONS.length-1,selected));host.page(n);tabs.removeAllViews();tabs.addView(DesignUi.tabs(a,SECTIONS,n,i->updateTabs(a,tabs,host,i)),new LinearLayout.LayoutParams(-1,-2));}
  static boolean apply(MainActivity a,JSONObject value,EditText name){
    String title=value.optString("name").trim();if(title.isEmpty()||title.length()>24){name.setError("请输入 1–24 字名称");return false;}
    if(value.optString("group").length()>12||value.optString("notes").length()>120){a.status("分组最多 12 字，备注最多 120 字");return false;}
    ChatSession s=a.session;int level=value.optInt("privacyLevel",s.privacy.level());if(level<0||level>2){a.status("请选择有效的保护等级");return false;}boolean change=level!=s.privacy.level();
    boolean displayChange=value.optBoolean("desktopSite",s.privacy.wantsDesktop())!=s.privacy.wantsDesktop();
    boolean deferred=(change||displayChange)&&browserBusy(s);

    if(change&&level>0&&!GeckoWebView.active(s.web)&&(!s.privacy.earlySupported()||!s.guard.workerProtection)){a.status("请更新 Android System WebView，设置未应用");return false;}
    if(deferred&&!DeferredBrowserSettings.save(s,level,value.optBoolean("desktopSite"))){a.status("设置暂时无法保存，请重试");return false;}Profiles.rename(a,Profiles.slot(a),title);ProfileCatalog.get(a).details(Profiles.slot(a),value.optString("group"),value.optString("notes"));if(!deferred){DeferredBrowserSettings.cancel(s);ProfileCatalog.get(a).browserDisplay(Profiles.slot(a),value.optBoolean("desktopSite",s.privacy.wantsDesktop()));s.prefs.edit().putInt("privacyLevel",level).commit();}AppPrefs.apply(a,value);ProfileCatalog.get(a).draft(Profiles.slot(a),null);
    if(!AppPrefs.enabled(a,"backgroundWait"))ChatService.end(a);if(!deferred&&(change||displayChange))s.applyBrowserSettings(change);
    s.audit.refresh(true);ProfileCatalog.get(a).heartbeat(s,true);if(a.hub!=null)a.hub.refresh();if(a.designChrome!=null)a.designChrome.update();a.status(deferred?"环境已保存，当前回复结束后自动应用网页设置":displayChange&&!s.networkReady?"环境配置已保存，加载网页时应用显示方式":"环境配置已保存");return true;
  }
  static String browserTaskReason(ChatSession s){return BrowserSettingsPolicy.reason(s.pending!=null,s.submitting,s.operation,s.transferActive,s.uploading(),false);}
  static boolean browserBusy(ChatSession s){boolean reply=BrowserSettingsPolicy.currentReply(MainActivity.chatUrl(s.web.getUrl()),WebReplyObserver.same(s.web.getUrl(),s.state.optString("url")),s.state.optBoolean("busy"),s.stateEpoch,s.navigationEpoch);return BrowserDisplay.busy(ProfileUi.working(s),s.navigating,s.connecting,s.recoveryScheduled,reply);}
  static void editingEnabled(android.view.View view,boolean enabled){view.setEnabled(enabled);if(view instanceof android.view.ViewGroup){android.view.ViewGroup group=(android.view.ViewGroup)view;for(int i=0;i<group.getChildCount();i++)editingEnabled(group.getChildAt(i),enabled);}}
  static void applySafely(MainActivity a,JSONObject value,EditText name,java.util.function.Consumer<Boolean> done){
    ChatSession s=a.session;boolean browserChange=value.optInt("privacyLevel",s.privacy.level())!=s.privacy.level()||value.optBoolean("desktopSite",s.privacy.wantsDesktop())!=s.privacy.wantsDesktop();
    if(value.optString("name").trim().isEmpty()||value.optString("name").trim().length()>24||!browserChange||!MainActivity.chatUrl(s.web.getUrl())||ProfileUi.working(s)){done.accept(apply(a,value,name));return;}
    final String url=s.web.getUrl(),scope=s.pageMemory.scope();final long epoch=s.navigationEpoch;
    s.operation=true;s.configurationCapture=true;s.changed();a.status("正在保留网页草稿…");
    java.util.function.Consumer<String> fail=message->{DeferredBrowserSettings.release(s);s.changed();a.status(message);done.accept(false);};
    // Inspect uses the existing read-only driver and detects oversized drafts before
    // page-state's bounded snapshot could omit them.
    s.asyncDriver("inspect",J.obj("expectedUrl",url),2500,inspected->{
      if(!WebReplyObserver.same(url,inspected.optString("url"))||epoch!=s.navigationEpoch||!scope.equals(s.pageMemory.scope())){
        fail.accept("网页状态已改变，请稍后重试；环境设置尚未应用");return;
      }
      s.state=inspected;s.stateEpoch=epoch;if(inspected.optBoolean("busy")){DeferredBrowserSettings.release(s);done.accept(apply(a,value,name));return;}
      if(inspected.optString("draft").length()>300000||inspected.optString("draftRaw").length()>300000){fail.accept("网页草稿过长，请先保存或发送，再切换显示方式");return;}
      s.asyncDriver("page-state",J.obj("expectedUrl",url),2500,state->{
        if(!state.optBoolean("ok")||epoch!=s.navigationEpoch||!WebReplyObserver.same(url,s.web.getUrl())||!scope.equals(s.pageMemory.scope())||!state.optString("draft").equals(inspected.optString("draft"))){
          fail.accept("网页草稿暂时无法保留，请稍后重试；环境设置尚未应用");return;
        }
        s.pageMemory.remember(scope,url,state);String draft=state.optString("draft");
        try{s.webStore.worker.execute(()->{
          boolean stored=false;try{stored=draft.isEmpty()||DraftArchive.get(s.context).save(url,draft,"切换网页显示前的草稿");}catch(RuntimeException ignored){}final boolean saved=stored;
          s.handler.post(()->{
            DeferredBrowserSettings.release(s);s.changed();if(a.isDestroyed()||a.isFinishing()){done.accept(false);return;}
            if(!saved||epoch!=s.navigationEpoch||!WebReplyObserver.same(url,s.web.getUrl())||!scope.equals(s.pageMemory.scope())){a.status("草稿保留未完成或网页已改变，环境设置尚未应用");done.accept(false);return;}
            done.accept(apply(a,value,name));
          });
        });}catch(RuntimeException ignored){fail.accept("草稿暂时无法保存，请稍后重试；环境设置尚未应用");}
      });
    });
  }
  static void storage(MainActivity a){
    JSONObject scan=AppPrefs.temporaryCache(a,System.currentTimeMillis(),false);
    new AlertDialog.Builder(a).setTitle("数据与存储 · "+Profiles.display(a,Profiles.slot(a))).setMessage("下载位置："+DefaultDownloads.description(a)+"\n\n可清理旧临时文件："+scan.optInt("count")+" 个 / "+NetworkMetricsUi.amount(scan.optLong("bytes"))+"\n任务引用的中间文件："+scan.optInt("protected")+" 个\n\n清理仅处理超过 30 天且未被任务引用的中间文件。聊天、草稿、登录与已保存文件保留。").setPositiveButton("清理旧临时文件",(d,w)->{JSONObject result=AppPrefs.temporaryCache(a,System.currentTimeMillis(),true);a.status("已清理 "+result.optInt("removed")+" 个旧临时文件");}).setNegativeButton("关闭",null).show();
  }
  static final class FrameLayoutHost extends android.widget.FrameLayout {
    final LinearLayout[] pages;FrameLayoutHost(MainActivity a,LinearLayout... views){super(a);pages=views;for(LinearLayout v:views)addView(v);}
    void page(int n){for(int i=0;i<pages.length;i++)pages[i].setVisibility(i==n?android.view.View.VISIBLE:android.view.View.GONE);}
  }
}
