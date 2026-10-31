"""Recover exact old runner oracles before their original trace/readiness checks.

Only the existing reviewed46 whole-byte inverse is used. The actual runner,
trace/window manifests, old oracles, input workloads and device timeouts stay put.
"""
import ast
import hashlib
from pathlib import Path
import unittest

from experience46_source_compatibility import experience46_source_bytes, manifest46
from reading_zoom_trace_contract import original_reading_fixture_bytes, strip_reviewed_reading_trace_additions

ROOT=Path(__file__).resolve().parents[1]
RUNNER='tests/gecko/run_device.py'
FORMAL45='54fa412be9f89e46d61597caf61b0246e451e6c9b5eebca592e36b05686ab8a6'
ORIGINAL_TRACE='019bc8e8b8e61def3d6fe87fe70d9eb7a87a3a556d86b921489331f9f4757e5d'


class Experience46RunnerCompatibility(unittest.TestCase):
 def test_original_ast_consumer_strip_stays_byte_exact_and_whole_guard_stays_strict(self):
  contract=(ROOT/'tests/reading_zoom_trace_contract.py').read_text()
  method=next(node for node in ast.parse(contract).body if isinstance(node,ast.FunctionDef) and node.name=='strip_reviewed_reading_trace_additions')
  self.assertEqual(hashlib.sha256(ast.get_source_segment(contract,method).encode()).hexdigest(),'841c1c873318240ca844661b5e28e2ba188438db6b319a68ef6ae7af50b6ab1b')
  source=(ROOT/RUNNER).read_text()
  formatted='# harmless comment\n'+source.replace("action=='downloadResume'",'action == "downloadResume"')
  self.assertIn('# harmless comment',strip_reviewed_reading_trace_additions(formatted.encode(),RUNNER).decode())
  with self.assertRaises(ValueError):original_reading_fixture_bytes(formatted.encode(),RUNNER)

 def test_existing_exact_inverse_and_original_trace_oracle_both_hold(self):
  current=(ROOT/RUNNER).read_bytes()
  previous=experience46_source_bytes(current,RUNNER)
  self.assertEqual(hashlib.sha256(previous).hexdigest(),FORMAL45)
  original=original_reading_fixture_bytes(current,RUNNER)
  self.assertEqual(hashlib.sha256(original).hexdigest(),ORIGINAL_TRACE)
  self.assertEqual(original_reading_fixture_bytes(previous,RUNNER),original)
  self.assertEqual(original_reading_fixture_bytes(original,RUNNER),original)

 def test_each_history_label_or_position_mutation_still_rejects_whole_source(self):
  source=(ROOT/RUNNER).read_text()
  history="        history_experience=update('historyExperience');assert history_experience['status']=='passed' and history_experience['actualAndroidExecution'] is True and history_experience['checks'] and all(row['pass'] is True for row in history_experience['checks']),history_experience\n        report['releaseHistoryExperience']=history_experience\n"
  label="for label in ['应用更新','当前安装版本','安装更新','删除安装包','自动检查更新','Wi-Fi 下自动下载新版']"
  self.assertEqual(source.count(history),1);self.assertEqual(source.count(label),1)
  changes={
   'missing-history':source.replace(history,'',1),
   'duplicate-history':source.replace(history,history*2,1),
   'changed-history':source.replace("history_experience['actualAndroidExecution'] is True","history_experience['actualAndroidExecution'] is False",1),
   'relocated-history':source.replace(history,'',1)+history,
   'missing-label':source.replace(label,label.replace('当前安装版本','当前版本'),1),
   'duplicate-label':source.replace(label,label+label,1),
   'changed-label':source.replace(label,label.replace('当前安装版本','安装版本'),1),
   'relocated-label':source.replace(label,'for label in []',1)+label,
  }
  for name,candidate in changes.items():
   with self.subTest(mutation=name):
    self.assertNotEqual(candidate,source)
    for guard in (lambda:experience46_source_bytes(candidate.encode(),RUNNER),lambda:original_reading_fixture_bytes(candidate.encode(),RUNNER)):
     with self.assertRaises(ValueError):guard()

 def test_update_scroll_call_and_original_installer_steps_cannot_be_bypassed(self):
  source=(ROOT/RUNNER).read_text()
  call="        update_ui,update_scroll=scan_update_controls(adb,update_ui,lambda name,xml:(OUT/name).write_text(xml),package)\n"
  self.assertEqual(source.count(call),1)
  originals=["button=next(node for node in ET.fromstring(update_ui).iter('node') if node.attrib.get('text')=='安装更新')",
   "adb('shell','input','tap',str((x1+x2)//2),str((y1+y2)//2));time.sleep(3)",
   "assert 'packageinstaller' in installer_ui and ('Update' in installer_ui or '更新' in installer_ui),installer_ui"]
  for statement in originals:self.assertEqual(source.count(statement),1)
  changes=[source.replace(call,'',1),source.replace(call,call*2,1),source.replace(call,call.replace('scan_update_controls(adb,','scan_update_controls(None,'),1),
   source.replace(call,call.replace('(OUT/name).write_text(xml)','None'),1),
   source.replace("assert label in update_scroll['labelsSeen']","assert True or label in update_scroll['labelsSeen']",1)]
  changes.extend(source.replace(statement,statement+';pass',1) for statement in originals)
  for candidate in changes:
   self.assertNotEqual(candidate,source)
   with self.assertRaises(ValueError):experience46_source_bytes(candidate.encode(),RUNNER)
   with self.assertRaises(ValueError):original_reading_fixture_bytes(candidate.encode(),RUNNER)

 def test_unrelated_workload_timeout_and_unknown_path_remain_rejected(self):
  source=(ROOT/RUNNER).read_text()
  for old,new in [('deadline=time.monotonic()+120','deadline=time.monotonic()+121'),("update('showUi');time.sleep(1)","update('showUi');time.sleep(2)"),("history_experience=update('historyExperience')","history_experience=update('showUi')")]:
   self.assertIn(old,source)
   candidate=source.replace(old,new,1).encode()
   with self.subTest(mutation=old),self.assertRaises(ValueError):original_reading_fixture_bytes(candidate,RUNNER)
  with self.assertRaises(ValueError):experience46_source_bytes((ROOT/RUNNER).read_bytes(),RUNNER+'.other')
  row=manifest46()['files'][RUNNER]
  self.assertEqual(row['previousSha256'],FORMAL45)
  self.assertEqual(len(row['deltas']),1)


if __name__=='__main__':unittest.main()
