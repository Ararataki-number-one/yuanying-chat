"""Actual current runner discovery/consumer, with explicit native journal adapters.

No Android/device result is synthesized. Original EventTransfer and all existing
business assertions execute; counterfeit discovery and payloads remain failures.
"""
import ast
import copy
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import gecko_event_transfer_test as original

ROOT=HERE.parent
TRANSFER=original.transfer


def discovery_class():
    source=ast.parse((ROOT/'tests/gecko/run_device.py').read_text())
    node=copy.deepcopy(next(n for n in source.body if isinstance(n,ast.ClassDef) and n.name=='ReceiptJournalDiscovery'))
    bindings=dict(json=json,parse_receipt_line=TRANSFER.parse_receipt_line)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),str(ROOT/'tests/gecko/run_device.py'),'exec'),bindings)
    return bindings['ReceiptJournalDiscovery']


def marker(receipt):return json.dumps(receipt,separators=(',',':'))
def journal(native_receipts,**changes):
    value=dict(schema=1,status='committed',runNonce='e'*32,processSlot=0,fixtureAction='read',command=7,
               receipts=[marker(receipt) for receipt in native_receipts])
    value.update(changes)
    return json.dumps(value).encode()
def pending():return json.dumps(dict(schema=1,status='pending',runNonce='e'*32,processSlot=0)).encode()


