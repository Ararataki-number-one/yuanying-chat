package local.pocketchat;

import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;
import java.net.URI;

/** The app hosts the original website; native code observes rather than sends. */
final class BrowserRuntimePolicy {
  private static final Set<String> ACTIONS=new HashSet<>(Arrays.asList(
    "inspect","web-inspect","observe-install","web-transcript","transcript",
    "poll","latest","chats","page-state","page-content","page-timing",
    "page-recover","page-restore","attachment-state",
    "file-prepare","file-point","file-followup"));
  static boolean usesGecko(){return true;}
  static boolean originalWebsite(){return true;}
  static boolean allows(String action){return ACTIONS.contains(action);}
  static boolean restoresPending(String savedEngine,String jobEngine,String kind){return "web".equals(kind)&&("gecko".equals(jobEngine)||jobEngine.isEmpty()&&"gecko".equals(savedEngine));}
  static String websiteActionMessage(){return "请在 ChatGPT 原网页中操作";}
  static boolean leftConversation(String from,String to,boolean composer,boolean hasMessages){
    try{
      URI before=URI.create(from),after=URI.create(to);
      if(!official(before)||!official(after))return false;
      String old=conversationId(before.getRawPath()),next=conversationId(after.getRawPath());
      if(old.isEmpty())return false; // A first send may legitimately allocate /c/id.
      if(!next.isEmpty())return !old.equals(next);
      return after.getRawPath().matches("/(g/[^/]+/?)?")&&composer&&!hasMessages;
    }catch(IllegalArgumentException failure){return false;}
  }
  static boolean official(URI uri){return "https".equals(uri.getScheme())&&"chatgpt.com".equals(uri.getHost())&&uri.getUserInfo()==null&&(uri.getPort()<0||uri.getPort()==443);}
  static String conversationId(String path){return path!=null&&path.matches("/(g/[^/]+/)?c/[^/]+/?")?path.replaceFirst("^/(g/[^/]+/)?c/","").replaceFirst("/$",""):"";}
}
