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


# The runtime workflow retains its current emulator setup and strict readback.
import importlib.util as _navigation_import
_navigation_spec = _navigation_import.spec_from_file_location('glass_emulator_navigation_history', Path(__file__).with_name('glass_emulator_navigation_source_compatibility.py'))
_navigation_module = _navigation_import.module_from_spec(_navigation_spec)
_navigation_spec.loader.exec_module(_navigation_module)
source_input = _navigation_module.wrap_source_input(source_input)


# Canonical history preparation is a separate two-hunk comparison input. Its
# metadata is read only by workflow assertions, never by the Activity host.
CANONICAL_PROFILE_FIXTURE = ROOT / 'tests/fixtures/canonical-profile-prerequisites-source-deltas.json'
CANONICAL_PROFILE_FIXTURE_SHA256 = '3c47df623b0ae97e4f9e2e703ce7ec35bba1e9dc3b9fa0245e49a0a5c0f55542'
CANONICAL_PROFILE_CURRENT_SHA256 = 'd75fe799c4ec95166385049e14382c2e810c7d39bf4c2d438f5099b5281c0340'


def _canonical_unique(items):
    value = {}
    for key, item in items:
        assert key not in value, 'Duplicate canonical prerequisite metadata'
        value[key] = item
    return value


def _canonical_nonfinite(value):
    raise AssertionError('Nonfinite canonical prerequisite metadata')


def canonical_profile_manifest():
    expected = ROOT / 'tests/fixtures/canonical-profile-prerequisites-source-deltas.json'
    assert CANONICAL_PROFILE_FIXTURE == expected and not expected.is_symlink() and expected.is_file() and expected.resolve() == expected.absolute()
    raw = expected.read_bytes()
    assert 0 < len(raw) <= 8192 and sha(raw) == CANONICAL_PROFILE_FIXTURE_SHA256, 'Exact bounded canonical prerequisite fixture required'
    value = json.loads(raw, object_pairs_hook=_canonical_unique, parse_constant=_canonical_nonfinite)
    assert set(value) == {'schema', 'kind', 'baseCommit', 'baseTree', 'path', 'previousBlob', 'actualAndroidExecution', 'runtimeAcceptance', 'transportRow', 'currentRow'}
    assert type(value['schema']) is int and value['schema'] == 1 and value['kind'] == 'canonical-profile-prerequisites-history-input-only'
    assert (value['baseCommit'], value['baseTree'], value['path'], value['previousBlob']) == (
        '7402ead321ca74b9fbefeab32a1aaffb32832011', '2aaec06687b65d9511ace499528b6946dc1b8d53', CANONICAL, '77ad725e792229d8ac89301d581f0dfa38c7fb9d')
    assert value['actualAndroidExecution'] is False and value['runtimeAcceptance'] is False
    prior, current = value['transportRow'], value['currentRow']
    assert type(prior) is dict and type(current) is dict
    assert set(prior) == set(current) == {'previousBytes', 'reviewedBytes', 'previousSha256', 'reviewedSha256', 'deltas'}
    assert (prior['previousBytes'], prior['previousSha256']) == (92044, PREVIOUS[CANONICAL])
    assert (prior['reviewedBytes'], prior['reviewedSha256']) == (92383, '2629831d0afd9176b0ce4d92a4c03117b66a3f20c4912885b4c31b391160f83e')
    assert (current['previousBytes'], current['previousSha256']) == (92044, PREVIOUS[CANONICAL])
    assert (current['reviewedBytes'], current['reviewedSha256']) == (92665, CANONICAL_PROFILE_CURRENT_SHA256)
    assert all(type(row[name]) is int for row in (prior, current) for name in ('previousBytes', 'reviewedBytes'))
    assert type(prior['deltas']) is list and type(current['deltas']) is list
    assert len(prior['deltas']) == 1 and len(current['deltas']) == 2 and current['deltas'][:1] == prior['deltas']
    for delta in current['deltas']:
        assert type(delta) is dict and set(delta) == {'previous', 'current', 'previousBytes', 'currentBytes', 'previousSha256', 'currentSha256'}
        for name in ('previous', 'current'):
            assert type(delta[name]) is str and type(delta[name + 'Bytes']) is int
            literal = delta[name].encode()
            assert 0 < len(literal) <= 32768 and (len(literal), sha(literal)) == (delta[name + 'Bytes'], delta[name + 'Sha256'])
        assert delta['previous'] != delta['current']
    return value


def canonical_profile_source_input(raw, path):
    """The canonical path admits only its current complete two-hunk image."""
    assert type(raw) is bytes and type(path) is str and path == CANONICAL, 'Complete canonical prerequisite workflow required'
    row = canonical_profile_manifest()['currentRow']
    assert (len(raw), sha(raw)) == (row['reviewedBytes'], CANONICAL_PROFILE_CURRENT_SHA256), 'Unreviewed complete canonical prerequisite workflow'
    for delta in reversed(row['deltas']):
        current, previous = delta['current'].encode(), delta['previous'].encode()
        assert raw.count(current) == 1, 'Unique exact canonical prerequisite context required'
        raw = raw.replace(current, previous, 1)
    assert (len(raw), sha(raw)) == (row['previousBytes'], PREVIOUS[CANONICAL]), 'Entire public canonical prerequisite predecessor did not restore'
    return raw


def _canonical_manifest_view(original):
    @functools.wraps(original)
    def current_workflow_manifest():
        value, fixture = original(), canonical_profile_manifest()
        assert value['files'][CANONICAL] == fixture['transportRow'], 'Original canonical transport row changed'
        files = dict(value['files'])
        files[CANONICAL] = fixture['currentRow']
        return dict(value, files=files)
    return current_workflow_manifest


def _canonical_source_view(original):
    @functools.wraps(original)
    def current_workflow_source(raw, path):
        if type(path) is str and path == CANONICAL:
            return canonical_profile_source_input(raw, path)
        return original(raw, path)
    return current_workflow_source


def wrap_canonical_current_after(original):
    """Only the retained test forward comparison advances its exact midpoint."""
    @functools.wraps(original)
    def complete_current_after(raw, path):
        raw = original(raw, path)
        if (type(raw) is not bytes or type(path) is not str or path != CANONICAL
                or (len(raw), sha(raw)) != (92383, '2629831d0afd9176b0ce4d92a4c03117b66a3f20c4912885b4c31b391160f83e')):
            return raw
        row = canonical_profile_manifest()['currentRow']
        delta = row['deltas'][1]
        previous, current = delta['previous'].encode(), delta['current'].encode()
        assert raw.count(previous) == 1, 'Unique canonical prerequisite forward context required'
        raw = raw.replace(previous, current, 1)
        assert (len(raw), sha(raw)) == (row['reviewedBytes'], CANONICAL_PROFILE_CURRENT_SHA256), 'Complete canonical prerequisite forward image differs'
        return raw
    return complete_current_after


manifest = _canonical_manifest_view(manifest)
source_input = _canonical_source_view(source_input)
