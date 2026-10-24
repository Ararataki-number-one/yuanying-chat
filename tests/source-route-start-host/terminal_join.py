#!/usr/bin/env python3
"""Complete source-bound terminal observer with actual original start scheduling."""
import argparse
import hashlib
import importlib.util
import json
import pathlib
import subprocess
import tempfile
from run import ROOT, member

EXPECTED_CHECK_NAMES = ['Complete observer waits for actual workerAfter after both original callbacks', 'Complete observer accepts exact joined restart with one fresh read and unchanged raw serials', 'Worker completion stays inside the original fetch budget and precedes the sole fresh read', 'Complete observer rejects a joined restart with wrong source', 'Complete observer rejects a joined restart with wrong nonce', 'Complete observer rejects a joined restart with wrong case', 'Original deadline rejects unfinished worker observation without fresh IPC or cancellation', 'Complete observer rejects real queued-worker ABA despite retained root waiter and closed core']
BEFORE_CHECK_NAMES = ['Original observer rejects the same actual joined restart before the fixture fix']

NEEDLES = ['interface Callback', 'enum RecoveryState', 'static final class RecoveryOutcome', 'interface RecoveryCallback', 'static final class RecoveryAdapter', 'void restart(Callback callback)', 'void recover(Callback callback)', 'void recoverOutcome(RecoveryCallback callback)', 'synchronized void startOperation(', 'void runStartOperation(']

def run(java_home, json_jar, output, before_observer_ref=None):
    production=ROOT/'app/src/main/java/local/pocketchat/NativeNetwork.java'
    observer=ROOT/'tests/gecko/SourceRouteTerminalObserver.java'
    helper=ROOT/'tests/gecko/SourceRouteStartObservation.java'
    fixture=pathlib.Path(__file__).with_name('TerminalJoinTest.java')
    base=fixture.with_name('StartObservationTest.java')
    contract=ROOT/'tools/gecko/network_sources_contract.py'
    inputs=[production,observer,helper,fixture,base,pathlib.Path(__file__).resolve(),fixture.with_name('run.py'),contract,ROOT/'app/src/main/java/local/pocketchat/J.java']
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    source=observer.read_text() if before_observer_ref is None else subprocess.check_output(['git','show',before_observer_ref+':tests/gecko/SourceRouteTerminalObserver.java'],cwd=ROOT,text=True)
    adapter=base.read_text().split('\nclass NativeNetwork {',1)[1]
    adapter='class NativeNetwork {'+adapter
    adapter=adapter.replace('/* ACTUAL_NATIVE_START_MEMBERS */','\n'.join(member(production.read_text(),needle) for needle in NEEDLES))
    adapter=adapter.replace('final ExecutorService worker=', 'final SourceRouteStartObservation startObservation=new SourceRouteStartObservation();final NetworkTransportClient transport=new NetworkTransportClient();long routeSerial;\n  final ExecutorService worker=')
    adapter=adapter.replace('boolean coreAlive(){return false;}', 'boolean coreAlive(){return transport.state.optBoolean("alive");}')
    adapter=adapter.replace('generation=String.format("00000000-0000-4000-8000-%012d",index);', 'generation=TerminalJoinTest.generation(true,index);')
    with tempfile.TemporaryDirectory(prefix='source-route-terminal-join-') as temp:
        work=pathlib.Path(temp)
        java=work/'local/pocketchat/TerminalJoinTest.java';java.parent.mkdir(parents=True)
        java.write_text(fixture.read_text().replace('/* BASE_NATIVE_ADAPTER */',adapter))
        actual_observer=java.with_name('SourceRouteTerminalObserver.java');actual_observer.write_text(source)
        clock=work/'android/os/SystemClock.java';clock.parent.mkdir(parents=True);clock.write_text('package android.os; public final class SystemClock { public static long elapsedRealtimeNanos(){return System.nanoTime();} }\n')
        subprocess.run([str(java_home/'bin/javac'),'-encoding','UTF-8','-cp',str(json_jar),'-d',str(work),str(java),str(actual_observer),str(helper),str(inputs[-1]),str(clock)],check=True)
        output.parent.mkdir(parents=True,exist_ok=True)
        subprocess.run([str(java_home/'bin/java'),'-cp',str(work)+':'+str(json_jar),'local.pocketchat.TerminalJoinTest',str(output), 'before' if before_observer_ref else 'current'],check=True,timeout=30)
    report=json.loads(output.read_text())
    report.update(publicJoinReplay=False,publicJoinContract=str(contract.relative_to(ROOT)))
    if before_observer_ref is None:
        joined=[case for case in report['cases'] if case['name']=='current-complete-observer-joined']
        assert len(joined)==1
        evidence=joined[0]['negative']['terminalEvidence']
        assert evidence['status']=='passed' and len(evidence['stopObservations'])==1 and len(evidence['recoveries'])==1
        spec=importlib.util.spec_from_file_location('source_route_join_public_contract',contract)
        verifier=importlib.util.module_from_spec(spec);spec.loader.exec_module(verifier)
        verifier._verify_source_route_join(evidence,evidence['stopObservations'][0],evidence['recoveries'][0],evidence['sourceCommit'],evidence['runNonce'])
        report['publicJoinReplay']=True
    report.update(sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),sourceFiles=hashes,observerSourceRef=before_observer_ref or 'working-tree',observerSourceSha256=hashlib.sha256(source.encode()).hexdigest(),productionMembers=NEEDLES,jsonJarSha256=hashlib.sha256(json_jar.read_bytes()).hexdigest(),executionInputsUnchanged=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==sha for p,sha in hashes.items()),scope='Complete actual fixture terminal observer plus actual production startOperation/runStartOperation; controlled host main dispatcher and transport, no Android or process-exit acceptance')
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    expected = BEFORE_CHECK_NAMES if before_observer_ref else EXPECTED_CHECK_NAMES
    assert report['status']==('baseline-rejected' if before_observer_ref else 'passed') and report['total']==len(expected) and len(report['checks'])==len(expected) and [c['name'] for c in report['checks']]==expected and all(c['pass'] is True for c in report['checks']) and report['executionInputsUnchanged'] and report['syntheticControlledHost'] is True and report['actualAndroidExecution'] is False and report['publicJoinReplay'] is (before_observer_ref is None)
    print(json.dumps({'status':report['status'],'total':report['total'],'executionInputsUnchanged':report['executionInputsUnchanged']}))
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--java-home',type=pathlib.Path,required=True);p.add_argument('--json-jar',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--before-observer-ref');a=p.parse_args();run(a.java_home.resolve(),a.json_jar.resolve(),a.output.resolve(),a.before_observer_ref)
