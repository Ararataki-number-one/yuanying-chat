"""Finite download-workspace inputs for retained historical source oracles.

The original Android runner, Java methods, observer and v1 evidence reader are
never replaced at execution. Only named historical readers use these inverses.
Unknown complete bytes or ASTs do not gain acceptance from this module.
"""
import ast
import copy
import functools
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/ui-download-workspace-v2-source-deltas.json'
FIXTURE_SHA256 = '474a0aa459c92a94cdbc3fe4f89bf738e7dc5fc1f8bc14ab871100c1984fe479'
BASE_COMMIT = '62b37a9c52b899ce593a9cec85050d70fb32e56e'
BASE_TREE = 'bc1e7d6844ec6bd0b4a34a9be321e55140cf32da'
RUNNER = 'tests/gecko/run_ui_visuals.py'
ACTIVITY = 'tests/gecko/UiVisualIntegrationActivity.java'
HOST = 'tests/gecko_ui_visual_capture_test.py'
# Whole before/after images independently verified against local real Git
# objects when this finite fixture was prepared. No Git/network access at run.
IDENTITIES = {
    RUNNER: (47085, '075279cecd6cadb4fa51b6f866b0779618cf78125dc6b30a7c1149e13408c5a9',
             '5c66f4e99bcab0240f819ad9835d62ac47414e4c', 47569,
             '824a4c8b8cc39d0d256018251de0b12fb0897656a3c1b82513a5e7a0ce5058af',
             'f9ee33dfa16151fcee93a133d508619ca06f7340'),
    ACTIVITY: (13373, '04f629d6053d1fc62bdddd590c4b405ddff2d564fd4dc3211332c849da0a4366',
               'be0704e74cc2f106dc1c765c909cf17c33e6f0dc', 13769,
               '89914f5692e9eefbc6e379108c0f97a471eeee6002d24ee4fc79417babe693f1',
               '13be2e3ce783c3d745f5e346be4566868ccdd1de'),
    HOST: (40714, '7c7918b3f0457c54df0cbb9e219931c5add087b8babef34611fa972ed273e0c4',
           'b02b389ee35c5d218b96a12801a184d8aa45fcea', 41130,
           '6827f7a4179243dd628af30c07ae2c1c32dbafce96695389a564ba4723b5c155',
           '94bbd9d25e420967604d2042368ec644d6c19c26'),
    'tests/ui_workspace_v2_source_compatibility.py': (
        8281, '8a4c0813116dee434c7266287c8be1c760d9b6a4f2fc53fef8022bd0830a4b43',
        'f796c6350a32ac1916650e40801a2c70ce3606d8', 9032,
        'd8096bd8ee28b637bc0975464feace9336cb716575ddbbe89018e49fd6b52164',
        '99f4dc287d325d510ffc6b2e8170e0361e895d0d'),
    'tests/ui_checkpoint_source_compatibility.py': (
        14535, '21055368f18ae0bce416e54fe198730089f3d50be11290a16f77c2bed0d3813d',
        '00e322b4fdbb5682a05d61bd8a3d2c1d429aef16', 14787,
        'd6629d40dedef6fd2b3eb9ff454291ced87075a6a857e62ce928e711731eacf5',
        'adef97f0fb3bff205d8d175a1c7fcde9bff6f654'),
    'tests/ui_workspace_v2_source_controls.py': (
        12328, '94aff2a1b309855b213921e314a425c2611908c4617beb0b9d7808cbf19462d5',
        '24272aa6c7a0abdc87e5fce27a8f45b021c7ae40', 12451,
        '7aa35280ee7cd90ac17d46de08bffe3d0eed192841759606eea4d73af678cf93',
        '40041260cd937b3a011c24687a6a7822a22d5c4c'),
    'tests/profile_ui_navigation_source_compatibility_test.py': (
        6017, 'acebb72bd6490634196638378fb58344d10159ef4b12809af0a9468743d5d140',
        '6b43c722e01bad9a708d3dd896dc2e6e8fb262f7', 6139,
        'd301f34032263630c16e090899645049a544978594f0aabc62497e0c97d2ce6e',
        '292c50d9b2edbea23da3bd366080b2e116315046'),
    'tests/gecko-ui-download-observer-host/ObserverCases.java.in': (
        15089, '2a143bef99b5f36bbd2a65d374e0ba58a3d7b6052d7232ea3e1a9c1c45639c76',
        'dbec2eab67d22525b4adb12c6c6a9fd93e572f19', 15359,
        '9dfffc6eeff308c16e1ec8c1c2d74f6c1c18895664ad92e35a812cdd4a5ce70e',
        '6f26f60097e8fa85258919c017940944a1b0e8a9'),
}
AST_PAIRS = {
    'b68a6289ce943dbca67e654d4d6cd3572c8cec6b71aff31cdb4efb0bc2240217':
        '5fbe79ffe0f0cfd37397814adb19efa27328d9cc41ab61d4b9493d41b19a062e',
    'b77dfa7a5611d3f850c5fb4192fecb4506cea7037b5c3ebb198676b289605e8f':
        'ca3d9bbe87f4645d9f25f6286b9ced0a2984bb05d7ec8013e7bfc2cff0b60dd2',
}
EDIT_IDS = ('owned-v2-capture-import', 'explicit-actual-v2-launch',
            'retained-v1-fresh-observation', 'versioned-v2-evidence-dispatch')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def blob(raw):
    return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()


