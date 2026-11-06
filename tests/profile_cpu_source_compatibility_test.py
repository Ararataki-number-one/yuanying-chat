"""Finite CPU historical metadata; never Android, compiler or release evidence."""
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch
import cpu_source_compatibility as cpu
ROOT=Path(__file__).resolve().parents[1]
SHA=lambda raw:hashlib.sha256(raw).hexdigest()
SUITES=('tests/profile_pure212_ci_source_compatibility_test.py','tests/profile_worker_timezone_source_compatibility_test.py','tests/profile_dual_browser_source_compatibility_test.py','tests/profile_ip_timezone_source_compatibility_test.py','tests/profile_ui_observer_source_compatibility_test.py','tests/profile_ui_quick_sheet_source_compatibility_test.py')
FROZEN_FIXTURES={'tests/fixtures/android-launcher-package-86db516.txt': '7e66eb178577df7b5919aef3031030ca337677533b67c6d84ab41381f8cc48d8', 'tests/fixtures/chrome-first-tap-source-deltas.json': '2c31cb3286d88a91079fb33cef1f27b9c81f7cefda6fbb1c7bc6537e6ca79795', 'tests/fixtures/connection-timezone-prerequisite-source-deltas.json': 'cf99d65553fa119fe6154f591487b103a1b805646220490c6992f19ba073b0b8', 'tests/fixtures/dual-browser-source-deltas.json': 'b593b0db2b56b5a5d8143a920fbd15858dafbab21d1cdaf90ca2a5ba164c9933', 'tests/fixtures/event-journal-source-deltas.json': '13620b58a536ebe4e0b822cd5b6ea11b9656cfdb83f2e18ee8c90ee0fa3c4254', 'tests/fixtures/experience46-source-deltas.json': 'd09e89773bac82f8fe7e5d7375967eafe72e20e55b014da79926d9f2bb1a1ef1', 'tests/fixtures/failed-chain-host-dependency210-inverse.json': '64c2382033dd565ec33f12cad1d737bd2ee13d842d12d441a16f991462e7257c', 'tests/fixtures/fingerprint-gecko-reading-preservation.patch': 'f831967e6d6a4265ffadc8ffa008402a091da1204812ec71e6593b37256c22b9', 'tests/fixtures/gecko-policy-dependency-source-deltas.json': '8cb13b6e7ca1ddcb9bd129f0bcd74707f36d9efb03db4f973f3e9dca3c6b8f2a', 'tests/fixtures/ip-timezone-source-deltas.json': '2a84a6ac4cb8246ea633d314bbcc9b75b8ab9e180507e6a7017533519106c0bb', 'tests/fixtures/network-performance-local-process46-inverse.json': '7e54f06265977462f05741a32c688ff4ddccb5760791f49054a5a1b6089a1974', 'tests/fixtures/network-settings-callback-source-deltas.json': '8f4157350dc8eb9bf2b6c8e6d6345b4383f67c5585198ca4299b0134ae56e21c', 'tests/fixtures/network-sources-ui46-actual-inactive.provenance.json': '884e61be1d163656751ed7710e2d5c922de580d80291d3a73fc12eea2c2abe03', 'tests/fixtures/network-sources-ui46-actual-inactive.xml': '5e2f431f22f2cad2fdb6e6b469f3312a67ee9040d20d1374b4422ad7d1573cf6', 'tests/fixtures/page-bridge-budget-source-deltas.json': '99746ad0db1b671e73088b0b7b90b3ba4b8c4f25c560266042f62777352dc619', 'tests/fixtures/phase1-context-fix-source-deltas.json': '6e9b6fb645c5b918c4b18d37fe69f1d3d9a586d6fa1db9b81d7b98c28d070ad4', 'tests/fixtures/profile-display-workflow-additions.json': '92bb795ef55d771692c5874ad20bfd446056c85b229517e98969a99dcf0aacde', 'tests/fixtures/pure212-ci-source-deltas.json': 'bc0b96d515e44c4fa9088dd46866f1f86819abe2bb06dee120c15344fa565137', 'tests/fixtures/reading-zoom-trace-additions.json': '80bcd24da9c5e7eb1ab975fa6e4d1ffa5193c63e5ecafa870b220c3d5fb16478', 'tests/fixtures/reading45-restoration-source-deltas.json': '8d9fd8380a5d6337860989ad8ce95b0529773cdfa433ef090b229a8beb423f3c', 'tests/fixtures/ui-observer-source-deltas.json': '998637d381722c943cb32517cb1c72e092d0d0db7581e0f7c9103d74303b42c8', 'tests/fixtures/ui-quick-sheet-source-deltas.json': 'c0588f2e30e6250bb446ecf472ffe3c2d7f3bf77c471d3cc16cdf845deb385e4', 'tests/fixtures/window-tap-readiness-additions.json': '50b47065b5e295702ce7e4b368e4c19d592935b37bcbcc2735a4e8febe0b7082', 'tests/fixtures/worker-timezone-host-adapter-source-deltas.json': '8c3f0c4d629d3d1a584ef3347f511b26081a59d35ba4d8621838db1f4735fbed', 'tests/fixtures/worker-timezone-source-deltas.json': '4eafec08cbeb3beb9098ebf5df7b976423616bb213e47e802a1d39315a27602b'}

