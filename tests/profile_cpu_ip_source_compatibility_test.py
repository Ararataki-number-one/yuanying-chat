"""Finite CPU-on-IP preparation only; no runtime projection or Android claims."""
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

import cpu_ip_source_compatibility as layer

ROOT=Path(__file__).resolve().parents[1]
SHA=lambda raw:hashlib.sha256(raw).hexdigest()


def git(*args):
    return subprocess.check_output(['git','--no-replace-objects',*args],cwd=ROOT,
        env=dict(os.environ,GIT_NO_LAZY_FETCH='1',GIT_OPTIONAL_LOCKS='0'))


class CpuIpHistoricalPreparation(unittest.TestCase):
    def test_complete_real_candidate_before_forward_and_inverse(self):
        self.assertEqual(git('rev-parse',layer.BASE_COMMIT+'^{tree}').decode().strip(),layer.BASE_TREE)
        value=layer.manifest();self.assertEqual(len(value['files']),2)
        self.assertEqual(sum(len(row['deltas']) for row in value['files'].values()),9)
        for relative,row in value['files'].items():
            before=git('show',layer.BASE_COMMIT+':'+relative);after=(ROOT/relative).read_bytes()
            self.assertEqual((SHA(before),len(before)),(row['previousSha256'],row['previousBytes']))
            self.assertEqual((SHA(after),len(after)),(row['reviewedSha256'],row['reviewedBytes']))
            self.assertEqual(layer.source_input(before,relative),before)
            self.assertEqual(layer.source_input(after,relative),before)
            forward=before
            for item in row['deltas']:
                old,new=item['previous'].encode(),item['current'].encode()
                self.assertEqual(forward.count(old),1);forward=forward.replace(old,new,1)
            self.assertEqual(forward,after)

    def test_every_missing_duplicate_changed_moved_truncated_and_unknown_input_rejects(self):
        rejected=0
        for relative,row in layer.manifest()['files'].items():
            after=(ROOT/relative).read_bytes()
            for delta in row['deltas']:
                part=delta['current'].encode();self.assertEqual(after.count(part),1)
                removed=after.replace(part,b'',1);moved=removed+part
                if moved==after:moved=part+removed
                for raw in (removed,after.replace(part,part+part,1),after.replace(part,part+b' ',1),moved,after[:-1],b'/* unknown */\n'+after):
                    with self.assertRaises(ValueError):layer.source_input(raw,relative)
                    rejected+=1
        self.assertEqual(rejected,54)

    def test_only_exact_complete_bytes_and_owned_paths_are_admitted(self):
        relative=next(iter(layer.PATHS));raw=(ROOT/relative).read_bytes()
        for bad in (None,'source',bytearray(raw),raw[:100]):
            with self.assertRaises(ValueError):layer.source_input(bad,relative)
        for bad in (None,Path(relative),'/'+relative,'./'+relative,'app/src/main/java/local/pocketchat/MainActivity.java'):
            with self.assertRaises(ValueError):layer.source_input(raw,bad)

    def test_fixture_whole_pin_type_duplicates_and_bound(self):
        raw=layer.DELTA_PATH.read_bytes()
        for bad in (raw+b'\n',b' '+raw,raw[:-1],None,raw.decode(),b'x'*(layer.MAX_FIXTURE_BYTES+1)):
            with self.assertRaises(ValueError):layer._decode(bad)
        duplicate=raw.replace(b'"schema": 1',b'"schema": 1, "schema": 1',1)
        with patch.object(layer,'DELTA_SHA256',SHA(duplicate)),self.assertRaises(ValueError):layer._decode(duplicate)

    def test_counterfeit_metadata_or_oracle_members_reject_even_with_rebound_outer_pin(self):
        original=json.loads(layer.DELTA_PATH.read_bytes());relative=next(iter(layer.PATHS))
        mutations=[]
        for key,value in (('schema',True),('baseCommit','0'*40),('baseTree','0'*40),('actualAndroidExecution',True),('runtimeAcceptance',True),('oracle','replacement')):
            current=copy.deepcopy(original);current[key]=value;mutations.append(current)
        for key,value in (('previousBytes',True),('reviewedBytes',131073),('contextLines',2),('reviewedSha256','x'*64),('oracle','replacement')):
            current=copy.deepcopy(original);current['files'][relative][key]=value;mutations.append(current)
        current=copy.deepcopy(original);current['files']['unexpected.java']=current['files'][relative];mutations.append(current)
        current=copy.deepcopy(original);current['files'][relative]['deltas'][0]['current']+='corruption';mutations.append(current)
        for value in mutations:
            raw=json.dumps(value).encode()
            with patch.object(layer,'DELTA_SHA256',SHA(raw)),self.assertRaises(ValueError):layer._decode(raw)
        self.assertEqual(len(mutations),13)

    def test_real_fixture_symlink_and_foreign_path_reject(self):
        with tempfile.TemporaryDirectory(prefix='cpu-ip-history-') as temporary:
            root=Path(temporary);target=root/'original';target.write_bytes(layer.DELTA_PATH.read_bytes())
            path=root/'tests/fixtures/cpu-ip-source-deltas.json';path.parent.mkdir(parents=True);path.symlink_to(target)
            with patch.object(layer,'ROOT',root),patch.object(layer,'DELTA_PATH',path),self.assertRaises(ValueError):layer.manifest()
        with patch.object(layer,'DELTA_PATH',ROOT/'tests/fixtures/unreviewed.json'),self.assertRaises(ValueError):layer.manifest()

    def test_focused_pin_and_duplicate_guard_counterfeits_fail_the_same_original_checks(self):
        source=(ROOT/'tests/cpu_ip_source_compatibility.py').read_text();raw=layer.DELTA_PATH.read_bytes()
        changed=raw+b'\n';needle=' or _sha(raw) != DELTA_SHA256';self.assertEqual(source.count(needle),1)
        namespace={'__file__':str(ROOT/'tests/cpu_ip_source_compatibility.py'),'__name__':'cpu_ip_counterfeit'}
        exec(compile(source.replace(needle,'',1),'<pin counterfeit>','exec'),namespace)
        def original_pin_check(decode):
            with self.assertRaises(ValueError):decode(changed)
        original_pin_check(layer._decode)
        with self.assertRaises(AssertionError):original_pin_check(namespace['_decode'])
        duplicate=raw.replace(b'"schema": 1',b'"schema": 1, "schema": 1',1)
        namespace={'__file__':str(ROOT/'tests/cpu_ip_source_compatibility.py'),'__name__':'cpu_ip_counterfeit'}
        exec(compile(source.replace('json.loads(raw, object_pairs_hook=_unique)','json.loads(raw)',1),'<duplicate counterfeit>','exec'),namespace)
        namespace['DELTA_SHA256']=SHA(duplicate)
        with patch.object(layer,'DELTA_SHA256',SHA(duplicate)),self.assertRaises(ValueError):layer._decode(duplicate)
        with self.assertRaises(AssertionError):
            with self.assertRaises(ValueError):namespace['_decode'](duplicate)

    def test_all_original_fixtures_and_preexisting_test_assertions_remain_whole_bytes(self):
        fixtures=git('ls-tree','-r','--name-only',layer.BASE_COMMIT,'tests/fixtures').decode().splitlines()
        tests=('tests/browser_acceptance_workflow_test.py','tests/browser_environment_publish_gate_test.py',
            'tests/browser_fingerprint_publish_gate_test.py','tests/gecko-addon-lifecycle-host/AddonHost.java.in',
            'tests/gecko-addon-lifecycle-host/run.py','tests/native-protection-host/NativeProtectionControllerHost.java.in',
            'tests/native-runtime-capabilities-host/NativeRuntimeCapabilitiesHost.java','tests/profile_dual_browser_source_compatibility_test.py',
            'tests/profile_native_protection_test.py','tests/profile_worker_timezone_host_source_compatibility_test.py',
            'tests/profile_worker_timezone_source_compatibility_test.py','tests/review-host/run_identity_controller_host.py',
            'tests/worker_timezone_host_source_compatibility.py','tests/worker_timezone_source_compatibility.py')
        for relative in [*fixtures,*tests]:
            with self.subTest(path=relative):self.assertEqual((ROOT/relative).read_bytes(),git('show',layer.BASE_COMMIT+':'+relative))

    def test_ip_desired_native_controller_parser_and_guard_assets_remain_verbatim(self):
        paths=['app/src/main/java/local/pocketchat/'+name+'.java' for name in ('GeckoTimeZoneSpec','GeckoTimeZoneStore',
            'GeckoTimeZoneController','GeckoTimeZonePolicy','GeckoTimeZoneUi','GeckoIpTimeZonePolicy','GeckoIpRouteWatch','GeckoPopupNavigationUi')]
        paths+=['app/src/main/assets/gecko/'+name for name in ('background.js','ip-timezone-bootstrap.js','request-headers.js','native-timezone-api.js','native-timezone-bridge.js')]
        for relative in paths:
            with self.subTest(path=relative):self.assertEqual((ROOT/relative).read_bytes(),git('show',layer.BASE_COMMIT+':'+relative))

    def test_no_runtime_or_behavior_consumer_imports_this_historical_layer(self):
        for folder in ('app','tools','tests/gecko-cpu-host','tests/gecko-cpu-controller-host','tests/gecko-cpu-ui-host','tests/gecko-ip-transport-host'):
            for path in (ROOT/folder).rglob('*.py'):
                for node in ast.walk(ast.parse(path.read_text())):
                    if isinstance(node,ast.ImportFrom):self.assertNotEqual(node.module,'cpu_ip_source_compatibility',str(path))
                    elif isinstance(node,ast.Import):self.assertNotIn('cpu_ip_source_compatibility',[entry.name for entry in node.names],str(path))


if __name__=='__main__':unittest.main(verbosity=2)
