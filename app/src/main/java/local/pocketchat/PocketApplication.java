package local.pocketchat;

import android.app.Application;
import android.content.Context;
import android.os.Build;
import android.webkit.WebView;

public class PocketApplication extends Application {
  final Context[] profiles=new Context[Profiles.MAX];
  @Override public void onCreate(){super.onCreate();int id=Profiles.processSlot();if(id>0){if(Build.VERSION.SDK_INT<28)throw new IllegalStateException("独立登录环境需要 Android 9 或更新版本");WebView.setDataDirectorySuffix("env"+id);}}
  synchronized Context profile(int id){if(profiles[id]==null)profiles[id]=new ProfileContext(this,id);return profiles[id];}
  @Override public Context getApplicationContext(){return profile(Profiles.processSlot());}
}
