"""Two exact source inputs for retained diagnostic oracles, never execution.

Current workflows, Java and host producers remain ordinary raw-source readers.
Only the explicit diagnostic wrappers below invoke these finite byte inverses.
"""
import functools
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/glass-diagnostic-source-deltas.json'
FIXTURE_SHA256 = '8aae6519cefb08e232b6f33849a6b03bbba5e5b468a504c850ea8694a5f8acf5'
DISPLAY = 'tests/profile_display_sampling_gate_test.py'
NATIVE = 'tests/profile_native_setup_diagnostic11_test.py'
PREVIOUS = {
    DISPLAY: '2141a7360b32a13f6987fe71519abf502f1bc8855148627204205db8b444be47',
    NATIVE: '1e1fbe80f0e66ae29e40edc63c83d7fa1d9faf0343db5d6b91898ed24d97bc9f',
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def manifest():
    raw = FIXTURE.read_bytes()
    assert not FIXTURE.is_symlink() and len(raw) <= 16384 and sha(raw) == FIXTURE_SHA256, 'Exact bounded diagnostic source fixture required'
    value = json.loads(raw)
    assert type(value['schema']) is int and value['schema'] == 1
    assert value['baseCommit'] == '4363dbc04df80d5c82ba966248e47a3fd69cbcc8'
    assert value['baseTree'] == '08189ae748eb1045ff21af4253369ef17d6bdad3'
    assert set(value['files']) == set(PREVIOUS), 'Only two diagnostic source paths are owned'
    assert all(value['files'][path]['previousSha256'] == previous for path, previous in PREVIOUS.items())
    assert [len(value['files'][path]['deltas']) for path in (DISPLAY, NATIVE)] == [3, 1]
    return value


def source_input(raw, path):
    assert type(raw) is bytes and type(path) is str and path in PREVIOUS, 'Complete owned diagnostic source bytes required'
    row = manifest()['files'][path]
    assert 0 < len(raw) <= 65536 and (len(raw), sha(raw)) == (row['reviewedBytes'], row['reviewedSha256']), 'Unreviewed complete diagnostic source'
    for delta in reversed(row['deltas']):
        current, previous = delta['current'].encode(), delta['previous'].encode()
        for name, literal in (('current', current), ('previous', previous)):
            assert 0 < len(literal) <= 32768 and (len(literal), sha(literal)) == (delta[name + 'Bytes'], delta[name + 'Sha256'])
        assert raw.count(current) == 1, 'Missing, duplicated or moved exact diagnostic source hunk'
        raw = raw.replace(current, previous, 1)
    assert (len(raw), sha(raw)) == (row['previousBytes'], PREVIOUS[path]), 'Entire original diagnostic source did not restore'
    return raw


def historical_input(raw, path):
    """Recognize only a complete after-image; all else faces the original guard."""
    assert type(path) is str and path in PREVIOUS
    if type(raw) is bytes and 0 < len(raw) <= 65536 and sha(raw) == manifest()['files'][path]['reviewedSha256']:
        return source_input(raw, path)
    return raw


def wrap_normalizers_restore(original):
    @functools.wraps(original)
    def historical_normalizers(cls, raw):
        return original(cls, historical_input(raw, DISPLAY))
    return historical_normalizers


def wrap_native_source_restore(original):
    @functools.wraps(original)
    def historical_native(raw):
        return original(historical_input(raw, NATIVE))
    return historical_native
