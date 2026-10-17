package local.pocketchat;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;
import org.json.JSONTokener;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Objects;
import java.util.UUID;

/** Immutable, credential-free environment state. A persisted setting is never an
 * acknowledgement that Gecko accepted it or that a webpage observed it. */
final class EnvironmentSpec {
  static final int SCHEMA=1,MAX_BYTES=256*1024;
  final Identity identity;
  final long desiredRevision,appliedRevision,observedRevision,appliedAt,observedAt;
  final String engineVersion;
  private final Configuration desired,applied;
  private final String observations;

  static final class Identity {
    final int slot,generation;
    final String environmentId;
    Identity(int slot,int generation,String environmentId){
      if(slot<0||slot>=8||generation<0)throw new IllegalArgumentException("Invalid environment slot/generation");
      String normalized=UUID.fromString(Objects.requireNonNull(environmentId)).toString();
      if(!normalized.equals(environmentId))throw new IllegalArgumentException("Invalid environment ID");
      this.slot=slot;this.generation=generation;this.environmentId=environmentId;
    }
    public boolean equals(Object value){if(!(value instanceof Identity))return false;Identity other=(Identity)value;return slot==other.slot&&generation==other.generation&&environmentId.equals(other.environmentId);}
    public int hashCode(){return Objects.hash(slot,generation,environmentId);}
    JSONObject json(){return object("slot",slot,"generation",generation,"environmentId",environmentId);}
  }

  /** Source/node identities only; credentials stay in the existing network vault.
   * Legacy node labels have an explicit legacy hash until the subscription parser
   * supplies a stable node ID. This model does not invent an applied route. */
  static final class NetworkBinding {
    final String mode,entrySourceId,entryNodeId,exitSourceId,exitNodeId,selectionMode,credentialRevision,entryConfigRevision,exitConfigRevision;
    NetworkBinding(String mode,String entrySourceId,String entryNodeId,String exitSourceId,String exitNodeId,String selectionMode,String credentialRevision){
      this(mode,entrySourceId,entryNodeId,exitSourceId,exitNodeId,selectionMode,credentialRevision,"","");
    }
    NetworkBinding(String mode,String entrySourceId,String entryNodeId,String exitSourceId,String exitNodeId,String selectionMode,String credentialRevision,String entryConfigRevision,String exitConfigRevision){
      if(!"internal".equals(mode)&&!"external".equals(mode))throw new IllegalArgumentException("Invalid network mode");
      // The shipped runtime accepts the empty legacy automatic/full-pool mode.
      // Retain it during migration rather than silently choosing a new policy.
      if(!"".equals(selectionMode)&&!"manual".equals(selectionMode)&&!"latency".equals(selectionMode)&&!"random".equals(selectionMode))throw new IllegalArgumentException("Invalid entry selection mode");
      this.mode=mode;this.entrySourceId=text(entrySourceId,512);this.entryNodeId=text(entryNodeId,512);this.exitSourceId=text(exitSourceId,512);this.exitNodeId=text(exitNodeId,512);this.selectionMode=selectionMode;this.credentialRevision=text(credentialRevision,512);this.entryConfigRevision=text(entryConfigRevision,512);this.exitConfigRevision=text(exitConfigRevision,512);
    }
    JSONObject json(){return object("mode",mode,"entrySourceId",entrySourceId,"entryNodeId",entryNodeId,"exitSourceId",exitSourceId,"exitNodeId",exitNodeId,"selectionMode",selectionMode,"credentialRevision",credentialRevision,"entryConfigRevision",entryConfigRevision,"exitConfigRevision",exitConfigRevision);}
    static NetworkBinding read(JSONObject json)throws JSONException{
      return new NetworkBinding(json.getString("mode"),json.getString("entrySourceId"),json.getString("entryNodeId"),json.getString("exitSourceId"),json.getString("exitNodeId"),json.getString("selectionMode"),json.getString("credentialRevision"),json.getString("entryConfigRevision"),json.getString("exitConfigRevision"));
    }
  }

  static final class Configuration {
    final NetworkBinding network;
    private final String browser;
    Configuration(JSONObject browser,NetworkBinding network){
      this.browser=canonical(Objects.requireNonNull(browser));
      if(this.browser.getBytes(StandardCharsets.UTF_8).length>16*1024)throw new IllegalArgumentException("Browser configuration too large");
      this.network=Objects.requireNonNull(network);
    }
    JSONObject browser(){return copy(browser);}
    JSONObject json(){return object("browser",browser(),"network",network.json());}
    public boolean equals(Object value){return value instanceof Configuration&&canonical(json()).equals(canonical(((Configuration)value).json()));}
    public int hashCode(){return canonical(json()).hashCode();}
    static Configuration read(JSONObject json)throws JSONException{return new Configuration(json.getJSONObject("browser"),NetworkBinding.read(json.getJSONObject("network")));}
  }

