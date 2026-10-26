"""Run new production JS regressions through the existing CI discovery step."""
import os
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]

class AppearanceCompatibilityTest(unittest.TestCase):
 def check_script(self,path):
  node=shutil.which('node')
  if not node:raise unittest.SkipTest('Node runtime unavailable')
  if not os.environ.get('JSDOM_MODULE'):raise unittest.SkipTest('Pinned JSDOM module unavailable')
  result=subprocess.run([node,'--test','--test-reporter=tap',str(ROOT/path)],cwd=ROOT,capture_output=True,text=True)
  out=ROOT/'work/profile-host';out.mkdir(parents=True,exist_ok=True)
  (out/(Path(path).stem+'.log')).write_text(result.stdout+result.stderr)
  self.assertEqual(result.returncode,0,result.stdout+result.stderr)
 def test_author_palette_and_visibility(self):self.check_script('tests/appearance_compatibility_test.cjs')
 def test_inserted_subtree_cache_ownership(self):self.check_script('tests/browser-runtime/inserted-subtree-invalidation.test.cjs')

if __name__=='__main__':unittest.main()
