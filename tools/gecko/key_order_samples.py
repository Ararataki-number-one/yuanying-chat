#!/usr/bin/env python3
"""Preserve and qualify predeclared independent runs of the unchanged workloads."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from check_caret_compat_evidence import EVIDENCE_FILES, IME_EVIDENCE_FILES, verify_caret_evidence

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ('1', '2')  # The ordinary editing phase is the third independent run.
SETUP_DIAGNOSTICS = (
    'native-adb-setup-results.json', 'emulator-bootstrap-results.json',
    'android-emulator-package-results.json', 'android-system-image-results.json',
    'android-platform-tools-results.json', 'emulator.log',
)
SCROLL_DIAGNOSTICS = ('gecko-scroll-diagnostics.json', 'gecko-scroll-diagnostic-log.json')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stage(args):
    args.out.mkdir(parents=True)
    compatibility = {'installed-apk-definition-audit.json', 'gecko-caret-compat-results.json',
                     'caret-ime-environment.json'}
    for name in (*EVIDENCE_FILES, *IME_EVIDENCE_FILES):
        original = args.input / ('caret-compat' if name in compatibility else '') / name
        if original.is_file():
            shutil.copy2(original, args.out / name)
    # A setup failure precedes all input evidence. Keep its original commands,
    # scans and state observations even though the unchanged oracle must fail.
    for name in SETUP_DIAGNOSTICS:
        original = args.input / name
        if original.is_file():
            shutil.copy2(original, args.out / name)
    # Preserve completed runner files byte-for-byte, including failed scrolls.
    # These are evidence retention only; missing files cannot become a pass.
    for name in SCROLL_DIAGNOSTICS:
        original = args.input / name
        if original.is_file():
            shutil.copy2(original, args.out / name)
    for folder in (args.input, args.input / 'caret-compat'):
        for pattern in ('*-failure-*', 'installed-apk-read-*.json', 'native-test.log', 'native-input-*.json', 'native-input-*.log'):
            for original in folder.glob(pattern):
                if original.is_file():
                    shutil.copy2(original, args.out / original.name)
    receipt = dict(schema=1, sample=args.sample, status='failed',
                   sourceCommit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                   runId=os.environ['GITHUB_RUN_ID'], runAttempt=os.environ.get('GITHUB_RUN_ATTEMPT', '1'),
                   predeclaredAdditionalSamples=list(SAMPLES), workloadRerun=False,
                   physicalPhoneAcceptance=False)
    try:
        receipt['verification'] = verify_caret_evidence(args.out, receipt['sourceCommit'])
        receipt['status'] = 'passed'
    except Exception as error:
        receipt['error'] = str(error)
    receipt['files'] = {p.name: sha(p) for p in args.out.iterdir() if p.is_file()}
    (args.out / 'sample-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    assert receipt['status'] == 'passed', receipt.get('error')


def collect(args):
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    directories = [('ordinary-editing', args.ordinary)]
    for number in SAMPLES:
        path = args.samples / ('key-order-' + os.environ['GITHUB_RUN_ID'] + '-' +
                               os.environ.get('GITHUB_RUN_ATTEMPT', '1') + '-sample-' + number)
        receipt = json.loads((path / 'sample-receipt.json').read_text())
        assert receipt['status'] == 'passed' and receipt['sample'] == number
        assert receipt['sourceCommit'] == source and receipt['runId'] == os.environ['GITHUB_RUN_ID']
        assert receipt['runAttempt'] == os.environ.get('GITHUB_RUN_ATTEMPT', '1')
        assert receipt['predeclaredAdditionalSamples'] == list(SAMPLES) and receipt['workloadRerun'] is False
        for name, expected in receipt['files'].items():
            assert sha(path / name) == expected, name
        directories.append(('sample-' + number, path))
    rows, nonces, phase_nonces, identities = [], set(), set(), set()
    for label, path in directories:
        result = verify_caret_evidence(path, source)
        report = json.loads((path / 'gecko-caret-compat-results.json').read_text())
        environment = json.loads((path / 'editing-phase-environment.json').read_text())
        nonces.add(report['runNonce']); phase_nonces.add(environment['runNonce'])
        identities.add(tuple(result[key] for key in ('sourceCommit', 'sourceTree', 'runId', 'runAttempt',
            'integrationApkSha256', 'releaseApkSha256', 'sdkBuildReceiptSha256')))
        rows.append(dict(sample=label, verification=result))
    assert len(nonces) == 3 and len(phase_nonces) == 3, 'Independent launches required; copied reports rejected'
    assert len(identities) == 1, 'Every sample must use the same compiled APK and SDK bytes'
    assert rows[0]['verification']['runId'] == os.environ['GITHUB_RUN_ID']
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(dict(schema=1, status='passed', sourceCommit=source,
        sampleCount=3, predeclaredAdditionalSamples=list(SAMPLES), workloadRerun=False,
        sameCompiledApkAndSdk=True, physicalPhoneAcceptance=False, samples=rows), indent=2) + '\n')
    print('Three independent original input workloads: passed')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='mode', required=True)
    s = sub.add_parser('stage')
    s.add_argument('--sample', choices=SAMPLES, required=True)
    s.add_argument('--input', type=Path, required=True)
    s.add_argument('--out', type=Path, required=True)
    c = sub.add_parser('collect')
    c.add_argument('--ordinary', type=Path, required=True)
    c.add_argument('--samples', type=Path, required=True)
    c.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    (stage if a.mode == 'stage' else collect)(a)


if __name__ == '__main__':
    main()
