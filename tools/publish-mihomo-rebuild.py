#!/usr/bin/env python3
"""Publish only native source/rebuild proof, its input receipt and public test log."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'work/mihomo-rebuild'
BRANCH = 'apk/mihomo-rebuild-20261012'
RECEIPT = 'third-party/patches/mihomo-v1.19.31-probe-build.json'
FILES = ('mihomo-rebuild-results.json', 'mihomo-build-receipt.json', 'build.log')


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def git(*args, env=None):
    return subprocess.check_output(['git', *args], cwd=ROOT, env=env, text=True).strip()


def prepare():
    source = git('rev-parse', 'HEAD')
    run_id = os.environ['GITHUB_RUN_ID']
    attempt = os.environ.get('GITHUB_RUN_ATTEMPT', '1')
    if not re.fullmatch('[0-9a-f]{40}', source) or not run_id.isdigit() or not attempt.isdigit():
        raise ValueError('Source or workflow identity is invalid')
    OUT.mkdir(parents=True, exist_ok=True)
    stage = OUT / 'public'
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir()
    result = {'schema': 1, 'sourceCommit': source, 'runId': run_id, 'runAttempt': attempt,
              'workflow': 'Reproducible Mihomo probe core',
              'status': 'failed', 'independentNativeRebuild': False,
              'actualAndroidExecution': False, 'publicArtifactsOnly': True,
              'buildOutcomes': {name: os.environ.get(name, 'missing')
                                for name in ['NATIVE_PINNED_OUTCOME', 'NATIVE_REBUILT_OUTCOME']}}
    receipt = ROOT / RECEIPT
    if receipt.is_file() and not receipt.is_symlink():
        shutil.copyfile(receipt, stage / 'mihomo-build-receipt.json')
    log = OUT / 'build.log'
    if log.is_file() and not log.is_symlink() and log.stat().st_size <= 8_000_000:
        shutil.copyfile(log, stage / 'build.log')
    try:
        if os.environ.get('GITHUB_ACTIONS') != 'true':
            raise ValueError('This proof must originate in an independent Actions runner')
        if any(outcome != 'success' for outcome in result['buildOutcomes'].values()):
            raise ValueError('Input verification or independent rebuilding did not pass')
        original = subprocess.check_output(['git', 'show', 'HEAD:' + RECEIPT], cwd=ROOT)
        if receipt.read_bytes() != original:
            raise ValueError('Rebuilding changed the committed receipt')
        subprocess.run(['python3', 'tools/build-mihomo.py', '--verify'], cwd=ROOT,
                       check=True, stdout=subprocess.DEVNULL)
        value = json.loads(original)
        rebuilt = {}
        for abi, target in [('arm64-v8a', 'android-arm64'), ('x86_64', 'android-amd64')]:
            path = ROOT / 'work/mihomo-build/bin' / ('mihomo-' + target)
            item = value['binaries'][abi]
            if path.is_symlink() or not path.is_file() or digest(path) != item['sha256'] or path.stat().st_size != item['bytes']:
                raise ValueError('A rebuilt Android binary differs from the committed bytes')
            rebuilt[abi] = {'bytes': item['bytes'], 'sha256': item['sha256'],
                            'goos': item['goos'], 'goarch': item['goarch'], 'elf': item['elf']}
        test_log = (stage / 'build.log').read_text('utf-8')
        passed = re.findall(r'^--- PASS: (Test(?:Pocket|Preconnect|SelectorPreconnect)\w+) ', test_log, re.MULTILINE)
        patch = (ROOT / value['inputs']['patch']).read_text('utf-8')
        expected = set(re.findall(r'^\+func (Test(?:Pocket|Preconnect|SelectorPreconnect)\w+)\(', patch, re.MULTILINE))
        probe = [name for name in passed if name.startswith('TestPocketProbe')]
        if len(probe) != 10 or len(expected) < 46 or set(passed) != expected or len(passed) != len(expected):
            raise ValueError('Every reviewed native regression must pass exactly once, including the ten original probe tests')
        fingerprint = [name for name in passed if name.startswith('TestPocketNodeFingerprint')]
        selected_exit = [name for name in passed if name.startswith('TestPocketSelectedExit')]
        subscription_patch = value['recipe'].get('nodeFingerprint') or value['recipe'].get('roleSpecificExitProvider')
        if subscription_patch and (len(fingerprint) != 7 or len(selected_exit) != 11 or len(expected) < 64):
            raise ValueError('Every node identity and selected exit regression must pass exactly once')
        result.update(status='passed', independentNativeRebuild=True,
                      inputs=value['inputs'], recipe=value['recipe'],
                      rebuiltBinaries=rebuilt, nativeRegressionCount=len(passed),
                      nativeRegressions=passed, nativeProbeRegressionCount=len(probe),
                      preconnectRegressionCount=len(passed)-len(probe)-len(fingerprint)-len(selected_exit),
                      nodeFingerprintRegressionCount=len(fingerprint),
                      selectedExitRegressionCount=len(selected_exit),
                      receiptSha256=hashlib.sha256(original).hexdigest(),
                      exactCommittedBytes=True)
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        # These are fixed local validation messages, not native URL error strings.
        result['failure'] = type(error).__name__
        if isinstance(error, ValueError):
            result['reason'] = str(error)
    (stage / 'mihomo-rebuild-results.json').write_text(json.dumps(result, indent=2) + '\n')
    manifest = {'schema': 1, 'sourceCommit': source, 'runId': run_id, 'runAttempt': attempt,
                'status': result['status'], 'independentNativeRebuild': result['independentNativeRebuild'],
                'actualAndroidExecution': False,
                'files': [{'path': name, 'bytes': (stage / name).stat().st_size,
                           'sha256': digest(stage / name)} for name in FILES if (stage / name).is_file()]}
    (stage / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    if {p.name for p in stage.iterdir()} - {*FILES, 'manifest.json'}:
        raise ValueError('Artifact whitelist violation')
    return source, stage, result


def publish(source, stage):
    env = dict(os.environ, GIT_INDEX_FILE=str(OUT / 'artifact-index'), GIT_WORK_TREE=str(stage),
               GIT_AUTHOR_NAME='PocketChat native build', GIT_AUTHOR_EMAIL='pocketchat@users.noreply.github.com',
               GIT_COMMITTER_NAME='PocketChat native build', GIT_COMMITTER_EMAIL='pocketchat@users.noreply.github.com')
    previous = git('ls-remote', 'origin', 'refs/heads/' + BRANCH).split()
    parents = ['-p', source]
    if previous:
        subprocess.run(['git', 'fetch', 'origin', 'refs/heads/' + BRANCH], cwd=ROOT, check=True)
        parents += ['-p', previous[0]]
    subprocess.run(['git', 'read-tree', '--empty'], cwd=ROOT, env=env, check=True)
    names = [name for name in (*FILES, 'manifest.json') if (stage / name).is_file()]
    subprocess.run(['git', 'add', '-f', '--', *names], cwd=ROOT, env=env, check=True)
    tree = git('write-tree', env=env)
    commit = git('commit-tree', tree, *parents, '-m', 'Publish reproducible native probe build proof', env=env)
    subprocess.run(['git', 'push', 'origin', commit + ':refs/heads/' + BRANCH], cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true', help='Validate and stage whitelisted proof without pushing.')
    args = parser.parse_args()
    source, stage, result = prepare()
    if not args.dry_run:
        publish(source, stage)
    print(json.dumps({'status': result['status'], 'sourceCommit': source,
                      'branch': BRANCH, 'published': not args.dry_run}))
    if result['status'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
