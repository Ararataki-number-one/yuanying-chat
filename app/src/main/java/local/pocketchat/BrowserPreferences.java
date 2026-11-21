package local.pocketchat;

import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;

/** Entry preferences belong to one environment; neither engine's login data is touched. */
final class BrowserPreferences {
  static final String DEFAULT_URL="https://chatgpt.com/";
  static final String START_CHAT=EnvironmentEngine.GECKO_TOKEN,START_BROWSER=EnvironmentEngine.CHROMIUM_TOKEN;
  static final String KEY_START=EnvironmentEngine.KEY,KEY_HOME="browserHomeUrl";
  private BrowserPreferences() {}
  private static SharedPreferences preferences(Context context){return context.getSharedPreferences("chat",Context.MODE_PRIVATE);}
  static EnvironmentEngine engine(Context context){
    try{return EnvironmentEngine.read(preferences(context));}
    catch(RuntimeException inaccessible){return EnvironmentEngine.UNAVAILABLE;}
  }
  static boolean startBrowser(Context context){return engine(context)==EnvironmentEngine.CHROMIUM;}
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
  static boolean saveHome(Context context,String address){
    return preferences(context).edit().putString(KEY_HOME,normalizeHome(address)).commit();
  }
  static boolean nativeOpening(Intent intent){
    if(intent==null||Intent.ACTION_VIEW.equals(intent.getAction()))return false;
    if(intent.hasExtra("openDownload")||intent.getBooleanExtra("openEnvironmentEditor",false)||intent.getBooleanExtra("returnToEnvironmentList",false))return true;
    String action=intent.getStringExtra("openWindowAction");
    if("network".equals(action)||"settings".equals(action)||"edit".equals(action)||"overview".equals(action))return true;
    Uri data=intent.getData();
    return data!=null&&"pocketchat".equals(data.getScheme())&&"download".equals(data.getHost());
  }
  static boolean shouldOpenBrowser(Context context,Intent intent){return startBrowser(context)&&!nativeOpening(intent);}
  static String openingAddress(Intent intent){
    if(intent==null||nativeOpening(intent))return null;
    String url;
    if(Intent.ACTION_VIEW.equals(intent.getAction())){
      Uri data=intent.getData();url=data==null?null:data.toString();
    }else{
      url=intent.getStringExtra("url");
      if(url==null){
        String conversation=intent.getStringExtra("openConversation");
        if(MainActivity.chatUrl(conversation))url=conversation;
      }
    }
    return BrowserAddressPolicy.allowed(url)?BrowserAddressPolicy.normalizeInput(url):null;
  }
}
