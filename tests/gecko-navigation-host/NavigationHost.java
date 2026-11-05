package local.pocketchat;

import org.json.*;

/** Complete production policy on literal inputs; this host makes no DNS query. */
public final class NavigationHost {
  static final JSONArray checks=new JSONArray();
  static void check(String name,boolean passed){checks.put(J.obj("name",name,"pass",passed));if(!passed)throw new AssertionError(name);}
  static void input(String raw,String expected){check("Normalize browser input "+raw,expected.equals(GeckoNavigationPolicy.normalizeInput(raw)));}
  static void reject(String raw){boolean failed=false;try{GeckoNavigationPolicy.normalizeInput(raw);}catch(IllegalArgumentException expected){failed=true;}check("Unsafe input fails visibly "+raw,failed);}
  public static void main(String[] args){
    check("Gecko generic home retains the established public ChatGPT home",GeckoNavigationPolicy.home().equals("https://chatgpt.com/"));
    input(null,GeckoNavigationPolicy.home());input("   ",GeckoNavigationPolicy.home());
    input("example.com","https://example.com/");
    input("HTTP://EXAMPLE.COM/Case?Query=Yes#fragment","http://example.com/Case?Query=Yes#fragment");
    input("例子.公司/中文","https://xn--fsqu00a.xn--55qx5d/%E4%B8%AD%E6%96%87");
    input("天气 明天","https://www.google.com/search?q=%E5%A4%A9%E6%B0%94+%E6%98%8E%E5%A4%A9");
    for(String url:new String[]{"https://chatgpt.com/","http://example.com/plain","https://www.wikipedia.org/wiki/Main_Page","https://accounts.google.com/o/oauth2/v2/auth","https://auth.openai.com/authorize?state=controlled","https://example.com:8443/path?q=1#part","https://8.8.8.8/","https://[2001:4860:4860::8888]/"}){
      check("Public arbitrary website navigation is admitted "+url,GeckoNavigationPolicy.publicWeb(url));
      check("Public arbitrary website can be restored "+url,GeckoNavigationPolicy.restorable(url));
    }
    for(String url:new String[]{null,"","javascript:alert(1)","data:text/html,private","file:///private","content://local/private","intent://example.com/#Intent;end","ftp://example.com/file","about:blank","http://localhost/","http://127.0.0.1/","http://2130706433/","http://0x7f000001/","http://0177.1/","http://10.0.0.1/","http://192.168.1.1/","http://169.254.169.254/","http://100.64.0.1/","http://[::1]/","http://[fd00::1]/","http://[::ffff:127.0.0.1]/","https://user:pass@example.com/","https://example.com\\@127.0.0.1/","https://example.com:65536/","https://example.com/\nprivate","https://example.com/\u202eprivate"}){
      check("Unsafe navigation is blocked "+url,!GeckoNavigationPolicy.publicWeb(url));
      check("Unsafe saved navigation is not restored "+url,!GeckoNavigationPolicy.restorable(url));
    }
    for(String raw:new String[]{"javascript:alert(1)","http://127.0.0.1/","localhost","192.168.1.1","file:///private","https://user@example.com/"})reject(raw);
    check("Same target ignores query and fragment",GeckoNavigationPolicy.sameTarget("https://example.com/path?old=1#before","https://example.com/path?new=2#after"));
    check("Same target canonicalizes HTTPS port and host case",GeckoNavigationPolicy.sameTarget("https://EXAMPLE.COM/path","https://example.com:443/path"));
    check("Same target canonicalizes HTTP port and empty path",GeckoNavigationPolicy.sameTarget("http://example.com","http://example.com:80/"));
    for(String[] pair:new String[][]{{"https://example.com/path","https://other.example/path"},{"https://example.com/path","http://example.com/path"},{"https://example.com/path","https://example.com:8443/path"},{"https://example.com/path","https://example.com/other"},{"https://example.com/Case","https://example.com/case"},{"https://example.com/a%2Fb","https://example.com/a/b"},{"http://127.0.0.1/path","http://127.0.0.1/path"},{null,"https://example.com/"}})check("Different or unsafe targets do not match "+pair[0]+" -> "+pair[1],!GeckoNavigationPolicy.sameTarget(pair[0],pair[1]));
    System.out.println(J.obj("status","passed","passed",checks.length(),"total",checks.length(),"checks",checks,"actualAndroidExecution",false,"actualNetworkExecution",false).toString());
  }
}
