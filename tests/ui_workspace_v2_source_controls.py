"""Fixed-cohort UI-v2 source controls, loaded by the original checkpoint suite.

These are source and controlled-host checks, never Android/device acceptance.
"""
import ast
import copy
import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import ui_workspace_v2_source_compatibility as current
from historical_source_inputs import historical_bytes
from ui_download_workspace_v2_source_compatibility import historical_input as download_history_input


ROOT = Path(__file__).resolve().parents[1]


def historical_workspace_input(path):
    """Original versioned proofs use verified release bytes, never execution."""
    return download_history_input(historical_bytes(path), path)
PREPARATION = ("from ui_test_device import prepare_workflow as prepare_ui_test_device\n"
               "(out/'ui-test-device-isolation.json').write_text(json.dumps(prepare_ui_test_device(adb,serial=args.serial,environment=os.environ),sort_keys=True,indent=2)+'\\n')\n")
LOAD_TESTS = """def load_tests(loader, tests, pattern):
    import ui_workspace_v2_source_controls
    tests.addTests(loader.loadTestsFromModule(ui_workspace_v2_source_controls))
    return tests


"""


def committed(path):
    return subprocess.check_output(['git', 'show', current.BASE_COMMIT+':'+path], cwd=ROOT)


def assertions(raw):
    return [ast.dump(node, include_attributes=False) for node in ast.walk(ast.parse(raw))
            if isinstance(node, ast.Assert) or isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute) and node.func.attr.startswith('assert')]


