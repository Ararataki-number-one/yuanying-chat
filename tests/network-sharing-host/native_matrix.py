#!/usr/bin/env python3
"""Production share export vs upstream Mihomo -t; never dials or proves fingerprints.

Each run snapshots current production Java, compiles a separate historical codec,
and records raw/typed-preservation assertions plus native parser acceptance.
All fixtures and logs are synthetic and written under the requested work output.
"""
import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
TESTS = pathlib.Path(__file__).resolve().parent
PRODUCTION = ROOT / 'app/src/main/java/local/pocketchat'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, **kwargs):
    return subprocess.run([str(x) for x in command], text=True, capture_output=True,
                          timeout=kwargs.pop('timeout', 90), **kwargs)


def compile_codec(args, mode, output):
    source = output / 'source' / mode
    source.mkdir(parents=True, exist_ok=True)
    names = ['J.java', 'NetworkShareCodec.java']
    if mode == 'current':
        for optional in ['NetworkShareSchema.java', 'NetworkShareSnapshot.java']:
            if (PRODUCTION / optional).exists():
                names.append(optional)
    for name in names:
        if mode == 'current':
            data = (PRODUCTION / name).read_bytes()
        else:
            data = subprocess.check_output(['git', 'show', f'{args.baseline}:app/src/main/java/local/pocketchat/{name}'], cwd=ROOT)
        (source / name).write_bytes(data)
    for name in ['NetworkCatalog.java', 'NetworkShareNativeMatrix.java']:
        shutil.copyfile(TESTS / name, source / name)
    classes = output / 'classes' / mode
    classes.mkdir(parents=True, exist_ok=True)
    classpath = f'{args.json_jar.resolve()}:{args.yaml_jar.resolve()}'
    javac = args.java_home / 'bin/javac' if args.java_home else shutil.which('javac')
    java = args.java_home / 'bin/java' if args.java_home else shutil.which('java')
    built = run([javac, '-encoding', 'UTF-8', '-cp', classpath, '-d', classes, *sorted(source.glob('*.java'))])
    (output / f'{mode}-compile.log').write_text(built.stdout + built.stderr)
    if built.returncode:
        raise RuntimeError(f'{mode} compile failed; inspect {mode}-compile.log')
    sample_dir = output / mode
    executed = run([java, '-cp', f'{classes}:{classpath}', 'local.pocketchat.NetworkShareNativeMatrix', sample_dir, mode])
    (output / f'{mode}-codec.log').write_text(executed.stdout + executed.stderr)
    if executed.returncode:
        raise RuntimeError(f'{mode} codec fixture failed; inspect {mode}-codec.log')
    report = json.loads((sample_dir / 'codec-results.json').read_text())
    report['sourceFiles'] = {p.name: sha(p) for p in source.glob('*.java')}
    return report


