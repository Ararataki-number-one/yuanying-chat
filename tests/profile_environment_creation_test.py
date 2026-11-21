"""Focused environment reservation and copy cases on controlled Java storage adapters."""
import hashlib
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PROD = ROOT / 'app/src/main/java/local/pocketchat'
FIXTURE = ROOT / 'tests/environment-creation-host'
DEFAULT_HOST = ROOT / 'tests/default-environment-host'
PINS = {'json.jar': '3ea61b2a06e31edf1c91134fe9106b0ebb16628be169f3db75bc7a2b06b45796',
        'android-json.jar': 'dfb7bae2f404cfe0b72b4d23944698cb716b7665171812a0a4d0f5926c0fac79'}


class EnvironmentCreationTest(unittest.TestCase):
    def test_reservation_copy_and_retry_on_synthetic_storage(self):
        java = os.environ.get('PROFILE_JAVA') or shutil.which('java')
        self.assertTrue(java, 'JDK17+ required')
        member = runpy.run_path(str(DEFAULT_HOST / 'run.py'))['member']
        selections = {
            'CATALOG': ('ProfileCatalog.java', (
                'JSONObject item(', 'static JSONObject row(', 'EnvironmentSpec.Identity identity(',
                'void browserDisplay(', 'boolean details(', 'boolean favorite(', 'interface IdentityAction<T>',
                '<T>T withIdentity(', '<T>T createNew(int slot,IdentityAction',
                '<T>T createNew(int slot,int generation,', 'void writeNewPresentation(')),
            'PROFILES': ('Profiles.java', (
                'static void prepare(Context c,int target,boolean copyNetwork)', 'static EnvironmentSpec.Identity create(',
                'private static <T>T prepare(', 'static void clearConfiguration(', 'static final class NetworkCopy',
                'static final class ConfigurationCopy', 'static EnvironmentSpec.Identity copyConfiguration(Context source,int target)throws',
                'static EnvironmentSpec.Identity copyConfiguration(Context source,int target,EnvironmentSpec.Identity',
                'static EnvironmentSpec.Identity copyConfiguration(Context source,int target,int generation,',
                'static EnvironmentSpec.Identity copyConfigurationWithEngine(',
                'static final class FileCheck')),
            'SPEC': ('EnvironmentSpec.java', ('static final class Identity', 'static void requireRevision(')),
            'BROWSER': ('BrowserPreferences.java', ('private static SharedPreferences preferences(',
                'static EnvironmentEngine engine(', 'static boolean startBrowser(', 'static String home(', 'static String normalizeHome(')),
            'PREFS': ('AppPrefs.java', ('static boolean enabled(', 'static JSONObject values(')),
            'DEFAULT': ('AppSettings.java', ('static boolean writeDefault(', 'static boolean defaultSlot(Context c,int id)',
                                             'static boolean eligibleDefault(', 'static boolean selectable(')),
            'MENU': ('WindowHomeActivity.java', ('void saveMenuChoice(',)),
        }
        text = (FIXTURE / 'CreationHost.java.in').read_text()
        for marker, (name, members) in selections.items():
            source = (PROD / name).read_text()
            data = '\n'.join(member(source, needle) for needle in members)
            if marker == 'DEFAULT' and 'boolean writeSetting(' in source:
                data += '\n' + member(source, 'static boolean writeSetting(')
            prefixes = {'BROWSER': ('static final String DEFAULT_URL=', 'static final String START_CHAT=', 'static final String KEY_START='),
                        'PREFS': ('static final String[] KEYS=',)}
            constants = '\n'.join(line.strip() for line in source.splitlines()
                                  if line.strip().startswith(prefixes.get(marker, ())))
            text = text.replace('/* ' + marker + ' */', constants + '\n' + data)
        zoom = next(line for line in (PROD / 'BrowserReadingPolicy.java').read_text().splitlines()
                    if line.strip().startswith('static final String ZOOM_KEY='))
        text = text.replace('/* ZOOM */', zoom)
        for jar_name, env in [('json.jar', 'PROFILE_JSON_JAR'), ('android-json.jar', 'PROFILE_ANDROID_JSON_JAR')]:
            with self.subTest(json=jar_name):
                jar = Path(os.environ.get(env, ROOT / 'work/profile-host' / jar_name)).resolve()
                self.assertEqual(hashlib.sha256(jar.read_bytes()).hexdigest(), PINS[jar_name])
                with tempfile.TemporaryDirectory(prefix='environment-creation-host-') as temp:
                    work = Path(temp)
                    fixture = work / 'CreationHost.java'
                    fixture.write_text(text, encoding='utf-8')
                    stubs = DEFAULT_HOST / 'stubs/android'
                    inputs = [fixture, FIXTURE / 'SharedPreferences.java', stubs / 'content/ContentValues.java',
                              stubs / 'database/Cursor.java', stubs / 'database/sqlite/SQLiteDatabase.java', stubs / 'os/Build.java',
                              *(PROD / name for name in ('J.java', 'BrowserAddressPolicy.java', 'EnvironmentBrowserData.java', 'EnvironmentEngine.java'))]
                    compile_result = subprocess.run([java, '-m', 'jdk.compiler/com.sun.tools.javac.Main', '--release', '17',
                        '-encoding', 'UTF-8', '-cp', str(jar), '-d', temp, *map(str, inputs)],
                        capture_output=True, text=True, timeout=30)
                    self.assertEqual(compile_result.returncode, 0, compile_result.stdout + compile_result.stderr)
                    run_result = subprocess.run([java, '-cp', temp + os.pathsep + str(jar),
                        'local.pocketchat.CreationHost', temp], capture_output=True, text=True, timeout=20)
                    self.assertEqual(run_result.returncode, 0, run_result.stdout + run_result.stderr)
                    self.assertEqual(run_result.stdout.strip(), 'passed=28')


if __name__ == '__main__':
    unittest.main()
