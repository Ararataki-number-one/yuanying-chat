#!/usr/bin/env python3
"""Run complete production network-state constructor and chrome metadata methods.

Adapters cover Android views, scheduling, preferences, catalogue rows and the
already-produced runtime observation. They do not manufacture Android evidence.
"""
import argparse,hashlib,json,pathlib,subprocess,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[2]
HERE=pathlib.Path(__file__).resolve().parent
PROD='app/src/main/java/local/pocketchat/'

def member(text,needle):
 start=text.index(needle);opened=text.index('{',start);depth=0;quote=None;escape=False;line=False;block=False;i=opened
 while i<len(text):
  c=text[i];n=text[i:i+2]
  if line:
   if c=='\n':line=False
  elif block:
   if n=='*/':block=False;i+=1
  elif quote:
   if escape:escape=False
   elif c=='\\':escape=True
   elif c==quote:quote=None
  elif n=='//':line=True;i+=1
  elif n=='/*':block=True;i+=1
  elif c in ('"',"\'"):quote=c
  elif c=='{':depth+=1
  elif c=='}':
   depth-=1
   if depth==0:return text[start:i+1]
  i+=1
 raise ValueError(needle)

def main():
 p=argparse.ArgumentParser();p.add_argument('--java-home',required=True,type=pathlib.Path);p.add_argument('--json-jar',required=True,type=pathlib.Path);p.add_argument('--before-ref');p.add_argument('--output',required=True,type=pathlib.Path);a=p.parse_args()
 names=['DesignChrome','WindowNetworkState','LatencyRefreshPolicy','LatencyProbePolicy','NetworkStatusPolicy','NetworkOptimizationPolicy','Sha256','NativeNetwork','NetworkCatalog']
 selected={name:(subprocess.check_output(['git','show',a.before_ref+':'+PROD+name+'.java'],cwd=ROOT).decode() if a.before_ref else (ROOT/(PROD+name+'.java')).read_text()) for name in names}
 inputs=[ROOT/(PROD+name+'.java') for name in names]+[HERE/'ChromeNetworkStateHost.java',pathlib.Path(__file__).resolve()]
 hashes={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs}
 chrome=selected['DesignChrome'];state=selected['WindowNetworkState'];current='static boolean profileAvailable(' in chrome
 methods=['void update(','private void renderLatest(','private void refreshMetadata(','private static void text(','private static void description(']
 if current:methods+=['static String profileLabel(','static boolean profileAvailable(','static boolean sameProfile(','private void applyMetadata(']
 initial=[]
 if current:initial.append(next(line.strip() for line in chrome.splitlines() if line.strip().startswith('profileRow=ProfileCatalog.get(a).item(')))
 initial += [next(line.strip() for line in chrome.splitlines() if line.strip().startswith(prefix)) for prefix in ['compactTitle=ReferenceUi.text(', 'title=ReferenceUi.text(', 'profileName=title.getText()']]
 fields=next(line for line in state.splitlines() if line.startswith('  final int slot;'))
 java=(HERE/'ChromeNetworkStateHost.java').read_text().replace('/* CHROME_METHODS */','\n'.join(member(chrome,needle) for needle in methods)).replace('/* INITIAL_METADATA */','\n'.join(initial)).replace('/* STATE_FIELDS */',fields).replace('/* STATE_CONSTRUCTOR */',member(state,'WindowNetworkState(Context c,'))
 java=java.replace('/* CATALOG_EXIT_ID */',member(selected['NetworkCatalog'],'static String exitId(')).replace('/* NATIVE_METHODS */','\n'.join(member(selected['NativeNetwork'],needle) for needle in ['static boolean subscribedExit(','static String exitIdentity(','static String hash(']))
 with tempfile.TemporaryDirectory(prefix='chrome-network-state-host-') as raw:
  temp=pathlib.Path(raw);src=temp/'src';src.mkdir();(src/'ChromeNetworkStateHost.java').write_text(java)
  for name in ['LatencyRefreshPolicy','LatencyProbePolicy','NetworkStatusPolicy','NetworkOptimizationPolicy','Sha256']:(src/(name+'.java')).write_text(selected[name])
  stubs={'android/content/Context.java':'package android.content; public class Context{public SharedPreferences getSharedPreferences(String name,int mode){return new SharedPreferences();}}','android/content/SharedPreferences.java':'package android.content; public class SharedPreferences{public String getString(String key,String fallback){return fallback;}public boolean getBoolean(String key,boolean fallback){return fallback;}}','android/os/SystemClock.java':'package android.os; public class SystemClock{public static long now=100000;public static long elapsedRealtime(){return now;}}'}
  for name,text in stubs.items():path=src/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
  classes=temp/'classes';subprocess.run([str(a.java_home/'bin/javac'),'-encoding','UTF-8','-cp',str(a.json_jar),'-d',str(classes),*map(str,src.rglob('*.java'))],check=True)
  run=subprocess.run([str(a.java_home/'bin/java'),'-Dbefore='+str(not current).lower(),'-cp',str(classes)+':'+str(a.json_jar),'local.pocketchat.ChromeNetworkStateHost'],text=True,capture_output=True)
  if not run.stdout:raise RuntimeError(run.stderr)
  report=json.loads(run.stdout)
 report.update(sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),sourceDirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)),selectedProductionRef=a.before_ref or 'working-tree',selectedProductionSha256={name:hashlib.sha256(text.encode()).hexdigest() for name,text in selected.items()},sourceFiles=hashes,executionInputsUnchanged=all(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest for path,digest in hashes.items()),jsonJarSha256=hashlib.sha256(a.json_jar.read_bytes()).hexdigest(),actualAndroidExecution=False,actualLatencyMeasurement=False,extractedChromeMethods=methods,scope='Complete production WindowNetworkState constructor and exact DesignChrome initial metadata statements/update/renderLatest/refreshMetadata/applyMetadata methods. Deterministic Android view, handler/executor, preferences and catalogue adapters; synthetic preproduced runtime observation. No Android scheduling, SQLite, native service or real network measurements.')
 if not report['executionInputsUnchanged']:report['status']='source-changed'
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':report['status'],'passed':report['passed'],'total':report['total'],'output':str(a.output)}))
 if run.returncode or report['status']!='passed':raise SystemExit(1)
if __name__=='__main__':main()
