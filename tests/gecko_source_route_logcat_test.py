#!/usr/bin/env python3
"""Source-route log capture: real child byte decoding and mocked runner boundaries."""
import argparse, ast, contextlib, hashlib, importlib.util, io, json, os, pathlib
import subprocess, sys, tempfile, textwrap, types, unittest
from unittest import mock

HERE=pathlib.Path(__file__).resolve().parent
def repository_root():
 override=os.environ.get('POCKET_SOURCE_ROUTE_TEST_ROOT')
 if override:return pathlib.Path(override).resolve()
 for directory in pathlib.Path(__file__).resolve().parents:
  if (directory/'tools/gecko/network_sources_contract.py').is_file() and (directory/'tests/gecko/run_gecko_pool.py').is_file():return directory
 raise RuntimeError('Cannot locate repository containing source-route runner and contract')
ROOT=repository_root()
parser=argparse.ArgumentParser();parser.add_argument('--candidate',type=pathlib.Path,default=pathlib.Path(os.environ.get('POCKET_SOURCE_ROUTE_RUNNER',str(ROOT/'tests/gecko/run_network_sources_route.py'))));parser.add_argument('--output',type=pathlib.Path,default=ROOT/'work/gecko-integration/source-route-logcat-host-results.json');ARGS=parser.parse_args() if __name__=='__main__' else parser.parse_args([])
CANDIDATE=ARGS.candidate.resolve();START_HASH=hashlib.sha256(CANDIDATE.read_bytes()).hexdigest()
sys.path[:0]=[str(ROOT),str(ROOT/'tests/gecko')]
spec=importlib.util.spec_from_file_location('candidate_source_route_runner',CANDIDATE)
RUNNER=importlib.util.module_from_spec(spec);spec.loader.exec_module(RUNNER)
RUNNER.ROOT=ROOT
OLD_SOURCE=CANDIDATE.read_text()
OLD_MAIN=next(n for n in ast.parse(OLD_SOURCE).body if isinstance(n,ast.FunctionDef) and n.name=='main')
OLD_ADB=next(n for n in OLD_MAIN.body if isinstance(n,ast.FunctionDef) and n.name=='adb')
OLD_ADB_SOURCE=textwrap.dedent(ast.get_source_segment(OLD_SOURCE,OLD_ADB))
COMMIT='0'*40  # Controlled verifier identity; no claim about an actual CI commit.
NONCE='1'*32  # Controlled invocation; never device evidence.
COMPLETE=b'PocketNetworkSourceRoute: {"kind":"complete"}\n'

class TestBase(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='source-route-logcat-host-');self.root=pathlib.Path(self.tmp.name)
  RUNNER.OUT=self.root/'out';RUNNER.OUT.mkdir()
 def tearDown(self):self.tmp.cleanup()

