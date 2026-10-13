"""Counterfeit transport controls only: no Android, Gecko or app acceptance."""
import ast
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import time
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/gecko'))
import integration_event_contract as transfer


def identity():
    return dict(schema=1, package='local.pocketchat.test', sourceCommit='a'*40,
                sourceTree='b'*40, dirtySource=False, version='1.7.0', versionCode=52,
                sdkCoordinate=transfer.SDK_COORDINATE, apkSha256='c'*64,
                apkBytes=100, buildStampSha256='d'*64)


def event(kind='fixture', result=None):
    return dict(kind=kind, result=result if result is not None else {'context':'1','action':'read'},
                nativeContext='environment-1', processSlot=0)


def packet(value=None, **changes):
    envelope = dict(schema=1, sourceCommit='a'*40, buildIdentity=identity(), runNonce='e'*32,
                    fixtureAction='read', command=7, sequence=1, nativeContext='environment-1',
                    processSlot=0, event=value or event())
    envelope.update(changes)
    raw = json.dumps(envelope, ensure_ascii=False, separators=(',',':')).encode('utf-8') + b'\n'
    receipt = {key:envelope[key] for key in ('schema','runNonce','fixtureAction','command','sequence','nativeContext','processSlot')}
    receipt.update(kind='eventReceipt', eventKind=envelope['event']['kind'], payloadBytes=len(raw),
                   payloadSha256=hashlib.sha256(raw).hexdigest())
    return receipt, raw


def decode(receipt, raw, **changes):
    arguments = dict(identity=identity(), nonce='e'*32, slot=0, action='read', command=7)
    arguments.update(changes)
    return transfer.decode_event(receipt, raw, **arguments)


