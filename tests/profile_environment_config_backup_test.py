"""Portable configuration crypto and strict parse boundaries, not phone acceptance."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
PRODUCTION = ROOT / 'app/src/main/java/local/pocketchat'
PINS = {'desktop': '3ea61b2a06e31edf1c91134fe9106b0ebb16628be169f3db75bc7a2b06b45796',
        'android-json': 'dfb7bae2f404cfe0b72b4d23944698cb716b7665171812a0a4d0f5926c0fac79'}


class EnvironmentConfigBackupTest(unittest.TestCase):
    def test_backup_entry_is_private_and_existing_manifest_protections_remain(self):
        source = ROOT / 'app/src/main/AndroidManifest.xml'
        root = ET.parse(source).getroot()
        android = '{http://schemas.android.com/apk/res/android}'
        application = root.find('application')
        self.assertEqual(application.get(android + 'allowBackup'), 'false')
        # Both general browsing surfaces admit public HTTP(S). The independent
        # audit/resource interception boundary still requires public HTTPS.
        self.assertEqual(application.get(android + 'usesCleartextTraffic'), 'true')
        self.assertEqual(application.get(android + 'networkSecurityConfig'), '@xml/network_security')
        guard=(PRODUCTION/'BrowserNetworkGuard.java').read_text()
        self.assertIn('return !allowed()||!publicHttps(uri)?denied():null;',guard)
        self.assertIn('"https".equalsIgnoreCase(uri.getScheme())',guard)
        gecko=(PRODUCTION/'GeckoWebView.java').read_text()
        self.assertIn('protected boolean allowedUrl(String target){return target!=null&&BrowserNetworkGuard.publicWeb(Uri.parse(target));}',gecko)
        self.assertIn('static boolean publicWeb(Uri uri){return uri!=null&&GeckoNavigationPolicy.publicWeb(uri.toString());}',guard)
        self.assertIn('static boolean publicWeb(String url){return BrowserAddressPolicy.allowed(url);}',(PRODUCTION/'GeckoNavigationPolicy.java').read_text())
        browser=[a for a in application.findall('activity') if a.get(android+'name')=='local.pocketchat.BrowserActivity']
        self.assertEqual(len(browser),1)
        self.assertEqual(browser[0].get(android+'exported'),'true')
        self.assertEqual(browser[0].get(android+'launchMode'),'singleTask')
        self.assertEqual(browser[0].get(android+'taskAffinity'),'local.pocketchat.browser0')
        filters=browser[0].findall('intent-filter');self.assertEqual(len(filters),1)
        self.assertEqual([a.get(android+'name') for a in filters[0].findall('action')],['android.intent.action.VIEW'])
        self.assertEqual({a.get(android+'name') for a in filters[0].findall('category')},{'android.intent.category.DEFAULT','android.intent.category.BROWSABLE'})
        self.assertEqual({a.get(android+'scheme') for a in filters[0].findall('data')},{'http','https'})
        for slot in range(1,8):
            profile=[a for a in application.findall('activity') if a.get(android+'name')=='local.pocketchat.BrowserActivity$Profile'+str(slot)]
            self.assertEqual(len(profile),1)
            self.assertEqual(profile[0].get(android+'exported'),'false')
            self.assertEqual(profile[0].get(android+'process'),':profile'+str(slot))
            self.assertEqual(profile[0].get(android+'taskAffinity'),'local.pocketchat.browser'+str(slot))
            self.assertEqual(profile[0].findall('intent-filter'),[])
        activities = [a for a in application.findall('activity') if a.get(android + 'name') == 'local.pocketchat.EnvironmentConfigBackupActivity']
        self.assertEqual(len(activities), 1)
        self.assertEqual(activities[0].get(android + 'exported'), 'false')
        self.assertEqual(activities[0].findall('intent-filter'), [])

    def test_restore_transaction_ownership_and_fault_boundaries(self):
        java = os.environ.get('PROFILE_JAVA') or shutil.which('java')
        self.assertTrue(java, 'JDK17+ required')
        sources = [PRODUCTION / name for name in ['J.java', 'BrowserIdentitySpec.java', 'EnvironmentConfigBackup.java', 'EnvironmentConfigTransfer.java']]
        sources += [ROOT / 'tests/environment-config-backup-host' / name for name in ['TransferDoubles.java', 'EnvironmentConfigTransferHost.java', 'android/content/Context.java', 'android/content/SharedPreferences.java']]
        before = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [*sources, Path(__file__)]}
        jars = {'desktop': Path(os.environ.get('PROFILE_JSON_JAR', ROOT / 'work/profile-host/json.jar')),
                'android-json': Path(os.environ.get('PROFILE_ANDROID_JSON_JAR', ROOT / 'work/profile-host/android-json.jar'))}
        runs = []
        for runtime, jar in jars.items():
            self.assertTrue(jar.is_file(), 'Pinned JSON jar required: ' + str(jar))
            self.assertEqual(hashlib.sha256(jar.read_bytes()).hexdigest(), PINS[runtime])
            with tempfile.TemporaryDirectory(prefix='environment-config-transfer-') as classes:
                built = subprocess.run([java, '-m', 'jdk.compiler/com.sun.tools.javac.Main', '--release', '8', '-encoding', 'UTF-8',
                                        '-cp', str(jar), '-d', classes, *map(str, sources)], capture_output=True, text=True, timeout=30)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                result = subprocess.run([java, '-cp', classes + os.pathsep + str(jar), 'local.pocketchat.EnvironmentConfigTransferHost'],
                                        capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                report = json.loads(result.stdout)
                self.assertEqual(report['status'], 'passed')
                self.assertGreaterEqual(report['passed'], 35)
                self.assertTrue(all(row['pass'] for row in report['checks']))
                self.assertIs(report['actualAndroidExecution'], False)
                self.assertIs(report['actualSQLiteExecution'], False)
                runs.append(dict(runtime=runtime, report=report))
        self.assertEqual(before, {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [*sources, Path(__file__)]})
        output = ROOT / 'work/environment-config-backup/transfer-results.json'
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(dict(status='passed', sourceSha256=before, runs=runs,
                                         actualAndroidExecution=False, actualSQLiteExecution=False), ensure_ascii=False, indent=2) + '\n')

    def test_crypto_and_strict_portable_payload(self):
        java = os.environ.get('PROFILE_JAVA') or shutil.which('java')
        self.assertTrue(java, 'JDK17+ required')
        sources = [PRODUCTION / name for name in ['J.java', 'BrowserIdentitySpec.java', 'EnvironmentConfigBackup.java']]
        sources.append(ROOT / 'tests/environment-config-backup-host/EnvironmentConfigBackupHost.java')
        before = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [*sources, Path(__file__)]}
        jars = {'desktop': Path(os.environ.get('PROFILE_JSON_JAR', ROOT / 'work/profile-host/json.jar')),
                'android-json': Path(os.environ.get('PROFILE_ANDROID_JSON_JAR', ROOT / 'work/profile-host/android-json.jar'))}
        runs = []
        for runtime, jar in jars.items():
            self.assertTrue(jar.is_file(), 'Pinned JSON jar required: ' + str(jar))
            self.assertEqual(hashlib.sha256(jar.read_bytes()).hexdigest(), PINS[runtime])
            with tempfile.TemporaryDirectory(prefix='environment-config-backup-') as classes:
                built = subprocess.run([java, '-m', 'jdk.compiler/com.sun.tools.javac.Main', '--release', '8', '-encoding', 'UTF-8',
                                        '-cp', str(jar), '-d', classes, *map(str, sources)], capture_output=True, text=True, timeout=30)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                result = subprocess.run([java, '-cp', classes + os.pathsep + str(jar), 'local.pocketchat.EnvironmentConfigBackupHost'],
                                        capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                report = json.loads(result.stdout)
                self.assertEqual(report['status'], 'passed')
                self.assertGreaterEqual(report['passed'], 80)
                self.assertTrue(all(row['pass'] for row in report['checks']))
                self.assertIs(report['physicalPhoneAcceptance'], False)
                runs.append(dict(runtime=runtime, report=report))
        self.assertEqual(before, {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [*sources, Path(__file__)]})
        output = ROOT / 'work/environment-config-backup/host-results.json'
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(dict(status='passed', sourceSha256=before, runs=runs,
                                         actualAndroidExecution=False, actualUiExecution=False), ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    unittest.main()
