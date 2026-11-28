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
      browserDetail=Profiles.display(a,target.slot)+" · "+BrowserPreferences.engine(profile).label;
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
    group(a,help,"应用更新",AppSettings.get(a,"updateLabel","当前版本 "+AppVersion.name(a)),"download",()->AppUpdates.open(a));
    group(a,help,"关于与使用帮助","版本与使用说明","info",()->about(a));
    group(a,help,"功能支持范围","查看支持的功能","shield",()->capabilities(a));
  }
  static void group(Activity a,LinearLayout box,String title,String detail,String icon,Runnable click){SettingsWorkspaceStyle.row(a,box,title,detail,icon,click);}
  private static void capabilityItem(LinearLayout group,String glyph,String title,String detail,String badge,int badgeTone){
    Context c=group.getContext();
    if(group.getChildCount()>0)group.addView(ReferenceUi.modalDivider(c,58));
    LinearLayout row=DesignUi.row(c);row.setGravity(android.view.Gravity.TOP);
    row.setPadding(DesignUi.dp(c,16),DesignUi.dp(c,13),DesignUi.dp(c,16),DesignUi.dp(c,13));
    ImageView icon=new ImageView(c);icon.setImageDrawable(new ReferenceUi.IconTileDrawable(c,glyph,30,false,false));
    icon.setImportantForAccessibility(android.view.View.IMPORTANT_FOR_ACCESSIBILITY_NO);
    LinearLayout.LayoutParams ip=new LinearLayout.LayoutParams(DesignUi.dp(c,30),DesignUi.dp(c,30));ip.topMargin=DesignUi.dp(c,1);ip.setMarginEnd(DesignUi.dp(c,12));
    row.addView(icon,ip);
    LinearLayout copy=DesignUi.column(c);
    LinearLayout head=DesignUi.row(c);head.setGravity(android.view.Gravity.CENTER_VERTICAL);
    TextView h=ReferenceUi.workspaceText(c,title,15,DesignUi.TEXT,true);
    head.addView(h,new LinearLayout.LayoutParams(0,-2,1));
    if(badge!=null&&!badge.isEmpty()){
      int fg=badgeTone==2?ReferenceUi.greenInk():badgeTone==1?ReferenceUi.brandBlue():ReferenceUi.secondaryInk();
      ReferenceUi.AdaptiveSurface bg=badgeTone==2
          ?new ReferenceUi.AdaptiveSurface(c,7,0x1815804e,0x2634d38b)
          :badgeTone==1
              ?new ReferenceUi.AdaptiveSurface(c,7,0x160067d8,0x266da4ff)
              :new ReferenceUi.AdaptiveSurface(c,7,0x12111827,0x1cffffff);
      TextView pill=ReferenceUi.crisp(ReferenceUi.workspaceText(c,badge,ReferenceUi.STATUS_SIZE,fg,true));
      pill.setTypeface(ReferenceUi.TYPE_SEMIBOLD);pill.setLetterSpacing(0.025f);
      pill.setPadding(DesignUi.dp(c,7),DesignUi.dp(c,2),DesignUi.dp(c,7),DesignUi.dp(c,2));
      pill.setBackground(bg);pill.setSingleLine(true);
      LinearLayout.LayoutParams bp=new LinearLayout.LayoutParams(-2,-2);bp.setMarginStart(DesignUi.dp(c,8));
      head.addView(pill,bp);
    }
    copy.addView(head,new LinearLayout.LayoutParams(-1,-2));
    TextView sub=ReferenceUi.prose(ReferenceUi.workspaceText(c,detail,ReferenceUi.SECONDARY_SIZE,ReferenceUi.secondaryInk(),false));
    sub.setPadding(0,DesignUi.dp(c,4),0,0);copy.addView(sub);
    row.addView(copy,new LinearLayout.LayoutParams(0,-2,1));
    group.addView(row,new LinearLayout.LayoutParams(-1,-2));
  }
  static void about(Activity a){
    ReferenceUi.Modal d=new ReferenceUi.Modal(a,"关于与使用帮助");
    LinearLayout hero=ReferenceUi.modalGroup(a);
    LinearLayout head=DesignUi.row(a);head.setPadding(DesignUi.dp(a,16),DesignUi.dp(a,14),DesignUi.dp(a,16),DesignUi.dp(a,14));
    ImageView mark=new ImageView(a);mark.setImageDrawable(new ReferenceUi.IconTileDrawable(a,"brand",36,false,true));
    mark.setImportantForAccessibility(android.view.View.IMPORTANT_FOR_ACCESSIBILITY_NO);
    LinearLayout.LayoutParams mp=new LinearLayout.LayoutParams(DesignUi.dp(a,36),DesignUi.dp(a,36));mp.setMarginEnd(DesignUi.dp(a,12));
    head.addView(mark,mp);
    LinearLayout titles=DesignUi.column(a);
    titles.addView(ReferenceUi.heroTitle(a,"元婴期院士"));
    TextView ver=ReferenceUi.tabular(ReferenceUi.crisp(ReferenceUi.workspaceText(a,"版本 "+AppVersion.name(a)+" · Android 双内核浏览器",ReferenceUi.SECONDARY_SIZE,ReferenceUi.secondaryInk(),false)));
    ver.setPadding(0,DesignUi.dp(a,3),0,0);titles.addView(ver);
    head.addView(titles,new LinearLayout.LayoutParams(0,-2,1));
    hero.addView(head,new LinearLayout.LayoutParams(-1,-2));
    d.body.addView(hero,new LinearLayout.LayoutParams(-1,-2));
    ReferenceUi.modalSection(d.body,"使用说明");
    LinearLayout notes=ReferenceUi.modalGroup(a);
    if(ChromiumEntry.managed(a)){
      capabilityItem(notes,"browser","双内核启动","Gecko 随应用安装，也是新环境的默认浏览器；独立 Chromium 可在环境的浏览器设置中下载安装。","",0);
      capabilityItem(notes,"window","独立环境与草稿","环境分别保存内核选择、登录和网络配置。Gecko 在 ChatGPT 网页提供草稿救援和离线会话检索。","",0);
      capabilityItem(notes,"file","许可与源码","Chromium 由 Cefrium 0.21.0 提供，使用 LGPL-3.0-or-later。上游源码和第三方声明随本版本发布说明提供。","",0);
    }else{
      capabilityItem(notes,"browser","双内核浏览","Gecko 与 Chromium 都能输入网址或搜索，默认网站为 https://chatgpt.com/；Gecko 额外提供草稿救援与离线会话检索，Chromium 支持多标签、收藏历史、页内查找与文件操作。","",0);
      capabilityItem(notes,"window","多环境独立隔离","每个环境分别保存登录、网络和指纹配置，双内核 Cookie 与指纹配置相互独立，内核只在创建环境时选择，默认 Firefox（Gecko）；创建后仍可编辑首页。","",0);
      capabilityItem(notes,"shield","本地加密与隐私","后台完成提醒默认关闭。登录数据保存在本机，网络凭据与 Chromium 指纹配置由 Android Keystore 加密；第三方许可随源码提供。","",0);
    }
    d.body.addView(notes,new LinearLayout.LayoutParams(-1,-2));
    d.buttons("关闭",d::dismiss,"",()->{});d.show();
  }
  static void capabilities(Activity a){
    ReferenceUi.Modal d=new ReferenceUi.Modal(a,"功能支持范围");
    ReferenceUi.modalSection(d.body,"核心能力");
    LinearLayout core=ReferenceUi.modalGroup(a);
    if(ChromiumEntry.managed(a)){
      capabilityItem(core,"browser","Gecko 浏览器","网页浏览、独立登录、原生隐私模板、文件操作和 ChatGPT 草稿救援。","已完整支持",2);
      capabilityItem(core,"browser","Chromium 浏览器","网页浏览、独立登录、文件上传下载。","已完整支持",2);
      capabilityItem(core,"globe","Chromium 线路","系统直连、内置线路、固定代理和强制 VPN（强制 VPN 核验需要 Android 13+）。","按环境生效",1);
      capabilityItem(core,"window","多环境隔离","最多 8 个独立环境，支持分组、备注、收藏和删除。","已完整支持",2);
      d.body.addView(core,new LinearLayout.LayoutParams(-1,-2));
    }else{
      capabilityItem(core,"browser","双内核浏览","切换网址、搜索、独立登录、环境指纹配置与自检。","已完整支持",2);
      capabilityItem(core,"shield","Gecko 原生隐私模板","在 ChatGPT 网页提供草稿救援与离线会话检索。","已完整支持",2);
      capabilityItem(core,"shield","Chromium 指纹保护","原生 UA / UA-CH，页面及框架的 Canvas、WebGL 调试显卡标识、音频复制读出与 WebRTC 构造器保护；支持多标签、收藏与历史、页内查找及文件操作。","按环境生效",1);
      capabilityItem(core,"window","多环境隔离","最多 8 个独立环境，支持分组、备注、收藏和删除。","已完整支持",2);
      d.body.addView(core,new LinearLayout.LayoutParams(-1,-2));
      ReferenceUi.modalSection(d.body,"边界与说明");
      LinearLayout limits=ReferenceUi.modalGroup(a);
      ReferenceUi.modalTopicItem(limits,"shield","Chromium 未覆盖范围","Worker、Service Worker、OffscreenCanvas、独立时区、字体、硬件及网络协议指纹未覆盖。Chrome 扩展尚不支持。设置回读不代表完整指纹已验证。");
      ReferenceUi.modalTopicItem(limits,"lock","网站权限与代理边界","Chromium 可按当前 HTTPS 网站的请求逐次授权相机、麦克风和大致位置，不保存长期允许记录。HTTP 代理不能代替设备 VPN，应用不会自动开启 VPN。");
      ReferenceUi.modalTopicItem(limits,"browser","Gecko 原生模板范围",NativeCapabilityManifest.officialGecko().unsupportedSummary());
      ReferenceUi.modalTopicItem(limits,"info","后台提醒与容量说明","后台完成提醒需主动开启。多环境同时运行容量尚未测量。");
      d.body.addView(limits,new LinearLayout.LayoutParams(-1,-2));
    }
    d.buttons("关闭",d::dismiss,"",()->{});d.show();
  }
  static void completionReminders(Activity a,Runnable refresh){
    ReferenceUi.Modal d=new ReferenceUi.Modal(a,"后台完成提醒");
    LinearLayout card=ReferenceUi.modalGroup(a);
    Switch enabled=ReferenceUi.modalSwitchRow(card,"离开应用后提醒完成",AppSettings.backgroundCompletionNotice(a));
    d.body.addView(card,new LinearLayout.LayoutParams(-1,-2));
    ReferenceUi.modalFooterNote(d.body,"下载完成后可提醒；网页回复状态请直接查看原网页。使用应用时保持安静；系统仍可能显示后台服务的静默提示。");
    enabled.setOnCheckedChangeListener((button,value)->{AppSettings.put(a,"backgroundCompletionNotice",String.valueOf(value));if(value){ChatService.channels(a);if(android.os.Build.VERSION.SDK_INT>=33&&a.checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS)!=android.content.pm.PackageManager.PERMISSION_GRANTED)a.requestPermissions(new String[]{android.Manifest.permission.POST_NOTIFICATIONS},91);}refresh.run();});
    d.buttons("",()->{},"完成",d::dismiss);d.show();
  }
  static void defaultEntry(Activity a,Runnable refresh){
    JSONArray rows=ProfileCatalog.get(a).list();
    List<EnvironmentSpec.Identity> choices=new ArrayList<>();List<String> titles=new ArrayList<>();
    int current=AppSettings.defaultSlot(a),initialSelected=0;
    for(int i=0;i<rows.length();i++){
      JSONObject row=rows.optJSONObject(i);
      if(row==null||!AppSettings.selectable(row))continue;
      try{
        EnvironmentSpec.Identity identity=new EnvironmentSpec.Identity(row.optInt("slot"),row.optInt("generation"),row.optString("environmentId"));
        if(identity.slot==current)initialSelected=choices.size();
        choices.add(identity);titles.add(row.optString("name"));
      }catch(IllegalArgumentException unavailable){}
    }
    if(choices.isEmpty()){ReferenceUi.message(a,"默认环境与启动入口","暂无可用环境，请返回环境管理后重试。");return;}
    ReferenceUi.Modal d=new ReferenceUi.Modal(a,"默认环境与启动入口");
    final int[] selected={initialSelected};
    ReferenceUi.modalSection(d.body,"默认启动环境");
    LinearLayout envGroup=ReferenceUi.modalGroup(a);
    final Runnable[] renderChoices={null};
    renderChoices[0]=()->{
      envGroup.removeAllViews();
      for(int i=0;i<titles.size();i++){
        final int idx=i;String name=titles.get(i);
        ReferenceUi.modalChoice(envGroup,name,"",name,true,selected[0]==i,()->{selected[0]=idx;renderChoices[0].run();});
      }
    };
    renderChoices[0].run();
    d.body.addView(envGroup,new LinearLayout.LayoutParams(-1,-2));
    ReferenceUi.modalSection(d.body,"启动行为");
    LinearLayout behavior=ReferenceUi.modalGroup(a);
    Switch direct=ReferenceUi.modalSwitchRow(behavior,"启动时显示默认环境的仪表盘",AppSettings.bool(a,"startupDirect",true));
    d.body.addView(behavior,new LinearLayout.LayoutParams(-1,-2));
    ReferenceUi.modalFooterNote(d.body,"关闭后先进入环境管理。底部“浏览器”会回到正在使用的环境。");
    TextView issue=ReferenceUi.workspaceText(a,"",ReferenceUi.ACTION_SIZE,ReferenceUi.redInk(),false);
    issue.setPadding(DesignUi.dp(a,16),DesignUi.dp(a,8),DesignUi.dp(a,16),0);
    issue.setVisibility(android.view.View.GONE);issue.setAccessibilityLiveRegion(android.view.View.ACCESSIBILITY_LIVE_REGION_POLITE);
    d.body.addView(issue,new LinearLayout.LayoutParams(-1,-2));
    d.buttons("取消",d::dismiss,"保存",()->{
      int position=selected[0];
      if(position<0||position>=choices.size())return;
      EnvironmentSpec.Identity identity=choices.get(position);
      boolean saved=false;
      try{saved=AppSettings.saveStartup(a,identity.slot,identity.generation,identity.environmentId,direct.isChecked());}
      catch(RuntimeException unavailable){}
      if(!saved){
        issue.setText("环境已变化或设置暂时无法保存，请重新选择或重试。");
        issue.setVisibility(android.view.View.VISIBLE);d.resize();return;
      }
      d.dismiss();refresh.run();
      if(a instanceof MainActivity&&((MainActivity)a).designChrome!=null)((MainActivity)a).designChrome.update();
    });
    d.show();
  }
  static void appearance(Activity a,Runnable refresh){
    ReferenceUi.Modal d=new ReferenceUi.Modal(a,"白天与黑夜");
    LinearLayout modes=ReferenceUi.modalGroup(a);
    final Runnable[] renderModes={null};
    String[] modeHints={"随系统深浅色与定时设置自动切换","始终使用浅色界面与网页配色","始终使用深色界面与网页配色"};
    renderModes[0]=()->{
      modes.removeAllViews();
      String active=AppAppearance.mode();
      for(int i=0;i<AppAppearance.MODES.length;i++){
        final String modeKey=AppAppearance.MODES[i];
        ReferenceUi.modalChoice(modes,AppAppearance.LABELS[i],modeHints[i],active.equals(modeKey),()->{
          AppAppearance.choose(a,modeKey);refresh.run();renderModes[0].run();
        });
      }
    };
    renderModes[0].run();
    d.body.addView(modes,new LinearLayout.LayoutParams(-1,-2));
    ReferenceUi.modalFooterNote(d.body,"网页使用 ChatGPT 自带的浅色／深色配色，保留输入，不重新加载。");
    ReferenceUi.modalSection(d.body,"网页配色同步");
    TextView website=ReferenceUi.workspaceText(a,"正在检查网页配色同步状态…",ReferenceUi.SECONDARY_SIZE,ReferenceUi.secondaryInk(),false);
    ReferenceUi.balancedBreaks(website);
    website.setPadding(DesignUi.dp(a,16),0,DesignUi.dp(a,16),DesignUi.dp(a,8));
    d.body.addView(website,new LinearLayout.LayoutParams(-1,-2));
    LinearLayout syncCard=ReferenceUi.modalGroup(a);
    ReferenceUi.modalRowAction(syncCard,"refresh","重新同步网页配色",false,()->AppAppearance.resynchronize(a));
    ReferenceUi.modalRowAction(syncCard,"clipboard","复制配色检查结果",false,()->{ChatSession session=ChatSession.peek();JSONObject value=session==null||session.web==null?J.obj("status","unavailable"):session.web.appearanceReport();
      android.content.ClipboardManager clipboard=(android.content.ClipboardManager)a.getSystemService(android.content.Context.CLIPBOARD_SERVICE);if(clipboard!=null)clipboard.setPrimaryClip(android.content.ClipData.newPlainText("网页配色检查",value.toString()));});
    ReferenceUi.modalRowAction(syncCard,"appearance","查看品牌启动页",false,()->{d.dismiss();a.startActivity(new android.content.Intent(a,BrandLaunchActivity.class).putExtra("previewBrand",true));});
    d.body.addView(syncCard,new LinearLayout.LayoutParams(-1,-2));
    Runnable status=new Runnable(){public void run(){if(!d.isShowing())return;ChatSession session=ChatSession.peek();JSONObject value=session==null||session.web==null?new JSONObject():session.web.appearanceReport();String state=value.optString("status");
      String message="page-hidden".equals(value.optString("reason"))?"返回会话后会继续确认网页配色。":"confirmed".equals(state)?"聊天区域配色采样与应用一致。":"partial".equals(state)?"聊天区域配色采样一致，但偏好暂未保存；可重新同步。":"failed".equals(state)?"网页配色尚未确认同步，可重新同步并复制检查结果。":"pending".equals(state)?"正在确认网页配色…":"打开 ChatGPT 会话后会自动同步网页配色。";
      if(!message.contentEquals(website.getText()))website.setText(message);website.postDelayed(this,500);}};
    d.buttons("",()->{},"完成",d::dismiss);d.show();website.post(status);
  }
}
