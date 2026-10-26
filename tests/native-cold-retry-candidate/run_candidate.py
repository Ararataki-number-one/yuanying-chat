#!/usr/bin/env python3
"""Diagnostic native candidate: real old-fail/new-pass, pinned builder, small exports.

Copy this file, inputs.json and the three patch files together into
tests/native-cold-retry-candidate on an isolated debug branch. This never pushes
source, changes a tag/release or claims final-release reproducibility acceptance.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = REPO / 'work/native-cold-retry'
DIAG = OUT / 'diagnostics'
BUILD = REPO / 'work/native-cold-retry-build'
PATCH = REPO / 'third-party/patches/mihomo-v1.19.31-probe.patch'
RECEIPT = REPO / 'third-party/patches/mihomo-v1.19.31-probe-build.json'
PART_BYTES = 16_000_000
PACKAGES = ['adapter', 'adapter/provider', 'hub/route', 'component/urltesttrace',
            'adapter/outbound', 'adapter/outboundgroup', 'component/proxydialer',
            'transport/socks5', 'tunnel']
BEFORE_FAILURES = {'TestPocketColdPrepareResetRetriesOnceBeforePayload',
                   'TestPocketColdPreparePersistentResetStopsAfterOneRetry',
                   'TestPocketColdPrepareRetryStaysInsideActualTunnelAttempt'}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2)+'\n')


def checked_file(path):
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise ValueError('Expected an ordinary source/output file: '+str(path))
    return path


def run(command, name):
    log = DIAG / name
    print('Executing '+name, flush=True)
    with log.open('wb') as stream:
        result = subprocess.run(command, cwd=REPO, stdout=stream, stderr=subprocess.STDOUT)
    print(name+' exit='+str(result.returncode), flush=True)
    return result.returncode, log


def parse_native(log, expected_names, expected_failures):
    text = Path(log).read_text()
    if set(expected_failures) not in (set(), BEFORE_FAILURES):
        raise ValueError('Only the exact three new behavioral failures are valid before')
    rows = re.findall(r'^--- (PASS|FAIL): (Test(?:Pocket|Preconnect|SelectorPreconnect)\w+) ', text, re.M)
    if len(rows) != len(expected_names) or len({name for _, name in rows}) != len(rows):
        raise ValueError('Every expected top-level native test must complete exactly once')
    if {name for _, name in rows} != set(expected_names):
        raise ValueError('Native test name inventory differs')
    failed = {name for status, name in rows if status == 'FAIL'}
    if failed != set(expected_failures):
        raise ValueError('Native failures differ from the exact predeclared before/after set')
    if '[build failed]' in text or re.search(r'^(?:panic:|fatal error:|signal:|runtime:)', text, re.M):
        raise ValueError('Compilation or panic cannot be used as a behavioral reproduction')
    if any(code != '1' for code in re.findall(r'^exit status (\d+)\s*$', text, re.M)):
        raise ValueError('Abnormal test binary exit cannot be used as a reproduction')
    packages = re.findall(r'^(ok|FAIL|\?)\s+github\.com/metacubex/mihomo/([^\s]+)\s+(.+)$', text, re.M)
    if len(packages) != len(PACKAGES) or {name for _, name, _ in packages} != set(PACKAGES):
        raise ValueError('Every original native test package must finish exactly once')
    expected_failed_packages = {'adapter/outbound', 'tunnel'} if expected_failures else set()
    for status, name, _ in packages:
        want = 'FAIL' if name in expected_failed_packages else ('?' if name == 'component/urltesttrace' else 'ok')
        if status != want:
            raise ValueError('Unexpected native package outcome: '+name)
    return {'completed': len(rows), 'passed': len(rows)-len(failed),
            'failed': sorted(failed), 'completionRows': [{'name': n, 'status': s} for s, n in rows],
            'packages': [{'name': n, 'status': s, 'detail': d} for s, n, d in packages],
            'logBytes': Path(log).stat().st_size, 'logSha256': digest(log)}


def source_module_hashes(patch_sha, inputs):
    source = BUILD / ('source-'+patch_sha[:16]) / 'MetaCubeX-mihomo-ab405ba'
    observed = {name: digest(checked_file(source/name)) for name in ('go.mod', 'go.sum')}
    if observed['go.mod'] != inputs['goModSha256'] or observed['go.sum'] != inputs['goSumSha256']:
        raise ValueError('Native build changed original go.mod or go.sum')
    return observed


def export_parts(receipt):
    binaries = {}
    for abi in ('arm64-v8a', 'x86_64'):
        item = receipt['binaries'][abi]
        expected = 'app/src/main/jniLibs/'+abi+'/libmihomo.so'
        if item['path'] != expected:
            raise ValueError('Unexpected native binary path')
        source = checked_file(REPO/expected)
        if source.stat().st_size != item['bytes'] or digest(source) != item['sha256']:
            raise ValueError('Generated binary differs from the authentic new receipt')
        destination = OUT/'binaries'/abi
        destination.mkdir(parents=True, exist_ok=False)
        parts = []
        total = hashlib.sha256()
        with source.open('rb') as stream:
            index = 0
            while block := stream.read(PART_BYTES):
                if index >= 6:
                    raise ValueError('Unexpected native size exceeds the reviewed six export slots')
                target = destination / ('part-'+str(index).zfill(2))
                target.write_bytes(block)
                total.update(block)
                parts.append({'path': str(target.relative_to(OUT)), 'bytes': len(block),
                              'sha256': hashlib.sha256(block).hexdigest()})
                index += 1
        if sum(p['bytes'] for p in parts) != item['bytes'] or total.hexdigest() != item['sha256']:
            raise ValueError('Binary split did not preserve every byte')
        binaries[abi] = {'file': expected, 'bytes': item['bytes'], 'sha256': item['sha256'],
                         'elf': item['elf'], 'parts': parts}
    return binaries


def main():
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        raise ValueError('Run this diagnostic on the isolated Actions candidate branch')
    if not os.environ.get('GITHUB_REF', '').startswith('refs/heads/debug/native-cold-retry-'):
        raise ValueError('This helper is restricted to the isolated candidate ref')
    DIAG.mkdir(parents=True, exist_ok=False)
    result = {'schema': 1, 'status': 'failed', 'diagnosticCandidateBuild': True,
              'actualAndroidExecution': False, 'releaseAcceptance': False,
              'finalSourceReproducibilityAcceptance': False, 'publicationExecuted': False}
    try:
        specification = load(checked_file(HERE/'inputs.json'))
        head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip()
        run_id, attempt = os.environ['GITHUB_RUN_ID'], os.environ.get('GITHUB_RUN_ATTEMPT', '1')
        if head != os.environ['GITHUB_SHA'] or not re.fullmatch('[0-9a-f]{40}', head) or not run_id.isdigit() or not attempt.isdigit():
            raise ValueError('Candidate head/run identity differs')
        result.update(sourceCommit=head, runId=run_id, runAttempt=attempt,
                      baselineNativeSourceReference=specification['baselineSource'])
        for path in (HERE/'inputs.json', Path(__file__).resolve()):
            if subprocess.check_output(['git', 'show', head+':'+str(path.relative_to(REPO))], cwd=REPO) != path.read_bytes():
                raise ValueError('Runner/input specification is not the source head Git blob')
        for name, item in specification['patches'].items():
            if name not in ('baseline-patch.patch', 'before-patch.patch', 'after-patch.patch'):
                raise ValueError('Unexpected patch input')
            path = checked_file(HERE/name)
            if path.stat().st_size != item['bytes'] or digest(path) != item['sha256']:
                raise ValueError('Candidate patch bytes differ')
            if subprocess.check_output(['git', 'show', head+':'+str(path.relative_to(REPO))], cwd=REPO) != path.read_bytes():
                raise ValueError('Candidate input is not this head commit\'s original Git blob')
        baseline = specification['patches']['baseline-patch.patch']['sha256']
        if digest(PATCH) != baseline or subprocess.check_output(['git', 'show', 'HEAD:third-party/patches/mihomo-v1.19.31-probe.patch'], cwd=REPO) != PATCH.read_bytes():
            raise ValueError('Baseline production patch was already modified')
        if digest(checked_file(REPO/'tools/build-mihomo.py')) != specification['builderSha256']:
            raise ValueError('Original native builder changed')
        original_receipt = load(RECEIPT)
        if original_receipt['inputs']['patchSha256'] != baseline or original_receipt['inputs']['archiveSha256'] != specification['archiveSha256']:
            raise ValueError('Original pinned native input receipt differs')
        original = specification['originalNativeTests']
        added = specification['addedNativeTests']
        expected = original+added
        if len(original) != 70 or len(added) != 5 or len(expected) != 75 or len(set(expected)) != 75:
            raise ValueError('Expected original70 plus new5 native test names')
        if any(not re.fullmatch(r'Test(?:Pocket|Preconnect|SelectorPreconnect)\w+', name) for name in expected):
            raise ValueError('Malformed native test name')
        actual_original = re.findall(r'^\+func (Test(?:Pocket|Preconnect|SelectorPreconnect)\w+)\(', (HERE/'baseline-patch.patch').read_text(), re.M)
        actual_after = re.findall(r'^\+func (Test(?:Pocket|Preconnect|SelectorPreconnect)\w+)\(', (HERE/'after-patch.patch').read_text(), re.M)
        if actual_original != original or len(actual_after) != 75 or set(actual_after) != set(expected):
            raise ValueError('Declared test inventories differ from actual native patch declarations')
        if set(specification['expectedBeforeFailures']) != BEFORE_FAILURES or not BEFORE_FAILURES <= set(added):
            raise ValueError('Only the three exact new cold-prepare failures may reproduce before')
        save(DIAG/'input-specification.json', specification)
        save(DIAG/'source-identity.json', {'sourceCommit': head, 'runId': run_id,
             'runAttempt': attempt, 'ref': os.environ['GITHUB_REF'],
             'baselinePatchSha256': baseline, 'builderSha256': digest(REPO/'tools/build-mihomo.py'),
             'candidateInputManifestSha256': digest(HERE/'inputs.json'),
             'runnerSha256': digest(Path(__file__)), 'patchInputs': specification['patches'],
             'sourceOverlayIsExplicit': True, 'releaseAcceptance': False})
        rc, _ = run([sys.executable, 'tools/build-mihomo.py', '--verify'], 'baseline-verify.log')
        if rc != 0: raise ValueError('Original baseline native bytes/receipt do not verify')
        PATCH.write_bytes((HERE/'before-patch.patch').read_bytes())
        rc, before_log = run([sys.executable, 'tools/build-mihomo.py', '--build', '--target',
             'linux-amd64', '--test', '--work-dir', str(BUILD)], 'before.log')
        if rc != 1: raise ValueError('Before must fail its new behavioral assertions, not succeed or crash')
        before = parse_native(before_log, expected, specification['expectedBeforeFailures'])
        before.update(implementation='unchanged baseline production; new test fixture only',
                      patchSha256=digest(PATCH), moduleHashes=source_module_hashes(digest(PATCH), original_receipt['inputs']))
        save(DIAG/'before-result.json', before)
        PATCH.write_bytes((HERE/'after-patch.patch').read_bytes())
        rc, after_log = run([sys.executable, 'tools/build-mihomo.py', '--build', '--target', 'all',
             '--test', '--install', '--work-dir', str(BUILD)], 'after-build.log')
        if rc != 0: raise ValueError('Original pinned full native test/install command failed')
        after = parse_native(after_log, expected, [])
        after.update(patchSha256=digest(PATCH), moduleHashes=source_module_hashes(digest(PATCH), original_receipt['inputs']))
        save(DIAG/'after-result.json', after)
        rc, _ = run([sys.executable, 'tools/build-mihomo.py', '--verify'], 'after-verify.log')
        if rc != 0: raise ValueError('Authentically generated candidate receipt/both binaries do not verify')
        receipt = load(RECEIPT)
        if receipt['inputs']['patchSha256'] != specification['patches']['after-patch.patch']['sha256'] or receipt['recipe'] != original_receipt['recipe']:
            raise ValueError('Generated candidate changed unrelated recipe/native version')
        if {k: v for k, v in receipt['inputs'].items() if k != 'patchSha256'} != {k: v for k, v in original_receipt['inputs'].items() if k != 'patchSha256'}:
            raise ValueError('Generated candidate changed unrelated upstream/module inputs')
        (DIAG/'authentic-candidate-build-receipt.json').write_bytes(RECEIPT.read_bytes())
        binaries = export_parts(receipt)
        result.update(status='passed', original70Retained=True, before=before, after=after,
                      authenticGeneratedReceiptSha256=digest(RECEIPT), binaries=binaries,
                      originalBuilderUnchanged=digest(REPO/'tools/build-mihomo.py') == specification['builderSha256'],
                      candidateBinariesRequireIntegrationAndIndependentFinalRebuild=True)
        pending_bytes = len((json.dumps(result, indent=2)+'\n').encode())
        if sum(f.stat().st_size for f in DIAG.iterdir() if f.is_file()) + 2*pending_bytes > 20_000_000:
            raise ValueError('Diagnostic package exceeds reviewed small-artifact limit')
        save(DIAG/'export-manifest.json', result)
    except Exception as error:
        result.update(status='failed', failureType=type(error).__name__, failure=str(error))
        (DIAG/'export-manifest.json').unlink(missing_ok=True)
        raise
    finally:
        save(DIAG/'candidate-run-result.json', result)


if __name__ == '__main__': main()
