"""Historical CPU source input only: never native, page or Android acceptance."""
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

import cpu_source_compatibility as cpu
import worker_timezone_source_compatibility as worker
import dual_browser_source_compatibility as dual

ROOT=Path(__file__).resolve().parents[1]
SHA=lambda raw:hashlib.sha256(raw).hexdigest()
PRODUCERS={'app/src/main/java/local/pocketchat/ChatSession.java','app/src/main/java/local/pocketchat/GeckoWebView.java'}
WORKER_HOOK="""    if (digest, len(raw)) not in ((row['previousSha256'], row['previousBytes']),
                                  (row['reviewedSha256'], row['reviewedBytes'])):
        from cpu_source_compatibility import source_input as cpu_source_input
        raw = cpu_source_input(raw, relative)
        digest = _sha(raw)
"""

def assertions(raw):
    return [ast.dump(n,include_attributes=False)for n in ast.walk(ast.parse(raw))if isinstance(n,ast.Assert)
            or isinstance(n,ast.Call)and isinstance(n.func,ast.Attribute)and n.func.attr.startswith('assert')]

class CpuSourceCompatibility(unittest.TestCase):
    sourceMutants=0;guardMutants=0;fixtureMutants=0
    def test_whole_forward_inverse_equals_real_phase1_source(self):
        self.assertEqual(subprocess.check_output(['git','rev-parse',cpu.BASE_COMMIT+'^{tree}'],cwd=ROOT).decode().strip(),cpu.BASE_TREE)
        value=cpu.manifest();self.assertEqual(len(value['files']),5)
        self.assertEqual(sum(len(row['deltas'])for row in value['files'].values()),24)
        for relative,row in value['files'].items():
            before=subprocess.check_output(['git','show',cpu.BASE_COMMIT+':'+relative],cwd=ROOT);after=(ROOT/relative).read_bytes()
            self.assertEqual((SHA(before),len(before)),(row['previousSha256'],row['previousBytes']))
            self.assertEqual((SHA(after),len(after)),(row['reviewedSha256'],row['reviewedBytes']))
            self.assertEqual(cpu.source_input(before,relative),before)
            self.assertEqual(cpu.source_input(after,relative),before)
            forward=before
            for delta in row['deltas']:
                previous,current=delta['previous'].encode(),delta['current'].encode()
                self.assertEqual(forward.count(previous),1);forward=forward.replace(previous,current,1)
            self.assertEqual(forward,after)
            if relative in PRODUCERS:
                self.assertEqual(worker.source_input(after,relative),worker.source_input(before,relative))
                self.assertEqual(dual.source_input(after,relative),dual.source_input(before,relative))

    def test_missing_duplicate_changed_relocated_and_unknown_whole_source_rejects(self):
        rejected=0
        for relative,row in cpu.manifest()['files'].items():
            after=(ROOT/relative).read_bytes()
            for delta in row['deltas']:
                current=delta['current'].encode();self.assertEqual(after.count(current),1);remainder=after.replace(current,b'',1)
                moved=remainder+current
                if moved==after:moved=current+remainder
                for mutant in (remainder,after.replace(current,current*2,1),after.replace(current,current+b' ',1),moved):
                    self.assertNotEqual(mutant,after)
                    with self.assertRaises(ValueError):cpu.source_input(mutant,relative)
                    if relative in PRODUCERS:
                        with self.assertRaises(ValueError):worker.source_input(mutant,relative)
                        with self.assertRaises(ValueError):dual.source_input(mutant,relative)
                    rejected+=1
            for mutant in (after[:100],after+b' ',b'unknown whole source'):
                with self.assertRaises(ValueError):cpu.source_input(mutant,relative)
                rejected+=1
        self.assertEqual(rejected,111);type(self).sourceMutants=rejected

    def test_cold_runtime_native_rfp_and_owner_fences_cannot_normalize_away(self):
        relative='app/src/main/java/local/pocketchat/GeckoWebView.java';raw=(ROOT/relative).read_bytes()
        guards=(('if(!owner.cpu.claimRuntime(cpuBoot))throw new IOException("CPU cold runtime ownership changed");',''),
                ('if(destroyed||runtime!=cpuRuntime)return;','if(destroyed)return;'),
                ('if(!accepted){failure("原生 CPU 配置未确认，请重新打开当前环境");return;}',''),
                ('return owner.cpu.readyFor(runtime)&&nativeProtection.allows(owner.privacy.level());','return true;'),
                ('owner.cpu.protectionWillChange();closeExitIpPage();','closeExitIpPage();'),
                ('owner.cpu.refreshNative();acknowledgeIdentity();','acknowledgeIdentity();'))
        for old,new in guards:
            self.assertEqual(raw.count(old.encode()),1)
            mutant=raw.replace(old.encode(),new.encode(),1)
            with self.assertRaises(ValueError):cpu.source_input(mutant,relative)
            with self.assertRaises(ValueError):dual.source_input(mutant,relative)
        type(self).guardMutants=len(guards)

    def test_full_source_identity_precedes_context_inverse_and_types_paths_are_exact(self):
        relative='app/src/main/java/local/pocketchat/GeckoWebView.java';after=(ROOT/relative).read_bytes()
        class Forbidden:
            def encode(self,*args):raise AssertionError('Unknown source reached context replacement')
        value=copy.deepcopy(cpu.manifest());value['files'][relative]['deltas'][0]['current']=Forbidden()
        with patch.object(cpu,'manifest',return_value=value),self.assertRaisesRegex(ValueError,'unknown whole source'):
            cpu.source_input(after+b' ',relative)
        for raw in (after.decode(),bytearray(after),memoryview(after),None):
            with self.assertRaises(ValueError):cpu.source_input(raw,relative)
        for path in ('/'+relative,'../'+relative,relative+'.other',Path(relative),None,'app/src/main/java/local/pocketchat/GeckoCpuNative.java'):
            with self.assertRaises(ValueError):cpu.source_input(after,path)

    def test_fixture_hash_schema_source_pins_and_bounded_shapes_reject(self):
        original=cpu.manifest();relative='app/src/main/java/local/pocketchat/GeckoWebView.java';variants=[[],True]
        for key,bad in [('schema',True),('kind','runtime-acceptance'),('baseCommit','a'*40),('baseTree','b'*40),('actualAndroidExecution',True),('runtimeAcceptance',True),('unknown',1)]:
            v=copy.deepcopy(original);v[key]=bad;variants.append(v)
        v=copy.deepcopy(original);v['files'].pop(relative);variants.append(v)
        v=copy.deepcopy(original);v['files']['unknown.java']=v['files'][relative];variants.append(v)
        for key,bad in [('previousBytes',True),('reviewedBytes',0),('reviewedBytes',128*1024+1),('reviewedSha256','invalid'),('contextLines',2),('contextLines',17),('deltas',[])]:
            v=copy.deepcopy(original);v['files'][relative][key]=bad;variants.append(v)
        for key,bad in [('id','context-99'),('currentSha256','0'*64),('previous',''),('current','x'*(16*1024+1))]:
            v=copy.deepcopy(original);v['files'][relative]['deltas'][0][key]=bad;variants.append(v)
        with tempfile.TemporaryDirectory(prefix='cpu-history-fixture-')as folder:
            path=Path(folder)/'fixture.json';path.write_bytes(cpu.DELTA_PATH.read_bytes()+b' ')
            with patch.object(cpu,'DELTA_PATH',path),self.assertRaises(ValueError):cpu.manifest()
            for value in variants:
                raw=json.dumps(value,ensure_ascii=False).encode();path.write_bytes(raw)
                with patch.object(cpu,'DELTA_PATH',path),patch.object(cpu,'DELTA_SHA256',SHA(raw)),self.assertRaises(ValueError):cpu.manifest()
            path.write_bytes(b' '*(cpu.MAX_FIXTURE_BYTES+1))
            with patch.object(cpu,'DELTA_PATH',path),self.assertRaises(ValueError):cpu.manifest()
        type(self).fixtureMutants=len(variants)+2

    def test_old_fixtures_assertions_and_whole_historical_ports_remain_exact(self):
        for relative in ('tests/fixtures/dual-browser-source-deltas.json','tests/fixtures/worker-timezone-source-deltas.json'):
            self.assertEqual((ROOT/relative).read_bytes(),subprocess.check_output(['git','show',cpu.BASE_COMMIT+':'+relative],cwd=ROOT))
        self.assertEqual(SHA(dual.DELTA_PATH.read_bytes()),'b593b0db2b56b5a5d8143a920fbd15858dafbab21d1cdaf90ca2a5ba164c9933')
        self.assertEqual(SHA(worker.DELTA_PATH.read_bytes()),'4eafec08cbeb3beb9098ebf5df7b976423616bb213e47e802a1d39315a27602b')
        relative='tests/worker_timezone_source_compatibility.py';after=(ROOT/relative).read_bytes()
        self.assertEqual(after.count(WORKER_HOOK.encode()),1)
        self.assertEqual(after.replace(WORKER_HOOK.encode(),b'',1),subprocess.check_output(['git','show',cpu.BASE_COMMIT+':'+relative],cwd=ROOT))
        for relative in sorted(cpu.PATHS-PRODUCERS):
            after=(ROOT/relative).read_bytes();before=subprocess.check_output(['git','show',cpu.BASE_COMMIT+':'+relative],cwd=ROOT)
            if relative=='tests/profile_native_protection_test.py':
                # Added CPU controls remain current and mandatory; retain both
                # original runtime test methods exactly, including all asserts.
                previous_tree,current_tree=ast.parse(before),ast.parse(after)
                for node in (n for n in ast.walk(previous_tree)if isinstance(n,ast.FunctionDef)and n.name.startswith('test_')):
                    now=next(n for n in ast.walk(current_tree)if isinstance(n,ast.FunctionDef)and n.name==node.name)
                    self.assertEqual(ast.get_source_segment(before.decode(),node),ast.get_source_segment(after.decode(),now))
            else:
                self.assertEqual(assertions(after),assertions(before))
            self.assertEqual(cpu.source_input(after,relative),before)

        relative='tests/worker_timezone_host_source_compatibility.py';current=(ROOT/relative).read_bytes();before=subprocess.check_output(['git','show',cpu.BASE_COMMIT+':'+relative],cwd=ROOT)
        hook=WORKER_HOOK.replace('from cpu_source_compatibility import source_input as cpu_source_input','from cpu_source_compatibility import PATHS as cpu_paths, source_input as cpu_source_input').replace('        raw = cpu_source_input(raw, relative)\n        digest = _sha(raw)\n','        if relative in cpu_paths:\n            raw = cpu_source_input(raw, relative)\n            digest = _sha(raw)\n').encode()
        self.assertEqual(current.count(hook),1);self.assertEqual(current.replace(hook,b'',1),before)
        relative='tests/profile_worker_timezone_host_source_compatibility_test.py';current=(ROOT/relative).read_bytes();before=subprocess.check_output(['git','show',cpu.BASE_COMMIT+':'+relative],cwd=ROOT)
        imported=b'from cpu_source_compatibility import PATHS as cpu_paths, source_input as cpu_source_input\n'
        self.assertEqual(current.count(imported),1);current=current.replace(imported,b'',1)
        for variable,count in [('after',1),('current',5)]:
            hook=(';'+variable+'=cpu_source_input('+variable+',relative) if relative in cpu_paths else '+variable).encode()
            self.assertEqual(current.count(hook),count);current=current.replace(hook,b'')
        self.assertEqual(current,before);self.assertEqual(assertions(current),assertions(before))

    def test_only_reviewed_historical_ports_import_cpu_view(self):
        allowed={'tests/worker_timezone_source_compatibility.py','tests/profile_worker_timezone_source_compatibility_test.py','tests/profile_dual_browser_source_compatibility_test.py','tests/profile_cpu_source_compatibility_test.py','tests/worker_timezone_host_source_compatibility.py','tests/profile_worker_timezone_host_source_compatibility_test.py'}
        for folder in ('tests','tools'):
            for path in (ROOT/folder).rglob('*.py'):
                raw=path.read_text()
                if 'cpu_source_compatibility'not in raw:continue
                imported=any(isinstance(n,ast.ImportFrom)and n.module=='cpu_source_compatibility' or isinstance(n,ast.Import)and any(a.name=='cpu_source_compatibility'for a in n.names)for n in ast.walk(ast.parse(raw)))
                if imported:self.assertIn(path.relative_to(ROOT).as_posix(),allowed)
        for relative in ('tests/profile_native_protection_test.py','tests/gecko-cpu-controller-host/run.py','tests/gecko-cpu-host/run.py','tests/gecko-cpu-ui-host/run.py','tests/gecko-cpu-host/cleanup.py','tools/gecko/run_gecko_cpu_acceptance.py'):
            raw=(ROOT/relative).read_text();self.assertNotIn('cpu_source_compatibility',raw)
        self.assertFalse(cpu.manifest()['runtimeAcceptance']);self.assertFalse(cpu.manifest()['actualAndroidExecution'])

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CpuSourceCompatibility))
    report=dict(status='passed'if result.wasSuccessful()else'failed',tests=result.testsRun,baseCommit=cpu.BASE_COMMIT,baseTree=cpu.BASE_TREE,fixtureSha256=cpu.DELTA_SHA256,rows=5,contexts=24,rejectedContextSourceMutants=CpuSourceCompatibility.sourceMutants,rejectedColdNativeRfpGuardMutants=CpuSourceCompatibility.guardMutants,rejectedFixtureCounterfeits=CpuSourceCompatibility.fixtureMutants,runtimeAcceptance=False,actualAndroidExecution=False,scope='Historical source-input inverse only; original fixtures/goldens/assertions/negative controls retained. Actual CPU runtime hosts always compile current production.')
    output=os.environ.get('CPU_SOURCE_REPORT')
    if output:Path(output).write_text(json.dumps(report,indent=2)+'\n')
    raise SystemExit(0 if result.wasSuccessful()else 1)
