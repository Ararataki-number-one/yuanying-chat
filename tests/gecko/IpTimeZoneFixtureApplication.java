package local.pocketchat;

import android.content.Context;

/** Integration-only explicit policy setup. Production has no fixture branch. */
public final class IpTimeZoneFixtureApplication extends PocketApplication {
  private volatile boolean initializing=true;
  @Override public void onCreate(){
    super.onCreate();
    IpTimeZoneFixtureScopes.declaredGeneric(this);
    // The scope provider must reserve its nonce before even catalog creation
    // can enumerate slot6 preferences. It never starts a browser/session.
    if(IpTimeZoneFixtureScopes.setupProcess(this))return;
    // Finish catalog creation while reentrant profile() calls are inert.
    ProfileCatalog.get(this).getWritableDatabase();
    initializing=false;
    for(int slot=0;slot<Profiles.MAX;slot++)if(ProfileCatalog.get(this).available(slot))profile(slot);
  }
  @Override Context profile(int slot){
    Context context=super.profile(slot); // Parent releases its monitor first.
    if(!initializing)IpTimeZoneFixtureScopes.prepareGeneric(this,context,slot);
    return context;
  }
}
