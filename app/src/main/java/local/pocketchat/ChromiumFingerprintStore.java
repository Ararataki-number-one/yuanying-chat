package local.pocketchat;

import android.content.Context;
import java.io.File;
import java.io.IOException;
import java.io.RandomAccessFile;
import java.nio.channels.FileLock;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.*;
import org.json.*;

/** Chromium-only desired policy and scoped setting receipts, never Gecko applied
 * state or a claim of complete fingerprint protection. All entry points perform
 * catalog/file/vault I/O and belong on the environment's background writer. */
final class ChromiumFingerprintStore {
  static final String STORE="chromium-fingerprint",ENGINE="chromium";
  static final int SCHEMA=1,MAX_BYTES=64*1024,SPEC_BYTES=16*1024,RECEIPT_BYTES=32*1024;
  private static final Object[] GATES=new Object[8];
  private static final SecureRandom RANDOM=new SecureRandom();
  private static final String PROCESS_NONCE=randomSeed();
  private static final Map<String,Active> ACTIVE=new HashMap<>();
  private static final Set<String> STATES=new HashSet<>(Arrays.asList("saved","requested","native-readback","page-observed","unsupported","failed"));
  static{for(int i=0;i<GATES.length;i++)GATES[i]=new Object();}

  static final class State {
    final EnvironmentSpec.Identity identity;
    final long revision;
    // Internal policy material; do not publish this identifier in a webpage or UI report.
    final String seed;
    private final String specification,receipt;
    private State(EnvironmentSpec.Identity identity,long revision,String seed,String specification,String receipt){
      this.identity=identity;this.revision=revision;this.seed=seed;this.specification=specification;this.receipt=receipt;
    }
    JSONObject spec(){return copy(specification);}
    private JSONObject receipt(){return copy(receipt);}
    private byte[] bytes()throws IOException{return canonical(J.obj("schema",SCHEMA,"engine",ENGINE,"identity",identity.json(),"revision",revision,
        "seed",seed,"spec",spec(),"receipt",receipt())).getBytes(StandardCharsets.UTF_8);}
  }

  /** Every native surface/navigation incarnation needs its own binding. A new
   * provider or runtime epoch cannot inherit an old setting acknowledgement. */
  static final class Binding {
    final String providerPackage,providerVersion,runtimeEpoch;
    final long surfaceGeneration,navigationGeneration;
    Binding(String providerPackage,String providerVersion,String runtimeEpoch,long surfaceGeneration,long navigationGeneration){
      this.providerPackage=nonempty(providerPackage,256);this.providerVersion=nonempty(providerVersion,256);
      this.runtimeEpoch=nonempty(runtimeEpoch,128);
      if(surfaceGeneration<0||navigationGeneration<0)throw new IllegalArgumentException("浏览器运行代际无效");
      this.surfaceGeneration=surfaceGeneration;this.navigationGeneration=navigationGeneration;
    }
    @Override public boolean equals(Object value){if(!(value instanceof Binding))return false;Binding other=(Binding)value;
      return providerPackage.equals(other.providerPackage)&&providerVersion.equals(other.providerVersion)&&runtimeEpoch.equals(other.runtimeEpoch)
          &&surfaceGeneration==other.surfaceGeneration&&navigationGeneration==other.navigationGeneration;}
    @Override public int hashCode(){return Objects.hash(providerPackage,providerVersion,runtimeEpoch,surfaceGeneration,navigationGeneration);}
    private void put(JSONObject value)throws JSONException{value.put("providerPackage",providerPackage).put("providerVersion",providerVersion)
        .put("runtimeEpoch",runtimeEpoch).put("surfaceGeneration",surfaceGeneration).put("navigationGeneration",navigationGeneration);}
    private static Binding read(JSONObject value)throws Exception{return new Binding(value.getString("providerPackage"),value.getString("providerVersion"),
        value.getString("runtimeEpoch"),integer(value,"surfaceGeneration"),integer(value,"navigationGeneration"));}
  }
  private static final class Active {
    final EnvironmentSpec.Identity identity;final long revision;final Binding binding;final String nonce=randomSeed();
    Active(EnvironmentSpec.Identity identity,long revision,Binding binding){this.identity=identity;this.revision=revision;this.binding=binding;}
    boolean matches(EnvironmentSpec.Identity expected,long expectedRevision,Binding expectedBinding){return identity.equals(expected)&&revision==expectedRevision&&binding.equals(expectedBinding);}
  }
  private interface Work<T>{T run(Repository repository,EnvironmentSpec.Identity identity)throws Exception;}
  private static final class Repository {
    final Context context;final ProfileCatalog catalog;final SecretStore vault;final int slot;final String path;
    Repository(Context context)throws IOException{this.context=context.getApplicationContext();slot=Profiles.slot(this.context);
      if(slot<0||slot>=GATES.length)throw new IOException("环境槽位无效");
      catalog=ProfileCatalog.get(this.context);vault=new SecretStore(this.context);path=this.context.getNoBackupFilesDir().getCanonicalPath();}
    State load(EnvironmentSpec.Identity expected)throws Exception{
      byte[] raw=vault.get(STORE);
      if(raw==null){State created=fresh(expected);write(created);forget();return created;}
      State saved=read(raw);
      if(saved.identity.slot!=expected.slot)throw new IOException("指纹配置属于另一环境槽位，原文件保留");
      if(!saved.identity.environmentId.equals(expected.environmentId)){
        // A valid previous owner's sidecar can survive interrupted slot cleanup.
        // The catalog authorizes the new owner; none of the old policy is copied.
        State created=fresh(expected);write(created);forget();return created;
      }
      if(saved.identity.generation>expected.generation)throw new IOException("指纹配置代际超前，原文件保留");
      if(saved.identity.generation<expected.generation){
        State rebound=new State(expected,saved.revision,randomSeed(),saved.specification,"{}");write(rebound);forget();return rebound;
      }
      return saved;
    }
    void write(State state)throws Exception{byte[] raw=state.bytes();if(raw.length>MAX_BYTES)throw new IOException("指纹配置过大，原文件保留");vault.put(STORE,raw);}
    void forget(){synchronized(ACTIVE){ACTIVE.remove(path);}}
    Active active(EnvironmentSpec.Identity expected,long revision,Binding binding){synchronized(ACTIVE){Active active=ACTIVE.get(path);return active!=null&&active.matches(expected,revision,binding)?active:null;}}
  }

