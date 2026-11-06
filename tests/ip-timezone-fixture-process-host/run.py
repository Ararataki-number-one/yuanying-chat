#!/usr/bin/env python3
"""Actual integration Application process gate; explicit JVM-only Android/catalog/vault boundaries."""
import argparse,hashlib,importlib.util,json,os,re,subprocess,tempfile,xml.etree.ElementTree as ET
from pathlib import Path
BASE_PUBLIC='c83ac9a915a58d0ae16c69884ba253137d2b56ac'
BASE_APPLICATION_SHA256='c24c75e230202a880e22e9b07a49a59066b1088351ecb64e223bf4d978a28894'
# Exact complete Application from BASE_PUBLIC; no ancestor object/network needed.
BASE_APPLICATION=r'''package local.pocketchat;

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
'''
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
OLD=ROOT/'tests/ip-timezone-fixture-setup-host/run.py'
spec=importlib.util.spec_from_file_location('original_setup_host_collaborators',OLD);old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def exact(text,before,after):
 if text.count(before)!=1:raise ValueError('One exact collaborator adaptation required: '+before)
 return text.replace(before,after,1)

# Only the two declared lookup hunks are reversed for this metadata guard.
# execute()/javac/JVM always consume the whole raw current Application.
UI_BEFORE_SOURCE='c5c539f75d4e95baa12b56593e59054615f0efde'
UI_BEFORE_APPLICATION_SHA256='5ac1e34e9a3add046df6f6a6e7e87e20ca5f8b891687592702132b72c40cfda9'
UI_AFTER_APPLICATION_SHA256='0e9f31149b2d9fb4f1f51780405f0515a17acee67afeb50c779c6e29012c0dab'
UI_LOOKUP_EDITS=(('for(int slot=0;slot<Profiles.MAX;slot++)if(ProfileCatalog.get(this).available(slot))profile(slot);', 'for(int slot=0;slot<Profiles.MAX;slot++)if(ProfileCatalog.get(this).available(slot))IpTimeZoneFixtureScopes.prepareGeneric(this,super.profile(slot),slot);'), ('    if(!initializing)IpTimeZoneFixtureScopes.prepareGeneric(this,context,slot);', '    // UI context lookup is a cache operation. The explicit startup loop above\n    // seeds old fixtures; background Store/Controller access still validates\n    // the current environment identity and marker before its first load.\n    if(!initializing&&android.os.Looper.myLooper()!=android.os.Looper.getMainLooper())IpTimeZoneFixtureScopes.prepareGeneric(this,context,slot);'))
def process_metadata_image(application):
 digest=hashlib.sha256(application.encode()).hexdigest()
 if digest==UI_BEFORE_APPLICATION_SHA256:return application
 if digest!=UI_AFTER_APPLICATION_SHA256:raise ValueError('Unknown whole fixture Application image')
 inverse=application
 for before,after in UI_LOOKUP_EDITS:
  if inverse.count(after)!=1 or before in inverse:raise ValueError('Unique declared UI lookup hunk required')
  inverse=inverse.replace(after,before,1)
 if hashlib.sha256(inverse.encode()).hexdigest()!=UI_BEFORE_APPLICATION_SHA256:raise ValueError('Fixture UI inverse does not close to its public beforeimage')
 return inverse

