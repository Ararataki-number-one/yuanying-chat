"""Counterfeit parser controls only; no Android/Binder/fixture acceptance."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/gecko'))
import network_client_binding_contract as C
from integration_event_contract import EventTransfer,decode_event

SOURCE='a'*40;NONCE='d'*32;UID=10209
ENV=dict(slot=0,generation=0,environmentId='12345678-1234-1234-1234-123456789012')
OWNER='11111111-1111-1111-1111-111111111111';MISSING_OWNER='22222222-2222-2222-2222-222222222222'

def encoded(value):return json.dumps(value,separators=(',',':'))+'\n'
def proof(value):
    raw=value if isinstance(value,str) else encoded(value);data=raw.encode()
    return dict(rawUtf8=raw,utf8Bytes=len(data),sha256=hashlib.sha256(data).hexdigest())

def journal(owner,events):
    rows=['\t'.join(['1700000000000',str(80+i),'0','CONTROL',owner,ENV['environmentId'],'0','unknown',event,'UNKNOWN' if event in ('IPC_CONNECTED','IPC_DETACH') else 'CONTROL_UNAVAILABLE','IPC' if event=='IPC_DETACH' else 'BIND','0'])for i,event in enumerate(events)]
    return dict(diagnosticWaitBegan=700,diagnosticWaitEnded=701,diagnosticWaitLimitMs=3000,owner=owner,
        environmentIdentity=copy.deepcopy(ENV),rawSummary='Synthetic journal parser control, not a captured device\n'+'\n'.join(rows)+'\n',ownedRows=rows,
        journalMonotonicClock='System.nanoTime()/1000000; distinct from elapsedRealtime call/wait clocks')

def fixture():
    # The SDK contract preserves explicitly historical official identities. This
    # synthetic source is not a current build and cannot qualify a release.
    identity=dict(schema=1,package=C.PACKAGE,sourceCommit=SOURCE,sourceTree='b'*40,dirtySource=False,
        version='1.7.0',versionCode=52,sdkCoordinate='org.mozilla.geckoview:geckoview:157.0.20261005135250',
        apkSha256='e'*64,apkBytes=123,buildStampSha256='f'*64)
    def service(role):return dict(schema=1,runNonce=NONCE,sourceCommit=SOURCE,buildIdentity=copy.deepcopy(identity),
        serviceClass=C.CLASS+('$NullService' if role=='null' else '$MessengerService'),servicePid=201,
        serviceUid=UID,serviceProcess=C.SERVICE_PROCESS,onBindAt=150 if role=='null' else 250,
        onBindMainLooper=True,role=role,returnedNull=role=='null')
    null,normal=service('null'),service('messenger')
    normal['messages']=[dict(id=('3'if i==0 else'4')*8+'-'+('3'if i==0 else'4')*4+'-'+('3'if i==0 else'4')*4+'-'+('3'if i==0 else'4')*4+'-'+('3'if i==0 else'4')*12,
        slot=0,action=action,configuration='',generation='' if i==0 else 'fixture-'+NONCE,
        stopReason='UNKNOWN',expectedGeneration='',sendingUid=UID,receivedAt=300+i*100,replySent=True)
        for i,action in enumerate(('snapshot','detach'))]
    def attempt(number,target,connection,gate,began,ended,accepted):return dict(number=number,target=target,
        connectionIdentity=connection,connectionClass='local.pocketchat.NetworkTransportClient$Binding',gateIdentity=gate,
        gateCount=0,began=began,ended=ended,accepted=accepted,error='',unbindError='',unbindAttempts=1,unbindSuccesses=1)
    result=dict(schema=1,status='passed',actualAndroidExecution=True,actualFrameworkBinding=True,actualMessengerIpc=True,
        actualProductionClient=True,actualProductionNetworkService=False,actualMihomoExecution=False,
        actualGeckoExecution=False,manualServiceConnectionCallbacks=0,automaticBindRetryAdded=False,
        securityExceptionAndroidAcceptance=False,bindingDiedAndroidAcceptance=False,physicalPhoneAcceptance=False,
        realUserProxyAcceptance=False,sourceCommit=SOURCE,runNonce=NONCE,buildIdentity=copy.deepcopy(identity),
        clientPid=101,clientUid=UID,clientProcess=C.ACTIVITY_PROCESS,androidSdk=35,bindingTimeoutSeconds=10,
        replyTimeoutSeconds=15,detachTimeoutSeconds=5,environmentIdentity=copy.deepcopy(ENV),
        checks=[dict(name=name,**{'pass':True})for name in C.CHECKS],checkCount=len(C.CHECKS),
        nullWaiter=dict(began=100,ended=200,elapsedMs=100,failed=True,failureClass='java.io.IOException'),
        missingWaiter=dict(began=500,ended=600,elapsedMs=100,failed=True,failureClass='java.io.IOException'),
        nullService=null,messengerService=normal,
        recoveredState=dict(slot=0,alive=False,state='fixture',generation='fixture-'+NONCE,servicePid=201,serviceUid=UID,fixtureNonce=NONCE,fixtureRole='messenger'),
        nullCallbackJournal=journal(OWNER,['IPC_NULL_BINDING','IPC_BIND_TIMEOUT']),
        completedCallbackJournal=journal(OWNER,['IPC_NULL_BINDING','IPC_BIND_TIMEOUT','IPC_CONNECTED','IPC_DETACH']),
        missingCallbackJournal=journal(MISSING_OWNER,['IPC_BIND_REJECTED','IPC_BIND_TIMEOUT']),
        bindings=[dict(missingComponent=False,outstanding=0,attempts=[attempt(1,C.CLASS+'$NullService',11,21,110,120,True),attempt(2,C.CLASS+'$MessengerService',12,22,240,245,True)]),
                  dict(missingComponent=True,outstanding=0,attempts=[attempt(1,C.MISSING,13,23,510,530,False)])])
    wrapper=dict(schema=1,status='passed',sourceCommit=SOURCE,runNonce=NONCE,buildIdentity=identity,
        installedBefore=proof(identity),installedAfter=proof(identity),packageUid=UID,
        packageUidBeforeRaw='package:'+C.PACKAGE+' uid:'+str(UID)+'\n',packageUidAfterRaw='package:'+C.PACKAGE+' uid:'+str(UID)+'\n',
        androidSdk=35,actualAndroidFixtureAttempted=True,fixtureInvocationCount=1,automaticRetryPerformed=False,result=result)
    align(wrapper);return wrapper

def align(wrapper,services=True):
    result=wrapper['result']
    if services:
        for key in ('nullService','messengerService'):result[key+'Raw']=proof(result[key])
    event=dict(kind=C.ACTION,result=copy.deepcopy(result),nativeContext='environment-1',processSlot=0)
    envelope=dict(schema=1,sourceCommit=SOURCE,buildIdentity=copy.deepcopy(wrapper['buildIdentity']),runNonce=NONCE,
        fixtureAction=C.ACTION,command=1,sequence=1,nativeContext='environment-1',processSlot=0,observedAtElapsedRealtime=900,event=event)
    raw=encoded(envelope);receipt=dict(kind='eventReceipt',schema=1,runNonce=NONCE,fixtureAction=C.ACTION,command=1,
        sequence=1,nativeContext='environment-1',processSlot=0,eventKind=C.ACTION,payloadBytes=len(raw.encode()),payloadSha256=hashlib.sha256(raw.encode()).hexdigest())
    wrapper['eventTransport']=[dict(receipt=receipt,rawUtf8=raw)]

class BindingControls(unittest.TestCase):
    def reject(self,edit,*,semantic=True,services=True):
        value=fixture();edit(value)
        if semantic:align(value,services)
        with self.assertRaises((ValueError,KeyError,TypeError)):C.verify_runner_report(value,SOURCE)
    def result(self,edit,**kwargs):self.reject(lambda w:edit(w['result']),**kwargs)
    def test_counterfeit_positive_exercises_parser_only(self):
        value=fixture();answer=C.verify_runner_report(value,SOURCE)
        self.assertEqual(answer['checks'],18);self.assertFalse(answer['productionNetworkServiceFaulted'])
    def test_each_missing_or_failed_named_check_is_rejected(self):
        for index in range(len(C.CHECKS)):
            with self.subTest(index=index):self.result(lambda r:r['checks'][index].update({'pass':False}))
        self.result(lambda r:r['checks'].pop())
    def test_count_zero_and_boolean_cannot_qualify(self):
        self.result(lambda r:r.update(checkCount=0));self.result(lambda r:r.update(checkCount=True))
    def test_manual_callbacks_are_never_framework_acceptance(self):
        self.result(lambda r:r.update(manualServiceConnectionCallbacks=1));self.result(lambda r:r.update(manualServiceConnectionCallbacks=False))
    def test_fault_scope_cannot_be_upgraded_to_real_service_or_phone(self):
        for key in ('actualProductionNetworkService','actualMihomoExecution','actualGeckoExecution','securityExceptionAndroidAcceptance','bindingDiedAndroidAcceptance','physicalPhoneAcceptance','realUserProxyAcceptance'):
            with self.subTest(key=key):self.result(lambda r:r.update({key:True}))
    def test_actual_framework_and_ipc_flags_are_required(self):
        for key in ('actualFrameworkBinding','actualMessengerIpc','actualProductionClient'):
            self.result(lambda r:r.update({key:False}))
    def test_caller_must_fail_before_original_deadline(self):
        self.result(lambda r:r['nullWaiter'].update(ended=10100,elapsedMs=10000))
        self.result(lambda r:r['missingWaiter'].update(failureClass='java.lang.IllegalStateException'))
    def test_original_deadlines_cannot_change(self):
        for key in ('bindingTimeoutSeconds','replyTimeoutSeconds','detachTimeoutSeconds'):self.result(lambda r:r.update({key:999}))
    def test_other_client_uid_or_process_is_rejected(self):
        self.result(lambda r:r.update(clientUid=UID+1));self.result(lambda r:r.update(clientProcess=C.PACKAGE))
    def test_service_source_uid_and_cross_process_proof_are_required(self):
        for key,replacement in [('sourceCommit','f'*40),('runNonce','f'*32),('serviceUid',UID+1),('servicePid',101),('serviceProcess',C.ACTIVITY_PROCESS),('onBindMainLooper',False),('returnedNull',False)]:
            with self.subTest(key=key):self.result(lambda r:r['nullService'].update({key:replacement}))
    def test_missing_or_changed_raw_service_receipt_is_rejected(self):
        self.result(lambda r:r.pop('nullServiceRaw'),services=False)
        self.result(lambda r:r['messengerServiceRaw'].update(sha256='0'*64),services=False)
    def test_raw_hash_cannot_substitute_for_matching_parsed_service(self):
        self.result(lambda r:r['nullService'].update(role='messenger'),services=False)
    def test_service_message_must_preserve_actual_command_fields(self):
        for key,replacement in [('action','launch'),('sendingUid',UID+1),('configuration','changed'),('generation','changed'),('stopReason','REQUESTED'),('expectedGeneration','changed'),('replySent',False)]:
            with self.subTest(key=key):self.result(lambda r:r['messengerService']['messages'][0].update({key:replacement}))
    def test_duplicate_request_id_or_missing_detach_is_rejected(self):
        self.result(lambda r:r['messengerService']['messages'][1].update(id=r['messengerService']['messages'][0]['id']))
        self.result(lambda r:r['messengerService']['messages'].pop())
    def test_messenger_client_return_cannot_come_from_another_service(self):
        self.result(lambda r:r['recoveredState'].update(servicePid=999));self.result(lambda r:r['recoveredState'].update(slot=False))
    def test_each_owner_requires_one_successful_unbind(self):
        for key,replacement in [('unbindAttempts',0),('unbindAttempts',2),('unbindAttempts',True),('unbindSuccesses',0),('unbindSuccesses',True),('unbindError','failed')]:
            with self.subTest(key=key,value=replacement):self.result(lambda r:r['bindings'][0]['attempts'][0].update({key:replacement}))
    def test_unreleased_or_missing_bindings_are_rejected(self):
        self.result(lambda r:r['bindings'][0].update(outstanding=1));self.result(lambda r:r['bindings'][0].update(outstanding=False));self.result(lambda r:r['bindings'].pop())
    def test_new_demand_requires_fresh_owner_and_gate(self):
        for key in ('connectionIdentity','gateIdentity'):
            self.result(lambda r:r['bindings'][0]['attempts'][1].update({key:r['bindings'][0]['attempts'][0][key]}))
    def test_true_null_bind_and_false_missing_bind_are_distinct(self):
        self.result(lambda r:r['bindings'][0]['attempts'][0].update(accepted=False));self.result(lambda r:r['bindings'][1]['attempts'][0].update(accepted=True))
    def test_callback_claim_requires_actual_owned_journal_rows(self):
        self.result(lambda r:r['nullCallbackJournal'].update(ownedRows=[]))
        def remove(r):
            value=r['nullCallbackJournal'];value['ownedRows']=[row for row in value['ownedRows']if '\tIPC_NULL_BINDING\t'not in row];value['rawSummary']='\n'.join(value['ownedRows'])
        self.result(remove)
    def test_callback_owner_and_environment_cannot_cross(self):
        self.result(lambda r:r['completedCallbackJournal'].update(owner=MISSING_OWNER))
        self.result(lambda r:r['nullCallbackJournal']['environmentIdentity'].update(generation=1))
    def test_missing_bind_has_its_own_rejection_owner(self):
        self.result(lambda r:r.update(missingCallbackJournal=copy.deepcopy(r['completedCallbackJournal'])))
    def test_owned_callback_rows_require_the_production_reason_and_stage(self):
        for column,replacement in ((9,'REQUESTED'),(10,'PROBE'),(11,'1')):
            def change(r):
                value=r['nullCallbackJournal'];row=value['ownedRows'][0].split('\t');row[column]=replacement
                value['ownedRows'][0]='\t'.join(row);value['rawSummary']='\n'.join(value['ownedRows'])+'\n'
            self.result(change)
    def test_unexpected_owned_event_cannot_stand_in_for_a_callback(self):
        def change(r):
            value=r['nullCallbackJournal'];row=value['ownedRows'][0].split('\t');row[8]='CORE_START'
            value['ownedRows'][0]='\t'.join(row);value['rawSummary']='\n'.join(value['ownedRows'])+'\n'
        self.result(change)
    def test_diagnostic_wait_clock_does_not_replace_actual_call_clock(self):
        self.result(lambda r:r['nullCallbackJournal'].update(diagnosticWaitLimitMs=30000));self.result(lambda r:r['nullCallbackJournal'].update(journalMonotonicClock='elapsedRealtime'))
    def test_provider_envelope_and_installed_bytes_are_independently_required(self):
        self.reject(lambda w:w.update(eventTransport=[]),semantic=False)
        self.reject(lambda w:w['eventTransport'][0].update(rawUtf8='{}'),semantic=False)
        self.reject(lambda w:w['installedAfter'].update(sha256='0'*64))
    def test_legally_reencoded_later_sequence_fails_runner_and_public_replay(self):
        import tempfile
        for sequence in (2,3,2**63-1):
            with self.subTest(sequence=sequence):
                value=fixture();record=value['eventTransport'][0];envelope=json.loads(record['rawUtf8'])
                envelope['sequence']=record['receipt']['sequence']=sequence
                record['rawUtf8']=encoded(envelope);raw=record['rawUtf8'].encode()
                record['receipt'].update(payloadBytes=len(raw),payloadSha256=hashlib.sha256(raw).hexdigest())
                options=dict(identity=value['buildIdentity'],nonce=NONCE,slot=0,action=C.ACTION,command=1)
                # This valid individual event was the independent review's
                # counterexample: only the complete transfer rejects its gap.
                self.assertEqual(decode_event(record['receipt'],raw,**options)['result'],value['result'])
                transfer=EventTransfer(fetch=lambda uri:raw,**options)
                with self.assertRaisesRegex(ValueError,'missing or out-of-order event sequence'):transfer.read(record['receipt'])
                with self.assertRaisesRegex(ValueError,'missing or out-of-order event sequence'):C.verify_runner_report(value,SOURCE)
                with tempfile.TemporaryDirectory()as name:
                    directory=Path(name)
                    device=dict(status='passed',sourceCommit=SOURCE,actualAndroidExecution=True,
                        eventTransport=dict(schema=1,buildIdentity=value['buildIdentity']))
                    (directory/'device-results.json').write_text(encoded(device))
                    (directory/'network-client-binding-results.json').write_text(encoded(value))
                    with self.assertRaisesRegex(ValueError,'missing or out-of-order event sequence'):C.verify_framework_binding_files(directory,SOURCE)
    def test_reference_build_rejects_cross_apk_mixing(self):
        value=fixture();reference=copy.deepcopy(value['buildIdentity']);reference['apkSha256']='0'*64
        with self.assertRaises(ValueError):C.verify_runner_report(value,SOURCE,reference)
    def test_only_one_actual_invocation_can_qualify(self):
        self.reject(lambda w:w.update(fixtureInvocationCount=2));self.reject(lambda w:w.update(automaticRetryPerformed=True));self.reject(lambda w:w.update(actualAndroidFixtureAttempted=False))
    def test_actual_installed_uid_is_not_a_prefix_match(self):
        self.reject(lambda w:w.update(packageUidAfterRaw='package:'+C.PACKAGE+'.other uid:'+str(UID)+'\n'))
    def test_raw_duplicate_nonfinite_or_overflow_json_is_rejected(self):
        for raw in ('{"a":1,"a":2}','{"a":NaN}','{"a":1e400}'):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):C.raw_value(proof(raw))


class FixtureSourceControls(unittest.TestCase):
    def test_real_android_destination_fault_does_not_call_connection_callbacks(self):
        raw=(ROOT/'tests/gecko/NetworkClientBindingIntegrationActivity.java').read_text()
        for method in ('onNullBinding(','onServiceConnected(','onServiceDisconnected(','onBindingDied('):self.assertNotIn(method,raw)
        self.assertIn('super.bindService(redirected,owner,flags)',raw);self.assertIn('super.unbindService(owner)',raw)
        self.assertIn('return null;',raw);self.assertIn('return endpoint.getBinder();',raw)
    def test_all_source_checks_are_required_in_order(self):
        import re
        names=re.findall(r'check\("([^"\n]+)"',(ROOT/'tests/gecko/NetworkClientBindingIntegrationActivity.java').read_text())
        self.assertEqual(names,list(C.CHECKS))
    def test_old_lifecycle_and_reviewed_92_oracle_stay_byte_exact(self):
        path='tests/gecko/NetworkTransportLifecycleActivity.java'
        self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),'43358547bea5378e409c8f97290929163905e6dd86e61197064e4f7cde933efe')
        oracle=ROOT/'tests/network-transport-client-host/NetworkTransportClientHost.java'
        self.assertEqual(hashlib.sha256(oracle.read_bytes()).hexdigest(),'6decfd84c9f5a0b314948133230ca03347c19e19be2cdb3c175b1467be054f60')
        # Run the real snapshot loader without any ancestor Git objects. Each
        # altered provenance/input must fail even when a local file is present.
        import tempfile
        selected=ROOT/'tests/network-transport-client-host/run.py'
        spec=importlib.util.spec_from_file_location('selected_binding_snapshot_loader',selected)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        before,helper,metadata=module.load_before_snapshot()
        self.assertEqual(metadata['sourceCommit'],'3eac2891438d37aa62f695b34a90f0aa02215ca2')
        def rejected(change):
            with tempfile.TemporaryDirectory()as name:
                temp=Path(name);module.HERE=temp;module.ROOT=temp
                (temp/'BeforeNetworkTransportClient.java.in').write_bytes(before)
                target=temp/metadata['sharedHelperPath'];target.parent.mkdir(parents=True);target.write_bytes(helper)
                altered=copy.deepcopy(metadata);change(temp,altered)
                (temp/'before-source.json').write_text(encoded(altered))
                with self.assertRaises(ValueError):module.load_before_snapshot()
        rejected(lambda p,m:(p/'BeforeNetworkTransportClient.java.in').write_bytes(before+b'\n'))
        rejected(lambda p,m:(p/metadata['sharedHelperPath']).write_bytes(helper+b'\n'))
        rejected(lambda p,m:m.update(sourceCommit='f'*40))
        rejected(lambda p,m:m.update(snapshotFile='../other.java.in'))
        rejected(lambda p,m:m.update(sha256='f'*64))
        rejected(lambda p,m:m.update(schema=True))
    def test_fixture_manifest_services_are_private_and_run_outside_client(self):
        import xml.etree.ElementTree as ET
        root=ET.parse(ROOT/'tests/gecko/AndroidManifest.xml').getroot();ns='{http://schemas.android.com/apk/res/android}'
        for role in ('NullService','MessengerService'):
            rows=[n for n in root.iter('service')if n.get(ns+'name')==C.CLASS+'$'+role]
            self.assertEqual(len(rows),1);self.assertEqual(rows[0].get(ns+'exported'),'false');self.assertEqual(rows[0].get(ns+'process'),':transport_binding_services')
        self.assertNotIn(C.CLASS,(ROOT/'app/src/main/AndroidManifest.xml').read_text())


class PublicWiringControls(unittest.TestCase):
    def evidence(self,directory):
        value=fixture();device=dict(status='passed',sourceCommit=SOURCE,actualAndroidExecution=True,
            eventTransport=dict(schema=1,buildIdentity=copy.deepcopy(value['buildIdentity'])))
        (directory/'device-results.json').write_text(encoded(device))
        (directory/'network-client-binding-results.json').write_text(encoded(value));return value,device
    def test_public_file_validator_replays_the_same_complete_wrapper(self):
        import tempfile
        with tempfile.TemporaryDirectory()as name:
            directory=Path(name);self.evidence(directory)
            self.assertEqual(C.verify_framework_binding_files(directory,SOURCE)['nullCallbacks'],1)
    def test_original_device_evidence_and_new_report_are_both_mandatory(self):
        import tempfile
        for missing in ('device-results.json','network-client-binding-results.json'):
            with tempfile.TemporaryDirectory()as name:
                directory=Path(name);self.evidence(directory);(directory/missing).unlink()
                with self.assertRaises(FileNotFoundError):C.verify_framework_binding_files(directory,SOURCE)
    def test_public_gate_rejects_a_different_original_apk_or_source(self):
        import tempfile
        with tempfile.TemporaryDirectory()as name:
            directory=Path(name);value,device=self.evidence(directory)
            device['eventTransport']['buildIdentity']['apkSha256']='0'*64
            (directory/'device-results.json').write_text(encoded(device))
            with self.assertRaises(ValueError):C.verify_framework_binding_files(directory,SOURCE)
            self.evidence(directory)
            with self.assertRaises(ValueError):C.verify_framework_binding_files(directory,'f'*40)
    def test_connections_step_keeps_every_original_command_and_condition(self):
        path='.github/workflows/gecko-integration.yml';raw=(ROOT/path).read_text()
        inserted='        if ! python3 tests/gecko/run_network_client_binding.py --adb "$(command -v adb)" --serial emulator-5554; then\n          checks_failed=1\n        fi\n'
        self.assertEqual(raw.count(inserted),1)
        self.assertEqual(hashlib.sha256(raw.replace(inserted,'',1).encode()).hexdigest(),'50fdca828ab3f661aff423bf6755359d2f4e8b24c3e78e0100d8ce29da8120c1')
    def test_connection_gate_only_adds_the_mandatory_framework_validator(self):
        path='tools/gecko/check_connection_evidence.py';raw=(ROOT/path).read_text()
        inserted='if __package__:\n    from .network_client_binding_contract import verify_framework_binding_files\nelse:\n    from network_client_binding_contract import verify_framework_binding_files\n'
        self.assertEqual(raw.count(inserted),1)
        restored=raw.replace(inserted,'',1).replace('    framework_binding = verify_framework_binding_files(directory, source)\n','',1).replace(", 'frameworkClientBinding': framework_binding",'',1)
        self.assertEqual(hashlib.sha256(restored.encode()).hexdigest(),'075b666ae597ecf2c4ec3d19eb3713c6a4c0b42359867197086fee1127cccd18')
    def test_publisher_actual_selected_ast_copies_report_and_pure_contract(self):
        import ast
        import types
        raw=(ROOT/'tools/publish-gecko-release.py').read_text();tree=ast.parse(raw)
        nodes=[node for node in tree.body if isinstance(node,ast.If) and ('network-client-binding-results.json'in ast.unparse(node)or'network_client_binding_contract.py'in ast.unparse(node))]
        self.assertEqual(len(nodes),2);copies=[]
        ns=dict(version_code=71,performance_files=[],root=ROOT,stage=Path('/tmp/synthetic-binding-stage'),shutil=types.SimpleNamespace(copy2=lambda a,b:copies.append((a,b))))
        exec(compile(ast.Module(body=nodes,type_ignores=[]),'<actual publisher binding selection>','exec'),ns)
        self.assertEqual(ns['performance_files'],['network-client-binding-results.json'])
        self.assertEqual(copies,[(ROOT/'tools/gecko/network_client_binding_contract.py',Path('/tmp/synthetic-binding-stage/tools/gecko/network_client_binding_contract.py'))])


if __name__=='__main__':unittest.main()
