package local.pocketchat;

import android.content.Context;
import android.os.SystemClock;
import android.util.AtomicFile;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.*;
import org.json.*;

/** Integration-only manual timezone baseline for exactly the two TLS fixtures.
 * This scope is not a native admission or proof that a runtime was cold. */
final class GeckoTlsFixtureScopes {
  static final int MAX_BYTES=8192;static final long MAX_AGE=1200000;
  static final String KIND="explicit-manual-tls-fixture";
  private static final Object LOCK=new Object();
  private static final Map<String,Set<String>> USED=new HashMap<>();
  private static volatile JSONObject installed;
  private GeckoTlsFixtureScopes(){}
  static String purpose(int slot){if(slot!=1&&slot!=2)throw new SecurityException("TLS fixture slot only");return "local.pocketchat.GeckoTlsAcceptanceActivity$Profile"+slot;}
  private static void integration(Context context){if(!"local.pocketchat.test".equals(context.getPackageName()))throw new SecurityException("Integration only");}
  private static void setup(Context context){integration(context);if(!android.app.Application.getProcessName().equals(context.getPackageName()+":ip_timezone_setup"))throw new SecurityException("Dedicated setup process only");}
  private static void args(String source,String run,int slot,String purpose){
    if(source==null||!source.matches("[0-9a-f]{40}")||run==null||!run.matches("[0-9a-f]{32}")||!purpose(slot).equals(purpose))throw new SecurityException("Exact manual TLS purpose required");
  }
  static JSONObject identity(Context context)throws Exception{
    JSONObject value=installed;if(value==null)synchronized(GeckoTlsFixtureScopes.class){value=installed;if(value==null)installed=value=IntegrationBuildIdentity.read(Profiles.global(context));}
    return J.parse(value.toString());
  }
  private static File file(Context context,int slot){purpose(slot);return new File(Profiles.global(context).getNoBackupFilesDir(),"tls-manual-fixture-"+slot+".json");}
  private static JSONObject read(Context context,int slot)throws Exception{
    File path=file(context,slot);if(Files.isSymbolicLink(path.toPath()))throw new SecurityException("Manual fixture link");if(!path.exists())return null;
    if(!path.isFile()||path.length()>MAX_BYTES)throw new SecurityException("Manual fixture bound");
    try(InputStream in=new AtomicFile(path).openRead()){return GeckoTimeZonePolicy.object(J.text(in,MAX_BYTES).getBytes(StandardCharsets.UTF_8),MAX_BYTES);}
  }
  private static void write(Context context,int slot,JSONObject value)throws Exception{
    File path=file(context,slot);if(Files.isSymbolicLink(path.toPath()))throw new SecurityException("Manual fixture link");byte[] raw=(value.toString()+"\n").getBytes(StandardCharsets.UTF_8);if(raw.length>MAX_BYTES)throw new SecurityException("Manual fixture bound");
    AtomicFile atomic=new AtomicFile(path);FileOutputStream out=null;try{out=atomic.startWrite();out.write(raw);atomic.finishWrite(out);}catch(Exception error){if(out!=null)atomic.failWrite(out);throw error;}
  }
  private static EnvironmentSpec.Identity owner(JSONObject value)throws Exception{
    GeckoTimeZonePolicy.keys(value,"slot","generation","environmentId");long slot=GeckoTimeZonePolicy.integer(value,"slot"),generation=GeckoTimeZonePolicy.integer(value,"generation");
    if(slot<1||slot>2||generation<0||generation>Integer.MAX_VALUE||!(value.opt("environmentId") instanceof String))throw new SecurityException("Manual fixture owner");return new EnvironmentSpec.Identity((int)slot,(int)generation,value.getString("environmentId"));
  }
  private static void systemSpec(JSONObject value)throws Exception{
    GeckoTimeZonePolicy.keys(value,"schema","engine","mode","zoneId");if(GeckoTimeZonePolicy.integer(value,"schema")!=2||!"gecko".equals(value.opt("engine"))||!"system".equals(value.opt("mode"))||!"".equals(value.opt("zoneId"))||!GeckoTimeZoneSpec.from(value).followsSystem())throw new SecurityException("Retained record must be current manual system");
  }
  /** Preparse before the real loader: never migrate/reset another user choice. */
  private static long retained(byte[] raw,EnvironmentSpec.Identity expected)throws Exception{
    if(raw==null)throw new SecurityException("Missing claimed manual record");JSONObject value=GeckoTimeZonePolicy.object(raw,GeckoTimeZoneStore.MAX_BYTES);
    GeckoTimeZonePolicy.keys(value,"schema","engine","identity","revision","spec","receipt");
    if(GeckoTimeZonePolicy.integer(value,"schema")!=1||!"gecko".equals(value.opt("engine"))||!owner(value.getJSONObject("identity")).equals(expected))throw new SecurityException("Retained record owner differs");
    systemSpec(value.getJSONObject("spec"));long revision=GeckoTimeZonePolicy.integer(value,"revision");if(revision<1)throw new SecurityException("Retained revision invalid");
    JSONObject receipt=value.getJSONObject("receipt");if(receipt.length()>0){
      GeckoTimeZonePolicy.keys(receipt,"schema","identity","desiredRevision","processNonce","requestToken","binding","nativeSettingReadback","pageObservationVerified","workerCoverageVerified","serviceWorkerCoverageVerified","nativeReceipt","recordedAt");
      if(GeckoTimeZonePolicy.integer(receipt,"schema")!=1||!expected.equals(owner(receipt.getJSONObject("identity")))||GeckoTimeZonePolicy.integer(receipt,"desiredRevision")!=revision||GeckoTimeZonePolicy.integer(receipt,"recordedAt")<0||!receipt.getString("processNonce").matches("[0-9a-f]{64}")||!receipt.getString("requestToken").matches("[0-9a-f]{64}")||!Boolean.TRUE.equals(receipt.opt("nativeSettingReadback"))||!Boolean.FALSE.equals(receipt.opt("pageObservationVerified"))||!Boolean.FALSE.equals(receipt.opt("workerCoverageVerified"))||!Boolean.FALSE.equals(receipt.opt("serviceWorkerCoverageVerified")))throw new SecurityException("Retained historical receipt differs");
      GeckoTimeZoneStore.Binding binding=GeckoTimeZoneStore.Binding.read(receipt.getJSONObject("binding"));GeckoTimeZonePolicy.nativeReadback(receipt.getJSONObject("nativeReceipt").toString(),GeckoTimeZoneSpec.system(),receipt.getString("requestToken"),binding.sessionId,binding.contextId);
    }return revision;
  }
  static JSONObject prepareManual(Context context,String source,String run,int slot,String target)throws Exception{
    synchronized(LOCK){setup(context);args(source,run,slot,target);if(Thread.holdsLock(Profiles.global(context)))throw new SecurityException("Application monitor must be released");
      JSONObject build=identity(context);if(!source.equals(build.getString("sourceCommit")))throw new SecurityException("Installed source differs");
      if(read(context,slot)!=null)throw new SecurityException("Explicit owned clear required before new cold claim");
      Profiles.prepare(context,slot,false);Context profile=Profiles.context(context,slot);EnvironmentSpec.Identity expected=ProfileCatalog.get(context).identity(slot);SecretStore vault=new SecretStore(profile);byte[] before=vault.get(GeckoTimeZoneStore.STORE);boolean missing=before==null;
      final long revision;
      if(missing){GeckoTimeZoneStore.State state=GeckoTimeZoneStore.save(profile,expected,1,GeckoTimeZoneSpec.system());if(!state.identity.equals(expected)||state.revision!=2||!state.spec.followsSystem())throw new SecurityException("Actual missing default CAS differs");revision=state.revision;}
      else{revision=retained(before,expected);ProfileCatalog.get(context).withIdentity(expected,()->{if(!Arrays.equals(before,vault.get(GeckoTimeZoneStore.STORE)))throw new SecurityException("Retained manual bytes changed");return true;});}
      JSONObject sdk=build.getJSONObject("sdkBuildIdentity"),marker=J.obj("schema",1,"kind",KIND,"phase","armed","sourceCommit",source,"sourceTree",build.getString("sourceTree"),"apkSha256",build.getString("apkSha256"),"sdkRunId",sdk.getString("runId"),"sdkRunAttempt",sdk.getString("runAttempt"),"runNonce",run,"claimNonce",UUID.randomUUID().toString().replace("-",""),"slot",slot,"purpose",target,"createdAtElapsed",SystemClock.elapsedRealtime(),"identity",expected.json(),"timezoneDesired",GeckoTimeZoneSpec.system().json(),"timezoneRevision",revision,"timezoneMissingBefore",missing,"systemSeeded",missing,"retainedBytesPreserved",!missing,"scopeOnly",true,"nativeAdmissionGranted",false,"coldRuntimeProvenByScope",false);
      ProfileCatalog.get(context).withIdentity(expected,()->{write(context,slot,marker);return true;});return J.parse(marker.toString());
    }
  }
  private static JSONObject checked(Context context,String source,String run,int slot,String target)throws Exception{
    args(source,run,slot,target);JSONObject marker=read(context,slot);if(marker==null)throw new SecurityException("Manual fixture marker absent");
    GeckoTimeZonePolicy.keys(marker,"schema","kind","phase","sourceCommit","sourceTree","apkSha256","sdkRunId","sdkRunAttempt","runNonce","claimNonce","slot","purpose","createdAtElapsed","identity","timezoneDesired","timezoneRevision","timezoneMissingBefore","systemSeeded","retainedBytesPreserved","scopeOnly","nativeAdmissionGranted","coldRuntimeProvenByScope");
    JSONObject build=identity(context),sdk=build.getJSONObject("sdkBuildIdentity");
    if(GeckoTimeZonePolicy.integer(marker,"schema")!=1||!KIND.equals(marker.opt("kind"))||!"armed".equals(marker.opt("phase"))||GeckoTimeZonePolicy.integer(marker,"slot")!=slot||!target.equals(marker.opt("purpose"))||!source.equals(marker.opt("sourceCommit"))||!source.equals(build.opt("sourceCommit"))||!build.getString("sourceTree").equals(marker.opt("sourceTree"))||!build.getString("apkSha256").equals(marker.opt("apkSha256"))||!sdk.getString("runId").equals(marker.opt("sdkRunId"))||!sdk.getString("runAttempt").equals(marker.opt("sdkRunAttempt"))||!run.equals(marker.opt("runNonce"))||!(marker.opt("claimNonce") instanceof String)||!marker.getString("claimNonce").matches("[0-9a-f]{32}"))throw new SecurityException("Manual fixture installed/purpose binding differs");
    long at=GeckoTimeZonePolicy.integer(marker,"createdAtElapsed"),now=SystemClock.elapsedRealtime();if(at<0||at>now||now-at>MAX_AGE)throw new SecurityException("Manual fixture expired");
    EnvironmentSpec.Identity expected=owner(marker.getJSONObject("identity"));if(!expected.equals(ProfileCatalog.get(context).identity(slot)))throw new SecurityException("Manual fixture owner changed");systemSpec(marker.getJSONObject("timezoneDesired"));if(GeckoTimeZonePolicy.integer(marker,"timezoneRevision")<1)throw new SecurityException("Manual fixture revision");
    for(String key:new String[]{"timezoneMissingBefore","systemSeeded","retainedBytesPreserved"})if(!(marker.opt(key) instanceof Boolean))throw new SecurityException("Manual fixture setup flag type");
    boolean missing=marker.getBoolean("timezoneMissingBefore");if(marker.getBoolean("systemSeeded")!=missing||marker.getBoolean("retainedBytesPreserved")==missing||!Boolean.TRUE.equals(marker.opt("scopeOnly"))||!Boolean.FALSE.equals(marker.opt("nativeAdmissionGranted"))||!Boolean.FALSE.equals(marker.opt("coldRuntimeProvenByScope")))throw new SecurityException("Manual fixture scope overclaim");return marker;
  }
  /** Run on the bounded fixture writer before MainActivity or a warm browse. */
  static JSONObject admitCase(Context context,String source,String run,int slot,String target,String caseNonce,String expectedClaim)throws Exception{
    synchronized(LOCK){integration(context);args(source,run,slot,target);
      if(Profiles.slot(context)!=slot||!android.app.Application.getProcessName().equals(context.getPackageName()+":profile"+slot)||!target.equals(context.getClass().getName())||caseNonce==null||!caseNonce.matches("[0-9a-f]{32}"))throw new SecurityException("Exact TLS Activity/process/case required");
      JSONObject marker=checked(context,source,run,slot,target);String claim=marker.getString("claimNonce");if(expectedClaim!=null&&!claim.equals(expectedClaim))throw new SecurityException("Warm manual claim replaced");
      EnvironmentSpec.Identity expected=owner(marker.getJSONObject("identity"));
      ProfileCatalog.get(context).withIdentity(expected,()->{SecretStore vault=new SecretStore(context);byte[] before=vault.get(GeckoTimeZoneStore.STORE);long revision=retained(before,expected);
        if(revision!=marker.getLong("timezoneRevision")||!Arrays.equals(before,vault.get(GeckoTimeZoneStore.STORE)))throw new SecurityException("Manual desired bytes/revision changed");return true;});
      Set<String> seen=USED.get(claim);if(seen==null){if(USED.size()>=8)throw new SecurityException("Manual claim bound");seen=new HashSet<>();USED.put(claim,seen);}if(seen.size()>=256||!seen.add(caseNonce))throw new SecurityException("Manual case replay or bound");
      return J.parse(marker.toString()).put("caseNonce",caseNonce).put("activityClass",context.getClass().getName()).put("processName",android.app.Application.getProcessName()).put("recordReadOnly",true);
    }
  }
  static JSONObject inspectManual(Context context,String source,String run,int slot,String target)throws Exception{synchronized(LOCK){setup(context);return J.parse(checked(context,source,run,slot,target).toString());}}
  static void clearManual(Context context,String source,String run,int slot,String target)throws Exception{
    synchronized(LOCK){setup(context);args(source,run,slot,target);if(read(context,slot)==null)return;JSONObject marker=checked(context,source,run,slot,target);new AtomicFile(file(context,slot)).delete();USED.remove(marker.getString("claimNonce"));}
  }
}
