"""Finite QuickSheet input inverse before unchanged historical UI oracles.

Actual runner and host execution keep current bytes. The forwarding input port
grants no acceptance: every unrecognized input still reaches the original guard.
"""
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/ui-quick-sheet-source-deltas.json'
FIXTURE_SHA256 = 'c0588f2e30e6250bb446ecf472ffe3c2d7f3bf77c471d3cc16cdf845deb385e4'
BASE_COMMIT = '03d0c4ace70942a3f6899daffac086cc6682885e'
BASE_TREE = 'bfd7bbcdf89ef947dd466dab795e94e83fc992c3'
RUNNER = 'tests/gecko/run_ui_visuals.py'
PREVIOUS = {
    RUNNER: '8816b3f7b36b59d1aac21827bbe06833ae6843462940c025dd3ba918efe6b81a',
    'tests/ui_observer_source_compatibility.py': '4521e34e43eea33a88dd9897f9cf6c562c97149def13d6c173279c6ca511745b',
    'tests/profile_ui_observer_source_compatibility_test.py': '8d92b22bc6ccea310d7dc066e6a844464d8d2c568d6d5df77d557ece156621d6',
}
HISTORY_PATHS = frozenset((RUNNER, 'tests/gecko/UiVisualIntegrationActivity.java',
    'tests/gecko/DownloadLocationLayoutEvidence.java', 'tests/ui_visual_preservation_contract.py',
    'tests/ui_runner14_source_contract.py', 'tests/profile_ui_settings_services11_test.py'))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def tree_sha(tree):
    return sha(ast.dump(tree, include_attributes=False).encode())


def manifest():
    raw = FIXTURE.read_bytes()
    assert len(raw) <= 32768 and sha(raw) == FIXTURE_SHA256, 'Exact bounded QuickSheet source fixture required'
    value = json.loads(raw)
    assert type(value['schema']) is int and value['schema'] == 1
    assert value['baseCommit'] == BASE_COMMIT and value['baseTree'] == BASE_TREE
    assert set(value['files']) == set(PREVIOUS), 'Finite QuickSheet source paths required'
    assert all(value['files'][path]['previousSha256'] == previous for path, previous in PREVIOUS.items())
    return value


def source_input(raw, path):
    assert type(raw) is bytes and type(path) is str and path in PREVIOUS, 'Exact current bytes and owned QuickSheet source path required'
    row = manifest()['files'][path]
    assert len(raw) == row['reviewedBytes'] and sha(raw) == row['reviewedSha256'], 'Unreviewed complete QuickSheet source'
    for delta in reversed(row['deltas']):
        current, previous = delta['current'].encode(), delta['previous'].encode()
        assert current and previous and raw.count(current) == 1, 'Exact positioned QuickSheet source delta required once'
        raw = raw.replace(current, previous, 1)
    assert len(raw) == row['previousBytes'] and sha(raw) == PREVIOUS[path], 'Entire committed Source7 input did not restore'
    return raw


def history_input(raw, path):
    """Map only exact new runner bytes; retain the original guard for all else."""
    assert type(raw) is bytes and type(path) is str and path in HISTORY_PATHS
    if path == RUNNER and sha(raw) == manifest()['files'][RUNNER]['reviewedSha256']:
        return source_input(raw, RUNNER)
    return raw


def original_runner_tree(tree):
    assert type(tree) is ast.Module, 'Complete parsed UI runner required'
    assert len([node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'capture']) == 1
    outer = [node for node in tree.body if isinstance(node, ast.Try) and node.finalbody]
    assert len(outer) == 1, 'Complete UI workload required, never an excerpt'
    names = {'quick_environment_sheet', 'management_navigation', 'environment_sheet'}
    references = [node for node in ast.walk(tree)
                  if isinstance(node, ast.Name) and node.id in names
                  or isinstance(node, ast.FunctionDef) and node.name in names]
    if not references:
        return tree
    value = manifest()['runnerAst']
    current = tree_sha(tree)
    assert current in value['allowedModulePairs'], 'Unreviewed complete QuickSheet AST'
    body = outer[0].body
    start, end = value['currentStart'], value['currentEnd']
    assert start > 0 and isinstance(body[start - 1], ast.FunctionDef) and body[start - 1].name == 'visible'
    selected = ast.Module(body=body[start:end], type_ignores=[])
    assert tree_sha(selected) == value['currentBlockSha256'], 'Exact positioned QuickSheet helper and compact loop required'
    replacement = ast.parse(value['previousSource'])
    assert tree_sha(replacement) == value['previousBlockSha256']
    body[start:end] = replacement.body
    assert tree_sha(tree) == value['allowedModulePairs'][current], 'Complete committed Source7 AST did not restore'
    return tree

# CPU latency preference changes affect historical metadata only.
import importlib.util as _cpu_util
_cpu_spec = _cpu_util.spec_from_file_location('_quick_cpu_metadata', ROOT/'tests/cpu_source_compatibility.py')
_cpu_metadata = _cpu_util.module_from_spec(_cpu_spec)
_cpu_spec.loader.exec_module(_cpu_metadata)
source_input = _cpu_metadata.wrap_bytes(source_input)
history_input = _cpu_metadata.wrap_bytes(history_input)
original_runner_tree = _cpu_metadata.wrap_tree(original_runner_tree)
