package local.pocketchat;

import android.content.Context;
import org.json.JSONObject;

/** Bridges existing protected route settings to the versioned environment model.
 * Callers supply detached settings: repository transactions never open the
 * shared subscription catalog, preserving the database/file lock order. */
final class EnvironmentSpecRuntime {
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
    String mode="external".equals(action)?"external":"internal";
    EnvironmentSpec.NetworkBinding network=binding(context,mode,"internal".equals(mode)?candidate:new JSONObject(),"external".equals(mode)?candidate.optString("proxy"):"");
    EnvironmentSpecRepository repository=new EnvironmentSpecRepository(context);
    EnvironmentSpec current=repository.load();
    return repository.updateDesired(current.identity,current.desiredRevision,new EnvironmentSpec.Configuration(current.desired().browser(),network));
  }
  /** After a pending change is cancelled, retain the browser edit while aligning
   * desired networking with the actual saved route. Invoke outside source and
   * active-snapshot locks, just like desireNetwork(). */
  static EnvironmentSpec desireActiveNetwork(Context context)throws Exception{
    android.content.SharedPreferences preferences=context.getSharedPreferences("chat",0);
    String mode=preferences.getString("networkMode","external");
    JSONObject network;
    if("internal".equals(mode)){byte[] bytes=new SecretStore(context).get("network");network=bytes==null?new JSONObject():EnvironmentSpecRepository.strictObject(bytes);}
    else{mode="external";network=J.obj("proxy",preferences.getString("proxy",""));}
    return desireNetwork(context,mode,network);
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
