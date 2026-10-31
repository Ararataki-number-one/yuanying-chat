package local.pocketchat;
import android.content.Context;
import java.io.IOException;
import org.json.JSONObject;
/** Optional migration is explicitly unavailable in the legacy transaction host.
 * Real selection/capture/publication behavior is tested in its own production suite. */
final class NetworkShareSelection {
  static void migrate(Context context,EnvironmentSpec.Identity owner,JSONObject config,String pending,EnvironmentSpec spec)throws IOException{throw new IOException("Share migration not executed by intent transaction adapters");}
  static void invalidateSaved(Context context,EnvironmentSpec.Identity owner)throws IOException{throw new IOException("Share invalidation not executed by intent transaction adapters");}
}
