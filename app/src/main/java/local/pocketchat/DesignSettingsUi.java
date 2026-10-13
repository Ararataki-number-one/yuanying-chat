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
    group(a,box,"默认环境与启动入口","默认："+Profiles.display(a,AppSettings.defaultSlot(a)),"window",()->defaultEntry(a,refresh));
    group(a,box,"界面与品牌页","浅色管理界面 · 蓝色重点操作","brand",()->appearance(a));
    DesignUi.section(box,"提醒与后台", "");
    group(a,box,"后台完成提醒",AppSettings.backgroundCompletionNotice(a)?"离开应用后提醒回复和下载完成":"已关闭 · 使用时保持安静","chat",()->completionReminders(a,refresh));
    group(a,box,"通知与电池设置","通知提醒与后台运行权限","chat",()->FeatureDialogs.backgroundSettings(a));
    DesignUi.section(box,"帮助与能力","");
    group(a,box,"应用更新",AppSettings.get(a,"updateLabel","当前版本 "+AppVersion.name(a)),"download",()->AppUpdates.open(a));
    group(a,box,"关于与使用帮助","版本与使用说明","settings",()->about(a));
    group(a,box,"功能支持范围","查看支持的功能","shield",()->capabilities(a));
  }
  static void group(Activity a,LinearLayout box,String title,String detail,String icon,Runnable click){DesignUi.addCard(box,DesignUi.setting(a,icon,title,detail,"",click));}
  static void about(Activity a){DesignUi.message(a,"元婴期院士 · "+AppVersion.name(a),"Android ChatGPT 网页客户端\n\n使用 Mozilla GeckoView 打开 ChatGPT 官方网页。消息、模型选择和输入框沿用网站本身。\n\n在环境列表新建或编辑环境，各环境分别保存登录和网络配置。下载中心汇总已保存的文件。\n\n后台完成提醒默认关闭，可在应用设置中开启。登录数据保存在本机，网络凭据由 Android Keystore 加密。第三方许可随源码提供。\n\n浏览器保护范围以实际自检为准。");}
  static void capabilities(Activity a){DesignUi.message(a,"功能支持范围","• GeckoView 浏览器与 ChatGPT 官方网页\n• 最多 8 个独立环境，支持分组、备注、收藏和删除\n• 每个环境分别保存登录、Cookie、草稿和网络配置\n• 手机网络、订阅入口与固定出口\n• 文件下载和后台回复检测\n\n后台完成提醒需主动开启。浏览器保护范围以自检结果为准。Chrome 扩展尚不支持。\n\n"+NativeCapabilityManifest.officialGecko().unsupportedSummary()+"\n多环境同时运行容量尚未测量。后台空闲只暂停保留会话的活动；回复、上传、下载和维护任务继续受到保护。");}
  static void completionReminders(Activity a,Runnable refresh){
    LinearLayout box=DesignUi.column(a);box.setPadding(DesignUi.dp(a,18),0,DesignUi.dp(a,18),DesignUi.dp(a,14));
    Switch enabled=new Switch(a);enabled.setText("离开应用后提醒完成");enabled.setTextSize(14);enabled.setTextColor(DesignUi.TEXT);enabled.setChecked(AppSettings.backgroundCompletionNotice(a));box.addView(enabled);
    DesignUi.note(box,"回复和文件下载完成后提醒。使用应用时保持安静；系统仍可能显示后台服务的静默提示。");
    enabled.setOnCheckedChangeListener((button,value)->{AppSettings.put(a,"backgroundCompletionNotice",String.valueOf(value));if(value){ChatService.channels(a);if(android.os.Build.VERSION.SDK_INT>=33&&a.checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS)!=android.content.pm.PackageManager.PERMISSION_GRANTED)a.requestPermissions(new String[]{android.Manifest.permission.POST_NOTIFICATIONS},91);}refresh.run();});
    new AlertDialog.Builder(a).setTitle("后台完成提醒").setView(box).setPositiveButton("完成",null).show();
  }
  static void defaultEntry(Activity a,Runnable refresh){
    JSONArray rows=ProfileCatalog.get(a).list();List<Integer> ids=new ArrayList<>();List<String> titles=new ArrayList<>();
    for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);if(row.optBoolean("created")){ids.add(row.optInt("slot"));titles.add(row.optString("name"));}}
    LinearLayout box=DesignUi.column(a);box.setPadding(DesignUi.dp(a,18),0,DesignUi.dp(a,18),DesignUi.dp(a,14));Spinner spinner=new Spinner(a);
    spinner.setAdapter(new ArrayAdapter<>(a,android.R.layout.simple_spinner_dropdown_item,titles));spinner.setSelection(Math.max(0,ids.indexOf(AppSettings.defaultSlot(a))));box.addView(spinner);
    CheckBox direct=new CheckBox(a);direct.setText("启动时直接进入默认环境的原网页");direct.setChecked(AppSettings.bool(a,"startupDirect",true));box.addView(direct);
    DesignUi.note(box,"关闭后先进入环境管理。底部“会话”会回到正在使用的环境。");
    AlertDialog dialog=new AlertDialog.Builder(a).setTitle("默认环境与启动入口").setView(box).setPositiveButton("保存",(d,w)->{if(spinner.getSelectedItemPosition()<0)return;AppSettings.defaultSlot(a,ids.get(spinner.getSelectedItemPosition()));AppSettings.put(a,"startupDirect",String.valueOf(direct.isChecked()));refresh.run();if(a instanceof MainActivity&&((MainActivity)a).designChrome!=null)((MainActivity)a).designChrome.update();}).setNegativeButton("取消",null).show();
  }
  static void appearance(Activity a){
    LinearLayout box=DesignUi.column(a);box.setPadding(DesignUi.dp(a,18),0,DesignUi.dp(a,18),DesignUi.dp(a,14));DesignUi.field(box,"管理界面","浅色背景 · 清晰分组 · 蓝色操作按钮");
    DesignUi.note(box,"ChatGPT 原网页继续使用网站自身的外观设置。");
    box.addView(DesignUi.button(a,"查看品牌启动页",false,()->a.startActivity(new android.content.Intent(a,BrandLaunchActivity.class).putExtra("previewBrand",true))));
    new AlertDialog.Builder(a).setTitle("界面与品牌页").setView(box).setPositiveButton("关闭",null).show();
  }
}
