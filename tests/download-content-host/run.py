#!/usr/bin/env python3
"""Compile the real download metadata validator and exercise byte-preserving cases."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).with_name('fixtures')
ENCRYPTED_FIXTURE_SHA256 = '87096c1f16703bf4a0e33b2a7e67af245974e647db61faee2f90754b8d8b6e18'
ENCRYPTED_LICENSE_SHA256 = 'b221010ab98a91225fe06a99b9f0528050b89dad97e7855fe771079a59714b25'
ENCRYPTED_SOURCE_COMMIT = 'bdb71ea5dfbdee2f3cd86f8852e74be7a6f15667'
ENCRYPTED_FILES = (
    ('ecma376standard_password.docx', 7168, 'd265dcf02f7d552486229b8c67a627ef3752fe6802b02fd2d2d485fcfbbac5de', '81030b5fc2ff6699056fcf27721bad49b836c7c8'),
    ('example_password.docx', 18432, '0605624697328060fdc75ca9929ea20b9d63ebed9387ff1a97aaf9979757234a', 'e36bff91729b1bf720b4b1b6762f6b9d0151e01c'),
    ('example_password.xlsx', 14848, '3f792e3902a615bf0e91771f3f3016b80d59098b8e492efcdc0752748e15b997', '08946a6c0e714039016c84a2aa092d06cced46d1'),
    ('ecma376agile_sha1_password.xlsx', 13824, '4d6437ede946382c471b681c7721e2874de569f829238c5a6b25321b172f104b', 'ac116f4f851ea1b0c29507f0328bd8701f4750c3'),
)


def encrypted_samples(directory):
    fixture = FIXTURES / 'encrypted-office.json'
    license_file = FIXTURES / 'LICENSE-msoffcrypto-tool.txt'
    assert hashlib.sha256(fixture.read_bytes()).hexdigest() == ENCRYPTED_FIXTURE_SHA256
    assert hashlib.sha256(license_file.read_bytes()).hexdigest() == ENCRYPTED_LICENSE_SHA256
    data = json.loads(fixture.read_text())
    assert data['schema'] == 1 and data['repository'] == 'nolze/msoffcrypto-tool'
    assert data['sourceCommit'] == ENCRYPTED_SOURCE_COMMIT
    assert data['licenseFile'] == license_file.name and len(data['files']) == len(ENCRYPTED_FILES)
    paths = []
    for record, (name, size, sha256, git_blob) in zip(data['files'], ENCRYPTED_FILES):
        assert record['file'] == name and record['path'] == 'tests/inputs/' + name
        assert (record['bytes'], record['sha256'], record['gitBlob']) == (size, sha256, git_blob)
        payload = base64.b64decode(record['base64'], validate=True)
        assert len(payload) == size and hashlib.sha256(payload).hexdigest() == sha256
        assert hashlib.sha1(f'blob {size}\0'.encode() + payload).hexdigest() == git_blob
        target = directory / name
        target.write_bytes(payload)
        paths.append(target)
    return paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT / 'work/download-content/results.json')
    args = parser.parse_args()
    java_sources = [ROOT / 'app/src/main/java/local/pocketchat/DownloadFileInfo.java',
                    Path(__file__).with_name('DownloadContentCases.java')]
    sources = java_sources + [Path(__file__).resolve(), FIXTURES / 'encrypted-office.json',
                              FIXTURES / 'LICENSE-msoffcrypto-tool.txt']
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    binary = lambda name: str(args.java_home / 'bin' / name) if args.java_home else name
    with tempfile.TemporaryDirectory(prefix='download-content-classes-') as directory:
        samples = encrypted_samples(Path(directory))
        subprocess.run([binary('javac'), '-encoding', 'UTF-8', '-d', directory, *map(str, java_sources)], check=True)
        result = subprocess.run([binary('java'), '-cp', directory, 'local.pocketchat.DownloadContentCases', *map(str, samples)],
                                check=True, capture_output=True, text=True, timeout=30)
        report = json.loads(result.stdout)
    assert all(hashlib.sha256(p.read_bytes()).hexdigest() == hashes[str(p.relative_to(ROOT))] for p in sources)
    report.update(sourceFiles=hashes, executionInputsUnchanged=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
