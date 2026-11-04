package local.pocketchat;

import java.util.*;

public final class BrowserAddressHost {
  static final List<String> checks=new ArrayList<>();
  static void check(String name,boolean result){if(!result)throw new AssertionError(name);checks.add(name);}
  static void input(String value,String expected){check("Normalize "+value,expected.equals(BrowserAddressPolicy.normalizeInput(value)));}
  static void refuse(String value){boolean rejected=false;try{BrowserAddressPolicy.normalizeInput(value);}catch(IllegalArgumentException expected){rejected=!expected.getMessage().isEmpty();}check("Refuse unsafe address "+value,rejected);}
  public static void main(String[] args){
    check("Default home is ChatGPT",BrowserAddressPolicy.home().equals("https://chatgpt.com/"));
    input(null,BrowserAddressPolicy.home());input("",BrowserAddressPolicy.home());input("  ",BrowserAddressPolicy.home());
    input("example.com","https://example.com/");input("  example.com/path?q=1#anchor  ","https://example.com/path?q=1#anchor");
    input("HTTP://EXAMPLE.COM/Case/Path?Sensitive=Yes#Heading","http://example.com/Case/Path?Sensitive=Yes#Heading");
    input("https://example.com","https://example.com/");input("//example.com/path","https://example.com/path");
    input("example.com:8443/path","https://example.com:8443/path");input("https://example.com:00443/","https://example.com:443/");
    input("https://EXAMPLE.COM./","https://example.com/");input("例子.公司/中文","https://xn--fsqu00a.xn--55qx5d/%E4%B8%AD%E6%96%87");
    input("天气 明天","https://www.google.com/search?q=%E5%A4%A9%E6%B0%94+%E6%98%8E%E5%A4%A9");
    input("hello","https://www.google.com/search?q=hello");input("C++ tutorial","https://www.google.com/search?q=C%2B%2B+tutorial");
    input("localhost help","https://www.google.com/search?q=localhost+help");
    input("site:example.com android","https://www.google.com/search?q=site%3Aexample.com+android");
    input("filetype:pdf manual","https://www.google.com/search?q=filetype%3Apdf+manual");
    input("intitle:test","https://www.google.com/search?q=intitle%3Atest");
    input("https://example.com/a%2Fb?q=%E4%B8%AD","https://example.com/a%2Fb?q=%E4%B8%AD");
    for(String address:new String[]{
      "https://chatgpt.com/","https://auth.openai.com/authorize?redirect_uri=https%3A%2F%2Fchatgpt.com%2F",
      "https://accounts.google.com/o/oauth2/v2/auth","https://login.microsoftonline.com/common/oauth2/authorize",
      "http://example.com/","https://www.wikipedia.org/","https://example.com:65535/path#fragment",
      "https://8.8.8.8/","https://[2001:4860:4860::8888]/","https://[::ffff:8.8.8.8]/",
      "https://例子.公司/路径","https://example.com/#/login"
    })check("Allow public navigation "+address,BrowserAddressPolicy.allowed(address));
    for(String address:new String[]{
      "javascript:alert(1)","JaVaScRiPt:alert(1)","data:text/html,test","file:///etc/passwd","content://app/private","intent://example.com/#Intent;end","ftp://example.com/","about:blank",
      "http://localhost/","https://localhost:443/","https://LOCALHOST./","http://a.localhost/","http://printer/","http://router.local/","http://router.lan/","http://service.internal/","http://home.arpa/","http://r.home.arpa/",
      "http://127.0.0.1/","http://127.1/","http://2130706433/","http://0x7f000001/","http://0177.0.0.1/","http://0x7f.1/","http://127.1./",
      "http://10.0.0.1/","http://172.16.0.1/","http://172.31.255.255/","http://192.168.0.1/","http://169.254.169.254/","http://100.64.0.1/","http://0.0.0.0/","http://224.0.0.1/","http://255.255.255.255/",
      "http://192.0.2.1/","http://198.51.100.1/","http://203.0.113.1/","http://198.18.0.1/",
      "http://[::]/","http://[::1]/","http://[::ffff:127.0.0.1]/","http://[::ffff:192.168.0.1]/","http://[fd00::1]/","http://[fc00::1]/","http://[fe80::1]/","http://[ff02::1]/","http://[2001:db8::1]/","http://[2002:7f00:0001::]/","http://[fe80::1%25eth0]/",
      "https://user@example.com/","https://user:password@example.com/","https://example.com@127.0.0.1/","https://%6cocalhost/","https://example.com%40evil.com/","https://example.com\\@127.0.0.1/",
      "https://example.com:0/","https://example.com:65536/","https://example.com:/","https://example.com:abc/","https:///missing/","http://[broken]/","http://1.2.3.999/","http://1.2.3.09/","http://999999999999999999999/","https://example.com..", "https://exa_mple.com/",
      "https://example.com/line\nbreak","https://example.com/\u202eevil","https://example.com/a b"
    }){check("Reject unsafe navigation "+address,!BrowserAddressPolicy.allowed(address));refuse(address);}
    for(String bare:new String[]{"localhost","localhost:8080","127.0.0.1","127.1","2130706433","0x7f000001","10.1.2.3/path","[::1]","user@example.com","example.com:abc"})refuse(bare);
    check("Relative link requires browser resolution",!BrowserAddressPolicy.allowed("/relative/login"));
    check("Scheme-relative link requires browser resolution",!BrowserAddressPolicy.allowed("//example.com/login"));
    check("Missing actual URL rejected",!BrowserAddressPolicy.allowed(null)&&!BrowserAddressPolicy.allowed(""));
    StringBuilder oversized=new StringBuilder();for(int i=0;i<8193;i++)oversized.append('a');refuse(oversized.toString());
    System.out.println("{\"status\":\"passed\",\"passed\":"+checks.size()+",\"total\":"+checks.size()+",\"actualAndroidExecution\":false,\"actualNetworkExecution\":false}");
  }
}
