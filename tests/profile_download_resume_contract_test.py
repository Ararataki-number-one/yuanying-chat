"""Synthetic receipt mutations, never evidence that Android cases executed."""
import importlib.util
import ast
import copy
import hashlib
import json
from pathlib import Path
import sys
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/gecko'))
import integration_event_contract as transfer
spec = importlib.util.spec_from_file_location('download_resume_contract', ROOT/'tools/gecko/download_resume_contract.py')
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)


def metadata():
    ids = [f'00000000-0000-0000-0000-{n:012d}' for n in range(1, 7)]
    http = []
    for code, task in zip((206, 200), ids):
        expected = list(range(1, 10)) if code == 206 else list(range(5, 10))
        http.append(dict(code=code, mappedFrom='https://download-fixture.example/'+task+'.bin',
                         mappedTo='http://127.0.0.1:12345/owned.bin', request='GET /owned.bin HTTP/1.1',
                         method='GET', range='bytes=4-', ifRange='"f06-v1"', responseBytes=5,
                         expectedBytes=len(expected), savedBytes=len(expected),
                         expectedSha256=contract.sha(expected), savedSha256=contract.sha(expected),
                         afterRetireSha256=contract.sha(expected), indexedAfterRetire=True,
                         taskIdBefore=task, taskIdAfter=task, state='saved', uri='content://media/external/downloads/1', sourcePartialExists=False))
    return dict(schema=1, status='passed', actualAndroidExecution=True, actualAdbTouchExecution=False,
                actualDialogPerformClick=True, ownedCleanupCompleted=True, processSlot=7,
                syntheticCookieReads=[dict(runNonce='a'*32,processSlot=7,taskId=row['taskIdBefore'],url=row['mappedFrom'],ticket=1,emptyCookie=True,realCookieBridge=False) for row in http],
                filePrepareCallbacks=2, runNonce='a'*32,
                buildIdentity=dict(schema=1, package='local.pocketchat.test', dirtySource=False,
                                   sdkCoordinate=transfer.SDK_COORDINATE, apkBytes=100,
                                   sourceCommit='a'*40, sourceTree='b'*40, apkSha256='c'*64,
                                   buildStampSha256='d'*64, version='2.0.18', versionCode=71),
                checkCount=len(contract.CHECK_NAMES), checks=[dict(name=name, **{'pass': True}) for name in contract.CHECK_NAMES],
                menus=[dict(label=label, performClick=True) for label in contract.MENU_LABELS], http=http,
                retirement=dict(oldTaskId=ids[2], newTaskId=ids[3], selectedAbsent=True,
                                otherBytesSha256=contract.sha([21, 22]), oldState='cancelled', oldUri='', retiredMarker='', nextState='saved'),
                writer=dict(taskId=ids[4], generation=ids[5], taskIdAfterLateMenu=ids[4], generationAfterLateMenu=ids[5],
                            oldTicket=1, oldTicketAfterDestroy=2, waitedInsideLease=True,
                            workerStack=['local.pocketchat.SealedFileIo.lease(SealedFileIo.java:20)',
                                         'java.util.concurrent.locks.ReentrantLock.lockInterruptibly(ReentrantLock.java:30)'],
                            beforeBytesSha256=contract.sha([7, 7, 7, 7]), lateBytesReturned=True,
                            partialExistsAfter=False, uriAfter='', retiredMarkerAfter='', retiringAfter=False,
                            lateCallbackUnchanged=True, lateMenuPerformClick=True, completeCopySha256=contract.sha([41, 42, 43])))


def bound_metadata():
    value=metadata();identity=copy.deepcopy(value['buildIdentity'])
    event=dict(kind='downloadResume',result=copy.deepcopy(value),nativeContext='environment-8',processSlot=7)
    envelope=dict(schema=1,sourceCommit=identity['sourceCommit'],buildIdentity=identity,runNonce=value['runNonce'],
                  fixtureAction='downloadResume',command=1,sequence=1,nativeContext='environment-8',processSlot=7,event=event)
    raw=json.dumps(envelope,ensure_ascii=False,separators=(',',':'))+'\n'
    receipt={key:envelope[key] for key in ('schema','runNonce','fixtureAction','command','sequence','nativeContext','processSlot')}
    receipt.update(kind='eventReceipt',eventKind='downloadResume',payloadBytes=len(raw.encode()),payloadSha256=hashlib.sha256(raw.encode()).hexdigest())
    return dict(savedFileDeletion=dict(downloadResume=value),steps=[event],eventTransport=dict(schema=1,buildIdentity=identity,
        invocations=[dict(fixtureAction='downloadResume',runNonce=value['runNonce'],processSlot=7,events=[dict(receipt=receipt,rawUtf8=raw)])]))


