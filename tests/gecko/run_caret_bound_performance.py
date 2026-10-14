#!/usr/bin/env python3
"""Read-only APK/SDK identity around one unchanged original performance invocation."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/gecko'))
from caret_build_identity import audit_apk, digest, embedded_identity, require, strict_json, validate_sdk_receipt
import sdk_identity_contract as sdk_contract

PACKAGE = 'local.pocketchat.test'
RUNNER = 'tests/gecko/run_gecko_performance.py'
ACTIVITY = 'tests/gecko/GeckoPerformanceIntegrationActivity.java'
STAMP = 'assets/pocketchat-integration-build.json'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', required=True)
    parser.add_argument('--serial', default='emulator-5554')
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--out', type=Path, required=True, help='Original output directory; must have no prior performance report or sidecar')
    for field in ('build-receipt', 'sdk-receipt', 'sdk-aar', 'official-sdk-aar', 'integration-apk'):
        parser.add_argument('--' + field, type=Path, required=True)
    args = parser.parse_args()
    root, out = args.root.resolve(), args.out.resolve()
    require(out == root / 'work/gecko-integration', 'Unchanged original runner uses exactly work/gecko-integration')
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / 'gecko-performance-results.json'
    sidecar_path = out / 'gecko-performance-build-identity.json'
    require(not report_path.exists() and not sidecar_path.exists(), 'Refuse a repeated invocation or retained performance report')
    build = strict_json(args.build_receipt.read_bytes())
    sdk = validate_sdk_receipt(args.sdk_receipt, args.sdk_aar, root, args.official_sdk_aar)
    identity = embedded_identity(sdk, args.sdk_receipt)
    source, tree = sdk['sourceCommit'], sdk['sourceTree']
    require(subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip() == source,
            'Checkout is not selected SDK source')
    require(subprocess.check_output(['git', 'rev-parse', source + '^{tree}'], cwd=root, text=True).strip() == tree,
            'SDK receipt tree differs from actual selected Git source')
    require(not subprocess.check_output(['git', 'diff', '--name-only', source], cwd=root, text=True).strip(),
            'Tracked source differs from selected source before original invocation')
    for field in ('sourceCommit', 'runId', 'runAttempt', 'sdkReceiptSha256', 'sdkAarSha256',
                  'sdkClassJarSha256', 'sdkEditableClassSha256', 'sdkManifestSha256', 'normalMode', 'sdkObserverIncluded'):
        require(build.get(field) == identity[field], 'Original invocation build identity differs: ' + field)
    require(digest(args.integration_apk) == build.get('integrationApkSha256'), 'Compiled integration APK hash differs')

    def source_reader(selected, name):
        return subprocess.check_output(['git', 'show', selected + ':' + name], cwd=root, stderr=subprocess.PIPE)

    runner_raw, activity_raw = source_reader(source, RUNNER), source_reader(source, ACTIVITY)
    require((root / RUNNER).read_bytes() == runner_raw and (root / ACTIVITY).read_bytes() == activity_raw,
            'Protected original runner or Activity differs from selected source')
    compiled_audit = audit_apk(args.integration_apk)

    def adb(*parts):
        return subprocess.check_output([args.adb, '-s', args.serial, *parts], text=True, timeout=30)

    def snapshot(label):
        paths = [line[len('package:'):] for line in adb('shell', 'pm', 'path', PACKAGE).splitlines()
                 if line.startswith('package:')]
        require(len(paths) == 1 and paths[0].startswith('/data/app/'), 'Expected one actual installed .test base APK; split APK unsupported')
        with tempfile.TemporaryDirectory(prefix='caret-performance-' + label + '-', dir=out) as temp:
            apk = Path(temp) / 'base.apk'
            adb('pull', paths[0], str(apk))
            actual_hash = digest(apk)
            require(actual_hash == build['integrationApkSha256'], 'Actual installed APK differs ' + label)
            audit = audit_apk(apk)
            require(audit == compiled_audit, 'Actual installed APK definitions/caret asset differ ' + label)
            with zipfile.ZipFile(apk) as archive:
                sdk_asset = sdk_contract.sdk_from_apk(archive, source, tree, source_reader)
                require(sdk_asset['sdkBuildReceiptSha256'] == digest(args.sdk_receipt)
                        and sdk_asset['runId'] == build['runId'] and sdk_asset['runAttempt'] == build['runAttempt'],
                        'Actual installed common SDK receipt/run differs ' + label)
                stamp_raw = archive.read(STAMP)
                stamp = strict_json(stamp_raw)
            require(stamp.get('schema') == 1 and stamp.get('sourceCommit') == source
                    and stamp.get('sourceTree') == tree and stamp.get('dirtySource') is False,
                    'Actual installed original source stamp differs ' + label)
            common = dict(stamp)
            common.update({key: sdk_asset[key] for key in sdk_contract.SDK_FIELDS})
            common.update(sdkBuildIdentity=sdk_asset, package=PACKAGE, apkBytes=apk.stat().st_size,
                          apkSha256=actual_hash, buildStampSha256=hashlib.sha256(stamp_raw).hexdigest(),
                          scope='Installed synthetic integration APK bytes and embedded source stamp only')
            return dict(apkSha256=actual_hash, installedApkPath=paths[0], apkDefinitionAudit=audit,
                        commonInstalledIdentity=common)

    before = snapshot('before')
    command = [sys.executable, str(root / RUNNER), '--adb', args.adb, '--serial', args.serial]
    # No diagnostic flags, pacing, retries, source edits or report rewriting.
    outcome = subprocess.run(command, cwd=root, check=False)
    require(report_path.is_file(), 'Original runner produced no raw performance report')
    raw = report_path.read_bytes()
    report = strict_json(raw)
    after = snapshot('after')
    require(before == after, 'Installed APK/source/SDK changed during the single original invocation')
    require(report_path.read_bytes() == raw, 'Original raw report changed while identity was captured')
    sidecar = dict(schema=1, sourceCommit=source, sourceTree=tree, runId=build['runId'], runAttempt=build['runAttempt'],
                   sdkManifestSha256=sdk['sdkManifestSha256'], sdkReceiptSha256=digest(args.sdk_receipt),
                   integrationApkSha256=build['integrationApkSha256'], buildReceiptSha256=digest(args.build_receipt),
                   rawReportSha256=hashlib.sha256(raw).hexdigest(), rawReportBytes=len(raw),
                   runnerSha256=hashlib.sha256(runner_raw).hexdigest(), activitySha256=hashlib.sha256(activity_raw).hexdigest(),
                   invocationCount=1, invocationRepositoryRoot=str(root), command=command,
                   before=before, after=after, runnerExitCode=outcome.returncode,
                   actualInstalledApkRead=True, rawReportUnmodified=True, diagnosticOnly=False,
                   actualAndroidExecution=report.get('actualAndroidExecution') is True,
                   scope='One unchanged original runner call; before/after actual installed APK/SDK byte evidence. Raw report is unchanged.')
    with sidecar_path.open('x') as stream:
        json.dump(sidecar, stream, indent=2); stream.write('\n')
    require(report_path.read_bytes() == raw, 'Raw original report was modified after sidecar publication')
    require(outcome.returncode == 0 and report.get('status') == 'passed', 'Original performance invocation failed; sidecar preserves failed raw evidence')
    print(json.dumps(dict(status='passed', rawReportSha256=sidecar['rawReportSha256'],
                         sidecarSha256=digest(sidecar_path), invocationCount=1, rawReportUnmodified=True)))


if __name__ == '__main__':
    main()
