"""Exact Gradle transport source inputs for retained workflow assertions.

The actual workflows and SDK/host producers continue reading current raw bytes.
These inverses only supply historical comparison inputs and verify their exact
current transport, fixed official asset, size, checksum and unchanged remainder.
"""
import functools
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/gradle-transport-source-deltas.json'
FIXTURE_SHA256 = '0e34228b10f4ecb511c584f5fc071e06ffd87e6981caddd80b0510897fbcc793'
CANONICAL = '.github/workflows/browser-2_1-acceptance.yml'
PREVIOUS = {
    CANONICAL: 'a4ef3a60391eb6a9fc86dba2986fcd7f7fc053f9e32bc4818cc6e773d8c84435',
    '.github/workflows/profile-upgrade-checks.yml': '37ec53f065fa4572b8d59c7d4138dc170267f73911c46b5d4db0855dfe024699',
    '.github/workflows/glass-release-validation.yml': '686928c3060c06808068f2f43f54276f64eb54136ee112709f1d61a8b8aa171b',
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def manifest():
    raw = FIXTURE.read_bytes()
    assert not FIXTURE.is_symlink() and len(raw) <= 16384 and sha(raw) == FIXTURE_SHA256, 'Exact bounded Gradle transport fixture required'
    value = json.loads(raw)
    assert type(value['schema']) is int and value['schema'] == 1
    assert value['baseCommit'] == '7402ead321ca74b9fbefeab32a1aaffb32832011'
    assert value['baseTree'] == '2aaec06687b65d9511ace499528b6946dc1b8d53'
    assert set(value['files']) == set(PREVIOUS), 'Only three reviewed transport workflows are owned'
    assert all(row['previousSha256'] == PREVIOUS[path] and len(row['deltas']) == 1 for path, row in value['files'].items())
    return value


def source_input(raw, path):
    """Require the complete reviewed current workflow before one finite inverse."""
    assert type(raw) is bytes and type(path) is str and path in PREVIOUS, 'Complete owned workflow source bytes required'
    row = manifest()['files'][path]
    assert 0 < len(raw) <= 131072 and (len(raw), sha(raw)) == (row['reviewedBytes'], row['reviewedSha256']), 'Unreviewed complete Gradle transport workflow'
    delta = row['deltas'][0]
    current, previous = delta['current'].encode(), delta['previous'].encode()
    for name, literal in (('current', current), ('previous', previous)):
        assert 0 < len(literal) <= 32768 and (len(literal), sha(literal)) == (delta[name + 'Bytes'], delta[name + 'Sha256'])
    assert raw.count(current) == 1, 'Missing, duplicated or moved exact Gradle transport hunk'
    restored = raw.replace(current, previous, 1)
    assert (len(restored), sha(restored)) == (row['previousBytes'], PREVIOUS[path]), 'Entire original Gradle workflow did not restore'
    return restored


def canonical_history_input(raw):
    """Unknown inputs still face the unchanged canonical workflow oracle."""
    if type(raw) is bytes and 0 < len(raw) <= 131072 and sha(raw) == manifest()['files'][CANONICAL]['reviewedSha256']:
        return source_input(raw, CANONICAL)
    return raw


def historical_toolchain_step(step):
    """One comparison LHS only; return a new dict and keep actual parsed YAML raw."""
    value = manifest()['toolchainStep']
    if type(step) is not dict or step.get('name') != value['name'] or type(step.get('run')) is not str:
        return step
    raw = step['run'].encode()
    if (len(raw), sha(raw)) != (value['reviewedRunBytes'], value['reviewedRunSha256']):
        return step
    current, previous = value['current'], value['previous']
    assert 0 < len(current.encode()) <= 32768 and 0 < len(previous.encode()) <= 32768
    assert step['run'].count(current) == 1, 'One exact official Gradle transport block required'
    restored = step['run'].replace(current, previous, 1)
    assert (len(restored.encode()), sha(restored.encode())) == (value['previousRunBytes'], value['previousRunSha256']), 'Entire original toolchain run did not restore'
    return dict(step, run=restored)


def wrap_checkpoint_workflow(original):
    @functools.wraps(original)
    def historical_workflow(raw):
        return original(canonical_history_input(raw))
    return historical_workflow
