#!/usr/bin/env python3
"""Replay actual recovery/search/selection bodies against controlled boundaries.

The same fixed desired behaviors can replay a historical --source. This is JVM
fault injection, not Android, the native core, real routing or phone evidence.
"""
import argparse
import hashlib
import importlib.util
import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]


def production_harness(source):
    helper = ROOT / 'tools/gecko/run_network_core_host.py'
    spec = importlib.util.spec_from_file_location('production_block', helper)
    extract = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(extract)
    classes = ['  static final class ExitRouteReceipt ', '  static final class RouteProbe',
               '  static final class RouteTransactionFailure ', '  static final class RetainedRouteFailure ',
               '  static final class StartupRoute ', '  static final class StartupRouteFailure ']
    optional_classes = ['  static final class RecoveryRoute ']
    classes += [s for s in optional_classes if s in source]
    methods = ['  void recoverExistingRoute(', '  RetainedRouteFailure retained(',
               '  void firstVerifiedRoute(String rejected)',
               '  void firstVerifiedRoute(String rejected,StartupRoute bootstrap)',
               '  RouteProbe startupProbe(', '  long startupSearchBudgetMs(',
               '  void selectNow(', '  void commitSelection(', '  static long exitRetryDelayMs(',
               '  void selectVerifiedRoute(String name,boolean measure)',
               '  void selectVerifiedRoute(String name,boolean measure,StartupRoute bootstrap)',
               '  JSONObject startupState(', '  void stopFailedTransaction(',
               '  void stopOwnedCore(', '  void clearReadyState(']
    optional_methods = ['  private void recoverFirstVerifiedRoute(', '  JSONObject recoveryState(', '  static boolean ordinaryRecoveryFailure(',
                        '  RouteProbe startupProbe(String name,int index,String epoch,RecoveryRoute recovery)',
                        '  void firstVerifiedRoute(String rejected,StartupRoute bootstrap,RecoveryRoute recovery)',
                        '  void selectVerifiedRoute(String name,boolean measure,StartupRoute bootstrap,RecoveryRoute recovery)']
    methods += [s for s in optional_methods if s in source]
    template = ROOT / 'tests/network-recovery-host/RecoverySearchHarness.java.txt'
    harness = template.read_text().replace('// PRODUCTION_CLASSES', '\n'.join(extract.block(source, s) for s in classes))
    if '  static final class RecoveryRoute ' not in source:
        # Historical production never invokes the scoped probe-double overload;
        # its inert type only lets the unchanged legacy fixture compile.
        harness = harness.replace('  // PRODUCTION_METHODS', '  static final class RecoveryRoute {}\n  // PRODUCTION_METHODS')
    harness = harness.replace('// PRODUCTION_METHODS', '\n'.join(extract.block(source, s) for s in methods))
    return harness, classes, methods


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--java-home', required=True, type=pathlib.Path)
    parser.add_argument('--json-jar', required=True, type=pathlib.Path)
    parser.add_argument('--source', type=pathlib.Path)
    parser.add_argument('--scenario', choices=['ordinary', 'all'], default='all')
    parser.add_argument('--output', required=True, type=pathlib.Path)
    args = parser.parse_args()
    source_path = args.source or ROOT / 'app/src/main/java/local/pocketchat/NativeNetwork.java'
    source = source_path.read_text()
    harness, classes, methods = production_harness(source)
    template = ROOT / 'tests/network-recovery-host/RecoverySearchHarness.java.txt'
    helper = ROOT / 'tools/gecko/run_network_core_host.py'
    work = args.output.parent / (args.output.stem + '-host')
    work.mkdir(parents=True, exist_ok=True)
    java_file = work / 'NativeNetwork.java'
    java_file.write_text(harness)
    clock = work / 'SystemClock.java'
    clock.write_text('package android.os;public class SystemClock{public static long offset;public static long elapsedRealtime(){return System.nanoTime()/1000000+offset;}public static void advance(long delta){offset+=delta;}}')
    production = [ROOT / 'app/src/main/java/local/pocketchat' / name for name in ('NetworkHealthPolicy.java', 'NetworkWork.java', 'NetworkDiagnostics.java')]
    inputs = [*production, template, helper, pathlib.Path(__file__).resolve()]
    digests = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    compiler = subprocess.run([str(args.java_home / 'bin/javac'), '-encoding', 'UTF-8', '-cp', str(args.json_jar), '-d', str(work), str(java_file), str(clock), *map(str, production)], capture_output=True, text=True, timeout=60)
    (work / 'compile.stdout').write_text(compiler.stdout)
    (work / 'compile.stderr').write_text(compiler.stderr)
    if compiler.returncode:
        raise RuntimeError(compiler.stderr)
    run = subprocess.run([str(args.java_home / 'bin/java'), '-cp', str(work)+':'+str(args.json_jar), 'local.pocketchat.NativeNetwork', args.scenario], capture_output=True, text=True, timeout=30)
    (work / 'execution.stdout').write_text(run.stdout)
    (work / 'execution.stderr').write_text(run.stderr)
    result = json.loads(run.stdout)
    unchanged = source_path.read_text() == source and all(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == digest for p, digest in digests.items())
    result.update(sourceFile=str(source_path), sourceSha256=hashlib.sha256(source.encode()).hexdigest(),
                  sourceCommit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  sourceDirty=bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True)),
                  files=digests, sourceInputsUnchanged=unchanged,
                  jsonJarSha256=hashlib.sha256(args.json_jar.read_bytes()).hexdigest(),
                  extractedClasses=classes, extractedMethods=methods,
                  harnessSha256=hashlib.sha256(harness.encode()).hexdigest(),
                  legacyRecoveryProbeTypeAdapter='  static final class RecoveryRoute ' not in source,
                  scope='Verbatim production recovery/search/selection with deterministic controller/HTTPS/process boundaries and real NetworkWork/executors. Candidate measurement is a completion-time binding double; this suite cannot prove production probe lifetime/serial correctness. run_real_probes.py covers the actual producer. No Android, Mihomo, real routing, browser or phone acceptance.',
                  stderr=run.stderr)
    if not unchanged:
        result['status'] = 'failed'
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'status': result['status'], 'passed': result['passed'], 'total': result['total'], 'output': str(args.output)}))
    raise SystemExit(run.returncode or (0 if unchanged else 1))


if __name__ == '__main__':
    main()
