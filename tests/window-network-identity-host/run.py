#!/usr/bin/env python3
"""Execute the full selected production state constructor; no copied identity algorithm."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
PROD='app/src/main/java/local/pocketchat/'

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home',required=True,type=Path);parser.add_argument('--json-jar',required=True,type=Path)
    parser.add_argument('--before-ref');parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();output=args.output.resolve();raw=output.with_name(output.stem+'-raw')
    if output.exists() or raw.exists():raise ValueError('Preserve old evidence; select a new output')
    raw.mkdir(parents=True);src=raw/'src';src.mkdir()
    def git(*parts):return subprocess.check_output(['git',*parts],cwd=ROOT,text=True).strip()
    source,status=git('rev-parse','HEAD'),git('status','--porcelain')
    selected_ref=git('rev-parse',args.before_ref+'^{commit}') if args.before_ref else source
    extractor=ROOT/'tests/chrome-network-state-host/run.py'
    spec=importlib.util.spec_from_file_location('actual_constructor_extractor',extractor);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);member=module.member
    names=['WindowNetworkState','NetworkWorkspaceUi','NetworkCatalog','NativeNetwork','LatencyRefreshPolicy','LatencyProbePolicy','NetworkStatusPolicy','NetworkOptimizationPolicy','Sha256']
    if not args.before_ref:names+=['NetworkCoreApplication','NetworkHealthPolicy','EnvironmentSpec','J']
    selected={name:(subprocess.check_output(['git','show',selected_ref+':'+PROD+name+'.java'],cwd=ROOT) if args.before_ref else (ROOT/(PROD+name+'.java')).read_bytes())for name in names}
    for name,data in selected.items():
        saved=raw/'selected-production'/(name+'.java');saved.parent.mkdir(exist_ok=True);saved.write_bytes(data)
    text={name:data.decode()for name,data in selected.items()};state=text['WindowNetworkState']
    device_fixture=ROOT/'tests/gecko/NetworkOptimizationIntegrationActivity.java'
    (raw/'selected-device-fixture.java').write_bytes(device_fixture.read_bytes())
    java=(HERE/'WindowNetworkIdentityHost.java').read_text()
    replacements={
        'STATE_FIELDS':next(line for line in state.splitlines()if line.startswith('  final int slot;')),
        'STATE_IDENTITY':member(state,'static boolean sameEnvironment(')if 'static boolean sameEnvironment('in state else '',
        'STATE_CONSTRUCTOR':member(state,'WindowNetworkState(Context c,'),'STATE_MAINLINE':member(state,'String mainline('),
        'RUNNING_CONFIGURATION':member(text['NetworkWorkspaceUi'],'static JSONObject runningConfiguration('),
        'CATALOG_EXIT_ID':member(text['NetworkCatalog'],'static String exitId('),
        'CATALOG_SUBSCRIPTION':member(text['NetworkCatalog'],'static String subscriptionName('),
        'NATIVE_METHODS':'\n'.join(member(text['NativeNetwork'],needle)for needle in ['static boolean subscribedExit(','static String exitIdentity(','static String hash(']),
        'DEVICE_IDENTITY_METHODS':'\n'.join(member(device_fixture.read_text(),needle)for needle in ['void checkReadModel(','void readModelIdentityChecks(']),
    }
    for key,value in replacements.items():java=java.replace('/* '+key+' */',value)
    (src/'WindowNetworkIdentityHost.java').write_text(java)
    for name in ('LatencyRefreshPolicy','LatencyProbePolicy','NetworkStatusPolicy','NetworkOptimizationPolicy','Sha256'):(src/(name+'.java')).write_bytes(selected[name])
    stubs={
        'android/content/Context.java':'package android.content; public class Context{public SharedPreferences getSharedPreferences(String name,int mode){return new SharedPreferences();}}',
        'android/content/SharedPreferences.java':'package android.content; public class SharedPreferences{public static String mode="internal",proxy="";public static boolean configured=true;public String getString(String key,String fallback){return key.equals("networkMode")?mode:key.equals("proxy")?proxy:fallback;}public boolean getBoolean(String key,boolean fallback){return key.equals("networkConfigured")?configured:fallback;}}',
        'android/net/Uri.java':'package android.net; public class Uri{String value;public static Uri parse(String value){Uri uri=new Uri();uri.value=value;return uri;}public String getHost(){return java.net.URI.create(value).getHost();}}',
        'android/util/Log.java':'package android.util; public class Log{public static int i(String tag,String value){return 0;}}',
    }
    for name,value in stubs.items():path=src/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(value)
    inputs=[HERE/'WindowNetworkIdentityHost.java',HERE/'ColdCoreWindowStateHost.java.in',Path(__file__).resolve(),extractor,device_fixture]+[ROOT/(PROD+name+'.java')for name in names]+sorted((ROOT/'tools/gecko').glob('*.py'))
    hashes={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()for path in inputs}
    def execute(label,command):
        result=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=60)
        for stream in ('stdout','stderr'):(raw/(label+'.'+stream+'.raw')).write_bytes(getattr(result,stream))
        return result
    classes=raw/'classes'
    compile_command=[str(args.java_home/'bin/javac'),'-encoding','UTF-8','-cp',str(args.json_jar),'-d',str(classes),*map(str,sorted(src.rglob('*.java')))]
    compiled=execute('compile',compile_command)
    if compiled.returncode:raise RuntimeError('Actual selected constructor failed compilation; originals retained in '+str(raw))
    run_command=[str(args.java_home/'bin/java'),'-cp',str(classes)+':'+str(args.json_jar),'local.pocketchat.WindowNetworkIdentityHost']
    run=execute('execute',run_command);report=json.loads(run.stdout)
    projection_command=[str(args.java_home/'bin/java'),'-DdeviceProjection=true','-cp',str(classes)+':'+str(args.json_jar),'local.pocketchat.WindowNetworkIdentityHost']
    projected=execute('device-projection',projection_command);projection=json.loads(projected.stdout)
    if report.get('total')!=93 or report.get('passed')!=93 or len(report.get('checks',[]))!=93 or not all(row.get('pass')is True for row in report['checks']):report['status']='failed'
    if projected.returncode or projection.get('status')!='passed' or projection.get('total')!=14 or projection.get('passed')!=14 or len(projection.get('checks',[]))!=14 or not all(row.get('pass')is True for row in projection['checks']):report['status']='failed'
    report['controlledAndroidProjectionHostReplay']=projection
    if projection.get('status')=='passed':
        sys.path.insert(0,str(ROOT))
        from tools.gecko.check_interaction_transfer_evidence import verify_read_model_identity
        rows=projection['checks'];summary=rows[0]['readModelSummary']
        public=dict(networkReadModelIdentity=dict(summary,cases=[row['readModel']for row in rows]),checks=rows)
        report['controlledAndroidProjectionPublicReplay']=verify_read_model_identity(public)
    if not args.before_ref:
        cold=raw/'cold-src';cold.mkdir();cold_java=(HERE/'ColdCoreWindowStateHost.java.in').read_text()
        cold_members=dict(replacements)
        cold_members.update(STATE_RUNNING=member(state,'static JSONObject running('),STATE_LIVE=member(state,'static JSONObject live('),
            CORE_OBSERVED=member(text['NetworkCoreApplication'],'static NetworkCoreApplication observed('),
            CORE_CURRENT=member(text['NetworkCoreApplication'],'boolean current('),
            CATALOG_PUT=member(text['NetworkCatalog'],'static void put('),
            NATIVE_ADMISSION=member(text['NativeNetwork'],'NetworkHealthPolicy.Admission connectionAdmission('),
            NATIVE_RECEIPT=member(text['NativeNetwork'],'static final class ExitRouteReceipt {'))
        for key,value in cold_members.items():cold_java=cold_java.replace('/* '+key+' */',value)
        (cold/'ColdCoreWindowStateHost.java').write_text(cold_java)
        for name in ('LatencyRefreshPolicy','LatencyProbePolicy','NetworkStatusPolicy','NetworkOptimizationPolicy','Sha256','NetworkHealthPolicy','EnvironmentSpec','J'):(cold/(name+'.java')).write_bytes(selected[name])
        cold_stubs=dict(stubs,**{'android/os/Process.java':'package android.os;public class Process{public static int myPid(){return 1234;}}',
            'android/content/Context.java':'package android.content;public class Context{public static Runnable beforeRead;public SharedPreferences getSharedPreferences(String name,int mode){Runnable hook=beforeRead;beforeRead=null;if(hook!=null)hook.run();return new SharedPreferences();}}'})
        for name,value in cold_stubs.items():
            path=cold/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(value)
        cold_classes=raw/'cold-classes';cold_compile_command=[str(args.java_home/'bin/javac'),'-encoding','UTF-8','-cp',str(args.json_jar),'-d',str(cold_classes),*map(str,sorted(cold.rglob('*.java')))]
        cold_compiled=execute('cold-compile',cold_compile_command)
        if cold_compiled.returncode:raise RuntimeError('Actual cold producer failed compilation; originals retained in '+str(raw))
        cold_run_command=[str(args.java_home/'bin/java'),'-cp',str(cold_classes)+':'+str(args.json_jar),'local.pocketchat.ColdCoreWindowStateHost']
        cold_run=execute('cold-execute',cold_run_command);cold_report=json.loads(cold_run.stdout)
        if cold_run.returncode or cold_report.get('status')!='passed' or cold_report.get('total')!=36 or cold_report.get('passed')!=36 or len(cold_report.get('checks',[]))!=36 or not all(row.get('pass') is True for row in cold_report['checks']):report['status']='failed'
        report['coldCoreProducerHostReplay']=cold_report
        report['coldCoreProducerCommands']=dict(compile=cold_compile_command,execute=cold_run_command)
        report['coldCoreProducerScope']='Exact running/live producers, observed/current predicates and ExitRouteReceipt matching; actual EnvironmentSpec identity and portable policies. Controlled proof construction, cached transport state, opaque fingerprint, preferences and latency adapters. No service IPC/capture, Android, live core or historical-event admission claim.'
    unchanged=source==git('rev-parse','HEAD') and status==git('status','--porcelain') and all(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest for path,digest in hashes.items())
    if not unchanged:report['status']='source-changed'
    report.update(schema=1,sourceCommit=source,sourceDirty=bool(status),selectedProductionRef=selected_ref,
        selectedProductionRole='before'if args.before_ref else 'current',selectedProductionSha256={name:hashlib.sha256(data).hexdigest()for name,data in selected.items()},
        sourceFiles=hashes,executionInputsUnchanged=unchanged,jsonJarSha256=hashlib.sha256(args.json_jar.read_bytes()).hexdigest(),
        commands=dict(compile=compile_command,execute=run_command,deviceProjection=projection_command),returnCodes=dict(compile=compiled.returncode,execute=run.returncode,deviceProjection=projected.returncode),
        actualAndroidExecution=False,actualLatencyMeasurement=False,scope='Complete actual selected production WindowNetworkState constructor, identity helper, mainline and actual runningConfiguration consumer; whole production portable display policies and actual selected NativeNetwork identity/hash and catalog label methods. Controlled Context/preferences/region/URI APIs and prepared observations only; no Android/Binder/Gecko/core/real-route acceptance.')
    artifacts={str(path.relative_to(raw)):dict(bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())for path in sorted(raw.rglob('*'))if path.is_file()}
    manifest=raw/'manifest.json';manifest.write_text(json.dumps(dict(sourceCommit=source,selectedProductionRef=selected_ref,artifacts=artifacts),indent=2)+'\n')
    report['rawEvidence']=dict(directory=str(raw),manifestSha256=hashlib.sha256(manifest.read_bytes()).hexdigest())
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status=report['status'],passed=report['passed'],total=report['total'],output=str(output))))
    if run.returncode or report['status']!='passed':raise SystemExit(1)

if __name__=='__main__':main()