  static State load(Context context)throws Exception{return locked(context,null,(repository,identity)->repository.load(identity));}
  static State save(Context context,EnvironmentSpec.Identity expected,long expectedRevision,JSONObject specification)throws Exception{
    String selected=specification(specification);
    return locked(context,expected,(repository,identity)->{
      State before=repository.load(identity);revision(before,expectedRevision);
      if(before.specification.equals(selected))return before;
      State after=new State(identity,nextRevision(before.revision),before.seed,selected,"{}");repository.write(after);repository.forget();return after;
    });
  }
  /** Explicit user action. Ordinary saves retain the stable environment seed. */
  static State rotate(Context context,EnvironmentSpec.Identity expected,long expectedRevision)throws Exception{
    return locked(context,expected,(repository,identity)->{
      State before=repository.load(identity);revision(before,expectedRevision);
      State after=new State(identity,nextRevision(before.revision),randomSeed(),before.specification,"{}");repository.write(after);repository.forget();return after;
    });
  }
  /** Call before configuring/observing the current surface, not on an old async
   * completion. Native owners still validate actual view/URL/provider ownership. */
  static void activate(Context context,EnvironmentSpec.Identity expected,long expectedRevision,Binding binding)throws Exception{
    Objects.requireNonNull(binding);
    locked(context,expected,(repository,identity)->{State state=repository.load(identity);revision(state,expectedRevision);
      synchronized(ACTIVE){Active previous=ACTIVE.get(repository.path);if(previous==null||!previous.matches(identity,expectedRevision,binding))
        ACTIVE.put(repository.path,new Active(identity,expectedRevision,binding));}return null;});
  }
  static void retire(Context context,EnvironmentSpec.Identity expected,Binding binding)throws Exception{
    Objects.requireNonNull(binding);
    locked(context,expected,(repository,identity)->{synchronized(ACTIVE){Active active=ACTIVE.get(repository.path);
      if(active!=null&&active.identity.equals(identity)&&active.binding.equals(binding))ACTIVE.remove(repository.path);}return null;});
  }
  /** Each field must state the actual acknowledgement level. A page observation
   * is not an engine-native setting receipt or proof about workers/other sites. */
  static JSONObject record(Context context,EnvironmentSpec.Identity expected,long expectedRevision,Binding binding,JSONObject fields)throws Exception{
    Objects.requireNonNull(binding);String selected=fields(fields);
    return locked(context,expected,(repository,identity)->{
      State before=repository.load(identity);revision(before,expectedRevision);
      Active active=repository.active(identity,expectedRevision,binding);
      if(active==null)throw new IOException("网页或内核已变化，旧确认未保存");
      JSONObject receipt=J.obj("schema",SCHEMA,"engine",ENGINE,"identity",identity.json(),"desiredRevision",expectedRevision,
          "processNonce",PROCESS_NONCE,"activationNonce",active.nonce,"fields",copy(selected),"recordedAt",System.currentTimeMillis(),"fingerprintProtectionVerified",false);
      binding.put(receipt);String encoded=canonical(receipt);
      if(encoded.getBytes(StandardCharsets.UTF_8).length>RECEIPT_BYTES)throw new IOException("指纹确认记录过大");
      repository.write(new State(identity,before.revision,before.seed,before.specification,encoded));return copy(encoded);
    });
  }
  /** Empty means saved-only/unconfirmed for this exact running surface. Persisted
   * historical receipts never become current merely by reopening a process. */
  static JSONObject lastReceipt(Context context,EnvironmentSpec.Identity expected,long expectedRevision,Binding binding)throws Exception{
    Objects.requireNonNull(binding);
    return locked(context,expected,(repository,identity)->{
      State state=repository.load(identity);revision(state,expectedRevision);JSONObject receipt=state.receipt();
      Active active=repository.active(identity,expectedRevision,binding);
      if(receipt.length()==0||active==null||!active.nonce.equals(receipt.optString("activationNonce"))||!PROCESS_NONCE.equals(receipt.optString("processNonce"))
          ||!Binding.read(receipt).equals(binding))return new JSONObject();
      return receipt;
    });
  }

