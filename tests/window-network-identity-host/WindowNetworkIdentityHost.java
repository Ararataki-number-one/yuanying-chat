package local.pocketchat;
import android.content.*;import android.net.Uri;import android.util.Log;import org.json.*;import java.util.*;import java.nio.charset.StandardCharsets;

/** Complete selected production constructor/helper, controlled observations only. */
public final class WindowNetworkIdentityHost {
  static final long NOW=1000000;
  static final JSONArray checks=new JSONArray();
  static JSONObject row(){return J.obj("slot",0,"environmentId","owned-environment","generation",2,"name","Owned");}
  static JSONObject config(){return J.obj("subscriptionUrl","https://saved.invalid/subscription","subscriptionName","Saved subscription","exitHost","192.0.2.9","exitPort",1080,"entry","Saved entry","entryMode","manual","exitRegion","Saved region");}
  static JSONObject runtime(JSONObject row,JSONObject config){
    JSONObject observed=J.obj("environmentId",row.opt("environmentId"),"generation",row.opt("generation"),"mode","internal","configurationFingerprint","controlled-fingerprint","entry","Observed entry","entryMode","latency","exitRegion","Observed region","subscriptionName","Observed subscription","exitId",NativeNetwork.exitIdentity(config),"subscriptionId",NativeNetwork.hash(config.optString("subscriptionUrl")));
    return J.obj("environmentId",row.opt("environmentId"),"generation",row.opt("generation"),"runningConfiguration",observed,"at",NOW,"mode","internal","configured",true,"connected",true,"uiLive",true,"exitId",NativeNetwork.exitIdentity(config),"subscriptionId",NativeNetwork.hash(config.optString("subscriptionUrl")),"ip","192.0.2.42","observedIp","192.0.2.99","entry","Observed entry","delayEntry","Observed entry","delay",42,"delayAt",NOW,"delayKind","response","latencyRemaining",120000,"healthDelay",20,"healthDelayAt",NOW,"website",J.obj("status","controlled"),"dnsActive","controlled-dns","appliedRevision",7);
  }
  static JSONObject copy(JSONObject value)throws Exception{return new JSONObject(value.toString());}
  static JSONObject shown(WindowNetworkState s){return J.obj("state",s.state,"connected",s.connected,"internal",s.internal,"ip",s.ip,"region",s.region,"latency",s.latency,"timer",s.latencyTimer,"entry",s.entry,"entryMode",s.entryMode,"subscription",s.subscription,"mainline",s.mainline(),"runtime",s.runtime,"runningConfiguration",NetworkWorkspaceUi.runningConfiguration(s));}
  static void check(String name,boolean pass,JSONObject row,JSONObject runtime,WindowNetworkState value){checks.put(J.obj("name",name,"pass",pass,"row",row,"input",runtime,"rowGenerationType",type(row.opt("generation")),"inputGenerationType",runtime==null?"null":type(runtime.opt("generation")),"output",shown(value)));}
  static String type(Object value){return value==null?"missing":value.getClass().getName();}
  static void mutate(JSONObject value,String name)throws Exception{
    if(name.equals("foreign-id"))value.put("environmentId","foreign-environment");
    else if(name.equals("foreign-generation"))value.put("generation",3);
    else if(name.equals("missing-id"))value.remove("environmentId");
    else if(name.equals("missing-generation"))value.remove("generation");
    else if(name.equals("missing-both")){value.remove("environmentId");value.remove("generation");}
    else if(name.equals("empty-id"))value.put("environmentId","");
    else if(name.equals("null-id"))value.put("environmentId",JSONObject.NULL);
    else if(name.equals("number-id"))value.put("environmentId",7);
    else if(name.equals("boolean-id"))value.put("environmentId",true);
    else if(name.equals("object-id"))value.put("environmentId",new JSONObject());
    else if(name.equals("string-generation"))value.put("generation","2");
    else if(name.equals("boolean-generation"))value.put("generation",true);
    else if(name.equals("fractional-generation"))value.put("generation",2.5);
    else if(name.equals("double-generation"))value.put("generation",2.0);
    else if(name.equals("negative-generation"))value.put("generation",-1);
    else if(name.equals("overflow-generation"))value.put("generation",2147483648L);
    else if(name.equals("long-overflow-generation"))value.put("generation",Long.MAX_VALUE);
    else if(name.equals("object-generation"))value.put("generation",new JSONObject());
    else if(name.equals("null-generation"))value.put("generation",JSONObject.NULL);
    else throw new AssertionError(name);
  }
  static final String[] INVALID={"foreign-id","foreign-generation","missing-id","missing-generation","missing-both","empty-id","null-id","number-id","boolean-id","object-id","string-generation","boolean-generation","fractional-generation","double-generation","negative-generation","overflow-generation","long-overflow-generation","object-generation","null-generation"};
  static boolean cleared(WindowNetworkState s,boolean saved){return s.runtime.length()==0&&!s.connected&&s.internal==saved&&s.ip.isEmpty()&&s.latency.equals("延迟未测")&&s.latencyTimer.equals("（等待连接）")&&s.state.equals(saved?"状态待核实":"未配置")&&s.entry.equals("Saved entry")&&s.entryMode.equals("手动指定")&&s.region.equals(saved?"Saved region":"")&&NetworkWorkspaceUi.runningConfiguration(s)==null;}
  static void foreignTop()throws Exception{
    for(boolean saved:new boolean[]{true,false})for(String name:INVALID){
      SharedPreferences.configured=saved;SharedPreferences.mode=saved?"internal":"external";
      JSONObject row=row(),config=config(),input=runtime(row,config);mutate(input,name);
      input.put("mode",saved?"external":"internal");input.put("configured",!saved);input.put("healthDelay",-1);input.put("blocked",true);input.put("issue","foreign issue");input.put("latencyMeasuring",true);
      String before=input.toString(),savedConfig=config.toString();WindowNetworkState value=new WindowNetworkState(new Context(),row,config,input,true,NOW);
      check("Foreign top-level observation "+name+" saved="+saved,cleared(value,saved)&&input.toString().equals(before)&&config.toString().equals(savedConfig)&&value.config==config,row,input,value);
    }
  }
  static void malformedRows()throws Exception{
    SharedPreferences.configured=true;SharedPreferences.mode="internal";
    for(String name:INVALID){
      if(name.equals("foreign-id")||name.equals("foreign-generation"))continue;
      JSONObject row=row(),config=config();mutate(row,name);JSONObject input=runtime(row,config);
      // Identical malformed metadata cannot become a self-asserted identity.
      String before=input.toString();WindowNetworkState value=new WindowNetworkState(new Context(),row,config,input,true,NOW);
      check("Malformed authoritative row "+name,cleared(value,true)&&input.toString().equals(before),row,input,value);
    }
    JSONObject row=row(),config=config(),input=runtime(row,config);row.put("environmentId",7);input.put("environmentId","7");WindowNetworkState value=new WindowNetworkState(new Context(),row,config,input,true,NOW);
    check("Coercible numeric row ID cannot match text",cleared(value,true),row,input,value);
  }
  static void nested()throws Exception{
    SharedPreferences.configured=true;SharedPreferences.mode="internal";
    for(String name:INVALID){
      JSONObject row=row(),config=config(),input=runtime(row,config);mutate(input.getJSONObject("runningConfiguration"),name);
      String before=input.toString();WindowNetworkState value=new WindowNetworkState(new Context(),row,config,input,true,NOW);
      check("Nested running configuration "+name,value.connected&&value.state.equals("正常")&&value.ip.equals("192.0.2.42")&&value.latency.equals("42 ms")&&value.entryMode.equals("手动指定")&&value.subscription.equals("Saved subscription")&&value.region.equals("Saved region")&&!value.runtime.has("runningConfiguration")&&NetworkWorkspaceUi.runningConfiguration(value)==null&&value.runtime!=input&&input.toString().equals(before),row,input,value);
    }
    for(Object bad:new Object[]{"wrong type",JSONObject.NULL,7}){
      JSONObject row=row(),config=config(),input=runtime(row,config);input.put("runningConfiguration",bad);String before=input.toString();WindowNetworkState value=new WindowNetworkState(new Context(),row,config,input,true,NOW);
      check("Malformed running configuration value "+type(bad),value.connected&&!value.runtime.has("runningConfiguration")&&input.toString().equals(before),row,input,value);
    }
  }
  static void trusted()throws Exception{
    SharedPreferences.configured=true;SharedPreferences.mode="internal";
    for(String name:new String[]{"fresh","stale","missing-time","zero-time","not-live","future","old-measurement","health-failed","blocked","integer-long","zero-generation","max-generation","no-running-configuration"}){
      JSONObject row=row(),config=config(),input=runtime(row,config);boolean live=!name.equals("not-live"),connected=name.equals("fresh")||name.equals("old-measurement")||name.equals("integer-long")||name.equals("zero-generation")||name.equals("max-generation")||name.equals("no-running-configuration");
      if(name.equals("stale"))input.put("at",NOW-45000);
      if(name.equals("missing-time"))input.remove("at");
      if(name.equals("zero-time"))input.put("at",0);
      if(name.equals("future"))input.put("at",NOW+60001);
      if(name.equals("old-measurement"))input.put("delayAt",NOW-120000);
      if(name.equals("health-failed"))input.put("healthDelay",-1);
      if(name.equals("blocked"))input.put("blocked",true);
      if(name.equals("integer-long"))input.put("generation",2L);
      if(name.equals("zero-generation")||name.equals("max-generation")){int generation=name.equals("zero-generation")?0:Integer.MAX_VALUE;row.put("generation",generation);input.put("generation",(long)generation);input.getJSONObject("runningConfiguration").put("generation",generation);}
      if(name.equals("no-running-configuration"))input.remove("runningConfiguration");
      String before=input.toString(),expectedLatency="42 ms"+(!connected||name.equals("old-measurement")?"（上次）":"");WindowNetworkState value=new WindowNetworkState(new Context(),row,config,input,live,NOW);
      String expectedState=connected?"正常":name.equals("not-live")?"未运行":name.equals("health-failed")?"需检查":name.equals("blocked")?"出口异常":"状态待核实";
      check("Owned observation preserves "+name,value.runtime==input&&value.connected==connected&&value.state.equals(expectedState)&&value.ip.equals(name.equals("blocked")?"192.0.2.99":"192.0.2.42")&&value.latency.equals(expectedLatency)&&input.toString().equals(before),row,input,value);
    }
    JSONObject row=row(),config=config(),input=runtime(row,config);row.put("environmentId","replacement-on-same-slot");WindowNetworkState reused=new WindowNetworkState(new Context(),row,config,input,true,NOW);check("Reused slot never inherits prior environment route",cleared(reused,true),row,input,reused);
    try{WindowNetworkState absent=new WindowNetworkState(new Context(),row,config,null,true,NOW);check("Absent runtime cannot contribute an actual route",cleared(absent,true),row,null,absent);}
    catch(RuntimeException error){checks.put(J.obj("name","Absent runtime cannot contribute an actual route","pass",false,"row",row,"exception",error.toString()));}
  }
  public static void main(String[]args)throws Exception{
    String executionFailure="";try{if(Boolean.getBoolean("deviceProjection"))new DeviceProjection().readModelIdentityChecks(new JSONObject());else{foreignTop();malformedRows();nested();trusted();}}catch(AssertionError failed){executionFailure=failed.toString();}
    int passed=0;for(int i=0;i<checks.length();i++)if(checks.getJSONObject(i).getBoolean("pass"))passed++;
    boolean success=executionFailure.isEmpty()&&passed==checks.length();System.out.println(J.obj("status",success?"passed":"failed","passed",passed,"total",checks.length(),"checks",checks,"executionFailure",executionFailure));if(!success)System.exit(1);
  }
  static class DeviceProjection extends Context{final JSONArray checks=WindowNetworkIdentityHost.checks;/* DEVICE_IDENTITY_METHODS */}
}
class WindowNetworkState{/* STATE_FIELDS *//* STATE_IDENTITY *//* STATE_CONSTRUCTOR *//* STATE_MAINLINE */}
class NetworkWorkspaceUi{/* RUNNING_CONFIGURATION */}
class Profiles{static Context context(Context c,int slot){return c;}}
class NetworkRegion{static String region(Context c,String ip){return "";}}
class NetworkCatalog{/* CATALOG_EXIT_ID *//* CATALOG_SUBSCRIPTION */}
class NativeNetwork{/* NATIVE_METHODS */}
class J{static JSONObject obj(Object...args){JSONObject value=new JSONObject();try{for(int i=0;i<args.length;i+=2)value.put((String)args[i],args[i+1]);}catch(JSONException e){throw new RuntimeException(e);}return value;}}
