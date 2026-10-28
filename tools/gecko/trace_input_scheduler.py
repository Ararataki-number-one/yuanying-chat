#!/usr/bin/env python3
"""Bounded, diagnostic-only tracing around one unchanged editing phase."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
BASE = 'fb67b081895bd37639d0a909155f607100d5cecb'
DURATION_MS = 240000
MAX_TRACE_BYTES = 24 * 1024 * 1024
SAMPLES = ('1', '2', '3')
ADDED = {
    '.github/workflows/gecko-input-scheduler-diagnostic.yml',
    'tools/gecko/generate_input_scheduler_diagnostic_workflow.py',
    'tools/gecko/trace_input_scheduler.py',
    'tools/gecko/analyze_input_scheduler_trace.py',
    'tests/gecko_scheduler_diagnostic_workflow_test.py',
}


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def validate_restored_identity(record, index, build, sdk):
    for name in ('sourceCommit', 'sourceTree', 'runId', 'runAttempt'):
        require(index.get(name) == record[name] and sdk.get(name) == record[name], 'Actual restored source/run/SDK binding differs: ' + name)
    # The existing APK receipt has no sourceTree; index and SDK carry it.
    for name in ('sourceCommit', 'runId', 'runAttempt'):
        require(build.get(name) == record[name], 'Actual compiled APK identity differs: ' + name)


def original_command():
    raw = subprocess.check_output(['git', 'show', BASE + ':.github/workflows/gecko-integration.yml'], cwd=ROOT).decode()
    section = raw.split('  editing-samples:\n', 1)[1]
    section = section.split('    - name: Run one original workload on this independent Android device\n', 1)[1]
    body = section.split('      run: |\n', 1)[1].split('    - name: Preserve and verify this sample without replay\n', 1)[0]
    lines = body.splitlines(keepends=True)
    require(all(line.startswith('        ') or not line.strip() for line in lines), 'Original block indentation changed')
    return ''.join(line[8:] if line.startswith('        ') else line for line in lines).encode()


def config_text(key):
    require(re.fullmatch(r'pc-input-[0-9a-f]{32}', key), 'Invalid own session key')
    return '''duration_ms: 240000
max_file_size_bytes: 25165824
write_into_file: true
file_write_period_ms: 1000
flush_period_ms: 1000
unique_session_name: "%s"
buffers { size_kb: 8192 fill_policy: RING_BUFFER }
buffers { size_kb: 1024 fill_policy: RING_BUFFER }
builtin_data_sources {
  disable_clock_snapshotting: false
  primary_trace_clock: BUILTIN_CLOCK_MONOTONIC
  snapshot_interval_ms: 1000
}
data_sources {
  config {
    name: "linux.ftrace"
    target_buffer: 0
    ftrace_config {
      ftrace_events: "sched/sched_switch"
      ftrace_events: "sched/sched_wakeup"
      ftrace_events: "sched/sched_waking"
      ftrace_events: "sched/sched_process_exit"
      ftrace_events: "sched/sched_process_fork"
      ftrace_events: "sched/sched_process_exec"
      ftrace_events: "task/task_newtask"
      ftrace_events: "task/task_rename"
      ftrace_events: "binder/binder_transaction"
      ftrace_events: "binder/binder_transaction_received"
      atrace_categories: "input"
      atrace_categories: "dalvik"
      atrace_categories: "binder_driver"
      atrace_apps: "*"
    }
  }
}
data_sources {
  config {
    name: "linux.process_stats"
    target_buffer: 1
    process_stats_config { scan_all_processes_on_start: true }
  }
}
''' % key


def host_snapshot(out, label):
    values = {'hostMonotonicNs': time.monotonic_ns(), 'hostRealtimeNs': time.time_ns(), 'files': {}}
    for name in ('/proc/stat', '/proc/pressure/cpu', '/proc/pressure/memory', '/proc/pressure/io',
                 '/proc/self/cgroup', '/proc/self/status', '/proc/loadavg', '/sys/fs/cgroup/cpu.stat',
                 '/sys/fs/cgroup/cpu.max', '/sys/fs/cgroup/memory.events'):
        try:
            with open(name, 'rb') as stream:
                raw = stream.read(65537)
            require(len(raw) <= 65536, 'Host snapshot exceeded bound')
            values['files'][name] = raw.decode('utf-8', errors='replace')
        except (OSError, ValueError) as error:
            values['files'][name] = {'unavailable': type(error).__name__}
    dump(out / ('host-' + label + '.json'), values)


def run(args):
    out = args.out.resolve()
    require(out.is_relative_to(ROOT / 'work') and not out.is_symlink(), 'Owned work output required')
    out.mkdir(parents=True, exist_ok=True)
    require(not (out / 'diagnostic-run.json').exists(), 'Refuse a repeated diagnostic invocation')
    record = dict(schema=1, diagnosticOnly=True, applicationAcceptance=False, physicalPhoneAcceptance=False,
                  sample=args.sample, status='incomplete', workloadInvocationCount=0, durationMs=DURATION_MS,
                  maxTraceBytes=MAX_TRACE_BYTES, scope='First bounded phase window; trace overhead can affect scheduling. Not qualification.')
    key = 'pc-input-' + uuid.uuid4().hex
    remote_config = '/data/local/tmp/' + key + '.pbtxt'
    remote_trace = '/data/misc/perfetto-traces/' + key + '.perfetto-trace'
    record.update(sessionKey=key, remoteConfig=remote_config, remoteTrace=remote_trace)
    calls = []

    def adb(label, *parts, timeout=20):
        started = time.monotonic_ns()
        try:
            p = subprocess.run([args.adb, '-s', args.serial, *parts], capture_output=True, timeout=timeout)
            stdout, stderr, code = p.stdout, p.stderr, p.returncode
        except subprocess.TimeoutExpired as error:
            stdout, stderr, code = error.stdout or b'', error.stderr or b'', None
        require(len(stdout) <= 1048576 and len(stderr) <= 1048576, 'Collector response exceeded bound')
        (out / (label + '.stdout.log')).write_bytes(stdout)
        (out / (label + '.stderr.log')).write_bytes(stderr)
        calls.append(dict(label=label, command=list(parts), returnCode=code,
                          hostStartedMonotonicNs=started, hostCompletedMonotonicNs=time.monotonic_ns()))
        return code, stdout

    exit_code = 2
    started = False
    start_attempted = False
    try:
        source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        tree = subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], cwd=ROOT, text=True).strip()
        require(source == os.environ.get('GITHUB_SHA'), 'Actual checkout differs from requested source')
        require(not subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT).strip(), 'Clean committed source required')
        changes = subprocess.check_output(['git', 'diff', '--name-status', BASE, source], cwd=ROOT, text=True).splitlines()
        require(changes and all(line.startswith('A\t') and line[2:] in ADDED for line in changes), 'Only reviewed diagnostic additions may differ from frozen baseline')
        record.update(sourceCommit=source, sourceTree=tree, baselineSource=BASE,
                      runId=os.environ['GITHUB_RUN_ID'], runAttempt=os.environ['GITHUB_RUN_ATTEMPT'],
                      productionSourceUnchanged=True, changedPaths=changes)
        index = json.loads((ROOT / 'work/gecko-integration/ci-build-index.json').read_bytes())
        build = json.loads((ROOT / 'work/gecko-integration/caret-apk-build-receipt.json').read_bytes())
        sdk = json.loads((ROOT / 'work/native-caret-sdk/sdk-build-receipt.json').read_bytes())
        validate_restored_identity(record, index, build, sdk)
        for field, path in (('integrationApkSha256', 'app/build/outputs/apk/integration/app-x86_64-integration.apk'),
                            ('releaseApkSha256', 'app/build/outputs/apk/release/app-arm64-v8a-release-unsigned.apk')):
            require(sha(ROOT / path) == build[field], 'Actual compiled APK bytes differ')
        command = args.command_file.resolve()
        require(command.is_relative_to(ROOT / 'work') and not command.is_symlink(), 'Owned original command file required')
        require(command.read_bytes() == original_command(), 'Original editing command bytes changed')
        record['originalCommandSha256'] = sha(command)
        record['compiledApkIdentity'] = {k: build[k] for k in ('integrationApkSha256', 'releaseApkSha256')}
        record['hostTimelineAvailable'] = False
        record['hostTimelineScope'] = 'Before/after aggregates only; cannot align a 46ms host contention interval. Guest precise timeline is separate.'
        config = out / 'perfetto-config.pbtxt'
        config.write_text(config_text(key))
        host_snapshot(out, 'before')
        adb('device-before', 'shell', 'cat /proc/uptime /proc/stat /proc/pressure/cpu /proc/pressure/memory /proc/pressure/io')
        adb('perfetto-version', 'shell', 'perfetto', '--version')
        adb('trace-capabilities', 'shell', 'atrace', '--list_categories')
        code, _ = adb('push-config', 'push', str(config), remote_config)
        if code == 0:
            record['traceStartHostBeforeNs'] = time.monotonic_ns()
            start_attempted = True
            code, _ = adb('start-own-session', 'shell', 'perfetto', '--txt', '--config', remote_config,
                          '--out', remote_trace, '--detach=' + key)
            record['traceStartHostAfterNs'] = time.monotonic_ns()
            started = code == 0
        record['traceStartSucceeded'] = started
        # Exactly one original shell block. No probe, poll, retry, extra input or
        # priority change occurs here while the original driver is running.
        record['workloadInvocationCount'] = 1
        record['phaseHostStartedMonotonicNs'] = time.monotonic_ns()
        p = subprocess.run(['bash', '--noprofile', '--norc', '-e', '-o', 'pipefail', str(command)], cwd=ROOT)
        record['phaseHostCompletedMonotonicNs'] = time.monotonic_ns()
        record['workloadExitCode'] = p.returncode
        exit_code = p.returncode if p.returncode >= 0 else 2
    except BaseException as error:
        record.update(errorType=type(error).__name__, error=str(error))
    finally:
        # Never kill global perfetto/traced or a guessed PID. Duration may have
        # already ended this exact keyed session; preserve that response too.
        if start_attempted:
            stop_code, _ = adb('stop-own-session', 'shell', 'perfetto', '--attach=' + key, '--stop')
            record['ownStopConfirmed'] = stop_code == 0
            if stop_code != 0:
                record['sessionCompletionScope'] = 'Own attach-stop was not confirmed; natural duration completion is not inferred.'
            code, _ = adb('pull-own-trace', 'pull', remote_trace, str(out / 'android.perfetto-trace'), timeout=45)
            trace = out / 'android.perfetto-trace'
            if code == 0 and trace.is_file():
                record.update(traceBytes=trace.stat().st_size, traceSha256=sha(trace), traceCapHit=trace.stat().st_size >= MAX_TRACE_BYTES)
                if trace.stat().st_size > MAX_TRACE_BYTES:
                    record['error'] = 'Trace exceeded declared file cap'
                    exit_code = 2
        try:
            host_snapshot(out, 'after')
            adb('device-after', 'shell', 'cat /proc/uptime /proc/stat /proc/pressure/cpu /proc/pressure/memory /proc/pressure/io')
        except BaseException as error:
            record['afterSnapshotError'] = type(error).__name__
        record['collectorCalls'] = calls
        record['status'] = 'captured-awaiting-analysis' if record.get('traceBytes', 0) > 0 and not record.get('error') and record.get('ownStopConfirmed') else 'incomplete'
        dump(out / 'diagnostic-run.json', record)
    return exit_code


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=('run', 'analyze'))
    p.add_argument('--sample', choices=SAMPLES, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--command-file', type=Path)
    p.add_argument('--adb', default='adb')
    p.add_argument('--serial', default='emulator-5554', choices=('emulator-5554',))
    p.add_argument('--trace-processor', type=Path)
    a = p.parse_args()
    if a.mode == 'run':
        require(a.command_file is not None, 'Original command required')
        return run(a)
    require(a.trace_processor is not None, 'Pinned trace processor required')
    from analyze_input_scheduler_trace import analyze
    result = analyze(a.out.resolve(), a.trace_processor.resolve())
    return 0 if result.get('status') == 'complete-diagnostic-evidence' else 1


if __name__ == '__main__':
    sys.exit(main())
