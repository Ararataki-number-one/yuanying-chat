"""Finite, explicit46 -> formal45 whole-source port and counterfeit controls.

These checks preserve historical oracle inputs; they are not runtime acceptance.
"""
import ast,hashlib,json,os
from pathlib import Path
import subprocess,tempfile,unittest
from unittest.mock import patch
import experience46_source_compatibility as compat
ROOT=Path(__file__).resolve().parents[1]
sha=lambda raw:hashlib.sha256(raw).hexdigest()
class Experience46SourceCompatibility(unittest.TestCase):
 rejected=0
 def test_formal45_identity_exact_forward_and_full_inverse(self):
  manifest=compat.manifest46()
  self.assertEqual(subprocess.check_output(['git','rev-parse',compat.BASE_COMMIT+'^{tree}'],cwd=ROOT).decode().strip(),compat.BASE_TREE)
  old45=json.loads((ROOT/'tests/fixtures/reading45-restoration-source-deltas.json').read_bytes())
  for path,row in manifest['files'].items():
   with self.subTest(path=path):
    previous=subprocess.check_output(['git','show',compat.BASE_COMMIT+':'+path],cwd=ROOT);current=(ROOT/path).read_bytes()
    self.assertEqual(sha(previous),row['previousSha256']);self.assertEqual(sha(current),row['reviewedSha256'])
    self.assertEqual(compat.experience46_source_bytes(previous,path),previous)
    self.assertEqual(compat.experience46_source_bytes(current,path),previous)
    allowed=[]
    if path in old45['files'] and old45['files'][path]['previousSha256']!=row['previousSha256']:allowed=[old45['files'][path]['previousSha256']]
    self.assertEqual(row['exactHistoricalSha256'],allowed)
    forward=previous
    for delta in row['deltas']:
     old,new=delta['previous'].encode(),delta['current'].encode();self.assertTrue(old and new);self.assertEqual(forward.count(old),1);forward=forward.replace(old,new,1)
    self.assertEqual(forward,current)
 def test_missing_duplicate_changed_relocated_and_unknown_whole_bytes_rejected(self):
  rejected=0
  for path,row in compat.manifest46()['files'].items():
   current=(ROOT/path).read_bytes()
   for delta in row['deltas']:
    chunk=delta['current'].encode()
    remaining=current.replace(chunk,b'',1);relocated=remaining+chunk
    if relocated==current:relocated=chunk+remaining
    self.assertNotEqual(relocated,current)
    for invalid in (remaining,current.replace(chunk,chunk*2,1),current.replace(chunk,chunk+b' ',1),relocated):
     with self.subTest(path=path,mutation=sha(invalid)),self.assertRaises(ValueError):compat.experience46_source_bytes(invalid,path)
     rejected+=1
   for invalid in (current+b' ',b'unknown source'):
    with self.assertRaises(ValueError):compat.experience46_source_bytes(invalid,path)
    rejected+=1
  self.assertGreaterEqual(rejected,200);type(self).rejected=rejected
 def test_altered_fixture_path_or_ancestor_cannot_be_whitelisted(self):
  relative='app/src/main/java/local/pocketchat/BrowserReading.java';raw=(ROOT/relative).read_bytes()
  with tempfile.TemporaryDirectory(prefix='experience46-fixture-negative-') as directory:
   fake=Path(directory)/'modified.json';fake.write_bytes(compat.DELTA_PATH.read_bytes()+b' ')
   with patch.object(compat,'DELTA_PATH',fake),self.assertRaises(ValueError):compat.experience46_source_bytes(raw,relative)
  with self.assertRaises(ValueError):compat.experience46_source_bytes(raw,'app/src/main/java/local/pocketchat/Unreviewed.java')
  before=subprocess.check_output(['git','show',compat.BASE_COMMIT+':'+relative],cwd=ROOT)
  with self.assertRaises(ValueError):compat.experience46_source_bytes(before+b' ',relative)
 def test_original45_fixture_goldens_and_behavior_hosts_remain(self):
  self.assertEqual(sha((ROOT/'tests/fixtures/reading45-restoration-source-deltas.json').read_bytes()),'8d9fd8380a5d6337860989ad8ce95b0529773cdfa433ef090b229a8beb423f3c')
  for relative in ['tests/profile_reading_restore_precision45_test.py','tests/profile_reading_zoom_trace_test.py']:
   self.assertEqual((ROOT/relative).read_bytes(),subprocess.check_output(['git','show',compat.BASE_COMMIT+':'+relative],cwd=ROOT))
  relative='tests/profile_reading_fit_completion_test.py';current=(ROOT/relative).read_bytes();previous=subprocess.check_output(['git','show',compat.BASE_COMMIT+':'+relative],cwd=ROOT)
  self.assertEqual(compat.experience46_source_bytes(current,relative),previous)
  for name in ['execute','test_measured_completion_and_failure_controls']:
   def body(raw):
    source=raw.decode();node=next(n for n in ast.walk(ast.parse(source)) if isinstance(n,ast.FunctionDef) and n.name==name);return ast.get_source_segment(source,node)
   self.assertEqual(body(current),body(previous))
   self.assertNotIn('experience46_source_bytes',body(current))
  for relative in ['tests/profile_environment_overview46_test.py','tests/profile_environment_overview46_native_compile_test.py','tests/profile_reading_restore_precision45_test.py']:
   tree=ast.parse((ROOT/relative).read_text());imports=[node for node in ast.walk(tree) if isinstance(node,(ast.Import,ast.ImportFrom))]
   self.assertFalse(any('experience46_source_compatibility' in ast.unparse(node) for node in imports),relative+' must observe actual source')
  native=(ROOT/'tests/native43_source_compatibility.py').read_text()
  for old in ['32e06089272bbbaf63ed94449ea208cd2feb930cc05a903ab3e83efb0f140546','07d027899ad2c4a48d3759fe19080d3aa72027aa75aac6147e470f310bb1a5be']:
   self.assertIn(old,native)
 @classmethod
 def tearDownClass(cls):
  output=os.environ.get('EXPERIENCE46_INVERSE_REPORT')
  if output:Path(output).write_text(json.dumps(dict(scope='Exact static source-input preservation only; no runtime acceptance.',baseCommit=compat.BASE_COMMIT,baseTree=compat.BASE_TREE,manifestSha256=compat.DELTA_SHA256,rejectedCounterfeits=cls.rejected,actualAndroidExecution=False,actualGeckoExecution=False),indent=2)+'\n')
if __name__=='__main__':unittest.main(verbosity=2)
