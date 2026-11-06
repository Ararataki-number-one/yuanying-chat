#!/usr/bin/env python3
"""Actual resource retry/timeout/fixture continuation; explicit asynchronous startup doubles."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def member(source, anchor):
    start = source.index(anchor); cursor = source.index('{', start)+1; depth = 1
    while depth:
        depth += (source[cursor] == '{')-(source[cursor] == '}'); cursor += 1
    return source[start:cursor]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--java-home', type=Path, required=True)
    parser.add_argument('--json-jar', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mutation', choices=['sync-runtime-only', 'pretend-allocation-ready'])
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]; prod = root/'app/src/main/java/local/pocketchat'
    view = prod/'GeckoWebView.java'; session = prod/'ChatSession.java'
    activity = root/'tests/gecko/ResourcePressureIntegrationActivity.java'
    parent = root/'tests/gecko/GeckoIdentityPrototypeIntegrationActivity.java'
    template = Path(__file__).with_name('ResourceRecoveryHost.java.in')
    methods = {'retry': member(view.read_text(), 'boolean retryResourceStart()'),
               'navigation': member(session.read_text(), 'void beginNavigation('),
               'timeout': member(session.read_text(), 'void navigationTimeout('),
               'cold': member(activity.read_text(), 'void coldAllocation()'),
               'allocated': member(activity.read_text(), 'void awaitRecoveryAllocation('),
               'ready': member(activity.read_text(), '  @Override void beginCase()')}
    startup = 'handler.postDelayed(()->{if(!finished&&caseIndex<0)finish(new IOException("Official Gecko startup did not become ready"));},60000);'
    assert parent.read_text().count(startup) == 1
    code = template.read_text()
    for key, body in methods.items():
        code = code.replace('@'+key.upper()+'@', body)
    code = code.replace('@STARTUP@', startup)
    if args.mutation == 'sync-runtime-only':
        needle = 'initialize();if(!resourceDeferred&&!failed){'
        assert code.count(needle) == 1
        code = code.replace(needle, 'initialize();if(!resourceDeferred&&!failed&&runtime!=null){', 1)
    if args.mutation == 'pretend-allocation-ready':
        needle = 'if(view.runtime==null){handler.postDelayed(()->awaitRecoveryAllocation(oldEpoch),20);return;}'
        assert code.count(needle) == 1
        code = code.replace(needle, 'if(false){handler.postDelayed(()->awaitRecoveryAllocation(oldEpoch),20);return;}', 1)
    boundaries = sorted((root/'tests/resource-pressure-host/android').rglob('*.java'))
    inputs = [view, session, activity, parent, prod/'ResourcePressureController.java', prod/'J.java',
              template, Path(__file__).resolve(), *boundaries]
    hashes = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='resource-recovery-', dir=args.output.parent) as temporary:
        work = Path(temporary); generated = work/'ResourceRecoveryHost.java'; generated.write_text(code)
        classes = work/'classes'; classes.mkdir()
        subprocess.run([str(args.java_home/'bin/javac'), '-J-XX:ActiveProcessorCount=2', '-encoding', 'UTF-8',
                        '-cp', str(args.json_jar), '-d', str(classes), str(generated),
                        str(prod/'ResourcePressureController.java'), str(prod/'J.java'), *map(str, boundaries)], check=True)
        result = subprocess.run([str(args.java_home/'bin/java'), '-XX:ActiveProcessorCount=2',
                                 '-cp', str(classes)+':'+str(args.json_jar), 'local.pocketchat.ResourceRecoveryHost'],
                                capture_output=True, text=True)
        if result.returncode:
            print(result.stderr[-5000:], file=sys.stderr); raise SystemExit(result.returncode)
        report = json.loads(result.stdout)
    assert report['status'] == 'passed' and report['passed'] == len(report['checks'])
    assert all(row['pass'] is True for row in report['checks'])
    assert all(hashlib.sha256((root/name).read_bytes()).hexdigest() == value for name, value in hashes.items())
    report.update(sourceCommit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
                  sourceDirty=bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=root)),
                  files=hashes, actualMethodsSha256={key:hashlib.sha256(value.encode()).hexdigest() for key,value in methods.items()},
                  startupDeadlineStatementSha256=hashlib.sha256(startup.encode()).hexdigest(),
                  actualAndroidExecution=False, actualGeckoExecution=False, actualNativeStartup=False,
                  scope='Current production resource retry, beginNavigation, navigationTimeout and ResourcePressureController; '
                        'current coldAllocation/awaitRecoveryAllocation/beginCase and original60s startup guard. '
                        'Explicit session, Gecko-runtime creation and asynchronous CPU/TLS/looper doubles; no real native execution or capacity claim.')
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(dict(status=report['status'], passed=report['passed'], output=str(args.output))))


if __name__ == '__main__':
    main()
