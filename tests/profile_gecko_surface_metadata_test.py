"""Finite native-surface metadata extension; retained old oracles stay whole."""
import copy
import json
import os
from pathlib import Path
import subprocess
import unittest

import gecko_surface_source_compatibility as surface
import profile_resource_startup_source_compatibility_test as resource_controls
import final_browser_source_compatibility as final

ROOT = Path(__file__).resolve().parents[1]
resource = resource_controls.layer


class GeckoSurfaceMetadataInputs(unittest.TestCase):
    def test_resource_configuration_extension_preserves_its_input_and_unowned_rows(self):
        original = resource.config.__wrapped__()
        frozen = copy.deepcopy(original)
        current = surface.wrap_resource_config(lambda: original)()
        self.assertEqual(original, frozen)
        self.assertEqual(current, resource.config())
        self.assertEqual(set(current), set(original))
        for key in set(original) - {'sources', 'finalAfter', 'finalAfterSha256'}:
            self.assertEqual(current[key], original[key])
        for path in original['sources']:
            if path != surface.GV:
                self.assertEqual(current['sources'][path], original['sources'][path])
        old, new = original['sources'][surface.GV], current['sources'][surface.GV]
        self.assertEqual(new['edits'][:-1], old['edits'])
        self.assertEqual((new['previousSha256'], new['previousBytes']), (old['previousSha256'], old['previousBytes']))
        self.assertEqual(surface.historical_resource_row(surface.GV, new), old)
        self.assertEqual(new, current['sources'][surface.GV])
        self.assertEqual(len(current['finalAfter']['deltas']), 9)
        self.assertEqual(len(final.manifest()['files']), 19)
        self.assertEqual(sum(len(row['deltas']) for row in final.manifest()['files'].values()), 59)

    def test_complete_public_final_predecessor_roundtrips_current_raw_with_bounded_unique_contexts(self):
        fixture = surface.manifest()
        row = fixture['finalCurrentRow']
        original = subprocess.check_output(['git', '--no-replace-objects', 'show',
            row['previousCommit'] + ':' + surface.GV], cwd=ROOT, env=dict(os.environ, GIT_NO_LAZY_FETCH='1'))
        self.assertEqual((surface.sha(original), len(original)), (row['previousSha256'], row['previousBytes']))
        current = (ROOT / surface.GV).read_bytes()
        forward = original
        for delta in row['deltas']:
            before, after = delta['previous'].encode(), delta['current'].encode()
            self.assertLessEqual(max(len(before), len(after)), 32768)
            self.assertEqual(surface.sha(before), delta['previousSha256'])
            self.assertEqual(surface.sha(after), delta['currentSha256'])
            self.assertEqual(forward.count(before), 1)
            forward = forward.replace(before, after, 1)
        self.assertEqual(forward, current)
        self.assertEqual(final.source_input(current, surface.GV), original)
        self.assertEqual(fixture['finalPreviousRow'], resource.config.__wrapped__()['finalAfter'])
        old = fixture['finalPreviousRow']
        for index, delta in enumerate(row['deltas']):
            if index != 4:self.assertEqual(delta, old['deltas'][index])

    def test_unknown_configuration_and_unreviewed_rows_are_never_normalized(self):
        original = resource.config.__wrapped__()
        variants = []
        changed = copy.deepcopy(original); changed['rootAfterRow']['reviewedSha256'] = '0' * 64; variants.append(changed)
        changed = copy.deepcopy(original); changed['sources'][surface.GV]['currentSha256'] = '0' * 64; variants.append(changed)
        changed = copy.deepcopy(original); changed['finalAfterSha256'] = '0' * 64; variants.append(changed)
        changed = copy.deepcopy(original); changed['extra'] = True; variants.append(changed)
        for changed in variants:
            frozen = copy.deepcopy(changed)
            with self.assertRaises(ValueError):surface.wrap_resource_config(lambda: changed)()
            self.assertEqual(changed, frozen)
        row = resource.config()['sources'][surface.GV]
        for field in ('previousSha256', 'currentSha256'):
            changed = copy.deepcopy(row); changed[field] = '0' * 64
            self.assertIs(surface.historical_resource_row(surface.GV, changed), changed)
        for path in ('app/Other.java', '../' + surface.GV, Path(surface.GV), None):
            self.assertIs(surface.historical_resource_row(path, row), row)
        self.assertEqual(row, resource.config()['sources'][surface.GV])

    def test_all_original_source_fixtures_and_before_metadata_remain(self):
        fixture = surface.manifest()
        for name in ('resource-startup-source-deltas.json', 'final-browser-source-deltas.json',
                     'profile-fixture-root-source-deltas.json'):
            relative = 'tests/fixtures/' + name
            previous = subprocess.check_output(['git', '--no-replace-objects', 'show',
                fixture['baseCommit'] + ':' + relative], cwd=ROOT, env=dict(os.environ, GIT_NO_LAZY_FETCH='1'))
            self.assertEqual((ROOT / relative).read_bytes(), previous)
        cfg = resource.config()
        for field in ('finalBefore', 'rootBeforeSha256', 'rootAfterRow', 'finalFixtureSha256'):
            self.assertEqual(cfg[field], resource.config.__wrapped__()[field])
        current = (ROOT / surface.GV).read_bytes()
        reported = surface.sha(current)
        self.assertEqual(surface.historical_report_sha(current, reported), surface.PREVIOUS_SHA256)
        with self.assertRaises(ValueError):surface.historical_report_sha(current, surface.PREVIOUS_SHA256)
        self.assertEqual(surface.sha(current), reported)


if __name__ == '__main__':
    unittest.main()

