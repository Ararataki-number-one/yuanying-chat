package local.pocketchat;
import android.app.*;
import android.os.*;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
/** Developer-only local export for the owner's explicitly requested personal package. */
public class DefaultExportActivity extends Activity {
 @Override public void onCreate(Bundle b){super.onCreate(b);try{if(!"local.pocketchat".equals(getPackageName())||(getApplicationInfo().flags&android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE)==0)throw new SecurityException();SecretStore vault=new SecretStore(this);JSONObject settings=vault.settings();NativeNetwork.validate(settings);byte[] provider=vault.get("subscription"),meta=vault.get("subscription-meta");if(provider!=null&&meta!=null&&NativeNetwork.hash(settings.optString("subscriptionUrl")).equals(new JSONObject(new String(meta,StandardCharsets.UTF_8)).optString("urlHash")))settings.put("provider",new String(provider,StandardCharsets.UTF_8));J.write(new File(getFilesDir(),"personal-package-export.json"),settings.toString());J.write(new File(getFilesDir(),"personal-package-export-status.json"),J.obj("ok",true,"cachedProvider",settings.has("provider")).toString());}catch(Exception e){try{J.write(new File(getFilesDir(),"personal-package-export-status.json"),J.obj("ok",false,"errorType",e.getClass().getSimpleName()).toString());}catch(Exception ignored){}}finish();}
}
