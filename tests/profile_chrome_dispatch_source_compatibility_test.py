"""Immutable first-tap fixture and bounded current comparison metadata only."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import chrome_dispatch_source_compatibility as dispatch
import chrome_first_tap_source_compatibility as first

ROOT = Path(__file__).resolve().parents[1]
SHA = lambda raw: hashlib.sha256(raw).hexdigest()


class ChromeDispatchHistoricalControls(unittest.TestCase):
    def test_original_fixture_is_actual_unchanged_bytes_before_and_after_comparison(self):
        path = ROOT / 'tests/fixtures/chrome-first-tap-source-deltas.json'
        before = path.read_bytes()
        self.assertEqual((len(before), SHA(before)), (13142,
            '2c31cb3286d88a91079fb33cef1f27b9c81f7cefda6fbb1c7bc6537e6ca79795'))
        self.assertEqual(first.FIXTURE_SHA256, SHA(before))
        first.manifest()
        first.source_input((ROOT / dispatch.PATH).read_bytes(), dispatch.PATH)
        self.assertEqual(path.read_bytes(), before)

    def test_only_current_after_row_is_overlaid_without_mutating_original_metadata(self):
        original = json.loads(first.FIXTURE.read_bytes())
        saved = copy.deepcopy(original)
        result = dispatch.wrap_manifest(lambda: original)()
        self.assertEqual(original, saved)
        self.assertEqual({k: v for k, v in result.items() if k != 'files'},
                         {k: v for k, v in original.items() if k != 'files'})
        for path, row in original['files'].items():
            if path != dispatch.PATH:
                self.assertEqual(result['files'][path], row)
        row = result['files'][dispatch.PATH]
        self.assertEqual((row['reviewedBytes'], row['reviewedSha256']), (16331, dispatch.CURRENT_SHA256))
        self.assertEqual((row['previousBytes'], row['previousSha256']),
            (original['files'][dispatch.PATH]['previousBytes'], original['files'][dispatch.PATH]['previousSha256']))
        self.assertEqual(len(row['deltas']), 1)
        self.assertEqual(sum(4 * len(row['deltas']) + 3 for path, row in result['files'].items()
            if path != 'tools/gecko/chrome_header_readiness.py'), 14)

    def test_exact_append_inverse_and_unchanged_normalizer_compose_to_public_before(self):
        raw = (ROOT / dispatch.PATH).read_bytes()
        previous = dispatch.source_input(raw)
        self.assertEqual((len(previous), SHA(previous)), (15834, dispatch.PREVIOUS_SHA256))
        self.assertEqual(raw[:len(previous)], previous)
        self.assertEqual(len(raw) - len(previous), 497)
        before = first.source_input(raw, dispatch.PATH)
        self.assertEqual(SHA(before), 'c2b30b11c52fbca41abfd2df289dcc1f5221194222edb1b6e5170ef0f5a36ac5')
        forward = before
        for delta in first.manifest()['files'][dispatch.PATH]['deltas']:
            self.assertEqual(forward.count(delta['previous'].encode()), 1)
            forward = forward.replace(delta['previous'].encode(), delta['current'].encode(), 1)
        self.assertEqual(forward, raw)

    def test_missing_repeated_moved_changed_append_or_original_body_are_rejected(self):
        raw = (ROOT / dispatch.PATH).read_bytes()
        delta = dispatch.manifest()['deltas'][0]
        chunk = delta['current'].encode()
        removed = raw.replace(chunk, b'', 1)
        mutations = (removed, raw.replace(chunk, chunk * 2, 1), chunk + removed,
            raw.replace(chunk, chunk + b' ', 1), raw + b' ',
            raw.replace(b'navigation_version=2', b'navigation_version=1', 1),
            raw.replace(b'return snapshot(label)', b'return before', 1), raw[:100])
        for mutant in mutations:
            self.assertNotEqual(mutant, raw)
            with self.subTest(sha=SHA(mutant)):
                with self.assertRaises(ValueError):dispatch.source_input(mutant)
                with self.assertRaises(ValueError):first.source_input(mutant, dispatch.PATH)

    def test_types_and_previous_stage_cannot_impersonate_current_source(self):
        raw = (ROOT / dispatch.PATH).read_bytes()
        for value in (raw.decode(), bytearray(raw), None, raw[:15834]):
            with self.assertRaises(ValueError):dispatch.source_input(value)

    def test_original_loader_still_rejects_corrupted_original_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            fake = Path(directory) / 'old.json'
            fake.write_bytes(first.FIXTURE.read_bytes() + b' ')
            with patch.object(first, 'FIXTURE', fake), self.assertRaises(ValueError):first.manifest()

    def test_new_manifest_cannot_be_changed_or_replace_the_original_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            fake = Path(directory) / 'new.json'
            fake.write_bytes(dispatch.FIXTURE.read_bytes() + b' ')
            with patch.object(dispatch, 'FIXTURE', fake), self.assertRaises(ValueError):dispatch.manifest()
        original = json.loads(first.FIXTURE.read_bytes())
        original['files'][dispatch.PATH]['previousBytes'] += 1
        with self.assertRaises(ValueError):dispatch.wrap_manifest(lambda: original)()

    def test_actual_v1_and_v2_runners_do_not_import_the_comparison_view(self):
        for path in (dispatch.PATH, 'tests/gecko/run_chrome_collapse_v2.py',
                     'tests/gecko/run_ui_visuals.py', 'tools/gecko/chrome_collapse_contract_v2.py'):
            source = (ROOT / path).read_text()
            self.assertNotIn('chrome_dispatch_source_compatibility', source)
            self.assertNotIn('chrome_first_tap_source_compatibility', source)


if __name__ == '__main__':
    unittest.main()
