package local.pocketchat;
import android.app.Activity;import android.content.*;import android.os.Bundle;import org.json.*;import java.io.File;import java.nio.charset.StandardCharsets;import java.util.*;

/** Test-only profile7 UI/IPC fixture. Its core and service observations are synthetic. */
public class NetworkBridgeProbeActivity extends Activity {
  @Override protected void attachBaseContext(Context base){super.attachBaseContext(new ProfileContext(base,7));}
  @Override public void onCreate(Bundle state){super.onCreate(state);if(!getPackageName().endsWith(".test"))throw new IllegalStateException();try{Fixture network=new Fixture(this);java.lang.reflect.Field field=NativeNetwork.class.getDeclaredField("instance");field.setAccessible(true);synchronized(NativeNetwork.class){field.set(null,network);}network.worker.execute(()->{try{network.connected();}catch(Exception failure){android.util.Log.e("NetworkBridgeProbe","Synthetic fixture failed",failure);}finally{network.main.post(this::finish);}});}catch(Exception e){throw new IllegalStateException(e);}}
  static final class Fixture extends NativeNetwork {
    int syntheticFreshSnapshots;
    Fixture(Context c){super(c,new File(c.getNoBackupFilesDir(),"network-runtime"),false);}
    void connected()throws Exception{
      context.getSharedPreferences("chat",0).edit().putString("networkMode","internal").putBoolean("networkConfigured",true).commit();settings=secrets.settings();JSONObject meta=J.parse(new String(secrets.get("subscription-ui"),StandardCharsets.UTF_8));names=EntrySelection.allowed(settings,EntrySelection.strings(meta.optJSONArray("nodes")));currentEntry=settings.optString("entry");fingerprint=exitIdentity(settings);exitIp="192.0.2.7";lastVerified=System.currentTimeMillis();
      token=UUID.randomUUID().toString();controllerPort=25101;proxyPort=25102;routeSerial++;starting=false;ready=true;recoveryBlocked=false;admission=NetworkHealthPolicy.Admission.VERIFIED;
      // Deliberately synthetic SDK/service adapter, never reported as a real child process.
      transport.state=J.obj("slot",Profiles.slot(context),"alive",true,"generation",UUID.randomUUID().toString(),"configuration",transportFingerprint(settings),"pid",android.os.Process.myPid(),"servicePid",android.os.Process.myPid(),"controllerPort",controllerPort,"proxyPort",proxyPort);
      verifiedRoute=new ExitRouteReceipt(this,transport.state);quality.configure("bridge-fixture:"+fingerprint+":"+NativeNetwork.hash(settings.optString("subscriptionUrl")));quality.record(currentEntry,137,System.currentTimeMillis());NetworkCoreApplication.observeRunning(this);WindowNetworkState.save(context,null,this);
      J.write(new File(context.getFilesDir(),"network-bridge-probe.json"),J.obj("slot",Profiles.slot(context),"pid",android.os.Process.myPid(),"entry",currentEntry,"webViewCreated",ChatSession.peek()!=null,"syntheticCoreReceipt",true,"syntheticServiceSnapshot",true,"actualMihomoExecution",false,"phoneAcceptance",false).toString());
    }
    @Override boolean coreAlive(){return ready;}
    @Override boolean verifiedRouteCurrent(){syntheticFreshSnapshots++;return ready&&verifiedRoute!=null&&verifiedRoute.matches(this,transport.state);}
    @Override boolean authoritySourcesCurrent(){return true;} // This UI fixture does not claim real runtime providers.
    @Override int probe(String name){return 137;}
    @Override void restart(Callback callback){worker.execute(()->{try{connected();main.post(()->callback.done(true,"Synthetic fixture connected"));}catch(Exception e){main.post(()->callback.done(false,"Synthetic fixture rejected"));}});}
    @Override void restartConfiguration(NetworkApplyCoordinator.RuntimeBinding expected,Callback callback){worker.execute(()->{try{expected.requireCurrent(context);connected();expected.requireCurrent(context);main.post(()->callback.done(true,"Synthetic bound fixture connected"));}catch(Exception failure){main.post(()->callback.done(false,"Synthetic bound fixture rejected"));}});}
    @Override void checkExit(Callback callback){lastVerified=System.currentTimeMillis();main.post(()->callback.done(true,"Synthetic fixture verified"));}
  }
}
