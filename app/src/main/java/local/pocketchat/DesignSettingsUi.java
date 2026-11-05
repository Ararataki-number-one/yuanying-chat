package local.pocketchat;

import android.app.*;
import android.widget.*;
import org.json.*;
import java.util.*;

/** App-wide settings live here; profile options belong to the environment editor. */
final class DesignSettingsUi {
  static void render(MainActivity a,LinearLayout box,int selected){render(a,box,()->a.hub.settings());}
  static void render(Activity a,LinearLayout box,Runnable refresh){
    DesignUi.action(box,"搜索操作",false,()->ActionSearchUi.show(a));
    DesignUi.section(box,"启动与界面","");
    LinearLayout appearance=DesignUi.group(a);box.addView(appearance);
    int defaultSlot=AppSettings.defaultSlot(a);
    group(a,appearance,"默认环境与启动入口","默认："+(defaultSlot<0?"暂不可用":Profiles.display(a,defaultSlot)),"window",()->defaultEntry(a,refresh));
    group(a,appearance,"此环境的浏览器与启动",Profiles.display(a,Profiles.slot(a))+" · "+(BrowserPreferences.startBrowser(a)?"Chromium 指纹浏览器":"Gecko 指纹浏览器"),"window",()->BrowserSettingsUi.show(a,refresh));
    group(a,appearance,"白天与黑夜",AppAppearance.label()+" · 应用与网页外观","brand",()->appearance(a,refresh));
    DesignUi.section(box,"提醒与后台", "");
    LinearLayout background=DesignUi.group(a);box.addView(background);
    group(a,background,"后台回复检测",BackgroundReplySettingsUi.summary(a),"chat",()->BackgroundReplySettingsUi.open(a,refresh));
    group(a,background,"后台完成提醒",AppSettings.backgroundCompletionNotice(a)?"离开应用后提醒回复和下载完成":"已关闭 · 使用时保持安静","chat",()->completionReminders(a,refresh));
    group(a,background,"通知与电池设置","通知提醒与后台运行权限","chat",()->FeatureDialogs.backgroundSettings(a));
    DesignUi.section(box,"配置备份","");
    LinearLayout backup=DesignUi.group(a);box.addView(backup);
    group(a,backup,"环境配置备份","密码加密模板与偏好 · 恢复为新环境","window",()->a.startActivity(new android.content.Intent(a,EnvironmentConfigBackupActivity.class)));
    DesignUi.section(box,"帮助与能力","");
    LinearLayout help=DesignUi.group(a);box.addView(help);
    group(a,help,"问题与建议","提交反馈 · 查看处理进度","chat",()->FeedbackUi.open(a));
    group(a,help,"应用更新",AppSettings.get(a,"updateLabel","当前版本 "+AppVersion.name(a)),"download",()->AppUpdates.open(a));
    group(a,help,"关于与使用帮助","版本与使用说明","info",()->about(a));
    group(a,help,"功能支持范围","查看支持的功能","shield",()->capabilities(a));
  }
  static void group(Activity a,LinearLayout box,String title,String detail,String icon,Runnable click){DesignUi.groupedRow(box,DesignUi.setting(a,icon,title,detail,"",click));}
  static void about(Activity a){DesignUi.message(a,"元婴期院士 · "+AppVersion.name(a),"Android 双内核指纹浏览器\n\nGecko 与 Chromium 都能输入网址或搜索，默认网站仍为 https://chatgpt.com/。Gecko 在 ChatGPT 网页额外提供草稿救援、回复检测和离线会话检索。\n\n每个环境分别保存登录、网络和指纹配置；两个内核的 Cookie 与指纹配置独立。Gecko 使用原生隐私模板，Chromium 使用原生 UA / UA-CH 和文档开始时的指纹保护，具体范围可分别查看设置与自检。\n\nChromium 基于 Android System WebView，提供多标签、收藏与历史、页内查找和文件上传下载。可选择每个环境的启动内核和两个内核共用的默认网站。\n\n后台完成提醒默认关闭，可在应用设置中开启。登录数据保存在本机，网络凭据及 Chromium 指纹配置由 Android Keystore 加密。第三方许可随源码提供。");}
  static void capabilities(Activity a){DesignUi.message(a,"功能支持范围","• 两个内核：切换网址、搜索、独立登录、环境指纹配置与自检\n• Gecko：原生隐私模板；在 ChatGPT 网页提供草稿救援、离线会话检索与回复检测\n• Chromium：原生 UA / UA-CH 设置，页面及框架的 Canvas、WebGL 调试显卡标识、音频复制读出和 WebRTC 构造器保护\n• Chromium 浏览：多标签、收藏与历史、页内查找、手机版／电脑版、文件上传下载\n• 最多 8 个独立环境，支持分组、备注、收藏和删除\n\nChromium 的 Worker、Service Worker、OffscreenCanvas、独立时区、字体、硬件及网络协议指纹未覆盖。Chrome 扩展尚不支持。请在各内核的设置中查看实际支持和确认状态；设置回读不代表完整指纹已验证。\n\nChromium 可按当前 HTTPS 网站的请求逐次授权相机、麦克风和大致位置，不保存网站的长期允许记录。页面 WebRTC 限制不覆盖 Worker；HTTP 代理不能代替设备 VPN。应用不会自动开启 VPN。\n\nGecko 原生模板的范围：\n\n"+NativeCapabilityManifest.officialGecko().unsupportedSummary()+"\n\n后台完成提醒需主动开启。多环境同时运行容量尚未测量。");}
  static void completionReminders(Activity a,Runnable refresh){
    LinearLayout box=DesignUi.column(a);box.setPadding(DesignUi.dp(a,18),0,DesignUi.dp(a,18),DesignUi.dp(a,14));
    Switch enabled=new Switch(a);enabled.setText("离开应用后提醒完成");NativeControls.prepare(enabled);enabled.setChecked(AppSettings.backgroundCompletionNotice(a));box.addView(enabled);
    DesignUi.note(box,"下载完成提醒可独立使用；回复完成提醒还需开启后台回复检测。使用应用时保持安静；系统仍可能显示后台服务的静默提示。");
    enabled.setOnCheckedChangeListener((button,value)->{AppSettings.put(a,"backgroundCompletionNotice",String.valueOf(value));if(value){ChatService.channels(a);if(android.os.Build.VERSION.SDK_INT>=33&&a.checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS)!=android.content.pm.PackageManager.PERMISSION_GRANTED)a.requestPermissions(new String[]{android.Manifest.permission.POST_NOTIFICATIONS},91);}refresh.run();});
    AppAppearance.dialog(a).setTitle("后台完成提醒").setView(box).setPositiveButton("完成",null).show();
  }
  static void defaultEntry(Activity a,Runnable refresh){
    JSONArray rows=ProfileCatalog.get(a).list();List<Integer> ids=new ArrayList<>();List<String> titles=new ArrayList<>();
    for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);if(AppSettings.selectable(row)){ids.add(row.optInt("slot"));titles.add(row.optString("name"));}}
    LinearLayout box=DesignUi.column(a);box.setPadding(DesignUi.dp(a,18),0,DesignUi.dp(a,18),DesignUi.dp(a,14));Spinner spinner=new Spinner(a);spinner.setContentDescription("默认启动环境");
    spinner.setAdapter(DesignUi.spinnerAdapter(a,titles.toArray(new String[0])));spinner.setSelection(Math.max(0,ids.indexOf(AppSettings.defaultSlot(a))));box.addView(spinner,new LinearLayout.LayoutParams(-1,-2));
    CheckBox direct=new CheckBox(a);direct.setText("启动时直接进入默认环境的原网页");direct.setChecked(AppSettings.bool(a,"startupDirect",true));box.addView(direct);
    DesignUi.note(box,"关闭后先进入环境管理。底部“会话”会回到正在使用的环境。");
    AlertDialog dialog=AppAppearance.dialog(a).setTitle("默认环境与启动入口").setView(box).setPositiveButton("保存",(d,w)->{if(spinner.getSelectedItemPosition()<0)return;AppSettings.defaultSlot(a,ids.get(spinner.getSelectedItemPosition()));AppSettings.put(a,"startupDirect",String.valueOf(direct.isChecked()));refresh.run();if(a instanceof MainActivity&&((MainActivity)a).designChrome!=null)((MainActivity)a).designChrome.update();}).setNegativeButton("取消",null).show();
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
