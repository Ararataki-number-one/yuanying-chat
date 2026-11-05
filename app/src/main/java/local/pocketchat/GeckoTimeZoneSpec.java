package local.pocketchat;

import java.time.Instant;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.util.*;
import org.json.JSONObject;

/** Desired per-environment policy. IP selection has no native zone until a
 * fresh lookup through this browser's exact admitted route has completed. */
final class GeckoTimeZoneSpec {
  static final int SCHEMA=2;
  static final String ENGINE="gecko";
  static final String IP="ip",SYSTEM="system",IANA="iana";
  final String mode,zoneId;
  private GeckoTimeZoneSpec(String mode,String zoneId){this.mode=mode;this.zoneId=zoneId;}
  static GeckoTimeZoneSpec automatic(){return new GeckoTimeZoneSpec(IP,"");}
  static GeckoTimeZoneSpec system(){return new GeckoTimeZoneSpec(SYSTEM,"");}
  static GeckoTimeZoneSpec of(String zoneId){
    if(zoneId==null||zoneId.length()>80||!zoneId.equals(zoneId.trim()))throw new IllegalArgumentException("请选择系统、UTC 或有效的 IANA 时区");
    if(zoneId.isEmpty())return system();
    // ZoneId.of alone accepts synthetic fixed offsets such as UTC+08:00.
    // Named TZDB regions/links retain their real historical and DST rules.
    if(!zoneId.matches("[A-Za-z0-9_+./-]+")||!ZoneId.getAvailableZoneIds().contains(zoneId))throw new IllegalArgumentException("请输入有效的 IANA 时区，例如 Asia/Shanghai");
    ZoneId.of(zoneId).getRules();return new GeckoTimeZoneSpec(IANA,zoneId);
  }
  static GeckoTimeZoneSpec from(JSONObject value){
    if(value==null)throw new IllegalArgumentException("缺少时区配置");
    Set<String> keys=new HashSet<>();for(Iterator<String> i=value.keys();i.hasNext();)keys.add(i.next());
    Object schema=value.opt("schema"),zone=value.opt("zoneId");
    if(!(schema instanceof Integer||schema instanceof Long)||!ENGINE.equals(value.opt("engine"))||!(zone instanceof String))throw new IllegalArgumentException("时区配置版本或结构不受支持");
    // An old empty selection may have been explicitly saved as system. It is
    // preserved; only a missing/new environment receives the new IP default.
    if(((Number)schema).longValue()==1&&keys.equals(new HashSet<>(Arrays.asList("schema","engine","zoneId"))))return of((String)zone);
    if(((Number)schema).longValue()!=SCHEMA||!keys.equals(new HashSet<>(Arrays.asList("schema","engine","mode","zoneId")))||!(value.opt("mode") instanceof String))throw new IllegalArgumentException("时区配置版本或结构不受支持");
    String mode=(String)value.opt("mode");
    if(IP.equals(mode)&&((String)zone).isEmpty())return automatic();
    if(SYSTEM.equals(mode)&&((String)zone).isEmpty())return system();
    if(IANA.equals(mode)&&!((String)zone).isEmpty())return of((String)zone);
    throw new IllegalArgumentException("时区模式与名称不一致");
  }
  boolean followsIp(){return IP.equals(mode);}
  boolean followsSystem(){return SYSTEM.equals(mode);}
  String label(){return followsIp()?"跟随当前出口 IP 时区":followsSystem()?"跟随系统时区":zoneId;}
  ZoneOffset offsetAt(Instant instant){if(followsIp())throw new IllegalStateException("出口 IP 时区尚未解析");return (followsSystem()?ZoneId.systemDefault():ZoneId.of(zoneId)).getRules().getOffset(Objects.requireNonNull(instant));}
  JSONObject json(){return J.obj("schema",SCHEMA,"engine",ENGINE,"mode",mode,"zoneId",zoneId);}
  @Override public boolean equals(Object value){return value instanceof GeckoTimeZoneSpec&&mode.equals(((GeckoTimeZoneSpec)value).mode)&&zoneId.equals(((GeckoTimeZoneSpec)value).zoneId);}
  @Override public int hashCode(){return Objects.hash(mode,zoneId);}
}
