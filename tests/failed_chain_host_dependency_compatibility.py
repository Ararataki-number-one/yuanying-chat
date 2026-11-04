"""Exact inverse of one reviewed host compilation dependency addition.

Only the source-compatibility test consumes this inverse. The behavioral host
continues to execute its current source and the real ChromiumRouteLease class.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = 'tests/profile_failed_chain_fixture_config_test.py'
PREVIOUS_SHA = '1780f6213812f9a44203cb4ced9d2aa9740b6590d41df59f817c76da910c2a56'
CURRENT_SHA = '2a16d59efb3f74684f4ffe4e30a7eb39d4be0a75f496b3d7d37ead4b3d4451e6'
MANIFEST_PATH = 'tests/fixtures/failed-chain-host-dependency210-inverse.json'
MANIFEST_SHA256 = '64c2382033dd565ec33f12cad1d737bd2ee13d842d12d441a16f991462e7257c'


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _pairs(rows):
    result = {}
    for key, value in rows:
        if key in result:
            raise ValueError('Duplicate host dependency inverse metadata field')
        result[key] = value
    return result


def manifest():
    path = ROOT / MANIFEST_PATH
    if any(parent.is_symlink() for parent in (path, *path.parents)):
        raise ValueError('Host dependency inverse manifest symlink rejected')
    raw = path.read_bytes()
    if _sha(raw) != MANIFEST_SHA256:
        raise ValueError('Reviewed host dependency inverse metadata changed')
    value = json.loads(raw, object_pairs_hook=_pairs)
    if (set(value) != {'schema', 'path', 'beforeSha256', 'afterSha256', 'changes'}
            or type(value['schema']) is not int or value['schema'] != 1
            or value['path'] != PATH or value['beforeSha256'] != PREVIOUS_SHA
            or value['afterSha256'] != CURRENT_SHA):
        raise ValueError('Unexpected host dependency inverse identity')
    changes = value['changes']
    if (not isinstance(changes, list) or len(changes) != 1
            or set(changes[0]) != {'id', 'before', 'old', 'new', 'after'}
            or changes[0]['id'] != 'compile-actual-chromium-route-lease'
            or any(not isinstance(item, str) or not item for item in changes[0].values())
            or changes[0]['old'] == changes[0]['new']):
        raise ValueError('Reviewed host dependency inverse change differs')
    return value


def restore_current_host(raw, path=PATH):
    """Require the exact current host, then recover its entire prior source."""
    if path != PATH or type(raw) is not bytes or _sha(raw) != CURRENT_SHA:
        raise ValueError('Exact reviewed current host bytes and path required')
    row, = manifest()['changes']
    literal = (row['before'] + row['new'] + row['after']).encode('utf-8')
    if raw.count(literal) != 1:
        raise ValueError('Host dependency addition is missing, duplicated or moved')
    result = raw.replace(literal, (row['before'] + row['old'] + row['after']).encode('utf-8'), 1)
    if _sha(result) != PREVIOUS_SHA:
        raise ValueError('Exact prior whole host source was not recovered')
    return result
