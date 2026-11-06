"""Fixture lifecycle/root regression; no Android or native-setting proof."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FixtureFrameworkRootTest(unittest.TestCase):
    def test_actual_fixture_context_and_storage_policy(self):
        java_bin = os.environ.get('PROFILE_JAVA') or shutil.which('java')
        java = Path(os.environ.get('PROFILE_JAVA_HOME') or os.environ.get('JAVA_HOME') or Path(java_bin).resolve().parents[1])
        jar = Path(os.environ.get('PROFILE_JSON_JAR', ROOT / 'work/profile-host/json.jar'))
        self.assertTrue((java / 'bin/javac').is_file(), 'Actual JDK required')
        self.assertTrue(jar.is_file(), 'Actual JSON jar required')
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'result.json'
            subprocess.run(['python3', str(ROOT / 'tests/profile-fixture-root-host/run.py'), '--java-home', str(java), '--json-jar', str(jar), '--output', str(output)], check=True, capture_output=True, text=True, timeout=300)
            report = json.loads(output.read_text())
            self.assertEqual(report['passed'], 33)
            self.assertEqual(report['total'], 33)
            self.assertEqual(len(report['compiledCounterfeits']), 4)
            self.assertTrue(report['executionInputsUnchanged'])
            self.assertFalse(report['actualAndroidExecution'])
            self.assertFalse(report['nativeSettingReadback'])

    def test_template_and_resource_inherit_same_actual_entry(self):
        template = (ROOT / 'tests/gecko/GeckoTemplateIntegrationActivity.java').read_text()
        resource = (ROOT / 'tests/gecko/ResourcePressureIntegrationActivity.java').read_text()
        for text in (template, resource):
            self.assertIn('extends GeckoIdentityPrototypeIntegrationActivity', text)
        self.assertNotIn('void openBrowser(', template)
        self.assertIn('super.openBrowser();if(finished||view==null)return;', resource)


if __name__ == '__main__':
    unittest.main()