class DownloadResumeContractTest(unittest.TestCase):
    def reject(self, edit):
        report=metadata();edit(report)
        with self.assertRaises(ValueError):
            contract.verify_download_resume(report)

    def test_missing_or_extra_synthetic_cookie_callbacks_are_rejected(self):
        self.reject(lambda r:r.pop('syntheticCookieReads'))
        for rows in ([],[{}],[{}, {}, {}]):self.reject(lambda r:r.update(syntheticCookieReads=rows))

    def test_synthetic_cookie_callback_owner_and_url_are_exact(self):
        for key,value in (('runNonce','b'*32),('processSlot',1),('taskId','foreign'),('url','https://foreign.example/')):
            self.reject(lambda r:r['syntheticCookieReads'][0].update({key:value}))
        self.reject(lambda r:r['syntheticCookieReads'].reverse())

    def test_synthetic_cookie_callback_scope_and_types_cannot_be_forged(self):
        for key,values in (('emptyCookie',(False,1,'true')),('realCookieBridge',(True,0,'false')),('ticket',(0,-1,True,1.0,'1')),('processSlot',(True,7.0,'7'))):
            for value in values:self.reject(lambda r:r['syntheticCookieReads'][0].update({key:value}))
        self.reject(lambda r:r['syntheticCookieReads'][0].update(secret='unexpected'))

    def test_complete_synthetic_metadata(self):
        report=metadata()
        self.assertEqual(contract.verify_download_resume(report, report['buildIdentity']),
                         dict(checks=20, httpCases=2, dialogCallbacks=7, actualAndroidExecution=True))

    def test_source_and_apk_are_bound_to_invocation(self):
        for key in ('sourceCommit', 'sourceTree', 'apkSha256', 'buildStampSha256'):
            report=metadata();identity=dict(report['buildIdentity']);identity[key]='f'*len(identity[key])
            with self.subTest(key=key), self.assertRaises(ValueError):
                contract.verify_download_resume(report,identity)
        with self.assertRaises(ValueError):
            contract.verify_download_resume(metadata(),expected_source='f'*40)

    def test_every_original_new_case_is_required_exactly_once_in_order(self):
        self.reject(lambda r:r['checks'].reverse())
        for index in range(20):
            with self.subTest(index=index):
                self.reject(lambda r:r['checks'].pop(index))
                self.reject(lambda r:r['checks'][index].update(name='replacement'))
                self.reject(lambda r:r['checks'][index].update({'pass':1}))

    def test_failed_status_or_cleanup_cannot_hide_behind_checks(self):
        self.reject(lambda r:r.update(status='failed'))
        self.reject(lambda r:r.update(error='read failed'))
        self.reject(lambda r:r.update(cleanupError='owned files remain'))
        self.reject(lambda r:r.update(ownedCleanupCompleted=False))

    def test_boolean_and_integer_types_are_strict(self):
        for key in ('actualAndroidExecution','actualDialogPerformClick','ownedCleanupCompleted'):
            for value in (False,1,'true',None):
                with self.subTest(key=key,value=value):self.reject(lambda r:r.update({key:value}))
        for key in ('schema','processSlot','filePrepareCallbacks','checkCount'):
            for value in (True,1.0,'1',None):
                with self.subTest(key=key,value=value):self.reject(lambda r:r.update({key:value}))

    def test_perform_click_cannot_claim_adb_touch(self):
        self.reject(lambda r:r.update(actualAdbTouchExecution=True))
        self.reject(lambda r:r['menus'][0].update(performClick=1))

    def test_real_menu_sequence_is_required(self):
        for index in range(7):
            self.reject(lambda r:r['menus'].pop(index))
            self.reject(lambda r:r['menus'][index].update(label='继续'))

    def test_both_http_cases_and_exact_request_are_required(self):
        self.reject(lambda r:r['http'].reverse())
        self.reject(lambda r:r['http'].pop())
        for key,value in [('code',True),('method','POST'),('request','GET /foreign HTTP/1.1'),
                          ('range','bytes=0-'),('ifRange','"old-version"'),('responseBytes',True)]:
            self.reject(lambda r:r['http'][0].update({key:value}))

    def test_network_mapping_is_explicit_and_loopback_only(self):
        for key,value in [('mappedFrom','https://chatgpt.com/file'),('mappedTo','https://example.com/owned.bin'),
                          ('mappedTo','http://127.0.0.1:65536/owned.bin'),('mappedTo','http://localhost:42/owned.bin')]:
            self.reject(lambda r:r['http'][0].update({key:value}))

    def test_copied_hashes_cannot_make_wrong_bytes_pass(self):
        for index in (0,1):
            for key in ('expectedSha256','savedSha256','afterRetireSha256'):
                self.reject(lambda r:r['http'][index].update({key:contract.sha([0])}))
            for key in ('expectedBytes','savedBytes'):
                self.reject(lambda r:r['http'][index].update({key:5 if index==0 else 9}))

    def test_continuation_must_retain_task_and_real_saved_target(self):
        for key,value in [('taskIdAfter','bad'),('state','paused'),('uri','file:///tmp/file'),
                          ('sourcePartialExists',True),('indexedAfterRetire',False)]:
            self.reject(lambda r:r['http'][0].update({key:value}))

    def test_next_web_response_cannot_reuse_retired_task(self):
        self.reject(lambda r:r['retirement'].update(newTaskId=r['retirement']['oldTaskId']))
        for key,value in [('selectedAbsent',False),('otherBytesSha256',contract.sha([])),
                          ('oldUri','content://media/1'),('retiredMarker','download-x.part'),('nextState','paused')]:
            self.reject(lambda r:r['retirement'].update({key:value}))

    def test_late_menu_must_preserve_both_generation_and_task(self):
        self.reject(lambda r:r['writer'].update(lateMenuPerformClick=False))
        self.reject(lambda r:r['writer'].update(generationAfterLateMenu=r['writer']['taskId']))
        self.reject(lambda r:r['writer'].update(taskIdAfterLateMenu=r['writer']['generation']))

    def test_writer_barrier_requires_real_lease_and_interruptible_lock_stack(self):
        self.reject(lambda r:r['writer'].update(waitedInsideLease=False))
        for index in (0,1):self.reject(lambda r:r['writer']['workerStack'].pop(index))
        self.reject(lambda r:r['writer'].update(workerStack=['fixture waited']))

    def test_writer_must_actually_return_late_bytes_after_invalidation(self):
        self.reject(lambda r:r['writer'].update(lateBytesReturned=False))
        self.reject(lambda r:r['writer'].update(oldTicketAfterDestroy=1))
        self.reject(lambda r:r['writer'].update(oldTicket=True))

    def test_no_reappearance_or_new_uri_can_pass(self):
        for key,value in [('partialExistsAfter',True),('retiringAfter',True),('uriAfter','content://media/2'),
                          ('retiredMarkerAfter','download-x.part'),('lateCallbackUnchanged',False)]:
            self.reject(lambda r:r['writer'].update({key:value}))

    def test_complete_copy_and_before_bytes_are_independently_required(self):
        for key in ('beforeBytesSha256','completeCopySha256'):
            self.reject(lambda r:r['writer'].update({key:contract.sha([])}))

    def test_missing_raw_structures_are_not_optional(self):
        for key in ('buildIdentity','runNonce','http','menus','retirement','writer'):
            self.reject(lambda r:r.pop(key))

    def bound_reject(self,edit):
        device=bound_metadata();edit(device)
        with self.assertRaises(ValueError):contract.verify_download_resume_invocation(device,'a'*40)

    def test_complete_original_invocation_round_trip(self):
        self.assertEqual(contract.verify_download_resume_invocation(bound_metadata(),'a'*40)['checks'],20)

    def test_original_raw_and_step_are_mandatory(self):
        for key in ('eventTransport','steps'):
            self.bound_reject(lambda d:d.pop(key))
        self.bound_reject(lambda d:d['eventTransport']['invocations'][0].update(events=[]))
        self.bound_reject(lambda d:d['eventTransport']['invocations'][0]['events'][0].pop('rawUtf8'))

    def test_duplicate_or_changed_invocation_rejected(self):
        self.bound_reject(lambda d:d['eventTransport']['invocations'].append(copy.deepcopy(d['eventTransport']['invocations'][0])))
        for key,value in [('runNonce','f'*32),('fixtureAction','read'),('processSlot',0)]:
            self.bound_reject(lambda d:d['eventTransport']['invocations'][0].update({key:value}))

    def test_raw_receipt_cannot_be_replaced_or_reordered(self):
        self.bound_reject(lambda d:d['eventTransport']['invocations'][0]['events'][0].update(rawUtf8='{}'))
        for key,value in [('sequence',2),('command',2),('runNonce','f'*32),('eventKind','fixture'),('payloadSha256','0'*64)]:
            self.bound_reject(lambda d:d['eventTransport']['invocations'][0]['events'][0]['receipt'].update({key:value}))

    def test_same_source_other_apk_or_nonce_summary_rejected(self):
        for key,value in [('apkSha256','f'*64),('sourceTree','f'*40),('schema',True)]:
            self.bound_reject(lambda d:d['savedFileDeletion']['downloadResume']['buildIdentity'].update({key:value}))
        self.bound_reject(lambda d:d['savedFileDeletion']['downloadResume'].update(runNonce='f'*32))

    def test_summary_and_step_copies_must_equal_actual_raw(self):
        self.bound_reject(lambda d:d['savedFileDeletion']['downloadResume'].update(scope='foreign extra data'))
        self.bound_reject(lambda d:d['steps'][0]['result'].update(scope='changed raw copy'))
        self.bound_reject(lambda d:d['steps'].append(copy.deepcopy(d['steps'][0])))

    def test_slot7_transport_only_accepts_exact_file_action_and_event(self):
        device=bound_metadata();record=device['eventTransport']['invocations'][0]['events'][0]
        receipt=record['receipt'];raw=record['rawUtf8'].encode();identity=device['eventTransport']['buildIdentity']
        self.assertIn('/gecko-events/7/',transfer.event_uri(receipt))
        self.assertEqual(transfer.decode_event(receipt,raw,identity=identity,nonce='a'*32,slot=7,action='downloadResume',command=1),device['steps'][0])
        for slot,action in ((7,'read'),(2,'downloadResume'),(6,'downloadResume'),(True,'downloadResume')):
            with self.subTest(slot=slot,action=action),self.assertRaises(ValueError):
                transfer.decode_event(receipt,raw,identity=identity,nonce='a'*32,slot=slot,action=action,command=1)
        for key,value in [('fixtureAction','read'),('eventKind','fixture'),('processSlot',6)]:
            altered=dict(receipt);altered[key]=value
            with self.assertRaises(ValueError):transfer.event_uri(altered)

    def stage(self,directory):
        publisher=ROOT/'tools/publish-gecko-release.py';tree=ast.parse(publisher.read_text())
        # Execute only real source-owned file-copy branches. Never run publisher setup,
        # signing, Git, network, or another statement just because it shares an if guard.
        expected={'version_code >= 44','version_code >= 45','version_code >= 46','template_release','roadmap_release'}
        blocks=[]
        for node in tree.body:
            if not isinstance(node,ast.If) or ast.unparse(node.test) not in expected:continue
            calls=[call for call in ast.walk(node) if isinstance(call,ast.Call)]
            if calls and all(isinstance(call.func,ast.Attribute) and isinstance(call.func.value,ast.Name)
                             and (call.func.value.id,call.func.attr)==('shutil','copy2') for call in calls):blocks.append(node)
        self.assertEqual({ast.unparse(node.test) for node in blocks},expected)
        stage=Path(directory);(stage/'tools/gecko').mkdir(parents=True)
        exec(compile(ast.Module(body=blocks,type_ignores=[]),str(publisher),'exec'),
             dict(root=ROOT,stage=stage,version_code=71,template_release=True,roadmap_release=True,shutil=shutil))
        (stage/'fixture.json').write_text(json.dumps(bound_metadata()))
        return stage

    def test_actual_publisher_stage_imports_and_checks_raw_without_repository_python_path(self):
        with tempfile.TemporaryDirectory(prefix='f06-public-stage-') as directory:
            stage=self.stage(directory)
            code="import sys,pathlib,json;sys.path.insert(0,str(pathlib.Path('tools/gecko').resolve()));import check_interaction_transfer_evidence as gate;import download_resume_contract as c;assert pathlib.Path(c.__file__).parent==pathlib.Path('tools/gecko').resolve();assert c.verify_download_resume_invocation(json.loads(pathlib.Path('fixture.json').read_text()),'a'*40)['checks']==20"
            run=subprocess.run([sys.executable,'-I','-c',code],cwd=stage,text=True,capture_output=True)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)

    def test_missing_new_module_breaks_isolated_public_stage_import(self):
        with tempfile.TemporaryDirectory(prefix='f06-public-stage-negative-') as directory:
            stage=self.stage(directory);(stage/'tools/gecko/download_resume_contract.py').unlink()
            run=subprocess.run([sys.executable,'-I','-c',"import sys,pathlib;sys.path.insert(0,str(pathlib.Path('tools/gecko').resolve()));import check_interaction_transfer_evidence"],cwd=stage,text=True,capture_output=True)
            self.assertNotEqual(run.returncode,0)
            self.assertIn("No module named 'download_resume_contract'",run.stderr)


if __name__=='__main__':unittest.main()
