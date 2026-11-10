"""Exact workspace runner history only; no Android or runtime acceptance."""
import ast
import copy
import difflib
import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch

import workspace_runner_source_compatibility as history
from ui_job_budget_source_compatibility import historical_source_input as ui_job_budget_source_input

ROOT = Path(__file__).resolve().parents[1]
OWNED = frozenset((
    'tests/gecko/run_device.py',
    'tests/event_journal_source_compatibility.py',
    'tests/profile_event_journal_source_compatibility_test.py',
    'tests/dual_browser_source_compatibility.py',
    'tests/profile_fixture_root_source_compatibility.py',
    'tests/profile_fixture_root_source_compatibility_test.py',
    'tests/gradle_workflow_test_source_compatibility.py',
    'tests/profile_gradle_workflow_test_source_compatibility_test.py',
    'tests/profile_resource_startup_source_compatibility_test.py',
    'tests/resource_startup_source_compatibility.py',
))


class WorkspaceRunnerHistoricalInputs(unittest.TestCase):
    def test_complete_current_images_restore_exact_real_c244_git_blobs_and_forward(self):
        self.assertEqual(history.BASE_COMMIT, 'c244835a4c1e3629909b2b1ce132ca5987a97d9a')
        self.assertEqual(history.BASE_TREE, '13f8feea716e7ceebd71fb46b21966292c920681')
        self.assertEqual(history.PATHS, OWNED)
        for relative, row in history.ROWS.items():
            with self.subTest(path=relative):
                current = ui_job_budget_source_input((ROOT/relative).read_bytes(), relative)
                self.assertEqual((len(current), history.sha(current)), (row['afterBytes'], row['afterSha256']))
                previous = history.source_input(current, relative)
                self.assertEqual((len(previous), history.sha(previous)), (row['beforeBytes'], row['beforeSha256']))
                self.assertEqual(hashlib.sha1(('blob '+str(len(previous))+'\0').encode()+previous).hexdigest(), row['beforeGitBlob'])
                self.assertEqual(history.historical_input(current, relative), previous)
                forward = previous
                for delta in row['deltas']:
                    before, after = delta['before'].encode(), delta['after'].encode()
                    self.assertEqual(forward.count(before), 1)
                    forward = forward.replace(before, after, 1)
                self.assertEqual(forward, current)

    def test_runner_inverse_owns_exactly_the_two_reviewed_lines_and_no_runtime_input(self):
        current = (ROOT/history.RUNNER).read_bytes()
        previous = history.source_input(current, history.RUNNER)
        before = previous.decode().splitlines(keepends=True)
        after = current.decode().splitlines(keepends=True)
        changes = [part for part in difflib.SequenceMatcher(None, before, after, autojunk=False).get_opcodes() if part[0] != 'equal']
        self.assertEqual(len(changes), 1)
        tag, i, j, k, l = changes[0]
        self.assertEqual((tag, j-i, l-k), ('replace', 1, 2))
        self.assertEqual(''.join(before[i:j]), "        for label in ['会话','环境','下载','网络','设置']:assert label in hierarchy,(label,hierarchy)\n")
        self.assertEqual(''.join(after[k:l]), "        from workspace_navigation_contract import exercise_workspace_roundtrip\n        report['productionNavigation']=exercise_workspace_roundtrip(adb,hierarchy,lambda name,xml:(OUT/name).write_text(xml),package)\n")
        tree = ast.parse(current)
        imports = [node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module == 'workspace_navigation_contract']
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'exercise_workspace_roundtrip']
        self.assertEqual(len(imports), 1)
        self.assertEqual(len(calls), 1)
        self.assertNotIn(b'workspace_runner_source_compatibility', current)
        self.assertEqual(len(history.ROWS[history.RUNNER]['deltas']), 1)

    def test_all_original_helper_bodies_and_old_assertion_trees_are_preserved(self):
        helpers = OWNED - {history.RUNNER} - {path for path in OWNED if path.endswith('_test.py')}
        for relative in helpers:
            current = ui_job_budget_source_input((ROOT/relative).read_bytes(), relative)
            previous = history.source_input(current, relative)
            def bodies(raw):
                return [ast.dump(node, include_attributes=False) for node in ast.parse(raw).body
                        if isinstance(node, (ast.FunctionDef, ast.ClassDef))]
            self.assertEqual(bodies(current), bodies(previous), relative)
        for relative in (path for path in OWNED if path.endswith('_test.py')):
            current = ui_job_budget_source_input((ROOT/relative).read_bytes(), relative)
            previous = history.source_input(current, relative)
            def assertions(raw):
                return [ast.dump(node, include_attributes=False) for node in ast.walk(ast.parse(raw))
                        if isinstance(node, ast.Assert) or isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute) and node.func.attr.startswith('assert')]
            self.assertEqual(assertions(current), assertions(previous), relative)

    def test_unknown_insert_delete_change_duplicate_and_moved_context_fail_closed(self):
        for relative, row in history.ROWS.items():
            current = ui_job_budget_source_input((ROOT/relative).read_bytes(), relative)
            candidates = [current+b' ', current[:-1], b'unknown', current[:80]]
            for delta in row['deltas']:
                context = delta['after'].encode()
                self.assertEqual(current.count(context), 1)
                remaining = current.replace(context, b'', 1)
                moved = remaining+context
                if moved == current:
                    moved = context+remaining
                candidates.extend((remaining, current.replace(context, context*2, 1),
                                   current.replace(context, context+b' ', 1), moved))
            for candidate in candidates:
                with self.subTest(path=relative, sha256=history.sha(candidate)):
                    self.assertNotEqual(candidate, current)
                    with self.assertRaises(ValueError):
                        history.source_input(candidate, relative)
                    self.assertIs(history.historical_input(candidate, relative), candidate)

    def test_navigation_arguments_anchor_and_unrelated_old_guard_mutations_reject(self):
        raw = (ROOT/history.RUNNER).read_bytes()
        changes = (
            (b'exercise_workspace_roundtrip(adb,hierarchy,', b'exercise_workspace_roundtrip(None,hierarchy,'),
            (b"report['productionNavigation']", b"report['other']"),
            (b"(OUT/name).write_text(xml),package)", b"(OUT/name).write_text(xml),'other.package')"),
            (b"(OUT/'production-ui.xml').write_text(hierarchy)", b"(OUT/'production-ui.xml').write_text('')"),
            (b'deadline=time.monotonic()+120', b'deadline=time.monotonic()+121'),
            (b"assert 'error' not in result,event", b'assert True,event'),
        )
        for old, new in changes:
            self.assertIn(old, raw)
            with self.subTest(context=old), self.assertRaises(ValueError):
                history.source_input(raw.replace(old, new, 1), history.RUNNER)

    def test_wrong_types_paths_and_reusing_restored_input_as_current_are_rejected(self):
        raw = (ROOT/history.RUNNER).read_bytes()
        for value in (raw.decode(), bytearray(raw), memoryview(raw), None, b''):
            with self.assertRaises(ValueError):
                history.source_input(value, history.RUNNER)
        for path in (None, Path(history.RUNNER), '../'+history.RUNNER, '/'+history.RUNNER,
                     history.RUNNER+'.other', 'tools/gecko/workspace_navigation_contract.py'):
            with self.assertRaises(ValueError):
                history.source_input(raw, path)
        previous = history.source_input(raw, history.RUNNER)
        with self.assertRaises(ValueError):
            history.source_input(previous, history.RUNNER)
        self.assertIs(history.historical_input(previous, history.RUNNER), previous)

    def test_whole_pin_precedes_context_and_restored_sha_and_git_blob_are_required(self):
        relative = history.RUNNER
        raw = (ROOT/relative).read_bytes()
        class ForbiddenContext:
            def encode(self, *args):
                raise AssertionError('Unknown source reached a context')
        rows = copy.deepcopy(history.ROWS)
        rows[relative]['deltas'][0]['after'] = ForbiddenContext()
        with patch.object(history, 'ROWS', rows), self.assertRaisesRegex(ValueError, 'unknown complete'):
            history.source_input(raw+b' ', relative)
        rows = copy.deepcopy(history.ROWS)
        delta = rows[relative]['deltas'][0]
        delta['before'] += 'unreviewed predecessor\n'
        delta['beforeSha256'] = history.sha(delta['before'].encode())
        with patch.object(history, 'ROWS', rows), self.assertRaisesRegex(ValueError, 'complete c244 predecessor'):
            history.source_input(raw, relative)
        rows = copy.deepcopy(history.ROWS)
        rows[relative]['beforeGitBlob'] = '0'*40
        with patch.object(history, 'ROWS', rows), self.assertRaisesRegex(ValueError, 'actual Git blob'):
            history.source_input(raw, relative)

    def test_explicit_wrapper_preserves_the_original_guard_for_unknown_inputs(self):
        calls = []
        def original(raw, relative):
            calls.append((raw, relative))
            return raw
        wrapped = history.wrap_input(original)
        raw = (ROOT/history.RUNNER).read_bytes()
        self.assertEqual(wrapped(raw, history.RUNNER), history.source_input(raw, history.RUNNER))
        unknown = raw+b'unknown'
        self.assertIs(wrapped(unknown, history.RUNNER), unknown)
        foreign = b'unowned current producer bytes'
        self.assertIs(wrapped(foreign, 'app/src/main/java/local/pocketchat/MainActivity.java'), foreign)
        self.assertEqual(len(calls), 3)
        self.assertIs(wrapped.__wrapped__, original)


if __name__ == '__main__':
    unittest.main(verbosity=2)