class RealChildByteCases(TestBase):
 """These tests use actual subprocess.run decoding, not a substitute decoder."""
 def setUp(self):
  super().setUp();self.adb=self.root/'fake-adb'
  self.adb.write_text('#!'+sys.executable+'\nimport os,sys\nos.write(1,bytes.fromhex(os.environ.get("BYTE_STDOUT","")))\nos.write(2,bytes.fromhex(os.environ.get("BYTE_STDERR","")))\nsys.exit(int(os.environ.get("BYTE_EXIT","0")))\n')
  self.adb.chmod(0o700)
 def environment(self,out=b'',err=b'',code=0):return mock.patch.dict(os.environ,{'BYTE_STDOUT':out.hex(),'BYTE_STDERR':err.hex(),'BYTE_EXIT':str(code)})
 def old(self):
  namespace={'subprocess':subprocess,'args':types.SimpleNamespace(adb=str(self.adb),serial='controlled')};exec(OLD_ADB_SOURCE,namespace);return namespace['adb']
 def test_before_actual_subprocess_invalid_stdout_fails(self):
  with self.environment(b'prefix\xc2 suffix'):
   with self.assertRaises(UnicodeDecodeError):self.old()('logcat','-d')
 def test_before_actual_subprocess_invalid_stderr_fails(self):
  with self.environment(b'valid',b'error\xc2 suffix'):
   with self.assertRaises(UnicodeDecodeError):self.old()('logcat','-d')
 def test_after_actual_child_invalid_both_streams_preserved(self):
  out='中文'.encode()+b'\xc2 x\n';err=b'err\xc2 z\n'
  with self.environment(out,err):display=RUNNER.capture_logcat(str(self.adb),'controlled',stem='bad')
  self.assertEqual(display,'中文\\xc2 x\n');self.assertEqual((RUNNER.OUT/'bad-stdout.raw.log').read_bytes(),out);self.assertEqual((RUNNER.OUT/'bad-stderr.raw.log').read_bytes(),err)
  meta=json.loads((RUNNER.OUT/'bad-decode.json').read_text());self.assertEqual(meta['errors'],'backslashreplace');self.assertFalse(meta['timedOut'])
  for key,raw in [('stdout',out),('stderr',err)]:self.assertIsNotNone(meta['streams'][key]['invalidUtf8']);self.assertEqual(meta['streams'][key]['sha256'],hashlib.sha256(raw).hexdigest());self.assertEqual(meta['streams'][key]['bytes'],len(raw))
 def test_after_actual_child_valid_unicode_is_unchanged(self):
  out='恢复线路 · 正常\n'.encode();err='提示\n'.encode()
  with self.environment(out,err):display=RUNNER.capture_logcat(str(self.adb),'controlled',stem='valid')
  self.assertEqual(display,out.decode());meta=json.loads((RUNNER.OUT/'valid-decode.json').read_text());self.assertIsNone(meta['streams']['stdout']['invalidUtf8']);self.assertIsNone(meta['streams']['stderr']['invalidUtf8'])
 def test_after_nonzero_real_child_preserves_bytes_before_error(self):
  out=b'x\xc2 y';err=b'e\xff';
  with self.environment(out,err,9):
   with self.assertRaises(subprocess.CalledProcessError) as got:RUNNER.capture_logcat(str(self.adb),'controlled',stem='exit')
  self.assertEqual(got.exception.returncode,9);self.assertEqual(got.exception.stdout,out);self.assertEqual(got.exception.stderr,err);self.assertEqual((RUNNER.OUT/'exit-stdout.raw.log').read_bytes(),out);self.assertEqual(json.loads((RUNNER.OUT/'exit-decode.json').read_text())['returncode'],9)
 def test_after_nonzero_real_child_check_false_is_diagnostic_only(self):
  with self.environment(b'x\xc2 y',b'e\xff',9):display=RUNNER.capture_logcat(str(self.adb),'controlled',stem='unchecked',check=False)
  self.assertEqual(display,'x\\xc2 y');self.assertEqual(json.loads((RUNNER.OUT/'unchecked-decode.json').read_text())['returncode'],9)

class HelperFaultCases(TestBase):
 def test_timeout_partial_bytes_saved_then_original_error_rethrown(self):
  error=subprocess.TimeoutExpired(['adb'],30,output=b'partial\xc2 x',stderr=b'e\xff')
  with mock.patch.object(RUNNER.subprocess,'run',side_effect=error):
   with self.assertRaises(subprocess.TimeoutExpired) as got:RUNNER.capture_logcat('adb','controlled',stem='timeout')
  self.assertIs(got.exception,error);self.assertEqual((RUNNER.OUT/'timeout-stdout.raw.log').read_bytes(),error.stdout);self.assertEqual((RUNNER.OUT/'timeout-stderr.raw.log').read_bytes(),error.stderr);self.assertTrue(json.loads((RUNNER.OUT/'timeout-decode.json').read_text())['timedOut'])
 def test_server_saved_before_diagnostic_capture_failure(self):
  server=self.root/'server.json';server.write_bytes(b'{"server":"kept"}\n')
  def fail(*a,**k):self.assertEqual((RUNNER.OUT/'network-source-route-server-failure.json').read_bytes(),server.read_bytes());raise OSError('secondary logcat failure')
  with mock.patch.object(RUNNER,'capture_logcat',side_effect=fail):RUNNER.save_failure_diagnostics('adb','controlled',server)
  errors=json.loads((RUNNER.OUT/'network-source-route-diagnostic-errors.json').read_text());self.assertEqual(errors['errors'][0]['stage'],'logcat')

