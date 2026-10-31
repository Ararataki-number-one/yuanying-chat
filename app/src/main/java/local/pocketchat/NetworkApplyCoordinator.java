package local.pocketchat;

import android.content.Context;
import java.io.IOException;
import org.json.JSONObject;

/** The network part of a saved environment. Never acknowledges a browser policy. */
final class NetworkApplyCoordinator {
  static final String UNSELECTED="unselected",AUTO="idle",DEFER="defer",IMMEDIATE="immediate",FAILED="failed";
  static String policy(JSONObject pending)throws IOException{
    String value=pending.optString("applicationPolicy",DEFER);
    if(!UNSELECTED.equals(value)&&!AUTO.equals(value)&&!DEFER.equals(value)&&!IMMEDIATE.equals(value)&&!FAILED.equals(value))throw new IOException("待应用方式无法确认，请重新检查网络设置");
    return value;
  }
  static boolean automatic(JSONObject pending)throws IOException{String value=policy(pending);return AUTO.equals(value)||DEFER.equals(value);}
  static String candidateId(JSONObject pending)throws Exception{
    JSONObject marker=NetworkChanges.intent(pending);return marker==null?"legacy:"+NativeNetwork.hash(pending.toString()):marker.getString("id");
  }
  /** Deletion may clean only its own unpublished snapshot while its writer
   * transaction still excludes recreation. It never authorizes an apply. */
  static boolean deletionCleanupOwner(EnvironmentSpec.Identity owner,JSONObject row,boolean confirmed){
    if(owner==null||row==null||confirmed||owner.generation==Integer.MAX_VALUE)return false;Object generation=row.opt("generation"),slot=row.opt("slot");
    return (slot instanceof Integer||slot instanceof Long)&&((Number)slot).longValue()==owner.slot&&owner.environmentId.equals(row.opt("environmentId"))&&Boolean.TRUE.equals(row.opt("deleting"))&&Boolean.FALSE.equals(row.opt("resetting"))&&Boolean.FALSE.equals(row.opt("created"))&&(generation instanceof Integer||generation instanceof Long)&&((Number)generation).longValue()==(long)owner.generation+1;
  }
  /** A native worker checks this before and after replacement, without holding
   * source/catalog leases during IPC. A rollback still owns the saved candidate. */
  static final class RuntimeBinding {
    final EnvironmentSpec.Identity identity;
    final String candidateId,pendingSnapshot,publishedHash,configuration;
    final long savedRevision;
    final boolean rollback;final String expectedGeneration;
    RuntimeBinding(EnvironmentSpec.Identity identity,String candidateId,long savedRevision,String pendingSnapshot,String publishedHash,String configuration,boolean rollback){this(identity,candidateId,savedRevision,pendingSnapshot,publishedHash,configuration,rollback,null);}
    RuntimeBinding(EnvironmentSpec.Identity identity,String candidateId,long savedRevision,String pendingSnapshot,String publishedHash,String configuration,boolean rollback,String expectedGeneration){
      this.expectedGeneration=expectedGeneration;this.identity=identity;this.candidateId=candidateId;this.savedRevision=savedRevision;this.pendingSnapshot=pendingSnapshot;this.publishedHash=publishedHash;this.configuration=configuration;this.rollback=rollback;
    }
    void requireCurrent(Context context)throws Exception{
      EnvironmentSpecRuntime.withIntent(context,()->{
        EnvironmentSpecRuntime.requireIdentity(context,identity);
        JSONObject pending=NetworkChanges.pendingStrict(context);
        if(pendingSnapshot.isEmpty()||!pendingSnapshot.equals(pending.toString())||!candidateId.equals(NetworkApplyCoordinator.candidateId(pending)))throw new IOException("待应用配置已变化，旧连接操作已取消");
        if(!rollback)NetworkChanges.validateSaved(context,pending);
        EnvironmentSpec model=new EnvironmentSpecRepository(context).load();
        if(!identity.equals(model.identity)||model.desiredRevision!=savedRevision||!publishedHash.equals(NetworkChanges.hash(context)))throw new IOException("网络配置版本已变化，旧连接操作已取消");
        if(configuration.isEmpty()){
          if(!"external".equals(context.getSharedPreferences("chat",0).getString("networkMode","external")))throw new IOException("网络方式已变化");
        }else{
          JSONObject active=EnvironmentSpecRepository.strictObject(new SecretStore(context).get("network"));
          if(!"internal".equals(context.getSharedPreferences("chat",0).getString("networkMode","external"))||!configuration.equals(NativeNetwork.transportFingerprint(active)))throw new IOException("运行配置与本次应用不一致");
        }
        EnvironmentSpecRuntime.requireIdentity(context,identity);return null;
      });
    }
  }
}
