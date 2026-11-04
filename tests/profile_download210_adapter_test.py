"""Fail-closed scaffold compatibility, with current production methods kept verbatim."""
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

import profile_download_names_catalog_compatibility_test as historical

ROOT=Path(__file__).resolve().parents[1]
NAMES=ROOT/'tests/download-names-host'
spec=importlib.util.spec_from_file_location('actual_download210_names',NAMES/'run.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
sha=lambda text:hashlib.sha256(text.encode()).hexdigest()


class Reviewed210ScaffoldControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        historical.DownloadNamesCatalogCompatibilityTest.setUpClass()
        cls.legacy=historical.DownloadNamesCatalogCompatibilityTest('test_exact_addition_retains_all_four_original_guards')
        cls.current=(ROOT/'app/src/main/java/local/pocketchat/DesignDownloads.java').read_text()
        cls.manifest=runner._review46.scaffold_manifest()

    def guards(self,source):
        self.legacy.guards_reach_compile(self.legacy.current,source)

    def test_provenance_connects_actual_current_to_original_reviewed46_digest(self):
        original=json.loads((NAMES/'reviewed46-inverse.json').read_text())['files']['DesignDownloads.java']
        self.assertEqual(self.manifest['before']['commit'],'5900426428e00a95acf5126f6154f34ff2d46930')
        self.assertEqual(self.manifest['after']['commit'],'856e7ccbb8f032d5ced7b01c6f43884f9d61a4b7')
        self.assertEqual(self.manifest['before']['sha256'],original['approvedSha256'])
        self.assertEqual(sha(self.current),self.manifest['after']['sha256'])
        projected=runner._review46.remove_scaffold(self.current,'DesignDownloads.java',runner.member)
        self.assertEqual(sha(projected),self.manifest['before']['sha256'])

    def test_every_current_behavior_method_remains_verbatim_before_historical_guards(self):
        projected=runner._review46.remove_scaffold(self.current,'DesignDownloads.java',runner.member)
        for needle,digest in self.manifest['testedMethodSha256'].items():
            with self.subTest(needle=needle):
                actual=runner.member(self.current,needle)
                self.assertEqual(sha(actual),digest)
                self.assertEqual(actual,runner.member(projected,needle))
        with self.assertRaises(historical.CompilationReached):self.guards(self.current)

    def test_mutating_each_actual_current_behavior_method_is_rejected(self):
        changes={
            'void apply(JSONArray data,':('row.binding.applied(next);','row.binding.applied(null);'),
            'void bind(JSONObject row,':('visible(location,false);','visible(location,true);'),
            'static void text(TextView':('view.setText(value);','view.setText("wrong");'),
            'static void visible(View':('View.VISIBLE:View.GONE','View.GONE:View.VISIBLE'),
            'static String timeLabel(':('DateFormat.SHORT','DateFormat.LONG'),
        }
        for needle,(old,new) in changes.items():
            with self.subTest(needle=needle):
                body=runner.member(self.current,needle)
                self.assertIn(old,body)
                changed=self.current.replace(body,body.replace(old,new,1),1)
                with self.assertRaisesRegex(AssertionError,'current tested method drift'):
                    self.guards(changed)

    def test_changed_scaffold_cannot_be_silently_projected(self):
        changed=self.current.replace('preferences=Profiles.global(a).getSharedPreferences("download-discovery",0);','preferences=Profiles.global(a).getSharedPreferences("unknown-scaffold",0);',1)
        self.assertNotEqual(changed,self.current)
        with self.assertRaisesRegex(AssertionError,'210 scaffold must occur exactly once'):
            self.guards(changed)

    def test_duplicate_scaffold_is_rejected(self):
        block=self.manifest['edits'][0]['after']
        self.assertEqual(self.current.count(block),1)
        with self.assertRaisesRegex(AssertionError,'210 scaffold must occur exactly once'):
            self.guards(self.current+block)

    def test_unknown_unrelated_source_reaches_and_fails_original_whole_file_guard(self):
        changed=self.current.replace('package local.pocketchat;','package local.pocketchat;\n// UNKNOWN_UNREVIEWED_SOURCE',1)
        projected=runner.remove_reviewed38(changed)
        self.assertIn('UNKNOWN_UNREVIEWED_SOURCE',projected)
        with self.assertRaisesRegex(AssertionError,'allOtherDownloadUiBytes'):
            self.guards(changed)

    def test_manifest_tampering_is_rejected(self):
        from unittest import mock
        original=Path.read_bytes
        def altered(path):
            value=original(path)
            return value+b' ' if path==NAMES/'reviewed210-scaffold-inverse.json' else value
        with mock.patch.object(Path,'read_bytes',altered):
            with self.assertRaisesRegex(AssertionError,'210 scaffold manifest bytes changed'):
                runner.remove_reviewed46(self.current)


if __name__=='__main__':unittest.main(verbosity=2)
