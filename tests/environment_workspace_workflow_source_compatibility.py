"""One reviewed environment-capture workflow inverse for source oracles only.

The actual workflow, capture scripts and host producers always read current
bytes. This finite adapter restores the exact upstream workflow before the
unchanged glass/host historical assertions run.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = '.github/workflows/profile-upgrade-checks.yml'
FIXTURE = ROOT / 'tests/fixtures/environment-workspace-workflow-source-deltas.json'
FIXTURE_SHA256 = '9de8ccbce4863b4d302ae45f4b7aff95474fb04e756efbf12158ac0a3f76eb37'
PREVIOUS_COMMIT = '7402ead321ca74b9fbefeab32a1aaffb32832011'
PREVIOUS_TREE = '2aaec06687b65d9511ace499528b6946dc1b8d53'
PREVIOUS_BYTES = 21727
PREVIOUS_SHA256 = '37ec53f065fa4572b8d59c7d4138dc170267f73911c46b5d4db0855dfe024699'
CURRENT_BYTES = 22906
CURRENT_SHA256 = 'b8cc066071862d11db66fd9064f11f824667e53b4af210a707715de90d4cc988'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def manifest():
    raw = FIXTURE.read_bytes()
    assert not FIXTURE.is_symlink() and 0 < len(raw) <= 16384 and sha(raw) == FIXTURE_SHA256, 'Exact bounded environment-workspace workflow fixture required'
    value = json.loads(raw)
    assert type(value['schema']) is int and value['schema'] == 1 and value['path'] == PATH
    assert (value['previousCommit'], value['previousTree']) == (PREVIOUS_COMMIT, PREVIOUS_TREE)
    assert (value['previousBytes'], value['previousSha256']) == (PREVIOUS_BYTES, PREVIOUS_SHA256)
    assert (value['reviewedBytes'], value['reviewedSha256']) == (CURRENT_BYTES, CURRENT_SHA256)
    assert len(value['deltas']) == 5, 'Only five reviewed environment capture and Gradle fallback workflow hunks are owned'
    return value


def source_input(raw, path):
    assert type(raw) is bytes and type(path) is str and path == PATH, 'Complete owned workflow bytes required'
    value = manifest()
    assert (len(raw), sha(raw)) == (CURRENT_BYTES, CURRENT_SHA256), 'Unreviewed complete environment-workspace workflow'
    for delta in reversed(value['deltas']):
        current, previous = delta['current'].encode(), delta['previous'].encode()
        for name, literal in (('current', current), ('previous', previous)):
            assert 0 < len(literal) <= 8192 and (len(literal), sha(literal)) == (delta[name + 'Bytes'], delta[name + 'Sha256'])
        assert raw.count(current) == 1, 'Missing, duplicated or moved exact environment capture hunk'
        raw = raw.replace(current, previous, 1)
    assert (len(raw), sha(raw)) == (PREVIOUS_BYTES, PREVIOUS_SHA256), 'Entire upstream workflow did not restore'
    return raw


def historical_workflow_text(source):
    """Recognize the one full after-image; unknown text faces the original guard."""
    assert type(source) is str, 'Complete workflow source text required'
    raw = source.encode()
    if (len(raw), sha(raw)) == (CURRENT_BYTES, CURRENT_SHA256):
        return source_input(raw, PATH).decode()
    return source
