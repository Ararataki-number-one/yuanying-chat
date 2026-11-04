package local.pocketchat;

import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;

/** Entry preferences belong to one environment; neither engine's login data is touched. */
final class BrowserPreferences {
  static final String DEFAULT_URL="https://chatgpt.com/";
  static final String START_CHAT="chatgpt-enhanced",START_BROWSER="chromium";
  static final String KEY_START="browserStartScreen",KEY_HOME="browserHomeUrl";
  private BrowserPreferences() {}
  private static SharedPreferences preferences(Context context){return context.getSharedPreferences("chat",Context.MODE_PRIVATE);}
  static boolean startBrowser(Context context){return START_BROWSER.equals(preferences(context).getString(KEY_START,START_CHAT));}
  static String home(Context context){
    try{return normalizeHome(preferences(context).getString(KEY_HOME,DEFAULT_URL));}
    catch(IllegalArgumentException invalid){return DEFAULT_URL;}
  }
  static String normalizeHome(String input){
    String value=input==null?"":input.trim();if(value.isEmpty())return DEFAULT_URL;
    // The address bar also accepts searches. A saved homepage is an explicit
    // website address; a pasted search-results URL remains a valid website.
    for(int i=0;i<value.length();i++)if(Character.isWhitespace(value.charAt(i))||Character.isSpaceChar(value.charAt(i)))throw new IllegalArgumentException("默认网站请填写网址，不接受搜索词");
    boolean explicit=value.matches("(?i)^https?://.*")||value.startsWith("//");
    if(!explicit&&value.indexOf('.')<0&&!value.startsWith("["))throw new IllegalArgumentException("默认网站请填写完整网址或域名");
    String candidate=value.startsWith("//")?"https:"+value:explicit?value:"https://"+value;
    if(!BrowserAddressPolicy.allowed(candidate))throw new IllegalArgumentException("请输入有效的公共 HTTP 或 HTTPS 网站地址");
    return BrowserAddressPolicy.normalizeInput(candidate);
  }
  static boolean save(Context context,boolean browser,String address){
    String normalized=normalizeHome(address);
    return preferences(context).edit().putString(KEY_START,browser?START_BROWSER:START_CHAT).putString(KEY_HOME,normalized).commit();
  }
  static boolean shouldOpenBrowser(Context context,Intent intent){
    if(intent!=null){
      if(intent.getBooleanExtra("legacyChat",false)||intent.hasExtra("openConversation")||intent.hasExtra("openDownload")||intent.getBooleanExtra("openEnvironmentEditor",false)||intent.getBooleanExtra("returnToEnvironmentList",false))return false;
      String action=intent.getStringExtra("openWindowAction");if(action!=null&&!"chat".equals(action))return false;
      Uri data=intent.getData();if(data!=null&&"pocketchat".equals(data.getScheme())&&("notification".equals(data.getHost())||"download".equals(data.getHost())))return false;
    }
    return startBrowser(context);
  }
}
