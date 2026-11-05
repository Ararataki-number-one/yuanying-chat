package local.pocketchat;

import android.content.Context;
import java.io.*;
import java.nio.channels.FileLock;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.*;
import org.json.*;

/** Independent schema1 sidecar; all methods perform catalog/vault/file I/O and
 * must run on the environment writer, never the UI or a native-port callback. */
final class GeckoTimeZoneStore {
  static final String STORE="gecko-timezone";
  static final int MAX_BYTES=32*1024;
  private static final Object[] GATES=new Object[8];
  private static final SecureRandom RANDOM=new SecureRandom();
  private static final String PROCESS_NONCE=nonce();
  private static final Map<String,Map<String,Ticket>> ACTIVE=new HashMap<>();
  static{for(int i=0;i<GATES.length;i++)GATES[i]=new Object();}
  static final class State {
    final EnvironmentSpec.Identity identity;final long revision;final GeckoTimeZoneSpec spec;
    private final String receipt;
    private State(EnvironmentSpec.Identity identity,long revision,GeckoTimeZoneSpec spec,String receipt){this.identity=identity;this.revision=revision;this.spec=spec;this.receipt=receipt;}
    byte[] bytes()throws IOException{return (J.obj("schema",1,"engine","gecko","identity",identity.json(),"revision",revision,"spec",spec.json(),"receipt",copy(receipt)).toString()+"\n").getBytes(StandardCharsets.UTF_8);}
  }
  static final class Binding {
    final String engineVersion,sessionId,sessionEpoch,contextId;
    Binding(String engineVersion,String sessionId,String sessionEpoch,String contextId){
      if(engineVersion==null||engineVersion.trim().isEmpty()||engineVersion.length()>128||engineVersion.indexOf('\0')>=0||!GeckoTimeZonePolicy.validSession(sessionId)||!GeckoTimeZonePolicy.validSession(sessionEpoch)
          ||!GeckoTimeZonePolicy.validContext(contextId))throw new IllegalArgumentException("时区浏览器上下文归属无效");
      this.engineVersion=engineVersion;this.sessionId=sessionId;this.sessionEpoch=sessionEpoch;this.contextId=contextId;
    }
    JSONObject json(){return J.obj("engineVersion",engineVersion,"sessionId",sessionId,"sessionEpoch",sessionEpoch,"contextId",contextId);}
    @Override public boolean equals(Object value){if(!(value instanceof Binding))return false;Binding b=(Binding)value;return engineVersion.equals(b.engineVersion)&&sessionId.equals(b.sessionId)&&sessionEpoch.equals(b.sessionEpoch)&&contextId.equals(b.contextId);}
    @Override public int hashCode(){return Objects.hash(engineVersion,sessionId,sessionEpoch,contextId);}
    static Binding read(JSONObject value)throws IOException{GeckoTimeZonePolicy.keys(value,"engineVersion","sessionId","sessionEpoch","contextId");try{return new Binding(value.getString("engineVersion"),value.getString("sessionId"),value.getString("sessionEpoch"),value.getString("contextId"));}catch(Exception invalid){throw new IOException("时区上下文记录无效",invalid);}}
  }
  static final class Ticket {
    final EnvironmentSpec.Identity identity;final long revision;final Binding binding;final String requestToken=nonce();private String receipt="{}";
    final GeckoTimeZoneSpec effective;final GeckoIpTimeZonePolicy.Observation ipObservation;final boolean rfpManaged;
    private Ticket(EnvironmentSpec.Identity identity,long revision,Binding binding,GeckoTimeZoneSpec effective,GeckoIpTimeZonePolicy.Observation ipObservation,boolean rfpManaged){this.identity=identity;this.revision=revision;this.binding=binding;this.effective=effective;this.ipObservation=ipObservation;this.rfpManaged=rfpManaged;}
  }
  private static final class Repository {
    final Context context;final ProfileCatalog catalog;final SecretStore vault;final int slot;final String path;
    Repository(Context context)throws IOException{this.context=context.getApplicationContext();slot=Profiles.slot(this.context);if(slot<0||slot>=8)throw new IOException("时区环境槽位无效");catalog=ProfileCatalog.get(this.context);vault=new SecretStore(this.context);path=this.context.getNoBackupFilesDir().getCanonicalPath();}
    State load(EnvironmentSpec.Identity expected)throws Exception{
      byte[] raw=vault.get(STORE);if(raw==null){State fresh=new State(expected,1,GeckoTimeZoneSpec.automatic(),"{}");write(fresh);forget();return fresh;}
      State saved=read(raw);if(saved.identity.slot!=expected.slot)throw new IOException("时区记录属于另一槽位，原文件保留");
      if(!saved.identity.environmentId.equals(expected.environmentId)){State fresh=new State(expected,1,GeckoTimeZoneSpec.automatic(),"{}");write(fresh);forget();return fresh;}
      if(saved.identity.generation>expected.generation)throw new IOException("时区记录代际超前，原文件保留");
      if(saved.identity.generation<expected.generation){State rebound=new State(expected,saved.revision,saved.spec,"{}");write(rebound);forget();return rebound;}
      return saved;
    }
    void write(State state)throws Exception{byte[] raw=state.bytes();if(raw.length>MAX_BYTES)throw new IOException("时区记录过大，原文件保留");vault.put(STORE,raw);}
    void forget(){synchronized(ACTIVE){ACTIVE.remove(path);}}
    boolean current(Ticket ticket){synchronized(ACTIVE){Map<String,Ticket> active=ACTIVE.get(path);return active!=null&&active.get(ticket.binding.sessionId)==ticket;}}
  }
  private interface Work<T>{T run(Repository repository,EnvironmentSpec.Identity identity)throws Exception;}
  static State load(Context context)throws Exception{return locked(context,null,(r,id)->r.load(id));}
  static State save(Context context,EnvironmentSpec.Identity expected,long revision,GeckoTimeZoneSpec spec)throws Exception{
    Objects.requireNonNull(spec);return locked(context,expected,(r,id)->{State before=r.load(id);revision(before,revision);if(before.spec.equals(spec))return before;
      if(revision==Long.MAX_VALUE)throw new IOException("时区配置版本已达到上限");State after=new State(id,revision+1,spec,"{}");r.write(after);r.forget();return after;});
  }
  /** A fresh request gets a fresh token even for identical zone/session IDs. */
  static Ticket activate(Context context,EnvironmentSpec.Identity expected,long revision,Binding binding)throws Exception{
    return activate(context,expected,revision,binding,null,false);
  }
  static Ticket activateIp(Context context,EnvironmentSpec.Identity expected,long revision,Binding binding,GeckoIpTimeZonePolicy.Observation observation)throws Exception{
    return activate(context,expected,revision,binding,Objects.requireNonNull(observation),false);
  }
  static Ticket activateRfp(Context context,EnvironmentSpec.Identity expected,long revision,Binding binding)throws Exception{return activate(context,expected,revision,binding,null,true);}
  private static Ticket activate(Context context,EnvironmentSpec.Identity expected,long revision,Binding binding,GeckoIpTimeZonePolicy.Observation observation,boolean rfpManaged)throws Exception{
    Objects.requireNonNull(binding);return locked(context,expected,(r,id)->{State desired=r.load(id);revision(desired,revision);
      if(desired.spec.followsIp()!=((observation!=null)||rfpManaged)||rfpManaged&&observation!=null)throw new IOException("出口 IP 时区尚未匹配当前线路");
      GeckoTimeZoneSpec effective=rfpManaged?GeckoTimeZoneSpec.system():observation==null?desired.spec:observation.effective();Ticket ticket=new Ticket(id,revision,binding,effective,observation,rfpManaged);
      synchronized(ACTIVE){Map<String,Ticket> active=ACTIVE.get(r.path);if(active==null){active=new HashMap<>();ACTIVE.put(r.path,active);}if(!active.containsKey(binding.sessionId)&&active.size()>=32)throw new IOException("时区上下文过多，请关闭不用的网页后重试");active.put(binding.sessionId,ticket);}return ticket;});
  }
  static void retire(Context context,Ticket ticket)throws Exception{
    Objects.requireNonNull(ticket);locked(context,ticket.identity,(r,id)->{synchronized(ACTIVE){Map<String,Ticket> active=ACTIVE.get(r.path);if(active!=null&&active.get(ticket.binding.sessionId)==ticket){active.remove(ticket.binding.sessionId);if(active.isEmpty())ACTIVE.remove(r.path);}}return null;});
  }
  static JSONObject record(Context context,Ticket ticket,String nativeAck)throws Exception{
    Objects.requireNonNull(ticket);return locked(context,ticket.identity,(r,id)->{
      State before=r.load(id);revision(before,ticket.revision);if(!r.current(ticket))throw new IOException("时区上下文已变化，旧确认未保存");
      if(before.spec.followsIp()!=((ticket.ipObservation!=null)||ticket.rfpManaged))throw new IOException("时区模式与原生确认不一致");
      JSONObject actual=GeckoTimeZonePolicy.nativeReadback(nativeAck,ticket.effective,ticket.requestToken,ticket.binding.sessionId,ticket.binding.contextId);
      JSONObject receipt=J.obj("schema",before.spec.followsIp()?2:1,"identity",id.json(),"desiredRevision",ticket.revision,"processNonce",PROCESS_NONCE,"requestToken",ticket.requestToken,
          "binding",ticket.binding.json(),"nativeSettingReadback",true,"pageObservationVerified",false,"workerCoverageVerified",false,"serviceWorkerCoverageVerified",false,
          "nativeReceipt",actual,"recordedAt",System.currentTimeMillis());
      if(before.spec.followsIp())receipt.put("effectiveZoneId",ticket.effective.zoneId).put("ipObservation",ticket.ipObservation==null?JSONObject.NULL:ticket.ipObservation.json()).put("rfpManaged",ticket.rfpManaged);
      r.write(new State(id,before.revision,before.spec,receipt.toString()));ticket.receipt=receipt.toString();return copy(ticket.receipt);
    });
  }
  /** Old process/session receipts stay historical; loading never makes one current. */
  static JSONObject lastReceipt(Context context,Ticket ticket)throws Exception{
    Objects.requireNonNull(ticket);return locked(context,ticket.identity,(r,id)->{State state=r.load(id);revision(state,ticket.revision);JSONObject receipt=copy(ticket.receipt);
      if(!r.current(ticket)||!PROCESS_NONCE.equals(receipt.optString("processNonce"))||!ticket.requestToken.equals(receipt.optString("requestToken"))||!ticket.binding.equals(Binding.read(receipt.getJSONObject("binding"))))return new JSONObject();return receipt;});
  }
  private static <T>T locked(Context context,EnvironmentSpec.Identity expected,Work<T> work)throws Exception{
    Repository r=new Repository(context);if(expected!=null&&expected.slot!=r.slot)throw new IOException("时区记录环境槽位不匹配");
    synchronized(GATES[r.slot]){EnvironmentSpec.Identity id=expected==null?r.catalog.identity(r.slot):expected;return r.catalog.withIdentity(id,()->{
      try(RandomAccessFile file=new RandomAccessFile(new File(r.context.getNoBackupFilesDir(),"gecko-timezone.lock"),"rw");FileLock ignored=file.getChannel().lock()){return work.run(r,id);}
    });}
  }
  private static void revision(State state,long expected)throws IOException{if(expected<1||state.revision!=expected)throw new IOException("时区配置已变化，请重新读取");}
  private static State read(byte[] raw)throws IOException{
    try{
      JSONObject value=GeckoTimeZonePolicy.object(raw,MAX_BYTES);GeckoTimeZonePolicy.keys(value,"schema","engine","identity","revision","spec","receipt");
      if(GeckoTimeZonePolicy.integer(value,"schema")!=1||!"gecko".equals(value.opt("engine")))throw new IOException("时区记录版本不受支持");
      EnvironmentSpec.Identity id=identity(value.getJSONObject("identity"));long revision=GeckoTimeZonePolicy.integer(value,"revision");if(revision<1)throw new IOException("时区配置版本无效");
      GeckoTimeZoneSpec spec=GeckoTimeZoneSpec.from(value.getJSONObject("spec"));JSONObject receipt=value.getJSONObject("receipt");
      if(receipt.length()>0){
        long receiptSchema=GeckoTimeZonePolicy.integer(receipt,"schema");GeckoTimeZoneSpec effective=spec;
        if(receiptSchema==2&&spec.followsIp()){
          GeckoTimeZonePolicy.keys(receipt,"schema","identity","desiredRevision","processNonce","requestToken","binding","nativeSettingReadback","pageObservationVerified","workerCoverageVerified","serviceWorkerCoverageVerified","nativeReceipt","recordedAt","effectiveZoneId","ipObservation","rfpManaged");
          if(Boolean.TRUE.equals(receipt.opt("rfpManaged"))&&receipt.opt("ipObservation")==JSONObject.NULL&&"".equals(receipt.opt("effectiveZoneId")))effective=GeckoTimeZoneSpec.system();
          else if(Boolean.FALSE.equals(receipt.opt("rfpManaged"))){GeckoIpTimeZonePolicy.Observation observation=GeckoIpTimeZonePolicy.historical(receipt.getJSONObject("ipObservation"));effective=observation.effective();}
          else throw new IOException("强化保护优先级记录无效");
          if(!effective.zoneId.equals(receipt.opt("effectiveZoneId")))throw new IOException("出口时区记录与原生确认不一致");
        }else if(receiptSchema==1&&!spec.followsIp())GeckoTimeZonePolicy.keys(receipt,"schema","identity","desiredRevision","processNonce","requestToken","binding","nativeSettingReadback","pageObservationVerified","workerCoverageVerified","serviceWorkerCoverageVerified","nativeReceipt","recordedAt");
        else throw new IOException("时区确认版本与当前模式不一致");
        if(!id.equals(identity(receipt.getJSONObject("identity")))||GeckoTimeZonePolicy.integer(receipt,"desiredRevision")!=revision
            ||GeckoTimeZonePolicy.integer(receipt,"recordedAt")<0||!receipt.getString("processNonce").matches("[0-9a-f]{64}")||!receipt.getString("requestToken").matches("[0-9a-f]{64}")
            ||!Boolean.TRUE.equals(receipt.opt("nativeSettingReadback"))||!Boolean.FALSE.equals(receipt.opt("pageObservationVerified"))
            ||!Boolean.FALSE.equals(receipt.opt("workerCoverageVerified"))||!Boolean.FALSE.equals(receipt.opt("serviceWorkerCoverageVerified")))throw new IOException("时区确认记录归属无效");
        Binding binding=Binding.read(receipt.getJSONObject("binding"));GeckoTimeZonePolicy.nativeReadback(receipt.getJSONObject("nativeReceipt").toString(),effective,receipt.getString("requestToken"),binding.sessionId,binding.contextId);
      }
      return new State(id,revision,spec,receipt.toString());
    }catch(IOException invalid){throw invalid;}catch(Exception invalid){throw new IOException("时区记录无法读取，原文件保留",invalid);}
  }
  private static EnvironmentSpec.Identity identity(JSONObject value)throws Exception{
    GeckoTimeZonePolicy.keys(value,"slot","generation","environmentId");long slot=GeckoTimeZonePolicy.integer(value,"slot"),generation=GeckoTimeZonePolicy.integer(value,"generation");
    if(slot<0||slot>7||generation<0||generation>Integer.MAX_VALUE)throw new IOException("时区环境身份无效");return new EnvironmentSpec.Identity((int)slot,(int)generation,value.getString("environmentId"));
  }
  private static JSONObject copy(String value)throws IOException{return GeckoTimeZonePolicy.object(value.getBytes(StandardCharsets.UTF_8),MAX_BYTES);}
  private static String nonce(){byte[] bytes=new byte[32];RANDOM.nextBytes(bytes);StringBuilder out=new StringBuilder(64);for(byte value:bytes)out.append(Character.forDigit((value>>>4)&15,16)).append(Character.forDigit(value&15,16));return out.toString();}
}