class UiWorkspaceV2SourceControls(unittest.TestCase):
    def test_exact_current_files_restore_real_c244_git_blobs_and_forward_roundtrip(self):
        self.assertEqual(subprocess.check_output(['git', 'rev-parse', current.BASE_COMMIT+'^{tree}'], cwd=ROOT, text=True).strip(), current.BASE_TREE)
        for path, row in current.manifest()['files'].items():
            raw, original = historical_workspace_input(path), committed(path)
            with self.subTest(path=path):
                self.assertEqual((len(raw), current.sha(raw)), (row['reviewedBytes'], row['reviewedSha256']))
                self.assertEqual(current.source_input(raw, path), original)
                self.assertEqual(current.historical_input(raw, path), original)
                self.assertIs(current.historical_input(original, path), original)
                self.assertEqual(hashlib.sha1(b'blob '+str(len(original)).encode()+b'\0'+original).hexdigest(), row['previousGitBlob'])
                for delta in row['deltas']:
                    previous, after = delta['previous'].encode(), delta['current'].encode()
                    self.assertEqual(original.count(previous), 1)
                    original = original.replace(previous, after, 1)
                self.assertEqual(original, raw)

    def test_whole_bytes_missing_duplicate_relocated_changed_and_legacy_images_reject(self):
        for path, row in current.manifest()['files'].items():
            raw = historical_workspace_input(path)
            candidates = [b'', raw[:1024], raw+b' ', committed(path)]
            for delta in row['deltas']:
                chunk = delta['current'].encode()
                remaining = raw.replace(chunk, b'', 1)
                moved = remaining+chunk
                if moved == raw:moved = chunk+remaining
                candidates.extend((remaining, raw.replace(chunk, chunk*2, 1),
                                   raw.replace(chunk, chunk+b' ', 1), moved))
            for candidate in candidates:
                self.assertNotEqual(candidate, raw)
                with self.subTest(path=path, sha=current.sha(candidate)), self.assertRaises(AssertionError):
                    current.source_input(candidate, path)

    def test_unknown_forwarded_inputs_still_fail_the_original_runner_guards(self):
        import ui_checkpoint_source_compatibility as checkpoint
        import ui_quick_sheet_source_compatibility as quick
        raw = historical_workspace_input(current.RUNNER)
        for value in (b'', raw[:200], raw+b' ', raw.replace(b'UI_NAVIGATION_CONTRACT=2', b'UI_NAVIGATION_CONTRACT=1', 1)):
            self.assertIs(current.historical_input(value, current.RUNNER), value)
            for guard in (checkpoint.require_current_runner, checkpoint.checkpoint_runner_input):
                with self.assertRaises(AssertionError):guard(value)
            with self.assertRaises(AssertionError):quick.source_input(value, current.RUNNER)

    def test_two_complete_ast_variants_and_formatting_keep_all_old_oracles(self):
        import ui_visual_preservation_contract as original_ui
        raw = historical_workspace_input(current.RUNNER).decode('utf-8')
        original = committed(current.RUNNER).decode()
        for after, before in ((raw, original), (raw.replace(PREPARATION, '', 1), original.replace(PREPARATION, '', 1))):
            for selected in (after, '# coding: utf-8\n# formatting only\n'+ast.unparse(ast.parse(after))+'\n'):
                tree = ast.parse(selected.encode())
                restored = current.original_runner_tree(tree)
                self.assertIs(restored, tree)
                self.assertEqual(ast.dump(restored, include_attributes=False), ast.dump(ast.parse(before), include_attributes=False))
                receipt = original_ui.verify_shared_ui_source(selected)
                self.assertEqual(receipt['normalizedModuleAstSha256'], '5c528802063ccba23d6cc0c36726c8ad3fee41efa44aef29c9f498f8b8e331f1')
                self.assertEqual(receipt['normalizedCaptureAstSha256'], '7bfb8cf6cabcce321ba9841a216dbb035f97ceee76384191d55543c80ebaf4d5')
                self.assertFalse(receipt['actualAndroidExecution'])

    def test_every_new_ast_block_missing_duplicate_moved_or_changed_rejects_before_mutation(self):
        raw = historical_workspace_input(current.RUNNER)
        for edit in current.manifest()['runnerAst']['edits']:
            reviewed = ast.parse(edit['currentSource']).body
            signatures = [ast.dump(n, include_attributes=False) for n in reviewed]
            for mutation in ('missing', 'duplicate', 'moved', 'altered'):
                tree = ast.parse(raw)
                matches = [(statements, index) for statements in current._statement_lists(tree)
                           for index in range(len(statements)-len(reviewed)+1)
                           if [ast.dump(n, include_attributes=False) for n in statements[index:index+len(reviewed)]] == signatures]
                self.assertEqual(len(matches), 1)
                statements, index = matches[0]
                block = statements[index:index+len(reviewed)]
                if mutation == 'missing':del statements[index:index+len(reviewed)]
                elif mutation == 'duplicate':statements[index:index] = copy.deepcopy(block)
                elif mutation == 'moved':del statements[index:index+len(reviewed)];tree.body.extend(block)
                else:statements.insert(index, ast.parse('unreviewed_source_change = True').body[0])
                before = ast.dump(tree, include_attributes=False)
                with self.subTest(edit=edit['id'], mutation=mutation), self.assertRaises(AssertionError):
                    current.original_runner_tree(tree)
                self.assertEqual(ast.dump(tree, include_attributes=False), before)

    def test_old_counts_deadlines_source_binding_and_new_version_cannot_be_weakened(self):
        import ui_visual_preservation_contract as original_ui
        raw = historical_workspace_input(current.RUNNER).decode('utf-8')
        changes = (("assert '已选 8 个' in xml", 'assert True'),
                   ('deadline=time.monotonic()+35;readiness_scrolls=0', 'deadline=time.monotonic()+36;readiness_scrolls=0'),
                   ('verify_captures(records,source)', 'verify_captures(records)'),
                   ('UI_NAVIGATION_CONTRACT=2', 'UI_NAVIGATION_CONTRACT=1'),
                   ('navigation_contract=2)', 'navigation_contract=1)'),
                   ('conversation_header(xml,package,width,height,scale,\'日常会话\')', 'pass'))
        for before, after in changes:
            self.assertEqual(raw.count(before), 1)
            candidate = raw.replace(before, after, 1)
            with self.subTest(before=before), self.assertRaises(AssertionError):
                current.original_runner_tree(ast.parse(candidate))
            with self.assertRaises(AssertionError):original_ui.verify_shared_ui_source(candidate)

    def test_types_paths_excerpt_and_modified_fixture_never_gain_acceptance(self):
        raw = historical_workspace_input(current.RUNNER)
        for value in (None, raw.decode(), bytearray(raw), memoryview(raw)):
            with self.assertRaises(AssertionError):current.source_input(value, current.RUNNER)
        for path in (None, Path(current.RUNNER), '/'+current.RUNNER, '../'+current.RUNNER, 'another.py'):
            with self.assertRaises(AssertionError):current.source_input(raw, path)
        for tree in (None, ast.Module(body=[], type_ignores=[]), ast.parse('def capture():\n pass')):
            with self.assertRaises(AssertionError):current.original_runner_tree(tree)
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)/'fixture.json';fixture.write_bytes(current.FIXTURE.read_bytes()+b' ')
            with patch.object(current, 'FIXTURE', fixture), self.assertRaises(AssertionError):current.manifest()

    def test_capture_host_uses_current_constant_and_retains_every_original_class_method(self):
        import gecko_ui_visual_capture_test as host
        previous, selected = committed(current.HOST).decode(), historical_workspace_input(current.HOST).decode('utf-8')
        def methods(text):
            return {cls.name: {n.name: ast.get_source_segment(text, n) for n in cls.body if isinstance(n, ast.FunctionDef)}
                    for cls in ast.parse(text).body if isinstance(cls, ast.ClassDef)}
        self.assertEqual(methods(selected), methods(previous))
        module = host.runner_functions('capture')
        self.assertEqual(module.body[0].name, 'capture')
        self.assertEqual(len(module.body), 2)
        actual = next(n for n in ast.parse((ROOT/current.RUNNER).read_bytes()).body if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == 'UI_NAVIGATION_CONTRACT' for t in n.targets))
        self.assertEqual(ast.dump(module.body[1], include_attributes=False), ast.dump(actual, include_attributes=False))
        namespace = {};exec(compile(module, 'actual-v2-capture-host', 'exec'), namespace)
        self.assertEqual(namespace['UI_NAVIGATION_CONTRACT'], 2)

    def test_original_compatibility_guards_fixture_pins_and_assertions_are_unchanged(self):
        path = 'tests/ui_checkpoint_source_compatibility.py'
        before, selected = committed(path), (ROOT/path).read_bytes()
        self.assertTrue(selected.startswith(before))
        self.assertEqual(assertions(selected), assertions(before))
        for path in ('tests/fixtures/ui-checkpoint-source-deltas.json', 'tests/fixtures/ui-quick-sheet-source-deltas.json',
                     'tests/fixtures/ui-observer-source-deltas.json', 'tests/ui_quick_sheet_source_compatibility.py',
                     'tests/ui_observer_source_compatibility.py', 'tests/ui_runner14_source_contract.py',
                     'tests/ui_visual_preservation_contract.py'):
            self.assertEqual((ROOT/path).read_bytes(), committed(path), path)

    def test_only_explicit_historical_read_ports_and_original_suite_loading_are_added(self):
        path = 'tests/profile_ui_checkpoint_source_compatibility_test.py'
        before, selected = committed(path), historical_workspace_input(path)
        self.assertEqual(assertions(selected), assertions(before))
        ports = (
            (b'from ui_workspace_v2_source_compatibility import historical_input as workspace_input\n', b''),
            (b'        raw = workspace_input((ROOT / checkpoint.RUNNER).read_bytes(), checkpoint.RUNNER)\n', b'        raw = (ROOT / checkpoint.RUNNER).read_bytes()\n'),
            (b'            raw = workspace_input((ROOT / path).read_bytes(), path)\n', b'            raw = (ROOT / path).read_bytes()\n'),
            (LOAD_TESTS.encode(), b''),
        )
        for after, previous in ports:
            self.assertEqual(selected.count(after), 1)
            selected = selected.replace(after, previous, 1)
        self.assertEqual(selected, before)
        import profile_ui_checkpoint_source_compatibility_test as original_suite
        loaded = unittest.defaultTestLoader.loadTestsFromModule(original_suite)
        self.assertEqual(loaded.countTestCases(), 16)
