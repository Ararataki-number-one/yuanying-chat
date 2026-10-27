package local.pocketchat;

/** Firefox owns browser identity, privacy and cookies for every environment. */
final class BrowserPrivacy {
  final ChatSession session;boolean earlyInstalled,desktop,desktopReady;String originalAgent="";
  BrowserPrivacy(ChatSession s){session=s;apply();}
  int level(){return session.prefs.getInt("privacyLevel",1);}
  boolean earlySupported(){return true;}
  boolean wantsDesktop(){return ProfileCatalog.get(session.context).item(Profiles.slot(session.context)).optBoolean("desktopSite");}
  boolean canNavigate(){return true;}
  static String reducedAgent(String original){return original;}
  void apply(){
    desktop=wantsDesktop();desktopReady=true;earlyInstalled=false;
    session.web.configure(desktop,level());session.reading.configure(desktop);
  }
  String summary(){String text="当前环境："+Profiles.display(session.context,Profiles.slot(session.context))+"\n保护等级："+(level()==2?"强化":level()==1?"标准":"兼容");
    return text+"\n内核："+GeckoWebView.VERSION+"\n网页显示："+BrowserDisplay.label(desktop)+"\n浏览器身份：Firefox 官方手机版 / 电脑版\n登录与网页存储：当前环境独立目录\n网页线路：沿用此环境已有网络配置\n代理不可用：阻止连接，不自动直连\nWebRTC：关闭\nHTTP 与已知本地网页地址：阻止\n指纹追踪器："+(level()>0?"官方列表拦截":"兼容模式")+"\n原生抗指纹状态："+session.web.protectionSummary()+"\nCanvas / 音频 / 设备信息：可按需自检；设置回读不代表所有 API 保护通过"+"\n手机 VPN 断开保护："+(session.guard.requiresVpn()?session.guard.vpnActive()?"已启用，VPN 已连接":"已启用，等待 VPN":"使用环境代理或已关闭")+"\n\n强化模式使用 Firefox 原生抗指纹设置，可能影响网站验证、Canvas 和音频。自检可以检查当前内核。原系统内核登录数据仍保留，各环境分别保存登录。";
  }
}
