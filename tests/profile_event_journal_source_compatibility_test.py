"""Exact historical source preservation only; no device execution or acceptance."""
import ast
import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import event_journal_source_compatibility as journal
import experience46_source_compatibility as experience

ROOT = Path(__file__).resolve().parents[1]
RUNNER = 'tests/gecko/run_device.py'
SHA = lambda raw: hashlib.sha256(raw).hexdigest()


class ReceiptJournalSourceCompatibility(unittest.TestCase):
    def test_each_whole_inverse_and_forward_equal_the_real_committed_source(self):
        for relative, row in journal.manifest()['files'].items():
            with self.subTest(path=relative):
                previous = subprocess.check_output(['git', 'show', journal.BASE_COMMIT + ':' + relative], cwd=ROOT)
                current = (ROOT / relative).read_bytes()
                self.assertEqual((SHA(previous), len(previous)), (row['previousSha256'], row['previousBytes']))
                self.assertEqual((SHA(current), len(current)), (row['reviewedSha256'], row['reviewedBytes']))
                self.assertEqual(journal.source_input(current, relative), previous)
                self.assertEqual(journal.source_input(previous, relative), previous)
                forward = previous
                for delta in row['deltas']:
                    old, new = delta['previous'].encode(), delta['current'].encode()
                    self.assertEqual((SHA(old), SHA(new)), (delta['previousSha256'], delta['currentSha256']))
                    self.assertEqual(forward.count(old), 1)
                    forward = forward.replace(old, new, 1)
                self.assertEqual(forward, current)

    def test_missing_duplicate_changed_relocated_and_unknown_bytes_are_rejected(self):
        rejected = 0
        for relative, row in journal.manifest()['files'].items():
            current = (ROOT / relative).read_bytes()
            for delta in row['deltas']:
                chunk = delta['current'].encode()
                remaining = current.replace(chunk, b'', 1)
                moved = remaining + chunk
                if moved == current:
                    moved = chunk + remaining
                for candidate in (remaining, current.replace(chunk, chunk * 2, 1),
                                  current.replace(chunk, chunk + b' ', 1), moved):
                    with self.subTest(path=relative, delta=delta['id'], mutant=SHA(candidate)):
                        self.assertNotEqual(candidate, current)
                        with self.assertRaises(ValueError):
                            journal.source_input(candidate, relative)
                        rejected += 1
            for candidate in (current + b' ', b'unknown source', current[:80]):
                with self.assertRaises(ValueError):
                    journal.source_input(candidate, relative)
                rejected += 1
        self.assertEqual(rejected, 61)

    def test_original_experience_manifest_goldens_and_assertions_are_unchanged(self):
        relative = 'tests/fixtures/experience46-source-deltas.json'
        old = subprocess.check_output(['git', 'show', journal.BASE_COMMIT + ':' + relative], cwd=ROOT)
        self.assertEqual((ROOT / relative).read_bytes(), old)
        for relative in journal.PATHS - {RUNNER}:
            previous = subprocess.check_output(['git', 'show', journal.BASE_COMMIT + ':' + relative], cwd=ROOT)
            current = (ROOT / relative).read_bytes()
            self.assertEqual(journal.source_input(current, relative), previous)
            def assertions(raw):
                return [ast.dump(node, include_attributes=False) for node in ast.walk(ast.parse(raw))
                        if isinstance(node, ast.Assert) or isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute) and node.func.attr.startswith('assert')]
            self.assertEqual(assertions(current), assertions(previous))

    def test_old_runner_predicates_timeouts_payload_and_sequence_gates_stay_strict(self):
        current = (ROOT / RUNNER).read_text()
        for old, new in (
                ('deadline=time.monotonic()+120', 'deadline=time.monotonic()+121'),
                ("assert 'error' not in result,event", 'assert True,event'),
                ('read_with_sequence_failure_diagnostics(transfer,receipt,',
                 'read_with_sequence_failure_diagnostics(None,receipt,'),
                ("if event.get('kind')=='error':", "if event.get('kind')=='ignoredError':")):
            self.assertIn(old, current)
            candidate = current.replace(old, new, 1).encode()
            with self.subTest(predicate=old):
                with self.assertRaises(ValueError):
                    journal.source_input(candidate, RUNNER)
                with self.assertRaises(ValueError):
                    experience.experience46_source_bytes(candidate, RUNNER)
        previous = journal.source_input(current.encode(), RUNNER)
        self.assertEqual(SHA(experience.experience46_source_bytes(previous, RUNNER)),
                         '54fa412be9f89e46d61597caf61b0246e451e6c9b5eebca592e36b05686ab8a6')
        self.assertEqual(experience.experience46_source_bytes(current.encode(), RUNNER),
                         experience.experience46_source_bytes(previous, RUNNER))

    def test_complete_run_ast_inverse_matches_git_history_and_retains_original_formatting_controls(self):
        from reading_zoom_trace_contract import strip_reviewed_reading_trace_additions
        from gecko_device_readiness_test import verify_runner_consumer
        def node(source):
            raw = strip_reviewed_reading_trace_additions(source.encode(), RUNNER)
            return next(value for value in ast.walk(ast.parse(raw))
                        if type(value) is ast.FunctionDef and value.name == 'run')
        dump = lambda value: ast.dump(value, include_attributes=False)
        previous = subprocess.check_output(['git', 'show', journal.BASE_COMMIT + ':' + RUNNER], cwd=ROOT).decode()
        current = (ROOT / RUNNER).read_text()
        expected = dump(node(previous))
        actual = node(current)
        before = dump(actual)
        self.assertEqual(dump(journal.original_runner_tree(actual)), expected)
        self.assertEqual(dump(actual), before)
        self.assertEqual(dump(journal.original_runner_tree(node(previous))), expected)
        formatted = '# harmless comment\n' + current.replace("action=='downloadResume'", 'action == "downloadResume"')
        self.assertEqual(dump(journal.original_runner_tree(node(formatted))), expected)
        self.assertTrue(verify_runner_consumer(formatted))
        discovery = '        discovery=ReceiptJournalDiscovery(transfer)\n'
        metadata = "        transfer_record['discovery']='native-committed-marker-journal'\n"
        native = "            for receipt in discovery.snapshot(adb_bytes('exec-out','content','read','--uri',discovery.uri())):\n"
        mutations = (
            current.replace(discovery, '', 1), current.replace(discovery, discovery * 2, 1),
            current.replace(discovery, '', 1).replace('        tapped=set()\n', '        tapped=set()\n' + discovery, 1),
            current.replace(metadata, '', 1), current.replace(metadata, metadata * 2, 1),
            current.replace(native, native.replace('discovery.uri()', "'replacement'"), 1),
            current.replace('deadline=time.monotonic()+120', 'deadline=time.monotonic()+121', 1),
            current.replace("assert 'error' not in result,event", 'assert True,event', 1),
            current.replace('slot=context-1', 'slot=context', 1),
        )
        for candidate in mutations:
            self.assertNotEqual(candidate, current)
            with self.assertRaises(ValueError):
                journal.original_runner_tree(node(candidate))
        for value in (ast.parse(current), ast.parse('def unrelated():\n pass').body[0], 'run', None):
            with self.assertRaises(ValueError):
                journal.original_runner_tree(value)

    def test_types_paths_excerpt_and_altered_fixture_are_rejected(self):
        current = (ROOT / RUNNER).read_bytes()
        for relative in (RUNNER + '.other', '../' + RUNNER, '/' + RUNNER,
                         Path(RUNNER), None):
            with self.subTest(path=relative), self.assertRaises(ValueError):
                journal.source_input(current, relative)
        for candidate in (current.decode(), bytearray(current), None):
            with self.assertRaises(ValueError):
                journal.source_input(candidate, RUNNER)
        with tempfile.TemporaryDirectory(prefix='journal-inverse-negative-') as directory:
            fake = Path(directory) / 'deltas.json'
            fake.write_bytes(journal.DELTA_PATH.read_bytes() + b' ')
            with patch.object(journal, 'DELTA_PATH', fake), self.assertRaises(ValueError):
                journal.source_input(current, RUNNER)

    def test_actual_journal_hosts_execute_current_runner_without_this_source_view(self):
        for relative in ('tests/gecko_event_transfer_test.py', 'tests/profile_event_journal_discovery_test.py'):
            source = (ROOT / relative).read_text()
            self.assertIn('ReceiptJournalDiscovery', source)
            self.assertIn('ast.parse', source)
            self.assertNotIn('event_journal_source_compatibility', source)
            self.assertNotIn('experience46_source_bytes', source)
        relative = 'tools/gecko/integration_event_contract.py'
        self.assertEqual((ROOT / relative).read_bytes(),
                         subprocess.check_output(['git', 'show', journal.BASE_COMMIT + ':' + relative], cwd=ROOT))
        self.assertIn('class ReceiptJournalDiscovery:', (ROOT / RUNNER).read_text())


if __name__ == '__main__':
    unittest.main(verbosity=2)