  private static <T>T locked(Context context,EnvironmentSpec.Identity expected,Work<T> work)throws Exception{
    Repository repository=new Repository(context);
    if(expected!=null&&expected.slot!=repository.slot)throw new IOException("指纹配置环境槽位不匹配");
    synchronized(GATES[repository.slot]){
      EnvironmentSpec.Identity identity=expected==null?repository.catalog.identity(repository.slot):expected;
      // Same writer order as EnvironmentSpecRepository: catalog -> file -> vault.
      return repository.catalog.withIdentity(identity,()->{
        try(RandomAccessFile file=new RandomAccessFile(new File(repository.context.getNoBackupFilesDir(),"chromium-fingerprint.lock"),"rw");
            FileLock ignored=file.getChannel().lock()){return work.run(repository,identity);}
      });
    }
  }
  private static State fresh(EnvironmentSpec.Identity identity)throws IOException{return new State(identity,1,randomSeed(),specification(J.obj("schema",SCHEMA,"engine",ENGINE)),"{}");}
  private static long nextRevision(long value)throws IOException{if(value==Long.MAX_VALUE)throw new IOException("指纹配置版本已达到上限");return value+1;}
  private static void revision(State state,long expected)throws IOException{if(expected!=state.revision)throw new IOException("指纹配置已改变，请重新读取后保存");}
  private static String randomSeed(){byte[] bytes=new byte[32];RANDOM.nextBytes(bytes);StringBuilder out=new StringBuilder(64);for(byte value:bytes)out.append(Character.forDigit((value>>>4)&15,16)).append(Character.forDigit(value&15,16));return out.toString();}
  private static String nonempty(String value,int maximum){if(value==null||value.trim().isEmpty()||value.length()>maximum||value.indexOf('\0')>=0)throw new IllegalArgumentException("浏览器运行身份无效");return value;}
  private static String specification(JSONObject value)throws IOException{
    if(value==null)throw new IOException("缺少 Chromium 指纹配置");
    String result=canonical(value);if(result.getBytes(StandardCharsets.UTF_8).length>SPEC_BYTES)throw new IOException("指纹配置过大，原文件保留");
    JSONObject detached=copy(result);
    if(!Integer.valueOf(SCHEMA).equals(detached.opt("schema"))||!ENGINE.equals(detached.opt("engine")))throw new IOException("Chromium 指纹配置版本或内核无效");
    return result;
  }
  private static String fields(JSONObject value)throws IOException{
    if(value==null)throw new IOException("缺少实际字段确认");
    String result=canonical(value);if(result.getBytes(StandardCharsets.UTF_8).length>24*1024)throw new IOException("字段确认记录过大");
    JSONObject detached=copy(result);
    if(detached.length()==0||detached.length()>96)throw new IOException("缺少实际字段确认");
    Iterator<String> keys=detached.keys();while(keys.hasNext()){String key=keys.next();JSONObject field=detached.optJSONObject(key);
      if(!key.matches("[a-zA-Z][a-zA-Z0-9._-]{0,63}")||field==null||!STATES.contains(field.opt("state")))throw new IOException("字段确认状态无效");}
    return result;
  }
  private static State read(byte[] raw)throws IOException{
    if(raw.length==0||raw.length>MAX_BYTES)throw new IOException("指纹配置无法读取或过大，原文件保留");
    try{
      String text=StandardCharsets.UTF_8.newDecoder().onMalformedInput(java.nio.charset.CodingErrorAction.REPORT).onUnmappableCharacter(java.nio.charset.CodingErrorAction.REPORT).decode(java.nio.ByteBuffer.wrap(raw)).toString();
      JSONTokener parser=new JSONTokener(text);Object parsed=parser.nextValue();if(!(parsed instanceof JSONObject)||parser.nextClean()!=0)throw new IOException("指纹配置 JSON 无效");
      JSONObject value=(JSONObject)parsed;keys(value,"schema","engine","identity","revision","seed","spec","receipt");
      if(integer(value,"schema")!=SCHEMA||!ENGINE.equals(value.getString("engine")))throw new IOException("指纹配置版本或内核不受支持");
      EnvironmentSpec.Identity identity=identity(value.getJSONObject("identity"));long revision=integer(value,"revision");String seed=value.getString("seed");
      if(revision<1||!seed.matches("[0-9a-f]{64}"))throw new IOException("指纹配置版本或种子无效");
      String specification=specification(value.getJSONObject("spec"));JSONObject receipt=value.getJSONObject("receipt");
      if(receipt.length()>0){
        keys(receipt,"schema","engine","identity","desiredRevision","processNonce","activationNonce","providerPackage","providerVersion","runtimeEpoch","surfaceGeneration","navigationGeneration","fields","recordedAt","fingerprintProtectionVerified");
        if(integer(receipt,"schema")!=SCHEMA||!ENGINE.equals(receipt.getString("engine"))||!identity.equals(identity(receipt.getJSONObject("identity")))
            ||integer(receipt,"desiredRevision")!=revision||integer(receipt,"recordedAt")<0||!Boolean.FALSE.equals(receipt.opt("fingerprintProtectionVerified"))
            ||!receipt.getString("processNonce").matches("[0-9a-f]{64}")||!receipt.getString("activationNonce").matches("[0-9a-f]{64}"))throw new IOException("指纹确认记录身份无效");
        Binding.read(receipt);fields(receipt.getJSONObject("fields"));
      }
      String encoded=canonical(receipt);if(encoded.getBytes(StandardCharsets.UTF_8).length>RECEIPT_BYTES)throw new IOException("指纹确认记录过大");
      return new State(identity,revision,seed,specification,encoded);
    }catch(IOException invalid){throw invalid;}catch(Exception invalid){throw new IOException("指纹配置无法读取，原文件保留",invalid);}
  }
  private static EnvironmentSpec.Identity identity(JSONObject value)throws Exception{keys(value,"slot","generation","environmentId");long slot=integer(value,"slot"),generation=integer(value,"generation");
    if(slot<0||slot>7||generation<0||generation>Integer.MAX_VALUE)throw new IOException("指纹环境身份无效");return new EnvironmentSpec.Identity((int)slot,(int)generation,value.getString("environmentId"));}
  private static long integer(JSONObject value,String key)throws Exception{Object raw=value.get(key);if(!(raw instanceof Byte)&&!(raw instanceof Short)&&!(raw instanceof Integer)&&!(raw instanceof Long))throw new IOException("指纹配置整数无效");return ((Number)raw).longValue();}
  private static void keys(JSONObject value,String... expected)throws IOException{Set<String> actual=new HashSet<>();Iterator<String> keys=value.keys();while(keys.hasNext())actual.add(keys.next());
    if(!actual.equals(new HashSet<>(Arrays.asList(expected))))throw new IOException("指纹配置结构不受支持，原文件保留");}
  private static JSONObject copy(String value){try{return new JSONObject(value);}catch(JSONException impossible){throw new IllegalStateException(impossible);}}
  private static String canonical(Object value)throws IOException{return canonical(value,0);}
  private static String canonical(Object value,int depth)throws IOException{
    if(depth>24)throw new IOException("指纹配置嵌套过深");
    if(value instanceof JSONObject){JSONObject object=(JSONObject)value;ArrayList<String> keys=new ArrayList<>();Iterator<String> iterator=object.keys();while(iterator.hasNext())keys.add(iterator.next());Collections.sort(keys);
      StringBuilder out=new StringBuilder("{");for(String key:keys){if(out.length()>1)out.append(',');out.append(JSONObject.quote(key)).append(':').append(canonical(object.opt(key),depth+1));}return out.append('}').toString();}
    if(value instanceof JSONArray){JSONArray array=(JSONArray)value;StringBuilder out=new StringBuilder("[");for(int i=0;i<array.length();i++){if(i>0)out.append(',');out.append(canonical(array.opt(i),depth+1));}return out.append(']').toString();}
    if(value==null||value==JSONObject.NULL)return "null";
    if(value instanceof String)return JSONObject.quote((String)value);
    if(value instanceof Boolean)return value.toString();
    if(value instanceof Number){double number=((Number)value).doubleValue();if(!Double.isFinite(number))throw new IOException("指纹配置数值无效");return value.toString();}
    throw new IOException("指纹配置包含不支持的数据");
  }
}
