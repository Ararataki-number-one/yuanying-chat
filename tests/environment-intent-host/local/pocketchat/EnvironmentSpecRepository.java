package local.pocketchat;
import android.content.Context;import org.json.*;import java.nio.charset.StandardCharsets;import java.io.IOException;
/** Persistence/CAS fault double. Tests execute the production Runtime, immutable
 * model, staged journal, exact rollback and real file leases; not Android AES. */
final class EnvironmentSpecRepository {
  static Runnable beforeUpdate;static boolean failUpdate;static int updates;
  final Context context;EnvironmentSpecRepository(Context context){this.context=context;}
  EnvironmentSpec load()throws Exception{EnvironmentSpec.Identity identity=ProfileCatalog.get(context).identity(Profiles.slot(context));byte[] raw=new SecretStore(context).get("environment-spec");if(raw!=null){EnvironmentSpec spec=EnvironmentSpec.read(raw);if(!spec.identity.equals(identity))throw new IOException("Wrong model identity");return spec;}EnvironmentSpec spec=EnvironmentSpecMigration.fromLegacy(identity,false,1,"external",new JSONObject(),context.getSharedPreferences("chat",0).getString("proxy",""));new SecretStore(context).put("environment-spec",spec.bytes());return spec;}
  EnvironmentSpec updateDesired(EnvironmentSpec.Identity identity,long revision,EnvironmentSpec.Configuration config)throws Exception{
    if(beforeUpdate!=null){Runnable callback=beforeUpdate;beforeUpdate=null;callback.run();}updates++;if(failUpdate){failUpdate=false;throw new IOException("Synthetic model publication failure");}
    EnvironmentSpec before=load();if(!before.identity.equals(identity))throw new IOException("Deleted/reused model identity");EnvironmentSpec after=before.withDesired(revision,config);if(after!=before)new SecretStore(context).put("environment-spec",after.bytes());return after;
  }
  static JSONObject strictObject(byte[] raw)throws Exception{return new JSONObject(new String(raw,StandardCharsets.UTF_8));}
}
