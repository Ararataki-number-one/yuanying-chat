"""Finite metadata inverse for the retained fixture's framework-root repair.

Actual device fixtures, compilers and behavior hosts always read current source.
This module serves only explicitly declared historical whole-source oracles.
"""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

ROOT = Path(__file__).resolve().parents[1]
BASE_COMMIT = '6ee06aced87581e52aa301431f8996ed46d666b8'
BASE_TREE = '19b74a878d2c238cdb209dd51d2fb66076057963'
DELTA_PATH = ROOT / 'tests/fixtures/profile-fixture-root-source-deltas.json'
DELTA_SHA256 = 'edad6886ab8867e8d76249de55f9ed23d1b664f830039eaf8e04caf9f9f19e1a'
MAX_FIXTURE_BYTES = 128 * 1024
MAX_SOURCE_BYTES = 256 * 1024
PATHS = frozenset((
    'tests/gecko/FingerprintFollowupIntegrationActivity.java',
    'tests/dual_browser_source_compatibility.py',
    'tests/profile_dual_browser_source_compatibility_test.py',
    'tests/profile_worker_timezone_source_compatibility_test.py',
    'tests/final_browser_source_compatibility.py',
))


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def manifest():
    if (DELTA_PATH.is_symlink() or not DELTA_PATH.is_file()
            or DELTA_PATH.resolve() != DELTA_PATH.absolute()):
        raise ValueError('Fixture-root metadata requires an ordinary pinned fixture')
    raw = DELTA_PATH.read_bytes()
    if not 0 < len(raw) <= MAX_FIXTURE_BYTES or _sha(raw) != DELTA_SHA256:
        raise ValueError('Fixture-root metadata fixture differs from the exact reviewed bytes')
    def pairs(items):
        result = {}
        for key, item in items:
            if key in result:
                raise ValueError('Duplicate fixture-root metadata key')
            result[key] = item
        return result
    def nonfinite(value):
        raise ValueError('Non-finite fixture-root metadata value')
    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)
    if (type(value) is not dict or set(value) != {'schema', 'kind', 'baseCommit', 'baseTree',
            'actualAndroidExecution', 'runtimeAcceptance', 'files'}
            or type(value.get('schema')) is not int or value['schema'] != 1
            or value.get('kind') != 'historical-source-input-only'
            or value.get('baseCommit') != BASE_COMMIT or value.get('baseTree') != BASE_TREE
            or value.get('actualAndroidExecution') is not False or value.get('runtimeAcceptance') is not False
            or type(value.get('files')) is not dict or set(value['files']) != PATHS or len(PATHS) != 5):
        raise ValueError('Fixture-root metadata scope or provenance differs')
    total = 0
    for row in value['files'].values():
        if (type(row) is not dict or set(row) != {'previousSha256', 'previousBytes', 'reviewedSha256',
                'reviewedBytes', 'contextLines', 'deltas'}
                or any(type(row.get(k)) is not int or not 0 < row[k] <= MAX_SOURCE_BYTES
                       for k in ('previousBytes', 'reviewedBytes'))
                or any(type(row.get(k)) is not str or re.fullmatch('[0-9a-f]{64}', row[k]) is None
                       for k in ('previousSha256', 'reviewedSha256'))
                or row['previousSha256'] == row['reviewedSha256']
                or type(row.get('contextLines')) is not int or row['contextLines'] != 3
                or type(row.get('deltas')) is not list or not 0 < len(row['deltas']) <= 8):
            raise ValueError('Fixture-root metadata row is not finite and exact')
        total += len(row['deltas'])
        for index, delta in enumerate(row['deltas']):
            if (type(delta) is not dict or set(delta) != {'id', 'previous', 'current',
                    'previousSha256', 'currentSha256'} or delta.get('id') != 'context-%02d' % index
                    or any(type(delta.get(k)) is not str or not 0 < len(delta[k].encode('utf-8')) <= 16 * 1024
                           or _sha(delta[k].encode('utf-8')) != delta.get(k+'Sha256')
                           for k in ('previous', 'current')) or delta['previous'] == delta['current']):
                raise ValueError('Fixture-root metadata context differs')
    if total != 7:
        raise ValueError('Fixture-root metadata context count differs')
    from connections_admission_metadata_compatibility import profile_manifest_input
    from resource_startup_source_compatibility import root_manifest_input
    return root_manifest_input(profile_manifest_input(value))


def _path(raw, relative):
    if type(raw) is not bytes or type(relative) is not str or not 0 < len(raw) <= MAX_SOURCE_BYTES:
        raise ValueError('Fixture-root metadata requires bounded complete bytes and a path string')
    path = PurePosixPath(relative)
    if (not relative or not path.parts or str(path) != relative or path.is_absolute() or '..' in path.parts
            or '\\' in relative or '\0' in relative
            or path.parts[0] not in ('app', 'tests', 'tools', '.github')):
        raise ValueError('Fixture-root metadata path is not canonical')


def source_input(raw, relative):
    """One exact owned image -> unique contextual inverse -> exact predecessor."""
    _path(raw, relative)
    if relative not in PATHS:
        raise ValueError('Fixture-root metadata rejects unowned source paths')
    row = manifest()['files'][relative]
    identity = (_sha(raw), len(raw))
    if identity == (row['previousSha256'], row['previousBytes']):
        return raw
    if identity != (row['reviewedSha256'], row['reviewedBytes']):
        raise ValueError('Fixture-root metadata rejects unknown complete source bytes')
    for delta in reversed(row['deltas']):
        current, previous = delta['current'].encode('utf-8'), delta['previous'].encode('utf-8')
        if raw.count(current) != 1:
            raise ValueError('Fixture-root metadata requires each exact context once')
        raw = raw.replace(current, previous, 1)
    if (_sha(raw), len(raw)) != (row['previousSha256'], row['previousBytes']):
        raise ValueError('Fixture-root metadata did not restore its exact complete predecessor')
    return raw


def historical_input(raw, relative):
    """Only declared historical reads; other canonical bytes remain unmodified."""
    _path(raw, relative)
    return source_input(raw, relative) if relative in PATHS else raw
