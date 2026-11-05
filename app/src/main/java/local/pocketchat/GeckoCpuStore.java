package local.pocketchat;

import android.content.Context;
import java.io.*;
import java.nio.ByteBuffer;
import java.nio.channels.FileLock;
import java.nio.charset.*;
import java.util.*;
import org.json.*;

/** Encrypted desired state only. A saved revision is never a native ACK.
 * All methods run on the environment writer, not the UI/native callback. */
final class GeckoCpuStore {
  static final String STORE="gecko-cpu";static final int MAX_BYTES=8192;
  private static final Object[] GATES=new Object[8];
  static{for(int i=0;i<GATES.length;i++)GATES[i]=new Object();}
  static final class State {
    final EnvironmentSpec.Identity identity;final long revision;final GeckoCpuSpec spec;
    private State(EnvironmentSpec.Identity identity,long revision,GeckoCpuSpec spec){this.identity=identity;this.revision=revision;this.spec=spec;}
    byte[] bytes(){return (J.obj("schema",1,"engine","gecko","identity",identity.json(),"revision",revision,"spec",spec.json()).toString()+"\n").getBytes(StandardCharsets.UTF_8);}
  }
  private static final class Repository {
    final Context context;final ProfileCatalog catalog;final SecretStore vault;final int slot;
    Repository(Context context)throws IOException{this.context=context.getApplicationContext();slot=Profiles.slot(this.context);if(slot<0||slot>=8)throw new IOException("CPU 配置环境槽位无效");catalog=ProfileCatalog.get(this.context);vault=new SecretStore(this.context);}
    State load(EnvironmentSpec.Identity identity)throws Exception{
      byte[] raw=vault.get(STORE);
      if(raw==null){State fresh=new State(identity,1,GeckoCpuSpec.automatic());write(fresh);return fresh;}
      State saved=read(raw);if(saved.identity.slot!=identity.slot)throw new IOException("CPU 配置属于另一槽位，原文件保留");
      if(!saved.identity.environmentId.equals(identity.environmentId)){State fresh=new State(identity,1,GeckoCpuSpec.automatic());write(fresh);return fresh;}
      if(saved.identity.generation>identity.generation)throw new IOException("CPU 配置代际超前，原文件保留");
      if(saved.identity.generation<identity.generation){State rebound=new State(identity,saved.revision,saved.spec);write(rebound);return rebound;}
      return saved;
    }
    void write(State state)throws Exception{byte[] raw=state.bytes();if(raw.length>MAX_BYTES)throw new IOException("CPU 配置过大，原文件保留");vault.put(STORE,raw);}
  }
  private interface Work<T>{T run(Repository repository,EnvironmentSpec.Identity identity)throws Exception;}
  interface Action<T>{T run()throws Exception;}
  static State load(Context context)throws Exception{return locked(context,null,(r,id)->r.load(id));}
  static State save(Context context,EnvironmentSpec.Identity expected,long revision,GeckoCpuSpec desired)throws Exception{
    if(expected==null)throw new IOException("缺少 CPU 配置的预期环境身份");Objects.requireNonNull(desired);return locked(context,expected,(r,id)->{State before=r.load(id);revision(before,revision);if(before.spec.equals(desired))return before;
      if(revision==Long.MAX_VALUE)throw new IOException("CPU 配置版本已达上限");State after=new State(id,revision+1,desired);r.write(after);return after;});
  }
  /** Native admission calls this off the UI before accepting its boot snapshot. */
  static boolean stillCurrent(Context context,EnvironmentSpec.Identity expected,long revision)throws Exception{
    if(expected==null)throw new IOException("缺少 CPU 原生确认的预期环境身份");
    return locked(context,expected,(r,id)->r.load(id).revision==revision&&revision>0);
  }
  /** Cold profile preparation must hold the same owner/revision transaction.
   * Callers must not wrap this in a catalog transaction or reenter this store. */
  static <T>T withCurrent(Context context,EnvironmentSpec.Identity expected,long revision,Action<T> action)throws Exception{
    if(expected==null||action==null)throw new IOException("缺少 CPU 冷启动的环境身份或操作");
    return locked(context,expected,(r,id)->{revision(r.load(id),revision);return action.run();});
  }
  private static <T>T locked(Context context,EnvironmentSpec.Identity expected,Work<T> work)throws Exception{
    Repository repository=new Repository(context);if(expected!=null&&expected.slot!=repository.slot)throw new IOException("CPU 配置环境槽位不匹配");
    synchronized(GATES[repository.slot]){EnvironmentSpec.Identity identity=expected==null?repository.catalog.identity(repository.slot):expected;
      return repository.catalog.withIdentity(identity,()->{try(RandomAccessFile handle=new RandomAccessFile(new File(repository.context.getNoBackupFilesDir(),"gecko-cpu.lock"),"rw");FileLock held=handle.getChannel().lock()){return work.run(repository,identity);}});
    }
  }
  private static void revision(State state,long expected)throws IOException{if(expected<1||state.revision!=expected)throw new IOException("CPU 配置已变化，请重新打开设置");}
  private static State read(byte[] raw)throws IOException{
    try{
      if(raw.length==0||raw.length>MAX_BYTES)throw new IOException("CPU 配置为空或超出限制");
      String text=StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT).onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(raw)).toString();
      Object decoded=NetworkShareJson.decode(text,MAX_BYTES);if(!(decoded instanceof JSONObject))throw new IOException("CPU 配置必须是对象");JSONObject value=(JSONObject)decoded;
      keys(value,"schema","engine","identity","revision","spec");if(integer(value,"schema")!=1||!"gecko".equals(value.opt("engine")))throw new IOException("CPU 配置版本不受支持");
      JSONObject owner=value.getJSONObject("identity");keys(owner,"slot","generation","environmentId");long slot=integer(owner,"slot"),generation=integer(owner,"generation"),revision=integer(value,"revision");
      if(slot<0||slot>=8||generation<0||generation>Integer.MAX_VALUE||revision<1)throw new IOException("CPU 配置身份或版本无效");
      EnvironmentSpec.Identity identity=new EnvironmentSpec.Identity((int)slot,(int)generation,owner.getString("environmentId"));
      return new State(identity,revision,GeckoCpuSpec.from(value.getJSONObject("spec")));
    }catch(IOException invalid){throw invalid;}catch(Exception invalid){throw new IOException("CPU 配置无法读取，原文件保留",invalid);}
  }
  private static long integer(JSONObject value,String key)throws IOException{Object raw=value.opt(key);if(!(raw instanceof Integer||raw instanceof Long||raw instanceof Short||raw instanceof Byte))throw new IOException("CPU 配置整数无效");return ((Number)raw).longValue();}
  private static void keys(JSONObject value,String... expected)throws IOException{Set<String> keys=new HashSet<>();for(Iterator<String> i=value.keys();i.hasNext();)keys.add(i.next());if(!keys.equals(new HashSet<>(Arrays.asList(expected))))throw new IOException("CPU 配置结构不受支持，原文件保留");}
}
