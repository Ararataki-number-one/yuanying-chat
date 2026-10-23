#!/usr/bin/env python3
"""Run production upload bookkeeping and JS with explicit host-only adapters."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def method(source, signature):
    start = source.index(signature)
    opening = source.index('{', start)
    depth, quote, i = 1, None, opening + 1
    while i < len(source):
        value = source[i]
        if quote:
            if value == '\\':
                i += 2
                continue
            if value == quote:
                quote = None
        elif value in ('"', "'"):
            quote = value
        elif source.startswith('//', i):
            i = source.index('\n', i)
        elif source.startswith('/*', i):
            i = source.index('*/', i) + 1
        elif value == '{':
            depth += 1
        elif value == '}':
            depth -= 1
            if depth == 0:
                return source[start:i + 1]
        i += 1
    raise ValueError('Incomplete production method: ' + signature)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--java', default=shutil.which('java'))
    parser.add_argument('--javac', default=shutil.which('javac'))
    parser.add_argument('--json-jar', required=True, type=Path)
    parser.add_argument('--jsdom-module', required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'work/upload-state-host')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    production = ROOT / 'app/src/main/java/local/pocketchat'
    template = ROOT / 'tests/resource-upload-host/FileWorkConsumersHostTest.java.in'
    bindings = {
        '__UPLOADING__': ('ChatSession.java', 'boolean uploading()'),
        '__FILE_WORK_ACTIVE__': ('ChatSession.java', 'boolean fileWorkActive()'),
        '__RESOURCE_FILES_ACTIVE__': ('ChatSession.java', 'boolean resourceFilesActive()'),
        '__BACKGROUND_BUSY__': ('NetworkRegion.java', 'static boolean backgroundBusy('),
        '__WORKING__': ('ProfileUi.java', 'static boolean working('),
        '__FENCE_IDLE__': ('NetworkUiProvider.java', 'boolean fenceIdle('),
    }
    rendered = template.read_text()
    for token, (name, signature) in bindings.items():
        rendered = rendered.replace(token, method((production / name).read_text(), signature))
    generated = output / 'FileWorkConsumersHostTest.java'
    generated.write_text(rendered)
    state_test = ROOT / 'tests/resource-upload-host/local/pocketchat/ResourceUploadHostTest.java'
    js_test = ROOT / 'tests/browser-runtime/attachment-lifecycle.test.cjs'
    files = [production / name for name in ('J.java', 'ResourceUploadState.java', 'GeckoWebView.java')]
    files += [production / name for name, _ in bindings.values()]
    files += [ROOT / 'app/src/main/assets' / name for name in ('attachment-driver.js', 'web-reply-observer.js')]
    files += [template, state_test, js_test, Path(__file__).resolve()]
    hashes = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    git = lambda *values: subprocess.check_output(['git', *values], cwd=ROOT, text=True).strip()
    report = dict(schema=1, sourceCommit=git('rev-parse', 'HEAD'), sourceDirty=bool(git('status', '--porcelain')), files=hashes,
                  actualAndroidExecution=False, realWebsiteExecution=False, actualPerformanceMeasurement=False,
                  scope='Production ResourceUploadState/J and extracted production gate methods on a JVM; production JS in JSDOM with explicit timer, geometry and trusted-event adapters. No Android, real upload or physical gesture acceptance.', checks=[])
    env = dict(os.environ, JSDOM_MODULE=args.jsdom_module)
    classes = output / 'classes'
    classes.mkdir(exist_ok=True)

    def run(name, command):
        result = subprocess.run([str(value) for value in command], cwd=ROOT, env=env, text=True, capture_output=True, timeout=60)
        (output / (name + '.stdout.txt')).write_text(result.stdout)
        (output / (name + '.stderr.txt')).write_text(result.stderr)
        if result.returncode:
            raise ValueError(name + ' failed; raw output preserved')
        return result.stdout

    try:
        run('compile', [args.javac, '-cp', args.json_jar, '-d', classes, production / 'J.java', production / 'ResourceUploadState.java', state_test, generated])
        for suite, main_class, expected in [('state', 'ResourceUploadHostTest', 20), ('consumers', 'FileWorkConsumersHostTest', 9)]:
            raw = run(suite, [args.java, '-cp', str(classes) + os.pathsep + str(args.json_jar), 'local.pocketchat.' + main_class])
            names = re.findall(r'^PASS (.+)$', raw, re.M)
            if len(names) != expected or len(set(names)) != expected or re.findall(r'^TOTAL (\d+)$', raw, re.M) != [str(expected)]:
                raise ValueError('Incomplete exact JVM checks: ' + suite)
            report['checks'] += [dict(suite=suite, name=name, passed=True) for name in names]
        # A single explicit file invokes node:test directly, avoiding nested test
        # worker IPC differences between host Node versions. Exact TAP is checked.
        raw = run('browser', ['node', '--test-reporter=tap', js_test])
        expected = re.findall(r"^test\('([^'\n]+)'", js_test.read_text(), re.M)
        observed = re.findall(r'^ok \d+ - (.+)$', raw, re.M)
        if observed != expected or len(expected) != 12 or re.findall(r'^# (tests|pass|fail|cancelled|skipped|todo) (\d+)$', raw, re.M) != [('tests', '12'), ('pass', '12'), ('fail', '0'), ('cancelled', '0'), ('skipped', '0'), ('todo', '0')]:
            raise ValueError('Incomplete exact browser checks')
        report['checks'] += [dict(suite='browser', name=name, passed=True) for name in observed]
        report['sourceUnchangedDuringChecks'] = all(hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == value for path, value in hashes.items())
        if not report['sourceUnchangedDuringChecks']:
            raise ValueError('Relevant sources changed during checks')
        report['status'] = 'passed'
    except Exception as error:
        report['status'] = 'failed'
        report['error'] = str(error)
        raise
    finally:
        report['passed'] = len(report['checks'])
        (output / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(status=report['status'], passed=report['passed'], actualAndroidExecution=False, report=str(output / 'results.json'))))


if __name__ == '__main__':
    main()
