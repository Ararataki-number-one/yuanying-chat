#!/usr/bin/env python3
"""Post-workload, bounded Perfetto evidence; never application qualification."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import resource
import subprocess

ROOT = Path(__file__).resolve().parents[2]
MAX_TRACE = 24 * 1024 * 1024
MAX_SQL = 256 * 1024
QUERIES = {
    'bounds': 'SELECT start_ts,end_ts FROM trace_bounds;',
    'clocks': 'SELECT ts,clock_id,clock_name,clock_value,snapshot_id FROM clock_snapshot ORDER BY snapshot_id,clock_id;',
    'stats': "SELECT name,idx,severity,source,value FROM stats WHERE name GLOB '*ftrace*' OR name GLOB '*buffer*' OR name GLOB '*traced_buf*' OR name GLOB '*clock*';",
    'sched': 'SELECT cpu,COUNT(*) AS events FROM sched GROUP BY cpu;',
    'ftrace': "SELECT name,COUNT(*) AS events FROM ftrace_event WHERE name IN ('sched_switch','sched_wakeup','sched_waking','binder_transaction','binder_transaction_received') GROUP BY name;",
    'slices': "SELECT name,COUNT(*) AS events FROM slice WHERE LOWER(name) LIKE '%input%' OR LOWER(name) LIKE '%dalvik%' OR name GLOB '*GC*' OR name GLOB '*JIT*' OR name GLOB '*Class*' GROUP BY name LIMIT 100;",
}


def read_json(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError('Missing or oversized bounded JSON: ' + path.name)
    return json.loads(path.read_bytes())


def analyze(out, trace_processor):
    out, tool = Path(out).resolve(), Path(trace_processor).resolve()
    out.mkdir(parents=True, exist_ok=True)
    result = dict(schema=1, status='incomplete', diagnosticOnly=True,
                  applicationAcceptance=False, physicalPhoneAcceptance=False,
                  cpuRootCauseEstablished=False, reasons=[], queries={},
                  clockMapping='unavailable', lossEvidence='unknown', gestureCoverage=[])
    reasons = result['reasons']
    trace = out / 'android.perfetto-trace'
    try:
        run = read_json(out / 'diagnostic-run.json')
        if run.get('diagnosticOnly') is not True or run.get('applicationAcceptance') is not False:
            reasons.append('collector-scope-not-diagnostic')
        if run.get('traceStartSucceeded') is not True or run.get('ownStopConfirmed') is not True:
            reasons.append('own-trace-start-or-stop-not-confirmed')
        if trace.is_symlink() or not trace.is_file() or trace.stat().st_size <= 0:
            raise ValueError('Trace missing or empty')
        size = trace.stat().st_size
        result.update(traceBytes=size, traceSha256=hashlib.sha256(trace.read_bytes()).hexdigest())
        if size > MAX_TRACE:
            raise ValueError('Trace exceeds fixed 24 MiB bound')
        if size >= MAX_TRACE - 65536:
            reasons.append('trace-near-file-cap-retention-not-proven')
        rows = {}
        for label, sql in QUERIES.items():
            stdout_path, stderr_path = out / ('analysis-' + label + '.csv'), out / ('analysis-' + label + '.stderr.log')
            # Analysis happens after the workload; only this tool child gets a file cap.
            with stdout_path.open('xb') as stdout, stderr_path.open('xb') as stderr:
                try:
                    process = subprocess.run([str(tool), '-Q', sql, str(trace)],
                                             stdout=stdout, stderr=stderr, timeout=45, check=False,
                                             preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_SQL, MAX_SQL)))
                    code = process.returncode
                except subprocess.TimeoutExpired:
                    code = -1
            if stdout_path.stat().st_size >= MAX_SQL or stderr_path.stat().st_size >= MAX_SQL:
                reasons.append('query-output-at-fixed-cap-' + label)
            result['queries'][label] = dict(exitCode=code, stdout=stdout_path.name,
                stderr=stderr_path.name, stdoutSha256=hashlib.sha256(stdout_path.read_bytes()).hexdigest(),
                stderrSha256=hashlib.sha256(stderr_path.read_bytes()).hexdigest())
            if code != 0:
                reasons.append('query-unavailable-' + label)
                rows[label] = []
                continue
            rows[label] = list(csv.DictReader(io.StringIO(stdout_path.read_text())))

        bounds = rows.get('bounds', [])
        if len(bounds) != 1:
            raise ValueError('Actual trace bounds unavailable')
        start, end = int(bounds[0]['start_ts']), int(bounds[0]['end_ts'])
        result['traceBoundsNs'] = dict(start=start, end=end)
        if end <= start:
            reasons.append('trace-has-no-time-range')
        clocks = rows.get('clocks', [])
        mono = [x for x in clocks if int(x['clock_id']) == 3]
        boot = [x for x in clocks if int(x['clock_id']) == 6]
        if not mono or not boot:
            reasons.append('monotonic-boottime-clock-snapshots-missing')
            offsets = []
        else:
            offsets = [int(x['ts']) - int(x['clock_value']) for x in mono]
            result['clockMapping'] = dict(source='actual-clock-snapshots',
                monotonicClockId=3, boottimeClockId=6, monotonicSnapshots=len(mono),
                boottimeSnapshots=len(boot), offsetMinNs=min(offsets), offsetMaxNs=max(offsets))
            if max(offsets) - min(offsets) > 1_000_000:
                reasons.append('clock-offset-not-stable-within-one-ms')

        stats = rows.get('stats', [])
        loss_words = ('overrun', 'dropped', 'discard', 'overwrite', 'overwritten', 'loss', 'error')
        nonzero = [x for x in stats if int(x['value']) != 0 and
                   any(word in x['name'] for word in loss_words)]
        cpu_ids = {int(x['cpu']) for x in rows.get('sched', []) if int(x['events']) > 0}
        end_stats = [x for x in stats if x['idx'] not in ('[NULL]', '') and
                     x['name'] in ('ftrace_cpu_overrun_end', 'ftrace_cpu_dropped_events_end')]
        counters = {(int(x['idx']), x['name']) for x in end_stats}
        actual_loss_counters = bool(cpu_ids) and all(
            (cpu, name) in counters for cpu in cpu_ids
            for name in ('ftrace_cpu_overrun_end', 'ftrace_cpu_dropped_events_end'))
        if nonzero:
            result['lossEvidence'] = dict(state='nonzero-loss-or-parser-error', stats=nonzero)
            reasons.append('trace-loss-or-parser-errors-observed')
        elif not actual_loss_counters:
            reasons.append('actual-per-cpu-loss-counters-unavailable')
        else:
            result['lossEvidence'] = dict(state='reported-zero-for-observed-cpus', cpus=sorted(cpu_ids))
        if not cpu_ids:
            reasons.append('sched-switch-events-unavailable')
        events = {x['name']: int(x['events']) for x in rows.get('ftrace', [])}
        result['observedFtraceEvents'] = events
        if not (events.get('sched_wakeup', 0) or events.get('sched_waking', 0)):
            reasons.append('sched-wakeup-events-unavailable')
        if not events.get('binder_transaction', 0) or not events.get('binder_transaction_received', 0):
            reasons.append('binder-events-unavailable')
        slices = rows.get('slices', [])
        result['observedInputDalvikSlices'] = slices
        if not any('input' in x['name'].lower() for x in slices):
            reasons.append('input-atrace-events-unavailable')
        if not any(any(s in x['name'] for s in ('GC', 'JIT', 'Class')) or 'dalvik' in x['name'].lower() for x in slices):
            reasons.append('dalvik-events-not-observed-or-unavailable')

        original = ROOT / 'work/gecko-integration'
        report = read_json(original / 'gecko-performance-results.json')
        phase = read_json(original / 'editing-phase-environment.json')
        result['originalPerformanceStatus'] = report.get('status')
        invocations = [x for x in phase.get('workloads', []) if x.get('name') == 'original-performance-wrapper']
        if len(invocations) != 1 or invocations[0].get('invocationCount') != 1:
            reasons.append('one-original-performance-invocation-not-proven')
        receipts = report.get('nativeInputDriver', {}).get('receipts', [])
        if not receipts:
            reasons.append('no-original-native-gesture-receipts')
        for item in receipts:
            name = item['file']
            if Path(name).name != name or not name.endswith('.json'):
                raise ValueError('Unsafe original receipt reference')
            path = original / name
            receipt = read_json(path)
            if hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
                raise ValueError('Original native receipt hash mismatch')
            identity = receipt.get('buildIdentity', {})
            if any(str(identity.get(k, '')) != str(run.get(k, ''))
                   for k in ('sourceCommit', 'sourceTree', 'runId', 'runAttempt')):
                reasons.append('receipt-source-run-binding-mismatch')
            events = list(receipt.get('trace', {}).get('events', []))
            cleanup = receipt.get('trace', {}).get('cleanup')
            if isinstance(cleanup, dict):
                events.append(cleanup)
            if not events or not offsets:
                reasons.append('gesture-clock-coverage-unavailable-' + name)
                continue
            a = min(int(x['callStartUptimeMs']) for x in events) * 1_000_000
            b = max(int(x['callEndUptimeMs']) for x in events) * 1_000_000
            covered = a + min(offsets) >= start and b + max(offsets) <= end
            result['gestureCoverage'].append(dict(file=name, uptimeStartNs=a,
                uptimeEndNs=b, retainedTraceContainsWholeObservedGesture=covered))
            if not covered:
                reasons.append('gesture-outside-retained-trace-' + name)
        result['status'] = 'complete-diagnostic-evidence' if not reasons else 'incomplete'
    except Exception as error:
        result['reasons'].append(type(error).__name__ + ': ' + str(error))
    (out / 'analysis.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--trace-processor', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(analyze(args.out, args.trace_processor)))
