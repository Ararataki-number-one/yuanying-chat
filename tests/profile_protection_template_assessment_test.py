"""Template guidance cannot promote settings or old manual records into safety proof."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
PRODUCTION=ROOT/'app/src/main/java/local/pocketchat'
PINS={'desktop':'3ea61b2a06e31edf1c91134fe9106b0ebb16628be169f3db75bc7a2b06b45796',
      'android-json':'dfb7bae2f404cfe0b72b4d23944698cb716b7665171812a0a4d0f5926c0fac79'}
SOURCES=[PRODUCTION/name for name in ('J.java','BrowserIdentitySpec.java','NativeCapabilityManifest.java',
    'FingerprintObservationHistory.java','FingerprintDeepBaseline.java','FingerprintContextBaselines.java',
    'AuditReport.java','FingerprintReportComparison.java','ProtectionTemplateAssessment.java')]
SOURCES += [ROOT/name for name in ('tests/browser-runtime/fingerprint-report-stubs/BrowserNetworkGuard.java',
    'tests/fingerprint-baseline-host/FingerprintDeepBaselineHost.java',
    'tests/fingerprint-context-baseline-host/FingerprintContextBaselinesHost.java',
    'tests/fingerprint-comparison-host/FingerprintReportComparisonHost.java',
    'tests/protection-template-host/ProtectionTemplateAssessmentHost.java')]

class ProtectionTemplateAssessmentTest(unittest.TestCase):
    def test_current_native_receipts_capabilities_and_owner_bound_manual_evidence(self):
        java=os.environ.get('PROFILE_JAVA') or shutil.which('java')
        self.assertTrue(java,'JDK17+ required')
        jars={'desktop':Path(os.environ.get('PROFILE_JSON_JAR',ROOT/'work/profile-host/json.jar')),
              'android-json':Path(os.environ.get('PROFILE_ANDROID_JSON_JAR',ROOT/'work/profile-host/android-json.jar'))}
        before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [*SOURCES,Path(__file__)]}
        runs=[]
        for name,jar in jars.items():
            self.assertTrue(jar.is_file(),'Pinned JSON jar required: '+str(jar))
            self.assertEqual(hashlib.sha256(jar.read_bytes()).hexdigest(),PINS[name])
            with tempfile.TemporaryDirectory(prefix='protection-template-host-') as output:
                built=subprocess.run([java,'-m','jdk.compiler/com.sun.tools.javac.Main','--release','8','-encoding','UTF-8',
                    '-cp',str(jar),'-d',output,*map(str,SOURCES)],capture_output=True,text=True,timeout=40)
                self.assertEqual(built.returncode,0,built.stdout+built.stderr)
                run=subprocess.run([java,'-cp',output+os.pathsep+str(jar),'local.pocketchat.ProtectionTemplateAssessmentHost'],
                    capture_output=True,text=True,timeout=20)
                self.assertEqual(run.returncode,0,run.stdout+run.stderr)
                report=json.loads(run.stdout)
                self.assertEqual(report['status'],'passed')
                self.assertEqual(report['total'],report['passed'])
                self.assertGreaterEqual(report['total'],35)
                self.assertEqual(len({row['name'] for row in report['checks']}),report['total'])
                self.assertTrue(all(row['pass'] is True for row in report['checks']))
                for flag in ('actualAndroidExecution','actualGeckoExecution','physicalPhoneAcceptance','protectionEffectivenessAcceptance'):
                    self.assertIs(report[flag],False)
                runs.append({'runtime':name,'report':report})
        self.assertEqual(before,{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [*SOURCES,Path(__file__)]})
        target=ROOT/'work/protection-template/host-results.json';target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps({'status':'passed','sourceSha256':before,'runs':runs,
            'actualAndroidExecution':False,'actualGeckoExecution':False},ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__': unittest.main()
