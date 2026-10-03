package local.pocketchat;

import java.net.URI;

/** Recognize login pages without collecting account text, credentials or redirect URLs. */
final class LoginPagePolicy {
  static String host(String url){try{URI uri=new URI(url);return "https".equalsIgnoreCase(uri.getScheme())&&uri.getUserInfo()==null&&(uri.getPort()==-1||uri.getPort()==443)?uri.getHost():null;}catch(Exception e){return null;}}
  static boolean google(String url){return "accounts.google.com".equalsIgnoreCase(host(url));}
  static boolean login(String url){
    String host=host(url);if(host==null)return false;host=host.toLowerCase(java.util.Locale.ROOT);
    if(host.equals("accounts.google.com")||host.equals("auth.openai.com")||host.equals("auth0.openai.com")||host.equals("appleid.apple.com")||host.equals("login.live.com")||host.equals("login.microsoftonline.com"))return true;
    try{return host.equals("chatgpt.com")&&new URI(url).getPath().startsWith("/auth/");}catch(Exception e){return false;}
  }
  static String blockedScript(){return "(()=>{if(window!==window.top||location.protocol!=='https:'||location.hostname!=='accounts.google.com')return false;const text=document.body?.innerText||document.body?.textContent||'';return /此浏览器或应用可能不安全|此瀏覽器或應用程式可能不安全|this browser or app may not be secure|disallowed_useragent/i.test(text);})()";}
}
