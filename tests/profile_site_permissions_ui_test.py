"""Actual permission panel/SDK adapter compile; app/Gecko edges are explicit doubles.

This host check does not execute the Android UI or a Gecko permission request.
The release APK's complete compilation and controlled-device checks remain separate.
"""
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


class SitePermissionsUiTest(unittest.TestCase):
    def test_permission_adapters_compile_against_android_framework(self):
        java = os.environ.get('PROFILE_JAVA') or shutil.which('java')
        self.assertTrue(java, 'JDK17+ is required')
        configured = os.environ.get('PROFILE_ANDROID_JAR')
        sdk_root = os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT')
        choices = [Path(configured)] if configured else ([Path(sdk_root) / 'platforms' / version / 'android.jar'
                  for version in ('android-37.1', 'android-37', 'android-35')] if sdk_root else [])
        framework = next((path for path in choices if path.is_file()), None)
        self.assertIsNotNone(framework, 'A real Android SDK platform JAR is required')
        names = ['SitePermissions.java', 'GeckoSitePermissions.java', 'SitePermissionsUi.java']
        sources = [PRODUCTION / name for name in names]
        sources += sorted((ROOT / 'tests/site-permissions-ui-host').rglob('*.java'))
        before = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [*sources, Path(__file__)]}
        with tempfile.TemporaryDirectory(prefix='site-permissions-ui-') as classes:
            result = subprocess.run([java, '-m', 'jdk.compiler/com.sun.tools.javac.Main', '--release', '8', '-encoding', 'UTF-8',
                                     '-cp', str(framework), '-d', classes, *map(str, sources)], capture_output=True, text=True, timeout=45)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(before, {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [*sources, Path(__file__)]})
        output = ROOT / 'work/site-permissions/ui-compile.json'
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(dict(status='passed', sourceSha256=before,
                                         androidFrameworkJarSha256=hashlib.sha256(framework.read_bytes()).hexdigest(),
                                         actualAndroidFrameworkClasses=True, applicationAndGeckoBoundaryDoubles=True,
                                         actualAndroidExecution=False, actualGeckoExecution=False,
                                         physicalPhoneAcceptance=False), indent=2) + '\n')

    def test_existing_hardware_refusals_and_manifest_capabilities_are_preserved(self):
        browser = (PRODUCTION / 'GeckoWebView.java').read_text()
        self.assertTrue('onAndroidPermissionsRequest(GeckoSession s,String[] permissions,Callback callback){callback.reject();}' in browser)
        self.assertTrue('onMediaPermissionRequest(GeckoSession s,String origin,MediaSource[] video,MediaSource[] audio,MediaCallback callback){callback.reject();}' in browser)
        manifest = (ROOT / 'app/src/main/AndroidManifest.xml').read_text()
        # The permission declarations support only explicit Chromium requests.
        # The two original Gecko refusals above remain unconditional.
        application=ET.fromstring(manifest);android='{http://schemas.android.com/apk/res/android}'
        declared={row.get(android+'name') for row in application.findall('uses-permission')}
        for permission in ['CAMERA','RECORD_AUDIO','ACCESS_COARSE_LOCATION']:
            self.assertIn('android.permission.'+permission,declared)
        self.assertNotIn('android.permission.ACCESS_FINE_LOCATION',declared)
        for feature in ['android.hardware.camera','android.hardware.camera.autofocus','android.hardware.microphone']:
            entries=[row for row in application.findall('uses-feature') if row.get(android+'name')==feature]
            self.assertEqual(len(entries),1)
            self.assertEqual(entries[0].get(android+'required'),'false')
        native = (PRODUCTION / 'GeckoSitePermissions.java').read_text()
        self.assertIn('getPermissions(scope.origin,scope.contextId,scope.privateMode)', native)
        self.assertIn('.withHandler(web.owner.handler)', native)
        for unwanted in ['getAllPermissions(', 'clearData(', 'fromJson(', 'setPrivateBrowsingPermanentPermission(', 'toJson(']:
            self.assertNotIn(unwanted, native)
        activity = (PRODUCTION / 'MainActivity.java').read_text()
        self.assertEqual(activity.count('option(d,"站点权限",()->SitePermissionsUi.show(this));'), 1)
        self.assertIn('web.identityPolicyRevision', native)
        self.assertIn('web.appearanceLoads.getOrDefault(session,0L)', native)
        self.assertIn('owner.lastDocumentId+"\\n"+web.locations.get(session)', native)
        for hook in ['private boolean reopenCurrent()', 'private void activate(GeckoSession session)']:
            body = browser[browser.index(hook):]
            self.assertIn('configure(desktop,owner.privacy.level())', body[:body.index('\n  }')])
        self.assertIn('long revision=++identityPolicyRevision', browser)
        self.assertIn('appearanceLoads.put(s,++appearanceLoadSerial)', browser)

    def test_chromium_permissions_execute_current_origin_and_android_grant_controls(self):
        java=os.environ.get('PROFILE_JAVA') or shutil.which('java')
        self.assertTrue(java,'JDK17+ required')
        before={name:hashlib.sha256((PRODUCTION/name).read_bytes()).hexdigest() for name in ['BrowserPermissions.java','BrowserAddressPolicy.java']}
        with tempfile.TemporaryDirectory(prefix='browser-permission-scope-') as temporary:
            report_path=Path(temporary)/'results.json'
            result=subprocess.run([os.environ.get('PYTHON','python3'),str(ROOT/'tests/browser-permissions-host/run.py'),
                '--java-home',str(Path(java).resolve().parent.parent),'--output',str(report_path)],cwd=ROOT,capture_output=True,text=True,timeout=45)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            report=json.loads(report_path.read_text())
            self.assertEqual(report['status'],'passed')
            self.assertGreaterEqual(report['passed'],43)
            self.assertEqual(report['passed'],report['total'])
            self.assertTrue(report['executionInputsUnchanged'])
            self.assertIs(report['actualAndroidExecution'],False)
            self.assertIs(report['actualWebViewExecution'],False)
            for name,sha in before.items():self.assertEqual(report['sourceFiles']['app/src/main/java/local/pocketchat/'+name],sha)
        self.assertEqual(before,{name:hashlib.sha256((PRODUCTION/name).read_bytes()).hexdigest() for name in before})


if __name__ == '__main__':
    unittest.main()
