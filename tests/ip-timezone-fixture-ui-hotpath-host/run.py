#!/usr/bin/env python3
"""Actual Application/context/Repository entry hot-path and fresh-owner host controls."""
import argparse,hashlib,importlib.util,json,os,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
OLD=ROOT/'tests/ip-timezone-fixture-setup-host/run.py'
spec=importlib.util.spec_from_file_location('setup_type_boundaries_for_ui',OLD);old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
BASE_SOURCE='c5c539f75d4e95baa12b56593e59054615f0efde'
BASE_APPLICATION='package local.pocketchat;\n\nimport android.content.Context;\n\n/** Integration-only explicit policy setup. Production has no fixture branch. */\npublic final class IpTimeZoneFixtureApplication extends PocketApplication {\n  private volatile boolean initializing=true;\n  @Override public void onCreate(){\n    super.onCreate();\n    // Retain the original package rejection before any process early return.\n    IpTimeZoneFixtureScopes.integration(this);\n    // SDK content/socket/isolated children inherit this test Application. They\n    // must retain the production parent path without fixture catalog/vault IO.\n    android.content.pm.ApplicationInfo application=getApplicationInfo();\n    if(application==null||android.os.Process.myUid()!=application.uid)return;\n    String process=android.app.Application.getProcessName();\n    if(!fixtureProcess(getPackageName(),process,Profiles.processSlot()))return;\n    IpTimeZoneFixtureScopes.declaredGeneric(this);\n    // The scope provider must reserve its nonce before even catalog creation\n    // can enumerate slot6 preferences. It never starts a browser/session.\n    if(IpTimeZoneFixtureScopes.setupProcess(this))return;\n    // Finish catalog creation while reentrant profile() calls are inert.\n    ProfileCatalog.get(this).getWritableDatabase();\n    initializing=false;\n    for(int slot=0;slot<Profiles.MAX;slot++)if(ProfileCatalog.get(this).available(slot))profile(slot);\n  }\n  static final String[] LEGACY_FIXTURE_PROCESSES={":caret_controlled_ime",":environment_intent_fixture",":environment_spec_fixture",":extension_upgrade_test",":fingerprint_followups",":identity_prototype",":management_test",":native_timezone_probe",":network_preflight",":network_protection",":resource_pressure_fixture",":template_fixture",":transport_binding_fixture",":transport_binding_services"};\n  static boolean fixtureProcess(String packageName,String process,int slot){\n    if(process==null||packageName==null)return false;\n    if(EnvironmentProcessPolicy.owns(packageName,process,slot))return true;\n    if(process.equals(packageName+":ip_timezone_setup"))return true;\n    for(String suffix:LEGACY_FIXTURE_PROCESSES)if(process.equals(packageName+suffix))return true;\n    return false;\n  }\n  @Override Context profile(int slot){\n    Context context=super.profile(slot); // Parent releases its monitor first.\n    if(!initializing)IpTimeZoneFixtureScopes.prepareGeneric(this,context,slot);\n    return context;\n  }\n}\n'
BASE_APPLICATION_SHA256='5ac1e34e9a3add046df6f6a6e7e87e20ca5f8b891687592702132b72c40cfda9'
COLLABORATORS=r'''package local.pocketchat;
import android.content.*;import java.io.*;import java.util.*;import java.util.concurrent.*;import org.json.*;
final class ProfileContext extends ContextWrapper{final int slot;ProfileContext(Context b,int s){super(b);slot=s;if(s==6)Host.firstProfileReads++;}
@PROFILE_METHODS@
}
final class BackgroundReplyPolicy{static void bootstrap(Context c){Host.bootstrapCalls++;}static void install(android.app.Application a){}}
final class AppAppearance{static void install(android.app.Application a){}}final class AppVisibility{static void install(android.app.Application a){}}
final class IntegrationBuildIdentity{static JSONObject read(Context c){Host.touch("build-identity");return J.obj("sourceCommit",Host.SOURCE,"sourceTree","e".repeat(40),"apkSha256","f".repeat(64),"sdkBuildIdentity",J.obj("runId","12345","runAttempt","1"));}}
final class ProfileCatalog{static ProfileCatalog instance;static ProfileCatalog get(Context c){return instance;}final Db db=new Db();int opens;final boolean[] created=new boolean[8],deleting=new boolean[8],resetting=new boolean[8];final EnvironmentSpec.Identity[] ids=new EnvironmentSpec.Identity[8];ProfileCatalog(){created[0]=true;for(int i=0;i<8;i++)ids[i]=new EnvironmentSpec.Identity(i,0,UUID.randomUUID().toString());}Db getWritableDatabase(){Host.touch("catalog-open");if(opens++==0)for(int i=0;i<8;i++)Profiles.context(Host.app,i);return db;}JSONObject item(int s){Host.touch("catalog-item");if(Host.itemHook!=null)Host.itemHook.accept(s);return J.obj("created",created[s],"deleting",deleting[s],"resetting",resetting[s]);}boolean available(int s){Host.touch("catalog-available");return created[s]&&!deleting[s]&&!resetting[s];}EnvironmentSpec.Identity identity(int s)throws IOException{Host.touch("catalog-identity");if(!available(s))throw new IOException("unavailable");return ids[s];}interface Action<T>{T run()throws Exception;}synchronized <T>T createNew(int s,Action<T>a)throws Exception{if(created[s]||deleting[s]||resetting[s])throw new IOException("occupied");db.transaction=true;created[s]=true;try{return a.run();}finally{db.transaction=false;}}static final class Db{volatile boolean transaction;boolean inTransaction(){Host.touch("catalog-in-transaction");return transaction;}}}
final class SecretStore{static final Map<Integer,byte[]> records=new ConcurrentHashMap<>();final Context context;SecretStore(Context c){context=c;}byte[] get(String k){Host.touch("vault-read");byte[] b=records.get(Profiles.slot(context));return b==null?null:b.clone();}void put(String k,byte[]b){Host.touch("vault-write");records.put(Profiles.slot(context),b.clone());}void remove(String k){records.remove(Profiles.slot(context));}}
final class EnvironmentResetActivity{static void verifyRoots(Context c,int s){Host.prepares++;}}
final class GeckoTimeZoneStore{static final String STORE="gecko-timezone";static final Map<Integer,State> states=new ConcurrentHashMap<>();static int monitorViolations;
 static final class State{final EnvironmentSpec.Identity identity;final long revision;final GeckoTimeZoneSpec spec;State(EnvironmentSpec.Identity i,long r,GeckoTimeZoneSpec s){identity=i;revision=r;spec=s;}}
 private static final class Repository{final Context context;final int slot;final ProfileCatalog catalog;final SecretStore vault;final String path;
@REPOSITORY_CONSTRUCTOR@
 }
 static State load(Context input)throws Exception{
  boolean outer=Thread.currentThread().getName().equals("declared-controller-env-io");if(outer)Host.trace.add("outer-repository-enter");Repository repository=new Repository(input);
  if(outer){Host.trace.add("outer-repository-ready");Host.trace.add("outer-transaction-enter");}Host.loads++;Host.touch("store-load");if(Thread.holdsLock(Host.app))monitorViolations++;if(Host.loadHook!=null)Host.loadHook.run();int slot=repository.slot;EnvironmentSpec.Identity owner=ProfileCatalog.get(repository.context).identity(slot);if(outer){Host.outerLoads++;Host.trace.add("outer-loader-body");}
  State state=states.get(slot);if(state==null){state=new State(owner,1,GeckoTimeZoneSpec.automatic());states.put(slot,state);repository.vault.put(STORE,"loader:ip".getBytes());}return state;
 }
 static State save(Context c,EnvironmentSpec.Identity owner,long revision,GeckoTimeZoneSpec spec)throws Exception{Host.saves++;Host.touch("store-save");if(Host.saveHook!=null)Host.saveHook.run();if(Thread.holdsLock(Host.app))monitorViolations++;if(!ProfileCatalog.get(c).identity(owner.slot).equals(owner))throw new IOException("owner changed");State before=states.get(owner.slot);if(before==null||before.revision!=revision)throw new IOException("stale CAS");State after=new State(owner,revision+1,spec);states.put(owner.slot,after);new SecretStore(c).put(STORE,("saved:"+spec.mode).getBytes());if(spec.followsSystem())Host.trace.add("fixture-write-system");return after;}
}
'''
def member(raw,needle):
 if raw.count(needle)!=1:raise ValueError('Unique raw current method required: '+needle)
 return old.member_at(raw,raw.index(needle))
