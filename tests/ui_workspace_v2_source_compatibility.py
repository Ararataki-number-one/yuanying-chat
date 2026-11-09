"""Finite source views for retained UI oracles after the five-page redesign.

Only historical source assertions call these inverses. Android execution and
the capture host still compile the actual current runner and its version value.
All original checkpoint, QuickSheet, observer and UI14 guards run afterward.
"""
import ast
import copy
import functools
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/ui-workspace-v2-source-deltas.json'
FIXTURE_SHA256 = '49b9a00ad3eb6e9a001f70fef41342b65c0d8fedd67939d2546fb669d81878b0'
BASE_COMMIT = 'c244835a4c1e3629909b2b1ce132ca5987a97d9a'
BASE_TREE = '13f8feea716e7ceebd71fb46b21966292c920681'
RUNNER = 'tests/gecko/run_ui_visuals.py'
HOST = 'tests/gecko_ui_visual_capture_test.py'
IDENTITIES = {
    RUNNER: (46016, 'b85896aa5b94e33fb40bbada323d239a66f75c12a39bf9adb2a4ff3e3483e14d',
             'fed65f826a7821002908d7b37d86647c58381943', 47085,
             '075279cecd6cadb4fa51b6f866b0779618cf78125dc6b30a7c1149e13408c5a9'),
    HOST: (40357, '4ec6b7535d37119d6674afc5090b33d8c26af91abaa5d53ecb2a52488e911f6a',
           '8999248d15abe71c72d747c49e5525206b39186c', 40714,
           '7c7918b3f0457c54df0cbb9e219931c5add087b8babef34611fa972ed273e0c4'),
    'tests/profile_ui_quick_sheet_source_compatibility_test.py': (
        10058, '140727717d2211ede38c86d54661dac1f66748f011faaddfe50e10fb40b9c5af',
        'fb933716758cd2467331bc4d153f339fc52a3285', 10166,
        '44ad29a3fe25b0fb6311f37611fde020ec22a9155de4780c813ea05c3f157a3a'),
}
# Only the original complete module and the already-supported variant without
# its old preparation block are admitted. Comments/formatting preserve ASTs.
AST_PAIRS = {
    '5fbe79ffe0f0cfd37397814adb19efa27328d9cc41ab61d4b9493d41b19a062e':
        'e4d4116f7bf22e5a791af482e4315446c3e521d5dec0a4d15543337650491220',
    'ca3d9bbe87f4645d9f25f6286b9ced0a2984bb05d7ec8013e7bfc2cff0b60dd2':
        '1e9931102c092304b30ea22c910f46737ddf34aa4879e7bf9cd93b8de5e5cbb3',
}
AST_EDIT_IDS = (
    'explicit-v2-imports-and-version', 'current-page-readiness',
    'actual-chat-presentation', 'actual-environments-presentation',
    'actual-v2-compact-dispatch', 'versioned-collapse-import', 'explicit-collapse-version',
)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def tree_sha(tree):
    return sha(ast.dump(tree, include_attributes=False).encode())


def manifest():
    assert not FIXTURE.is_symlink() and FIXTURE.is_file(), 'Ordinary exact UI-v2 source fixture required'
    raw = FIXTURE.read_bytes()
    assert len(raw) == 26424 and sha(raw) == FIXTURE_SHA256, 'UI-v2 fixture differs from its reviewed whole bytes'
    value = json.loads(raw)
    assert set(value) == {'schema', 'kind', 'baseCommit', 'baseTree', 'actualAndroidExecution', 'runtimeAcceptance', 'files', 'runnerAst'}
    assert type(value['schema']) is int and value['schema'] == 1
    assert value['kind'] == 'ui-workspace-v2-historical-source-input-only'
    assert (value['baseCommit'], value['baseTree']) == (BASE_COMMIT, BASE_TREE)
    assert value['actualAndroidExecution'] is value['runtimeAcceptance'] is False
    assert set(value['files']) == set(IDENTITIES)
    for path, row in value['files'].items():
        assert (row['previousBytes'], row['previousSha256'], row['previousGitBlob'], row['reviewedBytes'], row['reviewedSha256']) == IDENTITIES[path]
        assert row['contextLines'] == 3 and 0 < len(row['deltas']) <= 8
        for index, delta in enumerate(row['deltas']):
            assert delta['id'] == 'context-%02d' % index
            for name in ('previous', 'current'):
                text = delta[name].encode()
                assert 0 < len(text) <= 16384 and (len(text), sha(text)) == (delta[name+'Bytes'], delta[name+'Sha256'])
    assert value['runnerAst']['allowedModulePairs'] == AST_PAIRS
    assert tuple(row['id'] for row in value['runnerAst']['edits']) == AST_EDIT_IDS
    for edit in value['runnerAst']['edits']:
        for name in ('previous', 'current'):
            assert len(edit[name+'Source'].encode()) <= 16384
            node = ast.parse(edit[name+'Source'])
            assert len(node.body) == edit[name+'Nodes'] and tree_sha(node) == edit[name+'AstSha256']
        assert edit['currentNodes'] > 0
    return value


