package local.pocketchat;

import java.util.*;
import org.json.JSONObject;

/** A runtime-wide upper-bound request, never an invented physical CPU count. */
final class GeckoCpuSpec {
  static final String AUTOMATIC="automatic";
  final String mode;final Integer cap;
  private GeckoCpuSpec(String mode,Integer cap){this.mode=mode;this.cap=cap;}
  static GeckoCpuSpec automatic(){return new GeckoCpuSpec(AUTOMATIC,null);}
  static GeckoCpuSpec of(String mode){
    if(AUTOMATIC.equals(mode))return automatic();
    if("1".equals(mode))return new GeckoCpuSpec("1",1);
    if("2".equals(mode))return new GeckoCpuSpec("2",2);
    throw new IllegalArgumentException("请选择内核默认、最多 1 或最多 2");
  }
  boolean isAutomatic(){return cap==null;}
  Integer capOrNull(){return cap;}
  String label(){return isAutomatic()?"内核默认":"最多 "+cap;}
  JSONObject json(){return J.obj("schema",1,"engine","gecko","mode",mode);}
  static GeckoCpuSpec from(JSONObject value){
    if(value==null)throw new IllegalArgumentException("缺少 CPU 上限配置");
    Set<String> keys=new HashSet<>();for(Iterator<String> i=value.keys();i.hasNext();)keys.add(i.next());
    Object schema=value.opt("schema"),mode=value.opt("mode");
    if(!keys.equals(new HashSet<>(Arrays.asList("schema","engine","mode")))||!(schema instanceof Integer||schema instanceof Long)
        ||((Number)schema).longValue()!=1||!"gecko".equals(value.opt("engine"))||!(mode instanceof String))throw new IllegalArgumentException("CPU 上限配置版本或结构不受支持");
    return of((String)mode);
  }
  @Override public boolean equals(Object value){return value instanceof GeckoCpuSpec&&mode.equals(((GeckoCpuSpec)value).mode);}
  @Override public int hashCode(){return mode.hashCode();}
}