def main():
 p=argparse.ArgumentParser();p.add_argument('--java-home',type=Path,required=True);p.add_argument('--json-jar',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 app=ROOT/'app/src/main/java/local/pocketchat';geo=ROOT/'tests/gecko'
 whole=[geo/n for n in ['IpTimeZoneFixtureApplication.java','IpTimeZoneFixtureScopes.java']]+[app/n for n in ['J.java','GeckoTimeZoneSpec.java','GeckoTimeZonePolicy.java','NetworkShareJson.java','EnvironmentProcessPolicy.java']]
 extracted={}
 for name,needles in [('PocketApplication.java',['protected void attachBaseContext(','public void onCreate()','synchronized Context profile(','public Context getApplicationContext()']),('Profiles.java',['static int processSlot()','static int slot(','static Context global(','static Context context(','static void prepare(']),('EnvironmentSpec.java',['static final class Identity {','private static JSONObject object(']),('ProfileContext.java',['public Context getApplicationContext()','File directory(','public File getFilesDir()','public File getNoBackupFilesDir()']),('GeckoTimeZoneStore.java',['Repository(Context context)'])]:
  raw=(app/name).read_text()
  for needle in needles:extracted[name+':'+needle]=member(raw,needle)
 files=whole+[app/n for n in ['PocketApplication.java','Profiles.java','ProfileContext.java','EnvironmentSpec.java','GeckoTimeZoneStore.java']]+[HERE/'Host.java.in',Path(__file__).resolve(),HERE/'README.md',OLD,ROOT/'tests/gecko-navigation-host/run.py']
 before={str(q.relative_to(ROOT)):sha(q)for q in files};jar=sha(a.json_jar)
 if hashlib.sha256(BASE_APPLICATION.encode()).hexdigest()!=BASE_APPLICATION_SHA256:raise ValueError('Exact immutable public old-source regression fixture required')
 with tempfile.TemporaryDirectory(prefix='ui-fixture-hotpath-')as temp:
  base=Path(temp)
  def execute(label,mutation=None,base_application=False):
   folder=base/label;folder.mkdir();sources=[]
   def write(name,text):q=folder/name;q.parent.mkdir(parents=True,exist_ok=True);q.write_text(text);sources.append(q)
   stubs=dict(old.STUBS)
   stubs['android/os/Looper.java']='package android.os;public final class Looper{private static Thread main;private static final Looper value=new Looper();public static void bindMain(Thread t){main=t;}public static void bindApplicationThread(){if(main==null)main=Thread.currentThread();}public static Looper getMainLooper(){return value;}public static Looper myLooper(){return Thread.currentThread()==main?value:null;}}'
   stubs['android/content/ContextWrapper.java']='package android.content;import java.io.*;public class ContextWrapper extends Context{final Context base;public ContextWrapper(Context b){base=b;}public Context getBaseContext(){return base;}@Override public Context getApplicationContext(){return base.getApplicationContext();}@Override public File getNoBackupFilesDir(){return base.getNoBackupFilesDir();}@Override public File getFilesDir(){return base.getFilesDir();}}'
   context=stubs['android/content/Context.java'];context=context.replace('public File getNoBackupFilesDir(){','public File getNoBackupFilesDir(){local.pocketchat.Host.touch("files");').replace('public File getFilesDir(){','public File getFilesDir(){local.pocketchat.Host.touch("files");');stubs['android/content/Context.java']=context
   collaborators=COLLABORATORS.replace('@PROFILE_METHODS@','\n'.join(v for k,v in extracted.items()if k.startswith('ProfileContext.java:'))).replace('@REPOSITORY_CONSTRUCTOR@',extracted['GeckoTimeZoneStore.java:Repository(Context context)'])
   stubs['local/pocketchat/Collaborators.java']=collaborators
   for name,text in stubs.items():write(name,text)
   write('local/pocketchat/Host.java',(HERE/'Host.java.in').read_text())
   for q in whole:
    raw=BASE_APPLICATION if base_application and q.name=='IpTimeZoneFixtureApplication.java' else q.read_text()
    if mutation and q.name==mutation[0]:
     if raw.count(mutation[1])!=1:raise ValueError('Unique active mutation required: '+label)
     raw=raw.replace(mutation[1],mutation[2],1)
    write('local/pocketchat/'+q.name,raw)
   shells=[('PocketApplication.java','class PocketApplication extends android.app.Application {final android.content.Context[] profiles=new android.content.Context[Profiles.MAX];'),('Profiles.java','final class Profiles{static final int MAX=8;static final class NetworkCopy{String mode,proxy,entry;boolean requireVpn,configured;final Map<String,byte[]>records=new HashMap<>();}static NetworkCopy captureNetwork(Context c){throw new UnsupportedOperationException();}static void clearConfiguration(SecretStore s){}static final class FileCheck{static void requireUnusedBrowser(Context c){}}'),('EnvironmentSpec.java','final class EnvironmentSpec{')]
   for name,header in shells:write('local/pocketchat/'+name,'package local.pocketchat;import android.content.*;import android.os.*;import android.app.*;import java.util.*;import org.json.*;'+header+'\n'.join(v for k,v in extracted.items()if k.startswith(name+':'))+'}')
   compile_result=subprocess.run([str(a.java_home/'bin/javac'),'-encoding','UTF-8','-cp',str(a.json_jar),'-d',str(folder/'classes'),*map(str,sources)],text=True,capture_output=True,timeout=30)
   if compile_result.returncode:raise RuntimeError('Actual source host compile failed '+label+': '+compile_result.stderr[-8000:])
   return subprocess.run([str(a.java_home/'bin/java'),'-cp',str(folder/'classes')+os.pathsep+str(a.json_jar),'local.pocketchat.Host'],text=True,capture_output=True,timeout=30)
  current=execute('current')
  if current.returncode:raise RuntimeError(current.stdout+current.stderr)
  report=json.loads(current.stdout);negative=[]
  jobs=[('actual-public-source6-application',None,True),('remove-main-thread-guard',('IpTimeZoneFixtureApplication.java','&&android.os.Looper.myLooper()!=android.os.Looper.getMainLooper()',''),False),('skip-background-revalidation',('IpTimeZoneFixtureApplication.java','!initializing&&android.os.Looper.myLooper()!=android.os.Looper.getMainLooper()','false'),False),('slot-only-permanent-cache',('IpTimeZoneFixtureScopes.java','String key=expected.slot+":"+expected.environmentId+":"+expected.generation;','String key=String.valueOf(expected.slot);'),False),('missing-explicit-startup-seed',('IpTimeZoneFixtureApplication.java','IpTimeZoneFixtureScopes.prepareGeneric(this,super.profile(slot),slot);','super.profile(slot);'),False)]
  for label,mutation,old_application in jobs:
   result=execute(label,mutation,old_application)
   if result.returncode==0 or 'AssertionError:' not in result.stderr:raise AssertionError('Actual compiled counterfeit escaped '+label+': '+result.stderr[-2000:])
   negative.append(dict(name=label,compileSucceeded=True,runtimeRejected=True,assertion=result.stderr.split('AssertionError:',1)[1].splitlines()[0].strip()))
 stable=all(sha(ROOT/k)==v for k,v in before.items())and sha(a.json_jar)==jar
 report.update(schema=1,sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),sourceFiles=before,jsonJarSha256=jar,extractedMethodsSha256={k:hashlib.sha256(v.encode()).hexdigest()for k,v in extracted.items()},negativeControls=negative,executionInputsUnchanged=stable,baselineRegression=dict(sourceCommit=BASE_SOURCE,applicationSha256=BASE_APPLICATION_SHA256,sourceOnly=True,usedForPositiveExecution=False),actualAndroidExecution=False,actualGeckoExecution=False,actualEncryptedVaultExecution=False,actualNativeTimezoneReadback=False,scope='Complete raw current integration Application and Scopes, actual PocketApplication/Profiles/ProfileContext application-context chain and actual TZ Store Repository constructor; real temporary marker files and explicitly declared JVM Android main-thread, catalog, vault and subsequent store-transaction/load boundaries. No Android/native/Keystore/network or release qualification.')
 if not stable:report['status']='source-changed'
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k]for k in ['status','passed','total','mainLookups','executionInputsUnchanged']}))
 if not stable:raise SystemExit(1)
if __name__=='__main__':main()
