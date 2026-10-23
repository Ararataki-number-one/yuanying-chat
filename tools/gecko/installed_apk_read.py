"""Read one actual installed APK with uncompressed ADB SYNC and no byte fallback."""
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time


class InstalledApkReadError(ValueError):
    def __init__(self, diagnostics):
        self.diagnostics = diagnostics
        super().__init__('Actual installed APK read failed: ' + json.dumps(diagnostics, sort_keys=True))


def _disk(path):
    try:
        usage = shutil.disk_usage(path)
        return dict(total=usage.total, used=usage.used, free=usage.free)
    except OSError as error:
        return dict(error=str(error))


def _stderr(raw):
    raw = raw or b''
    if isinstance(raw, str):
        raw = raw.encode('utf-8', errors='replace')
    limit = 65536
    return dict(stderr=raw[-limit:].decode('utf-8', errors='replace'), stderrBytes=len(raw),
                stderrTruncated=len(raw) > limit)


def _stdout(raw):
    raw = raw or b''
    if isinstance(raw, str):
        raw = raw.encode('utf-8', errors='replace')
    limit = 65536
    return dict(cliStdout=raw[-limit:].decode('utf-8', errors='replace'),
                cliStdoutBytes=len(raw), cliStdoutSha256=hashlib.sha256(raw).hexdigest(),
                cliStdoutTruncated=len(raw) > limit)


def _file_identity(path):
    digest, size = hashlib.sha256(), 0
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            size += len(block); digest.update(block)
    return size, digest.hexdigest()


def _record(path, receipt):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    except OSError as error:
        # A full filesystem must not replace the original transfer failure.
        receipt['diagnosticsWriteError'] = str(error)
    if receipt['status'] != 'verified-bytes':
        print(json.dumps(receipt, sort_keys=True), file=sys.stderr, flush=True)


