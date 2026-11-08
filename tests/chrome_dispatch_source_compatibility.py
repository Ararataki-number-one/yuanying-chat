"""One reviewed dispatcher append for historical metadata comparisons only.

The original first-tap JSON stays byte-exact. Its loader validates those bytes
before this explicit outer metadata view composes the new known after-image.
No Android runner, workload, compiler or release producer imports this module.
"""
import copy
import functools
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/chrome-dispatch-source-deltas.json'
FIXTURE_SHA256 = 'e065d63cc7d114085fd12a2e2ee48864b7d857461ba543c1cf326b84916e62b0'
PATH = 'tests/gecko/run_chrome_collapse.py'
OLD_FIXTURE_SHA256 = '2c31cb3286d88a91079fb33cef1f27b9c81f7cefda6fbb1c7bc6537e6ca79795'
PREVIOUS_SHA256 = '630b6ac6be99f47316f4d6a49bf646ed43f5d064309b03588e09a01bb423fe67'
CURRENT_SHA256 = 'a64eb97979edbf10f392cc74ca018d33a6b9ac8e05266c4d3f4382a876b280b3'
SHA = lambda raw: hashlib.sha256(raw).hexdigest()


def unique(items):
    value = {}
    for key, item in items:
        if key in value:
            raise ValueError('Duplicate Chrome dispatcher comparison metadata')
        value[key] = item
    return value


def reject_constant(value):
    raise ValueError('Nonfinite Chrome dispatcher comparison metadata')


def manifest():
    expected = ROOT / 'tests/fixtures/chrome-dispatch-source-deltas.json'
    if FIXTURE != expected or FIXTURE.is_symlink() or not FIXTURE.is_file():
        raise ValueError('Exact ordinary dispatcher comparison fixture required')
    raw = FIXTURE.read_bytes()
    if not 0 < len(raw) <= 32768 or SHA(raw) != FIXTURE_SHA256:
        raise ValueError('Exact bounded dispatcher comparison fixture required')
    value = json.loads(raw, object_pairs_hook=unique, parse_constant=reject_constant)
    if (set(value) != {'schema', 'kind', 'actualAndroidExecution', 'runtimeAcceptance', 'path', 'baseCommit',
            'oldFixtureSha256', 'previousBytes', 'previousSha256', 'reviewedBytes', 'reviewedSha256', 'deltas', 'currentRow'}
            or type(value['schema']) is not int or value['schema'] != 1
            or value['kind'] != 'historical-chrome-dispatch-comparison-only'
            or value['actualAndroidExecution'] is not False or value['runtimeAcceptance'] is not False
            or value['path'] != PATH or value['baseCommit'] != '06a802663075664b75aa9d19184d9c02b6bab7c9'
            or value['oldFixtureSha256'] != OLD_FIXTURE_SHA256
            or (value['previousBytes'], value['previousSha256']) != (15834, PREVIOUS_SHA256)
            or (value['reviewedBytes'], value['reviewedSha256']) != (16331, CURRENT_SHA256)
            or type(value['deltas']) is not list or len(value['deltas']) != 1):
        raise ValueError('Foreign dispatcher comparison identity')
    delta = value['deltas'][0]
    for name in ('previous', 'current'):
        literal = delta[name].encode()
        if not 0 < len(literal) <= 32768 or (len(literal), SHA(literal)) != (delta[name+'Bytes'], delta[name+'Sha256']):
            raise ValueError('Dispatcher context is not exact and bounded')
    if not delta['current'].startswith(delta['previous']) or len(delta['current'].encode()) - len(delta['previous'].encode()) != 497:
        raise ValueError('Only the reviewed dispatcher append is owned')
    return value


def source_input(raw):
    value = manifest()
    if type(raw) is not bytes or (len(raw), SHA(raw)) != (16331, CURRENT_SHA256):
        raise ValueError('Unreviewed complete dispatcher source')
    delta = value['deltas'][0]
    current, previous = delta['current'].encode(), delta['previous'].encode()
    if raw.count(current) != 1:
        raise ValueError('Unique dispatcher context required')
    restored = raw.replace(current, previous, 1)
    if (len(restored), SHA(restored)) != (15834, PREVIOUS_SHA256):
        raise ValueError('The entire public06 runner did not restore')
    return restored


def wrap_manifest(original):
    @functools.wraps(original)
    def current_comparison_manifest():
        previous = original()  # Always validates the immutable original JSON.
        value = manifest()
        before = previous['files'][PATH]
        after = value['currentRow']
        if (set(after) != set(before) or len(before['deltas']) != 1 or len(after['deltas']) != 1
                or any(after[key] != before[key] for key in ('previousBytes', 'previousSha256'))
                or (after['reviewedBytes'], after['reviewedSha256']) != (16331, CURRENT_SHA256)):
            raise ValueError('The original first-tap identity or hunk count changed')
        old_delta, new_delta = before['deltas'][0], after['deltas'][0]
        if new_delta['id'] != old_delta['id']:
            raise ValueError('The original first-tap hunk identity changed')
        for name in ('previous', 'current'):
            literal = new_delta[name].encode()
            if not 0 < len(literal) <= 32768 or SHA(literal) != new_delta[name+'Sha256']:
                raise ValueError('The composed comparison hunk is not exact and bounded')
        append = value['deltas'][0]
        current, previous_append = append['current'], append['previous']
        if new_delta['current'].count(current) != 1:
            raise ValueError('The composed comparison does not own exactly one append')
        middle = new_delta['current'].replace(current, previous_append, 1)
        if (not middle.startswith(old_delta['current']) or not new_delta['previous'].startswith(old_delta['previous'])
                or middle[len(old_delta['current']):] != new_delta['previous'][len(old_delta['previous']):]):
            raise ValueError('The composed hunk changed an original runtime byte')
        result = copy.deepcopy(previous)
        result['files'][PATH] = copy.deepcopy(after)
        return result
    return current_comparison_manifest
