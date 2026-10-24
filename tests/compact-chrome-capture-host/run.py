#!/usr/bin/env python3
"""Exercise actual fixture capture methods on a controlled Android callback queue."""
import argparse,hashlib,importlib.util,json,pathlib,re,subprocess,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[2];HERE=pathlib.Path(__file__).resolve().parent;PROD='app/src/main/java/local/pocketchat/'
# Exact 62a0ff6e44ba08e4bbf28149a11d3f47a4f6a642 source receipts. Normal CI
# checkouts are shallow: preserve the original assertions without git history.
ORIGINAL_REPORT_SHA256='200192382212fee9889cd9905b837d551a27c75fcc4b777acdab3dd9982e63b7'
contract_path=ROOT/'tests/ui_visual_preservation_contract.py'
contract_spec=importlib.util.spec_from_file_location('ui_visual_preservation_contract',contract_path);contract=importlib.util.module_from_spec(contract_spec);contract_spec.loader.exec_module(contract)
spec=importlib.util.spec_from_file_location('chrome_production_extractor',ROOT/'tests/chrome-network-state-host/run.py');extract=importlib.util.module_from_spec(spec);spec.loader.exec_module(extract);member=extract.member

def main():
 p=argparse.ArgumentParser();p.add_argument('--java-home',required=True,type=pathlib.Path);p.add_argument('--json-jar',required=True,type=pathlib.Path);p.add_argument('--before-ref');p.add_argument('--output',required=True,type=pathlib.Path);a=p.parse_args()
 names=['DesignChrome','WindowNetworkState','LatencyRefreshPolicy','LatencyProbePolicy','NetworkStatusPolicy','NetworkOptimizationPolicy','Sha256','NativeNetwork','NetworkCatalog']
 paths=[PROD+name+'.java' for name in names]+['tests/gecko/CompactChromeIntegrationActivity.java','tests/gecko/run_ui_visuals.py']
 selected={path:(subprocess.check_output(['git','show',a.before_ref+':'+path],cwd=ROOT).decode() if a.before_ref else (ROOT/path).read_text()) for path in paths}
 helper=ROOT/'tests/gecko/CompactChromePresentationCapture.java'
 inputs=[ROOT/path for path in paths]+[helper,HERE/'CompactChromeCaptureHost.java',pathlib.Path(__file__).resolve(),ROOT/'tests/chrome-network-state-host/run.py',contract_path]
 hashes={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs}
 chrome=selected[PROD+'DesignChrome.java'];state=selected[PROD+'WindowNetworkState.java'];fixture=selected['tests/gecko/CompactChromeIntegrationActivity.java'];current='void capturePresentation(' in fixture
 methods=['void update(','private void renderLatest(','private void refreshMetadata(','private static void text(','private static void color(','private static void description(','void showNetwork(']
 initial=[]
 if 'static boolean profileAvailable(' in chrome:
  methods+=['static String profileLabel(','static boolean profileAvailable(','static boolean sameProfile(','private void applyMetadata(']
  initial.append(next(line.strip() for line in chrome.splitlines() if line.strip().startswith('profileRow=ProfileCatalog.get(a).item(')))
 initial += [next(line.strip() for line in chrome.splitlines() if line.strip().startswith(prefix)) for prefix in ['compactTitle=ReferenceUi.text(', 'title=ReferenceUi.text(', 'profileName=title.getText()']]
 fixture_methods=['void snapshot(','protected void onDestroy(','protected void onNewIntent(']
 if current:fixture_methods+=['void capturePresentation(','boolean presentationMatches(','boolean presentationLaidOut(','void releasePresentation(','void detachPresentation(']
 fields=next(line for line in state.splitlines() if line.startswith('  final int slot;'))
 java=(HERE/'CompactChromeCaptureHost.java').read_text().replace('/* CHROME_METHODS */','\n'.join(member(chrome,n) for n in methods)).replace('/* INITIAL_METADATA */','\n'.join(initial)).replace('/* STATE_FIELDS */',fields).replace('/* STATE_METHODS */','\n'.join(member(state,n) for n in ['WindowNetworkState(Context c,','int color(','String mainline(','String strip('])).replace('/* FIXTURE_METHODS */','\n'.join(member(fixture,n) for n in fixture_methods))
 java=java.replace('/* CATALOG_EXIT_ID */',member(selected[PROD+'NetworkCatalog.java'],'static String exitId(')).replace('/* NATIVE_METHODS */','\n'.join(member(selected[PROD+'NativeNetwork.java'],n) for n in ['static boolean subscribedExit(','static String exitIdentity(','static String hash(']))
 final_report=member(fixture,'void report(String event,').replace('"syntheticPresentation",true,"actualLatencyMeasurement",false,','')
 assert hashlib.sha256(final_report.encode()).hexdigest()==ORIGINAL_REPORT_SHA256,'Original geometry/touch/text report body changed'
 runner_contract=contract.verify_shared_ui_source(selected['tests/gecko/run_ui_visuals.py'])
 snapshot=member(fixture,'void snapshot(');assert '"delay",42,"delayAt",now' in snapshot and '"latencyRemaining",120000' in snapshot
 assert ',100);' in snapshot and '}},200);' in snapshot,'Original 200/100 preparation intervals changed'
 with tempfile.TemporaryDirectory(prefix='compact-chrome-capture-host-') as raw:
  temp=pathlib.Path(raw);src=temp/'src';src.mkdir();(src/'CompactChromeCaptureHost.java').write_text(java);(src/helper.name).write_bytes(helper.read_bytes())
  for name in ['LatencyRefreshPolicy','LatencyProbePolicy','NetworkStatusPolicy','NetworkOptimizationPolicy','Sha256']:(src/(name+'.java')).write_text(selected[PROD+name+'.java'])
  stubs={'android/content/Context.java':'package android.content; public class Context{public SharedPreferences getSharedPreferences(String name,int mode){return new SharedPreferences();}}','android/content/SharedPreferences.java':'package android.content; public class SharedPreferences{public String getString(String key,String fallback){return fallback;}public boolean getBoolean(String key,boolean fallback){return fallback;}}','android/content/Intent.java':'package android.content; public class Intent{public String command="new-command",action="";public String getStringExtra(String key){return key.equals("compactCommand")?command:action;}}','android/os/SystemClock.java':'package android.os; public class SystemClock{public static long now;public static long elapsedRealtime(){return now;}}','android/text/TextUtils.java':'package android.text; public class TextUtils{public static boolean equals(CharSequence a,CharSequence b){if(a==b)return true;int length;if(a!=null&&b!=null&&(length=a.length())==b.length()){if(a instanceof String&&b instanceof String)return a.equals(b);for(int i=0;i<length;i++)if(a.charAt(i)!=b.charAt(i))return false;return true;}return false;}}'}
  for name,text in stubs.items():path=src/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
  classes=temp/'classes';subprocess.run([str(a.java_home/'bin/javac'),'-encoding','UTF-8','-cp',str(a.json_jar),'-d',str(classes),*map(str,src.rglob('*.java'))],check=True)
  run=subprocess.run([str(a.java_home/'bin/java'),'-Dbefore='+str(not current).lower(),'-cp',str(classes)+':'+str(a.json_jar),'local.pocketchat.CompactChromeCaptureHost'],text=True,capture_output=True)
  if not run.stdout:raise RuntimeError(run.stderr)
  report=json.loads(run.stdout)
 report.update(sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),sourceDirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)),selectedProductionRef=a.before_ref or 'working-tree',selectedSourceSha256={name:hashlib.sha256(text.encode()).hexdigest() for name,text in selected.items()},sourceFiles=hashes,executionInputsUnchanged=all(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest for path,digest in hashes.items()),jsonJarSha256=hashlib.sha256(a.json_jar.read_bytes()).hexdigest(),actualAndroidExecution=False,actualLatencyMeasurement=False,originalGeometryReportPreserved=True,originalAndroidRunnerPreserved=True,original42Ms120SecondSamplePreserved=True,originalPreparationIntervalsPreserved=True,extractedFixtureMethods=fixture_methods,extractedChromeMethods=methods,scope='Actual complete fixture snapshot/capture/presentation/lifecycle methods, complete test-only capture helper, actual production chrome render/showNetwork/metadata methods and network-state constructor. Controlled Handler/View/ViewTreeObserver/layout/catalogue/runtime adapters. The geometry report callback records displayed values; the full geometry body is byte-checked and the Android runner preserves the original complete AST after strict normalization of the reviewed downloads-only label addition. Neither source check executes the Android runner. No real Android frame, Gecko, native network or latency execution.')
 report['androidRunnerSourceContract']=runner_contract
 if not report['executionInputsUnchanged']:report['status']='source-changed'
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':report['status'],'passed':report['passed'],'total':report['total'],'output':str(a.output)}))
 if run.returncode or report['status']!='passed':raise SystemExit(1)
if __name__=='__main__':main()
