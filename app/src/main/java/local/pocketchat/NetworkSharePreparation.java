package local.pocketchat;

import java.io.IOException;
import java.util.UUID;
import org.json.*;

/** A share request fixes its owner, source, version and scope before any node read. */
final class NetworkSharePreparation {
  static final int SOURCE_LIMIT=16*1024*1024;
  static final class Failure extends IOException {
    final String stage,code,side;
    Failure(String stage,String code,String side){super("网络分享暂不可用");this.stage=stage;this.code=code;this.side=side;}
    String shortReason(){
      String prefix="entry".equals(side)?"入口":"exit".equals(side)?"出口":"";
      String reason="CONFIG_READ".equals(stage)?"配置暂时无法读取":"SUBSCRIPTION_CACHE".equals(stage)?"已保存的订阅缓存不可读取":"NODE_EXTRACT".equals(stage)?"所选节点暂时无法提取":"PARAMETER_CHECK".equals(stage)?"节点参数未通过检查":"FILE_GENERATE".equals(stage)?"分享文件未生成":"SYSTEM_SHARE".equals(stage)?"无法打开系统分享":"配置未复制";
      if("OWNER_CHANGED".equals(code))reason="环境已变化，请重新打开分享";
      else if("VERSION_CHANGED".equals(code))reason="所选配置版本已变化，请重新打开分享";
      else if("ENTRY_SELECTION_REQUIRED".equals(code))reason="请先选择本次分享的入口";
      return prefix+reason+"。";
    }
    JSONObject json(){return J.obj("stage",stage,"reason",code,"side",side);}
    String diagnostic(){return "阶段："+stage+"\n原因："+code+"\n范围："+(side.isEmpty()?"所选配置":side)+"\n原线路未改变";}
    static Failure read(JSONObject o){return new Failure(safe(o.optString("stage"),"CONFIG_READ SUBSCRIPTION_CACHE NODE_EXTRACT PARAMETER_CHECK FILE_GENERATE SYSTEM_SHARE CLIPBOARD","CONFIG_READ"),safe(o.optString("reason"),"UNREADABLE ABSENT MALFORMED OWNER_CHANGED VERSION_CHANGED HASH_MISMATCH ENTRY_SELECTION_REQUIRED NODE_NOT_FOUND UNSUPPORTED NATIVE_REJECTED IDENTITY_MISMATCH FILE_IO NO_TARGET CANCELLED","UNREADABLE"),safe(o.optString("side"),"entry exit",""));}
  }
  static String safe(String value,String allowed,String fallback){for(String s:allowed.split(" "))if(s.equals(value))return s;return fallback;}
  static Failure fail(String stage,String code,String side){return new Failure(stage,code,side);}
  static final class Request {
    final EnvironmentSpec.Identity owner;final String source,scope,version,entry,id;
    Request(EnvironmentSpec.Identity owner,String source,String scope,String version,String entry){this(owner,source,scope,version,entry,UUID.randomUUID().toString());}
    Request(EnvironmentSpec.Identity owner,String source,String scope,String version,String entry,String id){
      if(owner==null||!("saved".equals(source)||"running".equals(source))||!("entry".equals(scope)||"exit".equals(scope)||"route".equals(scope))||version==null||!version.matches("[a-p]{32}")||entry==null||entry.length()>210||id==null||!id.matches("[0-9a-f-]{36}"))throw new IllegalArgumentException("Invalid share request");
      this.owner=owner;this.source=source;this.scope=scope;this.version=version;this.entry=entry;this.id=id;
    }
    boolean wants(int side){return "route".equals(scope)||(side==0?"entry":"exit").equals(scope);}
    Request entry(String selected){return new Request(owner,source,scope,version,selected,id);}
    JSONObject json(){return J.obj("schema",1,"owner",owner.json(),"source",source,"scope",scope,"version",version,"entry",entry,"id",id);}
    boolean same(Request other){return other!=null&&json().toString().equals(other.json().toString());}
  }
  static Request readRequest(JSONObject o)throws Exception{
    if(o==null||o.optInt("schema")!=1)throw fail("CONFIG_READ","MALFORMED","");
    JSONObject v=o.getJSONObject("owner");return new Request(new EnvironmentSpec.Identity(v.getInt("slot"),v.getInt("generation"),v.getString("environmentId")),o.getString("source"),o.getString("scope"),o.getString("version"),o.getString("entry"),o.getString("id"));
  }
  static final class Part {
    final JSONObject selection;final byte[] bytes;final Failure failure;
    Part(JSONObject selection,byte[] bytes,Failure failure){this.selection=selection;this.bytes=bytes==null?null:bytes.clone();this.failure=failure;}
  }
  static final class Frozen {
    final Request request;final Part[] parts=new Part[2];final String name;
    Frozen(Request request,String name){this.request=request;this.name=name;}
    boolean current(android.content.Context context){return NetworkShareSelection.current(context,request);}
  }
}
