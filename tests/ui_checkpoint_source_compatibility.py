"""Exact checkpoint opt-out inverses for retained source oracles only.

Runtime hosts and the actual Android runner continue to use current bytes.
No original oracle, golden, device action, assertion or timeout is replaced.
"""
import ast
import functools
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/ui-checkpoint-source-deltas.json'
FIXTURE_SHA256 = '91559ec13f9f31aeafdc5f87d16b54c9780fe80a341081c00e75ee1a99173480'
RUNNER = 'tests/gecko/run_ui_visuals.py'
RUNNER_CURRENT_SHA256 = 'b85896aa5b94e33fb40bbada323d239a66f75c12a39bf9adb2a4ff3e3483e14d'
PREFERENCE_PREVIOUS_SHA256 = 'be5c80463eb66171fc49a0056bbff3b5a8d47fc88d193b4647e37e301857a9b4'
PREFERENCE_PREVIOUS = "expected={'保存本机输入草稿','恢复网页滚动位置','允许此环境的后台回复提醒','仅在 Wi-Fi 下载文件','自动清理 30 天以上的无引用中间文件'}"
PREFERENCE_CURRENT = "expected={'保存本机输入草稿','恢复网页滚动位置','允许此环境的后台回复提醒','仅在 Wi-Fi 下载文件','自动清理 30 天以上的无引用中间文件','自动检测外部网络响应'}"
WORKFLOW_CURRENT_SHA256 = 'a4ef3a60391eb6a9fc86dba2986fcd7f7fc053f9e32bc4818cc6e773d8c84435'
WORKFLOW_PREVIOUS_SHA256 = 'a0fdfae87d0b32ee1ab9479aacdbff81755e9e5fe45cfcaf92a8bce3e11a0069'
TLS_DOWNLOAD_PREVIOUS = '    - name: Collect independent TLS workload from the exact same build and run\n      uses: actions/download-artifact@634f93cb2916e3fdff6788551b99b062d0335ce0\n      with:\n        name: tls-${{ github.run_id }}-${{ github.run_attempt }}-android\n        path: work/tls-acceptance\n'
TLS_DOWNLOAD_CURRENT = '    - name: Collect independent TLS workload from the exact same build and run\n      uses: actions/download-artifact@634f93cb2916e3fdff6788551b99b062d0335ce0\n      with:\n        name: tls-${{ github.run_id }}-${{ github.run_attempt }}-android\n        path: work\n'
BASE_COMMIT = '4dd0f4434a40c010e060d9651a371a986b6bd2c4'
BASE_TREE = '3f2cd6b5fe591d6f9eda4822c0b5326c38baceeb'
PREVIOUS = {
    RUNNER: '65fb205cbb7a466858a0a1869cd4b5388f70026d4e09da078318827e92432f4f',
    'tests/gecko_ui_checkpoint_publication_test.py': '32769fd0108f37858aefe38fdd9336ddb1ef18e724f970999fa0044cd747d0a7',
    'tests/gecko_ui_visual_capture_test.py': '8ab2a6335b9f313e38cb52deb4b7265ee1be3e8fefc4009d5ef5c3825c40d0c6',
    'tests/ui_quick_sheet_source_compatibility.py': '5be2bc842cc093c92523aa05dc77aefd8e7a076dd95c6d4f7ac6e861ee66b047',
    'tests/profile_ui_quick_sheet_source_compatibility_test.py': '637ca4c120c9ccc3be460f7c1c7227bc467aecec654d8a7307ba12a9f0ce3e01',
}
FORWARDED_PATHS = frozenset(PREVIOUS) | frozenset((
    'tests/gecko/UiVisualIntegrationActivity.java', 'tests/gecko/DownloadLocationLayoutEvidence.java',
    'tests/ui_visual_preservation_contract.py', 'tests/ui_runner14_source_contract.py',
    'tests/profile_ui_settings_services11_test.py', 'tests/ui_observer_source_compatibility.py',
    'tests/profile_ui_observer_source_compatibility_test.py'))
