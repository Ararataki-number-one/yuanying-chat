package android.app;

import android.content.*;

/** Only navigation/lifecycle boundary calls exist; no browser or document APIs. */
public class Activity extends Context {
  public boolean finishing,destroyed;
  public Intent started;public int starts;
  public boolean isFinishing(){return finishing;}
  public boolean isDestroyed(){return destroyed;}
  public void startActivity(Intent intent){starts++;started=intent;}
  @Override public SharedPreferences getSharedPreferences(String name,int mode){throw new AssertionError("navigation must not read profile preferences");}
}
