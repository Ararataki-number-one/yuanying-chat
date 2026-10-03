package local.pocketchat;

import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

/** Host checks: real UA policy and viewport script, with no Android account session. */
public final class BrowserDisplayPolicyTest {
  static final List<String> checks=new ArrayList<>();
  static void check(String name,boolean ok){if(!ok)throw new AssertionError(name);checks.add(name);}
  public static void main(String[] args)throws Exception{
    String mobile="Mozilla/5.0 (Linux; Android 15; Pixel 9 Build/ABC; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/129.0.6668.100 Mobile Safari/537.36";
    check("Compatibility mobile mode preserves the system UA",BrowserDisplay.agent(mobile,0,false).equals(mobile));
    for(int level=0;level<3;level++){
      String desktop=BrowserDisplay.agent(mobile,level,true),phone=BrowserDisplay.agent(mobile,level,false);
      check("Desktop mode removes mobile and embedded markers at protection "+level,!desktop.contains("Mobile")&&!desktop.contains("Android")&&!desktop.contains("wv")&&!desktop.contains("Version/4.0"));
      check("Desktop mode uses the installed Chromium version at protection "+level,desktop.contains("Chrome/"+(level==0?"129.0.6668.100":"129.0.0.0")));
      check("Returning to phone mode restores a mobile agent at protection "+level,phone.contains("Mobile")&&phone.contains("Android"));
      check("Mode recomputation cannot retain an earlier desktop UA at protection "+level,phone.equals(BrowserDisplay.agent(mobile,level,false)));
    }
    String chromium="Mozilla/5.0 Chromium/140.0.7339.12 Mobile";
    check("Chromium spelling retains the real major version",BrowserDisplay.agent(chromium,1,true).contains("Chrome/140.0.0.0"));
    check("An unknown engine does not fabricate a Chrome version",BrowserDisplay.agent("unknown-browser",1,true).equals("unknown-browser"));
    check("Human-readable labels distinguish the two choices",BrowserDisplay.label(false).equals("手机版")&&BrowserDisplay.label(true).equals("电脑版"));
    check("An idle window can change display mode",!BrowserDisplay.busy(false,false,false,false,false));
    for(int i=0;i<5;i++){boolean[] flags=new boolean[5];flags[i]=true;check("Only user work and replies block display changes, flag "+i,BrowserDisplay.busy(flags[0],flags[1],flags[2],flags[3],flags[4])==(i==0||i==4));}
    check("Viewport policy provides desktop layout width",BrowserDisplay.viewportScript().contains("width=1024"));
    if(args.length>0)Files.write(Paths.get(args[0]),BrowserDisplay.viewportScript().getBytes(StandardCharsets.UTF_8));
    StringBuilder out=new StringBuilder("{\"passed\":"+checks.size()+",\"total\":"+checks.size()+",\"checks\":[");
    for(int i=0;i<checks.size();i++){if(i>0)out.append(',');out.append("{\"name\":\"").append(checks.get(i)).append("\",\"pass\":true}");}System.out.println(out.append("]}"));
  }
}
