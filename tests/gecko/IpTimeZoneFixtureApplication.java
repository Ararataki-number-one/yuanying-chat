package local.pocketchat;

import android.content.Context;

/** Integration-only explicit policy setup. Production has no fixture branch. */
public final class IpTimeZoneFixtureApplication extends PocketApplication {
  private volatile boolean initializing=true;
  @Override public void onCreate(){
    super.onCreate();
    // Retain the original package rejection before any process early return.
    IpTimeZoneFixtureScopes.integration(this);
    // SDK content/socket/isolated children inherit this test Application. They
    // must retain the production parent path without fixture catalog/vault IO.
    android.content.pm.ApplicationInfo application=getApplicationInfo();
    if(application==null||android.os.Process.myUid()!=application.uid)return;
    String process=android.app.Application.getProcessName();
    if(!fixtureProcess(getPackageName(),process,Profiles.processSlot()))return;
    IpTimeZoneFixtureScopes.declaredGeneric(this);
    // The scope provider must reserve its nonce before even catalog creation
    // can enumerate slot6 preferences. It never starts a browser/session.
    if(IpTimeZoneFixtureScopes.setupProcess(this))return;
    // Finish catalog creation while reentrant profile() calls are inert.
    ProfileCatalog.get(this).getWritableDatabase();
    initializing=false;
    for(int slot=0;slot<Profiles.MAX;slot++)if(ProfileCatalog.get(this).available(slot))profile(slot);
  }
  static final String[] LEGACY_FIXTURE_PROCESSES={":caret_controlled_ime",":environment_intent_fixture",":environment_spec_fixture",":extension_upgrade_test",":fingerprint_followups",":identity_prototype",":management_test",":native_timezone_probe",":network_preflight",":network_protection",":resource_pressure_fixture",":template_fixture",":transport_binding_fixture",":transport_binding_services"};
  static boolean fixtureProcess(String packageName,String process,int slot){
    if(process==null||packageName==null)return false;
    if(EnvironmentProcessPolicy.owns(packageName,process,slot))return true;
    if(process.equals(packageName+":ip_timezone_setup"))return true;
    for(String suffix:LEGACY_FIXTURE_PROCESSES)if(process.equals(packageName+suffix))return true;
    return false;
  }
  @Override Context profile(int slot){
    Context context=super.profile(slot); // Parent releases its monitor first.
    if(!initializing)IpTimeZoneFixtureScopes.prepareGeneric(this,context,slot);
    return context;
  }
}
