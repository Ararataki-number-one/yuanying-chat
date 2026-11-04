#!/usr/bin/env python3
"""Execute exact route and candidate fences with explicit JVM boundaries."""
from pathlib import Path
import argparse, hashlib, importlib.util, json, os, re, subprocess

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--java-home',type=Path,default=Path(os.environ.get('JAVA_HOME',ROOT/'work/cloud-setup/jdk/usr/lib/jvm/java-17-openjdk-amd64')))
parser.add_argument('--json-jar',type=Path,default=ROOT/'work/ux-build-deps/json-20240303.jar')
parser.add_argument('--output',type=Path,default=ROOT/'work/chromium-route-lease-boundaries.json')
args=parser.parse_args()
output=args.output.resolve();output.parent.mkdir(parents=True,exist_ok=True)
work=output.parent/(output.stem+'-work');work.mkdir(parents=True,exist_ok=True)
prod=ROOT/'app/src/main/java/local/pocketchat'
java=args.java_home.resolve()/'bin';jar=args.json_jar.resolve()
helper=ROOT/'tools/gecko/run_network_core_host.py'
spec=importlib.util.spec_from_file_location('chromium_lease_production_blocks',helper)
extract=importlib.util.module_from_spec(spec);spec.loader.exec_module(extract)
texts={name:(prod/name).read_text() for name in ['NativeNetwork.java','NetworkUiProvider.java','NetworkRegion.java','NetworkApplyCoordinator.java','ChromiumRuntime.java']}
methods={
 'NATIVE_ROUTE_BUSY':('NativeNetwork.java','  boolean routeBusy('),
 'NATIVE_BACKGROUND_IDLE':('NativeNetwork.java','  boolean backgroundIdle('),
 'NATIVE_SELECT_NOW':('NativeNetwork.java','  void selectNow('),
 'NATIVE_START_OPERATION':('NativeNetwork.java','  synchronized void startOperation('),
 'NATIVE_RUN_HEALTH':('NativeNetwork.java','  void runHealth('),
 'NATIVE_PAUSE_BACKGROUND':('NativeNetwork.java','  synchronized void pauseBackgroundWhenBusy('),
 'NATIVE_CANCEL_MAINTENANCE':('NativeNetwork.java','  synchronized void cancelMaintenance('),
 'PROVIDER_CHROMIUM_CHANGED':('NetworkUiProvider.java','  static void chromiumLeaseChanged('),
 'PROVIDER_OBSERVE_CHROMIUM':('NetworkUiProvider.java','  void observeChromiumLease()'),
 'PROVIDER_OBSERVE_CHROMIUM_SNAPSHOT':('NetworkUiProvider.java','  void observeChromiumLease(ChromiumRouteLease.Snapshot state)'),
 'PROVIDER_BUSY':('NetworkUiProvider.java','  boolean busy('),
 'PROVIDER_TASK_IDLE':('NetworkUiProvider.java','  static boolean taskIdle('),
 'PROVIDER_FENCE_IDLE':('NetworkUiProvider.java','  boolean fenceIdle('),
 'PROVIDER_ADMIT_CANDIDATE':('NetworkUiProvider.java','  void admitCandidate('),
 'PROVIDER_WAIT_SAVED':('NetworkUiProvider.java','  void waitSaved('),
 'PROVIDER_OPERATE':('NetworkUiProvider.java','  void operate('),
 'RUNTIME_SURFACE_DEFERRED':('ChromiumRuntime.java','  void surfaceDeferred('),
 'RUNTIME_LEASE_CHANGED':('ChromiumRuntime.java','  void leaseChanged('),
 'REGION_BACKGROUND_BUSY':('NetworkRegion.java','  static boolean backgroundBusy('),
}
fragments={key:extract.block(texts[name],signature) for key,(name,signature) in methods.items()}
fragments['COORDINATOR_CONSTANTS']=next(line.strip() for line in texts['NetworkApplyCoordinator.java'].splitlines() if 'static final String UNSELECTED=' in line)
source=(HERE/'LeaseBoundaries.java.in').read_text()
for key,value in fragments.items():source=source.replace('@'+key+'@',value)
if re.search(r'@[A-Z_]+@',source):raise RuntimeError('Unexpanded production method marker')
generated=work/'LeaseBoundaries.java';generated.write_text(source)
production=[prod/name for name in ['ChromiumRouteLease.java','NetworkHealthPolicy.java','NetworkOptimizationPolicy.java','NetworkWork.java','NetworkApplyRetry.java','TaskGuardSnapshot.java','BrowserRuntimePolicy.java','J.java']]
inputs=production+[prod/name for name in texts]+[HERE/'LeaseBoundaries.java.in',Path(__file__).resolve(),helper]
hashes={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs}
clock=work/'android/os/SystemClock.java';clock.parent.mkdir(parents=True,exist_ok=True);clock.write_text('package android.os; public final class SystemClock { public static long now=1000000; public static long elapsedRealtime(){return now;} }\n')
classes=work/'classes';classes.mkdir(parents=True,exist_ok=True)
compiled=subprocess.run([str(java/'javac'),'-encoding','UTF-8','-cp',str(jar),'-d',str(classes),*map(str,production),str(generated),str(clock)],capture_output=True,text=True)
(work/'compile.stdout.log').write_text(compiled.stdout);(work/'compile.stderr.log').write_text(compiled.stderr)
if compiled.returncode:
 print(compiled.stdout+compiled.stderr);raise SystemExit(compiled.returncode)
result=subprocess.run([str(java/'java'),'-cp',str(classes)+os.pathsep+str(jar),'local.pocketchat.LeaseBoundaries'],capture_output=True,text=True)
(work/'stdout.log').write_text(result.stdout);(work/'stderr.log').write_text(result.stderr)
if result.returncode:
 print(result.stdout+result.stderr);raise SystemExit(result.returncode)
report=json.loads(result.stdout)
assert report['passed']==len(report['checks']) and all(check['pass'] for check in report['checks'])
unchanged=all(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest for path,digest in hashes.items())
report.update(scope='Complete production ChromiumRouteLease and exact NativeNetwork routeBusy/backgroundIdle/selectNow/startOperation/runHealth; exact NetworkUiProvider candidate busy/task/final fence/admit/operate/reason/release-wake methods and ChromiumRuntime surfaceDeferred/leaseChanged. Controller, startup execution, session, persistence, looper and android.os.SystemClock use explicit JVM boundaries. The single-method clock double is host-only and is not Android API verification. No Android device, real HTTP/controller or full configuration transaction execution claimed.',productionMethodSha256={key:hashlib.sha256(value.encode()).hexdigest() for key,value in fragments.items()},sourceSha256=hashes,generatedAdapterSha256=hashlib.sha256(generated.read_bytes()).hexdigest(),jsonJarSha256=hashlib.sha256(jar.read_bytes()).hexdigest(),hostClockSha256=hashlib.sha256(clock.read_bytes()).hexdigest(),executionInputsUnchanged=unchanged,javaVersion=subprocess.check_output([str(java/'java'),'-version'],stderr=subprocess.STDOUT,text=True).strip())
if not unchanged:report['status']='source-changed'
output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':report['status'],'passed':report['passed'],'report':str(output)},ensure_ascii=False))
if report['status']!='passed':raise SystemExit(1)
