#!/usr/bin/env python3
"""Actual production probe producer and low-level interpretation at controller API boundary.

Unlike the legacy 32 transaction cases, binding is captured before the API work.
C begins before B selection and returns a positive delay during B verification.
This is bounded JVM fault injection, not native/Android/real-network evidence.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--java-home',required=True,type=Path)
    parser.add_argument('--json-jar',required=True,type=Path)
    parser.add_argument('--source',type=Path)
    parser.add_argument('--scenario',choices=['ordinary','all'],default='all')
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    helper=ROOT/'tools/gecko/run_network_core_host.py'
    suite_path=ROOT/'tests/network-recovery-host/run.py'
    extract=module('probe_production_extract',helper)
    suite=module('recovery_production_extract',suite_path)
    source_path=args.source or ROOT/'app/src/main/java/local/pocketchat/NativeNetwork.java'
    source=source_path.read_text()
    harness,classes,methods=suite.production_harness(source)
    # Remove only explicit legacy measurement doubles; keep the same production
    # search, selection, verify boundaries, scopes and owned-core cleanup.
    for signature in ['  static class Binding ', '  static class ProbeResult ',
                      '  ProbeResult probeMeasured(String proxy,String entry)',
                      '  ProbeResult probeMeasured(String proxy,String entry,RecoveryRoute recovery)',
                      '  boolean probeCurrent(', '  void recordProbe(', '  public static void main(']:
        harness=harness.replace(extract.block(harness,signature),'')
    probe_classes=['  static final class ProbeTicket ', '  static final class ProbeResult ']
    probe_methods=['  ProbeResult probeMeasured(String proxy,String exactEntry)',
                   '  boolean probeCurrent(', '  static LatencyProbePolicy.Trace probeTrace(',
                   '  int probe(', '  String probeUrl(']
    probe_methods += [s for s in ['  ProbeResult probeMeasured(String proxy,String exactEntry,RecoveryRoute recovery)',
                                '  boolean probeBindingCurrent(', '  boolean probeCallCurrent('] if s in source]
    body='\n'.join(extract.block(source,s) for s in probe_classes+probe_methods)
    boundary=ROOT/'tests/network-recovery-host/ProbeProducerBoundary.java.txt'
    harness=harness.replace('  JSONObject api(', '  JSONObject selectionApi(',1)
    harness=harness.replace('// PRODUCTION_PROBE_BOUNDARY', '')
    harness=harness.replace('  // This legacy transaction suite substitutes probes and captures bindings at\n  // completion. It cannot establish real producer lifetime/serial correctness.\n  // run_real_probes.py separately executes the actual producer and low-level probe.\n','')
    harness=harness.replace('  static class ExitMismatch ',body+'\n'+boundary.read_text()+'\n  static class ExitMismatch ',1)
    harness=harness.replace('import java.io.*;', 'import java.io.*;\nimport java.net.*;\nimport java.time.Instant;')
    verbatim_blocks={s:hashlib.sha256(extract.block(source,s).encode()).hexdigest() for s in probe_classes+probe_methods}
    if any(harness.count(extract.block(source,s))!=1 for s in probe_classes+probe_methods):
        raise ValueError('A complete production probe block was removed, duplicated or rewritten')
    work=args.output.parent/(args.output.stem+'-host');work.mkdir(parents=True,exist_ok=True)
    java_file=work/'NativeNetwork.java';java_file.write_text(harness)
    clock=work/'SystemClock.java';clock.write_text('package android.os;public class SystemClock{public static volatile long offset;public static long elapsedRealtime(){return System.nanoTime()/1000000+offset;}public static void advance(long delta){offset+=delta;}}')
    production=[ROOT/'app/src/main/java/local/pocketchat'/name for name in ('NetworkHealthPolicy.java','NetworkWork.java','NetworkDiagnostics.java','LatencyProbePolicy.java')]
    inputs=[*production,helper,suite_path,ROOT/'tests/network-recovery-host/RecoverySearchHarness.java.txt',boundary,Path(__file__).resolve()]
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    compile_run=subprocess.run([str(args.java_home/'bin/javac'),'-encoding','UTF-8','-cp',str(args.json_jar),'-d',str(work),str(java_file),str(clock),*map(str,production)],capture_output=True,text=True,timeout=60)
    (work/'compile.stdout').write_text(compile_run.stdout);(work/'compile.stderr').write_text(compile_run.stderr)
    if compile_run.returncode:raise RuntimeError(compile_run.stderr)
    run=subprocess.run([str(args.java_home/'bin/java'),'-cp',str(work)+':'+str(args.json_jar),'local.pocketchat.NativeNetwork',args.scenario],capture_output=True,text=True,timeout=30)
    (work/'execution.stdout').write_text(run.stdout);(work/'execution.stderr').write_text(run.stderr)
    value=json.loads(run.stdout)
    unchanged=source_path.read_text()==source and all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==digest for p,digest in hashes.items())
    value.update(sourceFile=str(source_path),sourceSha256=hashlib.sha256(source.encode()).hexdigest(),
        sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        sourceDirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)),files=hashes,
        sourceInputsUnchanged=unchanged,jsonJarSha256=hashlib.sha256(args.json_jar.read_bytes()).hexdigest(),
        extractedClasses=classes+probe_classes,extractedMethods=methods+probe_methods,harnessSha256=hashlib.sha256(harness.encode()).hexdigest(),
        completeVerbatimProbeBlocks=verbatim_blocks,producerBindingCapturedAt='Production probeMeasured before probe() begins',
        controlledProbeBoundary='Controller delay GET and exact-proxy history GET only. Ordinary case captures C ticket before B selection and returns controller delay positive20 during B verification; a separate case returns during unconfirmed B selection. No production binding/guard/result conversion substituted.',
        otherControlledBoundaries='Exit-verification success/failure and receipt boundary, service snapshot/process lifetime, Android clock. Actual exit HTTPS is not executed.',
        actualProbeProducerExecution=True,actualLowLevelProbeExecution=True,actualExitHttpsExecution=False,
        scope='JVM fault injection with actual complete LatencyProbePolicy, probe producer/low-level interpretation, recovery/search/selection and NetworkWork. No Android, native routing, browser, phone or real-network acceptance.',stderr=run.stderr)
    if not unchanged:value['status']='failed'
    args.output.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'status':value['status'],'passed':value['passed'],'total':value['total'],'output':str(args.output)}))
    raise SystemExit(run.returncode or (0 if unchanged else 1))


if __name__=='__main__':main()
