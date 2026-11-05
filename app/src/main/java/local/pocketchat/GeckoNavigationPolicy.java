package local.pocketchat;

import java.net.URI;

/** Public website navigation is separate from the ChatGPT automation origin. */
final class GeckoNavigationPolicy {
  private GeckoNavigationPolicy() {}
  static String home(){return BrowserAddressPolicy.home();}
  static String normalizeInput(String input){return BrowserAddressPolicy.normalizeInput(input);}
  static boolean publicWeb(String url){return BrowserAddressPolicy.allowed(url);}
  static boolean restorable(String url){return publicWeb(url);}
  static boolean sameTarget(String first,String second){
    if(!publicWeb(first)||!publicWeb(second))return false;
    try{
      URI a=new URI(first),b=new URI(second);
      return a.getScheme().equalsIgnoreCase(b.getScheme())&&a.getHost().equalsIgnoreCase(b.getHost())&&port(a)==port(b)&&path(a).equals(path(b));
    }catch(Exception invalid){return false;}
  }
  private static int port(URI uri){return uri.getPort()==-1?("https".equalsIgnoreCase(uri.getScheme())?443:80):uri.getPort();}
  private static String path(URI uri){String path=uri.getRawPath();return path==null||path.isEmpty()?"/":path;}
}
