"""One exact empty preparation Activity image for historical assertions only.

The actual Java file, selected-source receipts and compiler inputs remain raw.
"""
import functools
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTIVITY = 'tests/gecko/UiVisualIntegrationActivity.java'
FIXTURE = ROOT / 'tests/fixtures/ui-preparation-source-deltas.json'
FIXTURE_SHA256 = '6c7d8304c1b003b633d3a0d1d2adafa16449099a884531af8cc302c12562cf3a'
PREVIOUS_SHA256 = '04f629d6053d1fc62bdddd590c4b405ddff2d564fd4dc3211332c849da0a4366'
CURRENT_SHA256 = 'f48e1f21ac5e68c992f14afd823410a4332dffa83a459b18d084a2ccf494b65b'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _unique(items):
    value = {}
    for key, item in items:
        assert key not in value, 'Duplicate preparation source metadata'
        value[key] = item
    return value


def _nonfinite(value):
    raise AssertionError('Nonfinite preparation source metadata')


def manifest():
    expected = ROOT / 'tests/fixtures/ui-preparation-source-deltas.json'
    assert FIXTURE == expected and not FIXTURE.is_symlink() and FIXTURE.is_file() and FIXTURE.resolve() == expected.absolute()
    raw = FIXTURE.read_bytes()
    assert 0 < len(raw) <= 16384 and sha(raw) == FIXTURE_SHA256, 'Exact bounded preparation source metadata required'
    value = json.loads(raw, object_pairs_hook=_unique, parse_constant=_nonfinite)
    assert set(value) == {'schema', 'kind', 'baseCommit', 'baseTree', 'path', 'previousBlob', 'previousSha256', 'previousBytes',
                          'reviewedSha256', 'reviewedBytes', 'actualAndroidExecution', 'runtimeAcceptance', 'deltas',
                          'navigationPreviousContext', 'navigationCurrentContext'}
    assert type(value['schema']) is int and value['schema'] == 1 and value['kind'] == 'historical-ui-preparation-source-input-only'
    assert (value['baseCommit'], value['baseTree'], value['previousBlob']) == (
        '4363dbc04df80d5c82ba966248e47a3fd69cbcc8', '08189ae748eb1045ff21af4253369ef17d6bdad3', 'be0704e74cc2f106dc1c765c909cf17c33e6f0dc')
    assert value['path'] == ACTIVITY and value['actualAndroidExecution'] is False and value['runtimeAcceptance'] is False
    assert type(value['previousBytes']) is int and type(value['reviewedBytes']) is int
    assert (value['previousBytes'], value['previousSha256']) == (13373, PREVIOUS_SHA256)
    assert (value['reviewedBytes'], value['reviewedSha256']) == (13638, CURRENT_SHA256)
    assert type(value['deltas']) is list and len(value['deltas']) == 1
    assert all(type(value[key]) is str and 0 < len(value[key].encode()) <= 32768
               for key in ('navigationPreviousContext', 'navigationCurrentContext'))
    for delta in value['deltas']:
        assert type(delta) is dict and set(delta) == {'previous', 'current', 'previousBytes', 'currentBytes', 'previousSha256', 'currentSha256'}
        for name in ('previous', 'current'):
            assert type(delta[name]) is str and type(delta[name + 'Bytes']) is int
            literal = delta[name].encode()
            assert 0 < len(literal) <= 32768 and (len(literal), sha(literal)) == (delta[name + 'Bytes'], delta[name + 'Sha256'])
        assert delta['previous'] != delta['current']
    return value


def source_input(raw, path):
    assert type(raw) is bytes and type(path) is str and path == ACTIVITY, 'Complete owned preparation source bytes required'
    value = manifest()
    assert (len(raw), sha(raw)) == (13638, CURRENT_SHA256), 'Unreviewed complete preparation source'
    for delta in reversed(value['deltas']):
        current, previous = delta['current'].encode(), delta['previous'].encode()
        assert raw.count(current) == 1, 'Missing, repeated or moved preparation context'
        raw = raw.replace(current, previous, 1)
    assert (len(raw), sha(raw)) == (13373, PREVIOUS_SHA256), 'Entire actual navigation predecessor did not restore'
    return raw


def historical_input(raw, path=ACTIVITY):
    if (type(raw) is bytes and type(path) is str and path == ACTIVITY
            and len(raw) == 13638 and sha(raw) == CURRENT_SHA256):
        return source_input(raw, path)
    return raw


def historical_report_sha(raw, reported_sha):
    assert type(raw) is bytes and type(reported_sha) is str and sha(raw) == reported_sha, 'Actual raw preparation receipt differs'
    return sha(historical_input(raw))


def actual_navigation_context(raw, context):
    """Retain the same old hunk while mutating its complete actual new span."""
    assert type(context) is bytes
    previous = source_input(raw, ACTIVITY)
    value = manifest()
    if context == value['navigationPreviousContext'].encode():
        assert previous.count(context) == 1
        context = value['navigationCurrentContext'].encode()
    assert raw.count(context) == 1, 'Unique actual navigation context required'
    return context


def wrap_source(original):
    @functools.wraps(original)
    def preparation_source(raw, path):
        return original(historical_input(raw, path), path)
    return preparation_source
