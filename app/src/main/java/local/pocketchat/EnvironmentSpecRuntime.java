package local.pocketchat;

import android.content.Context;
import org.json.JSONObject;

/** Bridges existing protected route settings to the versioned environment model.
 * Callers supply detached settings: repository transactions never open the
 * shared subscription catalog, preserving the database/file lock order. */
final class EnvironmentSpecRuntime {
  private static final java.util.Map<String,java.util.concurrent.locks.ReentrantLock> intentLocks=new java.util.concurrent.ConcurrentHashMap<>();
  interface IntentAction<T>{T run()throws Exception;}
  /** Intent -> source/active leases (released) -> model/catalog transaction.
   * No source or active lease is held while acquiring the catalog writer. */
  static <T>T withIntent(Context context,IntentAction<T> action)throws Exception{
    java.io.File directory=context.getNoBackupFilesDir();String path=directory.getCanonicalPath();java.util.concurrent.locks.ReentrantLock local=intentLocks.computeIfAbsent(path,key->new java.util.concurrent.locks.ReentrantLock());local.lockInterruptibly();
    try{if(local.getHoldCount()>1)return action.run();try(java.io.RandomAccessFile handle=new java.io.RandomAccessFile(new java.io.File(directory,"network-intent.lock"),"rw");java.nio.channels.FileLock lock=handle.getChannel().lock()){return action.run();}}finally{local.unlock();}
  }
  static void requireIdentity(Context context,EnvironmentSpec.Identity expected)throws Exception{
    if(!ProfileCatalog.get(context).identity(Profiles.slot(context)).equals(expected))throw new java.io.IOException("环境已删除或重新创建，旧操作未应用");
  }
  static EnvironmentSpec.NetworkBinding binding(Context context,String mode,JSONObject settings,String proxy)throws Exception{
    EnvironmentSpec.Identity identity=ProfileCatalog.get(context).identity(Profiles.slot(context));
    return binding(identity,mode,settings,proxy);
  }
  /** Reads no catalog or provider payload. Both initial migration and runtime
   * acknowledgement bind to the same receipt identity used by NativeNetwork. */
  static EnvironmentSpec.NetworkBinding binding(EnvironmentSpec.Identity identity,String mode,JSONObject settings,String proxy){
    JSONObject snapshot=settings==null?new JSONObject():settings;
    EnvironmentSpec.NetworkBinding migrated=EnvironmentSpecMigration.fromLegacy(identity,false,1,mode,snapshot,proxy).desired().network;
    if(!"internal".equals(mode))return migrated;
    boolean hasExit=NativeNetwork.subscribedExit(snapshot)?!snapshot.optString("exitNodeKey").isEmpty():!snapshot.optString("exitHost").isEmpty();
    return new EnvironmentSpec.NetworkBinding(mode,migrated.entrySourceId,migrated.entryNodeId,migrated.exitSourceId,migrated.exitNodeId,migrated.selectionMode,hasExit?NativeNetwork.exitIdentity(snapshot):"",NativeNetwork.transportFingerprint(snapshot),migrated.exitConfigRevision);
  }
  static EnvironmentSpec desireNetwork(Context context,String action,JSONObject candidate)throws Exception{
    return desireNetwork(context,ProfileCatalog.get(context).identity(Profiles.slot(context)),action,candidate);
  }
  static EnvironmentSpec desireNetwork(Context context,EnvironmentSpec.Identity expected,String action,JSONObject candidate)throws Exception{
    String mode="external".equals(action)?"external":"internal";
    EnvironmentSpec.NetworkBinding network=binding(expected,mode,"internal".equals(mode)?candidate:new JSONObject(),"external".equals(mode)?candidate.optString("proxy"):"");
    return mirror(context,expected,network);
  }
  private static EnvironmentSpec mirror(Context context,EnvironmentSpec.Identity expected,EnvironmentSpec.NetworkBinding network)throws Exception{
    EnvironmentSpecRepository repository=new EnvironmentSpecRepository(context);
    for(int attempt=0;attempt<3;attempt++){
      requireIdentity(context,expected);EnvironmentSpec current=repository.load();if(!current.identity.equals(expected))throw new java.io.IOException("环境已改变，旧操作未应用");
      try{EnvironmentSpec result=repository.updateDesired(expected,current.desiredRevision,new EnvironmentSpec.Configuration(current.desired().browser(),network));requireIdentity(context,expected);return result;}
      catch(java.io.IOException failure){EnvironmentSpec fresh=repository.load();if(!fresh.identity.equals(expected)||fresh.desiredRevision==current.desiredRevision)throw failure;}
    }
    throw new java.io.IOException("环境配置正在变化，请稍后重新保存");
  }
  /** pending-network is authoritative. The model is a revisioned mirror; a
   * failed mirror never leaves an unacknowledged new candidate drainable. */
  static String saveNetworkIntent(Context context,EnvironmentSpec.Identity expected,String action,JSONObject candidate,String baseline,JSONObject lineage)throws Exception{
    return withIntent(context,()->{
      if(!"apply".equals(action)&&!"external".equals(action))throw new java.io.IOException("网络意图操作无效");
      NetworkChanges.IntentGuard guard=()->requireIdentity(context,expected);guard.verify();NetworkChanges.recoverIntent(context,expected.json(),guard);if("external".equals(action))NetworkChanges.validate(context,action,candidate);
      NetworkChanges.IntentReceipt receipt=NetworkChanges.stageIntent(context,action,candidate,baseline,lineage,expected.json(),guard);
      try{desireNetwork(context,expected,action,J.parse(receipt.staged).getJSONObject("config"));return NetworkChanges.promoteIntent(context,receipt,guard);}
      catch(Exception failure){
        if(!receipt.ready.isEmpty())try{if(committed(context,expected,receipt,guard))return NetworkChanges.confirmIntent(context,receipt,guard);}catch(Exception verification){failure.addSuppressed(verification);}
        try{NetworkChanges.rollbackIntent(context,receipt,guard);}catch(Exception rollback){
          failure.addSuppressed(rollback);
          if(!receipt.ready.isEmpty()){
            try{if(committed(context,expected,receipt,guard))return NetworkChanges.confirmIntent(context,receipt,guard);}catch(Exception verification){failure.addSuppressed(verification);}
            throw new IntentRecoveryRequired(failure);
          }
        }
        try{reconcileNetwork(context,expected,"");}catch(Exception recovery){failure.addSuppressed(recovery);}throw failure;
      }
    });
  }
  static final class IntentRecoveryRequired extends java.io.IOException {
    IntentRecoveryRequired(Exception cause){super("网络设置保存状态暂未确认，请在存储恢复后检查待应用设置",cause);}
  }
  private static boolean committed(Context context,EnvironmentSpec.Identity expected,NetworkChanges.IntentReceipt receipt,NetworkChanges.IntentGuard guard)throws Exception{
    if(!NetworkChanges.readyReceipt(context,receipt,guard))return false;
    JSONObject record=J.parse(receipt.ready),config=record.getJSONObject("config");String mode="external".equals(record.optString("action"))?"external":"internal";
    EnvironmentSpec saved=new EnvironmentSpecRepository(context).load();if(!saved.identity.equals(expected)||!routeMatches(saved,binding(expected,mode,config,"external".equals(mode)?config.optString("proxy"):"")))return false;
    return NetworkChanges.readyReceipt(context,receipt,guard);
  }
  static final class Reconciled {
    final JSONObject pending;final String proof;final EnvironmentSpec spec;
    Reconciled(JSONObject pending,String proof,EnvironmentSpec spec){this.pending=pending;this.proof=proof;this.spec=spec;}
  }
  static final class Authority {
    final JSONObject pending,config;final EnvironmentSpec.Identity identity;final String mode,proof;
    Authority(JSONObject pending,JSONObject config,String mode,EnvironmentSpec.Identity identity){this.pending=pending;this.config=config;this.mode=mode;this.identity=identity;proof=NativeNetwork.hash(identity.json()+"|"+pending+"|"+mode+"|"+config);}
    EnvironmentSpec.NetworkBinding network(){return binding(identity,mode,config,"external".equals(mode)?config.optString("proxy"):"");}
  }
  private static String modelStamp(Context context)throws Exception{
    byte[] bytes=SealedFileIo.read(new SecretStore(context).file("environment-spec"));return bytes==null?"absent":NetworkSourceSelection.payloadHash(bytes);
  }
  private static String proof(Authority authority,String modelStamp){return NativeNetwork.hash(authority.proof+"|"+modelStamp);}
  private static Authority authority(Context context,EnvironmentSpec.Identity expected)throws Exception{
    return NetworkSourceSelection.withActiveSnapshot(context,()->{
      requireIdentity(context,expected);JSONObject pending=NetworkChanges.pendingStrict(context);String action;JSONObject config;
      if(pending.length()>0){if(!NetworkChanges.identityMatches(pending,expected.json()))throw new java.io.IOException("待应用网络设置属于已删除的环境");JSONObject marker=NetworkChanges.intent(pending);if(marker!=null&&!"ready".equals(marker.optString("state")))throw new java.io.IOException("网络候选尚未完成保存");action=pending.optString("action");config=pending.optJSONObject("config");if(config==null||!("apply".equals(action)||"external".equals(action)))throw new java.io.IOException("待应用网络设置无效，原文件已保留");}
      else{android.content.SharedPreferences preferences=context.getSharedPreferences("chat",0);action="internal".equals(preferences.getString("networkMode","external"))?"apply":"external";if("apply".equals(action)){byte[] raw=new SecretStore(context).get("network");config=raw==null?new JSONObject():EnvironmentSpecRepository.strictObject(raw);}else config=J.obj("proxy",preferences.getString("proxy",""));}
      String mode="external".equals(action)?"external":"internal";requireIdentity(context,expected);return new Authority(pending,config,mode,expected);
    });
  }
  /** Startup/drain/cancellation also repair a crash after model persistence or
   * intent removal. The newest browser JSON is retained through revision CAS. */
  static Reconciled reconcileNetwork(Context context,EnvironmentSpec.Identity expected,String previousProof)throws Exception{
    return withIntent(context,()->{
      NetworkChanges.IntentGuard guard=()->requireIdentity(context,expected);NetworkChanges.recoverIntent(context,expected.json(),guard);
      String cached=previousProof;for(int attempt=0;attempt<3;attempt++){
        Authority before=authority(context,expected);String stamp=modelStamp(context);
        if(proof(before,stamp).equals(cached)){requireIdentity(context,expected);return new Reconciled(before.pending,cached,null);}
        EnvironmentSpec.NetworkBinding network=before.network();mirror(context,expected,network);
        String first=modelStamp(context);EnvironmentSpec confirmed=new EnvironmentSpecRepository(context).load();String second=modelStamp(context);Authority after=authority(context,expected);
        if(first.equals(second)&&confirmed.identity.equals(expected)&&routeMatches(confirmed,network)&&before.proof.equals(after.proof))return new Reconciled(after.pending,proof(after,second),confirmed);cached="";
      }
      throw new java.io.IOException("网络候选已变化，请稍后重试");
    });
  }
  static boolean cancelNetworkIntent(Context context,EnvironmentSpec.Identity expected,String snapshot)throws Exception{
    return withIntent(context,()->{requireIdentity(context,expected);boolean removed=NetworkSourceSelection.withActiveSnapshot(context,()->{requireIdentity(context,expected);return NetworkChanges.clearIfCurrent(context,snapshot);});reconcileNetwork(context,expected,"");return removed;});
  }
  /** After a pending change is cancelled, retain the browser edit while aligning
   * desired networking with the actual saved route. Invoke outside source and
   * active-snapshot locks, just like desireNetwork(). */
  static EnvironmentSpec desireActiveNetwork(Context context)throws Exception{
    return reconcileNetwork(context,ProfileCatalog.get(context).identity(Profiles.slot(context)),"").spec;
  }
  static EnvironmentSpec desireBrowser(Context context,JSONObject browser)throws Exception{
    EnvironmentSpecRepository repository=new EnvironmentSpecRepository(context);
    EnvironmentSpec current=repository.load();
    return repository.updateDesired(current.identity,current.desiredRevision,new EnvironmentSpec.Configuration(browser,current.desired().network));
  }
  static boolean routeMatches(EnvironmentSpec spec,EnvironmentSpec.NetworkBinding actual){
    return new EnvironmentSpec.Configuration(spec.desired().browser(),actual).equals(spec.desired());
  }
}
