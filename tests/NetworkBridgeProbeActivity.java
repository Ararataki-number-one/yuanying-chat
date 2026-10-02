package local.pocketchat;
import android.app.Activity;import android.content.*;import android.os.Bundle;import org.json.*;import java.io.File;import java.nio.charset.StandardCharsets;import java.util.*;

/** Test-only connection fixture for verifying dispatch to profile 7 without creating a WebView. */
public class NetworkBridgeProbeActivity extends Activity {
  @Override protected void attachBaseContext(Context base){super.attachBaseContext(new ProfileContext(base,7));}
  @Override public void onCreate(Bundle state){super.onCreate(state);if(!getPackageName().endsWith(".test"))throw new IllegalStateException();try{Fixture network=new Fixture(this);java.lang.reflect.Field field=NativeNetwork.class.getDeclaredField("instance");field.setAccessible(true);field.set(null,network);network.connected();}catch(Exception e){throw new IllegalStateException(e);}finish();}
  static final class Fixture extends NativeNetwork {
    Fixture(Context c){super(c,new File(c.getNoBackupFilesDir(),"network-runtime"),false);}
    void connected()throws Exception{settings=secrets.settings();JSONObject meta=J.parse(new String(secrets.get("subscription-ui"),StandardCharsets.UTF_8));names=EntrySelection.allowed(settings,EntrySelection.strings(meta.optJSONArray("nodes")));currentEntry=settings.optString("entry");fingerprint=NetworkCatalog.exitId(settings);exitIp="192.0.2.7";lastVerified=System.currentTimeMillis();ready=true;quality.configure("bridge-fixture:"+fingerprint+":"+NativeNetwork.hash(settings.optString("subscriptionUrl")));quality.record(currentEntry,137,System.currentTimeMillis());WindowNetworkState.save(context,null,this);J.write(new File(context.getFilesDir(),"network-bridge-probe.json"),J.obj("slot",Profiles.slot(context),"entry",currentEntry,"webViewCreated",ChatSession.peek()!=null,"config",settings).toString());}
    @Override boolean coreAlive(){return ready;}
    @Override int probe(String name){return 137;}
    @Override void restart(Callback callback){try{connected();main.post(()->callback.done(true,"Fixture connected"));}catch(Exception e){main.post(()->callback.done(false,"Fixture rejected"));}}
    @Override void checkExit(Callback callback){lastVerified=System.currentTimeMillis();main.post(()->callback.done(true,"Fixture verified"));}
  }
}
