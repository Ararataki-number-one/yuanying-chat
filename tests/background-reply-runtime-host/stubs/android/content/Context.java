package android.content;
import android.app.ActivityManager;
import java.util.*;
/** Records synthetic framework calls; never starts a process, service, or browser. */
public class Context {
  public static final int RECEIVER_NOT_EXPORTED=4;
  public final Context root;public final int slot;
  public final SharedPreferences.Memory preferences=new SharedPreferences.Memory();
  public Context[] profiles;public ActivityManager manager;
  public final List<Registration> registrations=new ArrayList<>();
  public final List<Intent> broadcasts=new ArrayList<>(),stopped=new ArrayList<>();
  public int providerAcquisitions,serviceStarts;
  public Context(){root=this;slot=0;}
  public Context(Context root,int slot){this.root=root;this.slot=slot;}
  public String getPackageName(){return "local.pocketchat.test";}
  public Context getApplicationContext(){return root;}
  public <T>T getSystemService(Class<T> type){if(type!=ActivityManager.class)throw new AssertionError("Unexpected framework service: "+type);return type.cast(root.manager);}
  public SharedPreferences getSharedPreferences(String name,int mode){if(!"chat".equals(name)||mode!=0)throw new AssertionError("Unexpected preference scope");return preferences;}
  public Intent registerReceiver(BroadcastReceiver receiver,IntentFilter filter){root.registrations.add(new Registration(receiver,filter,0));return null;}
  public Intent registerReceiver(BroadcastReceiver receiver,IntentFilter filter,int flags){root.registrations.add(new Registration(receiver,filter,flags));return null;}
  public void sendBroadcast(Intent intent){root.broadcasts.add(intent);}
  public boolean stopService(Intent intent){root.stopped.add(intent);return true;}
  public void startService(Intent intent){root.serviceStarts++;throw new AssertionError("Policy must not start services");}
  public void startForegroundService(Intent intent){root.serviceStarts++;throw new AssertionError("Policy must not start services");}
  public Object getContentResolver(){root.providerAcquisitions++;throw new AssertionError("Policy must not acquire a provider");}
  public static final class Registration {public final BroadcastReceiver receiver;public final IntentFilter filter;public final int flags;Registration(BroadcastReceiver receiver,IntentFilter filter,int flags){this.receiver=receiver;this.filter=filter;this.flags=flags;}}
}
