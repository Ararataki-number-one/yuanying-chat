"""Finite current device-runner images for historical comparisons, never runtime."""
import ast
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import native_navigation_device_source_compatibility as port
import event_journal_source_compatibility as journal
from reading_zoom_trace_contract import original_reading_fixture_bytes

ROOT = Path(__file__).resolve().parents[1]
SHA = lambda raw: hashlib.sha256(raw).hexdigest()


class NativeNavigationDeviceHistoricalControls(unittest.TestCase):
    def current(self):
        return (ROOT / port.RUNNER).read_bytes()

    def test_current_whole_image_and_two_hunks_restore_the_actual_prior_hash(self):
        raw = self.current()
        value = port.manifest()
        self.assertEqual((len(raw), SHA(raw)), (93282, port.CURRENT_SHA256))
        before = port.comparison_input(raw)
        self.assertEqual((len(before), SHA(before)), (92698, port.PRIOR_SHA256))
        self.assertEqual(len(value['deltas']), 2)
        for row in value['deltas']:
            previous, current = row['previous'].encode(), row['current'].encode()
            self.assertEqual(before.count(previous), 1)
            before = before.replace(previous, current, 1)
        self.assertEqual(before, raw)

    def test_untouched_legacy_manifest_and_three_delta_overlay_keep_all_other_rows(self):
        raw = (ROOT / 'tests/fixtures/event-journal-source-deltas.json').read_bytes()
        self.assertEqual(SHA(raw), port.JOURNAL_SHA256)
        old = json.loads(raw)
        value = journal.manifest()
        self.assertEqual(old['runTree'], value['runTree'])
        self.assertEqual(old['baseCommit'], value['baseCommit'])
        for path in old['files']:
            if path != port.RUNNER:
                self.assertEqual(old['files'][path], value['files'][path])
        row = value['files'][port.RUNNER]
        self.assertEqual(len(row['deltas']), 3)
        self.assertEqual(sum(4 * len(row['deltas']) + 3 for row in value['files'].values()), 61)
        self.assertEqual(SHA(journal.source_input(self.current(), port.RUNNER)),
                         '65b5c56e3576f645a10d6f2b5a69147e2904601641d56e4a9ed31de246b0a103')
        self.assertEqual((old['files'][port.RUNNER]['previousBytes'], old['files'][port.RUNNER]['previousSha256']),
                         (row['previousBytes'], row['previousSha256']))
        self.assertTrue(all(max(len(delta['previous'].encode()), len(delta['current'].encode())) <= 32768
                            for delta in row['deltas']))

    def test_missing_duplicate_moved_or_changed_new_hunks_reject(self):
        raw = self.current()
        for row in port.manifest()['deltas']:
            current = row['current'].encode()
            self.assertEqual(raw.count(current), 1)
            remaining = raw.replace(current, b'', 1)
            moved = remaining + current
            if moved == raw:
                moved = current + remaining
            for bad in (remaining, raw.replace(current, current * 2, 1), moved,
                        raw.replace(current, current + b' ', 1)):
                self.assertNotEqual(raw, bad)
                with self.assertRaises(ValueError):
                    port.comparison_input(bad)
                with self.assertRaises(ValueError):
                    journal.source_input(bad, port.RUNNER)

    def test_formatted_input_requires_complete_known_ast_and_preserves_comments(self):
        source = self.current().decode()
        formatted = ('# harmless comment\n' + source.replace("action=='downloadResume'", 'action == "downloadResume"')).encode()
        before = port.comparison_input(formatted, formatted=True)
        self.assertTrue(before.startswith(b'# harmless comment\n'))
        self.assertIn(b'action == "downloadResume"', before)
        self.assertEqual(SHA(ast.dump(ast.parse(before), include_attributes=False).encode()), port.manifest()['priorAstSha256'])
        with self.assertRaises(ValueError):
            port.comparison_input(formatted)
        with self.assertRaises(ValueError):
            original_reading_fixture_bytes(formatted, port.RUNNER)

    def test_unowned_workload_or_protocol_drift_cannot_gain_formatted_acceptance(self):
        source = self.current().decode()
        for old, new in (
                ('deadline=time.monotonic()+120', 'deadline=time.monotonic()+121'),
                ('if args.native_navigation_version==1:', 'if args.native_navigation_version==2:'),
                ('choices=(1,2),default=2', 'choices=(1,2),default=1'),
                ("assert 'error' not in result,event", 'assert True,event'),
                ('slot=context-1', 'slot=context')):
            self.assertIn(old, source)
            raw = source.replace(old, new, 1).encode()
            with self.subTest(change=old), self.assertRaises(ValueError):
                port.comparison_input(raw, formatted=True)

    def test_types_unknown_wholes_and_excerpt_cannot_normalize(self):
        raw = self.current()
        for value in (None, raw.decode(), bytearray(raw), b'', raw[:80], raw + b' '):
            with self.assertRaises(ValueError):
                port.comparison_input(value)
        with self.assertRaises(ValueError):
            port.comparison_input(raw, formatted='true')

    def test_journal_helper_known_eof_inverse_preserves_both_input_objects(self):
        raw = (ROOT / 'tests/event_journal_source_compatibility.py').read_bytes()
        preserved = bytes(raw)
        before = port.journal_helper_input(raw)
        self.assertEqual((len(before), SHA(before)),
                         (5971, 'b35122f03dca997a2b5e3f25675371ec4f8f83d77e5a8ca2fbac7d40079fde31'))
        self.assertEqual(raw, preserved)
        self.assertIs(port.journal_helper_input(before), before)
        row = port.manifest()['journalHelper']['deltas'][0]
        self.assertEqual(before.count(row['previous'].encode()), 1)
        self.assertEqual(before.replace(row['previous'].encode(), row['current'].encode(), 1), raw)
        calls = []
        wrapper = port.wrap_fixture_root_history(lambda value, path: calls.append((value, path)) or value)
        self.assertEqual(wrapper(raw, 'tests/event_journal_source_compatibility.py'), before)
        marker = object()
        self.assertIs(wrapper(marker, 'some-other-path'), marker)
        self.assertIs(calls[-1][0], marker)

    def test_journal_helper_unknown_or_moved_eof_never_reaches_the_original_reader(self):
        raw = (ROOT / 'tests/event_journal_source_compatibility.py').read_bytes()
        chunk = port.manifest()['journalHelper']['deltas'][0]['current'].encode()
        remaining = raw.replace(chunk, b'', 1)
        mutants = (remaining, raw.replace(chunk, chunk * 2, 1), chunk + remaining,
                   raw.replace(chunk, chunk + b' ', 1), raw + b' ', raw[:80])
        self.assertEqual(raw.count(chunk), 1)
        calls = []
        wrapper = port.wrap_fixture_root_history(lambda value, path: calls.append((value, path)))
        for mutant in mutants:
            self.assertNotEqual(raw, mutant)
            with self.assertRaises(ValueError):
                port.journal_helper_input(mutant)
            with self.assertRaises(ValueError):
                wrapper(mutant, 'tests/event_journal_source_compatibility.py')
        self.assertEqual(calls, [])

    def test_corrupted_or_redirected_metadata_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'data.json'
            path.write_bytes(port.FIXTURE.read_bytes() + b' ')
            with patch.object(port, 'FIXTURE', path), self.assertRaises(ValueError):
                port.manifest()

    def test_original_journal_and_trace_functions_remain_byte_exact(self):
        source = (ROOT / 'tests/reading_zoom_trace_contract.py').read_text()
        node = next(node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef)
                    and node.name == 'strip_reviewed_reading_trace_additions')
        self.assertEqual(SHA(ast.get_source_segment(source, node).encode()),
                         '841c1c873318240ca844661b5e28e2ba188438db6b319a68ef6ae7af50b6ab1b')
        source = (ROOT / port.RUNNER).read_text()
        self.assertNotIn('native_navigation_device_source_compatibility', source)
        self.assertIn('native_navigation_version', source)
        self.assertIn('validate_chat(hierarchy', source)


if __name__ == '__main__':
    unittest.main()
