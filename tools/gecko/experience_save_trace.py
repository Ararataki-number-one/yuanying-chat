"""Strict ART v2/v3 non-streaming trace decoding for an extra diagnostic pass.

ART sampling emits stack-difference enter/exit records, not exact method edges.
Clock-weighted residence below is descriptive and never a benchmark duration or
a count of 1ms samples. Missing/overflowed/truncated evidence is rejected.

Format reference (Android15-derived source, not the pinned emulator binary):
LineageOS/android_art@95cd44650afc3f76f0e31dedcd6b736912d5c4a0,
runtime/trace.cc: GetThreadEncoding, CompareAndUpdateStackTrace, CreateSummary,
GetMethodLine, FlushEntriesFormatV1; runtime/trace.h: v2/v3 constants.
Public sampling passes flags=0 in android_frameworks_base@e1d69875104b9004b7a8bcbd2af590af8f7fd41a,
core/java/android/os/Debug.java. Every actual file must still pass runtime checks.
"""
import hashlib
import json
import math
from pathlib import Path
import re
import struct

from integration_event_contract import decode_event, parse_receipt_line
from profile_invocation_contract import verify_installed

BUFFER_BYTES = 16 * 1024 * 1024
MAX_FILE_BYTES = 32 * 1024 * 1024
INTERVAL_US = 1000
ACTION = 'experienceHistorySaveSampling'
RESULT_FILE = 'history-save-sampling-results.json'
TRACE_FILE = 'history-save.trace'
OBSERVERS = ('tools/gecko/experience_save_trace.py',
             'tools/gecko/run_experience_save_diagnostic.py',
             'tests/gecko/ExperienceSaveSampling.java',
             'tests/gecko/ExperienceBenchmarkActivity.java',
             'tests/gecko/ExperienceScenarios.java',
             'tests/gecko/IntegrationEvidenceProvider.java',
             'tests/gecko/run_experience_benchmark.py',
             'tools/gecko/experience_scenarios.py',
             'engine-probe/tests/run_device.py',
             'tools/gecko/integration_event_contract.py',
             'tools/gecko/profile_invocation_contract.py',
             'tools/gecko/sdk_identity_contract.py')
CATEGORIES = ('library-prune', 'library-sync', 'library-add', 'preferences-commit',
              'json-outside-library', 'other-save-stack')
LIMITS = ('ART sampling infers method entry/exit from successive sampled stacks; these are not exact method boundaries or call counts.',
          'The requested 1000us interval is nominal. Scheduling, stop-the-world stack walks and GC/profiler overhead remain; actual sample cadence is not reconstructed.',
          'Residence is weighted only between observed stack-change records. Initial/final uncovered tails and methods missed between samples are not estimated.',
          'Only the identified main thread in the traced main process is classified. Gecko child processes, native call stacks and display presentation are outside this trace.',
          'Categories are disjoint: the outermost named library stage wins; commit/JSON are classified only outside a library stage. Other-save-stack is a composite remainder, not a JSON or commit attribution.',
          'This extra diagnostic is excluded from all 12 formal iterations, 156 native actions, 96 timed saves, CPU/PSS summaries and before/after performance comparisons.')


def require(condition, message):
    if not condition:
        raise ValueError('ART diagnostic trace: ' + message)


def _method(value):
    parts = value.split('\t')
    require(len(parts) >= 4 and re.fullmatch(r'0|0x[0-9a-fA-F]+', parts[0]), 'invalid method dictionary row')
    key = int(parts[0], 16)
    require(0 <= key <= 0xfffffffc and key & 3 == 0 and parts[1] and parts[2]
            and parts[3].startswith('('), 'invalid method identity')
    return key, {'class': parts[1].replace('.', '/'), 'name': parts[2], 'signature': parts[3]}


def _save(method):
    return method['class'] == 'local/pocketchat/DownloadTasks' and method['name'] == 'save' and method['signature'] in ('()V', '(Z)V')


def _controller(method):
    return method['class'] == 'local/pocketchat/ExperienceScenarios' and method['name'] == 'saveStep' and method['signature'] == '(I)V'


