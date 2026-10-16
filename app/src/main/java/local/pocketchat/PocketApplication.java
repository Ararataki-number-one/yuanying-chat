package local.pocketchat;

import android.app.Application;
import android.content.Context;
import android.os.Build;

public class PocketApplication extends Application {
  final Context[] profiles=new Context[Profiles.MAX];
  @Override public void onCreate(){super.onCreate();AppAppearance.install(this);AppVisibility.install(this);int id=Profiles.processSlot();if(id>0&&Build.VERSION.SDK_INT<28)throw new IllegalStateException("独立登录环境需要 Android 9 或更新版本");}
  synchronized Context profile(int id){if(profiles[id]==null)profiles[id]=new ProfileContext(this,id);return profiles[id];}
  // Android and AndroidX initializers require an Application here. Browser callers
  // retain the isolated ProfileContext supplied by each activity/service.
  @Override public Context getApplicationContext(){return this;}
  @Override public void onTrimMemory(int level){super.onTrimMemory(level);ChatSession session=ChatSession.peek();if(session!=null)session.handler.post(()->{if(!session.deleted){session.resources.sample();session.updateBrowserActivity();}});}
  @Override public void onConfigurationChanged(android.content.res.Configuration c){super.onConfigurationChanged(c);AppAppearance.refresh(this);}
  @Override public void onLowMemory(){super.onLowMemory();onTrimMemory(android.content.ComponentCallbacks2.TRIM_MEMORY_COMPLETE);}
}
