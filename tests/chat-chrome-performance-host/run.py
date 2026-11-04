#!/usr/bin/env python3
"""Replay real chrome/metrics/save methods with separately controlled Handler and frame queues."""
import argparse,hashlib,importlib.util,json,pathlib,subprocess,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[2]
HERE=pathlib.Path(__file__).resolve().parent
PROD='app/src/main/java/local/pocketchat/'
spec=importlib.util.spec_from_file_location('chrome_extractor',ROOT/'tests/chrome-network-state-host/run.py')
extract=importlib.util.module_from_spec(spec);spec.loader.exec_module(extract)
member=extract.member

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--java-home',required=True,type=pathlib.Path)
    parser.add_argument('--json-jar',required=True,type=pathlib.Path)
    parser.add_argument('--before-ref')
    parser.add_argument('--output',required=True,type=pathlib.Path)
    args=parser.parse_args()
    names=['DesignChrome','NetworkMetricsUi','WindowNetworkState','LatencyRefreshPolicy','LatencyProbePolicy','NetworkStatusPolicy','NetworkOptimizationPolicy','Sha256','NativeNetwork','NetworkCatalog']
    selected={name:(subprocess.check_output(['git','show',args.before_ref+':'+PROD+name+'.java'],cwd=ROOT).decode() if args.before_ref else (ROOT/(PROD+name+'.java')).read_text()) for name in names}
    chrome=selected['DesignChrome'];metrics=selected['NetworkMetricsUi'];state=selected['WindowNetworkState']
    current='void updateMetrics(' in chrome
    chrome_methods=['void update(','private void renderLatest(','private void refreshMetadata(','static String profileLabel(','static boolean profileAvailable(','static boolean sameProfile(','private void applyMetadata(','private static void text(','private static void description(']
    if current:chrome_methods+=['void updateMetrics(','void cancelUpdates(']
    metrics_methods=['static final class Refresh ','static void update(','static void updateNow(']
    if 'static NativeNetwork maintainNow(' in metrics:metrics_methods+=['static NativeNetwork maintainNow(']
    save_methods=['static synchronized void save(Context c,ChatSession s,NativeNetwork n)']
    if current:save_methods+=['static synchronized void save(Context c,ChatSession s,NativeNetwork n,JSONObject value)']
    initial=[next(line.strip() for line in chrome.splitlines() if line.strip().startswith(prefix)) for prefix in ['profileRow=ProfileCatalog.get(a).item(', 'compactTitle=ReferenceUi.text(', 'title=ReferenceUi.text(', 'profileName=title.getText()']]
    text=(HERE/'ChatChromePerformanceHost.java').read_text().replace('/* INITIAL_METADATA */','\n'.join(initial)).replace('/* CHROME_METHODS */','\n'.join(member(chrome,needle) for needle in chrome_methods)).replace('/* METRICS_METHODS */','\n'.join(member(metrics,needle) for needle in metrics_methods)).replace('/* STATE_FIELDS */',next(line for line in state.splitlines() if line.startswith('  final int slot;'))).replace('/* STATE_IDENTITY */',member(state,'static boolean sameEnvironment(')).replace('/* STATE_CONSTRUCTOR */',member(state,'WindowNetworkState(Context c,')).replace('/* STATE_SAVE */','\n'.join(member(state,needle) for needle in save_methods))
    text=text.replace('/* CATALOG_EXIT_ID */',member(selected['NetworkCatalog'],'static String exitId(')).replace('/* NATIVE_METHODS */','\n'.join(member(selected['NativeNetwork'],needle) for needle in ['static boolean subscribedExit(','static String exitIdentity(','static String hash(']))
    text=text.replace('/* BASELINE_CHROME_ADAPTER */','' if current else 'void cancelUpdates(){a.handler.tasks.remove(render);queued=false;metricsPending=false;}')
    text=text.replace('/* BASELINE_SAVE_ADAPTER */','' if current else 'static void save(Context c,ChatSession s,NativeNetwork n,JSONObject value){throw new AssertionError("four-argument overload does not exist in baseline");}')
    sources=[ROOT/(PROD+name+'.java') for name in names]+[HERE/'ChatChromePerformanceHost.java',pathlib.Path(__file__).resolve(),ROOT/'tests/chrome-network-state-host/run.py']
    hashes={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}
    with tempfile.TemporaryDirectory(prefix='chat-chrome-performance-') as raw:
        source=pathlib.Path(raw)/'src';source.mkdir();(source/'ChatChromePerformanceHost.java').write_text(text)
        for name in ['LatencyRefreshPolicy','LatencyProbePolicy','NetworkStatusPolicy','NetworkOptimizationPolicy','Sha256']:(source/(name+'.java')).write_text(selected[name])
        stubs={'android/content/Context.java':'package android.content; public class Context{public SharedPreferences getSharedPreferences(String name,int mode){return new SharedPreferences();}}','android/content/SharedPreferences.java':'package android.content; public class SharedPreferences{public String getString(String key,String fallback){return fallback;}public boolean getBoolean(String key,boolean fallback){return fallback;}}','android/os/SystemClock.java':'package android.os; public class SystemClock{public static long now=100000;public static long elapsedRealtime(){return now;}}','android/util/Log.java':'package android.util; public class Log{public static int i(String tag,String value){return 0;}}','android/text/TextUtils.java':'package android.text; public class TextUtils{public static boolean equals(CharSequence left,CharSequence right){return java.util.Objects.equals(left==null?null:left.toString(),right==null?null:right.toString());}}'}
        for name,stub in stubs.items():path=source/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(stub)
        classes=pathlib.Path(raw)/'classes'
        subprocess.run([str(args.java_home/'bin/javac'),'-encoding','UTF-8','-cp',str(args.json_jar),'-d',str(classes),*map(str,source.rglob('*.java'))],check=True)
        result=subprocess.run([str(args.java_home/'bin/java'),'-DframeCoalesced='+str(current).lower(),'-cp',str(classes)+':'+str(args.json_jar),'local.pocketchat.ChatChromePerformanceHost'],capture_output=True,text=True)
        if not result.stdout:raise RuntimeError(result.stderr)
        report=json.loads(result.stdout)
    report.update(selectedProductionRef=args.before_ref or 'working-tree',sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),selectedProductionSha256={name:hashlib.sha256(value.encode()).hexdigest() for name,value in selected.items()},sourceFiles=hashes,jsonJarSha256=hashlib.sha256(args.json_jar.read_bytes()).hexdigest(),executionInputsUnchanged=all(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest for path,digest in hashes.items()),extractedChromeMethods=chrome_methods,extractedMetricsMethods=metrics_methods,extractedSaveMethods=save_methods,scope='Complete selected WindowNetworkState constructor and save overloads, exact DesignChrome update/updateMetrics/cancelUpdates/renderLatest/metadata methods and NetworkMetricsUi Refresh/update/updateNow/maintainNow. Handler, display-frame, catalogue, traffic/audit, async-store and live-projection boundaries are deterministic host adapters. The live boundary copies current synthetic session identity each invocation; it does not run real network projection internals. Async lambda capture inspection checks the identical observation passed to constructor and persistence. No Android, SQLite, native frame-time or network-speed measurement.')
    if not report['executionInputsUnchanged']:report['status']='source-changed'
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'passed':report['passed'],'total':report['total'],'output':str(args.output),'scenarios':report['scenarios']},ensure_ascii=False))
    if result.returncode or report['status']!='passed':raise SystemExit(1)
if __name__=='__main__':main()
