"""Exact navigation-emulator successor for historical workflow inputs only."""
import functools
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = '.github/workflows/glass-release-validation.yml'
FIXTURE = ROOT / 'tests/fixtures/glass-emulator-navigation-source-deltas.json'
FIXTURE_SHA256 = '36d554088558659a711d03f9eafdc5a05cddb0d567c33fb6605f3edff0fbd306'
PREVIOUS_SHA256 = '11cdccbdfeb5e5871acfb62e29ae34465f657c887d9d4e38beaa550c76857cf0'
CURRENT_SHA256 = 'f5923379924340e1238797386f7e382300817e4838ad026a90147e6caa743a00'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def manifest():
    assert FIXTURE.is_file() and not FIXTURE.is_symlink() and FIXTURE.resolve() == FIXTURE.absolute()
    raw = FIXTURE.read_bytes()
    assert 0 < len(raw) <= 8192 and sha(raw) == FIXTURE_SHA256, 'Exact bounded navigation workflow fixture required'
    value = json.loads(raw)
    assert (type(value['schema']) is int and value['schema'] == 1
            and value['kind'] == 'historical-emulator-navigation-input-only'
            and value['path'] == PATH
            and value['publicBaselineCommit'] == '7402ead321ca74b9fbefeab32a1aaffb32832011'
            and value['publicBaselineTree'] == '2aaec06687b65d9511ace499528b6946dc1b8d53'
            and value['publicBaselineSha256'] == '686928c3060c06808068f2f43f54276f64eb54136ee112709f1d61a8b8aa171b'
            and value['previousDerivation'] == 'original-gradle-transport-fixture-forward-from-public-baseline'
            and (value['previousSha256'], value['previousBytes']) == (PREVIOUS_SHA256, 15629)
            and (value['reviewedSha256'], value['reviewedBytes']) == (CURRENT_SHA256, 16587)
            and value['actualAndroidExecution'] is False and value['runtimeAcceptance'] is False
            and len(value['deltas']) == 2), 'Navigation workflow scope or reviewed identity differs'
    return value


def source_before(raw):
    assert type(raw) is bytes and (len(raw), sha(raw)) == (16587, CURRENT_SHA256), 'Unknown complete navigation workflow'
    value = manifest()
    for delta in reversed(value['deltas']):
        current, previous = delta['current'].encode(), delta['previous'].encode()
        for name, literal in (('current', current), ('previous', previous)):
            assert 0 < len(literal) <= 32768 and (len(literal), sha(literal)) == (delta[name + 'Bytes'], delta[name + 'Sha256'])
        assert raw.count(current) == 1, 'Unique exact navigation workflow context required'
        raw = raw.replace(current, previous, 1)
    assert (len(raw), sha(raw)) == (15629, PREVIOUS_SHA256), 'Complete pre-navigation workflow did not restore'
    return raw


def historical_input(raw, relative):
    if type(raw) is bytes and type(relative) is str and relative == PATH and len(raw) == 16587 and sha(raw) == CURRENT_SHA256:
        return source_before(raw)
    return raw


def current_after_input(raw, relative):
    """Advance one exact retained comparison LHS; runtime YAML stays raw."""
    if not (type(raw) is bytes and type(relative) is str and relative == PATH
            and len(raw) == 15629 and sha(raw) == PREVIOUS_SHA256):
        return raw
    for delta in manifest()['deltas']:
        previous, current = delta['previous'].encode(), delta['current'].encode()
        assert 0 < len(previous) <= 32768 and 0 < len(current) <= 32768
        assert sha(previous) == delta['previousSha256'] and sha(current) == delta['currentSha256']
        assert raw.count(previous) == 1, 'Unique pre-navigation context required'
        raw = raw.replace(previous, current, 1)
    assert (len(raw), sha(raw)) == (16587, CURRENT_SHA256), 'Complete actual navigation workflow did not restore'
    return raw


def wrap_source_input(original):
    @functools.wraps(original)
    def historical_workflow(raw, relative):
        return original(historical_input(raw, relative), relative)
    return historical_workflow
