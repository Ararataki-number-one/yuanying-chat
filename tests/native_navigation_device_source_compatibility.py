"""Exact C11 navigation inputs for retained historical assertions only.

The device runner and all runtime/behavior producers execute current raw bytes.
The original journal JSON and trace/oracle functions remain unchanged.
"""
import ast
import copy
import functools
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = 'tests/gecko/run_device.py'
FIXTURE = ROOT / 'tests/fixtures/native-navigation-device-source-deltas.json'
FIXTURE_SHA256 = '1f3429c07306d37bdf5ded8180a8c0178248372c800efe1ca9e20a2a3ee77cd4'
PRIOR_SHA256 = '18340d331bc78f1e8033bad4f4de2399a4b3bd9c417214e87551f8967cfe5474'
CURRENT_SHA256 = '9ce3ca89f60c8b6870316dd0fbba8fa60b1b85c94ced22cbb667c8fde0feb5ac'
JOURNAL_SHA256 = '13620b58a536ebe4e0b822cd5b6ea11b9656cfdb83f2e18ee8c90ee0fa3c4254'
MAX_SOURCE_BYTES = 131072


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def reject():
    raise ValueError('Unreviewed complete native-navigation device comparison input')


def _unique(items):
    value = {}
    for key, item in items:
        if key in value:
            reject()
        value[key] = item
    return value


def _nonfinite(value):
    reject()


def _deltas(rows, count):
    if type(rows) is not list or len(rows) != count:
        reject()
    for index, row in enumerate(rows):
        if (type(row) is not dict or set(row) != {'id', 'previous', 'current', 'previousSha256', 'currentSha256'}
                or row['id'] != str(index + 1)):
            reject()
        for name in ('previous', 'current'):
            literal = row[name]
            if type(literal) is not str or not 0 < len(literal.encode()) <= 32768 or sha(literal.encode()) != row[name+'Sha256']:
                reject()
        if row['previous'] == row['current']:
            reject()


def manifest():
    expected = ROOT / 'tests/fixtures/native-navigation-device-source-deltas.json'
    if FIXTURE != expected or FIXTURE.is_symlink() or not FIXTURE.is_file() or FIXTURE.resolve() != expected.absolute():
        reject()
    raw = FIXTURE.read_bytes()
    if not 0 < len(raw) <= MAX_SOURCE_BYTES or sha(raw) != FIXTURE_SHA256:
        reject()
    value = json.loads(raw, object_pairs_hook=_unique, parse_constant=_nonfinite)
    if (type(value) is not dict or set(value) != {'schema', 'kind', 'actualAndroidExecution', 'runtimeAcceptance', 'path',
            'legacyJournalFixtureSha256', 'legacyJournalFixtureBytes', 'legacyJournalBaseCommit', 'priorCommit',
            'priorBytes', 'priorSha256', 'currentBytes', 'currentSha256', 'priorAstSha256', 'currentAstSha256', 'deltas', 'journalRow', 'journalHelper'}
            or type(value['schema']) is not int or value['schema'] != 1
            or value['kind'] != 'historical-native-navigation-device-input-only'
            or value['actualAndroidExecution'] is not False or value['runtimeAcceptance'] is not False
            or value['path'] != RUNNER
            or value['legacyJournalFixtureSha256'] != JOURNAL_SHA256
            or value['legacyJournalBaseCommit'] != '03d0c4ace70942a3f6899daffac086cc6682885e'
            or value['priorCommit'] != '06a802663075664b75aa9d19184d9c02b6bab7c9'
            or (value['priorBytes'], value['priorSha256']) != (92698, PRIOR_SHA256)
            or (value['currentBytes'], value['currentSha256']) != (93282, CURRENT_SHA256)):
        reject()
    legacy = (ROOT / 'tests/fixtures/event-journal-source-deltas.json').read_bytes()
    if len(legacy) != value['legacyJournalFixtureBytes'] or sha(legacy) != JOURNAL_SHA256:
        reject()
    _deltas(value['deltas'], 2)
    row = value['journalRow']
    if (type(row) is not dict or set(row) != {'previousSha256', 'previousBytes', 'reviewedSha256', 'reviewedBytes', 'deltas'}
            or (row['previousBytes'], row['previousSha256']) != (89703, '65b5c56e3576f645a10d6f2b5a69147e2904601641d56e4a9ed31de246b0a103')
            or (row['reviewedBytes'], row['reviewedSha256']) != (93282, CURRENT_SHA256)):
        reject()
    _deltas(row['deltas'], 3)
    helper = value['journalHelper']
    if (type(helper) is not dict or set(helper) != {'path', 'previousCommit', 'previousBytes', 'previousSha256', 'currentBytes', 'currentSha256', 'deltas'}
            or helper['path'] != 'tests/event_journal_source_compatibility.py'
            or helper['previousCommit'] != '06a802663075664b75aa9d19184d9c02b6bab7c9'
            or (helper['previousBytes'], helper['previousSha256']) != (5971, 'b35122f03dca997a2b5e3f25675371ec4f8f83d77e5a8ca2fbac7d40079fde31')
            or (helper['currentBytes'], helper['currentSha256']) != (6536, '16f44c6a6896513672ee260c2a18fed174c74bc6e9d19cded2e223bf09b81abd')):
        reject()
    _deltas(helper['deltas'], 1)
    return value