def tree_sha(tree):
    return sha(ast.dump(tree, include_attributes=False).encode())


def manifest():
    assert FIXTURE.is_file() and not FIXTURE.is_symlink(), 'Ordinary owned download source fixture required'
    raw = FIXTURE.read_bytes()
    assert (len(raw), sha(raw)) == (30064, FIXTURE_SHA256), 'Unreviewed complete download source fixture'
    value = json.loads(raw)
    assert set(value) == {'schema', 'kind', 'baseCommit', 'baseTree', 'actualAndroidExecution', 'runtimeAcceptance', 'files', 'runnerAst'}
    assert type(value['schema']) is int and value['schema'] == 1
    assert value['kind'] == 'download-workspace-v2-historical-source-input-only'
    assert (value['baseCommit'], value['baseTree']) == (BASE_COMMIT, BASE_TREE)
    assert value['actualAndroidExecution'] is value['runtimeAcceptance'] is False
    assert set(value['files']) == set(IDENTITIES)
    for path, row in value['files'].items():
        assert (row['previousBytes'], row['previousSha256'], row['previousGitBlob'],
                row['reviewedBytes'], row['reviewedSha256'], row['reviewedGitBlob']) == IDENTITIES[path]
        assert row['contextLines'] == 3 and 0 < len(row['deltas']) <= 6
        for index, delta in enumerate(row['deltas']):
            assert delta['id'] == 'context-%02d' % index
            for side in ('previous', 'current'):
                content = delta[side].encode()
                assert 0 < len(content) <= 8192
                assert (len(content), sha(content)) == (delta[side+'Bytes'], delta[side+'Sha256'])
    assert value['runnerAst']['allowedModulePairs'] == AST_PAIRS
    assert tuple(row['id'] for row in value['runnerAst']['edits']) == EDIT_IDS
    for edit in value['runnerAst']['edits']:
        for side in ('previous', 'current'):
            assert len(edit[side+'Source'].encode()) <= 8192
            parsed = ast.parse(edit[side+'Source'])
            assert (len(parsed.body), tree_sha(parsed)) == (edit[side+'Nodes'], edit[side+'AstSha256'])
        assert edit['currentNodes'] > 0
    return value


def source_input(raw, path):
    """Accept one complete reviewed image and restore its entire real 62b blob."""
    assert type(raw) is bytes and type(path) is str and path in IDENTITIES, 'Owned complete download source bytes required'
    row = manifest()['files'][path]
    assert (len(raw), sha(raw), blob(raw)) == (row['reviewedBytes'], row['reviewedSha256'], row['reviewedGitBlob']), 'Unreviewed complete download source'
    for delta in reversed(row['deltas']):
        current, previous = delta['current'].encode(), delta['previous'].encode()
        assert raw.count(current) == 1, 'Download source context is missing, repeated or relocated'
        raw = raw.replace(current, previous, 1)
    assert (len(raw), sha(raw), blob(raw)) == (row['previousBytes'], row['previousSha256'], row['previousGitBlob']), 'Entire original download source did not restore'
    return raw


