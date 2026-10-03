package local.pocketchat;

import android.content.*;
import android.webkit.*;
import androidx.webkit.*;
import java.io.InputStream;
import java.util.*;
import java.util.regex.*;

final class BrowserPrivacy {
  final ChatSession session;ScriptHandler script,displayScript;boolean earlyInstalled,desktop,desktopReady;String originalAgent;
  BrowserPrivacy(ChatSession s){session=s;originalAgent=WebSettings.getDefaultUserAgent(s.context);apply();}
  int level(){return session.prefs.getInt("privacyLevel",1);}
  boolean earlySupported(){return WebViewFeature.isFeatureSupported(WebViewFeature.DOCUMENT_START_SCRIPT);}
  boolean wantsDesktop(){return ProfileCatalog.get(session.context).item(Profiles.slot(session.context)).optBoolean("desktopSite");}
  boolean canNavigate(){return (!desktop||desktopReady)&&(level()==0||earlyInstalled&&session.guard.workerProtection);}
  static String reducedAgent(String original){return BrowserDisplay.agent(original,1,false);}
  void apply(){WebSettings settings=session.web.getSettings();settings.setGeolocationEnabled(false);settings.setAllowFileAccess(false);settings.setAllowContentAccess(false);settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);settings.setSafeBrowsingEnabled(true);settings.setMediaPlaybackRequiresUserGesture(true);CookieManager.getInstance().setAcceptThirdPartyCookies(session.web,false);GeolocationPermissions.getInstance().clearAll();
    if(script!=null){script.remove();script=null;}if(displayScript!=null){displayScript.remove();displayScript=null;}
    earlyInstalled=false;desktop=wantsDesktop();desktopReady=!desktop;int level=level();
    settings.setUseWideViewPort(desktop);settings.setLoadWithOverviewMode(desktop);settings.setSupportZoom(true);settings.setBuiltInZoomControls(desktop);settings.setDisplayZoomControls(!desktop);session.reading.configure(desktop);
    if(desktop&&earlySupported())try{displayScript=WebViewCompat.addDocumentStartJavaScript(session.web,BrowserDisplay.viewportScript(),new HashSet<>(Arrays.asList("https://chatgpt.com","https://chat.openai.com")));desktopReady=true;}catch(Exception ignored){}
    settings.setUserAgentString(BrowserDisplay.agent(originalAgent,level,desktop));
    if(level>0&&earlySupported())try(InputStream in=session.context.getAssets().open("privacy-shield.js")){String source=J.text(in,64*1024).replace("__LEVEL__",String.valueOf(level));script=WebViewCompat.addDocumentStartJavaScript(session.web,source,Collections.singleton("*"));earlyInstalled=true;}catch(Exception ignored){}
  }
  String summary(){String text="当前环境："+Profiles.display(session.context,Profiles.slot(session.context))+"\n保护等级："+(level()==2?"强化":level()==1?"标准":"兼容");
    text+="\n网页显示："+BrowserDisplay.label(desktop)+(desktop&&!desktopReady?" · 当前 WebView 不支持":"");
    text+="\n第三方 Cookie：阻止\n位置 / 摄像头 / 网页麦克风：不授权\nHTTP / 混合内容：阻止\n设备型号 UA："+(level()>0?"精简":"系统默认");
    text+="\n加载前脚本保护："+(earlyInstalled?"已注册":level()==0?"未启用":"此 WebView 不支持");
    text+="\nWebRTC："+(earlyInstalled?"加载前限制":"未覆盖，不能保证防止 RTC 绕行");
    text+="\n网页后台请求："+(session.guard.workerProtection?session.guard.blocked?"已暂停联网":"与网页共用连接保护":"未覆盖");
    text+="\n局域网 / 本机地址探测：阻止已知本地地址";
    text+="\n电量 / 网络类型信息："+(earlyInstalled?"限制读取":"未覆盖");
    text+="\n手机 VPN 断开保护："+(session.guard.requiresVpn()?session.guard.vpnActive()?"已启用，系统报告 VPN 已连接":"已启用，等待 VPN":"当前使用应用代理或已手动关闭");
    text+="\nCanvas / 音频指纹读取："+(level()>=2&&earlyInstalled?"限制，可能影响页面功能":"允许");
    NativeNetwork n=NativeNetwork.get(session.context);text+="\n网页出口："+(session.internalNetwork()?n.ready&&n.lastVerified>0?"当前固定出口已核实":"固定出口尚未核实":"使用已配置的手机网络，未核实固定出口");
    return text+"\n\n独立环境分开保存登录、网页存储、记录与网络配置；仍由同一应用和设备承载。保护会降低部分可识别信息，网站仍能看到出口 IP，不能保证识别不出 VPN 或避免封号。不能隐藏已登录账号，也不能完全伪装浏览器内核、TLS 或所有硬件指纹。入口连接与订阅请求仍需使用手机网络。";
  }
}
