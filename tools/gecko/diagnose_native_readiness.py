#!/usr/bin/env python3
"""Observe one unchanged native-ADB bootstrap on a fresh synthetic emulator.

This does not run an application workload, retry setup, register a second native
transport, or turn a later successful observation into bootstrap acceptance.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import sys
import time

SOURCE = '757e0a500f2c59e02caf719c4e6a24e0d64c120b'
BUILD_RUN = '39935761203'
BUILD_ATTEMPT = '1'
APK = 'app/build/outputs/apk/integration/app-x86_64-integration.apk'
SETUP = 'tools/gecko/prepare_native_adb.py'
CNXN = int.from_bytes(b'CNXN', 'little')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def observed_text(value):
    if value is None:
        return ''
    if isinstance(value, bytes):
        value = value.decode('utf-8', errors='replace')
    return value[:65536]


class StateObserver:
    """Delegate the original call unchanged; retain its already captured result."""
    def __init__(self, run, adb):
        self.run, self.adb, self.rows = run, str(adb), []

    def __call__(self, command, *args, **kwargs):
        observe = command == [self.adb, '-s', 'emulator-5554', 'get-state']
        if not observe:
            return self.run(command, *args, **kwargs)
        started = time.monotonic_ns()
        row = {'command': list(command), 'startedMonotonicNs': started}
        try:
            result = self.run(command, *args, **kwargs)
            row.update(exitCode=result.returncode, stdout=observed_text(result.stdout),
                       stderr=observed_text(result.stderr), timedOut=False)
            return result
        except subprocess.TimeoutExpired as error:
            row.update(exitCode=None, timedOut=True, stdout=observed_text(error.stdout),
                       stderr=observed_text(error.stderr), timeoutSeconds=error.timeout)
            raise
        except BaseException as error:
            row.update(errorType=type(error).__name__, error=str(error))
            raise
        finally:
            row['elapsedMs'] = (time.monotonic_ns() - started) / 1000000
            self.rows.append(row)


def post_command(adb, parts):
    command = [str(adb), *parts]
    row = {'command': command, 'postSetupOnly': True}
    start = time.monotonic_ns()
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=4)
        row.update(exitCode=result.returncode, stdout=observed_text(result.stdout),
                   stderr=observed_text(result.stderr), timedOut=False)
    except subprocess.TimeoutExpired as error:
        row.update(exitCode=None, stdout=observed_text(error.stdout),
                   stderr=observed_text(error.stderr), timedOut=True)
    except OSError as error:
        row.update(errorType=type(error).__name__, error=str(error))
    row['elapsedMs'] = (time.monotonic_ns() - start) / 1000000
    return row


def probe_header(stream):
    """Read only the fixed header, never an AUTH challenge or other payload."""
    raw, deadline = b'', time.monotonic() + 3
    while len(raw) < 24:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('ADB response header exceeded its total deadline')
        stream.settimeout(remaining)
        block = stream.recv(24 - len(raw))
        if not block:
            raise EOFError('Peer closed before a complete ADB header')
        raw += block
    command, argument0, argument1, size, checksum, magic = struct.unpack('<6I', raw)
    require(magic == command ^ 0xffffffff, 'Invalid ADB header magic')
    require(size <= 1024 * 1024, 'Unexpected ADB payload size')
    name = command.to_bytes(4, 'little').decode('ascii', errors='replace')
    require(name in ('CNXN', 'AUTH', 'CLSE'), 'Unexpected initial ADB response')
    return {'responseCommand': name, 'argument0': argument0, 'argument1': argument1,
            'payloadBytesAdvertised': size, 'payloadRead': False}


def post_tcp_probe():
    result = {'address': '127.0.0.1', 'port': 5555, 'attempts': 1,
              'postSetupOnly': True, 'authResponseSent': False,
              'applicationCommandsSent': False, 'tcpAccepted': False,
              'connectTimeoutSeconds': 3, 'responseHeaderDeadlineSeconds': 3}
    started = time.monotonic_ns()
    try:
        with socket.create_connection(('127.0.0.1', 5555), timeout=3) as stream:
            result['tcpAccepted'] = True
            # A generic ADB host banner contains no key or account identifier.
            # Stop after the response header: never answer an AUTH challenge.
            banner = b'host::\0'
            request = struct.pack('<6I', CNXN, 0x01000000, 1024 * 1024,
                                  len(banner), sum(banner), CNXN ^ 0xffffffff) + banner
            stream.sendall(request)
            result.update(probe_header(stream))
    except (OSError, EOFError, ValueError) as error:
        result.update(errorType=type(error).__name__, error=str(error))
    result['elapsedMs'] = (time.monotonic_ns() - started) / 1000000
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-root', type=Path, required=True)
    parser.add_argument('--adb', type=Path, required=True)
    parser.add_argument('--monitor', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--sample', choices=list('123456'), required=True)
    args = parser.parse_args()
    root, out, adb = args.baseline_root.resolve(), args.out.resolve(), args.adb.resolve()
    out.mkdir(parents=True, exist_ok=True)
    require(not (out / 'readiness-results.json').exists(), 'Never replace an existing diagnostic')
    record = {'schema': 1, 'status': 'in_progress', 'sample': args.sample,
              'predeclaredSamples': list('123456'), 'sourceCommit': SOURCE,
              'originalBuildRunId': BUILD_RUN, 'originalBuildRunAttempt': BUILD_ATTEMPT,
              'diagnosticRunId': os.environ.get('GITHUB_RUN_ID', ''),
              'diagnosticRunAttempt': os.environ.get('GITHUB_RUN_ATTEMPT', ''),
              'originalWorkloadInvoked': False, 'actualGeckoExecution': False,
              'applicationAcceptance': False, 'releaseAcceptance': False,
              'setupInvocations': 0, 'setupReplayed': False,
              'scope': 'One original synthetic bootstrap; original get-state results and strictly post-result transport observations only.'}
    write_json(out / 'readiness-results.json', record)
    try:
        def git(*parts):
            return subprocess.check_output(['git', *parts], cwd=root, text=True, timeout=15).strip()
        require(git('rev-parse', 'HEAD') == SOURCE and not git('status', '--porcelain'),
                'Exact clean frozen baseline checkout required')
        index_path = root / 'work/gecko-integration/ci-build-index.json'
        index = json.loads(index_path.read_text())
        require(index['sourceCommit'] == SOURCE and index['sourceTree'] == git('rev-parse', 'HEAD^{tree}')
                and index['runId'] == BUILD_RUN and index['runAttempt'] == BUILD_ATTEMPT,
                'Restored original build identity differs')
        rows = [row for row in index['files'] if row['path'] == APK]
        require(len(rows) == 1, 'Exactly one original integration APK required')
        apk = root / APK
        require(apk.stat().st_size == rows[0]['bytes'] and digest(apk) == rows[0]['sha256'],
                'Original compiled integration APK bytes differ')
        setup = root / SETUP
        original_bytes = subprocess.check_output(['git', 'show', SOURCE + ':' + SETUP], cwd=root, timeout=15)
        require(setup.read_bytes() == original_bytes, 'Original setup script was changed')
        native_report = root / 'work/gecko-integration/native-adb-setup-results.json'
        require(not native_report.exists(), 'Original setup has already been invoked')
        record.update(sourceTree=index['sourceTree'], apkSha256=rows[0]['sha256'],
                      apkBytes=rows[0]['bytes'], originalSetupSha256=digest(setup),
                      buildIndexSha256=digest(index_path), diagnosticToolSha256=digest(__file__))
        spec = importlib.util.spec_from_file_location('observed_original_native_setup', setup)
        original = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(original)
        saved_run, saved_argv = subprocess.run, sys.argv
        observer = StateObserver(saved_run, str(adb))
        try:
            subprocess.run = observer
            sys.argv = [str(setup), '--adb', str(adb), '--apk', str(apk), '--monitor', str(args.monitor.resolve())]
            record['setupInvocations'] = 1
            original.main()
            record['originalSetupOutcome'] = 'passed'
        except Exception as error:
            record.update(originalSetupOutcome='failed', originalErrorType=type(error).__name__,
                          originalError=str(error))
        finally:
            subprocess.run, sys.argv = saved_run, saved_argv
            record['originalGetStateObservations'] = observer.rows
        require(native_report.is_file(), 'Original setup did not write its required receipt')
        native = json.loads(native_report.read_text())
        require(native['sourceCommit'] == SOURCE and native['originalWorkloadInvoked'] is False
                and native['actualGeckoExecution'] is False and native['applicationAcceptance'] is False,
                'Original receipt identity or diagnostic-only scope differs')
        require(native['status'] == record['originalSetupOutcome'], 'Original outcome was not preserved')
        shutil.copyfile(native_report, out / native_report.name)
        record['originalSetupReceiptSha256'] = digest(native_report)
        # These commands follow the frozen original outcome. None can qualify,
        # retry or repair that outcome; they inspect only this empty CI emulator.
        commands = [('devices', '-l'), ('-s', 'emulator-5556', 'get-state'),
                    ('-s', 'emulator-5556', 'shell', 'getprop', 'init.svc.adbd'),
                    ('-s', 'emulator-5556', 'shell', 'getprop', 'service.adb.tcp.port'),
                    ('-s', 'emulator-5556', 'shell', 'ss', '-ltn'),
                    ('-s', 'emulator-5556', 'shell', 'ip', '-4', '-o', 'addr', 'show'),
                    ('-s', 'emulator-5556', 'shell', 'ip', '-4', 'route'),
                    ('-s', 'emulator-5554', 'get-state')]
        if native.get('confirmedQemu') is True:
            record['postSetupObservations'] = [post_command(adb, list(parts)) for parts in commands]
            try:
                # Do not send an ADB header to an unrelated local listener if
                # setup stopped before establishing this exact QEMU forward.
                original.verify_forward(native.get('afterUsernet', ''))
            except ValueError:
                record['postSetupTcpProbeSkipped'] = 'Original setup did not prove the exact synthetic QEMU forwarding rule'
            else:
                record['postSetupTcpProbe'] = post_tcp_probe()
            record['postProbeDevices'] = post_command(adb, ['devices', '-l'])
        else:
            record['postSetupObservationSkipped'] = 'Original setup did not confirm the synthetic emulator'
        record['status'] = 'observed'
    except Exception as error:
        record.update(status='diagnostic_failed', errorType=type(error).__name__, error=str(error))
        raise
    finally:
        write_json(out / 'readiness-results.json', record)
    print(json.dumps({'status': record['status'], 'sample': args.sample,
                      'originalSetupOutcome': record['originalSetupOutcome'],
                      'originalGetStateObservations': len(record['originalGetStateObservations']),
                      'applicationAcceptance': False, 'originalWorkloadInvoked': False}))
    # The complete diagnostic retains setup failure as a failed CI step, even
    # if a later raw TCP connection or state observation happens to succeed.
    return 0 if record['originalSetupOutcome'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
