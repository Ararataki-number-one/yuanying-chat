#!/usr/bin/env python3
"""Run environment-model fixtures only after matching installed APK bytes to a clean source build."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
import uuid
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = 'local.pocketchat.test'
STAMP = 'assets/pocketchat-integration-build.json'


# The runner and public evidence gate share the same pure validators.
import sys
sys.path.insert(0, str(ROOT / 'tools/gecko'))
from profile_invocation_contract import (verify, expected_build, verify_installed,
    bind_report, verify_invocation, verify_diagnostic)
from template_invocation_contract import verify_template_report, expected_check_names


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
    if subprocess.check_output(['git','status','--porcelain','--untracked-files=normal'],cwd=ROOT,text=True).strip():
        raise ValueError('Fixture execution requires a clean committed host source tree')
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
        ('EnvironmentSpecIntegrationActivity','environment-spec',20,True),
        ('EnvironmentIntentIntegrationActivity','environment-intent',1,True),
        ('GeckoIdentityPrototypeIntegrationActivity','gecko-identity-prototype',1,True),
        ('GeckoTemplateIntegrationActivity','gecko-template',len(expected_check_names()),True),
    ]:
        path = output / (endpoint + '-results.json')
        path.unlink(missing_ok=True)
        # Only the fixed synthetic package is cleared; no user package argument exists.
        adb('shell','am','force-stop',PACKAGE)
        adb('shell','pm','clear',PACKAGE)
        adb('logcat','-c')
        identity = installed_build()
        nonce=uuid.uuid4().hex
        (output / (endpoint + '-runner-log.json')).unlink(missing_ok=True)
        adb('shell','am','start','-W','-n',PACKAGE + '/local.pocketchat.' + activity,
            '--es','sourceCommit',source,'--es','runNonce',nonce)
        deadline = time.monotonic() + args.timeout
        try:
            while time.monotonic() < deadline:
                raw = adb('exec-out','content','read','--uri','content://' + PACKAGE + '.evidence/' + endpoint,check=False)
                if raw.lstrip().startswith('{'):
                    report = json.loads(raw)
                    path.write_text(raw,encoding='utf-8')
                    verify_invocation(report,identity,nonce)
                    verify(report,minimum,complete)
                    verify_installed(installed_build(),identity)
                    if endpoint=='gecko-identity-prototype':
                        verify_diagnostic(report)
                    if endpoint=='gecko-template':
                        verify_template_report(report)
                    sdk=int(adb('shell','getprop','ro.build.version.sdk').strip())
                    if report.get('androidSdk')!=sdk:
                        raise ValueError('Device SDK observation does not match report')
                    (output / (endpoint + '-runner-log.json')).write_text(json.dumps({
                        'schema':1,'status':'passed','sourceCommit':source,'runNonce':nonce,
                        'buildIdentity':identity,'reportSha256':hashlib.sha256(raw.encode()).hexdigest(),
                        'reportBytes':len(raw.encode()),'installedBeforeAndAfterMatched':True,
                        'rawReportPreserved':True,'androidSdk':sdk,
                        'diagnosticOnly':endpoint=='gecko-identity-prototype',
                        'scope':'Installed test APK/source and invocation-bound raw Android report; prototype remains diagnostic, not template acceptance'
                    },indent=2)+'\n')
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
