"""Actual settings-maintenance wake on bounded JVM actors; no Android/Gecko acceptance."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PINS = {'json.jar': '3ea61b2a06e31edf1c91134fe9106b0ebb16628be169f3db75bc7a2b06b45796',
        'android-json.jar': 'dfb7bae2f404cfe0b72b4d23944698cb716b7665171812a0a4d0f5926c0fac79'}


class DeferredBrowserWake46Tests(unittest.TestCase):
    def test_actual_event_wake_and_existing_draft_protection_both_json(self):
        java = Path(os.environ.get('PROFILE_JAVA') or shutil.which('java') or '')
        self.assertTrue(java.is_file(), 'JDK17 is required')
        jdk = java.resolve().parent.parent
        self.assertTrue((jdk / 'bin/javac').is_file())
        output = ROOT / 'work/deferred-browser-wake46-profile'
        reports = []
        source = ROOT / 'app/src/main/java/local/pocketchat/ChatSession.java'
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        for jarname, pin in PINS.items():
            configured = os.environ.get('PROFILE_JSON_JAR' if jarname == 'json.jar' else 'PROFILE_ANDROID_JSON_JAR')
            jar = Path(configured) if configured else ROOT / 'work/profile-host' / jarname
            self.assertTrue(jar.is_file())
            self.assertEqual(hashlib.sha256(jar.read_bytes()).hexdigest(), pin)
            target = output / jarname / 'results.json'
            run = subprocess.run([sys.executable, str(ROOT / 'tests/deferred-browser-wake-host/run.py'),
                                  '--java-home', str(jdk), '--json-jar', str(jar), '--output', str(target)],
                                 capture_output=True, text=True, timeout=90)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            report = json.loads(target.read_text())
            self.assertEqual(report['status'], 'passed')
            self.assertEqual(report['count'], 30)
            self.assertTrue(all(row['pass'] for row in report['checks']))
            self.assertFalse(report['actualAndroidExecution'])
            self.assertFalse(report['backgroundReplyDetection'])
            self.assertEqual(report['replyServiceStarts'], 0)
            self.assertEqual(report['sourceSha256'], before)
            reports.append(report)
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), before)
        output.mkdir(parents=True, exist_ok=True)
        (output / 'profile-results.json').write_text(json.dumps(dict(
            status='passed', runs=2, checksPerRun=30, sourceSha256=before,
            actualAndroidExecution=False, actualGeckoExecution=False,
            backgroundReplyDetectionEnabled=False, actualPhysicalPhoneAcceptance=False,
            scope='Actual ChatSession work-ending methods and one-shot wake, complete DeferredBrowserSettings and TaskGuardSnapshot on explicit DOM/looper/storage/service edges.'), indent=2) + '\n')


if __name__ == '__main__':
    unittest.main(verbosity=2)
