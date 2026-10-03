package local.pocketchat;

import android.app.*;
import android.content.*;
import android.os.*;

/** Reopens one environment from a native control process that loads neither engine. */
public final class EngineRestartActivity extends Activity {
  @Override public void onCreate(Bundle state){
    super.onCreate(state);
    int slot=getIntent().getIntExtra("slot",-1),pid=getIntent().getIntExtra("pid",-1);
    if(slot<0||slot>=Profiles.MAX||pid<=0||pid==android.os.Process.myPid()){finish();return;}
    String expected=getPackageName()+(slot==0?"":":profile"+slot);boolean owned=false;
    ActivityManager manager=(ActivityManager)getSystemService(ACTIVITY_SERVICE);
    for(ActivityManager.RunningAppProcessInfo process:manager.getRunningAppProcesses())
      if(process.pid==pid&&process.uid==android.os.Process.myUid()&&expected.equals(process.processName))owned=true;
    if(!owned){finish();return;}
    android.widget.TextView label=new android.widget.TextView(this);label.setText("正在重新打开当前环境…");label.setGravity(android.view.Gravity.CENTER);setContentView(label);
    android.os.Process.killProcess(pid);
    new Handler(Looper.getMainLooper()).postDelayed(()->{
      startActivity(new Intent(this,Profiles.activity(slot)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_CLEAR_TASK));finish();
    },350);
  }
}
