"""Finite source inputs for retained workflow-test metadata oracles only.

Current YAML, Java compilation and host producers never use these inverses.
The three after-images restore actual public source before old guards run.
"""
import copy
import functools
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/gradle-workflow-test-source-deltas.json'
FIXTURE_SHA256 = '5d1f33ee4997b73e4c8785fbac39e831311247b5cae7c6d3e8c6182a8350a6ee'
FINAL = 'tests/final_browser_source_compatibility.py'
PREVIOUS = {
    FINAL: 'ffce17929a97c1f28c9ce5b29d155a2f88aee85581b1083ecc170df67ae0d6f8',
    'tests/profile_fixture_root_source_compatibility.py': '52832d737554f293ecb648d76369ffb4ee1d1bcbe1654575cff2e8dda3d3cdc6',
    'tests/profile_final_browser_source_compatibility_test.py': '1d211a864752086350097d7a1b9c0d60a03968a2bc44382d8ca80f1bc3ec0822',
}
MAX_SOURCE_BYTES = 256 * 1024


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def manifest():
    if FIXTURE.is_symlink() or not FIXTURE.is_file() or FIXTURE.resolve() != FIXTURE.absolute():
        raise ValueError('Workflow-test metadata requires its ordinary exact fixture')
    raw = FIXTURE.read_bytes()
    if not 0 < len(raw) <= 65536 or sha(raw) != FIXTURE_SHA256:
        raise ValueError('Exact bounded workflow-test metadata fixture required')
    value = json.loads(raw)
    if (type(value['schema']) is not int or value['schema'] != 1
            or value['kind'] != 'historical-workflow-test-source-input-only'
            or value['baseCommit'] != '7402ead321ca74b9fbefeab32a1aaffb32832011'
            or value['baseTree'] != '2aaec06687b65d9511ace499528b6946dc1b8d53'
            or value['actualAndroidExecution'] is not False or value['runtimeAcceptance'] is not False
            or set(value['files']) != set(PREVIOUS)
            or any(value['files'][path]['previousSha256'] != previous for path, previous in PREVIOUS.items())
            or [len(value['files'][path]['deltas']) for path in PREVIOUS] != [2, 1, 1]):
        raise ValueError('Workflow-test metadata scope or public provenance differs')
    before, after = value['rootPreviousRow'], value['rootCurrentRow']
    if ((before['previousSha256'], before['previousBytes']) !=
            ('0c57aeb34471f92629a36cdc8f71447f2353daaac6a7940423c2e85d9141e37d', 16085)
            or (before['reviewedSha256'], before['reviewedBytes']) !=
            (PREVIOUS[FINAL], value['files'][FINAL]['previousBytes'])
            or (after['previousSha256'], after['previousBytes']) !=
            (before['previousSha256'], before['previousBytes'])
            or (after['reviewedSha256'], after['reviewedBytes']) !=
            (value['files'][FINAL]['reviewedSha256'], value['files'][FINAL]['reviewedBytes'])
            or len(before['deltas']) != 1 or len(after['deltas']) != 1):
        raise ValueError('Workflow-test metadata lost its exact root predecessor or one context')
    return value


def source_input(raw, relative):
    if (type(raw) is not bytes or type(relative) is not str or relative not in PREVIOUS
            or not 0 < len(raw) <= MAX_SOURCE_BYTES):
        raise ValueError('Complete bounded owned workflow-test source required')
    row = manifest()['files'][relative]
    if (len(raw), sha(raw)) != (row['reviewedBytes'], row['reviewedSha256']):
        raise ValueError('Unknown complete workflow-test source after-image')
    for delta in reversed(row['deltas']):
        current, previous = delta['current'].encode(), delta['previous'].encode()
        for name, literal in (('current', current), ('previous', previous)):
            if (not 0 < len(literal) <= 32768
                    or (len(literal), sha(literal)) != (delta[name + 'Bytes'], delta[name + 'Sha256'])):
                raise ValueError('Exact bounded workflow-test source context required')
        if raw.count(current) != 1:
            raise ValueError('Missing, repeated or moved workflow-test context')
        raw = raw.replace(current, previous, 1)
    if (len(raw), sha(raw)) != (row['previousBytes'], PREVIOUS[relative]):
        raise ValueError('Entire public workflow-test source did not restore')
    return raw


def historical_input(raw, relative):
    """Only complete known after-images change; original guards see all else."""
    if (type(raw) is bytes and type(relative) is str and relative in PREVIOUS
            and 0 < len(raw) <= MAX_SOURCE_BYTES
            and sha(raw) == manifest()['files'][relative]['reviewedSha256']):
        return source_input(raw, relative)
    return raw


def wrap_source_input(original):
    @functools.wraps(original)
    def historical_source(raw, relative):
        return original(historical_input(raw, relative), relative)
    return historical_source


def _encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def wrap_resource_config(original):
    @functools.wraps(original)
    def current_source_rows():
        value = original()
        if sha(_encoded(value)) != '417f15a681f3fcf0bf29f4370a76b489e79a78f16f0e99d768e2fad73a9605a0':
            raise ValueError('Exact original resource configuration required')
        result = copy.deepcopy(value)
        for relative, row in manifest()['files'].items():
            selected = result['sources'][relative]
            if (selected['currentSha256'], selected['currentBytes']) != (row['previousSha256'], row['previousBytes']):
                raise ValueError('Resource source row lost its reviewed predecessor')
            selected['currentSha256'], selected['currentBytes'] = row['reviewedSha256'], row['reviewedBytes']
            selected['edits'].extend({'previous': delta['previous'], 'current': delta['current']} for delta in row['deltas'])
        return result
    return current_source_rows


def wrap_root_manifest(original):
    @functools.wraps(original)
    def current_root_row():
        value = original()
        fixture = manifest()
        if (sha(_encoded(value)) != fixture['rootManifestSha256']
                or value['files'][FINAL] != fixture['rootPreviousRow']):
            raise ValueError('Exact original root manifest required')
        result = copy.deepcopy(value)
        result['files'][FINAL] = copy.deepcopy(fixture['rootCurrentRow'])
        return result
    return current_root_row


def wrap_root_source_input(original):
    @functools.wraps(original)
    def root_source(raw, relative):
        if type(raw) is bytes and relative == FINAL and 0 < len(raw) <= MAX_SOURCE_BYTES:
            row = manifest()['rootPreviousRow']
            if (sha(raw), len(raw)) == (row['reviewedSha256'], row['reviewedBytes']):
                for delta in reversed(row['deltas']):
                    current, previous = delta['current'].encode(), delta['previous'].encode()
                    if (not 0 < len(current) <= 32768 or not 0 < len(previous) <= 32768
                            or sha(current) != delta['currentSha256'] or sha(previous) != delta['previousSha256']
                            or raw.count(current) != 1):
                        raise ValueError('Exact legacy root context required')
                    raw = raw.replace(current, previous, 1)
                if (sha(raw), len(raw)) != (row['previousSha256'], row['previousBytes']):
                    raise ValueError('Entire legacy root predecessor did not restore')
        return original(raw, relative)
    return root_source


def wrap_build_budget_helper_before(original):
    @functools.wraps(original)
    def historical_helper(raw):
        return original(historical_input(raw, FINAL))
    return historical_helper


# Exact workspace-navigation source view for historical metadata only.
from workspace_runner_source_compatibility import wrap_input as _workspace_source_input
source_input = _workspace_source_input(source_input)
historical_input = _workspace_source_input(historical_input)
