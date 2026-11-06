"""CPU-only raw source guard and retained CLI branch; no historical runtime view."""
import hashlib
import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
MODULE=ROOT/'tests/browser-profile-path-host/run.py'
spec=importlib.util.spec_from_file_location('cpu_profile_path_boundary',MODULE)
helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
OLD_CLI_SHA='c8f31abe9ff5b7330f7f683e3663c29c8e401289dedd08a1edf8483381f1e21a'

class ProfilePathBoundaryTests(unittest.TestCase):
 def test_exact_current_raw_sources_and_unknown_inputs(self):
  prod=ROOT/'app/src/main/java/local/pocketchat'
  self.assertEqual(len(helper.PINS),10)
  self.assertTrue(all('Tls'not in name for name in helper.PINS))
  for name in helper.PINS:
   raw=(prod/(name+'.java')).read_bytes()
   self.assertIs(helper.verify_factored_raw(name,raw),raw)
   for bad in (raw+b'\n',raw[:-1],raw.decode()):
    with self.subTest(name=name,kind=type(bad).__name__),self.assertRaises(ValueError):helper.verify_factored_raw(name,bad)
  with self.assertRaises(ValueError):helper.verify_factored_raw('Unknown',b'')
  with self.assertRaises(ValueError):helper.verify_factored_raw(None,b'')

 def test_original_cli_whole_bytes_recovered_by_only_declared_adapter(self):
  text=(ROOT/'tests/browser-runtime/BrowserRuntimePolicyTest.java').read_text()
  begin='  static String persistentProfileLayout(Path root)throws Exception{'
  end='  public static void main(String[] args)throws Exception{'
  self.assertEqual(text.count(begin),1);self.assertEqual(text.count(end),1)
  text=text[:text.index(begin)]+text[text.index(end):]
  start='      String layout=persistentProfileLayout(Path.of(args[0]));'
  finish='      check("Gecko wrapper cannot allocate or forward to a system WebView",'
  self.assertEqual(text.count(start),1);self.assertEqual(text.count(finish),1)
  original='      check("Gecko retains the existing persistent environment profile directory",view.contains("getNoBackupFilesDir(),\\"gecko-browser\\"")&&view.contains("\\"-profile\\",directory.getAbsolutePath()"));'
  branch=text[text.index(start):text.index(finish)]
  self.assertEqual(branch.count(original),1)
  self.assertIn('if("legacy".equals(layout))',branch)
  self.assertIn('"factored".equals(layout)',branch)
  restored=text[:text.index(start)]+original+'\n'+text[text.index(finish):]
  self.assertEqual(hashlib.sha256(restored.encode()).hexdigest(),OLD_CLI_SHA)

 def test_current_member_inputs_and_named_runtime_boundaries(self):
  view=(ROOT/'app/src/main/java/local/pocketchat/GeckoWebView.java').read_text()
  active=helper.uncomment(helper.member(view,'void initialize()'))
  self.assertEqual(active.count('File directory=cpuBoot.profile,config=cpuBoot.config;'),1)
  self.assertEqual(active.count('runtime=GeckoRuntime.create('),1)
  self.assertEqual(active.count('"-profile",directory.getAbsolutePath()'),1)
  host=(ROOT/'tests/browser-profile-path-host/Host.java.in').read_text()
  self.assertNotIn('GeckoTls',host)
  self.assertIn('GeckoRuntime.received==view.runtime.settings',host)
  self.assertIn('Files.exists(profile.resolve("cookies.sqlite"))',host)

if __name__=='__main__':unittest.main()
