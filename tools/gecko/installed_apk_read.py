"""Read one actual installed APK without adb SYNC compression or byte fallback."""
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
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
                   label=label, installedApkPath=installed_path, destination=str(destination),
                   expectedBytes=expected_bytes, expectedSha256=expected_sha256,
                   timeoutSeconds=timeout, returnCode=None, stdoutBytes=0, stdoutSha256=None,
                   stderr='', stderrBytes=0, stderrTruncated=False,
                   hostDiskBefore=_disk(destination.parent), startedAtMonotonicNanos=time.monotonic_ns(),
                   actualInstalledApkRead=False, actualAndroidFixtureExecution=False,
                   retryPerformed=False, compiledFileFallback=False, partialCleaned=False)
    owned = False
    try:
        # adb combines exec-out arguments on the remote side. Restrict the pm
        # path to canonical Android package paths with no quoting operators.
        if (not isinstance(installed_path, str)
                or not re.fullmatch(r'/data/app/[A-Za-z0-9_./~+=-]+/base\.apk', installed_path)
                or str(PurePosixPath(installed_path)) != installed_path
                or '..' in PurePosixPath(installed_path).parts):
            raise ValueError('Unsafe or noncanonical actual installed base APK path')
        if type(expected_bytes) is not int or expected_bytes <= 0 or not isinstance(expected_sha256, str) or not re.fullmatch('[0-9a-f]{64}', expected_sha256):
            raise ValueError('Exact selected APK byte count and SHA256 required')
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 30:
            raise ValueError('Installed byte read must use a finite deadline at most 30 seconds')
        command = [str(adb), '-s', serial, 'exec-out', 'cat', installed_path]
        receipt['command'] = command
        with destination.open('xb') as output:
            owned = True
            result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=output,
                                    stderr=subprocess.PIPE, timeout=timeout, check=False)
        receipt.update(returnCode=result.returncode, **_stderr(result.stderr))
        receipt['stdoutBytes'], receipt['stdoutSha256'] = _file_identity(destination)
        if result.returncode != 0:
            raise ValueError('ADB direct read returned nonzero exit status')
        if receipt['stdoutBytes'] != expected_bytes or receipt['stdoutSha256'] != expected_sha256:
            raise ValueError('Actual installed bytes differ from selected APK size/SHA256')
        receipt.update(status='verified-bytes', actualInstalledApkRead=True)
    except Exception as error:
        receipt.update(failureType=type(error).__name__, error=str(error))
        if isinstance(error, subprocess.TimeoutExpired):
            receipt.update(**_stderr(error.stderr))
        if owned and destination.is_file():
            try:
                receipt['stdoutBytes'], receipt['stdoutSha256'] = _file_identity(destination)
            except OSError as read_error:
                receipt['partialInspectionError'] = str(read_error)
            try:
                destination.unlink(); receipt['partialCleaned'] = True
            except OSError as cleanup_error:
                receipt['partialCleanupError'] = str(cleanup_error)
        receipt.update(hostDiskAfter=_disk(destination.parent), completedAtMonotonicNanos=time.monotonic_ns())
        _record(diagnostics, receipt)
        raise InstalledApkReadError(receipt) from error
    receipt.update(hostDiskAfter=_disk(destination.parent), completedAtMonotonicNanos=time.monotonic_ns())
    _record(diagnostics, receipt)
    return receipt
