#!/usr/bin/env python3
"""Exercise actual fixture capture methods on a controlled Android callback queue."""
import argparse,ast,hashlib,importlib.util,json,pathlib,re,subprocess,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[2];HERE=pathlib.Path(__file__).resolve().parent;PROD='app/src/main/java/local/pocketchat/'
# Exact 62a0ff6e44ba08e4bbf28149a11d3f47a4f6a642 source receipts. Normal CI
# checkouts are shallow: preserve the original assertions without git history.
ORIGINAL_REPORT_SHA256='200192382212fee9889cd9905b837d551a27c75fcc4b777acdab3dd9982e63b7'
# Exact report() members from c244835 (the existing synthetic presentation
# declaration) and a193ca8 (five read-only v2 observation additions). Only the
# historical body comparison uses this inverse; Java extraction keeps fixture.
PRESENTATION_REPORT_BYTES=3507
PRESENTATION_REPORT_SHA256='8de01adca0ba191e634a90aa8dc125fbe91e22172f4894ad32d0590ca9af8fd0'
V2_REPORT_BYTES=3982
V2_REPORT_SHA256='4cfa806c09c40ad3dcac9f3217b744f6d9d88b6acb0611e506f24939cc6b2e39'
V2_REPORT_INSERTIONS=(
 ('      JSONArray texts=new JSONArray();','int[] textRoles={16,12,12,11};int textRole=0;','\n      for(TextView text:new TextView[]{designChrome.title,networkLine,latency,designChrome.stateWord}){'),
 ('"clickable",text.isClickable()',',"lineCount",text.getLayout()==null?0:text.getLayout().getLineCount(),"layoutHeight",text.getLayout()==null?0:text.getLayout().getHeight(),"maxLines",text.getMaxLines(),"textSizePx",text.getTextSize(),"expectedTextSizePx",android.util.TypedValue.applyDimension(android.util.TypedValue.COMPLEX_UNIT_SP,textRoles[textRole++],getResources().getDisplayMetrics())','));\n      }\n      Rect networkBounds=screenBounds(designChrome.networkRow);'),
 ('"contentHeight",dot.getHeight()-dot.getPaddingTop()-dot.getPaddingBottom()',',"height",dot.getHeight()',');\n      Log.i("PocketCompactChrome",J.obj('),
 ('"fontScale",getResources().getConfiguration().fontScale,','"navigationContract",2,','"toolbar",rect(toolbarBounds),'),
 ('"toolbar",rect(toolbarBounds),','"topBounds",bounds(top),','"toolbarHeightDp",toolbar.getHeight()/density(),'),
)

def report_pin(text):
 assert type(text) is str,'Report source must be text'
 raw=text.encode('utf-8')
 return len(raw),hashlib.sha256(raw).hexdigest()

def restore_v2_report_body(text):
 assert report_pin(text)==(V2_REPORT_BYTES,V2_REPORT_SHA256),'Unknown v2 geometry report body'
 restored=text
 for left,addition,right in V2_REPORT_INSERTIONS:
  context=left+addition+right
  assert restored.count(context)==1,'V2 report addition is missing, duplicated or moved'
  restored=restored.replace(context,left+right,1)
 assert report_pin(restored)==(PRESENTATION_REPORT_BYTES,PRESENTATION_REPORT_SHA256),'Original presentation report body changed'
 return restored

def historical_report_body(text):
 if report_pin(text) in ((3445,ORIGINAL_REPORT_SHA256),(PRESENTATION_REPORT_BYTES,PRESENTATION_REPORT_SHA256)):return text
 return restore_v2_report_body(text)

contract_path=ROOT/'tests/ui_visual_preservation_contract.py'
contract_spec=importlib.util.spec_from_file_location('ui_visual_preservation_contract',contract_path);contract=importlib.util.module_from_spec(contract_spec);contract_spec.loader.exec_module(contract)
history_path=ROOT/'tests/historical_source_inputs.py'
history_spec=importlib.util.spec_from_file_location('compact_capture_history',history_path);history=importlib.util.module_from_spec(history_spec);history_spec.loader.exec_module(history)
spec=importlib.util.spec_from_file_location('chrome_production_extractor',ROOT/'tests/chrome-network-state-host/run.py');extract=importlib.util.module_from_spec(spec);spec.loader.exec_module(extract);member=extract.member

def compact_ui_members(source):
 """Select the current complete compact workload, not the unrelated scene capture."""
 tree=ast.parse(source.encode('utf-8'));one=contract.exactly_one
 result={name:one((node for node in ast.walk(tree) if isinstance(node,ast.FunctionDef) and node.name==name),name)
         for name in ('adb','dump','chrome_event','focus','visible','quick_environment_sheet')}
 workload=one((node for node in tree.body if isinstance(node,ast.Try) and
               any(contract.assignment(child,'compact') for child in node.body)),'compact workload')
 start=one((index for index,node in enumerate(workload.body) if contract.assignment(node,'compact')),'compact records')
 end=one((index for index,node in enumerate(workload.body) if isinstance(node,ast.For) and
           any(isinstance(call,ast.Call) and isinstance(call.func,ast.Name) and call.func.id=='capture_compact_v2' for call in ast.walk(node))),'complete compact capture loop')
 assert start<end,'Compact initialization must precede its complete loop'
 result['compactWorkload']=ast.Module(body=workload.body[start:end+1],type_ignores=[])
 result['compactImport']=one((node for node in tree.body if isinstance(node,ast.ImportFrom) and node.module=='compact_chrome_v2'),'compact consumer import')
 for name in ('UI_NAVIGATION_CONTRACT','ui_capture'):
  result[name]=one((node for node in tree.body if contract.assignment(node,name)),name)
 return result

