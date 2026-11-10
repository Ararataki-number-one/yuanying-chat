"""Finite final-report whitespace inputs for retained historical source oracles.

Only two final writers changed. No capture, assertion, reader, privacy limit or
checkpoint is replaced. Complete selected bytes and both existing complete AST
forms restore their exact 89729eb inputs before the unchanged old guards run.
Unknown inputs remain unknown; this module never establishes Android success.
"""
import ast
import copy
import functools
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_COMMIT = '89729eb2c079d40237ecd466c7444da934206d98'
BASE_TREE = '583db08f6595ddc8e5a387e5cc035de1e70cb690'
RUNNER = 'tests/gecko/run_ui_visuals.py'
PORT = 'tests/ui_download_workspace_v2_source_compatibility.py'
HOST = 'tests/profile_ui_download_workspace_v2_source_compatibility_test.py'
IDENTITIES = {
    RUNNER: (47569, '824a4c8b8cc39d0d256018251de0b12fb0897656a3c1b82513a5e7a0ce5058af',
             'f9ee33dfa16151fcee93a133d508619ca06f7340', 47593,
             '14704dde1ec60b4768080d2e322d53602abd044cab192afb15f28d5deed91b69',
             '4f1fae4724fcb6755dc7947492aca6b493e05912'),
    PORT: (11203, 'e6fd7cf1ed3e66b1bd9d9a1ddb179e6e5b1bcd9a496cbcf2b548ed7385ee5997',
           '685574533c686a4a5e478484b18d604bb0165356', 11901,
           '26108b975ae6916a658eccc3f3899708a5885227d6ffc25b2ba29dd90dfcc21b',
           '905c03d09c6972448cd3f83e2d6843750cf8ac7b'),
    HOST: (15802, '5e7fc5d14aeb2adb1c436a42da8921f344fab2f36f6bd6dfb7d9e637c0a66485',
           '18e5e880926e577cdfcdb8f4af5f5bfbeea977d2', 15916,
           '71e1ad67ef94bf460c6105a55f4553969a8dadf613e3af37d72500ee86b8903b',
           '4ea2a1c097c25f526223be8862d81a66662f7a8f'),
}
WRITERS_BEFORE = (
    "(out/'compact-chrome-results.json').write_text(json.dumps({'status':'passed','actualAndroidExecution':True,'sourceCommit':source,'cases':compact,'reloadConfirmation':reload_confirmation,'autoCollapse':auto_collapse},ensure_ascii=False,indent=2)+'\\n')",
    "(out/'ui-visual-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\\n')",
)
WRITERS_AFTER = tuple(value.replace('indent=2', "separators=(',',':')") for value in WRITERS_BEFORE)
PORT_APPEND = '''

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
'''
HOST_BEFORE = '''import ui_download_workspace_v2_source_compatibility as current

ROOT = Path(__file__).resolve().parents[1]
'''
HOST_AFTER = '''import ui_download_workspace_v2_source_compatibility as current
from ui_report_json_source_compatibility import historical_root as report_historical_root

ROOT = report_historical_root(Path(__file__).resolve().parents[1])
'''
DELTAS = {
    RUNNER: tuple((indent + before + '\n', indent + after + '\n')
                  for indent, before, after in zip(('    ', '        '), WRITERS_BEFORE, WRITERS_AFTER)),
    PORT: (('    return _HistoricalRoot(root, selected)\n',
            '    return _HistoricalRoot(root, selected)\n' + PORT_APPEND),),
    HOST: ((HOST_BEFORE, HOST_AFTER),),
}
AST_PAIRS = {
    'cbc4da15a4bc0a47210b4186d6dfc6f38470b72e553e7736f63e39f45ca25f7d':
        'b68a6289ce943dbca67e654d4d6cd3572c8cec6b71aff31cdb4efb0bc2240217',
    'ab6ad8a8f7ce9d0ffb6df7b982cc756bc725f7075c918ec5cf90ae7611927ae1':
        'b77dfa7a5611d3f850c5fb4192fecb4506cea7037b5c3ebb198676b289605e8f',
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def identity(raw):
    return len(raw), sha(raw), hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()


def tree_sha(tree):
    return sha(ast.dump(tree, include_attributes=False).encode())


def source_input(raw, path):
    """Invert only a complete reviewed image, including the two named ports."""
    assert type(raw) is bytes and type(path) is str and path in IDENTITIES, 'Owned complete report source required'
    assert identity(raw) == IDENTITIES[path][3:], 'Unreviewed complete report source'
    selected = raw
    for before, after in reversed(DELTAS[path]):
        assert raw.count(after.encode()) == 1, 'Report source block missing, repeated or relocated'
        raw = raw.replace(after.encode(), before.encode(), 1)
    assert identity(raw) == IDENTITIES[path][:3], 'Entire original report source did not restore'
    forward = raw
    for before, after in DELTAS[path]:
        assert forward.count(before.encode()) == 1, 'Original report source block is not unique'
        forward = forward.replace(before.encode(), after.encode(), 1)
    assert forward == selected, 'Report source roundtrip changed bytes'
    return raw


def historical_input(raw, path):
    if type(raw) is bytes and type(path) is str and path in IDENTITIES and identity(raw) == IDENTITIES[path][3:]:
        return source_input(raw, path)
    return raw


def _statement_lists(node):
    for _, value in ast.iter_fields(node):
        if isinstance(value, list):
            if value and all(isinstance(item, ast.stmt) for item in value):
                yield value
            for item in value:
                if isinstance(item, ast.AST):
                    yield from _statement_lists(item)
        elif isinstance(value, ast.AST):
            yield from _statement_lists(value)


def original_runner_tree(tree):
    """Validate the entire selected AST before changing either writer node."""
    assert type(tree) is ast.Module, 'Complete report runner AST required'
    selected = tree_sha(tree)
    assert selected in AST_PAIRS, 'Unreviewed complete report runner AST'
    restored = copy.deepcopy(tree)
    for before, after in zip(WRITERS_BEFORE, WRITERS_AFTER):
        expected = ast.dump(ast.parse(after).body[0], include_attributes=False)
        matches = [(parts, index) for parts in _statement_lists(restored)
                   for index, node in enumerate(parts) if ast.dump(node, include_attributes=False) == expected]
        assert len(matches) == 1, 'Exactly one selected final report writer required'
        parts, index = matches[0]
        parts[index] = ast.parse(before).body[0]
    assert tree_sha(restored) == AST_PAIRS[selected], 'Entire original report runner AST did not restore'
    tree.body, tree.type_ignores = restored.body, restored.type_ignores
    return tree


def historical_tree(tree):
    assert type(tree) is ast.Module, 'Complete parsed report runner required'
    return original_runner_tree(tree) if tree_sha(tree) in AST_PAIRS else tree


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
    def __init__(self, path):
        self.path = path

    def is_symlink(self):
        return self.path.is_symlink()

    def read_bytes(self):
        assert not self.is_symlink(), 'Ordinary named historical runner required'
        return historical_input(self.path.read_bytes(), RUNNER)

    def read_text(self):
        return self.read_bytes().decode('utf-8', 'strict')

    def __fspath__(self):
        return str(self.path)


class _HistoricalRoot(type(ROOT)):
    """A local Path-shaped read port keeps the old root identity assertions."""
    def __truediv__(self, relative):
        path = Path(self) / relative
        if self == ROOT and type(relative) is str and relative == RUNNER:
            return _HistoricalSource(path)
        return path


def historical_root(root):
    """Only the retained download source test reads its named prior runner."""
    assert type(root) is type(ROOT) and root == ROOT and not root.is_symlink(), 'Exact local historical test root required'
    return _HistoricalRoot(root)
