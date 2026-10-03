package local.pocketchat;

import android.content.*;
import java.util.concurrent.Executor;

/** The official SDK's fixed child service names must not join another environment's runtime. */
final class GeckoEnvironmentContext extends ContextWrapper {
  final int slot;
  GeckoEnvironmentContext(Context context){super(context.getApplicationContext());slot=Profiles.slot(context);}
  @Override public Context getApplicationContext(){return this;}
  private Intent isolated(Intent intent){
    ComponentName name=intent.getComponent();
    String prefix="org.mozilla.gecko.process.GeckoChildProcessServices$";
    if(name==null||!name.getClassName().startsWith(prefix))return intent;
    String type=name.getClassName().substring(prefix.length());
    // bindIsolatedService already allocates a unique instance for isolated content.
    if(type.startsWith("isolated")||type.equals("zygoteTab"))return intent;
    if(!type.matches("socket|gpu|rdd|utility|gmplugin|ipdlunittest|tab[0-9]+"))
      throw new IllegalStateException("未知浏览器子进程类型");
    return new Intent(intent).setClassName(getPackageName(),"local.pocketchat.GeckoEnvironmentServices$E"+slot+type);
  }
  @Override public boolean bindService(Intent intent,ServiceConnection connection,int flags){return super.bindService(isolated(intent),connection,flags);}
  @Override public boolean bindService(Intent intent,int flags,Executor executor,ServiceConnection connection){return super.bindService(isolated(intent),flags,executor,connection);}
  @Override public boolean bindIsolatedService(Intent intent,int flags,String instance,Executor executor,ServiceConnection connection){
    return super.bindIsolatedService(intent,flags,"environment"+slot+"-"+instance,executor,connection);
  }
}
