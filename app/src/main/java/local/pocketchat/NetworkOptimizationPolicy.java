package local.pocketchat;

import java.util.*;

/** Small bounded rounds; the caller rechecks activity before every request and switch. */
final class NetworkOptimizationPolicy {
  static final long ACTIVE_INTERVAL=60000, BACKGROUND_INTERVAL=180000, SCAN_INTERVAL=120000;
  static String label(String mode){return "latency".equals(mode)?"低延迟优先":"manual".equals(mode)?"手动指定":"random".equals(mode)?"自动随机":"自动选择";}
  static boolean pooled(String mode){return "random".equals(mode)||"latency".equals(mode);}
  static List<String> batch(List<String> nodes,List<String> ranked,String current,int cursor){
    LinkedHashSet<String> chosen=new LinkedHashSet<>();if(nodes.contains(current))chosen.add(current);
    for(String name:ranked){if(chosen.size()>=3)break;if(nodes.contains(name))chosen.add(name);}
    for(int i=0;i<nodes.size()&&chosen.size()<4;i++)chosen.add(nodes.get(Math.floorMod(cursor+i,nodes.size())));
    return new ArrayList<>(chosen);
  }
  static String websiteStatus(int code){return code>=200&&code<400?"ok":code==401||code==403||code==429?"restricted":code==405||code==501?"unsupported":"http-error";}
}
