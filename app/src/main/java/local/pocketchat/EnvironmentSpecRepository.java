package local.pocketchat;

import android.content.Context;
import android.content.SharedPreferences;
import android.util.AtomicFile;
import java.io.File;
import java.io.IOException;
import java.io.RandomAccessFile;
import java.nio.channels.FileLock;
import java.nio.charset.StandardCharsets;
import org.json.JSONObject;

/** Per-environment AES-GCM + AtomicFile state, retaining the existing SecretStore
 * key alias. Strict reads deliberately never replace corrupt/future data with defaults. */
final class EnvironmentSpecRepository {
  static final String STORE="environment-spec";
  static final Object[] GATES=new Object[8];
  static{for(int i=0;i<GATES.length;i++)GATES[i]=new Object();}
  final Context context;
  final ProfileCatalog catalog;
  final SecretStore vault;
  final int slot;
  EnvironmentSpecRepository(Context context){this.context=context.getApplicationContext();slot=Profiles.slot(this.context);catalog=ProfileCatalog.get(this.context);vault=new SecretStore(this.context);}

  EnvironmentSpec load()throws Exception{return locked(null,()->loadLocked(catalog.identity(slot)));}
  EnvironmentSpec updateDesired(EnvironmentSpec.Identity expected,long expectedDesiredRevision,EnvironmentSpec.Configuration configuration)throws Exception{
    return locked(expected,()->saveChanged(loadLocked(expected),spec->spec.withDesired(expectedDesiredRevision,configuration)));
  }
  /** Call only after the real policy adapter acknowledged every supported field. */
  EnvironmentSpec markApplied(EnvironmentSpec.Identity expected,long desiredRevision,String actualEngineVersion)throws Exception{
    return locked(expected,()->saveChanged(loadLocked(expected),spec->spec.withApplied(desiredRevision,actualEngineVersion,System.currentTimeMillis())));
  }
  /** The revision describes the applied policy when sampling began. Page context
   * and navigation epoch still need their own guards in the audit collector. */
  EnvironmentSpec recordObservation(EnvironmentSpec.Identity expected,long appliedRevision,JSONObject observation)throws Exception{
    return locked(expected,()->saveChanged(loadLocked(expected),spec->spec.withObservation(appliedRevision,observation,System.currentTimeMillis())));
  }
  interface Change{EnvironmentSpec apply(EnvironmentSpec spec)throws Exception;}
  private EnvironmentSpec saveChanged(EnvironmentSpec before,Change change)throws Exception{
    EnvironmentSpec after=change.apply(before);if(after!=before)vault.put(STORE,after.bytes());return after;
  }
  private EnvironmentSpec loadLocked(EnvironmentSpec.Identity expected)throws Exception{
    byte[] raw=readStrict(STORE);if(raw!=null){EnvironmentSpec saved=EnvironmentSpec.read(raw);if(!saved.identity.equals(expected))throw new IOException("保存的配置属于另一环境；原文件保留");return saved;}
    JSONObject metadata=catalog.item(slot);SharedPreferences preferences=context.getSharedPreferences("chat",0);
    byte[] legacy=readStrict("network");JSONObject network=legacy==null?new JSONObject():strictObject(legacy);
    EnvironmentSpec migrated=EnvironmentSpecMigration.fromLegacy(expected,metadata.optBoolean("desktopSite"),preferences.getInt("privacyLevel",1),preferences.getString("networkMode","external"),network,preferences.getString("proxy",""));
    vault.put(STORE,migrated.bytes());return migrated;
  }
  private byte[] readStrict(String name)throws Exception{
    File file=vault.file(name);
    // SecretStore's old get() checks the base file before AtomicFile can restore
    // its .bak. Recover an interrupted AtomicFile write under the same lock.
    if(new File(file.getPath()+".bak").exists())try(java.io.FileInputStream ignored=new AtomicFile(file).openRead()){}
    if(file.exists()&&file.length()>EnvironmentSpec.MAX_BYTES+64)throw new IOException("保存的环境配置过大；原文件保留");
    return vault.get(name);
  }
  private static JSONObject strictObject(byte[] raw)throws IOException{
    try{String decoded=StandardCharsets.UTF_8.newDecoder().onMalformedInput(java.nio.charset.CodingErrorAction.REPORT).onUnmappableCharacter(java.nio.charset.CodingErrorAction.REPORT).decode(java.nio.ByteBuffer.wrap(raw)).toString();org.json.JSONTokener parser=new org.json.JSONTokener(decoded);Object value=parser.nextValue();if(!(value instanceof JSONObject)||parser.nextClean()!=0)throw new IOException("旧网络配置无效；原文件保留");return (JSONObject)value;}
    catch(org.json.JSONException|java.nio.charset.CharacterCodingException invalid){throw new IOException("旧网络配置无法读取；原文件保留",invalid);}
  }
  private <T>T locked(EnvironmentSpec.Identity expected,ProfileCatalog.IdentityAction<T> action)throws Exception{
    if(expected!=null&&expected.slot!=slot)throw new IOException("环境配置槽位不匹配");
    synchronized(GATES[slot]){
      // Lock order is catalog writer transaction -> env file. Deletion also owns
      // the writer transaction, preventing delete/reuse during sealed writes.
      EnvironmentSpec.Identity identity=expected==null?catalog.identity(slot):expected;
      return catalog.withIdentity(identity,()->{
        File file=new File(context.getNoBackupFilesDir(),"environment-spec.lock");
        try(RandomAccessFile handle=new RandomAccessFile(file,"rw");FileLock lock=handle.getChannel().lock()){return action.run();}
      });
    }
  }
}
