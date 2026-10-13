package local.pocketchat;

import android.content.Context;
import org.json.JSONObject;

/** Bridges existing protected route settings to the versioned environment model.
 * Callers supply detached settings: repository transactions never open the
 * shared subscription catalog, preserving the database/file lock order. */
final class EnvironmentSpecRuntime {
  static EnvironmentSpec.NetworkBinding binding(Context context,String mode,JSONObject settings,String proxy)throws Exception{
    EnvironmentSpec.Identity identity=ProfileCatalog.get(context).identity(Profiles.slot(context));
    return EnvironmentSpecMigration.fromLegacy(identity,false,1,mode,settings,proxy).desired().network;
  }
  static EnvironmentSpec desireNetwork(Context context,String action,JSONObject candidate)throws Exception{
    String mode="external".equals(action)?"external":"internal";
    EnvironmentSpec.NetworkBinding network=binding(context,mode,"internal".equals(mode)?candidate:new JSONObject(),"external".equals(mode)?candidate.optString("proxy"):"");
    EnvironmentSpecRepository repository=new EnvironmentSpecRepository(context);
    EnvironmentSpec current=repository.load();
    return repository.updateDesired(current.identity,current.desiredRevision,new EnvironmentSpec.Configuration(current.desired().browser(),network));
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
