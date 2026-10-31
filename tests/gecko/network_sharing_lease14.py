"""Compose the existing exact foreign-source lease around the sharing fixture.

The staged visual APK is an actual byte copy of the current integration build
(build_ui_baseline.py and ci_bundle.py restore). Recheck that equality here;
never redirect a path or substitute a compiled file for installed byte proof.
The original sharing flow must still execute all of its own assertions.
"""
import hashlib
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

from ui_settings_services_device11 import prepare_workflow, finish_workflow


def file_digest(path):
    path = Path(path)
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise RuntimeError('Sharing lease requires ordinary current APK files')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= 256 * 1024 * 1024:
            raise RuntimeError('Sharing lease APK input is unavailable or exceeds its bound')
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
        after = os.fstat(stream.fileno())
    if (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise RuntimeError('Sharing lease APK changed while being read')
    return digest.hexdigest()


def prepare(root, out, args):
    def adb(*parts):
        return subprocess.check_output([args.adb, '-s', args.serial, *parts], timeout=90).decode(errors='replace')
    run = os.environ.get('GITHUB_RUN_ID', '')
    ci = os.environ.get('CI') == 'true' and isinstance(run, str) and re.fullmatch('[1-9][0-9]{0,19}', run) is not None
    if not ci:
        # Preserve the original guard's no-APK/no-device non-CI path. A normal
        # standalone sharing run need not stage the separate visual APK.
        return prepare_workflow(adb, serial=args.serial, environment=os.environ, root=root, source=None,
                                record_path=out / 'network-sharing-settings-services-isolation.json')
    integration = root / 'app/build/outputs/apk/integration/app-x86_64-integration.apk'
    staged = out / 'ui-current.apk'
    original_digest = file_digest(integration)
    if file_digest(staged) != original_digest:
        raise RuntimeError('Sharing and staged current APK bytes differ; original inputs are unchanged')
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True, timeout=15).strip()
    # The visual runner already provides this selected-source import directory;
    # the sharing runner originally imports only the parent tools namespace.
    sys.path.insert(0, str(root / 'tools/gecko'))
    lease = prepare_workflow(adb, serial=args.serial, environment=os.environ, root=root, source=source,
                             record_path=out / 'network-sharing-settings-services-isolation.json')
    lease.record.update(sharingIntegrationApkSha256=original_digest,
                        sharingAndStagedCurrentApkBytesMatched=True,
                        fullQualificationAcceptance=False)
    return lease


def finish(lease):
    # The caller is in its original finally. Preserve an original workload or
    # diagnostic exception explicitly when exact state restoration also fails.
    original = sys.exception()
    lease.record['sharingFlowReturnedWithoutError'] = original is None
    result = dict(status='passed' if original is None else 'failed')
    try:
        finish_workflow(lease, result)
    except Exception as restoration_error:
        if original is not None:
            raise restoration_error from original
        raise
