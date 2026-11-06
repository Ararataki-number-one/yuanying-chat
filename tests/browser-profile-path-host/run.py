#!/usr/bin/env python3
"""Actual persistent path construction and active create-argument proof; named host edges only."""
import argparse,base64,hashlib,importlib.util,json,os,re,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
SOURCE='82a3512a8cf67259049353d7145407292a5d9cba'
PINS={'GeckoCpuController': '2ceaa3bb6602392d9702339620832187f612a0c863c0ddf46a61aac00200a558', 'GeckoTlsController': '0bdcb528c6df40a5a03324d1dd8b4066c74d22c23af9ac715159667968c20f67', 'GeckoCpuProfile': 'd1569a11149f15b4e6da1c0259bfc25fe6ee1bc1c920f8419e26c8c60756b5dd', 'GeckoTlsProfile': '2b33d4bde7b44cd6068f794fe13cf074a4ced0975d32b444632455180bcf4ac4', 'GeckoCpuStore': '8b83942560d72a1ad432245228d4791965133d2db6064d8c6cb9466b56e87458', 'GeckoTlsStore': '9430714a847aafc8fbb56390566330c785b8c3dcc019de14015830f68dfe82c8', 'GeckoCpuSpec': '617c69ba3b1d3b4edd3abf455bee8e36f3b861e0c82857153a8f8c632dd1bedc', 'GeckoTlsSpec': '4ffd5f095d6528053c4b11938cf5807f2b95c189bf1feafc3402eb451553f341', 'EnvironmentSpec': 'e85b542ffad8e5ff09d4b8484333b52b22200df093cae633dcd05f6dc1c1fb99', 'NetworkShareJson': '2934074b1e0bb9bf2ebd114643e6966cb30b5cb7e0cb7acf27a1ea59f1ddf677', 'J': '772bcc91b130ace1f33b529c2d828771ff9f12ba44805685a703df14f7d68493', 'ProfileContext': '2b72094396c21c235e77ce79fbd6a6eb134abf14a71bf4c8c0ae010aa2369178', 'Profiles': '3cb6e029ef665699345bc2f9bf3ae468090f8eda64d77048130f0a00fe2e1716', 'GeckoWebView': '55225a8da3ba67b3be724e243c9b442e635dbc5aa282a2ef0257653e8fb2b364'}
LEGACY_GV_SHA='b8a32f9f7dccd67a4e0ab90a69a94d053c3130e470fdbe6af647244152817fb4'
NAMES=['GeckoCpuController','GeckoTlsController','GeckoCpuProfile','GeckoTlsProfile','GeckoCpuStore','GeckoTlsStore','GeckoCpuSpec','GeckoTlsSpec','EnvironmentSpec','NetworkShareJson','J']
sha=lambda b:hashlib.sha256(b).hexdigest()
spec=importlib.util.spec_from_file_location('raw_path_member_extractor',ROOT/'tests/gecko-navigation-host/run.py');extract=importlib.util.module_from_spec(spec);spec.loader.exec_module(extract)
def member(s,needle):
 if s.count(needle)!=1:raise ValueError('Unique active member required: '+needle)
 return extract.member_at(s,s.index(needle))
def uncomment(s):
 # Preserve string/character tokens; remove only lexical Java comments.
 return re.sub(r'("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')|//[^\n]*|/\*.*?\*/',lambda m:m[1]if m[1]else' ',s,flags=re.S)
