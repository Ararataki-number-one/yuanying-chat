#!/usr/bin/env python3
"""Publish exact synthetic diagnostic files; never binaries, profiles or keys."""
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / 'work/gecko-ime-writer-diagnostics'
EVIDENCE = OUT / 'evidence'
SOURCE_BRANCH = 'review/ime-writer-diagnostic-1f970ea'
BRANCH = 'debug/gecko-ime-writer-evidence-1f970ea'
BASE = '1f970ea51f90466fb69fc282692ecb535c38ce64'
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024
SHARED = (
    'setup.log', 'classpath.log', 'official-sdk-input-verification.json',
    'official-sdk-resolved-verification.json', 'compile-classpath.json',
    'transform.log', 'ime-writer-transform.json', 'build.log',
    'ime-writer-apk-verification.json', 'apk-verification.log',
)
TRIAL = tuple('trial-1/' + name for name in (
    'status.json', 'device-run.log', 'emulator.log', 'full-logcat.txt',
    'final-screen.png', 'preflight.log', 'runner.log',
    'emulator-bootstrap-results.json', 'gecko-performance-results.json',
    'gecko-performance-failure-log.txt', 'gecko-performance-failure-screen.png',
    'gecko-performance-failure-ui.xml', 'gecko-performance-failure-window.txt',
    'gecko-performance-failure-activity.txt', 'gecko-scroll-diagnostics.json',
    'gecko-scroll-diagnostic-log.json', 'gecko-performance-screen.png',
    'gecko-sdk-ime-log.txt', 'gecko-sdk-ime-transform-receipt.json',
    'gecko-sdk-ime-build-identity.json',
))
ALLOWED = frozenset(SHARED + TRIAL + (
    'workflow-manifest.json', 'manifest.json', 'manifest-sha256.txt',
))
PATH_PATTERN = re.compile(r'sources/([0-9a-f]{40})/runs/([1-9][0-9]*)/attempt-1/(.+)')


def git(*args, env=None):
    return subprocess.check_output(['git', *args], cwd=ROOT, env=env, text=True).strip()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_evidence(name):
    path = EVIDENCE / name
    if not path.exists():
        return None
    if not path.is_file() or any(part.is_symlink() for part in (path, *path.parents)
                                 if part == OUT or OUT in part.parents):
        raise ValueError('Refuse linked or non-file evidence: ' + name)
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError('Synthetic file exceeds publication bound: ' + name)
    return path.read_bytes()


def stage_evidence(stage, source, run_id, attempt):
    if not re.fullmatch('[0-9a-f]{40}', source) or not re.fullmatch('[1-9][0-9]*', run_id) or attempt != '1':
        raise ValueError('Exact source/run and first attempt required; reruns are disabled')
    prefix = pathlib.Path('sources') / source / 'runs' / run_id / 'attempt-1'
    directory = stage / prefix
    directory.mkdir(parents=True)
    artifacts, warnings, total = [], [], 0
    workflow = None
    for name, source_name in [(name, name) for name in SHARED + TRIAL] + [('workflow-manifest.json', 'manifest.json')]:
        data = read_evidence(source_name)
        if data is None:
            continue
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            raise ValueError('Synthetic publication exceeds total byte bound')
        if name.endswith('.json'):
            try:
                value = json.loads(data)
            except (ValueError, UnicodeDecodeError):
                if name == 'workflow-manifest.json':
                    raise ValueError('Required workflow manifest is invalid')
                warnings.append(dict(file=name, reason='Incomplete or malformed optional JSON; raw failure logs retained',
                                     bytes=len(data), sha256=digest(data)))
                continue
            if not isinstance(value, dict) or value.get('sourceCommit') != source or value.get('releaseAcceptance') is True:
                raise ValueError('Foreign or acceptance-promoted JSON: ' + name)
            if name in ('workflow-manifest.json', 'trial-1/status.json'):
                if (value.get('runId') != run_id or value.get('runAttempt') != attempt
                        or value.get('diagnosticOnly') is not True or value.get('releaseAcceptance') is not False
                        or value.get('baseSourceCommit') != BASE):
                    raise ValueError('Diagnostic source/run scope changed: ' + name)
            if name == 'workflow-manifest.json':
                workflow = value
        target = directory / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        artifacts.append(dict(file=name, bytes=len(data), sha256=digest(data)))
    if workflow is None:
        raise ValueError('Workflow diagnostic manifest is required even after failure')
    if (not re.fullmatch('[0-9a-f]{40}', workflow.get('sourceTree', ''))
            or set(workflow.get('outcomes', {})) != {'setup', 'classpath', 'transform', 'build', 'gecko'}
            or any(value not in {'success', 'failure', 'cancelled', 'skipped'} for value in workflow['outcomes'].values())):
        raise ValueError('Workflow source tree or outcome scope changed')
    manifest = dict(schema=1, sourceCommit=source, sourceTree=workflow['sourceTree'],
                    baseSourceCommit=BASE, firstParentSourceCommit=source,
                    runId=run_id, runAttempt=attempt, diagnosticOnly=True,
                    releaseAcceptance=False, productionArtifactPublished=False,
                    requestedTrials=1, requestedInputBursts=1,
                    branch=BRANCH, immutablePath=str(prefix),
                    stepOutcomes=workflow['outcomes'], artifacts=artifacts, warnings=warnings,
                    scope='Raw bounded synthetic logs and reports from a log-only SDK transform. No production artifact, release regression acceptance or phone acceptance.')
    raw = (json.dumps(manifest, indent=2) + '\n').encode()
    (directory / 'manifest.json').write_bytes(raw)
    (directory / 'manifest-sha256.txt').write_text(digest(raw) + '  manifest.json\n')
    names = [str(prefix / item['file']) for item in artifacts]
    names += [str(prefix / 'manifest.json'), str(prefix / 'manifest-sha256.txt')]
    return prefix, names, manifest, digest(raw)


