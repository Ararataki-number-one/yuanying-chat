package local.pocketchat;

import java.net.URI;

/** A blob can be read only by the document origin that created it. */
final class GeckoDownloadNavigation {
  private GeckoDownloadNavigation() {}

  static boolean sameOriginBlob(String page,String target){
    if(target==null||!target.startsWith("blob:")||!BrowserAddressPolicy.allowed(page)||!BrowserAddressPolicy.allowed(target.substring(5)))return false;
    try{
      URI source=new URI(page),blob=new URI(target.substring(5));
      return source.getHost()!=null&&blob.getHost()!=null
          &&source.getScheme().equalsIgnoreCase(blob.getScheme())
          &&source.getHost().equalsIgnoreCase(blob.getHost())
          &&port(source)==port(blob);
    }catch(Exception invalid){return false;}
  }

  private static int port(URI uri){return uri.getPort()>=0?uri.getPort():"https".equalsIgnoreCase(uri.getScheme())?443:80;}
}
