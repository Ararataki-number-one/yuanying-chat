package local.pocketchat;

import java.util.*;

/** Strict, portable interpretation of one native measurement, never inferred from history. */
final class LatencyProbePolicy {
  static final Set<String> REQUIRED_FIELDS=new LinkedHashSet<>(Arrays.asList("schema","kind","firstMs","warmMs","totalMs","warmAttempted","warmSucceeded","secondConnectionReused","warmError","firstStatus","secondStatus"));
  static final Set<String> PHASE_FIELDS=new LinkedHashSet<>(Arrays.asList("phaseSchema","chainMs","tlsMs","responseWaitMs","dnsMs"));
  static final Set<String> FIELDS=new LinkedHashSet<>(REQUIRED_FIELDS);static{FIELDS.add("dialCount");FIELDS.add("attempts");FIELDS.addAll(PHASE_FIELDS);}
  static final class Trace {
    final String kind,error;final long first,warm,total;final boolean attempted,succeeded,reused;final int firstStatus,secondStatus,dials,requests;
    Trace(String kind,String error,long first,long warm,long total,boolean attempted,boolean succeeded,boolean reused,int firstStatus,int secondStatus,int dials,int requests,Map<String,Object> phases){this.phases=Collections.unmodifiableMap(new LinkedHashMap<>(phases));this.kind=kind;this.error=error;this.first=first;this.warm=warm;this.total=total;this.attempted=attempted;this.succeeded=succeeded;this.reused=reused;this.firstStatus=firstStatus;this.secondStatus=secondStatus;this.dials=dials;this.requests=requests;}
    final Map<String,Object> phases;
    boolean comparable(){return "warm".equals(kind)&&attempted&&succeeded&&reused;}
    Map<String,Object> values(){Map<String,Object> m=new LinkedHashMap<>();m.put("schema",1);m.put("kind",kind);m.put("firstMs",first);m.put("warmMs",warm);m.put("totalMs",total);m.put("warmAttempted",attempted);m.put("warmSucceeded",succeeded);m.put("secondConnectionReused",reused);m.put("warmError",error);m.put("firstStatus",firstStatus);m.put("secondStatus",secondStatus);if(dials>=0)m.put("dialCount",dials);if(requests>=0)m.put("attempts",requests);m.putAll(phases);return m;}
  }
  static Trace parse(Map<String,Object> m,int delay){
    if(m==null||delay<=0||integer(m.get("schema"))!=1)return null;
    for(String key:REQUIRED_FIELDS)if(!m.containsKey(key))return null;
    Object k=m.get("kind"),e=m.get("warmError");if(!(k instanceof String)||!(e instanceof String))return null;
    String kind=(String)k,error=(String)e;if(!Arrays.asList("warm","cold-retest","cold-fallback","first").contains(kind)||!Arrays.asList("","cancelled","timeout","transport").contains(error))return null;
    for(String key:new String[]{"warmAttempted","warmSucceeded","secondConnectionReused"})if(!(m.get(key) instanceof Boolean))return null;
    long first=integer(m.get("firstMs")),warm=integer(m.get("warmMs")),total=integer(m.get("totalMs")),fs=integer(m.get("firstStatus")),ss=integer(m.get("secondStatus"));
    boolean attempted=(Boolean)m.get("warmAttempted"),succeeded=(Boolean)m.get("warmSucceeded"),reused=(Boolean)m.get("secondConnectionReused");
    long dials=m.containsKey("dialCount")?integer(m.get("dialCount")):-1,requests=m.containsKey("attempts")?integer(m.get("attempts")):-1;
    if(m.containsKey("dialCount")&&(dials<0||dials>128)||m.containsKey("attempts")&&(requests<0||requests>128))return null;
    if(first<0||first>120000||total<first||total>120000||warm< -1||warm>120000||warm>total||fs<100||fs>599||ss!=0&&(ss<100||ss>599))return null;
    if(!attempted&&(warm!=-1||succeeded||reused||ss!=0||!error.isEmpty()))return null;
    if(attempted&&warm<0)return null;
    if(succeeded&&(ss!=204||!error.isEmpty()||delay!=warm))return null;
    if("warm".equals(kind)){if(!attempted||!succeeded||!reused)return null;}
    else if("cold-retest".equals(kind)){if(!attempted||!succeeded||reused)return null;}
    else if("cold-fallback".equals(kind)){if(!attempted||succeeded||delay!=first||fs!=204||ss==204&&error.isEmpty())return null;}
    else if(attempted||delay!=first||fs!=204)return null;
    Map<String,Object> phases=new LinkedHashMap<>();
    boolean hasPhases=false;for(String key:PHASE_FIELDS)if(m.containsKey(key))hasPhases=true;
    if(hasPhases){
      if(integer(m.get("phaseSchema"))!=1||integer(m.get("dnsMs"))!=-1)return null;
      phases.put("phaseSchema",1);
      for(String key:Arrays.asList("chainMs","tlsMs","responseWaitMs")){long value=integer(m.get(key));if(value< -1||value>first)return null;phases.put(key,value);}
      // Remote DNS is part of SOCKS CONNECT and cannot be timed independently.
      phases.put("dnsMs",-1L);
    }
    return new Trace(kind,error,first,warm,total,attempted,succeeded,reused,(int)fs,(int)ss,(int)dials,(int)requests,phases);
  }
  static long integer(Object value){if(!(value instanceof Byte||value instanceof Short||value instanceof Integer||value instanceof Long))return Long.MIN_VALUE;return ((Number)value).longValue();}
  static String label(String kind,int delay){return ("first".equals(kind)||"cold-fallback".equals(kind)?"首次 ":"cold-retest".equals(kind)?"复测 ":"")+delay+" ms";}
  static String error(String value,int status){if("timeout".equals(value))return "复测超时";if("cancelled".equals(value))return "复测已取消";if("transport".equals(value))return "复测连接中断";return status>0&&status!=204?"复测响应未通过":"未取得可用复测结果";}
  static boolean comparable(String kind,int delay){return delay>0&&"warm".equals(kind);}
  static boolean currentSample(String origin,String route,String currentRoute){return origin.isEmpty()||"current".equals(origin)&&route.equals(currentRoute);}
  static final class Binding {
    final String proxy,entry,epoch;final long route,measurement;final int controller;final boolean current;
    Binding(String proxy,String entry,String epoch,long route,long measurement,int controller){this.proxy=proxy;this.entry=entry;this.epoch=epoch;this.route=route;this.measurement=measurement;this.controller=controller;current="FixedExit".equals(proxy);}
    boolean matches(String epoch,long route,int controller,String currentEntry){return this.epoch.equals(epoch)&&this.route==route&&this.controller==controller&&(!current||entry.equals(currentEntry));}
  }
}
