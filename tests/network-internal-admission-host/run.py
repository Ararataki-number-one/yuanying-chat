#!/usr/bin/env python3
"""Execute current integration admission methods with explicit observer/looper doubles."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def member(text, anchor):
    start = text.index(anchor)
    brace = text.index('{', start)
    depth, cursor = 1, brace + 1
    while depth:
        depth += (text[cursor] == '{') - (text[cursor] == '}')
        cursor += 1
    return text[start:cursor]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--java-home', type=Path, required=True)
    parser.add_argument('--json-jar', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mutation', choices=['discard-fresh-guard'],
                        help='Negative control only; must fail the actual-method workload')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    fixture = root / 'tests/gecko/NetworkSettingsInternalApplication.java'
    provider = root / 'app/src/main/java/local/pocketchat/NetworkUiProvider.java'
    template = Path(__file__).with_name('InternalAdmissionHost.java.in')
    source = fixture.read_text()
    anchors = ['static boolean currentIdleGuard(', 'void observeAdmission(',
               'boolean applicationDone(', 'void idle()']
    methods = {anchor: member(source, anchor) for anchor in anchors}
    if args.mutation:
        clause = '&&guard.isDone()&&currentIdleGuard(a.session,guard.getNow(null))'
        assert methods['void idle()'].count(clause) == 1
        methods['void idle()'] = methods['void idle()'].replace(clause, '', 1)
    inputs = [fixture, provider, template, Path(__file__).resolve(),
              root / 'app/src/main/java/local/pocketchat/TaskGuardSnapshot.java',
              root / 'app/src/main/java/local/pocketchat/J.java']
    hashes = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in inputs}
    task_idle = member(provider.read_text(), 'static boolean taskIdle(')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='internal-admission-', dir=args.output.parent) as directory:
        work = Path(directory)
        generated = work / 'InternalAdmissionHost.java'
        generated.write_text(template.read_text().replace('@FIXTURE_METHODS@', '\n'.join(methods.values()))
                             .replace('@TASK_IDLE@', task_idle))
        classes = work / 'classes'
        classes.mkdir()
        subprocess.run([str(args.java_home / 'bin/javac'), '-J-XX:ActiveProcessorCount=2',
                        '-encoding', 'UTF-8', '-cp', str(args.json_jar), '-d', str(classes),
                        str(generated), *map(str, inputs[-2:])], check=True)
        result = subprocess.run([str(args.java_home / 'bin/java'), '-XX:ActiveProcessorCount=2',
                                 '-cp', str(classes) + ':' + str(args.json_jar),
                                 'local.pocketchat.InternalAdmissionHost'],
                                capture_output=True, text=True)
        if result.returncode:
            print(result.stderr[-4000:], file=sys.stderr)
            raise SystemExit(result.returncode)
        report = json.loads(result.stdout)
        assert report['status'] == 'passed' and report['checks']
        assert report['passed'] == len(report['checks'])
        assert all(row['pass'] is True for row in report['checks'])
    assert all(hashlib.sha256((root / name).read_bytes()).hexdigest() == value
               for name, value in hashes.items())
    report.update(files=hashes,
                  exactMethodsSha256={name: hashlib.sha256(value.encode()).hexdigest()
                                      for name, value in methods.items()},
                  taskIdleSha256=hashlib.sha256(task_idle.encode()).hexdigest(),
                  actualAndroidExecution=False, actualGeckoExecution=False,
                  actualCoreVerification=False,
                  scope='Actual current integration idle/admission methods, production taskIdle and '
                        'TaskGuardSnapshot. Observer callbacks, session, looper and executor are '
                        'explicit deterministic doubles; no native execution or device acceptance.')
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': report['status'], 'passed': report['passed'],
                      'output': str(args.output)}))


if __name__ == '__main__':
    main()
