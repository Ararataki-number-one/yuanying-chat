package local.pocketchat;

import android.app.Activity;
import android.os.*;

/** Dies as a real profile process; the network-service data plane must remain alive. */
public final class NetworkTransportLifecycleActivity extends Activity {
  @Override public void onCreate(Bundle saved){super.onCreate(saved);if(!getPackageName().endsWith(".test"))throw new SecurityException();Messenger reply=getIntent().getParcelableExtra("reply");new Thread(()->{
    try{NetworkTransportClient client=new NetworkTransportClient(Profiles.context(this,1),state->{});org.json.JSONObject ticket=client.call("snapshot","");Message message=Message.obtain();Bundle body=new Bundle();body.putString("json",J.obj("clientPid",android.os.Process.myPid(),"corePid",ticket.optInt("pid"),"servicePid",ticket.optInt("servicePid")).toString());message.setData(body);reply.send(message);Thread.sleep(100);}catch(Exception ignored){}
    android.os.Process.killProcess(android.os.Process.myPid());
  },"transport-client-lifecycle").start();}
}
