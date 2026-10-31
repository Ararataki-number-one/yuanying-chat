"""Exact test-input inverse of the reviewed45 restoration delta.

This is used only by retained historical whole-source guards. Functional hosts
compile the actual production files. Unknown source/fixture bytes remain errors.
"""
import hashlib
import json
from pathlib import Path
from experience46_source_compatibility import experience46_source_bytes

ROOT = Path(__file__).resolve().parents[1]
DELTA_PATH = ROOT / 'tests/fixtures/reading45-restoration-source-deltas.json'
DELTA_SHA256 = '8d9fd8380a5d6337860989ad8ce95b0529773cdfa433ef090b229a8beb423f3c'
BASE_COMMIT = 'f263613422632740caed76505a20cb6696905003'
BASE_TREE = 'fa5fa7aea024e8225781c7da651c740ff7a4a59d'


def reading45_source_bytes(raw, relative):
    data = DELTA_PATH.read_bytes()
    if hashlib.sha256(data).hexdigest() != DELTA_SHA256:
        raise ValueError('Reading45 inverse fixture is not the reviewed whole bytes')
    manifest = json.loads(data)
    if manifest['baseCommit'] != BASE_COMMIT or manifest['baseTree'] != BASE_TREE:
        raise ValueError('Reading45 inverse has a foreign source identity')
    row = manifest['files'].get(relative)
    if row is None:
        raise ValueError('Reading45 inverse does not cover this path')
    raw = experience46_source_bytes(raw, relative)
    digest = hashlib.sha256(raw).hexdigest()
    if digest == row['previousSha256']:
        return raw
    if digest != row['reviewedSha256']:
        raise ValueError('Reading45 inverse rejects unknown whole source bytes')
    for delta in reversed(row['deltas']):
        current = delta['current'].encode('utf-8')
        previous = delta['previous'].encode('utf-8')
        if raw.count(current) != 1:
            raise ValueError('Reading45 inverse requires each exact reviewed delta once')
        raw = raw.replace(current, previous, 1)
    if hashlib.sha256(raw).hexdigest() != row['previousSha256']:
        raise ValueError('Reading45 inverse did not restore the entire original source')
    return raw
