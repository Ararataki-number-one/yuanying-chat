package local.pocketchat;

import android.app.Activity;
import android.os.Bundle;
import android.util.Log;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;

/** Actual storage/process cleanup through the production implementation, using synthetic data. */
public final class EnvironmentManagementIntegrationActivity extends Activity {
  @Override public void onCreate(Bundle state){super.onCreate(state);run(getIntent().getStringExtra("managementAction"));}
  @Override protected void onNewIntent(android.content.Intent i){super.onNewIntent(i);setIntent(i);run(i.getStringExtra("managementAction"));}
  void run(String action){new Thread(()->{JSONObject result=new JSONObject();try{
    android.content.Context zero=Profiles.context(this,0),one=Profiles.context(this,1);ProfileCatalog catalog=ProfileCatalog.get(this);
    if("copyAndReset".equals(action)){
      EnvironmentSpecRepository source=new EnvironmentSpecRepository(one);EnvironmentSpec old=source.load();
      JSONObject browser=BrowserIdentitySpec.preset(BrowserIdentitySpec.DESKTOP).withLocales(java.util.Arrays.asList("ja-JP","en-US")).json();EnvironmentSpecRuntime.desireBrowser(one,browser);
      Profiles.copyConfiguration(one,2);android.content.Context copy=Profiles.context(this,2);EnvironmentSpec cloned=new EnvironmentSpecRepository(copy).load();
      result=J.obj("action",action,"templateCopied",new EnvironmentSpec.Configuration(browser,cloned.desired().network).equals(cloned.desired()),"newIdentity",!cloned.identity.environmentId.equals(old.identity.environmentId),"freshAcknowledgements",cloned.appliedRevision==0&&cloned.observedRevision==0,"browserDataNotCopied",!new File(copy.getNoBackupFilesDir(),"gecko-browser").exists()&&!new File(copy.getNoBackupFilesDir(),"gecko-session.json").exists(),"draftNotCopied",!copy.getSharedPreferences("chat",0).contains("pending")&&!copy.getSharedPreferences("chat",0).contains("draft"),"sourceIdentityKept",catalog.identity(1).equals(old.identity));
      boolean occupiedRejected=false;try{Profiles.copyConfiguration(one,2);}catch(Exception expected){occupiedRejected=true;}NetworkCatalog.put(result,"occupiedTargetRejected",occupiedRejected);
      catalog.beginDelete(2);EnvironmentDeleteActivity.remove(this,2);
      // An interrupted pre-birth copy can leave a sealed spec despite SQL rollback.
      new SecretStore(copy).put(EnvironmentSpecRepository.STORE,cloned.bytes());Profiles.prepare(one,2,false);NetworkCatalog.put(result,"failedCopyThenOrdinaryCreation",!new EnvironmentSpecRepository(copy).load().identity.environmentId.equals(cloned.identity.environmentId));catalog.beginDelete(2);EnvironmentDeleteActivity.remove(this,2);
      // Copy persistence owns its own assertions above. Keep the original
      // controlled fixture template for the separate reset/cookie test.
      EnvironmentSpecRuntime.desireBrowser(one,old.desired().browser());
      new SecretStore(one).put("lifecycle-marker","keep-configuration-secret".getBytes(StandardCharsets.UTF_8));byte[] marker=java.nio.file.Files.readAllBytes(new SecretStore(one).file("lifecycle-marker").toPath());
      one.getSharedPreferences("chat",0).edit().putString("draft","clear-reset-draft").putString("draftBackup:fixture","clear-backup").putString("pending",J.obj("id","old-reset-task","kind","web").toString()).putBoolean("replyNotice",false).commit();
      String proxy=one.getSharedPreferences("chat",0).getString("proxy","");JSONObject candidate=J.obj("proxy",proxy,"requireExternalVpn",false);
      EnvironmentResetPlan staged=EnvironmentSpecRuntime.withIntent(one,()->{EnvironmentSpecRuntime.saveNetworkIntent(one,old.identity,"external",candidate,NetworkChanges.hash(one),new JSONObject());return EnvironmentResetActivity.begin(this,old.identity);});EnvironmentSpec before=staged.before;JSONObject paused=catalog.item(1);
      NetworkCatalog.put(result,"resetKeepsLogicalId",paused.optBoolean("created")&&!paused.optBoolean("deleting")&&paused.optBoolean("resetting")&&paused.optString("environmentId").equals(before.identity.environmentId));NetworkCatalog.put(result,"resetAdvancesGeneration",paused.optInt("generation")==before.identity.generation+1);
      boolean blocked=false;try{catalog.identity(1);}catch(IOException expected){blocked=true;}NetworkCatalog.put(result,"pausedIdentityRejected",blocked);
      EnvironmentResetActivity.reset(this,before.identity);EnvironmentSpec after=source.load();
      NetworkCatalog.put(result,"configurationPreserved",after.desired().equals(before.desired()));NetworkCatalog.put(result,"resetAppliedEvidenceRetired",after.appliedRevision==0&&after.observedRevision==0);NetworkCatalog.put(result,"pendingNetworkRebound",NetworkChanges.identityMatches(NetworkChanges.pendingStrict(one),after.identity.json())&&NetworkChanges.pendingStrict(one).getJSONObject("config").toString().equals(candidate.toString()));
      NetworkCatalog.put(result,"networkSecretUnchanged",java.util.Arrays.equals(marker,java.nio.file.Files.readAllBytes(new SecretStore(one).file("lifecycle-marker").toPath())));NetworkCatalog.put(result,"preferencesKept",!one.getSharedPreferences("chat",0).getBoolean("replyNotice",true));NetworkCatalog.put(result,"draftAndTaskCleared",!one.getSharedPreferences("chat",0).contains("draft")&&!one.getSharedPreferences("chat",0).contains("draftBackup:fixture")&&!one.getSharedPreferences("chat",0).contains("pending"));
      boolean staleRejected=false;try{source.updateDesired(before.identity,before.desiredRevision,before.desired());}catch(Exception expected){staleRejected=true;}NetworkCatalog.put(result,"oldConfigurationCallbackRejected",staleRejected);
      android.content.ContentValues late=new android.content.ContentValues();late.put("pid",987654);Long prior; synchronized(catalog.heartbeatGate){prior=catalog.heartbeatRevisions.put(1,90000L);}catalog.writeHeartbeat(new ProfileCatalog.Heartbeat(1,before.identity.generation,90000,late));NetworkCatalog.put(result,"oldHeartbeatRejected",catalog.item(1).optInt("pid")!=987654);synchronized(catalog.heartbeatGate){if(prior==null)catalog.heartbeatRevisions.remove(1);else catalog.heartbeatRevisions.put(1,prior);}
      File fresh=new File(one.getNoBackupFilesDir(),"gecko-browser/fresh-login-marker");fresh.getParentFile().mkdirs();java.nio.file.Files.write(fresh.toPath(),new byte[]{1});boolean expired=false;try{EnvironmentResetActivity.reset(this,before.identity);}catch(EnvironmentResetActivity.Expired expected){expired=true;}NetworkCatalog.put(result,"duplicateResetCannotClearNewLogin",expired&&fresh.isFile());fresh.delete();NetworkCatalog.put(result,"retryCompleted",!catalog.item(1).optBoolean("resetting")&&after.identity.equals(staged.next));
    }else if("resetZero".equals(action)){
      File shared=new File(zero.getNoBackupFilesDir(),"reset-shared-marker"),other=new File(one.getNoBackupFilesDir(),"reset-other-marker"),saved=new File(zero.getFilesDir(),"saved-downloads/reset-saved.txt");saved.getParentFile().mkdirs();java.nio.file.Files.write(shared.toPath(),new byte[]{1});java.nio.file.Files.write(other.toPath(),new byte[]{2});java.nio.file.Files.write(saved.toPath(),new byte[]{3});
      EnvironmentSpec before=new EnvironmentSpecRepository(zero).load();int defaultBefore=AppSettings.defaultSlot(this);EnvironmentResetActivity.reset(this,before.identity);EnvironmentSpec after=new EnvironmentSpecRepository(zero).load();result=J.obj("action",action,"identityKept",after.identity.environmentId.equals(before.identity.environmentId)&&after.identity.generation==before.identity.generation+1,"configurationKept",after.desired().equals(before.desired()),"sharedRootKept",shared.isFile(),"otherEnvironmentKept",other.isFile(),"savedDownloadsKept",saved.isFile(),"defaultKept",defaultBefore==AppSettings.defaultSlot(this));
    }else if("deleteOne".equals(action)){
      catalog.created(0);catalog.created(1);zero.getSharedPreferences("chat",0).edit().putString("managementMarker","kept-zero").commit();one.getSharedPreferences("chat",0).edit().putString("managementMarker","remove-one").commit();
      new SecretStore(one).put("exit-region","synthetic-private-data".getBytes(StandardCharsets.UTF_8));
      java.io.File saved=new File(one.getFilesDir(),"saved-downloads/synthetic/saved.txt");saved.getParentFile().mkdirs();java.nio.file.Files.write(saved.toPath(),"keep-saved-file".getBytes(StandardCharsets.UTF_8));
      java.nio.file.Path dangling=new File(one.getNoBackupFilesDir(),"synthetic-dangling-lock").toPath();java.nio.file.Files.createSymbolicLink(dangling,java.nio.file.Paths.get("nonexistent-browser-lock-target"));
      EnvironmentSpec old=new EnvironmentSpecRepository(one).load();int generation=catalog.item(1).optInt("generation");catalog.beginDelete(1);EnvironmentDeleteActivity.remove(this,1);
      result=J.obj("action",action,"removed",!catalog.item(1).optBoolean("created")&&!catalog.item(1).optBoolean("deleting"),"generationChanged",catalog.item(1).optInt("generation")==generation+1,"privateDataGone",!new SecretStore(one).file("exit-region").exists()&&!one.getSharedPreferences("chat",0).contains("managementMarker"),"otherEnvironmentKept","kept-zero".equals(zero.getSharedPreferences("chat",0).getString("managementMarker","")),"savedFileKept",saved.isFile(),"danglingLockRemoved",!java.nio.file.Files.isSymbolicLink(dangling));
      Profiles.prepare(zero,1,false);NetworkCatalog.put(result,"slotReusable",catalog.item(1).optBoolean("created")&&one.getSharedPreferences("chat",0).getBoolean("environmentInitialized",false));
      EnvironmentSpec replacement=new EnvironmentSpecRepository(one).load();NetworkCatalog.put(result,"slotReuseNewIdentity",!replacement.identity.environmentId.equals(old.identity.environmentId));boolean staleRejected=false;try{new EnvironmentSpecRepository(one).updateDesired(old.identity,old.desiredRevision,old.desired());}catch(Exception expected){staleRejected=true;}NetworkCatalog.put(result,"slotReuseOldCallbackRejected",staleRejected);
    }else if("deleteZero".equals(action)){
      one.getSharedPreferences("chat",0).edit().putString("managementMarker","kept-one").commit();Profiles.global(this).getSharedPreferences("app-updates",0).edit().putString("managementMarker","kept-updates").commit();
      NetworkCatalog library=new NetworkCatalog(this);JSONObject exit=library.addExit("synthetic shared exit","日本","example.test",1080,"",""),sub=library.addSubscription("synthetic shared subscription","https://example.test/subscription");library.parsed(sub.optString("id"),J.arr("大阪 03"),"synthetic cache".getBytes(StandardCharsets.UTF_8),123);
      catalog.beginDelete(0);EnvironmentDeleteActivity.remove(this,0);NetworkCatalog after=new NetworkCatalog(this);
      result=J.obj("action",action,"removed",!catalog.item(0).optBoolean("created"),"otherEnvironmentKept","kept-one".equals(one.getSharedPreferences("chat",0).getString("managementMarker","")),"updateSettingsKept","kept-updates".equals(Profiles.global(this).getSharedPreferences("app-updates",0).getString("managementMarker","")),"libraryKept",after.exit(exit.optString("id"))!=null&&after.subscription(sub.optString("id"))!=null&&after.cache(after.subscription(sub.optString("id")))!=null,"defaultReassigned",AppSettings.defaultSlot(this)==1);
      boolean lastProtected=false;try{catalog.beginDelete(1);}catch(IOException expected){lastProtected=true;}NetworkCatalog.put(result,"lastEnvironmentProtected",lastProtected);
    }else throw new IllegalArgumentException();
  }catch(Exception e){result=J.obj("action",action,"error",e.toString());}Log.i("PocketEnvironmentManagement",result.toString());},"management-fixture").start();}
}
