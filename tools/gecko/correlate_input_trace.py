#!/usr/bin/env python3
"""Offline, evidence-bound native input/Perfetto correlation; never qualification."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import time

NS_PER_MS = 1_000_000
MAX_ROWS = 100_000
MAX_CSV = 32 * 1024 * 1024
TP_DEFAULT = '/tmp/pocketchat-perfetto54/trace_processor_shell'
NULLS = {'[NULL]', 'NULL', ''}


def need(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def identity(path):
    path = Path(path)
    return dict(path=str(path.resolve()), bytes=path.stat().st_size, sha256=sha(path))


def integer(value):
    return type(value) is int


def num(row, key):
    value = row.get(key)
    if value is None or value in NULLS:
        return None
    return int(value)


def json_rows(rows):
    """Convert only obvious integer columns; original CSV always remains intact."""
    result = []
    words = {'ts', 'dur', 'cpu', 'priority', 'idx', 'value', 'id', 'tid', 'pid', 'utid', 'upid',
             'clock_id', 'clock_value', 'snapshot_id', 'machine_id', 'start_ts', 'end_ts',
             'io_wait', 'waker_utid', 'waker_id', 'is_sync', 'is_main_thread', 'open_interval',
             'slice_out', 'slice_in', 'trace_id', 'binder_txn_id', 'binder_reply_id'}
    for row in rows:
        out = {}
        for key, value in row.items():
            if value in NULLS:
                out[key] = None
            elif key in words or key.endswith(('_ns', '_tid', '_pid', '_utid', '_upid')):
                out[key] = int(value) if re.fullmatch(r'-?[0-9]+', value) else value
            else:
                out[key] = value
        result.append(out)
    return result


def parse_csv(raw):
    text = raw.decode('utf-8', errors='strict').lstrip('\r\n')
    reader = csv.DictReader(io.StringIO(text))
    need(reader.fieldnames and len(reader.fieldnames) == len(set(reader.fieldnames)), 'Invalid CSV header')
    rows = list(reader)
    need(all(None not in row and all(value is not None for value in row.values()) for row in rows), 'CSV column count differs')
    return rows


def union_ns(spans):
    total = 0
    prior = None
    for begin, end in sorted((a, b) for a, b in spans if b > a):
        if prior is None:
            prior = [begin, end]
        elif begin <= prior[1]:
            prior[1] = max(prior[1], end)
        else:
            total += prior[1] - prior[0]
            prior = [begin, end]
    return total + (prior[1] - prior[0] if prior else 0)


def overlap(row, begin, end, start_key='mono_start_ns', end_key='mono_end_ns'):
    a, b = num(row, start_key), num(row, end_key)
    if a is None or b is None or b < a:
        return None
    left, right = max(begin, a), min(end, b)
    return (left, right) if right > left else None


def state_label(state):
    if state == 'Running':
        return 'running'
    if state in ('R', 'R+'):
        return 'runnable'
    if state.startswith('S'):
        return 'sleeping-interruptible'
    if state.startswith('D'):
        return 'blocked-uninterruptible'
    return 'other:' + state


def thread_overlap(rows, tid, begin, end, *, states):
    grouped = {}
    for row in rows:
        if num(row, 'tid') != tid:
            continue
        span = overlap(row, begin, end)
        if span is None:
            continue
        key = (num(row, 'utid'), num(row, 'upid'))
        entry = grouped.setdefault(key, dict(utid=key[0], upid=key[1], tid=tid, rows=[], _spans={}, _all_spans=[]))
        value = json_rows([row])[0]
        value.update(overlapStartMonoNs=span[0], overlapEndMonoNs=span[1], overlapNs=span[1]-span[0])
        entry['rows'].append(value)
        label = state_label(row.get('state', '')) if states else 'running-from-sched'
        entry['_spans'].setdefault(label, []).append(span)
        entry['_all_spans'].append(span)
    result = []
    for entry in grouped.values():
        entry['overlapNsByState'] = {k: union_ns(v) for k, v in entry.pop('_spans').items()}
        entry['observedIntervalCoverageNs'] = union_ns(entry.pop('_all_spans'))
        entry['reportedCallWindowNs'] = end-begin
        entry['coverageFraction'] = entry['observedIntervalCoverageNs']/(end-begin) if end>begin else 0
        entry['coversReportedCall'] = entry['observedIntervalCoverageNs'] == end-begin
        entry['conflictingStateIntervals'] = states and sum(entry['overlapNsByState'].values()) > entry['observedIntervalCoverageNs']
        result.append(entry)
    return result


def binder_incomplete(row):
    client_dur,server_dur = num(row,'client_dur'),num(row,'server_dur')
    return client_dur is None or client_dur<0 or server_dur is None or server_dur<0 or num(row,'server_ts') is None or num(row,'server_tid') is None


def read_receipts(paths, slow_ms):
    receipts, windows = [], []
    for receipt_index, path in enumerate(paths):
        need(path.is_file() and not path.is_symlink() and path.stat().st_size <= 2 * 1024 * 1024,
             'Receipt must be a bounded ordinary file')
        value = json.loads(path.read_text(encoding='utf-8'))
        driver = value.get('driverPid')
        need(integer(driver) and driver > 0, 'Receipt driverPid unavailable')
        target = str(value.get('targetPidBefore', ''))
        need(re.fullmatch(r'[1-9][0-9]*', target), 'Receipt target PID unavailable')
        trace = value.get('trace', {})
        threshold = slow_ms if slow_ms is not None else trace.get('intervalMs')
        need(integer(threshold) and threshold > 0, 'Explicit/original interval threshold required')
        records = list(enumerate(trace.get('events', [])))
        if isinstance(trace.get('cleanup'), dict):
            records.append(('cleanup', trace['cleanup']))
        for event_index, event in records:
            begin, end = event.get('callStartUptimeMs'), event.get('callEndUptimeMs')
            need(integer(begin) and integer(end) and 0 <= begin <= end, 'Invalid original call timestamp')
            if end - begin <= threshold:
                continue
            windows.append(dict(windowId='r%d-e%s' % (receipt_index, event_index),
                receiptIndex=receipt_index, eventIndex=event_index, gesture=value.get('gesture'),
                driverPid=driver, targetPid=int(target), action=event.get('action'),
                cleanup=event.get('cleanup') is True, synchronousUp=event.get('sync') is True,
                beginMonoNs=begin*NS_PER_MS, endMonoNs=end*NS_PER_MS,
                reportedCallWallMs=end-begin, slowDescriptionThresholdMs=threshold,
                originalReceiptStatus=value.get('status'), originalReceiptError=value.get('error'),
                originalTraceError=trace.get('error'), originalEvent=event))
        build = value.get('buildIdentity', {})
        receipts.append(dict(file=identity(path), sourceCommit=value.get('sourceCommit'),
            sourceTree=value.get('sourceTree'), runId=build.get('runId'), runAttempt=build.get('runAttempt'),
            nonce=value.get('nonce'), gesture=value.get('gesture'), driverPid=driver,
            driverStartTicks=value.get('driverStartTicks'), targetPid=int(target),
            targetStartTicksBefore=value.get('targetStartTicksBefore'), originalStatus=value.get('status'),
            originalError=value.get('error'), traceProtocol={k: trace.get(k) for k in
                ('durationMs', 'moveCount', 'intervalMs', 'maxLateMs', 'expiresUptimeMs')}))
    cohorts = {(x['sourceCommit'], x['sourceTree'], x['runId'], x['runAttempt']) for x in receipts}
    need(len(cohorts) == 1, 'Do not correlate mixed source/run/attempt receipts against one trace')
    return receipts, windows


class Queries:
    def __init__(self, processor, trace, output):
        self.processor, self.trace, self.output = processor, trace, output
        self.records = []

    def run(self, name, sql):
        sql_file, out, err = (self.output / (name + suffix) for suffix in ('.sql', '.csv', '.stderr.log'))
        sql_file.write_text(sql + '\n', encoding='utf-8')
        command = [str(self.processor), '--full-sort', '-q', str(sql_file), str(self.trace)]
        started = time.monotonic_ns()
        record = dict(name=name, command=command, sqlFile=sql_file.name, csvFile=out.name,
                      stderrFile=err.name, diagnosticOnly=True)
        rows = []
        try:
            with out.open('xb') as stdout, err.open('xb') as stderr:
                result = subprocess.run(command, stdout=stdout, stderr=stderr, timeout=180, check=False)
            record['returnCode'] = result.returncode
            need(result.returncode == 0, 'Trace processor query failed')
            need(out.stat().st_size <= MAX_CSV, 'Query CSV exceeds analysis bound; original output retained')
            rows = parse_csv(out.read_bytes())
            record.update(status='queried', rows=len(rows), rowLimitReached=len(rows) > MAX_ROWS)
        except Exception as error:
            record.update(status='unavailable', errorType=type(error).__name__, error=str(error))
        record.update(startedMonotonicNs=started, completedMonotonicNs=time.monotonic_ns())
        for key, file in (('sqlIdentity', sql_file), ('csvIdentity', out), ('stderrIdentity', err)):
            if file.is_file():
                record[key] = identity(file)
        self.records.append(record)
        return rows


def ids(values):
    values = sorted(set(values))
    need(all(integer(x) and x >= 0 for x in values), 'Only parsed nonnegative numeric IDs may enter SQL')
    return ','.join(map(str, values)) if values else '-1'


def run(args):
    need(args.trace.is_file() and not args.trace.is_symlink() and args.trace.stat().st_size <= 512*1024*1024,
         'Trace must be a bounded ordinary file')
    need(args.processor.is_file() and not args.processor.is_symlink(), 'Ordinary trace processor required')
    need(not args.out.exists(), 'Output already exists; preserve earlier analysis')
    receipts, windows = read_receipts(args.receipt, args.slow_call_ms)
    originals = [identity(args.trace), *[identity(p) for p in args.receipt]]
    processor_identity, helper_identity = identity(args.processor), identity(Path(__file__))
    args.out.mkdir(parents=True)
    with (args.out/'processor-version.stdout.log').open('xb') as stdout, (args.out/'processor-version.stderr.log').open('xb') as stderr:
        version_run=subprocess.run([str(args.processor),'--version'],stdout=stdout,stderr=stderr,timeout=10,check=False)
    need(version_run.returncode == 0, 'Trace processor version query failed; raw logs retained')
    version_text=(args.out/'processor-version.stdout.log').read_text()+(args.out/'processor-version.stderr.log').read_text()
    need('Perfetto v54.' in version_text, 'This helper was verified against Trace Processor v54')
    q = Queries(args.processor, args.trace, args.out)
    drivers = [r['driverPid'] for r in receipts]
    targets = [r['targetPid'] for r in receipts]
    limit = ' LIMIT %d;' % (MAX_ROWS+1)
    clock = q.run('clock-snapshots', 'SELECT * FROM clock_snapshot ORDER BY snapshot_id,clock_id' + limit)
    bounds = q.run('trace-bounds', 'SELECT start_ts,end_ts,to_monotonic(start_ts) AS mono_start_ns,to_monotonic(end_ts) AS mono_end_ns FROM trace_bounds;')
    stats = q.run('trace-stats', 'SELECT name,idx,severity,source,value,description FROM stats WHERE value != 0 ORDER BY severity,name,idx' + limit)
    metadata = q.run('trace-metadata', 'SELECT * FROM metadata ORDER BY id' + limit)
    thread_rows = q.run('threads', '''SELECT t.utid,t.tid,t.name AS thread_name,t.start_ts,t.end_ts,t.is_main_thread,t.machine_id,
        p.upid,p.pid,p.name AS process_name,p.uid,p.cmdline,to_monotonic(t.start_ts) AS thread_start_mono_ns,
        to_monotonic(t.end_ts) AS thread_end_mono_ns
        FROM thread t LEFT JOIN process p ON p.upid=t.upid
        WHERE t.tid IN (%s) OR p.pid IN (%s) ORDER BY t.utid%s''' % (ids(drivers), ids(targets), limit))
    binder = q.run('binder-transactions', '''INCLUDE PERFETTO MODULE android.binder;
        SELECT b.*,to_monotonic(client_ts) AS client_mono_start_ns,
        to_monotonic(client_ts+CASE WHEN client_dur IS NULL OR client_dur<0 THEN (SELECT end_ts FROM trace_bounds)-client_ts ELSE client_dur END) AS client_mono_end_ns,
        CASE WHEN client_dur IS NULL OR client_dur<0 THEN 1 ELSE 0 END AS client_end_projected,
        CASE WHEN server_ts IS NOT NULL THEN to_monotonic(server_ts) END AS server_mono_start_ns,
        CASE WHEN server_ts IS NOT NULL THEN to_monotonic(server_ts+CASE WHEN server_dur IS NULL OR server_dur<0 THEN (SELECT end_ts FROM trace_bounds)-server_ts ELSE server_dur END) END AS server_mono_end_ns,
        CASE WHEN server_ts IS NULL OR server_dur IS NULL OR server_dur<0 THEN 1 ELSE 0 END AS server_end_projected
        FROM android_binder_txns b WHERE client_tid IN (%s) OR client_pid IN (%s) ORDER BY client_ts%s''' % (ids(drivers), ids(drivers), limit))
    servers = [num(r, 'server_tid') for r in binder if num(r, 'server_tid') is not None]
    selected_tids = ids(drivers + targets + servers)
    sched = q.run('sched', '''SELECT s.*,t.tid,t.name AS thread_name,t.upid,p.pid,p.name AS process_name,t.machine_id,
        to_monotonic(s.ts) AS mono_start_ns,
        to_monotonic(s.ts+CASE WHEN s.dur<0 THEN (SELECT end_ts FROM trace_bounds)-s.ts ELSE s.dur END) AS mono_end_ns,
        CASE WHEN s.dur<0 THEN 1 ELSE 0 END AS open_interval
        FROM sched s JOIN thread t ON t.utid=s.utid LEFT JOIN process p ON p.upid=t.upid
        WHERE t.tid IN (%s) ORDER BY s.ts%s''' % (selected_tids, limit))
    states = q.run('thread-states', '''SELECT s.*,t.tid,t.name AS thread_name,t.upid,p.pid,p.name AS process_name,t.machine_id,
        to_monotonic(s.ts) AS mono_start_ns,
        to_monotonic(s.ts+CASE WHEN s.dur<0 THEN (SELECT end_ts FROM trace_bounds)-s.ts ELSE s.dur END) AS mono_end_ns,
        CASE WHEN s.dur<0 THEN 1 ELSE 0 END AS open_interval
        FROM thread_state s JOIN thread t ON t.utid=s.utid LEFT JOIN process p ON p.upid=t.upid
        WHERE t.tid IN (%s) ORDER BY s.ts%s''' % (selected_tids, limit))
    flow_ids = [num(r, k) for r in binder for k in ('binder_txn_id', 'binder_reply_id') if num(r, k) is not None]
    flows = q.run('binder-flows', '''SELECT f.*,o.ts AS out_ts,o.dur AS out_dur,o.name AS out_name,
        i.ts AS in_ts,i.dur AS in_dur,i.name AS in_name,
        to_monotonic(o.ts) AS out_mono_ns,to_monotonic(i.ts) AS in_mono_ns
        FROM flow f JOIN slice o ON o.id=f.slice_out JOIN slice i ON i.id=f.slice_in
        WHERE f.slice_out IN (%s) OR f.slice_in IN (%s) ORDER BY o.ts%s''' % (ids(flow_ids), ids(flow_ids), limit))
    loss = [r for r in stats if (num(r, 'value') or 0) > 0 and
            (r.get('severity') in ('error','data_loss') or re.search(r'lost|loss|drop|overrun|truncat|parse_error|clock_sync_failure', r.get('name',''), re.I))]
    query_limits = [r['name'] for r in q.records if r.get('rowLimitReached')]
    query_errors = [r['name'] for r in q.records if r['status'] != 'queried']
    mono_clocks = [r for r in clock if num(r,'clock_id') == 3]
    machine_ids = {num(r,'machine_id') for r in clock}
    multi_machine = len(machine_ids) > 1
    trace_begin = num(bounds[0],'mono_start_ns') if bounds else None
    trace_end = num(bounds[0],'mono_end_ns') if bounds else None
    for w in windows:
        begin,end,tid = w['beginMonoNs'],w['endMonoNs'],w['driverPid']
        driver_states = thread_overlap(states,tid,begin,end,states=True)
        driver_sched = thread_overlap(sched,tid,begin,end,states=False)
        w.update(driverThreadStates=driver_states, driverRunningFromSched=driver_sched,
                 pidCandidateThreads=json_rows([r for r in thread_rows if num(r,'tid') == tid]),
                 pidGenerationIndependentlyVerified=False,
                 traceBoundsCoverReportedCall=trace_begin is not None and trace_end is not None and trace_begin <= begin and trace_end >= end,
                 clockConversionAvailable=bool(driver_states or driver_sched),
                 multipleDriverUtidCandidates=len({r['utid'] for r in driver_states+driver_sched}) > 1,
                 driverThreadStateCoversReportedCall=len(driver_states)==1 and driver_states[0]['coversReportedCall'] and not driver_states[0]['conflictingStateIntervals'],
                 monotonicSnapshotsBracketCall=bool(mono_clocks) and min(num(r,'clock_value') for r in mono_clocks) <= begin and max(num(r,'clock_value') for r in mono_clocks) >= end)
        transactions=[]
        for row in binder:
            if num(row,'client_tid') != tid:
                continue
            span=overlap(row,begin,end,'client_mono_start_ns','client_mono_end_ns')
            if span is None:
                continue
            item=json_rows([row])[0]
            server_tid=num(row,'server_tid')
            item.update(clientCallOverlapNs=span[1]-span[0],
                clientEndProjectedToTraceBounds=num(row,'client_end_projected')==1,
                serverEndProjectedOrUnavailable=num(row,'server_end_projected')==1,
                binderSpanIncomplete=binder_incomplete(row),
                serverThreadStatesOverReportedCall=thread_overlap(states,server_tid,begin,end,states=True) if server_tid else [],
                serverRunningOverReportedCall=thread_overlap(sched,server_tid,begin,end,states=False) if server_tid else [],
                matchingFlowRows=json_rows([f for f in flows if num(f,'slice_out') in (num(row,'binder_txn_id'),num(row,'binder_reply_id')) or num(f,'slice_in') in (num(row,'binder_txn_id'),num(row,'binder_reply_id'))]),
                temporalOverlapOnly=True, uniqueCauseEstablished=False)
            transactions.append(item)
        w.update(overlappingBinderTransactions=transactions,uniqueCauseEstablished=False)
        w['incompleteBinderEvidence']=any(t['binderSpanIncomplete'] for t in transactions)
        w['coveragePartial']=not w['driverThreadStateCoversReportedCall'] or w['multipleDriverUtidCandidates'] or w['incompleteBinderEvidence']
    report=dict(schema=1,status='offline-diagnostic-analysis',diagnosticOnly=True,
        applicationAcceptance=False,releaseAcceptance=False,physicalPhoneAcceptance=False,
        protectionEffectivenessAcceptance=False,uniqueCauseEstablished=False,
        trace=originals[0],receipts=receipts,processor=processor_identity,helper=helper_identity,
        processorVersion=version_text.strip(),
        traceReceiptSourceBindingIndependentlyEstablished=False,
        clockDomain=dict(receipt='Android SystemClock.uptimeMillis = CLOCK_MONOTONIC, milliseconds',
            trace='Perfetto unified trace clock; not assumed to be monotonic or boottime',
            conversion='Trace Processor v54 to_monotonic(ts), driven by trace clock snapshots',
            receiptTimestampQuantizationNs=NS_PER_MS,monotonicSnapshotCount=len(mono_clocks),
            multipleMachinesObserved=multi_machine,boundsMonotonicNs=dict(start=trace_begin,end=trace_end)),
        quality=dict(lossOrParseIssueStats=json_rows(loss),queryErrors=query_errors,queryRowLimits=query_limits,
            incompleteBinderWindows=[w['windowId'] for w in windows if w['incompleteBinderEvidence']],
            driverCoveragePartialWindows=[w['windowId'] for w in windows if not w['driverThreadStateCoversReportedCall'] or w['multipleDriverUtidCandidates']],
            slowCallWindows=len(windows),noLossObserved=not loss,
            partial=bool(loss or query_errors or query_limits or multi_machine or trace_begin is None or trace_end is None or any(not w['traceBoundsCoverReportedCall'] or not w['clockConversionAvailable'] or w['coveragePartial'] for w in windows))),
        windows=windows,queries=q.records,
        limitations=[
            'All output is diagnostic. Original receipt status/error remains unchanged and cannot qualify a failed workload.',
            'Per-call uptime fields are millisecond-quantized: interval edges have up to one millisecond uncertainty.',
            'Perfetto clock conversion is never replaced by a guessed constant offset. Null conversion, uncovered bounds, loss or query truncation limits correlation.',
            'PID-window candidates are shown but /proc startTicks generation is not independently converted without an actual CLK_TCK/creation binding.',
            'Running-from-sched and thread_state overlap totals are alternative observations; do not add them together.',
            'Incomplete Binder endpoints projected to trace bounds are explicitly labelled and make the window partial; projected ends are not actual reply times.',
            'Thread-state coverage is checked separately per UTID. Gaps, conflicting states or PID-reuse candidates cannot be merged into complete coverage.',
            'Sleep state overlapping a Binder transaction does not establish that Binder alone caused the elapsed delay. Runnable delay does not alone attribute host contention.',
            'Synchronous final UP may legally finish after its event slot if it stays inside the original AUT deadline; the slow-call filter is descriptive, not an oracle.',
            'Tracing can perturb scheduling. A successful diagnostic invocation does not retrospectively repair earlier failures or prove phone performance.',
            'Trace/receipt source/run correspondence requires the external capture manifest and original artifact audit; this helper preserves hashes but does not invent that proof.'
        ])
    need(originals == [identity(args.trace), *[identity(p) for p in args.receipt]], 'Original trace/receipts changed during analysis')
    need(processor_identity == identity(args.processor) and helper_identity == identity(Path(__file__)), 'Analysis executable changed during analysis')
    report['originalInputsUnchanged']=True
    (args.out/'analysis.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=report['status'],diagnosticOnly=True,windows=len(windows),partial=report['quality']['partial'],
        applicationAcceptance=False,releaseAcceptance=False,analysis=str(args.out/'analysis.json'))))
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--trace',type=Path,required=True)
    p.add_argument('--receipt',type=Path,action='append',required=True)
    p.add_argument('--processor',type=Path,default=Path(TP_DEFAULT))
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--slow-call-ms',type=int,help='Descriptive threshold only; default uses each original intervalMs')
    run(p.parse_args())


if __name__=='__main__':
    main()
