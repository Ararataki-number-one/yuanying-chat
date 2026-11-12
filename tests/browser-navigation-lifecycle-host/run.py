#!/usr/bin/env python3
"""Run current page-memory and reply-observer classes with explicit JVM boundaries."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PROD = ROOT / 'app/src/main/java/local/pocketchat'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json-jar', type=Path, required=True)
    parser.add_argument('--java-home', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    java = lambda name: str(args.java_home / 'bin' / name) if args.java_home else name
    sources = [PROD / name for name in ('PageMemory.java', 'WebReplyObserver.java', 'J.java')]
    sources += [HERE / 'NavigationLifecycleHost.java']
    sources += [ROOT / 'tests/local-draft-policy-host/stubs' / name for name in (
        'android/net/Uri.java', 'android/content/pm/ApplicationInfo.java')]
    inputs = sources + [Path(__file__).resolve(), args.json_jar]
    hashes = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs}
    with tempfile.TemporaryDirectory(prefix='navigation-lifecycle-') as directory:
        classes = Path(directory)
        subprocess.run([java('javac'), '-encoding', 'UTF-8', '-cp', str(args.json_jar),
                        '-d', str(classes), *map(str, sources)], check=True, timeout=60)
        result = subprocess.run([java('java'), '-cp', str(classes) + ':' + str(args.json_jar),
                                 'local.pocketchat.NavigationLifecycleHost'],
                                capture_output=True, text=True, check=True, timeout=30)
    report = json.loads(result.stdout)
    report['sourceFiles'] = {str(path.relative_to(ROOT)): hashes[str(path)] for path in sources}
    report['jsonJarSha256'] = hashes[str(args.json_jar)]
    report['executionInputsUnchanged'] = all(
        hashlib.sha256(path.read_bytes()).hexdigest() == hashes[str(path)] for path in inputs)
    report['sourceCommit'] = subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    report['scope'] = (
        'Whole current PageMemory and WebReplyObserver classes, without source rewriting. '
        'Explicit in-memory preferences/delivery/archive, deterministic main-thread scheduler, '
        'queued page-driver responses, and current browser port boundaries. '
        'No Android/Gecko, actual DOM, disk durability or network/server execution.')
    if not report['executionInputsUnchanged']:
        raise AssertionError('Production or test inputs changed during execution')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': report['status'], 'passed': report['passed'],
                      'output': str(args.output)}))


if __name__ == '__main__':
    main()
