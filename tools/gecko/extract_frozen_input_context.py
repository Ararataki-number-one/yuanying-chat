#!/usr/bin/env python3
"""Read existing data privately; emit only fixed roles and numeric scheduler totals."""
import csv
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import resource
import stat
import subprocess
import sys
import tempfile
import zipfile

REPOSITORY = 'Ararataki-number-one/yuanying-chat'
SOURCE = dict(sourceCommit='07350482a6aaa506bd6f258fbe56c5f238dbcd79',
              sourceTree='f36c90a44dbab1b401f8948731710a1632bc817b',
              runId='40734866831', runAttempt='1')
BRANCH = 'diagnostic/gecko-input-analysis-20261028'
FLAGS = dict(diagnosticOnly=True, applicationAcceptance=False, releaseAcceptance=False,
             physicalPhoneAcceptance=False, protectionEffectivenessAcceptance=False,
             uniqueCauseEstablished=False)
MAX_ZIP = 256 * 1024 * 1024
MAX_REPORT = 1024 * 1024
MAX_CSV = 8 * 1024 * 1024
MAX_EXPANDED = 1024 * 1024 * 1024
QUERY_NAMES = ('cpu-window-top-threads', 'input-art-thread-slices', 'input-service-thread-states')
ROLES = ('app', 'driver', 'input', 'system', 'render', 'gms', 'dex', 'trace', 'kernel', 'idle', 'other')
LIMITATIONS = [
    'Guest-clock scheduler durations do not measure physical CPU usage or establish a host cause.',
    'Fixed roles are coarse labels; unknown and unlisted thread time is grouped as other.',
    'Only existing top-20 thread groups per CPU are classified; no Android or trace processing is repeated.',
    'Temporal overlap does not establish a unique blocking cause or qualify an original failed workload.',
    'Synchronous UP delay alone does not change the original input oracle.'
]


