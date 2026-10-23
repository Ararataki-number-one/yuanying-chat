"""Read actual installed APK ranges through framed, non-PTY ADB, without retries."""
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
import time


class InstalledApkReadError(ValueError):
    def __init__(self, diagnostics):
        self.diagnostics = diagnostics
        super().__init__('Actual installed APK read failed: ' + json.dumps(diagnostics, sort_keys=True))


# Bound each stream and its host allocation. Ranges are contiguous, read once,
# and checked individually as well as by the unchanged whole-file identity.
RANGE_BYTES = 4 * 1024 * 1024


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
    """One bounded read of each APK range, followed by exact size/hash verification.

    The caller still audits ZIP/DEX/SDK/source assets on this actual transferred
    file. Failure removes only our exclusive partial file; no retry, install,
    test invocation, shell metacharacters or compiled-file substitution exists.
    """
    destination, diagnostics = Path(destination), Path(diagnostics)
    receipt = dict(schema=1, scope='host-read-only-installed-apk-byte-transfer', status='failed',
                   transport='adb-shell-v2-no-pty-ranged', dataSource='binary-stdout-destination-file',
                   adbTrace='adb,transport,sockets',
                   label=label, installedApkPath=installed_path, destination=str(destination),
                   expectedBytes=expected_bytes, expectedSha256=expected_sha256,
                   timeoutSeconds=timeout, returnCode=None, stdoutBytes=0, stdoutSha256=None,
                   actualFileBytes=0, actualFileSha256=None,
                   stderr='', stderrBytes=0, stderrTruncated=False,
                   cliStdout='', cliStdoutBytes=0, cliStdoutSha256=None, cliStdoutTruncated=False,
                   hostDiskBefore=_disk(destination.parent), startedAtMonotonicNanos=time.monotonic_ns(),
                   actualInstalledApkRead=False, actualAndroidFixtureExecution=False,
                   retryPerformed=False, compiledFileFallback=False, partialCleaned=False,
                   rangeBytes=RANGE_BYTES, ranges=[])
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
        # Reserve the destination exclusively. Shell v2 supplies remote exit
        # statuses and separate stderr; -T forbids terminal transformations.
        # Never replay a failed range or resume across a transport failure.
        with destination.open('xb') as output:
            owned = True
            before = os.fstat(output.fileno())
            owned_identity = (before.st_dev, before.st_ino)
            # The canonical absolute path cannot be an option and the whitelist
            # excludes shell syntax. No login shell, PTY, or alternate file is used.
            environment = dict(os.environ, ADB_TRACE=receipt['adbTrace'])
            deadline = time.monotonic() + timeout
            # An exactly aligned file requires a final zero-length EOF range;
            # otherwise a matching prefix could hide appended device bytes.
            for index, offset in enumerate(range(0, expected_bytes + 1, RANGE_BYTES)):
                count = min(RANGE_BYTES, expected_bytes - offset)
                command = [str(adb), '-s', serial, 'shell', '-T', 'dd',
                           'if=' + installed_path, 'bs=' + str(RANGE_BYTES),
                           'skip=' + str(index), 'count=1', 'status=none']
                receipt['command'] = command
                part = dict(index=index, offset=offset, expectedBytes=count, returnCode=None,
                            actualBytes=0, status='failed')
                receipt['ranges'].append(part)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(command, timeout)
                try:
                    result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                            stderr=subprocess.PIPE, timeout=remaining, check=False,
                                            env=environment)
                except subprocess.TimeoutExpired as error:
                    # Record partial bytes, never decode APK contents into logs.
                    if error.stdout:
                        output.write(error.stdout)
                        output.flush()
                        part['actualBytes'] = len(error.stdout)
                    raise
                output.write(result.stdout)
                output.flush()
                part.update(returnCode=result.returncode, actualBytes=len(result.stdout),
                            sha256=hashlib.sha256(result.stdout).hexdigest())
                receipt.update(returnCode=result.returncode, **_stderr(result.stderr))
                after = destination.lstat()
                if not stat.S_ISREG(after.st_mode) or (after.st_dev, after.st_ino) != owned_identity:
                    raise ValueError('Actual installed APK destination ownership changed')
                if result.returncode != 0:
                    raise ValueError('ADB direct range read returned nonzero exit status')
                if len(result.stdout) != count:
                    raise ValueError('Actual installed APK range has incorrect byte count')
                part['status'] = 'verified-length'
        # Compatibility names describe actual raw device bytes. No progress or
        # log text is accepted instead, even when the ADB process exits zero.
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
            receipt.update(**_stderr(error.stderr))
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
