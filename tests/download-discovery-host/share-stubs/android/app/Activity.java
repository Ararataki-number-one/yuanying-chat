package android.app;
import android.content.*;
public class Activity extends Context{public volatile int starts;public Intent launched;public Runnable beforeStart;public boolean isFinishing(){return false;}public boolean isDestroyed(){return false;}public void startActivity(Intent intent){if(beforeStart!=null)beforeStart.run();launched=intent;starts++;}}
