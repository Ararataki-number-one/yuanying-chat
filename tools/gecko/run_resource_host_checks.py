#!/usr/bin/env python3
"""Execute actual production resource-pressure code with explicit JVM Android doubles."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*arguments):
    return subprocess.check_output(['git', *arguments], cwd=ROOT, text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json-jar', required=True, type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--java-home', type=Path)
    args = parser.parse_args()
    jar = args.json_jar.resolve()
    if not jar.is_file():
        parser.error('--json-jar must name an existing JSON-java jar')
    java = str(args.java_home / 'bin/java') if args.java_home else os.environ.get('PROFILE_JAVA') or shutil.which('java')
    if not java:
        parser.error('Java 17 with jdk.compiler is required')
    work = ROOT / 'work/resource-pressure-host'
    classes = work / 'classes'
    if classes.exists():
        shutil.rmtree(classes)
    classes.mkdir(parents=True, exist_ok=True)
    output = args.output or work / 'results.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.unlink(missing_ok=True)
    production = ROOT / 'app/src/main/java/local/pocketchat/ResourcePressureController.java'
    fixtures = sorted((ROOT / 'tests/resource-pressure-host').rglob('*.java'))
    test = ROOT / 'tests/resource-pressure-host/local/pocketchat/ResourcePressureHostTest.java'
    inputs = [production, *fixtures, Path(__file__).resolve()]
    hashes = {str(path.relative_to(ROOT)): digest(path) for path in inputs}
    source, tree, dirty = git('rev-parse', 'HEAD'), git('rev-parse', 'HEAD^{tree}'), bool(git('status', '--porcelain', '--untracked-files=normal'))
    expected_names = re.findall(r'check\("([^"\n]+)"', test.read_text())
    if not expected_names or len(set(expected_names)) != len(expected_names):
        raise ValueError('The source must declare a nonempty unique literal checklist')
    command = [java, '-XX:ActiveProcessorCount=2', '-m', 'jdk.compiler/com.sun.tools.javac.Main',
               '-encoding', 'UTF-8', '-classpath', str(jar), '-d', str(classes),
               *map(str, [production, *fixtures])]
    subprocess.run(command, cwd=ROOT, check=True, timeout=60)
    run = subprocess.run([java, '-XX:ActiveProcessorCount=2', '-cp', str(classes) + os.pathsep + str(jar),
                          'local.pocketchat.ResourcePressureHostTest'], cwd=ROOT, text=True,
                         capture_output=True, timeout=60)
    try:
        report = json.loads(run.stdout)
    except (ValueError, TypeError):
        output.write_text(json.dumps({'schema': 1, 'status': 'failed', 'actualAndroidExecution': False,
            'synthetic': True, 'capacityAcceptance': False, 'passed': 0, 'total': len(expected_names),
            'executed': 0, 'checks': [], 'error': 'JVM produced no valid report',
            'stdout': run.stdout, 'stderr': run.stderr, 'sourceCommit': source, 'sourceTree': tree,
            'sourceDirty': dirty, 'files': hashes}, indent=2) + '\n')
        raise
    report.update(sourceCommit=source, sourceTree=tree, sourceDirty=dirty, files=hashes,
                  jsonJarSha256=digest(jar), expectedCheckNames=expected_names)
    stable = source == git('rev-parse', 'HEAD') and tree == git('rev-parse', 'HEAD^{tree}') and all(
        (ROOT / path).is_file() and digest(ROOT / path) == value for path, value in hashes.items())
    report['sourceUnchangedDuringChecks'] = stable
    checks = report.get('checks', [])
    complete = (run.returncode == 0 and report.get('status') == 'passed'
        and report.get('actualAndroidExecution') is False and report.get('synthetic') is True
        and report.get('capacityAcceptance') is False and report.get('actualPlatformMemoryObservation') is False
        and type(report.get('passed')) is int and report['passed'] == len(expected_names)
        and report.get('total') == len(expected_names) and report.get('executed') == len(expected_names)
        and isinstance(checks, list) and [row.get('name') for row in checks] == expected_names
        and all(row.get('pass') is True for row in checks) and not report.get('error') and stable)
    if not complete:
        report['status'] = 'failed'
        report['runnerError'] = 'Exact source-bound resource host checklist failed or changed'
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    if not complete:
        if run.stderr:
            print(run.stderr, file=sys.stderr)
        raise ValueError('Resource pressure host verification failed; report preserved: ' + str(output))
    print(json.dumps({'status': 'passed', 'passed': report['passed'], 'total': report['total'],
        'actualAndroidExecution': False, 'synthetic': True, 'capacityAcceptance': False,
        'report': str(output)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
