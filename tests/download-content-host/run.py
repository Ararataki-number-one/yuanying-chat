#!/usr/bin/env python3
"""Compile the real download metadata validator and exercise byte-preserving cases."""
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
    parser.add_argument('--output', type=Path, default=ROOT / 'work/download-content/results.json')
    args = parser.parse_args()
    sources = [ROOT / 'app/src/main/java/local/pocketchat/DownloadFileInfo.java',
               Path(__file__).with_name('DownloadContentCases.java')]
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    binary = lambda name: str(args.java_home / 'bin' / name) if args.java_home else name
    with tempfile.TemporaryDirectory(prefix='download-content-classes-') as directory:
        subprocess.run([binary('javac'), '-encoding', 'UTF-8', '-d', directory, *map(str, sources)], check=True)
        result = subprocess.run([binary('java'), '-cp', directory, 'local.pocketchat.DownloadContentCases'],
                                check=True, capture_output=True, text=True, timeout=30)
        report = json.loads(result.stdout)
    assert all(hashlib.sha256(p.read_bytes()).hexdigest() == hashes[str(p.relative_to(ROOT))] for p in sources)
    report.update(sourceFiles=hashes, executionInputsUnchanged=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
