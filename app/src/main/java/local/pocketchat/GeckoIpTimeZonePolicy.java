package local.pocketchat;

import java.io.IOException;
import java.net.Inet6Address;
import java.net.InetAddress;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.json.*;

/** Strict service observation, not a promise of physical location or Worker isolation. */
final class GeckoIpTimeZonePolicy {
  static final String SOURCE="https://ipwho.is/?fields=success,ip,timezone.id";
  static final int MAX_BYTES=8192;
  static final class Observation {
    final String ip,zoneId,routeStamp;final long observedAt;
    private Observation(String ip,String zoneId,String routeStamp,long observedAt){this.ip=ip;this.zoneId=zoneId;this.routeStamp=routeStamp;this.observedAt=observedAt;}
    GeckoTimeZoneSpec effective(){return GeckoTimeZoneSpec.of(zoneId);}
    JSONObject json(){return J.obj("schema",1,"source",SOURCE,"ip",ip,"zoneId",zoneId,"routeStamp",routeStamp,"observedAt",observedAt);}
  }
  static boolean token(String value){return value!=null&&value.matches("[0-9a-f]{64}");}
  static Observation parse(String raw,String requestToken,String routeStamp,long observedAt)throws IOException{
    if(raw==null||raw.length()>MAX_BYTES||!token(requestToken)||!token(routeStamp)||observedAt<0)throw invalid();
    try{
      JSONObject envelope=GeckoTimeZonePolicy.object(raw.getBytes(StandardCharsets.UTF_8),MAX_BYTES);
      GeckoTimeZonePolicy.keys(envelope,"schema","status","requestToken","routeStamp","source","body");
      if(GeckoTimeZonePolicy.integer(envelope,"schema")!=1||!"observed".equals(envelope.opt("status"))||!requestToken.equals(envelope.opt("requestToken"))||!routeStamp.equals(envelope.opt("routeStamp"))||!SOURCE.equals(envelope.opt("source"))||!(envelope.opt("body") instanceof String))throw invalid();
      String body=envelope.getString("body");JSONObject value=GeckoTimeZonePolicy.object(body.getBytes(StandardCharsets.UTF_8),MAX_BYTES);
      GeckoTimeZonePolicy.keys(value,"success","ip","timezone");
      if(!Boolean.TRUE.equals(value.opt("success"))||!(value.opt("ip") instanceof String)||!(value.opt("timezone") instanceof JSONObject))throw invalid();
      JSONObject zone=value.getJSONObject("timezone");GeckoTimeZonePolicy.keys(zone,"id");
      if(!(zone.opt("id") instanceof String))throw invalid();String named=zone.getString("id");GeckoTimeZoneSpec effective=GeckoTimeZoneSpec.of(named);if(effective.followsSystem()||effective.followsIp())throw invalid();
      return new Observation(publicIp(value.getString("ip")),named,routeStamp,observedAt);
    }catch(IOException invalid){throw invalid;}catch(Exception invalid){throw new IOException("出口 IP 或 IANA 时区响应无效，尚未匹配时区",invalid);}
  }
  /** Reading historical metadata never makes it a current route observation. */
  static Observation historical(JSONObject value)throws IOException{
    try{
      GeckoTimeZonePolicy.keys(value,"schema","source","ip","zoneId","routeStamp","observedAt");
      if(GeckoTimeZonePolicy.integer(value,"schema")!=1||!SOURCE.equals(value.opt("source"))||!(value.opt("ip") instanceof String)||!(value.opt("zoneId") instanceof String)||!(value.opt("routeStamp") instanceof String)||!token(value.getString("routeStamp")))throw invalid();
      String zone=value.getString("zoneId");if(GeckoTimeZoneSpec.of(zone).followsSystem())throw invalid();long at=GeckoTimeZonePolicy.integer(value,"observedAt");if(at<0)throw invalid();
      return new Observation(publicIp(value.getString("ip")),zone,value.getString("routeStamp"),at);
    }catch(IOException invalid){throw invalid;}catch(Exception invalid){throw new IOException("历史出口时区记录无效，原文件保留",invalid);}
  }
  static IOException invalid(){return new IOException("出口 IP 或 IANA 时区未被当前线路确认，尚未匹配时区");}
  /** Literal-only parsing: this method never resolves a service-supplied hostname. */
  static String publicIp(String value)throws IOException{
    if(value==null||value.isEmpty()||value.length()>64||!value.equals(value.trim()))throw invalid();
    if(value.indexOf(':')<0){
      String[] parts=value.split("\\.",-1);if(parts.length!=4)throw invalid();int[] b=new int[4];
      for(int i=0;i<4;i++){if(!parts[i].matches("0|[1-9][0-9]{0,2}"))throw invalid();b[i]=Integer.parseInt(parts[i]);if(b[i]>255)throw invalid();}
      int a=b[0],c=b[1],d=b[2];
      if(a==0||a==10||a==127||a>=224||a==169&&c==254||a==172&&c>=16&&c<=31||a==192&&c==168||a==100&&c>=64&&c<=127
          ||a==192&&c==0&&(d==0||d==2)||a==198&&(c==18||c==19)||a==198&&c==51&&d==100||a==203&&c==0&&d==113)throw invalid();
      return value;
    }
    if(!value.matches("[0-9a-fA-F:]+"))throw invalid();
    try{
      InetAddress parsed=InetAddress.getByName(value);if(!(parsed instanceof Inet6Address))throw invalid();byte[] b=parsed.getAddress();
      if(parsed.isAnyLocalAddress()||parsed.isLoopbackAddress()||parsed.isLinkLocalAddress()||parsed.isSiteLocalAddress()||parsed.isMulticastAddress()||(b[0]&0xe0)!=0x20
          ||(b[0]&255)==0x20&&(b[1]&255)==1&&(b[2]&255)==0x0d&&(b[3]&255)==0xb8)throw invalid();
      return parsed.getHostAddress().toLowerCase(Locale.ROOT);
    }catch(IOException invalid){throw invalid;}catch(Exception invalid){throw new IOException("出口 IP 地址无效",invalid);}
  }
}