def native_test(binary, source, directory):
    directory.mkdir(parents=True, exist_ok=True)
    # Inline proxies exercise their real outbound decoder and constructor. No
    # provider refresh, health checker, listeners, or network requests are started.
    config = directory / 'config.yaml'
    config.write_bytes(source.read_bytes() + b'\nmode: direct\nlog-level: error\nallow-lan: false\nipv6: false\ndns: {enable: false}\nprofile: {store-selected: false, store-fake-ip: false}\nrules: ["MATCH,DIRECT"]\n')
    try:
        process = run([binary, '-t', '-d', directory, '-f', config], timeout=20)
        result = {'accepted': process.returncode == 0, 'exitCode': process.returncode, 'timeout': False}
        (directory / 'native.log').write_text(process.stdout + process.stderr)
    except subprocess.TimeoutExpired as error:
        result = {'accepted': False, 'exitCode': None, 'timeout': True}
        (directory / 'native.log').write_text(str(error))
    result['log'] = str(directory / 'native.log')
    result['configSha256'] = sha(config)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--json-jar', required=True, type=pathlib.Path)
    p.add_argument('--yaml-jar', required=True, type=pathlib.Path)
    p.add_argument('--native-core', required=True, type=pathlib.Path)
    p.add_argument('--java-home', type=pathlib.Path)
    p.add_argument('--baseline', default='e551c09')
    p.add_argument('--output-directory', type=pathlib.Path, default=ROOT / 'work/network-sharing-native-matrix')
    args = p.parse_args()
    output = args.output_directory.resolve()
    output.mkdir(parents=True, exist_ok=True)
    binary = args.native_core.resolve()
    version = run([binary, '-v'])
    current = compile_codec(args, 'current', output)
    baseline = compile_codec(args, 'baseline', output)
    original = {}
    rows = []
    baseline_by_case = {row['case']: row for row in baseline['cases']}
    for case in current['cases']:
        name = case['case']
        original[name] = native_test(binary, pathlib.Path(case['input']), output / 'native' / name / 'original')
        row = {'case': name, 'expectedShareAccepted': case['expectedShareAccepted'],
               'expectedNativeOriginalAccepted': case['expectedNativeOriginalAccepted'],
               'nativeOriginal': original[name], 'current': case, 'baseline': baseline_by_case[name]}
        for mode in ['current', 'baseline']:
            exported = row[mode].get('export')
            row[f'native{mode.capitalize()}Export'] = (native_test(binary, pathlib.Path(exported), output / 'native' / name / mode) if exported else None)
        current_export = row['nativeCurrentExport']
        native_expected = original[name]['accepted'] == case['expectedNativeOriginalAccepted'] and not original[name]['timeout']
        export_ok = (current_export is not None and current_export['accepted'] and not current_export['timeout']) if case['expectedShareAccepted'] else current_export is None
        row['pass'] = case['pass'] and native_expected and export_ok
        rows.append(row)
        print(f"{name}: original={'accept' if original[name]['accepted'] else 'reject'}, baseline={'export' if row['baseline']['accepted'] else 'reject'}, current={'export' if case['accepted'] else 'reject'}, {'PASS' if row['pass'] else 'FAIL'}", flush=True)
    passed = sum(row['pass'] for row in rows)
    report = {'schema': 1, 'status': 'passed' if passed == len(rows) else 'failed', 'passed': passed, 'total': len(rows),
              'sourceCommit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'baselineCommit': subprocess.check_output(['git', 'rev-parse', args.baseline], cwd=ROOT, text=True).strip(),
              'sourceFiles': current['sourceFiles'], 'baselineSourceFiles': baseline['sourceFiles'],
              'nativeCore': {'path': str(binary), 'sha256': sha(binary), 'version': version.stdout.strip(), 'patchedPocketBuild': False},
              'fixtures': {'javaSha256': sha(TESTS / 'NetworkShareNativeMatrix.java'), 'driverSha256': sha(pathlib.Path(__file__)), 'jsonJarSha256': sha(args.json_jar), 'yamlJarSha256': sha(args.yaml_jar)},
              'scope': 'Actual production Codec extract/provider/reparse, strict case-specific value assertions, and actual upstream Mihomo -t configuration acceptance. Native -t is parse/construction validation only.',
              'limitations': ['No patched Pocket configFingerprint comparison; acceptance cannot prove semantic equality.',
                              'No Android app/device or real proxy connection, throughput, latency, authentication or TLS handshake was exercised.',
                              'Current share intentionally rejects ambiguous aliases, ignored plugin aliases and nonportable references even when upstream parser accepts them.',
                              'Baseline output is compared with current expected behavior; its failures are retained as historical differences rather than current test failures.'],
              'pocketFingerprintVerified': False, 'realNetworkMeasured': False, 'actualAndroidExecution': False, 'cases': rows}
    (output / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(f'{passed}/{len(rows)} current cases passed; report: {output / "results.json"}')
    return 0 if passed == len(rows) else 1


if __name__ == '__main__':
    sys.exit(main())
