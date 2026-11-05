"""Bounded IP-timezone source inputs for retained historical oracles only.

No runtime, device, application or behavior host imports this module. Every
complete input is identified before any inverse; unknown edits never fall back.
"""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_BEFORE = '802e56cc7ca11467ce960dc3608b7df5d7db2e40'
PRODUCTION_TREE = '2b470ed7d2f9445c5770107b5ef7d1a8ae0ebfc6'
PORTS_BEFORE = '972b7767300587af98b3f4a2088a44dd30af8098'
PORTS_TREE = '7da3a44c2b9c1f2d85623ac908a23154144ea045'
DELTA_PATH = ROOT / 'tests/fixtures/ip-timezone-source-deltas.json'
DELTA_SHA256 = '2a84a6ac4cb8246ea633d314bbcc9b75b8ab9e180507e6a7017533519106c0bb'
MAX_FIXTURE_BYTES = 512 * 1024
MAX_SOURCE_BYTES = 256 * 1024
PRODUCER_PATHS = frozenset((
    'app/src/main/java/local/pocketchat/GeckoWebView.java',
    'tests/profile_native_protection_test.py',
))
PORT_PATHS = frozenset((
    'tests/phase1_context_fix_source_compatibility.py',
    'tests/worker_timezone_host_source_compatibility.py',
    'tests/profile_phase1_context_fix_source_compatibility_test.py',
    'tests/profile_worker_timezone_host_source_compatibility_test.py',
    'tests/profile_page_bridge_budget_source_compatibility_test.py',
))
PATHS = PRODUCER_PATHS | PORT_PATHS


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def manifest():
    raw = DELTA_PATH.read_bytes()
    if not 0 < len(raw) <= MAX_FIXTURE_BYTES or _sha(raw) != DELTA_SHA256:
        raise ValueError('IP timezone historical fixture is not the exact reviewed bytes')
    def pairs(items):
        result = {}
        for key, item in items:
            if key in result:
                raise ValueError('Duplicate IP historical fixture key')
            result[key] = item
        return result
    def constant(value):
        raise ValueError('Non-finite IP historical fixture value')
    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    if (type(value) is not dict or set(value) != {'schema', 'kind', 'actualAndroidExecution', 'runtimeAcceptance', 'files'}
            or type(value.get('schema')) is not int or value['schema'] != 1
            or value.get('kind') != 'historical-source-input-only'
            or value.get('actualAndroidExecution') is not False or value.get('runtimeAcceptance') is not False
            or type(value.get('files')) is not dict or set(value['files']) != PATHS or len(PATHS) != 7):
        raise ValueError('IP timezone historical fixture identity differs')
    contexts = 0
    for relative, row in value['files'].items():
        predecessor = (PRODUCTION_BEFORE, PRODUCTION_TREE) if relative in PRODUCER_PATHS else (PORTS_BEFORE, PORTS_TREE)
        if (type(row) is not dict or set(row) != {'previousCommit', 'previousTree', 'previousSha256', 'previousBytes', 'reviewedSha256', 'reviewedBytes', 'contextLines', 'deltas'}
                or (row.get('previousCommit'), row.get('previousTree')) != predecessor
                or any(type(row.get(k)) is not int or not 0 < row[k] <= MAX_SOURCE_BYTES for k in ('previousBytes', 'reviewedBytes'))
                or any(type(row.get(k)) is not str or re.fullmatch('[0-9a-f]{64}', row[k]) is None for k in ('previousSha256', 'reviewedSha256'))
                or row['previousSha256'] == row['reviewedSha256']
                or type(row.get('contextLines')) is not int or not 3 <= row['contextLines'] <= 16
                or type(row.get('deltas')) is not list or not 0 < len(row['deltas']) <= 64):
            raise ValueError('IP timezone historical row is not exact and bounded')
        contexts += len(row['deltas'])
        for index, delta in enumerate(row['deltas']):
            if (type(delta) is not dict or set(delta) != {'id', 'previous', 'current', 'previousSha256', 'currentSha256'}
                    or delta.get('id') != 'context-%02d' % index
                    or any(type(delta.get(k)) is not str or not 0 < len(delta[k].encode('utf-8')) <= 32 * 1024
                           or _sha(delta[k].encode('utf-8')) != delta.get(k + 'Sha256') for k in ('previous', 'current'))
                    or delta['previous'] == delta['current']):
                raise ValueError('IP timezone historical context differs')
    if not 0 < contexts <= 128:
        raise ValueError('IP timezone historical contexts exceed the finite scope')
    return value


def source_input(raw, relative):
    if type(raw) is not bytes or type(relative) is not str or relative not in PATHS:
        raise ValueError('IP timezone inverse requires exact complete bytes and an owned relative path')
    row = manifest()['files'][relative]
    digest = _sha(raw)
    if (digest, len(raw)) == (row['previousSha256'], row['previousBytes']):
        return raw
    if (digest, len(raw)) != (row['reviewedSha256'], row['reviewedBytes']):
        from final_browser_source_compatibility import ip_input
        raw = ip_input(raw, relative)
        digest = _sha(raw)
    if (digest, len(raw)) != (row['reviewedSha256'], row['reviewedBytes']):
        raise ValueError('IP timezone inverse rejects unknown whole source bytes')
    for delta in reversed(row['deltas']):
        current, previous = delta['current'].encode('utf-8'), delta['previous'].encode('utf-8')
        if raw.count(current) != 1:
            raise ValueError('IP timezone inverse requires every unique exact contextual edit')
        raw = raw.replace(current, previous, 1)
    if (_sha(raw), len(raw)) != (row['previousSha256'], row['previousBytes']):
        raise ValueError('IP timezone inverse did not restore the full real predecessor')
    return raw


def historical_read(relative):
    """Read real non-owned source bytes; inverse only explicitly owned images."""
    if type(relative) is not str:
        raise ValueError('Historical read requires a canonical source-relative string')
    path = PurePosixPath(relative)
    if (not relative or str(path) != relative or path.is_absolute() or '..' in path.parts
            or '\\' in relative or '\0' in relative or path.parts[0] not in ('app', 'tests', 'tools', '.github')):
        raise ValueError('Historical read rejects unsafe source paths')
    source = ROOT / relative
    if source.is_symlink() or not source.is_file() or source.resolve() != source.absolute():
        raise ValueError('Historical read requires an ordinary source file')
    raw = source.read_bytes()
    if relative in PATHS:
        return source_input(raw, relative)
    from final_browser_source_compatibility import metadata_input
    return metadata_input(raw, relative)
