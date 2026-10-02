package local.pocketchat;

import android.net.VpnService;
import android.content.Intent;
import android.os.ParcelFileDescriptor;

/** Test-only VPN sink, scoped to the isolated test package. Never forwards traffic. */
public class ShieldFixtureVpnService extends VpnService {
  ParcelFileDescriptor tunnel;static volatile String error="";
  @Override public int onStartCommand(Intent intent,int flags,int id){try{if(intent!=null&&"STOP".equals(intent.getAction())){if(tunnel!=null)tunnel.close();tunnel=null;stopSelf();return START_NOT_STICKY;}if(prepare(this)!=null)throw new IllegalStateException("Test VPN permission not prepared");tunnel=new Builder().setSession("Local security test").addAddress("10.77.0.2",32).addRoute("0.0.0.0",0).addAllowedApplication(getPackageName()).establish();if(tunnel==null)error="VPN establish returned null";}catch(Exception e){error=e.toString();}return START_NOT_STICKY;}
  @Override public void onDestroy(){try{if(tunnel!=null)tunnel.close();}catch(Exception ignored){}super.onDestroy();}
}