def verify_current_compact_ui_source(source):
 path='tests/gecko/run_ui_visuals.py';released=history.historical_bytes(path).decode('utf-8')
 # The old whole-file inverse proves immutable release history only. Actual
 # helper methods and the complete compact loop are compared directly below.
 receipt=contract.verify_shared_ui_source(released)
 actual=compact_ui_members(source);expected=compact_ui_members(released)
 menu=contract.exactly_one((node for node in ast.walk(expected['compactWorkload']) if contract.assignment(node,'label')),'compact menu label')
 assert isinstance(menu.value,ast.Constant) and menu.value.value=='会话选项','Released compact menu identity changed'
 # Explicit current product wording; no current source is normalized into the
 # historical whole-file inverse, and every other compact AST node must match.
 menu.value=ast.Constant(value='浏览器菜单')
 for name,node in actual.items():
  assert ast.dump(node,include_attributes=False)==ast.dump(expected[name],include_attributes=False),('Current compact UI consumer changed',name)
 receipt.update(historicalSource=history.historical_identity(path),historicalProofOnly=True,
                currentCompactSourceSha256=hashlib.sha256(source.encode('utf-8')).hexdigest(),
                currentCompactMembersAstSha256={name:contract.digest(node) for name,node in actual.items()},
                currentCompactWorkloadPreserved=True,currentMenuLabel='浏览器菜单',
                currentWholeUiWorkloadClaimed=False,actualAndroidExecution=False)
 return receipt

def main():
 p=argparse.ArgumentParser();p.add_argument('--java-home',required=True,type=pathlib.Path);p.add_argument('--json-jar',required=True,type=pathlib.Path);p.add_argument('--before-ref');p.add_argument('--output',required=True,type=pathlib.Path);a=p.parse_args()
 names=['DesignChrome','WindowNetworkState','LatencyRefreshPolicy','LatencyProbePolicy','NetworkStatusPolicy','NetworkOptimizationPolicy','Sha256','NativeNetwork','NetworkCatalog']
 paths=[PROD+name+'.java' for name in names]+['tests/gecko/CompactChromeIntegrationActivity.java','tests/gecko/run_ui_visuals.py']
 selected={path:(subprocess.check_output(['git','show',a.before_ref+':'+path],cwd=ROOT).decode() if a.before_ref else (ROOT/path).read_text()) for path in paths}
 helper=ROOT/'tests/gecko/CompactChromePresentationCapture.java'
 inputs=[ROOT/path for path in paths]+[helper,HERE/'CompactChromeCaptureHost.java',pathlib.Path(__file__).resolve(),ROOT/'tests/chrome-network-state-host/run.py',contract_path,history_path,ROOT/'tools/browser/source_history.py']
 hashes={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs}
 chrome=selected[PROD+'DesignChrome.java'];state=selected[PROD+'WindowNetworkState.java'];fixture=selected['tests/gecko/CompactChromeIntegrationActivity.java'];current='void capturePresentation(' in fixture
 methods=['void update(','private void renderLatest(','private void refreshMetadata(','private static void text(','private static void color(','private static void description(','void showNetwork(']
 if 'void updateMetrics(' in chrome:methods+=['void updateMetrics(','void cancelUpdates(']
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
 java=java.replace('/* STATE_IDENTITY */',member(state,'static boolean sameEnvironment(') if 'static boolean sameEnvironment(' in state else '')
 final_report=historical_report_body(member(fixture,'void report(String event,')).replace('"syntheticPresentation",true,"actualLatencyMeasurement",false,','')
 assert hashlib.sha256(final_report.encode()).hexdigest()==ORIGINAL_REPORT_SHA256,'Original geometry/touch/text report body changed'
 runner_contract=contract.verify_shared_ui_source(selected['tests/gecko/run_ui_visuals.py']) if a.before_ref else verify_current_compact_ui_source(selected['tests/gecko/run_ui_visuals.py'])
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
 report.update(sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),sourceDirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)),selectedProductionRef=a.before_ref or 'working-tree',selectedSourceSha256={name:hashlib.sha256(text.encode()).hexdigest() for name,text in selected.items()},sourceFiles=hashes,executionInputsUnchanged=all(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest for path,digest in hashes.items()),jsonJarSha256=hashlib.sha256(a.json_jar.read_bytes()).hexdigest(),actualAndroidExecution=False,actualLatencyMeasurement=False,originalGeometryReportPreserved=True,originalAndroidRunnerPreserved=True,originalAndroidRunnerHistoricalProofOnly=True,original42Ms120SecondSamplePreserved=True,originalPreparationIntervalsPreserved=True,extractedFixtureMethods=fixture_methods,extractedChromeMethods=methods,scope='Actual complete fixture snapshot/capture/presentation/lifecycle methods, complete test-only capture helper, actual production chrome render/showNetwork/metadata methods and network-state constructor. Controlled Handler/View/ViewTreeObserver/layout/catalogue/runtime adapters. The full geometry report body is byte-checked. The old complete Android runner AST proof uses explicit historical input; current mode directly checks the complete compact loop, helpers and bindings with the current browser menu label. Neither source check executes the Android runner or claims current unrelated scene acceptance. Metrics-maintenance and persistence references are controlled unused boundaries here; the separate chat-chrome-performance-host suite executes those production methods. No real Android frame, Gecko, native network or latency execution.')
 report['androidRunnerSourceContract']=runner_contract
 if not report['executionInputsUnchanged']:report['status']='source-changed'
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':report['status'],'passed':report['passed'],'total':report['total'],'output':str(a.output)}))
 if run.returncode or report['status']!='passed':raise SystemExit(1)
if __name__=='__main__':main()