def comparison_input(raw, *, formatted=False):
    """Restore only the actual two navigation hunks before the old trace port."""
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_SOURCE_BYTES or type(formatted) is not bool:
        reject()
    value = manifest()
    exact = (len(raw), sha(raw)) == (value['currentBytes'], CURRENT_SHA256)
    if not exact:
        if not formatted:
            reject()
        try:
            current_ast = sha(ast.dump(ast.parse(raw), include_attributes=False).encode())
        except (SyntaxError, UnicodeError, ValueError):
            reject()
        if current_ast != value['currentAstSha256']:
            reject()
    for delta in reversed(value['deltas']):
        current, previous = delta['current'].encode(), delta['previous'].encode()
        if raw.count(current) != 1:
            reject()
        raw = raw.replace(current, previous, 1)
    if exact:
        if (len(raw), sha(raw)) != (value['priorBytes'], PRIOR_SHA256):
            reject()
    elif sha(ast.dump(ast.parse(raw), include_attributes=False).encode()) != value['priorAstSha256']:
        reject()
    return raw


def wrap_journal_manifest(original):
    @functools.wraps(original)
    def current_manifest():
        # Validate the untouched original JSON first. Only the private current
        # row is overlaid; every historical before and other source row stays.
        old = original()
        value = manifest()
        row = old['files'][RUNNER]
        if (old['baseCommit'] != value['legacyJournalBaseCommit']
                or (row['reviewedBytes'], row['reviewedSha256']) != (92698, PRIOR_SHA256)
                or len(row['deltas']) != 3):
            reject()
        result = copy.deepcopy(old)
        result['files'][RUNNER] = copy.deepcopy(value['journalRow'])
        return result
    return current_manifest


def journal_helper_input(raw):
    """One exact EOF binding inverse before existing historical helper guards."""
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_SOURCE_BYTES:
        reject()
    value = manifest()['journalHelper']
    identity = (len(raw), sha(raw))
    if identity == (value['previousBytes'], value['previousSha256']):
        return raw
    if identity != (value['currentBytes'], value['currentSha256']):
        reject()
    delta = value['deltas'][0]
    current, previous = delta['current'].encode(), delta['previous'].encode()
    if raw.count(current) != 1:
        reject()
    result = raw.replace(current, previous, 1)
    if (len(result), sha(result)) != (value['previousBytes'], value['previousSha256']):
        reject()
    return result


def wrap_fixture_root_history(original):
    @functools.wraps(original)
    def journal_history(raw, relative):
        if relative == 'tests/event_journal_source_compatibility.py':
            raw = journal_helper_input(raw)
        return original(raw, relative)
    return journal_history
