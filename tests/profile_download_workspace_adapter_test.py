"""Current download UI executes verbatim; exact inverse feeds historical guards."""
import hashlib
from pathlib import Path
import unittest
from unittest import mock

import profile_download_names_catalog_compatibility_test as historical

ROOT = Path(__file__).resolve().parents[1]
NAMES = ROOT / 'tests/download-names-host'
runner = historical.runner
sha = lambda text: hashlib.sha256(text.encode()).hexdigest()


class WorkspaceUiCompatibilityControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        historical.DownloadNamesCatalogCompatibilityTest.setUpClass()
        cls.legacy = historical.DownloadNamesCatalogCompatibilityTest('test_exact_addition_retains_all_four_original_guards')
        cls.current = (ROOT / 'app/src/main/java/local/pocketchat/DesignDownloads.java').read_text()
        cls.manifest = runner._workspace_ui.manifest()

    def test_exact_ui_delta_reaches_the_unchanged_reviewed210_source(self):
        self.assertEqual(self.manifest['before']['commit'], 'f274364e370e88aa6f94dd60945bd9ffdc589a4b')
        self.assertEqual(self.manifest['before']['tree'], '2d49cd16dcfce079dedd831c7aded7116b0e8400')
        self.assertEqual(self.manifest['before']['sha256'], runner._review46.scaffold_manifest()['after']['sha256'])
        self.assertEqual(sha(self.current), self.manifest['after']['sha256'])
        projected = runner.remove_workspace_ui(self.current)
        self.assertEqual(sha(projected), self.manifest['before']['sha256'])
        self.assertEqual(sha(runner.remove_reviewed38(self.current)), '8433e4cc4c72d8c6ed0b2f141ebcca762a5f357f2acb877a0a19b2814be98ed0')

    def test_generated_host_keeps_current_apply_bind_and_helpers_verbatim(self):
        captured = []
        write = Path.write_text

        def observe(path, text, *args, **kwargs):
            if path.name == 'DownloadNamesHost.java':
                captured.append(text)
            return write(path, text, *args, **kwargs)

        with mock.patch.object(Path, 'write_text', observe):
            with self.assertRaises(historical.CompilationReached):
                self.legacy.guards_reach_compile(self.legacy.raw_current, self.current)
        self.assertEqual(len(captured), 1)
        host = runner.member(captured[0], 'class DesignDownloads {')
        row = runner.member(host, 'static final class Row {')
        controller = runner.member(host, 'static final class Controller {')
        actual_apply = runner.member(controller, 'void productionApply(JSONArray data,').replace('void productionApply(JSONArray data,', 'void apply(JSONArray data,', 1)
        self.assertEqual(actual_apply, runner.member(self.current, 'void apply(JSONArray data,'))
        for needle in ('void bind(JSONObject row,', 'static void text(TextView', 'static void visible(View'):
            self.assertEqual(runner.member(row, needle), runner.member(self.current, needle))
        self.assertEqual(runner.member(host, 'static String timeLabel('), runner.member(self.current, 'static String timeLabel('))
        self.assertNotEqual(runner.member(row, 'void bind(JSONObject row,'), runner.member(runner.remove_workspace_ui(self.current), 'void bind(JSONObject row,'))

    def test_every_current_method_digest_is_verified_before_projection(self):
        mutations = {
            'void apply(JSONArray data,': ('row.binding.applied(next);', 'row.binding.applied(null);'),
            'void bind(JSONObject row,': ('text(stateLabel,DownloadTasks.label(state));', 'text(stateLabel,"incorrect-state");'),
            'static void text(TextView': ('view.setText(value);', 'view.setText("wrong");'),
            'static void visible(View': ('View.VISIBLE:View.GONE', 'View.GONE:View.VISIBLE'),
            'static String timeLabel(': ('DateFormat.SHORT', 'DateFormat.LONG'),
            'void refresh(int selected)': ('reads.complete();', 'requestScope.invalidate();reads.complete();'),
            'void syncCollection()': ('collecting?"完成选择":"收集文件"', '!collecting?"完成选择":"收集文件"'),
            'void selection(boolean mode,': ('icon.setVisibility(shown?View.GONE:View.VISIBLE);', 'icon.setVisibility(shown?View.VISIBLE:View.GONE);'),
            'String collectionKey()': ('DownloadCollection.key(value)', '"incorrect-publication"'),
        }
        self.assertEqual(set(mutations), set(self.manifest['currentMethodSha256']))
        for needle, (old, new) in mutations.items():
            with self.subTest(needle=needle):
                body = runner.member(self.current, needle)
                self.assertEqual(sha(body), self.manifest['currentMethodSha256'][needle])
                self.assertIn(old, body)
                changed = self.current.replace(body, body.replace(old, new, 1), 1)
                with self.assertRaisesRegex(AssertionError, 'current tested method drift: workspace UI'):
                    runner.remove_reviewed38(changed)

    def test_changed_ui_scaffold_is_rejected(self):
        old = 'search=DesignUi.searchInput(searchBox,"搜索文件、类型或环境");'
        self.assertEqual(self.current.count(old), 1)
        changed = self.current.replace(old, old.replace('搜索文件、类型或环境', 'unreviewed-scaffold'), 1)
        with self.assertRaisesRegex(AssertionError, 'workspace UI must occur exactly once'):
            runner.remove_reviewed38(changed)

    def test_duplicate_current_ui_block_is_rejected(self):
        block = self.manifest['edits'][0]['after']
        self.assertEqual(self.current.count(block), 1)
        with self.assertRaisesRegex(AssertionError, 'workspace UI must occur exactly once'):
            runner.remove_reviewed38(self.current + block)

    def test_manifest_tampering_is_rejected(self):
        original = Path.read_bytes

        def altered(path):
            value = original(path)
            return value + b' ' if path == NAMES / 'reviewed-workspace-ui-inverse.json' else value

        with mock.patch.object(Path, 'read_bytes', altered):
            with self.assertRaisesRegex(AssertionError, 'workspace UI manifest bytes changed'):
                runner.remove_reviewed38(self.current)

    def test_unknown_source_drift_reaches_original_whole_file_guard(self):
        changed = self.current.replace('package local.pocketchat;', 'package local.pocketchat;\n// UNKNOWN_WORKSPACE_UI_SOURCE', 1)
        self.assertIn('UNKNOWN_WORKSPACE_UI_SOURCE', runner.remove_reviewed38(changed))
        with self.assertRaisesRegex(AssertionError, 'allOtherDownloadUiBytes'):
            self.legacy.guards_reach_compile(self.legacy.raw_current, changed)

    def test_original_inverse_manifests_remain_byte_pinned(self):
        expected = {
            'reviewed38-inverse.json': 'd47ff93f57ba66ca2ebf3aa10c35a36721fbf78d3cf200a3318173cbf728495e',
            'reviewed46-inverse.json': 'ca4b9668e0dfa59cc35df2782c31729824ca1705baf7d55e1f731644e6aa5e6c',
            'reviewed210-scaffold-inverse.json': '67b4b7872c6a8c66b8ded982ccf75f4dbcde58481262ca0c140070420bb614df',
        }
        for name, digest in expected.items():
            self.assertEqual(hashlib.sha256((NAMES / name).read_bytes()).hexdigest(), digest)


if __name__ == '__main__':
    unittest.main(verbosity=2)
