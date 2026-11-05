#!/usr/bin/env python3
"""Run the additional source-bound real Android Gecko environment-policy gate.

Only synthetic, freshly CA-trusted HTTPS origins are served. No production TLS
setting, Android timezone, remote service, signing key or existing gate changes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/gecko'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from profile_invocation_contract import expected_build, verify_installed
from fingerprint_fixture_server import EphemeralCertificates, AndroidUserCa, GUEST_PORT
from newworker_fixture_server import WorkerFixtureServer
from check_gecko_environment_policy_evidence import (
    SOURCE_INPUTS, FIXTURE_TYPE, REPORT_NAME, expected_clock,
    verify_gecko_environment_policy_evidence, strict_json,
)

REPORT_URI = 'content://local.pocketchat.test.gecko-environment-policy-evidence/report'
ACTIVITY = 'local.pocketchat.test/local.pocketchat.GeckoEnvironmentPolicyIntegrationActivity'
MAX_ACTIVITY_BYTES = 1024 * 1024


def activity_start_args(nonce, source, leaf, ca):
    if not re.fullmatch(r'[0-9a-f]{32}', nonce) or not re.fullmatch(r'[0-9a-f]{40}', source) or not all(re.fullmatch(r'[0-9a-f]{64}', value) for value in (leaf, ca)):
        raise ValueError('Invalid source-bound Gecko policy launch')
    tokens = ['am', 'start', '-W', '-n', ACTIVITY, '--es', 'runNonce', nonce,
              '--es', 'sourceCommit', source, '--ei', 'fixturePort', str(GUEST_PORT),
              '--es', 'fixtureEngine', 'gecko', '--es', 'expectedLeafSha256', leaf,
              '--es', 'publicCaPemSha256', ca]
    return ['shell', shlex.join(tokens)]


def source_inputs():
    # Include the fixed checker contract plus every app Java/extension resource:
    # no selected runtime helper may silently change during this workload.
    paths = {ROOT / name for name in SOURCE_INPUTS}
    paths.update((ROOT / 'app/src/main/java').rglob('*.java'))
    paths.update((ROOT / 'app/src/main/assets').rglob('*.js'))
    paths.update((ROOT / 'app/src/main/assets').rglob('*.json'))
    paths.add(ROOT / 'tests/gecko/BrowserFingerprintIntegrationActivity.java')
    paths.add(ROOT / 'tests/gecko/assets/worker-policy-page.js')
    return sorted(paths)


def read_activity(raw, nonce, source, tree, identity):
    if len(raw) > MAX_ACTIVITY_BYTES:
        raise ValueError('Synthetic Gecko policy report exceeds bound')
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return None
    if type(value) is not dict or value.get('runNonce') != nonce:
        return None
    # Preserve strictness before reserializing the device bytes. Otherwise a
    # duplicate key or NaN could disappear before the final file checker sees it.
    value = strict_json(raw)
    if value.get('sourceCommit') != source or value.get('sourceTree') != tree or value.get('engine') != 'gecko' or value.get('fixtureType') != FIXTURE_TYPE:
        raise ValueError('Gecko policy source/tree/engine differs')
    verify_installed(value.get('buildIdentity', {}), identity)
    return value


def failure_summary(activity):
    """Bounded synthetic state only; never dump certificates, page text or images."""
    if not isinstance(activity, dict):
        return {'stage': 'unavailable'}
    result = {key: activity.get(key) for key in (
        'status', 'stage', 'failedAtStage', 'failure', 'checks', 'currentTimeZonePolicy',
        'lastNativeReadback', 'lifecycle')}
    result['nativeEvents'] = activity.get('nativeEvents', [])[-12:]
    raw = activity.get('lastPageObservation', {})
    def document(row):
        if not isinstance(row, dict):
            return {}
        return {key: row.get(key) for key in ('documentId', 'origin', 'phase', 'firstInline',
                'secure', 'nativeTimeZone', 'nativeUserAgent', 'markerComplete',
                'networkAllowed', 'markerError') if key in row}
    if isinstance(raw, dict):
        result['lastPageObservation'] = dict(
            page=document(raw.get('page', {})),
            frames=[document(row) for row in raw.get('frames', [])[:2] if isinstance(row, dict)],
            workers=raw.get('workers', {}))
    return result


def write_report(path, report):
    raw = (json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode()
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError('Gecko environment report exceeds bound')
    temporary = path.with_suffix('.tmp')
    temporary.write_bytes(raw)
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', default='adb')
    parser.add_argument('--serial', default='emulator-5554')
    parser.add_argument('--output', type=Path, default=ROOT / 'work/browser-acceptance')
    args = parser.parse_args()
    if args.serial != 'emulator-5554':
        parser.error('Only the controlled emulator target is allowed')
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip():
        raise ValueError('Clean committed Gecko policy source required')
    args.output.mkdir(parents=True, exist_ok=True)

    def adb(*values, check=True, timeout=30):
        return subprocess.run([args.adb, '-s', args.serial, *values], check=check,
                              capture_output=True, timeout=timeout)

    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    tree = subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], cwd=ROOT, text=True).strip()
    settings = (ROOT / 'app/build.gradle').read_text()
    identity = expected_build(ROOT / 'app/build/outputs/apk/integration/app-x86_64-integration.apk',
                              source, tree, re.search(r"versionName '([^']+)'", settings).group(1),
                              int(re.search(r'versionCode (\d+)', settings).group(1)))
    paths = source_inputs()
    hashes = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    nonce = uuid.uuid4().hex
    error = None
    certificates = server = ca = None
    reversed_port = False
    host_tls, activity = {}, None
    cleanup = dict(appStopped=False, reverseRemoved=False, caRemoved=False, privateMaterialRemoved=False)
    report = dict(schema=1, fixtureType=FIXTURE_TYPE, status='running', sourceCommit=source,
                  sourceTree=tree, runNonce=nonce, expectedBuildIdentity=identity,
                  actualAndroidExecution=False, actualGeckoExecution=False,
                  actualAndroidWebViewExecution=False, actualDesktopChromiumExecution=False,
                  actualPublicWebsiteExecution=False, actualDevicePerformanceMeasurement=False,
                  fingerprintProtectionVerified=False, workerCoverageVerified=False,
                  serviceWorkerCoverageVerified=False)
    try:
        if adb('shell', 'getprop', 'ro.kernel.qemu').stdout.decode().strip() != '1':
            raise ValueError('Actual controlled Android emulator required')
        installed = json.loads(adb('exec-out', 'content', 'read', '--uri', 'content://local.pocketchat.test.evidence/build-identity').stdout)
        verify_installed(installed, identity)
        system_zone = adb('shell', 'getprop', 'persist.sys.timezone').stdout.decode('ascii').strip()
        independent_clock = expected_clock(system_zone)
        report['systemTimeZone'] = dict(zoneId=system_zone, source='android-getprop-persist.sys.timezone',
                                      januaryOffsetMinutes=independent_clock['january']['offsetMinutes'],
                                      julyOffsetMinutes=independent_clock['july']['offsetMinutes'])
        certificates = EphemeralCertificates()
        binding = dict(sourceCommit=source, sourceTree=tree, runNonce=nonce,
                       integrationApkSha256=identity['apkSha256'],
                       sdkRunId=identity['sdkBuildIdentity']['runId'],
                       sdkRunAttempt=identity['sdkBuildIdentity']['runAttempt'])
        server = WorkerFixtureServer(certificates, (ROOT / 'tests/gecko/assets/worker-policy-page.js').read_text(),
                                     binding, gecko_script=(ROOT / 'tests/gecko/assets/gecko-environment-policy-page.js').read_text()).start()
        ca = AndroidUserCa(adb, certificates)
        ca.install()
        if any(('tcp:' + str(GUEST_PORT)) in line.split() for line in adb('reverse', '--list').stdout.decode('ascii').splitlines()):
            raise ValueError('Guest Gecko policy port already mapped; refusing replacement')
        reversed_port = True
        adb('reverse', 'tcp:' + str(GUEST_PORT), 'tcp:' + str(server.port))
        host_tls = dict(certificates.public, binding=binding, trustInstallation=ca.receipt, guestPort=GUEST_PORT)
        if adb('shell', 'pm', 'clear', 'local.pocketchat.test').stdout.decode().strip() != 'Success':
            raise ValueError('Fresh integration-only Gecko policy data required')
        if adb('shell', 'id', '-u').stdout.decode().strip() != '2000':
            raise ValueError('Gecko policy evidence requires shell UID2000')
        adb('shell', 'am', 'force-stop', 'local.pocketchat.test')
        server.begin('gecko')
        adb(*activity_start_args(nonce, source, certificates.leaf_sha, certificates.ca_sha))
        # New independent workload; no original 31/49/12 timing is changed.
        deadline = time.monotonic() + 660
        while time.monotonic() < deadline:
            raw = adb('exec-out', 'content', 'read', '--uri', REPORT_URI, check=False, timeout=15).stdout
            current = read_activity(raw, nonce, source, tree, identity)
            if current is not None:
                activity = current
                if current.get('status') in ('passed', 'failed'):
                    break
            time.sleep(.2)
        if activity is not None:
            activity['fixture'] = server.snapshot('gecko')
        if activity is None or activity.get('status') != 'passed':
            raise AssertionError('Gecko environment fixture failed or timed out: ' +
                                 str((activity or {}).get('stage', 'unavailable')) + ' / ' +
                                 str((activity or {}).get('failure', 'no terminal report')))
        if adb('shell', 'getprop', 'persist.sys.timezone').stdout.decode('ascii').strip() != system_zone:
            raise ValueError('Android system timezone changed during independent environment workload')
        report.update(status='passed', actualAndroidExecution=True, actualGeckoExecution=True)
    except Exception as failure:
        error = failure
        report.update(status='failed', error=type(failure).__name__ + ': ' + str(failure))
    finally:
        actions = [('appStopped', lambda: adb('shell', 'am', 'force-stop', 'local.pocketchat.test'))]
        if server is not None:
            if activity is not None:
                activity['fixture'] = server.snapshot('gecko')
            actions.append((None, server.close))
        if reversed_port:
            def remove_reverse():
                adb('reverse', '--remove', 'tcp:' + str(GUEST_PORT))
                host_tls['reverseRemoved'] = True
            actions.append(('reverseRemoved', remove_reverse))
        if ca is not None:
            actions.append(('caRemoved', ca.remove))
        if certificates is not None:
            def remove_material():
                certificates.close()
                host_tls['privateMaterialRemoved'] = not certificates.directory.exists()
                if not host_tls['privateMaterialRemoved']:
                    raise ValueError('Ephemeral Gecko policy private material remains')
            actions.append(('privateMaterialRemoved', remove_material))
        for key, action in actions:
            try:
                action()
                if key is not None:
                    cleanup[key] = True
            except Exception as failure:
                report.setdefault('cleanupErrors', []).append(type(failure).__name__)
                error = error or failure
                report.update(status='failed', error='Ephemeral Gecko policy cleanup failed')
        if server is not None and activity is not None:
            # Include requests arriving between terminal publication and the
            # native app stop. Server.close joins its connections; rows remain.
            activity['fixture'] = server.snapshot('gecko')
        unchanged = all(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == hashes[str(path.relative_to(ROOT))] for path in paths)
        report.update(activity=activity, hostTls=host_tls, sourceFiles=hashes, cleanup=cleanup,
                      executionInputsUnchanged=unchanged,
                      scope='Actual controlled Android MainActivity policy UI, exact native session/context receipts, raw first-inline Date/Intl and Worker/server HTTP identity. Service Worker timezone remains an independently reported limitation. No complete fingerprint, arbitrary-site or device-performance claim.')
        if not unchanged:
            error = error or ValueError('Gecko policy execution inputs changed')
            report.update(status='failed', error='Gecko policy execution inputs changed')
        output = args.output / REPORT_NAME
        write_report(output, report)
        if error is None:
            try:
                verify_gecko_environment_policy_evidence(args.output, source, identity)
            except Exception as rejected:
                error = rejected
                report.update(status='failed', validationError=str(rejected))
                write_report(output, report)
        if error is not None:
            print(json.dumps(dict(geckoPolicyFailure=failure_summary(activity)), ensure_ascii=False))
        print(json.dumps(dict(status=report['status'], sourceCommit=source, runNonce=nonce, output=str(output))))
    if error is not None:
        raise error


if __name__ == '__main__':
    main()
