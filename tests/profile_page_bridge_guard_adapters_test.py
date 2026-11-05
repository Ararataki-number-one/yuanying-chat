"""Current bridge mutation fragments, actual raw production behavior, no source view."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import unittest
import page_bridge_guard_adapters as adapter
ROOT=Path(__file__).resolve().parents[1]
VIEW=ROOT/'app/src/main/java/local/pocketchat/GeckoWebView.java'
def original_pairs():
 tree=ast.parse((ROOT/'tests/page_bridge42_source_compatibility.py').read_text())
 return next(ast.literal_eval(n.value)for n in tree.body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='DELTAS'for t in n.targets))
def runtime():
 spec=importlib.util.spec_from_file_location('current_bridge_mutation_execution',ROOT/'tests/profile_page_bridge_lifecycle_test.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
class CurrentBridgeGuardAdapters(unittest.TestCase):
 def test_original_four_guard_semantics_bind_current_audit_budget_without_old_image(self):
  raw=VIEW.read_bytes();old=original_pairs();pairs=adapter.current_deltas(raw,old)
  self.assertEqual(pairs[:3],old[:3]);self.assertEqual(len(pairs),4)
  self.assertEqual(raw.count(old[3][1]),0) # Reproduce the original no-op mutation trigger.
  before,current=pairs[3];self.assertEqual(raw.count(current),1)
  self.assertEqual(current.replace(b'||staleAppearanceConnections.contains(port)',b'',1),before)
  for unchanged in (b'int budget=14000;',b'if(configuration==null){callback.onReceiveValue("null");return;}',b'configuration.has("budgetMillis")',b'((Number)value).longValue()>14000'):
   self.assertIn(unchanged,current);self.assertIn(unchanged,before)
  mutant=raw.replace(current,before,1);self.assertNotEqual(mutant,raw)
  self.assertEqual(mutant,raw.replace(b'if(destroyed||port==null||staleAppearanceConnections.contains(port)){callback.onReceiveValue("null");return;}',b'if(destroyed||port==null){callback.onReceiveValue("null");return;}',1))
 def test_actual_current_method_and_single_stale_guard_mutant_have_distinct_observable_results(self):
  host=runtime();raw=VIEW.read_bytes();before,after=adapter.current_deltas(raw,original_pairs())[3]
  current=host.execute();mutant=host.execute(raw.replace(after,before,1).decode())
  self.assertEqual((current['status'],current['passed'],current['total']),('passed',32,32))
  self.assertEqual((mutant['status'],mutant['passed'],mutant['total']),('failed',31,32))
  # This controlled host historically puts java.util.List into JSONObject.
  # Desktop JSON wraps it; the old Android JSON renders its JSON object list
  # as a string. Decode only that host metadata, never production evidence.
  checks=json.loads(mutant['checks']) if type(mutant['checks'])is str else mutant['checks']
  self.assertIs(type(checks),list);self.assertEqual(len(checks),32)
  self.assertTrue(all(type(row)is dict and set(row)=={'name','passed'} and type(row['name'])is str and type(row['passed'])is bool for row in checks))
  self.assertEqual([row['name']for row in checks if row['passed']is False],['Audit is unavailable rather than dispatched to the retired document'])
  self.assertTrue(current['executionInputsUnchanged']);self.assertTrue(mutant['executionInputsUnchanged']);self.assertTrue(mutant['injectedCounterexample'])
  self.assertNotEqual(current['executedViewSha256'],mutant['executedViewSha256'])
  report=dict(schema=1,status='passed',current=current,staleGuardCounterexample=mutant,actualAndroidExecution=False,actualGeckoExecution=False,historicalRuntimeProjection=False,hostCheckListSerialization='Explicit legacy Android JSON collection-string versus desktop array boundary; raw output retained',scope='Actual current members compile unchanged; only the actual stale-port predicate is removed. New audit budget/null contract remains byte-identical in both source inputs. Explicit SDK/Android/default-timezone boundaries are inherited and not native proof.')
  output=Path(os.environ.get('PAGE_BRIDGE_GUARD_REPORT',ROOT/'work/page-bridge-guard-adapters/results.json'));output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2)+'\n')
 def test_missing_duplicated_mutated_partial_methods_and_changed_old_pairs_reject(self):
  raw=VIEW.read_bytes();old=original_pairs();method=adapter.AUDIT_METHOD
  for bad in (None,raw.decode(),bytearray(raw),raw[:120],method,raw+method,raw.replace(method,b'',1),raw.replace(b'int budget=14000;',b'int budget=20000;',1),raw.replace(b'if(configuration==null)',b'if(false)',1)):
   with self.subTest(kind=type(bad).__name__),self.assertRaises(ValueError):adapter.current_deltas(bad,old)
  changed=list(old);changed[3]=(old[3][0],old[3][1]+b' ')
  for bad in (None,list(old),tuple(changed),old[:3]):
   with self.assertRaises(ValueError):adapter.current_deltas(raw,bad)
if __name__=='__main__':unittest.main(verbosity=2)
