"""Exact historical Activity inputs; no Android rendering or execution claims."""
import hashlib
import os
from pathlib import Path
import subprocess
import unittest

import ui_checkpoint_source_compatibility as navigation
import ui_observer_source_compatibility as observer
import ui_visual_preservation_contract as original_ui

ROOT = Path(__file__).resolve().parents[1]


class NavigationSourceCompatibilityTests(unittest.TestCase):
    def test_inverse_and_forward_match_actual_pinned_git_blobs(self):
        value = navigation.navigation_manifest()
        environment = dict(os.environ, GIT_NO_LAZY_FETCH='1')
        def git(*args):
            return subprocess.check_output(['git', '--no-replace-objects', *args], cwd=ROOT, env=environment)
        self.assertEqual(git('rev-parse', value['previousCommit'] + '^{tree}').decode().strip(), value['previousTree'])
        self.assertEqual(git('rev-parse', value['reviewedCommit'] + '^{tree}').decode().strip(), value['reviewedTree'])
        previous = git('show', value['previousCommit'] + ':' + navigation.NAVIGATION_PATH)
        current = git('show', value['reviewedCommit'] + ':' + navigation.NAVIGATION_PATH)
        self.assertEqual((ROOT / navigation.NAVIGATION_PATH).read_bytes(), current)
        self.assertEqual(navigation.navigation_source_input(current, navigation.NAVIGATION_PATH), previous)
        self.assertEqual(navigation.history_input(current, navigation.NAVIGATION_PATH), previous)
        restored = previous
        for delta in value['deltas']:
            before, after = delta['previous'].encode(), delta['current'].encode()
            self.assertEqual(restored.count(before), 1)
            restored = restored.replace(before, after, 1)
        self.assertEqual(restored, current)

    def test_actual_navigation_anchors_cannot_be_missing_duplicated_moved_or_changed(self):
        raw = (ROOT / navigation.NAVIGATION_PATH).read_bytes()
        for delta in navigation.navigation_manifest()['deltas']:
            current = delta['current'].encode()
            self.assertEqual(raw.count(current), 1)
            remaining = raw.replace(current, b'', 1)
            moved = current + remaining
            if moved == raw:
                moved = remaining + current
            for changed in (remaining, raw.replace(current, current * 2, 1), moved,
                            raw.replace(current, current + b' ', 1)):
                with self.subTest(sha256=hashlib.sha256(changed).hexdigest()):
                    self.assertNotEqual(changed, raw)
                    with self.assertRaises(AssertionError):navigation.navigation_source_input(changed, navigation.NAVIGATION_PATH)
                    self.assertEqual(navigation.history_input(changed, navigation.NAVIGATION_PATH), changed)
                    with self.assertRaises(AssertionError):observer.source_input(changed, navigation.NAVIGATION_PATH)
                    with self.assertRaises(AssertionError):original_ui.verify_download_visual_fixture_source(changed)

    def test_actual_new_and_old_semantics_mutations_still_reach_original_guards(self):
        raw = (ROOT / navigation.NAVIGATION_PATH).read_bytes()
        changes = [(b'NavigationTypographyEvidence(this)', b'NavigationTypographyEvidence(null)'),
                   (b'"navigation-typography".equals(action)', b'"downloads".equals(action)'),
                   (b'downloads?WorkspaceNavigation.DOWNLOADS:WorkspaceNavigation.NONE', b'downloads?WorkspaceNavigation.NONE:WorkspaceNavigation.DOWNLOADS'),
                   (b'navigationTypographyEvidence.close()', b'navigationTypographyEvidence.toString()'),
                   (b'controller.setVisible(false);', b'controller.setVisible(true);'),
                   (b'downloadObservationNonces.contains(nonce)', b'false'),
                   (b'if(workspace!=null)workspace.close();', b'if(workspace!=null)workspace.toString();')]
        for before, after in changes:
            self.assertEqual(raw.count(before), 1)
            changed = raw.replace(before, after, 1)
            with self.subTest(anchor=before):
                self.assertNotEqual(changed, raw)
                with self.assertRaises(AssertionError):navigation.navigation_source_input(changed, navigation.NAVIGATION_PATH)
                with self.assertRaises(AssertionError):original_ui.verify_download_visual_fixture_source(changed)

    def test_types_paths_unknown_and_incomplete_sources_fail_closed(self):
        raw = (ROOT / navigation.NAVIGATION_PATH).read_bytes()
        for changed in (None, raw.decode(), bytearray(raw), memoryview(raw), True, b'', b'unknown', raw[:1024], raw + b'\n'):
            with self.assertRaises(AssertionError):navigation.navigation_source_input(changed, navigation.NAVIGATION_PATH)
        for path in (None, Path(navigation.NAVIGATION_PATH), '/' + navigation.NAVIGATION_PATH,
                     '../' + navigation.NAVIGATION_PATH, navigation.RUNNER):
            with self.assertRaises(AssertionError):navigation.navigation_source_input(raw, path)
        previous = navigation.navigation_source_input(raw, navigation.NAVIGATION_PATH)
        with self.assertRaises(AssertionError):navigation.navigation_source_input(previous, navigation.NAVIGATION_PATH)
        self.assertEqual(navigation.history_input(previous, navigation.NAVIGATION_PATH), previous)

    def test_retained_visual_oracle_reports_actual_selected_raw_source(self):
        path = ROOT / navigation.NAVIGATION_PATH
        raw = path.read_bytes()
        receipt = original_ui.verify_download_visual_fixture_source(raw)
        self.assertEqual(receipt['selectedFixtureSha256'], navigation.NAVIGATION_CURRENT_SHA256)
        self.assertEqual(receipt['originalFixtureSha256'], original_ui.PRE_DOWNLOAD_ISOLATION_FIXTURE_SHA256)
        self.assertFalse(receipt['actualAndroidExecution'])
        self.assertEqual(path.read_bytes(), raw)
        self.assertIn(b'NavigationTypographyEvidence(this)', raw)


if __name__ == '__main__':
    unittest.main(verbosity=2)
