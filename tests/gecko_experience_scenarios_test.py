"""Host controls for observation boundaries; no Android measurements are synthesized."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    result = importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result
B = module('scenario_benchmark', 'tests/gecko/run_experience_benchmark.py')
S = B.scenarios
C = module('scenario_comparison', 'tools/gecko/run_experience_comparison.py')
E = module('scenario_event_controls', 'tests/gecko_event_transfer_test.py')


def sample(start, end, ticks, available=True):
    return dict(available=available, uptimeSeconds=start, uptimeEndSeconds=end,
                processes=[dict(pid=1, startTicks=1, userTicks=ticks, systemTicks=0)])


class ScenariosTest(unittest.TestCase):
    def idle_observer(self, directory, log_sequences, error=False):
        packets = []
        for sequence, (kind, name, started) in enumerate([
                ('scenarioStarted', 'idle-foreground', 1000), ('scenarioFinished', 'idle-foreground', 1000),
                ('scenarioStarted', 'idle-background', 200000), ('scenarioFinished', 'idle-background', 200000)], 1):
            result = dict(name=name, start={'elapsedRealtimeMs': started})
            if kind == 'scenarioFinished': result.update(end={'elapsedRealtimeMs': started+120000}, elapsedDurationMs=120000)
            if error and sequence == 2: kind = 'error';result = dict(error='actual device fixture failure')
            packets.append(E.packet(E.event(kind, result), fixtureAction='experienceBenchmark', sequence=sequence))
        state = {'logReads': 0, 'providerReads': [], 'finishedReceiptObserved': False}
        def adb(*parts, **kwargs):
            if parts[0] == 'logcat':
                selected = log_sequences[min(state['logReads'], len(log_sequences)-1)]
                state['logReads'] += 1
                state['finishedReceiptObserved'] = bool(selected and max(selected) in (2, 4) and not error)
                return '\n'.join(json.dumps(packets[i-1][0]) for i in selected)
            self.assertEqual(parts[:4], ('exec-out', 'content', 'read', '--uri'))
            self.assertTrue(state['finishedReceiptObserved'], 'Provider read while device idle end has not been observed')
            sequence = int(parts[-1].rsplit('/', 1)[1]);state['providerReads'].append(sequence)
            return packets[sequence-1][1]
        return B.make_events(adb, E.identity(), 'e'*32, 'experienceBenchmark', Path(directory)), state, packets

    def test_device_end_receipt_precedes_all_idle_payload_reads(self):
        with tempfile.TemporaryDirectory() as directory:
            events, state, _ = self.idle_observer(directory, [[1], [1], [1, 2]])
            start = events('scenarioStarted', 'idle-foreground', receipt_only=True)
            self.assertEqual(state['providerReads'], [])
            # The host timer has expired but the device callback is still pending
            # on the next log read. Execute the actual finish boundary consumer.
            window = B.finish_idle_window(events, 'idle-foreground', start)
            self.assertEqual(window['elapsedDurationMs'], 120000)
            self.assertEqual(state['providerReads'], [1, 2])
            self.assertGreaterEqual(state['logReads'], 3)

    def test_previous_phase_end_cannot_end_the_next_idle_window(self):
        with tempfile.TemporaryDirectory() as directory:
            events, state, _ = self.idle_observer(directory, [[1, 2, 3], [1, 2, 3, 4]])
            receipt = events('scenarioFinished', 'idle-background', receipt_only=True, after_sequence=3)
            self.assertEqual(receipt['sequence'], 4)
            self.assertEqual(state['logReads'], 2);self.assertEqual(state['providerReads'], [])

    def test_receipt_boundary_cannot_return_an_older_cached_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            events, state, _ = self.idle_observer(directory, [[1, 2]])
            events('scenarioFinished', 'idle-foreground')
            self.assertEqual(state['providerReads'], [1, 2])
            with mock.patch.object(B.time, 'monotonic', side_effect=[0, 1, 100]), mock.patch.object(B.time, 'sleep'):
                with self.assertRaises(TimeoutError):
                    events('scenarioFinished', 'idle-foreground', receipt_only=True, after_sequence=2)
            self.assertEqual(state['providerReads'], [1, 2])

    def test_missing_or_error_end_keeps_payload_unread_and_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            events, state, packets = self.idle_observer(directory, [[1]])
            with mock.patch.object(B.time, 'monotonic', side_effect=[0, 1, 100]), mock.patch.object(B.time, 'sleep'):
                with self.assertRaises(TimeoutError): B.finish_idle_window(events, 'idle-foreground', packets[0][0])
            self.assertEqual(state['providerReads'], [])
        with tempfile.TemporaryDirectory() as directory:
            events, state, packets = self.idle_observer(directory, [[1, 2]], error=True)
            with self.assertRaisesRegex(AssertionError, 'eventKind.*error'):
                B.finish_idle_window(events, 'idle-foreground', packets[0][0])
            self.assertEqual(state['providerReads'], [])

    def test_declared_inputs_are_stable_and_unsupported_paths_are_gaps(self):
        for name in S.NAMES:
            value = S.manifest(name)
            self.assertEqual(S.digest(value), S.digest(copy.deepcopy(value)))
            self.assertEqual(value['name'], name)
        self.assertEqual(set(S.GAPS), {'P02', 'P04', 'F03'})
        for name in ('download-history-100', 'idle-0', 'P02', '../core'):
            with self.assertRaises(ValueError): S.manifest(name)
        changed = S.manifest('idle-120');changed['idle']['foregroundMs'] = 1000
        self.assertNotEqual(S.digest(changed), S.digest(S.manifest('idle-120')))

    def test_cpu_uses_contained_actual_envelopes_without_boundary_interpolation(self):
        samples = [sample(9.9, 10.1, 1), sample(10.2, 10.4, 10), sample(11.2, 11.4, 30), sample(11.9, 12.1, 60)]
        result = S.cpu_window(samples, 100, 10000, 12000, B.cpu_summary)
        self.assertEqual(result['sampleIndices'], [1, 2])
        self.assertEqual(result['cpuSecondsObserved'], .2)
        self.assertEqual(result['unobservedLeadingMs'], 200)
        self.assertEqual(result['unobservedTrailingMs'], 600)
        self.assertFalse(result['boundaryInterpolation'])
        self.assertFalse(result['completeProcessLifetimeCoverage'])

    def test_unbounded_or_missing_observations_do_not_become_idle_zero(self):
        for samples in ([], [sample(10.2, 10.4, 10)], [sample(10.2, 10.4, 10, False), sample(11.2, 11.4, 30, False)],
                        [dict(available=True, uptimeSeconds=10.2, processes=[])]):
            result = S.cpu_window(samples, 100, 10000, 12000, B.cpu_summary)
            self.assertFalse(result['available']);self.assertNotIn('cpuSecondsObserved', result)
        for start, end in ((12000, 10000), (0, 0), (float('nan'), 1000), (True, 1000)):
            with self.assertRaises(ValueError): S.cpu_window([], 100, start, end, B.cpu_summary)

    def test_pss_requires_successful_matching_raw_pid_header(self):
        raw = '** MEMINFO in pid 123 [local.pocketchat.test] **\n TOTAL PSS: 321 TOTAL RSS: 600\n'
        self.assertEqual(S.pss_value(raw, 123)['pssKb'], 321)
        for text, pid in ((raw, 124), ('No process found for: 123', 123), ('TOTAL PSS: 321', 123),
                          ('** MEMINFO in pid 123 [local.pocketchat.test] **\n', 123)):
            with self.assertRaises(ValueError): S.pss_value(text, pid)

    def test_idle_verifier_rejects_short_missing_reordered_and_truncated_windows(self):
        manifest = S.manifest('idle-120')
        windows = [dict(name='idle-'+state, start={'elapsedRealtimeMs': 1000}, end={'elapsedRealtimeMs': 121000},
                        elapsedDurationMs=120000, frameLimitReached=False, lifecycleChanges=0)
                   for state in ('foreground', 'background')]
        row = dict(seed={'scenario': {'manifest': manifest, 'manifestSha256': S.digest(manifest)}}, scenarioWindows=windows)
        C.verify_scenario(row, manifest)
        for mutate in (lambda r: r['scenarioWindows'].pop(), lambda r: r['scenarioWindows'].reverse(),
                       lambda r: r['scenarioWindows'][0].update(frameLimitReached=True),
                       lambda r: r['scenarioWindows'][0].update(lifecycleChanges=1),
                       lambda r: r['scenarioWindows'][0]['end'].update(elapsedRealtimeMs=120000)):
            changed = copy.deepcopy(row);mutate(changed)
            with self.assertRaises(ValueError): C.verify_scenario(changed, manifest)

    def test_history_verifier_requires_all_actual_saves_and_final_index(self):
        manifest = S.manifest('download-history-1000')
        window = dict(name='history-save', start={'elapsedRealtimeMs': 1000}, end={'elapsedRealtimeMs': 19000},
                      elapsedDurationMs=18000, frameLimitReached=False, lifecycleChanges=0,
                      saves=[dict(step=i, durationMs=20, received=i*65536, method='DownloadTasks.save', httpTransferMeasured=False)
                             for i in range(1, 9)],
                      verification=dict(savedRows=1000, taskRows=1001, verifiedProgressBytes=524288,
                                        actualAndroidSQLite=True, actualAndroidSharedPreferences=True))
        row = dict(seed={'scenario': {'manifest': manifest, 'manifestSha256': S.digest(manifest)}}, scenarioWindows=[window])
        C.verify_scenario(row, manifest)
        for mutate in (lambda r: r['scenarioWindows'][0]['saves'].pop(),
                       lambda r: r['scenarioWindows'][0]['saves'][0].update(httpTransferMeasured=True),
                       lambda r: r['scenarioWindows'][0]['verification'].update(taskRows=1),
                       lambda r: r['scenarioWindows'][0]['verification'].update(actualAndroidSQLite=False)):
            changed = copy.deepcopy(row);mutate(changed)
            with self.assertRaises(ValueError): C.verify_scenario(changed, manifest)


if __name__ == '__main__': unittest.main()
