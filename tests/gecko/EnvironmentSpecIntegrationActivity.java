package local.pocketchat;

import android.app.Activity;
import android.content.Context;
import android.content.ContextWrapper;
import android.content.SharedPreferences;
import android.database.Cursor;
import android.database.DatabaseErrorHandler;
import android.database.sqlite.SQLiteDatabase;
import android.os.Bundle;
import android.util.AtomicFile;
import android.util.Log;
import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.Arrays;
import org.json.JSONArray;
import org.json.JSONObject;

/** Synthetic integration variant only. Exercises real SQLite migration, Android
 * Keystore/AtomicFile, and production deletion/reuse. Never run against user data. */
public final class EnvironmentSpecIntegrationActivity extends Activity {
  int checks;
  final JSONArray assertions=new JSONArray();
  interface Work{void run()throws Exception;}
  void check(String message,boolean valid){assertions.put(J.obj("name",message,"pass",valid));if(!valid)throw new AssertionError(message);checks++;}
  void rejects(String message,Work work)throws Exception{boolean rejected=false;try{work.run();}catch(Exception expected){rejected=true;}check(message,rejected);}
  @Override public void onCreate(Bundle state){super.onCreate(state);new Thread(()->{
    JSONObject result=J.obj("schema",1,"status","failed","synthetic",true,"actualAndroidExecution",true,
      "syntheticAcknowledgementsOnly",true,"realAccountLogin",false,"webpageFingerprintAcceptance",false,
      "scope","Android SQLite v6→v7, sealed config migration and deletion/reuse; synthetic repository acknowledgements, no webpage fingerprint or real account/WAN claim");
    try{
      if(!getPackageName().equals("local.pocketchat.test"))throw new IOException("Synthetic integration package required");
      new File(getFilesDir(),"environment-spec-results.json").delete();
      JSONObject identity=IntegrationBuildIdentity.read(this);String source=getIntent().getStringExtra("sourceCommit"),nonce=getIntent().getStringExtra("runNonce");
      if(source==null||!source.equals(identity.optString("sourceCommit"))||nonce==null||!nonce.matches("[0-9a-f]{32}"))throw new IOException("Exact source and fresh invocation nonce required");
      NetworkCatalog.put(result,"sourceCommit",source);NetworkCatalog.put(result,"runNonce",nonce);NetworkCatalog.put(result,"buildIdentity",identity);
      NetworkCatalog.put(result,"androidSdk",android.os.Build.VERSION.SDK_INT);NetworkCatalog.put(result,"deviceAbi",android.os.Build.SUPPORTED_ABIS[0]);
      schemaUpgrade();runtimeReceiptBinding();repositoryLifecycle();
      NetworkCatalog.put(result,"status","passed");
    }catch(Throwable failure){NetworkCatalog.put(result,"error",failure.toString());}
    NetworkCatalog.put(result,"passed",checks);NetworkCatalog.put(result,"total",assertions.length());NetworkCatalog.put(result,"checks",assertions);
    try{AtomicFile report=new AtomicFile(new File(getFilesDir(),"environment-spec-results.json"));java.io.FileOutputStream out=report.startWrite();try{out.write((result.toString()+"\n").getBytes(StandardCharsets.UTF_8));report.finishWrite(out);}catch(Throwable failure){report.failWrite(out);throw failure;}}
    catch(Throwable failure){Log.e("PocketEnvironmentSpec","Synthetic report publication failed",failure);}
    Log.i("PocketEnvironmentSpec",result.toString());
  },"environment-spec-fixture").start();}

