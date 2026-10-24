#!/usr/bin/env python3
"""Run actual NativeNetwork start scheduling and the test-only observer; no Android claim."""
import argparse
import hashlib
import json
import pathlib
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
EXPECTED_CHECK_NAMES = ['Original mode1 leaves the running restart queued flag false', 'Original start worker launches exactly once for joined recovery', 'Original worker delivers the same immutable outcome to both adapters', 'Observed stop records the real zero-to-one request crossing', 'Join proves original monitor and exact waiter append', 'Stop and join bind the actual worker Java thread', 'A different owned PID cannot reuse the join', 'A different stop case cannot reuse the join', 'A stop returning in another invocation is rejected', 'A stop returning on another Java thread is rejected', 'Restoring exact original observations retains the valid join', 'Original mode2 sets restartQueued while retaining the first waiter', 'Original queued restart executes a second actual worker invocation', 'Queued flag returns false before the second operation completes', 'Both worker invocations reuse the exact original root callback', 'Queued restart ABA is rejected by actual invocation identity', 'Rejecting observation preserves all original queued callbacks', 'Real asynchronous main can deliver both callbacks before workerAfter', 'Callback thread is separate from the actual worker and test caller', 'Callbacks alone cannot stand in for the missing actual worker ending', 'An original bounded wait rejects an unfinished observer without altering it', 'Only actual workerAfter completes the observation future', 'The same asynchronously completed operation now yields a valid join', 'An unregistered adapter cannot claim a joined recovery', 'Unknown-adapter observation does not suppress original callbacks', 'Another scope cannot register a joined recovery', 'Wrong-scope observation does not suppress original callbacks', 'registrationBefore observer failure never skips original worker or callbacks', 'registrationBefore observer failure is retained as rejected evidence', 'registrationBefore incomplete proof cannot pass', 'registrationBefore completes the observation exceptionally instead of waiting indefinitely', 'registrationAfter observer failure never skips original worker or callbacks', 'registrationAfter observer failure is retained as rejected evidence', 'registrationAfter incomplete proof cannot pass', 'registrationAfter completes the observation exceptionally instead of waiting indefinitely', 'workerBefore observer failure never skips original worker or callbacks', 'workerBefore observer failure is retained as rejected evidence', 'workerBefore incomplete proof cannot pass', 'workerBefore completes the observation exceptionally instead of waiting indefinitely', 'workerAfter observer failure never skips original worker or callbacks', 'workerAfter observer failure is retained as rejected evidence', 'workerAfter incomplete proof cannot pass', 'workerAfter completes the observation exceptionally instead of waiting indefinitely']

def member(text, needle):
    start = text.index(needle)
    opened = text.index('{', start)
    depth = 0
    quote = None
    escape = line = block = False
    i = opened
    while i < len(text):
        c, pair = text[i], text[i:i+2]
        if line:
            if c == '\n': line = False
        elif block:
            if pair == '*/': block = False; i += 1
        elif quote:
            if escape: escape = False
            elif c == '\\': escape = True
            elif c == quote: quote = None
        elif pair == '//': line = True; i += 1
        elif pair == '/*': block = True; i += 1
        elif c in ('"', "'"): quote = c
        elif c == '{': depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0: return text[start:i+1]
        i += 1
    raise ValueError('Unclosed source member: ' + needle)

def run(java_home, json_jar, output):
    production = ROOT/'app/src/main/java/local/pocketchat/NativeNetwork.java'
    helper = ROOT/'tests/gecko/SourceRouteStartObservation.java'
    fixture = pathlib.Path(__file__).with_name('StartObservationTest.java')
    inputs = [production, helper, fixture, pathlib.Path(__file__).resolve(), ROOT/'app/src/main/java/local/pocketchat/J.java']
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    needles = ['interface Callback', 'enum RecoveryState', 'static final class RecoveryOutcome', 'interface RecoveryCallback', 'static final class RecoveryAdapter', 'void restart(Callback callback)', 'void recover(Callback callback)', 'void recoverOutcome(RecoveryCallback callback)', 'synchronized void startOperation(', 'void runStartOperation(']
    original = production.read_text()
    methods = [member(original, needle) for needle in needles]
    with tempfile.TemporaryDirectory(prefix='source-route-start-') as temp:
        work = pathlib.Path(temp)
        java = work/'local/pocketchat/StartObservationTest.java'
        java.parent.mkdir(parents=True)
        java.write_text(fixture.read_text().replace('/* ACTUAL_NATIVE_START_MEMBERS */', '\n'.join(methods)))
        clock = work/'android/os/SystemClock.java'
        clock.parent.mkdir(parents=True)
        clock.write_text('package android.os; public final class SystemClock { public static long elapsedRealtimeNanos(){return System.nanoTime();} }\n')
        subprocess.run([str(java_home/'bin/javac'), '-encoding', 'UTF-8', '-cp', str(json_jar), '-d', str(work), str(java), str(helper), str(inputs[-1]), str(clock)], check=True)
        output.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([str(java_home/'bin/java'), '-cp', str(work)+':'+str(json_jar), 'local.pocketchat.StartObservationTest', str(output)], check=True, timeout=30)
    report = json.loads(output.read_text())
    report.update(actualAndroidExecution=False, productionMembers=needles, sourceFiles=hashes, sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip(), jsonJarSha256=hashlib.sha256(json_jar.read_bytes()).hexdigest(), executionInputsUnchanged=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==sha for p,sha in hashes.items()), scope='Exact production NativeNetwork startOperation/runStartOperation/restart/recover plus actual fixture observer; controlled transport and main dispatcher, no Android acceptance')
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    assert report['status']=='passed' and report['total']==43 and len(report['checks'])==43 and [c['name'] for c in report['checks']]==EXPECTED_CHECK_NAMES and all(c['pass'] is True for c in report['checks']) and report['executionInputsUnchanged'] and report['syntheticControlledHost'] is True and report['actualAndroidExecution'] is False
    print(json.dumps({'status': report['status'], 'total':report['total'], 'executionInputsUnchanged':report['executionInputsUnchanged']}))
    return report

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--java-home', type=pathlib.Path, required=True)
    p.add_argument('--json-jar', type=pathlib.Path, required=True)
    p.add_argument('--output', type=pathlib.Path, required=True)
    a = p.parse_args()
    run(a.java_home.resolve(), a.json_jar.resolve(), a.output.resolve())