class GeckoEventTransportControls(unittest.TestCase):
    def device_runner_control(self, receipt, raw):
        """Extract the actual consumer body without importing/executing adb code."""
        source=ast.parse((ROOT/'tests/gecko/run_device.py').read_text())
        main=next(node for node in source.body if isinstance(node,ast.FunctionDef) and node.name=='main')
        run=copy.deepcopy(next(node for node in main.body if isinstance(node,ast.FunctionDef) and node.name=='run'))
        self.assertFalse(any(isinstance(node,ast.Name) and isinstance(node.ctx,ast.Store)
                             and node.id=='identity' for node in ast.walk(run)),
                         'A local dedup identity must not shadow the installed build identity')
        calls=[]
        def fake_adb(*parts):
            calls.append(parts)
            if parts==('logcat','-d','-s','PocketGeckoIntegration:I','*:S'):
                return '10-13 12:00 I PocketGeckoIntegration: '+json.dumps(receipt)+'\n'
            return ''
        def fake_bytes(*parts):
            self.assertEqual(parts,('exec-out','content','read','--uri',transfer.event_uri(receipt)))
            calls.append(parts)
            return raw
        bindings=dict(adb=fake_adb,adb_bytes=fake_bytes,identity=identity(),event_transfers=[],
                      uuid=types.SimpleNamespace(uuid4=lambda:types.SimpleNamespace(hex='e'*32)),
                      EventTransfer=transfer.EventTransfer,parse_receipt_line=transfer.parse_receipt_line,
                      has_pixel_launcher=False,launcher='counterfeit-unused-launcher',package='local.pocketchat.test',
                      surface_gestures={},time=time,json=json,report={},logs=[],steps=[],OUT=ROOT/'work/gecko-integration')
        exec(compile(ast.fix_missing_locations(ast.Module(body=[run],type_ignores=[])),
                     '<counterfeit-device-consumer-control>','exec'),bindings)
        return bindings,calls

    def test_large_unicode_full_fields_round_trip_without_acceptance_claim(self):
        result = dict(text='中文🙂'*30000, observations=[{'scope':'Worker','actual':'手机'}]*100,
                      arbitraryNested={'allFields':['kept',None,True,0]}, error='',
                      actualAndroidExecution=False, actualGeckoExecution=False, applicationAcceptance=False)
        original = event(result=result); receipt, raw = packet(original)
        self.assertGreater(len(raw), 100000)
        self.assertEqual(decode(receipt,raw), original)
        self.assertFalse(decode(receipt,raw)['result']['applicationAcceptance'])

    def test_errors_are_preserved_and_never_promoted_to_success(self):
        original = event('error',dict(error='AssertionError: exact draft differs', expected='ordered',
                                     observed='unordered', checks=[{'pass':False,'name':'real oracle'}],
                                     failureType='AssertionError', status='failed'))
        receipt,raw = packet(original)
        self.assertEqual(decode(receipt,raw),original)

    def test_truncation_and_same_length_corruption_fail(self):
        receipt,raw = packet()
        for candidate in [raw[:-1], raw[:-10], bytes([raw[0]^1])+raw[1:]]:
            with self.subTest(length=len(candidate)), self.assertRaises(ValueError):
                decode(receipt,candidate)

    def test_correct_digest_cannot_make_fragments_or_invalid_utf8_valid(self):
        receipt,_ = packet()
        for raw in [b'{"schema":1', b'{"schema":1}\n{"schema":1}', b'\xff', b'null', b'[]']:
            candidate=dict(receipt,payloadBytes=len(raw),payloadSha256=hashlib.sha256(raw).hexdigest())
            with self.subTest(raw=raw), self.assertRaises(ValueError):decode(candidate,raw)

    def test_source_apk_tree_and_stamp_are_bound(self):
        for key,replacement in [('sourceCommit','f'*40),('sourceTree','f'*40),('apkSha256','f'*64),
                                ('buildStampSha256','f'*64),('version','2.0.0'),('apkBytes',101),
                                ('dirtySource',True),('versionCode',True),('schema',True)]:
            candidate=identity();candidate[key]=replacement
            receipt,raw=packet(buildIdentity=candidate)
            with self.subTest(key=key), self.assertRaises(ValueError):decode(receipt,raw)
        receipt,raw=packet(sourceCommit='f'*40)
        with self.assertRaises(ValueError):decode(receipt,raw)

    def test_foreign_nonce_action_slot_and_command_fail_direct_validation(self):
        for key,replacement in [('runNonce','f'*32),('fixtureAction','seed'),('command',8),
                                ('nativeContext','environment-2'),('processSlot',1)]:
            receipt,raw=packet(**{key:replacement})
            with self.subTest(key=key), self.assertRaises(ValueError):decode(receipt,raw)

    def test_envelope_and_nested_event_cannot_relabel_receipt(self):
        receipt,raw=packet()
        for target,key,replacement in [('envelope','runNonce','f'*32),('envelope','fixtureAction','seed'),
                                       ('envelope','command',8),('envelope','sequence',2),
                                       ('envelope','processSlot',1),('event','kind','error'),
                                       ('event','nativeContext','environment-2'),('event','processSlot',1),
                                       ('event','result',[]),('event','result',None)]:
            envelope=json.loads(raw); container=envelope if target=='envelope' else envelope['event']
            container[key]=replacement;candidate=json.dumps(envelope).encode()
            adjusted=dict(receipt,payloadBytes=len(candidate),payloadSha256=hashlib.sha256(candidate).hexdigest())
            with self.subTest(target=target,key=key), self.assertRaises(ValueError):decode(adjusted,candidate)

    def test_boolean_numeric_and_missing_fields_are_rejected(self):
        receipt,raw=packet()
        for key in ['schema','command','sequence','processSlot','payloadBytes']:
            changed=dict(receipt);changed[key]=True
            with self.subTest(key=key), self.assertRaises(ValueError):decode(changed,raw)
        for key in receipt:
            changed=dict(receipt);del changed[key]
            with self.subTest(missing=key), self.assertRaises(ValueError):decode(changed,raw)

    def test_provider_payload_size_and_raw_byte_type_are_enforced(self):
        receipt,raw=packet()
        for size in [0,-1,transfer.MAX_PAYLOAD_BYTES+1,True]:
            with self.subTest(size=size), self.assertRaises(ValueError):decode(dict(receipt,payloadBytes=size),raw)
        with self.assertRaises(ValueError):decode(receipt,raw.decode())

    def test_tagged_malformed_or_truncated_marker_is_not_silently_skipped(self):
        for line in [transfer.TAG+': {"kind":"eventReceipt"',transfer.TAG+': no object',
                     transfer.TAG+': {"kind":"eventRece',transfer.TAG+': {"kind":"fixture","result":{}}',
                     transfer.TAG+': {"kind":"eventReceipt","kind":"fixture"}',
                     transfer.TAG+': {"kind":"eventReceipt","sequence":NaN}']:
            with self.subTest(line=line), self.assertRaises(ValueError):transfer.parse_receipt_line(line)
        self.assertIsNone(transfer.parse_receipt_line('OtherTag: {"kind":"fixture"}'))
        receipt,_=packet();self.assertEqual(transfer.parse_receipt_line('10-13 12:00 I '+transfer.TAG+': '+json.dumps(receipt)),receipt)
        failure={'kind':'eventTransportError','error':'AtomicFile write failed'}
        self.assertEqual(transfer.parse_receipt_line(transfer.TAG+': '+json.dumps(failure)),failure)

    def test_event_duplicate_json_fields_and_nonfinite_values_fail(self):
        receipt,raw=packet()
        for candidate in [raw.replace(b'"schema":1',b'"schema":1,"schema":1',1),
                          raw.replace(b'"command":7',b'"command":NaN',1)]:
            adjusted=dict(receipt,payloadBytes=len(candidate),payloadSha256=hashlib.sha256(candidate).hexdigest())
            with self.assertRaises(ValueError):decode(adjusted,candidate)

    def test_duplicate_cache_fetches_once_and_caller_mutation_is_isolated(self):
        receipt,raw=packet();calls=[]
        reader=transfer.EventTransfer(identity=identity(),nonce='e'*32,slot=0,action='read',fetch=lambda uri:calls.append(uri) or raw)
        first=reader.read(receipt);first['result']['context']='mutated'
        self.assertEqual(reader.read(copy.deepcopy(receipt)),event())
        self.assertEqual(calls,['content://local.pocketchat.test.evidence/gecko-events/0/'+'e'*32+'/1'])
        self.assertEqual(reader.command,7)
        self.assertEqual(reader.records,[dict(receipt=receipt,rawUtf8=raw.decode())])
        self.assertTrue(reader.records[0]['rawUtf8'].endswith('\n'))
        with self.assertRaises(ValueError):reader.read(dict(receipt,payloadSha256='f'*64))

    def test_sequence_gaps_and_command_changes_cannot_drop_events(self):
        packets=[packet(sequence=1),packet(event('error',{'error':'failed'}),sequence=2),packet(sequence=3,command=8)]
        reader=transfer.EventTransfer(identity=identity(),nonce='e'*32,slot=0,action='read',fetch=lambda uri:packets[int(uri.rsplit('/',1)[1])-1][1])
        with self.assertRaises(ValueError):reader.read(packets[1][0])
        self.assertEqual(reader.read(packets[0][0]),event())
        self.assertEqual(reader.read(packets[1][0])['result']['error'],'failed')
        with self.assertRaises(ValueError):reader.read(packets[2][0])

    def test_real_device_consumer_body_returns_large_original_provider_result(self):
        result=dict(text='原始完整数据🙂'*3000,attachment={'bytes':4097,'mime':'image/png'},
                    preservedNested=[{'name':'全部字段','values':[1,None,False]}],
                    actualAndroidExecution=False,actualGeckoExecution=False,applicationAcceptance=False)
        receipt,raw=packet(event('usability',result),fixtureAction='usability')
        self.assertGreater(len(raw),4096)
        bindings,calls=self.device_runner_control(receipt,raw)
        with contextlib.redirect_stdout(io.StringIO()):
            observed=bindings['run'](1,'usability','usability')
        self.assertEqual(observed,result)
        self.assertEqual(bindings['steps'],[event('usability',result)])
        self.assertEqual(bindings['event_transfers'][0]['events'],[dict(receipt=receipt,rawUtf8=raw.decode())])
        self.assertEqual(sum(parts[:3]==('exec-out','content','read') for parts in calls),1)
        self.assertFalse(observed['applicationAcceptance'])

    def test_real_device_consumer_body_preserves_original_error_assertion(self):
        original=event('error',dict(error='Exact real oracle still failed',observed='错序'*3000,
                                   checks=[{'name':'draft ordering','pass':False}],
                                   actualAndroidExecution=False,applicationAcceptance=False))
        receipt,raw=packet(original,fixtureAction='usability')
        bindings,_=self.device_runner_control(receipt,raw)
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(AssertionError) as failure:
            bindings['run'](1,'usability','usability')
        self.assertEqual(failure.exception.args[0],original)
        self.assertEqual(bindings['steps'],[])
        self.assertEqual(bindings['event_transfers'][0]['events'],[dict(receipt=receipt,rawUtf8=raw.decode())])


if __name__ == '__main__':
    unittest.main()
