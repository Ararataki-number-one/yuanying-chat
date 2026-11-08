#!/usr/bin/env python3
"""Prepare pinned public history before unchanged profile host tests run."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location('profile_host_public_history', ROOT / 'tools/browser/source_history.py')
history = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(history)
ADDITIONAL_MANIFEST = 'tests/baselines/glass-source-history.json'
ADDITIONAL_MANIFEST_SHA256 = 'af35f288a24a95da70d86559903fed6659c7fc7b8a283e1bc807732f964d5920'
ADDITIONAL_COMMITS = ('6ee06aced87581e52aa301431f8996ed46d666b8',
                      '7402ead321ca74b9fbefeab32a1aaffb32832011')
UI_MANIFEST = 'tests/baselines/ui-preparation-source-history.json'
UI_MANIFEST_SHA256 = 'a267fa95edd75fc29832cb3aa284815f3d8e870d0ca86f84df59cd46c1e7198f'


def require(condition, message):
    if not condition:
        raise RuntimeError('Profile host prerequisites: ' + message)


def authorize_fetch(root, source, environment):
    """Authorize the actual checkout using the event, without rewriting GITHUB_SHA."""
    require(environment.get('CI') == 'true' and environment.get('GITHUB_ACTIONS') == 'true'
            and environment.get('GITHUB_SERVER_URL') == 'https://github.com'
            and environment.get('GITHUB_REPOSITORY') == history.REPOSITORY,
            'missing history requires the fixed repository GitHub CI')
    for key, maximum in (('GITHUB_RUN_ID', 20), ('GITHUB_RUN_ATTEMPT', 10)):
        require(isinstance(environment.get(key), str)
                and re.fullmatch('[1-9][0-9]{0,' + str(maximum - 1) + '}', environment[key]),
                'positive workflow run and attempt required')
    require(re.fullmatch('[0-9a-f]{40}', environment.get('GITHUB_SHA', '')),
            'actual workflow SHA required')
    event_path = Path(environment.get('GITHUB_EVENT_PATH', ''))
    require(event_path.is_file() and not event_path.is_symlink() and event_path.stat().st_size <= 2 * 1024 * 1024,
            'bounded actual GitHub event required')
    event = json.loads(event_path.read_bytes())
    require(type(event) is dict and type(event.get('repository')) is dict
            and event['repository'].get('full_name') == history.REPOSITORY,
            'event repository differs')
    name, ref = environment.get('GITHUB_EVENT_NAME'), environment.get('GITHUB_REF')
    if name == 'pull_request':
        pull = event.get('pull_request')
        number = event.get('number')
        require(type(pull) is dict and type(number) is int and number > 0
                and ref == 'refs/pull/' + str(number) + '/merge', 'actual pull request event required')
        require(pull.get('head', {}).get('sha') == source
                and pull.get('base', {}).get('repo', {}).get('full_name') == history.REPOSITORY,
                'event pull request head or base repository differs')
    elif name == 'push':
        require(environment['GITHUB_SHA'] == source and event.get('after') == source
                and event.get('ref') == ref and isinstance(ref, str)
                and ref.startswith(('refs/heads/', 'refs/tags/')), 'push source or ref differs')
    elif name == 'workflow_dispatch':
        require(environment['GITHUB_SHA'] == source and isinstance(ref, str)
                and ref.startswith(('refs/heads/', 'refs/tags/'))
                and event.get('ref') in (ref, ref.split('/', 2)[2]), 'dispatch source or ref differs')
    else:
        require(False, 'unsupported workflow event')
    require(history.checked(root, 'rev-parse', '--show-toplevel').decode().strip() == str(root),
            'checkout root differs')
    require(history.checked(root, 'remote', 'get-url', 'origin').decode().strip() in history.ORIGINS,
            'fixed public GitHub origin required')
    require(not history.checked(root, 'status', '--porcelain', '--untracked-files=no').strip(),
            'tracked checkout must be clean before network fetch')


def prepare_history(root=ROOT, *, source_commit, environment=None):
    root = Path(root).resolve()
    environment = os.environ if environment is None else environment
    require(type(source_commit) is str and re.fullmatch('[0-9a-f]{40}', source_commit),
            'exact checkout source commit required')
    groups = history.manifest(root)
    require(len(groups) == 21, 'all twenty-one fixed historical owner groups required')
    before = history.checkout_state(root)
    require(before['sourceCommit'] == source_commit, 'requested source differs from actual checkout')
    missing = []
    for group in groups:
        try:
            history.verify_group(root, group)
        except history.MissingHistoricalObject:
            missing.append(group['commit'])
    if missing:
        authorize_fetch(root, source_commit, environment)
        require(history.checkout_state(root) == before, 'checkout changed before history fetch')
        try:
            # Exact owners only: no ref updates or lazy/test-time retrieval.
            # --no-filter also supplies blobs in local partial-clone checkouts.
            history.checked(root, 'fetch', '--no-tags', '--depth=1', '--no-write-fetch-head',
                            '--no-filter', 'origin', *missing)
        finally:
            require(history.checkout_state(root) == before,
                    'history fetch changed HEAD, tree, index or tracked bytes')
    observed = [history.verify_group(root, group) for group in groups]
    require(history.checkout_state(root) == before, 'history verification changed checkout')
    return dict(schema=1, status='passed', sourceCommit=source_commit, sourceTree=before['sourceTree'],
                manifestSha256=history.MANIFEST_SHA256, groups=observed, fetchedCommits=missing,
                checkoutUnchanged=True, testsExecuted=False, actualAndroidExecution=False)


def additional_manifest(root):
    """Separate fixed dependencies introduced by the new transport controls."""
    path = Path(root) / ADDITIONAL_MANIFEST
    require(path.is_file() and not path.is_symlink(), 'fixed additional history manifest required')
    raw = path.read_bytes()
    require(0 < len(raw) <= 16384 and hashlib.sha256(raw).hexdigest() == ADDITIONAL_MANIFEST_SHA256,
            'fixed additional history manifest bytes differ')
    value = json.loads(raw)
    require(type(value) is dict and set(value) == {'schema', 'repository', 'scope', 'groups'}
            and type(value['schema']) is int and value['schema'] == 1
            and value['repository'] == history.REPOSITORY
            and value['scope'] == 'additional-glass-transport-source-history',
            'fixed additional history manifest shape differs')
    groups = value['groups']
    require(type(groups) is list and len(groups) == 2
            and tuple(group.get('commit') for group in groups) == ADDITIONAL_COMMITS,
            'only two fixed additional public owners required')
    expected_paths = (
        {'tests/final_browser_source_compatibility.py'},
        {'.github/workflows/browser-2_1-acceptance.yml', '.github/workflows/profile-upgrade-checks.yml',
         '.github/workflows/glass-release-validation.yml', 'tests/final_browser_source_compatibility.py',
         'tests/profile_fixture_root_source_compatibility.py', 'tests/profile_final_browser_source_compatibility_test.py',
         'tests/fixtures/profile-fixture-root-source-deltas.json', 'tests/fixtures/resource-startup-source-deltas.json',
         'tests/fixtures/final-browser-source-deltas.json', 'app/src/main/java/local/pocketchat/ProfileContext.java',
         'app/src/main/java/local/pocketchat/GeckoWebView.java'},
    )
    for group, paths in zip(groups, expected_paths):
        require(type(group) is dict and set(group) == {'commit', 'tree', 'files'}
                and re.fullmatch('[0-9a-f]{40}', group.get('tree', ''))
                and type(group['files']) is dict and set(group['files']) == paths,
                'fixed additional owner tree and paths required')
        for row in group['files'].values():
            require(type(row) is dict and set(row) == {'mode', 'blob', 'bytes', 'sha256'}
                    and row['mode'] in ('100644', '100755') and type(row['bytes']) is int
                    and 0 < row['bytes'] <= 4 * 1024 * 1024
                    and re.fullmatch('[0-9a-f]{40}', row.get('blob', ''))
                    and re.fullmatch('[0-9a-f]{64}', row.get('sha256', '')),
                    'fixed additional historical object pins required')
    return groups


def prepare_additional_history(root=ROOT, *, source_commit, environment=None):
    """Fetch only missing fixed owners, then verify their real trees and blobs."""
    root = Path(root).resolve()
    environment = os.environ if environment is None else environment
    require(type(source_commit) is str and re.fullmatch('[0-9a-f]{40}', source_commit),
            'exact checkout source commit required')
    groups = additional_manifest(root)
    require(len(groups) == 2, 'two separate additional history groups required')
    before = history.checkout_state(root)
    require(before['sourceCommit'] == source_commit, 'requested source differs from actual checkout')
    missing = []
    for group in groups:
        try:
            history.verify_group(root, group)
        except history.MissingHistoricalObject:
            missing.append(group['commit'])
    if missing:
        authorize_fetch(root, source_commit, environment)
        require(history.checkout_state(root) == before, 'checkout changed before additional history fetch')
        try:
            history.checked(root, 'fetch', '--no-tags', '--depth=1', '--no-write-fetch-head',
                            '--no-filter', 'origin', *missing)
        finally:
            require(history.checkout_state(root) == before,
                    'additional history fetch changed HEAD, tree, index or tracked bytes')
    observed = [history.verify_group(root, group) for group in groups]
    require(history.checkout_state(root) == before, 'additional history verification changed checkout')
    return dict(schema=1, status='passed', sourceCommit=source_commit, sourceTree=before['sourceTree'],
                manifestSha256=ADDITIONAL_MANIFEST_SHA256, groups=observed, fetchedCommits=missing,
                checkoutUnchanged=True, testsExecuted=False, actualAndroidExecution=False)


def ui_manifest(root):
    """One independent fixed UI owner; the original inventories stay whole."""
    path = Path(root) / UI_MANIFEST
    require(path.is_file() and not path.is_symlink(), 'fixed UI history manifest required')
    raw = path.read_bytes()
    require(0 < len(raw) <= 4096 and hashlib.sha256(raw).hexdigest() == UI_MANIFEST_SHA256,
            'fixed UI history manifest bytes differ')
    value = json.loads(raw)
    require(type(value) is dict and set(value) == {'schema', 'repository', 'scope', 'groups'}
            and type(value['schema']) is int and value['schema'] == 1
            and value['repository'] == history.REPOSITORY
            and value['scope'] == 'additional-ui-preparation-source-history',
            'fixed UI history manifest shape differs')
    expected = {'commit': '4363dbc04df80d5c82ba966248e47a3fd69cbcc8',
                'tree': '08189ae748eb1045ff21af4253369ef17d6bdad3',
                'files': {'tests/gecko/UiVisualIntegrationActivity.java': {
                    'mode': '100644', 'blob': 'be0704e74cc2f106dc1c765c909cf17c33e6f0dc',
                    'bytes': 13373, 'sha256': '04f629d6053d1fc62bdddd590c4b405ddff2d564fd4dc3211332c849da0a4366'}}}
    require(type(value['groups']) is list and value['groups'] == [expected],
            'one fixed UI commit, tree and complete Activity blob required')
    return value['groups']


def prepare_ui_history(root=ROOT, *, source_commit, environment=None):
    """Use the same strict object checks and explicit fetch for the UI before."""
    root = Path(root).resolve()
    environment = os.environ if environment is None else environment
    require(type(source_commit) is str and re.fullmatch('[0-9a-f]{40}', source_commit),
            'exact checkout source commit required')
    groups = ui_manifest(root)
    require(len(groups) == 1, 'one separate UI history group required')
    before = history.checkout_state(root)
    require(before['sourceCommit'] == source_commit, 'requested source differs from actual checkout')
    missing = []
    for group in groups:
        try:
            history.verify_group(root, group)
        except history.MissingHistoricalObject:
            missing.append(group['commit'])
    if missing:
        authorize_fetch(root, source_commit, environment)
        require(history.checkout_state(root) == before, 'checkout changed before UI history fetch')
        try:
            history.checked(root, 'fetch', '--no-tags', '--depth=1', '--no-write-fetch-head',
                            '--no-filter', 'origin', *missing)
        finally:
            require(history.checkout_state(root) == before,
                    'UI history fetch changed HEAD, tree, index or tracked bytes')
    observed = [history.verify_group(root, group) for group in groups]
    require(history.checkout_state(root) == before, 'UI history verification changed checkout')
    return dict(schema=1, status='passed', sourceCommit=source_commit, sourceTree=before['sourceTree'],
                manifestSha256=UI_MANIFEST_SHA256, groups=observed, fetchedCommits=missing,
                checkoutUnchanged=True, testsExecuted=False, actualAndroidExecution=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-commit', required=True)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    value = prepare_history(args.root, source_commit=args.source_commit)
    value['additionalHistory'] = prepare_additional_history(args.root, source_commit=args.source_commit)
    value['uiActivityHistory'] = prepare_ui_history(args.root, source_commit=args.source_commit)
    raw = json.dumps(value, sort_keys=True, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw)
    else:
        print(raw, end='')


if __name__ == '__main__':
    main()
