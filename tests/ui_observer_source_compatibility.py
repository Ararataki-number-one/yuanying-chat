"""Exact source-only inverse for the reviewed fresh download observation.

Current Android runners, callbacks, host execution and native reports are never
rewritten. This module supplies only retained historical byte/AST oracles.
"""
import ast
import functools
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/ui-observer-source-deltas.json'
FIXTURE_SHA256 = '998637d381722c943cb32517cb1c72e092d0d0db7581e0f7c9103d74303b42c8'
RUNNER = 'tests/gecko/run_ui_visuals.py'
PATHS = frozenset((RUNNER, 'tests/gecko/UiVisualIntegrationActivity.java',
    'tests/gecko/DownloadLocationLayoutEvidence.java',
    'tests/ui_visual_preservation_contract.py', 'tests/ui_runner14_source_contract.py',
    'tests/profile_ui_settings_services11_test.py'))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def tree_sha(node):
    return sha(ast.dump(node, include_attributes=False).encode())


def manifest():
    raw = FIXTURE.read_bytes()
    assert len(raw) <= 128 * 1024 and sha(raw) == FIXTURE_SHA256, 'Exact UI observation source fixture required'
    value = json.loads(raw)
    assert value['schema'] == 1 and value['baseCommit'] == 'e21b4fd6698074310ee36f85f980b16ad643c934'
    assert set(value['files']) == PATHS, 'Finite UI source paths required'
    return value


def source_input(raw, path, *, allow_previous=False):
    assert type(raw) is bytes and type(path) is str and path in PATHS, 'Exact source bytes and owned relative path required'
    assert type(allow_previous) is bool
    row = manifest()['files'][path]
    if allow_previous and len(raw) == row['previousBytes'] and sha(raw) == row['previousSha256']:
        return raw
    assert len(raw) == row['reviewedBytes'] and sha(raw) == row['reviewedSha256'], 'Unreviewed complete UI observation source'
    for delta in reversed(row['deltas']):
        current, previous = delta['current'].encode(), delta['previous'].encode()
        assert len(current) == delta['currentBytes'] and sha(current) == delta['currentSha256']
        assert len(previous) == delta['previousBytes'] and sha(previous) == delta['previousSha256']
        assert current and raw.count(current) == 1, 'Missing, repeated or moved exact UI source delta'
        raw = raw.replace(current, previous, 1)
    assert len(raw) == row['previousBytes'] and sha(raw) == row['previousSha256'], 'Entire original UI source did not restore'
    return raw


def wrap_runner_bytes(original):
    @functools.wraps(original)
    def observed_ui_source(raw):
        assert type(raw) is bytes, 'Complete UI runner bytes required'
        if sha(raw) == manifest()['files'][RUNNER]['reviewedSha256']:
            raw = source_input(raw, RUNNER)
        return original(raw)
    return observed_ui_source


def original_runner_tree(tree):
    assert type(tree) is ast.Module, 'A complete parsed UI module is required'
    assert len([node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'capture']) == 1
    assert len([node for node in tree.body if isinstance(node, ast.Try) and node.finalbody]) == 1, 'Complete UI workload required, never an excerpt'
    value = manifest()['runnerAst']
    names = set(value['helperNames']) | {'download_observation_history'}
    references = [node for node in ast.walk(tree) if isinstance(node, ast.Name) and node.id in names
                  or isinstance(node, ast.FunctionDef) and node.name in names]
    if not references:
        return tree
    current = tree_sha(tree)
    assert current in value['allowedModulePairs'], 'Unreviewed complete fresh-observation AST'
    captures = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'capture']
    assert len(captures) == 1 and tree_sha(captures[0]) == value['captureReviewedSha256'], 'Complete reviewed capture required'
    capture = captures[0]
    for delta in reversed(value['captureDeltas']):
        selected = capture.body[delta['currentStart']:delta['currentEnd']]
        assert tree_sha(ast.Module(body=selected, type_ignores=[])) == delta['currentAstSha256'], 'Exact positioned capture addition changed'
        replacement = ast.parse(delta['previousSource']).body
        assert tree_sha(ast.Module(body=replacement, type_ignores=[])) == delta['previousAstSha256']
        capture.body[delta['currentStart']:delta['currentEnd']] = replacement
    assert tree_sha(capture) == value['capturePreviousSha256'], 'Entire original capture did not restore'
    helpers = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in value['helperNames']]
    assert [node.name for node in helpers] == value['helperNames'], 'Fresh-observation helpers missing or duplicated'
    first = tree.body.index(helpers[0])
    assert tree.body[first:first + len(helpers)] == helpers and first > 0
    assert isinstance(tree.body[first - 1], ast.FunctionDef) and tree.body[first - 1].name == 'dump'
    after = tree.body[first + len(helpers)]
    assert isinstance(after, ast.FunctionDef) and after.name == 'click', 'Fresh-observation helpers moved'
    for node in helpers:
        assert tree_sha(node) == value['helperSha256'][node.name], 'Fresh-observation helper changed'
    del tree.body[first:first + len(helpers)]
    assert tree_sha(tree) == value['allowedModulePairs'][current], 'Complete original UI AST did not restore'
    return tree


def wrap_runner_ast(original):
    @functools.wraps(original)
    def observed_ui_tree(tree):
        original_runner_tree(tree)
        return original(tree)
    return observed_ui_tree
