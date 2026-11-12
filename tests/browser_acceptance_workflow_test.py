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
from released_workflow_comparison import released_toolchain_step as historical_toolchain_step
from released_workflow_comparison import released_job_field_input as ui_job_budget_field_input

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
                    found=next((at for at in range(position,len(current['steps'])) if historical_toolchain_step(current['steps'][at])==step),None)
                    self.assertIsNotNone(found,(name,step.get('name')));position=found+1
                if name=='build':
                    self.assertIn('timeout-minutes',job)
                for key,value in job.items():
                    if key=='steps':continue
                    if name=='build' and key=='timeout-minutes':
                        self.assertIs(type(value),int)
                        self.assertEqual(value,40)
                        self.assertIn(key,current)
                        self.assertIs(type(current[key]),int)
                        self.assertEqual(current[key],60)
                    else:
                        self.assertEqual(ui_job_budget_field_input(name,key,current[key]),value+['browser','tls'] if name=='verify' and key=='needs' else value)
    def test_single_pipeline_shares_actual_apk_and_gates_browser(self):
        self.assertEqual(self.new['on']['push']['branches'],['release/browser-2.1.0','release/browser-2.1.0-*','release/browser-2.1.1','release/browser-2.1.1-*','release/browser-2.1.2','release/browser-2.1.2-*','release/browser-2.1.3','release/browser-2.1.3-*','release/browser-2.1.4','release/browser-2.1.4-*','release/browser-2.1.5','release/browser-2.1.5-*'])
        self.assertIn('browser',self.new['jobs']['verify']['needs'])
        self.assertEqual(self.new['jobs']['browser']['needs'],'build')
        browser=self.new['jobs']['browser'];self.assertNotIn('continue-on-error',browser)
        body='\n'.join(step.get('run','') for step in browser['steps'])
        self.assertIn('ci_bundle.py restore --kind build',body);self.assertIn('tools/browser/run_integration.py',body)
        final='\n'.join(step.get('run','') for step in self.new['jobs']['verify']['steps'])
        self.assertIn('test "$BROWSER_RESULT" = success',final);self.assertIn('tools/browser/check_evidence.py',final)
        self.assertIn('browser-results.json',final)
        self.assertIn('tls',self.new['jobs']['verify']['needs'])
        tls=self.new['jobs']['tls']
        self.assertEqual(tls['needs'],'build');self.assertEqual(tls['timeout-minutes'],40)
        self.assertEqual(tls['permissions'],{'contents':'read','actions':'read'})
        self.assertNotIn('continue-on-error',tls)
        tls_body='\n'.join(step.get('run','') for step in tls['steps'])
        self.assertIn('ci_bundle.py restore --kind build',tls_body)
        workload=[step for step in tls['steps'] if step.get('name')=='Execute production Gecko web TLS cold policy and independent wire workloads']
        self.assertEqual(len(workload),1);self.assertNotIn('if',workload[0]);self.assertNotIn('continue-on-error',workload[0])
        for required in ('tools/browser/run_gecko_tls_integration.py','--source "$GITHUB_SHA"','--apk app/build/outputs/apk/integration/app-x86_64-integration.apk'):
            self.assertIn(required,workload[0]['run'])
        self.assertIn('test "$TLS_RESULT" = success',final)
    def test_host_api_dependency_is_pinned_before_current_profile_checks(self):
        release_steps=self.new['jobs']['build']['steps']
        history=[(index,step) for index,step in enumerate(release_steps) if step.get('name')=='Prepare fixed release source proof objects']
        self.assertEqual(len(history),1)
        history_index,history_step=history[0]
        self.assertNotIn('if',history_step)
        self.assertNotIn('continue-on-error',history_step)
        self.assertIn('set -euo pipefail',history_step['run'])
        self.assertIn('tools/gecko/prepare_profile_host_prerequisites.py --source-commit "$GITHUB_SHA"',history_step['run'])
        first_proof=next(index for index,step in enumerate(release_steps) if step.get('name')=='Verify strict cellular emulator preparation controls')
        self.assertLess(history_index,first_proof)
        profile=yaml.safe_load((ROOT/'.github/workflows/profile-upgrade-checks.yml').read_text())
        for workflow,job_name in ((self.new,'build'),(profile,'host-contracts')):
            with self.subTest(job=job_name):
                steps=workflow['jobs'][job_name]['steps']
                setup=[(index,step) for index,step in enumerate(steps) if step.get('name')=='Prepare pinned Android 35 host API']
                self.assertEqual(len(setup),1)
                index,step=setup[0]
                self.assertNotIn('if',step)
                self.assertNotIn('continue-on-error',step)
                self.assertEqual(step.get('shell'),'bash')
                self.assertIn('set -euo pipefail',step['run'])
                self.assertIn('"$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" \'platforms;android-35\'',step['run'])
                self.assertIn('4566663c3876e022b4fa4ced8c8697c4ab1688267f090114fd92d027b32e619b  $PROFILE_ANDROID_JAR',step['run'])
                self.assertIn('| sha256sum -c -',step['run'])
                self.assertIn('echo "PROFILE_ANDROID_JAR=$PROFILE_ANDROID_JAR" >> "$GITHUB_ENV"',step['run'])
                checks=[at for at,item in enumerate(steps) if "-p 'profile_*_test.py'" in item.get('run','')]
                self.assertEqual(len(checks),1)
                self.assertLess(index,checks[0])
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
