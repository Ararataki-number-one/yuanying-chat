"""Exact context-fix history input: no native/Android/runtime acceptance."""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
from ip_timezone_source_compatibility import historical_read
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import phase1_context_fix_source_compatibility as overlay
ROOT=Path(__file__).resolve().parents[1]
SHA=lambda raw:hashlib.sha256(raw).hexdigest()
HOOK="""    if (digest, len(raw)) not in ((row['previousSha256'], row['previousBytes']),
                                  (row['reviewedSha256'], row['reviewedBytes'])):
        from phase1_context_fix_source_compatibility import PATHS as context_paths, source_input as context_source_input
        if relative in context_paths:
            raw = context_source_input(raw, relative)
            digest = _sha(raw)
"""
IMPORT=b'from phase1_context_fix_source_compatibility import PATHS as context_paths, source_input as context_source_input\n'
def read_hook(indent,name):return (' '*indent+'if relative in context_paths:\n'+' '*(indent+4)+name+' = context_source_input('+name+', relative)\n').encode()
def assertions(raw):return[ast.dump(n,include_attributes=False)for n in ast.walk(ast.parse(raw))if isinstance(n,ast.Assert)or isinstance(n,ast.Call)and isinstance(n.func,ast.Attribute)and n.func.attr.startswith('assert')]
class Phase1ContextFixSourceCompatibility(unittest.TestCase):
 source_negatives=0;guard_negatives=0;fixture_negatives=0
 def test_complete_before_after_forward_and_inverse_equal_actual_1a06(self):
  self.assertEqual(subprocess.check_output(['git','rev-parse',overlay.BASE_COMMIT+'^{tree}'],cwd=ROOT,text=True).strip(),overlay.BASE_TREE)
  rows=overlay.manifest()['files'];self.assertEqual(len(rows),1);self.assertEqual(sum(len(row['deltas'])for row in rows.values()),2)
  for path,row in rows.items():
   before=subprocess.check_output(['git','show',overlay.BASE_COMMIT+':'+path],cwd=ROOT);after=historical_read(path)
   self.assertEqual((SHA(before),len(before)),(row['previousSha256'],row['previousBytes']));self.assertEqual((SHA(after),len(after)),(row['reviewedSha256'],row['reviewedBytes']))
   self.assertEqual(overlay.source_input(before,path),before);self.assertEqual(overlay.source_input(after,path),before)
   forward=before
   for delta in row['deltas']:
    old,new=delta['previous'].encode(),delta['current'].encode();self.assertEqual((SHA(old),SHA(new)),(delta['previousSha256'],delta['currentSha256']));self.assertEqual(forward.count(old),1);forward=forward.replace(old,new,1)
   self.assertEqual(forward,after)
 def test_missing_duplicate_mutated_moved_truncated_and_unknown_whole_sources_reject(self):
  rejected=0
  for path,row in overlay.manifest()['files'].items():
   current=historical_read(path)
   for delta in row['deltas']:
    chunk=delta['current'].encode();self.assertEqual(current.count(chunk),1);remaining=current.replace(chunk,b'',1);moved=remaining+chunk
    if moved==current:moved=chunk+remaining
    for value in (remaining,current.replace(chunk,chunk*2,1),current.replace(chunk,chunk+b' ',1),moved):
     with self.subTest(path=path,context=delta['id'],mutation=SHA(value)),self.assertRaises(ValueError):overlay.source_input(value,path)
     rejected+=1
   for value in (current[:100],current+b' ',b'unknown full source'):
    with self.assertRaises(ValueError):overlay.source_input(value,path)
    rejected+=1
  self.assertEqual(rejected,11);type(self).source_negatives=rejected
 def test_document_native_ownership_pending_and_remaining_budget_guards_cannot_normalize_away(self):
  path='app/src/main/java/local/pocketchat/GeckoWebView.java';current=historical_read(path)
  variants=(
   ('!addonDisabled&&fence.session==current','fence.session==current'),
   ('fence.document==fence.open.documentSerial','true'),
   ('fence.page!=null&&fence.page==ports.get(current)','true'),
   ('!staleAppearanceConnections.contains(fence.page)','true'),
   ('fence.desired==owner.timeZone.status().optLong("desiredRevision",-1)','true'),
   ('ready&&environmentAuditDocumentCurrent(fence)','ready'),
   ('if(configuration==null){callback.onReceiveValue("null");return;}',''),
   ('((Number)value).longValue()>14000','((Number)value).longValue()>20000'),
   ('value instanceof Integer||value instanceof Long','value instanceof Integer||value instanceof Long||value instanceof Double'),
   ('callbacks.add(port,callback::onReceiveValue,budget)','callbacks.add(port,callback::onReceiveValue,14000)'),
  )
  for before,after in variants:
   with self.subTest(guard=before):
    self.assertEqual(current.count(before.encode()),1)
    with self.assertRaises(ValueError):overlay.source_input(current.replace(before.encode(),after.encode(),1),path)
  self.assertEqual(len(variants),10);type(self).guard_negatives=len(variants)
 def test_type_path_and_whole_source_identity_precedes_context_access(self):
  path='app/src/main/java/local/pocketchat/GeckoWebView.java';current=historical_read(path)
  for bad in (current.decode(),bytearray(current),memoryview(current),None):
   with self.assertRaises(ValueError):overlay.source_input(bad,path)
  for name in ('../'+path,'/'+path,path+'.other',Path(path),None,'app/src/main/java/local/pocketchat/EnvironmentAudit.java','app/src/main/java/local/pocketchat/GeckoTimeZoneController.java'):
   with self.assertRaises(ValueError):overlay.source_input(current,name)
  class Forbidden:
   def encode(self,*args):raise AssertionError('Unknown source reached contextual inversion')
  manifest=copy.deepcopy(overlay.manifest());manifest['files'][path]['deltas'][0]['current']=Forbidden()
  with patch.object(overlay,'manifest',return_value=manifest),self.assertRaisesRegex(ValueError,'unknown whole source'):overlay.source_input(current+b' ',path)
 def test_fixture_pin_identity_shape_and_bounds_remain_independently_strict(self):
  original=overlay.manifest();path='app/src/main/java/local/pocketchat/GeckoWebView.java';variants=[]
  for key,value in [('schema',True),('kind','runtime-acceptance'),('baseCommit','a'*40),('baseTree','b'*40),('actualAndroidExecution',True),('runtimeAcceptance',True)]:
   v=copy.deepcopy(original);v[key]=value;variants.append(v)
  v=copy.deepcopy(original);v['files'].pop(path);variants.append(v);v=copy.deepcopy(original);v['files']['unreviewed.java']=v['files'][path];variants.append(v)
  for key,value in [('previousBytes',True),('reviewedBytes',0),('reviewedBytes',131073),('reviewedSha256','not-a-source-pin'),('contextLines',2),('contextLines',17),('deltas',[]),('deltas',[copy.deepcopy(original['files'][path]['deltas'][0])]*9)]:
   v=copy.deepcopy(original);v['files'][path][key]=value;variants.append(v)
  v=copy.deepcopy(original);v['files'][path]['reviewedSha256']=v['files'][path]['previousSha256'];variants.append(v)
  for key,value in [('id','context-99'),('currentSha256','0'*64),('previous',''),('current','x'*16385)]:
   v=copy.deepcopy(original);v['files'][path]['deltas'][0][key]=value;variants.append(v)
  v=copy.deepcopy(original);v['unknownField']=True;variants.append(v)
  with tempfile.TemporaryDirectory(prefix='phase1-context-fixture-negative-')as directory:
   target=Path(directory)/'unreviewed.json';target.write_bytes(overlay.DELTA_PATH.read_bytes()+b' ')
   with patch.object(overlay,'DELTA_PATH',target),self.assertRaises(ValueError):overlay.manifest()
   for value in [[],True,*variants]:
    raw=(json.dumps(value,ensure_ascii=False)+'\n').encode();target.write_bytes(raw)
    with patch.object(overlay,'DELTA_PATH',target),patch.object(overlay,'DELTA_SHA256',SHA(raw)),self.assertRaises(ValueError):overlay.manifest()
   target.write_bytes(b' '*(overlay.MAX_FIXTURE_BYTES+1))
   with patch.object(overlay,'DELTA_PATH',target),self.assertRaises(ValueError):overlay.manifest()
  self.assertEqual(len(variants)+2,24);type(self).fixture_negatives=len(variants)+2
 def test_precise_input_ports_strip_to_entire_real_1a06_and_all_original_assertions(self):
  path='tests/worker_timezone_source_compatibility.py';before=subprocess.check_output(['git','show',overlay.BASE_COMMIT+':'+path],cwd=ROOT);current=historical_read(path)
  self.assertEqual(current.count(HOOK.encode()),1);self.assertEqual(current.replace(HOOK.encode(),b'',1),before)
  from page_bridge_budget_source_compatibility import source_input as budget_source_input
  path='tests/profile_worker_timezone_source_compatibility_test.py';before=subprocess.check_output(['git','show',overlay.BASE_COMMIT+':'+path],cwd=ROOT);current=budget_source_input(historical_read(path),path)
  self.assertEqual(assertions(current),assertions(before));self.assertEqual(current.count(IMPORT),1);current=current.replace(IMPORT,b'',1)
  for indent,name in ((16,'after'),(12,'after'),(8,'after'),(12,'current'),(8,'current')):
   hook=read_hook(indent,name);self.assertEqual(current.count(hook),1);current=current.replace(hook,b'',1)
  self.assertEqual(current,before)
  for path,pin in [('tests/fixtures/dual-browser-source-deltas.json','b593b0db2b56b5a5d8143a920fbd15858dafbab21d1cdaf90ca2a5ba164c9933'),('tests/fixtures/worker-timezone-source-deltas.json','4eafec08cbeb3beb9098ebf5df7b976423616bb213e47e802a1d39315a27602b'),('tests/fixtures/worker-timezone-host-adapter-source-deltas.json','8c3f0c4d629d3d1a584ef3347f511b26081a59d35ba4d8621838db1f4735fbed'),('tests/fixtures/connection-timezone-prerequisite-source-deltas.json','cf99d65553fa119fe6154f591487b103a1b805646220490c6992f19ba073b0b8')]:
   self.assertEqual(SHA((ROOT/path).read_bytes()),pin);self.assertEqual((ROOT/path).read_bytes(),subprocess.check_output(['git','show',overlay.BASE_COMMIT+':'+path],cwd=ROOT))
 def test_only_reviewed_historical_ports_import_context_source_view(self):
  allowed={'tests/worker_timezone_source_compatibility.py','tests/profile_worker_timezone_source_compatibility_test.py','tests/profile_phase1_context_fix_source_compatibility_test.py'}
  for folder in ('tests','tools'):
   for path in (ROOT/folder).rglob('*.py'):
    raw=path.read_text()
    if 'phase1_context_fix_source_compatibility'not in raw:continue
    imported=any(isinstance(n,ast.ImportFrom)and n.module=='phase1_context_fix_source_compatibility'or isinstance(n,ast.Import)and any(a.name=='phase1_context_fix_source_compatibility'for a in n.names)for n in ast.walk(ast.parse(raw)))
    if imported:self.assertIn(path.relative_to(ROOT).as_posix(),allowed)
  for path in ('tests/gecko-timezone-flow-host/run.py','tests/gecko-timezone-routing-host/run.py','tests/gecko-timezone-http-host/run.py','tests/gecko-timezone-stale-host/run.py','tests/environment-audit-pending-host/run.py','tests/request-identity-timezone-host/run.py','tests/profile_native_protection_test.py','tests/connection_route_timezone_prerequisite_test.py'):
   self.assertNotIn('phase1_context_fix_source_compatibility',(ROOT/path).read_text())
  self.assertFalse(overlay.manifest()['runtimeAcceptance']);self.assertFalse(overlay.manifest()['actualAndroidExecution'])
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Phase1ContextFixSourceCompatibility));report=dict(schema=1,status='passed'if result.wasSuccessful()else'failed',tests=result.testsRun,baseCommit=overlay.BASE_COMMIT,baseTree=overlay.BASE_TREE,fixtureSha256=overlay.DELTA_SHA256,rows=1,contexts=2,rejectedSourceMutants=Phase1ContextFixSourceCompatibility.source_negatives,rejectedProtectedGuardMutants=Phase1ContextFixSourceCompatibility.guard_negatives,rejectedFixtureCounterfeits=Phase1ContextFixSourceCompatibility.fixture_negatives,actualAndroidExecution=False,runtimeAcceptance=False,scope='Exact whole historical source inputs only; actual behavior hosts continue raw current production.')
 output=os.environ.get('PHASE1_CONTEXT_SOURCE_REPORT')
 if output:p=Path(output);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(report,indent=2)+'\n')
 raise SystemExit(0 if result.wasSuccessful()else 1)