def git(*args):return subprocess.check_output(['git','--no-replace-objects',*args],cwd=ROOT,env=dict(os.environ,GIT_NO_LAZY_FETCH='1'))
def rhs(raw):return [ast.dump(ast.Tuple(elts=n.args[1:],ctx=ast.Load()),include_attributes=False) for n in ast.walk(ast.parse(raw)) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr.startswith('assert')]
def test_names(raw):return [n.name for n in ast.walk(ast.parse(raw)) if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')]
def strip_read_ports(raw):
 s=raw.decode();lines=s.splitlines(keepends=True);changes=[]
 def span(n):return sum(map(len,lines[:n.lineno-1]))+n.col_offset,sum(map(len,lines[:n.end_lineno-1]))+n.end_col_offset
 def port(n):return isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name) and n.func.value.id=='_cpu_history' and n.func.attr=='metadata_input' and len(n.args)==2
 for n in ast.walk(ast.parse(s)):
  if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='decode' and port(n.func.value) and isinstance(n.func.value.args[1],ast.Constant) and n.func.value.args[1].value=='tools/browser/source_history.py':
   x,y=span(n);changes.append((x,y,ast.get_source_segment(s,n.func.value.args[0]).replace('.read_bytes()','.read_text()')))
  elif port(n):x,y=span(n);changes.append((x,y,ast.get_source_segment(s,n.args[0])))
 selected=[]
 for x,y,value in sorted(changes,key=lambda r:(r[0],-r[1])):
  if selected and x<selected[-1][1]:continue
  selected.append((x,y,value))
 for x,y,value in reversed(selected):s=s[:x]+value+s[y:]
 token='import cpu_source_compatibility as _cpu_history\n\n'
 if s.count(token)!=1:raise AssertionError('One declared CPU metadata import required')
 return s.replace(token,'',1).encode()