class Node:
 def __init__(self,command,**kwargs):self.stdout=io.StringIO('{"ready":true,"port":9879,"protocol":"h2"}\n');self.stderr=io.StringIO();pathlib.Path(command[-1]).write_text('{"server":"must-survive"}');self.stopped=False
 def terminate(self):self.stopped=True
 def communicate(self,timeout=None):return ('','')
 def kill(self):self.stopped=True

class MainScenario:
 """External commands are mocked; candidate main/JSON/actual verify stay real."""
 def __init__(self,log=COMPLETE,provider=None,provider_err=b'',diagnostic_failure=False):self.log=log;self.provider=provider if provider is not None else json.dumps(dict(schema=1,status='failed',error='controlled route failure',sourceCommit=COMMIT,runNonce=NONCE,buildIdentity=dict(sourceCommit=COMMIT))).encode();self.provider_err=provider_err;self.diagnostic_failure=diagnostic_failure;self.provider_reads=0;self.verify_calls=0;self.logs=0;self.clock=0;self.stdout=io.StringIO();self.run_calls=[]
 def run(self,command,**kwargs):
  self.run_calls.append((command,kwargs));out=b'';err=b''
  if command[0]=='openssl':return subprocess.CompletedProcess(command,0)
  parts=command[3:]
  if parts[:2]==['logcat','-d']:
   self.logs+=1
   if self.diagnostic_failure and self.logs>1:
    assert (RUNNER.OUT/'network-source-route-server-failure.json').exists(), 'server must be preserved before diagnostic log attempt'
    raise OSError('secondary logcat unavailable')
   assert not kwargs.get('text',False), 'only logcat must use bytes'
   out=self.log;err=b'log-stderr\xc2 tail'
  elif parts[:3]==['exec-out','content','read']:
   self.provider_reads+=1;assert kwargs.get('text') is True,'provider must keep original strict text path';out=self.provider;err=self.provider_err
  elif parts[:2]==['shell','getprop']:out=b'35\n'
  if kwargs.get('text'):
   # Boundary model for main tests. Real subprocess decoding is separately
   # executed by RealChildByteCases; this does not claim a real child here.
   out=out.decode('utf-8','strict');err=err.decode('utf-8','strict')
  return subprocess.CompletedProcess(command,0,out,err)
 def monotonic(self):self.clock+=1;return self.clock
 def execute(self):
  actual_verify=RUNNER.verify
  def verified(*a,**k):self.verify_calls+=1;return actual_verify(*a,**k)
  # These retained cases test strict log/provider failure boundaries. The new
  # external APK/ownership setup is controlled here; its actual helper has a
  # separate source_route_cleanup_contract_test.py suite with negative controls.
  class ControlledCleanup:
   def poll(self,raw):pass
   def cleanup(self,snapshot,evidence_saved):return dict(status='cleaned',fixtureResultChanged=False)
  with contextlib.ExitStack() as stack:
   stack.enter_context(mock.patch.object(RUNNER,'prepare_cleanup_fence',return_value=getattr(self,'cleanupFence',ControlledCleanup()),side_effect=getattr(self,'cleanupPreparationError',None)))
   stack.enter_context(mock.patch.object(RUNNER.subprocess,'run',side_effect=self.run));stack.enter_context(mock.patch.object(RUNNER.subprocess,'Popen',side_effect=Node));stack.enter_context(mock.patch.object(RUNNER.subprocess,'check_output',return_value=COMMIT+'\n'))
   stack.enter_context(mock.patch.object(RUNNER.select,'select',side_effect=lambda r,w,e,t:(r,w,e)));stack.enter_context(mock.patch.object(RUNNER.time,'monotonic',side_effect=self.monotonic));stack.enter_context(mock.patch.object(RUNNER.time,'sleep',return_value=None));stack.enter_context(mock.patch.object(RUNNER,'verify',side_effect=verified));stack.enter_context(mock.patch.object(sys,'argv',['runner','--adb','controlled-adb','--timeout','3']));stack.enter_context(contextlib.redirect_stdout(self.stdout))
   stack.enter_context(mock.patch.object(RUNNER.uuid,'uuid4',return_value=types.SimpleNamespace(hex=NONCE)))
   RUNNER.main()

