#!/usr/bin/env python3
"""Execute complete current test setup classes at explicit Android/vault/catalog host boundaries."""
import argparse,hashlib,json,os,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tests/gecko-navigation-host'))
from run import member_at
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

STUBS={
'android/content/Context.java':r'''package android.content;
import java.io.*;import android.content.pm.*;
public class Context {public static File directory;public static Context application;public static String packageName="local.pocketchat.test";public static final int MODE_PRIVATE=0;
 public String getPackageName(){return packageName;}public Context getApplicationContext(){return application;}public ApplicationInfo getApplicationInfo(){return new ApplicationInfo();}public File getNoBackupFilesDir(){File p=new File(directory,"no_backup");p.mkdirs();return p;}public File getFilesDir(){File p=new File(directory,"files");p.mkdirs();return p;}public PackageManager getPackageManager(){return new PackageManager();}public SharedPreferences getSharedPreferences(String n,int m){return new SharedPreferences();}}
''',
'android/content/SharedPreferences.java':r'''package android.content;public class SharedPreferences {public Editor edit(){return new Editor();}public static class Editor{public Editor clear(){return this;}public Editor putBoolean(String k,boolean v){return this;}public Editor putString(String k,String v){return this;}public boolean commit(){return true;}}}''',
'android/content/ContentValues.java':r'''package android.content;public class ContentValues {}''',
'android/content/ContentProvider.java':r'''package android.content;import android.database.*;import android.net.*;import android.os.*;import java.io.*;public abstract class ContentProvider{public Context context;public Context getContext(){return context;}public abstract boolean onCreate();public Bundle call(String m,String a,Bundle e){throw new UnsupportedOperationException();}public ParcelFileDescriptor openFile(Uri u,String m)throws FileNotFoundException{throw new FileNotFoundException();}public abstract String getType(Uri u);public abstract Cursor query(Uri u,String[]p,String s,String[]a,String o);public abstract Uri insert(Uri u,ContentValues v);public abstract int delete(Uri u,String s,String[]a);public abstract int update(Uri u,ContentValues v,String s,String[]a);}''',
'android/content/pm/ApplicationInfo.java':r'''package android.content.pm;import android.os.*;public class ApplicationInfo{public int uid=10200;public Bundle metaData;}''',
'android/content/pm/PackageManager.java':r'''package android.content.pm;import android.os.*;public class PackageManager{public static final int GET_META_DATA=128;public static String scope;public static class NameNotFoundException extends Exception{}public ApplicationInfo getApplicationInfo(String p,int f)throws NameNotFoundException{ApplicationInfo a=new ApplicationInfo();a.metaData=new Bundle();a.metaData.putString("local.pocketchat.test.genericTimeZoneScope",scope);return a;}}''',
'android/app/Application.java':r'''package android.app;import android.content.*;public class Application extends Context{public static String processName;public static String getProcessName(){return processName;}protected void attachBaseContext(Context c){}public void onCreate(){}}''',
'android/os/SystemClock.java':r'''package android.os;public class SystemClock{public static long now;public static long elapsedRealtime(){return now;}}''',
'android/os/Build.java':r'''package android.os;public class Build{public static class VERSION{public static int SDK_INT=35;}}''',
'android/os/Binder.java':r'''package android.os;public class Binder{public static int uid=2000;public static int getCallingUid(){return uid;}}''',
'android/os/Looper.java':r'''package android.os;public final class Looper{private static final Looper MAIN=new Looper();public static Looper getMainLooper(){return MAIN;}public static Looper myLooper(){return null;}}''',
'android/os/Process.java':r'''package android.os;public class Process{public static int uid=10200;public static int myUid(){return uid;}}''',
'android/os/Bundle.java':r'''package android.os;import java.util.*;public class Bundle{final Map<String,Object> map=new HashMap<>();public int size(){return map.size();}public boolean containsKey(String k){return map.containsKey(k);}public String getString(String k){Object v=map.get(k);return v instanceof String?(String)v:null;}public void putString(String k,String v){map.put(k,v);}}''',
'android/os/ParcelFileDescriptor.java':r'''package android.os;import java.io.*;public class ParcelFileDescriptor{public static final int MODE_READ_ONLY=1;public final File file;ParcelFileDescriptor(File f){file=f;}public static ParcelFileDescriptor open(File f,int m)throws FileNotFoundException{if(m!=MODE_READ_ONLY||!f.isFile())throw new FileNotFoundException();return new ParcelFileDescriptor(f);}}''',
'android/database/Cursor.java':r'''package android.database;public interface Cursor{}''',
'android/net/Uri.java':r'''package android.net;import java.net.*;public class Uri{final URI value;Uri(String s){value=URI.create(s);}public static Uri parse(String s){return new Uri(s);}public String getPath(){return value.getPath();}public String getQuery(){return value.getQuery();}public String getFragment(){return value.getFragment();}}''',
'android/util/AtomicFile.java':r'''package android.util;import java.io.*;import java.nio.file.*;public class AtomicFile{final File base;public AtomicFile(File f){base=f;}public FileInputStream openRead()throws IOException{return new FileInputStream(base);}public FileOutputStream startWrite()throws IOException{base.getParentFile().mkdirs();return new FileOutputStream(new File(base+".new"));}public void finishWrite(FileOutputStream o)throws IOException{try{o.close();Files.move(new File(base+".new").toPath(),base.toPath(),StandardCopyOption.REPLACE_EXISTING);local.pocketchat.Host.atomicSaved(base);}catch(Exception e){throw new IOException(e);}}public void failWrite(FileOutputStream o){try{o.close();}catch(Exception e){}new File(base+".new").delete();}public void delete(){base.delete();new File(base+".new").delete();new File(base+".bak").delete();}}''',
'android/webkit/WebView.java':r'''package android.webkit;public class WebView{public static void setDataDirectorySuffix(String s){}}''',
'local/pocketchat/Collaborators.java':r'''package local.pocketchat;
import android.content.*;import java.io.*;import java.util.*;import java.util.concurrent.*;import org.json.*;
final class ProfileContext extends Context{final Context base;final int slot;ProfileContext(Context b,int s){base=b;slot=s;if(s==6){Host.firstProfileReads++;Host.trace.add("slot6-first-profile");}}Context getBaseContext(){return base;}@Override public Context getApplicationContext(){return this;}@Override public File getNoBackupFilesDir(){File f=new File(base.getNoBackupFilesDir(),"profiles/env"+slot);f.mkdirs();return f;}@Override public File getFilesDir(){File f=new File(base.getFilesDir(),"profiles/env"+slot);f.mkdirs();return f;}}
final class BackgroundReplyPolicy {static void bootstrap(Context c){Host.bootstrapCalls++;String p=android.app.Application.getProcessName();if(p.equals(c.getPackageName())||p.matches(java.util.regex.Pattern.quote(c.getPackageName())+":profile[1-7]"))Profiles.context(c,6);}static void install(android.app.Application a){}}
final class AppAppearance {static void install(android.app.Application a){}}final class AppVisibility{static void install(android.app.Application a){}}
final class IntegrationBuildIdentity {static JSONObject read(Context c){return J.obj("sourceCommit",Host.SOURCE,"sourceTree","e".repeat(40),"apkSha256","f".repeat(64),"sdkBuildIdentity",J.obj("runId","12345","runAttempt","1"));}}
final class ProfileCatalog{static ProfileCatalog instance;static ProfileCatalog get(Context c){return instance;}final Db db=new Db();int opens;final boolean[] created=new boolean[8],deleting=new boolean[8],resetting=new boolean[8];final EnvironmentSpec.Identity[] ids=new EnvironmentSpec.Identity[8];ProfileCatalog(){created[0]=true;for(int i=0;i<8;i++)ids[i]=new EnvironmentSpec.Identity(i,0,UUID.randomUUID().toString());}Db getWritableDatabase(){if(opens++==0)for(int i=0;i<8;i++)Profiles.context(Host.app,i);return db;}JSONObject item(int s){java.util.function.IntConsumer hook=Host.itemHook;if(hook!=null)hook.accept(s);return J.obj("created",created[s],"deleting",deleting[s],"resetting",resetting[s]);}boolean available(int s){return created[s]&&!deleting[s]&&!resetting[s];}EnvironmentSpec.Identity identity(int s)throws IOException{if(!available(s))throw new IOException("unavailable");return ids[s];}interface Action<T>{T run()throws Exception;}synchronized <T>T createNew(int s,Action<T>a)throws Exception{if(created[s]||deleting[s]||resetting[s])throw new IOException("occupied");db.transaction=true;created[s]=true;try{return a.run();}finally{db.transaction=false;}}static final class Db{volatile boolean transaction;boolean inTransaction(){return transaction;}}}
final class SecretStore{static final Map<Integer,byte[]> records=new ConcurrentHashMap<>();final Context context;SecretStore(Context c){context=c;}byte[] get(String k){return records.get(Profiles.slot(context));}void put(String k,byte[]b){records.put(Profiles.slot(context),b.clone());}void remove(String k){}}
final class EnvironmentResetActivity{static void verifyRoots(Context c,int s){Host.prepares++;Host.trace.add("profiles-prepare");}}
final class GeckoTimeZoneStore {static final String STORE="gecko-timezone";static final Map<Integer,State> states=new ConcurrentHashMap<>();static int monitorViolations;static final class State{final EnvironmentSpec.Identity identity;final long revision;final GeckoTimeZoneSpec spec;State(EnvironmentSpec.Identity i,long r,GeckoTimeZoneSpec s){identity=i;revision=r;spec=s;}}
 static State load(Context c)throws Exception{Host.loads++;if(Thread.holdsLock(Host.app))monitorViolations++;Runnable hook=Host.loadHook;if(hook!=null)hook.run();int slot=Profiles.slot(c);State current=states.get(slot);if(current==null){current=new State(ProfileCatalog.get(c).identity(slot),1,GeckoTimeZoneSpec.automatic());states.put(slot,current);new SecretStore(c).put(STORE,"loader:ip".getBytes());}return current;}
 static State save(Context c,EnvironmentSpec.Identity expected,long revision,GeckoTimeZoneSpec spec)throws Exception{Host.saves++;Runnable saveHook=Host.saveHook;if(saveHook!=null)saveHook.run();if(Thread.holdsLock(Host.app))monitorViolations++;if(!ProfileCatalog.get(c).identity(expected.slot).equals(expected))throw new IOException("owner changed");State before=states.get(expected.slot);if(before==null||before.revision!=revision)throw new IOException("CAS revision changed");State after=new State(expected,revision+1,spec);states.put(expected.slot,after);new SecretStore(c).put(STORE,("saved:"+spec.mode).getBytes());return after;}}
'''
}

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--java-home',type=Path,required=True);p.add_argument('--json-jar',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 app=ROOT/'app/src/main/java/local/pocketchat';geo=ROOT/'tests/gecko'
 whole=[geo/n for n in ['IpTimeZoneFixtureScopes.java','IpTimeZoneFixtureApplication.java','GeckoIpTimeZoneEvidenceProvider.java']]+[app/n for n in ['J.java','GeckoTimeZoneSpec.java','GeckoTimeZonePolicy.java','NetworkShareJson.java','EnvironmentProcessPolicy.java']]
 parents=(app/'PocketApplication.java').read_text();profile=(app/'Profiles.java').read_text();environment=(app/'EnvironmentSpec.java').read_text()
 extracted={}
 for name,raw,needles in [('PocketApplication.java',parents,['protected void attachBaseContext(','public void onCreate()','synchronized Context profile(']),('Profiles.java',profile,['static int processSlot()','static int slot(','static Context global(','static Context context(','static void prepare(']),('EnvironmentSpec.java',environment,['static final class Identity {','private static JSONObject object('])]:
  for needle in needles:
   if raw.count(needle)!=1:raise ValueError('Unique current source member required: '+name+':'+needle)
   extracted[name+':'+needle]=member_at(raw,raw.index(needle))
 files=whole+[app/'PocketApplication.java',app/'Profiles.java',app/'EnvironmentSpec.java',app/'GeckoTimeZoneStore.java',geo/'AndroidManifest.xml',HERE/'Host.java.in',Path(__file__).resolve(),ROOT/'tests/gecko-navigation-host/run.py'];before={str(x.relative_to(ROOT)):sha(x) for x in files};jar=sha(a.json_jar)
 with tempfile.TemporaryDirectory(prefix='ip-fixture-setup-host-')as temp:
  base=Path(temp)
  def execute(label,changes=None):
   folder=base/label;folder.mkdir();sources=[]
   def write(name,text):
    q=folder/name;q.parent.mkdir(parents=True,exist_ok=True);q.write_text(text);sources.append(q)
   for name,text in STUBS.items():write(name,text)
   write('local/pocketchat/Host.java',(HERE/'Host.java.in').read_text())
   for q in whole:
    raw=q.read_text()
    if changes and q.name==changes[0]:
     if raw.count(changes[1])!=1:raise ValueError('Unique actual semantic control required: '+label)
     raw=raw.replace(changes[1],changes[2],1)
    write('local/pocketchat/'+q.name,raw)
   for owner,header,footer in [('PocketApplication.java','class PocketApplication extends android.app.Application {final android.content.Context[] profiles=new android.content.Context[Profiles.MAX];','}'),('Profiles.java','final class Profiles {static final int MAX=8;static final class NetworkCopy{String mode,proxy,entry;boolean requireVpn,configured;final Map<String,byte[]> records=new HashMap<>();}static NetworkCopy captureNetwork(Context c){throw new UnsupportedOperationException();}static void clearConfiguration(SecretStore s){}static final class FileCheck{static void requireUnusedBrowser(Context c){}}','}'),('EnvironmentSpec.java','final class EnvironmentSpec {','}')]:
    body='\n'.join(v for k,v in extracted.items()if k.startswith(owner+':'));write('local/pocketchat/'+owner,'package local.pocketchat;import android.content.*;import android.os.*;import android.app.*;import java.util.*;import org.json.*;\n'+header+body+footer)
   command=[str(a.java_home/'bin/javac'),'-encoding','UTF-8','-cp',str(a.json_jar),'-d',str(folder/'classes'),*map(str,sources)];c=subprocess.run(command,text=True,capture_output=True,timeout=30)
   if c.returncode:raise RuntimeError('Current exact-class host compile failed: '+c.stderr[-7000:])
   return subprocess.run([str(a.java_home/'bin/java'),'-cp',str(folder/'classes')+os.pathsep+str(a.json_jar),'local.pocketchat.Host'],text=True,capture_output=True,timeout=30)
  current=execute('current')
  if current.returncode:raise RuntimeError(current.stdout+current.stderr)
  report=json.loads(current.stdout);negative=[]
  mutants=[('missing-sealed-overwrite','IpTimeZoneFixtureScopes.java','if(before!=null){SEEN.add(key);return;}','if(false){SEEN.add(key);return;}'),('unarmed-profile-admission','IpTimeZoneFixtureScopes.java','if(!setupProcess(context)||value.opt("identity")!=JSONObject.NULL)','if(value.opt("identity")!=JSONObject.NULL)'),('foreign-claim','IpTimeZoneFixtureScopes.java','!nonce.equals(value.opt("runNonce"))||Profiles.slot(context)!=SLOT','false||Profiles.slot(context)!=SLOT'),('stale-environment','IpTimeZoneFixtureScopes.java','else if(!sameIdentity(value.getJSONObject("identity"),ProfileCatalog.get(context).identity(SLOT)))','else if(false)'),('non-shell-provider','GeckoIpTimeZoneEvidenceProvider.java','if(Binder.getCallingUid()!=2000)','if(false)'),('reservation-serialization','IpTimeZoneFixtureScopes.java','synchronized(SCOPE_LOCK){return prepareIpLocked(context,source,nonce);}','return prepareIpLocked(context,source,nonce);'),('provider-report-symlink','GeckoIpTimeZoneEvidenceProvider.java','java.nio.file.Files.isSymbolicLink(target.toPath())||','')]
  for label,name,old,new in mutants:
   bad=execute(label,(name,old,new))
   if bad.returncode==0 or 'AssertionError:' not in bad.stderr:raise AssertionError('Semantic false-proof escaped: '+label+' '+bad.stderr[-2000:])
   negative.append(dict(name=label,compileSucceeded=True,runtimeRejected=True,assertion=bad.stderr.split('AssertionError:',1)[1].splitlines()[0].strip()))
 stable=all(sha(ROOT/k)==v for k,v in before.items())and sha(a.json_jar)==jar
 report.update(schema=1,sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),sourceFiles=before,jsonJarSha256=jar,extractedMethodsSha256={k:hashlib.sha256(v.encode()).hexdigest()for k,v in extracted.items()},negativeControls=negative,executionInputsUnchanged=stable,actualAndroidExecution=False,actualGeckoExecution=False,actualNativeTimezoneReadback=False,actualNetworkRequestsSent=False,scope='Whole current integration-only Application/Scopes/UID2000 provider, complete current TZSpec/TZPolicy/strictJSON/J/EnvironmentProcessPolicy; verbatim PocketApplication attach/onCreate/profile and Profiles context/prepare plus exact Environment Identity. Android lifecycle/Application bootstrap callback, main/clock/Binder/metadata/AtomicFile, catalog/vault/TZ store are explicit host collaborators. Store default uses actual TZSpec.automatic but this does not prove actual sealed-vault or Android/native/network execution; separate real integration gate owns those claims.')
 if not stable:report['status']='source-changed'
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:report[k]for k in ['status','passed','total','executionInputsUnchanged','actualAndroidExecution']}))
 if not stable:raise SystemExit(1)
if __name__=='__main__':main()
