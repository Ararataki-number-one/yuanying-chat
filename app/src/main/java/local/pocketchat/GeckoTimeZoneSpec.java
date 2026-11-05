package local.pocketchat;

import java.time.Instant;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.util.*;
import org.json.JSONObject;

/** Desired per-environment Gecko setting. Empty means reset the BC override;
 * it does not persist today's phone zone or pretend RFP has accepted it. */
final class GeckoTimeZoneSpec {
  static final int SCHEMA=1;
  static final String ENGINE="gecko";
  final String zoneId;
  private GeckoTimeZoneSpec(String zoneId){this.zoneId=zoneId;}
  static GeckoTimeZoneSpec system(){return new GeckoTimeZoneSpec("");}
  static GeckoTimeZoneSpec of(String zoneId){
    if(zoneId==null||zoneId.length()>80||!zoneId.equals(zoneId.trim()))throw new IllegalArgumentException("请选择系统、UTC 或有效的 IANA 时区");
    if(zoneId.isEmpty())return system();
    // ZoneId.of alone accepts synthetic fixed offsets such as UTC+08:00.
    // Named TZDB regions/links retain their real historical and DST rules.
    if(!zoneId.matches("[A-Za-z0-9_+./-]+")||!ZoneId.getAvailableZoneIds().contains(zoneId))throw new IllegalArgumentException("请输入有效的 IANA 时区，例如 Asia/Shanghai");
    ZoneId.of(zoneId).getRules();return new GeckoTimeZoneSpec(zoneId);
  }
  static GeckoTimeZoneSpec from(JSONObject value){
    if(value==null)throw new IllegalArgumentException("缺少时区配置");
    Set<String> keys=new HashSet<>();for(Iterator<String> i=value.keys();i.hasNext();)keys.add(i.next());
    Object schema=value.opt("schema"),zone=value.opt("zoneId");
    if(!keys.equals(new HashSet<>(Arrays.asList("schema","engine","zoneId")))
        ||!(schema instanceof Integer||schema instanceof Long)||((Number)schema).longValue()!=SCHEMA
        ||!ENGINE.equals(value.opt("engine"))||!(zone instanceof String))throw new IllegalArgumentException("时区配置版本或结构不受支持");
    return of((String)zone);
  }
  boolean followsSystem(){return zoneId.isEmpty();}
  String label(){return followsSystem()?"跟随系统时区":zoneId;}
  ZoneOffset offsetAt(Instant instant){return (followsSystem()?ZoneId.systemDefault():ZoneId.of(zoneId)).getRules().getOffset(Objects.requireNonNull(instant));}
  JSONObject json(){return J.obj("schema",SCHEMA,"engine",ENGINE,"zoneId",zoneId);}
  @Override public boolean equals(Object value){return value instanceof GeckoTimeZoneSpec&&zoneId.equals(((GeckoTimeZoneSpec)value).zoneId);}
  @Override public int hashCode(){return zoneId.hashCode();}
}
