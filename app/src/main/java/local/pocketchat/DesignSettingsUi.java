package local.pocketchat;

import android.app.*;
import android.widget.*;
import org.json.*;
import java.util.*;

/** App-wide settings live here; profile options belong to the environment editor. */
final class DesignSettingsUi {
  static void render(MainActivity a,LinearLayout box,int selected){render(a,box,()->a.hub.settings());}
  static void render(Activity a,LinearLayout box,Runnable refresh){

    DesignUi.section(box,"启动与界面","");
    LinearLayout appearance=DesignUi.group(a);box.addView(appearance);
    int defaultSlot=AppSettings.defaultSlot(a);
    group(a,appearance,"默认环境与启动入口","默认："+(defaultSlot<0?"暂不可用":Profiles.display(a,defaultSlot)),"window",()->defaultEntry(a,refresh));
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
  static void about(Activity a){DesignUi.message(a,"元婴期院士 · "+AppVersion.name(a),"Android ChatGPT 网页客户端\n\n使用 Mozilla GeckoView 打开 ChatGPT 官方网页。消息、模型选择和输入框沿用网站本身。\n\n在环境列表新建或编辑环境，各环境分别保存登录和网络配置。下载中心汇总已保存的文件。\n\n后台完成提醒默认关闭，可在应用设置中开启。登录数据保存在本机，网络凭据由 Android Keystore 加密。第三方许可随源码提供。\n\n浏览器保护范围以实际自检为准。");}
  static void capabilities(Activity a){DesignUi.message(a,"功能支持范围","• GeckoView 浏览器与 ChatGPT 官方网页\n• 最多 8 个独立环境，支持分组、备注、收藏和删除\n• 每个环境分别保存登录、Cookie、草稿和网络配置\n• 手机网络、订阅入口与固定出口\n• 文件下载和后台回复检测\n\n后台完成提醒需主动开启。浏览器保护范围以自检结果为准。Chrome 扩展尚不支持。\n\n"+NativeCapabilityManifest.officialGecko().unsupportedSummary()+"\n多环境同时运行容量尚未测量。后台空闲只暂停保留会话的活动；回复、上传、下载和维护任务继续受到保护。");}
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
