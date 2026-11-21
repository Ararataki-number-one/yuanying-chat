package local.pocketchat;

import android.app.*;
import android.content.Context;
import android.widget.*;
import org.json.*;
import java.util.*;

/** App-wide settings live here; profile options belong to the environment editor. */
final class DesignSettingsUi {
  static void render(MainActivity a,LinearLayout box,int selected){render(a,box,()->a.hub.settings());}
  static void render(Activity a,LinearLayout box,Runnable refresh){
    SettingsWorkspaceStyle.section(box,"启动与外观","全局");
    LinearLayout appearance=SettingsWorkspaceStyle.group(a);box.addView(appearance);
    int defaultSlot=AppSettings.defaultSlot(a);
    group(a,appearance,"默认环境与启动入口","默认："+(defaultSlot<0?"暂不可用":Profiles.display(a,defaultSlot)),"window",()->defaultEntry(a,refresh));
    group(a,appearance,"白天与黑夜",AppAppearance.label()+" · 应用与网页外观","appearance",()->appearance(a,refresh));
    SettingsWorkspaceStyle.section(box,"当前环境","仅当前环境");
    LinearLayout environment=SettingsWorkspaceStyle.group(a);box.addView(environment);
    EnvironmentSpec.Identity target=BrowserSettingsUi.workspaceIdentity(a);
    String browserDetail="环境暂不可用";
    if(target!=null){
      Context profile=Profiles.context(a,target.slot);
      browserDetail=Profiles.display(a,target.slot)+" · "+(BrowserPreferences.startBrowser(profile)?"Chromium 指纹浏览器":"Gecko 指纹浏览器");
    }
    group(a,environment,"此环境的浏览器与启动",browserDetail,"browser",()->BrowserSettingsUi.openWorkspace(a,target,refresh));
    SettingsWorkspaceStyle.section(box,"提醒与后台","全局");
    LinearLayout background=SettingsWorkspaceStyle.group(a);box.addView(background);
    group(a,background,"后台完成提醒",AppSettings.backgroundCompletionNotice(a)?"离开应用后提醒下载完成":"已关闭 · 使用时保持安静","bell",()->completionReminders(a,refresh));
    group(a,background,"通知与电池设置","通知提醒与后台运行权限","battery",()->FeatureDialogs.backgroundSettings(a));
    SettingsWorkspaceStyle.section(box,"配置备份","");
    LinearLayout backup=SettingsWorkspaceStyle.group(a);box.addView(backup);
    group(a,backup,"环境配置备份","密码加密模板与偏好 · 恢复为新环境","backup",()->a.startActivity(new android.content.Intent(a,EnvironmentConfigBackupActivity.class)));
    SettingsWorkspaceStyle.section(box,"帮助与应用","");
    LinearLayout help=SettingsWorkspaceStyle.group(a);box.addView(help);
    group(a,help,"问题与建议","提交反馈 · 查看处理进度","feedback",()->FeedbackUi.open(a));
    if(AppUpdates.enabled(a))group(a,help,"应用更新",AppSettings.get(a,"updateLabel","当前版本 "+AppVersion.name(a)),"download",()->AppUpdates.open(a));
    group(a,help,"关于与使用帮助","版本与使用说明","info",()->about(a));
    group(a,help,"功能支持范围","查看支持的功能","shield",()->capabilities(a));
  }
  static void group(Activity a,LinearLayout box,String title,String detail,String icon,Runnable click){SettingsWorkspaceStyle.row(a,box,title,detail,icon,click);}
  static void about(Activity a){
    if(ChromiumEntry.managed(a)){
      DesignUi.message(a,"元婴期院士 · "+AppVersion.name(a),
          "Gecko 随应用安装，也是新环境的默认浏览器。独立 Chromium 可在环境的浏览器设置中下载安装。"
          +"\n\n环境分别保存内核选择、登录和网络配置。Gecko 在 ChatGPT 网页提供草稿救援和离线会话检索。"
          +"\n\nChromium 由 Cefrium 0.21.0 提供，使用 LGPL-3.0-or-later。上游源码和第三方声明随本版本发布说明提供。");
      return;
    }
    DesignUi.message(a,"元婴期院士 · "+AppVersion.name(a),"Android 双内核指纹浏览器\n\nGecko 与 Chromium 都能输入网址或搜索，默认网站仍为 https://chatgpt.com/。Gecko 在 ChatGPT 网页额外提供草稿救援和离线会话检索。\n\n每个环境分别保存登录、网络和指纹配置；两个内核的 Cookie 与指纹配置独立。Gecko 使用原生隐私模板，Chromium 使用原生 UA / UA-CH 和文档开始时的指纹保护，具体范围可分别查看设置与自检。\n\nChromium 基于 Android System WebView，提供多标签、收藏与历史、页内查找和文件上传下载。可选择每个环境的启动内核和两个内核共用的默认网站。\n\n后台完成提醒默认关闭，可在应用设置中开启。登录数据保存在本机，网络凭据及 Chromium 指纹配置由 Android Keystore 加密。第三方许可随源码提供。");}
  static void capabilities(Activity a){
    if(ChromiumEntry.managed(a)){
      DesignUi.message(a,"功能支持范围",
          "• Gecko：网页浏览、独立登录、原生隐私模板、文件操作和 ChatGPT 草稿救援"
          +"\n• Chromium：网页浏览、独立登录、文件上传下载"
          +"\n• Chromium 线路：系统直连、内置线路、固定代理和强制 VPN。强制 VPN 核验需要 Android 13 或更新版本"
          +"\n• 最多 8 个独立环境，支持分组、备注、收藏和删除");
      return;
    }
    DesignUi.message(a,"功能支持范围","• 两个内核：切换网址、搜索、独立登录、环境指纹配置与自检\n• Gecko：原生隐私模板；在 ChatGPT 网页提供草稿救援与离线会话检索\n• Chromium：原生 UA / UA-CH 设置，页面及框架的 Canvas、WebGL 调试显卡标识、音频复制读出和 WebRTC 构造器保护\n• Chromium 浏览：多标签、收藏与历史、页内查找、手机版／电脑版、文件上传下载\n• 最多 8 个独立环境，支持分组、备注、收藏和删除\n\nChromium 的 Worker、Service Worker、OffscreenCanvas、独立时区、字体、硬件及网络协议指纹未覆盖。Chrome 扩展尚不支持。请在各内核的设置中查看实际支持和确认状态；设置回读不代表完整指纹已验证。\n\nChromium 可按当前 HTTPS 网站的请求逐次授权相机、麦克风和大致位置，不保存网站的长期允许记录。页面 WebRTC 限制不覆盖 Worker；HTTP 代理不能代替设备 VPN。应用不会自动开启 VPN。\n\nGecko 原生模板的范围：\n\n"+NativeCapabilityManifest.officialGecko().unsupportedSummary()+"\n\n后台完成提醒需主动开启。多环境同时运行容量尚未测量。");}
  static void completionReminders(Activity a,Runnable refresh){
    LinearLayout box=DesignUi.column(a);box.setPadding(DesignUi.dp(a,18),0,DesignUi.dp(a,18),DesignUi.dp(a,14));
    Switch enabled=new Switch(a);enabled.setText("离开应用后提醒完成");NativeControls.prepare(enabled);enabled.setChecked(AppSettings.backgroundCompletionNotice(a));box.addView(enabled);
    DesignUi.note(box,"下载完成后可提醒；网页回复状态请直接查看原网页。使用应用时保持安静；系统仍可能显示后台服务的静默提示。");
    enabled.setOnCheckedChangeListener((button,value)->{AppSettings.put(a,"backgroundCompletionNotice",String.valueOf(value));if(value){ChatService.channels(a);if(android.os.Build.VERSION.SDK_INT>=33&&a.checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS)!=android.content.pm.PackageManager.PERMISSION_GRANTED)a.requestPermissions(new String[]{android.Manifest.permission.POST_NOTIFICATIONS},91);}refresh.run();});
    AppAppearance.dialog(a).setTitle("后台完成提醒").setView(box).setPositiveButton("完成",null).show();
  }
  static void defaultEntry(Activity a,Runnable refresh){
    JSONArray rows=ProfileCatalog.get(a).list();
    List<EnvironmentSpec.Identity> choices=new ArrayList<>();List<String> titles=new ArrayList<>();
    int current=AppSettings.defaultSlot(a),selected=0;
    for(int i=0;i<rows.length();i++){
      JSONObject row=rows.optJSONObject(i);
      if(row==null||!AppSettings.selectable(row))continue;
      try{
        EnvironmentSpec.Identity identity=new EnvironmentSpec.Identity(row.optInt("slot"),row.optInt("generation"),row.optString("environmentId"));
        if(identity.slot==current)selected=choices.size();
        choices.add(identity);titles.add(row.optString("name"));
      }catch(IllegalArgumentException unavailable){}
    }
    if(choices.isEmpty()){DesignUi.message(a,"默认环境与启动入口","暂无可用环境，请返回环境管理后重试。");return;}
    LinearLayout box=DesignUi.column(a);box.setPadding(DesignUi.dp(a,18),0,DesignUi.dp(a,18),DesignUi.dp(a,14));
    Spinner spinner=new Spinner(a);spinner.setContentDescription("默认启动环境");
    spinner.setAdapter(DesignUi.spinnerAdapter(a,titles.toArray(new String[0])));spinner.setSelection(selected);
    box.addView(spinner,new LinearLayout.LayoutParams(-1,-2));
    CheckBox direct=new CheckBox(a);direct.setText("启动时直接进入默认环境的原网页");
    direct.setChecked(AppSettings.bool(a,"startupDirect",true));box.addView(direct);
    DesignUi.note(box,"关闭后先进入环境管理。底部“浏览器”会回到正在使用的环境。");
    TextView issue=DesignUi.text(a,"",13,DesignUi.RED);
    issue.setVisibility(android.view.View.GONE);issue.setAccessibilityLiveRegion(android.view.View.ACCESSIBILITY_LIVE_REGION_POLITE);
    box.addView(issue);
    AlertDialog dialog=AppAppearance.dialog(a).setTitle("默认环境与启动入口").setView(box)
      .setPositiveButton("保存",null).setNegativeButton("取消",null).create();
    dialog.show();
    dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{
      int position=spinner.getSelectedItemPosition();
      if(position<0||position>=choices.size())return;
      EnvironmentSpec.Identity identity=choices.get(position);
      boolean saved=false;
      try{saved=AppSettings.saveStartup(a,identity.slot,identity.generation,identity.environmentId,direct.isChecked());}
      catch(RuntimeException unavailable){}
      if(!saved){
        issue.setText("环境已变化或设置暂时无法保存，请重新选择或重试。");
        issue.setVisibility(android.view.View.VISIBLE);return;
      }
      dialog.dismiss();refresh.run();
      if(a instanceof MainActivity&&((MainActivity)a).designChrome!=null)((MainActivity)a).designChrome.update();
    });
  }
  static void appearance(Activity a,Runnable refresh){
    ReferenceUi.Modal d=new ReferenceUi.Modal(a,"白天与黑夜");
    RadioGroup choices=new RadioGroup(a);d.body.addView(choices);
    for(int i=0;i<AppAppearance.MODES.length;i++){
      RadioButton choice=new RadioButton(a);choice.setId(android.view.View.generateViewId());choice.setText(AppAppearance.LABELS[i]);choice.setTag(AppAppearance.MODES[i]);choice.setTextSize(15);choice.setTextColor(DesignUi.TEXT);choice.setMinHeight(DesignUi.dp(a,48));choices.addView(choice);
      if(AppAppearance.mode().equals(AppAppearance.MODES[i]))choices.check(choice.getId());
      choice.setOnClickListener(v->{AppAppearance.choose(a,String.valueOf(choice.getTag()));refresh.run();});
    }
    d.note("跟随手机的浅色或深色设置，系统定时切换时也会自动调整。网页使用 ChatGPT 自带的浅色／深色配色，保留输入，不重新加载。");
    TextView website=ReferenceUi.text(a,"",13,DesignUi.MUTED,false);website.setPadding(0,DesignUi.dp(a,8),0,DesignUi.dp(a,8));d.body.addView(website);
    Runnable status=new Runnable(){public void run(){if(!d.isShowing())return;ChatSession session=ChatSession.peek();JSONObject value=session==null||session.web==null?new JSONObject():session.web.appearanceReport();String state=value.optString("status");
      String message="page-hidden".equals(value.optString("reason"))?"返回会话后会继续确认网页配色。":"confirmed".equals(state)?"聊天区域配色采样与应用一致。":"partial".equals(state)?"聊天区域配色采样一致，但偏好暂未保存；可重新同步。":"failed".equals(state)?"网页配色尚未确认同步，可重新同步并复制检查结果。":"pending".equals(state)?"正在确认网页配色…":"打开 ChatGPT 会话后会自动同步网页配色。";
      if(!message.contentEquals(website.getText()))website.setText(message);website.postDelayed(this,500);}};
    DesignUi.action(d.body,"重新同步网页配色",false,()->AppAppearance.resynchronize(a));
    DesignUi.action(d.body,"复制配色检查结果",false,()->{ChatSession session=ChatSession.peek();JSONObject value=session==null||session.web==null?J.obj("status","unavailable"):session.web.appearanceReport();
      android.content.ClipboardManager clipboard=(android.content.ClipboardManager)a.getSystemService(android.content.Context.CLIPBOARD_SERVICE);if(clipboard!=null)clipboard.setPrimaryClip(android.content.ClipData.newPlainText("网页配色检查",value.toString()));});
    DesignUi.action(d.body,"查看品牌启动页",false,()->{d.dismiss();a.startActivity(new android.content.Intent(a,BrandLaunchActivity.class).putExtra("previewBrand",true));});
    d.buttons("",()->{},"完成",d::dismiss);d.show();website.post(status);
  }
}
