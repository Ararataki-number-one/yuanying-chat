"""Run the new 46 behavior hosts within the existing source-bound host jobs.

Boundary adapters are explicit in each report. These are not Android, physical
phone, network-protection, frame-time or overall performance acceptance.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest
from experience46_host_evidence import INVOCATION_FILES, emit_evidence, new_attempt, run_recorded

ROOT=Path(__file__).resolve().parents[1]
HOST_FILES=('results.json','results.log','results.compile.stdout.log','results.compile.stderr.log',
            'results.stdout.log','results.stderr.log',*INVOCATION_FILES)
class Experience46Hosts(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  java=os.environ.get('PROFILE_JAVA') or shutil.which('java')
  if not java:raise RuntimeError('Existing JDK required for mandatory experience hosts')
  cls.java=Path(java).resolve();cls.home=cls.java.parents[1]
  cls.output=ROOT/'work/profile-host/experience46-unified';cls.output.mkdir(parents=True,exist_ok=True)
  choices=[os.environ.get('PROFILE_JSON_JAR',''),str(ROOT/'work/profile-host/json.jar'),str(ROOT/'work/gecko-integration/catalog-json.jar')]
  cls.desktop=next((Path(p) for p in choices if p and Path(p).is_file()),None)
  android=[Path(os.environ.get('PROFILE_ANDROID_JSON_JAR','/nonexistent-profile-android-json')),ROOT/'work/profile-host/android-json.jar',ROOT/'work/gecko-integration/sharing-android-json.jar']
  cls.android=next((p for p in android if p.is_file()),None)
  if cls.desktop is None or cls.android is None:raise RuntimeError('Both existing pinned desktop and Android JSON inputs required')
 def host(self,lane,script,jar,directory=False,java_flag=False):
  name=lane+('-android' if jar==self.android else '-desktop');output=new_attempt(self.output,name)
  target=output if directory else output/'results.json'
  args=[shutil.which('python3') or 'python3',str(ROOT/script)]
  args+=['--java',str(self.java)] if java_flag else ['--java-home',str(self.home)]
  args+=['--json-jar',str(jar),'--output',str(target)]
  try:
   completed=run_recorded(args,output,cwd=ROOT,timeout=180)
   self.assertEqual(completed.returncode,0,'Complete controlled output is retained in CI evidence: '+str(output))
   report=json.loads((target/'results.json' if directory else target).read_text())
   self.assertEqual(report['status'],'passed',report)
   for result in report.get('reports',[report]):
    self.assertEqual(result['status'],'passed',result)
    if 'checks' in result and isinstance(result['checks'],list):self.assertTrue(result['checks'] and all(row['pass'] is True for row in result['checks']),result)
   self.assertIsNot(report.get('actualAndroidExecution'),True)
   return report
  finally:
   emit_evidence(output,HOST_FILES,label=name)
 def test_authority_optional_detection_and_bound_network(self):
  for jar in (self.desktop,self.android):
   for lane,script in [('background-authority','tests/background-reply-policy-host/run.py'),('background-runtime','tests/background-reply-runtime-host/run.py'),('network-configuration','tests/network-configuration-host/run.py')]:
    with self.subTest(lane=lane,jar=jar.name):self.host(lane,script,jar)
 def test_document_bound_guards_and_preserved_network_document(self):
  for jar in (self.desktop,self.android):
   with self.subTest(jar=jar.name):
    args=[shutil.which('python3') or 'python3',str(ROOT/'tests/experience46-guards-host/run.py'),'--java-home',str(self.home),'--json-jar',str(jar)]
    name='session-guards-'+('android' if jar==self.android else 'desktop');output=new_attempt(self.output,name)
    guard_root=ROOT/'work/experience46-guards-host';before=set(guard_root.iterdir())if guard_root.is_dir()else set()
    try:
     result=run_recorded(args,output,cwd=ROOT,timeout=90)
     self.assertEqual(result.returncode,0,'Complete guard output is retained in CI evidence: '+str(output))
     attempt=Path(json.loads(result.stdout)['attempt'])
     self.assertEqual(attempt.parent,guard_root);self.assertNotIn(attempt,before)
     report=json.loads((attempt/'results.json').read_text())
     self.assertEqual(report['status'],'passed',report);self.assertGreaterEqual(report['total'],66);self.assertEqual(report['total'],len(report['checks']));self.assertTrue(all(row['pass'] is True for row in report['checks']));self.assertIsNot(report.get('actualAndroidExecution'),True)
    finally:
     emit_evidence(output,INVOCATION_FILES,label=name)
     fresh=sorted(set(guard_root.iterdir())-before)if guard_root.is_dir()else []
     self.assertLessEqual(len(fresh),8,'Bounded controlled guard attempts required')
     for attempt in fresh:
      if attempt.is_dir():
       names=('0.command.json','0.stdout.log','0.stderr.log','1.command.json','1.stdout.log','1.stderr.log','results.json')
       emit_evidence(attempt,names,label=name+'-'+attempt.name)
 def test_notes_history_transport_and_local_cache(self):
  for jar in (self.desktop,self.android):
   with self.subTest(jar=jar.name):self.host('update-history','tests/update-experience-host/run.py',jar,java_flag=True)
 def test_controlled_download_visual_fixture_cancels_unrelated_worker(self):
  path=ROOT/'tests/ui_visual_preservation_contract.py'
  spec=importlib.util.spec_from_file_location('experience46_visual_preservation',path)
  contract=importlib.util.module_from_spec(spec);spec.loader.exec_module(contract)
  contract.verify_download_visual_fixture_source((ROOT/'tests/gecko/UiVisualIntegrationActivity.java').read_bytes())
 def test_finite_resource_guard_and_disabled_capture(self):
  node=shutil.which('node');self.assertTrue(node)
  module=os.environ.get('JSDOM_MODULE');self.assertTrue(module,'Use existing source-host JSDOM dependency')
  output=new_attempt(self.output,'resource-guard46')
  try:
   run=run_recorded([node,'--test','--test-reporter=tap',str(ROOT/'tests/resource-guard46.cjs')],output,cwd=ROOT,timeout=60)
   (output/'resource-guard46.tap').write_bytes(run.stdout)
   self.assertEqual(run.returncode,0,'Complete TAP output is retained in CI evidence: '+str(output))
   for line in ['# tests 16','# pass 16','# fail 0','# cancelled 0','# skipped 0','# todo 0']:self.assertIn(line.encode(),run.stdout)
   (output/'resource-guard46.json').write_text(json.dumps({'status':'passed','checks':16,'productionSha256':hashlib.sha256((ROOT/'app/src/main/assets/web-reply-observer.js').read_bytes()).hexdigest(),'actualAndroidExecution':False,'actualPhoneExecution':False,'scope':'Production observer with existing synthetic DOM, gesture and timer boundary adapters'},indent=2)+'\n')
  finally:
   emit_evidence(output,('resource-guard46.tap','resource-guard46.json',*INVOCATION_FILES),label='resource-guard46')
if __name__=='__main__':unittest.main(verbosity=2)
