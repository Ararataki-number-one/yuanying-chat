"""Counterfeit dispatch/transport controls, with a deterministic host clock.

No adb, Android, Gecko, keyboard, real-time benchmark, or application acceptance
is exercised. The actual dispatcher and original full-payload decoder execute.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/gecko'))
from caret_dispatch import CaretDispatch, ACTION_LAYOUT
import integration_event_contract as transport
from gecko_event_transfer_test import identity as transport_identity
from gecko_caret_compat_contract_test import geometry as counterfeit_geometry
from check_caret_compat_evidence import IDS

NONCE = 'e' * 32
ACTION = 'caretCompatibility'
FOCUS_ID = ACTION_LAYOUT[0]['id']
RAPID_ID = ACTION_LAYOUT[1]['id']
RUNNER_SPEC = importlib.util.spec_from_file_location('caret_runner_host_control', ROOT / 'tests/gecko/run_gecko_caret_compat.py')
RUNNER = importlib.util.module_from_spec(RUNNER_SPEC)
RUNNER_SPEC.loader.exec_module(RUNNER)


def identity():
    value = transport_identity()
    value['sdkBuildIdentity'] = dict(sdkCoordinate=transport.SDK_COORDINATE,runId='12345',runAttempt='1')
    return value


def packet(sequence, kind='check', result=None, **changes):
    envelope = dict(schema=1, sourceCommit='a' * 40, buildIdentity=identity(), runNonce=NONCE,
                    fixtureAction=ACTION, command=1, sequence=sequence,
                    nativeContext='environment-1', processSlot=0, observedAtElapsedRealtime=1000 + sequence,
                    event=dict(kind=kind, result=result if result is not None else dict(index=sequence, **{'pass':True}),
                               nativeContext='environment-1', processSlot=0))
    envelope.update(changes)
    return encoded(envelope)


def encoded(envelope):
    raw = json.dumps(envelope, ensure_ascii=False, separators=(',', ':')).encode('utf-8') + b'\n'
    receipt = {field:envelope[field] for field in ('schema','runNonce','fixtureAction','command','sequence','nativeContext','processSlot')}
    receipt.update(kind='eventReceipt', eventKind=envelope['event']['kind'], payloadBytes=len(raw),
                   payloadSha256=hashlib.sha256(raw).hexdigest())
    return receipt, raw


def step(sequence, index=0, identifier=None, commands=None):
    expected = ACTION_LAYOUT[index]
    canonical = []
    for op,value in expected['commands']:
        if op == 'tap':
            geometry = counterfeit_geometry(IDS.index(expected['scenario']))
            geometry['runNonce'] = NONCE
            canonical.append(dict(op='tap',x=100+value,y=200,expectedCaret=value,
                clientPoint=dict(x=(100+value)/2.5,y=80),nativeGeometry=geometry,
                viewport=dict(width=432,height=720,scale=1,offsetLeft=0,offsetTop=0,pageLeft=0,pageTop=0)))
        else:
            canonical.append(dict(op=op,**{{'text':'text','key':'code','combination':'codes'}[op]:copy.deepcopy(value)}))
    return packet(sequence, 'stepNeeded', dict(id=identifier or expected['id'],scenario=expected['scenario'],
        origin='adb-input-keyboard-and-touch',commands=canonical if commands is None else commands))


def terminal(sequence, status='passed'):
    return packet(sequence, 'report', dict(status=status, error='' if status == 'passed' else 'Native exact oracle failed',
        actualAndroidExecution=False, actualGeckoExecution=False, controlledCaretCompatibilityAcceptance=False))


class Clock:
    def __init__(self):
        self.seconds = 0.0

    def monotonic(self):
        return self.seconds

    def wall_clock(self):
        return 1700000000.0 + self.seconds


class Harness:
    def __init__(self, packets, passive_delay=1.1, action_delay=.1, dispatch=None):
        self.packets = {receipt['sequence']:(copy.deepcopy(receipt), raw) for receipt,raw in packets}
        self.clock = Clock()
        self.fetches, self.dispatched, self.dispatch_times = [], [], []
        self.passive_delay, self.action_delay = passive_delay, action_delay

        def fetch(uri):
            sequence = int(uri.rsplit('/',1)[1])
            receipt, raw = self.packets[sequence]
            self.fetches.append(sequence)
            self.clock.seconds += action_delay if receipt['eventKind'] == 'stepNeeded' else passive_delay
            return raw

        def callback(value):
            self.dispatched.append(copy.deepcopy(value))
            self.dispatch_times.append(self.clock.seconds)
            if dispatch is not None:
                return dispatch(value)
            rows = []
            for index, command in enumerate(value['commands']):
                wall_start = int(self.clock.wall_clock() * 1000)
                mono_start = int(self.clock.monotonic() * 1_000_000_000)
                self.clock.seconds += .02
                rows.append(dict(commandIndex=index,op=command['op'],invocationCount=1,completed=True,
                    adbStartedAtWallTimeMillis=wall_start,
                    adbCompletedAtWallTimeMillis=int(self.clock.wall_clock() * 1000),
                    adbStartedAtMonotonicNanos=mono_start,
                    adbCompletedAtMonotonicNanos=int(self.clock.monotonic() * 1_000_000_000)))
            return rows

        self.agent = CaretDispatch(identity=identity(), nonce=NONCE, slot=0, action=ACTION, command=1,
            fetch=fetch, dispatch=callback)


class CaretDispatchTest(unittest.TestCase):
    def test_29_slow_passive_events_cannot_delay_the_next_input(self):
        packets = [packet(index) for index in range(1,30)] + [step(30),terminal(31)]
        h = Harness(packets)
        h.agent.ingest([receipt for receipt,_ in packets[:-1]])
        self.assertEqual(h.fetches,[30])
        self.assertEqual(len(h.dispatched),1)
        self.assertAlmostEqual(h.dispatch_times[0],.1)
        self.assertLess(h.clock.seconds,20, 'Passive payload collection must not consume the native focus deadline')
        self.assertFalse(h.agent.terminal)
        h.agent.ingest([packets[-1][0]])
        self.assertTrue(h.agent.terminal)
        complete = h.agent.drain()
        self.assertIsInstance(complete,transport.EventTransfer)
        self.assertEqual([record['receipt']['sequence'] for record in complete.records],list(range(1,32)))
        self.assertEqual([record['rawUtf8'].encode('utf-8') for record in complete.records],[raw for _,raw in packets])
        self.assertEqual(h.fetches,[30]+list(range(1,30))+[31])
        self.assertGreater(h.clock.seconds,30, 'Slow read-only collection occurs after input dispatch')
        self.assertEqual(len(h.dispatched),1, 'Ordered drain must never redispatch input')
        self.assertEqual(h.agent.actions[FOCUS_ID]['executions'][0]['invocationCount'],1)

    def test_exact_receipt_replays_dispatch_and_fetch_action_only_once(self):
        packets = [step(1),terminal(2)]
        h = Harness(packets)
        h.agent.ingest([copy.deepcopy(packets[0][0])])
        h.agent.ingest([copy.deepcopy(packets[0][0])])
        self.assertEqual(h.fetches,[1])
        self.assertEqual(len(h.dispatched),1)
        h.agent.ingest([copy.deepcopy(receipt) for receipt,_ in packets])
        complete = h.agent.drain()
        self.assertEqual(h.fetches,[1,2])
        self.assertEqual(len(h.dispatched),1)
        self.assertEqual(len(complete.records),2)

    def test_terminal_in_same_batch_suppresses_overdue_input_and_preserves_failure(self):
        packets = [packet(1),step(2),terminal(3,'failed')]
        h = Harness(packets)
        h.agent.ingest([receipt for receipt,_ in packets])
        self.assertTrue(h.agent.terminal)
        self.assertEqual(h.dispatched,[])
        self.assertEqual(h.fetches,[])
        complete = h.agent.drain()
        self.assertEqual(h.fetches,[1,2,3])
        self.assertEqual(h.dispatched,[])
        original = json.loads(complete.records[-1]['rawUtf8'])['event']['result']
        self.assertEqual(original['status'],'failed')
        self.assertEqual(original['error'],'Native exact oracle failed')
        self.assertFalse(original['controlledCaretCompatibilityAcceptance'])

    def test_whole_batch_is_validated_before_any_input_or_payload_fetch(self):
        first = step(1)
        candidates = [dict(packet(2)[0],sequence=3),dict(packet(2)[0],runNonce='f'*32),
            dict(packet(2)[0],fixtureAction='another-action'),dict(packet(2)[0],command=2),
            dict(packet(2)[0],processSlot=1),dict(packet(2)[0],nativeContext='environment-2'),
            dict(packet(2)[0],sequence=True),dict(packet(2)[0],payloadBytes=True),
            dict(packet(2)[0],sourceCommit='a'*40)]
        for invalid in candidates:
            with self.subTest(invalid=invalid):
                h = Harness([first,packet(2),packet(3)])
                with self.assertRaises(ValueError):
                    h.agent.ingest([copy.deepcopy(first[0]),invalid])
                self.assertEqual(h.dispatched,[])
                self.assertEqual(h.fetches,[])
                with self.assertRaises(ValueError):
                    h.agent.ingest([copy.deepcopy(first[0])])
                self.assertEqual(h.dispatched,[],'Rejected receipt metadata permanently locks this invocation')

    def test_conflicting_receipt_replay_cannot_swap_an_owned_action(self):
        owned = step(1)
        for field,value in [('payloadSha256','f'*64),('payloadBytes',owned[0]['payloadBytes']+1),('eventKind','check')]:
            with self.subTest(field=field):
                h = Harness([owned]);h.agent.ingest([owned[0]])
                with self.assertRaises(ValueError):
                    h.agent.ingest([dict(owned[0],**{field:value})])
                with self.assertRaises(ValueError):
                    h.agent.ingest([copy.deepcopy(owned[0])])
                self.assertEqual(h.fetches,[1])
                self.assertEqual(len(h.dispatched),1)

    def test_foreign_or_corrupt_action_bytes_are_rejected_before_dispatch(self):
        receipt,raw = step(1)
        changes = []
        changes.append((receipt,raw[:-1]))
        changes.append((dict(receipt,payloadSha256='f'*64),raw))
        changes.append((dict(receipt,payloadBytes=len(raw)+1),raw))
        for mutate in [lambda value:value.update(sourceCommit='f'*40),
            lambda value:value['buildIdentity'].update(apkSha256='f'*64),
            lambda value:value.update(command=2),
            lambda value:value['event'].update(kind='check'),
            lambda value:value['event'].update(result=['malformed']),
            lambda value:value['event'].update(processSlot=1)]:
            envelope = json.loads(raw)
            mutate(envelope)
            changed_receipt,changed_raw = encoded(envelope)
            changed_receipt.update(command=1,eventKind='stepNeeded')
            changes.append((changed_receipt,changed_raw))
        malformed = b'\xff' * len(raw)
        changes.append((dict(receipt,payloadSha256=hashlib.sha256(malformed).hexdigest()),malformed))
        for rejected_receipt,rejected_raw in changes:
            with self.subTest(receipt=rejected_receipt):
                h = Harness([(rejected_receipt,rejected_raw)])
                with self.assertRaises(ValueError):
                    h.agent.ingest([rejected_receipt])
                self.assertEqual(h.dispatched,[])
                self.assertEqual(h.agent.actions,{})

    def test_corrupt_deferred_payload_blocks_a_receipt_only_pass(self):
        passive = packet(1)
        packets = [passive,step(2),terminal(3)]
        h = Harness(packets)
        h.packets[1] = (passive[0],passive[1][:-1])
        h.agent.ingest([passive[0],packets[1][0]])
        self.assertEqual(len(h.dispatched),1)
        self.assertEqual(h.fetches,[2])
        h.agent.ingest([packets[-1][0]])
        with self.assertRaises(ValueError):
            h.agent.drain()
        self.assertEqual(len(h.dispatched),1)
        self.assertNotIn(3,h.fetches,'No terminal success payload may hide a prior corrupt event')
        fetched = h.fetches[:]
        with self.assertRaises(ValueError):
            h.agent.drain()
        with self.assertRaises(ValueError):
            h.agent.ingest([copy.deepcopy(packets[-1][0])])
        self.assertEqual(h.fetches,fetched,'A failed complete drain cannot later become acceptance')

    def test_source_mismatch_in_deferred_evidence_is_not_accepted_after_input(self):
        passive = packet(1,sourceCommit='f'*40)
        packets = [passive,step(2),terminal(3)]
        h = Harness(packets)
        h.agent.ingest([passive[0],packets[1][0]])
        h.agent.ingest([packets[-1][0]])
        with self.assertRaises(ValueError):
            h.agent.drain()
        self.assertEqual(h.fetches,[2,1])
        self.assertEqual(len(h.dispatched),1)

    def test_action_raw_cache_is_immutable_and_never_refetched_during_drain(self):
        owned = step(1)
        done = terminal(2)
        h = Harness([owned,done])
        caller_receipt = copy.deepcopy(owned[0])
        h.agent.ingest([caller_receipt])
        caller_receipt['payloadSha256'] = 'f'*64
        # A different provider response after dispatch must not replace the exact
        # bytes which authorized that single input action.
        h.packets[1] = (owned[0],b'changed after dispatch')
        h.agent.ingest([copy.deepcopy(owned[0]),done[0]])
        complete = h.agent.drain()
        self.assertEqual(h.fetches,[1,2])
        self.assertEqual(complete.records[0]['receipt'],owned[0])
        self.assertEqual(complete.records[0]['rawUtf8'].encode(),owned[1])
        self.assertEqual(json.loads(complete.records[0]['rawUtf8'])['event']['result']['commands'],
                         json.loads(owned[1])['event']['result']['commands'])
        self.assertEqual(len(h.dispatched),1)

    def test_partial_ledger_without_terminal_cannot_be_drained_as_completion(self):
        owned = step(1)
        h = Harness([owned])
        h.agent.ingest([owned[0]])
        self.assertFalse(h.agent.terminal)
        with self.assertRaises(ValueError):
            h.agent.drain()
        self.assertEqual(h.fetches,[1])

    def test_second_terminal_and_post_terminal_records_are_rejected(self):
        report = terminal(1)
        for extra in [terminal(2),step(2),packet(2)]:
            with self.subTest(kind=extra[0]['eventKind']):
                h = Harness([report,extra])
                h.agent.ingest([report[0]])
                with self.assertRaises(ValueError):
                    h.agent.ingest([extra[0]])
                self.assertEqual(h.dispatched,[])
                self.assertEqual(h.fetches,[])
        h = Harness([report])
        h.agent.ingest([report[0],copy.deepcopy(report[0])])
        self.assertTrue(h.agent.terminal)
        self.assertEqual(len(h.agent.drain().records),1)

    def test_duplicate_action_id_never_redispatches_commands(self):
        packets = [step(1),step(2)]
        h = Harness(packets)
        h.agent.ingest([packets[0][0]])
        with self.assertRaises(ValueError):
            h.agent.ingest([packets[1][0]])
        self.assertEqual(len(h.dispatched),1)

    def test_unicode_and_failure_fields_survive_ordered_deferred_drain(self):
        result = dict(index=1,text='中文🙂'*2000,checks=[{'name':'Preserved failure','pass':False}],
                      nested={'unchanged':[None,True,0]},error='Exact mismatch',actualAndroidExecution=False)
        packets = [packet(1,'checkpoint',result),terminal(2,'failed')]
        h = Harness(packets)
        h.agent.ingest([receipt for receipt,_ in packets])
        complete = h.agent.drain()
        self.assertEqual(complete.records[0]['rawUtf8'].encode('utf-8'),packets[0][1])
        self.assertEqual(json.loads(complete.records[0]['rawUtf8'])['event']['result'],result)
        self.assertEqual(h.dispatched,[])

    def test_read_only_phase_budget_is_checked_after_each_payload_fetch(self):
        packets = [packet(1),packet(2),packet(3),terminal(4)]
        h = Harness(packets)
        h.agent.ingest([receipt for receipt,_ in packets])
        with self.assertRaises(ValueError):
            h.agent.drain(timeout=2,clock=h.clock.monotonic)
        self.assertEqual(h.fetches,[1,2])
        self.assertEqual(len(h.agent.transfer.records),2)
        self.assertEqual(h.dispatched,[])
        self.assertNotIn(4,h.fetches, 'An exhausted evidence budget cannot reach terminal success')

    def test_nonfinite_nonpositive_or_non_numeric_evidence_budget_is_rejected(self):
        done = terminal(1)
        for budget in [None,True,'600',0,-1,float('nan'),float('inf'),float('-inf')]:
            with self.subTest(budget=budget):
                h = Harness([done])
                h.agent.ingest([done[0]])
                with self.assertRaises(ValueError):
                    h.agent.drain(timeout=budget,clock=h.clock.monotonic)
                self.assertEqual(h.fetches,[])

    def test_partial_callback_failure_is_preserved_and_can_never_retry_input(self):
        partial = dict(commandIndex=0,op='tap',invocationCount=1,completed=True)

        def failing_dispatch(action):
            if action['id'] == FOCUS_ID:
                return [copy.deepcopy(partial)]
            action['executions'].append(copy.deepcopy(partial))
            raise RuntimeError('Synthetic command two failed after command one')

        focus,owned = step(1),step(2,index=1)
        h = Harness([focus,owned],dispatch=failing_dispatch)
        with self.assertRaises(RuntimeError):
            h.agent.ingest([focus[0],owned[0]])
        self.assertEqual(h.agent.actions[RAPID_ID]['executions'],[partial])
        with self.assertRaises(ValueError):
            h.agent.ingest([copy.deepcopy(owned[0])])
        self.assertEqual(len(h.dispatched),2)
        self.assertEqual(h.fetches,[1,2])

    def test_invalid_callback_execution_count_fails_and_locks_replays(self):
        owned = step(1)
        h = Harness([owned],dispatch=lambda action:[])
        with self.assertRaises(ValueError):
            h.agent.ingest([owned[0]])
        with self.assertRaises(ValueError):
            h.agent.ingest([copy.deepcopy(owned[0])])
        self.assertEqual(len(h.dispatched),1)

    def test_unknown_passive_kind_locks_without_delaying_or_dispatching_input(self):
        packets = [packet(1,'unverifiedSuccessHint'),step(2)]
        h = Harness(packets)
        with self.assertRaises(ValueError):
            h.agent.ingest([receipt for receipt,_ in packets])
        with self.assertRaises(ValueError):
            h.agent.ingest([step(1)[0]])
        self.assertEqual(h.fetches,[])
        self.assertEqual(h.dispatched,[])

    def test_later_corrupt_action_in_one_batch_prevents_the_earlier_input(self):
        focus,rapid = step(1),step(2,index=1)
        h = Harness([focus,rapid])
        h.packets[2] = (rapid[0],rapid[1][:-1])
        with self.assertRaises(ValueError):
            h.agent.ingest([focus[0],rapid[0]])
        self.assertEqual(h.fetches,[1,2])
        self.assertEqual(h.dispatched,[])
        self.assertEqual(h.agent.actions,{})
        with self.assertRaises(ValueError):
            h.agent.ingest([focus[0],rapid[0]])
        self.assertEqual(h.fetches,[1,2])

    def test_canonical_two_action_batch_is_decoded_before_the_first_dispatch(self):
        packets = [step(1),step(2,index=1)]
        h = Harness(packets)
        h.agent.ingest([receipt for receipt,_ in packets])
        self.assertEqual(h.fetches,[1,2])
        self.assertAlmostEqual(h.dispatch_times[0],.2)
        self.assertEqual([value['id'] for value in h.dispatched],[FOCUS_ID,RAPID_ID])
        self.assertEqual([command['op'] for command in h.dispatched[1]['commands']],['tap','tap','text'])
        self.assertEqual(h.dispatched[1]['commands'][2],dict(op='text',text='Q'))

    def test_wrong_action_source_owner_caret_matrix_and_shape_are_rejected_before_input(self):
        mutations = [
            lambda value:value.update(id='selected-replace-focus-2'),
            lambda value:value.update(scenario='selected-replace'),
            lambda value:value.update(origin='synthetic-click'),
            lambda value:value.update(unexpected=True),
            lambda value:value['commands'][0].update(expectedCaret=4),
            lambda value:value['commands'][0].update(expectedCaret=True),
            lambda value:value['commands'][0].update(x=999),
            lambda value:value['commands'][0].update(x=True),
            lambda value:value['commands'][0].pop('nativeGeometry'),
            lambda value:value['commands'][0]['nativeGeometry'].update(sourceCommit='f'*40),
            lambda value:value['commands'][0]['nativeGeometry'].update(runId='99999'),
            lambda value:value['commands'][0]['nativeGeometry'].update(runAttempt='2'),
            lambda value:value['commands'][0]['nativeGeometry'].update(runNonce='f'*32),
            lambda value:value['commands'][0]['nativeGeometry'].update(case=1),
            lambda value:value['commands'][0]['nativeGeometry'].update(documentUrl='http://127.0.0.1:8771/caret?case=1'),
            lambda value:value['commands'][0]['nativeGeometry'].update(timeOrigin=0),
            lambda value:value['commands'][0]['nativeGeometry'].update(nativePort=0),
            lambda value:value['commands'][0]['nativeGeometry'].update(attachedSession=999),
            lambda value:value['commands'][0]['nativeGeometry'].update(shown=False),
            lambda value:value['commands'][0]['nativeGeometry'].update(clientToSurfaceMatrix=[1,0,0,0,2,0,0,0,1]),
            lambda value:value['commands'][0]['viewport'].update(height=0),
            lambda value:value['commands'][0]['clientPoint'].update(y=999),
        ]
        for mutate in mutations:
            envelope = json.loads(step(1)[1]);mutate(envelope['event']['result'])
            rejected = encoded(envelope)
            with self.subTest(action=envelope['event']['result']):
                h = Harness([rejected])
                with self.assertRaises(ValueError):
                    h.agent.ingest([rejected[0]])
                self.assertEqual(h.dispatched,[])
                self.assertEqual(h.agent.actions,{})

    def test_later_wrong_source_command_vector_prevents_all_batch_inputs(self):
        focus,rapid = step(1),step(2,index=1)
        envelope = json.loads(rapid[1]);envelope['event']['result']['commands'][2]['text'] = 'Z'
        wrong = encoded(envelope)
        h = Harness([focus,wrong])
        with self.assertRaises(ValueError):
            h.agent.ingest([focus[0],wrong[0]])
        self.assertEqual(h.dispatched,[])
        self.assertEqual(h.fetches,[1,2])


class ActualRunnerCallbackTest(unittest.TestCase):
    def action(self):
        value = json.loads(step(1,index=1)[1])['event']['result']
        value['executions'] = []
        return value

    def assert_timestamps(self, row):
        for start,end in [('adbStartedAtWallTimeMillis','adbCompletedAtWallTimeMillis'),
                          ('adbStartedAtMonotonicNanos','adbCompletedAtMonotonicNanos')]:
            self.assertIs(type(row[start]),int);self.assertIs(type(row[end]),int)
            self.assertGreater(row[start],0);self.assertGreaterEqual(row[end],row[start])

    def test_actual_source_callback_runs_tap_tap_text_q_once_without_sleep_or_extra_adb(self):
        action = self.action();calls = []
        with mock.patch.object(RUNNER.time,'sleep',side_effect=AssertionError('Input must not be paced')):
            rows = RUNNER.perform_android_action(action,lambda *parts:calls.append(parts))
        self.assertEqual(calls,[('shell','input','tap','102','200'),('shell','input','tap','109','200'),
                                ('shell','input','keyboard','text','Q')])
        self.assertIs(rows,action['executions'])
        self.assertEqual(len(rows),3)
        for index,row in enumerate(rows):
            self.assertEqual({key:row[key] for key in ('commandIndex','op','invocationCount','completed')},
                             dict(commandIndex=index,op=['tap','tap','text'][index],invocationCount=1,completed=True))
            self.assert_timestamps(row)

    def test_actual_source_callback_prevalidates_a_malformed_second_command_before_any_adb(self):
        for mutate in [lambda command:command.update(op='unknown'),lambda command:command.update(x=True),
                       lambda command:command.update(unexpected=True),lambda command:command.pop('viewport')]:
            action = self.action();mutate(action['commands'][1]);calls = []
            with self.subTest(command=action['commands'][1]), self.assertRaises(ValueError):
                RUNNER.perform_android_action(action,lambda *parts:calls.append(parts))
            self.assertEqual(calls,[])
            self.assertEqual(action['executions'],[])

    def test_actual_source_callback_keeps_failed_command_end_times_and_stops_later_commands(self):
        for fail_at in (0,1):
            action = self.action();calls = []

            def failed_adb(*parts):
                calls.append(parts)
                if len(calls)-1 == fail_at:
                    raise RuntimeError('Synthetic adb callback failed')

            with self.subTest(fail_at=fail_at), self.assertRaises(RuntimeError):
                RUNNER.perform_android_action(action,failed_adb)
            rows = action['executions']
            self.assertEqual(len(rows),fail_at+1)
            self.assertEqual(len(calls),fail_at+1)
            self.assertFalse(rows[-1]['completed'])
            self.assertTrue(all(row['completed'] for row in rows[:-1]))
            for row in rows:
                self.assert_timestamps(row)
            with self.assertRaises(ValueError):
                RUNNER.perform_android_action(action,failed_adb)
            self.assertEqual(len(calls),fail_at+1,'A partial action cannot be replayed')


if __name__ == '__main__':
    unittest.main()