def read_installed_apk(*, adb, serial, installed_path, destination, expected_sha256,
                       expected_bytes, diagnostics, label, timeout=30):
    """One bounded binary read, followed by exact size/hash verification.

    The caller still audits ZIP/DEX/SDK/source assets on this actual transferred
    file. Failure removes only our exclusive partial file; no retry, install,
    test invocation, shell metacharacters or compiled-file substitution exists.
    """
    destination, diagnostics = Path(destination), Path(diagnostics)
    receipt = dict(schema=1, scope='host-read-only-installed-apk-byte-transfer', status='failed',
                   transport='adb-sync-uncompressed', dataSource='destination-file',
                   adbTrace='sync,transport,sockets,sysdeps',
                   label=label, installedApkPath=installed_path, destination=str(destination),
                   expectedBytes=expected_bytes, expectedSha256=expected_sha256,
                   timeoutSeconds=timeout, returnCode=None, stdoutBytes=0, stdoutSha256=None,
                   actualFileBytes=0, actualFileSha256=None,
                   stderr='', stderrBytes=0, stderrTruncated=False,
                   cliStdout='', cliStdoutBytes=0, cliStdoutSha256=None, cliStdoutTruncated=False,
                   hostDiskBefore=_disk(destination.parent), startedAtMonotonicNanos=time.monotonic_ns(),
                   actualInstalledApkRead=False, actualAndroidFixtureExecution=False,
                   retryPerformed=False, compiledFileFallback=False, partialCleaned=False)
    owned = False
    owned_identity = None
    try:
        # Retain the canonical actual pm path guard; never select a compiled file.
        if (not isinstance(installed_path, str)
                or not re.fullmatch(r'/data/app/[A-Za-z0-9_./~+=-]+/base\.apk', installed_path)
                or str(PurePosixPath(installed_path)) != installed_path
                or '..' in PurePosixPath(installed_path).parts):
            raise ValueError('Unsafe or noncanonical actual installed base APK path')
        if type(expected_bytes) is not int or expected_bytes <= 0 or not isinstance(expected_sha256, str) or not re.fullmatch('[0-9a-f]{64}', expected_sha256):
            raise ValueError('Exact selected APK byte count and SHA256 required')
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 30:
            raise ValueError('Installed byte read must use a finite deadline at most 30 seconds')
        # Reserve the final file exclusively. ADB only writes a new file inside
        # our private 0700 staging directory, never an existing caller pathname.
        with destination.open('xb') as output:
            owned = True
            before = os.fstat(output.fileno())
            owned_identity = (before.st_dev, before.st_ino)
            with tempfile.TemporaryDirectory(prefix='.installed-apk-pull-', dir=destination.parent) as staging:
                transferred = Path(staging) / 'actual-installed.apk'
                command = [str(adb), '-s', serial, 'pull', '-Z', installed_path, str(transferred)]
                receipt['command'] = command
                try:
                    # SYNC can return rc1 and delete its partial file without
                    # printing the underlying read/EOF error. Trace this one
                    # host-side identity read only, outside the input workload.
                    # Do not change its command, deadline, or once-only rule.
                    environment = dict(os.environ, ADB_TRACE=receipt['adbTrace'])
                    result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                            stderr=subprocess.PIPE, timeout=timeout, check=False,
                                            env=environment)
                    receipt.update(returnCode=result.returncode, **_stderr(result.stderr), **_stdout(result.stdout))
                finally:
                    # This is a host-local copy of the one actual device read,
                    # including partial bytes on failure; it cannot use a build APK.
                    try:
                        transferred_state = transferred.lstat()
                    except FileNotFoundError:
                        transferred_state = None
                    if transferred_state is not None:
                        if not stat.S_ISREG(transferred_state.st_mode):
                            raise ValueError('ADB staging destination is not a regular file')
                        handle = os.open(transferred, os.O_RDONLY | os.O_NOFOLLOW)
                        with os.fdopen(handle, 'rb') as actual:
                            if (os.fstat(actual.fileno()).st_dev, os.fstat(actual.fileno()).st_ino) != (transferred_state.st_dev, transferred_state.st_ino):
                                raise ValueError('ADB staging file ownership changed')
                            shutil.copyfileobj(actual, output, 1024 * 1024)
                        output.flush()
            after = destination.lstat()
            if not stat.S_ISREG(after.st_mode) or (after.st_dev, after.st_ino) != owned_identity:
                raise ValueError('Actual installed APK destination ownership changed')
        # Compatibility names describe the actual destination file, not ADB's
        # progress text. CLI stdout is separately bounded diagnostic evidence.
        receipt['stdoutBytes'], receipt['stdoutSha256'] = _file_identity(destination)
        receipt.update(actualFileBytes=receipt['stdoutBytes'], actualFileSha256=receipt['stdoutSha256'])
        if result.returncode != 0:
            raise ValueError('ADB direct read returned nonzero exit status')
        if receipt['stdoutBytes'] != expected_bytes or receipt['stdoutSha256'] != expected_sha256:
            raise ValueError('Actual installed bytes differ from selected APK size/SHA256')
        receipt.update(status='verified-bytes', actualInstalledApkRead=True)
    except Exception as error:
        receipt.update(failureType=type(error).__name__, error=str(error))
        if isinstance(error, subprocess.TimeoutExpired):
            receipt.update(**_stderr(error.stderr), **_stdout(error.stdout))
        own_path = False
        if owned:
            try:
                current = destination.lstat()
                own_path = stat.S_ISREG(current.st_mode) and (current.st_dev, current.st_ino) == owned_identity
            except OSError as inspection_error:
                receipt['partialOwnershipInspectionError'] = str(inspection_error)
        if own_path:
            try:
                receipt['stdoutBytes'], receipt['stdoutSha256'] = _file_identity(destination)
                receipt.update(actualFileBytes=receipt['stdoutBytes'], actualFileSha256=receipt['stdoutSha256'])
            except OSError as read_error:
                receipt['partialInspectionError'] = str(read_error)
            try:
                destination.unlink(); receipt['partialCleaned'] = True
            except OSError as cleanup_error:
                receipt['partialCleanupError'] = str(cleanup_error)
        elif owned:
            receipt['partialCleanupSkipped'] = 'Destination no longer refers to the exclusively reserved file'
        receipt.update(hostDiskAfter=_disk(destination.parent), completedAtMonotonicNanos=time.monotonic_ns())
        _record(diagnostics, receipt)
        raise InstalledApkReadError(receipt) from error
    receipt.update(hostDiskAfter=_disk(destination.parent), completedAtMonotonicNanos=time.monotonic_ns())
    _record(diagnostics, receipt)
    return receipt
