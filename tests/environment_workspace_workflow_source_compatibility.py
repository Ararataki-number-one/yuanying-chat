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
FIXTURE_SHA256 = 'c7124c5d48a58ef71204e236941d84cf6408194b39af2520ace79b120e3358de'
PREVIOUS_COMMIT = '4e99ab57a4d58a2ce7ab4d7d8d0c3362da41cd2e'
PREVIOUS_TREE = '5af60118121ccdc5bff9410dc13e20b05af9b391'
PREVIOUS_BYTES = 22064
PREVIOUS_SHA256 = 'e916cce66ae0017ebcc54d071f7a7a46e70c245aeb0be8a64ab567b5da14cc6d'
CURRENT_BYTES = 22867
CURRENT_SHA256 = '48a50bc7b3870ed7d57166f3e86ebd49f698abccfb4de90df573a330d230eea7'


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
    assert len(value['deltas']) == 7, 'Only four capture, two branch-trigger and one fixed history-owner workflow hunks are owned'
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
