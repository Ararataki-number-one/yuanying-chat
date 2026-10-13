package local.pocketchat;

import android.app.Activity;
import android.content.Context;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.os.Build;
import android.util.AtomicFile;
import android.util.Log;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.Arrays;
import org.json.JSONArray;
import org.json.JSONObject;

/** Synthetic Android transaction/storage fixture, deliberately no web/native WAN
 * traffic. Real profile SQLite, AES-GCM and production deletion/reuse are used. */
public final class EnvironmentIntentIntegrationActivity extends Activity {
  static final String REPORT="environment-intent-results.json",TAG="PocketEnvironmentIntent";
  static final int TOTAL=43;
  final JSONArray checks=new JSONArray();Context profile;ProfileCatalog catalog;SecretStore vault;
  JSONObject buildIdentity=new JSONObject();String source="",nonce="";int passed;
  interface Work{void run()throws Exception;}
  void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));if(!pass)throw new AssertionError(name);passed++;}
  void rejects(String name,Work work)throws Exception{boolean rejected=false;try{work.run();}catch(Exception expected){rejected=true;}check(name,rejected);}
  EnvironmentSpec.Identity identity()throws Exception{return catalog.identity(5);}
  EnvironmentSpec model()throws Exception{return new EnvironmentSpecRepository(profile).load();}
  JSONObject pending()throws Exception{return NetworkChanges.pendingStrict(profile);}
  JSONObject proxy(String name){return J.obj("proxy","socks5://"+name+".synthetic.example:1080","requireExternalVpn",false);}
  String save(String name)throws Exception{return EnvironmentSpecRuntime.saveNetworkIntent(profile,identity(),"external",proxy(name),NetworkChanges.hash(profile),new JSONObject());}
  String digest(String name){return NativeNetwork.hash(proxy(name).optString("proxy"));}
  void browser(String label)throws Exception{EnvironmentSpec value=model();JSONObject browser=value.desired().browser();browser.put("intentFixtureBrowser",label);new EnvironmentSpecRepository(profile).updateDesired(value.identity,value.desiredRevision,new EnvironmentSpec.Configuration(browser,value.desired().network));}

  @Override public void onCreate(Bundle state){super.onCreate(state);new Thread(()->{
    String failure="";
    try{
      if(!"local.pocketchat.test".equals(getPackageName()))throw new SecurityException("Synthetic integration package required");
      new AtomicFile(new File(getFilesDir(),REPORT)).delete();source=getIntent().getStringExtra("sourceCommit");nonce=getIntent().getStringExtra("runNonce");buildIdentity=IntegrationBuildIdentity.read(this);
      if(source==null||!source.equals(buildIdentity.optString("sourceCommit"))||nonce==null||!nonce.matches("[0-9a-f]{32}"))throw new IOException("Exact source and fresh invocation nonce required");
      setup();failedModelAndRecovery();newerAndCancellation();deletionAndStrictReads();cacheInvalidation();
      if(passed!=TOTAL||checks.length()!=TOTAL)throw new AssertionError("Exact environment-intent checklist required: "+passed+"/"+TOTAL);
    }catch(Throwable error){failure=error.toString();}
    JSONObject result=J.obj("schema",1,"status",failure.isEmpty()?"passed":"failed","passed",passed,"total",TOTAL,"executed",checks.length(),"checks",checks,"synthetic",true,"actualAndroidExecution",true,"androidSdk",Build.VERSION.SDK_INT,"sourceCommit",source==null?"":source,"runNonce",nonce==null?"":nonce,"buildIdentity",buildIdentity,"error",failure,"scope","Real Android SQLite/Keystore staged-intent failure/recovery, exact CAS, deletion/reuse; no webpage login or WAN claim");
    try{AtomicFile report=new AtomicFile(new File(getFilesDir(),REPORT));FileOutputStream out=report.startWrite();try{out.write((result+"\n").getBytes(StandardCharsets.UTF_8));report.finishWrite(out);}catch(Throwable error){report.failWrite(out);throw error;}}
    catch(Throwable error){Log.e(TAG,"Could not preserve intent report",error);}Log.i(TAG,result.toString());
  },"environment-intent-fixture").start();}

  void setup()throws Exception{
    profile=Profiles.context(this,5);catalog=ProfileCatalog.get(this);catalog.created(0);catalog.created(5);vault=new SecretStore(profile);vault.remove("pending-network");vault.remove("environment-spec");
    SharedPreferences preferences=profile.getSharedPreferences("chat",0);if(!preferences.edit().putString("networkMode","external").putString("proxy",proxy("active").optString("proxy")).putBoolean("requireExternalVpn",false).putInt("privacyLevel",1).putBoolean("environmentInitialized",true).commit())throw new IOException("Synthetic settings could not be seeded");
    model();browser("initial browser edit");String ready=save("prior");JSONObject record=pending();
    check("Android successful save commits a ready intent",ready.equals(record.toString())&&"ready".equals(NetworkChanges.intent(record).optString("state")));
    check("Android intent binds UUID slot and generation",NetworkChanges.identityMatches(record,identity().json()));
    check("Android ready receipt is unique and has no predecessor",NetworkChanges.intent(record).optString("id").matches("[0-9a-f]{32}")&&!record.has("previousPending"));
    check("Android model mirrors committed candidate",model().desired().network.credentialRevision.equals(digest("prior")));
    check("Android save preserves latest browser JSON",model().desired().browser().optString("intentFixtureBrowser").equals("initial browser edit"));
    check("Android save does not acknowledge runtime application",model().appliedRevision==0&&model().observedRevision==0);
  }
  void failedModelAndRecovery()throws Exception{
    String privateSlot="pending-entry-subscription-abcdefghijklmnopabcdefghijklmnop";byte[] payload="previous private subscription payload".getBytes(StandardCharsets.UTF_8);JSONObject predecessor=pending();predecessor.put("entrySnapshot",privateSlot);vault.put(privateSlot,payload);vault.put("pending-network",predecessor.toString().getBytes(StandardCharsets.UTF_8));String prior=pending().toString();EnvironmentSpec valid=model();JSONObject future=valid.json();future.put("schema",99);vault.put("environment-spec",future.toString().getBytes(StandardCharsets.UTF_8));byte[] futureCipher=Files.readAllBytes(vault.file("environment-spec").toPath());
    rejects("Android model failure after staging is reported",()->save("rejected"));
    check("Android model failure restores exact previous candidate",pending().toString().equals(prior));
    check("Android model failure retains predecessor private payload",Arrays.equals(vault.get(privateSlot),payload));
    check("Android model failure never overwrites unreadable model",Arrays.equals(futureCipher,Files.readAllBytes(vault.file("environment-spec").toPath())));
    vault.put("environment-spec",valid.bytes());EnvironmentSpecRuntime.reconcileNetwork(profile,identity(),"");
    check("Android repaired model aligns with restored candidate",model().desired().network.credentialRevision.equals(digest("prior")));
    EnvironmentSpec.Identity id=identity();NetworkChanges.IntentReceipt stage=EnvironmentSpecRuntime.withIntent(profile,()->NetworkChanges.stageIntent(profile,"external",proxy("interrupted"),NetworkChanges.hash(profile),new JSONObject(),id.json(),()->EnvironmentSpecRuntime.requireIdentity(profile,id)));
    check("Android staged receipt retains predecessor for interruption",pending().getJSONObject("previousPending").toString().equals(prior));
    check("Android staging keeps private predecessor payload",Arrays.equals(vault.get(privateSlot),payload));
    EnvironmentSpecRuntime.desireNetwork(profile,id,"external",proxy("interrupted"));browser("edit after stage");EnvironmentSpecRuntime.Reconciled restored=EnvironmentSpecRuntime.reconcileNetwork(profile,id,"");
    check("Android startup recovery restores exact committed predecessor",restored.pending.toString().equals(prior));
    check("Android recovery repairs model written before interrupted promotion",model().desired().network.credentialRevision.equals(digest("prior")));
    check("Android interruption recovery preserves newer browser edit",model().desired().browser().optString("intentFixtureBrowser").equals("edit after stage"));
    check("Android interruption recovery keeps predecessor payload readable",Arrays.equals(vault.get(privateSlot),payload));
    save("committed-replacement");check("Android committed replacement releases predecessor private payload",vault.get(privateSlot)==null);
  }
  void newerAndCancellation()throws Exception{
    EnvironmentSpec.Identity id=identity();NetworkChanges.IntentReceipt older=EnvironmentSpecRuntime.withIntent(profile,()->NetworkChanges.stageIntent(profile,"external",proxy("old-stage"),NetworkChanges.hash(profile),new JSONObject(),id.json(),()->EnvironmentSpecRuntime.requireIdentity(profile,id)));
    NetworkChanges.save(profile,"external",proxy("newer"),NetworkChanges.hash(profile));String newer=pending().toString();boolean withdrawn=NetworkChanges.rollbackIntent(profile,older,()->EnvironmentSpecRuntime.requireIdentity(profile,id));EnvironmentSpecRuntime.reconcileNetwork(profile,id,"");
    check("Android rollback refuses an older exact receipt",!withdrawn&&pending().toString().equals(newer));
    check("Android newer publication becomes desired network",model().desired().network.credentialRevision.equals(digest("newer")));
    check("Android legacy candidate remains byte stable after reconciliation",NetworkChanges.intent(pending())==null&&pending().toString().equals(newer));
    NetworkChanges.save(profile,"external",proxy("newest"),NetworkChanges.hash(profile));String newest=pending().toString();boolean cancelled=EnvironmentSpecRuntime.cancelNetworkIntent(profile,id,newer);
    check("Android cancellation cannot clear newer candidate",!cancelled&&pending().toString().equals(newest));
    check("Android superseded cancellation reconciles newest route",model().desired().network.credentialRevision.equals(digest("newest")));
    browser("keep browser on cancel");EnvironmentSpec active=model();JSONObject future=active.json();future.put("schema",99);vault.put("environment-spec",future.toString().getBytes(StandardCharsets.UTF_8));
    rejects("Android cancellation model failure is reported",()->EnvironmentSpecRuntime.cancelNetworkIntent(profile,id,newest));
    check("Android cancellation remains authoritative after model failure",pending().length()==0);
    vault.put("environment-spec",active.bytes());EnvironmentSpecRuntime.reconcileNetwork(profile,id,"");
    check("Android startup repairs model after candidate removal",model().desired().network.credentialRevision.equals(digest("active")));
    check("Android cancellation recovery retains browser edit",model().desired().browser().optString("intentFixtureBrowser").equals("keep browser on cancel"));
  }
  void deletionAndStrictReads()throws Exception{
    EnvironmentSpec.Identity removed=identity();String old=save("deleted");catalog.beginDelete(5);EnvironmentDeleteActivity.remove(this,5);Profiles.prepare(Profiles.context(this,0),5,false);profile=Profiles.context(this,5);vault=new SecretStore(profile);model();String replacement=save("replacement");
    check("Android production deletion and reuse creates a new identity",!identity().environmentId.equals(removed.environmentId)&&identity().generation==removed.generation+1);
    rejects("Android old identity cannot publish to reused environment",()->EnvironmentSpecRuntime.saveNetworkIntent(profile,removed,"external",proxy("stale"),NetworkChanges.hash(profile),new JSONObject()));
    rejects("Android old identity cannot cancel replacement candidate",()->EnvironmentSpecRuntime.cancelNetworkIntent(profile,removed,old));
    rejects("Android old identity cannot reconcile reused model",()->EnvironmentSpecRuntime.reconcileNetwork(profile,removed,""));
    check("Android stale callbacks retain replacement pending and model",pending().toString().equals(replacement)&&model().desired().network.credentialRevision.equals(digest("replacement")));
    byte[] corrupt="{broken".getBytes(StandardCharsets.UTF_8);vault.put("pending-network",corrupt);rejects("Android malformed pending blocks recovery",()->EnvironmentSpecRuntime.reconcileNetwork(profile,identity(),""));
    check("Android malformed pending bytes remain intact",Arrays.equals(corrupt,vault.get("pending-network")));
    vault.remove("pending-network");EnvironmentSpecRuntime.reconcileNetwork(profile,identity(),"");
    check("Android intent fixture leaves other environment intact",catalog.item(0).optBoolean("created"));
  }
  void cacheInvalidation()throws Exception{
    EnvironmentSpec.Identity id=identity();EnvironmentSpecRuntime.Reconciled initial=EnvironmentSpecRuntime.reconcileNetwork(profile,id,"");String activeRevision=model().desired().network.credentialRevision;
    check("Android unchanged authority and authenticated model use confirmed cache",EnvironmentSpecRuntime.reconcileNetwork(profile,id,initial.proof).spec==null);
    EnvironmentSpec before=model();JSONObject browser=before.desired().browser();browser.put("intentFixtureBrowser","independent model writer");new EnvironmentSpecRepository(profile).updateDesired(id,before.desiredRevision,new EnvironmentSpec.Configuration(browser,EnvironmentSpecRuntime.binding(id,"external",new JSONObject(),proxy("foreign").optString("proxy"))));
    EnvironmentSpecRuntime.Reconciled aligned=EnvironmentSpecRuntime.reconcileNetwork(profile,id,initial.proof);
    check("Android independent network model write invalidates cache",aligned.spec!=null&&model().desired().network.credentialRevision.equals(activeRevision));
    check("Android cached repair retains independent browser edit",model().desired().browser().optString("intentFixtureBrowser").equals("independent model writer"));
    byte[] authenticated=Files.readAllBytes(vault.file("environment-spec").toPath());JSONObject future=model().json();future.put("schema",99);vault.put("environment-spec",future.toString().getBytes(StandardCharsets.UTF_8));byte[] futureCipher=Files.readAllBytes(vault.file("environment-spec").toPath());
    rejects("Android future schema invalidates confirmed idle cache",()->EnvironmentSpecRuntime.reconcileNetwork(profile,id,aligned.proof));
    check("Android cached future model remains encrypted and untouched",Arrays.equals(futureCipher,Files.readAllBytes(vault.file("environment-spec").toPath())));
    byte[] corrupt=authenticated.clone();corrupt[corrupt.length-1]^=1;SealedFileIo.publish(vault.file("environment-spec"),corrupt);
    rejects("Android authentication failure invalidates confirmed idle cache",()->EnvironmentSpecRuntime.reconcileNetwork(profile,id,aligned.proof));
    check("Android cached authentication failure preserves ciphertext",Arrays.equals(corrupt,Files.readAllBytes(vault.file("environment-spec").toPath())));
    SealedFileIo.publish(vault.file("environment-spec"),authenticated);
    check("Android restored authenticated bytes restore verified cache",EnvironmentSpecRuntime.reconcileNetwork(profile,id,aligned.proof).spec==null);
  }
}