FLAG_DECLARATION = "p.add_argument('--no-checkpoint-publication',action='store_true',help='Disable checkpoint publication for nonqualifying diagnostics');"
FLAG_RETURN = '    if args.no_checkpoint_publication:return\n'
NAVIGATION_PATH = 'tests/gecko/UiVisualIntegrationActivity.java'
NAVIGATION_FIXTURE = ROOT / 'tests/fixtures/ui-navigation-source-deltas.json'
NAVIGATION_FIXTURE_SHA256 = '98c2c894fc4eda4adc28d06064943af7b68a99e9c4270b2ed32dafc21bf80775'
NAVIGATION_CURRENT_SHA256 = '04f629d6053d1fc62bdddd590c4b405ddff2d564fd4dc3211332c849da0a4366'
NAVIGATION_PREVIOUS_SHA256 = '29d641025853a52cf00dbffb9fccad54126e33d04805f8f4dfe483fafb3180a5'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def tree_sha(tree):
    return sha(ast.dump(tree, include_attributes=False).encode())


def navigation_manifest():
    raw = NAVIGATION_FIXTURE.read_bytes()
    assert not NAVIGATION_FIXTURE.is_symlink() and len(raw) <= 32768 and sha(raw) == NAVIGATION_FIXTURE_SHA256, 'Exact bounded navigation source fixture required'
    value = json.loads(raw)
    assert type(value['schema']) is int and value['schema'] == 1 and value['path'] == NAVIGATION_PATH
    assert value['previousCommit'] == '03d0c4ace70942a3f6899daffac086cc6682885e'
    assert value['previousTree'] == 'bfd7bbcdf89ef947dd466dab795e94e83fc992c3'
    assert value['reviewedCommit'] == '4363dbc04df80d5c82ba966248e47a3fd69cbcc8'
    assert value['reviewedTree'] == '08189ae748eb1045ff21af4253369ef17d6bdad3'
    assert (value['previousBytes'], value['previousSha256']) == (12855, NAVIGATION_PREVIOUS_SHA256)
    assert (value['reviewedBytes'], value['reviewedSha256']) == (13373, NAVIGATION_CURRENT_SHA256)
    assert len(value['deltas']) == 5, 'Only five reviewed navigation source hunks are owned'
    return value


def navigation_source_input(raw, path):
    """Historical source assertions only; Android and host compilers read raw files.

    Restore the actual Source7 Git blob before the unchanged observer inverse.
    Whole-source pins reject moved context and every unreviewed byte before any
    hunk is reversed. This function is never a producer or compiler input.
    """
    assert type(raw) is bytes and type(path) is str and path == NAVIGATION_PATH, 'Complete owned navigation source bytes required'
    value = navigation_manifest()
    assert len(raw) == value['reviewedBytes'] and sha(raw) == NAVIGATION_CURRENT_SHA256, 'Unreviewed complete navigation source'
    for delta in reversed(value['deltas']):
        current, previous = delta['current'].encode(), delta['previous'].encode()
        assert 0 < len(current) <= 32768 and len(current) == delta['currentBytes'] and sha(current) == delta['currentSha256']
        assert 0 < len(previous) <= 32768 and len(previous) == delta['previousBytes'] and sha(previous) == delta['previousSha256']
        assert raw.count(current) == 1, 'Missing, repeated or moved exact navigation source hunk'
        raw = raw.replace(current, previous, 1)
    assert len(raw) == value['previousBytes'] and sha(raw) == NAVIGATION_PREVIOUS_SHA256, 'Entire actual Source7 Activity did not restore'
    return raw


