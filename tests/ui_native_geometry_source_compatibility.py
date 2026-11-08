"""Exact current-toolbar inputs for historical source assertions only.

The actual capture, native helper and behavior execution always read raw source.
"""
import ast
import functools
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = 'tests/gecko/run_ui_visuals.py'
NAVIGATION = 'tools/gecko/native_navigation_v2.py'
FIXTURE = ROOT / 'tests/fixtures/ui-native-geometry-source-deltas.json'
FIXTURE_SHA256 = '0c3081aa74be1eadc9960ab57551de9fba9e2d128d432edde170d913791db3ef'
BEFORE = (47025, '12d0f61c0f53efd5766f37cf34ae5526acadfa287a387eb81855dd2e5943783f')
AFTER = (47272, '6e1ace5e7fb823c650e2084f717e81aba75934c41f9db3df2e0a12188ba90989')
PREVIOUS_AST = frozenset(('3e66c8780755fb73fe5b12ca0fdf319daa8e208a357c43adb7a8b70e2660abef',
                          'a6518b20f3d67163aedbf2fb2e2ead51b71cd9c5d9d93215d8ae422308723ca4'))
sha = lambda raw: hashlib.sha256(raw).hexdigest()
tree_sha = lambda tree: sha(ast.dump(tree, include_attributes=False).encode())


def manifest():
    assert FIXTURE == ROOT / 'tests/fixtures/ui-native-geometry-source-deltas.json'
    assert not FIXTURE.is_symlink() and FIXTURE.is_file()
    raw = FIXTURE.read_bytes()
    assert 0 < len(raw) <= 32768 and sha(raw) == FIXTURE_SHA256, 'Exact bounded current-toolbar comparison metadata required'
    def unique(items):
        result = {}
        for key, value in items:
            assert key not in result, 'Duplicate current-toolbar comparison metadata'
            result[key] = value
        return result
    value = json.loads(raw, object_pairs_hook=unique)
    assert set(value) == {'schema', 'kind', 'actualAndroidExecution', 'runtimeAcceptance',
                          'baseCommit', 'baseTree', 'files', 'runnerAstPairs', 'previousRunnerAst'}
    assert type(value['schema']) is int and value['schema'] == 1
    assert value['kind'] == 'historical-current-toolbar-source-only'
    assert value['actualAndroidExecution'] is False and value['runtimeAcceptance'] is False
    assert (value['baseCommit'], value['baseTree']) == (
        'dea2d48a04facdc13e3245425f095be3f7d495ad', 'a3d612ccd509d3e84bf1e4efe49ea2ca07f5e485')
    assert set(value['files']) == {RUNNER}
    row = value['files'][RUNNER]
    assert (row['previousBytes'], row['previousSha256']) == BEFORE
    assert (row['currentBytes'], row['currentSha256']) == AFTER
    assert len(row['deltas']) == 3
    for delta in row['deltas']:
        for name in ('previous', 'current'):
            assert type(delta[name]) is str
            literal = delta[name].encode()
            assert 0 < len(literal) <= 32768
            assert (len(literal), sha(literal)) == (delta[name+'Bytes'], delta[name+'Sha256'])
    assert frozenset(value['previousRunnerAst']) == PREVIOUS_AST
    assert len(value['runnerAstPairs']) == 2
    assert {pair['previousAstSha256'] for pair in value['runnerAstPairs'].values()} == PREVIOUS_AST
    for pair in value['runnerAstPairs'].values():
        assert len(pair['operations']) == 3
        for operation in pair['operations']:
            assert operation['path'] and operation['path'][0] == 'body'
            assert all(type(part) is int and part >= 0 or type(part) is str and part in ('body', 'orelse', 'finalbody')
                       for part in operation['path'])
            for name in ('previous', 'current'):
                source = operation[name+'Source']
                assert type(source) is str and len(source.encode()) <= 32768
                assert tree_sha(ast.parse(source)) == operation[name+'AstSha256']
    return value


def source_input(raw, path=RUNNER):
    assert type(raw) is bytes and type(path) is str and path == RUNNER, 'One complete owned historical runner input required'
    row = manifest()['files'][path]
    if (len(raw), sha(raw)) == BEFORE:
        return raw
    assert (len(raw), sha(raw)) == AFTER, 'Unreviewed complete current-toolbar runner source'
    for delta in reversed(row['deltas']):
        current, previous = delta['current'].encode(), delta['previous'].encode()
        assert raw.count(current) == 1, 'One positioned current-toolbar source hunk required'
        raw = raw.replace(current, previous, 1)
    assert (len(raw), sha(raw)) == BEFORE, 'Entire historical runner comparison input did not restore'
    return raw


def historical_input(raw, path):
    return source_input(raw, path) if path == RUNNER else raw


def runner_tree_input(tree):
    assert type(tree) is ast.Module, 'Complete runner comparison module required'
    value = manifest()
    digest = tree_sha(tree)
    if digest in PREVIOUS_AST:
        return tree
    assert digest in value['runnerAstPairs'], 'Unreviewed complete current-toolbar runner AST'
    pair = value['runnerAstPairs'][digest]
    for operation in reversed(pair['operations']):
        body = tree
        for part in operation['path']:
            if type(part) is int:
                assert isinstance(body, list) and part < len(body)
                body = body[part]
            else:
                body = getattr(body, part)
        start, end = operation['currentStart'], operation['currentEnd']
        assert type(start) is int and type(end) is int and 0 <= start <= end <= len(body)
        assert tree_sha(ast.Module(body=body[start:end], type_ignores=[])) == operation['currentAstSha256']
        body[start:end] = ast.parse(operation['previousSource']).body
    assert tree_sha(tree) == pair['previousAstSha256'], 'Entire previous runner AST did not restore'
    return tree


def wrap_bytes(original):
    @functools.wraps(original)
    def compared(raw, path):
        # Older adapters also forward their own fixed intermediate images.
        # Only the new after-image is ours; every other byte faces that guard.
        if type(raw) is bytes and path == RUNNER and (len(raw), sha(raw)) == AFTER:
            raw = source_input(raw, path)
        return original(raw, path)
    return compared


def wrap_runner(original):
    @functools.wraps(original)
    def compared(raw):
        if type(raw) is bytes and (len(raw), sha(raw)) == AFTER:
            raw = source_input(raw)
        return original(raw)
    return compared


def wrap_ast(original):
    @functools.wraps(original)
    def compared(tree):
        if type(tree) is ast.Module:
            current = manifest()['runnerAstPairs']
            names = {'compact_navigation_protocol', 'validate_compact_toolbar_v2'}
            if tree_sha(tree) in current or tree_sha(tree) in PREVIOUS_AST or any(
                    isinstance(node, ast.Name) and node.id in names
                    or isinstance(node, ast.ImportFrom) and any(alias.name in names for alias in node.names)
                    for node in ast.walk(tree)):
                runner_tree_input(tree)
        return original(tree)
    return compared