def verify_factored_raw(name,raw):
 if type(raw) is not bytes or type(name) is not str or name not in PINS or sha(raw)!=PINS[name]:raise ValueError('Unknown factored raw source: '+str(name))
 if name=='GeckoWebView':
  current=b'initialize();if(!resourceDeferred&&!failed){if(!target.isEmpty())owner.beginNavigation'
  previous=b'initialize();if(!resourceDeferred&&!failed&&runtime!=null){if(!target.isEmpty())owner.beginNavigation'
  if len(raw)!=128874 or raw.count(current)!=1:raise ValueError('Unknown factored resource recovery context')
  restored=raw.replace(current,previous,1)
  if len(restored)!=128889 or sha(restored)!='34a651c3ccc50499dd5c720c370353600ccf20669df5393ccbf68d6a689f9670':raise ValueError('Unknown factored resource recovery predecessor')
 return raw

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--java-home',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--json-jar',type=Path,help='Explicit known desktop or Android JSON test input; no fallback');a=p.parse_args()
 prod=ROOT/'app/src/main/java/local/pocketchat';view=(prod/'GeckoWebView.java').read_text();active=uncomment(member(view,'void initialize()'))
 modern='File directory=cpuBoot.profile,config=cpuBoot.config;';legacy='getNoBackupFilesDir(),"gecko-browser"'
 if modern not in active:
  if sha(view.encode())!=LEGACY_GV_SHA or legacy not in active or '"-profile",directory.getAbsolutePath()'not in active:raise ValueError('Unknown or disconnected active profile layout')
  a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps({'status':'passed','layout':'legacy','sourceSha256':sha(view.encode()),'actualAndroidExecution':False})+'\n');print('PERSISTENT_PROFILE_PATH_PROOF:legacy');return
 for name,digest in PINS.items():
  verify_factored_raw(name,(prod/(name+'.java')).read_bytes())
 start=view.index(modern,view.index('void initialize()'));end=view.index('      owner.resources.runtimeCreated();',start);runtime=view[start:end].strip()
 if runtime.count('runtime=GeckoRuntime.create(')!=1 or runtime.count('"-profile",directory.getAbsolutePath()')!=1:raise ValueError('One actual runtime profile consumer required')
 raw={n:(prod/(n+'.java')).read_text()for n in NAMES};profile=(prod/'ProfileContext.java').read_text();profiles=(prod/'Profiles.java').read_text()
 bits={'@ACTIVE_RUNTIME@':runtime,'@DIRECTORY@':member(profile,'File directory('),'@NO_BACKUP@':member(profile,'public File getNoBackupFilesDir()'),'@SLOT@':member(profiles,'static int slot('),'@GLOBAL@':member(profiles,'static Context global(')}
 template=(HERE/'Host.java.in').read_text()
 for token,text in bits.items():
  if template.count(token)!=1:raise ValueError('One path host token required')
  template=template.replace(token,text)
 fixture=ROOT/'tests/persistent-runtime-path-host/json-20240303.jar.b64';license=fixture.parent/'LICENSE-JSON-java-20240303.txt';encoded=fixture.read_bytes()
 if len(encoded)!=105819 or sha(encoded)!='01e2506eba3d8bb475bfbb4a85714ec5b11f0abc841d45de516fe32ee8e30348':raise ValueError('Fixed public JSON fixture encoding differs')
 jarbytes=base64.b64decode(b''.join(encoded.splitlines()),validate=True);jarsha=sha(jarbytes)
 if len(jarbytes)!=78332 or jarsha!='3cf6cd6892e32e2b4c1c39e0f52f5248a2f5b37646fdfbb79a66b46b618414ed':raise ValueError('Original public JSON dependency bytes differ')
 if a.json_jar is not None:
  chosen=a.json_jar.read_bytes();known={'3cf6cd6892e32e2b4c1c39e0f52f5248a2f5b37646fdfbb79a66b46b618414ed':78332,'dfb7bae2f404cfe0b72b4d23944698cb716b7665171812a0a4d0f5926c0fac79':18279,'3ea61b2a06e31edf1c91134fe9106b0ebb16628be169f3db75bc7a2b06b45796':82710}
  if known.get(sha(chosen))!=len(chosen):raise ValueError('Explicit JSON input is not a fixed real test dependency')
  jarbytes=chosen;jarsha=sha(chosen)
 files=[prod/(n+'.java')for n in [*NAMES,'ProfileContext','Profiles','GeckoWebView']]+[HERE/'Host.java.in',HERE/'README.md',Path(__file__).resolve(),ROOT/'tests/gecko-navigation-host/run.py',fixture,license];hashes={str(q.relative_to(ROOT)):sha(q.read_bytes())for q in files}
 a.output.parent.mkdir(parents=True,exist_ok=True);artifacts=a.output.parent/(a.output.stem+'-artifacts');artifacts.mkdir(exist_ok=True);reports=[];negative=[]
 with tempfile.TemporaryDirectory(prefix='persistent-runtime-path-')as temporary:
  folder=Path(temporary);jar=folder/'json-20240303.jar';jar.write_bytes(jarbytes)
  def execute(label,changes=None,host=None,slots=(0,6)):
   out=folder/label;out.mkdir();sources=[]
   for name,text in raw.items():
    if changes and name in changes:
     old,new=changes[name]
     if text.count(old)!=1:raise ValueError('Unique compiled path control: '+label+'/'+name)
     text=text.replace(old,new,1)
    q=out/(name+'.java');q.write_text(text);sources.append(q)
   q=out/'PathHost.java';q.write_text(host or template);sources.append(q)
   stubs={'android/content/Context.java':'package android.content;public abstract class Context{public abstract Context getApplicationContext();public abstract java.io.File getNoBackupFilesDir();public abstract android.content.pm.ApplicationInfo getApplicationInfo();}', 'android/content/ContextWrapper.java':'package android.content;public class ContextWrapper extends Context{final Context base;public ContextWrapper(Context base){this.base=base;}public Context getBaseContext(){return base;}public Context getApplicationContext(){return base.getApplicationContext();}public java.io.File getNoBackupFilesDir(){return base.getNoBackupFilesDir();}public android.content.pm.ApplicationInfo getApplicationInfo(){return base.getApplicationInfo();}}','android/content/pm/ApplicationInfo.java':'package android.content.pm;public class ApplicationInfo{public String dataDir;}','android/os/Process.java':'package android.os;public final class Process{public static int myPid(){return 111;}}'}
   for name,text in stubs.items():q=out/name;q.parent.mkdir(parents=True,exist_ok=True);q.write_text(text);sources.append(q)
   logs=artifacts/label;logs.mkdir(exist_ok=True);cmd=[str(a.java_home/'bin/javac'),'-encoding','UTF-8','--release','17','-cp',str(jar),'-d',str(out/'classes'),*map(str,sources)];built=subprocess.run(cmd,capture_output=True,text=True,timeout=60);(logs/'compile.stderr.log').write_text(built.stderr);(logs/'compile.command.json').write_text(json.dumps(cmd)+'\n')
   if built.returncode:raise RuntimeError(label+' actual path compilation failed: '+built.stderr)
   result=[]
   for slot in slots:
    cmd=[str(a.java_home/'bin/java'),'-cp',str(out/'classes')+os.pathsep+str(jar),'local.pocketchat.PathHost',str(out/('fs'+str(slot))),str(slot)];ran=subprocess.run(cmd,capture_output=True,text=True,timeout=30);(logs/(str(slot)+'.stdout.log')).write_text(ran.stdout);(logs/(str(slot)+'.stderr.log')).write_text(ran.stderr);result.append(ran)
   return result
  for result in execute('current'):
   if result.returncode:raise RuntimeError(result.stdout+result.stderr)
   reports.append(json.loads(result.stdout))
  assertion='Actual runtime -profile consumes original persistent environment directory'
  variants=[('wrong-storage-root',{'GeckoCpuProfile':('return new Storage(canonicalRoot,','return new Storage(new File(canonicalRoot,"foreign-root"),')},None),('wrong-cpu-tls-boot-name',{n:('profile=new File(root,"gecko-browser")','profile=new File(root,"gecko-other")')for n in ['GeckoCpuController','GeckoTlsController']},None),('disconnected-runtime-arguments',None,template.replace('"-profile",directory.getAbsolutePath()','"-profile",new File(directory.getParentFile(),"gecko-disconnected").getAbsolutePath()',1)),('unused-correct-builder',None,template.replace('File directory=cpuBoot.profile,config=cpuBoot.config;','File directory=cpuBoot.profile,config=cpuBoot.config;GeckoRuntimeSettings unused=new GeckoRuntimeSettings.Builder().arguments(new String[]{"-profile",directory.getAbsolutePath()}).build();',1).replace('"-profile",directory.getAbsolutePath()}).configFilePath','"-profile",new File(directory.getParentFile(),"gecko-other").getAbsolutePath()}).configFilePath',1)),('comment-decoy-wrong-active-argument',None,template.replace('"-profile",directory.getAbsolutePath()','"-profile",new File(directory.getParentFile(),"gecko-other").getAbsolutePath()',1).replace('void create()throws Exception{','void create()throws Exception{/* getNoBackupFilesDir(),"gecko-browser" */',1))]
  for label,changes,host in variants:
   for result in execute(label,changes,host,slots=(6,)):
    if result.returncode!=1 or 'AssertionError: '+assertion not in result.stderr:raise AssertionError('Compiled path counterfeit escaped precise runtime oracle: '+label+' '+result.stderr)
   negative.append({'name':label,'compiled':True,'actualRuntimeArgumentAssertionRejected':True,'assertion':assertion})
  jar_unchanged=sha(jar.read_bytes())==jarsha
 stable=all(sha((ROOT/name).read_bytes())==h for name,h in hashes.items())and jar_unchanged and (a.json_jar is None or sha(a.json_jar.read_bytes())==jarsha)
 report={'schema':1,'status':'passed'if stable else'source-changed','layout':'factored','sourceAnchor':SOURCE,'sourceFiles':hashes,'executionInputsUnchanged':stable,'rawMemberSha256':{k:sha(v.encode())for k,v in bits.items()},'jsonJarSha256':jarsha,'jsonDependencySource':'explicit-known-real-json'if a.json_jar else'exact-public-Maven-20240303-test-fixture','decodedPrivateTemporaryJar':a.json_jar is None,'copiedPrivateTemporaryJar':True,'implicitNetworkOrExternalJarFallback':False,'positive':reports,'compiledNegatives':negative,'currentJavaFromRawCurrent':True,'sourceHistoryProjectionUsed':False,'originalPersistentCookieDraftOpaqueBytesPreserved':True,'actualAndroidOrGeckoOrSqliteOrKeystoreExecution':False,'scope':'Actual raw CPU/TLS controllers/stores/specs/profiles and actual Context directory methods; real temporary filesystem/locks/atomic moves. Context/process/catalogue/plain-vault/queues and SDK Builder/create are named boundaries. Captured arguments belong to the actual settings object passed to the active create statement.'};a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 if not stable:raise SystemExit(1)
 print('PERSISTENT_PROFILE_PATH_PROOF:factored')
if __name__=='__main__':main()
