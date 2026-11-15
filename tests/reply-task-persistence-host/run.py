#!/usr/bin/env python3
"""Run current task persistence with file-backed host storage and reentrant fault injection."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PROD = ROOT / 'app/src/main/java/local/pocketchat'
EXTRACTOR = ROOT / 'tests/review-host/run_deferred_browser_host.py'
sys.path.insert(0, str(EXTRACTOR.parent))
from run_deferred_browser_host import production_member


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json-jar', type=Path, required=True)
    parser.add_argument('--java-home', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    java = lambda name: str(args.java_home / 'bin' / name) if args.java_home else name
    selected = ['void delivery(', 'void completeReply(', 'void abandonWait(']
    chat = PROD / 'ChatSession.java'
    members = {name: production_member(chat.read_text(), name) for name in selected}
    fixture = ROOT / 'tests/gecko/GeckoIntegrationTestActivity.java'
    fixture_setup = production_member(fixture.read_text(), 'JSONObject beginSyntheticReply(')
    template = HERE / 'ReplyTaskPersistenceHost.java.in'
    sources = [PROD / name for name in ('DeliveryStore.java', 'WebReplyObserver.java', 'J.java')]
    coordinator = PROD / 'ReplyTaskPersistence.java'
    if coordinator.exists():
        sources.append(coordinator)
    sources += sorted((HERE / 'stubs').rglob('*.java'))
    sources += [ROOT / 'tests/local-draft-policy-host/stubs/android/net/Uri.java']
    inputs = sources + [chat, fixture, template, EXTRACTOR, Path(__file__).resolve(), args.json_jar]
    hashes = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.unlink(missing_ok=True)
    raw_output = args.output.with_suffix('.jvm.json')
    raw_output.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix='reply-task-persistence-') as directory:
        workspace = Path(directory)
        host = workspace / 'ReplyTaskPersistenceHost.java'
        host.write_text(template.read_text().replace('/* CHAT_MEMBERS */', '\n'.join(members.values()))
                       .replace('/* FIXTURE_SETUP */', fixture_setup))
        classes = workspace / 'classes'
        classes.mkdir()
        compiled = subprocess.run([java('javac'), '-encoding', 'UTF-8', '-cp', str(args.json_jar),
                                   '-d', str(classes), *map(str, sources), str(host)],
                                  capture_output=True, text=True, timeout=60)
        args.output.with_suffix('.compile.json').write_text(json.dumps(
            dict(exitCode=compiled.returncode, stdout=compiled.stdout, stderr=compiled.stderr),
            ensure_ascii=False, indent=2) + '\n')
        if compiled.returncode:
            print(compiled.stderr, file=sys.stderr)
            raise SystemExit(compiled.returncode)
        result = subprocess.run([java('java'), '-cp', str(classes) + ':' + str(args.json_jar),
                                 'local.pocketchat.ReplyTaskPersistenceHost', str(workspace / 'storage')],
                                capture_output=True, text=True, timeout=30)
        raw_output.write_text(json.dumps(dict(exitCode=result.returncode, stdout=result.stdout,
                                             stderr=result.stderr), ensure_ascii=False, indent=2) + '\n')
    if not result.stdout:
        raise RuntimeError('No task persistence result; original JVM output: ' + str(raw_output))
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError('Invalid task persistence JSON; original JVM output: ' + str(raw_output)) from error
    report['sourceFiles'] = {str(path.relative_to(ROOT)): hashes[str(path)] for path in inputs if path.is_relative_to(ROOT)}
    report['productionMembersSha256'] = {name: hashlib.sha256(value.encode()).hexdigest() for name, value in members.items()}
    report['fixtureSetupSha256'] = hashlib.sha256(fixture_setup.encode()).hexdigest()
    report['jsonJarSha256'] = hashes[str(args.json_jar)]
    report['executionInputsUnchanged'] = all(hashlib.sha256(path.read_bytes()).hexdigest() == hashes[str(path)] for path in inputs)
    report['sourceCommit'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    report['scope'] = (
        'Whole current DeliveryStore, WebReplyObserver and (when present) stateless ReplyTaskPersistence; '
        'verbatim ChatSession delivery/completeReply/abandonWait and integration beginSyntheticReply setup. '
        'Explicit file-backed delivery-row model with strict SQL shapes, separate preference memory/disk, '
        'commit failures after memory publication, synchronous preference/service reentrancy and fresh-context recovery. '
        'No actual Android SQLite/WAL, notification ledger, service lifecycle, Gecko or website execution; '
        'notification calls are boundary observations, not an exactly-once claim.')
    if not report['executionInputsUnchanged']:
        raise AssertionError('Production or test inputs changed during execution')
    if report['passed'] != sum(check['pass'] for check in report['checks']) or report['total'] != len(report['checks']):
        raise AssertionError('Incomplete task persistence result')
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': report['status'], 'passed': report['passed'], 'total': report['total'], 'output': str(args.output)}))
    if result.returncode or report['status'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