  void schemaUpgrade()throws Exception{
    CatalogContext isolated=new CatalogContext(this);File path=isolated.getDatabasePath("environment-catalog.db");
    isolated.deleteDatabase("environment-catalog.db");
    try(SQLiteDatabase old=isolated.openOrCreateDatabase("environment-catalog.db",0,null)){
      old.execSQL("CREATE TABLE environments (slot INTEGER PRIMARY KEY,name TEXT NOT NULL,created INTEGER NOT NULL DEFAULT 0,draft TEXT NOT NULL DEFAULT '',pid INTEGER NOT NULL DEFAULT 0,seen INTEGER NOT NULL DEFAULT 0,connected INTEGER NOT NULL DEFAULT 0,waiting INTEGER NOT NULL DEFAULT 0,mode TEXT NOT NULL DEFAULT '',privacy INTEGER NOT NULL DEFAULT 1,opened INTEGER NOT NULL DEFAULT 0,favorite INTEGER NOT NULL DEFAULT 0,problem TEXT NOT NULL DEFAULT '',page TEXT NOT NULL DEFAULT '原网页',group_name TEXT NOT NULL DEFAULT '',notes TEXT NOT NULL DEFAULT '',desktop INTEGER NOT NULL DEFAULT 0,generation INTEGER NOT NULL DEFAULT 0,deleting INTEGER NOT NULL DEFAULT 0)");
      old.execSQL("CREATE TABLE app_settings(name TEXT PRIMARY KEY,value TEXT NOT NULL)");
      old.execSQL("INSERT INTO environments(slot,name,created,draft,desktop,generation) VALUES(0,'existing profile',1,'draft preserved',1,12)");
      old.execSQL("INSERT INTO environments(slot,name,created,generation) VALUES(1,'second profile',1,3)");old.setVersion(6);
    }
    String firstId;
    try(ProfileCatalog upgraded=new ProfileCatalog(isolated)){
      JSONObject first=upgraded.item(0);firstId=first.getString("environmentId");
      check("Production SQLiteOpenHelper upgrades schema6 through schema7 to schema8",upgraded.getReadableDatabase().getVersion()==8&&!first.optBoolean("resetting"));
      check("Upgrade retains existing fields and generation",first.optString("name").equals("existing profile")&&first.optString("draft").equals("draft preserved")&&first.optBoolean("desktopSite")&&first.optInt("generation")==12);
      check("Existing profiles obtain different stable UUIDs",!firstId.isEmpty()&&!firstId.equals(upgraded.item(1).optString("environmentId")));
      check("Existing identity token is admitted",upgraded.withIdentity(upgraded.identity(0),()->true));
    }
    try(ProfileCatalog reopened=new ProfileCatalog(isolated)){check("UUID remains stable on database reopen",firstId.equals(reopened.identity(0).environmentId));}
    // Independently exercise a shipped schema7 database: UUID must not regenerate.
    isolated.deleteDatabase("environment-catalog.db");
    try(SQLiteDatabase seven=isolated.openOrCreateDatabase("environment-catalog.db",0,null)){
      seven.execSQL("CREATE TABLE environments (slot INTEGER PRIMARY KEY,name TEXT NOT NULL,created INTEGER NOT NULL DEFAULT 0,draft TEXT NOT NULL DEFAULT '',pid INTEGER NOT NULL DEFAULT 0,seen INTEGER NOT NULL DEFAULT 0,connected INTEGER NOT NULL DEFAULT 0,waiting INTEGER NOT NULL DEFAULT 0,mode TEXT NOT NULL DEFAULT '',privacy INTEGER NOT NULL DEFAULT 1,opened INTEGER NOT NULL DEFAULT 0,favorite INTEGER NOT NULL DEFAULT 0,problem TEXT NOT NULL DEFAULT '',page TEXT NOT NULL DEFAULT '原网页',group_name TEXT NOT NULL DEFAULT '',notes TEXT NOT NULL DEFAULT '',desktop INTEGER NOT NULL DEFAULT 0,generation INTEGER NOT NULL DEFAULT 0,deleting INTEGER NOT NULL DEFAULT 0,environment_id TEXT NOT NULL DEFAULT '')");seven.execSQL("CREATE TABLE app_settings(name TEXT PRIMARY KEY,value TEXT NOT NULL)");
      android.content.ContentValues values=new android.content.ContentValues();values.put("slot",0);values.put("name","existing schema7 profile");values.put("created",1);values.put("generation",12);values.put("environment_id",firstId);seven.insertOrThrow("environments",null,values);seven.setVersion(7);
    }
    try(ProfileCatalog upgradedSeven=new ProfileCatalog(isolated)){check("Production schema7 upgrades to schema8 without changing identity",upgradedSeven.getReadableDatabase().getVersion()==8&&upgradedSeven.identity(0).environmentId.equals(firstId));check("Schema7 upgrade starts with no pending login reset",!upgradedSeven.item(0).optBoolean("resetting"));}
    isolated.deleteDatabase("environment-catalog.db");
  }

