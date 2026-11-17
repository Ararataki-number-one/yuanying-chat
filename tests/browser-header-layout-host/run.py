#!/usr/bin/env python3
"""Run production compact-header geometry with JVM assertions, without Android emulation."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    executable = lambda name: str(args.java_home / 'bin' / name) if args.java_home else name
    sources = [ROOT / 'app/src/main/java/local/pocketchat/BrowserHeaderLayout.java',
               Path(__file__).with_name('BrowserHeaderLayoutHost.java')]
    inputs = sources + [Path(__file__).resolve()]
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    with tempfile.TemporaryDirectory(prefix='browser-header-') as directory:
        subprocess.run([executable('javac'), '-encoding', 'UTF-8', '-d', directory,
                        *map(str, sources)], check=True, timeout=60)
        result = subprocess.run([executable('java'), '-cp', directory,
                                 'local.pocketchat.BrowserHeaderLayoutHost'],
                                check=True, capture_output=True, text=True, timeout=30)
    report = json.loads(result.stdout)
    report['sourceFiles'] = hashes
    report['executionInputsUnchanged'] = all(
        hashes[str(p.relative_to(ROOT))] == hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs)
    assert report['executionInputsUnchanged']
    report['scope'] = ('Actual production header geometry over density, window-width and text-height cases. '
                       'Checks full-size effective network targets, capsule priority and no webpage interception. '
                       'Does not execute Android View dispatch, render screenshots or run either browser engine.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(status=report['status'], cases=report['cases'], checks=report['checks'],
                         output=str(args.output))))


if __name__ == '__main__':
    main()