def need(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def identity(path):
    need(path.is_file() and not path.is_symlink(), 'Ordinary file required')
    return dict(bytes=path.stat().st_size, sha256=sha(path))


def read_json(path, maximum=MAX_REPORT):
    need(path.is_file() and not path.is_symlink() and path.stat().st_size <= maximum,
         'Bounded ordinary JSON required')
    return json.loads(path.read_text(encoding='utf-8'))


def file_limit(maximum):
    def apply():
        resource.setrlimit(resource.RLIMIT_FSIZE, (maximum, maximum))
    return apply


def gh_read(route, target, maximum):
    errors = target.with_suffix(target.suffix + '.stderr.log')
    with target.open('xb') as stdout, errors.open('xb') as stderr:
        result = subprocess.run(['gh', 'api', route], stdout=stdout, stderr=stderr,
                                timeout=180, check=False, preexec_fn=file_limit(maximum))
    need(result.returncode == 0 and target.stat().st_size <= maximum,
         'Read of original GitHub data failed or exceeded bound')


def frozen_binding(path, sample):
    value = read_json(path)
    need(value.get('schema') == 1 and all(value.get(k) == v for k, v in SOURCE.items()) and
         all(value.get(k) is v for k, v in FLAGS.items()), 'Frozen analysis source/scope differs')
    rows = value.get('artifacts')
    need(isinstance(rows, list) and len(rows) == 3 and {r.get('sample') for r in rows} == {'1', '2', '3'},
         'All three original analysis artifact identities required')
    seen = set()
    for row in rows:
        need(type(row.get('artifactId')) is int and row['artifactId'] > 0 and row['artifactId'] not in seen and
             row.get('name') == 'frozen-input-analysis-40734866831-1-sample-' + row['sample'],
             'Distinct original artifact binding required')
        seen.add(row['artifactId'])
        need(type(row.get('zipBytes')) is int and 0 < row['zipBytes'] <= MAX_ZIP and
             re.fullmatch('[0-9a-f]{64}', str(row.get('zipSha256'))) and
             type(row.get('reportBytes')) is int and 0 < row['reportBytes'] <= MAX_REPORT and
             re.fullmatch('[0-9a-f]{64}', str(row.get('reportSha256'))),
             'Exact bounded ZIP/report size and digest required')
    return next(r for r in rows if r['sample'] == sample)


def zip_members(archive):
    infos = archive.infolist()
    need(0 < len(infos) <= 5000, 'Original ZIP entry count exceeds bound')
    names, total = {}, 0
    for info in infos:
        name = info.filename[:-1] if info.is_dir() else info.filename
        path = PurePosixPath(name)
        need(re.fullmatch('[A-Za-z0-9_./-]+', name) and not path.is_absolute() and
             '..' not in path.parts and str(path) == name and name not in names,
             'Unsafe, noncanonical or duplicate ZIP member')
        mode = stat.S_IFMT(info.external_attr >> 16)
        need(mode in ((0, stat.S_IFDIR) if info.is_dir() else (0, stat.S_IFREG)) and not info.flag_bits & 1,
             'Encrypted or special ZIP member')
        total += info.file_size
        need(0 <= info.file_size <= MAX_ZIP and total <= MAX_EXPANDED, 'ZIP expansion bound exceeded')
        names[name] = info
    return names


def read_member(archive, members, name, maximum):
    need(name in members and not members[name].is_dir() and 0 < members[name].file_size <= maximum,
         'Required small ordinary member missing or oversized')
    with archive.open(members[name]) as stream:
        raw = stream.read(maximum + 1)
    need(len(raw) == members[name].file_size and len(raw) <= maximum, 'Expanded member byte count differs')
    return raw


def select_context(archive, binding):
    with zipfile.ZipFile(archive) as source:
        members = zip_members(source)
        raw = read_member(source, members, 'supplemental-input-service/supplemental-analysis.json', MAX_REPORT)
        need(len(raw) == binding['reportBytes'] and hashlib.sha256(raw).hexdigest() == binding['reportSha256'],
             'Frozen supplemental report identity differs')
        report = json.loads(raw)
        need(report.get('schema') == 1 and all(report.get(k) is v for k, v in FLAGS.items()) and
             report.get('originalInputsUnchanged') is True and report.get('partial') is True and
             report.get('trace') == binding['trace'], 'Original supplemental scope or trace binding differs')
        need(report.get('script', {}).get('sha256') ==
             'e3410a7b3551f075f2b66e358a8ccb2ea2add08d7bcf115f03219f85eb4e3fcf',
             'Frozen supplemental tool differs')
        queries = report.get('queries')
        need(isinstance(queries, list) and len(queries) == 3 and
             {q.get('name') for q in queries} == set(QUERY_NAMES), 'Three original context query records required')
        query = next(q for q in queries if q['name'] == 'cpu-window-top-threads')
        name = query['name'] + '.csv'
        expected = query.get('files', {}).get('csv', {})
        need(query.get('status') == 'queried' and query.get('rowLimitReached') is False and
             expected.get('path') == name and type(expected.get('bytes')) is int and
             0 < expected['bytes'] <= MAX_CSV, 'Original bounded CPU table required')
        data = read_member(source, members, 'supplemental-input-service/' + name, MAX_CSV)
        need(len(data) == expected['bytes'] and hashlib.sha256(data).hexdigest() == expected.get('sha256'),
             'Original CPU table identity differs')
        original = report.get('originalAnalysis', {})
        need(type(original.get('bytes')) is int and 0 < original['bytes'] <= MAX_REPORT,
             'Bounded original correlation report required')
        original_raw = read_member(source, members, 'correlation/analysis.json', MAX_REPORT)
        need(len(original_raw) == original['bytes'] and hashlib.sha256(original_raw).hexdigest() == original.get('sha256'),
             'Original correlation identity differs')
        correlation = json.loads(original_raw)
        need(all(correlation.get(k) is v for k, v in FLAGS.items()) and
             correlation.get('originalInputsUnchanged') is True and
             correlation.get('helper', {}).get('sha256') ==
             '63ecae013dcc2f8e0232aa588ffcb7c57839cb99b0c4adb742ab7e2ca6d028f0',
             'Original correlation scope differs')
    return report, correlation, data, query['rows']


def natural(value, maximum=(1 << 63) - 1):
    need(type(value) is int and 0 <= value <= maximum, 'Integer field invalid')
    return value


def numeric(row, key, maximum=(1 << 63) - 1, nullable=False):
    value = row.get(key)
    if nullable and value in ('[NULL]', '', None):
        return None
    need(isinstance(value, str) and re.fullmatch('[0-9]{1,20}', value), 'Numeric cell invalid')
    return natural(int(value), maximum)


def hidden_name(row, key):
    value = row.get(key)
    need(isinstance(value, str) and len(value) <= 8192 and re.fullmatch('(?:[0-9A-F]{2})*', value) is not None,
         'Hidden name encoding invalid')
    return bytes.fromhex(value).decode('utf-8', errors='strict').lower()


def fixed_role(row, window):
    tid = numeric(row, 'tid', (1 << 31) - 1)
    pid = numeric(row, 'pid', (1 << 31) - 1, nullable=True)
    if tid == 0:
        return 'idle'
    if pid == window['driver'] or tid == window['driver']:
        return 'driver'
    thread, process = hidden_name(row, 'thread_name_utf8_hex'), hidden_name(row, 'process_name_utf8_hex')
    if tid in window['servers'] or 'inputdispatcher' in thread or 'inputreader' in thread or 'inputflinger' in process:
        return 'input'
    if any(word in thread or word in process for word in ('renderthread', 'surfaceflinger', 'compositor', 'swiftshader')):
        return 'render'
    if pid == window['target']:
        return 'app'
    if 'com.google.android.gms' in process:
        return 'gms'
    if 'dex2oat' in process or 'dexopt' in process:
        return 'dex'
    if any(word in process for word in ('perfetto', 'traced', 'atrace')):
        return 'trace'
    if thread.startswith(('kworker', 'ksoftirqd', 'rcu_', 'migration/', 'watchdog/', 'cpuhp/')):
        return 'kernel'
    if process == 'system_server':
        return 'system'
    return 'other'


def numeric_summary(report, correlation, raw, expected_rows):
    selected = report.get('selectedWindows')
    originals = correlation.get('windows')
    need(isinstance(selected, list) and len(selected) <= 44 and isinstance(originals, list), 'Window set invalid')
    windows, result = {}, []
    for index, item in enumerate(selected):
        key = item.get('windowId')
        need(isinstance(key, str) and re.fullmatch('r[0-9]+-e(?:[0-9]+|cleanup)', key) and key not in windows,
             'Window identity invalid')
        begin, end = natural(item.get('beginMonoNs')), natural(item.get('endMonoNs'))
        need(0 < end - begin <= 20_000_000_000, 'Window duration invalid')
        matches = [w for w in originals if w.get('windowId') == key]
        need(len(matches) == 1 and matches[0].get('beginMonoNs') == begin and matches[0].get('endMonoNs') == end,
             'Original window correspondence differs')
        driver, target = natural(item.get('driverPid'), (1 << 31) - 1), natural(item.get('targetPid'), (1 << 31) - 1)
        servers = {natural(t.get('server_tid'), (1 << 31) - 1)
                   for t in matches[0].get('overlappingBinderTransactions', []) if t.get('server_tid') is not None}
        windows[key] = dict(index=index, duration=end - begin, driver=driver, target=target, servers=servers, cpus={})
        result.append(dict(window=index, wholeWindowNs=end - begin, cpus=[]))
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8', errors='strict').lstrip('\r\n')))
    need(reader.fieldnames and len(reader.fieldnames) == len(set(reader.fieldnames)), 'CPU header invalid')
    rows = list(reader)
    need(type(expected_rows) is int and 0 <= len(rows) == expected_rows <= 20_000 and
         all(None not in row and all(v is not None for v in row.values()) for row in rows), 'CPU row count or shape invalid')
    seen = set()
    for row in rows:
        need(row.get('window_id') in windows, 'CPU window absent')
        window = windows[row['window_id']]
        cpu, utid = numeric(row, 'cpu', 63), numeric(row, 'utid')
        key = (row['window_id'], cpu, utid)
        need(key not in seen, 'Duplicate CPU group')
        seen.add(key)
        running = numeric(row, 'running_ns', window['duration'])
        total = numeric(row, 'cpu_all_threads_running_ns', window['duration'])
        groups = numeric(row, 'cpu_all_thread_groups', 20_000)
        rank = numeric(row, 'cpu_rank', 20)
        need(rank > 0 and groups > 0, 'CPU ranking invalid')
        bucket = window['cpus'].setdefault(cpu, dict(total=total, groups=groups, listed=0, running=0,
                                                    segments=0, open=0, roles={r: 0 for r in ROLES}))
        need(bucket['total'] == total and bucket['groups'] == groups, 'CPU group totals differ')
        bucket['listed'] += 1
        bucket['running'] += running
        bucket['segments'] += numeric(row, 'sched_segments', 1_000_000)
        bucket['open'] += numeric(row, 'includes_open_interval', 1)
        bucket['roles'][fixed_role(row, window)] += running
    for window in windows.values():
        for cpu, bucket in sorted(window['cpus'].items()):
            tail = bucket['total'] - bucket['running']
            need(tail >= 0 and bucket['listed'] == min(20, bucket['groups']), 'Incomplete or inconsistent top groups')
            bucket['roles']['other'] += tail
            result[window['index']]['cpus'].append(dict(cpu=cpu, totalRunningNs=bucket['total'],
                listedRunningNs=bucket['running'], tailRunningNs=tail, unobservedNs=window['duration'] - bucket['total'],
                listedThreadGroups=bucket['listed'], allThreadGroups=bucket['groups'],
                schedSegments=bucket['segments'], openIntervalRows=bucket['open'], roles=bucket['roles']))
    return dict(schema=1, status='diagnostic-numeric-context', partial=True,
                **FLAGS, windows=result, limitations=LIMITATIONS)


def validate_public(value):
    need(value.get('schema') == 1 and all(value.get(k) is v for k, v in FLAGS.items()) and
         value.get('limitations') == LIMITATIONS and value.get('partial') is True, 'Public scope differs')
    fixed = {'schema', 'status', 'partial', *FLAGS, 'windows', 'limitations'}
    if value.get('status') == 'unavailable':
        need(set(value) == fixed | {'errorClass', 'reason'} and value['windows'] == [] and
             value['reason'] == 'existing-context-unavailable' and value['errorClass'] in
             ('ValueError', 'OSError', 'TimeoutError', 'UnicodeError', 'OtherError'), 'Public error differs')
        return
    need(set(value) == fixed and value['status'] == 'diagnostic-numeric-context' and
         isinstance(value['windows'], list) and len(value['windows']) <= 44, 'Public shape differs')
    for index, window in enumerate(value['windows']):
        need(set(window) == {'window', 'wholeWindowNs', 'cpus'} and window['window'] == index, 'Public window differs')
        natural(window['wholeWindowNs'], 20_000_000_000)
        need(isinstance(window['cpus'], list) and len(window['cpus']) <= 64, 'Public CPU count differs')
        for cpu in window['cpus']:
            need(set(cpu) == {'cpu', 'totalRunningNs', 'listedRunningNs', 'tailRunningNs', 'unobservedNs',
                             'listedThreadGroups', 'allThreadGroups', 'schedSegments', 'openIntervalRows', 'roles'} and
                 isinstance(cpu['roles'], dict) and set(cpu['roles']) == set(ROLES), 'Public numeric keys differ')
            for key, item in cpu.items():
                if key == 'roles':
                    for amount in item.values():
                        natural(amount)
                else:
                    natural(item, 63 if key == 'cpu' else (1 << 63) - 1)


def run():
    need(os.environ.get('GITHUB_REPOSITORY') == REPOSITORY, 'Exact original repository required')
    binding = frozen_binding(Path(__file__).with_name('input_context_bindings.json'), '2')
    with tempfile.TemporaryDirectory(prefix='frozen-input-numeric-context-') as temporary:
        private = Path(temporary)
        prefix = 'repos/' + REPOSITORY + '/actions/'
        run_path = private / 'original-analysis-run.json'
        gh_read(prefix + 'runs/40734866831/attempts/1', run_path, MAX_REPORT)
        original_run = read_json(run_path)
        need(str(original_run.get('id')) == SOURCE['runId'] and original_run.get('run_attempt') == 1 and
             original_run.get('head_sha') == SOURCE['sourceCommit'] and original_run.get('head_branch') == BRANCH and
             original_run.get('head_commit', {}).get('tree_id') == SOURCE['sourceTree'] and
             original_run.get('status') == 'completed', 'Final original analysis run identity differs')
        metadata_path = private / 'original-artifact-metadata.json'
        route = prefix + 'artifacts/' + str(binding['artifactId'])
        gh_read(route, metadata_path, MAX_REPORT)
        metadata = read_json(metadata_path)
        workflow = metadata.get('workflow_run', {})
        need(metadata.get('id') == binding['artifactId'] and metadata.get('name') == binding['name'] and
             metadata.get('size_in_bytes') == binding['zipBytes'] and metadata.get('expired') is False and
             metadata.get('digest') == 'sha256:' + binding['zipSha256'] and
             str(workflow.get('id')) == SOURCE['runId'] and workflow.get('head_sha') == SOURCE['sourceCommit'] and
             workflow.get('head_branch') == BRANCH, 'Original analysis artifact identity differs')
        archive = private / 'original-analysis-artifact.zip'
        gh_read(route + '/zip', archive, MAX_ZIP)
        need(identity(archive) == dict(bytes=binding['zipBytes'], sha256=binding['zipSha256']),
             'Original complete ZIP size or digest differs')
        report, correlation, cpu, count = select_context(archive, binding)
        value = numeric_summary(report, correlation, cpu, count)
        need(identity(archive) == dict(bytes=binding['zipBytes'], sha256=binding['zipSha256']),
             'Original ZIP changed during numeric aggregation')
        validate_public(value)
        return value


def main():
    try:
        value = run()
        validate_public(value)
    except BaseException as error:
        kind = ('ValueError' if isinstance(error, ValueError) else 'UnicodeError' if isinstance(error, UnicodeError)
                else 'TimeoutError' if isinstance(error, (TimeoutError, subprocess.TimeoutExpired))
                else 'OSError' if isinstance(error, OSError) else 'OtherError')
        value = dict(schema=1, status='unavailable', partial=True, **FLAGS, windows=[], limitations=LIMITATIONS,
                     errorClass=kind, reason='existing-context-unavailable')
        validate_public(value)
        print('FROZEN_INPUT_NUMERIC_CONTEXT ' + json.dumps(value, separators=(',', ':')), flush=True)
        return 1
    print('FROZEN_INPUT_NUMERIC_CONTEXT ' + json.dumps(value, separators=(',', ':')), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