class MainBoundaryCases(TestBase):
 def test_fatal_log_rejected_even_with_complete_marker_and_invalid_bytes(self):
  scenario=MainScenario(log=b'noise\xc2 x\nFATAL EXCEPTION\n'+COMPLETE)
  with self.assertRaises(AssertionError) as got:scenario.execute()
  self.assertIn('FATAL EXCEPTION',str(got.exception));self.assertEqual(scenario.provider_reads,0);self.assertEqual(scenario.verify_calls,0);self.assertNotIn('"status": "passed"',scenario.stdout.getvalue());self.assertTrue((RUNNER.OUT/'network-source-route-logcat-stdout.raw.log').exists())
 def test_complete_marker_bad_provider_stdout_utf8_still_rejected(self):
  scenario=MainScenario(provider=b'{"status":"passed"}\xc2 x')
  with self.assertRaises(UnicodeDecodeError):scenario.execute()
  self.assertEqual(scenario.provider_reads,1);self.assertEqual(scenario.verify_calls,0);self.assertFalse((RUNNER.OUT/'network-source-route-results.json').exists())
 def test_complete_marker_bad_provider_stderr_utf8_still_rejected(self):
  scenario=MainScenario(provider=b'{"status":"passed"}',provider_err=b'bad\xc2 x')
  with self.assertRaises(UnicodeDecodeError):scenario.execute()
  self.assertEqual(scenario.provider_reads,1);self.assertEqual(scenario.verify_calls,0)
 def test_complete_marker_invalid_provider_json_still_rejected(self):
  scenario=MainScenario(provider=b'not JSON')
  with self.assertRaises(json.JSONDecodeError):scenario.execute()
  self.assertEqual(scenario.provider_reads,1);self.assertEqual(scenario.verify_calls,0)
 def test_complete_marker_failed_report_rejected_by_actual_verifier(self):
  scenario=MainScenario()
  with self.assertRaises(AssertionError):scenario.execute()
  self.assertEqual(scenario.verify_calls,1);self.assertEqual(json.loads((RUNNER.OUT/'network-source-route-results.json').read_text())['status'],'failed');self.assertNotIn('"status": "passed"',scenario.stdout.getvalue())
 def reject_identity(self,field,value):
  report=dict(schema=1,status='failed',sourceCommit=COMMIT,runNonce=NONCE,buildIdentity=dict(sourceCommit=COMMIT));report[field]=value
  scenario=MainScenario(provider=json.dumps(report).encode())
  with self.assertRaises(AssertionError):scenario.execute()
  self.assertEqual(scenario.verify_calls,0)
  saved=json.loads((RUNNER.OUT/'network-source-route-results.json').read_text())
  self.assertEqual(saved[field],value);self.assertEqual(saved['runnerInvocation'],dict(sourceCommit=COMMIT,runNonce=NONCE))
  launches=[command for command,_ in scenario.run_calls if command[3:7]==['shell','am','start','-W']]
  self.assertEqual(len(launches),1);self.assertEqual(launches[0][-6:],['--es','sourceCommit',COMMIT,'--es','runNonce',NONCE])
  self.assertNotIn('"status": "passed"',scenario.stdout.getvalue())
 def test_wrong_producer_source_is_retained_and_rejected(self):self.reject_identity('sourceCommit','2'*40)
 def test_wrong_producer_nonce_is_retained_and_rejected(self):self.reject_identity('runNonce','2'*32)
 def test_wrong_installed_build_source_is_retained_and_rejected(self):self.reject_identity('buildIdentity',dict(sourceCommit='2'*40))
 def test_complete_marker_in_unrelated_log_does_not_read_provider(self):
  scenario=MainScenario(log=b'{"kind":"complete"}\n')
  with self.assertRaises(TimeoutError):scenario.execute()
  self.assertEqual(scenario.provider_reads,0);self.assertEqual(scenario.verify_calls,0)
 def test_original_failure_survives_secondary_logcat_failure_and_server_is_saved(self):
  scenario=MainScenario(log=b'FATAL EXCEPTION: original\xc2 x\n',diagnostic_failure=True)
  with self.assertRaises(AssertionError) as got:scenario.execute()
  self.assertIn('FATAL EXCEPTION: original',str(got.exception));self.assertEqual(json.loads((RUNNER.OUT/'network-source-route-server-failure.json').read_text()),{'server':'must-survive'});meta=json.loads((RUNNER.OUT/'network-source-route-diagnostic-errors.json').read_text());self.assertEqual(meta['errors'][0]['stage'],'logcat');self.assertEqual(scenario.verify_calls,0)