  private EnvironmentSpec(Identity identity,long desiredRevision,Configuration desired,long appliedRevision,Configuration applied,long appliedAt,String engineVersion,long observedRevision,String observations,long observedAt){
    if(desiredRevision<1||appliedRevision<0||appliedRevision>desiredRevision||observedRevision<0||observedRevision>appliedRevision)throw new IllegalArgumentException("Invalid configuration revision order");
    if((appliedRevision==0)!=(applied==null)||appliedAt<0||observedAt<0)throw new IllegalArgumentException("Invalid applied state");
    if(observedRevision!=0&&observedRevision!=appliedRevision)throw new IllegalArgumentException("Observation must match the applied revision");
    if(appliedRevision==0&&(!engineVersion.isEmpty()||appliedAt!=0))throw new IllegalArgumentException("Unapplied configuration cannot have an engine acknowledgement");
    if(appliedRevision>0&&engineVersion.trim().isEmpty())throw new IllegalArgumentException("Applied configuration requires an engine acknowledgement");
    if(appliedRevision==desiredRevision&&!desired.equals(applied))throw new IllegalArgumentException("Equal revisions cannot contain different configurations");
    if(observedRevision==0&&(observedAt!=0||copy(observations).length()!=0))throw new IllegalArgumentException("Unobserved configuration cannot contain observations");
    this.identity=Objects.requireNonNull(identity);this.desiredRevision=desiredRevision;this.desired=Objects.requireNonNull(desired);this.appliedRevision=appliedRevision;this.applied=applied;this.appliedAt=appliedAt;this.engineVersion=text(engineVersion,256);this.observedRevision=observedRevision;this.observations=observations;this.observedAt=observedAt;
  }
  static EnvironmentSpec initial(Identity identity,Configuration configuration){return new EnvironmentSpec(identity,1,configuration,0,null,0,"",0,"{}",0);}
  Configuration desired(){return desired;}
  Configuration applied(){return applied;}
  JSONObject observations(){return copy(observations);}
  boolean pending(){return desiredRevision!=appliedRevision;}

  EnvironmentSpec withDesired(long expectedRevision,Configuration next)throws IOException{
    requireRevision(expectedRevision,desiredRevision);
    if(desired.equals(next))return this;
    if(desiredRevision==Long.MAX_VALUE)throw new IOException("环境配置版本已达到上限");
    return new EnvironmentSpec(identity,desiredRevision+1,next,appliedRevision,applied,appliedAt,engineVersion,observedRevision,observations,observedAt);
  }
  EnvironmentSpec withApplied(long expectedRevision,String engine,long now)throws IOException{
    requireRevision(expectedRevision,desiredRevision);
    if(engine==null||engine.trim().isEmpty()||now<0)throw new IOException("缺少实际内核应用结果");
    if(appliedRevision==expectedRevision&&engineVersion.equals(engine))return this;
    return new EnvironmentSpec(identity,desiredRevision,desired,expectedRevision,desired,now,engine,0,"{}",0);
  }
  EnvironmentSpec withObservation(long expectedAppliedRevision,JSONObject observation,long now)throws IOException{
    if(expectedAppliedRevision<1)throw new IOException("环境配置尚未应用");
    requireRevision(expectedAppliedRevision,appliedRevision);
    String encoded=canonical(Objects.requireNonNull(observation));
    if(encoded.getBytes(StandardCharsets.UTF_8).length>128*1024||now<0)throw new IOException("环境观测数据无效或过大");
    return new EnvironmentSpec(identity,desiredRevision,desired,appliedRevision,applied,appliedAt,engineVersion,expectedAppliedRevision,encoded,now);
  }
  static void requireRevision(long expected,long actual)throws IOException{if(expected!=actual)throw new IOException("环境配置已改变，请重新读取后操作");}

