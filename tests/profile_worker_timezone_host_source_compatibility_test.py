"""Finite host-adapter historical inputs; never execution or native acceptance."""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import worker_timezone_host_source_compatibility as overlay
from cpu_source_compatibility import PATHS as cpu_paths, source_input as cpu_source_input
ROOT=Path(__file__).resolve().parents[1]
SHA=lambda raw:hashlib.sha256(raw).hexdigest()
HOOK="""    if (digest, len(raw)) not in ((row['previousSha256'], row['previousBytes']),
                                  (row['reviewedSha256'], row['reviewedBytes'])):
        from worker_timezone_host_source_compatibility import PATHS as host_paths, source_input as host_source_input
        if relative in host_paths:
            raw = host_source_input(raw, relative)
            digest = _sha(raw)
"""
IMPORT=b'        from worker_timezone_host_source_compatibility import PATHS as host_adapter_paths, source_input as host_adapter_source_input\n'
READ=b'current = host_adapter_source_input((ROOT / relative).read_bytes(), relative) if relative in host_adapter_paths else (ROOT / relative).read_bytes()'
def assertions(raw):
 return [ast.dump(n,include_attributes=False)for n in ast.walk(ast.parse(raw))if isinstance(n,ast.Assert)or isinstance(n,ast.Call)and isinstance(n.func,ast.Attribute)and n.func.attr.startswith('assert')]
