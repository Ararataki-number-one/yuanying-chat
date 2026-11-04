"""Ensure the additive browser workflow retains every original release check."""
from pathlib import Path
import unittest
import yaml

ROOT=Path(__file__).resolve().parents[1]

class BrowserWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old=yaml.safe_load((ROOT/'.github/workflows/gecko-integration.yml').read_text())
        cls.new=yaml.safe_load((ROOT/'.github/workflows/browser-2_1-acceptance.yml').read_text())
    def test_original_checks_retained_in_order(self):
        for name,job in self.old['jobs'].items():
            with self.subTest(job=name):
                current=self.new['jobs'][name];position=0
                for step in job['steps']:
                    found=next((at for at in range(position,len(current['steps'])) if current['steps'][at]==step),None)
                    self.assertIsNotNone(found,(name,step.get('name')));position=found+1
                for key,value in job.items():
                    if key=='steps':continue
                    self.assertEqual(current[key],value+['browser'] if name=='verify' and key=='needs' else value)
    def test_single_pipeline_shares_actual_apk_and_gates_browser(self):
        self.assertEqual(self.new['on']['push']['branches'],['release/browser-2.1.0','release/browser-2.1.0-*'])
        self.assertIn('browser',self.new['jobs']['verify']['needs'])
        self.assertEqual(self.new['jobs']['browser']['needs'],'build')
        browser=self.new['jobs']['browser'];self.assertNotIn('continue-on-error',browser)
        body='\n'.join(step.get('run','') for step in browser['steps'])
        self.assertIn('ci_bundle.py restore --kind build',body);self.assertIn('tools/browser/run_integration.py',body)
        final='\n'.join(step.get('run','') for step in self.new['jobs']['verify']['steps'])
        self.assertIn('test "$BROWSER_RESULT" = success',final);self.assertIn('tools/browser/check_evidence.py',final)
        self.assertIn('browser-results.json',final)
    def test_new_host_suites_and_exact_history_are_mandatory(self):
        body='\n'.join(step.get('run','') for step in self.new['jobs']['build']['steps'])
        self.assertIn('tools/browser/prepare_baselines.py',body);self.assertIn('tools/browser/run_host_checks.py',body)
        lint=[step for step in self.new['jobs']['build']['steps'] if ':app:lintRelease' in step.get('run','')]
        self.assertEqual(len(lint),1);self.assertNotIn('continue-on-error',lint[0]);self.assertIn('set -euo pipefail',lint[0]['run'])
        runner=(ROOT/'tools/browser/run_host_checks.py').read_text()
        for script in ['browser-address-host','browser-files-host','browser-permissions-host','browser-preferences-host','browser-library-host','chromium-route-host','ux-shell-host','loading-performance-host','chat-progress-performance-host','chat-chrome-performance-host','browser-controls-performance-host','browser-transcript-order-host','transcript-store-performance-host']:
            self.assertIn('tests/'+script+'/',runner)
    def test_split_artifacts_never_include_signing_inputs(self):
        upload=[step for step in self.new['jobs']['build']['steps'] if 'official-sdk' in step.get('with',{}).get('name','') or 'derived-sdk' in step.get('with',{}).get('name','') or step.get('with',{}).get('name','').endswith('-apks')]
        self.assertEqual(len(upload),3)
        for step in upload:
            for line in step['with']['path'].splitlines():
                self.assertNotIn('private',line);self.assertNotIn('.jks',line);self.assertNotIn('.keystore',line);self.assertNotIn('.pem',line)
        self.assertIn('work/native-caret-sdk/maven/',upload[1]['with']['path'])

if __name__=='__main__':unittest.main(verbosity=2)
