package local.pocketchat;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.UUID;
import org.json.*;

/** Encrypted journal payload. No browser data is copied into this plan. */
final class EnvironmentResetPlan {
  static final int LIMIT=20*1024*1024;
  final EnvironmentSpec before,after;
  final EnvironmentSpec.Identity next;
  private final String pending;
  private EnvironmentResetPlan(EnvironmentSpec before,EnvironmentSpec after,JSONObject pending)throws IOException{
    this.before=before;
    if(before.identity.generation==Integer.MAX_VALUE)throw new IOException("环境代际已达到上限");next=new EnvironmentSpec.Identity(before.identity.slot,before.identity.generation+1,before.identity.environmentId);
    this.after=after;this.pending=pending==null?"":pending.toString();
    if(after!=null&&(!after.identity.equals(next)||after.appliedRevision!=0||after.observedRevision!=0
        ||!new EnvironmentSpec.Configuration(after.desired().browser(),before.desired().network).equals(before.desired())))throw new IOException("登录重置配置记录不匹配");
    if((after==null)!=(pending==null))throw new IOException("登录重置阶段无效");
    if(pending!=null&&pending.length()>0)validatePending(pending,next);
  }
  static EnvironmentResetPlan start(EnvironmentSpec before)throws IOException{return new EnvironmentResetPlan(before,null,null);}
  boolean frozen(){return after!=null;}
  JSONObject pending(){return pending.isEmpty()?new JSONObject():J.parse(pending);}
  EnvironmentResetPlan freeze(EnvironmentSpec.NetworkBinding route,JSONObject queued)throws Exception{
    EnvironmentSpec configured=before.withDesired(before.desiredRevision,new EnvironmentSpec.Configuration(before.desired().browser(),route));
    return new EnvironmentResetPlan(before,configured.afterLoginReset(next),rebind(queued,before.identity,next));
  }
  static JSONObject rebind(JSONObject value,EnvironmentSpec.Identity old,EnvironmentSpec.Identity next)throws Exception{
    JSONObject result=new JSONObject(value.toString());if(result.length()==0)return result;
    if(result.optJSONObject("config")==null||!("apply".equals(result.optString("action"))||"external".equals(result.optString("action"))))throw new IOException("待应用网络设置无效");
    JSONObject marker=result.optJSONObject("environmentIntent");
    if(marker!=null){
      validatePending(result,old);
      marker.put("identity",next.json());
    }else{if(result.has("environmentIntent"))throw new IOException("待应用网络身份无效");result.put("environmentIntent",J.obj("schema",1,"id",UUID.randomUUID().toString().replace("-",""),"identity",next.json(),"state","ready"));}
    result.remove("baselineLineage");return result;
  }
  private static void validatePending(JSONObject value,EnvironmentSpec.Identity expected)throws IOException{
    JSONObject marker=value.optJSONObject("environmentIntent"),id=marker==null?null:marker.optJSONObject("identity");
    if(value.optJSONObject("config")==null||!("external".equals(value.optString("action"))||"apply".equals(value.optString("action")))||marker==null||!Integer.valueOf(1).equals(marker.opt("schema"))||!marker.optString("id").matches("[0-9a-f]{32}")||!"ready".equals(marker.optString("state"))||id==null||!Integer.valueOf(expected.slot).equals(id.opt("slot"))||!Integer.valueOf(expected.generation).equals(id.opt("generation"))||!expected.environmentId.equals(id.opt("environmentId")))throw new IOException("待应用网络设置身份或阶段无效");
  }
  byte[] bytes(){return J.obj("schema",1,"before",before.json(),"after",after==null?JSONObject.NULL:after.json(),"pending",after==null?JSONObject.NULL:pending()).toString().getBytes(StandardCharsets.UTF_8);}
  static EnvironmentResetPlan read(byte[] bytes)throws Exception{
    if(bytes==null||bytes.length==0||bytes.length>LIMIT)throw new IOException("登录重置记录无法读取，原数据保留");
    String text=StandardCharsets.UTF_8.newDecoder().onMalformedInput(java.nio.charset.CodingErrorAction.REPORT).onUnmappableCharacter(java.nio.charset.CodingErrorAction.REPORT).decode(java.nio.ByteBuffer.wrap(bytes)).toString();JSONTokener parser=new JSONTokener(text);Object value=parser.nextValue();
    if(!(value instanceof JSONObject)||parser.nextClean()!=0)throw new IOException("登录重置记录无效");JSONObject json=(JSONObject)value;
    if(!Integer.valueOf(1).equals(json.opt("schema")))throw new IOException("登录重置记录版本不支持");
    EnvironmentSpec before=EnvironmentSpec.read(json.getJSONObject("before").toString().getBytes(StandardCharsets.UTF_8));
    EnvironmentSpec after=json.isNull("after")?null:EnvironmentSpec.read(json.getJSONObject("after").toString().getBytes(StandardCharsets.UTF_8));
    return new EnvironmentResetPlan(before,after,json.isNull("pending")?null:json.getJSONObject("pending"));
  }
}
