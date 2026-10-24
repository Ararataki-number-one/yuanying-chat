#!/usr/bin/env python3
"""Execute selected complete actual Activity reservation paths; never Android evidence."""
import argparse, hashlib, importlib.util, json, re, subprocess, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('reservation_actual_members',HERE/'run.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
member=base.member
ACTIVITY=['final class ReservedCaseGate','void reject(']
HOOKS=['synchronized void startOperation(', 'void runStartOperation(']
TERMINAL=['static long now(', 'static JSONObject copy(', 'static void require(', 'static long remaining(', 'static final class Recovery', 'static final class Scope', 'void beginFetch(', '<T>T ui(', 'void restartDone(']

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def original_checks(source):
    calls=[]
    for match in re.finditer(r'\bcheck\(',source):
        if source[max(0,match.start()-5):match.start()]=='void ':continue
        i=match.end();depth=1;quote=None;escaped=False
        while depth:
            char=source[i];i+=1
            if quote:
                if escaped:escaped=False
                elif char=='\\':escaped=True
                elif char==quote:quote=None
            elif char in ('"',"'"):quote=char
            elif char=='(':depth+=1
            elif char==')':depth-=1
        calls.append(source[match.start():i])
    digest=hashlib.sha256('\n'.join(calls).encode()).hexdigest()
    assert len(calls)==39 and digest=='253c0e448cbe73bfd2c015634241abeb4567ec1e6e16ecbb6dcba79df94c3b0c', 'Original77 runtime business assertions changed'
    assert re.findall(r'      reject\("([^"]+)"',source)==['invalid-entry-snapshot-sha','invalid-exit-snapshot-sha','same-name-changed-exit','same-name-changed-entry']
    return digest
def run(java_home,json_jar,output):
    native=ROOT/'app/src/main/java/local/pocketchat/NativeNetwork.java';session=ROOT/'app/src/main/java/local/pocketchat/ChatSession.java'
    activity=ROOT/'tests/gecko/NetworkSourcesRouteIntegrationActivity.java';terminal=ROOT/'tests/gecko/SourceRouteTerminalObserver.java'
    observer=ROOT/'tests/gecko/SourceRouteStartObservation.java';reservation=ROOT/'tests/gecko/SourceRouteStartReservation.java';whole_json=ROOT/'app/src/main/java/local/pocketchat/J.java'
    inputs=[native,session,activity,terminal,observer,reservation,whole_json,HERE/'ActivityReservationHost.java',HERE/'run.py',Path(__file__).resolve(),ROOT/'tests/source-route-start-host/run.py']
    hashes={str(p.relative_to(ROOT)):sha(p) for p in inputs}
    preserved_checks=original_checks(activity.read_text())
    hook_source=member(activity.read_text(),'static final class RouteNetwork')
    generated=(HERE/'ActivityReservationHost.java').read_text().replace('/* ACTUAL_NATIVE_MEMBERS */','\n'.join(member(native.read_text(),n) for n in base.NATIVE)).replace('/* ACTUAL_SESSION_RETRY */',member(session.read_text(),'void runRecovery(')).replace('/* ACTUAL_ACTIVITY_WORKER_HOOKS */','\n'.join(member(hook_source,n) for n in HOOKS)).replace('/* ACTUAL_ACTIVITY_GATE_AND_REJECT */','\n'.join(member(activity.read_text(),n) for n in ACTIVITY)).replace('/* ACTUAL_TERMINAL_MEMBERS */','\n'.join(member(terminal.read_text(),n) for n in TERMINAL))
    output.parent.mkdir(parents=True,exist_ok=True);raw=output.parent/(output.stem+'-raw');raw.mkdir(exist_ok=True)
    (raw/'generated-ActivityReservationHost.java').write_text(generated)
    (raw/'inputs.json').write_text(json.dumps(dict(sourceFiles=hashes,activityMembers=ACTIVITY,workerHooks=HOOKS,terminalMembers=TERMINAL,generatedSha256=hashlib.sha256(generated.encode()).hexdigest()),indent=2)+'\n')
    with tempfile.TemporaryDirectory(prefix='actual-activity-reservation-') as d:
        d=Path(d);java=d/'local/pocketchat/ActivityReservationHost.java';java.parent.mkdir(parents=True);java.write_text(generated)
        clock=d/'android/os/SystemClock.java';clock.parent.mkdir(parents=True)
        clock.write_text('package android.os; public final class SystemClock {public static long elapsedRealtimeNanos(){return System.nanoTime();}public static long elapsedRealtime(){return System.nanoTime()/1000000L;}}')
        looper=d/'android/os/Looper.java';looper.write_text('package android.os; public final class Looper {private static final Looper MAIN=new Looper();private static final Thread OWNER=Thread.currentThread();public static Looper getMainLooper(){return MAIN;}public static Looper myLooper(){return Thread.currentThread()==OWNER?MAIN:null;}}')
        compiled=subprocess.run([str(java_home/'bin/javac'),'-encoding','UTF-8','-cp',str(json_jar),'-d',str(d),str(java),str(observer),str(reservation),str(whole_json),str(clock),str(looper)],capture_output=True,timeout=30)
        (raw/'compile.stdout').write_bytes(compiled.stdout);(raw/'compile.stderr').write_bytes(compiled.stderr)
        if compiled.returncode:raise RuntimeError(compiled.stderr.decode())
        executed=subprocess.run([str(java_home/'bin/java'),'-cp',str(d)+':'+str(json_jar),'local.pocketchat.ActivityReservationHost',str(output)],capture_output=True,timeout=30)
        (raw/'stdout.log').write_bytes(executed.stdout);(raw/'stderr.log').write_bytes(executed.stderr)
        if executed.returncode:raise RuntimeError(executed.stderr.decode())
    report=json.loads(output.read_text());report.update(sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),sourceDirty=bool(subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True).strip()),sourceFiles=hashes,executionInputsUnchanged=all(sha(ROOT/p)==v for p,v in hashes.items()),jsonJarSha256=sha(json_jar),activityMembers=ACTIVITY,workerHooks=HOOKS,terminalMembers=TERMINAL,originalBusinessExpressionsSha256=preserved_checks,originalBusinessExpressionCount=39,generatedSha256=hashlib.sha256(generated.encode()).hexdigest(),rawFiles={str(p):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in raw.iterdir() if p.is_file()})
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    assert report['status']=='host-controls-passed-android-candidate' and report['passed']==report['total']==18 and len(report['checks'])==18 and len(report['cases'])==8 and all(c['pass'] is True for c in report['checks']) and report['executionInputsUnchanged'] and not report['actualAndroidExecution'] and not report['acceptedAsRepair']
    print(json.dumps(dict(status=report['status'],passed=report['passed'],total=report['total'],output=str(output))))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--java-home',type=Path,required=True);p.add_argument('--json-jar',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.java_home.resolve(),a.json_jar.resolve(),a.output.resolve())
