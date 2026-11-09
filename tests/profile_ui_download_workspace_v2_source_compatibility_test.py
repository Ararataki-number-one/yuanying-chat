"""Finite historical inputs; actual download UI acceptance is a separate gate."""
import ast
import copy
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import ui_download_workspace_v2_source_compatibility as current

ROOT = Path(__file__).resolve().parents[1]
PREPARATION = ("from ui_test_device import prepare_workflow as prepare_ui_test_device\n"
               "(out/'ui-test-device-isolation.json').write_text(json.dumps(prepare_ui_test_device(adb,serial=args.serial,environment=os.environ),sort_keys=True,indent=2)+'\\n')\n")
OWNED = frozenset((current.RUNNER, current.ACTIVITY, current.HOST,
    'tests/ui_workspace_v2_source_compatibility.py', 'tests/ui_checkpoint_source_compatibility.py',
    'tests/ui_workspace_v2_source_controls.py', 'tests/profile_ui_navigation_source_compatibility_test.py',
    'tests/gecko-ui-download-observer-host/ObserverCases.java.in'))


def assertions(raw):
    return [ast.dump(n, include_attributes=False) for n in ast.walk(ast.parse(raw))
            if isinstance(n, ast.Assert) or isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute) and n.func.attr.startswith('assert')]


def methods(raw):
    text = raw.decode()
    return {c.name: {n.name: ast.get_source_segment(text, n) for n in c.body if isinstance(n, ast.FunctionDef)}
            for c in ast.parse(raw).body if isinstance(c, ast.ClassDef)}