def manifest():
    raw = FIXTURE.read_bytes()
    assert not FIXTURE.is_symlink() and len(raw) <= 65536 and sha(raw) == FIXTURE_SHA256, 'Exact bounded checkpoint source fixture required'
    value = json.loads(raw)
    assert value['schema'] == 1 and type(value['schema']) is int
    assert value['baseCommit'] == BASE_COMMIT and value['baseTree'] == BASE_TREE
    assert set(value['files']) == set(PREVIOUS), 'Finite checkpoint source paths required'
    assert all(row['previousSha256'] == PREVIOUS[path] for path, row in value['files'].items())
    assert value['files'][RUNNER]['reviewedSha256'] == RUNNER_CURRENT_SHA256
    return value


def source_input(raw, path):
    assert type(raw) is bytes and type(path) is str and path in PREVIOUS, 'Exact complete checkpoint source bytes and path required'
    row = manifest()['files'][path]
    assert len(raw) == row['reviewedBytes'] and sha(raw) == row['reviewedSha256'], 'Unreviewed complete checkpoint source'
    for delta in reversed(row['deltas']):
        current, previous = delta['current'].encode(), delta['previous'].encode()
        assert current and previous and raw.count(current) == 1, 'Missing, duplicate or moved checkpoint source delta'
        assert len(current) == delta['currentBytes'] and sha(current) == delta['currentSha256']
        assert len(previous) == delta['previousBytes'] and sha(previous) == delta['previousSha256']
        raw = raw.replace(current, previous, 1)
    assert len(raw) == row['previousBytes'] and sha(raw) == PREVIOUS[path], 'Entire pre-opt-out source did not restore'
    return raw


def checkpoint_runner_input(raw):
    """Only the source-oracle LHS: restore the exact pre-sixth-label runner.

    Actual capture, parser and checkpoint hosts still compile current bytes.
    """
    assert type(raw) is bytes and sha(raw) == RUNNER_CURRENT_SHA256, 'Actual frozen six-control UI runner required'
    current, previous = PREFERENCE_CURRENT.encode(), PREFERENCE_PREVIOUS.encode()
    assert raw.count(current) == 1, 'Exact Preferences literal required'
    restored = raw.replace(current, previous, 1)
    assert sha(restored) == PREFERENCE_PREVIOUS_SHA256, 'Entire pre-sixth-label runner did not restore'
    return restored


def checkpoint_workflow_input(raw):
    """Source-oracle LHS only: inverse the one reviewed artifact download root."""
    assert type(raw) is bytes and sha(raw) == WORKFLOW_CURRENT_SHA256, 'Actual frozen TLS download workflow required'
    current, previous = TLS_DOWNLOAD_CURRENT.encode(), TLS_DOWNLOAD_PREVIOUS.encode()
    assert raw.count(current) == 1, 'One exact named TLS download root required'
    restored = raw.replace(current, previous, 1)
    assert sha(restored) == WORKFLOW_PREVIOUS_SHA256, 'Entire original canonical workflow did not restore'
    return restored


def require_current_runner(raw):
    assert type(raw) is bytes and sha(raw) == RUNNER_CURRENT_SHA256, 'Actual frozen checkpoint opt-out runner required'
    return source_input(raw, RUNNER)


def history_input(raw, path):
    """Forward unknown inputs unchanged to the existing strict source guards."""
    assert type(raw) is bytes and type(path) is str and path in FORWARDED_PATHS
    if path == NAVIGATION_PATH and sha(raw) == NAVIGATION_CURRENT_SHA256:
        return navigation_source_input(raw, path)
    if path in PREVIOUS and sha(raw) == manifest()['files'][path]['reviewedSha256']:
        return source_input(raw, path)
    return raw