class WorkerTimezoneHostSourceCompatibility(unittest.TestCase):
 rejected_sources=0;rejected_fixture_shapes=0
 def test_whole_forward_inverse_equals_actual_phase1_predecessor(self):
  self.assertEqual(subprocess.check_output(['git','rev-parse',overlay.BASE_COMMIT+'^{tree}'],cwd=ROOT,text=True).strip(),overlay.BASE_TREE)
  rows=overlay.manifest()['files'];self.assertEqual(len(rows),2);self.assertEqual(sum(len(row['deltas'])for row in rows.values()),5)
  for relative,row in rows.items():
   with self.subTest(path=relative):
    before=subprocess.check_output(['git','show',overlay.BASE_COMMIT+':'+relative],cwd=ROOT);after=(ROOT/relative).read_bytes();after=cpu_source_input(after,relative) if relative in cpu_paths else after
    self.assertEqual((SHA(before),len(before)),(row['previousSha256'],row['previousBytes']));self.assertEqual((SHA(after),len(after)),(row['reviewedSha256'],row['reviewedBytes']))
    self.assertEqual(overlay.source_input(before,relative),before);self.assertEqual(overlay.source_input(after,relative),before)
    forward=before
    for delta in row['deltas']:
     previous,current=delta['previous'].encode(),delta['current'].encode();self.assertEqual(forward.count(previous),1);forward=forward.replace(previous,current,1)
    self.assertEqual(forward,after)
 def test_unknown_missing_duplicate_changed_relocated_sources_still_fail(self):
  rejected=0
  for relative,row in overlay.manifest()['files'].items():
   current=(ROOT/relative).read_bytes();current=cpu_source_input(current,relative) if relative in cpu_paths else current
   for delta in row['deltas']:
    chunk=delta['current'].encode();self.assertEqual(current.count(chunk),1);remainder=current.replace(chunk,b'',1);moved=remainder+chunk
    if moved==current:moved=chunk+remainder
    for bad in (remainder,current.replace(chunk,chunk*2,1),current.replace(chunk,chunk+b' ',1),moved):
     with self.subTest(path=relative,delta=delta['id'],mutation=SHA(bad)),self.assertRaises(ValueError):overlay.source_input(bad,relative)
     rejected+=1
   for bad in (current[:80],current+b' ',b'unknown source'):
    with self.assertRaises(ValueError):overlay.source_input(bad,relative)
    rejected+=1
  self.assertEqual(rejected,26);type(self).rejected_sources=rejected
 def test_path_type_source_pin_precedes_all_context_access(self):
  relative='tests/profile_page_bridge_lifecycle_test.py';current=(ROOT/relative).read_bytes();current=cpu_source_input(current,relative) if relative in cpu_paths else current
  for bad in (current.decode(),bytearray(current),memoryview(current),None):
   with self.assertRaises(ValueError):overlay.source_input(bad,relative)
  for path in (relative+'.other','../'+relative,'/'+relative,Path(relative),None,'app/src/main/java/local/pocketchat/GeckoWebView.java'):
   with self.assertRaises(ValueError):overlay.source_input(current,path)
  class Forbidden:
   def encode(self,*args):raise AssertionError('Unknown bytes reached context inversion')
  manifest=copy.deepcopy(overlay.manifest());manifest['files'][relative]['deltas'][0]['current']=Forbidden()
  with patch.object(overlay,'manifest',return_value=manifest),self.assertRaisesRegex(ValueError,'unknown whole source'):overlay.source_input(current+b' ',relative)
 def test_fixture_counterfeits_cannot_broaden_the_two_owned_host_paths(self):
  original=overlay.manifest();relative='tests/profile_page_bridge_lifecycle_test.py';variants=[]
  for key,value in [('schema',True),('kind','runtime-acceptance'),('baseCommit','a'*40),('baseTree','b'*40),('actualAndroidExecution',True),('runtimeAcceptance',True)]:
   v=copy.deepcopy(original);v[key]=value;variants.append(v)
  v=copy.deepcopy(original);v['files'].pop(relative);variants.append(v);v=copy.deepcopy(original);v['files']['unreviewed.py']=v['files'][relative];variants.append(v)
  for key,value in [('previousBytes',True),('reviewedBytes',0),('reviewedBytes',32769),('reviewedSha256','not-a-source-pin'),('contextLines',2),('contextLines',17),('deltas',[]),('deltas',[copy.deepcopy(original['files'][relative]['deltas'][0])]*9)]:
   v=copy.deepcopy(original);v['files'][relative][key]=value;variants.append(v)
  v=copy.deepcopy(original);v['files'][relative]['reviewedSha256']=v['files'][relative]['previousSha256'];variants.append(v)
  for key,value in [('id','context-99'),('currentSha256','0'*64),('previous',''),('current','x'*16385)]:
   v=copy.deepcopy(original);v['files'][relative]['deltas'][0][key]=value;variants.append(v)
  with tempfile.TemporaryDirectory(prefix='host-source-fixture-negative-')as directory:
   p=Path(directory)/'unreviewed.json';p.write_bytes(overlay.DELTA_PATH.read_bytes()+b' ')
   with patch.object(overlay,'DELTA_PATH',p),self.assertRaises(ValueError):overlay.manifest()
   for value in [[],True,*variants]:
    raw=(json.dumps(value,ensure_ascii=False)+'\n').encode();p.write_bytes(raw)
    with patch.object(overlay,'DELTA_PATH',p),patch.object(overlay,'DELTA_SHA256',SHA(raw)),self.assertRaises(ValueError):overlay.manifest()
   p.write_bytes(b' '*(overlay.MAX_FIXTURE_BYTES+1))
   with patch.object(overlay,'DELTA_PATH',p),self.assertRaises(ValueError):overlay.manifest()
  self.assertEqual(len(variants)+2,23);type(self).rejected_fixture_shapes=len(variants)+2
 def test_only_exact_read_hooks_change_old_inputs_and_all_old_assertions_remain(self):
  relative='tests/gecko_policy_dependency_source_compatibility.py';current=(ROOT/relative).read_bytes();current=cpu_source_input(current,relative) if relative in cpu_paths else current;before=subprocess.check_output(['git','show',overlay.BASE_COMMIT+':'+relative],cwd=ROOT)
  self.assertEqual(current.count(HOOK.encode()),1);self.assertEqual(current.replace(HOOK.encode(),b'',1),before)
  relative='tests/profile_dual_browser_source_compatibility_test.py';current=(ROOT/relative).read_bytes();current=cpu_source_input(current,relative) if relative in cpu_paths else current;before=subprocess.check_output(['git','show',overlay.BASE_COMMIT+':'+relative],cwd=ROOT)
  self.assertEqual(assertions(current),assertions(before));self.assertEqual(current.count(IMPORT),1);self.assertEqual(current.count(READ),2)
  self.assertEqual(current.replace(IMPORT,b'',1).replace(READ,b'current = (ROOT / relative).read_bytes()'),before)
  for relative in overlay.PATHS:
   before=subprocess.check_output(['git','show',overlay.BASE_COMMIT+':'+relative],cwd=ROOT);current=(ROOT/relative).read_bytes();current=cpu_source_input(current,relative) if relative in cpu_paths else current;now=ast.parse(current)
   for old in (n for n in ast.walk(ast.parse(before))if isinstance(n,ast.FunctionDef)and n.name.startswith('test_')):
    found=[n for n in ast.walk(now)if isinstance(n,ast.FunctionDef)and n.name==old.name];self.assertEqual(len(found),1);self.assertEqual(ast.get_source_segment(current.decode(),found[0]),ast.get_source_segment(before.decode(),old))
  for relative,pin in [('tests/fixtures/dual-browser-source-deltas.json','b593b0db2b56b5a5d8143a920fbd15858dafbab21d1cdaf90ca2a5ba164c9933'),('tests/fixtures/gecko-policy-dependency-source-deltas.json','8cb13b6e7ca1ddcb9bd129f0bcd74707f36d9efb03db4f973f3e9dca3c6b8f2a')]:self.assertEqual(SHA((ROOT/relative).read_bytes()),pin)
 def test_runtime_hosts_never_import_the_overlay(self):
  allowed={'tests/worker_timezone_host_source_compatibility.py','tests/gecko_policy_dependency_source_compatibility.py','tests/profile_dual_browser_source_compatibility_test.py','tests/profile_worker_timezone_host_source_compatibility_test.py'}
  for folder in ('tests','tools'):
   for path in (ROOT/folder).rglob('*.py'):
    raw=path.read_text()
    if 'worker_timezone_host_source_compatibility'not in raw:continue
    imported=any(isinstance(n,ast.ImportFrom)and n.module=='worker_timezone_host_source_compatibility'or isinstance(n,ast.Import)and any(a.name=='worker_timezone_host_source_compatibility'for a in n.names)for n in ast.walk(ast.parse(raw)))
    if imported:self.assertIn(path.relative_to(ROOT).as_posix(),allowed)
  for relative in overlay.PATHS:
   raw=(ROOT/relative).read_text();self.assertNotIn('worker_timezone_host_source_compatibility',raw);self.assertNotIn('worker_timezone_source_compatibility',raw)
  for relative in ('tests/request-identity-timezone-host/run.py','tests/gecko-timezone-http-host/run.py','tests/gecko-timezone-routing-host/run.py'):
   self.assertNotIn('worker_timezone_host_source_compatibility',(ROOT/relative).read_text())
  self.assertFalse(overlay.manifest()['actualAndroidExecution']);self.assertFalse(overlay.manifest()['runtimeAcceptance'])
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(WorkerTimezoneHostSourceCompatibility));report=dict(schema=1,status='passed'if result.wasSuccessful()else'failed',tests=result.testsRun,baseCommit=overlay.BASE_COMMIT,baseTree=overlay.BASE_TREE,fixtureSha256=overlay.DELTA_SHA256,rows=2,contexts=5,rejectedSourceMutants=WorkerTimezoneHostSourceCompatibility.rejected_sources,rejectedFixtureCounterfeits=WorkerTimezoneHostSourceCompatibility.rejected_fixture_shapes,actualAndroidExecution=False,runtimeAcceptance=False,scope='Exact historical inputs only. Actual current behavior tests and their added assertions still run current source; no runtime source projection.')
 output=os.environ.get('WORKER_TIMEZONE_HOST_SOURCE_REPORT')
 if output:p=Path(output);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(report,indent=2)+'\n')
 raise SystemExit(0 if result.wasSuccessful()else 1)