class CpuHistoricalSources(unittest.TestCase):
 def test_public_working_predecessor_and_all_whole_rows_forward_inverse(self):
  self.assertEqual(git('rev-parse',cpu.BASE_COMMIT+'^{tree}').decode().strip(),cpu.BASE_TREE)
  m=cpu.manifest();self.assertEqual(len(m['files']),23);self.assertEqual(sum(len(r['deltas'])for r in m['files'].values()),84)
  self.assertFalse(m['actualAndroidExecution']);self.assertFalse(m['runtimeAcceptance'])
  for path,row in m['files'].items():
   before=git('show',cpu.BASE_COMMIT+':'+path);current=(ROOT/path).read_bytes()
   self.assertEqual((len(before),SHA(before)),(row['previousBytes'],row['previousSha256']))
   self.assertEqual(cpu.source_input(current,path),before);self.assertIs(cpu.source_input(before,path),before)
   for d in row['deltas']:
    self.assertEqual(before.count(d['previous'].encode()),1);before=before.replace(d['previous'].encode(),d['current'].encode(),1)
   self.assertEqual(before,current)
 def test_unknown_missing_duplicated_changed_moved_and_type_inputs_rejected(self):
  count=0
  for path,row in cpu.manifest()['files'].items():
   raw=(ROOT/path).read_bytes()
   for d in row['deltas']:
    chunk=d['current'].encode();remainder=raw.replace(chunk,b'',1);moved=remainder+chunk
    if moved==raw:moved=chunk+remainder
    for bad in (remainder,raw.replace(chunk,chunk*2,1),raw.replace(chunk,chunk+b' ',1),moved):
     with self.assertRaises(ValueError):cpu.source_input(bad,path)
     count+=1
   for bad in (raw[:60],raw+b' ',b'unknown complete image'):
    with self.assertRaises(ValueError):cpu.source_input(bad,path)
    count+=1
  self.assertEqual(count,405)
  path=next(iter(cpu.PATHS));raw=(ROOT/path).read_bytes()
  for bad in (None,True,bytearray(raw),raw.decode()):
   with self.assertRaises(ValueError):cpu.source_input(bad,path)
  for path in (None,Path(path),'../'+path,'/'+path,path+'.foreign','unknown.py'):
   with self.assertRaises(ValueError):cpu.source_input(raw,path)
 def test_manifest_types_scope_and_context_shapes_failclosed(self):
  original=cpu.manifest();path=next(iter(cpu.PATHS));variants=[]
  for key,value in [('schema',True),('kind','runtime'),('baseCommit','f'*40),('baseTree','e'*40),('actualAndroidExecution',True),('runtimeAcceptance',True)]:
   d=copy.deepcopy(original);d[key]=value;variants.append(d)
  for key,value in [('previousBytes',True),('reviewedBytes',0),('reviewedBytes',cpu.MAX_SOURCE+1),('reviewedSha256','bad'),('contextLines',2),('contextLines',17),('deltas',[])]:
   d=copy.deepcopy(original);d['files'][path][key]=value;variants.append(d)
  for key,value in [('id','context-99'),('previous',''),('current','x'*65537),('currentSha256','0'*64)]:
   d=copy.deepcopy(original);d['files'][path]['deltas'][0][key]=value;variants.append(d)
  d=copy.deepcopy(original);d['files'].pop(path);variants.append(d)
  d=copy.deepcopy(original);d['files']['foreign.py']=d['files'][path];variants.append(d)
  d=copy.deepcopy(original);d['unknown']=False;variants.append(d)
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'fixture.json'
   for d in variants:
    raw=json.dumps(d).encode();p.write_bytes(raw)
    with patch.object(cpu,'FIXTURE',p),patch.object(cpu,'FIXTURE_SHA256',SHA(raw)),self.assertRaises(ValueError):cpu.manifest()
   p.write_bytes(cpu.FIXTURE.read_bytes()+b' ')
   with patch.object(cpu,'FIXTURE',p),self.assertRaises(ValueError):cpu.manifest()
   target=Path(tmp)/'symlink.json';target.symlink_to(cpu.FIXTURE)
   with patch.object(cpu,'FIXTURE',target),self.assertRaises(ValueError):cpu.manifest()
  self.assertEqual(len(variants),20)
 def test_initial_whole_pin_and_final_closure_are_independent_executable_guards(self):
  source=Path(cpu.__file__).read_text();path='app/src/main/java/local/pocketchat/GeckoWebView.java';raw=(ROOT/path).read_bytes()
  class Forbidden:
   def encode(self,*args):raise AssertionError('Unknown whole input reached context inversion')
  value=copy.deepcopy(cpu.manifest());value['files'][path]['deltas'][0]['current']=Forbidden()
  with patch.object(cpu,'manifest',return_value=value),self.assertRaisesRegex(ValueError,'unknown whole'):cpu.source_input(raw+b' ',path)
  initial=" if (len(raw),sha(raw))!=(row['reviewedBytes'],row['reviewedSha256']):raise ValueError('CPU inverse rejects unknown whole source bytes')\n"
  final=" if (len(raw),sha(raw))!=(row['previousBytes'],row['previousSha256']):raise ValueError('CPU inverse did not close to complete public212 source')\n"
  for label,guard in [('whole',initial),('closure',final)]:
   self.assertEqual(source.count(guard),1);namespace={'__file__':cpu.__file__};exec(compile(source.replace(guard,'',1),'<compiled-cpu-'+label+'>','exec'),namespace)
   if label=='whole':
    namespace['manifest']=lambda:value
    with self.assertRaisesRegex(AssertionError,'reached context'):namespace['source_input'](raw+b' ',path)
   else:
    malformed=copy.deepcopy(cpu.manifest());malformed['files'][path]['deltas'][0]['previous']+='changed-closing-target'
    with patch.object(cpu,'manifest',return_value=malformed),self.assertRaisesRegex(ValueError,'did not close'):cpu.source_input(raw,path)
    namespace['manifest']=lambda:malformed
    self.assertNotEqual(namespace['source_input'](raw,path),git('show',cpu.BASE_COMMIT+':'+path))
 def test_original_suites_oracles_and_all_old_fixture_bytes_preserved(self):
  for path in SUITES:
   now=(ROOT/path).read_bytes();before=git('show',cpu.BASE_COMMIT+':'+path)
   self.assertEqual(strip_read_ports(now),before,path)
   self.assertEqual(rhs(now),rhs(before),path);self.assertEqual(test_names(now),test_names(before),path)
  for path,pin in FROZEN_FIXTURES.items():self.assertEqual(SHA((ROOT/path).read_bytes()),pin,path)
  for path in ('tests/pure212_ci_source_compatibility.py','tests/dual_browser_source_compatibility.py'):
   raw=(ROOT/path).read_bytes();token=b'\n# Later CPU additions are reversed only for retained source oracles.\nfrom cpu_source_compatibility import wrap_bytes as _cpu_wrap_bytes\nsource_input = _cpu_wrap_bytes(source_input)\n'
   self.assertEqual(raw.count(token),1);self.assertEqual(raw.replace(token,b'',1),git('show',cpu.BASE_COMMIT+':'+path))
 def test_catalog_prior_rows_prefix_and_real_public_before_objects(self):
  now=json.loads((ROOT/'tests/baselines/public-source-history.json').read_bytes());before=json.loads(git('show',cpu.BASE_COMMIT+':tests/baselines/public-source-history.json'))
  self.assertEqual((len(before['groups']),sum(len(g['files'])for g in before['groups'])),(17,149))
  self.assertEqual(now['groups'][:-1],before['groups']);self.assertEqual((len(now['groups']),sum(len(g['files'])for g in now['groups'])),(18,172))
  added=now['groups'][-1];self.assertEqual((added['commit'],added['tree']),(cpu.BASE_COMMIT,cpu.BASE_TREE));self.assertEqual(set(added['files']),cpu.PATHS)
  for path,pin in added['files'].items():
   raw=git('show',cpu.BASE_COMMIT+':'+path);self.assertEqual((len(raw),SHA(raw)),(pin['bytes'],pin['sha256']));self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),pin['blob'])
 def test_current_cpu_gate_mutants_cannot_borrow_historical_input(self):
  path='app/src/main/java/local/pocketchat/GeckoWebView.java';raw=(ROOT/path).read_bytes()
  for before,after in [('owner.cpu.readyFor(runtime)&&',''),('if(!owner.cpu.claimRuntime(cpuBoot))','if(false)'),('owner.cpu.retire(runtime);','')]:
   self.assertEqual(raw.count(before.encode()),1)
   with self.assertRaises(ValueError):cpu.source_input(raw.replace(before.encode(),after.encode(),1),path)
 def test_window_metadata_accepts_exact_cpu_image_but_compilation_stays_raw(self):
  p=ROOT/'tests/gecko-ip-window-barrier-host/run.py';s=importlib.util.spec_from_file_location('actual_raw_cpu_window_host',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
  raw=(ROOT/m.SOURCE_PATH).read_bytes();before=git('show',m.BASE+':'+m.SOURCE_PATH);reference=git('show',cpu.BASE_COMMIT+':'+m.SOURCE_PATH)
  self.assertTrue(m.composed_cpu_source_verified(raw,before,reference));self.assertFalse(m.composed_cpu_source_verified(raw+b' ',before,reference))
  self.assertIn('selected = {name: declaration(source.read_text(), name) for name in MEMBERS}',p.read_text());self.assertNotIn('cpu_source_compatibility',p.read_text())
  for marker,old,new in [('public void lookupIp(','if(!ready||!current())','if(false)'),('void lookupIpTimeZone(','},8500);','},8501);')]:
   member=m.declaration(raw.decode(),marker).encode();self.assertEqual(member.count(old.encode()),1)
   changed=raw.replace(member,member.replace(old.encode(),new.encode(),1),1);original_sha=m.sha
   with patch.object(m,'sha',side_effect=lambda value:'a99936da23c75199bcfd38fe9afbe81a64f412a723065296edcf0a5905437e62' if value==changed else original_sha(value)):
    self.assertFalse(m.composed_cpu_source_verified(changed,before,reference))
 def test_ui_whole_metadata_ast_and_raw_sixth_field_boundary(self):
  raw=(ROOT/cpu.UI_RUNNER).read_bytes();before=git('show',cpu.BASE_COMMIT+':'+cpu.UI_RUNNER);self.assertEqual(raw.count(cpu.UI_LABEL.encode()),1)
  self.assertEqual(cpu.source_input(raw,cpu.UI_RUNNER),before)
  preparation=("from ui_test_device import prepare_workflow as prepare_ui_test_device\n"
   "(out/'ui-test-device-isolation.json').write_text(json.dumps(prepare_ui_test_device(adb,serial=args.serial,environment=os.environ),sort_keys=True,indent=2)+'\\n')\n").encode()
  self.assertEqual(raw.count(preparation),1);self.assertEqual(before.count(preparation),1)
  self.assertEqual(len(cpu.UI_AST_PAIRS),2)
  for actual,previous in ((raw,before),(raw.replace(preparation,b'',1),before.replace(preparation,b'',1))):
   for text in (actual,b'# coding: utf-8\n# Formatting only\n'+ast.unparse(ast.parse(actual)).encode()+b'\n'):
    self.assertEqual(cpu.tree_sha(cpu.ui_tree_input(ast.parse(text))),cpu.tree_sha(ast.parse(previous)))
  imported,call=preparation.splitlines(keepends=True)
  for changed in (raw.replace(preparation,preparation*2,1),raw.replace(preparation,imported,1),raw.replace(preparation,call,1),raw.replace(preparation,b'',1)+preparation):
   with self.assertRaises(ValueError):cpu.ui_tree_input(ast.parse(changed))
  with self.assertRaises(ValueError):cpu.ui_tree_input(ast.parse(raw+b'\nextra_guard=False\n'))
  changed=raw.replace(cpu.UI_LABEL.encode(),'unknown extra field'.encode(),1)
  with self.assertRaises(ValueError):cpu.source_input(changed,cpu.UI_RUNNER)
 def test_no_application_runtime_or_compiler_imports_the_cpu_source_view(self):
  allowed={str(Path(__file__).relative_to(ROOT)),*SUITES,'tests/pure212_ci_source_compatibility.py','tests/dual_browser_source_compatibility.py','tests/ip_timezone_source_compatibility.py','tests/ui_quick_sheet_source_compatibility.py'}
  for directory in ('app/src/main','tools','tests'):
   for p in (ROOT/directory).rglob('*'):
    if not p.is_file()or p.suffix not in ('.py','.java','.js'):continue
    if p.suffix=='.py':
     imported=any(isinstance(n,ast.ImportFrom)and n.module=='cpu_source_compatibility'or isinstance(n,ast.Import)and any(a.name=='cpu_source_compatibility'for a in n.names)for n in ast.walk(ast.parse(p.read_text())))
     if imported:self.assertIn(p.relative_to(ROOT).as_posix(),allowed)
    elif directory=='app/src/main':self.assertNotIn('cpu_source_compatibility',p.read_text())
  self.assertFalse(cpu.manifest()['actualAndroidExecution']);self.assertFalse(cpu.manifest()['runtimeAcceptance'])
if __name__=='__main__':unittest.main(verbosity=2)
