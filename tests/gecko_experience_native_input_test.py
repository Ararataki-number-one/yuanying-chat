"""Exercise actual experience binding code with synthetic host artifacts, no device."""
import ast
import contextlib
import copy
import hashlib
import json
import io
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
import zipfile

import gecko_experience_comparison_test as original
from experience_native_input_fixture import add_file, attach_driver, digest, raw
from native_input_signature_fixture import signature_files

M = original.MODULE
ROOT = Path(__file__).resolve().parents[1]


class NativeExperienceTests(unittest.TestCase):
    def setUp(self):
        self.case = original.ComparisonTests(methodName='test_exact_installed_identity_is_required')
        self.case.setUp();self.addCleanup(self.case.doCleanups)
        self.report, self.build, self.protocol = self.case.report, self.case.build, self.case.protocol
        self.directory = Path(self.case.raw.name)

    def actual(self, number=1):
        row=self.report['iterations'][number-1]
        receipt=row['nativeInputDriver']['receipts'][0]
        name='iteration-%02d/'%number+receipt['file']
        return name, M.native_input.decode((self.directory/name).read_bytes()), receipt

    def change_actual(self, change, number=1):
        name,value,receipt=self.actual(number)
        change(value)
        receipt['sha256']=digest(add_file(self.report,self.directory,name,value))

    def verify(self):
        return self.case.verify(self.report)

    def test_every_driver_dependency_is_part_of_the_fixed_protocol(self):
        self.assertEqual(len(M.HARNESS),23);self.assertEqual(len(M.SETUP),14)
        for name in (*M.DRIVER_OBSERVERS,'tools/gecko/build_native_input_driver.py','tools/gecko/VerifyNativeInputSignature.java','tools/gecko/installed_apk_read.py'):
            self.assertIn(name,self.protocol)
            changed=dict(self.protocol);changed[name]='f'*64
            missing=dict(self.protocol);missing.pop(name)
            with self.subTest(name=name):
                with self.assertRaises(ValueError):M.matching_protocol(self.protocol,changed)
                with self.assertRaises(ValueError):M.matching_protocol(missing,missing)

    def test_original_raw_receipts_cannot_be_missing_changed_or_unindexed(self):
        self.verify()
        for entry in list(self.report['rawEvidence']):
            with self.subTest(path=entry['path']):
                saved=self.report['rawEvidence'][:]
                self.report['rawEvidence']=[v for v in saved if v!=entry]
                with self.assertRaises(ValueError):self.verify()
                self.report['rawEvidence']=saved
        name,_,_=self.actual();path=self.directory/name;data=path.read_bytes()
        path.write_bytes(data+b' ')
        with self.assertRaisesRegex(ValueError,'bytes differ'):self.verify()

    def test_role_certificate_apk_source_and_observer_mismatches_fail(self):
        for field,value in [('signerCertificateSha256','e'*64),('driverApkSha256','f'*64),
                            ('targetApkSha256','e'*64),('sourceCommit','f'*40)]:
            name,actual,receipt=self.actual();before=copy.deepcopy(actual)
            self.change_actual(lambda x:x.update({field:value}))
            with self.subTest(field=field),self.assertRaises(ValueError):self.verify()
            receipt['sha256']=digest(add_file(self.report,self.directory,name,before))
        for name in M.DRIVER_OBSERVERS:
            value=self.report['observerFiles'].pop(name)
            with self.subTest(observer=name),self.assertRaises(ValueError):self.verify()
            self.report['observerFiles'][name]=value

    def test_original_build_signature_verifier_must_match_the_fixed_setup(self):
        self.build['nativeInputDriver']['build']['signatureVerifierSourceSha256'] = 'f' * 64
        with self.assertRaisesRegex(ValueError, 'fixed setup'):
            self.verify()

    def test_formal_shell_receipt_rejects_wrong_backend_uid_or_process_identity(self):
        changes = [('executionBackend', 'self-target-instrumentation'), ('executionUid', 10123),
                   ('executionUid', True), ('inputTargetUid', 10124), ('targetUidAfter', 10124),
                   ('targetStartTicksAfter', '201'), ('driverPid', 0), ('driverStartTicks', ''),
                   ('displayId', 1), ('tracePersistence', 'per-event-file')]
        for field, value in changes:
            name, actual, receipt = self.actual()
            self.change_actual(lambda x: x.update({field: value}))
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.verify()
            receipt['sha256'] = digest(add_file(self.report, self.directory, name, actual))

    def test_formal_shell_focus_cannot_be_expected_only_or_change_mid_gesture(self):
        changes = [lambda v: v['focusBefore'].update(raw=''),
                   lambda v: v['focusBefore'].update(raw=v['focusBefore']['raw'].replace('local.pocketchat.test/', 'other.package/')),
                   lambda v: v['focusAfter'].update(packageName='other.package'),
                   lambda v: v['focusAfter'].update(displayId=1)]
        for index, change in enumerate(changes):
            name, actual, receipt = self.actual()
            self.change_actual(change)
            with self.subTest(change=index), self.assertRaises(ValueError):
                self.verify()
            receipt['sha256'] = digest(add_file(self.report, self.directory, name, actual))

    def test_formal_observer_inventory_includes_the_actual_shell_runner_source(self):
        tree = ast.parse((ROOT / 'tests/gecko/run_experience_benchmark.py').read_text())
        declaration = next(node for node in tree.body if isinstance(node, ast.Assign)
                           and any(isinstance(target, ast.Name) and target.id == 'DRIVER_OBSERVERS' for target in node.targets))
        self.assertEqual(ast.literal_eval(declaration.value), M.DRIVER_OBSERVERS)
        name = 'tests/native-input-driver/NativeInputShell.java'
        self.assertIn(name, M.HARNESS)
        self.assertIn(name, M.native_input.INPUTS)
        self.assertTrue((ROOT / name).is_file())

    def test_late_missing_reordered_and_wrong_profile_injections_fail(self):
        changes=[lambda v:v['trace']['events'].pop(), lambda v:v['trace']['events'].reverse(),
                 lambda v:v['trace']['events'][1].update(eventTime=1200,callStartUptimeMs=1200,callEndUptimeMs=1201),
                 lambda v:v['trace'].update(durationMs=300,intervalMs=15,maxLateMs=30),
                 lambda v:v['trace']['events'][-1].update(sync=False),
                 lambda v:v.update(status='failed'),lambda v:v['trace']['events'][4].update(accepted=False)]
        for i,change in enumerate(changes):
            name,actual,receipt=self.actual()
            self.change_actual(change)
            with self.subTest(case=i),self.assertRaises(ValueError):self.verify()
            receipt['sha256']=digest(add_file(self.report,self.directory,name,actual))

    def test_original_fifteen_second_action_budget_cannot_restart_at_ready(self):
        self.report['iterations'][0]['collapseInput']['armed']['expiresUptimeMs']+=5000
        with self.assertRaisesRegex(ValueError,'15-second'):self.verify()

    def test_target_byte_proof_and_already_installed_driver_are_required(self):
        row=self.report['iterations'][0];nonce=row['nativeInputDriver']['nonce']
        name='iteration-01/native-input-setup-'+nonce+'.json'
        value=M.native_input.decode((self.directory/name).read_bytes())
        value['installationRequested']=True;add_file(self.report,self.directory,name,value)
        with self.assertRaisesRegex(ValueError,'without reinstalling'):self.verify()
        value['installationRequested']=False;add_file(self.report,self.directory,name,value)
        row['nativeInputDriver']['receipts'][0]['request']['targetByteProofSha256']='f'*64
        with self.assertRaisesRegex(ValueError,'original role byte proof'):self.verify()

    def test_submission_does_not_replace_the_target_action_up_and_original_event(self):
        action=next(a for a in self.report['iterations'][0]['actions'] if a['name']=='collapse')
        action['inputUpUptimeMs']+=1
        with self.assertRaisesRegex(ValueError,'ACTION_UP'):self.verify()
        action['inputUpUptimeMs']-=1
        name='iteration-01/experienceBenchmark-transport.json'
        entries=M.native_input.decode((self.directory/name).read_bytes())
        entries.pop();add_file(self.report,self.directory,name,entries)
        with self.assertRaisesRegex(ValueError,'target collapse measurement'):self.verify()

    def test_same_phase_reused_proof_rejects_changed_actual_package_metadata(self):
        self.report['predeclaredRepetitions']=2
        self.report['iterations'].append(copy.deepcopy(self.report['iterations'][0]))
        self.report['iterations'][1]['index']=2
        attach_driver(M,self.report,self.build,self.protocol,self.directory)
        self.change_actual(lambda x:x.update(targetLastUpdateBefore=21,targetLastUpdateAfter=21),2)
        with self.assertRaisesRegex(ValueError,'metadata changed'):
            M.verify_report(self.report,self.build,'baseline-1',2,self.protocol,raw_root=self.directory,
                target_proof_sha256=self.report['targetByteProofSha256'])

    def test_automation_startup_is_retained_but_not_promoted_to_app_speed(self):
        summary=M.summarize([self.report])
        self.assertEqual(summary['automation']['driverOnStartToReadyMs']['raw'],[100])
        self.assertEqual(summary['automation']['armedActionToReadyMs']['raw'],[150])
        self.assertEqual(summary['actionToNativeDrawMs']['collapse']['raw'],[20])
        self.assertFalse(any('automation' in key for key in M.deltas(summary,summary)))

    def test_actual_collapse_call_uses_the_armed_deadline_once_even_on_failure(self):
        tree=ast.parse((ROOT/'tests/gecko/run_experience_benchmark.py').read_text())
        function=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='collapse')
        name,value,_=self.actual();filename=Path(name).name
        class Controller:
            calls=[]
            def inject(_,gesture,**kwargs):
                _.calls.append((gesture,kwargs));return {'file':filename,'hostStartedMonotonicNs':1000000,'hostCompletedMonotonicNs':2000000}
            def evidence(_,**kwargs):return {'calls':len(_.calls)}
        controller=Controller();controller.calls=[];row={};saved=[]
        env=dict(first=[100,600],last=[100,200],row=row,controller=controller,
                 directory=self.directory/'iteration-01',native_input=M.native_input,persist=lambda:saved.append(True))
        exec(compile(ast.Module(body=[function],type_ignores=[]),'<actual collapse function>','exec'),env)
        armed=dict(armedUptimeMs=800,expiresUptimeMs=15800)
        env['collapse'](armed)
        self.assertEqual(controller.calls,[({'id':'formal-collapse','x':100,'startY':600,'endY':200},
            {'expires_uptime_ms':15800,'purpose':'formal-collapse'})])
        self.assertEqual(row['collapseInput']['startupMs'],value['startupMs'])
        controller.calls=[]
        def fail(gesture,**kwargs):controller.calls.append(gesture);raise ValueError('actual failed invocation')
        controller.inject=fail
        with self.assertRaisesRegex(ValueError,'failed invocation'):env['collapse'](armed)
        self.assertEqual(len(controller.calls),1);self.assertEqual(len(saved),2)

    def test_each_role_preparation_passes_its_own_source_artifacts_and_certificate(self):
        calls=[]
        def installed(**kw):
            calls.append(kw);selected=self.build['nativeInputDriver']
            kw['out'].mkdir(parents=True)
            (kw['out']/('native-input-setup-'+kw['nonce']+'.json')).write_bytes(raw(dict(
                sourceCommit=kw['expected_source'],nonce=kw['nonce'],installationRequested=True,
                actualInstalledApkRead=True,**{k:selected[k] for k in ('apkSha256','apkBytes','signerCertificateSha256')})))
        with tempfile.TemporaryDirectory() as temp,mock.patch.object(M,'NativeInputDriver',side_effect=installed):
            for i in range(2):
                self.build.update(root=str(Path(temp)/('role%d'%i)),apk='/exact-role-%d.apk'%i,sourceCommit=str(i+1)*40)
                self.build['nativeInputDriver'].update(apk='/exact-driver-%d.apk'%i,receipt='/exact-build-%d.json'%i)
                self.build['nativeInputDriver']['signerCertificateSha256']=str(i+1)*64
                M.prepare_driver(self.build,Path(temp)/str(i),'adb','/original-target-proof.json')
        self.assertEqual(len(calls),2)
        for i,call in enumerate(calls):
            self.assertTrue(call['install']);self.assertEqual(call['expected_source'],str(i+1)*40)
            self.assertEqual(str(call['target_apk']),'/exact-role-%d.apk'%i)
            self.assertEqual(str(call['driver_apk']),'/exact-driver-%d.apk'%i)

    def test_one_untimed_target_read_uses_actual_bytes_and_preserves_original_receipt(self):
        payload=b'actual synthetic readback bytes'
        with tempfile.TemporaryDirectory() as temp:
            build=dict(self.build,root=temp,apkSha256=digest(payload),apkBytes=len(payload))
            calls=[]
            def remote(command,**kwargs):
                calls.append(command)
                return SimpleNamespace(returncode=0,stdout=payload,stderr=b'')
            with mock.patch.object(M.subprocess,'check_output',return_value='package:/data/app/observed/base.apk\n'),\
                 mock.patch.object(M.subprocess,'run',side_effect=remote):
                receipt=M.prepare_target_proof(build,Path(temp)/'phase-proof','adb')
            self.assertEqual(len(calls),1)
            self.assertEqual(calls[0][3:6],['shell','-T','dd'])
            original_bytes=Path(receipt['path']).read_bytes()
            self.assertEqual(digest(original_bytes),receipt['sha256'])
            value=json.loads(original_bytes)
            self.assertEqual(value['status'],'verified-bytes')
            self.assertFalse(value['retryPerformed']);self.assertFalse(value['compiledFileFallback'])
            self.assertEqual(Path(value['destination']).read_bytes(),payload)

    def test_failed_target_read_cannot_retry_or_use_the_compiled_apk(self):
        with tempfile.TemporaryDirectory() as temp:
            build=dict(self.build,root=temp)
            with mock.patch.object(M.subprocess,'check_output',return_value='package:/data/app/observed/base.apk\n'),\
                 mock.patch.object(M.subprocess,'run',return_value=SimpleNamespace(returncode=1,stdout=b'',stderr=b'closed')) as remote:
                with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(ValueError):
                    M.prepare_target_proof(build,Path(temp)/'phase-proof','adb')
            self.assertEqual(remote.call_count,1)
            failed=json.loads((Path(temp)/'phase-proof/installed-target-byte-proof.json').read_bytes())
            self.assertEqual(failed['status'],'failed');self.assertTrue(failed['partialCleaned'])
            self.assertFalse(failed['retryPerformed']);self.assertFalse(failed['compiledFileFallback'])

    def test_driver_restore_requires_both_original_indexed_inputs(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source='a'*40;tree='b'*40
            sources={p:('actual fixture source '+p).encode() for p in (*M.native_input.INPUTS, M.native_input.SIGNATURE_VERIFIER)}
            stamp=copy.deepcopy(self.build['nativeInputDriver']['build'])
            stamp.update(inputs={p:digest(sources[p]) for p in M.native_input.INPUTS},testOnly=True)
            for key in list(stamp):
                if key in ('apkSha256','apkBytes') or key.startswith('signature'): stamp.pop(key)
            apk=root/M.DRIVER_APK;apk.parent.mkdir(parents=True)
            with zipfile.ZipFile(apk,'w') as z:
                z.writestr('assets/native-input-driver-build.json',raw(stamp));z.writestr('classes.dex',b'host fixture only')
            built=dict(stamp,status='built',compileOnly=False,apkSha256=M.sha(apk),apkBytes=apk.stat().st_size,assetSha256=digest(raw(stamp)))
            signing = signature_files(built, digest(sources[M.native_input.SIGNATURE_VERIFIER]))
            for name,value in signing.items():(apk.parent/name).write_bytes(value)
            receipt=root/M.DRIVER_BUILD;receipt.write_bytes(raw(built))
            indexed=(M.DRIVER_APK,M.DRIVER_BUILD,*('work/gecko-integration/'+name for name in signing))
            index=dict(sourceTree=tree,files=[dict(path=n,bytes=(root/n).stat().st_size,sha256=M.sha(root/n)) for n in indexed])
            def selected_source(command,**kw):return sources[command[-1].split(':',1)[1]]
            with mock.patch.object(M.subprocess,'check_output',side_effect=selected_source):
                got=M.driver_identity(root,index,source,'901','1')
                self.assertEqual(got['apkSha256'],M.sha(apk))
                for missing in indexed:
                    incomplete=copy.deepcopy(index);incomplete['files']=[r for r in index['files'] if r['path']!=missing]
                    with self.subTest(missing=missing),self.assertRaisesRegex(ValueError,'Exactly one'):
                        M.driver_identity(root,incomplete,source,'901','1')
                with self.assertRaisesRegex(ValueError,'another original build'):
                    M.driver_identity(root,index,source,'902','1')
                apk.write_bytes(apk.read_bytes()+b'tampered')
                with self.assertRaisesRegex(ValueError,'bytes differ'):M.driver_identity(root,index,source,'901','1')


if __name__=='__main__':unittest.main()
