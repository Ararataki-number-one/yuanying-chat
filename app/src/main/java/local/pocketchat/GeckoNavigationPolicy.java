package local.pocketchat;

import java.net.URI;

/** Public website navigation is separate from the ChatGPT automation origin. */
final class GeckoNavigationPolicy {
  private GeckoNavigationPolicy() {}
  static String home(){return BrowserAddressPolicy.home();}
  static String normalizeInput(String input){return BrowserAddressPolicy.normalizeInput(input);}
  static boolean publicWeb(String url){return BrowserAddressPolicy.allowed(url);}
  /** A new-window blob belongs to the current public document's origin. */
  static boolean blobFrom(String target,String page){
    if(target==null||!target.startsWith("blob:")||!publicWeb(page))return false;
    String source=target.substring(5);
    if(!publicWeb(source))return false;
    try{
      URI a=new URI(source),b=new URI(page);
      return a.getScheme().equalsIgnoreCase(b.getScheme())&&a.getHost().equalsIgnoreCase(b.getHost())&&port(a)==port(b);
    }catch(Exception invalid){return false;}
  }
  /** Classify a file target only after the caller verifies the current page and user action. */
  static boolean chatDownloadPopup(String target,String source){
    URI page=chatHttps(source);
    if(page==null||!path(page).matches("/(g/[A-Za-z0-9_-]{1,160}/)?c/[A-Za-z0-9_-]{1,160}/?"))return false;
    return chatDownloadEndpoint(target);
  }
  static boolean chatDownloadEndpoint(String target){
    URI file=chatHttps(target);
    if(file==null||file.getRawFragment()!=null)return false;
    String filePath=path(file);
    if(filePath.equals("/backend-api/estuary/content"))return signedFileQuery(file.getRawQuery());
    // Bare file resources can return metadata. Require the explicit download operation.
    return filePath.matches("/backend-api/files/[A-Za-z0-9_-]{1,160}/download");
  }
  private static URI chatHttps(String value){
    if(value==null||value.length()>8192)return null;
    try{
      URI uri=URI.create(value);
      String authority=uri.getRawAuthority();
      return "https".equalsIgnoreCase(uri.getScheme())
          &&("chatgpt.com".equalsIgnoreCase(authority)||"chatgpt.com:443".equalsIgnoreCase(authority))?uri:null;
    }catch(IllegalArgumentException invalid){return null;}
  }
  private static boolean signedFileQuery(String query){
    if(query==null||query.indexOf(';')>=0)return false;
    String id=null,signature=null;
    for(String parameter:query.split("&",-1)){
      int equals=parameter.indexOf('=');
      if(equals<=0)return false;
      String key=parameter.substring(0,equals),value=parameter.substring(equals+1);
      if(!key.matches("[A-Za-z0-9_-]{1,32}"))return false;
      if(key.equalsIgnoreCase("id")){
        if(id!=null||!key.equals("id"))return false;
        id=value;
      }else if(key.equalsIgnoreCase("sig")){
        if(signature!=null||!key.equals("sig"))return false;
        signature=value;
      }
    }
    return id!=null&&id.matches("file[-_][A-Za-z0-9_-]{4,160}")
        &&signature!=null&&signature.matches("[A-Za-z0-9_-]{32,256}");
  }
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
