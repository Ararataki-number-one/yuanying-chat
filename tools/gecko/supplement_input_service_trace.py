#!/usr/bin/env python3
"""Bounded offline context for existing slow-call observations, never acceptance."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import resource
import subprocess
import time

MAX_TRACE = 256 * 1024 * 1024
MAX_ANALYSIS = 32 * 1024 * 1024
MAX_OUTPUT = 8 * 1024 * 1024
MAX_REPORT = 4 * 1024 * 1024
MAX_ROWS = 20_000
MAX_WINDOWS = 44
MAX_IDS = 512
QUERY_TIMEOUT = 60
HELPER_SHA = '63ecae013dcc2f8e0232aa588ffcb7c57839cb99b0c4adb742ab7e2ca6d028f0'
PROCESSOR_SHA = 'a7aa1f738bbe2926a70f0829d00837f5720be8cafe26de78f962094fa24a3da4'
FLAGS = dict(diagnosticOnly=True, applicationAcceptance=False, releaseAcceptance=False,
             physicalPhoneAcceptance=False, protectionEffectivenessAcceptance=False,
             uniqueCauseEstablished=False)


def need(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def identity(path):
    need(path.is_file() and not path.is_symlink(), 'Ordinary input file required')
    return dict(bytes=path.stat().st_size, sha256=sha(path))


def bounded(path, maximum):
    need(path.is_file() and not path.is_symlink() and 0 < path.stat().st_size <= maximum,
         'Input is missing, special, empty or exceeds size bound')


def number(value):
    return type(value) is int and 0 <= value <= 2**63-1


def windows_from(report):
    need(report.get('diagnosticOnly') is True and
         all(report.get(k) is False for k in ('applicationAcceptance', 'releaseAcceptance',
                                             'physicalPhoneAcceptance', 'protectionEffectivenessAcceptance',
                                             'uniqueCauseEstablished')),
         'Original diagnostic scope required')
    need(report.get('helper', {}).get('sha256') == HELPER_SHA, 'Reviewed helper binding differs')
    values = report.get('windows')
    need(isinstance(values, list) and len(values) <= MAX_WINDOWS, 'Slow-window count exceeds bound')
    bounds = report.get('clockDomain', {}).get('boundsMonotonicNs', {})
    lo, hi = bounds.get('start'), bounds.get('end')
    valid_bounds = number(lo) and number(hi) and lo <= hi
    selected, skipped, seen = [], [], set()
    for item in values:
        key = item.get('windowId')
        need(isinstance(key, str) and re.fullmatch(r'r[0-9]+-e(?:[0-9]+|cleanup)', key)
             and key not in seen, 'Invalid or duplicate window ID')
        seen.add(key)
        begin, end = item.get('beginMonoNs'), item.get('endMonoNs')
        need(number(begin) and number(end) and begin < end and end-begin <= 20_000_000_000,
             'Invalid or oversized call window')
        need(number(item.get('driverPid')) and 0 < item['driverPid'] <= 2**31-1
             and number(item.get('targetPid')) and 0 < item['targetPid'] <= 2**31-1,
             'Invalid numeric process IDs')
        need(type(item.get('action')) is int and item['action'] in (0,1,2,3)
             and type(item.get('synchronousUp')) is bool
             and item.get('originalReceiptStatus') in ('passed','failed'), 'Invalid original event/status')
        reasons = []
        if not valid_bounds or begin < lo or end > hi:
            reasons.append('outside-valid-monotonic-trace-bounds')
        if item.get('traceBoundsCoverReportedCall') is not True:
            reasons.append('original-analysis-reports-uncovered-window')
        if item.get('clockConversionAvailable') is not True:
            reasons.append('original-analysis-clock-conversion-unavailable')
        if reasons:
            skipped.append(dict(windowId=key, reasons=reasons))
        else:
            selected.append(item)
    return selected, skipped


def ids(values):
    value = sorted(set(values))
    need(len(value) <= MAX_IDS and all(number(v) and 0 < v <= 2**31-1 for v in value), 'Invalid/too many thread IDs')
    return ','.join(map(str, value)) if value else '-1'


def query_texts(windows):
    need(0 < len(windows) <= MAX_WINDOWS, 'Nonempty bounded windows required')
    rows = ','.join("('%s',%d,%d,%d,%d)" %
                    (w['windowId'], w['beginMonoNs'], w['endMonoNs'], w['driverPid'], w['targetPid'])
                    for w in windows)
    common = 'WITH windows(window_id,begin_ns,end_ns,driver_tid,target_pid) AS (VALUES ' + rows + ')'
    limit = ' LIMIT %d;' % (MAX_ROWS + 1)
    drivers = ids([w['driverPid'] for w in windows])
    targets = ids([w['targetPid'] for w in windows])
    servers = []
    for w in windows:
        txns = w.get('overlappingBinderTransactions', [])
        need(isinstance(txns, list) and len(txns) <= MAX_IDS, 'Binder transaction count exceeds bound')
        for txn in txns:
            tid = txn.get('server_tid')
            if tid is not None:
                need(number(tid) and tid > 0, 'Invalid server TID')
                servers.append(tid)
    service_ids = ids(servers)
    # Strings are hex-encoded before v54 CSV output; untrusted names never enter SQL.
    context_filter = """(t.tid IN (%s,%s) OR p.pid IN (%s) OR p.name='system_server'
       OR lower(t.name) LIKE '%%inputdispatcher%%' OR lower(t.name) LIKE '%%inputreader%%'
       OR lower(t.name) LIKE '%%heap%%daemon%%' OR lower(t.name) LIKE '%%gc%%daemon%%'
       OR lower(p.name) LIKE '%%inputflinger%%')""" % (drivers, service_ids, targets)
    cpu = common + """, normalized AS (
      SELECT s.cpu,s.utid,t.tid,hex(t.name) AS thread_name_utf8_hex,p.pid,
        hex(p.name) AS process_name_utf8_hex,to_monotonic(s.ts) AS mono_start_ns,
        to_monotonic(s.ts+CASE WHEN s.dur<0 THEN (SELECT end_ts FROM trace_bounds)-s.ts ELSE s.dur END) AS mono_end_ns,
        CASE WHEN s.dur<0 THEN 1 ELSE 0 END AS open_interval
      FROM sched s JOIN thread t ON t.utid=s.utid LEFT JOIN process p ON p.upid=t.upid
    ), grouped AS (
      SELECT w.window_id,n.cpu,n.utid,n.tid,n.thread_name_utf8_hex,n.pid,n.process_name_utf8_hex,
        SUM(MIN(n.mono_end_ns,w.end_ns)-MAX(n.mono_start_ns,w.begin_ns)) AS running_ns,
        COUNT(*) AS sched_segments,MAX(n.open_interval) AS includes_open_interval
      FROM windows w JOIN normalized n ON n.mono_end_ns>w.begin_ns AND n.mono_start_ns<w.end_ns
      GROUP BY w.window_id,n.cpu,n.utid,n.tid,n.thread_name_utf8_hex,n.pid,n.process_name_utf8_hex
    ), ranked AS (
      SELECT *,ROW_NUMBER() OVER(PARTITION BY window_id,cpu ORDER BY running_ns DESC,utid) AS cpu_rank,
        SUM(running_ns) OVER(PARTITION BY window_id,cpu) AS cpu_all_threads_running_ns,
        COUNT(*) OVER(PARTITION BY window_id,cpu) AS cpu_all_thread_groups FROM grouped
    ) SELECT * FROM ranked WHERE cpu_rank<=20 ORDER BY window_id,cpu,cpu_rank""" + limit
    slices = common + """, normalized AS (
      SELECT s.id,s.parent_id,s.depth,s.track_id,hex(s.name) AS slice_name_utf8_hex,
        hex(s.category) AS category_utf8_hex,t.utid,t.tid,hex(t.name) AS thread_name_utf8_hex,
        p.pid,hex(p.name) AS process_name_utf8_hex,to_monotonic(s.ts) AS mono_start_ns,
        to_monotonic(s.ts+CASE WHEN s.dur<0 THEN (SELECT end_ts FROM trace_bounds)-s.ts ELSE s.dur END) AS mono_end_ns,
        CASE WHEN s.dur<0 THEN 1 ELSE 0 END AS open_interval
      FROM slice s JOIN thread_track tt ON tt.id=s.track_id JOIN thread t ON t.utid=tt.utid
      LEFT JOIN process p ON p.upid=t.upid WHERE """ + context_filter + """
    ) SELECT w.window_id,n.*,MAX(n.mono_start_ns,w.begin_ns) AS overlap_start_ns,
      MIN(n.mono_end_ns,w.end_ns) AS overlap_end_ns FROM windows w JOIN normalized n
      ON n.mono_end_ns>w.begin_ns AND n.mono_start_ns<w.end_ns
      ORDER BY w.window_id,n.mono_start_ns,n.id""" + limit
    states = common + """, normalized AS (
      SELECT s.id,s.utid,t.tid,hex(t.name) AS thread_name_utf8_hex,p.pid,
        hex(p.name) AS process_name_utf8_hex,hex(s.state) AS state_utf8_hex,
        s.io_wait,hex(s.blocked_function) AS blocked_function_utf8_hex,s.waker_utid,
        to_monotonic(s.ts) AS mono_start_ns,
        to_monotonic(s.ts+CASE WHEN s.dur<0 THEN (SELECT end_ts FROM trace_bounds)-s.ts ELSE s.dur END) AS mono_end_ns,
        CASE WHEN s.dur<0 THEN 1 ELSE 0 END AS open_interval
      FROM thread_state s JOIN thread t ON t.utid=s.utid LEFT JOIN process p ON p.upid=t.upid
      WHERE """ + context_filter + """
    ) SELECT w.window_id,n.*,MAX(n.mono_start_ns,w.begin_ns) AS overlap_start_ns,
      MIN(n.mono_end_ns,w.end_ns) AS overlap_end_ns FROM windows w JOIN normalized n
      ON n.mono_end_ns>w.begin_ns AND n.mono_start_ns<w.end_ns
      ORDER BY w.window_id,n.mono_start_ns,n.utid""" + limit
    return {'cpu-window-top-threads': cpu, 'input-art-thread-slices': slices,
            'input-service-thread-states': states}


def parse_csv(raw):
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8', errors='strict').lstrip('\r\n')))
    need(reader.fieldnames and len(set(reader.fieldnames)) == len(reader.fieldnames), 'Invalid CSV header')
    rows = list(reader)
    need(len(rows) <= MAX_ROWS+1 and all(None not in row and all(v is not None for v in row.values()) for row in rows),
         'CSV exceeds rows or has unequal columns')
    for row in rows:
        for key, value in row.items():
            if key.endswith('_utf8_hex'):
                need(re.fullmatch(r'(?:[0-9A-F]{2})*', value) is not None, 'Invalid string hex')
                # Decode only after strict CSV parsing. Raw hex output is retained exactly.
                bytes.fromhex(value).decode('utf-8', errors='strict')
    return rows


def output_limit():
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_OUTPUT, MAX_OUTPUT))


def execute(processor, trace, output, name, sql):
    paths = {k: output/(name+suffix) for k,suffix in
             [('sql','.sql'),('csv','.csv'),('stderr','.stderr.log')]}
    paths['sql'].write_text(sql+'\n', encoding='utf-8')
    record = dict(name=name, **FLAGS)
    started = time.monotonic_ns()
    try:
        with paths['csv'].open('xb') as stdout, paths['stderr'].open('xb') as stderr:
            run = subprocess.run([str(processor),'--full-sort','-q',str(paths['sql']),str(trace)],
                                 stdout=stdout,stderr=stderr,timeout=QUERY_TIMEOUT,check=False,
                                 preexec_fn=output_limit)
        record['returnCode'] = run.returncode
        need(run.returncode == 0, 'Trace processor query failed or hit output bound')
        need(paths['csv'].stat().st_size < MAX_OUTPUT, 'Query reached output byte bound')
        rows = parse_csv(paths['csv'].read_bytes())
        counts = {}
        for row in rows:
            counts[row['window_id']] = counts.get(row['window_id'],0)+1
        truncated=[]
        projection=[]
        for index,row in enumerate(rows[:12]):
            projection.append({k:v[:512] for k,v in row.items()})
            truncated.extend(dict(row=index,field=k) for k,v in row.items() if len(v)>512)
        record.update(status='queried', rows=len(rows), rowsPerWindow=counts, rowLimitReached=len(rows)>MAX_ROWS,
                      projection=projection, projectionTruncatedFields=truncated)
    except Exception as error:
        record.update(status='unavailable',errorType=type(error).__name__,error=str(error))
    record['elapsedMs'] = (time.monotonic_ns()-started)//1_000_000
    record['files'] = {key:dict(path=file.name,**identity(file)) for key,file in paths.items() if file.is_file()}
    return record


def run(args):
    need(not args.out.exists() and not args.out.is_symlink(), 'Fresh output required; earlier evidence is preserved')
    bounded(args.trace, MAX_TRACE); bounded(args.analysis, MAX_ANALYSIS)
    need(args.processor.is_file() and not args.processor.is_symlink(), 'Ordinary processor required')
    original_analysis, original_trace = identity(args.analysis), identity(args.trace)
    report = json.loads(args.analysis.read_text(encoding='utf-8'))
    need(all(report.get('trace',{}).get(k)==v for k,v in original_trace.items()), 'Trace identity differs from original analysis')
    need(identity(args.processor)['sha256']==PROCESSOR_SHA and report.get('processor',{}).get('sha256')==PROCESSOR_SHA,
         'Pinned actual v54 processor binding differs')
    selected, skipped = windows_from(report)
    args.out.mkdir(parents=True)
    result = dict(schema=1,status='skipped-no-covered-slow-windows',**FLAGS,
        trace=original_trace,originalAnalysis=original_analysis,script=identity(Path(__file__)),
        selectedWindows=[dict(windowId=w['windowId'],beginMonoNs=w['beginMonoNs'],endMonoNs=w['endMonoNs'],
                              driverPid=w['driverPid'],targetPid=w['targetPid'],action=w.get('action'),
                              synchronousUp=w.get('synchronousUp'),originalReceiptStatus=w.get('originalReceiptStatus')) for w in selected],
        skippedWindows=skipped,queries=[],
        inheritedQualitySummary=dict(partial=report.get('quality',{}).get('partial',True),
            issueCounts={k:len(report.get('quality',{}).get(k,[])) for k in
                         ('lossOrParseIssueStats','queryErrors','queryRowLimits','incompleteBinderWindows','driverCoveragePartialWindows')}),
        partial=True,
        limits=dict(maxWindows=MAX_WINDOWS,maxRowsPerQuery=MAX_ROWS,maxRawBytesPerQueryFile=MAX_OUTPUT,
                    queryTimeoutSeconds=QUERY_TIMEOUT,topThreadsPerCpu=20),
        limitations=['Temporal context only; no unique blocking cause or acceptance is inferred.',
          'Top20 thread groups per CPU are ranked by time over the call; they are not proven competitors while the caller was runnable.',
          'Thread-track slices only. Missing input/ART slices do not prove no locks/GC; lock owners and native stacks may be unavailable.',
          'Hex avoids additional CSV quoting loss, but cannot recover upstream parser/string-table truncation. Empty and SQL NULL names both encode as empty hex; no name-based identity is inferred.',
          'Open intervals, trace loss, row/byte/time bounds and original quality issues remain partial evidence.',
          'UP wait exceeding15ms alone is not an original performance failure; all original outcomes remain unchanged.'])
    if selected:
        result['queries'] = [execute(args.processor,args.trace,args.out,name,sql)
                             for name,sql in query_texts(selected).items()]
        result['status'] = 'context-queries-completed' if all(q['status']=='queried' for q in result['queries']) else 'context-partly-unavailable'
    result['originalInputsUnchanged'] = identity(args.trace)==original_trace and identity(args.analysis)==original_analysis
    result['queryExecutionComplete'] = bool(selected) and all(q['status']=='queried' and not q.get('rowLimitReached') for q in result['queries'])
    # These bounded contextual views deliberately do not prove complete causal coverage.
    result['partial'] = True
    raw=(json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    need(len(raw)<=MAX_REPORT,'Supplemental report exceeds bound')
    (args.out/'supplemental-analysis.json').write_bytes(raw)
    print(json.dumps(dict(status=result['status'],coveredWindows=len(selected),skippedWindows=len(skipped),
                          partial=result['partial'],report='supplemental-analysis.json',**FLAGS)))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('processor','trace','analysis','out'):
        parser.add_argument('--'+name,required=True,type=Path)
    args=parser.parse_args()
    run(args)


if __name__=='__main__':
    main()
