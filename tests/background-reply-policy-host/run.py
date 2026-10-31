#!/usr/bin/env python3
"""Execute production AppSettings policy helpers with a synthetic transaction adapter."""
import argparse
import hashlib
import json
import pathlib
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--java-home', required=True, type=pathlib.Path)
    parser.add_argument('--json-jar', required=True, type=pathlib.Path)
    parser.add_argument('--output', required=True, type=pathlib.Path)
    args = parser.parse_args()
    source = ROOT / 'app/src/main/java/local/pocketchat/AppSettings.java'
    production = source.read_bytes()
    inputs = [source, pathlib.Path(__file__).resolve(), *sorted(HERE.rglob('*.java'))]
    hashes = {str(path.relative_to(ROOT)): digest(path) for path in inputs}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    log = args.output.with_suffix('.log')
    with tempfile.TemporaryDirectory(prefix='background-reply-policy-host-') as raw:
        temporary = pathlib.Path(raw)
        selected = temporary / 'local/pocketchat/AppSettings.java'
        selected.parent.mkdir(parents=True)
        selected.write_bytes(production)
        classes = temporary / 'classes'
        sources = [selected, *sorted(HERE.rglob('*.java'))]
        compile_result = subprocess.run(
            [str(args.java_home / 'bin/javac'), '-encoding', 'UTF-8', '-cp', str(args.json_jar),
             '-d', str(classes), *map(str, sources)], text=True, capture_output=True, timeout=60)
        log.write_text('Synthetic JVM compile\n' + compile_result.stdout + compile_result.stderr)
        if compile_result.returncode:
            raise SystemExit(f'Host harness compile failed; see {log}')
        result = subprocess.run(
            [str(args.java_home / 'bin/java'), '-cp', str(classes) + ':' + str(args.json_jar),
             'local.pocketchat.BackgroundReplyPolicyHost'], text=True, capture_output=True, timeout=60)
        with log.open('a') as stream:
            stream.write('\nSynthetic JVM execution\n' + result.stdout + result.stderr)
        if not result.stdout:
            raise SystemExit(f'Host harness produced no report; see {log}')
        report = json.loads(result.stdout)
        report.update(
            sourceCommit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
            selectedProductionRef='working-tree',
            selectedProductionSha256={'AppSettings.java': hashlib.sha256(production).hexdigest()},
            sourceFiles=hashes,
            executionInputsUnchanged=all(digest(ROOT / path) == expected for path, expected in hashes.items()),
            actualAndroidExecution=False,
            actualSQLiteExecution=False,
            actualPhoneExecution=False,
            scope='Complete production AppSettings.java policy authority helpers. Synthetic in-memory SQLiteDatabase adapter with writer locking, nested transaction rollback, fault injection, query snapshots, and actual Java threads. BackgroundReplyPolicy supplies its immutable Snapshot data carrier only. No Android lifecycle, WAL, multiprocess, device, or phone proof.')
        if not report['executionInputsUnchanged']:
            report['status'] = 'source-changed'
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps({'status': report['status'], 'passed': report['passed'], 'total': report['total'],
                          'actualAndroidExecution': False, 'actualSQLiteExecution': False,
                          'output': str(args.output), 'log': str(log)}))
        if result.returncode or report['status'] != 'passed':
            raise SystemExit(1)


if __name__ == '__main__':
    main()
