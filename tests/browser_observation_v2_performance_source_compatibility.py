"""Exact browser-observation-v2 input for retained performance source proofs.

Only historical hash assertions use this module. Current Java compilation,
callback hosts, JavaScript replay and Android execution read the original file.
The complete reviewed source must match before the ten contextual edits can be
reversed to the actual pre-migration source. This is not a general source view.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = 'tests/gecko/GeckoPerformanceIntegrationActivity.java'
DELTA_PATH = ROOT / 'tests/fixtures/browser-observation-v2-performance-source-deltas.json'
DELTA_SHA256 = '533b216bc694746cc3ba25909956d2fbfd549501e9723dcba26c368d0e5056c9'
DELTA_BYTES = 102476
PREVIOUS_BYTES = 105250
PREVIOUS_SHA256 = '13062ecb571592ceb8fb7347dbfd18223ec848328657fa54df0addc55896c36f'
REVIEWED_BYTES = 84404
REVIEWED_SHA256 = '8a4c44e37338cdda817b5428dcf8672f93441af11af45f76447a8103eaeb79ed'
METADATA = {
    'schema': 1,
    'kind': 'historical-source-input-only',
    'path': SOURCE_PATH,
    'browserObservationContract': 2,
    'previousCommit': '5bf46502f37ffe8f3c6f17054a2a7c9ec7d53df5',
    'previousTree': 'a7a65c9efd83cf1c44cd1e5ced26a27e060564b1',
    'reviewedCommit': 'af0feb3cbd0ca353f2a17058bcdbe001a00f1885',
    'reviewedTree': '7a0b2fb502a9d5dd57c8a6e74296cd003a48136f',
    'actualAndroidExecution': False,
    'runtimeAcceptance': False,
    'previousBytes': PREVIOUS_BYTES,
    'previousSha256': PREVIOUS_SHA256,
    'reviewedBytes': REVIEWED_BYTES,
    'reviewedSha256': REVIEWED_SHA256,
    'contextLines': 3,
}


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def manifest():
    raw = DELTA_PATH.read_bytes()
    if len(raw) != DELTA_BYTES or _sha(raw) != DELTA_SHA256:
        raise ValueError('Performance v2 historical fixture is not the reviewed whole bytes')
    value = json.loads(raw)
    if (type(value) is not dict or set(value) != set(METADATA) | {'deltas'}
            or any(type(value[key]) is not type(expected) or value[key] != expected
                   for key, expected in METADATA.items())
            or type(value['deltas']) is not list or len(value['deltas']) != 10):
        raise ValueError('Performance v2 historical fixture identity differs')
    for index, delta in enumerate(value['deltas']):
        if (type(delta) is not dict
                or set(delta) != {'id', 'previous', 'current', 'previousSha256', 'currentSha256'}
                or delta['id'] != 'context-%02d' % index
                or any(type(delta[key]) is not str or not 0 < len(delta[key].encode('utf-8')) <= 24 * 1024
                       or _sha(delta[key].encode('utf-8')) != delta[key + 'Sha256']
                       for key in ('previous', 'current'))
                or delta['previous'] == delta['current']):
            raise ValueError('Performance v2 historical context differs')
    return value


def _apply(raw, deltas, reverse):
    for delta in reversed(deltas) if reverse else deltas:
        before = delta['current' if reverse else 'previous'].encode('utf-8')
        after = delta['previous' if reverse else 'current'].encode('utf-8')
        if raw.count(before) != 1:
            raise ValueError('Performance v2 inverse requires every exact context once')
        raw = raw.replace(before, after, 1)
        if raw.count(after) != 1:
            raise ValueError('Performance v2 inverse produced a non-unique context')
    return raw


def source_input(raw, relative):
    """Restore one pinned whole source for historical assertions only."""
    if type(raw) is not bytes or type(relative) is not str or relative != SOURCE_PATH:
        raise ValueError('Performance v2 inverse requires complete bytes and its exact owned path')
    value = manifest()
    identity = len(raw), _sha(raw)
    previous_identity = PREVIOUS_BYTES, PREVIOUS_SHA256
    reviewed_identity = REVIEWED_BYTES, REVIEWED_SHA256
    if identity == reviewed_identity:
        previous = _apply(raw, value['deltas'], reverse=True)
    elif identity == previous_identity:
        previous = raw
    else:
        raise ValueError('Performance v2 inverse rejects unknown whole source bytes')
    if (len(previous), _sha(previous)) != previous_identity:
        raise ValueError('Performance v2 inverse did not restore the exact original source')
    forward = _apply(previous, value['deltas'], reverse=False)
    if ((len(forward), _sha(forward)) != reviewed_identity
            or identity == reviewed_identity and forward != raw
            or _apply(forward, value['deltas'], reverse=True) != previous):
        raise ValueError('Performance v2 inverse does not close in both directions')
    return previous
