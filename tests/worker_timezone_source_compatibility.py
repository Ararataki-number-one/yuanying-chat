"""Finite Worker/timezone overlay for retained historical source oracles.

Actual production/device/behavior hosts never call this module. The complete
reviewed source is identified before reversing contextual edits back to the real
2.1.1 commit, before the original 2.1.0 chain. Unknown files, edits, excerpts and fixture bytes always fail.
"""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
BASE_COMMIT = '8a0a487002993f5dacc02ed313fab00648ccb79a'
BASE_TREE = '4bcc73a10bcba0d9bf97c44d02045af525361fad'
DELTA_PATH = ROOT / 'tests/fixtures/worker-timezone-source-deltas.json'
DELTA_SHA256 = '4eafec08cbeb3beb9098ebf5df7b976423616bb213e47e802a1d39315a27602b'
MAX_FIXTURE_BYTES = 256 * 1024
PATHS = frozenset((
    'app/src/main/java/local/pocketchat/ChatSession.java',
    'app/src/main/java/local/pocketchat/GeckoWebView.java',
))

def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def manifest():
    raw = DELTA_PATH.read_bytes()
    if not 0 < len(raw) <= MAX_FIXTURE_BYTES or _sha(raw) != DELTA_SHA256:
        raise ValueError('Worker/timezone historical fixture is not the reviewed whole bytes')
    value = json.loads(raw)
    if (type(value) is not dict or type(value.get('schema')) is not int or value['schema'] != 1
            or value.get('kind') != 'historical-source-input-only'
            or value.get('baseCommit') != BASE_COMMIT or value.get('baseTree') != BASE_TREE
            or value.get('actualAndroidExecution') is not False or value.get('runtimeAcceptance') is not False
            or type(value.get('files')) is not dict or set(value['files']) != PATHS or len(PATHS) != 2):
        raise ValueError('Worker/timezone historical fixture identity differs')
    for row in value['files'].values():
        if (type(row) is not dict or set(row) != {'previousSha256', 'previousBytes', 'reviewedSha256', 'reviewedBytes', 'contextLines', 'deltas'}
                or any(type(row.get(key)) is not int or not 0 < row[key] <= 128 * 1024
                       for key in ('previousBytes', 'reviewedBytes'))
                or any(type(row.get(key)) is not str or re.fullmatch('[0-9a-f]{64}', row[key]) is None
                       for key in ('previousSha256', 'reviewedSha256'))
                or row['previousSha256'] == row['reviewedSha256']
                or type(row['contextLines']) is not int or not 3 <= row['contextLines'] <= 16
                or type(row['deltas']) is not list or not 0 < len(row['deltas']) <= 32):
            raise ValueError('Worker/timezone historical row is not bounded and exact')
        for index, delta in enumerate(row['deltas']):
            if (type(delta) is not dict or set(delta) != {'id', 'previous', 'current', 'previousSha256', 'currentSha256'}
                    or delta['id'] != 'context-%02d' % index
                    or any(type(delta[key]) is not str or not 0 < len(delta[key].encode('utf-8')) <= 16 * 1024
                           or _sha(delta[key].encode('utf-8')) != delta[key + 'Sha256']
                           for key in ('previous', 'current'))):
                raise ValueError('Worker/timezone historical delta differs')
    return value


def source_input(raw, relative):
    if type(raw) is not bytes or type(relative) is not str or relative not in PATHS:
        raise ValueError('Worker/timezone inverse requires exact complete bytes and an owned relative path')
    row = manifest()['files'][relative]
    digest = _sha(raw)
    if (digest, len(raw)) not in ((row['previousSha256'], row['previousBytes']),
                                  (row['reviewedSha256'], row['reviewedBytes'])):
        from cpu_source_compatibility import source_input as cpu_source_input
        raw = cpu_source_input(raw, relative)
        digest = _sha(raw)
    if digest == row['previousSha256'] and len(raw) == row['previousBytes']:
        return raw
    if digest != row['reviewedSha256'] or len(raw) != row['reviewedBytes']:
        raise ValueError('Worker/timezone inverse rejects unknown whole source bytes')
    for delta in reversed(row['deltas']):
        current, previous = delta['current'].encode('utf-8'), delta['previous'].encode('utf-8')
        if raw.count(current) != 1:
            raise ValueError('Worker/timezone inverse requires every exact contextual delta once')
        raw = raw.replace(current, previous, 1)
    if len(raw) != row['previousBytes'] or _sha(raw) != row['previousSha256']:
        raise ValueError('Worker/timezone inverse did not restore the complete original source')
    return raw
