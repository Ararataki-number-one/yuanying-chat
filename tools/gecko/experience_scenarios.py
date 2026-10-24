"""Frozen synthetic inputs and honest interval accounting; no Android stand-ins."""
import hashlib
import json
import math

NAMES = ('core', 'download-history-0', 'download-history-1000', 'download-history-3000', 'idle-120')
GAPS = {
    'P02': 'The external SOCKS core flow does not execute the internal Mihomo configuration/provider parse path. A dedicated real internal-core fixture and parse stage observations are required.',
    'P04': 'The static cookie preservation check does not count actual WebExtension getAll/storage writes or checkpoint latency. A real cookie burst and persistence barrier/restart fixture is required.',
    'F03': 'This flow does not invoke the real Gecko picker/file handoff. DOM completion alone does not prove that Gecko has released an upload copy; actual file ownership and picker fixture evidence is required.',
}


def manifest(name):
    if name not in NAMES:
        raise ValueError('Unsupported measured scenario: ' + str(name))
    value = dict(schema=1, name=name, coreFlowVersion=1,
                 fixture=dict(historicalPairs=120, replyRepeats=5000,
                              draft='unsent benchmark draft 中文 code()',
                              cookie='session=synthetic-experience'))
    if name.startswith('download-history-'):
        value['downloadHistory'] = dict(savedRows=int(name.rsplit('-', 1)[1]),
            progressRows=1, saveSteps=8, stepBytes=65536, intervalMs=2000,
            savedFileBytesHex='657870657269656e63652d666978747572650a',
            baseTimestampMs=1700000000000, recordContractVersion=1,
            scope='Actual DownloadTasks.save on the main thread and actual SQLite/prefs; controlled paused-record byte changes, not HTTP transfer throughput or production progress cadence.')
    if name == 'idle-120':
        value['idle'] = dict(foregroundMs=120000, backgroundMs=120000,
            scope='Normal app timers remain enabled; target 120 s foreground chat then HOME/background, ended by one device handler callback with actual overshoot retained. External process sampling continues, no periodic app broadcasts or JavaScript probes during either idle interval.')
    return value


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def cpu_window(samples, hz, start_elapsed_ms, end_elapsed_ms, summarize):
    """Use only complete actual /proc sample envelopes inside device elapsed bounds.

    Android elapsedRealtime and /proc/uptime share Linux boot-time semantics;
    native frame timestamps instead use uptime and must not be mixed with these.
    No interpolation, manufactured boundary counters, or missing-as-zero values.
    """
    if not all(type(v) in (int, float) and math.isfinite(v) for v in (start_elapsed_ms, end_elapsed_ms)) or end_elapsed_ms <= start_elapsed_ms:
        raise ValueError('Ordered finite device elapsedRealtime boundaries required')
    indices = [i for i, row in enumerate(samples)
               if row.get('uptimeSeconds') is not None and row.get('uptimeEndSeconds') is not None
               and row['uptimeSeconds'] * 1000 >= start_elapsed_ms
               and row['uptimeEndSeconds'] * 1000 <= end_elapsed_ms]
    chosen = [samples[i] for i in indices]
    result = summarize(chosen, hz)
    result.update(requestedStartElapsedMs=start_elapsed_ms, requestedEndElapsedMs=end_elapsed_ms,
                  requestedDurationMs=end_elapsed_ms-start_elapsed_ms,
                  sampleIndices=indices, boundaryInterpolation=False,
                  clockSource='Device SystemClock.elapsedRealtime window; /proc/uptime sample envelopes. These include suspend; native HWUI/Choreographer use uptime and are separate.',
                  boundaryScope='Complete sample envelopes only. Unsampled leading/trailing time and short-lived processes are not estimated. Observations are sequential, not atomic; CPU includes the unchanged sampler/evidence overhead.')
    if chosen:
        result['observedEnvelopeStartMs'] = chosen[0]['uptimeSeconds'] * 1000
        result['observedEnvelopeEndMs'] = chosen[-1]['uptimeEndSeconds'] * 1000
        result['unobservedLeadingMs'] = result['observedEnvelopeStartMs'] - start_elapsed_ms
        result['unobservedTrailingMs'] = end_elapsed_ms - result['observedEnvelopeEndMs']
    return result


def pss_value(raw, pid):
    """Reject stale/missing dumpsys output rather than reusing a previous PID."""
    import re
    header = re.search(r'\*\* MEMINFO in pid (\d+) \[([^\]]+)\] \*\*', raw)
    matched = re.search(r'^\s*TOTAL PSS:\s*(\d+)', raw, re.M) or re.search(r'^\s*TOTAL\s+(\d+)\s', raw, re.M)
    if not header or int(header[1]) != pid or not matched:
        raise ValueError('No matching successful process dumpsys PSS record')
    return dict(pssKb=int(matched[1]), observedProcess=header[2])
