package local.pocketchat;

import java.util.*;

/** Small bounded rounds; the caller rechecks activity before every request and switch. */
final class NetworkOptimizationPolicy {
  static final long ACTIVE_INTERVAL=120000, BACKGROUND_INTERVAL=180000, SCAN_INTERVAL=120000;
  static String label(String mode){return "latency".equals(mode)?"自动优选":"manual".equals(mode)?"手动指定":"random".equals(mode)?"自动随机":"自动选择";}
  static boolean pooled(String mode){return "random".equals(mode)||"latency".equals(mode);}
  static List<String> batch(List<String> nodes,List<String> ranked,String current,int cursor){
    LinkedHashSet<String> chosen=new LinkedHashSet<>();if(nodes.contains(current))chosen.add(current);
    for(String name:ranked){if(chosen.size()>=3)break;if(nodes.contains(name))chosen.add(name);}
    for(int i=0;i<nodes.size()&&chosen.size()<4;i++)chosen.add(nodes.get(Math.floorMod(cursor+i,nodes.size())));
    return new ArrayList<>(chosen);
  }
  /** Keep one exploration slot and one confirmation slot: a new fast node must not
   * wait behind mature slow nodes' sample-count bonus for an entire pool rotation. */
  static List<String> adaptiveBatch(List<String> nodes,List<String> ranked,String current,int cursor,Map<String,Integer> samples,Map<String,Integer> delays){
    LinkedHashSet<String> chosen=new LinkedHashSet<>();if(nodes.contains(current))chosen.add(current);
    for(String name:ranked)if(nodes.contains(name)&&!name.equals(current)){chosen.add(name);break;}
    String promising="";int fastest=Integer.MAX_VALUE;
    for(String name:nodes){int count=samples.getOrDefault(name,0),delay=delays.getOrDefault(name,-1);if(!chosen.contains(name)&&count>0&&count<3&&delay>0&&delay<fastest){promising=name;fastest=delay;}}
    if(!promising.isEmpty())chosen.add(promising);
    // Always reserve exploration even when the top candidates already have evidence.
    for(int i=0;i<nodes.size();i++){String name=nodes.get(Math.floorMod(cursor+i,nodes.size()));if(chosen.add(name))break;}
    for(String name:ranked){if(chosen.size()>=4)break;if(nodes.contains(name))chosen.add(name);}
    return new ArrayList<>(chosen);
  }
  static long scanInterval(int rounds){return rounds<3?60000:SCAN_INTERVAL;}
  /** Anonymous website probes are scarce; compare the active route and one challenger. */
  static List<String> websiteBatch(List<String> batch,List<String> ranked,String current){
    LinkedHashSet<String> chosen=new LinkedHashSet<>();if(batch.contains(current))chosen.add(current);
    for(String name:ranked)if(batch.contains(name)&&!name.equals(current)){chosen.add(name);break;}
    return new ArrayList<>(chosen);
  }
  static boolean websiteDue(String status,long at,long now){long ttl="restricted".equals(status)||"unsupported".equals(status)?300000:"ok".equals(status)?120000:60000;return at<=0||now<at-60000||now-at>=ttl;}
  static boolean websiteComparable(String status,long at,long now,int samples,int latest){return "ok".equals(status)&&at>0&&now>=at&&now-at<=300000&&samples>=3&&latest>0;}
  static String websiteStatus(int code){return code>=200&&code<400?"ok":code==401||code==403||code==429?"restricted":code==405||code==501?"unsupported":"http-error";}
}
