"""Download display fault containment and bounded row work, not device timing."""
import hashlib,importlib.util,json,os,shutil,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];HERE=ROOT/'tests/download-display-host';PROD=ROOT/'app/src/main/java/local/pocketchat'
spec=importlib.util.spec_from_file_location('download38_preservation',ROOT/'tests/download-names-host/run.py');runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
class DownloadDisplayControls(unittest.TestCase):
 def test_source_bound_display_and_snapshot_failure_controls(self):
  java=os.environ.get('PROFILE_JAVA') or shutil.which('java');self.assertTrue(java,'Java17 required');java_home=Path(java).resolve().parents[1]
  candidates=[os.environ.get('PROFILE_JSON_JAR',''),str(ROOT/'work/profile-host/json.jar'),str(ROOT/'work/gecko-integration/catalog-json.jar')];jar=next((Path(p)for p in candidates if p and Path(p).is_file()),None);self.assertIsNotNone(jar,'Existing host JSON dependency required')
  with tempfile.TemporaryDirectory(prefix='profile-download38-')as raw:
   out=Path(raw)
   for script,checks in [('run.py',74),('snapshot.py',14)]:
    result=subprocess.run([shutil.which('python3') or 'python3',str(HERE/script),'--java-home',str(java_home),'--json-jar',str(jar),'--output',str(out/(script+'.json'))],capture_output=True,text=True,timeout=50);self.assertEqual(result.returncode,0,result.stdout+result.stderr);report=json.loads((out/(script+'.json')).read_text());self.assertEqual(report['status'],'passed');self.assertEqual(report['total'],checks);self.assertTrue(all(c['pass'] is True for c in report['checks']));self.assertTrue(report['executionInputsUnchanged']);self.assertIs(report['actualAndroidExecution'],False)
 def test_single_statement_sql_on_real_host_sqlite(self):
  spec=importlib.util.spec_from_file_location('actual_download38_sqlite',HERE/'sql.py');sql=importlib.util.module_from_spec(spec);spec.loader.exec_module(sql);value=sql.run();self.assertEqual(value['status'],'passed');self.assertEqual(value['total'],9);self.assertIs(value['actualHostSqliteExecution'],True);self.assertIs(value['actualAndroidExecution'],False)
 def test_approved_delta_inverts_to_exact_prior31_body(self):
  restored=runner.remove_reviewed38((PROD/'DesignDownloads.java').read_text());self.assertEqual(hashlib.sha256(restored.encode()).hexdigest(),'8433e4cc4c72d8c6ed0b2f141ebcca762a5f357f2acb877a0a19b2814be98ed0')
 def test_changed_approved_delta_is_rejected(self):
  current=runner.remove_reviewed46((PROD/'DesignDownloads.java').read_text());changed=current.replace('row.binding.applied(next);','row.binding.applied(null);',1);self.assertNotEqual(changed,current)
  with self.assertRaisesRegex(AssertionError,'Reviewed38 bounded edit'):runner.remove_reviewed38(changed)
 def test_duplicate_approved_block_is_rejected(self):
  current=runner.remove_reviewed46((PROD/'DesignDownloads.java').read_text());block=json.loads((ROOT/'tests/download-names-host/reviewed38-inverse.json').read_text())['edits'][0]['after'];self.assertEqual(current.count(block),1)
  with self.assertRaisesRegex(AssertionError,'exactly once'):runner.remove_reviewed38(current+block)
 def test_changed_reviewed46_card_delta_is_rejected(self):
  current=(PROD/'DesignDownloads.java').read_text();changed=current.replace('name.setMaxLines(2);','name.setMaxLines(3);',1);self.assertNotEqual(current,changed)
  with self.assertRaisesRegex(AssertionError,'Reviewed46 bounded edit'):runner.remove_reviewed38(changed)
 def test_duplicate_reviewed46_block_is_rejected(self):
  current=(PROD/'DesignDownloads.java').read_text();manifest=json.loads((ROOT/'tests/download-names-host/reviewed46-inverse.json').read_text());block=manifest['files']['DesignDownloads.java']['edits'][0]['after'];self.assertEqual(current.count(block),1)
  with self.assertRaisesRegex(AssertionError,'exactly once'):runner.remove_reviewed38(current+block)
 def test_unrelated_drift_is_preserved_for_original_four_guards(self):
  current=(PROD/'DesignDownloads.java').read_text();mutated=current.replace('package local.pocketchat;','package local.pocketchat;\n// forbidden unrelated change',1);restored=runner.remove_reviewed38(mutated);self.assertIn('// forbidden unrelated change',restored);self.assertNotEqual(hashlib.sha256(restored.encode()).hexdigest(),'8433e4cc4c72d8c6ed0b2f141ebcca762a5f357f2acb877a0a19b2814be98ed0')
 def test_all_original_preservation_conditions_and_case_bodies_remain(self):
  code=(ROOT/'tests/download-names-host/run.py').read_text()
  for name in ['controllerApplyExceptProjectedNameLookup','rowBindExceptSuppliedEnvironmentName','allOtherDownloadUiBytes','allExistingCatalogBytes']:self.assertIn("unchanged['"+name+"']",code)
  self.assertIn('assert all(unchanged.values()),unchanged',code)
  host=(ROOT/'tests/download-names-host/DownloadNamesHost.java.in').read_text();self.assertIn('counts();freshnessAndFallbacks();filteringAndDuplicates();anchors();',host)
if __name__=='__main__':unittest.main()