  JSONObject json(){return object("schema",SCHEMA,"identity",identity.json(),"desiredRevision",desiredRevision,"desired",desired.json(),"appliedRevision",appliedRevision,"applied",applied==null?JSONObject.NULL:applied.json(),"appliedAt",appliedAt,"engineVersion",engineVersion,"observedRevision",observedRevision,"observations",observations(),"observedAt",observedAt);}
  byte[] bytes(){byte[] bytes=json().toString().getBytes(StandardCharsets.UTF_8);if(bytes.length>MAX_BYTES)throw new IllegalArgumentException("Environment state too large");return bytes;}
  static EnvironmentSpec read(byte[] bytes)throws IOException{
    if(bytes==null||bytes.length==0||bytes.length>MAX_BYTES)throw new IOException("保存的环境配置无效或过大");
    try{
      String decoded=StandardCharsets.UTF_8.newDecoder().onMalformedInput(java.nio.charset.CodingErrorAction.REPORT).onUnmappableCharacter(java.nio.charset.CodingErrorAction.REPORT).decode(java.nio.ByteBuffer.wrap(bytes)).toString();
      JSONTokener parser=new JSONTokener(decoded);Object parsed=parser.nextValue();
      if(!(parsed instanceof JSONObject)||parser.nextClean()!=0)throw new JSONException("Invalid root or trailing data");
      JSONObject json=(JSONObject)parsed;
      if(integer(json,"schema")!=SCHEMA)throw new IOException("环境配置版本不受当前版本支持；原文件保留");
      JSONObject id=json.getJSONObject("identity");long slot=integer(id,"slot"),generation=integer(id,"generation");
      if(slot>Integer.MAX_VALUE||generation>Integer.MAX_VALUE)throw new JSONException("Invalid identity");
      Identity identity=new Identity((int)slot,(int)generation,id.getString("environmentId"));
      long appliedRevision=integer(json,"appliedRevision");Configuration applied=appliedRevision==0?null:Configuration.read(json.getJSONObject("applied"));
      if(appliedRevision==0&&!json.isNull("applied"))throw new JSONException("Unexpected applied state");
      return new EnvironmentSpec(identity,integer(json,"desiredRevision"),Configuration.read(json.getJSONObject("desired")),appliedRevision,applied,integer(json,"appliedAt"),json.getString("engineVersion"),integer(json,"observedRevision"),canonical(json.getJSONObject("observations")),integer(json,"observedAt"));
    }catch(IOException problem){throw problem;}catch(Exception problem){throw new IOException("保存的环境配置无法读取；原文件保留",problem);}
  }
  private static long integer(JSONObject json,String key)throws JSONException{
    Object raw=json.get(key);if(!(raw instanceof Byte)&&!(raw instanceof Short)&&!(raw instanceof Integer)&&!(raw instanceof Long))throw new JSONException("Expected integer "+key);return ((Number)raw).longValue();
  }
  private static String text(String value,int max){if(value==null||value.length()>max||value.indexOf('\0')>=0)throw new IllegalArgumentException("Invalid configuration text");return value;}
  private static JSONObject object(Object... values){JSONObject json=new JSONObject();try{for(int i=0;i<values.length;i+=2)json.put((String)values[i],values[i+1]);}catch(JSONException problem){throw new IllegalArgumentException(problem);}return json;}
  private static JSONObject copy(String text){try{return new JSONObject(text);}catch(JSONException impossible){throw new IllegalStateException(impossible);}}
  /** Sorted object keys provide semantic equality without depending on JSONObject order. */
  private static String canonical(Object value){return canonical(value,0);}
  private static String canonical(Object value,int depth){
    if(depth>32)throw new IllegalArgumentException("Configuration nesting too deep");
    if(value instanceof JSONObject){JSONObject json=(JSONObject)value;List<String> keys=new ArrayList<>();java.util.Iterator<String> iterator=json.keys();while(iterator.hasNext())keys.add(iterator.next());Collections.sort(keys);StringBuilder out=new StringBuilder("{");for(String key:keys){if(out.length()>1)out.append(',');out.append(JSONObject.quote(key)).append(':').append(canonical(json.opt(key),depth+1));}return out.append('}').toString();}
    if(value instanceof JSONArray){JSONArray array=(JSONArray)value;StringBuilder out=new StringBuilder("[");for(int i=0;i<array.length();i++){if(i>0)out.append(',');out.append(canonical(array.opt(i),depth+1));}return out.append(']').toString();}
    if(value==null||value==JSONObject.NULL)return "null";
    if(value instanceof String)return JSONObject.quote((String)value);
    if(value instanceof Boolean||value instanceof Number)return String.valueOf(value);
    throw new IllegalArgumentException("Unsupported configuration value");
  }
}