def main():
    source = git('rev-parse', 'HEAD')
    if os.environ.get('GITHUB_SHA') != source or os.environ.get('GITHUB_REF') != 'refs/heads/' + SOURCE_BRANCH:
        raise ValueError('Only the exact diagnostic source branch/run may publish')
    if git('status', '--porcelain', '--untracked-files=normal'):
        raise ValueError('Diagnostic evidence requires clean committed source')
    subprocess.run(['git', 'merge-base', '--is-ancestor', BASE, source], cwd=ROOT, check=True)
    run_id, attempt = os.environ['GITHUB_RUN_ID'], os.environ['GITHUB_RUN_ATTEMPT']
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='git-evidence-', dir=OUT) as temporary:
        stage = pathlib.Path(temporary) / 'tree'
        stage.mkdir()
        prefix, names, manifest, manifest_sha = stage_evidence(stage, source, run_id, attempt)
        if manifest['sourceTree'] != git('rev-parse', 'HEAD^{tree}'):
            raise ValueError('Workflow manifest source tree differs from checked-out source')
        # Actions receives these same bounded, allowlisted bytes even if Git upload fails.
        sanitized = OUT / 'sanitized-evidence'
        if sanitized.exists() or sanitized.is_symlink():
            raise ValueError('Refuse to replace an existing sanitized invocation')
        shutil.copytree(stage, sanitized)
        previous = git('ls-remote', 'origin', 'refs/heads/' + BRANCH).split()
        parents = ['-p', source]
        env = dict(os.environ, GIT_INDEX_FILE=str(pathlib.Path(temporary) / 'index'), GIT_WORK_TREE=str(stage),
                   GIT_AUTHOR_NAME='PocketChat diagnostics', GIT_AUTHOR_EMAIL='pocketchat@users.noreply.github.com',
                   GIT_COMMITTER_NAME='PocketChat diagnostics', GIT_COMMITTER_EMAIL='pocketchat@users.noreply.github.com')
        if previous:
            commit = previous[0]
            git('fetch', '--no-tags', '--depth=1', 'origin', 'refs/heads/' + BRANCH)
            existing = git('ls-tree', '-r', '--name-only', commit).splitlines()
            for name in existing:
                match = PATH_PATTERN.fullmatch(name)
                if match is None or match.group(3) not in ALLOWED:
                    raise ValueError('Existing evidence branch contains an unexpected path')
                if name.startswith(str(prefix) + '/'):
                    raise ValueError('Immutable diagnostic invocation already exists')
            parents += ['-p', commit]
            git('read-tree', commit + '^{tree}', env=env)
        else:
            git('read-tree', '--empty', env=env)
        git('add', '-f', '--', *names, env=env)
        tree = git('write-tree', env=env)
        evidence_commit = git('commit-tree', tree, *parents, '-m',
                              'Preserve synthetic IME writer diagnostics ' + source + ' run ' + run_id, env=env)
        git('push', 'origin', evidence_commit + ':refs/heads/' + BRANCH)
        print(json.dumps(dict(sourceCommit=source, runId=run_id, runAttempt=attempt,
                              diagnosticOnly=True, releaseAcceptance=False, branch=BRANCH,
                              evidenceCommit=evidence_commit, immutablePath=str(prefix),
                              manifestSha256=manifest_sha), indent=2))


if __name__ == '__main__':
    main()
