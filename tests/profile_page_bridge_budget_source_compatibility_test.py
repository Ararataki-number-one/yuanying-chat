"""Exact PageBridge historical inputs; current runtime always remains raw."""
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
import page_bridge_budget_source_compatibility as overlay
ROOT=Path(__file__).resolve().parents[1]
SHA=lambda raw:hashlib.sha256(raw).hexdigest()
HOOK="""    if (digest, len(raw)) not in ((row['previousSha256'], row['previousBytes']),
                                  (row['reviewedSha256'], row['reviewedBytes'])):
        from page_bridge_budget_source_compatibility import PATHS as budget_paths, source_input as budget_source_input
        if relative in budget_paths:
            raw = budget_source_input(raw, relative)
            digest = _sha(raw)
"""
IMPORT=b'from page_bridge_budget_source_compatibility import PATHS as budget_paths, source_input as budget_source_input\n'
READ=b'(budget_source_input((ROOT/relative).read_bytes(),relative) if relative in budget_paths else (ROOT/relative).read_bytes())'
def assertions(raw):return[ast.dump(n,include_attributes=False)for n in ast.walk(ast.parse(raw))if isinstance(n,ast.Assert)or isinstance(n,ast.Call)and isinstance(n.func,ast.Attribute)and n.func.attr.startswith('assert')]
class PageBridgeBudgetSourceCompatibility(unittest.TestCase):
 source_negatives=0;guard_negatives=0;fixture_negatives=0
 def test_complete_source_forward_inverse_equals_real_802e(self):
  self.assertEqual(subprocess.check_output(['git','rev-parse',overlay.BASE_COMMIT+'^{tree}'],cwd=ROOT,text=True).strip(),overlay.BASE_TREE)
  rows=overlay.manifest()['files'];self.assertEqual(len(rows),3);self.assertEqual(sum(len(row['deltas'])for row in rows.values()),4)
  for relative,row in rows.items():
   before=subprocess.check_output(['git','show',overlay.BASE_COMMIT+':'+relative],cwd=ROOT);after=(ROOT/relative).read_bytes()
   self.assertEqual((SHA(before),len(before)),(row['previousSha256'],row['previousBytes']));self.assertEqual((SHA(after),len(after)),(row['reviewedSha256'],row['reviewedBytes']))
   self.assertEqual(overlay.source_input(before,relative),before);self.assertEqual(overlay.source_input(after,relative),before)
   forward=before
   for delta in row['deltas']:
    old,new=delta['previous'].encode(),delta['current'].encode();self.assertEqual((SHA(old),SHA(new)),(delta['previousSha256'],delta['currentSha256']));self.assertEqual(forward.count(old),1);forward=forward.replace(old,new,1)
   self.assertEqual(forward,after)
 def test_missing_duplicate_changed_relocated_unknown_source_bytes_reject(self):
  count=0
  for relative,row in overlay.manifest()['files'].items():
   after=(ROOT/relative).read_bytes()
   for delta in row['deltas']:
    current=delta['current'].encode();self.assertEqual(after.count(current),1);remaining=after.replace(current,b'',1);moved=remaining+current
    if moved==after:moved=current+remaining
    for value in (remaining,after.replace(current,current*2,1),after.replace(current,current+b' ',1),moved):
     with self.subTest(context=delta['id'],mutation=SHA(value)),self.assertRaises(ValueError):overlay.source_input(value,relative)
     count+=1
   for value in (after[:100],after+b' ',b'unknown source'):
    with self.assertRaises(ValueError):overlay.source_input(value,relative)
    count+=1
  self.assertEqual(count,25);type(self).source_negatives=count
 def test_actual_guard_binding_original_oracle_mutants_and_budget_cannot_be_erased(self):
  relative='tests/profile_page_bridge_lifecycle_test.py';current=(ROOT/relative).read_bytes()
  variants=(
   ('from page_bridge_guard_adapters import current_deltas\n',''),
   ("DELTAS = current_deltas((SOURCE / 'GeckoWebView.java').read_bytes(), DELTAS)", 'DELTAS = DELTAS'),
   ("ROOT / 'tests/page_bridge_guard_adapters.py', ",''),
   ("self.assertEqual(report['total'], 32)","self.assertEqual(report['total'], 31)"),
   ("self.assertEqual((old['passed'], old['total']), (21, 32))","self.assertEqual((old['passed'], old['total']), (32, 32))"),
   ("raw.replace(after, before, 1).decode()","raw.decode()"),
   ('capture_output=True, text=True, timeout=40)','capture_output=True, text=True, timeout=50)'),
  )
  for before,after in variants:
   with self.subTest(guard=before):
    self.assertEqual(current.count(before.encode()),1)
    with self.assertRaises(ValueError):overlay.source_input(current.replace(before.encode(),after.encode(),1),relative)
  count=len(variants)
  for relative in ('tests/profile_dual_browser_source_compatibility_test.py','tests/profile_worker_timezone_source_compatibility_test.py'):
   current=(ROOT/relative).read_bytes()
   for before,after in (('if relative in budget_paths else','if relative not in budget_paths else'),('budget_source_input((ROOT / relative).read_bytes(), relative)',"budget_source_input((ROOT / relative).read_bytes(), 'foreign.py')")):
    self.assertEqual(current.count(before.encode()),1)
    with self.assertRaises(ValueError):overlay.source_input(current.replace(before.encode(),after.encode(),1),relative)
    count+=1
  self.assertEqual(count,11);type(self).guard_negatives=count
 def test_source_type_path_and_whole_pin_precede_context_access(self):
  relative='tests/profile_page_bridge_lifecycle_test.py';current=(ROOT/relative).read_bytes()
  for bad in (current.decode(),bytearray(current),memoryview(current),None):
   with self.assertRaises(ValueError):overlay.source_input(bad,relative)
  for path in ('../'+relative,'/'+relative,relative+'.other',Path(relative),None,'tests/profile_native_protection_test.py','app/src/main/java/local/pocketchat/GeckoWebView.java'):
   with self.assertRaises(ValueError):overlay.source_input(current,path)
  class Forbidden:
   def encode(self,*args):raise AssertionError('Unknown source reached contextual inversion')
  value=copy.deepcopy(overlay.manifest());value['files'][relative]['deltas'][0]['current']=Forbidden()
  with patch.object(overlay,'manifest',return_value=value),self.assertRaisesRegex(ValueError,'unknown whole source'):overlay.source_input(current+b' ',relative)
 def test_fixture_pin_types_identity_and_finite_bounds_remain_strict(self):
  original=overlay.manifest();relative='tests/profile_page_bridge_lifecycle_test.py';variants=[]
  for key,value in [('schema',True),('kind','runtime-acceptance'),('baseCommit','a'*40),('baseTree','b'*40),('actualAndroidExecution',True),('runtimeAcceptance',True)]:
   v=copy.deepcopy(original);v[key]=value;variants.append(v)
  v=copy.deepcopy(original);v['files'].pop(relative);variants.append(v);v=copy.deepcopy(original);v['files']['unreviewed.py']=v['files'][relative];variants.append(v)
  for key,value in [('previousBytes',True),('reviewedBytes',0),('reviewedBytes',32769),('reviewedSha256','not-a-source-pin'),('contextLines',2),('contextLines',17),('deltas',[]),('deltas',[copy.deepcopy(original['files'][relative]['deltas'][0])]*9)]:
   v=copy.deepcopy(original);v['files'][relative][key]=value;variants.append(v)
  v=copy.deepcopy(original);v['files'][relative]['reviewedSha256']=v['files'][relative]['previousSha256'];variants.append(v)
  for key,value in [('id','context-99'),('currentSha256','0'*64),('previous',''),('current','x'*16385)]:
   v=copy.deepcopy(original);v['files'][relative]['deltas'][0][key]=value;variants.append(v)
  v=copy.deepcopy(original);v['extraField']=True;variants.append(v)
  with tempfile.TemporaryDirectory(prefix='page-bridge-source-negative-')as directory:
   p=Path(directory)/'unknown.json';p.write_bytes(overlay.DELTA_PATH.read_bytes()+b' ')
   with patch.object(overlay,'DELTA_PATH',p),self.assertRaises(ValueError):overlay.manifest()
   for value in [[],True,*variants]:
    raw=(json.dumps(value,ensure_ascii=False)+'\n').encode();p.write_bytes(raw)
    with patch.object(overlay,'DELTA_PATH',p),patch.object(overlay,'DELTA_SHA256',SHA(raw)),self.assertRaises(ValueError):overlay.manifest()
   p.write_bytes(b' '*(overlay.MAX_FIXTURE_BYTES+1))
   with patch.object(overlay,'DELTA_PATH',p),self.assertRaises(ValueError):overlay.manifest()
  self.assertEqual(len(variants)+2,24);type(self).fixture_negatives=len(variants)+2
 def test_only_exact_historical_hooks_strip_whole_files_and_original_assertions(self):
  relative='tests/worker_timezone_host_source_compatibility.py';before=subprocess.check_output(['git','show',overlay.BASE_COMMIT+':'+relative],cwd=ROOT);current=(ROOT/relative).read_bytes()
  self.assertEqual(current.count(HOOK.encode()),1);self.assertEqual(current.replace(HOOK.encode(),b'',1),before)
  relative='tests/profile_worker_timezone_host_source_compatibility_test.py';before=subprocess.check_output(['git','show',overlay.BASE_COMMIT+':'+relative],cwd=ROOT);current=(ROOT/relative).read_bytes()
  self.assertEqual(assertions(current),assertions(before));self.assertEqual(current.count(IMPORT),1);self.assertEqual(current.count(READ),6)
  self.assertEqual(current.replace(IMPORT,b'',1).replace(READ,b'(ROOT/relative).read_bytes()'),before)
  ports=(
   ('tests/profile_dual_browser_source_compatibility_test.py',b'        from page_bridge_budget_source_compatibility import PATHS as budget_paths, source_input as budget_source_input\n',b'            current = budget_source_input((ROOT / relative).read_bytes(), relative) if relative in budget_paths else (ROOT / relative).read_bytes()',b'            current = (ROOT / relative).read_bytes()'),
   ('tests/profile_worker_timezone_source_compatibility_test.py',b'        from page_bridge_budget_source_compatibility import PATHS as budget_paths, source_input as budget_source_input\n',b'        after = budget_source_input((ROOT / relative).read_bytes(), relative) if relative in budget_paths else (ROOT / relative).read_bytes()',b'        after = (ROOT / relative).read_bytes()'),
   ('tests/profile_phase1_context_fix_source_compatibility_test.py',b'  from page_bridge_budget_source_compatibility import source_input as budget_source_input\n',b'current=budget_source_input((ROOT/path).read_bytes(),path)',b'current=(ROOT/path).read_bytes()'),
  )
  for relative,import_line,new_read,old_read in ports:
   before=subprocess.check_output(['git','show',overlay.BASE_COMMIT+':'+relative],cwd=ROOT);current=(ROOT/relative).read_bytes()
   self.assertEqual(assertions(current),assertions(before));self.assertEqual(current.count(import_line),1);self.assertEqual(current.count(new_read),1)
   stripped=current.replace(import_line,b'',1).replace(new_read,old_read,1);self.assertEqual(stripped,before)
   # Changed, missing, duplicate and partial read ports cannot satisfy the
   # same complete-file mechanical proof, even if a local fragment survives.
   for bad in (current.replace(new_read,old_read,1),current.replace(new_read,new_read*2,1),current.replace(new_read,new_read+b' ',1),current[:100]):
    self.assertTrue(bad.count(import_line)!=1 or bad.count(new_read)!=1 or bad.replace(import_line,b'',1).replace(new_read,old_read,1)!=before)
  relative='tests/profile_page_bridge_lifecycle_test.py';before=subprocess.check_output(['git','show',overlay.BASE_COMMIT+':'+relative],cwd=ROOT);current=(ROOT/relative).read_bytes();self.assertEqual(assertions(current),assertions(before));tree=ast.parse(current)
  for old in (n for n in ast.walk(ast.parse(before))if isinstance(n,ast.FunctionDef)and n.name.startswith('test_')):
   matching=[n for n in ast.walk(tree)if isinstance(n,ast.FunctionDef)and n.name==old.name];self.assertEqual(len(matching),1);self.assertEqual(ast.get_source_segment(current.decode(),matching[0]),ast.get_source_segment(before.decode(),old))
  for relative,pin in [('tests/fixtures/dual-browser-source-deltas.json','b593b0db2b56b5a5d8143a920fbd15858dafbab21d1cdaf90ca2a5ba164c9933'),('tests/fixtures/worker-timezone-source-deltas.json','4eafec08cbeb3beb9098ebf5df7b976423616bb213e47e802a1d39315a27602b'),('tests/fixtures/worker-timezone-host-adapter-source-deltas.json','8c3f0c4d629d3d1a584ef3347f511b26081a59d35ba4d8621838db1f4735fbed'),('tests/fixtures/connection-timezone-prerequisite-source-deltas.json','cf99d65553fa119fe6154f591487b103a1b805646220490c6992f19ba073b0b8'),('tests/fixtures/phase1-context-fix-source-deltas.json','6e9b6fb645c5b918c4b18d37fe69f1d3d9a586d6fa1db9b81d7b98c28d070ad4')]:
   self.assertEqual(SHA((ROOT/relative).read_bytes()),pin);self.assertEqual((ROOT/relative).read_bytes(),subprocess.check_output(['git','show',overlay.BASE_COMMIT+':'+relative],cwd=ROOT))
 def test_actual_runtime_never_imports_this_historical_view(self):
  allowed={'tests/worker_timezone_host_source_compatibility.py','tests/profile_worker_timezone_host_source_compatibility_test.py','tests/profile_page_bridge_budget_source_compatibility_test.py','tests/profile_dual_browser_source_compatibility_test.py','tests/profile_worker_timezone_source_compatibility_test.py','tests/profile_phase1_context_fix_source_compatibility_test.py'}
  for folder in ('tests','tools'):
   for path in (ROOT/folder).rglob('*.py'):
    raw=path.read_text()
    if 'page_bridge_budget_source_compatibility'not in raw:continue
    imported=any(isinstance(n,ast.ImportFrom)and n.module=='page_bridge_budget_source_compatibility'or isinstance(n,ast.Import)and any(a.name=='page_bridge_budget_source_compatibility'for a in n.names)for n in ast.walk(ast.parse(raw)))
    if imported:self.assertIn(path.relative_to(ROOT).as_posix(),allowed)
  for relative in ('tests/profile_page_bridge_lifecycle_test.py','tests/page_bridge_guard_adapters.py','tests/profile_page_bridge_guard_adapters_test.py','tests/profile_resource_retirement_test.py'):
   self.assertNotIn('page_bridge_budget_source_compatibility',(ROOT/relative).read_text())
  self.assertFalse(overlay.manifest()['actualAndroidExecution']);self.assertFalse(overlay.manifest()['runtimeAcceptance'])
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PageBridgeBudgetSourceCompatibility));report=dict(schema=1,status='passed'if result.wasSuccessful()else'failed',tests=result.testsRun,baseCommit=overlay.BASE_COMMIT,baseTree=overlay.BASE_TREE,fixtureSha256=overlay.DELTA_SHA256,rows=3,contexts=4,rejectedSourceMutants=PageBridgeBudgetSourceCompatibility.source_negatives,rejectedProtectedGuardMutants=PageBridgeBudgetSourceCompatibility.guard_negatives,rejectedFixtureCounterfeits=PageBridgeBudgetSourceCompatibility.fixture_negatives,actualAndroidExecution=False,runtimeAcceptance=False,scope='Finite historical source inputs only. Actual PageBridge host keeps raw current production and actual guard mutation fragments.')
 output=os.environ.get('PAGE_BRIDGE_BUDGET_SOURCE_REPORT')
 if output:p=Path(output);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(report,indent=2)+'\n')
 raise SystemExit(0 if result.wasSuccessful()else 1)
