#!/usr/bin/env python3
"""Run environment-model fixtures only after matching installed APK bytes to a clean source build."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = 'local.pocketchat.test'
STAMP = 'assets/pocketchat-integration-build.json'


def verify(report, minimum, require_total=False):
    if report.get('status') != 'passed' or report.get('actualAndroidExecution') is not True or report.get('synthetic') is not True:
        raise ValueError('Fixture did not report successful actual synthetic Android execution')
    if type(report.get('passed')) is not int or report['passed'] < minimum or report.get('error') or report.get('failureType'):
        raise ValueError('Fixture assertions failed or were incomplete')
    if require_total:
        checks = report.get('checks')
        if not isinstance(checks, list) or len(checks) != report.get('total') or report['passed'] != len(checks) or any(not isinstance(item, dict) or item.get('pass') is not True for item in checks):
            raise ValueError('Catalog check list is incomplete')


def expected_build(apk, source, tree, version, code):
    with ZipFile(apk) as archive:
        raw = archive.read(STAMP)
    stamp = json.loads(raw)
    if stamp.get('schema') != 1 or stamp.get('dirtySource') is not False or stamp.get('sourceCommit') != source or stamp.get('sourceTree') != tree:
        raise ValueError('Local APK was not built from the current clean source commit/tree')
    if stamp.get('version') != version or stamp.get('versionCode') != code:
        raise ValueError('Local APK version does not match current Gradle metadata')
    if stamp.get('sdkCoordinate') != 'org.mozilla.geckoview:geckoview:157.0.20261005135250':
        raise ValueError('Local APK stamp does not identify the pinned official SDK')
    digest = hashlib.sha256()
    with apk.open('rb') as stream:
        for block in iter(lambda:stream.read(65536),b''):
            digest.update(block)
    return dict(stamp, package=PACKAGE, apkSha256=digest.hexdigest(), apkBytes=apk.stat().st_size,
                buildStampSha256=hashlib.sha256(raw).hexdigest())


def verify_installed(installed, expected):
    for key in ('schema','package','sourceCommit','sourceTree','dirtySource','version','versionCode','sdkCoordinate','apkSha256','apkBytes','buildStampSha256'):
        if installed.get(key) != expected.get(key):
            raise ValueError('Installed test APK differs from the expected build: ' + key)
    return installed


def bind_report(report, identity):
    # Existing fixture identities must agree; never replace a different source with host HEAD.
    if report.get('sourceCommit') not in (None, identity['sourceCommit']):
        raise ValueError('Fixture source differs from the verified installed APK')
    report['sourceCommit'] = identity['sourceCommit']
    report['buildIdentity'] = identity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', required=True)
    parser.add_argument('--apk', required=True, type=Path, help='Exact locally built .test APK installed on the device')
    parser.add_argument('--serial', default='emulator-5554')
    parser.add_argument('--timeout', type=int, default=120)
    args = parser.parse_args()
    if args.timeout < 1 or args.timeout > 600:
        parser.error('Timeout must be 1..600 seconds')
    output = ROOT / 'work/gecko-integration'
    output.mkdir(parents=True, exist_ok=True)
    source = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    tree = subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=ROOT,text=True).strip()
    settings = (ROOT / 'app/build.gradle').read_text()
    version = re.search(r"versionName '([0-9]+\.[0-9]+\.[0-9]+)'",settings).group(1)
    code = int(re.search(r'versionCode ([0-9]+)',settings).group(1))
    expected = expected_build(args.apk.resolve(), source, tree, version, code)
    def adb(*parts, check=True):
        return subprocess.run([args.adb,'-s',args.serial,*parts],check=check,text=True,capture_output=True,timeout=30).stdout
    def installed_build():
        raw = adb('exec-out','content','read','--uri','content://' + PACKAGE + '.evidence/build-identity')
        return verify_installed(json.loads(raw),expected)
    installed_build()
    for activity, endpoint, minimum, complete in [
        ('EnvironmentSpecIntegrationActivity','environment-spec',20,False),
    ]:
        path = output / (endpoint + '-results.json')
        path.unlink(missing_ok=True)
        # Only the fixed synthetic package is cleared; no user package argument exists.
        adb('shell','am','force-stop',PACKAGE)
        adb('shell','pm','clear',PACKAGE)
        adb('logcat','-c')
        identity = installed_build()
        adb('shell','am','start','-W','-n',PACKAGE + '/local.pocketchat.' + activity)
        deadline = time.monotonic() + args.timeout
        try:
            while time.monotonic() < deadline:
                raw = adb('exec-out','content','read','--uri','content://' + PACKAGE + '.evidence/' + endpoint,check=False)
                if raw.lstrip().startswith('{'):
                    report = json.loads(raw)
                    verify(report,minimum,complete)
                    verify_installed(installed_build(),identity)
                    bind_report(report,identity)
                    report['androidSdk'] = int(adb('shell','getprop','ro.build.version.sdk').strip())
                    report['executionScope'] = 'Actual synthetic Android SQLite/Keystore/environment-model execution; installed APK/source bound; no real account or webpage identity claim'
                    path.write_text(json.dumps(report,ensure_ascii=False,indent=2) + '\n')
                    print(json.dumps({'fixture':activity,'passed':report['passed'],'sourceCommit':identity['sourceCommit'],'apkSha256':identity['apkSha256']}))
                    break
                time.sleep(1)
            else:
                raise TimeoutError('No complete Android report: ' + activity)
        except Exception:
            (output / (endpoint + '-failure-log.txt')).write_text(adb('logcat','-d',check=False))
            raise
        finally:
            adb('shell','am','force-stop',PACKAGE,check=False)


if __name__ == '__main__':
    main()
