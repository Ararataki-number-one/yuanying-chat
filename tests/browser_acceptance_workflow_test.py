"""Ensure the additive browser workflow retains every original release check."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
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
        self.assertEqual(self.new['on']['push']['branches'][:6],['release/browser-2.1.0','release/browser-2.1.0-*','release/browser-2.1.1','release/browser-2.1.1-*','release/browser-2.1.2','release/browser-2.1.2-*'])
        self.assertEqual(self.new['on']['push']['branches'][6:],['release/browser-2.1.3','release/browser-2.1.3-*'])
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

    def test_actual_manifest_runtime_names_and_browser_fixture_contract(self):
        android='{http://schemas.android.com/apk/res/android}'
        manifest=ROOT/'tests/gecko/AndroidManifest.xml'
        application=ET.parse(manifest).getroot().find('application')
        activities=[item for item in application.findall('activity') if item.get(android+'name')=='local.pocketchat.BrowserIntegrationActivity']
        self.assertEqual(len(activities),1)
        fixture=activities[0]
        self.assertEqual(fixture.get(android+'taskAffinity'),'local.pocketchat.test.browser_probe')
        self.assertEqual(fixture.get(android+'launchMode'),'singleTask')
        self.assertEqual(fixture.get(android+'exported'),'true')
        self.assertIsNone(fixture.get(android+'process'))
        with tempfile.TemporaryDirectory(prefix='browser-manifest-contract-') as directory:
            target=Path(directory)/'results.json'
            command=[sys.executable,str(ROOT/'tests/browser-manifest-host/run.py'),'--output',str(target)]
            if os.environ.get('JAVA_HOME'):command+=['--java-home',os.environ['JAVA_HOME']]
            result=subprocess.run(command,cwd=ROOT,text=True,capture_output=True,timeout=60)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            report=json.loads(target.read_text())
            self.assertEqual(report['status'],'passed')
            self.assertEqual(report['passed'],report['total'])
            self.assertGreaterEqual(report['manifestCount'],4)
            self.assertTrue(report['executionInputsUnchanged'])
            self.assertTrue(report['actualAospNameMethodJvmExecution'])
            self.assertIs(report['actualAndroidExecution'],False)
            self.assertIs(report['actualPackageManagerExecution'],False)
            self.assertEqual(report['sourceFiles']['tests/gecko/AndroidManifest.xml'],hashlib.sha256(manifest.read_bytes()).hexdigest())
            controls=[row for row in report['checks'] if row['name'].startswith('control:')]
            self.assertEqual(len(controls),15)
            self.assertTrue(all(row['passed'] for row in controls))

if __name__=='__main__':unittest.main(verbosity=2)
