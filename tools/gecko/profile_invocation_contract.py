#!/usr/bin/env python3
"""Portable source/APK/invocation validators; no device execution or application imports."""
import hashlib
import json
import re
from zipfile import ZipFile

STAMP = "assets/pocketchat-integration-build.json"
PACKAGE = "local.pocketchat.test"


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
        if archive.namelist().count(STAMP) != 1:
            raise ValueError('Exactly one integration source stamp is required')
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
    # A host cannot manufacture a missing source or replace a device identity.
    if report.get('sourceCommit') != identity['sourceCommit']:
        raise ValueError('Fixture source differs from the verified installed APK')
    verify_installed(report.get('buildIdentity', {}), identity)



def verify_invocation(report, identity, nonce):
    if not re.fullmatch('[0-9a-f]{32}', nonce) or report.get('runNonce') != nonce:
        raise ValueError('Report belongs to another fixture invocation')
    bind_report(report, identity)



def verify_diagnostic(report):
    if report.get('diagnosticOnly') is not True or report.get('releaseAcceptance') is not False:
        raise ValueError('Prototype cannot claim template or release acceptance')
    if report.get('actualGeckoExecution') is not True or report.get('publicNetworkTraffic') is not False:
        raise ValueError('A controlled actual Gecko prototype report is required')
    cases = report.get('cases')
    if not isinstance(cases, list) or [case.get('index') for case in cases] != [0, 1, 2, 3]:
        raise ValueError('Prototype cases are incomplete')
    if any(case.get('status') != 'passed' for case in cases) or sum(len(case.get('sessions', [])) for case in cases) != 5:
        raise ValueError('All five actual session observations are required')
    if 'Service Worker' not in report.get('uncovered', []) or 'unsupported' not in report.get('independentTimezone', ''):
        raise ValueError('Prototype limitations must remain explicit')

