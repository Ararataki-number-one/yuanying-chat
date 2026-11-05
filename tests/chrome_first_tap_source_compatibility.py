"""Exact historical source-input inverse for first-tap preparation.

Only the retained header/HOME source guard uses this port. Current Android and
host first-tap workloads execute the actual new readiness helper and runner.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/chrome-first-tap-source-deltas.json'
FIXTURE_SHA256 = '2c31cb3286d88a91079fb33cef1f27b9c81f7cefda6fbb1c7bc6537e6ca79795'
BASE_COMMIT = 'd10843d321f426cb66a3fef7a232adf52fd0d15e'
PATHS = frozenset(('tests/gecko/run_chrome_collapse.py',
                   'tests/profile_chrome_home_resume_test.py',
                   'tools/gecko/chrome_header_readiness.py'))


def reject():
    # Retain the original guard's public failure contract for old counterfeits.
    raise ValueError('Unreviewed header readiness change')


def manifest():
    raw = FIXTURE.read_bytes()
    if len(raw) > 32768 or hashlib.sha256(raw).hexdigest() != FIXTURE_SHA256:
        reject()
    value = json.loads(raw)
    if type(value.get('schema')) is not int or value['schema'] != 1 or value.get('baseCommit') != BASE_COMMIT or set(value.get('files', {})) != PATHS:
        reject()
    return value


def source_input(raw, relative):
    if type(raw) is not bytes or type(relative) is not str or relative not in PATHS:
        reject()
    row = manifest()['files'][relative]
    current = (hashlib.sha256(raw).hexdigest(), len(raw))
    if current == (row['previousSha256'], row['previousBytes']):
        return raw
    if current != (row['reviewedSha256'], row['reviewedBytes']):
        reject()
    for delta in reversed(row['deltas']):
        before, after = delta['previous'].encode('utf-8'), delta['current'].encode('utf-8')
        if (not before or not after or raw.count(after) != 1
                or hashlib.sha256(before).hexdigest() != delta['previousSha256']
                or hashlib.sha256(after).hexdigest() != delta['currentSha256']):
            reject()
        raw = raw.replace(after, before, 1)
    if (hashlib.sha256(raw).hexdigest(), len(raw)) != (row['previousSha256'], row['previousBytes']):
        reject()
    return raw