  void runtimeReceiptBinding()throws Exception{
    EnvironmentSpec.Identity id=new EnvironmentSpec.Identity(6,1,java.util.UUID.randomUUID().toString());
    JSONObject subscribed=J.obj("subscriptionUrl","https://synthetic.example/entry","entrySubscriptionId","entry-fixture","entrySubscriptionAddressRevision",2,"entryNodeKey",NativeNetwork.hash("entry-node"),"entry","Entry|fixture","entryMode","latency","entryPool",J.arr("Entry|fixture"),"entryPoolKeys",J.arr(NativeNetwork.hash("entry-node")),"exitSource","subscription","exitSubscriptionId","exit-fixture","exitSubscriptionUrl","https://synthetic.example/exit","exitSubscriptionAddressRevision",3,"exitNodeKey",NativeNetwork.hash("exit-node"),"exitNodeName","Exit|fixture");
    EnvironmentSpec.NetworkBinding route=EnvironmentSpecRuntime.binding(id,"internal",subscribed,"");
    check("Desired subscribed route accepts no manual host",route.exitNodeId.equals(subscribed.optString("exitNodeKey"))&&route.exitSourceId.equals("exit-fixture"));
    check("Model uses the native fixed-exit receipt identity",route.credentialRevision.equals(NativeNetwork.exitIdentity(subscribed)));
    check("Model uses the native saved transport fingerprint",route.entryConfigRevision.equals(NativeNetwork.transportFingerprint(subscribed)));
    JSONObject changed=J.parse(subscribed.toString());changed.put("exitSubscriptionAddressRevision",4);
    check("New exit address revision cannot match prior native receipt",!route.entryConfigRevision.equals(EnvironmentSpecRuntime.binding(id,"internal",changed,"").entryConfigRevision));
    EnvironmentSpec.NetworkBinding external=EnvironmentSpecRuntime.binding(id,"external",subscribed,"http://proxy.synthetic:8080");
    check("External runtime binding ignores inactive internal route",external.entrySourceId.isEmpty()&&external.exitSourceId.isEmpty());
  }

