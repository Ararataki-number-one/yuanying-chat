package local.pocketchat;

import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;

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
}
