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
    DesignUi.section(box,"系统权限", "");
    group(a,box,"通知与电池设置","通知提醒与后台运行权限","chat",()->FeatureDialogs.backgroundSettings(a));
    DesignUi.section(box,"帮助与能力","");
    group(a,box,"关于与使用帮助","版本与使用说明","settings",()->about(a));
    group(a,box,"功能支持范围","查看支持的功能","shield",()->capabilities(a));
  }
  static void group(Activity a,LinearLayout box,String title,String detail,String icon,Runnable click){DesignUi.addCard(box,DesignUi.setting(a,icon,title,detail,"",click));}
  static void about(Activity a){DesignUi.message(a,"元婴期院士 · "+AppVersion.name(a),"Android ChatGPT 网页客户端\n\n在环境列表新建或编辑环境。每个环境分别登录，编辑页保存基本信息、浏览器保护和使用偏好。\n\n网络配置在所属环境内保存并连接。应用设置控制默认启动环境与系统权限。下载中心汇总文件。\n\n聊天与登录保存在本机，网络凭据由 Android Keystore 加密。第三方许可随源码提供，包括 Mihomo、AndroidX、KaTeX、Marked 与 DOMPurify。\n\n保护范围以实际自检为准。");}
  static void capabilities(Activity a){DesignUi.message(a,"功能支持范围","已实现\n• 最多 8 个独立环境、分组、备注与收藏\n• 独立登录、Cookie、聊天、草稿和网络配置\n• 手机网络 / VPN、应用代理、单个订阅与固定出口\n• 三档隐私保护、现有环境自检\n• 文件下载、后台等待与通知\n\n后续能力\n自定义 UA / 指纹、独立语言时区、多个订阅、自动化、环境删除与登录数据清理仍未开放。\n\n本应用使用 Android System WebView。实际保护范围以自检结果为准。");}
  static void defaultEntry(Activity a,Runnable refresh){
    JSONArray rows=ProfileCatalog.get(a).list();List<Integer> ids=new ArrayList<>();List<String> titles=new ArrayList<>();
    for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);if(row.optBoolean("created")){ids.add(row.optInt("slot"));titles.add(row.optString("name"));}}
    LinearLayout box=DesignUi.column(a);box.setPadding(DesignUi.dp(a,18),0,DesignUi.dp(a,18),DesignUi.dp(a,14));Spinner spinner=new Spinner(a);
    spinner.setAdapter(new ArrayAdapter<>(a,android.R.layout.simple_spinner_dropdown_item,titles));spinner.setSelection(Math.max(0,ids.indexOf(AppSettings.defaultSlot(a))));box.addView(spinner);
    CheckBox direct=new CheckBox(a);direct.setText("启动时直接进入默认环境的原网页");direct.setChecked(AppSettings.bool(a,"startupDirect",true));box.addView(direct);
    DesignUi.note(box,"关闭后先进入环境管理。底部“会话”会回到正在使用的环境。");
    int originalSlot=AppSettings.defaultSlot(a);boolean originalDirect=direct.isChecked();
    AlertDialog dialog=new AlertDialog.Builder(a).setTitle("默认环境与启动入口").setView(box).setPositiveButton("保存",(d,w)->{if(spinner.getSelectedItemPosition()<0)return;AppSettings.defaultSlot(a,ids.get(spinner.getSelectedItemPosition()));AppSettings.put(a,"startupDirect",String.valueOf(direct.isChecked()));refresh.run();DesignUi.feedback(a,"启动设置已保存");if(a instanceof MainActivity&&((MainActivity)a).designChrome!=null)((MainActivity)a).designChrome.update();}).setNegativeButton("取消",null).show();
    DesignUi.protectEdits(a,dialog,()->spinner.getSelectedItemPosition()>=0&&(ids.get(spinner.getSelectedItemPosition())!=originalSlot||direct.isChecked()!=originalDirect));
  }
  static void appearance(Activity a){
    LinearLayout box=DesignUi.column(a);box.setPadding(DesignUi.dp(a,18),0,DesignUi.dp(a,18),DesignUi.dp(a,14));DesignUi.field(box,"管理界面","浅色背景 · 清晰分组 · 蓝色操作按钮");
    DesignUi.note(box,"ChatGPT 原网页继续使用网站自身的外观设置。");
    box.addView(DesignUi.button(a,"查看品牌启动页",false,()->a.startActivity(new android.content.Intent(a,BrandLaunchActivity.class).putExtra("previewBrand",true))));
    new AlertDialog.Builder(a).setTitle("界面与品牌页").setView(box).setPositiveButton("关闭",null).show();
  }
}