def historical_input(raw, path):
    """Unknown input is unchanged so the original downstream oracle rejects it."""
    if (type(raw) is bytes and type(path) is str and path in IDENTITIES
            and (len(raw), sha(raw), blob(raw)) == IDENTITIES[path][3:]):
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
    """Only two complete current ASTs; no partial mutation on a rejected input."""
    assert type(tree) is ast.Module, 'Complete parsed download capture module required'
    current = tree_sha(tree)
    assert current in AST_PAIRS, 'Unreviewed complete download runner AST'
    restored = copy.deepcopy(tree)
    for edit in reversed(manifest()['runnerAst']['edits']):
        previous, reviewed = ast.parse(edit['previousSource']), ast.parse(edit['currentSource'])
        signatures = [ast.dump(node, include_attributes=False) for node in reviewed.body]
        matches = [(statements, index) for statements in _statement_lists(restored)
                   for index in range(len(statements)-len(signatures)+1)
                   if [ast.dump(node, include_attributes=False) for node in statements[index:index+len(signatures)]] == signatures]
        assert len(matches) == 1, 'One exact positioned download AST sequence required'
        statements, index = matches[0]
        statements[index:index+len(signatures)] = copy.deepcopy(previous.body)
    assert tree_sha(restored) == AST_PAIRS[current], 'Entire original download AST did not restore'
    tree.body, tree.type_ignores = restored.body, restored.type_ignores
    return tree


def historical_tree(tree):
    assert type(tree) is ast.Module, 'Complete parsed UI module required'
    references = [node for node in ast.walk(tree)
                  if isinstance(node, ast.Name) and node.id == 'capture_download_workspace'
                  or isinstance(node, ast.ImportFrom) and node.module == 'download_workspace_v2'
                  or isinstance(node, ast.Constant) and node.value == 'visualDownloadContract']
    return original_runner_tree(tree) if references else tree


def wrap_bytes(original):
    @functools.wraps(original)
    def retained_source(raw, path):
        return original(historical_input(raw, path), path)
    return retained_source


def wrap_ast(original):
    @functools.wraps(original)
    def retained_tree(tree):
        return original(historical_tree(tree))
    return retained_tree


class _HistoricalSource:
    """A named local test read port, never a global Path patch or compiler input."""
    def __init__(self, path, relative):
        self.path, self.relative = path, relative

    def read_bytes(self):
        assert not self.path.is_symlink(), 'Historical source read must be an ordinary file'
        return historical_input(self.path.read_bytes(), self.relative)

    def read_text(self):
        return self.read_bytes().decode('utf-8', 'strict')

    def __fspath__(self):
        return str(self.path)


class _HistoricalRoot:
    def __init__(self, root, selected):
        self.root, self.selected = root, selected

    def __truediv__(self, relative):
        path = self.root / relative
        if type(relative) is str and relative in self.selected:
            return _HistoricalSource(path, relative)
        return path

    def __fspath__(self):
        return str(self.root)


def historical_root(root, selected):
    """Only the two retained test modules' exact, explicitly selected read sets."""
    assert isinstance(root, Path) and root == ROOT and not root.is_symlink()
    assert type(selected) is tuple and selected in ((RUNNER, HOST), (ACTIVITY,))
    return _HistoricalRoot(root, selected)


# Only historical readers invert the two final JSON whitespace choices.
# Actual capture execution and complete publication scans keep current bytes.
import importlib.util as _report_import
_report_spec = _report_import.spec_from_file_location('selected_ui_report_json_input', Path(__file__).with_name('ui_report_json_source_compatibility.py'))
_report_input = _report_import.module_from_spec(_report_spec)
_report_spec.loader.exec_module(_report_input)
source_input = _report_input.wrap_bytes(source_input)
historical_input = _report_input.wrap_bytes(historical_input)
original_runner_tree = _report_input.wrap_ast(original_runner_tree)
historical_tree = _report_input.wrap_ast(historical_tree)