class RecordedResult(unittest.TextTestResult):
 def __init__(self,*a,**k):super().__init__(*a,**k);self.rows=[]
 def addSuccess(self,test):super().addSuccess(test);self.rows.append({'name':test.id(),'pass':True})
 def addFailure(self,test,err):super().addFailure(test,err);self.rows.append({'name':test.id(),'pass':False,'error':self._exc_info_to_string(err,test)})
 def addError(self,test,err):super().addError(test,err);self.rows.append({'name':test.id(),'pass':False,'error':self._exc_info_to_string(err,test)})

if __name__=='__main__':
 suite=unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]);stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=RecordedResult).run(suite)
 unchanged=hashlib.sha256(CANDIDATE.read_bytes()).hexdigest()==START_HASH
 report={'status':'passed' if result.wasSuccessful() and unchanged else 'failed','actualAndroidExecution':False,'candidateSha256':START_HASH,'candidateBytesUnchanged':unchanged,'baseline':'Exact retained nested strict adb helper invoked with logcat arguments; reproduces the prior logcat decoding behavior.','beforeAdbExactSourceSha256':hashlib.sha256(OLD_ADB_SOURCE.encode()).hexdigest(),'tests':result.rows,'scope':{'realSubprocessTests':6,'helperFaultTests':2,'mockedMainTests':10,'actualVerifierUsed':True,'limitations':['RealChildByteCases execute real Python subprocess decoding through a local fake adb executable; no adb/Android/socket execution.','MainBoundaryCases mock external commands, clock, Node process and the added external APK/cleanup fence; candidate main, strict adb/json.loads, diagnostics and the actual source-route verifier still execute. All original case assertions remain.','Cleanup identity/negative controls execute the actual helper separately in source_route_cleanup_contract_test.py; these boundary mocks are not cleanup or Android qualification.','No assertion claims the Android source-route fixture passed.']},'hostTestSha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'output':stream.getvalue()}
 ARGS.output.parent.mkdir(parents=True,exist_ok=True);ARGS.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:report[k] for k in ['status','candidateSha256','candidateBytesUnchanged','scope']},ensure_ascii=False));print(stream.getvalue())
 if not result.wasSuccessful() or not unchanged:raise SystemExit(1)