class EventJournalDiscoveryControls(unittest.TestCase):
    def setUp(self):
        self.first,self.first_raw=original.packet(original.event('initialRouteReady',{'actualRoute':'controlled'}),sequence=1)
        self.last,self.last_raw=original.packet(sequence=2)
        self.reads=[]
        self.payloads={TRANSFER.event_uri(self.first):self.first_raw,TRANSFER.event_uri(self.last):self.last_raw}
        self.reader=TRANSFER.EventTransfer(identity=original.identity(),nonce='e'*32,slot=0,action='read',
            fetch=lambda uri:self.reads.append(uri) or self.payloads[uri])
        self.discovery=discovery_class()(self.reader)

    def consume(self,raw):return [self.reader.read(receipt) for receipt in self.discovery.snapshot(raw)]

    def test_exact_native_markers_are_primary_even_when_logcat_first_receipt_is_missing(self):
        controls=original.GeckoEventTransportControls()
        bindings,calls=controls.device_runner_control(self.last,self.last_raw)
        payload_reads=[];journal_reads=[]
        def native(*parts):
            if parts[-1]==self.discovery.uri():journal_reads.append(parts);return journal([self.first,self.last])
            payload_reads.append(parts[-1]);return self.payloads[parts[-1]]
        bindings['adb_bytes']=native
        with mock.patch('sys.stdout'):
            result=bindings['run'](1,'read')
        self.assertEqual(result,original.event()['result'])
        self.assertEqual(payload_reads,[TRANSFER.event_uri(self.first),TRANSFER.event_uri(self.last)])
        self.assertEqual(len(journal_reads),1)
        self.assertEqual([row['receipt']['sequence'] for row in bindings['event_transfers'][0]['events']],[1,2])
        self.assertEqual(bindings['event_transfers'][0]['discovery'],'native-committed-marker-journal')
        self.assertEqual(bindings['steps'],[original.event()])

    def test_original_actual_consumer_adapter_records_journal_separately_from_payload(self):
        receipt,raw=original.packet()
        bindings,calls=original.GeckoEventTransportControls().device_runner_control(receipt,raw)
        with mock.patch('sys.stdout'):bindings['run'](1,'read')
        self.assertEqual(len(bindings['journal_calls']),1)
        self.assertEqual(sum(parts[:3]==('exec-out','content','read') for parts in calls),1)

    def test_original_reader_receives_native_order_and_rejects_missing_or_out_of_order(self):
        third,third_raw=original.packet(sequence=3);self.payloads[TRANSFER.event_uri(third)]=third_raw
        for receipts in ([self.last],[third,self.first,self.last],[self.first,third,self.last]):
            with self.subTest(sequences=[r['sequence'] for r in receipts]):
                self.setUp()
                self.payloads[TRANSFER.event_uri(third)]=third_raw
                with self.assertRaisesRegex(ValueError,'missing or out-of-order'):self.consume(journal(receipts))
                self.assertLessEqual(len(self.reads),1)

    def test_conflicting_duplicate_is_not_skipped(self):
        changed=dict(self.first,payloadSha256='f'*64)
        with self.assertRaisesRegex(ValueError,'conflicting duplicate'):self.consume(journal([self.first,changed,self.last]))
        self.assertEqual(len(self.reads),1)

    def test_valid_stable_prefix_grows_without_refetching_or_replacing_payloads(self):
        self.assertEqual(self.consume(journal([self.first])),[original.event('initialRouteReady',{'actualRoute':'controlled'})])
        self.consume(journal([self.first,self.last]));self.consume(journal([self.first,self.last]))
        self.assertEqual(self.reads,[TRANSFER.event_uri(self.first),TRANSFER.event_uri(self.last)])
        self.assertEqual(len(self.reader.records),2)

    def test_shrinking_mutated_or_disappeared_committed_prefix_fails(self):
        self.consume(journal([self.first,self.last]))
        for raw in (journal([self.first]),pending(),journal([self.first,self.last],receipts=[marker(self.first)+' ',marker(self.last)])):
            with self.subTest(raw=raw[:80]),self.assertRaisesRegex(ValueError,'prefix changed|disappeared'):self.discovery.snapshot(raw)
        self.assertEqual(len(self.reader.records),2)

    def test_wrong_journal_identity_schema_action_command_or_status_fails(self):
        for changes in (dict(schema=True),dict(schema=2),dict(runNonce='f'*32),dict(processSlot=True),dict(processSlot=1),
                        dict(fixtureAction='seed'),dict(status='passed'),dict(command=True),dict(command=0)):
            with self.subTest(changes=changes),self.assertRaises(ValueError):self.discovery.snapshot(journal([self.first],**changes))
        self.consume(journal([self.first]))
        with self.assertRaises(ValueError):self.discovery.snapshot(journal([self.first],command=8))

    def test_wrong_native_marker_owner_command_hash_or_payload_remains_original_failure(self):
        for changes in (dict(runNonce='f'*32),dict(fixtureAction='seed'),dict(processSlot=1),dict(command=8),
                        dict(payloadSha256='f'*64),dict(payloadBytes=self.first['payloadBytes']+1)):
            with self.subTest(changes=changes):
                self.setUp()
                with self.assertRaises((ValueError,KeyError)):self.consume(journal([dict(self.first,**changes)]))
                self.assertEqual(self.reader.records,[])

    def test_journal_cannot_supply_payloads_instead_of_native_markers(self):
        for receipts in ([self.first], [self.first_raw.decode()], ['{}'], ['null'], ['{"kind":"eventTransportError"}']):
            with self.subTest(receipts=str(receipts)[:80]),self.assertRaises(ValueError):
                self.discovery.snapshot(journal([],receipts=receipts))

    def test_malformed_duplicate_nonfinite_utf8_and_size_bounds_fail_closed(self):
        raw=journal([self.first])
        for candidate in (raw[:-1],b'\xff',b'[]',b'{}',b'',b' '* (self.discovery.MAX_BYTES+1),
                          raw.replace(b'{',b'{"schema":1,',1),raw.replace(b'"command": 7',b'"command": NaN')):
            with self.subTest(candidate=candidate[:70]),self.assertRaises((ValueError,UnicodeDecodeError)):
                self.discovery.snapshot(candidate)
        with self.assertRaises(ValueError):self.discovery.snapshot(journal([self.first],receipts=[marker(self.first)]*4097))

    def test_pending_is_an_explicit_native_observation_not_a_committed_empty_success(self):
        self.assertEqual(self.discovery.snapshot(pending()),[]);self.assertEqual(self.reader.records,[])
        with self.assertRaises(ValueError):self.discovery.snapshot(journal([]))
        with self.assertRaises(ValueError):self.discovery.snapshot(json.dumps(dict(schema=1,status='pending',runNonce='e'*32,processSlot=0,receipts=[])).encode())

    def test_actual_consumer_pending_uses_original_120_second_deadline_without_payload_reads(self):
        bindings,_=original.GeckoEventTransportControls().device_runner_control(self.last,self.last_raw)
        clock=types.SimpleNamespace(now=100)
        clock.monotonic=lambda:clock.now
        def sleep(seconds):clock.now+=seconds
        clock.sleep=sleep;bindings['time']=clock
        def native(*parts):
            self.assertEqual(parts[-1],self.discovery.uri());clock.now+=10;return pending()
        bindings['adb_bytes']=native
        with tempfile.TemporaryDirectory() as directory,mock.patch('sys.stdout'):
            bindings['OUT']=Path(directory)
            with self.assertRaisesRegex(TimeoutError,'No integration result'):bindings['run'](1,'read')
        self.assertLessEqual(clock.now,231)
        self.assertEqual(bindings['event_transfers'][0]['events'],[]);self.assertEqual(bindings['steps'],[])

    def test_actual_consumer_keeps_native_transport_error_observation_before_discovery(self):
        bindings,_=original.GeckoEventTransportControls().device_runner_control(self.last,self.last_raw)
        original_adb=bindings['adb'];journal_reads=[]
        def adb(*parts):
            if parts==('logcat','-d','-s','PocketGeckoIntegration:I','*:S'):
                return json.dumps(dict(kind='eventTransportError',runNonce='e'*32,processSlot=0,error='actual publication failure'))
            return original_adb(*parts)
        bindings['adb']=adb;bindings['adb_bytes']=lambda *parts:journal_reads.append(parts)
        with self.assertRaisesRegex(ValueError,'Native complete event publication failed'):bindings['run'](1,'read')
        self.assertEqual(journal_reads,[]);self.assertEqual(bindings['steps'],[])


if __name__=='__main__':unittest.main()
