"""Finite dual-browser input inverse for retained historical source oracles.

Actual production/device/behavior hosts never call this module. The complete
reviewed source is identified before reversing contextual edits back to the real
2.1.0 commit. Unknown files, edits, excerpts and fixture bytes always fail.
"""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
BASE_COMMIT = '72e3bcac55285fea483e612ba4481f7e073a5422'
BASE_TREE = '17901d0d1d5eccc2efff6b7c80564a85426a0ca4'
DELTA_PATH = ROOT / 'tests/fixtures/dual-browser-source-deltas.json'
DELTA_SHA256 = 'b593b0db2b56b5a5d8143a920fbd15858dafbab21d1cdaf90ca2a5ba164c9933'
MAX_FIXTURE_BYTES = 512 * 1024
PATHS = frozenset((
    'app/src/main/java/local/pocketchat/ChatSession.java',
    'app/src/main/java/local/pocketchat/GeckoWebView.java',
    'tests/gecko/GeckoIntegrationTestActivity.java',
    'tests/gecko/FingerprintFollowupIntegrationActivity.java',
    'tests/gecko/GeckoPerformanceIntegrationActivity.java',
    'tests/experience46_source_compatibility.py',
    'tests/profile_experience46_source_compatibility_test.py',
    'tests/event_journal_source_compatibility.py',
    'tests/profile_event_journal_source_compatibility_test.py',
))


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def manifest():
    raw = DELTA_PATH.read_bytes()
    if not 0 < len(raw) <= MAX_FIXTURE_BYTES or _sha(raw) != DELTA_SHA256:
        raise ValueError('Dual-browser historical fixture is not the reviewed whole bytes')
    value = json.loads(raw)
    if (type(value.get('schema')) is not int or value['schema'] != 1
            or value.get('kind') != 'historical-source-input-only'
            or value.get('baseCommit') != BASE_COMMIT or value.get('baseTree') != BASE_TREE
            or value.get('actualAndroidExecution') is not False or value.get('runtimeAcceptance') is not False
            or type(value.get('files')) is not dict or set(value['files']) != PATHS or len(PATHS) != 9):
        raise ValueError('Dual-browser historical fixture identity differs')
    for row in value['files'].values():
        if (set(row) != {'previousSha256', 'previousBytes', 'reviewedSha256', 'reviewedBytes', 'contextLines', 'deltas'}
                or any(type(row.get(key)) is not int or not 0 < row[key] <= 256 * 1024
                       for key in ('previousBytes', 'reviewedBytes'))
                or any(type(row.get(key)) is not str or re.fullmatch('[0-9a-f]{64}', row[key]) is None
                       for key in ('previousSha256', 'reviewedSha256'))
                or row['previousSha256'] == row['reviewedSha256']
                or type(row['contextLines']) is not int or not 3 <= row['contextLines'] <= 16
                or type(row['deltas']) is not list or not 0 < len(row['deltas']) <= 64):
            raise ValueError('Dual-browser historical row is not bounded and exact')
        for index, delta in enumerate(row['deltas']):
            if (set(delta) != {'id', 'previous', 'current', 'previousSha256', 'currentSha256'}
                    or delta['id'] != 'context-%02d' % index
                    or any(type(delta[key]) is not str or not 0 < len(delta[key].encode('utf-8')) <= 96 * 1024
                           or _sha(delta[key].encode('utf-8')) != delta[key + 'Sha256']
                           for key in ('previous', 'current'))):
                raise ValueError('Dual-browser historical delta differs')
    return value


def source_input(raw, relative):
    if type(raw) is not bytes or type(relative) is not str or relative not in PATHS:
        raise ValueError('Dual-browser inverse requires exact complete bytes and an owned relative path')
    row = manifest()['files'][relative]
    digest = _sha(raw)
    if (digest, len(raw)) not in ((row['previousSha256'], row['previousBytes']),
                                  (row['reviewedSha256'], row['reviewedBytes'])):
        from worker_timezone_source_compatibility import PATHS as worker_paths, source_input as worker_source_input
        if relative in worker_paths:
            raw = worker_source_input(raw, relative)
            digest = _sha(raw)
    if digest == row['previousSha256'] and len(raw) == row['previousBytes']:
        return raw
    if digest != row['reviewedSha256'] or len(raw) != row['reviewedBytes']:
        raise ValueError('Dual-browser inverse rejects unknown whole source bytes')
    for delta in reversed(row['deltas']):
        current, previous = delta['current'].encode('utf-8'), delta['previous'].encode('utf-8')
        if raw.count(current) != 1:
            raise ValueError('Dual-browser inverse requires every exact contextual delta once')
        raw = raw.replace(current, previous, 1)
    if len(raw) != row['previousBytes'] or _sha(raw) != row['previousSha256']:
        raise ValueError('Dual-browser inverse did not restore the complete original source')
    return raw

# Fixture storage roots affect historical metadata only; all runtime reads stay raw.
import importlib.util as _fixture_util
_fixture_spec = _fixture_util.spec_from_file_location('_fixture_context_metadata', Path(__file__).with_name('fixture_context_source_compatibility.py'))
_fixture_input = _fixture_util.module_from_spec(_fixture_spec)
_fixture_spec.loader.exec_module(_fixture_input)
source_input = _fixture_input.wrap_bytes(source_input)
