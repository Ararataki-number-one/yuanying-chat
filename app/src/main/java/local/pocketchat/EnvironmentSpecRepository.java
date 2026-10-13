package local.pocketchat;

import android.content.Context;
import android.content.SharedPreferences;
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
  static final String RESET="browser-reset";
  static final Object[] GATES=new Object[8];
  static{for(int i=0;i<GATES.length;i++)GATES[i]=new Object();}
  final Context context;
  final ProfileCatalog catalog;
  final SecretStore vault;
  final int slot;
  EnvironmentSpecRepository(Context context){this.context=context.getApplicationContext();slot=Profiles.slot(this.context);catalog=ProfileCatalog.get(this.context);vault=new SecretStore(this.context);}

  EnvironmentSpec load()throws Exception{return locked(null,()->loadLocked(catalog.identity(slot)));}
  EnvironmentSpec initializeCopy(EnvironmentSpec.Identity expected,JSONObject browser)throws Exception{
    return locked(expected,()->{
      if(vault.get(STORE)!=null)throw new IOException("新环境配置已存在，未覆盖");
      EnvironmentSpec migrated=loadLocked(expected);
      EnvironmentSpec copy=EnvironmentSpec.initial(expected,new EnvironmentSpec.Configuration(browser,migrated.desired().network));
      vault.put(STORE,copy.bytes());return copy;
    });
  }
  EnvironmentResetPlan beginLoginReset(EnvironmentSpec.Identity expected)throws Exception{
    return locked(expected,()->{
      EnvironmentResetPlan plan=EnvironmentResetPlan.start(loadLocked(expected));
      // Publication precedes the SQL marker. If SQL rolls back, the old spec and
      // browser still work and this staged journal can safely be replaced.
      vault.put(RESET,plan.bytes());catalog.beginReset(expected);return plan;
    });
  }
  EnvironmentResetPlan resetPlan(EnvironmentSpec.Identity expected)throws Exception{
    return resetLocked(expected,()->{EnvironmentResetPlan plan=EnvironmentResetPlan.read(vault.get(RESET));if(!plan.next.equals(expected))throw new IOException("登录重置记录属于另一环境");return plan;});
  }
  void freezeReset(EnvironmentResetPlan plan)throws Exception{
    resetLocked(plan.next,()->{EnvironmentResetPlan current=EnvironmentResetPlan.read(vault.get(RESET));if(!current.next.equals(plan.next)||current.frozen())throw new IOException("登录重置阶段已变化");vault.put(RESET,plan.bytes());return null;});
  }
  void finishLoginReset(EnvironmentResetPlan plan)throws Exception{
    resetLocked(plan.next,()->{
      EnvironmentResetPlan current=EnvironmentResetPlan.read(vault.get(RESET));
      if(!current.frozen()||!java.util.Arrays.equals(current.bytes(),plan.bytes()))throw new IOException("登录重置记录已变化");
      EnvironmentSpec stored=EnvironmentSpec.read(vault.get(STORE));
      if(!stored.identity.equals(plan.before.identity)&&!stored.identity.equals(plan.next))throw new IOException("环境配置属于另一身份，原文件保留");
      vault.put(STORE,plan.after.bytes());
      if(plan.pending().length()==0)vault.remove("pending-network");else vault.put("pending-network",plan.pending().toString().getBytes(StandardCharsets.UTF_8));
      BrowserIdentitySpec browser=BrowserIdentitySpec.from(plan.after.desired().browser());
      if(!context.getSharedPreferences("chat",0).edit().putInt("privacyLevel",browser.protectionLevel()).remove("nextPrivacyLevel").remove("nextDesktopSite").commit())throw new IOException("网页配置未能保留，请重试");
      catalog.completeReset(plan.next,browser.desktop());return null;
    });
    // Cleanup is after SQL commits. Losing this optional acknowledgement leaves
    // a completed journal, never a paused environment without recovery data.
    try{locked(plan.next,()->{EnvironmentResetPlan saved=EnvironmentResetPlan.read(vault.get(RESET));if(saved.next.equals(plan.next))vault.remove(RESET);return null;});}catch(Exception ignored){}
  }
  private <T>T resetLocked(EnvironmentSpec.Identity expected,ProfileCatalog.IdentityAction<T> action)throws Exception{
    if(expected.slot!=slot)throw new IOException("环境槽位不匹配");
    synchronized(GATES[slot]){return catalog.withReset(expected,()->{
      try(RandomAccessFile handle=new RandomAccessFile(new File(context.getNoBackupFilesDir(),"environment-spec.lock"),"rw");FileLock lock=handle.getChannel().lock()){return action.run();}
    });}
  }
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
    // v1.5.23 owns source/cache identity. The sealed desired model must use the
    // same detached route bridge as later runtime acknowledgement, not re-open
    // the shared subscription catalog under this database transaction.
    migrated=EnvironmentSpec.initial(expected,new EnvironmentSpec.Configuration(migrated.desired().browser(),EnvironmentSpecRuntime.binding(expected,preferences.getString("networkMode","external"),network,preferences.getString("proxy",""))));
    vault.put(STORE,migrated.bytes());return migrated;
  }
  private byte[] readStrict(String name)throws Exception{
    // v1.5.23 SecretStore owns AtomicFile recovery/publication through its shared
    // stripe lease. Never restore .bak outside that lease.
    byte[] raw=vault.get(name);if(raw!=null&&raw.length>EnvironmentSpec.MAX_BYTES)throw new IOException("保存的环境配置过大；原文件保留");return raw;
  }
  static JSONObject strictObject(byte[] raw)throws IOException{
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
