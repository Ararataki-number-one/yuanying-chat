"""Exact reviewed46 source-input inverse before formal45 and historical guards.

Only explicit historical source assertions use this port. Runtime/behavior hosts
compile actual production bytes. Unknown files, fixtures, or whole sources fail.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DELTA_PATH = ROOT / 'tests/fixtures/experience46-source-deltas.json'
DELTA_SHA256 = 'd09e89773bac82f8fe7e5d7375967eafe72e20e55b014da79926d9f2bb1a1ef1'
BASE_COMMIT = 'e15147246ceff2e1ed2ffd9a18df1fd17b03ddee'
BASE_TREE = 'cbb37b32ad11ec52bc91216185a033bf1d475e08'
READING45_FIXTURE_SHA256 = '8d9fd8380a5d6337860989ad8ce95b0529773cdfa433ef090b229a8beb423f3c'


def manifest46():
    data = DELTA_PATH.read_bytes()
    if hashlib.sha256(data).hexdigest() != DELTA_SHA256:
        raise ValueError('Experience46 inverse fixture is not the exact reviewed bytes')
    manifest = json.loads(data)
    if manifest.get('schema') != 1 or manifest.get('baseCommit') != BASE_COMMIT or manifest.get('baseTree') != BASE_TREE:
        raise ValueError('Experience46 inverse has a foreign formal45 source identity')
    original45 = ROOT / 'tests/fixtures/reading45-restoration-source-deltas.json'
    if hashlib.sha256(original45.read_bytes()).hexdigest() != READING45_FIXTURE_SHA256:
        raise ValueError('Experience46 inverse cannot change the original45 fixture')
    return manifest


def experience46_source_bytes(raw, relative):
    row = manifest46()['files'].get(relative)
    if row is None:
        raise ValueError('Experience46 inverse does not cover this exact path')
    digest = hashlib.sha256(raw).hexdigest()
    if digest == row['previousSha256'] or digest in row['exactHistoricalSha256']:
        return raw
    if digest != row['reviewedSha256']:
        raise ValueError('Experience46 inverse rejects unknown whole source bytes')
    for delta in reversed(row['deltas']):
        current, previous = delta['current'].encode('utf-8'), delta['previous'].encode('utf-8')
        if not current or not previous or raw.count(current) != 1:
            raise ValueError('Experience46 inverse requires every exact reviewed contextual delta once')
        raw = raw.replace(current, previous, 1)
    if hashlib.sha256(raw).hexdigest() != row['previousSha256']:
        raise ValueError('Experience46 inverse did not restore the complete formal45 source')
    return raw
