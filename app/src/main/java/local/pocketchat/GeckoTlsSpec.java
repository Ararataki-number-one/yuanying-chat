package local.pocketchat;

import java.util.*;
import org.json.JSONObject;

/** Desired protocol policy, independent from native readback and wire evidence. */
final class GeckoTlsSpec {
  static final String DEFAULT="default",TLS13="tls13";
  final String mode;
  private GeckoTlsSpec(String mode){this.mode=mode;}
  static GeckoTlsSpec defaults(){return new GeckoTlsSpec(DEFAULT);}
  static GeckoTlsSpec of(String mode){
    if(DEFAULT.equals(mode))return defaults();
    if(TLS13.equals(mode))return new GeckoTlsSpec(TLS13);
    throw new IllegalArgumentException("请选择内核默认或仅 TLS 1.3");
  }
  boolean isDefault(){return DEFAULT.equals(mode);}
  boolean requiresTls13(){return TLS13.equals(mode);}
  String label(){return isDefault()?"内核默认":"仅 TLS 1.3";}
  JSONObject json(){return J.obj("schema",1,"engine","gecko","mode",mode);}
  static GeckoTlsSpec from(JSONObject value){
    if(value==null)throw new IllegalArgumentException("缺少 TLS 配置");
    Set<String> keys=new HashSet<>();for(Iterator<String> i=value.keys();i.hasNext();)keys.add(i.next());
    Object schema=value.opt("schema"),mode=value.opt("mode");
    if(!keys.equals(new HashSet<>(Arrays.asList("schema","engine","mode")))||!(schema instanceof Integer||schema instanceof Long)
        ||((Number)schema).longValue()!=1||!"gecko".equals(value.opt("engine"))||!(mode instanceof String))throw new IllegalArgumentException("TLS 配置版本或结构不受支持");
    return of((String)mode);
  }
  @Override public boolean equals(Object value){return value instanceof GeckoTlsSpec&&mode.equals(((GeckoTlsSpec)value).mode);}
  @Override public int hashCode(){return mode.hashCode();}
}
