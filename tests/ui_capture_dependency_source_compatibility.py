"""One complete historical capture-host after-view; execution stays current."""
import copy
import functools
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = 'tests/gecko_ui_visual_capture_test.py'
FIXTURE = ROOT / 'tests/fixtures/ui-capture-dependency-source-deltas.json'
FIXTURE_SHA256 = 'db7f8697060729e82652b2d1cd961badae90623973588279f4ca1e8228b2ea37'
CHECKPOINT = ROOT / 'tests/fixtures/ui-checkpoint-source-deltas.json'
CHECKPOINT_SHA256 = 'efaa8da45f2697d95a0d514be8cd404260eed1f59595dd4c08b5c2ee8f37d22e'
BEFORE = (40357, '4ec6b7535d37119d6674afc5090b33d8c26af91abaa5d53ecb2a52488e911f6a')
AFTER = (41231, 'c8d5197124da49526f18f25f1c0f8d40672898a693334b8edf4772cf4d7c2dd0')
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def manifest():
    assert FIXTURE == ROOT / 'tests/fixtures/ui-capture-dependency-source-deltas.json'
    assert not FIXTURE.is_symlink() and FIXTURE.is_file()
    raw = FIXTURE.read_bytes()
    assert 0 < len(raw) <= 32768 and sha(raw) == FIXTURE_SHA256, 'Exact capture dependency metadata required'
    def unique(items):
        result = {}
        for key, value in items:
            assert key not in result, 'Duplicate capture dependency metadata'
            result[key] = value
        return result
    value = json.loads(raw, object_pairs_hook=unique)
    assert set(value) == {'schema', 'kind', 'actualAndroidExecution', 'runtimeAcceptance', 'path',
        'previousCommit', 'previousTree', 'checkpointFixtureSha256', 'previousBytes', 'previousSha256',
        'currentBytes', 'currentSha256', 'delta', 'originalRow', 'currentRow'}
    assert type(value['schema']) is int and value['schema'] == 1
    assert value['kind'] == 'historical-capture-dependency-only' and value['path'] == PATH
    assert value['actualAndroidExecution'] is False and value['runtimeAcceptance'] is False
    assert (value['previousCommit'], value['previousTree']) == (
        '9a5a9eeb3ef44d10c44e6e4fe580b5347c197367', '3724d45aabacf3af7c03e2ee8072bd32c3a516a3')
    assert (value['previousBytes'], value['previousSha256']) == BEFORE
    assert (value['currentBytes'], value['currentSha256']) == AFTER
    assert value['checkpointFixtureSha256'] == CHECKPOINT_SHA256
    assert not CHECKPOINT.is_symlink() and sha(CHECKPOINT.read_bytes()) == CHECKPOINT_SHA256
    original = json.loads(CHECKPOINT.read_bytes())['files'][PATH]
    assert value['originalRow'] == original
    expected = copy.deepcopy(original)
    expected.update(reviewedBytes=AFTER[0], reviewedSha256=AFTER[1])
    expected['deltas'].append(value['delta'])
    assert value['currentRow'] == expected and len(expected['deltas']) == 3
    delta = value['delta']
    assert set(delta) == {'previous', 'current', 'previousBytes', 'currentBytes', 'previousSha256', 'currentSha256'}
    for name in ('previous', 'current'):
        assert type(delta[name]) is str
        literal = delta[name].encode()
        assert 0 < len(literal) <= 4096
        assert (len(literal), sha(literal)) == (delta[name+'Bytes'], delta[name+'Sha256'])
    assert delta['previous'] != delta['current']
    return value


def source_input(raw):
    assert type(raw) is bytes, 'Complete capture dependency source bytes required'
    value = manifest()
    if (len(raw), sha(raw)) == BEFORE:
        return raw
    assert (len(raw), sha(raw)) == AFTER, 'Unreviewed complete capture dependency source'
    delta = value['delta']
    current, previous = delta['current'].encode(), delta['previous'].encode()
    assert raw.count(current) == 1, 'One positioned capture dependency hunk required'
    result = raw.replace(current, previous, 1)
    assert (len(result), sha(result)) == BEFORE, 'Entire previous capture host did not restore'
    return result


def wrap_checkpoint_manifest(original):
    @functools.wraps(original)
    def current_capture_metadata():
        value = original()
        cfg = manifest()
        assert value['files'][PATH] == cfg['originalRow'], 'Exact original capture row required'
        result = copy.deepcopy(value)
        result['files'][PATH] = copy.deepcopy(cfg['currentRow'])
        return result
    return current_capture_metadata