class DownloadWorkspaceHistoricalInputs(unittest.TestCase):
    def test_complete_images_restore_fixed_real_before_blobs_and_forward(self):
        manifest = current.manifest()
        self.assertEqual(set(manifest['files']), OWNED)
        self.assertEqual((current.BASE_COMMIT, current.BASE_TREE),
                         ('62b37a9c52b899ce593a9cec85050d70fb32e56e', 'bc1e7d6844ec6bd0b4a34a9be321e55140cf32da'))
        for path, row in manifest['files'].items():
            selected = (ROOT/path).read_bytes()
            with self.subTest(path=path):
                self.assertEqual((len(selected), current.sha(selected), current.blob(selected)), current.IDENTITIES[path][3:])
                before = current.source_input(selected, path)
                self.assertEqual((len(before), current.sha(before), current.blob(before)), current.IDENTITIES[path][:3])
                self.assertEqual(current.historical_input(selected, path), before)
                self.assertIs(current.historical_input(before, path), before)
                for delta in row['deltas']:
                    previous, after = delta['previous'].encode(), delta['current'].encode()
                    self.assertEqual(before.count(previous), 1)
                    before = before.replace(previous, after, 1)
                self.assertEqual(before, selected)

    def test_whole_bytes_missing_duplicate_moved_changed_and_old_images_fail_closed(self):
        for path, row in current.manifest()['files'].items():
            raw = (ROOT/path).read_bytes()
            candidates = [b'', raw[:1024], raw+b' ', current.source_input(raw, path)]
            for delta in row['deltas']:
                block = delta['current'].encode();remaining = raw.replace(block, b'', 1)
                moved = remaining+block
                if moved == raw:moved = block+remaining
                candidates.extend((remaining, moved, raw.replace(block, block*2, 1),
                                   raw.replace(block, block+b' ', 1)))
            for candidate in candidates:
                self.assertNotEqual(candidate, raw)
                with self.subTest(path=path, sha=current.sha(candidate)), self.assertRaises(AssertionError):
                    current.source_input(candidate, path)

    def test_two_complete_ast_forms_and_formatting_keep_original_oracles(self):
        import ui_visual_preservation_contract as original
        raw = (ROOT/current.RUNNER).read_text()
        before = current.source_input(raw.encode(), current.RUNNER).decode()
        self.assertEqual(raw.count(PREPARATION), 1)
        for after, previous in ((raw, before), (raw.replace(PREPARATION, '', 1), before.replace(PREPARATION, '', 1))):
            for selected in (after, '# coding: utf-8\n# formatting only\n'+ast.unparse(ast.parse(after))+'\n'):
                tree = ast.parse(selected.encode())
                self.assertIs(current.original_runner_tree(tree), tree)
                self.assertEqual(ast.dump(tree, include_attributes=False), ast.dump(ast.parse(previous), include_attributes=False))
                receipt = original.verify_shared_ui_source(selected)
                self.assertEqual(receipt['normalizedModuleAstSha256'], '5c528802063ccba23d6cc0c36726c8ad3fee41efa44aef29c9f498f8b8e331f1')
                self.assertEqual(receipt['normalizedCaptureAstSha256'], '7bfb8cf6cabcce321ba9841a216dbb035f97ceee76384191d55543c80ebaf4d5')
                self.assertFalse(receipt['actualAndroidExecution'])

    def test_every_ast_addition_rejects_missing_duplicate_moved_or_changed_before_mutation(self):
        import ui_visual_preservation_contract as original
        raw = (ROOT/current.RUNNER).read_bytes()
        for edit in current.manifest()['runnerAst']['edits']:
            expected = ast.parse(edit['currentSource']).body
            signatures = [ast.dump(n, include_attributes=False) for n in expected]
            for change in ('missing', 'duplicate', 'moved', 'altered'):
                tree = ast.parse(raw)
                matches = [(parts, i) for parts in current._statement_lists(tree)
                           for i in range(len(parts)-len(expected)+1)
                           if [ast.dump(n, include_attributes=False) for n in parts[i:i+len(expected)]] == signatures]
                self.assertEqual(len(matches), 1)
                parts, index = matches[0];block = parts[index:index+len(expected)]
                if change == 'missing':del parts[index:index+len(expected)]
                elif change == 'duplicate':parts[index:index] = copy.deepcopy(block)
                elif change == 'moved':del parts[index:index+len(expected)];tree.body.extend(block)
                else:parts.insert(index, ast.parse('unreviewed_download_change = True').body[0])
                before = ast.dump(tree, include_attributes=False)
                with self.subTest(edit=edit['id'], change=change), self.assertRaises(AssertionError):
                    current.original_runner_tree(tree)
                self.assertEqual(ast.dump(tree, include_attributes=False), before)
                with self.assertRaises(AssertionError):original.verify_shared_ui_source(ast.unparse(tree))

    def test_new_and_original_semantics_never_normalize_away(self):
        import ui_checkpoint_source_compatibility as navigation
        import ui_visual_preservation_contract as original
        cases = {
            current.RUNNER: (
                ("['--ei','visualDownloadContract','2']", "['--ei','visualDownloadContract','1']"),
                ('readiness_scrolls and UI_NAVIGATION_CONTRACT!=2', 'readiness_scrolls and UI_NAVIGATION_CONTRACT==2'),
                ('source,label_nonce,shots,stem,record)', 'None,label_nonce,shots,stem,record)'),
                ('deadline=time.monotonic()+35;readiness_scrolls=0', 'deadline=time.monotonic()+36;readiness_scrolls=0'),
                ('verify_captures(records,source)', 'verify_captures(records)'),
                ("assert '已选 8 个' in xml", 'assert True')),
            current.ACTIVITY: (
                ('downloadWorkspace.observe(request);return;', 'downloadWorkspace.observe(null);return;'),
                ('downloadWorkspace.close();', 'downloadWorkspace.toString();'),
                ('controller.setVisible(false);', 'controller.setVisible(true);'),
                ('downloadObservationNonces.contains(nonce)', 'false'),
                ('downloadWorkspace=new DownloadWorkspaceVisuals(this,root,nonce)', 'downloadWorkspace=new DownloadWorkspaceVisuals(this,root,null)')),
        }
        for path, changes in cases.items():
            source = (ROOT/path).read_text()
            for before, after in changes:
                self.assertEqual(source.count(before), 1)
                selected = source.replace(before, after, 1).encode()
                self.assertIs(current.historical_input(selected, path), selected)
                with self.subTest(path=path, before=before), self.assertRaises(AssertionError):current.source_input(selected, path)
                if path == current.RUNNER:
                    with self.assertRaises(AssertionError):navigation.require_current_runner(selected)
                    with self.assertRaises(AssertionError):original.verify_shared_ui_source(selected.decode())
                else:
                    with self.assertRaises(AssertionError):navigation.navigation_source_input(selected, path)
                    with self.assertRaises(AssertionError):original.verify_download_visual_fixture_source(selected)

    def test_original_assertions_class_methods_fixtures_and_observer_are_unchanged(self):
        for path in (current.HOST, 'tests/ui_workspace_v2_source_compatibility.py',
                     'tests/ui_checkpoint_source_compatibility.py', 'tests/ui_workspace_v2_source_controls.py',
                     'tests/profile_ui_navigation_source_compatibility_test.py'):
            raw = (ROOT/path).read_bytes();before = current.source_input(raw, path)
            with self.subTest(path=path):
                self.assertEqual(assertions(raw), assertions(before))
                self.assertEqual(methods(raw), methods(before))
        fixed = {
            'tests/fixtures/ui-workspace-v2-source-deltas.json': '49b9a00ad3eb6e9a001f70fef41342b65c0d8fedd67939d2546fb669d81878b0',
            'tests/fixtures/ui-checkpoint-source-deltas.json': '91559ec13f9f31aeafdc5f87d16b54c9780fe80a341081c00e75ee1a99173480',
            'tests/fixtures/ui-quick-sheet-source-deltas.json': 'c0588f2e30e6250bb446ecf472ffe3c2d7f3bf77c471d3cc16cdf845deb385e4',
            'tests/fixtures/ui-observer-source-deltas.json': '998637d381722c943cb32517cb1c72e092d0d0db7581e0f7c9103d74303b42c8',
            'tests/fixtures/ui-navigation-source-deltas.json': '98c2c894fc4eda4adc28d06064943af7b68a99e9c4270b2ed32dafc21bf80775',
            'tests/gecko/DownloadLocationLayoutEvidence.java': '31f238e1ca1a94b59cc924a4e21822d078da087687daf8885f4c467de6dfb77e',
        }
        for path, expected in fixed.items():self.assertEqual(current.sha((ROOT/path).read_bytes()), expected, path)

    def test_retained_v1_host_executes_current_ast_with_only_explicit_protocol_configuration(self):
        import gecko_ui_visual_capture_test as host
        raw = (ROOT/current.RUNNER).read_bytes()
        actual = next(n for n in ast.parse(raw).body if isinstance(n, ast.FunctionDef) and n.name == 'capture')
        compiled = host.runner_functions('capture')
        self.assertEqual(ast.dump(compiled.body[0], include_attributes=False), ast.dump(actual, include_attributes=False))
        self.assertEqual(len(compiled.body), 2)
        namespace = {};exec(compile(compiled, 'actual-current-capture', 'exec'), namespace)
        self.assertEqual(namespace['UI_NAVIGATION_CONTRACT'], 2)
        case = host.DownloadFreshObservationRunnerTest();case.setUp()
        self.assertEqual(case.namespace['UI_NAVIGATION_CONTRACT'], 1)
        record = case.final_evidence()
        self.assertEqual(record['downloadLocationRaw'], case.fresh_raw)
        self.assertEqual(record['downloadLocationObservationHistory'], [case.initial_raw, case.fresh_raw])
        selected = next(n for n in actual.body if isinstance(n, ast.If) and
                        any(isinstance(c, ast.Name) and c.id == 'label_log' and isinstance(c.ctx, ast.Store) for c in ast.walk(n)))
        before = ast.parse(current.source_input(raw, current.RUNNER))
        old_capture = next(n for n in before.body if isinstance(n, ast.FunctionDef) and n.name == 'capture')
        old_final = next(n for n in old_capture.body if isinstance(n, ast.If) and ast.unparse(n.test) == "scene == 'downloads'")
        self.assertEqual(len(selected.orelse), 1)
        self.assertEqual(ast.dump(selected.orelse[0], include_attributes=False), ast.dump(old_final, include_attributes=False))

    def test_historical_roots_only_change_named_read_ports_and_never_disk(self):
        for names in ((current.RUNNER, current.HOST), (current.ACTIVITY,)):
            root = current.historical_root(ROOT, names)
            self.assertEqual(os.fspath(root), str(ROOT))
            for path in names:
                raw = (ROOT/path).read_bytes()
                self.assertEqual((root/path).read_bytes(), current.source_input(raw, path))
                self.assertEqual((root/path).read_text().encode(), current.source_input(raw, path))
                self.assertFalse(hasattr(root/path, 'write_bytes'))
                self.assertEqual((ROOT/path).read_bytes(), raw)
            plain = 'tests/gecko/DownloadLocationLayoutEvidence.java'
            self.assertIsInstance(root/plain, Path)
            self.assertEqual((root/plain).read_bytes(), (ROOT/plain).read_bytes())
        for root, names in ((str(ROOT), (current.ACTIVITY,)), (ROOT.parent, (current.ACTIVITY,)),
                            (ROOT, [current.ACTIVITY]), (ROOT, (current.RUNNER,)), (ROOT, tuple(OWNED))):
            with self.assertRaises(AssertionError):current.historical_root(root, names)
        raw = (ROOT/current.ACTIVITY).read_bytes()+b'\n';read = Path.read_bytes
        def changed(path):return raw if path == ROOT/current.ACTIVITY else read(path)
        with patch.object(Path, 'read_bytes', changed):
            self.assertIs((current.historical_root(ROOT, (current.ACTIVITY,))/current.ACTIVITY).read_bytes(), raw)

    def test_types_paths_excerpt_modified_fixture_and_symlink_are_rejected(self):
        raw = (ROOT/current.RUNNER).read_bytes()
        for candidate in (None, raw.decode(), bytearray(raw), memoryview(raw), True):
            with self.assertRaises(AssertionError):current.source_input(candidate, current.RUNNER)
        for path in (None, Path(current.RUNNER), '/'+current.RUNNER, '../'+current.RUNNER, 'unknown.py'):
            with self.assertRaises(AssertionError):current.source_input(raw, path)
        for tree in (None, ast.Module(body=[], type_ignores=[]), ast.parse('def capture():\n pass')):
            with self.assertRaises(AssertionError):current.original_runner_tree(tree)
        with tempfile.TemporaryDirectory() as directory:
            changed = Path(directory)/'changed.json';changed.write_bytes(current.FIXTURE.read_bytes()+b' ')
            linked = Path(directory)/'linked.json';linked.symlink_to(current.FIXTURE)
            for candidate in (changed, linked):
                with patch.object(current, 'FIXTURE', candidate), self.assertRaises(AssertionError):current.manifest()

    def test_shallow_history_views_and_original_oracles_need_no_git_or_network(self):
        import ui_visual_preservation_contract as original
        raw = (ROOT/current.RUNNER).read_text();fixture = (ROOT/current.ACTIVITY).read_bytes()
        with (patch('subprocess.check_output', side_effect=AssertionError('No undeclared historical object access')),
              patch('subprocess.run', side_effect=AssertionError('No historical fetch or new process'))):
            runner = original.verify_shared_ui_source(raw)
            activity = original.verify_download_visual_fixture_source(fixture)
        self.assertEqual(runner['selectedSourceSha256'], current.sha(raw.encode()))
        self.assertEqual(activity['selectedFixtureSha256'], current.sha(fixture))
        self.assertTrue(activity['fourSyntheticRowsAndProductionRendererPreserved'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