def _save_root(stack, methods):
    owner = next((i for i, key in enumerate(stack) if _controller(methods[key])), None)
    return None if owner is None else next((i for i in range(owner + 1, len(stack)) if _save(methods[stack[i]])), None)


def category(stack, methods):
    """One non-overlapping category for an observed stack under production save."""
    first = _save_root(stack, methods)
    if first is None:
        return None
    inside = [methods[key] for key in stack[first + 1:]]
    for method in inside:
        if method['class'] == 'local/pocketchat/DownloadLibrary' and method['name'] in ('prune', 'sync', 'add'):
            return 'library-' + method['name']
    if any(method['class'] == 'android/app/SharedPreferencesImpl$EditorImpl' and method['name'] == 'commit' for method in inside):
        return 'preferences-commit'
    if any(method['class'].startswith('org/json/') for method in inside):
        return 'json-outside-library'
    return 'other-save-stack'


def parse_trace(raw, *, expected_pid, main_tid, main_thread_name):
    require(type(expected_pid) is int and expected_pid > 0 and type(main_tid) is int and main_tid == expected_pid, 'actual process main PID/TID required')
    require(isinstance(main_thread_name, str) and main_thread_name and '\n' not in main_thread_name, 'captured Java main-thread name required')
    require(isinstance(raw, bytes) and 32 < len(raw) <= MAX_FILE_BYTES, 'empty, missing or oversized original file')
    end = raw.find(b'*end\n')
    require(0 < end <= 4 * 1024 * 1024 and raw.startswith(b'*version\n'), 'missing bounded non-streaming text keys')
    text = raw[:end].decode('utf-8', errors='strict').splitlines()
    require(len(text) >= 4 and text[0] == '*version' and text[1] in ('2', '3'), 'unsupported text format version')
    version = int(text[1]); metadata, threads, methods = {}, {}, {}; section = 'metadata'
    for line in text[2:]:
        if line in ('*threads', '*methods'):
            require((line == '*threads' and section == 'metadata') or (line == '*methods' and section == 'threads'), 'reordered/duplicate dictionary section')
            section = line[1:]; continue
        require(line and not line.startswith('*'), 'unsupported key section')
        if section == 'metadata':
            key, separator, value = line.partition('=')
            require(separator and key not in metadata, 'invalid/duplicate metadata')
            metadata[key] = value
        elif section == 'threads':
            key, separator, value = line.partition('\t')
            require(separator and key.isdecimal() and 0 < int(key) < 65536 and value and int(key) not in threads, 'invalid/duplicate thread')
            threads[int(key)] = value
        else:
            key, value = _method(line)
            require(key not in methods, 'duplicate method identity'); methods[key] = value
    matching_threads = [key for key, value in threads.items() if value == main_thread_name]
    require(section == 'methods' and methods and len(matching_threads) == 1, 'missing or ambiguous exact main-thread name mapping')
    main_encoding = matching_threads[0]
    require(metadata.get('vm') == 'art' and metadata.get('pid') == str(expected_pid), 'trace belongs to another VM/process')
    require(metadata.get('data-file-overflow') == 'false', 'sampling buffer overflow or missing overflow proof')
    clock = metadata.get('clock')
    require(clock == 'dual' if version == 3 else clock in ('wall', 'thread-cpu'), 'clock/version mismatch')
    binary = raw[end + len(b'*end\n'):]
    require(len(binary) >= 32 and binary[:4] == b'SLOW', 'missing SLOW binary header')
    actual_version, offset = struct.unpack_from('<HH', binary, 4)
    start_us = struct.unpack_from('<Q', binary, 8)[0]
    require(actual_version == version and offset == 32 and start_us > 0, 'binary/text version, offset or start clock differs')
    record_bytes = 14 if version == 3 else 10
    require(version != 3 or struct.unpack_from('<H', binary, 16)[0] == record_bytes, 'unsupported dual record size')
    data = binary[offset:]
    require(data and len(data) % record_bytes == 0, 'truncated or empty event records')
    records = len(data) // record_bytes
    require(metadata.get('num-method-calls') == str(records), 'record count differs from original summary')
    require(metadata.get('elapsed-time-usec', '').isdecimal() and int(metadata['elapsed-time-usec']) > 0, 'missing actual elapsed trace clock')
    clocks = ('thread-cpu', 'wall') if version == 3 else (clock,)
    totals = {name: dict(categories={key: 0 for key in CATEGORIES}, outsideSave=0,
                         observedBetweenStackChanges=0) for name in clocks}
    stacks, previous, main_records, outer_entries, unmatched_final = {}, {}, 0, 0, {}
    for at in range(0, len(data), record_bytes):
        tid, encoded, first_time = struct.unpack_from('<HII', data, at)
        values = (first_time, struct.unpack_from('<I', data, at + 10)[0]) if version == 3 else (first_time,)
        method_id, action = encoded & ~3, encoded & 3
        require(tid in threads and method_id in methods and action in (0, 1, 2), 'unknown thread/method or invalid action')
        require(not _controller(methods[method_id]) or tid == main_encoding, 'main-only save callback appeared on another trace thread')
        stack = stacks.setdefault(tid, [])
        if tid in previous:
            gaps = tuple(now - old for now, old in zip(values, previous[tid]))
            require(all(value >= 0 for value in gaps), 'per-thread clock decreased/wrapped')
            if tid == main_encoding:
                bucket = category(stack, methods)
                for name, duration in zip(clocks, gaps):
                    totals[name]['observedBetweenStackChanges'] += duration
                    if bucket is None: totals[name]['outsideSave'] += duration
                    else: totals[name]['categories'][bucket] += duration
        previous[tid] = values
        if tid == main_encoding: main_records += 1
        if action == 0:
            if tid == main_encoding and _save(methods[method_id]) and any(_controller(methods[key]) for key in stack) and _save_root(stack, methods) is None: outer_entries += 1
            stack.append(method_id)
        else:
            require(stack and stack[-1] == method_id, 'unbalanced sampled stack transition')
            stack.pop()
    require(main_records and outer_entries, 'no observed production main-thread save stack')
    for tid, stack in stacks.items():
        if stack: unmatched_final[str(tid)] = len(stack)
    for value in totals.values():
        value['saveStackResidenceEstimateUs'] = sum(value['categories'].values())
        require(value['saveStackResidenceEstimateUs'] + value['outsideSave'] == value['observedBetweenStackChanges'], 'category accounting overlaps')
        denominator = value['saveStackResidenceEstimateUs']
        value['categoryFractionsWithinObservedSave'] = {key: count / denominator if denominator else None for key, count in value['categories'].items()}
    return dict(schema=1, status='decoded', diagnosticOnly=True, performanceComparisonAllowed=False,
                formatVersion=version, clock=clock, pid=expected_pid, mainTid=main_tid,
                mainThreadName=threads[main_encoding], mainThreadTraceEncoding=main_encoding,
                threadMapping='Exact unique captured Java main-thread name in the trace dictionary; receipt also asserts Looper main thread and OS mainTid==pid. Trace encoding is not an OS TID.',
                saveStackOwner='ExperienceScenarios.saveStep(I)V with an explicit diagnostic-only main-thread assertion; only descendant DownloadTasks.save stacks are classified.',
                bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                binaryStartClockUs=start_us, metadata=metadata, eventRecords=records,
                mainThreadEventRecords=main_records, sampledOuterSaveEntries=outer_entries,
                sampledEntriesAreExactCalls=False, exactMethodDurations=False,
                nominalIntervalUs=INTERVAL_US, clockWeightedResidence=totals,
                openStacksAtLastObservation=unmatched_final, initialAndFinalTailsEstimated=False,
                limits=list(LIMITS))


