#!/usr/bin/env python3
"""Run source-bound production observer JS in synthetic JSDOM, never Android or performance evidence."""
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
EXPECTED_TOTAL = 17


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*parts):
    return subprocess.check_output(['git', *parts], cwd=ROOT, text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jsdom-module', default=os.environ.get('JSDOM_MODULE'),
                        help='Existing JSDOM module path/name; no dependencies are downloaded')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    node = shutil.which('node')
    if not node:
        parser.error('An existing Node.js installation is required')
    test = ROOT / 'tests/resource-web-observer.cjs'
    inputs = [ROOT / 'app/src/main/assets/web-reply-observer.js',
              ROOT / 'app/src/main/assets/page-driver.js', test, Path(__file__).resolve()]
    hashes = {str(path.relative_to(ROOT)): digest(path) for path in inputs}
    source, tree = git('rev-parse', 'HEAD'), git('rev-parse', 'HEAD^{tree}')
    dirty = bool(git('status', '--porcelain', '--untracked-files=normal'))
    expected = re.findall(r"test\('([^'\n]+)'", test.read_text())
    if len(expected) != EXPECTED_TOTAL or len(set(expected)) != EXPECTED_TOTAL:
        raise ValueError('The exact seventeen unique literal observer checks are required')
    output = args.output or ROOT / 'work/resource-observer-host/results.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.unlink(missing_ok=True)
    environment = dict(os.environ)
    if args.jsdom_module:
        environment['JSDOM_MODULE'] = args.jsdom_module
    stdout, stderr, exit_code, error = '', '', None, ''
    try:
        run = subprocess.run([node, '--test', '--test-reporter=tap', str(test)], cwd=ROOT,
                             env=environment, text=True, capture_output=True, timeout=60)
        stdout, stderr, exit_code = run.stdout, run.stderr, run.returncode
    except subprocess.TimeoutExpired as failure:
        stdout = failure.stdout.decode() if isinstance(failure.stdout, bytes) else failure.stdout or ''
        stderr = failure.stderr.decode() if isinstance(failure.stderr, bytes) else failure.stderr or ''
        error = 'Synthetic DOM suite exceeded its bounded timeout'
    summary = {}
    for field in ('tests', 'pass', 'fail', 'cancelled', 'skipped', 'todo'):
        found = re.findall(r'^# ' + field + r' (\d+)$', stdout, re.M)
        summary[field] = int(found[0]) if len(found) == 1 else None
    declared = re.findall(r'^# Subtest: (.+)$', stdout, re.M)
    rows = re.findall(r'^(ok|not ok) (\d+) - (.+)$', stdout, re.M)
    checks = [{'name': name, 'pass': kind == 'ok', 'index': int(index)} for kind, index, name in rows]
    names = [row['name'] for row in checks]
    stable = (source == git('rev-parse', 'HEAD') and tree == git('rev-parse', 'HEAD^{tree}')
              and all((ROOT / path).is_file() and digest(ROOT / path) == value for path, value in hashes.items()))
    complete = (exit_code == 0 and not error and summary == {'tests': EXPECTED_TOTAL,
        'pass': EXPECTED_TOTAL, 'fail': 0, 'cancelled': 0, 'skipped': 0, 'todo': 0}
        and declared == expected and names == expected and len(set(names)) == EXPECTED_TOTAL
        and [row['index'] for row in checks] == list(range(1, EXPECTED_TOTAL + 1))
        and all(row['pass'] is True for row in checks) and stable)
    report = {'schema': 1, 'status': 'passed' if complete else 'failed',
        'passed': sum(row['pass'] is True for row in checks), 'total': EXPECTED_TOTAL,
        'executed': len(checks), 'failed': sum(row['pass'] is False for row in checks),
        'checks': checks, 'expectedCheckNames': expected, 'tapSummary': summary,
        'exitCode': exit_code, 'tap': stdout, 'stderr': stderr,
        'error': error if error else '' if complete else 'Exact source-bound synthetic DOM checklist failed or changed',
        'sourceCommit': source, 'sourceTree': tree, 'sourceDirty': dirty,
        'sourceUnchangedDuringChecks': stable, 'files': hashes,
        'jsdomModule': args.jsdom_module or 'jsdom', 'synthetic': True,
        'actualAndroidExecution': False, 'capacityAcceptance': False,
        'actualPerformanceMeasurement': False, 'realWebsiteExecution': False,
        'pageDriverExecuted': False,
        'scope': 'Production web-reply-observer.js in JSDOM with controlled timers and explicit gesture/API adapters; page-driver source binding only; no Android, real website, physical capacity or measured performance'}
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    if not complete:
        if stderr:
            print(stderr, file=sys.stderr)
        raise ValueError('Resource observer host verification failed; report preserved: ' + str(output))
    print(json.dumps({'status': 'passed', 'passed': report['passed'], 'total': EXPECTED_TOTAL,
        'actualAndroidExecution': False, 'synthetic': True, 'capacityAcceptance': False,
        'report': str(output)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
