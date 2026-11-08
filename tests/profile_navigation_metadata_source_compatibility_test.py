"""Finite metadata views preserve immutable fixtures and actual source bytes."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import profile_dual_browser_source_compatibility_test as dual_controls
import navigation_metadata_source_compatibility as metadata

# Compose through the retained historical test interface, as the existing
# Gradle metadata controls do. The fixed production/source-view import boundary
# stays unchanged; these are neither runtime inputs nor a replacement decoder.
dual = dual_controls.dual

ROOT = Path(__file__).resolve().parents[1]
SHA = lambda raw: hashlib.sha256(raw).hexdigest()


class NavigationMetadataControls(unittest.TestCase):
    def test_original_json_files_and_root_trace_helpers_are_actual_unchanged_bytes(self):
        pins = {
            'tests/fixtures/dual-browser-source-deltas.json': 'b593b0db2b56b5a5d8143a920fbd15858dafbab21d1cdaf90ca2a5ba164c9933',
            'tests/fixtures/gradle-workflow-test-source-deltas.json': '5d1f33ee4997b73e4c8785fbac39e831311247b5cae7c6d3e8c6182a8350a6ee',
            'tests/fixtures/event-journal-source-deltas.json': '13620b58a536ebe4e0b822cd5b6ea11b9656cfdb83f2e18ee8c90ee0fa3c4254',
            'tests/profile_fixture_root_source_compatibility.py': 'c79732d202afa92e1d76ee2f48dea13221d973f3813433d0b1cfe2d61e7df619',
            'tests/reading_zoom_trace_contract.py': '6deaf3e28b101cbcb65e55f46b8dc9e8b777cae9cadf0457863f37f021bb3102',
        }
        before = {path: (ROOT / path).read_bytes() for path in pins}
        for path, raw in before.items():self.assertEqual(SHA(raw), pins[path])
        dual.manifest()
        for path, raw in before.items():self.assertEqual((ROOT / path).read_bytes(), raw)

    def test_dual_metadata_changes_only_the_approved_journal_after_row(self):
        original = json.loads((ROOT / 'tests/fixtures/dual-browser-source-deltas.json').read_bytes())
        saved = copy.deepcopy(original)
        result = metadata.wrap_dual_manifest(lambda: original)()
        self.assertEqual(original, saved)
        self.assertEqual(len(result['files']), 9)
        for path, row in original['files'].items():
            if path != metadata.JOURNAL:self.assertEqual(result['files'][path], row)
        row = result['files'][metadata.JOURNAL]
        self.assertEqual((row['reviewedBytes'], row['reviewedSha256']),
            (6536, '16f44c6a6896513672ee260c2a18fed174c74bc6e9d19cded2e223bf09b81abd'))
        self.assertEqual(len(row['deltas']), len(original['files'][metadata.JOURNAL]['deltas']))
        raw = (ROOT / metadata.JOURNAL).read_bytes()
        before = dual.source_input(raw, metadata.JOURNAL)
        self.assertEqual((len(before), SHA(before)), (row['previousBytes'], row['previousSha256']))
        for delta in row['deltas']:
            self.assertEqual(before.count(delta['previous'].encode()), 1)
            before = before.replace(delta['previous'].encode(), delta['current'].encode(), 1)
        self.assertEqual(before, raw)

    def test_dual_helper_eof_inverse_preserves_its_complete_original_body(self):
        raw = (ROOT / metadata.DUAL).read_bytes()
        before = metadata.source_input(raw)
        self.assertEqual((len(before), SHA(before)), metadata.BEFORE)
        self.assertEqual((len(raw), SHA(raw)), metadata.AFTER)
        self.assertTrue(raw.startswith(before))
        self.assertIs(metadata.source_input(before), before)

    def test_missing_repeated_moved_changed_eof_or_any_original_byte_reject(self):
        raw = (ROOT / metadata.DUAL).read_bytes()
        chunk = metadata.manifest()['sourceImages'][metadata.DUAL]['current'].encode()
        removed = raw.replace(chunk, b'', 1)
        for value in (removed, raw.replace(chunk, chunk * 2, 1), chunk + removed,
                      raw.replace(chunk, chunk + b' ', 1), raw + b' ', raw[:100],
                      raw.replace(b'Dual-browser inverse rejects', b'Changed inverse rejects', 1)):
            self.assertNotEqual(value, raw)
            with self.assertRaises(ValueError):metadata.source_input(value)
        journal = (ROOT / metadata.JOURNAL).read_bytes()
        for value in (journal + b' ', journal[:100], journal.replace(b'unknown whole source', b'changed whole source', 1)):
            self.assertNotEqual(value, journal)
            with self.assertRaises(ValueError):dual.source_input(value, metadata.JOURNAL)

    def test_root_factory_view_is_pure_and_checks_the_exact_previous_dual_row(self):
        cfg = metadata.manifest()
        # Only cloning/row composition is modeled. Actual original loaders and
        # factories run unchanged in their retained direct-consumer suites.
        value = {'files': {metadata.DUAL: copy.deepcopy(cfg['rootDualBefore']), 'other': {'unchanged': True}}}
        saved = copy.deepcopy(value)
        factory = metadata.wrap_root_factory(lambda loader: loader)
        result = factory(lambda: value)()
        self.assertEqual(value, saved)
        self.assertEqual(result['files']['other'], {'unchanged': True})
        self.assertEqual(result['files'][metadata.DUAL], cfg['rootDualAfter'])
        value['files'][metadata.DUAL]['reviewedBytes'] += 1
        with self.assertRaises(ValueError):factory(lambda: value)()

    def test_metadata_redirects_types_and_unknown_images_fail_closed(self):
        raw = (ROOT / metadata.DUAL).read_bytes()
        for bad in (None, raw.decode(), bytearray(raw)):
            with self.assertRaises(ValueError):metadata.source_input(bad)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'changed.json'
            path.write_bytes(metadata.FIXTURE.read_bytes() + b' ')
            with patch.object(metadata, 'FIXTURE', path), self.assertRaises(ValueError):metadata.manifest()

    def test_actual_producers_never_import_a_historical_metadata_view(self):
        for path in ('tests/gecko/run_device.py', 'tests/gecko/run_chrome_collapse.py',
                     'tests/gecko/run_chrome_collapse_v2.py', 'tests/gecko/run_ui_visuals.py'):
            source = (ROOT / path).read_text()
            for forbidden in ('navigation_metadata_source_compatibility', 'chrome_dispatch_source_compatibility',
                              'native_navigation_device_source_compatibility'):
                self.assertNotIn(forbidden, source)


if __name__ == '__main__':
    unittest.main()
