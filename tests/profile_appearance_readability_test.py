"""Same production theme state machine under both JSON implementations in CI."""
import hashlib,json,os,shutil,subprocess,tempfile,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
JAVA=ROOT/'app/src/main/java/local/pocketchat'

def jars():
 explicit=os.environ.get('PROFILE_JSON_JAR')
 if explicit:return [(Path(explicit).stem,Path(explicit))]
 candidates=[('desktop',ROOT/'work/profile-host/json.jar'),('android',ROOT/'work/profile-host/android-json.jar')]
 if not any(p.is_file() for _,p in candidates):
  candidates=[('desktop',ROOT/'work/gecko-integration/catalog-json.jar'),('android',ROOT/'work/gecko-integration/sharing-android-json.jar')]
 if not any(p.is_file() for _,p in candidates):raise unittest.SkipTest('Pinned JSON jars unavailable')
 for _,p in candidates:
  if not p.is_file():raise AssertionError('Both pinned JSON runtimes required: '+str(p))
 return candidates

def run(jar,host_args=()):
 java=os.environ.get('PROFILE_JAVA') or shutil.which('java')
 if not java:raise unittest.SkipTest('Java runtime unavailable')
 if not jar.is_file():raise AssertionError('Pinned JSON jar unavailable: '+str(jar))
 with tempfile.TemporaryDirectory(prefix='appearance-readability-') as temp:
  files=[JAVA/'BrowserBridgeRequests.java',JAVA/'WebAppearanceSync.java',ROOT/'tests/web-appearance-host/WebAppearanceSyncHost.java',ROOT/'tests/web-appearance-host/WebAppearanceReadabilityHost.java']
  compile_run=subprocess.run([java,'-m','jdk.compiler/com.sun.tools.javac.Main','-encoding','UTF-8','-cp',str(jar),'-d',temp,*map(str,files)],capture_output=True,text=True)
  if compile_run.returncode:raise AssertionError(compile_run.stderr)
  result=subprocess.run([java,'-cp',temp+os.pathsep+str(jar),'local.pocketchat.WebAppearanceReadabilityHost',*host_args],capture_output=True,text=True)
  if result.returncode:raise AssertionError(result.stdout+result.stderr)
  return json.loads(result.stdout)

class AppearanceReadabilityTest(unittest.TestCase):
 def test_native_confirmation_includes_text_contrast(self):
  report={'actualAndroidExecution':False,'runtimes':{}}
  for label,jar in jars():
   with self.subTest(runtime=label):
    result=run(jar);self.assertEqual(result['passed'],16);self.assertTrue(all(r['passed'] for r in result['results']));report['runtimes'][label]=result
  output=Path(os.environ.get('APPEARANCE_READABILITY_REPORT',str(ROOT/'work/profile-host/appearance-readability-results.json')));output.parent.mkdir(parents=True,exist_ok=True)
  report['sourceSha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [JAVA/'WebAppearanceSync.java',ROOT/'tests/web-appearance-host/WebAppearanceReadabilityHost.java',Path(__file__)]}
  output.write_text(json.dumps(report,indent=2)+'\n')
 def test_reported_verified_flag_cannot_override_bad_contrast(self):
  for label,jar in jars():
   with self.subTest(runtime=label):self.assertEqual(run(jar,('observe',)),{'darkLowContrastConfirmed':False,'lightLowContrastConfirmed':False})

if __name__=='__main__':unittest.main()
