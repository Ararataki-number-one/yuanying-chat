package local.pocketchat;

import android.content.Context;
import android.os.SystemClock;
import android.util.AtomicFile;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;

/** Explicit test setup only. It never grants a production network/TZ admission. */
final class IpTimeZoneFixtureScopes {
  static final int SLOT=6;
  static final String ACTIVITY="local.pocketchat.GeckoIpTimeZoneIntegrationActivity";
  static final String MARKER="ip-timezone-fixture-scope.json",SETUP="ip-timezone-fixture-setup.json";
  static final long MAX_AGE=1200000;
  private static final ThreadLocal<Boolean> ENTERED=ThreadLocal.withInitial(()->false);
  // All marker writers live in the single declared setup-provider process.
  // Binder calls may be concurrent; reservation and clear are one operation.
  private static final Object SCOPE_LOCK=new Object();
  private static final ExecutorService WRITER=Executors.newSingleThreadExecutor(r->{Thread t=new Thread(r,"explicit-fixture-timezone-setup");t.setDaemon(true);return t;});
  private static final Set<String> SEEN=Collections.synchronizedSet(new HashSet<>());
  private static volatile JSONObject installed;
  private IpTimeZoneFixtureScopes(){}

  static boolean setupProcess(Context context){return android.app.Application.getProcessName().equals(context.getPackageName()+":ip_timezone_setup");}
  static Context global(Context context){return Profiles.global(context);}
  static void integration(Context context){if(!"local.pocketchat.test".equals(context.getPackageName()))throw new SecurityException("Integration fixture scope only");}
  static void declaredGeneric(Context context){
    integration(context);try{android.content.pm.ApplicationInfo app=context.getPackageManager().getApplicationInfo(context.getPackageName(),android.content.pm.PackageManager.GET_META_DATA);
      if(app.metaData==null||!"explicit-manual-system-baseline".equals(app.metaData.getString("local.pocketchat.test.genericTimeZoneScope")))throw new SecurityException("Declared fixture policy scope absent");
    }catch(android.content.pm.PackageManager.NameNotFoundException missing){throw new SecurityException("Integration fixture metadata absent",missing);}
  }
  static JSONObject identity(Context context)throws Exception{
    JSONObject value=installed;if(value==null)synchronized(IpTimeZoneFixtureScopes.class){value=installed;if(value==null)installed=value=IntegrationBuildIdentity.read(global(context));}
    return J.parse(value.toString());
  }
  static File file(Context context,String name){if(!MARKER.equals(name)&&!SETUP.equals(name))throw new SecurityException("Unknown fixture scope file");return new File(global(context).getNoBackupFilesDir(),name);}
  static boolean sameIdentity(JSONObject value,EnvironmentSpec.Identity expected)throws Exception{
    GeckoTimeZonePolicy.keys(value,"slot","generation","environmentId");return GeckoTimeZonePolicy.integer(value,"slot")==expected.slot&&GeckoTimeZonePolicy.integer(value,"generation")==expected.generation&&expected.environmentId.equals(value.opt("environmentId"));
  }
  static JSONObject read(Context context,String name)throws Exception{
    File value=file(context,name);if(Files.isSymbolicLink(value.toPath()))throw new SecurityException("Fixture scope symlink refused");
    if(!value.exists())return null;if(!value.isFile()||value.length()>16384)throw new SecurityException("Fixture scope bound invalid");
    try(InputStream in=new AtomicFile(value).openRead()){return GeckoTimeZonePolicy.object(J.text(in,16384).getBytes(StandardCharsets.UTF_8),16384);}
  }
  static void write(Context context,String name,JSONObject value)throws Exception{
    File target=file(context,name);if(Files.isSymbolicLink(target.toPath()))throw new SecurityException("Fixture scope symlink refused");
    byte[] raw=(value.toString()+"\n").getBytes(StandardCharsets.UTF_8);if(raw.length>16384)throw new SecurityException("Fixture scope bound invalid");
    AtomicFile atomic=new AtomicFile(target);FileOutputStream out=null;try{out=atomic.startWrite();out.write(raw);atomic.finishWrite(out);}catch(Exception error){if(out!=null)atomic.failWrite(out);throw error;}
  }
  static JSONObject marker(Context context)throws Exception{
    JSONObject value=read(context,MARKER);if(value==null)return null;
    GeckoTimeZonePolicy.keys(value,"schema","kind","phase","slot","activity","runNonce","sourceCommit","sourceTree","apkSha256","sdkRunId","sdkRunAttempt","createdAtElapsed","identity");
    JSONObject build=identity(context),sdk=build.getJSONObject("sdkBuildIdentity");
    if(GeckoTimeZonePolicy.integer(value,"schema")!=1||!"explicit-ip-default-fixture".equals(value.opt("kind"))||GeckoTimeZonePolicy.integer(value,"slot")!=SLOT||!ACTIVITY.equals(value.opt("activity"))
        ||!(value.opt("runNonce") instanceof String)||!value.getString("runNonce").matches("[0-9a-f]{32}")
        ||!build.getString("sourceCommit").equals(value.opt("sourceCommit"))||!build.getString("sourceTree").equals(value.opt("sourceTree"))||!build.getString("apkSha256").equals(value.opt("apkSha256"))
        ||!sdk.getString("runId").equals(value.opt("sdkRunId"))||!sdk.getString("runAttempt").equals(value.opt("sdkRunAttempt")))throw new SecurityException("Fixture scope installed identity differs");
    long at=GeckoTimeZonePolicy.integer(value,"createdAtElapsed"),now=SystemClock.elapsedRealtime();
    if(at<0||at>now||now-at>MAX_AGE)throw new SecurityException("Fixture scope expired");
    String phase=value.optString("phase");if(!"provisional".equals(phase)&&!"reserved".equals(phase)&&!"armed".equals(phase))throw new SecurityException("Fixture scope phase differs");
    if(!"armed".equals(phase)){if(!setupProcess(context)||value.opt("identity")!=JSONObject.NULL)throw new SecurityException("Unarmed fixture scope cannot start a profile");}
    else if(!sameIdentity(value.getJSONObject("identity"),ProfileCatalog.get(context).identity(SLOT)))throw new SecurityException("Fixture scope environment changed");
    return value;
  }
  static void prepareGeneric(Context application,Context context,int slot){
    integration(application);if(ENTERED.get())return;ENTERED.set(true);
    try{
      if(Thread.holdsLock(application))throw new IllegalStateException("Fixture setup must not hold application profile monitor");
      // Profile creation already owns the catalog writer. Its next ordinary
      // context access occurs before Controller.load and performs setup then.
      if(ProfileCatalog.get(application).getWritableDatabase().inTransaction())return;
      if(slot==SLOT&&marker(application)!=null)return;
      if(!ProfileCatalog.get(application).available(slot))return;
      EnvironmentSpec.Identity expected=ProfileCatalog.get(application).identity(slot);
      String key=expected.slot+":"+expected.environmentId+":"+expected.generation;
      if(SEEN.contains(key))return;
      Future<?> work=WRITER.submit(()->{
        ENTERED.set(true);
        try{
          if(slot==SLOT&&marker(application)!=null)return;
          if(!ProfileCatalog.get(application).identity(slot).equals(expected))throw new IOException("Fixture setup environment changed");
          byte[] before=new SecretStore(context).get(GeckoTimeZoneStore.STORE);
          // Never infer user intent from a revision or mode. Every already
          // persisted record, including revision1 IP and corrupt records, is
          // left to the actual production loader without fixture rewriting.
          if(before!=null){SEEN.add(key);return;}
          GeckoTimeZoneStore.State initial=GeckoTimeZoneStore.load(context);
          if(!initial.identity.equals(expected))throw new IOException("Fixture setup identity changed");
          GeckoTimeZoneStore.State selected=GeckoTimeZoneStore.save(context,expected,initial.revision,GeckoTimeZoneSpec.system());
          if(!selected.identity.equals(expected)||!selected.spec.followsSystem())throw new IOException("Explicit manual-system fixture setup failed");
          SEEN.add(key);
        }catch(Exception error){throw new IllegalStateException("Explicit manual-system fixture setup failed",error);}
        finally{ENTERED.remove();}
      });
      try{work.get(5000,TimeUnit.MILLISECONDS);}catch(Exception error){work.cancel(true);throw new IllegalStateException("Explicit fixture setup did not complete",error);}
    }catch(RuntimeException error){throw error;}catch(Exception error){throw new IllegalStateException("Explicit fixture scope could not be verified",error);}
    finally{ENTERED.remove();}
  }
  static JSONObject prepareIp(Context context,String source,String nonce)throws Exception{
    synchronized(SCOPE_LOCK){return prepareIpLocked(context,source,nonce);}
  }
  private static JSONObject prepareIpLocked(Context context,String source,String nonce)throws Exception{
    integration(context);if(source==null||!source.matches("[0-9a-f]{40}")||nonce==null||!nonce.matches("[0-9a-f]{32}"))throw new SecurityException("Fresh fixture invocation required");
    JSONObject build=identity(context);if(!source.equals(build.getString("sourceCommit")))throw new SecurityException("Fixture source differs");
    if(read(context,MARKER)!=null)throw new SecurityException("Existing fixture scope must be inspected or cleared explicitly");
    if(!setupProcess(context))throw new SecurityException("Dedicated pre-profile setup process required");
    JSONObject sdk=build.getJSONObject("sdkBuildIdentity"),selected=J.obj("schema",1,"kind","explicit-ip-default-fixture","phase","provisional","slot",SLOT,"activity",ACTIVITY,"runNonce",nonce,
        "sourceCommit",source,"sourceTree",build.getString("sourceTree"),"apkSha256",build.getString("apkSha256"),"sdkRunId",sdk.getString("runId"),"sdkRunAttempt",sdk.getString("runAttempt"),"createdAtElapsed",SystemClock.elapsedRealtime(),"identity",JSONObject.NULL);
    write(context,MARKER,selected);
    JSONObject row=ProfileCatalog.get(context).item(SLOT);if(row.optBoolean("created")||row.optBoolean("deleting")||row.optBoolean("resetting"))throw new SecurityException("Fresh unused fixture slot required");
    selected.put("phase","reserved");write(context,MARKER,selected);Profiles.prepare(context,SLOT,false);
    Context profile=Profiles.context(context,SLOT);EnvironmentSpec.Identity actual=ProfileCatalog.get(context).identity(SLOT);
    if(new SecretStore(profile).get(GeckoTimeZoneStore.STORE)!=null)throw new SecurityException("IP fixture timezone store was accessed before first default load");
    selected.put("identity",actual.json()).put("phase","armed");write(context,MARKER,selected);
    JSONObject proof=J.obj("schema",1,"status","armed","sourceCommit",source,"sourceTree",build.getString("sourceTree"),"runNonce",nonce,"integrationApkSha256",build.getString("apkSha256"),"slot",SLOT,"identity",actual.json(),
        "unusedSlotBeforeSetup",true,"scopeBeforeAnyProfileAccess",true,"timezoneSealedRecordMissing",true,"actualProfilesPrepare",true,"actualDefaultStoreLoadYet",false,"manualSeedAppliedToIpScope",false);
    write(context,SETUP,proof);return proof;
  }
  static JSONObject requireArmed(Context context,String source,String nonce)throws Exception{
    JSONObject value=marker(context);if(value==null||!"armed".equals(value.opt("phase"))||!source.equals(value.opt("sourceCommit"))||!nonce.equals(value.opt("runNonce"))||Profiles.slot(context)!=SLOT
        ||!android.app.Application.getProcessName().equals(context.getPackageName()+":profile6"))throw new SecurityException("Exact canonical fixture scope required");return value;
  }
  static void clear(Context context,String source,String nonce)throws Exception{
    synchronized(SCOPE_LOCK){
      integration(context);if(!setupProcess(context))throw new SecurityException("Dedicated scope owner required");
      JSONObject value=read(context,MARKER);if(value==null)return;
      if(!Objects.equals(source,value.opt("sourceCommit"))||!Objects.equals(nonce,value.opt("runNonce")))throw new SecurityException("Fixture scope owner differs");
      new AtomicFile(file(context,MARKER)).delete();
    }
  }
}
