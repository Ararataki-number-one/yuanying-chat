#!/usr/bin/env python3
"""Execute the complete runtime policy with explicitly synthetic Android dependencies."""
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
    source = ROOT / 'app/src/main/java/local/pocketchat/BackgroundReplyPolicy.java'
    production = source.read_bytes()
    hashes = {str(path.relative_to(ROOT)): digest(path)
              for path in [source, pathlib.Path(__file__).resolve(), *sorted(HERE.rglob('*.java'))]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    log = args.output.with_suffix('.log')
    with tempfile.TemporaryDirectory(prefix='background-reply-runtime-host-') as raw:
        temporary = pathlib.Path(raw)
        selected = temporary / 'local/pocketchat/BackgroundReplyPolicy.java'
        selected.parent.mkdir(parents=True)
        selected.write_bytes(production)
        classes = temporary / 'classes'
        compilation = subprocess.run(
            [str(args.java_home / 'bin/javac'), '-encoding', 'UTF-8', '-cp', str(args.json_jar),
             '-d', str(classes), str(selected), *map(str, sorted(HERE.rglob('*.java')))],
            text=True, capture_output=True, timeout=60)
        log.write_text('Synthetic JVM compile\n' + compilation.stdout + compilation.stderr)
        if compilation.returncode:
            raise SystemExit(f'Runtime host compile failed; see {log}')
        result = subprocess.run(
            [str(args.java_home / 'bin/java'), '-cp', str(classes) + ':' + str(args.json_jar),
             'local.pocketchat.BackgroundReplyRuntimeHost'], text=True, capture_output=True, timeout=60)
        with log.open('a') as stream:
            stream.write('\nSynthetic JVM execution\n' + result.stdout + result.stderr)
        if not result.stdout:
            raise SystemExit(f'Runtime host produced no report; see {log}')
        report = json.loads(result.stdout)
        report.update(
            sourceCommit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
            selectedProductionRef='working-tree',
            selectedProductionSha256={'BackgroundReplyPolicy.java': hashlib.sha256(production).hexdigest()},
            sourceFiles=hashes,
            executionInputsUnchanged=all(digest(ROOT / path) == expected for path, expected in hashes.items()),
            actualAndroidExecution=False,
            actualSQLiteExecution=False,
            actualPhoneExecution=False,
            scope='Complete production BackgroundReplyPolicy.java with fake AppSettings authority and synthetic Android process lists, preferences, broadcasts, main queue, writer-gate recorder, eight ChatService targets, ChatService release hook and ChatSession peek/hook. Tests policy dispatch and ownership decisions only. No Android receiver security/lifecycle, real service or wakelock release, browser capture, SQLite/WAL, process startup, network transport, or phone acceptance proof.')
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
