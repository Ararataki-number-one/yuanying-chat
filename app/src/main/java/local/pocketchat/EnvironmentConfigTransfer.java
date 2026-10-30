package local.pocketchat;

import android.content.Context;
import android.content.SharedPreferences;
import java.io.IOException;
import java.util.function.BooleanSupplier;
import org.json.JSONObject;

/** The portable file contains no source identity. Export ownership is checked
 * locally; restore reserves a fresh identity and never overwrites a live slot. */
final class EnvironmentConfigTransfer {
  static EnvironmentConfigBackup.Config capture(Context context,EnvironmentSpec.Identity expected)throws Exception{
    return EnvironmentSpecRuntime.withIntent(context,()->{
      EnvironmentSpecRuntime.requireIdentity(context,expected);EnvironmentSpec state=new EnvironmentSpecRepository(context).load();
      if(!state.identity.equals(expected))throw new IOException("环境已改变，请重新选择");
      JSONObject row=ProfileCatalog.get(context).item(expected.slot);
      EnvironmentConfigBackup.Config captured=new EnvironmentConfigBackup.Config(row.optString("name"),state.desired().browser(),AppPrefs.values(context));
      EnvironmentSpecRuntime.requireIdentity(context,expected);return captured;
    });
  }
  static EnvironmentSpec.Identity restore(Context root,int slot,EnvironmentConfigBackup.Config config,BooleanSupplier current)throws Exception{
    // Revalidate at the mutation boundary, including supported template fields.
    EnvironmentConfigBackup.Config safe=EnvironmentConfigBackup.Config.read(config.bytes());
    if(slot<0||slot>=Profiles.MAX)throw new IOException("目标环境不可用");
    requireCurrent(current);EnvironmentResetActivity.verifyRoots(root,slot);Context destination=Profiles.context(root,slot);ProfileCatalog catalog=ProfileCatalog.get(root);
    synchronized(EnvironmentSpecRepository.GATES[slot]){
      final String batch=java.util.UUID.randomUUID().toString();final EnvironmentSpec.Identity[] staged={null};
      try{return catalog.createNew(slot,()->{
          requireCurrent(current);Profiles.FileCheck.requireUnusedBrowser(destination);
          EnvironmentSpec.Identity identity=catalog.identity(slot);staged[0]=identity;SecretStore vault=new SecretStore(destination);SharedPreferences preferences=destination.getSharedPreferences("chat",0);
          // The marker is committed before any vault mutation. A later failed
          // batch may clean only its exact marker under a new writer lease.
          SharedPreferences.Editor edit=preferences.edit().clear().putBoolean("environmentInitialized",true).putBoolean("pageMode",true)
            .putString("networkMode","external").putBoolean("requireExternalVpn",true).putBoolean("networkConfigured",false)
            .putInt("privacyLevel",safe.browser.protectionLevel()).putString("configRestoreBatch",batch)
            .putString("configRestoreIdentity",identity.environmentId).putInt("configRestoreGeneration",identity.generation);
          JSONObject options=safe.preferences();for(String key:EnvironmentConfigBackup.PREFERENCES)edit.putBoolean(key,options.getBoolean(key));
          if(!edit.commit())throw new IOException("环境配置未能保存，请重试");
          Profiles.clearConfiguration(vault);new EnvironmentSpecRepository(destination).initializeCopy(identity,safe.browser.json());
          catalog.rename(slot,safe.name);catalog.browserDisplay(slot,safe.browser.desktop());requireCurrent(current);return identity;
      });}catch(Exception failure){
        if(staged[0]!=null)try{discardUnused(catalog,destination,staged[0],batch);}catch(Exception cleanup){failure.addSuppressed(cleanup);}
        throw failure;
      }
    }
  }
  private static final class CleanupRollback extends Exception{}
  private static void discardUnused(ProfileCatalog catalog,Context destination,EnvironmentSpec.Identity staged,String batch)throws Exception{
    try{catalog.createNew(staged.slot,()->{
      // createNew rejects active, deleting and resetting slots. Re-check the
      // exact failed batch before touching files; another process can win the
      // unused slot after rollback and must never be cleaned by this task.
      Profiles.FileCheck.requireUnusedBrowser(destination);SharedPreferences preferences=destination.getSharedPreferences("chat",0);
      if(!batch.equals(preferences.getString("configRestoreBatch",""))||!staged.environmentId.equals(preferences.getString("configRestoreIdentity",""))||staged.generation!=preferences.getInt("configRestoreGeneration",-1))throw new IOException("恢复暂存已改变，未清理");
      Profiles.clearConfiguration(new SecretStore(destination));if(!preferences.edit().clear().commit())throw new IOException("恢复暂存未能清理，请核对环境列表");
      // This second reservation exists only to obtain the cross-process writer
      // lease. It must always roll back rather than publish an empty environment.
      throw new CleanupRollback();
    });}catch(CleanupRollback completed){}
  }
  private static void requireCurrent(BooleanSupplier current)throws IOException{if(current==null||!current.getAsBoolean())throw new IOException("备份恢复任务已取消，原环境未改变");}
}
