#!/usr/bin/env python3
"""Separate an original-budget failure from the pending external cleanup proof."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('actual_member_extractor', ROOT/'tests/source-route-start-host/run.py')
extractor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extractor)
member = extractor.member
NATIVE = ['interface Callback', 'enum RecoveryState', 'static final class RecoveryOutcome',
          'interface RecoveryCallback', 'static final class RecoveryAdapter',
          'void start(Callback callback)', 'void restart(Callback callback)', 'void recover(Callback callback)',
          'void recoverOutcome(RecoveryCallback callback)', 'synchronized void startOperation(',
          'void runStartOperation(', 'void invalidateVerifiedRoute(', 'void clearReadyState(',
          'boolean stopNow()', 'boolean stopNow(NetworkDiagnostics.Reason reason)']
TERMINAL = ['static long now(', 'static JSONObject copy(', 'static void require(',
            'static long remaining(', 'static final class Recovery', 'static final class Scope',
            'Scope begin(', 'void beginFetch(', '<T>T ui(']

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def run(java_home, json_jar, output):
    native = ROOT/'app/src/main/java/local/pocketchat/NativeNetwork.java'
    session = ROOT/'app/src/main/java/local/pocketchat/ChatSession.java'
    terminal = ROOT/'tests/gecko/SourceRouteTerminalObserver.java'
    observer = ROOT/'tests/gecko/SourceRouteStartObservation.java'
    reservation = ROOT/'tests/gecko/SourceRouteStartReservation.java'
    whole_json = ROOT/'app/src/main/java/local/pocketchat/J.java'
    inputs = [native, session, terminal, observer, reservation, whole_json, HERE/'ReservationHost.java',
              HERE/'README.md', Path(__file__).resolve(), ROOT/'tests/source-route-start-host/run.py']
    hashes = {str(path.relative_to(ROOT)): sha(path) for path in inputs}
    generated = (HERE/'ReservationHost.java').read_text().replace(
        '/* ACTUAL_NATIVE_MEMBERS */', '\n'.join(member(native.read_text(), item) for item in NATIVE)).replace(
        '/* ACTUAL_SESSION_RETRY */', member(session.read_text(), 'void runRecovery(')).replace(
        '/* ACTUAL_TERMINAL_MEMBERS */', '\n'.join(member(terminal.read_text(), item) for item in TERMINAL))
    output.parent.mkdir(parents=True, exist_ok=True)
    raw = output.parent/(output.stem+'-raw')
    raw.mkdir(exist_ok=True)
    (raw/'generated-ReservationHost.java').write_text(generated)
    (raw/'inputs.json').write_text(json.dumps({'sourceFiles':hashes,
        'generatedSha256':hashlib.sha256(generated.encode()).hexdigest(),
        'selectedNativeMembers':NATIVE,'selectedTerminalMembers':TERMINAL,
        'selectedSessionMembers':['void runRecovery(']},indent=2)+'\n')
    for path in (observer,reservation,whole_json):
        (raw/path.name).write_bytes(path.read_bytes())
    with tempfile.TemporaryDirectory(prefix='source-route-reservation-') as name:
        directory = Path(name)
        java = directory/'local/pocketchat/ReservationHost.java'
        java.parent.mkdir(parents=True)
        java.write_text(generated)
        clock = directory/'android/os/SystemClock.java'
        clock.parent.mkdir(parents=True)
        clock.write_text('package android.os; public final class SystemClock {private static final java.util.concurrent.atomic.AtomicLong clock=new java.util.concurrent.atomic.AtomicLong(1000000000L);public static long elapsedRealtimeNanos(){return clock.getAndIncrement();}public static long elapsedRealtime(){return clock.get()/1000000L;}public static void set(long value){clock.set(value);}public static void advance(long value){clock.addAndGet(value);}}\n')
        compiled = subprocess.run([str(java_home/'bin/javac'), '-encoding', 'UTF-8', '-cp', str(json_jar),
            '-d', str(directory), str(java), str(observer), str(reservation), str(whole_json), str(clock)],
            capture_output=True, timeout=30)
        (raw/'compile.stdout').write_bytes(compiled.stdout)
        (raw/'compile.stderr').write_bytes(compiled.stderr)
        if compiled.returncode:
            raise RuntimeError(compiled.stderr.decode())
        executed = subprocess.run([str(java_home/'bin/java'), '-cp', str(directory)+':'+str(json_jar),
            'local.pocketchat.ReservationHost', str(output)], capture_output=True, timeout=30)
        (raw/'stdout.log').write_bytes(executed.stdout)
        (raw/'stderr.log').write_bytes(executed.stderr)
    report = json.loads(output.read_text())
    report.update(sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        sourceDirty=bool(subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True).strip()),
        sourceFiles=hashes, extractedNativeMembers=NATIVE, extractedTerminalMembers=TERMINAL,
        extractedSessionMembers=['void runRecovery('], generatedSha256=hashlib.sha256(generated.encode()).hexdigest(),
        jsonJarSha256=sha(json_jar), executionInputsUnchanged=all(sha(ROOT/path)==digest for path,digest in hashes.items()),
        exitCode=executed.returncode, originalBusiness77Executed=False, originalTerminalFreshIpcExecuted=False,
        fullAndroidFixtureExecuted=False, clocks='Controlled logical nanoseconds; actual JVM futures/threads.75s/22s constants preserved, not physical timing measurements.',
        rawFiles={str(path): {'bytes':path.stat().st_size,'sha256':sha(path)} for path in raw.iterdir() if path.is_file()})
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'hostControlsComplete':report['hostControlsComplete'],
        'passed':report['passed'],'total':report['total'],'prototypeAcceptedAsRepair':False,'output':str(output)}))
    if not report['executionInputsUnchanged'] or not report['hostControlsComplete']:
        raise SystemExit(1)
    raise SystemExit(2 if report['status']=='cleanup-proof-pending' else 1)

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--java-home',required=True,type=Path)
    parser.add_argument('--json-jar',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    run(args.java_home.resolve(),args.json_jar.resolve(),args.output.resolve())