def _owned_events(root, action, nonce, expected):
    path = root / (action + '-transport.json')
    records = json.loads(path.read_text())
    require(isinstance(records, list) and records, 'original invocation transport missing')
    pointers = []
    for line in (root / (action + '-log.txt')).read_text().splitlines():
        pointer = parse_receipt_line(line)
        if pointer is not None and pointer.get('runNonce') == nonce:
            pointers.append(pointer)
    events = []
    for sequence, row in enumerate(records, 1):
        require(row['receipt']['sequence'] == sequence, 'original invocation sequence gap/duplicate')
        require(row['receipt'] in pointers, 'original log pointer missing for a transported event')
        events.append(decode_event(row['receipt'], row['rawUtf8'].encode('utf-8'),
                                  identity=expected, nonce=nonce, slot=0, action=action, command=1))
    require(json.loads((root / (action + '-events.json')).read_text()) == events, 'decoded invocation events differ')
    require(not any(event['kind'] in ('error', 'samplingAborted', 'samplingStopError') for event in events), 'actual diagnostic reported failure')
    return events


def verify_diagnostic(report, expected, protocol, scenario, raw_root, selected_build):
    """Replay original app envelopes and trace bytes; do not trust host summaries."""
    root = Path(raw_root)
    require(report.get('schema') == 1 and report.get('status') == 'passed'
            and report.get('diagnosticOnly') is True and report.get('performanceComparisonAllowed') is False,
            'diagnostic is missing/failed or promoted into a performance result')
    require(all(report.get(name) is False for name in ('physicalDeviceAcceptance', 'realChatGptAcceptance', 'releaseAcceptance')), 'diagnostic scope promoted to unrelated acceptance')
    require(report.get('sourceCommit') == expected['sourceCommit'] and report.get('actualAndroidExecution') is True, 'actual diagnostic source/execution differs')
    verify_installed(report.get('buildIdentity', {}), expected)
    verify_installed(report.get('installedAfter', {}), expected)
    require(report.get('selectedRole') == 'A' and report.get('selectedBuild') == {
        name: selected_build[name] for name in ('sourceCommit', 'sourceTree', 'runId', 'runAttempt', 'apkSha256', 'apkBytes')},
        'diagnostic is not bound to the exact baseline role/original build')
    require(report.get('scenarioManifest') == scenario and scenario['name'].startswith('download-history-'), 'diagnostic workload manifest differs')
    require(report.get('formalIterationsAdded') == 0 and report.get('formalActionsAdded') == 0
            and report.get('timedSaveSamplesAdded') == 0 and report.get('additionalRealSaveCalls') == 8
            and report.get('additionalSaveCountComplete') is True,
            'diagnostic changed formal sample accounting')
    require(report.get('observerFiles') == {name: protocol[name] for name in OBSERVERS}
            and report.get('executionInputsUnchanged') is True, 'diagnostic observer differs')
    nonce, seed_nonce = report.get('runNonce'), report.get('seedNonce')
    require(isinstance(nonce, str) and re.fullmatch('[0-9a-f]{32}', nonce)
            and isinstance(seed_nonce, str) and re.fullmatch('[0-9a-f]{32}', seed_nonce) and nonce != seed_nonce,
            'separate owned diagnostic/seed nonces required')
    seed_events = _owned_events(root, 'experienceSeed', seed_nonce, expected)
    events = _owned_events(root, ACTION, nonce, expected)
    def owned(kind, value, source=events):
        require(sum(event['kind'] == kind and event['result'] == value for event in source) == 1, 'missing/duplicate actual owned ' + kind)
    owned('seeded', report['seed'], seed_events)
    require(report['seed'].get('timed') is False and report['seed']['scenario']['manifest'] == scenario, 'extra seed was not untimed original provisioning')
    owned('ready', report['ready']); owned('samplingFinished', report['traceReceipt'])
    window = report['scenarioWindow']; owned('scenarioFinished', window)
    require(window['name'] == 'diagnostic-history-save-sampling' and window['lifecycleChanges'] == 0
            and window['frameLimitReached'] is False, 'diagnostic window changed or truncated')
    start, end = window['start'], window['end']
    require(end['elapsedRealtimeMs'] - start['elapsedRealtimeMs'] == window['elapsedDurationMs'] >= 16000, 'diagnostic clock interval differs')
    saves = report['saves']
    require(isinstance(saves, list) and [save.get('step') for save in saves] == list(range(1, 9)), 'extra actual eight-save sequence missing')
    previous_up = start['uptimeMs']
    for number, save in enumerate(saves, 1):
        owned('scenarioSave', save)
        duration = save['durationMs']
        require(type(duration) in (int, float) and math.isfinite(duration) and duration >= 0, 'invalid diagnostic save clock')
        require(save['startUptimeMs'] - previous_up >= 2000 and save['endUptimeMs'] >= save['startUptimeMs'], 'original 2000ms step cadence changed')
        require(abs((save['endElapsedRealtimeNs'] - save['startElapsedRealtimeNs']) / 1e6 - duration) < 1e-6, 'actual save duration clocks differ')
        require(save.get('name') == 'history-save-' + str(number) and save.get('received') == number * 65536
                and save.get('method') == 'DownloadTasks.save' and save.get('thread') == 'Android main'
                and save.get('httpTransferMeasured') is False, 'extra production call or scope differs')
        previous_up = save['endUptimeMs']
    verification = window['verification']; count = scenario['downloadHistory']['savedRows']
    require(verification.get('savedRows') == count and verification.get('taskRows') == count + 1
            and verification.get('verifiedProgressBytes') == 8 * 65536
            and verification.get('actualAndroidSQLite') is True and verification.get('actualAndroidSharedPreferences') is True,
            'extra final SQLite/prefs verification incomplete')
    receipt = report['traceReceipt']
    require(receipt.get('schema') == 1 and receipt.get('diagnosticOnly') is True
            and receipt.get('performanceComparisonAllowed') is False and receipt.get('runNonce') == nonce
            and receipt.get('completedEightSaves') is True and receipt.get('verification') == verification,
            'actual trace receipt is not the completed extra pass')
    require(receipt.get('bufferBytes') == BUFFER_BYTES and receipt.get('intervalUs') == INTERVAL_US
            and receipt.get('traceUri') == 'content://local.pocketchat.test.evidence/experience-sampling/' + nonce,
            'sampling parameters or original trace path differs')
    require(receipt['startRequested']['elapsedRealtimeNs'] <= saves[0]['startElapsedRealtimeNs']
            <= saves[-1]['endElapsedRealtimeNs'] <= receipt['stopRequested']['elapsedRealtimeNs']
            <= receipt['stopped']['elapsedRealtimeNs'], 'sampling did not surround the extra saves')
    original = (root / TRACE_FILE).read_bytes()
    require(receipt['traceBytes'] == len(original) and receipt['traceSha256'] == hashlib.sha256(original).hexdigest(), 'raw trace differs from actual device receipt')
    analysis = parse_trace(original, expected_pid=receipt['pid'], main_tid=receipt['mainTid'], main_thread_name=receipt['mainThreadName'])
    require(report.get('traceAnalysis') == analysis, 'trace analysis was not recomputed from original bytes')
    for field in ('readySnapshot', 'finalSnapshot'):
        owned('snapshot', report[field])
    initial, final = report['readySnapshot'], report['finalSnapshot']
    require(all(initial[key] == final[key] for key in ('surface', 'session', 'attachedSession'))
            and all(initial['page'][key] == final['page'][key] for key in ('document', 'draft', 'cookie', 'replyFingerprint', 'sendCount', 'path'))
            and final['visibleDocument'] is True and final['networkReady'] is True, 'extra diagnostic lost browser state')
    indexed = report.get('rawEvidence')
    require(isinstance(indexed, list) and indexed, 'original diagnostic raw inventory missing')
    actual = []
    for path in sorted(root.rglob('*')):
        if path.is_file() and path.name != RESULT_FILE:
            data = path.read_bytes(); actual.append(dict(path=str(path.relative_to(root)), bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
    require(indexed == actual, 'diagnostic raw files missing, changed or unindexed')
    return analysis