def process_metadata_controls(application):
 inverse=process_metadata_image(application)
 if process_metadata_image(inverse)!=inverse:raise AssertionError('Original known layout must remain accepted')
 application=inverse
 for before,after in UI_LOOKUP_EDITS:
  if application.count(before)!=1:raise AssertionError('Known metadata beforeimage hunk differs')
  application=application.replace(before,after,1)
 if hashlib.sha256(application.encode()).hexdigest()!=UI_AFTER_APPLICATION_SHA256:raise AssertionError('Known metadata forward image differs')
 cases=[('unknown-whole',application+'\n'),('missing-ui-hunk',application.replace(UI_LOOKUP_EDITS[0][1],UI_LOOKUP_EDITS[0][0],1)),('duplicate-ui-hunk',application+UI_LOOKUP_EDITS[1][1]),('moved-ui-hunk',application.replace(UI_LOOKUP_EDITS[1][1],'',1)+UI_LOOKUP_EDITS[1][1]),('removed-main-thread-guard',application.replace('android.os.Looper.myLooper()!=android.os.Looper.getMainLooper()','true',1))]
 rows=[]
 for name,candidate in cases:
  try:process_metadata_image(candidate)
  except ValueError:rows.append(dict(name=name,rejected=True))
  else:raise AssertionError('Unknown metadata image escaped: '+name)
 return rows

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--java-home',type=Path);p.add_argument('--json-jar',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 java=(a.java_home/'bin/java' if a.java_home else Path(os.environ['PROFILE_JAVA']) if os.environ.get('PROFILE_JAVA') else Path(os.environ.get('PROFILE_JAVA_HOME',os.environ.get('JAVA_HOME','')))/'bin/java');javac=java.with_name('javac')
 if not java.is_file()or not javac.is_file():p.error('A real selected JDK17 is required')
 jar=a.json_jar or Path(os.environ.get('PROFILE_JSON_JAR',''))
 if not jar.is_file():p.error('A real explicitly selected JSON jar is required')
 app=ROOT/'app/src/main/java/local/pocketchat';geo=ROOT/'tests/gecko'
 whole=[geo/n for n in ['IpTimeZoneFixtureApplication.java','IpTimeZoneFixtureScopes.java']]+[app/n for n in ['EnvironmentProcessPolicy.java','J.java','GeckoTimeZoneSpec.java','GeckoTimeZonePolicy.java','NetworkShareJson.java']]
 extracted={}
 for name,markers in [('PocketApplication.java',['protected void attachBaseContext(','public void onCreate()','synchronized Context profile(','public Context getApplicationContext()']),('Profiles.java',['static int processSlot()','static int slot(','static Context global(','static Context context(','static void prepare(']),('EnvironmentSpec.java',['static final class Identity {','private static JSONObject object('])]:
  raw=(app/name).read_text()
  for marker in markers:
   if raw.count(marker)!=1:raise ValueError('Unique actual parent member required: '+name+marker)
   extracted[name+':'+marker]=old.member_at(raw,raw.index(marker))
 manifest=ET.parse(geo/'AndroidManifest.xml');processes={x.attrib['{http://schemas.android.com/apk/res/android}process']for x in manifest.iter()if'{http://schemas.android.com/apk/res/android}process'in x.attrib};legacy=sorted(processes-{':profile'+str(i)for i in range(1,8)}-{':ip_timezone_setup'})
 application=(geo/'IpTimeZoneFixtureApplication.java').read_text();match=re.search(r'LEGACY_FIXTURE_PROCESSES=\{([^}]*)\}',application)
 if match is None or re.findall(r'"([^"]+)"',match[1])!=legacy or len(legacy)!=14:raise ValueError('Exact fourteen actual manifest legacy processes required')
 files=whole+[app/n for n in ['PocketApplication.java','Profiles.java','EnvironmentSpec.java','GeckoTimeZoneStore.java']]+[OLD,OLD.parent/'Host.java.in',ROOT/'tests/gecko-navigation-host/run.py',HERE/'Host.java.in',HERE/'README.md',Path(__file__).resolve(),ROOT/'app/build.gradle',geo/'AndroidManifest.xml']
 hashes={str(q.relative_to(ROOT)):sha(q)for q in files};jarhash=sha(jar);stubs=dict(old.STUBS)
 for name,before,after in [
  ('android/content/Context.java','getNoBackupFilesDir(){','getNoBackupFilesDir(){local.pocketchat.Host.touch("files");'),
  ('android/content/Context.java','getFilesDir(){','getFilesDir(){local.pocketchat.Host.touch("files");'),
  ('android/content/Context.java','getPackageManager(){','getPackageManager(){local.pocketchat.Host.touch("metadata");'),
  ('android/content/Context.java','getSharedPreferences(String n,int m){','getSharedPreferences(String n,int m){local.pocketchat.Host.touch("preferences");'),
  ('android/content/Context.java','public ApplicationInfo getApplicationInfo(){return new ApplicationInfo();}','public ApplicationInfo getApplicationInfo(){return local.pocketchat.Host.applicationInfo();}'),
  ('android/content/pm/PackageManager.java','getApplicationInfo(String p,int f)throws NameNotFoundException{','getApplicationInfo(String p,int f)throws NameNotFoundException{local.pocketchat.Host.touch("metadata");'),
  ('android/app/Application.java','public void onCreate(){}','public void onCreate(){local.pocketchat.Host.parentCreated();}')]:stubs[name]=exact(stubs[name],before,after)
 c=stubs['local/pocketchat/Collaborators.java']
 for before,after in [
  ('if(p.equals(c.getPackageName())||p.matches(java.util.regex.Pattern.quote(c.getPackageName())+":profile[1-7]"))','if(p!=null&&(p.equals(c.getPackageName())||p.matches(java.util.regex.Pattern.quote(c.getPackageName())+":profile[1-7]")))'),
  ('static void install(android.app.Application a){}','static void install(android.app.Application a){Host.parentInstalled();}')]:
  if before.startswith('static void install'):c=c.replace(before,after)
  else:c=exact(c,before,after)
 for before,after in [('static ProfileCatalog get(Context c){','static ProfileCatalog get(Context c){Host.touch("catalog");'),('Db getWritableDatabase(){','Db getWritableDatabase(){Host.touch("catalog-db");'),('SecretStore(Context c){','SecretStore(Context c){Host.touch("vault");'),('static State load(Context c)throws Exception{','static State load(Context c)throws Exception{Host.touch("store");'),('static State save(Context c,EnvironmentSpec.Identity expected,long revision,GeckoTimeZoneSpec spec)throws Exception{','static State save(Context c,EnvironmentSpec.Identity expected,long revision,GeckoTimeZoneSpec spec)throws Exception{Host.touch("store");'),('static JSONObject read(Context c){','static JSONObject read(Context c){Host.touch("identity");')]:c=exact(c,before,after)
 stubs['local/pocketchat/Collaborators.java']=c
 a.output.parent.mkdir(parents=True,exist_ok=True);artifacts=a.output.parent/(a.output.stem+'-artifacts');artifacts.mkdir(exist_ok=True);controls=[]
 with tempfile.TemporaryDirectory(prefix='fixture-process-host-')as temp:
  def execute(label,change=None):
   folder=Path(temp)/label;folder.mkdir();sources=[];bodies={}
   def write(name,text):
    if change and name=='local/pocketchat/'+change[0]:text=exact(text,change[1],change[2])
    q=folder/name;q.parent.mkdir(parents=True,exist_ok=True);q.write_text(text);sources.append(q);bodies[name]=hashlib.sha256(text.encode()).hexdigest()
   for name,text in stubs.items():write(name,text)
   write('local/pocketchat/Host.java',(HERE/'Host.java.in').read_text().replace('@LEGACY@','new String[]{'+','.join(json.dumps(x)for x in legacy)+'}'))
   for q in whole:write('local/pocketchat/'+q.name,q.read_text())
   for owner,header in [('PocketApplication.java','class PocketApplication extends android.app.Application {final android.content.Context[] profiles=new android.content.Context[Profiles.MAX];'),('Profiles.java','final class Profiles {static final int MAX=8;static final class NetworkCopy{String mode,proxy,entry;boolean requireVpn,configured;final Map<String,byte[]> records=new HashMap<>();}static NetworkCopy captureNetwork(Context c){throw new UnsupportedOperationException();}static void clearConfiguration(SecretStore s){}static final class FileCheck{static void requireUnusedBrowser(Context c){}}'),('EnvironmentSpec.java','final class EnvironmentSpec {')]:write('local/pocketchat/'+owner,'package local.pocketchat;import android.content.*;import android.os.*;import android.app.*;import java.util.*;import org.json.*;\n'+header+'\n'+'\n'.join(v for k,v in extracted.items()if k.startswith(owner+':'))+'\n}')
   target=artifacts/label;target.mkdir(exist_ok=True);cmd=[str(javac),'-encoding','UTF-8','--release','17','-cp',str(jar.resolve()),'-d',str(folder/'classes'),*map(str,sources)];built=subprocess.run(cmd,capture_output=True,text=True,timeout=30);(target/'compile.command.json').write_text(json.dumps(cmd)+'\n');(target/'compile.stdout.log').write_text(built.stdout);(target/'compile.stderr.log').write_text(built.stderr)
   if built.returncode:raise RuntimeError(label+' compile failed: '+built.stderr)
   cmd=[str(java),'-cp',str(folder/'classes')+os.pathsep+str(jar.resolve()),'local.pocketchat.Host'];ran=subprocess.run(cmd,capture_output=True,text=True,timeout=30);(target/'run.command.json').write_text(json.dumps(cmd)+'\n');(target/'run.stdout.log').write_text(ran.stdout);(target/'run.stderr.log').write_text(ran.stderr);return ran,bodies
  current,bodies=execute('current')
  if current.returncode:raise RuntimeError(current.stdout+current.stderr)
  report=json.loads(current.stdout)
  guard='    if(!fixtureProcess(getPackageName(),process,Profiles.processSlot()))return;\n'
  application=(geo/'IpTimeZoneFixtureApplication.java').read_text();base=BASE_APPLICATION
  if hashlib.sha256(base.encode()).hexdigest()!=BASE_APPLICATION_SHA256:raise ValueError('Pinned actual original Application bytes differ')
  if application==base:raise ValueError('This candidate host requires the declared Application-only process gate')
  insertion=application[application.index('    // Retain the original package rejection'):application.index('    IpTimeZoneFixtureScopes.declaredGeneric(this);')]
  helper=application[application.index('  static final String[] LEGACY_FIXTURE_PROCESSES='):application.index('  @Override Context profile(int slot)')]
  metadata_application=process_metadata_image(application);ui_metadata_controls=process_metadata_controls(application)
  if metadata_application.replace(insertion,'',1).replace(helper,'',1)!=base:raise ValueError('Whole original Application is not preserved after exact candidate inverse')
  mutants=[('actual-original-application','IpTimeZoneFixtureApplication.java',application,base),('removed-owner-guard','IpTimeZoneFixtureApplication.java',guard,''),('owner-policy-bypass','EnvironmentProcessPolicy.java','&&processName.equals(packageName+(slot==0?"":":profile"+slot))','&&true'),('fake-profile-slot','Profiles.java','if(process.endsWith(":profile"+id))return id;','if(process.endsWith(":profile"+id))return 0;'),('isolated-uid-bypass','IpTimeZoneFixtureApplication.java','if(application==null||android.os.Process.myUid()!=application.uid)return;','if(application==null)return;'),('package-rejection-removed','IpTimeZoneFixtureApplication.java','    IpTimeZoneFixtureScopes.integration(this);\n','')]
  for label,name,before,after in mutants:
   ran,generated=execute(label,(name,before,after))
   if ran.returncode!=1 or 'java.lang.AssertionError:'not in ran.stderr:raise AssertionError('Compiled unsafe process counterfeit escaped: '+label+' '+ran.stderr)
   controls.append(dict(name=label,compiled=True,runtimeRejected=True,assertion=ran.stderr.split('java.lang.AssertionError:',1)[1].splitlines()[0].strip(),generatedSourceSha256=generated['local/pocketchat/'+name]))
 stable=all(sha(ROOT/name)==value for name,value in hashes.items())and sha(jar)==jarhash
 report.update(uiMetadataGuardOnly=True,uiMetadataCounterfeits=ui_metadata_controls,uiMetadataBeforeSource=UI_BEFORE_SOURCE,uiMetadataBeforeSha256=UI_BEFORE_APPLICATION_SHA256,uiMetadataCurrentSha256=UI_AFTER_APPLICATION_SHA256,schema=1,status='passed'if stable else'source-changed',sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),sourceFiles=hashes,jsonJarSha256=jarhash,generatedSourceSha256=bodies,manifestLegacyProcesses=legacy,extractedParentMethodSha256={k:hashlib.sha256(v.encode()).hexdigest()for k,v in extracted.items()},negativeControls=controls,originalApplicationInverseSha256=hashlib.sha256(base.encode()).hexdigest(),executionInputsUnchanged=stable,actualAndroidExecution=False,actualGeckoExecution=False,actualNativeTimezoneReadback=False,actualKeystoreExecution=False,actualNetworkExecution=False,scope='Whole actual candidate integration Application and Scopes, complete actual EnvironmentProcessPolicy/J/TZSpec/TZPolicy/strictJSON; actual PocketApplication lifecycle/profile/context and Profiles owner/context methods execute. Original104/7 setup assertions/mutants unchanged and separate; only actual Android UID API declarations are added to their collaborators. Android lifecycle/process name/UID/files/metadata/catalog/vault/TZ store are explicit JVM collaborators; throwing child collaborators enforce zero fixture IO before and after later same-profile access. Name-shaped isolated and generated env6 children are host cases, not Android isolation or runtime-cause proof.')
 a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:report[k]for k in ['status','passed','total','executionInputsUnchanged','actualAndroidExecution']}))
 if not stable:raise SystemExit(1)
if __name__=='__main__':main()