  void repositoryLifecycle()throws Exception{
    Context profile=Profiles.context(this,6);ProfileCatalog catalog=ProfileCatalog.get(this);catalog.created(0);catalog.created(6);
    SecretStore vault=new SecretStore(profile);new AtomicFile(vault.file(EnvironmentSpecRepository.STORE)).delete();
    SharedPreferences preferences=profile.getSharedPreferences("chat",0);
    preferences.edit().putInt("privacyLevel",2).putString("networkMode","internal").putBoolean("environmentInitialized",true).putString("fixtureLoginMarker","preserved").commit();
    catalog.browserDisplay(6,true);
    vault.save(J.obj("subscriptionUrl","https://synthetic.example/sub","exitHost","synthetic-exit.example","exitPort",1080,"exitUser","fixture-user","exitPassword","fixture-password","entry","synthetic entry","entryMode","manual"));
    vault.put("environment-fixture","private state retained".getBytes(StandardCharsets.UTF_8));
    File browserMarker=new File(profile.getNoBackupFilesDir(),"gecko-browser/spec-fixture-marker");browserMarker.getParentFile().mkdirs();Files.write(browserMarker.toPath(),"existing browser directory".getBytes(StandardCharsets.UTF_8));
    EnvironmentSpecRepository repository=new EnvironmentSpecRepository(profile);EnvironmentSpec migrated=repository.load();
    check("First sealed migration matches actual NativeNetwork receipt binding",migrated.desired().network.entryConfigRevision.equals(NativeNetwork.transportFingerprint(vault.settings()))&&migrated.desired().network.credentialRevision.equals(NativeNetwork.exitIdentity(vault.settings())));
    check("Migration preserves real profile storage and old encrypted data",browserMarker.isFile()&&"private state retained".equals(new String(vault.get("environment-fixture"),StandardCharsets.UTF_8))&&preferences.getString("fixtureLoginMarker","").equals("preserved"));
    check("Migrated settings remain desired until runtime acknowledgement",migrated.appliedRevision==0&&migrated.desired().browser().optString("display").equals("desktop")&&migrated.desired().browser().optString("privacy").equals("native-rfp"));
    byte[] cipher=Files.readAllBytes(vault.file(EnvironmentSpecRepository.STORE).toPath());
    check("Actual saved file is encrypted rather than clear JSON",!new String(cipher,StandardCharsets.UTF_8).contains(migrated.identity.environmentId));
    // Synthetic acknowledgement tests persistence protocol only. It is explicitly
    // not a claim that a Gecko runtime accepted this fixture's browser settings.
    EnvironmentSpec applied=repository.markApplied(migrated.identity,migrated.desiredRevision,"synthetic-repository-ack");
    check("Real Keystore roundtrip retains applied/desired separation",new EnvironmentSpecRepository(profile).load().appliedRevision==1&&applied.observedRevision==0);
    EnvironmentSpec observed=repository.recordObservation(applied.identity,1,J.obj("fixture",true));
    check("Observation acknowledgement roundtrips separately",repository.load().observedRevision==1);
    EnvironmentApplyCoordinator coordinator=new EnvironmentApplyCoordinator(repository);
    EnvironmentApplyCoordinator.Prepared deferred=coordinator.prepare(true);
    rejects("Busy apply preparation cannot acknowledge changes",()->coordinator.acknowledge(deferred,"synthetic-repository-ack"));
    EnvironmentApplyCoordinator.Prepared old=coordinator.prepare(false);
    JSONObject browser=J.obj("schema",1,"templateId","standard-mobile","display","mobile","privacy","standard","locales",new org.json.JSONArray(),"timezoneStrategy","system");
    EnvironmentSpec changed=repository.updateDesired(observed.identity,1,new EnvironmentSpec.Configuration(browser,observed.desired().network));
    check("Pending desired config preserves prior applied snapshot",changed.desiredRevision==2&&changed.appliedRevision==1&&changed.observedRevision==1);
    rejects("A second repository cannot overwrite a newer desired revision",()->new EnvironmentSpecRepository(profile).updateDesired(observed.identity,1,observed.desired()));
    rejects("Late prepared callback cannot acknowledge a superseded revision",()->coordinator.acknowledge(old,"synthetic-repository-ack"));
    repository.markApplied(changed.identity,2,"synthetic-repository-ack");
    rejects("Late observation cannot cross applied revisions",()->repository.recordObservation(changed.identity,1,J.obj("late",true)));

    EnvironmentSpec valid=repository.load();JSONObject future=valid.json();future.put("schema",99);vault.put(EnvironmentSpecRepository.STORE,future.toString().getBytes(StandardCharsets.UTF_8));
    byte[] futureCipher=Files.readAllBytes(vault.file(EnvironmentSpecRepository.STORE).toPath());
    rejects("Future schema is rejected without fallback defaults",repository::load);
    check("Future schema ciphertext is not overwritten",Arrays.equals(futureCipher,Files.readAllBytes(vault.file(EnvironmentSpecRepository.STORE).toPath())));
    vault.put(EnvironmentSpecRepository.STORE,valid.bytes());
    byte[] corrupt=Files.readAllBytes(vault.file(EnvironmentSpecRepository.STORE).toPath());corrupt[corrupt.length-1]^=1;Files.write(vault.file(EnvironmentSpecRepository.STORE).toPath(),corrupt);
    rejects("Authenticated ciphertext corruption is rejected",repository::load);
    check("Corrupt ciphertext is not overwritten",Arrays.equals(corrupt,Files.readAllBytes(vault.file(EnvironmentSpecRepository.STORE).toPath())));
    vault.put(EnvironmentSpecRepository.STORE,valid.bytes());
    File sealed=vault.file(EnvironmentSpecRepository.STORE),backup=new File(sealed.getPath()+".bak");
    check("AtomicFile interruption fixture prepared",sealed.renameTo(backup));
    check("Only-backup AtomicFile recovers without resetting state",repository.load().identity.equals(valid.identity)&&sealed.exists()&&!backup.exists());

    EnvironmentSpec.Identity removed=valid.identity;catalog.beginDelete(6);EnvironmentDeleteActivity.remove(this,6);
    rejects("Old identity cannot write after deletion",()->repository.markApplied(removed,2,"synthetic-repository-ack"));
    check("Production deletion removes sealed state",!vault.file(EnvironmentSpecRepository.STORE).exists());
    Profiles.prepare(Profiles.context(this,0),6,false);EnvironmentSpec reused=new EnvironmentSpecRepository(Profiles.context(this,6)).load();
    check("Reused slot has a new UUID and generation",!reused.identity.environmentId.equals(removed.environmentId)&&reused.identity.generation==removed.generation+1);
    rejects("Old async identity cannot alter reused slot",()->repository.updateDesired(removed,2,valid.desired()));
    check("Other environment remains created",catalog.item(0).optBoolean("created"));
  }
  static final class CatalogContext extends ContextWrapper {
    CatalogContext(Context base){super(base);}
    String name(String value){return "spec-upgrade-fixture-"+value;}
    @Override public File getDatabasePath(String name){return getBaseContext().getDatabasePath(name(name));}
    @Override public SQLiteDatabase openOrCreateDatabase(String name,int mode,SQLiteDatabase.CursorFactory factory){return getBaseContext().openOrCreateDatabase(name(name),mode,factory);}
    @Override public SQLiteDatabase openOrCreateDatabase(String name,int mode,SQLiteDatabase.CursorFactory factory,DatabaseErrorHandler handler){return getBaseContext().openOrCreateDatabase(name(name),mode,factory,handler);}
    @Override public boolean deleteDatabase(String name){return getBaseContext().deleteDatabase(name(name));}
  }
}