def original_runner_tree(tree):
    assert type(tree) is ast.Module, 'Complete parsed UI module required'
    assert len([n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'capture']) == 1
    assert len([n for n in tree.body if isinstance(n, ast.Try) and n.finalbody]) == 1, 'Complete UI workload required, not an excerpt'
    references = [n for n in ast.walk(tree)
                  if isinstance(n, ast.Constant) and n.value == '--no-checkpoint-publication'
                  or isinstance(n, ast.Attribute) and n.attr == 'no_checkpoint_publication']
    if not references:
        return tree
    value = manifest()['runnerAst']
    current = tree_sha(tree)
    assert current in value['allowedModulePairs'], 'Unreviewed complete checkpoint UI AST'
    declared = ast.parse(FLAG_DECLARATION).body[0]
    positions = [i for i, n in enumerate(tree.body) if ast.dump(n, include_attributes=False) == ast.dump(declared, include_attributes=False)]
    assert len(positions) == 1, 'One top-level opt-out declaration required'
    position = positions[0]
    serial = ast.parse("p.add_argument('--serial',required=True)").body[0]
    parsed = ast.parse('args=p.parse_args()').body[0]
    assert position > 0 and position + 1 < len(tree.body)
    assert ast.dump(tree.body[position-1], include_attributes=False) == ast.dump(serial, include_attributes=False)
    assert ast.dump(tree.body[position+1], include_attributes=False) == ast.dump(parsed, include_attributes=False), 'Opt-out parser declaration moved'
    checkpoint = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'checkpoint']
    assert len(checkpoint) == 1 and tree_sha(checkpoint[0]) == value['checkpointReviewedSha256']
    expected = ast.parse(FLAG_RETURN.strip()).body[0]
    assert len(checkpoint[0].body) == 4 and ast.dump(checkpoint[0].body[2], include_attributes=False) == ast.dump(expected, include_attributes=False), 'Opt-out must follow the original checkpoint write'
    del checkpoint[0].body[2]
    assert tree_sha(checkpoint[0]) == value['checkpointPreviousSha256'], 'Original complete checkpoint did not restore'
    del tree.body[position]
    capture = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'capture')
    expected = ast.parse(PREFERENCE_CURRENT).body[0]
    preferences = [n for n in capture.body if isinstance(n, ast.If) and len(n.body) > 2
                   and tree_sha(n.body[2]) == tree_sha(expected)
                   and ast.dump(n.test, include_attributes=False) == ast.dump(ast.parse("scene=='preferences'", mode='eval').body, include_attributes=False)]
    assert len(preferences) == 1, 'Exact Preferences capture branch required'
    assert len(preferences[0].body) > 2 and tree_sha(preferences[0].body[2]) == tree_sha(expected), 'Six-control expectation moved or changed'
    preferences[0].body[2] = ast.parse(PREFERENCE_PREVIOUS).body[0]
    assert tree_sha(tree) == value['allowedModulePairs'][current], 'Entire pre-opt-out AST did not restore'
    return tree


def wrap_bytes(original):
    @functools.wraps(original)
    def checkpoint_source(raw, path):
        return original(history_input(raw, path), path)
    return checkpoint_source


def wrap_ast(original):
    @functools.wraps(original)
    def checkpoint_tree(tree):
        original_runner_tree(tree)
        return original(tree)
    return checkpoint_tree


# Only historical workflow comparisons reverse the exact reviewed transport.
import importlib.util as _gradle_transport_import
_gradle_transport_spec = _gradle_transport_import.spec_from_file_location('selected_gradle_transport_source_input', Path(__file__).with_name('gradle_transport_source_compatibility.py'))
_gradle_transport_input = _gradle_transport_import.module_from_spec(_gradle_transport_spec)
_gradle_transport_spec.loader.exec_module(_gradle_transport_input)
checkpoint_transport_input = _gradle_transport_input.canonical_history_input
checkpoint_workflow_input = _gradle_transport_input.wrap_checkpoint_workflow(checkpoint_workflow_input)


# Only historical Activity guards reverse the exact empty preparation route.
import importlib.util as _preparation_import
_preparation_spec = _preparation_import.spec_from_file_location('selected_ui_preparation_source_input', Path(__file__).with_name('ui_preparation_source_compatibility.py'))
_preparation_input = _preparation_import.module_from_spec(_preparation_spec)
_preparation_spec.loader.exec_module(_preparation_input)
navigation_source_input = _preparation_input.wrap_source(navigation_source_input)
history_input = _preparation_input.wrap_source(history_input)
