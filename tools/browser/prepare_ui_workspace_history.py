"""Prepare fixed UI source-oracle objects independently of checkout depth.

The existing public-history verifier and CI fetch authorization remain the only
Git implementation. This supplement does not change historical input readers,
the original dependency manifest, source projections, or Android execution.
"""
import hashlib
import json
import os
from pathlib import Path
import re

import source_history as history


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = 'tests/baselines/ui-workspace-public-source-history.json'
MANIFEST_BYTES = 6926
MANIFEST_SHA256 = 'f39d449860021ab15d98ef35481c41ebbf97fdf43b7b48a73e152964cfdfbcf5'
OWNERS = (
    ('c244835a4c1e3629909b2b1ce132ca5987a97d9a', '13f8feea716e7ceebd71fb46b21966292c920681', 13),
    ('89729eb2c079d40237ecd466c7444da934206d98', '583db08f6595ddc8e5a387e5cc035de1e70cb690', 10),
)


def manifest(root):
    path = Path(root) / MANIFEST
    history.require(not path.is_symlink() and path.is_file(), 'fixed UI history manifest missing')
    raw = path.read_bytes()
    history.require(len(raw) == MANIFEST_BYTES and hashlib.sha256(raw).hexdigest() == MANIFEST_SHA256,
                    'fixed UI history manifest bytes differ')
    value = json.loads(raw)
    history.require(type(value) is dict and set(value) == {'schema', 'repository', 'scope', 'groups'}
                    and type(value['schema']) is int and value['schema'] == 1
                    and value['repository'] == history.REPOSITORY, 'fixed UI history manifest shape differs')
    groups = value['groups']
    history.require(type(groups) is list and len(groups) == len(OWNERS), 'fixed UI history owners required')
    for group, (commit, tree, count) in zip(groups, OWNERS):
        history.require(type(group) is dict and set(group) == {'commit', 'tree', 'files'}
                        and group['commit'] == commit and group['tree'] == tree
                        and type(group['files']) is dict and len(group['files']) == count,
                        'fixed UI history group differs')
        for name, row in group['files'].items():
            history.require(type(name) is str and re.fullmatch(r'[A-Za-z0-9_./-]{1,240}', name)
                            and not name.startswith('/')
                            and all(part not in ('', '.', '..') for part in name.split('/')),
                            'invalid fixed UI source path')
            history.require(type(row) is dict and set(row) == {'mode', 'blob', 'bytes', 'sha256'}
                            and row['mode'] in ('100644', '100755')
                            and type(row['bytes']) is int and 0 < row['bytes'] <= 4 * 1024 * 1024
                            and re.fullmatch('[0-9a-f]{40}', row.get('blob', ''))
                            and re.fullmatch('[0-9a-f]{64}', row.get('sha256', '')),
                            'invalid fixed UI source object pin')
    return groups


def prepare_ui_workspace_history(root=ROOT, environment=None):
    root = Path(root).resolve()
    environment = os.environ if environment is None else environment
    groups = manifest(root)
    before = history.checkout_state(root)
    observed, fetched = [], []
    for group in groups:
        try:
            ready = history.verify_group(root, group)
        except history.MissingHistoricalObject:
            state = history.authorize_fetch(root, environment)
            history.require(state == before, 'checkout changed before UI dependency fetch')
            try:
                history.checked(root, 'fetch', '--no-tags', '--depth=1', '--no-write-fetch-head', 'origin', group['commit'])
            finally:
                history.require(history.checkout_state(root) == before,
                                'UI dependency fetch changed HEAD, index or tracked bytes')
            fetched.append(group['commit'])
            ready = history.verify_group(root, group)
        observed.append(ready)
    history.require(history.checkout_state(root) == before, 'UI historical verification changed checkout')
    return dict(schema=1, status='passed', repository=history.REPOSITORY,
                sourceCommit=before['sourceCommit'], sourceTree=before['sourceTree'],
                checkoutUnchanged=True, manifest=MANIFEST, manifestSha256=MANIFEST_SHA256,
                supplementalTo=history.MANIFEST, groups=observed, fetchedCommits=fetched,
                testsExecuted=False, actualAndroidExecution=False,
                scope='Explicit setup-time exact UI public source dependencies; original commit/tree/blob verifier and CI authorization. No assertion, source projection, checkout, deadline, signing or app execution changes.')


if __name__ == '__main__':
    print(json.dumps(prepare_ui_workspace_history(), sort_keys=True))