def source_input(raw, path):
    """Exact current whole bytes -> contextual inverse -> actual c244 blob."""
    assert type(raw) is bytes and type(path) is str and path in IDENTITIES
    row = manifest()['files'][path]
    assert (len(raw), sha(raw)) == (row['reviewedBytes'], row['reviewedSha256']), 'Unreviewed complete UI-v2 source'
    for delta in reversed(row['deltas']):
        current, previous = delta['current'].encode(), delta['previous'].encode()
        assert raw.count(current) == 1, 'Missing, repeated or relocated UI-v2 context'
        raw = raw.replace(current, previous, 1)
    assert (len(raw), sha(raw)) == (row['previousBytes'], row['previousSha256']), 'Complete c244 source did not restore'
    blob = hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    assert blob == row['previousGitBlob'], 'Historical input is not the original Git blob'
    return raw


def historical_input(raw, path):
    """Forward every unknown image unchanged to the existing strict oracle."""
    if (type(raw) is bytes and type(path) is str and path in IDENTITIES
            and (len(raw), sha(raw)) == (IDENTITIES[path][3], IDENTITIES[path][4])):
        return source_input(raw, path)
    return raw


def _statement_lists(node):
    for _, field in ast.iter_fields(node):
        if isinstance(field, list):
            if field and all(isinstance(item, ast.stmt) for item in field):
                yield field
            for item in field:
                if isinstance(item, ast.AST):
                    yield from _statement_lists(item)
        elif isinstance(field, ast.AST):
            yield from _statement_lists(field)


def original_runner_tree(tree):
    """Reverse only one of two complete current ASTs; all old gates still run."""
    assert type(tree) is ast.Module, 'Complete parsed UI module required'
    current = tree_sha(tree)
    assert current in AST_PAIRS, 'Unreviewed complete UI-v2 runner AST'
    for edit in reversed(manifest()['runnerAst']['edits']):
        previous, reviewed = ast.parse(edit['previousSource']), ast.parse(edit['currentSource'])
        signatures = [ast.dump(node, include_attributes=False) for node in reviewed.body]
        matches = []
        for statements in _statement_lists(tree):
            for index in range(len(statements)-len(signatures)+1):
                if [ast.dump(node, include_attributes=False) for node in statements[index:index+len(signatures)]] == signatures:
                    matches.append((statements, index))
        assert len(matches) == 1, 'One exact positioned UI-v2 statement sequence required'
        statements, index = matches[0]
        statements[index:index+len(signatures)] = copy.deepcopy(previous.body)
    assert tree_sha(tree) == AST_PAIRS[current], 'Complete c244 UI AST did not restore'
    return tree


def historical_tree(tree):
    assert type(tree) is ast.Module, 'Complete parsed UI module required'
    references = [node for node in ast.walk(tree)
                  if isinstance(node, ast.Name) and node.id in ('UI_NAVIGATION_CONTRACT', 'capture_compact_v2', 'capture_environment_selection')
                  or isinstance(node, ast.ImportFrom) and node.module in ('workspace_navigation_contract', 'compact_chrome_v2', 'workspace_ui_v2')
                  or isinstance(node, ast.keyword) and node.arg == 'navigation_contract']
    return original_runner_tree(tree) if references else tree


def wrap_bytes(original):
    @functools.wraps(original)
    def historical_source(raw, path):
        return original(historical_input(raw, path), path)
    return historical_source


def wrap_runner_bytes(original):
    @functools.wraps(original)
    def historical_runner(raw):
        return original(historical_input(raw, RUNNER))
    return historical_runner


def wrap_ast(original):
    @functools.wraps(original)
    def historical_runner(tree):
        return original(historical_tree(tree))
    return historical_runner
